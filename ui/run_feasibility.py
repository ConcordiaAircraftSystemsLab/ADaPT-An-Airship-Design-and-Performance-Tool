# -*- coding: utf-8 -*-
"""
ADaPT Streamlit feasibility adapter.

All feasibility physics, OpenMDAO execution, optimization variables,
constraints, and sweeps are owned by:

    adapt.run_Feasibilty

This module is intentionally a thin UI adapter.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import adapt.run_Feasibilty as feas


# =============================================================================
# Paths
# =============================================================================

DEFAULT_OUTPUT_DIR = Path.cwd() / "app_out" / "feasibility"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Generic plotting helpers
# =============================================================================

def _grid_from_series(
    series: Dict,
    key: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert payload-range series output into a rectangular grid.

    Returns
    -------
    payloads : ndarray
    ranges : ndarray
    matrix : ndarray
    """
    ranges = np.asarray(sorted(series.keys()), dtype=float)

    payloads = np.unique(
        np.concatenate(
            [
                np.asarray(series[r]["payloads"], dtype=float)
                for r in sorted(series.keys())
            ]
        )
    )

    matrix = np.full(
        (len(ranges), len(payloads)),
        np.nan,
        dtype=float,
    )

    for j, range_km in enumerate(sorted(series.keys())):
        S = series[range_km]

        mapping = {
            float(payload): k
            for k, payload in enumerate(S["payloads"])
        }

        for i, payload in enumerate(payloads):
            k = mapping.get(float(payload))

            if k is not None:
                value = S[key][k]
                try:
                    matrix[j, i] = float(value)
                except (TypeError, ValueError):
                    matrix[j, i] = np.nan

    return payloads, ranges, matrix


def _safe_contour(
    ax,
    x,
    y,
    z,
    level: float,
    **kwargs,
):
    """
    Add a contour only when the requested level is actually contained
    within the finite data range.
    """
    z = np.asarray(z, dtype=float)
    finite = z[np.isfinite(z)]

    if finite.size == 0:
        return None

    if not (np.min(finite) <= level <= np.max(finite)):
        return None

    try:
        return ax.contour(
            x,
            y,
            z,
            levels=[level],
            **kwargs,
        )
    except Exception:
        return None


# =============================================================================
# Single-point feasibility
# =============================================================================

def run_feasibility_single(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    optimize: bool = False,
    pop_size: int = 60,
    n_gen: int = 80,
    seed: int = 11,
    ground_roll_max_m: Optional[float] = feas.GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = feas.MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = feas.MTOW_MAX_KG,
    power_margin_cap_W: Optional[float] = feas.POWER_MARGIN_CAP_W,
    max_envelope_volume_m3: Optional[float] = feas.MAX_ENVELOPE_VOLUME_M3,
) -> Dict[str, Any]:
    """
    Evaluate one current ADaPT configuration for feasibility.

    The backend problem is cleaned up here after all UI-ready results
    have been copied out.
    """

    result = feas.run_feasibility_once(
        cfg=cfg,
        optimize=optimize,
        pop_size=int(pop_size),
        n_gen=int(n_gen),
        seed=int(seed),
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        power_margin_cap_W=power_margin_cap_W,
        max_envelope_volume_m3=max_envelope_volume_m3,
    )

    prob = result.get("problem")

    try:
        mda = result.get("mda_results") or {}

        result["scalars"] = mda.get("scalars", {})
        result["outputs"] = mda.get("outputs", {})
        result["df_mass"] = mda.get(
            "df_mass",
            pd.DataFrame(columns=["Item", "Mass [kg]"]),
        )

        result["df_constraints"] = pd.DataFrame(
            result.get("constraint_rows", []),
            columns=["Name", "Value", "Feasible"],
        )

        # Flat one-row result for download.
        row = {}

        for key, value in result.get("config", {}).items():
            row[f"input_{key}"] = value

        for key, value in result["scalars"].items():
            row[key] = value

        for key, value in result["outputs"].items():
            row[key] = value

        row["feasible"] = bool(result.get("feasible", False))
        row["max_constraint_value"] = result.get(
            "max_constraint_value",
            np.nan,
        )

        if result.get("best_x") is not None:
            for name, value in zip(
                feas.DV_NAMES,
                np.asarray(result["best_x"]).reshape(-1),
            ):
                row[f"optimized_{name}"] = float(value)

        result["df_csv"] = pd.DataFrame([row])

        return result

    finally:
        # run_feasibility_once intentionally returns the problem.
        # The UI has no reason to keep OpenMDAO resources alive.
        if prob is not None:
            try:
                prob.cleanup()
            except Exception:
                pass

        result.pop("problem", None)


# =============================================================================
# Payload × range
# =============================================================================

