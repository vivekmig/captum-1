#!/usr/bin/env python3

import torch

from enum import Enum
from inspect import signature

from .approximation_methods import SUPPORTED_METHODS


class ExpansionTypes(Enum):
    repeat = 1
    repeat_interleave = 2


def safe_div(denom, quotient, default_value=None):
    r"""
        A simple utility function to perform `denom / quotient`
        if the statement is undefined => result will be `default_value`
    """
    return denom / quotient if quotient != 0.0 else default_value


def validate_target(num_samples, target):
    if isinstance(target, list) or (
        isinstance(target, torch.Tensor) and torch.numel(target) > 1
    ):
        assert num_samples == len(target), (
            "The number of samples provied in the"
            "input {} does not match with the number of targets. {}".format(
                num_samples, len(target)
            )
        )


def validate_input(
    inputs,
    baselines,
    n_steps=50,
    method="riemann_trapezoid",
    draw_baseline_from_distrib=False,
):
    assert len(inputs) == len(baselines), (
        "Input and baseline must have the same "
        "dimensions, baseline has {} features whereas input has {}.".format(
            len(baselines), len(inputs)
        )
    )

    for input, baseline in zip(inputs, baselines):
        if draw_baseline_from_distrib:
            assert input.shape[1:] == baseline.shape[1:], (
                "The samples in input and baseline batches must have"
                " the same shape. {} != {}".format(baseline.shape[1:], input.shape[1:])
            )
        else:
            assert (
                input.shape == baseline.shape
            ), "Input and baseline must have the same shape. {} != {}".format(
                baseline.shape, input.shape
            )

    assert (
        n_steps >= 0
    ), "The number of steps must be a positive integer. " "Given: {}".format(n_steps)

    assert method in SUPPORTED_METHODS, (
        "Approximation method must be one for the following {}. "
        "Given {}".format(SUPPORTED_METHODS, method)
    )


def validate_noise_tunnel_type(nt_type, supported_noise_tunnel_types):
    assert nt_type in supported_noise_tunnel_types, (
        "Noise types must be either `smoothgrad`, `smoothgrad_sq` or `vargrad`. "
        "Given {}".format(nt_type)
    )


def _format_tensor_into_tuples(inputs):
    if not isinstance(inputs, tuple):
        assert isinstance(
            inputs, torch.Tensor
        ), "`inputs` must have type " "torch.Tensor but {} found: ".format(type(inputs))
        inputs = (inputs,)
    return inputs


# TODO write test case here
def format_input(inputs):
    return _format_tensor_into_tuples(inputs)


def _format_additional_forward_args(additional_forward_args):
    if additional_forward_args is not None and not isinstance(
        additional_forward_args, tuple
    ):
        additional_forward_args = (additional_forward_args,)
    return additional_forward_args


def format_baseline(baselines, inputs):
    if baselines is None:
        return _zeros(inputs)

    if not isinstance(baselines, tuple):
        baselines = (baselines,)

    # TODO create a separate PR to support scalar baselines
    assert isinstance(
        baselines[0], torch.Tensor
    ), "baselines input argument must be either a torch.Tensor or a tuple \
         of those however {} detected".format(
        type(baselines[0])
    )

    return baselines


def _format_input_baseline(inputs, baselines):
    inputs = format_input(inputs)
    baselines = format_baseline(baselines, inputs)
    return inputs, baselines


# This function can potentially be merged with the `format_baseline` function
# however, since currently not all algorithms support baselines of type
# callable this will be kept in a separate function.
def _format_callable_baseline(baselines, inputs):
    if callable(baselines):
        # Note: this assumes that if baselines is a function and if it takes
        # arguments, then the first argument is the `inputs`.
        # This can be expanded in the future with better type checks
        baseline_parameters = signature(baselines).parameters
        if len(baseline_parameters) == 0:
            baselines = baselines()
        else:
            baselines = baselines(inputs)
        # check the type of the baselines and make sure that it is either a
        # tensor or a list of tensors
        assert isinstance(baselines, tuple) or isinstance(
            baselines, torch.Tensor
        ), "`baselines` function should either return a torch.Tensor \
             or a tuple of those"
    return format_baseline(baselines, inputs)


def _format_attributions(is_inputs_tuple, attributions):
    r"""
    In case input is a tensor and the attributions is returned in form of a
    tensor we take the first element of the attributions' tuple to match the
    same shape signatues of the inputs
    """
    assert isinstance(attributions, tuple), "Attributions must be in shape of a tuple"
    assert is_inputs_tuple or len(attributions) == 1, (
        "The input is a single tensor however the attributions aren't."
        "The number of attributed tensors is: {}".format(len(attributions))
    )
    return attributions if is_inputs_tuple else attributions[0]


