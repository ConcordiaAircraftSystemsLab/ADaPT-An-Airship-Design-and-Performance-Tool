# Energy Storage, Fuel-Cell, Solar-Electric, and Hydrogen-Storage Models

This Theory Guide page documents four tightly coupled energy-system components in ADaPT:

- `BatteryOnly`
- `SolarBattery`
- `FuelCellPolarization`
- `Tank`

These components sit downstream of the propulsion/power-allocation models and provide the detailed storage, electrochemical, photovoltaic, and hydrogen-inventory calculations required by the alternative-propulsion architectures.

Their responsibilities are deliberately separated:

$$
\boxed{
\text{Power demand}
\rightarrow
\begin{cases}
\text{BatteryOnly}\\
\text{SolarBattery}\\
\text{FuelCellPolarization}
\end{cases}
\rightarrow
\text{Tank, where H}_2\text{ is used}
\rightarrow
\text{Weight}
}
$$

The separation is important for mass ownership and prevents double counting of batteries, fuel-cell stacks, hydrogen, or tank hardware.

---

# 1. Architecture and Responsibility Map

## 1.1 BatteryOnly

`BatteryOnly` is the authoritative owner of:

- installed battery capacity,
- battery mass,
- battery volume,
- usable installed battery energy,
- conceptual series/parallel pack configuration.

It receives electrical power demand and does not calculate propulsion demand, hydrogen, fuel-cell mass, photovoltaic mass, or MTOW.

## 1.2 SolarBattery

`SolarBattery` is the authoritative owner of:

- photovoltaic power and energy generation,
- battery capacity for solar-battery architectures,
- battery mass and volume,
- PV-panel mass and volume,
- combined PV-battery system mass and volume,
- solar contribution diagnostics.

## 1.3 FuelCellPolarization

`FuelCellPolarization` provides the detailed load-dependent PEM fuel-cell operating model.

It calculates:

- reversible cell voltage,
- activation loss,
- ohmic loss,
- concentration loss,
- operating current density,
- operating cell voltage,
- electrical efficiency,
- hydrogen-consumption diagnostics,
- stack maximum power,
- requested-power shortfall.

It does **not** size stack mass. `Power.py` retains ownership of fuel-cell stack mass through the `fuel_cell_specific_power` model.

## 1.4 Tank

`Tank` is the authoritative owner of:

- mission hydrogen inventory,
- reserve hydrogen,
- total installed hydrogen mass,
- internal hydrogen volume,
- external insulated tank volume,
- vessel/structural mass,
- insulation mass,
- delivery-system mass,
- total empty EQ-system mass,
- hydrogen chemical-energy diagnostics.

---

# Part I — Battery-Only Energy Storage

# 2. Battery Mission Energy

The electrical mission demand is supplied as a discrete power history

$$
P_i.
$$

The current model assumes equally spaced mission points:

$$
\boxed{
\Delta t
=
\frac{t_m}{N}
}
\tag{EQ-1}
$$

where

- $t_m$ is total mission duration,
- $N$ is the number of mission points.

Mission electrical energy is

$$
\boxed{
E_{\mathrm{load}}
=
\frac{
\sum_{i=1}^{N} P_i\Delta t
}{3600}
}
\tag{EQ-2}
$$

with $E_{\mathrm{load}}$ expressed in Wh.

This is a rectangular numerical integration.

A future model with nonuniform mission time steps should integrate using the actual time vector rather than assuming equal spacing.

---

### Source and rationale for the mission-time discretization

- **Equal time increment, \(\Delta t=t_m/N\) [D/AS]:** This is a numerical quadrature assumption, not a physical coefficient. It is appropriate when the upstream mission is represented by \(N\) uniformly spaced time nodes. The resulting energy estimate is the rectangular-rule integration \(E\approx\sum_i P_i\Delta t\). If mission nodes are not equally spaced in time, the correct node-specific \(\Delta t_i\) should be passed instead.
- **Why retained:** The formulation is transparent, inexpensive, differentiable almost everywhere, and appropriate for conceptual MDAO. It should not be interpreted as a literature-mandated mission discretization.

**Source basis:** standard numerical integration practice; no aircraft-specific calibration is implied.

# 3. Battery Technology Inputs

| Input | Symbol | Default | Units | Meaning |
|---|---:|---:|---:|---|
| `battery_specific_energy` | $SE_{cell}$ | 250 | Wh/kg | Cell-level gravimetric specific energy |
| `battery_volumetric_ed` | $VE_{cell}$ | 600 | Wh/L | Cell-level volumetric energy density |
| `battery_pack_voltage` | $V_{pack}$ | 400 | V | Nominal pack voltage |
| `battery_cell_voltage_nom` | $V_{cell}$ | 3.7 | V | Nominal cell voltage |
| `depth_of_discharge` | DoD | 0.80 | – | Allowed usable depth of discharge |
| `battery_efficiency` | $\eta_b$ | 0.95 | – | Battery energy efficiency |
| `battery_packaging_factor` | $f_{pack}$ | 0.72 | – | Cell-to-pack mass/volume efficiency |

The packaging factor accounts conceptually for:

- battery-management system,
- cooling hardware,
- structural enclosure,
- interconnects,
- packaging overhead.

These parameters are technology assumptions, not universal battery constants.

---

### Source and rationale for the battery defaults

The battery defaults are intended as a **contemporary high-energy Li-ion conceptual-design baseline**, not as immutable chemistry constants.

- **\(SE_{cell}=250~\mathrm{Wh/kg}\) [L/C]:** Representative of high-energy commercial cylindrical Li-ion cells. For example, the Panasonic/SANYO NCR18650B is specified near \(243~\mathrm{Wh/kg}\); NASA aerospace-electric design studies also use cell/pack values in the \(200\)–\(250+\ \mathrm{Wh/kg}\) range. The ADaPT value is therefore a rounded high-energy cell-level baseline. It should be varied in technology-sensitivity studies rather than treated as a universal pack value.
- **\(VE_{cell}=600~\mathrm{Wh/L}\) [L/C]:** The same class of high-energy cells reaches roughly \(600\)–\(680~\mathrm{Wh/L}\). The selected value is a conservative rounded cell-level volumetric-energy-density baseline.
- **\(V_{pack}=400~\mathrm{V}\) [L/AS]:** A 400-V-class DC bus is widely used in conceptual electrified-aircraft testbeds and studies. NASA distributed-electric-propulsion studies have used 400-V-class buses, while other demonstrators use somewhat higher voltages. Hence 400 V is a representative system-architecture choice rather than a universal aircraft standard.
- **\(V_{cell}=3.7~\mathrm{V}\) [L]:** Representative rounded nominal voltage of NMC/NCA-type Li-ion cells, whose data sheets commonly list approximately \(3.6\)–\(3.7\) V nominal.
- **\(\mathrm{DoD}=0.80\) [L/AS]:** An 80% usable depth of discharge is a common conceptual-design assumption that preserves reserve capacity and reduces operation near electrochemical limits. NASA sizing studies have explicitly used 80% DoD for Li-ion packs. The correct value is mission- and cycle-life-dependent.
- **\(\eta_b=0.95\) [L/A]:** Carichner & Nicolai use a baseline battery round-trip efficiency of about 0.90 before transmission/switching losses in the solar-HALE example. If charge and discharge efficiencies are treated symmetrically, \(\sqrt{0.90}=0.949\), providing a direct rationale for a one-way efficiency of approximately 0.95. Modern Li-ion system studies also report high electrochemical efficiency in this range.
- **\(f_{pack}=0.72\) [C/AS]:** This converts cell-level energy density to installed-pack level by accounting for enclosure, bus bars, BMS, contactors, thermal management, wiring, and structural protection. \(250\times0.72=180~\mathrm{Wh/kg}\), which is deliberately more conservative than cell-level performance. Aerospace studies often apply approximately 25–30% installation/BMS overhead; \(f_{pack}=0.72\) corresponds to a somewhat stronger \(\sim39\%\) mass overhead relative to bare cells, appropriate for conservative conceptual sizing.

**Primary references:** Carichner & Nicolai [1], Chapter 5/Table 5.2 and Sample Problem 5.3; Panasonic/SANYO NCR18650B data sheet [3]; NASA electrified-aircraft battery sizing studies [4,5].

# 4. Battery Temperature Derating

The model uses the average ambient mission temperature

$$
\bar T
=
\frac{1}{N}\sum_i T_i.
$$

The absolute deviation from the reference temperature is

$$
\Delta T
=
\left|
\bar T-T_{ref}
\right|.
$$

The temperature factor is

$$
\boxed{
f_T
=
\operatorname{clip}
\left[
1-k_T\Delta T,
f_{T,\min},
1
\right]
}
\tag{EQ-3}
$$

with default values

$$
T_{ref}=298.15~{\rm K},
$$

$$
k_T=0.003~{\rm K^{-1}},
$$

and

$$
f_{T,\min}=0.60.
$$

This is a **conceptual derating model**. It does not represent a detailed electrochemical battery-temperature model.

---

### Source and rationale for thermal derating

- **\(T_{ref}=298.15~\mathrm{K}\) [AS]:** \(25^\circ\mathrm{C}\) is the standard room-temperature reference used in many battery data sheets and laboratory characterizations.
- **\(k_T=0.003~\mathrm{K^{-1}}\) [RO/AS]:** This is a **reduced-order sensitivity coefficient**, not a universal Li-ion property. Real battery power/energy capability depends nonlinearly on temperature, chemistry, SOC, C-rate, and thermal history. The value provides a mild first-order penalty for departure from room temperature while retaining a simple differentiable model.
- **\(f_{T,\min}=0.60\) [AS/N]:** A lower bound prevents the reduced-order correction from driving usable energy to zero or negative values outside its intended temperature range. It represents a conservative minimum retained capability, not a chemistry-specific experimentally fitted threshold.

