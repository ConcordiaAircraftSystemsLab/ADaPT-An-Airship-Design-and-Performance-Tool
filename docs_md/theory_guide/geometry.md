# Geometry

The geometry model defines the principal external and internal dimensions of the airship and provides the geometric quantities required by the aerodynamic, aerostatic, mass, propulsion, energy, and mission models.

Within the validated baseline implementation, the external envelope is represented as a **single-lobed prolate-spheroid-based hull** defined primarily by overall length $L$, fineness ratio $FR$, and an optional hull-volume shape factor $k_V$. From these quantities, the model evaluates maximum diameter, gross hull volume, wetted surface area, the airship aerodynamic reference area $V^{2/3}$, body aspect ratio, initial tail geometry, and—where applicable—ballonet capacity and takeoff lifting-gas volume. Additional conceptual structural quantities are generated for semi-rigid and rigid configurations.

The geometry model is implemented by the OpenMDAO component

```python
AirshipGeometry(om.ExplicitComponent)
```

and acts as one of the foundational components of the ADaPT multidisciplinary sizing framework.

Airship geometry is especially important because hull volume directly determines aerostatic capability, while hull dimensions and surface area affect aerodynamic drag and structural mass. Carichner and Nicolai identify body volume as a principal airship design parameter and describe fineness ratio as an important trade between aerostatic and aerodynamic requirements [1].

---

## 1. Model Scope

The principal baseline dependency is

$$
L,\;FR,\;k_V
\rightarrow
D_{\max},\;V,\;S_{\mathrm{wet}},\;V^{2/3},\;AR_b .
$$

Tail sizing adds

$$
V,\;L,\;\text{tail-sizing method}
\rightarrow
C_{HT,\mathrm{used}},\;C_{VT,\mathrm{used}}
\rightarrow
S_{HT},\;S_{VT}
\rightarrow
S_{\mathrm{fin,wet}}.
$$

For pressure-stabilized non-rigid and semi-rigid configurations,

$$
V,\;\rho_{SL},\;\rho_{\max}
\rightarrow
V_{\mathrm{ballonet}},
$$

or a known installed ballonet fraction may be prescribed for reference-airship validation.

The takeoff/reference gas state is then determined separately from installed ballonet capacity:

$$
V_{\mathrm{ballonet}},\;f_{B,\mathrm{TO}}
\rightarrow
V_{B,\mathrm{TO}}
\rightarrow
V_{g,\mathrm{TO}}.
$$

For semi-rigid and rigid vehicles, additional conceptual quantities are generated for:

- outer-envelope area,
- internal fabric/membrane area,
- primary framework member length, and
- rigid-airship gas-cell partitioning.

The component is intended for **conceptual multidisciplinary design, sizing, optimization, and reference-airship validation**. It is not a detailed CAD, structural-layout, manufacturing, or certification model.

---

## 2. Model Inputs and Options

A distinction is required between **OpenMDAO inputs**, which participate directly in the multidisciplinary data flow, and **component options**, which select model formulations or configuration settings. An OpenMDAO input is not necessarily an overall framework input: for example, `length` may be prescribed during reference-airship validation but treated as a design variable in clean-sheet sizing.

### 2.1 Core OpenMDAO Inputs

| Input | Symbol | Default | Units | Description | Provenance status |
|---|---:|---:|---:|---|---|
| `length` | $L$ | 53.6 | m | Overall hull length | Configuration/design variable |
| `fineness_ratio` | $FR$ | 4.09 | – | Hull length-to-maximum-diameter ratio | Configuration/design variable |
| `tail_volume_coeff_horizontal` | $C_{HT}$ | 0.066 | – | User-supplied horizontal-tail volume coefficient | Empirical/reference input |
| `tail_volume_coeff_vertical` | $C_{VT}$ | 0.059 | – | User-supplied vertical-tail volume coefficient | Empirical/reference input |
| `ballonet_fraction_prescribed` | $f_{B,\mathrm{pres}}$ | 0.08 | – | Known installed ballonet fraction used in prescribed-fraction mode | Reference/calibration input |
| `hull_volume_shape_factor` | $k_V$ | 1.0 | – | Correction from ideal prolate-spheroid volume to actual single-lobed hull volume | Configuration/reference parameter |
| `ballonet_fill_fraction_takeoff` | $f_{B,\mathrm{TO}}$ | 0.0 | – | Fraction of installed ballonet capacity occupied by air at the takeoff/reference condition | Operating-state input |
| `rho_sea_level` | $\rho_{SL}$ | 1.225 | kg/m³ | Air density at the low-altitude reference condition | Atmosphere coupling input |
| `rho_max_altitude` | $\rho_{\max}$ | 0.909 | kg/m³ | Air density at maximum pressure altitude | Atmosphere coupling input |

For semi-rigid and rigid configurations:

| Input | Symbol | Default | Units | Description |
|---|---:|---:|---:|---|
| `n_longitudinal_members` | $N_{\mathrm{long}}$ | 12 | – | Number of additional primary longitudinal members; the single central/keel member is represented separately |
| `n_rings` | $N_{\mathrm{rings}}$ | 16 | – | Number of circumferential frames/rings |

For rigid configurations:

| Input | Symbol | Default | Units | Description |
|---|---:|---:|---:|---|
| `n_gas_cells` | $N_{\mathrm{cells}}$ | 12 | – | Conceptual number of lifting-gas cells |

