# Propulsion

The `Propulsion` component is the low-fidelity model used by ADaPT for buoyant-airship analysis and sizing. It is independent of structural class and separates mechanical propulsion hardware from the upstream energy source.

The component supports:

- reciprocating-engine prime movers,
- electric-motor prime movers,
- direct mission shaft-power demand from `AirshipPerformance`,
- a backward-compatible thrust/speed power path,
- prescribed or mission-sized installed shaft power,
- three selectable preliminary propeller-sizing methods,
- literature-based propeller mass,
- specific-power, literature, or override prime-mover mass,
- generic, structure-integrated, or override installation mass,
- optional propulsion wiring mass, and
- complete propulsion-system mass buildup.

Prime mover: the propulsion machine represented by the Propulsion component that produces the mechanical shaft power delivered to the propeller. Depending on the propulsion architecture, this may represent a reciprocating engine, gas-turbine shaft engine, or electric propulsion motor. Upstream energy-conversion equipment such as batteries, fuel cells, generators, and associated electrical power-conditioning equipment is accounted for separately in the corresponding Power/Energy subsystem.

The principal theory source is Carichner and Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies* [1], particularly Chapters 5, 9, and 11.

A central modeling boundary is:

> **Propulsion owns the mechanical propulsor chain. Power and Energy Components own fuel, battery, fuel cell, generator, solar, hydrogen storage, or thermal energy conversion.**


---

## 1. Model Scope

The preferred calculation chain is

$$
P_{\mathrm{shaft,mission}}
\rightarrow
P_{\mathrm{shaft,rated}}
\rightarrow
P_{\mathrm{brake,rated}}
\rightarrow
\left[
D,\;J,\;C_s,\;V_{\mathrm{tip}}
\right]
\rightarrow
m_{\mathrm{PM}},
m_{\mathrm{prop}},
m_{\mathrm{nac}},
m_{\mathrm{mount}},
m_{\mathrm{wire}}
\rightarrow
m_{\mathrm{propulsion}}.
$$

The current component supports two prime-mover categories:

$$
\boxed{
\text{reciprocating engine},
\qquad
\text{electric motor}.
}
\tag{EQ-1}
$$

These categories identify the mechanical prime mover at the propulsor. 

For example, an electric motor may be supplied by a battery, fuel cell, turboelectric generator, solar system, or hybrid architecture without changing the fundamental mechanical propulsion interface.

---

## 2. Responsibility and Ownership Boundary

### 2.1 Quantities Owned by Propulsion

The component owns:

- mission shaft-power history,
- mission brake-power history,
- total rated shaft power,
- total rated brake power,
- per-unit rated power,
- preliminary propeller diameter,
- speed-power coefficient,
- advance ratio,
- estimated chart propeller efficiency,
- propeller tip speed,
- tip-speed violation diagnostic,
- prime-mover core mass,
- propeller mass,
- nacelle mass,
- mount/pylon mass,
- optional wiring mass, and
- total mechanical propulsion mass.


The authoritative mission shaft-power requirement should arrive from `AirshipPerformance`.

---

## 3. Structural and Energy-Architecture Independence

The component accepts

```text
airship_type
```

with

$$
\text{non-rigid},\quad
\text{semi-rigid},\quad
\text{rigid},
$$

but the structural class does not change the fundamental propeller equations.

Structural class becomes relevant primarily through the selected installation treatment. In particular, semi-rigid or rigid airships may use a structure-integrated installation to avoid separately applying a generic engine-mount WER where the propulsion unit is attached directly to the primary framework.

The energy architecture is similarly external. `engine_type="electric"` describes the mechanical prime mover, not whether the upstream source is battery, fuel cell, solar, hydrogen, or turboelectric.

---

## 4. Principal OpenMDAO Options

### 4.1 Prime-Mover and Configuration Options

| Option | Default | Allowed values / role |
|---|---|---|
| `engine_type` | `reciprocating` | `reciprocating`, `electric` |
| `landing_system` | `conventional` | `conventional`, `acls` |
| `airship_type` | `non-rigid` | `non-rigid`, `semi-rigid`, `rigid` |
| `num_steps` | 1 | Number of mission points |

`landing_system` and `airship_type` are retained as framework/configuration interfaces. The current mechanical sizing equations do not otherwise introduce different aerodynamic propulsion physics for these options.

### 4.2 Propeller-Sizing Options

| Option | Default | Meaning |
|---|---|---|
| `propeller_sizing_method` | `book_speed_power` | Chapter-5 $C_s/J$ chart-fit method |
|  | `book_power_coefficient` | Standard Eq. (5.27) $C_P$ method |
|  | `reduced_order` | simplified ADaPT diameter scaling |
| `propeller_mass_method` | `book` | Chapter-9 Eq. (9.16) |
|  | `simplified` | Linear mass-per-power proxy |
| `prop_power_coeff` | 0.65 | simplified reduced-order coefficient only |

The option `prop_power_coeff` is **not** the conventional nondimensional propeller power coefficient $C_P$.

### 4.3 Prime-Mover Mass Options

| Option | Default | Meaning |
|---|---|---|
| `prime_mover_mass_method` | `specific_power` | Technology-based specific-power model |
|  | `book_reciprocating` | Historical Chapter-5 reciprocating-engine WER |
|  | `override` | Prescribed validation/reference mass |
| `prime_mover_mass_override` | 0 kg | Used only in override mode |

### 4.4 Installation Options

| Option | Default | Meaning |
|---|---|---|
| `installation_mass_method` | `generic` | Generic preliminary nacelle + mount |
|  | `structure_integrated` | Retain nacelle; omit separate generic mount |
|  | `override` | Prescribed nacelle and mount masses |
| `mount_mass_method` | `book_for_recip` | Chapter-9 mount WER for reciprocating engine |
|  | `simplified` | Thrust-based conceptual fallback |
| `nacelle_mass_override` | 0 kg | Override nacelle mass |
| `mount_mass_override` | 0 kg | Override mount mass |

### 4.5 Installation and Wiring Parameters

