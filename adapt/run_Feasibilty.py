# -*- coding: utf-8 -*-
"""
ADaPT UI-facing feasibility and parametric-sweep driver.

This module uses the canonical ``run_MDA.py`` builder so all feasibility maps
evaluate the current coupled ADaPT model rather than recreating Geometry,
Weight, Performance, Propulsion, Power, Battery, or Tank physics externally.

Core conventions
----------------
1. ``AirshipAnalysisGroup`` is built only through ``run_MDA.build_problem``.
2. Current ADaPT feasibility convention is ``g <= 0``.
3. ``installed_shaft_power`` is TOTAL aircraft propulsor shaft power.
4. MTOW, required consumable, battery mass, hydrogen-tank mass and all current
   feasibility constraints are read from their authoritative model components.
5. The feasibility layer adds only study-level limits such as a requested
   ground-roll cap or optional MTOW window.

Author: Musavir Bashir
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import openmdao.api as om

from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.termination import get_termination
from pymoo.core.sampling import Sampling

try:
    from colorama import Fore
except Exception:
    class _F:
        LIGHTGREEN_EX = ""
        RED = ""
        CYAN = ""
        RESET = ""
    Fore = _F()


# Canonical UI/MDA API.
try:
    from run_MDA import build_problem, normalize_config, collect_results
except ImportError:
    from run_MDA_updated import build_problem, normalize_config, collect_results


# =============================================================================
# 1. Default feasibility study
# =============================================================================

BASE_CONFIG: Dict[str, Any] = {
    "power_source": "conventional_reciprocating",
    "airship_type": "non-rigid",
    "landing_system": "conventional",
    "num_steps": 1,

    # Mission
    "payload_kg": 1123.0,
    "range_m": 1_342_100.0,
    "cruise_alt_m": 914.0,
    "cruise_speed_mps": 19.5,
    "max_operating_altitude_m": 3000.0,

    # Geometry
    "length_m": 53.4,
    "fineness_ratio": 4.0,
    "tail_volume_coeff_horizontal": 0.066,
    "tail_volume_coeff_vertical": 0.059,
    "tail_coefficient_method": "user",

    # Installed capacities / crew
    "installed_consumable_capacity_kg": 599.0,
    "n_crew": 1,

    # Mechanical propulsion — TOTAL aircraft installed shaft power
    "installed_shaft_power_W": 268_000.0,
    "n_engine": 2,
    "propeller_efficiency": 0.75,

    # Aerodynamics / buoyancy
    "BR_takeoff": 0.83,
    "BR_landing": 0.90,
    "lift_coeff": 0.15,
    "drag_coeff_zero": 0.03542,
    "drag_due_to_lift_factor": 0.869,
}

# Study-level constraints.
GROUND_ROLL_MAX_M = 430.0

# Optional whole-aircraft mass window.  Use None to disable either bound.
MTOW_MIN_KG: Optional[float] = 5000.0
MTOW_MAX_KG: Optional[float] = 7000.0

# Optional installed-power oversizing limit.
POWER_MARGIN_CAP_W: Optional[float] = None

# Optional gross-envelope volume limit.
MAX_ENVELOPE_VOLUME_M3: Optional[float] = None

FAILED_OBJECTIVE = 1.0e12
FAILED_CONSTRAINT = 1.0e6


# =============================================================================
# 2. Journal-quality plotting
# =============================================================================

ELSEVIER_COL_W_CM = 7.5
CM_TO_IN = 1.0 / 2.54


def set_journal_style(
    width_cm: float = ELSEVIER_COL_W_CM,
    aspect: float = 0.85,
    base_font: float = 8.0,
):
    width_in = width_cm * CM_TO_IN
    height_in = width_in * aspect

    mpl.rcParams.update(
        {
            "figure.figsize": (width_in, height_in),
            "figure.dpi": 150,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "font.size": base_font,
            "axes.titlesize": base_font,
            "axes.labelsize": base_font,
            "xtick.labelsize": base_font - 1,
            "ytick.labelsize": base_font - 1,
            "legend.fontsize": base_font - 1,
            "font.family": "serif",
            "mathtext.fontset": "dejavuserif",
            "lines.linewidth": 1.0,
            "lines.markersize": 4.0,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.25,
        }
    )
    return width_in, height_in


def fig_ax(width_cm: float = ELSEVIER_COL_W_CM, aspect: float = 0.85):
    set_journal_style(width_cm=width_cm, aspect=aspect, base_font=8.0)
    fig, ax = plt.subplots(constrained_layout=True)
    return fig, ax


def save_figure(fig, outbase: str, png: bool = True, pdf: bool = True):
    if pdf:
        fig.savefig(outbase + ".pdf")
    if png:
        fig.savefig(outbase + ".png", dpi=600)


# =============================================================================
# 3. Generic OpenMDAO helpers
# =============================================================================

def _array(prob: om.Problem, name: str, units: Optional[str] = None) -> np.ndarray:
    value = prob.get_val(name, units=units)
    return np.asarray(value, dtype=float).reshape(-1)


def _get(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        a = _array(prob, name, units=units)
        return float(a[0]) if a.size else float(default)
    except Exception:
        return float(default)


def _max_value(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        a = _array(prob, name, units=units)
        a = a[np.isfinite(a)]
        return float(np.max(a)) if a.size else float(default)
    except Exception:
        return float(default)


def _first_available(
    prob: om.Problem,
    names: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in names:
        value = _get(prob, name, units=units, default=np.nan)
        if np.isfinite(value):
            return value
    return float(default)


def _maximum_available(
    prob: om.Problem,
    names: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in names:
        value = _max_value(prob, name, units=units, default=np.nan)
        if np.isfinite(value):
            return value
    return float(default)


def _set_if_present(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> bool:
    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
        return True
    except Exception:
        return False


def _set_vector_if_present(
    prob: om.Problem,
    name: str,
    value: float,
    n: int,
    units: Optional[str] = None,
) -> bool:
    return _set_if_present(
        prob,
        name,
        np.full(int(n), float(value)),
        units=units,
    )


# =============================================================================
# 4. Feasibility optimization variables
# =============================================================================

# Current Performance computes the aerodynamic CL required for equilibrium.
# Therefore ``lift_coeff`` is retained as a model input but is not used as a
# feasibility optimizer design variable.
#
# x = [
#   BR_takeoff,
#   tail_volume_coeff_horizontal,
#   tail_volume_coeff_vertical,
#   drag_due_to_lift_factor,
#   propeller_efficiency,
# ]

DV_NAMES = (
    "BR_takeoff",
    "tail_volume_coeff_horizontal",
    "tail_volume_coeff_vertical",
    "drag_due_to_lift_factor",
    "propeller_efficiency",
)

DEFAULT_LOWER_BOUNDS = np.array(
    [0.50, 0.05, 0.04, 0.45, 0.70],
    dtype=float,
)

DEFAULT_UPPER_BOUNDS = np.array(
    [0.98, 0.09, 0.08, 1.00, 0.90],
    dtype=float,
)


def get_bounds(
    lower: Optional[Sequence[float]] = None,
    upper: Optional[Sequence[float]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    lb = np.array(
        DEFAULT_LOWER_BOUNDS if lower is None else lower,
        dtype=float,
        copy=True,
    )
    ub = np.array(
        DEFAULT_UPPER_BOUNDS if upper is None else upper,
        dtype=float,
        copy=True,
    )

    if lb.size != len(DV_NAMES) or ub.size != len(DV_NAMES):
        raise ValueError(
            f"Bounds must contain {len(DV_NAMES)} values in the order {DV_NAMES}."
        )
    if np.any(~np.isfinite(lb)) or np.any(~np.isfinite(ub)):
        raise ValueError("All feasibility-optimization bounds must be finite.")
    if np.any(lb >= ub):
        raise ValueError("Every lower bound must be smaller than its upper bound.")

    return lb, ub


def set_x(prob: om.Problem, x: Sequence[float]) -> None:
    x = np.asarray(x, dtype=float).reshape(-1)
    if x.size != len(DV_NAMES):
        raise ValueError(
            f"Expected {len(DV_NAMES)} design variables; received {x.size}."
        )

    prob.set_val("BR_takeoff", x[0])
    prob.set_val("tail_volume_coeff_horizontal", x[1])
    prob.set_val("tail_volume_coeff_vertical", x[2])
    prob.set_val("drag_due_to_lift_factor", x[3])
    prob.set_val("propeller_efficiency", x[4])


def get_x(prob: om.Problem) -> np.ndarray:
    return np.array(
        [
            _get(prob, "BR_takeoff"),
            _get(prob, "tail_volume_coeff_horizontal"),
            _get(prob, "tail_volume_coeff_vertical"),
            _get(prob, "drag_due_to_lift_factor"),
            _get(prob, "propeller_efficiency"),
        ],
        dtype=float,
    )


class OMInitialSampling(Sampling):
    def __init__(self, x0: Sequence[float], jitter: float = 0.06):
        super().__init__()
        self.x0 = np.asarray(x0, dtype=float).copy()
        self.jitter = float(jitter)

    def _do(self, problem, n_samples, **kwargs):
        lb = np.asarray(problem.xl, dtype=float)
        ub = np.asarray(problem.xu, dtype=float)

        pop = np.random.uniform(lb, ub, size=(n_samples, lb.size))
        pop[0, :] = np.clip(self.x0, lb, ub)

        k = min(5, n_samples - 1)
        if k > 0:
            idx = np.random.choice(np.arange(1, n_samples), size=k, replace=False)
            width = ub - lb
            pop[idx] = np.clip(
                self.x0
                + self.jitter
                * width
                * (np.random.rand(k, lb.size) - 0.5),
                lb,
                ub,
            )
        return pop


# =============================================================================
# 5. Current ADaPT constraint handling
# =============================================================================

MODEL_CONSTRAINTS = (
    "buoyancy_constraint",
    "power_constraint",
    "energy_constraint",
    "lift_constraint",
    "ground_constraint",
    "landing_constraint",
    "ballast_constraint",
    "landing_BR_constraint",
)


def active_model_constraints(prob: om.Problem) -> Tuple[str, ...]:
    active = []
    for name in MODEL_CONSTRAINTS:
        value = _max_value(prob, name, default=np.nan)
        if np.isfinite(value):
            active.append(name)
    return tuple(active)


def _required_power_W(prob: om.Problem) -> float:
    return _maximum_available(
        prob,
        ("required_shaft_power", "shaft_power", "required_power"),
        units="W",
        default=np.nan,
    )


def _installed_power_W(prob: om.Problem) -> float:
    return _get(prob, "installed_shaft_power", "W", default=np.nan)


def _ground_roll_m(prob: om.Problem) -> float:
    return _first_available(
        prob,
        ("takeoff_ground_roll", "ground_roll_distance"),
        units="m",
        default=np.nan,
    )


def _gross_volume_m3(prob: om.Problem) -> float:
    return _first_available(
        prob,
        ("gross_volume", "geometry.gross_volume"),
        units="m**3",
        default=np.nan,
    )


def study_constraint_vector(
    prob: om.Problem,
    model_constraints: Sequence[str],
    *,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
) -> Tuple[np.ndarray, Tuple[str, ...]]:
    """
    Return all model + study constraints in the common ``g <= 0`` convention.
    """
    values = []
    names = []

    for name in model_constraints:
        value = _max_value(prob, name, default=np.nan)
        values.append(value if np.isfinite(value) else FAILED_CONSTRAINT)
        names.append(name)

    mtow = _get(prob, "mtow", "kg", default=np.nan)

    if mtow_min_kg is not None:
        values.append(
            float(mtow_min_kg) - mtow
            if np.isfinite(mtow)
            else FAILED_CONSTRAINT
        )
        names.append("mtow_lower_constraint_kg")

    if mtow_max_kg is not None:
        values.append(
            mtow - float(mtow_max_kg)
            if np.isfinite(mtow)
            else FAILED_CONSTRAINT
        )
        names.append("mtow_upper_constraint_kg")

    if ground_roll_max_m is not None:
        ground_roll = _ground_roll_m(prob)
        values.append(
            ground_roll - float(ground_roll_max_m)
            if np.isfinite(ground_roll)
            else FAILED_CONSTRAINT
        )
        names.append("ground_roll_limit_constraint_m")

    if power_margin_cap_W is not None:
        required = _required_power_W(prob)
        installed = _installed_power_W(prob)
        margin = (
            installed - required
            if np.isfinite(installed) and np.isfinite(required)
            else np.nan
        )
        values.append(
            margin - float(power_margin_cap_W)
            if np.isfinite(margin)
            else FAILED_CONSTRAINT
        )
        names.append("power_margin_cap_constraint_W")

    if max_envelope_volume_m3 is not None:
        volume = _gross_volume_m3(prob)
        values.append(
            volume - float(max_envelope_volume_m3)
            if np.isfinite(volume)
            else FAILED_CONSTRAINT
        )
        names.append("volume_cap_constraint_m3")

    return np.asarray(values, dtype=float), tuple(names)


def evaluate(
    prob: om.Problem,
    model_constraints: Sequence[str],
    *,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
) -> Tuple[float, np.ndarray]:
    """
    Feasibility-search objective and constraints.

    The objective preserves the original intent: find a short-ground-roll,
    moderate-buoyancy configuration.  Feasibility itself is controlled only by
    the explicit current-model and study constraints.
    """
    try:
        prob.run_model()
    except Exception:
        n_extra = (
            int(mtow_min_kg is not None)
            + int(mtow_max_kg is not None)
            + int(ground_roll_max_m is not None)
            + int(power_margin_cap_W is not None)
            + int(max_envelope_volume_m3 is not None)
        )
        return (
            FAILED_OBJECTIVE,
            np.full(len(model_constraints) + n_extra, FAILED_CONSTRAINT),
        )

    ground_roll = _ground_roll_m(prob)
    br = _get(prob, "BR_takeoff", default=np.nan)

    if not np.isfinite(ground_roll):
        ground_roll = 1.0e6
    if not np.isfinite(br):
        br = 1.0

    if ground_roll_max_m is not None and ground_roll_max_m > 0:
        normalized_gr = ground_roll / float(ground_roll_max_m)
        violation = max(0.0, ground_roll - float(ground_roll_max_m)) / float(
            ground_roll_max_m
        )
    else:
        normalized_gr = ground_roll / 430.0
        violation = 0.0

    objective = (
        normalized_gr
        + 0.2 * br
        + 20.0 * violation
        + 100.0 * violation**2
    )

    g, _ = study_constraint_vector(
        prob,
        model_constraints,
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
    )

    return float(objective), g


# =============================================================================
# 6. pymoo wrapper
# =============================================================================

class AirshipPymooProblem(ElementwiseProblem):
    def __init__(
        self,
        prob: om.Problem,
        model_constraints: Sequence[str],
        *,
        lower: Optional[Sequence[float]] = None,
        upper: Optional[Sequence[float]] = None,
        ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
        mtow_min_kg: Optional[float] = MTOW_MIN_KG,
        mtow_max_kg: Optional[float] = MTOW_MAX_KG,
        power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
        max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
    ):
        lb, ub = get_bounds(lower, upper)

        n_extra = (
            int(mtow_min_kg is not None)
            + int(mtow_max_kg is not None)
            + int(ground_roll_max_m is not None)
            + int(power_margin_cap_W is not None)
            + int(max_envelope_volume_m3 is not None)
        )

        super().__init__(
            n_var=len(DV_NAMES),
            n_obj=1,
            n_constr=len(model_constraints) + n_extra,
            xl=lb,
            xu=ub,
        )

        self.prob = prob
        self.model_constraints = tuple(model_constraints)
        self.ground_roll_max_m = ground_roll_max_m
        self.mtow_min_kg = mtow_min_kg
        self.mtow_max_kg = mtow_max_kg
        self.power_margin_cap_W = power_margin_cap_W
        self.max_envelope_volume_m3 = max_envelope_volume_m3

    def _evaluate(self, x, out, *args, **kwargs):
        try:
            set_x(self.prob, x)
            objective, g = evaluate(
                self.prob,
                self.model_constraints,
                ground_roll_max_m=self.ground_roll_max_m,
                mtow_min_kg=self.mtow_min_kg,
                mtow_max_kg=self.mtow_max_kg,
                power_margin_cap_W=self.power_margin_cap_W,
                max_envelope_volume_m3=self.max_envelope_volume_m3,
            )
        except Exception:
            objective = FAILED_OBJECTIVE
            n_extra = (
                int(self.mtow_min_kg is not None)
                + int(self.mtow_max_kg is not None)
                + int(self.ground_roll_max_m is not None)
                + int(self.power_margin_cap_W is not None)
                + int(self.max_envelope_volume_m3 is not None)
            )
            g = np.full(
                len(self.model_constraints) + n_extra,
                FAILED_CONSTRAINT,
            )

        out["F"] = objective
        out["G"] = g


def _select_best_from_result(res):
    X = getattr(res, "X", None)
    if X is not None:
        return X if np.ndim(X) == 1 else X[0], "res.X"

    if hasattr(res, "pop") and res.pop is not None:
        pop = res.pop
        Xp = pop.get("X")
        Fp = pop.get("F").reshape(-1)
        CVp = pop.get("CV").reshape(-1)
        idx = np.lexsort((Fp, CVp))
        return Xp[idx[0]], "res.pop"

    if hasattr(res, "history") and res.history:
        best = None
        for algorithm in res.history:
            pop = getattr(algorithm, "pop", None)
            if pop is None:
                continue
            Xp = pop.get("X")
            Fp = pop.get("F").reshape(-1)
            CVp = pop.get("CV").reshape(-1)
            idx = np.lexsort((Fp, CVp))[0]
            candidate = (CVp[idx], Fp[idx], Xp[idx])
            if (
                best is None
                or candidate[0] < best[0]
                or (candidate[0] == best[0] and candidate[1] < best[1])
            ):
                best = candidate
        if best is not None:
            return best[2], "history"

    raise RuntimeError(
        "pymoo returned no candidate. Check feasibility, bounds, "
        "population size and generation count."
    )


# =============================================================================
# 7. Single-point feasibility optimizer
# =============================================================================

def optimize_current_point(
    prob: om.Problem,
    *,
    x0: Optional[Sequence[float]] = None,
    pop_size: int = 60,
    n_gen: int = 80,
    seed: int = 11,
    jitter: float = 0.05,
    lower_bounds: Optional[Sequence[float]] = None,
    upper_bounds: Optional[Sequence[float]] = None,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
):
    """Optimize the active feasibility variables for the problem's current point."""
    prob.run_model()

    model_constraints = active_model_constraints(prob)

    if x0 is None:
        x0 = get_x(prob)

    lb, ub = get_bounds(lower_bounds, upper_bounds)
    x0 = np.clip(np.asarray(x0, dtype=float), lb, ub)

    moo_problem = AirshipPymooProblem(
        prob,
        model_constraints,
        lower=lb,
        upper=ub,
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
    )

    algorithm = DE(
        pop_size=int(pop_size),
        sampling=OMInitialSampling(x0, jitter=jitter),
    )
    termination = get_termination("n_gen", int(n_gen))

    result = minimize(
        moo_problem,
        algorithm,
        termination,
        seed=int(seed),
        verbose=False,
    )

    X, source = _select_best_from_result(result)
    X = np.asarray(X, dtype=float).reshape(-1)

    set_x(prob, X)
    prob.run_model()

    return X, source, result, model_constraints


