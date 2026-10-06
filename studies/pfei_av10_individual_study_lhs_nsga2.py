# pfei_pareto_cluster_study.py
# AV-10 equivalent single-class PFEI-MTOW*-Range Pareto and common-mission audit
#
# Uses the validated AV-10 equivalent mission, geometry, weight and technology settings.

from __future__ import annotations

import os
import sys
import time
import warnings
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Sequence

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import openmdao.api as om

# Optional global-search Pareto refinement. The LHS DOE remains the broad
# coverage stage; NSGA-II is used only as a second-stage optimizer.
try:
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.optimize import minimize as pymoo_minimize
    from pymoo.termination import get_termination
    PYMOO_AVAILABLE = True
    PYMOO_IMPORT_ERROR = None
except Exception as _pymoo_exc:
    ElementwiseProblem = object  # allows this module to import without pymoo
    NSGA2 = None
    pymoo_minimize = None
    get_termination = None
    PYMOO_AVAILABLE = False
    PYMOO_IMPORT_ERROR = _pymoo_exc


# =============================================================================
# Publication-quality plot styling
#
# Pure presentation layer -- does not touch sampling, closure, feasibility,
# or PFEI logic. Centralizes fonts, colors, and axis styling so every figure
# (per-architecture and combined) looks consistent and journal-ready.
# =============================================================================

PLOT_DPI = 400
FIGSIZE_2D = (7.2, 5.4)
FIGSIZE_3D = (8.6, 6.8)

# Colorblind-safe qualitative palette (Okabe-Ito), one fixed color per
# architecture so the same architecture reads identically across every
# figure (per-arch plots and the combined comparison).
ARCH_COLORS: Dict[str, str] = {
    "conventional_reciprocating": "#0072B2",
    "hydrogen_reciprocating": "#D55E00",
    "hydrogen_fuel_cell": "#009E73",
    "battery_only": "#CC79A7",
    "solar_battery": "#E69F00",
    "conventional_battery_hybrid": "#56B4E9",
    "hydrogen_hybrid": "#F0E442",
    "solar_hydrogen_hybrid": "#000000",
}
PARETO_COLOR = "#D62728"       # consistent accent for every Pareto front/marker
INFEASIBLE_COLOR = "#B0B0B0"


def _set_publication_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": PLOT_DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "STIXGeneral"],
        "mathtext.fontset": "stix",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "axes.labelweight": "regular",
        "axes.linewidth": 0.9,
        "axes.edgecolor": "#333333",
        "axes.grid": True,
        "grid.color": "#B0B0B0",
        "grid.alpha": 0.35,
        "grid.linewidth": 0.5,
        "legend.fontsize": 9.5,
        "legend.frameon": True,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "#CCCCCC",
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "lines.markeredgewidth": 0.6,
    })


