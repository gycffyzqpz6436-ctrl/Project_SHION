#!/usr/bin/env python3
"""Validate Project SHION JSONL dataset records without modifying inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_SCHEMA = Path("dataset/schemas/shion_dataset.schema.json")
DEFAULT_REJECTION_CODES = Path("dataset/schemas/rejection_reasons.md")
ID_PATTERN = re.compile(r"^shion_[0-9]{6}$")
REJECTION_CODE_PATTERN = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|")
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class Issue:
    severity: str
    file: str
    line: int
    id: str | None
    revision: int | None
    code: str
    message: str


@dataclass(frozen=True)
class Record:
    file: Path
    line: int
    data: dict[str, Any]

    @property
    def id(self) -> str | None:
        value = self.data.get("id")
        return value if isinstance(value, str) else None

    @property
    def revision(self) -> int | None:
        value = self.data.get("revision")
        return value if isinstance(value, int) and not isinstance(value, bool) else None


class EnvironmentFailure(Exception):
    """An argument, dependency, access, or runtime failure."""


def issue_for(
    record: Record | None,
    code: str,
    message: str,
    *,
    severity: str = "error",
    file: Path | None = None,
    line: int = 0,
) -> Issue:
    return Issue(
        severity=severity,
        file=str(record.file if record else file or ""),
        line=record.line if record else line,
        id=record.id if record else None,
        revision=record.revision if record else None,
        code=code,
        message=message,
    )


def expand_jsonl_paths(paths: Sequence[str], label: str) -> list[Path]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise EnvironmentFailure(f"{label} path does not exist: {path}")
        if path.is_dir():
            expanded.extend(sorted(item for item in path.rglob("*.jsonl") if item.is_file()))
        elif path.is_file() and path.suffix.lower() == ".jsonl":
            expanded.append(path)
        else:
            raise EnvironmentFailure(f"{label} must be a .jsonl file or directory: {path}")
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in expanded:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    if not unique:
        raise EnvironmentFailure(f"{label} contains no .jsonl files")
    return unique


def load_json_document(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvironmentFailure(f"{label} does not exist: {path}") from exc
    except UnicodeDecodeError as exc:
        raise EnvironmentFailure(f"{label} is not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise EnvironmentFailure(f"cannot read {label}: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EnvironmentFailure(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EnvironmentFailure(f"{label} must contain a JSON object: {path}")
    return value


def load_jsonschema_validator(schema_path: Path) -> Any:
    if os.environ.get("SHION_VALIDATOR_FORCE_MISSING_JSONSCHEMA") == "1":
        raise EnvironmentFailure(
            "jsonschema is required for Schema validation; install requirements-dev.txt"
        )
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
    except ImportError as exc:
        raise EnvironmentFailure(
            "jsonschema is required for Schema validation; install requirements-dev.txt"
        ) from exc

    schema = load_json_document(schema_path, "Schema")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise EnvironmentFailure(f"invalid JSON Schema: {schema_path}: {exc.message}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def load_rejection_codes(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise EnvironmentFailure(f"rejection-code file does not exist: {path}") from exc
    except UnicodeDecodeError as exc:
        raise EnvironmentFailure(f"rejection-code file is not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise EnvironmentFailure(f"cannot read rejection-code file: {path}: {exc}") from exc
    codes = {
        match.group(1)
        for line in lines
        if (match := REJECTION_CODE_PATTERN.match(line))
    }
    if not codes:
        raise EnvironmentFailure(f"no rejection reason codes found in: {path}")
    return codes


def read_jsonl(paths: Iterable[Path]) -> tuple[list[Record], list[Issue]]:
    records: list[Record] = []
    issues: list[Issue] = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8", newline=None) as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    text = raw_line.rstrip("\r\n")
                    if not text.strip():
                        issues.append(
                            issue_for(
                                None,
                                "E_EMPTY_LINE",
                                "JSONL contains an empty line",
                                file=path,
                                line=line_number,
                            )
                        )
                        continue
                    try:
                        value = json.loads(text)
                    except json.JSONDecodeError as exc:
                        issues.append(
                            issue_for(
                                None,
                                "E_JSON_SYNTAX",
                                f"invalid JSON: {exc.msg} at column {exc.colno}",
                                file=path,
                                line=line_number,
                            )
                        )
                        continue
                    if not isinstance(value, dict):
                        issues.append(
                            issue_for(
                                None,
                                "E_JSON_OBJECT",
                                "each JSONL line must contain one JSON object",
                                file=path,
                                line=line_number,
                            )
                        )
                        continue
                    records.append(Record(path, line_number, value))
        except UnicodeDecodeError as exc:
            issues.append(
                issue_for(
                    None,
                    "E_UTF8",
                    f"file is not valid UTF-8: {exc}",
                    file=path,
                )
            )
        except OSError as exc:
            raise EnvironmentFailure(f"cannot read input file: {path}: {exc}") from exc
    return records, issues


def format_schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "<record>"


def validate_schema(records: Iterable[Record], validator: Any) -> list[Issue]:
    issues: list[Issue] = []
    for record in records:
        errors = sorted(
            validator.iter_errors(record.data),
            key=lambda error: (list(error.absolute_path), error.message),
        )
        for error in errors:
            issues.append(
                issue_for(
                    record,
                    "E_SCHEMA",
                    f"{format_schema_path(error)}: {error.message}",
                )
            )
    return issues


def validate_messages(record: Record) -> list[Issue]:
    issues: list[Issue] = []
    messages = record.data.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return issues

    roles: list[Any] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        roles.append(role)
        if isinstance(content, str) and not content.strip():
            issues.append(
                issue_for(
                    record,
                    "E_EMPTY_MESSAGE",
                    f"messages[{index}].content must not be empty or whitespace-only",
                )
            )

    if roles and roles[0] != "user":
        issues.append(
            issue_for(
                record,
                "E_ROLE_FIRST",
                f"messages[0] must be user; found {roles[0]!r}",
            )
        )
    if roles and roles[-1] != "assistant":
        issues.append(
            issue_for(
                record,
                "E_ROLE_LAST",
                f"messages[{len(roles) - 1}] must be assistant; found {roles[-1]!r}",
            )
        )
    expected_roles = ("user", "assistant")
    for index, role in enumerate(roles):
        expected = expected_roles[index % 2]
        if role != expected:
            issues.append(
                issue_for(
                    record,
                    "E_ROLE_ORDER",
                    f"messages[{index}] must be {expected}; found {role!r}",
                )
            )
    return issues


def validate_status(record: Record, rejection_codes: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    status = record.data.get("status")
    quality = record.data.get("quality")
    review = record.data.get("review")
    if not isinstance(quality, dict) or not isinstance(review, dict):
        return issues

    reasons = review.get("rejection_reasons")
    if isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, str) and reason not in rejection_codes:
                issues.append(
                    issue_for(
                        record,
                        "E_REJECTION_REASON_UNKNOWN",
                        f"unknown rejection reason code: {reason}",
                    )
                )

    if status == "candidate":
        if review.get("owner_approved") is True:
            issues.append(
                issue_for(
                    record,
                    "E_CANDIDATE_APPROVAL",
                    "Candidate must not have owner_approved=true",
                )
            )
        contradictory = (
            review.get("result") is not None
            or review.get("reviewer") is not None
            or review.get("reviewed_at") is not None
            or bool(reasons)
            or any(
                quality.get(field) is not None
                for field in (
                    "character_consistency",
                    "naturalness",
                    "context_awareness",
                    "emotional_awareness",
                    "helpfulness",
                    "safety",
                )
            )
        )
        if contradictory:
            issues.append(
                issue_for(
                    record,
                    "E_CANDIDATE_REVIEW",
                    "unreviewed Candidate contains review results",
                )
            )

    if status == "golden":
        numeric_fields = (
            "character_consistency",
            "naturalness",
            "context_awareness",
            "emotional_awareness",
            "helpfulness",
        )
        missing = [field for field in numeric_fields if quality.get(field) is None]
        if missing:
            issues.append(
                issue_for(
                    record,
                    "E_GOLDEN_QUALITY",
                    f"Golden requires non-null quality values: {', '.join(missing)}",
                )
            )
        for field in ("character_consistency", "naturalness", "context_awareness"):
            value = quality.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value < 4:
                issues.append(
                    issue_for(
                        record,
                        "E_GOLDEN_QUALITY",
                        f"Golden requires {field} >= 4; found {value}",
                    )
                )
        if quality.get("safety") != "pass":
            issues.append(
                issue_for(record, "E_GOLDEN_SAFETY", "Golden requires safety=pass")
            )
        review_errors: list[str] = []
        if review.get("result") != "pass":
            review_errors.append("result must be pass")
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            review_errors.append("reviewer is required")
        if not isinstance(review.get("reviewed_at"), str) or not review["reviewed_at"].strip():
            review_errors.append("reviewed_at is required")
        if review.get("owner_approved") is not True:
            review_errors.append("owner_approved must be true")
        if reasons:
            review_errors.append("rejection_reasons must be empty")
        if review_errors:
            issues.append(
                issue_for(
                    record,
                    "E_GOLDEN_REVIEW",
                    "Golden review is incomplete: " + "; ".join(review_errors),
                )
            )

    if status == "rejected":
        if review.get("result") != "reject":
            issues.append(
                issue_for(
                    record,
                    "E_REJECTED_REVIEW",
                    "Rejected record requires review.result=reject",
                )
            )
        if not isinstance(reasons, list) or not reasons:
            issues.append(
                issue_for(
                    record,
                    "E_REJECTION_REASON_REQUIRED",
                    "Rejected record requires at least one rejection reason",
                )
            )
    return issues


def validate_ids_and_revisions(
    primary_records: Sequence[Record],
    lineage_records: Sequence[Record],
) -> list[Issue]:
    issues: list[Issue] = []
    primary_pairs: dict[tuple[str, int], Record] = {}
    history_pairs: dict[tuple[str, int], Record] = {}

    for record in lineage_records:
        if record.id is not None and record.revision is not None:
            history_pairs.setdefault((record.id, record.revision), record)

    for record in primary_records:
        if record.id is not None and not ID_PATTERN.fullmatch(record.id):
            issues.append(
                issue_for(
                    record,
                    "E_ID_FORMAT",
                    "id must match shion_ followed by six digits",
                )
            )
        if record.id is None or record.revision is None:
            continue
        pair = (record.id, record.revision)
        if pair in primary_pairs:
            issues.append(
                issue_for(
                    record,
                    "E_DUPLICATE_REVISION",
                    f"duplicate id and revision; first seen at "
                    f"{primary_pairs[pair].file}:{primary_pairs[pair].line}",
                )
            )
        else:
            primary_pairs[pair] = record
        history_pairs.setdefault(pair, record)

    ids = {record.id for record in primary_records if record.id is not None}
    for record_id in sorted(ids):
        revisions = sorted(
            revision for candidate_id, revision in history_pairs if candidate_id == record_id
        )
        if not revisions:
            continue
        expected = list(range(1, revisions[-1] + 1))
        if revisions != expected:
            primary = next(record for record in primary_records if record.id == record_id)
            issues.append(
                issue_for(
                    primary,
                    "E_REVISION_GAP",
                    f"revision history must be continuous from 1; found {revisions}",
                )
            )

    for record in primary_records:
        if record.id is None or record.revision is None:
            continue
        lineage = record.data.get("lineage")
        if not isinstance(lineage, dict):
            continue
        parent = lineage.get("parent_revision")
        if record.revision == 1:
            if parent is not None:
                issues.append(
                    issue_for(
                        record,
                        "E_PARENT_INVALID",
                        "revision 1 requires parent_revision=null",
                    )
                )
            continue
        if not isinstance(parent, int) or isinstance(parent, bool):
            issues.append(
                issue_for(
                    record,
                    "E_PARENT_MISSING",
                    "revision 2 or higher requires an integer parent_revision",
                )
            )
            continue
        if parent >= record.revision:
            issues.append(
                issue_for(
                    record,
                    "E_PARENT_INVALID",
                    "parent_revision must be lower than revision",
                )
            )
        if parent != record.revision - 1:
            issues.append(
                issue_for(
                    record,
                    "E_PARENT_SEQUENCE",
                    f"parent_revision must equal revision - 1; expected "
                    f"{record.revision - 1}, found {parent}",
                )
            )
        if (record.id, parent) not in history_pairs:
            issues.append(
                issue_for(
                    record,
                    "E_PARENT_NOT_FOUND",
                    f"parent revision {parent} was not found in inputs or lineage sources",
                )
            )
    return issues


def normalized_text(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", value.replace("\r\n", "\n").replace("\r", "\n").strip())


def message_fingerprint(record: Record) -> str | None:
    messages = record.data.get("messages")
    if not isinstance(messages, list):
        return None
    normalized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            return None
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            return None
        normalized.append({"role": role, "content": normalized_text(content)})
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scenario_summary(record: Record) -> str | None:
    scenario = record.data.get("scenario")
    if not isinstance(scenario, dict):
        return None
    summary = scenario.get("summary")
    return normalized_text(summary) if isinstance(summary, str) else None


def validate_evaluation_isolation(
    golden_records: Sequence[Record],
    evaluation_records: Sequence[Record],
) -> list[Issue]:
    issues: list[Issue] = []
    golden_pairs = {
        (record.id, record.revision): record
        for record in golden_records
        if record.id is not None and record.revision is not None
    }
    golden_fingerprints = {
        fingerprint: record
        for record in golden_records
        if (fingerprint := message_fingerprint(record)) is not None
    }
    golden_summaries = {
        summary: record
        for record in golden_records
        if (summary := scenario_summary(record))
    }

    for record in evaluation_records:
        pair = (record.id, record.revision)
        if pair in golden_pairs:
            issues.append(
                issue_for(
                    record,
                    "E_GOLDEN_EVALUATION_ID_OVERLAP",
                    f"id and revision also exist in Golden: {record.id} r{record.revision}",
                )
            )
        fingerprint = message_fingerprint(record)
        if fingerprint is not None and fingerprint in golden_fingerprints:
            source = golden_fingerprints[fingerprint]
            issues.append(
                issue_for(
                    record,
                    "E_GOLDEN_EVALUATION_CONTENT_OVERLAP",
                    f"normalized messages duplicate Golden record "
                    f"{source.id} r{source.revision}",
                )
            )
        summary = scenario_summary(record)
        if (
            summary
            and summary in golden_summaries
            and fingerprint not in golden_fingerprints
        ):
            source = golden_summaries[summary]
            issues.append(
                issue_for(
                    record,
                    "W_SIMILAR_SCENARIO",
                    f"normalized scenario summary matches Golden record "
                    f"{source.id} r{source.revision}; review for semantic overlap",
                    severity="warning",
                )
            )
    return issues


def validate_record_set(
    records: Sequence[Record],
    lineage_records: Sequence[Record],
    validator: Any,
    rejection_codes: set[str],
) -> list[Issue]:
    issues = validate_schema(records, validator)
    for record in records:
        issues.extend(validate_messages(record))
        issues.extend(validate_status(record, rejection_codes))
    issues.extend(validate_ids_and_revisions(records, lineage_records))
    return issues


def render_issue(issue: Issue, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(asdict(issue), ensure_ascii=False, sort_keys=True)
    identity = (
        f"[{issue.id or '-'} r{issue.revision if issue.revision is not None else '-'}]"
    )
    return (
        f"{issue.file}:{issue.line} {identity} {issue.code}: "
        f"{issue.message}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Project SHION JSONL dataset records."
    )
    parser.add_argument("files", nargs="+", help=".jsonl files or directories")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--rejection-codes", default=str(DEFAULT_REJECTION_CODES))
    parser.add_argument("--golden", nargs="+", default=[])
    parser.add_argument("--evaluation", nargs="+", default=[])
    parser.add_argument("--lineage-source", nargs="+", default=[])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    return parser


def run(args: argparse.Namespace) -> tuple[list[Issue], int]:
    validator = load_jsonschema_validator(Path(args.schema))
    rejection_codes = load_rejection_codes(Path(args.rejection_codes))

    input_paths = expand_jsonl_paths(args.files, "input")
    lineage_paths = (
        expand_jsonl_paths(args.lineage_source, "lineage source")
        if args.lineage_source
        else []
    )
    golden_paths = (
        expand_jsonl_paths(args.golden, "Golden input") if args.golden else []
    )
    evaluation_paths = (
        expand_jsonl_paths(args.evaluation, "Evaluation input")
        if args.evaluation
        else []
    )

    records, issues = read_jsonl(input_paths)
    lineage_records, lineage_issues = read_jsonl(lineage_paths)
    golden_records, golden_issues = read_jsonl(golden_paths)
    evaluation_records, evaluation_issues = read_jsonl(evaluation_paths)
    issues.extend(lineage_issues)
    issues.extend(golden_issues)
    issues.extend(evaluation_issues)

    issues.extend(validate_record_set(records, lineage_records, validator, rejection_codes))
    if lineage_records:
        issues.extend(validate_schema(lineage_records, validator))
    if golden_records:
        issues.extend(
            validate_record_set(golden_records, [], validator, rejection_codes)
        )
    if evaluation_records:
        issues.extend(
            validate_record_set(evaluation_records, [], validator, rejection_codes)
        )
    if golden_records and evaluation_records:
        issues.extend(validate_evaluation_isolation(golden_records, evaluation_records))

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    exit_code = 1 if error_count or (args.strict and warning_count) else 0
    return issues, exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        issues, exit_code = run(args)
        for issue in issues:
            print(render_issue(issue, args.format), file=sys.stderr)
        error_count = sum(issue.severity == "error" for issue in issues)
        warning_count = sum(issue.severity == "warning" for issue in issues)
        if args.format == "json":
            print(
                json.dumps(
                    {"summary": {"errors": error_count, "warnings": warning_count}},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        else:
            print(
                f"Validation complete: {error_count} error(s), "
                f"{warning_count} warning(s)",
                file=sys.stderr,
            )
        return exit_code
    except EnvironmentFailure as exc:
        print(f"E_ENVIRONMENT: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("E_ENVIRONMENT: validation interrupted", file=sys.stderr)
        return 2
    except Exception as exc:  # Defensive CLI boundary.
        print(f"E_INTERNAL: unexpected validator failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