# =============================================================================
# 8. Payload × range feasibility sweep
# =============================================================================

def run_sweep(
    payload_grid,
    range_list_km,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    pop_size: int = 100,
    n_gen: int = 120,
    seed: int = 11,
    optimize_each_point: bool = True,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    save_csv: str = "sweep_results.csv",
):
    c = normalize_config(BASE_CONFIG if cfg is None else {**BASE_CONFIG, **cfg})
    prob = build_problem(c)
    prob.run_model()

    x0 = get_x(prob)

    all_rows = []
    series = {}

    for range_km in range_list_km:
        range_m = float(range_km) * 1000.0

        series[range_km] = {
            "payloads": [],
            "mtow": [],
            "consumable": [],
            "battery": [],
            "tank": [],
            "gr": [],
            "pow_margin": [],
            "maxcv": [],
            "feasible": [],
        }

        x_init = x0.copy()

        for payload_kg in payload_grid:
            prob.set_val("payload", float(payload_kg), units="kg")
            prob.set_val("range", range_m, units="m")
            prob.run_model()

            model_constraints = active_model_constraints(prob)

            if optimize_each_point:
                X, _, _, model_constraints = optimize_current_point(
                    prob,
                    x0=x_init,
                    pop_size=pop_size,
                    n_gen=n_gen,
                    seed=seed,
                    jitter=0.05,
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )
                x_init = X

            g, constraint_names = study_constraint_vector(
                prob,
                model_constraints,
                ground_roll_max_m=ground_roll_max_m,
                mtow_min_kg=mtow_min_kg,
                mtow_max_kg=mtow_max_kg,
            )

            maxcv = float(np.max(g)) if g.size else float("-inf")
            feasible = bool(maxcv <= 0.0)

            mtow = _get(prob, "mtow", "kg")
            owe = _get(prob, "owe", "kg")
            consumable = _first_available(
                prob,
                (
                    "required_consumable_mass",
                    "fuel_mass",
                    "mission_consumable_mass_used",
                ),
                units="kg",
                default=np.nan,
            )
            battery = _first_available(
                prob,
                ("required_battery_mass", "battery_mass"),
                units="kg",
                default=np.nan,
            )
            tank = _first_available(
                prob,
                ("hydrogen_tank_mass", "tank_mass"),
                units="kg",
                default=np.nan,
            )

            ground_roll = _ground_roll_m(prob)
            required_W = _required_power_W(prob)
            installed_W = _installed_power_W(prob)
            power_margin_kW = (
                (installed_W - required_W) / 1000.0
                if np.isfinite(installed_W) and np.isfinite(required_W)
                else np.nan
            )

            S = series[range_km]
            S["payloads"].append(float(payload_kg))
            S["mtow"].append(mtow)
            S["consumable"].append(consumable)
            S["battery"].append(battery)
            S["tank"].append(tank)
            S["gr"].append(ground_roll)
            S["pow_margin"].append(power_margin_kW)
            S["maxcv"].append(maxcv)
            S["feasible"].append(feasible)

            row = {
                "range_km": float(range_km),
                "payload_kg": float(payload_kg),
                "mtow_kg": mtow,
                "owe_kg": owe,
                "required_consumable_mass_kg": consumable,
                "required_battery_mass_kg": battery,
                "hydrogen_tank_mass_kg": tank,
                "ground_roll_m": ground_roll,
                "required_shaft_power_kW": (
                    required_W / 1000.0 if np.isfinite(required_W) else np.nan
                ),
                "installed_shaft_power_kW": (
                    installed_W / 1000.0 if np.isfinite(installed_W) else np.nan
                ),
                "power_margin_kW": power_margin_kW,
                "max_constraint_violation": maxcv,
                "feasible": feasible,
            }

            for name, value in zip(constraint_names, g):
                row[name] = float(value)

            all_rows.append(row)

    if all_rows:
        with open(save_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(all_rows[0].keys()),
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(all_rows)

        print(
            Fore.LIGHTGREEN_EX
            + f"Saved sweep results -> {save_csv}"
            + Fore.RESET
        )

    prob.cleanup()
    return series


# =============================================================================
# 9. Payload × range plots
# =============================================================================

def plot_sweep(
    series,
    title_prefix: str = "ADaPT",
    outfile_prefix: str = "payload_range_sweep",
):
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.grid": True,
            "grid.linestyle": "--",
            "grid.alpha": 0.35,
            "lines.linewidth": 2.5,
            "lines.markersize": 6,
        }
    )

    ranges = sorted(series.keys())
    colors = plt.cm.tab10(np.linspace(0, 1, max(6, len(ranges))))

    fig, axs = plt.subplots(1, 3, figsize=(18, 5.2), constrained_layout=True)

    ax = axs[0]
    for i, range_km in enumerate(ranges):
        S = series[range_km]
        ax.plot(
            S["payloads"],
            S["mtow"],
            marker="o",
            color=colors[i],
            label=f"Range: {range_km:g} km",
        )
    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("MTOW [kg]")
    ax.set_title("(a) MTOW sensitivity")

    ax = axs[1]
    any_consumable = False
    for i, range_km in enumerate(ranges):
        S = series[range_km]
        y = np.asarray(S["consumable"], dtype=float)
        if np.isfinite(y).any():
            any_consumable = True
            ax.plot(
                S["payloads"],
                y,
                marker="o",
                color=colors[i],
                label=f"Range: {range_km:g} km",
            )
    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Required consumable [kg]")
    ax.set_title(
        "(b) Consumable requirement"
        + ("" if any_consumable else " (N/A)")
    )

    ax = axs[2]
    any_battery = False
    for i, range_km in enumerate(ranges):
        S = series[range_km]
        y = np.asarray(S["battery"], dtype=float)
        if np.isfinite(y).any():
            any_battery = True
            ax.plot(
                S["payloads"],
                y,
                marker="o",
                color=colors[i],
                label=f"Range: {range_km:g} km",
            )
    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Required battery mass [kg]")
    ax.set_title(
        "(c) Battery requirement"
        + ("" if any_battery else " (N/A)")
    )

    handles, labels = axs[0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=min(6, len(labels)),
        )

    fig.suptitle(
        f"{title_prefix}: Payload & Range Feasibility",
        fontsize=16,
        y=1.02,
    )
    fig.savefig(
        f"{outfile_prefix}_lines.png",
        dpi=160,
        bbox_inches="tight",
    )
    plt.close(fig)

    payloads = np.unique(
        np.concatenate(
            [np.asarray(series[r]["payloads"], dtype=float) for r in ranges]
        )
    )

    def grid_of(key):
        M = np.full((len(ranges), len(payloads)), np.nan)
        for j, range_km in enumerate(ranges):
            S = series[range_km]
            mapping = {
                float(p): k
                for k, p in enumerate(S["payloads"])
            }
            for i, payload in enumerate(payloads):
                k = mapping.get(float(payload))
                if k is not None:
                    M[j, i] = S[key][k]
        return M

    GR = grid_of("gr")
    CV = grid_of("maxcv")
    PM = grid_of("pow_margin")

    fig, ax = plt.subplots(figsize=(7.6, 5.8))
    im = ax.imshow(
        CV,
        origin="lower",
        aspect="auto",
        extent=[
            payloads.min(),
            payloads.max(),
            min(ranges),
            max(ranges),
        ],
        cmap="coolwarm",
    )
    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Range [km]")
    ax.set_title("Feasibility: maximum constraint value")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("max(g), feasible ≤ 0")

    try:
        ax.contour(
            payloads,
            ranges,
            CV,
            levels=[0.0],
            colors="black",
            linewidths=2,
        )
    except Exception:
        pass

    fig.savefig(
        f"{outfile_prefix}_feasibility.png",
        dpi=160,
        bbox_inches="tight",
    )
    plt.close(fig)

    if np.isfinite(PM).any():
        fig, ax = plt.subplots(figsize=(7.6, 5.8))
        im = ax.imshow(
            PM,
            origin="lower",
            aspect="auto",
            extent=[
                payloads.min(),
                payloads.max(),
                min(ranges),
                max(ranges),
            ],
            cmap="viridis",
        )
        ax.set_xlabel("Payload [kg]")
        ax.set_ylabel("Range [km]")
        ax.set_title("Installed power margin")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Installed − required [kW]")
        fig.savefig(
            f"{outfile_prefix}_powermargin.png",
            dpi=160,
            bbox_inches="tight",
        )
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.6, 5.8))
    im = ax.imshow(
        GR,
        origin="lower",
        aspect="auto",
        extent=[
            payloads.min(),
            payloads.max(),
            min(ranges),
            max(ranges),
        ],
        cmap="viridis",
    )
    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Range [km]")
    ax.set_title(
        f"Ground roll [m] (black line = {GROUND_ROLL_MAX_M:g} m)"
    )

    try:
        cs = ax.contour(
            payloads,
            ranges,
            GR,
            levels=[GROUND_ROLL_MAX_M],
            colors="black",
            linewidths=2,
        )
        ax.clabel(
            cs,
            fmt={GROUND_ROLL_MAX_M: f"{GROUND_ROLL_MAX_M:g} m"},
            inline=True,
            fontsize=10,
        )
    except Exception:
        pass

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Ground roll [m]")
    fig.savefig(
        f"{outfile_prefix}_groundroll.png",
        dpi=160,
        bbox_inches="tight",
    )
    plt.close(fig)


