# -*- coding: utf-8 -*-
"""
technology_assessment_av10_dual_v1.py
===========================================

Dual technology assessment for the validated AV-10 equivalent common mission.

Assessment A -- reference-geometry retrofit
    Freezes the validated AV-10-equivalent reference geometry (L=107.5 m, fineness ratio=4.00760, V=18 m/s) for every architecture and asks whether technology improvement alone can make that retrofit physics-feasible and field-feasible.

Assessment B -- architecture-specific Pareto baseline
    Imports the representative feasible common-mission design for each
    architecture from the validated LHS + NSGA-II study, freezes that
    architecture-specific geometry/operating point, and then varies technology.
    Architectures with no feasible common-mission Pareto design are not assigned
    an artificial baseline; they are explicitly reported as unavailable.

Two feasibility definitions are exported for every converged point:
    physics_feasible
        Matches the outer architecture-comparison logic: power, buoyancy,
        envelope volume, lift, mass closure, installed-power closure and, for
        fuel-only architectures, consumable-energy closure. Ground roll is not
        a rejection criterion.
    operational_feasible
        physics_feasible plus the 300 m ground-roll requirement.

The script retains the current one-at-a-time technology sweeps, coupled maps,
frozen technology roadmap, publication tables, failure audits, and optional
controlled reoptimization. Coupled maps and roadmaps show both physics and
operational distance-to-feasibility metrics.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import time
import traceback
import warnings
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm
import numpy as np
import openmdao.api as om
import pandas as pd

try:
    om.utils.reports_system.clear_reports()
except Exception:
    os.environ["OPENMDAO_REPORTS"] = "0"


# =============================================================================
# PROJECT PATH
# =============================================================================

MANUAL_PROJECT_ROOT: Optional[str] = None

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent

if MANUAL_PROJECT_ROOT:
    PROJECT_ROOT = Path(MANUAL_PROJECT_ROOT).expanduser().resolve()
elif THIS_DIR.name.lower() in {"studies", "validation"}:
    PROJECT_ROOT = THIS_DIR.parent
else:
    PROJECT_ROOT = THIS_DIR

CORE_DIR = PROJECT_ROOT / "adapt"

if not (CORE_DIR / "AirshipAnalysisGroup.py").exists():
    raise ModuleNotFoundError(
        "Could not locate core/AirshipAnalysisGroup.py.\n"
        f"Expected: {CORE_DIR / 'AirshipAnalysisGroup.py'}\n"
        "Set MANUAL_PROJECT_ROOT near the top of this script."
    )

for p in list(sys.path):
    try:
        rp = Path(p).resolve()
    except Exception:
        continue
    if "airship-design-tool" in str(rp).lower():
        try:
            sys.path.remove(p)
        except ValueError:
            pass

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CORE_DIR))

import adapt.AirshipAnalysisGroup as airship_group_module
from adapt.AirshipWeight import AirshipWeight as _BaseAirshipWeight
from adapt.operatingConditions import opCond


class ClassConfiguredAirshipWeight(_BaseAirshipWeight):
    """Validated AV-10-equivalent single-lobe non-rigid weight settings."""

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
            "hydrogen_reciprocating",
            "hydrogen_fuel_cell",
            "hydrogen_hybrid",
            "solar_hydrogen_hybrid",
        }:
            tank_mass = max(self._scalar(inputs["tank_mass"]), 0.0)
        else:
            tank_mass = 0.0

        misc_fraction = float(self.options["miscellaneous_fraction"])
        landing_fraction = float(self.options["landing_gear_fraction"])

        pre_misc = (
            envelope_mass + gondola_mass + fin_mass + propulsion_mass
            + power_system_mass + tank_mass + crew_mass
        )
        miscellaneous_mass = pre_misc * misc_fraction
        base_no_landing = pre_misc + miscellaneous_mass + helium_mass
        mtow = (
            base_no_landing + payload + consumable_mass + ballast_mass
        ) / max(1.0 - landing_fraction, 1.0e-12)
        landing_mass = landing_fraction * mtow
        owe = base_no_landing + landing_mass

        outputs["gondola_mass"] = gondola_mass
        outputs["miscellaneous_mass"] = miscellaneous_mass
        outputs["landing_system_mass"] = landing_mass
        outputs["owe"] = owe
        outputs["mtow"] = mtow
        outputs["operational_weight"] = owe + payload
        outputs["structure_mass"] = (
            envelope_mass + gondola_mass + fin_mass + landing_mass
            + miscellaneous_mass + helium_mass
        )
        outputs["installed_system_mass"] = (
            propulsion_mass + power_system_mass + tank_mass
        )
        outputs["useful_load_mass"] = payload + crew_mass
        outputs["installed_consumable_mass"] = consumable_mass
        outputs["mass_balance_error"] = (
            mtow - (owe + payload + consumable_mass + ballast_mass)
        )

airship_group_module.AirshipWeight = ClassConfiguredAirshipWeight
AirshipAnalysisGroup = airship_group_module.AirshipAnalysisGroup


# =============================================================================
# USER CONFIGURATION
# =============================================================================

SCHEMA_VERSION = "technology_assessment_av10_dual_v2_pfei_matched"
OUTPUT_DIR_DEFAULT = "technology_assessment_av10_dual_v2_pfei_matched_outputs"

NUM_STEPS = 1
COMMON_PAYLOAD_KG = 10_000.0
COMMON_RANGE_KM = 2_000.0
COMMON_CRUISE_ALT_M = 2_740.0
COMMON_CRUISE_SPEED_MS = 20.6
REFERENCE_CRUISE_SPEED_MS = 20.6
COMMON_LENGTH_M = 107.5
COMMON_FINENESS_RATIO = 4.00760
COMMON_N_ENGINES = 4
COMMON_N_CREW = 2
FIELD_LENGTH_LIMIT_M = 300.0

T_ENV_K = 281.65
RH_PCT = 70.0

MTOW_SANITY_CEILING_KG = 100_000.0

# Match the numerical feasibility tolerances used by the validated
# AV-10 PFEI/LHS+NSGA-II architecture study.
CONSTRAINT_TOL = {
    "power_W": 1.0,
    "energy": 1.0e-6,
    "buoyancy_N": 1.0,
    "groundroll_m": 1.0,
    "lift": 1.0e-6,
    "volume_m3": 1.0e-6,
    "mass_balance_kg": 1.0e-2,
}

NLBGS_MAXITER = 300
NLBGS_ATOL = 1.0e-8
NLBGS_RTOL = 1.0e-8

SLSQP_MAXITER = 180
SLSQP_TOL = 1.0e-7
QUIET_DRIVER_OUTPUT = True

# Robust roadmap optimization controls.
OPTIMIZATION_MTOW_ABS_TOL_KG = 0.25
OPTIMIZATION_MTOW_REL_TOL = 1.0e-5
MAX_MULTISTART_CASES = 6

PLOT_DPI = 400

# Publication-grade numerical audit controls.
ADAPTIVE_SWEEP_MAX_ROUNDS = 3
ADAPTIVE_SWEEP_JUMP_FRACTION = 0.15
ADAPTIVE_SWEEP_MIN_REL_SPACING = 2.5e-3
ADAPTIVE_SWEEP_MAX_NEW_POINTS_PER_ROUND = 24
FEASIBILITY_DISTANCE_EPS = 1.0e-12
PLOT_SHOW_INFEASIBLE_RESPONSES = True


# Direct operational-emission factors for reporting only.
EI_CO2_PER_KG_CONVENTIONAL_FUEL = 3258.0 / 1051.0
EI_NOX_PER_KG_CONVENTIONAL_FUEL = 13.01 / 1051.0
EI_H2O_PER_KG_CONVENTIONAL_FUEL = 1422.0 / 1051.0
EI_H2O_PER_KG_H2 = 8.935

# AV-10 equivalent installed-power closure settings, matching the validated LHS + NSGA-II study.
USE_INSTALLED_POWER_CLOSURE = True
POWER_MARGIN = 1.10
POWER_CLOSURE_MAX_ITERS = 20
POWER_CLOSURE_RELAX = 0.55
POWER_CLOSURE_RTOL = 1.0e-3

# AV-10 equivalent reference data used for validation / reporting.
REFERENCE_MTOW_KG = 21_500.0
REFERENCE_VOLUME_M3 = 40_500.0
REFERENCE_POWER_W = 1_500_000.0
REFERENCE_CRUISE_SPEED_MS = 20.6
REFERENCE_SITE_DIAMETER_M = 300.0

def _reference_prolate_wetted_area(length_m: float, fineness_ratio: float) -> float:
    """Approximate prolate-spheroid wetted area for fixed solar coverage."""
    a = 0.5 * float(length_m)
    b = 0.5 * float(length_m) / float(fineness_ratio)
    e = np.sqrt(max(1.0 - (b*b)/(a*a), 0.0))
    if e < 1.0e-10:
        return float(4.0 * np.pi * a * a)
    return float(2.0*np.pi*b*b*(1.0 + (a/(b*e))*np.arcsin(e)))

REFERENCE_WETTED_AREA_M2 = _reference_prolate_wetted_area(COMMON_LENGTH_M, COMMON_FINENESS_RATIO)
REFERENCE_SOLAR_COVERAGE_FRACTION = 0.20
REFERENCE_SOLAR_AREA_M2 = REFERENCE_SOLAR_COVERAGE_FRACTION * REFERENCE_WETTED_AREA_M2
REFERENCE_SOLAR_AVAILABILITY_FACTOR = 0.65

# Match the AV-10 ICE calibration used in the validated PFEI study.
AV10_ICE_SPECIFIC_POWER_WKG = 3000.0
AV10_ICE_THERMAL_EFFICIENCY = 0.36


# =============================================================================
# ARCHITECTURES AND REFERENCE DESIGN
# =============================================================================

ARCH_CONFIGS: Dict[str, Dict[str, Any]] = {
    "conventional_reciprocating": {
        "label": "Conventional ICE",
        "family": "fuel",
        "storage_type": "helium",
        "installed_shaft_power_W": 1_500_000.0,
        "color": "#404040",
    },
    "hydrogen_reciprocating": {
        "label": "Hydrogen ICE",
        "family": "hydrogen",
        "storage_type": "liquid_h2",
        "installed_shaft_power_W": 1_500_000.0,
        "color": "#d62728",
    },
    "battery_only": {
        "label": "Battery electric",
        "family": "battery",
        "storage_type": "helium",
        "installed_shaft_power_W": 1_500_000.0,
        "color": "#2ca02c",
    },
    "solar_battery": {
        "label": "Solar-battery",
        "family": "solar",
        "storage_type": "helium",
        "installed_shaft_power_W": 1_500_000.0,
        "color": "#9467bd",
    },
}

ARCHITECTURE_ORDER = list(ARCH_CONFIGS)

REFERENCE_DESIGN = {
    "length_m": COMMON_LENGTH_M,
    "fineness_ratio": COMMON_FINENESS_RATIO,
    "br_takeoff": 0.90,
    "br_landing": 0.90,
    "tvc_h": 0.066,
    "tvc_v": 0.059,
    "lift_coeff": 0.15,
    "drag_due_to_lift_factor": 0.25,
    "drag_coeff_zero": 0.030,
    "propeller_efficiency": 0.82,
    "thrust_vector_angle_deg": 0.0,
}

LOCAL_DESIGN_BOUNDS = {
    "BR_takeoff": (0.82, 0.94),
    "tail_volume_coeff_horizontal": (0.055, 0.080),
    "tail_volume_coeff_vertical": (0.050, 0.070),
    "lift_coeff": (0.10, 0.20),
    "drag_due_to_lift_factor": (0.80, 0.95),
}

# Propeller efficiency is intentionally excluded from the roadmap optimizer.
# It is a technology input and remains available in the dedicated sensitivity
# and coupled-map studies. Allowing SLSQP to alter it would mix technology
# forecasting with vehicle-design adaptation and previously drove the hydrogen
# case toward an unphysical lower-bound solution.


# =============================================================================
# TECHNOLOGY SCENARIOS
# =============================================================================

@dataclass(frozen=True)
class TechnologyScenario:
    year: int
    horizon: str
    battery_specific_energy_Wh_kg: float
    battery_volumetric_ed_Wh_L: float
    motor_specific_power_W_kg: float
    motor_efficiency: float
    inverter_efficiency: float
    solar_efficiency: float
    solar_area_m2: float
    pv_areal_density_kg_m2: float
    solar_irradiance_W_m2: float
    tank_gravimetric_efficiency: float
    battery_technology: str
    electric_machine_technology: str
    power_electronics_technology: str
    tank_technology: str
    source_note: str


# Paper-derived values are used whenever the current ADaPT components expose
# the same physical quantity. Solar quantities are airship-specific extensions
# because the reference regional-aircraft paper did not assess photovoltaic
# collection. The medium-term tank value 0.127 and long-term value 0.405 follow
# the gravimetric indices reported for pressurized and cryogenic H2 storage.
ROADMAP_SCENARIOS: Tuple[TechnologyScenario, ...] = (
    TechnologyScenario(
        year=2030,
        horizon="AV-10 current-technology anchor",
        battery_specific_energy_Wh_kg=300.0,
        battery_volumetric_ed_Wh_L=650.0,
        motor_specific_power_W_kg=5_500.0,
        motor_efficiency=0.95,
        inverter_efficiency=0.98,
        solar_efficiency=0.26,
        solar_area_m2=REFERENCE_SOLAR_AREA_M2,
        pv_areal_density_kg_m2=2.50,
        solar_irradiance_W_m2=600.0,
        tank_gravimetric_efficiency=0.08,
        battery_technology="Li-Ion",
        electric_machine_technology="Liquid-cooled PMSM with hairpin windings",
        power_electronics_technology="SiC converters",
        tank_technology="Pressurized H2 reference; hydrogen short-term is an ADaPT extension",
        source_note="Matches the validated AV-10 equivalent current technology assumptions used in the latest LHS + NSGA-II study; solar area is fixed at 20% reference wetted area.",
    ),
    TechnologyScenario(
        year=2040,
        horizon="Medium-term (2035-2045)",
        battery_specific_energy_Wh_kg=675.0,
        battery_volumetric_ed_Wh_L=735.0,
        motor_specific_power_W_kg=10_000.0,
        motor_efficiency=0.95,
        inverter_efficiency=0.98,
        solar_efficiency=0.28,
        solar_area_m2=REFERENCE_SOLAR_AREA_M2,
        pv_areal_density_kg_m2=0.40,
        solar_irradiance_W_m2=600.0,
        tank_gravimetric_efficiency=0.127,
        battery_technology="Li-S",
        electric_machine_technology="Halbach-array PMSM with direct-cooled stator windings",
        power_electronics_technology="SiC converters",
        tank_technology="Pressurized H2 tank",
        source_note="Battery values follow the selected medium-term Li-S case; tank gravimetric efficiency follows the reported 12.7% selected pressurized-tank result.",
    ),
    TechnologyScenario(
        year=2050,
        horizon="Long-term (2045-2050+)",
        battery_specific_energy_Wh_kg=945.0,
        battery_volumetric_ed_Wh_L=945.0,
        motor_specific_power_W_kg=10_000.0,
        motor_efficiency=0.95,
        inverter_efficiency=0.985,
        solar_efficiency=0.34,
        solar_area_m2=REFERENCE_SOLAR_AREA_M2,
        pv_areal_density_kg_m2=0.30,
        solar_irradiance_W_m2=600.0,
        tank_gravimetric_efficiency=0.405,
        battery_technology="Li-O2",
        electric_machine_technology="Halbach-array PMSM with direct-cooled stator windings",
        power_electronics_technology="GaN converters",
        tank_technology="Cryogenic LH2 tank",
        source_note="Battery values follow Table 5; tank gravimetric efficiency follows the reported 40.5% long-term cryogenic result. Solar assumptions are airship-specific.",
    ),
)

BASELINE_SCENARIO = TechnologyScenario(
    year=2026,
    horizon="Validated AV-10 current-technology anchor",
    battery_specific_energy_Wh_kg=300.0,
    battery_volumetric_ed_Wh_L=650.0,
    motor_specific_power_W_kg=5_500.0,
    motor_efficiency=0.95,
    inverter_efficiency=0.98,
    solar_efficiency=0.26,
    solar_area_m2=REFERENCE_SOLAR_AREA_M2,
    pv_areal_density_kg_m2=2.50,
    solar_irradiance_W_m2=600.0,
    tank_gravimetric_efficiency=0.08,
    battery_technology="Current AV-10 study assumption",
    electric_machine_technology="Current-study electric machine assumption",
    power_electronics_technology="Current-study converter assumption",
    tank_technology="Current AV-10 hydrogen-storage assumption",
    source_note="Matches the validated AV-10 equivalent LHS + NSGA-II study technology anchor.",
)


@dataclass(frozen=True)
class AssessmentCase:
    architecture: str
    payload_kg: float = COMMON_PAYLOAD_KG
    range_km: float = COMMON_RANGE_KM
    cruise_alt_m: float = COMMON_CRUISE_ALT_M
    cruise_speed_ms: float = COMMON_CRUISE_SPEED_MS
    length_m: float = COMMON_LENGTH_M
    fineness_ratio: float = COMMON_FINENESS_RATIO

    br_takeoff: float = REFERENCE_DESIGN["br_takeoff"]
    br_landing: float = REFERENCE_DESIGN["br_landing"]
    tvc_h: float = REFERENCE_DESIGN["tvc_h"]
    tvc_v: float = REFERENCE_DESIGN["tvc_v"]
    lift_coeff: float = REFERENCE_DESIGN["lift_coeff"]
    drag_due_to_lift_factor: float = REFERENCE_DESIGN["drag_due_to_lift_factor"]
    drag_coeff_zero: float = REFERENCE_DESIGN["drag_coeff_zero"]
    propeller_efficiency: float = REFERENCE_DESIGN["propeller_efficiency"]
    thrust_vector_angle_deg: float = REFERENCE_DESIGN["thrust_vector_angle_deg"]

    battery_specific_energy: float = BASELINE_SCENARIO.battery_specific_energy_Wh_kg
    battery_volumetric_ed: float = BASELINE_SCENARIO.battery_volumetric_ed_Wh_L
    solar_efficiency: float = BASELINE_SCENARIO.solar_efficiency
    solar_area_m2: float = BASELINE_SCENARIO.solar_area_m2
    pv_areal_density: float = BASELINE_SCENARIO.pv_areal_density_kg_m2
    solar_irradiance_W_m2: float = BASELINE_SCENARIO.solar_irradiance_W_m2
    solar_availability_factor: float = REFERENCE_SOLAR_AVAILABILITY_FACTOR
    tank_gravimetric_efficiency: float = BASELINE_SCENARIO.tank_gravimetric_efficiency
    motor_specific_power: float = BASELINE_SCENARIO.motor_specific_power_W_kg
    motor_efficiency: float = BASELINE_SCENARIO.motor_efficiency
    inverter_efficiency: float = BASELINE_SCENARIO.inverter_efficiency

    # Baseline provenance. These fields do not enter the physics model; they
    # make every technology result traceable to either the reference-geometry
    # retrofit case or the architecture-specific common-mission Pareto design.
    baseline_mode: str = "reference_geometry_retrofit"
    baseline_source_file: str = ""
    baseline_source_mtow_kg: float = np.nan
    baseline_source_pfei: float = np.nan
    baseline_source_selection: str = "reference_geometry"

    @property
    def architecture_label(self) -> str:
        return ARCH_CONFIGS[self.architecture]["label"]

    @property
    def installed_shaft_power_W(self) -> float:
        return float(ARCH_CONFIGS[self.architecture]["installed_shaft_power_W"])


def common_mission_cases() -> Dict[str, AssessmentCase]:
    """Reference-geometry retrofit cases.

    The nominal AV-10 equivalent geometry/operating point is frozen for every architecture.
    This is a retrofit question, not an architecture-ranking question.
    """
    return {
        architecture: AssessmentCase(
            architecture=architecture,
            baseline_mode="reference_geometry_retrofit",
            baseline_source_selection="AV-10 validated nominal reference geometry",
        )
        for architecture in ARCHITECTURE_ORDER
    }


def _bool_series(series: pd.Series) -> pd.Series:
    """Robust conversion of CSV boolean-like columns."""
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _pareto_utopia_knee(df: pd.DataFrame) -> pd.Series:
    """Reproduce the two-objective common-mission knee if no knee flag exists."""
    work = df.copy()
    if "pareto" in work.columns:
        mask = _bool_series(work["pareto"])
        if mask.any():
            work = work.loc[mask].copy()
    work = work[
        np.isfinite(pd.to_numeric(work.get("mtow_kg"), errors="coerce"))
        & np.isfinite(pd.to_numeric(work.get("pfei_MJ_per_kg_km"), errors="coerce"))
    ].copy()
    if work.empty:
        raise ValueError("No finite feasible points are available for baseline selection.")
    m = pd.to_numeric(work["mtow_kg"], errors="coerce").to_numpy(float)
    e = pd.to_numeric(work["pfei_MJ_per_kg_km"], errors="coerce").to_numpy(float)
    mn = (m - np.min(m)) / max(float(np.max(m)-np.min(m)), 1e-12)
    en = (e - np.min(e)) / max(float(np.max(e)-np.min(e)), 1e-12)
    return work.iloc[int(np.argmin(np.sqrt(mn*mn + en*en)))]


def _pareto_search_roots(requested_root: Path) -> List[Path]:
    """Return de-duplicated roots that may contain the AV-10 equivalent Pareto study.

    The previous loader assumed that ``--pareto-output-dir`` pointed directly to
    the exact output root.  In Spyder/IDE runs the working directory is often the
    ``studies`` folder, while the LHS+NSGA-II results may have been written below
    the project root, below ``studies/``, or below an older copied output folder.
    Assessment B should not disappear merely because of that path ambiguity.
    """
    raw_roots = [
        requested_root,
        requested_root.parent,
        Path.cwd(),
        Path.cwd() / "studies",
        THIS_FILE.parent,
        THIS_FILE.parent / "pfei_av10_outputs",
        PROJECT_ROOT,
        PROJECT_ROOT / "studies",
        PROJECT_ROOT / "pfei_av10_outputs",
        PROJECT_ROOT / "studies" / "pfei_av10_outputs",
    ]

    roots: List[Path] = []
    seen = set()
    for item in raw_roots:
        try:
            p = Path(item).expanduser().resolve()
        except Exception:
            continue
        key = str(p).lower()
        if key in seen or not p.exists() or not p.is_dir():
            continue
        seen.add(key)
        roots.append(p)
    return roots


def _pareto_file_rank(path: Path, architecture: str, requested_root: Path) -> Tuple[int, int, int, float, str]:
    """Rank candidate architecture-study CSVs deterministically.

    Lower is better.  We prefer a common-mission success table, then a Pareto
    front, then an all-points table.  Files below the user-requested root are
    preferred over global fallbacks; newer files break otherwise-equal ties.
    """
    low = path.name.lower()
    if "success" in low:
        kind_rank = 0
    elif "pareto_front" in low or ("pareto" in low and "front" in low):
        kind_rank = 1
    elif "all" in low:
        kind_rank = 2
    else:
        kind_rank = 3

    try:
        path.resolve().relative_to(requested_root.resolve())
        requested_rank = 0
    except Exception:
        requested_rank = 1

    # Exact architecture token in the filename outranks merely being in a
    # matching architecture directory.
    arch_rank = 0 if architecture.lower() in low else 1
    try:
        mtime_rank = -float(path.stat().st_mtime)
    except OSError:
        mtime_rank = 0.0
    return (kind_rank, requested_rank, arch_rank, mtime_rank, str(path).lower())


def _find_pareto_success_csv(root: Path, architecture: str) -> Optional[Path]:
    """Locate the best AV-10 equivalent common-mission architecture-study CSV robustly.

    This loader accepts the exact architecture-output root, the ``studies``
    directory, the project root, or an arbitrary working directory.  It searches
    all plausible roots for the validated output products written by the AV-10 equivalent
    LHS+NSGA-II script:

      * ``pfei_success_common_mission_<architecture>.csv``
      * ``pareto_front_common_mission_<architecture>.csv`` (when available)
      * ``pfei_all_common_mission_<architecture>.csv``

    Only files containing the ``common_mission`` token are admitted, preventing
    native-envelope results from being used accidentally as Assessment-B
    baselines.
    """
    preferred_names = [
        f"pfei_success_common_mission_{architecture}.csv",
        f"pareto_front_common_mission_{architecture}.csv",
        f"pfei_all_common_mission_{architecture}.csv",
    ]

    candidates: List[Path] = []
    seen = set()

    def add(path: Path) -> None:
        try:
            rp = path.resolve()
        except Exception:
            rp = path
        key = str(rp).lower()
        if key in seen or not path.is_file():
            return
        low = path.name.lower()
        if "common_mission" not in low:
            return
        # Architecture may be encoded either in the filename or parent folder.
        parent_tokens = {p.name.lower() for p in path.parents}
        if architecture.lower() not in low and architecture.lower() not in parent_tokens:
            return
        seen.add(key)
        candidates.append(path)

    search_roots = _pareto_search_roots(root)

    # Fast exact checks first.
    for base in search_roots:
        direct_dirs = [
            base / "common_mission" / architecture,
            base / architecture,
            base,
        ]
        for directory in direct_dirs:
            for name in preferred_names:
                p = directory / name
                if p.exists():
                    add(p)

    # Recursive exact-name search catches an extra output-root level and old
    # timestamped/copy folders.
    for base in search_roots:
        for name in preferred_names:
            try:
                for p in base.rglob(name):
                    add(p)
            except (OSError, PermissionError):
                pass

    # Last-resort tolerant matching supports renamed copies such as ``(1).csv``.
    for base in search_roots:
        try:
            for p in base.rglob("*.csv"):
                low = p.name.lower()
                if "common_mission" not in low:
                    continue
                if architecture.lower() not in low and architecture.lower() not in {q.name.lower() for q in p.parents}:
                    continue
                if not any(token in low for token in ("success", "pareto", "pfei_all", "all_common_mission")):
                    continue
                add(p)
        except (OSError, PermissionError):
            pass

    if not candidates:
        return None

    candidates.sort(key=lambda p: _pareto_file_rank(p, architecture, root))
    return candidates[0]


def _discover_pareto_output_root(requested: Any) -> Tuple[Path, pd.DataFrame]:
    """Discover the most complete common-mission Pareto output root.

    Returns the selected root plus a diagnostic table.  A root is scored by the
    number of architecture success/all/front files that can be found below it.
    This makes ``--pareto-output-dir auto`` safe for normal Spyder runs while
    preserving explicit-path behaviour when the user supplies a directory.
    """
    raw = str(requested).strip()
    auto = raw.lower() in {"", "auto", "discover", "none"}
    nominal = (PROJECT_ROOT / "pfei_av10_outputs") if auto else _resolve_pareto_root(raw)

    roots = _pareto_search_roots(nominal)
    rows: List[Dict[str, Any]] = []
    best_root = nominal
    best_score = -1

    for base in roots:
        found = {}
        for architecture in ARCHITECTURE_ORDER:
            p = _find_pareto_success_csv(base, architecture)
            # Only count a result if it is actually under this candidate base;
            # _find_pareto_success_csv itself has global fallbacks.
            local = False
            if p is not None:
                try:
                    p.resolve().relative_to(base.resolve())
                    local = True
                except Exception:
                    local = False
            found[architecture] = str(p) if local and p is not None else ""
        score = sum(bool(v) for v in found.values())
        rows.append({"candidate_root": str(base), "architectures_found": score, **found})
        if score > best_score:
            best_score = score
            best_root = base
        elif score == best_score and score >= 0:
            # Prefer the canonical folder name when scores tie.
            if base.name.lower() == "pfei_av10_outputs" and best_root.name.lower() != "pfei_av10_outputs":
                best_root = base

    return best_root.resolve(), pd.DataFrame(rows)

def load_architecture_specific_pareto_cases(
    pareto_output_dir: Path,
) -> Tuple[Dict[str, AssessmentCase], pd.DataFrame]:
    """Load one architecture-specific common-mission Pareto baseline per architecture.

    Selection priority is the knee marker written by the validated LHS+NSGA-II
    architecture study. If that marker is absent, the same normalized 2-D utopia
    distance is recomputed from the Pareto set. No infeasible design is promoted
    to a baseline. Architectures with no feasible common-mission point (currently
    possible for battery-only) are omitted and recorded in the audit table.
    """
    cases: Dict[str, AssessmentCase] = {}
    audit: List[Dict[str, Any]] = []

    for architecture in ARCHITECTURE_ORDER:
        csv_path = _find_pareto_success_csv(pareto_output_dir, architecture)
        if csv_path is None:
            audit.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "status": "missing_common_mission_pareto_csv",
                "source_file": "",
                "searched_root": str(pareto_output_dir),
            })
            continue

        df = pd.read_csv(csv_path)
        source_name = csv_path.name.lower()
        source_kind = (
            "success" if "success" in source_name
            else "pareto_front" if "pareto" in source_name and "front" in source_name
            else "all_points" if "all" in source_name
            else "fallback"
        )
        if df.empty:
            audit.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "status": "no_feasible_common_mission_design",
                "source_file": str(csv_path),
            })
            continue

        if "success" in df.columns:
            success = _bool_series(df["success"])
            df = df.loc[success].copy()
        if df.empty:
            audit.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "status": "no_success_rows",
                "source_file": str(csv_path),
            })
            continue

        selected = None
        selection = "recomputed_utopia_knee"
        if "knee" in df.columns:
            kmask = _bool_series(df["knee"])
            if kmask.any():
                selected = df.loc[kmask].iloc[0]
                selection = "stored_common_mission_knee"
        if selected is None:
            selected = _pareto_utopia_knee(df)

        def val(name: str, default: float) -> float:
            try:
                x = float(selected.get(name, default))
                return x if np.isfinite(x) else float(default)
            except Exception:
                return float(default)

        length = val("length_m", COMMON_LENGTH_M)
        fineness = val("fineness_ratio", COMMON_FINENESS_RATIO)
        speed = val("cruise_speed_mps", COMMON_CRUISE_SPEED_MS)
        solar_area = BASELINE_SCENARIO.solar_area_m2
        if architecture == "solar_battery":
            coverage = val("solar_coverage_fraction", REFERENCE_SOLAR_COVERAGE_FRACTION)
            solar_area = coverage * _reference_prolate_wetted_area(length, fineness)

        # Import the technology coordinates too whenever they are present.
        # In the common-mission architecture study these are normally fixed,
        # but importing them explicitly guarantees that Assessment B reproduces
        # the exact source design rather than silently substituting a different
        # technology anchor from this script.
        battery_se = val(
            "battery_specific_energy_Whkg",
            val("battery_specific_energy", BASELINE_SCENARIO.battery_specific_energy_Wh_kg),
        )
        battery_ve = val(
            "battery_volumetric_ed_WhL",
            val("battery_volumetric_ed", BASELINE_SCENARIO.battery_volumetric_ed_Wh_L),
        )
        solar_eff = val("solar_efficiency", BASELINE_SCENARIO.solar_efficiency)
        pv_areal = val("pv_areal_density_kg_m2", BASELINE_SCENARIO.pv_areal_density_kg_m2)
        tank_eta = val(
            "hydrogen_tank_gravimetric_efficiency",
            val("tank_gravimetric_efficiency", BASELINE_SCENARIO.tank_gravimetric_efficiency),
        )

        case = AssessmentCase(
            architecture=architecture,
            payload_kg=COMMON_PAYLOAD_KG,
            range_km=COMMON_RANGE_KM,
            cruise_alt_m=COMMON_CRUISE_ALT_M,
            cruise_speed_ms=speed,
            length_m=length,
            fineness_ratio=fineness,
            battery_specific_energy=battery_se,
            battery_volumetric_ed=battery_ve,
            solar_efficiency=solar_eff,
            solar_area_m2=solar_area,
            pv_areal_density=pv_areal,
            tank_gravimetric_efficiency=tank_eta,
            baseline_mode="architecture_specific_pareto",
            baseline_source_file=str(csv_path),
            baseline_source_mtow_kg=val("mtow_kg", np.nan),
            baseline_source_pfei=val("pfei_MJ_per_kg_km", np.nan),
            baseline_source_selection=selection,
        )
        cases[architecture] = case
        audit.append({
            "architecture": architecture,
            "architecture_name": case.architecture_label,
            "status": "loaded",
            "source_file": str(csv_path),
            "source_kind": source_kind,
            "selection": selection,
            "source_mtow_kg": case.baseline_source_mtow_kg,
            "source_pfei_MJ_per_kg_km": case.baseline_source_pfei,
            "length_m": length,
            "fineness_ratio": fineness,
            "cruise_speed_mps": speed,
            "solar_area_m2": solar_area,
            "battery_specific_energy_Whkg": battery_se,
            "battery_volumetric_ed_WhL": battery_ve,
            "solar_efficiency": solar_eff,
            "pv_areal_density_kg_m2": pv_areal,
            "tank_gravimetric_efficiency": tank_eta,
        })

    return cases, pd.DataFrame(audit)


# =============================================================================
# PLOTTING STYLE
# =============================================================================

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "axes.grid": True,
    "grid.alpha": 0.28,
    "grid.linestyle": ":",
    "legend.fontsize": 8,
    "figure.titlesize": 14,
})


# =============================================================================
# BASIC HELPERS
# =============================================================================

def _isfinite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def _scalar(value: Any, default: float = np.nan) -> float:
    try:
        return float(np.asarray(value, dtype=float).reshape(-1)[0])
    except Exception:
        return default


def _get(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        return _scalar(prob.get_val(name, units=units), default)
    except Exception:
        return default


def _max_get(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        return float(np.max(np.asarray(prob.get_val(name, units=units), dtype=float)))
    except Exception:
        return default


def _get_first(
    prob: om.Problem,
    names: Sequence[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> Tuple[float, str]:
    for name in names:
        value = _get(prob, name, units=units, default=np.nan)
        if _isfinite(value):
            return value, name
    return default, ""


def _set_required(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> None:
    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
    except Exception as exc:
        raise KeyError(
            f"Required promoted variable {name!r} is unavailable: {exc}"
        ) from exc


def _set_optional(
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


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "ok"}
    return bool(value)


def _cleanup(prob: Optional[om.Problem]) -> None:
    if prob is None:
        return
    try:
        prob.cleanup()
    except Exception:
        pass


def _driver_success(result: Any) -> bool:
    if hasattr(result, "success"):
        return bool(result.success)
    if hasattr(result, "fail"):
        return not bool(result.fail)
    if isinstance(result, (bool, np.bool_)):
        return not bool(result)
    return True


def _run_driver_captured(prob: om.Problem) -> Tuple[Any, str]:
    stream = io.StringIO()
    if QUIET_DRIVER_OUTPUT:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            result = prob.run_driver()
    else:
        result = prob.run_driver()
    return result, stream.getvalue()


def _ensure_dir(path: str | Path) -> Path:
    out = Path(path).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _ensure_baseline(values: Iterable[float], baseline: float) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if not np.any(np.isclose(arr, baseline, rtol=1.0e-9, atol=1.0e-12)):
        arr = np.append(arr, baseline)
    return np.unique(np.sort(arr))


def _solver_status(prob: om.Problem) -> Tuple[bool, int, float]:
    """Return a portable nonlinear-solver convergence audit.

    The top-level NLBGS can converge on either absolute or relative tolerance,
    while OpenMDAO does not expose the initial residual norm consistently across
    versions.  Therefore max-iteration exhaustion is the portable failure test;
    the final norm is retained as a diagnostic rather than used as a second,
    potentially false, rejection criterion.
    """
    solver = prob.model.nonlinear_solver
    maxiter = int(solver.options["maxiter"])
    iterations = int(getattr(solver, "_iter_count", -1))
    norm = float(getattr(solver, "_norm", np.nan))
    converged = iterations >= 0 and iterations < maxiter
    return bool(converged), iterations, norm


# =============================================================================
# MODEL BUILD
# =============================================================================

def build_problem(
    case: AssessmentCase,
    with_driver: bool = False,
) -> om.Problem:
    """Build the current centralized AirshipAnalysisGroup model."""

    phd = opCond(
        name="Cruise",
        T_env=T_ENV_K,
        altitude=case.cruise_alt_m,
        # Match the validated PFEI model construction. The sampled/selected
        # cruise speed is applied through the promoted cruise_speed input below.
        speed=REFERENCE_CRUISE_SPEED_MS / 337.5,
        time="day",
        RH=RH_PCT,
    )

    # Match the governing-model construction used by the validated AV-10
    # PFEI/LHS+NSGA-II study so imported Assessment-B Pareto points are
    # re-evaluated under the same model definition.
    model = AirshipAnalysisGroup(
        phd=phd,
        power_source=case.architecture,
        airship_type="non-rigid",
        landing_system="conventional",
        enable_pressure_control=False,
        num_steps=NUM_STEPS,
        use_prescribed_consumable_capacity=False,
    )

    # Match the PFEI study's promoted-input defaults before setup. These are
    # metadata/default values; the exact case values are set after setup.
    model.set_input_defaults(
        "cruise_altp",
        val=np.full(NUM_STEPS, COMMON_CRUISE_ALT_M),
        units="m",
    )
    model.set_input_defaults(
        "range",
        val=COMMON_RANGE_KM * 1000.0,
        units="m",
    )
    model.set_input_defaults(
        "cruise_speed",
        val=np.full(NUM_STEPS, REFERENCE_CRUISE_SPEED_MS),
        units="m/s",
    )

    prob = om.Problem(model=model)

    # Apply the same operational field-length requirement used in the validated
    # AV-10 equivalent LHS + NSGA-II study, with compatibility fallback.
    performance = getattr(prob.model, "performance", None)
    if performance is None:
        performance = getattr(prob.model, "mission", None)
    if performance is not None and "field_length_limit" in performance.options:
        performance.options["field_length_limit"] = float(FIELD_LENGTH_LIMIT_M)

    if with_driver:
        # Only the validated local design variables are allowed to adapt.
        for name, (lower, upper) in LOCAL_DESIGN_BOUNDS.items():
            prob.model.add_design_var(name, lower=lower, upper=upper)

        prob.model.add_constraint("power_constraint", upper=0.0, ref=1.0e5)
        prob.model.add_constraint("energy_constraint", upper=0.0, ref=1.0)
        prob.model.add_constraint("buoyancy_constraint", upper=0.0, ref=1.0e4)
        prob.model.add_constraint(
            "ground_roll_distance",
            upper=FIELD_LENGTH_LIMIT_M,
            ref=FIELD_LENGTH_LIMIT_M,
        )
        prob.model.add_constraint("envelope_volume_violation", upper=0.0, ref=1.0)
        prob.model.add_constraint(
            "mass_balance_error",
            lower=-CONSTRAINT_TOL["mass_balance_kg"],
            upper=CONSTRAINT_TOL["mass_balance_kg"],
            ref=1.0,
        )
        prob.model.add_objective("mtow", scaler=1.0e-3)

        prob.driver = om.ScipyOptimizeDriver()
        prob.driver.options["optimizer"] = "SLSQP"
        prob.driver.options["maxiter"] = SLSQP_MAXITER
        prob.driver.options["tol"] = SLSQP_TOL
        prob.driver.options["disp"] = False

    prob.setup(check=False, force_alloc_complex=False)

    nonlinear = prob.model.nonlinear_solver
    nonlinear.options["maxiter"] = NLBGS_MAXITER
    nonlinear.options["atol"] = NLBGS_ATOL
    nonlinear.options["rtol"] = NLBGS_RTOL
    nonlinear.options["use_aitken"] = True
    nonlinear.options["iprint"] = -1
    nonlinear.options["err_on_non_converge"] = False

    linear = prob.model.linear_solver
    try:
        linear.options["iprint"] = -1
    except Exception:
        pass

    # Common mission and vehicle.
    _set_required(prob, "range", case.range_km * 1000.0, "m")
    _set_required(prob, "payload", case.payload_kg, "kg")
    _set_required(
        prob,
        "cruise_speed",
        np.full(NUM_STEPS, case.cruise_speed_ms),
        "m/s",
    )
    _set_required(prob, "cruise_altp", np.full(NUM_STEPS, case.cruise_alt_m), "m")
    _set_required(prob, "cruise_disa", np.zeros(NUM_STEPS), "K")
    _set_required(prob, "tailwind_speed", 0.0, "m/s")
    _set_required(prob, "length", case.length_m, "m")
    _set_required(prob, "fineness_ratio", case.fineness_ratio)
    _set_required(prob, "n_engine", float(COMMON_N_ENGINES))
    _set_required(prob, "n_crew", float(COMMON_N_CREW))
    _set_required(prob, "ballast_mass", 0.0, "kg")

    # Fixed or initialized local design.
    _set_required(prob, "BR_takeoff", case.br_takeoff)
    _set_required(prob, "BR_landing", case.br_landing)
    _set_required(prob, "tail_volume_coeff_horizontal", case.tvc_h)
    _set_required(prob, "tail_volume_coeff_vertical", case.tvc_v)
    _set_required(prob, "lift_coeff", case.lift_coeff)
    _set_required(
        prob,
        "drag_due_to_lift_factor",
        case.drag_due_to_lift_factor,
    )
    _set_required(prob, "drag_coeff_zero", case.drag_coeff_zero)
    _set_required(prob, "propeller_efficiency", case.propeller_efficiency)

    # Match the AV-10 reciprocating-engine calibration used by the PFEI study.
    if case.architecture in {"conventional_reciprocating", "hydrogen_reciprocating"}:
        _set_optional(prob, "ice_specific_power", AV10_ICE_SPECIFIC_POWER_WKG, "W/kg")
        _set_optional(prob, "ice_thermal_efficiency", AV10_ICE_THERMAL_EFFICIENCY)

    _set_required(
        prob,
        "thrust_vector_angle",
        case.thrust_vector_angle_deg,
        "deg",
    )

    # Architecture-specific installed total shaft power.
    _set_required(
        prob,
        "installed_shaft_power",
        case.installed_shaft_power_W,
        "W",
    )

    # Consumables remain internally sized. A zero initial value is supplied
    # only where the promoted input exists.
    _set_optional(prob, "fuel_onboard_mass", np.zeros(NUM_STEPS), "kg")

    # Canonical current technology inputs.
    _set_required(
        prob,
        "battery_specific_energy",
        case.battery_specific_energy,
        "W*h/kg",
    )
    _set_required(
        prob,
        "battery_volumetric_ed",
        case.battery_volumetric_ed,
        "W*h/L",
    )
    _set_required(prob, "solar_efficiency", case.solar_efficiency)
    _set_required(prob, "solar_area", case.solar_area_m2, "m**2")
    _set_required(prob, "pv_areal_density", case.pv_areal_density, "kg/m**2")
    _set_required(
        prob,
        "solar_irradiance",
        np.full(NUM_STEPS, case.solar_irradiance_W_m2),
        "W/m**2",
    )

    # Match the current AV-10 PFEI solar-availability assumption when exposed.
    for _solar_availability_name in ("solar_availability_factor", "solar_availability"):
        if _set_optional(
            prob,
            _solar_availability_name,
            case.solar_availability_factor,
        ):
            break

    if case.architecture == "solar_battery":
        _set_required(prob, "solar_energy", 0.0, "MJ")

    _set_required(
        prob,
        "tank_gravimetric_efficiency",
        case.tank_gravimetric_efficiency,
    )

    # Paper-derived electric-machine and converter forecasts. These are
    # optional only to remain compatible with model variants that do not yet
    # promote a particular technology input. Their requested and applied values
    # are both recorded in the output tables.
    _set_optional(prob, "motor_specific_power", case.motor_specific_power, "W/kg")
    _set_optional(prob, "motor_efficiency", case.motor_efficiency)
    _set_optional(prob, "inverter_efficiency", case.inverter_efficiency)

    # Tank.storage_type is a non-promoted discrete input in the current model.
    # The current Tank component already defaults to liquid_h2, so no generic
    # promoted storage_type assignment is attempted here.

    return prob


# =============================================================================
# FEASIBILITY AND RESULTS
# =============================================================================

def _run_power_closure(prob: om.Problem, case: AssessmentCase) -> Tuple[bool, float]:
    """Close installed shaft power exactly as in the validated AV-10 equivalent DSE.

    Consumable/battery sizing stays internal to AirshipAnalysisGroup. Only the
    externally-owned installed shaft-power input is iterated to a 10% margin.
    """
    installed = max(float(case.installed_shaft_power_W), 1.0)
    last_error = np.inf
    for _ in range(POWER_CLOSURE_MAX_ITERS):
        _set_required(prob, "installed_shaft_power", installed, "W")
        prob.run_model()
        required, _ = _get_first(prob, ["required_shaft_power", "required_power"], "W", np.nan)
        if not _isfinite(required) or required <= 0.0:
            return False, np.inf
        target = max(float(required) * POWER_MARGIN, 1.0)
        new_installed = installed + POWER_CLOSURE_RELAX * (target - installed)
        last_error = abs(new_installed - installed) / max(abs(installed), 1.0)
        installed = new_installed
        if last_error < POWER_CLOSURE_RTOL:
            break
    _set_required(prob, "installed_shaft_power", installed, "W")
    prob.run_model()
    required, _ = _get_first(prob, ["required_shaft_power", "required_power"], "W", np.nan)
    if not _isfinite(required):
        return False, np.inf
    converged = (last_error < max(5.0 * POWER_CLOSURE_RTOL, 5.0e-3) and installed >= required - CONSTRAINT_TOL["power_W"])
    return bool(converged), float(last_error)

def collect_results(
    prob: om.Problem,
    case: AssessmentCase,
    study_type: str,
    parameter: str = "",
    parameter_value: float = np.nan,
    driver_success: Optional[bool] = None,
    driver_message: str = "",
    elapsed_s: float = np.nan,
) -> Dict[str, Any]:
    solver_converged, solver_iterations, solver_norm = _solver_status(prob)

    mtow = _get(prob, "mtow", "kg")
    owe = _get(prob, "owe", "kg")
    operational_weight = _get(prob, "operational_weight", "kg")
    gross_volume = _get(prob, "gross_volume", "m**3")
    mission_duration_s = _get(prob, "mission_duration", "s")

    required_power_W = _max_get(prob, "required_power", "W")
    installed_power_W = _get(
        prob,
        "installed_shaft_power",
        "W",
        case.installed_shaft_power_W,
    )

    g_power = _max_get(prob, "power_constraint", "W")
    g_energy = _max_get(prob, "energy_constraint")
    g_buoyancy = _max_get(prob, "buoyancy_constraint", "N")
    g_lift = _max_get(prob, "lift_constraint")
    ground_roll = _get(prob, "ground_roll_distance", "m")
    g_groundroll = ground_roll - FIELD_LENGTH_LIMIT_M
    g_volume = _get(prob, "envelope_volume_violation", "m**3")
    mass_balance = _get(prob, "mass_balance_error", "kg")

    consumable_mass, consumable_source = _get_first(
        prob,
        [
            "required_consumable_mass",
            "consumable_mass",
            "fuel_mass",
            "hydrogen_mass",
        ],
        "kg",
        0.0,
    )
    if case.architecture in {"battery_only", "solar_battery"}:
        consumable_mass = 0.0
        consumable_source = "not_applicable"

    battery_mass, battery_mass_source = _get_first(
        prob,
        ["battery_mass", "battery_pack_mass"],
        "kg",
        0.0,
    )
    battery_capacity_kWh, battery_capacity_source = _get_first(
        prob,
        ["battery_capacity", "net_battery_energy"],
        "kW*h",
        np.nan,
    )
    battery_volume_m3 = _get(prob, "battery_volume", "m**3")

    tank_mass, tank_mass_source = _get_first(
        prob,
        ["tank_mass", "tank_system_mass", "empty_tank_mass"],
        "kg",
        0.0,
    )
    tank_volume_m3, tank_volume_source = _get_first(
        prob,
        ["tank_installed_volume", "tank_volume"],
        "m**3",
        0.0,
    )

    propulsion_mass = _get(prob, "propulsion_mass", "kg")
    power_system_mass = _get(prob, "power_system_mass", "kg")
    power_system_volume = _get(prob, "power_system_volume", "m**3")

    solar_generated_kWh = _get(prob, "solar_energy_generated", "kW*h")
    solar_used_kWh = _get(prob, "solar_energy_used", "kW*h")
    solar_fraction = _get(prob, "solar_fraction")

    # ------------------------------------------------------------------
    # Numerical state and TWO feasibility definitions
    # ------------------------------------------------------------------
    # The validated LHS+NSGA-II architecture comparison deliberately does NOT
    # reject a design on ground-roll/landing distance in its outer Pareto loop.
    # It enforces power, buoyancy, envelope volume, static/aerodynamic lift,
    # mass closure, and (for fuel-only architectures) the consumable-energy
    # inequality.  The technology study now reproduces that definition exactly
    # as ``physics_feasible`` and reports the 300 m field requirement separately
    # as ``operational_feasible``. This prevents a field-performance diagnostic
    # from being mistaken for a contradiction with the architecture study.

    has_battery = case.architecture in {"battery_only", "solar_battery"}
    required_finite = [mtow, owe, gross_volume, g_power, g_buoyancy, g_lift, g_volume]
    if not has_battery:
        required_finite.append(g_energy)
    finite_core = all(_isfinite(v) for v in required_finite)

    mtow_sanity_warning = not (_isfinite(mtow) and 0.0 < mtow <= MTOW_SANITY_CEILING_KG)

    base_checks = {
        "solver": solver_converged,
        "finite": finite_core,
        "power": _isfinite(g_power) and g_power <= CONSTRAINT_TOL["power_W"],
        "buoyancy": _isfinite(g_buoyancy) and g_buoyancy <= CONSTRAINT_TOL["buoyancy_N"],
        "lift": _isfinite(g_lift) and g_lift <= CONSTRAINT_TOL["lift"],
        "volume": _isfinite(g_volume) and g_volume <= CONSTRAINT_TOL["volume_m3"],
        "mass_balance": (not _isfinite(mass_balance) or abs(mass_balance) <= CONSTRAINT_TOL["mass_balance_kg"]),
    }
    if not has_battery:
        base_checks["energy"] = _isfinite(g_energy) and g_energy <= CONSTRAINT_TOL["energy"]

    # Independent installed-power check, matching the architecture audit.
    installed_power_ok = (
        _isfinite(required_power_W) and _isfinite(installed_power_W)
        and required_power_W - installed_power_W <= CONSTRAINT_TOL["power_W"]
    )
    base_checks["installed_power"] = installed_power_ok

    physics_feasible = bool(all(base_checks.values()))
    physics_failure_reasons = [name for name, passed in base_checks.items() if not passed]

    field_check = _isfinite(g_groundroll) and g_groundroll <= CONSTRAINT_TOL["groundroll_m"]
    operational_feasible = bool(physics_feasible and field_check)
    operational_failure_reasons = list(physics_failure_reasons)
    if not field_check:
        operational_failure_reasons.append("ground_roll")

    # Backward-compatible ``feasible`` now means Pareto-comparable PHYSICS
    # feasibility.  Strict field-performance status is always retained in the
    # separate operational columns.
    feasible = physics_feasible
    failure_reasons = physics_failure_reasons

    numerical_failure = (not base_checks["solver"]) or (not base_checks["finite"])
    if physics_feasible:
        evaluation_status = "physics_feasible"
    elif numerical_failure:
        evaluation_status = "numerical_failure"
    else:
        evaluation_status = "physics_infeasible"

    if not physics_failure_reasons:
        dominant_failure_category = "none"
    elif numerical_failure:
        dominant_failure_category = "solver/convergence"
    elif "buoyancy" in physics_failure_reasons or "lift" in physics_failure_reasons:
        dominant_failure_category = "buoyancy/lift"
    elif "power" in physics_failure_reasons or "installed_power" in physics_failure_reasons:
        dominant_failure_category = "propulsion power"
    elif "energy" in physics_failure_reasons:
        dominant_failure_category = "energy/storage"
    elif "volume" in physics_failure_reasons:
        dominant_failure_category = "volume/envelope"
    else:
        dominant_failure_category = "other physics"

    operational_dominant_failure_category = (
        dominant_failure_category
        if physics_failure_reasons
        else ("field performance" if not field_check else "none")
    )

    # ------------------------------------------------------------------
    # Dimensionless utilization ratios.  A value of 1 is the active limit.
    # These are preferred to raw constraint residuals because unlike quantities
    # then become directly comparable.
    # ------------------------------------------------------------------
    weight_N = mtow * 9.80665 if _isfinite(mtow) and mtow > 0.0 else np.nan
    buoyant_capacity_N = (weight_N - g_buoyancy) if _isfinite(weight_N) and _isfinite(g_buoyancy) else np.nan
    buoyancy_utilization = (weight_N / buoyant_capacity_N if _isfinite(buoyant_capacity_N) and buoyant_capacity_N > 0.0 else np.nan)

    power_utilization = (
        required_power_W / installed_power_W
        if _isfinite(required_power_W) and _isfinite(installed_power_W) and installed_power_W > 0.0
        else np.nan
    )
    ground_roll_utilization = (ground_roll / FIELD_LENGTH_LIMIT_M if _isfinite(ground_roll) else np.nan)

    required_volume_m3 = (gross_volume + g_volume if _isfinite(gross_volume) and _isfinite(g_volume) else np.nan)
    volume_utilization = (required_volume_m3 / gross_volume if _isfinite(required_volume_m3) and _isfinite(gross_volume) and gross_volume > 0.0 else np.nan)

    # Try explicit energy channels first.  If unavailable, preserve a normalized
    # residual proxy only when the model already exposes a dimensionless energy
    # constraint.
    required_energy, required_energy_source = _get_first(
        prob, ["required_energy", "mission_energy_required", "mission_energy", "energy_required"], default=np.nan
    )
    available_energy, available_energy_source = _get_first(
        prob, ["available_energy", "energy_available", "usable_energy", "net_available_energy"], default=np.nan
    )
    if _isfinite(required_energy) and _isfinite(available_energy) and available_energy > 0.0:
        energy_utilization = required_energy / available_energy
    elif _isfinite(g_energy):
        # g_energy <= 0 is feasible.  Use 1+positive violation only as a
        # distance-to-boundary proxy; do not interpret it as an energy ratio.
        energy_utilization = 1.0 + max(float(g_energy), 0.0)
    else:
        energy_utilization = np.nan

    # Physics-comparable utilization excludes field performance, exactly as the
    # architecture Pareto rejection logic does. Battery architectures also omit
    # the algebraically closed battery-energy inequality from rejection.
    physics_utilizations = {
        "power": power_utilization,
        "buoyancy": buoyancy_utilization,
        "volume": volume_utilization,
    }
    if not has_battery:
        physics_utilizations["energy"] = energy_utilization
    operational_utilizations = dict(physics_utilizations)
    operational_utilizations["ground_roll"] = ground_roll_utilization

    finite_physics_util = {k: float(v) for k, v in physics_utilizations.items() if _isfinite(v)}
    finite_operational_util = {k: float(v) for k, v in operational_utilizations.items() if _isfinite(v)}

    nearest_constraint = max(finite_physics_util, key=finite_physics_util.get) if finite_physics_util else "unknown"
    nearest_constraint_value = finite_physics_util.get(nearest_constraint, np.nan)
    constraint_utilization = max(finite_physics_util.values()) if finite_physics_util else np.nan
    feasibility_distance = float(np.sqrt(sum(max(v - 1.0, 0.0) ** 2 for v in finite_physics_util.values()))) if finite_physics_util else np.nan
    feasibility_margin = (1.0 - constraint_utilization if _isfinite(constraint_utilization) else np.nan)

    nearest_operational_constraint = max(finite_operational_util, key=finite_operational_util.get) if finite_operational_util else "unknown"
    nearest_operational_constraint_value = finite_operational_util.get(nearest_operational_constraint, np.nan)
    operational_constraint_utilization = max(finite_operational_util.values()) if finite_operational_util else np.nan
    operational_feasibility_distance = float(np.sqrt(sum(max(v - 1.0, 0.0) ** 2 for v in finite_operational_util.values()))) if finite_operational_util else np.nan
    operational_margin_fraction = (1.0 - operational_constraint_utilization if _isfinite(operational_constraint_utilization) else np.nan)

    # Onboard energy and PFEI.
    onboard_energy_MJ = np.nan
    source_lhv_J_kg = np.nan

    if case.architecture == "conventional_reciprocating":
        # Fuel properties are owned by the current Power component and are
        # exposed as promoted OpenMDAO inputs. Do not import fuel-property
        # dictionaries from AirshipMission.
        source_lhv_J_kg = _get(
            prob,
            "gasoline_lhv",
            "J/kg",
            43.0e6,
        )
        onboard_energy_MJ = (
            consumable_mass * source_lhv_J_kg / 1.0e6
            if _isfinite(source_lhv_J_kg)
            else np.nan
        )

    elif case.architecture == "hydrogen_reciprocating":
        source_lhv_J_kg = _get(
            prob,
            "hydrogen_lhv",
            "J/kg",
            120.0e6,
        )
        onboard_energy_MJ = (
            consumable_mass * source_lhv_J_kg / 1.0e6
            if _isfinite(source_lhv_J_kg)
            else np.nan
        )

    elif case.architecture == "battery_only" and _isfinite(battery_capacity_kWh):
        # Match the validated architecture-comparison PFEI definition exactly:
        # battery onboard energy is the required/installed battery capacity.
        onboard_energy_MJ = battery_capacity_kWh * 3.6

    elif case.architecture == "solar_battery" and _isfinite(battery_capacity_kWh):
        # IMPORTANT: the validated AV-10 equivalent Pareto study defines ``onboard_total``
        # as battery energy + generated solar energy.  Counting battery capacity
        # alone makes the technology-assessment PFEI artificially low and breaks
        # direct comparability with the architecture study.
        solar_term_kWh = solar_generated_kWh if _isfinite(solar_generated_kWh) else 0.0
        onboard_energy_MJ = (battery_capacity_kWh + max(solar_term_kWh, 0.0)) * 3.6

    denominator = max(case.payload_kg, 1.0e-12) * max(case.range_km, 1.0e-12)
    pfei_onboard = (
        onboard_energy_MJ / denominator
        if _isfinite(onboard_energy_MJ)
        else np.nan
    )

    propulsive_energy_MJ = (
        required_power_W * mission_duration_s / 1.0e6
        if _isfinite(required_power_W) and _isfinite(mission_duration_s)
        else np.nan
    )
    pfei_propulsive = (
        propulsive_energy_MJ / denominator
        if _isfinite(propulsive_energy_MJ)
        else np.nan
    )

    # Direct operational emissions.
    if case.architecture == "conventional_reciprocating":
        co2_kg = consumable_mass * EI_CO2_PER_KG_CONVENTIONAL_FUEL
        nox_kg = consumable_mass * EI_NOX_PER_KG_CONVENTIONAL_FUEL
        h2o_kg = consumable_mass * EI_H2O_PER_KG_CONVENTIONAL_FUEL
        nox_note = "Static conventional-fuel reporting index."
    elif case.architecture == "hydrogen_reciprocating":
        co2_kg = 0.0
        nox_kg = np.nan
        h2o_kg = consumable_mass * EI_H2O_PER_KG_H2
        nox_note = (
            "Hydrogen-combustion NOx is not modeled; it must not be inferred "
            "from conventional fuel indices."
        )
    else:
        co2_kg = 0.0
        nox_kg = 0.0
        h2o_kg = 0.0
        nox_note = "Zero direct operational exhaust emissions."

    effective_tank_efficiency = (
        consumable_mass / (consumable_mass + tank_mass)
        if (
            case.architecture == "hydrogen_reciprocating"
            and consumable_mass > 0.0
            and _isfinite(tank_mass)
        )
        else np.nan
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "study_type": study_type,
        "architecture": case.architecture,
        "architecture_name": case.architecture_label,
        "parameter": parameter,
        "parameter_value": parameter_value,
        "feasible": feasible,
        "physics_feasible": physics_feasible,
        "operational_feasible": operational_feasible,
        "failure_reasons": ";".join(failure_reasons),
        "physics_failure_reasons": ";".join(physics_failure_reasons),
        "operational_failure_reasons": ";".join(operational_failure_reasons),
        "dominant_failure_category": dominant_failure_category,
        "operational_dominant_failure_category": operational_dominant_failure_category,
        "evaluation_status": evaluation_status,
        "numerical_failure": numerical_failure,
        "physical_failure_reasons": ";".join(physics_failure_reasons),
        "mtow_sanity_warning": mtow_sanity_warning,
        "driver_success": driver_success,
        "driver_message": driver_message,
        "solver_converged": solver_converged,
        "solver_iterations": solver_iterations,
        "solver_norm": solver_norm,
        "elapsed_s": elapsed_s,

        "baseline_mode": case.baseline_mode,
        "baseline_source_file": case.baseline_source_file,
        "baseline_source_mtow_kg": case.baseline_source_mtow_kg,
        "baseline_source_pfei": case.baseline_source_pfei,
        "baseline_source_selection": case.baseline_source_selection,
        "payload_kg": case.payload_kg,
        "range_km": case.range_km,
        "cruise_altitude_m": case.cruise_alt_m,
        "cruise_speed_mps": case.cruise_speed_ms,
        "length_m": _get(prob, "length", "m", case.length_m),
        "fineness_ratio": _get(prob, "fineness_ratio", default=case.fineness_ratio),

        "BR_takeoff": _get(prob, "BR_takeoff"),
        "BR_landing": _get(prob, "BR_landing"),
        "tail_volume_coeff_horizontal": _get(
            prob, "tail_volume_coeff_horizontal"
        ),
        "tail_volume_coeff_vertical": _get(
            prob, "tail_volume_coeff_vertical"
        ),
        "lift_coeff": _get(prob, "lift_coeff"),
        "drag_due_to_lift_factor": _get(prob, "drag_due_to_lift_factor"),
        "propeller_efficiency": _get(prob, "propeller_efficiency"),

        "mtow_kg": mtow,
        "owe_kg": owe,
        "operational_weight_kg": operational_weight,
        "gross_volume_m3": gross_volume,
        "mission_duration_hr": (
            mission_duration_s / 3600.0
            if _isfinite(mission_duration_s)
            else np.nan
        ),

        "installed_shaft_power_kW": installed_power_W / 1000.0,
        "required_power_kW": required_power_W / 1000.0,
        "ground_roll_distance_m": ground_roll,

        "g_power_W": g_power,
        "g_energy": g_energy,
        "g_buoyancy_N": g_buoyancy,
        "g_lift": g_lift,
        "g_groundroll_m": g_groundroll,
        "g_volume_m3": g_volume,
        "mass_balance_error_kg": mass_balance,
        "nearest_physics_constraint": nearest_constraint,
        "nearest_physics_constraint_normalized": nearest_constraint_value,
        "nearest_operational_constraint": nearest_operational_constraint,
        "nearest_operational_constraint_normalized": nearest_operational_constraint_value,
        "power_utilization": power_utilization,
        "energy_utilization": energy_utilization,
        "buoyancy_utilization": buoyancy_utilization,
        "ground_roll_utilization": ground_roll_utilization,
        "volume_utilization": volume_utilization,
        "required_volume_m3": required_volume_m3,
        "required_energy_audit": required_energy,
        "required_energy_source": required_energy_source,
        "available_energy_audit": available_energy,
        "available_energy_source": available_energy_source,
        "constraint_utilization": constraint_utilization,
        "constraint_margin_fraction": feasibility_margin,
        "feasibility_distance": feasibility_distance,
        "operational_constraint_utilization": operational_constraint_utilization,
        "operational_constraint_margin_fraction": operational_margin_fraction,
        "operational_feasibility_distance": operational_feasibility_distance,

        "consumable_mass_kg": consumable_mass,
        "consumable_mass_source": consumable_source,
        "battery_mass_kg": battery_mass,
        "battery_mass_source": battery_mass_source,
        "battery_capacity_kWh": battery_capacity_kWh,
        "battery_capacity_source": battery_capacity_source,
        "battery_volume_m3": battery_volume_m3,
        "tank_mass_kg": tank_mass,
        "tank_mass_source": tank_mass_source,
        "tank_volume_m3": tank_volume_m3,
        "tank_volume_source": tank_volume_source,
        "propulsion_mass_kg": propulsion_mass,
        "power_system_mass_kg": power_system_mass,
        "power_system_volume_m3": power_system_volume,

        "solar_energy_generated_kWh": solar_generated_kWh,
        "solar_energy_used_kWh": solar_used_kWh,
        "solar_fraction": solar_fraction,

        "battery_specific_energy_Wh_per_kg": _get(
            prob,
            "battery_specific_energy",
        ),
        "battery_volumetric_ed_Wh_per_L": _get(
            prob,
            "battery_volumetric_ed",
        ),
        "solar_efficiency": _get(prob, "solar_efficiency"),
        "solar_area_m2": _get(prob, "solar_area", "m**2"),
        "pv_areal_density_kg_m2": _get(
            prob,
            "pv_areal_density",
            "kg/m**2",
        ),
        "tank_gravimetric_efficiency_input": _get(
            prob,
            "tank_gravimetric_efficiency",
        ),
        "motor_specific_power_W_per_kg": _get(prob, "motor_specific_power", "W/kg"),
        "motor_efficiency": _get(prob, "motor_efficiency"),
        "inverter_efficiency": _get(prob, "inverter_efficiency"),
        "rated_shaft_power_kW": _get(prob, "rated_shaft_power", "kW"),
        "rated_brake_power_kW": _get(prob, "rated_brake_power", "kW"),
        "rated_shaft_power_per_unit_kW": _get(prob, "rated_shaft_power_per_unit", "kW"),
        "prime_mover_mass_kg": _get(prob, "prime_mover_mass", "kg"),
        "pv_mass_kg": _get(prob, "pv_mass", "kg"),
        "achieved_tank_gravimetric_efficiency": _get(prob, "achieved_tank_gravimetric_efficiency"),
        "effective_tank_gravimetric_efficiency": effective_tank_efficiency,

        "source_lhv_J_per_kg": source_lhv_J_kg,
        "battery_onboard_energy_MJ": (
            battery_capacity_kWh * 3.6 if _isfinite(battery_capacity_kWh) else np.nan
        ),
        "solar_generated_energy_MJ": (
            solar_generated_kWh * 3.6 if _isfinite(solar_generated_kWh) else np.nan
        ),
        "onboard_energy_MJ": onboard_energy_MJ,
        "pfei_energy_accounting": (
            "fuel_LHV" if case.architecture in {"conventional_reciprocating", "hydrogen_reciprocating"}
            else "battery_capacity" if case.architecture == "battery_only"
            else "battery_capacity_plus_solar_generated" if case.architecture == "solar_battery"
            else "unknown"
        ),
        "mission_propulsive_energy_MJ": propulsive_energy_MJ,
        "pfei_onboard_MJ_per_kg_km": pfei_onboard,
        "pfei_propulsive_MJ_per_kg_km": pfei_propulsive,

        "direct_co2_kg": co2_kg,
        "direct_nox_kg": nox_kg,
        "direct_h2o_kg": h2o_kg,
        "direct_nox_note": nox_note,

        "envelope_mass_kg": _get(prob, "envelop_mass", "kg"),
        "gondola_mass_kg": _get(prob, "gondola_mass", "kg"),
        "fin_mass_kg": _get(prob, "fin_mass", "kg"),
        "landing_system_mass_kg": _get(prob, "landing_system_mass", "kg"),
        "helium_mass_kg": _get(prob, "he_max_mass", "kg"),
        "miscellaneous_mass_kg": _get(prob, "miscellaneous_mass", "kg"),
    }


def evaluate_case(
    case: AssessmentCase,
    study_type: str,
    parameter: str = "",
    parameter_value: float = np.nan,
) -> Dict[str, Any]:
    prob: Optional[om.Problem] = None
    t0 = time.time()
    try:
        prob = build_problem(case, with_driver=False)
        power_closure_converged = True
        power_closure_error = 0.0
        if USE_INSTALLED_POWER_CLOSURE:
            power_closure_converged, power_closure_error = _run_power_closure(prob, case)
        else:
            prob.run_model()
        row = collect_results(
            prob,
            case,
            study_type,
            parameter,
            parameter_value,
            driver_success=None,
            elapsed_s=time.time() - t0,
        )
        row["power_closure_converged"] = power_closure_converged
        row["power_closure_relative_error"] = power_closure_error
        if USE_INSTALLED_POWER_CLOSURE and not power_closure_converged:
            row["feasible"] = False
            reasons = [r for r in str(row.get("failure_reasons", "")).split(";") if r]
            if "power_closure" not in reasons:
                reasons.append("power_closure")
            row["failure_reasons"] = ";".join(reasons)
            row["evaluation_status"] = "numerical_failure"
            row["numerical_failure"] = True
            row["dominant_failure_category"] = "solver/convergence"
        return row
    finally:
        _cleanup(prob)


def _case_from_result(
    case: AssessmentCase,
    row: Mapping[str, Any],
) -> AssessmentCase:
    return replace(
        case,
        br_takeoff=float(row["BR_takeoff"]),
        tvc_h=float(row["tail_volume_coeff_horizontal"]),
        tvc_v=float(row["tail_volume_coeff_vertical"]),
        lift_coeff=float(row["lift_coeff"]),
        drag_due_to_lift_factor=float(row["drag_due_to_lift_factor"]),
        # Propeller efficiency is a fixed technology input in roadmap
        # reoptimization and is not taken from the optimizer.
        propeller_efficiency=case.propeller_efficiency,
    )


def _midpoint_case(case: AssessmentCase) -> AssessmentCase:
    return replace(
        case,
        br_takeoff=float(np.mean(LOCAL_DESIGN_BOUNDS["BR_takeoff"])),
        tvc_h=float(np.mean(
            LOCAL_DESIGN_BOUNDS["tail_volume_coeff_horizontal"]
        )),
        tvc_v=float(np.mean(
            LOCAL_DESIGN_BOUNDS["tail_volume_coeff_vertical"]
        )),
        lift_coeff=float(np.mean(LOCAL_DESIGN_BOUNDS["lift_coeff"])),
        drag_due_to_lift_factor=float(np.mean(
            LOCAL_DESIGN_BOUNDS["drag_due_to_lift_factor"]
        )),
    )


def _low_mass_start(case: AssessmentCase) -> AssessmentCase:
    """Architecture-neutral start biased toward lower drag and tail mass."""
    return replace(
        case,
        br_takeoff=LOCAL_DESIGN_BOUNDS["BR_takeoff"][1],
        tvc_h=LOCAL_DESIGN_BOUNDS[
            "tail_volume_coeff_horizontal"
        ][0],
        tvc_v=LOCAL_DESIGN_BOUNDS[
            "tail_volume_coeff_vertical"
        ][0],
        lift_coeff=LOCAL_DESIGN_BOUNDS["lift_coeff"][0],
        drag_due_to_lift_factor=LOCAL_DESIGN_BOUNDS[
            "drag_due_to_lift_factor"
        ][0],
    )


def _balanced_start(case: AssessmentCase) -> AssessmentCase:
    return replace(
        case,
        br_takeoff=0.86,
        tvc_h=0.060,
        tvc_v=0.055,
        lift_coeff=0.15,
        drag_due_to_lift_factor=0.84,
    )


def _unique_start_cases(
    cases: Sequence[AssessmentCase],
) -> List[AssessmentCase]:
    unique: List[AssessmentCase] = []
    seen = set()
    for case in cases:
        key = (
            round(case.br_takeoff, 8),
            round(case.tvc_h, 8),
            round(case.tvc_v, 8),
            round(case.lift_coeff, 8),
            round(case.drag_due_to_lift_factor, 8),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return unique[:MAX_MULTISTART_CASES]


def _optimise_single_start(
    case: AssessmentCase,
    study_type: str,
    parameter: str,
    parameter_value: float,
    start_label: str,
) -> Tuple[AssessmentCase, Dict[str, Any]]:
    prob: Optional[om.Problem] = None
    t0 = time.time()
    try:
        prob = build_problem(case, with_driver=True)
        result, driver_text = _run_driver_captured(prob)
        success = _driver_success(result)
        row = collect_results(
            prob,
            case,
            study_type,
            parameter,
            parameter_value,
            driver_success=success,
            driver_message=driver_text.strip(),
            elapsed_s=time.time() - t0,
        )
        row["optimization_start"] = start_label
        row["optimizer_returned_success"] = success

        if not row["feasible"]:
            raise RuntimeError(
                "Optimizer point failed independent feasibility audit: "
                f"{row.get('failure_reasons', 'unknown')}; "
                f"driver_success={success}; "
                f"{driver_text[-400:]}"
            )

        optimized = _case_from_result(case, row)
        return optimized, row
    finally:
        _cleanup(prob)


def optimise_case(
    case: AssessmentCase,
    study_type: str,
    parameter: str = "",
    parameter_value: float = np.nan,
    extra_start_cases: Optional[Sequence[Tuple[str, AssessmentCase]]] = None,
) -> Tuple[AssessmentCase, Dict[str, Any]]:
    """Robust local reoptimization with multi-start and frozen fallback.

    The frozen design is always evaluated first and is a valid candidate.
    An optimizer result is accepted only if it is feasible and no heavier
    than the frozen point within a small numerical tolerance.
    """
    frozen_row = evaluate_case(
        case,
        f"{study_type}_frozen_candidate",
        parameter,
        parameter_value,
    )
    if not frozen_row.get("feasible", False):
        raise RuntimeError(
            "Frozen candidate is infeasible before optimization: "
            f"{frozen_row.get('failure_reasons', 'unknown')}"
        )

    frozen_row["optimization_start"] = "frozen_fallback"
    frozen_row["optimizer_returned_success"] = None
    frozen_row["selected_by_multistart"] = False
    frozen_row["optimization_improvement_kg"] = 0.0
    frozen_row["optimization_improvement_pct"] = 0.0
    frozen_row["optimization_candidate_count"] = 1

    labelled_starts: List[Tuple[str, AssessmentCase]] = [
        ("warm_or_reference", case),
        ("low_mass_bounds", _low_mass_start(case)),
        ("midpoint", _midpoint_case(case)),
        ("balanced", _balanced_start(case)),
    ]
    if extra_start_cases:
        labelled_starts.extend(extra_start_cases)

    unique_cases = _unique_start_cases([c for _, c in labelled_starts])
    label_by_key = {
        (
            round(c.br_takeoff, 8),
            round(c.tvc_h, 8),
            round(c.tvc_v, 8),
            round(c.lift_coeff, 8),
            round(c.drag_due_to_lift_factor, 8),
        ): label
        for label, c in labelled_starts
    }

    feasible_candidates: List[Tuple[AssessmentCase, Dict[str, Any]]] = []
    errors: List[str] = []

    for start_case in unique_cases:
        key = (
            round(start_case.br_takeoff, 8),
            round(start_case.tvc_h, 8),
            round(start_case.tvc_v, 8),
            round(start_case.lift_coeff, 8),
            round(start_case.drag_due_to_lift_factor, 8),
        )
        label = label_by_key.get(key, "multistart")
        try:
            optimized_case, row = _optimise_single_start(
                start_case,
                study_type,
                parameter,
                parameter_value,
                label,
            )
            feasible_candidates.append((optimized_case, row))
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")

    frozen_mtow = float(frozen_row["mtow_kg"])
    tolerance = max(
        OPTIMIZATION_MTOW_ABS_TOL_KG,
        OPTIMIZATION_MTOW_REL_TOL * abs(frozen_mtow),
    )

    acceptable = [
        (candidate_case, row)
        for candidate_case, row in feasible_candidates
        if float(row["mtow_kg"]) <= frozen_mtow + tolerance
    ]

    if acceptable:
        selected_case, selected_row = min(
            acceptable,
            key=lambda item: float(item[1]["mtow_kg"]),
        )
    else:
        selected_case = case
        selected_row = dict(frozen_row)
        selected_row["optimization_start"] = "frozen_fallback"
        selected_row["driver_message"] = (
            "No feasible optimizer candidate improved or matched the frozen "
            "design within tolerance. "
            + " | ".join(errors[-4:])
        )

    selected_mtow = float(selected_row["mtow_kg"])
    selected_row["selected_by_multistart"] = True
    selected_row["optimization_candidate_count"] = (
        1 + len(feasible_candidates)
    )
    selected_row["optimization_improvement_kg"] = (
        frozen_mtow - selected_mtow
    )
    selected_row["optimization_improvement_pct"] = (
        100.0 * (frozen_mtow - selected_mtow) / frozen_mtow
    )
    selected_row["frozen_candidate_mtow_kg"] = frozen_mtow
    selected_row["optimization_errors"] = " | ".join(errors)
    selected_row["optimization_fallback_used"] = (
        selected_row.get("optimization_start") == "frozen_fallback"
    )

    return selected_case, selected_row


# =============================================================================
# CASE AND SCENARIO APPLICATION
# =============================================================================

def apply_scenario(
    case: AssessmentCase,
    scenario: TechnologyScenario,
) -> AssessmentCase:
    return replace(
        case,
        battery_specific_energy=scenario.battery_specific_energy_Wh_kg,
        battery_volumetric_ed=scenario.battery_volumetric_ed_Wh_L,
        solar_efficiency=scenario.solar_efficiency,
        solar_area_m2=scenario.solar_area_m2,
        pv_areal_density=scenario.pv_areal_density_kg_m2,
        solar_irradiance_W_m2=scenario.solar_irradiance_W_m2,
        tank_gravimetric_efficiency=scenario.tank_gravimetric_efficiency,
        motor_specific_power=scenario.motor_specific_power_W_kg,
        motor_efficiency=scenario.motor_efficiency,
        inverter_efficiency=scenario.inverter_efficiency,
    )


def case_parameter_value(case: AssessmentCase, parameter: str) -> float:
    if not hasattr(case, parameter):
        raise AttributeError(f"AssessmentCase has no parameter {parameter!r}.")
    return float(getattr(case, parameter))


def architecture_available_in_scenario(
    architecture: str,
    scenario: TechnologyScenario,
) -> bool:
    """All four validated AV-10 equivalent architectures are assessed at every roadmap point."""
    return architecture in ARCH_CONFIGS


def unavailable_roadmap_row(
    architecture: str,
    scenario: TechnologyScenario,
    study_type: str,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "study_type": study_type,
        "architecture": architecture,
        "architecture_name": ARCH_CONFIGS[architecture]["label"],
        "parameter": "year",
        "parameter_value": float(scenario.year),
        "year": scenario.year,
        "horizon": scenario.horizon,
        "feasible": False,
        "architecture_available": False,
        "failure_reasons": "not_in_paper_aligned_horizon",
        "roadmap_status": "not assessed in this technology horizon",
        "error": "",
    }


def add_scenario_metadata(
    row: Dict[str, Any],
    scenario: TechnologyScenario,
) -> Dict[str, Any]:
    row.update({
        "year": scenario.year,
        "horizon": scenario.horizon,
        "scenario_battery_specific_energy_Wh_kg": (
            scenario.battery_specific_energy_Wh_kg
        ),
        "scenario_battery_volumetric_ed_Wh_L": (
            scenario.battery_volumetric_ed_Wh_L
        ),
        "scenario_solar_efficiency": scenario.solar_efficiency,
        "scenario_solar_area_m2": scenario.solar_area_m2,
        "scenario_pv_areal_density_kg_m2": (
            scenario.pv_areal_density_kg_m2
        ),
        "scenario_tank_gravimetric_efficiency": (
            scenario.tank_gravimetric_efficiency
        ),
        "scenario_motor_specific_power_W_kg": (
            scenario.motor_specific_power_W_kg
        ),
        "scenario_motor_efficiency": scenario.motor_efficiency,
        "scenario_inverter_efficiency": scenario.inverter_efficiency,
        "electric_machine_technology": scenario.electric_machine_technology,
        "power_electronics_technology": (
            scenario.power_electronics_technology
        ),
        "battery_technology": scenario.battery_technology,
        "tank_technology": scenario.tank_technology,
        "scenario_source_note": scenario.source_note,
        "architecture_available": row.get("architecture_available", True),
    })
    return row


# =============================================================================
# BASELINE ASSESSMENT
# =============================================================================

def run_common_baseline(
    cases: Mapping[str, AssessmentCase],
) -> pd.DataFrame:
    rows = []
    for architecture in ARCHITECTURE_ORDER:
        if architecture not in cases:
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "study_type": "common_mission_baseline",
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "feasible": False,
                "physics_feasible": False,
                "operational_feasible": False,
                "evaluation_status": "baseline_unavailable",
                "failure_reasons": "no_feasible_pareto_baseline",
                "error": "Architecture-specific assessment skipped because the architecture study supplied no feasible common-mission baseline.",
            })
            continue
        case = cases[architecture]
        try:
            row = evaluate_case(case, "common_mission_baseline")
            row["error"] = ""
        except Exception as exc:
            row = {
                "schema_version": SCHEMA_VERSION,
                "study_type": "common_mission_baseline",
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "feasible": False,
                "physics_feasible": False,
                "operational_feasible": False,
                "failure_reasons": "execution_exception",
                "error": f"{type(exc).__name__}: {exc}",
            }
        rows.append(row)
    return pd.DataFrame(rows)


# =============================================================================
# FIXED-DESIGN ONE-AT-A-TIME SWEEPS
# =============================================================================

def default_sweeps() -> List[Tuple[str, str, np.ndarray, str]]:
    """AV-10 equivalent technology sweeps centered on the validated current assumptions."""
    return [
        ("battery_only", "battery_specific_energy", np.arange(250.0, 1201.0, 50.0), "Battery pack specific energy [Wh/kg]"),
        ("battery_only", "battery_volumetric_ed", np.arange(500.0, 1401.0, 100.0), "Battery volumetric energy density [Wh/L]"),
        ("solar_battery", "solar_efficiency", np.arange(0.20, 0.421, 0.02), "Solar conversion efficiency [-]"),
        ("solar_battery", "pv_areal_density", np.arange(0.50, 3.01, 0.25), "PV areal density [kg/m²]"),
        ("hydrogen_reciprocating", "tank_gravimetric_efficiency", np.arange(0.05, 0.251, 0.0125), "Tank gravimetric efficiency [-]"),
        ("conventional_reciprocating", "propeller_efficiency", np.arange(0.68, 0.861, 0.01), "Propeller efficiency [-]"),
    ]


def run_fixed_sweep(
    base_case: AssessmentCase,
    parameter: str,
    values: Iterable[float],
) -> pd.DataFrame:
    baseline_value = case_parameter_value(base_case, parameter)
    grid = _ensure_baseline(values, baseline_value)

    baseline = evaluate_case(
        base_case,
        "fixed_design_baseline",
        parameter,
        baseline_value,
    )
    # The AV-10 equivalent battery-electric current-technology baseline may be physically
    # infeasible. That is a result, not an execution error: continue the sweep
    # so the technology threshold at which feasibility first appears is captured.

    rows: List[Dict[str, Any]] = []
    for value in grid:
        varied = replace(base_case, **{parameter: float(value)})
        try:
            row = evaluate_case(
                varied,
                "fixed_design_sensitivity",
                parameter,
                float(value),
            )
            row["error"] = ""
        except Exception as exc:
            row = {
                "schema_version": SCHEMA_VERSION,
                "study_type": "fixed_design_sensitivity",
                "architecture": base_case.architecture,
                "architecture_name": base_case.architecture_label,
                "parameter": parameter,
                "parameter_value": float(value),
                "feasible": False,
                "mtow_kg": np.nan,
                "pfei_onboard_MJ_per_kg_km": np.nan,
                "power_system_mass_kg": np.nan,
                "ground_roll_distance_m": np.nan,
                "error": f"{type(exc).__name__}: {exc}",
            }

        row.update({
            "baseline_parameter_value": baseline_value,
            "baseline_mtow_kg": baseline["mtow_kg"],
            "baseline_pfei": baseline["pfei_onboard_MJ_per_kg_km"],
            "baseline_power_system_mass_kg": baseline["power_system_mass_kg"],
        })
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("parameter_value").reset_index(drop=True)
    df = _adaptive_refine_fixed_sweep(base_case, parameter, df)

    # Re-attach baseline metadata to adaptively inserted points.
    df["baseline_parameter_value"] = baseline_value
    df["baseline_mtow_kg"] = baseline.get("mtow_kg", np.nan)
    df["baseline_pfei"] = baseline.get("pfei_onboard_MJ_per_kg_km", np.nan)
    df["baseline_power_system_mass_kg"] = baseline.get("power_system_mass_kg", np.nan)

    df["technology_change_pct"] = (
        100.0
        * (df["parameter_value"] - baseline_value)
        / baseline_value
    )
    base_mtow = float(baseline.get("mtow_kg", np.nan))
    df["delta_mtow_pct"] = (
        100.0 * (df["mtow_kg"] - base_mtow) / base_mtow
        if _isfinite(base_mtow) and abs(base_mtow) > 1.0e-12 else np.nan
    )
    base_pfei = float(baseline.get("pfei_onboard_MJ_per_kg_km", np.nan))
    df["delta_pfei_pct"] = (
        100.0 * (df["pfei_onboard_MJ_per_kg_km"] - base_pfei) / base_pfei
        if _isfinite(base_pfei) and abs(base_pfei) > 1.0e-12 else np.nan
    )
    df["delta_power_system_mass_pct"] = (
        100.0
        * (
            df["power_system_mass_kg"]
            - baseline["power_system_mass_kg"]
        )
        / max(abs(baseline["power_system_mass_kg"]), 1.0e-12)
    )

    df["elasticity_mtow"] = _compute_local_elasticity(df, "parameter_value", "mtow_kg")
    df["elasticity_pfei"] = _compute_local_elasticity(df, "parameter_value", "pfei_onboard_MJ_per_kg_km")

    # Explicit threshold reporting.
    feas = df[df["feasible"].map(_as_bool)]
    df["first_feasible_parameter_value"] = (float(feas["parameter_value"].min()) if not feas.empty else np.nan)
    df["last_feasible_parameter_value"] = (float(feas["parameter_value"].max()) if not feas.empty else np.nan)

    return df


def _adaptive_refine_fixed_sweep(
    base_case: AssessmentCase,
    parameter: str,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Refine feasibility transitions and large response jumps automatically.

    This is deliberately one-dimensional and conservative: it adds midpoint
    evaluations only where adjacent samples change feasibility status or where
    a finite MTOW jump exceeds ADAPTIVE_SWEEP_JUMP_FRACTION.
    """
    current = df.copy().sort_values("parameter_value").reset_index(drop=True)
    evaluated = set(np.round(current["parameter_value"].astype(float), 12))
    for _round in range(ADAPTIVE_SWEEP_MAX_ROUNDS):
        proposed: List[float] = []
        vals = current["parameter_value"].to_numpy(float)
        for i in range(len(current) - 1):
            a = current.iloc[i]
            b = current.iloc[i + 1]
            xa, xb = float(vals[i]), float(vals[i + 1])
            rel_spacing = abs(xb - xa) / max(abs(xa), abs(xb), 1.0)
            if rel_spacing <= ADAPTIVE_SWEEP_MIN_REL_SPACING:
                continue
            fa, fb = _as_bool(a.get("feasible", False)), _as_bool(b.get("feasible", False))
            status_change = fa != fb or str(a.get("evaluation_status", "")) != str(b.get("evaluation_status", ""))
            ya, yb = _scalar(a.get("mtow_kg", np.nan)), _scalar(b.get("mtow_kg", np.nan))
            jump = False
            if _isfinite(ya) and _isfinite(yb):
                jump = abs(yb - ya) / max(min(abs(ya), abs(yb)), 1.0) >= ADAPTIVE_SWEEP_JUMP_FRACTION
            if status_change or jump:
                xm = 0.5 * (xa + xb)
                key = round(xm, 12)
                if key not in evaluated:
                    proposed.append(xm)
        if not proposed:
            break
        proposed = proposed[:ADAPTIVE_SWEEP_MAX_NEW_POINTS_PER_ROUND]
        new_rows = []
        for value in proposed:
            varied = replace(base_case, **{parameter: float(value)})
            try:
                row = evaluate_case(varied, "fixed_design_sensitivity_adaptive", parameter, float(value))
                row["error"] = ""
            except Exception as exc:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "study_type": "fixed_design_sensitivity_adaptive",
                    "architecture": base_case.architecture,
                    "architecture_name": base_case.architecture_label,
                    "parameter": parameter,
                    "parameter_value": float(value),
                    "feasible": False,
                    "evaluation_status": "execution_exception",
                    "mtow_kg": np.nan,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            new_rows.append(row)
            evaluated.add(round(float(value), 12))
        current = pd.concat([current, pd.DataFrame(new_rows)], ignore_index=True).sort_values("parameter_value").reset_index(drop=True)
    return current


