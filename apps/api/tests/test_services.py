from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from atlas.database import Base
from atlas.models import (
    HardwareAllocation,
    HardwareRevision,
    HardwareStatus,
    HardwareUnit,
    Program,
    Requirement,
    RequirementTestLink,
    Risk,
    Task,
    TaskStatus,
    ValidationTest,
    VerificationStatus,
)
from atlas.models import (
    TestStatus as RunStatus,
)
from atlas.models import (
    TestTaskLink as ValidationTaskLink,
)
from atlas.resources import validate_tenant_references
from atlas.schemas import TestRunCreate as RunPayload
from atlas.services import ingest_test_run, update_requirement_statuses


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        yield session


def build_failure_fixture(db: Session, org: str = "org-a"):
    program = Program(
        organization_id=org, name="Telemetry", description="", start_date=date(2026, 1, 5)
    )
    db.add(program)
    db.flush()
    task = Task(
        organization_id=org,
        program_id=program.id,
        code="TASK-001",
        name="Thermal validation",
        owner="Val",
        duration_days=2,
        baseline_start=date(2026, 1, 5),
        baseline_end=date(2026, 1, 6),
    )
    revision = HardwareRevision(
        organization_id=org, program_id=program.id, code="Rev C", description=""
    )
    requirement = Requirement(
        organization_id=org,
        program_id=program.id,
        code="REQ-014",
        title="Thermal regulation",
        description="",
    )
    db.add_all([task, revision, requirement])
    db.flush()
    unit = HardwareUnit(
        organization_id=org,
        program_id=program.id,
        revision_id=revision.id,
        serial_number="P1-003",
        current_owner="Validation",
        status=HardwareStatus.TESTING,
    )
    test = ValidationTest(
        organization_id=org,
        program_id=program.id,
        code="TEST-021",
        name="Thermal",
        required_revision_id=revision.id,
    )
    db.add_all([unit, test])
    db.flush()
    db.add_all(
        [
            RequirementTestLink(
                organization_id=org,
                program_id=program.id,
                requirement_id=requirement.id,
                test_id=test.id,
                required=1,
            ),
            ValidationTaskLink(
                organization_id=org, program_id=program.id, test_id=test.id, task_id=task.id
            ),
        ]
    )
    db.commit()
    return program, task, unit, requirement


def test_failure_propagates_and_is_idempotent(db: Session):
    program, task, unit, requirement = build_failure_fixture(db)
    payload = RunPayload(
        external_run_id="run-1",
        program_id=program.id,
        test_code="TEST-021",
        hardware_serial="P1-003",
        measured_value={"voltage": 2.7},
        status=RunStatus.FAIL,
    )
    run, created = ingest_test_run(db, "org-a", payload)
    duplicate, created_again = ingest_test_run(db, "org-a", payload)
    db.refresh(task)
    db.refresh(unit)
    db.refresh(requirement)
    assert created is True and created_again is False and run.id == duplicate.id
    assert task.status == TaskStatus.BLOCKED
    assert unit.status == HardwareStatus.FAILED
    assert requirement.status == VerificationStatus.FAILED
    assert len(list(db.scalars(select(Risk)))) == 1


def test_cross_tenant_ingestion_cannot_see_program(db: Session):
    program, *_ = build_failure_fixture(db, "org-a")
    payload = RunPayload(
        external_run_id="run-2",
        program_id=program.id,
        test_code="TEST-021",
        hardware_serial="P1-003",
        status=RunStatus.PASS,
    )
    with pytest.raises(LookupError):
        ingest_test_run(db, "org-b", payload)


def test_relationship_reference_cannot_cross_tenant(db: Session):
    program, task, *_ = build_failure_fixture(db, "org-a")
    with pytest.raises(ValueError, match="active organization"):
        validate_tenant_references(db, "org-b", program.id, {"task_id": task.id})


def test_runner_accepts_prd_field_names_and_uppercase_status():
    payload = RunPayload.model_validate(
        {
            "external_run_id": "external-1",
            "program_id": "program-1",
            "test_id": "TEST-023",
            "hardware": "P1-003",
            "result": 1.42,
            "status": "PASS",
        }
    )
    assert payload.test_code == "TEST-023"
    assert payload.hardware_serial == "P1-003"
    assert payload.measured_value == 1.42
    assert payload.status == RunStatus.PASS


def test_blocked_hardware_allocation_blocks_requirement(db: Session):
    program, task, unit, requirement = build_failure_fixture(db)
    test = db.scalar(select(ValidationTest).where(ValidationTest.code == "TEST-021"))
    test.status = RunStatus.PASS
    db.add(
        HardwareAllocation(
            organization_id="org-a",
            program_id=program.id,
            hardware_unit_id=unit.id,
            test_id=test.id,
            task_id=task.id,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 6),
            status="blocked",
        )
    )
    db.flush()
    update_requirement_statuses(db, "org-a", program.id, test.id)
    assert requirement.status == VerificationStatus.BLOCKED
