"""Deterministic context and output budgets for local conversation generation."""

from __future__ import annotations

import re
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
