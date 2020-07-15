
# Investigating Saturation Effects in Integrated Gradients

## Split IG and Experiment Code
Code for expanded IG can be found [here](captum/attr/_core/integrated_gradients_exp.py), which is a variant of Captum's Integrated Gradients method that returns gradients along the path from input to baseline.
The experiments which use this to compute Split IG and experiment with this technique on ImageNet classification models can be found in this notebook.
[View Jupyter Notebook](notebooks/ImageNetSplitIG-Basic.ipynb)

## 3-min Talk
[![Spotlight Talk @ICML 2020 WHI Workshop](https://img.youtube.com/vi/Lft4gfVS1dU/0.jpg)](https://youtu.be/Lft4gfVS1dU)


## Article and BibTex

Here is an article describing SplitIG and initial results on ImageNet classification models. The article is accepted to the [WHI Workshop @ICML 2020](https://sites.google.com/view/whi2020).

You can cite the article as follows:
<br/>
```
@inproceedings{whi2020visualizing,
  title={Investigating Saturation Effects in Integrated Gradients},
  author={Vivek Miglani and Narine Kokhlikyan and Bilal Alsallakh and Miguel Martin and Reblitz-Richardson, Orion},
  booktitle={ICML Workshop on Human Interpretability in Machine Learning (WHI)},
  year={2020},
}
```

## Thank You

If you have any suggestions or feedback, we will be happy to hear from you!
