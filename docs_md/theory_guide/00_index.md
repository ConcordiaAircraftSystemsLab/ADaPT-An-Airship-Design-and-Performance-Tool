# ADaPT Multidisciplinary Airship Sizing — Theory Guide

This notebook set documents the theory, inputs, options, governing equations, and software traceability of the ADaPT airship conceptual-sizing framework, converted from the original Markdown Theory Guide chapters into Jupyter notebooks (one notebook per discipline/topic).

## Contents

### Vehicle Disciplines
1. [Geometry](geometry.md) — hull, tail, ballonet, and structural geometry (`AirshipGeometry`)
2. [Weight and Mass Estimation](mass.md) — envelope, structural, and systems mass build-up
3. [Propulsion](propulsion.md) — shaft power, propeller sizing, and propulsion-system mass
4. [Power and Energy Conversion](power.md) — mechanical-to-electrical conversion, fuel-cell and combustion architectures
5. [Performance and Mission Feasibility](performance.md) — buoyancy, drag polar, cruise strategies, and mission mass history
6. [Turbine-Based Propulsion Architectures](turbine_propulsion_architectures.md) — turboprop/turboshaft/turbofan mission shaft-power and mass models
7. [Energy Storage, Fuel-Cell, Solar-Electric, and Hydrogen-Storage Models](energy_storage_and_hydrogen_systems.md) — battery, fuel-cell, solar, and hydrogen-storage subsystems

### Methods and Verification
8. [Optimization Algorithms](optimization_algorithms.md) — OpenMDAO-based and pymoo-based optimization approaches
9. [Validation Methodology](validation.md) — verification strategy and reference-airship (A-170, Zeppelin NT 07-101) validation studies

Each notebook preserves the section structure, equations (rendered via MathJax), tables, component option/input listings, and software-traceability summaries of its source document. Equations originally written with `\( \)` and `\[ \]` LaTeX delimiters have been converted to `$ $` and `$$ $$` for native Jupyter/MathJax rendering; all other content is unchanged from the source Theory Guide chapters.
