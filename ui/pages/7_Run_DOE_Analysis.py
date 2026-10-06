# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Design of Experiments.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
import math

import pandas as pd
import streamlit as st

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from ui.run_doe import run_doe
from ui_widgets import sidebar_mda_inputs

import adapt.run_DOE as doe


# =============================================================================
# Page
# =============================================================================

st.set_page_config(
    page_title="ADaPT — DOE Analysis",
    page_icon="🧪",
    layout="wide",
)

st.title("ADaPT — Design of Experiments")

st.caption(
    "Architecture-specific optimization and local design-space exploration "
    "using the coupled ADaPT model. DOE samples vary system-level design "
    "variables and real technology inputs; subsystem physics remains inside "
    "the authoritative ADaPT components."
)


# =============================================================================
# Session state
# =============================================================================

if "doe_res" not in st.session_state:
    st.session_state["doe_res"] = None


# =============================================================================
# Current vehicle / mission configuration
# =============================================================================

cfg_mda = sidebar_mda_inputs()


# =============================================================================
# Helpers
# =============================================================================

def _parse_shells(text: str):
    try:
        values = tuple(
            float(x.strip())
            for x in text.split(",")
            if x.strip()
        )
    except ValueError as exc:
        raise ValueError(
            "Shell radii must be comma-separated numerical values."
        ) from exc

    if not values:
        raise ValueError(
            "At least one DOE shell radius is required."
        )

    if any(x <= 0.0 for x in values):
        raise ValueError(
            "All DOE shell radii must be greater than zero."
        )

    return values


def _existing_file(path):
    if not path:
        return None

    p = Path(path)

    return p if p.exists() else None


def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _fmt(value, digits=1):
    if not _finite(value):
        return "—"

    return f"{float(value):,.{digits}f}"


# =============================================================================
# DOE controls
# =============================================================================

with st.sidebar:

    st.divider()
    st.header("DOE Analysis")

    # -------------------------------------------------------------------------
    # Architecture selection
    # -------------------------------------------------------------------------

    st.subheader("Architectures")

    selected = []

    for arch in doe.ARCHES:

        key = arch["key"]
        name = arch["name"]

        if st.checkbox(
            name,
            value=True,
            key=f"doe_arch_{key}",
        ):
            selected.append(key)

    # -------------------------------------------------------------------------
    # Optimization
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader("Architecture Optimization")

    pop_size = st.number_input(
        "DE population size",
        min_value=10,
        max_value=500,
        value=96,
        step=8,
        key="doe_pop",
    )

    n_gen = st.number_input(
        "DE generations",
        min_value=10,
        max_value=1000,
        value=160,
        step=10,
        key="doe_gen",
    )

    optimization_seed = st.number_input(
        "Optimization seed",
        min_value=0,
        max_value=999999,
        value=11,
        step=1,
        key="doe_opt_seed",
    )

    # -------------------------------------------------------------------------
    # Local DOE
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader("Local DOE Cloud")

    n_per_shell = st.number_input(
        "Samples per shell",
        min_value=10,
        max_value=10000,
        value=800,
        step=50,
        key="doe_n_shell",
    )

    shells_text = st.text_input(
        "Shell radii",
        value="0.01, 0.02, 0.04, 0.07, 0.10",
        help=(
            "Normalized perturbation radii around each "
            "architecture-specific optimized design."
        ),
        key="doe_shells",
    )

    doe_seed = st.number_input(
        "DOE seed",
        min_value=0,
        max_value=999999,
        value=13,
        step=1,
        key="doe_seed",
    )

    # -------------------------------------------------------------------------
    # Technology perturbations
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader("Technology Perturbations")

    battery_se_jitter = st.number_input(
        "Battery specific-energy variation ±",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.01,
        format="%.2f",
        help=(
            "Fractional perturbation of battery specific energy. "
            "Example: 0.15 = ±15%."
        ),
        key="doe_bat_se",
    )

    battery_ve_jitter = st.number_input(
        "Battery volumetric-energy variation ±",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.01,
        format="%.2f",
        help=(
            "Fractional perturbation of battery volumetric "
            "energy density."
        ),
        key="doe_bat_ve",
    )

    efficiency_jitter = st.number_input(
        "Efficiency / tank variation ±",
        min_value=0.0,
        max_value=1.0,
        value=0.05,
        step=0.01,
        format="%.2f",
        help=(
            "Architecture-dependent perturbation. It affects ICE "
            "thermal efficiency for combustion architectures, tank "
            "gravimetric efficiency for hydrogen ICE, and solar "
            "efficiency for solar-battery."
        ),
        key="doe_eff",
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
            / "doe"
        ),
        key="doe_output",
    )


# =============================================================================
# Parse DOE configuration
# =============================================================================

shell_error = None

