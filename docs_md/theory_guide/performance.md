# Airship Performance and Mission Feasibility

The `AirshipPerformance` component is the universal **vehicle-level quasi-steady performance and feasibility model** used by ADaPT. It connects buoyancy, aerodynamic lift and drag, mission shaft-power demand, mission energy, installed-power feasibility, externally sized resource capacity, takeoff and landing performance, climb/descent behavior, and turning performance.

The current component is architecture neutral at the force and energy-demand level. It supports non-rigid, semi-rigid, and rigid airships. Propulsion and energy architecture enter through externally supplied installed shaft power, propeller characteristics, required/installed consumable and battery masses, usable-energy quantities, and architecture-selection options.

The principal literature basis is Carichner and Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies* [1], especially Chapter 4 and the integrated Chapter-11 conceptual-design example.

A central responsibility boundary is:

> **Performance calculates what the vehicle requires and whether the configured vehicle is feasible.**

All feasibility outputs use

$$
\boxed{
g\le0
}
$$

as the feasible convention.

---

## 0. Literature Traceability and Parameter-Provenance Framework

The Performance component is a **conceptual/quasi-steady model**, so not every numerical value has the same evidentiary status. The documentation therefore distinguishes:

1. **Direct literature relationship (L):** explicitly given in a cited source.
2. **Adapted literature relationship (A):** literature relation adapted to ADaPT bookkeeping/interfaces.
3. **Reference/design input (C):** tied to a particular reference airship or worked example.
4. **Modeling assumption (AS):** introduced because higher-fidelity data are unavailable; exposed as an input so it can be replaced.

The principal reference is Carichner and Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*. Its Chapter 4 covers airship performance, including drag, optimum speeds, climb/descent, takeoff, landing, and turning; Chapter 11 applies these methods to conceptual airship design. [1]

Independent NASA studies also use $V^{2/3}$ as the aerodynamic reference area and empirical airship drag methods, while Hoerner gives the same volumetric drag-coefficient convention. [2--4] Historical full-scale NACA tests and FAA airship guidance show that turning behaviour is configuration-dependent and should not be represented as a universal aircraft-style manoeuvring law. [5,6]

Thus, the documentation does **not** treat every coefficient as a universal constant. Where literature supports an equation but not a numerical value, the numerical value is explicitly labelled as an ADaPT assumption or calibration parameter.

## 1. Model Scope

The component owns:

- takeoff buoyancy requirement and available buoyant lift,
- cruise mission mass history,
- cruise heaviness and buoyancy ratio,
- aerodynamic lift coefficient required for equilibrium,
- three cruise-speed strategies,
- airship drag,
- required cruise thrust,
- required propeller shaft power,
- mission duration,
- shaft-energy integration,
- installed-power feasibility,
- externally sized fuel/hydrogen/battery feasibility,
- hybrid energy-consistency diagnostics,
- gas inertial mass treatment for accelerated phases,
- calculated or fixed takeoff speed,
- takeoff thrust selection hierarchy,
- ground roll, rotation, and obstacle-climb distance,
- climb angle and rate of climb,
- landing speed and distance,
- landing buoyancy-ratio and ballast requirements,
- minimum-power descent speed and rate of descent,
- conceptual turning radius/speed/time,
- optional pressure-control power and energy.


---
### Evidence boundary

The model is a **conceptual synthesis of established airship performance equations**. The strongest literature support is for the governing relations and airship-specific methodology in [1]. Independent NASA and historical sources are used to cross-check reference-area conventions, drag modelling, propulsion modelling, and turning behaviour [2--6].

Where the literature does not provide a defensible universal number, ADaPT keeps the quantity as an exposed parameter and labels it as an assumption.

## 2. Model Fidelity

`AirshipPerformance` is a **conceptual/quasi-steady** model.

It evaluates equilibrium, force, power, and energy relationships at a finite set of representative mission nodes.

The principal theoretical framework includes:

- buoyancy ratio and heaviness,
- aerodynamic lift required to support heaviness,
- parabolic airship drag polar,
- minimum-drag and minimum-power flight,
- shaft-power demand,
- distance-based mission integration,
- takeoff ground roll,
- rotation and obstacle clearance,
- landing approach and braking,
- rate of climb/descent,
- empirical turning performance.

This fidelity is appropriate for multidisciplinary conceptual design and architecture screening.

---

## 3. Architecture Support

The performance component recognizes the following energy-source groups.

### 3.1 Fuel / Consumable Architectures

```text
conventional_reciprocating
turboprop
turboelectric
hydrogen_reciprocating
hydrogen_fuel_cell
```

### 3.2 Battery-Dominant Architectures

```text
battery_only
solar_battery
solar-RFC
```

### 3.3 Hybrid Architectures

```text
hydrogen_hybrid
solar_hydrogen_hybrid
conventional_battery_hybrid
```



Structural type is independently selected as

$$
\boxed{
\text{non-rigid},\quad
\text{semi-rigid},\quad
\text{rigid}.
}
\tag{EQ-1}
$$

---

## 4. Principal Component Options

| Option | Default | Description |
|---|---:|---|
| `power_source` | `conventional_reciprocating` | Architecture/resource-feasibility selection |
| `num_steps` | 1 | Number of mission nodes |
| `landing_system` | `conventional` | Conventional gear or ACLS |
| `airship_type` | `non-rigid` | Non-rigid, semi-rigid, or rigid |
| `C_L_takeoff` | 0.10 | Aerodynamic lift coefficient available at takeoff |
| `C_L_max` | 0.60 | Magnitude limit for cruise aerodynamic lift coefficient |
| `field_length_limit` | 450 m | Takeoff/landing feasibility limit |
| `takeoff_speed_method` | `calculated` | Calculated or fixed takeoff speed |
| `takeoff_speed` | 19 m/s | Fixed value used only in fixed-speed mode |
| `takeoff_speed_factor` | 1.10 | Multiplier on calculated takeoff reference speed |
| `takeoff_average_speed_ratio` | $\sqrt{0.5}$ | Representative ground-run speed / $V_{TO}$ |
| `rotation_time` | 3 s | Rotation-time assumption |
| `obstacle_height` | 15.24 m | 50-ft obstacle |
| `takeoff_friction_coefficient` | 0.03 | Conventional brakes-off rolling resistance |
| `braking_friction_coefficient` | 0.30 | Landing braking coefficient |
| `reverse_thrust_fraction` | 0.60 | Fraction of available takeoff thrust used in reverse |
| `landing_approach_angle_deg` | 3 deg | Conceptual landing approach angle |
| `landing_free_roll_time` | 3 s | Free-roll transition time |
| `landing_field_factor` | $1/0.60$ | Landing-distance to field-length factor |
| `gas_masses_in_mtow` | `False` | Gas-inertial-mass bookkeeping convention |
| `takeoff_thrust_method` | `auto` | External, actuator disk, or power/speed fallback |
| `actuator_disk_power_efficiency` | 0.75 | Shaft-to-air-power factor for actuator disk |
| `minimum_thrust_speed` | 8 m/s | Final compatibility fallback speed floor |
| `turn_radius_to_length_ratio` | 2.7 | Conceptual $R/L$ turning parameter |
| `enable_pressure_control` | `False` | Enables pressure-control accounting |
| `pressure_control_base_power` | 0 W | Fixed pressure-control power |
| `pressure_control_fraction_of_prop_power` | 0 | Fraction of propulsion shaft power |

For Chapter-11 A-170 replication, the code notes that

$$
C_{L,TO}=0.175
$$

may be obtained from

$$
C_{L_\alpha}=0.0175/\deg
$$

and a $10^\circ$ scrape angle. The default 0.10 is therefore an implementation baseline, not a universal takeoff coefficient.

---

## 5. Principal OpenMDAO Inputs

### 5.1 Mission Inputs

| Input | Symbol | Default | Units |
|---|---:|---:|---:|
| `range` | $R$ | 1,342,100 | m |
| `cruise_altp` | $h_c$ | 914 | m |
| `cruise_disa` | $\Delta T$ | 0 | K |
| `cruise_speed` | $V_c$ | 31 | m/s |
| `n_engine` | $N_p$ | 2 | – |
| `mission_mass` | $m_i$ | -1 | kg |

A positive mission-mass vector is used directly. Negative values request an internally generated mission-mass history.

### 5.2 Geometry Inputs

| Input | Symbol | Units | Current role |
|---|---:|---:|---|
| `aerodynamic_reference_area` | $S_{\rm ref}$ | m² | Primary aerodynamic reference area |
| `gross_volume` | $V$ | m³ | Gross envelope/hull volume |
| `fin_area` | – | m² | Compatibility input |
| `planform_area` | $S_{\rm ref,fb}$ | m² | Fallback aerodynamic reference area |
| `aspect_ratio` | – | – | Compatibility input |
| `length` | $L$ | m | Turn-radius scaling |
| `ballonet_volume` | $V_B$ | m³ | Compatibility gas-volume fallback |
| `lifting_gas_volume_takeoff` | $V_{g,TO}$ | m³ | Preferred takeoff lifting-gas volume |

A very important current convention is that **both lift and drag use the same selected aerodynamic reference area**:

$$
\boxed{
S_{\rm ref}
=
\begin{cases}
\texttt{gross\_area},&\texttt{gross\_area}>0,\\
\texttt{planform\_area},&\text{otherwise}.
\end{cases}
}
\tag{EQ-2}
$$

In the integrated ADaPT group, these names are intended to carry the airship coefficient reference area $V^{2/3}$, not hull wetted area.

### 5.3 Mass and Gas-State Inputs

| Input | Symbol | Units |
|---|---:|---:|
| `operational_mass` | $m_{\rm op}$ | kg |
| `mtow` | $m_{TO}$ | kg |
| `he_max_mass` | $m_{\rm He}$ | kg |
| `ballast_mass` | $m_{\rm ballast}$ | kg |
| `ballonet_air_mass_takeoff` | $m_{B,air,TO}$ | kg |

`operational_mass` remains a compatibility input; current mission calculations primarily use MTOW and the optional mission-mass history.

### 5.4 Propulsion Inputs

| Input | Symbol | Units |
|---|---:|---:|
| `installed_shaft_power` | $P_{\rm inst}$ | W |
| `takeoff_thrust_available` | $T_{TO,\rm ext}$ | N |
| `propeller_diameter` | $D_p$ | m |
| `propeller_efficiency` | $\eta_p$ | – |

### 5.5 Atmosphere Inputs

| Input | Symbol | Units |
|---|---:|---:|
| `pamb_cruise` | $p_i$ | Pa |
| `tamb_cruise` | $T_i$ | K |
| `pamb_to` | $p_{TO}$ | Pa |
| `tamb_to` | $T_{TO}$ | K |

