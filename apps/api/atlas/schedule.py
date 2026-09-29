from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

import networkx as nx


def next_business_day(value: date) -> date:
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


def add_business_days(start: date, days: int) -> date:
    """Add working days with a task's start counted as day one."""
    current = next_business_day(start)
    if days <= 1:
        return current
    remaining = days - 1
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def business_days_between(start: date, end: date) -> int:
    if start == end:
        return 0
    sign = 1 if end > start else -1
    current = start
    count = 0
    while current != end:
        current += timedelta(days=sign)
        if current.weekday() < 5:
            count += sign
    return count


def business_day_after(value: date) -> date:
    return next_business_day(value + timedelta(days=1))


def subtract_business_days(end: date, days: int) -> date:
    current = next_business_day(end)
    remaining = max(0, days - 1)
    while remaining:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


@dataclass(frozen=True)
class TaskNode:
    id: str
    code: str
    name: str
    duration_days: int
    baseline_start: date
    status: str = "not_started"
    forecast_start: date | None = None
    forecast_end: date | None = None


def analyze_schedule(
    tasks: list[TaskNode],
    dependencies: list[tuple[str, str]],
    delay_overrides: dict[str, int] | None = None,
    target_finish: date | None = None,
) -> dict:
    delay_overrides = delay_overrides or {}
    graph = nx.DiGraph()
    by_id = {task.id: task for task in tasks}
    for task in tasks:
        graph.add_node(task.id)
    graph.add_edges_from(dependencies)
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("Task dependencies must form a directed acyclic graph")

    earliest_start: dict[str, date] = {}
    earliest_finish: dict[str, date] = {}
    path_to: dict[str, list[str]] = {}
    topo = list(nx.topological_sort(graph))

    for task_id in topo:
        task = by_id[task_id]
        predecessors = list(graph.predecessors(task_id))
        controlling = (
            max(predecessors, key=lambda item: earliest_finish[item]) if predecessors else None
        )
        dependency_start = (
            business_day_after(earliest_finish[controlling]) if controlling else task.baseline_start
        )
        start = max(next_business_day(task.baseline_start), dependency_start)
        delay = delay_overrides.get(task_id, 0)
        if delay:
            start = business_day_after(add_business_days(start, delay))
        if task.status == "complete" and task.forecast_start and task.forecast_end:
            start, finish = task.forecast_start, task.forecast_end
        else:
            start = max(start, task.forecast_start or start)
            finish = max(add_business_days(start, task.duration_days), task.forecast_end or start)
        earliest_start[task_id] = start
        earliest_finish[task_id] = finish
        path_to[task_id] = (path_to[controlling] + [task_id]) if controlling else [task_id]

    project_finish = max(earliest_finish.values()) if tasks else datetime.now(UTC).date()
    # CPM slack is measured against the earliest possible project finish. Program
    # target margin is reported separately so a healthy plan still has a critical path.
    deadline = project_finish
    target_deadline = target_finish or project_finish
    latest_finish: dict[str, date] = {}
    latest_start: dict[str, date] = {}
    for task_id in reversed(topo):
        successors = list(graph.successors(task_id))
        finish = (
            min(latest_start[item] - timedelta(days=1) for item in successors)
            if successors
            else deadline
        )
        finish = (
            next_business_day(finish)
            if finish.weekday() < 5
            else finish - timedelta(days=finish.weekday() - 4)
        )
        latest_finish[task_id] = finish
        latest_start[task_id] = subtract_business_days(finish, by_id[task_id].duration_days)

    rows = []
    for task_id in topo:
        slack = business_days_between(earliest_start[task_id], latest_start[task_id])
        task = by_id[task_id]
        rows.append(
            {
                "id": task_id,
                "code": task.code,
                "name": task.name,
                "earliest_start": earliest_start[task_id],
                "earliest_finish": earliest_finish[task_id],
                "latest_start": latest_start[task_id],
                "latest_finish": latest_finish[task_id],
                "slack_days": slack,
                "is_critical": slack == 0,
                "forecast_start": earliest_start[task_id],
                "forecast_finish": earliest_finish[task_id],
            }
        )
    terminal = max(topo, key=lambda item: earliest_finish[item]) if topo else None
    critical_path = [
        item
        for item in path_to.get(terminal, [])
        if next(row for row in rows if row["id"] == item)["is_critical"]
    ]
    return {
        "tasks": rows,
        "critical_path": critical_path,
        "project_finish": project_finish,
        "target_finish": target_deadline,
        "variance_days": max(0, business_days_between(target_deadline, project_finish)),
        "available_slack_days": max(0, business_days_between(project_finish, target_deadline)),
        "dependency_paths": path_to,
    }


def with_delay(task: TaskNode, days: int) -> TaskNode:
    return replace(
        task, forecast_start=business_day_after(add_business_days(task.baseline_start, days))
    )
