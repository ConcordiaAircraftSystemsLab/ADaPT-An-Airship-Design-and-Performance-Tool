# -*- coding: utf-8 -*-
"""
ADaPT UI-facing Design of Experiments (DOE) driver.

This module evaluates architecture-specific design spaces using the canonical
``run_MDA.py`` builder.  Geometry, Weight, Performance, Propulsion, Power,
Battery, Solar and Hydrogen/Tank physics remain inside their authoritative
ADaPT components.

The DOE layer performs only:
    - architecture selection,
    - system-level design-variable variation,
    - technology-parameter variation,
    - collection of current ADaPT outputs,
    - feasibility classification using ``g <= 0``,
    - PFEI/post-processing and visualization.

Author: Musavir Bashir
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import openmdao.api as om
from matplotlib.patches import Ellipse

from pymoo.optimize import minimize
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.core.sampling import Sampling
from pymoo.core.problem import ElementwiseProblem
from pymoo.termination import get_termination

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
    import seaborn as sns
    _HAVE_SNS = True
except Exception:
    _HAVE_SNS = False


# Canonical MDA/UI API.
try:
    from run_MDA import build_problem, normalize_config, collect_results
except ImportError:
    from run_MDA_updated import build_problem, normalize_config, collect_results


# =============================================================================
# 1. Mission and architecture definitions
# =============================================================================

PAYLOAD_KG = 1123.0
RANGE_M = 1_342_100.0
CRUISE_ALT_M = 914.0
CRUISE_V_MS = 19.5
NUM_STEPS = 1

BASE_CONFIG: Dict[str, Any] = {
    "airship_type": "non-rigid",
    "landing_system": "conventional",
    "num_steps": NUM_STEPS,

    "payload_kg": PAYLOAD_KG,
    "range_m": RANGE_M,
    "cruise_alt_m": CRUISE_ALT_M,
    "cruise_speed_mps": CRUISE_V_MS,

    "length_m": 53.4,
    "fineness_ratio": 4.0,
    "tail_volume_coeff_horizontal": 0.066,
    "tail_volume_coeff_vertical": 0.059,
    "tail_coefficient_method": "user",

    "n_crew": 1,
    "n_engine": 2,
    "BR_takeoff": 0.83,
    "BR_landing": 0.90,
    "lift_coeff": 0.15,
    "drag_coeff_zero": 0.03542,
    "drag_due_to_lift_factor": 0.869,
    "propeller_efficiency": 0.78,
}


# Architecture configurations now use only current ADaPT names and actual
# subsystem parameters.  There is no external battery/tank/fuel mass model.
ARCHES = [
    {
        "name": "Conventional ICE",
        "key": "conventional_reciprocating",
        "config": {
            "power_source": "conventional_reciprocating",
            "installed_shaft_power_W": 268_000.0,  # total aircraft
            "installed_consumable_capacity_kg": 599.0,
            "ice_thermal_efficiency": 0.30,
            "gasoline_lhv_Jkg": 43.0e6,
            "fuel_reserve_fraction": 0.10,
        },
        "mtow_lower_kg": 4_500.0,
        "mtow_upper_kg": 25_000.0,
        "tech_kind": "ice",
    },
    {
        "name": "Hydrogen ICE",
        "key": "hydrogen_reciprocating",
        "config": {
            "power_source": "hydrogen_reciprocating",
            "installed_shaft_power_W": 268_000.0,  # total aircraft
            "installed_consumable_capacity_kg": 150.0,
            "hydrogen_onboard_mass_kg": 150.0,
            "ice_thermal_efficiency": 0.30,
            "hydrogen_lhv_Jkg": 120.0e6,
            "tank_gravimetric_efficiency": 0.20,
            "hydrogen_storage_density_kgm3": 70.8,
            "fuel_reserve_fraction": 0.10,
        },
        "mtow_lower_kg": 4_500.0,
        "mtow_upper_kg": 25_000.0,
        "tech_kind": "hydrogen_ice",
    },
    {
        "name": "Battery Electric",
        "key": "battery_only",
        "config": {
            "power_source": "battery_only",
            "installed_shaft_power_W": 268_000.0,  # total aircraft
            "installed_consumable_capacity_kg": 0.0,
            "battery_specific_energy_Whkg": 250.0,
            "battery_volumetric_ed_WhL": 600.0,
            "battery_efficiency": 0.95,
            "depth_of_discharge": 0.80,
            "battery_packaging_factor": 0.72,
        },
        "mtow_lower_kg": None,
        "mtow_upper_kg": 90_000.0,
        "tech_kind": "battery",
    },
    {
        "name": "Solar-Battery",
        "key": "solar_battery",
        "config": {
            "power_source": "solar_battery",
            "installed_shaft_power_W": 268_000.0,  # total aircraft
            "installed_consumable_capacity_kg": 0.0,
            "battery_specific_energy_Whkg": 250.0,
            "battery_volumetric_ed_WhL": 600.0,
            "battery_efficiency": 0.95,
            "depth_of_discharge": 0.80,
            "battery_packaging_factor": 0.72,
            "solar_area_m2": 300.0,
            "solar_irradiance_Wm2": 600.0,
            "solar_efficiency": 0.22,
            "pv_areal_density_kgm2": 0.50,
            "solar_energy_MJ": 0.0,
        },
        "mtow_lower_kg": None,
        "mtow_upper_kg": 90_000.0,
        "tech_kind": "solar_battery",
    },
]

ARCH_COLORS = {
    "conventional_reciprocating": "#17becf",
    "hydrogen_reciprocating": "#e377c2",
    "battery_only": "#1f77b4",
    "solar_battery": "#ff7f0e",
}


# =============================================================================
# 2. Generic helpers
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
        arr = _array(prob, name, units=units)
        return float(arr[0]) if arr.size else float(default)
    except Exception:
        return float(default)


def _max_value(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        arr = _array(prob, name, units=units)
        arr = arr[np.isfinite(arr)]
        return float(np.max(arr)) if arr.size else float(default)
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


def architecture_config(
    arch: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = dict(BASE_CONFIG)
    cfg.update(arch.get("config", {}))
    if overrides:
        cfg.update(overrides)
    return normalize_config(cfg)


# =============================================================================
# 3. Design variables
# =============================================================================

# Current Performance calculates the aerodynamic CL required for equilibrium,
# so ``lift_coeff`` is retained as a normal model input rather than an active
# DOE/optimization design variable.
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

LB = np.array([0.50, 0.05, 0.04, 0.45, 0.70], dtype=float)
UB = np.array([0.98, 0.09, 0.08, 1.00, 0.88], dtype=float)


def _set_x(prob: om.Problem, x: Sequence[float]) -> None:
    x = np.asarray(x, dtype=float).reshape(-1)
    if x.size != len(DV_NAMES):
        raise ValueError(
            f"Expected {len(DV_NAMES)} design variables in order {DV_NAMES}."
        )

    prob.set_val("BR_takeoff", x[0])
    prob.set_val("tail_volume_coeff_horizontal", x[1])
    prob.set_val("tail_volume_coeff_vertical", x[2])
    prob.set_val("drag_due_to_lift_factor", x[3])
    prob.set_val("propeller_efficiency", x[4])


def _get_x(prob: om.Problem) -> np.ndarray:
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
    def __init__(self, x0, jitter=0.06):
        super().__init__()
        self.x0 = np.asarray(x0, float).copy()
        self.jitter = float(jitter)

    def _do(self, problem, n_samples, **kwargs):
        lb = np.asarray(problem.xl)
        ub = np.asarray(problem.xu)

        pop = np.random.uniform(lb, ub, size=(n_samples, lb.size))
        pop[0, :] = np.clip(self.x0, lb, ub)

        k = min(5, n_samples - 1)
        if k > 0:
            idx = np.random.choice(
                np.arange(1, n_samples),
                size=k,
                replace=False,
            )
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


def _select_best(res):
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
        for algo in res.history:
            pop = getattr(algo, "pop", None)
            if pop is None:
                continue

            Xp = pop.get("X")
            Fp = pop.get("F").reshape(-1)
            CVp = pop.get("CV").reshape(-1)
            j = np.lexsort((Fp, CVp))[0]
            cand = (CVp[j], Fp[j], Xp[j])

            if (
                best is None
                or cand[0] < best[0]
                or (cand[0] == best[0] and cand[1] < best[1])
            ):
                best = cand

        if best is not None:
            return best[2], "history"

    raise RuntimeError(
        "pymoo produced no candidate; check model feasibility and bounds."
    )


# =============================================================================
# 4. Current ADaPT feasibility
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


def _active_model_constraints(prob: om.Problem) -> Tuple[str, ...]:
    active = []
    for name in MODEL_CONSTRAINTS:
        value = _max_value(prob, name, default=np.nan)
        if np.isfinite(value):
            active.append(name)
    return tuple(active)


def _constraint_vector(
    prob: om.Problem,
    arch: Dict[str, Any],
    active_constraints: Sequence[str],
    ground_roll_max_m: Optional[float] = 450.0,
) -> Tuple[np.ndarray, Tuple[str, ...]]:
    """
    Return current ADaPT model constraints plus DOE-level limits.

    All entries already follow the common convention ``g <= 0``.
    """
    values = []
    names = []

    for name in active_constraints:
        value = _max_value(prob, name, default=np.nan)
        values.append(value if np.isfinite(value) else 1.0e6)
        names.append(name)

    if ground_roll_max_m is not None:
        ground_roll = _first_available(
            prob,
            ("takeoff_ground_roll", "ground_roll_distance"),
            units="m",
            default=np.nan,
        )
        values.append(
            ground_roll - float(ground_roll_max_m)
            if np.isfinite(ground_roll)
            else 1.0e6
        )
        names.append("doe_ground_roll_limit_m")

    mtow = _get(prob, "mtow", "kg", default=np.nan)

    lo = arch.get("mtow_lower_kg")
    hi = arch.get("mtow_upper_kg")

    if lo is not None:
        values.append(
            float(lo) - mtow if np.isfinite(mtow) else 1.0e6
        )
        names.append("doe_mtow_lower_limit_kg")

    if hi is not None:
        values.append(
            mtow - float(hi) if np.isfinite(mtow) else 1.0e6
        )
        names.append("doe_mtow_upper_limit_kg")

    return np.asarray(values, dtype=float), tuple(names)


# =============================================================================
# 5. Energy/PFEI post-processing from authoritative model outputs
# =============================================================================

def _required_power_W(prob: om.Problem) -> float:
    return _maximum_available(
        prob,
        ("required_shaft_power", "shaft_power", "required_power"),
        units="W",
        default=np.nan,
    )


def _source_energy_MJ(
    prob: om.Problem,
    arch: Dict[str, Any],
    cfg: Dict[str, Any],
) -> float:
    """
    Determine mission source-energy requirement without re-sizing hardware.

    Priority:
      1. an architecture model's explicit required/source-energy output;
      2. required consumable mass × fuel/hydrogen LHV;
      3. required battery electrical energy;
      4. Performance shaft-energy output as the general fallback.

    The function is post-processing only.  Battery mass, tank mass, fuel mass
    and installed system masses remain outputs of the ADaPT component models.
    """
    direct_MJ = _first_available(
        prob,
        (
            "required_primary_energy",
            "primary_energy_required",
            "source_energy_required",
            "total_source_energy_required",
            "required_energy",
        ),
        units="MJ",
        default=np.nan,
    )
    if np.isfinite(direct_MJ):
        return direct_MJ

    source = cfg["power_source"]

    if source in {"conventional_reciprocating", "turboprop", "turboelectric"}:
        required_mass = _first_available(
            prob,
            ("required_consumable_mass", "fuel_mass"),
            units="kg",
            default=np.nan,
        )
        if np.isfinite(required_mass):
            return required_mass * float(cfg["gasoline_lhv_Jkg"]) / 1.0e6

    if source in {
        "hydrogen_reciprocating",
        "hydrogen_fuel_cell",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
    }:
        required_mass = _first_available(
            prob,
            ("required_consumable_mass", "hydrogen_mass", "fuel_mass"),
            units="kg",
            default=np.nan,
        )
        if np.isfinite(required_mass):
            return required_mass * float(cfg["hydrogen_lhv_Jkg"]) / 1.0e6

    battery_MJ = _first_available(
        prob,
        (
            "required_battery_energy",
            "battery_energy_required",
            "battery_energy",
        ),
        units="MJ",
        default=np.nan,
    )
    if np.isfinite(battery_MJ):
        return battery_MJ

    battery_Wh = _first_available(
        prob,
        (
            "required_battery_energy",
            "battery_energy_required",
            "battery_energy",
        ),
        units="W*h",
        default=np.nan,
    )
    if np.isfinite(battery_Wh):
        return battery_Wh * 3.6e-3

    return _first_available(
        prob,
        ("total_mission_energy_required", "mission_energy_required"),
        units="MJ",
        default=np.nan,
    )


def _pfei(
    prob: om.Problem,
    arch: Dict[str, Any],
    cfg: Dict[str, Any],
) -> float:
    energy_MJ = _source_energy_MJ(prob, arch, cfg)
    payload = _get(prob, "payload", "kg", default=cfg["payload_kg"])
    range_km = _get(prob, "range", "km", default=cfg["range_m"] / 1000.0)

    denominator = payload * range_km
    if (
        np.isfinite(energy_MJ)
        and np.isfinite(denominator)
        and denominator > 0.0
    ):
        return energy_MJ / denominator

    return np.nan


# =============================================================================
# 6. Local PFEI optimization for each architecture
# =============================================================================

class PFEIProblem(ElementwiseProblem):
    def __init__(
        self,
        prob: om.Problem,
        arch: Dict[str, Any],
        cfg: Dict[str, Any],
        active_constraints: Sequence[str],
    ):
        g0, _ = _constraint_vector(
            prob,
            arch,
            active_constraints,
        )

        super().__init__(
            n_var=len(DV_NAMES),
            n_obj=1,
            n_constr=len(g0),
            xl=LB,
            xu=UB,
        )

        self.prob = prob
        self.arch = arch
        self.cfg = cfg
        self.active_constraints = tuple(active_constraints)

    def _evaluate(self, x, out, *args, **kwargs):
        try:
            _set_x(self.prob, x)
            self.prob.run_model()

            g, _ = _constraint_vector(
                self.prob,
                self.arch,
                self.active_constraints,
            )

            pfei = _pfei(self.prob, self.arch, self.cfg)
            out["F"] = pfei if np.isfinite(pfei) else 1.0e9
            out["G"] = g

        except Exception:
            out["F"] = 1.0e9
            out["G"] = np.full(self.n_ieq_constr, 1.0e6)


def _architecture_row(
    prob: om.Problem,
    arch: Dict[str, Any],
    cfg: Dict[str, Any],
    Xbest: Sequence[float],
    candidate_source: str,
) -> Dict[str, Any]:
    result = collect_results(prob, cfg)
    scalars = result["scalars"]
    outputs = result["outputs"]

    active = _active_model_constraints(prob)
    g, g_names = _constraint_vector(prob, arch, active)
    max_g = float(np.max(g)) if g.size else float("-inf")

    source_energy_MJ = _source_energy_MJ(prob, arch, cfg)
    pfei = _pfei(prob, arch, cfg)

    battery_volume = _first_available(
        prob,
        ("battery_volume", "battery_pack_volume"),
        units="m**3",
        default=np.nan,
    )
    tank_volume = _first_available(
        prob,
        ("tank_volume", "installed_tank_volume"),
        units="m**3",
        default=np.nan,
    )

    row = {
        "arch": arch["name"],
        "key": arch["key"],
        "power_source": cfg["power_source"],
        "Xbest": np.asarray(Xbest, dtype=float),
        "candidate_source": candidate_source,
        "feasible": bool(max_g <= 0.0),
        "max_constraint_value": max_g,

        "P_req_kW": scalars.get("required_power_kW", np.nan),
        "P_installed_kW": scalars.get("installed_power_kW", np.nan),
        "P_margin_kW": scalars.get("power_margin_kW", np.nan),

        "owe_kg": scalars.get("owe_kg", np.nan),
        "mtow_kg": scalars.get("mtow_kg", np.nan),

        "required_consumable_kg": scalars.get(
            "required_consumable_kg",
            np.nan,
        ),
        "installed_consumable_kg": scalars.get(
            "installed_consumable_kg",
            np.nan,
        ),
        "battery_mass_kg": scalars.get("battery_mass_kg", np.nan),
        "battery_vol_m3": battery_volume,
        "h2_tank_mass_kg": scalars.get("tank_mass_kg", np.nan),
        "h2_tank_vol_m3": tank_volume,

        "source_energy_MJ": source_energy_MJ,
        "mission_shaft_energy_MJ": scalars.get("mission_energy_MJ", np.nan),
        "pfei_MJ_per_kg_km": pfei,

        "gross_volume_m3": outputs.get("gross_volume_m3", np.nan),
        "propulsion_mass_kg": outputs.get("propulsion_mass_kg", np.nan),
        "power_system_mass_kg": outputs.get("power_system_mass_kg", np.nan),
    }

    for name, value in zip(g_names, g):
        row[name] = float(value)

    return row


def run_arch_pymoo(
    arch: Dict[str, Any],
    pop_size: int = 96,
    n_gen: int = 160,
    seed: int = 11,
    cfg_overrides: Optional[Dict[str, Any]] = None,
):
    cfg = architecture_config(arch, cfg_overrides)

    prob = build_problem(cfg)
    prob.run_model()

    x0 = np.clip(_get_x(prob), LB, UB)
    active_constraints = _active_model_constraints(prob)

    moo_prob = PFEIProblem(
        prob,
        arch,
        cfg,
        active_constraints,
    )

    algo = DE(
        pop_size=pop_size,
        sampling=OMInitialSampling(x0, jitter=0.06),
    )
    term = get_termination("n_gen", n_gen)

    res = minimize(
        moo_prob,
        algo,
        term,
        seed=seed,
        verbose=False,
    )

    X, source = _select_best(res)
    X = np.asarray(X, dtype=float).reshape(-1)

    _set_x(prob, X)
    prob.run_model()

    row = _architecture_row(
        prob,
        arch,
        cfg,
        X,
        source,
    )

    prob.cleanup()
    return row


# =============================================================================
# 7. Technology perturbations applied to real ADaPT inputs
# =============================================================================

def _technology_sample(
    prob: om.Problem,
    arch: Dict[str, Any],
    cfg: Dict[str, Any],
    rng: np.random.RandomState,
    *,
    battery_se_jitter: float,
    battery_ve_jitter: float,
    efficiency_jitter: float,
) -> Dict[str, float]:
    """
    Perturb architecture technology inputs inside the current ADaPT model.

    Returned values are recorded in the DOE CSV for complete traceability.
    """
    tech = arch["tech_kind"]
    used: Dict[str, float] = {}

    if tech in {"battery", "solar_battery"}:
        se_scale = rng.uniform(
            1.0 - battery_se_jitter,
            1.0 + battery_se_jitter,
        )
        ve_scale = rng.uniform(
            1.0 - battery_ve_jitter,
            1.0 + battery_ve_jitter,
        )

        se = cfg["battery_specific_energy_Whkg"] * se_scale
        ve = cfg["battery_volumetric_ed_WhL"] * ve_scale

        _set_if_present(
            prob,
            "battery_specific_energy",
            se,
            units="W*h/kg",
        )
        _set_if_present(
            prob,
            "battery_volumetric_ed",
            ve,
            units="W*h/L",
        )

        used["battery_specific_energy_Whkg"] = se
        used["battery_volumetric_energy_WhL"] = ve

        if tech == "solar_battery":
            solar_scale = rng.uniform(
                1.0 - efficiency_jitter,
                1.0 + efficiency_jitter,
            )
            eta_solar = np.clip(
                cfg["solar_efficiency"] * solar_scale,
                0.01,
                0.95,
            )
            _set_if_present(prob, "solar_efficiency", eta_solar)
            used["solar_efficiency"] = eta_solar

    elif tech in {"ice", "hydrogen_ice"}:
        eta_scale = rng.uniform(
            1.0 - efficiency_jitter,
            1.0 + efficiency_jitter,
        )
        eta_ice = np.clip(
            cfg["ice_thermal_efficiency"] * eta_scale,
            0.05,
            0.80,
        )
        _set_if_present(prob, "ice_thermal_efficiency", eta_ice)
        used["ice_thermal_efficiency"] = eta_ice

        if tech == "hydrogen_ice":
            tank_scale = rng.uniform(
                1.0 - efficiency_jitter,
                1.0 + efficiency_jitter,
            )
            eta_tank = np.clip(
                cfg["tank_gravimetric_efficiency"] * tank_scale,
                0.03,
                0.80,
            )
            _set_if_present(
                prob,
                "tank_gravimetric_efficiency",
                eta_tank,
            )
            used["tank_gravimetric_efficiency"] = eta_tank

    return used


# =============================================================================
# 8. DOE around architecture optimum
# =============================================================================

def _latin_hypercube(n: int, d: int, rng: np.random.RandomState):
    u = (rng.rand(n, d) + np.arange(n)[:, None]) / n
    for j in range(d):
        rng.shuffle(u[:, j])
    return u


def doe_around_best(
    arch: Dict[str, Any],
    Xbest,
    *,
    n_per_shell: int = 800,
    shells=(0.01, 0.02, 0.04, 0.07, 0.10),
    seed: int = 13,
    battery_se_jitter: float = 0.15,
    battery_ve_jitter: float = 0.15,
    efficiency_jitter: float = 0.05,
    cfg_overrides: Optional[Dict[str, Any]] = None,
):
    """
    Generate a dense DOE cloud around the architecture optimum.

    Design-variable perturbations operate on the coupled ADaPT model.
    Technology perturbations change actual component inputs rather than
    post-processing battery/tank/fuel masses externally.
    """
    rng = np.random.RandomState(seed)
    width = UB - LB

    cfg = architecture_config(arch, cfg_overrides)
    prob = build_problem(cfg)
    prob.run_model()

    active_constraints = _active_model_constraints(prob)

    records = []

    for shell in shells:
        U = _latin_hypercube(
            n_per_shell,
            len(Xbest),
            rng,
        )
        jitter = (2.0 * U - 1.0) * (shell * width)

        # Tail-volume coefficients receive smaller perturbations to maintain
        # a locally meaningful design cloud.
        jitter[:, 1] *= 0.5
        jitter[:, 2] *= 0.5

        Xs = np.clip(
            np.asarray(Xbest, dtype=float) + jitter,
            LB,
            UB,
        )

        for x in Xs:
            # Restore nominal architecture technology first.
            if arch["tech_kind"] in {"battery", "solar_battery"}:
                _set_if_present(
                    prob,
                    "battery_specific_energy",
                    cfg["battery_specific_energy_Whkg"],
                    units="W*h/kg",
                )
                _set_if_present(
                    prob,
                    "battery_volumetric_ed",
                    cfg["battery_volumetric_ed_WhL"],
                    units="W*h/L",
                )
                if arch["tech_kind"] == "solar_battery":
                    _set_if_present(
                        prob,
                        "solar_efficiency",
                        cfg["solar_efficiency"],
                    )

            if arch["tech_kind"] in {"ice", "hydrogen_ice"}:
                _set_if_present(
                    prob,
                    "ice_thermal_efficiency",
                    cfg["ice_thermal_efficiency"],
                )

            if arch["tech_kind"] == "hydrogen_ice":
                _set_if_present(
                    prob,
                    "tank_gravimetric_efficiency",
                    cfg["tank_gravimetric_efficiency"],
                )

            tech_used = _technology_sample(
                prob,
                arch,
                cfg,
                rng,
                battery_se_jitter=battery_se_jitter,
                battery_ve_jitter=battery_ve_jitter,
                efficiency_jitter=efficiency_jitter,
            )

            _set_x(prob, x)

            try:
                prob.run_model()
            except Exception:
                records.append(
                    {
                        "arch": arch["name"],
                        "key": arch["key"],
                        "mtow_kg": np.nan,
                        "pfei_MJ_per_kg_km": np.nan,
                        "feasible": False,
                        "max_constraint_value": 1.0e6,
                        "shell": shell,
                        **{
                            name: float(value)
                            for name, value in zip(DV_NAMES, x)
                        },
                        **tech_used,
                    }
                )
                continue

            g, g_names = _constraint_vector(
                prob,
                arch,
                active_constraints,
            )
            max_g = float(np.max(g)) if g.size else float("-inf")

            result = collect_results(prob, cfg)
            scalars = result["scalars"]

            record = {
                "arch": arch["name"],
                "key": arch["key"],
                "mtow_kg": scalars.get("mtow_kg", np.nan),
                "owe_kg": scalars.get("owe_kg", np.nan),
                "pfei_MJ_per_kg_km": _pfei(prob, arch, cfg),
                "source_energy_MJ": _source_energy_MJ(prob, arch, cfg),
                "required_power_kW": scalars.get(
                    "required_power_kW",
                    np.nan,
                ),
                "installed_power_kW": scalars.get(
                    "installed_power_kW",
                    np.nan,
                ),
                "required_consumable_kg": scalars.get(
                    "required_consumable_kg",
                    np.nan,
                ),
                "battery_mass_kg": scalars.get(
                    "battery_mass_kg",
                    np.nan,
                ),
                "tank_mass_kg": scalars.get(
                    "tank_mass_kg",
                    np.nan,
                ),
                "feasible": bool(max_g <= 0.0),
                "max_constraint_value": max_g,
                "shell": shell,
                **{
                    name: float(value)
                    for name, value in zip(DV_NAMES, x)
                },
                **tech_used,
            }

            for name, value in zip(g_names, g):
                record[name] = float(value)

            records.append(record)

    prob.cleanup()

    df = pd.DataFrame(records)
    csvname = f"doe_{arch['name'].replace(' ', '_')}.csv"
    df.to_csv(csvname, index=False)

    print(f"Saved {len(df)} samples -> {csvname}")
    return df


# =============================================================================
# 9. Plotting utilities
# =============================================================================

def _confidence_ellipse(
    x,
    y,
    ax,
    n_std=2.0,
    edgecolor="k",
    facecolor="none",
    linewidth=1.5,
    **kwargs,
):
    x = np.asarray(x)
    y = np.asarray(y)

    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]

    if x.size < 3:
        return None

    cov = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals = vals[order]
    vecs = vecs[:, order]

    theta = np.degrees(
        np.arctan2(*vecs[:, 0][::-1])
    )
    width = 2 * n_std * np.sqrt(max(vals[0], 1.0e-12))
    height = 2 * n_std * np.sqrt(max(vals[1], 1.0e-12))

    ellipse = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width,
        height=height,
        angle=theta,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        **kwargs,
    )
    ax.add_patch(ellipse)
    return ellipse


def plot_cluster_for_arch(
    df_arch_row,
    cloud_df,
    outfile_png=None,
    show=False,
):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(9.2, 7.0))

    arch_name = df_arch_row["arch"]
    key = df_arch_row.get(
        "key",
        arch_name.lower().replace(" ", "_"),
    )
    color = ARCH_COLORS.get(key, "#333333")

    if cloud_df is None or cloud_df.empty:
        ax.scatter(
            df_arch_row["mtow_kg"],
            df_arch_row["pfei_MJ_per_kg_km"],
            s=220,
            marker="*",
            c=color,
            edgecolors="k",
            linewidths=0.9,
            label="optimized baseline",
        )
        ax.set_xlabel("MTOW [kg]")
        ax.set_ylabel("PFEI [MJ/(kg·km)]")
        ax.set_title(f"{arch_name} DOE: PFEI vs MTOW")

        if outfile_png:
            plt.tight_layout()
            plt.savefig(outfile_png, dpi=160)
        if show:
            plt.show()

        plt.close(fig)
        return

    df = cloud_df[
        cloud_df["mtow_kg"].notna()
        & cloud_df["pfei_MJ_per_kg_km"].notna()
    ].copy()

    df["feasible"] = df["feasible"].astype(bool)

    feasible = df[df["feasible"]]
    infeasible = df[~df["feasible"]]

    if not infeasible.empty:
        ax.scatter(
            infeasible["mtow_kg"],
            infeasible["pfei_MJ_per_kg_km"],
            s=22,
            alpha=0.28,
            c="0.3",
            marker="x",
            linewidths=0.6,
            label=f"{arch_name} infeasible",
        )

    if not feasible.empty:
        ax.scatter(
            feasible["mtow_kg"],
            feasible["pfei_MJ_per_kg_km"],
            s=48,
            alpha=0.50,
            c=color,
            edgecolors="white",
            linewidths=0.6,
            label="DOE samples",
        )

        if _HAVE_SNS and len(feasible) >= 8:
            try:
                sns.kdeplot(
                    data=feasible,
                    x="mtow_kg",
                    y="pfei_MJ_per_kg_km",
                    color=color,
                    levels=4,
                    fill=True,
                    alpha=0.18,
                    ax=ax,
                )
            except Exception:
                pass

        _confidence_ellipse(
            feasible["mtow_kg"],
            feasible["pfei_MJ_per_kg_km"],
            ax,
            n_std=2.0,
            edgecolor=color,
            facecolor="none",
            linewidth=2.0,
        )

    ax.scatter(
        df_arch_row["mtow_kg"],
        df_arch_row["pfei_MJ_per_kg_km"],
        s=220,
        marker="*",
        c=color,
        edgecolors="k",
        linewidths=0.9,
        label="optimized baseline",
    )

    ax.annotate(
        df_arch_row["arch"],
        (
            df_arch_row["mtow_kg"],
            df_arch_row["pfei_MJ_per_kg_km"],
        ),
        xytext=(10, 8),
        textcoords="offset points",
        fontsize=11,
        weight="bold",
    )

    ax.set_xlabel("MTOW [kg]")
    ax.set_ylabel("PFEI [MJ/(kg·km)]")
    ax.set_title(f"{arch_name} DOE: PFEI vs MTOW")
    ax.legend(frameon=True, fontsize=10, loc="best")
    ax.grid(alpha=0.34)

    if not df.empty:
        x = df["mtow_kg"].values
        y = df["pfei_MJ_per_kg_km"].values

        xr = (np.nanmin(x), np.nanmax(x))
        yr = (np.nanmin(y), np.nanmax(y))

        xpad = (
            0.06 * (xr[1] - xr[0])
            if xr[1] != xr[0]
            else max(abs(xr[0]) * 0.05, 1.0)
        )
        ypad = (
            0.08 * (yr[1] - yr[0])
            if yr[1] != yr[0]
            else max(abs(yr[0]) * 0.05, 1.0e-3)
        )

        ax.set_xlim(xr[0] - xpad, xr[1] + xpad)
        ax.set_ylim(max(0.0, yr[0] - ypad), yr[1] + ypad)

    plt.tight_layout()

    if outfile_png:
        plt.savefig(outfile_png, dpi=180)

    if show:
        plt.show()

    plt.close(fig)


def plot_energy_chain(df):
    """
    Plot current architecture-level conversion efficiencies.

    Values come from the same configured architecture inputs used by ADaPT.
    This is a visualization of configured conversion assumptions, not a second
    energy model.
    """
    labels = []
    useful = []
    conversion_loss = []

    for arch in ARCHES:
        cfg = architecture_config(arch)
        source = cfg["power_source"]

        if source == "conventional_reciprocating":
            eta = (
                cfg["ice_thermal_efficiency"]
                * cfg["propeller_efficiency"]
            )

        elif source == "hydrogen_reciprocating":
            eta = (
                cfg["ice_thermal_efficiency"]
                * cfg["propeller_efficiency"]
            )

        elif source in {"battery_only", "solar_battery"}:
            # Battery discharge/system efficiency and propeller efficiency.
            eta = (
                cfg["battery_efficiency"]
                * cfg["propeller_efficiency"]
            )

        else:
            eta = np.nan

        labels.append(arch["name"])
        useful.append(eta)
        conversion_loss.append(
            1.0 - eta if np.isfinite(eta) else np.nan
        )

    y = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(9.2, 7.0))
    ax.barh(y, conversion_loss, label="conversion / propulsive losses")
    ax.barh(
        y,
        useful,
        left=conversion_loss,
        label="useful propulsive fraction",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Configured first-order energy fraction")
    ax.set_title("Architecture conversion-chain context")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(
        "energy_chain.png",
        dpi=140,
        bbox_inches="tight",
    )
    plt.close(fig)


def plot_pareto_with_clouds(df_arch, clouds):
    plt.figure(figsize=(9.2, 7.0))

    for _, row in df_arch.iterrows():
        name = row["arch"]
        key = row.get(
            "key",
            name.lower().replace(" ", "_"),
        )
        cloud = clouds.get(name)
        color = ARCH_COLORS.get(key, "#333333")

        if cloud is not None and not cloud.empty:
            feasible = cloud[cloud["feasible"]]
            infeasible = cloud[~cloud["feasible"]]

            if not infeasible.empty:
                plt.scatter(
                    infeasible["mtow_kg"],
                    infeasible["pfei_MJ_per_kg_km"],
                    s=10,
                    alpha=0.28,
                    c="0.3",
                    marker="x",
                    linewidths=0.6,
                    label=f"{name} infeasible",
                )

            if not feasible.empty:
                plt.scatter(
                    feasible["mtow_kg"],
                    feasible["pfei_MJ_per_kg_km"],
                    s=12,
                    alpha=0.28,
                    c=color,
                    marker="o",
                    label=f"{name} feasible",
                )

        if (
            np.isfinite(row.get("mtow_kg", np.nan))
            and np.isfinite(
                row.get("pfei_MJ_per_kg_km", np.nan)
            )
        ):
            plt.scatter(
                row["mtow_kg"],
                row["pfei_MJ_per_kg_km"],
                s=120,
                edgecolor="k",
                linewidth=0.7,
                c=color,
                label=f"{name} optimized baseline",
            )

            plt.annotate(
                name,
                (
                    row["mtow_kg"],
                    row["pfei_MJ_per_kg_km"],
                ),
                fontsize=9,
                xytext=(6, 6),
                textcoords="offset points",
            )

        pngname = f"{name.replace(' ', '_')}_DOE.png"
        try:
            plot_cluster_for_arch(
                row,
                cloud,
                outfile_png=pngname,
                show=False,
            )
        except Exception as exc:
            print(
                Fore.CYAN
                + f"  ! Could not create cluster plot for {name}: {exc}"
                + Fore.RESET
            )

    plt.xlabel("MTOW [kg]")
    plt.ylabel("PFEI [MJ/(kg·km)]")
    plt.grid(True, alpha=0.3)

    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(
        by_label.values(),
        by_label.keys(),
        fontsize=9,
        loc="best",
    )

    plt.tight_layout()
    plt.savefig(
        "pfei_vs_mtow_clouds.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close()


# =============================================================================
# 10. UI-facing DOE API
# =============================================================================

def run_doe(
    *,
    architectures: Optional[Sequence[Dict[str, Any]]] = None,
    pop_size: int = 96,
    n_gen: int = 160,
    optimization_seed: int = 11,
    n_per_shell: int = 800,
    shells=(0.01, 0.02, 0.04, 0.07, 0.10),
    doe_seed: int = 13,
    battery_se_jitter: float = 0.15,
    battery_ve_jitter: float = 0.15,
    efficiency_jitter: float = 0.05,
    make_plots: bool = True,
) -> Dict[str, Any]:
    """
    Run the architecture optimization + local DOE cloud workflow.

    Returns
    -------
    dict
        ``summary`` : architecture-level DataFrame
        ``clouds``  : mapping from architecture name to DOE DataFrame
    """
    arches = list(ARCHES if architectures is None else architectures)

    rows = []
    clouds = {}

    for arch in arches:
        print(
            Fore.LIGHTGREEN_EX
            + f"→ Running {arch['name']} ..."
            + Fore.RESET
        )

        try:
            row = run_arch_pymoo(
                arch,
                pop_size=pop_size,
                n_gen=n_gen,
                seed=optimization_seed,
            )

            print(
                f"   P_req={row['P_req_kW']:.1f} kW, "
                f"MTOW={row['mtow_kg']:.1f} kg, "
                f"PFEI={row['pfei_MJ_per_kg_km']:.5f}, "
                f"feasible={row['feasible']}"
            )

            rows.append(row)

            cloud = doe_around_best(
                arch,
                row["Xbest"],
                n_per_shell=n_per_shell,
                shells=shells,
                seed=doe_seed,
                battery_se_jitter=battery_se_jitter,
                battery_ve_jitter=battery_ve_jitter,
                efficiency_jitter=efficiency_jitter,
            )
            clouds[arch["name"]] = cloud

        except Exception as exc:
            print(
                Fore.RED
                + f"   FAILED: {exc}"
                + Fore.RESET
            )

            rows.append(
                {
                    "arch": arch["name"],
                    "key": arch["key"],
                    "power_source": arch["config"]["power_source"],
                    "feasible": False,
                }
            )

    summary = pd.DataFrame(rows)
    summary.to_csv(
        "architectures_pymoo_with_doe.csv",
        index=False,
    )

    print(
        Fore.LIGHTGREEN_EX
        + "Saved CSV -> architectures_pymoo_with_doe.csv"
        + Fore.RESET
    )

    if not summary.empty:
        wanted = [
            "arch",
            "P_req_kW",
            "P_installed_kW",
            "P_margin_kW",
            "mtow_kg",
            "pfei_MJ_per_kg_km",
            "feasible",
        ]
        available = [c for c in wanted if c in summary.columns]
        print("\nSummary:")
        print(summary[available])

    if make_plots and not summary.empty:
        plot_energy_chain(summary)
        plot_pareto_with_clouds(summary, clouds)

        print(
            Fore.LIGHTGREEN_EX
            + "Saved combined figure -> pfei_vs_mtow_clouds.png"
            + Fore.RESET
        )
        print(
            Fore.LIGHTGREEN_EX
            + "Saved per-architecture DOE PNGs"
            + Fore.RESET
        )

    return {
        "summary": summary,
        "clouds": clouds,
    }


# =============================================================================
# 11. Direct execution
# =============================================================================

def main():
    return run_doe(
        pop_size=96,
        n_gen=160,
        optimization_seed=11,
        n_per_shell=800,
        shells=(0.01, 0.02, 0.04, 0.07, 0.10),
        doe_seed=13,
        battery_se_jitter=0.15,
        battery_ve_jitter=0.15,
        efficiency_jitter=0.05,
        make_plots=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(Fore.RED + f"ERROR: {exc}" + Fore.RESET)
        sys.exit(1)
