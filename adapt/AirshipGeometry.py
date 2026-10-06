# -*- coding: utf-8 -*-
"""
Airship Geometry Component for ADaPT

Purpose
-------
Computes the geometric characteristics of a single-lobed buoyant-lift airship
and generates the geometry quantities required by downstream ADaPT modules.

The component supports three structural arrangements:
    - non-rigid
    - semi-rigid
    - rigid

The external hull is represented as a prolate spheroid (body of revolution)
defined by overall length and fineness ratio.

Model responsibilities
----------------------
    - Generate hull diameter, gross volume, and wetted surface area.
    - Compute the aerodynamic reference area V^(2/3).
    - Size horizontal and vertical tails using the airship tail-volume-
      coefficient method.
    - Estimate ballonet capacity for non-rigid and semi-rigid configurations.
    - Provide conceptual framework geometry for semi-rigid and rigid cases.
    - Estimate usable rigid-airship gas-cell volume from the gross hull volume.

Scope and provenance
--------------------
The baseline geometry relations for body-of-revolution sizing and tail-volume
coefficient sizing follow the conceptual airship-design methodology of
Carichner and Nicolai, Fundamentals of Aircraft and Airship Design, Vol. 2.

Important distinctions:
    - The prolate-spheroid equations are geometric relations.
    - The tail-arm ratio and optional historical tail-coefficient correlations
      are literature-based conceptual-design assumptions.
      -Pressure-altitude ballonet capacity follows the Chapter-11
     density-ratio sizing relation. An optional configurable multiplier
     is retained for sensitivity/calibration, with a neutral default of 1.0.
    - Semi-rigid/rigid framework member counts and internal-area factors are
      conceptual parameterizations, not detailed structural designs.
    - The rigid hull-to-lifting-gas volume ratio is a conceptual historical
      approximation and is configurable.

This component provides conceptual geometry for multidisciplinary design and
optimization. It is not a CAD, detailed structural, or certification-level
geometry model.

@author: Musavir Bashir
"""

import numpy as np
import openmdao.api as om