def _style_axes_2d(ax) -> None:
    """Strip top/right spines and tidy tick locators; shared by all 2D plots."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#333333")
    ax.spines["bottom"].set_color("#333333")
    ax.grid(True, which="major", axis="both")
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=7, prune=None))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=7, prune=None))


_set_publication_style()


# =============================================================================
# Spyder controls
# =============================================================================

SPYDER_MODE = "full"        # "quick" or "full"
SPYDER_ARCHS = [
    "conventional_reciprocating",
    "hydrogen_reciprocating",
    "battery_only",
    "solar_battery",
    # "conventional_battery_hybrid",
]

SPYDER_N_SAMPLES = None      # None => quick=80, full=600 per architecture
SPYDER_OUTPUT_DIR = "pfei_av10_outputs"
SPYDER_SEED = 11
SPYDER_RUN_VALIDATION = False

# =============================================================================
# Publication comparison controls
# =============================================================================
# "common_mission" is the defensible architecture-comparison mode: payload,
# range, cruise-speed bounds, and geometry bounds are identical for every
# architecture. "native" preserves each architecture's original exploratory
# bounds and is useful for architecture-specific design-space interpretation.
RUN_NATIVE_EXPLORATION = True
RUN_COMMON_MISSION_COMPARISON = True

# Common mission shared by every architecture.  This intentionally uses the
# paper comparison basis of 10,000 kg payload and 2,000 km range.  Battery and
# solar-battery are allowed to be infeasible; feasibility is an output, not an
# assumption.
COMMON_RANGE_KM = 2000.0
COMMON_PAYLOAD_KG = 10000.0
COMMON_CRUISE_SPEED_BOUNDS_MPS = (16.0, 21.0)
COMMON_FINENESS_RATIO_BOUNDS = (3.70, 4.50)
COMMON_LENGTH_BOUNDS_M = (95.0, 120.0)

# Technology assumptions are fixed during the common-mission comparison so
# the architecture ranking is not confounded by simultaneously sampling
# future and present-day technology. Native exploration still samples the
# architecture-specific technology bounds defined below.
COMMON_BATTERY_SPECIFIC_ENERGY_WHKG = 300.0
COMMON_BATTERY_VOLUMETRIC_ED_WHL = 650.0
COMMON_SOLAR_IRRADIANCE_WM2 = 600.0

# PFEI accounting basis used for Pareto ranking and plots.
#   "onboard_total": fuel + battery + solar energy handled onboard.
#   "external_supplied": fuel + grid/battery energy; solar is excluded.
# Both metrics are always exported to CSV regardless of this selection.
PFEI_BASIS = "onboard_total"

# Optional upstream/primary-energy multipliers. Keep at 1.0 for a strict
# onboard/tank-to-propulsor comparison. Change only when a documented energy
# pathway scenario is explicitly being studied.
PRIMARY_ENERGY_FACTOR = {
    "conventional_fuel": 1.0,
    "hydrogen": 1.0,
    "grid_electricity": 1.0,
    "solar": 1.0,
}

# Latin-hypercube sampling is used instead of independent random sampling.
USE_LATIN_HYPERCUBE = True

# =============================================================================
# Two-stage global Pareto search: LHS DOE -> NSGA-II refinement
# =============================================================================
# NSGA-II is a stochastic global-search method; it refines the Pareto set but
# does not mathematically prove a unique global optimum. The publication-grade
# workflow therefore retains the LHS cloud, refines it with NSGA-II, combines
# both populations, and recomputes the non-dominated set from the union.
RUN_NSGA2_REFINEMENT = True
NSGA2_QUICK_POP_SIZE = 32
NSGA2_QUICK_N_GEN = 8
NSGA2_FULL_POP_SIZE = 64
NSGA2_FULL_N_GEN = 30
NSGA2_DUPLICATE_DECIMALS = 9
NSGA2_VERBOSE = True

# Native-envelope knee points are intentionally disabled by default because
# the native study has three objectives. Set to "utopia3d" only if a single
# representative native point is explicitly required for an audit. Common-
# mission knees remain two-objective MTOW-PFEI utopia-distance points.
NATIVE_KNEE_MODE = "none"  # "none" or "utopia3d"

# =============================================================================
# AV-10 equivalent single-class audit configuration
# =============================================================================
# This script deliberately studies ONE airship class only.  The bounds below
# are taken from the validated AV-10 equivalent class definition used by the
# architecture-class study, not from the old A-170/native architecture bounds.
AIRSHIP_CLASS_KEY = "av10"
AIRSHIP_CLASS_LABEL = "AV-10 equivalent class"
AV10_REFERENCE_LENGTH_M = 107.5
AV10_REFERENCE_FINENESS_RATIO = 4.00760
AV10_REFERENCE_CRUISE_SPEED_MPS = 20.6
AV10_REFERENCE_MTOW_KG = 21500.0
AV10_REFERENCE_VOLUME_M3 = 40500.0
AV10_REFERENCE_POWER_W = 1500.0e3

# Separate physical feasibility from the validated class-volume domain.  This
# is important for diagnosing statements such as "hydrogen is infeasible".
# The previous class study used a +/-15% reference-volume validity band.
REFERENCE_VOLUME_RATIO_BOUNDS = (0.85, 1.15)
PARETO_FEASIBILITY_MODE = "physics"  # "physics" or "validated_domain"

# Study A: class-envelope exploration.  Payload/range are allowed to vary to
# answer "can this architecture work anywhere inside an AV-10-like mission
# envelope?".  Do NOT use this mode for architecture ranking.
AV10_NATIVE_RANGE_BOUNDS_KM = (300.0, 2000.0)
AV10_NATIVE_PAYLOAD_BOUNDS_KG = (3000.0, 10000.0)
AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS = (16.0, 21.0)
AV10_NATIVE_FINENESS_RATIO_BOUNDS = (3.70, 4.50)
AV10_NATIVE_LENGTH_BOUNDS_M = (95.0, 120.0)
# Native payload/range lower bounds preserve AV-10-scale geometry while allowing
# the optimizer to reveal where emerging architectures first become feasible.
# They do not alter the fixed 10,000 kg / 2,000 km common-mission comparison.

# Technology scenario for this isolated audit.  Start with current technology;
# change to "future" only after the current case has been understood.
TECHNOLOGY_SCENARIO = "current"  # "current" or "future"
TECHNOLOGY_SCENARIOS = {
    "current": {
        "battery_specific_energy_Whkg": 300.0,
        "battery_volumetric_ed_WhL": 650.0,
        "solar_efficiency": 0.26,
        "pv_areal_density_kg_m2": 2.5,
        "solar_irradiance_Wm2": 600.0,
        "solar_availability_factor": 0.65,
        "hydrogen_tank_gravimetric_efficiency": 0.08,
    },
    "future": {
        "battery_specific_energy_Whkg": 600.0,
        "battery_volumetric_ed_WhL": 1000.0,
        "solar_efficiency": 0.35,
        "pv_areal_density_kg_m2": 1.5,
        "solar_irradiance_Wm2": 600.0,
        "solar_availability_factor": 0.75,
        "hydrogen_tank_gravimetric_efficiency": 0.12,
    },
}

# Finalized-model controls
#
# The current AirshipAnalysisGroup internally sizes the mission consumable
# requirement and battery capacity.  The Pareto driver must therefore not
# perform the old external engine-power/fuel fixed-point closure.
NUM_STEPS = 1
CRUISE_ALT_M = 2740.0
T_ENV_K = 281.65
RH_PCT = 70.0

# Common operational field-length requirement used by every architecture.
FIELD_LENGTH_LIMIT_M: Optional[float] = 300.0

# Installed-power closure. The finalized model sizes consumables internally,
# but installed shaft power remains an external sizing input.
POWER_MARGIN = 1.10
POWER_CLOSURE_MAX_ITERS = 20
POWER_CLOSURE_RELAX = 0.55
POWER_CLOSURE_RTOL = 1.0e-3

N_ENGINE = 4.0
N_CREW = 2.0
INSTALLED_SHAFT_POWER_W = {
    "conventional_reciprocating": 1500.0e3,
    "hydrogen_reciprocating": 1500.0e3,
    "hydrogen_fuel_cell": 268.0e3,
    "battery_only": 1500.0e3,
    "solar_battery": 1500.0e3,
    "conventional_battery_hybrid": 268.0e3,
    "hydrogen_hybrid": 220.0e3,
    "solar_hydrogen_hybrid": 220.0e3,
}

# Baseline model inputs used for every sampled outer design.
TVC_H0 = 0.066
TVC_V0 = 0.059
CL0 = 0.15
K_LIFT0 = 0.25
ETA_PROP0 = 0.82
BR_TO0 = 0.90
BR_LDG0 = 0.90
CD0_0 = 0.030
AV10_ICE_SPECIFIC_POWER_WKG = 3000.0
AV10_ICE_THERMAL_EFFICIENCY = 0.36

# Feasibility tolerances.  They remove numerical roundoff only.
CONSTRAINT_TOL = {
    # Numerical tolerances only; these do not replace physical limits.
    "power": 1.0,            # W
    "energy": 1.0e-6,       # native energy-constraint units
    "buoyancy": 1.0,         # N
    "volume": 1.0e-6,        # m^3
    "mass_balance": 1.0e-2,  # kg
    "fc_power": 1.0,         # W
    "lift": 1.0e-6,          # dimensionless
    "ground": 1.0,           # m
    "landing": 1.0,          # m
}


# =============================================================================
# Path setup
# =============================================================================

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
CORE_DIR = os.path.join(PROJECT_ROOT, "core")

for p in [PROJECT_ROOT, CORE_DIR]:
    if p in sys.path:
        sys.path.remove(p)

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, CORE_DIR)

import adapt.AirshipAnalysisGroup as airship_group_module
from adapt.AirshipWeight import AirshipWeight as _BaseAirshipWeight
from adapt.operatingConditions import opCond

ACTIVE_CLASS_KEY = AIRSHIP_CLASS_KEY

class ClassConfiguredAirshipWeight(_BaseAirshipWeight):
    """Validated AV-10 equivalent-class non-rigid weight settings."""
    def __init__(self, **kwargs):
        options = {
            "envelope_areal_density_nonrigid": 0.34,
            "fin_areal_density": 4.20,
            "landing_gear_fraction": 0.0167,
            "miscellaneous_fraction": 0.023,
            "crew_mass_each": 113.0,
        }
        options.update(kwargs)
        super().__init__(**options)

    def compute(self, inputs, outputs):
        super().compute(inputs, outputs)
        if self.options["airship_type"] != "non-rigid":
            return
        gondola_mass = 1000.0
        payload = max(self._scalar(inputs["payload"]), 0.0)
        consumable_mass = max(self._scalar(inputs["consumable_mass"]), 0.0)
        ballast_mass = max(self._scalar(inputs["ballast_mass"]), 0.0)
        envelope_mass = float(outputs["envelope_mass"])
        fin_mass = float(outputs["fin_mass"])
        propulsion_mass = max(self._scalar(inputs["propulsion_mass"]), 0.0)
        power_system_mass = max(self._scalar(inputs["power_system_mass"]), 0.0)
        crew_mass = float(outputs["crew_mass"])
        helium_mass = float(outputs["he_max_mass"])
        if self.options["power_source"] in {
            "hydrogen_reciprocating", "hydrogen_fuel_cell",
            "hydrogen_hybrid", "solar_hydrogen_hybrid",
        }:
            tank_mass = max(self._scalar(inputs["tank_mass"]), 0.0)
        else:
            tank_mass = 0.0
        misc_fraction = float(self.options["miscellaneous_fraction"])
        landing_fraction = float(self.options["landing_gear_fraction"])
        pre_misc = (envelope_mass + gondola_mass + fin_mass + propulsion_mass
                    + power_system_mass + tank_mass + crew_mass)
        miscellaneous_mass = pre_misc * misc_fraction
        base_no_landing = pre_misc + miscellaneous_mass + helium_mass
        mtow = (base_no_landing + payload + consumable_mass + ballast_mass) / max(1.0 - landing_fraction, 1.0e-12)
        landing_mass = landing_fraction * mtow
        owe = base_no_landing + landing_mass
        outputs["gondola_mass"] = gondola_mass
        outputs["miscellaneous_mass"] = miscellaneous_mass
        outputs["landing_system_mass"] = landing_mass
        outputs["owe"] = owe
        outputs["mtow"] = mtow
        outputs["operational_weight"] = owe + payload
        outputs["structure_mass"] = envelope_mass + gondola_mass + fin_mass + landing_mass + miscellaneous_mass + helium_mass
        outputs["installed_system_mass"] = propulsion_mass + power_system_mass + tank_mass
        outputs["useful_load_mass"] = payload + crew_mass
        outputs["installed_consumable_mass"] = consumable_mass
        outputs["mass_balance_error"] = mtow - (owe + payload + consumable_mass + ballast_mass)

airship_group_module.AirshipWeight = ClassConfiguredAirshipWeight
AirshipAnalysisGroup = airship_group_module.AirshipAnalysisGroup


# =============================================================================
# Architecture definitions
# =============================================================================

@dataclass
class ArchConfig:
    label: str
    power_source: str
    has_fuel: bool
    has_battery: bool
    has_solar: bool
    has_tank: bool
    hybrid: bool
    useful_energy_MJ_per_kg: float
    pfei_energy_basis: str
    installed_shaft_power_W: float
    storage_type: str
    bounds: Dict[str, Tuple[float, float]]
    battery_specific_energy_Whkg: float = 400.0
    battery_volumetric_ed_WhL: float = 750.0
    solar_irradiance_Wm2: float = 600.0


ARCH_CONFIGS: Dict[str, ArchConfig] = {
    "conventional_reciprocating": ArchConfig(
        label="Conventional ICE",
        power_source="conventional_reciprocating",
        has_fuel=True, has_battery=False, has_solar=False,
        has_tank=False, hybrid=False,
        useful_energy_MJ_per_kg=43.0,
        pfei_energy_basis="fuel",
        installed_shaft_power_W=1500.0e3,
        storage_type="helium",
        bounds={
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
        },
    ),
    "hydrogen_reciprocating": ArchConfig(
        label="Hydrogen ICE",
        power_source="hydrogen_reciprocating",
        has_fuel=True, has_battery=False, has_solar=False,
        has_tank=True, hybrid=False,
        useful_energy_MJ_per_kg=120.0,
        pfei_energy_basis="fuel",
        installed_shaft_power_W=1500.0e3,
        storage_type="liquid_h2",
        bounds={
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
        },
    ),
    "hydrogen_fuel_cell": ArchConfig(
        label="Hydrogen Fuel Cell",
        power_source="hydrogen_fuel_cell",
        has_fuel=True, has_battery=False, has_solar=False,
        has_tank=True, hybrid=False,
        useful_energy_MJ_per_kg=120.0,
        pfei_energy_basis="fuel",
        installed_shaft_power_W=268.0e3,
        storage_type="liquid_h2",
        bounds={
            "range_km": (300.0, 1600.0),
            "payload_kg": (300.0, 1000.0),
            "cruise_speed_mps": (14.0, 24.0),
            "fineness_ratio": (3.5, 4.8),
            "length_m": (60.0, 75.0),
        },
    ),
    "battery_only": ArchConfig(
        label="Battery Electric",
        power_source="battery_only",
        has_fuel=False, has_battery=True, has_solar=False,
        has_tank=False, hybrid=False,
        useful_energy_MJ_per_kg=0.0,
        pfei_energy_basis="battery",
        installed_shaft_power_W=1500.0e3,
        storage_type="helium",
        battery_specific_energy_Whkg=400.0,
        battery_volumetric_ed_WhL=750.0,
        bounds={
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
            "battery_specific_energy_Whkg": (250.0, 600.0),
            "battery_volumetric_ed_WhL": (500.0, 1000.0),
        },
    ),
    "solar_battery": ArchConfig(
        label="Solar-Battery",
        power_source="solar_battery",
        has_fuel=False, has_battery=True, has_solar=True,
        has_tank=False, hybrid=False,
        useful_energy_MJ_per_kg=0.0,
        pfei_energy_basis="battery_solar",
        installed_shaft_power_W=1500.0e3,
        storage_type="helium",
        battery_specific_energy_Whkg=400.0,
        battery_volumetric_ed_WhL=750.0,
        bounds={
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
            "battery_specific_energy_Whkg": (250.0, 600.0),
            "battery_volumetric_ed_WhL": (500.0, 1000.0),
            "solar_area_m2": (50.0, 400.0),
        },
    ),
    "conventional_battery_hybrid": ArchConfig(
        label="Conventional-Battery Hybrid",
        power_source="conventional_battery_hybrid",
        has_fuel=True, has_battery=True, has_solar=False,
        has_tank=False, hybrid=True,
        useful_energy_MJ_per_kg=43.0,
        pfei_energy_basis="fuel_battery",
        installed_shaft_power_W=268.0e3,
        storage_type="helium",
        battery_specific_energy_Whkg=400.0,
        battery_volumetric_ed_WhL=750.0,
        bounds={
            # Kept consistent with the finalized hybrid DSE.
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
            "chi": (0.05, 0.35),
            "tau": (0.10, 0.60),
            "battery_specific_energy_Whkg": (250.0, 600.0),
            "battery_volumetric_ed_WhL": (500.0, 1000.0),
        },
    ),
    "hydrogen_hybrid": ArchConfig(
        label="Hydrogen Fuel-Cell/Battery Hybrid",
        power_source="hydrogen_hybrid",
        has_fuel=True, has_battery=True, has_solar=False,
        has_tank=True, hybrid=True,
        useful_energy_MJ_per_kg=120.0,
        pfei_energy_basis="fuel_battery",
        installed_shaft_power_W=220.0e3,
        storage_type="liquid_h2",
        bounds={
            "range_km": (250.0, 1200.0),
            "payload_kg": (250.0, 900.0),
            "cruise_speed_mps": (14.0, 24.0),
            "fineness_ratio": (3.8, 4.8),
            "length_m": (60.0, 80.0),
            "chi": (0.05, 0.35),
            "tau": (0.10, 0.60),
            "battery_specific_energy_Whkg": (250.0, 600.0),
            "battery_volumetric_ed_WhL": (500.0, 1000.0),
        },
    ),
    "solar_hydrogen_hybrid": ArchConfig(
        label="Solar-Hydrogen Hybrid",
        power_source="solar_hydrogen_hybrid",
        has_fuel=True, has_battery=True, has_solar=True,
        has_tank=True, hybrid=True,
        useful_energy_MJ_per_kg=120.0,
        pfei_energy_basis="fuel_battery_solar",
        installed_shaft_power_W=220.0e3,
        storage_type="liquid_h2",
        bounds={
            "range_km": (250.0, 1200.0),
            "payload_kg": (250.0, 900.0),
            "cruise_speed_mps": (14.0, 24.0),
            "fineness_ratio": (3.8, 4.8),
            "length_m": (60.0, 80.0),
            "chi": (0.05, 0.35),
            "tau": (0.10, 0.60),
            "battery_specific_energy_Whkg": (250.0, 600.0),
            "battery_volumetric_ed_WhL": (500.0, 1000.0),
            "solar_area_m2": (50.0, 300.0),
        },
    ),
}



def _isfinite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def _get_scalar(
    prob: om.Problem,
    names: Sequence[str] | str,
    units: Optional[str] = None,
    default: float = np.nan,
    reducer: str = "first",
) -> float:
    """Read the first available OpenMDAO variable alias."""
    if isinstance(names, str):
        names = [names]

    for name in names:
        try:
            value = prob.get_val(name, units=units)
            arr = np.asarray(value, dtype=float).reshape(-1)
            if arr.size == 0:
                continue
            result = float(np.max(arr)) if reducer == "max" else float(arr[0])
            if np.isfinite(result):
                return result
        except Exception:
            continue
    return default


def _safe_set(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
    required: bool = True,
) -> bool:
    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
        return True
    except Exception as exc:
        if required:
            raise RuntimeError(
                f"Required promoted model input {name!r} could not be set."
            ) from exc
        return False


def _consumable_mass(prob: om.Problem, arch: str) -> float:
    """Return the finalized model's authoritative mission consumable mass."""
    cfg = ARCH_CONFIGS[arch]
    if not cfg.has_fuel:
        return 0.0

    if arch in {
        "hydrogen_reciprocating",
        "hydrogen_fuel_cell",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
    }:
        return _get_scalar(
            prob,
            ["hydrogen_mass", "required_consumable_mass",
             "installed_consumable_mass", "fuel_mass"],
            units="kg",
            reducer="max",
        )

    return _get_scalar(
        prob,
        ["required_consumable_mass", "installed_consumable_mass", "fuel_mass"],
        units="kg",
        reducer="max",
    )


def _battery_energy_Wh(prob: om.Problem, design: Dict[str, float]) -> float:
    """Return required battery energy without assuming one legacy variable name."""
    direct = _get_scalar(
        prob,
        [
            "battery_capacity",
            "battery_energy",
            "battery_energy_required",
            "required_battery_energy",
            "mission_battery_energy",
        ],
        units="W*h",
        default=np.nan,
    )
    if np.isfinite(direct):
        return direct

    battery_mass = _get_scalar(
        prob,
        ["battery_mass", "battery_pack_mass", "energy_storage_mass"],
        units="kg",
        default=np.nan,
    )
    specific_energy = float(
        design.get(
            "battery_specific_energy_Whkg",
            design.get("battery_specific_energy", 400.0),
        )
    )
    if np.isfinite(battery_mass):
        return battery_mass * specific_energy
    return np.nan


