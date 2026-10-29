# Optimization Algorithms

Optimization drivers numerically search the ADaPT design space after the multidisciplinary airship analysis problem has been defined.

Within ADaPT, an optimizer repeatedly changes selected **system-level design variables**, runs the complete coupled airship model, evaluates one or more objective functions and feasibility constraints, and then determines the next candidate design.

A useful distinction is

$$
\boxed{
\text{analysis model}
\neq
\text{solver}
\neq
\text{optimizer}.
}
$$

The analysis model contains the physical disciplines. A solver closes coupled equations inside that analysis. An optimizer changes design variables in order to improve a system-level objective while satisfying constraints.

ADaPT supports two complementary optimization routes:

1. **OpenMDAO-based optimization**, in which the optimization driver operates directly on the OpenMDAO model hierarchy.
2. **pymoo-based optimization**, in which an external optimization algorithm treats the complete OpenMDAO analysis as a callable multidisciplinary evaluation.

The two approaches use the same physical model. They differ primarily in how the design space is searched.

---

## 1. Optimization in the ADaPT Workflow

The conceptual design problem can be written as

$$
\boxed{
\begin{aligned}
\min_{\mathbf{x}}\quad & f(\mathbf{x})\\
\text{subject to}\quad
& g_j(\mathbf{x})\le0,
\qquad j=1,\ldots,n_g,\\
& \mathbf{x}_L\le\mathbf{x}\le\mathbf{x}_U.
\end{aligned}
}
$$

where

- $\mathbf{x}$ is the vector of design variables,
- $f$ is the objective function,
- $g_j$ are inequality constraints,
- $\mathbf{x}_L$ and $\mathbf{x}_U$ are lower and upper variable bounds.

For multiobjective studies, the objective becomes a vector,

$$
\boxed{
\mathbf{F}(\mathbf{x})
=
[
f_1(\mathbf{x}),
f_2(\mathbf{x}),
\ldots
].
}
$$

A typical ADaPT optimization therefore follows

$$
\boxed{
\begin{array}{c}
\text{Mission requirements}\\
\downarrow\\
\text{Optimizer selects candidate design } \mathbf{x}\\
\downarrow\\
\text{Geometry}\\
\downarrow\\
\text{mass + Atmosphere + Performance}\\
\downarrow\\
\text{Propulsion + Power + Energy storage}\\
\downarrow\\
\text{Coupled vehicle outputs}\\
\downarrow\\
f,\;g_1,\ldots,g_n\\
\downarrow\\
\text{Optimizer updates }\mathbf{x}\\
\circlearrowleft
\end{array}
}
$$

---

## 2. What Is an Optimization Input?

The phrase **optimization input** must be distinguished from a component input.

Suppose `length` is passed into the Geometry component.

At component level,

```text
length = Geometry input
```

but in a clean-sheet optimization,

```text
length = system-level design variable
```

and after convergence,

```text
length = final sizing result.
```

Likewise, `MTOM` is

```text
output of mass
```

but

```text
input to Performance.
```

At the system level, MTOM is a coupling variable and usually a final design result rather than an independently selected input.

Therefore optimization documentation should always identify the **system-level role** of a quantity rather than relying only on the OpenMDAO words `input` and `output`.

---

## 3. Mission Requirements versus Design Variables

A normal clean-sheet sizing study holds the mission definition fixed while allowing the vehicle design to change.

Typical mission requirements are

$$
\boxed{
m_{\mathrm{payload}},
\quad
R,
\quad
h_{\mathrm{cruise}},
\quad
V_{\mathrm{cruise}},
\quad
\text{propulsion architecture}.
}
$$

Typical candidate design variables may include

$$
\boxed{
L,
\quad
FR,
\quad
BR,
\quad
C_{HT},
\quad
C_{VT},
\quad
P_{\mathrm{installed}},
\quad
\eta_p,
}
$$

together with architecture-specific technology variables.

