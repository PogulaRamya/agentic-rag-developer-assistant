from typing import Literal
from pydantic import BaseModel, Field

class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

class Plan(BaseModel):
    route: Literal["retrieval", "trend"]
    query: str = Field(min_length=1, max_length=2000)
    tag: str = Field(default="python", pattern=r"^[a-z0-9+#.\-]{1,40}$")
    months: int = Field(default=12, ge=1, le=36)

class RankedIds(BaseModel):
    ids: list[str] = Field(max_length=6)

class GroundedAnswer(BaseModel):
    answer: str = Field(max_length=12000)
    source_ids: list[str] = Field(max_length=6)
    insufficient_evidence: bool = False
