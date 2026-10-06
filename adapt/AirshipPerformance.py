# -*- coding: utf-8 -*-
"""
Universal Airship Performance Component for ADaPT
==================================================

Purpose
-------
Conceptual/quasi-steady performance analysis for buoyant airships using a
single, architecture-neutral force/energy formulation.  The component is
applicable to non-rigid, semi-rigid, and rigid airships; propulsion/energy
architecture enters only through externally supplied installed power,
resource sizing, propeller data, and efficiency.

Primary literature basis
------------------------
Carichner & Nicolai, Fundamentals of Aircraft and Airship Design, Vol. 2:

* Chapter 4: level-flight equilibrium, airship drag polar, power required,
  optimum speeds, climb/descent, takeoff, landing, and turning.
* Chapter 11: conceptual-design use of Chapter-4 relations, including the
  0.707 V_TO ground-roll approximation and the A-170-based sample design.

Important implementation distinctions
--------------------------------------
1. Airship aerodynamic coefficients are referenced to Vol**(2/3).
2. Buoyant lift does NOT create aerodynamic induced drag; only aerodynamic
   lift/heaviness enters K*CL**2.
3. Buoyant lift is treated as approximately constant during the mission for a
   pressure-regulated lifting-gas system.  BR therefore changes as vehicle
   mass changes.
4. Takeoff speed is calculated from heaviness and available takeoff CL by
   default.  It is not a universal fixed speed.
5. Low-speed propeller thrust should ideally come from Propulsion.  This
   component accepts an external takeoff thrust.  If unavailable, it can use
   an actuator-disk estimate when propeller diameter is supplied; only as a
   final compatibility fallback does it use P*eta/V with a finite speed floor.
6. Gas inertial mass treatment is explicit.  Set gas_masses_in_mtow=False if
   MTOW excludes helium and ballonet-air mass (the convention used in the
   book's takeoff derivation); set True if the Weight component already
   includes those masses.
7. The apparent dimensional inconsistency in the printed Chapter-4 climbout
   angle expression is not copied.  The dimensionally consistent relation
   sin(gamma)=(T-D)/W_H is used, consistent with the book's ROC equation.
8. Resource masses/energy capacities remain owned by external components.

Constraint convention
---------------------
All constraint outputs use g <= 0 as feasible.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


FUEL_SOURCES = [
    "conventional_reciprocating",
    "turboprop",
    "turboelectric",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
]

BATTERY_SOURCES = [
    "battery_only",
    "solar_battery",
    "solar-RFC",
]

HYBRID_SOURCES = [
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
    "conventional_battery_hybrid",
]

ALL_POWER_SOURCES = FUEL_SOURCES + BATTERY_SOURCES + HYBRID_SOURCES


class AirshipPerformance(om.ExplicitComponent):
    """Universal quasi-steady airship performance and feasibility model."""

    def initialize(self):
        self.options.declare("phd", types=object)
        self.options.declare(
            "power_source",
            default="conventional_reciprocating",
            values=ALL_POWER_SOURCES,
        )
        self.options.declare("num_steps", default=1, types=int)
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
        )
        self.options.declare(
            "airship_type",
            default="non-rigid",
            values=["non-rigid", "semi-rigid", "rigid"],
        )

        # --------------------------------------------------------------
        # Cruise/flight limits
        # --------------------------------------------------------------
        self.options.declare("C_L_takeoff", default=0.10, types=float,
            desc=("Prescribed aerodynamic lift coefficient available at the "
            "takeoff scrape/rotation condition. For Chapter-11 sample "
            "replication use C_L_takeoff=0.175, obtained from "
            "C_Lalpha=0.0175/deg and alpha_scrape=10 deg."
        ),)
        self.options.declare("C_L_max", default=0.60, types=float)
        self.options.declare("field_length_limit", default=450.0, types=float)

        # Default is a calculated Chapter-4 takeoff speed.  The historical
        # fixed option is retained only for backward compatibility.
        self.options.declare(
            "takeoff_speed_method",
            default="calculated",
            values=["calculated", "fixed"],
        )
        self.options.declare("takeoff_speed", default=19.0, types=float)
        self.options.declare("takeoff_speed_factor", default=1.10, types=float)
        self.options.declare("takeoff_average_speed_ratio", default=np.sqrt(0.5), types=float)
        self.options.declare("rotation_time", default=3.0, types=float)
        self.options.declare("obstacle_height", default=15.24, types=float)

        # Surface friction values are consistent with the ranges in Ch. 4,
        # Table 4.3; they remain user-selectable operating assumptions.
        self.options.declare("takeoff_friction_coefficient", default=0.03, types=float)
        self.options.declare("braking_friction_coefficient", default=0.30, types=float)
        self.options.declare("reverse_thrust_fraction", default=0.60, types=float)

        # Landing definition.
        self.options.declare("landing_approach_angle_deg", default=3.0, types=float)
        self.options.declare("landing_free_roll_time", default=3.0, types=float)
        self.options.declare("landing_field_factor", default=(1.0 / 0.60), types=float)

        # Explicit gas-inertia convention.
        self.options.declare(
            "gas_masses_in_mtow",
            default=False,
            types=bool,
            desc=(
                "True when Weight already includes helium/ballonet-air mass in MTOW. "
                "Set False for the book convention in which these gas masses are added "
                "to accelerated mass separately."
            ),
        )

        # Low-speed thrust hierarchy: external -> actuator disk -> finite-speed
        # power-over-speed fallback.
        self.options.declare(
            "takeoff_thrust_method",
            default="auto",
            values=["auto", "external", "actuator_disk", "power_over_speed"],
        )
        self.options.declare("actuator_disk_power_efficiency", default=0.75, types=float)
        self.options.declare("minimum_thrust_speed", default=8.0, types=float)

        # Turning.  R/L=2.7 is the Ch.4 worked example for delta_r=28 deg;
        # it is an explicit conceptual input, not treated as universal physics.
        self.options.declare("turn_radius_to_length_ratio", default=2.7, types=float)

        # Optional pressure-control accounting retained as an ADaPT extension.
        self.options.declare("enable_pressure_control", default=False, types=bool)
        self.options.declare("pressure_control_base_power", default=0.0, types=float)
        self.options.declare(
            "pressure_control_fraction_of_prop_power", default=0.0, types=float
        )

    # ==================================================================
    # Setup
    # ==================================================================

    def setup(self):
        n = self.options["num_steps"]

        # --------------------------------------------------------------
        # Mission / operating condition
        # --------------------------------------------------------------
        self.add_input("range", val=1_342_100.0, units="m")
        self.add_input("cruise_altp", val=np.full(n, 914.0), units="m")
        self.add_input("cruise_disa", val=np.zeros(n), units="K")
        self.add_input("cruise_speed", val=np.full(n, 31.0), units="m/s")
        self.add_input("n_engine", val=2.0)

        # Optional externally supplied mission mass history. Negative values
        # mean "derive internally from MTOW and mission consumable burn".
        self.add_input(
            "mission_mass",
            val=np.full(n, -1.0),
            units="kg",
            desc="Optional mass history; negative values request internal interpolation.",
        )

        # --------------------------------------------------------------
        # Geometry
        # --------------------------------------------------------------
        # Backward-compatible names are retained.  In ADaPT both aerodynamic_reference_area
        # and planform_area are currently connected to V**(2/3).  The model
        # uses aerodynamic_reference_area as the aerodynamic reference area, falling back to
        # planform_area if necessary.
        self.add_input("aerodynamic_reference_area", val=1.0, units="m**2")
        self.add_input("gross_volume", val=1.0, units="m**3")
        self.add_input("fin_area", val=1.0, units="m**2")
        self.add_input("planform_area", val=1.0, units="m**2")
        self.add_input("aspect_ratio", val=1.0)
        self.add_input("length", val=53.6, units="m")
        self.add_input(
            "ballonet_volume",
            val=0.0,
            units="m**3",
            desc="Installed maximum ballonet volume/capacity.",
        )

        # Optional direct takeoff lifting-gas volume. Negative means derive
        # from helium mass and takeoff helium density.
        self.add_input(
            "lifting_gas_volume_takeoff",
            val=-1.0,
            units="m**3",
        )

        # --------------------------------------------------------------
        # Mass / buoyancy state
        # --------------------------------------------------------------
        self.add_input("operational_weight", val=1_000.0, units="kg")
        self.add_input("mtow", val=1_000.0, units="kg")
        self.add_input("he_max_mass", val=1.0, units="kg")
        self.add_input("ballast_mass", val=0.0, units="kg")

        # Optional actual ballonet-air mass at takeoff. Negative means derive
        # from ballonet volume minus lifting-gas occupancy where possible.
        self.add_input("ballonet_air_mass_takeoff", val=-1.0, units="kg")

        # --------------------------------------------------------------
        # Propulsion interface
        # --------------------------------------------------------------
        self.add_input(
            "installed_shaft_power",
            val=134_000.0,
            units="W",
            desc="Total installed shaft power available to all propellers.",
        )
        self.add_input(
            "takeoff_thrust_available",
            val=-1.0,
            units="N",
            desc=(
                "Preferred external total thrust at the 0.707 V_TO ground-roll "
                "condition. Negative means derive internally."
            ),
        )
        self.add_input(
            "propeller_diameter",
            val=0.0,
            units="m",
            desc="Per-propeller diameter for actuator-disk takeoff-thrust estimate.",
        )

        # --------------------------------------------------------------
        # Atmosphere
        # --------------------------------------------------------------
        self.add_input("pamb_cruise", val=np.full(n, 89_876.0), units="Pa")
        self.add_input("tamb_cruise", val=np.full(n, 281.65), units="K")
        self.add_input("pamb_to", val=np.full(n, 101_325.0), units="Pa")
        self.add_input("tamb_to", val=np.full(n, 288.15), units="K")

        # --------------------------------------------------------------
        # Aerodynamics / controls
        # --------------------------------------------------------------
        self.add_input("lift_coeff", val=0.15)
        self.add_input("drag_due_to_lift_factor", val=0.869)
        self.add_input("drag_coeff_zero", val=0.03542)
        self.add_input("BR_takeoff", val=0.856)
        self.add_input("BR_landing", val=0.90)
        self.add_input("tailwind_speed", val=0.0, units="m/s")
        self.add_input("thrust_vector_angle", val=0.0, units="deg")
        self.add_input("rudder_deflection", val=28.0, units="deg")
        self.add_input(
            "cruise_strategy",
            val=1.0,
            desc=(
                "1: prescribed speed; 2: min drag/max aerodynamic L/D; "
                "3: min power/max endurance."
            ),
        )
        self.add_input("propeller_efficiency", val=0.75)
        self.add_input(
            "landing_lift_coefficient",
            val=-1.0,
            desc="Negative means use C_L_takeoff for landing speed sizing.",
        )

        # --------------------------------------------------------------
        # External resource-sizing interface
        # --------------------------------------------------------------
        self.add_input("required_consumable_mass", val=0.0, units="kg")
        self.add_input("installed_consumable_mass", val=0.0, units="kg")
        self.add_input("consumable_mass_used", val=0.0, units="kg")
        self.add_input("required_battery_mass", val=0.0, units="kg")
        self.add_input("installed_battery_mass", val=0.0, units="kg")

        self.add_input("installed_primary_usable_energy", val=0.0, units="W*h")
        self.add_input("installed_battery_usable_energy", val=0.0, units="W*h")
        self.add_input("solar_energy_recovered", val=0.0, units="W*h")
        self.add_input("chi", val=0.10)
        self.add_input("tau", val=0.10)
        self.add_input("eta_fc_dynamic", val=np.full(n, -1.0))

        if self.options["landing_system"] == "acls":
            self.add_input("acls_area", val=377.0, units="m**2")

        if self.options["enable_pressure_control"]:
            self.add_input("ascent_rate", val=1.0, units="m/s")
            self.add_input("descent_rate", val=1.0, units="m/s")
            self.add_input("takeoff_altitude", val=0.0, units="m")
            self.add_input("max_operating_altitude", val=914.0, units="m")

        # --------------------------------------------------------------
        # Feasibility constraints (g <= 0)
        # --------------------------------------------------------------
        self.add_output("power_constraint", val=np.zeros(n), units="W")
        self.add_output("energy_constraint", val=0.0, units="kg")
        self.add_output("energy_constraint_primary", val=0.0, units="kg")
        self.add_output("energy_constraint_bat", val=0.0, units="kg")
        self.add_output("buoyancy_constraint", val=0.0, units="N")
        self.add_output("lift_constraint", val=0.0)
        self.add_output("ground_constraint", val=0.0, units="m")
        self.add_output("landing_constraint", val=0.0, units="m")
        self.add_output("ballast_constraint", val=0.0, units="kg")
        self.add_output("landing_BR_constraint", val=0.0)

        # --------------------------------------------------------------
        # Cruise / mission outputs
        # --------------------------------------------------------------
        self.add_output("aerodynamic_lift_cruise", val=np.zeros(n), units="N")
        self.add_output("heaviness_cruise", val=np.zeros(n), units="N")
        self.add_output("buoyancy_ratio_cruise", val=np.zeros(n))
        self.add_output("lift_coefficient_cruise", val=np.zeros(n))
        self.add_output("thrust_cruise", val=np.zeros(n), units="N")
        self.add_output("required_shaft_power", val=np.zeros(n), units="W")
        self.add_output("mission_speed_used", val=np.full(n, 31.0), units="m/s")
        self.add_output("mission_mass_used", val=np.full(n, 1_000.0), units="kg")
        self.add_output("mission_duration", val=0.0, units="s")
        self.add_output("time", val=0.0, units="s")
        self.add_output("endurance", val=0.0, units="h")
        self.add_output("mission_energy_required", val=0.0, units="J")
        self.add_output("total_mission_energy_required", val=0.0, units="J")
        self.add_output("drag_cruise", val=np.zeros(n), units="N")

        # Resource compatibility outputs.
        self.add_output("fuel_mass", val=np.zeros(n), units="kg")
        self.add_output("battery_mass_required", val=0.0, units="kg")
        self.add_output("mission_consumable_mass_used", val=0.0, units="kg")

        # --------------------------------------------------------------
        # Buoyancy diagnostics
        # --------------------------------------------------------------
        self.add_output("buoyant_lift_required_takeoff", val=0.0, units="N")
        self.add_output("buoyant_lift_available_takeoff", val=0.0, units="N")
        self.add_output("lifting_gas_volume_takeoff_used", val=0.0, units="m**3")
        self.add_output("takeoff_heaviness", val=0.0, units="N")
        self.add_output("landing_heaviness", val=0.0, units="N")
        self.add_output("BR_landing_implied", val=0.0)
        self.add_output("ballast_required", val=0.0, units="kg")

        # --------------------------------------------------------------
        # Takeoff outputs
        # --------------------------------------------------------------
        self.add_output("takeoff_speed_calculated", val=0.0, units="m/s")
        self.add_output("takeoff_average_speed", val=0.0, units="m/s")
        self.add_output("takeoff_thrust_available_used", val=0.0, units="N")
        self.add_output("thrust_to", val=0.0, units="N")
        self.add_output("drag_takeoff_avg", val=0.0, units="N")
        self.add_output("takeoff_aerodynamic_lift_avg", val=0.0, units="N")
        self.add_output("takeoff_friction_force", val=0.0, units="N")
        self.add_output("takeoff_accelerated_mass", val=0.0, units="kg")
        self.add_output("takeoff_ground_roll", val=0.0, units="m")
        self.add_output("takeoff_rotation_distance", val=0.0, units="m")
        self.add_output("takeoff_climbout_distance", val=0.0, units="m")
        self.add_output("takeoff_distance", val=0.0, units="m")
        # simplified name now correctly means ground roll only.
        self.add_output("ground_roll_distance", val=0.0, units="m")
        self.add_output("takeoff_climb_angle", val=0.0, units="deg")
        self.add_output("takeoff_climb_gradient", val=0.0)

        # --------------------------------------------------------------
        # Landing outputs
        # --------------------------------------------------------------
        self.add_output("landing_reference_speed", val=0.0, units="m/s")
        self.add_output("landing_speed_50ft", val=0.0, units="m/s")
        self.add_output("landing_touchdown_speed", val=0.0, units="m/s")
        self.add_output("landing_air_distance", val=0.0, units="m")
        self.add_output("landing_free_roll_distance", val=0.0, units="m")
        self.add_output("landing_braking_distance", val=0.0, units="m")
        self.add_output("landing_distance", val=0.0, units="m")
        self.add_output("landing_field_length", val=0.0, units="m")
        self.add_output("drag_landing", val=0.0, units="N")

        # --------------------------------------------------------------
        # Climb/descent/turn
        # --------------------------------------------------------------
        self.add_output("roc", val=0.0, units="m/s")
        self.add_output("rod", val=0.0, units="m/s")
        self.add_output("minimum_power_speed", val=0.0, units="m/s")
        self.add_output("turn_radius", val=0.0, units="m")
        self.add_output("turn_speed", val=0.0, units="m/s")
        self.add_output("turn_speed_ratio", val=0.0)
        self.add_output("turn_time", val=0.0, units="s")

        # Kept only to avoid breaking older reporting scripts.  Stability is
        # not solved in this component.
        self.add_output(
            "stability_margin",
            val=0.0,
            desc="Deprecated compatibility output; stability is not calculated here.",
        )

        # Hybrid diagnostics retained for architecture compatibility.
        self.add_output("eta_fc_used", val=0.0)
        self.add_output("chi_consistency_error", val=0.0)
        self.add_output("chi_implied", val=0.0)
        self.add_output("tau_used", val=0.0)

        if self.options["enable_pressure_control"]:
            self.add_output("pressure_control_power", val=np.zeros(n), units="W")
            self.add_output("pressure_control_energy", val=0.0, units="J")

        self.declare_partials("*", "*", method="fd", step=1.0e-8)

    # ==================================================================
    # Utilities
    # ==================================================================

    @staticmethod
    def _scalar(value):
        return float(np.asarray(value).ravel()[0])

    @staticmethod
    def _vector(value, n, minimum=None):
        arr = np.atleast_1d(value).astype(float).ravel()
        if arr.size == 0:
            arr = np.zeros(n)
        elif arr.size == 1:
            arr = np.full(n, arr[0])
        elif arr.size < n:
            arr = np.pad(arr, (0, n - arr.size), mode="edge")
        elif arr.size > n:
            arr = arr[:n]
        if minimum is not None:
            arr = np.maximum(arr, minimum)
        return arr

    @staticmethod
    def _actuator_disk_thrust(power_air, rho, disk_area, speed):
        """Ideal actuator-disk thrust at finite forward speed.

        Solve P = 2 rho A vi (V+vi)^2, then T = 2 rho A vi (V+vi).
        This is a physics fallback for conceptual work, not a substitute for
        an actual propeller map.
        """
        power_air = max(float(power_air), 0.0)
        rho = max(float(rho), 1.0e-9)
        disk_area = max(float(disk_area), 1.0e-12)
        speed = max(float(speed), 0.0)

        if power_air <= 0.0:
            return 0.0

        # Static induced velocity gives a safe upper bracket.
        vi_static = (power_air / (2.0 * rho * disk_area)) ** (1.0 / 3.0)
        lo = 0.0
        hi = max(10.0 * vi_static + speed, 1.0)

        for _ in range(80):
            mid = 0.5 * (lo + hi)
            f_mid = 2.0 * rho * disk_area * mid * (speed + mid) ** 2 - power_air
            if f_mid > 0.0:
                hi = mid
            else:
                lo = mid

        vi = 0.5 * (lo + hi)
        return 2.0 * rho * disk_area * vi * (speed + vi)

    def _takeoff_thrust(self, inputs, rho, speed, eta_prop, n_engine):
        """Return total propulsive thrust magnitude at the takeoff average speed."""
        method = self.options["takeoff_thrust_method"]
        external = self._scalar(inputs["takeoff_thrust_available"])
        installed_power = max(self._scalar(inputs["installed_shaft_power"]), 0.0)
        prop_diameter = max(self._scalar(inputs["propeller_diameter"]), 0.0)

        if method in ("auto", "external") and external >= 0.0:
            return external
        if method == "external":
            return 0.0

        if method in ("auto", "actuator_disk") and prop_diameter > 0.0:
            n_engine = max(int(n_engine), 1)
            area_each = np.pi * prop_diameter**2 / 4.0
            shaft_each = installed_power / n_engine
            power_air_each = (
                float(self.options["actuator_disk_power_efficiency"]) * shaft_each
            )
            thrust_each = self._actuator_disk_thrust(
                power_air_each, rho, area_each, speed
            )
            return n_engine * thrust_each
        if method == "actuator_disk":
            return 0.0

        # Last-resort compatibility model.  A finite speed floor prevents the
        # singular static-thrust behavior of P/V.
        v_eff = max(float(speed), float(self.options["minimum_thrust_speed"]))
        return installed_power * eta_prop / v_eff

    # ==================================================================
    # Main computation
    # ==================================================================

    def compute(self, inputs, outputs):
        opt = self.options
        phd = opt["phd"]
        n = opt["num_steps"]
        power_source = opt["power_source"]
        landing_system = opt["landing_system"]
        g = 9.80665
        airship_type = opt["airship_type"]

        # --------------------------------------------------------------
        # Guarded inputs
        # --------------------------------------------------------------
        range_m = max(self._scalar(inputs["range"]), 1.0)
        cruise_speed_prescribed = self._vector(inputs["cruise_speed"], n, minimum=0.5)
        n_engine = max(int(round(self._scalar(inputs["n_engine"]))), 1)

        s_ref_primary = self._scalar(inputs["aerodynamic_reference_area"])
        s_ref_fallback = self._scalar(inputs["planform_area"])
        s_ref = max(s_ref_primary if s_ref_primary > 0.0 else s_ref_fallback, 1.0e-9)
        gross_volume = max(self._scalar(inputs["gross_volume"]), 1.0e-9)
        ballonet_volume = max(self._scalar(inputs["ballonet_volume"]), 0.0)
        length = max(self._scalar(inputs["length"]), 1.0e-6)

        mtow = max(self._scalar(inputs["mtow"]), 1.0)
        he_mass = max(self._scalar(inputs["he_max_mass"]), 0.0)
        ballast_available = max(self._scalar(inputs["ballast_mass"]), 0.0)

        installed_shaft_power = max(self._scalar(inputs["installed_shaft_power"]), 0.0)
        eta_prop = float(np.clip(self._scalar(inputs["propeller_efficiency"]), 0.05, 0.99))

        pamb_cruise = self._vector(inputs["pamb_cruise"], n, minimum=1.0e3)
        tamb_cruise = self._vector(inputs["tamb_cruise"], n, minimum=150.0)
        pamb_to = max(self._scalar(inputs["pamb_to"]), 1.0e3)
        tamb_to = max(self._scalar(inputs["tamb_to"]), 150.0)

        rho_cruise = np.maximum(
            phd.gas_density(pamb_cruise, tamb_cruise, gas="air"), 1.0e-8
        )
        rho_air_to = max(float(phd.gas_density(pamb_to, tamb_to, gas="air")), 1.0e-8)
        rho_he_to = max(float(phd.gas_density(pamb_to, tamb_to, gas="helium")), 1.0e-8)

        K = max(self._scalar(inputs["drag_due_to_lift_factor"]), 1.0e-12)
        C_D0 = max(self._scalar(inputs["drag_coeff_zero"]), 1.0e-12)
        C_L_max = max(float(opt["C_L_max"]), 1.0e-9)
        C_L_takeoff = max(float(opt["C_L_takeoff"]), 1.0e-9)

        BR_takeoff = float(np.clip(self._scalar(inputs["BR_takeoff"]), 0.0, 0.999999))
        BR_landing_target = float(np.clip(self._scalar(inputs["BR_landing"]), 0.0, 0.999999))
        thrust_angle_rad = np.radians(
            float(np.clip(self._scalar(inputs["thrust_vector_angle"]), -90.0, 90.0))
        )
        tailwind_speed = self._scalar(inputs["tailwind_speed"])
        cruise_strategy = int(round(self._scalar(inputs["cruise_strategy"])))

        required_consumable_mass = max(self._scalar(inputs["required_consumable_mass"]), 0.0)
        installed_consumable_mass = max(self._scalar(inputs["installed_consumable_mass"]), 0.0)
        consumable_mass_used = float(
            np.clip(
                self._scalar(inputs["consumable_mass_used"]),
                0.0,
                installed_consumable_mass if installed_consumable_mass > 0.0 else np.inf,
            )
        )
        required_battery_mass = max(self._scalar(inputs["required_battery_mass"]), 0.0)
        installed_battery_mass = max(self._scalar(inputs["installed_battery_mass"]), 0.0)

        # --------------------------------------------------------------
        # Buoyancy state
        # --------------------------------------------------------------
        required_buoyant_lift_to = BR_takeoff * mtow * g
        takeoff_heaviness = max(mtow * g - required_buoyant_lift_to, 0.0)

        v_he_override = self._scalar(inputs["lifting_gas_volume_takeoff"])
        if v_he_override >= 0.0:
            v_he_to = v_he_override
        elif he_mass > 0.0:
            v_he_to = he_mass / rho_he_to
        else:
            # Compatibility fallback when helium mass has not yet been supplied.
            v_he_to = max(gross_volume - ballonet_volume, 0.0)

        # Physical envelope/gas-cell capacity safeguard; report any mismatch
        # through the buoyancy constraint rather than allowing impossible volume.
        v_he_to = max(min(v_he_to, gross_volume), 0.0)
        buoyant_lift_available_to = (rho_air_to * v_he_to - he_mass) * g

        outputs["buoyant_lift_required_takeoff"] = required_buoyant_lift_to
        outputs["buoyant_lift_available_takeoff"] = buoyant_lift_available_to
        outputs["lifting_gas_volume_takeoff_used"] = v_he_to
        outputs["takeoff_heaviness"] = takeoff_heaviness
        outputs["buoyancy_constraint"] = required_buoyant_lift_to - buoyant_lift_available_to

        # For pressure-stabilized conceptual performance, use the selected
        # takeoff buoyant lift as the constant mission buoyant force.  This is
        # the quantity the design is attempting to provide; the separate
        # buoyancy constraint checks whether the actual gas state can supply it.
        buoyant_lift_mission = required_buoyant_lift_to

        # --------------------------------------------------------------
        # Mission mass history
        # --------------------------------------------------------------
        mission_mass_input = self._vector(inputs["mission_mass"], n)
        if np.all(mission_mass_input > 0.0):
            mission_mass = mission_mass_input
        else:
            landing_mass_est = max(mtow - consumable_mass_used, 1.0)
            if n == 1:
                mission_mass = np.array([0.5 * (mtow + landing_mass_est)])
            else:
                mission_mass = np.linspace(mtow, landing_mass_est, n)

        heaviness_cruise = mission_mass * g - buoyant_lift_mission
        # Negative heaviness is physically possible (BR>1) but cannot be
        # supported by positive aerodynamic lift.  Preserve sign for CL and
        # feasibility diagnostics rather than clipping it away.

        # --------------------------------------------------------------
        # Cruise equilibrium and optimum-speed modes
        # --------------------------------------------------------------
        if cruise_strategy == 2:
            # Minimum drag / maximum aerodynamic L/D: CL=sqrt(CD0/K).
            C_L_target = np.sqrt(C_D0 / K)
            # Preserve the sign of heaviness so light states request negative lift.
            sign_h = np.where(heaviness_cruise >= 0.0, 1.0, -1.0)
            C_L_cruise = sign_h * C_L_target
            speed_used = np.sqrt(
                2.0 * np.abs(heaviness_cruise)
                / np.maximum(rho_cruise * s_ref * C_L_target, 1.0e-12)
            )
            speed_used = np.maximum(speed_used, 0.5)

        elif cruise_strategy == 3:
            # Minimum power / maximum endurance: CL=sqrt(3 CD0/K).
            C_L_target = np.sqrt(3.0 * C_D0 / K)
            sign_h = np.where(heaviness_cruise >= 0.0, 1.0, -1.0)
            C_L_cruise = sign_h * C_L_target
            speed_used = np.sqrt(
                2.0 * np.abs(heaviness_cruise)
                / np.maximum(rho_cruise * s_ref * C_L_target, 1.0e-12)
            )
            speed_used = np.maximum(speed_used, 0.5)

        else:
            speed_used = cruise_speed_prescribed
            q_tmp = 0.5 * rho_cruise * speed_used**2
            C_L_cruise = heaviness_cruise / np.maximum(q_tmp * s_ref, 1.0e-12)

        q_cruise = 0.5 * rho_cruise * speed_used**2
        C_D_cruise = C_D0 + K * C_L_cruise**2
        drag_cruise = q_cruise * s_ref * C_D_cruise
        thrust_cruise = np.maximum(drag_cruise, 0.0)
        required_shaft_power = thrust_cruise * speed_used / eta_prop

        # Distance-based integration is robust when mission nodes represent
        # equal fractions of route distance.
        ground_speed = np.maximum(speed_used - tailwind_speed, 0.5)
        distance_per_node = range_m / n
        dt_nodes = distance_per_node / ground_speed
        mission_time = float(np.sum(dt_nodes))
        shaft_energy = float(np.sum(required_shaft_power * dt_nodes))

        aerodynamic_lift_cruise = q_cruise * s_ref * C_L_cruise
        BR_cruise = buoyant_lift_mission / np.maximum(mission_mass * g, 1.0e-12)

        outputs["heaviness_cruise"] = heaviness_cruise
        outputs["buoyancy_ratio_cruise"] = BR_cruise
        outputs["lift_coefficient_cruise"] = C_L_cruise
        outputs["aerodynamic_lift_cruise"] = aerodynamic_lift_cruise
        outputs["drag_cruise"] = drag_cruise
        outputs["thrust_cruise"] = thrust_cruise
        outputs["required_shaft_power"] = required_shaft_power
        outputs["mission_speed_used"] = speed_used
        outputs["mission_mass_used"] = mission_mass
        outputs["mission_duration"] = mission_time
        outputs["time"] = mission_time
        outputs["endurance"] = mission_time / 3600.0
        outputs["mission_energy_required"] = shaft_energy

        outputs["power_constraint"] = required_shaft_power - installed_shaft_power
        outputs["lift_constraint"] = float(np.max(np.abs(C_L_cruise))) - C_L_max

        # --------------------------------------------------------------
        # External resource feasibility
        # --------------------------------------------------------------
        primary_constraint = required_consumable_mass - installed_consumable_mass
        battery_constraint = required_battery_mass - installed_battery_mass

        if power_source in FUEL_SOURCES:
            energy_constraint = primary_constraint
        elif power_source in BATTERY_SOURCES:
            energy_constraint = battery_constraint
        elif power_source in HYBRID_SOURCES:
            energy_constraint = max(primary_constraint, battery_constraint)
        else:
            energy_constraint = 0.0

        outputs["energy_constraint"] = energy_constraint
        outputs["energy_constraint_primary"] = primary_constraint
        outputs["energy_constraint_bat"] = battery_constraint

        # --------------------------------------------------------------
        # Hybrid energy-consistency diagnostics
        # --------------------------------------------------------------
        primary_energy = max(self._scalar(inputs["installed_primary_usable_energy"]), 0.0)
        battery_energy = max(self._scalar(inputs["installed_battery_usable_energy"]), 0.0)
        solar_energy = max(self._scalar(inputs["solar_energy_recovered"]), 0.0)
        total_energy = primary_energy + battery_energy + solar_energy
        chi_implied = battery_energy / total_energy if total_energy > 0.0 else 0.0
        chi_target = float(np.clip(self._scalar(inputs["chi"]), 0.0, 1.0))
        tau_used = float(np.clip(self._scalar(inputs["tau"]), 0.0, 1.0))

        eta_fc_dynamic = self._vector(inputs["eta_fc_dynamic"], n)
        valid_eta = eta_fc_dynamic[eta_fc_dynamic >= 0.0]
        eta_fc_used = float(np.mean(valid_eta)) if valid_eta.size else 0.0

        outputs["chi_implied"] = chi_implied
        outputs["chi_consistency_error"] = chi_implied - chi_target
        outputs["tau_used"] = tau_used
        outputs["eta_fc_used"] = eta_fc_used

        # --------------------------------------------------------------
        # Gas inertial masses used for accelerated phases
        # --------------------------------------------------------------
        ballonet_air_input = self._scalar(
            inputs["ballonet_air_mass_takeoff"]
        )

        if ballonet_air_input >= 0.0:

            ballonet_air_mass_to = (
                ballonet_air_input
            )

        else:

            if airship_type in [
                "non-rigid",
                "semi-rigid",
            ]:

                ballonet_air_volume_to = max(
                    gross_volume - v_he_to,
                    0.0,
                )

                ballonet_air_mass_to = (
                    ballonet_air_volume_to
                    * rho_air_to
                )

            else:

                # Rigid airships use separate lifting-gas cells
                # rather than pressure-regulating ballonets.
                ballonet_air_mass_to = 0.0




        if bool(opt["gas_masses_in_mtow"]):
            accelerated_mass_to = mtow
        else:
            accelerated_mass_to = mtow + he_mass + ballonet_air_mass_to

        outputs["takeoff_accelerated_mass"] = accelerated_mass_to

        # --------------------------------------------------------------
        # Takeoff: Chapter-4 conceptual method
        # --------------------------------------------------------------
        if opt["takeoff_speed_method"] == "fixed":
            V_to = max(float(opt["takeoff_speed"]), 0.0)
        elif takeoff_heaviness <= 1.0e-8:
            V_to = 0.0
        else:
            V_to = float(opt["takeoff_speed_factor"]) * np.sqrt(
                2.0 * takeoff_heaviness / (rho_air_to * s_ref * C_L_takeoff)
            )

        avg_ratio = float(np.clip(opt["takeoff_average_speed_ratio"], 0.0, 1.0))
        V_avg_to = avg_ratio * V_to
        q_avg_to = 0.5 * rho_air_to * V_avg_to**2

        lift_avg_to = q_avg_to * s_ref * C_L_takeoff
        drag_avg_to = q_avg_to * s_ref * (C_D0 + K * C_L_takeoff**2)

        thrust_mag_avg = self._takeoff_thrust(
            inputs, rho_air_to, V_avg_to, eta_prop, n_engine
        )
        thrust_horizontal = thrust_mag_avg * np.cos(thrust_angle_rad)
        thrust_vertical = thrust_mag_avg * np.sin(thrust_angle_rad)

        mu_to = 0.0 if landing_system == "acls" else max(
            float(opt["takeoff_friction_coefficient"]), 0.0
        )
        normal_heaviness = max(
            takeoff_heaviness - lift_avg_to - max(thrust_vertical, 0.0), 0.0
        )
        friction_force = mu_to * normal_heaviness
        net_accel_force = thrust_horizontal - drag_avg_to - friction_force

        if V_to <= 0.0:
            ground_roll = 0.0
            acceleration = 0.0
        elif net_accel_force > 0.0:
            acceleration = net_accel_force / max(accelerated_mass_to, 1.0e-9)
            ground_roll = V_to**2 / (2.0 * acceleration)
        else:
            acceleration = 0.0
            ground_roll = 1.0e9

        rotation_distance = float(opt["rotation_time"]) * V_to

        # Climbout at V_TO.  Prefer an external thrust value if supplied; in
        # the absence of a propeller map, reuse the average-condition thrust as
        # a conservative conceptual estimate rather than invoke singular P/V.
        q_to = 0.5 * rho_air_to * V_to**2
        drag_to = q_to * s_ref * (C_D0 + K * C_L_takeoff**2)
        excess_horizontal_force = thrust_horizontal - drag_to

        if takeoff_heaviness > 1.0e-9:
            sin_gamma = float(np.clip(excess_horizontal_force / takeoff_heaviness, -0.999, 0.999))
        else:
            sin_gamma = 0.999 if excess_horizontal_force > 0.0 else 0.0

        gamma = np.arcsin(sin_gamma)
        tan_gamma = np.tan(gamma)
        if tan_gamma > 1.0e-9:
            climbout_distance = float(opt["obstacle_height"]) / tan_gamma
        else:
            climbout_distance = 1.0e9

        takeoff_distance = ground_roll + rotation_distance + climbout_distance
        field_limit = max(float(opt["field_length_limit"]), 1.0)

        outputs["takeoff_speed_calculated"] = V_to
        outputs["takeoff_average_speed"] = V_avg_to
        outputs["takeoff_thrust_available_used"] = thrust_mag_avg
        outputs["thrust_to"] = thrust_horizontal
        outputs["drag_takeoff_avg"] = drag_avg_to
        outputs["takeoff_aerodynamic_lift_avg"] = lift_avg_to
        outputs["takeoff_friction_force"] = friction_force
        outputs["takeoff_ground_roll"] = ground_roll
        outputs["ground_roll_distance"] = ground_roll
        outputs["takeoff_rotation_distance"] = rotation_distance
        outputs["takeoff_climbout_distance"] = climbout_distance
        outputs["takeoff_distance"] = takeoff_distance
        outputs["takeoff_climb_angle"] = np.degrees(gamma)
        outputs["takeoff_climb_gradient"] = tan_gamma
        outputs["ground_constraint"] = takeoff_distance - field_limit

        # Rate of climb at the takeoff/climbout condition, using the same
        # dimensionally consistent excess-force relation.
        outputs["roc"] = V_to * sin_gamma

        # --------------------------------------------------------------
        # Landing: air distance + free roll + braking
        # --------------------------------------------------------------
        landing_mass = max(mtow - consumable_mass_used, 1.0)
        landing_weight = landing_mass * g
        landing_heaviness = landing_weight - buoyant_lift_mission
        BR_landing_implied = buoyant_lift_mission / max(landing_weight, 1.0e-12)

        outputs["landing_heaviness"] = landing_heaviness
        outputs["BR_landing_implied"] = BR_landing_implied
        # Positive means actual BR exceeds the selected/allowable target.
        outputs["landing_BR_constraint"] = BR_landing_implied - BR_landing_target

        # Ballast is required only if the unballasted landing state is light.
        ballast_required = max(-landing_heaviness / g, 0.0)
        outputs["ballast_required"] = ballast_required
        outputs["ballast_constraint"] = ballast_required - ballast_available

        C_L_landing_input = self._scalar(inputs["landing_lift_coefficient"])
        C_L_landing = C_L_takeoff if C_L_landing_input <= 0.0 else C_L_landing_input
        landing_heaviness_for_speed = max(landing_heaviness, 0.0)

        if landing_heaviness_for_speed <= 1.0e-9:
            V_L = 0.0
        else:
            V_L = np.sqrt(
                2.0 * landing_heaviness_for_speed
                / (rho_air_to * s_ref * max(C_L_landing, 1.0e-9))
            )

        V_50 = 1.30 * V_L
        V_td = 1.15 * V_L

        # Ch.4 gives an alternate energy method and a simple 3-deg approach
        # method.  The latter is robust for conceptual design and avoids
        # introducing an unsupported approach-thrust schedule.
        approach_angle = np.radians(max(float(opt["landing_approach_angle_deg"]), 0.1))
        air_distance = float(opt["obstacle_height"]) / np.tan(approach_angle)
        free_roll_distance = float(opt["landing_free_roll_time"]) * V_td

        # During the free-roll transition the book assumes aerodynamic lift is
        # reduced to zero before braking.  Braking therefore acts on heaviness.
        q_td = 0.5 * rho_air_to * V_td**2
        drag_td = q_td * s_ref * C_D0
        reverse_thrust = float(opt["reverse_thrust_fraction"]) * max(thrust_horizontal, 0.0)

        mu_brake = 0.0 if landing_system == "acls" else max(
            float(opt["braking_friction_coefficient"]), 0.0
        )
        brake_force = mu_brake * max(landing_heaviness, 0.0)
        retarding_force = drag_td + reverse_thrust + brake_force

        if bool(opt["gas_masses_in_mtow"]):
            accelerated_mass_land = landing_mass
        else:
            # Conservative reuse of takeoff gas inertial mass at conceptual level.
            accelerated_mass_land = landing_mass + he_mass + ballonet_air_mass_to

        if V_td <= 0.0:
            braking_distance = 0.0
        elif retarding_force > 0.0:
            braking_distance = accelerated_mass_land * V_td**2 / (2.0 * retarding_force)
        else:
            braking_distance = 1.0e9

        landing_distance = air_distance + free_roll_distance + braking_distance
        landing_field_length = landing_distance * float(opt["landing_field_factor"])

        outputs["landing_reference_speed"] = V_L
        outputs["landing_speed_50ft"] = V_50
        outputs["landing_touchdown_speed"] = V_td
        outputs["landing_air_distance"] = air_distance
        outputs["landing_free_roll_distance"] = free_roll_distance
        outputs["landing_braking_distance"] = braking_distance
        outputs["landing_distance"] = landing_distance
        outputs["landing_field_length"] = landing_field_length
        outputs["drag_landing"] = drag_td
        outputs["landing_constraint"] = landing_field_length - field_limit

        # --------------------------------------------------------------
        # Minimum rate of descent
        # --------------------------------------------------------------
        if landing_heaviness_for_speed > 1.0e-9:
            V_min_power = (
                4.0 * K * landing_heaviness_for_speed**2
                / max(3.0 * (rho_air_to * s_ref) ** 2 * C_D0, 1.0e-12)
            ) ** 0.25
            q_min_power = 0.5 * rho_air_to * V_min_power**2
            C_L_min_power = landing_heaviness_for_speed / max(q_min_power * s_ref, 1.0e-12)
            C_D_min_power = C_D0 + K * C_L_min_power**2
            D_min_power = q_min_power * s_ref * C_D_min_power
            rod = -V_min_power * D_min_power / landing_heaviness_for_speed
        else:
            V_min_power = 0.0
            rod = 0.0

        outputs["minimum_power_speed"] = V_min_power
        outputs["rod"] = rod

        # --------------------------------------------------------------
        # Turning: Ch.4 empirical conceptual relation
        # --------------------------------------------------------------
        R_over_L = max(float(opt["turn_radius_to_length_ratio"]), 1.0e-6)
        L_over_R = 1.0 / R_over_L
        A_turn = 1.0 + 12.8 * L_over_R**2
        speed_ratio_turn = (-1.0 + np.sqrt(1.0 + 8.0 * A_turn)) / (2.0 * A_turn)
        speed_ratio_turn = float(np.clip(speed_ratio_turn, 0.0, 1.0))

        turn_radius = R_over_L * length
        turn_speed = speed_ratio_turn * float(speed_used[0])
        turn_time = 2.0 * np.pi * turn_radius / max(turn_speed, 1.0e-9)

        outputs["turn_radius"] = turn_radius
        outputs["turn_speed"] = turn_speed
        outputs["turn_speed_ratio"] = speed_ratio_turn
        outputs["turn_time"] = turn_time
        outputs["stability_margin"] = 0.0

        # --------------------------------------------------------------
        # Pressure-control accounting (optional ADaPT extension)
        # --------------------------------------------------------------
        pressure_control_energy = 0.0
        pressure_control_power = np.zeros(n)

        if opt["enable_pressure_control"]:
            base_power = max(float(opt["pressure_control_base_power"]), 0.0)
            power_fraction = max(float(opt["pressure_control_fraction_of_prop_power"]), 0.0)
            pressure_control_power = base_power + power_fraction * np.maximum(required_shaft_power, 0.0)

            takeoff_altitude = self._scalar(inputs["takeoff_altitude"])
            maximum_altitude = self._scalar(inputs["max_operating_altitude"])
            ascent_rate = max(self._scalar(inputs["ascent_rate"]), 1.0e-3)
            descent_rate = max(self._scalar(inputs["descent_rate"]), 1.0e-3)
            altitude_change = max(maximum_altitude - takeoff_altitude, 0.0)
            pressure_control_energy = float(np.mean(pressure_control_power)) * (
                altitude_change / ascent_rate + altitude_change / descent_rate
            )

            outputs["pressure_control_power"] = pressure_control_power
            outputs["pressure_control_energy"] = pressure_control_energy

        outputs["total_mission_energy_required"] = shaft_energy + pressure_control_energy

        # --------------------------------------------------------------
        # simplified resource outputs
        # --------------------------------------------------------------
        outputs["fuel_mass"] = np.full(n, required_consumable_mass)
        outputs["battery_mass_required"] = required_battery_mass
        outputs["mission_consumable_mass_used"] = consumable_mass_used


if __name__ == "__main__":
    print(
        "AirshipPerformance loaded successfully. "
        "Instantiate it inside an OpenMDAO Problem with a valid phd object."
    )
