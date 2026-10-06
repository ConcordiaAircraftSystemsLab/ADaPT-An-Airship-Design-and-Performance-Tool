# -*- coding: utf-8 -*-
"""
ADaPT validation adapter for Streamlit.

The validation physics and reference-aircraft definitions remain in the
authoritative validation drivers:

    validation/validation_1_paper_with_pymoo_a170.py
    validation/validation_1_paper_with_pymoo_zeppelin.py

This module does NOT reconstruct the validation cases.  It only:
    1. selects the requested authoritative driver,
    2. runs its baseline/reference OpenMDAO model,
    3. converts model outputs into UI-ready tables.

Author: Musavir Bashir
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


# =============================================================================
# Project paths
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = PROJECT_ROOT / "validation"
ADAPT_DIR = PROJECT_ROOT / "adapt"

for path in (
    PROJECT_ROOT,
    VALIDATION_DIR,
    ADAPT_DIR,
):
    p = str(path)

    if p not in sys.path:
        sys.path.insert(0, p)


# =============================================================================
# Public case library
# =============================================================================

CASE_LIBRARY = {
    "A-170 (Non-rigid)": {
        "key": "a170",
        "airship_type": "non-rigid",
        "description": (
            "A-170 non-rigid reference-airship validation using "
            "published geometry, mission conditions and installed hardware."
        ),
    },

    "Zeppelin NT 07-101 (Semi-rigid)": {
        "key": "zeppelin",
        "airship_type": "semi-rigid",
        "description": (
            "Zeppelin NT 07-101 semi-rigid reference-airship validation "
            "using the dedicated Zeppelin structural calibration."
        ),
    },
}


# =============================================================================
# Utilities
# =============================================================================

def _scalar(
    prob,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:

    try:
        value = prob.get_val(
            name,
            units=units,
        )

        return float(
            np.asarray(
                value,
                dtype=float,
            ).reshape(-1)[0]
        )

    except Exception:
        return float(default)


def _max_scalar(
    prob,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:

    try:
        value = prob.get_val(
            name,
            units=units,
        )

        array = np.asarray(
            value,
            dtype=float,
        ).reshape(-1)

        return float(
            np.max(array)
        )

    except Exception:
        return float(default)


def _percent_error(
    calculated: float,
    reference: float,
) -> float:

    if (
        not np.isfinite(calculated)
        or not np.isfinite(reference)
        or reference == 0.0
    ):
        return np.nan

    return (
        (calculated - reference)
        / reference
        * 100.0
    )


def _constraint_row(
    name: str,
    value: float,
    units: str = "-",
) -> Dict[str, Any]:
    """
    Current ADaPT validation convention:

        g <= 0  -> feasible
    """

    feasible = (
        bool(value <= 0.0)
        if np.isfinite(value)
        else False
    )

    return {
        "Constraint": name,
        "Value": value,
        "Units": units,
        "Feasible": feasible,
    }


# =============================================================================
# Protect against Zeppelin validation monkey-patching
# =============================================================================

def _restore_standard_weight_model() -> None:
    """
    Restore the standard AirshipWeight constructor in AirshipAnalysisGroup.

    This is necessary because the Zeppelin validation intentionally installs
    a validation-specific semi-rigid AirshipWeight subclass.
    """

    import AirshipAnalysisGroup as group_module
    import AirshipWeight as weight_module

    group_module.AirshipWeight = (
        weight_module.AirshipWeight
    )


def _activate_zeppelin_weight_model(
    zeppelin_module,
) -> None:
    """
    Explicitly activate the Zeppelin validation-specific weight model.
    """

    import AirshipAnalysisGroup as group_module

    group_module.AirshipWeight = (
        zeppelin_module.ZeppelinNTAirshipWeight
    )


# =============================================================================
# Driver loading
# =============================================================================

def _load_a170_driver():

    _restore_standard_weight_model()

    module_name = (
        "validation_1_paper_with_pymoo_a170"
    )

    module = importlib.import_module(
        module_name
    )

    # Ensure A-170 always uses the standard model,
    # even if Zeppelin was run previously.
    _restore_standard_weight_model()

    return module


def _load_zeppelin_driver():

    module_name = (
        "validation_1_paper_with_pymoo_zeppelin"
    )

    module = importlib.import_module(
        module_name
    )

    _activate_zeppelin_weight_model(
        module
    )

    return module


# =============================================================================
# A-170
# =============================================================================

def _run_a170() -> Dict[str, Any]:

    mod = _load_a170_driver()

    prob = mod.build_problem(
        power_source="conventional_reciprocating",
    )

    try:

        # build_problem() already runs the model in the
        # authoritative validation driver.

        ref = mod.A170_REFERENCE

        # ---------------------------------------------------------------------
        # Scalars
        # ---------------------------------------------------------------------

        mtow = _scalar(
            prob,
            "mtow",
            "kg",
        )

        owe = _scalar(
            prob,
            "owe",
            "kg",
        )

        gross_volume = _scalar(
            prob,
            "gross_volume",
            "m**3",
        )

        wetted_area = _scalar(
            prob,
            "wetted_surface_area",
            "m**2",
        )

        ground_roll = _scalar(
            prob,
            "ground_roll_distance",
            "m",
        )

        required_power = _max_scalar(
            prob,
            "required_shaft_power",
            "W",
        )

        installed_power = _scalar(
            prob,
            "installed_shaft_power",
            "W",
        )

        installed_consumable = _scalar(
            prob,
            "installed_consumable_mass",
            "kg",
        )

        buoyancy_g = _max_scalar(
            prob,
            "buoyancy_constraint",
            "N",
        )

        power_g = _max_scalar(
            prob,
            "power_constraint",
            "W",
        )

        energy_g = _max_scalar(
            prob,
            "energy_constraint",
        )

        scalars = {
            "case":
                "A-170 (Non-rigid)",

            "airship_type":
                "non-rigid",

            "mtow_kg":
                mtow,

            "owe_kg":
                owe,

            "gross_volume_m3":
                gross_volume,

            "wetted_area_m2":
                wetted_area,

            "ground_roll_m":
                ground_roll,

            "required_power_kW":
                required_power / 1000.0,

            "installed_power_kW":
                installed_power / 1000.0,

            "consumable_capacity_kg":
                installed_consumable,

            "BR_takeoff":
                _scalar(
                    prob,
                    "BR_takeoff",
                ),

            "buoyancy_constraint":
                buoyancy_g,

            "power_constraint":
                power_g,

            "energy_constraint":
                energy_g,

            "feasible":
                bool(
                    np.isfinite(buoyancy_g)
                    and np.isfinite(power_g)
                    and np.isfinite(energy_g)
                    and buoyancy_g <= 0.0
                    and power_g <= 0.0
                    and energy_g <= 0.0
                ),
        }

        # ---------------------------------------------------------------------
        # Validation table
        # ---------------------------------------------------------------------

        validation_definitions = [
            # --------------------------------------------------------------
            # Prescribed reference quantities
            # --------------------------------------------------------------
            {
                "Role": "REF",
                "Parameter": "Length",
                "Reference": ref["length_m"],
                "Tool": _scalar(
                    prob,
                    "length",
                    "m",
                ),
                "Units": "m",
                "Interpretation":
                    "Prescribed A-170 reference geometry",
            },

            {
                "Role": "REF",
                "Parameter": "Fineness ratio",
                "Reference":
                    ref["fineness_ratio"],
                "Tool": _scalar(
                    prob,
                    "fineness_ratio",
                ),
                "Units": "-",
                "Interpretation":
                    "Prescribed A-170 reference geometry",
            },

            {
                "Role": "REF",
                "Parameter": "Payload",
                "Reference":
                    ref["payload_kg"],
                "Tool": _scalar(
                    prob,
                    "payload",
                    "kg",
                ),
                "Units": "kg",
                "Interpretation":
                    "Prescribed validation loading",
            },

            {
                "Role": "REF",
                "Parameter": "Range",
                "Reference":
                    ref["range_m"],
                "Tool": _scalar(
                    prob,
                    "range",
                    "m",
                ),
                "Units": "m",
                "Interpretation":
                    "Prescribed reference mission",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Installed shaft power",

                "Reference":
                    ref[
                        "installed_shaft_power_w"
                    ]
                    / 1000.0,

                "Tool":
                    installed_power
                    / 1000.0,

                "Units": "kW",

                "Interpretation":
                    "Prescribed installed capacity",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Installed consumable capacity",

                "Reference":
                    ref[
                        "installed_consumable_capacity_kg"
                    ],

                "Tool":
                    installed_consumable,

                "Units": "kg",

                "Interpretation":
                    "Prescribed A-170 fuel capacity",
            },

            # --------------------------------------------------------------
            # Predicted quantities
            # --------------------------------------------------------------
            {
                "Role": "PRED",
                "Parameter":
                    "Gross volume",

                "Reference":
                    np.nan,

                "Tool":
                    gross_volume,

                "Units": "m³",

                "Interpretation":
                    "Predicted geometry quantity",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Wetted surface area",

                "Reference":
                    np.nan,

                "Tool":
                    wetted_area,

                "Units": "m²",

                "Interpretation":
                    "Predicted geometry quantity",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Operating empty weight",

                "Reference":
                    np.nan,

                "Tool":
                    owe,

                "Units": "kg",

                "Interpretation":
                    "Predicted integrated vehicle mass",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Maximum takeoff weight",

                "Reference":
                    np.nan,

                "Tool":
                    mtow,

                "Units": "kg",

                "Interpretation":
                    "Predicted integrated vehicle mass",
            },

            {
                "Role": "PERF",
                "Parameter":
                    "Ground/takeoff distance",

                "Reference":
                    np.nan,

                "Tool":
                    ground_roll,

                "Units": "m",

                "Interpretation":
                    "Predicted performance quantity",
            },

            {
                "Role": "PERF",
                "Parameter":
                    "Required shaft power",

                "Reference":
                    np.nan,

                "Tool":
                    required_power / 1000.0,

                "Units": "kW",

                "Interpretation":
                    "Predicted mission power requirement",
            },
        ]

        rows = []

        for item in validation_definitions:

            role = item["Role"]
            ref_value = float(
                item["Reference"]
            )
            tool_value = float(
                item["Tool"]
            )

            # Do NOT claim validation error for
            # quantities deliberately imposed.
            error = (
                np.nan
                if role == "REF"
                else _percent_error(
                    tool_value,
                    ref_value,
                )
            )

            rows.append(
                {
                    **item,
                    "% Error": error,
                }
            )

        df_validation = pd.DataFrame(
            rows
        )

        # ---------------------------------------------------------------------
        # Constraints
        # ---------------------------------------------------------------------

        df_constraints = pd.DataFrame(
            [
                _constraint_row(
                    "Buoyancy",
                    buoyancy_g,
                    "N",
                ),

                _constraint_row(
                    "Power",
                    power_g,
                    "W",
                ),

                _constraint_row(
                    "Energy",
                    energy_g,
                    "-",
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Mass breakdown
        # ---------------------------------------------------------------------

        mass_names = [
            ("Envelope", "envelope_mass"),
            ("Ballonet", "ballonet_mass"),
            ("Curtain", "curtain_mass"),
            ("Framework", "framework_mass"),
            ("Gondola", "gondola_mass"),
            ("Fin", "fin_mass"),
            (
                "Tail fixed",
                "tail_fixed_mass",
            ),
            (
                "Tail control surface",
                "tail_control_surface_mass",
            ),
            (
                "Tail actuator",
                "tail_actuator_mass",
            ),
            (
                "Propulsion",
                "propulsion_mass",
            ),
            (
                "Power system",
                "power_system_mass",
            ),
            (
                "Fuel tank/system",
                "fuel_tank_mass",
            ),
            (
                "Pressure system",
                "pressure_system_mass",
            ),
            (
                "Vehicle management",
                "vms_mass",
            ),
            (
                "Landing system",
                "landing_system_mass",
            ),
            ("Crew", "crew_mass"),
            (
                "Miscellaneous",
                "miscellaneous_mass",
            ),
            (
                "Weight margin",
                "weight_margin_mass",
            ),
            (
                "Operating empty weight",
                "owe",
            ),
            (
                "Maximum takeoff weight",
                "mtow",
            ),
        ]

        mass_rows = []

        for label, variable in mass_names:

            value = _scalar(
                prob,
                variable,
                "kg",
            )

            if np.isfinite(value):

                mass_rows.append(
                    {
                        "Component":
                            label,

                        "Mass [kg]":
                            value,
                    }
                )

        df_mass = pd.DataFrame(
            mass_rows
        )

        # ---------------------------------------------------------------------
        # Download table
        # ---------------------------------------------------------------------

        df_csv = pd.concat(
            [
                df_validation.assign(
                    Category="Validation"
                ),

                df_constraints.assign(
                    Category="Constraint"
                ),

                df_mass.assign(
                    Category="Mass"
                ),
            ],
            ignore_index=True,
            sort=False,
        )

        return {
            "case":
                "A-170 (Non-rigid)",

            "description":
                CASE_LIBRARY[
                    "A-170 (Non-rigid)"
                ]["description"],

            "scalars":
                scalars,

            "df_validation":
                df_validation,

            "df_constraints":
                df_constraints,

            "df_mass":
                df_mass,

            "df_csv":
                df_csv,

            "reference":
                dict(ref),
        }

    finally:

        try:
            prob.cleanup()
        except Exception:
            pass


# =============================================================================
# Zeppelin NT
# =============================================================================

def _run_zeppelin() -> Dict[str, Any]:

    mod = _load_zeppelin_driver()

    prob = mod.build_problem(
        power_source="conventional_reciprocating",
    )

    try:

        mtow = _scalar(
            prob,
            "mtow",
            "kg",
        )

        owe = _scalar(
            prob,
            "owe",
            "kg",
        )

        gross_volume = _scalar(
            prob,
            "gross_volume",
            "m**3",
        )

        wetted_area = _scalar(
            prob,
            "wetted_surface_area",
            "m**2",
        )

        ground_roll = _scalar(
            prob,
            "ground_roll_distance",
            "m",
        )

        required_power = _max_scalar(
            prob,
            "required_shaft_power",
            "W",
        )

        installed_power = _scalar(
            prob,
            "installed_shaft_power",
            "W",
        )

        installed_consumable = _scalar(
            prob,
            "installed_consumable_mass",
            "kg",
        )

        buoyancy_g = _max_scalar(
            prob,
            "buoyancy_constraint",
            "N",
        )

        power_g = _max_scalar(
            prob,
            "power_constraint",
            "W",
        )

        energy_g = _max_scalar(
            prob,
            "energy_constraint",
        )

        scalars = {
            "case":
                "Zeppelin NT 07-101 (Semi-rigid)",

            "airship_type":
                "semi-rigid",

            "mtow_kg":
                mtow,

            "owe_kg":
                owe,

            "gross_volume_m3":
                gross_volume,

            "wetted_area_m2":
                wetted_area,

            "ground_roll_m":
                ground_roll,

            "required_power_kW":
                required_power / 1000.0,

            "installed_power_kW":
                installed_power / 1000.0,

            "consumable_capacity_kg":
                installed_consumable,

            "BR_takeoff":
                _scalar(
                    prob,
                    "BR_takeoff",
                ),

            "buoyancy_constraint":
                buoyancy_g,

            "power_constraint":
                power_g,

            "energy_constraint":
                energy_g,

            "feasible":
                bool(
                    np.isfinite(buoyancy_g)
                    and np.isfinite(power_g)
                    and np.isfinite(energy_g)
                    and buoyancy_g <= 0.0
                    and power_g <= 0.0
                    and energy_g <= 0.0
                ),
        }

        # ---------------------------------------------------------------------
        # Zeppelin published/reference validation data
        # ---------------------------------------------------------------------

        validation_definitions = [
            {
                "Role": "REF",
                "Parameter": "Length",
                "Reference":
                    mod.REFERENCE_LENGTH_M,

                "Tool":
                    _scalar(
                        prob,
                        "length",
                        "m",
                    ),

                "Units": "m",
                "Interpretation":
                    "Prescribed Zeppelin geometry",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Fineness ratio",

                "Reference":
                    mod.REFERENCE_FINENESS_RATIO,

                "Tool":
                    _scalar(
                        prob,
                        "fineness_ratio",
                    ),

                "Units": "-",
                "Interpretation":
                    "Prescribed Zeppelin geometry",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Payload",

                "Reference":
                    mod.REFERENCE_PAYLOAD_KG,

                "Tool":
                    _scalar(
                        prob,
                        "payload",
                        "kg",
                    ),

                "Units": "kg",
                "Interpretation":
                    "Prescribed validation payload",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Installed fuel capacity",

                "Reference":
                    mod.REFERENCE_FUEL_KG,

                "Tool":
                    installed_consumable,

                "Units": "kg",
                "Interpretation":
                    "Prescribed published fuel capacity",
            },

            {
                "Role": "REF",
                "Parameter":
                    "Installed shaft power",

                "Reference":
                    mod.REFERENCE_POWER_W
                    / 1000.0,

                "Tool":
                    installed_power
                    / 1000.0,

                "Units": "kW",
                "Interpretation":
                    "Prescribed installed capacity",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Gross volume",

                "Reference":
                    mod.REFERENCE_VOLUME_M3,

                "Tool":
                    gross_volume,

                "Units": "m³",
                "Interpretation":
                    "Predicted from reference hull geometry",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Operating empty weight",

                "Reference":
                    mod.REFERENCE_BASE_MASS_KG,

                "Tool":
                    owe,

                "Units": "kg",
                "Interpretation":
                    "Predicted integrated vehicle mass",
            },

            {
                "Role": "PRED",
                "Parameter":
                    "Maximum takeoff weight",

                "Reference":
                    mod.REFERENCE_MTOW_KG,

                "Tool":
                    mtow,

                "Units": "kg",
                "Interpretation":
                    "Predicted integrated vehicle mass",
            },

            {
                "Role": "PERF",
                "Parameter":
                    "Required shaft power",

                "Reference":
                    np.nan,

                "Tool":
                    required_power / 1000.0,

                "Units": "kW",
                "Interpretation":
                    "Predicted performance quantity",
            },

            {
                "Role": "PERF",
                "Parameter":
                    "Ground/takeoff distance",

                "Reference":
                    np.nan,

                "Tool":
                    ground_roll,

                "Units": "m",
                "Interpretation":
                    (
                        "Predicted quantity; no directly "
                        "comparable published Zeppelin datum"
                    ),
            },
        ]

        rows = []

        for item in validation_definitions:

            role = item["Role"]
            ref_value = float(
                item["Reference"]
            )
            tool_value = float(
                item["Tool"]
            )

            error = (
                np.nan
                if role == "REF"
                else _percent_error(
                    tool_value,
                    ref_value,
                )
            )

            rows.append(
                {
                    **item,
                    "% Error": error,
                }
            )

        df_validation = pd.DataFrame(
            rows
        )

        # ---------------------------------------------------------------------
        # Constraints
        # ---------------------------------------------------------------------

        df_constraints = pd.DataFrame(
            [
                _constraint_row(
                    "Buoyancy",
                    buoyancy_g,
                    "N",
                ),

                _constraint_row(
                    "Power",
                    power_g,
                    "W",
                ),

                _constraint_row(
                    "Energy",
                    energy_g,
                    "-",
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Semi-rigid mass breakdown
        # ---------------------------------------------------------------------

        mass_names = [
            (
                "Framework",
                "framework_mass",
            ),
            (
                "Ballonet",
                "ballonet_mass",
            ),
            (
                "Curtain",
                "curtain_mass",
            ),
            (
                "Envelope",
                "envelope_mass",
            ),
            (
                "Gondola",
                "gondola_mass",
            ),
            (
                "Fin",
                "fin_mass",
            ),
            (
                "Propulsion",
                "propulsion_mass",
            ),
            (
                "Power system",
                "power_system_mass",
            ),
            (
                "Landing system",
                "landing_system_mass",
            ),
            (
                "Crew",
                "crew_mass",
            ),
            (
                "Miscellaneous",
                "miscellaneous_mass",
            ),
            (
                "Operating empty weight",
                "owe",
            ),
            (
                "Maximum takeoff weight",
                "mtow",
            ),
        ]

        mass_rows = []

        for label, variable in mass_names:

            value = _scalar(
                prob,
                variable,
                "kg",
            )

            if np.isfinite(value):

                mass_rows.append(
                    {
                        "Component":
                            label,

                        "Mass [kg]":
                            value,
                    }
                )

        df_mass = pd.DataFrame(
            mass_rows
        )

        df_csv = pd.concat(
            [
                df_validation.assign(
                    Category="Validation"
                ),

                df_constraints.assign(
                    Category="Constraint"
                ),

                df_mass.assign(
                    Category="Mass"
                ),
            ],
            ignore_index=True,
            sort=False,
        )

        return {
            "case":
                "Zeppelin NT 07-101 (Semi-rigid)",

            "description":
                CASE_LIBRARY[
                    "Zeppelin NT 07-101 (Semi-rigid)"
                ]["description"],

            "scalars":
                scalars,

            "df_validation":
                df_validation,

            "df_constraints":
                df_constraints,

            "df_mass":
                df_mass,

            "df_csv":
                df_csv,

            "reference": {
                "length_m":
                    mod.REFERENCE_LENGTH_M,

                "diameter_m":
                    mod.REFERENCE_DIAMETER_M,

                "fineness_ratio":
                    mod.REFERENCE_FINENESS_RATIO,

                "volume_m3":
                    mod.REFERENCE_VOLUME_M3,

                "mtow_kg":
                    mod.REFERENCE_MTOW_KG,

                "payload_kg":
                    mod.REFERENCE_PAYLOAD_KG,

                "fuel_kg":
                    mod.REFERENCE_FUEL_KG,

                "power_W":
                    mod.REFERENCE_POWER_W,

                "range_m":
                    mod.REFERENCE_RANGE_M,

                "cruise_speed_mps":
                    mod.REFERENCE_CRUISE_SPEED_MPS,

                "cruise_altitude_m":
                    mod.REFERENCE_CRUISE_ALTITUDE_M,
            },
        }

    finally:

        try:
            prob.cleanup()
        except Exception:
            pass


# =============================================================================
# Public API
# =============================================================================

def run_validation(
    cfg_in: Dict[str, Any],
) -> Dict[str, Any]:

    case_name = str(
        cfg_in.get(
            "validation_case",
            "A-170 (Non-rigid)",
        )
    )

    if case_name == "A-170 (Non-rigid)":
        return _run_a170()

    if (
        case_name
        == "Zeppelin NT 07-101 (Semi-rigid)"
    ):
        return _run_zeppelin()

    raise ValueError(
        f"Unknown validation case: {case_name}. "
        f"Available cases: {list(CASE_LIBRARY)}"
    )