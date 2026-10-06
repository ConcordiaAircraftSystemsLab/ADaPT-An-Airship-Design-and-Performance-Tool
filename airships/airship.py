# -*- coding: utf-8 -*-
"""Common reference-airship data container for ADaPT."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AirshipDefinition:
    name: str
    description: str = ""
    reference_case: bool = True

    airship_type: str = "non-rigid"
    power_source: str = "conventional_reciprocating"
    landing_system: str = "conventional"

    payload_kg: float = 0.0
    range_km: float = 0.0
    cruise_altitude_m: float = 0.0
    cruise_speed_ms: float = 0.0
    cruise_disa_K: float = 0.0
    maximum_speed_ms: Optional[float] = None

    length_m: Optional[float] = None
    diameter_m: Optional[float] = None
    fineness_ratio: Optional[float] = None
    reference_volume_m3: Optional[float] = None

    n_crew: float = 1.0
    n_engine: float = 1.0
    installed_shaft_power_kW: Optional[float] = None
    installed_consumable_capacity_kg: Optional[float] = None
    ballast_mass_kg: float = 0.0

    propeller_efficiency: float = 0.75
    BR_takeoff: float = 0.90
    BR_landing: float = 0.90
    lift_coeff: float = 0.15
    drag_due_to_lift_factor: float = 0.869

    tail_volume_coeff_horizontal: Optional[float] = None
    tail_volume_coeff_vertical: Optional[float] = None

    ballonet_fraction_prescribed: Optional[float] = None
    ballonet_fill_fraction_takeoff: Optional[float] = None
    hull_volume_shape_factor: Optional[float] = None

    reference_values: Dict[str, Any] = field(default_factory=dict)
    model_options: Dict[str, Any] = field(default_factory=dict)
    extra_inputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def range_m(self) -> float:
        return 1000.0 * self.range_km

    @property
    def installed_shaft_power_W(self) -> Optional[float]:
        return None if self.installed_shaft_power_kW is None else 1000.0 * self.installed_shaft_power_kW