The numerical defaults are implementation defaults and must not be interpreted as universal airship constants.

### 2.2 Component Options

| Option | Default | Description | Classification |
|---|---:|---|---|
| `max_altitude` | 3048 m | Maximum-pressure-altitude configuration retained for group compatibility; density is supplied through the shared atmosphere model | Configuration option |
| `landing_system` | `conventional` | Conventional landing gear or ACLS selection retained for group compatibility; not used directly by geometry | Compatibility option |
| `airship_type` | `non-rigid` | Selects non-rigid, semi-rigid, or rigid structural arrangement | Architecture option |
| `tail_arm_fraction` | 0.38 | Tail moment arm as a fraction of hull length | Literature-supported conceptual assumption |
| `tail_wetted_area_factor` | 2.2 | Conversion from total projected tail area to conceptual total tail wetted area | Literature-supported empirical relation |
| `tail_coefficient_method` | `user` | `user` uses supplied $C_{HT},C_{VT}$; `historical` evaluates Chapter-7 volume-based correlations | Model-selection option |
| `ballonet_sizing_method` | `pressure_altitude` | Selects pressure-altitude or prescribed-fraction ballonet sizing | Model-selection option |
| `ballonet_sizing_factor` | 1.0 | Optional multiplicative allowance on pressure-altitude ballonet sizing | Sensitivity/calibration parameter |
| `max_ballonet_fraction` | 0.80 | Diagnostic upper design limit; calculated pressure-altitude result is not silently clipped | Design-limit diagnostic |
| `internal_fabric_area_factor` | 0.25 | Internal fabric/membrane area as a fraction of external wetted area | Conceptual assumption |
| `inner_envelope_area_factor` | `None` | simplified alias; if supplied, overrides `internal_fabric_area_factor` | Backward compatibility |
| `framework_enabled` | `True` | Enables conceptual primary-framework member-length calculation | Configuration option |
| `rigid_hull_to_gas_volume_ratio` | 1.10 | Gross rigid-hull volume divided by usable lifting-gas-cell volume | Conceptual historical approximation |
| `minimum_length` | 10 m | Lower design bound used for violation reporting | Design-bound diagnostic |
| `minimum_fineness_ratio` | 2.0 | Lower fineness-ratio bound used for violation reporting | Design-bound diagnostic |

The default maximum altitude of 3048 m is approximately 10,000 ft. It is a model default, not a physical or certification limit.

---

## 3. Baseline Hull Representation

### 3.1 Prolate-Spheroid Basis

The baseline external hull uses a prolate spheroid as its analytical geometric basis. The longitudinal and transverse semi-axes are

$$
a=\frac{L}{2},
\qquad
b=\frac{D_{\max}}{2}.
$$

This body-of-revolution approximation is appropriate for conceptual airship sizing. Carichner and Nicolai use prolate-spheroid and related body-of-revolution representations throughout preliminary airship design [1].

The implementation also permits a dimensionless hull-volume shape factor $k_V$ so that a known single-lobed reference hull can retain its prescribed length and fineness ratio while reproducing a non-ideal-spheroid gross volume. The wetted-area calculation remains the analytical spheroid surface corresponding to $L$ and $D_{\max}$; therefore $k_V$ is specifically a **volume correction**, not a full higher-fidelity shape reconstruction.

**Classification:** fundamental analytical geometry with literature-supported conceptual application; $k_V$ is a configuration/reference correction.

---

## 4. Fineness Ratio and Maximum Diameter

The body fineness ratio is

$$
FR=\frac{L}{D_{\max}},
$$

and therefore

$$
\boxed{
D_{\max}=\frac{L}{FR}
}
\tag{EQ-1}
$$

where $L$ is overall hull length and $D_{\max}$ is the equivalent maximum diameter of the axisymmetric baseline hull.

The implementation evaluates

```python
max_diameter = length / fineness_ratio
```

Carichner and Nicolai identify fineness ratio as a major airship shape parameter. Compact bodies favor volume relative to surface area, whereas aerodynamic considerations generally favor more slender bodies [1].

### 4.1 Design-Bound Diagnostics and Numerical Guards


$$
\boxed{
g_L=\max(L_{\min}-L,0)
}
\tag{EQ-2}
$$

and

$$
\boxed{
g_{FR}=\max(FR_{\min}-FR,0)
}
\tag{EQ-3}
$$

are reported through `length_violation` and `fineness_ratio_violation`.

The configured defaults are

$$
L_{\min}=10\ {\rm m},
\qquad
FR_{\min}=2.
$$

These are design-bound diagnostics rather than physical laws.

Only tiny internal guards,

$$
L_{\mathrm{calc}}=\max(L,10^{-9}),
\qquad
FR_{\mathrm{calc}}=\max(FR,10^{-9}),
$$

are used to prevent undefined numerical operations. Physical/design bounds are intended to be imposed by the driver or optimizer.

**Classification:** design-limit diagnostics plus numerical safeguards.

---

## 5. Gross Hull Volume

The ideal prolate-spheroid volume is

$$
V_{\mathrm{sph}}
=
\frac{4}{3}\pi ab^2
=
\frac{\pi}{6}LD_{\max}^2.
$$

The current implementation introduces the hull-volume shape factor $k_V$:

$$
\boxed{
V
=
k_V
\frac{\pi}{6}LD_{\max}^{2}
}
\tag{EQ-4}
$$

with

