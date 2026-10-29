# Expected User Knowledge

The Airship Design Tool is intended primarily for aerospace researchers, students, conceptual-design engineers, and developers interested in airship design and alternative propulsion architectures.

The level of knowledge required depends on how the framework is being used.

## Airship Design

Users interpreting the physical results should have a basic understanding of:

- Aerostatic lift and buoyancy
- Lifting gases
- Airship geometry
- Aerodynamic drag
- Propulsion and propeller performance
- Vehicle mass estimation
- Range and endurance
- Mission energy
- Stability and control
- Conceptual vehicle sizing

Carichner and Nicolai provide a suitable theoretical background for these topics. Their text specifically covers aerostatics, aerodynamics, performance, propulsion, weights, structures/materials, subsystems, stability/control, and integrated airship design.

The book itself is aimed at upper-level undergraduate students, graduate students, and practicing engineers.

## Python

Basic familiarity with Python is recommended.

Users running existing cases should be comfortable with:

```python
import numpy as np
```

basic Python data structures, running Python scripts from a terminal or IDE, and reading traceback/error messages.

Developers modifying components should have a stronger understanding of Python classes, inheritance, modules, NumPy arrays, and object-oriented programming.

## OpenMDAO

Basic OpenMDAO knowledge is strongly recommended for users modifying the core model.

In particular, developers should understand the concepts of:

- `om.Problem`
- `om.Group`
- `om.ExplicitComponent`

together with component inputs and outputs, promoted variables, model connections, solvers, design variables, constraints, objectives, and drivers.

The current model consists predominantly of OpenMDAO `ExplicitComponent` objects assembled through `AirshipAnalysisGroup`.

Aviary similarly assumes increasing OpenMDAO knowledge as users progress from running existing models toward modifying subsystems and developing custom analyses.

## Optimization

Users performing design-space exploration or optimization should also understand the distinction between:

$$ \text{design variables},\qquad \text{constraints},\qquad \text{objectives},\qquad \text{model outputs}. $$

Knowledge of DOE, gradient-based optimization, evolutionary optimization, Pareto optimality, and sensitivity analysis is beneficial for advanced studies.
