# -*- coding: utf-8 -*-
"""
UI adapter for ADAPT mission-driven airship sizing.

This file contains NO airship physics.

It converts simple GUI inputs into calls to the existing ADAPT sizing
backend and returns GUI-friendly dictionaries/dataframes.

Authoritative sizing implementation:
    adapt/run_sizing.py

Authoritative common MDF/model helpers:
    adapt/adapt_mode_common.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


# ============================================================================
# Repository bootstrap
# ============================================================================

UI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = UI_DIR.parent
STUDIES_DIR = PROJECT_ROOT / "studies"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(STUDIES_DIR) not in sys.path:
    sys.path.insert(1, str(STUDIES_DIR))


# ============================================================================
# Backend imports
# ============================================================================
#
# Actual project structure:
#
#   project/
#       adapt/
#           run_Sizing.py
#
#       studies/
#           adapt_mode_common.py
#           run_sizing.py       <-- mission-driven sizing backend
#
#       ui/
#           run_sizing.py       <-- this GUI adapter
#
# The GUI sizing page uses studies/run_sizing.py because that is the
# mission-driven MDF sizing formulation.
# ============================================================================

try:
    from studies import run_sizing as sizing
    from studies import adapt_mode_common as common

except ImportError as exc:
    raise ImportError(
        "Could not import the ADAPT mission-driven sizing study.\n\n"
        "Expected project structure:\n"
        "  <project>/studies/run_sizing.py\n"
        "  <project>/studies/adapt_mode_common.py\n"
        "  <project>/ui/run_sizing.py"
    ) from exc


# ============================================================================
# User-facing labels
# ============================================================================

POWER_SOURCE_LABELS = {
    "Conventional reciprocating": "conventional_reciprocating",
    "Hydrogen reciprocating": "hydrogen_reciprocating",
    "Hydrogen fuel cell": "hydrogen_fuel_cell",
    "Battery electric": "battery_only",
    "Solar + battery": "solar_battery",
    "Solar regenerative fuel cell": "solar-RFC",
    "Hydrogen hybrid": "hydrogen_hybrid",
    "Solar + hydrogen hybrid": "solar_hydrogen_hybrid",
    "Conventional + battery hybrid": "conventional_battery_hybrid",
}


AIRSHIP_TYPE_LABELS = {
    "Non-rigid": "non-rigid",
    "Semi-rigid": "semi-rigid",
    "Rigid": "rigid",
}


LANDING_SYSTEM_LABELS = {
    "Conventional": "conventional",
}


DEFAULT_BOUNDS = {
    "length_m": (45.0, 110.0),
    "fineness_ratio": (3.0, 6.0),
    "installed_shaft_power_kW": (100.0, 1000.0),
    "BR_takeoff": (0.75, 0.99),
    "tail_volume_coeff_horizontal": (0.04, 0.10),
    "tail_volume_coeff_vertical": (0.035, 0.09),
}


DESIGN_LABELS = {
    "length_m": "Hull length",
    "fineness_ratio": "Fineness ratio",
    "installed_shaft_power_kW": "Installed shaft power",
    "BR_takeoff": "Take-off buoyancy ratio",
    "tail_volume_coeff_horizontal": "Horizontal tail-volume coefficient",
    "tail_volume_coeff_vertical": "Vertical tail-volume coefficient",
}


DESIGN_UNITS = {
    "length_m": "m",
    "fineness_ratio": "-",
    "installed_shaft_power_kW": "kW",
    "BR_takeoff": "-",
    "tail_volume_coeff_horizontal": "-",
    "tail_volume_coeff_vertical": "-",
}


# ============================================================================
# Helpers
# ============================================================================

def _finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        value = float(np.asarray(value).reshape(-1)[0])
        return value if np.isfinite(value) else float(default)
    except Exception:
        return float(default)


def _set_if_present(
    prob,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> bool:
    """
    Use the common backend setter where available.
    """
    if hasattr(common, "set_if_present"):
        return common.set_if_present(
            prob,
            name,
            value,
            units=units,
        )

    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
        return True
    except Exception:
        return False


def _cleanup_problem(prob) -> None:
    """
    Best-effort cleanup of OpenMDAO resources after results are copied.
    """
    if prob is None:
        return

    try:
        prob.cleanup()
    except Exception:
        pass


def _architecture_value(value: str) -> str:
    return POWER_SOURCE_LABELS.get(value, value)


def _airship_type_value(value: str) -> str:
    return AIRSHIP_TYPE_LABELS.get(value, value)


def _landing_system_value(value: str) -> str:
    return LANDING_SYSTEM_LABELS.get(value, value)


# ============================================================================
# Main UI sizing API
# ============================================================================

def run_sizing_ui(
    *,
    # Mission requirements
    payload_kg: float = 400.0,
    range_km: float = 900.0,
    cruise_speed_ms: float = 22.0,
    cruise_altitude_m: float = 914.4,
    cruise_disa_K: float = 0.0,

    # Architecture
    power_source: str = "conventional_reciprocating",
    airship_type: str = "non-rigid",
    landing_system: str = "conventional",

    # Common technology/configuration
    n_crew: float = 1.0,
    n_engine: float = 2.0,
    propeller_efficiency: float = 0.78,
    lift_coeff: float = 0.15,
    drag_due_to_lift_factor: float = 0.869,
    BR_landing: float = 0.90,
    ballast_mass_kg: float = 0.0,

    # Architecture-dependent technology
    battery_specific_energy_Whkg: float = 350.0,
    solar_area_m2: float = 300.0,
    solar_irradiance_Wm2: float = 600.0,

    # Sizing bounds
    bounds: Optional[Dict[str, tuple[float, float]]] = None,

    # Optimizer
    population_size: int = 80,
    generations: int = 120,
    random_seed: int = 11,

    # Model controls
    num_steps: int = 1,

) -> Dict[str, Any]:
    """
    Run the existing ADAPT MDF sizing formulation from GUI inputs.

    No sizing physics is implemented here.
    """

    from pymoo.algorithms.soo.nonconvex.de import DE
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination

    power_source = _architecture_value(power_source)
    airship_type = _airship_type_value(airship_type)
    landing_system = _landing_system_value(landing_system)

    bounds = dict(DEFAULT_BOUNDS if bounds is None else bounds)

    design_names = tuple(DEFAULT_BOUNDS.keys())

    missing = [name for name in design_names if name not in bounds]
    if missing:
        raise ValueError(
            "Missing sizing bounds for: " + ", ".join(missing)
        )

    lower = np.asarray(
        [bounds[name][0] for name in design_names],
        dtype=float,
    )

    upper = np.asarray(
        [bounds[name][1] for name in design_names],
        dtype=float,
    )

    if np.any(~np.isfinite(lower)) or np.any(~np.isfinite(upper)):
        raise ValueError("All sizing bounds must be finite.")

    if np.any(lower >= upper):
        raise ValueError(
            "Each sizing lower bound must be smaller than its upper bound."
        )

    population_size = int(population_size)
    generations = int(generations)
    random_seed = int(random_seed)
    num_steps = int(num_steps)

    if population_size < 4:
        raise ValueError("Population size must be at least 4.")

    if generations < 1:
        raise ValueError("Generations must be at least 1.")

    prob = None

    try:
        # ------------------------------------------------------------------
        # Build authoritative ADAPT model
        # ------------------------------------------------------------------

        prob = common.build_problem(
            power_source=power_source,
            num_steps=num_steps,
            landing_system=landing_system,
            use_prescribed_consumable_capacity=False,
            setup_check=False,
            formulation="direct",
        )

        # Airship structural architecture.
        #
        # Some versions of the common builder expose airship_type directly
        # through the model option; others expose it as a promoted variable.
        # Setting it here is therefore deliberately best-effort and does not
        # create any duplicate physics.
        _set_if_present(
            prob,
            "airship_type",
            airship_type,
        )

        # ------------------------------------------------------------------
        # Mission requirements
        # ------------------------------------------------------------------

        common.apply_mission(
            prob,
            payload_kg=float(payload_kg),
            range_km=float(range_km),
            cruise_speed_ms=float(cruise_speed_ms),
            cruise_altitude_m=float(cruise_altitude_m),
            cruise_disa_K=float(cruise_disa_K),
            num_steps=num_steps,
        )

        # ------------------------------------------------------------------
        # Common configuration
        # ------------------------------------------------------------------

        common.apply_common_configuration(
            prob,
            n_crew=float(n_crew),
            n_engine=float(n_engine),
            propeller_efficiency=float(propeller_efficiency),
            lift_coeff=float(lift_coeff),
            drag_due_to_lift_factor=float(
                drag_due_to_lift_factor
            ),
            BR_landing=float(BR_landing),
            ballast_mass_kg=float(ballast_mass_kg),
        )

        # ------------------------------------------------------------------
        # Architecture-specific technology assumptions
        # ------------------------------------------------------------------

        common.apply_architecture_defaults(
            prob,
            power_source=power_source,
            num_steps=num_steps,
            battery_specific_energy_Whkg=float(
                battery_specific_energy_Whkg
            ),
            solar_area_m2=float(solar_area_m2),
            solar_irradiance_Wm2=float(
                solar_irradiance_Wm2
            ),
        )

        # ------------------------------------------------------------------
        # Initial MDF evaluation at midpoint
        # ------------------------------------------------------------------

        x_mid = 0.5 * (lower + upper)

        sizing.set_design(prob, x_mid)
        prob.run_model()

        sizing.verify_sizing_interface(prob)

        # ------------------------------------------------------------------
        # IMPORTANT
        #
        # ADAPTSizingProblem in the backend uses the backend module's global
        # LOWER/UPPER arrays. The GUI supports editable bounds, so construct
        # a small subclass using the same authoritative evaluate_candidate()
        # function but the GUI-selected bounds.
        # ------------------------------------------------------------------

        try:
            from pymoo.core.problem import ElementwiseProblem
        except ImportError:
            raise ImportError(
                "pymoo is required for ADAPT sizing."
            )

        n_constraints = len(sizing.ACTIVE_CONSTRAINTS)

        class _UISizingProblem(ElementwiseProblem):
            def __init__(self, openmdao_problem):
                try:
                    super().__init__(
                        n_var=len(design_names),
                        n_obj=1,
                        n_ieq_constr=n_constraints,
                        xl=lower,
                        xu=upper,
                    )
                except TypeError:
                    super().__init__(
                        n_var=len(design_names),
                        n_obj=1,
                        n_constr=n_constraints,
                        xl=lower,
                        xu=upper,
                    )

                self.prob = openmdao_problem

            def _evaluate(self, x, out, *args, **kwargs):
                objective, constraints = (
                    sizing.evaluate_candidate(
                        self.prob,
                        x,
                    )
                )

                out["F"] = objective
                out["G"] = constraints

        pymoo_problem = _UISizingProblem(prob)

        algorithm = DE(
            pop_size=population_size,
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
                generations,
            ),
            seed=random_seed,
            verbose=False,
            save_history=False,
        )

        # ------------------------------------------------------------------
        # Select and independently evaluate final design
        # ------------------------------------------------------------------

        best_x, optimizer_found_feasible = (
            sizing.select_best(result)
        )

        sizing.set_design(prob, best_x)
        prob.run_model()

        final_feasible, final_constraints = (
            sizing.final_constraint_audit(prob)
        )

        # ------------------------------------------------------------------
        # Copy all results BEFORE cleanup
        # ------------------------------------------------------------------

        summary = common.collect_summary(prob)

        if hasattr(common, "collect_constraints"):
            all_constraints = common.collect_constraints(prob)
        else:
            all_constraints = dict(final_constraints)

        # Make final audit authoritative for duplicate entries.
        all_constraints.update(final_constraints)

        # ------------------------------------------------------------------
        # Design table
        # ------------------------------------------------------------------

        design_rows = []

        for name, value in zip(design_names, best_x):
            design_rows.append(
                {
                    "Design variable": DESIGN_LABELS[name],
                    "Value": float(value),
                    "Unit": DESIGN_UNITS[name],
                    "Lower bound": float(bounds[name][0]),
                    "Upper bound": float(bounds[name][1]),
                }
            )

        design_df = pd.DataFrame(design_rows)

        # ------------------------------------------------------------------
        # Constraint table
        # ------------------------------------------------------------------

        constraint_rows = []

        for name, value in all_constraints.items():
            value = _safe_float(value)

            if np.isfinite(value):
                status = "PASS" if value <= 1.0e-8 else "FAIL"
            else:
                status = "N/A"

            constraint_rows.append(
                {
                    "Constraint": name,
                    "Value": value,
                    "Status": status,
                }
            )

        constraint_df = pd.DataFrame(constraint_rows)

        # ------------------------------------------------------------------
        # Mass breakdown
        # ------------------------------------------------------------------

        mass_candidates = [
            ("Operating empty weight", "owe_kg"),
            ("Payload", "payload_kg"),
            ("Mission consumable", "consumable_mass_kg"),
            ("Battery", "battery_mass_kg"),
            ("Hydrogen tank", "tank_mass_kg"),
            ("Power system", "power_system_mass_kg"),
            ("Propulsion system", "propulsion_mass_kg"),
        ]

        mass_rows = []

        for label, key in mass_candidates:
            value = _safe_float(summary.get(key))

            if np.isfinite(value) and value > 1.0e-9:
                mass_rows.append(
                    {
                        "Component": label,
                        "Mass [kg]": value,
                    }
                )

        mass_df = pd.DataFrame(mass_rows)

        # ------------------------------------------------------------------
        # Power comparison
        # ------------------------------------------------------------------

        installed_power = _safe_float(
            summary.get("installed_shaft_power_kW")
        )

        required_power = _safe_float(
            summary.get("required_shaft_power_kW")
        )

        power_rows = []

        if np.isfinite(required_power):
            power_rows.append(
                {
                    "Power": "Required shaft power",
                    "Power [kW]": required_power,
                }
            )

        if np.isfinite(installed_power):
            power_rows.append(
                {
                    "Power": "Installed shaft power",
                    "Power [kW]": installed_power,
                }
            )

        power_df = pd.DataFrame(power_rows)

        power_margin_kW = (
            installed_power - required_power
            if (
                np.isfinite(installed_power)
                and np.isfinite(required_power)
            )
            else np.nan
        )

        # ------------------------------------------------------------------
        # Mission summary
        # ------------------------------------------------------------------

        mission = {
            "payload_kg": float(payload_kg),
            "range_km": float(range_km),
            "cruise_speed_ms": float(cruise_speed_ms),
            "cruise_altitude_m": float(cruise_altitude_m),
            "cruise_disa_K": float(cruise_disa_K),
        }

        architecture = {
            "power_source": power_source,
            "airship_type": airship_type,
            "landing_system": landing_system,
            "n_engine": float(n_engine),
            "n_crew": float(n_crew),
        }

        optimizer = {
            "population_size": population_size,
            "generations": generations,
            "random_seed": random_seed,
            "optimizer_found_feasible": bool(
                optimizer_found_feasible
            ),
        }

        return {
            "summary": dict(summary),
            "mission": mission,
            "architecture": architecture,
            "optimizer": optimizer,
            "bounds": bounds,
            "best_x": np.asarray(best_x, dtype=float).copy(),
            "design_names": design_names,
            "design_table": design_df,
            "constraint_table": constraint_df,
            "constraints": dict(all_constraints),
            "mass_table": mass_df,
            "power_table": power_df,
            "power_margin_kW": power_margin_kW,
            "feasible": bool(final_feasible),
            "optimizer_found_feasible": bool(
                optimizer_found_feasible
            ),
            "objective_mtow_kg": _safe_float(
                summary.get("mtow_kg")
            ),
        }

    finally:
        _cleanup_problem(prob)