$$
k_V=\texttt{hull\_volume\_shape\_factor}.
$$

For $k_V=1$, Eq. (EQ-4) reduces to the ideal prolate-spheroid relation. Using $D_{\max}=L/FR$,

$$
\boxed{
V
=
k_V
\frac{\pi L^3}{6FR^2}
}
\tag{EQ-5}
$$

so that, for fixed $FR$ and $k_V$,

$$
V\propto L^3,
$$

while for fixed $L$ and $k_V$,

$$
V\propto FR^{-2}.
$$

The cubic dependence on characteristic length explains the strong sensitivity of airship buoyant volume to vehicle dimensions.

Carichner and Nicolai use

$$
V=\frac{\pi LD^2}{6}
$$

for body-of-revolution preliminary sizing [1]. The additional $k_V$ factor is an ADaPT configuration/reference correction and should not be interpreted as a universal literature constant.

---

## 6. Wetted Surface Area

For the analytical prolate-spheroid basis,

$$
a=\frac{L}{2},
\qquad
b=\frac{D_{\max}}{2},
$$

with eccentricity

$$
\boxed{
e=
\sqrt{1-\frac{b^2}{a^2}}
}
\tag{EQ-6}
$$

for $a>b$.

The prolate-spheroid surface area is

$$
\boxed{
S_{\mathrm{wet}}
=
2\pi b^2+
\frac{2\pi ab}{e}\sin^{-1}(e)
}
\tag{EQ-7}
$$

and the spherical limit is

$$
\boxed{
S_{\mathrm{wet}}=4\pi a^2.
}
\tag{EQ-8}
$$

The software also retains a mathematically valid oblate-spheroid fallback for defensive numerical robustness, although normal airship design bounds are intended to keep the model in the elongated-body regime.

### 6.1 Multidisciplinary Role

The external wetted area affects, among other quantities:

1. envelope/structural material area,
2. aerodynamic skin-friction formulations,
3. conceptual internal-fabric area for semi-rigid/rigid configurations.

Carichner and Nicolai express airship skin-friction drag using wetted area normalized by an airship reference area based on $V^{2/3}$ [1]. Consequently, the coefficient's reference-area convention must be preserved consistently in the aerodynamic model.

**Classification:** fundamental analytical geometry; downstream use is literature-supported.

---

## 7. Aerodynamic Reference Area

The airship aerodynamic reference area is

$$
\boxed{
S_{\mathrm{ref}}=V^{2/3}
}
\tag{EQ-9}
$$

and is provided through

```python
ref_area_AeroCoeffs
```

This differs from the wing-planform reference area convention commonly used for fixed-wing aircraft.

A drag coefficient referenced to volume takes the form

$$
\boxed{
C_D=
\frac{D}
{\tfrac12\rho U^2V^{2/3}}.
}
\tag{EQ-10}
$$

Carichner and Nicolai use $V^{2/3}$ as a characteristic airship aerodynamic area [1].

This convention is important: a coefficient referenced to $V^{2/3}$ must not be used with wetted area, frontal area, or another area without an appropriate coefficient transformation.

**Classification:** established airship aerodynamic reference convention.

---

## 8. Body Geometric Ratios

### 8.1 simplified Geometric Slenderness Output

For simple analysis, the component uses

$$
\boxed{
AR_{\mathrm{geom,simplified}}
=
FR
=
\frac{L}{D_{\max}}
}
\tag{EQ-11}
$$

through

```text
aspect_ratio_geom
```

This is a body slenderness/fineness ratio and must not be confused with the lifting-surface aspect ratio.

### 8.2 Body Planform Aspect Ratio

The component also supplies a distinct body aspect ratio for airship aerodynamic correlations. For an axisymmetric ellipsoidal projected planform,

$$
S_{\mathrm{plan}}
=
\frac{\pi}{4}LD_{\max}.
$$

Therefore,

$$
\boxed{
AR_b
=
\frac{D_{\max}^2}{S_{\mathrm{plan}}}
=
\frac{4D_{\max}}{\pi L}
}
\tag{EQ-12}
$$

and the implementation outputs this as

```text
body_aspect_ratio
```

This quantity is distinct from both $FR=L/D_{\max}$ and the conventional fixed-wing aspect ratio $b^2/S$.

**Classification:** derived geometric quantity.

---

## 9. Initial Tail Sizing

Airship tails provide directional and longitudinal stability and control. At conceptual-design level, ADaPT sizes horizontal and vertical tail surfaces using airship tail-volume coefficients.

### 9.1 Tail-Volume-Coefficient Formulation

Carichner and Nicolai define the vertical-tail coefficient as

$$
\boxed{
C_{VT}
=
\frac{S_{VT}\ell_{VT}}
{L\,V^{2/3}}
}
\tag{EQ-13}
$$

and the horizontal-tail coefficient as

$$
\boxed{
C_{HT}
=
\frac{S_{HT}\ell_{HT}}
{L\,V^{2/3}}.
}
\tag{EQ-14}
$$

Solving for area,

$$
\boxed{
S_{HT}
=
C_{HT}
\frac{L V^{2/3}}{\ell_{HT}}
}
\tag{EQ-15}
$$

and

$$
\boxed{
S_{VT}
=
C_{VT}
\frac{L V^{2/3}}{\ell_{VT}}.
}
\tag{EQ-16}
$$

### 9.2 Tail Moment Arm