# =============================================================================
# 10. Payload × speed feasibility map
# =============================================================================

def run_payload_speed_feasibility(
    payload_grid,
    speed_grid_ms,
    range_m,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    pop_size: int = 60,
    n_gen: int = 80,
    seed: int = 11,
    optimize_each_point: bool = True,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    save_csv: str = "fig14_payload_speed.csv",
):
    """
    Generate a payload-speed feasibility map.

    The plotted value is the maximum current constraint value:

        max(g) <= 0  -> feasible
        max(g) >  0  -> infeasible
    """
    c = normalize_config(BASE_CONFIG if cfg is None else {**BASE_CONFIG, **cfg})
    prob = build_problem(c)
    prob.run_model()

    x0 = get_x(prob)

    rows = []
    CV = np.full(
        (len(payload_grid), len(speed_grid_ms)),
        np.nan,
    )

    n_steps = int(c["num_steps"])

    for i, payload_kg in enumerate(payload_grid):
        x_init = x0.copy()

        for j, speed_mps in enumerate(speed_grid_ms):
            prob.set_val("payload", float(payload_kg), units="kg")
            prob.set_val("range", float(range_m), units="m")
            _set_vector_if_present(
                prob,
                "cruise_speed",
                float(speed_mps),
                n_steps,
                units="m/s",
            )

            prob.run_model()
            model_constraints = active_model_constraints(prob)

            if optimize_each_point:
                X, _, _, model_constraints = optimize_current_point(
                    prob,
                    x0=x_init,
                    pop_size=pop_size,
                    n_gen=n_gen,
                    seed=seed,
                    jitter=0.05,
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )
                x_init = X

            g, constraint_names = study_constraint_vector(
                prob,
                model_constraints,
                ground_roll_max_m=ground_roll_max_m,
                mtow_min_kg=mtow_min_kg,
                mtow_max_kg=mtow_max_kg,
            )

            maxcv = float(np.max(g)) if g.size else float("-inf")
            CV[i, j] = maxcv

            required_W = _required_power_W(prob)
            volume = _gross_volume_m3(prob)

            row = {
                "payload_kg": float(payload_kg),
                "speed_mps": float(speed_mps),
                "max_constraint_value": maxcv,
                "feasible": bool(maxcv <= 0.0),
                "required_shaft_power_kW": (
                    required_W / 1000.0
                    if np.isfinite(required_W)
                    else np.nan
                ),
                "gross_volume_m3": volume,
                "mtow_kg": _get(prob, "mtow", "kg"),
                "ground_roll_m": _ground_roll_m(prob),
            }

            for name, value in zip(constraint_names, g):
                row[name] = float(value)

            rows.append(row)

    if rows:
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)

        with open(save_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)

        print(
            Fore.LIGHTGREEN_EX
            + f"Saved payload-speed feasibility CSV -> {save_csv}"
            + Fore.RESET
        )

    prob.cleanup()
    return CV