The optimizer does **not** decide what payload or range the mission requires unless the study explicitly formulates those quantities as trade variables.

---

## 4. Design Variables

A design variable is a quantity that the optimizer is permitted to modify.

A general ADaPT design vector can be represented as

$$
\boxed{
\mathbf{x}
=
[
x_1,x_2,\ldots,x_n
].
}
$$

Possible variables fall into several categories.

### Geometry variables

Examples include

$$
L,
\quad
FR,
\quad
C_{HT},
\quad
C_{VT}.
$$

### Aerodynamic/performance variables

Examples include

$$
BR_{TO},
\quad
C_L,
\quad
K,
\quad
\eta_p.
$$

### Propulsion variables

Examples include

$$
P_{\mathrm{installed}},
\quad
N_{\mathrm{engine}},
$$

and technology-specific efficiency or specific-power parameters.

### Energy-system variables

Examples can include

$$
SE_b,
\quad
\eta_{PV},
\quad
A_{PV},
\quad
\tau,
\quad
\chi,
$$

depending on the architecture and purpose of the study.

Not all of these should be optimized simultaneously in every study. The design vector should reflect the actual engineering question being asked.

---

## 5. Objectives

An objective is the system-level quantity that the optimizer seeks to minimize or maximize.

Examples relevant to ADaPT include

$$
\min(MTOM),
$$

$$
\min(\text{fuel or hydrogen consumption}),
$$

$$
\min(\text{energy intensity}),
$$

$$
\min(\text{takeoff distance}),
$$

or

$$
\max(\text{payload--range capability}).
$$

A multiobjective study may consider several quantities simultaneously, for example

$$
\boxed{
\min
[
MTOM^*,
PFEI,
-\text{payload--range transport work}
].
}
$$

The negative sign converts a maximization objective into minimization form when required by the optimization interface.

---

## 6. Constraints

The updated ADaPT framework follows

$$
\boxed{
g(\mathbf{x})\le0
\quad\Rightarrow\quad
\text{feasible}.
}
$$

Important constraints include:

$$
g_P
=
P_{\mathrm{required}}
-
P_{\mathrm{installed}},
$$

$$
g_E
=
\text{required resource}
-
\text{installed resource},
$$

$$
g_B
=
L_{\mathrm{buoy,required}}
-
L_{\mathrm{buoy,available}},
$$

$$
g_L
=
C_{L,\mathrm{required}}
-
C_{L,\max},
$$

$$
g_{TO}
=
S_{TO}
-
S_{TO,\max},
$$

and

$$
g_{LDG}
=
S_{LDG}
-
S_{LDG,\max}.
$$

The common sign convention is useful because both OpenMDAO and external optimization wrappers can use the same physical constraint outputs directly.

---

# Part I — OpenMDAO-Based Optimization

## 7. OpenMDAO Drivers

In OpenMDAO, an optimizer is implemented as a **driver**.

The driver:

1. sets the current design variables,
2. runs the multidisciplinary model,
3. obtains objectives and constraints,
4. obtains or approximates derivatives when required,
5. selects the next design point.

Conceptually,

```python
prob.driver = ...
prob.model.add_design_var(...)
prob.model.add_objective(...)
prob.model.add_constraint(...)
prob.run_driver()
```

The optimizer therefore operates directly on the OpenMDAO computational graph.

---

## 8. Optimizer versus Solver

This distinction is important.

A nonlinear or linear **solver** is used to satisfy coupled equations such as

$$
\mathbf{R}(\mathbf{y},\mathbf{x})=0.
$$

Examples include Newton-type nonlinear solvers and linear-system solvers.

An **optimizer** solves the outer design problem,

$$
\min_{\mathbf{x}} f(\mathbf{x})
$$

subject to constraints.

Therefore,

$$
\boxed{
\text{solver closes analysis coupling;}
\qquad
\text{optimizer changes the design}.
}
$$

An MDAO problem may use both simultaneously.

---