The performance component does not duplicate an ISA model. It receives atmospheric pressure/temperature from the shared atmosphere framework and uses the common `phd.gas_density()` property model to obtain air and helium density.

### 5.6 Aerodynamic and Control Inputs

| Input | Default | Meaning |
|---|---:|---|
| `lift_coeff` | 0.15 | Retained compatibility/design input |
| `drag_due_to_lift_factor` | 0.869 | $K$ |
| `drag_coeff_zero` | 0.03542 | $C_{D0}$ |
| `BR_takeoff` | 0.856 | Selected takeoff buoyancy ratio |
| `BR_landing` | 0.90 | Landing buoyancy-ratio target/limit |
| `tailwind_speed` | 0 m/s | Current signed wind input |
| `thrust_vector_angle` | 0 deg | Propulsive vector angle |
| `rudder_deflection` | 28 deg | Compatibility/turning input |
| `cruise_strategy` | 1 | 1 prescribed, 2 min drag, 3 min power |
| `landing_lift_coefficient` | -1 | Negative uses $C_{L,TO}$ |

### 5.7 External Resource Inputs

| Input | Units | Meaning |
|---|---:|---|
| `required_consumable_mass` | kg | Required fuel/hydrogen from authoritative source |
| `installed_consumable_mass` | kg | Installed fuel/hydrogen capacity |
| `consumable_mass_used` | kg | Mission consumable actually used |
| `required_battery_mass` | kg | Required battery mass |
| `installed_battery_mass` | kg | Installed battery mass |
| `installed_primary_usable_energy` | Wh | Usable primary-source energy |
| `installed_battery_usable_energy` | Wh | Usable battery energy |
| `solar_energy_recovered` | Wh | Recovered solar energy |
| `chi` | – | Target energy hybridization fraction |
| `tau` | – | Power hybridization fraction |
| `eta_fc_dynamic` | – | Optional dynamic fuel-cell-efficiency history |

---

## 6. Atmospheric and Gas-Property Coupling

The component obtains air density from

$$
\boxed{
\rho_{air,i}
=
\rho_{\rm gas}
(p_i,T_i,\text{air})
}
\tag{EQ-3}
$$

and takeoff helium density from

$$
\boxed{
\rho_{\rm He,TO}
=
\rho_{\rm gas}
(p_{TO},T_{TO},\text{helium}).
}
\tag{EQ-4}
$$

The physical-property implementation belongs to the shared `phd` object. The performance component therefore remains focused on vehicle physics rather than duplicating thermodynamic-property code.

---

## 7. Buoyancy Ratio and Heaviness

Carichner and Nicolai define buoyancy ratio as

$$
\boxed{
BR
=
\frac{L_B}{W}.
}
\tag{EQ-5}
$$

Heaviness is

$$
\boxed{
W_H
=
W-L_B
=
W(1-BR).
}
\tag{EQ-6}
$$

Heaviness is the portion of vehicle mass that must be supported aerodynamically for level equilibrium.

A key airship distinction is:

$$
\boxed{
L_B
\not\rightarrow
K C_L^2.
}
$$

Buoyant lift does not create aerodynamic induced drag. Only the aerodynamic lift required to support heaviness enters the $KC_L^2$ term.

---
### Interpretation of the numerical BR values

The equations for buoyancy ratio and heaviness are directly treated by Carichner and Nicolai. [1] The **numerical values** in ADaPT have different provenance:

- `BR_takeoff = 0.856` is a design/reference input for the current ADaPT baseline.
- `BR_landing = 0.90` is a landing-state target/limit.

They should not be described as universal optimum buoyancy ratios. The appropriate values depend on payload, aerodynamic lift capability, takeoff/landing system, ballast strategy, and mission fuel burn. [12]

**Provenance:** L/F for definitions; C/AS for present numerical targets.

## 8. Takeoff Buoyancy Requirement

The selected takeoff buoyancy ratio defines the **required** buoyant lift:

$$
\boxed{
L_{B,\rm req,TO}
=
BR_{TO}m_{TO}g.
}
\tag{EQ-7}
$$

Takeoff heaviness is

$$
\boxed{
W_{H,TO}
=
m_{TO}g-L_{B,\rm req,TO}
=
m_{TO}g(1-BR_{TO}).
}
\tag{EQ-8}
$$

The implementation clips

$$
0\le BR_{TO}<1
$$

for numerical stability.

---

## 9. Takeoff Lifting-Gas Volume

The current hierarchy is:

### 9.1 Preferred Direct Geometry Input

If

$$
V_{g,TO,\rm input}\ge0,
$$

then

$$
\boxed{
V_{g,TO}
=
V_{g,TO,\rm input}.
}
\tag{EQ-9}
$$

This is the preferred interface from the Geometry model.

### 9.2 Helium-Mass Reconstruction

If direct gas volume is unavailable but

$$
m_{\rm He}>0,
$$

then

$$
\boxed{
V_{g,TO}
=
\frac{m_{\rm He}}
{\rho_{\rm He,TO}}.
}
\tag{EQ-10}
$$

### 9.3 Compatibility Fallback

If neither is available,

$$
\boxed{
V_{g,TO}
=
\max
(V-V_B,0).
}
\tag{EQ-11}
$$

The result is physically safeguarded to

$$
0\le V_{g,TO}\le V.
$$

This assumes gross hull volume was always the helium volume.

---

## 10. Available Buoyant Lift

With the actual takeoff lifting-gas volume,

$$
\boxed{
L_{B,\rm avail,TO}
=
\left(
\rho_{air,TO}V_{g,TO}
-
m_{\rm He}
\right)g.
}
\tag{EQ-12}
$$

This is equivalent to

$$
(\rho_{air}-\rho_{\rm He})Vg
$$

when the helium mass and gas volume are thermodynamically consistent.

The buoyancy feasibility constraint is

$$
\boxed{
g_B
=
L_{B,\rm req,TO}
-
L_{B,\rm avail,TO}.
}
\tag{EQ-13}
$$

Feasibility requires

$$
g_B\le0.
$$

Thus the selected buoyancy ratio defines what the design **requires**, while the geometry/gas state defines what the design can **actually provide**.

---

## 11. Mission Buoyant Force

For pressure-regulated conceptual mission analysis, the current model assumes buoyant force remains approximately constant:

$$
\boxed{
L_{B,\rm mission}
=
L_{B,\rm req,TO}.
}
\tag{EQ-14}
$$

The separate buoyancy constraint ensures that the actual takeoff gas state can supply this selected design value.

As mission mass decreases through consumable burn,

$$
BR_i
=
\frac{L_{B,\rm mission}}{m_i g}
$$

therefore changes.

This is more physically transparent than assuming a constant buoyancy ratio throughout the mission.

---
### Literature/assumption distinction

Treating mission buoyant force as approximately constant is a **modeling assumption**, not a universal property of all airships. It is reasonable for the present conceptual model when the lifting-gas state is pressure-regulated and the design intent is to hold selected buoyant lift approximately fixed while consumable mass changes. The resulting BR then changes with vehicle mass.

A pressure/temperature-resolved gas-dynamics model would instead compute buoyant force as a time-varying state.

## 12. Mission Mass History

If every supplied mission-mass value is positive,

$$
\boxed{
m_i
=
m_{i,\rm supplied}.
}
\tag{EQ-15}
$$

Otherwise the model estimates landing mass from mission consumable used:

$$
\boxed{
m_L
=
\max
(m_{TO}-m_{\rm cons,used},1).
}
\tag{EQ-16}
$$

For one mission node,

$$
\boxed{
m_1
=
\frac{m_{TO}+m_L}{2}.
}
\tag{EQ-17}
$$

For multiple nodes, mass is linearly distributed from $m_{TO}$ to $m_L$:

$$
\boxed{
m_i
=
\operatorname{linspace}
(m_{TO},m_L,N).
}
\tag{EQ-18}
$$

This is a conceptual mission-mass history.

---

## 13. Cruise Heaviness and Buoyancy Ratio

At each node,

$$
\boxed{
W_{H,i}
=
m_i g
-
L_{B,\rm mission}.
}
\tag{EQ-19}
$$

The corresponding cruise buoyancy ratio is

$$
\boxed{
BR_i
=
\frac{
L_{B,\rm mission}
}{
m_i g
}.
}
\tag{EQ-20}
$$

Negative heaviness is preserved. A state with

$$
W_H<0
$$

corresponds to

$$
BR>1,
$$

meaning the vehicle is statically light and requires negative aerodynamic lift or ballast/control action.

The model deliberately does not silently clip this physical condition away.

---

## 14. Aerodynamic Reference-Area Convention

The airship drag polar is referenced to

$$
\boxed{
S_{\rm ref}=V^{2/3}.
}
\tag{EQ-21}
$$

In the current implementation, the OpenMDAO name `aerodynamic_reference_area` is a backward-compatible interface name and is intended to carry this **aerodynamic reference area**, not external hull wetted area.

Both aerodynamic lift and drag use the same selected $S_{\rm ref}$:

$$
\boxed{
L_A=qS_{\rm ref}C_L,
}
\tag{EQ-22}
$$

$$
\boxed{
D=qS_{\rm ref}C_D.
}
\tag{EQ-23}
$$





---
Carichner and Nicolai use volume-to-the-two-thirds-power as the principal airship aerodynamic reference quantity. [1] Independent NASA airship studies make the same choice explicitly, and Hoerner identifies the volumetric drag coefficient as the preferred airship convention. [2--4]

Therefore a coefficient derived with $V^{2/3}$ cannot be combined with wetted area without redefining the coefficient. The present use of one $S_{\rm ref}=V^{2/3}$ for lift and drag is consistent with the cited airship literature.

**Provenance:** L for reference-area convention; D for the software interface name.

## 15. Dynamic Pressure

At each mission node,

$$
\boxed{
q_i
=
\frac12\rho_iV_i^2.
}
\tag{EQ-24}
$$

This is fundamental aerodynamic theory.

---

## 16. Airship Drag Polar

The current model uses

$$
\boxed{
C_D
=
C_{D0}
+
KC_L^2.
}
\tag{EQ-25}
$$

This is the conventional parabolic airship aerodynamic polar described by Carichner and Nicolai.

The critical interpretation is

$$
C_L=C_{L,\rm aerodynamic},
$$

not total lift including buoyancy.

Thus,

$$
\boxed{
D
=
qS_{\rm ref}
\left(
C_{D0}
+
KC_L^2
\right).
}
\tag{EQ-26}
$$

The default values

$$
C_{D0}=0.03542,
\qquad
K=0.869
$$

are ADaPT baseline aerodynamic inputs. 

This distinction is particularly important for BASI MB-30T, where current mission-power feasibility remains sensitive to these generic aerodynamic assumptions.

