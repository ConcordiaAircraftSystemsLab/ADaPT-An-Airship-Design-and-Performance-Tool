# Turbine-Based Propulsion Architectures

These are two self-contained turbine-based propulsion architectures implemented in ADaPT:

- `Turboprop`
- `Turboelectric`

Both components replace the normal `Propulsion.py + Power.py` pairing for their respective architectures in case of airships using TURBOPROP or TURBOFAN, because the mechanical propulsion chain and fuel-conversion chain are tightly integrated inside a single component.

The two architectures share the same conceptual mission and power basis,

$$
P_{\mathrm{shaft}}
=
\frac{TV}{\eta_p},
$$

but differ in how that shaft-power requirement is produced.

For the turboprop architecture,

$$
\text{fuel}
\rightarrow
\text{gas-turbine core}
\rightarrow
\text{gearbox}
\rightarrow
\text{propeller}.
$$

For the turboelectric architecture,

$$
\text{fuel}
\rightarrow
\text{gas-turbine core}
\rightarrow
\text{generator}
\rightarrow
\text{electrical bus}
\rightarrow
\text{inverter}
\rightarrow
\text{motor}
\rightarrow
\text{gearbox}
\rightarrow
\text{propeller}.
$$

This page documents the common physical basis first, followed by the architecture-specific models.

---

# Literature Source — Turbine Propulsion Coefficients

The numerical baselines in this notebook are supported through a combination of Carichner and Nicolai, NASA/NACA propulsion literature, and Andrew Scott White's MIT thesis on electrified aircraft propulsion.

Key source support is:

- \(LHV_f=43~\mathrm{MJ/kg}\): literature value for aviation turbine fuel [R12, R13, R23].
- \(\eta_p=0.80\): representative conceptual propeller efficiency supported by NASA propeller studies [R2, R3].
- \(\eta_{th}=0.32\): conservative conceptual turboprop/turboshaft thermal-efficiency baseline; advanced transport-engine studies provide higher technology levels [R26].
- \(SP_{TS}=3.5~\mathrm{kW/kg}\): representative turbine-core specific power, supported by NASA turboshaft data and White's \(\sim4~\mathrm{kW/kg}\) LEAP-1B-based estimate [R14, R23].
- \(\eta_m=0.95\): directly consistent with the conventional aircraft-motor value used by White from Haran et al. [R23, R24].
- \(\eta_{gen}=0.96\): conservative relative to the \(0.98\) aircraft-generator value used by White from Zhang et al. [R23, R25].
- Motor, generator, inverter, propeller, nacelle, mount, wiring, and packaging coefficients are documented either as literature-supported technology values or concise conceptual-design assumptions with an engineering scaling rationale.

The source notes below give the reason for each coefficient in the same section where it is introduced.

# 1. Common Modeling Philosophy

Both components are conceptual multidisciplinary sizing models rather than detailed turbomachinery-cycle or propeller-design tools.

They use:

- mission thrust and speed to determine propeller shaft power,
- an explicit efficiency chain to propagate power upstream,
- fuel lower heating value and thermal efficiency to determine fuel flow,
- specific-power assumptions to size major propulsion hardware,
- simple installed-mass proxies for nacelles, propellers, mounts, wiring, and fuel-system hardware,
- a common conceptual propeller-diameter scaling.

The implementation was adapted from more detailed general-aircraft GPkit architecture models.

---


## Literature basis and provenance

The present component is intentionally a **conceptual sizing model**. This distinction is important because the literature does not support treating every numerical value below as a universal aircraft or airship constant.

The architecture and mass-estimation philosophy are consistent with established preliminary-design practice. NASA's WATE-2/WATE-S work develops component-level gas-turbine weight and dimensional estimates from physical design variables and existing-engine databases rather than relying on a single universal specific-power coefficient [R4, R5]. NASA also developed an explicit propeller/gearbox performance and weight extension to NNEP/WATE-2, using propeller maps and empirical propeller/gearbox weight equations [R6].

Accordingly, this notebook uses the following hierarchy:

1. **F — Fundamental:** equations that follow directly from energy, power, or efficiency definitions.
2. **L — Literature-supported:** numerical ranges or relationships directly supported by a cited source.
3. **A — Adapted:** a literature relationship simplified for the present conceptual model.
4. **C — Calibration/technology parameter:** a numerical value selected within a literature-supported technology range.
5. **AS — Assumption:** a value introduced for the ADaPT framework where no sufficiently direct source was found.
6. **N — Numerical safeguard:** bounds or clipping introduced only to keep the conceptual model numerically well behaved.

A value is therefore **not called literature-derived merely because a similar value exists somewhere in the literature**. When a coefficient is not directly transferable, it is explicitly identified as adapted, calibrated, or assumed.

# 2. Common Mission Shaft-Power Relation

For both architectures, mission propeller shaft power is

$$
\boxed{
P_{\mathrm{sh},i}
=
\frac{T_i V_i}{\eta_p}
}
\tag{EQ-1}
$$

where

- $T_i$ is total required thrust at mission point $i$,
- $V_i$ is true airspeed,
- $\eta_p$ is propeller efficiency.

This follows directly from

$$
\eta_p
=
\frac{TV}{P_{\mathrm{shaft}}}.
$$

Carichner and Nicolai use the same propulsive-efficiency definition for preliminary airship propeller design.

---


### Literature support

The above relation is a direct consequence of propulsive efficiency, and is therefore a **fundamental relation**, not an empirical coefficient. NASA's propeller documentation likewise distinguishes shaft power from useful thrust power and describes propeller thrust as the result of adding momentum/energy to the airflow [R1, R2].

For the numerical value of $\eta_p$, the present default of 0.80 is not treated as a universal airship value. NASA experimental work on advanced turboprops reported propeller net efficiencies near 80% under a specific high-speed, high-disk-loading test condition [R2, R3]. A separate NASA turboprop engine study assumed a combined propeller-and-gearbox efficiency of 0.86 [R7]. These sources support an efficiency of this order for well-designed propeller systems, but they do not prove that 0.80 applies at every airship flight condition. The present constant should therefore be regarded as a conceptual technology parameter (C) and replaced by a propeller map when higher fidelity is required.

# 3. Common Takeoff-Power Approximation

The axial takeoff thrust is

$$
\boxed{
T_{\mathrm{TO,axial}}
=
T_{\mathrm{TO}}\cos\theta_T
}
\tag{EQ-2}
$$

and the conceptual takeoff shaft power is

$$
\boxed{
P_{\mathrm{sh,TO}}
=
\frac{
T_{\mathrm{TO,axial}}V_{\mathrm{TO,eff}}
}
{\eta_p}.
}
\tag{EQ-3}
$$

Both components use

$$
V_{\mathrm{TO,eff}}=19~{\rm m/s}
$$

by default.

As documented for the baseline propulsion component, this is not a true static-thrust propeller equation. It is a conceptual installed-power sizing approximation, based on user settings

---

The use of an effective takeoff speed is a **conceptual approximation**, not a turboprop-specific physical law. NASA propeller literature emphasizes that propeller performance depends on operating condition, including speed and propeller loading [R1, R3, R6]. 

# 4. Installed-Power Requirement

The required installed shaft power is

$$
\boxed{
P_{\mathrm{sh,req}}
=
\max
\left(
\max_i P_{\mathrm{sh},i},
P_{\mathrm{sh,TO}}
\right).
}
\tag{EQ-4}
$$

Both components also accept an externally specified installed shaft power.

However, an important implementation distinction exists.

In the current turbine components, when

$$
P_{\mathrm{sh,installed}}\ge0,
$$

the model sets

$$
\boxed{
P_{\mathrm{sh,rated}}
=
P_{\mathrm{sh,installed}}
}
\tag{EQ-5}
$$

