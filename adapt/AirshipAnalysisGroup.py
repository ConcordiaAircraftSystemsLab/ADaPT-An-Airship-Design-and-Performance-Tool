# -*- coding: utf-8 -*-
"""
Airship Analysis Group for ADaPT
================================

Purpose
-------
Top-level multidisciplinary integration group for the ADaPT conceptual
airship framework.

The group assembles:

    - centralized independent variables,
    - atmospheric models,
    - geometry,
    - mission performance,
    - propulsion,
    - architecture-dependent power conversion,
    - battery and photovoltaic sizing,
    - hydrogen storage,
    - fuel-cell polarization,
    - vehicle weight and MTOW closure.

Component ownership
-------------------
The final ownership convention is:

    AirshipIndepVariables
        Mission, geometry, operating, and technology assumptions.

    AirshipPerformance
        Aerodynamics, thrust, shaft-energy demand, mission performance,
        operational constraints, and externally supplied resource
        feasibility.

    Propulsion
        Propeller shaft power and engine/motor/propeller/nacelle/mount mass.

    Power
        Upstream power conversion, hybrid source allocation, fuel flow,
        generator/accessory hardware, fuel-cell stack/BoP mass, PV mass for
        solar-hydrogen hybrid, and the ICE-generator source package for the
        series conventional-battery hybrid.

    BatteryOnly
        Battery capacity, battery mass, battery volume, and usable battery
        energy.

    SolarBattery
        Standalone solar-battery PV and battery sizing.

    Tank
        Hydrogen used, reserve hydrogen, installed hydrogen mass, empty tank
        mass, tank volume, and usable primary energy.

    AirshipWeight
        OEW, MTOW, mass breakdown, helium-volume closure, and final mass
        summation using one neutral ``consumable_mass`` input.

Mass closure
------------
For conventional fuel architectures:

    Power.fuel_flow
        -> ConsumableMassSizer
        -> required fuel, used fuel, usable primary energy
        -> Mission and AirshipWeight

For hydrogen architectures:

    Power.fuel_flow
        -> Tank
        -> hydrogen mass, used hydrogen, tank mass/volume
        -> Mission and AirshipWeight

For battery architectures:

    Power electrical demand
        -> BatteryOnly or SolarBattery
        -> battery mass and usable battery energy
        -> Mission and AirshipWeight

Supported architectures
-----------------------
    conventional_reciprocating
    hydrogen_reciprocating
    hydrogen_fuel_cell
    battery_only
    solar_battery
    solar-RFC
    hydrogen_hybrid
    solar_hydrogen_hybrid
    conventional_battery_hybrid
    turboprop
    turboelectric

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


# =============================================================================
# ADaPT imports
# =============================================================================

try:
    # Package mode
    from .operatingConditions import opCond
    from .AirshipIndepVariables import AirshipIndepVariables
    from .Atmosphere import Atmosphere
    from .AirshipGeometry import AirshipGeometry
    from .AirshipPerformance import AirshipPerformance
    from .Propulsion import Propulsion
    from .Power import Power
    from .BatteryOnly import BatteryOnly
    from .SolarBattery import SolarBattery
    from .Tank import Tank
    from .FuelCellPolarization import FuelCellPolarization
    from .AirshipWeight import AirshipWeight
    from .Turboelectric import Turboelectric
    from .Turboprop import Turboprop

except ImportError:
    # Standalone/script mode
    from operatingConditions import opCond
    from AirshipIndepVariables import AirshipIndepVariables
    from Atmosphere import Atmosphere
    from AirshipGeometry import AirshipGeometry
    from AirshipPerformance import AirshipPerformance
    from Propulsion import Propulsion
    from Power import Power
    from BatteryOnly import BatteryOnly
    from SolarBattery import SolarBattery
    from Tank import Tank
    from FuelCellPolarization import FuelCellPolarization
    from AirshipWeight import AirshipWeight
    from Turboelectric import Turboelectric
    from Turboprop import Turboprop

FUEL_SOURCES = [
    "conventional_reciprocating",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
]

HYDROGEN_SOURCES = [
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

HYDROGEN_HYBRIDS = [
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
]

ICE_HYBRIDS = [
    "conventional_battery_hybrid",
]

SOLAR_HYBRIDS = [
    "solar_hydrogen_hybrid",
]

FUEL_CELL_SOURCES = [
    "hydrogen_fuel_cell",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
]

TANK_SOURCES = HYDROGEN_SOURCES + HYDROGEN_HYBRIDS

TURBINE_SOURCES = [
    "turboprop",
    "turboelectric",
]

ALL_POWER_SOURCES = (
    FUEL_SOURCES
    + BATTERY_SOURCES
    + HYBRID_SOURCES
    + TURBINE_SOURCES
)


class MissionDuration(om.ExplicitComponent):
    """Compute cruise mission duration from range and ground speed."""

    def initialize(self):
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )

    def setup(self):
        n = self.options["num_steps"]

        self.add_input(
            "range",
            val=1.0,
            units="m",
        )
        self.add_input(
            "cruise_speed",
            val=np.full(n, 1.0),
            units="m/s",
        )
        self.add_input(
            "tailwind_speed",
            val=0.0,
            units="m/s",
        )
        self.add_output(
            "mission_duration",
            val=0.0,
            units="s",
        )

        self.declare_partials(
            "*",
            "*",
            method="fd",
        )

    def compute(self, inputs, outputs):
        cruise_speed = float(
            np.atleast_1d(inputs["cruise_speed"])[0]
        )
        tailwind = float(
            np.atleast_1d(inputs["tailwind_speed"])[0]
        )
        effective_speed = max(
            cruise_speed - tailwind,
            0.1,
        )

        outputs["mission_duration"] = (
            float(np.atleast_1d(inputs["range"])[0])
            / effective_speed
        )


class ConsumableMassSizer(om.ExplicitComponent):
    """
    Integrate non-hydrogen fuel flow and apply reserve.

    This component is used for:
        conventional_reciprocating
        conventional_battery_hybrid

    Hydrogen architectures use Tank instead.
    """

    def initialize(self):
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )

    def setup(self):
        n = self.options["num_steps"]

        self.add_input(
            "fuel_flow",
            val=np.zeros(n),
            units="kg/s",
        )
        self.add_input(
            "mission_duration",
            val=36_000.0,
            units="s",
        )
        self.add_input(
            "fuel_reserve_fraction",
            val=0.10,
        )
        self.add_input(
            "fuel_lhv",
            val=43.0e6,
            units="J/kg",
        )
        self.add_input(
            "conversion_efficiency",
            val=0.30,
        )

        self.add_output(
            "consumable_mass_used",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "consumable_reserve_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "required_consumable_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "usable_primary_energy",
            val=0.0,
            units="W*h",
        )

        self.declare_partials(
            "*",
            "*",
            method="fd",
        )

    def compute(self, inputs, outputs):
        fuel_flow = np.maximum(
            np.atleast_1d(inputs["fuel_flow"]).astype(float),
            0.0,
        )
        duration = max(
            float(np.atleast_1d(inputs["mission_duration"])[0]),
            0.0,
        )
        reserve_fraction = max(
            float(
                np.atleast_1d(
                    inputs["fuel_reserve_fraction"]
                )[0]
            ),
            0.0,
        )
        fuel_lhv = max(
            float(np.atleast_1d(inputs["fuel_lhv"])[0]),
            1.0,
        )
        efficiency = float(
            np.clip(
                np.atleast_1d(
                    inputs["conversion_efficiency"]
                )[0],
                0.0,
                1.0,
            )
        )

        dt = duration / max(fuel_flow.size, 1)
        used_mass = float(np.sum(fuel_flow) * dt)
        reserve_mass = used_mass * reserve_fraction
        installed_mass = used_mass + reserve_mass

        usable_energy_Wh = (
            installed_mass
            * fuel_lhv
            * efficiency
            / 3600.0
        )

        outputs["consumable_mass_used"] = used_mass
        outputs["consumable_reserve_mass"] = reserve_mass
        outputs["required_consumable_mass"] = installed_mass
        outputs["usable_primary_energy"] = usable_energy_Wh


class EnergyIntegrator(om.ExplicitComponent):
    """Integrate a power history into energy in Wh."""

    def initialize(self):
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )

    def setup(self):
        n = self.options["num_steps"]

        self.add_input(
            "power",
            val=np.zeros(n),
            units="W",
        )
        self.add_input(
            "duration",
            val=36_000.0,
            units="s",
        )
        self.add_output(
            "energy",
            val=0.0,
            units="W*h",
        )

        self.declare_partials(
            "*",
            "*",
            method="fd",
        )

    def compute(self, inputs, outputs):
        power = np.maximum(
            np.atleast_1d(inputs["power"]).astype(float),
            0.0,
        )
        duration = max(
            float(np.atleast_1d(inputs["duration"])[0]),
            0.0,
        )
        dt = duration / max(power.size, 1)

        outputs["energy"] = (
            float(np.sum(power) * dt / 3600.0)
        )


class AtmosphereDiscipline(om.Group):
    """Bundle cruise and take-off atmosphere evaluations as one XDSM discipline."""

    def initialize(self):
        self.options.declare("phd", types=opCond)
        self.options.declare("num_steps", default=1, types=int)

    def setup(self):
        phd = self.options["phd"]
        n = self.options["num_steps"]

        self.add_subsystem(
            "cruise",
            Atmosphere(phd=phd, num_steps=n),
            promotes_inputs=[
                ("altitude", "cruise_altp"),
                ("disa", "cruise_disa"),
            ],
        )
        self.add_subsystem(
            "takeoff",
            Atmosphere(phd=phd, num_steps=n),
            promotes_inputs=[
                ("altitude", "zero_alt"),
                ("disa", "zero_disa"),
            ],
        )

        # Maximum pressure-altitude atmosphere used consistently by Geometry
        # (ballonet sizing) and Weight (maximum-altitude helium mass).
        self.add_subsystem(
            "max_altitude",
            Atmosphere(phd=phd, num_steps=1),
            promotes_inputs=[
                ("altitude", "max_operating_altitude"),
                ("disa", "weight_max_altitude_disa"),
            ],
        )



class WeightDesignCondition(om.ExplicitComponent):
    """Derive scalar design-condition quantities required by AirshipWeight.

    The updated Chapter-9 weight relationships need a maximum speed and a
    corresponding dynamic pressure.  Until a separate V_max requirement is
    introduced in AirshipIndepVariables, this integration component uses the
    maximum prescribed mission/cruise speed and the corresponding maximum
    cruise atmospheric density.

    This keeps the coupling explicit and avoids silently using defaults inside
    AirshipWeight.  A later clean-sheet study can replace these derived values
    with a dedicated design-speed requirement without changing AirshipWeight.
    """

    def initialize(self):
        self.options.declare("num_steps", default=1, types=int)

    def setup(self):
        n = self.options["num_steps"]
        self.add_input(
           "maximum_speed",
           val=1.0,
           units="m/s",
       )
        self.add_input(
            "rho_design",
            val=1.225,
            units="kg/m**3",
        )

        self.add_output(
            "maximum_speed_for_weight",
            val=1.0,
            units="m/s",
        )
        self.add_output(
            "max_dynamic_pressure_for_weight",
            val=1.0,
            units="Pa",
        )
        self.declare_partials("*", "*", method="fd")

    def compute(self, inputs, outputs):

        vmax = max(
            float(np.atleast_1d(
                inputs["maximum_speed"]
            )[0]),
            0.0,
        )

        rho = max(
            float(np.atleast_1d(
                inputs["rho_design"]
            )[0]),
            0.0,
        )

        outputs[
            "max_dynamic_pressure_for_weight"
        ] = 0.5 * rho * vmax**2

class WeightClosureAudit(om.ExplicitComponent):
    """Final audit block for the closed-loop airship mass solution.

    ``AirshipWeight`` already performs the actual mass buildup and exposes
    ``mass_balance_error``.  This component intentionally does not create a
    second competing MTOW model.  It reports the final closure residual after
    mission, propulsion, power-system, and consumable sizing have updated the
    masses that feed back to ``weight`` on the next nonlinear sweep.
    """

    def setup(self):
        self.add_input("mtow", val=5000.0, units="kg")
        self.add_input("mass_balance_error", val=0.0, units="kg")
        self.add_input("installed_consumable_mass", val=0.0, units="kg")
        self.add_input("propulsion_mass", val=0.0, units="kg")
        self.add_input("power_system_mass", val=0.0, units="kg")

        self.add_output("weight_closure_residual", val=0.0, units="kg")
        self.add_output("weight_closure_relative", val=0.0)
        self.add_output("closed_loop_mtow", val=5000.0, units="kg")

        self.declare_partials(
            of="weight_closure_residual",
            wrt="mass_balance_error",
            val=1.0,
        )
        self.declare_partials(of="weight_closure_residual", wrt="mtow", val=0.0)
        self.declare_partials(of="closed_loop_mtow", wrt="mtow", val=1.0)
        self.declare_partials(
            of="weight_closure_relative",
            wrt=["mtow", "mass_balance_error"],
            method="fd",
        )
        # These inputs are retained explicitly so the XDSM displays the
        # downstream mass updates entering the closure audit.
        self.declare_partials(
            of=["weight_closure_residual", "weight_closure_relative", "closed_loop_mtow"],
            wrt=["installed_consumable_mass", "propulsion_mass", "power_system_mass"],
            val=0.0,
        )

    def compute(self, inputs, outputs):
        mtow = float(np.atleast_1d(inputs["mtow"])[0])
        residual = float(np.atleast_1d(inputs["mass_balance_error"])[0])
        outputs["weight_closure_residual"] = residual
        outputs["weight_closure_relative"] = abs(residual) / max(abs(mtow), 1.0)
        outputs["closed_loop_mtow"] = mtow


class AirshipAnalysisGroup(om.Group):
    """Fully coupled multidisciplinary ADaPT airship model."""

    def initialize(self):
        self.options.declare(
            "phd",
            types=opCond,
        )
        self.options.declare(
            "airship_type",
            default="non-rigid",
            values=["non-rigid", "semi-rigid", "rigid"],
        )
        self.options.declare(
            "enable_pressure_control",
            default=False,
            types=bool,
        )
        self.options.declare(
            "power_source",
            default="conventional_reciprocating",
            values=ALL_POWER_SOURCES,
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
        )
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )

        self.options.declare(
            "ballonet_sizing_method",
            default="pressure_altitude",
            values=[
                "pressure_altitude",
                "prescribed_fraction",
            ],
        )

        self.options.declare(
            "use_prescribed_consumable_capacity",
            default=False,
            types=bool,
        )

        self.options.declare(
            "tail_coefficient_method",
            default="user",
            values=["user", "historical"],
        )

        self.options.declare(
            "propulsion_installation_mass_method",
            default="generic",
            values=[
                "generic",
                "structure_integrated",
                "override",
            ],
        )

        self.options.declare(
            "propulsion_prime_mover_mass_method",
            default="specific_power",
            values=[
                "specific_power",
                "book_reciprocating",
                "override",
            ],
        )

        self.options.declare(
            "propulsion_prime_mover_mass_override",
            default=0.0,
            types=float,
        )

        # ==============================================================
        # Weight-model configuration
        # ==============================================================

        self.options.declare(
            "weight_gondola_method",
            default="book",
            values=["book", "override", "simpified"],
        )

        self.options.declare(
            "weight_gondola_category",
            default=2,
            values=[1, 2, 3],
        )

        self.options.declare(
            "weight_gondola_mass_override",
            default=0.0,
            types=float,
        )

        self.options.declare(
            "weight_miscellaneous_fraction",
            default=0.035,
            types=float,
        )

        self.options.declare(
            "weight_fuel_tank_method",
            default="none",
            values=["none", "book", "override"],
        )

        self.options.declare(
            "weight_fuel_tank_mass_override",
            default=0.0,
            types=float,
        )

        self.options.declare(
            "weight_pressure_system_method",
            default="none",
            values=["none", "book_fraction", "override"],
        )

        self.options.declare(
            "weight_pressure_system_mass_override",
            default=0.0,
            types=float,
        )

        self.options.declare(
            "weight_vms_method",
            default="none",
            values=["none", "book_fraction", "override"],
        )

        self.options.declare(
            "weight_vms_mass_override",
            default=0.0,
            types=float,
        )

    def setup(self):
        phd = self.options["phd"]
        power_source = self.options["power_source"]
        landing_system = self.options["landing_system"]
        airship_type = self.options["airship_type"]
        n = self.options["num_steps"]
        pressure_control = self.options[
            "enable_pressure_control"
        ]

        tail_coefficient_method = (
            self.options["tail_coefficient_method"]
        )
        ballonet_sizing_method = self.options[
            "ballonet_sizing_method"
        ]
        electric_propulsion = (
            power_source
            in [
                "hydrogen_fuel_cell",
                "battery_only",
                "solar_battery",
                "solar-RFC",
                "hydrogen_hybrid",
                "solar_hydrogen_hybrid",
                "conventional_battery_hybrid",
            ]
        )

        engine_type = (
            "electric"
            if electric_propulsion
            else "reciprocating"
        )

        # ==============================================================
        # Central independent variables
        # ==============================================================

        self.add_subsystem(
            "indep",
            AirshipIndepVariables(num_steps=n),
            promotes_outputs=["*"],
        )

        # Maximum-altitude atmosphere condition.
        # The authoritative altitude is the central independent variable
        # ``max_operating_altitude``.  Only the maximum-altitude ISA deviation
        # remains as a local zero-DISA fallback until it becomes a dedicated
        # design variable.
        max_altitude_ivc = om.IndepVarComp()
        max_altitude_ivc.add_output(
            "weight_max_altitude_disa",
            val=np.zeros(1),
            units="K",
        )
        self.add_subsystem(
            "max_altitude_ivc",
            max_altitude_ivc,
            promotes_outputs=["weight_max_altitude_disa"],
        )

        # ==============================================================
        # Atmosphere
        # ==============================================================

        self.add_subsystem(
            "atmosphere",
            AtmosphereDiscipline(phd=phd, num_steps=n),
            promotes_inputs=[
                "cruise_altp",
                "cruise_disa",
                "zero_alt",
                "zero_disa",
                "max_operating_altitude",
                "weight_max_altitude_disa",
            ],
        )

        # ==============================================================
        # Geometry
        # ==============================================================

        geometry_inputs = [
               "length",
               "fineness_ratio",
               "tail_volume_coeff_horizontal",
               "tail_volume_coeff_vertical",
               "ballonet_fraction_prescribed",
               "hull_volume_shape_factor",
               "ballonet_fill_fraction_takeoff",
        ]

        geometry_outputs = [
            "gross_volume",
            "wetted_surface_area",
            "max_diameter",
            "ref_area_AeroCoeffs",
            "fin_total_wetted_area",
            "horizontal_tail_planform_area",
            "vertical_tail_planform_area",
            "tail_arm",
            "tail_volume_coeff_horizontal_used",
            "tail_volume_coeff_vertical_used",
            "ballonet_volume",
            "ballonet_fraction",
            "ballonet_fraction_violation",
            "aspect_ratio_geom",
            "length_violation",
            "fineness_ratio_violation",
            "lifting_gas_volume_takeoff",
        ]

        if airship_type in ["semi-rigid", "rigid"]:
            geometry_inputs += [
                "n_longitudinal_members",
                "n_rings",
            ]
            geometry_outputs += [
                "outer_envelope_area",
                "inner_envelope_area",
                "internal_fabric_area",
                "framework_total_member_length",
            ]

            if airship_type == "rigid":
                geometry_inputs.append("n_gas_cells")
                geometry_outputs += [
                    "gas_cell_volume_each",
                    "gas_cell_total_volume",
                ]

        self.add_subsystem(
            "geometry",
            AirshipGeometry(
                landing_system=landing_system,
                airship_type=airship_type,
                ballonet_sizing_method=ballonet_sizing_method,
                tail_coefficient_method=tail_coefficient_method,
            ),
            promotes_inputs=geometry_inputs,
            promotes_outputs=geometry_outputs,
        )

        # ==============================================================
        # Weight
        # ==============================================================

        weight_inputs = [
            "payload",
            "cruise_altp",
            "cruise_disa",
            "n_crew",
            "gross_volume",
            "ballonet_volume",
            "ballast_mass",

            # Geometry -> Weight
            "length",
            "max_diameter",
            "horizontal_tail_planform_area",
            "vertical_tail_planform_area",

            # Gondola design -> Weight
            "gondola_length",
            "gondola_width",
            "gondola_height",
            "gondola_surface_area",

            # Configuration -> Weight
            "BR_takeoff",
        ]

        weight_outputs = [
            "envelop_mass",
            "envelope_mass",
            "ballonet_mass",
            "curtain_mass",
            "curtain_area",
            "gondola_mass",
            "fuel_tank_mass",
            "pressure_system_mass",
            "vms_mass",
            "fin_mass",
            "tail_fixed_mass",
            "tail_control_surface_mass",
            "tail_actuator_mass",
            "tail_fpsq_used",
            "tail_fact_used",
            "landing_system_mass",
            "miscellaneous_mass",
            "weight_margin_mass",
            "unmargined_owe",
            "owe",
            "mtow",
            "operational_weight",
            "he_max_volume",
            "he_max_mass",
            "air_max_volume",
            "envelope_volume_violation",
            "crew_mass",
            "structure_mass",
            "installed_system_mass",
            "useful_load_mass",
            "installed_consumable_mass",
            "mass_balance_error",
        ]

        if airship_type in ["semi-rigid", "rigid"]:
            weight_inputs += [
                "outer_envelope_area",
                "inner_envelope_area",
                "framework_total_member_length",
            ]
            weight_outputs.append("framework_mass")

            if airship_type == "rigid":
                weight_inputs.append("gas_cell_total_volume")

        if landing_system == "acls":
            weight_inputs.append("acls_area")

        self.add_subsystem(
            "weight",
            AirshipWeight(
                phd=phd,
                power_source=power_source,
                landing_system=landing_system,
                num_steps=n,
                airship_type=airship_type,

                gondola_weight_method=self.options[
                    "weight_gondola_method"
                ],

                gondola_category=self.options[
                    "weight_gondola_category"
                ],

                gondola_mass_override=self.options[
                    "weight_gondola_mass_override"
                ],

                miscellaneous_fraction=self.options[
                    "weight_miscellaneous_fraction"
                ],

                fuel_tank_weight_method=self.options[
                    "weight_fuel_tank_method"
                ],

                fuel_tank_mass_override=self.options[
                    "weight_fuel_tank_mass_override"
                ],

                pressure_system_weight_method=self.options[
                    "weight_pressure_system_method"
                ],

                pressure_system_mass_override=self.options[
                    "weight_pressure_system_mass_override"
                ],

                vms_weight_method=self.options[
                    "weight_vms_method"
                ],

                vms_mass_override=self.options[
                    "weight_vms_mass_override"
                ],
            ),
            promotes_inputs=weight_inputs,
            promotes_outputs=weight_outputs,
        )

        # Explicit mission/atmosphere -> Weight design-condition coupling.
        self.add_subsystem(
            "weight_design_condition",
            WeightDesignCondition(),
            promotes_inputs=["maximum_speed"],
            promotes_outputs=[
                "max_dynamic_pressure_for_weight",
            ],
        )

        # ==============================================================
        # Mission
        # ==============================================================

        mission_inputs = [
            "range",
            "cruise_altp",
            "cruise_disa",
            "cruise_speed",
            "length",
            "n_engine",
            "gross_volume",
            "ballonet_volume",
            "operational_weight",
            "installed_shaft_power",
            "he_max_mass",
            "mtow",
            "ballast_mass",
            "lift_coeff",
            "drag_due_to_lift_factor",
            "drag_coeff_zero",
            "BR_takeoff",
            "BR_landing",
            "tailwind_speed",
            "thrust_vector_angle",
            "rudder_deflection",
            "cruise_strategy",
            "propeller_efficiency",
            "chi",
            "tau",
        ]

        if landing_system == "acls":
            mission_inputs.append("acls_area")

        if pressure_control:
            mission_inputs += [
                "ascent_rate",
                "descent_rate",
                "takeoff_altitude",
                "max_operating_altitude",
            ]

        mission_outputs = [
            "power_constraint",
            "energy_constraint",
            "energy_constraint_primary",
            "energy_constraint_bat",
            "buoyancy_constraint",
            "lift_constraint",
            "aerodynamic_lift_cruise",
            "thrust_to",
            "thrust_cruise",
            "required_shaft_power",
            "mission_speed_used",
            "mission_duration",
            "fuel_mass",
            "mission_consumable_mass_used",
            "mission_energy_required",
            "total_mission_energy_required",
            "battery_mass_required",
            "ground_roll_distance",
            "takeoff_ground_roll",
            "takeoff_rotation_distance",
            "takeoff_climbout_distance",
            "takeoff_distance",
            "takeoff_speed_calculated",
            "takeoff_average_speed",
            "takeoff_thrust_available_used",
            "takeoff_heaviness",
            "takeoff_accelerated_mass",
            "takeoff_climb_angle",
            "takeoff_climb_gradient",
            "buoyant_lift_required_takeoff",
            "buoyant_lift_available_takeoff",
            "lifting_gas_volume_takeoff_used",
            "heaviness_cruise",
            "buoyancy_ratio_cruise",
            "lift_coefficient_cruise",
            "mission_mass_used",
            "ballast_constraint",
            "landing_BR_constraint",
            "BR_landing_implied",
            "ballast_required",
            "landing_reference_speed",
            "landing_speed_50ft",
            "landing_touchdown_speed",
            "landing_air_distance",
            "landing_free_roll_distance",
            "landing_braking_distance",
            "landing_field_length",
            "minimum_power_speed",
            "turn_radius",
            "turn_speed",
            "turn_speed_ratio",
            "stability_margin",
            "drag_cruise",
            "drag_takeoff_avg",
            "drag_landing",
            "turn_time",
            "roc",
            "rod",
            "time",
            "endurance",
            "ground_constraint",
            "landing_constraint",
            "landing_distance",
            "eta_fc_used",
            "chi_consistency_error",
            "chi_implied",
            "tau_used",
        ]

        if pressure_control:
            mission_outputs += [
                "pressure_control_power",
                "pressure_control_energy",
            ]

        self.add_subsystem(
            "performance",
            AirshipPerformance(
                phd=phd,
                power_source=power_source,
                landing_system=landing_system,
                num_steps=n,
                airship_type=airship_type,
                enable_pressure_control=pressure_control,
            ),
            promotes_inputs=mission_inputs,
            promotes_outputs=mission_outputs,
        )

        # ==============================================================
        # Propulsion
        # ==============================================================

        propulsion_inputs = [
            "n_engine",
            "thrust_cruise",
            ("tas", "mission_speed_used"),
            "propeller_efficiency",
            "gearbox_efficiency",
            "thrust_vector_angle",
            "installed_shaft_power",
        ]

        if power_source == "turboelectric":
            propulsion_inputs += [
                "thrust_to",
                "n_propulsor",
                "motor_efficiency",
                "inverter_efficiency",
                "generator_efficiency",
                "turboshaft_thermal_efficiency",
                "turboshaft_specific_power",
                "generator_specific_power",
                "motor_specific_power",
                ("fuel_lhv", "gasoline_lhv"),
            ]
            self.add_subsystem(
                "propulsion",
                Turboelectric(
                    phd=phd,
                    num_steps=n,
                ),
                promotes_inputs=propulsion_inputs,
                promotes_outputs=[
                    "required_power",
                    "shaft_power",
                    "fuel_flow",
                    "avg_efficiency",
                    "takeoff_shaft_power",
                    "rated_shaft_power",
                    "rated_shaft_power_per_unit",
                    "rated_electrical_power",
                    "rated_core_power",
                    "required_rated_shaft_power",
                    "power_shortfall",
                    "propulsion_mass",
                    "power_system_mass",
                    "power_system_volume",
                    "core_mass",
                    "generator_mass",
                    "inverter_mass",
                    "motor_mass",
                    "prime_mover_mass",
                    "nacelle_mass",
                    "propeller_mass",
                    "pylon_mass",
                    "wiring_mass",
                    "fuel_system_mass",
                    "propeller_diameter",
                ],
            )

        elif power_source == "turboprop":
            propulsion_inputs += [
                "thrust_to",
                "turboshaft_thermal_efficiency",
                "turboshaft_specific_power",
                ("fuel_lhv", "gasoline_lhv"),
            ]
            self.add_subsystem(
                "propulsion",
                Turboprop(
                    phd=phd,
                    num_steps=n,
                ),
                promotes_inputs=propulsion_inputs,
                promotes_outputs=[
                    "required_power",
                    "shaft_power",
                    "fuel_flow",
                    "avg_efficiency",
                    "takeoff_shaft_power",
                    "rated_shaft_power",
                    "rated_shaft_power_per_unit",
                    "rated_core_power",
                    "required_rated_shaft_power",
                    "power_shortfall",
                    "propulsion_mass",
                    "power_system_mass",
                    "power_system_volume",
                    "core_mass",
                    "motor_mass",
                    "prime_mover_mass",
                    "nacelle_mass",
                    "propeller_mass",
                    "pylon_mass",
                    "fuel_system_mass",
                    "propeller_diameter",
                ],
            )

        else:
            propulsion_inputs += [
                "ice_specific_power",
                "motor_specific_power",
                "propeller_rps",
                "propeller_blade_count",
                "propeller_power_coefficient",
            ]

            if landing_system == "acls":
                propulsion_inputs.append("acls_area")

            self.add_subsystem(
                "propulsion",
                Propulsion(
                    phd=phd,
                    num_steps=n,
                    engine_type=engine_type,
                    landing_system=landing_system,
                    airship_type=airship_type,

                    installation_mass_method=self.options[
                        "propulsion_installation_mass_method"
                    ],

                    prime_mover_mass_method=self.options[
                        "propulsion_prime_mover_mass_method"
                    ],

                    prime_mover_mass_override=self.options[
                        "propulsion_prime_mover_mass_override"
                    ],
                ),
                promotes_inputs=propulsion_inputs,
                promotes_outputs=[
                    ("total_mass", "propulsion_mass"),
                    "required_power",
                    "shaft_power",
                    "brake_power",
                    "takeoff_shaft_power",
                    "rated_shaft_power",
                    "rated_brake_power",
                    "rated_shaft_power_per_unit",
                    "rated_brake_power_per_unit",
                    "motor_mass",
                    "prime_mover_mass",
                    "nacelle_mass",
                    "propeller_mass",
                    "mount_mass",
                    "pylon_mass",
                    "propeller_diameter",
                    "propeller_speed_power_coefficient",
                    "propeller_advance_ratio",
                    "propeller_efficiency_estimated",
                    "propeller_tip_speed",
                    "propeller_tip_speed_violation",
                ],
            )

            self.connect(
                "required_shaft_power",
                "propulsion.mission_shaft_power_required",
            )

            self.connect(
                "maximum_speed",
                "propulsion.propeller_design_speed",
            )

            self.connect(
                "atmosphere.takeoff.rho",
                "propulsion.propeller_design_density",
            )

        # ==============================================================
        # Architecture-dependent power and energy systems
        # ==============================================================

        common_power_inputs = [
            "n_engine",
            "thrust_vector_angle",
            "gearbox_efficiency",
            "motor_efficiency",
            "inverter_efficiency",
            "ice_thermal_efficiency",
            "fuel_cell_efficiency",
            "gasoline_lhv",
            "hydrogen_lhv",
            "generator_specific_power",
            "generator_efficiency",
            "ice_specific_power",
            "fuel_cell_specific_power",
            "fuel_cell_bop_mass",
            "solar_efficiency",
            "pv_areal_density",
        ]

        if landing_system == "acls":
            common_power_inputs.append("acls_area")

        # --------------------------------------------------------------
        # A. Standalone conventional and hydrogen fuel architectures
        # --------------------------------------------------------------

        if power_source in TURBINE_SOURCES:
            # Turboprop and turboelectric are self-contained fuel-to-thrust
            # architectures. They replace the normal Propulsion + Power pair.
            self.connect(
                "power_system_mass",
                "weight.power_system_mass",
            )
            self.connect(
                "power_system_volume",
                "weight.power_system_volume",
            )

            self.add_subsystem(
                "fuel_sizer",
                ConsumableMassSizer(num_steps=n),
                promotes_inputs=[
                    "fuel_reserve_fraction",
                    ("fuel_lhv", "gasoline_lhv"),
                ],
                promotes_outputs=[
                    "consumable_mass_used",
                    "consumable_reserve_mass",
                    "required_consumable_mass",
                    "usable_primary_energy",
                ],
            )

            self.connect(
                "fuel_flow",
                "fuel_sizer.fuel_flow",
            )
            self.connect(
                "mission_duration",
                "fuel_sizer.mission_duration",
            )
            self.connect(
                "avg_efficiency",
                "fuel_sizer.conversion_efficiency",
            )

            if self.options["use_prescribed_consumable_capacity"]:
                self.connect(
                    "installed_consumable_capacity",
                    "performance.installed_consumable_mass",
                )
                self.connect(
                    "installed_consumable_capacity",
                    "weight.consumable_mass",
                )
            else:
                self.connect(
                    "required_consumable_mass",
                    "performance.installed_consumable_mass",
                )
                self.connect(
                    "required_consumable_mass",
                    "weight.consumable_mass",
                )

            self.connect(
                "required_consumable_mass",
                "performance.required_consumable_mass",
            )
            self.connect(
                "consumable_mass_used",
                "performance.consumable_mass_used",
            )
            self.connect(
                "usable_primary_energy",
                "performance.installed_primary_usable_energy",
            )

        elif power_source in FUEL_SOURCES:
            self.add_subsystem(
                "power",
                Power(
                    phd=phd,
                    num_steps=n,
                    power_source=power_source,
                    landing_system=landing_system,
                    enable_pressure_control=pressure_control,
                ),
                promotes_inputs=common_power_inputs,
                promotes_outputs=[
                    "power_system_mass",
                    "power_system_volume",
                    "fuel_flow",
                    "P_elec_total",
                    "P_ice_demand",
                    "P_fc_demand",
                    "P_bat_demand",
                    "generator_mass",
                    "fuel_system_mass",
                    "fuel_cell_stack_mass",
                    "avg_efficiency",
                ],
            )

            self.connect(
                "shaft_power",
                "power.shaft_power",
            )
            self.connect(
                "rated_shaft_power",
                "power.rated_shaft_power",
            )
            self.connect(
                "mission_duration",
                "power.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.pamb",
                "power.pamb",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "power.tamb",
            )

            if pressure_control:
                self.connect(
                    "pressure_control_power",
                    "power.pressure_control_power",
                )

            self.connect(
                "power_system_mass",
                "weight.power_system_mass",
            )
            self.connect(
                "power_system_volume",
                "weight.power_system_volume",
            )

            if power_source == "conventional_reciprocating":
                self.add_subsystem(
                    "fuel_sizer",
                    ConsumableMassSizer(num_steps=n),
                    promotes_inputs=[
                        "fuel_reserve_fraction",
                        ("fuel_lhv", "gasoline_lhv"),
                        (
                            "conversion_efficiency",
                            "ice_thermal_efficiency",
                        ),
                    ],
                    promotes_outputs=[
                        "consumable_mass_used",
                        "consumable_reserve_mass",
                        "required_consumable_mass",
                        "usable_primary_energy",
                    ],
                )

                if self.options["use_prescribed_consumable_capacity"]:

                    self.connect(
                        "installed_consumable_capacity",
                        "performance.installed_consumable_mass",
                    )

                    self.connect(
                        "installed_consumable_capacity",
                        "weight.consumable_mass",
                    )

                else:

                    self.connect(
                        "required_consumable_mass",
                        "performance.installed_consumable_mass",
                    )

                    self.connect(
                        "required_consumable_mass",
                        "weight.consumable_mass",
                    )

                self.connect(
                    "fuel_flow",
                    "fuel_sizer.fuel_flow",
                )
                self.connect(
                    "mission_duration",
                    "fuel_sizer.mission_duration",
                )

                # Required mission fuel always feeds the mission requirement.
                # Installed fuel capacity is selected above: either prescribed
                # or equal to the calculated requirement.
                self.connect(
                    "required_consumable_mass",
                    "performance.required_consumable_mass",
                )
                self.connect(
                    "consumable_mass_used",
                    "performance.consumable_mass_used",
                )
                self.connect(
                    "usable_primary_energy",
                    "performance.installed_primary_usable_energy",
                )

            else:
                # Hydrogen reciprocating and hydrogen fuel cell.
                tank_inputs = [
                    "fuel_reserve_fraction",
                    "fuel_onboard_mass",
                    "tank_pressure",
                    "hydrogen_storage_density",
                    "tank_gravimetric_efficiency",
                    "tank_volume_mass_density",
                    "delivery_mass_fraction",
                    "insulation_thickness",
                    "insulation_density",
                    "hydrogen_lhv",
                ]

                self.add_subsystem(
                    "tank",
                    Tank(
                        phd=phd,
                        num_steps=n,
                        landing_system=landing_system,
                    ),
                    promotes_inputs=tank_inputs,
                    promotes_outputs=[
                        "hydrogen_mass_used",
                        "hydrogen_reserve_mass",
                        "hydrogen_mass",
                        "tank_mass",
                        "tank_volume",
                        "tank_volume_outer",
                        "structural_mass",
                        "insulation_mass",
                        "delivery_mass",
                        "volume_penalty_mass",
                        "nominal_tank_empty_mass",
                        "achieved_tank_gravimetric_efficiency",
                        "hydrogen_energy_content",
                        "usable_primary_energy",
                    ],
                )

                self.connect(
                    "fuel_flow",
                    "tank.fuel_flow",
                )
                self.connect(
                    "mission_duration",
                    "tank.mission_duration",
                )

                if power_source == "hydrogen_reciprocating":
                    self.connect(
                        "ice_thermal_efficiency",
                        "tank.fuel_cell_efficiency",
                    )
                else:
                    self.connect(
                        "fuel_cell_efficiency",
                        "tank.fuel_cell_efficiency",
                    )

                self.connect(
                    "hydrogen_mass",
                    "weight.consumable_mass",
                )
                self.connect(
                    "tank_mass",
                    "weight.tank_mass",
                )
                self.connect(
                    "tank_volume_outer",
                    "weight.tank_installed_volume",
                )

                self.connect(
                    "hydrogen_mass",
                    "performance.required_consumable_mass",
                )
                self.connect(
                    "hydrogen_mass",
                    "performance.installed_consumable_mass",
                )
                self.connect(
                    "hydrogen_mass_used",
                    "performance.consumable_mass_used",
                )
                self.connect(
                    "usable_primary_energy",
                    "performance.installed_primary_usable_energy",
                )

            if power_source == "hydrogen_fuel_cell":
                self._add_fuel_cell_polarization(
                    n=n,
                    connect_to_mission=True,
                )

        # --------------------------------------------------------------
        # B. Battery-only
        # --------------------------------------------------------------

        elif power_source == "battery_only":
            self.add_subsystem(
                "power",
                Power(
                    phd=phd,
                    num_steps=n,
                    power_source=power_source,
                    landing_system=landing_system,
                    enable_pressure_control=pressure_control,
                ),
                promotes_inputs=common_power_inputs,
                promotes_outputs=[
                    "P_elec_total",
                    "P_bat_demand",
                    "avg_efficiency",
                ],
            )

            self.connect(
                "shaft_power",
                "power.shaft_power",
            )
            self.connect(
                "rated_shaft_power",
                "power.rated_shaft_power",
            )
            self.connect(
                "mission_duration",
                "power.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.pamb",
                "power.pamb",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "power.tamb",
            )

            if pressure_control:
                self.connect(
                    "pressure_control_power",
                    "power.pressure_control_power",
                )

            self.add_subsystem(
                "battery",
                BatteryOnly(
                    phd=phd,
                    num_steps=n,
                    landing_system=landing_system,
                ),
                promotes_inputs=[
                    "battery_specific_energy",
                    "battery_volumetric_ed",
                    "battery_pack_voltage",
                    "battery_cell_voltage_nom",
                    "depth_of_discharge",
                    "battery_efficiency",
                    "battery_packaging_factor",
                ],
                promotes_outputs=[
                    "battery_capacity",
                    "battery_mass",
                    "battery_volume",
                    "power_system_mass",
                    "power_system_volume",
                    "mission_electrical_energy",
                    "usable_battery_energy",
                    "temperature_factor",
                    "peak_battery_power",
                    "pack_specific_energy",
                    "pack_volumetric_energy_density",
                ],
            )

            self.connect(
                "P_bat_demand",
                "battery.output_power",
            )
            self.connect(
                "mission_duration",
                "battery.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "battery.tamb",
            )

            self.connect(
                "power_system_mass",
                "weight.power_system_mass",
            )
            self.connect(
                "power_system_volume",
                "weight.power_system_volume",
            )

            self.connect(
                "battery_mass",
                "performance.required_battery_mass",
            )
            self.connect(
                "battery_mass",
                "performance.installed_battery_mass",
            )
            self.connect(
                "usable_battery_energy",
                "performance.installed_battery_usable_energy",
            )

        # --------------------------------------------------------------
        # C. Standalone solar-battery
        # --------------------------------------------------------------

        elif power_source == "solar_battery":
            solar_power_inputs = (
                common_power_inputs
                + [
                    "solar_area",
                    "solar_irradiance",
                ]
            )

            self.add_subsystem(
                "power",
                Power(
                    phd=phd,
                    num_steps=n,
                    power_source=power_source,
                    landing_system=landing_system,
                    enable_pressure_control=pressure_control,
                ),
                promotes_inputs=solar_power_inputs,
                promotes_outputs=[
                    "P_elec_total",
                    "P_bat_demand",
                    "P_solar_available",
                    "P_solar_used",
                    "avg_efficiency",
                ],
            )

            self.connect(
                "shaft_power",
                "power.shaft_power",
            )
            self.connect(
                "rated_shaft_power",
                "power.rated_shaft_power",
            )
            self.connect(
                "mission_duration",
                "power.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.pamb",
                "power.pamb",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "power.tamb",
            )

            if pressure_control:
                self.connect(
                    "pressure_control_power",
                    "power.pressure_control_power",
                )

            self.add_subsystem(
                "solar_battery",
                SolarBattery(
                    phd=phd,
                    num_steps=n,
                    landing_system=landing_system,
                ),
                promotes_inputs=[
                    "solar_energy",
                    "solar_irradiance",
                    "solar_area",
                    "solar_efficiency",
                    "pv_temp_coeff_fracK",
                    "pv_reference_temperature",
                    "pv_areal_density",
                    "battery_efficiency",
                    "depth_of_discharge",
                    "battery_specific_energy",
                    "battery_volumetric_ed",
                    "battery_packaging_factor",
                ],
                promotes_outputs=[
                    "battery_capacity",
                    "battery_mass",
                    "battery_volume",
                    "pv_mass",
                    "pv_volume",
                    "power_system_mass",
                    "power_system_volume",
                    "mission_load_energy",
                    "solar_energy_generated",
                    "solar_energy_used",
                    "excess_solar_energy",
                    "net_battery_energy",
                    "usable_battery_energy",
                    "solar_fraction",
                    "average_pv_efficiency",
                    "battery_temperature_factor",
                    "pack_specific_energy",
                    "pack_volumetric_energy_density",
                    "pv_power_available",
                    "pv_power_used",
                    "battery_power_demand",
                ],
            )

            # SolarBattery receives full electrical-bus demand and internally
            # allocates direct solar and battery energy.
            self.connect(
                "P_elec_total",
                "solar_battery.output_power",
            )
            self.connect(
                "mission_duration",
                "solar_battery.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "solar_battery.tamb",
            )

            self.connect(
                "power_system_mass",
                "weight.power_system_mass",
            )
            self.connect(
                "power_system_volume",
                "weight.power_system_volume",
            )

            self.connect(
                "battery_mass",
                "performance.required_battery_mass",
            )
            self.connect(
                "battery_mass",
                "performance.installed_battery_mass",
            )
            self.connect(
                "usable_battery_energy",
                "performance.installed_battery_usable_energy",
            )
            self.connect(
                "solar_energy_used",
                "performance.solar_energy_recovered",
            )

        # --------------------------------------------------------------
        # D. Legacy solar-RFC
        # --------------------------------------------------------------

        elif power_source == "solar-RFC":
            solar_rfc_inputs = (
                common_power_inputs
                + [
                    "solar_area",
                    "solar_irradiance",
                ]
            )

            self.add_subsystem(
                "power",
                Power(
                    phd=phd,
                    num_steps=n,
                    power_source=power_source,
                    landing_system=landing_system,
                    enable_pressure_control=pressure_control,
                ),
                promotes_inputs=solar_rfc_inputs,
                promotes_outputs=[
                    "power_system_mass",
                    "power_system_volume",
                    "P_elec_total",
                    "P_bat_demand",
                    "P_solar_available",
                    "P_solar_used",
                    "solar_energy_generated",
                    "pv_mass",
                    "avg_efficiency",
                ],
            )

            self.connect(
                "shaft_power",
                "power.shaft_power",
            )
            self.connect(
                "rated_shaft_power",
                "power.rated_shaft_power",
            )
            self.connect(
                "mission_duration",
                "power.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.pamb",
                "power.pamb",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "power.tamb",
            )

            if pressure_control:
                self.connect(
                    "pressure_control_power",
                    "power.pressure_control_power",
                )

            self.connect(
                "power_system_mass",
                "weight.power_system_mass",
            )
            self.connect(
                "power_system_volume",
                "weight.power_system_volume",
            )

            # Legacy compatibility: the RFC storage-system mass is used as
            # both required and installed storage mass so the mission
            # capacity constraint remains closed.
            self.connect(
                "power_system_mass",
                "performance.required_battery_mass",
            )
            self.connect(
                "power_system_mass",
                "performance.installed_battery_mass",
            )

            self.add_subsystem(
                "solar_used_integrator",
                EnergyIntegrator(num_steps=n),
                promotes_outputs=[
                    (
                        "energy",
                        "solar_energy_used",
                    )
                ],
            )
            self.connect(
                "P_solar_used",
                "solar_used_integrator.power",
            )
            self.connect(
                "mission_duration",
                "solar_used_integrator.duration",
            )
            self.connect(
                "solar_energy_used",
                "performance.solar_energy_recovered",
            )

        # --------------------------------------------------------------
        # E. Hybrid architectures
        # --------------------------------------------------------------

        elif power_source in HYBRID_SOURCES:
            hybrid_power_inputs = (
                common_power_inputs
                + ["tau"]
            )

            if power_source in SOLAR_HYBRIDS:
                hybrid_power_inputs += [
                    "solar_area",
                    "solar_irradiance",
                ]

            self.add_subsystem(
                "power",
                Power(
                    phd=phd,
                    num_steps=n,
                    power_source=power_source,
                    landing_system=landing_system,
                    enable_pressure_control=pressure_control,
                ),
                promotes_inputs=hybrid_power_inputs,
                promotes_outputs=[
                    (
                        "power_system_mass",
                        "primary_power_system_mass",
                    ),
                    (
                        "power_system_volume",
                        "primary_power_system_volume",
                    ),
                    "fuel_flow",
                    "P_elec_total",
                    "P_bat_demand",
                    "P_fc_demand",
                    "P_ice_demand",
                    "P_solar_available",
                    "P_solar_used",
                    "solar_energy_generated",
                    "generator_mass",
                    "fuel_system_mass",
                    "fuel_cell_stack_mass",
                    "hybrid_ice_core_mass",
                    "pv_mass",
                    "avg_efficiency",
                    "primary_power_fraction",
                    "battery_power_fraction_actual",
                    "solar_power_fraction_actual",
                ],
            )

            self.connect(
                "shaft_power",
                "power.shaft_power",
            )
            self.connect(
                "rated_shaft_power",
                "power.rated_shaft_power",
            )
            self.connect(
                "mission_duration",
                "power.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.pamb",
                "power.pamb",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "power.tamb",
            )

            if pressure_control:
                self.connect(
                    "pressure_control_power",
                    "power.pressure_control_power",
                )

            self.add_subsystem(
                "battery",
                BatteryOnly(
                    phd=phd,
                    num_steps=n,
                    landing_system=landing_system,
                ),
                promotes_inputs=[
                    "battery_specific_energy",
                    "battery_volumetric_ed",
                    "battery_pack_voltage",
                    "battery_cell_voltage_nom",
                    "depth_of_discharge",
                    "battery_efficiency",
                    "battery_packaging_factor",
                ],
                promotes_outputs=[
                    (
                        "battery_capacity",
                        "hybrid_battery_capacity",
                    ),
                    (
                        "battery_mass",
                        "hybrid_battery_mass",
                    ),
                    (
                        "battery_volume",
                        "hybrid_battery_volume",
                    ),
                    (
                        "power_system_mass",
                        "battery_power_system_mass",
                    ),
                    (
                        "power_system_volume",
                        "battery_power_system_volume",
                    ),
                    (
                        "mission_electrical_energy",
                        "hybrid_battery_mission_energy",
                    ),
                    (
                        "usable_battery_energy",
                        "hybrid_battery_usable_energy",
                    ),
                    (
                        "temperature_factor",
                        "hybrid_battery_temperature_factor",
                    ),
                ],
            )

            self.connect(
                "P_bat_demand",
                "battery.output_power",
            )
            self.connect(
                "mission_duration",
                "battery.mission_duration",
            )
            self.connect(
                "atmosphere.cruise.tamb",
                "battery.tamb",
            )

            self.connect(
                "hybrid_battery_mass",
                "performance.required_battery_mass",
            )
            self.connect(
                "hybrid_battery_mass",
                "performance.installed_battery_mass",
            )
            self.connect(
                "hybrid_battery_usable_energy",
                "performance.installed_battery_usable_energy",
            )

            self.add_subsystem(
                "hybrid_mass_sum",
                om.ExecComp(
                    "total_mass = primary_mass + battery_mass",
                    primary_mass={
                        "val": 0.0,
                        "units": "kg",
                    },
                    battery_mass={
                        "val": 0.0,
                        "units": "kg",
                    },
                    total_mass={
                        "val": 0.0,
                        "units": "kg",
                    },
                ),
                promotes_outputs=[
                    (
                        "total_mass",
                        "power_system_mass_total",
                    )
                ],
            )

            self.connect(
                "primary_power_system_mass",
                "hybrid_mass_sum.primary_mass",
            )
            self.connect(
                "battery_power_system_mass",
                "hybrid_mass_sum.battery_mass",
            )
            self.connect(
                "power_system_mass_total",
                "weight.power_system_mass",
            )

            self.add_subsystem(
                "hybrid_volume_sum",
                om.ExecComp(
                    "total_volume = primary_volume + battery_volume",
                    primary_volume={
                        "val": 0.0,
                        "units": "m**3",
                    },
                    battery_volume={
                        "val": 0.0,
                        "units": "m**3",
                    },
                    total_volume={
                        "val": 0.0,
                        "units": "m**3",
                    },
                ),
                promotes_outputs=[
                    (
                        "total_volume",
                        "power_system_volume_total",
                    )
                ],
            )

            self.connect(
                "primary_power_system_volume",
                "hybrid_volume_sum.primary_volume",
            )
            self.connect(
                "battery_power_system_volume",
                "hybrid_volume_sum.battery_volume",
            )
            self.connect(
                "power_system_volume_total",
                "weight.power_system_volume",
            )

            if power_source in HYDROGEN_HYBRIDS:
                self.add_subsystem(
                    "tank",
                    Tank(
                        phd=phd,
                        num_steps=n,
                        landing_system=landing_system,
                    ),
                    promotes_inputs=[
                        "fuel_reserve_fraction",
                        "fuel_onboard_mass",
                        "tank_pressure",
                        "hydrogen_storage_density",
                        "tank_gravimetric_efficiency",
                        "tank_volume_mass_density",
                        "delivery_mass_fraction",
                        "insulation_thickness",
                        "insulation_density",
                        "hydrogen_lhv",
                    ],
                    promotes_outputs=[
                        "hydrogen_mass_used",
                        "hydrogen_reserve_mass",
                        "hydrogen_mass",
                        "tank_mass",
                        "tank_volume",
                        "tank_volume_outer",
                        "structural_mass",
                        "insulation_mass",
                        "delivery_mass",
                        "volume_penalty_mass",
                        "nominal_tank_empty_mass",
                        "achieved_tank_gravimetric_efficiency",
                        "hydrogen_energy_content",
                        "usable_primary_energy",
                    ],
                )

                self.connect(
                    "fuel_flow",
                    "tank.fuel_flow",
                )
                self.connect(
                    "mission_duration",
                    "tank.mission_duration",
                )
                self.connect(
                    "fuel_cell_efficiency",
                    "tank.fuel_cell_efficiency",
                )

                self.connect(
                    "hydrogen_mass",
                    "weight.consumable_mass",
                )
                self.connect(
                    "tank_mass",
                    "weight.tank_mass",
                )
                self.connect(
                    "tank_volume_outer",
                    "weight.tank_installed_volume",
                )

                self.connect(
                    "hydrogen_mass",
                    "performance.required_consumable_mass",
                )
                self.connect(
                    "hydrogen_mass",
                    "performance.installed_consumable_mass",
                )
                self.connect(
                    "hydrogen_mass_used",
                    "performance.consumable_mass_used",
                )
                self.connect(
                    "usable_primary_energy",
                    "performance.installed_primary_usable_energy",
                )

                self._add_fuel_cell_polarization(
                    n=n,
                    connect_to_mission=True,
                )

            elif power_source in ICE_HYBRIDS:
                self.add_subsystem(
                    "fuel_sizer",
                    ConsumableMassSizer(num_steps=n),
                    promotes_inputs=[
                        "fuel_reserve_fraction",
                        ("fuel_lhv", "gasoline_lhv"),
                        (
                            "conversion_efficiency",
                            "ice_thermal_efficiency",
                        ),
                    ],
                    promotes_outputs=[
                        "consumable_mass_used",
                        "consumable_reserve_mass",
                        "required_consumable_mass",
                        "usable_primary_energy",
                    ],
                )

                self.connect(
                    "fuel_flow",
                    "fuel_sizer.fuel_flow",
                )
                self.connect(
                    "mission_duration",
                    "fuel_sizer.mission_duration",
                )

                self.connect(
                    "required_consumable_mass",
                    "weight.consumable_mass",
                )
                self.connect(
                    "required_consumable_mass",
                    "performance.required_consumable_mass",
                )
                self.connect(
                    "required_consumable_mass",
                    "performance.installed_consumable_mass",
                )
                self.connect(
                    "consumable_mass_used",
                    "performance.consumable_mass_used",
                )
                self.connect(
                    "usable_primary_energy",
                    "performance.installed_primary_usable_energy",
                )

            if power_source in SOLAR_HYBRIDS:
                self.add_subsystem(
                    "solar_used_integrator",
                    EnergyIntegrator(num_steps=n),
                    promotes_outputs=[
                        (
                            "energy",
                            "solar_energy_used",
                        )
                    ],
                )

                self.connect(
                    "P_solar_used",
                    "solar_used_integrator.power",
                )
                self.connect(
                    "mission_duration",
                    "solar_used_integrator.duration",
                )
                self.connect(
                    "solar_energy_used",
                    "performance.solar_energy_recovered",
                )

        # ==============================================================
        # Final weight update / closure audit
        # ==============================================================

        self.add_subsystem(
            "weight_update_closure",
            WeightClosureAudit(),
            promotes_outputs=[
                "weight_closure_residual",
                "weight_closure_relative",
                "closed_loop_mtow",
            ],
        )
        self.connect("mtow", "weight_update_closure.mtow")
        self.connect(
            "mass_balance_error",
            "weight_update_closure.mass_balance_error",
        )
        self.connect(
            "installed_consumable_mass",
            "weight_update_closure.installed_consumable_mass",
        )
        self.connect(
            "propulsion_mass",
            "weight_update_closure.propulsion_mass",
        )

        # Every supported architecture supplies a mass to weight.power_system_mass.
        # Connect the same promoted source to the closure audit for an explicit
        # XDSM information-flow edge.
        if power_source in HYBRID_SOURCES:
            self.connect(
                "power_system_mass_total",
                "weight_update_closure.power_system_mass",
            )
        else:
            self.connect(
                "power_system_mass",
                "weight_update_closure.power_system_mass",
            )

        # ==============================================================
        # Cross-disciplinary couplings
        # ==============================================================

        # --------------------------------------------------------------
        # Atmosphere -> Geometry / Weight
        # --------------------------------------------------------------
        # Geometry's ballonet calculation uses a common authoritative
        # atmosphere source at sea level and at the maximum pressure altitude.
        self.connect(
            "atmosphere.takeoff.rho",
            "geometry.rho_sea_level",
        )
        self.connect(
            "atmosphere.max_altitude.rho",
            "geometry.rho_max_altitude",
        )

        self.connect(
            "lifting_gas_volume_takeoff",
            "performance.lifting_gas_volume_takeoff",
        )

        # Weight evaluates helium at the same maximum pressure altitude used by
        # Geometry for ballonet sizing.
        self.connect(
            "max_operating_altitude",
            "weight.max_altitude",
        )

        # Chapter-9 gondola/tail WER design conditions are explicitly derived
        # from the prescribed mission-speed vector and cruise atmosphere.
        self.connect(
            "atmosphere.takeoff.rho",
            "weight_design_condition.rho_design",
        )
        # self.connect(
        #     "maximum_speed_for_weight",
        #     "weight.maximum_speed",
        # )

        self.connect(
            "maximum_speed",
            "weight.maximum_speed",
        )

        self.connect(
            "max_dynamic_pressure_for_weight",
            "weight.max_dynamic_pressure",
        )

        self.connect(
            "atmosphere.cruise.pamb",
            "performance.pamb_cruise",
        )
        self.connect(
            "atmosphere.cruise.tamb",
            "performance.tamb_cruise",
        )
        self.connect(
            "atmosphere.takeoff.pamb",
            "performance.pamb_to",
        )
        self.connect(
            "atmosphere.takeoff.tamb",
            "performance.tamb_to",
        )
        self.connect(
            "atmosphere.cruise.rho",
            "propulsion.rho",
        )

        # Installed propeller geometry from Propulsion feeds the universal
        # low-speed/takeoff thrust model in Performance.  Together with the
        # Performance -> Propulsion shaft-power connection above, this is an
        # intentional multidisciplinary sizing loop solved by NLBGS.
        self.connect(
            "propeller_diameter",
            "performance.propeller_diameter",
        )

        self.connect(
            "ref_area_AeroCoeffs",
            "performance.aerodynamic_reference_area",
        )
        self.connect(
            "ref_area_AeroCoeffs",
            "performance.planform_area",
        )
        self.connect(
            "aspect_ratio_geom",
            "performance.aspect_ratio",
        )
        self.connect(
            "fin_total_wetted_area",
            "performance.fin_area",
        )

        self.connect(
            "wetted_surface_area",
            "weight.aerodynamic_reference_area",
        )
        self.connect(
            "fin_total_wetted_area",
            "weight.fin_area",
        )
        self.connect(
            "propulsion_mass",
            "weight.propulsion_mass",
        )

        # ==============================================================
        # Solvers
        # ==============================================================

        self.nonlinear_solver = om.NonlinearBlockGS(
            maxiter=300,
            atol=1.0e-10,
            rtol=1.0e-10,
            use_aitken=True,
            aitken_min_factor=0.1,
            aitken_max_factor=1.5,
            iprint=2,
            err_on_non_converge=True,
        )
        self.linear_solver = om.DirectSolver()

    def _add_fuel_cell_polarization(
        self,
        n,
        connect_to_mission=True,
    ):
        """Add and connect the fuel-cell polarization model."""
        self.add_subsystem(
            "fc_polar",
            FuelCellPolarization(num_steps=n),
            promotes_inputs=[
                "n_fc_cells",
                "fc_active_area",
                "fc_temperature",
                "fc_hydrogen_partial_pressure",
                "fc_oxygen_partial_pressure",
                "fc_water_partial_pressure",
                "fc_exchange_current_density",
                "fc_limiting_current_density",
                "fc_parasitic_current_density",
                "fc_area_specific_resistance",
                "fc_transfer_coefficient",
            ],
            promotes_outputs=[
                "P_fc_available",
                "P_fc_max",
                "fc_power_shortfall",
                "fc_power_margin",
                "fc_power_limited",
                "fc_load_fraction",
                "fc_hydrogen_flow",
                "fc_voltage_efficiency",
            ],
        )

        self.connect(
            "P_fc_demand",
            "fc_polar.P_fc_demand",
        )
        self.connect(
            "fc_polar.eta_fc",
            "power.eta_fc_dynamic",
        )

        if connect_to_mission:
            self.connect(
                "fc_polar.eta_fc",
                "performance.eta_fc_dynamic",
            )