# =============================================================================
# Model construction
# =============================================================================

def make_problem(
    arch: str,
    num_steps: int = NUM_STEPS,
) -> om.Problem:
    """Build one finalized AirshipAnalysisGroup instance."""
    cfg = ARCH_CONFIGS[arch]

    phd = opCond(
        name="Cruise",
        T_env=T_ENV_K,
        altitude=CRUISE_ALT_M,
        speed=AV10_REFERENCE_CRUISE_SPEED_MPS / 337.5,
        time="day",
        RH=RH_PCT,
    )

    model = AirshipAnalysisGroup(
        phd=phd,
        power_source=cfg.power_source,
        airship_type="non-rigid",
        landing_system="conventional",
        enable_pressure_control=False,
        num_steps=num_steps,
        use_prescribed_consumable_capacity=False,
    )

    # Resolve promoted-input metadata ambiguity before setup.
    model.set_input_defaults(
        "cruise_altp",
        val=np.full(num_steps, CRUISE_ALT_M),
        units="m",
    )
    model.set_input_defaults(
        "range",
        val=COMMON_RANGE_KM * 1000.0,
        units="m",
    )

    model.set_input_defaults(
        "cruise_speed",
        val=np.full(num_steps, AV10_REFERENCE_CRUISE_SPEED_MPS),
        units="m/s",
    )

    prob = om.Problem(model=model)
    prob.setup(check=False, force_alloc_complex=False)

    # AirshipAnalysisGroup exposes the mission/performance discipline as
    # ``performance`` (AirshipPerformance), not ``mission``.  Older versions
    # of this study looked for prob.model.mission, which caused every DOE row
    # to fail before the model was ever executed.
    #
    # Keep a compatibility fallback to ``mission`` in case an older local
    # AirshipAnalysisGroup is used, but prefer the finalized/current name.
    if FIELD_LENGTH_LIMIT_M is not None:
        performance = getattr(prob.model, "performance", None)
        if performance is None:
            performance = getattr(prob.model, "mission", None)

        if performance is None:
            available = sorted(
                name for name in getattr(prob.model, "_subsystems_allprocs", {}).keys()
            )
            raise RuntimeError(
                "AirshipAnalysisGroup has neither a 'performance' nor a 'mission' "
                "subsystem after setup; cannot apply field-length requirement. "
                f"Available subsystems: {available}"
            )

        if "field_length_limit" not in performance.options:
            raise RuntimeError(
                "The performance subsystem does not expose the option "
                "'field_length_limit'."
            )

        performance.options["field_length_limit"] = float(FIELD_LENGTH_LIMIT_M)

    try:
        prob.model.nonlinear_solver.options["err_on_non_converge"] = True
    except Exception:
        pass

    # Preflight sanity check: this catches model-API mismatches once, before
    # hundreds of DOE samples are attempted.
    if not hasattr(prob.model, "performance") and not hasattr(prob.model, "mission"):
        raise RuntimeError(
            "Model preflight failed: no performance/mission subsystem is present."
        )

    return prob


# =============================================================================
# Design sampling
# =============================================================================

def _study_bounds(cfg: ArchConfig, study_kind: str) -> Dict[str, Tuple[float, float]]:
    """Return AV-10-specific bounds for the two audit studies.

    native: exploratory AV-10 mission envelope, identical for all architectures.
    common_mission: exact AV-10 nominal payload/range, identical for all architectures.
    """
    if study_kind == "native":
        bounds: Dict[str, Tuple[float, float]] = {
            "range_km": AV10_NATIVE_RANGE_BOUNDS_KM,
            "payload_kg": AV10_NATIVE_PAYLOAD_BOUNDS_KG,
            "cruise_speed_mps": AV10_NATIVE_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": AV10_NATIVE_FINENESS_RATIO_BOUNDS,
            "length_m": AV10_NATIVE_LENGTH_BOUNDS_M,
        }
    elif study_kind == "common_mission":
        bounds = {
            "range_km": (COMMON_RANGE_KM, COMMON_RANGE_KM),
            "payload_kg": (COMMON_PAYLOAD_KG, COMMON_PAYLOAD_KG),
            "cruise_speed_mps": COMMON_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio": COMMON_FINENESS_RATIO_BOUNDS,
            "length_m": COMMON_LENGTH_BOUNDS_M,
        }
    else:
        raise ValueError(f"Unknown study_kind: {study_kind!r}")

    # Technology is fixed by TECHNOLOGY_SCENARIO so feasibility is not obtained
    # by silently sampling optimistic technology assumptions.
    if cfg.hybrid:
        bounds["chi"] = cfg.bounds.get("chi", (0.05, 0.35))
        bounds["tau"] = cfg.bounds.get("tau", (0.10, 0.60))
    if cfg.has_solar:
        bounds["solar_coverage_fraction"] = (0.05, 0.35)
    return bounds


def _latin_hypercube_unit(n: int, d: int, seed: int) -> np.ndarray:
    """Dependency-light Latin hypercube in [0, 1]^d."""
    if n <= 0 or d <= 0:
        return np.empty((max(n, 0), max(d, 0)))
    rng = np.random.default_rng(seed)
    u = np.empty((n, d), dtype=float)
    for j in range(d):
        strata = (np.arange(n, dtype=float) + rng.random(n)) / n
        rng.shuffle(strata)
        u[:, j] = strata
    return u


def sample_designs(
    cfg: ArchConfig,
    n: int,
    seed: int,
    study_kind: str = "native",
) -> pd.DataFrame:
    """Sample one architecture using reproducible Latin hypercube sampling."""
    bounds = _study_bounds(cfg, study_kind)
    keys = list(bounds.keys())
    varying = [k for k in keys if bounds[k][0] != bounds[k][1]]

    if USE_LATIN_HYPERCUBE and varying:
        unit = _latin_hypercube_unit(n, len(varying), seed)
    else:
        rng = np.random.default_rng(seed)
        unit = rng.random((n, len(varying))) if varying else np.empty((n, 0))

    rows: List[Dict[str, float]] = []
    for i in range(n):
        row: Dict[str, float] = {}
        j = 0
        for key in keys:
            lo, hi = bounds[key]
            if lo == hi:
                row[key] = float(lo)
            else:
                row[key] = float(lo + unit[i, j] * (hi - lo))
                j += 1
        row["study_kind"] = study_kind
        rows.append(row)
    return pd.DataFrame(rows)

def estimate_prolate_wetted_area(length_m: float, fineness_ratio: float) -> float:
    """Approximate AV-10 envelope wetted area for solar-coverage limiting."""
    length = max(float(length_m), 1.0e-9)
    fineness = max(float(fineness_ratio), 1.000001)
    diameter = length / fineness
    a = 0.5 * length
    b = 0.5 * diameter
    e2 = max(1.0 - (b*b)/(a*a), 0.0)
    e = np.sqrt(e2)
    if e < 1.0e-8:
        return float(4.0 * np.pi * a * a)
    return float(2.0*np.pi*b*b*(1.0 + (a/(b*e))*np.arcsin(e)))


def apply_design(
    prob: om.Problem,
    arch: str,
    design: Dict[str, float],
    num_steps: int = NUM_STEPS,
) -> None:
    """Apply one sampled design to the finalized promoted model inputs."""
    cfg = ARCH_CONFIGS[arch]

    # Outer Pareto/DSE coordinates
    _safe_set(prob, "range", float(design["range_km"]) * 1000.0, "m")
    _safe_set(prob, "payload", float(design["payload_kg"]), "kg")
    _safe_set(
        prob,
        "cruise_speed",
        np.full(num_steps, float(design["cruise_speed_mps"])),
        "m/s",
    )
    _safe_set(prob, "fineness_ratio", float(design["fineness_ratio"]))
    _safe_set(prob, "length", float(design["length_m"]), "m")

    # Fixed mission/environment values
    _safe_set(prob, "cruise_altp", np.full(num_steps, CRUISE_ALT_M), "m")
    _safe_set(prob, "cruise_disa", np.zeros(num_steps), "K")
    _safe_set(prob, "tailwind_speed", 0.0, "m/s")
    _safe_set(prob, "n_engine", N_ENGINE)
    _safe_set(prob, "n_crew", N_CREW)
    _safe_set(prob, "ballast_mass", 0.0, "kg")

    # Fixed aerodynamic/control starting values
    _safe_set(prob, "tail_volume_coeff_horizontal", TVC_H0)
    _safe_set(prob, "tail_volume_coeff_vertical", TVC_V0)
    _safe_set(prob, "propeller_efficiency", ETA_PROP0)
    if arch in {"conventional_reciprocating", "hydrogen_reciprocating"}:
        _safe_set(prob, "ice_specific_power", AV10_ICE_SPECIFIC_POWER_WKG, "W/kg", required=False)
        _safe_set(prob, "ice_thermal_efficiency", AV10_ICE_THERMAL_EFFICIENCY, required=False)
    _safe_set(prob, "lift_coeff", CL0)
    _safe_set(prob, "drag_due_to_lift_factor", K_LIFT0)
    _safe_set(prob, "drag_coeff_zero", CD0_0)
    _safe_set(prob, "BR_takeoff", BR_TO0)
    _safe_set(prob, "BR_landing", BR_LDG0)
    _safe_set(prob, "thrust_vector_angle", 0.0, "deg")

    # Current propulsion interface
    _safe_set(
        prob,
        "installed_shaft_power",
        float(cfg.installed_shaft_power_W),
        "W",
    )

    # Legacy compatibility inputs are optional; they are not used for sizing
    # in the finalized model.
    _safe_set(
        prob,
        "fuel_onboard_mass",
        np.zeros(num_steps),
        "kg",
        required=False,
    )
    _safe_set(prob, "storage_type", cfg.storage_type, required=False)

    # Battery/hybrid technology variables
    if cfg.has_battery:
        specific_energy = float(
            design.get(
                "battery_specific_energy_Whkg",
                cfg.battery_specific_energy_Whkg,
            )
        )
        volumetric_density = float(
            design.get(
                "battery_volumetric_ed_WhL",
                cfg.battery_volumetric_ed_WhL,
            )
        )
        _safe_set(
            prob,
            "battery_specific_energy",
            specific_energy,
            "W*h/kg",
        )
        _safe_set(
            prob,
            "battery_volumetric_ed",
            volumetric_density,
            "W*h/L",
        )

    # Fixed technology scenario: identical assumptions are applied to both
    # native-envelope and common-mission studies.
    tech = TECHNOLOGY_SCENARIOS[TECHNOLOGY_SCENARIO]
    if cfg.has_battery:
        _safe_set(prob, "battery_specific_energy", tech["battery_specific_energy_Whkg"], "W*h/kg")
        _safe_set(prob, "battery_volumetric_ed", tech["battery_volumetric_ed_WhL"], "W*h/L")
    if cfg.has_solar:
        for aliases, value, units in [
            (("solar_efficiency", "pv_efficiency"), tech["solar_efficiency"], None),
            (("pv_areal_density", "solar_panel_areal_density", "solar_areal_density"), tech["pv_areal_density_kg_m2"], "kg/m**2"),
            (("solar_irradiance", "irradiance"), tech["solar_irradiance_Wm2"], "W/m**2"),
            (("solar_availability_factor", "solar_availability"), tech["solar_availability_factor"], None),
        ]:
            for alias in aliases:
                if _safe_set(prob, alias, value, units, required=False):
                    break
    if cfg.has_tank:
        set_ok = False
        for alias in ("hydrogen_tank_gravimetric_efficiency", "tank_gravimetric_efficiency",
                      "tank_gravimetric_index", "hydrogen_storage_gravimetric_efficiency"):
            if _safe_set(prob, alias, tech["hydrogen_tank_gravimetric_efficiency"], required=False):
                set_ok = True
                break
        if not set_ok:
            raise RuntimeError("Hydrogen tank gravimetric-efficiency input not found; refusing an unaudited H2 run.")

    if cfg.hybrid:
        # chi and tau are physically distinct model inputs.  The previous
        # Pareto script incorrectly forced chi=tau.
        _safe_set(prob, "chi", float(design.get("chi", 0.15)))
        _safe_set(prob, "tau", float(design.get("tau", 0.30)))

    if cfg.has_solar:
        coverage = float(design.get("solar_coverage_fraction", 0.20))
        wetted = estimate_prolate_wetted_area(
            float(design["length_m"]), float(design["fineness_ratio"])
        )
        solar_area = coverage * wetted
        design["estimated_wetted_area_m2"] = wetted
        design["solar_area_m2"] = solar_area
        _safe_set(prob, "solar_area", solar_area, "m**2")
        _safe_set(
            prob,
            "solar_irradiance",
            np.full(num_steps, cfg.solar_irradiance_Wm2),
            "W/m**2",
            required=False,
        )


