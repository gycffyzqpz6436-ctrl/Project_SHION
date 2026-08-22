from torch import nn

from training.scripts.gemma4_feasibility import choose_smoke_records, is_text_decoder_target, lora_leaf_modules


def test_text_decoder_target_rejects_multimodal_and_non_attention_modules():
    assert is_text_decoder_target("model.language_model.layers.0.self_attn.q_proj")
    assert is_text_decoder_target("model.language_model.layers.47.self_attn.o_proj")
    assert is_text_decoder_target("model.layers.0.self_attn.q_proj")
    assert is_text_decoder_target("model.layers.47.self_attn.o_proj")
    assert not is_text_decoder_target("model.vision_tower.layers.0.self_attn.q_proj")
    assert not is_text_decoder_target("model.audio_tower.layers.0.self_attn.q_proj")
    assert not is_text_decoder_target("model.language_model.layers.0.mlp.up_proj")
    assert not is_text_decoder_target("model.language_model.embed_tokens")
    assert not is_text_decoder_target("lm_head")


def test_choose_smoke_records_is_deterministic_and_spans_lengths():
    rows = [{"id": f"shion_{index:06d}"} for index in range(1, 7)]
    lengths = {
        "shion_000001": 40,
        "shion_000002": 80,
        "shion_000003": 100,
        "shion_000004": 120,
        "shion_000005": 200,
        "shion_000006": 290,
    }
    selected = choose_smoke_records(rows, lengths)
    assert [row["id"] for row in selected] == [
        "shion_000001",
        "shion_000004",
        "shion_000005",
        "shion_000006",
    ]


def test_lora_leaf_modules_does_not_count_container_twice():
    model = nn.Module()
    model.proj = nn.Module()
    model.proj.lora_A = nn.ModuleDict({"default": nn.Linear(2, 1, bias=False)})
    assert lora_leaf_modules(model) == ["proj.lora_A.default"]
