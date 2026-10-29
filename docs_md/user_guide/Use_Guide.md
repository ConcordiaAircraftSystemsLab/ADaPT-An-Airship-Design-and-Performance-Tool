# How to use ADaPT 

**ADaPT** — an OpenMDAO-based multidisciplinary framework for conceptual airship design, analysis, sizing, and optimization.

This notebook compiles the ADaPT user documentation into a single, readable reference, in the recommended reading order.

## Contents

1. [1. ADaPT Fundamentals](#adapt-fundamentals)
2. [2. How ADaPT Works](#how-adapt-works)
3. [3. Analysis Modes](#analysis-modes)
4. [4. Variables](#variables)
5. [5. Airship Definition](#Airship-definition)
6. [6. Mission Definition](#mission-definition)
7. [7. Propulsion Architectures](#propulsion-architectures)
8. [8. Input Files](#input-files)
9. [9. Running ADaPT](#running-adapt)
10. [10. Optimization](#optimization)
11. [11. Interpreting Outputs](#interpreting-outputs)

---

---
# 1. ADaPT Fundamentals

# ADaPT Fundamentals

> **NOTE**
>
> Purpose of this page  This page introduces the concepts a user should understand before running ADaPT. It explains what the framework does, the different ways it can be used, and the distinction between **mission requirements**, **vehicle design variables**, **component inputs and outputs**, **multidisciplinary coupling variables**, and **final sizing results**.

## 1. What is ADaPT?

**ADaPT** is an OpenMDAO-based multidisciplinary framework for
conceptual airship design, analysis, sizing, and optimization. It
combines the principal disciplines needed to evaluate an airship as an
integrated vehicle:

-   geometry;
-   atmospheric and operating conditions;
-   structural and vehicle mass estimation;
-   buoyancy and aerodynamic performance;
-   propulsion sizing;
-   power conversion;
-   conventional fuel and hydrogen requirements;
-   battery energy storage;
-   solar-power integration;
-   fuel-cell performance;
-   hydrogen storage;
-   takeoff, landing, and mission feasibility;
-   design-space exploration and optimization.

A user may ask three fundamentally different questions:

> **Can ADaPT reproduce the characteristics of an existing airship?**

> **How will a specified airship perform on a mission?**

> **What airship should be designed to satisfy a specified payload and
> range?**

These correspond to different analysis modes.

## 2. Three Main Analysis Modes

$$
\boxed{\text{Validation}\qquad\text{Forward Mission Analysis}\qquad\text{Clean-Sheet Sizing / Optimization}}
$$

### 2.1 Reference-Airship Validation

Validation starts with an existing airship for which reference data are
known. Published quantities such as length, diameter/fineness ratio,
payload, installed power, fuel capacity, cruise speed, altitude, and
range may deliberately be prescribed.

The workflow is

$$
\boxed{\text{Reference Airship}\rightarrow\text{known reference inputs}\rightarrow\text{ADaPT}\rightarrow\text{predictions}\rightarrow\text{comparison}}
$$

The purpose is to test whether ADaPT reproduces independently known
quantities. A value that is imposed from the reference Airship should
not itself be presented as an independently predicted validation output.

> **IMPORTANT**
>
> Validation asks **“Does the model reproduce a known Airship?”** It does not ask **“What Airship should be designed from scratch?”**


### 2.2 Forward Mission Analysis

Here the vehicle is already defined. The user supplies the Airship and
mission, and ADaPT predicts mission performance:

$$
\boxed{\text{Fixed airship}+\text{specified mission}\rightarrow\text{ADaPT}\rightarrow\text{performance/resource use/feasibility}}
$$

Typical results include required power, mission duration, fuel or
hydrogen use, battery energy, solar contribution, takeoff/landing
performance, and feasibility margins.

### 2.3 Clean-Sheet Sizing and Optimization

In clean-sheet sizing, the user mainly defines **what the Airship must
accomplish**, not its final dimensions.

Typical requirements are

$$
\boxed{m_{\rm payload},\;R,\;h_{\rm cruise},\;V_{\rm cruise},\;\text{propulsion architecture}}
$$

while candidate design variables may include

$$
\boxed{L,\;FR,\;BR,\;C_{HT},\;C_{VT},\;P_{\rm installed},\ldots}
$$

The optimizer changes candidate design variables, ADaPT evaluates the
resulting vehicle, and constraints determine feasibility.

$$
\boxed{\text{requirements}\rightarrow\text{candidate design}\rightarrow\text{ADaPT}\rightarrow\text{objectives/constraints}\rightarrow\text{design update}}
$$

The converged geometry and subsystem capacities are therefore **sizing
results**, even when they are inputs to individual components.

## 3. The Most Important Input/Output Concept

$$
\boxed{\text{component input}\neq\text{system-level requirement}}
$$

OpenMDAO uses **input** and **output** to describe data flow between
components. Those words do not by themselves say whether a quantity is a
mission requirement, design variable, reference value, coupling
variable, or final sizing result.

The role must always be interpreted at the appropriate analysis
boundary.

## 4. Example: Why Length Is an Input

The Geometry component requires a candidate length (L) to construct a
candidate hull. For example,

$$ D=\frac{L}{FR}, $$

after which geometry determines quantities such as

$$
V_{\rm gross},\quad S_{\rm wet},\quad S_{\rm ref},\quad S_{\rm fin}.
$$

Therefore, at the Geometry-component boundary,

$$ \boxed{L=\text{input}.} $$

During clean-sheet optimization, however, (L=L_k) is simply the current
candidate proposed by the optimizer. After the complete vehicle is
evaluated, the optimizer proposes (L_{k+1}). After convergence,

$$ \boxed{L^*=\text{final sizing result}.} $$

  Analysis boundary               Role of `length`
  ------------------------------- ------------------------------
  Geometry component              Input
  Reference-Airship validation   Known reference input
  Forward analysis                Fixed vehicle characteristic
  Clean-sheet sizing              Design variable
  Final design report             Sizing result

There is no contradiction between these descriptions.

## 5. Example: Why MTOW Is Both an Output and an Input

The Weight component calculates (MTOW), so

$$ \boxed{MTOW=\text{Weight output}.} $$

Performance requires vehicle mass, so

$$ \boxed{MTOW=\text{Performance input}.} $$

At full-system level,

$$
\boxed{MTOW=\text{coupling variable and final vehicle result}.}
$$

Thus input/output terminology is always relative to a component.

## 6. ADaPT Variable Roles

### Mission requirement

What the vehicle must accomplish, e.g. payload and range.

### Operating condition

The environment/condition at which it is evaluated, e.g. altitude,
speed, DISA.

### System-level design variable

A vehicle quantity deliberately varied during sizing or optimization,
e.g. (L,FR,BR,C_{HT},C_{VT}).

### Reference input

A known quantity imposed because a reference Airship is being
validated.

### Component input/output

A variable entering or calculated by one OpenMDAO component.

### Coupling variable

An output from one discipline that becomes an input to another,
e.g. (V_{\rm gross}), (MTOW), or required shaft power.

### Installed capacity

Available capability, e.g. installed shaft power or installed
energy/fuel capacity.

### Required capacity

Capability demanded by the mission.

### Sizing result

A final vehicle characteristic obtained after multidisciplinary closure
or optimization.

## 7. Variable-Role Examples


| Variable | Typical component role | Typical clean-sheet system role |
| --- | --- | --- |
| `payload` | Weight/Performance input | Mission requirement |
| `range` | Mission/Performance input | Mission requirement |
| `cruise_altp` | Atmosphere/Performance input | Operating requirement |
| `cruise_speed` | Performance input | Operating requirement or design variable |
| `length` | Geometry input | Design variable / final size |
| `fineness_ratio` | Geometry input | Design variable |
| `gross_volume` | Geometry output | Coupling variable / result |
| `mtow` | Weight output; Performance input | Coupling variable / sizing result |
| `required_shaft_power` | Performance output | Coupling variable |
| `installed_shaft_power` | Propulsion/Performance input | Installed capacity / design variable |
| fuel/H₂/battery requirement | Energy-system output | Resource sizing result |

## 8. Requirements, Candidate Design, and Results

A useful mental model has three layers.

**Layer A --- What must the vehicle do?**

$$
\boxed{\text{payload}+\text{range}+\text{operating requirements}}
$$

**Layer B --- What candidate vehicle is being tested?**

$$
\boxed{\text{geometry}+\text{propulsion}+\text{energy technology}+\text{configuration}}
$$

**Layer C --- What does ADaPT calculate?**

$$
\boxed{\text{volume}+\text{mass}+\text{power}+\text{energy}+\text{performance}+\text{feasibility}}
$$

An optimizer normally changes Layer B while Layer A remains fixed.

## 9. Architecture-Dependent Analysis

ADaPT supports architecture-dependent analysis including conventional
reciprocating, hydrogen reciprocating, hydrogen fuel-cell,
battery-electric, solar-battery, hydrogen-hybrid, solar-hydrogen-hybrid,
conventional-battery-hybrid, turboprop, and turboelectric
configurations.

Different architectures activate different conversion and storage paths.
For example:

``` text
Conventional:
Performance -> Propulsion -> combustion power conversion -> fuel requirement

Battery electric:
Performance -> Propulsion -> electrical demand -> BatteryOnly

Hydrogen fuel cell:
Performance -> Propulsion -> electrical demand -> fuel-cell conversion -> H2 requirement -> Tank
```

The architecture therefore changes both the equations and the
mass-energy coupling.

## 10. Required versus Installed Capability

ADaPT distinguishes mission demand from installed capability.

$$ g_P=P_{\rm required}-P_{\rm installed} $$

and similarly for fuel, hydrogen, or battery capacity.

The general feasibility convention is

$$ \boxed{g_i\le0\Rightarrow\text{feasible}.} $$

A positive value indicates a violated requirement.

## 11. Analysis versus Optimization

One analysis evaluates one candidate:

$$
\boxed{\mathbf{x}\rightarrow\text{ADaPT}\rightarrow\mathbf{y}.}
$$

Optimization evaluates many candidates:

$$
\boxed{\mathbf{x}_k\rightarrow\text{ADaPT}\rightarrow f_k,\mathbf{g}_k\rightarrow\mathbf{x}_{k+1}.}
$$

ADaPT can use OpenMDAO-based optimization or external search through
pymoo while retaining the same physical model.

## 12. Analysis, Solver, and Optimizer

-   **Analysis model:** evaluates the physics of a candidate design.
-   **Solver:** closes coupled mathematical equations/residuals.
-   **Optimizer:** changes system-level design variables to improve an
    objective subject to constraints.

$$
\boxed{\text{solver closes the analysis; optimizer changes the design}.}
$$

## 13. Units

ADaPT uses OpenMDAO's unit-aware variable system. Explicit units are
recommended:

``` python
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1.0e6, units="m")
prob.set_val("cruise_altp", 1000.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")
```

## 14. Before Running ADaPT

A user should first decide:

1.  Is the study validation, forward mission analysis, sizing,
    optimization, sensitivity analysis, or DSE?
2.  Which quantities are fixed?
3.  Which quantities are allowed to vary?
4.  Which propulsion architecture is being evaluated?
5.  Which technology assumptions apply?
6.  Which outputs/objectives matter?
7.  Which constraints determine feasibility?

## 15. Recommended Reading Order

After this page:

1.  **How ADaPT Works** (section 2 below)
2.  Analysis Modes
3.  Variables
4.  Airship Definition
5.  Mission Definition
6.  Propulsion Architectures
7.  Running ADaPT
8.  Optimization
9.  Interpreting Outputs

Use the **Theory Guide** for equations, assumptions, provenance,
safeguards, and component-level validation.

## 16. Key Takeaways

$$
\boxed{\text{ADaPT is a multidisciplinary vehicle framework, not a single sizing equation.}}
$$

$$
\boxed{\text{component input/output describes data flow, not the overall design role.}}
$$

$$
\boxed{\text{payload and range can be requirements while length is a design variable.}}
$$

$$
\boxed{\text{a design variable becomes a sizing result after convergence.}}
$$

$$
\boxed{\text{validation, forward analysis, and clean-sheet sizing use the same physics differently.}}
$$

---
# 2. How ADaPT Works

# How ADaPT Works

> **NOTE**
>
> Purpose of this page  This page explains how user-defined requirements and candidate vehicle variables enter ADaPT, how multidisciplinary components exchange information, how architecture-dependent subsystems are activated, and how vehicle and mission outputs are produced.

## 1. Framework Overview

ADaPT evaluates an airship by combining coupled disciplines inside an
OpenMDAO system model.

$$
\boxed{\text{Requirements}+\text{Candidate Design}+\text{Technology Assumptions}\rightarrow\text{ADaPT}\rightarrow\text{Vehicle + Mission Results}}
$$

The framework is multidisciplinary because geometry, mass, performance,
propulsion, and energy systems cannot generally be determined
independently.

For example:

-   geometry determines volume and area;
-   volume affects buoyancy and structural mass;
-   mass affects lift and propulsion requirements;
-   propulsion power determines mission energy;
-   the energy system has mass;
-   that mass changes vehicle mass and therefore performance again.

This produces the central **energy--mass--propulsion coupling loop**.

## 2. Top-Level OpenMDAO Organization

The principal system model is assembled through `AirshipAnalysisGroup`.

Conceptually:

``` text
OpenMDAO Problem
└── AirshipAnalysisGroup
    ├── Independent/design variables
    ├── Geometry
    ├── Atmosphere / operating conditions
    ├── Weight
    ├── Performance
    ├── Propulsion
    ├── Power
    ├── Architecture-dependent energy subsystem(s)
    └── Constraints / diagnostics
```

The exact active subsystem chain depends on the selected architecture.

## 3. Information Entering ADaPT

### Mission requirements

Examples:

$$
m_{\rm payload},\quad R,\quad h_{\rm cruise},\quad V_{\rm cruise}.
$$

### Candidate vehicle definition

Examples:

$$
L,\quad FR,\quad BR,\quad C_{HT},\quad C_{VT}.
$$

These may be fixed in forward analysis or varied during optimization.

### Architecture definition

The propulsion/energy architecture determines which subsystem models
participate.

### Technology assumptions

Examples include propeller efficiency, engine/motor specific power,
thermal efficiency, battery specific energy, fuel-cell performance,
solar efficiency, and hydrogen-storage assumptions.

## 4. Component Inputs Are Not Necessarily User Inputs

A coupling variable such as `gross_volume` may be an input to downstream
components but is calculated by Geometry.

Therefore,

$$
\boxed{\text{user-level input}\neq\text{every OpenMDAO component input}.}
$$

OpenMDAO automatically transfers coupling quantities between connected
disciplines.

## 5. Geometry Stage

Geometry receives candidate hull parameters such as (L) and (FR).

$$ D=\frac{L}{FR} $$

and the model determines quantities such as gross volume, wetted area,
reference area, tail areas, ballonet volume, and architecture-dependent
structural geometry proxies.

$$
\boxed{L,FR,C_{HT},C_{VT},\ldots\rightarrow\text{Geometry}\rightarrow D,V,S_{\rm wet},S_{\rm fin},\ldots}
$$

These outputs feed Weight and Performance.

## 6. Atmosphere and Operating Conditions

The atmosphere model converts altitude and temperature deviation into
environmental properties:

$$
\boxed{h,\Delta T\rightarrow\text{Atmosphere}\rightarrow T,p,\rho,\mu,\ldots}
$$

Density affects buoyancy, aerodynamic forces, propulsion/propeller
calculations, and overall performance.

## 7. Weight Stage

Weight receives geometry and installed-system information and assembles
vehicle mass.

Contributions include envelope, fins, gondola, framework where
applicable, propulsion, power system, tank, crew, landing system,
miscellaneous mass, and helium.

It produces

$$ OEW $$

and

$$ MTOW. $$

$$
\boxed{\text{Geometry}+\text{installed systems}+\text{payload/resources}\rightarrow\text{Weight}\rightarrow OEW,MTOW,\ldots}
$$

MTOW then becomes an input to Performance.

## 8. Performance Stage

Performance combines vehicle mass, geometry, atmosphere, speed,
aerodynamic assumptions, and buoyancy ratio.

It calculates buoyant/aerodynamic lift, drag, thrust, required shaft
power, mission duration, takeoff and landing performance, and other
mission metrics.

A simplified cruise chain is

$$
\boxed{MTOW+V+\text{geometry}+\rho\rightarrow D_{\rm aero}\rightarrow T_{\rm required}\rightarrow P_{\rm shaft,required}.}
$$

Required shaft power is a key coupling variable.

## 9. Propulsion Stage

Propulsion receives mechanical demand from Performance.

For propeller-driven systems,

$$ P_{\rm shaft}=\frac{TV}{\eta_p}. $$

It determines required/rated propulsion quantities and estimates
propulsion-system mass, which can include prime mover/motor, propeller,
nacelle, mounts, and wiring depending on architecture.

The propulsion mass returns to Weight.

## 10. Power Conversion Stage

Power translates propulsion demand into architecture-dependent source
demand.

### Combustion

$$
P_{\rm shaft}\rightarrow P_{\rm brake}\rightarrow\dot m_{\rm fuel}.
$$

### Fuel-cell/electric

$$
P_{\rm shaft}\rightarrow P_{\rm electrical}\rightarrow P_{\rm FC}\rightarrow\dot m_{H_2}.
$$

### Battery

$$
P_{\rm shaft}\rightarrow P_{\rm electrical}\rightarrow P_{\rm battery}.
$$

### Solar/hybrid

Electrical demand is allocated among solar, battery, fuel-cell, or
combustion sources according to the selected architecture.

## 11. Energy and Resource Subsystems

### Battery-only

$$
P_{\rm battery}(t)\rightarrow E_{\rm mission}\rightarrow E_{\rm battery}\rightarrow m_{\rm battery},V_{\rm battery}.
$$

### Solar-battery

$$
P_{\rm load}(t)-P_{\rm solar,used}(t)\rightarrow P_{\rm battery}(t)\rightarrow E_{\rm battery}.
$$

PV area and areal density also determine panel mass.

### Hydrogen

$$
\dot m_{H_2}(t)\rightarrow m_{H_2,\rm required}\rightarrow\text{Tank}\rightarrow m_{\rm tank},V_{\rm tank}.
$$

### Fuel-cell polarization

Where used, the PEMFC model supplies load-dependent voltage, efficiency,
hydrogen-flow diagnostics, and power capability.

## 12. Energy--Mass--Propulsion Coupling

The central loop is

$$
\boxed{m\rightarrow D,T\rightarrow P\rightarrow E\rightarrow m_{\rm energy\ system}\rightarrow m.}
$$

Geometry participates simultaneously:

$$
\boxed{L,FR\rightarrow V,S\rightarrow\text{buoyancy + drag + structural mass}\rightarrow MTOW\rightarrow P\rightarrow E\rightarrow MTOW.}
$$

This is why geometry, propulsion, and energy storage cannot generally be
sized independently.

## 13. Architecture-Dependent Execution

Not every run activates every subsystem.

``` text
Conventional reciprocating:
Performance -> Propulsion -> Power/combustion -> fuel requirement

Battery electric:
Performance -> Propulsion -> electrical demand -> BatteryOnly

Solar battery:
Performance -> Propulsion -> electrical demand -> SolarBattery
                                                ├─ PV contribution
                                                └─ battery requirement

Hydrogen fuel cell:
Performance -> Propulsion -> Power/fuel cell -> H2 flow -> Tank
```

Turboprop and turboelectric configurations use dedicated architecture
components and mass-ownership boundaries.

## 14. Mass Ownership

Avoiding double counting is essential.


| Quantity | Authoritative model |
| --- | --- |
| Hull/vehicle structural buildup | Weight |
| Mechanical propulsion hardware | Propulsion or dedicated turbine architecture |
| Conversion-system hardware | Power or dedicated architecture |
| Battery pack | BatteryOnly / SolarBattery |
| PV panels in standard solar-battery architecture | SolarBattery |
| Hydrogen tank | Tank |
| Hydrogen inventory | Mission power/fuel-flow chain integrated by Tank |


Weight receives subsystem masses and assembles vehicle-level closure
instead of independently recalculating them.

## 15. Required versus Installed Closure

For power,

$$ g_P=P_{\rm required}-P_{\rm installed}. $$

For a resource,

$$ g_E=R_{\rm required}-R_{\rm installed}. $$

The framework convention is

$$ \boxed{g\le0\Rightarrow\text{feasible}.} $$

## 16. Vehicle-Level Outputs

### Geometry

Length, diameter, volume, wetted/reference area, tail geometry.

### Mass

Component masses, helium mass, OEW, MTOW.

### Propulsion and power

Required/rated power, propulsion mass, power-system mass.

### Energy/resources

Fuel, hydrogen, battery capacity/mass, solar contribution, tank
mass/volume.

### Performance

Drag, lift, buoyancy, mission duration, takeoff/landing and other
performance quantities.

### Feasibility

Power, energy, buoyancy, lift, takeoff, and landing constraints.

## 17. Running One Analysis

A schematic workflow is:

``` python
import openmdao.api as om

prob = om.Problem()

# Add/configure AirshipAnalysisGroup here.

prob.setup()

# Mission requirements
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1.0e6, units="m")
prob.set_val("cruise_altp", 1000.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")

# Candidate vehicle
prob.set_val("length", 60.0, units="m")
prob.set_val("fineness_ratio", 4.5)

prob.run_model()
```

`` {important} This illustrates the workflow. Exact constructor options and variables depend on the selected architecture and current `AirshipAnalysisGroup` configuration. ``

## 18. Reading Results

Results can be queried after execution, for example:

``` python
mtow = prob.get_val("mtow", units="kg")
volume = prob.get_val("gross_volume", units="m**3")
```

Users should inspect constraints as well as headline results. A low-MTOW
candidate is not a feasible design if a required constraint is positive.

## 19. From Analysis to Optimization

One execution evaluates one candidate. Optimization adds an outer loop:

$$
\boxed{\mathbf{x}_k\rightarrow\text{ADaPT}\rightarrow f_k,\mathbf{g}_k\rightarrow\mathbf{x}_{k+1}.}
$$

Two complementary routes are supported:

``` text
                ADaPT physics
                     │
          ┌──────────┴──────────┐
          │                     │
   OpenMDAO driver          pymoo wrapper
          │                     │
 gradient/local search    population/global search
```

The physical model is unchanged.

## 20. From Analysis to Design-Space Exploration

DSE evaluates many candidates:

$$
{\mathbf{x}_1,\ldots,\mathbf{x}_N}\rightarrow\text{ADaPT}\rightarrow{\mathbf{y}_1,\ldots,\mathbf{y}_N}.
$$

It is useful for identifying feasible regions, architecture-dependent
behavior, sensitivities, nonlinear trends, Pareto structure, and
technology thresholds.

## 21. Validation Uses the Same Components Differently

In validation, quantities that could be design variables in clean-sheet
sizing may instead be fixed to known reference values.

``` text
Clean-sheet sizing:
    length -> design variable -> final sizing result

Reference validation:
    length -> known reference value -> fixed
```

The downstream physics is still evaluated normally.

## 22. Complete Conceptual Data Flow

``` text
USER / STUDY DEFINITION
│
├── Mission requirements
│   ├── payload
│   ├── range
│   ├── altitude
│   └── speed
├── Candidate design / design variables
│   ├── length
│   ├── fineness ratio
│   ├── buoyancy ratio
│   └── tail/configuration parameters
├── Architecture
└── Technology assumptions
            │
            ▼
        GEOMETRY
            │
            ▼
   ATMOSPHERE / OPERATING STATE
            │
            ▼
          WEIGHT ◄───────────────────────────┐
            │                                │
            ▼                                │
        PERFORMANCE                          │
            │                                │
            ├── drag/thrust                  │
            ├── required shaft power         │
            └── mission duration             │
            ▼                                │
        PROPULSION                           │
            └── propulsion mass ─────────────┤
            ▼                                │
           POWER                             │
            ├── source demand                │
            ├── fuel/H2 flow                 │
            └── conversion mass ─────────────┤
            ▼                                │
   ENERGY / STORAGE SUBSYSTEM                │
            ├── resource requirement         │
            └── tank/battery/PV mass ────────┘
            ▼
       FEASIBILITY
            ▼
      VEHICLE RESULTS
```

This is a conceptual dependency map; exact execution and active
components depend on architecture and coupling configuration.

## 23. Why Multidisciplinary Closure Matters

If battery specific energy decreases,

$$ SE_b\downarrow\Rightarrow m_b\uparrow
\Rightarrow MTOW\uparrow
\Rightarrow P_{\rm required}\uparrow
\Rightarrow E_{\rm required}\uparrow
\Rightarrow m_b\uparrow. $$

Similarly, increasing hull size can improve buoyancy while also
increasing wetted area and structural mass.

The integrated framework captures these competing effects.

## 24. Numerical Safeguards versus Physical Constraints

Component safeguards such as minimum values, clipping, or bounded
empirical relations protect the numerical calculation.

They are not equivalent to physical feasibility constraints.

``` text
Numerical safeguard -> prevents invalid numerical states.
Physical constraint  -> determines whether the design satisfies a requirement.
```

Optimized designs should be checked to ensure apparent feasibility is
not created by an active numerical floor or clip.

## 25. What OpenMDAO Provides

OpenMDAO provides the infrastructure for:

-   component input/output definitions;
-   unit handling;
-   promotion and connections;
-   derivative calculation/approximation;
-   nonlinear and linear solvers;
-   optimization drivers;
-   recording and diagnostics.

ADaPT supplies the airship-specific physics and architecture logic.

## 26. What pymoo Provides

pymoo can provide an external optimization layer:

$$
\boxed{\text{pymoo}\rightarrow\text{candidate design}\rightarrow\text{OpenMDAO/ADaPT}\rightarrow\text{objective + constraints}\rightarrow\text{pymoo}.}
$$

It does not replace the ADaPT physical model.

## 27. Recommended User Workflow

1.  Define the engineering question.
2.  Select the propulsion/energy architecture.
3.  Define fixed mission requirements.
4.  Define the candidate vehicle or design variables.
5.  Define technology assumptions.
6.  Run the multidisciplinary model.
7.  Inspect geometry, mass, propulsion, energy, and performance outputs.
8.  Confirm all required constraints satisfy (g_i\le0).
9.  Verify that results are physically meaningful and not dominated by
    numerical safeguards.

## 28. Where to Go Next

Continue with:

-   **Analysis Modes**
-   **Variables**
-   **Airship Definition**
-   **Mission Definition**
-   **Propulsion Architectures**
-   **Running ADaPT**
-   **Optimization**
-   **Interpreting Outputs**

Use the **Theory Guide** for governing equations, assumptions, numerical
safeguards, provenance, and component-level verification/validation.

## 29. Summary

ADaPT propagates a candidate airship through a connected
multidisciplinary analysis:

$$
\boxed{\text{geometry}\rightarrow\text{mass}\rightarrow\text{performance}\rightarrow\text{power}\rightarrow\text{energy/resource mass}\rightarrow\text{mass}.}
$$

Mission requirements define what the Airship must accomplish. Design
variables define the candidate Airship. Coupling variables communicate
information between disciplines. Their interaction determines vehicle
mass, power, energy, performance, and feasibility.

The same framework can therefore be used to **validate an existing
airship**, **analyze a defined mission**, or **size and optimize a new
airship**. The analysis mode determines which quantities are fixed,
calculated, or allowed to vary.

---
# 3. Analysis Modes

# Analysis Modes

> **NOTE**
>
> Purpose of this page  ADaPT uses the same multidisciplinary physics in several different ways. This page explains the principal analysis modes and, for each mode, identifies **what the user specifies**, **what ADaPT calculates**, **what may be varied**, and **how the results should be interpreted**.

## 1. Why Analysis Mode Matters

Before running ADaPT, the user should first decide what engineering
question is being asked.

The three principal modes are

$$ \boxed{
\text{Reference-Airship Validation}
\qquad
\text{Forward Mission Analysis}
\qquad
\text{Clean-Sheet Sizing / Optimization}
} $$

Additional studies such as design-space exploration, sensitivity
analysis, technology assessment, and payload--range analysis are built
on these basic modes.

The physical components may be identical, but the **system-level role of
a variable changes with the analysis mode**.

For example, airship length (L) may be:

-   a known reference value during validation;
-   a fixed vehicle characteristic during mission analysis;
-   a design variable during clean-sheet sizing;
-   a reported sizing result after optimization.

Therefore, the analysis mode should always be stated before inputs and
outputs are interpreted.

------------------------------------------------------------------------

## 2. Mode 1 --- Reference-Airship Validation

### 2.1 Engineering question

Validation asks

$$ \boxed{
\text{Can ADaPT reproduce independently known characteristics of an existing airship?}
} $$

The objective is not to redesign the reference Airship.

Instead, published or otherwise established Airship characteristics are
used to define the reference configuration.

### 2.2 What the user specifies

Depending on data availability, reference inputs may include:

-   airship type;
-   length;
-   diameter or fineness ratio;
-   payload;
-   number of engines;
-   crew;
-   installed shaft power;
-   installed fuel/resource capacity;
-   cruise speed;
-   cruise altitude;
-   mission range;
-   known configuration parameters.

These are fixed because the reference Airship already exists.

### 2.3 What ADaPT calculates

The framework then predicts quantities that follow from the imposed
reference configuration, for example:

-   gross volume;
-   wetted area;
-   aerodynamic reference quantities;
-   component mass buildup;
-   helium mass;
-   OEW;
-   MTOW;
-   required shaft power;
-   mission duration;
-   takeoff/landing performance;
-   feasibility margins.

Where independent reference values exist, predicted quantities can be
compared quantitatively.

### 2.4 Validation data flow

``` text
Published / reference Airship data
                │
                ▼
       Prescribed reference inputs
                │
                ▼
              ADaPT
                │
       ┌────────┴────────┐
       ▼                 ▼
 predicted outputs   feasibility
       │
       ▼
 independent reference comparison
       │
       ▼
 error / agreement assessment
```

### 2.5 Prescribed values are not predictions

If the reference length is explicitly supplied,

$$ L=L_{\mathrm{ref}}, $$

then agreement in length is not independent validation.

Likewise, if installed shaft power is prescribed from the reference
Airship, that quantity documents the reference configuration but does
not demonstrate predictive accuracy.

A validation table should therefore distinguish:

``` text
REF  = prescribed reference input
CAL  = calibration parameter
PRED = independently predicted validation output
PERF = predicted performance output
N/A  = no independent comparison available
```

### 2.6 Calibration versus validation

Calibration and validation should be separated.

A calibration parameter is adjusted using reference data to improve the
model representation.

An independently predicted quantity is then used to evaluate the
calibrated model.

$$ \boxed{
\text{quantity used for calibration}
\neq
\text{independent validation evidence}
} $$

For integrated vehicle models, useful independent validation quantities
include gross volume, OEW, MTOW, and performance quantities for which
trustworthy reference data are available.

### 2.7 Validation output interpretation

A validation run should report:

1.  reference inputs;
2.  calibration assumptions, if any;
3.  predicted outputs;
4.  independent reference values;
5.  percentage errors where meaningful;
6.  feasibility constraints;
7.  unavailable reference data explicitly as `N/A`.

The percentage error for a genuinely predicted quantity is

$$ \epsilon =
\frac{x_{\mathrm{ADaPT}}-x_{\mathrm{ref}}}{x_{\mathrm{ref}}}
\times100%. $$

------------------------------------------------------------------------

## 3. Mode 2 --- Forward Mission Analysis

### 3.1 Engineering question

Forward mission analysis asks

$$ \boxed{
\text{How does an already defined airship perform on a specified mission?}
} $$

The vehicle is not being redesigned unless the user explicitly
introduces an outer sizing loop.

### 3.2 What the user specifies

The user normally provides two groups of information.

#### Vehicle definition

Examples:

-   airship type;
-   length;
-   fineness ratio;
-   propulsion architecture;
-   installed shaft power;
-   installed energy/resource capacity;
-   configuration and technology assumptions.

#### Mission definition

Examples:

-   payload;
-   range;
-   cruise altitude;
-   cruise speed;
-   atmospheric temperature deviation;
-   takeoff/landing conditions.

### 3.3 What ADaPT calculates

Typical mission-analysis outputs include:

-   atmospheric state;
-   buoyancy;
-   aerodynamic lift requirement;
-   drag;
-   thrust;
-   shaft/electrical power demand;
-   mission duration;
-   fuel or hydrogen consumption;
-   battery energy requirement;
-   solar contribution;
-   takeoff and landing performance;
-   resource margins;
-   feasibility constraints.

### 3.4 Forward-analysis data flow

``` text
Fixed vehicle definition
          +
Specified mission
          │
          ▼
        ADaPT
          │
 ┌────────┼─────────┐
 ▼        ▼         ▼
power   energy   performance
          │
          ▼
      feasibility
```

### 3.5 Required versus installed capability

Forward analysis is especially useful for checking whether the defined
vehicle can perform the mission.

For power,

$$ g_P = P_{\mathrm{required}} -
P_{\mathrm{installed}}. $$

For an energy/resource capacity,

$$ g_E = R_{\mathrm{required}} -
R_{\mathrm{installed}}. $$

The ADaPT convention is

$$ \boxed{g\le0\Rightarrow\text{feasible}.} $$

A positive constraint indicates that the mission demands more capability
than the Airship has installed.

### 3.6 What forward analysis does not imply

If the user supplies

$$ L=60\~{\rm m} $$

and runs the mission, the resulting analysis answers:

> How does this 60 m candidate perform?

It does not establish that 60 m is the optimum or required airship
length.

That requires a sizing or optimization study.

------------------------------------------------------------------------

## 4. Mode 3 --- Clean-Sheet Sizing

### 4.1 Engineering question

Clean-sheet sizing asks

$$ \boxed{
\text{What airship characteristics are required to satisfy a specified mission?}
} $$

The mission requirements are normally fixed while candidate vehicle
characteristics are changed.

### 4.2 Typical fixed requirements

Examples include

$$ m_{\mathrm{payload}}, \quad R, \quad
h_{\mathrm{cruise}}, \quad
V_{\mathrm{cruise}}, $$

together with:

-   propulsion architecture;
-   takeoff/landing limits;
-   technology assumptions;
-   certification/design constraints.

### 4.3 Typical sizing variables

Depending on the study, the candidate design vector may include

$$ \mathbf{x} = \[ L, FR, BR, C_{HT}, C_{VT},
P_{\mathrm{installed}}, \ldots$$. \]

Architecture-specific variables may also be included.

### 4.4 Sizing loop

``` text
Mission requirements
        │
        ▼
Candidate design x_k
        │
        ▼
      ADaPT
        │
        ├── geometry
        ├── mass
        ├── performance
        ├── propulsion
        └── energy/storage
        │
        ▼
Objectives + constraints
        │
        ▼
Design update
        │
        └───────────────┐
                        │
                 repeat until
                 convergence
                        │
                        ▼
                  final airship
```

### 4.5 Why candidate dimensions must exist during sizing

A sizing framework still needs a numerical candidate value for length,
fineness ratio, installed power, etc. at every iteration.

The optimizer cannot evaluate an undefined vehicle.

Thus

$$ L_k $$

is supplied to Geometry at iteration (k), but this is not the final
answer.

After convergence,

$$ L_k\rightarrow L\^\*. $$

Therefore,

$$ \boxed{
\text{candidate value used by a component}
\neq
\text{final prescribed design}.
} $$

------------------------------------------------------------------------

## 5. Mode 4 --- Optimization

Optimization is an outer numerical search around the multidisciplinary
sizing/analysis model.

The generic problem is

\[
`
\begin{aligned}
\min_{\mathbf{x}}\quad & f(\mathbf{x})\\
\text{subject to}\quad & g_i(\mathbf{x})\le0,\\
& \mathbf{x}_L\le\mathbf{x}\le\mathbf{x}_U.
\end{aligned}
```
\]

ADaPT supports two complementary routes:

``` text
                     ADaPT
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
     OpenMDAO driver          pymoo wrapper
            │                     │
     gradient/local        derivative-free /
        methods            population methods
```

The optimizer changes system-level design variables. ADaPT remains the
physics model.

### 5.1 Optimization inputs

The user defines:

-   fixed mission requirements;
-   architecture;
-   design-variable names and bounds;
-   objective(s);
-   physical constraints;
-   optimizer settings.

### 5.2 Optimization outputs

The final outputs include:

-   optimized design variables;
-   objective value(s);
-   all vehicle sizing outputs;
-   all constraint values;
-   feasibility status;
-   convergence/evaluation information.

------------------------------------------------------------------------

## 6. Mode 5 --- Design-Space Exploration

Design-space exploration (DSE) asks

\[ \boxed{\text{How does the design space behave?}} \]

rather than immediately asking for one optimum.

A set of candidate designs is evaluated:

\[ {\mathbf{x}_1,\ldots,\mathbf{x}_N}
\rightarrow \text{ADaPT} \rightarrow
{\mathbf{y}_1,\ldots,\mathbf{y}_N}. \]

DSE can reveal:

-   feasible and infeasible regions;
-   nonlinear behavior;
-   architecture-specific design spaces;
-   objective trade-offs;
-   coupling effects;
-   technology thresholds;
-   promising regions for later optimization.

DSE is particularly useful before optimization when the feasible region
is poorly understood.

------------------------------------------------------------------------

## 7. Mode 6 --- Sensitivity and Technology Studies

A sensitivity study deliberately varies selected model or technology
parameters while holding the study definition controlled.

Examples include:

-   battery specific energy;
-   motor specific power;
-   fuel-cell efficiency;
-   hydrogen storage gravimetric efficiency;
-   solar-cell efficiency;
-   structural areal density.

A study may evaluate

\[ \frac{\Delta MTOW}{\Delta SE_b} \]

or a normalized sensitivity/elasticity.

The purpose is not necessarily to find an optimum. It is to understand
which assumptions most strongly influence the vehicle.

Technology studies should clearly distinguish:

``` text
vehicle design variable
```

from

``` text
technology scenario parameter.
```

A technology parameter may be varied for sensitivity without implying
that an Airship designer can freely choose any value.

------------------------------------------------------------------------

## 8. Mode 7 --- Payload--Range Analysis

Payload--range analysis changes mission requirements to identify the
operational capability boundary.

Instead of fixing one payload and one range, ADaPT evaluates
combinations such as

\[ (m_{\mathrm{payload}},R). \]

The analysis determines which combinations remain feasible.

Conceptually,

``` text
payload/range pair
       │
       ▼
architecture-specific sizing or analysis
       │
       ▼
feasibility assessment
       │
       ▼
payload-range boundary
```

Payload and range therefore become **study variables**, even though they
are mission requirements within each individual vehicle evaluation.

This illustrates again why variable role depends on the analysis
boundary.

------------------------------------------------------------------------

## 9. Comparing the Analysis Modes


| Mode | What is mainly fixed? | What changes? | Main result |
| --- | --- | --- | --- |
| Validation | Known reference Airship + reference mission | Usually only internal model predictions | Agreement with reference |
| Forward mission analysis | Vehicle + mission | Internal states/resources | Performance and feasibility |
| Clean-sheet sizing | Mission requirements | Candidate vehicle | Sized vehicle |
| Optimization | Requirements + bounds | Design variables | Best feasible design |
| DSE | Study bounds/scenarios | Sampled design variables | Design-space structure |
| Sensitivity study | Baseline case | Selected parameter(s) | Response/sensitivity |
| Payload--range | Architecture/technology assumptions | Payload and range | Feasible mission envelope |



| 10. Same Variable, Diff nsider `length`. Mode | rent Mode Role |
| --- | --- |
| Validation Forward analysis Clean-sheet sizing Optimization DSE Final optimized result | Reference input Fixed vehicle definition Candidate sizing variable Design variable Sampled design variable Sizing output |
| nsider `payload`. |  |
| Mode ----------------------- Validation Forward mission Clean-sheet sizing Standard optimization Payload--range study Performance component | ole --------------------------- eference mission/useful-loa ission requirement ission requirement sually fixed requirement tudy variable omponent input |
| e physical variable has anged. | ot changed. Only the study |

## 11. Choosing the Correct Mode

Use **validation** when the question is:

> Can the framework reproduce a known Airship?

Use **forward mission analysis** when the question is:

> Can this Airship perform this mission?

Use **clean-sheet sizing** when the question is:

> What Airship is required for this mission?

Use **optimization** when the question is:

> Which feasible candidate is best?

Use **DSE** when the question is:

> What does the feasible design space look like?

Use **sensitivity analysis** when the question is:

> Which assumptions or technologies matter most?

Use **payload--range analysis** when the question is:

> What combinations of payload and range can this architecture support?

------------------------------------------------------------------------

## 12. Recommended Reporting Rule

Every ADaPT study should begin by stating:

``` text
Analysis mode:
Architecture:
Fixed mission requirements:
Fixed vehicle/reference quantities:
Design/study variables:
Technology assumptions:
Objective(s):
Constraints:
Primary outputs:
```

This small declaration removes most ambiguity about what the reported
results mean.

------------------------------------------------------------------------

## 13. Summary

The same ADaPT components can support very different engineering
studies.

The essential rule is

\[
\boxed{\text{variable role depends on the analysis mode and analysis boundary}.}
\]

A quantity that is fixed during validation may be optimized during
sizing. A mission requirement in one analysis may become a study
variable in a payload--range sweep. A component input may be a
system-level output from another discipline.

Correctly identifying the analysis mode is therefore the first step in
interpreting any ADaPT input or output.

---
# 4. Variables

# Variables

> **NOTE**
>
> Purpose of this page  This page explains how variables should be interpreted in ADaPT. It is a **user-level variable guide**, not a replacement for the complete OpenMDAO variable listing or the component equations in the Theory Guide.

## 1. Why Variable Roles Need to Be Explicit

ADaPT is a multidisciplinary OpenMDAO framework.

A variable can be:

-   supplied by the user;
-   calculated by one component;
-   passed into another component;
-   varied by an optimizer;
-   fixed during validation;
-   used as a feasibility constraint;
-   reported as a final sizing result.

Therefore,

\[
\boxed{\text{OpenMDAO input/output role}\neq\text{system-level design role}.}
\]

The words **input** and **output** should always be interpreted relative
to a specific component or analysis boundary.

------------------------------------------------------------------------

## 2. Variable Classification

ADaPT variables can be classified into the following user-facing roles.


| Code | Role | Meaning |
| --- | --- | --- |
| `REQ` | Mission requirement | What the vehicle must accomplish |
| `OP` | Operating condition | Environment/condition for evaluation |
| `REF` | Reference input | Known value imposed during validation |
| `DV` | Design variable | Quantity deliberately varied in sizing/optimization |
| `TECH` | Technology parameter | Technology capability/assumption |
| `CIN` | Component input | Variable entering a component |
| `COUT` | Component output | Variable calculated by a component |
| `COUP` | Coupling variable | Output of one discipline used by another |
| `INST` | Installed capacity | Capability physically installed |
| `REQCAP` | Required capacity | Capability demanded by mission |
| `CON` | Constraint | Feasibility measure |
| `OBJ` | Objective | Quantity minimized/maximized |
| `RES` | Reported result | Vehicle/mission result |
| `CAL` | Calibration parameter | Parameter adjusted using reference data |


A variable can have more than one label.

------------------------------------------------------------------------

## 3. Mission Requirements

Mission requirements define what the vehicle must accomplish.

Typical examples are:

### Payload

``` text
payload
```

Units:

\[ {\rm kg} \]

Typical system role:

\[ \boxed{\text{REQ}} \]

Payload enters the mass and performance calculations. It is normally
fixed during clean-sheet sizing, although it may be swept during
payload--range studies.

### Range

``` text
range
```

Typical units:

\[ {\rm m}\quad\text{or reported as km} \]

Typical role:

\[ \boxed{\text{REQ}} \]

Range affects mission duration and therefore fuel/energy requirement.

### Cruise altitude

``` text
cruise_altp
```

Typical units:

\[ {\rm m} \]

Typical roles:

\[ \boxed{\text{REQ / OP}} \]

Altitude determines atmospheric pressure, temperature, and density.

### Cruise speed

``` text
cruise_speed
```

or architecture/component-specific speed variables where applicable.

Typical units:

\[ {\rm m/s} \]

Typical roles:

\[ \boxed{\text{REQ / OP}} \]

In some studies cruise speed may instead be a design variable.

------------------------------------------------------------------------

## 4. Geometry Variables

### Length

``` text
length
```

Units:

\[ {\rm m} \]

Geometry role:

\[ \boxed{\text{CIN}} \]

Possible system roles:

\[ \boxed{\text{REF / DV / RES}} \]

Length is a candidate geometry input. It may be fixed for
validation/forward analysis or varied during clean-sheet sizing.

### Fineness ratio

``` text
fineness_ratio
```

Dimensionless:

\[ FR=\frac{L}{D}. \]

Typical roles:

\[ \boxed{\text{CIN / DV / REF}} \]

The Geometry component uses (L) and (FR) to determine diameter.

### Diameter

Conceptually,

\[ D=\frac{L}{FR}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Diameter is normally derived rather than independently prescribed when
the geometry is parameterized by length and fineness ratio.

### Gross volume

``` text
gross_volume
```

Units:

\[ {\rm m^3} \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Geometry calculates gross volume. Weight and Performance then use it.

### Wetted area / gross area

Geometry produces surface-area quantities used by aerodynamic and mass
models.

Typical units:

\[ {\rm m^2}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

Care should be taken not to assume that every area variable represents
the same physical area. The component documentation defines the exact
convention.

### Tail-volume coefficients

``` text
C_HT
C_VT
```

Dimensionless.

Typical roles:

\[ \boxed{\text{CIN / DV / REF}} \]

These determine horizontal and vertical tail sizing through the geometry
model.

### Ballonet volume

``` text
ballonet_volume
```

Units:

\[ {\rm m^3} \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

For non-rigid/semi-rigid configurations it is estimated from the
geometry/altitude assumptions and then affects the available
helium/internal volume budget.

------------------------------------------------------------------------

## 5. Vehicle-Mass Variables

### Operating empty weight

``` text
owe
```

Units:

\[ {\rm kg} \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

OEW is assembled by the Weight model from vehicle structure, installed
systems, crew, helium, landing system, and miscellaneous terms according
to the model convention.

### Maximum takeoff weight

``` text
mtow
```

Units:

\[ {\rm kg} \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES / OBJ}} \]

MTOW is a Weight output but becomes an input to Performance.

At system level it is a central coupled sizing result and may also be an
optimization objective.

### Operational weight

``` text
operational_weight
```

Units:

\[ {\rm kg} \]

In the current Weight convention this represents

\[ \text{OEW}+\text{payload}. \]

It should not be confused with MTOW.

### Envelope mass

``` text
envelope_mass
```

The code may also retain the simplified alias

``` text
envelop_mass
```

Units:

\[ {\rm kg}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

### Framework mass

``` text
framework_mass
```

Units:

\[ {\rm kg} \]

Relevant to semi-rigid/rigid structural representations.

### Gondola, fin, landing-system and miscellaneous masses

Representative names include:

``` text
gondola_mass
fin_mass
landing_system_mass
miscellaneous_mass
```

These are component-level mass outputs contributing to OEW.

### Helium mass and volume

Representative outputs include:

``` text
he_max_volume
he_max_mass
air_max_volume
```

They are part of the internal-volume and buoyancy/mass representation.

------------------------------------------------------------------------

## 6. Performance Variables

### Required thrust

Performance determines thrust needed to overcome aerodynamic resistance
and satisfy mission conditions.

Typical units:

\[ {\rm N}. \]

Typical role:

\[ \boxed{\text{COUT / COUP}} \]

### Required shaft power

Representative variables include architecture/component-specific
required or shaft-power outputs.

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP / REQCAP}} \]

This is a mission demand, not automatically the installed rating.

### Mission duration

``` text
mission_duration
```

Units:

\[ {\rm s}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Mission duration is used by downstream energy/resource models.

### Takeoff and landing quantities

Performance outputs may include ground-roll or field-length metrics.

Typical units:

\[ {\rm m}. \]

These are

\[ \boxed{\text{COUT / RES}} \]

and may participate in feasibility constraints.

------------------------------------------------------------------------

## 7. Propulsion Variables

### Number of engines / propulsors

Representative variables:

``` text
n_engine
n_propulsor
```

Dimensionless integer counts.

Possible roles:

\[ \boxed{\text{CIN / REF / DV}} \]

These should be treated as discrete quantities if optimized.

### Propeller efficiency

``` text
propeller_efficiency
```

Dimensionless.

Typical roles:

\[ \boxed{\text{CIN / TECH / DV}} \]

depending on the study.

### Shaft power

``` text
shaft_power
```

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{CIN/COUT / COUP}} \]

The exact role depends on the component boundary: Performance may
determine the mechanical demand, while Propulsion/Power consume it.

### Rated shaft power

``` text
rated_shaft_power
```

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{COUT / INST / RES}} \]

### Installed shaft power

``` text
installed_shaft_power
```

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{CIN / INST / REF / DV}} \]

During validation it may be fixed to a known Airship rating. During
sizing it may be a design variable or be determined from the required
rating logic.

### Propulsion-system mass

``` text
propulsion_mass
```

or the corresponding architecture output.

Units:

\[ {\rm kg}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

It is returned to Weight for vehicle mass closure.

------------------------------------------------------------------------

## 8. Power-System Variables

### Electrical demand

``` text
P_elec_total
```

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

For electrical architectures this represents electrical-bus demand.
Users should consult the Theory Guide for architecture-specific naming
conventions.

### Source-demand diagnostics

Representative outputs include:

``` text
P_ice_demand
P_fc_demand
P_bat_demand
P_solar_used
P_solar_available
```

Units:

\[ {\rm W}. \]

These show how total demand is allocated among architecture-specific
sources.

### Fuel flow

``` text
fuel_flow
```

Units:

\[ {\rm kg/s}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

For hydrogen architectures it represents the architecture's hydrogen
consumption path; for combustion architectures it represents fuel flow
according to the selected model.

### Power-system mass

``` text
power_system_mass
```

Units:

\[ {\rm kg}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

This mass is supplied to Weight and should not be independently added
again by the user.

### Power-system volume

``` text
power_system_volume
```

Units:

\[ {\rm m^3}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP}} \]

It participates in the internal-volume budget where applicable.

------------------------------------------------------------------------

## 9. Battery Variables

### Battery specific energy

``` text
battery_specific_energy
```

or the corresponding model input.

Typical units:

\[ {\rm Wh/kg}. \]

Typical roles:

\[ \boxed{\text{TECH / CIN}} \]

It is a technology capability, not a mission requirement.

### Battery efficiency

``` text
battery_efficiency
```

Dimensionless.

Typical role:

\[ \boxed{\text{TECH / CIN}} \]

### Depth of discharge

A dimensionless battery operating assumption.

Typical role:

\[ \boxed{\text{TECH / CIN}} \]

### Required battery capacity

The battery model determines installed capacity from mission energy,
efficiency, depth of discharge, and temperature derating.

Typical units:

\[ {\rm Wh}. \]

Typical roles:

\[ \boxed{\text{COUT / REQCAP / RES}} \]

### Battery mass and volume

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Battery mass feeds back to Weight.

------------------------------------------------------------------------

## 10. Solar Variables

### Solar irradiance

``` text
solar_irradiance
```

Typical units:

\[ {\rm W/m^2}. \]

Typical roles:

\[ \boxed{\text{OP / CIN}} \]

### Solar area

``` text
solar_area
```

Units:

\[ {\rm m^2}. \]

Possible roles:

\[ \boxed{\text{CIN / DV / INST}} \]

### Solar/PV efficiency

``` text
solar_efficiency
```

or corresponding PV-efficiency input.

Dimensionless.

Typical roles:

\[ \boxed{\text{TECH / CIN}} \]

### Solar available and solar used

``` text
P_solar_available
P_solar_used
```

Units:

\[ {\rm W}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Available solar power and solar power actually used by the load are
distinct quantities.

------------------------------------------------------------------------

## 11. Hydrogen and Tank Variables

### Hydrogen/fuel flow

The power system produces the consumption rate required by the selected
hydrogen architecture.

Typical units:

\[ {\rm kg/s}. \]

### Installed hydrogen mass

Tank integrates mission fuel flow and applies the storage/reserve
convention to determine required onboard hydrogen.

Typical roles:

\[ \boxed{\text{COUT / REQCAP / RES}} \]

### Hydrogen storage density

``` text
hydrogen_storage_density
```

Typical units:

\[ {\rm kg/m^3}. \]

Typical role:

\[ \boxed{\text{TECH / CIN}} \]

### Tank gravimetric efficiency

``` text
tank_gravimetric_efficiency
```

Dimensionless.

Typical role:

\[ \boxed{\text{TECH / CIN}} \]

### Tank mass and installed volume

``` text
tank_mass
tank_installed_volume
```

Typical units:

\[ {\rm kg}, \qquad {\rm m^3}. \]

Typical roles:

\[ \boxed{\text{COUT / COUP / RES}} \]

Both feed back to vehicle mass/volume closure.

------------------------------------------------------------------------

## 12. Fuel-Cell Variables

The PEMFC polarization model may use variables such as:

-   requested fuel-cell power;
-   number of cells;
-   active cell area;
-   stack temperature;
-   reactant partial pressures;
-   exchange-current density;
-   limiting-current density;
-   area-specific resistance.

These are detailed technology/component inputs rather than general
mission requirements.

Outputs include:

-   cell voltage;
-   available stack power;
-   maximum power;
-   efficiency;
-   hydrogen-flow diagnostic;
-   power shortfall/capability indicators.

The detailed equations and parameter definitions belong in the Fuel Cell
Theory Guide.

------------------------------------------------------------------------

## 13. Hybrid Variables

### Hybridization fraction

Representative variable:

``` text
tau
```

Dimensionless.

In the generic hybrid power allocation, it controls the battery share of
the residual demand after any solar contribution according to the
implemented architecture logic.

Typical roles:

\[ \boxed{\text{CIN / DV}} \]

The exact physical interpretation should always follow the
architecture-specific documentation.

### Source fractions

Diagnostic outputs may include:

``` text
primary_power_fraction
battery_power_fraction_actual
solar_power_fraction_actual
```

These are calculated outputs describing the resulting mission power
split.

They should not automatically be interpreted as prescribed design
fractions.

------------------------------------------------------------------------

## 14. Technology Parameters versus Design Variables

This distinction is important.

Suppose

\[ SE_b=250\~{\rm Wh/kg}. \]

If the study asks:

> What happens if future battery technology improves?

then (SE_b) is a

\[ \boxed{\text{TECH}} \]

scenario parameter.

If a formal technology optimization allows a range of specific energies,
it may numerically appear in the optimization vector, but physically it
still represents assumed technology capability rather than a geometric
choice made by the airship designer.

The same principle applies to:

-   fuel-cell specific power;
-   motor specific power;
-   PV efficiency;
-   hydrogen storage gravimetric efficiency;
-   structural material areal density.

------------------------------------------------------------------------

## 15. Required versus Installed Variables

ADaPT intentionally distinguishes demand from capacity.

### Power

\[ P_{\rm required}
\quad\text{versus}\quad
P_{\rm installed}. \]

### Fuel/hydrogen

\[ m_{\rm required}
\quad\text{versus}\quad
m_{\rm installed}. \]

### Battery

\[ E_{\rm required}
\quad\text{versus}\quad
E_{\rm installed}. \]

This distinction allows explicit feasibility evaluation.

A required quantity is calculated from the mission.

An installed quantity describes what the vehicle carries or can deliver.

------------------------------------------------------------------------

## 16. Coupling Variables

Coupling variables are central to MDAO.

Examples include:

``` text
gross_volume
gross_area / wetted-area quantities
mtow
propulsion_mass
power_system_mass
power_system_volume
tank_mass
tank_installed_volume
shaft_power
mission_duration
fuel_flow
```

A coupling variable follows the pattern

\[
\boxed{\text{Component A output}\rightarrow\text{Component B input}.}
\]

The user normally should not manually duplicate these calculations.

------------------------------------------------------------------------

## 17. Constraint Variables

ADaPT uses

\[ \boxed{g_i\le0\Rightarrow\text{feasible}.} \]

Representative constraints include:

### Power

\[ g_P=P_{\rm required}-P_{\rm installed}. \]

### Energy/resource

\[ g_E=R_{\rm required}-R_{\rm installed}. \]

### Buoyancy

Conceptually,

\[ g_B=L_{\rm buoy,required}-L_{\rm buoy,available}.
\]

### Lift

\[ g_L=C_{L,\rm required}-C_{L,\max}. \]

### Takeoff

\[ g_{TO}=S_{TO}-S_{TO,\max}. \]

### Landing

\[ g_{LDG}=S_{LDG}-S_{LDG,\max}. \]

A positive constraint value indicates violation.

------------------------------------------------------------------------

## 18. Objective Variables

Depending on the study, ADaPT may optimize quantities such as:

\[ MTOW, \]

fuel/resource consumption,

\[ PFEI, \]

takeoff distance, or payload--range transport work.

A variable becomes an objective only because the optimization problem
declares it as one.

For example, MTOW remains a physical model output whether or not the
optimizer minimizes it.

Thus

\[
\boxed{\text{physical output}\rightarrow\text{objective only when selected by the study}.}
\]


| 19. Validation-Specific Vari ring validation, variables sh ample: Quantity | ble Roles uld be classified Validation role |
| --- | --- |
| Known length Known fineness ratio Reference payload Known installed power Calibrated envelope density Predicted gross volume Predicted OEW Predicted MTOW Power constraint | `REF` `REF` `REF/REQ` `REF/INST` `CAL` `PRED/RES` `PRED/RES` `PRED/RES` `CON` |
| zero error for a `REF` variab lidation. | e does not consti |

## 20. Optimization-Specific Variable Roles

During optimization, the user should document:

``` text
Fixed requirements:
Design variables:
Technology parameters:
Objectives:
Constraints:
Reported outputs:
```

For example:

``` text
Fixed requirements:
    payload
    range
    cruise altitude

Design variables:
    length
    fineness_ratio
    BR_TO

Technology assumptions:
    propeller_efficiency
    battery_specific_energy

Objective:
    mtow

Constraints:
    power
    energy
    buoyancy
    lift
    takeoff
    landing
```

This is much clearer than describing every promoted OpenMDAO variable
simply as an input.

------------------------------------------------------------------------

## 21. Vector Variables

Several ADaPT quantities may be defined over multiple mission points.

Examples include:

-   altitude;
-   atmospheric state;
-   thrust;
-   shaft power;
-   fuel flow;
-   solar irradiance;
-   temperature.

If the model uses (N) mission evaluation points,

\[ \mathbf{P} = \[P_1,P_2,\ldots,P_N\]. \]

Downstream models may integrate these values over mission duration.

Users should therefore check whether a variable is scalar or vector
before assigning values.

------------------------------------------------------------------------

## 22. Units

OpenMDAO supports automatic unit conversion when compatible units are
declared.

Users should nevertheless set values with explicit units.

Examples:

``` python
prob.set_val("payload", 700.0, units="kg")
prob.set_val("length", 60.0, units="m")
prob.set_val("range", 1000.0, units="km")
prob.set_val("cruise_speed", 20.0, units="m/s")
```

Explicit units improve readability and reduce interpretation errors.

------------------------------------------------------------------------

## 23. Options Are Not the Same as Variables

OpenMDAO component **options** configure model behavior.

Examples include:

-   selected airship type;
-   selected power source;
-   number of mission steps;
-   framework mass model;
-   whether pressure-control power is enabled.

Options are generally established when a component/group is created.

Variables are values that participate directly in the model data flow.

Therefore,

\[
\boxed{\text{OpenMDAO option}\neq\text{OpenMDAO input variable}.}
\]

This distinction is important when configuring architecture-dependent
models.

------------------------------------------------------------------------

## 24. Numerical Safeguards Are Not Design Bounds

Some components internally apply operations such as

``` text
max(...)
min(...)
clip(...)
```

to avoid invalid numerical states.

These are not automatically valid engineering design limits.

For example, an internal minimum value may exist only to avoid division
by zero.

Optimization bounds should instead be chosen from physically meaningful
design/technology limits.

\[
\boxed{\text{numerical safeguard}\neq\text{physical design constraint}.}
\]

------------------------------------------------------------------------

## 25. Variable Naming and simplified Aliases

Some parts of the code retain simplified names for backward compatibility.

For example, the Weight component may expose both the corrected
`envelope_mass` name and a simplified alias.

Users should prefer the current documented name in new studies.

Where a name has an architecture-specific interpretation, the relevant
component/theory documentation should be consulted rather than inferring
meaning only from the variable name.

------------------------------------------------------------------------

## 26. Do Not Manually Double Count Coupled Outputs

If a subsystem already calculates and supplies

``` text
propulsion_mass
power_system_mass
tank_mass
battery mass
```

to the vehicle mass closure, the user should not manually add the same
mass again.

The same applies to resource and power quantities.

ADaPT uses subsystem ownership specifically to avoid double counting.

------------------------------------------------------------------------

## 27. Recommended Variable Declaration for Every Study

At the top of a study/run script, document the system-level roles
explicitly.

For example:

``` python
# ============================================================
# STUDY DEFINITION
# ============================================================
# Analysis mode:
#   Clean-sheet optimization
#
# Fixed mission requirements:
#   payload
#   range
#   cruise_altp
#   cruise_speed
#
# Design variables:
#   length
#   fineness_ratio
#   BR_TO
#
# Technology assumptions:
#   propeller_efficiency
#
# Objective:
#   mtow
#
# Constraints:
#   power
#   energy
#   buoyancy
#   lift
#   takeoff
#   landing
# ============================================================
```

This makes the study understandable even to a reader who is not an
OpenMDAO specialist.

------------------------------------------------------------------------

## 28. Recommended User-Facing Variable Table

For major run scripts, a table like the following is recommended:


| Variable | Units | Source | Component role | System role | Fixed/Varied |
| --- | --- | --- | --- | --- | --- |
| `payload` | kg | User | Input | Mission requirement | Fixed |
| `range` | km | User | Input | Mission requirement | Fixed |
| `length` | m | User/optimizer | Geometry input | Design variable | Varied |
| `fineness_ratio` | -- | User/optimizer | Geometry input | Design variable | Varied |
| `gross_volume` | m³ | Geometry | Output/input | Coupling/result | Calculated |
| `mtow` | kg | Weight | Output/input | Sizing result | Calculated |
| required shaft power | kW | Performance | Output/input | Required capacity | Calculated |
| installed shaft power | kW | User/sizing logic | Input | Installed capacity | Varied/calculated |


This is the preferred way to communicate inputs and outputs to
non-specialist users.

------------------------------------------------------------------------

## 29. How to Read a Variable in ADaPT

When encountering an unfamiliar variable, ask five questions:

1.  **Who owns it?**\
    Which component calculates or defines it?

2.  **Who uses it?**\
    Which downstream components consume it?

3.  **What is its system role?**\
    Requirement, design variable, coupling variable, technology
    parameter, capacity, constraint, or result?

4.  **Is it fixed or varied in this study?**

5.  **What are its units and shape?**\
    Scalar or mission vector?

These questions are more useful than asking only whether OpenMDAO labels
the quantity an input or output.

------------------------------------------------------------------------

## 30. Summary

The most important variable rule in ADaPT is

\[
\boxed{\text{a variable's meaning depends on the analysis boundary}.}
\]

For example,

\[ L: \quad \text{Geometry input} \rightarrow
\text{system design variable} \rightarrow
\text{final sizing result}, \]

while

\[ MTOW: \quad \text{Weight output} \rightarrow
\text{Performance input} \rightarrow
\text{coupling variable} \rightarrow
\text{vehicle sizing result}. \]

Similarly, payload is normally a mission requirement, but it can become
a study variable in payload--range analysis.

Users should therefore classify variables by **engineering role**, not
only by their component-level OpenMDAO direction.

---
# 5. Airship Definition

# Airship Definition

> **NOTE**
>
> Purpose of this page  This page explains how an airship is defined for an ADaPT analysis. It separates **vehicle configuration**, **candidate geometry**, **installed subsystem definition**, and **technology assumptions** from mission requirements. It also explains why quantities such as length are fixed inputs in some studies but design variables and final sizing results in others.

## 1. What Does "Airship Definition" Mean in ADaPT?

An ADaPT Airship definition describes the **vehicle being evaluated at
the current model evaluation**.

It may contain:

-   airship structural/configuration type;
-   hull geometry parameters;
-   tail-sizing parameters;
-   landing-system configuration;
-   propulsion and energy architecture;
-   number of engines/propulsors;
-   installed propulsion capability;
-   architecture-specific energy/storage assumptions;
-   crew and selected subsystem assumptions.

It should not be confused with the mission definition.

\[ \boxed{
\text{Airship definition}=\text{what vehicle is being evaluated}
} \]

\[ \boxed{
\text{Mission definition}=\text{what that vehicle must do}
} \]

During clean-sheet optimization, the Airship definition is a
**candidate definition** and may change from one optimizer iteration to
the next.


| 2. Airship Definit e same Airship vari Study | on Depends on Analysis Mode ble can have different system-level roles. Airship definition |
| --- | --- |
| Validation Forward analysis Clean-sheet sizing Optimization DSE | Known reference-Airship characteristics Fixed Airship characteristics Initial/candidate design characteristics Fixed configuration + design variables Sampled candidate characteristics |
| r example, |  |
| L=75\~{`\rm m`{=tex | } \] |
| y be a published ref ) may be changed rep | rence value in validation, but in optimiza atedly until a feasible/best design is fou |

## 3. Configuration versus Sizing Variables

A useful distinction is:

### Configuration choices

These describe the architecture or categorical form of the vehicle.

Examples include:

-   non-rigid, semi-rigid, or rigid;
-   conventional or ACLS landing system;
-   conventional, hydrogen, electric, solar, hybrid, turboprop, or
    turboelectric propulsion/energy architecture.

### Sizing variables

These describe the numerical size or characteristics of the current
candidate.

Examples include:

\[ L,\quad FR,\quad C_{HT},\quad C_{VT}, \]

and, depending on the study,

\[
BR,\quad P_{\rm installed},\quad A_{\rm solar},\ldots
\]

Configuration choices are often OpenMDAO/component **options**, whereas
sizing quantities are normally model variables.

------------------------------------------------------------------------

## 4. Airship Structural Type

The Geometry and Weight models distinguish three principal airship
structural types:

``` text
non-rigid
semi-rigid
rigid
```

### 4.1 Non-rigid

The envelope maintains the aerodynamic form primarily through internal
pressure.

The baseline ADaPT representation includes:

-   external envelope geometry;
-   ballonet volume;
-   envelope mass;
-   gondola;
-   fins;
-   installed propulsion/power systems;
-   helium and useful load.

### 4.2 Semi-rigid

The model additionally supports internal structural proxies such as:

-   outer-envelope area;
-   inner-envelope area;
-   framework/member length;
-   framework mass.

### 4.3 Rigid

The rigid representation additionally supports conceptual
gas-cell/internal structural quantities.

The current geometry and weight representations are conceptual-design
models. Detailed structural finite-element sizing is outside the present
Airship-definition level.

------------------------------------------------------------------------

## 5. Primary Hull Geometry

The baseline geometry is parameterized primarily by length and fineness
ratio.

### Length

``` text
length
```

Units:

\[ {\rm m} \]

### Fineness ratio

``` text
fineness_ratio
```

Dimensionless:

\[ FR=\frac{L}{D}. \]

The diameter is therefore calculated as

\[ D=\frac{L}{FR}. \]

For the baseline spheroidal geometry,

\[ V_{\rm gross} = \frac{\pi}{6}LD\^2 =
\frac{\pi L^3}{6FR^2}. \]

Thus the user/candidate definition provides (L) and (FR), while Geometry
derives diameter, volume, and surface-area quantities.

------------------------------------------------------------------------

## 6. Why Length Is Not Always a "Known Input"

This is an important distinction.

At the Geometry component boundary:

\[ \boxed{L=\text{input}} \]

because Geometry cannot calculate a candidate hull without a candidate
size.

At the system level during optimization:

\[ \boxed{L=\text{design variable}}. \]

At convergence:

\[ \boxed{L^*=\text{final sizing result}}. \]

Therefore the sequence is

``` text
Optimizer/user proposes candidate length
              ↓
Geometry receives length as an input
              ↓
ADaPT evaluates complete candidate
              ↓
Objective + constraints returned
              ↓
New candidate length
              ↓
...
              ↓
Final optimized length
```

A component input is not necessarily a fixed design requirement.

------------------------------------------------------------------------

## 7. Derived Geometry

From the candidate hull definition, Geometry produces quantities used
elsewhere in ADaPT.

Representative quantities include:

``` text
diameter
gross_volume
gross_area / wetted area
reference area
fin areas
ballonet volume
```

These are normally

\[ \boxed{\text{calculated coupling variables}} \]

rather than independent user inputs.

For example,

``` text
length + fineness_ratio
            ↓
         Geometry
            ↓
 diameter + volume + areas
            ↓
     Weight / Performance
```

------------------------------------------------------------------------

## 8. Aerodynamic Reference Area

The baseline Geometry model uses

\[ S_{\rm ref}=V_{\rm gross}\^{2/3}. \]

This reference quantity is passed to aerodynamic/performance
calculations where required.

Users should not confuse aerodynamic reference area with hull wetted
area.

\[ \boxed{S_{\rm ref}\neq S_{\rm wet}} \]

They have different purposes.

------------------------------------------------------------------------

## 9. Tail Definition

The baseline tail representation uses horizontal and vertical
tail-volume coefficients:

``` text
C_HT
C_VT
```

with the tail arm represented as a fraction of vehicle length.

The implemented sizing relation is conceptually

\[ S_{HT} = \frac{C_{HT}L V^{2/3}}{l_t}, \]

\[ S_{VT} = \frac{C_{VT}L V^{2/3}}{l_t}. \]

The resulting tail areas are Geometry outputs and contribute to
aerodynamic and mass calculations.

Depending on the study, (C_{HT}) and (C_{VT}) may be:

-   fixed reference values;
-   engineering assumptions;
-   sampled DSE variables;
-   optimization design variables.

------------------------------------------------------------------------

## 10. Ballonet Definition

For non-rigid and semi-rigid configurations, the baseline geometry
estimates ballonet volume from the altitude-dependent gas-volume
requirement.

The resulting

``` text
ballonet_volume
```

is passed to the Weight/internal-volume calculation.

It is therefore normally a derived geometry quantity rather than an
independent top-level mission requirement.

For rigid configurations, the current conceptual representation does not
use the same ballonet treatment.

------------------------------------------------------------------------

## 11. Buoyancy Ratio

Performance/sizing studies may use a buoyancy ratio such as

\[ BR \]

or a study-specific takeoff buoyancy-ratio variable.

Conceptually, this controls how much of the vehicle weight is supported
aerostatically versus aerodynamically.

Its precise definition and equations belong to the Performance Theory
Guide.

At user-guide level, it should be interpreted as a **vehicle/performance
design parameter**, not as a mission range/payload requirement.

Depending on the study it may be fixed, swept, or optimized.

------------------------------------------------------------------------

## 12. Landing-System Definition

ADaPT supports architecture/configuration choices including:

``` text
conventional
acls
```

for the landing-system option where applicable.

### Conventional landing system

The baseline Weight model represents conventional landing-system mass
using its implemented mass-fraction closure.

### ACLS

The ACLS option activates the corresponding area/mass treatment and may
also affect auxiliary power in the power model.

The landing-system choice is therefore a configuration option with
multidisciplinary consequences.

------------------------------------------------------------------------

## 13. Crew Definition

The Weight model accepts a crew count, represented by

``` text
n_crew
```

and applies the configured crew mass assumption.

Crew belongs to the Airship/operational definition rather than the
payload requirement in the current mass accounting.

Users should therefore avoid manually adding crew mass to payload unless
the study intentionally changes that convention.

------------------------------------------------------------------------

## 14. Propulsion/Energy Architecture

The Airship definition must identify the propulsion and energy
architecture.

The current framework includes representations for architectures such
as:

``` text
conventional_reciprocating
hydrogen_reciprocating
hydrogen_fuel_cell
battery_only
solar_battery
hydrogen_hybrid
solar_hydrogen_hybrid
conventional_battery_hybrid
turboprop
turboelectric
```

Architecture selection determines:

-   which propulsion/power components are active;
-   which resource is consumed;
-   which storage subsystem is required;
-   which subsystem masses and volumes are returned to Weight;
-   which architecture-specific feasibility conditions apply.

Architecture selection is discussed in detail in [Propulsion
Architectures](propulsion_architectures.md).

------------------------------------------------------------------------

## 15. Engine and Propulsor Count

Representative variables include:

``` text
n_engine
n_propulsor
```

These determine how total installed/rated power is distributed among
propulsion units.

For the standard Propulsion model, total rated power may be divided by
`n_engine`.

Turboelectric architectures can distinguish the number of
turbine-generator units from the number of distributed electric
propulsors.

These are discrete configuration quantities and should not be treated as
smooth continuous variables during gradient optimization.

------------------------------------------------------------------------

## 16. Installed versus Required Propulsion Power

The Airship definition may include

``` text
installed_shaft_power
```

where applicable.

This describes vehicle capability.

It should be distinguished from the mission-calculated requirement:

\[ P_{\rm required}. \]

A feasibility measure can be written as

\[ g_P = P_{\rm required} - P_{\rm installed}. \]

Thus:

``` text
installed power -> Airship definition/capability
required power  -> mission/performance result
```

During validation, installed power may be a known reference input.

During clean-sheet sizing, installed/rated power may instead be
determined by sizing logic or included as a design variable.

------------------------------------------------------------------------

## 17. Technology Assumptions Are Part of the Candidate Definition

The vehicle cannot be evaluated without assumptions about subsystem
technology.

Examples include:

-   propeller efficiency;
-   gearbox efficiency;
-   engine thermal efficiency;
-   motor and inverter efficiency;
-   engine/motor specific power;
-   battery specific energy;
-   battery volumetric energy density;
-   PV efficiency;
-   PV areal density;
-   fuel-cell efficiency/specific power;
-   hydrogen storage density;
-   tank gravimetric efficiency.

These are not geometry outputs and normally are not mission
requirements.

They are

\[ \boxed{\text{technology assumptions/scenario parameters}.} \]

Technology studies may vary them deliberately.


| 18. Mass Ownership in the Airship Definit e user should not manually assemble subsyst ned by ADaPT components. e intended ownership is conceptually: Mass | on m masses that are already Owning model |
| --- | --- |
| Envelope/vehicle structural buildup Propulsion hardware Power-conversion hardware Battery PV in standard solar-battery architecture Hydrogen tank Helium | Weight Propulsion or dedicated turbine model Power or dedicated architecture BatteryOnly / SolarBattery SolarBattery Tank Weight |
| ese subsystem outputs are connected to Weig | t for vehicle closure. |
| is prevents double counting. |  |

## 19. Internal-Volume Ownership

Similarly, architecture-specific subsystem volumes can reduce the volume
available to the lifting-gas system.

Representative coupling quantities include:

``` text
power_system_volume
tank_installed_volume
```

The Weight model incorporates these into its internal-volume budget.

A larger energy-storage or power system can therefore affect vehicle
feasibility even if its mass alone appears acceptable.

------------------------------------------------------------------------

## 20. Reference-Airship Definition

For validation, a reference-Airship block should explicitly identify
which quantities are known.

Example structure:

``` python
# ------------------------------------------------------------
# REFERENCE Airship DEFINITION
# ------------------------------------------------------------
# Airship type: ...
# Length: ...
# Fineness ratio: ...
# Number of engines: ...
# Installed power: ...
# Landing system: ...
# Propulsion architecture: ...
#
# These are REF inputs, not independently predicted outputs.
# ------------------------------------------------------------
```

The validation report should then separately identify predicted
quantities.

------------------------------------------------------------------------

## 21. Forward-Analysis Airship Definition

For a mission-analysis case:

``` python
# ------------------------------------------------------------
# FIXED Airship DEFINITION
# ------------------------------------------------------------
# Geometry:
#   length
#   fineness_ratio
#
# Configuration:
#   airship_type
#   landing_system
#   power_source
#   n_engine
#
# Installed capability:
#   installed_shaft_power
#
# Technology:
#   efficiencies / specific power / storage properties
# ------------------------------------------------------------
```

The mission is defined separately.

------------------------------------------------------------------------

## 22. Optimization Airship Definition

For clean-sheet optimization:

``` python
# ------------------------------------------------------------
# CANDIDATE Airship DEFINITION
# ------------------------------------------------------------
# Fixed configuration:
#   airship_type
#   power_source
#   landing_system
#
# Design variables:
#   length
#   fineness_ratio
#   BR_TO
#   C_HT
#   C_VT
#
# Technology assumptions:
#   ...
#
# The optimizer changes the candidate design variables.
# ------------------------------------------------------------
```

This makes it clear that the candidate geometry values supplied to the
components are not fixed mission requirements.

------------------------------------------------------------------------

## 23. Example Conceptual Setup

A simplified user-level configuration may look like:

``` python
# Configuration choices
airship_type = "non-rigid"
power_source = "hydrogen_fuel_cell"
landing_system = "conventional"

# Candidate geometry
prob.set_val("length", 60.0, units="m")
prob.set_val("fineness_ratio", 4.5)

# Propulsion configuration
prob.set_val("n_engine", 2)

# Technology assumptions
prob.set_val("propeller_efficiency", 0.75)
```

The exact variable availability depends on the configured architecture
and current `AirshipAnalysisGroup`.

------------------------------------------------------------------------

## 24. What the User Should Not Normally Prescribe Independently

When Geometry is active as the authoritative geometry model, users
should not independently prescribe mutually dependent quantities such
as:

``` text
length
diameter
gross volume
wetted area
```

unless a specific validation or alternative-geometry workflow
intentionally requires it.

Likewise, users should not independently override coupled mass, power,
and energy outputs without understanding the ownership boundary.

The preferred principle is

\[
\boxed{\text{one authoritative owner for each coupled quantity}.}
\]

------------------------------------------------------------------------

## 25. Airship Definition Checklist

Before running ADaPT, confirm:

-   [ ] airship structural type is selected;
-   [ ] landing-system option is selected;
-   [ ] propulsion/energy architecture is selected;
-   [ ] candidate/reference geometry is defined;
-   [ ] engine/propulsor count is defined;
-   [ ] installed capability is defined where required;
-   [ ] architecture-specific technology assumptions are defined;
-   [ ] crew convention is understood;
-   [ ] no subsystem mass is manually double counted;
-   [ ] design variables are distinguished from fixed quantities;
-   [ ] mission requirements are defined separately.

------------------------------------------------------------------------

## 26. Summary

The Airship definition answers:

\[ \boxed{\text{What vehicle is ADaPT evaluating right now?}} \]

It contains the current configuration, candidate geometry, installed
capability, and technology assumptions.

During validation, this may be a known reference Airship.

During forward analysis, it is a fixed Airship.

During optimization, it is a candidate that changes from iteration to
iteration.

Therefore,

\[ \boxed{
\text{Geometry component input}
\neq
\text{fixed system requirement}
} \]

and

\[ \boxed{
\text{candidate design variable}
\rightarrow
\text{component input}
\rightarrow
\text{multidisciplinary evaluation}
\rightarrow
\text{final sizing result}.
} \]

---
# 6. Mission Definition

# Mission Definition

> **NOTE**
>
> Purpose of this page  This page explains how a mission is defined in ADaPT, which quantities represent mission requirements and operating conditions, how mission information propagates through the multidisciplinary model, and how mission definition differs from Airship definition.

## 1. Airship Definition versus Mission Definition

ADaPT separates the vehicle from the task it must perform.

\[ \boxed{\text{Airship definition}=\text{what the vehicle is}}
\]

\[
\boxed{\text{Mission definition}=\text{what the vehicle must do and under what conditions}}
\]

Typical Airship-definition quantities include:

-   length;
-   fineness ratio;
-   airship type;
-   propulsion architecture;
-   installed power;
-   technology assumptions.

Typical mission-definition quantities include:

-   payload;
-   range;
-   cruise altitude;
-   cruise speed;
-   atmospheric temperature deviation;
-   takeoff/landing operating conditions.

This separation is essential for meaningful sizing studies.

------------------------------------------------------------------------

## 2. Mission Requirements

The principal mission requirements are generally represented by
quantities such as

\[ m_{\rm payload}, \quad R, \quad
h_{\rm cruise}, \quad V_{\rm cruise}. \]

These define the transportation task.

In a standard clean-sheet sizing problem they are normally fixed while
vehicle design variables change.

------------------------------------------------------------------------

## 3. Payload

Representative variable:

``` text
payload
```

Units:

\[ {\rm kg}. \]

Payload is normally a mission/useful-load requirement.

It affects:

-   vehicle mass;
-   required buoyancy/lift;
-   drag/power indirectly through vehicle sizing;
-   internal-volume assumptions where applicable;
-   MTOW.

Conceptually,

\[ m_{\rm payload}\uparrow \Rightarrow
MTOW\uparrow \Rightarrow
\text{lift/buoyancy requirement}\uparrow
\Rightarrow P_{\rm required}\uparrow. \]

In payload--range studies, payload becomes a study variable, but within
each individual evaluation it remains the required payload for that
mission.

------------------------------------------------------------------------

## 4. Range

Representative variable:

``` text
range
```

Range describes the required mission distance.

Depending on the run interface, it may be supplied in metres or another
compatible OpenMDAO unit.

Range strongly affects mission energy because it influences mission
duration.

For a simple constant-speed cruise interpretation,

\[ t_{\rm mission} \approx
\frac{R}{V_{\rm cruise}}. \]

Therefore,

\[ R\uparrow \Rightarrow
t_{\rm mission}\uparrow \Rightarrow
E_{\rm mission}\uparrow \Rightarrow
m_{\rm fuel/storage}\uparrow. \]

The exact mission-duration implementation should be taken from the
active Mission/Performance model.

------------------------------------------------------------------------

## 5. Cruise Altitude

Representative variable:

``` text
cruise_altp
```

Units:

\[ {\rm m}. \]

Cruise altitude is an operating requirement/condition.

It enters the atmospheric model, which determines quantities such as

\[ p,\quad T,\quad \rho. \]

Atmospheric density affects:

-   buoyancy;
-   aerodynamic performance;
-   propeller sizing/performance quantities;
-   helium state;
-   ballonet/internal-volume requirements.

Altitude therefore influences both performance and vehicle sizing.

------------------------------------------------------------------------

## 6. Temperature Deviation / DISA

Representative variables may include:

``` text
cruise_disa
```

or the architecture/mission-specific atmospheric temperature-deviation
input.

This modifies the atmospheric state relative to the standard atmosphere.

Its influence propagates through:

\[ \Delta T \rightarrow T,\rho
\rightarrow \text{buoyancy/aerodynamics/gas state}. \]

The user should specify it consistently with the intended operating
scenario.

------------------------------------------------------------------------

## 7. Cruise Speed

Representative variable:

``` text
cruise_speed
```

with component-level aliases such as true airspeed where applicable.

Units:

\[ {\rm m/s}. \]

Cruise speed affects both aerodynamic power and mission duration.

Conceptually,

\[ P_{\rm shaft} = \frac{TV}{\eta_p}, \]

while

\[ t_{\rm mission} \approx \frac{R}{V}. \]

Therefore speed creates a trade-off:

-   higher speed may shorten mission duration;
-   but it can substantially increase drag and power demand.

Cruise speed may be a fixed mission requirement or, in some optimization
studies, a design/operational variable.

------------------------------------------------------------------------

## 8. Mission Duration

Representative variable:

``` text
mission_duration
```

Units:

\[ {\rm s}. \]

Mission duration is normally calculated or propagated from the mission
definition rather than treated as an independent Airship-sizing
quantity.

It is a key coupling variable for energy/resource models.

For a discrete power history with (N) equal-duration points, several
current energy models use

\[ \Delta t = \frac{t_{\rm mission}}{N}, \]

and

\[ E = \sum_{i=1}\^{N}P_i\Delta t. \]

Thus the mission-duration output connects performance to fuel, battery,
solar, and hydrogen requirements.

------------------------------------------------------------------------

## 9. Mission Evaluation Points

Several ADaPT models support vector inputs/outputs over `num_steps`.

A mission-dependent variable may therefore be represented as

\[ \mathbf{P} = \[P_1,P_2,\ldots,P_N\]. \]

Examples include:

-   altitude;
-   density;
-   temperature;
-   thrust;
-   shaft/electrical power;
-   fuel flow;
-   solar irradiance.

The current energy/storage models may use equal-duration integration
over these points.

Users should not assume that `num_steps` automatically creates a
high-fidelity time-marching trajectory. It defines the discretization
used by the relevant component implementations.

------------------------------------------------------------------------

## 10. Takeoff Conditions

Takeoff analysis may use quantities such as:

-   takeoff thrust;
-   effective takeoff speed;
-   thrust-vector angle;
-   takeoff buoyancy ratio;
-   atmospheric condition;
-   available installed power.

The propulsion model uses a finite effective takeoff speed for its
conceptual takeoff power estimate.

This should not be interpreted as a detailed static-propeller model.

The Performance Theory Guide contains the exact takeoff equations and
assumptions.

------------------------------------------------------------------------

## 11. Landing Conditions

Landing analysis evaluates whether the candidate satisfies the
implemented landing requirement.

Depending on the active performance model/configuration, landing
quantities may include field/ground distance and associated limits.

A typical constraint form is

\[ g_{\rm landing} = S_{\rm landing} -
S_{\rm landing,max}. \]

Feasibility requires

\[ g_{\rm landing}\le0. \]

------------------------------------------------------------------------

## 12. Mission Requirement versus Performance Result

Users should distinguish what is requested from what is predicted.

For example:

``` text
Specified:
    payload
    range
    cruise altitude
    cruise speed

Predicted:
    drag
    thrust
    required power
    mission duration
    fuel/H2/battery requirement
    takeoff/landing performance
```

This distinction is especially important in validation and optimization.

------------------------------------------------------------------------

## 13. Mission Requirement versus Installed Capability

A mission requirement does not guarantee that the candidate Airship can
satisfy it.

The mission creates required quantities such as

\[ P_{\rm required}, \quad E_{\rm required},
\quad m_{\rm fuel,required}. \]

The Airship definition provides installed capability.

The framework then compares them.

\[ g_P = P_{\rm required} - P_{\rm installed}, \]

\[ g_E = R_{\rm required} - R_{\rm installed}. \]

\[
\boxed{g\le0\Rightarrow\text{mission feasible for that requirement}.}
\]

------------------------------------------------------------------------

## 14. How the Mission Propagates Through ADaPT

A simplified mission data flow is:

``` text
payload + range + altitude + speed
                │
                ▼
      atmosphere / operating state
                │
                ▼
       vehicle performance
                │
       ┌────────┴────────┐
       ▼                 ▼
  thrust/power      mission duration
       │                 │
       └────────┬────────┘
                ▼
       power/resource model
                │
                ▼
 fuel / H2 / battery / solar requirement
                │
                ▼
      subsystem mass and volume
                │
                ▼
             MTOW
                │
                └──────► performance coupling
```

This is why changing range or payload can change the final vehicle size
even though they are mission requirements rather than geometry
variables.

------------------------------------------------------------------------

## 15. Mission Definition in Validation

For reference-Airship validation, mission quantities should be matched
as closely as possible to the reference condition.

For example:

``` text
Reference payload:
Reference range:
Reference cruise speed:
Reference cruise altitude:
Reference atmospheric condition:
```

If the published Airship value corresponds to a different operating
condition from the ADaPT run, the comparison should be identified as
approximate rather than direct.

------------------------------------------------------------------------

## 16. Mission Definition in Forward Analysis

In forward analysis, the user defines the mission for the fixed
Airship.

Example:

``` python
# Mission
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1000.0, units="km")
prob.set_val("cruise_altp", 1000.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")
```

The framework then determines whether that vehicle can perform the
mission.

------------------------------------------------------------------------

## 17. Mission Definition in Clean-Sheet Sizing

In clean-sheet sizing, mission requirements are normally fixed:

``` text
payload = fixed
range = fixed
cruise altitude = fixed
cruise speed = fixed or prescribed study condition
```

while vehicle design variables change:

``` text
length
fineness ratio
buoyancy ratio
tail parameters
installed capability
...
```

This is the key distinction:

\[ \boxed{
\text{mission requirements define the target;}
\quad
\text{design variables define the candidate solution}.
} \]

------------------------------------------------------------------------

## 18. Mission Definition in Payload--Range Analysis

Payload--range analysis deliberately varies

\[ m_{\rm payload} \]

and

\[ R. \]

For every pair, ADaPT determines whether the architecture can satisfy
the mission.

The resulting feasible/infeasible transition forms the payload--range
boundary.

Thus payload and range are:

-   mission requirements inside each evaluation;
-   study variables across the payload--range sweep.

------------------------------------------------------------------------

## 19. Architecture Effects on Mission Definition

The high-level mission can remain the same while resource calculations
change by architecture.

For the same

\[ m_{\rm payload},R,h,V, \]

a conventional Airship may require gasoline, a hydrogen architecture
may require hydrogen and tank volume, a battery Airship may require
stored electrical energy, and a solar-battery Airship may offset part
of the electrical demand using solar energy.

Therefore:

\[ \boxed{
\text{same mission requirement}
\not\Rightarrow
\text{same vehicle/resource sizing}.
} \]

------------------------------------------------------------------------

## 20. Solar Mission Inputs

Solar architectures require additional operating information such as

``` text
solar_irradiance
```

and panel/technology definition.

The solar-battery model determines available power from irradiance,
area, and PV efficiency.

Only solar power available under the specified mission condition can
contribute to the mission calculation.

The current model also distinguishes solar energy generated from solar
energy actually used by the load.

------------------------------------------------------------------------

## 21. Mission Energy

For electrical architectures, mission power is converted into energy
demand.

Conceptually,

\[ E_{\rm mission} = \int_0\^{t_f}P(t),dt. \]

Current discrete implementations may approximate this as

\[ E_{\rm mission} \approx
\sum_iP_i\Delta t. \]

Battery and solar-battery sizing then account for the implemented
efficiency, depth-of-discharge, packaging, and temperature assumptions.

------------------------------------------------------------------------

## 22. Mission Fuel/Hydrogen Requirement

For combustion or fuel-cell architectures, the Power model produces a
mass-flow history:

\[ \dot m_f(t). \]

Tank/resource calculations integrate this over the mission:

\[ m_f = \int_0\^{t_f}\dot m_f(t),dt. \]

For hydrogen, the Tank model then applies its reserve/storage
assumptions and calculates tank mass and volume.

------------------------------------------------------------------------

## 23. Mission Feasibility

A mission is feasible only when all required constraints are satisfied.

Conceptually:

\[ \boxed{
g_P\le0,\quad
g_E\le0,\quad
g_B\le0,\quad
g_L\le0,\quad
g_{TO}\le0,\quad
g_{LDG}\le0.
} \]

A design that satisfies range but violates power or takeoff requirements
is not a feasible mission solution.


| 24. Mission Inputs versus Te not mix operating conditions r example: Quantity | hnology Inputs with technology assumptions. Category |
| --- | --- |
| Payload Range Cruise altitude Cruise speed Solar irradiance Battery specific energy Motor specific power Fuel-cell efficiency Hydrogen storage efficiency | Mission requirement Mission requirement Operating condition Operating condition/requirement Environmental/operating input Technology parameter Technology parameter Technology parameter Technology parameter |
| is separation is important wh | n interpreting sensitivity studie |

## 25. Mission Inputs versus Candidate Geometry

Likewise:

  Mission                   Candidate Airship
  ------------------------- ----------------------
  payload                   length
  range                     fineness ratio
  altitude                  buoyancy ratio
  cruise speed              tail coefficients
  environmental condition   installed capability

The mission says what must be achieved.

The candidate geometry says how ADaPT attempts to achieve it.

------------------------------------------------------------------------

## 26. Example Mission Block

A user-facing run script should keep mission definition visibly
separate:

``` python
# ============================================================
# MISSION DEFINITION
# ============================================================
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1000.0, units="km")
prob.set_val("cruise_altp", 1000.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")

# Optional/environmental mission inputs:
# prob.set_val("cruise_disa", ...)
# prob.set_val("solar_irradiance", ...)
# ============================================================
```

Then define the Airship in a separate block.

------------------------------------------------------------------------

## 27. Mission Definition Checklist

Before running the model, confirm:

-   [ ] payload requirement is defined;
-   [ ] range requirement is defined;
-   [ ] cruise altitude is defined;
-   [ ] cruise speed is defined;
-   [ ] atmospheric/environmental assumptions are defined;
-   [ ] architecture-specific mission inputs are supplied;
-   [ ] vector/scalar shapes are consistent with `num_steps`;
-   [ ] mission requirements are not confused with design variables;
-   [ ] installed capability is defined separately from mission demand;
-   [ ] feasibility limits are defined for the study.

------------------------------------------------------------------------

## 28. Summary

The mission definition answers:

\[
\boxed{\text{What must the airship accomplish, and under what operating conditions?}}
\]

The primary mission requirements create demands for lift, thrust, power,
energy, and resources.

Those demands propagate through the multidisciplinary model:

\[ \boxed{
\text{payload/range/conditions}
\rightarrow
\text{performance}
\rightarrow
\text{power}
\rightarrow
\text{energy/resource requirement}
\rightarrow
\text{vehicle mass}
}. \]

In clean-sheet sizing, mission requirements normally remain fixed while
the candidate Airship changes.

This separation between **mission** and **Airship definition** is
fundamental to understanding ADaPT.

---
# 7. Propulsion Architectures

# Propulsion Architectures

> **NOTE**
>
> Purpose of this page  This page helps users select and interpret the propulsion/energy architecture used by ADaPT. It focuses on **which subsystem chain is activated, where power and energy flow, which component owns each mass/resource, and which architecture-specific inputs and outputs matter**. Detailed equations are provided in the Theory Guide.

## 1. Why Architecture Selection Matters

Propulsion architecture changes much more than the engine type.

It changes:

-   mechanical/electrical power conversion;
-   mission resource consumption;
-   installed subsystem mass;
-   installed subsystem volume;
-   storage requirements;
-   vehicle MTOW;
-   multidisciplinary coupling;
-   feasibility constraints.

Therefore,

\[ \boxed{
\text{same payload + range}
+
\text{different architecture}
\rightarrow
\text{different airship design}.
} \]

------------------------------------------------------------------------

## 2. Architecture Families in ADaPT

The framework currently contains representations for architectures
including:

``` text
Conventional / combustion
├── conventional_reciprocating
└── turboprop

Hydrogen
├── hydrogen_reciprocating
├── hydrogen_fuel_cell
└── hydrogen_hybrid

Electric / solar
├── battery_only
├── solar_battery
└── turboelectric

Hybrid
├── conventional_battery_hybrid
└── solar_hydrogen_hybrid

simplified / specialized
└── solar-RFC
```

The exact architecture names accepted by a run script should follow the
current group/component implementation.

------------------------------------------------------------------------

## 3. Common Vehicle-to-Propulsion Chain

For most architectures, the mission first determines
aerodynamic/mechanical demand.

\[ \text{vehicle + mission} \rightarrow
T_{\rm required} \rightarrow
P_{\rm shaft,required}. \]

The selected architecture then determines how that mechanical demand is
supplied.

This separates:

\[ \boxed{\text{mission mechanical demand}} \]

from

\[ \boxed{\text{energy source used to satisfy it}}. \]

------------------------------------------------------------------------

## 4. Conventional Reciprocating Architecture

Architecture name:

``` text
conventional_reciprocating
```

Conceptual flow:

``` text
Performance
    ↓
required thrust / shaft power
    ↓
Propulsion
    ↓
mechanical propulsion hardware
    ↓
Power
    ↓
reciprocating-engine conversion
    ↓
fuel flow
```

The combustion conversion uses the implemented thermal-efficiency and
fuel-LHV assumptions.

### Main resource

Conventional liquid fuel.

### Important technology inputs

Representative inputs include:

``` text
propeller_efficiency
gearbox_efficiency
ice_thermal_efficiency
gasoline_lhv
ice_specific_power
```

### Main outputs

-   required/rated shaft power;
-   propulsion-system mass;
-   power/conversion-system mass;
-   fuel flow;
-   fuel/resource requirement;
-   vehicle-level MTOW and feasibility.

------------------------------------------------------------------------

## 5. Hydrogen Reciprocating Architecture

Architecture name:

``` text
hydrogen_reciprocating
```

Conceptually:

``` text
Performance
    ↓
Propulsion
    ↓
combustion power conversion
    ↓
hydrogen fuel flow
    ↓
Tank
    ↓
installed H2 + tank mass/volume
```

The mechanical propulsion path resembles the reciprocating architecture,
while the fuel properties and storage system are hydrogen-specific.

### Main resource

Hydrogen.

### Additional coupling

Hydrogen storage introduces:

-   tank mass;
-   tank volume;
-   storage-efficiency assumptions;
-   reserve mass;
-   internal-volume effects.

Thus a low fuel mass does not imply a low complete storage-system
penalty.

------------------------------------------------------------------------

## 6. Hydrogen Fuel-Cell Architecture

Architecture name:

``` text
hydrogen_fuel_cell
```

Conceptual flow:

``` text
Performance
    ↓
required shaft power
    ↓
electric Propulsion
    ↓
electrical-bus demand
    ↓
Power / fuel-cell conversion
    ↓
H2 flow
    ↓
Tank
```

The architecture includes both electrical propulsion conversion and
hydrogen storage.

### Main technology inputs

Representative quantities include:

``` text
motor_efficiency
inverter_efficiency
fuel_cell_efficiency
fuel_cell_specific_power
fuel_cell_bop_mass
hydrogen_lhv
```

### Fuel-cell polarization model

Where the semi-empirical PEMFC polarization model is activated, it can
provide load-dependent:

-   cell voltage;
-   efficiency;
-   maximum/capable power;
-   hydrogen-flow diagnostics;
-   shortfall indicators.

The polarization component does not itself own the complete hydrogen
tank.

------------------------------------------------------------------------

## 7. Battery-Only Architecture

Architecture name:

``` text
battery_only
```

Conceptual flow:

``` text
Performance
    ↓
required shaft power
    ↓
electric Propulsion
    ↓
electrical demand
    ↓
BatteryOnly
    ↓
required installed battery energy
    ↓
battery mass + volume
```

### Main resource

Stored electrical energy.

### Battery sizing inputs

Representative technology parameters include:

``` text
battery_specific_energy
battery_volumetric_energy_density
battery_efficiency
depth_of_discharge
packaging_factor
pack_voltage
```

### Important interpretation

Battery mass is owned by `BatteryOnly`, not by the generic Weight or
Power model.

The resulting battery mass is fed back into vehicle mass closure.

This creates a strong loop:

\[ m_b\uparrow \Rightarrow MTOW\uparrow
\Rightarrow P_{\rm required}\uparrow
\Rightarrow E_{\rm required}\uparrow
\Rightarrow m_b\uparrow. \]

------------------------------------------------------------------------

## 8. Solar-Battery Architecture

Architecture name:

``` text
solar_battery
```

Conceptual flow:

``` text
                 solar irradiance
                       ↓
                    PV array
                       ↓
Performance → electrical load
                       │
              ┌────────┴────────┐
              ▼                 ▼
         solar used       battery demand
                                ↓
                         battery sizing
```

The current SolarBattery model owns both:

-   battery pack mass/volume;
-   PV panel mass/volume for this standard architecture.

### Solar power

Conceptually,

\[ P_{\rm solar} = G
A_{\rm solar}\eta_{\rm PV}. \]

### Important distinction

The model distinguishes:

\[ P_{\rm solar,available} \]

from

\[ P_{\rm solar,used}. \]

Only coincident solar power used by the load directly reduces the
battery-delivered mission energy in the standard implementation.

Excess solar is reported and is not automatically credited as stored
battery energy.

------------------------------------------------------------------------

## 9. Hydrogen Hybrid Architecture

Architecture name:

``` text
hydrogen_hybrid
```

The generic hybrid power model combines:

-   fuel-cell primary power;
-   battery power.

Conceptually,

``` text
electrical demand
      │
      ├── battery share
      │
      └── fuel-cell share
               ↓
             H2 flow
               ↓
              Tank
```

The implemented hybridization parameter `tau` controls the battery share
of residual demand according to the current Power model convention.

Users should use the implemented definition rather than interpreting
`tau` generically as an arbitrary total mission-energy fraction.

------------------------------------------------------------------------

## 10. Solar-Hydrogen Hybrid Architecture

Architecture name:

``` text
solar_hydrogen_hybrid
```

This architecture combines:

-   solar power;
-   battery contribution;
-   fuel-cell/hydrogen primary power.

The implemented dispatch logic is conceptually:

\[ P_{\rm solar} =
\min(P_{\rm solar,available},P_{\rm elec,total}),
\]

\[ P_{\rm rem} =
P_{\rm elec,total}-P_{\rm solar}, \]

\[ P_{\rm battery} = \tau P_{\rm rem}, \]

\[ P_{\rm FC} = P_{\rm rem}-P_{\rm battery}.
\]

Thus `tau` is applied **after the solar contribution**.

This detail is important when comparing hybridization studies.

------------------------------------------------------------------------

## 11. Conventional-Battery Hybrid Architecture

Architecture name:

``` text
conventional_battery_hybrid
```

The generic hybrid model allocates residual demand between:

-   battery;
-   reciprocating/combustion primary source.

Conceptually:

``` text
power demand
    │
    ├── battery
    │
    └── combustion primary source
             ↓
           fuel flow
```

The exact interpretation of the electrical/mechanical conversion path
should follow the implemented Power model.

For user studies, the architecture should be described according to the
current code rather than assuming a generic parallel- or series-hybrid
topology that the model has not explicitly represented.

------------------------------------------------------------------------

## 12. Turboprop Architecture

Architecture name:

``` text
turboprop
```

The turboprop model is a dedicated architecture rather than simply the
standard `Propulsion.py + Power.py` path.

Conceptually:

``` text
required shaft power
       ↓
turboshaft / gearbox
       ↓
propeller
       ↓
fuel flow
```

The dedicated model owns its turbine-core/propulsion and associated
fuel-system representation according to its implemented mass boundary.

### Important outputs

-   required/rated shaft power;
-   rated core power;
-   fuel flow;
-   core mass;
-   nacelle/propeller/mount mass;
-   propulsion mass;
-   power-system/fuel-system mass;
-   power shortfall.

If an installed rating is explicitly supplied for validation, the model
can report a positive power shortfall if the reference installation is
insufficient for the calculated requirement.

------------------------------------------------------------------------

## 13. Turboelectric Architecture

Architecture name:

``` text
turboelectric
```

Turboelectric propulsion introduces an electrical transmission chain
between the turbine core and propulsors.

Conceptually:

``` text
fuel
 ↓
turbine core
 ↓
generator
 ↓
electrical bus
 ↓
inverter
 ↓
electric motor(s)
 ↓
propeller(s)
```

The model can distinguish:

``` text
n_engine
```

from

``` text
n_propulsor
```

which supports conceptual distributed-propulsion studies.

### Main component masses

The dedicated model represents quantities such as:

-   turbine core;
-   generator;
-   inverter;
-   wiring;
-   motors;
-   nacelles;
-   propellers;
-   mounts;
-   fuel-system/accessory mass.

Turboelectric propulsion should not automatically be interpreted as more
fuel efficient. Electrical conversion introduces efficiency and mass
penalties; any benefit must arise from the complete system-level design.

------------------------------------------------------------------------

## 14. Solar-RFC Architecture

Architecture name:

``` text
solar-RFC
```

The current Power model contains a simplified simplified
solar/regenerative-fuel-cell storage representation.

It performs a mission-level energy balance using solar generation and an
assumed storage specific energy/volumetric energy density.

This branch is useful as a conceptual/simplified architecture, but it is
less detailed than the dedicated battery, solar-battery, fuel-cell, and
tank pathways.

Users should consult the Theory Guide before using it for quantitative
conclusions.


| 15. Architecture Selection and Ma key ADaPT principle is boxed{\text{each subsystem mass ha simplified map is: Architecture/subsystem | s Ownership one authoritative owner} Main mass owner |
| --- | --- |
| Standard mechanical propulsion Generic conversion equipment Battery-only pack Solar-battery pack + PV Hydrogen tank Turboprop dedicated hardware Turboelectric dedicated hardware Hull/vehicle mass closure | Propulsion Power BatteryOnly SolarBattery Tank Turboprop component Turboelectric component Weight |
| ight receives these masses and ass | mbles the complete vehicl |

## 16. Architecture Selection and Volume Ownership

Architecture also changes internal-volume demand.

Examples include:

-   power-system volume;
-   battery volume;
-   hydrogen tank volume.

These quantities may reduce the volume available for lifting gas or
other vehicle functions.

Therefore architecture comparison should consider

\[ \boxed{\text{mass + volume + efficiency + mission resource}}
\]

rather than energy efficiency alone.

------------------------------------------------------------------------

## 17. Common Architecture Inputs

Although exact variables differ, architecture studies commonly require:

### Vehicle/mission

``` text
payload
range
cruise_altp
cruise_speed
```

### Propulsion

``` text
n_engine
propeller_efficiency
gearbox_efficiency
```

### Installed capability

``` text
installed_shaft_power
```

where applicable.

### Architecture-specific technology

Examples:

``` text
ice_thermal_efficiency
motor_efficiency
inverter_efficiency
battery_specific_energy
solar_efficiency
fuel_cell_efficiency
hydrogen_storage_density
tank_gravimetric_efficiency
```

------------------------------------------------------------------------

## 18. Common Architecture Outputs

Architecture comparison should normally inspect more than one output.

Recommended quantities include:

-   MTOW;
-   OEW;
-   propulsion mass;
-   power-system mass;
-   energy-storage/tank mass;
-   required/rated power;
-   mission fuel/H₂/battery requirement;
-   subsystem volume;
-   PFEI where used;
-   payload--range capability;
-   feasibility constraints.

This prevents an architecture from appearing favorable merely because
one subsystem metric is low.

------------------------------------------------------------------------

## 19. Architecture-Dependent Feasibility

The same mission can fail for different physical reasons.

Examples include:

### Conventional

-   installed power insufficient;
-   fuel/resource requirement excessive;
-   takeoff/landing constraint violated.

### Battery electric

-   battery energy/mass penalty;
-   insufficient installed power;
-   buoyancy/mass closure infeasible.

### Hydrogen

-   tank mass or volume penalty;
-   hydrogen resource requirement;
-   fuel-cell power capability.

### Solar

-   insufficient solar contribution;
-   battery residual energy too large;
-   panel mass/area penalty.

Therefore the architecture should be diagnosed using its active
constraint and resource outputs.

------------------------------------------------------------------------

## 20. Architecture Comparison versus Architecture Optimization

Two different questions can be asked.

### Common-design comparison

Evaluate different architectures using the same or closely controlled
vehicle/mission assumptions.

This helps isolate the effect of architecture.

### Architecture-specific redesign

Allow each architecture to optimize its own geometry/design variables.

This asks:

> What is the best feasible vehicle that each architecture can produce?

These studies answer different questions and should not be mixed.

------------------------------------------------------------------------

## 21. Architecture Selection in Validation

For validation, select the architecture that corresponds to the
reference Airship.

Then use known reference configuration quantities where appropriate.

Do not use a more advanced architecture simply because it produces
better performance if the purpose is to validate against a conventional
reference Airship.

Validation tests model fidelity; it is not an architecture competition.

------------------------------------------------------------------------

## 22. Architecture Selection in Clean-Sheet Sizing

For sizing, the architecture is usually fixed for one optimization run.

For example:

``` text
Run 1 -> conventional_reciprocating
Run 2 -> hydrogen_fuel_cell
Run 3 -> battery_only
Run 4 -> solar_battery
```

Each architecture can then be optimized within appropriate bounds.

This is preferable when different architectures have fundamentally
different feasible design spaces.

------------------------------------------------------------------------

## 23. Architecture Selection in DSE

Architecture-specific DSE is useful because bounds that are appropriate
for a conventional airship may not be appropriate for a battery or solar
configuration.

The design-space definition should therefore be architecture-aware.

A common mission can be retained while allowing architecture-specific
vehicle bounds and technology variables.

------------------------------------------------------------------------

## 24. Technology Assumptions Must Be Reported

Architecture results depend strongly on technology assumptions.

A battery result without battery specific energy, or a fuel-cell result
without fuel-cell efficiency/specific power and hydrogen-storage
assumptions, is incomplete.

For architecture comparisons, report the major assumptions alongside
results.

Recommended categories are:

``` text
Propulsion efficiency
Prime-mover specific power
Battery specific energy / efficiency
PV efficiency / areal density
Fuel-cell efficiency / specific power
Hydrogen storage density / gravimetric efficiency
Fuel LHV
```

------------------------------------------------------------------------

## 25. Choosing an Architecture

A practical selection workflow is:

``` text
What energy source is being studied?
        │
        ├── liquid fuel -> conventional / turboprop
        ├── hydrogen
        │      ├── combustion -> hydrogen_reciprocating
        │      ├── fuel cell -> hydrogen_fuel_cell
        │      └── FC + battery -> hydrogen_hybrid
        │
        ├── battery -> battery_only
        │
        ├── solar + battery -> solar_battery
        │
        ├── solar + H2 + battery -> solar_hydrogen_hybrid
        │
        └── turbine + electrical transmission -> turboelectric
```

The architecture should be chosen from the engineering question, not
from which result is most favorable.

------------------------------------------------------------------------

## 26. Example Architecture Block

A run script should make architecture selection obvious:

``` python
# ============================================================
# Airship ARCHITECTURE
# ============================================================
airship_type = "non-rigid"
power_source = "hydrogen_fuel_cell"
landing_system = "conventional"

# Architecture-specific technology assumptions are defined
# separately below this block.
# ============================================================
```

The exact constructor syntax should follow the current
`AirshipAnalysisGroup` interface.

------------------------------------------------------------------------

## 27. Architecture Checklist

Before running an architecture study, confirm:

-   [ ] architecture name matches the current implementation;
-   [ ] engine type is consistent with architecture;
-   [ ] required architecture-specific component is active;
-   [ ] energy-storage/resource model is active;
-   [ ] technology assumptions are defined;
-   [ ] subsystem mass ownership is understood;
-   [ ] subsystem volume is included where applicable;
-   [ ] installed versus required power is distinguished;
-   [ ] architecture-specific constraints are checked;
-   [ ] comparison cases use clearly stated common or
    architecture-specific assumptions.

------------------------------------------------------------------------

## 28. What This Page Does Not Replace

This page is a selection and interpretation guide.

For detailed equations, assumptions, constants, numerical safeguards,
derivatives, and provenance, use the corresponding Theory Guide pages
for:

-   Propulsion;
-   Power;
-   Turboprop and Turboelectric architectures;
-   BatteryOnly;
-   SolarBattery;
-   FuelCellPolarization;
-   Tank;
-   Weight and Performance.

------------------------------------------------------------------------

## 29. Summary

Architecture selection determines the path by which mission mechanical
demand is converted into stored-energy/resource demand:

\[ \boxed{
\text{mission}
\rightarrow
P_{\rm shaft}
\rightarrow
\text{architecture conversion}
\rightarrow
\text{fuel/H2/electricity/solar}
\rightarrow
\text{subsystem mass + volume}
\rightarrow
MTOW.
} \]

The propulsion architecture is therefore a vehicle-level design decision
with consequences for the entire multidisciplinary sizing loop.

Users should compare architectures using complete vehicle results and
feasibility, not only isolated subsystem efficiencies.

---
# 8. Input Files

# Input Files

> **NOTE**
>
> Purpose of this page  This page explains how user inputs should be organized before an ADaPT run. The objective is to make every study understandable without requiring the reader to trace promoted OpenMDAO variables through the source code.

## 1. What Is an ADaPT Input?

ADaPT has several kinds of information entering a study:

\[ \boxed{
\text{Study definition}
+
\text{Airship definition}
+
\text{Mission definition}
+
\text{Architecture}
+
\text{Technology assumptions}
} \]

Not every OpenMDAO component input is a user input. Many component
inputs are calculated by upstream ADaPT components and connected
internally.

For example,

``` text
length -> user/optimizer candidate
gross_volume -> calculated by Geometry
mtow -> calculated by Weight
shaft power -> calculated from mission/performance
fuel flow -> calculated by Power
```

The user should normally prescribe only the quantities that belong to
the selected study definition.

------------------------------------------------------------------------

## 2. Recommended Input Organization

For transparent studies, organize inputs into six blocks:

``` text
1. Analysis mode
2. Architecture/configuration
3. Mission requirements
4. Airship/reference/design variables
5. Technology assumptions
6. Optimization/DSE settings, if applicable
```

This organization is preferable to one long list of `set_val()` calls.

------------------------------------------------------------------------

## 3. Analysis-Mode Block

Every run should state its purpose first.

Example:

``` python
# ============================================================
# ANALYSIS MODE
# ============================================================
# Mode: forward mission analysis
# Purpose: evaluate a fixed airship for the specified mission
# ============================================================
```

Other valid study descriptions include:

``` text
reference-Airship validation
clean-sheet sizing
optimization
design-space exploration
sensitivity analysis
technology study
payload-range analysis
```

The mode determines how the remaining inputs should be interpreted.

------------------------------------------------------------------------

## 4. Architecture and Configuration Block

This block identifies categorical vehicle choices.

Example:

``` python
# ============================================================
# Airship CONFIGURATION
# ============================================================
airship_type = "non-rigid"
power_source = "hydrogen_fuel_cell"
landing_system = "conventional"
# ============================================================
```

Depending on the architecture, the model may also require engine type or
architecture-specific configuration options.

Configuration options should be established consistently when
`AirshipAnalysisGroup` and its subsystems are created.


| 5. Mission-Requ ssion requiremen riables. ample: ` python ================ MISSION REQUIREM ================ ob.set_val("payl ob.set_val("rang ob.set_val("crui ob.set_val("crui ================ ` pical roles are: Variable | rement Block s should be visibly separated from vehicl ========================================= NTS ========================================= ad", 700.0, units="kg") ", 1000.0, units="km") e_altp", 1000.0, units="m") e_speed", 20.0, units="m/s") ========================================= Role |
| --- | --- |
| `payload` `range` `cruise_altp` `cruise_speed` `cruise_disa` | Mission requirement Mission requirement Operating requirement Operating requirement or study variable Environmental condition |
| chitecture-speci ould also be ide | ic environmental inputs, such as solar ir tified here or in a dedicated environment |

## 6. Airship-Definition Block

For a fixed Airship:

``` python
# ============================================================
# FIXED Airship DEFINITION
# ============================================================
prob.set_val("length", 60.0, units="m")
prob.set_val("fineness_ratio", 4.5)
prob.set_val("n_engine", 2)
# ============================================================
```

For optimization, use a different heading:

``` python
# ============================================================
# CANDIDATE / DESIGN VARIABLES
# ============================================================
# length          -> varied by optimizer
# fineness_ratio  -> varied by optimizer
# BR_TO           -> varied by optimizer
# ============================================================
```

This prevents candidate geometry from being mistaken for a mission
requirement.

------------------------------------------------------------------------

## 7. Reference-Airship Input Block

Validation scripts should explicitly identify imposed reference
quantities.

``` python
# ============================================================
# REFERENCE Airship INPUTS
# ============================================================
# REF: length
# REF: fineness ratio
# REF: payload
# REF: installed shaft power
# REF: cruise condition
#
# These quantities define the known reference Airship.
# They are not independent validation predictions.
# ============================================================
```

If a quantity is calibrated, mark it separately as `CAL`.

------------------------------------------------------------------------

## 8. Technology-Assumption Block

Technology assumptions should never be hidden among geometry variables.

Example:

``` python
# ============================================================
# TECHNOLOGY ASSUMPTIONS
# ============================================================
prob.set_val("propeller_efficiency", 0.75)
prob.set_val("gearbox_efficiency", 0.98)
# architecture-specific battery / FC / solar / tank values...
# ============================================================
```

Representative technology parameters include:

-   propeller efficiency;
-   gearbox efficiency;
-   ICE thermal efficiency;
-   motor efficiency;
-   inverter efficiency;
-   prime-mover specific power;
-   battery specific energy;
-   battery efficiency and depth of discharge;
-   PV efficiency and areal density;
-   fuel-cell efficiency and specific power;
-   hydrogen storage density;
-   tank gravimetric efficiency.

These values should be reported with architecture-comparison results.

------------------------------------------------------------------------

## 9. Scalar and Vector Inputs

Some ADaPT variables are scalar while others may have `num_steps`
entries.

A scalar is conceptually

\[ x=x_0, \]

while a mission vector is

\[ \mathbf{x} = \[x_1,x_2,\ldots,x_N\]. \]

Representative vector quantities may include:

-   altitude;
-   atmospheric state;
-   speed;
-   thrust;
-   shaft power;
-   fuel flow;
-   temperature;
-   solar irradiance.

The supplied shape must match the active component configuration.

------------------------------------------------------------------------

## 10. Units

Use explicit units whenever possible.

``` python
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1000.0, units="km")
prob.set_val("length", 60.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")
```

OpenMDAO can convert compatible units, but explicit units make run files
easier to audit.

------------------------------------------------------------------------

## 11. Options versus Input Variables

OpenMDAO options configure component behavior.

Examples include:

``` text
airship_type
power_source
landing_system
num_steps
framework_mass_model
```

Model inputs participate in the numerical data flow.

Therefore,

\[ \boxed{\text{component option}\neq\text{component input}.} \]

Options are generally supplied during model construction; inputs are
normally assigned after `setup()`.

------------------------------------------------------------------------

## 12. Defaults

Many ADaPT components contain default values so that they can be
instantiated and tested.

A default does **not** automatically mean:

-   validated reference value;
-   recommended design value;
-   universal physical constant;
-   optimization baseline.

For formal studies, important defaults should be explicitly reviewed and
documented.

------------------------------------------------------------------------

## 13. Inputs That Should Normally Be Calculated Internally

When the standard coupled model is active, users should normally allow
authoritative components to calculate quantities such as:

``` text
diameter
gross_volume
wetted/reference area
fin area
ballonet volume
OEW
MTOW
required shaft power
propulsion mass
power-system mass
fuel flow
battery mass
tank mass
```

Manually overriding such quantities can break the intended
multidisciplinary coupling.

------------------------------------------------------------------------

## 14. One Authoritative Source per Quantity

A robust run follows:

\[
\boxed{\text{one quantity}\rightarrow\text{one authoritative owner}.}
\]

For example:

``` text
gross_volume      -> Geometry
mtow              -> Weight
propulsion_mass   -> Propulsion/dedicated architecture
battery mass      -> BatteryOnly or SolarBattery
tank_mass         -> Tank
fuel_flow         -> Power/dedicated architecture
```

This reduces inconsistency and double counting.

------------------------------------------------------------------------

## 15. Input Bounds

Optimization bounds are part of the study definition, not component
physics.

For a design variable,

\[ x_L\le x\le x_U. \]

Bounds should be based on:

-   physically meaningful geometry;
-   reference-airship experience;
-   technology applicability;
-   architecture-specific feasibility;
-   intended study scope.

Do not use internal clipping values as optimization bounds merely
because they appear in component code.

------------------------------------------------------------------------

## 16. Architecture-Specific Inputs

Not every input applies to every architecture.

### Battery architectures

May require:

``` text
battery_specific_energy
battery_volumetric_energy_density
battery_efficiency
depth_of_discharge
```

### Solar architectures

May additionally require:

``` text
solar_irradiance
solar_area
solar/PV efficiency
PV areal density
```

### Fuel-cell architectures

May require:

``` text
fuel_cell_efficiency
fuel_cell_specific_power
fuel_cell BOP assumptions
```

### Hydrogen storage

May require:

``` text
storage type
hydrogen_storage_density
tank_gravimetric_efficiency
reserve fraction
```

Only inputs relevant to the active architecture should be interpreted as
active study parameters.

------------------------------------------------------------------------

## 17. Input Data from External Files

A study may store case data externally rather than hard-code every
value.

Regardless of file format, the same conceptual organization should be
retained:

``` text
case identification
architecture
mission requirements
Airship/reference variables
technology assumptions
study/optimization settings
```

The loading script should map external names to ADaPT/OpenMDAO variable
names explicitly.

Avoid relying on column position alone.

------------------------------------------------------------------------

## 18. Recommended Input Table

Every documented case should include a table such as:


| Variable | Value | Units | Role | Source | Fixed/Varied |
| --- | --- | --- | --- | --- | --- |
| `payload` | ... | kg | REQ | Mission | Fixed |
| `range` | ... | km | REQ | Mission | Fixed |
| `length` | ... | m | REF or DV | Airship/optimizer | Fixed/varied |
| `fineness_ratio` | ... | -- | REF or DV | Airship/optimizer | Fixed/varied |
| `propeller_efficiency` | ... | -- | TECH | Assumption/source | Fixed |
| battery/FC/tank parameter | ... | ... | TECH | Assumption/source | Fixed/scenario |


This is much clearer than describing all quantities generically as
inputs.

------------------------------------------------------------------------

## 19. Input Validation Before Execution

Before `run_model()` or optimization:

-   confirm architecture is valid;
-   confirm required variables exist;
-   confirm units;
-   confirm vector shapes;
-   confirm design-variable bounds;
-   confirm no duplicated subsystem ownership;
-   confirm reference values are not being mistaken for predictions;
-   confirm technology assumptions are appropriate to the architecture.

------------------------------------------------------------------------

## 20. Recommended Run-File Header

``` python
# ============================================================
# ADaPT STUDY DEFINITION
# ============================================================
# Analysis mode:
#
# Architecture:
#
# Fixed mission requirements:
#
# Fixed Airship/reference quantities:
#
# Design variables:
#
# Technology assumptions:
#
# Objective(s):
#
# Constraints:
#
# Primary reported outputs:
# ============================================================
```

This header is recommended for validation, DSE, optimization, and
payload--range scripts.

------------------------------------------------------------------------

## 21. Summary

ADaPT input preparation should answer three questions:

\[ \boxed{\text{What is fixed?}} \]

\[ \boxed{\text{What is allowed to vary?}} \]

\[ \boxed{\text{What should ADaPT calculate internally?}} \]

A well-organized input definition makes the distinction between mission
requirements, Airship variables, technology assumptions, reference
data, and internally coupled outputs immediately clear.

---
# 9. Running ADaPT

# Running ADaPT

> **NOTE**
>
> Purpose of this page  This page describes the standard user workflow for configuring, executing, checking, and recording an ADaPT analysis. It is intentionally workflow-oriented; component equations are documented in the Theory Guide.

## 1. Standard Workflow

A typical ADaPT run follows:

``` text
Choose analysis mode
        ↓
Choose architecture
        ↓
Construct OpenMDAO Problem / AirshipAnalysisGroup
        ↓
prob.setup()
        ↓
Set mission + Airship + technology values
        ↓
Run model / driver
        ↓
Check convergence and feasibility
        ↓
Read and record outputs
```

The most important principle is:

\[
\boxed{\text{do not interpret results before checking feasibility}.}
\]

------------------------------------------------------------------------

## 2. Step 1 --- Define the Engineering Question

Before writing code, identify whether the run is:

-   validation;
-   forward mission analysis;
-   clean-sheet sizing;
-   optimization;
-   DSE;
-   sensitivity analysis;
-   payload--range analysis.

This determines what should be fixed and what should vary.

------------------------------------------------------------------------

## 3. Step 2 --- Select the Architecture

Select the appropriate airship and propulsion/energy configuration.

Conceptually:

``` python
airship_type = "non-rigid"
power_source = "conventional_reciprocating"
landing_system = "conventional"
```

The exact constructor/configuration syntax should follow the current
`AirshipAnalysisGroup`.

Architecture selection must occur before assuming that battery,
fuel-cell, tank, or solar variables are available.

------------------------------------------------------------------------

## 4. Step 3 --- Create the OpenMDAO Problem

The top-level workflow is conceptually:

``` python
import openmdao.api as om

prob = om.Problem()

# Configure/add AirshipAnalysisGroup
# prob.model = AirshipAnalysisGroup(...)

prob.setup()
```

`AirshipAnalysisGroup` assembles the multidisciplinary model and
architecture-dependent subsystem chain.

------------------------------------------------------------------------

## 5. Step 4 --- Set Inputs After Setup

User-level model variables are normally assigned after `prob.setup()`.

Example:

``` python
# Mission requirements
prob.set_val("payload", 700.0, units="kg")
prob.set_val("range", 1000.0, units="km")
prob.set_val("cruise_altp", 1000.0, units="m")
prob.set_val("cruise_speed", 20.0, units="m/s")

# Candidate/fixed Airship
prob.set_val("length", 60.0, units="m")
prob.set_val("fineness_ratio", 4.5)
```

Architecture-specific values can then be assigned where applicable.

------------------------------------------------------------------------

## 6. Step 5 --- Run a Single Analysis

For one candidate:

``` python
prob.run_model()
```

This evaluates the configured multidisciplinary system without asking an
optimizer to change the design.

Use `run_model()` for:

-   validation cases;
-   forward analysis;
-   one DSE sample;
-   one sensitivity sample;
-   debugging a candidate design;
-   testing a model configuration before optimization.

------------------------------------------------------------------------

## 7. Step 6 --- Run an Optimization

When an OpenMDAO driver has been configured:

``` python
prob.run_driver()
```

The driver repeatedly evaluates the ADaPT model while changing declared
design variables.

Conceptually:

\[ \mathbf{x}_k \rightarrow \text{ADaPT}
\rightarrow f_k,\mathbf{g}*k \rightarrow
\mathbf{x}*{k+1}. \]

Do not use `run_driver()` merely to evaluate one fixed vehicle.

------------------------------------------------------------------------

## 8. OpenMDAO-Based versus pymoo-Based Runs

### OpenMDAO route

``` text
OpenMDAO driver
      ↓
AirshipAnalysisGroup
      ↓
objective + constraints
```

### pymoo route

``` text
pymoo candidate population
          ↓
wrapper assigns ADaPT variables
          ↓
ADaPT/OpenMDAO run_model()
          ↓
objectives + constraints returned to pymoo
```

pymoo is an outer optimization/search layer. It does not replace the
ADaPT physics.

------------------------------------------------------------------------

## 9. Read Outputs

Use `get_val()` to retrieve quantities.

Example:

``` python
mtow = prob.get_val("mtow", units="kg")
volume = prob.get_val("gross_volume", units="m**3")
```

For vectors, inspect the complete array or the physically relevant
statistic rather than silently taking the first value.

------------------------------------------------------------------------

## 10. Check the Model Before Trusting the Result

A successful Python execution only means that the calculation completed.

It does not guarantee that the design is physically feasible.

Check:

1.  numerical convergence;
2.  finite outputs;
3.  multidisciplinary mass closure;
4.  power/resource constraints;
5.  buoyancy/lift constraints;
6.  takeoff/landing constraints;
7.  architecture-specific feasibility;
8.  whether any numerical safeguard is active at the reported solution.

------------------------------------------------------------------------

## 11. Feasibility Convention

ADaPT studies use the convention

\[ \boxed{g_i\le0\Rightarrow\text{feasible}.} \]

Therefore:

``` text
negative constraint -> margin available
zero constraint     -> active boundary
positive constraint -> violation
```

This convention should be printed or documented with every
optimization/DSE result.

------------------------------------------------------------------------

## 12. Required versus Installed Capability

A run should distinguish required mission quantities from installed
vehicle capability.

For example,

\[ g_P=P_{\rm required}-P_{\rm installed}. \]

If

\[ g_P\>0, \]

the vehicle lacks sufficient installed power even if all other outputs
appear numerically reasonable.

The same principle applies to energy/resource capacities.

------------------------------------------------------------------------

## 13. Debugging a Run

When a run fails, diagnose the problem in layers.

### Configuration

-   Is the architecture name valid?
-   Are the required architecture-specific components active?
-   Are component options consistent?

### Variable setup

-   Does the variable exist?
-   Are promoted names unambiguous?
-   Are input defaults consistent?
-   Are units compatible?
-   Are vector shapes correct?

### Physics

-   Is the candidate geometry physically meaningful?
-   Is internal volume positive?
-   Is installed capability sufficient?
-   Are technology parameters within meaningful ranges?

### Numerical behavior

-   Are NaN or infinite values produced?
-   Is a nonlinear coupling failing to converge?
-   Is clipping/flooring dominating the candidate?

------------------------------------------------------------------------

## 14. Promoted-Input Ambiguity

Because ADaPT uses promoted OpenMDAO variables, several subsystems may
consume the same promoted quantity.

Their default metadata should be consistent.

When OpenMDAO reports that promoted inputs have different default
values, the group should establish a single intended default using the
appropriate OpenMDAO input-default mechanism.

This is a model-assembly issue, not a reason to assign different
physical values to the same promoted variable.

------------------------------------------------------------------------

## 15. Running Validation Cases

A validation run should:

1.  construct the reference architecture;
2.  set known reference quantities;
3.  run the model;
4.  retrieve independently predicted quantities;
5.  compare them with independent reference data;
6.  report errors only for genuine predictions;
7.  report feasibility separately.

Conceptually:

``` python
# REF inputs
# ...
prob.run_model()

# PRED outputs
mtow_pred = prob.get_val("mtow", units="kg")
```

------------------------------------------------------------------------

## 16. Running Forward Mission Cases

For a fixed vehicle:

``` text
fixed Airship
     +
mission
     ↓
run_model()
     ↓
performance/resource use
     ↓
feasibility
```

If the mission is infeasible, the correct conclusion is that the
specified candidate cannot satisfy the mission under the implemented
assumptions---not that the code necessarily failed.

------------------------------------------------------------------------

## 17. Running DSE Cases

DSE repeatedly assigns candidate values and runs the model.

Pseudo-workflow:

``` python
for candidate in design_samples:
    assign_design(candidate)

    try:
        prob.run_model()
        collect_outputs()
        evaluate_feasibility()
    except Exception:
        record_failed_case()
```

A robust DSE should retain failed/infeasible cases rather than silently
deleting them.

The reason for infeasibility is valuable design-space information.

------------------------------------------------------------------------

## 18. Running Sensitivity Studies

Sensitivity studies should change one controlled parameter or a planned
set of parameters while retaining a clearly defined baseline.

For each case, record:

``` text
parameter value
vehicle outputs
performance outputs
constraints
feasibility
```

If changing a technology parameter causes the optimum geometry to be
redesigned, explicitly state whether the study is:

``` text
fixed-design sensitivity
```

or

``` text
re-optimized technology sensitivity.
```

These answer different questions.

------------------------------------------------------------------------

## 19. Running Payload--Range Studies

For each payload/range combination:

1.  assign mission requirements;
2.  run or resize the architecture according to the study definition;
3.  evaluate all feasibility constraints;
4.  record feasible/infeasible status;
5.  identify the boundary.

Do not define payload--range feasibility from a single metric if other
active constraints are violated.

------------------------------------------------------------------------

## 20. Record the Study Definition with the Results

Every output file should retain enough metadata to reconstruct the case:

``` text
analysis mode
architecture
mission requirements
design/reference variables
technology assumptions
optimizer/DSE settings
constraint convention
software/model version where available
```

Without these, a CSV of final numbers may be impossible to interpret
later.

------------------------------------------------------------------------

## 21. Output Files

Common study outputs may include:

-   CSV tables;
-   optimization histories;
-   feasibility traces;
-   payload--range boundaries;
-   Pareto sets;
-   plots;
-   validation comparison tables.

Use explicit column names and units.

Prefer:

``` text
mtow_kg
range_km
required_shaft_power_kw
power_constraint_kw
```

over ambiguous labels such as:

``` text
weight
power
constraint1
```

------------------------------------------------------------------------

## 22. Reproducibility

For optimization and stochastic DSE:

-   record random seed;
-   record bounds;
-   record population/sample size;
-   record algorithm;
-   record stopping criteria;
-   record technology assumptions.

For deterministic OpenMDAO runs, retain solver/driver configuration and
tolerances where relevant.

------------------------------------------------------------------------

## 23. Numerical Safeguards

Some components use floors, clipping, or minimum values.

A completed run may therefore be numerically valid while sitting on a
safeguard.

Examples include minimum geometry values, bounded efficiencies, minimum
storage volumes, or clipped empirical relations.

A final design should be checked for active safeguards before being
accepted as a physical optimum.

------------------------------------------------------------------------

## 24. Recommended Console Summary

A useful run should end with a concise summary such as:

``` text
============================================================
ADaPT RUN SUMMARY
============================================================
Mode:          Clean-sheet optimization
Architecture:  hydrogen_fuel_cell

Mission:
  Payload:     ...
  Range:       ...
  Altitude:    ...
  Speed:       ...

Final vehicle:
  Length:      ...
  FR:          ...
  Gross volume:...
  OEW:         ...
  MTOW:        ...

Power/resource:
  Required:    ...
  Installed:   ...
  H2/fuel/E:   ...

Constraints:
  Power:       ...
  Energy:      ...
  Buoyancy:    ...
  Lift:        ...
  Takeoff:     ...
  Landing:     ...

Overall feasible: YES / NO
============================================================
```

This is much easier for a non-specialist to interpret than raw OpenMDAO
output.

------------------------------------------------------------------------

## 25. Minimum Pre-Run Checklist

-   [ ] analysis mode identified;
-   [ ] architecture configured;
-   [ ] `prob.setup()` completed;
-   [ ] mission inputs assigned;
-   [ ] Airship/reference/design variables assigned;
-   [ ] technology assumptions assigned;
-   [ ] units and shapes checked;
-   [ ] optimization variables/objectives/constraints configured if
    needed.

------------------------------------------------------------------------

## 26. Minimum Post-Run Checklist

-   [ ] run completed without exception;
-   [ ] outputs are finite;
-   [ ] MTOW/mass balance is meaningful;
-   [ ] all active constraints inspected;
-   [ ] architecture-specific resource use inspected;
-   [ ] no unexpected numerical safeguard dominates;
-   [ ] results saved with case metadata.

------------------------------------------------------------------------

## 27. Summary

Running ADaPT is not simply:

``` python
prob.run_model()
```

A correct workflow is

\[ \boxed{
\text{define study}
\rightarrow
\text{configure architecture}
\rightarrow
\text{assign inputs}
\rightarrow
\text{execute}
\rightarrow
\text{check convergence}
\rightarrow
\text{check feasibility}
\rightarrow
\text{interpret results}.
} \]

The distinction between **a calculation that ran successfully** and **a
physically feasible airship design** is fundamental.

---
# 10. Optimization

# Optimization

> **NOTE**
>
> Purpose of this page  This page explains how ADaPT is used as an optimization model. It distinguishes the physical analysis from the optimization algorithm and describes the two principal routes used in the framework: **OpenMDAO-based optimization** and **pymoo-based optimization/design-space search**.

## 1. Optimization in ADaPT

ADaPT first evaluates the physics of one candidate airship.

Optimization adds an outer design loop:

\[ \boxed{
\mathbf{x}
\rightarrow
\text{ADaPT}
\rightarrow
f(\mathbf{x}),\mathbf{g}(\mathbf{x})
\rightarrow
\text{optimizer}
\rightarrow
\mathbf{x}_{\rm new}.
} \]

The optimizer does not replace Geometry, Weight, Performance,
Propulsion, Power, Battery, Tank, or other physical models.

It only determines which candidate should be evaluated next.

------------------------------------------------------------------------

## 2. Generic Optimization Problem

A single-objective constrained problem can be written as

\[
`
\begin{aligned}
\min_{\mathbf{x}}\quad & f(\mathbf{x})\\
\text{subject to}\quad
& g_i(\mathbf{x})\le0,\qquad i=1,\ldots,n_g,\\
& x_j^L\le x_j\le x_j^U.
\end{aligned}
```
\]

For multi-objective studies,

$$ \min_{\mathbf{x}} \left[
f_1(\mathbf{x}),
f_2(\mathbf{x}),
\ldots
\right]. $$

------------------------------------------------------------------------

## 3. What Is Fixed during Optimization?

The optimization study should explicitly identify fixed quantities.

Typical fixed requirements include:

``` text
payload
range
cruise altitude
cruise speed
architecture
technology scenario
```

These define the problem the optimizer must solve.

If a technology parameter is also optimized, that should be stated
explicitly because it changes the interpretation of the study.

------------------------------------------------------------------------

## 4. Design Variables

Representative airship design variables may include:

$$ L, \quad FR, \quad BR, \quad C_{HT},
\quad C_{VT}, $$

and architecture-specific quantities.

The design vector can be written as

$$ \mathbf{x} = \[L,FR,BR,C_{HT},C_{VT},\ldots$$. \]

A design variable is a **system-level role**.

It may still be an ordinary component input inside OpenMDAO.

------------------------------------------------------------------------

## 5. Why Length Is an Optimization Input and an Output

At iteration (k),

$$ L=L_k $$

is sent into Geometry.

ADaPT evaluates the complete candidate and returns objective/constraint
values.

The optimizer then chooses (L_{k+1}).

After convergence,

$$ L_k\rightarrow L\^\*. $$

Therefore:

$$ \boxed{
L_k=\text{optimizer candidate/component input}
} $$

but

$$ \boxed{
L^*=\text{final optimized sizing result}.
} $$

This is the same principle for other optimized vehicle variables.

------------------------------------------------------------------------

## 6. Objectives

Possible objectives depend on the study.

Examples include:

### Minimum MTOW

$$ \min MTOW. $$

### Minimum PFEI

$$ \min PFEI. $$

### Maximum payload--range transport work

If the optimization software minimizes objectives, a maximization
objective may be represented by minimizing its negative or another
consistent transformation.

### Multiple objectives

A study may simultaneously consider:

$$ \boxed{
\min MTOW^*,
\qquad
\min PFEI,
\qquad
\max W_{\rm transport}.
} $$

Multi-objective optimization generally produces a trade-off set rather
than one universally best design.

------------------------------------------------------------------------

## 7. Constraints

ADaPT studies use the convention

$$ \boxed{g_i\le0\Rightarrow\text{feasible}.} $$

Representative constraint families include:

-   power;
-   energy/resource;
-   buoyancy;
-   aerodynamic lift;
-   takeoff;
-   landing;
-   architecture-specific capability/volume limits.

For example,

$$ g_P = P_{\rm required} - P_{\rm installed}. $$

A positive value means insufficient installed power.

------------------------------------------------------------------------

## 8. Constraint Margins

The sign of a constraint is informative.

``` text
g < 0 -> feasible with margin
g = 0 -> active constraint
g > 0 -> infeasible
```

An optimized design often lies close to one or more active constraints.

Those active constraints help explain what physically sizes the airship.

------------------------------------------------------------------------

## 9. Design Bounds

Each design variable requires physically meaningful bounds:

$$ x_L\le x\le x_U. $$

Bounds should reflect:

-   intended airship class;
-   geometric plausibility;
-   architecture applicability;
-   technology applicability;
-   known/reference designs;
-   study purpose.

Architecture-specific bounds are often necessary.

A battery/solar design space does not have to use exactly the same
bounds as a conventional architecture if doing so would exclude
physically relevant regions or create meaningless candidates.

------------------------------------------------------------------------

## 10. OpenMDAO-Based Optimization

In the OpenMDAO route, design variables, objective(s), and constraints
are declared on the OpenMDAO model.

Conceptually:

``` python
prob.model.add_design_var(
    "length",
    lower=...,
    upper=...
)

prob.model.add_objective("mtow")

prob.model.add_constraint(
    "power_constraint",
    upper=0.0
)
```

A driver is then assigned and executed with

``` python
prob.run_driver()
```

The exact driver and declarations depend on the study script.

------------------------------------------------------------------------

## 11. Why Use OpenMDAO Optimization?

OpenMDAO-based optimization is useful when:

-   the design problem is relatively smooth;
-   derivative information is available or approximated;
-   a local constrained optimum is appropriate;
-   tight integration with the multidisciplinary model is desired.

OpenMDAO also provides infrastructure for derivatives, recorders,
solvers, and driver diagnostics.

------------------------------------------------------------------------

## 12. Derivatives

Many current ADaPT components use finite-difference derivative
approximation.

This permits gradient-based workflows but should not be interpreted as
equivalent to exact analytic derivatives.

Derivative quality can be affected by:

-   clipping;
-   `max()`/`min()` logic;
-   integer rounding;
-   architecture switches;
-   active numerical floors;
-   noisy/non-smooth empirical models.

These features are important when choosing an optimization algorithm.

------------------------------------------------------------------------

## 13. pymoo-Based Optimization

The pymoo route wraps ADaPT as an external engineering evaluator.

Conceptually:

``` text
pymoo
  │
  ├── proposes x
  ▼
ADaPT wrapper
  │
  ├── assigns OpenMDAO variables
  ├── runs model
  ├── retrieves objectives
  └── retrieves constraints
  ▼
pymoo
```

The physics remains inside ADaPT.

------------------------------------------------------------------------

## 14. Why Use pymoo?

pymoo is particularly useful for:

-   population-based search;
-   multi-objective optimization;
-   Pareto-front generation;
-   non-smooth design spaces;
-   broad/global exploration;
-   problems where derivatives are inconvenient;
-   architecture-specific design-space studies.

The trade-off is generally a larger number of model evaluations.


| 15. OpenMDAO versus Feature | pymoo OpenMDAO driver | pymoo route |
| --- | --- | --- |
| Physics model Typical search Derivatives Multi-objective Non-smoothness Evaluation count Pareto exploration | ADaPT Local/gradient-oriented Can exploit them Driver-dependent Can be challenging Often lower Possible, workflow-dependent | ADaPT Population/evolutionary Usually not required Strong native use case Often more tolerant Often higher Natural use case |
| ither route changes | he governing airship equations |  |

## 16. pymoo Constraint Convention

pymoo wrappers should preserve a clearly documented feasibility
convention.

If ADaPT uses

$$ g_i\le0, $$

the wrapper should return constraints consistently with the algorithm's
expected convention.

Do not silently change signs between scripts.

A useful code comment is:

``` python
# Constraint convention:
# g <= 0 is feasible
```

------------------------------------------------------------------------

## 17. Failed Evaluations

Optimization algorithms may propose physically impossible candidates.

A robust wrapper should handle:

-   model exceptions;
-   NaN/Inf outputs;
-   invalid geometry;
-   non-convergence;
-   severe constraint violations.

Failed candidates should be converted into clearly infeasible
objective/constraint values according to the study's failure-handling
policy.

They should not accidentally appear attractive to the optimizer.

------------------------------------------------------------------------

## 18. Design-Space Exploration before Optimization

DSE is often useful before optimization.

$$ \boxed{
\text{DSE}
\rightarrow
\text{understand feasible region}
\rightarrow
\text{choose bounds/algorithm}
\rightarrow
\text{optimization}.
} $$

DSE can reveal:

-   disconnected feasible regions;
-   strong nonlinearities;
-   active constraints;
-   architecture-specific feasible ranges;
-   objective conflicts.

------------------------------------------------------------------------

## 19. Single-Objective Optimization

For a single objective such as MTOW:

$$ \min_{\mathbf{x}} MTOW(\mathbf{x}) $$

subject to all active feasibility constraints.

The reported result should include not only the minimum MTOW but also:

-   final design variables;
-   component masses;
-   required/installed power;
-   energy/resource use;
-   active constraints;
-   convergence information.

------------------------------------------------------------------------

## 20. Multi-Objective Optimization

For multiple objectives, there may be no single design that improves
every objective simultaneously.

A design (\mathbf{x}_1) dominates (\mathbf{x}_2) if it
is no worse in all objectives and better in at least one, using a
consistent minimization/maximization convention.

The non-dominated solutions form the Pareto set/front.

ADaPT architecture studies may therefore report trade-offs among mass,
energy/environmental performance, and transport capability.

------------------------------------------------------------------------

## 21. Reading a Pareto Plot

A Pareto plot should distinguish:

-   all sampled/evaluated designs;
-   feasible designs;
-   non-dominated designs;
-   selected representative solutions.

The plot should state whether each axis is minimized or maximized.

A visually extreme point is not automatically the preferred engineering
design.

------------------------------------------------------------------------

## 22. Architecture-Specific Optimization

Each architecture can be optimized independently:

``` text
conventional -> its own design variables/bounds -> optimum
hydrogen     -> its own design variables/bounds -> optimum
battery      -> its own design variables/bounds -> optimum
solar        -> its own design variables/bounds -> optimum
```

This answers:

$$
\boxed{\text{What is the best feasible redesign for each architecture?}}
$$

It differs from evaluating all architectures on one common fixed
geometry.

------------------------------------------------------------------------

## 23. Common-Design versus Redesigned Comparison

### Common-design comparison

Same/controlled geometry and mission:

$$ \text{architecture effect on a common vehicle}. $$

### Architecture-specific redesign

Each architecture is allowed to adapt:

$$ \text{best achievable design under each architecture}. $$

Both are scientifically useful, but they answer different questions.

------------------------------------------------------------------------

## 24. Technology Optimization versus Technology Sensitivity

Suppose battery specific energy is varied.

If the vehicle geometry remains fixed, this is a **fixed-design
technology sensitivity**.

If the vehicle is re-optimized at every battery specific energy, this is
a **technology-conditioned redesign study**.

If battery specific energy itself is placed in the optimizer vector, the
study is effectively optimizing over technology assumptions and should
be described accordingly.

------------------------------------------------------------------------

## 25. Convergence

Optimization termination does not automatically prove a global optimum.

For local optimization, convergence means the selected algorithm met its
numerical stopping criteria.

For evolutionary optimization, termination means the configured
generation/evaluation criterion was reached.

The result should therefore be reported as the optimum or Pareto set
**found under the specified algorithm, bounds, constraints, and
technology assumptions**.

------------------------------------------------------------------------

## 26. Reproducibility

For OpenMDAO optimization, report:

-   driver;
-   tolerances/settings;
-   design-variable bounds;
-   objective;
-   constraints;
-   derivative method;
-   initial design.

For pymoo, additionally report:

-   algorithm;
-   population size;
-   number of generations/evaluations;
-   random seed;
-   termination criterion.

------------------------------------------------------------------------

## 27. Recommended Optimization Header

``` python
# ============================================================
# OPTIMIZATION DEFINITION
# ============================================================
# Architecture:
#
# Fixed mission requirements:
#
# Design variables and bounds:
#
# Technology assumptions:
#
# Objective(s):
#
# Constraints:
#   convention: g <= 0 is feasible
#
# Algorithm:
#
# Termination:
#
# Random seed (if applicable):
# ============================================================
```

------------------------------------------------------------------------

## 28. Recommended Optimization Output

For each final design or selected Pareto point, report:

``` text
Design variables
Geometry
OEW / MTOW
Propulsion mass
Power-system/storage mass
Required/rated power
Fuel/H2/battery requirement
Objective values
All active constraints
Overall feasibility
Algorithm/evaluation information
```

This allows the result to be interpreted physically rather than only
numerically.

------------------------------------------------------------------------

## 29. Avoiding False Optima

An apparent optimum should be investigated if it lies exactly on:

-   an internal numerical floor;
-   a clipped efficiency;
-   a minimum volume;
-   a maximum/minimum empirical correlation;
-   an arbitrary design bound.

Such a point may be optimizer-driven by model safeguards rather than
physics.

------------------------------------------------------------------------

## 30. Verification of an Optimized Design

After optimization:

1.  take the final design variables;
2.  run the final candidate independently with `run_model()`;
3.  retrieve all important outputs;
4.  verify all constraints;
5.  inspect active safeguards;
6.  confirm mass/resource balance;
7.  save the final case.

This final independent evaluation is recommended even when the optimizer
reports success.

------------------------------------------------------------------------

## 31. Optimization Does Not Replace Engineering Interpretation

The optimizer only solves the mathematical problem supplied to it.

If a required physical constraint is omitted, the optimizer is free to
exploit that omission.

Therefore,

$$ \boxed{
\text{optimization quality}
\le
\text{quality/completeness of the physical model and constraints}.
} $$

------------------------------------------------------------------------

## 32. Summary

ADaPT optimization consists of two distinct layers:

$$ \boxed{
\text{ADaPT physics}
+
\text{optimization algorithm}.
} $$

OpenMDAO and pymoo provide complementary search strategies around the
same multidisciplinary model.

The user must clearly define:

$$ \boxed{
\text{fixed requirements}
+
\text{design variables}
+
\text{bounds}
+
\text{objectives}
+
\text{constraints}
+
\text{algorithm}.
} $$

The final design should always be interpreted through its physical
outputs and feasibility constraints, not only through the optimizer's
success flag.

---
# 11. Interpreting Outputs

# Interpreting Outputs

> **NOTE**
>
> Purpose of this page  This page explains how to read ADaPT results at vehicle level. It distinguishes **component outputs**, **coupling variables**, **final sizing results**, **required and installed quantities**, **constraints**, and **validation metrics** so that a numerically completed run is not mistaken for a physically feasible design.

## 1. Start with the Analysis Mode

Before interpreting any number, identify the analysis mode.

The meaning of an output depends on whether the run is:

-   validation;
-   forward mission analysis;
-   clean-sheet sizing;
-   optimization;
-   DSE;
-   sensitivity analysis;
-   payload--range analysis.

For example, final length is:

-   not independently predicted if prescribed in validation;
-   simply the fixed vehicle length in forward analysis;
-   a sizing result after optimization.

------------------------------------------------------------------------

## 2. Four Questions to Ask for Every Output

For each reported quantity, ask:

1.  **Who calculated it?**
2.  **What physical quantity does it represent?**
3.  **Is it a final result or an intermediate coupling variable?**
4.  **Is the design feasible at this value?**

This is more informative than reading a raw variable name alone.

------------------------------------------------------------------------

## 3. Component Output versus Vehicle-Level Result

Suppose Weight outputs

``` text
mtow
```

and Performance consumes it.

Then MTOW is simultaneously:

$$ \boxed{\text{Weight component output}} $$

$$ \boxed{\text{Performance component input}} $$

$$ \boxed{\text{multidisciplinary coupling variable}} $$

and, after closure,

$$ \boxed{\text{vehicle-level sizing result}}. $$

These descriptions are all correct.

------------------------------------------------------------------------

## 4. Geometry Outputs

Representative geometry outputs include:

-   diameter;
-   gross volume;
-   wetted/gross area;
-   aerodynamic reference area;
-   tail areas;
-   ballonet volume;
-   structural geometry proxies.

These should be interpreted as the geometry implied by the current
candidate values such as length and fineness ratio.

### Gross volume

$$ V_{\rm gross} $$

is especially important because it affects:

-   buoyancy;
-   lifting-gas capacity;
-   structural mass;
-   internal-volume availability.

### Wetted versus reference area

Do not confuse

$$ S_{\rm wet} $$

with

$$ S_{\rm ref}. $$

They are used for different purposes.

------------------------------------------------------------------------

## 5. Mass Outputs

### OEW

``` text
owe
```

represents the current Weight-model operating-empty-weight convention.

It includes the vehicle and installed-system terms documented in the
Weight Theory Guide.

### MTOW

``` text
mtow
```

is the complete takeoff mass closure.

It should be one of the first quantities checked in a sizing study.

### Operational weight

``` text
operational_weight
```

follows the current code convention and should not be assumed to mean
the same thing as MTOW.

### Component masses

Inspect at least:

``` text
envelope mass
gondola mass
fin mass
framework mass, where applicable
landing-system mass
propulsion mass
power-system mass
battery/tank mass
helium mass
miscellaneous mass
```

The component breakdown often explains why one architecture is heavier
than another.

------------------------------------------------------------------------

## 6. Mass-Balance Diagnostics

Where available, inspect

``` text
mass_balance_error
```

or the corresponding closure diagnostic.

A very small value indicates that the implemented MTOW accounting is
internally consistent.

It does not by itself validate the physical accuracy of every component
mass.

$$ \boxed{
\text{mass-balance closure}
\neq
\text{mass-model validation}.
} $$

------------------------------------------------------------------------

## 7. Internal-Volume Outputs

Hydrogen, battery, power-system, ballonet, and lifting-gas requirements
can create internal-volume competition.

Representative outputs include:

``` text
he_max_volume
air_max_volume
power_system_volume
tank_installed_volume
envelope_volume_violation
```

A design can be mass-feasible but volume-infeasible.

Therefore internal-volume diagnostics should be inspected for
architectures with substantial storage volume.

------------------------------------------------------------------------

## 8. Performance Outputs

Representative performance results include:

-   drag;
-   required thrust;
-   required shaft power;
-   mission duration;
-   takeoff distance/performance;
-   landing distance/performance;
-   buoyancy/lift metrics.

These describe the performance of the current multidisciplinary
candidate, not an isolated aerodynamic body.

------------------------------------------------------------------------

## 9. Required Power versus Rated/Installed Power

This distinction is fundamental.

### Required power

$$ P_{\rm required} $$

is calculated from the mission/performance demand.

### Rated/installed power

$$ P_{\rm installed} $$

is the available propulsion capability.

The margin is determined from their difference.

For example,

$$ g_P = P_{\rm required} - P_{\rm installed}. $$

Thus a large installed power value is not itself a performance
requirement, and a required power value is not automatically the engine
rating.

------------------------------------------------------------------------

## 10. Power-System Outputs

Depending on architecture, inspect:

``` text
P_elec_total
P_ice_demand
P_fc_demand
P_bat_demand
P_solar_available
P_solar_used
rated_source_power
power_system_mass
power_system_volume
```

These diagnostics show how mission demand is converted and allocated.

The exact meaning of a power variable can be architecture-dependent; use
the Power Theory Guide for the detailed convention.

------------------------------------------------------------------------

## 11. Fuel Outputs

For combustion architectures, `fuel_flow` is typically reported in

$$ {\rm kg/s}. $$

Mission fuel requirement follows from integrating fuel flow over mission
duration.

A fuel-flow history should not be confused with total onboard fuel mass.

When reserve or installed-resource logic is used, distinguish:

``` text
mission consumed fuel
```

from

``` text
installed/onboard fuel.
```

------------------------------------------------------------------------

## 12. Hydrogen Outputs

For hydrogen architectures, inspect both:

-   hydrogen consumption;
-   tank/storage penalty.

A complete interpretation includes:

$$ m_{H_2,\rm mission}, \quad
m_{H_2,\rm installed}, \quad m_{\rm tank},
\quad V_{\rm tank}. $$

Hydrogen's high specific chemical energy does not eliminate the
storage-system mass and volume penalty.

------------------------------------------------------------------------

## 13. Battery Outputs

For battery architectures, important outputs include:

-   mission electrical energy;
-   required installed battery capacity;
-   battery mass;
-   battery volume;
-   usable installed energy;
-   conceptual series/parallel configuration diagnostics.

Battery capacity is not the same as mission-delivered energy because the
sizing model accounts for implemented efficiency, depth of discharge,
temperature factor, and packaging assumptions.

------------------------------------------------------------------------

## 14. Solar Outputs

Distinguish:

$$ P_{\rm solar,available} $$

from

$$ P_{\rm solar,used}. $$

Also distinguish:

$$ E_{\rm solar,generated} $$

from solar energy actually used to offset the mission load.

In the standard SolarBattery implementation, excess generated solar is
reported separately and is not automatically credited as battery
charging.

Therefore, do not calculate battery benefit from total generated solar
alone.

------------------------------------------------------------------------

## 15. Fuel-Cell Outputs

The PEMFC polarization model may report:

-   cell voltage;
-   current density;
-   available power;
-   maximum power;
-   efficiency;
-   hydrogen-flow diagnostic;
-   power shortfall;
-   capability margin/limited status.

A fuel-cell efficiency output should be interpreted at the modeled
operating point.

The generic Power model remains responsible for the architecture-level
resource/mass flow according to the configured coupling.

------------------------------------------------------------------------

## 16. Hybrid Outputs

For hybrid architectures, inspect actual source-demand diagnostics
rather than only the prescribed hybridization parameter.

Representative outputs include:

``` text
primary_power_fraction
battery_power_fraction_actual
solar_power_fraction_actual
```

For solar-hydrogen hybrid operation, the current allocation applies
solar first and then applies `tau` to the remaining demand.

Thus actual mission fractions may differ from a naive interpretation of
`tau`.


| 17. Feasibility C aPT uses `\boxed{g_i\le0\R terpretation: Constraint value | nstraints ghtarrow\text{feasible Meaning |
| --- | --- |
| (g\<0) (g=0) (g\>0) | Feasible with margin Active boundary Infeasible |
| is sign convention | should accompany every |

## 18. Overall Feasibility

A design is feasible only if **all required active constraints** are
satisfied.

$$ \boxed{
\text{overall feasible}
\iff
g_i\le0\quad\forall i.
} $$

Do not classify a candidate as feasible because only the power
constraint is satisfied.

Other possible limiting mechanisms include:

-   buoyancy;
-   lift;
-   energy/resource;
-   takeoff;
-   landing;
-   storage/internal volume;
-   architecture-specific capability.

------------------------------------------------------------------------

## 19. Active Constraints Explain the Design

If

$$ g_i\approx0, $$

constraint (i) is active or nearly active.

This often identifies the physical mechanism sizing the vehicle.

Examples:

``` text
power active     -> propulsion capability is limiting
buoyancy active  -> lifting capability is limiting
energy active    -> storage/resource is limiting
takeoff active   -> field performance is limiting
```

Active constraints are therefore engineering results, not merely
optimizer bookkeeping.

------------------------------------------------------------------------

## 20. Numerical Safeguards

A value can appear valid because an internal floor or clip is active.

Examples include:

-   minimum geometry;
-   clipped efficiency;
-   minimum propeller diameter;
-   minimum tank volume;
-   bounded current/operating region;
-   minimum battery capacity.

If an optimized result lies on such a safeguard, investigate it before
treating the point as a physical optimum.

------------------------------------------------------------------------

## 21. Validation Outputs

Validation outputs should be classified as:

``` text
REF  -> imposed reference value
CAL  -> calibration quantity
PRED -> independently predicted quantity
PERF -> predicted performance quantity
N/A  -> no independent reference available
```

Only `PRED`/appropriate `PERF` quantities with independent reference
data should normally be used to claim predictive agreement.

------------------------------------------------------------------------

## 22. Percentage Error

For an independently predicted quantity,

$$ \epsilon = \frac{x_{\rm ADaPT}-x_{\rm ref}}
{x_{\rm ref}} \times100%. $$

Absolute percentage error is

$$ \|\epsilon\|. $$

The sign can be useful:

``` text
positive -> ADaPT overpredicts
negative -> ADaPT underpredicts
```

Do not calculate a meaningful "validation error" for a quantity that was
directly imposed from the reference data.

------------------------------------------------------------------------

## 23. Forward-Analysis Outputs

For a fixed Airship, interpret outputs as:

$$ \boxed{\text{performance of this Airship on this mission}.}
$$

For example, if the run returns a positive power constraint, the
conclusion is:

> the specified Airship/mission combination requires more power than
> the installed capability under the model assumptions.

It does not mean the optimizer should automatically enlarge the vehicle,
because no sizing loop is active.

------------------------------------------------------------------------

## 24. Optimization Outputs

For an optimized design, report:

### Final design variables

$$ L^*,FR\^*,BR^\*,\ldots $$

### Vehicle sizing outputs

$$ V^*,OEW\^*,MTOW^\*,\ldots $$

### Architecture outputs

fuel/H₂/battery/solar quantities and subsystem masses.

### Objectives

final objective value(s).

### Constraints

all active constraint values.

### Numerical information

convergence/evaluation count and algorithm where relevant.

An optimizer success message alone is not a complete result.

------------------------------------------------------------------------

## 25. DSE Outputs

DSE results normally contain both feasible and infeasible samples.

Do not discard infeasible points automatically.

They reveal:

-   boundaries;
-   nonlinear coupling;
-   failure modes;
-   architecture limitations.

Plots should clearly distinguish feasible from infeasible samples.

------------------------------------------------------------------------

## 26. Pareto Outputs

In multi-objective studies, background sampled points and
Pareto/non-dominated solutions have different meanings.

The Pareto front represents designs for which one objective cannot be
improved without worsening at least one other objective.

It does not mean every Pareto point is equally desirable.

Engineering selection still requires preference, robustness, technology
confidence, and feasibility interpretation.


| 27. Architecture Comparison r architecture comparison, in recommended comparison includ Category | pect complete vehicle quantities. s: Example outputs |
| --- | --- |
| Vehicle Propulsion Energy Storage Solar Performance Environmental/energy metric Feasibility | length, volume, OEW, MTOW required/rated power, propulsion mass fuel/H₂/battery requirement battery/tank mass and volume available/used energy takeoff/landing, mission metrics PFEI where used all constraints |
| oid ranking architectures usi | g only one subsystem efficiency. |

## 28. Common-Design Comparison

When all architectures are evaluated on a common vehicle geometry,
interpret the result as:

$$
\boxed{\text{effect of changing architecture on a controlled vehicle}.}
$$

An architecture may be infeasible because the common geometry was
originally suited to another architecture.

That is still a meaningful result.

------------------------------------------------------------------------

## 29. Architecture-Specific Redesign

When each architecture is allowed to resize/optimize independently,
interpret the result as:

$$
\boxed{\text{best feasible design found for that architecture under its bounds and assumptions}.}
$$

This is not directly the same experiment as common-design substitution.

Both comparisons should be labeled clearly.

------------------------------------------------------------------------

## 30. Sensitivity Outputs

A sensitivity indicates response to a parameter change.

For a quantity (y) and parameter (x),

$$ S = \frac{\Delta y}{\Delta x} $$

is an absolute sensitivity.

A normalized elasticity may be written as

$$ \mathcal{E} = \frac{\Delta y/y}{\Delta x/x}. $$

Interpretation:

``` text
|elasticity| > 1 -> proportionally strong response
|elasticity| < 1 -> proportionally weaker response
sign              -> direction of response
```

The exact definition used by a study script should be stated with its
figure/table.

------------------------------------------------------------------------

## 31. Technology-Threshold Outputs

A technology-threshold study asks what improvement is required before a
design becomes feasible or competitive.

The threshold should be associated with:

-   the exact technology parameter;
-   the mission;
-   architecture;
-   design/redesign assumption;
-   constraint/objective defining the threshold.

A threshold is not a universal technology requirement outside that study
context.

------------------------------------------------------------------------

## 32. Payload--Range Outputs

Payload--range analysis identifies feasible combinations of

$$ (m_{\rm payload},R). $$

A boundary point means the mission is close to one or more active
feasibility limits.

The physically limiting constraint should be reported where possible.

This makes the payload--range curve more informative than a simple
feasible/infeasible line.

------------------------------------------------------------------------

## 33. NaN, Inf, and Failed Cases

A `NaN`, `Inf`, exception, or solver failure is not a valid physical
result.

Record such cases explicitly:

``` text
status = failed
reason = ...
```

Do not replace them silently with zero.

For optimization/DSE, failure handling should ensure such candidates are
treated as infeasible.

------------------------------------------------------------------------

## 34. Zero Values

A zero can have several meanings:

-   physically zero;
-   architecture not using that subsystem;
-   disabled option;
-   initialized/default diagnostic;
-   numerical fallback.

Therefore inspect the architecture and variable definition before
interpreting a zero.

For example, battery mass should naturally be zero in an architecture
whose battery model is inactive.

------------------------------------------------------------------------

## 35. Output Units

Always report units.

Prefer:

``` text
MTOW = ... kg
Required shaft power = ... kW
Tank volume = ... m^3
Mission energy = ... kWh
Range = ... km
```

Do not rely on the reader knowing the internal OpenMDAO unit.

------------------------------------------------------------------------

## 36. Significant Figures

Conceptual-design results should not be reported with unjustified
precision.

The code may return many decimal places, but model uncertainty,
empirical correlations, and technology assumptions usually do not
support that level of precision.

Use enough digits to reproduce comparisons while avoiding false
accuracy.

------------------------------------------------------------------------

## 37. Recommended Results Summary

``` text
============================================================
ADaPT RESULTS
============================================================
Analysis mode:
Architecture:

MISSION
  Payload:
  Range:
  Cruise altitude:
  Cruise speed:

FINAL VEHICLE
  Length:
  Fineness ratio:
  Gross volume:
  OEW:
  MTOW:

PROPULSION / ENERGY
  Required power:
  Rated/installed power:
  Propulsion mass:
  Power-system mass:
  Fuel/H2/battery requirement:
  Tank/battery volume:

PERFORMANCE
  Mission duration:
  Takeoff:
  Landing:
  Other primary metrics:

CONSTRAINTS
  Power:
  Energy:
  Buoyancy:
  Lift:
  Takeoff:
  Landing:

OVERALL FEASIBLE: YES / NO
============================================================
```


| 38. Recommended Arch Metric | tecture-Compar Conventional | son Table Hydrogen | Battery | Solar |
| --- | --- | --- | --- | --- |
| Length Gross volume OEW MTOW Propulsion mass Storage/system mass Required power Mission resource PFEI Limiting constraint Feasible? |  |  |  |  |
| ly include columns/ar | hitectures act | ally used | n the stu | y. |

## 39. Five Levels of Output Interpretation

A useful hierarchy is:

### Level 1 --- Did the code run?

No exception/NaN.

### Level 2 --- Did the multidisciplinary model close?

Mass/coupling diagnostics are consistent.

### Level 3 --- Is the candidate feasible?

All active (g_i\le0).

### Level 4 --- Is the result physically credible?

No inappropriate safeguard domination; assumptions/applicability are
respected.

### Level 5 --- Is the result validated or useful for comparison?

Reference agreement, uncertainty, and study context support the intended
conclusion.

$$ \boxed{
\text{successful execution}
\neq
\text{feasibility}
\neq
\text{validation}.
} $$

------------------------------------------------------------------------

## 40. Summary

ADaPT outputs should be read as an interconnected vehicle result.

The central interpretation chain is

$$ \boxed{
\text{geometry}
\rightarrow
\text{mass}
\rightarrow
\text{performance}
\rightarrow
\text{power}
\rightarrow
\text{energy/storage}
\rightarrow
\text{mass}
}. $$

A result is meaningful only when its analysis mode, architecture, units,
assumptions, and feasibility status are known.

The most important reporting rule is therefore:

$$ \boxed{
\text{report the design}
+
\text{report the mission}
+
\text{report the constraints}
+
\text{report the assumptions}.
} $$