## 9. Gradient-Based Optimization

OpenMDAO is particularly well suited to gradient-based optimization.

A gradient-based method uses information such as

$$
\frac{\partial f}{\partial x_i}
$$

and

$$
\frac{\partial g_j}{\partial x_i}.
$$

These derivatives indicate how the objective and constraints change when a design variable changes.

Gradient information generally allows efficient optimization when:

- the problem is smooth,
- derivatives are accurate,
- the number of variables is moderate or large,
- the design space is locally well behaved.

For strongly coupled MDAO problems, derivative-based optimization can require substantially fewer expensive model evaluations than purely population-based search.

---

## 10. SLSQP

SLSQP stands for **Sequential Least Squares Programming**.

It is available in OpenMDAO through `ScipyOptimizeDriver`.

A typical ADaPT setup is conceptually

```python
prob.driver = om.ScipyOptimizeDriver()
prob.driver.options["optimizer"] = "SLSQP"
```

SLSQP is useful for:

- continuous variables,
- nonlinear objectives,
- nonlinear inequality/equality constraints,
- relatively small or medium conceptual design problems.

It is attractive for ADaPT because SciPy is widely available and no external commercial optimizer is required.

### Advantages

- straightforward installation,
- direct OpenMDAO integration,
- supports nonlinear constrained optimization,
- suitable for local refinement,
- efficient when derivatives are reliable.

### Limitations

- local optimizer,
- sensitive to initial design,
- can struggle with nonsmooth constraints,
- finite-difference noise can degrade convergence,
- discrete variables are not naturally handled.

---

## 11. IPOPT

IPOPT is an interior-point nonlinear programming optimizer and can be accessed in OpenMDAO through `pyOptSparseDriver` when the required software is installed.

IPOPT is designed for large continuous constrained optimization problems.

It is particularly useful when:

- many continuous variables are present,
- gradients are available,
- the coupled problem is smooth,
- inequality constraints are numerous.

For future high-dimensional ADaPT studies, IPOPT can provide a useful alternative to SLSQP.

---

## 12. SNOPT

SNOPT is a Sequential Quadratic Programming optimizer available through `pyOptSparse`.

It is widely used in multidisciplinary design optimization because it is robust for large sparse nonlinear constrained problems.

SNOPT can be appropriate when ADaPT contains:

- many continuous design variables,
- many constraints,
- reliable gradients,
- tightly coupled disciplines.

Licensing and installation requirements should be checked before selecting it.

---

## 13. Derivatives in the Current ADaPT Model

Many present ADaPT components declare finite-difference partial derivatives.

A generic relation is

$$
\boxed{
\frac{\partial y}{\partial x}
\approx
\frac{
y(x+\Delta x)-y(x)
}{
\Delta x
}.
}
$$

Finite differences allow gradient-based optimization without deriving every analytic Jacobian manually.

However, several ADaPT components contain operations such as

- `max`,
- `min`,
- `clip`,
- integer rounding,
- architecture branches,
- capacity switching,
- discrete architecture selections.

These introduce nonsmoothness.

Consequently, derivative-based optimizers should be used with derivative checking and appropriate scaling.

---

## 14. Why Scaling Matters

Airship optimization variables can differ greatly in magnitude.

For example,

$$
C_L\sim10^{-1},
$$

while

$$
P\sim10^5~{\rm W},
$$

and

$$
MTOM\sim10^3-10^5~{\rm kg}.
$$

Poor scaling can produce an ill-conditioned optimization problem.

OpenMDAO allows design variables, objectives, and constraints to be scaled using `ref`, `ref0`, `scaler`, or `adder`.

Conceptually,

$$
\boxed{
\tilde{x}
=
\frac{x-x_0}{x_{\mathrm{ref}}-x_0}.
}
$$

Good scaling makes different optimization quantities numerically comparable and can substantially improve convergence.

---

## 15. OpenMDAO-Based Optimization Workflow

