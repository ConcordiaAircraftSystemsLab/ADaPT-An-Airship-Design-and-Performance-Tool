# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path


def add_project_root_to_syspath() -> Path:
    """
    Configure Python paths so ADaPT can be used in both modes:

    1. Streamlit / package-style imports:
           from adapt.run_MDA import run_mda_once

    2. Existing standalone ADaPT imports:
           from AirshipAnalysisGroup import AirshipAnalysisGroup
           from AirshipGeometry import ...
           from AirshipWeight import ...

    Returns
    -------
    Path
        Project root directory containing the 'adapt' folder.
    """

    ui_dir = Path(__file__).resolve().parent

    # Search upward for the ADaPT project root.
    for parent in [ui_dir] + list(ui_dir.parents):

        adapt_dir = parent / "adapt"

        # Use the directory + a known backend module as markers.
        # __init__.py is also accepted but is not the only marker.
        if (
            adapt_dir.is_dir()
            and (
                (adapt_dir / "__init__.py").exists()
                or (adapt_dir / "AirshipAnalysisGroup.py").exists()
            )
        ):
            project_root = parent

            # -------------------------------------------------
            # 1. Project root
            # -------------------------------------------------
            # Required for package-style imports:
            #
            #   from adapt.run_MDA import ...
            #   from adapt.AirshipAnalysisGroup import ...
            #
            root_str = str(project_root)

            if root_str not in sys.path:
                sys.path.insert(0, root_str)

            # -------------------------------------------------
            # 2. Existing ADaPT source directory
            # -------------------------------------------------
            # Required for legacy/standalone imports already
            # present throughout the original ADaPT code:
            #
            #   from AirshipAnalysisGroup import ...
            #   from AirshipGeometry import ...
            #   from AirshipWeight import ...
            #
            adapt_str = str(adapt_dir)

            if adapt_str not in sys.path:
                # Put after project root so package imports
                # remain the preferred GUI convention.
                sys.path.insert(1, adapt_str)

            return project_root

    raise ModuleNotFoundError(
        "Could not locate the ADaPT project root.\n"
        f"Started search from: {ui_dir}\n"
        "Expected structure:\n"
        "  <project>/adapt/AirshipAnalysisGroup.py\n"
        "  <project>/ui/utils_paths.py"
    )