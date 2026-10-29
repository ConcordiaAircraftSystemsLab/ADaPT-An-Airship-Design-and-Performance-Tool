# Validation Methodology

Validation in ADaPT is the structured process used to determine whether the multidisciplinary framework reproduces independently available characteristics of known airships when their published/reference configuration and operating conditions are supplied.

The validation methodology deliberately distinguishes:

- **mission requirements**,
- **prescribed reference-aircraft quantities**,
- **system-level design variables**,
- **calibration parameters**,
- **multidisciplinary coupling variables**,
- **independently predicted validation quantities**,
- **predicted performance quantities**, and
- **quantities for which no independent reference is available**.

This distinction is essential because an OpenMDAO variable can have different engineering roles depending on the analysis boundary.

A variable being an **input to a component does not mean that it is a fixed requirement of the complete aircraft-design problem**.

For example, airship length may simultaneously be:

$$
\boxed{
\begin{array}{ll}
\text{Geometry component:} & \text{input}\\
\text{Clean-sheet MDAO:} & \text{design variable}\\
\text{Reference validation:} & \text{prescribed reference quantity}\\
\text{Final optimized design:} & \text{sizing result}.
\end{array}
}
\tag{EQ-1}
$$

Likewise, MTOM may simultaneously be:

$$
\boxed{
\begin{array}{ll}
\text{mass component:} & \text{output}\\
\text{Performance component:} & \text{input}\\
\text{MDAO system:} & \text{coupling variable}\\
\text{Validation:} & \text{predicted quantity compared with reference data}.
\end{array}
}
\tag{EQ-2}
$$

The present validation framework is built around this interpretation.

---

## 1. Purpose of Validation

The fundamental validation question is

$$
\boxed{
\begin{array}{c}
\text{Given the known configuration, installed hardware,}\\
\text{loading, and operating conditions of a reference airship,}\\
\text{does ADaPT reproduce independently documented characteristics?}
\end{array}
}
\tag{EQ-3}
$$

The purpose is **not** to claim that a known aircraft has been rediscovered from payload and range alone.

Instead:

1. published or otherwise defensible reference quantities are imposed where appropriate;
2. the coupled ADaPT model is executed;
3. independent outputs are compared with available reference data;
4. component and vehicle mass buildup is inspected;
5. physical feasibility constraints are assessed separately;
6. unavailable data remain `N/A`;
7. calibration is reported explicitly rather than being hidden inside “validation.”

This methodology allows the same framework to be used rigorously for existing-aircraft validation and later for clean-sheet design.

---

## 2. Three Distinct ADaPT Analysis Modes

The same component models support three fundamentally different uses.

### 2.1 Reference-Aircraft Validation

A known aircraft is reconstructed using its documented:

- geometry,
- structural type,
- payload/loading,
- operating condition,
- installed propulsion rating,
- installed energy/resource capacity,
- and other known configuration quantities.

The question is:

$$
\boxed{
\text{Does the integrated model reproduce independent reference quantities?}
}
$$

Geometry and installed hardware may therefore be deliberately fixed.

### 2.2 Forward Mission Analysis

A vehicle is already defined.

The mission model predicts:

- drag,
- required power,
- mission duration,
- resource demand,
- takeoff/landing performance,
- buoyancy/lift feasibility,
- energy feasibility.

The vehicle is evaluated, not resized.

### 2.3 Clean-Sheet Sizing and Optimization

The user supplies requirements such as

$$
\boxed{
m_{\rm payload},
\quad
R,
\quad
h,
\quad
V,
\quad
\text{architecture}.
}
\tag{EQ-4}
$$

Candidate vehicle variables may include

$$
\boxed{
L,\quad
FR,\quad
BR,\quad
P_{\rm installed},\quad
C_{HT},\quad
C_{VT},\quad
\eta_p,\ldots
}
\tag{EQ-5}
$$

and are changed until the multidisciplinary design satisfies constraints and optimizes the chosen objectives.

Therefore:

$$
\boxed{
\text{validation}
\neq
\text{forward mission analysis}
\neq
\text{clean-sheet sizing}.
}
\tag{EQ-6}
$$

---

## 3. Validation Hierarchy

A rigorous validation program should proceed in layers.

### 3.1 Level I — Equation and Unit Verification

Individual equations are reproduced independently.

Examples include:

- prolate-spheroid geometry,
- $V^{2/3}$ reference area,
- envelope WER,
- tail WER,
- gondola WER,
- propulsion power relations,
- propeller equations,
- buoyancy force,
- takeoff force balance,
- resource-capacity constraints.

This establishes that the equations are implemented correctly.

### 3.2 Level II — Component-Level Verification/Validation

Each discipline is assessed independently where data exist:

$$
\boxed{
\text{Geometry},
\quad
\text{mass},
\quad
\text{Performance},
\quad
\text{Propulsion},
\quad
\text{Power/Energy},
\quad
\text{Tank}.
}
$$

### 3.3 Level III — Literature Conceptual-Design Reproduction

The strongest bridge between equation verification and real-aircraft validation is reproduction of a complete literature design example.

For ADaPT, the A-170/Chapter-11 case is particularly valuable because the source contains:

- geometry,
- payload and loading,
- installed propulsion,
- aerodynamic assumptions,
- takeoff assumptions,
- component mass breakdown,
- OEM/empty-mass information,
- MTOM/gross-mass information.

This tests the **integrated design chain** using a documented conceptual reference.

### 3.4 Level IV — Real-Aircraft Validation

Known production/research airships are used to test the integrated framework.

Current ADaPT reference cases span different structural and architecture classes, including:

- A-170 — non-rigid, conventional reciprocating,
- AVIC AS700 — non-rigid, conventional reciprocating,
- AV-10 — non-rigid,
- Zeppelin NT 07-101 — semi-rigid, conventional reciprocating,
- BASI MB-30T — rigid, turboelectric reference architecture.

Not every case has the same quality or completeness of public reference data.