A typical ADaPT gradient-based study follows:

```text
1. Build AirshipAnalysisGroup.
2. Define mission requirements.
3. Declare system-level design variables.
4. Define objective(s).
5. Add physical and operational constraints.
6. Select OpenMDAO optimization driver.
7. Scale variables and constraints.
8. Run derivative checks.
9. Run the optimizer.
10. Re-run the converged design independently.
11. Verify all constraints.
12. Save the final design and convergence history.
```

---

# Part II — pymoo-Based Optimization

## 16. Why ADaPT Also Uses pymoo

Not every airship design problem is well suited to a gradient-based local optimizer.

ADaPT contains:

- architecture-dependent equations,
- clipping and saturation,
- discrete choices,
- empirical correlations,
- possible disconnected feasible regions,
- strong nonlinear mass-energy-propulsion coupling.

For such studies, a derivative-free population-based optimizer can be valuable.

ADaPT therefore also supports a pymoo wrapper around the OpenMDAO analysis.

---

## 17. OpenMDAO Remains the Physics Model

Using pymoo does **not** create a second airship model.

The architecture is

$$
\boxed{
\text{pymoo optimizer}
\rightarrow
\text{OpenMDAO ADaPT model}
\rightarrow
f,\mathbf{g}
\rightarrow
\text{pymoo optimizer}.
}
$$

OpenMDAO still evaluates:

- geometry,
- mass,
- atmosphere,
- performance,
- propulsion,
- power,
- batteries,
- solar system,
- hydrogen tank,
- multidisciplinary constraints.

pymoo only controls the outer design-space search.

---

## 18. pymoo Problem Wrapper

A typical wrapper derives from

```python
ElementwiseProblem
```

and defines:

- number of design variables,
- number of objectives,
- number of inequality constraints,
- lower bounds,
- upper bounds.

Each candidate design

$$
\mathbf{x}
$$

is mapped into OpenMDAO variables.

The model is then executed:

```python
prob.run_model()
```

and outputs are converted into

```python
out["F"]
```

for objectives and

```python
out["G"]
```

for constraints.

---

## 19. Current Zeppelin pymoo Example

The current validation/design-study driver uses six variables:

$$
\boxed{
\mathbf{x}
=
[
BR_{TO},
C_{HT},
C_{VT},
C_L,
K,
\eta_p
].
}
$$

The bounds are

$$
0.50\le BR_{TO}\le0.99,
$$

$$
0.05\le C_{HT}\le0.09,
$$

$$
0.04\le C_{VT}\le0.08,
$$

$$
0.12\le C_L\le0.22,
$$

$$
0.45\le K\le1.00,
$$

$$
0.70\le\eta_p\le0.90.
$$

This should be described as a **limited parameter/design optimization**, not a clean-sheet sizing problem, because primary geometry variables such as length are not included in that design vector.

---

## 20. Differential Evolution

The present Zeppelin pymoo driver uses **Differential Evolution (DE)**.

DE is a derivative-free population-based evolutionary algorithm.

Instead of relying on

$$
\nabla f,
$$

it generates candidate designs by combining differences between members of the current population.

A simplified mutation concept is

$$
\boxed{
\mathbf{v}
=
\mathbf{x}_{r1}
+
F
(
\mathbf{x}_{r2}
-
\mathbf{x}_{r3}
).
}
$$

The resulting candidate is crossed with another population member and retained according to objective and constraint performance.

The exact internal implementation is handled by pymoo.

---

## 21. Why Differential Evolution Is Useful for ADaPT

DE can be useful when:

- derivatives are unavailable or noisy,
- the model contains nonsmooth logic,
- local minima are possible,
- a broader search of the design space is desired,
- the problem has a modest number of design variables.

It is therefore complementary to SLSQP/IPOPT/SNOPT.

### Main disadvantages

Population methods typically require many more model evaluations.

If

$$
N_{pop}=160
$$

and

$$
N_{gen}=300,
$$

