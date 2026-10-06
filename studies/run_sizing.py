# -*- coding: utf-8 -*-
"""
ADAPT — SIZING MODE WITH MDF XDSM
================================

Purpose
-------
Design an airship from mission requirements.

The user specifies:
- payload,
- range,
- cruise speed,
- cruise altitude,
- architecture and technology assumptions.

ADAPT internally varies:
- hull length,
- fineness ratio,
- installed shaft power,
- take-off buoyancy ratio,
- horizontal tail-volume coefficient,
- vertical tail-volume coefficient.

For every candidate design, the OpenMDAO model is converged as a
Multidisciplinary Feasible (MDF) analysis. The external pymoo differential-
evolution algorithm supplies the design variables; the OpenMDAO nonlinear
solver converges the coupled MDA.

Two XDSM products can be generated:
1. A detailed OpenMDAO connectivity XDSM using omxdsm.
2. A manually structured MDF architecture XDSM using pyXDSM, explicitly
   showing the sizing driver and MDA converger.

The only section a non-expert user normally edits is USER INPUTS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

try:
    from pymoo.algorithms.soo.nonconvex.de import DE
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination
except ImportError as exc:
    raise ImportError(
        "Sizing mode requires pymoo. Install it with:\n"
        "    pip install pymoo"
    ) from exc

try:
    from .adapt_mode_common import (
        apply_architecture_defaults,
        apply_common_configuration,
        apply_mission,
        build_problem,
        export_results,
        generate_xdsm,
        max_value,
        print_summary,
        scalar,
    )
except ImportError:
    from adapt_mode_common import (
        apply_architecture_defaults,
        apply_common_configuration,
        apply_mission,
        build_problem,
        export_results,
        generate_xdsm,
        max_value,
        print_summary,
        scalar,
    )

# Optional reference-airship definitions. These provide convenient starting
# missions/configurations without changing the generic sizing formulation.
from airships.A170 import A170
from airships.ZeppelinNT import ZeppelinNT


# =============================================================================
# USER INPUTS — AIRSHIP SIZING FROM MISSION REQUIREMENTS
# =============================================================================
#
# Sizing remains a CLEAN-SHEET mission-driven problem.  The airship files are
# used only when REFERENCE_AIRSHIP is selected below; they provide the mission
# and fixed technology/configuration assumptions.  Geometry such as length and
# fineness ratio is NOT copied from the reference aircraft because those are
# sizing design variables in this driver.
#
# Choices:
#     None         -> use the generic mission immediately below
#     A170         -> use mission/configuration data from airship/A170.py
#     ZeppelinNT   -> use mission/configuration data from airship/ZeppelinNT.py



# REFERENCE_AIRSHIP = None
REFERENCE_AIRSHIP = A170
# REFERENCE_AIRSHIP = ZeppelinNT


# -------------------------------------------------------------------------
# Generic mission/configuration used when REFERENCE_AIRSHIP is None
# -------------------------------------------------------------------------

POWER_SOURCE = "conventional_reciprocating"
NUM_STEPS = 1

# Mission requirements
PAYLOAD_KG = 400.0
RANGE_KM = 900.0
CRUISE_SPEED_MS = 22.0
CRUISE_ALTITUDE_M = 914.4
CRUISE_DISA_K = 0.0

# Fixed configuration and technology assumptions
N_CREW = 1.0
N_ENGINE = 2.0
PROPELLER_EFFICIENCY = 0.78
LIFT_COEFF = 0.15
DRAG_DUE_TO_LIFT_FACTOR = 0.869
BR_LANDING = 0.90
BALLAST_MASS_KG = 0.0

BATTERY_SPECIFIC_ENERGY_WHKG = 350.0
SOLAR_AREA_M2 = 300.0
SOLAR_IRRADIANCE_WM2 = 600.0


# -------------------------------------------------------------------------
# Optional reference-airship mission/configuration
# -------------------------------------------------------------------------
#
# IMPORTANT:
# The selected reference airship supplies only quantities that are FIXED in
# this sizing problem.  Its known length, diameter, fineness ratio, installed
# power and BR_takeoff are intentionally NOT imposed because the sizing driver
# optimizes those quantities.
#
if REFERENCE_AIRSHIP is not None:
    POWER_SOURCE = REFERENCE_AIRSHIP.power_source

    PAYLOAD_KG = REFERENCE_AIRSHIP.payload_kg
    RANGE_KM = REFERENCE_AIRSHIP.range_km
    CRUISE_SPEED_MS = REFERENCE_AIRSHIP.cruise_speed_ms
    CRUISE_ALTITUDE_M = REFERENCE_AIRSHIP.cruise_altitude_m
    CRUISE_DISA_K = REFERENCE_AIRSHIP.cruise_disa_K

    N_CREW = REFERENCE_AIRSHIP.n_crew
    N_ENGINE = REFERENCE_AIRSHIP.n_engine
    PROPELLER_EFFICIENCY = REFERENCE_AIRSHIP.propeller_efficiency
    LIFT_COEFF = REFERENCE_AIRSHIP.lift_coeff
    DRAG_DUE_TO_LIFT_FACTOR = REFERENCE_AIRSHIP.drag_due_to_lift_factor
    BR_LANDING = REFERENCE_AIRSHIP.BR_landing
    BALLAST_MASS_KG = REFERENCE_AIRSHIP.ballast_mass_kg


# Design-variable bounds
BOUNDS = {
    "length_m": (45.0, 110.0),
    "fineness_ratio": (3.0, 6.0),
    "installed_shaft_power_kW": (100.0, 1000.0),
    "BR_takeoff": (0.75, 0.99),
    "tail_volume_coeff_horizontal": (0.04, 0.10),
    "tail_volume_coeff_vertical": (0.035, 0.09),
}

# Optimizer controls
POPULATION_SIZE = 80
GENERATIONS = 120
RANDOM_SEED = 11

# MDF formulation
FORMULATION = "mdf"

# Output file
OUTPUT_CSV = Path(__file__).resolve().parent / "adapt_sizing_results.csv"

# XDSM controls
GENERATE_DETAILED_XDSM = True
GENERATE_MDF_ARCHITECTURE_XDSM = True

# Detailed omxdsm output
XDSM_FORMAT = "html"
XDSM_SHOW_BROWSER = True
XDSM_INCLUDE_INDEPVARS = True

# Manual pyXDSM output
MANUAL_XDSM_CLEANUP = False
MANUAL_XDSM_WRITE_SPECS = False

XDSM_OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "adapt_sizing_xdsm"
)


# =============================================================================
# INTERNAL SIZING DEFINITIONS
# =============================================================================

DESIGN_NAMES = tuple(BOUNDS.keys())

LOWER = np.array(
    [BOUNDS[name][0] for name in DESIGN_NAMES],
    dtype=float,
)

UPPER = np.array(
    [BOUNDS[name][1] for name in DESIGN_NAMES],
    dtype=float,
)

# Every required constraint must exist and satisfy g <= 0.
REQUIRED_CONSTRAINTS = (
    ("buoyancy_constraint", None),
    ("power_constraint", "W"),
    ("lift_constraint", None),
    ("ground_constraint", None),
)

# These may be absent for architectures for which they are not applicable.
OPTIONAL_CONSTRAINTS = (
    ("energy_constraint", None),
    ("volume_constraint", None),
)

ACTIVE_CONSTRAINTS = REQUIRED_CONSTRAINTS + OPTIONAL_CONSTRAINTS


# =============================================================================
# DESIGN-VARIABLE HANDLING
# =============================================================================

def set_design(prob, x: np.ndarray) -> None:
    """Apply one candidate sizing vector to the OpenMDAO problem."""
    x = np.asarray(x, dtype=float).reshape(-1)

    if x.size != len(DESIGN_NAMES):
        raise ValueError(
            f"Expected {len(DESIGN_NAMES)} variables, received {x.size}."
        )

    prob.set_val("length", x[0], units="m")
    prob.set_val("fineness_ratio", x[1])
    prob.set_val("installed_shaft_power", x[2], units="kW")
    prob.set_val("BR_takeoff", x[3])
    prob.set_val("tail_volume_coeff_horizontal", x[4])
    prob.set_val("tail_volume_coeff_vertical", x[5])


def evaluate_candidate(
    prob,
    x: np.ndarray,
    *,
    debug: bool = False,
) -> tuple[float, np.ndarray]:
    """
    Evaluate one candidate using the converged MDF model.

    Returns
    -------
    objective
        MTOW in kg.
    constraints
        Pymoo inequality vector following g <= 0.
    """
    try:
        set_design(prob, x)

        # The attached OpenMDAO nonlinear solver converges the coupled MDA.
        prob.run_model()

        mtow = scalar(
            prob,
            "mtow",
            units="kg",
            default=np.nan,
        )

        if not np.isfinite(mtow) or mtow <= 0.0:
            raise RuntimeError(
                f"Invalid MTOW returned by ADAPT: {mtow!r}"
            )

        constraint_values: list[float] = []

        for name, units in REQUIRED_CONSTRAINTS:
            value = max_value(
                prob,
                name,
                units=units,
                default=np.nan,
            )

            if not np.isfinite(value):
                raise RuntimeError(
                    f"Required constraint '{name}' is unavailable or "
                    "non-finite."
                )

            constraint_values.append(float(value))

        for name, units in OPTIONAL_CONSTRAINTS:
            value = max_value(
                prob,
                name,
                units=units,
                default=np.nan,
            )

            # Architecture-inactive optional constraints are feasible.
            if not np.isfinite(value):
                value = -1.0

            constraint_values.append(float(value))

        constraints = np.asarray(
            constraint_values,
            dtype=float,
        )

        if constraints.size != len(ACTIVE_CONSTRAINTS):
            raise RuntimeError(
                "Constraint-vector length mismatch: "
                f"expected {len(ACTIVE_CONSTRAINTS)}, "
                f"received {constraints.size}."
            )

        return float(mtow), constraints

    except Exception as exc:
        if debug:
            print("\nCandidate evaluation failed")
            print("-" * 78)
            print(f"Design vector: {np.asarray(x, dtype=float)}")
            print(f"Reason: {type(exc).__name__}: {exc}")

        return (
            1.0e12,
            np.full(
                len(ACTIVE_CONSTRAINTS),
                1.0e9,
                dtype=float,
            ),
        )


def verify_sizing_interface(prob) -> None:
    """
    Verify the objective and constraints before starting optimization.
    """
    print("\nVerifying ADAPT MDF sizing interface")
    print("-" * 78)

    mtow = scalar(
        prob,
        "mtow",
        units="kg",
        default=np.nan,
    )

    if not np.isfinite(mtow):
        raise RuntimeError(
            "Sizing objective 'mtow' is unavailable."
        )

    print(f"{'mtow':<38} available")

    for name in DESIGN_NAMES:
        print(f"{name:<38} configured")

    for name, units in REQUIRED_CONSTRAINTS:
        value = max_value(
            prob,
            name,
            units=units,
            default=np.nan,
        )

        if not np.isfinite(value):
            raise RuntimeError(
                f"Required sizing constraint '{name}' is unavailable."
            )

        print(
            f"{name:<38} "
            f"available, current value={value:.6g}"
        )

    for name, units in OPTIONAL_CONSTRAINTS:
        value = max_value(
            prob,
            name,
            units=units,
            default=np.nan,
        )

        if np.isfinite(value):
            status = f"available, current value={value:.6g}"
        else:
            status = "architecture-inactive"

        print(f"{name:<38} {status}")

    print("-" * 78)


# =============================================================================
# PYMOO PROBLEM
# =============================================================================

class ADAPTSizingProblem(ElementwiseProblem):
    """
    Pymoo wrapper around one persistent ADAPT MDF OpenMDAO problem.
    """

    def __init__(self, prob):
        try:
            super().__init__(
                n_var=len(DESIGN_NAMES),
                n_obj=1,
                n_ieq_constr=len(ACTIVE_CONSTRAINTS),
                xl=LOWER,
                xu=UPPER,
            )
        except TypeError:
            # Compatibility with older pymoo releases.
            super().__init__(
                n_var=len(DESIGN_NAMES),
                n_obj=1,
                n_constr=len(ACTIVE_CONSTRAINTS),
                xl=LOWER,
                xu=UPPER,
            )

        self.prob = prob

    def _evaluate(self, x, out, *args, **kwargs):
        objective, constraints = evaluate_candidate(
            self.prob,
            x,
        )

        out["F"] = objective
        out["G"] = constraints


def select_best(result) -> tuple[np.ndarray, bool]:
    """
    Select the best feasible candidate.

    If no feasible candidate exists, return the least-infeasible candidate
    and mark it as infeasible.
    """
    pop = getattr(result, "pop", None)

    if getattr(result, "X", None) is not None:
        x = np.asarray(
            result.X,
            dtype=float,
        )

        x = x if x.ndim == 1 else x[0]
        return x, True

    if pop is None:
        raise RuntimeError(
            "pymoo returned neither a solution nor a population."
        )

    X = np.asarray(
        pop.get("X"),
        dtype=float,
    )

    F = np.asarray(
        pop.get("F"),
        dtype=float,
    ).reshape(-1)

    CV = np.asarray(
        pop.get("CV"),
        dtype=float,
    ).reshape(-1)

    finite = (
        np.all(np.isfinite(X), axis=1)
        & np.isfinite(F)
        & np.isfinite(CV)
    )

    if not np.any(finite):
        raise RuntimeError(
            "The final population contains no finite candidate."
        )

    X = X[finite]
    F = F[finite]
    CV = CV[finite]

    feasible = CV <= 1.0e-10

    if np.any(feasible):
        feasible_indices = np.flatnonzero(feasible)
        local_best = np.argmin(F[feasible])
        index = feasible_indices[local_best]
        return X[index], True

    index = np.lexsort((F, CV))[0]
    return X[index], False


def final_constraint_audit(
    prob,
) -> tuple[bool, dict[str, float]]:
    """Perform an independent final feasibility check."""
    values: dict[str, float] = {}
    all_feasible = True

    optional_names = {
        name
        for name, _ in OPTIONAL_CONSTRAINTS
    }

    for name, units in ACTIVE_CONSTRAINTS:
        value = max_value(
            prob,
            name,
            units=units,
            default=np.nan,
        )

        values[name] = (
            float(value)
            if np.isfinite(value)
            else np.nan
        )

        if not np.isfinite(value):
            if name not in optional_names:
                all_feasible = False
        elif value > 1.0e-8:
            all_feasible = False

    return all_feasible, values


# =============================================================================
# MANUAL MDF XDSM
# =============================================================================

def latex_safe_text(value: str) -> str:
    """Escape common LaTeX-sensitive characters in plain text."""
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
    }

    result = str(value)

    for old, new in replacements.items():
        result = result.replace(old, new)

    return result


def generate_manual_mdf_xdsm(
    *,
    filename: str,
    output_dir: Path,
    power_source: str,
    cleanup: bool = False,
    write_system_specs: bool = False,
) -> Optional[Path]:
    """
    Generate the manual MDF sizing architecture using pyXDSM.

    The formatting follows the same conservative pattern as the user's
    verified pyXDSM example:
    - raw LaTeX text entries;
    - tuple labels for multi-line system names;
    - label_width=1 on all connections;
    - cleanup=False by default;
    - simple system identifiers.
    """
    try:
        from pyxdsm.XDSM import (
            XDSM,
            OPT,
            SOLVER,
            FUNC,
        )
    except ImportError:
        print(
            "\nManual MDF XDSM skipped: pyXDSM is not installed.\n"
            "Install it with:\n"
            "    pip install pyxdsm"
        )
        return None

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_stem = output_dir / filename
    power_source_label = latex_safe_text(power_source)

    x = XDSM()

    # -------------------------------------------------------------------------
    # SYSTEM BLOCKS
    # -------------------------------------------------------------------------

    x.add_system(
        "Driver",
        OPT,
        (
            r"\text{\huge Sizing}",
            r"\text{\huge Driver}",
        ),
    )

    x.add_system(
        "Converger",
        SOLVER,
        (
            r"\text{\huge MDA}",
            r"\text{\huge Converger}",
        ),
    )

    x.add_system(
        "Atmos",
        FUNC,
        (
            r"\text{\huge Operating}",
            r"\text{\huge Conditions}",
        ),
    )

    x.add_system(
        "Geometry",
        FUNC,
        (
            r"\text{\huge Airship}",
            r"\text{\huge Geometry}",
        ),
    )

    x.add_system(
        "Weight",
        FUNC,
        (
            r"\text{\huge Weight}",
            r"\text{\huge Analysis}",
        ),
    )

    x.add_system(
        "Performance",
        FUNC,
        (
            r"\text{\huge Airship}",
            r"\text{\huge Performance}",
        ),
    )

    x.add_system(
        "Propulsion",
        FUNC,
        (
            r"\text{\huge Propulsion}",
            r"\text{\huge System}",
        ),
    )

    x.add_system(
        "Power",
        FUNC,
        (
            r"\text{\huge Power}",
            r"\text{\huge System}",
        ),
    )

    x.add_system(
        "Consumable",
        FUNC,
        (
            r"\text{\huge Energy and}",
            r"\text{\huge Consumable}",
            r"\text{\huge System}",
        ),
    )

    x.add_system(
        "Closure",
        SOLVER,
        (
            r"\text{\huge Mass--Energy}",
            r"\text{\huge Closure}",
        ),
    )

    # -------------------------------------------------------------------------
    # PROCESS ORDER
    # -------------------------------------------------------------------------

    x.add_process(
        [
            "Driver",
            "Converger",
            "Atmos",
            "Geometry",
            "Weight",
            "Performance",
            "Propulsion",
            "Power",
            "Consumable",
            "Closure",
            "Weight",
            "Performance",
            "Converger",
            "Driver",
        ],
        arrow=True,
    )

    # -------------------------------------------------------------------------
    # DRIVER AND MDA CONVERGER
    # -------------------------------------------------------------------------

    x.connect(
        "Driver",
        "Converger",
        [
            r"\text{\huge Design}",
            r"\text{\huge Variables,}",
            r"\text{\huge Mission}",
            r"\text{\huge Requirements,}",
            r"\text{\huge Architecture}",
        ],
        label_width=1,
    )

    x.connect(
        "Converger",
        "Atmos",
        [
            r"\text{\huge Initial}",
            r"\text{\huge Operating}",
            r"\text{\huge Conditions}",
        ],
        label_width=1,
    )

    x.connect(
        "Converger",
        "Geometry",
        [
            r"\text{\huge Initial}",
            r"\text{\huge Geometry}",
        ],
        label_width=1,
    )

    x.connect(
        "Converger",
        "Weight",
        [
            r"\text{\huge Initial}",
            r"\text{\huge Mass}",
        ],
        label_width=1,
    )

    # -------------------------------------------------------------------------
    # DISCIPLINARY CONNECTIONS
    # -------------------------------------------------------------------------

    x.connect(
        "Atmos",
        "Geometry",
        [
            r"\text{\huge Ambient}",
            r"\text{\huge Conditions}",
        ],
        label_width=1,
    )

    x.connect(
        "Atmos",
        "Performance",
        [
            r"\text{\huge Density,}",
            r"\text{\huge Pressure,}",
            r"\text{\huge Temperature,}",
            r"\text{\huge Speed of Sound}",
        ],
        label_width=1,
    )

    x.connect(
        "Geometry",
        "Weight",
        [
            r"\text{\huge Gross Volume,}",
            r"\text{\huge Wetted Area,}",
            r"\text{\huge Tail Geometry,}",
            r"\text{\huge Envelope Size}",
        ],
        label_width=1,
    )

    x.connect(
        "Geometry",
        "Performance",
        [
            r"\text{\huge Reference Area,}",
            r"\text{\huge Hull Geometry,}",
            r"\text{\huge Fineness Ratio}",
        ],
        label_width=1,
    )

    x.connect(
        "Geometry",
        "Propulsion",
        [
            r"\text{\huge Propulsor}",
            r"\text{\huge Installation}",
        ],
        label_width=1,
    )

    x.connect(
        "Weight",
        "Performance",
        [
            r"\text{\huge Aircraft Mass,}",
            r"\text{\huge Buoyancy Ratio}",
        ],
        label_width=1,
    )

    x.connect(
        "Performance",
        "Propulsion",
        [
            r"\text{\huge Required}",
            r"\text{\huge Shaft Power,}",
            r"\text{\huge Mission Power}",
        ],
        label_width=1,
    )

    x.connect(
        "Performance",
        "Consumable",
        [
            r"\text{\huge Mission Energy,}",
            r"\text{\huge Mission Duration}",
        ],
        label_width=1,
    )

    x.connect(
        "Propulsion",
        "Power",
        [
            r"\text{\huge Rated Power,}",
            r"\text{\huge Shaft Power}",
        ],
        label_width=1,
    )

    x.connect(
        "Power",
        "Consumable",
        [
            r"\text{\huge Fuel or}",
            r"\text{\huge Energy Demand,}",
            r"\text{\huge Efficiency}",
        ],
        label_width=1,
    )

    x.connect(
        "Power",
        "Weight",
        [
            r"\text{\huge Power-System}",
            r"\text{\huge Mass}",
        ],
        label_width=1,
    )

    x.connect(
        "Consumable",
        "Weight",
        [
            r"\text{\huge Fuel Mass,}",
            r"\text{\huge Battery Mass,}",
            r"\text{\huge Tank Mass}",
        ],
        label_width=1,
    )

    x.connect(
        "Weight",
        "Closure",
        [
            r"\text{\huge Calculated}",
            r"\text{\huge Take-Off Mass}",
        ],
        label_width=1,
    )

    x.connect(
        "Consumable",
        "Closure",
        [
            r"\text{\huge Required}",
            r"\text{\huge Consumable Mass}",
        ],
        label_width=1,
    )

    x.connect(
        "Closure",
        "Weight",
        [
            r"\text{\huge Updated Mass,}",
            r"\text{\huge Mass Residual}",
        ],
        label_width=1,
    )

    x.connect(
        "Closure",
        "Performance",
        [
            r"\text{\huge Updated}",
            r"\text{\huge Aircraft Mass}",
        ],
        label_width=1,
    )

    x.connect(
        "Closure",
        "Converger",
        [
            r"\text{\huge Mass Residual,}",
            r"\text{\huge Energy Residual,}",
            r"\text{\huge Convergence}",
            r"\text{\huge Status}",
        ],
        label_width=1,
    )

    x.connect(
        "Converger",
        "Driver",
        [
            r"\text{\huge MTOW,}",
            r"\text{\huge Objective,}",
            r"\text{\huge Constraints,}",
            r"\text{\huge Feasibility}",
        ],
        label_width=1,
    )

    # -------------------------------------------------------------------------
    # EXTERNAL INPUTS
    # -------------------------------------------------------------------------

    x.add_input(
        "Driver",
        [
            r"\text{\huge Mission Requirements}",
            r"\text{\huge -Payload}",
            r"\text{\huge -Range}",
            r"\text{\huge -Cruise Speed}",
            r"\text{\huge -Cruise Altitude}",
            r"\text{\huge Technology Assumptions}",
            r"\text{\huge Design-Variable Bounds}",
        ],
        stack=True,
    )

    x.add_input(
        "Power",
        [
            r"\text{\huge Propulsion}",
            r"\text{\huge Architecture}",
            rf"\text{{\huge {power_source_label}}}",
        ],
        stack=True,
    )

    # -------------------------------------------------------------------------
    # WRITE OUTPUT
    # -------------------------------------------------------------------------

    try:
        x.write(
            str(file_stem),
            cleanup=cleanup,
        )

        if write_system_specs:
            specs_stem = (
                output_dir
                / f"{filename}_system_specs"
            )

            x.write_sys_specs(
                str(specs_stem)
            )

        pdf_path = file_stem.with_suffix(".pdf")

        print("\nManual MDF XDSM generation completed.")
        print("Mode: sizing")
        print(f"Power source: {power_source}")
        print(f"File stem: {file_stem}")

        return pdf_path

    except Exception as exc:
        print("\nManual MDF XDSM generation failed.")
        print(f"Reason: {type(exc).__name__}: {exc}")
        print(
            "The generated LaTeX files are preserved when cleanup=False."
        )
        return None


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    # The MDF wrapper must be selected in adapt_mode_common.build_problem().
    prob = build_problem(
        power_source=POWER_SOURCE,
        num_steps=NUM_STEPS,
        use_prescribed_consumable_capacity=False,
        setup_check=False,
        formulation=FORMULATION,
    )

    # If the backend exposes airship_type as a promoted model input, use the
    # selected reference-airship structural type.  This is deliberately
    # best-effort so the generic sizing driver remains compatible with older
    # ADaPT model versions.
    if REFERENCE_AIRSHIP is not None:
        try:
            prob.set_val("airship_type", REFERENCE_AIRSHIP.airship_type)
        except Exception:
            pass

    apply_mission(
        prob,
        payload_kg=PAYLOAD_KG,
        range_km=RANGE_KM,
        cruise_speed_ms=CRUISE_SPEED_MS,
        cruise_altitude_m=CRUISE_ALTITUDE_M,
        cruise_disa_K=CRUISE_DISA_K,
        num_steps=NUM_STEPS,
    )

    apply_common_configuration(
        prob,
        n_crew=N_CREW,
        n_engine=N_ENGINE,
        propeller_efficiency=PROPELLER_EFFICIENCY,
        lift_coeff=LIFT_COEFF,
        drag_due_to_lift_factor=DRAG_DUE_TO_LIFT_FACTOR,
        BR_landing=BR_LANDING,
        ballast_mass_kg=BALLAST_MASS_KG,
    )

    apply_architecture_defaults(
        prob,
        power_source=POWER_SOURCE,
        num_steps=NUM_STEPS,
        battery_specific_energy_Whkg=(
            BATTERY_SPECIFIC_ENERGY_WHKG
        ),
        solar_area_m2=SOLAR_AREA_M2,
        solar_irradiance_Wm2=(
            SOLAR_IRRADIANCE_WM2
        ),
    )

    # Transparent midpoint design for the first converged MDF evaluation.
    x_mid = 0.5 * (LOWER + UPPER)
    set_design(prob, x_mid)
    prob.run_model()

    verify_sizing_interface(prob)

    print("\nADAPT MDF sizing mode")
    print("=" * 78)
    print(
        f"Mission: payload={PAYLOAD_KG:.1f} kg, "
        f"range={RANGE_KM:.1f} km, "
        f"speed={CRUISE_SPEED_MS:.1f} m/s"
    )
    print(f"Architecture: {POWER_SOURCE}")
    print(f"Formulation: {FORMULATION.upper()}")
    print("Design variables:")

    for name, lower, upper in zip(
        DESIGN_NAMES,
        LOWER,
        UPPER,
    ):
        print(
            f"  {name:<38} "
            f"[{lower:g}, {upper:g}]"
        )

    print("=" * 78)

    pymoo_problem = ADAPTSizingProblem(prob)

    algorithm = DE(
        pop_size=POPULATION_SIZE,
        variant="DE/rand/1/bin",
        CR=0.9,
        F=0.8,
        dither="vector",
        jitter=False,
    )

    result = minimize(
        pymoo_problem,
        algorithm,
        get_termination(
            "n_gen",
            GENERATIONS,
        ),
        seed=RANDOM_SEED,
        verbose=True,
        save_history=False,
    )

    best_x, optimizer_found_feasible = select_best(result)

    if not optimizer_found_feasible:
        print(
            "\nWARNING: pymoo did not identify a fully feasible design. "
            "The least-infeasible candidate will be reported."
        )

    # One final, independent MDF evaluation of the selected design.
    set_design(prob, best_x)
    prob.run_model()

    final_feasible, final_constraints = (
        final_constraint_audit(prob)
    )

    print("\nSelected sizing variables")
    print("-" * 78)

    for name, value in zip(
        DESIGN_NAMES,
        best_x,
    ):
        print(
            f"{name:<38} "
            f"{value:>14.6f}"
        )

    print("\nIndependent final feasibility audit")
    print("-" * 78)

    for name, value in final_constraints.items():
        if np.isfinite(value):
            status = (
                "PASS"
                if value <= 1.0e-8
                else "FAIL"
            )

            print(
                f"{name:<38} "
                f"{value:>14.6g}   "
                f"{status}"
            )
        else:
            print(
                f"{name:<38} "
                f"{'inactive/unavailable':>22}"
            )

    if not final_feasible:
        print(
            "\nWARNING: The selected candidate does not satisfy all "
            "required ADAPT constraints."
        )

    print_summary(
        prob,
        title="ADAPT mission-driven MDF sizing result",
        mode="sizing",
    )

    csv_path = export_results(
        prob,
        output_csv=OUTPUT_CSV,
        mode="sizing",
        power_source=POWER_SOURCE,
    )

    print(f"\nResults saved to: {csv_path}")

    # -------------------------------------------------------------------------
    # XDSM GENERATION — EXECUTED ONLY AFTER THE FINAL CONVERGED DESIGN
    # -------------------------------------------------------------------------

    if GENERATE_DETAILED_XDSM:
        detailed_xdsm_path = generate_xdsm(
            prob,
            filename=(
                f"ADAPT_detailed_sizing_"
                f"{POWER_SOURCE}"
            ),
            output_dir=XDSM_OUTPUT_DIR,
            out_format=XDSM_FORMAT,
            show_browser=False,
            include_indepvarcomps=(
                XDSM_INCLUDE_INDEPVARS
            ),
            class_names=False,
            recurse=True,
        )

        if detailed_xdsm_path is not None:
            print(
                "Detailed OpenMDAO XDSM requested at: "
                f"{detailed_xdsm_path}"
            )

    if GENERATE_MDF_ARCHITECTURE_XDSM:
        manual_xdsm_path = generate_manual_mdf_xdsm(
            filename=(
                f"ADAPT_MDF_sizing_"
                f"{POWER_SOURCE}"
            ),
            output_dir=XDSM_OUTPUT_DIR,
            power_source=POWER_SOURCE,
            cleanup=MANUAL_XDSM_CLEANUP,
            write_system_specs=(
                MANUAL_XDSM_WRITE_SPECS
            ),
        )

        if manual_xdsm_path is not None:
            print(
                "Manual MDF architecture XDSM requested at: "
                f"{manual_xdsm_path}"
            )


if __name__ == "__main__":
    main()