def run_feasibility_payload_range(
    payload_min: float,
    payload_max: float,
    payload_n: int,
    range_list_km: Sequence[float],
    pop_size: int,
    n_gen: int,
    seed: int,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    optimize_each_point: bool = True,
    ground_roll_max_m: Optional[float] = feas.GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = feas.MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = feas.MTOW_MAX_KG,
) -> Dict[str, Any]:
    """
    Run the canonical payload × range feasibility sweep.
    """

    out_dir = _ensure_dir(Path(out_dir))
    csv_path = out_dir / "payload_range_sweep.csv"

    payload_grid = np.linspace(
        float(payload_min),
        float(payload_max),
        int(payload_n),
    )

    ranges = [float(x) for x in range_list_km]

    series = feas.run_sweep(
        payload_grid=payload_grid,
        range_list_km=ranges,
        cfg=cfg,
        pop_size=int(pop_size),
        n_gen=int(n_gen),
        seed=int(seed),
        optimize_each_point=bool(optimize_each_point),
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        save_csv=str(csv_path),
    )

    df = (
        pd.read_csv(csv_path)
        if csv_path.exists()
        else pd.DataFrame()
    )

    # -------------------------------------------------------------------------
    # Main sensitivity figure
    # -------------------------------------------------------------------------

    fig_lines, axs = plt.subplots(
        1,
        3,
        figsize=(18, 5.2),
        constrained_layout=True,
    )

    ranges_sorted = sorted(series.keys())

    # MTOW
    ax = axs[0]

    for range_km in ranges_sorted:
        S = series[range_km]

        ax.plot(
            S["payloads"],
            S["mtow"],
            marker="o",
            label=f"{range_km:g} km",
        )

    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("MTOW [kg]")
    ax.set_title("(a) MTOW")
    ax.grid(True, alpha=0.3)

    # Required consumable
    ax = axs[1]

    any_consumable = False

    for range_km in ranges_sorted:
        S = series[range_km]
        values = np.asarray(S["consumable"], dtype=float)

        if np.isfinite(values).any():
            any_consumable = True

            ax.plot(
                S["payloads"],
                values,
                marker="o",
                label=f"{range_km:g} km",
            )

    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Required consumable [kg]")
    ax.set_title(
        "(b) Required consumable"
        + ("" if any_consumable else " — N/A")
    )
    ax.grid(True, alpha=0.3)

    # Battery requirement
    ax = axs[2]

    any_battery = False

    for range_km in ranges_sorted:
        S = series[range_km]
        values = np.asarray(S["battery"], dtype=float)

        if np.isfinite(values).any():
            any_battery = True

            ax.plot(
                S["payloads"],
                values,
                marker="o",
                label=f"{range_km:g} km",
            )

    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Required battery mass [kg]")
    ax.set_title(
        "(c) Battery requirement"
        + ("" if any_battery else " — N/A")
    )
    ax.grid(True, alpha=0.3)

    handles, labels = axs[0].get_legend_handles_labels()

    if handles:
        fig_lines.legend(
            handles,
            labels,
            loc="lower center",
            ncol=min(len(labels), 6),
        )

    fig_lines.suptitle(
        "ADaPT Payload–Range Feasibility Study",
        fontsize=15,
    )

    # -------------------------------------------------------------------------
    # Grids
    # -------------------------------------------------------------------------

    payloads, range_values, CV = _grid_from_series(
        series,
        "maxcv",
    )

    _, _, GR = _grid_from_series(
        series,
        "gr",
    )

    _, _, PM = _grid_from_series(
        series,
        "pow_margin",
    )

    # -------------------------------------------------------------------------
    # Feasibility map
    # -------------------------------------------------------------------------

    fig_feasibility, ax = plt.subplots(
        figsize=(7.6, 5.8),
        constrained_layout=True,
    )

    finite_cv = CV[np.isfinite(CV)]

    if finite_cv.size:
        vmin = min(np.nanpercentile(finite_cv, 5), -1.0e-6)
        vmax = max(np.nanpercentile(finite_cv, 95), 1.0e-6)
    else:
        vmin, vmax = -1.0, 1.0

    im = ax.imshow(
        CV,
        origin="lower",
        aspect="auto",
        extent=[
            payloads.min(),
            payloads.max(),
            range_values.min(),
            range_values.max(),
        ],
        cmap="coolwarm",
        vmin=vmin,
        vmax=vmax,
    )

    cs = _safe_contour(
        ax,
        payloads,
        range_values,
        CV,
        0.0,
        colors="black",
        linewidths=1.5,
    )

    if cs is not None:
        ax.clabel(
            cs,
            fmt={0.0: "g = 0"},
            inline=True,
            fontsize=9,
        )

    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Range [km]")
    ax.set_title("Feasibility Map")

    cbar = fig_feasibility.colorbar(im, ax=ax)
    cbar.set_label("Maximum constraint value, feasible ≤ 0")

    # -------------------------------------------------------------------------
    # Ground-roll map
    # -------------------------------------------------------------------------

    fig_groundroll, ax = plt.subplots(
        figsize=(7.6, 5.8),
        constrained_layout=True,
    )

    im = ax.imshow(
        GR,
        origin="lower",
        aspect="auto",
        extent=[
            payloads.min(),
            payloads.max(),
            range_values.min(),
            range_values.max(),
        ],
        cmap="viridis",
    )

    if ground_roll_max_m is not None:
        cs = _safe_contour(
            ax,
            payloads,
            range_values,
            GR,
            float(ground_roll_max_m),
            colors="black",
            linewidths=1.5,
        )

        if cs is not None:
            ax.clabel(
                cs,
                fmt={
                    float(ground_roll_max_m):
                    f"{ground_roll_max_m:g} m"
                },
                inline=True,
                fontsize=9,
            )

    ax.set_xlabel("Payload [kg]")
    ax.set_ylabel("Range [km]")
    ax.set_title("Takeoff Ground Roll")

    cbar = fig_groundroll.colorbar(im, ax=ax)
    cbar.set_label("Ground roll [m]")

    # -------------------------------------------------------------------------
    # Power-margin map
    # -------------------------------------------------------------------------

    fig_powermargin = None

    if np.isfinite(PM).any():

        fig_powermargin, ax = plt.subplots(
            figsize=(7.6, 5.8),
            constrained_layout=True,
        )

        im = ax.imshow(
            PM,
            origin="lower",
            aspect="auto",
            extent=[
                payloads.min(),
                payloads.max(),
                range_values.min(),
                range_values.max(),
            ],
            cmap="viridis",
        )

        _safe_contour(
            ax,
            payloads,
            range_values,
            PM,
            0.0,
            colors="black",
            linewidths=1.5,
        )

        ax.set_xlabel("Payload [kg]")
        ax.set_ylabel("Range [km]")
        ax.set_title(
            "Installed − Required Shaft-Power Margin"
        )

        cbar = fig_powermargin.colorbar(im, ax=ax)
        cbar.set_label("Power margin [kW]")

    return {
        "df": df,
        "csv_path": str(csv_path),
        "series": series,
        "fig_lines": fig_lines,
        "fig_feasibility": fig_feasibility,
        "fig_groundroll": fig_groundroll,
        "fig_powermargin": fig_powermargin,
        "payload_grid": payloads,
        "range_grid_km": range_values,
        "CV": CV,
        "GR": GR,
        "PM": PM,
    }