**Why this form is acceptable at conceptual fidelity:** NASA and manufacturer literature consistently show pronounced loss of Li-ion capability at low temperature and increased thermal constraints at high temperature, but no single linear coefficient is transferable across chemistries. Therefore the current \(k_T\) and floor are explicitly model assumptions and should be replaced by chemistry-specific maps when detailed battery data are available.

# 5. Usable Battery Fraction

The fraction of installed battery capacity considered deliverable over the mission is

$$
\boxed{
f_{\mathrm{usable}}
=
\eta_b
\,
DoD
\,
f_T.
}
\tag{EQ-4}
$$

Therefore the required installed battery capacity is

$$
\boxed{
E_{\mathrm{capacity}}
=
\frac{
E_{\mathrm{load}}
}{
\eta_b\,DoD\,f_T
}.
}
\tag{EQ-5}
$$

This is the central battery-sizing relationship.

---

# 6. Pack-Level Specific Energy

The model converts cell-level performance into effective installed-pack performance using the packaging factor:

$$
\boxed{
SE_{pack}
=
SE_{cell}f_{pack}
}
\tag{EQ-6}
$$

and

$$
\boxed{
VE_{pack}
=
VE_{cell}f_{pack}.
}
\tag{EQ-7}
$$

This is an intentionally simple representation of pack integration losses.

---

# 7. Battery Mass

The installed battery mass is

$$
\boxed{
m_b
=
\frac{
E_{\mathrm{capacity}}
}{
SE_{pack}
}
}
\tag{EQ-8}
$$

or equivalently,

$$
m_b
=
\frac{
E_{\mathrm{capacity}}
}{
SE_{cell}f_{pack}
}.
$$

---

# 8. Battery Volume

The pack volume in litres is

$$
V_{b,L}
=
\frac{
E_{\mathrm{capacity}}
}{
VE_{pack}
}.
$$

Therefore,

$$
\boxed{
V_b
=
\frac{1}{1000}
\frac{
E_{\mathrm{capacity}}
}{
VE_{pack}
}
}
\tag{EQ-9}
$$

with $V_b$ in cubic metres.

---

# 9. Usable Installed Battery Energy

The deliverable mission energy from the installed pack is

$$
\boxed{
E_{\mathrm{usable}}
=
E_{\mathrm{capacity}}
\eta_b
DoD
f_T.
}
\tag{EQ-10}
$$

For a correctly sized battery-only case,

$$
E_{\mathrm{usable}}
\approx
E_{\mathrm{load}}.
$$

This output is particularly useful in coupled mission-energy consistency checks.

---

# 10. Conceptual Battery Series Count

The number of series cells is estimated as

$$
\boxed{
N_s
=
\max
\left[
1,
\left\lceil
\frac{V_{pack}}{V_{cell}}
\right\rceil
\right].
}
\tag{EQ-11}
$$

This is a conceptual electrical configuration only.

The model does not presently calculate an individual cell energy capacity or derive total cell count from both energy and power simultaneously.

---

# 11. Conceptual Parallel Count

The peak battery power is

$$
P_{b,\max}
=
\max_i P_i.
$$

The model assumes a conservative operating pack voltage

$$
\boxed{
V_{pack,cons}
=
0.85V_{pack}.
}
\tag{EQ-12}
$$

Peak current is

$$
\boxed{
I_{peak}
=
\frac{
P_{b,\max}
}{
0.85V_{pack}
}.
}
\tag{EQ-13}
$$

With a default continuous-current capability of

$$
I_{string}=10~{\rm A},
$$

the parallel count is

$$
\boxed{
N_p
=
\max
\left[
1,
\left\lceil
\frac{I_{peak}}{I_{string}}
\right\rceil
\right].
}
\tag{EQ-14}
$$

The 10 A/string value and 0.85 voltage factor are implementation assumptions.

---

### Source and rationale for electrical-sizing margins

- **\(I_{string}=10~\mathrm{A}\) [L/C]:** This is representative of the maximum continuous-current capability of high-energy 18650-class cells; for example, LG Chem MJ1-class cells are rated around 10 A. It is used here as a convenient high-energy-cell current baseline, not as a universal cell current limit.
- **\(0.85V_{pack}\) [AS]:** The 15% voltage margin represents loaded/end-of-discharge voltage sag and preserves current capability when the pack is below nominal open-circuit voltage. It is intentionally conservative and should be replaced by a cell-specific minimum-voltage/SOC model when detailed electrochemical data are available.
- **Interpretation:** these two quantities are **electrical architecture assumptions** used to estimate parallel-string count; they do not modify the mission-energy requirement itself.

**Reference basis:** representative high-energy Li-ion cell data sheets [3] and aerospace battery-pack design practice [4].

# 12. BatteryOnly Outputs

| Output | Meaning |
|---|---|
| `battery_capacity` | Required installed energy capacity |
| `battery_mass` | Installed battery mass |
| `battery_volume` | Installed battery volume |
| `power_system_mass` | Compatibility alias of battery mass |
| `power_system_volume` | Compatibility alias of battery volume |
| `mission_electrical_energy` | Integrated mission load |
| `usable_battery_energy` | Mission-deliverable battery energy |
| `energy_consumption` | Battery power-demand history |
| `n_series` | Conceptual series-cell count |
| `n_parallel` | Conceptual parallel-string count |
| `avg_efficiency` | $\eta_b f_T$ |
| `temperature_factor` | Battery temperature derating |
| `peak_battery_power` | Peak electrical battery demand |
| `pack_specific_energy` | Effective installed gravimetric energy density |
| `pack_volumetric_energy_density` | Effective installed volumetric energy density |

---

# Part II — Solar-Battery System

# 13. SolarBattery Scope

`SolarBattery` extends the battery-only formulation by explicitly calculating photovoltaic generation and using direct solar energy to offset mission electrical demand before sizing the battery.

The principal energy flow is

$$
\boxed{
P_{\mathrm{load}}
\rightarrow
P_{\mathrm{solar,used}}
+
P_{\mathrm{battery}}.
}
$$

The component also owns both PV and battery mass for the standard solar-battery architecture.

---

# 14. Temperature-Dependent PV Efficiency

The reference photovoltaic efficiency is

$$
\eta_{PV,ref}.
$$

The temperature-adjusted efficiency is

$$
\boxed{
\eta_{PV}(T)
=
\operatorname{clip}
\left[
\eta_{PV,ref}
\left(
1+k_{PV}(T-T_{PV,ref})
\right),
0,
1
\right].
}
\tag{EQ-1}
$$

The defaults are

$$
\eta_{PV,ref}=0.22,
$$

$$
k_{PV}=-0.003~{\rm K^{-1}},
$$

and

$$
T_{PV,ref}=298.15~{\rm K}.
$$

This is a linear temperature correction rather than a full photovoltaic performance model.

---

### Source and rationale for photovoltaic defaults

- **\(\eta_{PV,ref}=0.22\) [L/C]:** A 22% reference efficiency is representative of high-efficiency commercial monocrystalline-silicon modules/cells at standard test conditions. NREL technology surveys report commercial crystalline-silicon module efficiencies reaching approximately this level. This is intentionally different from the Carichner & Nicolai HALE example, which assumes much more expensive multijunction cells at 32% cell efficiency.
- **\(k_{PV}=-0.003~\mathrm{K^{-1}}\) [L]:** Equivalent to a \(-0.3\%\)/K power-temperature coefficient, within the typical range reported by NREL for high-efficiency crystalline-silicon PV technologies.
- **\(T_{PV,ref}=298.15~\mathrm{K}\) [L/AS]:** \(25^\circ\mathrm{C}\) is the conventional photovoltaic standard-test-condition reference temperature.
- **Why retained:** ADaPT uses silicon-like PV as the general baseline while allowing technology studies to replace \(\eta_{PV,ref}\) with multijunction or thin-film values. Carichner & Nicolai remain important for the **airship-level solar-energy architecture and diurnal balance**, not for forcing their historical 32% multijunction choice onto every modern study.

**References:** Carichner & Nicolai [1], Chapter 5; NREL photovoltaic technology benchmarking [6].

# 15. Available Photovoltaic Power

At mission point $i$,

$$
\boxed{
P_{PV,i}
=
G_i A_{PV}\eta_{PV,i}
}
\tag{EQ-2}
$$

where

- $G_i$ is incident solar irradiance,
- $A_{PV}$ is installed solar area.

Carichner and Nicolai use the corresponding physical form

$$
P_{elect}
=
P_{solar}\eta_{sc}\sin\theta
$$

for horizontal solar collectors, where the incidence geometry appears explicitly.

In ADaPT, the supplied irradiance is assumed to already represent the appropriate incident irradiance for the modeled surface/orientation, so no separate incidence-angle factor is applied inside `SolarBattery`.

---

# 16. External Solar-Energy Override

The model permits an externally supplied total solar energy input

$$
E_{\mathrm{solar,ext}}.
$$

If this value is greater than zero, it overrides the internally integrated irradiance calculation.

The supplied value in MJ is converted to Wh:

$$
\boxed{
E_{\mathrm{solar}}
=
E_{\mathrm{solar,ext}}
\frac{10^6}{3600}.
}
\tag{EQ-3}
$$

The equivalent average solar power is then

$$
\boxed{
\bar P_{\mathrm{solar}}
=
\frac{
E_{\mathrm{solar}}3600
}{
t_m
}.
}
\tag{EQ-4}
$$

This equivalent constant power is distributed across mission nodes.

This option is a useful coupling interface for an external solar-resource model.

---

# 17. Solar Power Used

Instantaneous directly usable solar power is

$$
\boxed{
P_{\mathrm{solar,used},i}
=
\min
\left(
P_{PV,i},
P_{\mathrm{load},i}
\right).
}
\tag{EQ-5}
$$

Battery demand is

