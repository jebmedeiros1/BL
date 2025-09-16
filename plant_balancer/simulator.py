from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Tuple

from .models import DaySummary, Machine, MachineUsage, Plant, ProductionOrder, RecipeStep, SimulationResult


class SimulationError(RuntimeError):
    """Raised when the production plan cannot be simulated."""


def _normalize_allocation(machines: Iterable[Machine], allocation: Dict[str, float] | None) -> Dict[str, float]:
    machines = list(machines)
    if not machines:
        raise ValueError("Cannot allocate recipe step without available machines")
    if not allocation:
        share = 1.0 / len(machines)
        return {machine.id: share for machine in machines}
    normalized: Dict[str, float] = {}
    total = 0.0
    for machine in machines:
        if machine.id in allocation:
            value = allocation[machine.id]
            if value < 0:
                raise SimulationError(f"Allocation for machine '{machine.id}' cannot be negative")
            normalized[machine.id] = float(value)
            total += float(value)
    if not normalized:
        raise SimulationError("Allocation provided does not match any machine in the group")
    if total == 0:
        share = 1.0 / len(normalized)
        return {machine_id: share for machine_id in normalized}
    return {machine_id: value / total for machine_id, value in normalized.items()}


def _resolve_step_machines(step: RecipeStep, order: ProductionOrder, plant: Plant) -> List[Tuple[Machine, float]]:
    if step.target == "order_machine":
        machine = plant.get_machine(order.machine_id)
        if step.required_group and machine.group_id != step.required_group:
            raise SimulationError(
                f"Ordem para '{order.product_id}' usa máquina '{machine.id}' fora do grupo requerido '{step.required_group}'"
            )
        return [(machine, 1.0)]
    if step.target == "machine":
        if not step.machine_id:
            raise SimulationError(f"Etapa '{step.name}' requer 'machine_id'")
        machine = plant.get_machine(step.machine_id)
        return [(machine, 1.0)]
    if step.target == "group":
        if not step.group_id:
            raise SimulationError(f"Etapa '{step.name}' requer 'group_id'")
        machines = plant.machines_in_group(step.group_id)
        allocation = _normalize_allocation(machines, step.allocation)
        resolved = []
        for machine in machines:
            share = allocation.get(machine.id)
            if share:
                resolved.append((machine, share))
        if not resolved:
            raise SimulationError(f"Etapa '{step.name}' não possui alocação válida de equipamentos")
        return resolved
    raise SimulationError(f"Alvo de etapa desconhecido: {step.target}")


def _scale_values(values: Dict[str, float], factor: float) -> Dict[str, float]:
    return {key: value * factor for key, value in values.items()}


def simulate(plant: Plant, plan: Iterable[ProductionOrder]) -> SimulationResult:
    """Simulate how the plant behaves for the given production plan."""

    orders_by_day: Dict[date, List[ProductionOrder]] = defaultdict(list)
    for order in plan:
        orders_by_day[order.date].append(order)

    days: List[DaySummary] = []
    for current_day in sorted(orders_by_day.keys()):
        day_orders = orders_by_day[current_day]
        product_totals: Dict[str, float] = defaultdict(float)
        machine_usage: Dict[str, MachineUsage] = {}
        resource_balance: Dict[str, float] = defaultdict(float)

        for order in day_orders:
            product = plant.get_product(order.product_id)
            product_totals[product.id] += order.quantity
            for step in product.steps:
                machines = _resolve_step_machines(step, order, plant)
                for machine, share in machines:
                    quantity_factor = order.quantity * share
                    usage = machine_usage.setdefault(machine.id, MachineUsage(machine=machine))
                    capacity_add = _scale_values(step.capacity_usage, quantity_factor)
                    usage.add_capacity(capacity_add)
                    resource_add = _scale_values(step.resource_changes, quantity_factor)
                    usage.add_resource_balance(resource_add)
                    for resource_id, value in resource_add.items():
                        resource_balance[resource_id] += value

        machine_usage = {
            machine_id: MachineUsage(
                machine=usage.machine,
                capacity_used=dict(usage.capacity_used),
                resource_balance=dict(usage.resource_balance),
            )
            for machine_id, usage in machine_usage.items()
        }

        day_summary = DaySummary(
            date=current_day,
            product_quantities=dict(product_totals),
            machine_usage=machine_usage,
            resource_balance=dict(resource_balance),
        )
        days.append(day_summary)

    return SimulationResult(plant=plant, days=days)
