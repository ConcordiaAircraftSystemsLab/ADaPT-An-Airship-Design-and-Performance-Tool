# -*- coding: utf-8 -*-
"""
ADaPT canonical single-run MDA / UI API.

This module provides one authoritative UI-facing interface to the current
AirshipAnalysisGroup.  Other run layers (optimization, feasibility, DOE,
Pareto and mission studies) can import the builder and result-collection
helpers from this file instead of reproducing subsystem equations.

Core conventions
----------------
1. AirshipAnalysisGroup is the top-level OpenMDAO model and owns the central
   independent-variable component.
2. Current ADaPT constraint convention: g <= 0 is feasible.
3. ``installed_shaft_power`` is TOTAL installed propulsor shaft power.
4. ``installed_consumable_capacity`` is installed fuel / hydrogen capacity.
5. Energy-storage, hydrogen-tank, propulsion, power and weight quantities are
   taken from their authoritative ADaPT components.
6. The builder supports non-rigid, semi-rigid and rigid airships and all power
   architectures exposed by the current AirshipAnalysisGroup.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import openmdao.api as om

# from adapt.AirshipAnalysisGroup import AirshipAnalysisGroup
# from adapt.operatingConditions import opCond
# -----------------------------------------------------------------------------
# ADaPT imports
# -----------------------------------------------------------------------------
# Package form is preferred for the UI.  The local-form fallback is useful when
# this file is executed directly inside the source folder.
try:
    from adapt.AirshipAnalysisGroup import AirshipAnalysisGroup
    from adapt.operatingConditions import opCond
except ImportError:
    from AirshipAnalysisGroup import AirshipAnalysisGroup
    from operatingConditions import opCond


# omxdsm is optional and only required when an XDSM report is requested.
try:
    from omxdsm import write_xdsm
    _HAS_OMXDSM = True
except Exception:
    write_xdsm = None
    _HAS_OMXDSM = False


# =============================================================================
# 1. Architecture definitions
# =============================================================================

POWER_SOURCE_ALIASES = {
    # Short UI labels retained as input aliases only.
    "conventional_fuel": "conventional_reciprocating",
    "conventional": "conventional_reciprocating",
    "hydrogen": "hydrogen_fuel_cell",
    "fuel_cell": "hydrogen_fuel_cell",
    "battery": "battery_only",
    "solar": "solar_battery",
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
    "turboprop",
    "turboelectric",
}

HYDROGEN_SOURCES = {
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
}

BATTERY_SOURCES = {
    "battery_only",
    "solar_battery",
    "solar-RFC",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
    "conventional_battery_hybrid",
}

SOLAR_SOURCES = {
    "solar_battery",
    "solar-RFC",
    "solar_hydrogen_hybrid",
}

TURBINE_SOURCES = {"turboprop", "turboelectric"}


# =============================================================================
# 2. Defaults used by the UI layer
# =============================================================================

POWER_SOURCE_DEFAULT = "conventional_reciprocating"
LANDING_SYSTEM_DEFAULT = "conventional"
AIRSHIP_TYPE_DEFAULT = "non-rigid"
NUM_STEPS_DEFAULT = 1

FIGSIZE_PROFILE_DEFAULT = (8.0, 6.0)


# =============================================================================
# 3. Generic helpers
# =============================================================================

def _cfg_get(cfg: Optional[Dict[str, Any]], key: str, default: Any) -> Any:
    return default if cfg is None else cfg.get(key, default)


def _canonical_power_source(value: str) -> str:
    source = POWER_SOURCE_ALIASES.get(str(value), str(value))
    if source not in SUPPORTED_POWER_SOURCES:
        raise ValueError(
            f"Unsupported power_source={source!r}. "
            f"Choose one of {sorted(SUPPORTED_POWER_SOURCES)}."
        )
    return source


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


def _get_max(
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


def _get_min(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    try:
        arr = _array(prob, name, units=units)
        arr = arr[np.isfinite(arr)]
        return float(np.min(arr)) if arr.size else float(default)
    except Exception:
        return float(default)


def _first_available(
    prob: om.Problem,
    candidates: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in candidates:
        value = _get(prob, name, units=units, default=np.nan)
        if np.isfinite(value):
            return value
    return float(default)


def _max_available(
    prob: om.Problem,
    candidates: Iterable[str],
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    for name in candidates:
        value = _get_max(prob, name, units=units, default=np.nan)
        if np.isfinite(value):
            return value
    return float(default)


def _set_if_present(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> bool:
    """Set a promoted model variable when that variable is active."""
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
    return _set_if_present(prob, name, np.full(int(n), float(value)), units=units)


def _set_group_option_if_available(group: om.Group, name: str, value: Any) -> bool:
    """
    Set an AirshipAnalysisGroup option before Problem.setup() when the current
    Group exposes that option.

    This lets the UI remain compatible with Group revisions that add optional
    configuration controls while keeping the core API stable.
    """
    try:
        if name in group.options:
            group.options[name] = value
            return True
    except Exception:
        pass
    return False


# =============================================================================
# 4. UI configuration normalization
# =============================================================================

def normalize_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a complete, canonical configuration dictionary for one MDA run."""
    cfg = {} if cfg is None else dict(cfg)

    source = _canonical_power_source(
        str(_cfg_get(cfg, "power_source", POWER_SOURCE_DEFAULT))
    )

    normalized = {
        # Architecture
        "power_source": source,
        "airship_type": str(_cfg_get(cfg, "airship_type", AIRSHIP_TYPE_DEFAULT)),
        "landing_system": str(_cfg_get(cfg, "landing_system", LANDING_SYSTEM_DEFAULT)),
        "num_steps": int(_cfg_get(cfg, "num_steps", NUM_STEPS_DEFAULT)),
        "enable_pressure_control": bool(_cfg_get(cfg, "enable_pressure_control", False)),
        "use_prescribed_consumable_capacity": bool(
            _cfg_get(cfg, "use_prescribed_consumable_capacity", True)
        ),
        "ballonet_sizing_method": str(
            _cfg_get(cfg, "ballonet_sizing_method", "pressure_altitude")
        ),
        "tail_coefficient_method": str(
            _cfg_get(cfg, "tail_coefficient_method", "user")
        ),
        "propulsion_installation_mass_method": str(
            _cfg_get(cfg, "propulsion_installation_mass_method", "generic")
        ),

        # Environment / mission
        "cruise_alt_m": float(
            _cfg_get(cfg, "cruise_alt_m", _cfg_get(cfg, "altitude_m", 914.0))
        ),
        "cruise_speed_mps": float(
            _cfg_get(cfg, "cruise_speed_mps", _cfg_get(cfg, "cruise_speed_ms", 19.5))
        ),
        "cruise_disa_K": float(
            _cfg_get(cfg, "cruise_disa_K", _cfg_get(cfg, "disa_K", 0.0))
        ),
        "T_env_K": float(_cfg_get(cfg, "T_env_K", _cfg_get(cfg, "T_env", 281.65))),
        "RH_pct": float(_cfg_get(cfg, "RH_pct", _cfg_get(cfg, "RH", 70.0))),
        "time": str(_cfg_get(cfg, "time", "day")),
        "payload_kg": float(_cfg_get(cfg, "payload_kg", 1123.0)),
        "range_m": float(_cfg_get(cfg, "range_m", 1_342_100.0)),
        "max_operating_altitude_m": float(
            _cfg_get(cfg, "max_operating_altitude_m", 3000.0)
        ),
        "takeoff_altitude_m": float(_cfg_get(cfg, "takeoff_altitude_m", 0.0)),
        "ascent_rate_mps": float(_cfg_get(cfg, "ascent_rate_mps", 3.0)),
        "descent_rate_mps": float(_cfg_get(cfg, "descent_rate_mps", 3.0)),

        # Geometry / structure
        "length_m": float(_cfg_get(cfg, "length_m", 53.4)),
        "fineness_ratio": float(_cfg_get(cfg, "fineness_ratio", 4.0)),
        "tail_volume_coeff_horizontal": float(
            _cfg_get(cfg, "tail_volume_coeff_horizontal", 0.066)
        ),
        "tail_volume_coeff_vertical": float(
            _cfg_get(cfg, "tail_volume_coeff_vertical", 0.059)
        ),
        "ballonet_fraction_prescribed": float(
            _cfg_get(cfg, "ballonet_fraction_prescribed", 0.08)
        ),
        "n_longitudinal_members": int(_cfg_get(cfg, "n_longitudinal_members", 12)),
        "n_rings": int(_cfg_get(cfg, "n_rings", 16)),
        "n_gas_cells": int(_cfg_get(cfg, "n_gas_cells", 12)),

        # Loading / installed capacity
        "installed_consumable_capacity_kg": float(
            _cfg_get(
                cfg,
                "installed_consumable_capacity_kg",
                _cfg_get(cfg, "fuel_mass_kg", 599.0),
            )
        ),
        "ballast_mass_kg": float(_cfg_get(cfg, "ballast_mass_kg", 0.0)),
        "n_crew": int(_cfg_get(cfg, "n_crew", 1)),

        # Mechanical propulsion
        # IMPORTANT: total installed shaft power for all propulsors.
        "installed_shaft_power_W": float(
            _cfg_get(
                cfg,
                "installed_shaft_power_W",
                _cfg_get(cfg, "engine_power_W", 268_000.0),
            )
        ),
        "n_engine": int(_cfg_get(cfg, "n_engine", 2)),
        "propeller_efficiency": float(
            _cfg_get(cfg, "propeller_efficiency", _cfg_get(cfg, "eta_p", 0.75))
        ),
        "gearbox_efficiency": float(_cfg_get(cfg, "gearbox_efficiency", 0.98)),
        "propeller_rps": float(_cfg_get(cfg, "propeller_rps", 20.0)),
        "propeller_blade_count": int(_cfg_get(cfg, "propeller_blade_count", 3)),
        "propeller_power_coefficient": float(
            _cfg_get(cfg, "propeller_power_coefficient", 0.08)
        ),
        "ice_specific_power_Wkg": float(_cfg_get(cfg, "ice_specific_power_Wkg", 1200.0)),

        # Aerodynamics / operation
        "BR_takeoff": float(_cfg_get(cfg, "BR_takeoff", 0.83)),
        "BR_landing": float(_cfg_get(cfg, "BR_landing", 0.90)),
        "lift_coeff": float(_cfg_get(cfg, "lift_coeff", 0.15)),
        "drag_coeff_zero": float(_cfg_get(cfg, "drag_coeff_zero", 0.03542)),
        "drag_due_to_lift_factor": float(
            _cfg_get(cfg, "drag_due_to_lift_factor", _cfg_get(cfg, "k_lift", 0.869))
        ),
        "tailwind_speed_mps": float(_cfg_get(cfg, "tailwind_speed_mps", 0.0)),
        "thrust_vector_angle_deg": float(_cfg_get(cfg, "thrust_vector_angle_deg", 0.0)),
        "rudder_deflection_deg": float(_cfg_get(cfg, "rudder_deflection_deg", 28.0)),
        "cruise_strategy": int(_cfg_get(cfg, "cruise_strategy", 1)),

        # Fuel / reciprocating technology
        "ice_thermal_efficiency": float(_cfg_get(cfg, "ice_thermal_efficiency", 0.30)),
        "gasoline_lhv_Jkg": float(_cfg_get(cfg, "gasoline_lhv_Jkg", 43.0e6)),
        "fuel_reserve_fraction": float(_cfg_get(cfg, "fuel_reserve_fraction", 0.10)),

        # Battery technology
        "battery_specific_energy_Whkg": float(
            _cfg_get(cfg, "battery_specific_energy_Whkg", 250.0)
        ),
        "battery_volumetric_ed_WhL": float(
            _cfg_get(cfg, "battery_volumetric_ed_WhL", 600.0)
        ),
        "battery_pack_voltage_V": float(_cfg_get(cfg, "battery_pack_voltage_V", 400.0)),
        "battery_cell_voltage_nom_V": float(
            _cfg_get(cfg, "battery_cell_voltage_nom_V", 3.7)
        ),
        "battery_efficiency": float(_cfg_get(cfg, "battery_efficiency", 0.95)),
        "depth_of_discharge": float(_cfg_get(cfg, "depth_of_discharge", 0.80)),
        "battery_packaging_factor": float(_cfg_get(cfg, "battery_packaging_factor", 0.72)),

        # Solar technology
        "solar_area_m2": float(_cfg_get(cfg, "solar_area_m2", 300.0)),
        "solar_irradiance_Wm2": float(_cfg_get(cfg, "solar_irradiance_Wm2", 600.0)),
        "solar_energy_MJ": float(_cfg_get(cfg, "solar_energy_MJ", 0.0)),
        "solar_efficiency": float(_cfg_get(cfg, "solar_efficiency", 0.22)),
        "pv_temp_coeff_fracK": float(_cfg_get(cfg, "pv_temp_coeff_fracK", -0.003)),
        "pv_reference_temperature_K": float(
            _cfg_get(cfg, "pv_reference_temperature_K", 298.15)
        ),
        "pv_areal_density_kgm2": float(
            _cfg_get(cfg, "pv_areal_density_kgm2", 0.50)
        ),

        # Hydrogen / tank technology
        "hydrogen_onboard_mass_kg": float(
            _cfg_get(
                cfg,
                "hydrogen_onboard_mass_kg",
                _cfg_get(cfg, "installed_consumable_capacity_kg", _cfg_get(cfg, "fuel_mass_kg", 150.0)),
            )
        ),
        "hydrogen_lhv_Jkg": float(_cfg_get(cfg, "hydrogen_lhv_Jkg", 120.0e6)),
        "hydrogen_storage_density_kgm3": float(
            _cfg_get(cfg, "hydrogen_storage_density_kgm3", 70.8)
        ),
        "tank_pressure_Pa": float(_cfg_get(cfg, "tank_pressure_Pa", 101325.0)),
        "tank_gravimetric_efficiency": float(
            _cfg_get(cfg, "tank_gravimetric_efficiency", 0.20)
        ),
        "tank_volume_mass_density_kgm3": float(
            _cfg_get(cfg, "tank_volume_mass_density_kgm3", 15.0)
        ),
        "delivery_mass_fraction": float(_cfg_get(cfg, "delivery_mass_fraction", 0.08)),
        "insulation_thickness_m": float(_cfg_get(cfg, "insulation_thickness_m", 0.05)),
        "insulation_density_kgm3": float(_cfg_get(cfg, "insulation_density_kgm3", 50.0)),

        # Fuel cell technology
        "fuel_cell_specific_power_Wkg": float(
            _cfg_get(cfg, "fuel_cell_specific_power_Wkg", 2000.0)
        ),
        "fuel_cell_efficiency": float(_cfg_get(cfg, "fuel_cell_efficiency", 0.55)),

        # Hybridization
        "chi": float(_cfg_get(cfg, "chi", 0.0)),
        "tau": float(_cfg_get(cfg, "tau", 0.0)),

        # Turbine / turboelectric technology
        "turboshaft_thermal_efficiency": float(
            _cfg_get(cfg, "turboshaft_thermal_efficiency", 0.32)
        ),
        "turboshaft_specific_power_Wkg": float(
            _cfg_get(cfg, "turboshaft_specific_power_Wkg", 3500.0)
        ),
        "generator_specific_power_Wkg": float(
            _cfg_get(cfg, "generator_specific_power_Wkg", 5000.0)
        ),
        "generator_efficiency": float(_cfg_get(cfg, "generator_efficiency", 0.96)),
        "motor_specific_power_Wkg": float(
            _cfg_get(cfg, "motor_specific_power_Wkg", 5000.0)
        ),
        "motor_efficiency": float(_cfg_get(cfg, "motor_efficiency", 0.95)),
        "inverter_efficiency": float(_cfg_get(cfg, "inverter_efficiency", 0.98)),
        "n_propulsor": int(_cfg_get(cfg, "n_propulsor", _cfg_get(cfg, "n_engine", 2))),
    }

    if normalized["num_steps"] < 1:
        raise ValueError("num_steps must be at least 1.")
    if normalized["airship_type"] not in {"non-rigid", "semi-rigid", "rigid"}:
        raise ValueError("airship_type must be 'non-rigid', 'semi-rigid', or 'rigid'.")
    if normalized["landing_system"] not in {"conventional", "acls"}:
        raise ValueError("landing_system must be 'conventional' or 'acls'.")

    # Keep any extra UI keys so the caller can retain application metadata.
    for key, value in cfg.items():
        normalized.setdefault(key, value)

    return normalized


