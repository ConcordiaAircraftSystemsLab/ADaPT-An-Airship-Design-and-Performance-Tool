# -*- coding: utf-8 -*-
"""
Operating Conditions and Physical Properties Module for ADaPT

Purpose
-------
Provides the environmental, atmospheric, thermodynamic, and physical
properties required by all analysis components within the ADaPT framework.
This module serves as the common source of atmospheric and material data,
ensuring consistency across multidisciplinary analyses.

The module provides:
    - International Standard Atmosphere (ISA) properties
    - Ambient pressure, temperature, and density
    - Air thermodynamic and transport properties
    - Gas properties for air, helium, and hydrogen
    - Fuel properties for conventional and alternative energy sources
    - Solar radiation and sky thermal radiation
    - Reynolds number and flow properties
    - Speed of sound and air viscosity

Module responsibilities
-----------------------
    - Compute atmospheric properties as a function of altitude and ISA
      temperature deviation.
    - Evaluate ambient pressure, temperature, and density.
    - Compute gas thermodynamic properties including gas constant, specific
      heats, and specific heat ratio.
    - Estimate transport properties such as air viscosity and Reynolds
      number.
    - Compute solar irradiance and radiative sky heat flux.
    - Provide reference properties for fuels including density and lower
      heating value.
    - Supply environmental and physical properties required by geometry,
      mission, propulsion, power, buoyancy, thermal, and weight analysis
      components.

Model assumptions
-----------------
    - Atmospheric properties follow the International Standard Atmosphere
      (ISA) model up to 50 km altitude.
    - Gas behavior is modeled using the ideal gas law.
    - Air viscosity is computed using Sutherland's law.
    - Solar radiation and sky radiation are represented using simplified
      empirical relationships suitable for conceptual design.
    - Fuel properties are represented using constant reference values.
    - The module is intended for conceptual multidisciplinary analysis rather
      than high-fidelity atmospheric or thermodynamic simulation.

Outputs
-------
    - Atmospheric pressure
    - Ambient and total temperature
    - Air density
    - Gas thermodynamic properties
    - Air viscosity
    - Reynolds number
    - Speed of sound
    - Solar heat flux
    - Sky radiative heat flux
    - Fuel density and energy content

@author: Musavir Bashir
"""

import numpy as np


