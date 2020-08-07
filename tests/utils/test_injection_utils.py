from nemo.utils.injection_utils import run_injected


def test_inspect_inject_args():
    def foo(x, y=1, *, z=None):
        return (x, y, z)

    assert run_injected(foo, 5, a=4, b=5, z=6) == (5, 1, 6)
    assert run_injected(foo, 5) == (5, 1, None)
    assert run_injected(foo, 5, u=None) == (5, 1, None)
