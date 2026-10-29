# Power and Energy Conversion

The Power component converts the mechanical shaft-power demand supplied by the propulsion model into architecture-dependent source power, electrical-bus demand, fuel or hydrogen flow, and conversion-equipment sizing.

The component is implemented as

```python
Power(om.ExplicitComponent)
```

and acts as the interface between the **mechanical propulsion requirement** and the **energy-source architecture**. Its principal responsibility is not to resize the propeller or prime mover, but to determine how much source-side power is required and how that power is supplied by combustion, fuel cells, batteries, solar generation, or combinations of these technologies.

The model supports conventional reciprocating, hydrogen reciprocating, hydrogen fuel-cell, battery-electric, solar-battery, solar regenerative-fuel-cell, hydrogen-hybrid, solar-hydrogen-hybrid, and conventional-battery-hybrid architectures.

Carichner and Nicolai treat airship propulsion and power generation as an integrated system in which mechanical propulsion demand [1]. Rest electric motors, batteries, fuel cells, solar cells, generators, and energy storage are studied and must be considered consistently during conceptual design.

---

## 1. Model Scope

The overall information flow is

$$
P_{\mathrm{shaft}}
\rightarrow
P_{\mathrm{source/electrical}}
\rightarrow
\begin{cases}
\dot m_f,\\
\dot m_{H_2},\\
P_{\mathrm{battery}},\\
P_{\mathrm{solar}},\\
P_{\mathrm{FC}},\\
P_{\mathrm{ICE}}
\end{cases}
$$

followed by architecture-dependent conversion-equipment sizing.

The component calculates:

- mission brake-power or electrical-bus demand,
- conventional-fuel or hydrogen mass flow,
- solar power available and used,
- battery power demand,
- fuel-cell power demand,
- ICE power demand,
- hybrid source fractions,
- source-side rated power,
- fuel-cell stack mass,
- fuel-cell balance-of-plant contribution,
- accessory generator mass,
- conceptual fuel-system mass,
- PV-panel mass where this component owns it,
- conversion-system volume.

---

## 2. Mass-Ownership Convention

The framework deliberately separates component ownership.

### Propulsion component owns

- reciprocating-engine or electric-motor core mass,
- propeller mass,
- nacelle mass,
- pylon/mount mass,
- propulsion wiring where enabled.

### Power component owns

- accessory generator mass,
- conceptual fuel-system allowance,
- fuel-cell stack mass,
- fuel-cell balance of plant,
- PV panel mass for `solar_hydrogen_hybrid`,
- simplified RFC storage mass in the retained `solar-RFC` branch.

### Battery components own

- battery capacity,
- battery mass,
- battery volume.

### Tank component owns

- hydrogen mass,
- hydrogen tank mass,
- installed tank volume.

This ownership convention prevents double counting in the vehicle mass buildup.

---

## 3. Supported Power Architectures

The current implementation supports:

| Architecture | ICE | Fuel cell | Battery | Solar |
|---|---:|---:|---:|---:|
| `conventional_reciprocating` | ✓ | – | – | – |
| `hydrogen_reciprocating` | ✓ | – | – | – |
| `hydrogen_fuel_cell` | – | ✓ | – | – |
| `battery_only` | – | – | ✓ | – |
| `solar_battery` | – | – | ✓ | ✓ |
| `solar-RFC` | – | RFC storage | storage | ✓ |
| `hydrogen_hybrid` | – | ✓ | ✓ | – |
| `solar_hydrogen_hybrid` | – | ✓ | ✓ | ✓ |
| `conventional_battery_hybrid` | ✓ | – | ✓ | – |

The hybrid architecture dictionary explicitly identifies whether each architecture contains an ICE, fuel cell, battery, or solar path.

---

## 4. Core Inputs

### 4.1 Power-Demand Inputs

| Input | Symbol | Default | Units | Description |
|---|---:|---:|---:|---|
| `shaft_power` | $P_{sh}$ | 60 kW | W | Mission mechanical shaft-power history |
| `rated_shaft_power` | $P_{sh,r}$ | -1 | W | Installed shaft-power rating; negative means use mission peak |
| `mission_duration` | $t_m$ | 36,000 | s | Total mission duration |
| `n_engine` | $N_e$ | 2 | – | Propulsor count |
| `pamb` | $p_\infty$ | 55,280 | Pa | Ambient pressure history |
| `tamb` | $T_\infty$ | 216.65 | K | Ambient temperature history |
| `thrust_vector_angle` | $\theta_T$ | 0 | deg | Thrust-vector angle |


---

## 5. Technology Inputs

