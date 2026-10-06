# -*- coding: utf-8 -*-
"""
@author: Musavir Bashir
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import openmdao.api as om
from matplotlib.patches import Ellipse

from pymoo.optimize import minimize
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.core.sampling import Sampling
from pymoo.core.problem import ElementwiseProblem
from pymoo.termination import get_termination

try:
    from colorama import Fore
except Exception:
    class _F: LIGHTGREEN_EX=""; RED=""; CYAN=""; RESET=""
    Fore=_F()

# seaborn optional (for KDE)
try:
    import seaborn as sns
    _HAVE_SNS = True
except Exception:
    _HAVE_SNS = False

from AirshipAnalysisGroup import AirshipAnalysisGroup
from operatingConditions import opCond
from BatteryOnly import BatteryOnly

# ----------------------------- helpers -----------------------------
def _get(prob, name, units=None, default=np.nan):
    try:
        v = prob.get_val(name, units=units)
        return float(np.asarray(v).flat[0])
    except Exception:
        return default

class OMInitialSampling(Sampling):
    def __init__(self, x0, jitter=0.06):
        super().__init__()
        self.x0 = np.asarray(x0, float).copy()
        self.jitter = float(jitter)
    def _do(self, problem, n_samples, **kwargs):
        lb, ub = np.asarray(problem.xl), np.asarray(problem.xu)
        pop = np.random.uniform(lb, ub, size=(n_samples, lb.size))
        pop[0, :] = np.clip(self.x0, lb, ub)
        k = min(5, n_samples-1)
        if k > 0:
            idx = np.random.choice(np.arange(1, n_samples), size=k, replace=False)
            rng = ub - lb
            pop[idx] = np.clip(self.x0 + self.jitter*rng*(np.random.rand(k, lb.size)-0.5), lb, ub)
        return pop

def _select_best(res):
    X = getattr(res, "X", None)
    if X is not None:
        return X if np.ndim(X)==1 else X[0], "res.X"
    if hasattr(res, "pop") and res.pop is not None:
        pop = res.pop
        Xp = pop.get("X"); Fp = pop.get("F").reshape(-1); CVp = pop.get("CV").reshape(-1)
        idx = np.lexsort((Fp, CVp))
        return Xp[idx[0]], "res.pop"
    if hasattr(res, "history") and res.history:
        best = None
        for algo in res.history:
            pop = getattr(algo, "pop", None)
            if pop is None: continue
            Xp = pop.get("X"); Fp = pop.get("F").reshape(-1); CVp = pop.get("CV").reshape(-1)
            j = np.lexsort((Fp, CVp))[0]
            cand = (CVp[j], Fp[j], Xp[j])
            if best is None or cand[0] < best[0] or (cand[0]==best[0] and cand[1] < best[1]):
                best = cand
        if best is not None: return best[2], "history"
    raise RuntimeError("pymoo produced no candidate; relax bounds/constraints.")


# ----------------------------- architecture configs -----------------------------
# Modified to only include "Battery Electric" for this run
ARCHES = [
    dict(name="Battery Electric",
         key="battery_only",
         power_source="battery_only", engine_type="electric",
         engine_power_W=400e3, bsfc_kg_per_Ws=0.0, lhv_J_per_kg=0.0, solar_MJ=0.0,
         mtow_lower_kg=10_000.0, mtow_upper_kg=100_000.0),   # allow heavy pack
]

ARCH_COLORS = {
    "conventional_fuel": "#17becf",
    "hydrogen": "#e377c2",
    "battery_only": "#1f77b4",
    "solar_battery": "#ff7f0e"
}

# Pack/tank assumptions
BAT_WH_PER_KG = 200.0  # Match BatteryOnly spec_energy_Wh_per_kg
BAT_WH_PER_L  = 500.0  # Match BatteryOnly spec_vol_Wh_per_L
H2_LIQ_RHO    = 70.0
H2_TANK_MASS_FRAC = 0.15
H2_TANK_VOL_MARGIN = 1.25

# Mission anchors
PAYLOAD_KG   = 1123.0
RANGE_M      = 1_342_100.0
CRUISE_ALT_M = 914.0
CRUISE_V_MS  = 19.5
NUM_STEPS    = 161


# ----------------------------- Build OM problem -----------------------------
def build_problem(arch):
    phd = opCond(name="Cruise", T_env=281.65, altitude=CRUISE_ALT_M, speed=CRUISE_V_MS/337.5, time="day", RH=70.0)
    prob = om.Problem()
    m = prob.model
    iv = m.add_subsystem("indeps", om.IndepVarComp(), promotes=["*"])

    iv.add_output("length", 53.4, units="m")
    iv.add_output("fineness_ratio", 4.0)
    iv.add_output("tail_volume_coeff_horizontal", 0.066)
    iv.add_output("tail_volume_coeff_vertical",   0.059)
    iv.add_output("payload", PAYLOAD_KG, units="kg")
    iv.add_output("range",   RANGE_M,    units="m")
    iv.add_output("cruise_altp",  np.array([CRUISE_ALT_M]), units="m")
    iv.add_output("cruise_disa",  np.array([0.0]), units="K")
    iv.add_output("cruise_speed", np.array([CRUISE_V_MS]), units="m/s")
    iv.add_output("tailwind_speed", 0.0, units="m/s")
    iv.add_output("n_crew", 1)
    iv.add_output("engine_power", np.array([arch["engine_power_W"]]), units="W")
    iv.add_output("n_engine", 2)
    iv.add_output("propeller_efficiency", 0.78)
    iv.add_output("BR_takeoff", 0.83)
    iv.add_output("BR_landing", 0.90)
    iv.add_output("lift_coeff", 0.15)
    iv.add_output("drag_due_to_lift_factor", 0.869)
    iv.add_output("drag_coeff_zero", 0.03542)
    iv.add_output("solar_energy", arch.get("solar_MJ", 0.0), units="MJ")

    m.add_subsystem(
        "airship",
        AirshipAnalysisGroup(
            phd=phd,
            power_source=arch["power_source"],
            landing_system="conventional",
            power_type="conventional_reciprocating",
            engine_type=arch["engine_type"],
            fixed_power=True,
            num_steps=NUM_STEPS,
        ), promotes=["*"]
    )

    m.linear_solver = om.DirectSolver()
    m.nonlinear_solver = om.NonlinearBlockGS(maxiter=100, atol=1e-6, rtol=1e-6)

    prob.setup(check=False)
    prob.run_model()
    return prob


# ----------------------------- pymoo problem -----------------------------
# DVs: [BR_takeoff, tvc_h, tvc_v, lift_coeff, k_lift, eta_prop]
LB = np.array([0.50, 0.05, 0.04, 0.12, 0.45, 0.70])
UB = np.array([0.98, 0.09, 0.08, 0.22, 1.00, 0.88])

def _set_x(prob, x):
    prob.set_val("BR_takeoff", x[0])
    prob.set_val("tail_volume_coeff_horizontal", x[1])
    prob.set_val("tail_volume_coeff_vertical",   x[2])
    prob.set_val("lift_coeff", x[3])
    prob.set_val("drag_due_to_lift_factor", x[4])
    prob.set_val("propeller_efficiency", x[5])

def _energy_packaging(prob, arch):
    V = _get(prob, "cruise_speed", "m/s")
    D = _get(prob, "drag_cruise", "N", default=np.nan)
    if not np.isfinite(D):
        T = _get(prob, "thrust_cruise", "N", default=np.nan)
        if np.isfinite(T): D = T
    eta_prop = max(_get(prob, "propeller_efficiency", default=0.75), 0.5)
    P_req = (max(D,1.0) * max(V,1.0)) / eta_prop
    t = _get(prob, "mission_duration", "s")

    bsfc = arch["bsfc_kg_per_Ws"]; lhv = arch["lhv_J_per_kg"]
    fuel_mass = np.nan; pack_mass=np.nan; pack_vol=np.nan; tank_mass=np.nan; tank_vol=np.nan; E_MJ=np.nan

    if arch["power_source"] in ("conventional_fuel","hydrogen"):
        fuel_mass = bsfc * P_req * t
        E_MJ = (lhv * fuel_mass) / 1e6
        if arch["power_source"] == "hydrogen":
            tank_vol  = H2_TANK_VOL_MARGIN * (fuel_mass / H2_LIQ_RHO)
            tank_mass = H2_TANK_MASS_FRAC * fuel_mass
    else:
        E_req_Wh = (P_req * t) / 3600.0  # Convert J to Wh
        pack_mass = _get(prob, "power_system_mass", "kg")
        pack_vol  = _get(prob, "power_system_volume", "m**3")
        E_MJ      = (E_req_Wh * 3600.0) / 1e6  # Convert back to MJ for consistency

    owe = _get(prob, "owe", "kg", default=np.nan)
    mtow_star = owe + PAYLOAD_KG + (0.0 if np.isnan(fuel_mass) else fuel_mass) + \
                (0.0 if np.isnan(pack_mass) else pack_mass) + \
                (0.0 if np.isnan(tank_mass) else tank_mass)

    return dict(E_MJ=E_MJ, P_req=P_req, mtow_star=mtow_star,
                fuel_mass=fuel_mass, pack_mass=pack_mass, pack_vol=pack_vol,
                tank_mass=tank_mass, tank_vol=tank_vol)

def _feasibility_g(prob, arch, m):
    """Constraints g<=0; includes arch-specific MTOW window."""
    g = []
    g.append(-_get(prob, "power_constraint", "W", default=1.0))
    g.append(-_get(prob, "energy_constraint", "kg", default=1.0))
    g.append(-_get(prob, "buoyancy_constraint", default=1.0))
    g.append(_get(prob, "ground_roll_distance", "m", default=1e6) - 1000.0)
    g.append(0.05 - _get(prob, "stability_margin", default=0.0))
    air_max_vol = _get(prob, "air_max_volume", "m**3", default=np.nan)
    if np.isfinite(air_max_vol):
        pack_vol = 0.0 if np.isnan(m["pack_vol"]) else m["pack_vol"]
        tank_vol = 0.0 if np.isnan(m["tank_vol"]) else m["tank_vol"]
        g.append(pack_vol + tank_vol - 0.9*air_max_vol)
    else:
        g.append(0.0)
    g.append(max(m["mtow_star"] - arch["mtow_upper_kg"], 0.0))
    g.append(max(arch["mtow_lower_kg"] - m["mtow_star"], 0.0))
    return np.array(g, float)

class PFEIProblem(ElementwiseProblem):
    def __init__(self, prob, arch):
        super().__init__(n_var=6, n_obj=1, n_constr=8, xl=LB, xu=UB)
        self.prob = prob
        self.arch = arch
    def _evaluate(self, x, out, *args, **kwargs):
        _set_x(self.prob, x); self.prob.run_model()
        m = _energy_packaging(self.prob, self.arch)
        g = _feasibility_g(self.prob, self.arch, m)
        pfei = m["E_MJ"] / (PAYLOAD_KG*(RANGE_M/1000.0))
        out["F"] = pfei if np.isfinite(pfei) else 1e9
        out["G"] = g


# ----------------------------- run one architecture -----------------------------
def run_arch_pymoo(arch, pop_size=96, n_gen=160, seed=11):
    prob = build_problem(arch)
    x0 = np.array([
        _get(prob,"BR_takeoff"),
        _get(prob,"tail_volume_coeff_horizontal"),
        _get(prob,"tail_volume_coeff_vertical"),
        _get(prob,"lift_coeff"),
        _get(prob,"drag_due_to_lift_factor"),
        _get(prob,"propeller_efficiency"),
    ], float)

    moo_prob = PFEIProblem(prob, arch)
    algo = DE(pop_size=pop_size, sampling=OMInitialSampling(x0, jitter=0.06))
    term = get_termination("n_gen", n_gen)
    res = minimize(moo_prob, algo, term, seed=seed, verbose=False)

    X, _ = _select_best(res)
    _set_x(prob, X); prob.run_model()
    m = _energy_packaging(prob, arch)

    row = dict(
        arch=arch["name"],
        key=arch.get("key", arch["name"].lower().replace(" ","_")),
        Xbest=X,
        P_req_kW=m["P_req"]/1e3,
        P_installed_kW=_get(prob, "engine_power", "W")/1e3,
        P_margin_kW=(_get(prob, "engine_power", "W")-m["P_req"])/1e3,
        owe_kg=_get(prob, "owe", "kg"),
        mtow_star_kg=m["mtow_star"],
        fuel_mass_kg=m["fuel_mass"],
        battery_mass_kg=m["pack_mass"],
        battery_vol_m3=m["pack_vol"],
        h2_tank_mass_kg=m["tank_mass"],
        h2_tank_vol_m3=m["tank_vol"],
        total_energy_MJ=m["E_MJ"],
        pfei_MJ_per_kg_km=m["E_MJ"]/(PAYLOAD_KG*(RANGE_M/1000.0)),
    )
    prob.cleanup()
    return row


# ----------------------------- DOE around optimum -----------------------------
def _latin_hypercube(n, d, rng):
    u = (rng.rand(n, d) + np.arange(n)[:, None]) / n
    for j in range(d): rng.shuffle(u[:, j])
    return u

def doe_around_best(arch, Xbest, n_per_shell=1000, shells=(0.05, 0.1, 0.15, 0.2, 0.25, 0.3), seed=13):
    """Dense multi-shell jitter around the optimum in DV space."""
    rng = np.random.RandomState(seed)
    lb, ub = LB, UB
    width = (ub - lb)

    records = []
    prob = build_problem(arch)

    for r in shells:
        jitter = rng.normal(0, (r * width) / 3, size=(n_per_shell, len(Xbest)))
        Xs = np.clip(Xbest + jitter, lb, ub)

        for x in Xs:
            _set_x(prob, x); prob.run_model()
            m = _energy_packaging(prob, arch)
            g = _feasibility_g(prob, arch, m)
            feasible = (g <= 0.0).all()
            pfei = m["E_MJ"]/(PAYLOAD_KG*(RANGE_M/1000.0))
            records.append(dict(
                arch=arch["name"],
                key=arch.get("key", arch["name"].lower().replace(" ","_")),
                mtow_star_kg=m["mtow_star"],
                pfei_MJ_per_kg_km=pfei,
                feasible=bool(feasible),
                shell=r
            ))

    prob.cleanup()
    df = pd.DataFrame(records)
    csvname = f"doe_{arch['name'].replace(' ','_')}.csv"
    df.to_csv(csvname, index=False)
    print(f"Saved {len(df)} samples -> {csvname}")
    return df


# ----------------------------- plotting utilities -----------------------------
def _confidence_ellipse(x, y, ax, n_std=2.0, edgecolor='k', facecolor='none', linewidth=1.5, **kwargs):
    """Draw a covariance ellipse; quietly do nothing if not enough points."""
    x = np.asarray(x); y = np.asarray(y)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 3:
        return None
    cov = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    width = 2 * n_std * np.sqrt(max(vals[0], 1e-12))
    height = 2 * n_std * np.sqrt(max(vals[1], 1e-12))
    e = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width, height=height, angle=theta,
        facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth, **kwargs
    )
    ax.add_patch(e)
    return e

def plot_cluster_for_arch(df_arch_row, cloud_df, outfile_png=None, show=False):
    """
    Per-architecture DOE cluster plot.
    df_arch_row: pandas Series with arch, mtow_star_kg, pfei_MJ_per_kg_km, key
    cloud_df: DataFrame with columns ['mtow_star_kg','pfei_MJ_per_kg_km','feasible', ...]
    """
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(9.2, 7.0))
    arch_name = df_arch_row['arch']
    key = df_arch_row.get('key', arch_name.lower().replace(" ", "_"))
    color = ARCH_COLORS.get(key, '#333333')

    if cloud_df is None or cloud_df.empty:
        ax.scatter(df_arch_row['mtow_star_kg'], df_arch_row['pfei_MJ_per_kg_km'],
                   s=220, marker='*', c=color, edgecolors='k', linewidths=0.9, label='best')
        ax.set_xlabel("MTOW [kg]")
        ax.set_ylabel("PFEI [MJ/(kg·km)]")
        ax.set_title(f"{arch_name} DOE (pymoo local optimization): PFEI vs MTOW")
        if outfile_png:
            plt.tight_layout()
            plt.savefig(outfile_png, dpi=160)
        if show: plt.show()
        plt.close(fig)
        return

    ok = cloud_df['mtow_star_kg'].notna() & cloud_df['pfei_MJ_per_kg_km'].notna()
    df = cloud_df[ok].copy()
    if df.empty:
        ax.scatter(df_arch_row['mtow_star_kg'], df_arch_row['pfei_MJ_per_kg_km'],
                   s=220, marker='*', c=color, edgecolors='k', linewidths=0.9, label='best')
        ax.set_xlabel("MTOW [kg]")
        ax.set_ylabel("PFEI [MJ/(kg·km)]")
        ax.set_title(f"{arch_name} DOE (pymoo local optimization): PFEI vs MTOW")
        if outfile_png:
            plt.tight_layout()
            plt.savefig(outfile_png, dpi=160)
        if show: plt.show()
        plt.close(fig)
        return

    df['feasible'] = df['feasible'].astype(bool)
    samples = df[~df.index.duplicated()]
    feas = samples[samples['feasible']]
    infe = samples[~samples['feasible']]

    print(f"For {arch_name}: Feasible points: {len(feas)}, Infeasible points: {len(infe)}")

    if not infe.empty:
        ax.scatter(infe['mtow_star_kg'], infe['pfei_MJ_per_kg_km'],
                   s=18, alpha=0.08, c="0.6", marker='.', label=f"{arch_name} infeasible")
    if not feas.empty:
        ax.scatter(feas['mtow_star_kg'], feas['pfei_MJ_per_kg_km'],
                   s=48, alpha=0.54, c=color, edgecolors='white', linewidths=0.6, label='samples (optimized)')
        if _HAVE_SNS and len(feas) >= 8:
            try:
                sns.kdeplot(data=feas, x='mtow_star_kg', y='pfei_MJ_per_kg_km',
                            color=color, levels=4, fill=True, alpha=0.14, ax=ax)
            except Exception:
                pass
        _confidence_ellipse(feas['mtow_star_kg'], feas['pfei_MJ_per_kg_km'],
                            ax, n_std=2.0, edgecolor=color, facecolor='none', linewidth=2.0)

    ax.scatter(df_arch_row['mtow_star_kg'], df_arch_row['pfei_MJ_per_kg_km'],
               s=220, marker='*', c=color, edgecolors='k', linewidths=0.9, label='baseline')
    ax.annotate(df_arch_row['arch'],
                (df_arch_row['mtow_star_kg'], df_arch_row['pfei_MJ_per_kg_km']),
                xytext=(10,8), textcoords='offset points', fontsize=11, weight='bold')

    ax.set_xlabel("MTOW [kg]")
    ax.set_ylabel("PFEI [MJ/(kg·km)]")
    ax.set_title(f"{df_arch_row['arch']} DOE (pymoo local optimization): PFEI vs MTOW")
    ax.legend(frameon=True, fontsize=10, loc='best')
    ax.grid(alpha=0.34)

    x = samples['mtow_star_kg'].values; y = samples['pfei_MJ_per_kg_km'].values
    xr = (np.nanmin(x), np.nanmax(x))
    yr = (np.nanmin(y), np.nanmax(y))
    if xr[0] == xr[1]:
        xpad = xr[0]*0.05 if xr[0] != 0.0 else 1.0
    else:
        xpad = 0.06*(xr[1]-xr[0])
    if yr[0] == yr[1]:
        ypad = yr[0]*0.05 if yr[0] != 0.0 else 1e-3
    else:
        ypad = 0.08*(yr[1]-yr[0])
    ax.set_xlim(xr[0]-xpad, xr[1]+xpad)
    ax.set_ylim(max(0.0, yr[0]-ypad), yr[1]+ypad)

    plt.tight_layout()
    if outfile_png:
        plt.savefig(outfile_png, dpi=170)
    if show:
        plt.show()
    plt.close(fig)


def plot_energy_chain(df):
    def chain(arch):
        if arch in ("Conventional ICE","Hydrogen ICE"):
            η_gear=0.97; η_prop=0.78
            return dict(inv=0.0, motor=0.0, gear=1-η_gear, prop=1-η_prop, useful=η_gear*η_prop)
        else:
            η_inv=0.97; η_motor=0.95; η_gear=0.97; η_prop=0.78
            useful=η_inv*η_motor*η_gear*η_prop
            return dict(inv=1-η_inv, motor=1-η_motor, gear=1-η_gear, prop=1-η_prop, useful=useful)
    stacks = [chain(a) for a in df["arch"]]
    labels = df["arch"].tolist()
    inv = np.array([s["inv"] for s in stacks])
    mot = np.array([s["motor"] for s in stacks])
    gear= np.array([s["gear"] for s in stacks])
    prop= np.array([s["prop"] for s in stacks])
    useful = np.array([s["useful"] for s in stacks])
    x = np.arange(len(labels))
    plt.figure(figsize=(11,3.6))
    plt.barh(x, inv, label="inverter loss")
    plt.barh(x, mot, left=inv, label="motor loss")
    plt.barh(x, gear, left=inv+mot, label="gear loss")
    plt.barh(x, prop, left=inv+mot+gear, label="prop loss")
    plt.barh(x, useful, left=inv+mot+gear+prop, label="useful shaft")
    plt.yticks(x, labels)
    plt.xlabel("Fraction of input energy (losses stacked → useful)")
    plt.title("Energy chain breakdown per architecture")
    for i,u in enumerate(useful):
        plt.text(1.005, i, f"η_chain={u:.2f}", va="center")
    plt.legend(ncol=5, bbox_to_anchor=(0.5, -0.2), loc="upper center")
    plt.tight_layout()
    plt.savefig("energy_chain.png", dpi=140, bbox_inches="tight")


def plot_pareto_with_clouds(df_arch, clouds):
    """
    Combined plot (all architectures) using cluster clouds.
    Also creates per-arch plots via plot_cluster_for_arch.
    """
    plt.figure(figsize=(11.0, 7.0))
    for _, r in df_arch.iterrows():
        name = r["arch"]
        key = r.get("key", name.lower().replace(" ", "_"))
        cdf = clouds.get(name)
        color = ARCH_COLORS.get(key, '#333333')
        if cdf is not None and not cdf.empty:
            feas = cdf[cdf["feasible"]]
            infe = cdf[~cdf["feasible"]]
            if not infe.empty:
                plt.scatter(infe["mtow_star_kg"], infe["pfei_MJ_per_kg_km"],
                            s=6, alpha=0.06, c="0.6", marker=".", label=f"{r['arch']} infeasible")
            if not feas.empty:
                plt.scatter(feas["mtow_star_kg"], feas["pfei_MJ_per_kg_km"],
                            s=10, alpha=0.25, c=color, marker="o", label=f"{r['arch']} feasible")
        plt.scatter(r["mtow_star_kg"], r["pfei_MJ_per_kg_km"],
                    s=120, edgecolor="k", linewidth=0.7, c=color, label=f"{r['arch']} best")
        plt.annotate(r["arch"], (r["mtow_star_kg"], r["pfei_MJ_per_kg_km"]),
                     fontsize=9, xytext=(6,6), textcoords="offset points")
        pngname = f"{r['arch'].replace(' ','_')}_DOE.png"
        try:
            plot_cluster_for_arch(r, cdf, outfile_png=pngname, show=False)
        except Exception as e:
            print(Fore.CYAN + f"  ! Failed to create cluster plot for {r['arch']}: {e}" + Fore.RESET)

    plt.xlabel("MTOW* [kg]")
    plt.ylabel("PFEI [MJ/(kg·km)]")
    plt.grid(True, alpha=0.3)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), fontsize=9, loc='best')
    plt.tight_layout()
    plt.savefig("pfei_vs_mtow_clouds.png", dpi=180, bbox_inches="tight")
    plt.close()


# ----------------------------- main -----------------------------
def main():
    rows = []; clouds = {}
    for arch in ARCHES:
        print(Fore.LIGHTGREEN_EX + f"→ Running {arch['name']} ..." + Fore.RESET)
        try:
            r = run_arch_pymoo(arch, pop_size=96, n_gen=160, seed=11)
            print(f"   P_req={r['P_req_kW']:.0f} kW, MTOW*={r['mtow_star_kg']:.0f} kg, PFEI={r['pfei_MJ_per_kg_km']:.4f}")
            rows.append(r)

            cloud = doe_around_best(
                arch, r["Xbest"],
                n_per_shell=1000,
                shells=(0.05, 0.1, 0.15, 0.2, 0.25, 0.3),
                seed=13
            )
            clouds[arch["name"]] = cloud

            pngname = f"{arch['name'].replace(' ','_')}_DOE.png"
            plot_cluster_for_arch(r, cloud, outfile_png=pngname, show=True)
        except Exception as e:
            print(Fore.RED + f"   FAILED: {e}" + Fore.RESET)
            rows.append(dict(arch=arch["name"], key=arch.get("key", arch["name"].lower().replace(" ","_"))))

    df = pd.DataFrame(rows)
    df.to_csv("architectures_pymoo_with_doe.csv", index=False)
    print(Fore.LIGHTGREEN_EX + "Saved CSV -> architectures_pymoo_with_doe.csv" + Fore.RESET)

    print("\nSummary:")
    print(df[["arch","P_req_kW","P_installed_kW","P_margin_kW","mtow_star_kg","pfei_MJ_per_kg_km"]])

    plot_energy_chain(df)
    plot_pareto_with_clouds(df, clouds)
    print(Fore.LIGHTGREEN_EX + "Saved combined figure -> pfei_vs_mtow_clouds.png" + Fore.RESET)
    print(Fore.LIGHTGREEN_EX + "Saved per-architecture DOE PNGs" + Fore.RESET)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)