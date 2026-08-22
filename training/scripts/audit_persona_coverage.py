"""Read-only, deterministic Persona Coverage Audit for SHION Golden records."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "dataset" / "golden"
DATABASE_PATH = ROOT / "dataset" / "database" / "shion_database.jsonl"
ID_RE = re.compile(r"shion_(\d{6})$")
ASSISTANT_BIAS = {
    "何かお手伝い": r"何か.{0,8}お手伝い",
    "お手伝いできます": r"お手伝い(?:が)?できます",
    "何かできること": r"何か.{0,5}できること",
    "何か私にできる": r"何か.{0,5}私にできる",
    "遠慮なく": r"遠慮なく",
    "お申し付け": r"お申し付け",
    "ご質問": r"ご質問",
    "ご相談": r"ご相談",
    "サポート": r"サポート",
    "お役に立て": r"お役に立て",
    "いかがでしょうか": r"いかがでしょうか",
    "してみてください": r"してみてください",
    "おすすめします": r"(?:することを)?おすすめします",
}
TEASING = re.compile(r"へぇ|しょうがない|甘えんぼ|また.+[〜~]|ほんと.+らしい|見抜|ばれ|あはは|なんてね|からか|ちょっと.+じゃん|欲張|さぼ|油断|うっかり|ちゃっかり")
AFFECTION = re.compile(r"甘やか|♡|ぎゅ|撫で|なで|よしよし|そばに|ここにい|一緒にい|大事|特別")
COMFORT = re.compile(r"休ん|休も|無理し|落ち着|そっか|つら|しんど|疲れ|大丈夫|ここにい|話して|聞くよ")
ENCOURAGE = re.compile(r"頑張|できる|いける|応援|一歩|進め|えら|見直した|ちゃんと.+じゃん")
EMPATHY = re.compile(r"そっか|それは|つらかった|しんどかった|悔しい|怖かった|疲れた|気持ち|わかる")
HUMOR = re.compile(r"あはは|ふふ|笑|なんてね|冗談|ぷっ")
PLAYFUL = re.compile(r"へぇ[〜~]?|いいじゃん|採用[〜~]?|ほらね|しょうがない|あはは|ふふ|♪|♡|[〜~][？?]")
CARE = re.compile(r"気をつけ|忘れない|確認し|休ん|無理し|心配|ちゃんと|先に|しておいで|見てあげ")
CASUAL_END = re.compile(r"(?:だよ|だね|じゃん|でしょ|かな|かも|しよ|してね|してよ|なの|なんだ|だって)[〜~♪♡。！？!?]*$")
POLITE = re.compile(r"(?:です|ます|ください|でしょう|ございます)(?:[。！？!?]|$)")
STRONG_POLITE = re.compile(r"(?:いたします|くださいませ|申し上げ|ございます|でしょうか|お勧めします)")
TECHNICAL_CATEGORIES = {"technical_support"}
SERIOUS_CATEGORIES = {"serious_support"}
SAFETY_CATEGORIES = {"safety_and_boundary"}
CASUAL_CATEGORIES = {"daily_conversation", "daily_routine", "work_or_study_fatigue", "achievement_report", "light_teasing", "unexpected_input"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_golden(directory: Path = GOLDEN_DIR) -> list[dict]:
    records = [record for path in sorted(directory.glob("*.jsonl")) for record in load_jsonl(path)]
    records = [record for record in records if 101 <= int(ID_RE.fullmatch(record["id"]).group(1)) <= 300]
    records.sort(key=lambda record: record["id"])
    if len(records) != 200 or [record["id"] for record in records] != [f"shion_{index:06d}" for index in range(101, 301)]:
        raise ValueError("Golden audit requires exactly shion_000101 through shion_000300")
    return records


def assistant_turns(record: dict) -> list[str]:
    return [message["content"] for message in record["messages"] if message["role"] == "assistant"]


def assistant_text(record: dict) -> str:
    return "\n".join(assistant_turns(record))


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def style_class(text: str) -> str:
    polite = len(POLITE.findall(text))
    strong = len(STRONG_POLITE.findall(text))
    casual = len(re.findall(r"(?:だよ|だね|じゃん|でしょ|かな|かも|〜|♪|♡|ふふ|へぇ)", text))
    if strong >= 2 or (polite >= 5 and casual == 0):
        return "Strongly polite"
    if polite >= 2 and casual == 0:
        return "Polite"
    if polite and casual:
        return "Mixed"
    return "Casual"


def sentence_count(text: str) -> int:
    chunks = [item for item in re.split(r"[。！？!?]+|\n+", text) if item.strip()]
    return max(1, len(chunks))


def normalized_ending(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    ending = re.sub(r"[。！？!?♪♡〜~…]+$", "", lines[-1]).strip()
    ending = re.sub(r"^(?:だから|じゃあ|ほら、?|うん、?)", "", ending).strip()
    return ending[-24:]


def flags(record: dict) -> dict[str, bool]:
    text = assistant_text(record)
    category = record["category"]
    serious = category in SERIOUS_CATEGORIES or record["scenario"]["seriousness"] == "serious"
    safety = category in SAFETY_CATEGORIES or record["scenario"]["seriousness"] == "safety_sensitive"
    technical = category in TECHNICAL_CATEGORIES
    teasing = bool(TEASING.search(text))
    affection = bool(AFFECTION.search(text))
    comfort = bool(COMFORT.search(text))
    empathy = bool(EMPATHY.search(text))
    return {
        "address": "お兄さん" in text,
        "teasing": teasing,
        "pampering": bool(re.search(r"甘やか|よしよし|ぎゅ|撫で|なで|今日は.+していい|休んでいい", text)),
        "kindness": bool(COMFORT.search(text) or CARE.search(text) or AFFECTION.search(text)),
        "intimate_chat": bool(category in {"relationship_and_memory_boundary", "daily_conversation"} and (AFFECTION.search(text) or "お兄さん" in text or "♡" in text)),
        "daily_conversation": category in CASUAL_CATEGORIES,
        "encouragement": bool(ENCOURAGE.search(text)),
        "empathy": empathy,
        "comforting": comfort,
        "affectionate": affection,
        "physical_affection": bool(re.search(r"ぎゅ|撫で|なで|抱き|膝枕", text)),
        "emotional_closeness": bool(affection or "お兄さん" in text or re.search(r"そばに|ここにい|私に話して", text)),
        "humor": bool(HUMOR.search(text)),
        "playful_response": bool(PLAYFUL.search(text)),
        "caretaking": bool(CARE.search(text)),
        "coolness": bool(re.search(r"落ち着|まず|順番|冷静|切り分け|焦ら", text)),
        "intelligence": technical or category == "decision_and_organization" or bool(re.search(r"原因|確認|比較|仕組み|整理", text)),
        "technical_help": technical,
        "serious": serious,
        "safety": safety,
        "boundary": category in {"relationship_and_memory_boundary", "safety_and_boundary"},
    }


def persona_density(record: dict, item_flags: dict[str, bool]) -> int:
    text = assistant_text(record)
    # Per Canonical, address/symbols/signature phrases cannot make generic prose pass.
    # Score semantic behavior: contextual teasing, relationship/perspective, care,
    # affection, humor, empathy, and spoken rhythm. Address and ♪/♡ are audited separately.
    markers = sum((
        item_flags["teasing"], item_flags["affectionate"], item_flags["humor"],
        item_flags["caretaking"], item_flags["empathy"],
        bool(re.search(r"私(?:も|は|が|なら)|一緒に|見てあげ|聞いてあげ|私に", text)),
        bool(CASUAL_END.search(text.strip())),
    ))
    generic = any(re.search(pattern, text) for pattern in ASSISTANT_BIAS.values())
    # Metadata supplies context intent; content markers supply realized voice. Neither is sufficient alone.
    if markers == 0 or (generic and markers <= 1):
        return 0
    if markers <= 2:
        return 1
    if markers <= 4:
        return 2
    return 3


def address_positions(turn: str) -> Counter:
    result = Counter()
    for match in re.finditer("お兄さん", turn):
        prefix, suffix = turn[:match.start()], turn[match.end():]
        if not prefix.strip(" \n　、。！？!?…〜~♪♡"):
            result["start"] += 1
        elif not suffix.strip(" \n　、。！？!?…〜~♪♡"):
            result["end"] += 1
        else:
            result["middle"] += 1
    return result


def audit(records: list[dict], database_path: Path = DATABASE_PATH) -> dict:
    database = load_jsonl(database_path)
    database_index = defaultdict(list)
    for revision in database:
        database_index[revision["id"]].append(revision)
    lineage_ok = all(any(item["revision"] == record["revision"] and item["status"] == "golden"
                            for item in database_index[record["id"]]) for record in records)

    per_record = []
    phrase_hits = defaultdict(list)
    address = Counter()
    ending_ids = defaultdict(list)
    all_turn_lengths = []
    record_lengths = []
    sentence_buckets = Counter()
    turn_sentence_buckets = Counter()
    markdown = Counter()
    action_endings = defaultdict(list)
    symbol_counts = Counter()
    polite_counts = Counter()
    category_counts = Counter(record["category"] for record in records)
    element_counts = Counter()
    style_counts = Counter()

    for record in records:
        text = assistant_text(record)
        turns = assistant_turns(record)
        item_flags = flags(record)
        density = persona_density(record, item_flags)
        for key, value in item_flags.items():
            if value:
                element_counts[key] += 1
        style_counts[style_class(text)] += 1
        for marker in ("です", "ます", "ください", "でしょう", "ございます"):
            polite_counts[marker] += text.count(marker)
        occurrences = text.count("お兄さん")
        if occurrences:
            address["records"] += 1
            address["occurrences"] += occurrences
            if occurrences > 1:
                address["multiple_records"] += 1
            for turn in turns:
                address.update(address_positions(turn))
            for context in ("daily_conversation", "technical_help", "serious", "safety"):
                if item_flags[context]:
                    address[context] += 1
        for label, pattern in ASSISTANT_BIAS.items():
            if re.search(pattern, text):
                phrase_hits[label].append(record["id"])
        length = len(text)
        record_lengths.append(length)
        all_turn_lengths.extend(map(len, turns))
        sentences = sentence_count(text)
        sentence_buckets["1 sentence" if sentences == 1 else "2 sentences" if sentences == 2 else "3 sentences" if sentences == 3 else "long (4+)"] += 1
        for turn in turns:
            turn_sentences = sentence_count(turn)
            turn_sentence_buckets[
                "1 sentence" if turn_sentences == 1 else "2 sentences" if turn_sentences == 2
                else "3 sentences" if turn_sentences == 3 else "long (4+)"
            ] += 1
        markdown["bullet list"] += int(bool(re.search(r"(?m)^\s*[-*+]\s+", text)))
        markdown["numbered list"] += int(bool(re.search(r"(?m)^\s*\d+[.)]\s+", text)))
        markdown["heading"] += int(bool(re.search(r"(?m)^#{1,6}\s+", text)))
        markdown["code block"] += int("```" in text)
        markdown["bold"] += int("**" in text)
        for symbol in ("。", "！", "？", "♪", "〜", "…", "笑", "ふふ", "ね", "よ", "かな", "でしょ", "だよ"):
            symbol_counts[symbol] += text.count(symbol)
        ending = normalized_ending(text)
        ending_ids[ending].append(record["id"])
        action_match = re.search(
            r"(教えて|報告して|見せて|やってみて|しておいで|しよっか|してみて)[^\n。！？]*[。！？♪♡〜~]*$",
            text.strip(),
        )
        if action_match:
            action_endings[action_match.group(1)].append(record["id"])
        per_record.append({
            "id": record["id"], "category": record["category"], "summary": record["scenario"]["summary"],
            "chars": length, "sentences": sentences, "style": style_class(text), "density": density,
            "flags": item_flags, "ending": ending,
        })

    density_counts = Counter(item["density"] for item in per_record)
    technical = [item for item in per_record if item["flags"]["technical_help"]]
    serious = [item for item in per_record if item["flags"]["serious"]]
    safety = [item for item in per_record if item["flags"]["safety"]]
    persona_maintained = lambda item: item["density"] >= 2
    top = sorted(per_record, key=lambda item: (-item["density"], -sum(item["flags"].values()), item["id"]))
    weak = sorted(per_record, key=lambda item: (item["density"], sum(item["flags"].values()), -item["chars"], item["id"]))
    harmful = [item for item in weak if item["density"] <= 1 or item["style"] in {"Polite", "Strongly polite"}]
    repeated_endings = sorted(
        ({"ending": ending, "count": len(ids), "ids": ids} for ending, ids in ending_ids.items() if ending),
        key=lambda item: (-item["count"], item["ending"]),
    )[:20]
    return {
        "schema_version": 1,
        "record_count": len(records),
        "id_range": [records[0]["id"], records[-1]["id"]],
        "database_lineage_match": lineage_ok,
        "category_counts": dict(category_counts),
        "persona_elements": dict(element_counts),
        "address": dict(address),
        "assistant_bias": {label: {"count": len(ids), "ids": ids} for label, ids in phrase_hits.items()},
        "assistant_bias_record_count": len({record_id for ids in phrase_hits.values() for record_id in ids}),
        "style_distribution": dict(style_counts),
        "polite_marker_counts": dict(polite_counts),
        "record_characters": {
            "min": min(record_lengths), "median": statistics.median(record_lengths),
            "average": round(statistics.mean(record_lengths), 2), "p75": percentile(record_lengths, .75),
            "p90": percentile(record_lengths, .90), "max": max(record_lengths),
        },
        "assistant_turn_characters": {
            "min": min(all_turn_lengths), "median": statistics.median(all_turn_lengths),
            "average": round(statistics.mean(all_turn_lengths), 2), "p75": percentile(all_turn_lengths, .75),
            "p90": percentile(all_turn_lengths, .90), "max": max(all_turn_lengths),
        },
        "sentence_buckets": dict(sentence_buckets),
        "assistant_turn_sentence_buckets": dict(turn_sentence_buckets),
        "markdown_usage": dict(markdown),
        "style_marker_counts": dict(symbol_counts),
        "density_distribution": {str(score): density_counts[score] for score in range(4)},
        "technical_persona_maintained": sum(map(persona_maintained, technical)),
        "technical_count": len(technical),
        "short_casual_count": sum(
            record["category"] in CASUAL_CATEGORIES
            and "single_turn" in record["tags"]
            and record["scenario"]["response_length"] == "short"
            for record in records
        ),
        "serious_persona_maintained": sum(map(persona_maintained, serious)),
        "serious_count": len(serious),
        "safety_persona_maintained": sum(map(persona_maintained, safety)),
        "safety_count": len(safety),
        "top_strong": [item["id"] for item in top[:20]],
        "top_weak": [item["id"] for item in weak[:20]],
        "potentially_harmful": [item["id"] for item in harmful[:20]],
        "repeated_endings": repeated_endings,
        "action_endings": {label: {"count": len(ids), "ids": ids} for label, ids in action_endings.items()},
        "action_ending_record_count": sum(len(ids) for ids in action_endings.values()),
        "records": per_record,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-dir", type=Path, default=GOLDEN_DIR)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = audit(load_golden(args.golden_dir), args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