| Option | Default | Meaning |
|---|---:|---|
| `nacelle_mass_per_kw_recip` | 0.92 kg/kW | Conceptual/calibration reciprocating nacelle coefficient |
| `nacelle_mass_per_kw_electric` | 3.0 kg/kW | Conceptual/calibration electric nacelle coefficient |
| `propeller_mass_per_watt` | $1.2\times10^{-4}$ kg/W | simplified propeller mass coefficient |
| `minimum_propeller_mass_each` | 0 kg | simplified propeller minimum |
| `enable_mount_mass` | `True` | Enables mount mass |
| `mount_mass_per_kn` | 0.03 kg/kN | simplified conceptual mount coefficient |
| `enable_wiring_mass` | `False` | Enables electric propulsion wiring mass |
| `wiring_mass_per_kw` | 0 kg/kW | User-defined wiring coefficient |

---

## 5. Principal Inputs

### 5.1 Mission and Mechanical-Demand Inputs

| Input | Symbol | Default | Units | Role |
|---|---:|---:|---:|---|
| `n_engine` | $N_p$ | 2 | – | Number of propulsor units |
| `mission_shaft_power_required` | $P_{\mathrm{sh,req},i}$ | -1 | W | Preferred demand from Performance |
| `thrust_cruise` | $T_i$ | 0 | N | simplified fallback thrust |
| `tas` | $V_i$ | 19.5 | m/s | Mission true airspeed |
| `propeller_efficiency` | $\eta_p$ | 0.75 | – | Used by fallback $TV/\eta_p$ path |
| `gearbox_efficiency` | $\eta_{gb}$ | 0.98 | – | Shaft-to-brake mechanical efficiency |
| `rho` | $\rho_i$ | 1.099 | kg/m³ | Mission atmospheric density |
| `installed_shaft_power` | $P_{\mathrm{installed}}$ | -1 | W | Prescribed total installed rating; negative sizes to mission |

A negative value in `mission_shaft_power_required` activates the compatibility thrust/speed calculation at that mission point.

A negative `installed_shaft_power` means:

$$
\boxed{
\text{size installed shaft power to peak mission demand}.
}
\tag{EQ-2}
$$

A nonnegative value represents an externally selected installed rating.

### 5.2 Propeller Design Inputs

| Input | Default | Units | Role |
|---|---:|---:|---|
| `propeller_rps` | 20 | s$^{-1}$ | Rotational speed |
| `propeller_design_speed` | -1 | m/s | Explicit propeller design speed; negative uses critical mission point |
| `propeller_design_density` | -1 | kg/m³ | Explicit design density; negative uses critical mission point |
| `propeller_blade_count` | 3 | – | Blades per propeller |
| `propeller_power_coefficient` | 0.08 | – | Standard $C_P$ for Eq. (5.27) method |
| `thrust_vector_angle` | 0 | deg | Compatibility input; not used by current mechanical sizing equations |

### 5.3 Technology Inputs

| Input | Default | Units | Meaning |
|---|---:|---:|---|
| `ice_specific_power` | 1200 | W/kg | Reciprocating-engine brake-power specific power |
| `motor_specific_power` | 5000 | W/kg | Electric-motor brake-power specific power |

These are explicit technology parameters and may be varied in technology-sensitivity studies.

---

## 6. Mission Shaft-Power Demand

### 6.1 Preferred Interface

The preferred input is

$$
P_{\mathrm{sh,req},i}
=
\texttt{mission\_shaft\_power\_required}_i,
$$

supplied directly by the performance model.

When

$$
P_{\mathrm{sh,req},i}\ge0,
$$

the propulsion component uses that value directly:

$$
\boxed{
P_{\mathrm{sh},i}
=
P_{\mathrm{sh,req},i}.
}
\tag{EQ-3}
$$

This establishes a clean ownership boundary:

$$
\boxed{
\text{Performance}
\rightarrow
P_{\mathrm{shaft,required}}
\rightarrow
\text{Propulsion}.
}
\tag{EQ-4}
$$

### 6.2 Compatibility Fallback

For a mission point where the direct input is negative, the component uses the conventional propulsive-efficiency relation

$$
\boxed{
\eta_p
=
\frac{TV}{P_{\mathrm{sh}}}
}
\tag{EQ-5}
$$

from Carichner and Nicolai Eq. (5.30).

Rearranging,

$$
\boxed{
P_{\mathrm{sh}}
=
\frac{TV}{\eta_p}.
}
\tag{EQ-6}
$$

Thus the implemented pointwise logic is

$$
\boxed{
P_{\mathrm{sh},i}
=
\begin{cases}
P_{\mathrm{sh,req},i},
&
P_{\mathrm{sh,req},i}\ge0,
\\[4pt]
\dfrac{T_iV_i}{\eta_p},
&
P_{\mathrm{sh,req},i}<0.
\end{cases}
}
\tag{EQ-7}
$$

The final mission power is constrained numerically to be nonnegative.

**Classification:** EQ-5 [L/F]; EQ-6 [D]; EQ-7 [A/software interface].

---

## 7. Shaft Power and Brake Power

The current model distinguishes propeller shaft power from prime-mover brake power through gearbox efficiency:

$$
\boxed{
P_{\mathrm{br},i}
=
\frac{P_{\mathrm{sh},i}}
{\eta_{gb}}.
}
\tag{EQ-8}
$$

The default is

$$
\eta_{gb}=0.98.
$$

This is a mechanical transmission assumption and is not an energy-source thermal efficiency.

Therefore,

$$
P_{\mathrm{br}}
\neq
P_{\mathrm{fuel}}
$$

and

$$
P_{\mathrm{br}}
\neq
P_{\mathrm{battery}}
$$

unless the relevant upstream conversion efficiencies are separately applied.

---

## 8. Installed and Rated Power

The peak mission shaft-power demand is

$$
\boxed{
P_{\mathrm{sh,peak}}
=
\max_i P_{\mathrm{sh},i}.
}
\tag{EQ-9}
$$

Let the externally supplied installed rating be

$$
P_{\mathrm{installed}}.
$$

When

$$
P_{\mathrm{installed}}\ge0,
$$

