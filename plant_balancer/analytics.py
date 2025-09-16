from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable, Dict, Iterable, List, Sequence, Tuple, TypeVar

from .models import DaySummary, MachineUsage, Plant, SimulationResult

RESOURCE_CATEGORY = "resource_balance"
MACHINE_CAPACITY_CATEGORY = "machine_capacity"
PRODUCT_CATEGORY = "product_output"


@dataclass(frozen=True)
class HourlyPoint:
    """One value for a specific timestamp."""

    timestamp: datetime
    value: float


@dataclass(frozen=True)
class HourlySeries:
    """Represents a time series expanded to hourly values."""

    id: str
    label: str
    category: str
    unit: str | None
    points: Sequence[HourlyPoint]

    def total(self) -> float:
        return sum(point.value for point in self.points)


def _hourly_points(day: DaySummary, total: float, slots_per_day: int) -> List[HourlyPoint]:
    if slots_per_day <= 0:
        raise ValueError("slots_per_day must be positive")
    base = datetime.combine(day.date, time.min)
    portion = total / slots_per_day
    return [
        HourlyPoint(timestamp=base + timedelta(hours=hour), value=portion)
        for hour in range(slots_per_day)
    ]


_KeyT = TypeVar("_KeyT")


def _expand_daily_values(
    plant: Plant,
    days: Sequence[DaySummary],
    ids: Iterable[_KeyT],
    id_getter: Callable[[_KeyT], str],
    extractor: Callable[[DaySummary, _KeyT], float],
    label_getter: Callable[[Plant, _KeyT], str],
    unit_getter: Callable[[Plant, _KeyT], str | None],
    category: str,
    slots_per_day: int,
) -> List[HourlySeries]:
    series_list: List[HourlySeries] = []
    sorted_days = sorted(days, key=lambda day: day.date)
    for item_id in ids:
        points: List[HourlyPoint] = []
        has_data = False
        for day in sorted_days:
            value = extractor(day, item_id)
            if not has_data and abs(value) > 1e-9:
                has_data = True
            points.extend(_hourly_points(day, value, slots_per_day))
        if not has_data:
            continue
        series_list.append(
            HourlySeries(
                id=id_getter(item_id),
                label=label_getter(plant, item_id),
                category=category,
                unit=unit_getter(plant, item_id),
                points=tuple(points),
            )
        )
    return series_list


def hourly_resource_series(result: SimulationResult, slots_per_day: int = 24) -> List[HourlySeries]:
    plant = result.plant
    resource_ids = set(plant.resources.keys())
    for day in result.days:
        resource_ids.update(day.resource_balance.keys())

    def _extract(day: DaySummary, resource_id: str) -> float:
        return day.resource_balance.get(resource_id, 0.0)

    def _label(_: Plant, resource_id: str) -> str:
        resource = plant.resources.get(resource_id)
        return resource.name if resource else resource_id

    def _unit(_: Plant, resource_id: str) -> str | None:
        resource = plant.resources.get(resource_id)
        if not resource:
            return None
        return resource.unit or None

    return _expand_daily_values(
        plant,
        result.days,
        sorted(resource_ids),
        lambda resource_id: resource_id,
        _extract,
        _label,
        _unit,
        RESOURCE_CATEGORY,
        slots_per_day,
    )


def hourly_product_series(result: SimulationResult, slots_per_day: int = 24) -> List[HourlySeries]:
    plant = result.plant
    product_ids = set(plant.products.keys())
    for day in result.days:
        product_ids.update(day.product_quantities.keys())

    def _extract(day: DaySummary, product_id: str) -> float:
        return day.product_quantities.get(product_id, 0.0)

    def _label(_: Plant, product_id: str) -> str:
        product = plant.products.get(product_id)
        return product.name if product else product_id

    def _unit(_: Plant, product_id: str) -> str | None:
        product = plant.products.get(product_id)
        if not product:
            return None
        return product.unit or None

    return _expand_daily_values(
        plant,
        result.days,
        sorted(product_ids),
        lambda product_id: product_id,
        _extract,
        _label,
        _unit,
        PRODUCT_CATEGORY,
        slots_per_day,
    )


def hourly_machine_capacity_series(result: SimulationResult, slots_per_day: int = 24) -> List[HourlySeries]:
    plant = result.plant
    machine_capacity_ids: Dict[Tuple[str, str], None] = {}
    for day in result.days:
        for machine_id, usage in day.machine_usage.items():
            for capacity_key in usage.capacity_used.keys():
                machine_capacity_ids[(machine_id, capacity_key)] = None

    def _extract(day: DaySummary, key: Tuple[str, str]) -> float:
        machine_id, capacity_key = key
        usage: MachineUsage | None = day.machine_usage.get(machine_id)
        if not usage:
            return 0.0
        return usage.capacity_used.get(capacity_key, 0.0)

    def _label(_: Plant, key: Tuple[str, str]) -> str:
        machine_id, capacity_key = key
        machine = plant.machines.get(machine_id)
        machine_name = machine.name if machine else machine_id
        return f"{machine_name} - {capacity_key}"

    def _unit(_: Plant, key: Tuple[str, str]) -> str | None:
        _machine_id, _capacity_key = key
        return None

    return _expand_daily_values(
        plant,
        result.days,
        sorted(machine_capacity_ids.keys()),
        lambda key: f"{key[0]}::{key[1]}",
        _extract,
        _label,
        _unit,
        MACHINE_CAPACITY_CATEGORY,
        slots_per_day,
    )


def build_hourly_series(result: SimulationResult, slots_per_day: int = 24) -> List[HourlySeries]:
    series: List[HourlySeries] = []
    series.extend(hourly_resource_series(result, slots_per_day=slots_per_day))
    series.extend(hourly_product_series(result, slots_per_day=slots_per_day))
    series.extend(hourly_machine_capacity_series(result, slots_per_day=slots_per_day))
    return series

