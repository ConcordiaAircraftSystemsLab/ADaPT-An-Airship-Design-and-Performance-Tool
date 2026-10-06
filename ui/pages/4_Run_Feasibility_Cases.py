# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Feasibility Analysis.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
import math

import streamlit as st

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from ui.run_feasibility import (
    run_feasibility_single,
    run_feasibility_payload_range,
    run_feasibility_payload_speed,
    run_feasibility_altitude_power_volume,
)

from ui_widgets import sidebar_mda_inputs


# =============================================================================
# Page
# =============================================================================

st.set_page_config(
    page_title="ADaPT — Feasibility Analysis",
    page_icon="🗺️",
    layout="wide",
)

st.title("ADaPT — Feasibility Analysis")

st.caption(
    "Evaluate vehicle–mission feasibility using the current coupled "
    "ADaPT model. Feasibility follows the common convention g ≤ 0."
)


OUT_DIR = Path.cwd() / "app_out" / "feasibility"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Helpers
# =============================================================================

def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _fmt(value, fmt=",.1f", suffix=""):
    if not _finite(value):
        return "—"

    return f"{float(value):{fmt}}{suffix}"


def _optional_limit(
    label,
    default,
    *,
    min_value=None,
    step=1.0,
    key=None,
):
    """
    UI control for optional feasibility constraints.
    """
    enabled = st.checkbox(
        f"Enable {label}",
        value=default is not None,
        key=f"{key}_enabled",
    )

    if not enabled:
        return None

    kwargs = {
        "label": label,
        "value": float(default if default is not None else 0.0),
        "step": float(step),
        "key": key,
    }

    if min_value is not None:
        kwargs["min_value"] = float(min_value)

    return float(st.number_input(**kwargs))


def _download_csv(df, filename, key):
    if df is None or df.empty:
        return

    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
        key=key,
    )


# =============================================================================
# Vehicle / architecture configuration
# =============================================================================

cfg = sidebar_mda_inputs()


# =============================================================================
# Feasibility controls
# =============================================================================

with st.sidebar:

    st.divider()
    st.header("Feasibility Study")

    st.subheader("Optimizer")

    pop_size = st.number_input(
        "DE population size",
        min_value=10,
        max_value=400,
        value=60,
        step=10,
    )

    n_gen = st.number_input(
        "DE generations",
        min_value=10,
        max_value=500,
        value=80,
        step=10,
    )

    seed = st.number_input(
        "Random seed",
        min_value=0,
        max_value=9999,
        value=11,
        step=1,
    )

    st.divider()
    st.subheader("Study-Level Constraints")

    ground_roll_max_m = _optional_limit(
        "Maximum ground roll [m]",
        430.0,
        min_value=0.0,
        step=10.0,
        key="feas_ground_roll",
    )

    mtow_min_kg = _optional_limit(
        "Minimum MTOW [kg]",
        5000.0,
        min_value=0.0,
        step=100.0,
        key="feas_mtow_min",
    )

    mtow_max_kg = _optional_limit(
        "Maximum MTOW [kg]",
        7000.0,
        min_value=0.0,
        step=100.0,
        key="feas_mtow_max",
    )


# =============================================================================
# Tabs
# =============================================================================

tab0, tab1, tab2, tab3 = st.tabs(
    [
        "Single Point",
        "Payload × Range",
        "Payload × Speed",
        "Altitude × Power × Volume",
    ]
)


# =============================================================================
# TAB 0 — single-point feasibility
# =============================================================================

