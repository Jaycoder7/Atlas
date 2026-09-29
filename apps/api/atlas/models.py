import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    NOT_TESTED = "not_tested"
    BLOCKED = "blocked"


class TestStatus(str, enum.Enum):
    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class RiskStatus(str, enum.Enum):
    OPEN = "open"
    MITIGATING = "mitigating"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class HardwareStatus(str, enum.Enum):
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    TESTING = "testing"
    FAILED = "failed"
    OBSOLETE = "obsolete"


class ChangeStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TenantMixin:
    organization_id: Mapped[str] = mapped_column(String(80), index=True)


class Organization(Base, IdMixin):
    __tablename__ = "organizations"
    auth0_org_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))


class UserProfile(Base, IdMixin):
    __tablename__ = "user_profiles"
    auth0_sub: Mapped[str] = mapped_column(String(160), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(160))


class Membership(Base, IdMixin, TenantMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.MEMBER)


class ServiceClient(Base, IdMixin, TenantMixin):
    __tablename__ = "service_clients"
    __table_args__ = (UniqueConstraint("auth0_client_id"),)
    auth0_client_id: Mapped[str] = mapped_column(String(160), index=True)
    name: Mapped[str] = mapped_column(String(160))


class Program(Base, IdMixin, TenantMixin):
    __tablename__ = "programs"
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[date] = mapped_column(Date)


class Team(Base, IdMixin, TenantMixin):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "name"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))


class Task(Base, IdMixin, TenantMixin):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(160), default="Unassigned")
    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    baseline_start: Mapped[date] = mapped_column(Date)
    baseline_end: Mapped[date] = mapped_column(Date)
    forecast_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.NOT_STARTED)


class TaskDependency(Base, IdMixin, TenantMixin):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("predecessor_id", "successor_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    predecessor_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    successor_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))


class Milestone(Base, IdMixin, TenantMixin):
    __tablename__ = "milestones"
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    target_date: Mapped[date] = mapped_column(Date)
    forecast_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="upcoming")


class HardwareRevision(Base, IdMixin, TenantMixin):
    __tablename__ = "hardware_revisions"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")


class HardwareUnit(Base, IdMixin, TenantMixin):
    __tablename__ = "hardware_units"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "serial_number"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    revision_id: Mapped[str] = mapped_column(ForeignKey("hardware_revisions.id"))
    serial_number: Mapped[str] = mapped_column(String(80))
    current_owner: Mapped[str] = mapped_column(String(160), default="Unassigned")
    current_test: Mapped[str | None] = mapped_column(String(160), nullable=True)
    available_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[HardwareStatus] = mapped_column(
        Enum(HardwareStatus), default=HardwareStatus.AVAILABLE
    )
    failure_state: Mapped[str | None] = mapped_column(Text, nullable=True)


class Requirement(Base, IdMixin, TenantMixin):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.NOT_TESTED
    )


class ValidationTest(Base, IdMixin, TenantMixin):
    __tablename__ = "validation_tests"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TestStatus] = mapped_column(Enum(TestStatus), default=TestStatus.NOT_RUN)
    required_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("hardware_revisions.id"), nullable=True
    )


class RequirementTestLink(Base, IdMixin, TenantMixin):
    __tablename__ = "requirement_test_links"
    __table_args__ = (UniqueConstraint("requirement_id", "test_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    test_id: Mapped[str] = mapped_column(ForeignKey("validation_tests.id", ondelete="CASCADE"))
    required: Mapped[int] = mapped_column(Integer, default=1)


class TestTaskLink(Base, IdMixin, TenantMixin):
    __tablename__ = "test_task_links"
    __table_args__ = (UniqueConstraint("test_id", "task_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    test_id: Mapped[str] = mapped_column(ForeignKey("validation_tests.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))


class HardwareAllocation(Base, IdMixin, TenantMixin):
    __tablename__ = "hardware_allocations"
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    hardware_unit_id: Mapped[str] = mapped_column(
        ForeignKey("hardware_units.id", ondelete="CASCADE")
    )
    test_id: Mapped[str | None] = mapped_column(
        ForeignKey("validation_tests.id", ondelete="CASCADE"), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="planned")


class TestRun(Base, IdMixin, TenantMixin):
    __tablename__ = "test_runs"
    __table_args__ = (UniqueConstraint("organization_id", "external_run_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    external_run_id: Mapped[str] = mapped_column(String(120))
    test_id: Mapped[str] = mapped_column(ForeignKey("validation_tests.id"))
    hardware_unit_id: Mapped[str] = mapped_column(ForeignKey("hardware_units.id"))
    measured_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    status: Mapped[TestStatus] = mapped_column(Enum(TestStatus))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Risk(Base, IdMixin, TenantMixin):
    __tablename__ = "risks"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    probability: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    owner: Mapped[str] = mapped_column(String(160), default="Unassigned")
    mitigation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RiskStatus] = mapped_column(Enum(RiskStatus), default=RiskStatus.OPEN)
    affected_milestone_id: Mapped[str | None] = mapped_column(
        ForeignKey("milestones.id"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    @property
    def score(self) -> int:
        return self.probability * self.impact

    @property
    def severity(self) -> str:
        score = self.score
        return (
            "critical"
            if score >= 16
            else "high"
            if score >= 10
            else "medium"
            if score >= 5
            else "low"
        )


class RiskTaskLink(Base, IdMixin, TenantMixin):
    __tablename__ = "risk_task_links"
    __table_args__ = (UniqueConstraint("risk_id", "task_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))


class EngineeringChange(Base, IdMixin, TenantMixin):
    __tablename__ = "engineering_changes"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", "code"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ChangeStatus] = mapped_column(Enum(ChangeStatus), default=ChangeStatus.DRAFT)
    schedule_impact_days: Mapped[int] = mapped_column(Integer, default=0)


class ChangeLink(Base, IdMixin, TenantMixin):
    __tablename__ = "change_links"
    __table_args__ = (UniqueConstraint("change_id", "entity_type", "entity_id"),)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    change_id: Mapped[str] = mapped_column(ForeignKey("engineering_changes.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))


class Scenario(Base, IdMixin, TenantMixin):
    __tablename__ = "scenarios"
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    overrides: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ScenarioOption(Base, IdMixin, TenantMixin):
    __tablename__ = "scenario_options"
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    cost_delta: Mapped[int] = mapped_column(Integer, default=0)
    schedule_delta_days: Mapped[int] = mapped_column(Integer, default=0)
    risk_note: Mapped[str] = mapped_column(Text, default="")


class Decision(Base, IdMixin, TenantMixin):
    __tablename__ = "decisions"
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    selected_option: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="required")