the theoretical evaluation count can be on the order of tens of thousands, depending on algorithm behavior and termination.

For expensive high-fidelity analysis, this can become prohibitive.

---

## 22. Initial Population

The current wrapper seeds the first DE population around the reference design while also sampling the rest of the bounded design space.

This combines:

- global coverage,
- at least one known reference point,
- several local perturbations around the baseline.

The strategy improves the probability that the population includes both physically reasonable designs and exploratory candidates.

---

## 23. Persistent OpenMDAO Problem

The pymoo implementation retains one OpenMDAO `Problem` object.

For each candidate,

$$
\mathbf{x}_k,
$$

the driver:

1. updates the selected OpenMDAO independent variables,
2. calls `prob.run_model()`,
3. reads the objective,
4. reads constraint outputs.

The OpenMDAO hierarchy is therefore not reconstructed for every individual.

This reduces wrapper overhead.

---

## 24. Constraint Handling in pymoo

The updated ADaPT convention

$$
g\le0
$$

matches pymoo's inequality-constraint convention.

For example,

$$
P_{\mathrm{required}}
-
P_{\mathrm{installed}}
\le0
$$

can be supplied directly.

The current Zeppelin wrapper also includes bounds on MTOM and takeoff distance.

A typical constraint vector is

$$
\boxed{
\mathbf{G}
=
[
MTOM_{\min}-MTOM,\,
MTOM-MTOM_{\max},\,
S_{TO}-S_{\max},\,
g_B,\,
g_P,\,
g_E
].
}
$$

---

## 25. Failed Candidate Handling

A global optimizer will intentionally evaluate poor designs.

Some may cause:

- physically impossible geometry,
- singular equations,
- failed subsystem calculations,
- NaN values.

The current wrapper handles a failed candidate by assigning a very poor objective and large positive constraint violations.

Conceptually,

$$
f\rightarrow f_{\mathrm{penalty}}
$$

and

$$
g_i\rightarrow g_{\mathrm{large}}>0.
$$

This prevents a single failed design point from terminating the entire evolutionary search.

---

## 26. Penalty Terms

The optional Zeppelin objective includes an additional takeoff-distance penalty.

If

$$
S_{TO}>S_{\mathrm{limit}},
$$

the normalized violation is

$$
\boxed{
v
=
\max
\left(
0,
\frac{
S_{TO}-S_{\mathrm{limit}}
}{
S_{\mathrm{limit}}
}
\right).
}
$$

The objective includes both linear and quadratic penalty terms,

$$
\boxed{
J
=
\frac{S_{TO}}{S_{\mathrm{limit}}}
+
0.2BR
+
20v
+
100v^2.
}
$$

This causes strongly infeasible takeoff designs to become increasingly unattractive.

Because the takeoff-distance requirement is also passed as an explicit inequality constraint, the penalty is best interpreted as additional search guidance rather than the sole feasibility mechanism.

---

# Part III — Choosing Between OpenMDAO and pymoo

## 27. The Two Approaches Are Complementary

The two optimizer families should not be presented as competitors where one universally replaces the other.

They answer different numerical needs.

| Characteristic | OpenMDAO gradient-based | pymoo population-based |
|---|---|---|
| Uses derivatives | Usually yes | No |
| Model evaluations | Usually lower | Usually much higher |
| Local convergence | Strong | Less direct |
| Global exploration | Limited | Stronger |
| Nonsmooth models | Can be difficult | More tolerant |
| Discrete choices | Limited | Easier to accommodate |
| High-dimensional smooth MDO | Very effective | Often expensive |
| Multiobjective Pareto search | Possible but less direct | Natural strength |
| Good for refinement | Excellent | Good but expensive |
| Good for design-space exploration | Limited | Excellent |

---

## 28. Recommended ADaPT Optimization Strategy

A practical strategy is hierarchical.

### Stage 1 — Design-space exploration

Use sampling or a population-based method to understand:

- feasible regions,
- architecture behavior,
- major nonlinearities,
- parameter sensitivities.

### Stage 2 — Global or multiobjective search

Use pymoo where the goal is:

- broad design-space search,
- Pareto-front generation,
- nonsmooth optimization,
- comparison of architecture-specific feasible spaces.

### Stage 3 — Local refinement

Use SLSQP, IPOPT, or SNOPT when:

- a promising feasible region is known,
- variables are continuous,
- derivatives are sufficiently reliable.

This gives

$$
\boxed{
\text{explore globally}
\rightarrow
\text{identify feasible basin}
\rightarrow
\text{refine locally}.
}
$$

---

## 29. Single-Objective versus Multiobjective Optimization

A single-objective problem seeks one scalar optimum,

$$
\min f(\mathbf{x}).
$$

A multiobjective problem seeks a set of trade-off solutions.

For two competing objectives,

$$
f_1(\mathbf{x}),
\qquad
f_2(\mathbf{x}),
$$

a design is Pareto-optimal if improving one objective necessarily worsens at least one other objective.

The resulting set is the Pareto front.

This is particularly useful in alternative-propulsion airship design because objectives such as

$$
MTOM,
\quad
PFEI,
\quad
\text{payload--range capability}
$$

can conflict strongly.

pymoo is especially convenient for these Pareto-based studies.

---

## 30. Multiobjective Algorithms

pymoo provides several multiobjective evolutionary algorithms.

Algorithms such as NSGA-II can be used when an ADaPT study explicitly requires Pareto-front generation.

However, the optimizer documented as **currently used in the Zeppelin validation/design driver** is Differential Evolution for a single-objective problem.

Therefore documentation should distinguish:

```text
implemented in the cited study
```

from

```text
available through the optimization library.
```

---

## 31. Architecture Selection Is Not Automatically an Optimization Variable

ADaPT evaluates several propulsion architectures, including conventional, hydrogen, battery, solar, hybrid, turboprop, and turboelectric configurations.

In many studies, architecture is treated as an outer-loop case:

```text
run conventional
run hydrogen
run battery
run solar-battery
...
```

and each architecture has its own continuous design space.

This is often preferable to encoding propulsion architecture as a single continuous optimization variable because architecture is fundamentally discrete and changes the underlying physics/model structure.

The architecture-specific optimum can then be compared at system level.

---

## 32. Optimization versus Design-Space Exploration

Design-space exploration (DSE) and optimization are related but different.

DSE asks:

$$
\boxed{
\text{What does the design space look like?}
}
$$

Optimization asks:

$$
\boxed{
\text{Which feasible design is best according to the objective?}
}
$$

A DSE can reveal:

- nonlinear trends,
- disconnected feasible regions,
- sensitivity,
- architecture-specific boundaries,
- trade-offs.

An optimizer can then search those regions more efficiently.

For scientific interpretation, DSE is often as important as the final optimum.

---

## 33. Optimization versus Validation

Optimization must also be distinguished from validation.

Validation asks:

$$
\boxed{
\text{Does ADaPT reproduce known reference behavior?}
}
$$

Optimization asks:

$$
\boxed{
\text{What design should ADaPT select?}
}
$$

A reference aircraft should normally be validated **before** its design variables are optimized.

Otherwise an optimized match to reference data can become calibration rather than independent validation.

---

## 34. Inputs and Outputs of an Optimization Study

For clarity, every ADaPT optimization study should document four groups.

### Fixed requirements

Examples:

```text
payload
range
cruise altitude
architecture
field-length requirements
```

### Design variables

Examples:

```text
length
fineness ratio
buoyancy ratio
tail-volume coefficients
installed power
technology parameters
```

### Objective(s)

Examples:

```text
MTOM
PFEI
fuel burn
takeoff distance
payload-range transport work
```

### Constraints

Examples:

```text
power adequacy
energy capacity
buoyancy
lift
takeoff field length
landing field length
technology or geometry bounds
```