the current component evaluates

$$
\boxed{
P_{\mathrm{sh,rated}}
=
\max
\left(
P_{\mathrm{sh,peak}},
P_{\mathrm{installed}}
\right).
}
\tag{EQ-10}
$$

When

$$
P_{\mathrm{installed}}<0,
$$

$$
\boxed{
P_{\mathrm{sh,rated}}
=
P_{\mathrm{sh,peak}}.
}
\tag{EQ-11}
$$

This distinction is important.

`installed_shaft_power` is an **OpenMDAO input**, not an `AirshipAnalysisGroup` option. It is therefore set through the model input interface after setup, not passed as a Group constructor option.

### 8.1 Brake-Power Rating

$$
\boxed{
P_{\mathrm{br,rated}}
=
\frac{P_{\mathrm{sh,rated}}}
{\eta_{gb}}.
}
\tag{EQ-12}
$$

### 8.2 Per-Unit Ratings

For $N_p$ propulsors,

$$
\boxed{
P_{\mathrm{sh,unit}}
=
\frac{P_{\mathrm{sh,rated}}}{N_p},
}
\tag{EQ-13}
$$

$$
\boxed{
P_{\mathrm{br,unit}}
=
\frac{P_{\mathrm{br,rated}}}{N_p}.
}
\tag{EQ-14}
$$

---

## 9. Takeoff Power Ownership

The current propulsion component no longer constructs a fictitious finite-speed takeoff power from

$$
P=\frac{TV}{\eta_p}.
$$

At true static conditions,

$$
V=0
$$

and the conventional propulsive efficiency

$$
\eta_p=\frac{TV}{P}
$$

tends to zero even though the propeller can produce nonzero static thrust.

Therefore, the component sets

$$
\boxed{
P_{\mathrm{sh,TO}}
=
P_{\mathrm{sh,rated}}.
}
\tag{EQ-15}
$$

This represents the installed shaft power available to `AirshipPerformance`.

True static/takeoff thrust is handled in the performance model using either:

- a supplied static-thrust value, or
- an actuator-disk estimate based on installed shaft power and propeller diameter.



---

## 10. Critical Propeller Design Condition

Unless explicit design values are supplied, the preliminary propeller is sized at the mission node having the maximum shaft-power demand.

Let

$$
i^*
=
\arg\max_i P_{\mathrm{sh},i}.
$$

Then

$$
\boxed{
\rho_{\mathrm{ref}}
=
\rho_{i^*},
\qquad
V_{\mathrm{ref}}
=
V_{i^*}.
}
\tag{EQ-16}
$$

If `propeller_design_density > 0`, that value replaces $\rho_{i^*}$.

If `propeller_design_speed > 0`, that value replaces $V_{i^*}$.


---

## 11. Literature Propeller Coefficients

Carichner and Nicolai define the standard power coefficient as

$$
\boxed{
C_P
=
\frac{P}
{\rho n^3D^5}.
}
\tag{EQ-17}
$$

They define the speed-power coefficient as

$$
\boxed{
C_s
=
\left(
\frac{\rho V^5}
{Pn^2}
\right)^{1/5}.
}
\tag{EQ-18}
$$

The advance ratio is

$$
\boxed{
J
=
\frac{V}{nD}.
}
\tag{EQ-19}
$$

The propeller tip speed is

$$
\boxed{
V_{\mathrm{tip}}
=
\pi nD.
}
\tag{EQ-20}
$$

These correspond to Chapter-5 Eqs. (5.27), (5.29), (5.33), and (5.32), respectively.

---

## 12. Default Propeller Sizing: Speed-Power Chart Method

The default is

```text
propeller_sizing_method = "book_speed_power"
```

and follows the Chapter-5/Chapter-11 speed-power-coefficient design procedure.

First,

$$
\boxed{
C_s
=
\left(
\frac{
\rho_{\mathrm{ref}}
V_{\mathrm{ref}}^5
}{
P_{\mathrm{sh,unit}}
n^2
}
\right)^{1/5}.
}
\tag{EQ-21}
$$

For the variable-pitch, three-bladed Clark-Y preliminary-design chart used in the Chapter-11 example, ADaPT implements the polynomial fit

$$
\boxed{
J
\approx
0.156C_s^2
+
0.241C_s
+
0.138.
}
\tag{EQ-22}
$$

The propeller diameter follows from the definition of advance ratio:

$$
\boxed{
D
=
\frac{V_{\mathrm{ref}}}{nJ}.
}
\tag{EQ-23}
$$

The corresponding chart efficiency estimate is

$$
\boxed{
\eta_{p,\mathrm{chart}}
\approx
0.139C_s^3
-
0.749C_s^2
+
1.37C_s
+
0.0115.
}
\tag{EQ-24}
$$

The implementation bounds the estimated efficiency numerically to

$$
0\le\eta_{p,\mathrm{chart}}\le0.90.
$$

The polynomial relations are **fits to a particular preliminary-design propeller chart**, not universal propeller laws.

They should therefore be interpreted as adapted literature relationships suitable for conceptual sizing.

**Classification:** EQ-21 [L]; EQ-22 [A/L chart fit]; EQ-23 [D]; EQ-24 [A/L chart fit].

---

## 13. Standard Power-Coefficient Propeller Sizing

The second method is

```text
propeller_sizing_method = "book_power_coefficient".
```

From Eq. (EQ-17),

$$
C_P
=
\frac{P}{\rho n^3D^5}.
$$

Solving for diameter gives

$$
\boxed{
D
=
\left(
\frac{
P_{\mathrm{sh,unit}}
}{
\rho_{\mathrm{ref}}
n^3C_P
}
\right)^{1/5}.
}
\tag{EQ-25}
$$

The current input

```text
propeller_power_coefficient
```

is the standard nondimensional $C_P$, with default

$$
C_P=0.08.
$$

After diameter is calculated,

$$
\boxed{
J
=
\frac{V_{\mathrm{ref}}}{nD}.
}
\tag{EQ-26}
$$

The current implementation does not estimate chart efficiency for this method and reports

