import torch

from training.scripts.gemma4_memory_profile import optimizer_tensors, tensor_bytes, tensor_inventory


def test_tensor_bytes_deduplicates_shared_tensor_storage():
    tensor = torch.zeros(8, dtype=torch.bfloat16)
    assert tensor_bytes([tensor, tensor]) == 16


def test_tensor_inventory_groups_actual_dtypes():
    inventory = tensor_inventory([torch.zeros(2, dtype=torch.float32), torch.zeros(3, dtype=torch.bfloat16)])
    assert inventory["tensor_count"] == 2
    assert inventory["unique_bytes"] == 14
    assert inventory["by_dtype"]["torch.float32"]["bytes"] == 8
    assert inventory["by_dtype"]["torch.bfloat16"]["bytes"] == 6


def test_optimizer_tensors_empty_before_first_step():
    parameter = torch.nn.Parameter(torch.ones(2))
    optimizer = torch.optim.AdamW([parameter], lr=1e-3)
    assert optimizer_tensors(optimizer) == []