---
### Literature justification for the parabolic polar

The form $C_D=C_{D0}+KC_L^2$ is a low-order representation of airship drag due to aerodynamic lift. NASA airship design work uses quadratic drag-due-to-lift relations for preliminary estimates, while more detailed studies show that airship zero-lift drag depends strongly on fineness ratio, Reynolds number, fins, gondola, propulsion installations, and interference. [2--4]


**Provenance:** L for polar form; C/AS for the numerical values.

## 17. Cruise Strategy 1 — Prescribed Speed

For

```text
cruise_strategy = 1
```

the selected mission speed is

$$
\boxed{
V_i
=
V_{c,i}.
}
\tag{EQ-27}
$$

The required aerodynamic lift coefficient is evaluated **point by point**:

$$
\boxed{
C_{L,i}
=
\frac{
W_{H,i}
}{
q_iS_{\rm ref}
}.
}
\tag{EQ-28}
$$


Consequently, changes in mission mass, air density, or speed can modify $C_L$ at each node while maintaining quasi-steady vertical force balance.

---

## 18. Cruise Strategy 2 — Minimum Drag / Maximum Aerodynamic $L/D$

For the parabolic polar,

$$
C_D=C_{D0}+KC_L^2,
$$

minimum drag / maximum aerodynamic $L/D$ occurs at

$$
\boxed{
|C_{L,D_{\min}}|
=
\sqrt{
\frac{C_{D0}}{K}
}.
}
\tag{EQ-29}
$$

The sign follows the sign of heaviness:

$$
\boxed{
C_{L,i}
=
\operatorname{sgn}(W_{H,i})
\sqrt{
\frac{C_{D0}}{K}
}.
}
\tag{EQ-30}
$$

The corresponding speed is

$$
\boxed{
V_{D_{\min},i}
=
\sqrt{
\frac{
2|W_{H,i}|
}{
\rho_iS_{\rm ref}|C_{L,D_{\min}}|
}
}.
}
\tag{EQ-31}
$$

The implementation applies a numerical minimum speed of 0.5 m/s.

---

## 19. Cruise Strategy 3 — Minimum Power / Maximum Endurance

For the same parabolic polar, minimum propulsive power occurs at

$$
\boxed{
|C_{L,P_{\min}}|
=
\sqrt{
\frac{
3C_{D0}
}{K}
}.
}
\tag{EQ-32}
$$

Again,

$$
\boxed{
C_{L,i}
=
\operatorname{sgn}(W_{H,i})
|C_{L,P_{\min}}|.
}
\tag{EQ-33}
$$

The corresponding speed is

$$
\boxed{
V_{P_{\min},i}
=
\sqrt{
\frac{
2|W_{H,i}|
}{
\rho_iS_{\rm ref}|C_{L,P_{\min}}|
}
}.
}
\tag{EQ-34}
$$

This strategy represents the low-order maximum-endurance condition for the adopted parabolic polar.

---

## 20. Cruise Drag and Thrust

After the cruise strategy determines $V_i$ and $C_{L,i}$,

$$
\boxed{
q_i
=
\frac12\rho_iV_i^2,
}
$$

$$
\boxed{
C_{D,i}
=
C_{D0}+KC_{L,i}^2,
}
$$

and

$$
\boxed{
D_i
=
q_iS_{\rm ref}C_{D,i}.
}
\tag{EQ-35}
$$

For quasi-steady level flight,

$$
\boxed{
T_{\rm req,i}
=
D_i.
}
\tag{EQ-36}
$$

The implementation safeguards the thrust requirement as nonnegative.

---

## 21. Required Shaft Power

Using propeller efficiency,

$$
\boxed{
\eta_p
=
\frac{TV}{P_{\rm shaft}},
}
\tag{EQ-37}
$$

so

$$
\boxed{
P_{\rm shaft,req,i}
=
\frac{
T_{\rm req,i}V_i
}{
\eta_p
}.
}
\tag{EQ-38}
$$

The current implementation clips

$$
0.05\le\eta_p\le0.99
$$

for numerical protection.



---
### Literature justification for propulsive efficiency

The relation $P_{\rm shaft}=TV/\eta_p$ is the definition of propulsive efficiency. Airship-specific propulsion studies calculate propeller efficiency from thrust/power coefficients and advance ratio rather than treating efficiency as a universal constant. [8,9] A representative conceptual airship treatment uses a propulsive efficiency of 0.80, illustrating that values around 0.7--0.8 can be reasonable for preliminary work but are configuration-dependent. [10]

## 22. Mission Distance, Time, and Wind Convention

The current signed ground-speed relation is

$$
\boxed{
V_{g,i}
=
\max
(V_i-V_w,0.5).
}
\tag{EQ-39}
$$

Thus a **positive** `tailwind_speed` currently reduces ground speed.

Accordingly, despite its historical name, the present sign convention behaves as:

$$
\boxed{
V_w>0
\quad\Rightarrow\quad
\text{headwind magnitude}.
}
$$

This should either be renamed in future software or documented consistently. Until then, validation scripts should explicitly state the sign convention.

---

## 23. Distance-Based Mission Integration

The mission route is divided into equal-distance segments:

$$
\boxed{
\Delta R
=
\frac{R}{N}.
}
\tag{EQ-40}
$$

Time at each node is

$$
\boxed{
\Delta t_i
=
\frac{\Delta R}{V_{g,i}}.
}
\tag{EQ-41}
$$

Mission duration is

$$
\boxed{
t_m
=
\sum_i\Delta t_i.
}
\tag{EQ-42}
$$

Endurance is

$$
\boxed{
E_t
=
\frac{t_m}{3600}.
}
\tag{EQ-43}
$$


---

## 24. Mission Shaft Energy

Distance-based integration gives

$$
\boxed{
E_{\rm shaft}
=
\sum_i
P_{\rm shaft,req,i}\Delta t_i.
}
\tag{EQ-44}
$$


This integration is exact for the adopted piecewise-constant node representation when each node corresponds to an equal fraction of route distance.

---

## 25. Installed-Power Feasibility

At each mission node,

$$
\boxed{
g_{P,i}
=
P_{\rm shaft,req,i}
-
P_{\rm shaft,installed}.
}
\tag{EQ-45}
$$

Feasibility requires

$$
g_{P,i}\le0
\qquad
\forall i.
$$

The output is a mission vector.

A positive value means the prescribed installed mechanical power is insufficient for that mission condition.

This is a capacity check; it does not automatically resize the published/reference installation.

---

## 26. Aerodynamic-Lift Feasibility

The current constraint is

$$
\boxed{
g_L
=
\max_i
|C_{L,i}|
-
C_{L,\max}.
}
\tag{EQ-46}
$$

Thus both positive and negative aerodynamic-lift requirements are checked.

Feasibility requires

$$
g_L\le0.
$$

This is important for both heavy $BR<1$ and potentially statically light $BR>1$ states.

---

## 27. External Resource Feasibility

Performance does not independently recreate fuel, hydrogen, or battery sizing.

### 27.1 Primary Consumable Constraint

$$
\boxed{
g_{E,p}
=
m_{\rm cons,req}
-
m_{\rm cons,inst}.
}
\tag{EQ-47}
$$

### 27.2 Battery Constraint

$$
\boxed{
g_{E,b}
=
m_{b,\rm req}
-
m_{b,\rm inst}.
}
\tag{EQ-48}
$$

### 27.3 Architecture-Level Energy Constraint

For fuel/consumable architectures,

$$
\boxed{
g_E=g_{E,p}.
}
\tag{EQ-49}
$$

For battery architectures,

$$
\boxed{
g_E=g_{E,b}.
}
\tag{EQ-50}
$$

For hybrids,

$$
\boxed{
g_E
=
\max(g_{E,p},g_{E,b}).
}
\tag{EQ-51}
$$

Therefore both required resources must be individually feasible in a hybrid case.

---

## 28. Hybrid Energy-Consistency Diagnostics

The usable-energy accounting is

$$
\boxed{
E_{\rm total}
=
E_{\rm primary}
+
E_{\rm battery}
+
E_{\rm solar}.
}
\tag{EQ-52}
$$

The battery-energy fraction implied by installed capacities is

$$
\boxed{
\chi_{\rm implied}
=
\frac{
E_{\rm battery}
}{
E_{\rm total}
}.
}
\tag{EQ-53}
$$

The consistency error is

$$
\boxed{
\epsilon_\chi
=
\chi_{\rm implied}
-
\chi_{\rm target}.
}
\tag{EQ-54}
$$

The power hybridization quantity

$$
\tau
$$

is separately clipped to 0–1 and reported as `tau_used`.

Therefore,

$$
\boxed{
\chi\ne\tau
}
\tag{EQ-55}
$$

in general:

- $\chi$: energy hybridization,
- $\tau$: power allocation/hybridization.

For a supplied dynamic fuel-cell-efficiency vector, valid nonnegative entries are averaged:

$$
\boxed{
\eta_{\rm FC,used}
=
\operatorname{mean}
(\eta_{\rm FC,dynamic}\ge0).
}
\tag{EQ-56}
$$

This is a reporting diagnostic rather than a fuel-cell stack model.

---

## 29. Gas Inertial Mass Convention

Carichner and Nicolai's takeoff derivation accelerates the vehicle and lifting/ballonet gas masses.

The current option

```text
gas_masses_in_mtow
```

makes this bookkeeping explicit.

### 29.1 Ballonet-Air Mass

If `ballonet_air_mass_takeoff` is supplied as a nonnegative value,

$$
m_{B,air,TO}
=
m_{B,air,\rm supplied}.
$$

Otherwise, for non-rigid and semi-rigid vehicles,

$$
\boxed{
V_{B,air,TO}
=
\max
(V-V_{g,TO},0),
}
\tag{EQ-57}
$$

$$
\boxed{
m_{B,air,TO}
=
\rho_{air,TO}V_{B,air,TO}.
}
\tag{EQ-58}
$$

For rigid airships,

$$
\boxed{
m_{B,air,TO}=0.
}
\tag{EQ-59}
$$

### 29.2 Accelerated Mass

If gas masses are already included in MTOW,

$$
\boxed{
m_{\rm accel,TO}
=
m_{TO}.
}
\tag{EQ-60}
$$

Under the current ADaPT/book convention, helium and ballonet air are excluded from MTOW, so

$$
\boxed{
m_{\rm accel,TO}
=
m_{TO}
+
m_{\rm He}
+
m_{B,air,TO}.
}
\tag{EQ-61}
$$

This distinction is essential for consistency with the mass model, where helium is not included in OEW/MTOW.

---
### Literature justification

Carichner and Nicolai's takeoff derivation explicitly separates vehicle mass from the masses of envelope/ballonet gases so that accelerated mass is not inadvertently omitted. [1]

