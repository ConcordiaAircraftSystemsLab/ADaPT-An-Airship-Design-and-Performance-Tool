# -*- coding: utf-8 -*-
"""
Shared utilities for the two explicit ADAPT operating modes.

This module is intentionally not a user-facing run file. The two user-facing
files are:

    run_adapt_analysis.py
    run_adapt_sizing.py

Important:
- AirshipAnalysisGroup already contains AirshipIndepVariables.
- Do not add another promoted IndepVarComp.
- ADAPT feasibility convention is constraint <= 0.
"""

from __future__ import annotations

import os
import sys
import time
import warnings
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Sequence
import csv
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import openmdao.api as om

# =============================================================================
# ADAPT package imports
# =============================================================================
#
# Current repository structure:
#
#   project/
#       adapt/
#           AirshipAnalysisGroup.py
#           operatingConditions.py
#           ...
#
#       studies/
#           adapt_mode_common.py
#           run_sizing.py
#
# All authoritative aircraft physics comes from the adapt package.
# Do NOT add adapt/ itself to sys.path because that can load the same
# classes under two different module names.
# =============================================================================

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from adapt.AirshipAnalysisGroup import AirshipAnalysisGroup
from adapt.operatingConditions import opCond


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


def scalar(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    """Return one scalar OpenMDAO value or default when unavailable."""
    try:
        value = prob.get_val(name, units=units)
        return float(np.asarray(value, dtype=float).reshape(-1)[0])
    except Exception:
        return float(default)


def max_value(
    prob: om.Problem,
    name: str,
    units: Optional[str] = None,
    default: float = np.nan,
) -> float:
    """Return the maximum entry of a scalar/vector output."""
    try:
        value = prob.get_val(name, units=units)
        arr = np.asarray(value, dtype=float).reshape(-1)
        return float(np.nanmax(arr))
    except Exception:
        return float(default)


def set_if_present(
    prob: om.Problem,
    name: str,
    value: Any,
    units: Optional[str] = None,
) -> bool:
    """Set an input/output when it exists; return True on success."""
    try:
        if units is None:
            prob.set_val(name, value)
        else:
            prob.set_val(name, value, units=units)
        return True
    except Exception:
        return False


def build_problem(
    *,
    power_source: str,
    num_steps: int = 1,
    landing_system: str = "conventional",
    use_prescribed_consumable_capacity: bool = False,
    setup_check: bool = False,
    formulation: str = "mdf",
) -> om.Problem:
    """
    Build an ADAPT OpenMDAO problem.

    Parameters
    ----------
    formulation
        Retained for compatibility with existing study/UI scripts. Both
        ``"mdf"`` and ``"direct"`` use the authoritative
        :class:`AirshipAnalysisGroup` in the current ADAPT repository. Any
        multidisciplinary coupling/convergence is therefore handled by that
        model's own configured OpenMDAO structure/solvers.
    """
    power_source = POWER_SOURCE_ALIASES.get(
        power_source,
        power_source,
    )

    if power_source not in SUPPORTED_POWER_SOURCES:
        raise ValueError(
            f"Unsupported power_source={power_source!r}. "
            f"Choose one of {sorted(SUPPORTED_POWER_SOURCES)}."
        )

    if formulation not in {"mdf", "direct"}:
        raise ValueError(
            "formulation must be either 'mdf' or 'direct'."
        )

    operating_point = opCond(
        name="Cruise",
        T_env=281.65,
        altitude=914.0,
        speed=19.5 / 337.5,
        time="day",
        RH=70.0,
    )

    prob = om.Problem()

    model_options = dict(
        phd=operating_point,
        power_source=power_source,
        landing_system=landing_system,
        num_steps=num_steps,
        use_prescribed_consumable_capacity=(
            use_prescribed_consumable_capacity
        ),
    )

    # AirshipAnalysisGroup is the authoritative coupled ADAPT model.
    #
    # The current repository no longer defines the legacy ADAPTMDFGroup.
    # Keep the formulation argument for backward compatibility with existing
    # study/UI scripts, but evaluate both accepted modes with the same
    # authoritative coupled OpenMDAO group.
    prob.model = AirshipAnalysisGroup(**model_options)

    prob.setup(check=setup_check)

    return prob


def apply_mission(
    prob: om.Problem,
    *,
    payload_kg: float,
    range_km: float,
    cruise_speed_ms: float,
    cruise_altitude_m: float,
    cruise_disa_K: float,
    num_steps: int,
) -> None:
    """Apply top-level mission requirements."""
    prob.set_val("payload", payload_kg, units="kg")
    prob.set_val("range", range_km * 1000.0, units="m")
    prob.set_val(
        "cruise_speed",
        np.full(num_steps, cruise_speed_ms),
        units="m/s",
    )
    prob.set_val(
        "cruise_altp",
        np.full(num_steps, cruise_altitude_m),
        units="m",
    )
    prob.set_val(
        "cruise_disa",
        np.full(num_steps, cruise_disa_K),
        units="K",
    )


def apply_common_configuration(
    prob: om.Problem,
    *,
    n_crew: float,
    n_engine: float,
    propeller_efficiency: float,
    lift_coeff: float,
    drag_due_to_lift_factor: float,
    BR_landing: float,
    ballast_mass_kg: float,
) -> None:
    """Apply common configuration/technology assumptions."""
    set_if_present(prob, "n_crew", n_crew)
    set_if_present(prob, "n_engine", n_engine)
    set_if_present(prob, "propeller_efficiency", propeller_efficiency)
    set_if_present(prob, "lift_coeff", lift_coeff)
    set_if_present(prob, "drag_due_to_lift_factor", drag_due_to_lift_factor)
    set_if_present(prob, "BR_landing", BR_landing)
    set_if_present(prob, "ballast_mass", ballast_mass_kg, units="kg")


def apply_architecture_defaults(
    prob: om.Problem,
    *,
    power_source: str,
    num_steps: int,
    battery_specific_energy_Whkg: float = 350.0,
    solar_area_m2: float = 300.0,
    solar_irradiance_Wm2: float = 600.0,
) -> None:
    """Apply only architecture-specific assumptions that are active."""
    power_source = POWER_SOURCE_ALIASES.get(power_source, power_source)

    if power_source in {
        "battery_only",
        "solar_battery",
        "solar-RFC",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
        "conventional_battery_hybrid",
    }:
        set_if_present(
            prob,
            "battery_specific_energy",
            battery_specific_energy_Whkg,
            units="W*h/kg",
        )

    if power_source in {
        "solar_battery",
        "solar-RFC",
        "solar_hydrogen_hybrid",
    }:
        set_if_present(prob, "solar_area", solar_area_m2, units="m**2")
        set_if_present(
            prob,
            "solar_irradiance",
            np.full(num_steps, solar_irradiance_Wm2),
            units="W/m**2",
        )


def collect_summary(prob: om.Problem) -> dict[str, float]:
    """Collect the most useful user-facing results."""
    fields = {
        "length_m": ("length", "m"),
        "fineness_ratio": ("fineness_ratio", None),
        "maximum_diameter_m": ("maximum_diameter", "m"),
        "gross_volume_m3": ("gross_volume", "m**3"),
        "wetted_area_m2": ("wetted_surface_area", "m**2"),
        "mtow_kg": ("mtow", "kg"),
        "owe_kg": ("owe", "kg"),
        "payload_kg": ("payload", "kg"),
        "installed_shaft_power_kW": ("installed_shaft_power", "kW"),
        "required_shaft_power_kW": ("required_shaft_power", "kW"),
        "consumable_mass_kg": ("installed_consumable_mass", "kg"),
        "battery_mass_kg": ("battery_mass", "kg"),
        "tank_mass_kg": ("tank_mass", "kg"),
        "power_system_mass_kg": ("power_system_mass", "kg"),
        "propulsion_mass_kg": ("propulsion_mass", "kg"),
        "BR_takeoff": ("BR_takeoff", None),
        "tail_volume_coeff_horizontal": ("tail_volume_coeff_horizontal", None),
        "tail_volume_coeff_vertical": ("tail_volume_coeff_vertical", None),
        "ground_roll_m": ("ground_roll_distance", "m"),
    }
    return {
        label: scalar(prob, variable, units=units)
        for label, (variable, units) in fields.items()
    }


CONSTRAINT_SPECS = (
    ("buoyancy_constraint", None),
    ("power_constraint", "W"),
    ("energy_constraint", None),
    ("lift_constraint", None),
    ("volume_constraint", None),
    ("ground_constraint", None),
)


def collect_constraints(prob: om.Problem) -> dict[str, float]:
    """
    Return available model constraints.

    Missing constraints are reported as NaN and are not automatically treated
    as failures in the user-facing report.
    """
    return {
        name: max_value(prob, name, units=units, default=np.nan)
        for name, units in CONSTRAINT_SPECS
    }


def constraint_status(value: float, tolerance: float = 1.0e-8) -> str:
    if not np.isfinite(value):
        return "N/A"
    return "PASS" if value <= tolerance else "FAIL"


def print_summary(
    prob: om.Problem,
    *,
    title: str,
    mode: str,
) -> None:
    """Print a compact, non-MDAO-expert-friendly report."""
    summary = collect_summary(prob)
    constraints = collect_constraints(prob)

    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    print(f"Operating mode: {mode.upper()}")
    print("\nFinal airship design")
    print("-" * 78)

    display_order = [
        ("Hull length", "length_m", "m"),
        ("Fineness ratio", "fineness_ratio", "-"),
        ("Maximum diameter", "maximum_diameter_m", "m"),
        ("Gross volume", "gross_volume_m3", "m³"),
        ("MTOW", "mtow_kg", "kg"),
        ("Operating empty weight", "owe_kg", "kg"),
        ("Payload", "payload_kg", "kg"),
        ("Installed shaft power", "installed_shaft_power_kW", "kW"),
        ("Required shaft power", "required_shaft_power_kW", "kW"),
        ("Mission consumable mass", "consumable_mass_kg", "kg"),
        ("Battery mass", "battery_mass_kg", "kg"),
        ("Tank mass", "tank_mass_kg", "kg"),
        ("Take-off buoyancy ratio", "BR_takeoff", "-"),
        ("Horizontal tail-volume coefficient", "tail_volume_coeff_horizontal", "-"),
        ("Vertical tail-volume coefficient", "tail_volume_coeff_vertical", "-"),
    ]

    for label, key, unit in display_order:
        value = summary[key]
        if np.isfinite(value):
            print(f"{label:<38} {value:>14.4f} {unit}")

    print("\nFeasibility checks (ADAPT convention: value <= 0 is feasible)")
    print("-" * 78)
    for name, value in constraints.items():
        if np.isfinite(value):
            print(
                f"{name:<38} {value:>14.6g}   "
                f"{constraint_status(value)}"
            )

    finite_constraints = [v for v in constraints.values() if np.isfinite(v)]
    overall = all(v <= 1.0e-8 for v in finite_constraints)
    print("-" * 78)
    print(f"Overall available-constraint status: {'PASS' if overall else 'FAIL'}")
    print("=" * 78)


def export_results(
    prob: om.Problem,
    *,
    output_csv: Path,
    mode: str,
    power_source: str,
) -> Path:
    """Export a simple one-row design summary plus constraint values."""
    output_csv = Path(output_csv).resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "mode": mode,
        "power_source": power_source,
        **collect_summary(prob),
        **collect_constraints(prob),
    }

    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    return output_csv