def run_physics(
    prob: om.Problem,
    arch: str,
    num_steps: int = NUM_STEPS,
) -> Tuple[bool, float]:
    """
    Close installed shaft power against the model-computed required shaft power.

    Mission consumable and battery sizing remain internal to the finalized
    AirshipAnalysisGroup. Only installed power is externally closed because it
    is still an independent sizing input.
    """
    cfg = ARCH_CONFIGS[arch]
    installed = float(cfg.installed_shaft_power_W)
    last_error = np.inf

    for _ in range(POWER_CLOSURE_MAX_ITERS):
        _safe_set(
            prob,
            "installed_shaft_power",
            np.full(num_steps, installed),
            "W",
        )
        prob.run_model()

        required = _get_scalar(
            prob,
            ["required_shaft_power", "required_power"],
            units="W",
            default=np.nan,
            reducer="max",
        )
        if not np.isfinite(required) or required <= 0.0:
            return False, np.inf

        target = max(required * POWER_MARGIN, 1.0)
        new_installed = installed + POWER_CLOSURE_RELAX * (target - installed)
        last_error = abs(new_installed - installed) / max(abs(installed), 1.0)
        installed = new_installed

        if last_error < POWER_CLOSURE_RTOL:
            break

    _safe_set(
        prob,
        "installed_shaft_power",
        np.full(num_steps, installed),
        "W",
    )
    prob.run_model()

    required_final = _get_scalar(
        prob,
        ["required_shaft_power", "required_power"],
        units="W",
        default=np.nan,
        reducer="max",
    )
    if not np.isfinite(required_final):
        return False, np.inf

    power_margin = installed - required_final
    converged = (
        np.isfinite(last_error)
        and last_error < max(5.0 * POWER_CLOSURE_RTOL, 5.0e-3)
        and power_margin >= -CONSTRAINT_TOL["power"]
    )
    return bool(converged), float(last_error)


# =============================================================================
# Output extraction
# =============================================================================

def extract_outputs(
    prob: om.Problem,
    arch: str,
    design: Dict[str, float],
) -> Dict[str, float]:
    cfg = ARCH_CONFIGS[arch]
    out: Dict[str, float] = {}

    out["mtow_kg"] = _get_scalar(prob, "mtow", "kg")
    out["oew_kg"] = _get_scalar(prob, "owe", "kg")
    out["gross_volume_m3"] = _get_scalar(prob, "gross_volume", "m**3")
    out["reference_volume_ratio"] = (
        out["gross_volume_m3"] / AV10_REFERENCE_VOLUME_M3
        if np.isfinite(out["gross_volume_m3"]) else np.nan
    )
    lo_vr, hi_vr = REFERENCE_VOLUME_RATIO_BOUNDS
    out["within_reference_volume_domain"] = bool(
        np.isfinite(out["reference_volume_ratio"])
        and lo_vr <= out["reference_volume_ratio"] <= hi_vr
    )
    out["he_max_mass_kg"] = _get_scalar(prob, "he_max_mass", "kg")

    out["required_power_kW"] = (
        _get_scalar(
            prob,
            ["required_shaft_power", "required_power"],
            "W",
            reducer="max",
        )
        / 1000.0
    )
    out["cruise_shaft_power_kW"] = (
        _get_scalar(
            prob,
            ["required_shaft_power", "required_power"],
            "W",
            reducer="max",
        )
        / 1000.0
    )
    out["engine_power_kW"] = (
        _get_scalar(
            prob,
            ["installed_shaft_power", "rated_shaft_power"],
            "W",
            reducer="max",
            default=cfg.installed_shaft_power_W,
        )
        / 1000.0
    )

    out["ground_roll_m"] = _get_scalar(
        prob,
        [
            "ground_roll",
            "ground_roll_m",
            "takeoff_ground_roll",
            "ground_roll_distance",
        ],
        "m",
        default=np.nan,
    )
    out["landing_distance_m"] = _get_scalar(
        prob, "landing_distance", "m", default=np.nan
    )
    out["endurance_h"] = _get_scalar(
        prob, "endurance", "h", default=np.nan
    )

    out["fuel_mass_kg"] = _consumable_mass(prob, arch)
    out["battery_capacity_Wh"] = (
        _battery_energy_Wh(prob, design) if cfg.has_battery else 0.0
    )
    out["battery_mass_kg"] = (
        _get_scalar(
            prob,
            ["battery_mass", "battery_pack_mass", "energy_storage_mass"],
            "kg",
            default=np.nan,
        )
        if cfg.has_battery else 0.0
    )
    out["solar_energy_Wh"] = (
        _get_scalar(
            prob,
            ["solar_energy_generated", "solar_energy"],
            "W*h",
            default=0.0,
        )
        if cfg.has_solar else 0.0
    )
    out["tank_mass_kg"] = (
        _get_scalar(prob, "tank_mass", "kg", default=0.0)
        if cfg.has_tank else 0.0
    )

    # Finalized constraint and closure diagnostics
    out["power_constraint"] = _get_scalar(
        prob, "power_constraint", "W", reducer="max"
    )
    out["energy_constraint"] = _get_scalar(
        prob, "energy_constraint", default=np.nan, reducer="max"
    )
    out["buoyancy_constraint"] = _get_scalar(
        prob, "buoyancy_constraint", "N", reducer="max"
    )
    out["envelope_volume_violation"] = _get_scalar(
        prob, "envelope_volume_violation", "m**3"
    )
    out["mass_balance_error_kg"] = _get_scalar(
        prob, "mass_balance_error", "kg", default=0.0
    )
    out["fc_power_shortfall"] = _get_scalar(
        prob, "fc_power_shortfall", "W", default=np.nan, reducer="max"
    )

    # Operational diagnostics. These are exported for interpretation but are
    # not Pareto rejection criteria because this driver does not run the DSE
    # inner take-off/landing control optimisation.
    out["lift_constraint"] = _get_scalar(
        prob, "lift_constraint", default=np.nan, reducer="max"
    )
    out["ground_constraint"] = _get_scalar(
        prob, "ground_constraint", "m", default=np.nan, reducer="max"
    )
    out["landing_constraint"] = _get_scalar(
        prob, "landing_constraint", "m", default=np.nan, reducer="max"
    )

    try:
        performance = getattr(prob.model, "performance", None)
        if performance is None:
            performance = getattr(prob.model, "mission", None)
        out["field_length_limit_m"] = (
            float(performance.options["field_length_limit"])
            if performance is not None else np.nan
        )
    except Exception:
        out["field_length_limit_m"] = np.nan

    field_limit = out["field_length_limit_m"]
    out["ground_roll_margin_m"] = (
        field_limit - out["ground_roll_m"]
        if np.isfinite(field_limit) and np.isfinite(out["ground_roll_m"])
        else np.nan
    )
    out["landing_margin_m"] = (
        field_limit - out["landing_distance_m"]
        if np.isfinite(field_limit) and np.isfinite(out["landing_distance_m"])
        else np.nan
    )

    return out


def estimate_pfei(row: Dict[str, Any], cfg: ArchConfig) -> Dict[str, float]:
    """Compute transparent, architecture-consistent energy-intensity metrics.

    Two metrics are exported:
      * onboard-total PFEI counts every onboard mission-energy contribution,
        including solar energy generated during flight;
      * external-supplied PFEI counts fuel and grid/battery energy but excludes
        solar generation from the supplied-energy numerator.

    The selected global ``PFEI_BASIS`` determines which metric is used for the
    Pareto front, while both remain available in the output CSV.
    """
    range_km = max(float(row["range_km"]), 1.0e-9)
    payload_kg = max(float(row["payload_kg"]), 1.0e-9)
    transport_work = payload_kg * range_km

    fuel_mass = max(float(row.get("fuel_mass_kg", 0.0)), 0.0)
    battery_Wh = max(float(row.get("battery_capacity_Wh", 0.0)), 0.0)
    solar_Wh = max(float(row.get("solar_energy_Wh", 0.0)), 0.0)

    fuel_energy_MJ = fuel_mass * cfg.useful_energy_MJ_per_kg if cfg.has_fuel else 0.0
    battery_energy_MJ = battery_Wh * 0.0036 if cfg.has_battery else 0.0
    solar_energy_MJ = solar_Wh * 0.0036 if cfg.has_solar else 0.0

    is_hydrogen = cfg.storage_type == "liquid_h2"
    fuel_factor = PRIMARY_ENERGY_FACTOR[
        "hydrogen" if is_hydrogen else "conventional_fuel"
    ]
    battery_factor = PRIMARY_ENERGY_FACTOR["grid_electricity"]
    solar_factor = PRIMARY_ENERGY_FACTOR["solar"]

    onboard_total_MJ = fuel_energy_MJ + battery_energy_MJ + solar_energy_MJ
    external_supplied_MJ = fuel_energy_MJ + battery_energy_MJ
    primary_total_MJ = (
        fuel_energy_MJ * fuel_factor
        + battery_energy_MJ * battery_factor
        + solar_energy_MJ * solar_factor
    )

    pfei_onboard = onboard_total_MJ / transport_work
    pfei_external = external_supplied_MJ / transport_work
    pfei_primary = primary_total_MJ / transport_work

    if PFEI_BASIS == "onboard_total":
        selected = pfei_onboard
        selected_energy = onboard_total_MJ
    elif PFEI_BASIS == "external_supplied":
        selected = pfei_external
        selected_energy = external_supplied_MJ
    elif PFEI_BASIS == "primary_scenario":
        selected = pfei_primary
        selected_energy = primary_total_MJ
    else:
        raise ValueError(
            "PFEI_BASIS must be 'onboard_total', 'external_supplied', "
            "or 'primary_scenario'."
        )

    return {
        "transport_work_kg_km": transport_work,
        "fuel_energy_MJ": fuel_energy_MJ,
        "battery_energy_MJ": battery_energy_MJ,
        "solar_energy_MJ": solar_energy_MJ,
        "onboard_total_energy_MJ": onboard_total_MJ,
        "external_supplied_energy_MJ": external_supplied_MJ,
        "primary_scenario_energy_MJ": primary_total_MJ,
        "pfei_onboard_MJ_per_kg_km": pfei_onboard,
        "pfei_external_MJ_per_kg_km": pfei_external,
        "pfei_primary_scenario_MJ_per_kg_km": pfei_primary,
        "total_energy_MJ": selected_energy,
        "pfei_MJ_per_kg_km": selected,
        "pfei_basis": PFEI_BASIS,
    }

