# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Multidisciplinary Optimization.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd
import streamlit as st

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from ui.run_optimization import run_optimization
from ui_widgets import sidebar_mda_inputs

import adapt.run_Optimization as opt


# =============================================================================
# Page
# =============================================================================

st.set_page_config(
    page_title="ADaPT — Optimization",
    page_icon="🎯",
    layout="wide",
)

st.title(
    "ADaPT — Multidisciplinary Optimization"
)

st.caption(
    "Minimum-MTOW airship optimization using the coupled ADaPT model. "
    "The optimizer changes selected system-level design variables while "
    "geometry, mass, aerodynamics, propulsion, mission, energy-system and "
    "feasibility physics remain in their authoritative ADaPT components."
)


# =============================================================================
# Session state
# =============================================================================

if "opt_res" not in st.session_state:
    st.session_state["opt_res"] = None


# =============================================================================
# Current MDA configuration
# =============================================================================

cfg_mda = sidebar_mda_inputs()


# =============================================================================
# Helpers
# =============================================================================

def _finite(value):
    try:
        return math.isfinite(
            float(value)
        )
    except (TypeError, ValueError):
        return False


def _fmt(value, digits=1):
    if not _finite(value):
        return "—"

    return (
        f"{float(value):,.{digits}f}"
    )


def _optional_number(text):
    text = str(text).strip()

    if not text:
        return None

    return float(text)


# =============================================================================
# Optimization controls
# =============================================================================

with st.sidebar:

    st.divider()
    st.header("Optimization")

    # -------------------------------------------------------------------------
    # Algorithm
    # -------------------------------------------------------------------------

    st.subheader(
        "Differential Evolution"
    )

    pop_size = st.number_input(
        "Population size",
        min_value=10,
        max_value=2000,
        value=200,
        step=10,
        key="opt_population",
    )

    n_gen = st.number_input(
        "Generations",
        min_value=1,
        max_value=5000,
        value=400,
        step=10,
        key="opt_generations",
    )

    seed = st.number_input(
        "Random seed",
        min_value=0,
        max_value=999999,
        value=11,
        step=1,
        key="opt_seed",
    )

    jitter = st.number_input(
        "Initial population jitter",
        min_value=0.0,
        max_value=1.0,
        value=0.08,
        step=0.01,
        format="%.2f",
        help=(
            "Normalized perturbation around the current "
            "ADaPT design used when seeding part of the "
            "initial DE population."
        ),
        key="opt_jitter",
    )

    verbose = st.checkbox(
        "Verbose console output",
        value=False,
        key="opt_verbose",
    )

    # -------------------------------------------------------------------------
    # Constraint shaping
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader(
        "Optimization Constraints"
    )

    ground_roll_max_m = st.number_input(
        "Maximum ground roll [m]",
        min_value=0.0,
        value=float(
            opt.GROUND_ROLL_MAX_M
        ),
        step=10.0,
        key="opt_ground_roll",
    )

    power_margin_cap_kw = st.number_input(
        "Maximum installed power margin [kW]",
        min_value=0.0,
        value=float(
            opt.POWER_MARGIN_CAP_W
            / 1000.0
        ),
        step=5.0,
        key="opt_power_margin",
    )

    power_margin_penalty = st.number_input(
        "Positive power-margin penalty",
        min_value=0.0,
        value=float(
            opt.POWER_MARGIN_PENALTY
        ),
        step=1.0e-5,
        format="%.1e",
        help=(
            "Small shaping penalty added to MTOW for "
            "excess positive installed-power margin."
        ),
        key="opt_power_penalty",
    )

    max_volume_text = st.text_input(
        "Maximum envelope volume [m³]",
        value="",
        help=(
            "Leave blank to disable the optional "
            "envelope-volume constraint."
        ),
        key="opt_volume_cap",
    )

    # -------------------------------------------------------------------------
    # Bounds
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader(
        "Design-Variable Bounds"
    )

    st.caption(
        "Installed shaft power is TOTAL aircraft "
        "propulsor shaft power."
    )

    lower_bounds = []
    upper_bounds = []

    for i, name in enumerate(
        opt.DV_NAMES
    ):

        st.markdown(
            f"**{name}**"
        )

        c1, c2 = st.columns(2)

        lower = c1.number_input(
            "Lower",
            value=float(
                opt.DEFAULT_LOWER_BOUNDS[i]
            ),
            format="%.6g",
            key=f"opt_lb_{name}",
        )

        upper = c2.number_input(
            "Upper",
            value=float(
                opt.DEFAULT_UPPER_BOUNDS[i]
            ),
            format="%.6g",
            key=f"opt_ub_{name}",
        )

        lower_bounds.append(
            float(lower)
        )

        upper_bounds.append(
            float(upper)
        )

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader("Output")

    out_dir = st.text_input(
        "Output folder",
        value=str(
            Path.cwd()
            / "app_out"
            / "optimization"
        ),
        key="opt_output",
    )


# =============================================================================
# Parse optional values
# =============================================================================

volume_error = None

try:
    max_envelope_volume_m3 = (
        _optional_number(
            max_volume_text
        )
    )
except ValueError:
    max_envelope_volume_m3 = None
    volume_error = (
        "Maximum envelope volume must "
        "be a numerical value."
    )


# =============================================================================
# Build backend configuration
# =============================================================================

cfg = dict(cfg_mda)

