# -*- coding: utf-8 -*-
"""
Zeppelin NT 07-101 validation and optional pymoo optimization for ADaPT.

===============================================================================
HOW TO READ THIS DRIVER: FRAMEWORK INPUTS, COMPONENT INPUTS, AND OUTPUTS
===============================================================================

A variable can have different roles depending on the boundary being discussed.
This is especially important in an MDAO framework.

LEVEL 1 — MISSION / DESIGN REQUIREMENTS
---------------------------------------
These describe what the vehicle must accomplish and are imposed by the user:

    payload
    range
    cruise_altp
    cruise_speed
    architecture / power_source

In a true conceptual-sizing study these are normally held fixed as requirements.

LEVEL 2 — SYSTEM-LEVEL DESIGN VARIABLES
---------------------------------------
These describe the vehicle design that may be selected by a designer or optimizer:

    length
    fineness_ratio
    tail_volume_coeff_horizontal
    tail_volume_coeff_vertical
    BR_takeoff
    lift_coeff
    drag_due_to_lift_factor
    propeller_efficiency
    installed_shaft_power

Important:
    "Input to an OpenMDAO component" does NOT mean "known mission requirement."

For example, ``length`` is an input to AirshipGeometry because that component
needs a candidate length in order to calculate diameter, volume, wetted area,
tail area, etc. In a sizing/optimization problem, however, length can be a
SYSTEM-LEVEL DESIGN VARIABLE. The optimizer changes length until the complete
airship satisfies payload, range, power, buoyancy, energy, and other constraints.
The final optimized length is therefore a SIZING RESULT even though it is a
component input mathematically.

LEVEL 3 — COUPLING VARIABLES / COMPONENT OUTPUTS
------------------------------------------------
These are calculated by one component and become inputs to another component:

    length + fineness_ratio
        -> Geometry
        -> gross_volume, wetted_surface_area, planform_area, fin_area
        -> Weight / Performance

    geometry + payload + installed systems
        -> Weight
        -> OEW, MTOW, helium mass
        -> Performance

    MTOW + geometry + mission conditions
        -> Performance
        -> drag, thrust, required shaft power, mission duration
        -> Propulsion / Power

    power demand
        -> Propulsion / Power / energy-storage components
        -> propulsion mass, fuel/hydrogen/battery requirement
        -> Weight

These variables close the multidisciplinary sizing loop.

LEVEL 4 — FINAL VEHICLE RESULTS
-------------------------------
These are the quantities normally reported to a designer after sizing:

    optimized/final length and diameter
    gross volume
    wetted area
    OEW
    MTOW
    propulsion-system mass
    fuel / hydrogen / battery requirement
    installed power
    mission duration
    takeoff / landing performance
    feasibility margins

Thus, a quantity such as ``length`` may simultaneously be:
    - an input to the Geometry component,
    - a design variable of the full MDAO problem, and
    - a final reported sizing result.

===============================================================================
WHAT THIS PARTICULAR SCRIPT DOES
===============================================================================

This file is primarily a VALIDATION DRIVER, not a free-sizing driver.

For validation against the existing Zeppelin NT 07-101, published vehicle
quantities such as length, fineness ratio, payload, installed power, range, and
cruise condition are deliberately imposed. The purpose is to ask:

    "If ADaPT is given the known Zeppelin configuration and mission, does it
     reproduce published quantities such as volume, OEW and MTOW?"

Therefore ``length`` is FIXED in the baseline validation run. This does not mean
that ADaPT generally requires the user to know the final airship length before a
sizing study.

The optional pymoo section in this file is also NOT a complete clean-sheet
airship-sizing optimization. It varies only six selected parameters:

    BR_takeoff,
    tail_volume_coeff_horizontal,
    tail_volume_coeff_vertical,
    lift_coeff,
    drag_due_to_lift_factor,
    propeller_efficiency.

A full sizing study would normally expose geometry variables such as length
(and potentially fineness ratio, volume or another size parameter) to the
optimizer while holding mission requirements such as payload and range fixed.

===============================================================================
OPENMDAO OWNERSHIP
===============================================================================

AirshipAnalysisGroup already contains the central AirshipIndepVariables
subsystem. Do not add a second promoted IndepVarComp. This driver therefore:

    1. Adds AirshipAnalysisGroup directly to the Problem.
    2. Calls Problem.setup().
    3. Sets the built-in independent-variable outputs with Problem.set_val().
    4. Runs the model.

Constraint convention
---------------------
The updated ADaPT components use:

    constraint <= 0  -> feasible

for power, energy, buoyancy, lift, takeoff-field, and landing-field constraints.
"""

from __future__ import annotations

import csv
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import numpy as np
import openmdao.api as om
# omxdsm is used to create a XDSM diagram of the model
# from omxdsm import write_xdsm

try:
    from pymoo.optimize import minimize
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.algorithms.soo.nonconvex.de import DE
    from pymoo.termination import get_termination
    from pymoo.core.sampling import Sampling
except ImportError as exc:
    raise ImportError(
        "pymoo is required for the optimization part of this script. "
        "Install it with: pip install pymoo"
    ) from exc

try:
    from colorama import Fore
except Exception:
    class _F:
        LIGHTGREEN_EX = ""
        RED = ""
        CYAN = ""
        YELLOW = ""
        RESET = ""

    Fore = _F()


# -------------------------------------------------------------------------
# Repository path bootstrap
# -------------------------------------------------------------------------

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
CORE_DIR = PROJECT_ROOT / "adapt"

# Add repository root so that packages/folders such as
# airships/ can be imported.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Add adapt/ so that the core modules can be imported directly.
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import adapt.AirshipAnalysisGroup as airship_group_module
from adapt.AirshipWeight import AirshipWeight as _BaseAirshipWeight
from adapt.operatingConditions import opCond
from airships.ZeppelinNT import ZeppelinNT


class ZeppelinNTAirshipWeight(_BaseAirshipWeight):
    """
    Zeppelin NT 07-101 validation-specific semi-rigid calibration.

    Published anchors:
        envelope/hull fabric mass ~ 1000 kg
        load-bearing structure    ~ 1100 kg

    The universal AirshipWeight model is not modified.
    """

    def __init__(self, **kwargs):

        # Zeppelin:
        # S_wet = 2668.39 m^2
        #
        # sigma_env = 1000 / 2668.39
        #           = 0.37476 kg/m^2
        zeppelin_envelope_areal_density = ZeppelinNT.model_options["outer_envelope_areal_density"]

        # Zeppelin:
        # V^(2/3) ~= 414.05 m^2
        #
        # k_frame = 1100 / 414.05
        #         ~= 2.657
        zeppelin_framework_k_v23 = ZeppelinNT.model_options["k_framework_v23"]

        calibrated_options = {

            # ----------------------------------------------------------
            # Semi-rigid envelope
            # ----------------------------------------------------------
            "outer_envelope_areal_density":
                zeppelin_envelope_areal_density,

            # Do not invent an additional generic 25%-area inner
            # envelope mass for Zeppelin NT.
            "inner_envelope_areal_density": ZeppelinNT.model_options["inner_envelope_areal_density"],

            # ----------------------------------------------------------
            # Published Zeppelin semi-rigid load-bearing framework
            # ----------------------------------------------------------
            "framework_mass_model": ZeppelinNT.model_options["framework_mass_model"],
            "k_framework_v23":
                zeppelin_framework_k_v23,

            # The generic 22% DSE safeguard would otherwise prevent
            # the published ~1100 kg structural calibration.
            "framework_mass_frac_cap": ZeppelinNT.model_options["framework_mass_frac_cap"],

            # ----------------------------------------------------------
            # Remaining bookkeeping
            # ----------------------------------------------------------
            "miscellaneous_fraction": ZeppelinNT.model_options["weight_miscellaneous_fraction"],
            "crew_mass_each": ZeppelinNT.model_options["crew_mass_each"],
        }

        calibrated_options.update(kwargs)

        super().__init__(**calibrated_options)