$$
\boxed{
P_{b,i}
=
\max
\left(
P_{\mathrm{load},i}
-
P_{\mathrm{solar,used},i},
0
\right).
}
\tag{EQ-6}
$$

Thus solar generation is prioritized before battery discharge.

---

# 18. Solar Energy Accounting

Generated solar energy is

$$
\boxed{
E_{\mathrm{solar,gen}}
=
\frac{
\sum_iP_{PV,i}\Delta t
}{3600}.
}
\tag{EQ-7}
$$

Directly used solar energy is

$$
\boxed{
E_{\mathrm{solar,used}}
=
\frac{
\sum_iP_{\mathrm{solar,used},i}\Delta t
}{3600}.
}
\tag{EQ-8}
$$

It is additionally constrained so that

$$
E_{\mathrm{solar,used}}
\le
E_{\mathrm{load}}.
$$

Excess solar energy is

$$
\boxed{
E_{\mathrm{solar,excess}}
=
\max
\left(
E_{\mathrm{solar,gen}}
-
E_{\mathrm{solar,used}},
0
\right).
}
\tag{EQ-9}
$$

The current model does **not** automatically credit excess solar generation as battery charging energy unless it is directly represented in the supplied mission energy balance.

That distinction is important.

---

# 19. Net Battery Energy in SolarBattery

Battery-delivered mission energy is

$$
\boxed{
E_{b,\mathrm{delivered}}
=
\max
\left(
E_{\mathrm{load}}
-
E_{\mathrm{solar,used}},
0
\right).
}
\tag{EQ-10}
$$

The required installed battery capacity is

$$
\boxed{
E_{\mathrm{capacity}}
=
\max
\left[
\frac{
E_{b,\mathrm{delivered}}
}{
\eta_bDoDf_{T,b}
},
E_{\mathrm{capacity,min}}
\right].
}
\tag{EQ-11}
$$

The minimum default capacity is

$$
E_{\mathrm{capacity,min}}=10~{\rm Wh}.
$$

This is a numerical floor rather than a physical battery-sizing requirement.

---

# 20. Solar-Battery Pack Mass and Volume

Battery mass remains

$$
\boxed{
m_b
=
\frac{
E_{\mathrm{capacity}}
}{
SE_{cell}f_{pack}
}.
}
\tag{EQ-12}
$$

Battery volume remains

$$
\boxed{
V_b
=
\frac{1}{1000}
\frac{
E_{\mathrm{capacity}}
}{
VE_{cell}f_{pack}
}.
}
\tag{EQ-13}
$$

---

# 21. PV Mass

The installed photovoltaic mass is

$$
\boxed{
m_{PV}
=
A_{PV}\sigma_{PV}.
}
\tag{EQ-14}
$$

The default areal density is

$$
\sigma_{PV}=0.50~{\rm kg/m^2}.
$$

Carichner and Nicolai use areal mass relationships for installed solar cells in their Solar HALE example, but the current 0.50 kg/m² value should be treated as a framework technology assumption unless a direct contemporary source is cited.

---

### Source and rationale for PV areal density

- **\(\sigma_{PV}=0.50~\mathrm{kg/m^2}\) [L/C]:** This value has unusually strong support from the airship-design reference itself. Carichner & Nicolai Table 5.2 list an installed solar-cell weight of approximately \(0.1~\mathrm{lb/ft^2}\), which converts to about \(0.488~\mathrm{kg/m^2}\). The ADaPT default \(0.50~\mathrm{kg/m^2}\) is therefore essentially the rounded book value.
- Lightweight aerospace flexible-array demonstrations also report blanket/system areal densities of the same order, depending on substrate, deployment hardware, encapsulation, and wiring.
- **Interpretation:** the coefficient represents **installed array areal mass**, not bare semiconductor-cell density.

**References:** Carichner & Nicolai [1], Table 5.2; NASA lightweight/deployable aerospace PV-array studies [7].

# 22. PV Volume

PV volume is estimated as

$$
\boxed{
V_{PV}
=
A_{PV}t_{PV}.
}
\tag{EQ-15}
$$

The default conceptual panel thickness is

$$
t_{PV}=0.001~{\rm m}.
$$

This is a simple packaging proxy.

---

### Source and rationale for PV thickness

- **\(t_{PV}=0.001~\mathrm{m}\) [AS]:** The 1-mm value is a geometric/packaging proxy for a flexible encapsulated PV laminate. It is **not** intended as the physical silicon-junction thickness and is not used to infer PV mass, because mass is independently determined from \(\sigma_{PV}\).
- **Why retained:** the thickness is useful only when a downstream geometry/volume model requires a finite installed layer. It should be replaced by the actual laminate stack thickness for a selected PV technology.

This value is therefore an explicit design assumption rather than a literature-derived universal constant.

# 23. Combined Solar-Battery System

Total installed mass is

$$
\boxed{
m_{\mathrm{PV+battery}}
=
m_b+m_{PV}.
}
\tag{EQ-16}
$$

Total volume is

$$
\boxed{
V_{\mathrm{PV+battery}}
=
V_b+V_{PV}.
}
\tag{EQ-17}
$$

The mission solar fraction is

$$
\boxed{
f_{\mathrm{solar}}
=
\frac{
E_{\mathrm{solar,used}}
}{
E_{\mathrm{load}}
}.
}
\tag{EQ-18}
$$

---

# 24. SolarBattery Outputs

| Output | Meaning |
|---|---|
| `battery_capacity` | Installed battery capacity |
| `battery_mass` | Battery mass |
| `battery_volume` | Battery volume |
| `pv_mass` | PV-system mass |
| `pv_volume` | PV-system volume |
| `power_system_mass` | Battery + PV mass |
| `power_system_volume` | Battery + PV volume |
| `mission_load_energy` | Mission electrical load |
| `mission_electrical_energy` | Compatibility alias |
| `solar_energy_generated` | Total solar energy generated |
| `solar_energy_used` | Directly useful solar energy |
| `excess_solar_energy` | Generated but not directly used |
| `net_battery_energy` | Energy delivered by battery |
| `usable_battery_energy` | Deliverable battery energy |
| `solar_fraction` | Mission energy fraction offset by solar |
| `average_pv_efficiency` | Mean temperature-adjusted PV efficiency |
| `battery_temperature_factor` | Battery temperature derating |
| `pv_power_available` | Solar power availability history |
| `pv_power_used` | Directly used solar history |
| `battery_power_demand` | Residual battery demand |

---

# Part III — PEM Fuel-Cell Polarization Model

# 25. FuelCellPolarization Scope

The fuel-cell polarization component replaces a single fixed fuel-cell efficiency with a load-dependent semi-empirical PEM model.

At every mission point it solves

$$
P_{\mathrm{requested}}
\rightarrow
i_{\mathrm{op}}
\rightarrow
V_{\mathrm{cell}}
\rightarrow
P_{\mathrm{available}}
\rightarrow
\eta_{FC}.
$$

The model includes:

- reversible/Nernst voltage,
- activation polarization,
- ohmic polarization,
- concentration polarization,
- current-density limits,
- stack power capability,
- hydrogen-consumption diagnostics.

It does not size fuel-cell stack mass; that mass remains in `Power.py`.

---

# 26. Reversible Cell Voltage

The standard electrochemical potential used by the implementation is

$$
\boxed{
E^0(T)
=
-\frac{\Delta H}{nF}
+
\frac{T\Delta S}{nF}.
}
\tag{EQ-1}
$$

The current constants are

$$
\Delta H=-241\,820~{\rm J/mol},
$$

$$
\Delta S=-44.43~{\rm J/(mol\,K)},
$$

$$
n=2,
$$

$$
F=96\,485~{\rm C/mol}.
$$

The simplified Nernst correction is

$$
\boxed{
E_N
=
E^0(T)
+
\frac{RT}{nF}
\ln
\left(
\frac{
p_{H_2}p_{O_2}^{1/2}
}{
p_{H_2O}
}
\right).
}
\tag{EQ-2}
$$

This is a fundamental electrochemical relationship in simplified PEMFC form.

---

### Thermochemical source basis

For the reaction

\[
\mathrm{H_2+\frac12O_2\rightarrow H_2O(g)},
\]

the adopted values are standard-state thermochemical properties:

- **\(\Delta H=-241{,}820~\mathrm{J/mol}\) [F/L]:** Standard enthalpy of formation/reaction for water vapor, i.e. the **LHV/gaseous-water basis**.
- **\(\Delta S=-44.43~\mathrm{J/(mol\,K)}\) [F/L]:** Obtained from standard molar entropies:
  \[
  S^\circ_{\mathrm{H_2O(g)}}-
  S^\circ_{\mathrm{H_2}}-
  \tfrac12S^\circ_{\mathrm{O_2}}
  \approx-44.42~\mathrm{J/(mol\,K)}.
  \]
- **\(n=2\) [F]:** Two electrons are transferred per mole of hydrogen oxidized.
- **\(F=96{,}485~\mathrm{C/mol}\) [F]:** Faraday constant, rounded from the CODATA value.

These values are appropriate for the simplified Nernst/open-circuit-voltage model on an LHV/gaseous-water reaction basis.

**References:** NIST Chemistry WebBook / NIST-JANAF thermochemical tables [8]; O'Hayre et al. [9].

# 27. Activation Loss

The activation loss is modeled as

$$
\boxed{
V_{\mathrm{act}}
=
\frac{RT}{\alpha F}
\ln
\left(
\frac{
i+i_{\mathrm{loss}}
}{
i_0
}
\right).
}
\tag{EQ-3}
$$

where

- $i$ is operating current density,
- $i_0$ is exchange current density,
- $i_{\mathrm{loss}}$ is parasitic current density,
- $\alpha$ is the transfer coefficient.

The baseline values are

$$
i_0=3\times10^{-6}~{\rm A/cm^2},
$$