with tab0:

    st.subheader("Single-Point Feasibility")

    st.write(
        "Evaluate the currently selected airship and mission against "
        "the active ADaPT model constraints and study-level limits."
    )

    optimize_single = st.checkbox(
        "Optimize local feasibility variables",
        value=False,
        key="single_optimize",
    )

    run0 = st.button(
        "Evaluate Current Design",
        type="primary",
        use_container_width=True,
        key="run_single_feasibility",
    )

    if run0:

        st.session_state.pop("feas_single", None)

        try:
            with st.spinner(
                "Evaluating current ADaPT configuration..."
            ):
                result = run_feasibility_single(
                    cfg=cfg,
                    optimize=optimize_single,
                    pop_size=int(pop_size),
                    n_gen=int(n_gen),
                    seed=int(seed),
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )

            st.session_state["feas_single"] = result

        except Exception as exc:
            st.error("Single-point feasibility analysis failed.")
            st.exception(exc)

    result = st.session_state.get("feas_single")

    if result:

        feasible = bool(result.get("feasible", False))
        max_g = result.get("max_constraint_value")

        if feasible:
            st.success(
                "FEASIBLE — all active model and study constraints "
                "satisfy g ≤ 0."
            )
        else:
            st.error(
                "INFEASIBLE — at least one active constraint "
                "has g > 0."
            )

        scal = result.get("scalars", {})

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Maximum g",
            _fmt(max_g, ".4g"),
        )

        c2.metric(
            "MTOW",
            _fmt(scal.get("mtow_kg"), ",.1f", " kg"),
        )

        c3.metric(
            "Required Power",
            _fmt(
                scal.get("required_power_kW"),
                ",.2f",
                " kW",
            ),
        )

        c4.metric(
            "Ground Roll",
            _fmt(
                scal.get("ground_roll_m"),
                ",.1f",
                " m",
            ),
        )

        st.subheader("Constraint Status")

        df_constraints = result.get("df_constraints")

        if (
            df_constraints is not None
            and not df_constraints.empty
        ):
            st.dataframe(
                df_constraints,
                use_container_width=True,
                hide_index=True,
            )

        if result.get("best_x") is not None:

            st.subheader("Optimized Feasibility Variables")

            names = [
                "BR_takeoff",
                "Tail volume coefficient — horizontal",
                "Tail volume coefficient — vertical",
                "Drag due to lift factor",
                "Propeller efficiency",
            ]

            best_x = result["best_x"]

            cols = st.columns(len(names))

            for col, name, value in zip(
                cols,
                names,
                best_x,
            ):
                col.metric(
                    name,
                    f"{float(value):.4f}",
                )

        st.subheader("Mass Breakdown")

        df_mass = result.get("df_mass")

        if df_mass is not None:
            st.dataframe(
                df_mass,
                use_container_width=True,
                hide_index=True,
            )

        _download_csv(
            result.get("df_csv"),
            "ADaPT_single_point_feasibility.csv",
            "download_single_feas",
        )


# =============================================================================
# TAB 1 — payload × range
# =============================================================================