The final outputs are the optimized design variables together with all resulting vehicle characteristics.

---

## 35. Example of a Clean-Sheet Sizing Problem

Suppose the mission requirements are

$$
m_{\mathrm{payload}}=700~{\rm kg},
$$

$$
R=1000~{\rm km},
$$

and

$$
V_c=20~{\rm m/s}.
$$

A possible design vector is

$$
\mathbf{x}
=
[
L,
FR,
BR,
P_{\mathrm{installed}}
].
$$

The optimizer may minimize

$$
MTOM
$$

subject to

$$
g_P\le0,
$$

$$
g_E\le0,
$$

$$
g_B\le0,
$$

$$
g_L\le0,
$$

$$
g_{TO}\le0,
$$

$$
g_{LDG}\le0.
$$

The optimized result is then

$$
\boxed{
L^*,FR^*,BR^*,P_{\mathrm{installed}}^*,MTOM^*
}
$$

together with predicted subsystem masses and mission performance.

This is fundamentally different from the Zeppelin validation, where the known Zeppelin length and power are intentionally imposed.

---

## 36. Continuous and Discrete Variables

Some ADaPT variables are naturally continuous:

$$
L,\quad FR,\quad BR,\quad \eta,\quad A_{PV}.
$$

Others are discrete:

$$
N_{\mathrm{engine}},
\quad
N_{\mathrm{cells}},
\quad
\text{airship type},
\quad
\text{propulsion architecture}.
$$

Gradient-based optimization is naturally suited to continuous variables.

Discrete decisions can be handled through:

- outer-loop enumeration,
- mixed-variable evolutionary methods,
- architecture-by-architecture optimization,
- integer-aware optimization methods.

ADaPT currently benefits from architecture-by-architecture studies because each architecture has different governing equations and practical bounds.

---

## 37. Optimization Bounds

Every design variable requires physically meaningful lower and upper bounds.

For variable $x_i$,

$$
\boxed{
x_{i,L}
\le
x_i
\le
x_{i,U}.
}
$$

Bounds serve several roles:

- prevent unphysical designs,
- prevent numerical failure,
- limit search to the technology/design regime being studied,
- improve optimizer efficiency.

Bounds should be traceable to:

- geometry feasibility,
- reference vehicles,
- technology capability,
- certification constraints,
- or explicitly stated conceptual assumptions.

Bounds should not be chosen only to make the optimizer converge.

---

## 38. Convergence

A successful optimizer termination does not automatically imply a valid design.

After optimization, ADaPT should independently verify:

$$
g_i(\mathbf{x}^*)\le0
$$

for every constraint.

The final design should also be re-evaluated directly using

```python
prob.run_model()
```

rather than relying only on optimizer-internal values.

---

## 39. Optimization Diagnostics

Recommended quantities to store include:

- final design vector,
- objective value,
- all constraint values,
- feasibility status,
- number of function evaluations,
- convergence history,
- optimizer termination reason,
- random seed for stochastic algorithms,
- algorithm settings,
- failed-evaluation count.

These data are important for reproducibility.

---

## 40. Reproducibility for Evolutionary Algorithms

Population-based algorithms contain stochastic operations.

Therefore the random seed should be recorded.

For example,

```python
seed = 11
```

allows the same stochastic optimization experiment to be repeated.

A robust design study may also repeat the optimization using several different seeds to determine whether the same solution region is consistently recovered.

---

## 41. Verification of an Optimized Design

Every reported optimum should undergo a post-optimization audit:

1. Re-run the model at the exact final design vector.
2. Confirm all variables lie within bounds.
3. Confirm every physical constraint.
4. Confirm mass closure.
5. Confirm resource closure.
6. Confirm installed versus required power.
7. Check for active numerical clips/floors.
8. Check that the solution is not created by a numerical safeguard.
9. Perturb the design locally and verify that the objective behaves reasonably.
10. For stochastic optimization, compare with independent runs.

