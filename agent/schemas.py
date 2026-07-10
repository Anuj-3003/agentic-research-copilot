"""
agent/schemas.py
Pydantic contracts for every tool input/output and the planner's execution plan.
"""
import json
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field, field_validator

# Extend this as more tools are added (Phase 3: calculator/code-exec, etc.)
ToolName = Literal["findocgpt"]


class PlanStep(BaseModel):
    tool: ToolName
    tool_input: str = Field(description="The natural-language input to pass to the tool")
    reasoning: str = Field(description="Why this step is needed to answer the question")


class ExecutionPlan(BaseModel):
    steps: list[PlanStep] = Field(description="Ordered (but independently executable) steps")

    @field_validator("steps", mode="before")
    @classmethod
    def _parse_stringified_steps(cls, v):
        # Ollama tool-calling sometimes serializes nested list fields as a
        # JSON string instead of a real list (same issue hit in FinDocGPT's
        # CitedAnswer.citations) -- parse it back if that happens.
        if isinstance(v, str):
            return json.loads(v)
        return v


class FinDocGPTSource(BaseModel):
    doc_name: str
    page_number: int


class FinDocGPTToolResponse(BaseModel):
    """Mirrors FinDocGPT's actual /query response shape exactly (see
    findocgpt/api/main.py and findocgpt/agent/schemas.py::Citation)."""
    answer: str
    sources: list[FinDocGPTSource]
    confidence: Optional[Literal["high", "medium", "low"]] = None


class ToolResult(BaseModel):
    step: PlanStep
    output: FinDocGPTToolResponse
    error: Optional[str] = None


class Claim(BaseModel):
    text: str = Field(description="A single claim in the draft answer")
    source_tool: ToolName
    source_ref: str = Field(description="The tool_input of the ToolResult this claim is drawn from")
    confidence: Literal["high", "medium", "low"]


class Report(BaseModel):
    question: str
    claims: list[Claim]

    @field_validator("claims", mode="before")
    @classmethod
    def _parse_stringified_claims(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


CriticVerdict = Literal["PASS", "RETRY", "INSUFFICIENT_INFO"]


class CriticResult(BaseModel):
    # evidence_check comes first so the model has to work through each claim
    # against its source before committing to a verdict, instead of jumping
    # straight to a categorical judgment (small local models are much more
    # reliable when forced to show this intermediate step -- see the
    # false-positive this fixed in agent/self_critic.py's docstring).
    evidence_check: str = Field(
        description="For each claim, quote the exact matching text from its cited tool "
        "output, or state exactly what specific fact/number/name is missing. Be literal."
    )
    verdict: CriticVerdict
    reason: str = Field(description="Why this verdict was reached, based on the evidence_check above")


class AgentState(TypedDict):
    question: str
    plan: Optional[ExecutionPlan]
    tool_results: list[ToolResult]
    draft_report: Optional[Report]
    critic_result: Optional[CriticResult]
    retry_count: int
    final_output: str
    trace: list[dict]