# =============================================================================
# 5. OpenMDAO builder
# =============================================================================

def build_problem(cfg: Optional[Dict[str, Any]] = None) -> om.Problem:
    """
    Build and set up one current ADaPT MDA problem.

    The function does not run the model.  This makes it suitable for reuse by
    optimization, DOE and feasibility drivers that need to set values repeatedly.
    """
    c = normalize_config(cfg)

    # Shared operating-condition / property object.
    speed_for_opcond = c["cruise_speed_mps"] / 337.5
    phd = opCond(
        name="Cruise",
        T_env=c["T_env_K"],
        altitude=c["cruise_alt_m"],
        speed=speed_for_opcond,
        time=c["time"],
        RH=c["RH_pct"],
    )

    # Instantiate the Group with the required property object, then set the
    # options exposed by the current Group before setup().
    group = AirshipAnalysisGroup(phd=phd)

    required_group_options = {
        "power_source": c["power_source"],
        "landing_system": c["landing_system"],
        "airship_type": c["airship_type"],
        "num_steps": c["num_steps"],
        "enable_pressure_control": c["enable_pressure_control"],
        "use_prescribed_consumable_capacity": c["use_prescribed_consumable_capacity"],
    }
    for name, value in required_group_options.items():
        if not _set_group_option_if_available(group, name, value):
            raise RuntimeError(
                f"Current AirshipAnalysisGroup does not expose required option {name!r}."
            )

    # Optional Group-level method selections are applied when exposed by the
    # installed Group implementation.
    optional_group_options = {
        "ballonet_sizing_method": c["ballonet_sizing_method"],
        "tail_coefficient_method": c["tail_coefficient_method"],
        "propulsion_installation_mass_method": c["propulsion_installation_mass_method"],
    }
    for name, value in optional_group_options.items():
        _set_group_option_if_available(group, name, value)

    prob = om.Problem(model=group)
    prob.setup(check=False)

    n = c["num_steps"]

    # ------------------------------------------------------------------
    # Geometry / structure
    # ------------------------------------------------------------------
    _set_if_present(prob, "length", c["length_m"], units="m")
    _set_if_present(prob, "fineness_ratio", c["fineness_ratio"])
    _set_if_present(prob, "tail_volume_coeff_horizontal", c["tail_volume_coeff_horizontal"])
    _set_if_present(prob, "tail_volume_coeff_vertical", c["tail_volume_coeff_vertical"])
    _set_if_present(prob, "ballonet_fraction_prescribed", c["ballonet_fraction_prescribed"])
    _set_if_present(prob, "n_longitudinal_members", c["n_longitudinal_members"])
    _set_if_present(prob, "n_rings", c["n_rings"])
    _set_if_present(prob, "n_gas_cells", c["n_gas_cells"])

    # ------------------------------------------------------------------
    # Mission and atmosphere
    # ------------------------------------------------------------------
    _set_if_present(prob, "payload", c["payload_kg"], units="kg")
    _set_if_present(prob, "range", c["range_m"], units="m")
    _set_vector_if_present(prob, "cruise_altp", c["cruise_alt_m"], n, units="m")
    _set_vector_if_present(prob, "cruise_disa", c["cruise_disa_K"], n, units="K")
    _set_vector_if_present(prob, "cruise_speed", c["cruise_speed_mps"], n, units="m/s")
    _set_if_present(prob, "takeoff_altitude", c["takeoff_altitude_m"], units="m")
    _set_if_present(prob, "max_operating_altitude", c["max_operating_altitude_m"], units="m")
    _set_if_present(prob, "ascent_rate", c["ascent_rate_mps"], units="m/s")
    _set_if_present(prob, "descent_rate", c["descent_rate_mps"], units="m/s")

    # ------------------------------------------------------------------
    # Loading / capacity
    # ------------------------------------------------------------------
    _set_if_present(
        prob,
        "installed_consumable_capacity",
        c["installed_consumable_capacity_kg"],
        units="kg",
    )
    _set_if_present(prob, "ballast_mass", c["ballast_mass_kg"], units="kg")
    _set_if_present(prob, "n_crew", c["n_crew"])

    # ------------------------------------------------------------------
    # Mechanical propulsion
    # installed_shaft_power is TOTAL aircraft propulsor shaft power.
    # ------------------------------------------------------------------
    _set_if_present(prob, "installed_shaft_power", c["installed_shaft_power_W"], units="W")
    _set_if_present(prob, "n_engine", c["n_engine"])
    _set_if_present(prob, "propeller_efficiency", c["propeller_efficiency"])
    _set_if_present(prob, "gearbox_efficiency", c["gearbox_efficiency"])
    _set_if_present(prob, "propeller_rps", c["propeller_rps"], units="1/s")
    _set_if_present(prob, "propeller_blade_count", c["propeller_blade_count"])
    _set_if_present(prob, "propeller_power_coefficient", c["propeller_power_coefficient"])
    _set_if_present(prob, "ice_specific_power", c["ice_specific_power_Wkg"], units="W/kg")

    # ------------------------------------------------------------------
    # Aerodynamics / operations
    # ------------------------------------------------------------------
    _set_if_present(prob, "BR_takeoff", c["BR_takeoff"])
    _set_if_present(prob, "BR_landing", c["BR_landing"])
    _set_if_present(prob, "lift_coeff", c["lift_coeff"])
    _set_if_present(prob, "drag_coeff_zero", c["drag_coeff_zero"])
    _set_if_present(prob, "drag_due_to_lift_factor", c["drag_due_to_lift_factor"])
    _set_if_present(prob, "tailwind_speed", c["tailwind_speed_mps"], units="m/s")
    _set_if_present(prob, "thrust_vector_angle", c["thrust_vector_angle_deg"], units="deg")
    _set_if_present(prob, "rudder_deflection", c["rudder_deflection_deg"], units="deg")
    _set_if_present(prob, "cruise_strategy", c["cruise_strategy"])

    # ------------------------------------------------------------------
    # Fuel / reciprocating technology
    # ------------------------------------------------------------------
    _set_if_present(prob, "ice_thermal_efficiency", c["ice_thermal_efficiency"])
    _set_if_present(prob, "gasoline_lhv", c["gasoline_lhv_Jkg"], units="J/kg")
    _set_if_present(prob, "fuel_reserve_fraction", c["fuel_reserve_fraction"])

    # ------------------------------------------------------------------
    # Hydrogen and tank technology
    # ------------------------------------------------------------------
    if c["power_source"] in HYDROGEN_SOURCES:
        _set_if_present(
            prob,
            "fuel_onboard_mass",
            c["hydrogen_onboard_mass_kg"],
            units="kg",
        )
        _set_if_present(prob, "hydrogen_lhv", c["hydrogen_lhv_Jkg"], units="J/kg")
        _set_if_present(
            prob,
            "hydrogen_storage_density",
            c["hydrogen_storage_density_kgm3"],
            units="kg/m**3",
        )
        _set_if_present(prob, "tank_pressure", c["tank_pressure_Pa"], units="Pa")
        _set_if_present(prob, "tank_gravimetric_efficiency", c["tank_gravimetric_efficiency"])
        _set_if_present(
            prob,
            "tank_volume_mass_density",
            c["tank_volume_mass_density_kgm3"],
            units="kg/m**3",
        )
        _set_if_present(prob, "delivery_mass_fraction", c["delivery_mass_fraction"])
        _set_if_present(prob, "insulation_thickness", c["insulation_thickness_m"], units="m")
        _set_if_present(prob, "insulation_density", c["insulation_density_kgm3"], units="kg/m**3")

    # ------------------------------------------------------------------
    # Fuel-cell technology
    # ------------------------------------------------------------------
    if c["power_source"] in {"hydrogen_fuel_cell", "hydrogen_hybrid", "solar_hydrogen_hybrid"}:
        _set_if_present(
            prob,
            "fuel_cell_specific_power",
            c["fuel_cell_specific_power_Wkg"],
            units="W/kg",
        )
        _set_if_present(prob, "fuel_cell_efficiency", c["fuel_cell_efficiency"])

    # ------------------------------------------------------------------
    # Battery technology
    # ------------------------------------------------------------------
    if c["power_source"] in BATTERY_SOURCES:
        _set_if_present(
            prob,
            "battery_specific_energy",
            c["battery_specific_energy_Whkg"],
            units="W*h/kg",
        )
        _set_if_present(
            prob,
            "battery_volumetric_ed",
            c["battery_volumetric_ed_WhL"],
            units="W*h/L",
        )
        _set_if_present(prob, "battery_pack_voltage", c["battery_pack_voltage_V"], units="V")
        _set_if_present(
            prob,
            "battery_cell_voltage_nom",
            c["battery_cell_voltage_nom_V"],
            units="V",
        )
        _set_if_present(prob, "battery_efficiency", c["battery_efficiency"])
        _set_if_present(prob, "depth_of_discharge", c["depth_of_discharge"])
        _set_if_present(prob, "battery_packaging_factor", c["battery_packaging_factor"])

    # ------------------------------------------------------------------
    # Solar technology
    # ------------------------------------------------------------------
    if c["power_source"] in SOLAR_SOURCES:
        _set_if_present(prob, "solar_area", c["solar_area_m2"], units="m**2")
        _set_vector_if_present(
            prob,
            "solar_irradiance",
            c["solar_irradiance_Wm2"],
            n,
            units="W/m**2",
        )
        _set_if_present(prob, "solar_energy", c["solar_energy_MJ"], units="MJ")
        _set_if_present(prob, "solar_efficiency", c["solar_efficiency"])
        _set_if_present(prob, "pv_temp_coeff_fracK", c["pv_temp_coeff_fracK"], units="1/K")
        _set_if_present(
            prob,
            "pv_reference_temperature",
            c["pv_reference_temperature_K"],
            units="K",
        )
        _set_if_present(
            prob,
            "pv_areal_density",
            c["pv_areal_density_kgm2"],
            units="kg/m**2",
        )

    # ------------------------------------------------------------------
    # Hybrid controls
    # ------------------------------------------------------------------
    if c["power_source"] in {
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
        "conventional_battery_hybrid",
    }:
        _set_if_present(prob, "chi", c["chi"])
        _set_if_present(prob, "tau", c["tau"])

    # ------------------------------------------------------------------
    # Turbine / turboelectric technology
    # ------------------------------------------------------------------
    if c["power_source"] in TURBINE_SOURCES:
        _set_if_present(
            prob,
            "turboshaft_thermal_efficiency",
            c["turboshaft_thermal_efficiency"],
        )
        _set_if_present(
            prob,
            "turboshaft_specific_power",
            c["turboshaft_specific_power_Wkg"],
            units="W/kg",
        )

    if c["power_source"] == "turboelectric":
        _set_if_present(prob, "n_propulsor", c["n_propulsor"])
        _set_if_present(
            prob,
            "generator_specific_power",
            c["generator_specific_power_Wkg"],
            units="W/kg",
        )
        _set_if_present(prob, "generator_efficiency", c["generator_efficiency"])
        _set_if_present(
            prob,
            "motor_specific_power",
            c["motor_specific_power_Wkg"],
            units="W/kg",
        )
        _set_if_present(prob, "motor_efficiency", c["motor_efficiency"])
        _set_if_present(prob, "inverter_efficiency", c["inverter_efficiency"])

    return prob