The default conceptual tail arm is

$$
\boxed{
\ell_t=f_tL
}
\tag{EQ-17}
$$

with

$$
f_t=0.38.
$$

Carichner and Nicolai report conceptual tail-arm values of approximately $0.36L$–$0.43L$ and use $0.38L$ in preliminary sizing examples [1]. The value remains configurable through `tail_arm_fraction`.

### 9.3 User-Supplied Tail Coefficients

With

```text
tail_coefficient_method = "user"
```

the component directly uses the supplied inputs

$$
C_{HT}=C_{HT,\mathrm{input}},
\qquad
C_{VT}=C_{VT,\mathrm{input}}.
$$

The default input values are

$$
C_{HT}=0.066,
\qquad
C_{VT}=0.059.
$$

These are baseline empirical inputs rather than universal constants.

### 9.4 Historical Volume-Based Correlations

With

```text
tail_coefficient_method = "historical"
```

the component evaluates the Chapter-7 initial-sizing correlations

$$
\boxed{
x=\frac{10^6}{V_{\mathrm{ft^3}}}
}
\tag{EQ-18}
$$

$$
\boxed{
C_{HT}
=
-0.0051x+0.0717
}
\tag{EQ-19}
$$

and

$$
\boxed{
C_{VT}
=
-0.0049x+0.0641.
}
\tag{EQ-20}
$$

A very small positive numerical lower guard is retained to prevent nonphysical negative coefficients if the empirical relation is evaluated far outside its intended conceptual range.

The outputs

```text
tail_volume_coeff_horizontal_used
tail_volume_coeff_vertical_used
```

report the coefficients actually used by the active sizing method.

**Classification:** literature-based empirical initial-sizing correlations.

---

## 10. Fin Wetted Area

After the projected horizontal and vertical tail areas are calculated, total conceptual tail wetted area is

$$
\boxed{
S_{\mathrm{fin,wet}}
=
k_{\mathrm{fin}}
\left(
S_{HT}+S_{VT}
\right)
}
\tag{EQ-21}
$$

with default

$$
k_{\mathrm{fin}}=2.2.
$$

Carichner and Nicolai use the same factor in conceptual tail-drag calculations as a wetted-to-projected-area conversion [1].

**Classification:** literature-supported empirical/conceptual relation.

---

## 11. Ballonet Sizing

Ballonets are internal air-filled volumes used in pressure-stabilized non-rigid and semi-rigid airships. They accommodate lifting-gas expansion/contraction and support envelope pressure management.

The current component distinguishes **installed ballonet capacity** from **actual ballonet air volume at the takeoff/reference condition**.

Rigid airships do not use the baseline ballonet formulation.

### 11.1 Pressure-Altitude Sizing

The default clean-sheet method is

```text
ballonet_sizing_method = "pressure_altitude"
```

and evaluates

$$
\boxed{
f_{B,\mathrm{theory}}
=
\max\left(
\frac{\rho_{SL}}{\rho_{\max}}-1,\,
0
\right).
}
\tag{EQ-22}
$$

An optional sizing factor is then applied:

$$
\boxed{
f_B
=
k_B f_{B,\mathrm{theory}}
}
\tag{EQ-23}
$$

where

$$
k_B=\texttt{ballonet\_sizing\_factor}
$$

and the default is

$$
k_B=1.
$$

Thus the default introduces no additional multiplier.

Installed ballonet capacity is

$$
\boxed{
V_B=f_BV.
}
\tag{EQ-24}
$$

This formulation follows the Chapter-11 density-ratio pressure-altitude sizing logic used in preliminary airship design [1]. It is a conceptual sizing relation and does not explicitly model every pressure-management effect such as lifting-gas superheat, atmospheric-pressure deviations, leakage, or detailed pressure-control schedules.

### 11.2 Prescribed-Fraction Validation Mode

For a reference aircraft with a known installed ballonet fraction,

```text
ballonet_sizing_method = "prescribed_fraction"
```

uses

$$
\boxed{
f_B=f_{B,\mathrm{pres}}
}
\tag{EQ-25}
$$

and

$$
\boxed{
V_B=f_{B,\mathrm{pres}}V.
}
\tag{EQ-26}
$$

For numerical protection, the prescribed input is limited to

$$
0\le f_{B,\mathrm{pres}}\le0.95.
$$

This mode is intended primarily for reference-airship validation. It should not be interpreted as an independent prediction of ballonet size.

### 11.3 Ballonet Design-Limit Diagnostic

The configured maximum ballonet fraction, default

$$
f_{B,\max}=0.80,
$$

is used as a diagnostic limit:

$$
\boxed{
g_B
=
\max(f_B-f_{B,\max},0).
}
\tag{EQ-27}
$$

The output is

```text
ballonet_fraction_violation
```

and feasibility corresponds to

$$
g_B\le0.
$$

For pressure-altitude sizing, the calculated physical result is **not silently clipped** to 0.80. This permits the driver/optimizer to identify an infeasible pressure-volume requirement.

There is no imposed 1% minimum ballonet fraction in the current implementation.

---

## 12. Atmospheric Coupling for Ballonet Sizing

The geometry component receives

$$
\rho_{SL}
$$

and

$$
\rho_{\max}
$$

through the OpenMDAO inputs

```text
rho_sea_level
rho_max_altitude
```

respectively.

In the integrated ADaPT framework, these values are intended to be supplied by the common atmosphere/operating-condition model. The dependency is therefore