def plot_fig14_payload_speed(
    payload_grid,
    speed_grid_ms,
    CV,
    outbase: str = "Fig14_payload_speed_feasibility",
):
    fig, ax = fig_ax(width_cm=7.5, aspect=0.95)

    finite = np.isfinite(CV)
    if finite.any():
        vmin = np.nanpercentile(CV[finite], 5)
        vmax = np.nanpercentile(CV[finite], 95)
        vmin = min(vmin, -1.0e-6)
        vmax = max(vmax, 1.0e-6)
    else:
        vmin, vmax = -1.0, 1.0

    im = ax.imshow(
        CV,
        origin="lower",
        aspect="auto",
        extent=[
            np.min(speed_grid_ms),
            np.max(speed_grid_ms),
            np.min(payload_grid),
            np.max(payload_grid),
        ],
        cmap="coolwarm",
        vmin=vmin,
        vmax=vmax,
    )

    try:
        cs = ax.contour(
            speed_grid_ms,
            payload_grid,
            CV,
            levels=[0.0],
            colors="k",
            linewidths=1.2,
        )
        ax.clabel(
            cs,
            fmt={0.0: "g = 0"},
            inline=True,
            fontsize=mpl.rcParams["font.size"] - 1,
        )
    except Exception:
        pass

    ax.set_xlabel("Cruise speed [m/s]")
    ax.set_ylabel("Payload [kg]")
    ax.grid(False)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Maximum constraint value, feasible ≤ 0")

    save_figure(fig, outbase, png=True, pdf=True)
    plt.close(fig)

    print(
        Fore.LIGHTGREEN_EX
        + f"Saved payload-speed feasibility map -> {outbase}.pdf/.png"
        + Fore.RESET
    )


