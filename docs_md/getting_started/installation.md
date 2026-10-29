# Installation

The Airship Design Tool is currently maintained as a Python project rather than as an independently distributed Python package.

## Requirements

A working Python environment is required.

The primary computational dependency is **OpenMDAO**, which provides the multidisciplinary model assembly, variable connections, nonlinear solution infrastructure, derivative handling, and optimization framework used by the tool.

Additional packages support numerical computation, optimization, data management, and visualization. The repository currently contains a `requirements.txt` file specifying the principal software dependencies, listed below.

| Package | Role in the framework |
|---|---|
| `openmdao` | Multidisciplinary model assembly, coupling and optimization |
| `numpy` | Numerical array operations |
| `scipy` | Scientific/numerical algorithms |
| `pandas` | DOE and results-data processing |
| `matplotlib` | Visualization |
| `pymoo` | Multi-objective/evolutionary optimization and associated studies |
| `colorama` | Terminal output formatting |

The package list itself is defined by the repository requirements file.

## Creating a Virtual Environment

A dedicated virtual environment is recommended so that the framework dependencies remain isolated from other Python projects.

For example:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```bash
.venv\Scripts\activate
```

or on Linux/macOS:

```bash
source .venv/bin/activate
```

Then install the required packages:

```bash
pip install -r requirements.txt
```

These are also the installation steps currently specified by the repository.

## Repository Structure

A typical installation has the following organization:

```text
airship-design-tool/
│
├── core/
│   ├── operatingConditions.py
│   ├── Atmosphere.py
│   ├── AirshipGeometry.py
│   ├── AirshipWeight.py
│   ├── AirshipMission.py
│   ├── Propulsion.py
│   ├── Power.py
│   ├── Tank.py
│   ├── BatteryOnly.py
│   ├── SolarBattery.py
│   ├── FuelCellPolarization.py
│   ├── MissionProfile.py
│   └── AirshipAnalysisGroup.py
│
├── studies/
├── validation/
├── outputs/
├── requirements.txt
└── README.md
```

The repository documentation defines `core/` as the reusable physical model, `studies/` as the design-space/trade-study layer, `validation/` as the reference-validation layer, and `outputs/` as the destination for generated results.

## Running Analyses

The current repository intentionally keeps the core modules as flat Python modules rather than installing them as a package. Analysis scripts outside `core/` add the core directory to the Python search path at runtime.

Consequently, analyses can be executed directly, for example:

```bash
python studies/design_space_exploration.py --archs hydrogen_fuel_cell
```

or a validation case can be executed using:

```bash
python validation/validation_1_paper_with_pymoo_A170.py
```

These execution patterns are documented in the current repository README.

## Documentation Note

A specific supported Python-version range is not presently stated in the supplied repository files. We should therefore not invent one. Once the actual environment in which the framework has been verified is audited, the supported Python and OpenMDAO versions should be recorded here.

That is an example of the provenance discipline that should be applied throughout the documentation.
