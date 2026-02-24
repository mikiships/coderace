"""Tests for cost estimation engine (D1)."""

from __future__ import annotations

import pytest

from coderace.cost import (
    PRICING,
    CostResult,
    calculate_cost,
    estimate_from_sizes,
    get_pricing,
    parse_aider_cost,
    parse_claude_cost,
    parse_codex_cost,
    parse_gemini_cost,
    parse_opencode_cost,
)


# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------


def test_pricing_table_has_required_models() -> None:
    """Pricing table must have all required models."""
    required_keys = {
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "gpt-5.3-codex",
        "gemini-2.5-pro",
        "gemini-3.1-pro",
    }
    for key in required_keys:
        assert key in PRICING, f"Missing pricing entry for {key!r}"


def test_pricing_values_are_positive() -> None:
    for key, (inp, out) in PRICING.items():
        assert inp >= 0, f"{key}: input price must be >= 0"
        assert out >= 0, f"{key}: output price must be >= 0"


def test_get_pricing_exact_match() -> None:
    inp, out = get_pricing("claude-sonnet-4-6")
    assert inp == 3.00
    assert out == 15.00


def test_get_pricing_case_insensitive() -> None:
    inp, out = get_pricing("Claude-Sonnet-4-6")
    assert inp > 0


def test_get_pricing_partial_match() -> None:
    # "gemini-pro" should match gemini-2.5-pro or similar
    inp, out = get_pricing("gemini-pro")
    assert inp > 0
    assert out > 0


def test_get_pricing_unknown_model_fallback() -> None:
    inp, out = get_pricing("totally-unknown-model-xyz")
    # Returns fallback, not zero
    assert inp > 0
    assert out > 0


# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------


def test_calculate_cost_basic() -> None:
    # 1M input + 0 output at $3/M = $3.00
    cost = calculate_cost(1_000_000, 0, "claude-sonnet-4-6")
    assert abs(cost - 3.00) < 0.01


def test_calculate_cost_zero_tokens() -> None:
    cost = calculate_cost(0, 0, "claude-sonnet-4-6")
    assert cost == 0.0


def test_calculate_cost_custom_pricing() -> None:
    custom = {"mymodel": (1.0, 2.0)}
    cost = calculate_cost(1_000_000, 1_000_000, "mymodel", custom_pricing=custom)
    assert abs(cost - 3.0) < 0.01  # (1M * 1 + 1M * 2) / 1M = 3.0


def test_calculate_cost_output_tokens() -> None:
    # 0 input + 1M output at $15/M = $15
    cost = calculate_cost(0, 1_000_000, "claude-sonnet-4-6")
    assert abs(cost - 15.00) < 0.01


# ---------------------------------------------------------------------------
# CostResult dataclass
# ---------------------------------------------------------------------------


def test_cost_result_valid() -> None:
    cr = CostResult(
        input_tokens=1000,
        output_tokens=200,
        estimated_cost_usd=0.05,
        model_name="claude-sonnet-4-6",
        pricing_source="parsed",
    )
    assert cr.input_tokens == 1000
    assert cr.output_tokens == 200
    assert cr.estimated_cost_usd == 0.05
    assert cr.pricing_source == "parsed"


def test_cost_result_invalid_negative_tokens() -> None:
    with pytest.raises(ValueError):
        CostResult(
            input_tokens=-1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            model_name="test",
            pricing_source="parsed",
        )


def test_cost_result_invalid_negative_cost() -> None:
    with pytest.raises(ValueError):
        CostResult(
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=-0.01,
            model_name="test",
            pricing_source="parsed",
        )


# ---------------------------------------------------------------------------
# estimate_from_sizes
# ---------------------------------------------------------------------------


def test_estimate_from_sizes_basic() -> None:
    result = estimate_from_sizes(4000, 1000, "claude-sonnet-4-6")
    assert result.input_tokens == 1000  # 4000 / 4
    assert result.output_tokens == 250  # 1000 / 4
    assert result.estimated_cost_usd > 0
    assert result.pricing_source == "estimated"


def test_estimate_from_sizes_zero_bytes() -> None:
    # Should not crash; tokens = max(1, 0//4) = 1
    result = estimate_from_sizes(0, 0, "claude-sonnet-4-6")
    assert result.input_tokens >= 1
    assert result.output_tokens >= 1