$$
\eta_{p,\mathrm{estimated}}=0.
$$

This does not mean the physical propeller efficiency is zero; it means this sizing branch does not supply a separate chart-efficiency estimate.

---

## 14. simplified Reduced-Order Propeller Sizing

For backward compatibility,

```text
propeller_sizing_method = "reduced_order"
```

uses

$$
\boxed{
D
=
\sqrt{
\frac{
P_{\mathrm{sh,unit}}
}{
\rho_{\mathrm{ref}}
V_{\mathrm{ref}}^3
C_{\mathrm{red}}
}
}.
}
\tag{EQ-27}
$$

Here,

$$
C_{\mathrm{red}}
=
\texttt{prop\_power\_coeff}
$$

with default

$$
C_{\mathrm{red}}=0.65.
$$

This coefficient is **not**

$$
C_P=\frac{P}{\rho n^3D^5}.
$$

Equation (EQ-27) is a simplified ADaPT conceptual scaling relation and should not be presented as a standard propeller-theory equation.

The current implementation only imposes the numerical floor

$$
\boxed{
D\ge0.05\ {\rm m}.
}
\tag{EQ-28}
$$


---

## 15. Propeller Tip-Speed Diagnostic

For all propeller-sizing methods,

$$
\boxed{
V_{\mathrm{tip}}
=
\pi nD.
}
\tag{EQ-29}
$$

The current preliminary upper guidance is

$$
800\ {\rm ft/s}
=
243.84\ {\rm m/s}.
$$

The component reports

$$
\boxed{
\Delta V_{\mathrm{tip}}
=
\max
\left(
V_{\mathrm{tip}}
-
243.84,
0
\right).
}
\tag{EQ-30}
$$

Thus

$$
\Delta V_{\mathrm{tip}}=0
$$

passes the preliminary tip-speed check, while a positive value indicates the amount above the guideline.

This is a diagnostic, not an automatic clipping operation.


---

## 16. Prime-Mover Core Mass

Three methods are available.

### 16.1 Technology Specific-Power Method

The default is

```text
prime_mover_mass_method = "specific_power".
```

For either prime-mover category,

$$
\boxed{
m_{\mathrm{PM}}
=
\frac{
P_{\mathrm{br,rated}}
}{
SP
}.
}
\tag{EQ-31}
$$

For reciprocating engines,

$$
SP=SP_{\mathrm{ICE}}
=
\texttt{ice\_specific\_power},
$$

with default

$$
SP_{\mathrm{ICE}}
=
1200\ {\rm W/kg}.
$$

For electric motors,

$$
SP=SP_{\mathrm{motor}}
=
\texttt{motor\_specific\_power},
$$

with default

$$
SP_{\mathrm{motor}}
=
5000\ {\rm W/kg}.
$$

This is a technology-based model rather than a universal literature WER.

It is useful for technology-sensitivity analysis because

$$
SP\uparrow
\quad\Rightarrow\quad
m_{\mathrm{PM}}\downarrow.
$$

However, changing specific power does not automatically change efficiency, cooling requirements, reliability, or installation mass.

### 16.2 Book Reciprocating-Engine Method

For

```text
prime_mover_mass_method = "book_reciprocating"
```

with

```text
engine_type = "reciprocating",
```

the current Chapter-5/Fig.-5.8 fit is

$$
\boxed{
W_{\mathrm{engine,total}}
=
N_p
\left[
4.848
\left(
HP_{\mathrm{unit}}
\right)^{0.7956}
\right].
}
\tag{EQ-32}
$$

Here,

$$
HP_{\mathrm{unit}}
=
\frac{
P_{\mathrm{br,unit}}
}{
745.6998716
}
$$

and Eq. (EQ-32) returns pounds before conversion to kilograms.

This is a historical empirical reciprocating-engine WER. It should not automatically be extrapolated to modern engines outside its source-data range.

If `book_reciprocating` is selected for an electric motor, the component falls back to the specific-power formulation rather than applying a reciprocating-engine equation to an electric machine.

### 16.3 Override Method

For validation/reference configurations,

$$
\boxed{
m_{\mathrm{PM}}
=
m_{\mathrm{PM,override}}.
}
\tag{EQ-33}
$$

This is a prescribed value and therefore must not be reported as an independently predicted validation result.

---

## 17. Propeller Mass

### 17.1 Book Method

The default is

```text
propeller_mass_method = "book".
```

Carichner and Nicolai Chapter 9 Eq. (9.16) is

$$
\boxed{
W_{\mathrm{prop}}
=
K_p
N_p
N_b^{0.391}
\left(
\frac{
D_{\mathrm{ft}}
HP_{\mathrm{unit}}
}{
1000
}
\right)^{0.782}.
}
\tag{EQ-34}
$$

The current implementation uses

$$
K_p=31.92.
$$

The equation is evaluated in its original imperial form:

- $D_{\mathrm{ft}}$ in feet,
- $HP_{\mathrm{unit}}$ in horsepower,
- resulting $W_{\mathrm{prop}}$ in pounds,

and then converted to kilograms.

This is the **total mass of all propellers**, because the equation explicitly contains $N_p$.

### 17.2 simplified Propeller-Mass Method

The compatibility model calculates mass per propeller as

$$
\boxed{
m_{\mathrm{prop,each}}
=
\max
\left(
k_{\mathrm{prop}}P_{\mathrm{sh,unit}},
m_{\mathrm{prop,min}}
\right),
}
\tag{EQ-35}
$$

and

$$
\boxed{
m_{\mathrm{prop}}
=
N_pm_{\mathrm{prop,each}}.
}
\tag{EQ-36}
$$

The default coefficient is

$$
k_{\mathrm{prop}}
=
1.2\times10^{-4}\ {\rm kg/W}.
$$

This is a simplified conceptual model, not the default literature WER.

---

## 18. Nacelle Mass

For the generic preliminary installation,

$$
\boxed{
m_{\mathrm{nac}}
=
k_{\mathrm{nac}}
\frac{
P_{\mathrm{br,rated}}
}{
1000
}.
}
\tag{EQ-37}
$$

For reciprocating engines,

