# -*- coding: utf-8 -*-
"""
Turboelectric Component for ADaPT
====================================

Purpose
-------
Computes mission propeller shaft-power demand and performs conceptual sizing
of a complete turboelectric propulsion/power group: N_engine gas-turbine
generator sets feeding an electrical bus that drives N_propulsor electric
motor + propeller units, for a single power_source architecture:
"turboelectric".

Like Turboprop.py, this is a self-contained architecture component that
replaces BOTH Propulsion.py and Power.py for this one architecture, since
the turbine core, generator, motor, and propeller form a single fuel-to-
thrust chain with no independently-sized battery/tank. Wire this INSTEAD
OF Propulsion + Power when power_source == "turboelectric".

Adapted from a general-aircraft gpkit reference (Cheetah Project)

Power flow / fuel-burn chain
-----------------------------
    P_shaft (propellers, total)
        -> / gearbox_efficiency                      -> P_motor_out
        -> / motor_efficiency / inverter_efficiency   -> P_elec (bus demand)
        -> / generator_efficiency                     -> P_core (turbine shaft power, total)
        -> / turboshaft_thermal_efficiency, / fuel_lhv -> fuel_flow

    fuel_flow = P_core / (eta_th * LHV)

Mission-versus-rating convention (matches Propulsion.py)
----------------------------------------------------------
Mission shaft power is calculated from the cruise thrust history; takeoff
power from the takeoff thrust; the installed/rated shaft power is:

    P_sh,rated = max(max(P_sh,mission), P_sh,takeoff, installed_shaft_power)

All downstream ratings (electrical bus, generator, core) are propagated
from ``rated_shaft_power`` through the same efficiency chain used for the
mission history, so conversion equipment is sized on the same physical
basis as the fuel burn.

Mass convention (matches Propulsion.py / Power.py)
----------------------------------------------------
Ratings are total installed powers for the complete group; per-unit power
is obtained by dividing by n_engine (cores) or n_propulsor (motors/props)
as appropriate. Specific-power technology inputs are interpreted on a
total installed power basis, e.g.:

    core_mass = rated_core_power / turboshaft_specific_power
    generator_mass = rated_electrical_power / generator_specific_power
    motor_mass = rated_shaft_power / motor_specific_power

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


class Turboelectric(om.ExplicitComponent):
    """Gas-turbine-generator + motor + propeller propulsion/power group."""

    def initialize(self):
        self.options.declare("phd", types=object, default=None, allow_none=True)
        self.options.declare("num_steps", default=1, types=int)

        # ------------------------------------------------------------
        # Propeller sizing (same conventions as Propulsion.py)
        # ------------------------------------------------------------
        self.options.declare("prop_power_coeff", default=0.65, types=float)
        self.options.declare("takeoff_speed", default=19.0, types=float)
        self.options.declare("propeller_mass_per_watt", default=1.2e-4, types=float)
        self.options.declare("minimum_propeller_mass_each", default=20.0, types=float)
        self.options.declare(
            "nacelle_mass_per_kw",
            default=3.0,
            types=float,
            desc="Electric-motor nacelle mass coefficient in kg/kW per propulsor.",
        )
        self.options.declare("enable_mount_mass", default=True, types=bool)
        self.options.declare("mount_mass_per_kn", default=0.03, types=float)

        # ------------------------------------------------------------
        # Distributed-power wiring (bus cabling from cores to propulsors)
        # ------------------------------------------------------------
        self.options.declare("enable_wiring_mass", default=True, types=bool)
        self.options.declare(
            "wiring_mass_per_kw",
            default=0.10,
            types=float,
            desc="Bus cabling mass coefficient in kg/kW of rated electrical power.",
        )

        # ------------------------------------------------------------
        # Fuel-system / accessory allowances (same conventions as Power.py)
        # ------------------------------------------------------------
        self.options.declare("fuel_system_mass_per_kw", default=0.01, types=float)
        self.options.declare("fixed_accessory_mass", default=40.0, types=float)
        self.options.declare(
            "inverter_specific_power",
            default=10_000.0,
            types=float,
            desc="Inverter specific power in W/kg.",
        )
        self.options.declare(
            "power_system_power_density",
            default=500_000.0,
            types=float,
            desc="Installed turboelectric power-system volumetric density in W/m^3.",
        )

        self.options.declare("debug_print", default=False, types=bool)

    def setup(self):
        n = self.options["num_steps"]

        # ==============================================================
        # Architecture and mission inputs
        # ==============================================================
        self.add_input("n_engine", val=2.0, desc="Number of turbine-generator cores.")
        self.add_input(
            "n_propulsor",
            val=2.0,
            desc="Number of motor-driven propellers (may differ from n_engine).",
        )
        self.add_input("thrust_cruise", val=np.zeros(n), units="N")
        self.add_input("thrust_to", val=4_400.0, units="N")
        self.add_input("tas", val=np.full(n, 19.5), units="m/s")
        self.add_input("propeller_efficiency", val=0.80)
        self.add_input(
            "gearbox_efficiency",
            val=1.0,
            desc="Motor-to-propeller gearbox efficiency (1.0 for direct drive).",
        )
        self.add_input("rho", val=np.full(n, 1.099), units="kg/m**3")
        self.add_input("thrust_vector_angle", val=0.0, units="deg")
        self.add_input("installed_shaft_power", val=-1.0, units="W")
        self.add_input("mission_duration", val=36_000.0, units="s")

        # ==============================================================
        # Technology inputs
        # ==============================================================
        self.add_input("motor_efficiency", val=0.95)
        self.add_input("inverter_efficiency", val=0.98)
        self.add_input("generator_efficiency", val=0.96)
        self.add_input(
            "turboshaft_thermal_efficiency",
            val=0.32,
            desc="Gas-turbine core chemical-to-shaft efficiency.",
        )
        self.add_input(
            "turboshaft_specific_power",
            val=3_500.0,
            units="W/kg",
            desc="Gas-generator (turbine core) specific power, rated-power basis.",
        )
        self.add_input(
            "generator_specific_power",
            val=5_000.0,
            units="W/kg",
            desc="Electrical generator specific power, rated electrical-power basis.",
        )
        self.add_input(
            "motor_specific_power",
            val=5_000.0,
            units="W/kg",
            desc="Electric-motor specific power, rated shaft-power basis.",
        )
        self.add_input("fuel_lhv", val=43.0e6, units="J/kg")
        self.add_input(
            "inverter_specific_power",
            val=float(self.options["inverter_specific_power"]),
            units="W/kg",
        )

        # ==============================================================
        # Mission power / fuel-flow outputs
        # ==============================================================
        self.add_output("shaft_power", val=np.zeros(n), units="W")
        self.add_output("required_power", val=np.zeros(n), units="W", desc="Alias of shaft_power.")
        self.add_output(
            "electrical_power",
            val=np.zeros(n),
            units="W",
            desc="Mission electrical-bus demand history.",
        )
        self.add_output(
            "core_shaft_power",
            val=np.zeros(n),
            units="W",
            desc="Mission total turbine-core shaft-power history.",
        )
        self.add_output("fuel_flow", val=np.zeros(n), units="kg/s")
        self.add_output("avg_efficiency", val=0.0)

        # ==============================================================
        # Installed/rated power outputs
        # ==============================================================
        self.add_output("takeoff_shaft_power", val=0.0, units="W")
        self.add_output("rated_shaft_power", val=0.0, units="W")
        self.add_output("rated_shaft_power_per_unit", val=0.0, units="W")
        self.add_output("rated_electrical_power", val=0.0, units="W")
        self.add_output("rated_core_power", val=0.0, units="W")
        self.add_output("rated_core_power_per_unit", val=0.0, units="W")

        # ==============================================================
        # Mass and geometry outputs
        # ==============================================================
        self.add_output("core_mass", val=0.0, units="kg", desc="Total gas-turbine core mass.")
        self.add_output("generator_mass", val=0.0, units="kg")
        self.add_output("inverter_mass", val=0.0, units="kg")
        self.add_output("motor_mass", val=0.0, units="kg", desc="Total electric-motor mass.")
        self.add_output("nacelle_mass", val=0.0, units="kg")
        self.add_output("propeller_mass", val=0.0, units="kg")
        self.add_output("pylon_mass", val=0.0, units="kg")
        self.add_output("wiring_mass", val=0.0, units="kg")
        self.add_output("fuel_system_mass", val=0.0, units="kg")
        self.add_output(
            "total_mass",
            val=0.0,
            units="kg",
            desc="Complete turboelectric propulsion+power group mass.",
        )
        self.add_output(
            "propulsion_mass",
            val=0.0,
            units="kg",
            desc="Motor, nacelle, propeller, and mount mass only.",
        )
        self.add_output("power_system_volume", val=0.0, units="m**3")
        self.add_output("required_rated_shaft_power", val=0.0, units="W")
        self.add_output("power_shortfall", val=0.0, units="W")
        self.add_output("propeller_diameter", val=0.0, units="m")

        # Backward-compatible aliases matching Propulsion.py's naming.
        self.add_output("prime_mover_mass", val=0.0, units="kg", desc="Alias of motor_mass.")
        self.add_output(
            "power_system_mass",
            val=0.0,
            units="kg",
            desc="Alias of core_mass + generator_mass + fuel_system_mass.",
        )

        self.declare_partials("*", "*", method="fd", step=1.0e-8)

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

    def compute(self, inputs, outputs):
        n = self.options["num_steps"]

        n_engine = max(int(round(self._scalar(inputs["n_engine"]))), 1)
        n_propulsor = max(int(round(self._scalar(inputs["n_propulsor"]))), 1)

        thrust_cruise = self._vector(inputs["thrust_cruise"], n, minimum=0.0)
        thrust_takeoff_total = max(self._scalar(inputs["thrust_to"]), 0.0)
        tas = self._vector(inputs["tas"], n, minimum=0.1)
        rho = self._vector(inputs["rho"], n, minimum=1.0e-6)

        propeller_efficiency = float(np.clip(self._scalar(inputs["propeller_efficiency"]), 0.05, 0.99))
        gearbox_efficiency = float(np.clip(self._scalar(inputs["gearbox_efficiency"]), 0.10, 1.0))
        thrust_vector_angle = float(np.clip(self._scalar(inputs["thrust_vector_angle"]), -90.0, 90.0))

        eta_motor = float(np.clip(self._scalar(inputs["motor_efficiency"]), 0.10, 1.0))
        eta_inverter = float(np.clip(self._scalar(inputs["inverter_efficiency"]), 0.10, 1.0))
        eta_generator = float(np.clip(self._scalar(inputs["generator_efficiency"]), 0.10, 1.0))
        eta_th = float(np.clip(self._scalar(inputs["turboshaft_thermal_efficiency"]), 0.05, 0.55))

        specific_power_core = max(self._scalar(inputs["turboshaft_specific_power"]), 1.0)
        specific_power_gen = max(self._scalar(inputs["generator_specific_power"]), 1.0)
        specific_power_motor = max(self._scalar(inputs["motor_specific_power"]), 1.0)
        specific_power_inverter = max(
            self._scalar(inputs["inverter_specific_power"]), 1.0
        )
        lhv = max(self._scalar(inputs["fuel_lhv"]), 1.0)

        eta_chain_elec = gearbox_efficiency * eta_motor * eta_inverter

        # ==============================================================
        # 1. Mission shaft, electrical-bus, and core power
        # ==============================================================
        shaft_power_mission = thrust_cruise * tas / propeller_efficiency
        electrical_power_mission = shaft_power_mission / eta_chain_elec
        core_shaft_power_mission = electrical_power_mission / eta_generator

        # ==============================================================
        # 2. Takeoff and installed rating (propagated through same chain)
        # ==============================================================
        takeoff_speed = max(float(self.options["takeoff_speed"]), 0.1)
        axial_takeoff_thrust = max(thrust_takeoff_total * np.cos(np.radians(thrust_vector_angle)), 0.0)
        takeoff_shaft_power = axial_takeoff_thrust * takeoff_speed / propeller_efficiency

        peak_mission_shaft_power = float(np.max(shaft_power_mission))
        required_rated_shaft_power = max(peak_mission_shaft_power, takeoff_shaft_power)

        installed_shaft_power = self._scalar(inputs["installed_shaft_power"])
        if installed_shaft_power >= 0.0:
            # Validation mode: size hardware to the stated installed rating.
            rated_shaft_power = installed_shaft_power
        else:
            # Design mode: no external rating, so size to the requirement.
            rated_shaft_power = required_rated_shaft_power
        power_shortfall = required_rated_shaft_power - rated_shaft_power

        rated_shaft_power_per_unit = rated_shaft_power / n_propulsor
        rated_electrical_power = rated_shaft_power / eta_chain_elec
        rated_core_power = rated_electrical_power / eta_generator
        rated_core_power_per_unit = rated_core_power / n_engine

        # ==============================================================
        # 3. Fuel flow (chemical energy -> turbine shaft, before generator)
        # ==============================================================
        fuel_flow = core_shaft_power_mission / (eta_th * lhv)

        # ==============================================================
        # 4. Core / generator / motor mass
        # ==============================================================
        core_mass = rated_core_power / specific_power_core
        generator_mass = rated_electrical_power / specific_power_gen
        inverter_mass = rated_electrical_power / specific_power_inverter
        motor_mass = rated_shaft_power / specific_power_motor

        # ==============================================================
        # 5. Nacelle / propeller / mount mass (per propulsor, then totalled)
        # ==============================================================
        nacelle_mass_per_kw = float(self.options["nacelle_mass_per_kw"])
        nacelle_mass_each = rated_shaft_power_per_unit / 1000.0 * max(nacelle_mass_per_kw, 0.0)
        nacelle_mass = nacelle_mass_each * n_propulsor

        propeller_mass_each = max(
            float(self.options["propeller_mass_per_watt"]) * rated_shaft_power_per_unit,
            float(self.options["minimum_propeller_mass_each"]),
        )
        propeller_mass = propeller_mass_each * n_propulsor

        mount_mass = 0.0
        if self.options["enable_mount_mass"]:
            thrust_per_unit = thrust_takeoff_total / n_propulsor
            mount_mass_each = float(self.options["mount_mass_per_kn"]) * (thrust_per_unit / 1000.0)
            mount_mass_each = float(np.clip(mount_mass_each, 15.0, 75.0))
            mount_mass = mount_mass_each * n_propulsor

        # ==============================================================
        # 6. Bus wiring mass (turbine-generator cores to distributed motors)
        # ==============================================================
        wiring_mass = 0.0
        if self.options["enable_wiring_mass"]:
            wiring_mass = float(self.options["wiring_mass_per_kw"]) * (rated_electrical_power / 1000.0)

        # ==============================================================
        # 7. Fuel-system / accessory allowance
        # ==============================================================
        fuel_system_mass = float(self.options["fuel_system_mass_per_kw"]) * (rated_core_power / 1000.0)
        fixed_accessory_mass = max(float(self.options["fixed_accessory_mass"]), 0.0)
        fuel_system_mass_total = fuel_system_mass + fixed_accessory_mass

        total_mass = (
            core_mass
            + generator_mass
            + inverter_mass
            + motor_mass
            + nacelle_mass
            + propeller_mass
            + mount_mass
            + wiring_mass
            + fuel_system_mass_total
        )

        # ==============================================================
        # 8. Propeller diameter (same formula as Propulsion.py)
        # ==============================================================
        rho_reference = max(float(rho[0]), 1.0e-6)
        tas_reference = max(float(tas[0]), 0.1)
        power_coefficient = max(float(self.options["prop_power_coeff"]), 1.0e-6)
        propeller_diameter = np.sqrt(
            rated_shaft_power_per_unit / (rho_reference * tas_reference**3 * power_coefficient)
        )
        propeller_diameter = float(np.clip(propeller_diameter, 1.0, 8.0))

        # ==============================================================
        # Outputs
        # ==============================================================
        outputs["shaft_power"] = shaft_power_mission
        outputs["required_power"] = shaft_power_mission
        outputs["electrical_power"] = electrical_power_mission
        outputs["core_shaft_power"] = core_shaft_power_mission
        outputs["fuel_flow"] = fuel_flow
        outputs["avg_efficiency"] = eta_th * eta_generator * eta_inverter * eta_motor * gearbox_efficiency

        outputs["takeoff_shaft_power"] = takeoff_shaft_power
        outputs["rated_shaft_power"] = rated_shaft_power
        outputs["rated_shaft_power_per_unit"] = rated_shaft_power_per_unit
        outputs["rated_electrical_power"] = rated_electrical_power
        outputs["rated_core_power"] = rated_core_power
        outputs["rated_core_power_per_unit"] = rated_core_power_per_unit

        outputs["core_mass"] = core_mass
        outputs["generator_mass"] = generator_mass
        outputs["inverter_mass"] = inverter_mass
        outputs["motor_mass"] = motor_mass
        outputs["nacelle_mass"] = nacelle_mass
        outputs["propeller_mass"] = propeller_mass
        outputs["pylon_mass"] = mount_mass
        outputs["wiring_mass"] = wiring_mass
        outputs["fuel_system_mass"] = fuel_system_mass_total
        outputs["total_mass"] = total_mass
        outputs["propeller_diameter"] = propeller_diameter

        propulsion_mass = motor_mass + nacelle_mass + propeller_mass + mount_mass
        power_system_mass = (
            core_mass
            + generator_mass
            + inverter_mass
            + wiring_mass
            + fuel_system_mass_total
        )
        power_system_volume = rated_core_power / max(
            float(self.options["power_system_power_density"]), 1.0
        )

        outputs["prime_mover_mass"] = motor_mass
        outputs["propulsion_mass"] = propulsion_mass
        outputs["power_system_mass"] = power_system_mass
        outputs["power_system_volume"] = power_system_volume
        outputs["required_rated_shaft_power"] = required_rated_shaft_power
        outputs["power_shortfall"] = power_shortfall

        if self.options["debug_print"]:
            print(
                f"[Turboelectric] P_mission_max={peak_mission_shaft_power / 1000.0:.1f} kW "
                f"P_elec={float(np.max(electrical_power_mission)) / 1000.0:.1f} kW "
                f"P_core={float(np.max(core_shaft_power_mission)) / 1000.0:.1f} kW "
                f"fuel_flow[0]={float(fuel_flow[0]) * 1e3:.3f} g/s "
                f"total_mass={total_mass:.1f} kg"
            )


if __name__ == "__main__":
    problem = om.Problem()
    problem.model.add_subsystem("turboelectric", Turboelectric(num_steps=5), promotes=["*"])
    problem.setup()

    problem.set_val("n_engine", 2.0)
    problem.set_val("n_propulsor", 4.0)
    problem.set_val("thrust_cruise", np.full(5, 8_000.0), units="N")
    problem.set_val("thrust_to", 12_000.0, units="N")
    problem.set_val("tas", np.full(5, 25.0), units="m/s")
    problem.set_val("propeller_efficiency", 0.80)
    problem.set_val("motor_efficiency", 0.95)
    problem.set_val("inverter_efficiency", 0.98)
    problem.set_val("generator_efficiency", 0.96)
    problem.set_val("turboshaft_thermal_efficiency", 0.32)
    problem.set_val("turboshaft_specific_power", 3_500.0, units="W/kg")
    problem.set_val("generator_specific_power", 5_000.0, units="W/kg")
    problem.set_val("motor_specific_power", 5_000.0, units="W/kg")
    problem.set_val("fuel_lhv", 43.0e6, units="J/kg")

    problem.run_model()

    print("\n=== Turboelectric smoke test ===")
    print(f"Mission shaft power  : {np.max(problem.get_val('shaft_power')) / 1000.0:.1f} kW")
    print(f"Rated electrical pwr : {problem.get_val('rated_electrical_power')[0] / 1000.0:.1f} kW")
    print(f"Rated core power     : {problem.get_val('rated_core_power')[0] / 1000.0:.1f} kW")
    print(f"Core (turbine) mass  : {problem.get_val('core_mass')[0]:.1f} kg")
    print(f"Generator mass       : {problem.get_val('generator_mass')[0]:.1f} kg")
    print(f"Motor mass (total)   : {problem.get_val('motor_mass')[0]:.1f} kg")
    print(f"Wiring mass          : {problem.get_val('wiring_mass')[0]:.1f} kg")
    print(f"Total group mass     : {problem.get_val('total_mass')[0]:.1f} kg")
    print(f"Fuel flow[0]         : {float(problem.get_val('fuel_flow')[0]) * 1e3:.3f} g/s")
    print(f"Propeller diameter   : {problem.get_val('propeller_diameter')[0]:.2f} m")