class AirshipGeometry(om.ExplicitComponent):
    """Geometry model for a single-lobed buoyant-lift airship."""

    def initialize(self):
        self.options.declare(
            "max_altitude",
            default=3048.0,
            types=float,
            desc="Maximum pressure altitude used for ballonet sizing [m].",
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
            desc=(
                "Landing-system selection retained for group compatibility. "
                "Not used directly in this geometry component."
            ),
        )
        self.options.declare(
            "airship_type",
            default="non-rigid",
            values=["non-rigid", "semi-rigid", "rigid"],
            desc="Airship structural arrangement.",
        )

        # Tail sizing
        self.options.declare(
            "tail_arm_fraction",
            default=0.38,
            types=float,
            desc=(
                "Tail moment arm as a fraction of hull length. "
                "0.38 is representative of the historical 0.36-0.43 range."
            ),
        )
        self.options.declare(
            "tail_wetted_area_factor",
            default=2.2,
            types=float,
            desc=(
                "Conceptual conversion factor from total projected tail "
                "planform area to total tail wetted area."
            ),
        )
        self.options.declare(
            "tail_coefficient_method",
            default="user",
            values=["user", "historical"],
            desc=(
                "'user': use supplied C_HT and C_VT. 'historical': calculate "
                "them from the Chapter-7 volume-based correlations."
            ),
        )

        # Ballonet sizing
        self.options.declare(
            "ballonet_sizing_method",
            default="pressure_altitude",
            values=["pressure_altitude", "prescribed_fraction"],
            desc=(
               "Ballonet sizing method. 'pressure_altitude' uses the Chapter-11 "
                "conservative density-ratio relation "
                "V_ball/V_env = rho_SL/rho_alt - 1; "
                "'prescribed_fraction' uses a known installed ballonet fraction "
                "for reference-airship validation."
            ),
        )

        # Ballonet sizing
        self.options.declare(
            "ballonet_sizing_factor",
            default=1.0,
            types=float,
            desc=(
                "Optional multiplicative allowance applied to the selected "
                "ballonet-capacity relation. Default 1.0 uses the relation "
                "without an additional sizing multiplier."
            ),
        )




        self.options.declare(
            "max_ballonet_fraction",
            default=0.80,
            types=float,
            desc=(
                "Diagnostic upper design limit for ballonet fraction. "
                "The calculated physics result is not silently clipped."
            ),
        )

        # Semi-rigid / rigid conceptual structure geometry
        self.options.declare(
            "internal_fabric_area_factor",
            default=0.25,
            types=float,
            desc=(
                "Conceptual internal fabric/membrane area as a fraction of "
                "outer hull wetted area for semi-rigid/rigid cases."
            ),
        )
        # Backward-compatible alias for the older option name.
        self.options.declare(
            "inner_envelope_area_factor",
            default=None,
            allow_none=True,
            desc=(
                "simplified alias for internal_fabric_area_factor. If supplied, "
                "it overrides internal_fabric_area_factor."
            ),
        )
        self.options.declare(
            "framework_enabled",
            default=True,
            types=bool,
            desc=(
                "If True, compute conceptual primary framework member length "
                "for semi-rigid and rigid configurations."
            ),
        )
        self.options.declare(
            "rigid_hull_to_gas_volume_ratio",
            default=1.10,
            types=float,
            desc=(
                "Conceptual ratio gross rigid hull volume / lifting-gas-cell "
                "volume. Default 1.10 follows historical preliminary sizing."
            ),
        )

        # Design-bound diagnostics
        self.options.declare(
            "minimum_length",
            default=10.0,
            types=float,
            desc="Design lower bound used for violation reporting [m].",
        )
        self.options.declare(
            "minimum_fineness_ratio",
            default=2.0,
            types=float,
            desc="Design lower bound used for violation reporting [-].",
        )

    def setup(self):
        # Primary hull inputs
        self.add_input("length", val=53.6, units="m", desc="Airship overall hull length")
        self.add_input("fineness_ratio", val=4.09, desc="Body fineness ratio L/D")
        self.add_input(
            "tail_volume_coeff_horizontal",
            val=0.066,
            desc="Horizontal tail volume coefficient C_HT",
        )
        self.add_input(
            "tail_volume_coeff_vertical",
            val=0.059,
            desc="Vertical tail volume coefficient C_VT",
        )

        self.add_input(
            "ballonet_fraction_prescribed",
            val=0.08,
            desc=(
                "Installed ballonet volume fraction of gross envelope volume. "
                "Used only when ballonet_sizing_method='prescribed_fraction'."
            ),
        )

        self.add_input(
            "hull_volume_shape_factor",
            val=1.0,
            desc=(
                "Correction from the ideal prolate-spheroid volume to the actual "
                "single-lobed hull volume. A value of 1.0 gives the ideal spheroid."
            ),
        )

        self.add_input(
            "ballonet_fill_fraction_takeoff",
            val=0.0,
            desc=(
                "Fraction of installed ballonet capacity occupied by air at the "
                "takeoff/reference condition. This is a state variable and is distinct "
                "from installed ballonet capacity."
            ),
        )

        # Atmosphere inputs for ballonet sizing. These allow the group to use
        # one authoritative atmosphere model rather than a duplicate ISA here.
        self.add_input(
            "rho_sea_level",
            val=1.225,
            units="kg/m**3",
            desc="Air density at the low-altitude reference condition",
        )
        self.add_input(
            "rho_max_altitude",
            val=0.909,
            units="kg/m**3",
            desc=(
                "Air density at maximum pressure altitude; normally supplied "
                "by the common Atmosphere model"
            ),
        )

        # Common outputs
        self.add_output("gross_volume", units="m**3", desc="Gross prolate-spheroid hull volume")
        self.add_output("wetted_surface_area", units="m**2", desc="External hull wetted surface area")
        self.add_output("max_diameter", units="m", desc="Maximum hull diameter L/FR")
        self.add_output("ref_area_AeroCoeffs", units="m**2", desc="Aerodynamic reference area V^(2/3)")
        self.add_output("horizontal_tail_planform_area", units="m**2")
        self.add_output("vertical_tail_planform_area", units="m**2")
        self.add_output("fin_total_wetted_area", units="m**2", desc="Total conceptual tail wetted area")
        self.add_output("tail_arm", units="m")
        self.add_output("tail_volume_coeff_horizontal_used")
        self.add_output("tail_volume_coeff_vertical_used")
        self.add_output("ballonet_volume", units="m**3", desc="Installed ballonet capacity")
        self.add_output("ballonet_fraction")
        self.add_output(
            "ballonet_fraction_violation",
            desc=(
                "Positive amount by which calculated fraction exceeds the "
                "configured diagnostic maximum; zero is feasible"
            ),
        )

        self.add_output(
            "lifting_gas_volume_takeoff",
            val=0.0,
            units="m**3",
            desc=(
                "Lifting-gas volume at the takeoff/reference condition. "
                "For non-rigid and semi-rigid airships this is gross hull "
                "volume minus ballonet volume. For rigid airships it is "
                "the total gas-cell volume."
            ),
        )

        self.add_output(
            "ballonet_volume_takeoff",
            val=0.0,
            units="m**3",
            desc="Actual ballonet air volume at the takeoff/reference condition.",
        )


        self.add_output(
            "aspect_ratio_geom",
            desc=(
                "simplified compatibility alias equal to fineness ratio L/D; "
                "not wing/planform aspect ratio"
            ),
        )

        self.add_output(
            "body_aspect_ratio",
            desc=(
                "Body planform aspect ratio used in airship aerodynamic "
                "correlations, AR = D^2 / S_plan = 4D/(pi L) for the "
                "axisymmetric ellipsoidal hull."
            ),
        )

        self.add_output("length_violation", units="m")
        self.add_output("fineness_ratio_violation")

        airship_type = self.options["airship_type"]
        if airship_type in ["semi-rigid", "rigid"]:
            self.add_output("outer_envelope_area", units="m**2")
            self.add_output(
                "inner_envelope_area",
                units="m**2",
                desc="simplified-compatible conceptual internal fabric area",
            )
            self.add_output("internal_fabric_area", units="m**2")
            self.add_input(
                "n_longitudinal_members",
                val=12.0,
                desc="Conceptual number of primary longitudinal members",
            )
            self.add_input(
                "n_rings",
                val=16.0,
                desc="Conceptual number of circumferential frames/rings",
            )
            self.add_output("framework_total_member_length", units="m")

        if airship_type == "rigid":
            self.add_input("n_gas_cells", val=12.0, desc="Conceptual number of lifting-gas cells")
            self.add_output("gas_cell_volume_each", units="m**3")
            self.add_output("gas_cell_total_volume", units="m**3")

        self.declare_partials("*", "*", method="fd", step=1.0e-7)

    @staticmethod
    def _scalar(value):
        return float(np.asarray(value).ravel()[0])

    @staticmethod
    def _spheroid_area(a, b):
        """Surface area for a prolate spheroid, with robust sphere/oblate fallback."""
        if abs(a - b) < 1.0e-10:
            return 4.0 * np.pi * a**2

        if a < b:
            ecc_sq = max(1.0 - (a**2 / b**2), 0.0)
            ecc = np.sqrt(ecc_sq)
            if ecc < 1.0e-10:
                return 4.0 * np.pi * b**2
            return (
                2.0 * np.pi * b**2
                + (np.pi * a**2 / ecc) * np.log((1.0 + ecc) / (1.0 - ecc))
            )

        ecc_sq = max(1.0 - (b**2 / a**2), 0.0)
        ecc = np.sqrt(ecc_sq)
        if ecc < 1.0e-10:
            return 4.0 * np.pi * a**2
        return 2.0 * np.pi * b**2 + (2.0 * np.pi * a * b / ecc) * np.arcsin(ecc)

    @staticmethod
    def _historical_tail_coefficients(gross_volume_m3):
        """
        Chapter-7 initial-sizing correlations:
            C_HT = -0.0051*x + 0.0717
            C_VT = -0.0049*x + 0.0641
            x = 1,000,000 / V_ft3
        """
        m3_to_ft3 = 35.31466672148859
        volume_ft3 = max(gross_volume_m3 * m3_to_ft3, 1.0)
        x = 1.0e6 / volume_ft3
        c_ht = -0.0051 * x + 0.0717
        c_vt = -0.0049 * x + 0.0641
        return max(c_ht, 1.0e-6), max(c_vt, 1.0e-6)

    def compute(self, inputs, outputs):
        opt = self.options
        airship_type = opt["airship_type"]

        # Candidate values and diagnostics
        length_raw = self._scalar(inputs["length"])
        fr_raw = self._scalar(inputs["fineness_ratio"])
        min_length = float(opt["minimum_length"])
        min_fr = float(opt["minimum_fineness_ratio"])

        outputs["length_violation"] = max(min_length - length_raw, 0.0)
        outputs["fineness_ratio_violation"] = max(min_fr - fr_raw, 0.0)

        # Tiny guards only for numerical safety. Physical bounds belong in the
        # driver/optimizer and are exposed above as violations.
        length = max(length_raw, 1.0e-9)
        fineness_ratio = max(fr_raw, 1.0e-9)

        # External hull geometry
        max_diameter = length / fineness_ratio
        volume_shape_factor = max(
        self._scalar(inputs["hull_volume_shape_factor"]),
        1.0e-6,
        )

        gross_volume = (volume_shape_factor* (np.pi / 6.0)* length* max_diameter**2       )
        a_s = length / 2.0
        b_s = max_diameter / 2.0
        wetted_surface_area = self._spheroid_area(a_s, b_s)
        ref_area = gross_volume ** (2.0 / 3.0)
        body_aspect_ratio = (4.0 * max_diameter / (np.pi * length))

        outputs["max_diameter"] = max_diameter
        outputs["gross_volume"] = gross_volume
        outputs["wetted_surface_area"] = wetted_surface_area
        outputs["ref_area_AeroCoeffs"] = ref_area
        outputs["aspect_ratio_geom"] = fineness_ratio
        outputs["body_aspect_ratio"] = body_aspect_ratio

        # Initial tail sizing
        tail_arm_fraction = max(float(opt["tail_arm_fraction"]), 1.0e-9)
        tail_arm = tail_arm_fraction * length

        if opt["tail_coefficient_method"] == "historical":
            C_HT, C_VT = self._historical_tail_coefficients(gross_volume)
        else:
            C_HT = self._scalar(inputs["tail_volume_coeff_horizontal"])
            C_VT = self._scalar(inputs["tail_volume_coeff_vertical"])

        # Explicit Chapter-7 form:
        # C_H/V = S_H/V * l_H/V / (L * V^(2/3))
        horizontal_tail_planform_area = C_HT * length * ref_area / tail_arm
        vertical_tail_planform_area = C_VT * length * ref_area / tail_arm

        tail_wet_factor = max(float(opt["tail_wetted_area_factor"]), 0.0)
        total_fin_wetted_area = (
            horizontal_tail_planform_area + vertical_tail_planform_area
        ) * tail_wet_factor

        outputs["tail_arm"] = tail_arm
        outputs["tail_volume_coeff_horizontal_used"] = C_HT
        outputs["tail_volume_coeff_vertical_used"] = C_VT
        outputs["horizontal_tail_planform_area"] = horizontal_tail_planform_area
        outputs["vertical_tail_planform_area"] = vertical_tail_planform_area
        outputs["fin_total_wetted_area"] = total_fin_wetted_area


        # ==============================================================
        # Ballonet capacity
        # ==============================================================

        if airship_type in ["non-rigid", "semi-rigid"]:

            if opt["ballonet_sizing_method"] == "prescribed_fraction":
                ballonet_fraction = float(
                    np.clip(
                        self._scalar(inputs["ballonet_fraction_prescribed"]),
                        0.0,
                        0.95,
                    )
                )

                ballonet_volume = gross_volume * ballonet_fraction

            else:
                # Universal clean-sheet pressure-altitude sizing
                rho_sl = max(
                    self._scalar(inputs["rho_sea_level"]),
                    1.0e-12,
                )

                rho_alt = max(
                    self._scalar(inputs["rho_max_altitude"]),
                    1.0e-12,
                )

                theoretical_fraction = max(
                    (rho_sl / rho_alt) - 1.0,
                    0.0,
                )

                sizing_factor = max(
                    float(opt["ballonet_sizing_factor"]),
                    0.0,
                )

                ballonet_fraction = (
                    sizing_factor * theoretical_fraction
                )

                ballonet_volume = (
                    gross_volume * ballonet_fraction
                )

            max_fraction = max(
                float(opt["max_ballonet_fraction"]),
                0.0,
            )

            ballonet_violation = max(
                ballonet_fraction - max_fraction,
                0.0,
            )


        elif airship_type == "rigid":

            ballonet_fraction = 0.0
            ballonet_volume = 0.0
            ballonet_violation = 0.0


        else:
            raise ValueError(
                f"Unsupported airship_type: {airship_type}"
            )


        outputs["ballonet_fraction"] = ballonet_fraction
        outputs["ballonet_volume"] = ballonet_volume
        outputs["ballonet_fraction_violation"] = ballonet_violation

        # Semi-rigid / rigid conceptual structure geometry
        if airship_type in ["semi-rigid", "rigid"]:
            outer_area = wetted_surface_area

            simplified_factor = opt["inner_envelope_area_factor"]
            if simplified_factor is None:
                internal_factor = float(opt["internal_fabric_area_factor"])
            else:
                internal_factor = float(simplified_factor)
            internal_factor = max(internal_factor, 0.0)
            internal_area = outer_area * internal_factor

            outputs["outer_envelope_area"] = outer_area
            outputs["inner_envelope_area"] = internal_area
            outputs["internal_fabric_area"] = internal_area

            if opt["framework_enabled"]:
                n_long = max(self._scalar(inputs["n_longitudinal_members"]), 0.0)
                n_rings = max(self._scalar(inputs["n_rings"]), 0.0)
                circumference = np.pi * max_diameter

                # Conceptual framework: one keel/central longitudinal member,
                # additional longitudinal members, and circumferential frames.
                total_member_length = (
                    length
                    + n_long * length
                    + n_rings * circumference
                )
            else:
                total_member_length = 0.0

            outputs["framework_total_member_length"] = total_member_length

        # Rigid lifting-gas cells
        if airship_type == "rigid":
            n_cells = max(self._scalar(inputs["n_gas_cells"]), 1.0)
            hull_to_gas_ratio = max(float(opt["rigid_hull_to_gas_volume_ratio"]), 1.0)
            gas_cell_total_volume = gross_volume / hull_to_gas_ratio
            outputs["gas_cell_total_volume"] = gas_cell_total_volume
            outputs["gas_cell_volume_each"] = gas_cell_total_volume / n_cells

        # ==============================================================
        # Lifting-gas volume at takeoff/reference condition
        # ==============================================================

        if airship_type in ["non-rigid", "semi-rigid"]:

            fill_fraction_to = float(
                np.clip(
                    self._scalar(inputs["ballonet_fill_fraction_takeoff"]),
                    0.0,
                    1.0,
                )
            )

            ballonet_volume_takeoff = (
                fill_fraction_to * ballonet_volume
            )

            lifting_gas_volume_takeoff = max(
                gross_volume - ballonet_volume_takeoff,
                0.0,
            )

        elif airship_type == "rigid":

            ballonet_volume_takeoff = 0.0

            lifting_gas_volume_takeoff = max(
                gas_cell_total_volume,
                0.0,
            )

        else:
            raise ValueError(
                f"Unsupported airship_type: {airship_type}"
            )


        outputs["ballonet_volume_takeoff"] = (
            ballonet_volume_takeoff
        )

        outputs["lifting_gas_volume_takeoff"] = (
            lifting_gas_volume_takeoff
        )



