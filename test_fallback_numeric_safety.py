import pytest
from types import SimpleNamespace

from kasp.core.fallback import SolverChain, FallbackTracker


def test_k_based_fallback_guards_zero_and_negative_inlet_pressure():
    """_k_based_fallback must not raise ZeroDivisionError when state_in.P <= 0."""
    chain = SolverChain(FallbackTracker())
    state_in = SimpleNamespace(P=0.0, T=300.0, k=1.4, k_s=1.4)
    # Should safely compute without ZeroDivisionError
    t_out = chain._k_based_fallback(state_in, p_out=100000.0)
    assert t_out >= 300.0


def test_k_based_fallback_guards_zero_and_negative_outlet_pressure():
    """_k_based_fallback must handle p_out <= 0 gracefully without complex numbers or crashes."""
    chain = SolverChain(FallbackTracker())
    state_in = SimpleNamespace(P=100000.0, T=300.0, k=1.4, k_s=1.4)
    t_out = chain._k_based_fallback(state_in, p_out=0.0)
    assert isinstance(t_out, float)
    assert t_out >= 300.0


def test_k_based_fallback_guards_invalid_k():
    """_k_based_fallback must default to a valid physical exponent when k <= 1.0."""
    chain = SolverChain(FallbackTracker())
    state_in = SimpleNamespace(P=100000.0, T=300.0, k=0.5, k_s=0.0)
    t_out = chain._k_based_fallback(state_in, p_out=200000.0)
    assert isinstance(t_out, float)
    assert t_out > 300.0