The validation evidence must therefore be interpreted per quantity and per vehicle.

---

## 4. Variable-Role Classification

Each quantity should be assigned an engineering role.

The recommended labels are:

```text
REQ   = mission/design requirement
REF   = prescribed reference-aircraft quantity
CAL   = calibration/reference-model parameter
PRED  = independently predicted validation quantity
COUP  = multidisciplinary coupling variable
PERF  = predicted performance quantity
DER   = derived reference quantity
N/A   = no independent reference available
```

### 4.1 Mission Requirements — `REQ`

These define what the aircraft must accomplish.

Examples:

$$
m_{\rm payload},
\quad
R,
\quad
h_c,
\quad
V_c.
$$

### 4.2 Reference-Aircraft Inputs — `REF`

These describe known characteristics of the validation aircraft.

Examples:

$$
L,
\quad
FR,
\quad
N_{\rm engine},
\quad
P_{\rm installed},
\quad
m_{\rm fuel,installed}.
$$

They are imposed for reference-aircraft validation.

### 4.3 Calibration Parameters — `CAL`

A parameter is `CAL` if its value is deliberately selected from or tuned to reference-aircraft information.

Examples can include:

- aircraft-specific envelope areal density,
- framework coefficient,
- known gondola mass override,
- known fuel-system hardware mass,
- known pressure-system mass.

A calibration quantity must not subsequently be counted as an independent validation prediction.

### 4.4 Coupling Variables — `COUP`

These are outputs of one discipline and inputs to another:

$$
V,
\quad
S_{\rm ref},
\quad
m_{\rm MTOM},
\quad
P_{\rm required},
\quad
m_{\rm fuel,req},
\quad
m_{\rm battery,req}.
$$

### 4.5 Predicted Validation Quantities — `PRED`

These are calculated by ADaPT and have an independent reference.

Examples may include:

$$
V,
\quad
S_{\rm wet},
\quad
OEM,
\quad
MTOM,
\quad
m_{\rm envelope},
\quad
m_{\rm gondola}.
$$

### 4.6 Predicted Performance Quantities — `PERF`

These are model outputs such as:

- ground roll,
- takeoff distance,
- required shaft power,
- mission duration,
- landing distance.

They are true predictions, but only become **validation comparisons** when independent reference data exist.

### 4.7 Derived Reference Quantities — `DER`

Some comparison values are calculated from published quantities rather than published directly.

For example:

$$
m_{\rm base,ref}
=
m_{\rm MTOM,ref}
-
m_{\rm useful,ref}.
$$

Such quantities must be labeled as derived.

---

## 5. Why Prescribed Values Must Not Receive “Validation Error”

If a reference quantity is imposed exactly,

$$
x_{\rm model}
=
x_{\rm ref}
$$

by construction.

Reporting

$$
0\%
$$

error would falsely imply predictive capability.

Therefore percent error is reported only for independently predicted quantities:

$$
\boxed{
\epsilon_x
=
\frac{
x_{\rm ADaPT}-x_{\rm ref}
}{
x_{\rm ref}
}
100\%.
}
\tag{EQ-7}
$$

For `REF`, `REQ`, or unavailable values, validation error should be reported as:

```text
N/A
```

or

```text
Prescribed
```

rather than `0.0%`.

This rule is implemented in the current A-170 validation driver.

---

## 6. Validation versus Calibration

Validation and calibration are different operations.

### 6.1 Calibration

Calibration uses known reference information to select or adjust a model parameter:

$$
\boxed{
\text{reference datum}
\rightarrow
\text{model parameter}.
}
\tag{EQ-8}
$$

### 6.2 Validation

Validation compares a model output with an independent datum that was not used to force that same result:

$$
\boxed{
\text{model prediction}
\leftrightarrow
\text{independent reference}.
}
\tag{EQ-9}
$$

A useful validation dataset should therefore be partitioned:

$$
\boxed{
D_{\rm reference}
=
D_{\rm prescribed}
\cup
D_{\rm calibration}
\cup
D_{\rm independent}.
}
\tag{EQ-10}
$$

Only

$$
D_{\rm independent}
$$

can support independent prediction error.

---

## 7. Validation Data Provenance

Reference values should be classified as:

```text
PUB   = directly published value
BOOK  = value from primary literature/design example
DER   = derived from published values
EST   = secondary estimate
CAL   = used for calibration
N/A   = unavailable
```

The source and definition of each datum matter as much as its number.

For example, the terms

- empty mass,
- basic empty mass,
- operating empty mass,
- base mass,
- useful load,
- payload,
- loading capacity

must not be silently treated as interchangeable.

---

## 8. Missing Reference Data

No value should be invented merely to fill a validation table.

If a source does not provide:

- component mass,
- ground-roll distance,
- wetted area,
- framework mass,
- fuel-system hardware mass,

the reference field remains

```text
N/A.
```

The model prediction can still be reported for transparency, but no validation percentage should be calculated.

This avoids converting model assumptions into false experimental evidence.

---

## 9. Mass-Accounting Convention

The current ADaPT mass model uses

$$
\boxed{
m_{\rm MTOM}
=
m_{\rm OEM}
+
m_{\rm payload}
+
m_{\rm consumable}
+
m_{\rm ballast}.
}
\tag{EQ-11}
$$

Helium mass is calculated as a gas-state/aerostatic quantity but is excluded from OEM and MTOM:

$$
\boxed{
m_{\rm He}\notin OEM,
\qquad
m_{\rm He}\notin MTOM.
}
\tag{EQ-12}
$$

Validation drivers must preserve this convention.

A previous validation document incorrectly included helium in the conceptual OEM buildup. That representation is obsolete.

The helium value may be reported separately as a gas-state diagnostic.

---

## 10. Geometry Validation

For a known aircraft, length and fineness ratio may be prescribed:

$$
L=L_{\rm ref},
\qquad
FR=FR_{\rm ref}.
$$

Geometry then predicts quantities such as:

