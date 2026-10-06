# -*- coding: utf-8 -*-
"""Zeppelin NT 07-101 reference-airship definition used by ADaPT validation."""

from .airship import AirshipDefinition

REFERENCE_LENGTH_M = 75.0
REFERENCE_DIAMETER_M = 14.2

ZeppelinNT = AirshipDefinition(
    name="Zeppelin NT 07-101",
    description="Zeppelin NT 07-101 semi-rigid reference validation configuration",
    airship_type="semi-rigid",
    power_source="conventional_reciprocating",
    landing_system="conventional",

    payload_kg=800.0,
    range_km=1000.0,
    cruise_altitude_m=600.0,
    cruise_speed_ms=31.0,
    cruise_disa_K=0.0,
    maximum_speed_ms=125.0 / 3.6,

    length_m=REFERENCE_LENGTH_M,
    diameter_m=REFERENCE_DIAMETER_M,
    fineness_ratio=REFERENCE_LENGTH_M / REFERENCE_DIAMETER_M,
    reference_volume_m3=8425.0,

    n_crew=2.0,
    n_engine=3.0,
    installed_shaft_power_kW=441.0,
    installed_consumable_capacity_kg=1100.0,
    ballast_mass_kg=0.0,

    propeller_efficiency=0.75,
    BR_takeoff=0.95,
    BR_landing=0.95,
    lift_coeff=0.15,
    drag_due_to_lift_factor=0.869,

    hull_volume_shape_factor=1.0640,
    ballonet_fill_fraction_takeoff=0.340,
    ballonet_fraction_prescribed=0.26,

    model_options={
        "use_prescribed_consumable_capacity": True,
        "ballonet_sizing_method": "prescribed_fraction",
        "tail_coefficient_method": "historical",
        "propulsion_installation_mass_method": "structure_integrated",
        "weight_gondola_method": "book",
        "weight_gondola_category": 2,
        "weight_miscellaneous_fraction": 0.085,

        # Values consumed by the validation-specific Zeppelin weight subclass.
        "outer_envelope_areal_density": 1000.0 / 2668.39,
        "inner_envelope_areal_density": 0.0,
        "framework_mass_model": "v23",
        "k_framework_v23": 1100.0 / 414.05,
        "framework_mass_frac_cap": 1.0,
        "crew_mass_each": 113.0,
    },

    extra_inputs={
        "weight.gondola_length": {"value": 10.7, "units": "m"},
        "weight.gondola_width": {"value": 1.67, "units": "m"},
        "weight.gondola_height": {"value": 1.80, "units": "m"},
    },

    reference_values={
        "volume_m3": 8425.0,
        "mtow_kg": 8050.0,
        "useful_load_kg": 1900.0,
        "base_mass_kg": 6150.0,
        "secondary_published_empty_mass_kg": 6622.0,
        "fuel_kg": 1100.0,
    },
)

AIRSHIP = ZeppelinNT
