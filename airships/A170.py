# -*- coding: utf-8 -*-
"""A-170 reference-airship definition used by ADaPT validation."""

from .airship import AirshipDefinition

A170 = AirshipDefinition(
    name="A-170",
    description="A-170 reference validation configuration",
    airship_type="non-rigid",
    power_source="conventional_reciprocating",
    landing_system="conventional",

    payload_kg=1122.0,
    range_km=1342.1,
    cruise_altitude_m=914.4,
    cruise_speed_ms=19.57,
    cruise_disa_K=0.0,
    maximum_speed_ms=19.57,

    length_m=53.58,
    fineness_ratio=4.10,

    n_crew=1.0,
    n_engine=2.0,
    installed_shaft_power_kW=268.0,
    installed_consumable_capacity_kg=599.0,
    ballast_mass_kg=0.0,

    propeller_efficiency=0.75,
    BR_takeoff=0.816,
    BR_landing=0.90,
    lift_coeff=0.15,
    drag_due_to_lift_factor=0.869,

    tail_volume_coeff_horizontal=0.066,
    tail_volume_coeff_vertical=0.059,
    ballonet_fraction_prescribed=0.08,

    model_options={
        "use_prescribed_consumable_capacity": True,
        "ballonet_sizing_method": "prescribed_fraction",
        "propulsion_installation_mass_method": "generic",
        "weight_gondola_method": "override",
        "weight_gondola_mass_override": 1500.0,
        "weight_fuel_tank_method": "override",
        "weight_fuel_tank_mass_override": 42.0,
        "weight_pressure_system_method": "override",
        "weight_pressure_system_mass_override": 67.1,
        "weight_vms_method": "none",
        "weight_vms_mass_override": 0.0,
        "weight_miscellaneous_fraction": 75.0 / 3908.0,
    },

    reference_values={
        "mtow_kg": 5629.0,
        "owe_kg": 3908.0,
        "ground_roll_m": 432.0,
        "wetted_surface_area_m2": 1771.0,
        "gross_volume_m3": 4823.0,
        "ref_area_aerocoeffs_m2": 285.0,
        "weight_gross_area_m2": 1771.0,
        "envelope_mass_kg": 678.0,
        "gondola_mass_kg": 1500.0,
        "fin_mass_kg": 317.0,
        "tail_structural_mass_kg": 317.0,
        "landing_system_mass_kg": 94.0,
        "propulsion_mass_kg": 595.0,
        "power_system_mass_kg": 98.0,
        "fuel_tank_mass_kg": 42.0,
        "pressure_system_mass_kg": 67.1,
        "crew_mass_kg": 113.0,
        "miscellaneous_mass_kg": 75.0,
    },
)

AIRSHIP = A170
