<h1 align="center">ADaPT — Airship Design and Performance Tool</h1>
<p align="center">
  An open-source,
physics-based multidisciplinary framework for the **conceptual design,
sizing, mission analysis, technology assessment, and optimization of
airships**.
</p>

<hr>

<p align="center">
  <img src="docs/images/Graphical Abstract.svg"
       alt="ADaPT — Airship Design and Performance Tool"
       width="1000">
</p>





Built on [OpenMDAO](https://github.com/OpenMDAO/OpenMDAO), ADaPT couples
airship geometry, aerodynamics, buoyancy, mass estimation, propulsion,
power and energy systems, mission requirements, and operational
constraints within a common computational framework.

ADaPT is intended for both **conventional and alternative-propulsion
airships**, allowing different vehicle architectures to be evaluated on
a consistent basis while explicitly accounting for the strong
**mass--energy--propulsion--geometry coupling** that governs airship
design.





------------------------------------------------------------------------

## Key Capabilities

### Airship Conceptual Design and Sizing

ADaPT provides physics-based and semi-empirical models for conceptual
airship sizing, including:

-   Hull geometry and lifting-gas volume
-   Wetted and aerodynamic reference areas
-   Horizontal and vertical tail sizing
-   Ballonet sizing and takeoff gas state
-   Buoyancy and lifting-gas calculations
-   Structural and subsystem mass estimation
-   Operating empty mass (OEM) and maximum takeoff mass (MTOM)
-   Mission consumable and energy requirements
-   Installed-power and mission-feasibility assessment

The framework supports:

-   **Non-rigid airships**
-   **Semi-rigid airships**
-   **Rigid airships**

------------------------------------------------------------------------

## Multidisciplinary Analysis

ADaPT is implemented as a coupled **OpenMDAO multidisciplinary analysis
(MDA)** framework.

The principal design coupling can be represented schematically as:

``` text
Geometry
   ↓
Aerodynamics / Drag
   ↓
Propulsion Power
   ↓
Mission Energy
   ↓
Energy / Fuel / H₂ Storage Mass
   ↓
Aircraft Mass
   ↓
Buoyancy and Geometry
   ↺
```

The framework solves the resulting multidisciplinary dependencies while
maintaining consistent information exchange between:

-   Geometry
-   Atmosphere
-   Aerodynamics and performance
-   Mass estimation
-   Propulsion
-   Power systems
-   Energy storage
-   Hydrogen storage
-   Mission analysis

This allows ADaPT to distinguish between a physically converged vehicle
and a design that violates power, buoyancy, energy, storage, or other
feasibility requirements.

------------------------------------------------------------------------

## Propulsion and Energy Architectures

ADaPT supports multiple propulsion and energy-system architectures
within the same aircraft-level framework, including:

-   Conventional reciprocating-engine propulsion
-   Turboprop propulsion
-   Hydrogen internal-combustion propulsion
-   Hydrogen fuel-cell electric propulsion
-   Battery-electric propulsion
-   Solar--battery propulsion
-   Solar regenerative fuel-cell architectures
-   Hydrogen-hybrid architectures
-   Solar--hydrogen hybrid architectures
-   Conventional--battery hybrid architectures
-   Turboelectric architectures

Architecture-specific models account for the corresponding propulsion,
power-conversion, energy-storage, fuel, and tank mass contributions.

------------------------------------------------------------------------

## Mission and Operational Analysis

ADaPT includes mission-level analysis for evaluating whether a sized
vehicle can satisfy its intended mission.

Capabilities include:

-   Range and cruise-speed analysis
-   Altitude-dependent atmospheric conditions
-   Mission duration and energy requirements
-   Fuel or hydrogen consumption
-   Battery-energy requirements
-   Installed-power feasibility
-   Energy-storage feasibility
-   Buoyancy feasibility
-   Mission constraint evaluation
-   Payload--range studies



------------------------------------------------------------------------

## Design, Analysis, and Optimization Modes

ADaPT can be used at several levels depending on the study.

### Forward Analysis

Evaluate the performance and feasibility of a prescribed airship
configuration.

### Conceptual Sizing

Determine coupled vehicle mass, propulsion, energy, and mission
requirements for a specified design and mission.

### Reference-Aircraft Validation

Reproduce published or documented airship configurations to assess
individual models and integrated framework behavior.

### Design-Space Exploration

Explore the effects of vehicle, mission, architecture, and technology
parameters over prescribed design spaces.

### Multidisciplinary Optimization

Search for feasible designs and architecture-specific trade-offs using
evolutionary and other optimization methods.

------------------------------------------------------------------------

## Optimization and Design-Space Exploration

ADaPT supports automated design-space exploration and multi-objective
optimization using **pymoo** and OpenMDAO-compatible workflows.

Capabilities include:

-   Design of Experiments (DOE)
-   Architecture-dependent design spaces
-   Feasible/infeasible design classification
-   Constraint-aware optimization
-   Evolutionary optimization
-   Multi-objective optimization
-   Pareto-front identification
-   Payload--range boundary analysis
-   Technology sensitivity studies
-   Feasibility-threshold identification

Design variables can include vehicle geometry, mission requirements,
propulsion parameters, energy-storage characteristics, and technology
assumptions.

------------------------------------------------------------------------

## Performance and Architecture Metrics

ADaPT provides several aircraft- and architecture-level metrics.

### Maximum Takeoff Mass (MTOM)

Total takeoff mass of the modeled vehicle, including the installed
propulsion, energy-storage, structural, payload, and mission-consumable
contributions represented by the selected architecture.

### Architecture-Normalized MTOM (MTOM\*)

A comparison metric used in architecture studies to reduce distortions
caused by differences between installed energy capacity and
mission-required energy.

### Payload--Fuel Energy Intensity (PFEI)

A transport-energy metric defined as

\[ `\mathrm{PFEI}`{=tex} = `\frac{E_{\mathrm{mission}}}`{=tex}
{m\_{`\mathrm{payload}`{=tex}},d} \]

where:

-   (E\_{`\mathrm{mission}`{=tex}}) is mission energy,
-   (m\_{`\mathrm{payload}`{=tex}}) is transported payload mass, and
-   \(d\) is mission distance.

These metrics enable architecture comparisons beyond MTOM alone.

------------------------------------------------------------------------

## Technology Assessment

ADaPT can investigate how emerging technologies influence airship
feasibility and performance.

Example technology parameters include:

-   Battery specific energy
-   Battery specific power
-   Fuel-cell specific power
-   Hydrogen storage characteristics
-   Solar-cell efficiency
-   Solar-system specific mass
-   Electric-machine efficiency
-   Power-electronics efficiency
-   Propulsion-system specific power

Technology studies can be used to identify:

-   Performance sensitivities
-   Diminishing returns
-   Architecture crossover regions
-   Technology feasibility thresholds
-   Required technology improvements
-   Future architecture potential

------------------------------------------------------------------------

## Validation

ADaPT includes component-level and integrated validation workflows.

Reference configurations can be used to assess:

-   Geometry
-   Volume
-   Buoyancy
-   Structural and subsystem masses
-   OEM
-   MTOM
-   Propulsion requirements
-   Mission feasibility

Validation cases include published and documented airship configurations
representing different vehicle classes and scales.

Validation is kept conceptually separate from clean-sheet sizing:
published quantities may be prescribed for model verification without
treating them as design predictions.

------------------------------------------------------------------------

## Visualization

ADaPT provides visualization tools for both aircraft-design and
operational studies, including:

-   MTOM\*--PFEI architecture trade spaces
-   Pareto fronts
-   Feasibility maps
-   Payload--range envelopes
-   Technology sensitivity plots
-   Technology feasibility boundaries
-   Design-space distributions
-   Mission-leg performance
-   Route and wind profiles
-   Operational fleet trade spaces

------------------------------------------------------------------------

## Software Structure

A typical ADaPT analysis follows:

``` text
Mission / Design Requirements
            │
            ▼
      AirshipAnalysisGroup
            │
    ┌───────┼────────┐
    ▼       ▼        ▼
 Geometry  Mass  Atmosphere
    │        ▲        │
    ▼        │        ▼
Performance ─┼──► Propulsion
    │        │        │
    ▼        │        ▼
 Mission ────┼────► Power
    │        │        │
    ▼        │        ▼
Energy Storage / Hydrogen Systems
            │
            ▼
   Coupled Vehicle Solution
            │
            ▼
 Feasibility / DOE / Optimization
```

The framework is designed so that subsystem models remain modular while
exchanging variables through the common OpenMDAO model.

------------------------------------------------------------------------

## Installation

### Requirements

-   Python ≥ 3.9

Core dependencies include:

-   OpenMDAO
-   NumPy
-   SciPy
-   pandas
-   Matplotlib
-   pymoo

### Clone the Repository

``` bash
git clone <repository-url>
cd ADaPT-An-Airship-Design-and-Performance-Tool
```

### Create a Virtual Environment

#### Windows

``` bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install ADaPT

Install the package and its dependencies in editable mode:

``` bash
pip install -e .
```

Editable installation links the Python environment directly to the local
source tree, so code changes take effect without reinstalling the
package.

Optional dependencies can be installed using:

``` bash
pip install -e ".[plots,dev]"
```


## Documentation

ADaPT includes dedicated documentation covering both the theoretical foundations of the framework and its practical use.

The documentation is organized under the [`docs/`](docs/) directory:

```text
docs/
├── getting_started/    # Installation, setup, and introductory examples
├── theory_guide/       # Governing equations, assumptions, models, and theory
└── user_guide/         # Practical guidance for running and using ADaPT
```

### Getting Started

The **Getting Started** documentation provides introductory material for new users, including environment setup, installation, project organization, and basic ADaPT workflows.

### Theory Guide

The **Theory Guide** documents the mathematical and physical models implemented within ADaPT. It provides the theoretical basis, assumptions, inputs, outputs, multidisciplinary dependencies, and source traceability for the principal analysis modules.

Topics include airship geometry, atmosphere, buoyancy and mass estimation, aerodynamic performance, propulsion, power and energy systems, energy storage, hydrogen systems, mission analysis, and optimization-related formulations.

The Theory Guide is particularly useful for researchers who need to understand the physical assumptions and equations behind an ADaPT analysis rather than treating the framework as a black-box design tool.

### User Guide

The **User Guide** focuses on practical use of the framework, including model configuration, execution of analyses, interpretation of outputs, and use of the available design and research workflows.

Together, these resources provide three complementary levels of documentation:

- **Getting Started** — installing ADaPT and running the first analyses
- **Theory Guide** — understanding the underlying physics, equations, assumptions, and model coupling
- **User Guide** — configuring and applying ADaPT to design and research studies

Users developing new models or modifying existing components are encouraged to consult the Theory Guide alongside the corresponding source code.


------------------------------------------------------------------------

## Usage

ADaPT can be used directly through **Python scripts** or through the **graphical user interface (GUI)**.

For research, detailed design studies, and framework development, the **Python-based workflow is currently recommended** because it provides direct access to the complete set of model inputs, design variables, architecture options, constraints, technology assumptions, and optimization settings. The GUI provides a convenient interface for configuring and visualizing common analyses, but it exposes a selected subset of the full framework capabilities.

### Python-Based Usage

ADaPT scripts can be run directly from a Python development environment such as **Spyder**, **VS Code**, **PyCharm**, or from a terminal.

For example, in **Spyder**:

1. Open the ADaPT project directory.
2. Open the desired run script.
3. Edit the analysis inputs and configuration parameters as required.
4. Run the script using **Run File (F5)**.
5. Results, plots, and generated output files will be produced by the selected analysis.

The Python workflow allows users to directly modify parameters such as:

- Airship geometry and structural configuration
- Payload, range, altitude, and cruise speed
- Propulsion and energy architecture
- Installed propulsion power
- Fuel or hydrogen capacity
- Battery and solar-system parameters
- Hydrogen-storage assumptions
- Aerodynamic and propulsion parameters
- Design-variable bounds
- Feasibility constraints
- DOE sampling ranges
- Optimization variables and objectives
- Technology assumptions and sensitivity ranges
- Mission, weather, routing, and operational parameters

This makes the Python workflow particularly suitable for **research studies, model development, sensitivity analysis, design-space exploration, and multidisciplinary optimization**.

### Basic Multidisciplinary Analysis

The main MDA driver performs a coupled aircraft analysis using the current ADaPT framework.

Open `run_MDA.py` in your Python IDE, modify the configuration as required, and run the file.

Alternatively, from a terminal:

```bash

python validation_a170.py

python run_sizing.py

python run_MDA.py
```


### Additional Research Studies

Additional scripts in the repository provide specialized analyses including:

- Architecture comparison
- Payload–range analysis
- Technology sensitivity studies
- Technology feasibility thresholds
- Energy and propulsion trade studies
- Design-space exploration
- Surrogate and response-surface analysis
- Reference-aircraft validation

These scripts can be modified directly to define study-specific variables, bounds, assumptions, and output quantities.

---

### Graphical User Interface

ADaPT also includes a **Streamlit-based graphical user interface** for interactive setup and visualization of common analyses.

Start the GUI from the ADaPT project directory using:

```bash
streamlit run ui/app.py
```

The GUI provides a convenient way to configure an airship, select analysis options, run supported studies, and inspect results without directly modifying Python scripts.

The GUI is particularly useful for:

- Rapid configuration and preliminary analysis
- Exploring common design inputs
- Comparing configurations
- Inspecting model outputs
- Visualizing feasibility and trade spaces
- Demonstrating ADaPT workflows

The **Python workflow currently provides greater flexibility** than the GUI because users can directly access and modify the complete model configuration, introduce additional design variables, change parameter bounds, define custom DOE studies, modify optimization formulations, and develop new research cases.

Accordingly, the GUI is intended as a convenient interface to ADaPT, while direct Python execution remains the preferred workflow for advanced research and framework development.

---

### Validation

Reference-aircraft validation cases are provided separately from clean-sheet design studies.

For example:

```bash
python validation_a170.py
```

Validation scripts can be used to compare ADaPT predictions with published or documented reference-aircraft data and to evaluate individual subsystem models and integrated framework behavior.

------------------------------------------------------------------------

## Example Applications

ADaPT can be used to investigate questions such as:

-   How does propulsion architecture affect airship MTOM and energy
    efficiency?
-   When does battery-electric propulsion become mass-feasible?
-   What hydrogen-storage performance is required for a given mission?
-   How does solar-cell efficiency affect solar-assisted airship
    performance?
-   How do payload and range affect architecture feasibility?
-   Which technologies most strongly influence future airship
    performance?
-   How do winds and route conditions affect mission feasibility?
-   How many vehicles are required to transport a specified payload
    within a given operational time?

------------------------------------------------------------------------

## Current Scope and Limitations

ADaPT is a **conceptual and preliminary design framework**. It is
intended primarily for architecture exploration, multidisciplinary
sizing, technology assessment, and comparative studies rather than
detailed certification-level aircraft design.

Current limitations include:

-   Conceptual/semi-empirical structural mass models
-   Simplified aerodynamic representations
-   Conceptual propulsion and energy-system models
-   Simplified geometric representation of the airship hull
-   Technology-dependent parameters that require appropriate literature
    or experimental calibration
-   Mission models that do not replace high-fidelity trajectory, CFD,
    structural FEA, or detailed propulsion-cycle analysis

Results should therefore be interpreted at the fidelity level of the
underlying models.

------------------------------------------------------------------------

## Contributing

Contributions to ADaPT are welcome.

Areas of particular interest include:

-   Additional airship configurations
-   New propulsion architectures
-   Higher-fidelity aerodynamic models
-   Improved structural mass estimation
-   Hydrogen-storage models
-   Battery and fuel-cell models
-   Solar-energy models
-   Thermal-management systems
-   Weather and routing models
-   Operational and lifecycle analysis
-   Cost models
-   Additional reference-aircraft validation cases
-   Optimization and surrogate-modeling methods

------------------------------------------------------------------------

## License

MIT License

------------------------------------------------------------------------

## Acknowledgements

ADaPT builds upon:

-   OpenMDAO
-   pymoo
-   Established airship design methodologies
-   Aircraft propulsion and energy-system literature
-   Published airship reference configurations

The framework is developed as a research tool for multidisciplinary
investigation of conventional and emerging airship technologies.

------------------------------------------------------------------------

## Contact

Questions, bug reports, feature requests, and contributions can be
submitted through **GitHub Issues** or **GitHub Discussions**.

------------------------------------------------------------------------

## Citing ADaPT

If you use ADaPT in academic or research work, please cite the
associated ADaPT publication.

> Citation information will be added following publication.
