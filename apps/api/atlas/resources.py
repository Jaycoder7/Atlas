from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, inspect, select
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Session

from .models import (
    ChangeLink,
    Decision,
    EngineeringChange,
    HardwareAllocation,
    HardwareRevision,
    HardwareUnit,
    Milestone,
    Requirement,
    RequirementTestLink,
    Risk,
    RiskTaskLink,
    Scenario,
    ScenarioOption,
    Task,
    Team,
    TestTaskLink,
    ValidationTest,
)
from .services import model_dict

RESOURCE_MODELS = {
    "teams": Team,
    "tasks": Task,
    "milestones": Milestone,
    "hardware-revisions": HardwareRevision,
    "hardware-units": HardwareUnit,
    "allocations": HardwareAllocation,
    "requirements": Requirement,
    "tests": ValidationTest,
    "requirement-test-links": RequirementTestLink,
    "test-task-links": TestTaskLink,
    "risks": Risk,
    "risk-task-links": RiskTaskLink,
    "engineering-changes": EngineeringChange,
    "change-links": ChangeLink,
    "scenarios": Scenario,
    "scenario-options": ScenarioOption,
    "decisions": Decision,
}

REFERENCE_MODELS = {
    "team_id": Team,
    "task_id": Task,
    "revision_id": HardwareRevision,
    "required_revision_id": HardwareRevision,
    "hardware_unit_id": HardwareUnit,
    "test_id": ValidationTest,
    "requirement_id": Requirement,
    "risk_id": Risk,
    "affected_milestone_id": Milestone,
    "change_id": EngineeringChange,
    "scenario_id": Scenario,
}


def get_model(resource: str):
    model = RESOURCE_MODELS.get(resource)
    if not model:
        raise KeyError(f"Unknown resource: {resource}")
    return model


def _coerce(column, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date) and isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(column.type, SqlEnum) and isinstance(value, str):
        return column.type.enum_class(value)
    return value


def prepare_payload(model, payload: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    columns = {item.name: item for item in inspect(model).columns}
    immutable = {"id", "organization_id", "program_id", "created_at", "updated_at"}
    unknown = set(payload) - set(columns)
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
    result = {
        key: _coerce(columns[key], value) for key, value in payload.items() if key not in immutable
    }
    if model is Risk:
        probability = result.get("probability")
        impact = result.get("impact")
        if (probability is not None and not 1 <= probability <= 5) or (
            impact is not None and not 1 <= impact <= 5
        ):
            raise ValueError("Risk probability and impact must be between 1 and 5")
    if model is Task:
        duration = result.get("duration_days")
        if duration is not None and not 1 <= duration <= 365:
            raise ValueError("Task duration must be between 1 and 365 business days")
        if (
            result.get("baseline_start")
            and result.get("baseline_end")
            and result["baseline_end"] < result["baseline_start"]
        ):
            raise ValueError("Task baseline finish must not precede its start")
    if (
        model is HardwareAllocation
        and result.get("start_date")
        and result.get("end_date")
        and result["end_date"] < result["start_date"]
    ):
        raise ValueError("Allocation end date must not precede start date")
    return result


def list_resources(db: Session, model, org_id: str, program_id: str) -> list[dict[str, Any]]:
    query = select(model).where(model.organization_id == org_id)
    if hasattr(model, "program_id"):
        query = query.where(model.program_id == program_id)
    elif model is ScenarioOption:
        query = query.join(Scenario, Scenario.id == ScenarioOption.scenario_id).where(
            Scenario.program_id == program_id
        )
    return [model_dict(item) for item in db.scalars(query)]


def get_resource(db: Session, model, org_id: str, item_id: str):
    return db.scalar(select(model).where(model.id == item_id, model.organization_id == org_id))


def validate_tenant_references(
    db: Session, org_id: str, program_id: str, payload: dict[str, Any]
) -> None:
    """Reject relationship IDs that cross an organization or program boundary."""
    for field, model in REFERENCE_MODELS.items():
        value = payload.get(field)
        if not value:
            continue
        referenced = get_resource(db, model, org_id, value)
        if not referenced:
            raise ValueError(f"{field} must reference the active organization")
        if hasattr(referenced, "program_id") and referenced.program_id != program_id:
            raise ValueError(f"{field} must reference the active program")
