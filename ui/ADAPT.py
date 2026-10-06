# -*- coding: utf-8 -*-
"""
@author: Musavir Bashir
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Tuple, Optional
import json
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import plotly.graph_objects as go


# ---------------------------
# Data model
# ---------------------------
@dataclass
class AirshipGeomConfig:
    # Hull
    length_m: float = 53.4
    fineness_ratio: float = 4.0
    hull_shape: str = "Prolate spheroid"   # ["Prolate spheroid", "Elliptic (simple)", "NPL-like (smooth)"]
    n_profile_pts: int = 600

    # Optional add-ons
    has_gondola: bool = True
    gondola_length_m: float = 10.0
    gondola_height_m: float = 2.2

    has_tail: bool = True
    tail_span_m: float = 8.0
    tail_height_m: float = 5.0

    # Reference conditions (for quick buoyancy intuition)
    rho_air_kg_m3: float = 1.225
    rho_helium_kg_m3: float = 0.1786

    @property
    def diameter_m(self) -> float:
        return float(self.length_m) / max(float(self.fineness_ratio), 1e-9)


# ---------------------------
# Geometry helpers
# ---------------------------
def hull_profile(cfg: AirshipGeomConfig) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns x (m) from -L/2..+L/2 and radius r(x) (m).
    """
    L = float(cfg.length_m)
    R = float(cfg.diameter_m) / 2.0
    n = int(cfg.n_profile_pts)

    x = np.linspace(-L / 2.0, L / 2.0, n)

    if cfg.hull_shape == "Prolate spheroid":
        # (x/a)^2 + (r/b)^2 = 1
        a = L / 2.0
        b = R
        r = b * np.sqrt(np.clip(1.0 - (x / a) ** 2, 0.0, 1.0))

    elif cfg.hull_shape == "NPL-like (smooth)":
        # Smooth "cigar": r = R * (1 - (|x|/a)^p)^(1/q)
        # Tuned exponents for a realistic-ish nose/tail
        a = L / 2.0
        p = 2.4
        q = 1.9
        s = np.abs(x) / a
        r = R * np.power(np.clip(1.0 - np.power(s, p), 0.0, 1.0), 1.0 / q)

    else:
        # "Elliptic (simple)" (same as prolate but kept for clarity)
        a = L / 2.0
        r = R * np.sqrt(np.clip(1.0 - (x / a) ** 2, 0.0, 1.0))

    return x, r


def revolve_mesh(x: np.ndarray, r: np.ndarray, n_theta: int = 80) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create a surface of revolution mesh for Plotly: X, Y, Z arrays.
    """
    theta = np.linspace(0.0, 2.0 * np.pi, n_theta)
    X = np.tile(x[:, None], (1, len(theta)))
    Y = r[:, None] * np.cos(theta)[None, :]
    Z = r[:, None] * np.sin(theta)[None, :]
    return X, Y, Z


def volume_by_revolution(x: np.ndarray, r: np.ndarray) -> float:
    """
    Volume = pi * integral(r^2 dx)
    """
    return float(np.pi * np.trapz(r**2, x))


def surface_area_by_revolution(x: np.ndarray, r: np.ndarray) -> float:
    """
    Surface area = 2*pi*integral(r * sqrt(1 + (dr/dx)^2) dx)
    """
    drdx = np.gradient(r, x)
    integrand = r * np.sqrt(1.0 + drdx**2)
    return float(2.0 * np.pi * np.trapz(integrand, x))


def buoyant_lift_kg(cfg: AirshipGeomConfig, volume_m3: float) -> float:
    """
    Net buoyant lift mass equivalent:
    (rho_air - rho_gas) * V   (kg)
    """
    return float((cfg.rho_air_kg_m3 - cfg.rho_helium_kg_m3) * volume_m3)


# ---------------------------
# Plots
# ---------------------------
def fig_profile_2d(cfg: AirshipGeomConfig) -> plt.Figure:
    x, r = hull_profile(cfg)
    fig = plt.figure(figsize=(9.0, 3.8))
    ax = fig.add_subplot(111)
    ax.plot(x,  r, linewidth=2.0)
    ax.plot(x, -r, linewidth=2.0)
    ax.set_aspect("equal", "box")
    ax.set_title("Hull profile (side view)")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("radius [m]")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def fig_top_view_2d(cfg: AirshipGeomConfig) -> plt.Figure:
    x, r = hull_profile(cfg)
    fig = plt.figure(figsize=(9.0, 3.8))
    ax = fig.add_subplot(111)
    ax.plot(x,  r, linewidth=2.0)
    ax.plot(x, -r, linewidth=2.0)
    ax.set_aspect("equal", "box")
    ax.set_title("Hull footprint (top view proxy)")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("radius [m]")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def fig_hull_3d(cfg: AirshipGeomConfig) -> go.Figure:
    x, r = hull_profile(cfg)
    X, Y, Z = revolve_mesh(x, r, n_theta=90)

    fig = go.Figure(
        data=[
            go.Surface(x=X, y=Y, z=Z, showscale=False, opacity=0.95),
        ]
    )
    fig.update_layout(
        title="3D Hull (surface of revolution)",
        scene=dict(
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="z [m]",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=45, b=0),
        height=520,
    )
    return fig


def geometry_summary_table(cfg: AirshipGeomConfig) -> pd.DataFrame:
    x, r = hull_profile(cfg)
    V = volume_by_revolution(x, r)
    S = surface_area_by_revolution(x, r)
    lift = buoyant_lift_kg(cfg, V)

    rows = [
        ("Length [m]", cfg.length_m),
        ("Fineness ratio [-]", cfg.fineness_ratio),
        ("Max diameter [m]", cfg.diameter_m),
        ("Volume (hull) [m^3]", V),
        ("Surface area (hull) [m^2]", S),
        ("Net buoyant lift (He) [kg]", lift),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


# ---------------------------
# Presets
# ---------------------------
def preset_library() -> Dict[str, AirshipGeomConfig]:
    return {
        "A-170 baseline (example)": AirshipGeomConfig(length_m=53.4, fineness_ratio=4.0, hull_shape="Prolate spheroid"),
        "Slender (fast cruise)": AirshipGeomConfig(length_m=70.0, fineness_ratio=5.5, hull_shape="NPL-like (smooth)"),
        "Fat (high volume)": AirshipGeomConfig(length_m=55.0, fineness_ratio=3.2, hull_shape="Prolate spheroid"),
        "Small demo": AirshipGeomConfig(length_m=25.0, fineness_ratio=4.2, hull_shape="Elliptic (simple)"),
    }


def cfg_to_json(cfg: AirshipGeomConfig) -> str:
    return json.dumps(asdict(cfg), indent=2)


def cfg_from_json(s: str) -> AirshipGeomConfig:
    d = json.loads(s)
    return AirshipGeomConfig(**d)