The `gas_masses_in_mtow` switch is therefore a bookkeeping consistency control: gas mass must neither be counted twice nor omitted from inertial mass when excluded from MTOW.

**Provenance:** L/A.

## 30. Calculated Takeoff Speed

The default method is

```text
takeoff_speed_method = "calculated".
```

For positive takeoff heaviness,

$$
\boxed{
V_{TO}
=
k_{TO}
\sqrt{
\frac{
2W_{H,TO}
}{
\rho_{air,TO}
S_{\rm ref}
C_{L,TO}
}
}.
}
\tag{EQ-62}
$$

The default is

$$
k_{TO}=1.10.
$$

If

$$
W_{H,TO}\le0,
$$

the calculated takeoff reference speed is set to zero.

The compatibility mode

```text
takeoff_speed_method = "fixed"
```

uses the configured fixed value directly.



---
### Parameter source

The calculated $V_{TO}$ follows the airship condition that aerodynamic lift balances heaviness; Carichner and Nicolai formulate takeoff speed from heaviness and takeoff lift coefficient rather than prescribing one universal speed. [1]

Two values must be distinguished:

- `C_L_takeoff = 0.175` is from Chapter-11 documented in the implementation: $0.0175/\mathrm{deg}\times10^\circ=0.175$.
- The general default `C_L_takeoff = 0.10` is an ADaPT conceptual assumption, not a universal literature constant.

The additional factor $k_{TO}=1.10$ is also an **ADaPT design margin**.

**Provenance:** L/A for governing relation; C for sample value; AS for general default and 1.10 margin.

## 31. Representative Ground-Run Speed

Carichner and Nicolai use approximately

$$
0.707V_{TO}
$$

as a representative ground-run speed.

The current default is exactly

$$
\boxed{
V_{\rm avg,TO}
=
\sqrt{0.5}\,V_{TO}
\approx
0.7071V_{TO}.
}
\tag{EQ-63}
$$

This corrects the older documentation that described 0.7 rather than the current $\sqrt{0.5}$ default.

Dynamic pressure is

$$
\boxed{
q_{\rm avg,TO}
=
\frac12
\rho_{air,TO}
V_{\rm avg,TO}^2.
}
\tag{EQ-64}
$$

---
### Literature justification

Carichner and Nicolai use approximately $0.707V_{TO}$ as the representative ground-run speed and state that evaluating acceleration there approximates the time-wise integration well. [1] The implementation uses the mathematically equivalent $\sqrt{0.5}V_{TO}=0.7071068V_{TO}$.

**Provenance:** L.

## 32. Takeoff Aerodynamic Lift and Drag

Average aerodynamic lift is

$$
\boxed{
L_{A,\rm avg,TO}
=
q_{\rm avg,TO}
S_{\rm ref}
C_{L,TO}.
}
\tag{EQ-65}
$$

Average drag is

$$
\boxed{
D_{\rm avg,TO}
=
q_{\rm avg,TO}
S_{\rm ref}
\left(
C_{D0}
+
KC_{L,TO}^2
\right).
}
\tag{EQ-66}
$$

The same aerodynamic reference area is used for both quantities.

---

## 33. Takeoff Thrust Hierarchy

The current model hierarchy is:

$$
\boxed{
\text{external thrust}
\rightarrow
\text{actuator disk}
\rightarrow
\text{finite-speed power fallback}.
}
\tag{EQ-67}
$$

### 33.1 External Thrust

If a nonnegative external thrust is supplied and the selected method allows it,

$$
\boxed{
T_{TO}
=
T_{TO,\rm ext}.
}
\tag{EQ-68}
$$

This is the preferred path when a propeller or propulsion model can supply low-speed thrust.

### 33.2 Actuator-Disk Fallback

When propeller diameter is available, each propeller has disk area

$$
\boxed{
A_p
=
\frac{\pi D_p^2}{4}.
}
\tag{EQ-69}
$$

Per-unit shaft power is

$$
P_{\rm sh,each}
=
\frac{P_{\rm installed}}{N_p}.
$$

The air power used by the idealized disk is

$$
\boxed{
P_{\rm air}
=
\eta_{AD}P_{\rm sh,each}.
}
\tag{EQ-70}
$$

The actuator-disk relation solved numerically is

$$
\boxed{
P_{\rm air}
=
2\rho A
v_i
(V+v_i)^2.
}
\tag{EQ-71}
$$

After finding induced velocity $v_i$,

$$
\boxed{
T
=
2\rho A
v_i
(V+v_i).
}
\tag{EQ-72}
$$

The total thrust is the sum over propulsors.

This is a low-order physics fallback, not a substitute for a full propeller map.

### 33.3 Final Compatibility Fallback

If neither external thrust nor usable propeller diameter is available,

$$
\boxed{
T
=
\frac{
P_{\rm installed}\eta_p
}{
\max(V,V_{\min})
}.
}
\tag{EQ-73}
$$

with

$$
V_{\min}=8\ {\rm m/s}
$$

by default.

This final path is retained only for compatibility and avoids the singularity of $P/V$ at static conditions.

---

## 34. Thrust Vectoring

The total selected thrust magnitude is resolved into

$$
\boxed{
T_H
=
T\cos\theta_T,
}
\tag{EQ-74}
$$

$$
\boxed{
T_V
=
T\sin\theta_T.
}
\tag{EQ-75}
$$

Horizontal thrust accelerates the vehicle and overcomes drag.

Positive vertical thrust reduces the normal heaviness carried by the landing system during the ground roll.

---

## 35. Takeoff Rolling Resistance

For conventional landing gear,

$$
\boxed{
N_{\rm wheel}
=
\max
\left(
W_{H,TO}
-
L_{A,\rm avg,TO}
-
\max(T_V,0),
0
\right).
}
\tag{EQ-76}
$$

Rolling resistance is

$$
\boxed{
F_f
=
\mu_{TO}N_{\rm wheel}.
}
\tag{EQ-77}
$$

The default

$$
\mu_{TO}=0.03
$$

is consistent with the Chapter-4 hard-surface conceptual example/range.

For ACLS,

$$
\boxed{
\mu_{TO}=0.
}
\tag{EQ-78}
$$

---
### Literature justification for friction coefficients

The default takeoff rolling-friction coefficient $\mu_{TO}=0.03$ is supported by Carichner and Nicolai Table 4.3: concrete/macadam brakes-off resistance is listed as 0.015--0.04. [1]

The default braking coefficient $\mu_{\rm brake}=0.30$ is also directly within the table: 0.3--0.6 for fully applied wheel braking on concrete/macadam and 0.30 for firm, dry dirt. [1]

These are **surface-dependent coefficients**, not airship constants. For a real runway, surface, tire, brake, and environmental conditions should determine the value.

**Provenance:** L for ranges; C/AS for single-point selection.

## 36. Takeoff Acceleration and Ground Roll

Net horizontal accelerating force is

$$
\boxed{
F_{\rm net}
=
T_H
-
D_{\rm avg,TO}
-
F_f.
}
\tag{EQ-79}
$$

If

$$
F_{\rm net}>0,
$$

then

$$
\boxed{
a_{TO}
=
\frac{
F_{\rm net}
}{
m_{\rm accel,TO}
}.
}
\tag{EQ-80}
$$

Ground roll is

$$
\boxed{
S_G
=
\frac{
V_{TO}^2
}{
2a_{TO}
}.
}
\tag{EQ-81}
$$

If $V_{TO}=0$, ground roll is zero.

If $V_{TO}>0$ but

$$
F_{\rm net}\le0,
$$

the code deliberately returns

$$
\boxed{
S_G=10^9\ {\rm m}
}
\tag{EQ-82}
$$

as an infeasibility/penalty value rather than pretending a physically non-accelerating aircraft can take off.



---
### Literature justification

The ground-roll relation is a reduced form of the book's airship force balance: thrust minus drag and rolling resistance, evaluated at approximately $0.707V_{TO}$. [1]

The $10^9$ m value used when net accelerating force is non-positive is **not a physical distance**; it is a numerical infeasibility penalty.

**Provenance:** L/A for force model; N for penalty.

## 37. Rotation Distance

The current relation is

$$
\boxed{
S_R
=
t_{\rm rot}V_{TO}.
}
\tag{EQ-83}
$$

The default

$$
t_{\rm rot}=3\ {\rm s}
$$

gives

$$
S_R=3V_{TO},
$$

consistent with the conceptual certification-style assumption discussed by Carichner and Nicolai.

---
### Literature justification

Carichner and Nicolai state that certification agencies use an approximately 3-s time increment for rotation and give $S_R=t_{ROT}V_{TO}$ with $t_{ROT}\approx3$ s. [1]

**Provenance:** L.

## 38. Climbout Force Balance

At $V_{TO}$,

$$
\boxed{
D_{TO}
=
q_{TO}
S_{\rm ref}
(C_{D0}+KC_{L,TO}^2).
}
\tag{EQ-84}
$$

The excess horizontal force is

$$
\boxed{
F_{\rm excess}
=
T_H-D_{TO}.
}
\tag{EQ-85}
$$

The current model uses the **dimensionally consistent** climb-force relation

$$
\boxed{
\sin\gamma
=
\frac{
T_H-D_{TO}
}{
W_{H,TO}
}.
}
\tag{EQ-86}
$$

This is consistent with the book's rate-of-climb equation and deliberately avoids copying the apparent dimensional inconsistency in the printed Chapter-4 climbout-angle expression.

The value is numerically limited before inverse sine.

The climb gradient is

$$
\boxed{
G_{TO}
=
\tan\gamma.
}
\tag{EQ-87}
$$

---
### Literature justification

The book's airship climbout relation uses excess thrust over drag divided by heaviness to obtain the dimensionless climb-angle relation and then uses $\tan\gamma$ for climbout distance. [1] The 50-ft (15.24-m) obstacle height is also taken from the book's analysis.

**Provenance:** L/A.

## 39. Climbout Distance and Total Takeoff Distance

For positive climb gradient,

$$
\boxed{
S_{CL}
=
\frac{
h_{\rm obs}
}{
\tan\gamma
}.
}
\tag{EQ-88}
$$

If no positive climbout gradient exists,

$$
\boxed{
S_{CL}=10^9\ {\rm m}
}
\tag{EQ-89}
$$

as an infeasibility penalty.

The total takeoff distance is

$$
\boxed{
S_{TO}
=
S_G
+
S_R
+
S_{CL}.
}
\tag{EQ-90}
$$

The field-length constraint is

$$
\boxed{
g_G
=
S_{TO}
-
S_{\rm field,max}.
}
\tag{EQ-91}
$$

Feasibility requires

$$
g_G\le0.
$$

