# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Single MDA analysis.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
import math

import streamlit as st
import streamlit.components.v1 as components

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from run_mda import run_mda
from ui_widgets import sidebar_mda_inputs


# =============================================================================
# Page configuration
# =============================================================================

st.set_page_config(
    page_title="ADaPT — Run MDA",
    page_icon="🎈",
    layout="wide",
)

st.title("ADaPT — Multidisciplinary Design Analysis")

st.caption(
    "Run the fully coupled ADaPT airship model for the selected "
    "vehicle, mission, and propulsion architecture."
)


# =============================================================================
# Helpers
# =============================================================================

def _finite(value) -> bool:
    """Return True when value can be represented as a finite float."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _fmt(value, fmt=",.1f", suffix=""):
    """Safely format numerical UI values."""
    if not _finite(value):
        return "—"

    return f"{float(value):{fmt}}{suffix}"


# =============================================================================
# Inputs
# =============================================================================

cfg = sidebar_mda_inputs()

run_btn = st.button(
    "Run MDA",
    type="primary",
    use_container_width=True,
)


# =============================================================================
# Execute
# =============================================================================

if run_btn:

    # Clear previous result so a failed new run cannot leave an old result
    # looking like the current case.
    st.session_state.pop("mda_res", None)

    try:
        with st.spinner("Running coupled ADaPT MDA model..."):
            st.session_state["mda_res"] = run_mda(
                cfg,
                make_figure=True,
                make_reports=True,
            )

        st.success("MDA completed successfully.")

    except Exception as exc:
        st.error("The MDA run failed.")
        st.exception(exc)
        st.stop()


res = st.session_state.get("mda_res")

if res is None:
    st.info(
        "Configure the airship and mission using the sidebar, "
        "then click **Run MDA**."
    )
    st.stop()


# =============================================================================
# Results
# =============================================================================

scal = res.get("scalars", {})
out = res.get("outputs", {})
run_cfg = res.get("config", {})


# -----------------------------------------------------------------------------
# Architecture summary
# -----------------------------------------------------------------------------

st.subheader("Configuration")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Power Architecture",
    str(scal.get("power_source", run_cfg.get("power_source", "—"))),
)

c2.metric(
    "Airship Type",
    str(scal.get("airship_type", run_cfg.get("airship_type", "—"))),
)

c3.metric(
    "Payload",
    _fmt(scal.get("payload_kg"), ",.0f", " kg"),
)

c4.metric(
    "Mission Range",
    _fmt(
        float(run_cfg.get("range_m", float("nan"))) / 1000.0
        if _finite(run_cfg.get("range_m"))
        else float("nan"),
        ",.0f",
        " km",
    ),
)


st.divider()


# -----------------------------------------------------------------------------
# Primary MDA metrics
# -----------------------------------------------------------------------------

st.subheader("MDA Summary")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "MTOW",
    _fmt(scal.get("mtow_kg"), ",.1f", " kg"),
)

c2.metric(
    "Operating Empty Weight",
    _fmt(scal.get("owe_kg"), ",.1f", " kg"),
)

c3.metric(
    "Required Shaft Power",
    _fmt(scal.get("required_power_kW"), ",.2f", " kW"),
)

c4.metric(
    "Installed Shaft Power",
    _fmt(scal.get("installed_power_kW"), ",.2f", " kW"),
)


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Power Margin",
    _fmt(scal.get("power_margin_kW"), ",.2f", " kW"),
)

c2.metric(
    "Required Consumable",
    _fmt(scal.get("required_consumable_kg"), ",.1f", " kg"),
)

c3.metric(
    "Installed Consumable",
    _fmt(scal.get("installed_consumable_kg"), ",.1f", " kg"),
)

c4.metric(
    "Mission Energy",
    _fmt(scal.get("mission_energy_MJ"), ",.1f", " MJ"),
)


# -----------------------------------------------------------------------------
# Architecture-specific mass information
# -----------------------------------------------------------------------------

power_source = str(
    scal.get(
        "power_source",
        run_cfg.get("power_source", ""),
    )
)

if (
    "battery" in power_source
    or "hybrid" in power_source
    or power_source == "solar-RFC"
):
    c1, c2 = st.columns(2)

    c1.metric(
        "Battery Mass",
        _fmt(scal.get("battery_mass_kg"), ",.1f", " kg"),
    )

    c2.metric(
        "Power-System Mass",
        _fmt(out.get("power_system_mass_kg"), ",.1f", " kg"),
    )


if (
    "hydrogen" in power_source
    or power_source == "solar-RFC"
):
    c1, c2 = st.columns(2)

    c1.metric(
        "Hydrogen Tank Mass",
        _fmt(scal.get("tank_mass_kg"), ",.1f", " kg"),
    )

    c2.metric(
        "Tank Volume",
        _fmt(out.get("tank_volume_m3"), ",.2f", " m³"),
    )


st.divider()


# =============================================================================
# Feasibility / constraints
# =============================================================================

st.subheader("Constraint Status")

df_constraints = res.get("df_constraints")

if df_constraints is not None and not df_constraints.empty:

    if "Feasible" in df_constraints.columns:
        all_feasible = bool(df_constraints["Feasible"].all())

        if all_feasible:
            st.success(
                "All reported MDA constraints satisfy the "
                "ADaPT convention g ≤ 0."
            )
        else:
            violated = df_constraints.loc[
                ~df_constraints["Feasible"], "Name"
            ].tolist()

            st.warning(
                "One or more constraints are violated: "
                + ", ".join(map(str, violated))
            )

    st.dataframe(
        df_constraints,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info("No constraint data were returned by the current architecture.")


# =============================================================================
# Geometry
# =============================================================================

st.subheader("Airship Geometry")

g1, g2, g3, g4 = st.columns(4)

g1.metric(
    "Length",
    _fmt(out.get("length_m"), ",.2f", " m"),
)

g2.metric(
    "Maximum Diameter",
    _fmt(out.get("diameter_m"), ",.2f", " m"),
)

g3.metric(
    "Gross Volume",
    _fmt(out.get("gross_volume_m3"), ",.1f", " m³"),
)

g4.metric(
    "Wetted Area",
    _fmt(out.get("wetted_area_m2"), ",.1f", " m²"),
)


fig_profile = res.get("fig_profile")

if fig_profile is not None:
    st.pyplot(
        fig_profile,
        use_container_width=True,
    )


# =============================================================================
# Performance
# =============================================================================

st.subheader("Performance")

p1, p2, p3, p4 = st.columns(4)

p1.metric(
    "Cruise Drag",
    _fmt(out.get("drag_cruise_N"), ",.1f", " N"),
)

p2.metric(
    "Cruise Thrust",
    _fmt(out.get("thrust_cruise_N"), ",.1f", " N"),
)

p3.metric(
    "Takeoff Speed",
    _fmt(out.get("takeoff_speed_mps"), ",.2f", " m/s"),
)

p4.metric(
    "Turn Radius",
    _fmt(out.get("turn_radius_m"), ",.1f", " m"),
)


p1, p2, p3, p4 = st.columns(4)

p1.metric(
    "Ground Roll",
    _fmt(scal.get("ground_roll_m"), ",.1f", " m"),
)

p2.metric(
    "Takeoff Distance",
    _fmt(scal.get("takeoff_distance_m"), ",.1f", " m"),
)

p3.metric(
    "Landing Field Length",
    _fmt(scal.get("landing_field_length_m"), ",.1f", " m"),
)

p4.metric(
    "Mission Duration",
    _fmt(scal.get("mission_duration_hr"), ",.2f", " h"),
)


# =============================================================================
# Mass breakdown
# =============================================================================

st.subheader("Mass Breakdown")

df_mass = res.get("df_mass")

if df_mass is not None and not df_mass.empty:
    st.dataframe(
        df_mass,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No mass-breakdown data were returned.")


# =============================================================================
# Detailed outputs
# =============================================================================

with st.expander("Detailed MDA Outputs"):

    st.markdown("#### Primary Scalars")
    st.json(scal)

    st.markdown("#### Detailed Model Outputs")
    st.json(out)

    st.markdown("#### Normalized Input Configuration")
    st.json(run_cfg)


# =============================================================================
# N2
# =============================================================================

st.divider()
st.subheader("OpenMDAO N² Diagram")

reports = res.get("reports") or {}

n2_html = reports.get("n2_html")

if n2_html:
    components.html(
        n2_html,
        height=900,
        scrolling=True,
    )
else:
    st.info("N² diagram was not generated for this run.")


# =============================================================================
# Downloads
# =============================================================================

st.divider()
st.subheader("Downloads")


# -----------------------------------------------------------------------------
# CSV
# -----------------------------------------------------------------------------

df_csv = res.get("df_csv")

if df_csv is not None:
    st.download_button(
        "Download MDA Results (CSV)",
        data=df_csv.to_csv(index=False).encode("utf-8"),
        file_name="ADaPT_MDA_results.csv",
        mime="text/csv",
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------

d1, d2 = st.columns(2)

n2_path = reports.get("n2_path")

if n2_path and Path(n2_path).exists():
    path = Path(n2_path)

    d1.download_button(
        "Download N² Diagram (HTML)",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/html",
        use_container_width=True,
    )


xdsm_path = reports.get("xdsm_path")

if xdsm_path and Path(xdsm_path).exists():

    path = Path(xdsm_path)

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        mime = "application/pdf"
        label = "Download XDSM (PDF)"

    elif suffix == ".tex":
        mime = "application/x-tex"
        label = "Download XDSM (TEX)"

    else:
        mime = "application/octet-stream"
        label = "Download XDSM"

    d2.download_button(
        label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
        use_container_width=True,
    )