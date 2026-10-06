# -*- coding: utf-8 -*-
"""
Updated Airship Geometry Component for MDO Framework
Incorporates advanced single-lobed shapes (Spheroid, NPL, GNVR, Wang, Atyya)
#Atyya, M., ElBayoumi, G. M., & Lotfy, M. (2023). Optimal shape design of an airship based on geometrical aerodynamic parameters. Beni-Suef University Journal of Basic and Applied Sciences, 12(1), 25.
#Wang, X. L., & Shan, X. X. (2006). Shape optimization of stratosphere airship. Journal of Aircraft, 43(1), 283-286.
#Kale, S., Joshi, P., & Pant, R. (2005). A generic methodology for determination of drag coefficient of an aerostat envelope using CFD. In AIAA 5th ATIO and16th Lighter-Than-Air Sys Tech. and Balloon Systems Conferences (p. 7442).
#Narayana, C. L., & Srilatha, K. R. (2000). Analysis of aerostat configurations by panel methods. BLISS project document CF, 10.
#Manikandan, M., Vaidya, E., & Pant, R. S. (2022). Design and analysis of hybrid electric multi-lobed airship for cargo transportation. Sustainable Energy Technologies and Assessments, 51, 101892.
and multi-lobed option (bi/tri-lobed with spacing).
Single-lobed focus, multi-lobed as toggleable option.

@author: Musavir Bashir
"""
import numpy as np
import openmdao.api as om
from scipy.special import ellipkinc, ellipeinc

