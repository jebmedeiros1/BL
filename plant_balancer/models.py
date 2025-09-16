from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Resource:
    """Represents a material or utility tracked by the model."""

    id: str
    name: str
    unit: str


@dataclass(frozen=True)
class MachineGroup:
    """Logical group of machines with the same function."""

    id: str
    name: str


@dataclass
class Machine:
    """Physical equipment with an optional daily capacity per metric."""

    id: str
    name: str
    group_id: str
    capacity: Dict[str, float] = field(default_factory=dict)


@dataclass
class RecipeStep:
    """One step of a production recipe."""

    name: str
    target: str  # "group", "machine", or "order_machine"
    machine_id: Optional[str] = None
    group_id: Optional[str] = None
    required_group: Optional[str] = None
    allocation: Optional[Dict[str, float]] = None
    capacity_usage: Dict[str, float] = field(default_factory=dict)
    resource_changes: Dict[str, float] = field(default_factory=dict)


@dataclass
class Product:
    """Product manufactured by the plant."""

    id: str
    name: str
    unit: str
    steps: List[RecipeStep]


@dataclass(frozen=True)
class ProductionOrder:
    """Planned production quantity for a given day and machine."""

    date: date
    product_id: str
    machine_id: str
    quantity: float


@dataclass
class MachineUsage:
    """Aggregated usage of a machine during one day."""

    machine: Machine
    capacity_used: Dict[str, float] = field(default_factory=dict)
    resource_balance: Dict[str, float] = field(default_factory=dict)

    def add_capacity(self, values: Dict[str, float]) -> None:
        for key, value in values.items():
            if value == 0:
                continue
            self.capacity_used[key] = self.capacity_used.get(key, 0.0) + value

    def add_resource_balance(self, values: Dict[str, float]) -> None:
        for key, value in values.items():
            if value == 0:
                continue
            self.resource_balance[key] = self.resource_balance.get(key, 0.0) + value

    def utilization(self, capacity_key: str) -> Optional[float]:
        capacity = self.machine.capacity.get(capacity_key)
        if capacity in (None, 0):
            return None
        used = self.capacity_used.get(capacity_key, 0.0)
        return used / capacity


@dataclass
class DaySummary:
    """Summary of production, resource balance and machine usage for a single day."""

    date: date
    product_quantities: Dict[str, float]
    machine_usage: Dict[str, MachineUsage]
    resource_balance: Dict[str, float]

    def capacity_alerts(self) -> List[Dict[str, object]]:
        alerts: List[Dict[str, object]] = []
        for usage in self.machine_usage.values():
            for key, used in usage.capacity_used.items():
                capacity = usage.machine.capacity.get(key)
                if capacity not in (None, 0) and used > capacity:
                    alerts.append(
                        {
                            "machine_id": usage.machine.id,
                            "machine_name": usage.machine.name,
                            "capacity_key": key,
                            "used": used,
                            "limit": capacity,
                        }
                    )
        return alerts


@dataclass
class SimulationResult:
    """Holds the outcome of a production plan simulation."""

    plant: "Plant"
    days: List[DaySummary]

    def overall_resource_balance(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for day in self.days:
            for resource_id, value in day.resource_balance.items():
                totals[resource_id] = totals.get(resource_id, 0.0) + value
        return totals

    def overall_product_quantities(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for day in self.days:
            for product_id, quantity in day.product_quantities.items():
                totals[product_id] = totals.get(product_id, 0.0) + quantity
        return totals


@dataclass
class Plant:
    """Complete representation of the plant configuration."""

    resources: Dict[str, Resource]
    machine_groups: Dict[str, MachineGroup]
    machines: Dict[str, Machine]
    products: Dict[str, Product]
    machines_by_group: Dict[str, List[Machine]] = field(init=False)

    def __post_init__(self) -> None:
        mapping: Dict[str, List[Machine]] = {group_id: [] for group_id in self.machine_groups}
        for machine in self.machines.values():
            mapping.setdefault(machine.group_id, []).append(machine)
        self.machines_by_group = mapping

    def get_machine(self, machine_id: str) -> Machine:
        try:
            return self.machines[machine_id]
        except KeyError as exc:
            raise KeyError(f"Unknown machine '{machine_id}'") from exc

    def get_product(self, product_id: str) -> Product:
        try:
            return self.products[product_id]
        except KeyError as exc:
            raise KeyError(f"Unknown product '{product_id}'") from exc

    def machines_in_group(self, group_id: str) -> List[Machine]:
        machines = self.machines_by_group.get(group_id)
        if machines is None:
            raise KeyError(f"Unknown machine group '{group_id}'")
        if not machines:
            raise ValueError(f"No machines registered in group '{group_id}'")
        return machines
