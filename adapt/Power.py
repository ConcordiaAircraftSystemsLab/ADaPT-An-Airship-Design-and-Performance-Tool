# -*- coding: utf-8 -*-
"""
Power Component for ADaPT
=========================

Purpose
-------
Computes architecture-dependent power conversion, source-power allocation,
fuel flow, and conversion-equipment sizing for the ADaPT airship framework.

This component receives mechanical propeller shaft-power demand from
``Propulsion`` and converts it into the corresponding prime-source or
electrical-bus demand.  Mechanical propulsor hardware remains owned by
Propulsion; Power owns architecture-specific conversion/source equipment.

Responsibilities
----------------
- Receive mission shaft-power history and installed shaft-power rating from Propulsion.
- Convert shaft power to brake or electrical demand.
- Allocate hybrid power among solar, battery, fuel-cell, and ICE paths.
- Compute conventional-fuel or hydrogen flow.
- Size conversion equipment only:
    * ICE accessory generator and fuel-system allowance
    * Fuel-cell stack and balance of plant
    * PV panel mass for solar-hydrogen hybrid
- Expose battery power demand for external sizing.

Important mass-ownership rule
-----------------------------
Battery mass is NOT sized in this component.

Battery-only and solar-battery installed mass must be sized by:
    - BatteryOnly.py
    - SolarBattery.py

Hydrogen mass and tank mass must be sized by:
    - Tank.py

ICE or electric-motor core mass must be sized by:
    - Propulsion.py

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

Hybrid convention
-----------------
For hybrid architectures, ``tau`` is the battery power fraction after any
direct solar contribution:

    P_solar   = min(P_solar_available, P_elec_total)
    P_rem     = P_elec_total - P_solar
    P_battery = tau * P_rem
    P_primary = P_rem - P_battery

The primary source is:
    - fuel cell for hydrogen hybrids
    - reciprocating-engine/generator set for conventional battery hybrid

``conventional_battery_hybrid`` is treated as a SERIES hybrid.  Therefore
``P_ice_demand`` is the generator electrical contribution to the bus, while
fuel flow and ICE-core sizing account for generator efficiency.

Technology inputs
-----------------
Technology quantities are explicit OpenMDAO inputs so that they may be
provided by ``AirshipIndepVariables`` and varied during DOE, sensitivity,
optimization, and technology-assessment studies.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


HYBRID_ARCHITECTURES = {
    "hydrogen_hybrid": {
        "ice": False,
        "fuel_cell": True,
        "battery": True,
        "solar": False,
    },
    "solar_hydrogen_hybrid": {
        "ice": False,
        "fuel_cell": True,
        "battery": True,
        "solar": True,
    },
    "conventional_battery_hybrid": {
        "ice": True,
        "fuel_cell": False,
        "battery": True,
        "solar": False,
    },
}

LEGACY_POWER_SOURCES = [
    "conventional_reciprocating",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "battery_only",
    "solar_battery",
    "solar-RFC",
]

ALL_POWER_SOURCES = LEGACY_POWER_SOURCES + list(HYBRID_ARCHITECTURES.keys())


def is_hybrid_source(power_source: str) -> bool:
    """Return True when the architecture uses the general hybrid branch."""
    return power_source in HYBRID_ARCHITECTURES


def uses_fuel_cell(power_source: str) -> bool:
    """Return True when the architecture contains a fuel cell."""
    return (
        power_source == "hydrogen_fuel_cell"
        or (
            is_hybrid_source(power_source)
            and HYBRID_ARCHITECTURES[power_source]["fuel_cell"]
        )
    )


def uses_solar(power_source: str) -> bool:
    """Return True when the architecture contains direct solar generation."""
    return (
        power_source in ["solar_battery", "solar-RFC"]
        or (
            is_hybrid_source(power_source)
            and HYBRID_ARCHITECTURES[power_source]["solar"]
        )
    )


class Power(om.ExplicitComponent):
    """Architecture-dependent power-conversion and source-sizing component."""

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
            "power_source",
            default="conventional_reciprocating",
            values=ALL_POWER_SOURCES,
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
        )

        # Fixed model assumptions that are not currently technology variables.
        self.options.declare("aux_power", default=10_000.0, types=float)
        self.options.declare("fixed_accessory_mass", default=90.0, types=float)
        self.options.declare(
            "fuel_system_mass_per_kw",
            default=0.01,
            types=float,
            desc="Conceptual fuel-system mass allowance in kg/kW.",
        )
        self.options.declare(
            "fuel_cell_power_density",
            default=500_000.0,
            types=float,
            desc="Conceptual fuel-cell system volumetric power density in W/m^3.",
        )
        self.options.declare(
            "ice_power_density",
            default=800_000.0,
            types=float,
            desc="Conceptual ICE accessory-system volumetric power density in W/m^3.",
        )
        self.options.declare(
            "solar_rfc_specific_energy",
            default=180.0,
            types=float,
            desc="Legacy RFC storage specific energy in Wh/kg.",
        )
        self.options.declare(
            "solar_rfc_volumetric_energy_density",
            default=500.0,
            types=float,
            desc="Legacy RFC storage volumetric energy density in Wh/L.",
        )
        self.options.declare(
            "solar_rfc_areal_density",
            default=0.8,
            types=float,
            desc="Legacy RFC panel areal density in kg/m^2.",
        )

        # Optional pressure-control demand.
        self.options.declare(
            "enable_pressure_control",
            default=False,
            types=bool,
        )
        self.options.declare(
            "pressure_control_base_power",
            default=0.0,
            types=float,
        )
        self.options.declare(
            "pressure_control_fraction_of_output",
            default=0.0,
            types=float,
        )

        self.options.declare("debug_print", default=False, types=bool)

    def setup(self):
        n = self.options["num_steps"]
        ps = self.options["power_source"]

        # ==============================================================
        # Core demand and operating inputs
        # ==============================================================
        self.add_input(
            "n_engine",
            val=2.0,
            desc="Engine count.",
        )


        self.add_input(
            "shaft_power",
            val=np.full(n, 60_000.0),
            units="W",
            desc="Mechanical propeller shaft-power demand from Propulsion.",
        )

        self.add_input(
            "rated_shaft_power",
            val=-1.0,
            units="W",
            desc=(
                "Installed/rated mechanical shaft power used only for "
                "conversion-equipment sizing. A negative value falls back "
                "to the peak shaft_power history."
            ),
        )

        self.add_input(
            "mission_duration",
            val=36_000.0,
            units="s",
            desc="Total mission duration.",
        )

        self.add_input(
            "pamb",
            val=np.full(n, 55_280.0),
            units="Pa",
            desc="Ambient pressure over the mission points.",
        )

        self.add_input(
            "tamb",
            val=np.full(n, 216.65),
            units="K",
            desc="Ambient temperature over the mission points.",
        )

        self.add_input(
            "thrust_vector_angle",
            val=0.0,
            units="deg",
            desc="Propulsion thrust-vector angle.",
        )

        # ==============================================================
        # Technology inputs from AirshipIndepVariables
        # ==============================================================

        self.add_input(
            "gearbox_efficiency",
            val=0.98,
            desc="Mechanical gearbox efficiency.",
        )

        self.add_input(
            "motor_efficiency",
            val=0.95,
            desc="Electric-motor efficiency.",
        )

        self.add_input(
            "inverter_efficiency",
            val=0.98,
            desc="Power-inverter efficiency.",
        )

        self.add_input(
            "ice_thermal_efficiency",
            val=0.30,
            desc="Reciprocating-engine chemical-to-brake efficiency.",
        )

        self.add_input(
            "fuel_cell_efficiency",
            val=0.55,
            desc="Fallback fuel-cell electrical efficiency.",
        )

        self.add_input(
            "gasoline_lhv",
            val=43.0e6,
            units="J/kg",
            desc="Lower heating value of conventional aviation fuel.",
        )

        self.add_input(
            "hydrogen_lhv",
            val=120.0e6,
            units="J/kg",
            desc="Lower heating value of hydrogen.",
        )

        self.add_input(
            "generator_specific_power",
            val=2_000.0,
            units="W/kg",
            desc="Accessory generator specific power.",
        )

        self.add_input(
            "generator_efficiency",
            val=0.95,
            desc=(
                "Electrical generator efficiency. Used for conventional "
                "hotel loads and for the series conventional-battery hybrid."
            ),
        )

        self.add_input(
            "ice_specific_power",
            val=1_200.0,
            units="W/kg",
            desc=(
                "Reciprocating-engine brake-power specific power. In the "
                "conventional_battery_hybrid series architecture the ICE core "
                "is owned here because Propulsion owns the downstream motor."
            ),
        )

        self.add_input(
            "fuel_cell_specific_power",
            val=700.0,
            units="W/kg",
            desc="Fuel-cell stack specific power.",
        )

        self.add_input(
            "fuel_cell_bop_mass",
            val=100.0,
            units="kg",
            desc="Fuel-cell balance-of-plant mass.",
        )

        self.add_input(
            "solar_efficiency",
            val=0.22,
            desc="Photovoltaic conversion efficiency.",
        )

        self.add_input(
            "pv_areal_density",
            val=0.50,
            units="kg/m**2",
            desc="Photovoltaic panel areal mass density.",
        )

        if self.options["landing_system"] == "acls":
            self.add_input(
                "acls_area",
                val=377.0,
                units="m**2",
            )

        if self.options["enable_pressure_control"]:
            self.add_input(
                "pressure_control_power",
                val=np.zeros(n),
                units="W",
            )

        if uses_solar(ps):
            self.add_input(
                "solar_irradiance",
                val=np.full(n, 800.0),
                units="W/m**2",
            )
            self.add_input(
                "solar_area",
                val=30.0,
                units="m**2",
            )

        if uses_fuel_cell(ps):
            self.add_input(
                "eta_fc_dynamic",
                val=np.full(n, -1.0),
                desc=(
                    "Load-dependent fuel-cell efficiency. Negative values "
                    "use fuel_cell_efficiency."
                ),
            )

        if is_hybrid_source(ps):
            self.add_input(
                "tau",
                val=0.10,
                desc=(
                    "Battery power fraction after direct solar contribution."
                ),
            )

        # ==============================================================
        # Core outputs
        # ==============================================================

        self.add_output(
            "fuel_flow",
            val=np.zeros(n),
            units="kg/s",
            desc="Architecture fuel or hydrogen mass-flow rate.",
        )

        self.add_output(
            "power_system_mass",
            val=0.0,
            units="kg",
            desc=(
                "Conversion-source mass only. Battery and hydrogen-storage "
                "mass are external."
            ),
        )

        self.add_output(
            "power_system_volume",
            val=0.0,
            units="m**3",
            desc="Conversion-source system volume.",
        )

        self.add_output(
            "avg_efficiency",
            val=0.0,
            desc="Average active primary-source conversion efficiency.",
        )

        self.add_output(
            "rated_source_power",
            val=0.0,
            units="W",
            desc=(
                "Rated source-side power used to size conversion equipment."
            ),
        )

        self.add_output(
            "rated_power_per_unit",
            val=0.0,
            units="W",
            desc="Rated source-side power divided by n_engine.",
        )

        # ==============================================================
        # Diagnostic outputs
        # ==============================================================

        self.add_output(
            "P_elec_total",
            val=np.zeros(n),
            units="W",
            desc="Total electrical-bus or equivalent source demand.",
        )

        self.add_output(
            "P_ice_demand",
            val=np.zeros(n),
            units="W",
        )

        self.add_output(
            "P_fc_demand",
            val=np.zeros(n),
            units="W",
        )

        self.add_output(
            "P_bat_demand",
            val=np.zeros(n),
            units="W",
        )

        self.add_output(
            "P_solar_used",
            val=np.zeros(n),
            units="W",
        )

        self.add_output(
            "P_solar_available",
            val=np.zeros(n),
            units="W",
        )

        self.add_output(
            "solar_energy_generated",
            val=0.0,
            units="W*h",
        )

        self.add_output(
            "primary_power_fraction",
            val=1.0,
        )

        self.add_output(
            "battery_power_fraction_actual",
            val=0.0,
        )

        self.add_output(
            "solar_power_fraction_actual",
            val=0.0,
        )

        self.add_output(
            "generator_mass",
            val=0.0,
            units="kg",
            desc="Accessory generator mass.",
        )

        self.add_output(
            "fuel_system_mass",
            val=0.0,
            units="kg",
            desc="Conceptual fuel-system mass allowance.",
        )

        self.add_output(
            "fuel_cell_stack_mass",
            val=0.0,
            units="kg",
        )

        self.add_output(
            "hybrid_ice_core_mass",
            val=0.0,
            units="kg",
            desc=(
                "ICE core mass owned by Power only for the series "
                "conventional_battery_hybrid architecture."
            ),
        )

        self.add_output(
            "pv_mass",
            val=0.0,
            units="kg",
        )

        self.declare_partials("*", "*", method="fd", step=1e-8)

    def compute(self, inputs, outputs):
        n = self.options["num_steps"]
        src = self.options["power_source"]

        P_sh = self._as_vector(inputs["shaft_power"], n, minimum=0.0)
        aux = self._auxiliary(inputs)
        pc = self._pressure_control(inputs, P_sh)

        self._reset_outputs(outputs, n)

        if src == "conventional_reciprocating":
            self._combustion(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
                lhv=max(self._scalar(inputs["gasoline_lhv"]), 1.0),
            )

        elif src == "hydrogen_reciprocating":
            self._combustion(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
                lhv=max(self._scalar(inputs["hydrogen_lhv"]), 1.0),
            )

        elif src == "hydrogen_fuel_cell":
            self._fuel_cell(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
            )

        elif src == "battery_only":
            self._battery_only(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
            )

        elif src == "solar_battery":
            self._solar_battery(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
            )

        elif src == "solar-RFC":
            self._solar_rfc(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
            )

        elif is_hybrid_source(src):
            self._general_hybrid(
                inputs=inputs,
                outputs=outputs,
                P_sh=P_sh,
                aux=aux,
                pc=pc,
            )

        else:
            raise ValueError(f"Unsupported power_source: {src}")

        if self.options["debug_print"]:
            print(
                f"[Power] src={src} "
                f"P_elec={float(np.max(outputs['P_elec_total'])) / 1000.0:.1f} kW "
                f"P_fc={float(np.max(outputs['P_fc_demand'])) / 1000.0:.1f} kW "
                f"P_bat={float(np.max(outputs['P_bat_demand'])) / 1000.0:.1f} kW "
                f"P_ice={float(np.max(outputs['P_ice_demand'])) / 1000.0:.1f} kW "
                f"mass={float(outputs['power_system_mass']):.1f} kg"
            )

    # ------------------------------------------------------------------
    # General helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _as_vector(value, n, minimum=None):
        """Convert an input into a length-n float vector."""
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
    def _scalar(value):
        """Return a scalar float from an OpenMDAO scalar input."""
        return float(np.asarray(value).ravel()[0])

    def _reset_outputs(self, outputs, n):
        outputs["fuel_flow"] = np.zeros(n)
        outputs["power_system_mass"] = 0.0
        outputs["power_system_volume"] = 0.0
        outputs["avg_efficiency"] = 0.0
        outputs["rated_source_power"] = 0.0
        outputs["rated_power_per_unit"] = 0.0

        outputs["P_elec_total"] = np.zeros(n)
        outputs["P_ice_demand"] = np.zeros(n)
        outputs["P_fc_demand"] = np.zeros(n)
        outputs["P_bat_demand"] = np.zeros(n)
        outputs["P_solar_used"] = np.zeros(n)
        outputs["P_solar_available"] = np.zeros(n)
        outputs["solar_energy_generated"] = 0.0

        outputs["primary_power_fraction"] = 1.0
        outputs["battery_power_fraction_actual"] = 0.0
        outputs["solar_power_fraction_actual"] = 0.0

        outputs["generator_mass"] = 0.0
        outputs["fuel_system_mass"] = 0.0
        outputs["fuel_cell_stack_mass"] = 0.0
        outputs["hybrid_ice_core_mass"] = 0.0
        outputs["pv_mass"] = 0.0

    def _auxiliary(self, inputs):
        base = max(float(self.options["aux_power"]), 0.0)
        tva = float(
            np.clip(
                self._scalar(inputs["thrust_vector_angle"]),
                -90.0,
                90.0,
            )
        )

        vectoring_power = 5_000.0 if abs(tva) > 1e-12 else 0.0

        if self.options["landing_system"] == "acls":
            acls_area = max(self._scalar(inputs["acls_area"]), 50.0)
            acls_power = 1_000.0 * acls_area
        else:
            acls_power = 0.0

        return base + vectoring_power + acls_power

    def _pressure_control(self, inputs, P_sh):
        if not self.options["enable_pressure_control"]:
            return np.zeros_like(P_sh)

        if "pressure_control_power" in inputs:
            return np.maximum(
                np.atleast_1d(inputs["pressure_control_power"]).astype(float),
                0.0,
            )

        base = max(
            float(self.options["pressure_control_base_power"]),
            0.0,
        )
        fraction = max(
            float(self.options["pressure_control_fraction_of_output"]),
            0.0,
        )

        return base + fraction * P_sh

    def _rated_shaft_power(self, inputs, P_sh):
        """Return installed shaft rating or peak mission shaft demand."""
        specified = self._scalar(inputs["rated_shaft_power"])
        mission_peak = float(np.max(P_sh)) if P_sh.size else 0.0
        return max(specified, mission_peak) if specified >= 0.0 else mission_peak

    def _engine_count(self, inputs):
        """Return a positive integer engine/propulsor count for diagnostics."""
        return max(int(round(self._scalar(inputs["n_engine"]))), 1)

    def _rated_brake_power(self, inputs, P_sh, aux, pc):
        """Return rated combustion source power without engine-count duplication."""
        rated_shaft = self._rated_shaft_power(inputs, P_sh)
        eta_gb = float(np.clip(self._scalar(inputs["gearbox_efficiency"]), 0.10, 1.0))
        eta_generator = float(
            np.clip(self._scalar(inputs["generator_efficiency"]), 0.10, 1.0)
        )
        pc_peak = float(np.max(pc)) if np.size(pc) else 0.0
        return max(
            rated_shaft / eta_gb + (aux + pc_peak) / eta_generator,
            0.0,
        )

    def _rated_electrical_power(self, inputs, P_sh, aux, pc):
        """Return rated electrical-bus power without engine-count duplication."""
        rated_shaft = self._rated_shaft_power(inputs, P_sh)
        eta_gb = float(np.clip(self._scalar(inputs["gearbox_efficiency"]), 0.10, 1.0))
        eta_motor = float(np.clip(self._scalar(inputs["motor_efficiency"]), 0.10, 1.0))
        eta_inverter = float(np.clip(self._scalar(inputs["inverter_efficiency"]), 0.10, 1.0))
        pc_peak = float(np.max(pc)) if np.size(pc) else 0.0
        return max(rated_shaft / (eta_gb * eta_motor * eta_inverter) + aux + pc_peak, 0.0)

    def _brake_power(self, inputs, P_sh, aux, pc):
        eta_gb = float(
            np.clip(
                self._scalar(inputs["gearbox_efficiency"]),
                0.10,
                1.0,
            )
        )

        # Auxiliary and pressure-control powers are electrical hotel loads
        # supplied by the accessory generator for combustion architectures.
        eta_generator = float(
            np.clip(self._scalar(inputs["generator_efficiency"]), 0.10, 1.0)
        )

        return P_sh / eta_gb + (aux + pc) / eta_generator

    def _electrical_power(self, inputs, P_sh, aux, pc):
        eta_gb = float(
            np.clip(
                self._scalar(inputs["gearbox_efficiency"]),
                0.10,
                1.0,
            )
        )
        eta_motor = float(
            np.clip(
                self._scalar(inputs["motor_efficiency"]),
                0.10,
                1.0,
            )
        )
        eta_inverter = float(
            np.clip(
                self._scalar(inputs["inverter_efficiency"]),
                0.10,
                1.0,
            )
        )

        return P_sh / (eta_gb * eta_motor * eta_inverter) + aux + pc

    def _resolve_eta_fc(self, inputs, n):
        eta_flat = float(
            np.clip(
                self._scalar(inputs["fuel_cell_efficiency"]),
                0.05,
                0.75,
            )
        )

        if "eta_fc_dynamic" not in inputs:
            return np.full(n, eta_flat)

        dynamic_eta = self._as_vector(
            inputs["eta_fc_dynamic"],
            n,
        )

        eta = np.where(
            dynamic_eta >= 0.0,
            dynamic_eta,
            eta_flat,
        )

        return np.clip(eta, 0.05, 0.75)

    def _solar_available(self, inputs, n):
        if "solar_irradiance" not in inputs or "solar_area" not in inputs:
            return np.zeros(n)

        irradiance = self._as_vector(
            inputs["solar_irradiance"],
            n,
            minimum=0.0,
        )
        area = max(self._scalar(inputs["solar_area"]), 0.0)
        eta_pv = float(
            np.clip(
                self._scalar(inputs["solar_efficiency"]),
                0.0,
                1.0,
            )
        )

        return irradiance * area * eta_pv

    def _mission_energy_wh(self, power, inputs):
        duration = max(self._scalar(inputs["mission_duration"]), 0.0)
        n = max(power.size, 1)
        dt = duration / n
        return float(np.sum(power) * dt / 3600.0)

    @staticmethod
    def _set_fraction_diagnostics(
        outputs,
        P_total,
        P_solar,
        P_bat,
        P_primary,
    ):
        denominator = max(float(np.mean(P_total)), 1.0)

        outputs["solar_power_fraction_actual"] = (
            float(np.mean(P_solar)) / denominator
        )
        outputs["battery_power_fraction_actual"] = (
            float(np.mean(P_bat)) / denominator
        )
        outputs["primary_power_fraction"] = (
            float(np.mean(P_primary)) / denominator
        )

    # ------------------------------------------------------------------
    # Standalone architecture methods
    # ------------------------------------------------------------------

    def _combustion(self, inputs, outputs, P_sh, aux, pc, lhv):
        """
        Conventional or hydrogen reciprocating architecture.

        Prime-mover core mass is sized in Propulsion.py. This method includes
        only accessory-generator mass, a conceptual fuel-system allowance,
        and fixed accessory mass.
        """
        eta_thermal = float(
            np.clip(
                self._scalar(inputs["ice_thermal_efficiency"]),
                0.05,
                0.70,
            )
        )

        P_brake = np.maximum(
            self._brake_power(inputs, P_sh, aux, pc),
            0.0,
        )

        outputs["P_ice_demand"] = P_brake
        outputs["P_elec_total"] = np.maximum(aux + pc, 0.0)
        outputs["fuel_flow"] = P_brake / (eta_thermal * lhv)

        generator_specific_power = max(
            self._scalar(inputs["generator_specific_power"]),
            1.0,
        )

        pc_peak = float(np.max(pc)) if np.size(pc) else 0.0
        generator_mass = (aux + pc_peak) / generator_specific_power
        rated_brake = self._rated_brake_power(inputs, P_sh, aux, pc)

        fuel_system_mass = (
            float(self.options["fuel_system_mass_per_kw"])
            * (rated_brake / 1000.0)
        )

        fixed_accessory_mass = max(
            float(self.options["fixed_accessory_mass"]),
            0.0,
        )

        power_system_mass = (
            generator_mass
            + fuel_system_mass
            + fixed_accessory_mass
        )

        power_system_volume = (
            rated_brake
            / max(float(self.options["ice_power_density"]), 1.0)
        )

        outputs["generator_mass"] = generator_mass
        outputs["fuel_system_mass"] = fuel_system_mass
        outputs["power_system_mass"] = power_system_mass
        outputs["power_system_volume"] = power_system_volume
        outputs["avg_efficiency"] = eta_thermal
        outputs["rated_source_power"] = rated_brake
        outputs["rated_power_per_unit"] = (
            rated_brake / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_brake,
            np.zeros_like(P_brake),
            np.zeros_like(P_brake),
            P_brake,
        )

    def _fuel_cell(self, inputs, outputs, P_sh, aux, pc):
        """
        Standalone hydrogen fuel-cell architecture.

        Electric-motor mass remains in Propulsion.py. This method sizes only
        the fuel-cell stack and balance of plant.
        """
        n = self.options["num_steps"]

        P_elec = np.maximum(
            self._electrical_power(inputs, P_sh, aux, pc),
            0.0,
        )

        eta_fc = self._resolve_eta_fc(inputs, n)
        lhv_h2 = max(self._scalar(inputs["hydrogen_lhv"]), 1.0)

        outputs["P_elec_total"] = P_elec
        outputs["P_fc_demand"] = P_elec
        outputs["fuel_flow"] = P_elec / (eta_fc * lhv_h2)

        max_fc_power = self._rated_electrical_power(inputs, P_sh, aux, pc)
        fc_specific_power = max(
            self._scalar(inputs["fuel_cell_specific_power"]),
            1.0,
        )
        bop_mass = max(
            self._scalar(inputs["fuel_cell_bop_mass"]),
            0.0,
        )

        stack_mass = max_fc_power / fc_specific_power
        power_system_mass = stack_mass + bop_mass
        power_system_volume = (
            max_fc_power
            / max(float(self.options["fuel_cell_power_density"]), 1.0)
        )

        outputs["fuel_cell_stack_mass"] = stack_mass
        outputs["power_system_mass"] = power_system_mass
        outputs["power_system_volume"] = power_system_volume
        outputs["avg_efficiency"] = float(np.mean(eta_fc))
        outputs["rated_source_power"] = max_fc_power
        outputs["rated_power_per_unit"] = (
            max_fc_power / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_elec,
            np.zeros_like(P_elec),
            np.zeros_like(P_elec),
            P_elec,
        )

    def _battery_only(self, inputs, outputs, P_sh, aux, pc):
        """
        Standalone battery-electric power-demand branch.

        Battery capacity, mass, and volume are sized externally by
        BatteryOnly.py.
        """
        P_elec = np.maximum(
            self._electrical_power(inputs, P_sh, aux, pc),
            0.0,
        )

        outputs["P_elec_total"] = P_elec
        outputs["P_bat_demand"] = P_elec
        outputs["fuel_flow"] = np.zeros_like(P_elec)

        # No battery mass is owned by Power.py.
        outputs["power_system_mass"] = 0.0
        outputs["power_system_volume"] = 0.0
        outputs["avg_efficiency"] = float(
            np.clip(
                self._scalar(inputs["gearbox_efficiency"])
                * self._scalar(inputs["motor_efficiency"])
                * self._scalar(inputs["inverter_efficiency"]),
                0.0,
                1.0,
            )
        )
        rated_electrical = self._rated_electrical_power(inputs, P_sh, aux, pc)
        outputs["rated_source_power"] = rated_electrical
        outputs["rated_power_per_unit"] = (
            rated_electrical / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_elec,
            np.zeros_like(P_elec),
            P_elec,
            np.zeros_like(P_elec),
        )

    def _solar_battery(self, inputs, outputs, P_sh, aux, pc):
        """
        Standalone solar-battery power-flow branch.

        This method does NOT size PV or battery mass. The complete solar and
        battery system is sized externally by SolarBattery.py.
        """
        n = self.options["num_steps"]

        P_elec = np.maximum(
            self._electrical_power(inputs, P_sh, aux, pc),
            0.0,
        )
        P_solar_available = self._solar_available(inputs, n)
        P_solar_used = np.minimum(P_solar_available, P_elec)
        P_battery = np.maximum(P_elec - P_solar_used, 0.0)

        outputs["P_elec_total"] = P_elec
        outputs["P_solar_available"] = P_solar_available
        outputs["P_solar_used"] = P_solar_used
        outputs["P_bat_demand"] = P_battery
        outputs["solar_energy_generated"] = self._mission_energy_wh(
            P_solar_available,
            inputs,
        )

        # Mass ownership belongs to SolarBattery.py.
        outputs["power_system_mass"] = 0.0
        outputs["power_system_volume"] = 0.0
        outputs["avg_efficiency"] = float(
            np.clip(
                self._scalar(inputs["gearbox_efficiency"])
                * self._scalar(inputs["motor_efficiency"])
                * self._scalar(inputs["inverter_efficiency"]),
                0.0,
                1.0,
            )
        )
        rated_electrical = self._rated_electrical_power(inputs, P_sh, aux, pc)
        outputs["rated_source_power"] = rated_electrical
        outputs["rated_power_per_unit"] = (
            rated_electrical / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_elec,
            P_solar_used,
            P_battery,
            np.zeros_like(P_elec),
        )

    def _solar_rfc(self, inputs, outputs, P_sh, aux, pc):
        """
        Legacy solar regenerative-fuel-cell branch.

        This architecture is retained for backward compatibility. Unlike
        solar_battery, it retains its legacy storage-system sizing here until
        a dedicated RFC component is introduced.
        """
        n = self.options["num_steps"]

        P_elec = np.maximum(
            self._electrical_power(inputs, P_sh, aux, pc),
            0.0,
        )
        P_solar_available = self._solar_available(inputs, n)
        P_solar_used = np.minimum(P_solar_available, P_elec)
        P_storage = np.maximum(P_elec - P_solar_used, 0.0)

        E_required_Wh = self._mission_energy_wh(P_elec, inputs)
        E_solar_Wh = self._mission_energy_wh(
            P_solar_available,
            inputs,
        )
        E_net_Wh = max(E_required_Wh - E_solar_Wh, 10.0)

        area = max(self._scalar(inputs["solar_area"]), 0.0)
        specific_energy = max(
            float(self.options["solar_rfc_specific_energy"]),
            1.0,
        )
        volumetric_energy_density = max(
            float(self.options["solar_rfc_volumetric_energy_density"]),
            1.0,
        )
        panel_areal_density = max(
            float(self.options["solar_rfc_areal_density"]),
            0.0,
        )

        storage_mass = E_net_Wh / specific_energy
        panel_mass = area * panel_areal_density

        outputs["P_elec_total"] = P_elec
        outputs["P_solar_available"] = P_solar_available
        outputs["P_solar_used"] = P_solar_used
        outputs["P_bat_demand"] = P_storage
        outputs["solar_energy_generated"] = E_solar_Wh
        outputs["pv_mass"] = panel_mass

        outputs["power_system_mass"] = storage_mass + panel_mass
        outputs["power_system_volume"] = (
            E_net_Wh
            / volumetric_energy_density
            / 1000.0
        )
        outputs["avg_efficiency"] = 0.88
        rated_electrical = self._rated_electrical_power(inputs, P_sh, aux, pc)
        outputs["rated_source_power"] = rated_electrical
        outputs["rated_power_per_unit"] = (
            rated_electrical / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_elec,
            P_solar_used,
            P_storage,
            np.zeros_like(P_elec),
        )

    # ------------------------------------------------------------------
    # General hybrid architecture method
    # ------------------------------------------------------------------

    def _general_hybrid(self, inputs, outputs, P_sh, aux, pc):
        n = self.options["num_steps"]
        src = self.options["power_source"]
        architecture = HYBRID_ARCHITECTURES[src]

        P_total = np.maximum(
            self._electrical_power(inputs, P_sh, aux, pc),
            0.0,
        )

        if architecture["solar"]:
            P_solar_available = self._solar_available(inputs, n)
            P_solar = np.minimum(P_solar_available, P_total)
        else:
            P_solar_available = np.zeros(n)
            P_solar = np.zeros(n)

        P_remaining = np.maximum(P_total - P_solar, 0.0)

        if architecture["battery"]:
            tau = float(
                np.clip(
                    self._scalar(inputs["tau"]),
                    0.0,
                    0.95,
                )
            )
            P_battery = tau * P_remaining
        else:
            P_battery = np.zeros(n)

        P_primary = np.maximum(P_remaining - P_battery, 0.0)

        P_fc = (
            P_primary
            if architecture["fuel_cell"]
            else np.zeros(n)
        )
        P_ice = (
            P_primary
            if architecture["ice"]
            else np.zeros(n)
        )

        mass_terms = []
        volume_terms = []
        efficiency_terms = []

        if architecture["fuel_cell"]:
            eta_fc = self._resolve_eta_fc(inputs, n)
            lhv_h2 = max(
                self._scalar(inputs["hydrogen_lhv"]),
                1.0,
            )

            outputs["fuel_flow"] += P_fc / (eta_fc * lhv_h2)

            rated_total = self._rated_electrical_power(inputs, P_sh, aux, pc)
            rated_solar = min(
                float(np.max(P_solar_available)) if P_solar_available.size else 0.0,
                rated_total,
            ) if architecture["solar"] else 0.0
            rated_remaining = max(rated_total - rated_solar, 0.0)
            tau_rated = float(np.clip(self._scalar(inputs["tau"]), 0.0, 0.95))
            max_fc_power = rated_remaining * (1.0 - tau_rated)
            fc_specific_power = max(
                self._scalar(inputs["fuel_cell_specific_power"]),
                1.0,
            )
            bop_mass = max(
                self._scalar(inputs["fuel_cell_bop_mass"]),
                0.0,
            )

            stack_mass = max_fc_power / fc_specific_power

            mass_terms.append(stack_mass + bop_mass)
            volume_terms.append(
                max_fc_power
                / max(
                    float(self.options["fuel_cell_power_density"]),
                    1.0,
                )
            )
            efficiency_terms.append(float(np.mean(eta_fc)))

            outputs["fuel_cell_stack_mass"] = stack_mass

        if architecture["ice"]:
            # conventional_battery_hybrid is treated as a SERIES hybrid:
            # ICE -> generator -> electrical bus -> inverter/motor -> propeller.
            # This makes source allocation unambiguous and avoids pretending
            # that electrical bus power is engine brake power.
            eta_ice = float(
                np.clip(
                    self._scalar(inputs["ice_thermal_efficiency"]),
                    0.05,
                    0.70,
                )
            )
            eta_gen = float(
                np.clip(
                    self._scalar(inputs["generator_efficiency"]),
                    0.10,
                    1.0,
                )
            )
            lhv_gasoline = max(
                self._scalar(inputs["gasoline_lhv"]),
                1.0,
            )

            P_ice_brake = P_ice / eta_gen
            outputs["fuel_flow"] += (
                P_ice_brake / (eta_ice * lhv_gasoline)
            )

            rated_total_elec = self._rated_electrical_power(
                inputs, P_sh, aux, pc
            )
            tau_rated = float(
                np.clip(self._scalar(inputs["tau"]), 0.0, 0.95)
            )
            max_ice_electrical = rated_total_elec * (1.0 - tau_rated)
            max_ice_brake = max_ice_electrical / eta_gen

            generator_specific_power = max(
                self._scalar(inputs["generator_specific_power"]),
                1.0,
            )
            ice_specific_power = max(
                self._scalar(inputs["ice_specific_power"]),
                1.0,
            )

            generator_mass = (
                max_ice_electrical / generator_specific_power
            )
            ice_core_mass = max_ice_brake / ice_specific_power
            fuel_system_mass = (
                float(self.options["fuel_system_mass_per_kw"])
                * (max_ice_brake / 1000.0)
            )
            fixed_accessory_mass = max(
                float(self.options["fixed_accessory_mass"]),
                0.0,
            )

            mass_terms.append(
                ice_core_mass
                + generator_mass
                + fuel_system_mass
                + fixed_accessory_mass
            )
            volume_terms.append(
                max_ice_brake
                / max(float(self.options["ice_power_density"]), 1.0)
            )
            efficiency_terms.append(eta_ice * eta_gen)

            outputs["hybrid_ice_core_mass"] = ice_core_mass
            outputs["generator_mass"] = generator_mass
            outputs["fuel_system_mass"] = fuel_system_mass

        if architecture["solar"]:
            area = max(
                self._scalar(inputs["solar_area"]),
                0.0,
            )
            pv_areal_density = max(
                self._scalar(inputs["pv_areal_density"]),
                0.0,
            )
            panel_mass = area * pv_areal_density

            # For solar-hydrogen hybrid, Power.py currently owns PV mass
            # because no separate SolarBattery component is instantiated.
            mass_terms.append(panel_mass)

            outputs["pv_mass"] = panel_mass
            outputs["solar_energy_generated"] = self._mission_energy_wh(
                P_solar_available,
                inputs,
            )

        outputs["P_elec_total"] = P_total
        outputs["P_solar_available"] = P_solar_available
        outputs["P_solar_used"] = P_solar
        outputs["P_bat_demand"] = P_battery
        outputs["P_fc_demand"] = P_fc
        outputs["P_ice_demand"] = P_ice

        outputs["power_system_mass"] = (
            float(np.sum(mass_terms))
            if mass_terms
            else 0.0
        )
        outputs["power_system_volume"] = (
            float(np.sum(volume_terms))
            if volume_terms
            else 0.0
        )
        outputs["avg_efficiency"] = (
            float(np.mean(efficiency_terms))
            if efficiency_terms
            else 0.0
        )

        rated_total_source = self._rated_electrical_power(inputs, P_sh, aux, pc)
        outputs["rated_source_power"] = rated_total_source
        outputs["rated_power_per_unit"] = (
            rated_total_source / self._engine_count(inputs)
        )

        self._set_fraction_diagnostics(
            outputs,
            P_total,
            P_solar,
            P_battery,
            P_primary,
        )


if __name__ == "__main__":
    test_sources = [
        "conventional_reciprocating",
        "hydrogen_reciprocating",
        "hydrogen_fuel_cell",
        "battery_only",
        "solar_battery",
        "solar-RFC",
        "hydrogen_hybrid",
        "solar_hydrogen_hybrid",
        "conventional_battery_hybrid",
    ]

    for source in test_sources:
        problem = om.Problem()

        problem.model.add_subsystem(
            "power",
            Power(
                num_steps=10,
                power_source=source,
            ),
            promotes=["*"],
        )

        problem.setup()

        problem.set_val(
            "shaft_power",
            np.full(10, 45_000.0),
            units="W",
        )
        problem.set_val("n_engine", 2.0)
        problem.set_val("rated_shaft_power", 70_000.0, units="W")
        problem.set_val(
            "mission_duration",
            18_000.0,
            units="s",
        )

        if is_hybrid_source(source):
            problem.set_val("tau", 0.15)

        if uses_solar(source):
            problem.set_val(
                "solar_irradiance",
                np.full(10, 600.0),
                units="W/m**2",
            )
            problem.set_val(
                "solar_area",
                300.0,
                units="m**2",
            )

        problem.run_model()

        print(f"\n=== Power Test: {source} ===")
        print(
            "fuel_flow[0]        : "
            f"{float(problem.get_val('fuel_flow')[0]) * 1e3:.4f} g/s"
        )
        print(
            "power_system_mass   : "
            f"{float(problem.get_val('power_system_mass')[0]):.1f} kg"
        )
        print(
            "avg_efficiency      : "
            f"{float(problem.get_val('avg_efficiency')[0]):.3f}"
        )
        print(
            "P_solar_used[0]     : "
            f"{float(problem.get_val('P_solar_used')[0]) / 1000.0:.2f} kW"
        )
        print(
            "P_fc_demand[0]      : "
            f"{float(problem.get_val('P_fc_demand')[0]) / 1000.0:.2f} kW"
        )
        print(
            "P_bat_demand[0]     : "
            f"{float(problem.get_val('P_bat_demand')[0]) / 1000.0:.2f} kW"
        )
        print(
            "P_ice_demand[0]     : "
            f"{float(problem.get_val('P_ice_demand')[0]) / 1000.0:.2f} kW"
        )