class opCond:
    """
    Operating Conditions class with integrated physical data.

    This class provides methods to calculate atmospheric properties, gas properties,
    fuel properties, and other relevant environmental conditions.
    """

    # Sea level reference conditions
    pressureSL = 101325.0  # Pa
    densitySL = 1.225      # kg/m^3
    temperatureSL = 15.0   # °C
    g = 9.80665            # m/s^2
    gamma = 1.4            # Air specific heat ratio
    R = 287.04             # J/(kg*K) Air gas constant

    def __init__(self, name, T_env, altitude, speed, time, RH,  *args, **kwargs):
        """
        Initializes the operating conditions object.

        Args:
            name (str): Name of the operating conditions.
            T_env (float): Static temperature of the environment in °C.
            altitude (float): Altitude of the aircraft in feet.
            speed (float): Aircraft speed in Mach number.
            time (str): Time of the day (day or night).
            RH (float): Relative Humidity of air in %.
        """
        self.name = name
        self.T_env = T_env
        self.altitude = altitude
        self.speed = speed
        self.time = time
        self.RH = RH

        # Compute deviation from ISA temperature
        _, T_isa, _ = self.atmosphere(self.altitude)  # Get standard temperature
        self.disa = self.T_env - (T_isa - 273.15)  # Convert from K to °C

    def pressure(self):
        """Calculates ambient pressure in Pa."""
        altitudeMeter = self.altitude / 3.28084
        T_ISA_K = self.T_ISA() + 273.15
        return opCond.pressureSL * (1.0 - (0.0065 * altitudeMeter / T_ISA_K)) ** 5.255

    def T_ISA(self):
        """Calculates International Standard Atmosphere Temperature in °C."""
        if self.altitude <= 36000.0:
            return opCond.temperatureSL - (1.98 * self.altitude / 1000)
        else:
            return -56.5

    def T_Tot(self):
        """Calculates total air temperature in Kelvin."""
        T_stat = self.T_env + 273.15
        return (1 + ((opCond.gamma - 1) / 2) * self.speed**2) * T_stat

    def solarLoad(self):
        """Calculates solar heat flux outside the atmosphere."""
        Q_sun = 1367  # W/m^2

        if self.altitude == 0.0:
            return 0.77 * Q_sun
        elif self.altitude <= 10000.0:
            return 0.84 * Q_sun
        else:
            return 0.92 * Q_sun

    def radSky(self):
        """Calculates radiative sky heat flux."""
        dewTemp = -34.56 + 0.446 * self.RH + 0.873 * (self.T_Tot() - 273.15)
        skyEmissivity = 0.741 + 0.0062 * dewTemp
        sigmaB = 5.67e-8  # Stefan-Boltzmann constant
        return skyEmissivity * sigmaB * (self.T_Tot() - 273.15) ** 4

    def atmosphere(self, altp, disa=0.):
        """Calculates ambient data from pressure altitude according to Standard Atmosphere."""
        g = 9.80665
        r = 287.053
        gam = 1.4
        Z = np.array([0., 11000., 20000., 32000., 47000., 50000.])
        dtodz = np.array([-0.0065, 0., 0.0010, 0.0028, 0.])
        P = np.array([101325., 0., 0., 0., 0., 0.])
        T = np.array([288.15, 0., 0., 0., 0., 0.])

        if Z[-1] < altp:
            raise ValueError("atmosphere: altitude cannot exceed 50km")

        j = 0
        while Z[1 + j] <= altp:
            T[j + 1] = T[j] + dtodz[j] * (Z[j + 1] - Z[j])
            if abs(dtodz[j]) > 0.:
                P[j + 1] = P[j] * (1. + (dtodz[j] / T[j]) * (Z[j + 1] - Z[j])) ** (-g / (r * dtodz[j]))
            else:
                P[j + 1] = P[j] * np.exp(-(g / r) * ((Z[j + 1] - Z[j]) / T[j]))
            j += 1

        if abs(dtodz[j]) > 0.:
            pamb = P[j] * (1 + (dtodz[j] / T[j]) * (altp - Z[j])) ** (-g / (r * dtodz[j]))
        else:
            pamb = P[j] * np.exp(-(g / r) * ((altp - Z[j]) / T[j]))
        tamb = T[j] + dtodz[j] * (altp - Z[j]) + disa
        return pamb, tamb, g

    def gas_data(self, gas="air"):
        """Returns gas data (r, gamma, cp, cv)."""
        r_dict = {"air": 287.053, "helium": 2077., "hydrogen": 4124.}
        gam_dict = {"air": 1.40, "helium": 1.66, "hydrogen": 1.41}
        r = r_dict.get(gas, "Error: gas unknown")
        gam = gam_dict.get(gas, "Error: gas unknown")
        cv = r / (gam - 1.)
        cp = gam * cv
        return r, gam, cp, cv

    def gas_density(self, pamb, tamb, gas="air"):
        """Calculates ideal gas density."""
        r, gam, cp, cv = self.gas_data(gas)
        rho = pamb / (r * tamb)
        return rho

    def sound_speed(self, tamb):
        """Calculates sound speed for ideal gas."""
        r, gam, cp, cv = self.gas_data()
        vsnd = np.sqrt(gam * r * tamb)
        return vsnd

    def air_viscosity(self, tamb):
        """Calculates mixed gas dynamic viscosity using Sutherland's formula."""
        mu0, T0, S = 1.715e-5, 273.15, 110.4
        mu = (mu0 * ((T0 + S) / (tamb + S)) * (tamb / T0) ** 1.5)
        return mu

    def reynolds_number(self, pamb, tamb, tas, length):
        rho = self.gas_density(pamb, tamb)
        mu = self.air_viscosity(tamb)
        re = rho * tas * length / mu
        return re

    def fuel_density(self, fuel_type, press=101325.):
        """Returns reference fuel density."""
        if fuel_type == "kerosene":
            return 803.  # kg/m^3
        elif fuel_type == "liquid_h2":
            return 70.8  # kg/m^3
        elif fuel_type == "Compressed_h2":
            p = press * 1.e-5
            return (-3.11480362e-05 * p + 7.82320891e-02) * p + 1.03207822e-01  # kg/m^3
        elif fuel_type == "methane":
            return 422.6  # kg/m^3
        elif fuel_type == "battery":
            return 2800.  # kg/m^3
        else:
            raise ValueError("fuel_type key is unknown")

    def fuel_heat(self, fuel_type):
        """Returns reference fuel lower heating value or battery specific energy in J/kg."""
        if fuel_type == "kerosene":
            return 43.1e6       # J/kg  (43.1 MJ/kg)
        elif fuel_type == "liquid_h2":
            return 121.0e6      # J/kg
        elif fuel_type == "Compressed_h2":
            return 140.0e6      # J/kg
        elif fuel_type == "methane":
            return 50.3e6       # J/kg
        elif fuel_type == "battery":
            return 200 * 3600   # 200 Wh/kg → 720,000 J/kg
        else:
            raise ValueError(f"fuel_type '{fuel_type}' is unknown")

    def stoichiometry(self, oxydizer, fuel):
        """Returns stoichiometry ratio."""
        if oxydizer == "air":
            if fuel == "hydrogen":
                return 34.5
            else:
                raise ValueError("Fuel type is unknown")
        else:
            raise ValueError("Oxydizer type is unknown")