from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import (
    ChangeLink,
    ChangeStatus,
    Decision,
    EngineeringChange,
    HardwareAllocation,
    HardwareRevision,
    HardwareStatus,
    HardwareUnit,
    Milestone,
    Organization,
    Program,
    Requirement,
    RequirementTestLink,
    Risk,
    RiskStatus,
    Scenario,
    ScenarioOption,
    Task,
    TaskDependency,
    Team,
    TestStatus,
    TestTaskLink,
    ValidationTest,
)
from .schedule import add_business_days, business_day_after, next_business_day
from .services import get_schedule

PROGRAM_NAME = "Avionics Telemetry Module"
TEAM_NAMES = [
    "Electrical",
    "Embedded Software",
    "Systems",
    "Validation",
    "Mechanical",
    "Manufacturing",
]


def next_monday(value: date) -> date:
    return value + timedelta(days=(7 - value.weekday()) % 7 or 7)


def seed(start_date: date | None = None, reset: bool = False) -> str:
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    org_id = settings.atlas_demo_org_id
    start_date = next_business_day(start_date or next_monday(datetime.now(UTC).date()))
    with SessionLocal() as db:
        organization = db.scalar(select(Organization).where(Organization.auth0_org_id == org_id))
        if not organization:
            db.add(Organization(auth0_org_id=org_id, name="Atlas Demo Organization"))
        existing = db.scalar(
            select(Program).where(Program.organization_id == org_id, Program.name == PROGRAM_NAME)
        )
        if existing and not reset:
            return existing.id
        if existing:
            db.delete(existing)
            db.commit()

        program = Program(
            organization_id=org_id,
            name=PROGRAM_NAME,
            description="Connected development plan for a six-team avionics telemetry module.",
            start_date=start_date,
        )
        db.add(program)
        db.flush()

        teams = [
            Team(organization_id=org_id, program_id=program.id, name=name) for name in TEAM_NAMES
        ]
        db.add_all(teams)
        db.flush()

        task_names = [
            "System architecture",
            "Sensor trade study",
            "Power budget",
            "PCB Rev B schematic",
            "PCB Rev B layout",
            "PCB Rev B fabrication",
            "Rev B assembly",
            "Rev B bring-up",
            "Bootloader implementation",
            "Telemetry protocol",
            "Sensor drivers",
            "CAN interface",
            "Enclosure concept",
            "Thermal model",
            "Mechanical drawings",
            "Prototype machining",
            "Manufacturing test plan",
            "Supplier qualification",
            "Requirements review",
            "Design review",
            "PCB Rev C changes",
            "PCB Rev C layout",
            "PCB Rev C fabrication",
            "Rev C assembly",
            "Rev C hardware bring-up",
            "Firmware integration",
            "Bench validation setup",
            "Telemetry-rate test",
            "Packet-loss test",
            "Brownout recovery test",
            "Thermal chamber setup",
            "Thermal validation",
            "Vibration fixture",
            "Vibration test",
            "EMI pre-scan",
            "Power-cycle campaign",
            "Regression campaign",
            "Failure review",
            "Corrective action",
            "Validation rerun",
            "Manufacturing work instructions",
            "End-of-line fixture",
            "Pilot build material",
            "Pilot build",
            "Pilot build acceptance",
            "Release documentation",
            "Safety review",
            "Production readiness review",
            "Release candidate",
            "Program release",
        ]
        tasks: list[Task] = []
        cursor = start_date
        for index, name in enumerate(task_names, 1):
            duration = 2 + (index % 4)
            task = Task(
                organization_id=org_id,
                program_id=program.id,
                team_id=teams[(index - 1) % len(teams)].id,
                code=f"TASK-{index:03d}",
                name=name,
                description=f"Planned work for {name.lower()}.",
                owner=f"{TEAM_NAMES[(index - 1) % len(teams)]} Lead",
                duration_days=duration,
                baseline_start=cursor,
                baseline_end=add_business_days(cursor, duration),
            )
            tasks.append(task)
            db.add(task)
            cursor = business_day_after(task.baseline_end)
        db.flush()

        # A main chain plus cross-discipline branches converging on validation and release.
        dependency_pairs = [(index, index + 1) for index in range(1, 50)]
        dependency_pairs += [(2, 18), (9, 25), (13, 30), (17, 40), (24, 30), (31, 36), (39, 44)]
        for left, right in dependency_pairs:
            db.add(
                TaskDependency(
                    organization_id=org_id,
                    program_id=program.id,
                    predecessor_id=tasks[left - 1].id,
                    successor_id=tasks[right - 1].id,
                )
            )

        release_target = add_business_days(tasks[-1].baseline_end, 4)
        milestones = [
            Milestone(
                organization_id=org_id,
                program_id=program.id,
                name="Critical Design Review",
                target_date=tasks[19].baseline_end,
                task_id=tasks[19].id,
            ),
            Milestone(
                organization_id=org_id,
                program_id=program.id,
                name="Rev C Ready",
                target_date=tasks[24].baseline_end,
                task_id=tasks[24].id,
            ),
            Milestone(
                organization_id=org_id,
                program_id=program.id,
                name="Validation Complete",
                target_date=tasks[39].baseline_end,
                task_id=tasks[39].id,
            ),
            Milestone(
                organization_id=org_id,
                program_id=program.id,
                name="Program Release",
                target_date=release_target,
                task_id=tasks[-1].id,
            ),
        ]
        db.add_all(milestones)
        db.flush()

        rev_b = HardwareRevision(
            organization_id=org_id,
            program_id=program.id,
            code="Rev B",
            description="Bring-up revision",
        )
        rev_c = HardwareRevision(
            organization_id=org_id,
            program_id=program.id,
            code="Rev C",
            description="Validation candidate",
        )
        db.add_all([rev_b, rev_c])
        db.flush()
        units = [
            HardwareUnit(
                organization_id=org_id,
                program_id=program.id,
                revision_id=rev_b.id,
                serial_number="P1-001",
                current_owner="Embedded Software",
                available_date=start_date,
                status=HardwareStatus.AVAILABLE,
            ),
            HardwareUnit(
                organization_id=org_id,
                program_id=program.id,
                revision_id=rev_b.id,
                serial_number="P1-002",
                current_owner="Electrical",
                available_date=start_date,
                status=HardwareStatus.AVAILABLE,
            ),
            HardwareUnit(
                organization_id=org_id,
                program_id=program.id,
                revision_id=rev_c.id,
                serial_number="P1-003",
                current_owner="Validation",
                current_test="Thermal Validation",
                available_date=tasks[30].baseline_start,
                status=HardwareStatus.TESTING,
            ),
            HardwareUnit(
                organization_id=org_id,
                program_id=program.id,
                revision_id=rev_c.id,
                serial_number="P1-004",
                current_owner="Systems",
                available_date=tasks[32].baseline_start,
                status=HardwareStatus.AVAILABLE,
            ),
        ]
        db.add_all(units)
        db.flush()

        requirements: list[Requirement] = []
        requirement_titles = [
            "Telemetry rate shall be at least 100 Hz",
            "Operating temperature shall be 0–50°C",
            "Packet loss shall remain below 1%",
            "Brownout recovery shall complete within 2 seconds",
        ]
        for index in range(1, 31):
            title = (
                requirement_titles[index - 1]
                if index <= 4
                else f"Engineering requirement {index:02d}"
            )
            if index == 14:
                title = "Voltage regulator shall remain within limits during thermal operation"
            requirement = Requirement(
                organization_id=org_id,
                program_id=program.id,
                code=f"REQ-{index:03d}",
                title=title,
                description=f"Verification requirement for telemetry module capability {index:02d}.",
            )
            requirements.append(requirement)
            db.add(requirement)
        db.flush()

        tests: list[ValidationTest] = []
        for index in range(1, 41):
            name = f"Validation procedure {index:02d}"
            if index == 21:
                name = "Rev C thermal validation"
            test = ValidationTest(
                organization_id=org_id,
                program_id=program.id,
                code=f"TEST-{index:03d}",
                name=name,
                description=f"Automated validation procedure {index:02d}.",
                required_revision_id=rev_c.id if index >= 20 else rev_b.id,
                status=TestStatus.NOT_RUN,
            )
            tests.append(test)
            db.add(test)
        db.flush()
        for index, requirement in enumerate(requirements):
            linked_test = tests[20] if requirement.code == "REQ-014" else tests[index % len(tests)]
            db.add(
                RequirementTestLink(
                    organization_id=org_id,
                    program_id=program.id,
                    requirement_id=requirement.id,
                    test_id=linked_test.id,
                    required=1,
                )
            )
        for index, test in enumerate(tests):
            linked_task = tasks[27 + (index % 13)]
            db.add(
                TestTaskLink(
                    organization_id=org_id,
                    program_id=program.id,
                    test_id=test.id,
                    task_id=linked_task.id,
                )
            )

        db.add(
            HardwareAllocation(
                organization_id=org_id,
                program_id=program.id,
                hardware_unit_id=units[2].id,
                test_id=tests[20].id,
                task_id=tasks[31].id,
                start_date=tasks[31].baseline_start,
                end_date=tasks[31].baseline_end,
                status="active",
            )
        )

        risks: list[Risk] = []
        descriptions = [
            "PCB supplier delay",
            "Sensor allocation shortage",
            "Firmware integration overrun",
            "Thermal margin below target",
            "EMI susceptibility",
            "Prototype damage",
            "Test chamber availability",
            "Manufacturing fixture delay",
            "CAN interoperability",
            "Requirements churn",
        ]
        for index, description in enumerate(descriptions, 1):
            risk = Risk(
                organization_id=org_id,
                program_id=program.id,
                code=f"RISK-{index:03d}",
                description=description,
                probability=1 + (index % 5),
                impact=1 + ((index + 2) % 5),
                owner=f"{TEAM_NAMES[(index - 1) % len(teams)]} Lead",
                mitigation="Track leading indicator and execute contingency when threshold is crossed.",
                status=RiskStatus.OPEN,
                affected_milestone_id=milestones[min(index // 3, len(milestones) - 1)].id,
            )
            risks.append(risk)
            db.add(risk)

        changes: list[EngineeringChange] = []
        change_specs = [
            ("EC-013", "Update IMU selection", 2),
            ("EC-014", "Revise telemetry packet", 1),
            ("EC-015", "Add enclosure venting", 3),
            ("EC-016", "Update CAN termination", 1),
            ("EC-017", "Replace voltage regulator on PCB Rev C", 4),
        ]
        for code, title, impact in change_specs:
            change = EngineeringChange(
                organization_id=org_id,
                program_id=program.id,
                code=code,
                title=title,
                description=f"Engineering assessment and implementation for {title.lower()}.",
                schedule_impact_days=impact,
                status=ChangeStatus.REVIEW if code == "EC-017" else ChangeStatus.DRAFT,
            )
            changes.append(change)
            db.add(change)
        db.flush()
        for entity_type, entity_id in [
            ("requirement", requirements[13].id),
            ("test", tests[20].id),
            ("hardware_revision", rev_c.id),
            ("task", tasks[20].id),
        ]:
            db.add(
                ChangeLink(
                    organization_id=org_id,
                    program_id=program.id,
                    change_id=changes[-1].id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )

        scenario = Scenario(
            organization_id=org_id,
            program_id=program.id,
            name="PCB Rev C eight-day delay",
            overrides=[{"kind": "task_delay", "entity_id": tasks[22].id, "delay_business_days": 8}],
            result={},
        )
        db.add(scenario)
        db.flush()
        db.add_all(
            [
                ScenarioOption(
                    organization_id=org_id,
                    scenario_id=scenario.id,
                    name="Wait for PCB",
                    cost_delta=0,
                    schedule_delta_days=0,
                    risk_note="Low",
                ),
                ScenarioOption(
                    organization_id=org_id,
                    scenario_id=scenario.id,
                    name="Expedite fabrication",
                    cost_delta=1400,
                    schedule_delta_days=-4,
                    risk_note="Low",
                ),
                ScenarioOption(
                    organization_id=org_id,
                    scenario_id=scenario.id,
                    name="Continue Rev B testing",
                    cost_delta=0,
                    schedule_delta_days=-5,
                    risk_note="Medium technical risk",
                ),
            ]
        )
        db.add(
            Decision(
                organization_id=org_id,
                program_id=program.id,
                scenario_id=scenario.id,
                title="Select Rev C schedule mitigation",
                rationale="Compare schedule, cost, and technical exposure before committing.",
                status="required",
            )
        )
        db.commit()
        get_schedule(db, org_id, program.id)
        db.commit()
        return program.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Atlas avionics demo")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    program_id = seed(args.start_date, args.reset)
    print(f"Atlas demo ready: {program_id}")


if __name__ == "__main__":
    main()