rather than taking the maximum of required and installed power.

This permits a validation mode in which the user imposes the actual installed rating of a reference vehicle.

The corresponding shortfall is

$$
\boxed{
P_{\mathrm{shortfall}}
=
P_{\mathrm{sh,req}}
-
P_{\mathrm{sh,rated}}.
}
\tag{EQ-6}
$$

Therefore,

$$
P_{\mathrm{shortfall}}>0
$$

indicates that the imposed installed rating is insufficient to meet the modeled mission/takeoff requirement.

This is intentionally different from the baseline `Propulsion.py` design-mode convention.

---

# 5. Common Propeller Diameter Approximation

Both components currently use

$$
\boxed{
D_{\mathrm{prop}}
=
\sqrt{
\frac{
P_{\mathrm{sh,rated,unit}}
}{
\rho_{\mathrm{ref}}
V_{\mathrm{ref}}^3
C_{\mathrm{model}}
}
}
}
\tag{EQ-7}
$$

with

$$
C_{\mathrm{model}}=0.65
$$

by default. This value should be calibrated against a selected propeller family or replaced by a standard map when propeller sizing becomes a design driver, or based on a specific case-study

The diameter is clipped to

$$
\boxed{
1\le D_{\mathrm{prop}}\le8~{\rm m}.
}
\tag{EQ-8}
$$

As with `Propulsion.py`, this is a framework-specific conceptual scaling relationship and is distinct from the standard nondimensional propeller power coefficient

$$
C_P
=
\frac{P}{\rho n^3D^5}.
$$

A future higher-fidelity model should preferably use propeller RPM, advance ratio, and standard propeller performance maps.

---





# Part I — Turboprop Architecture

# 6. Turboprop Scope

The `Turboprop` component represents a complete gas-turbine + gearbox + propeller propulsion group.

It replaces both `Propulsion.py` and `Power.py` when

```text
power_source = "turboprop"
```

because a simple turboprop does not contain an independent electrical propulsion bus.

The power chain is

$$
\boxed{
P_{\mathrm{shaft}}
\rightarrow
P_{\mathrm{core}}
\rightarrow
\dot m_f.
}
$$

---

# 7. Turboprop Inputs

### 7.1 Mission and Architecture Inputs

| Input | Symbol | Default | Units | Description |
|---|---:|---:|---:|---|
| `n_engine` | $N_e$ | 2 | – | Number of turboprop units |
| `thrust_cruise` | $T$ | 0 | N | Mission thrust history |
| `thrust_to` | $T_{TO}$ | 4400 | N | Total takeoff thrust |
| `tas` | $V$ | 19.5 | m/s | True airspeed history |
| `propeller_efficiency` | $\eta_p$ | 0.80 | – | Propeller efficiency |
| `gearbox_efficiency` | $\eta_g$ | 0.97 | – | Reduction-gear efficiency |
| `rho` | $\rho$ | 1.099 | kg/m³ | Atmospheric density |
| `thrust_vector_angle` | $\theta_T$ | 0 | deg | Thrust-vector angle |
| `installed_shaft_power` | $P_{\mathrm{installed}}$ | -1 | W | Optional imposed shaft rating |

### 7.2 Technology Inputs

| Input | Symbol | Default | Units |
|---|---:|---:|---:|
| `turboshaft_thermal_efficiency` | $\eta_{th}$ | 0.32 | – |
| `turboshaft_specific_power` | $SP_{TS}$ | 3500 | W/kg |
| `fuel_lhv` | $LHV_f$ | $43\times10^6$ | J/kg |

These are explicit technology parameters.

---


### Source status of numerical inputs

The mission values $T_{TO}=4400$ N, $V=19.5$ m/s, $\rho=1.099$ kg/m$^3$, and $N_e=2$ are **vehicle/scenario inputs**, not generic turboprop literature constants.

The default $\eta_p=0.80$ is a conceptual technology value supported in order of magnitude by NASA propeller studies, which report approximately 80% net propeller efficiency for advanced propellers at specific operating conditions [R2, R3]. It must nevertheless remain an input because propeller efficiency varies with advance ratio, disk loading, Reynolds number, Mach number, and installation.

The default gearbox efficiency $\eta_g=0.97$ is likewise treated as a **technology parameter (C)** rather than a universal constant. The need for reduction gearing in turboprops is well established by NASA [R0], while measured gearbox efficiency is configuration and operating-point dependent [R11].

# 8. Turboprop Core Shaft Power

The turbine core must supply the propeller shaft demand through the reduction gearbox.

Thus

$$
\boxed{
P_{\mathrm{core}}
=
\frac{P_{\mathrm{sh}}}
{\eta_g}.
}
\tag{TP-1}
$$

The rated core power is similarly

$$
\boxed{
P_{\mathrm{core,rated}}
=
\frac{P_{\mathrm{sh,rated}}}
{\eta_g}.
}
\tag{TP-2}
$$

Carichner and Nicolai note that turboprop engines typically include reduction gearing because turbine shaft speeds are far above practical propeller speeds.

---

# 9. Turboprop Fuel Flow

Thermal efficiency is defined as

$$
\eta_{th}
=
\frac{P_{\mathrm{core}}}
{\dot m_fLHV_f}.
$$

Therefore,

$$
\boxed{
\dot m_f
=
\frac{
P_{\mathrm{core}}
}{
\eta_{th}LHV_f
}.
}
\tag{TP-3}
$$

The default values are

$$
\eta_{th}=0.32
$$

and

$$
LHV_f=43~{\rm MJ/kg}.
$$

The relation is fundamental. The numerical efficiency is a technology assumption.

---


### Source and rationale

- **\(LHV_f=43~\mathrm{MJ/kg}\) [L]:** Standard aviation-turbine-fuel lower heating value used in NASA aircraft-energy studies and in White's turbine fuel-flow model [R12, R13, R23].
- **\(\eta_{th}=0.32\) [C]:** Representative conservative thermal-efficiency baseline for conceptual turboprop/turboshaft sizing; advanced transport gas-turbine literature provides higher values for larger, higher-performance engines [R14, R15, R26].
- **Fuel-flow relation [F/L]:** White uses the same gas-turbine relation \(\dot m_f=P_{\mathrm{core}}/(\eta_{th}LHV_f)\), providing direct literature support for the present formulation [R23].

# 10. Turboprop Overall Efficiency

The output `avg_efficiency` is

$$
\boxed{
\eta_{\mathrm{overall}}
=
\eta_{th}\eta_g.
}
\tag{TP-4}
$$

This represents the chemical-energy-to-propeller-shaft efficiency of the modeled chain, excluding propeller aerodynamic efficiency.

If thrust power were included, total fuel-to-thrust efficiency would additionally involve $\eta_p$.

---

# 11. Turboprop Core Mass

The turbine core mass is modeled using rated core power:

$$
\boxed{
m_{\mathrm{core}}
=
\frac{
P_{\mathrm{core,rated}}
}{
SP_{TS}
}.
}
\tag{TP-5}
$$

The default is

$$
SP_{TS}=3500~{\rm W/kg}.
$$

Carichner and Nicolai show that turboprop/turboshaft engines can have substantially higher specific power than reciprocating engines, but the current 3.5 kW/kg value should be treated as an explicit technology assumption rather than a direct transcription of a single literature point.

---


### Source and rationale for turbine-core specific power

- **\(SP_{TS}=3.5~\mathrm{kW/kg}\) [C/L-range]:** A representative conservative turbine-core specific-power baseline. NASA turboshaft data span this order of magnitude, while White derives approximately \(4~\mathrm{kW/kg}\) from LEAP-1B published mass and thrust data [R14, R23].

# 12. Turboprop Nacelle Mass

Per engine,

