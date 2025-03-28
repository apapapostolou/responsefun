#  Copyright (C) 2023 by the responsefun authors
#
#  This file is part of responsefun.
#
#  responsefun is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  responsefun is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with responsefun. If not, see <http:www.gnu.org/licenses/>.
#

import warnings
from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Any, Union

import adcc
import numpy as np
from adcc.adc_pp.modified_transition_moments import modified_transition_moments
from adcc.adc_pp.state2state_transition_dm import state2state_transition_dm
from adcc.adc_pp.transition_dm import transition_dm
from adcc.IsrMatrix import IsrMatrix
from adcc.OneParticleOperator import product_trace
from cached_property import cached_property
from respondo.cpp_algebra import ResponseVector as RV
from respondo.solve_response import (
    transition_polarizability,
    transition_polarizability_complex,
)
from tqdm import tqdm

from responsefun.testdata.mock import MockExcitedStates


class Symmetry(Enum):
    NOSYMMETRY = 0
    HERMITIAN = 1
    ANTIHERMITIAN = 2


@dataclass(frozen=True)
class Operator:
    name: str
    symbol: str  # used for printing
    symmetry: Symmetry  # 0: no symmetry, 1: hermitian, 2: anti-hermitian
    dim: int  # dimensionality
    is_imag: bool


available_operators = [
    Operator(
        name="electric_dipole",
        symbol="mu",
        symmetry=Symmetry.HERMITIAN,
        dim=1,
        is_imag=False,
    ),
    Operator(
        name="magnetic_dipole",
        symbol="m",
        symmetry=Symmetry.ANTIHERMITIAN,
        dim=1,
        is_imag=True,
    ),
    Operator(
        name="diamagnetic_magnetizability",
        symbol="xi",
        symmetry=Symmetry.HERMITIAN,
        dim=2,
        is_imag=False,
    ),
]


def get_operator_by_name(name: str) -> Operator:
    for operator in available_operators:
        if operator.name == name:
            return operator
    raise NotImplementedError("The requested operator is not implemented.")


def compute_transition_moments(state, integrals):
    if state.property_method.level == 0:
        warnings.warn("ADC(0) transition moments are known to be faulty in some cases.")

    op_shape = np.shape(integrals)
    iterables = [list(range(shape)) for shape in op_shape]
    components = list(product(*iterables))
    moments = np.zeros((state.size, *op_shape))
    for i, ee in enumerate(state.excitations):
        tdm = transition_dm(state.property_method, state.ground_state, ee.excitation_vector)
        tms = np.zeros(op_shape)
        for c in components:
            # list indices must be integers (1-D operators)
            c = c[0] if len(c) == 1 else c
            tms[c] = product_trace(integrals[c], tdm)
        moments[i] = tms
    return np.squeeze(moments)


def compute_state_to_state_transition_moments(state, integrals, initial_state=None,
                                              final_state=None):
    istates = state.size
    excitations1 = state.excitations
    if initial_state is not None:
        istates = 1
        excitations1 = [state.excitations[initial_state]]
    fstates = state.size
    excitations2 = state.excitations
    if final_state is not None:
        fstates = 1
        excitations2 = [state.excitations[final_state]]

    op_shape = np.shape(integrals)
    iterables = [list(range(shape)) for shape in op_shape]
    components = list(product(*iterables))
    s2s_tm = np.zeros((istates, fstates, *op_shape))
    for i, ee1 in enumerate(tqdm(excitations1)):
        for j, ee2 in enumerate(excitations2):
            tdm = state2state_transition_dm(
                state.property_method,
                state.ground_state,
                ee1.excitation_vector,
                ee2.excitation_vector,
                state.matrix.intermediates,
            )
            tms = np.zeros(op_shape)
            for c in components:
                # list indices must be integers (1-D operators)
                c = c[0] if len(c) == 1 else c
                tms[c] = product_trace(tdm, integrals[c])
            s2s_tm[i, j] = tms
    return np.squeeze(s2s_tm)