# =============================================================================
# 11. Altitude × cruise-fraction power/volume/feasibility slice
# =============================================================================

def run_altitude_power_volume_slice(
    max_alt_grid_m,
    cruise_frac_grid,
    payload_kg,
    speed_ms,
    range_m,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    optimize_at_each_point: bool = False,
    pop_size: int = 60,
    n_gen: int = 80,
    seed: int = 11,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    save_csv: str = "fig16_altitude_power_volume.csv",
):
    """
    Sweep maximum operating altitude and cruise-altitude fraction.

    Returns
    -------
    PkW : ndarray
        Peak required shaft power [kW].
    Vm3 : ndarray
        Current gross envelope volume [m^3].
    CV : ndarray
        Maximum current constraint value; <= 0 is feasible.
    """
    c = normalize_config(BASE_CONFIG if cfg is None else {**BASE_CONFIG, **cfg})
    c["payload_kg"] = float(payload_kg)
    c["range_m"] = float(range_m)
    c["cruise_speed_mps"] = float(speed_ms)

    prob = build_problem(c)
    prob.run_model()

    x0 = get_x(prob)

    PkW = np.full(
        (len(cruise_frac_grid), len(max_alt_grid_m)),
        np.nan,
    )
    Vm3 = np.full_like(PkW, np.nan, dtype=float)
    CV = np.full_like(PkW, np.nan, dtype=float)

    rows = []
    n_steps = int(c["num_steps"])

    for i, frac in enumerate(cruise_frac_grid):
        x_init = x0.copy()

        for j, hmax in enumerate(max_alt_grid_m):
            hcr = float(frac) * float(hmax)

            prob.set_val("payload", float(payload_kg), units="kg")
            prob.set_val("range", float(range_m), units="m")

            _set_vector_if_present(
                prob,
                "cruise_speed",
                float(speed_ms),
                n_steps,
                units="m/s",
            )
            _set_vector_if_present(
                prob,
                "cruise_altp",
                hcr,
                n_steps,
                units="m",
            )

            # Current canonical Group/Weight/Geometry interfaces may expose one
            # or more of these names depending on the active component version.
            for name in (
                "max_operating_altitude",
                "max_altitude",
                "maximum_altitude",
                "max_altp",
            ):
                _set_if_present(prob, name, float(hmax), units="m")

            prob.run_model()
            model_constraints = active_model_constraints(prob)

            if optimize_at_each_point:
                X, _, _, model_constraints = optimize_current_point(
                    prob,
                    x0=x_init,
                    pop_size=pop_size,
                    n_gen=n_gen,
                    seed=seed,
                    jitter=0.05,
                    ground_roll_max_m=ground_roll_max_m,
                    mtow_min_kg=mtow_min_kg,
                    mtow_max_kg=mtow_max_kg,
                )
                x_init = X

            g, constraint_names = study_constraint_vector(
                prob,
                model_constraints,
                ground_roll_max_m=ground_roll_max_m,
                mtow_min_kg=mtow_min_kg,
                mtow_max_kg=mtow_max_kg,
            )

            maxcv = float(np.max(g)) if g.size else float("-inf")
            required_W = _required_power_W(prob)
            volume = _gross_volume_m3(prob)

            PkW[i, j] = (
                required_W / 1000.0
                if np.isfinite(required_W)
                else np.nan
            )
            Vm3[i, j] = volume
            CV[i, j] = maxcv

            row = {
                "max_alt_m": float(hmax),
                "cruise_fraction": float(frac),
                "cruise_alt_m": hcr,
                "required_shaft_power_kW": PkW[i, j],
                "gross_volume_m3": Vm3[i, j],
                "mtow_kg": _get(prob, "mtow", "kg"),
                "max_constraint_value": maxcv,
                "feasible": bool(maxcv <= 0.0),
            }

            for name, value in zip(constraint_names, g):
                row[name] = float(value)

            rows.append(row)

    if rows:
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)

        with open(save_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)

        print(
            Fore.LIGHTGREEN_EX
            + f"Saved altitude-power-volume CSV -> {save_csv}"
            + Fore.RESET
        )

    prob.cleanup()
    return PkW, Vm3, CV