`ground_roll_distance` is used as **ground roll only**, not total takeoff distance.

---

## 40. Rate of Climb

Using the same climb force balance,

$$
\boxed{
ROC
=
V_{TO}\sin\gamma.
}
\tag{EQ-92}
$$

This is dimensionally consistent:

$$
[{\rm m/s}]
=
[{\rm m/s}]
\times[-].
$$

---

## 41. Landing Mass and Buoyancy State

Landing mass is estimated as

$$
\boxed{
m_L
=
\max
(m_{TO}-m_{\rm cons,used},1).
}
\tag{EQ-93}
$$

Landing mass is

$$
W_L=m_Lg.
$$

With the constant mission buoyant force,

$$
\boxed{
W_{H,L}
=
W_L
-
L_{B,\rm mission}.
}
\tag{EQ-94}
$$

The implied landing buoyancy ratio is

$$
\boxed{
BR_{L,\rm implied}
=
\frac{
L_{B,\rm mission}
}{
W_L
}.
}
\tag{EQ-95}
$$

The landing BR constraint is

$$
\boxed{
g_{BR,L}
=
BR_{L,\rm implied}
-
BR_{L,\rm target}.
}
\tag{EQ-96}
$$

A positive value means the actual landing buoyancy ratio exceeds the selected target/limit.

---

## 42. Ballast Requirement

If the unballasted landing vehicle becomes statically light,

$$
W_{H,L}<0,
$$

the required ballast is

$$
\boxed{
m_{\rm ballast,req}
=
\max
\left(
-\frac{W_{H,L}}{g},
0
\right).
}
\tag{EQ-97}
$$

The ballast feasibility constraint is

$$
\boxed{
g_{\rm ballast}
=
m_{\rm ballast,req}
-
m_{\rm ballast,available}.
}
\tag{EQ-98}
$$

---

## 43. Landing Reference Speed

The landing lift coefficient is

$$
C_{L,L}
=
\begin{cases}
C_{L,TO},&
\texttt{landing\_lift\_coefficient}\le0,\\
C_{L,L,\rm supplied},&
\text{otherwise}.
\end{cases}
$$

For positive landing heaviness,

$$
\boxed{
V_L
=
\sqrt{
\frac{
2W_{H,L}
}{
\rho_{air,TO}
S_{\rm ref}
C_{L,L}
}
}.
}
\tag{EQ-99}
$$

If landing heaviness is nonpositive,

$$
V_L=0.
$$

The current speed factors are

$$
\boxed{
V_{50}
=
1.30V_L,
}
\tag{EQ-100}
$$

$$
\boxed{
V_{TD}
=
1.15V_L.
}
\tag{EQ-101}
$$

---
### Literature justification

Carichner and Nicolai directly use
$$V_{50}=1.30V_L,\qquad V_{TD}=1.15V_L.$$
The landing speed $V_L$ is defined from the landing configuration. [1]



**Provenance:** L for 1.30 and 1.15; AS/A for the fallback.

## 44. Landing Air Distance

The current conceptual landing method uses a prescribed approach angle:

$$
\boxed{
S_{\rm air}
=
\frac{
h_{\rm obs}
}{
\tan\gamma_{\rm app}
}.
}
\tag{EQ-102}
$$

The default is

$$
\gamma_{\rm app}=3^\circ.
$$

This is intentionally a simple conceptual approach model and avoids introducing an unsupported detailed approach-thrust schedule.

---
### Literature justification

Carichner and Nicolai give the simplified air-distance relation
$$S_A=\frac{50}{\tan\theta_{\rm app}}$$
and identify approximately $3^\circ$ as a typical conventional approach glide slope. [1]

This is a conceptual geometry approximation, not a certification-level trajectory model.

**Provenance:** L/A.

## 45. Landing Free Roll

The free-roll transition distance is

$$
\boxed{
S_{\rm free}
=
t_{\rm free}V_{TD}.
}
\tag{EQ-103}
$$

The default is

$$
t_{\rm free}=3\ {\rm s}.
$$

The conceptual model assumes aerodynamic lift is subsequently reduced before braking.

---
### Literature/assumption distinction

The 3-s free-roll interval is consistent with the standard conceptual landing methodology associated with Nicolai/Carichner-type performance analysis. [1] It should nevertheless be treated as a **conceptual timing assumption**, because actual pilot/control-system response varies with vehicle and procedure.

**Provenance:** A/AS.

## 46. Landing Braking

At touchdown,

$$
\boxed{
q_{TD}
=
\frac12
\rho_{air,TO}
V_{TD}^2.
}
$$

The current drag used during braking is parasite drag only:

$$
\boxed{
D_{TD}
=
q_{TD}
S_{\rm ref}
C_{D0}.
}
\tag{EQ-104}
$$

Available reverse thrust is

$$
\boxed{
T_{\rm rev}
=
f_{\rm rev}
\max(T_H,0).
}
\tag{EQ-105}
$$

For conventional landing gear,

$$
\boxed{
F_{\rm brake}
=
\mu_{\rm brake}
\max(W_{H,L},0),
}
\tag{EQ-106}
$$

with default

$$
\mu_{\rm brake}=0.30.
$$

For ACLS,

$$
F_{\rm brake}=0.
$$

Total retarding force is

$$
\boxed{
F_{\rm retard}
=
D_{TD}
+
T_{\rm rev}
+
F_{\rm brake}.
}
\tag{EQ-107}
$$

---
### Literature justification

The braking coefficient $\mu_{\rm brake}=0.30$ is directly within the airship-specific range in Carichner and Nicolai Table 4.3. [1]

The default reverse-thrust fraction $f_{\rm rev}=0.60$ is an ADaPT assumption representing a strong reverse-thrust capability. Conceptual aircraft studies allow reverse pitch/thrust on the order of 60% of static thrust, but the actual value is propeller-, engine-, and control-dependent. [11]

For airship validation, use a propulsion-model reverse-thrust curve; if no reverse capability exists, set the fraction to zero.

**Provenance:** L for friction; AS for reverse thrust.

## 47. Landing Accelerated Mass and Braking Distance

If gas masses are already included in vehicle mass,

$$
m_{\rm accel,L}=m_L.
$$

Under the current ADaPT/book convention,

$$
\boxed{
m_{\rm accel,L}
=
m_L
+
m_{\rm He}
+
m_{B,air,TO}.
}
\tag{EQ-108}
$$

The takeoff gas inertial mass is conservatively reused for landing at conceptual fidelity.

For positive retarding force,

$$
\boxed{
S_B
=
\frac{
m_{\rm accel,L}V_{TD}^2
}{
2F_{\rm retard}
}.
}
\tag{EQ-109}
$$

If retarding force is nonpositive while touchdown speed is positive,

$$
S_B=10^9\ {\rm m}
$$

as an infeasibility penalty.

---

## 48. Landing Distance and Field Length

Landing distance is

$$
\boxed{
S_L
=
S_{\rm air}
+
S_{\rm free}
+
S_B.
}
\tag{EQ-110}
$$

The field length is

$$
\boxed{
S_{\rm field,L}
=
f_{\rm field,L}
S_L.
}
\tag{EQ-111}
$$

with default

$$
f_{\rm field,L}
=
\frac{1}{0.60}.
$$

The feasibility constraint is

$$
\boxed{
g_{\rm landing}
=
S_{\rm field,L}
-
S_{\rm field,max}.
}
\tag{EQ-112}
$$

---
### Provenance note on the $1/0.60$ factor

The factor $f_{\rm field,L}=1/0.60$ is a **safety/operational correction**, not an aerodynamic coefficient. It is consistent with conventional certification-style practice of dividing demonstrated landing distance by 0.6 to obtain an operational field-length requirement. [11]


**Provenance:** C/AS.

## 49. Minimum-Power Descent

For positive landing heaviness, the current minimum-power speed is

$$
\boxed{
V_{P,\min}
=
\left[
\frac{
4KW_{H,L}^2
}{
3(\rho S_{\rm ref})^2C_{D0}
}
\right]^{1/4}.
}
\tag{EQ-113}
$$

The corresponding lift coefficient is

$$
\boxed{
C_{L,P}
=
\frac{
W_{H,L}
}{
q_PS_{\rm ref}
}.
}
\tag{EQ-114}
$$

Drag is

$$
\boxed{
D_P
=
q_PS_{\rm ref}
\left(
C_{D0}
+
KC_{L,P}^2
\right).
}
\tag{EQ-115}
$$

The rate of descent is reported as negative:

$$
\boxed{
ROD
=
-
\frac{
V_{P,\min}D_P
}{
W_{H,L}
}.
}
\tag{EQ-116}
$$

For nonpositive landing heaviness,

$$
V_{P,\min}=0,
\qquad
ROD=0.
$$

---

## 50. Turning Performance

The current low-order turn model uses the explicit conceptual input

$$
\boxed{
\frac{R}{L}=2.7
}
\tag{EQ-117}
$$

by default, corresponding to the Chapter-4 worked example context.

Define

$$
\boxed{
A_T
=
1
+
12.8
\left(
\frac{L}{R}
\right)^2.
}
\tag{EQ-118}
$$

The turn/cruise speed ratio is

$$
\boxed{
\frac{V_T}{V_C}
=
\frac{
-1+\sqrt{1+8A_T}
}{
2A_T
}.
}
\tag{EQ-119}
$$

Then

$$
\boxed{
R
=
\left(\frac{R}{L}\right)L,
}
\tag{EQ-120}
$$

$$
\boxed{
V_T
=
\left(
\frac{V_T}{V_C}
\right)
V_{C,1},
}
\tag{EQ-121}
$$

and 360-degree turn time is

$$
\boxed{
t_T
=
\frac{
2\pi R
}{
V_T
}.
}
\tag{EQ-122}
$$

The default $R/L=2.7$ is a conceptual input, not a universal turning law.

The input `rudder_deflection` is retained for compatibility, but the current turning calculation does not directly use it.

---
### Literature justification

The turning model is intentionally empirical. Carichner and Nicolai relate turning coefficient $R/L$ to rudder deflection and give a worked example where $\delta_r=28^\circ$ gives $R/L=2.7$. They then use
$$
\frac{V_{\rm turn}}{V_\infty}
=
\frac{-1+\sqrt{1+8[1+12.8(L/R)^2]}}
{2[1+12.8(L/R)^2]}.
$$
[1]

Thus $R/L=2.7$ is justified **only as the book's worked-example value associated with about 28 deg rudder deflection**. 

Full-scale NACA trials and FAA airship guidance independently show that turning radius depends on rudder input, yaw damping, speed, and vehicle geometry. [5,6] For a specific airship, measured/CFD-derived turning data or a rudder/yaw-dynamics model is preferable.

**Provenance:** L/C for the book example; E for empirical generalization.