| Input | Symbol | Default | Units | Interpretation |
|---|---:|---:|---:|---|
| `gearbox_efficiency` | $\eta_g$ | 0.98 | – | Mechanical transmission efficiency |
| `motor_efficiency` | $\eta_m$ | 0.95 | – | Electric-motor efficiency |
| `inverter_efficiency` | $\eta_{inv}$ | 0.98 | – | Power-electronics efficiency |
| `ice_thermal_efficiency` | $\eta_{ICE}$ | 0.30 | – | Chemical-to-brake efficiency |
| `fuel_cell_efficiency` | $\eta_{FC}$ | 0.55 | – | Fallback fuel-cell efficiency |
| `gasoline_lhv` | $LHV_f$ | $43\times10^6$ | J/kg | Conventional fuel lower heating value |
| `hydrogen_lhv` | $LHV_{H_2}$ | $120\times10^6$ | J/kg | Hydrogen lower heating value |
| `generator_specific_power` | $SP_g$ | 2000 | W/kg | Accessory-generator specific power |
| `fuel_cell_specific_power` | $SP_{FC}$ | 700 | W/kg | Fuel-cell stack specific power |
| `fuel_cell_bop_mass` | $m_{BOP}$ | 100 | kg | Fuel-cell balance-of-plant mass |
| `solar_efficiency` | $\eta_{PV}$ | 0.22 | – | Photovoltaic conversion efficiency |
| `pv_areal_density` | $\sigma_{PV}$ | 0.50 | kg/m² | PV installed areal mass density |

These values are technology assumptions and are intentionally exposed as OpenMDAO inputs for DOE, sensitivity, optimization, and technology assessment.

---

## 6. Fixed Model Options

The component also contains several fixed assumptions.

| Option | Default | Units | Interpretation |
|---|---:|---:|---|
| `aux_power` | 10,000 | W | Baseline hotel/auxiliary electrical power |
| `fixed_accessory_mass` | 90 | kg | Fixed combustion-system accessory mass |
| `fuel_system_mass_per_kw` | 0.01 | kg/kW | Fuel-system mass allowance |
| `fuel_cell_power_density` | 500,000 | W/m³ | Fuel-cell volumetric power density |
| `ice_power_density` | 800,000 | W/m³ | ICE accessory-system volumetric power density |
| `solar_rfc_specific_energy` | 180 | Wh/kg | simplified RFC storage specific energy |
| `solar_rfc_volumetric_energy_density` | 500 | Wh/L | simplified RFC volumetric energy density |
| `solar_rfc_areal_density` | 0.8 | kg/m² | simplified RFC solar-panel areal density |

Unless separately traced to a source, these quantities should be documented as implementation assumptions or calibration parameters.

---

# 7. Mechanical-to-Brake-Power Conversion

For combustion architectures, shaft power is converted to brake/source power through the gearbox efficiency:

$$
\boxed{
P_{br}
=
\frac{P_{sh}}{\eta_g}
+
\frac{P_{aux}}{\eta_{gen}}
+
P_{pc}
}
\tag{EQ-1}
$$

where

- $P_{sh}$ is required propeller shaft power,
- $\eta_g$ is gearbox efficiency,
- $P_{aux}$ is auxiliary electrical load,
- $\eta_{gen}$ is accessory-generator efficiency,
- $P_{pc}$ is pressure-control power.

The implementation uses

$$
\eta_{gen}=0.95.
$$

The gearbox relationship itself is a fundamental efficiency relation. The generator efficiency is an implementation assumption.

---

## 8. Electrical-Bus Power

For electrically driven propulsion, the electrical demand is

$$
\boxed{
P_{elec}
=
\frac{P_{sh}}
{\eta_g\eta_m\eta_{inv}}
+
P_{aux}
+
P_{pc}.
}
\tag{EQ-2}
$$

Thus every conversion loss upstream of the propeller shaft increases source-side electrical demand.

With the baseline efficiencies,

$$
\eta_g=0.98,\qquad
\eta_m=0.95,\qquad
\eta_{inv}=0.98.
$$

The combined shaft-to-bus conversion efficiency is

$$
\eta_{chain}
=
\eta_g\eta_m\eta_{inv}.
$$

**Classification:** fundamental efficiency-chain formulation with technology-dependent parameters.

---

## 9. Rated Source Power

The component separates mission power history from installed source rating.

If an explicit rated shaft power is available,

$$
P_{sh,rated}
=
\max(P_{sh,specified},P_{sh,mission,max}),
$$

otherwise

$$
P_{sh,rated}
=
P_{sh,mission,max}.
$$

For combustion architectures,

$$
\boxed{
P_{source,rated}^{ICE}
=
\frac{P_{sh,rated}}{\eta_g}
+
\frac{P_{aux}}{\eta_{gen}}
+
P_{pc,max}.
}
\tag{EQ-3}
$$

For electrical architectures,

$$
\boxed{
P_{source,rated}^{elec}
=
\frac{P_{sh,rated}}
{\eta_g\eta_m\eta_{inv}}
+
P_{aux}
+
P_{pc,max}.
}
\tag{EQ-4}
$$

These ratings are used to size conversion equipment. 

---

# 10. Auxiliary Power

The baseline auxiliary demand is

$$
P_{aux,base}=10~{\rm kW}.
$$

Additional loads are added conditionally.

### 10.1 Thrust-Vectoring Load

If

$$
|\theta_T|>0,
$$

the code adds

$$
\boxed{
P_{vector}=5~{\rm kW}.
}
\tag{EQ-5}
$$

### 10.2 ACLS Load

For ACLS configurations,

$$
\boxed{
P_{ACLS}
=
1000\,S_{ACLS}
}
\tag{EQ-6}
$$

with $P$ in watts when $S_{ACLS}$ is supplied in square metres.

The ACLS area is internally floored at

$$
S_{ACLS}\ge50~{\rm m^2}.
$$

The total auxiliary demand is

