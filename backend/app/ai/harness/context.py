"""Token-aware context planning for Contract Intelligence Harness v2.

The planner is deliberately provider-neutral.  It does not pretend that UTF-8 bytes
are tokens; instead it uses a conservative language-agnostic estimate with a safety
factor and keeps an explicit reserve for chat-template / multimodal overhead.  The
provider remains the final authority and receives the requested context window on
every call.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.ai.harness.document import Block


class ContextOverflow(ValueError):
    pass


class CallBudgetExhausted(Exception):
    """The model call budget was consumed; no further provider calls are allowed.

    Intentionally NOT a subclass of ContextOverflow or ValueError so that
    budget exhaustion can never be mislabelled as a prompt-size problem and so
    that call sites can handle it explicitly before generic error handlers.
    """


# A conservative fallback for unknown tokenizers.  For Latin-heavy legal text,
# modern subword tokenizers are commonly around 3-4 characters/token.  UTF-8 byte
# count is used only as a language-neutral size signal, then divided and padded by
# a safety factor.  This is intentionally conservative without the 3-4x inflation
# of the old one-byte-equals-one-token rule.
_TOKEN_BYTES_PER_TOKEN = 3.0
_TOKEN_SAFETY_FACTOR = 1.35
_BASE_PROMPT_RESERVE = 512


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-independent estimate used only for planning.

    It is *not* an accounting value.  Runtime provider usage remains authoritative.
    A fixed reserve is handled separately by :class:`ContextPlanner`.
    """
    if not text:
        return 0
    raw_bytes = len(text.encode("utf-8"))
    return max(1, math.ceil((raw_bytes / _TOKEN_BYTES_PER_TOKEN) * _TOKEN_SAFETY_FACTOR))


@dataclass
class ContextPlanner:
    configured: int
    advertised: int | None
    output_tokens: int
    decisions: list[dict] = field(default_factory=list)
    prompt_reserve: int = _BASE_PROMPT_RESERVE

    @property
    def capacity(self) -> int:
        configured = max(1024, int(self.configured or 0))
        advertised = int(self.advertised) if self.advertised else configured
        return max(1024, min(configured, advertised))

    @property
    def input_budget(self) -> int:
        # Never let output reservation consume the entire context window.  A broken
        # configuration should fail loudly instead of silently sending truncated text.
        budget = self.capacity - int(self.output_tokens or 0) - self.prompt_reserve
        if budget <= 0:
            raise ContextOverflow(
                f"Invalid context budget: capacity={self.capacity}, output={self.output_tokens}, "
                f"reserve={self.prompt_reserve}"
            )
        return budget

    def check(self, text: str, purpose: str, *, extra_reserve: int = 0) -> int:
        tokens = estimate_tokens(text)
        allowed = self.input_budget - max(0, int(extra_reserve))
        fits = tokens <= allowed
        self.decisions.append(
            {
                "purpose": purpose,
                "estimated_prompt_tokens": tokens,
                "input_budget": allowed,
                "fits": fits,
                "decision": "include" if fits else "abstain_overflow",
            }
        )
        if not fits:
            raise ContextOverflow(f"Context overflow for {purpose}: {tokens}/{allowed}")
        return tokens

    def fits(self, text: str, *, extra_reserve: int = 0) -> bool:
        return estimate_tokens(text) <= self.input_budget - max(0, int(extra_reserve))

    def segments(self, blocks: list[Block], overhead: str = "", *, purpose: str = "segmentation",
                 extra_reserve: int = 0, per_block_cost=None) -> list[list[Block]]:
        """Pack complete structural blocks without silent truncation.

        Oversized structural units are rejected explicitly; splitting a table/section
        without source-address remapping would weaken evidence guarantees.  Upstream
        document intelligence should already expose finer structural units when needed.
        `extra_reserve` carves out room for per-segment local context (visual and
        section readings) so the assembled segment prompt still fits the budget.
        `per_block_cost(block)` adds deterministic per-block variable context (e.g.
        the token cost of that block's visual observation row) so packing reflects
        the ACTUAL assembled prompt instead of a static magic reserve.
        """
        budget = self.input_budget - estimate_tokens(overhead) - max(0, int(extra_reserve))
        if budget <= 0:
            raise ContextOverflow(f"Prompt overhead exceeds context budget for {purpose}")

        segments: list[list[Block]] = []
        current: list[Block] = []
        size = 0
        for block in blocks:
            required = estimate_tokens(block.render()) + 4
            if per_block_cost is not None:
                required += max(0, int(per_block_cost(block) or 0))
            if required > budget:
                self.decisions.append(
                    {
                        "purpose": purpose,
                        "block": block.id,
                        "estimated_tokens": required,
                        "budget": budget,
                        "decision": "oversized_structural_unit",
                    }
                )
                raise ContextOverflow(f"Structural unit {block.id} exceeds budget; manual review")
            if current and size + required > budget:
                segments.append(current)
                current, size = [], 0
            current.append(block)
            size += required
        if current:
            segments.append(current)

        self.decisions.append(
            {
                "purpose": purpose,
                "segments": [[b.id for b in segment] for segment in segments],
                "decision": "full_document" if len(segments) <= 1 else "hierarchical",
                "block_budget": budget,
                "overhead_tokens": estimate_tokens(overhead),
                "extra_reserve": int(extra_reserve or 0),
                "per_block_cost": per_block_cost is not None,
            }
        )
        return segments

    def pack_ranked(self, blocks: list[Block], overhead: str = "", *, purpose: str,
                    extra_reserve: int = 0, per_block_cost=None) -> list[Block]:
        """Take ranked blocks until the current prompt budget is full.

        No block is cut.  The decision is recorded so retrieval is auditable.
        `extra_reserve` carves out room for the surrounding local context.
        `per_block_cost(block)` accounts for deterministic per-block variable
        context so the pack reflects the actual assembled prompt.
        """
        budget = self.input_budget - estimate_tokens(overhead) - max(0, int(extra_reserve))
        if budget <= 0:
            raise ContextOverflow(f"Prompt overhead exceeds context budget for {purpose}")
        chosen: list[Block] = []
        used = 0
        for block in blocks:
            required = estimate_tokens(block.render()) + 4
            if per_block_cost is not None:
                required += max(0, int(per_block_cost(block) or 0))
            if required > budget:
                continue
            if chosen and used + required > budget:
                continue
            chosen.append(block)
            used += required
        self.decisions.append(
            {
                "purpose": purpose,
                "retrieved_blocks": [b.id for b in chosen],
                "estimated_tokens": used,
                "budget": budget,
                "decision": "ranked_pack",
                "overhead_tokens": estimate_tokens(overhead),
                "extra_reserve": int(extra_reserve or 0),
                "per_block_cost": per_block_cost is not None,
            }
        )
        return chosen


def assemble(blocks: list[Block]) -> str:
    return "\n\n".join(block.render() for block in blocks)