$$
h_{\max}
\rightarrow
\text{Atmosphere}
\rightarrow
\rho_{\max}
\rightarrow
\text{Geometry}
\rightarrow
V_B.
$$



---

## 13. Structural Configuration

The component supports

$$
\boxed{
\text{non-rigid},
\qquad
\text{semi-rigid},
\qquad
\text{rigid}.
}
\tag{EQ-28}
$$

These categories are consistent with classical airship structural concepts described by Carichner and Nicolai [1].

The geometry component does not itself determine structural mass. Instead, it supplies geometric quantities required by the downstream mass model.

### 13.1 Outer Envelope Area

For semi-rigid and rigid configurations,

$$
\boxed{
S_{\mathrm{outer}}=S_{\mathrm{wet}}.
}
\tag{EQ-29}
$$

### 13.2 Internal Fabric/Membrane Area

The canonical current formulation is

$$
\boxed{
S_{\mathrm{internal}}
=
f_{\mathrm{internal}}S_{\mathrm{outer}}
}
\tag{EQ-30}
$$

with default

$$
f_{\mathrm{internal}}=0.25.
$$

This is a conceptual early-stage structural/mass proxy, not a universal airship constant.

The current canonical option is

```text
internal_fabric_area_factor
```

and the canonical output is

```text
internal_fabric_area
```

while `inner_envelope_area_factor` and `inner_envelope_area` are also used for simplicity.

---

## 14. Conceptual Framework Geometry

For semi-rigid and rigid airships, a characteristic total member length is generated for downstream conceptual structural-mass estimation.

### 14.1 Central/Keel Longitudinal Member

$$
L_{\mathrm{axis}}=L.
$$

### 14.2 Additional Longitudinal Members

$$
L_{\mathrm{long}}
=
N_{\mathrm{long}}L.
$$

Here $N_{\mathrm{long}}$ counts the **additional** longitudinal members and excludes the single central/keel member represented by $L_{\mathrm{axis}}$.

### 14.3 Circumferential Rings

With approximate circumference

$$
C_{\mathrm{ring}}=\pi D_{\max},
$$

the ring contribution is

$$
L_{\mathrm{rings}}
=
N_{\mathrm{rings}}\pi D_{\max}.
$$

The total conceptual framework member length is

$$
\boxed{
L_{\mathrm{framework}}
=
L+
N_{\mathrm{long}}L+
N_{\mathrm{rings}}\pi D_{\max}.
}
\tag{EQ-31}
$$

The default inputs are

$$
N_{\mathrm{long}}=12,
\qquad
N_{\mathrm{rings}}=16.
$$

If `framework_enabled=False`, the output is set to zero.

This is a **conceptual geometry parameterization**. It does not resolve geodesic structure, nonuniform longerons, detailed ring spacing, joints, cut-outs, local reinforcement, concentrated-load attachments, buckling, or structural optimization.

---

## 15. Rigid-Airship Gas Cells

For rigid airships,

$$
\boxed{
V_B=0
}
\tag{EQ-32}
$$

in the baseline geometry model.

Unlike the earlier approximation that equated gas-cell volume with gross hull volume, the current implementation uses a configurable gross-hull-to-lifting-gas ratio,

$$
R_{h/g}
=
\frac{V_{\mathrm{hull}}}
{V_{\mathrm{gas,cells}}}.
$$

Therefore,

$$
\boxed{
V_{\mathrm{cells,total}}
=
\frac{V}{R_{h/g}}
}
\tag{EQ-33}
$$

with default

$$
R_{h/g}=1.10.
$$

The equal-volume conceptual cell partition is

$$
\boxed{
V_{\mathrm{cell}}
=
\frac{V_{\mathrm{cells,total}}}
{N_{\mathrm{cells}}}.
}
\tag{EQ-34}
$$

The default is

$$
N_{\mathrm{cells}}=12.
$$

The 1.10 ratio is a conceptual historical preliminary-sizing approximation and is configurable. It represents the fact that gross rigid-hull volume is not entirely available for lifting gas because structure, cell spacing, access, equipment, and other internal volumes occupy space.

This model does not resolve actual gas-cell shape, local cell boundaries, pressure differences, or detailed internal structural packaging.

---

## 16. Lifting-Gas Volume at the Takeoff/Reference Condition

Installed ballonet capacity must be distinguished from actual ballonet air volume at a particular operating condition.

### 16.1 Non-Rigid and Semi-Rigid Airships

For an installed ballonet capacity $V_B$, the takeoff/reference ballonet air volume is

$$
\boxed{
V_{B,\mathrm{TO}}
=
f_{B,\mathrm{TO}}V_B
}
\tag{EQ-35}
$$

where

$$
0\le f_{B,\mathrm{TO}}\le1.
$$

The corresponding lifting-gas volume is

$$
\boxed{
V_{g,\mathrm{TO}}
=
\max\left(
V-V_{B,\mathrm{TO}},0
\right).
}
\tag{EQ-36}
$$

Therefore, an installed ballonet capacity of a given percentage of gross volume does **not** imply that the same percentage of the envelope is occupied by air at takeoff.

### 16.2 Rigid Airships

For rigid configurations,

$$
\boxed{
V_{B,\mathrm{TO}}=0
}
\tag{EQ-37}
$$

and

$$
\boxed{
V_{g,\mathrm{TO}}
=
V_{\mathrm{cells,total}}.
}
\tag{EQ-38}
$$

