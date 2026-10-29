# Mass Estimation

The `AirshipMass` component performs the conceptual airship mass buildup and closes operating empty mass (OEM) and maximum takeoff mass (MTOM) for the ADaPT multidisciplinary sizing framework. It supports **non-rigid, semi-rigid, and rigid** structural arrangements and multiple propulsion/energy architectures.

The current implementation is deliberately not a single monolithic statistical mass equation. It combines literature-based component **mass-estimating relationships (MERs)**, explicit subsystem masses supplied by their authoritative models, and clearly identified conceptual/calibration relationships where a universal literature MER is not available.

The principal theory source is Carichner and Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies* [1], especially Chapters 6, 8, 9, and 11. Units: OpenMDAO inputs/outputs are SI. Literature WERs that are defined in imperial units are evaluated internally in their original units and then converted back to SI. This avoids silently reusing imperial numerical coefficients as SI coefficients. 

A critical bookkeeping convention in the current implementation is:

> **Helium is a lifting-gas state quantity and is not included in OEM or MTOM.**

The component calculates helium mass and volume for aerostatic and volume diagnostics, but vehicle mass closure uses the book-consistent net-buoyancy convention rather than adding helium again as an aircraft mass item.

---

## 1. Model Scope

The mass model accounts for:

- non-rigid envelope mass using the Chapter-8 envelope MER,
- ballonet fabric mass,
- suspension-curtain mass,
- semi-rigid/rigid outer and internal envelope mass,
- conceptual semi-rigid/rigid framework mass,
- tail fixed-structure, control-surface, and actuator masses,
- gondola/crew-station mass,
- conventional landing gear or ACLS mass,
- conventional liquid-fuel tank hardware when enabled,
- pressure-system mass when enabled,
- vehicle-management-system (VMS) mass when enabled,
- propulsion-system mass supplied by the propulsion model,
- power-system mass supplied by the architecture-specific power model,
- hydrogen-tank-system mass supplied by the tank model when applicable,
- crew mass,
- miscellaneous systems,
- optional design margin,
- payload,
- installed mission consumable mass,
- ballast,
- lifting-gas volume and helium-mass diagnostics,
- internal-volume feasibility, and
- coupled OEM/MTOM closure.

The component does **not** independently size the propulsion system, battery, fuel cell, solar system, hydrogen tank, or mission fuel/hydrogen requirement. Those quantities remain owned by their corresponding subsystem models.

---

## 2. Mass-Ownership Convention

The component follows an explicit ownership convention to avoid double counting.

### 2.1 Externally Owned Installed Systems

The following masses enter `AirshipMass` as inputs:

$$
m_{\mathrm{prop}}
$$

from the propulsion component,

$$
m_{\mathrm{power}}
$$

from the architecture-specific power/energy component, and, for tank-using hydrogen architectures,

$$
m_{\mathrm{tank}}
$$

from the hydrogen-storage component.

The generic input

```text
consumable_mass
```

represents installed mission consumable mass. Depending on architecture this may be hydrocarbon fuel, hydrogen, or zero for architectures without a consumable fuel.

The mass component therefore **assembles** these masses rather than recalculating them.

### 2.2 Conventional Liquid-Fuel Tank Hardware

The current component can separately estimate the **empty hardware mass** of a conventional liquid-fuel tank using a Chapter-9/11 MER. This is distinct from the fuel itself:

$$
m_{\mathrm{fuel,tank}}
\in OEM,
\qquad
m_{\mathrm{fuel}}
=\texttt{consumable\_mass}
\notin OEM.
$$

### 2.3 Helium Ownership

The component calculates

$$
V_{\mathrm{He,max}},
\qquad
m_{\mathrm{He}},
\qquad
V_{\mathrm{air,max}}
$$

for lifting-gas and volume diagnostics.

However,

$$
\boxed{
m_{\mathrm{He}}\notin m_{\mathrm{OEM}}
}
\tag{EQ-1}
$$

and

$$
\boxed{
m_{\mathrm{He}}\notin m_{\mathrm{MTOM}}.
}
\tag{EQ-2}
$$

This prevents double counting when aerostatic lift is handled through the net air-minus-helium buoyancy formulation.

**Classification:** vehicle bookkeeping convention consistent with the adopted aerostatic formulation.

---

## 3. Vehicle Mass Definitions

### 3.1 Operating Empty Mass

The current implementation closes OEM from

$$
\boxed{
\begin{aligned}
m_{\mathrm{OEM}}={}&
m_{\mathrm{env}}
+m_{\mathrm{ballonet}}
+m_{\mathrm{curtain}}
+m_{\mathrm{frame}}
+m_{\mathrm{gondola}}
+m_{\mathrm{tail,OEM}}\\
&+m_{\mathrm{landing}}
+m_{\mathrm{prop}}
+m_{\mathrm{power}}
+m_{\mathrm{H_2,tank}}
+m_{\mathrm{fuel,tank}}\\
&+m_{\mathrm{crew}}
+m_{\mathrm{pressure}}
+m_{\mathrm{VMS}}
+m_{\mathrm{misc}}
+m_{\mathrm{margin}} .
\end{aligned}
}
\tag{EQ-3}
$$

Terms not active for a selected architecture/configuration are zero.

### 3.2 Unmargined OEM

When a design margin is enabled,

$$
\boxed{
m_{\mathrm{OEM,unmargined}}
=
m_{\mathrm{OEM}}
-
m_{\mathrm{margin}}.
}
\tag{EQ-4}
$$

### 3.3 Operational Mass

The current diagnostic definition is

$$
\boxed{
m_{\mathrm{operational}}
=
m_{\mathrm{OEM}}
+
m_{\mathrm{payload}}.
}
\tag{EQ-5}
$$

### 3.4 Maximum Takeoff Mass

$$
\boxed{
m_{\mathrm{MTOM}}
=
m_{\mathrm{OEM}}
+
m_{\mathrm{payload}}
+
m_{\mathrm{consumable}}
+
m_{\mathrm{ballast}}.
}
\tag{EQ-6}
$$

Helium is not added to Eq. (EQ-6).

---

## 4. Architecture Support

The structural architecture is selected through

```text
airship_type
```

with

$$
\boxed{
\text{non-rigid},\quad
\text{semi-rigid},\quad
\text{rigid}.
}
\tag{EQ-7}
$$

The energy/propulsion architecture is selected through `power_source`. The current registry includes:

- conventional reciprocating,
- turboprop,
- turboelectric,
- hydrogen reciprocating,
- hydrogen fuel cell,
- battery only,
- solar battery,
- solar-RFC,
- hydrogen hybrid,
- solar-hydrogen hybrid, and
- conventional-battery hybrid.

Tank-system inputs are activated for the hydrogen architectures registered in `TANK_SOURCES`.

Structural class and propulsion architecture are independent modeling dimensions. A non-rigid airship is not inherently tied to a particular propulsion system, and a rigid airship is not inherently turboelectric.

---

## 5. Principal OpenMDAO Inputs

An OpenMDAO component input is not necessarily an overall design requirement. Some quantities are outputs of other disciplines or system-level design variables.

### 5.1 Geometry Inputs

| Input | Symbol | Default | Units | Role |
|---|---:|---:|---:|---|
| `payload` | $m_{PL}$ | 1123 | kg | Payload mass |
| `aerodynamic_reference_area` | $S_{\mathrm{wet}}$ | 1050 | m² | External hull area used by envelope MER |
| `gross_volume` | $V$ | 4979 | m³ | Gross hull volume |
| `ballonet_volume` | $V_B$ | 500 | m³ | Installed ballonet capacity |
| `fin_area` | $S_{f,\mathrm{simplified}}$ | 50 | m² | simplified tail-area input |
| `horizontal_tail_planform_area` | $S_{HT}$ | 25 | m² | Horizontal-tail planform |
| `vertical_tail_planform_area` | $S_{VT}$ | 25 | m² | Vertical-tail planform |
| `length` | $L$ | 53.6 | m | Hull length |
| `max_diameter` | $D_{\max}$ | 13.1 | m | Hull maximum diameter |

Semi-rigid and rigid configurations additionally receive:

- `outer_envelope_area`,
- `inner_envelope_area`,
- `framework_total_member_length`.

Rigid configurations additionally receive:

- `gas_cell_total_volume`.

### 5.2 Gondola and Tail-Loading Inputs

| Input | Default | Units | Role |
|---|---:|---:|---|
| `gondola_length` | 13.1 | m | Category-2/3 gondola MER |
| `gondola_width` | 2.56 | m | Category-2/3 gondola MER |
| `gondola_height` | 2.29 | m | Category-2/3 gondola MER |
| `gondola_surface_area` | 0 | m² | Category-3 area; fallback generated if absent |
| `maximum_speed` | 19.57 | m/s | Gondola MER speed |
| `max_dynamic_pressure` | 240 | Pa | Tail MER loading |

### 5.3 Conventional Fuel-Tank Inputs

