# Proposed Documentation Navigation

This page records the proposed top-level structure for the Airship Design Tool documentation, and the rationale for the order in which sections are introduced.

## Proposed Sidebar Structure

```text
Airship Design Tool
│
├── Welcome to the Airship Design Tool
│
├── Getting Started
│   ├── Getting Started
│   ├── Installation
│   ├── Expected User Knowledge
│   ├── Underlying Tools
│   └── What's Next?
│
├── User Guide
│
├── Examples
│
├── Theory Guide
│
├── Verification and Validation
│
├── Developer Guide
│
└── Source Reference
```

This preserves the high-level organization used by Aviary's documentation, whose current documentation explicitly separates *Getting Started*, *User Guide*, *Examples*, *Theory Guide*, *Developer Guide*, and *Source Docs*.

## Rationale for the Next Documentation Step

For the next step, development should move to the **User Guide** rather than the **Theory Guide**. Specifically, the next page should be:

> "Airship Design Tool Fundamentals → How the Airship Design Tool Works."

There, the documentation should introduce the actual `AirshipAnalysisGroup`, explain the component flow and sizing loop at a high level, and present the first architecture diagram. After that, the User Guide should cover:

- Variables
- Inputs/configurations
- Running a model
- Outputs
- Propulsion architecture selection

Only after these topics are covered should the documentation enter the **Theory Guide** and begin the rigorous, equation-by-equation audit against the Carichner & Nicolai book and the other sources used by the code.