$$
\boxed{
m_{\mathrm{nac},1}
=
k_{\mathrm{nac,TP}}
\frac{
P_{\mathrm{core,rated}}/N_e
}{1000}.
}
\tag{TP-6}
$$

Total nacelle mass is

$$
\boxed{
m_{\mathrm{nac}}
=
N_e m_{\mathrm{nac},1}.
}
\tag{TP-7}
$$

The default coefficient is

$$
k_{\mathrm{nac,TP}}
=
1.1~{\rm kg/kW}.
$$

This is a conceptual/calibrated installation parameter.

---


### Source and rationale for turboprop nacelle mass

- **\(k_{\mathrm{nac,TP}}=1.1~\mathrm{kg/kW}\) [C/AS]:** A reasonable conceptual installation coefficient because turboprop nacelle structure, inlet/ducting, gearbox support, accessories, and thrust/torque load paths scale broadly with installed core power; NASA propulsion-installation studies support this first-order installed-mass scaling philosophy [R9, R10].

# 13. Turboprop Fuel-System and Accessory Mass

The variable fuel-system allowance is

$$
\boxed{
m_{\mathrm{fuel,var}}
=
k_{\mathrm{fuel}}
\frac{P_{\mathrm{core,rated}}}{1000}.
}
\tag{TP-8}
$$

The default coefficient is

$$
k_{\mathrm{fuel}}
=
0.01~{\rm kg/kW}.
$$

A fixed accessory allowance is added:

$$
m_{\mathrm{accessory}}=40~{\rm kg}.
$$

Therefore,

$$
\boxed{
m_{\mathrm{fuel\,sys}}
=
m_{\mathrm{fuel,var}}
+
m_{\mathrm{accessory}}.
}
\tag{TP-9}
$$

The fixed allowance conceptually represents items such as accessory gearbox, oil system, and FADEC.

---


### Source and rationale for fuel-system/accessory mass

- **\(k_{\mathrm{fuel}}=0.01~\mathrm{kg/kW}\) [C/AS]:** Represents the first-order growth of pumps, lines, controls, and fuel-handling hardware with installed engine power, consistent with subsystem-level installation scaling used in preliminary aircraft propulsion design [R4, R5, R10].
- **\(m_{\mathrm{accessory}}=40~\mathrm{kg}\) [C/AS]:** Provides a compact allowance for accessory gearbox, lubrication, FADEC, and fixed installation hardware whose mass changes more slowly than rated engine power at conceptual fidelity.

# 14. Turboprop Total Mass

The total turboprop propulsion/power-group mass is

$$
\boxed{
m_{\mathrm{total,TP}}
=
m_{\mathrm{core}}
+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}}
+
m_{\mathrm{fuel\,sys}}.
}
\tag{TP-10}
$$

The output

$$
m_{\mathrm{propulsion}}
$$

contains

$$
\boxed{
m_{\mathrm{propulsion}}
=
m_{\mathrm{core}}
+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}},
}
\tag{TP-11}
$$

while

$$
m_{\mathrm{power\,system}}
=
m_{\mathrm{fuel\,sys}}.
$$

This split preserves compatibility with the vehicle weight model.

---

# 15. Turboprop Power-System Volume

The packaging volume is approximated as

$$
\boxed{
V_{\mathrm{power}}
=
\frac{
P_{\mathrm{core,rated}}
}{
\Pi_{TP}
}.
}
\tag{TP-12}
$$

The default is

$$
\Pi_{TP}
=
800\,000~{\rm W/m^3}.
$$

This is a conceptual packaging proxy.

---


### Source and rationale for packaging volume

- **\(\Pi_{TP}=800~\mathrm{kW/m^3}\) [C/AS]:** A compact conceptual packaging density representing the combined turbine core, reduction gearbox, accessories, and installation volume; gas-turbine preliminary-design literature supports power/flow-based engine dimensional scaling [R4, R5].

# 16. Turboprop Outputs

| Output | Meaning |
|---|---|
| `shaft_power` | Mission propeller shaft-power history |
| `core_shaft_power` | Mission turbine-core power history |
| `fuel_flow` | Fuel mass-flow history |
| `avg_efficiency` | $\eta_{th}\eta_g$ |
| `takeoff_shaft_power` | Effective takeoff shaft power |
| `rated_shaft_power` | Installed propeller-shaft rating |
| `rated_core_power` | Installed turbine-core rating |
| `core_mass` | Total gas-turbine core mass |
| `nacelle_mass` | Total nacelle mass |
| `propeller_mass` | Total propeller mass |
| `pylon_mass` | Total mount mass |
| `fuel_system_mass` | Fuel/accessory-system mass |
| `total_mass` | Complete turboprop group mass |
| `propulsion_mass` | Core+nacelle+propeller+mount |
| `power_system_mass` | Fuel/accessory mass |
| `power_system_volume` | Packaging volume |
| `power_shortfall` | Required minus imposed rating |
| `propeller_diameter` | Conceptual propeller diameter |

---

# Part II — Turboelectric Architecture

# 17. Turboelectric Scope

The `Turboelectric` component models

$$
\boxed{
\text{gas turbine}
+
\text{generator}
+
\text{electrical bus}
+
\text{inverter}
+
\text{electric motor}
+
\text{propeller}.
}
$$

It is self-contained and replaces both `Propulsion.py` and `Power.py` for

```text
power_source = "turboelectric".
```

A defining feature is that the number of turbine-generator cores may differ from the number of propulsors:

$$
N_{\mathrm{engine}}
\ne
N_{\mathrm{propulsor}}.
$$

This allows distributed electric propulsion concepts such as two turbine-generator cores feeding four electric propulsors.

---

# 18. Turboelectric Inputs

### 18.1 Architecture Inputs

| Input | Symbol | Default |
|---|---:|---:|
| `n_engine` | $N_c$ | 2 |
| `n_propulsor` | $N_p$ | 2 |

Here,

- $N_c$ is the number of turbine-generator cores,
- $N_p$ is the number of motor/propeller units.

### 18.2 Mechanical and Electrical Efficiencies

| Input | Symbol | Default |
|---|---:|---:|
| propeller efficiency | $\eta_p$ | 0.80 |
| gearbox efficiency | $\eta_g$ | 1.00 |
| motor efficiency | $\eta_m$ | 0.95 |
| inverter efficiency | $\eta_{inv}$ | 0.98 |
| generator efficiency | $\eta_{gen}$ | 0.96 |
| turboshaft thermal efficiency | $\eta_{th}$ | 0.32 |

A gearbox efficiency of unity corresponds to direct-drive motor/propeller operation.

---


### Source and rationale for electric-drive efficiencies

- **\(\eta_m=0.95\) [L]:** Directly consistent with White's conventional aircraft-motor assumption sourced from Haran et al. [R23, R24].
- **\(\eta_{gen}=0.96\) [C/L-range]:** Conservative relative to White's \(0.98\) aircraft-generator value sourced from Zhang et al. [R23, R25].
- **\(\eta_{inv}=0.98\) [L/C]:** Representative of high-efficiency aerospace power electronics and consistent with NASA electrified-aircraft inverter studies [R17, R20, R21].
- **\(\eta_g=1.00\) [AS]:** Direct-drive motor/propeller assumption representing the baseline electric propulsor arrangement.
- **\(\eta_{th}=0.32\) [C]:** Representative conservative turbine-core thermal-efficiency baseline used consistently with the turboprop architecture.

# 19. Turboelectric Electrical Power

The component defines the combined downstream electric-drive efficiency as

$$
\boxed{
\eta_{\mathrm{drive}}
=
\eta_g\eta_m\eta_{inv}.
}
\tag{TE-1}
$$

The electrical-bus demand is

$$
\boxed{
P_{\mathrm{elec}}
=
\frac{
P_{\mathrm{sh}}
}{
\eta_g\eta_m\eta_{inv}
}.
}
\tag{TE-2}
$$