def plot_fig16_altitude_power_volume(
    max_alt_grid_m,
    cruise_frac_grid,
    PkW,
    Vm3,
    CV,
    outbase: str = "Fig16_altitude_power_volume",
):
    set_journal_style(width_cm=15.0, aspect=0.55, base_font=8.0)
    fig, axs = plt.subplots(1, 2, constrained_layout=True)

    X = np.asarray(max_alt_grid_m, dtype=float) / 1000.0
    Y = np.asarray(cruise_frac_grid, dtype=float)

    ax = axs[0]
    im1 = ax.imshow(
        PkW,
        origin="lower",
        aspect="auto",
        extent=[X.min(), X.max(), Y.min(), Y.max()],
        cmap="viridis",
    )
    try:
        ax.contour(
            X,
            Y,
            CV,
            levels=[0.0],
            colors="w",
            linewidths=1.1,
        )
    except Exception:
        pass
    ax.set_xlabel("Maximum operating altitude [km]")
    ax.set_ylabel("Cruise altitude / maximum altitude [-]")
    cbar1 = fig.colorbar(im1, ax=ax)
    cbar1.set_label("Required shaft power [kW]")

    ax = axs[1]
    im2 = ax.imshow(
        Vm3,
        origin="lower",
        aspect="auto",
        extent=[X.min(), X.max(), Y.min(), Y.max()],
        cmap="plasma",
    )
    try:
        ax.contour(
            X,
            Y,
            CV,
            levels=[0.0],
            colors="w",
            linewidths=1.1,
        )
    except Exception:
        pass
    ax.set_xlabel("Maximum operating altitude [km]")
    ax.set_ylabel("Cruise altitude / maximum altitude [-]")
    cbar2 = fig.colorbar(im2, ax=ax)
    cbar2.set_label("Gross envelope volume [m$^3$]")

    save_figure(fig, outbase, png=True, pdf=True)
    plt.close(fig)

    print(
        Fore.LIGHTGREEN_EX
        + f"Saved altitude-power-volume figure -> {outbase}.pdf/.png"
        + Fore.RESET
    )


