# -*- coding: utf-8 -*-
"""
ADaPT Streamlit DOE adapter.

The authoritative DOE implementation is:
    adapt.run_DOE

This module contains no aircraft, propulsion, battery, solar,
hydrogen, tank, or feasibility physics. It only:
    - translates Streamlit settings into the DOE API,
    - selects architectures,
    - manages the output directory,
    - collects generated CSV/PNG assets,
    - returns UI-ready results.

Author: Musavir Bashir
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import adapt.run_DOE as doe


DEFAULT_OUTPUT_DIR = Path.cwd() / "app_out" / "doe"


# =============================================================================
# Helpers
# =============================================================================

def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _selected_architectures(
    selected_keys: Optional[List[str]],
):
    """
    Return architecture dictionaries from the authoritative DOE backend.
    """
    if selected_keys is None:
        return list(doe.ARCHES)

    selected = [
        arch
        for arch in doe.ARCHES
        if arch["key"] in selected_keys
    ]

    if not selected:
        raise RuntimeError(
            "No DOE architectures were selected."
        )

    return selected


def _parse_shells(value):
    if value is None:
        return (0.01, 0.02, 0.04, 0.07, 0.10)

    shells = tuple(float(x) for x in value)

    if not shells:
        raise ValueError(
            "At least one DOE shell radius is required."
        )

    if any(x <= 0.0 for x in shells):
        raise ValueError(
            "DOE shell radii must all be greater than zero."
        )

    return shells


# =============================================================================
# Main UI API
# =============================================================================

def run_doe(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the current ADaPT architecture optimization + DOE workflow.

    Parameters
    ----------
    cfg : dict
        UI settings.

    Supported keys
    --------------
    arches
        List of architecture keys.

    payload_kg
    range_m
    cruise_alt_m
    cruise_speed_mps
    num_steps
        Mission/current-MDA overrides.

    pop_size
    n_gen
    seed
        Differential-evolution settings.

    n_per_shell
    shells
    doe_seed
        Local DOE settings.

    battery_se_jitter
    battery_ve_jitter
    efficiency_jitter
        Technology-input perturbations.

    out_dir
        Output directory.

    Returns
    -------
    dict
        df_arch
        clouds
        arch_csv
        combined_png
        energy_png
        arch_plots
        arch_clouds
        out_dir
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

    # -------------------------------------------------------------------------
    # Architecture selection
    # -------------------------------------------------------------------------

    selected_keys = cfg.get("arches")

    architectures = _selected_architectures(
        selected_keys
    )

    # -------------------------------------------------------------------------
    # Mission / vehicle overrides
    #
    # The current backend builds each architecture from BASE_CONFIG.
    # Update only the common configuration anchors requested by the UI.
    # Architecture-specific settings remain in ARCHES.
    # -------------------------------------------------------------------------

    common_overrides = {}

    if "payload_kg" in cfg:
        common_overrides["payload_kg"] = float(
            cfg["payload_kg"]
        )

    if "range_m" in cfg:
        common_overrides["range_m"] = float(
            cfg["range_m"]
        )

    if "cruise_alt_m" in cfg:
        common_overrides["cruise_alt_m"] = float(
            cfg["cruise_alt_m"]
        )

    if "cruise_speed_mps" in cfg:
        common_overrides["cruise_speed_mps"] = float(
            cfg["cruise_speed_mps"]
        )

    if "num_steps" in cfg:
        common_overrides["num_steps"] = int(
            cfg["num_steps"]
        )

    # Save original BASE_CONFIG so the UI call does not permanently mutate
    # the imported DOE module during a Streamlit session.
    original_base_config = dict(doe.BASE_CONFIG)

    # -------------------------------------------------------------------------
    # DOE settings
    # -------------------------------------------------------------------------

    pop_size = int(
        cfg.get("pop_size", 96)
    )

    n_gen = int(
        cfg.get("n_gen", 160)
    )

    optimization_seed = int(
        cfg.get(
            "optimization_seed",
            cfg.get("seed", 11),
        )
    )

    n_per_shell = int(
        cfg.get("n_per_shell", 800)
    )

    shells = _parse_shells(
        cfg.get(
            "shells",
            (0.01, 0.02, 0.04, 0.07, 0.10),
        )
    )

    doe_seed = int(
        cfg.get("doe_seed", 13)
    )

    battery_se_jitter = float(
        cfg.get(
            "battery_se_jitter",
            0.15,
        )
    )

    battery_ve_jitter = float(
        cfg.get(
            "battery_ve_jitter",
            0.15,
        )
    )

    efficiency_jitter = float(
        cfg.get(
            "efficiency_jitter",
            0.05,
        )
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    if pop_size < 4:
        raise ValueError(
            "DE population size must be at least 4."
        )

    if n_gen < 1:
        raise ValueError(
            "Number of DE generations must be positive."
        )

    if n_per_shell < 1:
        raise ValueError(
            "Samples per shell must be positive."
        )

    for name, value in (
        ("battery_se_jitter", battery_se_jitter),
        ("battery_ve_jitter", battery_ve_jitter),
        ("efficiency_jitter", efficiency_jitter),
    ):
        if value < 0.0:
            raise ValueError(
                f"{name} cannot be negative."
            )

    # -------------------------------------------------------------------------
    # Run inside output directory
    # -------------------------------------------------------------------------

    old_cwd = Path.cwd()

    try:
        os.chdir(out_dir)

        # Apply common mission anchors.
        doe.BASE_CONFIG.update(
            common_overrides
        )

        # Use the authoritative backend API.
        result = doe.run_doe(
            architectures=architectures,
            pop_size=pop_size,
            n_gen=n_gen,
            optimization_seed=optimization_seed,
            n_per_shell=n_per_shell,
            shells=shells,
            doe_seed=doe_seed,
            battery_se_jitter=battery_se_jitter,
            battery_ve_jitter=battery_ve_jitter,
            efficiency_jitter=efficiency_jitter,
            make_plots=True,
        )

        df_arch = result.get(
            "summary",
            pd.DataFrame(),
        )

        clouds = result.get(
            "clouds",
            {},
        )

        # ---------------------------------------------------------------------
        # Generated assets
        # ---------------------------------------------------------------------

        arch_csv_path = (
            out_dir
            / "architectures_pymoo_with_doe.csv"
        )

        combined_png_path = (
            out_dir
            / "pfei_vs_mtow_clouds.png"
        )

        energy_png_path = (
            out_dir
            / "energy_chain.png"
        )

        arch_plots: Dict[str, str] = {}
        arch_clouds: Dict[str, str] = {}

        for arch in architectures:

            name = arch["name"]
            safe_name = name.replace(" ", "_")

            cloud_csv = (
                out_dir
                / f"doe_{safe_name}.csv"
            )

            cluster_png = (
                out_dir
                / f"{safe_name}_DOE.png"
            )

            if cloud_csv.exists():
                arch_clouds[name] = str(
                    cloud_csv
                )

            if cluster_png.exists():
                arch_plots[name] = str(
                    cluster_png
                )

        # ---------------------------------------------------------------------
        # UI summary statistics
        # ---------------------------------------------------------------------

        n_architectures = len(df_arch)

        if (
            not df_arch.empty
            and "feasible" in df_arch.columns
        ):
            feasible_series = (
                df_arch["feasible"]
                .fillna(False)
                .astype(bool)
            )

            n_feasible_architectures = int(
                feasible_series.sum()
            )
        else:
            n_feasible_architectures = 0

        total_samples = 0
        feasible_samples = 0

        for cloud in clouds.values():

            if cloud is None or cloud.empty:
                continue

            total_samples += len(cloud)

            if "feasible" in cloud.columns:
                feasible_samples += int(
                    cloud["feasible"]
                    .fillna(False)
                    .astype(bool)
                    .sum()
                )

        feasible_fraction = (
            feasible_samples / total_samples
            if total_samples > 0
            else float("nan")
        )

        return {
            "df_arch": df_arch,
            "clouds": clouds,

            "arch_csv": (
                str(arch_csv_path)
                if arch_csv_path.exists()
                else None
            ),

            "combined_png": (
                str(combined_png_path)
                if combined_png_path.exists()
                else None
            ),

            "energy_png": (
                str(energy_png_path)
                if energy_png_path.exists()
                else None
            ),

            "arch_plots": arch_plots,
            "arch_clouds": arch_clouds,

            "out_dir": str(out_dir),

            "n_architectures": n_architectures,
            "n_feasible_architectures": (
                n_feasible_architectures
            ),
            "total_samples": total_samples,
            "feasible_samples": feasible_samples,
            "feasible_fraction": feasible_fraction,

            "settings": {
                "pop_size": pop_size,
                "n_gen": n_gen,
                "optimization_seed": (
                    optimization_seed
                ),
                "n_per_shell": n_per_shell,
                "shells": shells,
                "doe_seed": doe_seed,
                "battery_se_jitter": (
                    battery_se_jitter
                ),
                "battery_ve_jitter": (
                    battery_ve_jitter
                ),
                "efficiency_jitter": (
                    efficiency_jitter
                ),
            },
        }

    finally:

        # Restore imported backend state.
        doe.BASE_CONFIG.clear()
        doe.BASE_CONFIG.update(
            original_base_config
        )

        os.chdir(old_cwd)