def check_feasible(
    row: Dict[str, Any],
    arch: str,
) -> Tuple[bool, str]:
    """
    Pareto-study feasibility using the same architecture-level physics logic
    as the original working Pareto driver.

    Important
    ---------
    Static/aerodynamic lift feasibility is a physical requirement and is
    therefore enforced here through ``lift_constraint <= tolerance``.

    Ground-roll and landing-distance constraints remain diagnostics only in
    this outer Pareto driver because their satisfaction requires the separate
    operational/control optimization used by the DSE workflow. They are still
    exported to CSV but are deliberately not Pareto rejection criteria.
    """
    cfg = ARCH_CONFIGS[arch]

    mtow = float(row.get("mtow_kg", np.nan))
    pfei = float(row.get("pfei_MJ_per_kg_km", np.nan))

    if not np.isfinite(mtow) or mtow <= 0.0:
        return False, "bad_mtow"
    if not np.isfinite(pfei) or pfei <= 0.0:
        return False, "bad_pfei"

    # Essential model outputs must be finite and positive.
    for name in ("gross_volume_m3", "required_power_kW", "engine_power_kW"):
        value = float(row.get(name, np.nan))
        if not np.isfinite(value) or value <= 0.0:
            return False, f"bad_{name}"

    # Core architecture constraints only. These are the constraints used by
    # the original Pareto cloud logic and are meaningful without an inner
    # operational-control optimisation.
    core_checks = [
        ("power_constraint", "power"),
        ("buoyancy_constraint", "buoyancy"),
        ("envelope_volume_violation", "volume"),
        ("lift_constraint", "lift"),
    ]

    # Fuel-only architectures expose a consumable energy inequality. Battery
    # architectures close required battery capacity algebraically, so their
    # energy_constraint is not required as a separate rejection test.
    if not cfg.has_battery:
        core_checks.append(("energy_constraint", "energy"))

    for name, tol_key in core_checks:
        value = row.get(name, np.nan)
        try:
            value = float(value)
        except Exception:
            return False, f"missing_{name}"

        if not np.isfinite(value):
            return False, f"missing_{name}"

        if value > CONSTRAINT_TOL[tol_key]:
            return False, name

    # Independent installed-power verification.
    installed_W = 1000.0 * float(row["engine_power_kW"])
    required_W = 1000.0 * float(row["required_power_kW"])
    if required_W - installed_W > CONSTRAINT_TOL["power"]:
        return False, "installed_power_shortfall"

    # Mass closure is required whenever the finalized model reports it.
    mass_balance = float(row.get("mass_balance_error_kg", np.nan))
    if np.isfinite(mass_balance):
        if abs(mass_balance) > CONSTRAINT_TOL["mass_balance"]:
            return False, "mass_balance_error"

    # Fuel-cell-specific power availability.
    if arch in {
        "hydrogen_fuel_cell",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
    }:
        fc_shortfall = float(row.get("fc_power_shortfall", np.nan))
        if np.isfinite(fc_shortfall):
            if fc_shortfall > CONSTRAINT_TOL["fc_power"]:
                return False, "fc_power_shortfall"

    # Ground-roll, landing-distance, and direct field-length diagnostics are
    # intentionally not rejection criteria in this outer architecture study.
    # Lift, however, is enforced above as a core physical feasibility condition.
    return True, "feasible"


# =============================================================================
# Evaluation of a single design
# =============================================================================

def evaluate_design(
    arch: str,
    design: Dict[str, float],
    num_steps: int = NUM_STEPS,
) -> Dict[str, Any]:
    cfg = ARCH_CONFIGS[arch]
    out = dict(design)
    out["arch"] = arch
    out["arch_label"] = cfg.label

    t0 = time.time()
    prob: Optional[om.Problem] = None
    try:
        prob = make_problem(arch, num_steps=num_steps)
        apply_design(prob, arch, design, num_steps=num_steps)
        model_converged, closure_error = run_physics(prob, arch, num_steps=num_steps)

        out.update(extract_outputs(prob, arch, design))
        out.update(estimate_pfei(out, cfg))
        out["closure_converged"] = bool(model_converged)
        out["closure_rel_error"] = float(closure_error)

        if not model_converged:
            out["success"] = False
            out["failure_reason"] = "nonlinear_model_not_converged"
        else:
            physics_feasible, physics_reason = check_feasible(out, arch)
            out["physics_feasible"] = bool(physics_feasible)
            out["physics_failure_reason"] = physics_reason
            in_domain = bool(out.get("within_reference_volume_domain", False))
            out["validated_domain_feasible"] = bool(physics_feasible and in_domain)
            if PARETO_FEASIBILITY_MODE == "physics":
                out["success"] = bool(physics_feasible)
                out["failure_reason"] = physics_reason
            elif PARETO_FEASIBILITY_MODE == "validated_domain":
                out["success"] = bool(physics_feasible and in_domain)
                if not physics_feasible:
                    out["failure_reason"] = physics_reason
                elif not in_domain:
                    out["failure_reason"] = "outside_reference_volume_domain"
                else:
                    out["failure_reason"] = "feasible"
            else:
                raise ValueError("PARETO_FEASIBILITY_MODE must be 'physics' or 'validated_domain'.")

    except Exception as exc:
        out["success"] = False
        out["failure_reason"] = f"{type(exc).__name__}: {exc}"
        out["mtow_kg"] = np.nan
        out["pfei_MJ_per_kg_km"] = np.nan
        out["total_energy_MJ"] = np.nan
        out["physics_feasible"] = False
        out["validated_domain_feasible"] = False
        out["within_reference_volume_domain"] = False
    finally:
        if prob is not None:
            try:
                prob.cleanup()
            except Exception:
                pass

    out["runtime_s"] = time.time() - t0
    return out


# =============================================================================
# Pareto front (minimize MTOW*, minimize PFEI)
# =============================================================================

def pareto_mask_min_min(df: pd.DataFrame) -> np.ndarray:
    """Return the nondominated mask for minimizing MTOW and selected PFEI."""
    vals = df[["mtow_kg", "pfei_MJ_per_kg_km"]].to_numpy(dtype=float, copy=True)
    finite = np.all(np.isfinite(vals), axis=1)
    mask = np.zeros(len(df), dtype=bool)
    valid_idx = np.flatnonzero(finite)
    if valid_idx.size == 0:
        return mask

    # Sort by MTOW, then keep strictly improving PFEI values. This is stable,
    # deterministic, and handles duplicate points without O(n^2) comparisons.
    order = valid_idx[np.lexsort((vals[valid_idx, 1], vals[valid_idx, 0]))]
    best_y = np.inf
    for idx in order:
        y = vals[idx, 1]
        if y < best_y - 1.0e-12:
            mask[idx] = True
            best_y = y
    return mask


def pareto_mask_for_study(df: pd.DataFrame, study_kind: str) -> np.ndarray:
    """Return the appropriate non-dominated set for each study.

    common_mission: minimize MTOW and PFEI because mission capability is fixed.
    native: minimize MTOW and PFEI while maximizing transport work, so a short/
    light mission cannot dominate a longer/higher-payload AV-10 mission merely
    because it is easier.
    """
    if study_kind == "common_mission":
        return pareto_mask_min_min(df)
    if study_kind != "native":
        raise ValueError(f"Unknown study_kind: {study_kind!r}")
    cols = ["mtow_kg", "pfei_MJ_per_kg_km", "transport_work_kg_km"]
    vals = df[cols].to_numpy(dtype=float, copy=True)
    finite = np.all(np.isfinite(vals), axis=1)
    mask = np.zeros(len(df), dtype=bool)
    ids = np.flatnonzero(finite)
    # Objectives are [min MTOW, min PFEI, max transport work].
    for i in ids:
        xi = vals[i]
        dominated = False
        for j in ids:
            if i == j:
                continue
            xj = vals[j]
            no_worse = (xj[0] <= xi[0] and xj[1] <= xi[1] and xj[2] >= xi[2])
            strictly = (xj[0] < xi[0] or xj[1] < xi[1] or xj[2] > xi[2])
            if no_worse and strictly:
                dominated = True
                break
        mask[i] = not dominated
    return mask


def identify_knee_point(
    front: pd.DataFrame,
    study_kind: str,
) -> Optional[pd.Series]:
    """Return a representative Pareto point using the correct objective set.

    Common mission
        Two objectives are active: min(MTOW), min(PFEI). A normalized
        Euclidean distance to the 2-D utopia point is used.

    Native mission-envelope study
        Three objectives are active: min(MTOW), min(PFEI), max(transport work).
        Native knees are disabled by default because a single knee can obscure
        the mission-capability trade. If ``NATIVE_KNEE_MODE='utopia3d'``, the
        same normalized utopia-distance concept is extended to all three
        objectives, with transport work reversed because it is maximized.
    """
    if front is None or front.empty:
        return None

    if study_kind == "native" and NATIVE_KNEE_MODE == "none":
        return None

    mtow = front["mtow_kg"].to_numpy(float)
    pfei = front["pfei_MJ_per_kg_km"].to_numpy(float)

    def _norm_min(v: np.ndarray) -> np.ndarray:
        span = max(float(np.nanmax(v) - np.nanmin(v)), 1.0e-12)
        return (v - np.nanmin(v)) / span

    m_n = _norm_min(mtow)
    p_n = _norm_min(pfei)

    if study_kind == "common_mission":
        score = np.sqrt(m_n**2 + p_n**2)
    elif study_kind == "native":
        if NATIVE_KNEE_MODE != "utopia3d":
            raise ValueError("NATIVE_KNEE_MODE must be 'none' or 'utopia3d'.")
        work = front["transport_work_kg_km"].to_numpy(float)
        span = max(float(np.nanmax(work) - np.nanmin(work)), 1.0e-12)
        # 0 at maximum transport work (the utopia direction), 1 at minimum.
        w_n = (np.nanmax(work) - work) / span
        score = np.sqrt(m_n**2 + p_n**2 + w_n**2)
    else:
        raise ValueError(f"Unknown study_kind: {study_kind!r}")

    finite = np.isfinite(score)
    if not np.any(finite):
        return None
    idx = np.flatnonzero(finite)[int(np.argmin(score[finite]))]
    return front.iloc[idx]


# =============================================================================
# NSGA-II global-search refinement
# =============================================================================