$$
i_{\mathrm{loss}}=0.002~{\rm A/cm^2},
$$

and

$$
\alpha=1.0.
$$

These are semi-empirical PEMFC parameters.

---

### Source and rationale for activation-loss parameters

- **\(i_0=3\times10^{-6}~\mathrm{A/cm^2}\) [L/E]:** This magnitude is representative of semi-empirical PEMFC cathode exchange-current-density values used in published polarization models. A published PEMFC numerical study by Arear, Zeiny & Al-Baghdadi uses the same \(3\times10^{-6}~\mathrm{A/cm^2}\) order/value for the cathode baseline.
- **\(i_{loss}=0.002~\mathrm{A/cm^2}\) [L/A]:** Interpreted as an effective crossover/parasitic-current correction. DOE PEM membrane targets use hydrogen/oxygen crossover currents of order a few mA/cm², supporting the magnitude. It is not a universal stack leakage current.
- **\(\alpha=1.0\) [A/C]:** An **effective Tafel coefficient** for the single-slope reduced-order activation model. It should not be interpreted as a literal elementary charge-transfer coefficient for every electrode reaction. Published simplified PEMFC models commonly use effective values of order unity.

These parameters are deliberately exposed as inputs because activation behavior is catalyst, pressure, humidity, temperature, and MEA dependent.

**References:** Larminie & Dicks [10]; Barbir [11]; Arear et al. [12]; U.S. DOE PEMFC component targets [13].

# 28. Ohmic Loss

The ohmic loss is

$$
\boxed{
V_{\mathrm{ohm}}
=
iR_A
}
\tag{EQ-4}
$$

where $R_A$ is area-specific resistance.

The default is

$$
R_A=0.10~\Omega{\rm cm^2}.
$$

---

### Source and rationale for area-specific resistance

- **\(R_A=0.10~\Omega\,\mathrm{cm^2}\) [L/C]:** This represents an **effective whole-cell area-specific ohmic resistance**, including membrane proton resistance plus contact/electronic contributions. Historical DOE PEM membrane targets and many semi-empirical stack models use values of order \(0.1~\Omega\,\mathrm{cm^2}\); current state-of-the-art membranes can be significantly lower.
- **Why retained:** \(0.10~\Omega\,\mathrm{cm^2}\) is conservative and suitable for conceptual stack sizing, but it should be replaced by measured MEA/stack resistance when a specific fuel-cell technology is selected.

**References:** U.S. DOE PEMFC component technical targets [13]; Larminie & Dicks [10]; Barbir [11].

# 29. Concentration Loss

The concentration polarization term is

$$
\boxed{
V_{\mathrm{conc}}
=
\frac{RT}{nF}
\ln
\left(
\frac{
i_L
}{
i_L-i
}
\right).
}
\tag{EQ-5}
$$

The default limiting current density is

$$
i_L=1.60~{\rm A/cm^2}.
$$

The implementation protects the denominator from reaching zero.

---

### Source and rationale for limiting current density

- **\(i_L=1.60~\mathrm{A/cm^2}\) [L/E]:** This is a representative air-cathode limiting-current density for conventional PEMFC MEAs. DOE-supported MEA studies report limiting-current behavior around this magnitude, and published reduced-order PEMFC models commonly use \(1.4\)–\(2.0~\mathrm{A/cm^2}\) depending on pressure, temperature, stoichiometry, and transport design.
- **Interpretation:** \(i_L\) is a transport-limit parameter, not a recommended continuous operating current. Normal design operation should remain below it.

**References:** Barbir [11]; U.S. DOE PEMFC/MEA literature [13].

# 30. PEM Cell Voltage

The operating cell voltage is

$$
\boxed{
V_{\mathrm{cell}}
=
E_N
-
V_{\mathrm{act}}
-
V_{\mathrm{ohm}}
-
V_{\mathrm{conc}}.
}
\tag{EQ-6}
$$

This captures the characteristic reduction in voltage as load/current increases.

---

# 31. Stack Electrical Power

For

- $N_c$ series cells,
- active area $A_c$ per cell,
- current density $i$,

stack power is

$$
\boxed{
P_{\mathrm{stack}}
=
N_c
V_{\mathrm{cell}}
i
A_c.
}
\tag{EQ-7}
$$

The baseline sizing inputs are

$$
N_c=300,
$$

$$
A_c=300~{\rm cm^2}.
$$

---

### Rationale for the baseline stack dimensions

- **\(N_c=300\) [AS/D]** and **\(A_c=300~\mathrm{cm^2}\) [AS/D]:** These are representative stack-scaling values, not universal PEMFC design constants. They were chosen to place the baseline stack in the tens-of-kilowatts class without introducing detailed bipolar-plate/manifold geometry.
- At a representative operating point of roughly \(V_{cell}\sim0.7~\mathrm{V}\) and \(i\sim0.8~\mathrm{A/cm^2}\),
  \[
  P\approx N_c V_{cell} i A_c
  \approx300(0.7)(0.8)(300)
  \approx50~\mathrm{kW},
  \]
  showing why the selected cell count/area are internally consistent with the notebook's 50-kW demonstration case.
- **Use in studies:** these values should be treated as scalable architecture inputs. A real stack would require packaging, cooling, manifold, compression, and plate-area constraints.

**References:** fuel-cell stack-scaling relationships in O'Hayre et al. [9], Larminie & Dicks [10], and Barbir [11].

# 32. Fuel-Cell Capability Search

The polarization power curve is not guaranteed to remain monotonic up to the limiting-current boundary.

Therefore, the solver first evaluates a grid of current densities between

$$
i_{\min}=10^{-6}~{\rm A/cm^2}
$$

and

$$
i_{\max}=0.97i_L.
$$

It locates the actual maximum-power point

$$
\boxed{
P_{\mathrm{FC,max}}
=
\max_i P_{\mathrm{stack}}(i).
}
\tag{EQ-8}
$$

This is an important numerical/physical safeguard because solving blindly near the limiting-current boundary could select the descending branch of the polarization curve.

---

### Numerical-grid interpretation

- **\(i_{min}=10^{-6}~\mathrm{A/cm^2}\) [N]:** Purely numerical floor that avoids \(\ln(0)\) in the activation term.
- **\(i_{max}=0.97\,i_L\) [N]:** Numerical buffer that prevents the concentration-loss term from approaching its logarithmic singularity at \(i=i_L\). The 0.97 factor is **not** a physical continuous-operation limit.
- The useful engineering operating region should be determined from voltage, efficiency, thermal, durability, and mass-transport limits rather than from this numerical 97% boundary.

# 33. Operating-Point Solution

The requested power is limited to

$$
P_{\mathrm{target}}
=
\min
\left(
P_{\mathrm{requested}},
P_{\mathrm{FC,max}}
\right).
$$

The operating current density is then solved by bisection on the **ascending power branch**.

The default solver uses 80 bisection iterations.

This is a robust deterministic operating-point solve rather than a gradient-based root solver.

---

### Numerical-solver rationale

- **80 bisection iterations [N]:** This is a numerical robustness setting only. Bisection reduces the bracket by a factor \(2^{-80}\), which is far smaller than practical engineering precision and near/beyond floating-point relevance for this problem.
- The large fixed iteration count ensures deterministic convergence without introducing a separate nonlinear-solver dependency. It has no physical interpretation and should not appear in sensitivity discussions as a technology parameter.

# 34. Fuel-Cell Power Shortfall

After solving,

$$
P_{\mathrm{FC,available}}
=
N_cV_{\mathrm{cell}}iA_c.
$$

The shortfall is

$$
\boxed{
P_{\mathrm{FC,shortfall}}
=
\max
\left(
P_{\mathrm{requested}}
-
P_{\mathrm{FC,available}},
0
\right).
}
\tag{EQ-9}
$$

Thus,

$$
P_{\mathrm{FC,shortfall}}=0
$$

is feasible.

A positive value indicates that the selected stack geometry cannot supply the requested electrical demand.

The companion power margin is

$$
\boxed{
P_{\mathrm{FC,margin}}
=
P_{\mathrm{FC,max}}
-
P_{\mathrm{requested}}.
}
\tag{EQ-10}
$$

---

# 35. Fuel-Cell Load Fraction

The diagnostic load fraction is

$$
\boxed{
f_{\mathrm{load}}
=
\frac{
P_{\mathrm{requested}}
}{
P_{\mathrm{FC,max}}
}.
}
\tag{EQ-11}
$$

Values above unity indicate an over-demanded stack.

---

# 36. Fuel-Cell Efficiency

The model uses the thermoneutral voltage

$$
V_{TN}=1.481~{\rm V}.
$$

Voltage-based efficiency is

$$
\eta_V
=
\frac{
V_{\mathrm{cell}}
}{
V_{TN}
}.
$$

The final fuel-cell efficiency includes a correction for parasitic current:

$$
\boxed{
\eta_{FC}
=
\frac{
V_{\mathrm{cell}}
}{
V_{TN}
}
\frac{
i
}{
i+i_{\mathrm{loss}}
}.
}
\tag{EQ-12}
$$

The result is clipped to

$$
0.05\le\eta_{FC}\le0.75.
$$

This is the efficiency that can be passed back into `Power.py` as a load-dependent replacement for the constant fallback efficiency.

---

### Source basis and an important HHV/LHV convention note

- **\(V_{TN}=1.481~\mathrm{V}\) [F/L]:** This is the standard **HHV/liquid-water thermoneutral voltage** of hydrogen near room temperature:
  \[
  V_{TN}=\frac{\Delta H_{HHV}}{nF}\approx1.48~\mathrm{V}.
  \]
  It is widely used as an HHV efficiency reference for hydrogen fuel cells.