def _zeros(inputs):
    r"""
    Takes a tuple of tensors as input and returns a tuple that has the same
    size as the `inputs` which contains zero tensors of the same
    shape as the `inputs`

    """
    return tuple(0 * input for input in inputs)


def _reshape_and_sum(tensor_input, num_steps, num_examples, layer_size):
    # Used for attribution methods which perform integration
    # Sums across integration steps by reshaping tensor to
    # (num_steps, num_examples, (layer_size)) and summing over
    # dimension 0. Returns a tensor of size (num_examples, (layer_size))
    return torch.sum(
        tensor_input.reshape((num_steps, num_examples) + layer_size), dim=0
    )


def _verify_select_column(output, target):
    target = (target,) if isinstance(target, int) else target
    assert (
        len(target) <= len(output.shape) - 1
    ), "Cannot choose target column with output shape %r." % (output.shape,)
    return output[(slice(None), *target)]


def _select_targets(output, target):
    num_examples = output.shape[0]
    dims = len(output.shape)
    if target is None:
        return output
    elif isinstance(target, int) or isinstance(target, tuple):
        return _verify_select_column(output, target)
    elif isinstance(target, torch.Tensor):
        if torch.numel(target) == 1 and isinstance(target.item(), int):
            return _verify_select_column(output, target.item())
        elif len(target.shape) == 1 and torch.numel(target) == num_examples:
            assert dims == 2, "Output must be 2D to select tensor of targets."
            return torch.gather(output, 1, target.reshape(len(output), 1))
        else:
            raise AssertionError(
                "Tensor target dimension %r is not valid." % (target.shape,)
            )
    elif isinstance(target, list):
        assert len(target) == num_examples, "Target list length does not match output!"
        if type(target[0]) is int:
            assert dims == 2, "Output must be 2D to select tensor of targets."
            return torch.gather(output, 1, torch.tensor(target).reshape(len(output), 1))
        elif type(target[0]) is tuple:
            return torch.stack(
                [output[(i,) + targ_elem] for i, targ_elem in enumerate(target)]
            )
        else:
            raise AssertionError("Target element type in list is not valid.")
    else:
        raise AssertionError("Target type %r is not valid." % target)


def _run_forward(forward_func, inputs, target=None, additional_forward_args=None):
    # make everything a tuple so that it is easy to unpack without
    # using if-statements
    inputs = format_input(inputs)
    additional_forward_args = _format_additional_forward_args(additional_forward_args)

    output = forward_func(
        *(*inputs, *additional_forward_args)
        if additional_forward_args is not None
        else inputs
    )
    return _select_targets(output, target)


def _expand_additional_forward_args(
    additional_forward_args, n_steps, expansion_type=ExpansionTypes.repeat
):
    def _expand_tensor_forward_arg(
        additional_forward_arg, n_steps, expansion_type=ExpansionTypes.repeat
    ):
        if len(additional_forward_arg.size()) == 0:
            return additional_forward_arg
        if expansion_type == ExpansionTypes.repeat:
            return torch.cat([additional_forward_arg] * n_steps, dim=0)
        elif expansion_type == ExpansionTypes.repeat_interleave:
            return additional_forward_arg.repeat_interleave(n_steps, dim=0)
        else:
            raise NotImplementedError(
                "Currently only `repeat` and `repeat_interleave`"
                " expansion_types are supported"
            )

    return tuple(
        _expand_tensor_forward_arg(additional_forward_arg, n_steps, expansion_type)
        if isinstance(additional_forward_arg, torch.Tensor)
        else additional_forward_arg
        for additional_forward_arg in additional_forward_args
    )


def _expand_target(target, n_steps, expansion_type=ExpansionTypes.repeat):
    if isinstance(target, list):
        if expansion_type == ExpansionTypes.repeat:
            return target * n_steps
        elif expansion_type == ExpansionTypes.repeat_interleave:
            expanded_target = []
            for i in target:
                expanded_target.extend([i] * n_steps)
            return expanded_target
        else:
            raise NotImplementedError(
                "Currently only `repeat` and `repeat_interleave`"
                " expansion_types are supported"
            )

    elif isinstance(target, torch.Tensor) and torch.numel(target) > 1:
        if expansion_type == ExpansionTypes.repeat:
            return torch.cat([target] * n_steps, dim=0)
        elif expansion_type == ExpansionTypes.repeat_interleave:
            return target.repeat_interleave(n_steps, dim=0)
        else:
            raise NotImplementedError(
                "Currently only `repeat` and `repeat_interleave`"
                " expansion_types are supported"
            )

    return target


