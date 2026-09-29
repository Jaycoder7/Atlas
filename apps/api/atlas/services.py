from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import UTC, date, datetime
from itertools import pairwise
from typing import Any

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    ChangeLink,
    Decision,
    EngineeringChange,
    HardwareAllocation,
    HardwareRevision,
    HardwareStatus,
    HardwareUnit,
    Milestone,
    Program,
    Requirement,
    RequirementTestLink,
    Risk,
    RiskStatus,
    RiskTaskLink,
    Task,
    TaskDependency,
    TaskStatus,
    TestRun,
    TestStatus,
    TestTaskLink,
    ValidationTest,
    VerificationStatus,
)
from .schedule import TaskNode, analyze_schedule
from .schemas import ScenarioEvaluate, TestRunCreate


def enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def model_dict(item: Any) -> dict[str, Any]:
    result = {
        column.name: enum_value(getattr(item, column.name)) for column in item.__table__.columns
    }
    if isinstance(item, Risk):
        result.update(score=item.score, severity=item.severity)
    return result


def assert_program(db: Session, org_id: str, program_id: str) -> Program:
    program = db.scalar(
        select(Program).where(Program.id == program_id, Program.organization_id == org_id)
    )
    if not program:
        raise LookupError("Program not found")
    return program


def get_schedule(
    db: Session, org_id: str, program_id: str, delays: dict[str, int] | None = None
) -> dict:
    assert_program(db, org_id, program_id)
    tasks = list(
        db.scalars(
            select(Task).where(Task.organization_id == org_id, Task.program_id == program_id)
        )
    )
    dependencies = list(
        db.scalars(
            select(TaskDependency).where(
                TaskDependency.organization_id == org_id, TaskDependency.program_id == program_id
            )
        )
    )
    milestones = list(
        db.scalars(
            select(Milestone).where(
                Milestone.organization_id == org_id, Milestone.program_id == program_id
            )
        )
    )
    target = max((item.target_date for item in milestones), default=None)
    nodes = [
        TaskNode(
            id=item.id,
            code=item.code,
            name=item.name,
            duration_days=item.duration_days,
            baseline_start=item.baseline_start,
            status=enum_value(item.status),
            forecast_start=item.forecast_start,
            forecast_end=item.forecast_end,
        )
        for item in tasks
    ]
    result = analyze_schedule(
        nodes,
        [(item.predecessor_id, item.successor_id) for item in dependencies],
        delays,
        target,
    )
    task_results = {item["id"]: item for item in result["tasks"]}
    for task in tasks:
        computed = task_results[task.id]
        task.forecast_start = computed["forecast_start"]
        task.forecast_end = computed["forecast_finish"]
    for milestone in milestones:
        if milestone.task_id and milestone.task_id in task_results:
            milestone.forecast_date = task_results[milestone.task_id]["forecast_finish"]
    return result


def validate_dependency(
    db: Session, org_id: str, program_id: str, predecessor_id: str, successor_id: str
) -> None:
    if predecessor_id == successor_id:
        raise ValueError("A task cannot depend on itself")
    ids = set(
        db.scalars(
            select(Task.id).where(
                Task.organization_id == org_id,
                Task.program_id == program_id,
                Task.id.in_([predecessor_id, successor_id]),
            )
        )
    )
    if ids != {predecessor_id, successor_id}:
        raise ValueError("Both tasks must belong to the active organization and program")
    existing = list(
        db.scalars(
            select(TaskDependency).where(
                TaskDependency.organization_id == org_id, TaskDependency.program_id == program_id
            )
        )
    )
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in existing:
        adjacency[edge.predecessor_id].append(edge.successor_id)
    queue = deque([successor_id])
    seen: set[str] = set()
    while queue:
        current = queue.popleft()
        if current == predecessor_id:
            raise ValueError("Dependency would create a cycle")
        if current not in seen:
            seen.add(current)
            queue.extend(adjacency[current])


