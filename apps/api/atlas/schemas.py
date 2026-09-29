from datetime import date, datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import TestStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ProgramCreate(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    start_date: date


class ProgramRead(ProgramCreate):
    id: str
    organization_id: str


class TaskCreate(ApiModel):
    code: str
    name: str
    team_id: str | None = None
    owner: str = "Unassigned"
    description: str = ""
    duration_days: int = Field(ge=1, le=365)
    baseline_start: date
    baseline_end: date
    status: str = "not_started"


class DependencyCreate(ApiModel):
    predecessor_id: str
    successor_id: str

    @model_validator(mode="after")
    def no_self_dependency(self) -> "DependencyCreate":
        if self.predecessor_id == self.successor_id:
            raise ValueError("A task cannot depend on itself")
        return self


class TestRunCreate(ApiModel):
    external_run_id: str = Field(min_length=1, max_length=120)
    program_id: str
    test_code: str = Field(validation_alias=AliasChoices("test_code", "test_id"))
    hardware_serial: str = Field(validation_alias=AliasChoices("hardware_serial", "hardware"))
    measured_value: dict[str, Any] | float | str | None = Field(
        default=None, validation_alias=AliasChoices("measured_value", "result")
    )
    status: TestStatus
    executed_at: datetime | None = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> Any:
        return value.lower() if isinstance(value, str) else value


class ScenarioOverride(ApiModel):
    kind: Literal["task_delay", "revision_delay"]
    entity_id: str
    delay_business_days: int = Field(ge=0, le=365)


class ScenarioOptionInput(ApiModel):
    name: str
    cost_delta: int = 0
    schedule_delta_days: int = 0
    risk_note: str = ""


class ScenarioEvaluate(ApiModel):
    program_id: str
    overrides: list[ScenarioOverride]
    options: list[ScenarioOptionInput] = []


class ScheduleTask(ApiModel):
    id: str
    code: str
    name: str
    earliest_start: date
    earliest_finish: date
    latest_start: date
    latest_finish: date
    slack_days: int
    is_critical: bool
    forecast_start: date
    forecast_finish: date


class ScheduleResult(ApiModel):
    tasks: list[ScheduleTask]
    critical_path: list[str]
    project_finish: date
    target_finish: date
    variance_days: int
    available_slack_days: int
    dependency_paths: dict[str, list[str]]


class ImpactSuggestion(ApiModel):
    entity_type: Literal[
        "requirement", "test", "hardware_revision", "hardware_unit", "task", "milestone"
    ]
    entity_id: str
    confidence: float = Field(ge=0, le=1)
    rationale: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