$$
\boxed{
P_{aux}
=
P_{aux,base}
+
P_{vector}
+
P_{ACLS}.
}
\tag{EQ-7}
$$

These numerical relationships are implementation assumptions.

Carichner and Nicolai describe the ACLS as a dedicated pressure/blower system with its own pressurization requirements, but the present $1000~{\rm W/m^2}$ relationship is not directly established by the cited book [1].

---

# 11. Pressure-Control Power

Pressure-control power is optional.

If disabled,

$$
P_{pc}=0.
$$

If an external `pressure_control_power` history is supplied, the model uses that demand directly.

Otherwise, the fallback model is

$$
\boxed{
P_{pc}
=
P_{pc,base}
+
f_{pc}P_{sh}.
}
\tag{EQ-8}
$$

Both coefficients default to zero.

This is therefore an extensibility mechanism rather than an active baseline physical model.

---

# 12. Conventional and Hydrogen Reciprocating Architectures

The conventional and hydrogen reciprocating branches use the same mechanical power model. Only the fuel lower heating value differs.

The fuel mass-flow relation follows directly from thermal efficiency:

$$
\eta_{ICE}
=
\frac{P_{br}}
{\dot m_f LHV}.
$$

Therefore,

$$
\boxed{
\dot m_f
=
\frac{P_{br}}
{\eta_{ICE}LHV}.
}
\tag{EQ-9}
$$

For conventional fuel,

$$
LHV=LHV_f,
$$

while for hydrogen reciprocating propulsion,

$$
LHV=LHV_{H_2}.
$$

The default values are

$$
\eta_{ICE}=0.30,
$$

$$
LHV_f=43~{\rm MJ/kg},
$$

and

$$
LHV_{H_2}=120~{\rm MJ/kg}.
$$

Equation (EQ-9) is a fundamental energy-conversion relation. The numerical technology values should be traced to appropriate engine/fuel-property references or treated as explicit technology assumptions.

---

# 13. Combustion Conversion-Equipment Mass

The ICE core mass is **not** calculated here.

This branch sizes only the accessory conversion-system terms.

### 13.1 Accessory Generator Mass

$$
\boxed{
m_{gen}
=
\frac{P_{aux}}
{SP_g}.
}
\tag{EQ-10}
$$

### 13.2 Fuel-System Mass Allowance

$$
\boxed{
m_{fuel\,sys}
=
k_{fuel}
\frac{P_{br,rated}}{1000}
}
\tag{EQ-11}
$$

where

$$
k_{fuel}=0.01~{\rm kg/kW}
$$

by default.

### 13.3 Total Conversion-System Mass

$$
\boxed{
m_{power}
=
m_{gen}
+
m_{fuel\,sys}
+
m_{accessory,fixed}.
}
\tag{EQ-12}
$$

The default fixed accessory mass is

$$
m_{accessory,fixed}=90~{\rm kg}.
$$

These are conceptual system-sizing assumptions.

---

# 14. Combustion Conversion-System Volume

The combustion accessory-system volume is approximated using a volumetric power density:

$$
\boxed{
V_{power}^{ICE}
=
\frac{P_{br,rated}}
{\Pi_{ICE}},
}
\tag{EQ-13}
$$

with

$$
\Pi_{ICE}=800\,000~{\rm W/m^3}.
$$

This volume is passed to the mass/internal-volume model.

**Classification:** conceptual packaging proxy.

---

# 15. Fuel-Cell Architecture

A standalone Fuel-Cell component is used. Here, shaft power is first converted to electrical-bus demand through Eq. (EQ-2).

The fuel-cell demand is then

$$
\boxed{
P_{FC}=P_{elec}.
}
\tag{EQ-14}
$$

---

## 16. Fuel-Cell Efficiency

The model permits either:

1. a constant fallback efficiency, or
2. a load-dependent efficiency history from `eta_fc_dynamic`.

The fallback value is

$$
\eta_{FC}=0.55.
$$

If dynamic values are available, they replace the fallback on a point-by-point basis.

The implemented efficiency is constrained to

$$
0.05\le\eta_{FC}\le0.75.
$$

Carichner and Nicolai describe hydrogen/oxygen fuel cells as electrochemical converters and report approximately 55% efficiency for the technology data in their Table 5.2, with higher projected values for later technology [1].

Thus the baseline

$$
\eta_{FC}=0.55
$$

has direct historical support from the principal airship reference, although modern or architecture-specific studies may justify different values.

---

# 17. Hydrogen Flow for Fuel Cells

Fuel-cell hydrogen flow follows

$$
\eta_{FC}
=
\frac{P_{FC}}
{\dot m_{H_2}LHV_{H_2}}.
$$

Therefore,

$$
\boxed{
\dot m_{H_2}
=
\frac{P_{FC}}
{\eta_{FC}LHV_{H_2}}.
}
\tag{EQ-15}
$$

This relation is evaluated at every mission point.

Hydrogen **storage mass** is not calculated here. The resulting mission hydrogen requirement is intended for downstream storage/tank sizing.

---

# 18. Fuel-Cell Stack Mass

The rated electrical power required from the fuel-cell source is

$$
P_{FC,rated}.
$$

The stack mass is

