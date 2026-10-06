# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Route Mission Analysis.

Author: Musavir Bashir
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from adapt.run_Mission import Waypoint
from ui.run_mission_analysis import run_route_mission_ui
from ui_widgets import sidebar_mda_inputs

try:
    from adapt.RealTimeWeather import RealTimeWeather
except Exception:
    RealTimeWeather = None


# =============================================================================
# Page
# =============================================================================

st.set_page_config(
    page_title="ADaPT — Mission Analysis",
    page_icon="🗺️",
    layout="wide",
)

st.title("ADaPT — Mission Analysis")

st.caption(
    "Route-level operational analysis using the current coupled ADaPT "
    "airship model. Each route leg is evaluated with the authoritative "
    "performance, propulsion, energy and feasibility models."
)


# =============================================================================
# Helpers
# =============================================================================

def _finite(value):
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value, digits=1):
    if not _finite(value):
        return "—"
    return f"{float(value):,.{digits}f}"


# =============================================================================
# Common aircraft configuration
# =============================================================================

cfg = sidebar_mda_inputs()


# =============================================================================
# Session state
# =============================================================================

if "mission_route_df" not in st.session_state:

    st.session_state[
        "mission_route_df"
    ] = pd.DataFrame(
        [
            {
                "name": "Montreal",
                "lat": 45.5017,
                "lon": -73.5673,
                "refuel": True,
            },
            {
                "name": "Quebec",
                "lat": 46.8139,
                "lon": -71.2080,
                "refuel": True,
            },
            {
                "name": "Moncton",
                "lat": 46.0878,
                "lon": -64.7782,
                "refuel": True,
            },
            {
                "name": "Halifax",
                "lat": 44.6488,
                "lon": -63.5752,
                "refuel": True,
            },
        ]
    )


if "mission_result" not in st.session_state:
    st.session_state["mission_result"] = None


if "mission_weather_engine" not in st.session_state:
    st.session_state["mission_weather_engine"] = None


# =============================================================================
# Operational settings
# =============================================================================

with st.sidebar:

    st.divider()
    st.header("Mission Operations")

    trip_type = st.selectbox(
        "Trip type",
        options=[
            "one_way",
            "reverse_return",
            "empty_direct_return",
        ],
        format_func=lambda x: {
            "one_way": "One way",
            "reverse_return": "Return along route",
            "empty_direct_return": "Direct return",
        }[x],
    )

    allow_refuel = st.checkbox(
        "Allow en-route refuelling",
        value=False,
    )

    st.divider()
    st.subheader("Speed management")

    ground_speed_floor = st.number_input(
        "Minimum ground speed [m/s]",
        min_value=0.1,
        value=2.0,
        step=0.5,
    )

    min_tas = st.number_input(
        "Minimum TAS [m/s]",
        min_value=1.0,
        value=10.0,
        step=1.0,
    )

    auto_max_tas = st.checkbox(
        "Automatic maximum TAS",
        value=True,
    )

    if auto_max_tas:
        max_tas = None
    else:
        max_tas = st.number_input(
            "Maximum TAS [m/s]",
            min_value=float(min_tas),
            value=max(
                float(min_tas),
                35.0,
            ),
            step=1.0,
        )

    throttle_steps = st.number_input(
        "TAS search points",
        min_value=2,
        max_value=200,
        value=30,
        step=1,
    )

    st.divider()
    st.header("Weather")

    weather_mode = st.radio(
        "Wind source",
        ["Constant", "Real weather"],
    )

    wind_samples = st.number_input(
        "Wind samples per leg",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
    )

    wind_dir = st.slider(
        "Constant wind direction FROM [deg]",
        min_value=0,
        max_value=360,
        value=270,
        step=5,
    )

    wind_speed = st.slider(
        "Constant wind speed [m/s]",
        min_value=0.0,
        max_value=50.0,
        value=8.0,
        step=0.5,
    )

    st.caption(
        "Mission convention: along-track wind > 0 is tailwind; "
        "along-track wind < 0 is headwind."
    )

    if weather_mode == "Real weather":

        if RealTimeWeather is None:

            st.warning(
                "RealTimeWeather is unavailable. "
                "Constant wind will be used."
            )

        else:

            if st.button(
                "Initialize weather provider",
                use_container_width=True,
            ):
                try:
                    st.session_state[
                        "mission_weather_engine"
                    ] = RealTimeWeather()

                    st.success(
                        "Weather provider initialized."
                    )

                except Exception as exc:
                    st.error(
                        f"Weather initialization failed: {exc}"
                    )

    st.divider()
    st.header("Fleet / Logistics")

    mission_cargo_kg = st.number_input(
        "Total logistics requirement [kg]",
        min_value=0.0,
        value=20_000.0,
        step=1000.0,
    )

    fleet_size = st.number_input(
        "Fleet size",
        min_value=1,
        value=1,
        step=1,
    )

    refuel_time_min = st.number_input(
        "Refuel/service time [min]",
        min_value=0.0,
        value=30.0,
        step=5.0,
    )

    unload_time_min = st.number_input(
        "Unload time [min]",
        min_value=0.0,
        value=60.0,
        step=5.0,
    )

    crew_rest_hr = st.number_input(
        "Crew rest [hr]",
        min_value=0.0,
        value=8.0,
        step=0.5,
    )


