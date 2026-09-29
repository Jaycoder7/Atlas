from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import AuthContext, get_auth_context, require_admin
from .database import get_db
from .models import (
    ChangeLink,
    HardwareAllocation,
    Program,
    RequirementTestLink,
    ServiceClient,
    TaskDependency,
    ValidationTest,
)
from .resources import (
    get_model,
    get_resource,
    list_resources,
    prepare_payload,
    validate_tenant_references,
)
from .schemas import (
    DependencyCreate,
    ProgramCreate,
    ProgramRead,
    ScenarioEvaluate,
    TestRunCreate,
)
from .services import (
    assert_program,
    change_impact,
    dashboard,
    evaluate_scenario,
    get_schedule,
    hardware_warnings,
    ingest_test_run,
    model_dict,
    ollama_suggestions,
    update_requirement_statuses,
    validate_dependency,
)

router = APIRouter(prefix="/api/v1")


def resolve_org(auth: AuthContext, db: Session) -> str:
    if auth.organization_id:
        return auth.organization_id
    if auth.client_id:
        client = db.scalar(
            select(ServiceClient).where(ServiceClient.auth0_client_id == auth.client_id)
        )
        if client:
            return client.organization_id
    raise HTTPException(
        status_code=403, detail="Token is not associated with an Atlas organization"
    )


