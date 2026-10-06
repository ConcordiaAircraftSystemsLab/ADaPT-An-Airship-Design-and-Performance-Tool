# -*- coding: utf-8 -*-
"""
Airship independent-variable definitions for ADaPT.

Purpose
-------
Provides a single, explicit OpenMDAO source for the principal independent
variables used by the ADaPT multidisciplinary airship model.

The component groups independent variables into:

    1. Mission and operating-condition inputs
    2. Vehicle geometry and configuration inputs
    3. Aerodynamic and operational design inputs
    4. Propulsion and power-system technology assumptions
    5. Battery, solar, hydrogen-storage, and hybridization assumptions

The component contains no governing equations. Its outputs are connected to
the corresponding analysis components in AirshipAnalysisGroup.

The run, DOE, optimization, and technology-assessment scripts may modify these
outputs with ``Problem.set_val`` or register selected outputs as design
variables with ``model.add_design_var``.

Notes
-----
- ``num_steps`` controls the size of mission arrays.
- Component-level input defaults should remain as safe standalone fallbacks.
- ``set_input_defaults`` in AirshipAnalysisGroup should only be retained where
  promoted metadata, array shape, or architecture-specific ambiguity requires
  it.

@author: Musavir Bashir
"""

import numpy as np
import openmdao.api as om