# ---------------------------------------------------------------------------
# parse_claude_cost
# ---------------------------------------------------------------------------


def test_parse_claude_cost_json_usage() -> None:
    stdout = '{"type": "result", "usage": {"input_tokens": 1500, "output_tokens": 300}}'
    result = parse_claude_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 1500
    assert result.output_tokens == 300
    assert result.estimated_cost_usd > 0
    assert result.pricing_source == "parsed"


def test_parse_claude_cost_total_cost_line() -> None:
    stderr = "Total cost: $0.0523\nInput: 1234 tokens\nOutput: 567 tokens"
    result = parse_claude_cost("", stderr)
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.0523) < 0.001
    assert result.input_tokens == 1234
    assert result.output_tokens == 567


def test_parse_claude_cost_total_cost_no_tokens() -> None:
    """Cost line with no token counts — should still return a result."""
    stderr = "Total cost: $0.10"
    result = parse_claude_cost("", stderr)
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.10) < 0.001


def test_parse_claude_cost_missing_output() -> None:
    """No cost data at all — return None."""
    result = parse_claude_cost("", "")
    assert result is None


def test_parse_claude_cost_partial_tokens() -> None:
    """Only input tokens, no output — return None (can't compute)."""
    result = parse_claude_cost("", "Input: 1000 tokens")
    assert result is None


def test_parse_claude_cost_custom_model() -> None:
    stdout = '{"usage": {"input_tokens": 100, "output_tokens": 50}}'
    result = parse_claude_cost(stdout, "", model_name="claude-opus-4-6")
    assert result is not None
    assert result.model_name == "claude-opus-4-6"
    # Opus is more expensive than Sonnet
    sonnet = parse_claude_cost(stdout, "", model_name="claude-sonnet-4-6")
    assert result.estimated_cost_usd > sonnet.estimated_cost_usd


# ---------------------------------------------------------------------------
# parse_codex_cost
# ---------------------------------------------------------------------------


def test_parse_codex_cost_usage_line() -> None:
    stderr = "Usage: prompt_tokens=1234, completion_tokens=567, total_tokens=1801"
    result = parse_codex_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 1234
    assert result.output_tokens == 567
    assert result.estimated_cost_usd > 0
    assert result.pricing_source == "parsed"


def test_parse_codex_cost_input_output_style() -> None:
    stdout = "Input: 800 tokens\nOutput: 200 tokens"
    result = parse_codex_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 800
    assert result.output_tokens == 200


def test_parse_codex_cost_tokens_used_format() -> None:
    stdout = "Tokens used: 1000 (800 input, 200 output)"
    result = parse_codex_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 800
    assert result.output_tokens == 200


def test_parse_codex_cost_missing_output() -> None:
    result = parse_codex_cost("", "")
    assert result is None


def test_parse_codex_cost_comma_separated_numbers() -> None:
    stderr = "Usage: prompt_tokens=12,345, completion_tokens=6,789"
    result = parse_codex_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 12345
    assert result.output_tokens == 6789


# ---------------------------------------------------------------------------
# parse_gemini_cost
# ---------------------------------------------------------------------------


def test_parse_gemini_cost_token_count_style() -> None:
    stdout = "inputTokenCount=1000, outputTokenCount=250"
    result = parse_gemini_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 1000
    assert result.output_tokens == 250
    assert result.pricing_source == "parsed"


def test_parse_gemini_cost_input_output_style() -> None:
    stderr = "input=500, output=100"
    result = parse_gemini_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 500
    assert result.output_tokens == 100


def test_parse_gemini_cost_generic_tokens() -> None:
    stdout = "Input: 300 tokens\nOutput: 75 tokens"
    result = parse_gemini_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 300
    assert result.output_tokens == 75


def test_parse_gemini_cost_missing_output() -> None:
    result = parse_gemini_cost("", "")
    assert result is None


# ---------------------------------------------------------------------------
# parse_aider_cost
# ---------------------------------------------------------------------------


def test_parse_aider_cost_full_line() -> None:
    stderr = "Tokens: 1234 sent, 567 received. Cost: $0.052 message, $0.052 session."
    result = parse_aider_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 1234
    assert result.output_tokens == 567
    assert abs(result.estimated_cost_usd - 0.052) < 0.001
    assert result.pricing_source == "parsed"


