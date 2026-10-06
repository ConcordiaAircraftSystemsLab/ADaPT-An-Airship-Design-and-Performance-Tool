# -*- coding: utf-8 -*-
"""
MissionProfile.py
==================
Fuel-cell-sustained + battery-peaking power allocation across discrete mission segments.

AirshipMission.py computes a single steady-state cruise point (num_steps is used for cruise sub-steps,not distinct flight phases). 
This component sits alongside AirshipMission, not inside it, and is used for post-design mission verification / plotting. It does not change
sizing/optimization loop — it is a diagnostic/visualization layer that consumes the SIZED airship (mtow, P_fc_rated, battery & tank capacity) and
simulates how it behaves across a representative mission profile.

POWER ALLOCATION LOGIC
----------------------------------------------------------------
For each segment, given P_total demand and P_fc_rated:
    if P_total > P_fc_rated and SOC > 0 and SOF > 0:
        P_fc  = P_fc_rated         (fuel cell at rated power)
        P_bat = P_total - P_fc     (battery covers the deficit)
    elif SOF > 0:
        P_fc  = P_total            (fuel cell alone matches demand)
        P_bat = 0
    else:
        P_fc  = 0                  (hydrogen depleted)
        P_bat = P_total             (battery only, until SOC = 0)

SOC and SOF are tracked and decremented segment by segment.

WIRING
------
This is a standalone post-processing function, NOT an OpenMDAO component, because it operates on already-converged design outputs (mtow, capacities)
rather than being part of the multidisciplinary residual loop. Call it after prob.run_model() / run_driver() using the values pulled from 
existing AirshipAnalysisGroup outputs: from MissionProfile import simulate_mission_profile, DEFAULT_SEGMENTS

    mission_log = simulate_mission_profile(
        P_cruise_W   = float(prob.get_val('shaft_power')[0]),
        P_fc_rated_W = float(prob.get_val('engine_power')[0]),   # for hybrid case
        E_bat_avail_Wh = battery_capacity_Wh,                     # from BatteryOnly output
        m_H2_avail_kg  = float(prob.get_val('fuel_onboard_mass')[0]),
        eta_fc_func    = lambda P: fc_polarization_eta(P),        # from FuelCellPolarization
    )
    
@author: Musavir Bashir
"""

from __future__ import annotations
import numpy as np


Q_H2_WH_PER_KG = 33_330.0
Q_GASOLINE_WH_PER_KG = 43.0e6 / 3600.0

ARCHITECTURE_MAP = {
    "conventional_reciprocating": dict(ice=True, fuel_cell=False, battery=False, solar=False),
    "hydrogen_reciprocating": dict(ice=True, fuel_cell=False, battery=False, solar=False),
    "hydrogen_fuel_cell": dict(ice=False, fuel_cell=True, battery=False, solar=False),
    "battery_only": dict(ice=False, fuel_cell=False, battery=True, solar=False),
    "solar_battery": dict(ice=False, fuel_cell=False, battery=True, solar=True),
    "solar-RFC": dict(ice=False, fuel_cell=False, battery=True, solar=True),
    "hydrogen_hybrid": dict(ice=False, fuel_cell=True, battery=True, solar=False),
    "solar_hydrogen_hybrid": dict(ice=False, fuel_cell=True, battery=True, solar=True),
    "conventional_battery_hybrid": dict(ice=True, fuel_cell=False, battery=True, solar=False),
}

DEFAULT_SEGMENTS = [
    {"name": "Takeoff", "duration_s": 30, "P_factor": 1.93},
    {"name": "Climb", "duration_s": 100, "P_factor": 1.60},
    {"name": "Cruise", "duration_s": 3600, "P_factor": 1.00},
    {"name": "Loiter", "duration_s": 3600, "P_factor": 0.85},
    {"name": "Max speed", "duration_s": 600, "P_factor": 1.40},
    {"name": "Emergency", "duration_s": 300, "P_factor": 1.20},
]


def _eta_fc_default(P_W: float, eta_fc_func=None, eta_fc_const: float = 0.55) -> float:
    if eta_fc_func is not None and P_W > 0.0:
        return max(float(eta_fc_func(P_W)), 0.05)
    return max(float(eta_fc_const), 0.05)