- **Efficiency bounds \(0.05\le\eta_{FC}\le0.75\) [N/AS]:** These are numerical/engineering bounds that prevent the reduced-order diagnostic from returning nonphysical or extreme efficiencies. DOE and airship literature place practical PEMFC electrical efficiency broadly around 55–65% depending on basis and operating point; 0.75 is therefore a generous upper guard, not a predicted technology target.

> **Basis consistency warning:** the polarization thermochemistry above uses \(\Delta H=-241.82~\mathrm{kJ/mol}\), i.e. the gaseous-water/LHV reaction basis, whereas \(V_{TN}=1.481~\mathrm{V}\) is the liquid-water/HHV basis. This is acceptable **only if the efficiency based on \(V/V_{TN}\) is intentionally reported on an HHV basis**. If that efficiency is later combined directly with \(LHV_{H_2}=120~\mathrm{MJ/kg}\) for fuel-flow calculation, the HHV/LHV bases must first be reconciled. The LHV thermoneutral equivalent is approximately \(1.25~\mathrm{V}\).

**References:** NIST thermochemical data [8]; O'Hayre et al. [9]; U.S. DOE fuel-cell efficiency references [18].

# 37. Hydrogen Consumption from Faraday's Law

The hydrogen molar-flow rate implied by the electrochemical current is

$$
\boxed{
\dot n_{H_2}
=
\frac{
N_c i A_c
}{
2F
}.
}
\tag{EQ-13}
$$

With hydrogen molar mass

$$
M_{H_2}
=
2.016\times10^{-3}~{\rm kg/mol},
$$

hydrogen mass flow is

$$
\boxed{
\dot m_{H_2}
=
\dot n_{H_2}M_{H_2}.
}
\tag{EQ-14}
$$

The power-specific fuel consumption is

$$
\boxed{
PSFC
=
\frac{
\dot m_{H_2}
}{
P_{\mathrm{FC,available}}
}.
}
\tag{EQ-15}
$$

These outputs are diagnostic because authoritative mission hydrogen inventory is integrated from `Power.fuel_flow` in `Tank.py`.

---

### Source basis

- **\(M_{H_2}=2.016\times10^{-3}~\mathrm{kg/mol}\) [F/L]:** Standard molar mass of molecular hydrogen, rounded for engineering calculations.
- The value is a physical property, not a model calibration.

**Reference:** NIST Chemistry WebBook [8].

# 38. FuelCellPolarization Inputs

| Input | Default | Units |
|---|---:|---:|
| Requested FC power | 50 kW | W |
| Number of cells | 300 | – |
| Active cell area | 300 | cm² |
| FC temperature | 333.15 | K |
| $p_{H_2}$ | 0.60 | bar |
| $p_{O_2}$ | 0.21 | bar |
| $p_{H_2O}$ | 1.0 | bar |
| Exchange current density | $3\times10^{-6}$ | A/cm² |
| Limiting current density | 1.60 | A/cm² |
| Parasitic current density | 0.002 | A/cm² |
| Area-specific resistance | 0.10 | Ω cm² |
| Transfer coefficient | 1.0 | – |

These polarization parameters require calibration against a representative PEMFC technology before the model is treated as predictive for a particular stack.

---

### Source and rationale for the default PEMFC operating point

The values in this cell define a **representative low-temperature PEMFC demonstration case**, not universal stack requirements.

- **Requested power \(P_{FC}=50~\mathrm{kW}\) [AS]:** Chosen to demonstrate the stack-scaling solver at a propulsion-relevant tens-of-kilowatts level.
- **\(N_c=300,\ A_c=300~\mathrm{cm^2}\) [AS/D]:** Internally consistent with approximately 50 kW at representative PEMFC voltage/current density, as shown above.
- **\(T=333.15~\mathrm{K}\) (60°C) [L/C]:** Within the normal low-temperature PEMFC operating regime; many PEMFC references use approximately 60–80°C depending on membrane and humidification strategy.
- **\(p_{O_2}=0.21~\mathrm{bar}\) [F/AS]:** Represents the oxygen partial pressure of dry air at approximately 1 bar total pressure.
- **\(p_{H_2}=0.60~\mathrm{bar}\) [AS]:** Effective hydrogen partial-pressure assumption representing humidified/reactant-side operation. It is a model input, not a universal anode pressure.
- **\(p_{H_2O}=1.0~\mathrm{bar}\) [A/AS]:** In this simplified Nernst implementation it should be interpreted as a **standard-state water activity/reference term**, not literally as the physical water-vapor partial pressure at 60°C. Saturated water vapor at 60°C is far below 1 bar. A detailed humidification model should replace this assumption when water management is modeled explicitly.
- The polarization coefficients in this cell inherit the literature/assumption classification given in the preceding sections.

**References:** O'Hayre et al. [9]; Larminie & Dicks [10]; Barbir [11]; Arear et al. [12].

# 39. FuelCellPolarization Outputs

| Output | Meaning |
|---|---|
| `eta_fc` | Load-dependent fuel-cell efficiency |
| `PSFC` | Power-specific hydrogen consumption |
| `i_op` | Operating current density |
| `v_op` | Operating cell voltage |
| `P_fc_available` | Electrical power delivered |
| `P_fc_max` | Maximum stack power capability |
| `fc_power_shortfall` | Requested minus available power |
| `fc_power_margin` | Maximum minus requested power |
| `fc_power_limited` | Binary power-limited indicator |
| `fc_load_fraction` | Requested/max power |
| `fc_hydrogen_flow` | Faraday-law hydrogen flow |
| `fc_voltage_efficiency` | $V_{\mathrm{cell}}/V_{TN}$ |

---

# Part IV — Hydrogen Inventory and Tank Sizing

# 40. Tank Mission Hydrogen Integration

The tank component receives mission hydrogen mass-flow history

$$
\dot m_{H_2,i}.
$$

With equal mission time increments,

$$
\Delta t
=
\frac{t_m}{N},
$$

hydrogen consumed is

$$
\boxed{
m_{H_2,\mathrm{used}}
=
\sum_i
\dot m_{H_2,i}\Delta t.
}
\tag{EQ-1}
$$

This is the authoritative mission hydrogen inventory.

---

# 41. Hydrogen Reserve

The reserve hydrogen mass is

$$
\boxed{
m_{H_2,\mathrm{reserve}}
=
f_R
m_{H_2,\mathrm{used}}.
}
\tag{EQ-2}
$$

The installed hydrogen mass is

$$
\boxed{
m_{H_2,\mathrm{installed}}
=
m_{H_2,\mathrm{used}}
+
m_{H_2,\mathrm{reserve}}
=
m_{H_2,\mathrm{used}}(1+f_R).
}
\tag{EQ-3}
$$

The default reserve fraction is

$$
f_R=0.10.
$$

This is an operational/design assumption.

---

### Source and rationale for hydrogen reserve

- **\(f_R=0.10\) [AS]:** The 10% factor is a **conceptual mission-sizing contingency**, not a universal certification reserve requirement. Carichner & Nicolai explicitly recommend carrying approximately 6–10% margin during conceptual design in their solar-HALE energy-balance example, which supports the magnitude as a preliminary design allowance.
- For certification-oriented aircraft sizing, this scalar should be replaced by a mission-specific reserve model including diversion, hold, unusable fuel, trapped fuel, and operational contingency as applicable.

**Reference:** Carichner & Nicolai [1], Sample Problem 5.3.

# 42. simplified Hydrogen-Mass Fallback

A simplified `fuel_onboard_mass` input is retained.

By default,

```text
use_simplified_fallback_mass = False
```

so the tank model sizes hydrogen only from integrated fuel flow.

If the simplified option is explicitly enabled and integrated fuel flow is zero, the model uses the maximum supplied fallback onboard mass.

This fallback is disabled during normal coupled sizing to avoid discontinuous mass jumps.

---

# 43. Hydrogen Storage Type

The model accepts a discrete storage type.

The default is

```text
liquid_h2
```

and a simplified

```text
compressed_h2
```

branch is also available.

For liquid hydrogen, the default storage density is

$$
\rho_{H_2}=70.8~{\rm kg/m^3}.
$$

For compressed hydrogen, if the density input has not been explicitly changed from the liquid-hydrogen default, the code uses the fallback approximation

$$
\boxed{
\rho_{H_2,\mathrm{comp}}
=
5
+
40
\min
\left(
\frac{p_{tank}}{350},
2
\right).
}
\tag{EQ-4}
$$

This is a **conceptual fallback correlation**, not a thermodynamic equation of state.

For rigorous compressed-hydrogen analysis, density should be supplied from a real-gas property model.

---

### Source basis and storage-state caution

- **\(\rho_{LH_2}=70.8~\mathrm{kg/m^3}\) [F/L]:** Representative density of saturated liquid hydrogen near its normal boiling point (\(\sim20.3~\mathrm{K}\), 1 atm). This is a physical-property input and should be replaced by state-dependent property data if tank pressure/temperature vary substantially.
- **Compressed-H\(_2\) density fallback [RO/AS]:**
  \[
  \rho=5+40\min\left(\frac{p_{tank}}{350},2\right)
  \]
  is **not an equation of state and is not claimed as a literature correlation**. It is a coarse reduced-order placeholder that gives plausible order-of-magnitude density near some moderate pressures but becomes unreliable at high pressure.
- In particular, it should **not** be used for rigorous 700-bar storage prediction. A real-gas property source such as NIST REFPROP, CoolProp with a validated H\(_2\) EOS, or tabulated manufacturer/DOE data should be used instead.

**References:** NIST hydrogen-property data [8]; U.S. DOE physical-hydrogen-storage references [16].

# 44. Internal Hydrogen Volume

The contained hydrogen volume is

$$
\boxed{
V_{H_2}
=
\frac{
m_{H_2,\mathrm{installed}}
}{
\rho_{H_2}
}.
}
\tag{EQ-5}
$$

A numerical minimum volume is enforced.

---

# 45. Tank Gravimetric Efficiency

