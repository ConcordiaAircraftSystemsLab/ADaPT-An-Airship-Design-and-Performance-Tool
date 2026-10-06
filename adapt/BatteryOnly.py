# -*- coding: utf-8 -*-
"""
BatteryOnly Component for ADaPT
===============================

Purpose
-------
Sizes the battery energy-storage system for battery-electric and hybrid
airship architectures.

The component receives an electrical power-demand history and determines:

    - mission electrical energy demand,
    - required installed battery capacity,
    - battery pack mass and volume,
    - usable installed battery energy,
    - conceptual pack series/parallel configuration,
    - average effective battery efficiency.

Responsibility boundary
-----------------------
This component is the authoritative owner of battery capacity, battery mass,
battery volume, and usable installed battery energy.

It does not calculate:

    - aerodynamic or shaft-power demand,
    - fuel or hydrogen mass,
    - fuel-cell mass,
    - PV panel mass,
    - MTOW.

Those quantities are owned by the mission, power, solar, tank, and weight
components.

Sizing convention
-----------------
For a mission electrical-energy requirement E_load:

    E_capacity = E_load / (eta_battery * DoD * temperature_factor)

    battery_mass = E_capacity
                   / battery_specific_energy
                   / packaging_factor

    battery_volume = E_capacity
                     / battery_volumetric_energy_density
                     / packaging_factor

The output ``usable_battery_energy`` is the mission-deliverable energy:

    usable_battery_energy =
        battery_capacity
        * battery_efficiency
        * depth_of_discharge
        * temperature_factor

This quantity is intended for hybrid-energy consistency diagnostics in
AirshipMission.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


class BatteryOnly(om.ExplicitComponent):
    """Battery pack sizing from mission electrical power demand."""

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
            "cell_continuous_current",
            default=10.0,
            types=float,
            desc="Conceptual continuous current capability per parallel string in A.",
        )
        self.options.declare(
            "minimum_temperature_factor",
            default=0.60,
            types=float,
        )
        self.options.declare(
            "reference_temperature",
            default=298.15,
            types=float,
        )
        self.options.declare(
            "temperature_derating_per_K",
            default=0.003,
            types=float,
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
            desc="Electrical power demanded from the battery.",
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
            desc="Ambient temperature over the mission points.",
        )

        # ==============================================================
        # Battery technology inputs from AirshipIndepVariables
        # ==============================================================

        self.add_input(
            "battery_specific_energy",
            val=250.0,
            units="W*h/kg",
            desc="Cell-level gravimetric specific energy.",
        )
        self.add_input(
            "battery_volumetric_ed",
            val=600.0,
            units="W*h/L",
            desc="Cell-level volumetric energy density.",
        )
        self.add_input(
            "battery_pack_voltage",
            val=400.0,
            units="V",
        )
        self.add_input(
            "battery_cell_voltage_nom",
            val=3.7,
            units="V",
        )
        self.add_input(
            "depth_of_discharge",
            val=0.80,
        )
        self.add_input(
            "battery_efficiency",
            val=0.95,
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
            desc="Installed battery-pack mass.",
        )
        self.add_output(
            "battery_volume",
            val=0.0,
            units="m**3",
            desc="Installed battery-pack volume.",
        )
        self.add_output(
            "power_system_mass",
            val=0.0,
            units="kg",
            desc="Compatibility alias equal to battery_mass.",
        )
        self.add_output(
            "power_system_volume",
            val=0.0,
            units="m**3",
            desc="Compatibility alias equal to battery_volume.",
        )

        # ==============================================================
        # Energy and pack diagnostics
        # ==============================================================

        self.add_output(
            "mission_electrical_energy",
            val=0.0,
            units="W*h",
            desc="Electrical energy demanded over the mission.",
        )
        self.add_output(
            "usable_battery_energy",
            val=0.0,
            units="W*h",
            desc="Mission-deliverable energy from the installed pack.",
        )
        self.add_output(
            "energy_consumption",
            val=np.zeros(n),
            units="W",
            desc="Compatibility output equal to the battery power-demand history.",
        )
        self.add_output(
            "n_series",
            val=0.0,
        )
        self.add_output(
            "n_parallel",
            val=0.0,
        )
        self.add_output(
            "avg_efficiency",
            val=0.0,
        )
        self.add_output(
            "temperature_factor",
            val=1.0,
        )
        self.add_output(
            "peak_battery_power",
            val=0.0,
            units="W",
        )
        self.add_output(
            "pack_specific_energy",
            val=0.0,
            units="W*h/kg",
            desc="Effective pack-level specific energy.",
        )
        self.add_output(
            "pack_volumetric_energy_density",
            val=0.0,
            units="W*h/L",
            desc="Effective pack-level volumetric energy density.",
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

        power = self._vector(
            inputs["output_power"],
            n,
            minimum=0.0,
        )
        mission_duration = max(
            self._scalar(inputs["mission_duration"]),
            0.0,
        )
        temperature = self._vector(
            inputs["tamb"],
            n,
        )

        specific_energy = max(
            self._scalar(inputs["battery_specific_energy"]),
            1.0,
        )
        volumetric_energy_density = max(
            self._scalar(inputs["battery_volumetric_ed"]),
            1.0,
        )
        pack_voltage = max(
            self._scalar(inputs["battery_pack_voltage"]),
            1.0,
        )
        cell_voltage = max(
            self._scalar(inputs["battery_cell_voltage_nom"]),
            0.1,
        )
        depth_of_discharge = float(
            np.clip(
                self._scalar(inputs["depth_of_discharge"]),
                0.01,
                0.99,
            )
        )
        battery_efficiency = float(
            np.clip(
                self._scalar(inputs["battery_efficiency"]),
                0.01,
                0.999,
            )
        )
        packaging_factor = float(
            np.clip(
                self._scalar(inputs["battery_packaging_factor"]),
                0.10,
                1.0,
            )
        )

        average_temperature = float(np.mean(temperature))
        temperature_deviation = abs(
            average_temperature
            - float(self.options["reference_temperature"])
        )

        temperature_factor = float(
            np.clip(
                1.0
                - float(self.options["temperature_derating_per_K"])
                * temperature_deviation,
                float(self.options["minimum_temperature_factor"]),
                1.0,
            )
        )

        dt = mission_duration / max(n, 1)
        mission_energy_Wh = float(
            np.sum(power) * dt / 3600.0
        )

        usable_fraction = max(
            battery_efficiency
            * depth_of_discharge
            * temperature_factor,
            1.0e-9,
        )

        required_capacity_Wh = (
            mission_energy_Wh / usable_fraction
        )

        pack_specific_energy = (
            specific_energy * packaging_factor
        )
        pack_volumetric_energy_density = (
            volumetric_energy_density * packaging_factor
        )

        battery_mass = (
            required_capacity_Wh
            / max(pack_specific_energy, 1.0e-9)
        )

        battery_volume_L = (
            required_capacity_Wh
            / max(pack_volumetric_energy_density, 1.0e-9)
        )
        battery_volume_m3 = battery_volume_L / 1000.0

        usable_battery_energy = (
            required_capacity_Wh
            * usable_fraction
        )

        n_series = max(
            1.0,
            np.ceil(pack_voltage / cell_voltage),
        )

        peak_power = float(np.max(power))
        conservative_pack_voltage = 0.85 * pack_voltage
        peak_current = (
            peak_power / max(conservative_pack_voltage, 1.0e-9)
        )
        current_per_string = max(
            float(self.options["cell_continuous_current"]),
            1.0e-9,
        )
        n_parallel = max(
            1.0,
            np.ceil(peak_current / current_per_string),
        )

        outputs["battery_capacity"] = required_capacity_Wh
        outputs["battery_mass"] = battery_mass
        outputs["battery_volume"] = battery_volume_m3

        outputs["power_system_mass"] = battery_mass
        outputs["power_system_volume"] = battery_volume_m3

        outputs["mission_electrical_energy"] = mission_energy_Wh
        outputs["usable_battery_energy"] = usable_battery_energy
        outputs["energy_consumption"] = power

        outputs["n_series"] = n_series
        outputs["n_parallel"] = n_parallel
        outputs["avg_efficiency"] = (
            battery_efficiency * temperature_factor
        )
        outputs["temperature_factor"] = temperature_factor
        outputs["peak_battery_power"] = peak_power
        outputs["pack_specific_energy"] = pack_specific_energy
        outputs["pack_volumetric_energy_density"] = (
            pack_volumetric_energy_density
        )


if __name__ == "__main__":
    problem = om.Problem()
    problem.model.add_subsystem(
        "battery",
        BatteryOnly(num_steps=10),
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

    problem.run_model()

    print("\n=== BatteryOnly smoke test ===")
    print(
        f"Mission energy      : "
        f"{problem.get_val('mission_electrical_energy')[0]:,.1f} Wh"
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
        f"Battery volume      : "
        f"{problem.get_val('battery_volume')[0]:,.3f} m^3"
    )