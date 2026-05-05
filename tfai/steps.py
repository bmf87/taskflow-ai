from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PlannerStep:
    prompt_kwargs: dict
    response: str
    tasks: List[str] = field(default_factory=list)

@dataclass
class ResearchStep:
    task: str
    prompt_kwargs: dict
    response: str
    notes: str

@dataclass
class WriterStep:
    prompt_kwargs: dict
    response: str  # final draft

@dataclass
class ReviewerStep:
    prompt_kwargs: dict
    response: str  # critique

@dataclass
class OrchestrationTrace:
    goal: str
    model_id: str
    planner: Optional[PlannerStep] = None
    research: List[ResearchStep] = field(default_factory=list)
    writer: Optional[WriterStep] = None
    reviewer: Optional[ReviewerStep] = None
    refiner: Optional[WriterStep] = None