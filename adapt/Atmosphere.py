# -*- coding: utf-8 -*-
"""
Created on Mon Apr 7 15:32:14 2025

@author: Musavir Bashir
"""

import numpy as np
import openmdao.api as om
try:
    # Package mode
    from .operatingConditions import opCond
except ImportError:
    # Standalone/script mode
    from operatingConditions import opCond

class Atmosphere(om.ExplicitComponent):
    def initialize(self):
        self.options.declare('phd', types=opCond)
        self.options.declare('num_steps', default=1, types=int)

    def setup(self):
        num_steps = self.options['num_steps']
        self.add_input('altitude', val=np.full(num_steps, 0.0), units='m')
        self.add_input('disa', val=np.zeros(num_steps), units='K')
        self.add_output('pamb', val=np.zeros(num_steps), units='Pa')
        self.add_output('tamb', val=np.zeros(num_steps), units='K')
        self.add_output('rho', val=np.zeros(num_steps), units='kg/m**3')
        self.declare_partials('*', '*', method='fd')

    def compute(self, inputs, outputs):
        phd = self.options['phd']
        altitude = np.maximum(inputs['altitude'], 0.0)
        disa = inputs['disa']

        for i in range(self.options['num_steps']):
            pamb, tamb, _ = phd.atmosphere(altitude[i], disa[i])
            outputs['pamb'][i] = pamb
            outputs['tamb'][i] = tamb
            outputs['rho'][i] = max(phd.gas_density(pamb, tamb), 1e-6)