$$
\boxed{
m_{FC,stack}
=
\frac{P_{FC,rated}}
{SP_{FC}}.
}
\tag{EQ-16}
$$

The default specific power is

$$
SP_{FC}=700~{\rm W/kg}.
$$

This is a technology assumption.

---

# 19. Fuel-Cell Balance of Plant

The total standalone fuel-cell conversion-system mass is

$$
\boxed{
m_{power}^{FC}
=
m_{FC,stack}
+
m_{BOP}.
}
\tag{EQ-17}
$$

The baseline BOP mass is

$$
m_{BOP}=100~{\rm kg}.
$$

The BOP term conceptually represents supporting equipment such as pumps, compressors, humidification, thermal-management hardware, plumbing, controls, and related auxiliaries.

The single fixed value is a simplified conceptual assumption rather than a universal fuel-cell-system relationship.

---

# 20. Fuel-Cell System Volume

Fuel-cell conversion-system volume is modeled as

$$
\boxed{
V_{power}^{FC}
=
\frac{P_{FC,rated}}
{\Pi_{FC}},
}
\tag{EQ-18}
$$

with default

$$
\Pi_{FC}=500\,000~{\rm W/m^3}.
$$

This is a conceptual packaging relation.

---

# 21. Battery-Only Architecture

For `battery_only`, the Power component calculates electrical demand:

$$
\boxed{
P_{battery}=P_{elec}.
}
\tag{EQ-19}
$$

It sets

$$
\dot m_f=0,
$$

and deliberately returns

$$
m_{power}=0,
\qquad
V_{power}=0
$$

for the battery itself.

Battery capacity, mass, and volume are owned by `BatteryOnly.py`.

This prevents duplicate battery sizing.

---

# 22. Solar Power Availability

For architectures containing solar generation, available photovoltaic power is

$$
\boxed{
P_{solar,avail}
=
G\,A_{PV}\eta_{PV},
}
\tag{EQ-20}
$$

where

- $G$ is solar irradiance,
- $A_{PV}$ is solar-cell area,
- $\eta_{PV}$ is photovoltaic efficiency.

Carichner and Nicolai present the corresponding physical relation

$$
P_{elect}=P_{solar}\eta_{sc}\sin\theta
$$

for a horizontal solar-cell surface, where the sine term accounts for solar elevation and projected area [1].

The ADaPT implementation assumes that the supplied `solar_irradiance` already represents the irradiance appropriate to the installed-array orientation and atmospheric condition. Therefore, no additional incidence-angle term appears inside `Power.py`.

**Classification:** fundamental PV conversion relation with externally supplied irradiance.

---

# 23. Solar Efficiency

The baseline value is

$$
\eta_{PV}=0.22.
$$

Carichner and Nicolai discuss approximately 20% efficiency for single-junction silicon cells and approximately 28% laboratory efficiency for then-current triple-junction cells, with higher projected values [1].

Therefore 22% is physically plausible as a conceptual value, but it should be treated as an explicit technology assumption rather than as a fixed value from the book.

---

# 24. Solar-Battery Power Allocation

For `solar_battery`,

$$
\boxed{
P_{solar,used}
=
\min(P_{solar,avail},P_{elec})
}
\tag{EQ-21}
$$

and

$$
\boxed{
P_{battery}
=
\max(P_{elec}-P_{solar,used},0).
}
\tag{EQ-22}
$$

Thus solar power is used directly whenever available, and the battery supplies the residual electrical demand.

This branch does not size PV or battery mass. Those quantities are owned by `SolarBattery.py`.

---

# 25. Solar Energy Generated

The mission is divided into $N$ equal numerical intervals:

$$
\Delta t
=
\frac{t_m}{N}.
$$

For a power history $P_i$,

$$
\boxed{
E_{\mathrm{Wh}}
=
\frac{
\sum_i P_i\Delta t
}{3600}.
}
\tag{EQ-23}
$$

This rectangular summation is used to compute solar energy generated.

The method assumes equal-duration mission points. If the mission discretization is nonuniform, an explicit time vector or numerical integration against time would be preferable.

---

# 26. Simplified Solar-RFC Architecture

The `solar-RFC` branch is retained for backward compatibility.

It computes

$$
P_{storage}
=
\max(P_{elec}-P_{solar,used},0).
$$

Mission electrical demand and available solar energy are integrated:

$$
E_{req},
\qquad
E_{solar}.
$$

Net storage energy is then

$$
\boxed{
E_{net}
=
\max(E_{req}-E_{solar},10~{\rm Wh}).
}
\tag{EQ-24}
$$

The 10 Wh floor is purely numerical.

---

## 27. Simplified RFC Storage Mass

The RFC storage mass is

$$
\boxed{
m_{RFC}
=
\frac{E_{net}}
{SE_{RFC}},
}
\tag{EQ-25}
$$

where

$$
SE_{RFC}=180~{\rm Wh/kg}.
$$

PV-panel mass is

$$
\boxed{
m_{PV}
=
A_{PV}\sigma_{PV,RFC}.
}
\tag{EQ-26}
$$

The simplified default is

$$
\sigma_{PV,RFC}=0.8~{\rm kg/m^2}.
$$

Total power-system mass is

$$
\boxed{
m_{power}
=
m_{RFC}
+
m_{PV}.
}
\tag{EQ-27}
$$

