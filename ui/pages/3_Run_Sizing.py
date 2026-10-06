# -*- coding: utf-8 -*-
"""
ADAPT — Mission-Driven Airship Sizing
Beginner-facing Streamlit page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


# ============================================================================
# Repository bootstrap
# ============================================================================

PAGE_DIR = Path(__file__).resolve().parent
UI_DIR = PAGE_DIR.parent
PROJECT_ROOT = UI_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ui.run_sizing import (
    AIRSHIP_TYPE_LABELS,
    DEFAULT_BOUNDS,
    LANDING_SYSTEM_LABELS,
    POWER_SOURCE_LABELS,
    run_sizing_ui,
)


# ============================================================================
# Page configuration
# ============================================================================

st.set_page_config(
    page_title="ADAPT | Airship Sizing",
    page_icon="📐",
    layout="wide",
)


# ============================================================================
# Small helpers
# ============================================================================

def finite(value) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def metric_value(
    value,
    unit: str = "",
    decimals: int = 1,
) -> str:
    if not finite(value):
        return "N/A"

    value = float(value)

    if abs(value) >= 10000:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.{decimals}f}"

    return f"{text} {unit}".strip()


def architecture_has_battery(power_source: str) -> bool:
    return power_source in {
        "battery_only",
        "solar_battery",
        "solar-RFC",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
        "conventional_battery_hybrid",
    }


def architecture_has_solar(power_source: str) -> bool:
    return power_source in {
        "solar_battery",
        "solar-RFC",
        "solar_hydrogen_hybrid",
    }


def render_mass_plot(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("No positive mass components were available.")
        return

    fig, ax = plt.subplots(figsize=(8, 4.8))

    ax.bar(
        df["Component"],
        df["Mass [kg]"],
    )

    ax.set_ylabel("Mass [kg]")
    ax.set_title("Airship mass breakdown")
    ax.tick_params(
        axis="x",
        rotation=30,
    )

    fig.tight_layout()

    st.pyplot(
        fig,
        use_container_width=True,
    )

    plt.close(fig)


def render_power_plot(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("Power results were not available.")
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.bar(
        df["Power"],
        df["Power [kW]"],
    )

    ax.set_ylabel("Shaft power [kW]")
    ax.set_title("Required and installed shaft power")

    fig.tight_layout()

    st.pyplot(
        fig,
        use_container_width=True,
    )

    plt.close(fig)


def render_constraint_plot(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("No constraint information was available.")
        return

    plot_df = df.copy()

    plot_df = plot_df[
        np.isfinite(
            pd.to_numeric(
                plot_df["Value"],
                errors="coerce",
            )
        )
    ]

    if plot_df.empty:
        st.info("No active finite constraints were available.")
        return

    fig, ax = plt.subplots(figsize=(8, 4.8))

    ax.bar(
        plot_df["Constraint"],
        plot_df["Value"],
    )

    ax.axhline(
        0.0,
        linewidth=1.2,
    )

    ax.set_ylabel("Constraint value")
    ax.set_title(
        "Final feasibility constraints — feasible when value ≤ 0"
    )

    ax.tick_params(
        axis="x",
        rotation=35,
    )

    fig.tight_layout()

    st.pyplot(
        fig,
        use_container_width=True,
    )

    plt.close(fig)


# ============================================================================
# Header
# ============================================================================

st.title("Mission-Driven Airship Sizing")

st.markdown(
    """
Enter the **mission requirements** and select the **airship and propulsion
architecture**. ADAPT then sizes the airship automatically.

You do **not** need to edit an input file or change the source code.
"""
)


# ============================================================================
# Beginner explanation
# ============================================================================

with st.container(border=True):

    left, middle, right = st.columns(
        [1.0, 0.15, 1.0]
    )

    with left:
        st.subheader("You provide")

        st.markdown(
            """
