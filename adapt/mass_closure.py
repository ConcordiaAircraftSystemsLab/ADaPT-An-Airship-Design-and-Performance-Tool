# -*- coding: utf-8 -*-
"""
Mass closure component for the ADAPT airship sizing framework.

The component evaluates the consistency between the MTOW produced by the
weight buildup and the mass reconstructed from the converged subsystem
masses.

Feasible/converged closure:
    mass_closure_residual = 0 kg
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


class MassClosureComp(om.ExplicitComponent):
    """
    Evaluate the airship total-mass closure residual.

    The component does not create a second MTOW estimate independently of
    the weight model. It reconstructs total mass from the final subsystem
    outputs and compares it with the current MTOW state.

    Residual convention
    -------------------
    mass_closure_residual = reconstructed_mtow - mtow

    Therefore:

        residual = 0  -> exact mass closure
        residual > 0  -> current MTOW is too low
        residual < 0  -> current MTOW is too high
        
        @author: Musavir Bashir
    """

    def setup(self):
        # Current MTOW produced by the weight model.
        self.add_input(
            "mtow",
            val=5000.0,
            units="kg",
            desc="Current total-mass estimate from the weight discipline",
        )

        # Operating-empty mass produced by the weight discipline.
        self.add_input(
            "owe",
            val=3000.0,
            units="kg",
            desc="Operating empty mass",
        )

        self.add_input(
            "payload",
            val=0.0,
            units="kg",
            desc="Mission payload",
        )

        self.add_input(
            "crew_mass",
            val=0.0,
            units="kg",
            desc="Crew mass, included only when not already contained in OWE",
        )

        self.add_input(
            "ballast_mass",
            val=0.0,
            units="kg",
            desc="Installed or mission ballast mass",
        )

        self.add_input(
            "installed_consumable_mass",
            val=0.0,
            units="kg",
            desc="Installed mission consumable mass",
        )

        # Optional external masses. Set them to zero when they are already
        # included in OWE.
        self.add_input(
            "additional_mass",
            val=0.0,
            units="kg",
            desc="Any mass not already included in OWE",
        )

        self.add_output(
            "reconstructed_mtow",
            val=5000.0,
            units="kg",
            desc="MTOW reconstructed from final subsystem masses",
        )

        self.add_output(
            "mass_closure_residual",
            val=0.0,
            units="kg",
            desc="Reconstructed MTOW minus current MTOW",
        )

        self.add_output(
            "mass_closure_relative",
            val=0.0,
            desc="Absolute mass-closure residual divided by MTOW",
        )

        self.declare_partials(
            of="reconstructed_mtow",
            wrt=[
                "owe",
                "payload",
                "crew_mass",
                "ballast_mass",
                "installed_consumable_mass",
                "additional_mass",
            ],
            val=1.0,
        )

        self.declare_partials(
            of="mass_closure_residual",
            wrt="mtow",
            val=-1.0,
        )

        self.declare_partials(
            of="mass_closure_residual",
            wrt=[
                "owe",
                "payload",
                "crew_mass",
                "ballast_mass",
                "installed_consumable_mass",
                "additional_mass",
            ],
            val=1.0,
        )

        # Relative residual contains an absolute-value operation, so use
        # complex-step approximation for this diagnostic output.
        self.declare_partials(
            of="mass_closure_relative",
            wrt="*",
            method="cs",
        )

    def compute(self, inputs, outputs):
        mtow = float(inputs["mtow"])

        reconstructed_mtow = (
            float(inputs["owe"])
            + float(inputs["payload"])
            + float(inputs["crew_mass"])
            + float(inputs["ballast_mass"])
            + float(inputs["installed_consumable_mass"])
            + float(inputs["additional_mass"])
        )

        residual = reconstructed_mtow - mtow

        outputs["reconstructed_mtow"] = reconstructed_mtow
        outputs["mass_closure_residual"] = residual
        outputs["mass_closure_relative"] = (
            abs(residual) / max(abs(mtow), 1.0)
        )