# =============================================================================
# 6. Result collection
# =============================================================================

CONSTRAINT_NAMES = [
    "power_constraint",
    "energy_constraint",
    "energy_constraint_primary",
    "energy_constraint_bat",
    "buoyancy_constraint",
    "lift_constraint",
    "ground_constraint",
    "landing_constraint",
    "ballast_constraint",
    "landing_BR_constraint",
]


def collect_constraint_table(prob: om.Problem) -> pd.DataFrame:
    """Return current ADaPT constraints using the g <= 0 convention."""
    rows = []
    for name in CONSTRAINT_NAMES:
        try:
            values = _array(prob, name)
        except Exception:
            continue
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            continue
        max_value = float(np.max(finite))
        rows.append(
            {
                "Name": name,
                "Max Value": max_value,
                "Feasible": bool(max_value <= 0.0),
                "N Values": int(finite.size),
            }
        )
    return pd.DataFrame(rows, columns=["Name", "Max Value", "Feasible", "N Values"])


def collect_mass_table(prob: om.Problem, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Collect the active current Weight-model mass breakdown for the UI."""
    candidates = [
        ("Envelope", "envelope_mass"),
        ("Ballonet", "ballonet_mass"),
        ("Suspension curtain", "curtain_mass"),
        ("Framework", "framework_mass"),
        ("Gondola", "gondola_mass"),
        ("Tail / fins", "fin_mass"),
        ("Landing system", "landing_system_mass"),
        ("Propulsion system", "propulsion_mass"),
        ("Power system", "power_system_mass"),
        ("Hydrogen tank", "tank_mass"),
        ("Conventional fuel-tank hardware", "fuel_tank_mass"),
        ("Pressure system", "pressure_system_mass"),
        ("Vehicle management system", "vms_mass"),
        ("Crew", "crew_mass"),
        ("Miscellaneous", "miscellaneous_mass"),
        ("Weight margin", "weight_margin_mass"),
        ("Operating empty weight", "owe"),
        ("Payload", "payload"),
        ("Installed consumable", "installed_consumable_mass"),
        ("Ballast", "ballast_mass"),
        ("MTOW", "mtow"),
        ("Helium mass (reported separately)", "he_max_mass"),
    ]

    rows = []
    for label, name in candidates:
        value = _get(prob, name, "kg", default=np.nan)
        if np.isfinite(value):
            rows.append([label, value])

    # Payload is a promoted design input and should always be visible in the UI.
    if not any(row[0] == "Payload" for row in rows):
        rows.append(["Payload", float(cfg["payload_kg"])])

    return pd.DataFrame(rows, columns=["Item", "Mass [kg]"])


def collect_results(prob: om.Problem, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect one solved ADaPT problem into UI-ready Python/Pandas objects."""
    c = normalize_config(cfg)

    required_power_kW = _max_available(
        prob,
        ["required_shaft_power", "shaft_power", "required_power"],
        units="kW",
    )

    installed_power_kW = _get(prob, "installed_shaft_power", "kW")
    rated_power_kW = _first_available(
        prob,
        ["rated_shaft_power", "takeoff_shaft_power"],
        units="kW",
    )

    installed_consumable_kg = _first_available(
        prob,
        ["installed_consumable_mass", "installed_consumable_capacity"],
        units="kg",
        default=0.0,
    )
    required_consumable_kg = _first_available(
        prob,
        ["required_consumable_mass", "fuel_mass", "hydrogen_mass"],
        units="kg",
        default=np.nan,
    )

    battery_mass_kg = _first_available(
        prob,
        ["battery_mass", "battery_mass_required"],
        units="kg",
        default=0.0,
    )

    tank_mass_kg = _get(prob, "tank_mass", "kg", default=0.0)

    scalars = {
        "power_source": c["power_source"],
        "airship_type": c["airship_type"],
        "mtow_kg": _get(prob, "mtow", "kg"),
        "owe_kg": _get(prob, "owe", "kg"),
        "payload_kg": _get(prob, "payload", "kg", default=c["payload_kg"]),
        "required_power_kW": required_power_kW,
        "installed_power_kW": installed_power_kW,
        "rated_power_kW": rated_power_kW,
        "power_margin_kW": (
            installed_power_kW - required_power_kW
            if np.isfinite(installed_power_kW) and np.isfinite(required_power_kW)
            else np.nan
        ),
        "installed_consumable_kg": installed_consumable_kg,
        "required_consumable_kg": required_consumable_kg,
        "battery_mass_kg": battery_mass_kg,
        "tank_mass_kg": tank_mass_kg,
        "ground_roll_m": _get(prob, "takeoff_ground_roll", "m", default=_get(prob, "ground_roll_distance", "m")),
        "takeoff_distance_m": _get(prob, "takeoff_distance", "m"),
        "landing_field_length_m": _get(prob, "landing_field_length", "m"),
        "mission_duration_hr": _get(prob, "mission_duration", "h"),
        "mission_energy_MJ": _get(prob, "mission_energy_required", "MJ"),
        "BR_takeoff": _get(prob, "BR_takeoff"),
        "BR_landing_implied": _get(prob, "BR_landing_implied"),
        "mass_balance_error_kg": _get(prob, "mass_balance_error", "kg"),
    }

    outputs = {
        # Geometry
        "length_m": _get(prob, "length", "m"),
        "diameter_m": _first_available(prob, ["max_diameter", "geometry.max_diameter"], "m"),
        "fineness_ratio": _get(prob, "fineness_ratio"),
        "gross_volume_m3": _first_available(prob, ["gross_volume", "geometry.gross_volume"], "m**3"),
        "wetted_area_m2": _first_available(prob, ["wetted_surface_area", "geometry.wetted_surface_area"], "m**2"),
        "aero_reference_area_m2": _first_available(prob, ["ref_area_AeroCoeffs", "geometry.ref_area_AeroCoeffs"], "m**2"),
        "fin_wetted_area_m2": _first_available(prob, ["fin_total_wetted_area", "geometry.fin_total_wetted_area"], "m**2"),
        "ballonet_volume_m3": _get(prob, "ballonet_volume", "m**3"),
        "lifting_gas_volume_takeoff_m3": _first_available(
            prob,
            ["lifting_gas_volume_takeoff", "lifting_gas_volume_takeoff_used"],
            "m**3",
        ),

        # Weight / aerostatics
        "helium_mass_kg": _get(prob, "he_max_mass", "kg"),
        "air_max_volume_m3": _get(prob, "air_max_volume", "m**3"),
        "structure_mass_kg": _get(prob, "structure_mass", "kg"),
        "installed_system_mass_kg": _get(prob, "installed_system_mass", "kg"),

        # Performance
        "drag_cruise_N": _get_max(prob, "drag_cruise", "N"),
        "thrust_cruise_N": _get_max(prob, "thrust_cruise", "N"),
        "lift_coefficient_cruise_max_abs": (
            max(
                abs(_get_max(prob, "lift_coefficient_cruise", default=np.nan)),
                abs(_get_min(prob, "lift_coefficient_cruise", default=np.nan)),
            )
            if np.isfinite(_get_max(prob, "lift_coefficient_cruise", default=np.nan))
            else np.nan
        ),
        "buoyant_lift_required_takeoff_N": _get(prob, "buoyant_lift_required_takeoff", "N"),
        "buoyant_lift_available_takeoff_N": _get(prob, "buoyant_lift_available_takeoff", "N"),
        "takeoff_speed_mps": _get(prob, "takeoff_speed_calculated", "m/s"),
        "takeoff_climb_gradient": _get(prob, "takeoff_climb_gradient"),
        "roc_mps": _get(prob, "roc", "m/s"),
        "rod_mps": _get(prob, "rod", "m/s"),
        "turn_radius_m": _get(prob, "turn_radius", "m"),

        # Propulsion / energy
        "propeller_diameter_m": _get(prob, "propeller_diameter", "m"),
        "propulsion_mass_kg": _get(prob, "propulsion_mass", "kg"),
        "power_system_mass_kg": _get(prob, "power_system_mass", "kg"),
        "power_system_volume_m3": _get(prob, "power_system_volume", "m**3"),
        "battery_volume_m3": _get(prob, "battery_volume", "m**3"),
        "tank_volume_m3": _get(prob, "tank_volume", "m**3"),
    }

    df_constraints = collect_constraint_table(prob)
    df_mass = collect_mass_table(prob, c)

    return {
        "scalars": scalars,
        "outputs": outputs,
        "df_constraints": df_constraints,
        "df_mass": df_mass,
    }


# =============================================================================
# 7. UI visualization
# =============================================================================

def make_profile_figure(
    length_m: float,
    diameter_m: float,
    title: str = "Airship profile (ellipse proxy)",
    figsize: Tuple[float, float] = FIGSIZE_PROFILE_DEFAULT,
) -> plt.Figure:
    """Return a lightweight side/top-view profile figure for the UI."""
    L = max(float(length_m), 1.0e-6)
    D = max(float(diameter_m), 1.0e-6)

    t = np.linspace(0.0, 2.0 * np.pi, 600)
    x = 0.5 * L * np.cos(t)
    y = 0.5 * D * np.sin(t)

    fig = plt.figure(figsize=figsize)

    ax1 = fig.add_subplot(2, 1, 1)
    ax1.plot(x, y, linewidth=1.6)
    ax1.set_aspect("equal", "box")
    ax1.set_title(title + " — side view")
    ax1.set_xlabel("x [m]")
    ax1.set_ylabel("radius [m]")
    ax1.grid(True, alpha=0.3)

    ax2 = fig.add_subplot(2, 1, 2)
    ax2.plot(x, y, linewidth=1.6)
    ax2.set_aspect("equal", "box")
    ax2.set_title(title + " — top view")
    ax2.set_xlabel("x [m]")
    ax2.set_ylabel("radius [m]")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


# =============================================================================
# 8. N2 / XDSM reporting
# =============================================================================

def generate_reports(
    prob: om.Problem,
    out_dir: str | Path,
    base_name: str = "Airship_Sizing",
    make_n2: bool = True,
    make_xdsm: bool = True,
    xdsm_format: str = "pdf",
) -> Dict[str, Any]:
    """Generate optional OpenMDAO N2 and XDSM artifacts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {
        "n2_path": None,
        "n2_html": None,
        "n2_ok": False,
        "xdsm_path": None,
        "xdsm_ok": False,
    }

    if make_n2:
        n2_path = out_dir / f"{base_name}_n2.html"
        try:
            om.n2(prob, outfile=str(n2_path), show_browser=False)
            results["n2_path"] = str(n2_path)
            results["n2_ok"] = n2_path.exists()
            if n2_path.exists():
                results["n2_html"] = n2_path.read_text(
                    encoding="utf-8", errors="ignore"
                )
        except Exception as exc:
            results["n2_html"] = f"<pre>N2 generation failed: {exc}</pre>"

    if make_xdsm and _HAS_OMXDSM:
        try:
            stem = out_dir / f"{base_name}_xdsm"
            requested = str(xdsm_format).lower()
            formats = [requested]
            if requested == "pdf":
                formats.append("tex")

            for fmt in formats:
                try:
                    write_xdsm(
                        prob,
                        filename=str(stem),
                        out_format=fmt,
                        show_browser=False,
                        quiet=True,
                        output_side="left",
                        include_indepvarcomps=True,
                        class_names=False,
                    )
                    candidate = stem.with_suffix(f".{fmt}")
                    if candidate.exists():
                        results["xdsm_path"] = str(candidate)
                        results["xdsm_ok"] = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

    return results


# =============================================================================
# 9. Canonical single-run API
# =============================================================================

def run_mda_once(
    cfg: Optional[Dict[str, Any]] = None,
    make_figure: bool = True,
    make_reports: bool = False,
    reports_dir: Optional[str | Path] = None,
    reports_basename: str = "Airship_Sizing",
) -> Dict[str, Any]:
    """
    Run one fully coupled ADaPT MDA case and return UI-ready results.

    Returns
    -------
    dict
        ``config``
            Canonical normalized configuration used for the run.
        ``scalars``
            Primary values for UI cards/summary fields.
        ``outputs``
            Detailed geometry, weight, performance and propulsion outputs.
        ``df_constraints``
            Constraint table using g <= 0 as the feasibility convention.
        ``df_mass``
            Current component-level mass breakdown.
        ``fig_profile``
            Optional Matplotlib figure.
        ``reports``
            Optional N2/XDSM artifact information.
    """
    c = normalize_config(cfg)
    prob = build_problem(c)

    try:
        prob.run_model()

        result = collect_results(prob, c)

        fig_profile = None
        if make_figure:
            L = result["outputs"]["length_m"]
            D = result["outputs"]["diameter_m"]
            if np.isfinite(L) and np.isfinite(D) and L > 0.0 and D > 0.0:
                fig_profile = make_profile_figure(L, D)

        reports = None
        if make_reports:
            if reports_dir is None:
                reports_dir = Path.cwd() / "app_out" / "reports"
            reports = generate_reports(
                prob,
                out_dir=reports_dir,
                base_name=reports_basename,
                make_n2=True,
                make_xdsm=True,
                xdsm_format="pdf",
            )

        result.update(
            {
                "config": c,
                "fig_profile": fig_profile,
                "reports": reports,
            }
        )
        return result

    finally:
        prob.cleanup()


# =============================================================================
# 10. Script entry point
# =============================================================================

if __name__ == "__main__":
    # A-170-like conventional reference case for a quick installation check.
    # installed_shaft_power_W is TOTAL aircraft shaft power.
    cfg0 = {
        "power_source": "conventional_reciprocating",
        "landing_system": "conventional",
        "airship_type": "non-rigid",
        "use_prescribed_consumable_capacity": True,
        "ballonet_sizing_method": "pressure_altitude",
        "tail_coefficient_method": "user",
        "propulsion_installation_mass_method": "generic",
        "length_m": 53.4,
        "fineness_ratio": 4.0,
        "tail_volume_coeff_horizontal": 0.066,
        "tail_volume_coeff_vertical": 0.059,
        "payload_kg": 1123.0,
        "range_m": 1_342_100.0,
        "cruise_speed_mps": 19.5,
        "cruise_alt_m": 914.0,
        "cruise_disa_K": 0.0,
        "T_env_K": 281.65,
        "RH_pct": 70.0,
        "installed_consumable_capacity_kg": 599.0,
        "n_crew": 1,
        "installed_shaft_power_W": 268_000.0,
        "n_engine": 2,
        "propeller_efficiency": 0.75,
        "BR_takeoff": 0.83,
        "BR_landing": 0.90,
        "lift_coeff": 0.15,
        "drag_coeff_zero": 0.03542,
        "drag_due_to_lift_factor": 0.869,
    }

    result = run_mda_once(
        cfg0,
        make_figure=False,
        make_reports=False,
    )

    print("\n=== ADaPT MDA summary ===")
    for key, value in result["scalars"].items():
        print(f"{key:28s}: {value}")

    print("\n=== Constraints (g <= 0 feasible) ===")
    print(result["df_constraints"].to_string(index=False))

    print("\n=== Mass breakdown ===")
    print(result["df_mass"].to_string(index=False))