The input base gravimetric efficiency is defined as

$$
\boxed{
\eta_{g,base}
=
\frac{
m_{H_2}
}{
m_{H_2}
+
m_{\mathrm{storage,base}}
}.
}
\tag{EQ-6}
$$

Solving for base empty storage mass,

$$
\boxed{
m_{\mathrm{storage,base}}
=
m_{H_2}
\frac{
1-\eta_{g,base}
}{
\eta_{g,base}
}.
}
\tag{EQ-7}
$$

The default is

$$
\eta_{g,base}=0.20.
$$

The code explicitly defines this as the vessel-plus-insulation efficiency **before** delivery hardware and volume-dependent penalties.

---

### Source and rationale for tank gravimetric efficiency

- **\(\eta_{g,base}=0.20\) [L/C]:** The gravimetric efficiency is defined as
  \[
  \eta_g=\frac{m_{H_2}}{m_{H_2}+m_{tank}}.
  \]
  A 20% system/tank-level baseline is intentionally conservative for small-to-medium aviation cryogenic storage, where insulation, supports, fittings, thermal management, and structural margins can dominate.
- Recent regional-aviation hydrogen studies have explicitly adopted approximately 20% tank gravimetric efficiency as a conservative assumption when low boil-off and additional insulation are desired. Historical and advanced composite-aircraft tank concepts span a much wider range, so 0.20 should be treated as a technology/design baseline rather than a universal LH\(_2\) capability.
- **Why retained:** it prevents conceptual studies from assuming optimistic large-scale/composite tank performance before detailed structural/thermal design is available.

**References:** NASA aircraft LH\(_2\)-tank studies [14,15]; U.S. DOE hydrogen-storage system targets [16]; recent regional-aviation LH\(_2\) studies [17].

# 46. Structural and Insulation Mass Split

The base storage mass is split using the default shares

$$
f_s=0.72,
$$

$$
f_i=0.28.
$$

After normalization,

$$
\boxed{
m_{\mathrm{struct}}
=
m_{\mathrm{storage,base}}
\frac{
f_s
}{
f_s+f_i
}
}
\tag{EQ-8}
$$

and

$$
\boxed{
m_{\mathrm{ins,base}}
=
m_{\mathrm{storage,base}}
\frac{
f_i
}{
f_s+f_i
}.
}
\tag{EQ-9}
$$

These are conceptual mass-allocation assumptions.

---

### Source and rationale for the structural/thermal split

- **\(f_s=0.72,\ f_i=0.28\) [C/AS]:** These fractions partition the baseline tank hardware mass into structural and insulation/thermal portions. They are **not universal literature constants**.
- Historical NASA/NACA aircraft LH\(_2\) tank mass breakdowns show the tank shell, baffles, and structural hardware as the dominant fraction, with insulation and protective covering forming a smaller but still significant share. The present 72/28 split intentionally allocates somewhat more mass to thermal protection than some large historical tanks, making it conservative for smaller aviation tanks with higher surface-to-volume ratio.
- The fractions should be recalibrated when a specific tank material, pressure, aspect ratio, insulation concept, or support architecture is selected.

**References:** Reynolds/NACA aircraft LH\(_2\) tank design [14]; NASA liquid-hydrogen fuel-tank studies [15].

# 47. External Insulated Tank Volume

The current tank geometry is not a detailed cylindrical or spherical pressure-vessel model.

Instead, a characteristic radius is approximated as

$$
\boxed{
r_{\mathrm{eff}}
=
V_{H_2}^{1/3}.
}
\tag{EQ-10}
$$

The outer-volume scale is

$$
\boxed{
f_V
=
\left(
1+
\frac{
3t_{ins}
}{
\max(r_{\mathrm{eff}},0.1)
}
\right)^3.
}
\tag{EQ-11}
$$

Thus,

$$
\boxed{
V_{\mathrm{tank,outer}}
=
V_{H_2}f_V.
}
\tag{EQ-12}
$$

This is a conceptual insulation-volume proxy rather than exact tank geometry.

---

### Interpretation of the tank-geometry proxy

- **\(r_{eff}=V^{1/3}\) [RO/D]:** This is a reduced-order characteristic-length scaling. It follows dimensional similitude: a characteristic length of a geometrically similar tank varies as the cube root of volume.
- The insulation/outer-radius expression therefore captures the first-order increase in external size without claiming to reproduce an actual cylindrical, spherical, conformal, or multi-lobe tank.
- **The 0.1 factor/limit used in the proxy [AS/N]** is a geometric safeguard/heuristic rather than a literature tank-design constant. Detailed tank geometry should supersede it when diameter/length constraints are known.

This cell is best interpreted as conceptual geometric scaling, not detailed cryogenic vessel design.

# 48. Delivery-System Mass

The hydrogen delivery system is

$$
\boxed{
m_{\mathrm{delivery}}
=
f_{\mathrm{delivery}}
m_{H_2,\mathrm{installed}}.
}
\tag{EQ-13}
$$

The default is

$$
f_{\mathrm{delivery}}=0.08.
$$

This term conceptually covers fuel delivery hardware such as lines, valves, pumps, regulators, and associated equipment.

---

### Source and rationale for delivery-system mass

- **\(f_{delivery}=0.08\) [AS/C]:** The inclusion of a separate balance-of-plant/delivery allowance is strongly supported by system-level hydrogen-storage definitions, which include valves, regulators, piping, supports, instrumentation, pressure relief, and related hardware in addition to the bare vessel.
- The **8% numerical value itself is a conceptual allocation**, not a universal DOE/NASA coefficient. It is intended to prevent the tank-only model from omitting these unavoidable installation items.
- The factor should be calibrated against a specific cryogenic fuel-feed architecture when pumps, heat exchangers, vaporizers, pressure-build systems, or redundant shutoff hardware are explicitly modeled.

**References:** U.S. DOE onboard-hydrogen-storage system definitions and targets [16]; NASA aircraft cryogenic tank studies [14,15].

# 49. Volume-Dependent Tank Mass Penalty

The model adds

$$
\boxed{
m_{\mathrm{volume}}
=
k_VV_{H_2}
+
\rho_{ins}t_{ins}k_{ins}.
}
\tag{EQ-14}
$$

The defaults are

$$
k_V=15~{\rm kg/m^3},
$$

$$
\rho_{ins}=50~{\rm kg/m^3},
$$

$$
t_{ins}=0.05~{\rm m},
$$

and

$$
k_{ins}=150.
$$

This expression is a **conceptual calibration/penalty model**, not a first-principles structural or heat-transfer equation.

The second term is called an insulation-shell penalty in the code.

---

### Source and rationale for tank volume/insulation penalties

- **\(\rho_{ins}=50~\mathrm{kg/m^3}\) [L/C]:** This lies within the density range of lightweight cryogenic foam insulation reported in historical NASA aircraft-tank studies. NASA reports aircraft cryogenic foam systems spanning roughly a few tens to several tens of \(\mathrm{kg/m^3}\), making 50 kg/m³ a reasonable mid-range conceptual value.
- **\(t_{ins}=0.05~\mathrm{m}\) [L/C]:** A 50-mm insulation thickness is close to historical aircraft LH\(_2\) conceptual designs using approximately 57 mm foam insulation. It is suitable as a baseline, but required thickness depends on mission duration, ambient heat flux, vacuum/MLI use, allowable boil-off, and tank size.
- **\(k_V=15~\mathrm{kg/m^3}\) [C/RO]:** This is a reduced-order installation/volume penalty coefficient. It is not a first-principles material property and should be calibrated against a tank/system database.
- **\(k_{ins}=150\) [C/RO]:** This is also a reduced-order insulation-installation coefficient. For dimensional consistency in
  \[
  m_{ins,penalty}=\rho_{ins}t_{ins}k_{ins},
  \]
  \(k_{ins}\) must be interpreted as an **effective reference area with units of \(\mathrm{m^2}\)** (or an equivalent area-producing scaling coefficient), not as a dimensionless physical constant.
- **Important:** neither \(k_V\) nor \(k_{ins}\) should be presented as directly measured literature constants. They are conceptual calibration/penalty terms that should eventually be replaced by explicit vessel surface area, support mass, insulation area, and thermal-design equations.

**References:** Reynolds/NACA aircraft LH\(_2\) tank design [14]; NASA liquid-hydrogen tank studies [15].

# 50. Total Insulation Mass

The total insulation mass is

$$
\boxed{
m_{\mathrm{ins}}
=
m_{\mathrm{ins,base}}
+
m_{\mathrm{volume}}.
}
\tag{EQ-15}
$$

Because `volume_penalty_mass` includes both the volume term and insulation-shell term, it should be interpreted as a combined storage-installation penalty rather than a purely geometric insulation mass.

---

# 51. Total Empty EQ-System Mass

The total empty EQ-system mass is

$$
\boxed{
m_{\mathrm{tank}}
=
m_{\mathrm{struct}}
+
m_{\mathrm{ins}}
+
m_{\mathrm{delivery}}.
}
\tag{EQ-16}
$$

Hydrogen itself is excluded.

This is the quantity passed to the weight model as empty storage-system mass.

---

# 52. Achieved Installed Gravimetric Efficiency

Because delivery hardware and volume penalties are added after the nominal base efficiency, the achieved efficiency is

$$
\boxed{
\eta_{g,\mathrm{achieved}}
=
\frac{
m_{H_2,\mathrm{installed}}
}{
m_{H_2,\mathrm{installed}}
+
m_{\mathrm{tank}}
}.
}
\tag{EQ-17}
$$

In general,

$$
\eta_{g,\mathrm{achieved}}
<
\eta_{g,base}.
$$

This output is a useful diagnostic for checking whether added installation penalties have substantially degraded the target storage performance.

---

# 53. Hydrogen Chemical Energy

The installed hydrogen chemical energy is