class AirshipIndepVariables(om.IndepVarComp):
    """Central independent-variable component for the ADaPT framework."""

    def initialize(self):
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
            desc="Number of mission-analysis points.",
        )

    def setup(self):
        n = self.options["num_steps"]

        # ==============================================================
        # 1. Mission definition and operating conditions
        # ==============================================================

        self.add_output(
            "range",
            val=1_342_100.0,
            units="m",
            desc="Mission range.",
        )

        self.add_output(
            "maximum_speed",
            val=35.0,
            units="m/s",
        )

        self.add_output(
            "installed_shaft_power",
            val=134_000.0,
            units="W",
            desc=(
                "Selected total installed shaft-power rating used for "
                "mission feasibility and propulsion hardware sizing."
            ),
        )

        self.add_output(
            "cruise_speed",
            val=np.full(n, 31.0),
            units="m/s",
            desc="True airspeed during the cruise mission points.",
        )

        self.add_output(
            "cruise_altp",
            val=np.full(n, 914.0),
            units="m",
            desc="Cruise pressure altitude.",
        )

        self.add_output(
            "cruise_disa",
            val=np.zeros(n),
            units="K",
            desc="Cruise temperature deviation from ISA.",
        )

        self.add_output(
            "zero_alt",
            val=np.zeros(n),
            units="m",
            desc="Takeoff/reference pressure altitude.",
        )

        self.add_output(
            "zero_disa",
            val=np.zeros(n),
            units="K",
            desc="Takeoff/reference temperature deviation from ISA.",
        )

        self.add_output(
            "tailwind_speed",
            val=0.0,
            units="m/s",
            desc=(
                "Tailwind component used in the mission-duration calculation. "
                "Use a negative value for a headwind."
            ),
        )

        self.add_output(
            "takeoff_altitude",
            val=0.0,
            units="m",
            desc="Takeoff altitude for optional pressure-control analysis.",
        )

        self.add_output(
            "max_operating_altitude",
            val=3048.0,
            units="m",
            desc="Maximum operating altitude.",
        )



        self.add_output(
            "ascent_rate",
            val=1.0,
            units="m/s",
            desc="Representative ascent rate for pressure-control analysis.",
        )

        self.add_output(
            "descent_rate",
            val=1.0,
            units="m/s",
            desc="Representative descent rate for pressure-control analysis.",
        )

        self.add_output(
            "solar_irradiance",
            val=np.full(n, 600.0),
            units="W/m**2",
            desc="Incident solar irradiance over the mission points.",
        )

        self.add_output(
            "solar_energy",
            val=0.0,
            units="MJ",
            desc=(
                "Optional externally prescribed total solar energy. "
                "A value of zero uses irradiance-based integration."
            ),
        )

        # ==============================================================
        # 2. Vehicle geometry and configuration inputs
        # ==============================================================

        self.add_output(
            "length",
            val=53.6,
            units="m",
            desc="Overall airship length.",
        )

        self.add_output(
            "fineness_ratio",
            val=4.09,
            desc="Airship length divided by maximum hull diameter.",
        )

        self.add_output(
            "tail_volume_coeff_horizontal",
            val=0.066,
            desc="Horizontal-tail volume coefficient.",
        )

        self.add_output(
            "tail_volume_coeff_vertical",
            val=0.059,
            desc="Vertical-tail volume coefficient.",
        )

        self.add_output(
            "n_longitudinal_members",
            val=12.0,
            desc="Number of conceptual longitudinal structural members.",
        )

        self.add_output(
            "n_rings",
            val=16.0,
            desc="Number of conceptual circumferential rings or frames.",
        )

        self.add_output(
            "n_gas_cells",
            val=12.0,
            desc="Number of internal lifting-gas cells for rigid airships.",
        )

        self.add_output(
            "acls_area",
            val=377.0,
            units="m**2",
            desc="Air-cushion landing-system planform area.",
        )

        self.add_output(
            "solar_area",
            val=300.0,
            units="m**2",
            desc="Installed photovoltaic collector area.",
        )

        # --------------------------------------------------------------
        # Gondola geometry
        # --------------------------------------------------------------

        self.add_output(
            "gondola_length",
            val=13.1,
            units="m",
            desc="Gondola overall length used by the Chapter-9 gondola WER.",
        )

        self.add_output(
            "gondola_width",
            val=2.56,
            units="m",
            desc="Gondola overall width used by the Chapter-9 gondola WER.",
        )

        self.add_output(
            "gondola_height",
            val=2.29,
            units="m",
            desc="Gondola overall height used by the Chapter-9 gondola WER.",
        )

        self.add_output(
            "gondola_surface_area",
            val=0.0,
            units="m**2",
            desc=(
                "Optional gondola external surface area for Chapter-9 Category-3 "
                "weight estimation. Zero requests the internal box-area approximation."
            ),
        )

        # ==============================================================
        # 3. Payload, crew, and vehicle operating/design inputs
        # ==============================================================

        self.add_output(
            "payload",
            val=1123.0,
            units="kg",
            desc="Mission payload mass.",
        )

        self.add_output(
            "n_crew",
            val=1.0,
            desc="Number of crew members.",
        )

        self.add_output(
            "n_engine",
            val=2.0,
            desc="Number of propulsion units.",
        )

        self.add_output(
            "installed_consumable_capacity",
            val=599.0,
            units="kg",
            desc=(
                "Installed fuel or hydrogen capacity. Used independently from "
                "calculated mission consumable requirement."),
        )

        self.add_output(
            "ballast_mass",
            val=0.0,
            units="kg",
            desc="Installed ballast mass.",
        )

        self.add_output(
            "fuel_onboard_mass",
            val=599.0,
            units="kg",
            desc=(
                "simplified prescribed onboard fuel or hydrogen mass. "
                "closure is connected to AirshipWeight."
            ),
        )

        self.add_output(
            "lift_coeff",
            val=0.15,
            desc="Reference aerodynamic lift coefficient.",
        )

        self.add_output(
            "drag_due_to_lift_factor",
            val=0.869,
            desc="Induced-drag or drag-due-to-lift coefficient factor.",
        )

        self.add_output(
            "drag_coeff_zero",
            val=0.03542,
            desc="Zero-lift drag coefficient.",
        )

        self.add_output(
            "BR_takeoff",
            val=0.856,
            desc="Takeoff buoyancy ratio.",
        )

        self.add_output(
            "BR_landing",
            val=0.90,
            desc="Landing buoyancy ratio.",
        )

        self.add_output(
            "thrust_vector_angle",
            val=0.0,
            units="deg",
            desc="Propulsion thrust-vector angle.",
        )

        self.add_output(
            "rudder_deflection",
            val=28.0,
            units="deg",
            desc="Reference rudder deflection.",
        )

        self.add_output(
            "cruise_strategy",
            val=1.0,
            desc="Mission cruise-strategy selector used by AirshipMission.",
        )

        # ==============================================================
        # 4. Propeller and mechanical-transmission technology
        # ==============================================================

        self.add_output(
            "propeller_efficiency",
            val=0.75,
            desc="Propeller shaft-power-to-thrust efficiency.",
        )

        self.add_output(
            "gearbox_efficiency",
            val=0.98,
            desc="Mechanical gearbox efficiency.",
        )

        self.add_output(
            "propeller_rps",
            val=20.0,
            units="1/s",
            desc=(
                "Propeller rotational speed used for preliminary propeller "
                "sizing. Chapter-11 sample design uses 20 rps."
            ),
        )

        self.add_output(
            "propeller_blade_count",
            val=3.0,
            desc="Number of blades per propeller for Chapter-9 mass sizing.",
        )

        self.add_output(
            "propeller_power_coefficient",
            val=0.08,
            desc=(
                "Standard nondimensional propeller power coefficient Cp for "
                "the optional Chapter-5 Eq. (5.27) diameter method."
            ),
        )

        # ==============================================================
        # 5. Reciprocating-engine technology
        # ==============================================================

        self.add_output(
            "ice_specific_power",
            val=1200.0,
            units="W/kg",
            desc="Reciprocating-engine brake-power specific power.",
        )

        self.add_output(
            "ice_thermal_efficiency",
            val=0.30,
            desc="Reciprocating-engine chemical-to-brake efficiency.",
        )

        self.add_output(
            "gasoline_lhv",
            val=43.0e6,
            units="J/kg",
            desc="Lower heating value of conventional aviation fuel.",
        )

        self.add_output(
            "generator_specific_power",
            val=2000.0,
            units="W/kg",
            desc="Accessory generator specific power.",
        )

        self.add_output(
            "generator_efficiency",
            val=0.95,
            desc=(
                "Electrical generator efficiency for combustion hotel loads "
                "and the series conventional-battery hybrid."
            ),
        )

        # ==============================================================
        # 6. Electric motor and electrical-conversion technology
        # ==============================================================

        self.add_output(
            "motor_specific_power",
            val=5000.0,
            units="W/kg",
            desc="Electric-motor brake-power specific power.",
        )

        self.add_output(
            "motor_efficiency",
            val=0.95,
            desc="Electric-motor efficiency.",
        )

        self.add_output(
            "inverter_efficiency",
            val=0.98,
            desc="Power-inverter efficiency.",
        )

        # ==============================================================
        # 7. Fuel-cell technology
        # ==============================================================

        self.add_output(
            "fuel_cell_specific_power",
            val=700.0,
            units="W/kg",
            desc="Fuel-cell stack specific power.",
        )

        self.add_output(
            "fuel_cell_efficiency",
            val=0.55,
            desc="Fallback fuel-cell electrical efficiency.",
        )

        self.add_output(
            "fuel_cell_bop_mass",
            val=100.0,
            units="kg",
            desc="Fuel-cell balance-of-plant mass.",
        )

        self.add_output(
            "hydrogen_lhv",
            val=120.0e6,
            units="J/kg",
            desc="Lower heating value of hydrogen.",
        )

        self.add_output(
            "n_fc_cells",
            val=300.0,
            desc="Number of fuel-cell cells.",
        )

        self.add_output(
            "fc_active_area",
            val=300.0,
            units="cm**2",
            desc="Active area of one fuel-cell cell.",
        )

        self.add_output(
            "fc_temperature",
            val=333.15,
            units="K",
            desc="Fuel-cell operating temperature.",
        )

        self.add_output(
            "fc_hydrogen_partial_pressure",
            val=0.60,
            units="bar",
            desc="Hydrogen partial pressure at the fuel-cell anode.",
        )

        self.add_output(
            "fc_oxygen_partial_pressure",
            val=0.21,
            units="bar",
            desc="Oxygen partial pressure at the fuel-cell cathode.",
        )

        self.add_output(
            "fc_water_partial_pressure",
            val=1.0,
            units="bar",
            desc="Water-vapour partial pressure used in the Nernst model.",
        )

        self.add_output(
            "fc_exchange_current_density",
            val=3.0e-6,
            units="A/cm**2",
            desc="Fuel-cell exchange current density.",
        )

        self.add_output(
            "fc_limiting_current_density",
            val=1.60,
            units="A/cm**2",
            desc="Fuel-cell limiting current density.",
        )

        self.add_output(
            "fc_parasitic_current_density",
            val=0.002,
            units="A/cm**2",
            desc="Fuel-cell parasitic current-density loss.",
        )

        self.add_output(
            "fc_area_specific_resistance",
            val=0.10,
            units="ohm*cm**2",
            desc="Fuel-cell area-specific ohmic resistance.",
        )

        self.add_output(
            "fc_transfer_coefficient",
            val=1.0,
            desc="Fuel-cell charge-transfer coefficient.",
        )

        # ==============================================================
        # 8. Battery technology
        # ==============================================================

        self.add_output(
            "battery_specific_energy",
            val=250.0,
            units="W*h/kg",
            desc="Cell-level battery specific energy.",
        )

        self.add_output(
            "battery_volumetric_ed",
            val=600.0,
            units="W*h/L",
            desc="Cell-level battery volumetric energy density.",
        )

        self.add_output(
            "battery_pack_voltage",
            val=400.0,
            units="V",
            desc="Nominal battery-pack voltage.",
        )

        self.add_output(
            "battery_cell_voltage_nom",
            val=3.7,
            units="V",
            desc="Nominal cell voltage.",
        )

        self.add_output(
            "battery_efficiency",
            val=0.95,
            desc="Battery charge-discharge efficiency.",
        )

        self.add_output(
            "depth_of_discharge",
            val=0.80,
            desc="Allowable battery depth of discharge.",
        )

        self.add_output(
            "battery_packaging_factor",
            val=0.72,
            desc=(
                "Cell-to-pack mass and volume efficiency accounting for "
                "battery management, cooling, structure, and packaging."
            ),
        )


        # ==============================================================
        # 9. Solar photovoltaic technology
        # ==============================================================

        self.add_output(
            "solar_efficiency",
            val=0.22,
            desc="Reference photovoltaic conversion efficiency.",
        )

        self.add_output(
            "pv_temp_coeff_fracK",
            val=-0.003,
            units="1/K",
            desc="Fractional PV efficiency temperature coefficient.",
        )

        self.add_output(
            "pv_reference_temperature",
            val=298.15,
            units="K",
            desc="Reference temperature for photovoltaic efficiency.",
        )

        self.add_output(
            "pv_areal_density",
            val=0.50,
            units="kg/m**2",
            desc="Photovoltaic panel areal mass density.",
        )


        # ==============================================================
        # 10. Hydrogen-storage technology
        # ==============================================================

        self.add_output(
            "hydrogen_storage_density",
            val=70.8,
            units="kg/m**3",
            desc="Stored hydrogen density.",
        )

        self.add_output(
            "tank_pressure",
            val=1.0,
            units="bar",
            desc="Hydrogen tank operating pressure.",
        )

        self.add_output(
            "tank_gravimetric_efficiency",
            val=0.20,
            desc=(
                "Stored hydrogen mass divided by the combined hydrogen and "
                "empty tank-system mass."
            ),
        )

        self.add_output(
            "tank_volume_mass_density",
            val=15.0,
            units="kg/m**3",
            desc="Tank volume-dependent mass coefficient.",
        )

        self.add_output(
            "delivery_mass_fraction",
            val=0.08,
            desc=(
                "Hydrogen delivery-system mass divided by installed "
                "hydrogen mass."
            ),
        )

        self.add_output(
            "insulation_thickness",
            val=0.05,
            units="m",
            desc="Hydrogen tank insulation thickness.",
        )

        self.add_output(
            "insulation_density",
            val=50.0,
            units="kg/m**3",
            desc="Hydrogen tank insulation density.",
        )

        self.add_output(
            "fuel_reserve_fraction",
            val=0.10,
            desc="Required mission fuel or hydrogen reserve fraction.",
        )

        # ==============================================================
        # 11. Hybridization parameters
        # ==============================================================

        self.add_output(
            "tau",
            val=0.10,
            desc=(
                "Battery power fraction of the remaining hybrid demand "
                "after direct solar contribution."
            ),
        )

        self.add_output(
            "chi",
            val=0.10,
            desc="Battery energy hybridization fraction.",
        )


if __name__ == "__main__":
    # Standalone smoke test.
    problem = om.Problem()
    problem.model.add_subsystem(
        "indep",
        AirshipIndepVariables(num_steps=5),
        promotes=["*"],
    )
    problem.setup()
    problem.run_model()

    print("\n=== AirshipIndepVariables smoke test ===")
    print(f"Range                    : {problem.get_val('range')[0] / 1000.0:.1f} km")
    print(f"Cruise speed             : {problem.get_val('cruise_speed')[0]:.1f} m/s")
    print(f"Length                   : {problem.get_val('length')[0]:.1f} m")
    print(f"Battery specific energy  : "
          f"{problem.get_val('battery_specific_energy')[0]:.1f} Wh/kg")
    print(f"Fuel-cell specific power : "
          f"{problem.get_val('fuel_cell_specific_power')[0]:.1f} W/kg")