def hardware_warnings(db: Session, org_id: str, program_id: str) -> list[dict[str, Any]]:
    allocations = list(
        db.scalars(
            select(HardwareAllocation).where(
                HardwareAllocation.organization_id == org_id,
                HardwareAllocation.program_id == program_id,
            )
        )
    )
    units = {
        item.id: item
        for item in db.scalars(
            select(HardwareUnit).where(
                HardwareUnit.organization_id == org_id, HardwareUnit.program_id == program_id
            )
        )
    }
    tests = {
        item.id: item
        for item in db.scalars(
            select(ValidationTest).where(
                ValidationTest.organization_id == org_id, ValidationTest.program_id == program_id
            )
        )
    }
    warnings: list[dict[str, Any]] = []
    by_unit: dict[str, list[HardwareAllocation]] = defaultdict(list)
    for allocation in allocations:
        by_unit[allocation.hardware_unit_id].append(allocation)
        unit = units.get(allocation.hardware_unit_id)
        test = tests.get(allocation.test_id or "")
        if not unit:
            continue
        if unit.available_date and allocation.start_date < unit.available_date:
            warnings.append(
                {"type": "unavailable", "allocation_id": allocation.id, "unit": unit.serial_number}
            )
        if test and test.required_revision_id and test.required_revision_id != unit.revision_id:
            warnings.append(
                {
                    "type": "revision_mismatch",
                    "allocation_id": allocation.id,
                    "unit": unit.serial_number,
                }
            )
    for unit_id, values in by_unit.items():
        ordered = sorted(values, key=lambda item: item.start_date)
        for left, right in pairwise(ordered):
            if right.start_date <= left.end_date:
                warnings.append(
                    {
                        "type": "overlap",
                        "unit": units[unit_id].serial_number,
                        "allocation_ids": [left.id, right.id],
                    }
                )
    return warnings


def update_requirement_statuses(
    db: Session, org_id: str, program_id: str, test_id: str
) -> list[Requirement]:
    requirement_ids = list(
        db.scalars(
            select(RequirementTestLink.requirement_id).where(
                RequirementTestLink.organization_id == org_id,
                RequirementTestLink.program_id == program_id,
                RequirementTestLink.test_id == test_id,
            )
        )
    )
    updated: list[Requirement] = []
    for requirement_id in requirement_ids:
        requirement = db.scalar(
            select(Requirement).where(
                Requirement.id == requirement_id, Requirement.organization_id == org_id
            )
        )
        linked_test_ids = list(
            db.scalars(
                select(RequirementTestLink.test_id).where(
                    RequirementTestLink.requirement_id == requirement_id,
                    RequirementTestLink.required == 1,
                )
            )
        )
        statuses = list(
            db.scalars(select(ValidationTest.status).where(ValidationTest.id.in_(linked_test_ids)))
        )
        allocation_blocked = db.scalar(
            select(HardwareAllocation.id)
            .join(HardwareUnit, HardwareUnit.id == HardwareAllocation.hardware_unit_id)
            .where(
                HardwareAllocation.organization_id == org_id,
                HardwareAllocation.test_id.in_(linked_test_ids),
                or_(
                    HardwareAllocation.status == "blocked",
                    HardwareUnit.status == HardwareStatus.FAILED,
                ),
            )
            .limit(1)
        )
        if any(value == TestStatus.FAIL for value in statuses):
            requirement.status = VerificationStatus.FAILED
        elif any(value == TestStatus.BLOCKED for value in statuses) or allocation_blocked:
            requirement.status = VerificationStatus.BLOCKED
        elif statuses and all(value == TestStatus.PASS for value in statuses):
            requirement.status = VerificationStatus.VERIFIED
        else:
            requirement.status = VerificationStatus.NOT_TESTED
        updated.append(requirement)
    return updated