class AdccProperties(ABC):
    """Abstract base class encompassing all properties that can be obtained
    from adcc for a given operator."""

    def __init__(self, state: Union[adcc.ExcitedStates, MockExcitedStates],
                 gauge_origin: Union[str, tuple[float, float, float], None] = None):
        self._state = state
        self._state_size = len(state.excitation_energy_uncorrected)
        self._property_method = self._state.property_method
        if isinstance(self._state, MockExcitedStates):
            self._pm_level = self._state.property_method.replace("adc", "")
        else:
            self._pm_level = self._state.property_method.level

        self._gauge_origin = gauge_origin

        # to make things faster if not all state-to-state transition moments are needed
        # but only from or to a specific state
        self._s2s_tm_i = np.empty((self._state_size), dtype=object)
        self._s2s_tm_f = np.empty((self._state_size), dtype=object)

    @abstractproperty
    def _operator(self) -> Operator:
        pass

    @property
    def op_symmetry(self) -> Symmetry:
        return self._operator.symmetry

    @property
    def op_dim(self) -> int:
        return self._operator.dim

    @abstractproperty
    def integrals(self) -> list[adcc.OneParticleOperator]:
        pass

    @abstractproperty
    def gs_moment(self) -> np.ndarray:
        pass

    def revert_transition_moment(self, moment: Any) -> Any:
        if self.op_symmetry == Symmetry.HERMITIAN:
            return moment
        elif self.op_symmetry == Symmetry.ANTIHERMITIAN:
            return -1.0 * moment
        else:
            raise NotImplementedError(
                "Only Hermitian and anti-Hermitian operators are implemented."
            )

    @cached_property
    def transition_moment(self) -> np.ndarray:
        return self._transition_moment()

    @property
    def transition_moment_reverse(self) -> np.ndarray:
        return self.revert_transition_moment(self.transition_moment)

    @cached_property
    def state_to_state_transition_moment(self) -> np.ndarray:
        return self._state_to_state_transition_moment()
    
    def s2s_tm_view(self, initial_state=None, final_state=None):
        if initial_state is None and final_state is None:
            return self.state_to_state_transition_moment[:]
        elif initial_state is None:
            if isinstance(self._state, MockExcitedStates):
                return self.state_to_state_transition_moment[:, final_state]
            if self._s2s_tm_f[final_state] is None:
                self._s2s_tm_f[final_state] = compute_state_to_state_transition_moments(
                    self._state, self.integrals, final_state=final_state
                )
            return self._s2s_tm_f[final_state]
        elif final_state is None:
            if isinstance(self._state, MockExcitedStates):
                return self.state_to_state_transition_moment[initial_state, :]
            if self._s2s_tm_i[initial_state] is None:
                self._s2s_tm_i[initial_state] = compute_state_to_state_transition_moments(
                    self._state, self.integrals, initial_state=initial_state
                )
            return self._s2s_tm_i[initial_state]
        else:
            if isinstance(self._state, MockExcitedStates):
                return self.state_to_state_transition_moment[initial_state, final_state]
            s2s_tm = compute_state_to_state_transition_moments(
                self._state, self.integrals, initial_state, final_state
            )
            return s2s_tm

    @abstractmethod
    def _transition_moment(self) -> np.ndarray:
        pass

    @abstractmethod
    def _state_to_state_transition_moment(self) -> np.ndarray:
        pass

    def modified_transition_moments(
        self, comp: Union[int, None] = None
    ) -> Union[adcc.AmplitudeVector, list[adcc.AmplitudeVector]]:
        if comp is None:
            op = self.integrals
        else:
            op = self.integrals[comp]
        mtms = modified_transition_moments(
            self._property_method, self._state.ground_state, op
        )
        return mtms

    def modified_transition_moments_reverse(
        self, comp: Union[int, None] = None
    ) -> Union[adcc.AmplitudeVector, list[adcc.AmplitudeVector]]:
        return self.revert_transition_moment(self.modified_transition_moments(comp))

    def isr_matrix(self, comp: Union[int, None] = None) -> adcc.IsrMatrix:
        if comp is None:
            op = self.integrals
        else:
            op = np.array(self.integrals)[comp]
        return IsrMatrix(self._property_method, self._state.ground_state, op)

    def transition_polarizability(
        self,
        to_vec: Union[adcc.AmplitudeVector, RV],
        from_vec: Union[adcc.AmplitudeVector, RV],
        comp: Union[int, None] = None
        ) -> np.ndarray:
        if comp is None:
            op = self.integrals
        else:
            op = np.array(self.integrals)[comp]
        # note that initial and final states are defined differently
        # in the respondo functions than here
        if isinstance(to_vec, adcc.AmplitudeVector) \
            and isinstance(from_vec, adcc.AmplitudeVector):
            ret = transition_polarizability(
                self._property_method, self._state.ground_state,
                from_vec, op, to_vec
            )
        else:
            if isinstance(to_vec, adcc.AmplitudeVector):
                to_vec = RV(to_vec)
            if isinstance(from_vec, adcc.AmplitudeVector):
                from_vec = RV(from_vec)
            ret = transition_polarizability_complex(
                self._property_method, self._state.ground_state,
                from_vec, op, to_vec
            )
        return ret


