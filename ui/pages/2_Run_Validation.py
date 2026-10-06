# -*- coding: utf-8 -*-
"""
ADaPT Streamlit page — Reference-Airship Validation.

Author: Musavir Bashir
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from utils_paths import add_project_root_to_syspath

add_project_root_to_syspath()

from run_validation_cases import (
    CASE_LIBRARY,
    run_validation,
)


# =============================================================================
# Page configuration
# =============================================================================

st.set_page_config(
    page_title="ADaPT — Validation",
    page_icon="✅",
    layout="wide",
)

st.title(
    "ADaPT — Reference-Airship Validation"
)

st.caption(
    "Validation of the current ADaPT framework against published "
    "reference-airship data. Known reference quantities are prescribed; "
    "independently calculated quantities are compared with available data."
)


# =============================================================================
# Helpers
# =============================================================================

def _finite(value) -> bool:

    try:
        return math.isfinite(
            float(value)
        )
    except Exception:
        return False


def _fmt(
    value,
    digits: int = 1,
) -> str:

    if not _finite(value):
        return "—"

    return (
        f"{float(value):,.{digits}f}"
    )


# =============================================================================
# Case selection
# =============================================================================

with st.sidebar:

    st.header(
        "Validation Case"
    )

    validation_case = st.selectbox(
        "Reference airship",
        options=list(
            CASE_LIBRARY.keys()
        ),
    )

    case_meta = CASE_LIBRARY[
        validation_case
    ]

    st.info(
        case_meta["description"]
    )

    st.markdown(
        f"""
**Airship type:**  
`{case_meta["airship_type"]}`

**Analysis mode:**  
Reference-aircraft validation

**Constraint convention:**  
`g ≤ 0` = feasible
"""
    )

    st.divider()

    st.caption(
        "Reference geometry, mission conditions and installed "
        "hardware are defined by the selected authoritative "
        "validation driver and are intentionally not editable here."
    )


# =============================================================================
# Reference case explanation
# =============================================================================

if validation_case == "A-170 (Non-rigid)":

    st.subheader(
        "A-170 Non-rigid Airship"
    )

    st.markdown(
        """
The A-170 validation fixes the published/reference vehicle geometry,
mission conditions and installed capacities. ADaPT then predicts the
remaining coupled geometry, mass and performance quantities.

This is a **validation problem**, not a clean-sheet sizing problem.
Therefore quantities such as length, payload, range and installed power
are deliberately prescribed.
"""
    )

else:

    st.subheader(
        "Zeppelin NT 07-101"
    )

    st.markdown(
        """
The Zeppelin NT case validates the semi-rigid formulation against the
published Zeppelin NT 07-101 configuration.