try:
    shells = _parse_shells(
        shells_text
    )
except ValueError as exc:
    shells = ()
    shell_error = str(exc)


cfg = {
    "arches": selected,

    # Current MDA / mission configuration
    "payload_kg": float(
        cfg_mda.get(
            "payload_kg",
            doe.PAYLOAD_KG,
        )
    ),
    "range_m": float(
        cfg_mda.get(
            "range_m",
            doe.RANGE_M,
        )
    ),
    "cruise_alt_m": float(
        cfg_mda.get(
            "cruise_alt_m",
            doe.CRUISE_ALT_M,
        )
    ),
    "cruise_speed_mps": float(
        cfg_mda.get(
            "cruise_speed_mps",
            doe.CRUISE_V_MS,
        )
    ),
    "num_steps": int(
        cfg_mda.get(
            "num_steps",
            doe.NUM_STEPS,
        )
    ),

    # Optimization
    "pop_size": int(pop_size),
    "n_gen": int(n_gen),
    "optimization_seed": int(
        optimization_seed
    ),

    # DOE
    "n_per_shell": int(n_per_shell),
    "shells": shells,
    "doe_seed": int(doe_seed),

    # Technology perturbations
    "battery_se_jitter": float(
        battery_se_jitter
    ),
    "battery_ve_jitter": float(
        battery_ve_jitter
    ),
    "efficiency_jitter": float(
        efficiency_jitter
    ),

    "out_dir": str(out_dir),
}


# =============================================================================
# Study description
# =============================================================================