# AirshipAnalysisGroup imported AirshipWeight into its module namespace.
# Replace only that module-level constructor for this validation process.
# The original AirshipAnalysisGroup.py and AirshipWeight.py files remain unchanged.
airship_group_module.AirshipWeight = ZeppelinNTAirshipWeight
AirshipAnalysisGroup = airship_group_module.AirshipAnalysisGroup


# -------------------------------------------------------------------------
# Supported architecture aliases
# -------------------------------------------------------------------------

POWER_SOURCE_ALIASES = {
    "conventional_fuel": "conventional_reciprocating",
    "hydrogen": "hydrogen_fuel_cell",
}

SUPPORTED_POWER_SOURCES = {
    "conventional_reciprocating",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "battery_only",
    "solar_battery",
    "solar-RFC",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
    "conventional_battery_hybrid",
}


# -------------------------------------------------------------------------
# Zeppelin NT 07-101 reference airship
# -------------------------------------------------------------------------
#
# All Zeppelin vehicle/reference data now live in airship/ZeppelinNT.py.
# The aliases below preserve the existing validation/reporting code exactly.
CASE_NAME = ZeppelinNT.name
REFERENCE_LENGTH_M = ZeppelinNT.length_m
REFERENCE_DIAMETER_M = ZeppelinNT.diameter_m
REFERENCE_FINENESS_RATIO = ZeppelinNT.fineness_ratio
REFERENCE_VOLUME_M3 = ZeppelinNT.reference_values["volume_m3"]
REFERENCE_MTOW_KG = ZeppelinNT.reference_values["mtow_kg"]
REFERENCE_USEFUL_LOAD_KG = ZeppelinNT.reference_values["useful_load_kg"]
REFERENCE_BASE_MASS_KG = ZeppelinNT.reference_values["base_mass_kg"]
SECONDARY_PUBLISHED_EMPTY_MASS_KG = ZeppelinNT.reference_values["secondary_published_empty_mass_kg"]
REFERENCE_FUEL_KG = ZeppelinNT.reference_values["fuel_kg"]
REFERENCE_PAYLOAD_KG = ZeppelinNT.payload_kg
REFERENCE_POWER_W = ZeppelinNT.installed_shaft_power_W
REFERENCE_RANGE_M = ZeppelinNT.range_m
REFERENCE_CRUISE_SPEED_MPS = ZeppelinNT.cruise_speed_ms
REFERENCE_CRUISE_ALTITUDE_M = ZeppelinNT.cruise_altitude_m
REFERENCE_BR_TAKEOFF = ZeppelinNT.BR_takeoff

# Broad bounds used only by the optional optimization.
MTOW_LOWER_KG = 6500.0
MTOW_UPPER_KG = 9500.0
GROUND_DISTANCE_LIMIT_M = 250.0

# The supplied Zeppelin sources do not provide component-level masses or a
# conventional ground-roll datum. Those reference entries are deliberately
# reported as N/A rather than invented.

RUN_OPTIMIZATION = False
GENERATE_XDSM = False