---

## 42. Recommended Algorithm Selection

A practical decision rule for ADaPT is:

| Problem characteristic | Suggested starting approach |
|---|---|
| Smooth, continuous, few/moderate variables | SLSQP |
| Smooth, large constrained problem | IPOPT or SNOPT |
| Nonsmooth/problematic derivatives | pymoo DE |
| Need broad global exploration | pymoo evolutionary method |
| Need Pareto front | pymoo multiobjective algorithm |
| Discrete architecture comparison | optimize architectures separately |
| Final local refinement | OpenMDAO gradient-based driver |

No single optimizer is expected to be best for every ADaPT study.

---

## 43. Current Documentation Status

ADaPT presently contains examples of both optimization families:

```text
OpenMDAO-based optimization
```

for optimization directly on the multidisciplinary model, and

```text
pymoo-based optimization
```

for derivative-free external search around the same OpenMDAO analysis.

The Zeppelin validation/design driver specifically demonstrates the second route using `ElementwiseProblem` and Differential Evolution.

The two routes should therefore be documented as complementary interfaces to the same physical framework.

---

## 44. Recommended Future Improvements

Future optimization development should include:

1. Centralize design-variable definitions and bounds.
2. Centralize objective and constraint naming.
3. Add explicit variable-role metadata:
   - mission requirement,
   - design variable,
   - coupling variable,
   - constraint,
   - objective,
   - reported result.
4. Improve analytic or complex-step derivatives for smooth components.
5. Remove unnecessary clips from regions intended for gradient optimization.
6. Add derivative verification to regression testing.
7. Add normalized/scaled optimization templates.
8. Provide separate examples for:
   - SLSQP,
   - IPOPT/SNOPT where available,
   - Differential Evolution,
   - multiobjective Pareto optimization.
9. Store convergence history automatically.
10. Add repeated-seed robustness checks for stochastic methods.
11. Add hybrid global-local optimization workflows.
12. Keep architecture selection separate from continuous optimization unless an explicit mixed-variable formulation is introduced.

---

## 45. Summary

ADaPT uses two complementary optimization paths.

### OpenMDAO route

$$
\boxed{
\text{OpenMDAO driver}
\rightarrow
\text{coupled ADaPT model}
\rightarrow
\text{gradients}
\rightarrow
\text{local constrained optimum}.
}
$$

This route is efficient when the design problem is smooth and derivatives are reliable.

### pymoo route

$$
\boxed{
\text{pymoo population}
\rightarrow
\text{OpenMDAO ADaPT evaluations}
\rightarrow
\text{objective + constraints}
\rightarrow
\text{global/evolutionary search}.
}
$$

This route is valuable for nonsmooth, multimodal, derivative-free, or Pareto-based studies.

The key modeling principle is the same in both cases:

$$
\boxed{
\text{mission requirements are prescribed;}
\quad
\text{design variables are changed;}
\quad
\text{coupling variables are calculated;}
\quad
\text{constraints determine feasibility;}
\quad
\text{objectives determine preference}.
}
$$

This separation is essential for interpreting an optimized airship correctly.

---

## References

- OpenMDAO, *Optimization Drivers*, OpenMDAO documentation:  
  <https://openmdao.org/newdocs/versions/latest/features/building_blocks/drivers/index.html>

- OpenMDAO Practical MDO, *Basic Optimization Problem Formulation*:  
  <https://openmdao.github.io/PracticalMDO/Notebooks/Optimization/basic_opt_problem_formulation.html>

- SciPy, *SLSQP*:  
  <https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html>

- IPOPT documentation:  
  <https://coin-or.github.io/Ipopt/>

- SNOPT documentation:  
  <https://web.stanford.edu/group/SOL/guides/sndoc7.pdf>

- pyOptSparse:  
  <https://github.com/mdolab/pyoptsparse>

- pymoo documentation:  
  <https://pymoo.org/>