cfg.update(
    {
        "pop_size": int(
            pop_size
        ),

        "n_gen": int(
            n_gen
        ),

        "seed": int(
            seed
        ),

        "jitter": float(
            jitter
        ),

        "verbose": bool(
            verbose
        ),

        "ground_roll_max_m": float(
            ground_roll_max_m
        ),

        "power_margin_cap_w": (
            float(
                power_margin_cap_kw
            )
            * 1000.0
        ),

        "power_margin_penalty": float(
            power_margin_penalty
        ),

        "max_envelope_volume_m3":
            max_envelope_volume_m3,

        "lower_bounds":
            lower_bounds,

        "upper_bounds":
            upper_bounds,

        "out_dir":
            str(out_dir),
    }
)


# =============================================================================
# Optimization definition
# =============================================================================

with st.expander(
    "Optimization definition",
    expanded=False,
):

    st.markdown(
        """
### Objective

The primary objective is minimum aircraft MTOW. The optimization backend
uses

\[
J =
m_{\\mathrm{TOW}}
+
w_P
\\left(
\\frac{
\\max(P_{\\mathrm{installed}}-P_{\\mathrm{required}},0)
}{1000}
\\right)^2 .
\]

The second term is a small shaping penalty for unnecessary positive installed
power margin; it is not a separate aircraft sizing model.

### Feasibility convention

All optimization constraints use

\[
g_i(\\mathbf{x}) \\leq 0.
\]

The native ADaPT feasibility constraints are combined with the optional
optimization-level limits on ground roll, positive installed-power margin,
and envelope volume.

### Design variables

The current optimization contains eight system-level design variables.
"""
    )

    bounds_df = pd.DataFrame(
        {
            "Design Variable":
                opt.DV_NAMES,

            "Lower Bound":
                lower_bounds,

            "Upper Bound":
                upper_bounds,
        }
    )

    st.dataframe(
        bounds_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# Run
# =============================================================================

run_btn = st.button(
    "Run Optimization",
    type="primary",
    use_container_width=True,
)


if run_btn:

    if volume_error:

        st.error(volume_error)

    elif any(
        lo >= hi
        for lo, hi in zip(
            lower_bounds,
            upper_bounds,
        )
    ):

        st.error(
            "Every design-variable lower bound "
            "must be smaller than its upper bound."
        )

    else:

        # Remove stale result before starting.
        st.session_state[
            "opt_res"
        ] = None

        try:

            with st.spinner(
                "Running coupled ADaPT "
                "multidisciplinary optimization..."
            ):

                st.session_state[
                    "opt_res"
                ] = run_optimization(
                    cfg
                )

        except Exception as exc:

            st.error(
                "Optimization failed."
            )

            st.exception(exc)


# =============================================================================
# Results
# =============================================================================

res = st.session_state.get(
    "opt_res"
)


if res is None:

    st.info(
        "Configure the optimization and click "
        "**Run Optimization**."
    )

else:

    scal = res["scalars"]

    feasible = bool(
        scal.get(
            "feasible",
            False,
        )
    )

    if feasible:

        st.success(
            "Optimization complete — "
            "best returned design is feasible."
        )

    else:

        st.warning(
            "Optimization complete, but the best returned "
            "candidate violates at least one active constraint."
        )

    # -------------------------------------------------------------------------
    # Primary metrics
    # -------------------------------------------------------------------------

    st.subheader(
        "Optimized Aircraft"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "MTOW",
        (
            f"{_fmt(scal.get('mtow_kg'))} kg"
        ),
    )

    c2.metric(
        "Required Shaft Power",
        (
            f"{_fmt(scal.get('required_shaft_total_kW'))} kW"
        ),
    )

    c3.metric(
        "Installed Shaft Power",
        (
            f"{_fmt(scal.get('installed_power_total_kW'))} kW"
        ),
    )

    c4.metric(
        "Power Margin",
        (
            f"{_fmt(scal.get('power_margin_total_kW'))} kW"
        ),
    )

    c5, c6, c7, c8 = st.columns(4)

    c5.metric(
        "Ground Roll",
        (
            f"{_fmt(scal.get('ground_roll_m'))} m"
        ),
    )

    c6.metric(
        "Envelope Volume",
        (
            f"{_fmt(scal.get('gross_volume_m3'))} m³"
        ),
    )

    c7.metric(
        "Objective",
        _fmt(
            scal.get("objective"),
            digits=3,
        ),
    )

    max_g = scal.get(
        "max_g",
        np.nan,
    )

    c8.metric(
        "Maximum g",
        (
            f"{float(max_g):.3e}"
            if _finite(max_g)
            else "—"
        ),
    )

    # -------------------------------------------------------------------------
    # Best design
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader(
        "Optimized Design Variables"
    )

    st.dataframe(
        res["df_design"],
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    st.subheader(
        "Constraint Status"
    )

    st.caption(
        "Current ADaPT optimization convention: "
        "g ≤ 0 is feasible."
    )

    df_constraints = res[
        "df_constraints"
    ].copy()

    st.dataframe(
        df_constraints,
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------------
    # Complete result
    # -------------------------------------------------------------------------

    with st.expander(
        "Complete optimized result",
        expanded=False,
    ):

        st.dataframe(
            res["df_best"],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander(
        "Optimization settings used",
        expanded=False,
    ):

        settings_df = pd.DataFrame(
            [
                {
                    "Setting": key,
                    "Value": value,
                }
                for key, value
                in res[
                    "settings_used"
                ].items()
            ]
        )

        st.dataframe(
            settings_df,
            use_container_width=True,
            hide_index=True,
        )

    # -------------------------------------------------------------------------
    # Download
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader("Download")

    st.download_button(
        "Download Optimized Design CSV",
        data=(
            res["df_csv"]
            .to_csv(index=False)
            .encode("utf-8")
        ),
        file_name=(
            "best_mdo_design.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        f"Saved to: "
        f"{res['paths']['best_csv']}"
    )