$$
\boxed{
E_{H_2}
=
\frac{
m_{H_2,\mathrm{installed}}
LHV_{H_2}
}{
3600
}.
}
\tag{EQ-18}
$$

The default hydrogen lower heating value is

$$
LHV_{H_2}=120~{\rm MJ/kg}.
$$

The output is expressed in Wh.

---

### Source basis for hydrogen heating value

- **\(LHV_{H_2}=120~\mathrm{MJ/kg}\) [F/L]:** Standard lower heating value of hydrogen, equivalent to approximately \(33.3~\mathrm{kWh/kg}\). It corresponds to water remaining in the vapor phase and is the appropriate basis for many fuel-cell/propulsion energy calculations.
- This is a physical thermochemical property rather than a calibration parameter.

**References:** NIST thermochemical data [8]; U.S. DOE hydrogen-storage references [16].

# 54. Usable Primary Energy Diagnostic

The tank component also reports

$$
\boxed{
E_{\mathrm{usable}}
=
E_{H_2}\eta_{\mathrm{conv}}.
}
\tag{EQ-19}
$$

The default conversion efficiency is

$$
\eta_{\mathrm{conv}}=0.55.
$$

This is only a diagnostic. It does not replace the load-dependent efficiency calculation in the fuel-cell polarization or power model.

---

### Source and rationale for conversion efficiency

- **\(\eta_{conv}=0.55\) [L/C]:** Carichner & Nicolai Table 5.2 use approximately **55% fuel-cell efficiency** for their electric-airship technology database, with higher projected future performance. Modern DOE summaries commonly place direct-hydrogen PEMFC electrical efficiency around the upper-50% to ~60% range depending on load and LHV/HHV basis.
- The ADaPT value is therefore a conservative conceptual conversion efficiency for diagnostic energy-to-fuel calculations.
- **Basis warning:** always state whether the efficiency is referenced to hydrogen LHV or HHV. If \(LHV_{H_2}=120~\mathrm{MJ/kg}\) is used in the denominator, \(\eta_{conv}\) should be interpreted on an LHV basis unless explicitly converted.

**References:** Carichner & Nicolai [1], Table 5.2; U.S. DOE fuel-cell efficiency summaries [18].

# 55. Tank Outputs

| Output | Meaning |
|---|---|
| `hydrogen_mass_used` | Mission hydrogen consumption |
| `hydrogen_reserve_mass` | Reserve hydrogen |
| `hydrogen_mass` | Installed hydrogen |
| `tank_mass` | Empty installed EQ-system mass |
| `tank_volume` | Internal H₂ volume |
| `tank_volume_outer` | Insulated outer tank volume |
| `structural_mass` | Structural share of base storage mass |
| `insulation_mass` | Base insulation + installation penalty |
| `delivery_mass` | Hydrogen delivery-system mass |
| `volume_penalty_mass` | Volume/insulation penalty |
| `nominal_tank_empty_mass` | Empty mass implied by base gravimetric efficiency |
| `achieved_tank_gravimetric_efficiency` | Final installed gravimetric efficiency |
| `hydrogen_energy_content` | Installed H₂ chemical energy |
| `usable_primary_energy` | Efficiency-adjusted diagnostic energy |

---

# 56. Cross-Component Coupling

These four components form an architecture-dependent energy-storage chain.

## Battery-Electric

$$
P_{\mathrm{elec}}
\rightarrow
\text{BatteryOnly}
\rightarrow
m_b,\;V_b
\rightarrow
\text{Weight}.
$$

## Solar-Battery

$$
P_{\mathrm{elec}},\;G,\;A_{PV}
\rightarrow
\text{SolarBattery}
\rightarrow
P_{PV},\;E_{PV},\;m_b,\;m_{PV}
\rightarrow
\text{Weight}.
$$

## Hydrogen Fuel Cell

$$
P_{FC}
\rightarrow
\text{FuelCellPolarization}
\rightarrow
\eta_{FC}(P)
\rightarrow
\text{Power}
\rightarrow
\dot m_{H_2}
\rightarrow
\text{Tank}
\rightarrow
m_{H_2},\;m_{\mathrm{tank}},\;V_{\mathrm{tank}}
\rightarrow
\text{Weight}.
$$

This creates the coupled relationship

$$
\boxed{
P_{\mathrm{required}}
\rightarrow
m_{\mathrm{energy\,system}}
\rightarrow
MTOW
\rightarrow
\text{drag/buoyancy}
\rightarrow
P_{\mathrm{required}}.
}
$$

---

# 57. Architecture-Dependent Mass and Volume Effects

Battery and hydrogen architectures influence the vehicle differently.

For batteries,

$$
E_{\mathrm{mission}}
\rightarrow
m_b,\;V_b.
$$

For hydrogen,

$$
E_{\mathrm{mission}}
\rightarrow
m_{H_2}
\rightarrow
m_{\mathrm{tank}},\;V_{\mathrm{tank}}.
$$

For solar-battery systems,

$$
E_{\mathrm{solar,used}}
\uparrow
\quad\Rightarrow\quad
E_{b,\mathrm{delivered}}
\downarrow
\quad\Rightarrow\quad
m_b\downarrow,
$$

but

$$
A_{PV}\uparrow
\quad\Rightarrow\quad
m_{PV}\uparrow.
$$

Thus solar integration naturally creates a mass-energy trade.

For fuel cells,

$$
\eta_{FC}\uparrow
\quad\Rightarrow\quad
\dot m_{H_2}\downarrow
\quad\Rightarrow\quad
m_{H_2}\downarrow
\quad\Rightarrow\quad
m_{\mathrm{tank}}\downarrow.
$$

---

# 58. Model Assumptions and Limitations

| Model item | Current treatment | Classification |
|---|---|---|
| Equal mission time steps | $t_m/N$ | Numerical assumption |
| Battery specific energy | 250 Wh/kg | Technology input |
| Battery volumetric density | 600 Wh/L | Technology input |
| Battery efficiency | 0.95 | Technology input |
| DoD | 0.80 | Operational/technology input |
| Battery packaging factor | 0.72 | Pack integration assumption |
| Battery temperature slope | 0.003/K | Conceptual derating |
| Minimum battery temperature factor | 0.60 | Numerical/design bound |
| 0.85 pack-voltage factor | fixed | Conceptual current-sizing assumption |
| Cell continuous current | 10 A/string | Conceptual assumption |
| PV reference efficiency | 0.22 | Technology input |
| PV temperature coefficient | -0.003/K | Technology assumption |
| PV areal density | 0.50 kg/m² | Technology assumption |
| PV thickness | 1 mm | Packaging assumption |
| Excess solar charging | not automatically stored | Limitation |
| FC polarization | semi-empirical | Model scope |
| FC stack mass | external to polarization model | Ownership rule |
| FC thermoneutral voltage | 1.481 V | Electrochemical constant/reference |
| FC efficiency limits | 0.05–0.75 | Numerical/conceptual bound |
| FC maximum-current fraction | 0.97 $i_L$ | Numerical safeguard |
| FC polarization parameters | baseline defaults | Calibration required |
| H₂ reserve | 10% | Operational assumption |
| LH₂ density | 70.8 kg/m³ | Storage property input |
| compressed-H₂ density fallback | simple pressure correlation | Conceptual fallback |
| base tank gravimetric efficiency | 0.20 | Technology input |
| tank structural share | 0.72 | Conceptual assumption |
| tank insulation share | 0.28 | Conceptual assumption |
| delivery mass fraction | 0.08 | Conceptual assumption |
| volume mass density | 15 kg/m³ | Calibration assumption |
| insulation coefficient | 150 | Calibration assumption |
| tank outer-volume model | $V^{1/3}$-based proxy | Conceptual geometry |
| detailed tank stress | not modeled | Limitation |
| boil-off/heat leak | not modeled here | Limitation |
| hydrogen real-gas EOS | not modeled in fallback | Limitation |

---

### Interpretation of the assumptions/defaults table

The defaults in this notebook intentionally mix three different types of quantities:

1. **Physical/literature quantities** such as \(F\), \(M_{H_2}\), \(LHV_{H_2}\), \(\rho_{LH_2}\), and standard thermochemical data.
2. **Technology baselines** such as battery specific energy, PV efficiency, PV areal density, PEMFC \(i_0\), \(R_A\), and \(i_L\), which are literature-supported but technology-dependent.
3. **Reduced-order/design assumptions** such as the battery temperature slope/floor, the 0.85 pack-voltage margin, tank delivery fraction, structural/insulation split, \(k_V\), \(k_{ins}\), and the compressed-H\(_2\) density fallback.

The third category should never be described as universal literature constants. They are deliberately exposed so that sensitivity analysis, calibration, or higher-fidelity replacement is possible.

# 59. Provenance Classification

The Theory Guide uses:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical relationship |
| **L** | Literature-supported relationship |
| **A** | Adapted literature relationship |
| **E** | Empirical/semi-empirical relationship |
| **AS** | Modeling assumption |
| **C** | Calibration/technology parameter |
| **D** | Derived quantity |
| **N** | Numerical safeguard |

| Equation group | Classification |
|---|---|
| EQ-1–2 | D |
| EQ-3 | AS / C |
| EQ-4–10 | D / A |
| EQ-11–14 | AS / D |
| EQ-1 | E / C |
| EQ-2 | F / L |
| EQ-3–4 | D |
| EQ-5–18 | D / AS |
| EQ-1–2 | F |
| EQ-3–5 | E / F |
| EQ-6–7 | F / D |
| EQ-8–11 | D / N |
| EQ-12 | A / E |
| EQ-13–15 | F / D |
| EQ-1–3 | D / AS |
| EQ-4 | AS / C |
| EQ-5 | F |
| EQ-6–7 | D |
| EQ-8–9 | AS / D |
| EQ-10–12 | AS |
| EQ-13 | AS / C |
| EQ-14–16 | AS / C / D |
| EQ-17 | D |
| EQ-18 | F |
| EQ-19 | D / AS |