$$
D,
\quad
V,
\quad
S_{\rm wet},
\quad
V^{2/3},
\quad
S_T,
\quad
V_B,
\quad
V_{g,TO}.
$$

If `hull_volume_shape_factor` is itself fitted from the reference volume, the reproduced volume is a **calibrated geometry closure**, not an independent validation prediction.

This distinction is especially important for real-airship geometries that deviate from the ideal spheroid.

---

## 11. mass Validation

mass validation should examine both:

1. component mass buildup;
2. integrated OEM/MTOM closure.

The current mass definition is

$$
\boxed{
\begin{aligned}
OEM={}&
m_{\rm envelope}
+m_{\rm ballonet}
+m_{\rm curtain}
+m_{\rm framework}
+m_{\rm gondola}
+m_{\rm tail}\\
&+m_{\rm landing}
+m_{\rm propulsion}
+m_{\rm power}
+m_{\rm tank}
+m_{\rm fuel\ tank}
+m_{\rm crew}\\
&+m_{\rm pressure}
+m_{\rm VMS}
+m_{\rm misc}
+m_{\rm margin}.
\end{aligned}
}
\tag{EQ-13}
$$

Inactive terms are zero.

Helium is excluded.

MTOM is then obtained through Eq. (EQ-11).

Whole-aircraft OEM/MTOM agreement is strong integrated evidence, but it cannot by itself prove that every component WER is correct because compensating errors may occur.

---

## 12. Propulsion Validation

Installed shaft power and required shaft power must be separated.

For a known aircraft,

$$
P_{\rm installed}
$$

is generally a reference input.

Performance independently predicts

$$
P_{\rm required}.
$$

The power constraint is

$$
\boxed{
g_P
=
P_{\rm required}
-
P_{\rm installed}.
}
\tag{EQ-14}
$$

Thus:

$$
g_P\le0
$$

is feasible.

A published installed rating should not be automatically increased merely because the configured mission predicts a higher requirement.

That discrepancy is itself a validation/consistency result requiring physical investigation.

---

## 13. Resource-Capacity Validation

ADaPT distinguishes required and installed resources.

For a fuel/hydrogen architecture,

$$
\boxed{
g_{E,p}
=
m_{\rm cons,req}
-
m_{\rm cons,installed}.
}
\tag{EQ-15}
$$

For a battery architecture,

$$
\boxed{
g_{E,b}
=
m_{\rm batt,req}
-
m_{\rm batt,installed}.
}
\tag{EQ-16}
$$

For hybrid architectures,

$$
\boxed{
g_E
=
\max(g_{E,p},g_{E,b}).
}
\tag{EQ-17}
$$

Installed capacity from a reference aircraft is a `REF` input.

Required resource is a model prediction.

---

## 14. Buoyancy Validation

The selected takeoff buoyancy ratio defines required buoyancy:

$$
\boxed{
L_{B,\rm req}
=
BR_{TO}m_{TO}g.
}
\tag{EQ-18}
$$

Available buoyancy is independently obtained from the gas state:

$$
\boxed{
L_{B,\rm avail}
=
(\rho_{\rm air}V_{g,TO}-m_{\rm He})g.
}
\tag{EQ-19}
$$

The constraint is

$$
\boxed{
g_B
=
L_{B,\rm req}
-
L_{B,\rm avail}.
}
\tag{EQ-20}
$$

Feasibility requires

$$
g_B\le0.
$$

The direct Geometry-to-Performance takeoff lifting-gas-volume coupling should be used whenever available.

---

## 15. Aerodynamic Lift and Performance Validation

The cruise lift constraint is

$$
\boxed{
g_L
=
\max_i|C_{L,i}|
-
C_{L,\max}.
}
\tag{EQ-21}
$$

Takeoff-field and landing-field constraints are

$$
\boxed{
g_{TO}
=
S_{TO}
-
S_{\rm field,max},
}
\tag{EQ-22}
$$

$$
\boxed{
g_L^{field}
=
S_{L,\rm field}
-
S_{\rm field,max}.
}
\tag{EQ-23}
$$

Again,

$$
g\le0
$$

means feasible.

These constraints should be reported separately from validation percent error.

---

## 16. OpenMDAO Validation Workflow

The top-level driver uses

```python
AirshipAnalysisGroup
```

which already owns the central independent-variable subsystem.

The correct validation sequence is

$$
\boxed{
\begin{array}{c}
\text{Create }om.Problem\\
\downarrow\\
\text{Assign }AirshipAnalysisGroup\\
\downarrow\\
\text{Problem.setup()}\\
\downarrow\\
\text{set known reference values with }set\_val\\
\downarrow\\
\text{run model}\\
\downarrow\\
\text{extract predictions/constraints}\\
\downarrow\\
\text{compare only independent quantities}.
\end{array}
}
\tag{EQ-24}
$$

A second promoted `IndepVarComp` should not be added by the validation driver.

---

# Part II — A-170 Literature Validation

## 17. Purpose of the A-170 Case

The A-170 case is the most important literature-level integrated validation because it is tied directly to the Carichner–Nicolai conceptual-design/reference breakdown.

The current driver treats the aircraft as:

```text
airship_type = non-rigid
power_source = conventional_reciprocating
landing_system = conventional
```

The baseline run is a **reference validation**, not a free-sizing optimization.

---

## 18. A-170 Reference Definition

The current driver uses:

| Quantity | Reference |
|---|---:|
| Length | 53.58 m |
| Fineness ratio | 4.10 |
| Payload | 1122 kg |
| Range | 1,342,100 m |
| Cruise altitude | 914.4 m |
| Cruise speed | 19.57 m/s |
| Installed consumable capacity | 599 kg |
| Crew | 1 |
| Engines | 2 |
| Installed shaft power | 268 kW |
| Takeoff buoyancy ratio | 0.816 |
| Landing BR input | 0.90 |
| Reference MTOM | 5629 kg |

These values define the A-170 validation configuration.

---

## 19. A-170 Reference/Predicted Roles

### 19.1 Prescribed A-170 Values

