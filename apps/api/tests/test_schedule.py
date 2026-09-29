from datetime import date
from time import perf_counter

import pytest

from atlas.schedule import TaskNode, add_business_days, analyze_schedule, business_day_after


def node(code: str, start: date, duration: int = 1) -> TaskNode:
    return TaskNode(id=code, code=code, name=code, duration_days=duration, baseline_start=start)


def test_business_days_skip_weekends():
    friday = date(2026, 10, 2)
    assert add_business_days(friday, 2) == date(2026, 10, 5)
    assert business_day_after(friday) == date(2026, 10, 5)


def test_critical_path_and_target_margin_are_separate():
    start = date(2026, 10, 5)
    tasks = [node("A", start, 3), node("B", start, 2), node("C", start, 4)]
    result = analyze_schedule(tasks, [("A", "C")], target_finish=date(2026, 10, 16))
    assert result["critical_path"] == ["A", "C"]
    assert result["available_slack_days"] == 3
    by_id = {item["id"]: item for item in result["tasks"]}
    assert by_id["B"]["slack_days"] > 0


def test_cycle_is_rejected():
    tasks = [node("A", date(2026, 1, 5)), node("B", date(2026, 1, 5))]
    with pytest.raises(ValueError, match="directed acyclic graph"):
        analyze_schedule(tasks, [("A", "B"), ("B", "A")])


def test_delay_consumes_margin_before_target_slips():
    start = date(2026, 10, 5)
    tasks = [node("A", start, 2), node("B", start, 2)]
    baseline = analyze_schedule(tasks, [("A", "B")], target_finish=date(2026, 10, 12))
    delayed = analyze_schedule(tasks, [("A", "B")], {"A": 3}, target_finish=date(2026, 10, 12))
    assert baseline["available_slack_days"] == 2
    assert delayed["variance_days"] == 1


def test_seed_scale_analysis_is_under_one_second():
    start = date(2026, 1, 5)
    tasks = [node(str(index), start, 2 + index % 4) for index in range(50)]
    edges = [(str(index), str(index + 1)) for index in range(49)]
    before = perf_counter()
    result = analyze_schedule(tasks, edges)
    elapsed = perf_counter() - before
    assert len(result["tasks"]) == 50
    assert elapsed < 1