# =============================================================================
# Route editor
# =============================================================================

st.subheader("Route")

st.caption(
    "Waypoints are evaluated sequentially. "
    "Refuel flags identify operational stops where replenishment is allowed."
)

edited_route = st.data_editor(
    st.session_state[
        "mission_route_df"
    ],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "name": st.column_config.TextColumn(
            "Waypoint",
            required=True,
        ),
        "lat": st.column_config.NumberColumn(
            "Latitude [deg]",
            format="%.5f",
        ),
        "lon": st.column_config.NumberColumn(
            "Longitude [deg]",
            format="%.5f",
        ),
        "refuel": st.column_config.CheckboxColumn(
            "Refuel allowed",
        ),
    },
)

st.session_state[
    "mission_route_df"
] = edited_route


# =============================================================================
# Route validation
# =============================================================================

route_error = None
route_objs = []

try:

    if len(edited_route) < 2:
        raise ValueError(
            "At least two waypoints are required."
        )

    for _, row in edited_route.iterrows():

        name = str(row["name"]).strip()

        if not name:
            raise ValueError(
                "Every waypoint requires a name."
            )

        lat = float(row["lat"])
        lon = float(row["lon"])

        if not (-90.0 <= lat <= 90.0):
            raise ValueError(
                f"Invalid latitude for {name}."
            )

        if not (-180.0 <= lon <= 180.0):
            raise ValueError(
                f"Invalid longitude for {name}."
            )

        route_objs.append(
            Waypoint(
                name=name,
                lat_deg=lat,
                lon_deg=lon,
                refuel_allowed=bool(
                    row["refuel"]
                ),
            )
        )

except Exception as exc:
    route_error = str(exc)


# =============================================================================
# Wind callback
# =============================================================================

wind_fn = None

if (
    weather_mode == "Real weather"
    and RealTimeWeather is not None
):

    wx = st.session_state.get(
        "mission_weather_engine"
    )

    if wx is not None:

        altitude_m = float(
            cfg.get(
                "cruise_alt_m",
                914.0,
            )
        )

        def wind_fn(
            lat: float,
            lon: float,
            t_hr: float,
        ):
            data = wx.get_winds_aloft(
                float(lat),
                float(lon),
                altitude_m,
                time_offset_hours=float(t_hr),
            )

            return (
                float(data["dir_deg"]),
                float(data["speed_mps"]),
            )


# =============================================================================
# Run mission
# =============================================================================

run_button = st.button(
    "Run Mission Analysis",
    type="primary",
    use_container_width=True,
)


if run_button:

    if route_error:

        st.error(route_error)

    elif (
        weather_mode == "Real weather"
        and wind_fn is None
    ):

        st.error(
            "Initialize the real-weather provider "
            "before running the mission."
        )

    else:

        try:

            with st.spinner(
                "Evaluating route with coupled ADaPT model..."
            ):

                result = run_route_mission_ui(
                    cfg=cfg,
                    route=route_objs,
                    trip_type=trip_type,

                    wind_fn=wind_fn,
                    wind_dir_deg=float(wind_dir),
                    wind_speed_mps=float(wind_speed),
                    wind_samples_per_leg=int(
                        wind_samples
                    ),

                    ground_speed_floor_mps=float(
                        ground_speed_floor
                    ),

                    min_tas_mps=float(
                        min_tas
                    ),

                    max_tas_mps=max_tas,

                    throttle_steps=int(
                        throttle_steps
                    ),

                    allow_enroute_refuel=bool(
                        allow_refuel
                    ),

                    mission_cargo_kg=float(
                        mission_cargo_kg
                    ),

                    fleet_size=int(
                        fleet_size
                    ),

                    refuel_time_min=float(
                        refuel_time_min
                    ),

                    unload_time_min=float(
                        unload_time_min
                    ),

                    crew_rest_hr=float(
                        crew_rest_hr
                    ),
                )

            st.session_state[
                "mission_result"
            ] = result

        except Exception as exc:

            st.error(
                "Mission analysis failed."
            )

            st.exception(exc)


# =============================================================================
# Results
# =============================================================================

