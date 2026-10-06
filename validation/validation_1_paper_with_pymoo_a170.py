# -*- coding: utf-8 -*-
"""
A-170 validation and optional pymoo optimization for the updated ADaPT framework.

===============================================================================
HOW TO READ THIS DRIVER: FRAMEWORK INPUTS, COMPONENT INPUTS, AND OUTPUTS
===============================================================================

A variable can have different roles depending on the analysis boundary.

LEVEL 1 — MISSION / DESIGN REQUIREMENTS
---------------------------------------
These describe what the airship must accomplish and are normally imposed by
the user in a clean-sheet sizing study:

    payload
    range
    cruise_altp
    cruise_speed
    architecture / power_source

LEVEL 2 — SYSTEM-LEVEL DESIGN VARIABLES
---------------------------------------
These describe the candidate airship and may be selected by a designer or
optimizer:

    length
    fineness_ratio
    tail_volume_coeff_horizontal
    tail_volume_coeff_vertical
    BR_takeoff
    lift_coeff
    drag_due_to_lift_factor
    propeller_efficiency
    installed_shaft_power

IMPORTANT:
    "Input to an OpenMDAO component" does NOT mean "known mission requirement."

Example: length
---------------
``length`` is an input to AirshipGeometry because Geometry needs a candidate
length to calculate diameter, gross volume, wetted area, tail area, etc.

In a CLEAN-SHEET sizing problem, however, length may be a SYSTEM-LEVEL DESIGN
VARIABLE. The optimizer changes length until the complete vehicle satisfies
payload, range, power, energy, buoyancy, lift, takeoff, landing, and other
constraints. The final optimized length is therefore a SIZING RESULT even
though it is an input to the Geometry component mathematically.

LEVEL 3 — COUPLING VARIABLES / COMPONENT OUTPUTS
------------------------------------------------
These are calculated by one component and passed to another:

    length + fineness_ratio
        -> Geometry
        -> gross_volume, wetted_surface_area, reference area, fin area
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
        -> Propulsion / Power / resource models
        -> propulsion mass, power-system mass, fuel/H2/battery requirement
        -> Weight

These variables close the multidisciplinary sizing loop.

LEVEL 4 — FINAL VEHICLE RESULTS
-------------------------------
Typical final results include:

    final/optimized length and diameter
    gross volume
    wetted area
    OEW
    MTOW
    propulsion-system mass
    fuel / hydrogen / battery requirement
    required and installed power
    takeoff / landing performance
    feasibility margins

Thus a quantity such as ``length`` may simultaneously be:
    - an input to Geometry,
    - a system-level design variable,
    - a known reference input during validation,
    - and a final reported sizing result after optimization.

===============================================================================
THREE DIFFERENT WAYS ADaPT CAN BE USED
===============================================================================

1. REFERENCE-AIRCRAFT VALIDATION
   Known A-170 geometry, mission conditions, and installed hardware are fixed.
   ADaPT predicts other quantities for comparison with the published A-170.

2. FORWARD MISSION ANALYSIS
   A fixed airship is evaluated on a specified mission to predict power,
   energy/resource use, endurance, takeoff/landing performance, and feasibility.

3. CLEAN-SHEET SIZING / OPTIMIZATION
   Payload, range, operating conditions, and architecture are requirements.
   Candidate geometry/technology/design variables are changed until the coupled
   design satisfies constraints and the objective is optimized.

===============================================================================
WHAT THIS PARTICULAR SCRIPT DOES
===============================================================================

This file is primarily an A-170 VALIDATION DRIVER, with a separate OPTIONAL
pymoo parameter optimization.

For the baseline validation, published/book-based A-170 quantities such as:

    length
    fineness ratio
    payload
    range
    cruise condition
    installed consumable capacity
    installed shaft power
    BR_takeoff

are deliberately imposed.

The purpose is to ask:

    "If ADaPT is given the known A-170 configuration and mission, does it
     reproduce published quantities such as gross volume, wetted area, OEW,
     MTOW, takeoff performance, and component masses?"

Therefore ``length`` is FIXED in the baseline validation run. This does NOT
mean that ADaPT generally requires the user to know the final airship length
before a clean-sheet sizing study.

The optional pymoo section is also NOT a complete clean-sheet airship-sizing
optimization. It currently varies only:

    BR_takeoff,
    tail_volume_coeff_horizontal,
    tail_volume_coeff_vertical,
    lift_coeff,
    drag_due_to_lift_factor,
    propeller_efficiency.

Primary geometry variables such as length and fineness ratio remain fixed in
that optional study.

===============================================================================
OPENMDAO OWNERSHIP
===============================================================================

AirshipAnalysisGroup already contains the central AirshipIndepVariables
subsystem. Do not add another promoted IndepVarComp.

The driver therefore:
    1. Adds/configures AirshipAnalysisGroup directly.
    2. Calls Problem.setup().
    3. Sets the built-in independent-variable outputs with Problem.set_val().
    4. Runs the model.

Constraint convention
---------------------
The updated ADaPT components use:

    constraint <= 0  -> feasible

This applies to power, energy, buoyancy, lift, takeoff/ground, and landing
constraints.
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

# Add ONLY the repository root.
#
# Do not add PROJECT_ROOT / "adapt" directly to sys.path.
# ADaPT is now imported consistently as a package.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapt.AirshipAnalysisGroup import AirshipAnalysisGroup
from adapt.operatingConditions import opCond


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
# A-170 reference constants
# -------------------------------------------------------------------------

A170_REFERENCE = {
    "length_m": 53.58,
    "fineness_ratio": 4.10,
    "payload_kg": 1122.0,
    "range_m": 1_342_100.0,
    "cruise_altitude_m": 914.4,
    "cruise_speed_mps": 19.57,
    "installed_consumable_capacity_kg": 599.0,
    "ballast_mass_kg": 0.0,
    "n_crew": 1.0,
    "n_engine": 2.0,
    "installed_shaft_power_w": 268_000.0,
    "BR_takeoff": 0.816,
    "BR_landing": 0.90,
}

# -------------------------------------------------------------------------
# Variable-role map
# -------------------------------------------------------------------------
#
# This registry is for USER/REVIEWER CLARITY. It does not change the physics.
#
# component_direction -> how OpenMDAO components exchange the quantity
# system_role         -> engineering meaning in a sizing/MDAO problem
# validation_role     -> what this A-170 validation does with the quantity
#
VARIABLE_ROLE_MAP = OrderedDict(
    [
        (
            "payload",
            {
                "component_direction": "Independent variable -> Weight/Performance",
                "system_role": "MISSION REQUIREMENT",
                "validation_role": "FIXED to published A-170 payload",
                "explanation": (
                    "Payload is what the airship must carry. In a clean-sheet sizing "
                    "study it is normally prescribed rather than solved."
                ),
            },
        ),
        (
            "range",
            {
                "component_direction": "Independent variable -> Performance/Mission",
                "system_role": "MISSION REQUIREMENT",
                "validation_role": "FIXED to the A-170 reference mission",
                "explanation": (
                    "Range defines the mission distance and drives mission duration "
                    "and resource/energy requirement."
                ),
            },
        ),
        (
            "cruise_altp",
            {
                "component_direction": "Independent variable -> Atmosphere/Performance",
                "system_role": "MISSION / OPERATING CONDITION",
                "validation_role": "FIXED to the A-170 reference cruise altitude",
                "explanation": "Defines the atmospheric operating state.",
            },
        ),
        (
            "cruise_speed",
            {
                "component_direction": "Independent variable -> Performance",
                "system_role": "MISSION / OPERATING CONDITION",
                "validation_role": "FIXED to the A-170 reference cruise speed",
                "explanation": (
                    "The baseline validation evaluates the reference aircraft at its "
                    "specified cruise condition."
                ),
            },
        ),
        (
            "length",
            {
                "component_direction": "Input to Geometry",
                "system_role": "SYSTEM DESIGN VARIABLE / FINAL SIZING RESULT",
                "validation_role": "FIXED because A-170 reference length is known",
                "explanation": (
                    "Geometry needs a candidate length to calculate diameter, volume "
                    "and areas. In clean-sheet sizing an optimizer may vary length; "
                    "the converged value is then reported as the final size."
                ),
            },
        ),
        (
            "fineness_ratio",
            {
                "component_direction": "Input to Geometry",
                "system_role": "SYSTEM DESIGN VARIABLE",
                "validation_role": "FIXED to the A-170 reference value",
                "explanation": (
                    "Together with length it defines the candidate hull geometry."
                ),
            },
        ),
        (
            "gross_volume",
            {
                "component_direction": "Geometry output -> Weight/Performance",
                "system_role": "COUPLING VARIABLE / VEHICLE RESULT",
                "validation_role": "PREDICTED and compared with the A-170 reference",
                "explanation": (
                    "Gross volume is calculated from the imposed A-170 geometry and "
                    "then used by buoyancy, helium, mass and performance models."
                ),
            },
        ),
        (
            "wetted_surface_area",
            {
                "component_direction": "Geometry output -> downstream models",
                "system_role": "COUPLING VARIABLE / VEHICLE RESULT",
                "validation_role": "PREDICTED and compared with the A-170 reference",
                "explanation": "Calculated hull surface area.",
            },
        ),
        (
            "BR_takeoff",
            {
                "component_direction": "Independent/design variable -> Performance",
                "system_role": "CONFIGURATION / DESIGN VARIABLE",
                "validation_role": "FIXED to the A-170 reference baseline",
                "explanation": (
                    "Controls the split between buoyant and aerodynamic support. "
                    "It may be varied in design studies."
                ),
            },
        ),
        (
            "installed_shaft_power",
            {
                "component_direction": "Installed-capacity input -> Performance/Propulsion",
                "system_role": "INSTALLED CAPACITY / DESIGN VARIABLE",
                "validation_role": "FIXED to published A-170 installed power",
                "explanation": (
                    "The known reference rating is imposed for validation. In sizing "
                    "it may instead be selected by sizing logic or an optimizer."
                ),
            },
        ),
        (
            "installed_consumable_mass",
            {
                "component_direction": "Resource capacity -> Weight/Performance",
                "system_role": "INSTALLED RESOURCE CAPACITY",
                "validation_role": "FIXED from A-170 reference fuel capacity",
                "explanation": (
                    "The validation intentionally imposes the known onboard capacity; "
                    "mission-required consumption is evaluated separately."
                ),
            },
        ),
        (
            "owe",
            {
                "component_direction": "Weight output",
                "system_role": "PRIMARY VEHICLE SIZING RESULT",
                "validation_role": "PREDICTED and compared with A-170 OEW",
                "explanation": "Integrated operating-empty-weight prediction.",
            },
        ),
        (
            "mtow",
            {
                "component_direction": "Weight output -> Performance input",
                "system_role": "COUPLING VARIABLE / PRIMARY SIZING RESULT",
                "validation_role": "PREDICTED and compared with A-170 MTOW",
                "explanation": (
                    "MTOW is calculated from the vehicle mass buildup and then used "
                    "by Performance."
                ),
            },
        ),
        (
            "required_shaft_power",
            {
                "component_direction": "Performance output -> Propulsion/Power",
                "system_role": "COUPLING VARIABLE / REQUIRED CAPABILITY",
                "validation_role": "PREDICTED",
                "explanation": (
                    "Mission/performance calculates required power; installed power "
                    "is a separate capability."
                ),
            },
        ),
        (
            "ground_roll_distance",
            {
                "component_direction": "Performance output",
                "system_role": "PERFORMANCE RESULT / FEASIBILITY METRIC",
                "validation_role": "PREDICTED and compared with A-170 reference",
                "explanation": (
                    "A performance output. Note that current component naming may "
                    "represent total takeoff distance under this legacy name."
                ),
            },
        ),
    ]
)


def print_variable_role_guide() -> None:
    """Print a reviewer-friendly guide to A-170 validation variable roles."""
    print("\n" + "=" * 92)
    print("ADaPT A-170 VARIABLE ROLES — HOW TO INTERPRET INPUTS AND OUTPUTS")
    print("=" * 92)
    print(
        "OpenMDAO input/output describes COMPONENT DATA FLOW. It does not by itself "
        "say whether a quantity is a mission requirement, a design variable, a "
        "reference-aircraft value, or a final sizing result."
    )
    print("\nThree analysis modes:")
    print("  1. VALIDATION: known A-170 geometry/hardware are fixed; ADaPT predicts")
    print("     independent quantities for comparison with the reference aircraft.")
    print("  2. FORWARD MISSION ANALYSIS: a fixed airship is evaluated on a mission.")
    print("  3. CLEAN-SHEET SIZING/OPTIMIZATION: mission requirements remain fixed while")
    print("     candidate geometry/technology variables are varied until constraints close.")
    print("\nKey example:")
    print("  length -> INPUT to Geometry component")
    print("         -> DESIGN VARIABLE in clean-sheet MDAO sizing")
    print("         -> FIXED REFERENCE VALUE in this A-170 validation")
    print("         -> FINAL SIZING RESULT after optimization")
    print("\nVariable map:")
    for name, meta in VARIABLE_ROLE_MAP.items():
        print(f"\n  {name}")
        print(f"    Component flow : {meta['component_direction']}")
        print(f"    System role    : {meta['system_role']}")
        print(f"    This validation: {meta['validation_role']}")
        print(f"    Why            : {meta['explanation']}")
    print("=" * 92)


def export_variable_role_map(
    filename: str = "a170_validation_variable_roles.csv",
) -> Path:
    """Export the reviewer-facing A-170 variable-role classification."""
    path = Path(filename).resolve()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "Variable",
                "Component Direction",
                "System-Level Role",
                "Role in A-170 Validation",
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
# Run controls
# -------------------------------------------------------------------------

RUN_OPTIMIZATION = False
GENERATE_XDSM = False


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
        T_env=281.65,
        altitude=914.0,
        speed=19.5 / 337.5,
        time="day",
        RH=70.0,
    )

    prob = om.Problem()

    # AirshipAnalysisGroup is the top-level model. Its internal subsystem
    # "indep" supplies the independent variables.
    prob.model = AirshipAnalysisGroup(
        phd=phd,
        power_source=power_source,
        landing_system="conventional",
        airship_type="non-rigid",
        num_steps=num_steps,

        use_prescribed_consumable_capacity=True,
        ballonet_sizing_method="prescribed_fraction",

        # ----------------------------------------------------------
        # A-170 propulsion configuration
        # ----------------------------------------------------------
        propulsion_installation_mass_method="generic",

        # ----------------------------------------------------------
        # A-170 weight validation configuration
        # ----------------------------------------------------------
        weight_gondola_method="override",
        weight_gondola_mass_override=1500.0,

        # A-170 actual/reference conventional fuel-system hardware.
        weight_fuel_tank_method="override",
        weight_fuel_tank_mass_override=42.0,

        # A-170 air/pressure-system mass from the published breakdown.
        weight_pressure_system_method="override",
        weight_pressure_system_mass_override=67.1,

        # VMS/FCS ownership is not imposed until actuator/FCS mapping is unambiguous.
        weight_vms_method="none",
        weight_vms_mass_override=0.0,

        # 75 kg / 3908 kg reference OEW
        weight_miscellaneous_fraction=(75.0 / 3908.0),
    )

    prob.setup(check=setup_check)

    # ------------------------------------------------------------------
    # A-170 VALIDATION CASE DEFINITION
    # ------------------------------------------------------------------
    #
    # IMPORTANT:
    # These set_val() calls do not mean that all values below are fundamental
    # framework inputs. They mean that, for THIS reference-aircraft validation,
    # known/book-based A-170 data are imposed so that other quantities can be
    # predicted independently and compared with the reference.
    #
    # In clean-sheet sizing:
    #   * payload/range/operating conditions are mission requirements;
    #   * length, fineness ratio, BR, installed power, etc. may be design variables;
    #   * gross volume, OEW, MTOW, power demand and resource masses are calculated
    #     coupling variables/results.
    #
    # --- A. Known A-170 geometry imposed ONLY for validation ---
    prob.set_val("length", A170_REFERENCE["length_m"], units="m")
    prob.set_val("fineness_ratio", A170_REFERENCE["fineness_ratio"])
    prob.set_val("tail_volume_coeff_horizontal", 0.066)
    prob.set_val("tail_volume_coeff_vertical", 0.059)

    # --- B. Mission requirements / operating conditions ---
    prob.set_val("payload", A170_REFERENCE["payload_kg"], units="kg")
    prob.set_val("range", A170_REFERENCE["range_m"], units="m")

    prob.set_val(
        "cruise_altp",
        np.full(num_steps, A170_REFERENCE["cruise_altitude_m"]),
        units="m",
    )
    prob.set_val(
        "cruise_disa",
        np.zeros(num_steps),
        units="K",
    )
    prob.set_val(
        "cruise_speed",
        np.full(num_steps, A170_REFERENCE["cruise_speed_mps"]),
        units="m/s",
    )

    prob.set_val(
        "maximum_speed",
        A170_REFERENCE["cruise_speed_mps"],
        units="m/s",
    )

    # --- C. Known installed resource/capacity imposed for validation ---
    prob.set_val(
        "installed_consumable_capacity",
        A170_REFERENCE["installed_consumable_capacity_kg"],
        units="kg",
    )

    prob.set_val(
        "ballast_mass",
        A170_REFERENCE["ballast_mass_kg"],
        units="kg",
    )

    prob.set_val(
        "ballonet_fraction_prescribed",
        0.08,
    )

    # --- D. Known A-170 configuration / installed hardware ---
    prob.set_val("n_crew", A170_REFERENCE["n_crew"])
    prob.set_val("n_engine", A170_REFERENCE["n_engine"])

    # Installed power is a known reference-aircraft capacity in validation.
    # In a clean-sheet sizing run it may instead be sized or optimized.
    # Updated name: engine_power -> installed_shaft_power.
    prob.set_val(
        "installed_shaft_power",
        A170_REFERENCE["installed_shaft_power_w"],
        units="W",
    )

    prob.set_val("propeller_efficiency", 0.75)
    prob.set_val("BR_takeoff", A170_REFERENCE["BR_takeoff"])
    prob.set_val("BR_landing", A170_REFERENCE["BR_landing"])
    prob.set_val("lift_coeff", 0.15)
    prob.set_val("drag_due_to_lift_factor", 0.869)

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

        # Hinge plus quadratic penalty for ground roll above 430 m.
        violation = max(0.0, ground_roll - 430.0) / 430.0
        objective = (
            ground_roll / 430.0
            + 0.2 * buoyancy_ratio
            + 20.0 * violation
            + 100.0 * violation**2
        )

        mtow = _get(prob, "mtow", units="kg")

        constraints = np.array(
            [
                5000.0 - mtow,                    # MTOW >= 5000 kg
                mtow - 7000.0,                    # MTOW <= 7000 kg
                ground_roll - 430.0,              # ground roll <= 430 m
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
    violation = max(0.0, ground_roll - 430.0) / 430.0
    objective = (
        ground_roll / 430.0
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
    csv_filename: str = "airship_a170_validation_results.csv",
) -> None:
    """Print and export the A-170 reference comparison."""
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
        "(target 5.000–7.000)"
    )
    print(
        f"ground_roll_distance [m]: "
        f"{_p(prob, 'ground_roll_distance', 'm'):.2f} "
        "(target <= 430)"
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
        "Reference set: book-based A-170 sample problem / "
        "extracted breakdown values"
    )
    print(
        "A-170 validation overrides: gondola=1500.0 kg, "
        "fuel tank/system=42.0 kg, pressure/air system=67.1 kg, "
        "VMS disabled pending unambiguous FCS/actuator mapping."
    )

    reference_data = OrderedDict(
        [
            (
                "Length [m]",
                {
                    "ref": 53.58,
                    "var": "length",
                    "units": "m",
                },
            ),
            (
                "Fineness Ratio",
                {
                    "ref": 4.10,
                    "var": "fineness_ratio",
                    "units": None,
                },
            ),
            (
                "BR at Takeoff",
                {
                    "ref": A170_REFERENCE["BR_takeoff"],
                    "var": "BR_takeoff",
                    "units": None,
                },
            ),
            (
                "MTOW [kg]",
                {
                    "ref": 5629.0,
                    "var": "mtow",
                    "units": "kg",
                },
            ),
            (
                "Fuel Mass [kg]",
                {
                    "ref": 599.0,
                    "var": "installed_consumable_mass",
                    "units": "kg",
                },
            ),
            (
                "Installed Shaft Power [kW]",
                {
                    "ref": 268.0,
                    "var": "installed_shaft_power",
                    "units": "kW",
                },
            ),
            (
                "Cruise Speed [m/s]",
                {
                    "ref": 19.57,
                    "var": "mission_speed_used",
                    "units": "m/s",
                },
            ),
            (
                "Ground Roll [m]",
                {
                    "ref": 432.0,
                    "var": "ground_roll_distance",
                    "units": "m",
                },
            ),
            (
                "Wetted Surface Area [m²]",
                {
                    "ref": 1771.0,
                    "var": "wetted_surface_area",
                    "units": "m**2",
                },
            ),
            (
                "Gross Volume [m³]",
                {
                    "ref": 4823.0,
                    "var": "gross_volume",
                    "units": "m**3",
                },
            ),
            (
                "Ref Area AeroCoeffs [m²]",
                {
                    "ref": 285.0,
                    "var": "ref_area_AeroCoeffs",
                    "units": "m**2",
                },
            ),
            (
                "Weight Gross Area [m²]",
                {
                    "ref": 1771.0,
                    "var": "weight.aerodynamic_reference_area",
                    "units": "m**2",
                },
            ),
        ]
    )

    breakdown_variables = OrderedDict(
        [
            (
                "Envelope Mass",
                {
                    "var": "envelope_mass",
                    "ref": 678.0,
                },
            ),
            (
                "Gondola Mass",
                {
                    "var": "gondola_mass",
                    "ref": 1500.0,
                },
            ),
            (
                "Fin Mass",
                {
                    "var": "fin_mass",
                    "ref": 317.0,
                },
            ),
            (
                "Tail Structural Mass",
                {
                    "var": None,
                    "ref": 317.0,
                },
            ),
            (
                "Landing System Mass",
                {
                    "var": "landing_system_mass",
                    "ref": 94.0,
                },
            ),
            (
                "Propulsion Mass",
                {
                    "var": "propulsion_mass",
                    "ref": 595.0,
                },
            ),
            (
                "Power System Mass",
                {
                    "var": "power_system_mass",
                    "ref": 98.0,
                },
            ),
            (
                "Fuel Tank/System Mass",
                {
                    "var": "fuel_tank_mass",
                    "ref": 42.0,
                },
            ),
            (
                "Pressure/Air System Mass",
                {
                    "var": "pressure_system_mass",
                    "ref": 67.1,
                },
            ),
            (
                "VMS Mass",
                {
                    "var": "vms_mass",
                    "ref": np.nan,
                },
            ),
            (
                "Crew Mass",
                {
                    "var": None,
                    "ref": 113.0,
                },
            ),
            (
                "Miscellaneous Mass",
                {
                    "var": "miscellaneous_mass",
                    "ref": 75.0,
                },
            ),
            (
                "Operating Empty Weight (OEW)",
                {
                    "var": "owe",
                    "ref": 3908.0,
                },
            ),
            (
                "Fuel Capacity Mass",
                {
                    "var": "installed_consumable_mass",
                    "ref": 599.0,
                },
            ),
            (
                "Payload Mass",
                {
                    "var": "payload",
                    "ref": 1122.0,
                },
            ),
            (
                "Maximum Takeoff Weight (MTOW)",
                {
                    "var": "mtow",
                    "ref": 5629.0,
                },
            ),
            (
                "Helium Mass",
                {
                    "var": "he_max_mass",
                    "ref": np.nan,
                },
            ),
        ]
    )

    # ------------------------------------------------------------------
    # Validation-role classification
    # ------------------------------------------------------------------
    # REF  = prescribed reference input (do NOT use zero error as validation evidence)
    # PRED = independently predicted validation quantity
    # PERF = independently predicted performance quantity
    # CAL  = calibration parameter
    # N/A  = no independent reference available
    validation_role = {
        "Length [m]": ("REF", "Prescribed A-170 reference geometry"),
        "Fineness Ratio": ("REF", "Prescribed A-170 reference geometry"),
        "BR at Takeoff": ("REF", "Prescribed A-170 configuration value"),
        "MTOW [kg]": ("PRED", "Weight-model output compared with reference MTOW"),
        "Fuel Mass [kg]": ("REF", "Known installed consumable capacity"),
        "Installed Shaft Power [kW]": ("REF", "Known installed A-170 power rating"),
        "Cruise Speed [m/s]": ("REF", "Prescribed reference operating condition"),
        "Ground Roll [m]": ("PERF", "Performance-model prediction compared with reference"),
        "Wetted Surface Area [m²]": ("PRED", "Geometry-model prediction"),
        "Gross Volume [m³]": ("PRED", "Geometry-model prediction"),
        "Ref Area AeroCoeffs [m²]": ("PRED", "Derived geometry/aerodynamic quantity"),
        "Weight Gross Area [m²]": ("PRED", "Derived geometry quantity used by Weight"),
    }

    validation_rows = []
    mass_breakdown_data = {}
    csv_rows = [
        [
            "Category",
            "Role",
            "Parameter",
            "Reference",
            "Our Tool",
            "Units",
            "Percent Error (%)",
            "Interpretation",
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

        role, interpretation = validation_role.get(
            parameter_name,
            ("PRED", "Calculated ADaPT quantity"),
        )

        # Percent error is reported as VALIDATION ERROR only for independently
        # predicted quantities. For REF inputs, agreement is expected because
        # the value was deliberately imposed from the reference aircraft.
        error = (
            np.nan
            if (
                role == "REF"
                or not np.isfinite(calculated)
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
                "Role": role,
                "Parameter": parameter_name,
                "Reference": reference,
                "Our Tool": calculated,
                "% Error": error,
                "Interpretation": interpretation,
            }
        )

        csv_rows.append(
            [
                "Validation",
                role,
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
                interpretation,
            ]
        )

    crew_mass = _get_crew_mass(prob)

    tail_fixed_mass = _get(prob, "tail_fixed_mass", units="kg")
    tail_control_mass = _get(prob, "tail_control_surface_mass", units="kg")
    tail_actuator_mass = _get(prob, "tail_actuator_mass", units="kg")
    tail_structural_mass = (
        tail_fixed_mass + tail_control_mass
        if np.isfinite(tail_fixed_mass) and np.isfinite(tail_control_mass)
        else np.nan
    )

    for label, data in breakdown_variables.items():
        reference = data["ref"]
        variable = data["var"]

        if variable is None and label == "Crew Mass":
            calculated = crew_mass
        elif variable is None and label == "Tail Structural Mass":
            calculated = tail_structural_mass
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

        validation_override_labels = {
            "Gondola Mass",
            "Fuel Tank/System Mass",
            "Pressure/Air System Mass",
            "Fuel Capacity Mass",
            "Payload Mass",
        }

        mass_role = (
            "REF"
            if label in validation_override_labels
            else ("PRED" if np.isfinite(reference) else "N/A")
        )

        mass_interpretation = (
            "Prescribed A-170 validation/reference quantity"
            if mass_role == "REF"
            else (
                "Predicted mass quantity compared with A-170 reference"
                if mass_role == "PRED"
                else "Predicted quantity; no independent reference available"
            )
        )

        # As above, do not present prescribed REF quantities as independent
        # validation errors.
        if mass_role == "REF":
            error = np.nan

        csv_rows.append(
            [
                "Mass Breakdown",
                mass_role,
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
                mass_interpretation,
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
        + "\n=== Table 4.1. A-170 validation results ==="
        + Fore.RESET
    )
    print("-" * 92)
    print(
        f"{'Role':<8}"
        f"{'Parameter':<30}"
        f"{'Reference':>15}"
        f"{'Our Tool':>15}"
        f"{'% Error':>15}"
    )
    print("-" * 92)

    for data in validation_rows:
        role = data["Role"]
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
            f"{role:<8}"
            f"{parameter:<30}"
            f"{reference_text:>15}"
            f"{calculated_text:>15}"
            f"{error_text:>15}"
        )

    print("-" * 92)
    print(
        "Role key: REF=prescribed reference input, "
        "PRED=independently predicted quantity, PERF=predicted performance."
    )
    print(
        "Percent error is intentionally suppressed for REF quantities because "
        "their values were imposed from the A-170 reference."
    )

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
    # A-170 Complete OEW Closure Audit (Model)
    # -------------------------------------------------------------------------
    audit_vars = [
        "envelope_mass",
        "ballonet_mass",
        "curtain_mass",
        "framework_mass",
        "gondola_mass",
        "fin_mass",
        "tail_fixed_mass",
        "tail_control_surface_mass",
        "tail_actuator_mass",
        "propulsion_mass",
        "power_system_mass",
        "fuel_tank_mass",
        "pressure_system_mass",
        "vms_mass",
        "landing_system_mass",
        "crew_mass",
        "miscellaneous_mass",
        "weight_margin_mass",
        "owe",
    ]

    print("\n--- A-170 complete OEW closure audit ---")
    component_sum = 0.0
    for name in audit_vars:
        try:
            value = float(np.asarray(prob.get_val(name, units="kg")).flat[0])
            print(f"{name:35s}: {value:10.3f} kg")

            if name != "owe":
                component_sum += value
        except Exception:
            print(f"{name:35s}: {'N/A':>10s}")

    owe = float(np.asarray(prob.get_val("owe", units="kg")).flat[0])
    print("-" * 55)
    print(f"{'Displayed component sum':35s}: {component_sum:10.3f} kg")
    print(f"{'Model OEW':35s}: {owe:10.3f} kg")
    print(f"{'Unaccounted model OEW':35s}: {owe - component_sum:10.3f} kg")

    # -------------------------------------------------------------------------
    # A-170 Reference OEW Closure Audit (Published/Literature Data)
    # -------------------------------------------------------------------------
    reference_components = {
        "Envelope": 678.0,
        "Gondola": 1500.0,
        "Fin": 317.0,
        "Landing": 94.0,
        "Propulsion": 595.0,
        "Power": 98.0,
        "Fuel Tank/System": 42.0,
        "Pressure/Air System": 67.1,
        "Crew": 113.0,
        "Miscellaneous": 75.0,
    }
    reference_component_sum = sum(reference_components.values())
    reference_owe = 3908.0

    print("\n--- A-170 reference OEW closure audit ---")
    print(f"Reference listed components : {reference_component_sum:.2f} kg")
    print(f"Reference OEW               : {reference_owe:.2f} kg")
    print(
        f"Reference unaccounted mass  : "
        f"{reference_owe - reference_component_sum:.2f} kg"
    )

    # Optional XDSM export. Disabled by default because it requires LaTeX and
    # is documentation output rather than part of the numerical validation.
    if GENERATE_XDSM:
        write_xdsm(
            prob,
            filename=r"A170_Airship_Sizing_xdsm",
            out_format="pdf",
            show_browser=True,
            quiet=False,
            output_side="left",
            include_indepvarcomps=True,
            class_names=False,
        )

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


    # Optional XDSM export. Disabled by default because it requires LaTeX and
    # is documentation output rather than part of the numerical validation.
    if GENERATE_XDSM:
        write_xdsm(
            prob,
            filename=r"A170_Airship_Sizing_xdsm",
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
    # Explain the analysis boundary before printing numerical results. This is
    # especially useful for reviewers who are not OpenMDAO specialists.
    print_variable_role_guide()
    role_map_path = export_variable_role_map()
    print(f"\nA-170 variable-role map saved to: {role_map_path}")

    # 1. A-170 baseline/reference VALIDATION case.
    # Known A-170 geometry, mission conditions and installed capacities are
    # intentionally imposed. ADaPT then predicts the coupled outputs.
    baseline_prob = build_problem(
        power_source="conventional_reciprocating",
    )

    print(
        Fore.LIGHTGREEN_EX
        + "\n=== A-170 baseline/reference case ==="
        + Fore.RESET
    )

    run_validation_and_print(
        baseline_prob,
        label="baseline / reference case",
    )

    # 2. Optional separate parameter/design optimization.
    # Disabled for a pure validation run. This optimizer varies only:
    # [BR_TO, C_HT, C_VT, C_L, K, eta_p].
    # It does NOT perform complete clean-sheet sizing because length and
    # fineness ratio remain fixed to the A-170 reference.
    if RUN_OPTIMIZATION:
        opt_prob, result = run_pymoo(
            pop_size=160,
            n_gen=300,
            seed=11,
            power_source="conventional_reciprocating",
        )

        print(
            Fore.LIGHTGREEN_EX
            + "\n=== Optimized parameter-study constraint check ==="
            + Fore.RESET
        )

        buoyancy_constraint = _max_value(opt_prob, "buoyancy_constraint")
        power_constraint = _max_value(opt_prob, "power_constraint", units="W")
        energy_constraint = _max_value(opt_prob, "energy_constraint")

        print(f"mtow [t]:                 {_p(opt_prob, 'mtow', 'kg') / 1000.0:.3f}")
        print(f"ground_roll_distance [m]: {_p(opt_prob, 'ground_roll_distance', 'm'):.2f}")
        print(
            f"buoyancy_constraint [N]:  {buoyancy_constraint:.6f} "
            f"(<= 0 feasible: {_constraint_status(buoyancy_constraint)})"
        )
        print(
            f"power_constraint [W]:     {power_constraint:.6f} "
            f"(<= 0 feasible: {_constraint_status(power_constraint)})"
        )
        print(
            f"energy_constraint [kg]:   {energy_constraint:.6f} "
            f"(<= 0 feasible: {_constraint_status(energy_constraint)})"
        )
        print(f"BR_takeoff [-]:            {_p(opt_prob, 'BR_takeoff'):.6f}")
        print(f"propeller_efficiency [-]:  {_p(opt_prob, 'propeller_efficiency'):.3f}")

    print(
        Fore.LIGHTGREEN_EX
        + "=== A-170 validation run complete ==="
        + Fore.RESET
    )


    print("\n--- Takeoff diagnostics ---")

    takeoff_vars = [
        ("takeoff_speed_calculated", "m/s"),
        ("takeoff_average_speed", "m/s"),
        ("takeoff_thrust_available_used", "N"),
        ("drag_takeoff_avg", "N"),
        ("takeoff_aerodynamic_lift_avg", "N"),
        ("takeoff_friction_force", "N"),
        ("takeoff_accelerated_mass", "kg"),
        ("takeoff_heaviness", "N"),
        ("propeller_diameter", "m"),
    ]

    for name, units in takeoff_vars:
        try:
            value = float(np.atleast_1d(prob.get_val(name, units=units))[0])
            print(f"{name:40s}: {value:12.4f} {units}")
        except Exception:
            pass