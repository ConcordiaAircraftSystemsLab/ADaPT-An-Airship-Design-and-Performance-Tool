# -*- coding: utf-8 -*-
"""
@author: Musavir Bashir
"""


from __future__ import annotations
import streamlit as st


# ---------------------------------------------------------------------
# Validation sidebar (now supports 3 airship types)
# ---------------------------------------------------------------------
def sidebar_a170_inputs() -> dict:
    st.sidebar.header("Validation Inputs")

    # -----------------------
    # Airship Type / Case
    # -----------------------
    st.sidebar.subheader("Validation Case")
    validation_case = st.sidebar.selectbox(
        "Select airship validation case",
        options=[
            "A-170 (Non-rigid)",
            "DGPA 50T (Rigid)",
            "Zeppelin NT (Semi-rigid)",
        ],
        index=0,
    )

    is_rigid = validation_case.startswith("DGPA")
    is_semi  = validation_case.startswith("Zeppelin")
    is_8dv   = is_rigid or is_semi

    st.sidebar.caption(
        "Non-rigid uses 6 DVs; Rigid/Semi-rigid use 8 DVs (+Cd0 +Thrust Vector)."
    )

    # -----------------------
    # Mission
    # -----------------------
    st.sidebar.subheader("Mission")

    # Defaults depend on case (Can be tuned as per the airship config.)
    if "DGPA" in validation_case:
        default_range_m = 2_800_000.0
        default_payload = 50_000.0
        default_speed   = 36.1
        default_alt     = 3000.0
        default_T       = 268.65
    elif "Zeppelin" in validation_case:
        default_range_m = 1_000_000.0
        default_payload = 1900.0
        default_speed   = 31.0
        default_alt     = 600.0
        default_T       = 288.15
    else:
        default_range_m = 1_342_100.0
        default_payload = 1123.0
        default_speed   = 19.5
        default_alt     = 914.0
        default_T       = 281.65

    range_m = st.sidebar.number_input(
        "Range [m]", value=float(default_range_m), step=10_000.0, format="%.1f"
    )
    payload_kg = st.sidebar.number_input(
        "Payload [kg]", value=float(default_payload), step=10.0, format="%.1f"
    )
    cruise_speed_ms = st.sidebar.number_input(
        "Cruise speed [m/s]", value=float(default_speed), step=0.1, format="%.2f"
    )
    altitude_m = st.sidebar.number_input(
        "Cruise altitude [m]", value=float(default_alt), step=10.0, format="%.1f"
    )
    disa_K = st.sidebar.number_input(
        "Cruise DISA [K]", value=0.0, step=1.0, format="%.1f"
    )
    RH = st.sidebar.number_input(
        "Relative humidity RH [%]", value=70.0, step=1.0, format="%.1f"
    )
    T_env = st.sidebar.number_input(
        "Ambient temperature T_env [K] (optional)",
        value=float(default_T),
        step=0.5,
        format="%.2f",
    )
    time_of_day = st.sidebar.selectbox("Time of day", ["day", "night"], index=0)

    # -----------------------
    # Geometry
    # -----------------------
    st.sidebar.subheader("Geometry")

    if "DGPA" in validation_case:
        default_length = 169.0
        default_fin    = 5.12
    elif "Zeppelin" in validation_case:
        default_length = 75.0
        default_fin    = 4.3
    else:
        default_length = 53.4
        default_fin    = 4.0

    length_m = st.sidebar.number_input(
        "Length [m]", value=float(default_length), step=0.1, format="%.3f"
    )
    fineness_ratio = st.sidebar.number_input(
        "Fineness ratio [-]", value=float(default_fin), step=0.05, format="%.3f"
    )

    # -----------------------
    # Tail / Aero
    # -----------------------
    st.sidebar.subheader("Tail / Aero")

    if "DGPA" in validation_case:
        default_tvc_h = 0.060
        default_tvc_v = 0.055
        default_cl    = 0.16
        default_k     = 0.80
    elif "Zeppelin" in validation_case:
        default_tvc_h = 0.065
        default_tvc_v = 0.058
        default_cl    = 0.15
        default_k     = 0.80
    else:
        default_tvc_h = 0.066
        default_tvc_v = 0.059
        default_cl    = 0.15
        default_k     = 0.869

    tail_volume_coeff_horizontal = st.sidebar.number_input(
        "Tail volume coeff (horizontal)", value=float(default_tvc_h), step=0.001, format="%.4f"
    )
    tail_volume_coeff_vertical = st.sidebar.number_input(
        "Tail volume coeff (vertical)", value=float(default_tvc_v), step=0.001, format="%.4f"
    )
    lift_coeff = st.sidebar.number_input(
        "Lift coefficient C_L [-]", value=float(default_cl), step=0.005, format="%.3f"
    )
    k_lift = st.sidebar.number_input(
        "Induced drag factor K [-] (drag due to lift)", value=float(default_k), step=0.01, format="%.3f"
    )

    # Extra aero knobs (ONLY for rigid / semi-rigid)
    drag_coeff_zero = None
    thrust_vector_angle_deg = None
    if is_8dv:
        st.sidebar.subheader("Extra Aero (Rigid / Semi-rigid)")
        drag_coeff_zero = st.sidebar.number_input(
            "Zero-lift drag Cd0 [-]",
            value=0.040 if is_rigid else 0.038,
            step=0.001,
            format="%.4f",
        )
        thrust_vector_angle_deg = st.sidebar.number_input(
            "Thrust vector angle [deg]",
            value=0.0,
            step=0.5,
            format="%.2f",
        )

    # -----------------------
    # Propulsion / Power
    # -----------------------
    st.sidebar.subheader("Propulsion / Power")

    if "DGPA" in validation_case:
        default_power = 8_113_000.0
        default_n_eng = 4
        default_eta_p = 0.70
    elif "Zeppelin" in validation_case:
        default_power = 441_000.0
        default_n_eng = 3
        default_eta_p = 0.75
    else:
        default_power = 268_000.0
        default_n_eng = 2
        default_eta_p = 0.75

    engine_power_W = st.sidebar.number_input(
        "Installed power [W] (total or per engine per model)",
        value=float(default_power),
        step=10_000.0,
        format="%.1f",
    )
    n_engine = st.sidebar.number_input(
        "Number of engines", value=int(default_n_eng), step=1, min_value=1
    )
    eta_p = st.sidebar.number_input(
        "Propeller efficiency η_p [-]", value=float(default_eta_p), step=0.01, format="%.3f"
    )

    # -----------------------
    # Mass / Gas / Crew
    # -----------------------
    st.sidebar.subheader("Mass / Gas / Crew")

    if "DGPA" in validation_case:
        default_fuel = 20_000.0
        default_crew = 5
    elif "Zeppelin" in validation_case:
        default_fuel = 1100.0
        default_crew = 1
    else:
        default_fuel = 599.0
        default_crew = 1

    fuel_onboard_kg = st.sidebar.number_input(
        "Fuel onboard [kg]", value=float(default_fuel), step=10.0, format="%.2f"
    )
    storage_type = st.sidebar.selectbox(
        "Lift gas / storage type", options=["helium", "hydrogen"], index=0
    )
    n_crew = st.sidebar.number_input(
        "Crew count", value=int(default_crew), step=1, min_value=0
    )

    # -----------------------
    # Semi-rigid-only inputs
    # -----------------------
    zero_alt_m = None
    zero_disa_K = None
    ballast_mass_kg = None
    bsfc_kg_W_s = None
    tailwind_speed_ms = None
    n_longitudinal_members = None
    n_rings = None
    ascent_rate_mps = None
    descent_rate_mps = None
    takeoff_altitude_m = None
    max_operating_altitude_m = None

    if is_semi:
        st.sidebar.subheader("Semi-rigid Settings (Zeppelin)")
        zero_alt_m = st.sidebar.number_input("zero_alt [m]", value=0.0, step=10.0, format="%.1f")
        zero_disa_K = st.sidebar.number_input("zero_disa [K]", value=0.0, step=1.0, format="%.1f")
        ballast_mass_kg = st.sidebar.number_input("Ballast mass [kg]", value=0.0, step=10.0, format="%.1f")
        bsfc_kg_W_s = st.sidebar.number_input("BSFC [kg/W/s]", value=7.6034e-8, format="%.8e")
        tailwind_speed_ms = st.sidebar.number_input("Tailwind speed [m/s]", value=0.0, step=0.5, format="%.2f")
        n_longitudinal_members = st.sidebar.number_input("n_longitudinal_members", value=18.0, step=1.0, format="%.1f")
        n_rings = st.sidebar.number_input("n_rings", value=25.0, step=1.0, format="%.1f")

        st.sidebar.subheader("Pressure Control Drivers (optional)")
        ascent_rate_mps = st.sidebar.number_input("ascent_rate [m/s]", value=1.0, step=0.1, format="%.2f")
        descent_rate_mps = st.sidebar.number_input("descent_rate [m/s]", value=1.0, step=0.1, format="%.2f")
        takeoff_altitude_m = st.sidebar.number_input("takeoff_altitude [m]", value=0.0, step=10.0, format="%.1f")
        max_operating_altitude_m = st.sidebar.number_input("max_operating_altitude [m]", value=float(altitude_m), step=50.0, format="%.1f")

    # -----------------------
    # Feasibility Solve Options
    # -----------------------
    st.sidebar.subheader("Feasibility Solve")
    solve_br = st.sidebar.toggle(
        "Solve BR_takeoff for buoyancy (recommended for stability)",
        value=True,
    )

    br_guess = st.sidebar.number_input(
        "BR_takeoff initial guess [-]", value=0.83, step=0.01, format="%.3f"
    )
    br_lo = st.sidebar.number_input(
        "BR_takeoff lower bound", value=0.50, step=0.01, format="%.2f"
    )
    br_hi = st.sidebar.number_input(
        "BR_takeoff upper bound", value=1.00, step=0.01, format="%.2f"
    )

    # -----------------------
    # Constraints (for reporting / UI checks)
    # -----------------------
    st.sidebar.subheader("Constraints (reporting)")
    ground_roll_limit_m = st.sidebar.number_input(
        "Ground roll limit [m]", value=450.0, step=10.0, format="%.1f"
    )

    # default MTOW bounds depend on case
    if "DGPA" in validation_case:
        default_mtow_lo = 110_000.0
        default_mtow_hi = 150_000.0
    elif "Zeppelin" in validation_case:
        default_mtow_lo = 7500.0
        default_mtow_hi = 9500.0
    else:
        default_mtow_lo = 5000.0
        default_mtow_hi = 7000.0

    mtow_lo_kg = st.sidebar.number_input(
        "MTOW lower bound [kg]", value=float(default_mtow_lo), step=100.0, format="%.1f"
    )
    mtow_hi_kg = st.sidebar.number_input(
        "MTOW upper bound [kg]", value=float(default_mtow_hi), step=100.0, format="%.1f"
    )

    # -----------------------
    # pymoo controls
    # -----------------------
    st.sidebar.subheader("pymoo (DE) Optimization")
    use_pymoo = st.sidebar.checkbox("Run pymoo optimization", value=True)
    pop_size = st.sidebar.slider("Population size", 40, 300, 160, step=20)
    n_gen = st.sidebar.slider("Generations", 50, 500, 300, step=50)
    seed = st.sidebar.number_input("Seed", value=11, step=1)

    # -----------------------
    # Return a SINGLE, stable config dict
    # -----------------------
    cfg = dict(
    
        airship_type="rigid" if is_rigid else "semi-rigid" if is_semi else "non-rigid",
        # NEW: case selection
        validation_case=validation_case,

        # environment / opCond
        altitude_m=altitude_m,
        T_env=T_env,
        RH=RH,
        time=time_of_day,
        cruise_speed_ms=cruise_speed_ms,
        disa_K=disa_K,

        # mission
        range_m=range_m,
        payload_kg=payload_kg,

        # geometry
        length_m=length_m,
        fineness_ratio=fineness_ratio,

        # aero / tail (common)
        tvc_h=tail_volume_coeff_horizontal,
        tvc_v=tail_volume_coeff_vertical,
        lift_coeff=lift_coeff,
        k_lift=k_lift,

        # propulsion
        engine_power_W=engine_power_W,
        n_engine=int(n_engine),
        eta_p=eta_p,

        # mass / gas / crew
        fuel_onboard_kg=fuel_onboard_kg,
        storage_type=storage_type,
        n_crew=int(n_crew),

        # solve options
        solve_br=solve_br,
        br_guess=br_guess,
        br_lo=br_lo,
        br_hi=br_hi,

        # constraints reporting
        ground_roll_limit_m=ground_roll_limit_m,
        mtow_lo_kg=mtow_lo_kg,
        mtow_hi_kg=mtow_hi_kg,

        # pymoo
        use_pymoo=use_pymoo,
        pop_size=int(pop_size),
        n_gen=int(n_gen),
        seed=int(seed),
    )

    # Add 8DV extras only when relevant
    if is_8dv:
        cfg["drag_coeff_zero"] = float(drag_coeff_zero)
        cfg["thrust_vector_angle_deg"] = float(thrust_vector_angle_deg)

    # Add semi-rigid extras only when relevant
    if is_semi:
        cfg.update(
            dict(
                zero_alt_m=float(zero_alt_m),
                zero_disa_K=float(zero_disa_K),
                ballast_mass_kg=float(ballast_mass_kg),
                bsfc_kg_W_s=float(bsfc_kg_W_s),
                tailwind_speed_ms=float(tailwind_speed_ms),
                n_longitudinal_members=float(n_longitudinal_members),
                n_rings=float(n_rings),
                ascent_rate_mps=float(ascent_rate_mps),
                descent_rate_mps=float(descent_rate_mps),
                takeoff_altitude_m=float(takeoff_altitude_m),
                max_operating_altitude_m=float(max_operating_altitude_m),
            )
        )

    return cfg


