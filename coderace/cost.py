"""Cost estimation engine for coderace.

Pricing table maps model names to (input_price, output_price) per 1M tokens.
Prices are in USD. Easy to update — just edit the PRICING dict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Pricing table  (USD per 1M tokens — input, output)
# ---------------------------------------------------------------------------
# Keys are canonical model identifiers used in agent output.
# Entries: (input_usd_per_1m, output_usd_per_1m)
PRICING: dict[str, tuple[float, float]] = {
    # Claude Code
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    # Aliases / short names that agents may print
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
    # Codex / GPT
    "gpt-5.3-codex": (3.00, 15.00),
    "codex": (3.00, 15.00),
    # Gemini CLI
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3.1-pro": (1.25, 10.00),
    "gemini-pro": (1.25, 10.00),
    # Aider default (user-configurable, falls back to this)
    "aider-default": (3.00, 15.00),
    # OpenCode default (user-configurable)
    "opencode-default": (3.00, 15.00),
}

# Fallback pricing used when model is unknown
_FALLBACK_PRICING: tuple[float, float] = (3.00, 15.00)

# Rough estimate: bytes per token (used for file-size fallback)
_BYTES_PER_TOKEN = 4


@dataclass
class CostResult:
    """Cost estimate for a single agent run."""

    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    model_name: str
    pricing_source: str  # "parsed" | "estimated" | "custom"

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError("input_tokens must be >= 0")
        if self.output_tokens < 0:
            raise ValueError("output_tokens must be >= 0")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be >= 0")


def get_pricing(model_name: str) -> tuple[float, float]:
    """Return (input_usd_per_1m, output_usd_per_1m) for a model.

    Performs case-insensitive prefix matching so partial names work.
    Falls back to _FALLBACK_PRICING if no match found.
    """
    lower = model_name.lower()
    # Exact match first
    if lower in PRICING:
        return PRICING[lower]
    # Prefix/substring match
    for key, prices in PRICING.items():
        if key in lower or lower in key:
            return prices
    return _FALLBACK_PRICING


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model_name: str,
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> float:
    """Return estimated cost in USD."""
    if custom_pricing:
        lower = model_name.lower()
        for key, prices in custom_pricing.items():
            if key.lower() in lower or lower in key.lower():
                inp_price, out_price = prices
                return (input_tokens * inp_price + output_tokens * out_price) / 1_000_000
    inp_price, out_price = get_pricing(model_name)
    return (input_tokens * inp_price + output_tokens * out_price) / 1_000_000


def estimate_from_sizes(
    input_bytes: int,
    output_bytes: int,
    model_name: str,
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> CostResult:
    """Estimate cost from file/diff sizes when token counts aren't available."""
    input_tokens = max(1, input_bytes // _BYTES_PER_TOKEN)
    output_tokens = max(1, output_bytes // _BYTES_PER_TOKEN)
    cost = calculate_cost(input_tokens, output_tokens, model_name, custom_pricing)
    return CostResult(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
        model_name=model_name,
        pricing_source="estimated",
    )


# ---------------------------------------------------------------------------
# Claude Code parser
# ---------------------------------------------------------------------------
# Claude Code with --output-format json prints a JSON object as stdout.
# The session summary includes token usage in the structure:
#   {"usage": {"input_tokens": N, "output_tokens": N, ...}}
# or in the session_summary field.
#
# Claude also prints a human-readable summary to stderr:
#   "Total cost: $0.0523"
#   or token lines like "Input: 1234 tokens, Output: 567 tokens"

def parse_claude_cost(
    stdout: str,
    stderr: str,
    model_name: str = "claude-sonnet-4-6",
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> Optional[CostResult]:
    """Parse cost data from Claude Code output.

    Claude Code (--output-format json) outputs a JSON object that may include
    usage stats. It also prints token/cost summaries to stderr.
    """
    combined = stdout + "\n" + stderr

    # Try to extract a direct cost line: "Total cost: $0.052"
    cost_match = re.search(r"[Tt]otal\s+cost[:\s]+\$?([\d]+\.[\d]+)", combined)
    if cost_match:
        cost_usd = float(cost_match.group(1))
        # Also try to get token counts
        in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
        out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
        if in_tok is not None and out_tok is not None:
            return CostResult(
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost_usd,
                model_name=model_name,
                pricing_source="parsed",
            )
        # Cost parsed but no tokens — synthesise token counts from cost
        inp_price, out_price = get_pricing(model_name)
        if inp_price + out_price > 0:
            # assume 4:1 input:output ratio as rough split
            ratio = 4.0
            out_tok = int(cost_usd * 1_000_000 / (inp_price * ratio + out_price))
            in_tok = int(out_tok * ratio)
        else:
            in_tok = out_tok = 0
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost_usd,
            model_name=model_name,
            pricing_source="parsed",
        )

    # Try to parse JSON usage block from Claude --output-format json output
    try:
        import json as _json
        # The stdout may contain a JSON object
        data = _json.loads(stdout.strip())
        usage = None
        if isinstance(data, dict):
            usage = data.get("usage") or data.get("token_usage")
        if usage and isinstance(usage, dict):
            in_tok = int(usage.get("input_tokens", 0))
            out_tok = int(usage.get("output_tokens", 0))
            cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
            return CostResult(
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost,
                model_name=model_name,
                pricing_source="parsed",
            )
    except Exception:
        pass

    # Try generic token patterns
    in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
    out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    return None


# ---------------------------------------------------------------------------
# Codex parser
# ---------------------------------------------------------------------------
# Codex prints something like:
#   "Usage: prompt_tokens=1234, completion_tokens=567, total_tokens=1801"
# or lines containing "tokens used:" etc.

def parse_codex_cost(
    stdout: str,
    stderr: str,
    model_name: str = "gpt-5.3-codex",
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> Optional[CostResult]:
    """Parse cost data from Codex CLI output."""
    combined = stdout + "\n" + stderr

    # Pattern: "prompt_tokens=N" / "completion_tokens=N"
    in_tok = _extract_token_count(combined, r"prompt_tokens[=:\s]+([\d,]+)")
    out_tok = _extract_token_count(combined, r"completion_tokens[=:\s]+([\d,]+)")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    # Alternative pattern: "input: N tokens" / "output: N tokens"
    in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
    out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    # "Tokens used: N (N input, N output)"
    m = re.search(r"[Tt]okens?\s+used[:\s]+([\d,]+)\s*\(([\d,]+)\s+input[,\s]+([\d,]+)\s+output", combined)
    if m:
        in_tok = _parse_int(m.group(2))
        out_tok = _parse_int(m.group(3))
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    return None


# ---------------------------------------------------------------------------
# Gemini parser
# ---------------------------------------------------------------------------
# Gemini CLI may print:
#   "Tokens: input=N, output=N" or
#   "Usage: inputTokens=N, outputTokens=N"

def parse_gemini_cost(
    stdout: str,
    stderr: str,
    model_name: str = "gemini-2.5-pro",
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> Optional[CostResult]:
    """Parse cost data from Gemini CLI output."""
    combined = stdout + "\n" + stderr

    # "inputTokenCount" / "outputTokenCount" (Gemini API JSON style)
    in_tok = _extract_token_count(combined, r"[Ii]nput[Tt]oken[Cc]ount[=:\s]+([\d,]+)")
    out_tok = _extract_token_count(combined, r"[Oo]utput[Tt]oken[Cc]ount[=:\s]+([\d,]+)")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    # "input=N, output=N" style
    in_tok = _extract_token_count(combined, r"\binput[=:\s]+([\d,]+)")
    out_tok = _extract_token_count(combined, r"\boutput[=:\s]+([\d,]+)")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    # Generic token patterns
    in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
    out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    return None


# ---------------------------------------------------------------------------
# Aider parser
# ---------------------------------------------------------------------------
# Aider prints cost to stderr:
#   "Tokens: 1234 sent, 567 received. Cost: $0.052 message, $0.052 session."
# or
#   "Cost: $0.0523"

def parse_aider_cost(
    stdout: str,
    stderr: str,
    model_name: str = "aider-default",
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> Optional[CostResult]:
    """Parse cost data from Aider output."""
    combined = stdout + "\n" + stderr

    # "Tokens: 1234 sent, 567 received. Cost: $0.052 message, $0.123 session."
    m = re.search(
        r"[Tt]okens?[:\s]+([\d,]+)\s+sent[,\s]+([\d,]+)\s+received",
        combined,
    )
    if m:
        in_tok = _parse_int(m.group(1))
        out_tok = _parse_int(m.group(2))
        # Try to get the cost directly
        cost_m = re.search(r"[Cc]ost[:\s]+\$?([\d.]+)\s+message", combined)
        if cost_m:
            cost_usd = float(cost_m.group(1))
        else:
            cost_usd = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost_usd,
            model_name=model_name,
            pricing_source="parsed",
        )

    # Fallback: just a cost line
    cost_match = re.search(r"[Cc]ost[:\s]+\$?([\d.]+)", combined)
    if cost_match:
        cost_usd = float(cost_match.group(1))
        inp_price, out_price = get_pricing(model_name)
        if inp_price + out_price > 0:
            ratio = 4.0
            out_tok = int(cost_usd * 1_000_000 / (inp_price * ratio + out_price))
            in_tok = int(out_tok * ratio)
        else:
            in_tok = out_tok = 0
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost_usd,
            model_name=model_name,
            pricing_source="parsed",
        )

    return None


# ---------------------------------------------------------------------------
# OpenCode parser
# ---------------------------------------------------------------------------
# OpenCode output format is not well-documented; attempt generic patterns.

def parse_opencode_cost(
    stdout: str,
    stderr: str,
    model_name: str = "opencode-default",
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> Optional[CostResult]:
    """Parse cost data from OpenCode output."""
    combined = stdout + "\n" + stderr

    # Generic cost line
    cost_match = re.search(r"[Tt]otal\s+cost[:\s]+\$?([\d.]+)", combined)
    if cost_match:
        cost_usd = float(cost_match.group(1))
        in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
        out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
        if in_tok is not None and out_tok is not None:
            return CostResult(
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost_usd,
                model_name=model_name,
                pricing_source="parsed",
            )
        return CostResult(
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=cost_usd,
            model_name=model_name,
            pricing_source="parsed",
        )

    # Generic token patterns
    in_tok = _extract_token_count(combined, r"[Ii]nput[:\s]+([\d,]+)\s*tokens?")
    out_tok = _extract_token_count(combined, r"[Oo]utput[:\s]+([\d,]+)\s*tokens?")
    if in_tok is not None and out_tok is not None:
        cost = calculate_cost(in_tok, out_tok, model_name, custom_pricing)
        return CostResult(
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost,
            model_name=model_name,
            pricing_source="parsed",
        )

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_token_count(text: str, pattern: str) -> Optional[int]:
    """Extract an integer token count from text using a regex pattern."""
    m = re.search(pattern, text)
    if m:
        return _parse_int(m.group(1))
    return None


def _parse_int(s: str) -> int:
    """Parse an integer, removing commas."""
    return int(s.replace(",", ""))
