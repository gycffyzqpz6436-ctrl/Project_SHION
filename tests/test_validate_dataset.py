"""Tests for the Project SHION dataset Validator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_dataset.py"
FIXTURES = ROOT / "tests" / "fixtures" / "dataset_validator"
SCHEMA = ROOT / "dataset" / "schemas" / "shion_dataset.schema.json"
REJECTION_CODES = ROOT / "dataset" / "schemas" / "rejection_reasons.md"


class DatasetValidatorTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_directory.name)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def fixture_copy(self, relative_path: str) -> Path:
        source = FIXTURES / relative_path
        destination = self.temp_path / Path(relative_path).name
        text = source.read_text(encoding="utf-8")
        destination.write_text(
            text.replace("fixture_shion_", "shion_"),
            encoding="utf-8",
            newline="\n",
        )
        return destination

    def run_validator(
        self,
        *arguments: str | Path,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(VALIDATOR),
            *[str(argument) for argument in arguments],
            "--schema",
            str(SCHEMA),
            "--rejection-codes",
            str(REJECTION_CODES),
        ]
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        return subprocess.run(
            command,
            cwd=ROOT,
            env=process_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_valid_candidate_returns_zero(self) -> None:
        result = self.run_validator(self.fixture_copy("valid_candidate.jsonl"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_golden_returns_zero(self) -> None:
        result = self.run_validator(self.fixture_copy("valid_golden.jsonl"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_rejected_returns_zero(self) -> None:
        result = self.run_validator(self.fixture_copy("valid_rejected.jsonl"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_fixtures_return_one_and_expected_code(self) -> None:
        cases = {
            "invalid_empty_line.jsonl": "E_EMPTY_LINE",
            "invalid_role_order.jsonl": "E_ROLE_ORDER",
            "invalid_id.jsonl": "E_ID_FORMAT",
            "invalid_revision.jsonl": "E_REVISION_GAP",
            "invalid_golden_quality.jsonl": "E_GOLDEN_QUALITY",
            "invalid_rejected_without_reason.jsonl": "E_REJECTION_REASON_REQUIRED",
            "invalid_unknown_rejection_reason.jsonl": "E_REJECTION_REASON_UNKNOWN",
            "invalid_json_syntax.jsonl": "E_JSON_SYNTAX",
            "invalid_empty_message.jsonl": "E_EMPTY_MESSAGE",
            "invalid_candidate_approval.jsonl": "E_CANDIDATE_APPROVAL",
        }
        for fixture, code in cases.items():
            with self.subTest(fixture=fixture):
                result = self.run_validator(self.fixture_copy(fixture))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(code, result.stderr)

    def test_missing_file_returns_two(self) -> None:
        result = self.run_validator(self.temp_path / "missing.jsonl")
        self.assertEqual(result.returncode, 2)
        self.assertIn("E_ENVIRONMENT", result.stderr)

    def test_missing_dependency_returns_two(self) -> None:
        result = self.run_validator(
            self.fixture_copy("valid_candidate.jsonl"),
            env={"SHION_VALIDATOR_FORCE_MISSING_JSONSCHEMA": "1"},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("jsonschema is required", result.stderr)

    def test_text_error_contains_required_context(self) -> None:
        fixture = self.fixture_copy("invalid_candidate_approval.jsonl")
        result = self.run_validator(fixture)
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(fixture), result.stderr)
        self.assertIn(":1 [shion_000013 r1]", result.stderr)
        self.assertIn("E_CANDIDATE_APPROVAL", result.stderr)
        self.assertIn("Candidate must not", result.stderr)

    def test_json_error_contains_required_fields(self) -> None:
        fixture = self.fixture_copy("invalid_candidate_approval.jsonl")
        result = self.run_validator(fixture, "--format", "json")
        self.assertEqual(result.returncode, 1)
        payloads = [json.loads(line) for line in result.stderr.splitlines()]
        error = next(payload for payload in payloads if "severity" in payload)
        self.assertEqual(error["severity"], "error")
        self.assertEqual(error["file"], str(fixture))
        self.assertEqual(error["line"], 1)
        self.assertEqual(error["id"], "shion_000013")
        self.assertEqual(error["revision"], 1)
        self.assertEqual(error["code"], "E_CANDIDATE_APPROVAL")
        self.assertTrue(error["message"])

    def test_input_file_is_not_modified(self) -> None:
        fixture = self.fixture_copy("valid_candidate.jsonl")
        before = self.digest(fixture)
        result = self.run_validator(fixture)
        after = self.digest(fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)

    def test_candidate_with_quality_scores_is_review_contradiction(self) -> None:
        data = json.loads(
            self.fixture_copy("valid_candidate.jsonl").read_text(encoding="utf-8")
        )
        data["quality"]["naturalness"] = 4
        fixture = self.temp_path / "candidate_with_score.jsonl"
        fixture.write_text(
            json.dumps(data, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        result = self.run_validator(fixture)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("E_CANDIDATE_REVIEW", result.stderr)

    def test_golden_evaluation_overlap_returns_one(self) -> None:
        golden = self.fixture_copy("duplicate_golden_evaluation/golden.jsonl")
        evaluation_source = FIXTURES / "duplicate_golden_evaluation" / "evaluation.jsonl"
        evaluation = self.temp_path / "evaluation.jsonl"
        evaluation.write_text(
            evaluation_source.read_text(encoding="utf-8").replace(
                "fixture_shion_", "shion_"
            ),
            encoding="utf-8",
            newline="\n",
        )
        primary = self.fixture_copy("valid_candidate.jsonl")
        result = self.run_validator(
            primary,
            "--golden",
            golden,
            "--evaluation",
            evaluation,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("E_GOLDEN_EVALUATION_ID_OVERLAP", result.stderr)
        self.assertIn("E_GOLDEN_EVALUATION_CONTENT_OVERLAP", result.stderr)

    def test_warning_returns_zero_and_strict_returns_one(self) -> None:
        golden_data = json.loads(
            self.fixture_copy("valid_golden.jsonl").read_text(encoding="utf-8")
        )
        evaluation_data = dict(golden_data)
        evaluation_data["id"] = "shion_000099"
        evaluation_data["status"] = "evaluation"
        evaluation_data["messages"] = [
            {"role": "user", "content": "DISTINCT FIXTURE USER"},
            {"role": "assistant", "content": "DISTINCT FIXTURE ASSISTANT"},
        ]
        evaluation_data["review"] = dict(evaluation_data["review"])
        evaluation_data["review"]["owner_approved"] = False
        golden = self.temp_path / "warning_golden.jsonl"
        evaluation = self.temp_path / "warning_evaluation.jsonl"
        golden.write_text(
            json.dumps(golden_data, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        evaluation.write_text(
            json.dumps(evaluation_data, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        primary = self.fixture_copy("valid_candidate.jsonl")

        normal = self.run_validator(
            primary, "--golden", golden, "--evaluation", evaluation
        )
        strict = self.run_validator(
            primary, "--golden", golden, "--evaluation", evaluation, "--strict"
        )
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertIn("W_SIMILAR_SCENARIO", normal.stderr)
        self.assertEqual(strict.returncode, 1, strict.stderr)

    def test_lineage_source_resolves_parent(self) -> None:
        revision_one = json.loads(
            self.fixture_copy("valid_candidate.jsonl").read_text(encoding="utf-8")
        )
        revision_two = json.loads(json.dumps(revision_one))
        revision_two["revision"] = 2
        revision_two["lineage"] = {
            "parent_revision": 1,
            "edited_by_human": True,
            "change_summary": "fixture revision",
        }
        lineage = self.temp_path / "lineage.jsonl"
        current = self.temp_path / "current.jsonl"
        lineage.write_text(
            json.dumps(revision_one, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        current.write_text(
            json.dumps(revision_two, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        result = self.run_validator(current, "--lineage-source", lineage)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fixture_files_are_outside_dataset(self) -> None:
        for path in FIXTURES.rglob("*"):
            if path.is_file():
                self.assertNotIn(ROOT / "dataset", path.parents)


if __name__ == "__main__":
    unittest.main()
