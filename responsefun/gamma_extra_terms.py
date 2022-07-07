import numpy as np
from itertools import permutations, product
import adcc
from pyscf import gto, scf
from adcc.workflow import construct_adcmatrix
from adcc.adc_pp import modified_transition_moments
from respondo.misc import select_property_method
from respondo.solve_response import solve_response


def sos_antonia(state, omega_1, omega_2, omega_3):
    omega_o = omega_1 + omega_2 + omega_3
    sos = np.zeros((3, 3, 3, 3))
    components = list(product([0, 1, 2], repeat=4))
    for n, dip_n in enumerate(state.transition_dipole_moment):
        for m, dip_m in enumerate(state.transition_dipole_moment):
            for c in components:
                A, B, C, D = c
                perms = list(permutations([(A, -omega_o), (B, omega_1), (C, omega_2), (D, omega_3)]))
                for p in perms:
                    sos[c] += dip_n[p[0][0]]*dip_n[p[1][0]]*dip_m[p[2][0]]*dip_m[p[3][0]] / ( 
                            (state.excitation_energy_uncorrected[n] + p[0][1])
                            *(p[2][1] + p[3][1])
                            *(state.excitation_energy_uncorrected[m] - p[3][1])
                    )
    return sos


def sos_panor(state, omega_1, omega_2, omega_3):
    omega_o = omega_1 + omega_2 + omega_3
    sos = np.zeros((3, 3, 3, 3))
    components = list(product([0, 1, 2], repeat=4))
    for n, dip_n in enumerate(state.transition_dipole_moment):
        for m, dip_m in enumerate(state.transition_dipole_moment):
            for c in components:
                A, B, C, D = c
                perms = list(permutations([(A, -omega_o), (B, omega_1), (C, omega_2), (D, omega_3)]))
                for p in perms:
                    sos[c] += dip_n[p[0][0]]*dip_n[p[1][0]]*dip_m[p[2][0]]*dip_m[p[3][0]] / (
                            (state.excitation_energy_uncorrected[n] + p[0][1])
                            *(state.excitation_energy_uncorrected[m] - p[3][1])
                            *(state.excitation_energy_uncorrected[m] + p[2][1])
                    )
    return sos


def sos_panor_single(state, omega_1, omega_2, omega_3):
    omega_o = omega_1 + omega_2 + omega_3
    tf = state.excitation_energy_uncorrected
    sos = np.zeros((3, 3, 3, 3))
    components = list(product([0, 1, 2], repeat=4))
    for n, dip_n in enumerate(state.transition_dipole_moment):
        for m, dip_m in enumerate(state.transition_dipole_moment):
            for c in components:
                A, B, C, D = c
                sos[c] += dip_n[A]*dip_n[B]*dip_m[C]*dip_m[D] / (
                        (tf[n]-omega_o) * (tf[m]-omega_3) * (tf[m]+omega_2)
                )
    return sos


def isr_panor_single(state, omega_1, omega_2, omega_3):
    omega_o = omega_1 + omega_2 + omega_3
    matrix = construct_adcmatrix(state.matrix)
    property_method = select_property_method(matrix)
    mp = matrix.ground_state
    dips = state.reference_state.operators.electric_dipole
    mtms = modified_transition_moments(property_method, mp, dips)
    response1 = [solve_response(matrix, mtm, omega_o, gamma=0.0) for mtm in mtms]
    response2 = [solve_response(matrix, mtm, omega_3, gamma=0.0) for mtm in mtms]
    response3 = [solve_response(matrix, mtm, -omega_2, gamma=0.0) for mtm in mtms]
    isr = np.zeros((3, 3, 3, 3))
    components = list(product([0, 1, 2], repeat=4))
    for c in components:
        A, B, C, D = c
        isr[c] = (response1[A] @ mtms[B]) * (response2[C] @ response3[D])
    return isr


mol = gto.M(
    atom="""
    O 0 0 0
    H 0 0 1.795239827225189
    H 1.693194615993441 0 -0.599043184453037
    """,
    unit="Bohr",
    basis="sto-3g",
)

scfres = scf.RHF(mol)
scfres.conv_tol = 1e-8
scfres.conv_tol_grad = 1e-8
scfres.kernel()

refstate = adcc.ReferenceState(scfres)
matrix = adcc.AdcMatrix("adc2", refstate)
state = adcc.adc2(scfres, n_singlets=65)
#print(state.describe())

#panor_terms = sos_panor(state, 0.5, 0.4, 0.3)
#antonia_terms = sos_antonia(state, 0.5, 0.4, 0.3)
#print(panor_terms)
#print(antonia_terms)
#np.testing.assert_allclose(panor_terms, antonia_terms, atol=1e-7)
sos = sos_panor_single(state, 0.0, 0.0, 0.0)
isr = isr_panor_single(state, 0.0, 0.0, 0.0)
print(sos)
print(isr)
np.testing.assert_allclose(sos, isr, atol=1e-7)