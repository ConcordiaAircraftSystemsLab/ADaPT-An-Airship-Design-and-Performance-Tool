# -*- coding: utf-8 -*-
"""
SolarBattery Component for ADaPT
================================

Purpose
-------
Sizes the integrated photovoltaic and battery energy-storage system for
solar-assisted electric airship architectures.

The component receives an electrical power-demand history and determines:

    - total mission electrical load,
    - photovoltaic power and energy generation,
    - net electrical energy assigned to the battery,
    - required battery capacity,
    - battery mass and volume,
    - photovoltaic panel mass and volume,
    - total installed PV-battery system mass and volume,
    - usable installed battery energy,
    - solar contribution diagnostics.

Responsibility boundary
-----------------------
This component is the authoritative owner of:

    - battery capacity for solar-battery architectures,
    - battery mass and volume,
    - PV panel mass and volume,
    - total installed PV-battery system mass and volume,
    - mission solar-energy generation.

It does not calculate:

    - aerodynamic or shaft-power demand,
    - fuel or hydrogen mass,
    - fuel-cell mass,
    - MTOW.

Those quantities are owned by the mission, power, tank, and weight components.

Sizing convention
-----------------
Mission load energy:

    E_load = integral(P_load dt)

Solar generation:

    P_pv = irradiance * area * eta_pv(T)

    E_solar = integral(P_pv dt)

Net battery-delivered energy:

    E_battery_delivered = max(E_load - E_solar_used, 0)

Required installed battery capacity:

    E_capacity =
        E_battery_delivered
        / (eta_battery * DoD * battery_temperature_factor)

Battery pack mass and volume:

    battery_mass =
        E_capacity
        / battery_specific_energy
        / battery_packaging_factor

    battery_volume =
        E_capacity
        / battery_volumetric_energy_density
        / battery_packaging_factor

PV system mass:

    pv_mass = solar_area * panel_mass_per_area

The output ``usable_battery_energy`` is the deliverable mission energy from
the installed pack after efficiency, depth-of-discharge, and temperature
effects.

Solar-energy accounting
-----------------------
``solar_energy_generated`` reports total generated solar energy.

``solar_energy_used`` reports the portion that can directly offset mission
electrical demand. Excess generation is reported separately and does not
reduce battery capacity below zero.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


class SolarBattery(om.ExplicitComponent):
    """Integrated photovoltaic and battery sizing component."""

    def initialize(self):
        self.options.declare(
            "phd",
            types=object,
            default=None,
            allow_none=True,
        )
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
        )

        self.options.declare(
            "minimum_battery_capacity",
            default=10.0,
            types=float,
            desc="Numerical minimum battery capacity in Wh.",
        )
        self.options.declare(
            "minimum_temperature_factor",
            default=0.60,
            types=float,
        )
        self.options.declare(
            "battery_reference_temperature",
            default=298.15,
            types=float,
        )
        self.options.declare(
            "battery_temperature_derating_per_K",
            default=0.003,
            types=float,
        )
        self.options.declare(
            "pv_panel_thickness",
            default=0.001,
            types=float,
            desc="Conceptual PV panel thickness in m.",
        )

    def setup(self):
        n = self.options["num_steps"]

        # ==============================================================
        # Mission and environment inputs
        # ==============================================================

        self.add_input(
            "output_power",
            val=np.full(n, 30_315.0),
            units="W",
            desc="Electrical load power history.",
        )
        self.add_input(
            "mission_duration",
            val=36_000.0,
            units="s",
        )
        self.add_input(
            "tamb",
            val=np.full(n, 298.15),
            units="K",
            desc="Ambient temperature history.",
        )

        # ==============================================================
        # Solar inputs from AirshipIndepVariables
        # ==============================================================

        self.add_input(
            "solar_energy",
            val=0.0,
            units="MJ",
            desc=(
                "Optional externally supplied total solar energy. "
                "If greater than zero, it overrides irradiance integration."
            ),
        )
        self.add_input(
            "solar_irradiance",
            val=np.full(n, 600.0),
            units="W/m**2",
        )
        self.add_input(
            "solar_area",
            val=20.0,
            units="m**2",
        )
        self.add_input(
            "solar_efficiency",
            val=0.22,
            desc="Reference photovoltaic conversion efficiency.",
        )
        self.add_input(
            "pv_temp_coeff_fracK",
            val=-0.003,
            units="1/K",
            desc="Fractional PV efficiency temperature coefficient.",
        )
        self.add_input(
            "pv_reference_temperature",
            val=298.15,
            units="K",
        )
        self.add_input(
            "pv_areal_density",
            val=0.50,
            units="kg/m**2",
            desc="Photovoltaic panel areal mass density.",
        )

        # ==============================================================
        # Battery technology inputs from AirshipIndepVariables
        # ==============================================================

        self.add_input(
            "battery_efficiency",
            val=0.95,
        )
        self.add_input(
            "depth_of_discharge",
            val=0.80,
        )
        self.add_input(
            "battery_specific_energy",
            val=250.0,
            units="W*h/kg",
        )
        self.add_input(
            "battery_volumetric_ed",
            val=600.0,
            units="W*h/L",
        )
        self.add_input(
            "battery_packaging_factor",
            val=0.72,
            desc=(
                "Cell-to-pack mass and volume efficiency accounting for "
                "BMS, cooling, structure, and packaging."
            ),
        )

        # ==============================================================
        # Core outputs
        # ==============================================================

        self.add_output(
            "battery_capacity",
            val=0.0,
            units="W*h",
            desc="Required installed battery capacity.",
        )
        self.add_output(
            "battery_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "battery_volume",
            val=0.0,
            units="m**3",
        )
        self.add_output(
            "pv_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "pv_volume",
            val=0.0,
            units="m**3",
        )
        self.add_output(
            "power_system_mass",
            val=0.0,
            units="kg",
            desc="Combined battery and photovoltaic system mass.",
        )
        self.add_output(
            "power_system_volume",
            val=0.0,
            units="m**3",
            desc="Combined battery and photovoltaic system volume.",
        )

        # ==============================================================
        # Energy and solar diagnostics
        # ==============================================================

        self.add_output(
            "mission_load_energy",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "mission_electrical_energy",
            val=0.0,
            units="W*h",
            desc="Compatibility alias equal to mission_load_energy.",
        )
        self.add_output(
            "solar_energy_generated",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "solar_energy_used",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "excess_solar_energy",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "net_battery_energy",
            val=0.0,
            units="W*h",
            desc="Energy that must be delivered by the battery.",
        )
        self.add_output(
            "usable_battery_energy",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "solar_fraction",
            val=0.0,
            desc="Fraction of mission electrical load offset by solar energy.",
        )
        self.add_output(
            "average_pv_efficiency",
            val=0.0,
        )
        self.add_output(
            "battery_temperature_factor",
            val=1.0,
        )
        self.add_output(
            "pack_specific_energy",
            val=0.0,
            units="W*h/kg",
        )
        self.add_output(
            "pack_volumetric_energy_density",
            val=0.0,
            units="W*h/L",
        )
        self.add_output(
            "energy_consumption",
            val=np.zeros(n),
            units="W",
            desc="Compatibility output equal to electrical load history.",
        )
        self.add_output(
            "pv_power_available",
            val=np.zeros(n),
            units="W",
        )
        self.add_output(
            "pv_power_used",
            val=np.zeros(n),
            units="W",
        )
        self.add_output(
            "battery_power_demand",
            val=np.zeros(n),
            units="W",
        )

        self.declare_partials("*", "*", method="fd", step=1e-8)

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

        power_load = self._vector(
            inputs["output_power"],
            n,
            minimum=0.0,
        )
        mission_duration = max(
            self._scalar(inputs["mission_duration"]),
            0.0,
        )
        tamb = self._vector(
            inputs["tamb"],
            n,
        )

        dt = mission_duration / max(n, 1)
        mission_load_energy_Wh = float(
            np.sum(power_load) * dt / 3600.0
        )

        # ==============================================================
        # Photovoltaic power and energy
        # ==============================================================

        solar_area = max(
            self._scalar(inputs["solar_area"]),
            0.0,
        )
        solar_efficiency_ref = float(
            np.clip(
                self._scalar(inputs["solar_efficiency"]),
                0.0,
                1.0,
            )
        )
        pv_temp_coeff = self._scalar(
            inputs["pv_temp_coeff_fracK"]
        )
        pv_reference_temperature = self._scalar(
            inputs["pv_reference_temperature"]
        )

        pv_efficiency = np.clip(
            solar_efficiency_ref
            * (
                1.0
                + pv_temp_coeff
                * (tamb - pv_reference_temperature)
            ),
            0.0,
            1.0,
        )

        irradiance = self._vector(
            inputs["solar_irradiance"],
            n,
            minimum=0.0,
        )
        pv_power_available = (
            irradiance
            * solar_area
            * pv_efficiency
        )

        external_solar_energy_MJ = max(
            self._scalar(inputs["solar_energy"]),
            0.0,
        )

        if external_solar_energy_MJ > 0.0:
            solar_energy_generated_Wh = (
                external_solar_energy_MJ
                * 1.0e6
                / 3600.0
            )

            if mission_duration > 0.0:
                equivalent_average_solar_power = (
                    solar_energy_generated_Wh
                    * 3600.0
                    / mission_duration
                )
                pv_power_available = np.full(
                    n,
                    equivalent_average_solar_power,
                )
            else:
                pv_power_available = np.zeros(n)

        else:
            solar_energy_generated_Wh = float(
                np.sum(pv_power_available)
                * dt
                / 3600.0
            )

        pv_power_used = np.minimum(
            pv_power_available,
            power_load,
        )
        battery_power_demand = np.maximum(
            power_load - pv_power_used,
            0.0,
        )

        solar_energy_used_Wh = float(
            np.sum(pv_power_used)
            * dt
            / 3600.0
        )

        solar_energy_used_Wh = min(
            solar_energy_used_Wh,
            mission_load_energy_Wh,
        )

        excess_solar_energy_Wh = max(
            solar_energy_generated_Wh
            - solar_energy_used_Wh,
            0.0,
        )

        battery_delivered_energy_Wh = max(
            mission_load_energy_Wh
            - solar_energy_used_Wh,
            0.0,
        )

        # ==============================================================
        # Battery sizing
        # ==============================================================

        battery_efficiency = float(
            np.clip(
                self._scalar(inputs["battery_efficiency"]),
                0.01,
                0.999,
            )
        )
        depth_of_discharge = float(
            np.clip(
                self._scalar(inputs["depth_of_discharge"]),
                0.01,
                0.99,
            )
        )
        battery_specific_energy = max(
            self._scalar(inputs["battery_specific_energy"]),
            1.0,
        )
        battery_volumetric_ed = max(
            self._scalar(inputs["battery_volumetric_ed"]),
            1.0,
        )
        packaging_factor = float(
            np.clip(
                self._scalar(inputs["battery_packaging_factor"]),
                0.10,
                1.0,
            )
        )

        average_temperature = float(np.mean(tamb))
        temperature_deviation = abs(
            average_temperature
            - float(
                self.options[
                    "battery_reference_temperature"
                ]
            )
        )

        battery_temperature_factor = float(
            np.clip(
                1.0
                - float(
                    self.options[
                        "battery_temperature_derating_per_K"
                    ]
                )
                * temperature_deviation,
                float(
                    self.options[
                        "minimum_temperature_factor"
                    ]
                ),
                1.0,
            )
        )

        usable_fraction = max(
            battery_efficiency
            * depth_of_discharge
            * battery_temperature_factor,
            1.0e-9,
        )

        required_capacity_Wh = max(
            battery_delivered_energy_Wh
            / usable_fraction,
            float(
                self.options[
                    "minimum_battery_capacity"
                ]
            ),
        )

        pack_specific_energy = (
            battery_specific_energy
            * packaging_factor
        )
        pack_volumetric_energy_density = (
            battery_volumetric_ed
            * packaging_factor
        )

        battery_mass = (
            required_capacity_Wh
            / max(pack_specific_energy, 1.0e-9)
        )

        battery_volume_L = (
            required_capacity_Wh
            / max(
                pack_volumetric_energy_density,
                1.0e-9,
            )
        )
        battery_volume_m3 = battery_volume_L / 1000.0

        usable_battery_energy_Wh = (
            required_capacity_Wh
            * usable_fraction
        )

        # ==============================================================
        # PV mass and volume
        # ==============================================================

        pv_areal_density = max(
            self._scalar(inputs["pv_areal_density"]),
            0.0,
        )
        pv_mass = (
            solar_area
            * pv_areal_density
        )
        pv_volume = (
            solar_area
            * max(
                float(
                    self.options[
                        "pv_panel_thickness"
                    ]
                ),
                0.0,
            )
        )

        total_mass = battery_mass + pv_mass
        total_volume = battery_volume_m3 + pv_volume

        solar_fraction = (
            solar_energy_used_Wh
            / max(mission_load_energy_Wh, 1.0e-9)
            if mission_load_energy_Wh > 0.0
            else 0.0
        )

        # ==============================================================
        # Outputs
        # ==============================================================

        outputs["battery_capacity"] = required_capacity_Wh
        outputs["battery_mass"] = battery_mass
        outputs["battery_volume"] = battery_volume_m3

        outputs["pv_mass"] = pv_mass
        outputs["pv_volume"] = pv_volume

        outputs["power_system_mass"] = total_mass
        outputs["power_system_volume"] = total_volume

        outputs["mission_load_energy"] = mission_load_energy_Wh
        outputs["mission_electrical_energy"] = (
            mission_load_energy_Wh
        )
        outputs["solar_energy_generated"] = (
            solar_energy_generated_Wh
        )
        outputs["solar_energy_used"] = (
            solar_energy_used_Wh
        )
        outputs["excess_solar_energy"] = (
            excess_solar_energy_Wh
        )
        outputs["net_battery_energy"] = (
            battery_delivered_energy_Wh
        )
        outputs["usable_battery_energy"] = (
            usable_battery_energy_Wh
        )
        outputs["solar_fraction"] = solar_fraction
        outputs["average_pv_efficiency"] = float(
            np.mean(pv_efficiency)
        )
        outputs["battery_temperature_factor"] = (
            battery_temperature_factor
        )
        outputs["pack_specific_energy"] = (
            pack_specific_energy
        )
        outputs[
            "pack_volumetric_energy_density"
        ] = pack_volumetric_energy_density

        outputs["energy_consumption"] = power_load
        outputs["pv_power_available"] = (
            pv_power_available
        )
        outputs["pv_power_used"] = pv_power_used
        outputs["battery_power_demand"] = (
            battery_power_demand
        )


if __name__ == "__main__":
    problem = om.Problem()
    problem.model.add_subsystem(
        "solar_battery",
        SolarBattery(num_steps=10),
        promotes=["*"],
    )
    problem.setup()

    problem.set_val(
        "output_power",
        np.full(10, 30_000.0),
        units="W",
    )
    problem.set_val(
        "mission_duration",
        18_000.0,
        units="s",
    )
    problem.set_val(
        "solar_area",
        300.0,
        units="m**2",
    )
    problem.set_val(
        "solar_irradiance",
        np.full(10, 600.0),
        units="W/m**2",
    )

    problem.run_model()

    print("\n=== SolarBattery smoke test ===")
    print(
        f"Mission load energy : "
        f"{problem.get_val('mission_load_energy')[0]:,.1f} Wh"
    )
    print(
        f"Solar energy used   : "
        f"{problem.get_val('solar_energy_used')[0]:,.1f} Wh"
    )
    print(
        f"Battery capacity    : "
        f"{problem.get_val('battery_capacity')[0]:,.1f} Wh"
    )
    print(
        f"Battery mass        : "
        f"{problem.get_val('battery_mass')[0]:,.1f} kg"
    )
    print(
        f"PV mass             : "
        f"{problem.get_val('pv_mass')[0]:,.1f} kg"
    )