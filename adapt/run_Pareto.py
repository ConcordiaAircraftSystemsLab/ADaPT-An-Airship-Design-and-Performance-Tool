# -*- coding: utf-8 -*-
"""
ADaPT UI-facing multi-objective Pareto driver.

The Pareto layer reuses the canonical ``run_MDA.py`` problem builder and reads
all masses, power/energy requirements, capacities and feasibility constraints
from the current coupled ADaPT model.

Objectives
----------
1. Minimize MTOW.
2. Minimize PFEI = source-energy / (payload * range).

Current conventions
-------------------
- Feasible constraints satisfy ``g <= 0``.
- ``installed_shaft_power`` is total aircraft propulsor shaft power.
- Battery, solar, hydrogen-tank, fuel and propulsion masses are evaluated only
  by their authoritative ADaPT subsystem models.
- PFEI is post-processing of authoritative model energy/resource outputs.

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

from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
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


# Canonical ADaPT UI/MDA API.
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


ARCHES = [
    {
        "name": "Conventional ICE",
        "key": "conventional_reciprocating",
        "config": {
            "power_source": "conventional_reciprocating",
            "installed_shaft_power_W": 268_000.0,
            "installed_consumable_capacity_kg": 599.0,
            "ice_thermal_efficiency": 0.30,
            "gasoline_lhv_Jkg": 43.0e6,
            "fuel_reserve_fraction": 0.10,
        },
        "mtow_upper_kg": 25_000.0,
    },
    {
        "name": "Hydrogen ICE",
        "key": "hydrogen_reciprocating",
        "config": {
            "power_source": "hydrogen_reciprocating",
            "installed_shaft_power_W": 268_000.0,
            "installed_consumable_capacity_kg": 150.0,
            "hydrogen_onboard_mass_kg": 150.0,
            "ice_thermal_efficiency": 0.30,
            "hydrogen_lhv_Jkg": 120.0e6,
            "tank_gravimetric_efficiency": 0.20,
            "hydrogen_storage_density_kgm3": 70.8,
            "fuel_reserve_fraction": 0.10,
        },
        "mtow_upper_kg": 25_000.0,
    },
    {
        "name": "Battery Electric",
        "key": "battery_only",
        "config": {
            "power_source": "battery_only",
            "installed_shaft_power_W": 268_000.0,
            "installed_consumable_capacity_kg": 0.0,
            "battery_specific_energy_Whkg": 250.0,
            "battery_volumetric_ed_WhL": 600.0,
            "battery_efficiency": 0.95,
            "depth_of_discharge": 0.80,
            "battery_packaging_factor": 0.72,
        },
        "mtow_upper_kg": 90_000.0,
    },
    {
        "name": "Solar-Battery",
        "key": "solar_battery",
        "config": {
            "power_source": "solar_battery",
            "installed_shaft_power_W": 268_000.0,
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
        "mtow_upper_kg": 90_000.0,
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


def architecture_config(
    arch: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = dict(BASE_CONFIG)
    cfg.update(arch["config"])
    if overrides:
        cfg.update(overrides)
    return normalize_config(cfg)


# =============================================================================
# 3. Design variables
# =============================================================================

# Current Performance calculates required aerodynamic CL from equilibrium.
# Therefore ``lift_coeff`` is not an active Pareto variable.
#
# x = [
#   BR_takeoff,
#   C_HT,
#   C_VT,
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


# =============================================================================
# 4. Current ADaPT constraints
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
    *,
    ground_roll_max_m: Optional[float] = 450.0,
) -> Tuple[np.ndarray, Tuple[str, ...]]:
    """
    Return model + study-level constraints, all in ``g <= 0`` form.
    """
    values = []
    names = []

    for name in active_constraints:
        value = _max_value(prob, name, default=np.nan)
        values.append(value if np.isfinite(value) else 1.0e6)
        names.append(name)

    if ground_roll_max_m is not None:
        gr = _first_available(
            prob,
            ("takeoff_ground_roll", "ground_roll_distance"),
            units="m",
            default=np.nan,
        )
        values.append(
            gr - float(ground_roll_max_m)
            if np.isfinite(gr)
            else 1.0e6
        )
        names.append("pareto_ground_roll_limit_m")

    mtow_upper = arch.get("mtow_upper_kg")
    if mtow_upper is not None:
        mtow = _get(prob, "mtow", "kg", default=np.nan)
        values.append(
            mtow - float(mtow_upper)
            if np.isfinite(mtow)
            else 1.0e6
        )
        names.append("pareto_mtow_upper_limit_kg")

    return np.asarray(values, dtype=float), tuple(names)


# =============================================================================
# 5. PFEI from authoritative model outputs
# =============================================================================

def _source_energy_MJ(
    prob: om.Problem,
    cfg: Dict[str, Any],
) -> float:
    """
    Return architecture source energy for PFEI post-processing.

    Hardware masses remain outputs of their ADaPT models; this function does
    not create external battery/tank/fuel sizing relationships.
    """
    direct = _first_available(
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
    if np.isfinite(direct):
        return direct

    source = cfg["power_source"]

    if source in {
        "conventional_reciprocating",
        "turboprop",
        "turboelectric",
    }:
        mass = _first_available(
            prob,
            ("required_consumable_mass", "fuel_mass"),
            units="kg",
            default=np.nan,
        )
        if np.isfinite(mass):
            return mass * float(cfg["gasoline_lhv_Jkg"]) / 1.0e6

    if source in {
        "hydrogen_reciprocating",
        "hydrogen_fuel_cell",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
    }:
        mass = _first_available(
            prob,
            (
                "required_consumable_mass",
                "hydrogen_mass",
                "fuel_mass",
            ),
            units="kg",
            default=np.nan,
        )
        if np.isfinite(mass):
            return mass * float(cfg["hydrogen_lhv_Jkg"]) / 1.0e6

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
        (
            "total_mission_energy_required",
            "mission_energy_required",
        ),
        units="MJ",
        default=np.nan,
    )


def _pfei(prob: om.Problem, cfg: Dict[str, Any]) -> float:
    energy_MJ = _source_energy_MJ(prob, cfg)

    payload_kg = _get(
        prob,
        "payload",
        "kg",
        default=float(cfg["payload_kg"]),
    )
    range_km = _get(
        prob,
        "range",
        "km",
        default=float(cfg["range_m"]) / 1000.0,
    )

    transport_work = payload_kg * range_km
    if (
        np.isfinite(energy_MJ)
        and np.isfinite(transport_work)
        and transport_work > 0.0
    ):
        return energy_MJ / transport_work

    return np.nan


# =============================================================================
# 6. Multi-objective pymoo problem
# =============================================================================

class AirshipParetoProblem(ElementwiseProblem):
    def __init__(
        self,
        prob: om.Problem,
        arch: Dict[str, Any],
        cfg: Dict[str, Any],
        active_constraints: Sequence[str],
        *,
        ground_roll_max_m: Optional[float] = 450.0,
    ):
        g0, _ = _constraint_vector(
            prob,
            arch,
            active_constraints,
            ground_roll_max_m=ground_roll_max_m,
        )

        super().__init__(
            n_var=len(DV_NAMES),
            n_obj=2,
            n_constr=len(g0),
            xl=LB,
            xu=UB,
        )

        self.prob = prob
        self.arch = arch
        self.cfg = cfg
        self.active_constraints = tuple(active_constraints)
        self.ground_roll_max_m = ground_roll_max_m

    def _evaluate(self, x, out, *args, **kwargs):
        try:
            _set_x(self.prob, x)
            self.prob.run_model()

            mtow = _get(
                self.prob,
                "mtow",
                "kg",
                default=np.nan,
            )
            pfei = _pfei(
                self.prob,
                self.cfg,
            )

            g, _ = _constraint_vector(
                self.prob,
                self.arch,
                self.active_constraints,
                ground_roll_max_m=self.ground_roll_max_m,
            )

            if not np.isfinite(mtow):
                mtow = 1.0e12
            if not np.isfinite(pfei):
                pfei = 1.0e9

            out["F"] = np.array([mtow, pfei], dtype=float)
            out["G"] = g

        except Exception:
            out["F"] = np.array([1.0e12, 1.0e9], dtype=float)
            out["G"] = np.full(self.n_ieq_constr, 1.0e6)


# =============================================================================
# 7. Pareto result extraction
# =============================================================================

def _as_2d(x):
    arr = np.asarray(x, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def _nondominated_mask(F: np.ndarray) -> np.ndarray:
    """
    Simple nondominated filter for two or more minimization objectives.
    """
    F = _as_2d(F)
    n = F.shape[0]
    keep = np.ones(n, dtype=bool)

    for i in range(n):
        if not keep[i]:
            continue
        for j in range(n):
            if i == j or not keep[j]:
                continue

            if np.all(F[j] <= F[i]) and np.any(F[j] < F[i]):
                keep[i] = False
                break

    return keep


def _result_population(res):
    """
    Return X, F, CV from the final population.

    This also allows recovery when ``res.X`` is empty because the final
    generation contains only infeasible solutions.
    """
    if getattr(res, "pop", None) is not None:
        pop = res.pop
        X = _as_2d(pop.get("X"))
        F = _as_2d(pop.get("F"))
        CV = np.asarray(pop.get("CV"), dtype=float).reshape(-1)
        return X, F, CV

    X = getattr(res, "X", None)
    F = getattr(res, "F", None)

    if X is not None and F is not None:
        X = _as_2d(X)
        F = _as_2d(F)
        CV = np.zeros(X.shape[0], dtype=float)
        return X, F, CV

    raise RuntimeError("No final Pareto population was returned by pymoo.")


def _evaluate_design_record(
    prob: om.Problem,
    arch: Dict[str, Any],
    cfg: Dict[str, Any],
    x: Sequence[float],
    active_constraints: Sequence[str],
    *,
    ground_roll_max_m: Optional[float],
) -> Dict[str, Any]:
    _set_x(prob, x)
    prob.run_model()

    result = collect_results(prob, cfg)
    scalars = result["scalars"]
    outputs = result["outputs"]

    g, g_names = _constraint_vector(
        prob,
        arch,
        active_constraints,
        ground_roll_max_m=ground_roll_max_m,
    )

    max_g = float(np.max(g)) if g.size else float("-inf")

    record: Dict[str, Any] = {
        "arch": arch["name"],
        "key": arch["key"],
        "power_source": cfg["power_source"],

        **{
            name: float(value)
            for name, value in zip(DV_NAMES, x)
        },

        "mtow_kg": scalars.get("mtow_kg", np.nan),
        "owe_kg": scalars.get("owe_kg", np.nan),

        "pfei_MJ_per_kg_km": _pfei(prob, cfg),
        "source_energy_MJ": _source_energy_MJ(prob, cfg),

        "required_power_kW": scalars.get(
            "required_power_kW",
            np.nan,
        ),
        "installed_power_kW": scalars.get(
            "installed_power_kW",
            np.nan,
        ),
        "power_margin_kW": scalars.get(
            "power_margin_kW",
            np.nan,
        ),

        "required_consumable_kg": scalars.get(
            "required_consumable_kg",
            np.nan,
        ),
        "installed_consumable_kg": scalars.get(
            "installed_consumable_kg",
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

        "gross_volume_m3": outputs.get(
            "gross_volume_m3",
            np.nan,
        ),
        "propulsion_mass_kg": outputs.get(
            "propulsion_mass_kg",
            np.nan,
        ),
        "power_system_mass_kg": outputs.get(
            "power_system_mass_kg",
            np.nan,
        ),

        "max_constraint_value": max_g,
        "feasible": bool(max_g <= 0.0),
    }

    for name, value in zip(g_names, g):
        record[name] = float(value)

    return record


# =============================================================================
# 8. Run one architecture
# =============================================================================

def run_arch_pareto(
    arch: Dict[str, Any],
    *,
    pop_size: int = 160,
    n_gen: int = 260,
    seed: int = 11,
    ground_roll_max_m: Optional[float] = 450.0,
    cfg_overrides: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    cfg = architecture_config(
        arch,
        cfg_overrides,
    )

    prob = build_problem(cfg)
    prob.run_model()

    active_constraints = _active_model_constraints(prob)

    problem = AirshipParetoProblem(
        prob,
        arch,
        cfg,
        active_constraints,
        ground_roll_max_m=ground_roll_max_m,
    )

    algorithm = NSGA2(
        pop_size=int(pop_size),
        eliminate_duplicates=True,
    )

    termination = get_termination(
        "n_gen",
        int(n_gen),
    )

    result = minimize(
        problem,
        algorithm,
        termination,
        seed=int(seed),
        verbose=False,
    )

    X, F, CV = _result_population(result)

    feasible_mask = CV <= 1.0e-12

    # Prefer the feasible final population.  If none is feasible, retain the
    # minimum-CV set so the UI can still show how close the architecture came.
    if np.any(feasible_mask):
        Xc = X[feasible_mask]
        Fc = F[feasible_mask]
        status = "feasible"
    else:
        cv_min = np.nanmin(CV)
        near = np.isclose(CV, cv_min)
        Xc = X[near]
        Fc = F[near]
        status = "minimum_constraint_violation"

    nd = _nondominated_mask(Fc)
    Xpareto = Xc[nd]
    Fpareto = Fc[nd]

    # Sort for clean plotting/export by MTOW.
    order = np.argsort(Fpareto[:, 0])
    Xpareto = Xpareto[order]
    Fpareto = Fpareto[order]

    records = []

    for x in Xpareto:
        try:
            row = _evaluate_design_record(
                prob,
                arch,
                cfg,
                x,
                active_constraints,
                ground_roll_max_m=ground_roll_max_m,
            )
            row["pareto_status"] = status
            records.append(row)
        except Exception:
            continue

    prob.cleanup()

    df = pd.DataFrame(records)

    filename = (
        f"pareto_{arch['name'].replace(' ', '_')}.csv"
    )
    df.to_csv(
        filename,
        index=False,
    )

    print(
        Fore.LIGHTGREEN_EX
        + f"Saved Pareto set -> {filename} ({len(df)} points)"
        + Fore.RESET
    )

    return df


# =============================================================================
# 9. Pareto metrics and representative design points
# =============================================================================

def representative_points(df: pd.DataFrame) -> Dict[str, Optional[pd.Series]]:
    """
    Return minimum-MTOW, minimum-PFEI and normalized knee points.
    """
    if df is None or df.empty:
        return {
            "minimum_mtow": None,
            "minimum_pfei": None,
            "knee": None,
        }

    d = df[
        np.isfinite(df["mtow_kg"])
        & np.isfinite(df["pfei_MJ_per_kg_km"])
    ].copy()

    if d.empty:
        return {
            "minimum_mtow": None,
            "minimum_pfei": None,
            "knee": None,
        }

    i_mtow = d["mtow_kg"].idxmin()
    i_pfei = d["pfei_MJ_per_kg_km"].idxmin()

    mtow = d["mtow_kg"].to_numpy(dtype=float)
    pfei = d["pfei_MJ_per_kg_km"].to_numpy(dtype=float)

    mtow_span = max(np.ptp(mtow), 1.0e-12)
    pfei_span = max(np.ptp(pfei), 1.0e-12)

    mtow_n = (mtow - np.min(mtow)) / mtow_span
    pfei_n = (pfei - np.min(pfei)) / pfei_span

    distance = np.sqrt(mtow_n**2 + pfei_n**2)
    knee_pos = int(np.argmin(distance))
    i_knee = d.index[knee_pos]

    return {
        "minimum_mtow": d.loc[i_mtow],
        "minimum_pfei": d.loc[i_pfei],
        "knee": d.loc[i_knee],
    }


# =============================================================================
# 10. Plotting
# =============================================================================

def plot_arch_pareto(
    arch: Dict[str, Any],
    df: pd.DataFrame,
    *,
    outfile: Optional[str] = None,
    show: bool = False,
):
    if df is None or df.empty:
        return

    key = arch["key"]
    color = ARCH_COLORS.get(key, "#333333")

    d = df[
        np.isfinite(df["mtow_kg"])
        & np.isfinite(df["pfei_MJ_per_kg_km"])
    ].sort_values("mtow_kg")

    if d.empty:
        return

    fig, ax = plt.subplots(figsize=(8.2, 6.2))

    ax.plot(
        d["mtow_kg"],
        d["pfei_MJ_per_kg_km"],
        "-o",
        color=color,
        linewidth=1.8,
        markersize=4.5,
        label=arch["name"],
    )

    reps = representative_points(d)
    markers = {
        "minimum_mtow": ("s", "Minimum MTOW"),
        "minimum_pfei": ("^", "Minimum PFEI"),
        "knee": ("*", "Knee"),
    }

    for key_name, (marker, label) in markers.items():
        row = reps[key_name]
        if row is None:
            continue

        ax.scatter(
            row["mtow_kg"],
            row["pfei_MJ_per_kg_km"],
            marker=marker,
            s=130 if marker == "*" else 70,
            color=color,
            edgecolor="k",
            linewidth=0.7,
            label=label,
            zorder=5,
        )

    ax.set_xlabel("MTOW [kg]")
    ax.set_ylabel("PFEI [MJ/(kg·km)]")
    ax.set_title(f"{arch['name']}: Pareto front")
    ax.grid(True, alpha=0.30)
    ax.legend(loc="best")

    fig.tight_layout()

    if outfile is None:
        outfile = (
            f"pareto_{arch['name'].replace(' ', '_')}.png"
        )

    fig.savefig(
        outfile,
        dpi=180,
        bbox_inches="tight",
    )

    if show:
        plt.show()

    plt.close(fig)


def plot_combined_pareto(
    pareto_sets: Dict[str, pd.DataFrame],
    *,
    outfile: str = "pareto_all_architectures.png",
    show: bool = False,
):
    fig, ax = plt.subplots(figsize=(9.2, 7.0))

    for arch in ARCHES:
        df = pareto_sets.get(arch["name"])

        if df is None or df.empty:
            continue

        d = df[
            np.isfinite(df["mtow_kg"])
            & np.isfinite(df["pfei_MJ_per_kg_km"])
        ].sort_values("mtow_kg")

        if d.empty:
            continue

        color = ARCH_COLORS.get(
            arch["key"],
            "#333333",
        )

        ax.plot(
            d["mtow_kg"],
            d["pfei_MJ_per_kg_km"],
            "-o",
            color=color,
            linewidth=1.8,
            markersize=4.0,
            label=arch["name"],
        )

        reps = representative_points(d)
        knee = reps["knee"]

        if knee is not None:
            ax.scatter(
                knee["mtow_kg"],
                knee["pfei_MJ_per_kg_km"],
                marker="*",
                s=130,
                color=color,
                edgecolor="k",
                linewidth=0.7,
                zorder=5,
            )

    ax.set_xlabel("MTOW [kg]")
    ax.set_ylabel("PFEI [MJ/(kg·km)]")
    ax.set_title("ADaPT architecture-specific Pareto fronts")
    ax.grid(True, alpha=0.30)
    ax.legend(loc="best")

    fig.tight_layout()
    fig.savefig(
        outfile,
        dpi=180,
        bbox_inches="tight",
    )

    if show:
        plt.show()

    plt.close(fig)


# =============================================================================
# 11. UI-facing API
# =============================================================================

def run_pareto(
    *,
    architectures: Optional[Sequence[Dict[str, Any]]] = None,
    pop_size: int = 160,
    n_gen: int = 260,
    seed: int = 11,
    ground_roll_max_m: Optional[float] = 450.0,
    make_plots: bool = True,
) -> Dict[str, Any]:
    arches = list(
        ARCHES
        if architectures is None
        else architectures
    )

    pareto_sets: Dict[str, pd.DataFrame] = {}
    summary_rows = []

    for arch in arches:
        print(
            Fore.LIGHTGREEN_EX
            + f"→ Pareto optimization: {arch['name']} ..."
            + Fore.RESET
        )

        try:
            df = run_arch_pareto(
                arch,
                pop_size=pop_size,
                n_gen=n_gen,
                seed=seed,
                ground_roll_max_m=ground_roll_max_m,
            )

            pareto_sets[arch["name"]] = df

            reps = representative_points(df)

            for point_name, row in reps.items():
                if row is None:
                    continue

                summary_rows.append(
                    {
                        "arch": arch["name"],
                        "key": arch["key"],
                        "representative_point": point_name,
                        "mtow_kg": row["mtow_kg"],
                        "pfei_MJ_per_kg_km": row[
                            "pfei_MJ_per_kg_km"
                        ],
                        "required_power_kW": row.get(
                            "required_power_kW",
                            np.nan,
                        ),
                        "installed_power_kW": row.get(
                            "installed_power_kW",
                            np.nan,
                        ),
                        "required_consumable_kg": row.get(
                            "required_consumable_kg",
                            np.nan,
                        ),
                        "battery_mass_kg": row.get(
                            "battery_mass_kg",
                            np.nan,
                        ),
                        "tank_mass_kg": row.get(
                            "tank_mass_kg",
                            np.nan,
                        ),
                        "max_constraint_value": row.get(
                            "max_constraint_value",
                            np.nan,
                        ),
                        "feasible": row.get(
                            "feasible",
                            False,
                        ),
                    }
                )

            if make_plots:
                plot_arch_pareto(
                    arch,
                    df,
                    outfile=(
                        f"pareto_{arch['name'].replace(' ', '_')}.png"
                    ),
                )

        except Exception as exc:
            print(
                Fore.RED
                + f"   FAILED: {exc}"
                + Fore.RESET
            )
            pareto_sets[arch["name"]] = pd.DataFrame()

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        "pareto_representative_points.csv",
        index=False,
    )

    if make_plots:
        plot_combined_pareto(
            pareto_sets,
            outfile="pareto_all_architectures.png",
        )

    print(
        Fore.LIGHTGREEN_EX
        + "Saved representative Pareto points -> "
        "pareto_representative_points.csv"
        + Fore.RESET
    )

    if not summary.empty:
        print("\nRepresentative Pareto points:")
        display_columns = [
            "arch",
            "representative_point",
            "mtow_kg",
            "pfei_MJ_per_kg_km",
            "feasible",
        ]
        print(
            summary[
                [c for c in display_columns if c in summary.columns]
            ]
        )

    return {
        "summary": summary,
        "pareto_sets": pareto_sets,
    }


# =============================================================================
# 12. Direct execution
# =============================================================================

def main():
    return run_pareto(
        pop_size=160,
        n_gen=260,
        seed=11,
        ground_roll_max_m=450.0,
        make_plots=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            Fore.RED
            + f"ERROR: {exc}"
            + Fore.RESET
        )
        sys.exit(1)