---


### Source and rationale

The relation

\[
P_{\mathrm{elec}}
=
\frac{P_{\mathrm{sh}}}{\eta_g\eta_m\eta_{inv}}
\]

is the direct component-efficiency energy balance for the electric-drive chain. White describes the same turbine-generator-electric-drive architecture, with shaft power converted to electrical power and delivered to motor-driven propulsors [R23].

# 20. Turboelectric Turbine-Core Power

The generator converts turbine mechanical power to electrical power.

Therefore,

$$
\boxed{
P_{\mathrm{core}}
=
\frac{
P_{\mathrm{elec}}
}{
\eta_{gen}
}
}
\tag{TE-3}
$$

or equivalently,

$$
\boxed{
P_{\mathrm{core}}
=
\frac{
P_{\mathrm{sh}}
}{
\eta_g\eta_m\eta_{inv}\eta_{gen}
}.
}
\tag{TE-4}
$$

The rated quantities follow the same efficiency chain:

$$
\boxed{
P_{\mathrm{elec,rated}}
=
\frac{
P_{\mathrm{sh,rated}}
}{
\eta_g\eta_m\eta_{inv}
}
}
\tag{TE-5}
$$

and

$$
\boxed{
P_{\mathrm{core,rated}}
=
\frac{
P_{\mathrm{elec,rated}}
}{
\eta_{gen}
}.
}
\tag{TE-6}
$$

This consistent propagation ensures that mission fuel flow and equipment sizing use the same physical chain.

---


### Source and rationale for generator conversion

- **\(\eta_{gen}=0.96\) [C/L-range]:** A conservative aircraft-generator baseline; White uses \(0.98\), sourced from Zhang et al. for large aircraft electric machines [R23, R25].
- **Generator power relation [F]:** \(P_{\mathrm{out}}=\eta_{gen}P_{\mathrm{in}}\) is the standard generator energy balance used in the turboelectric chain.

# 21. Turboelectric Fuel Flow

Fuel flow is

$$
\boxed{
\dot m_f
=
\frac{
P_{\mathrm{core}}
}{
\eta_{th}LHV_f
}.
}
\tag{TE-7}
$$

The default thermal efficiency is

$$
\eta_{th}=0.32,
$$

and the default fuel lower heating value is

$$
LHV_f=43~{\rm MJ/kg}.
$$

---


### Source and rationale

- **\(LHV_f=43~\mathrm{MJ/kg}\) [L]:** Standard aviation-turbine-fuel lower heating value used by NASA and White [R12, R13, R23].
- **\(\eta_{th}=0.32\) [C]:** Representative conservative turbine-core thermal-efficiency baseline for conceptual airship analysis.
- **Fuel-flow relation [F/L]:** White uses the same relation \(\dot m_f=P_{\mathrm{core}}/(\eta_{th}LHV_f)\) for gas-turbine fuel flow [R23].

# 22. Turboelectric Overall Efficiency

The component reports

$$
\boxed{
\eta_{\mathrm{overall}}
=
\eta_{th}
\eta_{gen}
\eta_{inv}
\eta_m
\eta_g.
}
\tag{TE-8}
$$

This represents fuel chemical energy to propeller shaft energy.

Again, propeller aerodynamic efficiency is separate.

---

### Source and rationale for overall efficiency

White's turboelectric architecture consists of gas-turbine shaft power, generator conversion, electrical transmission, motor conversion, and propulsor shaft power [R23]. Multiplying the component efficiencies is the corresponding reduced-order fuel-chemical-to-propeller-shaft efficiency.

# 23. Turboelectric Rated Power per Unit

Propeller-side rated power per electric propulsor is

$$
\boxed{
P_{\mathrm{sh,unit}}
=
\frac{
P_{\mathrm{sh,rated}}
}{
N_p
}.
}
\tag{TE-9}
$$

Turbine-core rated power per gas-generator unit is

$$
\boxed{
P_{\mathrm{core,unit}}
=
\frac{
P_{\mathrm{core,rated}}
}{
N_c
}.
}
\tag{TE-10}
$$

This distinction is fundamental to distributed turboelectric architectures.

---

# 24. Turboelectric Turbine-Core Mass

The total core mass is

$$
\boxed{
m_{\mathrm{core}}
=
\frac{
P_{\mathrm{core,rated}}
}{
SP_{\mathrm{core}}
}.
}
\tag{TE-11}
$$

The default is

$$
SP_{\mathrm{core}}
=
3500~{\rm W/kg}.
$$

---


### Source and rationale for turbine-core specific power

- **\(SP_{\mathrm{core}}=3.5~\mathrm{kW/kg}\) [C/L-range]:** Representative conservative gas-turbine-core specific power, supported by NASA turboshaft data and White's approximately \(4~\mathrm{kW/kg}\) LEAP-1B-based estimate [R14, R23].
- The same value is used for turboprop and turboelectric cores so architecture comparisons use a common turbine technology level.

# 25. Generator Mass

The total generator mass is

$$
\boxed{
m_{\mathrm{gen}}
=
\frac{
P_{\mathrm{elec,rated}}
}{
SP_{\mathrm{gen}}
}.
}
\tag{TE-12}
$$

The default generator specific power is

$$
SP_{\mathrm{gen}}
=
5000~{\rm W/kg}.
$$

This is an explicit technology assumption.

---


### Source and rationale for generator specific power

- **\(SP_{\mathrm{gen}}=5~\mathrm{kW/kg}\) [C/AS]:** A conservative conceptual installed-generator baseline. White uses \(20~\mathrm{N\,m/kg}\) specific torque and \(22{,}000~\mathrm{rpm}\), sourced from Zhang et al.; this supports substantial machine power density while retaining allowance for cooling, insulation, structure, and packaging at system level [R23, R25].

# 26. Inverter Mass

The inverter mass is

$$
\boxed{
m_{\mathrm{inv}}
=
\frac{
P_{\mathrm{elec,rated}}
}{
SP_{\mathrm{inv}}
}.
}
\tag{TE-13}
$$

The default is

$$
SP_{\mathrm{inv}}
=
10\,000~{\rm W/kg}.
$$

---


### Source and rationale for inverter specific power

- **\(SP_{\mathrm{inv}}=10~\mathrm{kW/kg}\) [C/L-range]:** A conservative conceptual aerospace inverter baseline; NASA electric-aircraft programs report demonstrated and targeted inverter specific powers around \(12\)–\(25~\mathrm{kW/kg}\), depending on cooling and technology level [R17, R20, R21].

# 27. Electric-Motor Mass

The motor mass is based on total rated propeller shaft power:

$$
\boxed{
m_{\mathrm{motor}}
=
\frac{
P_{\mathrm{sh,rated}}
}{
SP_{\mathrm{motor}}
}.
}
\tag{TE-14}
$$

The default is

$$
SP_{\mathrm{motor}}
=
5000~{\rm W/kg}.
$$

This is the combined total mass of all propulsion motors.

---


### Source and rationale for motor specific power

- **\(SP_{\mathrm{motor}}=5~\mathrm{kW/kg}\) [C/L-range]:** A conservative conceptual aircraft-motor baseline. White uses \(20~\mathrm{N\,m/kg}\) specific torque at approximately \(4000~\mathrm{rpm}\) for conventional motors, sourced from Haran et al.; the corresponding torque-speed scale is about \(8.4~\mathrm{kW/kg}\), providing strong order-of-magnitude support for the selected installed specific-power baseline [R23, R24].
- White also uses \(70~\mathrm{N\,m/kg}\) for superconducting motors, illustrating a higher technology level for future sensitivity studies [R23, R24].

# 28. Turboelectric Nacelle Mass

Nacelle mass is evaluated on a per-propulsor basis:

$$
\boxed{
m_{\mathrm{nac},1}
=
k_{\mathrm{nac,TE}}
\frac{
P_{\mathrm{sh,unit}}
}{
1000
}.
}
\tag{TE-15}
$$

The total is

$$
\boxed{
m_{\mathrm{nac}}
=
N_p m_{\mathrm{nac},1}.
}
\tag{TE-16}
$$

The default coefficient is

$$
k_{\mathrm{nac,TE}}
=
3.0~{\rm kg/kW}.
$$

This is a conceptual/calibrated parameter.

---


### Source and rationale for turboelectric nacelle mass

- **\(k_{\mathrm{nac,TE}}=3.0~\mathrm{kg/kW}\) [C/AS]:** A conservative distributed-electric-propulsor installation allowance that captures motor enclosure, nacelle structure, local supports, cooling interfaces, and propulsion-system integration; NASA installation studies support the strong configuration dependence of these masses [R9, R10].

# 29. Distributed Wiring Mass

A turboelectric architecture may place turbine-generator cores and propulsion motors far apart.

The current model therefore includes a distributed wiring allowance:

$$
\boxed{
m_{\mathrm{wire}}
=
k_{\mathrm{wire}}
\frac{
P_{\mathrm{elec,rated}}
}{
1000
}.
}
\tag{TE-17}
$$

The default is

$$
k_{\mathrm{wire}}
=
0.10~{\rm kg/kW}.
$$

This is a framework-specific installation assumption.

A higher-fidelity model would depend on:

- bus voltage,
- current,
- cable length,
- conductor material,
- allowable voltage drop,
- thermal limit,
- redundancy,
- shielding.

---


### Literature support for distributed wiring mass

The coefficient

\[
k_{\mathrm{wire}}=0.10~\mathrm{kg/kW}
\]

is a **framework-level conceptual allowance**. Aircraft electrification studies show that wiring, voltage, converter specific power, and power-distribution architecture are important system-level mass drivers [R20, R22], but the literature does not support one universal kg/kW coefficient independent of voltage, current, cable length, conductor material, shielding, cooling, and architecture.

The present coefficient should therefore be classified **AS/C**. A higher-fidelity model should calculate cable mass from voltage, current, route length, conductor allowable current density, shielding, and insulation requirements.

# 30. Turboelectric Fuel-System Mass

The variable fuel-system allowance is

$$
\boxed{
m_{\mathrm{fuel,var}}
=
k_{\mathrm{fuel}}
\frac{
P_{\mathrm{core,rated}}
}{
1000
}.
}
\tag{TE-18}
$$

A fixed accessory allowance is added:

$$
m_{\mathrm{accessory}}=40~{\rm kg}.
$$

Thus,

$$
\boxed{
m_{\mathrm{fuel\,sys}}
=
m_{\mathrm{fuel,var}}
+
m_{\mathrm{accessory}}.
}
\tag{TE-19}
$$

---

# 31. Turboelectric Total Group Mass

The complete turboelectric group mass is

$$
\boxed{
\begin{aligned}
m_{\mathrm{total,TE}}
={}&
m_{\mathrm{core}}
+
m_{\mathrm{gen}}
+
m_{\mathrm{inv}}
+
m_{\mathrm{motor}}\\
&+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}}
+
m_{\mathrm{wire}}
+
m_{\mathrm{fuel\,sys}}.
\end{aligned}
}
\tag{TE-20}
$$

---

# 32. Turboelectric Propulsion/Power Mass Split

For compatibility with the vehicle weight model, the architecture exposes two aggregate masses.

The mechanical/distributed propulsion mass is

$$
\boxed{
m_{\mathrm{propulsion}}
=
m_{\mathrm{motor}}
+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}}.
}
\tag{TE-21}
$$

The source/conversion-system mass is

$$
\boxed{
m_{\mathrm{power}}
=
m_{\mathrm{core}}
+
m_{\mathrm{gen}}
+
m_{\mathrm{inv}}
+
m_{\mathrm{wire}}
+
m_{\mathrm{fuel\,sys}}.
}
\tag{TE-22}
$$

Thus,

$$
m_{\mathrm{total,TE}}
=
m_{\mathrm{propulsion}}
+
m_{\mathrm{power}}.
$$

This split avoids double counting when the two aggregate outputs are connected to the weight model.

---

# 33. Turboelectric Power-System Volume

The packaging volume is

$$
\boxed{
V_{\mathrm{power}}
=
\frac{
P_{\mathrm{core,rated}}
}{
\Pi_{TE}
}.
}
\tag{TE-23}
$$

The default is

$$
\Pi_{TE}
=
500\,000~{\rm W/m^3}.
$$

This is a conceptual volumetric power-density assumption.

---


### Source and rationale for turboelectric packaging volume

- **\(\Pi_{TE}=500~\mathrm{kW/m^3}\) [C/AS]:** A conservative system-level packaging density for generator, inverter, motor, wiring, thermal-management, and installation hardware; aerospace electric-propulsion studies show that these components jointly drive mass and volume at architecture level [R18--R22].

# 34. Turboelectric Outputs

| Output | Meaning |
|---|---|
| `shaft_power` | Mission propeller shaft power |
| `electrical_power` | Mission electrical-bus demand |
| `core_shaft_power` | Mission turbine-core shaft power |
| `fuel_flow` | Fuel mass-flow history |
| `avg_efficiency` | Fuel-to-propeller-shaft efficiency |
| `rated_shaft_power` | Total installed propeller shaft rating |
| `rated_electrical_power` | Installed bus power |
| `rated_core_power` | Installed turbine-core power |
| `rated_core_power_per_unit` | Core rating per turbine |
| `core_mass` | Total turbine core mass |
| `generator_mass` | Total generator mass |
| `inverter_mass` | Total inverter mass |
| `motor_mass` | Total electric-motor mass |
| `nacelle_mass` | Total motor nacelle mass |
| `propeller_mass` | Total propeller mass |
| `pylon_mass` | Total mount mass |
| `wiring_mass` | Distributed electrical-bus wiring mass |
| `fuel_system_mass` | Fuel-system/accessory mass |
| `total_mass` | Complete turboelectric group mass |
| `propulsion_mass` | Motor-side propulsion mass |
| `power_system_mass` | Turbine/generator/electrical source mass |
| `power_system_volume` | Source-system packaging volume |
| `power_shortfall` | Required minus imposed shaft rating |
| `propeller_diameter` | Conceptual propeller diameter |

---

# 35. Turboprop versus Turboelectric Comparison

| Feature | Turboprop | Turboelectric |
|---|---|---|
| Gas turbine | Yes | Yes |
| Generator | No | Yes |
| Electrical bus | No | Yes |
| Inverter | No | Yes |
| Electric motor | No | Yes |
| Distributed propulsor count independent of core count | No | Yes |
| Gearbox | Turbine-to-propeller | Motor-to-propeller/direct drive |
| Fuel flow basis | Core shaft power | Core shaft power after electrical chain |
| Wiring mass | No | Yes |
| Main advantage represented | Simpler direct mechanical chain | Distributed propulsion flexibility |
| Main modeled penalty | Turbine/core + gearbox | Generator + inverter + motor + wiring losses/mass |

---

# 36. Physical Interpretation of Architecture Trade-Off

For identical propeller shaft power,

$$
P_{\mathrm{sh}},
$$

the turboprop requires turbine-core power

$$
P_{\mathrm{core,TP}}
=
\frac{P_{\mathrm{sh}}}{\eta_g}.
$$

The turboelectric architecture requires

$$
P_{\mathrm{core,TE}}
=
\frac{P_{\mathrm{sh}}}
{\eta_g\eta_m\eta_{inv}\eta_{gen}}.
$$

Therefore,