| Input | Default | Role |
|---|---:|---|
| `n_fuel_tanks` | 2 | Number of conventional fuel tanks |
| `integral_fuel_tank_flag` | 0 | 0 non-integral; 1 integral |
| `liquid_fuel_density_lb_gal` | 6.0 lb/US gal | Fuel density for tank-volume conversion |
| `n_engine` | 2 | Number of engines used by fuel-tank MER |

### 5.4 Installed-System Inputs

| Input | Symbol | Units | Role |
|---|---:|---:|---|
| `propulsion_mass` | $m_{\mathrm{prop}}$ | kg | Externally owned propulsion installation |
| `power_system_mass` | $m_{\mathrm{power}}$ | kg | Externally owned power/energy system |
| `power_system_volume` | $V_{\mathrm{power}}$ | m³ | Internal volume occupied by power system |
| `tank_mass` | $m_{\mathrm{H_2,tank}}$ | kg | Empty hydrogen tank-system mass |
| `tank_installed_volume` | $V_{\mathrm{H_2,tank}}$ | m³ | Internal hydrogen-storage volume |

### 5.5 Mission and Configuration Inputs

| Input | Default | Units | Role |
|---|---:|---:|---|
| `cruise_altp` | 914 | m | Retained mission altitude input |
| `cruise_disa` | 0 | K | Temperature deviation used for gas-state evaluation |
| `max_altitude` | 3048 | m | Maximum pressure altitude for maximum helium volume |
| `BR_takeoff` | 0.90 | – | Buoyancy ratio used by conventional landing-gear MER |
| `n_crew` | 1 | – | Crew count |
| `consumable_mass` | 0 | kg | Installed mission fuel/hydrogen |
| `ballast_mass` | 0 | kg | Ballast |
| `acls_area` | 377 | m² | ACLS area when ACLS is selected |

---

## 6. Principal Model Options

### 6.1 Non-Rigid Envelope

| Option | Default | Meaning |
|---|---:|---|
| `envelope_mass_method` | `book` | `book` or simplified effective areal-density method |
| `envelope_fabric_areal_density` | $0.383/(1.20\,1.26)$ kg/m² | Raw baseline fabric density |
| `envelope_manufacturing_factor` | 1.20 | Chapter-8 $F_{MA}$ |
| `envelope_attachment_factor` | 1.26 | Chapter-8 $F_{AF}$ |
| `envelope_areal_density_nonrigid` | 0.383 kg/m² | simplified effective density only |

### 6.2 Ballonet and Curtain

| Option | Default | Meaning |
|---|---:|---|
| `ballonet_fabric_density_lb_ft2` | 0.035 | Ballonet fabric density in original MER units |
| `ballonet_mass_factor` | 1.13 | Chapter-9 ballonet allowance |
| `include_ballonet_mass` | `True` | Enables ballonet fabric mass |
| `include_suspension_curtain` | `True` | Enables suspension-curtain mass |
| `curtain_area_fraction` | 0.20 | Curtain area / hull side projection |
| `curtain_joint_factor` | 1.06 | Assembly/joint factor |
| `curtain_fabric_density_lb_ft2` | 0.028 | Baseline curtain material density |

### 6.3 Tail

| Option | Default | Meaning |
|---|---:|---|
| `tail_mass_method` | `book_lightmass` | Chapter-9 lightmass tail or simplified areal model |
| `tail_control_surface_fraction` | 0.20 | Movable area fraction |
| `tail_attachment_factor` | 1.26 | Fixed-tail attachment factor |
| `tail_actuator_installation_factor` | 1.15 | Actuator installation factor |
| `tail_fpsq_low_q` | 0.30 lb/ft² | Low-$q$ structural coefficient |
| `tail_fpsq_high_q` | 1.00 lb/ft² | High-$q$ structural coefficient |
| `tail_fact_low_q` | 0.08 lb/ft² | Low-$q$ actuator coefficient |
| `tail_fact_high_q` | 0.79 lb/ft² | High-$q$ actuator coefficient |
| `fin_areal_density` | 4.90 kg/m² | simplified-only tail density |

### 6.4 Gondola

| Option | Default | Meaning |
|---|---:|---|
| `gondola_mass_method` | `book` | Book, override, or simplified |
| `gondola_category` | 2 | Chapter-9 payload category 1, 2, or 3 |
| `gondola_mass_override` | 1500 kg | Used only in override mode |

### 6.5 Semi-Rigid/Rigid Structure

| Option | Default | Meaning |
|---|---:|---|
| `outer_envelope_areal_density` | 1.07 kg/m² | Conceptual/calibration parameter |
| `inner_envelope_areal_density` | 0.10 kg/m² | Conceptual/calibration parameter |
| `framework_mass_model` | `v23` | `linear`, `v23`, `ld`, or `fraction_envelope` |
| `frame_linear_density` | 1.5 kg/m | Linear-model parameter |
| `k_framework_v23` | 0.35 | $V^{2/3}$-model coefficient |
| `k_framework_ld` | 2.0 | Alternative $V^{2/3}$-scaled coefficient |
| `framework_mass_frac_cap` | 0.22 | Optimization safeguard |

The book does not provide one universal closed-form framework MER valid for all semi-rigid and rigid layouts. These framework relations are therefore explicit conceptual/calibration models, not direct literature equations.

### 6.6 Landing System

| Option | Default | Meaning |
|---|---:|---|
| `landing_system` | `conventional` | Conventional gear or ACLS |
| `landing_gear_method` | `book` | Chapter-9 gear MER or simplified fraction |
| `conventional_gear_type` | `tricycle` | Single or tricycle |
| `landing_gear_fraction` | 0.0167 | simplified-only fraction |
| `acls_coefficient_lb_ft2` | 1.6 | Chapter-9 ACLS coefficient in imperial units |

### 6.7 Pressure System, VMS, Miscellaneous, and Margin

| Option | Default | Meaning |
|---|---:|---|
| `pressure_system_mass_method` | `none` | none, book fraction, or override |
| `pressure_system_fraction` | 0.02 | OEM fraction when enabled |
| `pressure_system_mass_override` | 0 | Direct override |
| `vms_mass_method` | `none` | none, book fraction, or override |
| `vms_fraction` | 0.03 | OEM fraction when enabled |
| `vms_mass_override` | 0 | Direct override |
| `miscellaneous_fraction` | 0.035 | Fraction of OEM |
| `crew_mass_each` | 250 lb | Crew + luggage per person |
| `apply_mass_margin` | `False` | Enables conceptual design margin |
| `mass_margin_fraction` | 0.06 | Margin fraction when enabled |

The default pressure and VMS methods are `none`; therefore the 2% and 3% fractions do not contribute unless explicitly activated.


### 6.9 Supporting Evidence for Non-Book Coefficients

The coefficients below are not universal material or structural constants; they are
conceptual/calibration values selected for the airship class represented by ADaPT.
Their magnitudes are supported by independent literature or historical ranges as
summarized below.

- **Non-rigid raw envelope fabric density:** the default
  `0.383/(1.20\,1.26) \approx 0.2533 kg/m^2` lies within published structural
  airship laminate ranges of approximately 100--480 g/m². Thin stratospheric
  laminates are lighter, while full-scale structurally loaded non-rigid envelopes
  are reported at substantially higher areal densities. The resulting
  `0.383 kg/m²` effective installed density is therefore a class-appropriate
  calibrated value rather than an arbitrary constant [2--6].
- **Suspension-curtain fabric density:** `0.028 lb/ft² \approx 0.137 kg/m²`
  is consistent with structural UHMWPE/Vectran fabric ranges of roughly
  100--230 g/m². It is deliberately much heavier than non-structural
  backpacking-grade Dyneema sheeting and is therefore appropriate as a preliminary
  load-bearing curtain value [2--6].
- **Semi-rigid/rigid envelope densities:** `1.07 kg/m²` for the outer cover and
  `0.10 kg/m²` for the inner gas-cell envelope are conceptual values. Historical
  rigid-airship outer covers used doped cotton systems in an approximate
  0.8--1.3 kg/m² range, while lightmass gas-cell fabrics were substantially
  lighter. The defaults preserve this expected ordering [9].
- **Framework coefficients:** the `V^{2/3}` exponent has a classical structural
  basis in rigid-airship scaling, whereas `k_framework_v23 = 0.35` remains an
  ADaPT calibration coefficient. The alternative coefficients and the
  `framework_mass_frac_cap` are likewise conceptual/calibration or numerical
  controls, not independently validated universal constants [7--9].
- **simplified landing-gear fraction:** `0.0167` is retained only for compatibility.
  Its magnitude is directionally plausible because airship landing systems do not
  react the full vehicle mass in the same way as conventional aircraft landing
  gear; however, no independent source establishes 1.67% as a universal airship
  coefficient. The book-based landing-gear method remains the default [2,8].
- **Crew mass:** `250 lb/person` is a conservative crew-plus-kit allowance. FAA
  mass-and-balance guidance and survey data provide adult passenger/crew
  reference masss near 190--205 lb before allowing additional crew equipment
  and luggage, supporting the magnitude of the adopted value [10].
- **Miscellaneous systems:** the `3.5%` OEM fraction follows the conventional
  airship conceptual-example basis and is also consistent with the single-digit
  percentage magnitude commonly used for fixed equipment/furnishings in
  conceptual aircraft/airship mass estimation [1,11].