def build_adcc_properties(
    state: Union[adcc.ExcitedStates, MockExcitedStates],
    op_type: str,
    gauge_origin: Union[str, tuple[float, float, float], None] = None
) -> AdccProperties:
    if op_type == "electric_dipole":
        return ElectricDipole(state, gauge_origin)
    elif op_type == "magnetic_dipole":
        return MagneticDipole(state, gauge_origin)
    else:
        raise NotImplementedError


class ElectricDipole(AdccProperties):
    @property
    def _operator(self) -> Operator:
        return get_operator_by_name("electric_dipole")

    @property
    def integrals(self) -> list[adcc.OneParticleOperator]:
        return self._state.reference_state.operators.electric_dipole

    @property
    def gs_moment(self) -> np.ndarray:
        if isinstance(self._state, MockExcitedStates):
            return self._state.ground_state.dipole_moment[self._pm_level]
        else:
            return self._state.ground_state.dipole_moment(self._pm_level)

    def _transition_moment(self) -> np.ndarray:
        return self._state.transition_dipole_moment

    def _state_to_state_transition_moment(self) -> np.ndarray:
        if isinstance(self._state, MockExcitedStates):
            return self._state.transition_dipole_moment_s2s
        else:
            return compute_state_to_state_transition_moments(self._state, self.integrals)


class MagneticDipole(AdccProperties):
    @property
    def _operator(self) -> Operator:
        return get_operator_by_name("magnetic_dipole")

    @property
    def integrals(self) -> list[adcc.OneParticleOperator]:
        return self._state.reference_state.operators.magnetic_dipole

    @property
    def gs_moment(self) -> np.ndarray:
        # the minus sign is needed, because the negative charge is not yet included
        # in the operator definitions
        # TODO: remove minus after adc-connect/adcc#190 is merged
        ref_dipmom = -1.0 * np.array(
            [product_trace(dip, self._state.ground_state.reference_state.density)
             for dip in self.integrals]
        )
        if self._pm_level in [0, 1]:
            return ref_dipmom
        elif self._pm_level == 2:
            mp2corr = -1.0 * np.array([product_trace(dip, self._state.ground_state.mp2_diffdm)
                                       for dip in self.integrals])
            return ref_dipmom + mp2corr
        else:
            raise NotImplementedError(
                "Only magnetic dipole moments for level 1 and 2 are implemented."
            )

    def _transition_moment(self) -> np.ndarray:
        return self._state.transition_magnetic_dipole_moment

    def _state_to_state_transition_moment(self) -> np.ndarray:
        if isinstance(self._state, MockExcitedStates):
            return self._state.transition_magnetic_moment_s2s
        else:
            return compute_state_to_state_transition_moments(self._state, self.integrals)