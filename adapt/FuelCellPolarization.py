# -*- coding: utf-8 -*-
"""
Fuel-Cell Polarization Component for ADaPT
==========================================

Purpose
-------
Computes load-dependent PEM fuel-cell operating conditions, electrical
conversion efficiency, hydrogen consumption diagnostics, and stack power
capability.

The component replaces a single constant fuel-cell efficiency with a
semi-empirical polarization model evaluated at each mission point.

Responsibilities
----------------
- Receive requested fuel-cell electrical power.
- Compute cell voltage from Nernst, activation, ohmic, and concentration
  losses.
- Solve for the operating current density.
- Compute load-dependent fuel-cell efficiency.
- Compute stack maximum power capability.
- Report requested-power shortfall explicitly.
- Compute power-specific hydrogen consumption for diagnostics.

Responsibility boundary
-----------------------
This component does not size:

    - fuel-cell stack mass,
    - hydrogen mass,
    - hydrogen tank mass,
    - battery mass,
    - MTOW.

Fuel-cell stack mass is sized in Power.py from ``fuel_cell_specific_power``.
Hydrogen mass is integrated from Power.fuel_flow in Tank.py.

Capability convention
---------------------
The polarization solver determines the maximum stack power available at the
upper operating-current limit. If requested power exceeds this capability,
the operating point is evaluated at the maximum allowable current and the
difference is reported as:

    fc_power_shortfall = P_requested - P_available

A value less than or equal to zero is feasible.

Efficiency convention
---------------------
Fuel-cell electrical efficiency is estimated from operating cell voltage
relative to the thermoneutral voltage, with a correction for parasitic
current loss:

    eta_fc = (V_cell / V_thermoneutral)
             * i / (i + i_loss)

The result is bounded to a conceptual range.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


DEFAULT_FC_PARAMS = {
    "R": 8.314,
    "T": 333.15,
    "alpha": 1.0,
    "n": 2.0,
    "F": 96_485.0,
    "pH2": 0.60,
    "pO2": 0.21,
    "pH2O": 1.0,
    "i0": 3.0e-6,
    "iL": 1.60,
    "i_loss": 0.002,
    "Ri_per_cell": 0.10,
}

THERMONEUTRAL_VOLTAGE = 1.481
HYDROGEN_MOLAR_MASS = 2.016e-3


def nernst_voltage(
    temperature,
    p_h2,
    p_o2,
    p_h2o,
    params=DEFAULT_FC_PARAMS,
    delta_h=-241_820.0,
    delta_s=-44.43,
):
    """Return reversible cell voltage from a simplified Nernst relation."""
    gas_constant = params["R"]
    electrons = params["n"]
    faraday = params["F"]

    standard_voltage = (
        -(delta_h / (electrons * faraday))
        + temperature * delta_s / (electrons * faraday)
    )

    reaction_quotient = (
        max(p_h2, 1.0e-12)
        * max(p_o2, 1.0e-12) ** 0.5
        / max(p_h2o, 1.0e-12)
    )

    return (
        standard_voltage
        + (
            gas_constant
            * temperature
            / (electrons * faraday)
        )
        * np.log(reaction_quotient)
    )


def cell_voltage(
    current_density,
    temperature,
    p_h2,
    p_o2,
    p_h2o,
    exchange_current_density,
    limiting_current_density,
    parasitic_current_density,
    area_specific_resistance,
    transfer_coefficient,
    params=DEFAULT_FC_PARAMS,
):
    """Return PEM fuel-cell voltage at a specified current density."""
    gas_constant = params["R"]
    faraday = params["F"]
    electrons = params["n"]

    reversible_voltage = nernst_voltage(
        temperature=temperature,
        p_h2=p_h2,
        p_o2=p_o2,
        p_h2o=p_h2o,
        params=params,
    )

    effective_current = np.clip(
        current_density + parasitic_current_density,
        1.0e-12,
        None,
    )
    concentration_margin = np.clip(
        limiting_current_density - current_density,
        1.0e-9,
        None,
    )

    activation_loss = (
        gas_constant
        * temperature
        / max(
            transfer_coefficient * faraday,
            1.0e-12,
        )
        * np.log(
            effective_current
            / max(exchange_current_density, 1.0e-15)
        )
    )

    ohmic_loss = (
        current_density * area_specific_resistance
    )

    concentration_loss = (
        gas_constant
        * temperature
        / (electrons * faraday)
        * np.log(
            limiting_current_density
            / concentration_margin
        )
    )

    return (
        reversible_voltage
        - activation_loss
        - ohmic_loss
        - concentration_loss
    )


def stack_power(
    current_density,
    n_cells,
    active_area_cm2,
    **voltage_kwargs,
):
    """Return stack electrical power at a current density."""
    voltage = cell_voltage(
        current_density=current_density,
        **voltage_kwargs,
    )

    return (
        n_cells
        * voltage
        * current_density
        * active_area_cm2
    )


def solve_operating_point(
    requested_power,
    n_cells,
    active_area_cm2,
    voltage_kwargs,
    upper_current_fraction=0.97,
    iterations=80,
):
    """
    Solve the fuel-cell operating point and stack power capability.

    Returns
    -------
    current_density : float
    cell_voltage_value : float
    efficiency : float
    psfc : float
    available_power : float
    maximum_power : float
    power_shortfall : float
    is_power_limited : float
    """
    limiting_current = voltage_kwargs[
        "limiting_current_density"
    ]
    parasitic_current = voltage_kwargs[
        "parasitic_current_density"
    ]
    faraday = DEFAULT_FC_PARAMS["F"]

    lower_current = 1.0e-6
    upper_current = max(
        limiting_current * upper_current_fraction,
        lower_current * 10.0,
    )

    # The stack power curve is not guaranteed to be monotonic up to the
    # limiting-current boundary. Locate the true peak first, then solve only
    # on the stable ascending branch.
    current_grid = np.linspace(lower_current, upper_current, 500)
    power_grid = np.array([
        max(
            float(
                stack_power(
                    current_value,
                    n_cells,
                    active_area_cm2,
                    **voltage_kwargs,
                )
            ),
            0.0,
        )
        for current_value in current_grid
    ])
    peak_index = int(np.argmax(power_grid))
    current_at_max_power = float(current_grid[peak_index])
    maximum_power = float(power_grid[peak_index])

    requested_power = max(float(requested_power), 0.0)
    target_power = min(requested_power, maximum_power)

    if target_power <= 1.0e-12:
        current_density = lower_current
    else:
        low = lower_current
        high = current_at_max_power

        for _ in range(iterations):
            mid = 0.5 * (low + high)
            mid_power = float(
                stack_power(
                    mid,
                    n_cells,
                    active_area_cm2,
                    **voltage_kwargs,
                )
            )

            if mid_power < target_power:
                low = mid
            else:
                high = mid

        current_density = 0.5 * (low + high)

    voltage_value = float(
        cell_voltage(
            current_density=current_density,
            **voltage_kwargs,
        )
    )

    available_power = max(
        float(
            n_cells
            * voltage_value
            * current_density
            * active_area_cm2
        ),
        0.0,
    )

    efficiency = float(
        np.clip(
            (
                voltage_value / THERMONEUTRAL_VOLTAGE
            )
            * (
                current_density
                / max(
                    current_density + parasitic_current,
                    1.0e-12,
                )
            ),
            0.05,
            0.75,
        )
    )

    hydrogen_molar_flow = (
        n_cells
        * current_density
        * active_area_cm2
        / (2.0 * faraday)
    )
    hydrogen_mass_flow = (
        hydrogen_molar_flow
        * HYDROGEN_MOLAR_MASS
    )

    psfc = (
        hydrogen_mass_flow
        / max(available_power, 1.0)
    )

    power_shortfall = max(
        requested_power - available_power,
        0.0,
    )
    is_power_limited = (
        1.0 if power_shortfall > 1.0e-9 else 0.0
    )

    return (
        current_density,
        voltage_value,
        efficiency,
        psfc,
        available_power,
        maximum_power,
        power_shortfall,
        is_power_limited,
    )


class FuelCellPolarization(om.ExplicitComponent):
    """Semi-empirical PEM fuel-cell polarization and capability model."""

    def initialize(self):
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )

    def setup(self):
        n = self.options["num_steps"]

        # ==============================================================
        # Power demand and stack sizing inputs
        # ==============================================================

        self.add_input(
            "P_fc_demand",
            val=np.full(n, 50_000.0),
            units="W",
            desc="Requested fuel-cell electrical power.",
        )
        self.add_input(
            "n_fc_cells",
            val=300.0,
        )
        self.add_input(
            "fc_active_area",
            val=300.0,
            units="cm**2",
        )

        # ==============================================================
        # Polarization and operating-condition inputs
        # ==============================================================

        self.add_input(
            "fc_temperature",
            val=333.15,
            units="K",
        )
        self.add_input(
            "fc_hydrogen_partial_pressure",
            val=0.60,
            units="bar",
        )
        self.add_input(
            "fc_oxygen_partial_pressure",
            val=0.21,
            units="bar",
        )
        self.add_input(
            "fc_water_partial_pressure",
            val=1.0,
            units="bar",
        )
        self.add_input(
            "fc_exchange_current_density",
            val=3.0e-6,
            units="A/cm**2",
        )
        self.add_input(
            "fc_limiting_current_density",
            val=1.60,
            units="A/cm**2",
        )
        self.add_input(
            "fc_parasitic_current_density",
            val=0.002,
            units="A/cm**2",
        )
        self.add_input(
            "fc_area_specific_resistance",
            val=0.10,
            units="ohm*cm**2",
        )
        self.add_input(
            "fc_transfer_coefficient",
            val=1.0,
        )

        # ==============================================================
        # Core outputs
        # ==============================================================

        self.add_output(
            "eta_fc",
            val=np.full(n, 0.55),
            desc="Load-dependent fuel-cell electrical efficiency.",
        )
        self.add_output(
            "PSFC",
            val=np.full(n, 1.0e-8),
            units="kg/(W*s)",
            desc="Power-specific hydrogen consumption.",
        )
        self.add_output(
            "i_op",
            val=np.full(n, 0.3),
            units="A/cm**2",
        )
        self.add_output(
            "v_op",
            val=np.full(n, 0.65),
            units="V",
        )

        # ==============================================================
        # Capability and feasibility outputs
        # ==============================================================

        self.add_output(
            "P_fc_available",
            val=np.zeros(n),
            units="W",
            desc="Fuel-cell power delivered at the solved operating point.",
        )
        self.add_output(
            "P_fc_max",
            val=np.zeros(n),
            units="W",
            desc="Maximum stack power at the allowed current-density limit.",
        )
        self.add_output(
            "fc_power_shortfall",
            val=np.zeros(n),
            units="W",
            desc=(
                "Requested fuel-cell power minus available power. "
                "A value <= 0 is feasible."
            ),
        )
        self.add_output(
            "fc_power_margin",
            val=np.zeros(n),
            units="W",
            desc="Maximum stack power minus requested power.",
        )
        self.add_output(
            "fc_power_limited",
            val=np.zeros(n),
            desc="1 where requested power exceeds stack capability.",
        )
        self.add_output(
            "fc_load_fraction",
            val=np.zeros(n),
            desc="Requested power divided by maximum stack power.",
        )

        # ==============================================================
        # Hydrogen-flow diagnostics
        # ==============================================================

        self.add_output(
            "fc_hydrogen_flow",
            val=np.zeros(n),
            units="kg/s",
            desc="Hydrogen flow implied by the polarization operating point.",
        )
        self.add_output(
            "fc_voltage_efficiency",
            val=np.zeros(n),
            desc="Cell voltage divided by thermoneutral voltage.",
        )

        self.declare_partials("*", "*", method="fd", step=1e-6)

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
            arr = np.pad(
                arr,
                (0, n - arr.size),
                mode="edge",
            )
        elif arr.size > n:
            arr = arr[:n]

        if minimum is not None:
            arr = np.maximum(arr, minimum)

        return arr

    def compute(self, inputs, outputs):
        n = self.options["num_steps"]

        power_demand = self._vector(
            inputs["P_fc_demand"],
            n,
            minimum=0.0,
        )

        n_cells = max(
            self._scalar(inputs["n_fc_cells"]),
            1.0,
        )
        active_area = max(
            self._scalar(inputs["fc_active_area"]),
            1.0,
        )

        temperature = max(
            self._scalar(inputs["fc_temperature"]),
            250.0,
        )
        p_h2 = max(
            self._scalar(
                inputs["fc_hydrogen_partial_pressure"]
            ),
            1.0e-9,
        )
        p_o2 = max(
            self._scalar(
                inputs["fc_oxygen_partial_pressure"]
            ),
            1.0e-9,
        )
        p_h2o = max(
            self._scalar(
                inputs["fc_water_partial_pressure"]
            ),
            1.0e-9,
        )
        exchange_current = max(
            self._scalar(
                inputs["fc_exchange_current_density"]
            ),
            1.0e-15,
        )
        limiting_current = max(
            self._scalar(
                inputs["fc_limiting_current_density"]
            ),
            1.0e-4,
        )
        parasitic_current = max(
            self._scalar(
                inputs["fc_parasitic_current_density"]
            ),
            0.0,
        )
        area_specific_resistance = max(
            self._scalar(
                inputs["fc_area_specific_resistance"]
            ),
            0.0,
        )
        transfer_coefficient = max(
            self._scalar(
                inputs["fc_transfer_coefficient"]
            ),
            1.0e-6,
        )

        voltage_kwargs = {
            "temperature": temperature,
            "p_h2": p_h2,
            "p_o2": p_o2,
            "p_h2o": p_h2o,
            "exchange_current_density": exchange_current,
            "limiting_current_density": limiting_current,
            "parasitic_current_density": parasitic_current,
            "area_specific_resistance": area_specific_resistance,
            "transfer_coefficient": transfer_coefficient,
        }

        eta = np.zeros(n)
        psfc = np.zeros(n)
        current_density = np.zeros(n)
        voltage = np.zeros(n)
        available_power = np.zeros(n)
        maximum_power = np.zeros(n)
        shortfall = np.zeros(n)
        limited = np.zeros(n)
        load_fraction = np.zeros(n)
        hydrogen_flow = np.zeros(n)
        voltage_efficiency = np.zeros(n)

        for index in range(n):
            (
                i_value,
                v_value,
                eta_value,
                psfc_value,
                available_value,
                maximum_value,
                shortfall_value,
                limited_value,
            ) = solve_operating_point(
                requested_power=power_demand[index],
                n_cells=n_cells,
                active_area_cm2=active_area,
                voltage_kwargs=voltage_kwargs,
            )

            eta[index] = eta_value
            psfc[index] = psfc_value
            current_density[index] = i_value
            voltage[index] = v_value
            available_power[index] = available_value
            maximum_power[index] = maximum_value
            shortfall[index] = shortfall_value
            limited[index] = limited_value

            load_fraction[index] = (
                power_demand[index]
                / max(maximum_value, 1.0e-12)
            )

            hydrogen_flow[index] = (
                psfc_value
                * available_value
            )
            voltage_efficiency[index] = (
                v_value / THERMONEUTRAL_VOLTAGE
            )

        outputs["eta_fc"] = eta
        outputs["PSFC"] = psfc
        outputs["i_op"] = current_density
        outputs["v_op"] = voltage

        outputs["P_fc_available"] = available_power
        outputs["P_fc_max"] = maximum_power
        outputs["fc_power_shortfall"] = shortfall
        outputs["fc_power_margin"] = (
            maximum_power - power_demand
        )
        outputs["fc_power_limited"] = limited
        outputs["fc_load_fraction"] = load_fraction

        outputs["fc_hydrogen_flow"] = hydrogen_flow
        outputs["fc_voltage_efficiency"] = (
            voltage_efficiency
        )


if __name__ == "__main__":
    problem = om.Problem()
    problem.model.add_subsystem(
        "fc",
        FuelCellPolarization(num_steps=5),
        promotes=["*"],
    )
    problem.setup()

    problem.set_val(
        "P_fc_demand",
        np.linspace(10_000.0, 100_000.0, 5),
        units="W",
    )

    problem.run_model()

    print("\n=== FuelCellPolarization smoke test ===")
    print(
        "Requested power [kW] :",
        problem.get_val("P_fc_demand") / 1000.0,
    )
    print(
        "Available power [kW] :",
        problem.get_val("P_fc_available") / 1000.0,
    )
    print(
        "Efficiency           :",
        problem.get_val("eta_fc"),
    )
    print(
        "Power shortfall [kW] :",
        problem.get_val("fc_power_shortfall") / 1000.0,
    )