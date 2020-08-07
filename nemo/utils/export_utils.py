from typing import Callable, Dict, Optional, Type

import torch
import torch.nn as nn

from nemo.utils import logging


def expand_Conv1D(conv1d: nn.Module) -> Optional[nn.Conv2d]:
    """
    Expands a Conv1D into a Conv2D. This is required for many (closed source) commercial tools with poor support for 1D Convolutions in Onnx.
    Args:
        conv1d: the Conv1D pytorch module to expand
    Returns:
        conv2d: Conv2D module with identical weights and params
    """
    if not isinstance(conv1d, nn.Conv1d):
        return None
    conv2d = nn.Conv2d(
        conv1d.in_channels,
        conv1d.out_channels,
        kernel_size=(conv1d.kernel_size[0], 1),
        stride=(conv1d.stride[0], 1),
        padding=(conv1d.padding[0], 0),
        dilation=(conv1d.dilation[0], 1),
        groups=conv1d.groups,
        padding_mode=conv1d.padding_mode,
    )
    conv2d.bias = conv1d.bias
    conv2d.weight = nn.Parameter(conv1d.weight.unsqueeze(-1))
    # check that expansion is valid
    for _ in range(2):
        sample_input = torch.rand(1, conv1d.in_channels, 256)
        close = conv1d(sample_input).mean() - conv2d(sample_input.unsqueeze(-1)).squeeze().mean()
        if close.abs() > 1e-6:
            raise ValueError("Unable to expand Conv1D to Conv2D")
    return conv2d


def expand_BatchNorm1d(bn1d: nn.Module) -> Optional[nn.BatchNorm2d]:
    if not isinstance(bn1d, nn.BatchNorm1d):
        return None
    mod = torch.nn.BatchNorm2d(
        bn1d.num_features,
        eps=bn1d.eps,
        momentum=bn1d.momentum,
        affine=bn1d.affine,
        track_running_stats=bn1d.track_running_stats,
    )
    bn_state = bn1d.state_dict()
    mod.load_state_dict(bn_state)
    return mod


def swap_expanded(model: nn.Module, mapping: Dict[str, nn.Module]):
    """
    This function swaps nested modules as specified by "dot paths" in mod with a desired replacement. This allows
    for swapping nested modules through arbitrary levels if children

    NOTE: This occurs in place, if you want to preserve model then make sure to copy it first.

    """
    for path, new_mod in mapping.items():
        expanded_path = path.split(".")
        parent_mod = model
        for sub_path in expanded_path[:-1]:
            parent_mod = parent_mod._modules[sub_path]  # noqa
        parent_mod._modules[expanded_path[-1]] = new_mod  # noqa

    return model


def simple_expand(BaseT: Type[nn.Module], DestT: Type[nn.Module]) -> Callable[[nn.Module], Optional[nn.Module]]:
    def expansion_fn(mod: nn.Module) -> Optional[nn.Module]:
        if not isinstance(mod, BaseT):
            return None
        args = [getattr(mod, name, None) for name in mod.__constants__]
        out = DestT(*args)
        return out

    return expansion_fn


def auto_expand(
    model: nn.Module, *, expansions: Dict[str, Callable[[nn.Module], Optional[nn.Module]]] = None
) -> nn.Module:
    if expansions is None:
        expansions = {
            "Conv1d": expand_Conv1D,
            "BatchNorm1d": expand_BatchNorm1d,
            "AdaptiveAvgPool1d": simple_expand(nn.AdaptiveAvgPool1d, nn.AdaptiveAvgPool2d),
            "AvgPool1d": simple_expand(nn.AvgPool1d, nn.AvgPool2d),
        }
    mapping: Dict[str, nn.Module] = {}
    for name, m in model.named_modules():
        m_type = type(m).__name__
        if m_type in expansions:
            swapped = expansions[m_type](m)
            if swapped:
                mapping[name] = swapped
    logging.warning(f"Swapped {len(mapping)} modules")
    swap_expanded(model, mapping)
    return model