- **Design margin:** the `6%` value is directly supported by the approximately
  5--10% conceptual margin range discussed in the book and therefore does not
  require an additional independent coefficient source [1].

These comparisons support the **magnitude and physical direction** of the
non-book coefficients; they do not convert the coefficients into universal
literature MERs. Where the model is calibrated, the calibration status should
remain explicit in validation and sensitivity studies.

### 6.8 Lifting-Gas/Volume Parameters

| Option | Default | Meaning |
|---|---:|---|
| `helium_calibration_factor` | 1.0 | Optional deliberate helium-state calibration |
| `structure_volumetric_index` | 0.0 | Fraction of lifting volume unavailable to gas |
| `gondola_volumetric_index` | 0.0 m³/kg | simplified internal-gondola displacement proxy |
| `buoyancy_reserve` | 0.0 | Additional lifting-volume reserve |
| `minimum_helium_volume` | $10^{-6}$ m³ | Numerical floor |

The current zero defaults are important: no hidden 15% buoyancy reserve, gondola-volume penalty, or structural-volume penalty is imposed unless explicitly configured.

---

## 7. Unit Treatment

OpenMDAO interfaces use SI units. Literature MERs originally defined in imperial units are evaluated internally in their original unit system and converted back to SI.

The principal conversion constants are

$$
1\ {\rm kg}=2.20462262185\ {\rm lb},
$$

$$
1\ {\rm m}=3.28083989501\ {\rm ft},
$$

$$
1\ {\rm m^2}=10.7639104167\ {\rm ft^2},
$$

$$
1\ {\rm m^3}=35.3146667215\ {\rm ft^3},
$$

and

$$
1\ {\rm Pa}=0.0208854342730\ {\rm psf}.
$$

This is important because empirical coefficients from the book must not be numerically reused as SI coefficients unless they have been converted.

---

## 8. Non-Rigid Envelope Mass

With

```text
envelope_mass_method = "book"
```

the Chapter-8 relation is

$$
\boxed{
m_{\mathrm{env}}
=
S_{\mathrm{wet}}
\,\sigma_{\mathrm{fabric}}
\,F_{MA}
\,F_{AF}.
}
\tag{EQ-8}
$$

The defaults are

$$
F_{MA}=1.20,
\qquad
F_{AF}=1.26,
$$

and

$$
\sigma_{\mathrm{fabric}}
=
\frac{0.383}{1.20(1.26)}
\approx0.2533\ {\rm kg/m^2}.
$$

Consequently, the default effective installed areal density remains approximately

$$
0.383\ {\rm kg/m^2}.
$$

The **equation form** is literature based, while the baseline raw material density is an implementation/calibration value.

With

```text
envelope_mass_method = "simplified_areal"
```

the retained compatibility relation is

$$
\boxed{
m_{\mathrm{env,simplified}}
=
S_{\mathrm{wet}}
\sigma_{\mathrm{env,simplified}}.
}
\tag{EQ-9}
$$

**Classification:** EQ-8 [L] with baseline material parameter [C/AS]; EQ-9 simplified [C].

---

## 9. Semi-Rigid and Rigid Envelope Mass

For semi-rigid and rigid vehicles,

$$
\boxed{
m_{\mathrm{env}}
=
S_{\mathrm{outer}}\sigma_{\mathrm{outer}}
+
S_{\mathrm{inner}}\sigma_{\mathrm{inner}}.
}
\tag{EQ-10}
$$

The defaults are

$$
\sigma_{\mathrm{outer}}=1.07\ {\rm kg/m^2},
\qquad
\sigma_{\mathrm{inner}}=0.10\ {\rm kg/m^2}.
$$

These values are conceptual/calibration parameters. They are not presented as universal material constants or as a single book MER.


Independent historical evidence provides a magnitude check for these non-book
defaults. The `1.07 kg/m²` outer-cover value lies within an approximate
0.8--1.3 kg/m² range associated with doped-cotton outer covers on classic rigid
airships, while `0.10 kg/m²` for the inner gas-cell envelope is consistent with
the much lighter gas-cell fabric used for the gas-retention function. The
relative ordering, with the gas-cell envelope substantially lighter than the
outer weather cover, is physically consistent with these historical
configurations [9]. These values should therefore be treated as
**conceptual/calibration parameters**, not universal material properties.

---

## 10. Ballonet Fabric Mass

For non-rigid and semi-rigid vehicles with ballonet mass enabled, the initial model represents the installed capacity by two equal spherical ballonets.

For total installed ballonet volume $V_B$,

$$
V_{B,1}=V_{B,2}=\frac{V_B}{2}.
$$

The equivalent radius of each sphere is

$$
\boxed{
r_B=
\left(
\frac{3(V_B/2)}{4\pi}
\right)^{1/3}.
}
\tag{EQ-11}
$$

The total fabric area is

$$
\boxed{
S_B=2(4\pi r_B^2).
}
\tag{EQ-12}
$$

The Chapter-8/9 mass relation is evaluated in imperial units:

$$
\boxed{
W_B
=
\sigma_B S_B F_B,
}
\tag{EQ-13}
$$

with default

$$
\sigma_B=0.035\ {\rm lb/ft^2},
\qquad
F_B=1.13.
$$

The result is converted to kilograms.

For rigid airships,

$$
\boxed{
m_{\mathrm{ballonet}}=0.
}
\tag{EQ-14}
$$

The factor 1.13 belongs to the **ballonet mass relation**. It is not a multiplier on ballonet volume sizing.

**Classification:** literature-supported initial-sizing MER.

---

## 11. Suspension-Curtain Mass

The suspension curtain is included for non-rigid and semi-rigid configurations when enabled.

The side projection of the axisymmetric hull is approximated as an ellipse:

$$
\boxed{
S_{\mathrm{side}}
=
\frac{\pi L D_{\max}}{4}.
}
\tag{EQ-15}
$$

The curtain area follows the Chapter-8 conceptual relation

$$
\boxed{
S_{\mathrm{curtain}}
=
f_{\mathrm{curtain}}S_{\mathrm{side}},
}
\tag{EQ-16}
$$

with

$$
f_{\mathrm{curtain}}=0.20.
$$

Curtain mass is

$$
\boxed{
W_{\mathrm{curtain}}
=
\sigma_{\mathrm{curtain}}
S_{\mathrm{curtain}}
F_J,
}
\tag{EQ-17}
$$

where the defaults are

$$
\sigma_{\mathrm{curtain}}=0.028\ {\rm lb/ft^2},
\qquad
F_J=1.06.
$$

The 0.028 lb/ft² material value follows the conceptual worked-material example and should be replaced when a specific curtain material/stress design is available.


As an independent magnitude check, structural-grade UHMWPE/Vectran airship
fabrics are reported at approximately 100--230 g/m², whereas
non-structural backpacking-grade Dyneema composite fabrics can be only
11--17 g/m². The adopted `0.028 lb/ft² \approx 137 g/m²` therefore falls in the
structural-fabric range rather than the non-structural sheeting range [2--6].
This supports the material-class assumption, but it is not a stress-sized
curtain design coefficient.

Rigid airships receive zero suspension-curtain mass in this model.

---

## 12. Tail Mass

The default tail model is

```text
tail_mass_method = "book_lightmass"
```

and follows the Chapter-9 lightmass structural-tail approach.

### 12.1 Dynamic-Pressure Coefficients

The book provides endpoint coefficients:

for

$$
q\le1\ {\rm psf},
$$

$$
F_{PSQ}=0.30\ {\rm lb/ft^2},
\qquad
F_{act}=0.08\ {\rm lb/ft^2},
$$

and for

$$
q\ge10\ {\rm psf},
$$

$$
F_{PSQ}=1.00\ {\rm lb/ft^2},
\qquad
F_{act}=0.79\ {\rm lb/ft^2}.
$$

For

$$
1<q<10\ {\rm psf},
$$

ADaPT linearly interpolates:

$$
\boxed{
t=\frac{q_{\mathrm{psf}}-1}{9},
}
\tag{EQ-18}
$$

$$
\boxed{
F_{PSQ}
=
F_{PSQ,L}
+t(F_{PSQ,H}-F_{PSQ,L}),
}
\tag{EQ-19}
$$

$$
\boxed{
F_{act}
=
F_{act,L}
+t(F_{act,H}-F_{act,L}).
}
\tag{EQ-20}
$$

The endpoint values are literature based; the intermediate linear interpolation is an ADaPT adaptation.

### 12.2 Fixed Tail

Let

$$
S_T=S_{HT}+S_{VT},
$$

and let $f_c$ be the control-surface fraction. Then

$$
S_{\mathrm{fixed}}
=
(1-f_c)S_T.
$$

The fixed-tail relation is

$$
\boxed{
W_{\mathrm{fixed}}
=
F_{PSQ}
(1-f_c)
S_T
F_{AF}.
}
\tag{EQ-21}
$$

### 12.3 Control Surface

The movable/control-surface contribution is evaluated separately using the Chapter-9 lightmass-tail formulation and the control-surface area