## 51. Stability Output

The output

```text
stability_margin
```

is retained only for backward compatibility and is set to

$$
\boxed{
0.
}
$$

The performance component does **not** calculate static or dynamic stability margin.

Publications and validation reports should therefore not interpret this output as a predicted stability metric.

---

## 52. Optional Pressure-Control Accounting

Pressure-control power is an ADaPT extension and is disabled by default.

When enabled,

$$
\boxed{
P_{PC,i}
=
P_{PC,0}
+
f_{PC}
P_{\rm shaft,req,i}.
}
\tag{EQ-123}
$$

Let

$$
\Delta h
=
\max
(h_{\max}-h_{TO},0).
$$

The conceptual ascent/descent pressure-control duration is

$$
\boxed{
t_{PC}
=
\frac{\Delta h}{\dot h_{\rm asc}}
+
\frac{\Delta h}{\dot h_{\rm des}}.
}
\tag{EQ-124}
$$

Pressure-control energy is

$$
\boxed{
E_{PC}
=
\bar P_{PC}t_{PC}.
}
\tag{EQ-125}
$$

Total mission energy diagnostic is

$$
\boxed{
E_{\rm mission,total}
=
E_{\rm shaft}
+
E_{PC}.
}
\tag{EQ-126}
$$

This extension does not independently size blowers, valves, or pressure-control hardware.

---
### Literature/assumption distinction

Pressure-control accounting is an **ADaPT extension**, not a Carichner–Nicolai Chapter-4 relation. The current linear model is parameterized so that a future blower/valve/pressure-system model can replace it.

The defaults $P_{PC,0}=0$ and $f_{PC}=0$ mean only that this optional extension contributes no energy unless explicitly enabled. They do not imply zero pressure-control energy for a real pressure airship.

**Provenance:** AS/D.

## 53. Feasibility Constraints Summary

All constraints follow $g\le0$.

| Output | Definition | Feasible condition |
|---|---|---|
| `power_constraint` | $P_{\rm req}-P_{\rm installed}$ | $\le0$ at all nodes |
| `energy_constraint_primary` | $m_{\rm cons,req}-m_{\rm cons,inst}$ | $\le0$ |
| `energy_constraint_bat` | $m_{b,\rm req}-m_{b,\rm inst}$ | $\le0$ |
| `energy_constraint` | Architecture-selected resource constraint | $\le0$ |
| `buoyancy_constraint` | $L_{B,\rm req}-L_{B,\rm avail}$ | $\le0$ |
| `lift_constraint` | $\max|C_L|-C_{L,\max}$ | $\le0$ |
| `ground_constraint` | $S_{TO}-S_{\rm field,max}$ | $\le0$ |
| `landing_constraint` | $S_{\rm field,L}-S_{\rm field,max}$ | $\le0$ |
| `ballast_constraint` | $m_{\rm ballast,req}-m_{\rm ballast,avail}$ | $\le0$ |
| `landing_BR_constraint` | $BR_{L,\rm implied}-BR_{L,\rm target}$ | $\le0$ |

A single positive constraint is sufficient to classify that particular capability as infeasible.

Multiple constraint outputs may also represent related manifestations of the same underlying design shortfall and should be interpreted physically rather than simply counted.

---

## 54. Principal Outputs

### 54.1 Cruise and Mission

| Output | Units | Meaning |
|---|---:|---|
| `aerodynamic_lift_cruise` | N | Aerodynamic lift history |
| `heaviness_cruise` | N | Mission heaviness history |
| `buoyancy_ratio_cruise` | – | Mission BR history |
| `lift_coefficient_cruise` | – | Required $C_L$ history |
| `drag_cruise` | N | Cruise drag history |
| `thrust_cruise` | N | Required thrust history |
| `required_shaft_power` | W | Required mechanical shaft power |
| `mission_speed_used` | m/s | Selected cruise speed history |
| `mission_mass_used` | kg | Mass history |
| `mission_duration` | s | Integrated mission duration |
| `time` | s | Compatibility alias |
| `endurance` | h | Mission duration in hours |
| `mission_energy_required` | J | Shaft energy |
| `total_mission_energy_required` | J | Shaft + optional pressure-control energy |

### 54.2 Buoyancy

| Output | Units | Meaning |
|---|---:|---|
| `buoyant_lift_required_takeoff` | N | Required by selected $BR_{TO}$ |
| `buoyant_lift_available_takeoff` | N | Available from gas state |
| `lifting_gas_volume_takeoff_used` | m³ | Gas volume actually used |
| `takeoff_heaviness` | N | $W-L_B$ at takeoff |
| `landing_heaviness` | N | Landing heaviness |
| `BR_landing_implied` | – | Implied landing BR |
| `ballast_required` | kg | Ballast required if statically light |

### 54.3 Takeoff

| Output | Units | Meaning |
|---|---:|---|
| `takeoff_speed_calculated` | m/s | Calculated/fixed takeoff reference speed |
| `takeoff_average_speed` | m/s | Representative ground-run speed |
| `takeoff_thrust_available_used` | N | Selected total thrust magnitude |
| `thrust_to` | N | Horizontal thrust component |
| `drag_takeoff_avg` | N | Average ground-run drag |
| `takeoff_aerodynamic_lift_avg` | N | Average ground-run aerodynamic lift |
| `takeoff_friction_force` | N | Rolling resistance |
| `takeoff_accelerated_mass` | kg | Vehicle + gas inertial mass as configured |
| `takeoff_ground_roll` | m | Ground acceleration distance |
| `ground_roll_distance` | m | simplified alias of ground roll |
| `takeoff_rotation_distance` | m | Rotation distance |
| `takeoff_climbout_distance` | m | Distance to obstacle |
| `takeoff_distance` | m | Ground + rotation + climbout |
| `takeoff_climb_angle` | deg | $\gamma$ |
| `takeoff_climb_gradient` | – | $\tan\gamma$ |

### 54.4 Landing

| Output | Units | Meaning |
|---|---:|---|
| `landing_reference_speed` | m/s | $V_L$ |
| `landing_speed_50ft` | m/s | $1.30V_L$ |
| `landing_touchdown_speed` | m/s | $1.15V_L$ |
| `landing_air_distance` | m | 50-ft approach distance |
| `landing_free_roll_distance` | m | Free-roll transition |
| `landing_braking_distance` | m | Braking distance |
| `landing_distance` | m | Sum of landing segments |
| `landing_field_length` | m | Factored field requirement |
| `drag_landing` | N | Touchdown parasite drag |

### 54.5 Climb, Descent, and Turn

| Output | Units | Meaning |
|---|---:|---|
| `roc` | m/s | Rate of climb |
| `rod` | m/s | Rate of descent, negative downward |
| `minimum_power_speed` | m/s | Minimum-power/descent speed |
| `turn_radius` | m | Conceptual turn radius |
| `turn_speed` | m/s | Turn speed |
| `turn_speed_ratio` | – | $V_T/V_C$ |
| `turn_time` | s | 360-degree turn time |
| `stability_margin` | – | Deprecated; always zero |

### 54.6 Hybrid and Resource Diagnostics

| Output | Units | Meaning |
|---|---:|---|
| `eta_fc_used` | – | Average valid supplied FC efficiency |
| `chi_consistency_error` | – | $\chi_{\rm implied}-\chi_{\rm target}$ |
| `chi_implied` | – | Battery fraction of usable installed energy |
| `tau_used` | – | Clipped supplied power hybridization |
| `fuel_mass` | kg | Compatibility output equal to required consumable mass |
| `battery_mass_required` | kg | Compatibility required battery mass |
| `mission_consumable_mass_used` | kg | Consumable used in mission mass history |

---

## 55. Multidisciplinary Coupling

The principal ADaPT loop is

$$
\boxed{
\begin{array}{c}
\text{Geometry}\\
\downarrow\\
V,\;S_{\rm ref},\;V_{g,TO},\;L\\
\downarrow\\
\text{mass + gas state}\\
\downarrow\\
m_{TO},\;m_{\rm He},\;BR\\
\downarrow\\
\text{Performance}\\
\downarrow\\
D,\;T,\;P_{\rm shaft,req},\;E_{\rm shaft}\\
\downarrow\\
\text{Propulsion / Power / Energy}\\
\downarrow\\
P_{\rm installed},\;
m_{\rm consumable},\;
m_{\rm battery},\;
m_{\rm system}\\
\downarrow\\
\text{mass}\\
\circlearrowleft
\end{array}
}
\tag{EQ-127}
$$

The Performance component is therefore not merely a post-processing module. It is a central source of coupling quantities and feasibility constraints.

---

## 56. Important Consistency Rules

The current implementation depends on several conventions that must remain consistent across the framework.

### 56.1 Aerodynamic Area

`aerodynamic_reference_area` entering Performance must represent the aerodynamic coefficient reference area, intended as

$$
V^{2/3},
$$

not wetted hull area.

### 56.2 Helium Mass

When mass excludes helium from MTOW,

```text
gas_masses_in_mtow = False
```

must remain consistent so gas inertial mass is added separately during accelerated phases.

### 56.3 Takeoff Gas Volume

Prefer Geometry's

```text
lifting_gas_volume_takeoff
```

rather than reconstructing gas volume from gross envelope volume.

### 56.4 Installed Power

Reference-aircraft validation should preserve the published/reference installed rating. Performance should be allowed to report a positive power constraint if the configured mission exceeds that capacity.

### 56.5 Resource Capacity

Required consumable/battery masses should be supplied by their authoritative sizing models; Performance checks them rather than recomputing them.

---

## 57. Assumptions and Limitations

| Item | Current treatment | Classification |
|---|---|---|
| Performance fidelity | Quasi-steady | AS |
| Reference area | $V^{2/3}$ through promoted interface | L / software convention |
| Drag polar | $C_{D0}+KC_L^2$ | L / E |
| Buoyant lift induced drag | None | L / physical distinction |
| Buoyant force through mission | Constant selected takeoff buoyant force | AS |
| Mission mass | Supplied or linear burn history | AS |
| Cruise strategy 1 | Pointwise equilibrium $C_L$ | F / D |
| Min-drag strategy | $C_L=\sqrt{C_{D0}/K}$ | L |
| Min-power strategy | $C_L=\sqrt{3C_{D0}/K}$ | L |
| Mission integration | Equal route-distance nodes | AS / D |
| Wind sign | Positive current input reduces ground speed | simplified convention |
| Takeoff speed | Calculated from heaviness and $C_{L,TO}$ | L / A |
| Average ground-run speed | $\sqrt{0.5}V_{TO}$ | L |
| Static thrust | External preferred, actuator disk fallback | F / A |
| Actuator-disk efficiency | 0.75 | AS |
| Final low-speed thrust | $P\eta/V_{\min}$ | Compatibility fallback |
| Gas inertia | Explicit configurable convention | L / D |
| Ground roll | Constant representative acceleration | L / A |
| Failed acceleration | $10^9$ m penalty | N |
| Rotation | 3-s assumption | L / AS |
| Climb angle | $\sin\gamma=(T-D)/W_H$ | F / L-consistent |
| Landing approach | 3-deg geometric path | AS / L-adapted |
| Landing braking | Constant coefficients | AS |
| Landing gas inertia | Takeoff gas mass reused | AS |
| Minimum-power descent | Parabolic-polar relation | L / D |
| Turn | Empirical $R/L$ relation | L / E / AS |
| Stability | Not calculated | Limitation |
| Pressure control | Optional low-order energy extension | AS |
| Full transient dynamics | Not modeled | Limitation |
| Gusts / turbulence | Not modeled | Limitation |
| Propeller maps | External/actuator disk only | Limitation |
| Detailed ground dynamics | Not modeled | Limitation |
| Detailed landing flare | Not modeled | Limitation |