def test_parse_aider_cost_tokens_only() -> None:
    """Tokens present but no cost line — should estimate from tokens."""
    stderr = "Tokens: 800 sent, 200 received."
    result = parse_aider_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 800
    assert result.output_tokens == 200
    assert result.estimated_cost_usd > 0


def test_parse_aider_cost_cost_only() -> None:
    """Cost line without tokens."""
    stderr = "Cost: $0.08"
    result = parse_aider_cost("", stderr)
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.08) < 0.001


def test_parse_aider_cost_missing_output() -> None:
    result = parse_aider_cost("", "")
    assert result is None


def test_parse_aider_cost_comma_numbers() -> None:
    stderr = "Tokens: 12,345 sent, 6,789 received. Cost: $0.52 message, $1.23 session."
    result = parse_aider_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 12345
    assert result.output_tokens == 6789


# ---------------------------------------------------------------------------
# parse_opencode_cost
# ---------------------------------------------------------------------------


def test_parse_opencode_cost_total_cost_with_tokens() -> None:
    stdout = "Input: 1000 tokens\nOutput: 250 tokens\nTotal cost: $0.04"
    result = parse_opencode_cost(stdout, "")
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.04) < 0.001
    assert result.pricing_source == "parsed"


def test_parse_opencode_cost_total_cost_no_tokens() -> None:
    stdout = "Total cost: $0.05"
    result = parse_opencode_cost(stdout, "")
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.05) < 0.001


def test_parse_opencode_cost_generic_tokens() -> None:
    stdout = "Input: 500 tokens\nOutput: 100 tokens"
    result = parse_opencode_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 500
    assert result.output_tokens == 100


def test_parse_opencode_cost_missing_output() -> None:
    result = parse_opencode_cost("", "")
    assert result is None


# ---------------------------------------------------------------------------
# Adapter parse_cost methods
# ---------------------------------------------------------------------------


def test_claude_adapter_parse_cost() -> None:
    from coderace.adapters.claude import ClaudeAdapter
    adapter = ClaudeAdapter()
    stdout = '{"usage": {"input_tokens": 500, "output_tokens": 100}}'
    result = adapter.parse_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 500


def test_codex_adapter_parse_cost() -> None:
    from coderace.adapters.codex import CodexAdapter
    adapter = CodexAdapter()
    stderr = "Usage: prompt_tokens=400, completion_tokens=100, total_tokens=500"
    result = adapter.parse_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 400


def test_gemini_adapter_parse_cost() -> None:
    from coderace.adapters.gemini import GeminiAdapter
    adapter = GeminiAdapter()
    stdout = "inputTokenCount=800, outputTokenCount=200"
    result = adapter.parse_cost(stdout, "")
    assert result is not None
    assert result.input_tokens == 800


def test_aider_adapter_parse_cost() -> None:
    from coderace.adapters.aider import AiderAdapter
    adapter = AiderAdapter()
    stderr = "Tokens: 600 sent, 150 received. Cost: $0.02 message, $0.05 session."
    result = adapter.parse_cost("", stderr)
    assert result is not None
    assert result.input_tokens == 600


def test_opencode_adapter_parse_cost() -> None:
    from coderace.adapters.opencode import OpenCodeAdapter
    adapter = OpenCodeAdapter()
    stdout = "Total cost: $0.03"
    result = adapter.parse_cost(stdout, "")
    assert result is not None
    assert abs(result.estimated_cost_usd - 0.03) < 0.001


def test_all_adapters_return_none_on_empty() -> None:
    """All adapters must return None (not raise) when output is empty."""
    from coderace.adapters.aider import AiderAdapter
    from coderace.adapters.claude import ClaudeAdapter
    from coderace.adapters.codex import CodexAdapter
    from coderace.adapters.gemini import GeminiAdapter
    from coderace.adapters.opencode import OpenCodeAdapter

    for adapter_cls in [ClaudeAdapter, CodexAdapter, AiderAdapter, GeminiAdapter, OpenCodeAdapter]:
        adapter = adapter_cls()
        result = adapter.parse_cost("", "")
        assert result is None, f"{adapter_cls.__name__} should return None on empty output"