$$
\boxed{
S_{\mathrm{control}}
=
f_cS_T.
}
\tag{EQ-22}
$$

### 12.4 Actuator

Actuator mass is evaluated using $F_{act}$ and the configured installation factor

$$
F_{\mathrm{act,inst}}=1.15.
$$

The component exposes

```text
tail_fixed_mass
tail_control_surface_mass
tail_actuator_mass
tail_fpsq_used
tail_fact_used
```

for transparent bookkeeping.

### 12.5 VMS Double-Counting Prevention

Chapter 11 groups actuator mass with the vehicle-management system. Therefore, when

```text
vms_mass_method = "book_fraction"
```

the OEM tail contribution is

$$
\boxed{
m_{\mathrm{tail,OEM}}
=
m_{\mathrm{fixed}}
+
m_{\mathrm{control}},
}
\tag{EQ-23}
$$

while actuator mass is added through the VMS term.

Otherwise,

$$
\boxed{
m_{\mathrm{tail,OEM}}
=
m_{\mathrm{fin}},
}
\tag{EQ-24}
$$

where `fin_mass` includes the complete physical tail result.

This ownership rule prevents actuator mass from being counted twice.

### 12.6 simplified Tail Model

The retained simplified mode is

$$
\boxed{
m_{\mathrm{fin,simplified}}
=
S_{\mathrm{fin,simplified}}
\sigma_{\mathrm{fin}}.
}
\tag{EQ-25}
$$

It is provided only for backward compatibility.

---

## 13. Gondola Mass

The default is

```text
gondola_mass_method = "book"
```

with Chapter-9 category selection.

### 13.1 Category 1

$$
\boxed{
W_G=0.15W_{\mathrm{payload}}.
}
\tag{EQ-26}
$$

This is evaluated in pounds and converted to kilograms.

### 13.2 Category 2

The Chapter-9 crew-station/systems relation is

$$
\boxed{
W_{G,2}
=
353
\left[
\left(\frac{L_G}{10}\right)^{0.857}
\left(\frac{W_G+H_G}{10}\right)
\left(\frac{V_{\max}}{10}\right)^{0.338}
\right]^{1.1},
}
\tag{EQ-27}
$$

where dimensions are in feet, speed is in knots, and the resulting mass is in pounds.

### 13.3 Category 3

For a heavy payload bay,

$$
\boxed{
W_{G,3}
=
1.875S_G+W_{G,2},
}
\tag{EQ-28}
$$

with $S_G$ in ft².

If an external gondola surface area is not supplied, the component uses the six-side rectangular approximation

$$
\boxed{
S_G
=
2(L_GW_G+L_GH_G+W_GH_G).
}
\tag{EQ-29}
$$

This fallback is a geometric approximation, not a literature statement that all gondolas are rectangular.

### 13.4 Override and simplified Modes

`override` uses a deliberately supplied user defined reference value/calibrated value in case the gondola mass is known.

`simplified` uses ADaPT logic:

$$
m_G=1500\ {\rm kg}
$$

for non-rigid configurations and

$$
m_G=250+0.05m_{\mathrm{payload}}
$$

for semi-rigid/rigid configurations.

These simplified relations are not the default literature-based model.

---

## 14. Semi-Rigid and Rigid Framework Mass

Carichner and Nicolai discuss semi-rigid and rigid structural concepts but do not provide one universal MER applicable to every possible frame layout. The current framework model is therefore explicitly conceptual.

Let

$$
A_V=V^{2/3}.
$$

### 14.1 Linear Member-Length Model

For

```text
framework_mass_model = "linear"
```

$$
\boxed{
m_{\mathrm{frame}}
=
\lambda_fL_{\mathrm{members}},
}
\tag{EQ-30}
$$

where the default is

$$
\lambda_f=1.5\ {\rm kg/m}.
$$

This is a conceptual structural proxy. The default 1.5 kg/m must not be described as a validated universal rigid-airship structural density.

### 14.2 $V^{2/3}$ Model

For

```text
framework_mass_model = "v23"
```

$$
\boxed{
m_{\mathrm{frame}}
=
k_{V23}V^{2/3},
}
\tag{EQ-31}
$$

with default

$$
k_{V23}=0.35.
$$

### 14.3 `ld` Alternative

The current implementation of

```text
framework_mass_model = "ld"
```

is

$$
\boxed{
m_{\mathrm{frame}}
=
k_{LD}V^{2/3},
}
\tag{EQ-32}
$$

with

$$
k_{LD}=2.0.
$$

Despite the option name, the present code does not explicitly use $LD$. This name is retained for compatibility and must not be documented as a length-diameter equation.

### 14.4 Envelope-Fraction Model

For

```text
framework_mass_model = "fraction_envelope"
```

$$
\boxed{
m_{\mathrm{frame}}
=
f_{\mathrm{frame}}
S_{\mathrm{outer}}
\sigma_{\mathrm{outer}},
}
\tag{EQ-33}
$$

where

$$
f_{\mathrm{frame}}
=
\begin{cases}
0.20,&\text{semi-rigid},\\
0.35,&\text{rigid}.
\end{cases}
$$

### 14.5 Framework Safeguard

After the candidate framework mass is evaluated, a proxy mass is formed:

$$
\boxed{
m_{\mathrm{proxy}}
=
m_{\mathrm{env}}
+m_{\mathrm{gondola}}
+m_{\mathrm{fin}}
+m_{\mathrm{prop}}
+m_{\mathrm{poMER}}
+m_{\mathrm{tank}}
+m_{\mathrm{crew}}.
}
\tag{EQ-34}
$$

The framework is limited to

$$
\boxed{
m_{\mathrm{frame}}
\le
f_{\mathrm{cap}}m_{\mathrm{proxy}},
}
\tag{EQ-35}
$$

with default

$$
f_{\mathrm{cap}}=0.22.
$$

This cap is an **optimization safeguard**, not a physical structural law.


#### 14.6 Supporting Evidence for the Framework Scaling

The `V^{2/3}` dependence has a classical structural basis. Roxbee Cox's
analysis of rigid-airship structure masss relates structural mass to gross
volume through geometric scaling; for geometrically similar hulls, characteristic
load-bearing and surface quantities scale approximately with $L^2$ while gross
volume scales with $L^3$, giving the familiar $V^{2/3}$ dependence [7].
Accordingly, the **exponent/form** in EQ-31 has literature support.

In contrast, the numerical coefficient `k_framework_v23 = 0.35` is an ADaPT
calibration value and is not independently established by Cox (1929) or by a
single universal airship MER. The same distinction applies to the alternative
framework coefficients and to the 0.22 cap. Historical structural fractions
vary substantially with airship class and mass basis, so such data are useful
as context but should not be used to claim direct validation of the 22%-of-OEM
cap [8].

For the BASI MB-30T validation, use of the linear framework model must therefore be reported as the selected conceptual structural model/sensitivity unless independent structural data justify the 1.5 kg/m coefficient. Improved MTOM agreement alone is not sufficient to establish physical validation of that coefficient.

---

## 15. Conventional Liquid-Fuel Tank Hardware

The optional method

```text
fuel_tank_mass_method = "book"
```

estimates empty conventional liquid-fuel tank hardware.

The fuel mass is first converted to fuel volume:

$$
\boxed{
V_{\mathrm{fuel,gal}}
=
\frac{W_{\mathrm{fuel,lb}}}
{\rho_{\mathrm{fuel,lb/gal}}}.
}
\tag{EQ-36}
$$

The MER is

$$
\boxed{
W_{FT}
=
2.49
V_{\mathrm{fuel,gal}}^{0.6}
N_{\mathrm{tank}}^{0.2}
N_{\mathrm{engine}}^{0.13}
\left[
\frac{1}{1+I_{\mathrm{integral}}}
\right]^{0.3}.
}
\tag{EQ-37}
$$

The result is converted from pounds to kilograms.

This term represents **empty tank hardware** and belongs in OEM. The liquid fuel itself remains `consumable_mass`.

The method can also be set to `override` or `none`.

---

## 16. Landing-System Mass

### 16.1 Conventional Landing Gear

For the Chapter-9 method, takeoff heaviness is represented by

$$
\boxed{
W_{H0}
=
(1-BR_{\mathrm{TO}})W_{\mathrm{TO}}.
}
\tag{EQ-38}
$$

For single conventional gear,

$$
\boxed{
W_{LG}
=
24.2
\left(
\frac{2W_{H0}}{1000}
\right)^{0.84},
}
\tag{EQ-39}
$$

and for tricycle gear,

$$
\boxed{
W_{LG}
=
31.2
\left(
\frac{2W_{H0}}{1000}
\right)^{0.84}.
}
\tag{EQ-40}
$$

The MER is evaluated in pounds and converted to kilograms.

Because

$$
W_{H0}
\propto W_{\mathrm{TO}},
$$

landing-system mass is coupled to MTOM and participates in the fixed-point closure.

The retained simplified option is

$$
\boxed{
m_{LG,\mathrm{simplified}}
=
f_{LG}m_{\mathrm{MTOM}},
}
\tag{EQ-41}
$$

