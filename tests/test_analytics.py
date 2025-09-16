from datetime import date

import pytest

import sys
from pathlib import Path

# Ensure package import works when running tests from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plant_balancer.analytics import (
    MACHINE_CAPACITY_CATEGORY,
    PRODUCT_CATEGORY,
    RESOURCE_CATEGORY,
    build_hourly_series,
    hourly_machine_capacity_series,
    hourly_product_series,
    hourly_resource_series,
)
from plant_balancer.models import (
    DaySummary,
    Machine,
    MachineGroup,
    MachineUsage,
    Plant,
    Product,
    SimulationResult,
    Resource,
)


def _make_sample_result() -> SimulationResult:
    plant = Plant(
        resources={
            "steam": Resource(id="steam", name="Vapor", unit="t"),
            "fiber": Resource(id="fiber", name="Fibra", unit="t"),
        },
        machine_groups={"dig": MachineGroup(id="dig", name="Digestores")},
        machines={
            "D1": Machine(id="D1", name="Digestor 1", group_id="dig", capacity={"ton": 120.0}),
        },
        products={
            "pulp": Product(id="pulp", name="Polpa", unit="t", steps=[]),
        },
    )

    day1 = DaySummary(
        date=date(2024, 1, 1),
        product_quantities={"pulp": 100.0},
        machine_usage={
            "D1": MachineUsage(
                machine=plant.machines["D1"],
                capacity_used={"ton": 90.0},
                resource_balance={"steam": -30.0, "fiber": -70.0},
            )
        },
        resource_balance={"steam": -30.0, "fiber": -70.0},
    )

    day2 = DaySummary(
        date=date(2024, 1, 2),
        product_quantities={"pulp": 80.0},
        machine_usage={
            "D1": MachineUsage(
                machine=plant.machines["D1"],
                capacity_used={"ton": 60.0},
                resource_balance={"steam": -18.0, "fiber": -50.0},
            )
        },
        resource_balance={"steam": -18.0, "fiber": -50.0},
    )

    return SimulationResult(plant=plant, days=[day1, day2])


def test_hourly_resource_series_preserves_daily_totals():
    result = _make_sample_result()
    series = hourly_resource_series(result)
    steam = next(item for item in series if item.id == "steam")

    assert steam.category == RESOURCE_CATEGORY
    assert steam.unit == "t"
    assert len(steam.points) == 48

    first_day_total = sum(point.value for point in steam.points[:24])
    second_day_total = sum(point.value for point in steam.points[24:])
    assert first_day_total == pytest.approx(-30.0)
    assert second_day_total == pytest.approx(-18.0)


def test_hourly_product_series_uses_product_units():
    result = _make_sample_result()
    series = hourly_product_series(result)
    pulp = next(item for item in series if item.id == "pulp")

    assert pulp.category == PRODUCT_CATEGORY
    assert pulp.unit == "t"
    assert len(pulp.points) == 48
    assert sum(point.value for point in pulp.points[:24]) == pytest.approx(100.0)
    assert sum(point.value for point in pulp.points[24:]) == pytest.approx(80.0)


def test_hourly_machine_capacity_series_identifies_machine_and_metric():
    result = _make_sample_result()
    series = hourly_machine_capacity_series(result)
    assert len(series) == 1
    capacity = series[0]
    assert capacity.category == MACHINE_CAPACITY_CATEGORY
    assert capacity.id == "D1::ton"
    assert "Digestor 1" in capacity.label
    assert sum(point.value for point in capacity.points[:24]) == pytest.approx(90.0)
    assert sum(point.value for point in capacity.points[24:]) == pytest.approx(60.0)


def test_build_hourly_series_combines_all_categories():
    result = _make_sample_result()
    series = build_hourly_series(result)
    categories = {item.category for item in series}
    assert categories == {RESOURCE_CATEGORY, PRODUCT_CATEGORY, MACHINE_CAPACITY_CATEGORY}