$$
P_{\mathrm{core,TE}}
>
P_{\mathrm{core,TP}}
$$

for efficiencies below unity.

The turboelectric architecture consequently incurs additional conversion losses.

It also introduces additional masses:

$$
m_{\mathrm{generator}},
\quad
m_{\mathrm{inverter}},
\quad
m_{\mathrm{motor}},
\quad
m_{\mathrm{wiring}}.
$$

Its benefit is not inherently lower fuel consumption in the present model. Its principal architectural advantage is the ability to decouple the number/location of gas-generator cores from the number/location of propulsors.

That flexibility may enable:

- distributed propulsion,
- improved installation,
- redundancy,
- propulsor placement flexibility,
- potentially reduced local nacelle/core constraints.

Those aerodynamic and system-level benefits would need to be modeled elsewhere to offset the electrical conversion penalties.

---

### White thesis support for the architecture trade

White's trade-space study shows that generators and motor-driven propulsors add conversion losses and mass, while distributed-propulsion integration, superconducting motors, and boundary-layer-ingestion benefits can compensate for part of those penalties [R23]. This supports treating turboelectric propulsion as an architecture whose value depends on both electrical-chain performance and aircraft-level integration benefits.

# 37. Turbine Technology Context

Carichner and Nicolai note that turboprop/turboshaft engines can offer substantially lower engine weight than equivalent piston engines, but historically their fuel consumption has often been less attractive for low-speed airship operation.

They also explain that turbine engines generally require reduction gearing because turbine shaft speed is much higher than suitable propeller rotational speed.

The present ADaPT model captures this trade through:

- explicit thermal efficiency,
- specific power,
- gearbox efficiency,
- fuel flow,
- installation masses.

It does not include a detailed Brayton-cycle model.

---


### Literature-supported interpretation of turbine technology

Carichner and Nicolai provide the airship-level propulsion context for turbine engines and reduction gearing [R0]. NASA turboshaft and turboprop studies provide engine power, weight, efficiency, and fuel-consumption ranges for conceptual design [R14, R15].

White's 2022 MIT thesis provides an additional transport-aircraft technology comparison set [R23]:

- gas-turbine specific power: approximately \(4~\mathrm{kW/kg}\);
- conventional motor specific torque: \(20~\mathrm{N\,m/kg}\);
- generator specific torque: \(20~\mathrm{N\,m/kg}\);
- superconducting motor specific torque: \(70~\mathrm{N\,m/kg}\);
- conventional motor efficiency: \(0.95\);
- generator efficiency: \(0.98\);
- superconducting motor efficiency: \(0.999\);
- motor speed: approximately \(4000~\mathrm{rpm}\);
- generator speed: approximately \(22{,}000~\mathrm{rpm}\);
- fuel LHV: \(43~\mathrm{MJ/kg}\) for ATF and \(120~\mathrm{MJ/kg}\) for hydrogen.

White also uses advanced transport-class gas-turbine thermal-efficiency levels of 0.50, 0.55, and 0.60 for conservative, projected, and optimistic cases [R23, R26]. These provide useful technology context alongside the present conservative airship baseline \(\eta_{th}=0.32\).

# 38. Multidisciplinary Coupling

The turbine architectures close the same core airship sizing loop:

$$
\boxed{
\begin{array}{c}
\text{Geometry + Aerodynamics + Mission}\\
\downarrow\\
T_{\mathrm{required}}\\
\downarrow\\
P_{\mathrm{shaft}}\\
\downarrow\\
\text{Turboprop or Turboelectric conversion}\\
\downarrow\\
\dot m_f,\;
m_{\mathrm{propulsion}},\;
m_{\mathrm{power}}\\
\downarrow\\
OEW,\ MTOW\\
\downarrow\\
\text{drag, buoyancy, mission power}\\
\circlearrowleft
\end{array}}
$$

Turboelectric additionally introduces an architectural coupling through distributed propulsion:

$$
N_{\mathrm{engine}}
\ne
N_{\mathrm{propulsor}}.
$$

This can affect propulsor rating, nacelle count, mounting mass, wiring mass, and installation trade space.

---

## 39. Assumptions and Literature Traceability

The following table summarizes the **source basis and engineering rationale** for each numerical baseline.

| Item | Turboprop | Turboelectric | Status | Evidence / justification |
|---|---:|---:|---|---|
| Propeller efficiency | 0.80 | 0.80 | C/L-range | NASA advanced propeller tests report net efficiencies near 80% at representative operating conditions [R2, R3]. |
| Gearbox efficiency | 0.97 | 1.00 | C / AS | Reduction gearing is physically required in conventional turboprops [R0]; numerical efficiency is operating/design dependent. Unity is direct-drive idealization. |
| Effective takeoff speed | 19 m/s | 19 m/s | AS | Conceptual low-speed takeoff sizing input consistent with the selected airship mission scale. |
| Propeller diameter coefficient | 0.65 | 0.65 | AS | Framework-specific scaling; standard literature uses $C_P$, $J$, RPM and propeller maps [R6]. |
| Propeller diameter bounds | 1--8 m | 1--8 m | N/AS | Numerical design bounds for conceptual sizing. |
| Propeller mass coefficient | $1.2\times10^{-4}$ kg/W | same | A/C | Simplified linearization; NASA uses power/diameter-based empirical propeller weight methods [R6, R8]. |
| Minimum propeller mass | 20 kg | 20 kg | N/AS | Numerical/conceptual lower bound. |
| Mount coefficient | 0.03 | 0.03 | AS | Installation mass is configuration dependent [R9, R10]. |
| Mount mass bounds | 15--75 kg | 15--75 kg | N/AS | Numerical safeguards. |
| Turbine thermal efficiency | 0.32 | 0.32 | C | Representative conservative turboprop/turboshaft technology level; NASA engine data provide supporting ranges [R14, R15]. |
| Fuel LHV | 43 MJ/kg | 43 MJ/kg | L | NASA uses approximately 43 MJ/kg for jet fuel [R12, R13]. |
| Turbine specific power | 3.5 kW/kg | 3.5 kW/kg | C/L-range | Within broad open NASA turboshaft engine database; strongly dependent on engine size/technology [R14]. |
| Turboprop nacelle coefficient | 1.1 kg/kW | -- | AS/C | Conceptual installation coefficient supported by the observed scaling of nacelle and installation hardware with propulsion-system size and power [R10]. |
| Turboelectric nacelle coefficient | -- | 3.0 kg/kW | AS/C | Architecture-specific installation allowance reflecting motor enclosure, nacelle structure, supports, and cooling interfaces [R9, R10]. |
| Fuel-system coefficient | 0.01 kg/kW | 0.01 kg/kW | AS/C | Conceptual first-order fuel-system scaling based on component-level propulsion installation modeling [R4, R5, R10]. |
| Fixed accessory mass | 40 kg | 40 kg | AS/C | Conceptual fixed allowance for accessory gearbox, lubrication, controls, and installation hardware. |
| Turboprop packaging density | 800 kW/m$^3$ | -- | AS/C | Conceptual packaging proxy based on propulsion-component dimensional scaling [R4, R5]. |
| Generator efficiency | -- | 0.96 | C | Conservative conceptual value within aircraft-generator technology ranges [R18, R19, R23, R25]. |
| Generator specific power | -- | 5 kW/kg | C/AS | Conservative installed electric-machine specific-power baseline supported by aircraft-machine technology studies [R18--R20, R23--R25]. |
| Inverter efficiency | -- | 0.98 | L/C | Consistent with NASA aircraft-electric studies and demonstrated X-57 controller performance [R16, R17]. |
| Inverter specific power | -- | 10 kW/kg | C/AS | Conservative relative to NASA 12--25 kW/kg targets and 18 kVA/kg demonstrated cryogenic inverter [R20, R21]. |
| Motor efficiency | -- | 0.95 | L/C | Used in NASA aircraft-electric conceptual analysis [R16]. |
| Motor specific power | -- | 5 kW/kg | C/AS | Conservative conceptual value relative to NASA electric-machine development targets [R18--R20]. |
| Wiring coefficient | -- | 0.10 kg/kW | AS/C | No universal kg/kW value; wiring depends strongly on voltage, current and route length [R20, R22]. |
| Turboelectric packaging density | -- | 500 kW/m$^3$ | AS/C | Framework-level packaging proxy; a representative conceptual-design value. |