@router.get("/programs", response_model=list[ProgramRead])
def list_programs(auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    org_id = resolve_org(auth, db)
    return list(
        db.scalars(select(Program).where(Program.organization_id == org_id).order_by(Program.name))
    )


@router.post("/programs", response_model=ProgramRead, status_code=201)
def create_program(
    payload: ProgramCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    program = Program(organization_id=org_id, **payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.get("/programs/{program_id}", response_model=ProgramRead)
def get_program(
    program_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
):
    return assert_program(db, resolve_org(auth, db), program_id)


@router.delete("/programs/{program_id}", status_code=204)
def delete_program(
    program_id: str,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    program = assert_program(db, resolve_org(auth, db), program_id)
    db.delete(program)
    db.commit()
    return Response(status_code=204)


@router.get("/programs/{program_id}/resources/{resource}")
def resources_list(
    program_id: str,
    resource: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    assert_program(db, org_id, program_id)
    try:
        model = get_model(resource)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return list_resources(db, model, org_id, program_id)


@router.post("/programs/{program_id}/resources/{resource}", status_code=201)
def resources_create(
    program_id: str,
    resource: str,
    payload: dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    assert_program(db, org_id, program_id)
    try:
        model = get_model(resource)
        values = prepare_payload(model, payload)
        validate_tenant_references(db, org_id, program_id, values)
        if model is ChangeLink:
            _validate_change_link(db, org_id, program_id, values)
        item = model(
            organization_id=org_id,
            **({"program_id": program_id} if hasattr(model, "program_id") else {}),
            **values,
        )
        db.add(item)
        db.flush()
        if isinstance(item, (HardwareAllocation, RequirementTestLink)) and item.test_id:
            update_requirement_statuses(db, org_id, program_id, item.test_id)
        db.commit()
        db.refresh(item)
        return model_dict(item)
    except (KeyError, ValueError, TypeError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/programs/{program_id}/resources/{resource}/{item_id}")
def resources_update(
    program_id: str,
    resource: str,
    item_id: str,
    payload: dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    assert_program(db, org_id, program_id)
    try:
        model = get_model(resource)
        item = get_resource(db, model, org_id, item_id)
        if not item or (hasattr(item, "program_id") and item.program_id != program_id):
            raise HTTPException(status_code=404, detail="Resource not found")
        values = prepare_payload(model, payload, partial=True)
        validate_tenant_references(db, org_id, program_id, values)
        for key, value in values.items():
            setattr(item, key, value)
        if isinstance(item, (HardwareAllocation, RequirementTestLink)) and item.test_id:
            update_requirement_statuses(db, org_id, program_id, item.test_id)
        elif isinstance(item, ValidationTest):
            update_requirement_statuses(db, org_id, program_id, item.id)
        db.commit()
        db.refresh(item)
        return model_dict(item)
    except (KeyError, ValueError, TypeError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/programs/{program_id}/resources/{resource}/{item_id}", status_code=204)
def resources_delete(
    program_id: str,
    resource: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    try:
        model = get_model(resource)
        item = get_resource(db, model, org_id, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not item or (hasattr(item, "program_id") and item.program_id != program_id):
        raise HTTPException(status_code=404, detail="Resource not found")
    affected_test_id = (
        item.test_id if isinstance(item, (HardwareAllocation, RequirementTestLink)) else None
    )
    db.delete(item)
    db.flush()
    if affected_test_id:
        update_requirement_statuses(db, org_id, program_id, affected_test_id)
    db.commit()
    return Response(status_code=204)


@router.get("/programs/{program_id}/snapshot")
def snapshot(
    program_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
):
    org_id = resolve_org(auth, db)
    program = assert_program(db, org_id, program_id)
    names = [
        "teams",
        "tasks",
        "milestones",
        "hardware-revisions",
        "hardware-units",
        "allocations",
        "requirements",
        "tests",
        "requirement-test-links",
        "test-task-links",
        "risks",
        "engineering-changes",
        "change-links",
        "scenarios",
        "decisions",
    ]
    return {
        "program": model_dict(program),
        "resources": {
            name: list_resources(db, get_model(name), org_id, program_id) for name in names
        },
        "hardware_warnings": hardware_warnings(db, org_id, program_id),
    }


@router.post("/programs/{program_id}/dependencies", status_code=201)
def create_dependency(
    program_id: str,
    payload: DependencyCreate,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    try:
        validate_dependency(db, org_id, program_id, payload.predecessor_id, payload.successor_id)
        item = TaskDependency(
            organization_id=org_id,
            program_id=program_id,
            predecessor_id=payload.predecessor_id,
            successor_id=payload.successor_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return model_dict(item)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/programs/{program_id}/dependencies")
def list_dependencies(
    program_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
):
    org_id = resolve_org(auth, db)
    assert_program(db, org_id, program_id)
    return [
        model_dict(item)
        for item in db.scalars(
            select(TaskDependency).where(
                TaskDependency.organization_id == org_id, TaskDependency.program_id == program_id
            )
        )
    ]


@router.delete("/programs/{program_id}/dependencies/{dependency_id}", status_code=204)
def delete_dependency(
    program_id: str,
    dependency_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    result = db.execute(
        delete(TaskDependency).where(
            TaskDependency.id == dependency_id,
            TaskDependency.organization_id == org_id,
            TaskDependency.program_id == program_id,
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Dependency not found")
    db.commit()
    return Response(status_code=204)


@router.get("/schedule/analyze")
def schedule_analyze(
    program_id: str = Query(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    try:
        result = get_schedule(db, resolve_org(auth, db), program_id)
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test-runs", status_code=201)
def test_run_create(
    payload: TestRunCreate,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    auth.require_scope("test-results:write")
    try:
        run, created = ingest_test_run(db, resolve_org(auth, db), payload)
        if not created:
            response.status_code = status.HTTP_200_OK
        return {"created": created, "run": model_dict(run)}
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dashboard")
def dashboard_get(
    program_id: str = Query(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    result = dashboard(db, resolve_org(auth, db), program_id)
    db.commit()
    return result


@router.post("/scenarios/evaluate")
def scenario_evaluate(
    payload: ScenarioEvaluate,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    return evaluate_scenario(db, resolve_org(auth, db), payload)


@router.get("/changes/{change_id}/impact")
def impact_get(
    change_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
):
    try:
        return change_impact(db, resolve_org(auth, db), change_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/changes/{change_id}/suggestions")
async def suggestions_get(
    change_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    return await ollama_suggestions(db, resolve_org(auth, db), change_id)


@router.post("/changes/{change_id}/suggestions/accept", status_code=201)
def suggestion_accept(
    change_id: str,
    payload: dict[str, str] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    org_id = resolve_org(auth, db)
    impact = change_impact(db, org_id, change_id)
    values = {
        "change_id": change_id,
        "entity_type": payload.get("entity_type"),
        "entity_id": payload.get("entity_id"),
    }
    _validate_change_link(db, org_id, impact["change"]["program_id"], values)
    link = ChangeLink(organization_id=org_id, program_id=impact["change"]["program_id"], **values)
    db.add(link)
    db.commit()
    db.refresh(link)
    return model_dict(link)


@router.get("/admin/service-clients")
def service_clients(auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    return [
        model_dict(item)
        for item in db.scalars(
            select(ServiceClient).where(ServiceClient.organization_id == resolve_org(auth, db))
        )
    ]


@router.post("/admin/service-clients", status_code=201)
def service_client_create(
    payload: dict[str, str] = Body(...),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = ServiceClient(
        organization_id=resolve_org(auth, db),
        auth0_client_id=payload["auth0_client_id"],
        name=payload["name"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return model_dict(item)


def _validate_change_link(
    db: Session, org_id: str, program_id: str, values: dict[str, Any]
) -> None:
    model_by_type = {
        "requirement": get_model("requirements"),
        "test": get_model("tests"),
        "hardware_revision": get_model("hardware-revisions"),
        "hardware_unit": get_model("hardware-units"),
        "task": get_model("tasks"),
        "milestone": get_model("milestones"),
    }
    model = model_by_type.get(values.get("entity_type"))
    if not model:
        raise ValueError("Unsupported change-link entity type")
    item = get_resource(db, model, org_id, values.get("entity_id", ""))
    if not item or item.program_id != program_id:
        raise ValueError("Linked entity must belong to the active organization and program")