Carichner and Nicolai explicitly discuss regenerative hydrogen/oxygen fuel cells as solar-energy storage devices and compare RFC and battery specific energy and round-trip efficiency [1].

However, the numerical values used by this simplified branch are not direct copies of the book's Table 5.2 and should be treated as framework-specific simplified technology assumptions.

---

## 28. Simplified RFC Storage Volume

The storage volume is estimated from volumetric energy density:

$$
\boxed{
V_{RFC}
=
\frac{E_{net}}
{\rho_{E,RFC}}
\frac{1}{1000},
}
\tag{EQ-28}
$$

where the factor $1/1000$ converts litres to cubic metres and

$$
\rho_{E,RFC}=500~{\rm Wh/L}.
$$

This is a conceptual storage-volume approximation.

---

# 29. Hybrid Architecture Convention

For hybrid architectures, the component uses a sequential power-allocation convention.

First,

$$
\boxed{
P_{solar}
=
\min(P_{solar,avail},P_{total}).
}
\tag{EQ-29}
$$

Then

$$
\boxed{
P_{rem}
=
P_{total}-P_{solar}.
}
\tag{EQ-30}
$$

The battery receives a fraction $\tau$ of this residual demand:

$$
\boxed{
P_{bat}
=
\tau P_{rem}.
}
\tag{EQ-31}
$$

The primary source supplies

$$
\boxed{
P_{primary}
=
P_{rem}-P_{bat}.
}
\tag{EQ-32}
$$

The parameter is constrained to

$$
0\le\tau\le0.95.
$$

Thus $\tau$ is **not the fraction of total propulsion power supplied by the battery** when solar is present. It is the battery fraction **after direct solar contribution**.

This distinction is essential when interpreting hybridization results.

---

# 30. Hydrogen Hybrid

For `hydrogen_hybrid`,

$$
P_{solar}=0,
$$

$$
P_{bat}=\tau P_{total},
$$

and

$$
P_{FC}=(1-\tau)P_{total}.
$$

Hydrogen flow is

$$
\boxed{
\dot m_{H_2}
=
\frac{P_{FC}}
{\eta_{FC}LHV_{H_2}}.
}
\tag{EQ-33}
$$

Battery power demand is exposed externally for battery sizing.

---

# 31. Solar-Hydrogen Hybrid

For `solar_hydrogen_hybrid`, power is allocated in the order

$$
\boxed{
\text{solar}
\rightarrow
\text{battery}
\rightarrow
\text{fuel cell}.
}
$$

Specifically,

$$
P_{solar}
=
\min(P_{solar,avail},P_{total}),
$$

$$
P_{rem}
=
P_{total}-P_{solar},
$$

$$
P_{bat}
=
\tau P_{rem},
$$

$$
P_{FC}
=
(1-\tau)P_{rem}.
$$

The Power component currently owns PV mass for this architecture because a separate `SolarBattery` component is not instantiated in this path.

---

# 32. Conventional-Battery Hybrid

For `conventional_battery_hybrid`,

$$
P_{solar}=0,
$$

$$
P_{bat}=\tau P_{total},
$$

and

$$
P_{ICE}=(1-\tau)P_{total}.
$$

Fuel flow is

$$
\boxed{
\dot m_f
=
\frac{P_{ICE}}
{\eta_{ICE}LHV_f}.
}
\tag{EQ-34}
$$

Again, the battery mass itself is externally sized.

---

# 33. Rated Hybrid Source Sizing

For fuel-cell hybrids, rated source power is allocated using the rated total electrical demand.

When solar exists, the code first estimates a rated solar contribution,

$$
P_{solar,rated}
=
\min(P_{solar,avail,max},P_{total,rated}),
$$

then

$$
P_{rem,rated}
=
P_{total,rated}-P_{solar,rated}.
$$

The fuel-cell rating is

$$
\boxed{
P_{FC,rated}
=
(1-\tau)P_{rem,rated}.
}
\tag{EQ-35}
$$

For conventional-battery hybrid, the ICE source rating is

$$
\boxed{
P_{ICE,rated}
=
(1-\tau)P_{total,rated}.
}
\tag{EQ-36}
$$

These are architecture-level design conventions.

---

# 34. Hybrid Conversion-System Mass

The hybrid branch sums only the conversion equipment that belongs to the active architecture.

For a fuel-cell path,

$$
m_{FC}
=
\frac{P_{FC,rated}}{SP_{FC}}
+
m_{BOP}.
$$

For a combustion path,

$$
m_{ICE,accessories}
=
m_{gen}
+
m_{fuel\,sys}
+
m_{accessory,fixed}.
$$

For solar-hydrogen hybrid,

$$
m_{PV}
=
A_{PV}\sigma_{PV}.
$$

The total power-system mass is

$$
\boxed{
m_{power}
=
\sum_j m_j.
}
\tag{EQ-37}
$$

Battery mass and hydrogen tank mass remain external.

---

# 35. Hybrid Conversion-System Volume

Similarly,

$$
\boxed{
V_{power}
=
\sum_j V_j
}
\tag{EQ-38}
$$

where the active terms may include

$$
\frac{P_{FC,rated}}{\Pi_{FC}}
$$

or