def generate_xdsm(
    prob: om.Problem,
    *,
    filename: str,
    output_dir: Path,
    out_format: str = "html",
    show_browser: bool = False,
    include_indepvarcomps: bool = True,
    class_names: bool = False,
    recurse: bool = True,
) -> Optional[Path]:
    """
    Generate an XDSM representation of the ADAPT OpenMDAO model.

    Parameters
    ----------
    prob
        Fully set up OpenMDAO Problem.
    filename
        File stem without extension.
    output_dir
        Directory in which XDSM files are written.
    out_format
        Usually "html", "pdf", "tex", or "json".

        "html" is the most portable option.
        "pdf" normally requires a working LaTeX installation.
    show_browser
        Open the generated diagram automatically when supported.
    include_indepvarcomps
        Include the internal AirshipIndepVariables block.
    class_names
        Show Python class names rather than subsystem names.

    Returns
    -------
    pathlib.Path or None
        Expected principal output path, or None when generation fails.

    Notes
    -----
    In sizing mode this function describes the internal OpenMDAO model.
    An external pymoo optimization loop is not represented automatically.
    """
    try:
        from omxdsm import write_xdsm
    except ImportError:
        print(
            "\nXDSM generation skipped: omxdsm is not installed.\n"
            "Install it with:\n"
            "    pip install omxdsm"
        )
        return None

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    file_stem = output_dir / filename

    try:
        write_xdsm(
            prob,
            filename=str(file_stem),
            out_format=out_format,
            show_browser=show_browser,
            quiet=False,
            output_side="left",
            include_indepvarcomps=include_indepvarcomps,
            class_names=class_names,
            recurse=recurse,
        )

        expected_path = file_stem.with_suffix(f".{out_format}")

        print("\nXDSM generation completed.")
        print(f"XDSM file stem: {file_stem}")
        print(f"Requested format: {out_format}")

        return expected_path

    except Exception as exc:
        print("\nXDSM generation failed.")
        print(f"Reason: {exc}")

        if out_format.lower() == "pdf":
            print(
                "\nPDF generation normally requires a working LaTeX "
                "installation. Try out_format='html' first."
            )

        return None