### Important interpretation

The model should **not** state that all numerical defaults are "from the literature." The defensible statement is that the literature establishes the physical relationships and credible technology ranges, while several ADaPT coefficients are simplified/calibrated values selected to close a conceptual sizing model.

This distinction is particularly important for peer review because coefficients such as $k_{\mathrm{nac}}$, $k_{\mathrm{wire}}$, $\Pi$, $C_{\mathrm{model}}$, and the minimum/bound values are architecture- and implementation-dependent.

### White thesis evidence supporting the selected baselines

| Item | White thesis / underlying literature support | Status |
|---|---|---|
| Fuel LHV, 43 MJ/kg | Used directly in White's gas-turbine fuel-flow model [R23] | **L** |
| Turbine specific power, 3.5 kW/kg | White derives approximately 4 kW/kg from LEAP-1B data [R23] | **C/L-range** |
| Motor efficiency, 0.95 | White uses 0.95 from Haran et al. [R23, R24] | **L** |
| Generator efficiency, 0.96 | White uses 0.98 from Zhang et al.; 0.96 is retained as a conservative baseline [R23, R25] | **C/L-range** |
| Motor specific power, 5 kW/kg | White uses 20 N·m/kg at 4000 rpm for conventional motors [R23, R24] | **C/L-range/RO** |
| Generator specific power, 5 kW/kg | White uses 20 N·m/kg at 22,000 rpm for aircraft generators [R23, R25] | **C/AS/RO** |
| Turboelectric power chain | White describes turbine → generator → motor-driven propulsor power transmission [R23] | **F/L/A** |

# 40. Provenance Classification

| Label | Meaning |
|---|---|
| **F** | Fundamental physical relation |
| **L** | Directly supported by literature |
| **L-range** | Value lies within a literature-supported technology range, but is not a direct published coefficient |
| **A** | Adapted/simplified from a literature relationship |
| **C** | Calibration or technology parameter selected using literature evidence |
| **AS** | ADaPT modeling assumption with no sufficiently direct published source |
| **D** | Derived quantity |
| **N** | Numerical safeguard |

### Rule used in this documentation

A source is attached to a parameter when it supports one or more of the following:

- the exact equation;
- the exact numerical value;
- a documented range containing the selected value; or
- the physical dependency used to motivate the simplified relation.

Component-level sources are used to support numerical values, technology ranges, or the physical scaling adopted in the conceptual model.

### Literature hierarchy

1. Carichner and Nicolai for the airship conceptual-design context [R0].
2. NASA/NACA engine and propeller technical reports for aircraft propulsion correlations and real engine data [R4--R15].
3. NASA electric-aircraft research for motor, generator, inverter, and power-electronics technology levels [R16--R22].
4. Engineering assumptions and calibration parameters for concise conceptual-design quantities such as installation and packaging allowances.

# 40. Important Implementation Notes

## 40.1 Installed-rating behavior

In both turbine components, an explicitly supplied nonnegative `installed_shaft_power` is used directly.

Therefore,

$$
P_{\mathrm{shortfall}}>0
$$

is possible.

This is useful for reference-aircraft validation, but users performing unconstrained design optimization must ensure that the shortfall is constrained to

$$
P_{\mathrm{shortfall}}\le0.
$$

## 40.2 `motor_mass` alias in Turboprop

For compatibility with existing downstream wiring, the Turboprop component exposes

```text
motor_mass = core_mass
```

and

```text
prime_mover_mass = core_mass.
```

The variable name `motor_mass` is therefore only a backward-compatible alias in the turboprop architecture; physically it represents gas-turbine core mass.

## 40.3 `prime_mover_mass` alias in Turboelectric

In Turboelectric,

```text
prime_mover_mass = motor_mass
```

because the downstream propulsion-side prime mover is the electric motor.

The gas-turbine core belongs to the power-system side of the architecture.

## 40.4 Total mass ownership

For either architecture, downstream vehicle bookkeeping should use the architecture-specific `propulsion_mass` and `power_system_mass` outputs consistently.

Using `total_mass` in addition to both aggregates would double count the architecture mass.

---

# 41. Derivatives

Both components use finite-difference derivatives:

```python
self.declare_partials("*", "*", method="fd", step=1.0e-8)
```

so the perturbation is

$$
\Delta x=10^{-8}.
$$

Nonsmooth operations include:

- engine/propulsor count rounding,
- `max`,
- `clip`,
- imposed-rating switching,
- minimum propeller mass,
- mount-mass bounds,
- propeller-diameter bounds.

These should be considered during gradient-based optimization.

---



# 42. Recommended Future Refinements

Recommended upgrades include:

1. Add engine-deck model for gas-turbine performance.
2. Make thermal efficiency altitude-, Mach-, and power-dependent.
3. Replace constant specific power with technology maps or engine database interpolation.
4. Replace the conceptual propeller-diameter model with a standard $C_P$/advance-ratio method.
5. Add RPM, tip-Mach, noise, and blade-loading constraints.
6. Add static-thrust modeling for takeoff.
7. Add generator-specific efficiency and mass maps versus speed/loading.
8. Add inverter and motor efficiency maps.
9. Replace wiring kg/kW with voltage/current/length-based cable sizing.
10. Add cooling-system mass and parasitic power for turboelectric architectures.
11. Model generator redundancy and fault-tolerant electrical buses.
12. Couple distributed propulsor placement to aerodynamic interference and structural effects.
13. Model turbine exhaust residual thrust if relevant.
14. Replace finite-difference derivatives with analytic or complex-step-compatible derivatives for smooth relations.

---


### Literature-driven future refinements

The highest-value refinements are:

1. Replace constant $\eta_{th}$ with an engine deck.
2. Replace constant $\eta_p$ with a $C_T(J)$/$C_P(J)$ propeller map.
3. Replace the linear propeller-mass relation with a published power/diameter-based correlation [R6, R8].
4. Replace constant turbine specific power with interpolation of an open engine database such as the NASA RVLT models [R14].
5. Replace nacelle and mount coefficients with geometry-based installation models [R9, R10].
6. Replace constant generator/motor/inverter specific powers with technology-specific values from the selected electric-machine technology level [R18--R22].
7. Replace the wiring kg/kW proxy with a voltage/current/length-based cable model.
8. Replace the single packaging-density coefficient with component envelopes and installation clearances.

These changes would improve fidelity without changing the architecture-level formulation of ADaPT.

# 43. References

**[R0]** Carichner, G. E., and Nicolai, L. M., *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013, ISBN 978-1-60086-898-6.  
Publisher information: https://www.aiaa.org/docs/default-source/uploadedfiles/publications/aerospace-america-december-2013.pdf

**[R1]** NASA Glenn Research Center, “Propeller Thrust,” Beginner's Guide to Aeronautics.  
https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/

**[R2]** Mikkelson, D. C., Blaha, B. J., Mitchell, G. A., and Wikete, J. E., “Design and Performance of Energy Efficient Propellers for Mach 0.8 Cruise,” SAE Paper 770458, NASA Technical Reports Server, 1977.  
https://ntrs.nasa.gov/search.jsp?R=19770054225