The following are `REF`/`REQ` and should not receive predictive validation errors:

- length,
- fineness ratio,
- payload,
- range,
- cruise altitude,
- cruise speed,
- installed fuel capacity,
- installed shaft power,
- $BR_{TO}$,
- engine count,
- crew count.

### 19.2 Predicted Comparison Quantities

The current driver compares predictions including:

- MTOM,
- ground roll,
- wetted surface area,
- gross volume,
- aerodynamic reference area,
- mass geometry area.

The driver explicitly assigns validation roles and calculates percent error only for the independently predicted rows.

---

## 20. A-170 Aircraft-Specific Mass Anchors

The present A-170 validation includes several **explicit aircraft-specific known masses**:

$$
\boxed{
m_{\rm gondola}=1500\ {\rm kg},
}
\tag{EQ-25}
$$

$$
\boxed{
m_{\rm conventional\ fuel\ system}=42.0\ {\rm kg},
}
\tag{EQ-26}
$$

$$
\boxed{
m_{\rm pressure/air\ system}=67.1\ {\rm kg}.
}
\tag{EQ-27}
$$

These are imposed through validation-specific overrides.

VMS is currently disabled in the A-170 validation until the mapping between the source FCS/actuator categories and ADaPT VMS ownership is unambiguous.

The miscellaneous fraction uses the A-170 reference bookkeeping ratio

$$
\boxed{
f_{\rm misc}
=
\frac{75}{3908}.
}
\tag{EQ-28}
$$

These values are `CAL/REF`, not independent predictions.

---

## 21. A-170 Component Breakdown

The A-170 source includes a component-level mass breakdown, which makes this case especially valuable.

Where a source value is independently available, ADaPT component outputs may be directly compared.

Examples include reference categories such as:

- gondola,
- envelope,
- propulsion installation,
- ballonet,
- tail-related structure,
- fuel-system hardware,
- pressure/air system,
- crew,
- miscellaneous items,
- empty/base mass,
- fuel,
- payload,
- gross mass.

This allows the framework to be assessed at both subsystem and integrated levels.

---

## 22. A-170 Ground-Roll Validation

The current A-170 comparison uses

$$
\boxed{
S_{G,\rm ref}=432\ {\rm m}
}
\tag{EQ-29}
$$

and compares it with

```text
ground_roll_distance
```

from the current Performance component.

The current Performance convention is now unambiguous:

```text
ground_roll_distance = takeoff_ground_roll
```

and does **not** represent total takeoff distance.

This corrects older validation-document wording that warned the simplified name might contain total takeoff distance.

---

## 23. A-170 Validation Value

The A-170 case provides three complementary forms of evidence:

1. **equation implementation** against the same primary literature;
2. **component mass buildup** against published breakdown data;
3. **integrated vehicle closure** against reference MTOM and performance quantities.

Because some A-170 subsystem masses are explicitly overridden from the source, the final validation report must distinguish those reference anchors from independently predicted WER results.

---

# Part III — Zeppelin NT 07-101 Validation

## 24. Purpose of the Zeppelin Case

The Zeppelin NT case tests ADaPT on a **semi-rigid real aircraft** rather than the non-rigid A-170 literature example.

The current driver uses:

```text
airship_type = semi-rigid
power_source = conventional_reciprocating
landing_system = conventional
ballonet_sizing_method = prescribed_fraction
tail_coefficient_method = historical
propulsion_installation_mass_method = structure_integrated
```

This preserves structural-class and installation distinctions.

---

## 25. Correct Zeppelin Reference Definition

The current reference values are:

$$
L_{\rm ref}=75.0\ {\rm m},
$$

$$
D_{\rm ref}=14.2\ {\rm m},
$$

$$
FR_{\rm ref}
=
\frac{75.0}{14.2}
\approx5.282,
$$

$$
V_{\rm ref}=8425\ {\rm m^3},
$$

$$
MTOM_{\rm ref}=8050\ {\rm kg},
$$

$$
m_{\rm useful,ref}=1900\ {\rm kg},
$$

$$
m_{\rm fuel,ref}=1100\ {\rm kg},
$$

so the validation loading split is

$$
\boxed{
m_{\rm payload,ref}
=
1900-1100
=
800\ {\rm kg}.
}
\tag{EQ-30}
$$

The primary comparison base mass is therefore

$$
\boxed{
m_{\rm base,ref}
=
8050-1900
=
6150\ {\rm kg}.
}
\tag{EQ-31}
$$

A secondary published empty-mass value

$$
\boxed{
6622\ {\rm kg}
}
\tag{EQ-32}
$$

is retained as contextual information but is **not silently substituted for the primary derived base-mass comparison**.

This corrects the old validation documentation, which used the obsolete 5065-kg value and treated the full 1900-kg loading capacity as payload.

---

## 26. Zeppelin Mission and Installed Hardware

The current validation uses:

| Quantity | Value |
|---|---:|
| Range | 1000 km |
| Cruise speed | 31 m/s |
| Cruise altitude | 600 m |
| Installed shaft power | 441 kW |
| Engines | 3 |
| Crew | 2 |
| Fuel capacity | 1100 kg |
| Payload interpretation | 800 kg |
| $BR_{TO}$ | 0.95 |

These values are prescribed reference/configuration quantities.

---

## 27. Zeppelin Geometry-Specific Inputs

The current validation uses

$$
\boxed{
k_V=1.0640
}
\tag{EQ-33}
$$

for the hull-volume shape factor.

It also uses

$$
\boxed{
f_{B,\rm prescribed}=0.26,
}
\tag{EQ-34}
$$

and

$$
\boxed{
f_{B,TO}=0.340.
}
\tag{EQ-35}
$$

The gondola dimensions are:

$$
L_G=10.7\ {\rm m},
\qquad
W_G=1.67\ {\rm m},
\qquad
H_G=1.80\ {\rm m}.
$$