res = st.session_state.get(
    "mission_result"
)


if res is None:

    st.info(
        "Define the route and operational conditions, "
        "then click **Run Mission Analysis**."
    )

else:

    scal = res["scalars"]

    # -------------------------------------------------------------------------
    # Feasibility
    # -------------------------------------------------------------------------

    if scal["feasible"]:

        st.success(
            "Mission feasible with the current aircraft "
            "and operational assumptions."
        )

    else:

        st.error(
            "Mission is infeasible for at least one route leg "
            "or aircraft constraint."
        )

    if res["notes"]:
        st.info(res["notes"])

    # -------------------------------------------------------------------------
    # Primary metrics
    # -------------------------------------------------------------------------

    st.subheader("Mission Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Distance",
        f"{_fmt(scal['total_distance_km'])} km",
    )

    c2.metric(
        "Flight Time",
        f"{_fmt(scal['total_time_hr'], 2)} hr",
    )

    c3.metric(
        "Consumable",
        f"{_fmt(scal['total_consumable_kg'])} kg",
    )

    c4.metric(
        "Mission Energy",
        f"{_fmt(scal['total_energy_MJ'])} MJ",
    )

    c5, c6, c7, c8 = st.columns(4)

    c5.metric(
        "MTOW",
        f"{_fmt(scal['mtow_kg'])} kg",
    )

    c6.metric(
        "Max Required Power",
        f"{_fmt(scal['max_power_kW'])} kW",
    )

    c7.metric(
        "Refuel Stops",
        str(scal["refuel_stops"]),
    )

    c8.metric(
        "Fleet Close Time",
        f"{_fmt(scal['close_time_hr'], 2)} hr",
    )

    st.caption(
        f"Power source: {scal['power_source']}"
    )

    # -------------------------------------------------------------------------
    # Tabs
    # -------------------------------------------------------------------------

    (
        tab_legs,
        tab_wind,
        tab_fleet,
        tab_data,
    ) = st.tabs(
        [
            "Route Legs",
            "Wind Environment",
            "Fleet / Logistics",
            "Complete Data",
        ]
    )

    # =========================================================================
    # Leg results
    # =========================================================================

    with tab_legs:

        st.subheader(
            "Leg-by-Leg Performance"
        )

        st.dataframe(
            res["df_legs"],
            use_container_width=True,
            hide_index=True,
        )

        df_legs = res["df_legs"]

        if not df_legs.empty:

            fig = go.Figure()

            fig.add_trace(
                go.Bar(
                    x=[
                        f"{a} → {b}"
                        for a, b in zip(
                            df_legs["Origin"],
                            df_legs["Destination"],
                        )
                    ],
                    y=df_legs[
                        "Required shaft power [kW]"
                    ],
                    name="Required shaft power",
                )
            )

            fig.update_layout(
                title="Required Shaft Power by Route Leg",
                xaxis_title="Route leg",
                yaxis_title="Power [kW]",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    # =========================================================================
    # Wind
    # =========================================================================

    with tab_wind:

        st.subheader(
            "Along-Track Wind"
        )

        st.caption(
            "Positive = tailwind; negative = headwind."
        )

        df_wind = res[
            "wind_profiles_df"
        ]

        if df_wind.empty:

            st.info(
                "No wind-profile data available."
            )

        else:

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=df_wind["route_km"],
                    y=df_wind["along_wind_mps"],
                    mode="lines+markers",
                    name="Along-track wind",
                )
            )

            fig.add_hline(
                y=0.0,
                line_dash="dash",
            )

            fig.update_layout(
                xaxis_title="Distance along route [km]",
                yaxis_title="Along-track wind [m/s]",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

            fig_cross = px.line(
                df_wind,
                x="route_km",
                y="crosswind_mps",
                markers=True,
                labels={
                    "route_km":
                        "Distance along route [km]",

                    "crosswind_mps":
                        "Crosswind [m/s]",
                },
                title="Crosswind Along Route",
            )

            st.plotly_chart(
                fig_cross,
                use_container_width=True,
            )

    # =========================================================================
    # Fleet
    # =========================================================================

    with tab_fleet:

        st.subheader(
            "Fleet / Logistics"
        )

        st.dataframe(
            res["df_fleet"],
            use_container_width=True,
            hide_index=True,
        )

    # =========================================================================
    # Complete data
    # =========================================================================

    with tab_data:

        st.subheader("Mission Totals")

        st.dataframe(
            res["df_totals"],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Route")

        st.dataframe(
            res["df_route"],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download Leg Results CSV",
            data=(
                res["df_legs"]
                .to_csv(index=False)
                .encode("utf-8")
            ),
            file_name="mission_leg_results.csv",
            mime="text/csv",
            use_container_width=True,
        )