with default $f_{LG}=0.0167$, but this is not the default method.

### 16.2 ACLS

For ACLS,

$$
\boxed{
W_{\mathrm{ACLS}}
=
1.6S_{\mathrm{ACLS}},
}
\tag{EQ-42}
$$

with the coefficient applied in its original imperial basis:

$$
S_{\mathrm{ACLS}}:\ {\rm ft^2},
\qquad
W_{\mathrm{ACLS}}:\ {\rm lb}.
$$

The result is then converted to kilograms. The current implementation therefore avoids treating 1.6 as an SI kg/m² coefficient.


The simplified `landing_gear_fraction = 0.0167` is retained only as a compatibility
option. For comparison, conventional heavier-than-air aircraft landing gear is
often represented by a higher percentage of MTOM, while an airship's landing
system does not normally absorb the full vehicle mass because the hull is
buoyant. Thus the lower magnitude is directionally plausible, but there is no
independent literature basis for treating exactly 1.67% as a universal airship
landing-gear fraction [2,8]. New studies should therefore use the default
book-based method.

---

## 17. Pressure-System Mass

The default is

```text
pressure_system_mass_method = "none"
```

so pressure-system mass is zero unless deliberately enabled.

For

```text
pressure_system_mass_method = "book_fraction"
```

the current conceptual relation is

$$
\boxed{
m_{\mathrm{pressure}}
=
f_{\mathrm{pressure}}
m_{\mathrm{OEM}},
}
\tag{EQ-43}
$$

with default

$$
f_{\mathrm{pressure}}=0.02.
$$

Because this term depends on OEM, it participates in the fixed-point mass closure.

`override` permits a directly specified reference/configuration mass.

The fraction must be treated as configuration-dependent rather than as a universal constant.

---

## 18. Vehicle-Management-System Mass

The default is

```text
vms_mass_method = "none".
```

When the Chapter-11-style fraction is enabled,

$$
\boxed{
m_{\mathrm{VMS}}
=
f_{\mathrm{VMS}}m_{\mathrm{OEM}}
+
m_{\mathrm{tail,actuator}},
}
\tag{EQ-44}
$$

with default

$$
f_{\mathrm{VMS}}=0.03.
$$

The tail actuator is then removed from the tail contribution used in OEM so it appears exactly once.

The `override` mode uses a directly supplied VMS mass.

---

## 19. Miscellaneous Systems

The current relation is

$$
\boxed{
m_{\mathrm{misc}}
=
f_{\mathrm{misc}}m_{\mathrm{OEM}},
}
\tag{EQ-45}
$$

with default

$$
f_{\mathrm{misc}}=0.035.
$$

Because miscellaneous mass depends on OEM, it is solved as part of the coupled fixed-point closure rather than being evaluated once from an arbitrary preliminary subtotal.

The 3.5% default follows the conventional-airship conceptual example basis and remains configuration dependent.


A cross-check against conceptual aircraft/airship mass practice places fixed
equipment and miscellaneous furnishings in the single-digit percentage range
of empty mass. Historical passenger-airship equipment and furnishing masses
are likewise small fractions of total empty mass. The 3.5% value is therefore
reasonable in magnitude, but should remain tied to the conventional-airship
conceptual-example basis rather than being presented as a universal coefficient
[1,11].

---

## 20. Crew Mass

$$
\boxed{
m_{\mathrm{crew}}
=
N_{\mathrm{crew}}
m_{\mathrm{crew,each}}.
}
\tag{EQ-46}
$$

The default is

$$
m_{\mathrm{crew,each}}
=
250\ {\rm lb}
\approx113.4\ {\rm kg},
$$

representing crew plus luggage in the conceptual literature example.

**Classification:** literature-supported conceptual assumption.


As an independent magnitude check, FAA aircraft mass-and-balance guidance and
survey data use adult passenger/crew reference masss of roughly 190--205 lb
depending on the applicable standard. Allowing additional crew kit, headsets,
manuals, and luggage makes `250 lb/person` a conservative conceptual
crew-plus-luggage allowance rather than an unexplained constant [10].

---

## 21. Optional Design Margin

The book discusses conceptual empty-mass design margins in the approximate 5–10% range and uses values around 5–6% in examples.

When

```text
apply_mass_margin = True
```

the current component evaluates

$$
\boxed{
m_{\mathrm{margin}}
=
f_{\mathrm{margin}}m_{\mathrm{OEM}},
}
\tag{EQ-47}
$$

with default

$$
f_{\mathrm{margin}}=0.06.
$$

The margin is included in the same fixed-point closure as other OEM-dependent terms.

The adopted 6% value is directly within the book-supported conceptual
5--10% range and is close to the 5--6% values used in worked examples [1].

The default setting is

```text
apply_mass_margin = False
```

so reference-aircraft validation does not automatically add a margin that may already be embedded in the measured/reference empty mass.

---

## 22. Lifting-Gas Volume Budget

The current lifting-gas volume treatment differs by structural architecture.

### 22.1 Base Lifting Volume

For non-rigid and semi-rigid airships,

$$
\boxed{
V_{\mathrm{lift,base}}=V_{\mathrm{gross}}.
}
\tag{EQ-48}
$$

At maximum pressure altitude, the ballonet is conceptually empty. Therefore **installed ballonet capacity is not subtracted from maximum helium volume**.

For rigid airships,

$$
\boxed{
V_{\mathrm{lift,base}}
=
V_{\mathrm{gas,cells}},
}
\tag{EQ-49}
$$

using `gas_cell_total_volume` supplied by Geometry.

If that input is unavailable/zero, a backward-compatible fallback is

$$
\boxed{
V_{\mathrm{lift,base}}
=
\frac{V_{\mathrm{gross}}}{1.10}.
}
\tag{EQ-50}
$$

### 22.2 Maximum Helium Volume

The raw maximum helium volume is

$$
\boxed{
V_{\mathrm{He,max,raw}}
=
(1-f_s-f_R)V_{\mathrm{lift,base}}
-
k_Gm_{\mathrm{payload}}
-
V_{\mathrm{power}}
-
V_{\mathrm{tank}}.
}
\tag{EQ-51}
$$

where

- $f_s$ is `structure_volumetric_index`,
- $f_R$ is `buoyancy_reserve`,
- $k_G$ is `gondola_volumetric_index`,
- $V_{\mathrm{power}}$ is internal power-system volume,
- $V_{\mathrm{tank}}$ is installed hydrogen-storage volume.

Current defaults are

$$
f_s=0,
\qquad
f_R=0,
\qquad
k_G=0.
$$

Thus no hidden internal-volume penalty is imposed by default.

The gondola term is retained only as a simplified/internal-gondola displacement proxy; conventional external gondolas should normally leave it at zero.

---

## 23. Internal-Volume Feasibility

If the required internal volume exceeds the available lifting volume,

$$
V_{\mathrm{He,max,raw}}<0.
$$

The component reports

$$
\boxed{
V_{\mathrm{violation}}
=
\max(-V_{\mathrm{He,max,raw}},0).
}
\tag{EQ-52}
$$

Thus

$$
V_{\mathrm{violation}}=0
$$

is feasible, whereas

$$
V_{\mathrm{violation}}>0
$$

indicates an internal-volume violation.

For numerical gas-property evaluation only,

$$
\boxed{
V_{\mathrm{He,max}}
=
\max
\left(
V_{\mathrm{He,max,raw}},
V_{\mathrm{He,min}}
\right),
}
\tag{EQ-53}
$$

with

$$
V_{\mathrm{He,min}}=10^{-6}\ {\rm m^3}.
$$

This floor does not hide physical infeasibility because the violation is reported separately.

---

## 24. Helium State at Maximum Altitude

The common operating-condition/property object supplies atmospheric pressure and temperature at

$$
h_{\max}
$$

and the average mission DISA value.

Therefore,

$$
P_{\max},T_{\max}
=
\mathrm{Atmosphere}
(h_{\max},\Delta T).
$$

Helium density is obtained from the shared gas-property model:

$$
\boxed{
\rho_{\mathrm{He,max}}
=
\rho_{\mathrm{He}}
(P_{\max},T_{\max}).
}
\tag{EQ-54}
$$

Conceptually, for an ideal gas,

$$
\rho_{\mathrm{He}}
=
\frac{P}{R_{\mathrm{He}}T},
$$

but the authoritative thermodynamic implementation resides in the common property model rather than being duplicated inside `Airshipmass`.

The maximum helium mass is

$$
\boxed{
m_{\mathrm{He}}
=
f_{\mathrm{He,cal}}
V_{\mathrm{He,max}}
\rho_{\mathrm{He,max}},
}
\tag{EQ-55}
$$

with default

$$
f_{\mathrm{He,cal}}=1.
$$

The optional calibration factor should only be changed deliberately and documented as calibration.

Again, Eq. (EQ-55) is a gas-state diagnostic and does not add helium to OEM or MTOM.

---

## 25. Sea-Level Helium Volume and Available Air Volume

The same conserved helium mass is evaluated at sea-level atmospheric conditions.

Let