def ingest_test_run(db: Session, org_id: str, payload: TestRunCreate) -> tuple[TestRun, bool]:
    assert_program(db, org_id, payload.program_id)
    existing = db.scalar(
        select(TestRun).where(
            TestRun.organization_id == org_id, TestRun.external_run_id == payload.external_run_id
        )
    )
    if existing:
        return existing, False
    test = db.scalar(
        select(ValidationTest).where(
            ValidationTest.organization_id == org_id,
            ValidationTest.program_id == payload.program_id,
            ValidationTest.code == payload.test_code,
        )
    )
    unit = db.scalar(
        select(HardwareUnit).where(
            HardwareUnit.organization_id == org_id,
            HardwareUnit.program_id == payload.program_id,
            HardwareUnit.serial_number == payload.hardware_serial,
        )
    )
    if not test or not unit:
        raise LookupError("Test or hardware unit not found in active organization")
    if test.required_revision_id and unit.revision_id != test.required_revision_id:
        raise ValueError("Hardware revision is not compatible with this test")
    run = TestRun(
        organization_id=org_id,
        program_id=payload.program_id,
        external_run_id=payload.external_run_id,
        test_id=test.id,
        hardware_unit_id=unit.id,
        measured_value=payload.measured_value,
        status=payload.status,
        executed_at=payload.executed_at or datetime.now(UTC),
    )
    db.add(run)
    test.status = payload.status
    # Sessions intentionally disable autoflush; make the new test state visible to
    # the requirement aggregation queries in this same transaction.
    db.flush()
    update_requirement_statuses(db, org_id, payload.program_id, test.id)
    if payload.status == TestStatus.FAIL:
        unit.status = HardwareStatus.FAILED
        unit.failure_state = f"{test.code} failed"
        sibling_units = list(
            db.scalars(
                select(HardwareUnit).where(
                    HardwareUnit.organization_id == org_id,
                    HardwareUnit.program_id == payload.program_id,
                    HardwareUnit.revision_id == unit.revision_id,
                    HardwareUnit.id != unit.id,
                )
            )
        )
        for sibling in sibling_units:
            sibling.failure_state = (
                f"Potentially affected by {test.code} failure on {unit.serial_number}"
            )
        linked_tasks = list(
            db.scalars(
                select(Task)
                .join(TestTaskLink, TestTaskLink.task_id == Task.id)
                .where(TestTaskLink.test_id == test.id, Task.organization_id == org_id)
            )
        )
        for task in linked_tasks:
            if task.status != TaskStatus.COMPLETE:
                task.status = TaskStatus.BLOCKED
        risk = db.scalar(
            select(Risk).where(
                Risk.organization_id == org_id,
                Risk.program_id == payload.program_id,
                Risk.source_type == "test_failure",
                Risk.source_id == test.id,
            )
        )
        if not risk:
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.program_id == payload.program_id)
                )
                or 0
            )
            risk = Risk(
                organization_id=org_id,
                program_id=payload.program_id,
                code=f"RISK-AUTO-{count + 1:03d}",
                description=f"{test.code} failed on {unit.serial_number}: {test.name}",
                probability=5,
                impact=5,
                owner="Validation Lead",
                mitigation="Triage failure, assess affected requirements, and select a mitigation.",
                status=RiskStatus.OPEN,
                source_type="test_failure",
                source_id=test.id,
            )
            db.add(risk)
            db.flush()
            for task in linked_tasks:
                db.add(
                    RiskTaskLink(
                        organization_id=org_id,
                        program_id=payload.program_id,
                        risk_id=risk.id,
                        task_id=task.id,
                    )
                )
    db.flush()
    get_schedule(db, org_id, payload.program_id)
    db.commit()
    db.refresh(run)
    return run, True


