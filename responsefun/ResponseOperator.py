import sympy.physics.quantum.operator as qmoperator
from sympy import Symbol
from sympy.logic.boolalg import Boolean

from responsefun.AdccProperties import available_operators

for op_type, tup in available_operators.items():
    if tup[1] not in [0, 1, 2]:
        raise ValueError(
            f"An unknown symmetry was specified for the {op_type} operator. "
            "Only the following symmetries are allowed:\n"
            "0: no symmetry assumed, 1: hermitian, 2: anti-hermitian"
        )


class ResponseOperator(qmoperator.Operator):
    """Base class for (state-to-state) modified transition moments and response vectors."""

    def __new__(cls, comp, *args, **kwargs):
        """
        Parameters
        ----------
        comp: str
            Cartesian component.
        """
        obj = qmoperator.Operator.__new__(cls, comp, *args, **kwargs)
        if isinstance(comp, Symbol):
            obj._comp = str(comp)
        else:
            assert isinstance(comp, str)
            obj._comp = comp
        return obj

    @property
    def comp(self):
        return self._comp

    def _print_contents(self, printer):
        return "{}_{}".format(self.__class__.__name__, self._comp)


class MTM(ResponseOperator):
    def __new__(cls, comp, op_type):
        obj = ResponseOperator.__new__(cls, comp, op_type)
        if isinstance(op_type, Symbol):
            obj._op_type = str(op_type)
        else:
            assert isinstance(op_type, str)
            obj._op_type = op_type
        assert obj._op_type in available_operators
        obj._symmetry = available_operators[obj._op_type][1]
        obj._dim = available_operators[obj._op_type][2]
        if len(obj._comp) != obj._dim:
            raise ValueError(
                f"The operator is {obj._dim}-dimensional, but {len(obj._comp)} "
                "components were specified."
            )
        return obj

    @property
    def op_type(self):
        return self._op_type

    @property
    def symmetry(self):
        return self._symmetry

    @property
    def dim(self):
        return self._dim

    def _print_contents(self, printer):
        op = available_operators[self._op_type][0]
        return "F({})_{}".format(op, self._comp)

    def _print_contents_latex(self, printer):
        op = available_operators[self._op_type][0]
        if len(op) > 1:
            op = "\\" + op
        return "F({})_{{{}}}".format(op, self._comp)


class S2S_MTM(ResponseOperator):
    def __new__(cls, comp, op_type):
        obj = ResponseOperator.__new__(cls, comp, op_type)
        if isinstance(op_type, Symbol):
            obj._op_type = str(op_type)
        else:
            assert isinstance(op_type, str)
            obj._op_type = op_type
        assert obj._op_type in available_operators

        obj._symmetry = available_operators[obj._op_type][1]
        obj._dim = available_operators[obj._op_type][2]
        if len(obj._comp) != obj._dim:
            raise ValueError(
                f"The operator is {obj._dim}-dimensional, but {len(obj._comp)} "
                "components were specified."
            )
        return obj

    @property
    def op_type(self):
        return self._op_type

    @property
    def symmetry(self):
        return self._symmetry

    @property
    def dim(self):
        return self._dim

    def _print_contents(self, printer):
        op = available_operators[self._op_type][0]
        return "B({})_{}".format(op, self._comp)

    def _print_contents_latex(self, printer):
        op = available_operators[self._op_type][0]
        if len(op) > 1:
            op = "\\" + op
        return "B({})_{{{}}}".format(op, self._comp)


class ResponseVector(ResponseOperator):
    def __new__(cls, comp, no, mtm_type, symmetry):
        if mtm_type:
            assert mtm_type in ["MTM", "S2S_MTM"]
        if symmetry:
            assert symmetry in [0, 1, 2]
        obj = ResponseOperator.__new__(cls, comp, no, mtm_type, symmetry)
        obj._no = no
        obj._mtm_type = mtm_type
        obj._symmetry = symmetry
        return obj

    @property
    def no(self):
        return self._no

    @property
    def mtm_type(self):
        return self._mtm_type

    @property
    def symmetry(self):
        return self._symmetry

    def _print_contents(self, printer):
        return "X_({}, {})".format(self._comp, self._no)

    def _print_contents_latex(self, printer):
        return "X_{{{}, {}}}".format(self._comp, self._no)


class OneParticleOperator(ResponseOperator):
    def __new__(cls, comp, op_type, shifted, *args, **kwargs):
        obj = ResponseOperator.__new__(cls, comp, op_type, shifted, *args, **kwargs)
        if isinstance(op_type, Symbol):
            obj._op_type = str(op_type)
        else:
            assert isinstance(op_type, str)
            obj._op_type = op_type
        assert obj._op_type in available_operators

        obj._symmetry = available_operators[obj._op_type][1]
        obj._dim = available_operators[obj._op_type][2]
        if len(obj._comp) != obj._dim:
            raise ValueError(
                f"The operator is {obj._dim}-dimensional, but {len(obj._comp)} "
                "components were specified."
            )
        assert isinstance(shifted, bool) or isinstance(shifted, Boolean)
        obj._shifted = shifted
        return obj

    def copy_with_new_shifted(self, shifted):
        return OneParticleOperator(self.comp, self.op_type, shifted)

    @property
    def op_type(self):
        return self._op_type

    @property
    def symmetry(self):
        return self._symmetry

    @property
    def dim(self):
        return self._dim

    @property
    def shifted(self):
        return self._shifted

    def _print_contents(self, printer):
        op = available_operators[self._op_type][0]
        if self.shifted:
            return "{}_{}_bar".format(op, self._comp)
        else:
            return "{}_{}".format(op, self._comp)

    def _print_contents_latex(self, printer):
        op = available_operators[self._op_type][0]
        if len(op) > 1:
            op = "\\" + op
        if self.shifted:
            return "\\hat{{\\overline{{{}}}}}_{{{}}}".format(op, self._comp)
        else:
            return "\\hat{{{}}}_{{{}}}".format(op, self._comp)


class Moment(Symbol):
    def __new__(cls, comp, from_state, to_state, op_type, **assumptions):
        assert isinstance(comp, str)
        assert isinstance(from_state, Symbol)
        assert isinstance(to_state, Symbol)
        assert op_type in available_operators
        name = "{}_{}^{}".format(
            available_operators[op_type][0], comp, str(from_state) + str(to_state)
        )
        obj = Symbol.__new__(cls, name, **assumptions)
        obj._comp = comp
        obj._from_state = from_state
        obj._to_state = to_state
        obj._op_type = op_type
        obj._symmetry = available_operators[op_type][1]
        obj._dim = available_operators[op_type][2]
        if len(comp) != obj._dim:
            raise ValueError(
                f"The operator is {obj._dim}-dimensional, but {len(comp)} "
                "components were specified."
            )
        return obj

    @property
    def comp(self):
        return self._comp

    @property
    def from_state(self):
        return self._from_state

    @property
    def to_state(self):
        return self._to_state

    @property
    def op_type(self):
        return self._op_type

    @property
    def symmetry(self):
        return self._symmetry

    @property
    def dim(self):
        return self._dim


class TransitionFrequency(Symbol):
    def __new__(self, state, **assumptions):
        assert isinstance(state, Symbol)
        name = "w_{}".format(str(state))
        obj = Symbol.__new__(self, name, **assumptions)
        obj._state = state
        return obj

    @property
    def state(self):
        return self._state