The validation uses a dedicated semi-rigid structural calibration for
the Zeppelin reference aircraft without modifying the universal
ADaPT weight model.
"""
    )


# =============================================================================
# Run
# =============================================================================

run_btn = st.button(
    "Run Reference Validation",
    type="primary",
    use_container_width=True,
)


if "validation_result" not in st.session_state:

    st.session_state[
        "validation_result"
    ] = None


if "validation_case_last" not in st.session_state:

    st.session_state[
        "validation_case_last"
    ] = None


if run_btn:

    cfg = {
        "validation_case":
            validation_case,
    }

    try:

        with st.spinner(
            f"Running {validation_case} validation..."
        ):

            result = run_validation(
                cfg
            )

        st.session_state[
            "validation_result"
        ] = result

        st.session_state[
            "validation_case_last"
        ] = validation_case

    except Exception as exc:

        st.error(
            f"{validation_case} validation failed."
        )

        st.exception(exc)


# =============================================================================
# Results
# =============================================================================

res = st.session_state.get(
    "validation_result"
)


if res is None:

    st.info(
        "Select a reference aircraft and click "
        "**Run Reference Validation**."
    )

else:

    scal = res["scalars"]

    result_case = res.get(
        "case",
        st.session_state.get(
            "validation_case_last",
            "",
        ),
    )

    st.divider()

    st.header(
        f"Results — {result_case}"
    )

    # -------------------------------------------------------------------------
    # Overall status
    # -------------------------------------------------------------------------

    if scal.get(
        "feasible",
        False,
    ):

        st.success(
            "All reported ADaPT feasibility constraints satisfy "
            "the current g ≤ 0 convention."
        )

    else:

        st.warning(
            "At least one reported ADaPT feasibility constraint "
            "is positive."
        )

    # -------------------------------------------------------------------------
    # Main metrics
    # -------------------------------------------------------------------------

    c1, c2, c3, c4 = st.columns(
        4
    )

    c1.metric(
        "MTOW",
        (
            f"{_fmt(scal.get('mtow_kg'))} kg"
        ),
    )

    c2.metric(
        "OEW",
        (
            f"{_fmt(scal.get('owe_kg'))} kg"
        ),
    )

    c3.metric(
        "Gross Volume",
        (
            f"{_fmt(scal.get('gross_volume_m3'))} m³"
        ),
    )

    c4.metric(
        "BR Takeoff",
        _fmt(
            scal.get(
                "BR_takeoff"
            ),
            3,
        ),
    )

    c5, c6, c7, c8 = st.columns(
        4
    )

    c5.metric(
        "Required Shaft Power",
        (
            f"{_fmt(scal.get('required_power_kW'))} kW"
        ),
    )

    c6.metric(
        "Installed Shaft Power",
        (
            f"{_fmt(scal.get('installed_power_kW'))} kW"
        ),
    )

    c7.metric(
        "Consumable Capacity",
        (
            f"{_fmt(scal.get('consumable_capacity_kg'))} kg"
        ),
    )

    c8.metric(
        "Takeoff / Ground Distance",
        (
            f"{_fmt(scal.get('ground_roll_m'))} m"
        ),
    )


    # =========================================================================
    # Tabs
    # =========================================================================

    (
        tab_validation,
        tab_constraints,
        tab_mass,
        tab_reference,
    ) = st.tabs(
        [
            "Validation Comparison",
            "Constraints",
            "Mass Breakdown",
            "Reference Case",
        ]
    )


    # =========================================================================
    # Validation table
    # =========================================================================

    with tab_validation:

        st.subheader(
            "Reference vs ADaPT"
        )

        st.caption(
            "REF = prescribed reference quantity; "
            "PRED = independently predicted vehicle quantity; "
            "PERF = predicted performance quantity. "
            "Percent error is not reported for REF quantities because "
            "their values were intentionally imposed."
        )

        df_val = res[
            "df_validation"
        ].copy()

        st.dataframe(
            df_val,
            use_container_width=True,
            hide_index=True,
            column_config={
                "% Error":
                    st.column_config.NumberColumn(
                        "% Error",
                        format="%.2f%%",
                    ),
            },
        )

        # -------------------------------------------------------------
        # Error plot only for genuine predicted validation quantities
        # -------------------------------------------------------------

        if (
            "% Error" in df_val.columns
            and "Role" in df_val.columns
        ):

            plot_df = df_val[
                (
                    df_val["Role"]
                    != "REF"
                )
                & (
                    pd.to_numeric(
                        df_val["% Error"],
                        errors="coerce",
                    ).notna()
                )
            ].copy()

            if not plot_df.empty:

                st.subheader(
                    "Prediction Error"
                )

                st.bar_chart(
                    plot_df.set_index(
                        "Parameter"
                    )["% Error"],
                    horizontal=True,
                )


    # =========================================================================
    # Constraints
    # =========================================================================

    with tab_constraints:

        st.subheader(
            "Feasibility Constraints"
        )

        st.caption(
            "The current ADaPT convention is g ≤ 0 for feasibility."
        )

        st.dataframe(
            res["df_constraints"],
            use_container_width=True,
            hide_index=True,
        )


    # =========================================================================
    # Mass breakdown
    # =========================================================================

    with tab_mass:

        st.subheader(
            "Model Mass Breakdown"
        )

        df_mass = res[
            "df_mass"
        ].copy()

        st.dataframe(
            df_mass,
            use_container_width=True,
            hide_index=True,
        )

        if (
            not df_mass.empty
            and "Component"
            in df_mass.columns
            and "Mass [kg]"
            in df_mass.columns
        ):

            plot_mass = df_mass[
                ~df_mass[
                    "Component"
                ].isin(
                    [
                        "Operating empty weight",
                        "Maximum takeoff weight",
                    ]
                )
            ].copy()

            if not plot_mass.empty:

                st.bar_chart(
                    plot_mass.set_index(
                        "Component"
                    )["Mass [kg]"],
                    horizontal=True,
                )


    # =========================================================================
    # Reference case
    # =========================================================================

    with tab_reference:

        st.subheader(
            "Reference Inputs"
        )

        reference = res.get(
            "reference",
            {},
        )

        if reference:

            reference_df = pd.DataFrame(
                [
                    {
                        "Parameter": key,
                        "Reference Value": value,
                    }
                    for key, value
                    in reference.items()
                ]
            )

            st.dataframe(
                reference_df,
                use_container_width=True,
                hide_index=True,
            )

        st.info(
            "These values define the reference-aircraft validation "
            "case. They are intentionally fixed rather than exposed "
            "as sizing controls."
        )


    # =========================================================================
    # Download
    # =========================================================================

    st.divider()

    safe_case = (
        result_case
        .lower()
        .replace(" ", "_")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    st.download_button(
        "Download Validation Results CSV",
        data=(
            res["df_csv"]
            .to_csv(index=False)
            .encode("utf-8")
        ),
        file_name=(
            f"{safe_case}_validation_results.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )