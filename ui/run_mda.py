# -*- coding: utf-8 -*-
"""
UI adapter for the canonical ADaPT MDA runner.

The computational model, OpenMDAO setup, result collection,
profile generation, and report generation are owned by:

    adapt.run_MDA

This module intentionally remains thin so that the Streamlit UI
does not duplicate backend physics or OpenMDAO logic.

Author: Musavir Bashir
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from adapt.run_MDA import run_mda_once


# =============================================================================
# UI defaults
# =============================================================================

DEFAULT_OUTPUT_DIR = Path.cwd() / "app_out"
DEFAULT_REPORTS_DIR = DEFAULT_OUTPUT_DIR / "reports"


# =============================================================================
# UI-facing runner
# =============================================================================

def run_mda(
    cfg: Dict[str, Any],
    *,
    make_figure: bool = True,
    make_reports: bool = True,
) -> Dict[str, Any]:
    """
    Run one ADaPT MDA case for the Streamlit interface.

    Notes
    -----
    All model construction and physics remain in adapt.run_MDA.

    This wrapper only:
        1. chooses the UI report directory,
        2. calls the canonical run_mda_once() API,
        3. prepares a one-row summary DataFrame for CSV download.

    Parameters
    ----------
    cfg : dict
        User configuration from the Streamlit widgets.

    make_figure : bool
        Generate the airship profile figure.

    make_reports : bool
        Generate OpenMDAO N2 / XDSM reports.

    Returns
    -------
    dict
        Canonical ADaPT MDA results plus ``df_csv``.
    """

    DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Canonical backend call
    # -------------------------------------------------------------------------
    res = run_mda_once(
        cfg=cfg,
        make_figure=make_figure,
        make_reports=make_reports,
        reports_dir=DEFAULT_REPORTS_DIR,
        reports_basename="Airship_Sizing",
    )

    # -------------------------------------------------------------------------
    # Defensive UI defaults
    # -------------------------------------------------------------------------
    res.setdefault("config", dict(cfg))
    res.setdefault("scalars", {})
    res.setdefault("outputs", {})

    res.setdefault(
        "df_constraints",
        pd.DataFrame(
            columns=["Name", "Max Value", "Feasible", "N Values"]
        ),
    )

    res.setdefault(
        "df_mass",
        pd.DataFrame(
            columns=["Item", "Mass [kg]"]
        ),
    )

    res.setdefault("fig_profile", None)

    if res.get("reports") is None:
        res["reports"] = {
            "n2_path": None,
            "n2_html": None,
            "n2_ok": False,
            "xdsm_path": None,
            "xdsm_ok": False,
        }

    # -------------------------------------------------------------------------
    # Flat summary for CSV download
    # -------------------------------------------------------------------------
    #
    # Include:
    #   - normalized configuration actually used by the backend
    #   - principal scalar outputs
    #   - detailed outputs
    #
    # This is more useful than exporting only the old scalar dictionary.
    #
    flat_row = {}

    for key, value in res.get("config", {}).items():
        flat_row[f"input_{key}"] = value

    for key, value in res.get("scalars", {}).items():
        flat_row[key] = value

    for key, value in res.get("outputs", {}).items():
        flat_row[key] = value

    res["df_csv"] = pd.DataFrame([flat_row])

    return res