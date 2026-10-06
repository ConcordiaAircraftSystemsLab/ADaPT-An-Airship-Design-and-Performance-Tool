# -*- coding: utf-8 -*-
"""
ADaPT UI-facing mission, route, weather, fleet and operational DOE driver.

This module uses the canonical ``run_MDA.py`` builder.  Route/weather logic is
kept at the operational layer, while aerodynamic power, installed-power
feasibility, mission energy and consumable requirements are evaluated by the
current coupled ADaPT model.

Core conventions
----------------
1. ``AirshipAnalysisGroup`` is built only through ``run_MDA.build_problem``.
2. ``installed_shaft_power`` is TOTAL aircraft propulsor shaft power.
3. Current ADaPT feasibility convention is ``g <= 0``.
4. Route wind convention:
       wind_along > 0  -> tailwind
       wind_along < 0  -> headwind
   The current Performance input ``tailwind_speed`` uses the opposite sign
   convention internally, therefore this driver passes
       tailwind_speed = -wind_along.
5. The mission driver does not reconstruct drag, CL, shaft power, BSFC,
   battery mass or hydrogen-tank mass outside their authoritative components.
6. Fleet scheduling and weather sampling remain operational post-processing.

Author: Musavir Bashir
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Callable, Iterable
import math
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.gridspec import GridSpec
import openmdao.api as om


# Canonical ADaPT MDA / UI API.
try:
    from run_MDA import (
        build_problem,
        normalize_config,
        collect_results,
        collect_constraint_table,
    )
except ImportError:
    from run_MDA_updated import (
        build_problem,
        normalize_config,
        collect_results,
        collect_constraint_table,
    )


# Optional real-time weather interface.
try:
    from adapt.RealTimeWeather import RealTimeWeather
except ImportError:
    try:
        from RealTimeWeather import RealTimeWeather
    except ImportError:
        RealTimeWeather = None


# =============================================================================
# 1. Geography and wind utilities
# =============================================================================

R_EARTH_M = 6_371_000.0

# Callback:
#   (latitude_deg, longitude_deg, mission_time_hr)
#       -> (meteorological_wind_from_deg, wind_speed_mps)
WindFn = Callable[[float, float, float], Tuple[float, float]]


def haversine_distance_and_bearing(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
) -> Tuple[float, float]:
    """
    Return great-circle distance [m] and initial bearing [rad].

    Bearing is clockwise from geographic north.
    """
    lat1 = math.radians(lat1_deg)
    lon1 = math.radians(lon1_deg)
    lat2 = math.radians(lat2_deg)
    lon2 = math.radians(lon2_deg)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(
        math.sqrt(a),
        math.sqrt(max(1.0 - a, 0.0)),
    )
    distance_m = R_EARTH_M * c

    y = math.sin(dlon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1)
        * math.cos(lat2)
        * math.cos(dlon)
    )
    bearing_rad = math.atan2(y, x)

    return float(distance_m), float(bearing_rad)


def wind_components_from_met(
    bearing_rad: float,
    wind_from_dir_deg: float,
    wind_speed_mps: float,
) -> Tuple[float, float]:
    """
    Convert meteorological wind into track-relative components.

    Returns
    -------
    wind_along : float
        Positive = tailwind, negative = headwind.
    wind_cross : float
        Positive = crosswind from the right under this driver's convention.
    """
    track_deg = (
        math.degrees(bearing_rad) + 360.0
    ) % 360.0

    # Meteorological direction is where the wind comes FROM.
    wind_toward_deg = (
        float(wind_from_dir_deg) + 180.0
    ) % 360.0

    rel = math.radians(
        (
            (
                wind_toward_deg
                - track_deg
                + 540.0
            )
            % 360.0
        )
        - 180.0
    )

    wind_along = float(wind_speed_mps) * math.cos(rel)
    wind_cross = float(wind_speed_mps) * math.sin(rel)

    return float(wind_along), float(wind_cross)


def wind_model_constant(
    lat_deg: float,
    lon_deg: float,
    t_hours: float,
    wdir: float = 270.0,
    wspd: float = 8.0,
) -> Tuple[float, float]:
    """Constant meteorological wind fallback."""
    return float(wdir), float(wspd)


def sample_wind_along_leg(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    bearing_rad: float,
    leg_time_s_guess: float,
    wind_fn: WindFn,
    n_samples: int = 10,
    t0_hours: float = 0.0,
) -> Dict[str, Any]:
    """
    Sample the wind field along one route leg.

    Linear latitude/longitude interpolation is adequate for the present
    operational UI layer; the aircraft physics remain in ADaPT.
    """
    along = []
    cross = []
    wdir_list = []
    wspd_list = []

    ns = max(int(n_samples), 1)

    for i in range(ns):
        f = (
            i / (ns - 1)
            if ns > 1
            else 0.0
        )

        lat = lat1 + f * (lat2 - lat1)
        lon = lon1 + f * (lon2 - lon1)

        mission_time_hr = (
            float(t0_hours)
            + f * float(leg_time_s_guess) / 3600.0
        )

        wfrom, wspd = wind_fn(
            lat,
            lon,
            mission_time_hr,
        )

        walong, wcross = wind_components_from_met(
            bearing_rad,
            wfrom,
            wspd,
        )

        along.append(walong)
        cross.append(wcross)
        wdir_list.append(float(wfrom))
        wspd_list.append(float(wspd))

    return {
        "wind_along_mean": (
            float(np.mean(along))
            if along
            else 0.0
        ),
        "wind_cross_mean": (
            float(np.mean(cross))
            if cross
            else 0.0
        ),
        "wind_along_profile": np.asarray(
            along,
            dtype=float,
        ),
        "wind_cross_profile": np.asarray(
            cross,
            dtype=float,
        ),
        "wind_dir_profile": np.asarray(
            wdir_list,
            dtype=float,
        ),
        "wind_speed_profile": np.asarray(
            wspd_list,
            dtype=float,
        ),
    }


# =============================================================================
# 2. Data classes
# =============================================================================

@dataclass
class Waypoint:
    name: str
    lat_deg: float
    lon_deg: float
    refuel_allowed: bool = False


@dataclass
class LegResult:
    origin: str
    dest: str

    distance_m: float
    bearing_deg: float

    wind_along_mps: float
    wind_cross_mps: float

    flown_tas_mps: float
    ground_speed_mps: float
    time_s: float

    shaft_power_W: float

    # Primary consumable used by the architecture over this route leg.
    # For conventional/hydrogen architectures this is fuel/H2 mass.
    consumable_kg: float

    # Energy delivered/required over this route leg when available.
    energy_MJ: float

    feasible: bool
    reason: str = ""

    max_constraint_value: float = np.nan

    wind_along_profile: Optional[np.ndarray] = None
    wind_cross_profile: Optional[np.ndarray] = None
    wind_dir_profile: Optional[np.ndarray] = None
    wind_speed_profile: Optional[np.ndarray] = None

    # Backward-compatible name used by existing UI plots.
    @property
    def fuel_kg(self) -> float:
        return self.consumable_kg


@dataclass
class MissionSummary:
    trip_type: str
    feasible: bool

    total_distance_m: float
    total_time_s: float

    total_consumable_kg: float
    total_energy_MJ: float

    installed_consumable_capacity_kg: float

    notes: str

    # Baseline vehicle snapshot
    power_source: str
    mtow_kg: float
    owe_kg: float
    max_power_W: float
    ref_area_m2: float

    # Current constraints for the baseline sized vehicle.
    baseline_max_constraint_value: float

    # Backward-compatible names.
    @property
    def total_fuel_kg(self) -> float:
        return self.total_consumable_kg

    @property
    def fuel_capacity_kg(self) -> float:
        return self.installed_consumable_capacity_kg


# =============================================================================
# 3. Generic OpenMDAO helpers
# =============================================================================

def _array(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
) -> np.ndarray:
    value = prob.get_val(
        name,
        units=units,
    )
    return np.asarray(
        value,
        dtype=float,
    ).reshape(-1)


def _get(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        arr = _array(
            prob,
            name,
            units=units,
        )
        return (
            float(arr[0])
            if arr.size
            else float(default)
        )
    except Exception:
        return float(default)


def _max_value(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        arr = _array(
            prob,
            name,
            units=units,
        )
        arr = arr[np.isfinite(arr)]

        return (
            float(np.max(arr))
            if arr.size
            else float(default)
        )
    except Exception:
        return float(default)


def _first_available(
    prob: om.Problem,
    names: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in names:
        value = _get(
            prob,
            name,
            units=units,
            default=np.nan,
        )
        if np.isfinite(value):
            return value

    return float(default)


def _max_available(
    prob: om.Problem,
    names: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in names:
        value = _max_value(
            prob,
            name,
            units=units,
            default=np.nan,
        )
        if np.isfinite(value):
            return value

    return float(default)


def _set_if_present(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> bool:
    try:
        if units is None:
            prob.set_val(
                name,
                value,
            )
        else:
            prob.set_val(
                name,
                value,
                units=units,
            )
        return True
    except Exception:
        return False


def _set_vector_if_present(
    prob: om.Problem,
    name: str,
    value: float,
    n: int,
    units: Optional[str] = None,
) -> bool:
    return _set_if_present(
        prob,
        name,
        np.full(
            int(n),
            float(value),
        ),
        units=units,
    )


def _max_constraint_value(
    prob: om.Problem,
) -> float:
    df = collect_constraint_table(prob)

    if df.empty:
        return float("-inf")

    vals = pd.to_numeric(
        df["Max Value"],
        errors="coerce",
    ).to_numpy(dtype=float)

    vals = vals[np.isfinite(vals)]

    return (
        float(np.max(vals))
        if vals.size
        else float("-inf")
    )


# =============================================================================
# 4. Route/trip handling
# =============================================================================

def expand_route_for_trip_type(
    route: List[Waypoint],
    trip_type: str,
) -> List[Waypoint]:
    if trip_type == "one_way":
        return list(route)

    if trip_type == "reverse_return":
        return (
            list(route)
            + list(
                reversed(route[:-1])
            )
        )

    if trip_type == "empty_direct_return":
        return (
            list(route)
            + [route[0]]
        )

    raise ValueError(
        f"Unknown trip_type={trip_type!r}."
    )


# =============================================================================
# 5. Current ADaPT leg evaluator
# =============================================================================

PRIMARY_CONSUMABLE_SOURCES = {
    "conventional_reciprocating",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "turboprop",
    "turboelectric",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
    "conventional_battery_hybrid",
}


def _set_leg_operating_point(
    prob: om.Problem,
    cfg: Dict[str, Any],
    *,
    distance_m: float,
    tas_mps: float,
    wind_along_mps: float,
) -> None:
    """
    Apply one route-leg operating point to the current coupled model.

    Route convention:
        +wind_along = tailwind.

    Current Performance convention uses the opposite sign for
    ``tailwind_speed``, therefore ``-wind_along`` is passed to ADaPT.
    """
    n = int(cfg["num_steps"])

    _set_if_present(
        prob,
        "range",
        float(distance_m),
        units="m",
    )

    _set_vector_if_present(
        prob,
        "cruise_speed",
        float(tas_mps),
        n,
        units="m/s",
    )

    _set_if_present(
        prob,
        "tailwind_speed",
        -float(wind_along_mps),
        units="m/s",
    )


def _leg_consumable_kg(
    prob: om.Problem,
    cfg: Dict[str, Any],
) -> float:
    """
    Read leg consumable use from current ADaPT outputs.

    ``mission_consumable_mass_used`` is preferred because it represents the
    flown mission use directly.  The general required-consumable output is the
    fallback for component configurations that expose only sizing requirement.
    """
    source = cfg["power_source"]

    if source not in PRIMARY_CONSUMABLE_SOURCES:
        return 0.0

    return _first_available(
        prob,
        (
            "mission_consumable_mass_used",
            "mission_consumable_mass",
            "consumable_mass_used",
            "required_consumable_mass",
            "fuel_mass",
            "hydrogen_mass",
        ),
        units="kg",
        default=np.nan,
    )


def _leg_energy_MJ(
    prob: om.Problem,
) -> float:
    """
    Read current leg energy requirement from authoritative model outputs.
    """
    direct = _first_available(
        prob,
        (
            "mission_energy_required",
            "total_mission_energy_required",
            "required_primary_energy",
            "source_energy_required",
            "required_energy",
        ),
        units="MJ",
        default=np.nan,
    )

    if np.isfinite(direct):
        return direct

    battery_MJ = _first_available(
        prob,
        (
            "required_battery_energy",
            "battery_energy_required",
            "battery_energy",
        ),
        units="MJ",
        default=np.nan,
    )

    if np.isfinite(battery_MJ):
        return battery_MJ

    battery_Wh = _first_available(
        prob,
        (
            "required_battery_energy",
            "battery_energy_required",
            "battery_energy",
        ),
        units="W*h",
        default=np.nan,
    )

    if np.isfinite(battery_Wh):
        return battery_Wh * 3.6e-3

    return np.nan


def evaluate_leg_state(
    prob: om.Problem,
    cfg: Dict[str, Any],
    *,
    distance_m: float,
    tas_mps: float,
    wind_along_mps: float,
    ground_speed_floor_mps: float = 2.0,
) -> Dict[str, Any]:
    """
    Evaluate one route-leg speed/wind state using the current coupled model.
    """
    ground_speed_mps = (
        float(tas_mps)
        + float(wind_along_mps)
    )

    if ground_speed_mps < float(ground_speed_floor_mps):
        return {
            "feasible": False,
            "reason": (
                f"Ground speed {ground_speed_mps:.2f} m/s "
                f"is below the operational floor "
                f"{ground_speed_floor_mps:.2f} m/s."
            ),
            "tas_mps": float(tas_mps),
            "ground_speed_mps": float(ground_speed_mps),
            "time_s": 0.0,
            "shaft_power_W": np.nan,
            "consumable_kg": np.nan,
            "energy_MJ": np.nan,
            "max_constraint_value": np.inf,
        }

    _set_leg_operating_point(
        prob,
        cfg,
        distance_m=distance_m,
        tas_mps=tas_mps,
        wind_along_mps=wind_along_mps,
    )

    try:
        prob.run_model()
    except Exception as exc:
        return {
            "feasible": False,
            "reason": f"ADaPT leg evaluation failed: {exc}",
            "tas_mps": float(tas_mps),
            "ground_speed_mps": float(ground_speed_mps),
            "time_s": 0.0,
            "shaft_power_W": np.nan,
            "consumable_kg": np.nan,
            "energy_MJ": np.nan,
            "max_constraint_value": np.inf,
        }

    required_power_W = _max_available(
        prob,
        (
            "required_shaft_power",
            "shaft_power",
            "required_power",
        ),
        units="W",
        default=np.nan,
    )

    power_constraint = _max_value(
        prob,
        "power_constraint",
        default=np.nan,
    )

    # Mission duration from the route kinematics is used for fleet scheduling.
    route_time_s = (
        float(distance_m)
        / max(
            ground_speed_mps,
            1.0e-12,
        )
    )

    consumable_kg = _leg_consumable_kg(
        prob,
        cfg,
    )
    energy_MJ = _leg_energy_MJ(prob)

    max_g = _max_constraint_value(prob)

    power_ok = (
        not np.isfinite(power_constraint)
        or power_constraint <= 0.0
    )

    feasible = bool(
        power_ok
        and max_g <= 0.0
    )

    reason_parts = []

    if not power_ok:
        reason_parts.append(
            f"power constraint = {power_constraint:.3e}"
        )

    if np.isfinite(max_g) and max_g > 0.0:
        reason_parts.append(
            f"max model constraint = {max_g:.3e}"
        )

    reason = (
        "OK"
        if feasible
        else "; ".join(reason_parts)
    )

    return {
        "feasible": feasible,
        "reason": reason,
        "tas_mps": float(tas_mps),
        "ground_speed_mps": float(ground_speed_mps),
        "time_s": float(route_time_s),
        "shaft_power_W": float(required_power_W),
        "consumable_kg": float(consumable_kg),
        "energy_MJ": float(energy_MJ),
        "max_constraint_value": float(max_g),
    }


def fly_leg(
    prob: om.Problem,
    cfg: Dict[str, Any],
    dist_m: float,
    wind_along_mps: float,
    *,
    ground_speed_floor_mps: float = 2.0,
    min_tas_mps: float = 10.0,
    max_tas_mps: Optional[float] = None,
    throttle_steps: int = 30,
) -> Dict[str, Any]:
    """
    Find a feasible TAS for one route leg using repeated current-model solves.

    Search logic:
    1. Try configured cruise TAS.
    2. If the current model reports infeasibility, search downward in TAS.
    3. If route ground speed is too low, search upward to the minimum TAS that
       satisfies the ground-speed floor while remaining model-feasible.
    """
    target_tas = float(
        cfg["cruise_speed_mps"]
    )

    if max_tas_mps is None:
        max_tas_mps = 1.20 * target_tas

    max_tas_mps = max(
        float(max_tas_mps),
        float(min_tas_mps),
    )

    first = evaluate_leg_state(
        prob,
        cfg,
        distance_m=dist_m,
        tas_mps=target_tas,
        wind_along_mps=wind_along_mps,
        ground_speed_floor_mps=ground_speed_floor_mps,
    )

    if first["feasible"]:
        return first

    # If the route ground-speed floor itself is the issue, first determine the
    # minimum kinematic TAS and search upward from there.
    tas_floor = max(
        float(min_tas_mps),
        float(ground_speed_floor_mps)
        - float(wind_along_mps),
    )

    if (
        first["ground_speed_mps"]
        < float(ground_speed_floor_mps)
    ):
        speeds = np.linspace(
            tas_floor,
            max_tas_mps,
            max(int(throttle_steps), 2),
        )

        for tas in speeds:
            state = evaluate_leg_state(
                prob,
                cfg,
                distance_m=dist_m,
                tas_mps=float(tas),
                wind_along_mps=wind_along_mps,
                ground_speed_floor_mps=ground_speed_floor_mps,
            )

            if state["feasible"]:
                state["reason"] = (
                    f"Adjusted TAS to {tas:.1f} m/s "
                    f"for route wind."
                )
                return state

    # Otherwise search down from requested cruise TAS for a power-feasible state.
    lower = max(
        float(min_tas_mps),
        tas_floor,
    )

    if lower <= target_tas:
        speeds = np.linspace(
            target_tas,
            lower,
            max(int(throttle_steps), 2),
        )

        for tas in speeds:
            state = evaluate_leg_state(
                prob,
                cfg,
                distance_m=dist_m,
                tas_mps=float(tas),
                wind_along_mps=wind_along_mps,
                ground_speed_floor_mps=ground_speed_floor_mps,
            )

            if state["feasible"]:
                state["reason"] = (
                    "OK"
                    if abs(tas - target_tas) < 1.0e-9
                    else f"Throttled to {tas:.1f} m/s."
                )
                return state

    # Return the most informative first state if no candidate is feasible.
    first["reason"] = (
        "No feasible TAS found within "
        f"{min_tas_mps:.1f}–{max_tas_mps:.1f} m/s; "
        + first["reason"]
    )
    return first


# =============================================================================
# 6. Mission simulation after baseline sizing
# =============================================================================

def run_mission(
    cfg: Dict[str, Any],
    base_route: List[Waypoint],
    trip_type: str = "one_way",
    wind_fn: Optional[WindFn] = None,
    wind_constant: Optional[Dict[str, float]] = None,
    wind_samples_per_leg: int = 10,
    t0_hours: float = 0.0,
    *,
    ground_speed_floor_mps: float = 2.0,
    min_tas_mps: float = 10.0,
    max_tas_mps: Optional[float] = None,
    throttle_steps: int = 30,
    allow_enroute_refuel: bool = False,
) -> Tuple[MissionSummary, List[LegResult], Dict[str, Any]]:
    """
    Run baseline sizing once and simulate the route leg by leg.

    Vehicle sizing/configuration comes from the canonical ADaPT MDA builder.
    Each route leg is then evaluated with the current Performance/Power/Energy
    model at the sampled wind and selected TAS.
    """
    c = normalize_config(cfg)

    if wind_fn is None:
        wc = (
            {"dir": 270.0, "speed": 8.0}
            if wind_constant is None
            else dict(wind_constant)
        )

        wind_fn = lambda lat, lon, t: wind_model_constant(
            lat,
            lon,
            t,
            wc["dir"],
            wc["speed"],
        )

    route = expand_route_for_trip_type(
        base_route,
        trip_type,
    )

    if len(route) < 2:
        raise ValueError(
            "Mission route requires at least two waypoints."
        )

    # ------------------------------------------------------------------
    # Baseline vehicle sizing / analysis
    # ------------------------------------------------------------------
    prob = build_problem(c)
    prob.run_model()

    baseline = collect_results(
        prob,
        c,
    )

    scalars = baseline["scalars"]
    outputs = baseline["outputs"]

    mtow_kg = float(
        scalars.get(
            "mtow_kg",
            np.nan,
        )
    )
    owe_kg = float(
        scalars.get(
            "owe_kg",
            np.nan,
        )
    )

    installed_power_W = (
        float(
            scalars.get(
                "installed_power_kW",
                np.nan,
            )
        )
        * 1000.0
    )

    installed_consumable_kg = float(
        scalars.get(
            "installed_consumable_kg",
            0.0,
        )
    )

    ref_area_m2 = float(
        outputs.get(
            "aero_reference_area_m2",
            np.nan,
        )
    )

    baseline_max_g = _max_constraint_value(
        prob,
    )

    # ------------------------------------------------------------------
    # Route simulation
    # ------------------------------------------------------------------
    legs: List[LegResult] = []

    total_distance_m = 0.0
    total_time_s = 0.0
    total_consumable_kg = 0.0
    total_energy_MJ = 0.0

    # Consumable since the most recent permitted refuel stop.
    consumable_since_refuel_kg = 0.0

    feasible = True
    notes = ""

    mission_clock_hr = float(t0_hours)

    for i in range(
        len(route) - 1
    ):
        origin = route[i]
        dest = route[i + 1]

        dist_m, bearing_rad = (
            haversine_distance_and_bearing(
                origin.lat_deg,
                origin.lon_deg,
                dest.lat_deg,
                dest.lon_deg,
            )
        )

        bearing_deg = (
            math.degrees(bearing_rad)
            + 360.0
        ) % 360.0

        time_guess_s = (
            dist_m
            / max(
                c["cruise_speed_mps"],
                1.0,
            )
        )

        wind_samp = sample_wind_along_leg(
            origin.lat_deg,
            origin.lon_deg,
            dest.lat_deg,
            dest.lon_deg,
            bearing_rad=bearing_rad,
            leg_time_s_guess=time_guess_s,
            wind_fn=wind_fn,
            n_samples=wind_samples_per_leg,
            t0_hours=mission_clock_hr,
        )

        walong = float(
            wind_samp["wind_along_mean"]
        )
        wcross = float(
            wind_samp["wind_cross_mean"]
        )

        state = fly_leg(
            prob,
            c,
            dist_m,
            walong,
            ground_speed_floor_mps=ground_speed_floor_mps,
            min_tas_mps=min_tas_mps,
            max_tas_mps=max_tas_mps,
            throttle_steps=throttle_steps,
        )

        leg = LegResult(
            origin=origin.name,
            dest=dest.name,
            distance_m=float(dist_m),
            bearing_deg=float(bearing_deg),
            wind_along_mps=walong,
            wind_cross_mps=wcross,
            flown_tas_mps=float(
                state["tas_mps"]
            ),
            ground_speed_mps=float(
                state["ground_speed_mps"]
            ),
            time_s=float(
                state["time_s"]
            ),
            shaft_power_W=float(
                state["shaft_power_W"]
            ),
            consumable_kg=float(
                state["consumable_kg"]
            ),
            energy_MJ=float(
                state["energy_MJ"]
            ),
            feasible=bool(
                state["feasible"]
            ),
            reason=str(
                state["reason"]
            ),
            max_constraint_value=float(
                state["max_constraint_value"]
            ),
            wind_along_profile=wind_samp[
                "wind_along_profile"
            ],
            wind_cross_profile=wind_samp[
                "wind_cross_profile"
            ],
            wind_dir_profile=wind_samp[
                "wind_dir_profile"
            ],
            wind_speed_profile=wind_samp[
                "wind_speed_profile"
            ],
        )

        legs.append(leg)

        if not leg.feasible:
            feasible = False
            notes = (
                f"Leg failed: "
                f"{origin.name}->{dest.name}: "
                f"{leg.reason}"
            )
            break

        total_distance_m += leg.distance_m
        total_time_s += leg.time_s

        if np.isfinite(leg.consumable_kg):
            total_consumable_kg += leg.consumable_kg
            consumable_since_refuel_kg += leg.consumable_kg

        if np.isfinite(leg.energy_MJ):
            total_energy_MJ += leg.energy_MJ

        mission_clock_hr += (
            leg.time_s / 3600.0
        )

        # Capacity check only applies where a primary consumable is carried.
        if (
            c["power_source"]
            in PRIMARY_CONSUMABLE_SOURCES
            and installed_consumable_kg > 0.0
            and consumable_since_refuel_kg
            > installed_consumable_kg
        ):
            feasible = False
            leg.feasible = False
            leg.reason = (
                "Installed consumable capacity exceeded: "
                f"{consumable_since_refuel_kg:.1f} kg used "
                f"since last refuel > "
                f"{installed_consumable_kg:.1f} kg installed."
            )
            notes = (
                f"Consumable capacity exceeded on "
                f"{origin.name}->{dest.name}."
            )
            break

        # Optional operational refuel at destination.
        if (
            allow_enroute_refuel
            and dest.refuel_allowed
            and i < len(route) - 2
        ):
            consumable_since_refuel_kg = 0.0

    summary = MissionSummary(
        trip_type=trip_type,
        feasible=bool(feasible),
        total_distance_m=float(
            total_distance_m
        ),
        total_time_s=float(
            total_time_s
        ),
        total_consumable_kg=float(
            total_consumable_kg
        ),
        total_energy_MJ=float(
            total_energy_MJ
        ),
        installed_consumable_capacity_kg=float(
            installed_consumable_kg
        ),
        notes=notes,
        power_source=c["power_source"],
        mtow_kg=mtow_kg,
        owe_kg=owe_kg,
        max_power_W=installed_power_W,
        ref_area_m2=ref_area_m2,
        baseline_max_constraint_value=float(
            baseline_max_g
        ),
    )

    vehicle = {
        "power_source": c["power_source"],
        "mtow": mtow_kg,
        "owe": owe_kg,
        "installed_consumable_capacity": installed_consumable_kg,
        "ref_area": ref_area_m2,
        "cruise_speed": c["cruise_speed_mps"],
        "installed_shaft_power": installed_power_W,
        "baseline_max_constraint_value": baseline_max_g,
        "baseline_results": baseline,
        "config": c,
    }

    prob.cleanup()

    return summary, legs, vehicle


# =============================================================================
# 7. Fleet studies
# =============================================================================

def compute_fleet_close_time(
    trip_time_s: float,
    cargo_per_trip_kg: float,
    mission_cargo_kg: float,
    fleet_size: int,
    refuel_time_s: float = 0.0,
    unload_time_s: float = 0.0,
    crew_rest_time_s: float = 0.0,
    refuel_stops: int = 0,
) -> Dict[str, float]:
    """
    Compute trips, waves and total fleet mission-close time.
    """
    if cargo_per_trip_kg <= 0.0:
        return {
            "nt": float("inf"),
            "waves": float("inf"),
            "close_time_s": float("inf"),
        }

    trips = int(
        math.ceil(
            mission_cargo_kg
            / cargo_per_trip_kg
        )
    )

    fleet_size = max(
        int(fleet_size),
        1,
    )

    waves = int(
        math.ceil(
            trips / fleet_size
        )
    )

    cycle_s = float(
        trip_time_s
        + refuel_stops
        * refuel_time_s
        + unload_time_s
    )

    close_time_s = (
        waves * cycle_s
        + max(waves - 1, 0)
        * crew_rest_time_s
    )

    return {
        "nt": float(trips),
        "waves": float(waves),
        "close_time_s": float(
            close_time_s
        ),
    }


def count_refuel_stops(
    route: List[Waypoint],
) -> int:
    return int(
        sum(
            1
            for wp in route[1:]
            if getattr(
                wp,
                "refuel_allowed",
                False,
            )
        )
    )


# =============================================================================
# 8. Operational DOE / fleet DSE
# =============================================================================

def pareto_front(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
) -> pd.DataFrame:
    """Return 2-D minimization Pareto front."""
    d = (
        df.sort_values(x_col)
        .reset_index(drop=True)
    )

    best_y = float("inf")
    keep = []

    for _, row in d.iterrows():
        y = float(row[y_col])

        if y < best_y:
            keep.append(True)
            best_y = y
        else:
            keep.append(False)

    return d.loc[keep].copy()


def run_doe_sweep(
    base_cfg: Dict[str, Any],
    route: List[Waypoint],
    trip_type: str,
    wind_constant: Dict[str, float],
    payload_grid_kg: List[float],
    speed_grid_mps: List[float],
    fleet_grid: List[int],
    mission_cargo_kg: float,
    refuel_time_s: float = 0.0,
    unload_time_s: float = 0.0,
    crew_rest_time_s: float = 0.0,
    wind_fn: Optional[WindFn] = None,
    *,
    n_weather_trials: int = 5,
    trial_time_step_hr: float = 3.0,
    aggregate_mode: str = "worst",
    allow_enroute_refuel: bool = False,
) -> pd.DataFrame:
    """
    Operational DOE across payload, cruise speed, fleet size and weather time.

    This study repeatedly calls ``run_mission``; no subsystem physics are
    duplicated in the DOE layer.
    """
    rows = []

    expanded_route = expand_route_for_trip_type(
        route,
        trip_type,
    )

    refuel_stops = count_refuel_stops(
        expanded_route
    )

    for payload_kg in payload_grid_kg:
        for speed_mps in speed_grid_mps:
            for fleet_size in fleet_grid:

                cfg = dict(
                    base_cfg
                )

                cfg["payload_kg"] = float(
                    payload_kg
                )
                cfg["cruise_speed_mps"] = float(
                    speed_mps
                )

                times_hr = []
                consumables_kg = []
                energies_MJ = []
                feasible_trials = []
                notes = []
                mtow_trials = []
                max_power_trials_kW = []

                for trial in range(
                    int(n_weather_trials)
                ):
                    start_hr = (
                        float(trial)
                        * float(
                            trial_time_step_hr
                        )
                    )

                    summary, _, _ = run_mission(
                        cfg=cfg,
                        base_route=route,
                        trip_type=trip_type,
                        wind_fn=wind_fn,
                        wind_constant=wind_constant,
                        wind_samples_per_leg=8,
                        t0_hours=start_hr,
                        allow_enroute_refuel=allow_enroute_refuel,
                    )

                    times_hr.append(
                        summary.total_time_s
                        / 3600.0
                    )

                    consumables_kg.append(
                        summary.total_consumable_kg
                    )

                    energies_MJ.append(
                        summary.total_energy_MJ
                    )

                    feasible_trials.append(
                        bool(
                            summary.feasible
                        )
                    )

                    notes.append(
                        summary.notes
                    )

                    mtow_trials.append(
                        summary.mtow_kg
                    )

                    max_power_trials_kW.append(
                        summary.max_power_W
                        / 1000.0
                    )

                p_feasible = float(
                    np.mean(
                        feasible_trials
                    )
                )

                robust_feasible = bool(
                    all(
                        feasible_trials
                    )
                )

                if (
                    str(
                        aggregate_mode
                    ).lower()
                    == "mean"
                ):
                    trip_time_hr = float(
                        np.mean(
                            times_hr
                        )
                    )
                    trip_consumable_kg = float(
                        np.mean(
                            consumables_kg
                        )
                    )
                    trip_energy_MJ = float(
                        np.mean(
                            energies_MJ
                        )
                    )
                else:
                    trip_time_hr = float(
                        np.max(
                            times_hr
                        )
                    )
                    trip_consumable_kg = float(
                        np.max(
                            consumables_kg
                        )
                    )
                    trip_energy_MJ = float(
                        np.max(
                            energies_MJ
                        )
                    )

                fleet = compute_fleet_close_time(
                    trip_time_s=(
                        trip_time_hr
                        * 3600.0
                    ),
                    cargo_per_trip_kg=float(
                        payload_kg
                    ),
                    mission_cargo_kg=float(
                        mission_cargo_kg
                    ),
                    fleet_size=int(
                        fleet_size
                    ),
                    refuel_time_s=float(
                        refuel_time_s
                    ),
                    unload_time_s=float(
                        unload_time_s
                    ),
                    crew_rest_time_s=float(
                        crew_rest_time_s
                    ),
                    refuel_stops=int(
                        refuel_stops
                    ),
                )

                feasible = bool(
                    robust_feasible
                    and math.isfinite(
                        fleet["close_time_s"]
                    )
                )

                mtow_kg = float(
                    np.nanmean(
                        mtow_trials
                    )
                )

                # Operational cost proxy retained from the original UI study,
                # now based on the current-model consumable output.
                cost_proxy = (
                    float(
                        trip_consumable_kg
                    )
                    + 0.0005
                    * float(
                        fleet_size
                    )
                    * mtow_kg
                )

                rows.append(
                    {
                        "payload_kg": float(
                            payload_kg
                        ),
                        "cruise_speed_mps": float(
                            speed_mps
                        ),
                        "fleet_size": int(
                            fleet_size
                        ),

                        "feasible": feasible,
                        "p_feasible": p_feasible,
                        "feasible_all_trials": robust_feasible,

                        "trip_consumable_kg": float(
                            trip_consumable_kg
                        ),
                        "trip_energy_MJ": float(
                            trip_energy_MJ
                        ),
                        "trip_time_hr": float(
                            trip_time_hr
                        ),
                        "close_time_hr": float(
                            fleet["close_time_s"]
                            / 3600.0
                        ),

                        "trip_time_mean_hr": float(
                            np.mean(
                                times_hr
                            )
                        ),
                        "trip_time_p90_hr": float(
                            np.percentile(
                                times_hr,
                                90,
                            )
                        ),
                        "trip_consumable_mean_kg": float(
                            np.mean(
                                consumables_kg
                            )
                        ),
                        "trip_consumable_p90_kg": float(
                            np.percentile(
                                consumables_kg,
                                90,
                            )
                        ),
                        "trip_energy_mean_MJ": float(
                            np.mean(
                                energies_MJ
                            )
                        ),
                        "trip_energy_p90_MJ": float(
                            np.percentile(
                                energies_MJ,
                                90,
                            )
                        ),

                        "trips_needed": (
                            int(
                                fleet["nt"]
                            )
                            if math.isfinite(
                                fleet["nt"]
                            )
                            else -1
                        ),
                        "waves": (
                            int(
                                fleet["waves"]
                            )
                            if math.isfinite(
                                fleet["waves"]
                            )
                            else -1
                        ),

                        "mtow_kg": mtow_kg,
                        "installed_power_kW": float(
                            np.nanmean(
                                max_power_trials_kW
                            )
                        ),
                        "cost_proxy": float(
                            cost_proxy
                        ),
                        "notes_last": notes[-1],
                    }
                )

    df = pd.DataFrame(
        rows
    )

    # Compatibility aliases used by older plotting/UI code.
    if not df.empty:
        df["trip_fuel_kg"] = df[
            "trip_consumable_kg"
        ]

    return df


# =============================================================================
# 9. Visualization
# =============================================================================

def plot_route_map(
    route: List[Waypoint],
    title: str = "Route",
):
    lats = [
        wp.lat_deg
        for wp in route
    ]
    lons = [
        wp.lon_deg
        for wp in route
    ]

    plt.figure(
        figsize=(8, 6)
    )

    plt.plot(
        lons,
        lats,
        "o--",
    )

    for wp in route:
        plt.annotate(
            wp.name,
            (
                wp.lon_deg,
                wp.lat_deg,
            ),
            xytext=(5, 5),
            textcoords="offset points",
        )

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_leg_bars(
    legs: List[LegResult],
):
    if not legs:
        return

    labels = [
        f"{leg.origin}-{leg.dest}"
        for leg in legs
    ]

    x = np.arange(
        len(labels)
    )

    time_hr = np.asarray(
        [
            leg.time_s
            for leg in legs
        ]
    ) / 3600.0

    consumable = np.asarray(
        [
            leg.consumable_kg
            for leg in legs
        ]
    )

    gs = np.asarray(
        [
            leg.ground_speed_mps
            for leg in legs
        ]
    )

    power_kW = np.asarray(
        [
            leg.shaft_power_W
            for leg in legs
        ]
    ) / 1000.0

    for y, ylabel, title in (
        (
            time_hr,
            "Time [hr]",
            "Leg flight time",
        ),
        (
            consumable,
            "Primary consumable [kg]",
            "Leg consumable use",
        ),
        (
            gs,
            "Ground speed [m/s]",
            "Leg ground speed",
        ),
        (
            power_kW,
            "Required shaft power [kW]",
            "Leg shaft power",
        ),
    ):
        plt.figure(
            figsize=(10, 4)
        )
        plt.bar(
            x,
            y,
        )
        plt.xticks(
            x,
            labels,
            rotation=30,
            ha="right",
        )
        plt.ylabel(
            ylabel
        )
        plt.title(
            title
        )
        plt.grid(
            True,
            axis="y",
        )
        plt.tight_layout()
        plt.show()


def plot_consumable_cumulative(
    legs: List[LegResult],
    installed_capacity_kg: float,
):
    if not legs:
        return

    burn = np.asarray(
        [
            leg.consumable_kg
            for leg in legs
        ],
        dtype=float,
    )

    cumulative = np.cumsum(
        np.nan_to_num(
            burn,
            nan=0.0,
        )
    )

    x = np.arange(
        1,
        len(legs) + 1,
    )

    plt.figure(
        figsize=(8, 4)
    )

    plt.plot(
        x,
        cumulative,
        marker="o",
    )

    if (
        np.isfinite(
            installed_capacity_kg
        )
        and installed_capacity_kg > 0.0
    ):
        plt.axhline(
            installed_capacity_kg,
            linestyle="--",
        )

    plt.xlabel("Leg #")
    plt.ylabel(
        "Cumulative primary consumable [kg]"
    )
    plt.title(
        "Mission consumable state"
    )
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# Backward-compatible function name.
def plot_fuel_cumulative(
    legs: List[LegResult],
    fuel_capacity_kg: float,
):
    return plot_consumable_cumulative(
        legs,
        fuel_capacity_kg,
    )


def plot_wind_profiles(
    legs: List[LegResult],
):
    if not legs:
        return

    xs = []
    along = []
    cross = []

    cumulative_m = 0.0

    for leg in legs:
        profile_a = (
            leg.wind_along_profile
        )
        profile_c = (
            leg.wind_cross_profile
        )

        if (
            profile_a is None
            or profile_c is None
            or len(profile_a) == 0
        ):
            xs.append(
                cumulative_m
            )
            along.append(
                leg.wind_along_mps
            )
            cross.append(
                leg.wind_cross_mps
            )
            cumulative_m += (
                leg.distance_m
            )
            continue

        n = len(profile_a)

        for i in range(n):
            f = (
                i / (n - 1)
                if n > 1
                else 0.0
            )

            xs.append(
                cumulative_m
                + f * leg.distance_m
            )
            along.append(
                float(
                    profile_a[i]
                )
            )
            cross.append(
                float(
                    profile_c[i]
                )
            )

        cumulative_m += (
            leg.distance_m
        )

    xs_km = (
        np.asarray(
            xs,
            dtype=float,
        )
        / 1000.0
    )

    plt.figure(
        figsize=(9, 4)
    )
    plt.plot(
        xs_km,
        along,
    )
    plt.xlabel(
        "Route progress [km]"
    )
    plt.ylabel(
        "Along-track wind [m/s] (+tailwind)"
    )
    plt.title(
        "Wind along track"
    )
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    plt.figure(
        figsize=(9, 4)
    )
    plt.plot(
        xs_km,
        cross,
    )
    plt.xlabel(
        "Route progress [km]"
    )
    plt.ylabel(
        "Crosswind [m/s] (+from right)"
    )
    plt.title(
        "Crosswind along route"
    )
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_dse_scatter(
    df: pd.DataFrame,
    x: str = "trip_consumable_kg",
    y: str = "close_time_hr",
    color: str = "fleet_size",
):
    d = df[
        df["feasible"]
    ].copy()

    if d.empty:
        print(
            "No feasible points to plot."
        )
        return

    plt.figure(
        figsize=(7, 5)
    )

    sc = plt.scatter(
        d[x],
        d[y],
        c=d[color],
    )

    plt.xlabel(x)
    plt.ylabel(y)
    plt.title(
        "Operational design space"
    )
    plt.grid(True)

    plt.colorbar(
        sc,
        label=color,
    )

    plt.tight_layout()
    plt.show()


def plot_pareto(
    df: pd.DataFrame,
    x: str = "trip_consumable_kg",
    y: str = "close_time_hr",
):
    d = df[
        df["feasible"]
    ].copy()

    if d.empty:
        print(
            "No feasible points for Pareto plot."
        )
        return

    pf = pareto_front(
        d,
        x,
        y,
    )

    plt.figure(
        figsize=(7, 5)
    )

    plt.scatter(
        d[x],
        d[y],
        alpha=0.3,
    )

    plt.plot(
        pf[x],
        pf[y],
        marker="o",
    )

    plt.xlabel(x)
    plt.ylabel(y)
    plt.title(
        "Operational Pareto front"
    )
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# =============================================================================
# 10. Weather dashboard
# =============================================================================

class WeatherDashboard:
    """
    Route-level operational weather visualization.
    """

    def __init__(
        self,
        route: List[Waypoint],
        legs: List[LegResult],
    ):
        self.route = route
        self.legs = legs

    def _wind_to_color(
        self,
        wdir_deg,
        speed_mps,
        max_speed=30.0,
    ):
        hue = (
            float(wdir_deg)
            % 360.0
        ) / 360.0

        alpha = min(
            max(
                float(speed_mps)
                / max(
                    float(max_speed),
                    1.0e-9,
                ),
                0.30,
            ),
            1.0,
        )

        rgb = mcolors.hsv_to_rgb(
            (
                hue,
                0.8,
                0.9,
            )
        )

        return (
            *rgb,
            alpha,
        )

    def find_wp(
        self,
        name: str,
    ) -> Optional[Waypoint]:
        for wp in self.route:
            if wp.name == name:
                return wp

        return None

    def plot_dashboard(
        self,
    ):
        fig = plt.figure(
            figsize=(16, 9),
            constrained_layout=True,
        )

        gs = GridSpec(
            2,
            3,
            figure=fig,
        )

        ax_map = fig.add_subplot(
            gs[:, :2]
        )

        lats = [
            wp.lat_deg
            for wp in self.route
        ]
        lons = [
            wp.lon_deg
            for wp in self.route
        ]

        ax_map.plot(
            lons,
            lats,
            "k-",
            linewidth=1,
            alpha=0.5,
            label="Course",
        )

        ax_map.plot(
            lons,
            lats,
            "ko",
            markersize=4,
        )

        for leg in self.legs:
            wp_o = self.find_wp(
                leg.origin
            )
            wp_d = self.find_wp(
                leg.dest
            )

            if (
                wp_o is None
                or wp_d is None
            ):
                continue

            mid_lat = (
                wp_o.lat_deg
                + wp_d.lat_deg
            ) / 2.0

            mid_lon = (
                wp_o.lon_deg
                + wp_d.lon_deg
            ) / 2.0

            heading = math.radians(
                leg.bearing_deg
            )

            # Reconstruct Earth-frame vector from route-relative components.
            u_wind = (
                -leg.wind_along_mps
                * math.sin(
                    heading
                )
                + leg.wind_cross_mps
                * math.cos(
                    heading
                )
            )

            v_wind = (
                -leg.wind_along_mps
                * math.cos(
                    heading
                )
                - leg.wind_cross_mps
                * math.sin(
                    heading
                )
            )

            speed = math.sqrt(
                leg.wind_along_mps**2
                + leg.wind_cross_mps**2
            )

            wdir = (
                math.degrees(
                    math.atan2(
                        -u_wind,
                        -v_wind,
                    )
                )
                % 360.0
            )

            color = self._wind_to_color(
                wdir,
                speed,
            )

            ax_map.quiver(
                mid_lon,
                mid_lat,
                u_wind,
                v_wind,
                color=color,
                scale=100,
                width=0.005,
                headwidth=4,
            )

        for wp in self.route:
            ax_map.text(
                wp.lon_deg,
                wp.lat_deg,
                f"  {wp.name}",
                fontsize=9,
                fontweight="bold",
            )

        ax_map.set_title(
            "Operational Wind Map"
        )
        ax_map.set_xlabel(
            "Longitude"
        )
        ax_map.set_ylabel(
            "Latitude"
        )
        ax_map.grid(
            True,
            linestyle=":",
            alpha=0.6,
        )

        ax_profile1 = fig.add_subplot(
            gs[0, 2]
        )

        dists = np.cumsum(
            [0.0]
            + [
                leg.distance_m / 1000.0
                for leg in self.legs
            ]
        )

        winds_along = np.asarray(
            [0.0]
            + [
                leg.wind_along_mps
                for leg in self.legs
            ]
        )

        ax_profile1.fill_between(
            dists,
            winds_along,
            0.0,
            where=(
                winds_along >= 0.0
            ),
            alpha=0.3,
            label="Tailwind",
        )

        ax_profile1.fill_between(
            dists,
            winds_along,
            0.0,
            where=(
                winds_along < 0.0
            ),
            alpha=0.3,
            label="Headwind",
        )

        ax_profile1.plot(
            dists,
            winds_along,
            "k.-",
            lw=1,
        )

        ax_profile1.set_title(
            "Route Wind Profile"
        )
        ax_profile1.set_ylabel(
            "Along-track wind [m/s]"
        )
        ax_profile1.axhline(
            0.0,
            linewidth=1,
        )
        ax_profile1.grid(True)

        ax_profile2 = fig.add_subplot(
            gs[1, 2]
        )

        winds_cross = np.asarray(
            [0.0]
            + [
                leg.wind_cross_mps
                for leg in self.legs
            ]
        )

        ax_profile2.fill_between(
            dists,
            winds_cross,
            0.0,
            alpha=0.2,
        )

        ax_profile2.plot(
            dists,
            winds_cross,
            ".-",
            lw=1,
        )

        ax_profile2.set_title(
            "Crosswind Profile"
        )
        ax_profile2.set_xlabel(
            "Route Progress [km]"
        )
        ax_profile2.set_ylabel(
            "Crosswind [m/s]"
        )
        ax_profile2.axhline(
            0.0,
            linewidth=1,
        )
        ax_profile2.grid(True)

        plt.show()


def visualize_weather_dashboard(
    route: List[Waypoint],
    legs: List[LegResult],
):
    WeatherDashboard(
        route,
        legs,
    ).plot_dashboard()


# =============================================================================
# 11. Example route and reporting
# =============================================================================

def example_canada_route_montreal_to_halifax() -> List[Waypoint]:
    return [
        Waypoint(
            "Montreal",
            45.5017,
            -73.5673,
            refuel_allowed=True,
        ),
        Waypoint(
            "Quebec",
            46.8139,
            -71.2080,
            refuel_allowed=True,
        ),
        Waypoint(
            "Moncton",
            46.0878,
            -64.7782,
            refuel_allowed=True,
        ),
        Waypoint(
            "Halifax",
            44.6488,
            -63.5752,
            refuel_allowed=True,
        ),
    ]


def print_mission_report(
    summary: MissionSummary,
    legs: List[LegResult],
    vehicle: Dict[str, Any],
):
    print(
        "\n=== ADaPT MISSION RESULTS ==="
    )
    print(
        f"Trip type:           {summary.trip_type}"
    )
    print(
        f"Architecture:        {summary.power_source}"
    )
    print(
        f"Feasible:            {summary.feasible}"
    )
    print(
        f"Total distance:      "
        f"{summary.total_distance_m / 1000.0:.2f} km"
    )
    print(
        f"Total time:          "
        f"{summary.total_time_s / 3600.0:.2f} hr"
    )
    print(
        f"Primary consumable:  "
        f"{summary.total_consumable_kg:.2f} kg"
    )
    print(
        f"Installed capacity:  "
        f"{summary.installed_consumable_capacity_kg:.2f} kg"
    )
    print(
        f"Mission energy sum:  "
        f"{summary.total_energy_MJ:.2f} MJ"
    )

    if summary.notes:
        print(
            f"Notes:               {summary.notes}"
        )

    print(
        "\n--- Baseline sized vehicle ---"
    )
    print(
        f"MTOW [kg]:           {summary.mtow_kg:.2f}"
    )
    print(
        f"OWE [kg]:            {summary.owe_kg:.2f}"
    )
    print(
        f"Aero ref. area [m2]: {summary.ref_area_m2:.2f}"
    )
    print(
        f"Installed power [kW]:"
        f" {summary.max_power_W / 1000.0:.2f}"
    )
    print(
        f"Baseline max g:      "
        f"{summary.baseline_max_constraint_value:.6e}"
    )

    print(
        "\n--- Route legs ---"
    )

    for leg in legs:
        print(
            f"{leg.origin:10s} -> {leg.dest:10s} "
            f"{leg.distance_m / 1000.0:7.1f} km  "
            f"wind={leg.wind_along_mps:+5.1f} m/s  "
            f"cross={leg.wind_cross_mps:+5.1f} m/s  "
            f"TAS={leg.flown_tas_mps:5.1f}  "
            f"GS={leg.ground_speed_mps:5.1f}  "
            f"time={leg.time_s / 3600.0:6.2f} hr  "
            f"cons={leg.consumable_kg:8.2f} kg  "
            f"P={leg.shaft_power_W / 1000.0:7.1f} kW  "
            f"gmax={leg.max_constraint_value: .2e}  "
            f"{'OK' if leg.feasible else 'FAIL'}  "
            f"{leg.reason}"
        )


# =============================================================================
# 12. UI-facing API
# =============================================================================

def run_mission_ui(
    cfg: Dict[str, Any],
    route: List[Waypoint],
    *,
    trip_type: str = "one_way",
    wind_fn: Optional[WindFn] = None,
    wind_constant: Optional[Dict[str, float]] = None,
    wind_samples_per_leg: int = 10,
    t0_hours: float = 0.0,
    allow_enroute_refuel: bool = False,
) -> Dict[str, Any]:
    """
    UI-friendly wrapper returning named Python objects instead of a tuple.
    """
    summary, legs, vehicle = run_mission(
        cfg=cfg,
        base_route=route,
        trip_type=trip_type,
        wind_fn=wind_fn,
        wind_constant=wind_constant,
        wind_samples_per_leg=wind_samples_per_leg,
        t0_hours=t0_hours,
        allow_enroute_refuel=allow_enroute_refuel,
    )

    leg_rows = [
        {
            "origin": leg.origin,
            "destination": leg.dest,
            "distance_km": leg.distance_m / 1000.0,
            "bearing_deg": leg.bearing_deg,
            "wind_along_mps": leg.wind_along_mps,
            "wind_cross_mps": leg.wind_cross_mps,
            "tas_mps": leg.flown_tas_mps,
            "ground_speed_mps": leg.ground_speed_mps,
            "time_hr": leg.time_s / 3600.0,
            "required_shaft_power_kW": leg.shaft_power_W / 1000.0,
            "consumable_kg": leg.consumable_kg,
            "energy_MJ": leg.energy_MJ,
            "max_constraint_value": leg.max_constraint_value,
            "feasible": leg.feasible,
            "reason": leg.reason,
        }
        for leg in legs
    ]

    return {
        "summary": summary,
        "legs": legs,
        "vehicle": vehicle,
        "df_legs": pd.DataFrame(leg_rows),
    }


# =============================================================================
# 13. Direct execution example
# =============================================================================

if __name__ == "__main__":

    # ------------------------------------------------------------------
    # Current ADaPT configuration
    # ------------------------------------------------------------------
    cfg = {
        "power_source": "conventional_reciprocating",
        "airship_type": "non-rigid",
        "landing_system": "conventional",
        "num_steps": 1,

        "length_m": 53.4,
        "fineness_ratio": 4.0,
        "tail_volume_coeff_horizontal": 0.066,
        "tail_volume_coeff_vertical": 0.059,
        "tail_coefficient_method": "user",

        "payload_kg": 2000.0,
        "range_m": 1_500_000.0,
        "cruise_speed_mps": 31.0,
        "cruise_alt_m": 914.0,

        "installed_consumable_capacity_kg": 599.0,

        # TOTAL aircraft installed shaft power.
        "installed_shaft_power_W": 280_000.0,
        "n_engine": 2,

        "propeller_efficiency": 0.75,

        "ice_thermal_efficiency": 0.30,
        "gasoline_lhv_Jkg": 43.0e6,
        "fuel_reserve_fraction": 0.10,

        "lift_coeff": 0.15,
        "drag_coeff_zero": 0.03542,
        "drag_due_to_lift_factor": 0.869,

        "BR_takeoff": 0.83,
        "BR_landing": 0.90,

        "T_env_K": 281.65,
        "RH_pct": 70.0,
        "time": "day",
    }

    route = (
        example_canada_route_montreal_to_halifax()
    )

    wind_constant = {
        "dir": 270.0,
        "speed": 8.0,
    }

    # ------------------------------------------------------------------
    # Optional real-time weather
    # ------------------------------------------------------------------
    weather_engine = None

    if RealTimeWeather is not None:
        try:
            weather_engine = RealTimeWeather()
            print(
                ">>> RealTimeWeather initialized."
            )
        except Exception as exc:
            print(
                "Warning: RealTimeWeather initialization failed "
                f"({exc}); using constant-wind fallback."
            )

    def mission_wind_callback(
        lat,
        lon,
        t_hr,
    ):
        if weather_engine is not None:
            data = weather_engine.get_winds_aloft(
                lat,
                lon,
                cfg["cruise_alt_m"],
                time_offset_hours=t_hr,
            )

            return (
                data["dir_deg"],
                data["speed_mps"],
            )

        return (
            wind_constant["dir"],
            wind_constant["speed"],
        )

    trip_type = "one_way"

    # ------------------------------------------------------------------
    # Mission
    # ------------------------------------------------------------------
    result = run_mission_ui(
        cfg,
        route,
        trip_type=trip_type,
        wind_fn=mission_wind_callback,
        wind_constant=wind_constant,
        wind_samples_per_leg=12,
        allow_enroute_refuel=False,
    )

    summary = result["summary"]
    legs = result["legs"]
    vehicle = result["vehicle"]

    print_mission_report(
        summary,
        legs,
        vehicle,
    )

    # ------------------------------------------------------------------
    # Fleet study
    # ------------------------------------------------------------------
    mission_cargo_kg = 20_000.0
    fleet_size = 4

    expanded_route = (
        expand_route_for_trip_type(
            route,
            trip_type,
        )
    )

    refuel_stops = (
        count_refuel_stops(
            expanded_route
        )
    )

    fleet = compute_fleet_close_time(
        trip_time_s=summary.total_time_s,
        cargo_per_trip_kg=cfg["payload_kg"],
        mission_cargo_kg=mission_cargo_kg,
        fleet_size=fleet_size,
        refuel_time_s=30.0 * 60.0,
        unload_time_s=45.0 * 60.0,
        crew_rest_time_s=8.0 * 3600.0,
        refuel_stops=refuel_stops,
    )

    print(
        "\n=== FLEET STUDY ==="
    )
    print(
        f"Mission cargo required: "
        f"{mission_cargo_kg:.0f} kg"
    )
    print(
        f"Cargo per trip:         "
        f"{cfg['payload_kg']:.0f} kg"
    )
    print(
        f"Fleet size:             "
        f"{fleet_size}"
    )
    print(
        f"Trips needed:           "
        f"{int(fleet['nt'])}"
    )
    print(
        f"Waves:                  "
        f"{int(fleet['waves'])}"
    )
    print(
        f"Close time:             "
        f"{fleet['close_time_s'] / 3600.0:.2f} hr"
    )

    # ------------------------------------------------------------------
    # Mission plots
    # ------------------------------------------------------------------
    plot_route_map(
        route,
        title="Canada route (Montreal → Halifax)",
    )
    plot_leg_bars(
        legs
    )
    plot_consumable_cumulative(
        legs,
        summary.installed_consumable_capacity_kg,
    )
    plot_wind_profiles(
        legs
    )

    # ------------------------------------------------------------------
    # Operational DOE / fleet DSE
    # ------------------------------------------------------------------
    payload_grid = [
        1500.0,
        2000.0,
        2500.0,
    ]

    speed_grid = [
        25.0,
        31.0,
        35.0,
    ]

    fleet_grid = [
        1,
        2,
        4,
        8,
    ]

    df = run_doe_sweep(
        base_cfg=cfg,
        route=route,
        trip_type=trip_type,
        wind_constant=wind_constant,
        payload_grid_kg=payload_grid,
        speed_grid_mps=speed_grid,
        fleet_grid=fleet_grid,
        mission_cargo_kg=mission_cargo_kg,
        refuel_time_s=30.0 * 60.0,
        unload_time_s=45.0 * 60.0,
        crew_rest_time_s=8.0 * 3600.0,
        wind_fn=mission_wind_callback,
        n_weather_trials=5,
        trial_time_step_hr=3.0,
        aggregate_mode="worst",
        allow_enroute_refuel=False,
    )

    df.to_csv(
        "mission_operational_doe.csv",
        index=False,
    )

    print(
        "\n=== OPERATIONAL DOE RESULTS ==="
    )
    print(
        df.head(10).to_string(
            index=False
        )
    )

    plot_dse_scatter(
        df,
        x="trip_consumable_kg",
        y="close_time_hr",
        color="fleet_size",
    )

    plot_pareto(
        df,
        x="trip_consumable_kg",
        y="close_time_hr",
    )

    visualize_weather_dashboard(
        route,
        legs,
    )
