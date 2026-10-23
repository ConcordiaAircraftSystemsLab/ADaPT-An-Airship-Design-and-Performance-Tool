# -*- coding: utf-8 -*-
"""
Airship Mass Component for ADaPT
==================================

Purpose
-------
Conceptual mass build-up and OEW/MTOW closure for single-lobed buoyant-lift
airships. The component supports non-rigid, semi-rigid, and rigid structural
arrangements.

The default non-rigid subsystem relationships are written to follow the
conceptual-design methodology in Carichner and Nicolai, Fundamentals of
Aircraft and Airship Design, Volume 2, especially Chapters 6, 8, and 9.

Important modeling distinction
------------------------------
Not every structural relationship in the three architecture branches has a
published closed-form WER in the book. Where the book provides an applicable
WER, this component implements it explicitly. Where it does not, the existing
semi-rigid/rigid conceptual framework parameterization is retained and is
clearly identified as a framework assumption/calibration rather than a direct
literature equation.

Book-based relationships implemented here
-----------------------------------------
Envelope, non-rigid:
    Chapter 8 Eq. (8.7)
        W_env = sigma_fabric * S_wet * F_MA * F_AF

Ballonet fabric:
    Chapter 8 Eq. (8.8) / Chapter 9 Eq. (9.8)
    Two equal spherical ballonets are used for initial sizing.

Suspension curtain:
    Chapter 8 Eqs. (8.13) and (8.14b)
        S_curtain = 0.20 * S_side_projected
        W_curtain = sigma_curtain * S_curtain * F_J

Tail:
    Chapter 9 Eqs. (9.2)-(9.4), lightweight structural-tail path.
    The book gives endpoint coefficients for q < 1 lb/ft^2 and
    q > 10 lb/ft^2. ADaPT uses those values exactly at the endpoints and
    linearly interpolates between them for 1 <= q <= 10 lb/ft^2. The
    interpolation is an ADaPT adaptation [A], not a verbatim book equation.

Gondola:
    Chapter 9 Eqs. (9.5)-(9.7), selected by gondola payload category rather
    than by airship structural type.

Landing gear:
    Chapter 9 Eqs. (9.19)-(9.21)
    Single or tricycle conventional gear, or ACLS.

Crew:
    250 lb/person (~113.4 kg/person) is used as the literature default.

Miscellaneous:
    A fraction of OEW. 3.5% is used as the default conventional-airship
    conceptual value; this remains configuration dependent.

Mass margin:
    Optional. The book discusses typical 5-10% design margins and uses
    5-6% in examples. The ADaPT default is 6%, but application of the margin
    is disabled by default so reference-aircraft validation does not
    automatically double-count a margin already embedded in measured OEW.

Mass ownership
--------------
Fuel/hydrogen consumable mass, propulsion mass, power-system mass, and
hydrogen-tank mass remain owned by their authoritative components and are
supplied to this component.

Units
-----
OpenMDAO inputs/outputs are SI. Literature WERs that are defined in imperial
units are evaluated internally in their original units and then converted back
to SI. This avoids silently reusing imperial numerical coefficients as SI
coefficients.

@author: Musavir Bashir
"""

from __future__ import annotations

import numpy as np
import openmdao.api as om


# ---------------------------------------------------------------------------
# Architecture registry
# ---------------------------------------------------------------------------

TANK_SOURCES = [
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
]

ALL_POWER_SOURCES = [
    "conventional_reciprocating",
    "turboprop",
    "turboelectric",
    "hydrogen_reciprocating",
    "hydrogen_fuel_cell",
    "battery_only",
    "solar_battery",
    "solar-RFC",
    "hydrogen_hybrid",
    "solar_hydrogen_hybrid",
    "conventional_battery_hybrid",
]


# ---------------------------------------------------------------------------
# Unit conversion constants
# ---------------------------------------------------------------------------

KG_TO_LB = 2.2046226218487757
LB_TO_KG = 1.0 / KG_TO_LB

M_TO_FT = 3.280839895013123
M2_TO_FT2 = 10.763910416709722
M3_TO_FT3 = 35.31466672148859

PA_TO_PSF = 0.020885434273039
LBFT2_TO_KGM2 = LB_TO_KG / 0.09290304