# =============================================================================
# Payload × speed
# =============================================================================

def run_feasibility_payload_speed(
    payload_min: float,
    payload_max: float,
    payload_n: int,
    speed_min: float,
    speed_max: float,
    speed_n: int,
    range_m: float,
    optimize_each_point: bool,
    pop_size: int,
    n_gen: int,
    seed: int,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    ground_roll_max_m: Optional[float] = feas.GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = feas.MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = feas.MTOW_MAX_KG,
) -> Dict[str, Any]:

    out_dir = _ensure_dir(Path(out_dir))
    csv_path = out_dir / "payload_speed_feasibility.csv"

    payload_grid = np.linspace(
        float(payload_min),
        float(payload_max),
        int(payload_n),
    )

    speed_grid = np.linspace(
        float(speed_min),
        float(speed_max),
        int(speed_n),
    )

    CV = feas.run_payload_speed_feasibility(
        payload_grid=payload_grid,
        speed_grid_ms=speed_grid,
        range_m=float(range_m),
        cfg=cfg,
        pop_size=int(pop_size),
        n_gen=int(n_gen),
        seed=int(seed),
        optimize_each_point=bool(optimize_each_point),
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        save_csv=str(csv_path),
    )

    df = (
        pd.read_csv(csv_path)
        if csv_path.exists()
        else pd.DataFrame()
    )

    fig, ax = plt.subplots(
        figsize=(7.0, 5.8),
        constrained_layout=True,
    )

    finite = CV[np.isfinite(CV)]

    if finite.size:
        vmin = min(np.nanpercentile(finite, 5), -1.0e-6)
        vmax = max(np.nanpercentile(finite, 95), 1.0e-6)
    else:
        vmin, vmax = -1.0, 1.0

    im = ax.imshow(
        CV,
        origin="lower",
        aspect="auto",
        extent=[
            speed_grid.min(),
            speed_grid.max(),
            payload_grid.min(),
            payload_grid.max(),
        ],
        cmap="coolwarm",
        vmin=vmin,
        vmax=vmax,
    )

    cs = _safe_contour(
        ax,
        speed_grid,
        payload_grid,
        CV,
        0.0,
        colors="black",
        linewidths=1.5,
    )

    if cs is not None:
        ax.clabel(
            cs,
            fmt={0.0: "g = 0"},
            fontsize=9,
        )

    ax.set_xlabel("Cruise Speed [m/s]")
    ax.set_ylabel("Payload [kg]")
    ax.set_title("Payload–Speed Feasibility")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Maximum constraint value, feasible ≤ 0")

    return {
        "df": df,
        "csv_path": str(csv_path),
        "fig": fig,
        "payload_grid": payload_grid,
        "speed_grid": speed_grid,
        "CV": CV,
    }