$$
k_{\mathrm{nac,ICE}}
=
0.92\ {\rm kg/kW},
$$

while for electric motors,

$$
k_{\mathrm{nac,electric}}
=
3.0\ {\rm kg/kW}.
$$

These coefficients are explicitly conceptual/calibration parameters. They are not universal Carichner–Nicolai WER coefficients.

Reference-aircraft-specific values should therefore be introduced through a documented calibration or through `installation_mass_method="override"` rather than silently changing the universal defaults.

---

## 19. Mount/Pylon Mass

### 19.1 Reciprocating-Engine Book Method

For a generic reciprocating-engine installation with

```text
mount_mass_method = "book_for_recip",
```

the Chapter-9 relation is

$$
\boxed{
W_{\mathrm{mount}}
\approx
0.64W_{\mathrm{engine,total}}.
}
\tag{EQ-38}
$$

Since the same mass unit appears on both sides,

$$
\boxed{
m_{\mathrm{mount}}
=
0.64m_{\mathrm{PM}}.
}
\tag{EQ-39}
$$

This relation is applied only when mount mass is enabled.

### 19.2 simplified Thrust-Based Fallback

For electric or unconventional installations using the simplified mount method, the component first forms the per-unit thrust proxy

$$
\boxed{
T_{\mathrm{proxy,unit}}
=
\frac{
P_{\mathrm{sh,unit}}\eta_p
}{
V_{\mathrm{ref}}
}.
}
\tag{EQ-40}
$$

The mount mass is then

$$
\boxed{
m_{\mathrm{mount}}
=
N_p
k_{\mathrm{mount}}
\frac{
T_{\mathrm{proxy,unit}}
}{
1000
},
}
\tag{EQ-41}
$$

with default

$$
k_{\mathrm{mount}}
=
0.03\ {\rm kg/kN}.
$$

This is a conceptual fallback, not a literature structural WER.

---

## 20. Installation-Mass Methods

### 20.1 Generic

With

```text
installation_mass_method = "generic",
```

the component calculates:

- nacelle mass from Eq. (EQ-37),
- mount mass from the selected mount model.

This is the default preliminary-design treatment.

### 20.2 Structure-Integrated

For

```text
installation_mass_method = "structure_integrated",
```

the component retains

$$
\boxed{
m_{\mathrm{nac}}
=
k_{\mathrm{nac}}
P_{\mathrm{br,rated}}/1000
}
\tag{EQ-42}
$$

but sets

$$
\boxed{
m_{\mathrm{mount}}=0.
}
\tag{EQ-43}
$$

This is intended for semi-rigid/rigid configurations in which propulsion units are attached directly to the primary load-bearing structure.

The interpretation is **not** that propulsion installation has zero structural cost. Rather, the separate generic mount WER is omitted to reduce potential overlap with framework mass until a dedicated integrated-installation structural model is available.

### 20.3 Override

For reference-aircraft validation,

$$
\boxed{
m_{\mathrm{nac}}
=
m_{\mathrm{nac,override}},
}
\tag{EQ-44}
$$

$$
\boxed{
m_{\mathrm{mount}}
=
m_{\mathrm{mount,override}}.
}
\tag{EQ-45}
$$

These are prescribed values and must be labeled as such in validation tables.

---

## 21. Electrical Wiring Mass

When

```text
enable_wiring_mass = True
```

and

```text
engine_type = "electric",
```

the component evaluates

$$
\boxed{
m_{\mathrm{wire}}
=
k_{\mathrm{wire}}
\frac{
P_{\mathrm{br,rated}}
}{
1000
}.
}
\tag{EQ-46}
$$

The default is

$$
k_{\mathrm{wire}}=0.
$$

Therefore no wiring mass is silently imposed by default.

This term represents only propulsion-associated wiring assigned to this component. Architecture-level inverter, generator, battery, fuel-cell, or other electrical-system masses must remain in their authoritative subsystem models to prevent double counting.

---

## 22. Total Mechanical Propulsion Mass

The complete propulsion mass is

$$
\boxed{
m_{\mathrm{propulsion}}
=
m_{\mathrm{PM}}
+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}}
+
m_{\mathrm{wire}}.
}
\tag{EQ-47}
$$

The output

```text
total_mass
```

is the authoritative propulsion-system mass passed to the mass component:

$$
\boxed{
\text{Propulsion}
\rightarrow
m_{\mathrm{propulsion}}
\rightarrow
\text{mass}.
}
\tag{EQ-48}
$$

The simplified output

```text
motor_mass
```

is currently an alias of total **prime-mover core mass**, even when the prime mover is a reciprocating engine.

Similarly,

```text
pylon_mass
```

is a compatibility alias of

```text
mount_mass.
```

These aliases should not be interpreted as separate physical masses.

---

## 23. Outputs

### 23.1 Mission Power

| Output | Units | Meaning |
|---|---:|---|
| `shaft_power` | W | Mission shaft-power history |
| `required_power` | W | Backward-compatible alias of `shaft_power` |
| `brake_power` | W | Mission brake-power history |

### 23.2 Installed/Rated Power

| Output | Units | Meaning |
|---|---:|---|
| `takeoff_shaft_power` | W | Installed/rated shaft power available to Performance |
| `rated_shaft_power` | W | Total rated shaft power |
| `rated_brake_power` | W | Total rated brake power |
| `rated_shaft_power_per_unit` | W | Rated shaft power per propulsor |
| `rated_brake_power_per_unit` | W | Rated brake power per propulsor |

`takeoff_shaft_power` should not be described as a separately computed finite-speed takeoff requirement. In the current implementation it equals `rated_shaft_power`.

### 23.3 Propeller Diagnostics

| Output | Units | Meaning |
|---|---:|---|
| `propeller_diameter` | m | Preliminary propeller diameter |
| `propeller_speed_power_coefficient` | – | $C_s$ |
| `propeller_advance_ratio` | – | $J$ |
| `propeller_efficiency_estimated` | – | Chart-fit efficiency for speed-power method |
| `propeller_tip_speed` | m/s | $\pi nD$ |
| `propeller_tip_speed_violation` | m/s | Amount above 243.84 m/s |