# -------------------------------------------------------------------------
# Variable-role map
# -------------------------------------------------------------------------
#
# This registry is documentation for users.  It does not change the numerical
# model.  Its purpose is to make the distinction between:
#   (a) mission requirements,
#   (b) validation-fixed reference quantities,
#   (c) system-level design variables,
#   (d) component-to-component coupling variables, and
#   (e) final reported results
# explicit.
#
# "component_direction" describes the variable at the component boundary.
# "system_role" describes how a designer should interpret it at MDAO level.
#
VARIABLE_ROLE_MAP = OrderedDict(
    [
        (
            "payload",
            {
                "component_direction": "Independent variable -> Weight/Performance",
                "system_role": "MISSION REQUIREMENT",
                "validation_role": "Fixed to published Zeppelin payload",
                "explanation": (
                    "Payload is what the airship must carry. In sizing studies it "
                    "is normally prescribed, not solved."
                ),
            },
        ),
        (
            "range",
            {
                "component_direction": "Independent variable -> Performance",
                "system_role": "MISSION REQUIREMENT",
                "validation_role": "Fixed to published/reference mission range",
                "explanation": (
                    "Range defines the transport mission. Performance converts it "
                    "with flight speed into mission duration and energy demand."
                ),
            },
        ),
        (
            "cruise_altp",
            {
                "component_direction": "Independent variable -> Atmosphere/Performance",
                "system_role": "MISSION / OPERATING REQUIREMENT",
                "validation_role": "Fixed validation condition",
                "explanation": "Defines the atmospheric operating point.",
            },
        ),
        (
            "cruise_speed",
            {
                "component_direction": "Independent variable -> Performance",
                "system_role": "MISSION / OPERATING REQUIREMENT",
                "validation_role": "Fixed validation condition",
                "explanation": (
                    "Prescribed cruise speed for this validation case. Other studies "
                    "may optimize speed or use the minimum-drag cruise strategy."
                ),
            },
        ),
        (
            "length",
            {
                "component_direction": "Input to Geometry",
                "system_role": "SYSTEM DESIGN VARIABLE / REPORTED SIZING RESULT",
                "validation_role": "FIXED because the real Zeppelin length is known",
                "explanation": (
                    "Geometry needs a candidate length to compute diameter, volume "
                    "and areas. In clean-sheet sizing an optimizer may vary length; "
                    "the converged/optimized value is then reported as a sizing result."
                ),
            },
        ),
        (
            "fineness_ratio",
            {
                "component_direction": "Input to Geometry",
                "system_role": "SYSTEM DESIGN VARIABLE",
                "validation_role": "Fixed from published L/D",
                "explanation": (
                    "Together with length it defines the candidate hull dimensions. "
                    "It need not be a mission requirement."
                ),
            },
        ),
        (
            "gross_volume",
            {
                "component_direction": "Geometry output -> Weight/Performance",
                "system_role": "COUPLING VARIABLE / FINAL VEHICLE RESULT",
                "validation_role": "Predicted and compared with published volume",
                "explanation": (
                    "This is calculated from the candidate geometry and then drives "
                    "buoyancy, helium, structure and vehicle mass."
                ),
            },
        ),
        (
            "wetted_surface_area",
            {
                "component_direction": "Geometry output -> downstream models",
                "system_role": "COUPLING VARIABLE / FINAL VEHICLE RESULT",
                "validation_role": "Predicted; no published datum is invented",
                "explanation": "Calculated geometric area used by downstream disciplines.",
            },
        ),
        (
            "BR_takeoff",
            {
                "component_direction": "Independent/design variable -> Performance",
                "system_role": "CONFIGURATION / DESIGN VARIABLE",
                "validation_role": "Fixed to reference value in baseline",
                "explanation": (
                    "Buoyancy ratio controls the split between buoyant and aerodynamic "
                    "lift. It can be varied in design studies."
                ),
            },
        ),
        (
            "installed_shaft_power",
            {
                "component_direction": "Independent/design variable -> Performance/Propulsion",
                "system_role": "INSTALLED CAPACITY / DESIGN VARIABLE",
                "validation_role": "Fixed to published installed power",
                "explanation": (
                    "For validation, the known installed rating is imposed. In sizing, "
                    "it may be selected by the propulsion sizing logic or optimizer."
                ),
            },
        ),
        (
            "mtow",
            {
                "component_direction": "Weight output -> Performance",
                "system_role": "COUPLING VARIABLE / PRIMARY SIZING OUTPUT",
                "validation_role": "Predicted and compared with reference MTOW",
                "explanation": (
                    "MTOW is not prescribed in the baseline model closure. It is built "
                    "from OEW, payload, consumables, ballast and landing-system closure."
                ),
            },
        ),
        (
            "owe",
            {
                "component_direction": "Weight output",
                "system_role": "PRIMARY SIZING OUTPUT",
                "validation_role": "Predicted and compared with reference OEW",
                "explanation": "Calculated vehicle empty operating mass.",
            },
        ),
        (
            "required_shaft_power",
            {
                "component_direction": "Performance output -> Propulsion",
                "system_role": "COUPLING VARIABLE",
                "validation_role": "Predicted",
                "explanation": (
                    "Calculated from drag, speed and propeller efficiency; used to "
                    "check whether installed shaft power is sufficient."
                ),
            },
        ),
        (
            "installed_consumable_mass",
            {
                "component_direction": "Fuel/tank sizing output or prescribed capacity -> Weight/Performance",
                "system_role": "RESOURCE CAPACITY",
                "validation_role": "Prescribed to published Zeppelin fuel capacity",
                "explanation": (
                    "This validation intentionally imposes known fuel capacity. In a "
                    "clean-sheet sizing run, required consumable mass comes from the "
                    "mission/power chain and is closed with the installed capacity."
                ),
            },
        ),
        (
            "ground_roll_distance",
            {
                "component_direction": "Performance output",
                "system_role": "PERFORMANCE RESULT / FEASIBILITY METRIC",
                "validation_role": "Predicted; no comparable published datum supplied",
                "explanation": (
                    "A performance result, not a sizing input. Current component naming "
                    "stores total takeoff distance under this legacy output name."
                ),
            },
        ),
    ]
)


def print_variable_role_guide() -> None:
    """Print a concise user-facing explanation of model inputs and outputs."""
    print("\n" + "=" * 88)
    print("ADaPT VARIABLE ROLES — HOW TO INTERPRET INPUTS AND OUTPUTS")
    print("=" * 88)
    print(
        "OpenMDAO 'input/output' describes data flow between components; it does NOT "
        "by itself say whether a quantity is a mission requirement, design variable, "
        "or final sizing result."
    )
    print("\nThree analysis modes:")
    print("  1. VALIDATION: known aircraft geometry/installed data are fixed; ADaPT predicts")
    print("     quantities such as volume, OEW, MTOW and performance for comparison.")
    print("  2. FORWARD MISSION ANALYSIS: a fixed vehicle is flown through specified mission")
    print("     conditions to predict power, energy, fuel use and feasibility.")
    print("  3. CLEAN-SHEET SIZING/OPTIMIZATION: payload/range are fixed requirements while")
    print("     geometry/technology design variables are varied until constraints close.")
    print("\nKey example:")
    print("  length -> INPUT to Geometry component")
    print("         -> DESIGN VARIABLE in a clean-sheet MDAO sizing problem")
    print("         -> FIXED REFERENCE VALUE in this Zeppelin validation")
    print("         -> FINAL REPORTED SIZE after optimization")
    print("\nVariable map:")
    for name, meta in VARIABLE_ROLE_MAP.items():
        print(f"\n  {name}")
        print(f"    Component flow : {meta['component_direction']}")
        print(f"    System role    : {meta['system_role']}")
        print(f"    This validation: {meta['validation_role']}")
        print(f"    Why            : {meta['explanation']}")
    print("=" * 88)


def export_variable_role_map(
    filename: str = "zeppelin_validation_variable_roles.csv",
) -> Path:
    """Export the human-readable variable classification used in this validation."""
    path = Path(filename).resolve()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "Variable",
                "Component Direction",
                "System-Level Role",
                "Role in This Validation",
                "Explanation",
            ]
        )
        for name, meta in VARIABLE_ROLE_MAP.items():
            writer.writerow(
                [
                    name,
                    meta["component_direction"],
                    meta["system_role"],
                    meta["validation_role"],
                    meta["explanation"],
                ]
            )
    return path


# -------------------------------------------------------------------------
# Safe value helpers
# -------------------------------------------------------------------------

def _array(prob: om.Problem, name: str, units: Optional[str] = None) -> np.ndarray:
    """Return an OpenMDAO value as a one-dimensional float array."""
    value = prob.get_val(name, units=units)
    return np.asarray(value, dtype=float).reshape(-1)


