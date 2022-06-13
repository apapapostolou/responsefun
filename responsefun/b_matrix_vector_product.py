import numpy as np
from itertools import product

from pyscf import gto, scf

import adcc
from adcc import AdcMethod
from adcc import LazyMp
from adcc import block as b
from adcc.functions import einsum
from adcc.AmplitudeVector import AmplitudeVector
from adcc.adc_pp import modified_transition_moments


def b_matrix_vector_product(method, ground_state, dips, vecs):
    if not isinstance(method, AdcMethod):
        method = AdcMethod(method)
    if method.name != "adc2":
        raise NotImplementedError(f"b_matrix_vector_product is not implemented for {method.name}.")
    if not isinstance(ground_state, LazyMp):
        raise TypeError("ground_state should be a LazyMp object.")
    if not isinstance(dips, list):
        dips = [dips]
    if not isinstance(vecs, np.ndarray):
        vecs = np.array(vecs)

    p0 = ground_state.mp2_diffdm
    t2 = ground_state.t2(b.oovv)
    
    comp_list_dips = list(range(len(dips)))
    comp_list_vecs = [list(range(shape)) for shape in vecs.shape]
    comp = list(product(comp_list_dips, *comp_list_vecs))
    
    ret_shape = (len(dips), *vecs.shape)
    ret = np.empty(ret_shape, dtype=object)

    for c in comp:
        dip = dips[c[0]]
        vec = vecs[c[1:]]
        ph = (
            + 1.0 * einsum('ac,ic->ia', dip.vv, vec.ph)
            - 1.0 * einsum('ik,ka->ia', dip.oo, vec.ph)
        )
        ph += (
            - 1.0 * einsum('ic,ja,jc->ia', vec.ph, p0.ov, dip.ov)
            - 1.0 * einsum('ic,jc,ja->ia', vec.ph, p0.ov, dip.ov)
            - 1.0 * einsum('ka,ib,kb->ia', vec.ph, p0.ov, dip.ov)
            - 1.0 * einsum('ka,kb,ib->ia', vec.ph, p0.ov, dip.ov)
            # 
            - 0.25 * einsum('ic,mnef,mnaf,ec->ia', vec.ph, t2, t2, dip.vv)
            - 0.25 * einsum('ic,mnef,mncf,ea->ia', vec.ph, t2, t2, dip.vv)
            - 0.5 * einsum('ic,mnce,mnaf,ef->ia', vec.ph, t2, t2, dip.vv)
            + 1.0 * einsum('ic,mncf,jnaf,jm->ia', vec.ph, t2, t2, dip.oo)
            # 
            + 0.25 * einsum('ka,mnef,inef,km->ia', vec.ph, t2, t2, dip.oo)
            + 0.25 * einsum('ka,mnef,knef,im->ia', vec.ph, t2, t2, dip.oo)
            # 
            - 1.0 * einsum('ka,knef,indf,ed->ia', vec.ph, t2, t2, dip.vv)
            + 0.5 * einsum('ka,knef,imef,mn->ia', vec.ph, t2, t2, dip.oo)
            # 
            + 0.5 * einsum('kc,knef,inaf,ec->ia', vec.ph, t2, t2, dip.vv)
            - 0.5 * einsum('kc,mncf,inaf,km->ia', vec.ph, t2, t2, dip.oo)
            + 0.5 * einsum('kc,inef,kncf,ea->ia', vec.ph, t2, t2, dip.vv)
            - 0.5 * einsum('kc,mnaf,kncf,im->ia', vec.ph, t2, t2, dip.oo)
            # 
            - 1.0 * einsum('kc,kncf,imaf,mn->ia', vec.ph, t2, t2, dip.oo)
            + 1.0 * einsum('kc,knce,inaf,ef->ia', vec.ph, t2, t2, dip.vv)
            # 
            - 2.0 * einsum('ilad,ld->ia', vec.pphh, dip.ov)
            + 2.0 * einsum('ilad,lndf,nf->ia', vec.pphh, t2, dip.ov)
            - 1.0 * einsum('klad,kled,ie->ia', vec.pphh, t2, dip.ov)
            - 1.0 * einsum('ilcd,nlcd,na->ia', vec.pphh, t2, dip.ov)
        )
        pphh = 0.5 * (
            + (
                - 1.0 * einsum('kc,ld->klcd', vec.ph, dip.ov)
                + 1.0 * einsum('kc,lndf,nf->klcd', vec.ph, t2, dip.ov)
                + 1.0 * einsum('lc,kd->klcd', vec.ph, dip.ov)
                - 1.0 * einsum('lc,kndf,nf->klcd', vec.ph, t2, dip.ov)
                + 1.0 * einsum('kd,lc->klcd', vec.ph, dip.ov)
                - 1.0 * einsum('kd,lncf,nf->klcd', vec.ph, t2, dip.ov)
                - 1.0 * einsum('ld,kc->klcd', vec.ph, dip.ov)
                + 1.0 * einsum('ld,kncf,nf->klcd', vec.ph, t2, dip.ov)
            ).antisymmetrise(0, 1).antisymmetrise(2, 3)
            + (
                - 1.0 * einsum('ic,kled,ie->klcd', vec.ph, t2, dip.ov)
                + 1.0 * einsum('id,klec,ie->klcd', vec.ph, t2, dip.ov)
            ).antisymmetrise(2, 3)
            + (
                - 1.0 * einsum('ka,nlcd,na->klcd', vec.ph, t2, dip.ov)
                + 1.0 * einsum('la,nkcd,na->klcd', vec.ph, t2, dip.ov)
            ).antisymmetrise(0, 1)
        )
        pphh += 1.0 * (
            + 1.0 * einsum('ac,ijcb->ijab', dip.vv, vec.pphh)
            - 1.0 * einsum('bc,ijca->ijab', dip.vv, vec.pphh)
        ).antisymmetrise(2, 3)
        pphh += 1.0 * (
            - 1.0 * einsum('ki,kjab->ijab', dip.oo, vec.pphh)
            + 1.0 * einsum('kj,kiab->ijab', dip.oo, vec.pphh)
        ).antisymmetrise(0, 1)
        ret[c] = AmplitudeVector(ph=ph, pphh=pphh)
    return ret


if __name__ == "__main__":
    from adcc.OneParticleOperator import product_trace
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
    scfres.kernel()
    refstate = adcc.ReferenceState(scfres)

    state = adcc.adc2(scfres, n_singlets=10)
    mp = state.ground_state
    dips = state.reference_state.operators.electric_dipole
    mtms = modified_transition_moments("adc2", mp, dips)

    product_vecs = b_matrix_vector_product("adc2", mp, dips, state.excitation_vector)

    for excitation in state.excitations:
        dipmom = [
            excitation.excitation_vector @ pr
            for pr in product_vecs[:, excitation.index]
        ]
        diffdm = excitation.state_diffdm
        dipmom_ref = [
            product_trace(diffdm, dip) for dip in dips
        ]
        np.testing.assert_allclose(
            dipmom, dipmom_ref, atol=1e-12
        )