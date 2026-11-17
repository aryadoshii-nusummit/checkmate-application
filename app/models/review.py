"""Validated models for structured AI-generated code reviews."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
Confidence = Literal["HIGH", "MEDIUM"]
Quality = Literal["GOOD", "ACCEPTABLE", "NEEDS IMPROVEMENT"]


class ReviewFinding(BaseModel):
    """A distinct, evidence-backed issue identified in a source file."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    severity: Severity
    confidence: Confidence
    category: str = Field(min_length=1)
    line_numbers: list[int] = Field(min_length=1)
    evidence: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)

    @field_validator("line_numbers")
    @classmethod
    def validate_line_numbers(cls, values: list[int]) -> list[int]:
        """Require unique, positive source line numbers."""
        if any(number < 1 for number in values):
            raise ValueError("Line numbers must be positive integers.")

        if len(values) != len(set(values)):
            raise ValueError("Line numbers must not contain duplicates.")

        return values


class ReviewResult(BaseModel):
    """Complete structured result returned by the AI reviewer."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1)
    overall_quality: Quality
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    additional_suggestions: list[str] = Field(default_factory=list)