### 23.4 Mass Outputs

| Output | Units | Meaning |
|---|---:|---|
| `total_mass` | kg | Total mechanical propulsion mass |
| `prime_mover_mass` | kg | Total engine/motor core mass |
| `motor_mass` | kg | simplified alias of prime-mover mass |
| `nacelle_mass` | kg | Total nacelle mass |
| `propeller_mass` | kg | Total propeller mass |
| `mount_mass` | kg | Total mounting/support mass |
| `pylon_mass` | kg | simplified alias of mount mass |
| `wiring_mass` | kg | Optional electric propulsion wiring mass |

`wiring_mass` exists only when wiring mass is enabled.

---

## 24. Propeller Efficiency: Two Distinct Quantities

The current component contains two conceptually different efficiency quantities.

### 24.1 `propeller_efficiency`

This is an **input** used by the simplified fallback

$$
P_{\mathrm{sh}}=\frac{TV}{\eta_p}
$$

and by the simplified thrust-based mount proxy.

It does not automatically vary with propeller geometry.

### 24.2 `propeller_efficiency_estimated`

This is an **output diagnostic** from the default Chapter-11 chart fit:

$$
\eta_{p,\mathrm{chart}}
=
f(C_s).
$$

The current component does not feed this chart estimate back into the mission shaft-power calculation.

Therefore,

$$
\boxed{
\texttt{propeller\_efficiency}
\neq
\texttt{propeller\_efficiency\_estimated}
}
$$

in the general case.

This distinction is preserved in documentation and validation.

---

## 25. Multidisciplinary Coupling

The principal coupling is

$$
\boxed{
\begin{array}{c}
m_{\mathrm{MTOW}},\;V,\;S,\;\text{mission state}\\
\downarrow\\
\text{Performance}\\
\downarrow\\
P_{\mathrm{shaft,required}}\\
\downarrow\\
\text{Propulsion}\\
\downarrow\\
P_{\mathrm{rated}},\;D_{\mathrm{prop}},\;m_{\mathrm{propulsion}}\\
\downarrow\\
\text{mass}\\
\downarrow\\
m_{\mathrm{MTOW}}
\end{array}
}
\tag{EQ-49}
$$

For architecture-specific energy systems,

$$
P_{\mathrm{brake}}
$$

also feeds the corresponding power/energy model, which determines fuel, hydrogen, electrical energy, and/or component masses.

The resulting energy-system masses return to mass, closing the energy–mass–propulsion loop.

---

## 26. Installed Power: Validation Versus Sizing

The same input supports two different study modes.

### 26.1 Reference-Capacity Validation

For a known aircraft,

$$
P_{\mathrm{installed}}
=
P_{\mathrm{reference}}.
$$

The model then uses

$$
P_{\mathrm{rated}}
=
\max(P_{\mathrm{mission,peak}},P_{\mathrm{reference}}).
$$

The reference installed rating is a prescribed input. It is not an independently predicted validation output.

If the configured mission requires more power than the published installation, that discrepancy must be investigated as a mission/performance/reference-data consistency issue rather than hidden by automatically increasing the published reference value.

### 26.2 Clean-Sheet Sizing

Set

$$
P_{\mathrm{installed}}<0.
$$

Then

$$
P_{\mathrm{rated}}
=
P_{\mathrm{mission,peak}}.
$$

This allows the mechanical propulsion system to size to the mission requirement.

The distinction between these two modes is essential when interpreting the BASI MB-30T and other reference-airship cases.

---

## 27. Technology Sensitivity

The specific-power formulation directly exposes technology effects.

For a fixed rated brake power,

$$
\boxed{
m_{\mathrm{PM}}
\propto
\frac{1}{SP}.
}
\tag{EQ-50}
$$

Thus

$$
SP\uparrow
\Rightarrow
m_{\mathrm{PM}}\downarrow.
$$

However, this should not be interpreted as a complete technology forecast. Changes in specific power do not automatically change:

- propulsive efficiency,
- thermal efficiency,
- cooling mass,
- nacelle mass,
- reliability,
- cost,
- noise,
- power electronics,
- maintenance requirements.

Those effects require their own models.

---

## 28. Assumptions and Limitations

| Item | Current treatment | Classification |
|---|---|---|
| Mission mechanical demand | Prefer direct Performance shaft power | Coupling/interface |
| simplified demand | $TV/\eta_p$ | Literature/fundamental |
| Gearbox | Constant efficiency | Assumption |
| Installed rating | Prescribed or peak mission demand | Design logic |
| Static thrust | Owned by Performance, not Propulsion | Responsibility boundary |
| Default propeller sizing | Chapter-11 $C_s/J$ chart fits | Adapted literature |
| Standard $C_P$ sizing | Selectable Eq. (5.27) method | Literature |
| simplified diameter | Reduced-order scaling | simplified conceptual |
| Propeller diameter clipping | Only 0.05 m numerical floor | Numerical safeguard |
| Tip speed | $\pi nD$ | Literature/fundamental |
| Tip-speed limit | 800 ft/s preliminary guidance | Literature guidance |
| Propeller efficiency | Prescribed for mission fallback | Assumption/input |
| Chart efficiency | Diagnostic only | Adapted literature |
| Prime mover | Specific power by default | Technology model |
| Book engine WER | Reciprocating only | Historical empirical |
| Propeller mass | Chapter-9 Eq. (9.16) | Literature empirical |
| Nacelle mass | kg/kW coefficient | Conceptual/calibration |
| Recip mount | $0.64m_{\mathrm{engine}}$ | Literature empirical |
| Electric/unconventional mount | Thrust proxy | Conceptual |
| Structure-integrated mount | Separate mount omitted | Ownership assumption |
| Wiring | Optional kg/kW model | User technology model |
| Blade aerodynamics | Not explicitly solved | Limitation |
| Variable pitch | Represented only through chart fit | Limitation |
| Helical tip Mach | Not calculated | Limitation |
| Noise | Not calculated | Limitation |
| Propeller-airframe interference | Not modeled | Limitation |
| Distributed-propulsion interference | Not modeled | Limitation |
| Cooling | Not modeled here | External/limitation |
| Detailed gearbox sizing | Not modeled | Limitation |