# ---------------------------------------------------------------------
# MDA sidebar (UNCHANGED)
# ---------------------------------------------------------------------
def sidebar_mda_inputs() -> dict:
    st.sidebar.header("MDA Inputs")

    st.sidebar.subheader("Mission")
    range_m = st.sidebar.number_input("Range [m]", value=1_342_100.0, step=10_000.0)
    payload_kg = st.sidebar.number_input("Payload [kg]", value=1123.0, step=10.0)

    st.sidebar.subheader("Cruise")
    cruise_speed_mps = st.sidebar.number_input("Cruise speed [m/s]", value=19.5, step=0.1)
    cruise_alt_m = st.sidebar.number_input("Cruise altitude [m]", value=914.0, step=10.0)
    cruise_disa_K = st.sidebar.number_input("Cruise DISA [K]", value=0.0, step=1.0)

    st.sidebar.subheader("Environment")
    RH_pct = st.sidebar.number_input("Relative humidity [%]", value=70.0, step=1.0)
    T_env_K = st.sidebar.number_input("Ambient temperature [K]", value=281.65, step=0.5)
    time_of_day = st.sidebar.selectbox("Time of day", ["day", "night"], index=0)

    st.sidebar.subheader("Geometry")
    length_m = st.sidebar.number_input("Length [m]", value=53.4, step=0.1)
    fineness_ratio = st.sidebar.number_input("Fineness ratio [-]", value=4.0, step=0.05)

    st.sidebar.subheader("Aero / Takeoff")
    BR_takeoff = st.sidebar.number_input("BR_takeoff [-]", value=0.83, step=0.01)
    lift_coeff = st.sidebar.number_input("Lift coefficient C_L [-]", value=0.15, step=0.005)
    drag_due_to_lift_factor = st.sidebar.number_input("Induced drag factor K [-]", value=0.869, step=0.01)

    st.sidebar.subheader("Propulsion")
    engine_power_W = st.sidebar.number_input("Installed power [W] (model-defined: total or per engine)", value=268_000.0, step=10_000.0)
    n_engine = st.sidebar.number_input("Number of engines", value=2, step=1, min_value=1)
    propeller_efficiency = st.sidebar.number_input("Propeller efficiency η_p [-]", value=0.75, step=0.01)

    st.sidebar.subheader("Fuel / Gas")
    fuel_mass_kg = st.sidebar.number_input("Fuel onboard [kg]", value=599.0, step=10.0)
    storage_type = st.sidebar.selectbox("Lift gas / storage type", options=["helium", "hydrogen"], index=0)
    n_crew = st.sidebar.number_input("Crew count", value=1, step=1, min_value=0)

    return dict(
        # matches ui/run_mda.py expectations:
        range_m=range_m,
        payload_kg=payload_kg,
        cruise_speed_mps=cruise_speed_mps,
        cruise_alt_m=cruise_alt_m,
        cruise_disa_K=cruise_disa_K,
        RH_pct=RH_pct,
        T_env_K=T_env_K,
        time=time_of_day,

        length_m=length_m,
        fineness_ratio=fineness_ratio,

        BR_takeoff=BR_takeoff,
        lift_coeff=lift_coeff,
        drag_due_to_lift_factor=drag_due_to_lift_factor,

        engine_power_W=engine_power_W,
        n_engine=int(n_engine),
        propeller_efficiency=propeller_efficiency,

        fuel_mass_kg=fuel_mass_kg,
        storage_type=storage_type,
        n_crew=int(n_crew),
    )