$$
\rho_{\mathrm{He,SL}}
=
\rho_{\mathrm{He}}
(P_{SL},T_{SL}).
$$

The corresponding minimum helium volume is

$$
\boxed{
V_{\mathrm{He,min,SL}}
=
\frac{
m_{\mathrm{He}}
}{
f_{\mathrm{He,cal}}
\rho_{\mathrm{He,SL}}
}.
}
\tag{EQ-56}
$$

The available air-volume capacity is

$$
\boxed{
V_{\mathrm{air,max}}
=
\max
\left(
V_{\mathrm{lift,base}}
-
V_{\mathrm{He,min,SL}},
0
\right).
}
\tag{EQ-57}
$$

This provides a lifting-gas expansion/contraction diagnostic between sea level and the maximum-pressure-altitude state.

---

## 26. Coupled OEM/MTOM Closure

Several current mass terms depend on OEM or MTOM:

- conventional landing gear depends on takeoff heaviness and MTOM,
- pressure-system fraction depends on OEM when enabled,
- VMS fraction depends on OEM when enabled,
- miscellaneous mass depends on OEM,
- design margin depends on OEM when enabled.

The component therefore performs an internal fixed-point iteration.

### 26.1 Base Independent Mass

Before fractional/closure-dependent terms,

$$
\boxed{
\begin{aligned}
m_{\mathrm{base}}={}&
m_{\mathrm{env}}
+m_{\mathrm{ballonet}}
+m_{\mathrm{curtain}}
+m_{\mathrm{frame}}
+m_{\mathrm{gondola}}
+m_{\mathrm{tail,OEM}}\\
&+m_{\mathrm{prop}}
+m_{\mathrm{power}}
+m_{\mathrm{H_2,tank}}
+m_{\mathrm{fuel,tank}}
+m_{\mathrm{crew}}.
\end{aligned}
}
\tag{EQ-58}
$$

### 26.2 Iteration

An initial estimate is

$$
m_{\mathrm{OEM}}^{(0)}
=
m_{\mathrm{base}},
$$

$$
m_{\mathrm{MTOM}}^{(0)}
=
m_{\mathrm{OEM}}^{(0)}
+m_{\mathrm{payload}}
+m_{\mathrm{consumable}}
+m_{\mathrm{ballast}}.
$$

At iteration $k$, the closure-dependent masses are recalculated:

$$
m_{\mathrm{landing}}^{(k)}
=
f_{\mathrm{landing}}
(m_{\mathrm{MTOM}}^{(k)}),
$$

$$
m_{\mathrm{pressure}}^{(k)}
=
f_{\mathrm{pressure}}
(m_{\mathrm{OEM}}^{(k)}),
$$

$$
m_{\mathrm{VMS}}^{(k)}
=
f_{\mathrm{VMS}}
(m_{\mathrm{OEM}}^{(k)}),
$$

$$
m_{\mathrm{misc}}^{(k)}
=
f_{\mathrm{misc}}
m_{\mathrm{OEM}}^{(k)},
$$

and, when enabled,

$$
m_{\mathrm{margin}}^{(k)}
=
f_{\mathrm{margin}}
m_{\mathrm{OEM}}^{(k)}.
$$

The updated OEM is

$$
\boxed{
m_{\mathrm{OEM}}^{(k+1)}
=
m_{\mathrm{base}}
+
m_{\mathrm{landing}}^{(k)}
+
m_{\mathrm{pressure}}^{(k)}
+
m_{\mathrm{VMS}}^{(k)}
+
m_{\mathrm{misc}}^{(k)}
+
m_{\mathrm{margin}}^{(k)}.
}
\tag{EQ-59}
$$

Then

$$
\boxed{
m_{\mathrm{MTOM}}^{(k+1)}
=
m_{\mathrm{OEM}}^{(k+1)}
+
m_{\mathrm{payload}}
+
m_{\mathrm{consumable}}
+
m_{\mathrm{ballast}}.
}
\tag{EQ-60}
$$

### 26.3 Convergence Criterion

The normalized iteration error is

$$
\boxed{
\epsilon
=
\frac{
\max
\left(
|m_{\mathrm{OEM}}^{(k+1)}-m_{\mathrm{OEM}}^{(k)}|,
|m_{\mathrm{MTOM}}^{(k+1)}-m_{\mathrm{MTOM}}^{(k)}|
\right)
}{
\max
\left(
|m_{\mathrm{OEM}}|,
|m_{\mathrm{MTOM}}|,
1
\right)
}.
}
\tag{EQ-61}
$$

The defaults are

$$
\epsilon_{\mathrm{tol}}=10^{-8},
\qquad
N_{\max}=100.
$$

This internal iteration is separate from the higher-level multidisciplinary OpenMDAO solver that closes geometry, performance, propulsion, energy, and mass.

---

## 27. Diagnostic Mass Aggregates

### 27.1 Installed-System Mass

The current diagnostic is

$$
\boxed{
\begin{aligned}
m_{\mathrm{installed}}
={}&
m_{\mathrm{prop}}
+m_{\mathrm{power}}
+m_{\mathrm{H_2,tank}}
+m_{\mathrm{fuel,tank}}\\
&+m_{\mathrm{pressure}}
+m_{\mathrm{VMS}}.
\end{aligned}
}
\tag{EQ-62}
$$

### 27.2 Structure Mass

The current `structure_mass` diagnostic is

$$
\boxed{
\begin{aligned}
m_{\mathrm{structure}}
={}&
m_{\mathrm{env}}
+m_{\mathrm{ballonet}}
+m_{\mathrm{curtain}}
+m_{\mathrm{frame}}
+m_{\mathrm{gondola}}\\
&+m_{\mathrm{tail,OEM}}
+m_{\mathrm{landing}}.
\end{aligned}
}
\tag{EQ-63}
$$

Unlike the previous documentation, this output **does not include helium or miscellaneous mass**.

When VMS owns the tail actuator, `structure_mass` uses the same actuator-free tail contribution as OEM. This avoids overlap if structural and installed-system diagnostics are later combined.

### 27.3 Useful Load Diagnostic

The retained diagnostic is

$$
\boxed{
m_{\mathrm{useful}}
=
m_{\mathrm{payload}}
+
m_{\mathrm{crew}}.
}
\tag{EQ-64}
$$

This is a software diagnostic definition and should not automatically be equated with every manufacturer's published “useful load,” whose definition may include fuel and other items.

### 27.4 Installed Consumable

$$
\boxed{
m_{\mathrm{installed,consumable}}
=
m_{\mathrm{consumable}}.
}
\tag{EQ-65}
$$

---

## 28. Mass-Balance Diagnostic

The component independently forms

$$
\boxed{
m_{\mathrm{explicit}}
=
m_{\mathrm{OEM}}
+
m_{\mathrm{payload}}
+
m_{\mathrm{consumable}}
+
m_{\mathrm{ballast}}.
}
\tag{EQ-66}
$$

The reported mass-balance error is

$$
\boxed{
e_m
=
m_{\mathrm{MTOM}}
-
m_{\mathrm{explicit}}.
}
\tag{EQ-67}
$$

A correctly converged calculation should satisfy

$$
e_m\approx0.
$$

This diagnostic checks bookkeeping closure; it does not prove that the individual empirical mass models are physically accurate.

---

## 29. Model Outputs

### 29.1 Principal Vehicle Outputs

| Output | Units | Meaning |
|---|---:|---|
| `owe` | kg | Closed operating empty mass |
| `unmargined_owe` | kg | OEM before optional design margin |
| `MTOM` | kg | Closed maximum takeoff mass |
| `operational_mass` | kg | OEM + payload |
| `mass_balance_error` | kg | Explicit bookkeeping residual |

### 29.2 Structural and Airframe Outputs

| Output | Units | Meaning |
|---|---:|---|
| `envelope_mass` | kg | Envelope mass |
| `envelop_mass` | kg | simplified alias |
| `ballonet_mass` | kg | Ballonet fabric mass |
| `curtain_mass` | kg | Suspension-curtain mass |
| `curtain_area` | m² | Curtain area |
| `framework_mass` | kg | Semi-rigid/rigid framework mass |
| `gondola_mass` | kg | Gondola mass |
| `fin_mass` | kg | Complete physical tail mass |
| `tail_fixed_mass` | kg | Fixed tail |
| `tail_control_surface_mass` | kg | Movable tail surfaces |
| `tail_actuator_mass` | kg | Tail actuator |
| `landing_system_mass` | kg | Conventional gear or ACLS |
| `structure_mass` | kg | Non-overlapping structural/airframe diagnostic |

### 29.3 Installed-System Outputs

| Output | Units | Meaning |
|---|---:|---|
| `fuel_tank_mass` | kg | Conventional liquid-fuel tank hardware |
| `pressure_system_mass` | kg | Pressure system |
| `vms_mass` | kg | Vehicle-management system |
| `miscellaneous_mass` | kg | Miscellaneous systems |
| `mass_margin_mass` | kg | Optional design margin |
| `installed_system_mass` | kg | Installed-system aggregate diagnostic |

### 29.4 Tail MER Diagnostics