def _compute_local_elasticity(df: pd.DataFrame, xcol: str, ycol: str) -> pd.Series:
    """Dimensionless local elasticity computed only on smooth valid branches."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    x = pd.to_numeric(df[xcol], errors="coerce").to_numpy(float)
    y = pd.to_numeric(df[ycol], errors="coerce").to_numpy(float)
    status = df.get("evaluation_status", pd.Series([""] * len(df))).astype(str).to_numpy()
    order = np.argsort(x)
    for k in range(1, len(order) - 1):
        i0, i, i1 = order[k - 1], order[k], order[k + 1]
        if not all(np.isfinite([x[i0], x[i], x[i1], y[i0], y[i], y[i1]])):
            continue
        if min(x[i0], x[i], x[i1], y[i0], y[i], y[i1]) <= 0.0:
            continue
        # Do not differentiate across solver/physics branch changes or abrupt
        # discontinuities; those are reported as thresholds instead.
        if not (status[i0] == status[i] == status[i1]):
            continue
        local_jump = max(abs(y[i] - y[i0]), abs(y[i1] - y[i])) / max(abs(y[i]), 1.0)
        if local_jump > ADAPTIVE_SWEEP_JUMP_FRACTION:
            continue
        dlny = np.log(y[i1]) - np.log(y[i0])
        dlnx = np.log(x[i1]) - np.log(x[i0])
        if abs(dlnx) > 1.0e-14:
            out.iloc[i] = dlny / dlnx
    return out


# =============================================================================
# COUPLED TECHNOLOGY MAPS
# =============================================================================

def run_two_parameter_grid(
    base_case: AssessmentCase,
    xname: str,
    xvalues: Iterable[float],
    yname: str,
    yvalues: Iterable[float],
    study_type: str,
) -> pd.DataFrame:
    x0 = case_parameter_value(base_case, xname)
    y0 = case_parameter_value(base_case, yname)
    xgrid = _ensure_baseline(xvalues, x0)
    ygrid = _ensure_baseline(yvalues, y0)

    baseline = evaluate_case(
        base_case,
        f"{study_type}_baseline",
        f"{xname}__{yname}",
        np.nan,
    )
    # Do not abort on an infeasible current-tech baseline. The purpose of this
    # map is precisely to identify the feasibility boundary in technology space.

    rows: List[Dict[str, Any]] = []
    for xv in xgrid:
        for yv in ygrid:
            varied = replace(
                base_case,
                **{
                    xname: float(xv),
                    yname: float(yv),
                },
            )
            try:
                row = evaluate_case(
                    varied,
                    study_type,
                    f"{xname}__{yname}",
                    float(xv),
                )
                row["error"] = ""
            except Exception as exc:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "study_type": study_type,
                    "architecture": base_case.architecture,
                    "architecture_name": base_case.architecture_label,
                    "feasible": False,
                    "mtow_kg": np.nan,
                    "pfei_onboard_MJ_per_kg_km": np.nan,
                    "error": f"{type(exc).__name__}: {exc}",
                }

            row[f"{xname}_input"] = float(xv)
            row[f"{yname}_input"] = float(yv)
            rows.append(row)

    df = pd.DataFrame(rows)
    base_mtow = float(baseline.get("mtow_kg", np.nan))
    base_pfei = float(baseline.get("pfei_onboard_MJ_per_kg_km", np.nan))
    df["delta_mtow_pct"] = (100.0 * (df["mtow_kg"] - base_mtow) / base_mtow
                            if _isfinite(base_mtow) and abs(base_mtow) > 1.0e-12 else np.nan)
    df["delta_pfei_pct"] = (100.0 * (df["pfei_onboard_MJ_per_kg_km"] - base_pfei) / base_pfei
                            if _isfinite(base_pfei) and abs(base_pfei) > 1.0e-12 else np.nan)
    return df


# =============================================================================
# ROADMAPS
# =============================================================================

def run_frozen_roadmap(
    cases: Mapping[str, AssessmentCase],
    scenarios: Sequence[TechnologyScenario],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for architecture in ARCHITECTURE_ORDER:
        if architecture not in cases:
            for scenario in sorted(scenarios, key=lambda s: s.year):
                rows.append(add_scenario_metadata(
                    unavailable_roadmap_row(architecture, scenario, "frozen_design_roadmap"),
                    scenario,
                ))
            continue
        base = cases[architecture]
        for scenario in sorted(scenarios, key=lambda s: s.year):
            if not architecture_available_in_scenario(architecture, scenario):
                rows.append(
                    add_scenario_metadata(
                        unavailable_roadmap_row(
                            architecture,
                            scenario,
                            "frozen_design_roadmap",
                        ),
                        scenario,
                    )
                )
                continue

            scenario_case = apply_scenario(base, scenario)
            try:
                row = evaluate_case(
                    scenario_case,
                    "frozen_design_roadmap",
                    "year",
                    float(scenario.year),
                )
                row["error"] = ""
                row["roadmap_status"] = "evaluated"
            except Exception as exc:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "study_type": "frozen_design_roadmap",
                    "architecture": architecture,
                    "architecture_name": base.architecture_label,
                    "parameter": "year",
                    "parameter_value": float(scenario.year),
                    "feasible": False,
                    "architecture_available": True,
                    "roadmap_status": "execution exception",
                    "error": f"{type(exc).__name__}: {exc}",
                }

            rows.append(add_scenario_metadata(row, scenario))

    return pd.DataFrame(rows)


def run_reoptimised_roadmap(
    cases: Mapping[str, AssessmentCase],
    scenarios: Sequence[TechnologyScenario],
) -> pd.DataFrame:
    """Controlled multi-start roadmap with same-year cross-architecture starts."""

    rows: List[Dict[str, Any]] = []
    best_case_by_architecture: Dict[str, AssessmentCase] = dict(cases)
    best_case_by_year: Dict[Tuple[int, str], AssessmentCase] = {}

    # Architecture order is deliberate: battery is optimized before solar so
    # its same-year aerodynamic solution can seed the solar-battery search.
    roadmap_order = [
        "conventional_reciprocating",
        "hydrogen_reciprocating",
        "battery_only",
        "solar_battery",
    ]

    for architecture in roadmap_order:
        if architecture not in best_case_by_architecture:
            for scenario in sorted(scenarios, key=lambda s: s.year):
                rows.append(add_scenario_metadata(
                    unavailable_roadmap_row(architecture, scenario, "reoptimised_roadmap"),
                    scenario,
                ))
            continue
        warm = best_case_by_architecture[architecture]

        for scenario in sorted(scenarios, key=lambda s: s.year):
            if not architecture_available_in_scenario(architecture, scenario):
                rows.append(
                    add_scenario_metadata(
                        unavailable_roadmap_row(
                            architecture,
                            scenario,
                            "reoptimised_roadmap",
                        ),
                        scenario,
                    )
                )
                continue

            scenario_case = apply_scenario(warm, scenario)
            extra_starts: List[Tuple[str, AssessmentCase]] = []

            # Solar-battery inherits a same-year battery-electric aerodynamic
            # seed. This addresses the previous 2030 solar local optimum.
            if architecture == "solar_battery":
                battery_seed = best_case_by_year.get(
                    (scenario.year, "battery_only")
                )
                if battery_seed is not None:
                    extra_starts.append((
                        "same_year_battery_seed",
                        replace(
                            scenario_case,
                            br_takeoff=battery_seed.br_takeoff,
                            tvc_h=battery_seed.tvc_h,
                            tvc_v=battery_seed.tvc_v,
                            lift_coeff=battery_seed.lift_coeff,
                            drag_due_to_lift_factor=(
                                battery_seed.drag_due_to_lift_factor
                            ),
                        ),
                    ))

            try:
                optimized_case, row = optimise_case(
                    scenario_case,
                    "reoptimised_roadmap",
                    "year",
                    float(scenario.year),
                    extra_start_cases=extra_starts,
                )
                warm = optimized_case
                best_case_by_architecture[architecture] = optimized_case
                best_case_by_year[(scenario.year, architecture)] = optimized_case
                row["error"] = ""
                row["roadmap_status"] = "evaluated"
            except Exception as exc:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "study_type": "reoptimised_roadmap",
                    "architecture": architecture,
                    "architecture_name": warm.architecture_label,
                    "parameter": "year",
                    "parameter_value": float(scenario.year),
                    "year": scenario.year,
                    "feasible": False,
                    "driver_success": False,
                    "architecture_available": True,
                    "failure_reasons": "optimisation_exception",
                    "roadmap_status": "optimization exception",
                    "error": f"{type(exc).__name__}: {exc}",
                }

            rows.append(add_scenario_metadata(row, scenario))

    return pd.DataFrame(rows)


# =============================================================================
# PLOTS
# =============================================================================

def _save(
    fig: plt.Figure,
    path: Path,
    rect: Optional[Tuple[float, ...]] = None,
) -> None:
    if rect:
        fig.tight_layout(rect=rect)
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)


def _style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)


def plot_baseline_architectures(df: pd.DataFrame, path: Path) -> None:
    order = [a for a in ARCHITECTURE_ORDER if a in set(df.get("architecture", []))]
    if not order:
        return
    labels = [ARCH_CONFIGS[a]["label"] for a in order]
    colors = [ARCH_CONFIGS[a]["color"] for a in order]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    metrics = [("mtow_kg", "MTOW [kg]"),
               ("pfei_onboard_MJ_per_kg_km", "Onboard PFEI [MJ/(kg·km)]"),
               ("ground_roll_distance_m", "Ground-roll distance [m]")]
    for ax, (column, ylabel) in zip(axes, metrics):
        values=[]
        for a in order:
            row=df.loc[df["architecture"]==a]
            values.append(float(row[column].iloc[0]) if (not row.empty and column in row and _isfinite(row[column].iloc[0])) else np.nan)
        bars=ax.bar(labels, np.nan_to_num(values, nan=0.0), color=colors)
        for bar,a,v in zip(bars,order,values):
            row=df.loc[df["architecture"]==a].iloc[0]
            ok=_as_bool(row.get("physics_feasible", row.get("feasible",False)))
            op_ok=_as_bool(row.get("operational_feasible",False))
            status = "physics OK / field OK" if (ok and op_ok) else ("physics OK / field fail" if ok else "PHYSICS INFEASIBLE")
            text=(f"{v:.3g}" if _isfinite(v) else "n/a") + "\n" + status
            ax.annotate(text,(bar.get_x()+bar.get_width()/2,bar.get_height()),xytext=(0,4),textcoords="offset points",ha="center",va="bottom",fontsize=8)
            if not ok:
                bar.set_alpha(0.35)
                bar.set_hatch("//")
        ax.set_ylabel(ylabel); ax.tick_params(axis="x",rotation=25); _style_axes(ax)
    modes = [str(x) for x in df.get("baseline_mode", pd.Series(dtype=str)).dropna().unique()]
    mode = modes[0] if len(modes) == 1 else "mixed/unavailable"
    fig.suptitle(
        "AV-10 equivalent common-mission technology baseline\n"
        f"payload={COMMON_PAYLOAD_KG:.0f} kg, range={COMMON_RANGE_KM:.0f} km | baseline={mode}"
    )
    _save(fig,path,(0,0,1,0.88))


def plot_sweep(
    df: pd.DataFrame,
    xlabel: str,
    path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.4))
    panels = [
        ("mtow_kg", "MTOW [kg]"),
        ("power_system_mass_kg", "Power-system mass [kg]"),
        ("pfei_onboard_MJ_per_kg_km", "Onboard PFEI [MJ/(kg·km)]"),
        ("ground_roll_distance_m", "Ground-roll distance [m]"),
        ("constraint_utilization", "Physics-constraint utilization [-]"),
        ("feasibility_distance", "Physics distance to feasibility [-]"),
    ]

    status_styles = {
        "physics_feasible": dict(marker="o", label="Physics feasible"),
        "physics_infeasible": dict(marker="o", label="Physics infeasible"),
        "numerical_failure": dict(marker="x", label="Numerical failure"),
        "execution_exception": dict(marker="x", label="Execution exception"),
    }

    for ax, (column, ylabel) in zip(axes.ravel(), panels):
        if column not in df.columns:
            ax.set_visible(False)
            continue
        finite = df[np.isfinite(pd.to_numeric(df[column], errors="coerce"))].copy()
        finite = finite.sort_values("parameter_value")
        if finite.empty:
            ax.text(0.5, 0.5, "No finite response", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); _style_axes(ax)
            continue

        # Show the complete converged response as a thin neutral line so that
        # infeasible physics trends are not discarded.
        ax.plot(finite["parameter_value"], finite[column], "-", linewidth=1.0, alpha=0.45)
        statuses = finite.get("evaluation_status", pd.Series(["physics_infeasible"] * len(finite), index=finite.index)).astype(str)
        for status in status_styles:
            sub = finite[statuses == status]
            if sub.empty:
                continue
            marker = status_styles[status]["marker"]
            if status == "physics_feasible":
                ax.scatter(sub["parameter_value"], sub[column], marker=marker, s=36, label=status_styles[status]["label"])
            elif status == "physics_infeasible":
                ax.scatter(sub["parameter_value"], sub[column], marker=marker, s=36, facecolors="none", label=status_styles[status]["label"])
            else:
                ax.scatter(sub["parameter_value"], sub[column], marker=marker, s=42, label=status_styles[status]["label"])

        baseline = float(df["baseline_parameter_value"].iloc[0])
        base_row = finite[np.isclose(finite["parameter_value"], baseline)]
        if len(base_row) >= 1:
            ax.scatter([baseline], [base_row.iloc[0][column]], marker="*", s=180, edgecolors="k", zorder=10, label="Baseline")

        if column == "constraint_utilization":
            ax.axhline(1.0, linestyle="--", linewidth=1.2, label="Active limit")
        if column == "feasibility_distance":
            ax.axhline(0.0, linestyle="--", linewidth=1.0)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        _style_axes(ax)

    # Deduplicate legend entries across panels.
    handles, labels = [], []
    for ax in axes.ravel():
        if not ax.get_visible():
            continue
        h, l = ax.get_legend_handles_labels()
        for hh, ll in zip(h, l):
            if ll not in labels:
                handles.append(hh); labels.append(ll)
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=min(5, len(labels)), frameon=False)

    arch = df["architecture_name"].iloc[0]
    parameter = df["parameter"].iloc[0]
    feasible = df[df["feasible"].map(_as_bool)]
    threshold_text = ""
    if not feasible.empty:
        threshold_text = f" | feasible sampled range {feasible['parameter_value'].min():.4g}–{feasible['parameter_value'].max():.4g}"
    fig.suptitle(f"Technology sensitivity — {arch}\n{parameter}{threshold_text}", y=0.995)
    _save(fig, path, (0, 0, 1, 0.91))


def plot_normalised(
    sweeps: Sequence[pd.DataFrame],
    path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))

    for df in sweeps:
        status = df.get("evaluation_status", pd.Series([""] * len(df), index=df.index)).astype(str)
        good = df[(status != "numerical_failure") & np.isfinite(df["technology_change_pct"])].copy()
        if good.empty:
            continue
        label = f"{df['architecture_name'].iloc[0]}: {df['parameter'].iloc[0]}"
        finite_delta = good[np.isfinite(good["delta_mtow_pct"])]
        if not finite_delta.empty:
            axes[0].plot(finite_delta["technology_change_pct"], finite_delta["delta_mtow_pct"], "o-", label=label)
        finite_e = good[np.isfinite(good["elasticity_mtow"])]
        if not finite_e.empty:
            axes[1].plot(finite_e["technology_change_pct"], finite_e["elasticity_mtow"], "o-", label=label)

    for ax in axes:
        ax.axhline(0.0, linewidth=1.0)
        ax.axvline(0.0, linewidth=1.0, linestyle=":")
        ax.set_xlabel("Technology-parameter change from baseline [%]")
        _style_axes(ax)
    axes[0].set_ylabel("MTOW change from baseline [%]")
    axes[1].set_ylabel("Local dimensionless MTOW elasticity")
    handles, labels = axes[0].get_legend_handles_labels()
    if not handles:
        handles, labels = axes[1].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.98), ncol=2, frameon=False)
    fig.suptitle("Normalized technology sensitivity\nElasticity is evaluated only on locally smooth numerical branches", y=1.02)
    _save(fig, path, (0, 0, 1, 0.84))


def _grid_arrays(
    df: pd.DataFrame,
    xcol: str,
    ycol: str,
    zcol: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    xs = np.sort(df[xcol].dropna().unique().astype(float))
    ys = np.sort(df[ycol].dropna().unique().astype(float))
    xx, yy = np.meshgrid(xs, ys)
    zz = np.full_like(xx, np.nan, dtype=float)

    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            row = df[
                np.isclose(df[xcol], x)
                & np.isclose(df[ycol], y)
            ]
            if row.empty:
                continue
            value = row.iloc[0].get(zcol, np.nan)
            if zcol == "feasible":
                value = float(_as_bool(value))
            zz[i, j] = _scalar(value)

    return xx, yy, zz


def plot_grid(
    df: pd.DataFrame,
    xcol: str,
    ycol: str,
    xlabel: str,
    ylabel: str,
    title: str,
    path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(16.5, 9.0))
    panels = [
        ("mtow_kg", "MTOW [kg]"),
        ("pfei_onboard_MJ_per_kg_km", "Onboard PFEI [MJ/(kg·km)]"),
        ("constraint_utilization", "Physics-constraint utilization"),
        ("feasibility_distance", "Physics distance to feasibility"),
        ("operational_constraint_utilization", "Operational utilization incl. ground roll"),
        ("operational_feasibility_distance", "Operational distance incl. ground roll"),
    ]

    for ax, (zcol, panel_title) in zip(axes.ravel(), panels):
        xx, yy, zz = _grid_arrays(df, xcol, ycol, zcol)
        # Mask actual execution/numerical failures. Physical infeasible values are
        # retained so the response surface remains scientifically interpretable.
        mesh = ax.pcolormesh(xx, yy, zz, shading="auto")
        cbar = fig.colorbar(mesh, ax=ax)
        if zcol in {"constraint_utilization", "operational_constraint_utilization"}:
            cbar.set_label("1.0 = active limit")
            finite = zz[np.isfinite(zz)]
            if finite.size and np.nanmin(finite) <= 1.0 <= np.nanmax(finite):
                ax.contour(xx, yy, zz, levels=[1.0], linewidths=1.6)
        elif zcol in {"feasibility_distance", "operational_feasibility_distance"}:
            cbar.set_label("0 = feasible")
            finite = zz[np.isfinite(zz)]
            if finite.size and np.nanmin(finite) <= 0.0 <= np.nanmax(finite):
                ax.contour(xx, yy, zz, levels=[0.0], linewidths=1.4)

        # Overlay true feasible samples and numerical failures.
        if "evaluation_status" in df.columns:
            feas = df[df["evaluation_status"].astype(str) == "physics_feasible"]
            fail = df[df["evaluation_status"].astype(str).isin(["numerical_failure", "execution_exception"])]
            if not feas.empty:
                ax.scatter(feas[xcol], feas[ycol], s=13, facecolors="none", edgecolors="k", linewidths=0.45)
            if not fail.empty:
                ax.scatter(fail[xcol], fail[ycol], s=18, marker="x")

        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(panel_title); _style_axes(ax)

    fig.suptitle(title + "\nOpen circles = physics-feasible samples; × = numerical failure", y=1.02)
    _save(fig, path, (0, 0, 1, 0.90))


def plot_roadmap(
    df: pd.DataFrame,
    title: str,
    path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(16.0, 9.0))
    metrics = [
        ("mtow_kg", "MTOW [kg]"),
        ("pfei_onboard_MJ_per_kg_km", "Onboard PFEI [MJ/(kg·km)]"),
        ("ground_roll_distance_m", "Ground-roll distance [m]"),
        ("constraint_utilization", "Physics-constraint utilization [-]"),
        ("feasibility_distance", "Physics distance to feasibility [-]"),
        ("operational_feasibility_distance", "Operational distance incl. ground roll [-]"),
    ]
    for architecture in ARCHITECTURE_ORDER:
        group = df[df["architecture"] == architecture].sort_values("year")
        if group.empty:
            continue
        label = ARCH_CONFIGS[architecture]["label"]
        for ax, (column, ylabel) in zip(axes.ravel(), metrics):
            if column not in group.columns:
                continue
            finite = group[np.isfinite(pd.to_numeric(group[column], errors="coerce"))]
            if finite.empty:
                continue
            ax.plot(finite["year"], finite[column], "--", linewidth=1.1, alpha=0.65)
            feas = finite[finite["feasible"].map(_as_bool)]
            infeas = finite[~finite["feasible"].map(_as_bool)]
            if not feas.empty:
                ax.scatter(feas["year"], feas[column], s=48, label=label)
            if not infeas.empty:
                ax.scatter(infeas["year"], infeas[column], s=48, facecolors="none", label=label + " (infeasible)")
            for _, row in finite.iterrows():
                ax.annotate(str(int(row["year"])), (row["year"], row[column]), xytext=(4, 4), textcoords="offset points", fontsize=7)
            ax.set_xlabel("Technology scenario year"); ax.set_ylabel(ylabel); _style_axes(ax)
    axes[0,2].axhline(FIELD_LENGTH_LIMIT_M, linestyle="--", linewidth=1.0)
    axes[1,0].axhline(1.0, linestyle="--", linewidth=1.0)
    axes[1,1].axhline(0.0, linestyle="--", linewidth=1.0)
    axes[1,2].axhline(0.0, linestyle="--", linewidth=1.0)
    handles, labels = [], []
    for ax in axes.ravel():
        h,l=ax.get_legend_handles_labels()
        for hh,ll in zip(h,l):
            if ll not in labels: handles.append(hh); labels.append(ll)
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5,0.965), ncol=4, frameon=False)
    fig.suptitle(title + "\nOpen markers retain converged but physics-infeasible technology points", y=0.995)
    _save(fig, path, (0,0,1,0.91))


def plot_trajectory(
    df: pd.DataFrame,
    title: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 6.8))
    any_points = False
    for architecture in ARCHITECTURE_ORDER:
        group = df[(df["architecture"] == architecture) & np.isfinite(df["mtow_kg"]) & np.isfinite(df["pfei_onboard_MJ_per_kg_km"])].sort_values("year")
        if group.empty:
            continue
        any_points = True
        label = ARCH_CONFIGS[architecture]["label"]
        ax.plot(group["mtow_kg"], group["pfei_onboard_MJ_per_kg_km"], "--", linewidth=1.0, alpha=0.6)
        feas = group[group["feasible"].map(_as_bool)]
        infeas = group[~group["feasible"].map(_as_bool)]
        if not feas.empty:
            ax.scatter(feas["mtow_kg"], feas["pfei_onboard_MJ_per_kg_km"], s=55, label=label)
        if not infeas.empty:
            ax.scatter(infeas["mtow_kg"], infeas["pfei_onboard_MJ_per_kg_km"], s=55, facecolors="none", label=label + " (infeasible)")
        for _, row in group.iterrows():
            ax.annotate(str(int(row["year"])), (row["mtow_kg"], row["pfei_onboard_MJ_per_kg_km"]), xytext=(5,4), textcoords="offset points", fontsize=8)
    ax.set_xlabel("MTOW [kg]"); ax.set_ylabel("Onboard PFEI [MJ/(kg·km)]"); _style_axes(ax)
    if any_points:
        ax.legend(fontsize=8)
    else:
        ax.text(0.5,0.5,"No numerically converged roadmap points",ha="center",va="center",transform=ax.transAxes)
    ax.set_title(title + "\nOpen markers = converged but physics-infeasible")
    _save(fig, path)


# =============================================================================
# TABLES AND REPORT
# =============================================================================


def build_paper_assumption_tables() -> Dict[str, pd.DataFrame]:
    """Static paper-inspired assumption tables mapped to ADaPT inputs."""
    table2 = pd.DataFrame([
        {"horizon":"Short-term (2025-2035)","architecture":"Conventional ICE","battery":"-","electric_machine":"-","fuel":"Conventional fuel","tank":"-","power_electronics":"-"},
        {"horizon":"Short-term (2025-2035)","architecture":"Battery electric / solar-battery","battery":"Li-Ion","electric_machine":"Liquid-cooled PMSM","fuel":"-","tank":"-","power_electronics":"SiC"},
        {"horizon":"Medium-term (2035-2045)","architecture":"Conventional ICE","battery":"-","electric_machine":"-","fuel":"Conventional fuel","tank":"-","power_electronics":"-"},
        {"horizon":"Medium-term (2035-2045)","architecture":"Battery electric / solar-battery","battery":"Li-S","electric_machine":"Halbach PMSM","fuel":"-","tank":"-","power_electronics":"SiC"},
        {"horizon":"Medium-term (2035-2045)","architecture":"Hydrogen ICE (ADaPT analog)","battery":"-","electric_machine":"-","fuel":"Hydrogen","tank":"Pressurized analog, eta_g=12.7%","power_electronics":"-"},
        {"horizon":"Long-term (2045-2050+)","architecture":"Battery electric / solar-battery","battery":"Li-O2","electric_machine":"Halbach PMSM","fuel":"-","tank":"-","power_electronics":"GaN"},
        {"horizon":"Long-term (2045-2050+)","architecture":"Hydrogen ICE (ADaPT analog)","battery":"-","electric_machine":"-","fuel":"Hydrogen","tank":"Cryogenic LH2, eta_g=40.5%","power_electronics":"-"},
    ])
    table3 = pd.DataFrame([
        {"horizon":x.horizon,"technology":x.electric_machine_technology,
         "specific_power_kW_kg":x.motor_specific_power_W_kg/1000.0,
         "nominal_efficiency":x.motor_efficiency} for x in ROADMAP_SCENARIOS
    ])
    table4 = pd.DataFrame([
        {"horizon":x.horizon,"technology":x.power_electronics_technology,
         "ADaPT_single_converter_efficiency_proxy":x.inverter_efficiency,
         "paper_note":"Paper reports separate motor/generator inverter and battery-converter values; ADaPT currently exposes one inverter_efficiency input."}
        for x in ROADMAP_SCENARIOS
    ])
    table5 = pd.DataFrame([
        {"horizon":x.horizon,"battery_technology":x.battery_technology,
         "specific_energy_Wh_kg":x.battery_specific_energy_Wh_kg,
         "volumetric_energy_density_Wh_L":x.battery_volumetric_ed_Wh_L}
        for x in ROADMAP_SCENARIOS
    ])
    return {"table2":table2,"table3":table3,"table4":table4,"table5":table5}


def _same_year_conventional_percent(df: pd.DataFrame, metrics: Sequence[str]) -> pd.DataFrame:
    out=df.copy()
    for metric in metrics:
        out[f"{metric}_diff_vs_same_year_conventional_pct"]=np.nan
    for year in sorted(out["year"].dropna().unique()):
        ref=out[(out["year"]==year)&(out["architecture"]=="conventional_reciprocating")]
        if ref.empty: continue
        for metric in metrics:
            refv=_scalar(ref.iloc[0].get(metric,np.nan))
            if not _isfinite(refv) or abs(refv)<1e-12: continue
            mask=out["year"]==year
            out.loc[mask,f"{metric}_diff_vs_same_year_conventional_pct"]=100.0*(pd.to_numeric(out.loc[mask,metric],errors="coerce")-refv)/refv
    return out


def build_table8_design_results(roadmap: pd.DataFrame) -> pd.DataFrame:
    cols=["year","horizon","architecture","architecture_name","BR_takeoff",
          "tail_volume_coeff_horizontal","tail_volume_coeff_vertical","lift_coeff",
          "drag_due_to_lift_factor","propeller_efficiency","length_m","fineness_ratio"]
    return roadmap.loc[roadmap["feasible"].map(_as_bool),[c for c in cols if c in roadmap.columns]].sort_values(["year","architecture"])


def build_table9_rated_power(roadmap: pd.DataFrame) -> pd.DataFrame:
    cols=["year","horizon","architecture","architecture_name","installed_shaft_power_kW",
          "rated_shaft_power_kW","rated_brake_power_kW","rated_shaft_power_per_unit_kW",
          "required_power_kW","battery_capacity_kWh","solar_energy_generated_kWh",
          "consumable_mass_kg"]
    return roadmap.loc[roadmap["feasible"].map(_as_bool),[c for c in cols if c in roadmap.columns]].sort_values(["year","architecture"])


def build_table10_mass_breakdown(roadmap: pd.DataFrame) -> pd.DataFrame:
    """Build a mutually exclusive ADaPT mass-breakdown table.

    Compatibility aliases are not summed together:
    * BatteryOnly.power_system_mass == battery_mass.
    * SolarBattery.power_system_mass == battery_mass + pv_mass.
    * Propulsion.prime_mover_mass is already included in propulsion_mass.
    """
    feasible = roadmap.loc[roadmap["feasible"].map(_as_bool)].copy()
    rows: List[Dict[str, Any]] = []

    common_components = [
        "envelope_mass_kg",
        "gondola_mass_kg",
        "fin_mass_kg",
        "landing_system_mass_kg",
        "helium_mass_kg",
        "miscellaneous_mass_kg",
    ]

    for _, source in feasible.iterrows():
        architecture = str(source["architecture"])
        row: Dict[str, Any] = {
            "year": source.get("year", np.nan),
            "horizon": source.get("horizon", ""),
            "architecture": architecture,
            "architecture_name": source.get("architecture_name", ""),
            "owe_kg": source.get("owe_kg", np.nan),
            "payload_kg": source.get("payload_kg", np.nan),
            "mtow_kg": source.get("mtow_kg", np.nan),
        }

        exclusive_columns: List[str] = []
        for column in common_components:
            row[column] = source.get(column, np.nan)
            exclusive_columns.append(column)

        # Mechanical propulsion total already includes prime mover, nacelles,
        # propellers, mounts, and optional wiring.
        row["propulsion_mass_kg"] = source.get(
            "propulsion_mass_kg",
            np.nan,
        )
        exclusive_columns.append("propulsion_mass_kg")

        # Architecture-dependent source/storage ownership.
        row["conversion_source_mass_kg"] = 0.0
        row["battery_storage_mass_kg"] = 0.0
        row["pv_mass_kg"] = 0.0
        row["hydrogen_tank_mass_kg"] = 0.0
        row["consumable_mass_kg"] = source.get(
            "consumable_mass_kg",
            0.0,
        )

        if architecture in {
            "conventional_reciprocating",
            "hydrogen_reciprocating",
        }:
            # Power.power_system_mass is conversion/accessory source mass and
            # is distinct from Propulsion.total_mass.
            row["conversion_source_mass_kg"] = source.get(
                "power_system_mass_kg",
                0.0,
            )
            exclusive_columns.append("conversion_source_mass_kg")

        if architecture == "battery_only":
            # Do not also add power_system_mass; it is an alias of battery_mass.
            row["battery_storage_mass_kg"] = source.get(
                "battery_mass_kg",
                0.0,
            )
            exclusive_columns.append("battery_storage_mass_kg")

        elif architecture == "solar_battery":
            # Use the transparent decomposition battery + PV. Do not add the
            # combined power_system_mass alias.
            row["battery_storage_mass_kg"] = source.get(
                "battery_mass_kg",
                0.0,
            )
            row["pv_mass_kg"] = source.get("pv_mass_kg", 0.0)
            exclusive_columns.extend([
                "battery_storage_mass_kg",
                "pv_mass_kg",
            ])

        elif architecture == "hydrogen_reciprocating":
            row["hydrogen_tank_mass_kg"] = source.get(
                "tank_mass_kg",
                0.0,
            )
            exclusive_columns.append("hydrogen_tank_mass_kg")

        if architecture in {
            "conventional_reciprocating",
            "hydrogen_reciprocating",
        }:
            exclusive_columns.append("consumable_mass_kg")

        exclusive_columns.append("payload_kg")

        numeric_values = [
            _scalar(row.get(column, np.nan))
            for column in exclusive_columns
        ]
        known_sum = float(np.nansum(numeric_values))
        mtow = _scalar(row.get("mtow_kg", np.nan))

        row["exclusive_mass_columns"] = ";".join(exclusive_columns)
        row["known_exclusive_mass_sum_kg"] = known_sum
        row["unexposed_or_closure_mass_kg"] = (
            mtow - known_sum if _isfinite(mtow) else np.nan
        )
        row["unexposed_or_closure_mass_pct_mtow"] = (
            100.0 * row["unexposed_or_closure_mass_kg"] / mtow
            if _isfinite(mtow) and abs(mtow) > 1.0e-12
            else np.nan
        )
        row["mass_accounting_note"] = (
            "Mutually exclusive ownership used. Residual represents masses "
            "not separately exposed by the current group and numerical closure; "
            "it is not a duplicate-component correction."
        )
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["year", "architecture"])


def build_table11_performance_emissions(roadmap: pd.DataFrame) -> pd.DataFrame:
    cols=["year","horizon","architecture","architecture_name","mtow_kg","ground_roll_distance_m",
          "consumable_mass_kg","battery_capacity_kWh","onboard_energy_MJ",
          "mission_propulsive_energy_MJ","pfei_onboard_MJ_per_kg_km",
          "direct_co2_kg","direct_nox_kg","direct_h2o_kg"]
    tbl=roadmap.loc[roadmap["feasible"].map(_as_bool),[c for c in cols if c in roadmap.columns]].copy()
    metrics=[c for c in ["mtow_kg","consumable_mass_kg","onboard_energy_MJ",
                         "pfei_onboard_MJ_per_kg_km","direct_co2_kg","direct_h2o_kg"] if c in tbl.columns]
    return _same_year_conventional_percent(tbl,metrics).sort_values(["year","architecture"])

def architecture_summary_table(
    roadmap: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for architecture in ARCHITECTURE_ORDER:
        group = roadmap[
            (roadmap["architecture"] == architecture)
            & roadmap["feasible"].map(_as_bool)
        ].sort_values("year")

        if group.empty:
            continue

        first = group.iloc[0]
        last = group.iloc[-1]

        rows.append({
            "architecture": architecture,
            "architecture_name": ARCH_CONFIGS[architecture]["label"],
            "first_year": int(first["year"]),
            "last_year": int(last["year"]),
            "mtow_first_kg": first["mtow_kg"],
            "mtow_last_kg": last["mtow_kg"],
            "mtow_change_pct": (
                100.0
                * (last["mtow_kg"] - first["mtow_kg"])
                / first["mtow_kg"]
            ),
            "pfei_first": first["pfei_onboard_MJ_per_kg_km"],
            "pfei_last": last["pfei_onboard_MJ_per_kg_km"],
            "pfei_change_pct": (
                100.0
                * (
                    last["pfei_onboard_MJ_per_kg_km"]
                    - first["pfei_onboard_MJ_per_kg_km"]
                )
                / first["pfei_onboard_MJ_per_kg_km"]
            ),
            "ground_roll_first_m": first["ground_roll_distance_m"],
            "ground_roll_last_m": last["ground_roll_distance_m"],
        })

    return pd.DataFrame(rows)


def simple_markdown_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "No data."

    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]

    for _, row in df.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if pd.isna(value):
                values.append("")
            elif isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.5g}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def write_report(
    baseline: pd.DataFrame,
    sweep_summary: pd.DataFrame,
    frozen_summary: pd.DataFrame,
    reoptimized_summary: Optional[pd.DataFrame],
    output_dir: Path,
    assessment_name: str = "AV-10 equivalent Technology Assessment",
    baseline_mode: str = "reference_geometry_retrofit",
) -> None:
    lines = [
        f"# {assessment_name}",
        "",
        f"Schema: `{SCHEMA_VERSION}`",
        "",
        "## Common mission and frozen baseline",
        "",
        f"- Payload: {COMMON_PAYLOAD_KG:.1f} kg",
        f"- Range: {COMMON_RANGE_KM:.1f} km",
        f"- Cruise speed: {COMMON_CRUISE_SPEED_MS:.1f} m/s",
        f"- Cruise altitude: {COMMON_CRUISE_ALT_M:.1f} m",
        f"- Baseline mode: {baseline_mode}",
        ("- Geometry/operating point: nominal AV-10 equivalent reference values for every architecture"
         if baseline_mode == "reference_geometry_retrofit"
         else "- Geometry/operating point: architecture-specific common-mission Pareto baseline imported from the LHS + NSGA-II study"),
        f"- Field-length requirement: {FIELD_LENGTH_LIMIT_M:.1f} m",
        "",
        "## Reference-paper mapping",
        "",
        ("The technology horizons, battery assumptions, electric-machine assumptions, and same-year conventional comparison structure are inspired by Marciello et al. (2023). The numerical aircraft/airship results are generated by ADaPT and are not copied from the paper."),
        "",
        ("Solar-battery is an airship-specific extension. Hydrogen fuel-cell architectures from the reference paper are represented by the currently validated hydrogen-reciprocating ADaPT architecture; this is an analog comparison, not a claim of identical powertrain physics."),
        "",
        "## Model structure",
        "",
        (
            "AirshipAnalysisGroup is used directly as the OpenMDAO root model. "
            "No duplicate promoted IndepVarComp is created. Fuel, hydrogen, "
            "battery, and tank requirements are sized by their authoritative "
            "components with prescribed consumable capacity disabled."
        ),
        "",
        (
            "Fixed-design sweeps isolate technology effects. The optional "
            "reoptimized roadmap permits only the validated local variables "
            "BR_takeoff, tail-volume coefficients, lift coefficient, induced-"
            "drag factor, and propeller efficiency to adapt. Hull geometry, "
            "installed shaft power, mission, and consumable ownership remain "
            "fixed."
        ),
        "",
        "## Common-mission baseline",
        "",
    ]

    baseline_columns = [
        "architecture_name",
        "physics_feasible",
        "operational_feasible",
        "length_m",
        "fineness_ratio",
        "cruise_speed_mps",
        "mtow_kg",
        "owe_kg",
        "consumable_mass_kg",
        "battery_mass_kg",
        "tank_mass_kg",
        "pfei_onboard_MJ_per_kg_km",
        "ground_roll_distance_m",
        "nearest_operational_constraint",
    ]
    lines.append(
        simple_markdown_table(
            baseline[
                [c for c in baseline_columns if c in baseline.columns]
            ]
        )
    )

    lines.extend([
        "",
        "## One-at-a-time sensitivity summary",
        "",
    ])
    lines.append(simple_markdown_table(sweep_summary))

    lines.extend([
        "",
        "## Frozen-design roadmap summary",
        "",
    ])
    lines.append(simple_markdown_table(frozen_summary))

    if reoptimized_summary is not None and not reoptimized_summary.empty:
        lines.extend([
            "",
            "## Reoptimized roadmap summary",
            "",
        ])
        lines.append(simple_markdown_table(reoptimized_summary))

    lines.extend([
        "",
        "## Interpretation notes",
        "",
        ("- `physics_feasible` exactly follows the outer architecture-comparison rejection logic: ground-roll/landing distance are diagnostics, not rejection criteria. `operational_feasible` adds the 300 m ground-roll requirement."),
        ("- Onboard PFEI uses the same accounting as the validated AV-10 equivalent Pareto study: fuel LHV for combustion architectures, battery capacity for battery-electric, and battery capacity plus generated solar energy for solar-battery."),
        (
            "- Conventional-fuel emission indices are reporting-level static "
            "indices, not a combustor model."
        ),
        (
            "- Hydrogen reciprocating direct CO2 is reported as zero and "
            "stoichiometric water is reported. Hydrogen-combustion NOx is left "
            "undefined because the present model does not calculate it."
        ),
        (
            "- Battery and solar-battery direct operational exhaust emissions "
            "are zero; lifecycle electricity and manufacturing emissions are "
            "outside this script."
        ),
        (
            "- Satisfied energy and volume sizing closures are excluded from "
            "nearest-active operational-constraint ranking."
        ),
        (
            "- Hydrogen ICE is omitted from the 2030 paper-aligned roadmap; "
            "its common-mission baseline and dedicated sensitivity studies "
            "remain available as ADaPT analyses."
        ),
        (
            "- Reoptimized roadmap points use multi-start SLSQP and retain the "
            "frozen design whenever no feasible optimizer result matches or "
            "improves its MTOW."
        ),
        (
            "- Table 10 uses mutually exclusive component ownership and does "
            "not sum compatibility aliases with their underlying masses."
        ),
    ])

    (output_dir / "technology_assessment_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_manifest(
    args: argparse.Namespace,
    output_dir: Path,
) -> None:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "script": str(THIS_FILE),
        "project_root": str(PROJECT_ROOT),
        "architectures": ARCHITECTURE_ORDER,
        "common_mission": {
            "payload_kg": COMMON_PAYLOAD_KG,
            "range_km": COMMON_RANGE_KM,
            "cruise_altitude_m": COMMON_CRUISE_ALT_M,
            "cruise_speed_mps": COMMON_CRUISE_SPEED_MS,
            "length_m": COMMON_LENGTH_M,
            "fineness_ratio": COMMON_FINENESS_RATIO,
            "field_length_limit_m": FIELD_LENGTH_LIMIT_M,
            "reference_mtow_kg": REFERENCE_MTOW_KG,
            "reference_volume_m3": REFERENCE_VOLUME_M3,
            "reference_power_W": REFERENCE_POWER_W,
            "reference_solar_area_m2": REFERENCE_SOLAR_AREA_M2,
        },
        "use_installed_power_closure": USE_INSTALLED_POWER_CLOSURE,
        "reference_design": REFERENCE_DESIGN,
        "local_design_bounds": LOCAL_DESIGN_BOUNDS,
        "roadmap_optimizer_excludes_propeller_efficiency": True,
        "hydrogen_short_term_roadmap_excluded": False,
        "roadmap_scenarios": [asdict(s) for s in ROADMAP_SCENARIOS],
        "run_reoptimised_roadmap": getattr(args, "run_reoptimised_roadmap", False),
        "quick": args.quick,
        "pareto_output_dir": getattr(args, "pareto_output_dir", None),
        "dual_assessment_modes": ["reference_geometry_retrofit", "architecture_specific_pareto"],
        "physics_feasibility_ground_roll_rejection": False,
        "operational_feasibility_ground_roll_rejection": True,
        "adaptive_sweep_max_rounds": ADAPTIVE_SWEEP_MAX_ROUNDS,
        "adaptive_sweep_jump_fraction": ADAPTIVE_SWEEP_JUMP_FRACTION,
        "feasibility_metric": "RSS of positive normalized utilization exceedances above 1.0",
        "pfei_basis": "onboard_total, matched to validated AV-10 Pareto study",
        "solar_battery_pfei_components": ["battery_capacity", "solar_energy_generated"],
        "pareto_source_file_priority": ["pfei_success", "pareto_front", "pfei_all"],
    }

    (output_dir / "technology_assessment_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )



# =============================================================================
# DUAL-ASSESSMENT ORCHESTRATION HELPERS
# =============================================================================

def _resolve_pareto_root(value: Any) -> Path:
    """Resolve an explicitly supplied architecture-study output directory.

    ``auto`` is handled by :func:`_discover_pareto_output_root`.  For a relative
    explicit path, check the locations used by normal terminal and Spyder runs.
    """
    raw_text = str(value).strip()
    if raw_text.lower() in {"", "auto", "discover", "none"}:
        return (PROJECT_ROOT / "pfei_av10_outputs").resolve()

    raw = Path(raw_text).expanduser()
    if raw.is_absolute():
        return raw.resolve()

    candidates = [
        Path.cwd() / raw,
        THIS_FILE.parent / raw,
        PROJECT_ROOT / raw,
        PROJECT_ROOT / "studies" / raw,
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except OSError:
            pass
    return (PROJECT_ROOT / raw).resolve()

def build_pareto_reproduction_audit(
    cases: Mapping[str, AssessmentCase],
    baseline: pd.DataFrame,
) -> pd.DataFrame:
    """Compare imported Pareto baseline metadata with the re-evaluated model.

    This is deliberately an audit, not an acceptance test. Assessment B imports
    a physics-feasible Pareto design from the validated AV-10 PFEI/LHS+NSGA-II
    study and re-evaluates it with the matched governing-model configuration.
    Small numerical differences can remain because installed power is independently
    closed. Large MTOW/PFEI differences, or a source-feasible point becoming
    rerun-infeasible, indicate a reproduction mismatch that must be investigated
    before the technology trends are used in the paper.
    """
    rows: List[Dict[str, Any]] = []
    if baseline is None:
        baseline = pd.DataFrame()

    for architecture in ARCHITECTURE_ORDER:
        case = cases.get(architecture)
        group = baseline[baseline.get("architecture", pd.Series(dtype=str)) == architecture] if not baseline.empty else pd.DataFrame()
        result = group.iloc[0] if not group.empty else None

        source_mtow = case.baseline_source_mtow_kg if case is not None else np.nan
        source_pfei = case.baseline_source_pfei if case is not None else np.nan
        rerun_mtow = _scalar(result.get("mtow_kg", np.nan)) if result is not None else np.nan
        rerun_pfei = _scalar(result.get("pfei_onboard_MJ_per_kg_km", np.nan)) if result is not None else np.nan

        mtow_delta = rerun_mtow - source_mtow if _isfinite(rerun_mtow) and _isfinite(source_mtow) else np.nan
        pfei_delta = rerun_pfei - source_pfei if _isfinite(rerun_pfei) and _isfinite(source_pfei) else np.nan
        mtow_pct = 100.0 * mtow_delta / source_mtow if _isfinite(mtow_delta) and abs(source_mtow) > 1e-12 else np.nan
        pfei_pct = 100.0 * pfei_delta / source_pfei if _isfinite(pfei_delta) and abs(source_pfei) > 1e-12 else np.nan

        rows.append({
            "architecture": architecture,
            "architecture_name": ARCH_CONFIGS[architecture]["label"],
            "baseline_available": case is not None,
            "source_file": case.baseline_source_file if case is not None else "",
            "source_selection": case.baseline_source_selection if case is not None else "unavailable",
            "source_mtow_kg": source_mtow,
            "rerun_mtow_kg": rerun_mtow,
            "mtow_delta_kg": mtow_delta,
            "mtow_delta_pct": mtow_pct,
            "source_pfei_MJ_per_kg_km": source_pfei,
            "rerun_pfei_MJ_per_kg_km": rerun_pfei,
            "pfei_delta": pfei_delta,
            "pfei_delta_pct": pfei_pct,
            "physics_feasible_on_rerun": bool(result.get("physics_feasible", False)) if result is not None else False,
            "operational_feasible_on_rerun": bool(result.get("operational_feasible", False)) if result is not None else False,
            "failure_reasons": str(result.get("failure_reasons", "")) if result is not None else "baseline_unavailable",
        })
    return pd.DataFrame(rows)


def _run_assessment_bundle(
    cases: Mapping[str, AssessmentCase],
    output_dir: Path,
    args: argparse.Namespace,
    assessment_name: str,
    baseline_mode: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """Run one complete technology assessment for a supplied baseline set.

    The same workflow is used for both questions in the paper:
      A) nominal AV-10 equivalent reference-geometry retrofit; and
      B) architecture-specific common-mission Pareto baselines.

    Architectures absent from ``cases`` (for example battery-only when the
    architecture study found no feasible common-mission design) are retained
    in the baseline/roadmap audit as unavailable, but their sweeps and coupled
    maps are skipped rather than raising a KeyError.
    """
    output_dir = _ensure_dir(output_dir)
    print("\n" + "=" * 78)
    print(assessment_name)
    print("=" * 78)

    # ------------------------------------------------------------------
    # 1. Baseline
    # ------------------------------------------------------------------
    print("[1/5] Common-mission baseline architecture assessment")
    baseline = run_common_baseline(cases)
    baseline["assessment_mode"] = baseline_mode
    baseline.to_csv(output_dir / "common_mission_baseline.csv", index=False)

    baseline_failure_cols = [c for c in [
        "architecture", "architecture_name", "baseline_mode",
        "physics_feasible", "operational_feasible", "feasible",
        "failure_reasons", "physics_failure_reasons",
        "operational_failure_reasons", "dominant_failure_category",
        "operational_dominant_failure_category", "evaluation_status",
        "g_power_W", "g_energy", "g_buoyancy_N", "g_lift",
        "g_groundroll_m", "g_volume_m3", "power_utilization",
        "energy_utilization", "buoyancy_utilization",
        "ground_roll_utilization", "volume_utilization",
        "constraint_utilization", "feasibility_distance",
        "operational_constraint_utilization",
        "operational_feasibility_distance", "power_closure_converged",
        "power_closure_relative_error", "error",
    ] if c in baseline.columns]
    baseline[baseline_failure_cols].to_csv(
        output_dir / "common_mission_baseline_failure_audit.csv", index=False
    )
    plot_baseline_architectures(baseline, output_dir / "common_mission_baseline.png")

    # ------------------------------------------------------------------
    # 2. One-at-a-time technology sweeps
    # ------------------------------------------------------------------
    print("[2/5] Frozen-design one-at-a-time technology sweeps")
    sweep_frames: List[pd.DataFrame] = []
    sweep_summary_rows: List[Dict[str, Any]] = []

    for architecture, parameter, values, xlabel in default_sweeps():
        if architecture not in cases:
            sweep_summary_rows.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "parameter": parameter,
                "status": "skipped_no_feasible_baseline",
                "assessment_mode": baseline_mode,
            })
            continue

        if args.quick:
            values = np.linspace(float(np.min(values)), float(np.max(values)), 5)

        print(f"    {architecture}: {parameter}")
        try:
            df = run_fixed_sweep(cases[architecture], parameter, values)
            df["assessment_mode"] = baseline_mode
            filename = f"sweep_{architecture}_{parameter}.csv"
            df.to_csv(output_dir / filename, index=False)
            plot_sweep(df, xlabel, output_dir / filename.replace(".csv", ".png"))
            sweep_frames.append(df)

            physics_feasible = df[df["physics_feasible"].map(_as_bool)] if "physics_feasible" in df.columns else df[df["feasible"].map(_as_bool)]
            operational_feasible = df[df["operational_feasible"].map(_as_bool)] if "operational_feasible" in df.columns else pd.DataFrame()
            sweep_summary_rows.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "parameter": parameter,
                "assessment_mode": baseline_mode,
                "baseline_value": df["baseline_parameter_value"].iloc[0] if "baseline_parameter_value" in df.columns and not df.empty else np.nan,
                "minimum_physics_feasible_value": physics_feasible["parameter_value"].min() if not physics_feasible.empty else np.nan,
                "maximum_physics_feasible_value": physics_feasible["parameter_value"].max() if not physics_feasible.empty else np.nan,
                "minimum_operational_feasible_value": operational_feasible["parameter_value"].min() if not operational_feasible.empty else np.nan,
                "maximum_operational_feasible_value": operational_feasible["parameter_value"].max() if not operational_feasible.empty else np.nan,
                "minimum_physics_feasible_mtow_kg": physics_feasible["mtow_kg"].min() if not physics_feasible.empty else np.nan,
                "maximum_absolute_elasticity": pd.to_numeric(df.get("elasticity_mtow"), errors="coerce").abs().max() if "elasticity_mtow" in df.columns else np.nan,
                "status": "evaluated",
            })
        except Exception as exc:
            traceback.print_exc()
            sweep_summary_rows.append({
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "parameter": parameter,
                "assessment_mode": baseline_mode,
                "status": "execution_exception",
                "error": f"{type(exc).__name__}: {exc}",
            })

    sweep_summary = pd.DataFrame(sweep_summary_rows)
    sweep_summary.to_csv(output_dir / "fixed_sweep_summary.csv", index=False)
    if sweep_frames:
        plot_normalised(sweep_frames, output_dir / "normalised_technology_sensitivities.png")

    # ------------------------------------------------------------------
    # 3. Coupled maps
    # ------------------------------------------------------------------
    print("[3/5] Coupled technology maps")
    if args.quick:
        battery_x = np.array([300.0, 700.0, 1100.0])
        battery_y = np.array([650.0, 1000.0, 1400.0])
        solar_x = np.array([0.26, 0.35, 0.42])
        solar_y = np.array([300.0, 600.0, 900.0])
        hydrogen_x = np.array([0.08, 0.15, 0.25])
        hydrogen_y = np.array([0.72, 0.78, 0.84])
    else:
        battery_x = np.arange(250.0, 1201.0, 50.0)
        battery_y = np.arange(500.0, 1401.0, 100.0)
        solar_x = np.arange(0.20, 0.421, 0.02)
        solar_y = np.arange(250.0, 1001.0, 50.0)
        hydrogen_x = np.arange(0.05, 0.251, 0.0125)
        hydrogen_y = np.arange(0.68, 0.861, 0.01)

    grid_specs = [
        ("battery_only", "battery_specific_energy", battery_x,
         "battery_volumetric_ed", battery_y, "battery_storage_map",
         "battery_specific_energy_input", "battery_volumetric_ed_input",
         "Battery specific energy [Wh/kg]", "Battery volumetric energy density [Wh/L]",
         "Battery-electric coupled storage map"),
        ("solar_battery", "solar_efficiency", solar_x,
         "battery_specific_energy", solar_y, "solar_battery_map",
         "solar_efficiency_input", "battery_specific_energy_input",
         "Solar conversion efficiency [-]", "Battery specific energy [Wh/kg]",
         "Solar-battery coupled technology map"),
        ("hydrogen_reciprocating", "tank_gravimetric_efficiency", hydrogen_x,
         "propeller_efficiency", hydrogen_y, "hydrogen_tank_propulsion_map",
         "tank_gravimetric_efficiency_input", "propeller_efficiency_input",
         "Tank gravimetric efficiency [-]", "Propeller efficiency [-]",
         "Hydrogen-ICE tank and propulsion technology map"),
    ]

    for (architecture, xname, xvalues, yname, yvalues, stem,
         xcol, ycol, xlabel, ylabel, title) in grid_specs:
        if architecture not in cases:
            pd.DataFrame([{
                "architecture": architecture,
                "architecture_name": ARCH_CONFIGS[architecture]["label"],
                "assessment_mode": baseline_mode,
                "status": "skipped_no_feasible_baseline",
            }]).to_csv(output_dir / f"{stem}_skipped.csv", index=False)
            continue
        try:
            grid = run_two_parameter_grid(
                cases[architecture], xname, xvalues, yname, yvalues, stem
            )
            grid["assessment_mode"] = baseline_mode
            grid.to_csv(output_dir / f"{stem}.csv", index=False)
            plot_grid(grid, xcol, ycol, xlabel, ylabel, title,
                      output_dir / f"{stem}.png")
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------------
    # 4. Frozen roadmap
    # ------------------------------------------------------------------
    print("[4/5] Frozen-design technology roadmap")
    frozen_roadmap = run_frozen_roadmap(cases, ROADMAP_SCENARIOS)
    frozen_roadmap["assessment_mode"] = baseline_mode
    frozen_roadmap.to_csv(output_dir / "frozen_design_roadmap.csv", index=False)
    plot_roadmap(frozen_roadmap, "Common-mission frozen-design technology roadmap",
                 output_dir / "frozen_design_roadmap.png")
    plot_trajectory(frozen_roadmap, "Frozen-design MTOW–PFEI technology trajectories",
                    output_dir / "frozen_design_trajectory.png")
    frozen_summary = architecture_summary_table(frozen_roadmap)
    if not frozen_summary.empty:
        frozen_summary["assessment_mode"] = baseline_mode
    frozen_summary.to_csv(output_dir / "frozen_design_roadmap_summary.csv", index=False)
    build_table8_design_results(frozen_roadmap).to_csv(output_dir / "table8_design_results_analog.csv", index=False)
    build_table9_rated_power(frozen_roadmap).to_csv(output_dir / "table9_rated_power_analog.csv", index=False)
    build_table10_mass_breakdown(frozen_roadmap).to_csv(output_dir / "table10_mass_breakdown_analog.csv", index=False)
    build_table11_performance_emissions(frozen_roadmap).to_csv(output_dir / "table11_performance_emissions_analog.csv", index=False)

    # ------------------------------------------------------------------
    # 5. Controlled reoptimized roadmap
    # ------------------------------------------------------------------
    reoptimized_summary: Optional[pd.DataFrame] = None
    if not args.run_reoptimised_roadmap:
        print("[5/5] Reoptimized roadmap skipped")
    else:
        print("[5/5] Controlled reoptimized technology roadmap")
        try:
            reoptimized = run_reoptimised_roadmap(cases, ROADMAP_SCENARIOS)
            reoptimized["assessment_mode"] = baseline_mode
            reoptimized.to_csv(output_dir / "reoptimised_roadmap.csv", index=False)
            plot_roadmap(reoptimized, "Common-mission controlled reoptimized technology roadmap",
                         output_dir / "reoptimised_roadmap.png")
            plot_trajectory(reoptimized, "Reoptimized MTOW–PFEI technology trajectories",
                            output_dir / "reoptimised_trajectory.png")
            reoptimized_summary = architecture_summary_table(reoptimized)
            if not reoptimized_summary.empty:
                reoptimized_summary["assessment_mode"] = baseline_mode
            reoptimized_summary.to_csv(output_dir / "reoptimised_roadmap_summary.csv", index=False)
            build_table8_design_results(reoptimized).to_csv(output_dir / "table8_design_results_reoptimised_analog.csv", index=False)
            build_table9_rated_power(reoptimized).to_csv(output_dir / "table9_rated_power_reoptimised_analog.csv", index=False)
            build_table10_mass_breakdown(reoptimized).to_csv(output_dir / "table10_mass_breakdown_reoptimised_analog.csv", index=False)
            build_table11_performance_emissions(reoptimized).to_csv(output_dir / "table11_performance_emissions_reoptimised_analog.csv", index=False)
        except Exception:
            traceback.print_exc()
            print("WARNING: controlled reoptimized roadmap failed; frozen roadmap outputs remain valid.")

    write_report(
        baseline, sweep_summary, frozen_summary, reoptimized_summary,
        output_dir, assessment_name=assessment_name, baseline_mode=baseline_mode,
    )
    return baseline, frozen_roadmap, reoptimized_summary


def write_dual_assessment_summary(
    reference_baseline: Optional[pd.DataFrame],
    pareto_baseline: Optional[pd.DataFrame],
    output_dir: Path,
) -> None:
    """Write a compact cross-assessment baseline comparison and explanation."""
    frames: List[pd.DataFrame] = []
    for mode, df in [
        ("reference_geometry_retrofit", reference_baseline),
        ("architecture_specific_pareto", pareto_baseline),
    ]:
        if df is None or df.empty:
            continue
        tmp = df.copy()
        tmp["assessment_mode"] = mode
        frames.append(tmp)

    if not frames:
        return

    combined = pd.concat(frames, ignore_index=True, sort=False)
    keep = [c for c in [
        "assessment_mode", "architecture", "architecture_name",
        "baseline_source_selection", "length_m", "fineness_ratio",
        "cruise_speed_mps", "mtow_kg", "pfei_onboard_MJ_per_kg_km",
        "physics_feasible", "operational_feasible", "ground_roll_distance_m",
        "constraint_utilization", "operational_constraint_utilization",
        "failure_reasons", "operational_failure_reasons",
    ] if c in combined.columns]
    summary = combined[keep].copy()
    summary.to_csv(output_dir / "dual_assessment_baseline_comparison.csv", index=False)

    md = [
        "# AV-10 equivalent dual technology-assessment summary",
        "",
        "Two distinct questions are evaluated and must not be conflated:",
        "",
        "1. **Reference-geometry retrofit:** all architectures are imposed on the nominal AV-10 equivalent geometry/operating point.",
        "2. **Architecture-specific Pareto baseline:** each architecture starts from its own physics-feasible common-mission design from the LHS + NSGA-II study; architectures with no such baseline are reported as unavailable.",
        "",
        "`physics_feasible` is directly comparable with the architecture Pareto study and does **not** reject a point for ground roll. `operational_feasible` additionally enforces the 300 m field-length criterion.",
        "",
        "## Baseline comparison",
        "",
        simple_markdown_table(summary),
    ]
    (output_dir / "dual_assessment_summary.md").write_text("\n".join(md), encoding="utf-8")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AV-10 equivalent dual technology assessment: reference retrofit + architecture-specific Pareto baseline"
    )
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--pareto-output-dir", default="auto",
                        help=("Root output directory from the AV-10 equivalent LHS+NSGA-II architecture study. "
                              "Default 'auto' searches the working directory, studies folder, and project root."))
    parser.add_argument("--quick", action="store_true",
                        help="Use reduced one- and two-parameter grids for a fast test.")
    parser.add_argument("--run-reoptimised-roadmap", action="store_true",
                        help="Also run the controlled local SLSQP roadmap for each available baseline.")
    parser.add_argument("--skip-reference-retrofit", action="store_true",
                        help="Skip the nominal 75 m reference-geometry retrofit assessment.")
    parser.add_argument("--skip-pareto-baseline", action="store_true",
                        help="Skip the architecture-specific Pareto-baseline assessment.")
    args = parser.parse_args()

    root = _ensure_dir(args.output_dir)
    write_manifest(args, root)

    # Shared technology-assumption tables are written once at the root.
    assumption_tables = build_paper_assumption_tables()
    assumption_tables["table2"].to_csv(root / "table2_technology_architecture_matrix.csv", index=False)
    assumption_tables["table3"].to_csv(root / "table3_electric_machine_assumptions.csv", index=False)
    assumption_tables["table4"].to_csv(root / "table4_power_electronics_assumptions.csv", index=False)
    assumption_tables["table5"].to_csv(root / "table5_battery_assumptions.csv", index=False)

    reference_baseline: Optional[pd.DataFrame] = None
    pareto_baseline: Optional[pd.DataFrame] = None

    # Assessment A: nominal AV-10 equivalent reference-geometry retrofit.
    if not args.skip_reference_retrofit:
        reference_cases = common_mission_cases()
        reference_baseline, _, _ = _run_assessment_bundle(
            reference_cases,
            root / "assessment_A_reference_geometry_retrofit",
            args,
            "AV-10 equivalent reference-geometry retrofit technology assessment",
            "reference_geometry_retrofit",
        )

    # Assessment B: architecture-specific feasible common-mission Pareto baseline.
    if not args.skip_pareto_baseline:
        pareto_root, discovery_audit = _discover_pareto_output_root(args.pareto_output_dir)
        print(f"\nLoading architecture-specific common-mission baselines from: {pareto_root}")
        pareto_dir = _ensure_dir(root / "assessment_B_architecture_specific_pareto")
        discovery_audit.to_csv(pareto_dir / "pareto_root_discovery_audit.csv", index=False)
        pareto_cases, source_audit = load_architecture_specific_pareto_cases(pareto_root)
        source_audit.to_csv(pareto_dir / "pareto_baseline_source_audit.csv", index=False)

        if not pareto_cases:
            print("WARNING: no architecture-specific Pareto baselines could be loaded.")
            print("  Check: " + str(pareto_dir / "pareto_root_discovery_audit.csv"))
            print("  Check: " + str(pareto_dir / "pareto_baseline_source_audit.csv"))
            print("  If needed, pass the exact architecture-study output folder with --pareto-output-dir <path>.")
        else:
            pareto_baseline, _, _ = _run_assessment_bundle(
                pareto_cases,
                pareto_dir,
                args,
                "AV-10 equivalent architecture-specific Pareto-baseline technology assessment",
                "architecture_specific_pareto",
            )
            reproduction = build_pareto_reproduction_audit(pareto_cases, pareto_baseline)
            reproduction.to_csv(pareto_dir / "pareto_baseline_reproduction_audit.csv", index=False)



    write_dual_assessment_summary(reference_baseline, pareto_baseline, root)

    print("\nCompleted AV-10 equivalent dual technology assessment.")
    print(f"Output directory: {root}")
    print("Feasibility convention: 'physics_feasible' matches the architecture Pareto study; "
          "'operational_feasible' additionally enforces the 300 m ground-roll requirement.")


if __name__ == "__main__":
    main()