#!/usr/bin/env python3

import torch

from .._utils.common import (
    _format_attributions,
    _format_input,
    _format_input_baseline,
    _run_forward,
    _expand_additional_forward_args,
    _expand_target,
    _format_additional_forward_args,
)
from .._utils.attribution import PerturbationAttribution


class ShapleyValueSampling(PerturbationAttribution):
    def __init__(self, forward_func):
        r"""
        Args:

            forward_func (callable): The forward function of the model or
                        any modification of it
        """
        PerturbationAttribution.__init__(self, forward_func)
        self.use_weights = False

    def attribute(
        self,
        inputs,
        baselines=None,
        target=None,
        additional_forward_args=None,
        feature_mask=None,
        num_samples=1,
        ablations_per_eval=1,
    ):
        r""""
        A perturbation based approach to computing attribution, involving
        replacing each input feature with a given baseline / reference, and
        computing the difference in output. By default, each scalar value within
        each input tensor is taken as a feature and replaced independently. Passing
        a feature mask, allows grouping features to be ablated together. This can
        be used in cases such as images, where an entire segment or region
        can be ablated, measuring the importance of the segment (feature group).
        Each input scalar in the group will be given the same attribution value
        equal to the change in target as a result of ablating the entire feature
        group.

        The forward function can either return a scalar per example, or a single
        scalar for the full batch. If a single scalar is returned for the batch,
        `ablations_per_eval` must be 1, and the returned attributions will have
        first dimension 1, corresponding to feature importance across all
        examples in the batch.

        Args:

                inputs (tensor or tuple of tensors):  Input for which ablation
                            attributions are computed. If forward_func takes a single
                            tensor as input, a single input tensor should be provided.
                            If forward_func takes multiple tensors as input, a tuple
                            of the input tensors should be provided. It is assumed
                            that for all given input tensors, dimension 0 corresponds
                            to the number of examples (aka batch size), and if
                            multiple input tensors are provided, the examples must
                            be aligned appropriately.
                baselines (scalar, tensor, tuple of scalars or tensors, optional):
                            Baselines define reference value which replaces each
                            feature when ablated.
                            Baselines can be provided as:
                            - a single tensor, if inputs is a single tensor, with
                                exactly the same dimensions as inputs or
                                broadcastable to match the dimensions of inputs
                            - a single scalar, if inputs is a single tensor, which will
                                be broadcasted for each input value in input tensor.
                            - a tuple of tensors or scalars, the baseline corresponding
                                to each tensor in the inputs' tuple can be:
                                - either a tensor with
                                    exactly the same dimensions as inputs or
                                    broadcastable to match the dimensions of inputs
                                - or a scalar, corresponding to a tensor in the
                                    inputs' tuple. This scalar value is broadcasted
                                    for corresponding input tensor.
                            In the cases when `baselines` is not provided, we internally
                            use zero scalar corresponding to each input tensor.
                            Default: None
                target (int, tuple, tensor or list, optional):  Output indices for
                            which difference is computed (for classification cases,
                            this is usually the target class).
                            If the network returns a scalar value per example,
                            no target index is necessary.
                            For general 2D outputs, targets can be either:

                            - a single integer or a tensor containing a single
                                integer, which is applied to all input examples

                            - a list of integers or a 1D tensor, with length matching
                                the number of examples in inputs (dim 0). Each integer
                                is applied as the target for the corresponding example.

                            For outputs with > 2 dimensions, targets can be either:

                            - A single tuple, which contains #output_dims - 1
                                elements. This target index is applied to all examples.

                            - A list of tuples with length equal to the number of
                                examples in inputs (dim 0), and each tuple containing
                                #output_dims - 1 elements. Each tuple is applied as the
                                target for the corresponding example.

                            Default: None
                additional_forward_args (tuple, optional): If the forward function
                            requires additional arguments other than the inputs for
                            which attributions should not be computed, this argument
                            can be provided. It must be either a single additional
                            argument of a Tensor or arbitrary (non-tuple) type or a
                            tuple containing multiple additional arguments including
                            tensors or any arbitrary python types. These arguments
                            are provided to forward_func in order following the
                            arguments in inputs.
                            For a tensor, the first dimension of the tensor must
                            correspond to the number of examples. For all other types,
                            the given argument is used for all forward evaluations.
                            Note that attributions are not computed with respect
                            to these arguments.
                            Default: None
                feature_mask (tensor or tuple of tensors, optional):
                            feature_mask defines a mask for the input, grouping
                            features which should be ablated together. feature_mask
                            should contain the same number of tensors as inputs.
                            Each tensor should
                            be the same size as the corresponding input or
                            broadcastable to match the input tensor. Each tensor
                            should contain integers in the range 0 to num_features
                            - 1, and indices corresponding to the same feature should
                            have the same value.
                            Note that features within each input tensor are ablated
                            independently (not across tensors).
                            If the forward function returns a single scalar per batch,
                            we enforce that the first dimension of each mask must be 1,
                            since attributions are returned batch-wise rather than per
                            example, so the attributions must correspond to the
                            same features (indices) in each input example.
                            If None, then a feature mask is constructed which assigns
                            each scalar within a tensor as a separate feature, which
                            is ablated independently.
                            Default: None
                ablations_per_eval (int, optional): Allows ablation of multiple features
                            to be processed simultaneously in one call to forward_fn.
                            Each forward pass will contain a maximum of
                            ablations_per_eval * #examples samples.
                            For DataParallel models, each batch is split among the
                            available devices, so evaluations on each available
                            device contain at most
                            (ablations_per_eval * #examples) / num_devices
                            samples.
                            If the forward function returns a single scalar per batch,
                            ablations_per_eval must be set to 1.
                            Default: 1

        Returns:
                *tensor* or tuple of *tensors* of **attributions**:
                - **attributions** (*tensor* or tuple of *tensors*):
                            The attributions with respect to each input feature.
                            If the forward function returns
                            a scalar value per example, attributions will be
                            the same size as the provided inputs, with each value
                            providing the attribution of the corresponding input index.
                            If the forward function returns a scalar per batch, then
                            attribution tensor(s) will have first dimension 1 and
                            the remaining dimensions will match the input.
                            If a single tensor is provided as inputs, a single tensor is
                            returned. If a tuple is provided for inputs, a tuple of
                            corresponding sized tensors is returned.


        Examples::

            >>> # SimpleClassifier takes a single input tensor of size Nx4x4,
            >>> # and returns an Nx3 tensor of class probabilities.
            >>> net = SimpleClassifier()
            >>> # Generating random input with size 2 x 4 x 4
            >>> input = torch.randn(2, 4, 4)
            >>> # Defining FeatureAblation interpreter
            >>> ablator = FeatureAblation(net)
            >>> # Computes ablation attribution, ablating each of the 16
            >>> # scalar input independently.
            >>> attr = ablator.attribute(input, target=1)

            >>> # Alternatively, we may want to ablate features in groups, e.g.
            >>> # grouping each 2x2 square of the inputs and ablating them together.
            >>> # This can be done by creating a feature mask as follows, which
            >>> # defines the feature groups, e.g.:
            >>> # +---+---+---+---+
            >>> # | 0 | 0 | 1 | 1 |
            >>> # +---+---+---+---+
            >>> # | 0 | 0 | 1 | 1 |
            >>> # +---+---+---+---+
            >>> # | 2 | 2 | 3 | 3 |
            >>> # +---+---+---+---+
            >>> # | 2 | 2 | 3 | 3 |
            >>> # +---+---+---+---+
            >>> # With this mask, all inputs with the same value are ablated
            >>> # simultaneously, and the attribution for each input in the same
            >>> # group (0, 1, 2, and 3) per example are the same.
            >>> # The attributions can be calculated as follows:
            >>> # feature mask has dimensions 1 x 4 x 4
            >>> feature_mask = torch.tensor([[[0,0,1,1],[0,0,1,1],
            >>>                             [2,2,3,3],[2,2,3,3]]])
            >>> attr = ablator.attribute(input, target=1, feature_mask=feature_mask)
        """
        # Keeps track whether original input is a tuple or not before
        # converting it into a tuple.
        is_inputs_tuple = isinstance(inputs, tuple)
        inputs, baselines = _format_input_baseline(inputs, baselines)
        additional_forward_args = _format_additional_forward_args(
            additional_forward_args
        )
        baselines = _tensorize_baseline(inputs, baselines)
        initial_eval = _run_forward(
            self.forward_func, baselines, target, additional_forward_args
        )

        num_examples = inputs[0].shape[0]
        feature_mask = _format_input(feature_mask) if feature_mask is not None else None
        if feature_mask is None:
            feature_mask = []
            current_num_features = 0
            for i in range(len(inputs)):
                num_features = torch.numel(inputs[i][0])
                feature_mask.append(current_num_features + torch.reshape(
                    torch.arange(num_features, device=inputs[i].device),
                    inputs[i][0:1].shape,
                ))
                current_num_features += num_features
            total_features = current_num_features
        else:
            total_features = max(torch.max(single_mask).item() for single_mask in feature_mask)

        assert (
            isinstance(ablations_per_eval, int) and ablations_per_eval >= 1
        ), "Ablations per evaluation must be at least 1."

        # Initialize attribution totals and counts
        total_attrib = [
            torch.zeros_like(input[0:1] if single_output_mode else input)
            for input in inputs
        ]

        # Iterate for number of samples, generate a permutation of the features
        # and evlaute the incremntal increase for each feature.
        for i in range(num_samples):
            feature_permutation = torch.randperm(total_features)
            prev_results = initial_eval
            for (
                current_inputs,
                current_add_args,
                current_target,
                current_mask,
            ) in self._ablation_generator(
                inputs,
                additional_forward_args,
                target,
                baselines,
                input_mask,
                feature_permutation,
                ablations_per_eval,
            ):
                # modified_eval dimensions: 1D tensor with length
                # equal to #num_examples * #features in batch
                modified_eval = _run_forward(
                    self.forward_func, current_inputs, current_target, current_add_args
                )
                all_eval = torch.cat((prev_results, modified_eval), dim=0)
                # eval_diff dimensions: (#features in batch, #num_examples, 1,.. 1)
                # (contains 1 more dimension than inputs). This adds extra dimensions
                # of 1 to make the tensor broadcastable with the inputs tensor.
                if single_output_mode:
                    eval_diff = initial_eval - modified_eval
                else:
                    eval_diff = (
                        initial_eval - modified_eval.reshape(-1, num_examples)
                    ).reshape((-1, num_examples) + (len(inputs[i].shape) - 1) * (1,))
                if self.use_weights:
                    weights[i] += current_mask.float().sum(dim=0)
                total_attrib[i] += (eval_diff * current_mask.float()).sum(dim=0)

        # Divide total attributions by number of random permutations and return
        # formatted attributions.
        attrib = tuple(tensor_attrib_total / num_samples for tensor_attrib_total in total_attrib)
        return _format_attributions(is_inputs_tuple, attrib)

    def _ablation_generator(
        self,
        inputs,
        additional_args,
        target,
        baselines,
        feature_permutation,
        input_masks,
        ablations_per_eval,
    ):
        current_count = 0
        current_tensors = baselines
        current_tensors_list = []
        current_mask_list = []

        # Compute repeated additional args and targets
        additional_args_repeated = (
            _expand_additional_forward_args(additional_args, ablations_per_eval)
            if additional_args is not None
            else None
        )
        target_repeated = _expand_target(target, ablations_per_eval)

        for i in range(len(feature_permutation)):
            current_tensors = tuple(current + input*(mask == feature_permutation[i]) for input, current, mask in zip(inputs, current_tensors, input_masks))
            current_tensors_list.append(current_tensors)
            current_mask_list.append(tuple(mask == feature_permutation[i] for mask in input_masks))
            if len(current_tensor_list) == ablations_per_eval:
                combined_inputs = tuple(torch.cat(aligned_tensors, dim=0) for aligned_tensors in zip(*current_tensors_list))
                combined_masks = tuple(torch.cat(aligned_masks, dim=0) for aligned_masks in zip(*current_mask_list))
                yield combined_inputs, additional_args_repeated, target_repeated, combined_masks
                current_tensors_list = []
                current_mask_list = []

        # Create batch with remaining evaluations, may not be a complete batch
        # (= ablations_per_eval)
        if len(current_tensors_list) != 0:
            additional_args_repeated = (
                _expand_additional_forward_args(additional_args, len(current_tensor_list))
                if additional_args is not None
                else None
            )
            target_repeated = _expand_target(target, len(current_tensor_list))
            combined_inputs = tuple(torch.cat(aligned_tensors, dim=0) for aligned_tensors in zip(*current_tensors_list))
            combined_masks = tuple(torch.cat(aligned_masks, dim=0) for aligned_masks in zip(*current_mask_list))
            yield combined_inputs, additional_args_repeated, target_repeated, combined_masks