---
### Parameter-specific evidence status

| Parameter | Default | Evidence status | Recommended interpretation |
|---|---:|---|---|
| `C_L_takeoff` | 0.10 | AS | Generic conceptual value; 0.175 is retained for the book sample replication |
| `C_L_max` | 0.60 | AS | Not a universal airship value; replace with configuration-specific data |
| `takeoff_speed_factor` | 1.10 | AS | ADaPT margin; use 1.0 for exact book relation |
| `takeoff_average_speed_ratio` | $\sqrt{0.5}$ | L | Directly supported by 0.707 $V_{TO}$ approximation |
| `rotation_time` | 3 s | L | Directly supported by the book |
| `obstacle_height` | 15.24 m | L | 50-ft obstacle convention |
| `mu_TO` | 0.03 | L/C | Within 0.015--0.04 concrete/macadam range |
| `mu_brake` | 0.30 | L/C | Within 0.3--0.6 concrete/macadam range |
| `reverse_thrust_fraction` | 0.60 | AS | Strong reverse-thrust assumption |
| `landing_approach_angle_deg` | 3 deg | L/A | Book's typical conventional approach angle |
| `landing_free_roll_time` | 3 s | A/AS | Conceptual timing assumption |
| `landing_field_factor` | $1/0.60$ | C/AS | Operational/certification correction |
| `actuator_disk_power_efficiency` | 0.75 | AS | Conceptual fallback; not a propeller map |
| `minimum_thrust_speed` | 8 m/s | N/AS | Numerical regularization |
| `turn_radius_to_length_ratio` | 2.7 | C | Book worked-example value at about 28 deg rudder |
| `propeller_efficiency` | 0.75 | AS | Plausible conceptual value; replace with propeller map |
| `C_D0` | 0.03542 | C/AS | Baseline polar input; not universal |
| `K` | 0.869 | C/AS | Baseline polar input; not universal |
| `BR_takeoff` | 0.856 | C/AS | Reference/design input |
| `BR_landing` | 0.90 | C/AS | Reference/design/operational target |
| `field_length_limit` | 450 m | AS/C | Requirement/design input |
| pressure-control defaults | 0 | AS/D | Disabled extension; not a real-hardware claim |

The key methodological point is that **literature support for an equation does not automatically validate every numerical coefficient inserted into it**.

## 58. Provenance Classification

The documentation uses:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical relationship |
| **L** | Direct literature relationship |
| **A** | Adapted literature relationship |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **N** | Numerical safeguard |
| **D** | Derived/software relationship |
| **C** | Calibration/reference parameter |

Selected equations are classified as:

| Equations | Relationship | Classification |
|---|---|---|
| EQ-5–6 | BR and heaviness | L / F |
| EQ-7–8 | Takeoff buoyancy requirement | D / L |
| EQ-9–13 | Actual gas volume and buoyancy feasibility | F / D |
| EQ-14 | Constant mission buoyant force | AS |
| EQ-15–18 | Mission mass history | AS / D |
| EQ-19–20 | Mission heaviness/BR | D |
| EQ-21 | $V^{2/3}$ reference area | L |
| EQ-22–26 | Aerodynamic lift/drag | F / L |
| EQ-27–28 | Prescribed-speed equilibrium | F / D |
| EQ-29–31 | Minimum drag | L / D |
| EQ-32–34 | Minimum power | L / D |
| EQ-35–38 | Cruise drag/thrust/power | F / L |
| EQ-39 | Wind/ground-speed convention | D / simplified |
| EQ-40–44 | Distance-based mission integration | D / AS |
| EQ-45–51 | Capacity constraints | D |
| EQ-52–56 | Hybrid diagnostics | D |
| EQ-57–61 | Gas inertial mass | L / D / AS |
| EQ-62 | Calculated takeoff speed | L / A |
| EQ-63–66 | Representative takeoff condition | L / D |
| EQ-67–73 | Takeoff-thrust hierarchy | F / A / compatibility |
| EQ-74–81 | Ground-run force balance | F / L / D |
| EQ-82 | Infeasibility distance | N |
| EQ-83 | Rotation distance | L / AS |
| EQ-84–92 | Climbout and ROC | F / L-consistent |
| EQ-93–101 | Landing mass/BR/speed | D / L-adapted |
| EQ-102–112 | Landing distance/braking | AS / D |
| EQ-113–116 | Minimum-power descent | L / D |
| EQ-117–122 | Turn relation | L / E / AS |
| EQ-123–126 | Pressure-control extension | AS / D |
| EQ-127 | MDAO coupling | D |

---
### Evidence rule

A coefficient is marked **L** only when the cited source gives the relation or a numerical range directly supporting the value. **C** denotes a particular reference-airship or worked example. **AS** denotes an ADaPT modelling choice without a sufficiently direct literature basis.

Airship $C_{D0}$ and $K$ are especially configuration-dependent because hull fineness ratio, Reynolds number, surface condition, fins, gondola, propulsion installation, and interference affect drag. [2--4] Turning coefficients are likewise empirical and vehicle-specific. [1,5,6]

## 59. Numerical Implementation

### 59.1 Input Guards

Representative numerical protections include:

- mission range $\ge1$ m,
- cruise speed $\ge0.5$ m/s,
- $N_p\ge1$,
- $S_{\rm ref}\ge10^{-9}$ m²,
- gross volume $\ge10^{-9}$ m³,
- length $\ge10^{-6}$ m,
- MTOW $\ge1$ kg,
- pressure $\ge1000$ Pa,
- temperature $\ge150$ K,
- density $\ge10^{-8}$ kg/m³,
- $C_{D0},K>0$,
- propeller efficiency clipped to 0.05–0.99,
- buoyancy-ratio inputs clipped below 1,
- ground speed $\ge0.5$ m/s.

These are numerical protections rather than physical certification boundaries.

### 59.2 Vector Handling

Scalar mission inputs are broadcast to `num_steps`. Short arrays are edge-padded; long arrays are truncated.

Mission nodes are interpreted as equal fractions of route distance for the time/energy integration.

### 59.3 Actuator-Disk Solver

The induced velocity in the actuator-disk fallback is solved by 80 iterations of a bounded bisection procedure.

This is an internal numerical method, not an empirical thrust fit.

### 59.4 OpenMDAO Derivatives

The component currently declares finite-difference derivatives:

```python
self.declare_partials("*", "*", method="fd", step=1.0e-8)
```

with

$$
\Delta x=10^{-8}.
$$

Piecewise logic, clipping, `max`, and penalty distances introduce nonsmooth behavior that should be considered in gradient-based optimization.

---

## 60. Verification Strategy

The current model should be verified in layers.

### 60.1 Buoyancy Verification

Independently check:

- required buoyant lift from $BR_{TO}$,
- gas volume from direct input,
- gas volume reconstructed from helium mass/density,
- gross-minus-ballonet fallback,
- available net buoyant lift,
- buoyancy constraint,
- rigid versus pressure-airship ballonet-air treatment.

### 60.2 Cruise Verification

For known $\rho,V,S,C_{D0},K,W_H$, independently verify:

- pointwise $C_L$,
- lift,
- drag,
- thrust,
- shaft power,
- minimum-drag strategy,
- minimum-power strategy.

### 60.3 Reference-Area Verification

Explicitly confirm in the integrated Group that the value connected to `aerodynamic_reference_area` is

$$
V^{2/3},
$$

not wetted surface area.

This is particularly important for the BASI MB-30T power-demand audit.

### 60.4 Mission Integration Verification

Use a constant-speed/constant-power case and confirm

$$
t=R/V,
\qquad
E=Pt.
$$

Then use varying node speeds and powers and independently reproduce the equal-distance integration.

### 60.5 Takeoff Verification

Verify separately:

- calculated and fixed takeoff speed,
- $\sqrt{0.5}V_{TO}$ average speed,
- external thrust path,
- actuator-disk path,
- power/speed fallback,
- thrust vectoring,
- gas inertial mass,
- rolling friction,
- ground roll,
- failed-acceleration penalty,
- rotation,
- climbout angle,
- climbout distance,
- total field length,
- ROC.

### 60.6 Landing Verification

Check:

- landing mass,
- implied BR,
- ballast requirement,
- landing speed factors,
- air distance,
- free roll,
- reverse thrust,
- braking,
- landing field factor,
- infeasible braking penalty.

### 60.7 Resource Verification

Test fuel, battery, and hybrid architecture groups and confirm the appropriate resource constraint is selected.

### 60.8 Turn and Descent Verification

Independently evaluate minimum-power descent and the $R/L$-based turn relation.

---
### Literature traceability checks

For every numerical parameter that materially affects a published performance result, the validation record should identify one of:

- a direct literature source and page/section,
- a reference-airship source,
- a measured/CFD-derived value, or
- an explicitly declared ADaPT assumption.

The highest-priority sensitivity checks are $C_{D0}$, $K$, $C_{L,\max}$, $C_{L,TO}$, friction coefficients, propeller efficiency/thrust, reverse thrust, $BR_{TO}$, $BR_L$, and $R/L$.

## 61. Reference-Airship Validation Guidance

Reference-aircraft validation must distinguish:

1. **prescribed reference inputs,**
2. **derived reference quantities,**
3. **independently predicted outputs,**
4. **architecture/model assumptions,**
5. **feasibility constraints.**

For example, if installed shaft power is prescribed from a reference table, a zero-percent error in that row is not a predictive validation result.

By contrast, the following may be genuine predictions depending on what was prescribed:

- cruise drag,
- required shaft power,
- mission duration,
- takeoff speed,
- ground roll,
- buoyancy margin,
- landing distance,
- required ballast,
- required resource capacity.