with tab1:

    st.subheader("Payload × Range Feasibility")

    st.write(
        "Evaluate how payload and mission range affect MTOW, "
        "energy/consumable requirements, ground roll, power margin, "
        "and overall feasibility."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        payload_min = st.number_input(
            "Payload minimum [kg]",
            value=600.0,
            step=50.0,
            key="pr_payload_min",
        )

    with c2:
        payload_max = st.number_input(
            "Payload maximum [kg]",
            value=2000.0,
            step=50.0,
            key="pr_payload_max",
        )

    with c3:
        payload_n = st.slider(
            "Payload points",
            min_value=3,
            max_value=40,
            value=8,
            key="pr_payload_n",
        )

    range_text = st.text_input(
        "Ranges [km], comma separated",
        value="445, 828, 1231, 1624, 2017",
        key="pr_ranges",
    )

    try:
        range_list_km = [
            float(x.strip())
            for x in range_text.split(",")
            if x.strip()
        ]
    except ValueError:
        st.error(
            "Ranges must be comma-separated numerical values."
        )
        range_list_km = []

    optimize_pr = st.checkbox(
        "Optimize each payload–range point",
        value=True,
        key="pr_optimize",
    )

    run1 = st.button(
        "Run Payload × Range Study",
        type="primary",
        use_container_width=True,
        key="run_payload_range",
    )

    if run1 and range_list_km:

        st.session_state.pop("feas_payload_range", None)

        try:
            with st.spinner(
                "Running payload–range feasibility study..."
            ):

                result = run_feasibility_payload_range(
                    payload_min=float(payload_min),
                    payload_max=float(payload_max),
                    payload_n=int(payload_n),
                    range_list_km=range_list_km,
                    pop_size=int(pop_size),
                    n_gen=int(n_gen),
                    seed=int(seed),
                    out_dir=OUT_DIR,
                    cfg=cfg,
                    optimize_each_point=optimize_pr,
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )

            st.session_state["feas_payload_range"] = result

        except Exception as exc:
            st.error(
                "Payload–range feasibility study failed."
            )
            st.exception(exc)

    result = st.session_state.get(
        "feas_payload_range"
    )

    if result:

        df = result["df"]

        if (
            not df.empty
            and "feasible" in df.columns
        ):

            n_total = len(df)
            n_feasible = int(df["feasible"].sum())

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Cases Evaluated",
                f"{n_total}",
            )

            c2.metric(
                "Feasible Cases",
                f"{n_feasible}",
            )

            c3.metric(
                "Feasible Fraction",
                f"{100.0 * n_feasible / n_total:.1f}%",
            )

        st.subheader("Payload–Range Results")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Mass and Energy Trends")

        st.pyplot(
            result["fig_lines"],
            use_container_width=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Feasibility Map")

            st.pyplot(
                result["fig_feasibility"],
                use_container_width=True,
            )

        with c2:
            st.subheader("Ground-Roll Map")

            st.pyplot(
                result["fig_groundroll"],
                use_container_width=True,
            )

        if result.get("fig_powermargin") is not None:

            st.subheader("Shaft-Power Margin")

            st.pyplot(
                result["fig_powermargin"],
                use_container_width=True,
            )

        _download_csv(
            df,
            "ADaPT_payload_range_feasibility.csv",
            "download_payload_range",
        )


# =============================================================================
# TAB 2 — payload × speed
# =============================================================================

with tab2:

    st.subheader("Payload × Cruise-Speed Feasibility")

    c1, c2, c3 = st.columns(3)

    with c1:
        ps_payload_min = st.number_input(
            "Payload minimum [kg]",
            value=600.0,
            step=50.0,
            key="ps_payload_min",
        )

        speed_min = st.number_input(
            "Speed minimum [m/s]",
            value=12.0,
            step=0.5,
            key="ps_speed_min",
        )

    with c2:
        ps_payload_max = st.number_input(
            "Payload maximum [kg]",
            value=2000.0,
            step=50.0,
            key="ps_payload_max",
        )

        speed_max = st.number_input(
            "Speed maximum [m/s]",
            value=35.0,
            step=0.5,
            key="ps_speed_max",
        )

    with c3:
        ps_payload_n = st.slider(
            "Payload points",
            5,
            40,
            17,
            key="ps_payload_n",
        )

        speed_n = st.slider(
            "Speed points",
            5,
            60,
            24,
            key="ps_speed_n",
        )

    range_m = st.number_input(
        "Mission range [m]",
        value=float(cfg.get("range_m", 1_342_100.0)),
        step=10_000.0,
        key="ps_range",
    )

    optimize_ps = st.checkbox(
        "Optimize each payload–speed point",
        value=True,
        key="ps_optimize",
    )

    run2 = st.button(
        "Run Payload × Speed Study",
        type="primary",
        use_container_width=True,
        key="run_payload_speed",
    )

    if run2:

        st.session_state.pop("feas_payload_speed", None)

        try:
            with st.spinner(
                "Running payload–speed feasibility study..."
            ):

                result = run_feasibility_payload_speed(
                    payload_min=ps_payload_min,
                    payload_max=ps_payload_max,
                    payload_n=ps_payload_n,
                    speed_min=speed_min,
                    speed_max=speed_max,
                    speed_n=speed_n,
                    range_m=range_m,
                    optimize_each_point=optimize_ps,
                    pop_size=pop_size,
                    n_gen=n_gen,
                    seed=seed,
                    out_dir=OUT_DIR,
                    cfg=cfg,
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )

            st.session_state["feas_payload_speed"] = result

        except Exception as exc:
            st.error(
                "Payload–speed feasibility study failed."
            )
            st.exception(exc)

    result = st.session_state.get(
        "feas_payload_speed"
    )

    if result:

        st.pyplot(
            result["fig"],
            use_container_width=True,
        )

        st.dataframe(
            result["df"],
            use_container_width=True,
            hide_index=True,
        )

        _download_csv(
            result["df"],
            "ADaPT_payload_speed_feasibility.csv",
            "download_payload_speed",
        )


# =============================================================================
# TAB 3 — altitude / power / volume
# =============================================================================

with tab3:

    st.subheader(
        "Maximum Altitude × Cruise-Altitude Fraction"
    )

    st.write(
        "Evaluate required shaft power, gross envelope volume, "
        "and feasibility as operating altitude requirements change."
    )

    c1, c2 = st.columns(2)

    with c1:

        max_alt_min_m = st.number_input(
            "Minimum maximum altitude [m]",
            value=2000.0,
            step=500.0,
            key="alt_min",
        )

        max_alt_max_m = st.number_input(
            "Maximum maximum altitude [m]",
            value=12000.0,
            step=500.0,
            key="alt_max",
        )

        max_alt_n = st.slider(
            "Altitude points",
            5,
            60,
            26,
            key="alt_n",
        )

    with c2:

        frac_min = st.number_input(
            "Minimum cruise-altitude fraction",
            value=0.25,
            min_value=0.01,
            max_value=1.0,
            step=0.05,
            key="frac_min",
        )

        frac_max = st.number_input(
            "Maximum cruise-altitude fraction",
            value=1.0,
            min_value=0.01,
            max_value=1.0,
            step=0.05,
            key="frac_max",
        )

        frac_n = st.slider(
            "Cruise-fraction points",
            5,
            40,
            16,
            key="frac_n",
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        payload_fixed = st.number_input(
            "Payload [kg]",
            value=float(cfg.get("payload_kg", 1123.0)),
            step=50.0,
            key="alt_payload",
        )

    with c2:
        speed_fixed = st.number_input(
            "Cruise speed [m/s]",
            value=float(
                cfg.get("cruise_speed_mps", 19.5)
            ),
            step=0.5,
            key="alt_speed",
        )

    with c3:
        altitude_range_m = st.number_input(
            "Mission range [m]",
            value=float(
                cfg.get("range_m", 1_342_100.0)
            ),
            step=10_000.0,
            key="alt_range",
        )

    optimize_alt = st.checkbox(
        "Optimize each altitude point",
        value=False,
        key="alt_optimize",
    )

    run3 = st.button(
        "Run Altitude Study",
        type="primary",
        use_container_width=True,
        key="run_altitude",
    )

    if run3:

        st.session_state.pop("feas_altitude", None)

        try:
            with st.spinner(
                "Running altitude feasibility study..."
            ):

                result = (
                    run_feasibility_altitude_power_volume(
                        max_alt_min_m=max_alt_min_m,
                        max_alt_max_m=max_alt_max_m,
                        max_alt_n=max_alt_n,
                        cruise_frac_min=frac_min,
                        cruise_frac_max=frac_max,
                        cruise_frac_n=frac_n,
                        payload_kg=payload_fixed,
                        speed_ms=speed_fixed,
                        range_m=altitude_range_m,
                        optimize_each_point=optimize_alt,
                        pop_size=pop_size,
                        n_gen=n_gen,
                        seed=seed,
                        out_dir=OUT_DIR,
                        cfg=cfg,
                        ground_roll_max_m=ground_roll_max_m,
                        mtow_min_kg=mtow_min_kg,
                        mtow_max_kg=mtow_max_kg,
                    )
                )

            st.session_state["feas_altitude"] = result

        except Exception as exc:
            st.error(
                "Altitude feasibility study failed."
            )
            st.exception(exc)

    result = st.session_state.get(
        "feas_altitude"
    )

    if result:

        st.pyplot(
            result["fig"],
            use_container_width=True,
        )

        st.dataframe(
            result["df"],
            use_container_width=True,
            hide_index=True,
        )

        _download_csv(
            result["df"],
            "ADaPT_altitude_power_volume.csv",
            "download_altitude",
        )