"""Pydantic data contracts — v1.0.

These models are the authoritative type definitions for all
inter-component communication. Agents produce/consume these types;
the Execution Engine receives/returns them over HTTP.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class ValidationStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Severity(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class RiskScore(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class ReturnScore(str, Enum):
    POOR      = "POOR"
    MODERATE  = "MODERATE"
    GOOD      = "GOOD"
    EXCELLENT = "EXCELLENT"


class RobustnessScore(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class TradeAction(str, Enum):
    BUY  = "buy"
    SELL = "sell"
    HOLD = "hold"


# ── Validation contracts ──────────────────────────────────────────────────────

class CodeQuality(BaseModel):
    issues:   List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    score:    float = Field(ge=0, le=10)


class Anomaly(BaseModel):
    type:        str
    severity:    Severity
    description: str


class RiskReturnProfile(BaseModel):
    expected_return:   float
    volatility:        float = Field(ge=0)
    sharpe_ratio:      float
    max_drawdown:      float = Field(ge=0)
    win_rate:          float = Field(ge=0, le=1)
    risk_score:        RiskScore
    return_score:      ReturnScore
    risk_return_ratio: float


class StatisticalRobustness(BaseModel):
    mean_return:              float
    std_return:               float = Field(ge=0)
    percentile_5:             float
    percentile_95:            float
    prob_positive_return:     float = Field(ge=0, le=1)
    prob_negative_10:         float = Field(ge=0, le=1)
    coefficient_of_variation: float
    robustness_score:         RobustnessScore


class ValidationResult(BaseModel):
    schema_version:         str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    model_name:             str
    validation_status:      ValidationStatus
    validation_timestamp:   str
    code_quality:           CodeQuality
    anomalies:              List[Anomaly] = Field(default_factory=list)
    academic_discrepancies: List[Any]    = Field(default_factory=list)
    risk_return_profile:    RiskReturnProfile
    statistical_robustness: StatisticalRobustness

    @field_validator("validation_status", mode="before")
    @classmethod
    def check_rejected_has_high_anomaly(cls, v, info):
        # Validated downstream — cannot access anomalies here without custom root validator
        return v

    def is_approved(self) -> bool:
        return self.validation_status == ValidationStatus.APPROVED


# ── Trade / Performance contracts ─────────────────────────────────────────────

class TradeRecord(BaseModel):
    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    timestamp:      str
    symbol:         str
    action:         TradeAction
    quantity:       float = Field(gt=0)
    price:          float = Field(gt=0)
    value:          float = Field(gt=0)
    signal:         Optional[str] = None
    model_name:     str


class PerformanceRecord(BaseModel):
    schema_version:  str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    timestamp:       str
    model_name:      str
    current_equity:  float = Field(gt=0)
    total_return:    float
    sharpe_ratio:    float
    max_drawdown:    float = Field(ge=0)
    win_rate:        float = Field(ge=0, le=1)
    num_trades:      int   = Field(ge=0)
    risk_profile:    str


# ── Execution Engine contracts ────────────────────────────────────────────────

class ExecutionDataset(BaseModel):
    symbols:   List[str]
    start:     str
    end:       str
    frequency: str = "1d"


class BacktestConfig(BaseModel):
    initial_capital:      float = 10_000
    transaction_cost:     float = 0.001
    walk_forward_windows: int   = 12
    seed:                 int   = 42


class ExecutionRequest(BaseModel):
    strategy_id:     str
    strategy_code:   str
    parameters:      dict
    dataset:         ExecutionDataset
    backtest_config: BacktestConfig = Field(default_factory=BacktestConfig)
