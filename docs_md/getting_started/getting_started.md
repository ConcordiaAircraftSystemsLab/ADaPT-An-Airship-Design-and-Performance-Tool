# Getting Started

The Airship Design Tool can be used at several levels.

- A **new user** may begin by running an existing reference configuration.
- **More experienced users** can modify mission requirements, vehicle parameters, propulsion architecture, or technology assumptions.
- **Advanced users** can directly interact with the OpenMDAO model to perform optimization, design-space exploration, sensitivity analysis, validation, or development of additional subsystem models.

This follows the same general philosophy used by Aviary: provide an integrated sizing capability while allowing individual subsystem models and analysis methods to be modified or extended.

## Core Capabilities

The computational model is organized around the following major analysis areas.

| Analysis area | Primary responsibility |
|---|---|
| Operating conditions | Atmospheric, gas, and fuel properties |
| Atmosphere | Pressure, temperature, and density |
| Geometry | Hull, wetted area, fins, ballonets, structural geometry |
| Aerostatics / Mass | Buoyancy, helium requirements, structural and subsystem masses, OEM and MTOM |
| Mission | Design-point mission performance |
| Propulsion | Shaft power, propeller sizing, prime mover and installation mass |
| Power | Propulsion-energy architecture sizing |
| Hydrogen tank | Hydrogen storage, insulation, structural and delivery-system sizing |
| Battery | Battery-electric energy storage |
| Solar-battery | Solar generation and battery hybridization |
| Fuel cell | Load-dependent PEMFC performance |
| Mission profile | Post-design mission and power-allocation analysis |
| Integrated model | Multidisciplinary coupling and model assembly |

This mapping follows the actual current repository structure.

## Design Studies

The core physics models are deliberately separated from scripts used to investigate the resulting design space.

- The `studies/` directory contains design-space exploration, optimization, sensitivity, payload-range, and related trade-study analyses.
- The `validation/` directory contains independent validation/regression cases.

Conceptually, the framework is therefore divided into:

```text
                    AIRSHIP DESIGN TOOL
                           │
            ┌──────────────┴──────────────┐
            │                             │
       CORE PHYSICS                  ANALYSIS LAYER
            │                             │
     ┌──────┼───────┐              ┌──────┼───────┐
     │      │       │              │      │       │
 Geometry  Mass  Propulsion       DOE   Optimization
     │      │       │              │      │
 Atmosphere│     Energy       Sensitivity Analysis
     │      │       │              │
     └──── Mission ─┘         Payload–Range Studies
            │
      Coupled Sizing
```

The distinction is important: a design study *uses* the core model; it does not redefine the underlying airship physics.