- Payload
- Mission range
- Cruise speed
- Cruise altitude
- Airship type
- Propulsion architecture
- Technology assumptions
"""
        )

    with middle:
        st.markdown(
            """
<br><br><br>

### →
""",
            unsafe_allow_html=True,
        )

    with right:
        st.subheader("ADAPT determines")

        st.markdown(
            """
- Hull length
- Fineness ratio
- Installed shaft power
- Take-off buoyancy ratio
- Horizontal tail sizing
- Vertical tail sizing
"""
        )


st.caption(
    "Sizing objective: minimize MTOW while satisfying the active "
    "ADAPT multidisciplinary constraints."
)


# ============================================================================
# Sidebar — user inputs
# ============================================================================

st.sidebar.header("Airship Sizing Inputs")

st.sidebar.caption(
    "For a normal sizing study, these are the only inputs you need."
)


# ----------------------------------------------------------------------------
# Mission requirements
# ----------------------------------------------------------------------------

st.sidebar.subheader("1. Mission Requirements")

payload_kg = st.sidebar.number_input(
    "Payload [kg]",
    min_value=0.0,
    value=400.0,
    step=50.0,
    help="Required useful payload carried by the airship.",
)

range_km = st.sidebar.number_input(
    "Mission range [km]",
    min_value=1.0,
    value=900.0,
    step=50.0,
    help="Required design mission range.",
)

cruise_speed_ms = st.sidebar.number_input(
    "Cruise speed [m/s]",
    min_value=1.0,
    value=22.0,
    step=0.5,
    help="Design true airspeed during cruise.",
)

cruise_altitude_m = st.sidebar.number_input(
    "Cruise altitude [m]",
    min_value=0.0,
    value=914.4,
    step=100.0,
)

cruise_disa_K = st.sidebar.number_input(
    "Temperature offset ΔISA [K]",
    value=0.0,
    step=1.0,
    help=(
        "Temperature difference from the International "
        "Standard Atmosphere."
    ),
)


# ----------------------------------------------------------------------------
# Architecture
# ----------------------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("2. Architecture")

airship_label = st.sidebar.selectbox(
    "Airship type",
    list(AIRSHIP_TYPE_LABELS.keys()),
    index=0,
    help=(
        "Structural architecture of the airship: "
        "non-rigid, semi-rigid or rigid."
    ),
)

airship_type = AIRSHIP_TYPE_LABELS[airship_label]


power_label = st.sidebar.selectbox(
    "Propulsion / power architecture",
    list(POWER_SOURCE_LABELS.keys()),
    index=0,
)

power_source = POWER_SOURCE_LABELS[power_label]


landing_label = st.sidebar.selectbox(
    "Landing system",
    list(LANDING_SYSTEM_LABELS.keys()),
    index=0,
)

landing_system = LANDING_SYSTEM_LABELS[
    landing_label
]


n_engine = st.sidebar.number_input(
    "Number of engines / propulsors",
    min_value=1,
    max_value=20,
    value=2,
    step=1,
)


n_crew = st.sidebar.number_input(
    "Number of crew",
    min_value=0,
    max_value=50,
    value=1,
    step=1,
)


# ----------------------------------------------------------------------------
# Technology
# ----------------------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("3. Technology Assumptions")

propeller_efficiency = st.sidebar.slider(
    "Propeller efficiency",
    min_value=0.50,
    max_value=0.95,
    value=0.78,
    step=0.01,
)


if architecture_has_battery(power_source):

    battery_specific_energy_Whkg = (
        st.sidebar.number_input(
            "Battery specific energy [Wh/kg]",
            min_value=50.0,
            max_value=2000.0,
            value=350.0,
            step=25.0,
        )
    )

else:
    battery_specific_energy_Whkg = 350.0


if architecture_has_solar(power_source):

    solar_area_m2 = st.sidebar.number_input(
        "Solar-panel area [m²]",
        min_value=0.0,
        value=300.0,
        step=25.0,
    )

    solar_irradiance_Wm2 = (
        st.sidebar.number_input(
            "Solar irradiance [W/m²]",
            min_value=0.0,
            value=600.0,
            step=25.0,
        )
    )

else:
    solar_area_m2 = 300.0
    solar_irradiance_Wm2 = 600.0


# ----------------------------------------------------------------------------
# Advanced assumptions
# ----------------------------------------------------------------------------

with st.sidebar.expander(
    "Advanced aerodynamic / operational assumptions"
):

    lift_coeff = st.number_input(
        "Lift coefficient",
        min_value=0.0,
        value=0.15,
        step=0.01,
        format="%.3f",
    )

    drag_due_to_lift_factor = st.number_input(
        "Drag-due-to-lift factor",
        min_value=0.0,
        value=0.869,
        step=0.01,
        format="%.3f",
    )

    BR_landing = st.number_input(
        "Landing buoyancy ratio",
        min_value=0.10,
        max_value=1.20,
        value=0.90,
        step=0.01,
    )

    ballast_mass_kg = st.number_input(
        "Ballast mass [kg]",
        min_value=0.0,
        value=0.0,
        step=25.0,
    )


# ----------------------------------------------------------------------------
# Sizing bounds
# ----------------------------------------------------------------------------

with st.sidebar.expander(
    "Advanced sizing-variable bounds"
):

    st.caption(
        "ADAPT varies these quantities automatically. "
        "Most users should keep the default bounds."
    )

    length_min = st.number_input(
        "Minimum hull length [m]",
        value=float(
            DEFAULT_BOUNDS["length_m"][0]
        ),
        step=5.0,
    )

    length_max = st.number_input(
        "Maximum hull length [m]",
        value=float(
            DEFAULT_BOUNDS["length_m"][1]
        ),
        step=5.0,
    )

    fineness_min = st.number_input(
        "Minimum fineness ratio",
        value=float(
            DEFAULT_BOUNDS["fineness_ratio"][0]
        ),
        step=0.1,
    )

    fineness_max = st.number_input(
        "Maximum fineness ratio",
        value=float(
            DEFAULT_BOUNDS["fineness_ratio"][1]
        ),
        step=0.1,
    )

    power_min = st.number_input(
        "Minimum installed shaft power [kW]",
        value=float(
            DEFAULT_BOUNDS[
                "installed_shaft_power_kW"
            ][0]
        ),
        step=25.0,
    )

    power_max = st.number_input(
        "Maximum installed shaft power [kW]",
        value=float(
            DEFAULT_BOUNDS[
                "installed_shaft_power_kW"
            ][1]
        ),
        step=25.0,
    )

    br_min = st.number_input(
        "Minimum take-off buoyancy ratio",
        value=float(
            DEFAULT_BOUNDS["BR_takeoff"][0]
        ),
        step=0.01,
    )

    br_max = st.number_input(
        "Maximum take-off buoyancy ratio",
        value=float(
            DEFAULT_BOUNDS["BR_takeoff"][1]
        ),
        step=0.01,
    )

    htail_min = st.number_input(
        "Minimum horizontal tail-volume coefficient",
        value=float(
            DEFAULT_BOUNDS[
                "tail_volume_coeff_horizontal"
            ][0]
        ),
        step=0.005,
        format="%.3f",
    )

    htail_max = st.number_input(
        "Maximum horizontal tail-volume coefficient",
        value=float(
            DEFAULT_BOUNDS[
                "tail_volume_coeff_horizontal"
            ][1]
        ),
        step=0.005,
        format="%.3f",
    )

    vtail_min = st.number_input(
        "Minimum vertical tail-volume coefficient",
        value=float(
            DEFAULT_BOUNDS[
                "tail_volume_coeff_vertical"
            ][0]
        ),
        step=0.005,
        format="%.3f",
    )

    vtail_max = st.number_input(
        "Maximum vertical tail-volume coefficient",
        value=float(
            DEFAULT_BOUNDS[
                "tail_volume_coeff_vertical"
            ][1]
        ),
        step=0.005,
        format="%.3f",
    )


bounds = {
    "length_m": (
        float(length_min),
        float(length_max),
    ),
    "fineness_ratio": (
        float(fineness_min),
        float(fineness_max),
    ),
    "installed_shaft_power_kW": (
        float(power_min),
        float(power_max),
    ),
    "BR_takeoff": (
        float(br_min),
        float(br_max),
    ),
    "tail_volume_coeff_horizontal": (
        float(htail_min),
        float(htail_max),
    ),
    "tail_volume_coeff_vertical": (
        float(vtail_min),
        float(vtail_max),
    ),
}


# ----------------------------------------------------------------------------
# Optimizer
# ----------------------------------------------------------------------------

with st.sidebar.expander(
    "Sizing computation settings"
):

    st.caption(
        "Higher values generally increase computational cost. "
        "The defaults correspond to the sizing backend."
    )

    population_size = st.number_input(
        "Population size",
        min_value=4,
        max_value=1000,
        value=80,
        step=10,
    )

    generations = st.number_input(
        "Generations",
        min_value=1,
        max_value=5000,
        value=120,
        step=10,
    )

    random_seed = st.number_input(
        "Random seed",
        min_value=0,
        value=11,
        step=1,
    )


st.sidebar.divider()

run_clicked = st.sidebar.button(
    "RUN AIRSHIP SIZING",
    type="primary",
    use_container_width=True,
)


# ============================================================================
# Current sizing problem — always visible
# ============================================================================

st.subheader("Current Sizing Problem")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Payload",
    metric_value(payload_kg, "kg"),
)

c2.metric(
    "Range",
    metric_value(range_km, "km"),
)

c3.metric(
    "Cruise Speed",
    metric_value(cruise_speed_ms, "m/s"),
)

c4.metric(
    "Cruise Altitude",
    metric_value(cruise_altitude_m, "m"),
)


a1, a2, a3 = st.columns(3)

a1.metric(
    "Airship Type",
    airship_label,
)

a2.metric(
    "Power Architecture",
    power_label,
)

a3.metric(
    "Propulsors",
    str(int(n_engine)),
)


# ============================================================================
# No run yet
# ============================================================================

if not run_clicked and "adapt_sizing_result" not in st.session_state:

    st.info(
        "Set the mission requirements and architecture in the "
        "sidebar, then click **RUN AIRSHIP SIZING**."
    )

    st.subheader("What ADAPT will size")

    preview = pd.DataFrame(
        [
            {
                "Design variable": "Hull length",
                "Lower bound": bounds["length_m"][0],
                "Upper bound": bounds["length_m"][1],
                "Unit": "m",
            },
            {
                "Design variable": "Fineness ratio",
                "Lower bound": bounds[
                    "fineness_ratio"
                ][0],
                "Upper bound": bounds[
                    "fineness_ratio"
                ][1],
                "Unit": "-",
            },
            {
                "Design variable": "Installed shaft power",
                "Lower bound": bounds[
                    "installed_shaft_power_kW"
                ][0],
                "Upper bound": bounds[
                    "installed_shaft_power_kW"
                ][1],
                "Unit": "kW",
            },
            {
                "Design variable": "Take-off buoyancy ratio",
                "Lower bound": bounds[
                    "BR_takeoff"
                ][0],
                "Upper bound": bounds[
                    "BR_takeoff"
                ][1],
                "Unit": "-",
            },
            {
                "Design variable":
                    "Horizontal tail-volume coefficient",
                "Lower bound": bounds[
                    "tail_volume_coeff_horizontal"
                ][0],
                "Upper bound": bounds[
                    "tail_volume_coeff_horizontal"
                ][1],
                "Unit": "-",
            },
            {
                "Design variable":
                    "Vertical tail-volume coefficient",
                "Lower bound": bounds[
                    "tail_volume_coeff_vertical"
                ][0],
                "Upper bound": bounds[
                    "tail_volume_coeff_vertical"
                ][1],
                "Unit": "-",
            },
        ]
    )

    st.dataframe(
        preview,
        use_container_width=True,
        hide_index=True,
    )

    st.stop()


# ============================================================================
# Execute sizing
# ============================================================================

if run_clicked:

    try:
        with st.spinner(
            "ADAPT is sizing the airship. "
            "The multidisciplinary model is being converged "
            "for each candidate design..."
        ):

            result = run_sizing_ui(
                payload_kg=payload_kg,
                range_km=range_km,
                cruise_speed_ms=cruise_speed_ms,
                cruise_altitude_m=cruise_altitude_m,
                cruise_disa_K=cruise_disa_K,

                power_source=power_source,
                airship_type=airship_type,
                landing_system=landing_system,

                n_crew=n_crew,
                n_engine=n_engine,
                propeller_efficiency=(
                    propeller_efficiency
                ),
                lift_coeff=lift_coeff,
                drag_due_to_lift_factor=(
                    drag_due_to_lift_factor
                ),
                BR_landing=BR_landing,
                ballast_mass_kg=ballast_mass_kg,

                battery_specific_energy_Whkg=(
                    battery_specific_energy_Whkg
                ),
                solar_area_m2=solar_area_m2,
                solar_irradiance_Wm2=(
                    solar_irradiance_Wm2
                ),

                bounds=bounds,

                population_size=int(
                    population_size
                ),
                generations=int(generations),
                random_seed=int(random_seed),

                num_steps=1,
                
            )

        st.session_state[
            "adapt_sizing_result"
        ] = result

    except Exception as exc:

        st.error(
            "ADAPT sizing analysis failed."
        )

        st.exception(exc)

        st.stop()


result = st.session_state.get(
    "adapt_sizing_result"
)

if result is None:
    st.stop()


# ============================================================================
# Results
# ============================================================================

summary = result["summary"]
feasible = result["feasible"]


st.divider()
st.header("Sized Airship")


if feasible:
    st.success(
        "FEASIBLE DESIGN — the selected design satisfies "
        "all active ADAPT sizing constraints."
    )
else:
    st.warning(
        "NO FULLY FEASIBLE DESIGN WAS IDENTIFIED — "
        "the best available candidate is shown below. "
        "Review the feasibility tab and sizing bounds."
    )


# ============================================================================
# Main result cards
# ============================================================================

r1, r2, r3, r4 = st.columns(4)

r1.metric(
    "MTOW",
    metric_value(
        summary.get("mtow_kg"),
        "kg",
    ),
)

r2.metric(
    "Hull Length",
    metric_value(
        summary.get("length_m"),
        "m",
    ),
)

r3.metric(
    "Gross Volume",
    metric_value(
        summary.get("gross_volume_m3"),
        "m³",
        0,
    ),
)

r4.metric(
    "Installed Power",
    metric_value(
        summary.get(
            "installed_shaft_power_kW"
        ),
        "kW",
    ),
)


r5, r6, r7, r8 = st.columns(4)

r5.metric(
    "Maximum Diameter",
    metric_value(
        summary.get("maximum_diameter_m"),
        "m",
    ),
)

r6.metric(
    "Operating Empty Weight",
    metric_value(
        summary.get("owe_kg"),
        "kg",
    ),
)

r7.metric(
    "Required Power",
    metric_value(
        summary.get(
            "required_shaft_power_kW"
        ),
        "kW",
    ),
)

r8.metric(
    "Power Margin",
    metric_value(
        result.get("power_margin_kW"),
        "kW",
    ),
)


# ============================================================================
# Result tabs
# ============================================================================

(
    tab_overview,
    tab_design,
    tab_mass,
    tab_power,
    tab_feasibility,
    tab_run,
) = st.tabs(
    [
        "Overview",
        "Airship Design",
        "Mass Breakdown",
        "Power & Energy",
        "Feasibility",
        "Sizing Setup",
    ]
)


# ----------------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------------

with tab_overview:

    st.subheader("Mission and Selected Design")

    left, right = st.columns(2)

    with left:

        st.markdown("#### Mission requirements")

        mission_df = pd.DataFrame(
            [
                [
                    "Payload",
                    payload_kg,
                    "kg",
                ],
                [
                    "Range",
                    range_km,
                    "km",
                ],
                [
                    "Cruise speed",
                    cruise_speed_ms,
                    "m/s",
                ],
                [
                    "Cruise altitude",
                    cruise_altitude_m,
                    "m",
                ],
                [
                    "ΔISA",
                    cruise_disa_K,
                    "K",
                ],
            ],
            columns=[
                "Requirement",
                "Value",
                "Unit",
            ],
        )

        st.dataframe(
            mission_df,
            use_container_width=True,
            hide_index=True,
        )

    with right:

        st.markdown("#### Architecture")

        architecture_df = pd.DataFrame(
            [
                [
                    "Airship type",
                    airship_label,
                ],
                [
                    "Power architecture",
                    power_label,
                ],
                [
                    "Landing system",
                    landing_label,
                ],
                [
                    "Number of propulsors",
                    int(n_engine),
                ],
                [
                    "Number of crew",
                    int(n_crew),
                ],
            ],
            columns=[
                "Selection",
                "Value",
            ],
        )

        st.dataframe(
            architecture_df,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Principal sizing results")

    overview_rows = [
        [
            "MTOW",
            summary.get("mtow_kg"),
            "kg",
        ],
        [
            "Operating empty weight",
            summary.get("owe_kg"),
            "kg",
        ],
        [
            "Payload",
            summary.get("payload_kg"),
            "kg",
        ],
        [
            "Hull length",
            summary.get("length_m"),
            "m",
        ],
        [
            "Maximum diameter",
            summary.get(
                "maximum_diameter_m"
            ),
            "m",
        ],
        [
            "Fineness ratio",
            summary.get("fineness_ratio"),
            "-",
        ],
        [
            "Gross volume",
            summary.get("gross_volume_m3"),
            "m³",
        ],
        [
            "Installed shaft power",
            summary.get(
                "installed_shaft_power_kW"
            ),
            "kW",
        ],
        [
            "Required shaft power",
            summary.get(
                "required_shaft_power_kW"
            ),
            "kW",
        ],
    ]

    overview_df = pd.DataFrame(
        overview_rows,
        columns=[
            "Quantity",
            "Value",
            "Unit",
        ],
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True,
    )


# ----------------------------------------------------------------------------
# Airship design
# ----------------------------------------------------------------------------

with tab_design:

    st.subheader(
        "Design Variables Selected by ADAPT"
    )

    st.caption(
        "These quantities were not prescribed by the user. "
        "They were varied by the sizing optimizer."
    )

    st.dataframe(
        result["design_table"],
        use_container_width=True,
        hide_index=True,
    )

    d1, d2, d3 = st.columns(3)

    d1.metric(
        "Take-off Buoyancy Ratio",
        metric_value(
            summary.get("BR_takeoff"),
            "",
            3,
        ),
    )

    d2.metric(
        "Horizontal Tail Coefficient",
        metric_value(
            summary.get(
                "tail_volume_coeff_horizontal"
            ),
            "",
            4,
        ),
    )

    d3.metric(
        "Vertical Tail Coefficient",
        metric_value(
            summary.get(
                "tail_volume_coeff_vertical"
            ),
            "",
            4,
        ),
    )


# ----------------------------------------------------------------------------
# Mass
# ----------------------------------------------------------------------------

with tab_mass:

    st.subheader("Mass Breakdown")

    render_mass_plot(
        result["mass_table"]
    )

    st.dataframe(
        result["mass_table"],
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Only positive mass quantities available from the "
        "active architecture are displayed."
    )


# ----------------------------------------------------------------------------
# Power / energy
# ----------------------------------------------------------------------------

with tab_power:

    st.subheader("Power and Energy System")

    render_power_plot(
        result["power_table"]
    )

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Required Shaft Power",
        metric_value(
            summary.get(
                "required_shaft_power_kW"
            ),
            "kW",
        ),
    )

    p2.metric(
        "Installed Shaft Power",
        metric_value(
            summary.get(
                "installed_shaft_power_kW"
            ),
            "kW",
        ),
    )

    p3.metric(
        "Power Margin",
        metric_value(
            result.get("power_margin_kW"),
            "kW",
        ),
    )

    energy_rows = []

    optional_results = [
        (
            "Mission consumable mass",
            "consumable_mass_kg",
            "kg",
        ),
        (
            "Battery mass",
            "battery_mass_kg",
            "kg",
        ),
        (
            "Tank mass",
            "tank_mass_kg",
            "kg",
        ),
        (
            "Power-system mass",
            "power_system_mass_kg",
            "kg",
        ),
        (
            "Propulsion-system mass",
            "propulsion_mass_kg",
            "kg",
        ),
    ]

    for label, key, unit in optional_results:

        value = summary.get(key)

        if finite(value) and float(value) > 1.0e-9:
            energy_rows.append(
                [label, float(value), unit]
            )

    if energy_rows:

        st.dataframe(
            pd.DataFrame(
                energy_rows,
                columns=[
                    "Quantity",
                    "Value",
                    "Unit",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )


# ----------------------------------------------------------------------------
# Feasibility
# ----------------------------------------------------------------------------

with tab_feasibility:

    st.subheader("Final Feasibility Audit")

    st.markdown(
        """