---

### Recommended interpretation of provenance labels

To avoid overstating support for simplified coefficients, use the following language consistently:

- **[F] Fundamental:** physical constant or first-principles relation.
- **[L] Literature:** value/equation directly supported by a cited source.
- **[A] Adapted literature:** literature relationship rearranged, interpolated, or simplified for ADaPT.
- **[E] Empirical:** fitted/semi-empirical correlation.
- **[RO] Reduced-order:** simplified physical/scaling representation retaining dominant dependencies.
- **[AS] Assumption:** engineering choice where no unique literature value exists.
- **[C] Calibration/technology baseline:** representative value selected from a literature range or reference configuration.
- **[D] Derived:** algebraically obtained quantity.
- **[N] Numerical safeguard:** floor, cap, clipping factor, or solver setting.

This is preferable to calling simplified formulations “legacy,” because the framework has not yet had a public historical release and the simplified models remain valid lower-fidelity options.

# 60. Derivatives

The battery, solar-battery, and tank components use finite-difference derivatives with

$$
\Delta x=10^{-8}.
$$

The fuel-cell polarization component uses

$$
\Delta x=10^{-6}.
$$

The latter is reasonable given the nested operating-point solve, but the polarization model contains substantial nonsmooth numerical logic:

- clipping,
- maximum-power search,
- current-density limits,
- bisection,
- power saturation,
- shortfall logic.

Similarly, the battery and tank models contain:

- `max`,
- `clip`,
- `ceil`,
- discrete storage-type branching,
- minimum-capacity/volume floors.

These features should be considered during gradient-based optimization.

---

### Source and rationale for finite-difference steps

- **\(10^{-8}\) for Battery/Solar/Tank and \(10^{-6}\) for Fuel Cell [N]:** These are numerical differentiation settings, not physical coefficients.
- Smaller steps reduce truncation error but can amplify floating-point cancellation; larger steps improve robustness for piecewise/logarithmic fuel-cell calculations. The fuel-cell model contains logarithms, clipping, and root solving, so the slightly larger \(10^{-6}\) perturbation is a pragmatic robustness choice.
- These values should be verified with OpenMDAO derivative checks if gradients materially affect optimization convergence.

# 61. Verification Recommendations

## 61.1 BatteryOnly

For constant power $P$, verify analytically:

$$
E_{\mathrm{load}}
=
Pt_m/3600,
$$

then independently calculate:

$$
E_{\mathrm{capacity}},
\quad
m_b,
\quad
V_b,
\quad
E_{\mathrm{usable}}.
$$

Check that

$$
E_{\mathrm{usable}}
\approx
E_{\mathrm{load}}.
$$

## 61.2 SolarBattery

Test three limiting cases:

1. no solar,
2. partial solar contribution,
3. solar generation greater than instantaneous load.

Confirm energy conservation:

$$
E_{\mathrm{load}}
=
E_{\mathrm{solar,used}}
+
E_{b,\mathrm{delivered}}.
$$

## 61.3 FuelCellPolarization

Verify:

- open/low-current voltage trend,
- decreasing voltage with increasing current density,
- existence of a maximum stack-power point,
- correct shortfall when demand exceeds capability,
- Faraday-law hydrogen consumption.

Plotting $V(i)$ and $P(i)$ is strongly recommended for regression testing.

## 61.4 Tank

For constant hydrogen flow, verify:

$$
m_{H_2,\mathrm{used}}
=
\dot m_{H_2}t_m.
$$

Then independently verify:

$$
m_{H_2,\mathrm{installed}},
\quad
V_{H_2},
\quad
m_{\mathrm{storage,base}},
\quad
m_{\mathrm{delivery}},
\quad
m_{\mathrm{tank}},
\quad
\eta_{g,\mathrm{achieved}}.
$$

## 61.5 Coupled Hydrogen Chain

For a fuel-cell case, verify consistency between:

$$
P_{\mathrm{FC}},
\quad
\eta_{FC},
\quad
\dot m_{H_2}
$$

in `Power.py` and the integrated mission hydrogen mass in `Tank.py`.

---

# 62. Recommended Future Refinements

1. Replace equal-time integration with explicit mission time arrays.
2. Introduce battery charge/discharge efficiency separately.
3. Add battery C-rate and peak-power constraints directly to the capacity sizing.
4. Add cell-level energy capacity so series/parallel counts are physically coupled to energy as well as current.
5. Replace the linear battery temperature derating with chemistry-specific maps.
6. Include state-of-charge propagation for hybrid missions.
7. Model solar incidence geometry explicitly or document that it is embedded in irradiance.
8. Route excess solar generation into explicit battery charging where appropriate.
9. Add degradation and cycle-life constraints for long-duration missions.
10. Calibrate the PEM polarization parameters against a representative stack.
11. Add compressor, humidifier, thermal-management, and parasitic-power effects to the PEMFC operating model.
12. Couple fuel-cell temperature and reactant partial pressures to altitude and balance-of-plant behavior.
13. Replace compressed-hydrogen fallback density with a real-gas property model.
14. Replace the tank $V^{1/3}$ geometry proxy with explicit vessel geometry.
15. Add pressure-vessel stress sizing.
16. Add LH₂ heat-leak, boil-off, dormancy, venting, and pressure-control models when required.
17. Replace tank calibration penalties with material- and geometry-based correlations.
18. Add insulation conductivity and thermal design to storage sizing.
19. Develop analytic or complex-step-compatible derivatives where practical.

---



# 64. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.


### Additional technical references supporting default coefficients and assumptions

[2] NASA Small Spacecraft Systems Virtual Institute, **State of the Art of Small Spacecraft Technology — Power Systems**, current NASA technical web/report series. Used for representative Li-ion cell/pack specific energy, voltage, and efficiency ranges.

[3] Panasonic/SANYO Energy, **NCR18650B Lithium-Ion Cell Data Sheet**, Version 13.11.1. Representative high-energy cylindrical Li-ion cell; nominal voltage approximately 3.6 V, specific energy approximately 243 Wh/kg, and volumetric energy density approximately 676 Wh/L.

[4] NASA, **Sizing Power Components of an Electrically Driven Tail Concept for a Hybrid-Electric Aircraft**, NASA technical report/NTRS 20160007561. Representative 400-V-class electrified-aircraft bus and explicit battery installation/BMS mass allowance.

[5] NASA/CR-2020-220368, NASA conceptual power-system sizing study using an **80% Li-ion depth-of-discharge** assumption and representative battery specific-energy values.

[6] National Renewable Energy Laboratory (NREL), **Photovoltaic Module Technologies: Benchmark Costs and Technology Evolution Framework Results**, NREL technical report. Supports approximately 22% high-efficiency crystalline-silicon module baselines and power temperature coefficients of order \(-0.3\%\)/K.

[7] NASA, **Deployable Aerospace Photovoltaic Array Based on Lightweight/Flexible Cell Technology**, NASA NTRS 19890015349. Used as an aerospace lightweight-PV areal-mass comparison.

[8] NIST Chemistry WebBook, SRD 69, and NIST-JANAF Thermochemical Tables. Standard thermochemical properties for \(\mathrm{H_2}\), \(\mathrm{O_2}\), and \(\mathrm{H_2O}\), hydrogen molar mass, and reaction enthalpy/entropy data.

[9] R. O'Hayre, S.-W. Cha, W. Colella, and F. B. Prinz, **Fuel Cell Fundamentals**, Wiley. Nernst potential, activation/ohmic/concentration polarization, thermoneutral voltage, and PEMFC stack fundamentals.

[10] J. Larminie and A. Dicks, **Fuel Cell Systems Explained**, Wiley. Semi-empirical PEMFC polarization relations and system-level efficiency interpretation.

[11] F. Barbir, **PEM Fuel Cells: Theory and Practice**, Academic Press. PEMFC electrochemistry, transport, resistance, and practical operating ranges.

[12] W. F. Arear, A. R. N. Zeiny, and M. A. R. S. Al-Baghdadi, “Influence of Al\(_2\)O\(_3\)-Water Nanofluid Coolant on Thermal Performance of Hydrogen PEM Fuel Cell Stacks,” *IOP Conference Series: Materials Science and Engineering*, 1094 (2021) 012064, doi:10.1088/1757-899X/1094/1/012064. Provides representative PEMFC semi-empirical parameters including cathode \(i_0\) of order \(3\times10^{-6}~\mathrm{A/cm^2}\).

[13] U.S. Department of Energy, **PEM Fuel Cell Component Technical Targets**. Used for membrane/cell resistance, crossover-current, transport, and durability context.

[14] T. W. Reynolds, **Aircraft-Fuel-Tank Design for Liquid Hydrogen**, NACA RM E55F22, 1955. Historical aircraft LH\(_2\) tank structural and insulation mass/thickness data.

[15] NASA, **Liquid Hydrogen Fuel Tanks**, NASA technical report/NTRS archival study. Aircraft cryogenic insulation concepts, foam density/thickness ranges, and system integration considerations.

[16] U.S. Department of Energy, Hydrogen and Fuel Cell Technologies Office, **Hydrogen Storage / Physical Hydrogen Storage Technical Targets and System Definitions**. Hydrogen LHV, storage-system gravimetric metrics, and balance-of-plant scope.

[17] Recent regional-aviation liquid-hydrogen system studies using approximately **20% tank gravimetric efficiency as a conservative baseline** when low boil-off and additional thermal protection are required. This value is treated in ADaPT as a technology/calibration baseline rather than a universal tank limit.

[18] U.S. Department of Energy, **Comparison of Fuel Cell Technologies / PEM Fuel Cell Efficiency Summaries**. Typical direct-hydrogen PEM electrical-efficiency range and LHV/HHV basis context.
