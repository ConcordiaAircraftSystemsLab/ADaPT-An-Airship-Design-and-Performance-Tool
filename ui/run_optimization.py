# -*- coding: utf-8 -*-
"""
ADaPT Streamlit adapter for multidisciplinary optimization.

The authoritative optimization implementation is:
    adapt.run_Optimization

This wrapper contains no aircraft sizing or subsystem physics. It only:
    - translates Streamlit settings into the optimization backend API,
    - manages the output directory,
    - converts the structured backend result into UI-ready tables,
    - returns paths/results for visualization and download.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

import adapt.run_Optimization as opt


DEFAULT_OUTPUT_DIR = Path.cwd() / "app_out" / "optimization"


# =============================================================================
# Helpers
# =============================================================================

def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _scalar(
    mapping: Dict[str, Any],
    key: str,
    default: float = np.nan,
) -> float:
    value = mapping.get(key, default)

    try:
        arr = np.asarray(value, dtype=float).reshape(-1)
        return float(arr[0]) if arr.size else float(default)
    except Exception:
        return float(default)


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None

    value = float(value)

    if not np.isfinite(value):
        return None

    return value


def _build_constraints_table(
    result: Dict[str, Any],
    ground_roll_max_m: Optional[float],
    power_margin_cap_W: Optional[float],
    max_envelope_volume_m3: Optional[float],
) -> pd.DataFrame:
    """
    Build a UI table using the current ADaPT convention:

        g <= 0  -> feasible
        g >  0  -> violated
    """

    prob = result["problem"]

    records = []

    # -------------------------------------------------------------------------
    # Native model constraints
    # -------------------------------------------------------------------------

    for name in result.get("active_model_constraints", ()):

        value = opt._max_value(
            prob,
            name,
            default=np.nan,
        )

        records.append(
            {
                "Constraint": name,
                "g": value,
                "Convention": "g <= 0",
                "Feasible": (
                    bool(value <= 0.0)
                    if _finite(value)
                    else False
                ),
            }
        )

    # -------------------------------------------------------------------------
    # Additional optimization constraints
    # -------------------------------------------------------------------------

    ground_roll = opt._first_available(
        prob,
        (
            "takeoff_ground_roll",
            "ground_roll_distance",
        ),
        units="m",
        default=np.nan,
    )

    if ground_roll_max_m is not None:

        g_ground = (
            ground_roll - ground_roll_max_m
            if _finite(ground_roll)
            else np.nan
        )

        records.append(
            {
                "Constraint": (
                    f"Ground roll <= "
                    f"{ground_roll_max_m:.1f} m"
                ),
                "g": g_ground,
                "Convention": "g <= 0",
                "Feasible": (
                    bool(g_ground <= 0.0)
                    if _finite(g_ground)
                    else False
                ),
            }
        )

    required_W = opt._required_power_W(prob)
    installed_W = opt._installed_power_W(prob)

    if (
        _finite(required_W)
        and _finite(installed_W)
    ):
        power_margin_W = (
            installed_W - required_W
        )
    else:
        power_margin_W = np.nan

    if power_margin_cap_W is not None:

        g_margin = (
            power_margin_W - power_margin_cap_W
            if _finite(power_margin_W)
            else np.nan
        )

        records.append(
            {
                "Constraint": (
                    "Installed power margin <= "
                    f"{power_margin_cap_W / 1000.0:.1f} kW"
                ),
                "g": g_margin,
                "Convention": "g <= 0",
                "Feasible": (
                    bool(g_margin <= 0.0)
                    if _finite(g_margin)
                    else False
                ),
            }
        )

    if max_envelope_volume_m3 is not None:

        volume = opt._first_available(
            prob,
            (
                "gross_volume",
                "geometry.gross_volume",
            ),
            units="m**3",
            default=np.nan,
        )

        g_volume = (
            volume - max_envelope_volume_m3
            if _finite(volume)
            else np.nan
        )

        records.append(
            {
                "Constraint": (
                    "Envelope volume <= "
                    f"{max_envelope_volume_m3:.1f} m³"
                ),
                "g": g_volume,
                "Convention": "g <= 0",
                "Feasible": (
                    bool(g_volume <= 0.0)
                    if _finite(g_volume)
                    else False
                ),
            }
        )

    return pd.DataFrame(records)


# =============================================================================
# Main UI API
# =============================================================================

def run_optimization(
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the current ADaPT multidisciplinary optimization.

    The backend objective is minimum MTOW with a small penalty for excessive
    positive installed-power margin.

    All aircraft/subsystem physics remain in adapt.run_Optimization and the
    canonical run_MDA model.
    """

    # -------------------------------------------------------------------------
    # Output directory
    # -------------------------------------------------------------------------

    out_dir = _ensure_dir(
        Path(
            cfg.get(
                "out_dir",
                DEFAULT_OUTPUT_DIR,
            )
        ).resolve()
    )

    best_csv = (
        out_dir
        / "best_mdo_design.csv"
    )

    # -------------------------------------------------------------------------
    # Vehicle / mission configuration
    # -------------------------------------------------------------------------

    model_cfg = {}

    config_keys = (
        "power_source",
        "airship_type",
        "landing_system",
        "num_steps",
        "payload_kg",
        "range_m",
        "cruise_alt_m",
        "cruise_speed_mps",
        "length_m",
        "fineness_ratio",
        "tail_volume_coeff_horizontal",
        "tail_volume_coeff_vertical",
        "tail_coefficient_method",
        "installed_consumable_capacity_kg",
        "n_crew",
        "installed_shaft_power_W",
        "n_engine",
        "propeller_efficiency",
        "BR_takeoff",
        "BR_landing",
        "drag_coeff_zero",
        "drag_due_to_lift_factor",
        "lift_coeff",
    )

    for key in config_keys:
        if key in cfg:
            model_cfg[key] = cfg[key]

    # -------------------------------------------------------------------------
    # Algorithm settings
    # -------------------------------------------------------------------------

    pop_size = int(
        cfg.get("pop_size", 200)
    )

    n_gen = int(
        cfg.get("n_gen", 400)
    )

    seed = int(
        cfg.get("seed", 11)
    )

    jitter = float(
        cfg.get("jitter", 0.08)
    )

    verbose = bool(
        cfg.get("verbose", False)
    )

    # -------------------------------------------------------------------------
    # Optimization shaping / limits
    # -------------------------------------------------------------------------

    ground_roll_max_m = _optional_float(
        cfg.get(
            "ground_roll_max_m",
            opt.GROUND_ROLL_MAX_M,
        )
    )

    power_margin_cap_W = _optional_float(
        cfg.get(
            "power_margin_cap_w",
            opt.POWER_MARGIN_CAP_W,
        )
    )

    max_envelope_volume_m3 = _optional_float(
        cfg.get(
            "max_envelope_volume_m3",
            opt.MAX_ENVELOPE_VOLUME_M3,
        )
    )

    power_margin_penalty = float(
        cfg.get(
            "power_margin_penalty",
            opt.POWER_MARGIN_PENALTY,
        )
    )

    # -------------------------------------------------------------------------
    # Bounds
    # -------------------------------------------------------------------------

    lower_bounds = cfg.get(
        "lower_bounds",
        None,
    )

    upper_bounds = cfg.get(
        "upper_bounds",
        None,
    )

    if lower_bounds is not None:
        lower_bounds = np.asarray(
            lower_bounds,
            dtype=float,
        )

    if upper_bounds is not None:
        upper_bounds = np.asarray(
            upper_bounds,
            dtype=float,
        )

    # Validate with authoritative backend.
    lb, ub = opt.get_bounds(
        lower_bounds,
        upper_bounds,
    )

    # -------------------------------------------------------------------------
    # Basic validation
    # -------------------------------------------------------------------------

    if pop_size < 4:
        raise ValueError(
            "Population size must be at least 4."
        )

    if n_gen < 1:
        raise ValueError(
            "Number of generations must be positive."
        )

    if jitter < 0.0:
        raise ValueError(
            "Initial-population jitter cannot be negative."
        )

    if power_margin_penalty < 0.0:
        raise ValueError(
            "Power-margin penalty cannot be negative."
        )

    # -------------------------------------------------------------------------
    # Run authoritative backend
    # -------------------------------------------------------------------------

    result = opt.run_optimization(
        cfg=model_cfg,
        lower_bounds=lb,
        upper_bounds=ub,
        pop_size=pop_size,
        n_gen=n_gen,
        seed=seed,
        jitter=jitter,
        verbose=verbose,
        ground_roll_max_m=ground_roll_max_m,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
        power_margin_penalty=power_margin_penalty,
        save_best_csv=best_csv,
    )

    # -------------------------------------------------------------------------
    # Extract structured MDA result
    # -------------------------------------------------------------------------

    mda_results = result.get(
        "mda_results",
        {},
    )

    scalars_raw = mda_results.get(
        "scalars",
        {},
    )

    outputs_raw = mda_results.get(
        "outputs",
        {},
    )

    prob = result["problem"]

    required_W = opt._required_power_W(
        prob
    )

    installed_W = opt._installed_power_W(
        prob
    )

    if (
        _finite(required_W)
        and _finite(installed_W)
    ):
        margin_W = (
            installed_W - required_W
        )
    else:
        margin_W = np.nan

    ground_roll = opt._first_available(
        prob,
        (
            "takeoff_ground_roll",
            "ground_roll_distance",
        ),
        units="m",
        default=np.nan,
    )

    volume = opt._first_available(
        prob,
        (
            "gross_volume",
            "geometry.gross_volume",
        ),
        units="m**3",
        default=np.nan,
    )

    mtow = opt._get(
        prob,
        "mtow",
        units="kg",
        default=np.nan,
    )

    # -------------------------------------------------------------------------
    # UI scalar summary
    # -------------------------------------------------------------------------

    scalars = {
        "mtow_kg": mtow,

        "owe_kg": _scalar(
            scalars_raw,
            "owe_kg",
        ),

        "required_shaft_total_kW": (
            required_W / 1000.0
            if _finite(required_W)
            else np.nan
        ),

        "installed_power_total_kW": (
            installed_W / 1000.0
            if _finite(installed_W)
            else np.nan
        ),

        "power_margin_total_kW": (
            margin_W / 1000.0
            if _finite(margin_W)
            else np.nan
        ),

        "ground_roll_m": ground_roll,
        "gross_volume_m3": volume,

        "objective": float(
            result["objective"]
        ),

        "max_g": float(
            result["max_constraint_violation"]
        ),

        "feasible": bool(
            result["feasible"]
        ),
    }

    # Add useful current MDA scalars without overwriting
    # explicitly calculated values.
    for key, value in scalars_raw.items():
        if key not in scalars:
            scalars[key] = value

    # -------------------------------------------------------------------------
    # Design-variable table
    # -------------------------------------------------------------------------

    best_design = result[
        "best_design"
    ]

    df_design = pd.DataFrame(
        [
            {
                "Design Variable": name,
                "Value": best_design[name],
                "Lower Bound": lb[i],
                "Upper Bound": ub[i],
            }
            for i, name in enumerate(
                opt.DV_NAMES
            )
        ]
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    df_constraints = (
        _build_constraints_table(
            result,
            ground_roll_max_m,
            power_margin_cap_W,
            max_envelope_volume_m3,
        )
    )

    # -------------------------------------------------------------------------
    # Best-result CSV
    # -------------------------------------------------------------------------

    if best_csv.exists():
        df_best = pd.read_csv(
            best_csv
        )
    else:
        # The backend normally creates this file. This fallback keeps the UI
        # usable if CSV output is intentionally disabled in a future backend.
        row = {
            **best_design,
            **{
                k: v
                for k, v in scalars.items()
                if np.isscalar(v)
            },
        }

        df_best = pd.DataFrame(
            [row]
        )

    # -------------------------------------------------------------------------
    # Output summary table
    # -------------------------------------------------------------------------

    output_rows = []

    for key, value in scalars.items():

        if np.isscalar(value):

            output_rows.append(
                {
                    "Output": key,
                    "Value": value,
                }
            )

    df_outputs = pd.DataFrame(
        output_rows
    )

    # -------------------------------------------------------------------------
    # Settings used
    # -------------------------------------------------------------------------

    settings_used = {
        "pop_size": pop_size,
        "n_gen": n_gen,
        "seed": seed,
        "jitter": jitter,

        "ground_roll_max_m":
            ground_roll_max_m,

        "power_margin_cap_W":
            power_margin_cap_W,

        "max_envelope_volume_m3":
            max_envelope_volume_m3,

        "power_margin_penalty":
            power_margin_penalty,

        "candidate_source":
            result.get(
                "candidate_source"
            ),
    }

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    try:
        prob.cleanup()
    except Exception:
        pass

    # Do not expose the cleaned-up Problem to Streamlit.
    result_for_ui = {
        k: v
        for k, v in result.items()
        if k not in (
            "problem",
            "pymoo_result",
        )
    }

    return {
        "scalars": scalars,

        "best_design": best_design,

        "df_design": df_design,
        "df_constraints": df_constraints,
        "df_outputs": df_outputs,
        "df_best": df_best,
        "df_csv": df_best.copy(),

        "outputs_raw": outputs_raw,

        "backend_result": result_for_ui,

        "paths": {
            "best_csv": str(best_csv),
            "out_dir": str(out_dir),
        },

        "settings_used": settings_used,

        "module_file": getattr(
            opt,
            "__file__",
            "unknown",
        ),
    }