def _varying_design_variables(cfg: ArchConfig, study_kind: str) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Return varying outer-design variables and lower/upper bounds."""
    bounds = _study_bounds(cfg, study_kind)
    names = [k for k, (lo, hi) in bounds.items() if float(lo) != float(hi)]
    xl = np.array([bounds[k][0] for k in names], dtype=float)
    xu = np.array([bounds[k][1] for k in names], dtype=float)
    return names, xl, xu


def _vector_to_design(
    x: Sequence[float],
    cfg: ArchConfig,
    study_kind: str,
    names: Sequence[str],
) -> Dict[str, float]:
    """Decode a pymoo decision vector into the existing model design dictionary."""
    bounds = _study_bounds(cfg, study_kind)
    design: Dict[str, float] = {}
    x_map = {name: float(value) for name, value in zip(names, x)}
    for key, (lo, hi) in bounds.items():
        design[key] = x_map[key] if key in x_map else float(lo)
    design["study_kind"] = study_kind
    return design


def _row_constraint_vector(row: Dict[str, Any], arch: str) -> np.ndarray:
    """Dimensionless optimizer constraints, all feasible when G <= 0.

    Ground-roll and landing-distance constraints are deliberately excluded.
    Lift is included as a core physical constraint, matching ``check_feasible``.
    Characteristic scales prevent one dimensional residual (for example N)
    from numerically overwhelming another during infeasible-population ranking.
    """
    cfg = ARCH_CONFIGS[arch]

    def g(name: str, tol: float, scale: float, default: float = 1.0e12) -> float:
        try:
            v = float(row.get(name, np.nan))
        except Exception:
            v = np.nan
        if not np.isfinite(v):
            return float(default)
        return (v - tol) / max(scale, 1.0e-12)

    G: List[float] = [
        g("power_constraint", CONSTRAINT_TOL["power"], 1.0e4),
        g("buoyancy_constraint", CONSTRAINT_TOL["buoyancy"], 1.0e4),
        g("envelope_volume_violation", CONSTRAINT_TOL["volume"], 10.0),
        g("lift_constraint", CONSTRAINT_TOL["lift"], 1.0),
    ]

    if cfg.has_battery:
        G.append(-1.0)
    else:
        G.append(g("energy_constraint", CONSTRAINT_TOL["energy"], 1.0))

    try:
        required_W = 1000.0 * float(row.get("required_power_kW", np.nan))
        installed_W = 1000.0 * float(row.get("engine_power_kW", np.nan))
        installed_g = (required_W - installed_W - CONSTRAINT_TOL["power"]) / 1.0e4
        if not np.isfinite(installed_g):
            installed_g = 1.0e12
    except Exception:
        installed_g = 1.0e12
    G.append(float(installed_g))

    try:
        mbe = abs(float(row.get("mass_balance_error_kg", np.nan)))
        mass_g = (mbe - CONSTRAINT_TOL["mass_balance"]) / 1.0
        if not np.isfinite(mass_g):
            mass_g = 1.0e12
    except Exception:
        mass_g = 1.0e12
    G.append(float(mass_g))

    if arch in {"hydrogen_fuel_cell", "hydrogen_hybrid", "solar_hydrogen_hybrid"}:
        G.append(g("fc_power_shortfall", CONSTRAINT_TOL["fc_power"], 1.0e4))
    else:
        G.append(-1.0)

    # Nonlinear closure is a hard requirement for optimizer acceptance.
    closure_ok = bool(row.get("closure_converged", False))
    G.append(-1.0 if closure_ok else 1.0)

    # Optional validated-domain gate. Physical mode leaves it inactive.
    if PARETO_FEASIBILITY_MODE == "validated_domain":
        G.append(-1.0 if bool(row.get("within_reference_volume_domain", False)) else 1.0)
    else:
        G.append(-1.0)

    return np.asarray(G, dtype=float)


def _objective_vector(row: Dict[str, Any], study_kind: str) -> np.ndarray:
    """Pymoo minimization objectives using the same definitions as the DOE Pareto set."""
    try:
        mtow = float(row.get("mtow_kg", np.nan))
        pfei = float(row.get("pfei_MJ_per_kg_km", np.nan))
    except Exception:
        mtow, pfei = np.nan, np.nan
    if not np.isfinite(mtow) or mtow <= 0.0:
        mtow = 1.0e9
    if not np.isfinite(pfei) or pfei <= 0.0:
        pfei = 1.0e3

    if study_kind == "common_mission":
        return np.array([mtow, pfei], dtype=float)
    if study_kind == "native":
        try:
            work = float(row.get("transport_work_kg_km", np.nan))
        except Exception:
            work = np.nan
        if not np.isfinite(work) or work <= 0.0:
            work = 0.0
        return np.array([mtow, pfei, -work], dtype=float)
    raise ValueError(f"Unknown study_kind: {study_kind!r}")


def _design_cache_key(x: Sequence[float]) -> Tuple[float, ...]:
    return tuple(np.round(np.asarray(x, dtype=float), NSGA2_DUPLICATE_DECIMALS).tolist())


def _maximin_seed_indices(Xn: np.ndarray, n_select: int, priority: Sequence[int] = ()) -> List[int]:
    """Deterministic farthest-point subset for diverse NSGA-II initialization."""
    n = len(Xn)
    if n_select >= n:
        return list(range(n))
    selected: List[int] = []
    for idx in priority:
        idx = int(idx)
        if 0 <= idx < n and idx not in selected:
            selected.append(idx)
        if len(selected) >= n_select:
            return selected
    if not selected:
        center = np.full(Xn.shape[1], 0.5)
        selected.append(int(np.argmin(np.linalg.norm(Xn - center, axis=1))))
    while len(selected) < n_select:
        d2 = np.full(n, np.inf)
        for j in selected:
            d2 = np.minimum(d2, np.sum((Xn - Xn[j])**2, axis=1))
        d2[selected] = -np.inf
        selected.append(int(np.argmax(d2)))
    return selected


def _lhs_seed_population(
    lhs_df: pd.DataFrame,
    cfg: ArchConfig,
    study_kind: str,
    names: Sequence[str],
    xl: np.ndarray,
    xu: np.ndarray,
    pop_size: int,
) -> np.ndarray:
    """Seed NSGA-II from the already evaluated global LHS cloud."""
    if lhs_df is None or lhs_df.empty:
        # Fallback remains global LHS rather than random initialization.
        seed_df = sample_designs(cfg, pop_size, SPYDER_SEED + 777, study_kind)
        return seed_df[list(names)].to_numpy(float)

    finite = np.ones(len(lhs_df), dtype=bool)
    for name in names:
        finite &= pd.to_numeric(lhs_df[name], errors="coerce").notna().to_numpy()
    candidates = lhs_df.loc[finite].copy()
    if candidates.empty:
        seed_df = sample_designs(cfg, pop_size, SPYDER_SEED + 777, study_kind)
        return seed_df[list(names)].to_numpy(float)

    X = candidates[list(names)].to_numpy(float)
    span = np.maximum(xu - xl, 1.0e-12)
    Xn = np.clip((X - xl) / span, 0.0, 1.0)

    # Preserve known LHS Pareto designs in the initial population, then fill
    # the remainder by maximin diversity over the whole LHS cloud.
    priority = np.flatnonzero(candidates.get("pareto", pd.Series(False, index=candidates.index)).to_numpy(bool))
    if len(priority) > max(1, pop_size // 3):
        priority = np.asarray(_maximin_seed_indices(Xn[priority], max(1, pop_size // 3)))
        priority = np.flatnonzero(candidates.get("pareto", pd.Series(False, index=candidates.index)).to_numpy(bool))[priority]
    ids = _maximin_seed_indices(Xn, min(pop_size, len(candidates)), priority=priority)
    Xseed = X[ids]

    if len(Xseed) < pop_size:
        extra = sample_designs(cfg, pop_size - len(Xseed), SPYDER_SEED + 778, study_kind)
        Xseed = np.vstack([Xseed, extra[list(names)].to_numpy(float)])
    return Xseed[:pop_size]


if PYMOO_AVAILABLE:
    class AirshipParetoProblem(ElementwiseProblem):
        """Elementwise pymoo wrapper around the full converged OpenMDAO model."""
        def __init__(
            self,
            arch: str,
            study_kind: str,
            lhs_df: pd.DataFrame,
        ):
            self.arch = arch
            self.cfg = ARCH_CONFIGS[arch]
            self.study_kind = study_kind
            self.names, xl, xu = _varying_design_variables(self.cfg, study_kind)
            self.records: List[Dict[str, Any]] = []
            self.cache: Dict[Tuple[float, ...], Dict[str, Any]] = {}

            # Cache all already evaluated LHS designs so initial NSGA-II seeds
            # do not repeat expensive OpenMDAO analyses.
            if lhs_df is not None and not lhs_df.empty:
                for _, r in lhs_df.iterrows():
                    try:
                        x = [float(r[name]) for name in self.names]
                    except Exception:
                        continue
                    if np.all(np.isfinite(x)):
                        self.cache[_design_cache_key(x)] = r.to_dict()

            n_obj = 2 if study_kind == "common_mission" else 3
            super().__init__(
                n_var=len(self.names),
                n_obj=n_obj,
                n_ieq_constr=10,
                xl=xl,
                xu=xu,
            )

        def _evaluate(self, x, out, *args, **kwargs):
            key = _design_cache_key(x)
            if key in self.cache:
                row = dict(self.cache[key])
                row["search_source"] = "LHS_seed_reused"
            else:
                design = _vector_to_design(x, self.cfg, self.study_kind, self.names)
                row = evaluate_design(self.arch, design)
                row["search_source"] = "NSGA2"
                self.cache[key] = dict(row)
            self.records.append(dict(row))
            out["F"] = _objective_vector(row, self.study_kind)
            out["G"] = _row_constraint_vector(row, self.arch)


def run_nsga2_refinement(
    arch: str,
    study_kind: str,
    lhs_df: pd.DataFrame,
    seed: int,
) -> pd.DataFrame:
    """Refine the global LHS cloud with NSGA-II using the full OpenMDAO model."""
    if not RUN_NSGA2_REFINEMENT:
        return pd.DataFrame()
    if not PYMOO_AVAILABLE:
        raise RuntimeError(
            "RUN_NSGA2_REFINEMENT=True but pymoo could not be imported. "
            "Install pymoo in the airship_design environment (for example, "
            "`python -m pip install pymoo`) and rerun. Original import error: "
            f"{PYMOO_IMPORT_ERROR}"
        )

    pop_size = NSGA2_QUICK_POP_SIZE if SPYDER_MODE == "quick" else NSGA2_FULL_POP_SIZE
    n_gen = NSGA2_QUICK_N_GEN if SPYDER_MODE == "quick" else NSGA2_FULL_N_GEN
    problem = AirshipParetoProblem(arch, study_kind, lhs_df)
    _, xl, xu = _varying_design_variables(ARCH_CONFIGS[arch], study_kind)
    X0 = _lhs_seed_population(lhs_df, ARCH_CONFIGS[arch], study_kind, problem.names, xl, xu, pop_size)

    print("\n  NSGA-II refinement")
    print(f"    variables : {problem.names}")
    print(f"    pop_size  : {pop_size}")
    print(f"    n_gen     : {n_gen}")
    print("    seed      : LHS cloud (Pareto-preserving + maximin diverse subset)")

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=X0,
        eliminate_duplicates=True,
    )
    pymoo_minimize(
        problem,
        algorithm,
        get_termination("n_gen", n_gen),
        seed=seed,
        verbose=NSGA2_VERBOSE,
        save_history=False,
    )

    if not problem.records:
        return pd.DataFrame()
    nsga = pd.DataFrame(problem.records)
    # Reused LHS seeds are already in the DOE table; keep only genuinely new
    # NSGA-II evaluations in the dedicated optimizer CSV.
    if "search_source" in nsga.columns:
        nsga_new = nsga[nsga["search_source"] == "NSGA2"].copy()
    else:
        nsga_new = nsga.copy()
    return nsga_new


# =============================================================================
# Per-architecture run
# =============================================================================

def run_architecture(
    arch: str,
    n_samples: int,
    output_dir: str,
    seed: int,
    study_kind: str,
) -> pd.DataFrame:
    """Run broad LHS coverage, optional NSGA-II refinement, then merge fronts."""
    cfg = ARCH_CONFIGS[arch]
    arch_dir = os.path.join(output_dir, study_kind, arch)
    os.makedirs(arch_dir, exist_ok=True)

    print("\n" + "=" * 80)
    print(f"PFEI Pareto search: {arch} - {cfg.label} [{study_kind}]")
    print("Stage 1 = global LHS DOE; Stage 2 = NSGA-II Pareto refinement")
    print("=" * 80)

    # ------------------------------------------------------------------
    # Stage 1: global Latin-hypercube DOE
    # ------------------------------------------------------------------
    designs = sample_designs(cfg, n_samples, seed, study_kind=study_kind)
    lhs_rows: List[Dict[str, Any]] = []
    for i, design in designs.iterrows():
        row = evaluate_design(arch, design.to_dict())
        row["search_source"] = "LHS"
        lhs_rows.append(row)
        status = "OK" if row["success"] else "--"
        print(
            f"[LHS {i+1:4d}/{n_samples}] {status} "
            f"R={row.get('range_km', np.nan):.0f} km  "
            f"P={row.get('payload_kg', np.nan):.0f} kg  "
            f"MTOW*={row.get('mtow_kg', np.nan):.0f} kg  "
            f"PFEI={row.get('pfei_MJ_per_kg_km', np.nan):.5f}  "
            f"[{row.get('failure_reason', '')}]"
        )

    lhs_df = pd.DataFrame(lhs_rows)
    lhs_ok = lhs_df[lhs_df["success"]].copy() if len(lhs_df) else pd.DataFrame()
    if len(lhs_ok):
        lhs_ok["pareto"] = pareto_mask_for_study(lhs_ok, study_kind)
        lhs_pareto_names = set(lhs_ok.index[lhs_ok["pareto"]])
        lhs_df["pareto"] = lhs_df.index.isin(lhs_pareto_names)
    else:
        lhs_df["pareto"] = False

    lhs_path = os.path.join(arch_dir, f"pfei_lhs_all_{study_kind}_{arch}.csv")
    lhs_df.to_csv(lhs_path, index=False)

    # ------------------------------------------------------------------
    # Stage 2: NSGA-II global-search refinement, seeded from LHS
    # ------------------------------------------------------------------
    nsga_df = run_nsga2_refinement(
        arch=arch,
        study_kind=study_kind,
        lhs_df=lhs_df,
        seed=seed + 50_000,
    )
    nsga_path = os.path.join(arch_dir, f"pfei_nsga2_all_{study_kind}_{arch}.csv")
    nsga_df.to_csv(nsga_path, index=False)

    # ------------------------------------------------------------------
    # Union of DOE + optimizer evaluations; final Pareto set is recomputed
    # globally on the union, never accepted directly from either stage.
    # ------------------------------------------------------------------
    frames = [lhs_df]
    if nsga_df is not None and not nsga_df.empty:
        frames.append(nsga_df)
    df = pd.concat(frames, ignore_index=True, sort=False)

    design_names, _, _ = _varying_design_variables(cfg, study_kind)
    dedup_cols = [c for c in design_names if c in df.columns]
    if dedup_cols:
        rounded = df[dedup_cols].apply(pd.to_numeric, errors="coerce").round(NSGA2_DUPLICATE_DECIMALS)
        keep = ~rounded.duplicated(keep="first")
        df = df.loc[keep].copy().reset_index(drop=True)

    df_ok = df[df["success"]].copy()
    df_ok["pareto"] = pareto_mask_for_study(df_ok, study_kind) if len(df_ok) else False
    front = df_ok[df_ok["pareto"]].copy().sort_values("mtow_kg")
    knee = identify_knee_point(front, study_kind)
    df_ok["knee"] = False
    if knee is not None:
        df_ok.loc[knee.name, "knee"] = True

    # Propagate final Pareto/knee labels back to the all-points table.
    df["pareto"] = False
    df["knee"] = False
    if len(df_ok):
        df.loc[df_ok.index, "pareto"] = df_ok["pareto"].to_numpy(bool)
        df.loc[df_ok.index, "knee"] = df_ok["knee"].to_numpy(bool)

    all_path = os.path.join(arch_dir, f"pfei_all_{study_kind}_{arch}.csv")
    ok_path = os.path.join(arch_dir, f"pfei_success_{study_kind}_{arch}.csv")
    front_path = os.path.join(arch_dir, f"pareto_front_{study_kind}_{arch}.csv")
    df.to_csv(all_path, index=False)
    df_ok.to_csv(ok_path, index=False)
    front.to_csv(front_path, index=False)

    print(f"\nSaved LHS      -> {lhs_path}")
    print(f"Saved NSGA-II  -> {nsga_path}")
    print(f"Saved combined -> {all_path}")
    print(f"Saved success  -> {ok_path}")
    print(f"Saved Pareto   -> {front_path}")
    print(f"Combined feasibility -> {len(df_ok)}/{len(df)} = {100*len(df_ok)/max(len(df),1):.1f}%")
    print(f"Final Pareto points  -> {len(front)}")
    if study_kind == "native" and NATIVE_KNEE_MODE == "none":
        print("Native knee          -> disabled (three-objective mission-envelope study)")
    elif knee is not None:
        print(
            "Representative knee -> "
            f"MTOW={knee['mtow_kg']:.1f} kg, PFEI={knee['pfei_MJ_per_kg_km']:.6f}, "
            f"R={knee['range_km']:.1f} km, payload={knee['payload_kg']:.1f} kg"
        )

    if "failure_reason" in df.columns:
        print("\nFailure summary:")
        print(df.loc[~df["success"], "failure_reason"].value_counts(dropna=False).head(15))

    make_arch_plots(df, df_ok, arch, cfg, arch_dir, study_kind=study_kind)
    return df_ok


# =============================================================================
# Plotting
# =============================================================================

def make_arch_plots(df_all: pd.DataFrame, df_ok: pd.DataFrame, arch: str, cfg: ArchConfig, arch_dir: str, study_kind: str):
    if df_ok.empty:
        print(f"Too few feasible points for {arch}. No plots.")
        return

    pareto = df_ok[df_ok["pareto"]].copy().sort_values("mtow_kg")
    knee = df_ok[df_ok.get("knee", False)].copy() if "knee" in df_ok.columns else df_ok.iloc[0:0]
    base_color = ARCH_COLORS.get(arch, "#0072B2")

    # ---- 1. PFEI vs MTOW* Pareto cloud -------------------------------------
    fig, ax = plt.subplots(figsize=FIGSIZE_2D)
    bad = df_all[(~df_all["success"]) & df_all["mtow_kg"].notna() & df_all["pfei_MJ_per_kg_km"].notna()]
    if len(bad):
        ax.scatter(bad["mtow_kg"], bad["pfei_MJ_per_kg_km"], marker="x", s=26,
                   linewidths=0.9, color=INFEASIBLE_COLOR, alpha=0.5, label="Infeasible", zorder=1)
    ax.scatter(df_ok["mtow_kg"], df_ok["pfei_MJ_per_kg_km"], s=34, marker="o",
               facecolor=base_color, edgecolor="white", linewidths=0.4, alpha=0.55,
               label="Feasible design", zorder=2)
    if len(pareto):
        ax.plot(pareto["mtow_kg"], pareto["pfei_MJ_per_kg_km"], color=PARETO_COLOR,
                linewidth=1.1, linestyle="--", alpha=0.85, zorder=3)
        ax.scatter(pareto["mtow_kg"], pareto["pfei_MJ_per_kg_km"], marker="*", s=170,
                   facecolor=PARETO_COLOR, edgecolor="black", linewidths=0.7,
                   label="Pareto front", zorder=4)
    ax.set_xlabel(r"MTOW$^{*}$ [kg]")
    ax.set_ylabel(r"PFEI [MJ (kg$\cdot$km)$^{-1}$]")
    ax.set_title(f"{cfg.label} \u2014 PFEI vs. MTOW$^{{*}}$")
    _style_axes_2d(ax)
    ax.legend(loc="best")
    fig.tight_layout()
    path = os.path.join(arch_dir, f"pfei_vs_mtow_pareto_{arch}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  -> {path}")

    # ---- 2. MTOW*-PFEI-Range 3D Pareto cloud -------------------------------
    fig = plt.figure(figsize=FIGSIZE_3D)
    ax = fig.add_subplot(111, projection="3d")
    ax.xaxis.pane.set_facecolor("white")
    ax.yaxis.pane.set_facecolor("white")
    ax.zaxis.pane.set_facecolor("white")
    ax.xaxis.pane.set_edgecolor("#DDDDDD")
    ax.yaxis.pane.set_edgecolor("#DDDDDD")
    ax.zaxis.pane.set_edgecolor("#DDDDDD")
    ax.grid(True, alpha=0.25, linewidth=0.4)

    sc = ax.scatter(df_ok["mtow_kg"], df_ok["pfei_MJ_per_kg_km"], df_ok["range_km"],
                     c=df_ok["range_km"], cmap="viridis", s=28, alpha=0.65,
                     edgecolor="white", linewidths=0.3, label="Feasible design")
    if len(pareto):
        ax.scatter(pareto["mtow_kg"], pareto["pfei_MJ_per_kg_km"], pareto["range_km"],
                   marker="*", s=150, facecolor=PARETO_COLOR, edgecolor="black",
                   linewidths=0.7, label="Pareto front", depthshade=False)
    ax.set_xlabel(r"MTOW$^{*}$ [kg]", labelpad=10)
    ax.set_ylabel(r"PFEI [MJ (kg$\cdot$km)$^{-1}$]", labelpad=10)
    ax.set_zlabel("Range [km]", labelpad=8)
    ax.set_title(f"{cfg.label} \u2014 MTOW$^{{*}}$-PFEI-Range Pareto cloud", pad=14)
    ax.view_init(elev=20, azim=-60)
    ax.legend(loc="upper left", fontsize=8.5)
    cbar = fig.colorbar(sc, ax=ax, shrink=0.65, pad=0.08)
    cbar.set_label("Range [km]")
    fig.tight_layout()
    path = os.path.join(arch_dir, f"pfei_mtow_range_3d_{arch}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  -> {path}")

    # ---- 3. PFEI-MTOW* colored by the architecture's key design driver ----
    if "chi" in df_ok.columns:
        color_key, color_label = "chi", "Battery energy share, " + r"$\chi$"
    elif "tau" in df_ok.columns:
        color_key, color_label = "tau", "Battery power share, " + r"$\tau$"
    elif "solar_area_m2" in df_ok.columns:
        color_key, color_label = "solar_area_m2", r"Solar panel area [m$^2$]"
    elif cfg.has_tank:
        color_key, color_label = "tank_mass_kg", "Tank mass [kg]"
    else:
        color_key, color_label = "cruise_speed_mps", "Cruise speed [m/s]"

    if color_key in df_ok.columns:
        fig, ax = plt.subplots(figsize=FIGSIZE_2D)
        sc = ax.scatter(df_ok["mtow_kg"], df_ok["pfei_MJ_per_kg_km"], c=df_ok[color_key],
                        cmap="viridis", s=36, alpha=0.75, edgecolor="white",
                        linewidths=0.4, zorder=2)
        if len(pareto):
            ax.plot(pareto["mtow_kg"], pareto["pfei_MJ_per_kg_km"], color=PARETO_COLOR,
                    linewidth=1.1, linestyle="--", alpha=0.85, zorder=3)
            ax.scatter(pareto["mtow_kg"], pareto["pfei_MJ_per_kg_km"], marker="*", s=170,
                       facecolor="none", edgecolor="black", linewidths=1.1,
                       label="Pareto front", zorder=4)
        ax.set_xlabel(r"MTOW$^{*}$ [kg]")
        ax.set_ylabel(r"PFEI [MJ (kg$\cdot$km)$^{-1}$]")
        ax.set_title(f"{cfg.label} \u2014 PFEI vs. MTOW$^{{*}}$, colored by {color_label}")
        _style_axes_2d(ax)
        if len(pareto):
            ax.legend(loc="best")
        cbar = fig.colorbar(sc, ax=ax, pad=0.02)
        cbar.set_label(color_label)
        fig.tight_layout()
        path = os.path.join(arch_dir, f"pfei_mtow_colored_{arch}.png")
        fig.savefig(path)
        plt.close(fig)
        print(f"  -> {path}")


def make_combined_plot(
    results: Dict[str, pd.DataFrame],
    output_dir: str,
    study_kind: str,
) -> None:
    """Create a true multi-architecture comparison on one common mission."""
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    plotted = 0

    for arch, df in results.items():
        if df is None or df.empty:
            continue
        cfg = ARCH_CONFIGS[arch]
        color = ARCH_COLORS.get(arch, "#333333")
        front = df[df["pareto"]].sort_values("mtow_kg")

        # Background feasible cloud is deliberately faint; the comparison is
        # carried by architecture-specific Pareto fronts and knee markers.
        ax.scatter(
            df["mtow_kg"], df["pfei_MJ_per_kg_km"],
            s=18, alpha=0.12, color=color, edgecolor="none", zorder=1,
        )
        if len(front):
            ax.plot(
                front["mtow_kg"], front["pfei_MJ_per_kg_km"],
                color=color, linewidth=1.8, marker="o", markersize=4.0,
                label=cfg.label, zorder=3,
            )
            knee = front[front.get("knee", False)] if "knee" in front.columns else front.iloc[0:0]
            if len(knee):
                ax.scatter(
                    knee["mtow_kg"], knee["pfei_MJ_per_kg_km"],
                    marker="D", s=70, facecolor=color, edgecolor="black",
                    linewidths=0.8, zorder=4,
                )
        plotted += len(df)

    ax.set_xlabel(r"MTOW$^{*}$ [kg]")
    ax.set_ylabel(r"PFEI [MJ (kg$\cdot$km)$^{-1}$]")
    if study_kind == "common_mission":
        title = (
            "Architecture comparison — common-mission Pareto fronts\n"
            f"Payload = {COMMON_PAYLOAD_KG:.0f} kg, range = {COMMON_RANGE_KM:.0f} km; "
            f"PFEI basis: {PFEI_BASIS.replace('_', ' ')}"
        )
    else:
        title = (
            "AV-10 equivalent common design-envelope Pareto sets\n"
            "Three objectives: min MTOW, min PFEI, max payload-range transport work"
        )
    ax.set_title(title)
    _style_axes_2d(ax)

    if plotted == 0:
        ax.text(
            0.5, 0.5,
            "No feasible points passed constraints.\nCheck pfei_all_*.csv failure_reason columns.",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=10, color="#666666",
        )
    else:
        ax.legend(loc="best", fontsize=8.5, ncol=1)

    fig.tight_layout()
    path = os.path.join(output_dir, study_kind, f"combined_architecture_pfei_mtow_{study_kind}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    print(f"\nCombined plot -> {path}")


def write_study_metadata(output_dir: str, n_samples: int) -> None:
    metadata = {
        "script_purpose": "AV-10 equivalent single-class Pareto and common-mission architecture audit",
        "airship_class": AIRSHIP_CLASS_LABEL,
        "technology_scenario": TECHNOLOGY_SCENARIO,
        "pareto_feasibility_mode": PARETO_FEASIBILITY_MODE,
        "reference_volume_ratio_bounds": REFERENCE_VOLUME_RATIO_BOUNDS,
        "technology_assumptions": TECHNOLOGY_SCENARIOS[TECHNOLOGY_SCENARIO],
        "pfei_basis_selected": PFEI_BASIS,
        "primary_energy_factor": PRIMARY_ENERGY_FACTOR,
        "common_mission": {
            "range_km": COMMON_RANGE_KM,
            "payload_kg": COMMON_PAYLOAD_KG,
            "cruise_speed_bounds_mps": COMMON_CRUISE_SPEED_BOUNDS_MPS,
            "fineness_ratio_bounds": COMMON_FINENESS_RATIO_BOUNDS,
            "length_bounds_m": COMMON_LENGTH_BOUNDS_M,
            "battery_specific_energy_Whkg": COMMON_BATTERY_SPECIFIC_ENERGY_WHKG,
            "battery_volumetric_energy_density_WhL": COMMON_BATTERY_VOLUMETRIC_ED_WHL,
            "solar_irradiance_Wm2": COMMON_SOLAR_IRRADIANCE_WM2,
        },
        "sampling": {
            "method": "Latin hypercube + NSGA-II" if RUN_NSGA2_REFINEMENT else ("Latin hypercube" if USE_LATIN_HYPERCUBE else "uniform random"),
            "nsga2_enabled": RUN_NSGA2_REFINEMENT,
            "nsga2_pop_size": NSGA2_QUICK_POP_SIZE if SPYDER_MODE == "quick" else NSGA2_FULL_POP_SIZE,
            "nsga2_generations": NSGA2_QUICK_N_GEN if SPYDER_MODE == "quick" else NSGA2_FULL_N_GEN,
            "native_knee_mode": NATIVE_KNEE_MODE,
            "lift_constraint_enforced": True,
            "ground_constraint_enforced": False,
            "landing_constraint_enforced": False,
            "n_samples_per_architecture": n_samples,
            "seed": SPYDER_SEED,
        },
        "field_length_limit_m": FIELD_LENGTH_LIMIT_M,
        "power_margin": POWER_MARGIN,
        "architectures": SPYDER_ARCHS,
    }
    path = os.path.join(output_dir, "study_metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Study metadata -> {path}")



def run_validation() -> bool:
    """Optional legacy regression validation hook; disabled by default for this AV-10 audit."""
    print("\n" + "=" * 70)
    print("VALIDATION — A-170 reference case")
    print("=" * 70)

    phd = opCond(
        name="Cruise",
        T_env=281.65,
        altitude=914.0,
        speed=19.57 / 337.5,
        time="day",
        RH=70.0,
    )

    prob = om.Problem()
    prob.model = AirshipAnalysisGroup(
        phd=phd,
        power_source="conventional_reciprocating",
        landing_system="conventional",
        num_steps=1,
        use_prescribed_consumable_capacity=True,
    )
    prob.setup(check=False)

    settings = [
        ("length", 53.58, "m"),
        ("fineness_ratio", 4.10, None),
        ("tail_volume_coeff_horizontal", 0.066, None),
        ("tail_volume_coeff_vertical", 0.059, None),
        ("payload", 1122.0, "kg"),
        ("range", 1_342_100.0, "m"),
        ("cruise_altp", np.array([914.4]), "m"),
        ("cruise_disa", np.array([0.0]), "K"),
        ("cruise_speed", np.array([19.57]), "m/s"),
        ("n_crew", 1.0, None),
        ("n_engine", 2.0, None),
        ("installed_shaft_power", 268_000.0, "W"),
        ("propeller_efficiency", 0.75, None),
        ("BR_takeoff", 0.896, None),
        ("BR_landing", 0.90, None),
        ("lift_coeff", 0.15, None),
        ("drag_due_to_lift_factor", 0.869, None),
        ("installed_consumable_capacity", 599.0, "kg"),
        ("ballast_mass", 113.0, "kg"),
        ("tailwind_speed", 0.0, "m/s"),
        ("thrust_vector_angle", 0.0, "deg"),
    ]
    for name, value, units in settings:
        _safe_set(prob, name, value, units)

    prob.run_model()

    references = [
        ("MTOW [kg]", 5629.0, "mtow", "kg"),
        ("Gross Volume [m3]", 4823.0, "gross_volume", "m**3"),
        ("Installed Shaft Power [kW]", 268.0,
         "installed_shaft_power", "kW"),
    ]

    passed = True
    for label, reference, variable, units in references:
        value = _get_scalar(prob, variable, units)
        error = 100.0 * (value - reference) / reference
        ok = np.isfinite(error) and abs(error) < 5.0
        passed = passed and ok
        print(
            f"  {label:<32}{reference:>12.2f}{value:>12.2f}"
            f"{error:>+9.2f}%  {'OK' if ok else 'CHECK'}"
        )

    prob.cleanup()
    print("\nVALIDATION PASSED" if passed else "\nVALIDATION REQUIRES REVIEW")
    return passed



# =============================================================================
# Main
# =============================================================================

def _build_summary(
    study_results: Dict[str, pd.DataFrame],
    study_kind: str,
    output_dir: str,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for arch, df in study_results.items():
        if df is None or df.empty:
            continue
        cfg = ARCH_CONFIGS[arch]
        front = df[df["pareto"]].sort_values("mtow_kg")
        knee = identify_knee_point(front, study_kind)
        min_mtow = df.loc[df["mtow_kg"].idxmin()]
        min_pfei = df.loc[df["pfei_MJ_per_kg_km"].idxmin()]
        row: Dict[str, Any] = {
            "study_kind": study_kind,
            "arch": arch,
            "label": cfg.label,
            "n_success": len(df),
            "n_pareto": int(df["pareto"].sum()),
            "minimum_mtow_kg": float(min_mtow["mtow_kg"]),
            "pfei_at_minimum_mtow": float(min_mtow["pfei_MJ_per_kg_km"]),
            "minimum_pfei_MJ_per_kg_km": float(min_pfei["pfei_MJ_per_kg_km"]),
            "mtow_at_minimum_pfei_kg": float(min_pfei["mtow_kg"]),
        }
        if knee is not None:
            row.update({
                "knee_mtow_kg": float(knee["mtow_kg"]),
                "knee_pfei_MJ_per_kg_km": float(knee["pfei_MJ_per_kg_km"]),
                "knee_range_km": float(knee["range_km"]),
                "knee_payload_kg": float(knee["payload_kg"]),
                "knee_cruise_speed_mps": float(knee["cruise_speed_mps"]),
                "knee_fineness_ratio": float(knee["fineness_ratio"]),
                "knee_length_m": float(knee["length_m"]),
            })
        rows.append(row)

    summary = pd.DataFrame(rows)
    path = os.path.join(output_dir, study_kind, f"architecture_summary_{study_kind}.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    summary.to_csv(path, index=False)
    print(f"Summary CSV -> {path}")
    return summary


def main():
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    if SPYDER_MODE == "quick":
        n_samples = SPYDER_N_SAMPLES or 80
    elif SPYDER_MODE == "full":
        n_samples = SPYDER_N_SAMPLES or 600
    else:
        raise ValueError("SPYDER_MODE must be 'quick' or 'full'.")

    os.makedirs(SPYDER_OUTPUT_DIR, exist_ok=True)

    print("\nUsing AV-10 equivalent single-class PFEI/Pareto audit configuration:")
    print(f"  mode               : {SPYDER_MODE}")
    print(f"  archs              : {SPYDER_ARCHS}")
    print(f"  n_samples          : {n_samples}")
    print(f"  PFEI basis         : {PFEI_BASIS}")
    print(f"  global search      : LHS + NSGA-II = {RUN_NSGA2_REFINEMENT}")
    if RUN_NSGA2_REFINEMENT:
        _pop = NSGA2_QUICK_POP_SIZE if SPYDER_MODE == "quick" else NSGA2_FULL_POP_SIZE
        _gen = NSGA2_QUICK_N_GEN if SPYDER_MODE == "quick" else NSGA2_FULL_N_GEN
        print(f"  NSGA-II            : pop={_pop}, generations={_gen}")
    print(f"  native knee        : {NATIVE_KNEE_MODE}")
    print("  feasibility        : lift enforced; ground/landing diagnostic only")
    print(f"  native exploration : {RUN_NATIVE_EXPLORATION}")
    print(f"  common comparison  : {RUN_COMMON_MISSION_COMPARISON}")
    print(f"  airship class       : {AIRSHIP_CLASS_LABEL}")
    print(f"  technology         : {TECHNOLOGY_SCENARIO}")
    print(f"  Pareto feasibility : {PARETO_FEASIBILITY_MODE}")
    print(f"  common mission     : {COMMON_PAYLOAD_KG:.0f} kg, {COMMON_RANGE_KM:.0f} km")
    print(f"  output_dir         : {SPYDER_OUTPUT_DIR}")
    print(f"  CORE_DIR           : {CORE_DIR}")

    write_study_metadata(SPYDER_OUTPUT_DIR, n_samples)

    if SPYDER_RUN_VALIDATION and not run_validation():
        raise RuntimeError("AV-10 equivalent validation did not pass. Pareto study was not started.")

    study_kinds: List[str] = []
    if RUN_NATIVE_EXPLORATION:
        study_kinds.append("native")
    if RUN_COMMON_MISSION_COMPARISON:
        study_kinds.append("common_mission")
    if not study_kinds:
        raise RuntimeError("Enable at least one study mode.")

    all_summaries: List[pd.DataFrame] = []
    for study_offset, study_kind in enumerate(study_kinds):
        study_results: Dict[str, pd.DataFrame] = {}
        for i, arch in enumerate(SPYDER_ARCHS):
            if arch not in ARCH_CONFIGS:
                raise ValueError(f"Unknown architecture: {arch}")
            seed = SPYDER_SEED + 10_000 * study_offset + 100 * i
            study_results[arch] = run_architecture(
                arch=arch,
                n_samples=n_samples,
                output_dir=SPYDER_OUTPUT_DIR,
                seed=seed,
                study_kind=study_kind,
            )

        make_combined_plot(study_results, SPYDER_OUTPUT_DIR, study_kind)
        all_summaries.append(_build_summary(study_results, study_kind, SPYDER_OUTPUT_DIR))

    if all_summaries:
        combined_summary = pd.concat(all_summaries, ignore_index=True)
        combined_path = os.path.join(SPYDER_OUTPUT_DIR, "pareto_architecture_summary_all_studies.csv")
        combined_summary.to_csv(combined_path, index=False)
        print(f"Combined summary -> {combined_path}")
        print(combined_summary)

    print("\nDone.")


if __name__ == "__main__":
    main()