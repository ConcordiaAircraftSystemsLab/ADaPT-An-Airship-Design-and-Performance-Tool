# -*- coding: utf-8 -*-
"""
ADaPT Streamlit adapter for route/mission analysis.

Authoritative backend:
    adapt.run_Mission

This module contains no aircraft sizing, propulsion, aerodynamic,
energy-system, or mission physics.  It only converts the structured
mission results into UI-ready tables and scalar summaries.

Author: Musavir Bashir
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from adapt.run_Mission import (
    Waypoint,
    run_mission,
    expand_route_for_trip_type,
    count_refuel_stops,
    compute_fleet_close_time,
)


M_TO_NM = 0.000539956803


# =============================================================================
# Helpers
# =============================================================================

def _safe(value: Any, default=np.nan) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def _route_to_df(
    route: List[Waypoint],
) -> pd.DataFrame:

    return pd.DataFrame(
        [
            {
                "Waypoint": wp.name,
                "Latitude [deg]": float(wp.lat_deg),
                "Longitude [deg]": float(wp.lon_deg),
                "Refuel allowed": bool(wp.refuel_allowed),
            }
            for wp in route
        ]
    )


def _legs_to_df(
    legs: List[Any],
) -> pd.DataFrame:

    rows = []

    for leg in legs:

        rows.append(
            {
                "Origin": leg.origin,
                "Destination": leg.dest,

                "Distance [km]":
                    _safe(leg.distance_m) / 1000.0,

                "Distance [nm]":
                    _safe(leg.distance_m) * M_TO_NM,

                "Bearing [deg]":
                    _safe(leg.bearing_deg),

                "Along-track wind [m/s]":
                    _safe(leg.wind_along_mps),

                "Crosswind [m/s]":
                    _safe(leg.wind_cross_mps),

                "TAS [m/s]":
                    _safe(leg.flown_tas_mps),

                "Ground speed [m/s]":
                    _safe(leg.ground_speed_mps),

                "Flight time [hr]":
                    (
                        _safe(leg.time_s) / 3600.0
                        if _finite(leg.time_s)
                        else np.nan
                    ),

                "Required shaft power [kW]":
                    (
                        _safe(leg.shaft_power_W) / 1000.0
                        if _finite(leg.shaft_power_W)
                        else np.nan
                    ),

                "Consumable [kg]":
                    _safe(leg.consumable_kg),

                "Energy [MJ]":
                    _safe(leg.energy_MJ),

                "Max constraint":
                    _safe(
                        getattr(
                            leg,
                            "max_constraint_value",
                            np.nan,
                        )
                    ),

                "Feasible":
                    bool(leg.feasible),

                "Reason":
                    str(leg.reason),
            }
        )

    return pd.DataFrame(rows)


def _build_wind_profiles_df(
    legs: List[Any],
) -> pd.DataFrame:
    """
    Build dense route-position wind data for plotting.

    Convention:
        along > 0 -> tailwind
        along < 0 -> headwind
    """

    rows = []
    cumulative_m = 0.0

    for leg_index, leg in enumerate(legs):

        distance_m = _safe(
            getattr(leg, "distance_m", 0.0),
            0.0,
        )

        along = getattr(
            leg,
            "wind_along_profile",
            None,
        )

        cross = getattr(
            leg,
            "wind_cross_profile",
            None,
        )

        direction = getattr(
            leg,
            "wind_dir_profile",
            None,
        )

        speed = getattr(
            leg,
            "wind_speed_profile",
            None,
        )

        # Fallback to leg-average values.
        if along is None or len(along) == 0:
            along = np.asarray(
                [
                    _safe(
                        getattr(
                            leg,
                            "wind_along_mps",
                            0.0,
                        ),
                        0.0,
                    )
                ]
            )

        if cross is None or len(cross) == 0:
            cross = np.asarray(
                [
                    _safe(
                        getattr(
                            leg,
                            "wind_cross_mps",
                            0.0,
                        ),
                        0.0,
                    )
                ]
            )

        n = min(
            len(along),
            len(cross),
        )

        if direction is not None:
            n = min(n, len(direction))

        if speed is not None:
            n = min(n, len(speed))

        n = max(n, 1)

        for i in range(n):

            frac = (
                i / (n - 1)
                if n > 1
                else 0.5
            )

            rows.append(
                {
                    "leg_index": leg_index,
                    "origin": leg.origin,
                    "destination": leg.dest,

                    "route_km":
                        (
                            cumulative_m
                            + frac * distance_m
                        )
                        / 1000.0,

                    "along_wind_mps":
                        _safe(along[min(i, len(along) - 1)]),

                    "crosswind_mps":
                        _safe(cross[min(i, len(cross) - 1)]),

                    "wind_from_deg":
                        (
                            _safe(direction[i])
                            if direction is not None
                            and i < len(direction)
                            else np.nan
                        ),

                    "wind_speed_mps":
                        (
                            _safe(speed[i])
                            if speed is not None
                            and i < len(speed)
                            else np.nan
                        ),
                }
            )

        cumulative_m += distance_m

    return pd.DataFrame(rows)


# =============================================================================
# Main UI API
# =============================================================================

def run_route_mission_ui(
    cfg: Dict[str, Any],
    route: List[Waypoint],
    trip_type: str,

    *,
    wind_fn=None,
    wind_dir_deg: float = 270.0,
    wind_speed_mps: float = 8.0,
    wind_samples_per_leg: int = 10,

    ground_speed_floor_mps: float = 2.0,
    min_tas_mps: float = 10.0,
    max_tas_mps: Optional[float] = None,
    throttle_steps: int = 30,
    allow_enroute_refuel: bool = False,

    mission_cargo_kg: float = 0.0,
    fleet_size: int = 1,
    refuel_time_min: float = 0.0,
    unload_time_min: float = 0.0,
    crew_rest_hr: float = 0.0,
) -> Dict[str, Any]:
    """
    Streamlit-safe mission-analysis wrapper.
    """

    if len(route) < 2:
        raise ValueError(
            "At least two waypoints are required."
        )

    if fleet_size < 1:
        raise ValueError(
            "Fleet size must be at least 1."
        )

    wind_constant = {
        "dir": float(wind_dir_deg),
        "speed": float(wind_speed_mps),
    }

    # -------------------------------------------------------------------------
    # Run authoritative mission backend
    # -------------------------------------------------------------------------

    summary, legs, vehicle = run_mission(
        cfg=cfg,
        base_route=route,
        trip_type=trip_type,
        wind_fn=wind_fn,
        wind_constant=wind_constant,
        wind_samples_per_leg=int(wind_samples_per_leg),
        ground_speed_floor_mps=float(ground_speed_floor_mps),
        min_tas_mps=float(min_tas_mps),
        max_tas_mps=(
            None
            if max_tas_mps is None
            else float(max_tas_mps)
        ),
        throttle_steps=int(throttle_steps),
        allow_enroute_refuel=bool(allow_enroute_refuel),
    )

    # -------------------------------------------------------------------------
    # Tables
    # -------------------------------------------------------------------------

    df_route = _route_to_df(route)
    df_legs = _legs_to_df(legs)

    expanded_route = expand_route_for_trip_type(
        route,
        trip_type,
    )

    refuel_stops = count_refuel_stops(
        expanded_route
    )

    # -------------------------------------------------------------------------
    # Fleet/logistics
    # -------------------------------------------------------------------------

    payload_kg = float(
        cfg.get(
            "payload_kg",
            0.0,
        )
    )

    fleet = compute_fleet_close_time(
        trip_time_s=float(summary.total_time_s),
        cargo_per_trip_kg=payload_kg,
        mission_cargo_kg=float(mission_cargo_kg),
        fleet_size=int(fleet_size),
        refuel_time_s=float(refuel_time_min) * 60.0,
        unload_time_s=float(unload_time_min) * 60.0,
        crew_rest_time_s=float(crew_rest_hr) * 3600.0,
        refuel_stops=int(refuel_stops),
    )

    # -------------------------------------------------------------------------
    # Scalar summary
    # -------------------------------------------------------------------------

    scalars = {
        "feasible":
            bool(summary.feasible),

        "power_source":
            str(summary.power_source),

        "mtow_kg":
            float(summary.mtow_kg),

        "owe_kg":
            float(summary.owe_kg),

        "total_distance_km":
            float(summary.total_distance_m) / 1000.0,

        "total_distance_nm":
            float(summary.total_distance_m) * M_TO_NM,

        "total_time_hr":
            float(summary.total_time_s) / 3600.0,

        "total_consumable_kg":
            float(summary.total_consumable_kg),

        "total_energy_MJ":
            float(summary.total_energy_MJ),

        "installed_consumable_capacity_kg":
            float(
                summary.installed_consumable_capacity_kg
            ),

        "max_power_kW":
            float(summary.max_power_W) / 1000.0,

        "reference_area_m2":
            float(summary.ref_area_m2),

        "baseline_max_constraint":
            float(
                summary.baseline_max_constraint_value
            ),

        "refuel_stops":
            int(refuel_stops),

        "trips_needed":
            (
                int(fleet["nt"])
                if _finite(fleet["nt"])
                else np.nan
            ),

        "waves":
            (
                int(fleet["waves"])
                if _finite(fleet["waves"])
                else np.nan
            ),

        "close_time_hr":
            (
                float(fleet["close_time_s"]) / 3600.0
                if _finite(fleet["close_time_s"])
                else np.nan
            ),
    }

    # -------------------------------------------------------------------------
    # Totals table
    # -------------------------------------------------------------------------

    df_totals = pd.DataFrame(
        [
            ["Trip feasible", scalars["feasible"]],
            ["Power source", scalars["power_source"]],
            ["MTOW [kg]", scalars["mtow_kg"]],
            ["OWE [kg]", scalars["owe_kg"]],
            ["Total distance [km]", scalars["total_distance_km"]],
            ["Total distance [nm]", scalars["total_distance_nm"]],
            ["Total flight time [hr]", scalars["total_time_hr"]],
            ["Total consumable [kg]", scalars["total_consumable_kg"]],
            ["Mission energy [MJ]", scalars["total_energy_MJ"]],
            [
                "Installed consumable capacity [kg]",
                scalars["installed_consumable_capacity_kg"],
            ],
            ["Maximum required power [kW]", scalars["max_power_kW"]],
            [
                "Baseline maximum constraint",
                scalars["baseline_max_constraint"],
            ],
            ["Refuel stops", scalars["refuel_stops"]],
            ["Trips required", scalars["trips_needed"]],
            ["Fleet waves", scalars["waves"]],
            ["Fleet close time [hr]", scalars["close_time_hr"]],
        ],
        columns=[
            "Metric",
            "Value",
        ],
    )

    # -------------------------------------------------------------------------
    # Fleet table
    # -------------------------------------------------------------------------

    df_fleet = pd.DataFrame(
        [
            {
                "Fleet size":
                    int(fleet_size),

                "Mission cargo [kg]":
                    float(mission_cargo_kg),

                "Payload/trip [kg]":
                    payload_kg,

                "Trips":
                    scalars["trips_needed"],

                "Waves":
                    scalars["waves"],

                "Refuel stops/trip":
                    int(refuel_stops),

                "Close time [hr]":
                    scalars["close_time_hr"],
            }
        ]
    )

    # -------------------------------------------------------------------------
    # Wind profiles
    # -------------------------------------------------------------------------

    wind_profiles_df = (
        _build_wind_profiles_df(
            legs
        )
    )

    return {
        "summary": summary,
        "legs_obj": legs,
        "route_obj": route,
        "expanded_route_obj": expanded_route,
        "vehicle": vehicle,

        "scalars": scalars,

        "df_route": df_route,
        "df_legs": df_legs,
        "df_totals": df_totals,
        "df_fleet": df_fleet,

        "wind_profiles_df":
            wind_profiles_df,

        "notes":
            str(summary.notes),
    }