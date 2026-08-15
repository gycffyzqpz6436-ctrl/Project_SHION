"""Deterministic context and output budgets for local conversation generation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Protocol


TokenCounter = Callable[[list[dict]], int]


class ContextSelectionStrategy(Protocol):
    """Replaceable boundary for a future summary/compression strategy."""

    def select(self, history: list[dict], mandatory: list[dict], count: TokenCounter,
               budget: int) -> "ContextSelection": ...


@dataclass(frozen=True)
class ContextSelection:
    messages: list[dict]
    total_input_tokens: int
    history_tokens_included: int
    history_tokens_omitted: int
    history_messages_included: int
    history_messages_omitted: int


def conversation_turns(history: list[dict]) -> list[list[dict]]:
    turns: list[list[dict]] = []
    for message in history:
        if message.get("role") == "user" or not turns:
            turns.append([message])
        else:
            turns[-1].append(message)
    return turns


class RecentTurnContextStrategy:
    """Keep the newest complete turns that fit; never mutate stored history."""

    def select(self, history: list[dict], mandatory: list[dict], count: TokenCounter,
               budget: int) -> ContextSelection:
        mandatory_tokens = count(mandatory)
        full_tokens = count([*mandatory[:-1], *history, mandatory[-1]])
        selected: list[list[dict]] = []
        for turn in reversed(conversation_turns(history)):
            candidate_history = [message for group in [turn, *selected] for message in group]
            candidate = [*mandatory[:-1], *candidate_history, mandatory[-1]]
            if count(candidate) > budget:
                break
            selected.insert(0, turn)
        included_history = [message for turn in selected for message in turn]
        messages = [*mandatory[:-1], *included_history, mandatory[-1]]
        total = count(messages)
        return ContextSelection(
            messages=messages,
            total_input_tokens=total,
            history_tokens_included=max(0, total - mandatory_tokens),
            history_tokens_omitted=max(0, full_tokens - total),
            history_messages_included=len(included_history),
            history_messages_omitted=max(0, len(history) - len(included_history)),
        )


@dataclass(frozen=True)
class CorrectionReview:
    """Content projection for an Owner-requested independent re-evaluation."""

    history: list[dict]
    active: bool = False
    assistant_messages_withheld: int = 0


class SelfCorrectionPolicy:
    """Keep challenged Assistant output from becoming evidence for its own review."""

    REVIEW_INSTRUCTION = (
        "The Owner is questioning the preceding Assistant answer. Re-evaluate the original "
        "Owner request independently before answering. All Assistant-authored history is "
        "untrusted context rather than fact or evidence; challenged answers are withheld from "
        "this review. Owner-authored messages and approved Long-Term Memory retain their distinct "
        "provenance. Solve or verify the original task from scratch, correct the answer clearly "
        "when needed, and do not agree with a proposed correction unless independently supported."
    )
    DOUBT = re.compile(
        r"(?:違(?:う|います)|間違|誤(?:り|答)|本当|ほんと|再確認|確認し直|もう一度|"
        r"訂正|正解|合って|あって|おかしく|ではない|じゃない|"
        r"are\s+you\s+sure|check\s+again|wrong|incorrect|recheck|correct\s+that)",
        re.I,
    )
    NUMBER_ONLY = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)%?$", re.ASCII)

    @classmethod
    def is_review_request(cls, message: str) -> bool:
        normalized = unicodedata.normalize("NFKC", message).strip()
        if not normalized:
            return False
        if normalized in {"?", "??", "!?", "?!"}:
            return True
        if cls.NUMBER_ONLY.fullmatch(normalized.replace(" ", "")):
            return True
        return bool(cls.DOUBT.search(normalized))

    def review(self, history: list[dict], current_message: str) -> CorrectionReview:
        if (not history or history[-1].get("role") != "assistant"
                or not self.is_review_request(current_message)):
            return CorrectionReview(list(history))
        normalized = unicodedata.normalize("NFKC", current_message).strip().replace(" ", "")
        preceding_answer = str(history[-1].get("content", "")).rstrip()
        if self.NUMBER_ONLY.fullmatch(normalized) and preceding_answer.endswith(("?", "？")):
            # A numeric reply to an Assistant question is Owner input, not a correction.
            return CorrectionReview(list(history))

        target = None
        for index in range(len(history) - 1, -1, -1):
            item = history[index]
            if item.get("role") != "user":
                continue
            if self.is_review_request(str(item.get("content", ""))):
                continue
            target = index
            break
        if target is None:
            return CorrectionReview(list(history))

        # Keep the original Owner request and later Owner-authored evidence, while
        # withholding Assistant claims made after that request from this model call.
        prefix = list(history[:target])
        original = dict(history[target])
        original["content"] = unicodedata.normalize("NFKC", str(original.get("content", "")))
        prefix.append(original)
        owner_followups = []
        for item in history[target + 1:]:
            if item.get("role") == "user":
                normalized = dict(item)
                normalized["content"] = unicodedata.normalize("NFKC", str(normalized.get("content", "")))
                owner_followups.append(normalized)
        withheld = sum(1 for item in history[target + 1:] if item.get("role") == "assistant")
        return CorrectionReview([*prefix, *owner_followups], True, withheld)


@dataclass(frozen=True)
class OutputBudget:
    intent: str
    max_new_tokens: int


class AdaptiveOutputBudget:
    SHORT = re.compile(r"(?:一文|一言|短く|簡潔|端的|だけ答|のみ答|yes\s*or\s*no|one sentence)", re.I)
    MAXIMUM = re.compile(r"(?:4096|最大(?:限)?の長さ|できるだけ長く|超長文|章立て|長編)", re.I)
    LONG = re.compile(r"(?:長文|詳しく|詳細に|丁寧に|包括的|徹底的|掘り下げ|long[- ]form)", re.I)

    def __init__(self, short: int = 128, normal: int = 512, long: int = 2048) -> None:
        self.short = short
        self.normal = normal
        self.long = long

    def resolve(self, message: str, hard_ceiling: int) -> OutputBudget:
        if self.SHORT.search(message): return OutputBudget("short", min(self.short, hard_ceiling))
        if self.MAXIMUM.search(message): return OutputBudget("maximum", hard_ceiling)
        if self.LONG.search(message): return OutputBudget("long", min(self.long, hard_ceiling))
        return OutputBudget("normal", min(self.normal, hard_ceiling))