These quantities are provided through

```text
ballonet_volume_takeoff
lifting_gas_volume_takeoff
```

and are the geometry outputs intended for downstream aerostatic/takeoff gas-state calculations.

---

## 17. Model Outputs

### 17.1 Common Outputs

| Output | Symbol | Units | Description |
|---|---:|---:|---|
| `gross_volume` | $V$ | m³ | Gross hull volume after application of $k_V$ |
| `wetted_surface_area` | $S_{\mathrm{wet}}$ | m² | External analytical hull wetted surface |
| `max_diameter` | $D_{\max}$ | m | Equivalent maximum hull diameter $L/FR$ |
| `ref_area_AeroCoeffs` | $V^{2/3}$ | m² | Airship aerodynamic reference area |
| `horizontal_tail_planform_area` | $S_{HT}$ | m² | Horizontal-tail projected planform area |
| `vertical_tail_planform_area` | $S_{VT}$ | m² | Vertical-tail projected planform area |
| `fin_total_wetted_area` | $S_{\mathrm{fin,wet}}$ | m² | Total conceptual tail wetted area |
| `tail_arm` | $\ell_t$ | m | Tail moment arm used for initial sizing |
| `tail_volume_coeff_horizontal_used` | $C_{HT,\mathrm{used}}$ | – | Horizontal coefficient actually used |
| `tail_volume_coeff_vertical_used` | $C_{VT,\mathrm{used}}$ | – | Vertical coefficient actually used |
| `ballonet_volume` | $V_B$ | m³ | Installed ballonet capacity |
| `ballonet_fraction` | $f_B$ | – | Installed ballonet fraction |
| `ballonet_fraction_violation` | $g_B$ | – | Positive excess above configured maximum ballonet fraction |
| `ballonet_volume_takeoff` | $V_{B,\mathrm{TO}}$ | m³ | Actual ballonet air volume at takeoff/reference state |
| `lifting_gas_volume_takeoff` | $V_{g,\mathrm{TO}}$ | m³ | Lifting-gas volume at takeoff/reference state |
| `aspect_ratio_geom` | $FR$ | – | simplified compatibility alias equal to fineness ratio |
| `body_aspect_ratio` | $AR_b$ | – | Body planform aspect ratio $4D/(\pi L)$ |
| `length_violation` | $g_L$ | m | Lower-bound length violation |
| `fineness_ratio_violation` | $g_{FR}$ | – | Lower-bound fineness-ratio violation |

### 17.2 Semi-Rigid and Rigid Outputs

| Output | Symbol | Units | Description |
|---|---:|---:|---|
| `outer_envelope_area` | $S_{\mathrm{outer}}$ | m² | Outer structural-envelope area |
| `internal_fabric_area` | $S_{\mathrm{internal}}$ | m² | Canonical conceptual internal fabric/membrane area |
| `inner_envelope_area` | $S_{\mathrm{internal}}$ | m² | Backward-compatible alias |
| `framework_total_member_length` | $L_{\mathrm{framework}}$ | m | Conceptual total primary-framework member length |

### 17.3 Rigid-Airship Outputs

| Output | Symbol | Units | Description |
|---|---:|---:|---|
| `gas_cell_total_volume` | $V_{\mathrm{cells,total}}$ | m³ | Total conceptual usable lifting-gas-cell volume |
| `gas_cell_volume_each` | $V_{\mathrm{cell}}$ | m³ | Equal-volume conceptual gas-cell estimate |

---

## 18. Multidisciplinary Coupling

The geometry component participates directly in the closed airship mass–buoyancy–drag–propulsion–energy problem.

A simplified dependency chain is

$$
\boxed{
\begin{array}{c}
L,\ FR,\ k_V,\ \text{configuration}\\
\downarrow\\
D_{\max},\ V,\ S_{\mathrm{wet}},\ V^{2/3},\ V_{g,\mathrm{TO}}\\
\downarrow\\
\text{Buoyancy,\ Aerodynamics,\ Structure}\\
\downarrow\\
m_{\mathrm{vehicle}},\ D,\ P_{\mathrm{req}}\\
\downarrow\\
E_{\mathrm{mission}},\ m_{\mathrm{energy}}\\
\downarrow\\
\text{vehicle sizing and multidisciplinary closure}
\end{array}}
$$

Important couplings include:

- $V$ and $V_{g,\mathrm{TO}}$ affect available aerostatic lift.
- $S_{\mathrm{wet}}$ affects envelope/structural mass and participates in aerodynamic wetted-area formulations.
- $V^{2/3}$ establishes the airship aerodynamic coefficient reference area.
- $L$, $V$, and tail coefficients determine initial tail geometry.
- Ballonet capacity and takeoff fill state determine the lifting-gas volume available at the reference condition.
- Semi-rigid/rigid framework geometry feeds structural-mass estimation.
- Rigid hull-to-gas-volume ratio changes usable lifting-gas volume and therefore aerostatic capability.

The distinction between $S_{\mathrm{wet}}$ and $V^{2/3}$ is especially important: geometry supplies both quantities, but aerodynamic coefficients must be used with the reference area for which they were defined.

---

## 19. Assumptions and Limitations