$$
\frac{P_{ICE,rated}}{\Pi_{ICE}}.
$$

This volume is passed to the mass model and reduces available internal helium volume.

Thus power architecture influences both vehicle mass and buoyant volume.

---

# 36. Actual Power-Fraction Diagnostics

The component reports mean mission power fractions rather than simply echoing the commanded value $\tau$.

For total mean demand

$$
\bar P_{total},
$$

the solar fraction is

$$
\boxed{
f_{solar}
=
\frac{\overline{P_{solar}}}
{\overline{P_{total}}}.
}
\tag{EQ-39}
$$

The battery fraction is

$$
\boxed{
f_{bat}
=
\frac{\overline{P_{bat}}}
{\overline{P_{total}}}.
}
\tag{EQ-40}
$$

The primary-source fraction is

$$
\boxed{
f_{primary}
=
\frac{\overline{P_{primary}}}
{\overline{P_{total}}}.
}
\tag{EQ-41}
$$

These diagnostics are useful because, in solar hybrids,

$$
f_{bat}\ne\tau
$$

in general.

---

# 37. Average Efficiency Output

For standalone combustion architecture,

$$
\eta_{avg}=\eta_{ICE}.
$$

For standalone fuel cell,

$$
\eta_{avg}
=
\overline{\eta_{FC}}.
$$

For battery-only and solar-battery,

$$
\boxed{
\eta_{avg}
=
\eta_m\eta_{inv}.
}
\tag{EQ-42}
$$

For general hybrids, the implementation currently reports the arithmetic mean of the active primary-source efficiency terms.

This quantity is primarily a diagnostic. For mixed architectures it should **not** automatically be interpreted as a rigorous mission energy-weighted system efficiency.

A future improvement would compute

$$
\eta_{\mathrm{mission}}
=
\frac{\int P_{useful}\,dt}
{\int P_{source}\,dt}.
$$

---

# 38. Solar Technology Context

Carichner and Nicolai define photovoltaic power availability in terms of solar irradiance, cell efficiency, and solar incidence geometry. They discuss multijunction solar cells, array packing, electronics efficiency, degradation, and the need to collect excess daytime energy for nighttime operation [1].

Their Solar HALE example illustrates the complete energy-balance problem:

$$
\text{daytime solar collection}
\rightarrow
\text{vehicle load}
+
\text{storage charging}
\rightarrow
\text{nighttime discharge}.
$$

The current `Power.py` performs instantaneous solar allocation but leaves detailed battery sizing to `SolarBattery.py`.

This is consistent with the framework's mass-ownership philosophy.

---

# 39. Fuel-Cell Technology Context

Carichner and Nicolai describe hydrogen/oxygen fuel cells as electrochemical systems converting hydrogen and oxygen into electricity, heat, and water. They also discuss regenerative fuel cells as reversible energy-storage systems for solar-powered airships [1].

The current model separates:

- standalone consuming fuel cell,
- fuel-cell/battery hybrids,
- solar-hydrogen hybrids,
- simplified regenerative fuel-cell storage.

These should not be conflated.

A standalone hydrogen fuel-cell architecture consumes onboard hydrogen continuously, while a regenerative fuel-cell system is conceptually an energy-storage loop involving hydrogen, oxygen, water, electrolysis, and reconversion.

---

# 40. Power-System Outputs

### 40.1 Primary Outputs

| Output | Symbol | Units | Description |
|---|---:|---:|---|
| `fuel_flow` | $\dot m_f$ | kg/s | Fuel or hydrogen mass-flow history |
| `power_system_mass` | $m_{power}$ | kg | Conversion-source mass owned by Power |
| `power_system_volume` | $V_{power}$ | m³ | Conversion-source packaging volume |
| `avg_efficiency` | $\eta_{avg}$ | – | Diagnostic mean efficiency |
| `rated_source_power` | $P_{source,rated}$ | W | Installed source-side power |
| `rated_power_per_unit` | $P_{source,rated}/N_e$ | W | Rated source power per propulsor |

### 40.2 Power-Flow Diagnostics

| Output | Meaning |
|---|---|
| `P_elec_total` | Total electrical or source-equivalent demand |
| `P_ice_demand` | ICE source demand |
| `P_fc_demand` | Fuel-cell demand |
| `P_bat_demand` | Battery demand |
| `P_solar_used` | Solar power directly used |
| `P_solar_available` | Available PV power |
| `solar_energy_generated` | Integrated available solar energy |
| `primary_power_fraction` | Mean primary-source fraction |
| `battery_power_fraction_actual` | Mean actual battery contribution |
| `solar_power_fraction_actual` | Mean actual solar contribution |

### 40.3 Mass Diagnostics

| Output | Meaning |
|---|---|
| `generator_mass` | Accessory generator mass |
| `fuel_system_mass` | Conceptual fuel-system mass |
| `fuel_cell_stack_mass` | Fuel-cell stack mass |
| `pv_mass` | PV-panel mass when owned by this component |

---

# 41. Multidisciplinary Coupling

The Power component closes the central propulsion-energy-mass loop:

$$
\boxed{
\begin{array}{c}
\text{Geometry + Aerodynamics + Mission}\\
\downarrow\\
T_{\mathrm{required}}\\
\downarrow\\
P_{\mathrm{shaft}}\\
\downarrow\\
\text{Power architecture}\\
\downarrow\\
\dot m_f,\;
\dot m_{H_2},\;
P_{bat},\;
P_{FC},\;
P_{solar}\\
\downarrow\\
m_{\mathrm{power}},
m_{\mathrm{battery}},
m_{\mathrm{tank}},
m_{\mathrm{consumable}}\\
\downarrow\\
OEW,\ MTOW,\ V_{\mathrm{He}}\\
\downarrow\\
\text{Geometry + drag + power requirement}\\
\circlearrowleft
\end{array}}
$$

This coupling is architecture-dependent.

A battery system primarily creates a mass penalty.

A hydrogen system creates both:

- hydrogen/tank mass,
- internal storage-volume demand.

Solar systems modify instantaneous source demand but add photovoltaic-system mass and may reduce storage or consumable requirements.

---

# 42. Assumptions and Limitations

| Item | Current treatment | Classification |
|---|---|---|
| Gearbox efficiency | 0.98 | Technology assumption |
| Motor efficiency | 0.95 | Technology assumption |
| Inverter efficiency | 0.98 | Technology assumption |
| ICE thermal efficiency | 0.30 | Technology assumption |
| Fuel-cell efficiency | 0.55 fallback | Literature-supported baseline / technology input |
| Gasoline LHV | 43 MJ/kg | Fuel-property input |
| Hydrogen LHV | 120 MJ/kg | Fuel-property input |
| Generator efficiency | 0.95 fixed internally | Assumption |
| Base auxiliary load | 10 kW | Assumption |
| Vectoring load | 5 kW when active | Assumption |
| ACLS power | 1000 W/m² | Conceptual assumption |
| Pressure-control load | optional user model | Extensibility assumption |
| Generator specific power | 2 kW/kg | Technology assumption |
| Fuel-cell specific power | 0.7 kW/kg | Technology assumption |
| Fuel-cell BOP mass | 100 kg | Conceptual assumption |
| Fuel-cell power density | 500 kW/m³ | Packaging assumption |
| ICE accessory power density | 800 kW/m³ | Packaging assumption |
| Solar efficiency | 22% | Technology assumption |
| PV areal density | 0.50 kg/m² | Technology assumption |
| Hybrid $\tau$ | battery fraction after solar | Framework convention |
| Maximum $\tau$ | 0.95 | Numerical/design bound |
| Equal mission time steps | assumed for energy integration | Numerical assumption |
| Solar incidence | embedded in supplied irradiance | Modeling convention |
| Battery mass | external | Mass ownership |
| Tank mass | external | Mass ownership |
| Prime-mover mass | external | Mass ownership |
| Solar-RFC | simplified branch | Backward compatibility |
| Hybrid `avg_efficiency` | arithmetic mean of active source efficiencies | Diagnostic approximation |

---

# 43. Provenance Classification

The Theory Guide uses:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical relation |
| **L** | Literature-supported relation |
| **A** | Adapted relation |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **C** | Calibration/technology parameter |
| **D** | Derived quantity |
| **N** | Numerical safeguard |

| Equation | Relationship | Classification |
|---|---|---|
| EQ-1 | Combustion brake-power demand | F / A |
| EQ-2 | Electrical-bus demand | F |
| EQ-3–4 | Rated source power | D |
| EQ-5 | Vectoring auxiliary power | AS |
| EQ-6 | ACLS power proxy | AS |
| EQ-7 | Total auxiliary power | D |
| EQ-8 | Pressure-control fallback | AS |
| EQ-9 | Combustion fuel flow | F |
| EQ-10 | Generator mass | A / C |
| EQ-11 | Fuel-system mass | AS / C |
| EQ-12 | Combustion conversion mass | D |
| EQ-13 | Combustion packaging volume | AS / C |
| EQ-14 | FC electrical demand | D |
| EQ-15 | Hydrogen flow | F |
| EQ-16 | FC stack mass | A / C |
| EQ-17 | FC total mass | D |
| EQ-18 | FC system volume | AS / C |
| EQ-19 | Battery demand | D |
| EQ-20 | PV available power | F / L |
| EQ-21–22 | Solar-battery allocation | D |
| EQ-23 | Mission energy integration | D |
| EQ-24 | simplified storage energy | D / N |
| EQ-25–28 | simplified RFC sizing | A / C |
| EQ-29–32 | Hybrid power allocation | D / AS |
| EQ-33 | Hybrid hydrogen flow | F |
| EQ-34 | Hybrid conventional fuel flow | F |
| EQ-35–36 | Hybrid source rating | D / AS |
| EQ-37–38 | Hybrid mass and volume | D |
| EQ-39–41 | Actual power fractions | D |
| EQ-42 | Electric diagnostic efficiency | D |

---

# 44. Important Documentation Notes

## 44.1 `P_elec_total` naming

For combustion architectures, `P_elec_total` is currently assigned the brake-power demand even though the quantity is not literally an electrical bus power.

Therefore, this output should be interpreted more generally as an **equivalent total source-side demand diagnostic** in those architectures.

A future code cleanup could rename it to something like

```text
P_source_total
```

while maintaining a simplified alias.

## 44.2 `avg_efficiency` in hybrids

