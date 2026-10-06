# -*- coding: utf-8 -*-
"""
ADaPT UI-facing multidisciplinary optimization driver.

This module reuses the canonical MDA builder from ``run_MDA.py`` so that the
optimization layer does not duplicate OpenMDAO setup or subsystem physics.

Core conventions
----------------
1. ``AirshipAnalysisGroup`` is created only through ``run_MDA.build_problem``.
2. Current ADaPT feasibility convention is ``g <= 0``.
3. ``installed_shaft_power`` is TOTAL aircraft propulsor shaft power.
4. Fuel, hydrogen, battery, tank, propulsion and power-system quantities are
   evaluated by their authoritative ADaPT components.
5. The optimization layer changes only selected system-level design variables
   and reads objective/constraint values from the current coupled model.

Author: Musavir Bashir
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

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


try:
    from run_MDA import build_problem, normalize_config, collect_results
except ImportError:
    from run_MDA_updated import build_problem, normalize_config, collect_results


BASE_CONFIG: Dict[str, Any] = {
    "power_source": "conventional_reciprocating",
    "airship_type": "non-rigid",
    "landing_system": "conventional",
    "num_steps": 1,

    "payload_kg": 1123.0,
    "range_m": 1_342_100.0,
    "cruise_alt_m": 914.0,
    "cruise_speed_mps": 19.5,

    "length_m": 53.4,
    "fineness_ratio": 4.0,
    "tail_volume_coeff_horizontal": 0.066,
    "tail_volume_coeff_vertical": 0.059,
    "tail_coefficient_method": "user",

    "installed_consumable_capacity_kg": 599.0,
    "n_crew": 1,

    # TOTAL aircraft propulsor shaft power.
    "installed_shaft_power_W": 268_000.0,
    "n_engine": 2,
    "propeller_efficiency": 0.75,

    "BR_takeoff": 0.84,
    "BR_landing": 0.90,
    "drag_coeff_zero": 0.03542,
    "drag_due_to_lift_factor": 0.869,
    "lift_coeff": 0.15,
}

GROUND_ROLL_MAX_M = 430.0
POWER_MARGIN_CAP_W = 80_000.0
MAX_ENVELOPE_VOLUME_M3: Optional[float] = None

POWER_MARGIN_PENALTY = 2.0e-5  # kg/(kW^2)

FAILED_OBJECTIVE = 1.0e12
FAILED_CONSTRAINT = 1.0e6


DV_NAMES = (
    "length_m",
    "fineness_ratio",
    "BR_takeoff",
    "tail_volume_coeff_horizontal",
    "tail_volume_coeff_vertical",
    "drag_due_to_lift_factor",
    "propeller_efficiency",
    "installed_shaft_power_kW_total",
)

DEFAULT_LOWER_BOUNDS = np.array(
    [48.0, 3.6, 0.80, 0.055, 0.050, 0.60, 0.72, 220.0],
    dtype=float,
)

DEFAULT_UPPER_BOUNDS = np.array(
    [62.0, 4.6, 0.90, 0.080, 0.075, 0.95, 0.88, 400.0],
    dtype=float,
)


def _array(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
) -> np.ndarray:
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
            f"Bounds must each contain {len(DV_NAMES)} values in the order {DV_NAMES}."
        )
    if np.any(~np.isfinite(lb)) or np.any(~np.isfinite(ub)):
        raise ValueError("All optimization bounds must be finite.")
    if np.any(lb >= ub):
        raise ValueError("Every lower bound must be smaller than its upper bound.")

    return lb, ub


def set_x(prob: om.Problem, x: Sequence[float]) -> None:
    x = np.asarray(x, dtype=float).reshape(-1)
    if x.size != len(DV_NAMES):
        raise ValueError(
            f"Expected {len(DV_NAMES)} design variables; received {x.size}."
        )

    prob.set_val("length", x[0], units="m")
    prob.set_val("fineness_ratio", x[1])
    prob.set_val("BR_takeoff", x[2])
    prob.set_val("tail_volume_coeff_horizontal", x[3])
    prob.set_val("tail_volume_coeff_vertical", x[4])
    prob.set_val("drag_due_to_lift_factor", x[5])
    prob.set_val("propeller_efficiency", x[6])

    # Current convention: total installed aircraft shaft power.
    prob.set_val("installed_shaft_power", x[7] * 1000.0, units="W")


def get_x(prob: om.Problem) -> np.ndarray:
    return np.array(
        [
            _get(prob, "length", "m"),
            _get(prob, "fineness_ratio"),
            _get(prob, "BR_takeoff"),
            _get(prob, "tail_volume_coeff_horizontal"),
            _get(prob, "tail_volume_coeff_vertical"),
            _get(prob, "drag_due_to_lift_factor"),
            _get(prob, "propeller_efficiency"),
            _get(prob, "installed_shaft_power", "kW"),
        ],
        dtype=float,
    )


class OMInitialSampling(Sampling):
    def __init__(self, x0: Sequence[float], jitter: float = 0.08):
        super().__init__()
        self.x0 = np.asarray(x0, dtype=float).copy()
        self.jitter = float(jitter)

    def _do(self, problem, n_samples, **kwargs):
        lb = np.asarray(problem.xl, dtype=float)
        ub = np.asarray(problem.xu, dtype=float)

        pop = np.random.uniform(lb, ub, size=(n_samples, lb.size))
        pop[0, :] = np.clip(self.x0, lb, ub)

        k = min(8, n_samples - 1)
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


def _active_model_constraints(prob: om.Problem) -> Tuple[str, ...]:
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


def evaluate(
    prob: om.Problem,
    active_constraints: Sequence[str],
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
    power_margin_penalty: float = POWER_MARGIN_PENALTY,
) -> Tuple[float, np.ndarray]:
    try:
        prob.run_model()
    except Exception:
        n_extra = (
            int(ground_roll_max_m is not None)
            + int(power_margin_cap_W is not None)
            + int(max_envelope_volume_m3 is not None)
        )
        return (
            FAILED_OBJECTIVE,
            np.full(len(active_constraints) + n_extra, FAILED_CONSTRAINT),
        )

    mtow = _get(prob, "mtow", "kg", default=np.nan)
    if not np.isfinite(mtow):
        n_extra = (
            int(ground_roll_max_m is not None)
            + int(power_margin_cap_W is not None)
            + int(max_envelope_volume_m3 is not None)
        )
        return (
            FAILED_OBJECTIVE,
            np.full(len(active_constraints) + n_extra, FAILED_CONSTRAINT),
        )

    required_W = _required_power_W(prob)
    installed_W = _installed_power_W(prob)

    if np.isfinite(required_W) and np.isfinite(installed_W):
        power_margin_W = installed_W - required_W
        positive_margin_kW = max(power_margin_W, 0.0) / 1000.0
    else:
        power_margin_W = np.nan
        positive_margin_kW = 0.0

    objective = mtow + float(power_margin_penalty) * positive_margin_kW**2

    g = []

    # Current ADaPT model constraints already use g <= 0.
    for name in active_constraints:
        value = _max_value(prob, name, default=np.nan)
        g.append(value if np.isfinite(value) else FAILED_CONSTRAINT)

    if ground_roll_max_m is not None:
        ground_roll = _first_available(
            prob,
            ("takeoff_ground_roll", "ground_roll_distance"),
            units="m",
            default=np.nan,
        )
        g.append(
            ground_roll - float(ground_roll_max_m)
            if np.isfinite(ground_roll)
            else FAILED_CONSTRAINT
        )

    if power_margin_cap_W is not None:
        g.append(
            power_margin_W - float(power_margin_cap_W)
            if np.isfinite(power_margin_W)
            else FAILED_CONSTRAINT
        )

    if max_envelope_volume_m3 is not None:
        volume = _first_available(
            prob,
            ("gross_volume", "geometry.gross_volume"),
            units="m**3",
            default=np.nan,
        )
        g.append(
            volume - float(max_envelope_volume_m3)
            if np.isfinite(volume)
            else FAILED_CONSTRAINT
        )

    return float(objective), np.asarray(g, dtype=float)


class AirshipMDOProblem(ElementwiseProblem):
    def __init__(
        self,
        prob: om.Problem,
        active_constraints: Sequence[str],
        lower: Optional[Sequence[float]] = None,
        upper: Optional[Sequence[float]] = None,
        ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
        power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
        max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
        power_margin_penalty: float = POWER_MARGIN_PENALTY,
    ):
        lb, ub = get_bounds(lower, upper)

        n_extra = (
            int(ground_roll_max_m is not None)
            + int(power_margin_cap_W is not None)
            + int(max_envelope_volume_m3 is not None)
        )

        super().__init__(
            n_var=len(DV_NAMES),
            n_obj=1,
            n_constr=len(active_constraints) + n_extra,
            xl=lb,
            xu=ub,
        )

        self.prob = prob
        self.active_constraints = tuple(active_constraints)
        self.ground_roll_max_m = ground_roll_max_m
        self.power_margin_cap_W = power_margin_cap_W
        self.max_envelope_volume_m3 = max_envelope_volume_m3
        self.power_margin_penalty = float(power_margin_penalty)

    def _evaluate(self, x, out, *args, **kwargs):
        try:
            set_x(self.prob, x)
            objective, g = evaluate(
                self.prob,
                self.active_constraints,
                ground_roll_max_m=self.ground_roll_max_m,
                power_margin_cap_W=self.power_margin_cap_W,
                max_envelope_volume_m3=self.max_envelope_volume_m3,
                power_margin_penalty=self.power_margin_penalty,
            )
        except Exception:
            objective = FAILED_OBJECTIVE
            n_extra = (
                int(self.ground_roll_max_m is not None)
                + int(self.power_margin_cap_W is not None)
                + int(self.max_envelope_volume_m3 is not None)
            )
            g = np.full(
                len(self.active_constraints) + n_extra,
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
        "pymoo returned no candidate. Check model feasibility, bounds, "
        "population size and generation count."
    )


def _constraint_record(
    prob: om.Problem,
    active_constraints: Sequence[str],
    ground_roll_max_m: Optional[float],
    power_margin_cap_W: Optional[float],
    max_envelope_volume_m3: Optional[float],
) -> Dict[str, float]:
    row: Dict[str, float] = {}

    for name in active_constraints:
        row[name] = _max_value(prob, name, default=np.nan)

    ground_roll = _first_available(
        prob,
        ("takeoff_ground_roll", "ground_roll_distance"),
        units="m",
        default=np.nan,
    )
    if ground_roll_max_m is not None:
        row["ground_roll_limit_constraint_m"] = (
            ground_roll - float(ground_roll_max_m)
            if np.isfinite(ground_roll)
            else np.nan
        )

    required_W = _required_power_W(prob)
    installed_W = _installed_power_W(prob)
    margin_W = (
        installed_W - required_W
        if np.isfinite(installed_W) and np.isfinite(required_W)
        else np.nan
    )

    if power_margin_cap_W is not None:
        row["power_margin_cap_constraint_W"] = (
            margin_W - float(power_margin_cap_W)
            if np.isfinite(margin_W)
            else np.nan
        )

    if max_envelope_volume_m3 is not None:
        volume = _first_available(
            prob,
            ("gross_volume", "geometry.gross_volume"),
            units="m**3",
            default=np.nan,
        )
        row["volume_cap_constraint_m3"] = (
            volume - float(max_envelope_volume_m3)
            if np.isfinite(volume)
            else np.nan
        )

    return row


def _save_best_csv(
    path: str | Path,
    prob: om.Problem,
    cfg: Dict[str, Any],
    x: Sequence[float],
    source: str,
    objective: float,
    active_constraints: Sequence[str],
    ground_roll_max_m: Optional[float],
    power_margin_cap_W: Optional[float],
    max_envelope_volume_m3: Optional[float],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    results = collect_results(prob, cfg)
    scalars = results["scalars"]
    outputs = results["outputs"]

    x = np.asarray(x, dtype=float).reshape(-1)

    row: Dict[str, Any] = {
        "result_source": source,
        "objective": float(objective),
    }

    for name, value in zip(DV_NAMES, x):
        row[name] = float(value)

    for key, value in scalars.items():
        if np.isscalar(value) or isinstance(value, str):
            row[key] = value

    for key in (
        "gross_volume_m3",
        "diameter_m",
        "wetted_area_m2",
        "aero_reference_area_m2",
        "propeller_diameter_m",
        "propulsion_mass_kg",
        "power_system_mass_kg",
        "helium_mass_kg",
    ):
        if key in outputs:
            row[key] = outputs[key]

    row.update(
        _constraint_record(
            prob,
            active_constraints,
            ground_roll_max_m,
            power_margin_cap_W,
            max_envelope_volume_m3,
        )
    )

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def run_optimization(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    lower_bounds: Optional[Sequence[float]] = None,
    upper_bounds: Optional[Sequence[float]] = None,
    pop_size: int = 200,
    n_gen: int = 400,
    seed: int = 11,
    jitter: float = 0.08,
    verbose: bool = True,
    ground_roll_max_m: Optional[float] = GROUND_ROLL_MAX_M,
    power_margin_cap_W: Optional[float] = POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = MAX_ENVELOPE_VOLUME_M3,
    power_margin_penalty: float = POWER_MARGIN_PENALTY,
    save_best_csv: Optional[str | Path] = "best_mdo_design.csv",
) -> Dict[str, Any]:
    c = normalize_config(BASE_CONFIG if cfg is None else {**BASE_CONFIG, **cfg})

    prob = build_problem(c)
    prob.run_model()

    x0 = get_x(prob)
    lb, ub = get_bounds(lower_bounds, upper_bounds)
    x0 = np.clip(x0, lb, ub)

    active_constraints = _active_model_constraints(prob)

    mdo_problem = AirshipMDOProblem(
        prob=prob,
        active_constraints=active_constraints,
        lower=lb,
        upper=ub,
        ground_roll_max_m=ground_roll_max_m,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
        power_margin_penalty=power_margin_penalty,
    )

    algorithm = DE(
        pop_size=int(pop_size),
        sampling=OMInitialSampling(x0, jitter=jitter),
    )
    termination = get_termination("n_gen", int(n_gen))

    print(
        Fore.LIGHTGREEN_EX
        + (
            "=== ADaPT multidisciplinary optimization "
            f"(minimum MTOW): pop={pop_size}, gen={n_gen} ==="
        )
        + Fore.RESET
    )

    res = minimize(
        mdo_problem,
        algorithm,
        termination,
        seed=int(seed),
        verbose=bool(verbose),
    )

    X, source = _select_best_from_result(res)
    X = np.asarray(X, dtype=float).reshape(-1)

    set_x(prob, X)
    prob.run_model()

    objective, g = evaluate(
        prob,
        active_constraints,
        ground_roll_max_m=ground_roll_max_m,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
        power_margin_penalty=power_margin_penalty,
    )

    max_g = float(np.max(g)) if g.size else float("-inf")
    feasible = bool(max_g <= 0.0)

    mda_results = collect_results(prob, c)

    required_W = _required_power_W(prob)
    installed_W = _installed_power_W(prob)
    margin_W = (
        installed_W - required_W
        if np.isfinite(installed_W) and np.isfinite(required_W)
        else np.nan
    )

    best_design = {
        name: float(value)
        for name, value in zip(DV_NAMES, X)
    }

    print(Fore.LIGHTGREEN_EX + "\n=== Best ADaPT optimization result ===" + Fore.RESET)
    print(f"Candidate source: {source}")
    for name in DV_NAMES:
        print(f"{name:36s}: {best_design[name]:.6g}")

    print(f"MTOW [kg]                          : {_get(prob, 'mtow', 'kg'):.3f}")
    print(
        f"Required shaft power [kW]          : "
        f"{required_W / 1000.0 if np.isfinite(required_W) else np.nan:.3f}"
    )
    print(
        f"Installed shaft power [kW]         : "
        f"{installed_W / 1000.0 if np.isfinite(installed_W) else np.nan:.3f}"
    )
    print(
        f"Installed power margin [kW]        : "
        f"{margin_W / 1000.0 if np.isfinite(margin_W) else np.nan:.3f}"
    )
    print(
        f"Takeoff ground roll [m]            : "
        f"{_first_available(prob, ('takeoff_ground_roll', 'ground_roll_distance'), 'm'):.3f}"
    )
    print(f"Objective                           : {objective:.6f}")
    print(f"Maximum g (<= 0 feasible)          : {max_g:.6e}")
    print(f"Feasible                            : {feasible}")

    if active_constraints:
        print("\nCurrent model constraints:")
        for name in active_constraints:
            value = _max_value(prob, name, default=np.nan)
            print(f"  {name:30s}: {value: .6e}")

    if save_best_csv is not None:
        _save_best_csv(
            save_best_csv,
            prob,
            c,
            X,
            source,
            objective,
            active_constraints,
            ground_roll_max_m,
            power_margin_cap_W,
            max_envelope_volume_m3,
        )
        print(
            Fore.LIGHTGREEN_EX
            + f"Saved best design -> {save_best_csv}"
            + Fore.RESET
        )

    return {
        "problem": prob,
        "pymoo_result": res,
        "config": c,
        "best_x": X,
        "best_design": best_design,
        "candidate_source": source,
        "objective": float(objective),
        "constraint_vector": g,
        "max_constraint_violation": max_g,
        "feasible": feasible,
        "active_model_constraints": tuple(active_constraints),
        "mda_results": mda_results,
    }


def run_mdo(
    pop_size: int = 200,
    n_gen: int = 400,
    seed: int = 11,
    jitter: float = 0.08,
    verbose: bool = True,
    save_best_csv: str = "best_mdo_design.csv",
    cfg: Optional[Dict[str, Any]] = None,
):
    """
    Compact compatibility entry point.

    For the graphical interface, ``run_optimization`` is preferred because it
    returns the full structured result dictionary.
    """
    result = run_optimization(
        cfg=cfg,
        pop_size=pop_size,
        n_gen=n_gen,
        seed=seed,
        jitter=jitter,
        verbose=verbose,
        save_best_csv=save_best_csv,
    )
    return result["problem"], result["pymoo_result"]


if __name__ == "__main__":
    try:
        result = run_optimization(
            cfg=BASE_CONFIG,
            pop_size=220,
            n_gen=450,
            seed=11,
            jitter=0.08,
            verbose=True,
            save_best_csv="best_mdo_design.csv",
        )

        result["problem"].cleanup()

        print(
            Fore.LIGHTGREEN_EX
            + "=== ADaPT optimization run complete ==="
            + Fore.RESET
        )

    except Exception as exc:
        print(Fore.RED + f"ERROR: {exc}" + Fore.RESET)
        sys.exit(1)