---

## 29. Provenance Classification

The documentation uses:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical relationship |
| **L** | Literature relationship |
| **A** | Adapted literature relationship |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **N** | Numerical safeguard |
| **D** | Derived/software relationship |
| **C** | Calibration/reference parameter |

Principal propulsion relations are classified as:

| Equation | Relationship | Classification |
|---|---|---|
| EQ-3–4 | Direct Performance power interface | D |
| EQ-5 | $\eta_p=TV/P$ | L/F |
| EQ-6 | $P=TV/\eta_p$ | D |
| EQ-7 | Pointwise direct/fallback logic | A/D |
| EQ-8 | Brake/shaft power | F/AS |
| EQ-9–14 | Rating and per-unit power | D |
| EQ-15 | Takeoff available power = rated power | D/interface |
| EQ-16 | Critical design node | AS/D |
| EQ-17 | $C_P$ | L |
| EQ-18 | $C_s$ | L |
| EQ-19 | Advance ratio | L |
| EQ-20 | Tip speed | L/F |
| EQ-21 | Speed-power coefficient evaluation | L |
| EQ-22 | $J(C_s)$ chart polynomial | A/L |
| EQ-23 | Diameter from $J$ | D |
| EQ-24 | $\eta(C_s)$ chart polynomial | A/L |
| EQ-25–26 | Standard $C_P$ diameter method | L/D |
| EQ-27 | Reduced-order diameter | C/simplified |
| EQ-28 | Diameter floor | N |
| EQ-29 | Tip speed | L/F |
| EQ-30 | Tip-speed violation | D/N |
| EQ-31 | Specific-power mass | AS/technology |
| EQ-32 | Historical reciprocating WER | L/E |
| EQ-33 | Prime-mover override | C |
| EQ-34 | Propeller mass Eq. 9.16 | L/E |
| EQ-35–36 | simplified propeller mass | C |
| EQ-37 | Nacelle kg/kW model | AS/C |
| EQ-38–39 | Reciprocating mount WER | L/E |
| EQ-40–41 | simplified mount proxy | AS/C |
| EQ-42–45 | Installation ownership/override | AS/C |
| EQ-46 | Wiring mass | AS/C |
| EQ-47–48 | Total mass and ownership | D |
| EQ-49 | MDAO coupling | D |
| EQ-50 | Specific-power sensitivity | D |

---

## 30. Numerical Implementation

### 30.1 Input Protection

The implementation contains small numerical guards including:

- $V\ge0.1$ m/s inside propeller sizing,
- $n\ge10^{-3}$ s$^{-1}$,
- $\rho\ge10^{-9}$ kg/m³,
- $P\ge1$ W inside the preliminary propeller-sizing helper,
- $D\ge0.05$ m,
- $C_P\ge10^{-6}$,
- $\eta_p$ clipped to 0.05–0.99,
- $\eta_{gb}$ clipped to 0.10–1.0.

These are numerical protections and bounds, not new physical laws.

### 30.2 Mission Vector Handling

Mission inputs are converted to the configured `num_steps`. Scalar inputs are broadcast; shorter arrays are edge-padded; longer arrays are truncated.

This is a software convenience and should not replace correct mission discretization upstream.

### 30.3 OpenMDAO Derivatives

The component currently declares finite-difference derivatives:

```python
self.declare_partials("*", "*", method="fd", step=1.0e-8)
```

with perturbation

$$
\Delta x=10^{-8}.
$$

This is a numerical implementation choice.

### 30.4 Piecewise Behavior

Nonsmooth behavior occurs through:

- direct versus fallback mission power,
- prescribed versus mission-sized installed power,
- prime-mover method selection,
- propeller-sizing method selection,
- installation method selection,
- mount method selection,
- numerical clipping and `max` operations.

These features should be considered in gradient-based optimization.

---

## 31. Verification Strategy

### 31.1 Mission-Power Verification

Construct known $T,V,\eta_p$ cases and verify

$$
P_{\mathrm{sh}}=\frac{TV}{\eta_p}.
$$

Then supply direct `mission_shaft_power_required` values and verify that they replace the fallback pointwise.

### 31.2 Rating Verification

Verify separately:

1. negative installed power:
   $$
   P_{\mathrm{rated}}=P_{\mathrm{peak}};
   $$

2. installed power below mission peak:
   $$
   P_{\mathrm{rated}}=P_{\mathrm{peak}};
   $$

3. installed power above mission peak:
   $$
   P_{\mathrm{rated}}=P_{\mathrm{installed}}.
   $$

Also verify all per-unit shaft and brake quantities.

### 31.3 Propeller-Speed-Power Verification

For a known $P,\rho,V,n$:

1. independently calculate $C_s$,
2. evaluate the Chapter-11 $J(C_s)$ polynomial,
3. calculate $D=V/(nJ)$,
4. calculate chart efficiency,
5. calculate $V_{\mathrm{tip}}=\pi nD$.

### 31.4 Standard-$C_P$ Verification

Verify

$$
D=
\left(
\frac{P}{\rho n^3C_P}
\right)^{1/5}
$$

and

$$
J=\frac{V}{nD}.
$$

### 31.5 Propeller-Mass Verification

Evaluate Chapter-9 Eq. (9.16) independently in imperial units and verify the kg conversion.

### 31.6 Prime-Mover Verification

Check:

- reciprocating specific-power method,
- electric specific-power method,
- book reciprocating WER,
- override method.

Ensure the book reciprocating equation is not applied to electric motors.

### 31.7 Installation Verification

Verify separately:

- generic reciprocating + book mount,
- generic electric + simplified mount,
- structure-integrated installation,
- override installation,
- mount disabled,
- optional wiring enabled/disabled.

### 31.8 Mass-Buildup Verification

Confirm

$$
m_{\mathrm{total}}
=
m_{\mathrm{PM}}
+
m_{\mathrm{nac}}
+
m_{\mathrm{prop}}
+
m_{\mathrm{mount}}
+
m_{\mathrm{wire}}.
$$