def generate_manual_mdf_xdsm(
    *,
    filename: str,
    output_dir: Path,
    mode: str,
    power_source: str,
    cleanup: bool = False,
    write_system_specs: bool = False,
) -> Optional[Path]:
    """
    Generate a manually structured MDF architecture XDSM using pyXDSM.

    This figure explicitly shows:
    - the external execution or sizing driver;
    - the central MDA converger;
    - the principal ADAPT disciplines;
    - the multidisciplinary feedback loop.

    Parameters
    ----------
    filename
        Output file stem without extension.

    output_dir
        Directory in which the PDF and LaTeX files are written.

    mode
        Either ``"analysis"`` or ``"sizing"``.

    power_source
        Active ADAPT propulsion/power architecture.

    cleanup
        Passed directly to pyXDSM. Using False preserves the generated
        LaTeX files and is recommended for debugging.

    write_system_specs
        When True, also generates a system-specification file.

    Returns
    -------
    pathlib.Path or None
        Expected PDF path when generation succeeds, otherwise None.
    """
    try:
        from pyxdsm.XDSM import (
            XDSM,
            OPT,
            SOLVER,
            FUNC,
            LEFT,
            RIGHT,
        )
    except ImportError:
        print(
            "\nManual MDF XDSM skipped: pyXDSM is not installed.\n"
            "Install it with:\n"
            "    pip install pyxdsm"
        )
        return None

    mode_key = str(mode).strip().lower()

    if mode_key not in {"analysis", "sizing"}:
        raise ValueError(
            "Manual MDF XDSM mode must be either 'analysis' or 'sizing'."
        )

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    file_stem = output_dir / filename

    x = XDSM()

    # =====================================================================
    # SYSTEM BLOCKS
    # =====================================================================

    if mode_key == "sizing":
        x.add_system(
            "Driver",
            OPT,
            (
                r"\text{\huge Sizing}",
                r"\text{\huge Driver}",
            ),
        )
    else:
        x.add_system(
            "Driver",
            OPT,
            (
                r"\text{\huge Analysis}",
                r"\text{\huge Execution}",
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

    # =====================================================================
    # PROCESS LINE
    # =====================================================================

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

    # =====================================================================
    # DRIVER TO MDA
    # =====================================================================

    if mode_key == "sizing":
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
    else:
        x.connect(
            "Driver",
            "Converger",
            [
                r"\text{\huge Prescribed}",
                r"\text{\huge Airship Design,}",
                r"\text{\huge Mission}",
                r"\text{\huge Requirements,}",
                r"\text{\huge Architecture}",
            ],
            label_width=1,
        )

    # =====================================================================
    # CONVERGER CONTROL
    # =====================================================================

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

    # =====================================================================
    # DISCIPLINARY CONNECTIONS
    # =====================================================================

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
        "Atmos",
        "Geometry",
        [
            r"\text{\huge Ambient}",
            r"\text{\huge Conditions}",
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

    # =====================================================================
    # MDA OUTPUTS TO DRIVER
    # =====================================================================

    if mode_key == "sizing":
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
    else:
        x.connect(
            "Converger",
            "Driver",
            [
                r"\text{\huge Performance,}",
                r"\text{\huge Masses,}",
                r"\text{\huge Constraints,}",
                r"\text{\huge Feasibility}",
            ],
            label_width=1,
        )

    # =====================================================================
    # EXTERNAL INPUTS
    # =====================================================================

    if mode_key == "sizing":
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
    else:
        x.add_input(
            "Driver",
            [
                r"\text{\huge Mission Requirements}",
                r"\text{\huge -Payload}",
                r"\text{\huge -Range}",
                r"\text{\huge -Cruise Speed}",
                r"\text{\huge -Cruise Altitude}",
                r"\text{\huge Prescribed Design}",
                r"\text{\huge -Hull Length}",
                r"\text{\huge -Fineness Ratio}",
                r"\text{\huge -Installed Power}",
                r"\text{\huge -Buoyancy Ratio}",
            ],
            stack=True,
        )

    x.add_input(
        "Power",
        [
            r"\text{\huge Propulsion}",
            r"\text{\huge Architecture}",
            rf"\text{{\huge {power_source}}}",
        ],
        stack=True,
    )

    # =====================================================================
    # WRITE FILES
    # =====================================================================

    try:
        x.write(
            str(file_stem),
            cleanup=cleanup,
        )

        if write_system_specs:
            specs_stem = output_dir / f"{filename}_system_specs"
            x.write_sys_specs(str(specs_stem))

        pdf_path = file_stem.with_suffix(".pdf")

        print("\nManual MDF XDSM generation completed.")
        print(f"Mode: {mode_key}")
        print(f"Power source: {power_source}")
        print(f"File stem: {file_stem}")

        return pdf_path

    except Exception as exc:
        print("\nManual MDF XDSM generation failed.")
        print(f"Reason: {type(exc).__name__}: {exc}")
        print(
            "The generated .tex file has been preserved when cleanup=False."
        )
        return None