Because $k_V$ is chosen as part of the known Zeppelin geometry representation, exact reproduction of gross volume should be interpreted as a **reference/configuration closure**, not an entirely independent prediction from an ideal spheroid.

---

## 28. Zeppelin Validation-Specific Structural Calibration

The Zeppelin case intentionally uses a validation-only subclass:

```python
class ZeppelinNTAirshipMass(_BaseAirshipMass)
```

The universal `AirshipMass.py` file is not modified.

Two published structural anchors are used:

$$
m_{\rm envelope}\approx1000\ {\rm kg},
$$

$$
m_{\rm framework}\approx1100\ {\rm kg}.
$$

The corresponding validation coefficients are

$$
\boxed{
\sigma_{\rm outer}
=
\frac{1000}{2668.39}
\approx0.37476\ {\rm kg/m^2},
}
\tag{EQ-36}
$$

and

$$
\boxed{
k_{\rm framework,V^{2/3}}
=
\frac{1100}{414.05}
\approx2.657.
}
\tag{EQ-37}
$$

The inner-envelope areal density is set to

$$
\boxed{
0
}
$$

to avoid inventing an additional generic inner-envelope mass for this specific Zeppelin configuration.

The generic framework cap is set to 1.0 so that the published 1100-kg structural anchor is not artificially clipped.

These are clearly **calibration/reference quantities**.

---

## 29. Zeppelin Remaining Bookkeeping

The validation-only Zeppelin mass configuration also uses

$$
\boxed{
f_{\rm misc}=0.085
}
\tag{EQ-38}
$$

and

$$
\boxed{
m_{\rm crew,each}=113\ {\rm kg}.
}
\tag{EQ-39}
$$

The 8.5% miscellaneous value represents the selected validation bookkeeping for other installed systems and should not be interpreted as a universal semi-rigid-airship miscellaneous fraction.

---

## 30. Zeppelin Independent Comparison Quantities

The current driver treats the following as principal comparison quantities:

- MTOM,
- gross volume,
- predicted vehicle/base/OEM quantity,
- component outputs where independent data exist.

Reference values that are unavailable remain `N/A`, including:

- conventional ground-roll datum,
- wetted surface area,
- many component masses.

This is deliberate.

The Zeppelin driver explicitly states that no comparable conventional ground-roll reference was supplied because the Zeppelin uses vectored thrust and can perform very short/vertical takeoff operations.

---

## 31. Zeppelin Base Mass versus “OEM”

The validation should use careful terminology.

The quantity

$$
6150\ {\rm kg}
$$

is derived as

$$
8050-1900.
$$

It should therefore be described as

```text
derived reference base mass
```

rather than automatically as published OEM.

The 6622-kg figure should be described as

```text
secondary published empty mass
```

with its possibly different definition preserved.

The model output remains ADaPT `owe`.

A publication-quality comparison should therefore say:

```text
ADaPT OEM vs derived reference base mass
```

rather than asserting that the source directly publishes an OEM of 6150 kg.

---

## 32. Zeppelin Calibration Does Not Invalidate the Case

Calibration is acceptable if it is transparent.

The Zeppelin case is still useful because it demonstrates:

- correct semi-rigid architecture selection,
- correct geometry coupling,
- correct ballonet/gas-state treatment,
- correct framework mass ownership,
- correct structure-integrated propulsion installation,
- coupled mass closure,
- required power and resource feasibility.

However, calibrated quantities cannot be reused as independent validation evidence.

For example:

$$
m_{\rm framework}\approx1100\ {\rm kg}
$$

is a structural anchor used to determine $k_{\rm framework}$. The resulting 1100-kg model value is therefore not an independent prediction.

---

# Part IV — Broader Multi-Airship Validation

## 33. Why Multiple Airships Are Necessary

One aircraft cannot establish universal validity.

Different structural types exercise different parts of the framework:

| Reference | Structural class | Principal validation value |
|---|---|---|
| A-170 | Non-rigid | Primary-literature integrated design and mass buildup |
| AS700 | Non-rigid | Modern real-aircraft mass/geometry closure |
| AV-10 | Non-rigid | Larger vehicle / high installed-power configuration |
| Zeppelin NT | Semi-rigid | Semi-rigid framework/envelope treatment |
| BASI MB-30T | Rigid | Rigid structure, gas-cell volume, turboelectric capacity |

This provides substantially stronger evidence than tuning one configuration.

---

## 34. AS700 Validation Interpretation

The AS700 validation uses independently documented values including approximately:

- MTOM 4150 kg,
- payload 840 kg,
- non-rigid configuration,
- two Lycoming engines,
- 700-km range class,
- up to ten occupants.

The current validation baseline gives approximately:

$$
m_{\rm MTOM,ADaPT}
\approx4064\ {\rm kg},
$$

which is about

$$
-2.1\%
$$

relative to 4150 kg.

A reference/base mass of approximately 2960 kg has been used in the current study, but this value has not been independently confirmed as a directly published OEM and should therefore be labeled

```text
derived/reference base mass
```

unless a primary source is supplied.

The AS700 case should not be tuned further merely to eliminate the remaining few-percent mass error.

---

## 35. AV-10 Validation Interpretation

The corrected AV-10 validation uses the current ADaPT mass convention and does **not** add helium to OEM/MTOM.

The corrected integrated result is approximately

$$
m_{\rm MTOM}
\approx21.33\ {\rm t}
$$

against a 21.5-t reference, an error of roughly

$$
-0.8\%.
$$

The supplied 11.5-t OEM figure is not mathematically compatible with:

$$
21.5\ {\rm t\ MTOM}
$$

plus

$$
10\ {\rm t\ payload}
$$

while also carrying nonzero fuel.

Therefore the framework should not be tuned to force simultaneous agreement with mutually inconsistent reference numbers.

The validation conclusion should explicitly separate:

- strong MTOM agreement,
- uncertain/inconsistent OEM definition,
- mission/resource feasibility,
- reference-data consistency.

---

## 36. BASI MB-30T Validation Interpretation

The current rigid/turboelectric reference-capacity case gives approximately:

$$
m_{\rm MTOM}
=
60.67\ {\rm t}
$$

against

$$
62.0\ {\rm t},
$$

or approximately

$$
-2.15\%.
$$

The corresponding ADaPT OEM is approximately

$$
30.67\ {\rm t}
$$

against a 32.0-t closure/reference value, approximately

$$
-4.17\%.
$$

These results indicate good **integrated mass closure**.

However, the selected linear framework model

$$
m_{\rm framework}
=
1.5L_{\rm members}
$$

remains a conceptual structural model. The 1.5 kg/m coefficient is not independently validated merely because integrated MTOM agreement improves.

The same BASI case currently predicts approximately

$$
P_{\rm required}
\approx2.696\ {\rm MW}
$$

against

$$
P_{\rm installed}
=
1.560\ {\rm MW},
$$

giving a power shortfall of roughly

$$
1.136\ {\rm MW}.
$$

It also predicts required consumable fuel well above the selected installed reference fuel capacity.

These are **performance/mission-capacity results**, not mass-bookkeeping failures.

They should remain visible until the aerodynamic coefficient/reference convention and the source mission definition are fully reconciled.

---

## 37. Validation Reference-Data Consistency

Reference data must themselves be audited.

A real-aircraft source may contain values that are:

- measured under different missions,
- corresponding to different variants,
- maximum rather than cruise conditions,
- useful-load rather than payload quantities,
- fuel capacity rather than mission fuel,
- ferry range rather than full-payload range.

A validation study must therefore ask:

$$
\boxed{
\text{Are all compared reference quantities from the same aircraft definition and mission?}
}
\tag{EQ-40}
$$

If not, model disagreement may reflect the reference dataset rather than model physics.

---

## 38. Validation Error Is Not the Same as Feasibility

A design may reproduce mass accurately but fail a configured mission.

For example:

$$
|\epsilon_{\rm MTOM}|
\ll 5\%
$$

does not imply

$$
g_P\le0
$$

or

$$
g_E\le0.
$$

Conversely, a vehicle may satisfy all feasibility constraints while exhibiting a noticeable mass-model error.

Therefore reporting should keep two separate blocks:

### A. Validation Accuracy

$$
x_{\rm model}
\leftrightarrow
x_{\rm ref}.
$$

### B. Physical/Mission Feasibility

$$
g_P,\;
g_E,\;
g_B,\;
g_L,\;
g_{TO},\;
g_{\rm landing},\ldots
$$

This separation is essential scientifically.

---

## 39. Constraint Convention

The complete current validation convention is

$$
\boxed{
g\le0
\quad\Rightarrow\quad
\text{feasible}.
}
\tag{EQ-41}
$$

The principal constraints are:

| Constraint | Meaning |
|---|---|
| `power_constraint` | Required shaft power minus installed shaft power |
| `energy_constraint_primary` | Required primary consumable minus installed |
| `energy_constraint_bat` | Required battery mass minus installed |
| `energy_constraint` | Architecture-selected energy/resource constraint |
| `buoyancy_constraint` | Required buoyant lift minus available |
| `lift_constraint` | Required $|C_L|$ minus allowed maximum |
| `ground_constraint` | Total takeoff distance minus field limit |
| `landing_constraint` | Landing field length minus limit |
| `ballast_constraint` | Required ballast minus available |
| `landing_BR_constraint` | Implied landing BR minus selected target |

---

## 40. Validation Tables

A publication-quality table should use the structure:

| Quantity | Role | Reference | ADaPT | Error | Interpretation |
|---|---|---:|---:|---:|---|
| Payload | REQ | value | imposed | – | Mission requirement |
| Length | REF | value | imposed | – | Known geometry |
| Installed power | REF | value | imposed | – | Known installed capacity |
| Framework coefficient | CAL | value | imposed | – | Validation-specific calibration |
| Gross volume | PRED | value | calculated | % | Independent only if not shape-factor fitted |
| OEM/base mass | PRED/DER | value | calculated | % | Definition must be stated |
| MTOM | PRED | value | calculated | % | Whole-vehicle mass closure |
| Required power | PERF | reference if available | calculated | %/N.A. | Mission performance |
| Ground roll | PERF | reference if available | calculated | %/N.A. | Performance |
| Helium mass | N/A/PRED | N/A unless sourced | calculated | N/A | Gas-state diagnostic |

The `Role` and `Interpretation` columns are essential.

---

## 41. CSV Export

Current validation drivers export machine-readable result files.

The recommended columns are:

```text
Category
Role
Parameter
Reference
ADaPT
Units
Percent Error (%)
Interpretation
Source/Provenance
```

The current A-170 driver already includes:

```text
Category
Role
Parameter
Reference
Our Tool
Units
Percent Error (%)
Interpretation
```

and suppresses percent error for prescribed reference inputs.

Each validation driver should also export its variable-role map.

---

## 42. Mass-Breakdown Reporting

For every validation case, print a complete mass buildup including, where active:

- envelope,
- ballonet,
- curtain,
- framework,
- gondola,
- fixed tail,
- control surfaces,
- actuator,
- landing system,
- propulsion,
- power system,
- hydrogen tank,
- conventional fuel-tank hardware,
- pressure system,
- VMS,
- crew,
- miscellaneous,
- margin,
- OEM,
- payload,
- consumable,
- ballast,
- MTOM,
- helium separately.

Where no independent component reference exists, display:

```text
N/A
```

in the reference column.

---

## 43. Geometry Diagnostics

Each integrated validation should report:

- length,
- fineness ratio,
- maximum diameter,
- shape factor,
- gross volume,
- wetted surface area,
- $V^{2/3}$,
- body aspect ratio,
- ballonet capacity,
- takeoff ballonet volume,
- takeoff lifting-gas volume,
- rigid gas-cell total volume where applicable.

These outputs help detect a geometry mismatch before it propagates into mass, buoyancy, or drag.

---

## 44. Propulsion Diagnostics

Each validation should report:

- required shaft power,
- installed shaft power,
- rated shaft power,
- brake power,
- prime-mover mass,
- propeller mass,
- nacelle mass,
- mount/pylon mass,
- wiring mass,
- total propulsion mass,
- propeller diameter,
- advance ratio,
- tip speed.

A reference installed rating remains a `REF` quantity.

---

## 45. Performance Diagnostics

Each validation should report:

- aerodynamic $C_L$,
- drag,
- thrust,
- required shaft power,
- mission speed,
- mission duration,
- mission energy,
- required/available buoyant lift,
- buoyancy constraint,
- calculated takeoff speed,
- ground roll,
- total takeoff distance,
- climb gradient,
- landing distance,
- ballast requirement,
- power constraint,
- energy constraint.

Performance outputs without independent source values remain predictions, not validated quantities.

---

## 46. Do Not Tune Across Structural Classes

Validation/calibration must remain architecture specific.

A calibration derived for:

```text
Zeppelin NT — semi-rigid
```

must not silently modify:

```text
A-170 — non-rigid
AS700 — non-rigid
AV-10 — non-rigid
BASI MB-30T — rigid.
```

Shared physics remains common.

Aircraft-specific calibration remains isolated inside the corresponding validation driver.

This is why the current Zeppelin driver monkeypatches only the validation process rather than changing universal `Airshipmass.py`.

---

## 47. Do Not Tune One Discipline to Hide Another

If a reference case has:

- good MTOM closure,
- but a large power shortfall,

do not change the mass model merely to eliminate the Performance discrepancy.

Similarly:

- do not alter aerodynamics to fix a known mass bookkeeping error;
- do not modify fuel capacity to hide a mission-definition inconsistency;
- do not modify framework mass solely to satisfy a published installed power.

Each discrepancy should be traced to the discipline that physically controls it.

---

## 48. Acceptance Criteria

The validation framework intentionally does **not** impose one universal error threshold such as 5% on every quantity.

Acceptable error depends on:

- fidelity of the submodel,
- uncertainty of the reference data,
- whether the quantity is measured, published, derived, or estimated,
- calibration status,
- expected conceptual-design accuracy,
- sensitivity of downstream conclusions.

A formal criterion should therefore be quantity specific.

For example:

- geometry may reasonably require tighter agreement,
- historical WER component masses may tolerate greater scatter,
- whole-vehicle MTOM may be assessed against a conceptual-design range,
- feasibility constraints use sign rather than percentage error.

---

## 49. Validation Evidence Strength

Validation claims can be ranked qualitatively.

### Strong

Independent source quantity, unambiguous definition, not used for calibration.

### Moderate

Independent source quantity but with known configuration/definition uncertainty.

### Weak

Secondary estimate or derived quantity.

### Calibration

Used directly to set a model coefficient.

### Not Validatable

No independent datum.

This hierarchy should be reflected in publications rather than treating every row equally.

---

## 50. Reproducibility

A validation case is reproducible when it contains:

- explicit reference constants,
- explicit source/provenance,
- architecture selection,
- structural type,
- mass/propulsion method selections,
- all calibration parameters,
- mission definition,
- installed capacities,
- fixed random seed for optional optimization,
- exported comparison table,
- exported variable-role map,
- feasibility constraints.

No hidden hand calculation should be required to recreate the baseline.

---

## 51. Optional Optimization in Validation Drivers

The A-170 and Zeppelin validation files contain optional pymoo studies.

They are disabled by default:

```python
RUN_OPTIMIZATION = False
```

because optimization is not required for baseline validation.

The optional studies vary selected variables such as

$$
BR_{TO},
\quad
C_{HT},
\quad
C_{VT},
\quad
C_L,
\quad
K,
\quad
\eta_p.
$$

They are **parameter/design studies**, not complete clean-sheet airship sizing, because principal geometry variables remain fixed.

Optimization results must therefore be presented after, and separately from, reference validation.

---

## 52. Validation Workflow

The recommended process is

$$
\boxed{
\begin{array}{c}
\text{Primary/reference data}\\
\downarrow\\
\text{Definition and provenance audit}\\
\downarrow\\
\text{Classify REQ / REF / CAL / PRED / DER / N/A}\\
\downarrow\\
\text{Configure structural and propulsion architecture}\\
\downarrow\\
\text{Apply only defensible aircraft-specific calibration}\\
\downarrow\\
\text{Run coupled ADaPT baseline}\\
\downarrow\\
\text{Verify mass and geometry closure}\\
\downarrow\\
\text{Compare independent outputs}\\
\downarrow\\
\text{Report feasibility constraints separately}\\
\downarrow\\
\text{Diagnose discrepancies by discipline}\\
\downarrow\\
\text{Freeze validated baseline}\\
\downarrow\\
\text{only then perform optimization/sensitivity studies}.
\end{array}
}
\tag{EQ-42}
$$

---

## 53. What Validation Demonstrates

A successful integrated comparison demonstrates that:

- the subsystem equations can operate together,
- the data interfaces are consistent,
- the mass/energy/propulsion coupling closes,
- the selected structural architecture is handled correctly,
- the framework reproduces independent aircraft-level quantities within conceptual accuracy,
- mission feasibility can be assessed using the known installed capacity.

This is genuine multidisciplinary validation evidence.

---

## 54. What Validation Does Not Demonstrate

Even excellent whole-aircraft agreement does not prove that every submodel is universally accurate.

A validation case does not independently establish:

- universal aerodynamic coefficients,
- universal framework coefficients,
- universal envelope areal density,
- universal nacelle mass coefficients,
- universal propeller efficiency,
- universal takeoff friction,
- universal battery/fuel-cell/tank assumptions.

Whole-vehicle agreement may contain compensating errors.

Therefore component-level provenance and verification remain necessary.

---

## 55. Recommended Publication Structure

A validation section in a paper or thesis should proceed in this order:

1. State the validation objective.
2. Define the reference aircraft and source data.
3. State structural and propulsion architecture.
4. Classify every reference quantity as REQ/REF/CAL/PRED/DER/N/A.
5. Describe aircraft-specific calibration separately.
6. Run the baseline without optimization.
7. Present geometry/component mass validation.
8. Present integrated OEM/base-mass and MTOM comparison.
9. Present power/resource/performance feasibility separately.
10. Discuss source-data inconsistencies and unavailable data.
11. Freeze the reference baseline.
12. Present optional optimization or design-space exploration only afterward.

This prevents calibration, validation, feasibility, and design optimization from becoming mixed together.

---

## 56. Recommended Multi-Airship Summary Table

A high-level summary can use:

| Aircraft | Structure | Architecture | Key independent comparison | Calibration caveat | Main unresolved issue |
|---|---|---|---|---|---|
| A-170 | Non-rigid | Conventional reciprocating | Geometry, component buildup, MTOM, ground roll | Some actual subsystem masses prescribed | Distinguish conceptual vs actual breakdown |
| AS700 | Non-rigid | Conventional reciprocating | MTOM/base mass | Some geometry/installation assumptions | Published OEM definition |
| AV-10 | Non-rigid | Reference conventional | MTOM | Reference-data consistency | Supplied OEM vs payload/fuel closure |
| Zeppelin NT | Semi-rigid | Conventional reciprocating | MTOM/base mass/geometry | Envelope and framework calibrated to published anchors | Empty/base-mass definition |
| BASI MB-30T | Rigid | Turboelectric | MTOM/OEM closure | Framework model remains conceptual | Power/fuel mission-capacity discrepancy |

This is more scientifically useful than presenting one overall “validation error.”

---

## 57. Software Traceability

| Validation concept | Current implementation |
|---|---|
| Analysis-mode explanation | Driver header documentation |
| Variable-role registry | `VARIABLE_ROLE_MAP` |
| Reference values | Explicit constants/dictionaries |
| Reference setup | `Problem.set_val()` after `setup()` |
| Central IV ownership | `AirshipAnalysisGroup` internal independent variables |
| Constraint convention | `g <= 0` |
| Safe scalar extraction | `_get`, `_max_value` |
| Optional inactive-variable handling | `_set_if_present` |
| Reference comparison | `run_validation_and_print()` |
| Role-aware error | Error suppressed for `REF` |
| CSV export | Validation result table |
| Role export | `export_variable_role_map()` |
| Optional optimization | pymoo DE, disabled by default |
| XDSM | Optional, disabled by default |
| Architecture-specific calibration | Isolated validation subclass/driver |

---

## 58. Current Corrections Relative to the Previous Validation Guide

The previous `validation(1).md` is no longer authoritative because several important assumptions have changed.

The principal corrections are:

1. Validation is no longer documented as a Zeppelin-only methodology; A-170 is now a primary literature/integrated validation case.
2. Zeppelin `1900 kg` is **useful/loading capacity**, not payload.
3. The current Zeppelin payload split is:
   $$
   800\ {\rm kg\ payload}
   +
   1100\ {\rm kg\ fuel}.
   $$
4. The primary Zeppelin comparison mass is:
   $$
   6150\ {\rm kg}
   =
   8050-1900,
   $$
   labeled derived reference base mass.
5. The previous 5065-kg Zeppelin OEM value is obsolete and should not be used.
6. The secondary 6622-kg empty-mass datum is retained separately.
7. Current Zeppelin structural calibration is:
   $$
   \sigma_{\rm outer}\approx0.37476\ {\rm kg/m^2},
   $$
   not 0.77 kg/m².
8. Zeppelin inner-envelope density is 0, not 0.10 kg/m².
9. Zeppelin framework coefficient is approximately 2.657, not 0.35.
10. Zeppelin miscellaneous fraction is 0.085, not 0.023.
11. Helium is excluded from ADaPT OEM/MTOM.
12. `ground_roll_distance` in the current Performance model means ground roll only.
13. Validation tables now need an explicit role field.
14. Percent error should not be reported for prescribed reference inputs.
15. Geometry shape-factor and prescribed-ballonet calibration must be identified explicitly.
16. Mass accuracy and mission feasibility must be reported separately.

These are substantive methodology updates rather than editorial changes.

---

## 59. Provenance Labels

For consistency with the component Theory Guides, validation may also use:

| Label | Meaning |
|---|---|
| **F** | Fundamental relationship |
| **L** | Literature relationship/data |
| **A** | Adapted literature relation |
| **E** | Empirical relationship |
| **AS** | Modeling assumption |
| **N** | Numerical safeguard |
| **D** | Derived quantity |
| **C** | Calibration/reference parameter |

These provenance labels describe the **source/status of the equation or parameter**.

They complement, rather than replace, the validation-role labels:

```text
REQ / REF / CAL / PRED / COUP / PERF / DER / N/A.
```

For example:

```text
Zeppelin framework coefficient:
Validation role = CAL
Provenance = C / L-derived anchor
```

while

```text
Zeppelin MTOM:
Validation role = PRED
Reference provenance = PUB/L
```

---

## 60. Final Validation Principle

The governing interpretation rule is

$$
\boxed{
\text{the engineering role of a variable depends on the analysis boundary.}
}
\tag{EQ-43}
$$

and the governing validation rule is

$$
\boxed{
\text{Only independently predicted quantities provide independent validation evidence.}
}
\tag{EQ-44}
$$

Prescribed inputs document the reference configuration.

Calibration parameters anchor uncertain model terms.

Coupling variables close the MDAO system.

Predicted quantities test the framework.

Feasibility constraints test whether the configured vehicle can satisfy the selected mission.

Keeping these categories separate is what makes the ADaPT validation scientifically interpretable and reproducible.

---

## 61. References

[1] G. E. Carichner and L. M. Nicolai, *Fundamentals of Aircraft and Airship Design, Volume 2—Airship Design and Case Studies*, AIAA Education Series, American Institute of Aeronautics and Astronautics, Reston, VA, 2013.



---

```