ADAPT uses the convention

**constraint ≤ 0 → feasible**

Positive values indicate a violated constraint.
"""
    )

    render_constraint_plot(
        result["constraint_table"]
    )

    st.dataframe(
        result["constraint_table"],
        use_container_width=True,
        hide_index=True,
    )

    if feasible:
        st.success(
            "All required active sizing constraints passed."
        )
    else:
        failed = result["constraint_table"]

        failed = failed[
            failed["Status"] == "FAIL"
        ]

        if not failed.empty:
            st.error(
                "The following constraints remain violated:"
            )

            st.dataframe(
                failed,
                use_container_width=True,
                hide_index=True,
            )


# ----------------------------------------------------------------------------
# Sizing setup
# ----------------------------------------------------------------------------

with tab_run:

    st.subheader("Sizing Computation")

    st.markdown(
        """
The mission and architecture are fixed by the user. ADAPT uses
Differential Evolution to vary the airship sizing variables. Each
candidate is evaluated using the coupled MDF/OpenMDAO model.
"""
    )

    s1, s2, s3 = st.columns(3)

    s1.metric(
        "Population",
        int(
            result["optimizer"][
                "population_size"
            ]
        ),
    )

    s2.metric(
        "Generations",
        int(
            result["optimizer"][
                "generations"
            ]
        ),
    )

    s3.metric(
        "Random Seed",
        int(
            result["optimizer"][
                "random_seed"
            ]
        ),
    )

    st.markdown(
        "#### Design-variable search bounds"
    )

    st.dataframe(
        result["design_table"][
            [
                "Design variable",
                "Lower bound",
                "Upper bound",
                "Unit",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        "#### Calculation sequence"
    )

    st.markdown(
        """
1. Read the mission requirements and architecture.
2. Build the coupled ADAPT MDF model.
3. Apply the selected technology assumptions.
4. Generate candidate airship designs.
5. Converge the multidisciplinary analysis for each candidate.
6. Check the active feasibility constraints.
7. Minimize MTOW.
8. Independently evaluate the selected final design.
"""
    )