def change_impact(db: Session, org_id: str, change_id: str) -> dict[str, Any]:
    change = db.scalar(
        select(EngineeringChange).where(
            EngineeringChange.id == change_id, EngineeringChange.organization_id == org_id
        )
    )
    if not change:
        raise LookupError("Engineering change not found")
    links = list(db.scalars(select(ChangeLink).where(ChangeLink.change_id == change.id)))
    direct: dict[str, list[str]] = defaultdict(list)
    for link in links:
        direct[link.entity_type].append(link.entity_id)
    task_ids = set(direct.get("task", []))
    test_ids = set(direct.get("test", []))
    requirement_ids = set(direct.get("requirement", []))
    revision_ids = set(direct.get("hardware_revision", []))
    unit_ids = set(direct.get("hardware_unit", []))
    milestone_ids = set(direct.get("milestone", []))

    if requirement_ids:
        test_ids.update(
            db.scalars(
                select(RequirementTestLink.test_id).where(
                    RequirementTestLink.requirement_id.in_(requirement_ids)
                )
            )
        )
    if test_ids:
        requirement_ids.update(
            db.scalars(
                select(RequirementTestLink.requirement_id).where(
                    RequirementTestLink.test_id.in_(test_ids)
                )
            )
        )
        task_ids.update(
            db.scalars(select(TestTaskLink.task_id).where(TestTaskLink.test_id.in_(test_ids)))
        )
    if revision_ids:
        unit_ids.update(
            db.scalars(select(HardwareUnit.id).where(HardwareUnit.revision_id.in_(revision_ids)))
        )

    dependencies = list(
        db.scalars(
            select(TaskDependency).where(
                TaskDependency.organization_id == org_id,
                TaskDependency.program_id == change.program_id,
            )
        )
    )
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in dependencies:
        adjacency[edge.predecessor_id].append(edge.successor_id)
    paths: dict[str, list[str]] = {task_id: [task_id] for task_id in task_ids}
    queue = deque(task_ids)
    while queue:
        current = queue.popleft()
        for successor in adjacency[current]:
            if successor not in paths:
                paths[successor] = paths[current] + [successor]
                task_ids.add(successor)
                queue.append(successor)
    if task_ids:
        milestone_ids.update(
            db.scalars(select(Milestone.id).where(Milestone.task_id.in_(task_ids)))
        )
    schedule = get_schedule(db, org_id, change.program_id)
    projected = change.schedule_impact_days
    affected = {
        "requirements": sorted(requirement_ids),
        "tests": sorted(test_ids),
        "hardware_revisions": sorted(revision_ids),
        "hardware_units": sorted(unit_ids),
        "tasks": sorted(task_ids),
        "milestones": sorted(milestone_ids),
    }
    return {
        "change": model_dict(change),
        "affected": affected,
        "counts": {key: len(value) for key, value in affected.items()},
        "dependency_paths": paths,
        "tests_requiring_rerun": sorted(test_ids),
        "obsolete_prototypes": sorted(unit_ids),
        "projected_schedule_impact_days": projected,
        "current_project_finish": schedule["project_finish"],
    }


def evaluate_scenario(db: Session, org_id: str, payload: ScenarioEvaluate) -> dict[str, Any]:
    baseline = get_schedule(db, org_id, payload.program_id)
    task_delays = {
        item.entity_id: item.delay_business_days
        for item in payload.overrides
        if item.kind == "task_delay"
    }
    simulated = get_schedule(db, org_id, payload.program_id, task_delays)
    # Roll back forecast writes made by schedule calculation; scenarios are read-only.
    db.rollback()
    base_finish = baseline["target_finish"]
    projected_finish = max(base_finish, simulated["project_finish"])
    impact = max(0, sum(1 for _ in _business_range(base_finish, projected_finish)))
    options = [
        {
            **item.model_dump(),
            "projected_impact_days": max(0, impact + item.schedule_delta_days),
        }
        for item in payload.options
    ]
    return {
        "baseline_finish": base_finish,
        "projected_finish": projected_finish,
        "schedule_impact_days": impact,
        "available_slack_days": baseline["available_slack_days"],
        "critical_path_before": baseline["critical_path"],
        "critical_path_after": simulated["critical_path"],
        "affected_tasks": sorted(task_delays),
        "options": options,
    }


def _business_range(start: date, end: date):
    current = start
    while current < end:
        current = date.fromordinal(current.toordinal() + 1)
        if current.weekday() < 5:
            yield current