def simulate_hybrid_mission(
    architecture: str,
    P_cruise_W: float,
    P_primary_rated_W: float = np.inf,
    E_bat_avail_Wh: float = 0.0,
    fuel_mass_kg: float = 0.0,
    solar_power_available_W: float = 0.0,
    tau_bat: float = 1.0,
    eta_fc_func=None,
    eta_fc_const: float = 0.55,
    eta_ice: float = 0.30,
    primary_fuel: str | None = None,
    segments: list | None = None,
    primary_margin: float = 0.10,
    bat_margin: float = 0.20,
):
    if architecture not in ARCHITECTURE_MAP:
        raise ValueError(f"Unknown architecture: {architecture}")

    cfg = ARCHITECTURE_MAP[architecture]
    segments = DEFAULT_SEGMENTS if segments is None else segments
    tau_bat = float(np.clip(tau_bat, 0.0, 1.0))

    if primary_fuel is None:
        if architecture in ["conventional_reciprocating", "conventional_battery_hybrid"]:
            primary_fuel = "gasoline"
        else:
            primary_fuel = "hydrogen"

    if primary_fuel == "gasoline":
        Q_primary = Q_GASOLINE_WH_PER_KG
    else:
        Q_primary = Q_H2_WH_PER_KG

    E_primary_avail_Wh = fuel_mass_kg * Q_primary * (1.0 - primary_margin)
    E_bat_usable_Wh = E_bat_avail_Wh * (1.0 - bat_margin)

    SOC = 1.0 if E_bat_usable_Wh > 0.0 else 0.0
    primary_remaining = 1.0 if E_primary_avail_Wh > 0.0 else 0.0

    log = []
    t_cum = 0.0

    for seg in segments:
        dur = float(seg["duration_s"])
        P_total = float(seg["P_factor"]) * float(P_cruise_W)
        remaining = P_total

        P_solar = 0.0
        P_bat = 0.0
        P_fc = 0.0
        P_ice = 0.0

        if cfg["solar"]:
            P_solar = min(max(solar_power_available_W, 0.0), remaining)
            remaining -= P_solar

        if cfg["battery"] and SOC > 0.0:
            if cfg["fuel_cell"] or cfg["ice"]:
                P_bat = min(tau_bat * remaining, remaining)
            else:
                P_bat = remaining
            remaining -= P_bat

        if cfg["fuel_cell"] and primary_remaining > 0.0:
            P_fc = min(remaining, P_primary_rated_W)
            remaining -= P_fc

        if cfg["ice"] and primary_remaining > 0.0:
            P_ice = min(remaining, P_primary_rated_W)
            remaining -= P_ice

        if remaining > 1e-9 and cfg["battery"] and SOC > 0.0:
            P_extra = remaining
            P_bat += P_extra
            remaining -= P_extra

        unmet_power = max(remaining, 0.0)

        eta_fc = _eta_fc_default(P_fc, eta_fc_func, eta_fc_const)
        E_solar_used_Wh = P_solar * dur / 3600.0
        E_bat_used_Wh = P_bat * dur / 3600.0

        E_fc_primary_Wh = (P_fc / eta_fc) * dur / 3600.0 if P_fc > 0.0 else 0.0
        E_ice_primary_Wh = (P_ice / max(eta_ice, 1e-6)) * dur / 3600.0 if P_ice > 0.0 else 0.0
        E_primary_used_Wh = E_fc_primary_Wh + E_ice_primary_Wh

        if E_bat_usable_Wh > 0.0:
            SOC = max(0.0, SOC - E_bat_used_Wh / E_bat_usable_Wh)

        if E_primary_avail_Wh > 0.0:
            primary_remaining = max(
                0.0, primary_remaining - E_primary_used_Wh / E_primary_avail_Wh
            )

        total_nonzero = max(P_total, 1.0)
        log.append(
            {
                "segment": seg["name"],
                "t_start_s": t_cum,
                "t_end_s": t_cum + dur,
                "duration_s": dur,
                "P_total_W": P_total,
                "P_solar_W": P_solar,
                "P_bat_W": P_bat,
                "P_fc_W": P_fc,
                "P_ice_W": P_ice,
                "P_unmet_W": unmet_power,
                "solar_fraction": P_solar / total_nonzero,
                "battery_fraction": P_bat / total_nonzero,
                "fuel_cell_fraction": P_fc / total_nonzero,
                "ice_fraction": P_ice / total_nonzero,
                "eta_fc": eta_fc,
                "SOC": SOC,
                "primary_remaining": primary_remaining,
                "E_solar_used_Wh": E_solar_used_Wh,
                "E_bat_used_Wh": E_bat_used_Wh,
                "E_primary_used_Wh": E_primary_used_Wh,
                "fuel_mass_used_kg": E_primary_used_Wh / max(Q_primary, 1.0),
            }
        )

        t_cum += dur

    return log


def mission_summary(mission_log):
    total_fuel_kg = sum(s["fuel_mass_used_kg"] for s in mission_log)
    total_bat_Wh = sum(s["E_bat_used_Wh"] for s in mission_log)
    total_solar_Wh = sum(s["E_solar_used_Wh"] for s in mission_log)
    final_SOC = mission_log[-1]["SOC"]
    final_primary = mission_log[-1]["primary_remaining"]
    total_time_h = mission_log[-1]["t_end_s"] / 3600.0
    max_unmet_W = max(s["P_unmet_W"] for s in mission_log)

    return dict(
        total_fuel_kg=total_fuel_kg,
        total_bat_Wh=total_bat_Wh,
        total_solar_Wh=total_solar_Wh,
        final_SOC=final_SOC,
        final_primary_remaining=final_primary,
        total_time_h=total_time_h,
        max_unmet_W=max_unmet_W,
    )


if __name__ == "__main__":
    from FuelCellPolarization import solve_operating_point

    def eta_fn(P_W):
        _, _, eta, _ = solve_operating_point(P_W, N_cells=72, A_cm2=100.0)
        return eta

    log = simulate_hybrid_mission(
        architecture="solar_hydrogen_hybrid",
        P_cruise_W=45_000.0,
        P_primary_rated_W=60_000.0,
        E_bat_avail_Wh=8_000.0,
        fuel_mass_kg=120.0,
        solar_power_available_W=8_000.0,
        tau_bat=0.15,
        eta_fc_func=eta_fn,
    )

    print(
        f"{'Segment':<14}{'Ptot[kW]':>9}{'Psol[kW]':>9}{'Pbat[kW]':>9}"
        f"{'Pfc[kW]':>9}{'Pice[kW]':>9}{'SOC':>8}{'Primary':>10}"
    )
    for s in log:
        print(
            f"{s['segment']:<14}"
            f"{s['P_total_W']/1000:>9.1f}"
            f"{s['P_solar_W']/1000:>9.1f}"
            f"{s['P_bat_W']/1000:>9.1f}"
            f"{s['P_fc_W']/1000:>9.1f}"
            f"{s['P_ice_W']/1000:>9.1f}"
            f"{s['SOC']:>8.3f}"
            f"{s['primary_remaining']:>10.3f}"
        )

    print("\nSummary:", mission_summary(log))