if __name__ == "__main__":
    # Standalone smoke test. Full ADaPT runs should normally supply the two
    # density inputs from the shared Atmosphere model.
    prob = om.Problem()
    prob.model.add_subsystem(
        "geometry",
        AirshipGeometry(
            airship_type="non-rigid",
            tail_coefficient_method="user",
        ),
        promotes=["*"],
    )
    prob.setup()

    prob.set_val("length", 53.6, units="m")
    prob.set_val("fineness_ratio", 4.09)
    prob.set_val("rho_sea_level", 1.225, units="kg/m**3")
    prob.set_val("rho_max_altitude", 0.909, units="kg/m**3")
    prob.run_model()

    print("\nADaPT AirshipGeometry smoke test")
    print("--------------------------------")
    print(f"Max diameter [m]:             {prob.get_val('max_diameter')[0]:.3f}")
    print(f"Gross volume [m^3]:           {prob.get_val('gross_volume')[0]:.3f}")
    print(f"Wetted area [m^2]:            {prob.get_val('wetted_surface_area')[0]:.3f}")
    print(f"Reference area [m^2]:         {prob.get_val('ref_area_AeroCoeffs')[0]:.3f}")
    print(f"Horizontal tail area [m^2]:   {prob.get_val('horizontal_tail_planform_area')[0]:.3f}")
    print(f"Vertical tail area [m^2]:     {prob.get_val('vertical_tail_planform_area')[0]:.3f}")
    print(f"Ballonet fraction [-]:        {prob.get_val('ballonet_fraction')[0]:.4f}")
    print(f"Ballonet volume [m^3]:        {prob.get_val('ballonet_volume')[0]:.3f}")
