import numpy as np
from .run import EBLT

def default_eblt_merit(I: EBLT):
    """
    merit function to operate on an evaluated LUME-Impact object I.

    Returns dict of scalar values
    """
    # Check for error
    if I.output.run.error:
        return {'error': True}
    else:
        m = {'error': False}

    # Gather stat output
    for k in dir(I.output.stats):
        if k == 'units':
            continue
        else:
            m['end_' + k] = getattr(I.output.stats, k)[-1]

    m['run_time'] = I.output.run.run_time

    P = I.output.particle_distributions[201].to_particlegroup()
    P_init = I.output.particle_distributions[101].to_particlegroup()

    # All impact particles read back have status==1
    #
    ntotal = len(P_init)
    nlost = ntotal - len(P)

    m['end_n_particle_loss'] = nlost

    # Get live only for stat calcs
    P = P.where(P.status == 1)

    # No live particles
    if len(P) == 0:
        return {'error': True}

    # Special
    m['end_total_charge'] = P['charge']
    m['end_higher_order_energy_spread'] = P['higher_order_energy_spread']


    # Remove annoying strings
    if 'why_error' in m:
        m.pop('why_error')

    return m