The hybrid branch reports a simple mean of active source efficiency values, not an energy-weighted overall efficiency.

This is useful diagnostically but should not be used directly as a thermodynamic system efficiency without further processing.

## 44.3 Solar-energy integration

The energy calculation uses

$$
\Delta t=t_m/N
$$

and equal numerical spacing.

If mission nodes correspond to unequal phase durations, Eq. (EQ-23) should be replaced by explicit time integration.

## 44.4 Solar availability versus solar use

The code distinguishes

$$
P_{solar,avail}
$$

from

$$
P_{solar,used}.
$$

This is important because available solar power may exceed instantaneous aircraft demand.

The current model does not automatically route all excess solar energy into battery charging in the generic instantaneous allocation branch. Detailed storage charging behavior belongs in the dedicated solar/battery model.

---

# 45. Numerical Safeguards

The component applies numerous limits, including:

$$
0.10\le\eta_g\le1,
$$

$$
0.10\le\eta_m\le1,
$$

$$
0.10\le\eta_{inv}\le1,
$$

$$
0.05\le\eta_{ICE}\le0.70,
$$

$$
0.05\le\eta_{FC}\le0.75,
$$

$$
0\le\eta_{PV}\le1,
$$

$$
0\le\tau\le0.95.
$$

Fuel lower heating values and specific powers are protected against zero or negative values.

These are numerical robustness measures, not certification limits.

---

# 46. Derivatives

The Power component currently declares finite-difference derivatives:

```python
self.declare_partials("*", "*", method="fd", step=1e-8)
```

so

$$
\Delta x=10^{-8}.
$$

The architecture logic contains many nonsmooth operations, including:

- `max`,
- `min`,
- `clip`,
- source switching,
- architecture branching,
- solar saturation,
- hybrid saturation,
- fallback/dynamic fuel-cell efficiency switching.

These features should be considered when using gradient-based optimization.

---

# 47. Verification Recommendations

## 47.1 Power-Chain Verification

For a known shaft-power demand, independently verify:

$$
P_{br},
\qquad
P_{elec},
\qquad
P_{source,rated}.
$$

## 47.2 Fuel-Flow Verification

For known power, efficiency, and LHV, independently verify:

$$
\dot m
=
\frac{P}{\eta LHV}
$$

for:

- conventional fuel,
- hydrogen combustion,
- hydrogen fuel cell.

## 47.3 Solar Verification

For specified irradiance, area, and efficiency, verify

$$
P_{solar}=GA\eta.
$$

Then verify the saturation condition

$$
P_{solar,used}
=
\min(P_{solar,avail},P_{load}).
$$

## 47.4 Hybrid Verification

For a simple constant-load case, verify exactly:

$$
P_{solar},
\quad
P_{rem},
\quad
P_{bat},
\quad
P_{primary}.
$$

Check that

$$
P_{solar}+P_{bat}+P_{primary}=P_{total}
$$

to numerical tolerance.





# 48. Recommended Future Refinements

Recommended improvements include:

1. Replace fixed auxiliary-power assumptions with subsystem-resolved load models.
2. Trace gasoline and hydrogen LHV values to the case-study-based thermochemical property source.
3. Replace constant ICE efficiency with engine maps or BSFC-dependent operation if higher fidelity is needed.
4. Couple the dynamic PEMFC efficiency model directly as the standard fuel-cell path.
5. Replace fixed BOP mass with power-dependent compressor, cooling, humidification, and control-system models.
6. Replace the single fuel-cell volumetric power density with component-level packaging.
7. Move the simplified `solar-RFC` sizing into a dedicated RFC component.
8. Use explicit mission time histories for all energy integrations.
9. Model excess solar charging explicitly instead of only instantaneous direct use.
10. Include battery charge/discharge efficiencies in hybrid dispatch when the battery model is coupled.
11. Replace the arithmetic hybrid average efficiency with an energy-weighted metric.
12. Add source power limits and state-dependent dispatch constraints.
13. Add power-management optimization rather than prescribing $\tau$.
14. Provide analytic or complex-step-compatible derivatives for smooth portions of the model.

---

# 49. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.

Relevant material includes:

- Chapter 5 — Propulsion,
- electric motors,
- solar power,
- regenerative fuel cells,
- rechargeable batteries,
- solar-powered airship subsystem sizing,
- Chapter 9 — Subsystems and Weights.

Important source-supported relationships and concepts include:

$$
P_{elect}
=
P_{solar}\eta_{sc}\sin\theta
$$

for solar-cell output,

the approximately 55% fuel-cell efficiency presented in the source's electric-airship technology table,

the distinction between direct electric propulsion and stored energy,

and the diurnal energy-balance approach for solar-powered airships.

```{note}
Power.py is an architecture-allocation and source-conversion component. Separate owners (components) are there for all propulsion-energy masses. Battery mass, hydrogen storage, and prime-mover mass are intentionally delegated to their dedicated components.
```

```{warning}
Several numerical technology values in this component are design assumptions rather than values taken directly from Carichner and Nicolai. These include auxiliary power, generator specific power, fuel-cell specific power, BOP mass, volumetric power densities, and several simplified RFC parameters. They should remain identified as assumptions until separately sourced or calibrated. That is why Fuel-Cell architectures are not studied in the paper for now.
```