def _get(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    """Return the first scalar value, or a default if unavailable."""
    try:
        return float(_array(prob, name, units=units)[0])
    except Exception:
        return float(default)


def _max_value(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    """Return the maximum array value, useful for vector constraints."""
    try:
        values = _array(prob, name, units=units)
        return float(np.max(values))
    except Exception:
        return float(default)


def _p(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
) -> float:
    """Compact printing helper."""
    return _get(prob, name, units=units)


def _get_crew_mass(prob: om.Problem) -> float:
    """Prefer the component output; fall back to the conceptual correlation."""
    crew_mass = _get(prob, "crew_mass", units="kg")
    if np.isfinite(crew_mass):
        return crew_mass

    n_crew = _get(prob, "n_crew", default=1.0)
    return n_crew * 113.0


def _set_if_present(
    prob: om.Problem,
    name: str,
    value,
    units: Optional[str] = None,
) -> bool:
    """
    Set a variable when it exists.

    This permits the validation driver to remain usable across architecture
    branches where some variables are inactive.
    """
    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
        return True
    except Exception:
        return False


# -------------------------------------------------------------------------
# OpenMDAO problem construction
# -------------------------------------------------------------------------

def build_problem(
    power_source: str = "conventional_reciprocating",
    *,
    num_steps: int = 1,
    run_model: bool = True,
    setup_check: bool = False,
) -> om.Problem:
    """
    Build the updated ADaPT OpenMDAO model.

    The AirshipAnalysisGroup already owns the central IndepVarComp, so this
    function deliberately does not create another one.
    """
    print(
        Fore.LIGHTGREEN_EX
        + f"=== Building OpenMDAO model: {power_source} ==="
        + Fore.RESET
    )

    power_source = POWER_SOURCE_ALIASES.get(power_source, power_source)

    if power_source not in SUPPORTED_POWER_SOURCES:
        raise ValueError(
            f"Unsupported power_source={power_source!r}. "
            f"Choose one of {sorted(SUPPORTED_POWER_SOURCES)}."
        )

    if num_steps < 1:
        raise ValueError("num_steps must be at least 1.")

    phd = opCond(
        name="Cruise",
        T_env=284.25,
        altitude=REFERENCE_CRUISE_ALTITUDE_M,
        speed=REFERENCE_CRUISE_SPEED_MPS / 340.0,
        time="day",
        RH=70.0,
    )

    prob = om.Problem()

    # AirshipAnalysisGroup is the top-level model. Its internal subsystem
    # "indep" supplies the independent variables.
    # Zeppelin NT is semi-rigid. AirshipAnalysisGroup must propagate this
    # option into AirshipWeight; otherwise the non-rigid gondola correlation
    # is used and the mass validation is not meaningful.
    try:
        prob.model = AirshipAnalysisGroup(
            phd=phd,
            power_source=power_source,
            landing_system=ZeppelinNT.landing_system,
            airship_type=ZeppelinNT.airship_type,
            num_steps=num_steps,

            use_prescribed_consumable_capacity=ZeppelinNT.model_options["use_prescribed_consumable_capacity"],
            ballonet_sizing_method=ZeppelinNT.model_options["ballonet_sizing_method"],
            tail_coefficient_method=ZeppelinNT.model_options["tail_coefficient_method"],

            # Zeppelin propulsion installation
            propulsion_installation_mass_method=ZeppelinNT.model_options["propulsion_installation_mass_method"],

            # Zeppelin weight configuration
            weight_gondola_method=ZeppelinNT.model_options["weight_gondola_method"],
            weight_gondola_category=ZeppelinNT.model_options["weight_gondola_category"],
            weight_miscellaneous_fraction=ZeppelinNT.model_options["weight_miscellaneous_fraction"],
        )
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "AirshipAnalysisGroup does not yet support airship_type. "
            "Declare airship_type in the group and pass it to AirshipWeight."
        ) from exc

    prob.setup(check=setup_check)

    # ------------------------------------------------------------------
    # Zeppelin NT 07-101 VALIDATION CASE DEFINITION
    # ------------------------------------------------------------------
    #
    # IMPORTANT:
    # These set_val() calls do not mean every quantity below is a fundamental
    # framework input. They mean that, for THIS validation experiment, known
    # Zeppelin data are imposed so that downstream predictions can be compared
    # against the published aircraft.
    #
    # In a clean-sheet sizing run:
    #   * payload/range/operating conditions remain mission requirements;
    #   * length, fineness ratio, BR, installed power, etc. may be design variables;
    #   * gross volume, OEW, MTOW, drag, power and resource masses are calculated
    #     coupling variables/results.
    #
    # --- A. Known vehicle geometry imposed ONLY for validation ---
    prob.set_val("length", REFERENCE_LENGTH_M, units="m")
    prob.set_val("fineness_ratio", REFERENCE_FINENESS_RATIO)
    # prob.set_val("tail_volume_coeff_horizontal", 0.066)
    # prob.set_val("tail_volume_coeff_vertical", 0.059)

    # --- B. Mission requirements / operating conditions ---
    # These are the quantities the vehicle is required to satisfy.
    prob.set_val("payload", REFERENCE_PAYLOAD_KG, units="kg")
    prob.set_val("range", REFERENCE_RANGE_M, units="m")

    prob.set_val(
        "cruise_altp",
        np.full(num_steps, REFERENCE_CRUISE_ALTITUDE_M),
        units="m",
    )
    prob.set_val(
        "cruise_disa",
        np.zeros(num_steps),
        units="K",
    )
    prob.set_val(
        "cruise_speed",
        np.full(num_steps, REFERENCE_CRUISE_SPEED_MPS),
        units="m/s",
    )

    prob.set_val(
        "hull_volume_shape_factor",
        ZeppelinNT.hull_volume_shape_factor,
    )

    prob.set_val(
        "ballonet_fill_fraction_takeoff",
        ZeppelinNT.ballonet_fill_fraction_takeoff,
    )
    prob.set_val(
        "ballonet_fraction_prescribed",
        ZeppelinNT.ballonet_fraction_prescribed,
    )


    prob.set_val(
        "weight.gondola_length",
        ZeppelinNT.extra_inputs["weight.gondola_length"]["value"],
        units=ZeppelinNT.extra_inputs["weight.gondola_length"]["units"],
    )

    prob.set_val(
        "weight.gondola_width",
        ZeppelinNT.extra_inputs["weight.gondola_width"]["value"],
        units=ZeppelinNT.extra_inputs["weight.gondola_width"]["units"],
    )

    prob.set_val(
        "weight.gondola_height",
        ZeppelinNT.extra_inputs["weight.gondola_height"]["value"],
        units=ZeppelinNT.extra_inputs["weight.gondola_height"]["units"],
    )

    prob.set_val(
        "maximum_speed",
        ZeppelinNT.maximum_speed_ms,
        units="m/s",
    )

    # --- C. Known installed capacities imposed for reference-aircraft validation ---
    # In clean-sheet sizing these capacities would normally be closed against the
    # mission-derived required resource quantities.
    prob.set_val(
        "installed_consumable_capacity",
        REFERENCE_FUEL_KG,
        units="kg",
    )

    prob.set_val(
        "ballast_mass",
        ZeppelinNT.ballast_mass_kg,
        units="kg",
    )

    # --- D. Configuration choices / known installed hardware ---
    prob.set_val("n_crew", ZeppelinNT.n_crew)
    prob.set_val("n_engine", ZeppelinNT.n_engine)

    # Installed power is known for Zeppelin validation. In a clean-sheet design
    # it is an installed-capacity/design quantity checked against required power.
    # Updated name: engine_power -> installed_shaft_power.
    prob.set_val(
        "installed_shaft_power",
        REFERENCE_POWER_W,
        units="W",
    )

    prob.set_val("propeller_efficiency", ZeppelinNT.propeller_efficiency)
    prob.set_val("BR_takeoff", REFERENCE_BR_TAKEOFF)
    prob.set_val("BR_landing", ZeppelinNT.BR_landing)
    prob.set_val("lift_coeff", ZeppelinNT.lift_coeff)
    prob.set_val("drag_due_to_lift_factor", ZeppelinNT.drag_due_to_lift_factor)

    # Legacy fallback is disabled in the final Tank component. Setting this
    # remains harmless and helps compatibility with older Tank files.
    if power_source in {
        "hydrogen_reciprocating",
        "hydrogen_fuel_cell",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
    }:
        _set_if_present(
            prob,
            "fuel_onboard_mass",
            np.full(num_steps, 150.0),
            units="kg",
        )

    if power_source in {
        "battery_only",
        "solar_battery",
        "solar-RFC",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
        "conventional_battery_hybrid",
    }:
        _set_if_present(
            prob,
            "battery_specific_energy",
            250.0,
            units="W*h/kg",
        )

    if power_source in {"solar_battery", "solar-RFC", "solar_hydrogen_hybrid"}:
        _set_if_present(prob, "solar_area", 300.0, units="m**2")
        _set_if_present(
            prob,
            "solar_irradiance",
            np.full(num_steps, 600.0),
            units="W/m**2",
        )
        _set_if_present(prob, "solar_energy", 0.0, units="MJ")

    if run_model:
        prob.run_model()

    return prob


# -------------------------------------------------------------------------
# Design-variable mapping
# -------------------------------------------------------------------------

# x = [BR_takeoff, tvc_h, tvc_v, lift_coeff, k_lift, prop_eff]

def set_x(prob: om.Problem, x: np.ndarray) -> None:
    """Apply one pymoo design vector to the existing OpenMDAO problem."""
    x = np.asarray(x, dtype=float).reshape(-1)

    if x.size != 6:
        raise ValueError(f"Expected six design variables, received {x.size}.")

    prob.set_val("BR_takeoff", x[0])
    prob.set_val("tail_volume_coeff_horizontal", x[1])
    prob.set_val("tail_volume_coeff_vertical", x[2])
    prob.set_val("lift_coeff", x[3])
    prob.set_val("drag_due_to_lift_factor", x[4])
    prob.set_val("propeller_efficiency", x[5])


def get_bounds() -> tuple[np.ndarray, np.ndarray]:
    """Return lower and upper bounds for the six design variables."""
    lower = np.array(
        [0.50, 0.05, 0.04, 0.12, 0.45, 0.70],
        dtype=float,
    )
    upper = np.array(
        [0.99, 0.09, 0.08, 0.22, 1.00, 0.90],
        dtype=float,
    )
    return lower, upper


# -------------------------------------------------------------------------
# Initial sampling
# -------------------------------------------------------------------------

class OMInitialSampling(Sampling):
    """Seed the initial DE population around the reference design."""

    def __init__(self, x0, jitter: float = 0.08):
        super().__init__()
        self.x0 = np.asarray(x0, dtype=float).copy()
        self.jitter = float(jitter)

    def _do(self, problem, n_samples, **kwargs):
        lower = np.asarray(problem.xl, dtype=float)
        upper = np.asarray(problem.xu, dtype=float)

        population = np.random.uniform(
            lower,
            upper,
            size=(n_samples, lower.size),
        )

        population[0, :] = np.clip(
            self.x0,
            lower,
            upper,
        )

        n_local = min(5, max(n_samples - 1, 0))
        if n_local > 0:
            indices = np.random.choice(
                np.arange(1, n_samples),
                size=n_local,
                replace=False,
            )
            span = upper - lower
            perturbation = (
                self.jitter
                * span
                * (
                    np.random.rand(n_local, lower.size)
                    - 0.5
                )
            )
            population[indices] = np.clip(
                self.x0 + perturbation,
                lower,
                upper,
            )

        return population


# -------------------------------------------------------------------------
# Objective and constraints
# -------------------------------------------------------------------------

def evaluate(prob: om.Problem) -> tuple[float, np.ndarray]:
    """
    Run one model evaluation.

    pymoo uses g <= 0 as the feasibility convention, which now matches the
    updated ADaPT constraint outputs directly.
    """
    try:
        prob.run_model()

        ground_roll = _get(
            prob,
            "ground_roll_distance",
            units="m",
            default=1.0e6,
        )
        buoyancy_ratio = _get(
            prob,
            "BR_takeoff",
            default=2.0,
        )

        if not np.isfinite(ground_roll):
            ground_roll = 1.0e6
        if not np.isfinite(buoyancy_ratio):
            buoyancy_ratio = 2.0

        # Hinge plus quadratic penalty above the optional ground-distance limit.
        violation = max(0.0, ground_roll - GROUND_DISTANCE_LIMIT_M) / GROUND_DISTANCE_LIMIT_M
        objective = (
            ground_roll / GROUND_DISTANCE_LIMIT_M
            + 0.2 * buoyancy_ratio
            + 20.0 * violation
            + 100.0 * violation**2
        )

        mtow = _get(prob, "mtow", units="kg")

        constraints = np.array(
            [
                MTOW_LOWER_KG - mtow,             # MTOW >= lower bound
                mtow - MTOW_UPPER_KG,             # MTOW <= upper bound
                ground_roll - GROUND_DISTANCE_LIMIT_M,              # ground distance <= optional limit
                _max_value(prob, "buoyancy_constraint"),
                _max_value(prob, "power_constraint", units="W"),
                _max_value(prob, "energy_constraint"),
            ],
            dtype=float,
        )

        constraints = np.where(
            np.isfinite(constraints),
            constraints,
            1.0e6,
        )

        return float(objective), constraints

    except Exception as exc:
        # Optimizers should receive a penalized design rather than terminate
        # the complete run because one candidate failed numerically.
        print(
            Fore.YELLOW
            + f"OpenMDAO candidate evaluation failed: {exc}"
            + Fore.RESET
        )
        return 1.0e12, np.full(6, 1.0e6)


# -------------------------------------------------------------------------
# pymoo wrapper
# -------------------------------------------------------------------------

class AirshipPymooProblem(ElementwiseProblem):
    """pymoo wrapper around one persistent OpenMDAO problem."""

    def __init__(self, prob: om.Problem):
        lower, upper = get_bounds()

        # pymoo changed the constructor keyword from n_constr to
        # n_ieq_constr in newer releases. Support both.
        try:
            super().__init__(
                n_var=6,
                n_obj=1,
                n_ieq_constr=6,
                xl=lower,
                xu=upper,
            )
        except TypeError:
            super().__init__(
                n_var=6,
                n_obj=1,
                n_constr=6,
                xl=lower,
                xu=upper,
            )

        self.prob = prob

    def _evaluate(self, x, out, *args, **kwargs):
        set_x(self.prob, x)
        objective, constraints = evaluate(self.prob)
        out["F"] = objective
        out["G"] = constraints


# -------------------------------------------------------------------------
# Robust result extraction
# -------------------------------------------------------------------------

def _select_best_from_result(res):
    """Select the best feasible or least-infeasible pymoo candidate."""
    X = getattr(res, "X", None)

    if X is not None:
        X = np.asarray(X)
        return (X if X.ndim == 1 else X[0]), "res.X"

    population = getattr(res, "pop", None)
    if population is not None:
        Xp = population.get("X")
        Fp = np.asarray(population.get("F")).reshape(-1)
        CVp = np.asarray(population.get("CV")).reshape(-1)
        index = np.lexsort((Fp, CVp))[0]
        return Xp[index], "res.pop"

    history = getattr(res, "history", None)
    if history:
        best = None

        for algorithm in history:
            population = getattr(algorithm, "pop", None)
            if population is None:
                continue

            Xp = population.get("X")
            Fp = np.asarray(population.get("F")).reshape(-1)
            CVp = np.asarray(population.get("CV")).reshape(-1)
            index = np.lexsort((Fp, CVp))[0]

            candidate = (
                float(CVp[index]),
                float(Fp[index]),
                np.asarray(Xp[index], dtype=float),
            )

            if (
                best is None
                or candidate[0] < best[0]
                or (
                    candidate[0] == best[0]
                    and candidate[1] < best[1]
                )
            ):
                best = candidate

        if best is not None:
            return best[2], "history"

    raise RuntimeError(
        "pymoo returned no candidates. Increase pop_size/n_gen or inspect "
        "the OpenMDAO constraint outputs."
    )


# -------------------------------------------------------------------------
# Optimization
# -------------------------------------------------------------------------

def run_pymoo(
    pop_size: int = 160,
    n_gen: int = 300,
    seed: int = 11,
    power_source: str = "conventional_reciprocating",
):
    """Run differential-evolution optimization."""
    prob = build_problem(power_source=power_source)

    x0 = np.array(
        [
            _get(prob, "BR_takeoff"),
            _get(prob, "tail_volume_coeff_horizontal"),
            _get(prob, "tail_volume_coeff_vertical"),
            _get(prob, "lift_coeff"),
            _get(prob, "drag_due_to_lift_factor"),
            _get(prob, "propeller_efficiency"),
        ],
        dtype=float,
    )

    pymoo_problem = AirshipPymooProblem(prob)

    algorithm = DE(
        pop_size=pop_size,
        sampling=OMInitialSampling(
            x0,
            jitter=0.08,
        ),
    )
    termination = get_termination(
        "n_gen",
        n_gen,
    )

    print(
        Fore.LIGHTGREEN_EX
        + f"=== pymoo DE: pop={pop_size}, generations={n_gen} ==="
        + Fore.RESET
    )

    result = minimize(
        pymoo_problem,
        algorithm,
        termination,
        seed=seed,
        verbose=True,
        save_history=False,
    )

    design, source = _select_best_from_result(result)
    design = np.asarray(design, dtype=float).reshape(-1)

    set_x(prob, design)
    prob.run_model()

    ground_roll = _get(
        prob,
        "ground_roll_distance",
        units="m",
    )
    buoyancy_ratio = _get(
        prob,
        "BR_takeoff",
    )
    violation = max(0.0, ground_roll - GROUND_DISTANCE_LIMIT_M) / GROUND_DISTANCE_LIMIT_M
    objective = (
        ground_roll / GROUND_DISTANCE_LIMIT_M
        + 0.2 * buoyancy_ratio
        + 20.0 * violation
        + 100.0 * violation**2
    )

    print(
        Fore.LIGHTGREEN_EX
        + "\n=== Best design (pymoo) ==="
        + Fore.RESET
    )
    print(
        f"X (source={source}) = "
        "[BR, tvc_h, tvc_v, Cl, k_lift, eta_p] = "
        f"{design}"
    )
    print(
        f"Objective (hinge + quadratic penalty) = "
        f"{objective:.6f}"
    )
    print(
        f"Result CV, if available = "
        f"{getattr(result, 'CV', None)}"
    )

    return prob, result



    print("\n--- Zeppelin critical diagnostics ---")

    diagnostics = [
        ("ballonet_volume", "m**3"),
        ("ballonet_volume_takeoff", "m**3"),
        ("lifting_gas_volume_takeoff", "m**3"),
        ("lifting_gas_volume_takeoff_used", "m**3"),
        ("he_max_mass", "kg"),
        ("buoyant_lift_required_takeoff", "N"),
        ("buoyant_lift_available_takeoff", "N"),
        ("buoyancy_constraint", "N"),

        ("framework_mass", "kg"),
        ("ballonet_mass", "kg"),
        ("curtain_mass", "kg"),

        ("prime_mover_mass", "kg"),
        ("propeller_mass", "kg"),
        ("nacelle_mass", "kg"),
        ("pylon_mass", "kg"),
        ("propulsion_mass", "kg"),
    ]

    for name, units in diagnostics:
        try:
            value = float(
                np.atleast_1d(
                    prob.get_val(name, units=units)
                )[0]
            )
            print(f"{name:40s}: {value:12.4f} {units}")
        except Exception:
            pass

# -------------------------------------------------------------------------
# Validation reporting
# -------------------------------------------------------------------------

def _constraint_status(value: float) -> str:
    if not np.isfinite(value):
        return "N/A"
    return "PASS" if value <= 0.0 else "FAIL"


def run_validation_and_print(
    prob: om.Problem,
    label: str = "reference / validation case",
    csv_filename: str = "airship_zeppelin_nt_validation_results.csv",
) -> None:
    """Print and export the Zeppelin NT 07-101 reference comparison."""
    buoyancy_constraint = _max_value(
        prob,
        "buoyancy_constraint",
        default=np.nan,
    )
    power_constraint = _max_value(
        prob,
        "power_constraint",
        units="W",
        default=np.nan,
    )
    energy_constraint = _max_value(
        prob,
        "energy_constraint",
        default=np.nan,
    )

    print(f"\n--- Constraint check ({label}) ---")
    print(
        f"mtow [t]:                 "
        f"{_p(prob, 'mtow', 'kg') / 1000.0:.3f} "
        f"(reference {REFERENCE_MTOW_KG / 1000.0:.3f} t)"
    )
    print(
        f"ground_roll_distance [m]: "
        f"{_p(prob, 'ground_roll_distance', 'm'):.2f} "
        f"(optional optimization limit <= {GROUND_DISTANCE_LIMIT_M:.0f})"
    )
    print(
        f"buoyancy_constraint [N]:  "
        f"{buoyancy_constraint:.6f} "
        f"(<= 0 feasible: {_constraint_status(buoyancy_constraint)})"
    )
    print(
        f"power_constraint [W]:     "
        f"{power_constraint:.6f} "
        f"(<= 0 feasible: {_constraint_status(power_constraint)})"
    )
    print(
        f"energy_constraint [kg]:   "
        f"{energy_constraint:.6f} "
        f"(<= 0 feasible: {_constraint_status(energy_constraint)})"
    )
    print(
        f"BR_takeoff [-]:            "
        f"{_p(prob, 'BR_takeoff'):.6f}"
    )
    print(
        f"propeller_efficiency [-]:  "
        f"{_p(prob, 'propeller_efficiency'):.3f}"
    )

    print(
        "Reference set: supplied Zeppelin NT comparison table and technical "
        "data sheets. Unpublished component masses are shown as N/A."
    )
    print(
        f"Geometry basis: L={REFERENCE_LENGTH_M:.2f} m, "
        f"D={REFERENCE_DIAMETER_M:.2f} m, "
        f"L/D={REFERENCE_FINENESS_RATIO:.5f}."
    )
    print(
        f"Secondary published empty mass: "
        f"{SECONDARY_PUBLISHED_EMPTY_MASS_KG:.0f} kg "
        "(not assumed identical to the comparison-table OEW)."
    )

    reference_data = OrderedDict(
        [
            ("Length [m]", {"ref": REFERENCE_LENGTH_M, "var": "length", "units": "m"}),
            ("Fineness Ratio (L/D)", {"ref": REFERENCE_FINENESS_RATIO, "var": "fineness_ratio", "units": None}),
            ("BR at Takeoff", {"ref": REFERENCE_BR_TAKEOFF, "var": "BR_takeoff", "units": None}),
            ("MTOW [kg]", {"ref": REFERENCE_MTOW_KG, "var": "mtow", "units": "kg"}),
            ("Fuel Mass [kg]", {"ref": REFERENCE_FUEL_KG, "var": "installed_consumable_mass", "units": "kg"}),
            ("Installed Shaft Power [kW]", {"ref": REFERENCE_POWER_W / 1000.0, "var": "installed_shaft_power", "units": "kW"}),
            ("Cruise Speed [m/s]", {"ref": REFERENCE_CRUISE_SPEED_MPS, "var": "mission_speed_used", "units": "m/s"}),
            # Zeppelin NT uses vectored thrust and can perform very short/vertical
            # takeoff. No comparable conventional ground-roll reference was supplied.
            ("Ground Roll [m]", {"ref": np.nan, "var": "ground_roll_distance", "units": "m"}),
            ("Wetted Surface Area [m²]", {"ref": np.nan, "var": "wetted_surface_area", "units": "m**2"}),
            ("Gross Volume [m³]", {"ref": REFERENCE_VOLUME_M3, "var": "gross_volume", "units": "m**3"}),
            ("Ref Area AeroCoeffs [m²]", {"ref": np.nan, "var": "ref_area_AeroCoeffs", "units": "m**2"}),
            ("Weight Gross Area [m²]", {"ref": np.nan, "var": "weight.aerodynamic_reference_area", "units": "m**2"}),
        ]
    )

    breakdown_variables = OrderedDict(
        [
            ("Envelope Mass", {"var": "envelope_mass", "ref": np.nan}),
            ("Gondola Mass", {"var": "gondola_mass", "ref": np.nan}),
            ("Fin Mass", {"var": "fin_mass", "ref": np.nan}),
            ("Landing System Mass", {"var": "landing_system_mass", "ref": np.nan}),
            ("Propulsion Mass", {"var": "propulsion_mass", "ref": np.nan}),
            ("Power System Mass", {"var": "power_system_mass", "ref": np.nan}),
            ("Tank Mass", {"var": "tank_mass", "ref": np.nan}),
            ("Crew Mass", {"var": None, "ref": np.nan}),
            ("Miscellaneous Mass", {"var": "miscellaneous_mass", "ref": np.nan}),
            ("Operating Empty Weight (OEW)", {"var": "owe", "ref": REFERENCE_BASE_MASS_KG}),
            ("Fuel Capacity Mass", {"var": "installed_consumable_mass", "ref": REFERENCE_FUEL_KG}),
            ("Payload Mass", {"var": "payload", "ref": REFERENCE_PAYLOAD_KG}),
            ("Maximum Takeoff Weight (MTOW)", {"var": "mtow", "ref": REFERENCE_MTOW_KG}),
            ("Helium Mass", {"var": "he_max_mass", "ref": np.nan}),
        ]
    )

    validation_rows = []
    mass_breakdown_data = {}
    csv_rows = [
        [
            "Category",
            "Parameter",
            "Reference",
            "Our Tool",
            "Units",
            "Percent Error (%)",
        ]
    ]

    for parameter_name, data in reference_data.items():
        reference = data["ref"]
        variable = data["var"]
        units = data["units"]
        calculated = _get(
            prob,
            variable,
            units=units,
        )

        error = (
            np.nan
            if (
                not np.isfinite(calculated)
                or not np.isfinite(reference)
                or reference == 0.0
            )
            else (
                (calculated - reference)
                / reference
                * 100.0
            )
        )

        validation_rows.append(
            {
                "Parameter": parameter_name,
                "Reference": reference,
                "Our Tool": calculated,
                "% Error": error,
            }
        )

        csv_rows.append(
            [
                "Validation",
                parameter_name,
                f"{reference:.4f}",
                (
                    f"{calculated:.4f}"
                    if np.isfinite(calculated)
                    else "N/A"
                ),
                units or "-",
                (
                    f"{error:+.4f}"
                    if np.isfinite(error)
                    else "N/A"
                ),
            ]
        )

    crew_mass = _get_crew_mass(prob)

    for label, data in breakdown_variables.items():
        reference = data["ref"]
        variable = data["var"]

        if variable is None and label == "Crew Mass":
            calculated = crew_mass
        elif variable is not None:
            calculated = _get(
                prob,
                variable,
                units="kg",
            )
        else:
            continue

        mass_breakdown_data[label] = {
            "calc": calculated,
            "ref": reference,
        }

        error = (
            np.nan
            if (
                not np.isfinite(calculated)
                or not np.isfinite(reference)
                or reference == 0.0
            )
            else (
                (calculated - reference)
                / reference
                * 100.0
            )
        )

        csv_rows.append(
            [
                "Mass Breakdown",
                label,
                (
                    f"{reference:.4f}"
                    if np.isfinite(reference)
                    else "N/A"
                ),
                (
                    f"{calculated:.4f}"
                    if np.isfinite(calculated)
                    else "N/A"
                ),
                "kg",
                (
                    f"{error:+.4f}"
                    if np.isfinite(error)
                    else "N/A"
                ),
            ]
        )

    csv_path = Path(csv_filename).resolve()

    try:
        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as stream:
            csv.writer(stream).writerows(csv_rows)

        print(
            "\n"
            + Fore.LIGHTGREEN_EX
            + f"Validation results saved to {csv_path}"
            + Fore.RESET
        )
    except Exception as exc:
        print(
            Fore.RED
            + f"CSV save failed: {exc}"
            + Fore.RESET
        )

    print(
        Fore.LIGHTGREEN_EX
        + "\n=== Table 4.1. Zeppelin NT validation results ==="
        + Fore.RESET
    )
    print("-" * 78)
    print(
        f"{'Parameter':<30}"
        f"{'Reference':>15}"
        f"{'Our Tool':>15}"
        f"{'% Error':>15}"
    )
    print("-" * 78)

    for data in validation_rows:
        parameter = data["Parameter"]
        reference = data["Reference"]
        calculated = data["Our Tool"]
        error = data["% Error"]

        reference_text = (
            f"{reference:.2f}"
            if np.isfinite(reference)
            else "N/A"
        )
        calculated_text = (
            f"{calculated:.2f}"
            if np.isfinite(calculated)
            else "N/A"
        )
        error_text = (
            f"{error:+.2f}%"
            if np.isfinite(error)
            else "N/A"
        )

        print(
            f"{parameter:<30}"
            f"{reference_text:>15}"
            f"{calculated_text:>15}"
            f"{error_text:>15}"
        )

    print("-" * 78)

    print(
        Fore.LIGHTGREEN_EX
        + "\n=== Table 4.2. MTOW mass buildup [kg] ==="
        + Fore.RESET
    )
    print("-" * 78)
    print(
        f"{'Component':<32}"
        f"{'Reference':>15}"
        f"{'Our Tool':>15}"
        f"{'% Error':>15}"
    )
    print("-" * 78)


    # -------------------------------------------------------------------------
    # Zeppelin semi-rigid detailed mass breakdown
    # -------------------------------------------------------------------------
    print("\n--- Zeppelin semi-rigid detailed mass breakdown ---")
    for name in [
        "framework_mass",
        "ballonet_mass",
        "curtain_mass",
        "envelope_mass",
        "gondola_mass",
        "fin_mass",
        "propulsion_mass",
        "power_system_mass",
        "landing_system_mass",
        "crew_mass",
        "miscellaneous_mass",
        "owe",
        "mtow",
    ]:
        try:
            value = float(np.atleast_1d(prob.get_val(name, units="kg"))[0])
            print(f"{name:35s}: {value:10.2f} kg")
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Zeppelin critical diagnostics
    # -------------------------------------------------------------------------
    print("\n--- Zeppelin critical diagnostics ---")
    diagnostics = [
        ("ballonet_volume", "m**3"),
        ("ballonet_volume_takeoff", "m**3"),
        ("lifting_gas_volume_takeoff", "m**3"),
        ("lifting_gas_volume_takeoff_used", "m**3"),
        ("he_max_mass", "kg"),
        ("buoyant_lift_required_takeoff", "N"),
        ("buoyant_lift_available_takeoff", "N"),
        ("buoyancy_constraint", "N"),
        ("framework_mass", "kg"),
        ("ballonet_mass", "kg"),
        ("curtain_mass", "kg"),
        ("prime_mover_mass", "kg"),
        ("propeller_mass", "kg"),
        ("nacelle_mass", "kg"),
        ("pylon_mass", "kg"),
        ("propulsion_mass", "kg"),
    ]
    for name, units in diagnostics:
        try:
            value = float(np.atleast_1d(prob.get_val(name, units=units))[0])
            print(f"{name:40s}: {value:12.4f} {units}")
        except Exception:
            pass

    for label, data in mass_breakdown_data.items():
        reference = data["ref"]
        calculated = data["calc"]

        error = (
            np.nan
            if (
                not np.isfinite(reference)
                or not np.isfinite(calculated)
                or reference == 0.0
            )
            else (
                (calculated - reference)
                / reference
                * 100.0
            )
        )

        reference_text = (
            f"{reference:.2f}"
            if np.isfinite(reference)
            else "N/A"
        )
        calculated_text = (
            f"{calculated:.2f}"
            if np.isfinite(calculated)
            else "N/A"
        )
        error_text = (
            f"{error:+.2f}%"
            if np.isfinite(error)
            else "N/A"
        )

        row = (
            f"{label:<32}"
            f"{reference_text:>15}"
            f"{calculated_text:>15}"
            f"{error_text:>15}"
        )

        if "OEW" in label or "MTOW" in label:
            print(Fore.CYAN + row + Fore.RESET)
        else:
            print(row)

    print("-" * 78)


    # Optional XDSM export. Disabled by default because it requires LaTeX.
    if GENERATE_XDSM:
        write_xdsm(
            prob,
            filename=r"Zeppelin_NT_Airship_Sizing_xdsm",
            out_format="pdf",
            show_browser=True,
            quiet=False,
            output_side="left",
            include_indepvarcomps=True,
            class_names=False,
        )



# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

if __name__ == "__main__":
    # First explain the analysis boundary to the user/reviewer. This is especially
    # useful because a component input (e.g. length) can still be a system-level
    # design variable and final sizing result.
    print_variable_role_guide()
    role_map_path = export_variable_role_map()
    print(f"\nVariable-role map saved to: {role_map_path}")

    # 1. Zeppelin NT reference validation case.
    # Known Zeppelin geometry and installed capacities are intentionally imposed.
    baseline_prob = build_problem(
        power_source="conventional_reciprocating",
    )

    print(
        Fore.LIGHTGREEN_EX
        + "\n=== Zeppelin NT baseline/reference case ==="
        + Fore.RESET
    )

    run_validation_and_print(
        baseline_prob,
        label="Zeppelin NT baseline / reference case",
    )

    # 2. Optional optimization. It is disabled for a pure validation run.
    # The supplied references do not include a directly comparable ground-roll
    # target, so enable this only when you intentionally want a design study.
    if RUN_OPTIMIZATION:
        opt_prob, result = run_pymoo(
            pop_size=160,
            n_gen=300,
            seed=11,
            power_source="conventional_reciprocating",
        )

        print(
            Fore.LIGHTGREEN_EX
            + "\n=== Optimized design constraint check ==="
            + Fore.RESET
        )

        buoyancy_constraint = _max_value(opt_prob, "buoyancy_constraint")
        power_constraint = _max_value(opt_prob, "power_constraint", units="W")
        energy_constraint = _max_value(opt_prob, "energy_constraint")

        print(f"mtow [t]:                 {_p(opt_prob, 'mtow', 'kg') / 1000.0:.3f}")
        print(f"ground_roll_distance [m]: {_p(opt_prob, 'ground_roll_distance', 'm'):.2f}")
        print(f"buoyancy_constraint [N]:  {buoyancy_constraint:.6f} "
              f"(<= 0 feasible: {_constraint_status(buoyancy_constraint)})")
        print(f"power_constraint [W]:     {power_constraint:.6f} "
              f"(<= 0 feasible: {_constraint_status(power_constraint)})")
        print(f"energy_constraint [kg]:   {energy_constraint:.6f} "
              f"(<= 0 feasible: {_constraint_status(energy_constraint)})")
        print(f"BR_takeoff [-]:            {_p(opt_prob, 'BR_takeoff'):.6f}")
        print(f"propeller_efficiency [-]:  {_p(opt_prob, 'propeller_efficiency'):.3f}")

    print(
        Fore.LIGHTGREEN_EX
        + "=== Zeppelin NT validation run complete ==="
        + Fore.RESET
    )


    print("\n--- Zeppelin semi-rigid detailed mass breakdown ---")