A constraint failure should not automatically be “corrected” by changing the published/reference aircraft specification. It may reveal:

- inconsistent source data,
- an incompatible mission interpretation,
- generic aerodynamic assumptions,
- a missing reference-specific physical model, or
- actual infeasibility under the configured mission.

---

## 62. Current BASI MB-30T Interpretation

The current reference-capacity BASI case gives approximately:

$$
P_{\rm required}
=
2.696\ {\rm MW},
$$

against

$$
P_{\rm installed}
=
1.560\ {\rm MW}.
$$

The associated power shortfall is therefore about

$$
1.136\ {\rm MW}.
$$

The same case has a mission fuel requirement well above the selected reference fuel capacity.

These outputs should be interpreted as **mission-capacity feasibility results**, not mass-model failures.

Before changing the published power or fuel capacity, the first physics audit should verify the aerodynamic coefficient/reference-area convention and whether the generic

$$
C_{D0}=0.03542,
\qquad
K=0.869
$$

are appropriate for the MB-30T.

The current Performance implementation itself uses the same selected $S_{\rm ref}$ for lift and drag. Therefore any BASI discrepancy should now be traced through the **integrated Group connections and the provenance of the aerodynamic coefficients**, rather than assuming Performance is multiplying those coefficients by hull wetted area.

---
### Literature-based audit recommendation

The independent literature supports auditing the **coefficient/reference-area pair together**. NASA airship studies use $V^{2/3}$ as reference area, but their $C_{D0}$ values are obtained from fineness ratio, Reynolds number, component drag, and interference rather than copied between unrelated airships. [2--4]

Therefore the MB-30T audit should ask whether 0.03542 and 0.869 were derived using the same reference area, geometry, Reynolds-number regime, and drag-build-up convention as the MB-30T source. This is a stronger basis for the audit than simply asking whether the two numerical values "look reasonable".

## 63. Important Improvements Relative to the Previous Documentation

The current implementation resolves several issues described in the older guide:

1. The aerodynamic reference-area interface is now explicitly intended to carry $V^{2/3}$, and the same $S_{\rm ref}$ is used for both lift and drag.
2. Cruise Strategy 1 now calculates the required $C_L$ point by point.
3. Mission mass can vary through the mission.
4. Buoyancy ratio changes with mission mass while selected buoyant force remains constant.
5. Actual takeoff lifting-gas volume is accepted directly from Geometry.
6. Buoyant lift uses the actual lifting-gas volume and helium mass.
7. Gas inertial mass treatment is explicit.
8. Takeoff speed is calculated from heaviness by default rather than universally fixed.
9. The representative ground-run speed is $\sqrt{0.5}V_{TO}$, matching the 0.707 literature approximation.
10. Takeoff thrust uses an external/actuator-disk/fallback hierarchy.
11. Nonaccelerating takeoff cases are explicitly penalized rather than hidden by a tiny positive acceleration.
12. Climbout uses the dimensionally consistent force relation.
13. Mission time and shaft energy use distance-based node integration.
14. Landing includes explicit BR, ballast, approach, free-roll, braking, and field-length logic.
15. Stability is explicitly marked as not calculated.

The previous `performance(1).md` should therefore not be retained as the authoritative description of the current `AirshipPerformance` component.

---

## 64. Recommended Future Refinements

The current model is suitable for conceptual MDAO, while future fidelity increases may include:

- rename `aerodynamic_reference_area` to `aero_reference_area`,
- rename or clarify `tailwind_speed` sign convention,
- fully coupled propeller-map takeoff thrust,
- time- or trajectory-based mission integration,
- Dymos-based climb/cruise/descent trajectory optimization,
- variable buoyant force with thermal/pressure gas dynamics,
- dynamic ballonet state,
- explicit flare and approach thrust,
- detailed ground-reaction dynamics,
- crosswind and gust analysis,
- aerodynamic coefficient variation with Reynolds/Mach/angle of attack,
- propeller–hull interaction,
- detailed turning/rudder force model,
- explicit static/dynamic stability model,
- analytic or complex-step-compatible derivatives.

These are fidelity extensions, not reasons to discard the present conceptual framework.

---
### Evidence-driven refinement priority

1. Replace generic $C_{D0}$ and $K$ with a reference-specific drag build-up or CFD/wind-tunnel polar.
2. Replace constant $\eta_p$ and low-speed actuator-disk assumptions with propulsion/propeller maps.
3. Replace generic $C_{L,\max}$ and takeoff $C_L$ with configuration-specific aerodynamic data.
4. Replace empirical $R/L$ turning calibration with rudder/yaw-dynamics or test data.
5. Keep runway friction as an explicit surface-dependent input.
6. Keep certification/operational correction factors separate from physics-based distances.

The literature is comparatively strong for the governing equations; the largest uncertainty is in configuration-specific aerodynamic, propulsion, and manoeuvrability coefficients.

## 65. Software Traceability Summary

| Theory/model item | Current implementation |
|---|---|
| Required buoyancy | `BR_takeoff * mtow * g` |
| Takeoff heaviness | `mtow*g - required_buoyant_lift` |
| Preferred gas volume | `lifting_gas_volume_takeoff` |
| Gas-volume fallback | `he_mass/rho_he_to`, then `gross_volume-ballonet_volume` |
| Available buoyancy | `(rho_air_to*v_he_to - he_mass)*g` |
| Mission buoyant force | selected takeoff required buoyant lift |
| Mission mass | supplied vector or MTOW-to-landing linear history |
| Cruise heaviness | `mission_mass*g - buoyant_lift_mission` |
| Aerodynamic area | `aerodynamic_reference_area`, fallback `planform_area` |
| Prescribed-speed $C_L$ | pointwise `heaviness/(q*Sref)` |
| Min-drag $C_L$ | `sqrt(CD0/K)` with heaviness sign |
| Min-power $C_L$ | `sqrt(3*CD0/K)` with heaviness sign |
| Drag | `q*Sref*(CD0 + K*CL**2)` |
| Required shaft power | `drag*speed/eta_prop` |
| Mission time | equal-distance node integration |
| Shaft energy | `sum(P_i*dt_i)` |
| Power constraint | required minus installed |
| Resource constraints | required minus installed masses |
| Gas accelerated mass | MTOW plus gas masses when excluded from MTOW |
| Takeoff speed | heaviness-based, 1.10 factor |
| Average TO speed | `sqrt(0.5)*V_TO` |
| Low-speed thrust | external → actuator disk → power/speed |
| TO friction | heaviness minus aero/vertical thrust |
| Ground roll | $V^2/(2a)$, or $10^9$ penalty |
| Rotation | `rotation_time * V_TO` |
| Climb angle | `asin((T-D)/W_H)` |
| ROC | `V_TO*sin(gamma)` |
| Landing mass | `mtow - consumable_mass_used` |
| Landing ballast | light-state mass correction |
| Landing reference speed | heaviness-based |
| Landing distance | approach + free roll + braking |
| Minimum-power descent | parabolic-polar relation |
| Turn | Chapter-4 $R/L$ conceptual relation |
| Pressure-control energy | optional ascent/descent accounting |
| Stability | not calculated; compatibility zero |
| Derivatives | finite difference, $10^{-8}$ |

---

## 66. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, 2013, ISBN 978-1-60086-898-6. Chapters 3, 4, and 11 are the principal sources for the airship aerodynamic and performance relations used here.  
AIAA bibliographic source: https://www.aiaa.org/docs/default-source/uploadedfiles/publications/aerospace-america-december-2013.pdf

[2] C. J. Huang and C. Dalton, *Cargo Transportation by Airships: A Systems Study*, NASA CR-2636, 1976. Uses $V^{2/3}$ as the aerodynamic reference area and empirical component drag/K-factor methods.  
NASA NTRS: https://ntrs.nasa.gov/citations/19760020076

[3] J. W. Lancaster, *Feasibility Study of Modern Airships, Phase 1, Volume 4: Appendices*, NASA CR-137692-VOL-4, 1975. Provides independent airship drag/reference-area treatment.  
NASA NTRS: https://ntrs.nasa.gov/citations/19750023962

[4] S. F. Hoerner, *Fluid-Dynamic Drag*, Hoerner Fluid Dynamics, 1965. Airship chapter: volumetric drag coefficient and skin-friction-based hull drag.  
https://home.hvl.no/ansatte/gste/ftp/MarinLab_files/Litteratur/Hoerner_1965_Fluid-dynamic_drag.pdf

[5] U.S. Army Air Corps, *Airship Aerodynamics*, TM 1-320. Directional-control discussion of airship turning, yaw damping, and fineness ratio.  
FAA-hosted copy: https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/airship_aerodynamics.pdf

[6] F. L. Thompson, *Full-Scale Turning Characteristics of the U.S.S. Los Angeles*, NACA-TR-333, 1930. Full-scale evidence that airship turning characteristics are configuration-dependent.  
NASA NTRS: https://ntrs.nasa.gov/citations/19930091403

[7] EASA, *CS 30T — Certification Specifications for Transport Category Airships*, Issue 2. Independent certification context for airship performance, takeoff, landing, and manoeuvrability.  
EASA: https://www.easa.europa.eu/en/downloads/139573/en

[8] A. Colozza and J. Dolce, *Initial Feasibility Assessment of a High Altitude Long Endurance Airship*, NASA/CR-2003-212724, 2003. Uses propeller thrust/power coefficients and operating-point propeller efficiency.  
NASA NTRS: https://ntrs.nasa.gov/citations/20040021326

[9] J. Jiao, B.-F. Song, Y.-G. Zhang, and Y.-B. Li, “Optimal design and experiment of propellers for high altitude airship,” *Proceedings of the Institution of Mechanical Engineers, Part G*, 2018. Propeller optimization and experimental validation.  
DOI: https://doi.org/10.1177/0954410017704217

[10] Embry-Riddle Aeronautical University, *Introduction to Aerospace Flight Vehicles — Airships, Blimps, & Aerostats*. Independent conceptual cross-check for airship drag and propulsive-efficiency modelling.  
https://eaglepubs.erau.edu/introductiontoaerospaceflightvehicles/chapter/lth/

[11] Conceptual aircraft-performance literature using Nicolai/Carichner methods for free-roll and reverse-thrust treatment. These sources are used only to characterize reverse thrust and field-length corrections as operational assumptions, not as universal airship coefficients. The airship-specific friction coefficients remain sourced to [1].

[12] “Hybrid Airship: More of a Faster Ship, Than a Slower Aircraft,” 2020. Discusses buoyancy ratio, heaviness, drag-due-to-lift, and the coupled BR/takeoff/propulsion trade.  
https://www.researchgate.net/publication/344073578_Hybrid_Airship_More_of_a_Faster_Ship_Than_a_Slower_Aircraft

---