class AirshipWeight(om.ExplicitComponent):
    """Conceptual airship mass build-up and MTOW closure."""

    def initialize(self):
        # ------------------------------------------------------------------
        # Core architecture
        # ------------------------------------------------------------------
        self.options.declare(
            "phd",
            types=object,
            desc="Operating-condition/property object.",
        )
        self.options.declare(
            "power_source",
            default="conventional_reciprocating",
            values=ALL_POWER_SOURCES,
        )
        self.options.declare(
            "num_steps",
            default=1,
            types=int,
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

        # ------------------------------------------------------------------
        # Non-rigid envelope: Chapter 8 Eq. (8.7)
        # ------------------------------------------------------------------
        # The raw fabric density is multiplied by the book factors F_MA and
        # F_AF.  The default raw density below is selected so the historical
        # ADaPT installed effective density (~0.383 kg/m^2) is retained:
        #
        #   0.2533 * 1.20 * 1.26 ~= 0.383 kg/m^2.
        #
        # Therefore the EQUATION is literature-based while this default
        # material density remains a baseline/calibration value.
        self.options.declare(
            "envelope_fabric_areal_density",
            default=0.383 / (1.20 * 1.26),
            types=float,
            desc="Raw non-rigid envelope fabric areal density [kg/m^2].",
        )
        self.options.declare(
            "envelope_manufacturing_factor",
            default=1.20,
            types=float,
            desc="Chapter 8 F_MA manufacturing/assembly factor.",
        )
        self.options.declare(
            "envelope_attachment_factor",
            default=1.26,
            types=float,
            desc="Chapter 8 F_AF attachment-fitting factor.",
        )

        # It is used only when envelope_weight_method='simplified_areal'.
        self.options.declare(
            "envelope_areal_density_nonrigid",
            default=0.383,
            types=float,
        )
        self.options.declare(
            "envelope_weight_method",
            default="book",
            values=["book", "simplified_areal"],
            desc="Non-rigid envelope mass method.",
        )

        # ------------------------------------------------------------------
        # Ballonet: Eqs. (8.8)/(9.8)
        # ------------------------------------------------------------------
        self.options.declare(
            "ballonet_fabric_density_lb_ft2",
            default=0.035,
            types=float,
            desc="Book early-design ballonet fabric density [lb/ft^2].",
        )
        self.options.declare(
            "ballonet_weight_factor",
            default=1.13,
            types=float,
            desc="Chapter 9 Eq. (9.8) ballonet weight allowance.",
        )
        self.options.declare(
            "include_ballonet_mass",
            default=True,
            types=bool,
        )

        # ------------------------------------------------------------------
        # Pressure System Mass
        # ------------------------------------------------------------------
        self.options.declare(
            "pressure_system_weight_method",
            default="none",
            values=["none", "book_fraction", "override"],
        )

        self.options.declare(
            "pressure_system_fraction",
            default=0.02,
            types=float,
        )

        self.options.declare(
            "pressure_system_mass_override",
            default=0.0,
            types=float,
        )

        # ------------------------------------------------------------------
        # VMS mass
        # ------------------------------------------------------------------
        self.options.declare(
            "vms_weight_method",
            default="none",
            values=["none", "book_fraction", "override"],
        )

        self.options.declare(
            "vms_fraction",
            default=0.03,
            types=float,
        )

        self.options.declare(
            "vms_mass_override",
            default=0.0,
            types=float,
        )

        # ------------------------------------------------------------------
        # Suspension curtain: Eqs. (8.13)/(8.14b)
        # ------------------------------------------------------------------
        self.options.declare(
            "include_suspension_curtain",
            default=True,
            types=bool,
        )
        self.options.declare(
            "curtain_area_fraction",
            default=0.20,
            types=float,
            desc="Eq. (8.14b): curtain area / hull side projected area.",
        )
        self.options.declare(
            "curtain_joint_factor",
            default=1.06,
            types=float,
            desc="Eq. (8.13) F_J assembly-joint factor.",
        )
        self.options.declare(
            "curtain_fabric_density_lb_ft2",
            default=0.028,
            types=float,
            desc=(
                "Conceptual curtain fabric density [lb/ft^2]. "
                "Default follows the worked Dyneema example; replace when "
                "material/stress sizing is available."
            ),
        )


        # ------------------------------------------------------------------
        # Conventional liquid-fuel tank:
        # ------------------------------------------------------------------
        self.options.declare(
            "fuel_tank_weight_method",
            default="none",
            values=["none", "book", "override"],
        )

        self.options.declare(
            "fuel_tank_mass_override",
            default=0.0,
            types=float,
        )

        # ------------------------------------------------------------------
        # Tail: Chapter 9 Eqs. (9.2)-(9.4)
        # ------------------------------------------------------------------
        self.options.declare(
            "tail_weight_method",
            default="book_lightweight",
            values=["book_lightweight", "simplified_areal"],
        )
        self.options.declare(
            "tail_control_surface_fraction",
            default=0.20,
            types=float,
            desc="Book conceptual control-surface fraction of total planform.",
        )
        self.options.declare(
            "tail_attachment_factor",
            default=1.26,
            types=float,
            desc="Chapter 9 F_AF for fixed tail attachment.",
        )
        self.options.declare(
            "tail_actuator_installation_factor",
            default=1.15,
            types=float,
            desc="Chapter 9 actuator installation factor.",
        )
        self.options.declare(
            "tail_fpsq_low_q",
            default=0.30,
            types=float,
            desc="Eq. (9.2) F_PSQ [lb/ft^2] for q < 1 lb/ft^2.",
        )
        self.options.declare(
            "tail_fpsq_high_q",
            default=1.00,
            types=float,
            desc="Eq. (9.2) F_PSQ [lb/ft^2] for q > 10 lb/ft^2.",
        )
        self.options.declare(
            "tail_fact_low_q",
            default=0.08,
            types=float,
            desc="Eq. (9.4) actuator factor for q < 1 lb/ft^2.",
        )
        self.options.declare(
            "tail_fact_high_q",
            default=0.79,
            types=float,
            desc="Eq. (9.4) actuator factor for q > 10 lb/ft^2.",
        )

        # simplified tail option retained only for compatibility.
        self.options.declare(
            "fin_areal_density",
            default=4.90,
            types=float,
        )

        # ------------------------------------------------------------------
        # Gondola: Chapter 9 Eqs. (9.5)-(9.7)
        # ------------------------------------------------------------------
        self.options.declare(
            "gondola_weight_method",
            default="book",
            values=["book", "override", "simplified"],
            desc=(
                "'book' uses the selected payload category; 'override' uses "
                "gondola_mass_override; 'simplified' reproduces old ADaPT logic."
            ),
        )
        self.options.declare(
            "gondola_category",
            default=2,
            values=[1, 2, 3],
            desc="Chapter 9 gondola payload category.",
        )
        self.options.declare(
            "gondola_mass_override",
            default=1500.0,
            types=float,
            desc=(
                "Reference-aircraft/calibration override [kg]. Used only when "
                "gondola_weight_method='override'."
            ),
        )

        # ------------------------------------------------------------------
        # Semi-rigid / rigid envelope and framework
        # ------------------------------------------------------------------
        # The book discusses these architectures but does not provide one
        # general closed-form framework WER applicable to every rigid/semi-rigid
        # layout. These remain explicit conceptual/calibration options.
        self.options.declare(
            "outer_envelope_areal_density",
            default=1.07,
            types=float,
        )
        self.options.declare(
            "inner_envelope_areal_density",
            default=0.10,
            types=float,
        )
        self.options.declare(
            "frame_linear_density",
            default=1.5,
            types=float,
        )
        self.options.declare(
            "framework_mass_model",
            default="v23",
            values=["linear", "v23", "ld", "fraction_envelope"],
        )
        self.options.declare(
            "k_framework_v23",
            default=0.35,
            types=float,
        )
        self.options.declare(
            "k_framework_ld",
            default=2.0,
            types=float,
        )
        self.options.declare(
            "framework_mass_frac_cap",
            default=0.22,
            types=float,
            desc="Optimization safeguard, not a physical structural law.",
        )

        # ------------------------------------------------------------------
        # Landing system: Eqs. (9.19)-(9.21)
        # ------------------------------------------------------------------
        self.options.declare(
            "conventional_gear_type",
            default="tricycle",
            values=["single", "tricycle"],
        )
        self.options.declare(
            "landing_gear_method",
            default="book",
            values=["book", "simplified_fraction"],
        )
        self.options.declare(
            "landing_gear_fraction",
            default=0.0167,
            types=float,
            desc="simplified ADaPT fraction, used only in simplified_fraction mode.",
        )
        self.options.declare(
            "acls_coefficient_lb_ft2",
            default=1.6,
            types=float,
            desc="Eq. (9.21) ACLS coefficient in original imperial units.",
        )

        # ------------------------------------------------------------------
        # Miscellaneous, crew, design margin
        # ------------------------------------------------------------------
        self.options.declare(
            "miscellaneous_fraction",
            default=0.035,
            types=float,
            desc=(
                "Conceptual miscellaneous systems fraction of OEW. "
                "3.5% is the conventional-airship example value."
            ),
        )
        self.options.declare(
            "crew_mass_each",
            default=250.0 * LB_TO_KG,
            types=float,
            desc="Crew plus luggage mass per person [kg].",
        )
        self.options.declare(
            "apply_weight_margin",
            default=False,
            types=bool,
            desc=(
                "Apply conceptual empty-weight design margin. Keep False for "
                "reference-aircraft validation unless the reference excludes it."
            ),
        )
        self.options.declare(
            "weight_margin_fraction",
            default=0.06,
            types=float,
            desc="Conceptual empty-weight design margin fraction.",
        )

        # ------------------------------------------------------------------
        # Helium / internal-volume assumptions
        # ------------------------------------------------------------------
        self.options.declare(
            "helium_calibration_factor",
            default=1.0,
            types=float,
        )
        self.options.declare(
            "structure_volumetric_index",
            default=0.0,
            types=float,
            desc=(
                "Fraction of gross hull volume unavailable to lifting gas "
                "because of internal structure. Explicit model assumption."
            ),
        )
        self.options.declare(
            "gondola_volumetric_index",
            default=0.0,
            types=float,
            desc=(
                "simplified/internal-gondola displacement proxy [m^3/kg payload]. "
                "Default is zero because a conventional gondola is external."
            ),
        )
        self.options.declare(
            "buoyancy_reserve",
            default=0.0,
            types=float,
            desc=(
                "Additional lifting-gas-volume reserve fraction. Default zero; "
                "do not double count ballonet/usable-volume allowances."
            ),
        )
        self.options.declare(
            "minimum_helium_volume",
            default=1.0e-6,
            types=float,
        )

        # ------------------------------------------------------------------
        # Closure controls
        # ------------------------------------------------------------------
        self.options.declare(
            "mass_closure_tolerance",
            default=1.0e-8,
            types=float,
        )
        self.options.declare(
            "mass_closure_maxiter",
            default=100,
            types=int,
        )

    # ======================================================================
    # Setup
    # ======================================================================

    def setup(self):
        n = self.options["num_steps"]
        airship_type = self.options["airship_type"]
        uses_tank = self.options["power_source"] in TANK_SOURCES

        # ------------------------------------------------------------------
        # Geometry inputs
        # ------------------------------------------------------------------
        self.add_input("payload", val=1123.0, units="kg")
        self.add_input("aerodynamic_reference_area", val=1050.0, units="m**2")
        self.add_input("gross_volume", val=4979.0, units="m**3")
        self.add_input("ballonet_volume", val=500.0, units="m**3")

        # simplified geometry input; used only by simplified tail mass mode.
        self.add_input("fin_area", val=50.0, units="m**2")

        # New Geometry outputs. If promoted in AirshipAnalysisGroup these
        # connect automatically by name.
        self.add_input(
            "horizontal_tail_planform_area",
            val=25.0,
            units="m**2",
        )
        self.add_input(
            "vertical_tail_planform_area",
            val=25.0,
            units="m**2",
        )
        self.add_input(
            "length",
            val=53.6,
            units="m",
            desc="Hull length; used for projected side-area/curtain sizing.",
        )
        self.add_input(
            "max_diameter",
            val=13.1,
            units="m",
            desc="Hull maximum diameter; used for projected side area.",
        )

        if airship_type in ["semi-rigid", "rigid"]:
            self.add_input("outer_envelope_area", val=1050.0, units="m**2")
            self.add_input("inner_envelope_area", val=250.0, units="m**2")
            self.add_input(
                "framework_total_member_length",
                val=0.0,
                units="m",
            )

        if airship_type == "rigid":
            self.add_input(
                "gas_cell_total_volume",
                val=0.0,
                units="m**3",
                desc="Total usable lifting-gas volume from Geometry.",
            )

        # ------------------------------------------------------------------
        # Gondola inputs
        # ------------------------------------------------------------------
        self.add_input(
            "gondola_length",
            val=13.1,
            units="m",
            desc="Gondola/crew-station length for Eq. (9.6).",
        )
        self.add_input(
            "gondola_width",
            val=2.56,
            units="m",
            desc="Gondola/crew-station width for Eq. (9.6).",
        )
        self.add_input(
            "gondola_height",
            val=2.29,
            units="m",
            desc="Gondola/crew-station height for Eq. (9.6).",
        )
        self.add_input(
            "gondola_surface_area",
            val=0.0,
            units="m**2",
            desc=(
                "External gondola surface area for Category 3 Eq. (9.7). "
                "If <=0, a rectangular six-side approximation is used."
            ),
        )
        self.add_input(
            "maximum_speed",
            val=19.57,
            units="m/s",
            desc="Maximum design speed used by gondola Eq. (9.6).",
        )

        # ------------------------------------------------------------------
        # Tail loading input
        # ------------------------------------------------------------------
        self.add_input(
            "max_dynamic_pressure",
            val=240.0,
            units="Pa",
            desc=(
                "Maximum design dynamic pressure for Chapter 9 tail WER. "
                "Book endpoint coefficients are defined at q<1 and q>10 psf."
            ),
        )


        self.add_input(
            "n_fuel_tanks",
            val=2.0,
        )

        self.add_input(
            "integral_fuel_tank_flag",
            val=0.0,
            desc="0 for non-integral tanks; 1 for integral tanks.",
        )

        self.add_input(
            "liquid_fuel_density_lb_gal",
            val=6.0,
            units="lb/galUS",
        )

        # ------------------------------------------------------------------
        # Installed subsystem inputs
        # ------------------------------------------------------------------
        self.add_input(
            "propulsion_mass",
            val=0.0,
            units="kg",
            desc="Engine/motor, propeller, nacelle, and mount mass.",
        )
        self.add_input(
            "power_system_mass",
            val=0.0,
            units="kg",
            desc=(
                "Installed conversion or energy-storage system mass, "
                "excluding hydrogen tank mass."
            ),
        )
        self.add_input(
            "power_system_volume",
            val=0.0,
            units="m**3",
        )

        if uses_tank:
            self.add_input(
                "tank_mass",
                val=0.0,
                units="kg",
                desc="Empty hydrogen tank-system mass.",
            )
            self.add_input(
                "tank_installed_volume",
                val=0.0,
                units="m**3",
                desc="Internal hydrogen storage volume.",
            )

        # ------------------------------------------------------------------
        # Mission / atmosphere / configuration inputs
        # ------------------------------------------------------------------
        self.add_input(
            "cruise_altp",
            val=np.full(n, 914.0),
            units="m",
        )
        self.add_input(
            "cruise_disa",
            val=np.zeros(n),
            units="K",
        )
        self.add_input(
            "max_altitude",
            val=3048.0,
            units="m",
            desc=(
                "Maximum pressure altitude. Helium mass is evaluated from the "
                "maximum-altitude lifting-gas volume, where the ballonet is "
                "conceptually empty for non-rigid/semi-rigid airships."
            ),
        )
        self.add_input(
            "BR_takeoff",
            val=0.90,
            desc="Takeoff buoyancy ratio used by conventional landing-gear WER.",
        )

        
        self.add_input(
            "width",
            val=13.1,
            units="m",
            desc="simplified compatibility input; not used by book gondola WER.",
        )
        self.add_input(
            "height",
            val=13.1,
            units="m",
            desc="simplified compatibility input; not used by book gondola WER.",
        )

        self.add_input("n_engine", val=2.0)
        self.add_input("n_crew", val=1.0)
        self.add_input(
            "consumable_mass",
            val=0.0,
            units="kg",
            desc=(
                "Installed mission fuel or hydrogen mass including reserve. "
                "Use zero for architectures without consumable fuel."
            ),
        )
        self.add_input("ballast_mass", val=0.0, units="kg")

        if self.options["landing_system"] == "acls":
            self.add_input(
                "acls_area",
                val=377.0,
                units="m**2",
            )

        # ------------------------------------------------------------------
        # Core outputs - simplified names preserved
        # ------------------------------------------------------------------
        self.add_output("envelop_mass", units="kg")
        self.add_output("envelope_mass", units="kg")
        self.add_output("gondola_mass", units="kg")
        self.add_output("fin_mass", units="kg")
        self.add_output("landing_system_mass", units="kg")
        self.add_output("miscellaneous_mass", units="kg")
        self.add_output("owe", units="kg")
        self.add_output("mtow", units="kg")
        self.add_output("operational_weight", units="kg")
        self.add_output("he_max_volume", units="m**3")
        self.add_output("he_max_mass", units="kg")
        self.add_output("air_max_volume", units="m**3")
        self.add_output(
            "envelope_volume_violation",
            units="m**3",
            desc="Positive unavailable-volume violation; zero is feasible.",
        )
        self.add_output("pressure_system_mass",units="kg",)

        if airship_type in ["semi-rigid", "rigid"]:
            self.add_output("framework_mass", units="kg")

        # ------------------------------------------------------------------
        # New transparent subsystem outputs
        # ------------------------------------------------------------------
        self.add_output("fuel_tank_mass",units="kg",)
        self.add_output("ballonet_mass", units="kg")
        self.add_output("curtain_mass", units="kg")
        self.add_output("curtain_area", units="m**2")
        self.add_output("tail_fixed_mass", units="kg")
        self.add_output("tail_control_surface_mass", units="kg")
        self.add_output("tail_actuator_mass", units="kg")
        self.add_output("tail_fpsq_used", units="lb/ft**2")
        self.add_output("tail_fact_used", units="lb/ft**2")
        self.add_output("weight_margin_mass", units="kg")
        self.add_output("unmargined_owe", units="kg")
        self.add_output("vms_mass",units="kg",)

        self.add_output("crew_mass", units="kg")
        self.add_output(
            "structure_mass",
            units="kg",
            desc=(
                "Airframe/structural aggregate diagnostic including envelope, "
                "ballonet, curtain, framework, gondola, tail, and landing system."
            ),
        )
        self.add_output(
            "installed_system_mass",
            units="kg",
            desc="Propulsion, power-system, and empty tank-system mass.",
        )
        self.add_output(
            "useful_load_mass",
            units="kg",
            desc="simplified diagnostic: payload plus crew mass.",
        )
        self.add_output(
            "installed_consumable_mass",
            units="kg",
            desc="Consumable mass included in MTOW.",
        )
        self.add_output(
            "mass_balance_error",
            units="kg",
            desc=(
                "MTOW minus explicit OEW+payload+consumable+ballast sum. "
                "Should be approximately zero."
            ),
        )

        self.declare_partials("*", "*", method="fd", step=1.0e-8)

    # ======================================================================
    # Helpers
    # ======================================================================

    @staticmethod
    def _scalar(value):
        return float(np.asarray(value).ravel()[0])

    @staticmethod
    def _rectangular_box_surface_area(length_m, width_m, height_m):
        """Six-side surface area used only as a Category-3 conceptual fallback."""
        return 2.0 * (
            length_m * width_m
            + length_m * height_m
            + width_m * height_m
        )

    @staticmethod
    def _two_spherical_ballonet_area(total_volume_m3):
        """
        Surface area of two equal spherical ballonets.

        Each ballonet volume is total_volume/2.
        """
        if total_volume_m3 <= 0.0:
            return 0.0

        v_each = 0.5 * total_volume_m3
        radius = (3.0 * v_each / (4.0 * np.pi)) ** (1.0 / 3.0)
        return 2.0 * 4.0 * np.pi * radius**2

    def _tail_coefficients_from_q(self, q_pa):
        """
        Return F_PSQ and F_act in the original Chapter-9 units [lb/ft^2].

        Book endpoints:
            q < 1 psf  -> F_PSQ=0.3, F_act=0.08
            q > 10 psf -> F_PSQ=1.0, F_act=0.79

        For 1 <= q <= 10 psf ADaPT linearly interpolates between the two
        literature endpoints. This interpolation is explicitly an adapted
        conceptual relationship [A].
        """
        q_psf = max(q_pa * PA_TO_PSF, 0.0)

        fpsq_low = float(self.options["tail_fpsq_low_q"])
        fpsq_high = float(self.options["tail_fpsq_high_q"])
        fact_low = float(self.options["tail_fact_low_q"])
        fact_high = float(self.options["tail_fact_high_q"])

        if q_psf <= 1.0:
            return fpsq_low, fact_low
        if q_psf >= 10.0:
            return fpsq_high, fact_high

        t = (q_psf - 1.0) / 9.0
        fpsq = fpsq_low + t * (fpsq_high - fpsq_low)
        fact = fact_low + t * (fact_high - fact_low)
        return fpsq, fact

    def _book_gondola_mass(self, payload_kg, inputs):
        """
        Gondola mass from Chapter 9 Eqs. (9.5)-(9.7).

        All book equations are evaluated in their original imperial units.
        """
        category = int(self.options["gondola_category"])
        payload_lb = payload_kg * KG_TO_LB

        if category == 1:
            # Eq. (9.5)
            w_gond_lb = 0.15 * payload_lb
            return w_gond_lb * LB_TO_KG

        l_ft = max(self._scalar(inputs["gondola_length"]) * M_TO_FT, 1.0e-12)
        w_ft = max(self._scalar(inputs["gondola_width"]) * M_TO_FT, 1.0e-12)
        h_ft = max(self._scalar(inputs["gondola_height"]) * M_TO_FT, 1.0e-12)
        vmax_kt = max(
            self._scalar(inputs["maximum_speed"]) * 1.9438444924406048,
            1.0e-12,
        )

        # Eq. (9.6): crew station + systems / Category 2 gondola.
        w_category2_lb = 353.0 * (
            (l_ft / 10.0) ** 0.857
            * ((w_ft + h_ft) / 10.0)
            * (vmax_kt / 10.0) ** 0.338
        ) ** 1.1

        if category == 2:
            return w_category2_lb * LB_TO_KG

        # Eq. (9.7): heavy payload bay plus crew station/systems.
        area_m2 = self._scalar(inputs["gondola_surface_area"])
        if area_m2 <= 0.0:
            area_m2 = self._rectangular_box_surface_area(
                self._scalar(inputs["gondola_length"]),
                self._scalar(inputs["gondola_width"]),
                self._scalar(inputs["gondola_height"]),
            )

        area_ft2 = area_m2 * M2_TO_FT2
        w_category3_lb = 1.875 * area_ft2 + w_category2_lb
        return w_category3_lb * LB_TO_KG

    def _conventional_landing_mass(self, mtow_kg, br_takeoff):
        """
        Chapter 9 Eqs. (9.19)/(9.20), evaluated in original imperial units.

        WH0 is represented as takeoff heaviness:
            WH0 = (1 - BR_TO) * W_TO
        in lbf numerically.
        """
        if self.options["landing_gear_method"] == "simplified_fraction":
            frac = np.clip(
                float(self.options["landing_gear_fraction"]),
                0.0,
                0.95,
            )
            return frac * mtow_kg

        mtow_lb = max(mtow_kg, 0.0) * KG_TO_LB
        br = float(np.clip(br_takeoff, 0.0, 1.5))
        wh0_lb = max((1.0 - br) * mtow_lb, 0.0)

        if self.options["conventional_gear_type"] == "single":
            coeff = 24.2  # Eq. (9.19)
        else:
            coeff = 31.2  # Eq. (9.20)

        w_lg_lb = coeff * (2.0 * wh0_lb / 1000.0) ** 0.84
        return w_lg_lb * LB_TO_KG

    def compute(self, inputs, outputs):

        opt = self.options
        phd = opt["phd"]

        airship_type = opt["airship_type"]
        power_source = opt["power_source"]
        uses_tank = power_source in TANK_SOURCES

        # ==============================================================
        # Inputs
        # ==============================================================

        payload = max(
            self._scalar(inputs["payload"]),
            0.0,
        )

        aerodynamic_reference_area = max(
            self._scalar(inputs["aerodynamic_reference_area"]),
            1.0e-12,
        )

        gross_volume = max(
            self._scalar(inputs["gross_volume"]),
            1.0e-12,
        )

        ballonet_volume = max(
            self._scalar(inputs["ballonet_volume"]),
            0.0,
        )

        length = max(
            self._scalar(inputs["length"]),
            1.0e-12,
        )

        max_diameter = max(
            self._scalar(inputs["max_diameter"]),
            1.0e-12,
        )

        propulsion_mass = max(
            self._scalar(inputs["propulsion_mass"]),
            0.0,
        )

        power_system_mass = max(
            self._scalar(inputs["power_system_mass"]),
            0.0,
        )

        power_system_volume = max(
            self._scalar(inputs["power_system_volume"]),
            0.0,
        )

        # --------------------------------------------------------------
        # Hydrogen tank system
        # --------------------------------------------------------------

        if uses_tank:

            tank_mass = max(
                self._scalar(inputs["tank_mass"]),
                0.0,
            )

            tank_installed_volume = max(
                self._scalar(inputs["tank_installed_volume"]),
                0.0,
            )

        else:

            tank_mass = 0.0
            tank_installed_volume = 0.0

        # --------------------------------------------------------------
        # Mission / operating quantities
        # --------------------------------------------------------------

        cruise_disa = np.atleast_1d(
            inputs["cruise_disa"]
        ).astype(float)

        average_disa = float(
            np.mean(cruise_disa)
        )

        n_crew = max(
            int(
                round(
                    self._scalar(inputs["n_crew"])
                )
            ),
            0,
        )

        consumable_mass = max(
            self._scalar(inputs["consumable_mass"]),
            0.0,
        )

        ballast_mass = max(
            self._scalar(inputs["ballast_mass"]),
            0.0,
        )

        br_takeoff = self._scalar(
            inputs["BR_takeoff"]
        )

        crew_mass = (
            n_crew
            * float(opt["crew_mass_each"])
        )

        # ==============================================================
        # Conventional liquid-fuel tank mass
        # ==============================================================
        #
        # Chapter-9/11 WER:
        #
        # W_FT =
        #   2.49
        #   * Fuel_gal^0.6
        #   * N_tank^0.2
        #   * N_engine^0.13
        #   * [1/(1 + Int)]^0.3
        #
        # This term represents EMPTY conventional liquid-fuel tank
        # hardware and therefore belongs in OEW.
        #
        # The fuel itself remains in consumable_mass and is added
        # separately when calculating MTOW.
        # ==============================================================

        fuel_tank_method = opt[
            "fuel_tank_weight_method"
        ]

        if fuel_tank_method == "book":

            fuel_lb = (
                consumable_mass
                * KG_TO_LB
            )

            fuel_density_lb_gal = max(
                self._scalar(
                    inputs[
                        "liquid_fuel_density_lb_gal"
                    ]
                ),
                1.0e-12,
            )

            fuel_gal = (
                fuel_lb
                / fuel_density_lb_gal
            )

            n_tanks = max(
                self._scalar(
                    inputs["n_fuel_tanks"]
                ),
                1.0,
            )

            n_engine = max(
                self._scalar(
                    inputs["n_engine"]
                ),
                1.0,
            )

            integral_flag = max(
                self._scalar(
                    inputs[
                        "integral_fuel_tank_flag"
                    ]
                ),
                0.0,
            )

            w_fuel_tank_lb = (
                2.49
                * fuel_gal**0.6
                * n_tanks**0.2
                * n_engine**0.13
                * (
                    1.0
                    / (1.0 + integral_flag)
                )**0.3
            )

            fuel_tank_mass = (
                w_fuel_tank_lb
                * LB_TO_KG
            )

        elif fuel_tank_method == "override":

            fuel_tank_mass = max(
                float(
                    opt[
                        "fuel_tank_mass_override"
                    ]
                ),
                0.0,
            )

        else:

            fuel_tank_mass = 0.0

        # ==============================================================
        # Envelope mass
        # ==============================================================

        framework_mass = 0.0

        if airship_type == "non-rigid":

            if (
                opt["envelope_weight_method"]
                == "book"
            ):

                envelope_mass = (
                    aerodynamic_reference_area
                    * float(
                        opt[
                            "envelope_fabric_areal_density"
                        ]
                    )
                    * float(
                        opt[
                            "envelope_manufacturing_factor"
                        ]
                    )
                    * float(
                        opt[
                            "envelope_attachment_factor"
                        ]
                    )
                )

            else:

                envelope_mass = (
                    aerodynamic_reference_area
                    * float(
                        opt[
                            "envelope_areal_density_nonrigid"
                        ]
                    )
                )

        else:

            outer_area = max(
                self._scalar(
                    inputs[
                        "outer_envelope_area"
                    ]
                ),
                1.0e-12,
            )

            inner_area = max(
                self._scalar(
                    inputs[
                        "inner_envelope_area"
                    ]
                ),
                0.0,
            )

            member_length = max(
                self._scalar(
                    inputs[
                        "framework_total_member_length"
                    ]
                ),
                0.0,
            )

            outer_areal_density = float(
                opt[
                    "outer_envelope_areal_density"
                ]
            )

            inner_areal_density = float(
                opt[
                    "inner_envelope_areal_density"
                ]
            )

            envelope_mass = (
                outer_area
                * outer_areal_density
                + inner_area
                * inner_areal_density
            )

            # ----------------------------------------------------------
            # Semi-rigid / rigid conceptual framework
            # ----------------------------------------------------------

            volume_two_thirds = (
                gross_volume
                ** (2.0 / 3.0)
            )

            framework_model = opt[
                "framework_mass_model"
            ]

            if framework_model == "linear":

                framework_mass = (
                    member_length
                    * float(
                        opt[
                            "frame_linear_density"
                        ]
                    )
                )

            elif framework_model == "ld":

                framework_mass = (
                    float(
                        opt[
                            "k_framework_ld"
                        ]
                    )
                    * volume_two_thirds
                )

            elif (
                framework_model
                == "fraction_envelope"
            ):

                framework_fraction = (
                    0.20
                    if airship_type
                    == "semi-rigid"
                    else 0.35
                )

                framework_mass = (
                    framework_fraction
                    * outer_area
                    * outer_areal_density
                )

            else:

                framework_mass = (
                    float(
                        opt[
                            "k_framework_v23"
                        ]
                    )
                    * volume_two_thirds
                )

        # ==============================================================
        # Ballonet mass
        # ==============================================================

        if (
            airship_type != "rigid"
            and bool(
                opt["include_ballonet_mass"]
            )
            and ballonet_volume > 0.0
        ):

            ballonet_surface_m2 = (
                self._two_spherical_ballonet_area(
                    ballonet_volume
                )
            )

            ballonet_surface_ft2 = (
                ballonet_surface_m2
                * M2_TO_FT2
            )

            w_ballonet_lb = (
                float(
                    opt[
                        "ballonet_fabric_density_lb_ft2"
                    ]
                )
                * ballonet_surface_ft2
                * float(
                    opt[
                        "ballonet_weight_factor"
                    ]
                )
            )

            ballonet_mass = (
                w_ballonet_lb
                * LB_TO_KG
            )

        else:

            ballonet_mass = 0.0

        # ==============================================================
        # Suspension curtain mass
        # ==============================================================

        if (
            airship_type
            in ["non-rigid", "semi-rigid"]
            and bool(
                opt[
                    "include_suspension_curtain"
                ]
            )
        ):

            # Side projection of axisymmetric hull:
            # ellipse of length L and height D.
            side_projected_area_m2 = (
                np.pi
                * length
                * max_diameter
                / 4.0
            )

            curtain_area_m2 = (
                float(
                    opt[
                        "curtain_area_fraction"
                    ]
                )
                * side_projected_area_m2
            )

            curtain_area_ft2 = (
                curtain_area_m2
                * M2_TO_FT2
            )

            w_curtain_lb = (
                float(
                    opt[
                        "curtain_fabric_density_lb_ft2"
                    ]
                )
                * curtain_area_ft2
                * float(
                    opt[
                        "curtain_joint_factor"
                    ]
                )
            )

            curtain_mass = (
                w_curtain_lb
                * LB_TO_KG
            )

        else:

            curtain_area_m2 = 0.0
            curtain_mass = 0.0

        # ==============================================================
        # Tail mass
        # ==============================================================

        if (
            opt["tail_weight_method"]
            == "simplified_areal"
        ):

            fin_area = max(
                self._scalar(
                    inputs["fin_area"]
                ),
                0.0,
            )

            fin_mass = (
                fin_area
                * float(
                    opt[
                        "fin_areal_density"
                    ]
                )
            )

            tail_fixed_mass = fin_mass
            tail_control_mass = 0.0
            tail_actuator_mass = 0.0

            fpsq_used = 0.0
            fact_used = 0.0

        else:

            s_ht = max(
                self._scalar(
                    inputs[
                        "horizontal_tail_planform_area"
                    ]
                ),
                0.0,
            )

            s_vt = max(
                self._scalar(
                    inputs[
                        "vertical_tail_planform_area"
                    ]
                ),
                0.0,
            )

            s_tail_m2 = (
                s_ht
                + s_vt
            )

            s_tail_ft2 = (
                s_tail_m2
                * M2_TO_FT2
            )

            control_fraction = float(
                np.clip(
                    opt[
                        "tail_control_surface_fraction"
                    ],
                    0.0,
                    0.95,
                )
            )

            fixed_fraction = (
                1.0
                - control_fraction
            )

            q_pa = max(
                self._scalar(
                    inputs[
                        "max_dynamic_pressure"
                    ]
                ),
                0.0,
            )

            (
                fpsq_used,
                fact_used,
            ) = (
                self._tail_coefficients_from_q(
                    q_pa
                )
            )

            # ----------------------------------------------------------
            # Eq. (9.2): fixed tail structure
            # ----------------------------------------------------------

            w_fixed_lb = (
                fpsq_used
                * fixed_fraction
                * s_tail_ft2
                * float(
                    opt[
                        "tail_attachment_factor"
                    ]
                )
            )

            # ----------------------------------------------------------
            # Eq. (9.3): movable surfaces
            # ----------------------------------------------------------

            w_control_lb = (
                fpsq_used
                * control_fraction
                * s_tail_ft2
            )

            # ----------------------------------------------------------
            # Eq. (9.4): actuators
            # ----------------------------------------------------------

            w_act_lb = (
                fact_used
                * control_fraction
                * s_tail_ft2
                * float(
                    opt[
                        "tail_actuator_installation_factor"
                    ]
                )
            )

            tail_fixed_mass = (
                w_fixed_lb
                * LB_TO_KG
            )

            tail_control_mass = (
                w_control_lb
                * LB_TO_KG
            )

            tail_actuator_mass = (
                w_act_lb
                * LB_TO_KG
            )

            fin_mass = (
                tail_fixed_mass
                + tail_control_mass
                + tail_actuator_mass
            )

        # ==============================================================
        # Gondola mass
        # ==============================================================

        gondola_method = opt[
            "gondola_weight_method"
        ]

        if gondola_method == "override":

            gondola_mass = max(
                float(
                    opt[
                        "gondola_mass_override"
                    ]
                ),
                0.0,
            )

        elif gondola_method == "simplified":

            if airship_type == "non-rigid":

                gondola_mass = 1500.0

            else:

                gondola_mass = (
                    250.0
                    + 0.05 * payload
                )

        else:

            gondola_mass = (
                self._book_gondola_mass(
                    payload,
                    inputs,
                )
            )

        # ==============================================================
        # Semi-rigid / rigid framework safeguard
        # ==============================================================

        if (
            airship_type
            in ["semi-rigid", "rigid"]
        ):

            framework_proxy = max(
                envelope_mass
                + gondola_mass
                + fin_mass
                + propulsion_mass
                + power_system_mass
                + tank_mass
                + crew_mass,
                1.0,
            )

            framework_cap = (
                float(
                    opt[
                        "framework_mass_frac_cap"
                    ]
                )
                * framework_proxy
            )

            framework_mass = min(
                framework_mass,
                framework_cap,
            )

        # ==============================================================
        # Helium volume and helium mass
        # ==============================================================
        #
        # At maximum pressure altitude the ballonet is conceptually
        # empty for non-rigid/semi-rigid airships. Installed ballonet
        # CAPACITY therefore does not reduce maximum helium volume.
        #
        # Helium is used for gas-state/buoyancy calculations and is NOT
        # included in OEW or MTOW.
        # ==============================================================

        structure_fraction = float(
            np.clip(
                opt[
                    "structure_volumetric_index"
                ],
                0.0,
                0.95,
            )
        )

        reserve_fraction = float(
            np.clip(
                opt["buoyancy_reserve"],
                0.0,
                0.95,
            )
        )

        if airship_type == "rigid":

            gas_cell_total_volume = max(
                self._scalar(
                    inputs[
                        "gas_cell_total_volume"
                    ]
                ),
                0.0,
            )

            if gas_cell_total_volume > 0.0:

                base_lifting_volume = (
                    gas_cell_total_volume
                )

            else:

                # Backward-compatibility fallback.
                base_lifting_volume = (
                    gross_volume
                    / 1.10
                )

        else:

            base_lifting_volume = (
                gross_volume
            )

        he_max_volume_raw = (
            (
                1.0
                - structure_fraction
                - reserve_fraction
            )
            * base_lifting_volume
            - float(
                opt[
                    "gondola_volumetric_index"
                ]
            )
            * payload
            - power_system_volume
            - tank_installed_volume
        )

        outputs[
            "envelope_volume_violation"
        ] = max(
            -he_max_volume_raw,
            0.0,
        )

        he_max_volume = max(
            he_max_volume_raw,
            float(
                opt[
                    "minimum_helium_volume"
                ]
            ),
        )

        max_altitude = max(
            self._scalar(
                inputs["max_altitude"]
            ),
            0.0,
        )

        (
            max_pressure,
            max_temperature,
            _,
        ) = phd.atmosphere(
            max_altitude,
            average_disa,
        )

        rho_he_max_altitude = (
            phd.gas_density(
                max_pressure,
                max_temperature,
                gas="helium",
            )
        )

        he_max_mass = (
            float(
                opt[
                    "helium_calibration_factor"
                ]
            )
            * he_max_volume
            * rho_he_max_altitude
        )

        # --------------------------------------------------------------
        # Sea-level helium volume from conserved helium mass
        # --------------------------------------------------------------

        (
            sea_level_pressure,
            sea_level_temperature,
            _,
        ) = phd.atmosphere(
            0.0,
            average_disa,
        )

        rho_he_sea_level = (
            phd.gas_density(
                sea_level_pressure,
                sea_level_temperature,
                gas="helium",
            )
        )

        he_min_volume = (
            he_max_mass
            / max(
                float(
                    opt[
                        "helium_calibration_factor"
                    ]
                )
                * rho_he_sea_level,
                1.0e-12,
            )
        )

        air_max_volume = max(
            base_lifting_volume
            - he_min_volume,
            0.0,
        )

        # ==============================================================
        # ACLS mass
        # ==============================================================

        if (
            opt["landing_system"]
            == "acls"
        ):

            acls_area_m2 = max(
                self._scalar(
                    inputs["acls_area"]
                ),
                0.0,
            )

            acls_area_ft2 = (
                acls_area_m2
                * M2_TO_FT2
            )

            w_acls_lb = (
                float(
                    opt[
                        "acls_coefficient_lb_ft2"
                    ]
                )
                * acls_area_ft2
            )

            fixed_landing_mass = (
                w_acls_lb
                * LB_TO_KG
            )

        else:

            fixed_landing_mass = None

        # ==============================================================
        # Coupled OEW / MTOW closure
        # ==============================================================
        #
        # Book-dependent terms requiring closure:
        #
        #   landing gear:
        #       function of MTOW / takeoff heaviness
        #
        #   pressure system:
        #       W_press = f_press * OEW
        #
        #   VMS:
        #       W_VMS = f_VMS * OEW + W_actuator
        #
        #   miscellaneous systems:
        #       W_misc = f_misc * OEW
        #
        #   design margin:
        #       W_margin = f_margin * OEW
        #
        # The terms are solved simultaneously by fixed-point iteration.
        # ==============================================================

        pressure_method = opt[
            "pressure_system_weight_method"
        ]

        vms_method = opt[
            "vms_weight_method"
        ]

        # --------------------------------------------------------------
        # Tail bookkeeping
        # --------------------------------------------------------------
        #
        # Chapter 11 puts actuator mass in the VMS group.
        #
        # Therefore, when the book VMS method is active, actuator mass
        # is removed from the structural-tail contribution to OEW and
        # added exactly once through VMS.
        #
        # fin_mass itself remains unchanged as a physical-tail output.
        # --------------------------------------------------------------

        if vms_method == "book_fraction":

            tail_mass_for_owe = (
                tail_fixed_mass
                + tail_control_mass
            )

        else:

            tail_mass_for_owe = (
                fin_mass
            )

        # --------------------------------------------------------------
        # OEW terms independent of OEW/MTOW closure
        # --------------------------------------------------------------

        base_without_fractional_systems = (
            envelope_mass
            + ballonet_mass
            + curtain_mass
            + framework_mass
            + gondola_mass
            + tail_mass_for_owe
            + propulsion_mass
            + power_system_mass
            + tank_mass
            + fuel_tank_mass
            + crew_mass
        )

        # --------------------------------------------------------------
        # Fractional OEW terms
        # --------------------------------------------------------------

        misc_fraction = max(
            float(
                opt[
                    "miscellaneous_fraction"
                ]
            ),
            0.0,
        )

        margin_fraction = (
            max(
                float(
                    opt[
                        "weight_margin_fraction"
                    ]
                ),
                0.0,
            )
            if bool(
                opt["apply_weight_margin"]
            )
            else 0.0
        )

        # --------------------------------------------------------------
        # Initial estimate
        # --------------------------------------------------------------

        owe = (
            base_without_fractional_systems
        )

        mtow = (
            owe
            + payload
            + consumable_mass
            + ballast_mass
        )

        tol = float(
            opt[
                "mass_closure_tolerance"
            ]
        )

        maxiter = int(
            opt[
                "mass_closure_maxiter"
            ]
        )

        landing_system_mass = 0.0
        pressure_system_mass = 0.0
        vms_mass = 0.0
        miscellaneous_mass = 0.0
        weight_margin_mass = 0.0

        # ==============================================================
        # Fixed-point iteration
        # ==============================================================

        for _ in range(maxiter):

            old_owe = owe
            old_mtow = mtow

            # ----------------------------------------------------------
            # Landing gear
            # ----------------------------------------------------------

            if fixed_landing_mass is not None:

                landing_system_mass = (
                    fixed_landing_mass
                )

            else:

                landing_system_mass = (
                    self._conventional_landing_mass(
                        mtow,
                        br_takeoff,
                    )
                )

            # ----------------------------------------------------------
            # Pressure system
            # ----------------------------------------------------------

            if (
                pressure_method
                == "book_fraction"
            ):

                pressure_system_mass = (
                    max(
                        float(
                            opt[
                                "pressure_system_fraction"
                            ]
                        ),
                        0.0,
                    )
                    * max(owe, 0.0)
                )

            elif (
                pressure_method
                == "override"
            ):

                pressure_system_mass = max(
                    float(
                        opt[
                            "pressure_system_mass_override"
                        ]
                    ),
                    0.0,
                )

            else:

                pressure_system_mass = 0.0

            # ----------------------------------------------------------
            # Vehicle management system
            # ----------------------------------------------------------

            if (
                vms_method
                == "book_fraction"
            ):

                vms_mass = (
                    max(
                        float(
                            opt[
                                "vms_fraction"
                            ]
                        ),
                        0.0,
                    )
                    * max(owe, 0.0)
                    + tail_actuator_mass
                )

            elif (
                vms_method
                == "override"
            ):

                vms_mass = max(
                    float(
                        opt[
                            "vms_mass_override"
                        ]
                    ),
                    0.0,
                )

            else:

                vms_mass = 0.0

            # ----------------------------------------------------------
            # Miscellaneous systems
            # ----------------------------------------------------------

            miscellaneous_mass = (
                misc_fraction
                * max(owe, 0.0)
            )

            # ----------------------------------------------------------
            # Design margin
            # ----------------------------------------------------------

            weight_margin_mass = (
                margin_fraction
                * max(owe, 0.0)
            )

            # ----------------------------------------------------------
            # Updated OEW
            # ----------------------------------------------------------

            owe = (
                base_without_fractional_systems
                + landing_system_mass
                + pressure_system_mass
                + vms_mass
                + miscellaneous_mass
                + weight_margin_mass
            )

            # ----------------------------------------------------------
            # Updated MTOW
            # ----------------------------------------------------------

            mtow = (
                owe
                + payload
                + consumable_mass
                + ballast_mass
            )

            # ----------------------------------------------------------
            # Convergence
            # ----------------------------------------------------------

            scale = max(
                abs(owe),
                abs(mtow),
                1.0,
            )

            err = max(
                abs(owe - old_owe),
                abs(mtow - old_mtow),
            ) / scale

            if err <= tol:
                break

        # ==============================================================
        # Post-closure quantities
        # ==============================================================

        unmargined_owe = (
            owe
            - weight_margin_mass
        )

        operational_weight = (
            owe
            + payload
        )

        explicit_mtow_sum = (
            owe
            + payload
            + consumable_mass
            + ballast_mass
        )

        mass_balance_error = (
            mtow
            - explicit_mtow_sum
        )

        # --------------------------------------------------------------
        # Installed-system diagnostic
        # --------------------------------------------------------------
        #
        # Includes installed propulsion/energy/fuel-system hardware.
        # Pressure and VMS are also installed vehicle systems.
        # --------------------------------------------------------------

        installed_system_mass = (
            propulsion_mass
            + power_system_mass
            + tank_mass
            + fuel_tank_mass
            + pressure_system_mass
            + vms_mass
        )

        # --------------------------------------------------------------
        # Structural diagnostic
        # --------------------------------------------------------------
        #
        # Use the same accounting tail mass as OEW when VMS owns the
        # actuator. This avoids overlap between structure_mass and
        # installed_system_mass if those diagnostics are later summed.
        # --------------------------------------------------------------

        structure_mass = (
            envelope_mass
            + ballonet_mass
            + curtain_mass
            + framework_mass
            + gondola_mass
            + tail_mass_for_owe
            + landing_system_mass
        )

        useful_load_mass = (
            payload
            + crew_mass
        )

        # ==============================================================
        # Outputs
        # ==============================================================

        # Envelope / structure
        outputs["envelop_mass"] = (
            envelope_mass
        )

        outputs["envelope_mass"] = (
            envelope_mass
        )

        outputs["ballonet_mass"] = (
            ballonet_mass
        )

        outputs["curtain_mass"] = (
            curtain_mass
        )

        outputs["curtain_area"] = (
            curtain_area_m2
        )

        # Gondola
        outputs["gondola_mass"] = (
            gondola_mass
        )

        # Conventional fuel tank
        outputs["fuel_tank_mass"] = (
            fuel_tank_mass
        )

        # Pressure / VMS
        outputs["pressure_system_mass"] = (
            pressure_system_mass
        )

        outputs["vms_mass"] = (
            vms_mass
        )

        # Tail
        outputs["fin_mass"] = (
            fin_mass
        )

        outputs["tail_fixed_mass"] = (
            tail_fixed_mass
        )

        outputs[
            "tail_control_surface_mass"
        ] = tail_control_mass

        outputs["tail_actuator_mass"] = (
            tail_actuator_mass
        )

        outputs["tail_fpsq_used"] = (
            fpsq_used
        )

        outputs["tail_fact_used"] = (
            fact_used
        )

        # Landing / misc / margin
        outputs["landing_system_mass"] = (
            landing_system_mass
        )

        outputs["miscellaneous_mass"] = (
            miscellaneous_mass
        )

        outputs["weight_margin_mass"] = (
            weight_margin_mass
        )

        outputs["unmargined_owe"] = (
            unmargined_owe
        )

        # Vehicle weights
        outputs["owe"] = owe
        outputs["mtow"] = mtow

        outputs["operational_weight"] = (
            operational_weight
        )

        # Helium / available internal volume
        outputs["he_max_volume"] = (
            he_max_volume
        )

        outputs["he_max_mass"] = (
            he_max_mass
        )

        outputs["air_max_volume"] = (
            air_max_volume
        )

        # Diagnostics
        outputs["crew_mass"] = (
            crew_mass
        )

        outputs["structure_mass"] = (
            structure_mass
        )

        outputs["installed_system_mass"] = (
            installed_system_mass
        )

        outputs["useful_load_mass"] = (
            useful_load_mass
        )

        outputs[
            "installed_consumable_mass"
        ] = consumable_mass

        outputs["mass_balance_error"] = (
            mass_balance_error
        )

        if (
            airship_type
            in ["semi-rigid", "rigid"]
        ):

            outputs["framework_mass"] = (
                framework_mass
            )


if __name__ == "__main__":
    print(
        "AirshipWeight component loaded successfully. "
        "Instantiate it inside an OpenMDAO Problem with a valid phd object."
    )