class MaxList:
    """Keep track of N maximal items

    Implementation of MaxList:
        for keeping track of the N top values of a large collection of items.
        Maintains a sorted list of the top N items that can be fetched with
        getlist().

    Example use:
        m = MaxList(2, key=lamda x: len(x))
        ml.add("Hello World")
        ml.add("Mermaid Man!!!!")
        ml.add("Why?")
        ml.getlist() -> ["Mermaid Man!!!!", "Hello World"]

    If storing values that are not comparable, please provide a key function that
        that maps the values to some numeric value.
    """

    def __init__(self, size, key=lambda x: x):
        self.size = size
        self.key = key
        self.list = []

    def add(self, item):
        """Add an element to the MaxList

        Args:
            item: the item that you want to add to the MaxList
        """
        value = self.key(item)
        if len(self.list) < self.size:
            if len(self.list) == 0:
                self.list.append((value, item))
            elif self.list[-1][0] >= value:
                self.list.append((value, item))
            else:
                self._insert(item, value)
        if self.list[-1][0] < value:
            self._insert(item, value)

    def get_list(self):
        """Retrive the list of N maximal items in sorted order

        Returns:
            list: the sorted list of maximal items
        """
        return [item[1] for item in self.list]

    def _insert(self, item, value):
        if len(self.list) == 0:
            self.list.append((value, item))

        for i in range(len(self.list)):
            if self.list[i][0] < value:
                self.list.insert(i, (value, item))
                break
        self.list = self.list[: self.size]


class Stat:
    """Keep track of statistics for a quantity that is measured live

    Implementation of an online statistics tracker, Stat:
        For a memory efficient way of keeping track of statistics on a large set of
        numbers. Adding numbers to the object will update the values stored in the
        object to reflect the statistics of all numbers that the object has seen
        so far.

    Example usage:
        s = Stat()
        s([5,7]) OR s.update([5,7])
        stats.get_mean() -> 6
        stats.get_std() -> 1

    """

    def __init__(self):
        self.count = 0
        self.mean = 0
        self.mean_squared_error = 0
        self.min = float("inf")
        self.max = float("-inf")

    def _std_size_check(self):
        if self.count < 2:
            raise Exception(
                "Std/Variance is not defined for {} datapoints\
                ".format(
                    self.count
                )
            )

    def update(self, x):
        """Update the stats given a new number

        Adds x to the running statistics being kept track of, and updates internal
        values that relfect that change.

        Args:
            x: a numeric value, or a list of numeric values
        """
        if isinstance(x, list):
            for value in x:
                self.update(value)
        else:
            x = float(x)
            self.min = min(self.min, x)
            self.max = max(self.max, x)
            self.count += 1
            delta = x - self.mean
            self.mean += delta / self.count
            delta2 = x - self.mean
            self.mean_squared_error += delta * delta2

    def get_stats(self):
        """Retrieves a dictionary of statistics for the values seen.

        Returns:
            a fully populated dictionary for the statistics that have been
            maintained. This output is easy to pipe into a table with a loop over
            key value pairs.
        """
        self._std_size_check()

        sampleVariance = self.mean_squared_error / (self.count - 1)
        Variance = self.mean_squared_error / self.count

        return {
            "mean": self.mean,
            "sample_variance": sampleVariance,
            "variance": Variance,
            "std": Variance ** 0.5,
            "min": self.min,
            "max": self.max,
            "count": self.count,
        }

    def get_std(self):
        """get the std of the statistics kept"""
        self._std_size_check()
        return (self.mean_squared_error / self.count) ** 0.5

    def get_variance(self):
        """get the variance of the statistics kept"""
        self._std_size_check()
        return self.mean_squared_error / self.count

    def get_sample_variance(self):
        """get the sample variance of the statistics kept"""
        self._std_size_check()
        return self.mean_squared_error / (self.count - 1)

    def get_mean(self):
        """get the mean of the statistics kept"""
        return self.mean

    def get_max(self):
        """get the max of the statistics kept"""
        return self.max

    def get_min(self):
        """get the min of the statistics kept"""
        return self.min

    def get_count(self):
        """get the count of the statistics kept"""
        return self.count
