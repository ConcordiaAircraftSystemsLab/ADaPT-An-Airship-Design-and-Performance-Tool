# -*- coding: utf-8 -*-
"""
Hydrogen Tank Component for ADaPT
=================================

Purpose
-------
Sizes the installed hydrogen inventory and hydrogen-storage hardware from the
mission hydrogen-flow history.

The component determines:

    - hydrogen consumed during the mission,
    - reserve hydrogen,
    - total installed hydrogen mass,
    - internal hydrogen volume,
    - external insulated tank volume,
    - structural and insulation mass,
    - hydrogen delivery-system mass,
    - total empty tank-system mass,
    - chemical and usable primary energy.

Responsibility boundary
-----------------------
Tank is the authoritative owner of hydrogen inventory and hydrogen-storage
mass/volume. It does not calculate propulsion demand, fuel-cell stack mass,
battery mass, or MTOW.

Hydrogen inventory
------------------
Mission hydrogen consumption is integrated from Power.fuel_flow:

    m_H2,used = integral(mdot_H2 dt)

Installed hydrogen includes reserve:

    m_H2,installed = m_H2,used * (1 + reserve_fraction)


Storage gravimetric efficiency
------------------------------
``tank_gravimetric_efficiency`` describes the base storage vessel and
insulation package before delivery hardware and volume penalties:

    eta_g,base = m_H2 / (m_H2 + m_storage,base)

therefore:

    m_storage,base = m_H2 * (1 - eta_g,base) / eta_g,base

The base storage mass is divided between structural and insulation masses.
The delivery system is then added independently:

    m_delivery = delivery_mass_fraction * m_H2

A volume-dependent penalty is also added. The output
``achieved_tank_gravimetric_efficiency`` reports the overall installed result,
including delivery hardware and volume penalties.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


class Tank(om.ExplicitComponent):
    """Hydrogen inventory and storage-system sizing component."""

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
            "insulation_type",
            default="foam",
            values=["foam", "vacuum_mli"],
        )

        self.options.declare(
            "structural_storage_share",
            default=0.72,
            types=float,
            desc="Structural fraction of base storage mass.",
        )
        self.options.declare(
            "insulation_storage_share",
            default=0.28,
            types=float,
            desc="Insulation fraction of base storage mass.",
        )
        self.options.declare(
            "use_legacy_fallback_mass",
            default=False,
            types=bool,
            desc=(
                "Use fuel_onboard_mass when integrated fuel flow is zero. "
                "Keep False for coupled sizing."
            ),
        )
        self.options.declare(
            "minimum_hydrogen_mass",
            default=1.0e-6,
            types=float,
        )
        self.options.declare(
            "minimum_tank_volume",
            default=1.0e-9,
            types=float,
        )
        self.options.declare(
            "insulation_geometry_coefficient",
            default=150.0,
            types=float,
            desc=(
                "Conceptual coefficient multiplying insulation density and "
                "thickness in the additional insulation-mass penalty."
            ),
        )

    def setup(self):
        n = self.options["num_steps"]

        # Mission hydrogen inputs
        self.add_input(
            "fuel_flow",
            val=np.zeros(n),
            units="kg/s",
            desc="Hydrogen mass-flow history from Power.",
        )
        self.add_input(
            "mission_duration",
            val=36_000.0,
            units="s",
        )
        self.add_input(
            "fuel_reserve_fraction",
            val=0.10,
            desc="Reserve hydrogen fraction relative to mission use.",
        )
        self.add_input(
            "fuel_onboard_mass",
            val=np.zeros(n),
            units="kg",
            desc=(
                "Legacy fallback installed hydrogen mass. Used only when "
                "use_legacy_fallback_mass=True and fuel flow is zero."
            ),
        )

        # Storage technology inputs
        self.add_discrete_input(
            "storage_type",
            val="liquid_h2",
        )
        self.add_input(
            "tank_pressure",
            val=1.0,
            units="bar",
        )
        self.add_input(
            "hydrogen_storage_density",
            val=70.8,
            units="kg/m**3",
        )
        self.add_input(
            "tank_gravimetric_efficiency",
            val=0.20,
            desc=(
                "Base vessel-plus-insulation gravimetric efficiency before "
                "delivery hardware and volume penalties."
            ),
        )
        self.add_input(
            "tank_volume_mass_density",
            val=15.0,
            units="kg/m**3",
            desc="Volume-dependent tank mass coefficient.",
        )
        self.add_input(
            "delivery_mass_fraction",
            val=0.08,
            desc=(
                "Hydrogen delivery-system mass divided by installed "
                "hydrogen mass."
            ),
        )
        self.add_input(
            "insulation_thickness",
            val=0.05,
            units="m",
        )
        self.add_input(
            "insulation_density",
            val=50.0,
            units="kg/m**3",
        )
        self.add_input(
            "hydrogen_lhv",
            val=120.0e6,
            units="J/kg",
        )
        self.add_input(
            "fuel_cell_efficiency",
            val=0.55,
            desc=(
                "Conversion efficiency used only for usable-energy "
                "diagnostics."
            ),
        )

        if self.options["landing_system"] == "acls":
            self.add_input(
                "acls_area",
                val=377.0,
                units="m**2",
            )

        # Hydrogen inventory outputs
        self.add_output(
            "hydrogen_mass_used",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "hydrogen_reserve_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "hydrogen_mass",
            val=0.0,
            units="kg",
            desc="Installed hydrogen mass including reserve.",
        )

        # Tank mass and volume outputs
        self.add_output(
            "tank_mass",
            val=0.0,
            units="kg",
            desc="Total empty tank-system mass excluding hydrogen.",
        )
        self.add_output(
            "tank_volume",
            val=0.0,
            units="m**3",
            desc="Internal hydrogen storage volume.",
        )
        self.add_output(
            "tank_volume_outer",
            val=0.0,
            units="m**3",
            desc="External volume including insulation.",
        )
        self.add_output(
            "structural_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "insulation_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "delivery_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "volume_penalty_mass",
            val=0.0,
            units="kg",
        )
        self.add_output(
            "nominal_tank_empty_mass",
            val=0.0,
            units="kg",
            desc=(
                "Base vessel-plus-insulation mass implied by the nominal "
                "gravimetric efficiency."
            ),
        )
        self.add_output(
            "achieved_tank_gravimetric_efficiency",
            val=0.0,
        )

        # Energy diagnostics
        self.add_output(
            "hydrogen_energy_content",
            val=0.0,
            units="W*h",
        )
        self.add_output(
            "usable_primary_energy",
            val=0.0,
            units="W*h",
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

    def compute(
        self,
        inputs,
        outputs,
        discrete_inputs=None,
        discrete_outputs=None,
    ):
        n = self.options["num_steps"]

        fuel_flow = self._vector(
            inputs["fuel_flow"],
            n,
            minimum=0.0,
        )
        mission_duration = max(
            self._scalar(inputs["mission_duration"]),
            0.0,
        )
        reserve_fraction = max(
            self._scalar(inputs["fuel_reserve_fraction"]),
            0.0,
        )

        dt = mission_duration / max(n, 1)
        hydrogen_used = float(np.sum(fuel_flow) * dt)

        if (
            hydrogen_used <= 1.0e-12
            and self.options["use_legacy_fallback_mass"]
        ):
            fallback = self._vector(
                inputs["fuel_onboard_mass"],
                n,
                minimum=0.0,
            )
            hydrogen_installed = float(np.max(fallback))
            hydrogen_used = (
                hydrogen_installed
                / max(1.0 + reserve_fraction, 1.0)
            )
            hydrogen_reserve = max(
                hydrogen_installed - hydrogen_used,
                0.0,
            )
        else:
            hydrogen_reserve = (
                hydrogen_used * reserve_fraction
            )
            hydrogen_installed = (
                hydrogen_used + hydrogen_reserve
            )

        hydrogen_installed = max(
            hydrogen_installed,
            float(self.options["minimum_hydrogen_mass"]),
        )

        if (
            discrete_inputs is not None
            and "storage_type" in discrete_inputs
        ):
            storage_type = str(
                discrete_inputs["storage_type"]
            ).lower()
        else:
            storage_type = "liquid_h2"

        tank_pressure = max(
            self._scalar(inputs["tank_pressure"]),
            1.0e-6,
        )
        hydrogen_density = max(
            self._scalar(inputs["hydrogen_storage_density"]),
            1.0e-6,
        )

        if storage_type == "compressed_h2":
            compressed_default_density = (
                5.0
                + 40.0
                * min(tank_pressure / 350.0, 2.0)
            )
            if abs(hydrogen_density - 70.8) < 1.0e-3:
                hydrogen_density = compressed_default_density

        base_gravimetric_efficiency = float(
            np.clip(
                self._scalar(
                    inputs["tank_gravimetric_efficiency"]
                ),
                0.01,
                0.95,
            )
        )
        volume_mass_density = max(
            self._scalar(inputs["tank_volume_mass_density"]),
            0.0,
        )
        delivery_mass_fraction = float(
            np.clip(
                self._scalar(inputs["delivery_mass_fraction"]),
                0.0,
                2.0,
            )
        )
        insulation_thickness = max(
            self._scalar(inputs["insulation_thickness"]),
            0.0,
        )
        insulation_density = max(
            self._scalar(inputs["insulation_density"]),
            0.0,
        )

        tank_volume = max(
            hydrogen_installed / hydrogen_density,
            float(self.options["minimum_tank_volume"]),
        )

        effective_radius = tank_volume ** (1.0 / 3.0)
        outer_volume_scale = (
            1.0
            + 3.0
            * insulation_thickness
            / max(effective_radius, 0.1)
        ) ** 3
        tank_volume_outer = tank_volume * outer_volume_scale

        nominal_storage_mass = (
            hydrogen_installed
            * (1.0 - base_gravimetric_efficiency)
            / base_gravimetric_efficiency
        )

        structural_share = max(
            float(self.options["structural_storage_share"]),
            0.0,
        )
        insulation_share = max(
            float(self.options["insulation_storage_share"]),
            0.0,
        )
        share_sum = max(
            structural_share + insulation_share,
            1.0e-12,
        )

        structural_mass = (
            nominal_storage_mass
            * structural_share
            / share_sum
        )
        insulation_baseline_mass = (
            nominal_storage_mass
            * insulation_share
            / share_sum
        )

        delivery_mass = (
            delivery_mass_fraction
            * hydrogen_installed
        )

        insulation_shell_penalty = (
            insulation_density
            * insulation_thickness
            * float(
                self.options[
                    "insulation_geometry_coefficient"
                ]
            )
        )
        volume_penalty_mass = (
            volume_mass_density * tank_volume
            + insulation_shell_penalty
        )

        insulation_mass = (
            insulation_baseline_mass
            + volume_penalty_mass
        )

        total_tank_mass = (
            structural_mass
            + insulation_mass
            + delivery_mass
        )

        achieved_efficiency = (
            hydrogen_installed
            / max(
                hydrogen_installed + total_tank_mass,
                1.0e-12,
            )
        )

        hydrogen_lhv = max(
            self._scalar(inputs["hydrogen_lhv"]),
            1.0,
        )
        conversion_efficiency = float(
            np.clip(
                self._scalar(inputs["fuel_cell_efficiency"]),
                0.0,
                1.0,
            )
        )

        chemical_energy_Wh = (
            hydrogen_installed
            * hydrogen_lhv
            / 3600.0
        )
        usable_primary_energy_Wh = (
            chemical_energy_Wh
            * conversion_efficiency
        )

        outputs["hydrogen_mass_used"] = hydrogen_used
        outputs["hydrogen_reserve_mass"] = hydrogen_reserve
        outputs["hydrogen_mass"] = hydrogen_installed

        outputs["tank_mass"] = total_tank_mass
        outputs["tank_volume"] = tank_volume
        outputs["tank_volume_outer"] = tank_volume_outer

        outputs["structural_mass"] = structural_mass
        outputs["insulation_mass"] = insulation_mass
        outputs["delivery_mass"] = delivery_mass
        outputs["volume_penalty_mass"] = volume_penalty_mass
        outputs["nominal_tank_empty_mass"] = (
            nominal_storage_mass
        )
        outputs[
            "achieved_tank_gravimetric_efficiency"
        ] = achieved_efficiency

        outputs["hydrogen_energy_content"] = (
            chemical_energy_Wh
        )
        outputs["usable_primary_energy"] = (
            usable_primary_energy_Wh
        )


if __name__ == "__main__":
    problem = om.Problem()
    problem.model.add_subsystem(
        "tank",
        Tank(num_steps=10),
        promotes=["*"],
    )
    problem.setup()

    problem.set_val(
        "fuel_flow",
        np.full(10, 0.002),
        units="kg/s",
    )
    problem.set_val(
        "mission_duration",
        18_000.0,
        units="s",
    )
    problem.run_model()

    print("\n=== Tank smoke test ===")
    print(
        f"Hydrogen used      : "
        f"{problem.get_val('hydrogen_mass_used')[0]:.2f} kg"
    )
    print(
        f"Hydrogen installed : "
        f"{problem.get_val('hydrogen_mass')[0]:.2f} kg"
    )
    print(
        f"Delivery mass      : "
        f"{problem.get_val('delivery_mass')[0]:.2f} kg"
    )
    print(
        f"Tank mass          : "
        f"{problem.get_val('tank_mass')[0]:.2f} kg"
    )
    print(
        f"Achieved grav. eff.: "
        f"{problem.get_val('achieved_tank_gravimetric_efficiency')[0]:.3f}"
    )