def dashboard(db: Session, org_id: str, program_id: str) -> dict[str, Any]:
    schedule = get_schedule(db, org_id, program_id)
    db.flush()
    tasks = list(
        db.scalars(
            select(Task).where(Task.organization_id == org_id, Task.program_id == program_id)
        )
    )
    risks = list(
        db.scalars(
            select(Risk).where(Risk.organization_id == org_id, Risk.program_id == program_id)
        )
    )
    units = list(
        db.scalars(
            select(HardwareUnit).where(
                HardwareUnit.organization_id == org_id, HardwareUnit.program_id == program_id
            )
        )
    )
    tests = list(
        db.scalars(
            select(ValidationTest).where(
                ValidationTest.organization_id == org_id, ValidationTest.program_id == program_id
            )
        )
    )
    milestones = list(
        db.scalars(
            select(Milestone).where(
                Milestone.organization_id == org_id, Milestone.program_id == program_id
            )
        )
    )
    decisions = list(
        db.scalars(
            select(Decision).where(
                Decision.organization_id == org_id,
                Decision.program_id == program_id,
                Decision.status == "required",
            )
        )
    )
    ranked_risks = sorted(
        [item for item in risks if item.status != RiskStatus.CLOSED],
        key=lambda item: item.score,
        reverse=True,
    )
    blocked = [item for item in tasks if item.status == TaskStatus.BLOCKED]
    failed_units = [item for item in units if item.status == HardwareStatus.FAILED]
    failed_tests = [item for item in tests if item.status == TestStatus.FAIL]
    current_milestone = min(
        (item for item in milestones if item.status != "complete"),
        key=lambda item: item.target_date,
        default=None,
    )
    critical_codes = {
        task.id: task.code for task in tasks if task.id in set(schedule["critical_path"])
    }
    return {
        "program_health": {
            "schedule": "at_risk" if schedule["variance_days"] > 0 or blocked else "on_track",
            "hardware": "at_risk" if failed_units else "on_track",
            "firmware": "blocked"
            if any(item.team_id and "Firmware" in item.name and item in blocked for item in tasks)
            else "on_track",
            "validation": "blocked" if failed_tests or blocked else "on_track",
        },
        "current_milestone": model_dict(current_milestone) if current_milestone else None,
        "target_completion": schedule["target_finish"],
        "forecast_completion": schedule["project_finish"],
        "critical_path": list(critical_codes.values()),
        "top_blocker": model_dict(blocked[0]) if blocked else None,
        "highest_risks": [model_dict(item) for item in ranked_risks[:5]],
        "required_decisions": [model_dict(item) for item in decisions],
        "hardware_warnings": hardware_warnings(db, org_id, program_id),
        "counts": {
            "tasks": len(tasks),
            "blocked_tasks": len(blocked),
            "failed_tests": len(failed_tests),
            "open_risks": len(ranked_risks),
        },
    }


async def ollama_suggestions(db: Session, org_id: str, change_id: str) -> dict[str, Any]:
    impact = change_impact(db, org_id, change_id)
    change = impact["change"]
    program_id = change["program_id"]
    catalog: dict[str, list[dict[str, str]]] = {
        "requirement": [
            {"id": item.id, "label": f"{item.code}: {item.title}"}
            for item in db.scalars(select(Requirement).where(Requirement.program_id == program_id))
        ],
        "test": [
            {"id": item.id, "label": f"{item.code}: {item.name}"}
            for item in db.scalars(
                select(ValidationTest).where(ValidationTest.program_id == program_id)
            )
        ],
        "task": [
            {"id": item.id, "label": f"{item.code}: {item.name}"}
            for item in db.scalars(select(Task).where(Task.program_id == program_id))
        ],
        "hardware_revision": [
            {"id": item.id, "label": item.code}
            for item in db.scalars(
                select(HardwareRevision).where(HardwareRevision.program_id == program_id)
            )
        ],
        "hardware_unit": [
            {"id": item.id, "label": item.serial_number}
            for item in db.scalars(
                select(HardwareUnit).where(HardwareUnit.program_id == program_id)
            )
        ],
        "milestone": [
            {"id": item.id, "label": item.name}
            for item in db.scalars(select(Milestone).where(Milestone.program_id == program_id))
        ],
    }
    valid = {item["id"] for values in catalog.values() for item in values}
    settings = get_settings()
    prompt = (
        'Return JSON only as {"suggestions":[{"entity_type":"requirement|test|task",'
        '"entity_id":"existing id","confidence":0.0,"rationale":"short reason"}]}. '
        "Suggest at most five missing links. Never invent an ID. Entity type may also be "
        "hardware_revision, hardware_unit, or milestone.\n"
        f"Engineering change: {change['title']} — {change['description']}\nCatalog: {json.dumps(catalog)}"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            raw = json.loads(response.json()["response"])
    except Exception:
        return {
            "available": False,
            "suggestions": [],
            "message": "Local Ollama suggestions are unavailable",
        }
    suggestions = []
    for item in raw.get("suggestions", []):
        if item.get("entity_id") in valid and item.get("entity_type") in catalog:
            try:
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            suggestions.append(
                {
                    "entity_type": item["entity_type"],
                    "entity_id": item["entity_id"],
                    "confidence": min(1, max(0, confidence)),
                    "rationale": str(item.get("rationale", ""))[:500],
                }
            )
    return {"available": True, "suggestions": suggestions}