| Item | Current treatment | Classification |
|---|---|---|
| Baseline external shape | Single-lobed prolate-spheroid analytical basis | Literature-supported conceptual assumption |
| Hull-volume correction | Configurable $k_V$ | Configuration/reference correction |
| Wetted area with $k_V\neq1$ | Remains spheroid area from $L,D_{\max}$ | Modeling limitation |
| Minimum length | 10 m diagnostic bound; not silently imposed | Design-limit diagnostic |
| Minimum fineness ratio | 2.0 diagnostic bound; not silently imposed | Design-limit diagnostic |
| Aerodynamic reference area | $V^{2/3}$ | Literature-supported convention |
| simplified `aspect_ratio_geom` | Equal to $L/D$ | Backward compatibility |
| Body aspect ratio | $4D/(\pi L)$ | Derived geometry |
| Tail moment arm | Default $0.38L$ | Literature-supported conceptual assumption |
| User tail coefficients | Default $0.066/0.059$ | Baseline empirical inputs |
| Historical tail coefficients | Chapter-7 volume-based correlations | Literature-supported empirical relation |
| Tail wetted/planform factor | 2.2 | Literature-supported empirical relation |
| Ballonet pressure-altitude method | Density-ratio relation | Adapted/literature-supported conceptual relation |
| Ballonet sizing factor | Default 1.0 | Sensitivity/calibration parameter |
| Prescribed ballonet mode | Known installed fraction | Reference-validation input |
| Maximum ballonet fraction | 0.80 diagnostic only | Design-limit assumption |
| Takeoff ballonet fill | User/state input | Operating-state assumption/input |
| Atmospheric density | Supplied by common atmosphere model | Multidisciplinary coupling |
| Internal fabric factor | 0.25 | Conceptual assumption |
| Framework member counts | 12 longitudinal + 16 rings by default | Conceptual structural assumptions |
| Framework geometry | Characteristic member-length model | Conceptual approximation |
| Rigid hull/gas ratio | 1.10 default | Conceptual historical approximation |
| Gas-cell distribution | Equal-volume | Conceptual approximation |
| Number of gas cells | 12 default | Conceptual assumption |
| Geometry fidelity | Conceptual/preliminary design | Model scope |

---

## 20. Model Provenance Classification

The documentation uses the following labels:

| Label | Meaning |
|---|---|
| **F** | Fundamental physical or geometric relation |
| **L** | Directly supported by literature |
| **A** | Adapted literature relation |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **N** | Numerical safeguard |
| **D** | Internally derived quantity |
| **C** | Calibration/reference-configuration parameter |

The principal relations are classified as follows:

| Equation | Relationship | Classification |
|---|---|---|
| EQ-1 | $D_{\max}=L/FR$ | F / L |
| EQ-2–3 | Design-bound violation metrics | D / N |
| EQ-4 | Shape-factor-corrected spheroid volume | F / D / C |
| EQ-5 | Volume through $L,FR,k_V$ | D |
| EQ-6–8 | Spheroid eccentricity and surface area | F |
| EQ-9–10 | $V^{2/3}$ aerodynamic reference convention | L |
| EQ-11 | simplified geometric slenderness output | D |
| EQ-12 | Body planform aspect ratio | D |
| EQ-13–16 | Tail-volume coefficient definitions and area sizing | L / E / D |
| EQ-17 | Tail arm | L / AS |
| EQ-18–20 | Historical tail-coefficient correlations | L / E |
| EQ-21 | Tail wetted-area factor | L / E |
| EQ-22 | Pressure-altitude ballonet fraction | A / L |
| EQ-23 | Ballonet sizing multiplier | AS / C |
| EQ-24 | Installed ballonet capacity | D |
| EQ-25–26 | Prescribed-fraction validation mode | C / D |
| EQ-27 | Ballonet-fraction violation | D / N |
| EQ-28 | Structural configuration categories | L |
| EQ-29 | Outer-envelope area | D |
| EQ-30 | Internal-fabric-area proxy | AS |
| EQ-31 | Framework characteristic member length | AS |
| EQ-32 | No baseline rigid-airship ballonet | AS |
| EQ-33 | Rigid usable gas-cell volume | AS |
| EQ-34 | Equal gas-cell partition | AS |
| EQ-35–38 | Takeoff/reference ballonet and lifting-gas state | D |

---

## 21. Numerical Implementation and Derivatives

The geometry component currently declares partial derivatives using finite differences:

```python
self.declare_partials("*", "*", method="fd", step=1.0e-7)
```

with perturbation

$$
\Delta x=10^{-7}.
$$

This is an implementation choice rather than part of the physical theory.

For future large-scale gradient-based optimization, analytic derivatives or complex-step-compatible formulations may improve derivative accuracy and computational efficiency. Particular care is required around `max`, `clip`, architecture branches, and model-selection branches because these introduce nonsmooth or piecewise behavior.

The implementation converts OpenMDAO scalar arrays to Python scalars through an internal helper. Extremely small positive guards are used only where required to avoid division by zero or undefined geometry.

---

## 22. Verification and Validation Strategy

The geometry component should be assessed at three distinct levels.

### 22.1 Equation and Unit Verification

For selected $L$, $FR$, and $k_V$, independently confirm:

- $D_{\max}=L/FR$,
- ideal spheroid volume and shape-factor-corrected volume,
- spheroid wetted surface area,
- $V^{2/3}$,
- body aspect ratio $4D/(\pi L)$,
- tail coefficients for both `user` and `historical` modes,
- tail planform and wetted areas,
- ballonet capacity for both sizing modes,
- ballonet violation metric,
- takeoff ballonet and lifting-gas volumes,
- framework characteristic length, and
- rigid gas-cell volume and equal-cell partition.