| Output | Units | Meaning |
|---|---:|---|
| `tail_fpsq_used` | lb/ft² | Tail structural coefficient actually used |
| `tail_fact_used` | lb/ft² | Tail actuator coefficient actually used |

### 29.5 Lifting-Gas and Volume Outputs

| Output | Units | Meaning |
|---|---:|---|
| `he_max_volume` | m³ | Maximum lifting-gas volume |
| `he_max_mass` | kg | Helium mass diagnostic |
| `air_max_volume` | m³ | Available air-volume diagnostic |
| `envelope_volume_violation` | m³ | Positive internal-volume infeasibility |

### 29.6 Load Diagnostics

| Output | Units | Meaning |
|---|---:|---|
| `crew_mass` | kg | Crew + luggage |
| `useful_load_mass` | kg | Payload + crew software diagnostic |
| `installed_consumable_mass` | kg | Installed fuel/hydrogen mass |

---

## 30. Multidisciplinary Coupling

The mass model is central to the ADaPT closed-loop design problem.

A simplified coupling is

$$
\boxed{
\begin{array}{c}
L,\ D,\ V,\ S_{\mathrm{wet}},\ S_T,\ V_B,\ \text{structure}\\
\downarrow\\
m_{\mathrm{airframe}},\ V_{\mathrm{He}}\\
\downarrow\\
m_{\mathrm{OEM}},\ m_{\mathrm{MTOM}}\\
\downarrow\\
\text{buoyancy requirement,\ drag,\ takeoff heaviness}\\
\downarrow\\
P_{\mathrm{required}},\ E_{\mathrm{mission}}\\
\downarrow\\
m_{\mathrm{prop}},\ m_{\mathrm{power}},\ m_{\mathrm{tank}},\ m_{\mathrm{consumable}}\\
\downarrow\\
m_{\mathrm{OEM}},\ m_{\mathrm{MTOM}}
\end{array}}
$$

Important coupling variables include:

- `gross_volume`: geometry → mass and aerostatics,
- `aerodynamic_reference_area`: geometry → envelope mass,
- tail planform areas: geometry → tail mass,
- `framework_total_member_length`: geometry → semi/rigid framework mass,
- `gas_cell_total_volume`: rigid geometry → lifting-gas volume,
- `propulsion_mass`: propulsion → mass,
- `power_system_mass` and volume: power system → mass and lifting-volume budget,
- `tank_mass` and volume: hydrogen storage → mass and lifting-volume budget,
- `consumable_mass`: mission/performance → MTOM,
- `MTOM`: mass → performance/aerostatics and, through landing-gear MER, back to mass.

The mass component therefore participates in both an **internal mass closure** and the larger **multidisciplinary vehicle closure**.

---

## 31. Assumptions and Limitations

| Item | Current treatment | Status |
|---|---|---|
| Non-rigid envelope | Chapter-8 MER | Literature based |
| Raw envelope density | Baseline value chosen to preserve 0.383 kg/m² installed effective density | Calibration/assumption |
| Ballonet geometry | Two equal spheres | Conceptual initial-sizing assumption |
| Ballonet mass factor | 1.13 | Literature MER |
| Curtain area | 20% of side projection | Literature conceptual relation |
| Curtain material density | 0.028 lb/ft² | Worked-example/baseline material |
| Tail model | Chapter-9 lightmass MER | Literature based |
| Intermediate tail coefficients | Linear interpolation between book endpoints | ADaPT adaptation |
| Gondola | Chapter-9 category MERs | Literature based |
| Category-3 missing area | Rectangular six-side fallback | Geometric approximation |
| Semi/rigid envelope densities | Fixed defaults | Conceptual/calibration |
| Framework | Four selectable proxies | Conceptual/calibration |
| Framework cap | 22% of proxy mass | Numerical/DSE safeguard |
| Conventional fuel tank | Chapter-9/11 MER when enabled | Literature based |
| Pressure system | Optional OEM fraction | Configuration-dependent conceptual model |
| VMS | Optional OEM fraction + actuator | Configuration-dependent conceptual model |
| Miscellaneous | 3.5% of OEM | Literature-supported conceptual default |
| Design margin | Optional 6% of OEM | Conceptual design allowance |
| Helium | Calculated but excluded from OEM/MTOM | Bookkeeping convention |
| Ballonet at max altitude | Conceptually empty | Preliminary pressure-airship assumption |
| Structural volume index | Default zero | Optional modeling assumption |
| Buoyancy reserve | Default zero | Optional modeling assumption |
| Gondola volume penalty | Default zero | simplified/internal-gondola option |
| Rigid gas volume | Geometry gas-cell volume; fallback $V/1.10$ | Coupled model + compatibility fallback |
| Internal closure | Fixed-point iteration | Numerical method |
| Detailed stress/buckling | Not modeled | Limitation |
| Detailed manufacturing joints | Not modeled except empirical factors | Limitation |
| Certification mass accounting | Not modeled | Limitation |


### 31.1 Evidence for Non-Book Defaults

The non-book numerical defaults are not all supported in the same way. The
following distinction should be retained in interpretation:

- `envelope_fabric_areal_density`: calibration value, with an independent
  literature range of approximately 100--480 g/m² for relevant structural
  airship laminate classes [2--6].
- `curtain_fabric_density`: calibration/baseline material value, with
  approximately 100--230 g/m² structural fabric data providing an independent
  magnitude check [2--6].
- `outer_envelope_areal_density` and `inner_envelope_areal_density`:
  conceptual assumptions anchored to historical rigid-airship cover and
  gas-cell material ranges [9].
- `k_framework_v23`: calibration coefficient; the `V^{2/3}` form itself has
  classical literature support, but the coefficient does not [7].
- `framework_mass_frac_cap`: numerical DSE safeguard, not a physical
  literature target.
- `landing_gear_fraction`: simplified calibration/compatibility value only; its
  lower-than-aircraft magnitude is plausible, but 1.67% is not a universal
  literature coefficient [2,8].
- `crew_mass_each`: literature-anchored conceptual allowance based on FAA
  standard masss plus crew kit/luggage [10].
- `miscellaneous_fraction`: literature-supported conceptual default based on
  the conventional-airship example and consistent single-digit fixed-equipment
  fractions [1,11].

Accordingly, validation should demonstrate the performance of the **complete
mass model under its stated assumptions**, rather than implying that every
individual non-book coefficient has been independently measured.

---

## 32. Provenance Classification

The documentation uses:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical/geometric relationship |
| **L** | Literature relationship |
| **A** | Adapted literature relationship |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **N** | Numerical safeguard |
| **D** | Derived/bookkeeping relationship |
| **C** | Calibration/reference parameter |

Principal equations are classified as:

| Equation | Relationship | Classification |
|---|---|---|
| EQ-1–2 | Helium excluded from OEM/MTOM | D / bookkeeping |
| EQ-3–6 | Vehicle mass definitions | D |
| EQ-8 | Non-rigid envelope MER | L / E |
| EQ-9 | simplified envelope model | C |
| EQ-10 | Semi/rigid envelope buildup | AS / C |
| EQ-11–14 | Ballonet mass | L / A |
| EQ-15–17 | Suspension curtain | L / A |
| EQ-18–20 | Tail coefficient interpolation | L endpoints / A interpolation |
| EQ-21–24 | Tail mass and ownership | L / D |
| EQ-25 | simplified tail model | C |
| EQ-26–28 | Gondola MERs | L / E |
| EQ-29 | Gondola area fallback | D / AS |
| EQ-30–35 | Framework models and cap | AS / C / N |
| EQ-36–37 | Conventional fuel-tank MER | L / E |
| EQ-38–40 | Conventional landing MER | L / E |
| EQ-41 | simplified landing fraction | C |
| EQ-42 | ACLS MER | L / E |
| EQ-43 | Pressure system | AS / L-adapted |
| EQ-44 | VMS | AS / L-adapted |
| EQ-45 | Miscellaneous | L / AS |
| EQ-46 | Crew | L / AS |
| EQ-47 | Design margin | L / AS |
| EQ-48–51 | Lifting-volume budget | D / AS |
| EQ-52–53 | Volume violation/floor | D / N |
| EQ-54–57 | Helium gas-state diagnostics | F / D |
| EQ-58–61 | Fixed-point mass closure | D / N |
| EQ-62–67 | Diagnostic aggregates and balance | D |

---

## 33. Numerical Implementation

### 33.1 Internal Fixed-Point Closure

The component uses a maximum of

$$
N_{\max}=100
$$

mass-closure iterations with default normalized tolerance

$$
10^{-8}.
$$

This closure is required because the default miscellaneous relation and optional pressure/VMS/margin relations depend on OEM, while conventional landing mass depends on MTOM.

### 33.2 OpenMDAO Derivatives

The component currently declares finite-difference partial derivatives:

```python
self.declare_partials("*", "*", method="fd", step=1.0e-8)
```

with perturbation

$$
\Delta x=10^{-8}.
$$

This is a numerical implementation choice, not part of the physical model.

### 33.3 Piecewise/Nonsmooth Behavior

Several model choices introduce piecewise behavior:

- structural architecture branches,
- power-source/tank branches,
- tail coefficient endpoint/interpolation regions,
- framework-model selection,
- framework cap,
- gondola category/method,
- landing-system method,
- pressure/VMS method,
- optional margin,
- numerical `max`/`clip` guards.

These should be considered when using high-order gradient-based optimization.

---

## 34. Verification Strategy

### 34.1 Equation-Level Verification

Independently verify:

1. non-rigid envelope mass from raw fabric density and $F_{MA},F_{AF}$,
2. simplified envelope recovery,
3. two-sphere ballonet area and mass,
4. suspension-curtain projected area and mass,
5. tail endpoint coefficients at $q=1$ and $10$ psf,
6. tail interpolation inside that range,
7. tail fixed/control/actuator bookkeeping,
8. gondola Categories 1–3,
9. rectangular gondola-area fallback,
10. each framework model,
11. framework cap,
12. conventional fuel-tank MER,
13. single/tricycle landing MER,
14. ACLS imperial-unit conversion,
15. pressure and VMS fractions,
16. miscellaneous and design-margin closure,
17. helium volume at maximum altitude,
18. rigid gas-cell volume coupling,
19. internal-volume violation,
20. sea-level helium-volume calculation,
21. OEM/MTOM fixed-point convergence, and
22. mass-balance residual.

### 34.2 Architecture Tests

Test at least:

- non-rigid + conventional fuel,
- non-rigid + battery,
- semi-rigid configuration,
- rigid configuration,
- hydrogen tank-using architecture,
- turboprop/turboelectric externally owned system masses,
- conventional landing gear,
- ACLS,
- pressure/VMS disabled,
- pressure/VMS enabled,
- design margin disabled/enabled.

### 34.3 Book Conceptual-Design Verification

The strongest literature-level integrated verification is reproduction of the relevant Chapter-11 conceptual airship mass buildup using the book's own design inputs and definitions.

This verifies the implementation of the MER chain before comparison with real aircraft.

---

## 35. Reference-Airship Validation

Real-aircraft validation must distinguish **prescribed inputs** from **independently predicted quantities**.

A recommended validation table should identify each quantity as one of:

1. prescribed reference input,
2. independently predicted output,
3. derived reference quantity,
4. architecture/configuration assumption,
5. feasibility/constraint diagnostic.

A zero-percent error in a prescribed fuel capacity, installed poMER, length, or payload is not an independent predictive validation result.

### 35.1 Non-Rigid Reference Cases

For non-rigid vehicles, validation should focus on:

- envelope mass where available,
- ballonet mass/capacity where available,
- gondola mass,
- tail mass,
- propulsion/power ownership,
- OEM or a clearly defined reference base mass,
- MTOM,
- mass closure.

### 35.2 Semi-Rigid and Rigid Reference Cases

For semi-rigid and rigid airships, special care is required because the framework model is conceptual.

If a framework coefficient is selected because it improves agreement with a known aircraft, it must be labeled calibration.

For example, in the BASI MB-30T case, the current linear model

$$
m_{\mathrm{frame}}
=
1.5L_{\mathrm{members}}
$$

produces a plausible integrated mass closure, but the 1.5 kg/m coefficient is not thereby independently validated. Until structural data support that value, the result should be reported as a selected conceptual framework model or structural-model sensitivity.

### 35.3 Helium Reporting

Reference validation tables may report

$$
m_{\mathrm{He}}
$$

as a gas-state diagnostic, but it must not be added to the ADaPT OEM/MTOM closure unless a different explicitly defined mass convention is adopted consistently throughout aerostatics and performance.

---

## 36. Interpretation of Current BASI MB-30T Mass Validation

The latest rigid-airship validation illustrates the intended interpretation of the model.

The predicted mass closure is approximately:

$$
m_{\mathrm{OEM}}\approx30.67\ {\rm t}
$$

against a 32.0 t reference closure mass, and

$$
m_{\mathrm{MTOM}}\approx60.67\ {\rm t}
$$

against 62.0 t.

This corresponds to approximately

$$
-4.17\%
$$

OEM/base-mass error and

$$
-2.15\%
$$

MTOM error.

These results indicate good **integrated mass closure**, but they do not independently validate each unpublished component mass. In particular, the framework contribution remains dependent on the selected conceptual framework model.

The approximately 8.26 t helium mass calculated in that case is correctly reported separately and is not added to OEM or MTOM.

The power and fuel feasibility failures observed in the same BASI run are not mass-bookkeeping failures. They arise from the performance/propulsion/mission capacity comparison and should be documented in the corresponding performance and architecture validation sections.

---

## 37. Recommended Reporting Terminology

To prevent ambiguity, use the following terms consistently:

- **OEM** — ADaPT closed operating empty mass under the adopted bookkeeping convention.
- **Reference closure mass** — a derived or supplied comparison mass when the source does not unambiguously define OEM.
- **MTOM** — OEM + payload + installed consumable + ballast.
- **Helium mass** — lifting-gas state diagnostic, excluded from OEM/MTOM.
- **Installed system mass** — propulsion + power + tank hardware + fuel-tank hardware + pressure system + VMS.
- **Structure mass** — non-overlapping airframe/structural diagnostic defined by Eq. (EQ-63).
- **Consumable mass** — mission fuel or hydrogen carried at takeoff.
- **Fuel-tank mass** — empty conventional liquid-fuel tank hardware.
- **Framework mass** — semi-rigid/rigid conceptual structural estimate.
- **Prescribed quantity** — reference value imposed on the model, not independently predicted.
- **Predicted quantity** — output calculated without prescribing the same reference value.
- **Calibration parameter** — parameter deliberately adjusted against reference data.
- **Numerical safeguard** — implementation protection that is not a physical law.

---

## 38. Software Traceability Summary

| Theory/model item | Current implementation |
|---|---|
| Non-rigid envelope | `aerodynamic_reference_area * envelope_fabric_areal_density * envelope_manufacturing_factor * envelope_attachment_factor` |
| simplified envelope | `aerodynamic_reference_area * envelope_areal_density_nonrigid` |
| Semi/rigid envelope | `outer_area*outer_density + inner_area*inner_density` |
| Ballonet | two equal spheres; 0.035 lb/ft² × area × 1.13 |
| Curtain | 0.20 × elliptical side projection × material density × 1.06 |
| Tail | Chapter-9 lightmass fixed/control/actuator buildup |
| Tail interpolation | linear between 1 and 10 psf endpoints |
| Gondola | Chapter-9 Categories 1–3 |
| Framework linear | `member_length * frame_linear_density` |
| Framework v23 | `k_framework_v23 * gross_volume**(2/3)` |
| Framework ld | `k_framework_ld * gross_volume**(2/3)` |
| Framework fraction | 0.20 semi-rigid / 0.35 rigid × outer-envelope mass |
| Framework cap | 0.22 × proxy mass by default |
| Conventional fuel tank | Chapter-9/11 MER from fuel gallons, tank count, engine count, integral flag |
| Conventional gear | Chapter-9 takeoff-heaviness MER |
| ACLS | 1.6 lb/ft² × ACLS area in ft² |
| Pressure system | optional fraction of OEM or override |
| VMS | optional fraction of OEM + actuator or override |
| Miscellaneous | 0.035 × OEM |
| Crew | number × 250 lb |
| Margin | optional 0.06 × OEM |
| Non-rigid/semi lifting volume | gross hull volume at maximum pressure altitude |
| Rigid lifting volume | geometry `gas_cell_total_volume` |
| Helium volume penalties | optional structure/reserve/gondola + power/tank volumes |
| Helium mass | gas density at max altitude × max helium volume |
| Helium in OEM/MTOM | excluded |
| Closure | fixed-point OEM/MTOM iteration |
| Derivatives | finite difference, step $10^{-8}$ |

---

## 39. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.
[2] H. Roxbee Cox, “Structure masss of Rigid Airships: An Elementary Consideration of the Variations of Structure mass with Gross Volume,” *Aircraft Engineering and Aerospace Technology*, 1929.
[3] US Patent 6,914,021, “Flexible wall material for use in an inflatable structure.”
[4] “Study of the Mechanical Properties of Near-Space Airship Envelope Material Based on an Optimization Method,” *Aerospace* (MDPI), 2022.
[5] “Development of High Specific Strength Envelope Materials,” ResearchGate.
[6] “Material Challenges for Lighter-Than-Air Systems in High Altitude Applications,” ResearchGate.
[7] Cox, H. Roxbee, “Structure masss of Rigid Airships,” *Aircraft Engineering and Aerospace Technology*, 1929. The source is used specifically for the classical $V^{2/3}$ structural scaling form.
[8] Barkley, R. L. & Buckley, F. D., “Carrier Crisis,” *Proceedings*, March 1943. Used only as historical context for the configuration sensitivity of airship structural fractions.
[9] Historical accounts of Hindenburg, Graf Zeppelin, and USS Akron construction, including outer-cover, gas-cell, and framework materials.
[10] FAA Advisory Circulars 120-27E (2005) and 120-27F (2019), *Aircraft mass and Balance Control*; FAA AWBCPARC survey memorandum, 7/7/2003.

---

