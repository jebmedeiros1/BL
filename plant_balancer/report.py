from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .models import MachineUsage, SimulationResult


def _format_quantity(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def _format_resource(result: SimulationResult, resource_id: str, value: float, decimals: int = 2) -> str:
    resource = result.plant.resources.get(resource_id)
    name = resource.name if resource else resource_id
    unit = resource.unit if resource else ""
    quantity = _format_quantity(value, decimals)
    if unit:
        return f"{name}: {quantity} {unit}"
    return f"{name}: {quantity}"


def _max_utilization(result: SimulationResult) -> List[Tuple[str, str, float, float, float, str]]:
    stats: Dict[Tuple[str, str], Tuple[float, float, float, str]] = {}
    for day in result.days:
        for usage in day.machine_usage.values():
            for key, used in usage.capacity_used.items():
                capacity = usage.machine.capacity.get(key)
                if capacity in (None, 0):
                    continue
                ratio = used / capacity
                current = stats.get((usage.machine.id, key))
                if current is None or ratio > current[0]:
                    stats[(usage.machine.id, key)] = (ratio, used, capacity, day.date.isoformat(), usage.machine.name)
    entries = [
        (machine_id, cap_key, ratio, used, capacity, day, name)
        for (machine_id, cap_key), (ratio, used, capacity, day, name) in stats.items()
    ]
    entries.sort(key=lambda item: item[2], reverse=True)
    return entries


def _format_machine_usage(result: SimulationResult, usage: MachineUsage, decimals: int) -> List[str]:
    lines: List[str] = []
    header = f"- {usage.machine.name} ({usage.machine.id})"
    lines.append(header)
    if usage.capacity_used:
        for key, value in sorted(usage.capacity_used.items()):
            capacity = usage.machine.capacity.get(key)
            if capacity in (None, 0):
                lines.append(f"    {key}: {_format_quantity(value, decimals)} (sem limite definido)")
            else:
                percent = (value / capacity) * 100
                lines.append(
                    f"    {key}: {_format_quantity(value, decimals)} / {_format_quantity(capacity, decimals)} ({percent:.1f}%)"
                )
    if usage.resource_balance:
        lines.append("    Recursos associados:")
        for resource_id, value in sorted(usage.resource_balance.items()):
            lines.append(f"      {_format_resource(result, resource_id, value, decimals)}")
    return lines


def format_simulation_report(result: SimulationResult, decimals: int = 2) -> str:
    """Create a human-readable textual report for the simulation."""

    lines: List[str] = []
    if not result.days:
        return "Nenhuma ordem de produção disponível."

    for day in result.days:
        lines.append(f"Dia {day.date.isoformat()}")
        if day.product_quantities:
            lines.append("  Produção planejada:")
            for product_id, quantity in sorted(day.product_quantities.items()):
                product = result.plant.products.get(product_id)
                description = product.name if product else product_id
                unit = product.unit if product else ""
                formatted_quantity = _format_quantity(quantity, decimals)
                if unit:
                    lines.append(f"    - {description}: {formatted_quantity} {unit}")
                else:
                    lines.append(f"    - {description}: {formatted_quantity}")
        if day.machine_usage:
            lines.append("  Utilização dos equipamentos:")
            ordered = sorted(day.machine_usage.values(), key=lambda item: item.machine.name)
            for usage in ordered:
                lines.extend(["  " + entry for entry in _format_machine_usage(result, usage, decimals)])
        if day.resource_balance:
            lines.append("  Balanço de recursos do dia:")
            for resource_id, value in sorted(day.resource_balance.items()):
                lines.append(f"    - {_format_resource(result, resource_id, value, decimals)}")
        alerts = day.capacity_alerts()
        if alerts:
            lines.append("  Alertas de capacidade:")
            for alert in alerts:
                used = _format_quantity(alert["used"], decimals)
                limit = _format_quantity(alert["limit"], decimals)
                lines.append(
                    f"    - {alert['machine_name']} ({alert['machine_id']}) excede {alert['capacity_key']}: {used} / {limit}"
                )
        lines.append("")

    lines.append("Resumo consolidado do horizonte:")
    totals = result.overall_product_quantities()
    if totals:
        lines.append("  Produção acumulada:")
        for product_id, quantity in sorted(totals.items()):
            product = result.plant.products.get(product_id)
            description = product.name if product else product_id
            unit = product.unit if product else ""
            formatted_quantity = _format_quantity(quantity, decimals)
            if unit:
                lines.append(f"    - {description}: {formatted_quantity} {unit}")
            else:
                lines.append(f"    - {description}: {formatted_quantity}")
    resource_totals = result.overall_resource_balance()
    if resource_totals:
        lines.append("  Balanço acumulado de recursos:")
        for resource_id, value in sorted(resource_totals.items()):
            lines.append(f"    - {_format_resource(result, resource_id, value, decimals)}")
    utilization = _max_utilization(result)
    if utilization:
        lines.append("  Picos de utilização dos equipamentos:")
        for machine_id, capacity_key, ratio, used, capacity, day, name in utilization:
            lines.append(
                "    - "
                + f"{name} ({machine_id}) - {capacity_key}: {ratio*100:.1f}% ("
                + f"{_format_quantity(used, decimals)} de {_format_quantity(capacity, decimals)} no dia {day})"
            )
    return "\n".join(lines).strip()