# =============================================================================
# 12. UI-facing single-point feasibility API
# =============================================================================

def run_feasibility_once(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    optimize: bool = False,
    pop_size: int = 60,
    n_gen: int = 80,
    seed: int = 11,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = MTOW_MAX_KG,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
) -> Dict[str, Any]:
    """
    Evaluate one vehicle/mission point and return a UI-ready feasibility result.

    If ``optimize=True``, the local feasibility variables are optimized before
    the final result is collected.
    """
    c = normalize_config(BASE_CONFIG if cfg is None else {**BASE_CONFIG, **cfg})
    prob = build_problem(c)
    prob.run_model()

    model_constraints = active_model_constraints(prob)

    best_x = None
    optimization_result = None

    if optimize:
        best_x, _, optimization_result, model_constraints = optimize_current_point(
            prob,
            pop_size=pop_size,
            n_gen=n_gen,
            seed=seed,
            ground_roll_max_m=ground_roll_max_m,
            mtow_min_kg=mtow_min_kg,
            mtow_max_kg=mtow_max_kg,
            power_margin_cap_W=power_margin_cap_W,
            max_envelope_volume_m3=max_envelope_volume_m3,
        )

    g, names = study_constraint_vector(
        prob,
        model_constraints,
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
    )

    max_g = float(np.max(g)) if g.size else float("-inf")
    feasible = bool(max_g <= 0.0)

    mda_results = collect_results(prob, c)

    constraint_rows = [
        {
            "Name": name,
            "Value": float(value),
            "Feasible": bool(value <= 0.0),
        }
        for name, value in zip(names, g)
    ]

    return {
        "problem": prob,
        "config": c,
        "feasible": feasible,
        "max_constraint_value": max_g,
        "constraint_names": names,
        "constraint_vector": g,
        "constraint_rows": constraint_rows,
        "best_x": best_x,
        "optimization_result": optimization_result,
        "mda_results": mda_results,
    }