# =============================================================================
# Altitude × cruise-fraction
# =============================================================================

def run_feasibility_altitude_power_volume(
    max_alt_min_m: float,
    max_alt_max_m: float,
    max_alt_n: int,
    cruise_frac_min: float,
    cruise_frac_max: float,
    cruise_frac_n: int,
    payload_kg: float,
    speed_ms: float,
    range_m: float,
    optimize_each_point: bool,
    pop_size: int,
    n_gen: int,
    seed: int,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    ground_roll_max_m: Optional[float] = feas.GROUND_ROLL_MAX_M,
    mtow_min_kg: Optional[float] = feas.MTOW_MIN_KG,
    mtow_max_kg: Optional[float] = feas.MTOW_MAX_KG,
) -> Dict[str, Any]:

    out_dir = _ensure_dir(Path(out_dir))
    csv_path = out_dir / "altitude_power_volume.csv"

    max_alt_grid_m = np.linspace(
        float(max_alt_min_m),
        float(max_alt_max_m),
        int(max_alt_n),
    )

    cruise_frac_grid = np.linspace(
        float(cruise_frac_min),
        float(cruise_frac_max),
        int(cruise_frac_n),
    )

    PkW, Vm3, CV = feas.run_altitude_power_volume_slice(
        max_alt_grid_m=max_alt_grid_m,
        cruise_frac_grid=cruise_frac_grid,
        payload_kg=float(payload_kg),
        speed_ms=float(speed_ms),
        range_m=float(range_m),
        cfg=cfg,
        optimize_at_each_point=bool(optimize_each_point),
        pop_size=int(pop_size),
        n_gen=int(n_gen),
        seed=int(seed),
        ground_roll_max_m=ground_roll_max_m,
        mtow_min_kg=mtow_min_kg,
        mtow_max_kg=mtow_max_kg,
        save_csv=str(csv_path),
    )

    df = (
        pd.read_csv(csv_path)
        if csv_path.exists()
        else pd.DataFrame()
    )

    X = max_alt_grid_m / 1000.0
    Y = cruise_frac_grid

    fig, axs = plt.subplots(
        1,
        2,
        figsize=(12, 5),
        constrained_layout=True,
    )

    # Required power
    ax = axs[0]

    im1 = ax.imshow(
        PkW,
        origin="lower",
        aspect="auto",
        extent=[
            X.min(),
            X.max(),
            Y.min(),
            Y.max(),
        ],
        cmap="viridis",
    )

    _safe_contour(
        ax,
        X,
        Y,
        CV,
        0.0,
        colors="white",
        linewidths=1.5,
    )

    ax.set_xlabel("Maximum Operating Altitude [km]")
    ax.set_ylabel(
        "Cruise Altitude / Maximum Altitude [-]"
    )
    ax.set_title("(a) Required Shaft Power")

    cbar = fig.colorbar(im1, ax=ax)
    cbar.set_label("Required shaft power [kW]")

    # Envelope volume
    ax = axs[1]

    im2 = ax.imshow(
        Vm3,
        origin="lower",
        aspect="auto",
        extent=[
            X.min(),
            X.max(),
            Y.min(),
            Y.max(),
        ],
        cmap="plasma",
    )

    _safe_contour(
        ax,
        X,
        Y,
        CV,
        0.0,
        colors="white",
        linewidths=1.5,
    )

    ax.set_xlabel("Maximum Operating Altitude [km]")
    ax.set_ylabel(
        "Cruise Altitude / Maximum Altitude [-]"
    )
    ax.set_title("(b) Gross Envelope Volume")

    cbar = fig.colorbar(im2, ax=ax)
    cbar.set_label("Gross envelope volume [m³]")

    return {
        "df": df,
        "csv_path": str(csv_path),
        "fig": fig,
        "PkW": PkW,
        "Vm3": Vm3,
        "CV": CV,
        "max_alt_grid_m": max_alt_grid_m,
        "cruise_frac_grid": cruise_frac_grid,
    }