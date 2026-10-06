# -*- coding: utf-8 -*-
"""
Propulsion Component for ADaPT
==============================

Universal low-order mechanical propulsion model for buoyant airships.

The component is independent of structural type (non-rigid, semi-rigid, rigid)
and of the upstream energy source.  It owns the mechanical propulsor hardware:
prime mover at the propulsor (reciprocating engine OR electric motor),
propeller, nacelle, mount/pylon, and optional wiring.

Mechanical mission demand should preferably be supplied directly by
AirshipPerformance through ``mission_shaft_power_required``.  The older
thrust/speed path is retained as a compatibility fallback.

Book-based relations
--------------------
Carichner & Nicolai, Fundamentals of Aircraft and Airship Design, Vol. 2:

    eta_p = T V / P_sh                                      Eq. (5.30)
    C_P   = P / (rho n^3 D^5)                              Eq. (5.27)
    C_s   = [rho V^5 / (P n^2)]^(1/5)                      Eq. (5.29)
    J     = V / (n D)                                      Eq. (5.33)
    V_tip = pi n D                                         Eq. (5.32)

For the variable-pitch three-bladed Clark-Y preliminary-design chart used in
the Chapter-11 sample design, the following polynomial fits are available:

    J ~= 0.156 C_s^2 + 0.241 C_s + 0.138
    eta_p ~= 0.139 C_s^3 - 0.749 C_s^2 + 1.37 C_s + 0.0115

They are chart fits, not universal propeller laws.  Therefore the sizing method
is selectable.

Propeller mass follows Chapter 9 Eq. (9.16) when the book method is selected:

    W_prop = Kp Np N_blades^0.391 (D_ft hp_unit / 1000)^0.782

with Kp = 31.92 and weight in lb.

For reciprocating engines a book-compatible engine-mount estimate is available:

    W_mount = 0.64 W_engine,total                          Eq. (9.12)

The prime-mover core itself is intentionally sized from an explicit technology
specific-power input.  This keeps the component usable for present/future
technology studies; the Chapter-5 historical engine-weight curve can be used
as a validation/calibration reference rather than being imposed universally.

Takeoff
-------
True static thrust is NOT calculated from eta_p = TV/P, since eta_p -> 0 at
V=0.  Takeoff thrust is handled by AirshipPerformance using either a supplied
thrust value or an actuator-disk estimate based on installed shaft power and
the propeller diameter.  This component therefore does not use a fictitious
finite takeoff speed to create static thrust.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


KG_TO_LB = 2.2046226218487757
LB_TO_KG = 1.0 / KG_TO_LB
M_TO_FT = 3.280839895013123
W_TO_HP = 1.0 / 745.6998715822702


class Propulsion(om.ExplicitComponent):
    """Mechanical propulsion demand and installed hardware sizing."""

    def initialize(self):
        self.options.declare("phd", types=object, default=None, allow_none=True)
        self.options.declare("num_steps", default=1, types=int)
        self.options.declare(
            "engine_type",
            default="reciprocating",
            values=["electric", "reciprocating"],
        )
        self.options.declare(
            "landing_system",
            default="conventional",
            values=["conventional", "acls"],
        )
        self.options.declare(
            "airship_type",
            default="non-rigid",
            values=["non-rigid", "semi-rigid", "rigid"],
        )

        self.options.declare(
            "propeller_sizing_method",
            default="book_speed_power",
            values=["book_speed_power", "book_power_coefficient", "reduced_order"],
            desc=(
                "book_speed_power: Chapter-5 Cs/J chart-fit method; "
                "book_power_coefficient: Eq. (5.27); "
                "reduced_order: simplified ADaPT D~sqrt(P/(rho V^3 C))."
            ),
        )
        self.options.declare(
            "propeller_mass_method",
            default="book",
            values=["book", "simplified"],
        )

        self.options.declare(
            "prime_mover_mass_method",
            default="specific_power",
            values=[
                "specific_power",
                "book_reciprocating",
                "override",
            ],
            desc=(
                "Prime-mover core mass method. 'specific_power' retains the "
                "technology-based ADaPT model; 'book_reciprocating' uses the "
                "Chapter-5/Fig.-5.8 reciprocating-engine WER; 'override' uses "
                "a prescribed validation mass."
            ),
        )

        self.options.declare(
            "prime_mover_mass_override",
            default=0.0,
            types=float,
        )

        self.options.declare(
            "installation_mass_method",
            default="generic",
            values=[
                "generic",
                "structure_integrated",
                "override",
            ],
            desc=(
                "Method used for nacelle and engine/motor installation mass. "
                "'generic' retains the existing preliminary correlations; "
                "'structure_integrated' uses configurable installation fractions "
                "for propulsion units attached directly to a load-bearing airship "
                "structure; 'override' uses prescribed validated masses."
            ),
        )

        self.options.declare(
            "nacelle_mass_override",
            default=0.0,
            types=float,
        )

        self.options.declare(
            "mount_mass_override",
            default=0.0,
            types=float,
        )


        self.options.declare(
            "mount_mass_method",
            default="book_for_recip",
            values=["book_for_recip", "simplified"],
        )

        # simplified reduced-order diameter coefficient.  It is not the standard Cp.
        self.options.declare(
            "prop_power_coeff",
            default=0.65,
            types=float,
            desc="simplified reduced-order diameter coefficient; not Eq. (5.27) Cp.",
        )

        self.options.declare(
            "nacelle_mass_per_kw_recip",
            default=0.92,
            types=float,
            desc="Conceptual/calibration nacelle coefficient [kg/kW].",
        )
        self.options.declare(
            "nacelle_mass_per_kw_electric",
            default=3.0,
            types=float,
            desc="Conceptual/calibration nacelle coefficient [kg/kW].",
        )
        self.options.declare("propeller_mass_per_watt", default=1.2e-4, types=float)
        self.options.declare("minimum_propeller_mass_each", default=0.0, types=float)

        self.options.declare("enable_wiring_mass", default=False, types=bool)
        self.options.declare("wiring_mass_per_kw", default=0.0, types=float)

        self.options.declare("enable_mount_mass", default=True, types=bool)
        self.options.declare(
            "mount_mass_per_kn",
            default=0.03,
            types=float,
            desc="simplified conceptual mount coefficient [kg/kN].",
        )

        self.options.declare("debug_print", default=False, types=bool)

    def setup(self):
        n = self.options["num_steps"]

        # ------------------------------------------------------------------
        # Mission / configuration inputs
        # ------------------------------------------------------------------
        self.add_input("n_engine", val=2.0, desc="Number of propulsor units.")

        # Preferred mechanical-demand interface from Performance.
        self.add_input(
            "mission_shaft_power_required",
            val=np.full(n, -1.0),
            units="W",
            desc=(
                "Preferred propeller shaft-power demand from Performance. "
                "Negative entries invoke the simplified thrust/speed fallback."
            ),
        )

        # Compatibility path.
        self.add_input(
            "thrust_cruise",
            val=np.zeros(n),
            units="N",
            desc="simplified total cruise-thrust demand history.",
        )
        self.add_input(
            "tas",
            val=np.full(n, 19.5),
            units="m/s",
            desc="Mission true airspeed history.",
        )
        self.add_input(
            "propeller_efficiency",
            val=0.75,
            desc="Prescribed propeller efficiency for simplified T*V/eta path.",
        )

        self.add_input(
            "gearbox_efficiency",
            val=0.98,
            desc="Mechanical gearbox efficiency between prime mover and propeller.",
        )
        self.add_input(
            "rho",
            val=np.full(n, 1.099),
            units="kg/m**3",
            desc="Atmospheric density history.",
        )
        self.add_input(
            "installed_shaft_power",
            val=-1.0,
            units="W",
            desc=(
                "Externally selected total installed shaft-power rating. "
                "Negative means size to peak mission demand."
            ),
        )

        # Propeller design inputs.
        self.add_input(
            "propeller_rps",
            val=20.0,
            units="1/s",
            desc="Propeller rotational speed used for preliminary sizing.",
        )

        self.add_input(
            "propeller_design_speed",
            val=-1.0,
            units="m/s",
            desc=(
                "Explicit flight speed used for preliminary propeller sizing. "
                "Negative uses the highest mission shaft-power node."
            ),
        )

        self.add_input(
            "propeller_design_density",
            val=-1.0,
            units="kg/m**3",
            desc=(
                "Atmospheric density at the selected propeller design condition. "
                "Negative uses the density at the highest mission shaft-power node."
            ),
        )
        self.add_input(
            "propeller_blade_count",
            val=3.0,
            desc="Number of blades per propeller.",
        )
        self.add_input(
            "propeller_power_coefficient",
            val=0.08,
            desc="Standard nondimensional Cp for Eq. (5.27) sizing option.",
        )

        # Kept for compatibility with existing promoted interfaces.  The
        # mechanical sizing equations below do not use thrust vector angle.
        self.add_input("thrust_vector_angle", val=0.0, units="deg")

        if self.options["landing_system"] == "acls":
            self.add_input("acls_area", val=0.0, units="m**2")

        # ------------------------------------------------------------------
        # Technology inputs
        # ------------------------------------------------------------------
        self.add_input(
            "ice_specific_power",
            val=1200.0,
            units="W/kg",
            desc="Reciprocating-engine brake-power specific power.",
        )
        self.add_input(
            "motor_specific_power",
            val=5000.0,
            units="W/kg",
            desc="Electric-motor brake-power specific power.",
        )

        # ------------------------------------------------------------------
        # Mission power outputs
        # ------------------------------------------------------------------
        self.add_output("shaft_power", val=np.zeros(n), units="W")
        self.add_output(
            "required_power",
            val=np.zeros(n),
            units="W",
            desc="Backward-compatible alias of shaft_power.",
        )
        self.add_output("brake_power", val=np.zeros(n), units="W")

        # ------------------------------------------------------------------
        # Installed/rated power outputs
        # ------------------------------------------------------------------
        self.add_output("takeoff_shaft_power", val=0.0, units="W")
        self.add_output("rated_shaft_power", val=0.0, units="W")
        self.add_output("rated_brake_power", val=0.0, units="W")
        self.add_output("rated_shaft_power_per_unit", val=0.0, units="W")
        self.add_output("rated_brake_power_per_unit", val=0.0, units="W")

        # ------------------------------------------------------------------
        # Propeller diagnostics
        # ------------------------------------------------------------------
        self.add_output("propeller_diameter", val=0.0, units="m")
        self.add_output("propeller_speed_power_coefficient", val=0.0)
        self.add_output("propeller_advance_ratio", val=0.0)
        self.add_output("propeller_efficiency_estimated", val=0.0)
        self.add_output("propeller_tip_speed", val=0.0, units="m/s")
        self.add_output(
            "propeller_tip_speed_violation",
            val=0.0,
            units="m/s",
            desc=(
                "Positive amount above 243.84 m/s (800 ft/s), the upper end of "
                "the Chapter-5 preliminary tip-speed guidance."
            ),
        )

        # ------------------------------------------------------------------
        # Mass outputs
        # ------------------------------------------------------------------
        self.add_output("total_mass", val=0.0, units="kg")
        self.add_output(
            "motor_mass",
            val=0.0,
            units="kg",
            desc="Backward-compatible alias of total prime-mover core mass.",
        )
        self.add_output(
            "prime_mover_mass",
            val=0.0,
            units="kg",
        )

        self.add_output(
            "nacelle_mass",
            val=0.0,
            units="kg",
        )

        self.add_output(
            "propeller_mass",
            val=0.0,
            units="kg",
        )

        self.add_output(
            "mount_mass",
            val=0.0,
            units="kg",
            desc="Total propulsion-unit mounting/support mass.",
        )

        self.add_output(
            "pylon_mass",
            val=0.0,
            units="kg",
            desc="simplified compatibility alias of mount_mass.",
        )

        if self.options["enable_wiring_mass"]:
            self.add_output("wiring_mass", val=0.0, units="kg")

        self.declare_partials("*", "*", method="fd", step=1.0e-8)

    @staticmethod
    def _scalar(value):
        return float(np.asarray(value).ravel()[0])

    @staticmethod
    def _vector(value, n):
        arr = np.atleast_1d(value).astype(float).ravel()
        if arr.size == 0:
            return np.zeros(n)
        if arr.size == 1:
            return np.full(n, arr[0])
        if arr.size < n:
            return np.pad(arr, (0, n - arr.size), mode="edge")
        return arr[:n]

    @staticmethod
    def _book_chart_j(cs):
        """Chapter-11 polynomial fit to the Fig. 5.9 variable-pitch chart."""
        return 0.156 * cs**2 + 0.241 * cs + 0.138

    @staticmethod
    def _book_chart_eta(cs):
        """Chapter-11 polynomial fit to optimum propeller efficiency."""
        return 0.139 * cs**3 - 0.749 * cs**2 + 1.37 * cs + 0.0115

    def _propeller_design(self, power_unit, rho_ref, v_ref, rps):
        """Return D, Cs, J, eta_chart, Vtip for the selected sizing method."""
        method = self.options["propeller_sizing_method"]
        P = max(power_unit, 1.0)
        rho = max(rho_ref, 1.0e-9)
        V = max(v_ref, 0.1)
        n = max(rps, 1.0e-3)

        cs = (rho * V**5 / (P * n**2)) ** 0.2

        if method == "book_speed_power":
            j = max(self._book_chart_j(cs), 1.0e-3)
            diameter = V / (n * j)
            eta_chart = float(np.clip(self._book_chart_eta(cs), 0.0, 0.90))

        elif method == "book_power_coefficient":
            cp = max(self._current_cp, 1.0e-6)
            diameter = (P / (rho * n**3 * cp)) ** 0.2
            j = V / max(n * diameter, 1.0e-12)
            eta_chart = 0.0

        else:
            c_red = max(float(self.options["prop_power_coeff"]), 1.0e-6)
            diameter = np.sqrt(P / (rho * V**3 * c_red))
            j = V / max(n * diameter, 1.0e-12)
            eta_chart = 0.0

        # Do not silently clip a physical design variable to a narrow range.
        diameter = max(float(diameter), 0.05)
        v_tip = np.pi * n * diameter
        return diameter, float(cs), float(j), eta_chart, float(v_tip)

    def _book_propeller_mass(self, diameter_m, power_unit_w, n_prop, n_blades):
        """Chapter 9 Eq. (9.16), evaluated in its original imperial form."""
        d_ft = diameter_m * M_TO_FT
        hp_unit = power_unit_w * W_TO_HP
        kp = 31.92
        w_lb = (
            kp
            * n_prop
            * max(n_blades, 1.0) ** 0.391
            * max(d_ft * hp_unit / 1000.0, 1.0e-12) ** 0.782
        )
        return w_lb * LB_TO_KG

    def compute(self, inputs, outputs):
        n = self.options["num_steps"]
        engine_type = self.options["engine_type"]

        n_engine = max(int(round(self._scalar(inputs["n_engine"]))), 1)

        mission_direct = self._vector(inputs["mission_shaft_power_required"], n)
        thrust = np.maximum(self._vector(inputs["thrust_cruise"], n), 0.0)
        tas = np.maximum(self._vector(inputs["tas"], n), 0.1)
        rho = np.maximum(self._vector(inputs["rho"], n), 1.0e-9)

        eta_p = float(
            np.clip(self._scalar(inputs["propeller_efficiency"]), 0.05, 0.99)
        )
        eta_gb = float(
            np.clip(self._scalar(inputs["gearbox_efficiency"]), 0.10, 1.0)
        )

        # Prefer the authoritative Performance shaft-power demand pointwise.
        fallback_power = thrust * tas / eta_p
        shaft_power_mission = np.where(
            mission_direct >= 0.0,
            mission_direct,
            fallback_power,
        )
        shaft_power_mission = np.maximum(shaft_power_mission, 0.0)

        brake_power_mission = shaft_power_mission / eta_gb

        peak_mission_shaft = (
            float(np.max(shaft_power_mission)) if shaft_power_mission.size else 0.0
        )
        installed = self._scalar(inputs["installed_shaft_power"])
        rated_shaft = (
            max(peak_mission_shaft, installed)
            if installed >= 0.0
            else peak_mission_shaft
        )
        rated_brake = rated_shaft / eta_gb

        rated_shaft_unit = rated_shaft / n_engine
        rated_brake_unit = rated_brake / n_engine

        # There is no separate fictitious takeoff-power calculation here.
        # The installed rating is the power available to Performance for
        # actuator-disk/static-thrust estimation.
        takeoff_shaft_power = rated_shaft

        # Critical preliminary propeller-sizing condition: highest mission
        # shaft-power node.  If mission demand is zero, use the first node.
        if shaft_power_mission.size and np.any(shaft_power_mission > 0.0):
            i_crit = int(np.argmax(shaft_power_mission))
        else:
            i_crit = 0

        rho_mission_ref = float(
            rho[min(i_crit, rho.size - 1)]
        )

        v_mission_ref = float(
            tas[min(i_crit, tas.size - 1)]
        )

        rho_design_input = self._scalar(
            inputs["propeller_design_density"]
        )

        v_design_input = self._scalar(
            inputs["propeller_design_speed"]
        )

        rho_ref = (
            rho_design_input
            if rho_design_input > 0.0
            else rho_mission_ref
        )

        v_ref = (
            v_design_input
            if v_design_input > 0.0
            else v_mission_ref
        )

        rps = max(self._scalar(inputs["propeller_rps"]), 1.0e-3)
        self._current_cp = max(
            self._scalar(inputs["propeller_power_coefficient"]),
            1.0e-6,
        )

        diameter, cs, j, eta_chart, v_tip = self._propeller_design(
            rated_shaft_unit,
            rho_ref,
            v_ref,
            rps,
        )



        # ==============================================================
        # Prime mover
        # ==============================================================

        if engine_type == "electric":

            specific_power = max(
                self._scalar(inputs["motor_specific_power"]),
                1.0,
            )

            nacelle_coeff = max(
                float(self.options["nacelle_mass_per_kw_electric"]),
                0.0,
            )

        else:

            specific_power = max(
                self._scalar(inputs["ice_specific_power"]),
                1.0,
            )

            nacelle_coeff = max(
                float(self.options["nacelle_mass_per_kw_recip"]),
                0.0,
            )


        prime_mover_mass_method = self.options[
            "prime_mover_mass_method"
        ]

        if (
            prime_mover_mass_method
            == "book_reciprocating"
            and engine_type == "reciprocating"
        ):

            hp_per_engine = (
                rated_brake_unit
                * W_TO_HP
            )

            w_engine_total_lb = (
                n_engine
                * 4.848
                * max(
                    hp_per_engine,
                    1.0e-12,
                ) ** 0.7956
            )

            prime_mover_mass = (
                w_engine_total_lb
                * LB_TO_KG
            )

        elif (
            prime_mover_mass_method
            == "override"
        ):

            prime_mover_mass = max(
                float(
                    self.options[
                        "prime_mover_mass_override"
                    ]
                ),
                0.0,
            )

        else:

            prime_mover_mass = (
                rated_brake
                / specific_power
            )


        # ==============================================================
        # Propeller mass
        # ==============================================================

        n_blades = max(
            self._scalar(inputs["propeller_blade_count"]),
            1.0,
        )

        if self.options["propeller_mass_method"] == "book":

            propeller_mass = self._book_propeller_mass(
                diameter,
                rated_shaft_unit,
                n_engine,
                n_blades,
            )

        else:

            per_prop = max(
                float(self.options["propeller_mass_per_watt"])
                * rated_shaft_unit,
                float(self.options["minimum_propeller_mass_each"]),
            )

            propeller_mass = per_prop * n_engine


        # ==============================================================
        # Nacelle / propulsion-installation mass
        # ==============================================================

        installation_method = self.options["installation_mass_method"]

        nacelle_mass = 0.0
        mount_mass = 0.0


        # --------------------------------------------------------------
        # 1. Generic preliminary-design installation model
        # --------------------------------------------------------------

        if installation_method == "generic":

            # Conceptual nacelle model.
            nacelle_mass = (
                nacelle_coeff
                * rated_brake
                / 1000.0
            )

            if self.options["enable_mount_mass"]:

                if (
                    self.options["mount_mass_method"] == "book_for_recip"
                    and engine_type == "reciprocating"
                ):

                    # Carichner & Nicolai Chapter 9 Eq. (9.12):
                    #
                    # W_mount ~= 0.64 W_engine,total
                    #
                    mount_mass = (
                        0.64
                        * prime_mover_mass
                    )

                else:

                    # Conceptual thrust-based fallback for electric or
                    # unconventional propulsion installations.
                    thrust_unit_proxy = (
                        rated_shaft_unit
                        * eta_p
                        / max(v_ref, 0.1)
                    )

                    raw_each = (
                        float(
                            self.options["mount_mass_per_kn"]
                        )
                        * thrust_unit_proxy
                        / 1000.0
                    )

                    mount_mass = (
                        max(raw_each, 0.0)
                        * n_engine
                    )


        # --------------------------------------------------------------
        # 2. Structure-integrated propulsion installation
        # --------------------------------------------------------------

        elif installation_method == "structure_integrated":

            # Semi-rigid / rigid airships may attach propulsion units
            # directly to the primary load-bearing structure.
            #
            # IMPORTANT:
            # Do not automatically set installation mass to zero.
            # Until a dedicated structural installation model is available,
            # retain the nacelle estimate but avoid applying a separate
            # generic engine-mount WER that may overlap with the primary
            # structural-framework mass.

            nacelle_mass = (
                nacelle_coeff
                * rated_brake
                / 1000.0
            )

            mount_mass = 0.0


        # --------------------------------------------------------------
        # 3. Validation / externally prescribed installation masses
        # --------------------------------------------------------------

        elif installation_method == "override":

            nacelle_mass = max(
                float(
                    self.options["nacelle_mass_override"]
                ),
                0.0,
            )

            mount_mass = max(
                float(
                    self.options["mount_mass_override"]
                ),
                0.0,
            )


        else:

            raise ValueError(
                "Unsupported installation_mass_method: "
                f"{installation_method}"
            )

        wiring_mass = 0.0
        if self.options["enable_wiring_mass"] and engine_type == "electric":
            wiring_mass = (
                max(float(self.options["wiring_mass_per_kw"]), 0.0)
                * rated_brake / 1000.0
            )

        total_mass = (
            prime_mover_mass
            + nacelle_mass
            + propeller_mass
            + mount_mass
            + wiring_mass
        )

        outputs["shaft_power"] = shaft_power_mission
        outputs["required_power"] = shaft_power_mission
        outputs["brake_power"] = brake_power_mission

        outputs["takeoff_shaft_power"] = takeoff_shaft_power
        outputs["rated_shaft_power"] = rated_shaft
        outputs["rated_brake_power"] = rated_brake
        outputs["rated_shaft_power_per_unit"] = rated_shaft_unit
        outputs["rated_brake_power_per_unit"] = rated_brake_unit

        outputs["propeller_diameter"] = diameter
        outputs["propeller_speed_power_coefficient"] = cs
        outputs["propeller_advance_ratio"] = j
        outputs["propeller_efficiency_estimated"] = eta_chart
        outputs["propeller_tip_speed"] = v_tip
        outputs["propeller_tip_speed_violation"] = max(v_tip - 243.84, 0.0)

        outputs["total_mass"] = total_mass
        outputs["motor_mass"] = prime_mover_mass
        outputs["prime_mover_mass"] = prime_mover_mass
        outputs["nacelle_mass"] = nacelle_mass
        outputs["propeller_mass"] = propeller_mass

        outputs["mount_mass"] = mount_mass

        # simplified compatibility alias.
        outputs["pylon_mass"] = mount_mass

        if self.options["enable_wiring_mass"]:
            outputs["wiring_mass"] = wiring_mass

        if self.options["debug_print"]:
            print(
                f"[Propulsion] type={engine_type} "
                f"Pmission={peak_mission_shaft/1000:.1f} kW "
                f"Prated={rated_shaft/1000:.1f} kW "
                f"Dprop={diameter:.2f} m J={j:.3f} "
                f"mass={total_mass:.1f} kg"
            )


if __name__ == "__main__":
    print(
        "Propulsion component loaded. Instantiate it in an OpenMDAO Problem "
        "or ADaPT AirshipAnalysisGroup."
    )
