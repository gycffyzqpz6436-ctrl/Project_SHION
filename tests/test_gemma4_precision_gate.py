import torch

from training.scripts.gemma4_precision_gate import category_for_parameter, parameter_inventory


class Params4bit(torch.nn.Parameter):
    pass


def test_parameter_categories_are_explicit():
    assert category_for_parameter("model.layers.0.self_attn.q_proj.weight", Params4bit(torch.zeros(2), requires_grad=False)) == "quantized_linear4bit"
    assert category_for_parameter("model.embed_tokens.weight", torch.zeros(2)) == "embedding"
    assert category_for_parameter("model.layers.0.input_layernorm.weight", torch.zeros(2)) == "norm"
    assert category_for_parameter("model.layers.0.self_attn.some_scale", torch.zeros(2)) == "attention_non_quantized"
    assert category_for_parameter("model.layers.0.mlp.some_scale", torch.zeros(2)) == "mlp_non_quantized"


def test_parameter_inventory_reports_dtype_and_category_bytes():
    model = torch.nn.Module()
    model.embed_tokens = torch.nn.Embedding(3, 2, dtype=torch.bfloat16)
    inventory = parameter_inventory(model)
    assert inventory["by_dtype"]["torch.bfloat16"] == {"tensors": 1, "elements": 6, "bytes": 12}
    assert inventory["by_category"]["embedding"]["bytes"] == 12