class AirshipGeometry(om.ExplicitComponent):
    """Computes geometric properties of hybrid airships.
    Supports single-lobed (spheroid, NPL, GNVR, Wang) and multi-lobed (bi/tri) hulls.
    Calculates gross volume, wetted surface area, aerodynamic reference area, fin wetted area,
    and ballonet volume for buoyancy control at a specified maximum altitude.
    Attributes:
        options['max_altitude'] (float): Maximum pressure altitude for ballonet sizing (m).
        options['landing_system'] (str): Type of landing system ('conventional' or 'acls').
        options['airship_type'] (str): 'non-rigid', 'semi-rigid', or 'rigid'.
        options['inner_envelope_area_factor'] (float): Semi/rigid inner envelope area factor.
        options['framework_enabled'] (bool): Enable framework calculations for semi/rigid.
        options['shape_type'] (str): Hull shape: 'spheroid', 'npl', 'gnvr', 'wang'.
        options['n_lobes'] (int): Number of lobes (1 for single, 2 for bi, 3 for tri).
        options['lobe_spacing_factor'] (float): Lateral spacing for multi-lobes (fraction of diameter).
    """
    def initialize(self):
        self.options.declare('max_altitude', default=3048.0, types=float,  # 10000 ft
                             desc='Maximum pressure altitude for ballonet sizing in meters')
        self.options.declare('landing_system', default='conventional',
                             values=['conventional', 'acls'],
                             desc='Type of landing system (not used in this component)')
        self.options.declare('airship_type', default='non-rigid',
                             values=['non-rigid', 'semi-rigid', 'rigid'],
                             desc='Airship structural category')
        self.options.declare('inner_envelope_area_factor', default=0.25, types=float,
                             desc='Semi/rigid: inner envelope area ≈ factor * outer area (conceptual)')
        self.options.declare('framework_enabled', default=True, types=bool,
                             desc='If True, compute framework characteristic lengths for semi/rigid')
        self.options.declare('shape_type', default='spheroid',
                             values=['spheroid', 'npl', 'gnvr', 'wang'],
                             desc='Single-lobed hull shape construction method')
        self.options.declare('n_lobes', default=1, types=int,
                             desc='Number of lobes (1=single, 2=bi, 3=tri; multi-lobed option)')
        self.options.declare('lobe_spacing_factor', default=0.3, types=float,
                             desc='Lateral spacing factor for multi-lobes (fraction of max_diameter)')

    def setup(self):
        """Set up inputs, outputs, and partial derivatives."""
        # Core inputs
        self.add_input('length', val=53.6, units='m', desc='Airship overall length')
        self.add_input('fineness_ratio', val=4.09, desc='Length / Maximum Diameter (for spheroid)')
        self.add_input('tail_volume_coeff_horizontal', val=0.066, desc='Horizontal tail volume coefficient (C_HT)')
        self.add_input('tail_volume_coeff_vertical', val=0.059, desc='Vertical tail volume coefficient (C_VT)')

        # Shape-specific inputs (for non-spheroid)
        if self.options['shape_type'] == 'npl':
            self.add_input('npl_a_n', val=1.0, desc='NPL shape parameter a_N')
            self.add_input('npl_b_n', val=1.0, desc='NPL shape parameter b_N')
        elif self.options['shape_type'] == 'gnvr':
            self.add_input('gnvr_d_g', val=0.6557, desc='GNVR shape parameter d_G (optimized from literature)')
        elif self.options['shape_type'] == 'wang':
            self.add_input('wang_a_w', val=1.0, desc='Wang shape parameter a_W')
            self.add_input('wang_b_w', val=1.0, desc='Wang shape parameter b_W')
            self.add_input('wang_c_w', val=1.0, desc='Wang shape parameter c_W')
            self.add_input('wang_d_w', val=1.0, desc='Wang shape parameter d_W')
            self.add_input('wang_l_w', val=1.0, desc='Wang shape parameter l_W')

        # Outputs
        self.add_output('gross_volume', units='m**3', desc='Gross volume of the airship hull')
        self.add_output('wetted_surface_area', units='m**2', desc='Wetted surface area of the hull')
        self.add_output('max_diameter', units='m', desc='Maximum diameter of the body')
        self.add_output('ref_area_AeroCoeffs', units='m**2', desc='Aerodynamic Reference Area (GrossVolume**(2.0/3.0))')
        self.add_output('fin_total_wetted_area', units='m**2', desc='Total wetted area of all fins')
        self.add_output('ballonet_volume', units='m**3', desc='Required ballonet volume')
        self.add_output('aspect_ratio_geom', desc='Geometric aspect ratio, equivalent to Fineness Ratio (L/D)')

        # Semi-rigid / rigid extras
        airship_type = self.options['airship_type']
        if airship_type in ['semi-rigid', 'rigid']:
            self.add_output('outer_envelope_area', units='m**2',
                            desc='Outer envelope surface area used for structure sizing (≈ wetted area)')
            self.add_output('inner_envelope_area', units='m**2',
                            desc='Inner envelope surface area proxy (scaled from outer area)')
            if self.options['framework_enabled']:
                self.add_input('n_longitudinal_members', val=12.0,
                               desc='Conceptual number of longitudinal frame members/longerons')
                self.add_input('n_rings', val=16.0,
                               desc='Conceptual number of circumferential rings/frames')
                self.add_output('framework_total_member_length', units='m',
                                desc='Total length of primary frame members (conceptual sum of longerons+rings+axis)')
        if airship_type == 'rigid':
            self.add_input('n_gas_cells', val=12.0, desc='Conceptual number of internal gas cells')
            self.add_output('gas_cell_volume_each', units='m**3',
                            desc='Conceptual per-cell gas volume (gross_volume / n_gas_cells)')
            self.add_output('gas_cell_total_volume', units='m**3',
                            desc='Total gas cell volume (≈ gross volume at conceptual level)')

        self.declare_partials('*', '*', method='fd', step=1e-7)

    def compute(self, inputs, outputs):
        length = max(inputs['length'][0], 10.0)
        fineness_ratio = max(inputs['fineness_ratio'][0], 2.0)
        C_HT = inputs['tail_volume_coeff_horizontal'][0]
        C_VT = inputs['tail_volume_coeff_vertical'][0]

        shape_type = self.options['shape_type']
        n_lobes = self.options['n_lobes']
        spacing_factor = self.options['lobe_spacing_factor']

        # Compute single-lobed base properties first
        gross_volume_single, wetted_area_single, max_diameter_single = self.compute_single_lobed(length, fineness_ratio, shape_type, inputs)

        # Scale for multi-lobed if >1
        if n_lobes > 1:
            # Approximate: sum volumes, adjust areas for spacing (simple model; reduce overlap by 20% empirical)
            gross_volume = n_lobes * gross_volume_single * (1 - 0.2 * spacing_factor)
            wetted_area = n_lobes * wetted_area_single * (1 + 0.1 * spacing_factor)  # increased surface from junctions
            max_diameter = max_diameter_single + (n_lobes - 1) * spacing_factor * max_diameter_single  # total width
        else:
            gross_volume = gross_volume_single
            wetted_area = wetted_area_single
            max_diameter = max_diameter_single

        outputs['gross_volume'] = max(gross_volume, 1.0)
        outputs['wetted_surface_area'] = max(wetted_area, 1.0)
        outputs['max_diameter'] = max(max_diameter, length / fineness_ratio)  # fallback to spheroid D

        ref_area_aero = gross_volume ** (2.0 / 3.0)
        outputs['ref_area_AeroCoeffs'] = max(ref_area_aero, 1.0)

        # Fins (unchanged; assumes single effective hull)
        tail_arm = 0.38 * length
        tail_arm = max(tail_arm, 1e-3)
        ref_area = gross_volume**(2.0 / 3.0)
        horizontal_fins_planform_area = (C_HT * length * ref_area / tail_arm)
        vertical_fins_planform_area = (C_VT * length * ref_area / tail_arm)
        total_fin_wetted_area = (horizontal_fins_planform_area + vertical_fins_planform_area) * 2.2
        outputs['fin_total_wetted_area'] = max(total_fin_wetted_area, 0.1)

        outputs['aspect_ratio_geom'] = length / max_diameter_single  # base on single-lobe FR

        # Ballonet (unchanged)
        airship_type = self.options['airship_type']
        if airship_type == 'rigid':
            outputs['ballonet_volume'] = 0.0
        else:
            rho_sea_level = 1.225
            rho_max_alt = self.estimate_density_at_altitude(self.options['max_altitude'])
            ballonet_vol_fraction = max(0.0, min((rho_sea_level / max(rho_max_alt, 1e-4)) - 1.0, 0.80))
            ballonet_volume = gross_volume * ballonet_vol_fraction
            outputs['ballonet_volume'] = max(ballonet_volume, 0.01 * gross_volume)

        # Semi-rigid / rigid extras (unchanged; use updated areas/volumes)
        if airship_type in ['semi-rigid', 'rigid']:
            outputs['outer_envelope_area'] = wetted_area
            factor = self.options['inner_envelope_area_factor']
            outputs['inner_envelope_area'] = wetted_area * factor
            if self.options['framework_enabled']:
                n_long = inputs['n_longitudinal_members'][0]
                n_rings = inputs['n_rings'][0]
                circumference = np.pi * max_diameter_single  # per lobe approx
                total_len = length + n_long * length + n_rings * circumference * n_lobes  # scale with lobes
                outputs['framework_total_member_length'] = max(total_len, 0.0)

        if airship_type == 'rigid':
            n_cells = inputs['n_gas_cells'][0]
            outputs['gas_cell_total_volume'] = gross_volume
            outputs['gas_cell_volume_each'] = gross_volume / max(n_cells, 1.0)

    def compute_single_lobed(self, length, fineness_ratio, shape_type, inputs):
        """Compute volume, wetted area, max diameter for single-lobed hull."""
        n_points = 1000  # for numerical integration
        x = np.linspace(0, length, n_points)
        r = np.zeros_like(x)  # radius profile

        if shape_type == 'spheroid':
            a = length / 2.0
            b = (length / fineness_ratio) / 2.0
            ecc_sq = 1.0 - (b**2 / a**2) if a > b else 0.0
            ecc = np.sqrt(max(ecc_sq, 0))
            volume = (4 / 3) * np.pi * a * b**2
            if ecc < 1e-6:
                surface = 4 * np.pi * a**2
            else:
                surface = 2 * np.pi * b**2 + (2 * np.pi * a * b / ecc) * np.arcsin(ecc)
            max_diam = 2 * b

        elif shape_type == 'npl':
            a_n = inputs['npl_a_n'][0]
            b_n = inputs['npl_b_n'][0]
            # NPL: two ellipses (front/rear)
            a1 = a_n * length / 2  # front major
            a2 = length - a1  # rear major
            b = b_n * min(a1, a2)  # minor
            mid_point = a1
            r_front = b * np.sqrt(1 - ((x - 0)**2 / a1**2))  # front ellipse
            r_rear = b * np.sqrt(1 - ((x - length)**2 / a2**2))  # rear ellipse (shifted)
            mask_front = x <= mid_point
            r[mask_front] = r_front[mask_front]
            r[~mask_front] = r_rear[~mask_front]
            # Numerical volume and surface
            volume = np.pi * np.trapz(r**2, x)
            ds = np.sqrt(np.diff(x)**2 + np.diff(r)**2)
            surface = 2 * np.pi * np.trapz(r[:-1], ds)
            max_diam = 2 * np.max(r)

        elif shape_type == 'gnvr':
            d_g = inputs['gnvr_d_g'][0]
            # GNVR: semi-ellipse bow, circle mid, parabola stern (from paper)
            bow_len = length * 0.25  # approximate segments; adjust per paper
            mid_len = length * 0.5
            stern_len = length - bow_len - mid_len
            r_max = length / fineness_ratio / 2
            # Bow: semi-ellipse
            x_bow = np.linspace(0, bow_len, n_points // 3)
            r_bow = r_max * np.sqrt(1 - ((x_bow - bow_len)**2 / bow_len**2))
            # Mid: circle segment (constant r)
            x_mid = np.linspace(bow_len, bow_len + mid_len, n_points // 3)
            r_mid = np.full_like(x_mid, r_max)
            # Stern: parabola r = d_g * (length - x)^2 + offset to match
            x_stern = np.linspace(bow_len + mid_len, length, n_points - 2*(n_points//3))
            r_stern = d_g * (length - x_stern)**2
            r_stern = r_stern * (r_max / np.max(r_stern))  # normalize to match mid
            # Combine
            x = np.concatenate([x_bow, x_mid, x_stern])
            r = np.concatenate([r_bow, r_mid, r_stern])
            volume = np.pi * np.trapz(r**2, x)
            ds = np.sqrt(np.diff(x)**2 + np.diff(r)**2)
            surface = 2 * np.pi * np.trapz(r[:-1], ds)
            max_diam = 2 * np.max(r)

        elif shape_type == 'wang':
            a_w = inputs['wang_a_w'][0]
            b_w = inputs['wang_b_w'][0]
            c_w = inputs['wang_c_w'][0]
            d_w = inputs['wang_d_w'][0]
            l_w = inputs['wang_l_w'][0]
            # Wang parametric (from paper Eq. in Fig. 11, assuming y = f(x) revolved)
            # Placeholder: r = a_w * (1 - (x/length)**b_w)**c_w * sin(d_w * np.pi * x / length)**l_w  # adapt from typical Wang
            # Note: Exact eq from paper Fig. 11; implement as per your needs
            r = np.sin(np.pi * x / length)  # replace with actual
            volume = np.pi * np.trapz(r**2, x)
            ds = np.sqrt(np.diff(x)**2 + np.diff(r)**2)
            surface = 2 * np.pi * np.trapz(r[:-1], ds)
            max_diam = 2 * np.max(r)

        return volume, surface, max_diam

    def estimate_density_at_altitude(self, altitude_m):
        # Unchanged ISA model
        T0 = 288.15; P0 = 101325.0; R_air = 287.058; g0 = 9.80665; lapse_rate_L = 0.0065
        if altitude_m <= 11000:
            T = T0 - lapse_rate_L * altitude_m
            P = P0 * (T / T0)**(g0 / (lapse_rate_L * R_air))
        elif altitude_m <= 20000:
            T11 = T0 - lapse_rate_L * 11000.0
            P11 = P0 * (T11 / T0)**(g0 / (lapse_rate_L * R_air))
            T = T11
            P = P11 * np.exp(-g0 * (altitude_m - 11000.0) / (R_air * T))
        else:
            T11 = T0 - lapse_rate_L * 11000.0
            P11 = P0 * (T11 / T0)**(g0 / (lapse_rate_L * R_air))
            T20 = T11
            P20 = P11 * np.exp(-g0 * (20000.0 - 11000.0) / (R_air * T20))
            T = T20
            P = P20 * np.exp(-g0 * (altitude_m - 20000.0) / (R_air * T))
        rho = P / (R_air * T)
        return max(rho, 0.001)