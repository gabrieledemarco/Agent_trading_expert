"""Contract tests for ValidationAgent output schema.

These tests verify the SHAPE of the data, not the values.
They act as a regression gate: if any of these fail after a refactor,
the output contract has been broken.
"""
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# ── Required fields with expected types ──────────────────────────────────────
TOP_LEVEL_FIELDS = {
    "model_name": str,
    "validation_status": str,
    "validation_timestamp": str,
    "code_quality": dict,
    "anomalies": list,
    "academic_discrepancies": list,
    "risk_return_profile": dict,
    "statistical_robustness": dict,
}

CODE_QUALITY_FIELDS = {
    "issues": list,
    "warnings": list,
    "score": (int, float),
}

RISK_RETURN_FIELDS = {
    "expected_return": float,
    "volatility": float,
    "sharpe_ratio": float,
    "max_drawdown": float,
    "win_rate": float,
    "risk_score": str,
    "return_score": str,
    "risk_return_ratio": float,
}

ROBUSTNESS_FIELDS = {
    "mean_return": float,
    "std_return": float,
    "percentile_5": float,
    "percentile_95": float,
    "prob_positive_return": float,
    "prob_negative_10": float,
    "coefficient_of_variation": float,
    "robustness_score": str,
}

VALID_STATUSES = {"APPROVED", "REJECTED"}
VALID_RISK_SCORES = {"LOW", "MEDIUM", "HIGH"}
VALID_RETURN_SCORES = {"POOR", "MODERATE", "GOOD", "EXCELLENT"}
VALID_ROBUSTNESS_SCORES = {"LOW", "MEDIUM", "HIGH"}

ANOMALY_FIELDS = {"type": str, "severity": str, "description": str}
VALID_SEVERITIES = {"high", "medium", "low"}


def _load_all_validation_files():
    validated_dir = ROOT / "models" / "validated"
    results = []
    for p in validated_dir.glob("*_validation.json"):
        with open(p) as f:
            results.append((p.name, json.load(f)))
    assert len(results) > 0, "No validation files found"
    return results


@pytest.mark.parametrize("filename,data", _load_all_validation_files())
class TestValidationSchema:

    def test_top_level_fields_present(self, filename, data):
        for field, expected_type in TOP_LEVEL_FIELDS.items():
            assert field in data, f"[{filename}] Missing top-level field: '{field}'"
            assert isinstance(data[field], expected_type), (
                f"[{filename}] Field '{field}' expected {expected_type}, got {type(data[field])}"
            )

    def test_validation_status_enum(self, filename, data):
        assert data["validation_status"] in VALID_STATUSES, (
            f"[{filename}] Invalid validation_status: '{data['validation_status']}'"
        )

    def test_code_quality_fields(self, filename, data):
        cq = data["code_quality"]
        for field, expected_type in CODE_QUALITY_FIELDS.items():
            assert field in cq, f"[{filename}] Missing code_quality.{field}"
            assert isinstance(cq[field], expected_type), (
                f"[{filename}] code_quality.{field} wrong type"
            )
        assert 0 <= cq["score"] <= 10, f"[{filename}] code_quality.score out of range"

    def test_risk_return_profile_fields(self, filename, data):
        rr = data["risk_return_profile"]
        for field, expected_type in RISK_RETURN_FIELDS.items():
            assert field in rr, f"[{filename}] Missing risk_return_profile.{field}"
            assert isinstance(rr[field], expected_type), (
                f"[{filename}] risk_return_profile.{field} wrong type"
            )

    def test_risk_score_enum(self, filename, data):
        score = data["risk_return_profile"]["risk_score"]
        assert score in VALID_RISK_SCORES, f"[{filename}] Invalid risk_score: '{score}'"

    def test_return_score_enum(self, filename, data):
        score = data["risk_return_profile"]["return_score"]
        assert score in VALID_RETURN_SCORES, f"[{filename}] Invalid return_score: '{score}'"

    def test_statistical_robustness_fields(self, filename, data):
        rob = data["statistical_robustness"]
        for field, expected_type in ROBUSTNESS_FIELDS.items():
            assert field in rob, f"[{filename}] Missing statistical_robustness.{field}"
            assert isinstance(rob[field], expected_type), (
                f"[{filename}] statistical_robustness.{field} wrong type"
            )

    def test_robustness_score_enum(self, filename, data):
        score = data["statistical_robustness"]["robustness_score"]
        assert score in VALID_ROBUSTNESS_SCORES, f"[{filename}] Invalid robustness_score: '{score}'"

    def test_probabilities_in_range(self, filename, data):
        rob = data["statistical_robustness"]
        assert 0.0 <= rob["prob_positive_return"] <= 1.0
        assert 0.0 <= rob["prob_negative_10"] <= 1.0
        rr = data["risk_return_profile"]
        assert 0.0 <= rr["win_rate"] <= 1.0
        assert rr["max_drawdown"] >= 0.0

    def test_anomalies_structure(self, filename, data):
        for i, anomaly in enumerate(data["anomalies"]):
            for field, expected_type in ANOMALY_FIELDS.items():
                assert field in anomaly, f"[{filename}] anomaly[{i}] missing '{field}'"
                assert isinstance(anomaly[field], expected_type)
            assert anomaly["severity"] in VALID_SEVERITIES, (
                f"[{filename}] anomaly[{i}] invalid severity '{anomaly['severity']}'"
            )

    def test_rejected_has_high_severity_anomaly(self, filename, data):
        """REJECTED models must have at least one high-severity anomaly."""
        if data["validation_status"] == "REJECTED":
            high = [a for a in data["anomalies"] if a["severity"] == "high"]
            assert len(high) > 0, (
                f"[{filename}] REJECTED model has no high-severity anomaly"
            )