### 22.2 Limiting and Configuration Tests

Recommended tests include:

- sphere limit $a\rightarrow b$,
- increasing $FR$ at constant $L$,
- increasing $L$ at constant $FR$,
- $k_V=1$ recovery of the ideal spheroid volume,
- low/no altitude excursion in pressure-altitude ballonet sizing,
- prescribed ballonet fraction at 0 and representative installed values,
- takeoff ballonet fill fractions of 0 and 1,
- ballonet fraction above the configured diagnostic limit,
- non-rigid, semi-rigid, and rigid architecture selections,
- framework enabled and disabled,
- single gas-cell limit,
- rigid hull-to-gas ratio of 1.0 and values greater than 1.0,
- length and fineness-ratio design-bound violations, and
- nonphysical candidate inputs intercepted only by tiny numerical guards.

### 22.3 Integrated Reference-Airship Validation

Reference-airship validation should compare independently available geometric quantities such as:

- overall length,
- maximum/equivalent diameter,
- gross hull volume,
- fineness ratio,
- ballonet fraction where known,
- tail geometry where known,
- rigid lifting-gas volume where known, and
- wetted area where independently available.

Prescribed inputs should not be counted as independent prediction successes. For example, if a known hull volume is reproduced by setting $k_V$ from that same reference volume, the result verifies implementation consistency but is not an independent validation of volume prediction.

Similarly, a prescribed ballonet fraction is a reference configuration input, not an independently predicted output.

Integrated validation results should therefore distinguish:

1. **prescribed/reference quantities,**
2. **derived quantities,**
3. **independently predicted quantities**, and
4. **constraint/feasibility quantities**.

This distinction prevents zero-error prescribed values from being misrepresented as predictive validation.

---

## 23. Advanced Geometry Models

Separate experimental geometry developments may include NPL-type, GNVR-type, Wang-type, or multi-lobed hull representations. These are **not part of the validated baseline geometry theory documented here** unless their exact equations, area/volume definitions, aerodynamic reference conventions, and verification cases are implemented and independently checked.

The official baseline Theory Guide therefore treats the current single-lobed prolate-spheroid-based `AirshipGeometry` component as the reference geometry implementation.

Advanced hull formulations should be documented separately once their literature equations and implementation have been verified.

---

## 24. Software Traceability Summary

The current theory maps to the implementation as follows:

| Theory item | Current implementation |
|---|---|
| Hull diameter | `max_diameter = length / fineness_ratio` |
| Gross volume | `hull_volume_shape_factor * (pi/6) * length * max_diameter**2` |
| Wetted area | `_spheroid_area(length/2, max_diameter/2)` |
| Aerodynamic reference area | `gross_volume**(2/3)` |
| simplified geometric ratio | `aspect_ratio_geom = fineness_ratio` |
| Body aspect ratio | `4*max_diameter/(pi*length)` |
| Tail coefficient selection | `tail_coefficient_method = user/historical` |
| Historical coefficients | `_historical_tail_coefficients(gross_volume)` |
| Tail arm | `tail_arm_fraction * length` |
| Tail areas | $C_t L V^{2/3}/\ell_t$ |
| Tail wetted area | `(S_HT + S_VT) * tail_wetted_area_factor` |
| Pressure-altitude ballonet | `ballonet_sizing_factor * max(rho_SL/rho_alt - 1, 0)` |
| Prescribed ballonet | `ballonet_fraction_prescribed` |
| Ballonet diagnostic | `max(ballonet_fraction - max_ballonet_fraction, 0)` |
| Internal fabric area | `outer_area * internal_fabric_area_factor` |
| Framework length | `L + N_long*L + N_rings*pi*D` |
| Rigid gas volume | `gross_volume / rigid_hull_to_gas_volume_ratio` |
| Takeoff ballonet volume | `ballonet_fill_fraction_takeoff * ballonet_volume` |
| Takeoff lifting-gas volume | non-rigid/semi-rigid: `gross_volume - ballonet_volume_takeoff`; rigid: `gas_cell_total_volume` |
| Derivatives | finite difference, step $10^{-7}$ |

This table is intended as a traceability aid rather than a replacement for the governing-equation sections.

---

## 25. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.

### Additional references retained for future advanced-geometry development

[2] M. Atyya, G. M. ElBayoumi, and M. Lotfy, “Optimal shape design of an airship based on geometrical aerodynamic parameters,” *Beni-Suef University Journal of Basic and Applied Sciences*, vol. 12, article 25, 2023.

[3] X. L. Wang and X. X. Shan, “Shape optimization of stratosphere airship,” *Journal of Aircraft*, vol. 43, no. 1, pp. 283–286, 2006.

[4] S. Kale, P. Joshi, and R. Pant, “A generic methodology for determination of drag coefficient of an aerostat envelope using CFD,” AIAA 5th Aviation Technology, Integration and Operations Conference / 16th Lighter-Than-Air Systems Technology Conference, AIAA Paper 2005-7442, 2005.

[5] M. Manikandan, E. Vaidya, and R. S. Pant, “Design and analysis of hybrid electric multi-lobed airship for cargo transportation,” *Sustainable Energy Technologies and Assessments*, vol. 51, 101892, 2022.

---

