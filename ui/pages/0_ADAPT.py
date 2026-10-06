# -*- coding: utf-8 -*-
"""
@author: Musavir Bashir
"""

from __future__ import annotations

import streamlit as st

from ui.utils_paths import add_project_root_to_syspath
add_project_root_to_syspath()

from ui.ADAPT import (
    AirshipGeomConfig,
    preset_library,
    geometry_summary_table,
    fig_profile_2d,
    fig_top_view_2d,
    fig_hull_3d,
    cfg_to_json,
    cfg_from_json,
)

st.set_page_config(page_title="Airship Geometry", layout="wide")
st.title("Airship Geometry — Interactive Viewer")

# ----------------------------
# Session state
# ----------------------------
if "geom_cfg" not in st.session_state:
    st.session_state.geom_cfg = AirshipGeomConfig()

presets = preset_library()

# ----------------------------
# Sidebar controls
# ----------------------------
st.sidebar.header("Geometry Inputs")

preset_name = st.sidebar.selectbox("Preset", options=list(presets.keys()), index=0)
if st.sidebar.button("Load preset", use_container_width=True):
    st.session_state.geom_cfg = presets[preset_name]

cfg: AirshipGeomConfig = st.session_state.geom_cfg

cfg.length_m = st.sidebar.number_input("Length [m]", min_value=5.0, max_value=300.0, value=float(cfg.length_m), step=0.5)
cfg.fineness_ratio = st.sidebar.number_input("Fineness ratio L/D [-]", min_value=1.5, max_value=12.0, value=float(cfg.fineness_ratio), step=0.1)
cfg.hull_shape = st.sidebar.selectbox("Hull shape", ["Prolate spheroid", "NPL-like (smooth)", "Elliptic (simple)"], index=["Prolate spheroid","NPL-like (smooth)","Elliptic (simple)"].index(cfg.hull_shape))
cfg.n_profile_pts = st.sidebar.slider("Profile resolution", 200, 2000, int(cfg.n_profile_pts), 50)

st.sidebar.divider()
st.sidebar.subheader("Add-ons (display-only for now)")
cfg.has_gondola = st.sidebar.checkbox("Show gondola", value=bool(cfg.has_gondola))
if cfg.has_gondola:
    cfg.gondola_length_m = st.sidebar.number_input("Gondola length [m]", 1.0, 40.0, float(cfg.gondola_length_m), 0.5)
    cfg.gondola_height_m = st.sidebar.number_input("Gondola height [m]", 0.3, 10.0, float(cfg.gondola_height_m), 0.1)

cfg.has_tail = st.sidebar.checkbox("Show tail (placeholder dims)", value=bool(cfg.has_tail))
if cfg.has_tail:
    cfg.tail_span_m = st.sidebar.number_input("Tail span [m]", 0.5, 60.0, float(cfg.tail_span_m), 0.5)
    cfg.tail_height_m = st.sidebar.number_input("Tail height [m]", 0.5, 60.0, float(cfg.tail_height_m), 0.5)

st.sidebar.divider()
st.sidebar.subheader("Buoyancy reference (quick intuition)")
cfg.rho_air_kg_m3 = st.sidebar.number_input("Air density [kg/m³]", 0.5, 1.5, float(cfg.rho_air_kg_m3), 0.01)
cfg.rho_helium_kg_m3 = st.sidebar.number_input("Helium density [kg/m³]", 0.05, 0.30, float(cfg.rho_helium_kg_m3), 0.001)

# Write back
st.session_state.geom_cfg = cfg

# ----------------------------
# Main tabs
# ----------------------------
tab_overview, tab_2d, tab_3d, tab_table, tab_io = st.tabs(
    ["Overview", "2D Views", "3D Hull", "Dimensions Table", "Export / Import"]
)

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)

    summary = geometry_summary_table(cfg)
    # Extract a few top metrics for st.metric()
    L = float(summary.loc[summary["Metric"] == "Length [m]", "Value"].values[0])
    D = float(summary.loc[summary["Metric"] == "Max diameter [m]", "Value"].values[0])
    V = float(summary.loc[summary["Metric"] == "Volume (hull) [m^3]", "Value"].values[0])
    lift = float(summary.loc[summary["Metric"] == "Net buoyant lift (He) [kg]", "Value"].values[0])

    col1.metric("Length [m]", f"{L:,.2f}")
    col2.metric("Diameter [m]", f"{D:,.2f}")
    col3.metric("Hull volume [m³]", f"{V:,.0f}")
    col4.metric("Net lift (He) [kg]", f"{lift:,.0f}")

    st.info(
        "This page is geometry-only (fast). Later you can feed these values into MDA/Optimization/DOE."
    )

with tab_2d:
    c1, c2 = st.columns(2)
    with c1:
        st.pyplot(fig_profile_2d(cfg), clear_figure=True)
    with c2:
        st.pyplot(fig_top_view_2d(cfg), clear_figure=True)

with tab_3d:
    st.plotly_chart(fig_hull_3d(cfg), use_container_width=True)

with tab_table:
    st.dataframe(geometry_summary_table(cfg), use_container_width=True, hide_index=True)

with tab_io:
    st.subheader("Export geometry config (JSON)")
    j = cfg_to_json(cfg)
    st.code(j, language="json")
    st.download_button("Download JSON", data=j, file_name="airship_geometry.json", mime="application/json")

    st.divider()
    st.subheader("Import geometry config (JSON)")
    uploaded = st.file_uploader("Upload airship_geometry.json", type=["json"])
    if uploaded is not None:
        try:
            txt = uploaded.read().decode("utf-8")
            st.session_state.geom_cfg = cfg_from_json(txt)
            st.success("Loaded JSON into the current session.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to read JSON: {e}")