Also confirm

```text
motor_mass == prime_mover_mass
```

and

```text
pylon_mass == mount_mass.
```

### 31.9 Takeoff Interface Verification

Verify that

$$
P_{\mathrm{sh,TO}}
=
P_{\mathrm{sh,rated}}
$$

and that static-thrust calculations occur in Performance rather than being recreated inside Propulsion.

---

## 32. Reference-Airship Validation

Validation should separate **reference inputs** from **predictions**.

### 32.1 Prescribed Quantities

Examples include:

- number of engines,
- installed shaft power,
- engine/motor technology,
- propeller RPM when known,
- blade count,
- known prime-mover mass override,
- known installation mass override.

A zero-percent error in these quantities is not predictive validation.

### 32.2 Independently Predicted Quantities

Depending on which values are prescribed, useful predictions include:

- mission-required shaft power,
- rated power in clean-sheet mode,
- propeller diameter,
- propeller mass,
- prime-mover mass,
- nacelle mass,
- mount mass,
- total propulsion mass,
- tip-speed diagnostic.

### 32.3 Calibration

If a nacelle coefficient, specific power, installation override, or other parameter is selected to match a reference aircraft, label it `[C]`.

Do not subsequently present the matched quantity as an independent validation result.

---

## 33. Interpretation for Current Reference Cases

### 33.1 Zeppelin NT

For the Zeppelin NT reference case, the propulsion installation includes three reciprocating engines. The propulsion mass comparison should distinguish:

- engine core mass,
- propellers,
- nacelle/installation mass,
- mount treatment,
- total propulsion mass.

A reference-specific installation treatment should not be converted into a universal semi-rigid-airship rule.

### 33.2 AS700

For AS700, the Lycoming engine's published dry mass/specific power can provide an independent technology input for the reciprocating prime-mover model.

The aircraft-specific thrust-vectoring ducted-propeller arrangement is more detailed than the present low-order open-propeller model; therefore propeller-diameter and installation results should be interpreted at conceptual fidelity.

### 33.3 AV-10

A published/reference installed power may be retained even when mission utilization is low. Installed rating is a design/reference input and should not be reduced merely to force the utilization ratio toward unity.

### 33.4 BASI MB-30T

For the BASI MB-30T turboelectric case, the mechanical propulsors are electric motors even though upstream energy conversion is turbine/generator based.

The propulsion component should therefore be interpreted as owning the motor/propeller mechanical installation, while the turbine core, generator, inverter, and architecture-level electrical conversion are owned by the turboelectric power model according to the framework's subsystem partitioning.

If the configured mission requires more mechanical power than the published/reference installation, the resulting shortfall is a **capacity/mission consistency result**, not evidence that the propulsion mass bookkeeping should be changed.

---



## 35. Remaining Model-Development Priorities

The current propulsion component is suitable for conceptual MDAO, but further fidelity improvements may include:

- blade-element/momentum or higher-order propeller analysis,
- explicit blade pitch and activity factor,
- propeller-map interpolation across the full mission,
- helical tip Mach and compressibility,
- acoustic/noise constraints,
- propeller–hull interaction,
- distributed-propulsion interference,
- dedicated ducted-propeller models,
- dedicated structure-integrated propulsion-support sizing,
- validated contemporary nacelle databases,
- motor/controller/cooling installation partitioning,
- gearbox mass and variable gearbox efficiency,
- analytic or complex-step-compatible derivatives.

These should be treated as future fidelity upgrades rather than corrections required for the current low-order framework.

---

## 36. Software Traceability Summary

| Theory/model item | Current implementation |
|---|---|
| Preferred mission demand | direct `mission_shaft_power_required` |
| Fallback mission demand | `thrust * tas / propeller_efficiency` |
| Brake power | `shaft_power / gearbox_efficiency` |
| Peak mission power | maximum mission shaft power |
| Prescribed rating | `max(peak_mission, installed_shaft_power)` |
| Sizing mode | negative `installed_shaft_power` → peak mission |
| Takeoff available power | `rated_shaft_power` |
| Critical propeller state | highest mission shaft-power node |
| $C_s$ | $(\rho V^5/(Pn^2))^{1/5}$ |
| Default $J$ | Chapter-11 polynomial chart fit |
| Default diameter | $V/(nJ)$ |
| Chart efficiency | Chapter-11 polynomial fit |
| Standard $C_P$ method | $(P/(\rho n^3C_P))^{1/5}$ |
| simplified diameter | $\sqrt{P/(\rho V^3C_{\rm red})}$ |
| Diameter numerical floor | 0.05 m |
| Tip speed | $\pi nD$ |
| Tip-speed violation | `max(Vtip - 243.84, 0)` |
| Default prime mover | rated brake power / specific power |
| Book reciprocating engine | $N\,4.848\,HP^{0.7956}$ lb |
| Default propeller mass | Chapter-9 Eq. (9.16) |
| Generic nacelle | kg/kW conceptual coefficient |
| Recip mount | $0.64m_{\rm engine}$ |
| simplified mount | thrust-based proxy |
| Structure-integrated install | nacelle retained, separate mount zero |
| Override install | prescribed nacelle + mount |
| Wiring | optional kg/kW electric model |
| Total propulsion mass | prime mover + nacelle + propeller + mount + wiring |
| Derivatives | finite difference, $10^{-8}$ step |

---

## 37. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.

Relevant material includes:

- Chapter 5 — airship propulsion and propeller theory,
- Eq. (5.27) — propeller power coefficient,
- Eq. (5.29) — speed-power coefficient,
- Eq. (5.30) — propulsive efficiency,
- Eq. (5.32) — propeller tip speed,
- Eq. (5.33) — advance ratio,
- Chapter-5 reciprocating-engine mass trends,
- Chapter 9 Eq. (9.12) — engine-mount mass,
- Chapter 9 Eq. (9.16) — propeller mass,
- Chapter 11 — integrated preliminary airship propulsion design and Clark-Y chart-fit application.

---

