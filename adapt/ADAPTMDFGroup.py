# -*- coding: utf-8 -*-
"""
ADAPT MDF wrapper.

The wrapper separates:
- the external execution driver;
- the central MDA convergence block;
- the coupled ADAPT disciplinary model.

@author: Musavir Bashir
"""

from __future__ import annotations

import openmdao.api as om

from AirshipAnalysisGroup import AirshipAnalysisGroup


class ADAPTMDFGroup(om.Group):
    """
    Multidisciplinary Feasible architecture for ADAPT.

    The complete coupled airship analysis is contained in the ``mda`` group.
    Its nonlinear solver converges the multidisciplinary coupling before
    returning outputs to the external driver.
    """

    def initialize(self):
        self.options.declare("phd")
        self.options.declare(
            "power_source",
            default="conventional_reciprocating",
            types=str,
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            types=str,
        )
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
        )
        self.options.declare(
            "use_prescribed_consumable_capacity",
            default=False,
            types=bool,
        )

    def setup(self):
        mda = om.Group()

        mda.add_subsystem(
            "airship",
            AirshipAnalysisGroup(
                phd=self.options["phd"],
                power_source=self.options["power_source"],
                landing_system=self.options["landing_system"],
                num_steps=self.options["num_steps"],
                use_prescribed_consumable_capacity=(
                    self.options["use_prescribed_consumable_capacity"]
                ),
            ),
            promotes=["*"],
        )

        # Central MDF multidisciplinary converger.
        nonlinear_solver = om.NonlinearBlockGS(
            use_aitken=True,
        )

        nonlinear_solver.options["maxiter"] = 100
        nonlinear_solver.options["atol"] = 1.0e-8
        nonlinear_solver.options["rtol"] = 1.0e-8
        nonlinear_solver.options["err_on_non_converge"] = True
        nonlinear_solver.options["iprint"] = 2

        mda.nonlinear_solver = nonlinear_solver

        # Needed only for total derivatives or future gradient optimisation.
        mda.linear_solver = om.DirectSolver(
            assemble_jac=True,
        )

        self.add_subsystem(
            "mda",
            mda,
            promotes=["*"],
        )