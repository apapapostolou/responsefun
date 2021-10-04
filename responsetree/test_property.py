import unittest
import adcc
import numpy as np
from scipy.constants import physical_constants


from responsetree.testdata.static_data import xyz
from responsetree.testdata import cache
from responsetree.misc import expand_test_templates, assert_allclose_signfix
from responsetree.symbols_and_labels import *
from responsetree.sum_over_states import TransitionMoment
from responsetree.evaluate_property import evaluate_property_isr, evaluate_property_sos, evaluate_property_sos_fast
from respondo.polarizability import static_polarizability, real_polarizability, complex_polarizability
from respondo.tpa import tpa_resonant
from respondo.rixs import rixs
from adcc.Excitation import Excitation


Hartree = physical_constants["hartree-electron volt relationship"][0]


def run_scf(molecule, basis, backend="pyscf"):
    scfres = adcc.backends.run_hf(
        backend, xyz=xyz[molecule],
        basis=basis,
    )
    return scfres


case_list = [(c, ) for c in cache.cases]
SOS_expressions = {
        "alpha": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, O) / (w_n - w)
            + TransitionMoment(O, op_b, n) * TransitionMoment(n, op_a, O) / (w_n + w)), None
        ),
        "alpha_complex": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, O) / (w_n - w - 1j*gamma)
            + TransitionMoment(O, op_b, n) * TransitionMoment(n, op_a, O) / (w_n + w + 1j*gamma)), None
        ),
        "rixs_short": (
            (TransitionMoment(f, op_a, n) * TransitionMoment(n, op_b, O) / (w_n - w - 1j*gamma)), None
        ),
        "rixs": (
            (TransitionMoment(f, op_a, n) * TransitionMoment(n, op_b, O) / (w_n - w - 1j*gamma)
            + TransitionMoment(f, op_b, n) * TransitionMoment(n, op_a, O) / (w_n + w - w_f + 1j*gamma)), None
        ),
        "tpa_resonant": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, f) / (w_n - (w_f/2))
            + TransitionMoment(O, op_b, n) * TransitionMoment(n, op_a, f) / (w_n - (w_f/2))), None
        ),
        "beta": (
            TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, k) * TransitionMoment(k, op_c, O) / ((w_n - w_o) * (w_k - w_2)),
            [(op_a, -w_o), (op_b, w_1), (op_c, w_2)]
        ),
        "beta_complex": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, k) * TransitionMoment(k, op_c, O)
            / ((w_n - w_o - 1j*gamma) * (w_k - w_2 - 1j*gamma))),
            [(op_a, -w_o-1j*gamma), (op_b, w_1+1j*gamma), (op_c, w_2+1j*gamma)]
        ),
        "gamma_extra_terms_1": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, O) * TransitionMoment(O, op_c, m) * TransitionMoment(m, op_d, O)
            / ((w_n - w_o) * (w_m - w_3) * (w_m + w_2))),
            [(op_a, -w_o), (op_b, w_1), (op_c, w_2), (op_d, w_3)]
        ),
        "gamma_extra_terms_2": (
            (TransitionMoment(O, op_a, n) * TransitionMoment(n, op_b, O) * TransitionMoment(O, op_c, m) * TransitionMoment(m, op_d, O)
            / ((w_n - w_o) * (-w_2 - w_3) * (w_m - w_3))),
            [(op_a, -w_o), (op_b, w_1), (op_c, w_2), (op_d, w_3)]
        )
        }


