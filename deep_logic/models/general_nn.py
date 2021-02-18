import torch

from ..nn import XLinear
from ..utils.general_nn import prune_features_fanin
from ..utils.relu_nn import prune_features
from ..logic.relu_nn import combine_local_explanations, explain_local
from .base import BaseClassifier, BaseXModel


class XGeneralNN(BaseClassifier, BaseXModel):
    """
        Feed forward Neural Network with pruning on the first layer.
        After training it provides both local and global explanations

        :param n_classes: int
            number of classes to classify - dimension of the output layer of the network
        :param n_features: int
            number of features - dimension of the input space
        :param hidden_neurons: list
            number of hidden neurons per layer. The length of the list corresponds to the depth of the network.
        :param loss: torch.nn.modules.loss
            type of loss to employ
        :param l1_weight: float
            weight of the l1 regularization on the weights of the network. Allows extracting compact explanations
     """

    def __init__(self, n_classes: int, n_features: int, hidden_neurons: list, loss: torch.nn.modules.loss,
                 l1_weight: float = 1e-4, fan_in: int = None, device: torch.device = torch.device('cpu'),
                 name: str = "general_net.pth"):

        super().__init__(loss, name, device)
        self.n_classes = n_classes
        self.n_features = n_features

        layers = []
        for i in range(len(hidden_neurons) + 1):
            input_nodes = hidden_neurons[i - 1] if i != 0 else n_features
            output_nodes = hidden_neurons[i] if i != len(hidden_neurons) else n_classes
            if i == 0:
                layer = torch.nn.Linear(input_nodes, output_nodes * self.n_classes)
            elif i != len(hidden_neurons):
                layer = XLinear(input_nodes, output_nodes, self.n_classes)
            else:
                layer = XLinear(input_nodes, 1, self.n_classes)
            layers.extend([
                layer,
                torch.nn.LeakyReLU() if i != len(hidden_neurons) else torch.nn.Identity()
            ])
        self.model = torch.nn.Sequential(*layers)
        self.l1_weight = l1_weight
        self.fan_in = fan_in
        self.need_pruning = True

    def get_loss(self, output: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        get_loss method extended from Classifier. The loss passed in the __init__ function of the InterpretableReLU is
        employed. An L1 weight regularization is also always applied

        :param output: output tensor from the forward function
        :param target: label tensor
        :return: loss tensor value
        """
        l1_reg_loss = .0
        for layer in self.model.children():
            if hasattr(layer, "weight"):
                l1_reg_loss += torch.sum(torch.abs(layer.weight))
                break
        output_loss = super().get_loss(output, target)
        return output_loss + self.l1_weight * l1_reg_loss

    def forward(self, x, logits=False) -> torch.Tensor:
        """
        forward method extended from Classifier. Here input data goes through the layer of the Sigmoid network.
        A probability value is returned in output after sigmoid activation

        :param x: input tensor
        :param logits: whether to return the logits or the probability value after the activation (default)
        :return: output classification
        """
        super(XGeneralNN, self).forward(x)
        output = self.model(x)
        if logits:
            return output
        output = self.activation(output)
        return output

    def prune(self):
        if self.fan_in is None:
            prune_features(self.model, self.n_classes, device=self.get_device())
        else:
            prune_features_fanin(self.model, self.fan_in, self.n_classes, device=self.get_device())

    def get_local_explanation(self, x: torch.Tensor, y: torch.Tensor, x_sample: torch.Tensor,
                              target_class, simplify: bool = True, concept_names: list = None):
        """
        Get explanation of model decision taken on the input x_sample.

        :param x: input samples
        :param y: target labels
        :param x_sample: input for which the explanation is required
        :param target_class: class ID
        :param simplify: simplify local explanation
        :param concept_names: list containing the names of the input concepts

        :return: Local Explanation
        """
        if self.fan_in is None:
            method = "weights"
        else:
            method = "pruning"
        return explain_local(self.model, x, y, x_sample, target_class, method=method, simplify=simplify,
                             concept_names=concept_names, device=self.get_device(), num_classes=self.n_classes)

    def get_global_explanation(self, x, y, target_class: int, topk_explanations: int = 2, simplify: bool = True,
                               concept_names: list = None):
        """
        Generate a global explanation combining local explanations.

        :param x: input samples
        :param y: target labels
        :param target_class: class ID
        :param topk_explanations: number of most common local explanations to combine in a global explanation
                (it controls the complexity of the global explanation)
        :param simplify: simplify local explanation
        :param concept_names: list containing the names of the input concepts
        """
        if self.fan_in is None:
            method = "weights"
        else:
            method = "pruning"
        global_expl, _, _ = combine_local_explanations(self.model, x, y, target_class, method=method,
                                                       simplify=simplify, topk_explanations=topk_explanations,
                                                       concept_names=concept_names, device=self.get_device(),
                                                       num_classes=self.n_classes)
        return global_expl


if __name__ == "__main__":
    pass
