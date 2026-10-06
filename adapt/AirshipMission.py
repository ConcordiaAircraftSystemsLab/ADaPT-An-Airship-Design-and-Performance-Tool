# -*- coding: utf-8 -*-
"""
Airship Mission Component for ADaPT

Purpose
-------
Core mission analysis module that evaluates the aircraft performance over the
specified mission profile and generates the propulsion, energy, and operational
requirements used by downstream subsystem sizing models.

This component serves as the central multidisciplinary coupling module within
the ADaPT framework, linking aerodynamics, propulsion, energy storage,
atmospheric conditions, and vehicle performance.

The component provides:
    - Cruise, takeoff, and landing performance
    - Propulsion thrust and shaft power requirements
    - Mission energy and fuel/battery consumption
    - Flight endurance and mission time
    - Aerodynamic forces and drag
    - Operational performance metrics
    - Mission feasibility constraints for optimization

Model responsibilities
----------------------
    - Compute cruise equilibrium and aerodynamic performance.
    - Evaluate propulsion thrust and shaft power requirements.
    - Estimate mission duration, endurance, and energy consumption.
    - Size mission fuel or battery requirements for multiple powertrain
      architectures.
    - Evaluate takeoff, landing, climb, descent, and turning performance.
    - Compute buoyancy and aerodynamic lift requirements.
    - Generate multidisciplinary design constraints for optimization,
      including:
          * Power availability
          * Energy availability
          * Buoyancy
          * Lift capability
          * Takeoff field length
          * Landing distance
    - Support conventional, hydrogen, battery-electric, solar-electric,
      and hybrid propulsion architectures through a unified formulation.

Model assumptions
-----------------
    - The mission is evaluated using quasi-steady flight mechanics.
    - Cruise is assumed to satisfy force equilibrium between buoyancy,
      aerodynamic lift, weight, thrust, and drag.
    - Fuel, hydrogen, and battery consumption are computed from the required
      propeller shaft energy using architecture-dependent conversion
      efficiencies.
    - Atmospheric properties are obtained from the operating conditions model.
    - The component performs conceptual mission analysis and is intended for
      multidisciplinary design optimization rather than high-fidelity flight
      simulation.

Outputs
-------
    - Mission time and endurance
    - Required propulsion thrust and shaft power
    - Mission energy demand
    - Fuel and battery mass requirements
    - Aerodynamic lift and drag
    - Takeoff and landing performance
    - Climb, descent, and turning performance
    - Mission feasibility constraints for MDO

@author: Musavir Bashir
"""
import numpy as np
import openmdao.api as om
try:
    # Package mode
    from .operatingConditions import opCond
except ImportError:
    # Standalone/script mode
    from operatingConditions import opCond
    

FUEL_SOURCES = ['conventional_reciprocating', 'hydrogen_reciprocating', 'hydrogen_fuel_cell']
BATTERY_SOURCES = ['battery_only', 'solar_battery', 'solar-RFC']

HYBRID_SOURCES = [
    'hydrogen_hybrid',
    'solar_hydrogen_hybrid',
    'conventional_battery_hybrid',
]

HYDROGEN_HYBRIDS = ['hydrogen_hybrid', 'solar_hydrogen_hybrid']
ICE_HYBRIDS = ['conventional_battery_hybrid']
SOLAR_HYBRIDS = ['solar_hydrogen_hybrid']


# chemical -> shaft conversion efficiency and fuel LHV by source
SOURCE_FUEL = {
    'conventional_reciprocating': {'LHV': 43.0e6,  'eta_chem2shaft': 0.30 * 0.98},
    'hydrogen_reciprocating':     {'LHV': 120.0e6, 'eta_chem2shaft': 0.30 * 0.98},
    'hydrogen_fuel_cell':         {'LHV': 120.0e6, 'eta_chem2shaft': 0.55 * 0.95 * 0.98},
    # hydrogen_hybrid does NOT use a single fixed eta_chem2shaft — its H2 share
    # uses the (possibly dynamic) eta_fc, its battery share uses chi/tau directly.
    # See energy_constraint branch below.
}