# =============================================================================
# 13. Direct execution example
# =============================================================================

if __name__ == "__main__":
    try:
        # ------------------------------------------------------------------
        # Payload × range
        # ------------------------------------------------------------------
        payload_grid = np.linspace(600.0, 2000.0, 8)
        range_list_km = [445, 828, 1231, 1624, 2017]

        series = run_sweep(
            payload_grid,
            range_list_km,
            cfg=BASE_CONFIG,
            pop_size=80,
            n_gen=120,
            seed=11,
            optimize_each_point=True,
            save_csv="sweep_results.csv",
        )

        plot_sweep(
            series,
            title_prefix="ADaPT",
            outfile_prefix="payload_range_sweep",
        )

        # ------------------------------------------------------------------
        # Payload × speed
        # ------------------------------------------------------------------
        payload_grid_14 = np.linspace(600.0, 2000.0, 17)
        speed_grid_ms_14 = np.linspace(12.0, 35.0, 24)
        range_m_14 = 1_342_100.0

        CV14 = run_payload_speed_feasibility(
            payload_grid_14,
            speed_grid_ms_14,
            range_m_14,
            cfg=BASE_CONFIG,
            pop_size=60,
            n_gen=80,
            seed=11,
            optimize_each_point=True,
            save_csv="fig14_payload_speed.csv",
        )

        plot_fig14_payload_speed(
            payload_grid_14,
            speed_grid_ms_14,
            CV14,
            outbase="Fig14_payload_speed_feasibility",
        )

        # ------------------------------------------------------------------
        # Maximum altitude × cruise-altitude fraction
        # ------------------------------------------------------------------
        max_alt_grid_m_16 = np.linspace(2000.0, 12000.0, 26)
        cruise_frac_grid_16 = np.linspace(0.25, 1.0, 16)

        PkW16, Vm316, CV16 = run_altitude_power_volume_slice(
            max_alt_grid_m_16,
            cruise_frac_grid_16,
            payload_kg=1123.0,
            speed_ms=19.5,
            range_m=1_342_100.0,
            cfg=BASE_CONFIG,
            optimize_at_each_point=False,
            pop_size=60,
            n_gen=80,
            seed=11,
            save_csv="fig16_altitude_power_volume.csv",
        )

        plot_fig16_altitude_power_volume(
            max_alt_grid_m_16,
            cruise_frac_grid_16,
            PkW16,
            Vm316,
            CV16,
            outbase="Fig16_altitude_power_volume",
        )

        print(
            Fore.LIGHTGREEN_EX
            + "=== ADaPT feasibility studies complete ==="
            + Fore.RESET
        )

    except Exception as exc:
        print(Fore.RED + f"ERROR: {exc}" + Fore.RESET)
        sys.exit(1)
