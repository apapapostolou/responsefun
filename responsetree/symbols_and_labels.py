from sympy import Symbol, Mul, Add, Pow, symbols, adjoint, latex, simplify, fraction
from sympy.physics.quantum.operator import Operator
from responsetree.response_operators import MTM, S2S_MTM, ResponseVector, DipoleOperator, TransitionFrequency


O, f = symbols(r"0, f", real=True)
gamma = symbols(r"\gamma", real=True)
n, m, p, k = symbols(r"n, m, p, k", real=True)
w, w_o, w_1, w_2, w_3 = symbols(r"w, w_{\sigma}, w_{1}, w_{2}, w_{3}", real=True)

w_f = TransitionFrequency("f", real=True)
w_n = TransitionFrequency("n", real=True)
w_m = TransitionFrequency("m", real=True)
w_p = TransitionFrequency("p", real=True)
w_k = TransitionFrequency("k", real=True)

op_a = DipoleOperator("A")
op_b = DipoleOperator("B")
op_c = DipoleOperator("C")
op_d = DipoleOperator("D")

F_A = MTM("A")
F_B = MTM("B")
F_C = MTM("C")
F_D = MTM("D")

B_A = S2S_MTM("A")
B_B = S2S_MTM("B")
B_C = S2S_MTM("C")
B_D = S2S_MTM("D")

X_A = ResponseVector("A")
X_B = ResponseVector("B")
X_C = ResponseVector("C")
X_D = ResponseVector("D")

M = Operator("M")