class AirshipMission(om.ExplicitComponent):
    def initialize(self):
        self.options.declare('phd', types=object)
        self.options.declare(
                            'power_source',
                            default='conventional_reciprocating',
                            values=[
                                'conventional_reciprocating',
                                'hydrogen_reciprocating',
                                'hydrogen_fuel_cell',
                                'battery_only',
                                'solar_battery',
                                'solar-RFC',
                                'hydrogen_hybrid',
                                'solar_hydrogen_hybrid',
                                'conventional_battery_hybrid',
                            ],
                        )
        self.options.declare('num_steps', default=1, types=int)
        self.options.declare('landing_system', default='conventional',
                             values=['conventional', 'acls'])
        self.options.declare('airship_type', default='non-rigid',
                             values=['non-rigid', 'semi-rigid', 'rigid'])

        # operating / limits (no longer hardcoded)
        self.options.declare('takeoff_speed', default=19.0, types=float)
        self.options.declare('C_L_takeoff', default=0.175, types=float)
        self.options.declare('C_L_max', default=0.60, types=float)
        self.options.declare('field_length_limit', default=450.0, types=float)
        self.options.declare('fuel_reserve_factor', default=1.05, types=float)
        self.options.declare('drivetrain_eff_electric', default=0.95 * 0.98 * 0.98, types=float)
        self.options.declare('eta_fc_fallback', default=0.55, types=float,
                             desc='Flat FC efficiency for hydrogen_hybrid when '
                                  'eta_fc_dynamic is not connected upstream')

        # pressure control (optional)
        self.options.declare('enable_pressure_control', default=False, types=bool)
        self.options.declare('pressure_control_base_power', default=0.0, types=float)
        self.options.declare('pressure_control_fraction_of_prop_power', default=0.0, types=float)

    def setup(self):
        n = self.options['num_steps']
        ps = self.options['power_source']

        self.add_input('range', val=1342100.0, units='m')
        self.add_input('cruise_altp', val=np.full(n, 914.0), units='m')
        self.add_input('cruise_disa', val=np.zeros(n), units='K')
        self.add_input('cruise_speed', val=np.full(n, 31.0), units='m/s')
        self.add_input('n_engine', val=2)
        self.add_input('gross_area', units='m**2')
        self.add_input('gross_volume', units='m**3')
        self.add_input('fin_area', units='m**2')
        self.add_input('planform_area', units='m**2')
        self.add_input('aspect_ratio')
        self.add_input('length', val=53.6, units='m')
        self.add_input('operational_weight', units='kg')
        self.add_input('engine_power', val=np.full(n, 134000.0), units='W')
        self.add_input('pamb_cruise', val=np.full(n, 89876.0), units='Pa')
        self.add_input('tamb_cruise', val=np.full(n, 281.65), units='K')
        self.add_input('pamb_to', val=np.full(n, 101325.0), units='Pa')
        self.add_input('tamb_to', val=np.full(n, 288.15), units='K')
        self.add_input('he_max_mass', units='kg')
        self.add_input('mtow', units='kg')
        self.add_input('ballast_mass', units='kg')
        self.add_input('lift_coeff', val=0.15)
        self.add_input('drag_due_to_lift_factor', val=0.869)
        self.add_input('drag_coeff_zero', val=0.03542)
        self.add_input('BR_takeoff', val=0.856)
        self.add_input('BR_landing', val=0.90)
        self.add_input('tailwind_speed', val=0.0, units='m/s')
        self.add_input('thrust_vector_angle', val=0.0, units='deg')
        self.add_input('rudder_deflection', val=28.0, units='deg')
        self.add_input('cruise_strategy', val=1)
        self.add_input('propeller_efficiency', val=0.75)

        if ps in FUEL_SOURCES:
            self.add_input('fuel_onboard_mass', val=599.0, units='kg')

        if ps in BATTERY_SOURCES:
            self.add_input('battery_specific_energy', val=200.0, units='W*h/kg')
            self.add_input('battery_dod', val=0.80)
            self.add_input('battery_eta', val=0.95)
            self.add_input('available_energy_mass', val=1.0e6, units='kg',
                           desc='Onboard battery mass; CONNECT from battery sizing component')
            self.add_input('solar_energy_recovered', val=0.0, units='W*h',
                           desc='Mission solar energy (0 for pure battery)')

        if ps in HYBRID_SOURCES:
            self.add_input('fuel_onboard_mass', val=120.0, units='kg',
                           desc='Primary fuel mass: H2 for hydrogen hybrids, gasoline for ICE hybrid')
            self.add_input('battery_specific_energy', val=200.0, units='W*h/kg')
            self.add_input('battery_dod', val=0.80)
            self.add_input('battery_eta', val=0.95)
            self.add_input('available_energy_mass', val=1.0e6, units='kg',
                           desc='Onboard battery mass from BatteryOnly sizing component')
            self.add_input('chi', val=0.10)
            self.add_input('tau', val=0.10)

            if ps in HYDROGEN_HYBRIDS:
                self.add_input('eta_fc_dynamic', val=np.full(n, -1.0))

            if ps in SOLAR_HYBRIDS:
                self.add_input('solar_energy_recovered', val=0.0, units='W*h')

        if self.options['landing_system'] == 'acls':
            self.add_input('acls_area', val=377.0, units='m**2')

        if self.options['enable_pressure_control']:
            self.add_input('ascent_rate', val=1.0, units='m/s')
            self.add_input('descent_rate', val=1.0, units='m/s')
            self.add_input('takeoff_altitude', val=0.0, units='m')
            self.add_input('max_operating_altitude', val=914.0, units='m')

        # --- outputs ---
        self.add_output('power_constraint', val=np.zeros(n), units='W')   # P_sh - P_avail <= 0
        self.add_output('energy_constraint', val=0.0, units='kg')         # req - avail   <= 0
        self.add_output('buoyancy_constraint', units='N')                 # L_buoy_req - L_buoy_avail <= 0
        self.add_output('lift_constraint', val=0.0)                       # C_L - C_L_max <= 0
        self.add_output('ground_constraint', val=0.0, units='m')          # s_gr - limit  <= 0
        self.add_output('landing_constraint', val=0.0, units='m')         # s_land- limit <= 0

        self.add_output('aerodynamic_lift_cruise', val=np.zeros(n), units='N')
        self.add_output('thrust_to', units='N')
        self.add_output('thrust_cruise', val=np.zeros(n), units='N')
        self.add_output('time', val=0.0, units='s')
        self.add_output('fuel_mass', val=np.zeros(n), units='kg')
        self.add_output('mission_energy_required', val=0.0, units='J')
        self.add_output('battery_mass_required', val=0.0, units='kg')
        self.add_output('ground_roll_distance', units='m')
        self.add_output('landing_distance', units='m')
        self.add_output('endurance', val=0.0)
        self.add_output('roc', val=0.0, units='m/s')
        self.add_output('rod', val=0.0, units='m/s')
        self.add_output('turn_time', val=0.0, units='s')
        self.add_output('ballast_constraint', units='kg')
        self.add_output('stability_margin', val=0.1)
        self.add_output('drag_cruise', val=np.zeros(n), units='N')
        self.add_output('drag_takeoff_avg', val=0.0, units='N')
        self.add_output('drag_landing', val=0.0, units='N')

        if ps in HYBRID_SOURCES:
            self.add_output('energy_constraint_primary', val=0.0, units='kg',
                            desc='Hydrogen sub-constraint: H2 required - available <= 0')
            self.add_output('energy_constraint_bat', val=0.0, units='kg',
                            desc='Battery sub-constraint: battery required - available <= 0')
            self.add_output('eta_fc_used', val=0.55,
                            desc='FC efficiency actually used in sizing this pass')
            self.add_output('chi_consistency_error', val=0.0,
                            desc='Implied chi (from sized capacities) minus specified chi. '
                                 '0 = the (tau, chi) design point is self-consistent.')
            self.add_output('chi_implied', val=0.10,
                            desc='Energy hybridization degree implied by actual sized '
                                 'battery and H2 tank capacities')

        if self.options['enable_pressure_control']:
            self.add_output('pressure_control_power', val=np.zeros(n), units='W')
            self.add_output('pressure_control_energy', val=0.0, units='J')

        self.declare_partials('*', '*', method='fd', step=1e-8)

    def compute(self, inputs, outputs):
        opt = self.options
        phd = opt['phd']
        n = opt['num_steps']
        ps = opt['power_source']
        landing_system = opt['landing_system']
        g = 9.80665

        prop_eff = float(np.clip(np.asarray(inputs['propeller_efficiency']).ravel()[0], 0.6, 0.95))
        takeoff_speed = opt['takeoff_speed']
        C_L_takeoff = opt['C_L_takeoff']
        C_L_max = opt['C_L_max']
        field_limit = opt['field_length_limit']

        # ---- guarded inputs ----
        range_m = float(max(inputs['range'], 1e3))
        cruise_speed = np.maximum(inputs['cruise_speed'], 1.0)
        n_engine = max(int(inputs['n_engine']), 1)
        gross_area = float(max(inputs['gross_area'], 1.0))
        planform_area = float(max(inputs['planform_area'], 1.0))
        length = float(max(inputs['length'], 10.0))

        engine_power = np.maximum(inputs['engine_power'], 1e3)
        pamb_cruise = np.maximum(inputs['pamb_cruise'], 1e3)
        tamb_cruise = np.maximum(inputs['tamb_cruise'], 200.0)
        pamb_to = float(max(inputs['pamb_to'][0], 1e3))
        tamb_to = float(max(inputs['tamb_to'][0], 200.0))

        he_mass = float(max(inputs['he_max_mass'], 1.0))
        mtow = float(max(inputs['mtow'], 1e3))
        ballast_mass = float(max(inputs['ballast_mass'], 0.0))

        C_L = float(inputs['lift_coeff'])
        K = float(inputs['drag_due_to_lift_factor'])
        C_D0 = float(inputs['drag_coeff_zero'])
        BR_takeoff = float(np.clip(inputs['BR_takeoff'], 0.4, 0.99))
        BR_landing = float(np.clip(inputs['BR_landing'], 0.7, 1.0))
        thrust_angle = float(np.clip(inputs['thrust_vector_angle'], -90.0, 90.0))
        tailwind_speed = float(inputs['tailwind_speed'])
        cruise_strategy = int(inputs['cruise_strategy'])

        eff_speed = max(float(cruise_speed[0] - tailwind_speed), 0.5)

        rho_cruise = np.maximum(phd.gas_density(pamb_cruise, tamb_cruise), 1e-3)
        rho_to = float(max(phd.gas_density(pamb_to, tamb_to), 1e-3))

        q_cruise = 0.5 * rho_cruise * cruise_speed**2
        W_H = mtow * g * (1 - BR_takeoff)
        L_buoy = BR_takeoff * mtow * g

        # ---- cruise equilibrium ----
        C_L_raw = C_L  # for lift constraint
        if cruise_strategy == 1:
            C_L_raw = float(W_H / (q_cruise[0] * planform_area))
            C_L_cruise = np.clip(C_L_raw, -0.2, 1.2)   # numerical guard for drag
            D_cruise = q_cruise * gross_area * (C_D0 + K * C_L_cruise**2)
            V_used = cruise_speed
        elif cruise_strategy == 2:
            C_L_opt = np.sqrt(C_D0 / K)
            C_L_raw = float(C_L_opt)
            C_L_cruise = C_L_opt
            V = np.sqrt(2 * W_H / (rho_cruise * planform_area * C_L_opt))
            q_var = 0.5 * rho_cruise * V**2
            D_cruise = q_var * gross_area * (C_D0 + K * C_L_opt**2)
            V_used = V
        else:
            C_L_opt = np.sqrt(C_D0 / K)
            C_L_raw = float(C_L_opt)
            C_L_cruise = C_L_opt
            D_cruise = q_cruise * gross_area * (C_D0 + K * C_L_opt**2)
            V_used = cruise_speed

        T_cruise = np.maximum(D_cruise, 0.0)
        P_shaft = T_cruise * V_used / prop_eff
        time_s = range_m / eff_speed
        endurance = time_s / 3600.0

        # ---- energy & fuel / battery (single physical model) ----
        E_shaft = float(np.mean(P_shaft)) * time_s                 # J at propeller shaft
        outputs['mission_energy_required'] = E_shaft

        fuel_mass = 0.0
        battery_mass_required = 0.0
        if ps in FUEL_SOURCES:
            par = SOURCE_FUEL[ps]
            fuel_mass = (E_shaft / (par['eta_chem2shaft'] * par['LHV'])
                         * opt['fuel_reserve_factor'])
            available = float(inputs['fuel_onboard_mass'])
            energy_constraint = fuel_mass - available            # req - avail <= 0
        elif ps in BATTERY_SOURCES:
            e_spec = float(np.asarray(inputs['battery_specific_energy']).flat[0])
            dod = float(np.asarray(inputs['battery_dod']).flat[0])
            eta_b = float(np.asarray(inputs['battery_eta']).flat[0])
            eta_dt = opt['drivetrain_eff_electric']

            E_elec_Wh = (E_shaft / eta_dt) / 3600.0

            if ps in ['solar_battery', 'solar-RFC']:
                E_solar_Wh = float(np.asarray(inputs['solar_energy_recovered']).flat[0])
            else:
                E_solar_Wh = 0.0

            E_net_Wh = max(E_elec_Wh - E_solar_Wh, 0.0)
            battery_mass_required = E_net_Wh / max(e_spec * dod * eta_b, 1e-6)

            available_mass = float(np.asarray(inputs['available_energy_mass']).flat[0])
            energy_constraint = battery_mass_required - available_mass
        elif ps in HYBRID_SOURCES:
            eta_dt = opt['drivetrain_eff_electric']
            E_elec_total_Wh = (E_shaft / eta_dt) / 3600.0

            chi = float(np.clip(np.asarray(inputs['chi']).flat[0], 0.0, 0.999))
            tau = float(np.clip(np.asarray(inputs['tau']).flat[0], 0.0, 0.95))

            if ps in SOLAR_HYBRIDS:
                E_solar_Wh = float(np.asarray(inputs['solar_energy_recovered']).flat[0])
            else:
                E_solar_Wh = 0.0

            E_after_solar_Wh = max(E_elec_total_Wh - E_solar_Wh, 0.0)

            E_bat_req_Wh = tau * E_after_solar_Wh
            E_primary_req_Wh = (1.0 - tau) * E_after_solar_Wh

            e_spec = float(np.asarray(inputs['battery_specific_energy']).flat[0])
            dod = float(np.asarray(inputs['battery_dod']).flat[0])
            eta_b = float(np.asarray(inputs['battery_eta']).flat[0])

            battery_mass_required = E_bat_req_Wh / max(e_spec * dod * eta_b, 1e-6)
            available_bat = float(np.asarray(inputs['available_energy_mass']).flat[0])
            g_bat = battery_mass_required - available_bat

            if ps in HYDROGEN_HYBRIDS:
                eta_fc_in = float(np.asarray(inputs['eta_fc_dynamic']).flat[0])
                eta_fc = eta_fc_in if eta_fc_in >= 0.0 else opt['eta_fc_fallback']
                eta_fc = float(np.clip(eta_fc, 0.05, 0.75))

                LHV_H2 = 120.0e6
                E_primary_chem_J = (E_primary_req_Wh * 3600.0) / max(eta_fc, 1e-3)
                fuel_mass = (E_primary_chem_J / LHV_H2) * opt['fuel_reserve_factor']
                available_primary = float(np.asarray(inputs['fuel_onboard_mass']).flat[0])
                g_primary = fuel_mass - available_primary

                E_primary_capacity_Wh = (available_primary * LHV_H2 / 3600.0) * eta_fc

            elif ps in ICE_HYBRIDS:
                eta_ice = SOURCE_FUEL['conventional_reciprocating']['eta_chem2shaft']
                LHV_fuel = SOURCE_FUEL['conventional_reciprocating']['LHV']

                E_primary_chem_J = (E_primary_req_Wh * 3600.0) / max(eta_ice, 1e-3)
                fuel_mass = (E_primary_chem_J / LHV_fuel) * opt['fuel_reserve_factor']
                available_primary = float(np.asarray(inputs['fuel_onboard_mass']).flat[0])
                g_primary = fuel_mass - available_primary

                eta_fc = 0.0
                E_primary_capacity_Wh = (available_primary * LHV_fuel / 3600.0) * eta_ice

            E_bat_capacity_Wh = available_bat * e_spec * dod * eta_b
            E_total_capacity_Wh = max(E_bat_capacity_Wh + E_primary_capacity_Wh + E_solar_Wh, 1.0)
            chi_implied = E_bat_capacity_Wh / E_total_capacity_Wh
            chi_consistency_error = chi_implied - chi

            energy_constraint = max(g_primary, g_bat)

        else:
            energy_constraint = 0.0

        # Expose hybrid sub-constraints as extra (non-breaking) outputs when relevant
        if ps in HYBRID_SOURCES:
            outputs['energy_constraint_primary'] = g_primary
            outputs['energy_constraint_bat'] = g_bat
            outputs['eta_fc_used'] = eta_fc
            outputs['chi_consistency_error'] = chi_consistency_error
            outputs['chi_implied'] = chi_implied

        # ---- outputs: cruise ----
        outputs['drag_cruise'] = D_cruise
        outputs['aerodynamic_lift_cruise'] = q_cruise * planform_area * C_L_cruise
        outputs['thrust_cruise'] = T_cruise
        outputs['time'] = time_s
        outputs['fuel_mass'] = np.full(n, fuel_mass)
        outputs['battery_mass_required'] = battery_mass_required
        outputs['endurance'] = endurance

        # ---- constraints (all g <= 0 feasible) ----
        outputs['power_constraint'] = P_shaft - engine_power
        outputs['energy_constraint'] = energy_constraint

        # ---- buoyancy constraint (PHYSICAL) ----
        rho_air_cr = float(phd.gas_density(pamb_cruise[0], tamb_cruise[0], gas="air"))
        rho_he_cr = float(phd.gas_density(pamb_cruise[0], tamb_cruise[0], gas="helium"))
        gross_volume = float(max(inputs['gross_volume'], 1.0))
        rho_air_to = float(phd.gas_density(pamb_to, tamb_to, gas="air"))
        rho_he_to = float(phd.gas_density(pamb_to, tamb_to, gas="helium"))

        buoyant_lift_available = (rho_air_to - rho_he_to) * gross_volume * g
        outputs['buoyancy_constraint'] = L_buoy - buoyant_lift_available


        outputs['lift_constraint'] = C_L_raw - C_L_max

        # ---- takeoff ----
        q_to_avg = 0.5 * rho_to * (0.7 * takeoff_speed)**2
        D_to_avg = q_to_avg * gross_area * (C_D0 + K * C_L_takeoff**2)
        L_aero_to_avg = q_to_avg * planform_area * C_L_takeoff
        friction_coeff = 0.03 if landing_system == 'conventional' else 0.0
        friction_force = friction_coeff * max(mtow * g - L_aero_to_avg - L_buoy, 0.0)

        P_installed = float(engine_power[0])
        T_to_max = (P_installed * prop_eff) / takeoff_speed
        T_to = T_to_max * np.cos(np.radians(thrust_angle))

        net_force = T_to - D_to_avg - friction_force
        accel = net_force / mtow if net_force > 0 else 1e-6
        S_G = takeoff_speed**2 / (2 * accel)
        S_R = 3 * takeoff_speed
        theta_CL = np.arctan((takeoff_speed * max(T_to - D_to_avg, 0.0)) / max(W_H, 1e-6))
        S_CL = 15.24 / np.tan(theta_CL) if np.tan(theta_CL) > 0 else 15.24
        S_total = S_G + S_R + S_CL

        outputs['drag_takeoff_avg'] = D_to_avg
        outputs['thrust_to'] = T_to
        outputs['ground_roll_distance'] = S_total
        outputs['ground_constraint'] = S_total - field_limit

        # ---- landing (corrected, deceleration-based braking) ----
        m_land = mtow - fuel_mass
        W_H_land = m_land * g * (1 - BR_landing)
        V_L = np.sqrt(2 * W_H_land / (rho_to * planform_area * max(C_L, 1e-6)))
        V_50 = 1.3 * V_L
        V_TD = 1.15 * V_L
        q_TD = 0.5 * rho_to * V_TD**2
        D_TD = q_TD * gross_area * (C_D0 + K * C_L**2)
        T_rev = 0.6 * T_to

        # air distance (50 ft to touchdown)
        S_A = (m_land / max(D_TD, 1e-6)) * ((V_50**2 - V_TD**2) / 2.0 + 15.24 * g)
        S_FR = 3 * V_TD
        # braking: a_decel from aero drag + reverse thrust + wheel braking
        brake_force = 0.0 if landing_system == 'acls' else 0.3 * max(m_land * g * (1 - BR_landing), 0.0)
        a_decel = max((D_TD + T_rev + brake_force) / max(m_land, 1.0), 1e-3)
        S_B = 0.0 if landing_system == 'acls' else V_TD**2 / (2.0 * a_decel)
        S_LAND = S_A + S_FR + S_B

        outputs['drag_landing'] = D_TD
        outputs['landing_distance'] = S_LAND
        outputs['landing_constraint'] = S_LAND - field_limit

        # ---- climb / descent / turn (conceptual) ----
        outputs['roc'] = (cruise_speed[0] * (T_to - float(D_cruise[0]))) / max(W_H, 1e-6)
        V_min_PR = ((4 * K * W_H_land**2) / (3 * (rho_to * planform_area)**2 * C_D0))**0.25
        C_D_land = C_D0 + K * C_L**2
        outputs['rod'] = -(C_D_land / max(C_L, 1e-6)) * V_min_PR
        R = 2.7 * length
        V_turn = 0.69 * cruise_speed[0]
        outputs['turn_time'] = (2 * np.pi * R) / max(V_turn, 1e-6)

        outputs['ballast_constraint'] = ballast_mass
        outputs['stability_margin'] = 0.1

        # ---- pressure control (optional) ----
        if opt['enable_pressure_control']:
            base = max(float(opt['pressure_control_base_power']), 0.0)
            frac = max(float(opt['pressure_control_fraction_of_prop_power']), 0.0)
            pc_power = base + frac * np.maximum(P_shaft, 0.0)
            takeoff_alt = float(inputs['takeoff_altitude'])
            max_alt = float(inputs['max_operating_altitude'])
            climb_rate = max(float(inputs['ascent_rate']), 1e-3)
            descent_rate = max(float(inputs['descent_rate']), 1e-3)
            climb_time = max((max_alt - takeoff_alt) / climb_rate, 0.0)
            descent_time = max((max_alt - takeoff_alt) / descent_rate, 0.0)
            outputs['pressure_control_power'] = pc_power
            outputs['pressure_control_energy'] = base * (climb_time + descent_time)