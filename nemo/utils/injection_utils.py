import inspect
from typing import Any, Callable, Dict, Set, TypeVar

T = TypeVar("T")


def run_injected(fn: Callable[..., T], *args, **kwargs) -> T:
    """
    Args:
        fn: (Callable) function that kwargs should be bound to
        **kwargs: named args that can be injected into fn args
    Returns:
        result of calling fn with the safely injected args and kwargs

    Example:
        def foo(x,y=1, *, z=None):
            return (x,y,z)
        # the extra kwargs are dropped
        assert foo(5, z=6, b=5, a=2, u=5) == (5,1,6)

    """
    signature: inspect.Signature = inspect.signature(fn)
    fn_arg_names: Set[str] = set(signature.parameters.keys())
    out_kwargs: Dict[str, Any] = {k: v for (k, v) in kwargs.items() if k in fn_arg_names}
    bound_args: inspect.BoundArguments = signature.bind(*args, **out_kwargs)
    bound_args.apply_defaults()
    return fn(*bound_args.args, **bound_args.kwargs)