@expand_test_templates(case_list)
class TestIsrAgainstRespondo(unittest.TestCase):
    def template_static_polarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        alpha_ref = static_polarizability(refstate, method=method)
        
        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        alpha_expr = SOS_expressions["alpha"][0]
        alpha = evaluate_property_isr(state, alpha_expr, [n], (w, 0.0), symmetric=True)
        np.testing.assert_allclose(alpha, alpha_ref, atol=1e-7)

    def template_real_polarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        omega = 0.05
        alpha_ref = real_polarizability(refstate, method=method, omega=omega)

        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        alpha_expr = SOS_expressions["alpha_complex"][0]
        alpha = evaluate_property_isr(state, alpha_expr, [n], (w, omega), symmetric=True)
        np.testing.assert_allclose(alpha, alpha_ref, atol=1e-7)
        
    def template_complex_polarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        omega = 0.05
        gamma_val = 0.124/Hartree
        alpha_ref = complex_polarizability(refstate, method=method, omega=omega, gamma=gamma_val)

        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        alpha_expr = SOS_expressions["alpha_complex"][0]
        alpha = evaluate_property_isr(state, alpha_expr, [n], (w, omega), gamma_val, symmetric=True)
        np.testing.assert_allclose(alpha, alpha_ref, atol=1e-7)

    def template_rixs_short(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        omega = 0.05
        gamma_val = 0.124/Hartree
        rixs_expr = SOS_expressions["rixs_short"][0]

        for ee in state.excitations:
            final_state = ee.index
            excited_state = Excitation(state, final_state, method)

            rixs_ref = rixs(excited_state, omega, gamma_val)
            rixs_short = evaluate_property_isr(state, rixs_expr, [n], (w, omega), gamma_val, final_state=(f, final_state))
            np.testing.assert_allclose(rixs_short, rixs_ref[1], atol=1e-7, err_msg="final_state = {}".format(final_state))

    def template_rixs(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        omega = 0.05
        gamma_val = 0.124/Hartree
        rixs_expr = SOS_expressions["rixs"][0]

        for ee in state.excitations:
            final_state = ee.index
            excited_state = Excitation(state, final_state, method)

            rixs_ref = rixs(excited_state, omega, gamma_val, rotating_wave=False)
            rixs_tens = evaluate_property_isr(state, rixs_expr, [n], (w, omega), gamma_val, final_state=(f, final_state))
            np.testing.assert_allclose(rixs_tens, rixs_ref[1], atol=1e-7, err_msg="final_state = {}".format(final_state))

    def template_tpa_resonant(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        tpa_expr = SOS_expressions["tpa_resonant"][0]
        
        for ee in state.excitations:
            final_state = ee.index
            excited_state = Excitation(state, final_state, method)

            tpa_ref = tpa_resonant(excited_state)
            tpa = evaluate_property_isr(state, tpa_expr, [n], final_state=(f, final_state))
            np.testing.assert_allclose(tpa, tpa_ref[1], atol=1e-7, err_msg="final_state = {}".format(final_state))


@expand_test_templates(case_list)
class TestIsrAgainstSos(unittest.TestCase):
    def template_polarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        alpha_expr = SOS_expressions["alpha_complex"][0]
        gamma_val = 0.124/Hartree
        value_list = [((w, 0.0), 0.0), ((w, 0.05), 0.0), ((w, 0.03), gamma_val)] # static, real and complex polarizability
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for tup in value_list:
            alpha_sos = evaluate_property_sos(mock_state, alpha_expr, [n], tup[0], tup[1], symmetric=True)
            alpha_isr = evaluate_property_isr(state, alpha_expr, [n], tup[0], tup[1], symmetric=True)
            np.testing.assert_allclose(alpha_isr, alpha_sos, atol=1e-7, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))

        # mistakenly specify final state
        self.assertRaises(
                ValueError, evaluate_property_sos,
                mock_state, alpha_expr, [n], (w, 0.0), 0.0, final_state=(f, 2), symmetric=True
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, alpha_expr, [n], (w, 0.0), 0.0, final_state=(f, 2), symmetric=True
        )

    def template_rixs_short(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        rixs_expr = SOS_expressions["rixs_short"][0]
        gamma_val = 0.124/Hartree
        value_list = [((w, 0.0), 0.0), ((w, 0.05), 0.0), ((w, 1), 0), ((w, 0.03), gamma_val)]
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for tup in value_list:
            for ee in state.excitations:
                final_state = ee.index
                if tup[0][1] == 0.0 and tup[1] == 0.0:
                    self.assertRaises(
                            ZeroDivisionError,
                            evaluate_property_sos,
                            mock_state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state)
                    )
                    self.assertRaises(
                            ZeroDivisionError,
                            evaluate_property_isr,
                            state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state)
                    )
                else:
                    rixs_sos = evaluate_property_sos(mock_state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state))
                    rixs_isr = evaluate_property_isr(state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state))
                    assert_allclose_signfix(rixs_isr, rixs_sos, atol=1e-7, err_msg="w = {}, gamma = {}, final_state = {}".format(tup[0][1], tup[1], final_state))

    def template_rixs(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        rixs_expr = SOS_expressions["rixs"][0]
        omega = (w, 0.05)
        gamma_val = 0.124/Hartree
        final_state = 2
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)
        
        rixs_sos = evaluate_property_sos(mock_state, rixs_expr, [n], omega, gamma_val, final_state=(f, final_state))
        rixs_isr = evaluate_property_isr(state, rixs_expr, [n], omega, gamma_val, final_state=(f, final_state))
        assert_allclose_signfix(rixs_isr, rixs_sos, atol=1e-7)

    def template_tpa_resonant(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        tpa_expr = SOS_expressions["tpa_resonant"][0]
        final_state = 2
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        tpa_sos = evaluate_property_sos(mock_state, tpa_expr, [n], final_state=(f, final_state))
        tpa_isr = evaluate_property_isr(state, tpa_expr, [n], final_state=(f, final_state))

        assert_allclose_signfix(tpa_isr, tpa_sos, atol=1e-7)
        
        # specify frequency that is not included in the SOS expression
        self.assertRaises(
                ValueError, evaluate_property_sos,
                mock_state, tpa_expr, [n], (w, 0.05), final_state=(f, final_state)
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, tpa_expr, [n], (w, 0.05), final_state=(f, final_state)
        )

#    def template_first_hyperpolarizability(self, case):
#        molecule, basis, method = case.split("_")
#        scfres = run_scf(molecule, basis)
#        refstate = adcc.ReferenceState(scfres)
#        beta_expr = SOS_expressions["beta"][0]
#        perm_pairs = SOS_expressions["beta"][1]
#        omega_list = [
#                [(w_o, w_1+w_2), (w_1, 0.0), (w_2, 0.0)],
#                [(w_o, w_1+w_2), (w_1, 0.05), (w_2, 0.05)],
#                [(w_o, w_1+w_2), (w_1, -0.05), (w_2, 0.05)],
#                [(w_o, w_1+w_2), (w_1, 0.04), (w_2, 0.06)]
#        ]
#        mock_state = cache.data_fulldiag[case]
#        state = adcc.run_adc(refstate, method=method, n_singlets=5)
#
#        for omegas in omega_list:
#            beta_sos = evaluate_property_sos(mock_state, beta_expr, [n, k], omegas, perm_pairs=perm_pairs)
#            beta_isr = evaluate_property_isr(state, beta_expr, [n, k], omegas, perm_pairs=perm_pairs)
#            np.testing.assert_allclose(beta_isr, beta_sos, atol=1e-7)#, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))


@expand_test_templates(case_list)
class TestIsrAgainstSosFast(unittest.TestCase):
    def template_polarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        alpha_expr = SOS_expressions["alpha_complex"][0]
        gamma_val = 0.124/Hartree
        value_list = [((w, 0.0), 0.0), ((w, 0.05), 0.0), ((w, 0.03), gamma_val)] # static, real and complex polarizability
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for tup in value_list:
            alpha_sos = evaluate_property_sos_fast(mock_state, alpha_expr, [n], tup[0], tup[1])
            alpha_isr = evaluate_property_isr(state, alpha_expr, [n], tup[0], tup[1], symmetric=True)
            np.testing.assert_allclose(alpha_isr, alpha_sos, atol=1e-7, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))

        # mistakenly specify final state
        self.assertRaises(
                ValueError, evaluate_property_sos_fast,
                mock_state, alpha_expr, [n], (w, 0.0), 0.0, final_state=(f, 2)
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, alpha_expr, [n], (w, 0.0), 0.0, final_state=(f, 2), symmetric=True
        )

    def template_rixs_short(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        rixs_expr = SOS_expressions["rixs_short"][0]
        gamma_val = 0.124/Hartree
        value_list = [((w, 0.0), 0.0), ((w, 0.05), 0.0), ((w, 1), 0), ((w, 0.03), gamma_val)]
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for tup in value_list:
            for ee in state.excitations:
                final_state = ee.index
                if tup[0][1] == 0.0 and tup[1] == 0.0:
                    self.assertRaises(
                            ZeroDivisionError,
                            evaluate_property_sos_fast,
                            mock_state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state)
                    )
                    self.assertRaises(
                            ZeroDivisionError,
                            evaluate_property_isr,
                            state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state)
                    )
                else:
                    rixs_sos = evaluate_property_sos_fast(mock_state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state))
                    rixs_isr = evaluate_property_isr(state, rixs_expr, [n], tup[0], tup[1], final_state=(f, final_state))
                    assert_allclose_signfix(rixs_isr, rixs_sos, atol=1e-7, err_msg="w = {}, gamma = {}, final_state = {}".format(tup[0][1], tup[1], final_state))

    def template_rixs(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        rixs_expr = SOS_expressions["rixs"][0]
        omega = (w, 0.05)
        gamma_val = 0.124/Hartree
        final_state = 2
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        rixs_sos = evaluate_property_sos_fast(mock_state, rixs_expr, [n], omega, gamma_val, final_state=(f, final_state))
        rixs_isr = evaluate_property_isr(state, rixs_expr, [n], omega, gamma_val, final_state=(f, final_state))
        assert_allclose_signfix(rixs_isr, rixs_sos, atol=1e-7)

        # give two different values for the same frequency
        self.assertRaises(
                ValueError, evaluate_property_sos_fast,
                mock_state, rixs_expr, [n], [(w, 0.05), (w, 0.03)], gamma_val, final_state=(f, final_state)
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, rixs_expr, [n], [(w, 0.05), (w, 0.03)], gamma_val, final_state=(f, final_state)
        )

    def template_tpa_resonant(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        tpa_expr = SOS_expressions["tpa_resonant"][0]
        final_state = 2
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        tpa_sos = evaluate_property_sos_fast(mock_state, tpa_expr, [n], final_state=(f, final_state))
        tpa_isr = evaluate_property_isr(state, tpa_expr, [n], final_state=(f, final_state))

        assert_allclose_signfix(tpa_isr, tpa_sos, atol=1e-7)

        # specify frequency that is not included in the SOS expression
        self.assertRaises(
                ValueError, evaluate_property_sos_fast,
                mock_state, tpa_expr, [n], (w, 0.05), final_state=(f, final_state)
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, tpa_expr, [n], (w, 0.05), final_state=(f, final_state)
        )
    
    def template_first_hyperpolarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        beta_expr, perm_pairs = SOS_expressions["beta"]
        omega_list = [
                [(w_o, w_1+w_2), (w_1, 0.0), (w_2, 0.0)],
                [(w_o, w_1+w_2), (w_1, 0.05), (w_2, 0.05)],
                [(w_o, w_1+w_2), (w_1, -0.05), (w_2, 0.05)],
                [(w_o, w_1+w_2), (w_1, 0.04), (w_2, 0.06)]
        ]
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for omegas in omega_list:
            beta_sos = evaluate_property_sos_fast(mock_state, beta_expr, [n, k], omegas, perm_pairs=perm_pairs)
            beta_isr = evaluate_property_isr(state, beta_expr, [n, k], omegas, perm_pairs=perm_pairs)
            np.testing.assert_allclose(beta_isr, beta_sos, atol=1e-7)#, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))

        # give wrong indices of summation
        self.assertRaises(
                ValueError, evaluate_property_sos_fast,
                mock_state, beta_expr, [n, p], omega_list[0], perm_pairs=perm_pairs
        )
        self.assertRaises(
                ValueError, evaluate_property_isr,
                state, beta_expr, [n, p], omega_list[0], perm_pairs=perm_pairs
        )

    def template_complex_first_hyperpolarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        beta_expr, perm_pairs = SOS_expressions["beta_complex"]
        omega_list = [
                [(w_o, w_1+w_2), (w_1, 0.05), (w_2, 0.05)],
                [(w_o, w_1+w_2), (w_1, -0.05), (w_2, 0.05)],
                [(w_o, w_1+w_2), (w_1, 0.04), (w_2, 0.06)]
        ]
        gamma_val = 0.124/Hartree
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for omegas in omega_list:
            # extra terms of beta complex are not evaluated automatically
            beta_sos = evaluate_property_sos_fast(mock_state, beta_expr, [n, k], omegas, gamma_val, perm_pairs=perm_pairs, extra_terms=False)
            beta_isr = evaluate_property_isr(state, beta_expr, [n, k], omegas, gamma_val, perm_pairs=perm_pairs, extra_terms=False)
            np.testing.assert_allclose(beta_isr, beta_sos, atol=1e-7)#, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))

    def template_extra_terms_second_hyperpolarizability(self, case):
        molecule, basis, method = case.split("_")
        scfres = run_scf(molecule, basis)
        refstate = adcc.ReferenceState(scfres)
        gamma_expr, perm_pairs = SOS_expressions["gamma_extra_terms_2"]
        omega_list = [
                [(w_o, w_1+w_2+w_3), (w_1, 0.0), (w_2, 0.0), (w_3, 0.0)],
                [(w_o, w_1+w_2+w_3), (w_1, 0.0), (w_2, 0.0), (w_3, 0.05)],
                [(w_o, w_1+w_2+w_3), (w_1, 0.04), (w_2, 0.05), (w_3, 0.06)]
        ]
        mock_state = cache.data_fulldiag[case]
        state = adcc.run_adc(refstate, method=method, n_singlets=5)

        for omegas in omega_list:
            if omegas[1][1] == 0.0 and omegas[2][1] == 0.0:
                self.assertRaises(
                        ZeroDivisionError,
                        evaluate_property_sos_fast,
                        mock_state, gamma_expr, [n, m], omegas, perm_pairs=perm_pairs, extra_terms=False
                )
                self.assertRaises(
                        ZeroDivisionError,
                        evaluate_property_isr,
                        state, gamma_expr, [n, m], omegas, perm_pairs=perm_pairs, extra_terms=False
                )
            else:
                gamma_sos = evaluate_property_sos_fast(mock_state, gamma_expr, [n, m], omegas, perm_pairs=perm_pairs, extra_terms=False)
                gamma_isr = evaluate_property_isr(state, gamma_expr, [n, m], omegas, perm_pairs=perm_pairs, extra_terms=False)
                np.testing.assert_allclose(gamma_isr, gamma_sos, atol=1e-7)#, err_msg="w = {}, gamma = {}".format(tup[0][1], tup[1]))