**[R3]** Black, D. M., Menthe, R. W., and Wainauski, H. S., “Aerodynamic Design and Performance Testing of an Advanced 30 Deg Swept, Eight Bladed Propeller at Mach Numbers from 0.2 to 0.85,” NASA-CR-3047, 1978.  
https://ntrs.nasa.gov/citations/19780024123

**[R4]** Pera, R. J., Onat, E., Klees, G. W., and Tjonneland, E., “A Method to Estimate Weight and Dimensions of Aircraft Gas Turbine Engines, Volume 1: Method of Analysis,” NASA-CR-135170, 1977.  
https://ntrs.nasa.gov/citations/19770018227

**[R5]** Hale, P. L., “A Method to Estimate Weight and Dimensions of Small Aircraft Propulsion Gas Turbine Engines: User's Guide,” NASA-CR-168049, 1982.  
https://ntrs.nasa.gov/citations/19830008072

**[R6]** Plencner, R. M., Senty, P., and Wickenheiser, T. J., “Propeller Performance and Weight Predictions Appended to the Navy/NASA Engine Program,” NASA-TM-83458, 1983.  
https://ntrs.nasa.gov/citations/19830024539

**[R7]** NASA/NACA technical report, turboprop engine performance analysis, reporting an assumed combined propeller and gearbox efficiency of 0.86 for the investigated turboprop model.  
https://ntrs.nasa.gov/api/citations/19930090341/downloads/19930090341.pdf

**[R8]** NASA, “Propulsion System Weight” section of aircraft preliminary-design study, reporting the empirical propeller-weight relation $W_p=0.2515(SHP)^{1.04}$.  
https://ntrs.nasa.gov/api/citations/19790009677/downloads/19790009677.pdf

**[R9]** Waters, M. H., and Schairer, E. T., “Analysis of Turbofan Propulsion System Weight and Dimensions,” NASA-TM-X-73199, 1977.  
https://ntrs.nasa.gov/citations/19770012125

**[R10]** NASA advanced turboprop/prop-fan installation-weight study, documenting the separation of bare engine, propeller, gearbox, nacelle and installation-system weights and reporting historical installation-weight relationships.  
https://ntrs.nasa.gov/api/citations/19760022145/downloads/19760022145.pdf

**[R11]** Howe, D. C., Sundt, C. V., and McKibbon, A. H., “AGBT Advanced Counter-Rotating Gearbox Detailed Design Report,” NASA-CR-180883, 1988.  
https://ntrs.nasa.gov/citations/19940005945

**[R12]** Datta, A., et al., NASA technical report discussing aviation fuel energy content and using approximately 43 MJ/kg for jet fuel/kerosene.  
https://ntrs.nasa.gov/api/citations/20210000284/downloads/1502_Datta__CR%2020210000284_081821.pdf

**[R13]** NASA technical report on turboshaft-engine dynamics, listing aviation-fuel LHV = 43.1 MJ/kg.  
https://ntrs.nasa.gov/api/citations/20120002627/downloads/20120002627.pdf

**[R14]** Snyder, C. A., “Modeling Turboshaft Engines for the Revolutionary Vertical Lift Technology Project,” NASA technical report, 2019; expanded version subsequently extended the database to approximately 200--15,000 shaft horsepower.  
https://ntrs.nasa.gov/citations/20190025407  
Expanded model: https://ntrs.nasa.gov/citations/20230006287

**[R15]** NASA, “Turboprop Candidate Engine Characteristics,” technical report containing candidate-engine shaft power, shaft SFC, and engine-weight data.  
https://ntrs.nasa.gov/api/citations/19810010591/downloads/19810010591.pdf

**[R16]** Bowles, J. V., Fong, R. K., Schuh, M. J., Pham, D. D. V., and Kuptsov, V., NASA work on electrified/all-electric aircraft conceptual design; representative aircraft-level assumptions include approximately 95% motor efficiency and 97% inverter efficiency.  
https://ntrs.nasa.gov/citations/20230017408  
Related NASA electric-aircraft study: https://ntrs.nasa.gov/api/citations/20150000747/downloads/20150000747.pdf

**[R17]** Kowalewski, S., et al., “NASA's X-57 High Lift Motor Controller: Detailed Design, Test Results, and Outcomes,” NASA NTRS, 2024; reported 14 kW, 1 kg and 98.3% controller efficiency.  
https://ntrs.nasa.gov/citations/20240008854

**[R18]** NASA, “Electromagnetic Redesign of NASA's High Efficiency Megawatt Motor,” NTRS, 2020; HEMM target greater than 16 kW/kg and greater than 98% efficiency.  
https://ntrs.nasa.gov/citations/20205004521

**[R19]** Tallerico, T., Anderson, A. D., Scheidler, J. J., Jansen, R., and Sixel, W., “Concept Design of a 5 MW Partially Superconducting Generator,” NASA NTRS, 2023; predicted 22.3 kW/kg and 99.1% efficiency after higher-fidelity analysis.  
https://ntrs.nasa.gov/citations/20230006340

**[R20]** Woodworth, A., NASA's Electric Aircraft Propulsion Research: Yesterday, Today and Tomorrow; NASA presentation documenting aircraft electric-machine and inverter specific-power/efficiency goals.  
https://ntrs.nasa.gov/api/citations/20230008891/downloads/Woodworth_PEASA%202023%20Keynote-STI-Final.pdf

**[R21]** Chen, R., Niu, J., Ren, R., Gui, H., Wang, F., Tolbert, L., Choi, B., and Brown, G., “A Cryogenically-Cooled MW Inverter for Electric Aircraft Propulsion,” AIAA Propulsion and Energy Forum, 2020; demonstrated approximately 18 kVA/kg and 99% efficiency.  
https://ntrs.nasa.gov/citations/20205005738

**[R22]** NASA, “Overview of NASA Electrified Aircraft Propulsion Research,” documenting aircraft electric-powertrain development and the importance of converter efficiency, voltage, and power density.  
https://ntrs.nasa.gov/api/citations/20170006235/downloads/20170006235.pdf

## Source-use note

The references above are used conservatively. They support the physical formulation, documented technology ranges, or the type of dependency being modeled. They are **not** cited as proof of an exact ADaPT coefficient unless the source actually reports that coefficient. 

**[R23]** White, A. S., *Trade-Space Analysis of Liquid Hydrogen Propulsion Systems for Electrified Aircraft*, S.M. Thesis, Department of Aeronautics and Astronautics, Massachusetts Institute of Technology, 2022. Used for gas-turbine specific power, gas-turbine fuel-flow formulation, conventional motor/generator technology values, electric-machine speeds, fuel heating values, and turboelectric architecture interpretation.

**[R24]** Haran, K. S., Kalsi, S., Arndt, T., Karmaker, H., Badcock, R., Buckley, B., Haugan, T., Izumi, M., Loder, D., Bray, J. W., Masson, P., and Stautner, E. W., “High Power Density Superconducting Rotating Machines—Development Status and Technology Roadmap,” *Superconductor Science and Technology*, Vol. 30, No. 12, 2017. Source used by White for conventional and superconducting motor torque-density and efficiency technology context.

**[R25]** Zhang, X., Bowman, C. L., O'Connell, T. C., and Haran, K. S., “Large Electric Machines for Aircraft Electric Propulsion,” *IET Electric Power Applications*, Vol. 12, No. 6, pp. 767–779, 2018, doi:10.1049/iet-epa.2017.0639. Source used by White for aircraft-generator specific torque and efficiency.

**[R26]** Epstein, A. H., “Aeropropulsion for Commercial Aviation in the Twenty-First Century and Research Directions Needed,” *AIAA Journal*, Vol. 52, No. 5, pp. 901–911, 2014, doi:10.2514/1.J052713. Source used by White for advanced transport gas-turbine thermal-efficiency projections.
