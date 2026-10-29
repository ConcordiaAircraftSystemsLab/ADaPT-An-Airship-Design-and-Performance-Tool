# What's Next?

After installation, users can approach the documentation according to what they want to accomplish.

- A user interested primarily in **running the tool** should continue to the **User Guide**, which will explain how an airship configuration is defined, how propulsion architectures are selected, how mission requirements are specified, how analyses are executed, and how outputs are interpreted.
- A user interested in **understanding how the airship is actually calculated** should proceed to the **Theory Guide**.
- A **developer** who wants to modify or extend the Python implementation should instead consult the **Developer Guide**.
- Users interested in **evidence supporting the models** should consult **Verification and Validation**.

Aviary uses essentially this progressive documentation philosophy: introductory material leads into a User Guide, while a separate Theory Guide explains equations and modeling assumptions and a Developer Guide addresses code modification.

## Structure of the Theory Guide

The Theory Guide will document the physical formulation at equation level:

```text
Theory Guide
│
├── Modeling Philosophy and Conventions
├── Atmosphere and Operating Conditions
├── Geometry
├── Aerostatics and Buoyancy
├── Aerodynamics
├── Mass Estimation
├── Propulsion
├── Power and Energy Systems
│   ├── Conventional
│   ├── Hydrogen combustion
│   ├── Fuel cell
│   ├── Battery
│   └── Solar-battery
├── Hydrogen Storage
├── Mission Performance
├── Environmental / Energy Metrics
└── Coupled Airship Sizing
```

## Standard Content per Model

For every computational model, the Theory Guide will provide:

$$ \boxed{ \begin{array}{c} \text{Purpose}\\ \downarrow\\ \text{Inputs}\\ \downarrow\\ \text{Governing equations}\\ \downarrow\\ \text{Constants/parameters}\\ \downarrow\\ \text{Assumptions}\\ \downarrow\\ \text{Outputs}\\ \downarrow\\ \text{Model coupling}\\ \downarrow\\ \text{Source/provenance}\\ \downarrow\\ \text{Verification/validation} \end{array}} $$

This is where the documentation will deliberately become more detailed than the introductory material.