with st.expander(
    "DOE definition",
    expanded=False,
):

    st.markdown(
        """
The DOE is performed in two stages:

1. **Architecture optimization** — each selected propulsion architecture is
   optimized for PFEI using the active ADaPT feasibility constraints.

2. **Local DOE cloud** — Latin-hypercube samples are generated in normalized
   shells around the architecture-specific optimum.

The active system-level design variables are:

- takeoff buoyancy ratio,
- horizontal tail-volume coefficient,
- vertical tail-volume coefficient,
- drag-due-to-lift factor,
- propeller efficiency.

Technology perturbations are architecture dependent and act on actual ADaPT
component inputs rather than externally recalculating battery, fuel, tank, or
propulsion masses.
"""
    )

    dv_df = pd.DataFrame(
        {
            "Design variable": doe.DV_NAMES,
            "Lower bound": doe.LB,
            "Upper bound": doe.UB,
        }
    )

    st.dataframe(
        dv_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# Run
# =============================================================================

run_btn = st.button(
    "Run DOE Analysis",
    type="primary",
    use_container_width=True,
)


if run_btn:

    if not selected:

        st.error(
            "Select at least one architecture."
        )

    elif shell_error:

        st.error(shell_error)

    else:

        # Do not retain stale results if a new run fails.
        st.session_state["doe_res"] = None

        try:

            with st.spinner(
                "Running architecture optimization and DOE. "
                "This may require substantial computation..."
            ):

                st.session_state["doe_res"] = (
                    run_doe(cfg)
                )

        except Exception as exc:

            st.error(
                "DOE analysis failed."
            )

            st.exception(exc)


# =============================================================================
# Results
# =============================================================================

res = st.session_state.get(
    "doe_res"
)


if res is None:

    st.info(
        "Select the architectures and DOE settings, then click "
        "**Run DOE Analysis**."
    )

else:

    st.success(
        f"DOE complete. Outputs saved in: {res['out_dir']}"
    )

    df_arch = res.get(
        "df_arch",
        pd.DataFrame(),
    )

    # -------------------------------------------------------------------------
    # Overall metrics
    # -------------------------------------------------------------------------

    st.subheader("DOE Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Architectures",
        res.get(
            "n_architectures",
            len(df_arch),
        ),
    )

    c2.metric(
        "Feasible Optima",
        res.get(
            "n_feasible_architectures",
            0,
        ),
    )

    c3.metric(
        "DOE Samples",
        f"{res.get('total_samples', 0):,}",
    )

    feasible_fraction = res.get(
        "feasible_fraction",
        float("nan"),
    )

    c4.metric(
        "Feasible DOE Samples",
        (
            f"{100.0 * feasible_fraction:.1f}%"
            if _finite(feasible_fraction)
            else "—"
        ),
    )

    # -------------------------------------------------------------------------
    # Architecture optima
    # -------------------------------------------------------------------------

    st.subheader(
        "Architecture-Specific Optimized Baselines"
    )

    if not df_arch.empty:

        preferred_columns = [
            "arch",
            "feasible",
            "max_constraint_value",
            "P_req_kW",
            "P_installed_kW",
            "P_margin_kW",
            "owe_kg",
            "mtow_kg",
            "required_consumable_kg",
            "battery_mass_kg",
            "h2_tank_mass_kg",
            "source_energy_MJ",
            "pfei_MJ_per_kg_km",
            "gross_volume_m3",
            "propulsion_mass_kg",
            "power_system_mass_kg",
        ]

        display_columns = [
            c
            for c in preferred_columns
            if c in df_arch.columns
        ]

        st.dataframe(
            df_arch[display_columns],
            use_container_width=True,
            hide_index=True,
        )

    # -------------------------------------------------------------------------
    # Combined DOE trade space
    # -------------------------------------------------------------------------

    combined_png = _existing_file(
        res.get("combined_png")
    )

    if combined_png is not None:

        st.subheader(
            "Architecture DOE Trade Space"
        )

        st.image(
            str(combined_png),
            use_container_width=True,
        )

        st.caption(
            "Architecture-specific local DOE clouds in the "
            "MTOW–PFEI design space. Feasibility is evaluated using "
            "the current ADaPT constraints with g ≤ 0."
        )

    # -------------------------------------------------------------------------
    # Energy-chain context
    # -------------------------------------------------------------------------

    energy_png = _existing_file(
        res.get("energy_png")
    )

    if energy_png is not None:

        st.subheader(
            "Architecture Energy-Conversion Context"
        )

        st.image(
            str(energy_png),
            use_container_width=True,
        )

        st.caption(
            "Configured first-order conversion and propulsive "
            "efficiencies used by the selected architecture models. "
            "This figure is contextual post-processing, not a separate "
            "energy-sizing model."
        )

    # -------------------------------------------------------------------------
    # Per-architecture results
    # -------------------------------------------------------------------------

    st.divider()
    st.subheader(
        "Architecture DOE Clouds"
    )

    arch_plots = res.get(
        "arch_plots",
        {},
    )

    arch_cloud_paths = res.get(
        "arch_clouds",
        {},
    )

    clouds = res.get(
        "clouds",
        {},
    )

    for arch_name in arch_plots.keys():

        with st.expander(
            arch_name,
            expanded=True,
        ):

            png_path = _existing_file(
                arch_plots.get(
                    arch_name
                )
            )

            if png_path is not None:

                st.image(
                    str(png_path),
                    use_container_width=True,
                )

            cloud = clouds.get(
                arch_name
            )

            if (
                cloud is not None
                and not cloud.empty
            ):

                total = len(cloud)

                if "feasible" in cloud.columns:
                    n_feasible = int(
                        cloud["feasible"]
                        .fillna(False)
                        .astype(bool)
                        .sum()
                    )
                else:
                    n_feasible = 0

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Samples",
                    f"{total:,}",
                )

                c2.metric(
                    "Feasible",
                    f"{n_feasible:,}",
                )

                c3.metric(
                    "Feasible Fraction",
                    (
                        f"{100.0*n_feasible/total:.1f}%"
                        if total
                        else "—"
                    ),
                )

                with st.expander(
                    "View DOE data",
                    expanded=False,
                ):

                    st.dataframe(
                        cloud,
                        use_container_width=True,
                        hide_index=True,
                    )

            cloud_path = _existing_file(
                arch_cloud_paths.get(
                    arch_name
                )
            )

            d1, d2 = st.columns(2)

            if cloud_path is not None:

                d1.download_button(
                    "Download DOE Cloud CSV",
                    data=cloud_path.read_bytes(),
                    file_name=cloud_path.name,
                    mime="text/csv",
                    use_container_width=True,
                    key=(
                        "download_doe_cloud_"
                        + arch_name
                    ),
                )

            if png_path is not None:

                d2.download_button(
                    "Download DOE Plot",
                    data=png_path.read_bytes(),
                    file_name=png_path.name,
                    mime="image/png",
                    use_container_width=True,
                    key=(
                        "download_doe_plot_"
                        + arch_name
                    ),
                )


# =============================================================================
# Main downloads
# =============================================================================

if res is not None:

    st.divider()
    st.subheader("Downloads")

    c1, c2, c3 = st.columns(3)

    arch_csv = _existing_file(
        res.get("arch_csv")
    )

    combined_png = _existing_file(
        res.get("combined_png")
    )

    energy_png = _existing_file(
        res.get("energy_png")
    )

    if arch_csv is not None:

        c1.download_button(
            "Architecture Summary CSV",
            data=arch_csv.read_bytes(),
            file_name=arch_csv.name,
            mime="text/csv",
            use_container_width=True,
        )

    if combined_png is not None:

        c2.download_button(
            "Combined DOE Plot",
            data=combined_png.read_bytes(),
            file_name=combined_png.name,
            mime="image/png",
            use_container_width=True,
        )

    if energy_png is not None:

        c3.download_button(
            "Energy-Chain Plot",
            data=energy_png.read_bytes(),
            file_name=energy_png.name,
            mime="image/png",
            use_container_width=True,
        )