from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Plant, ProductionOrder


@dataclass
class ProductionPlan:
    """Collection of production orders."""

    orders: List[ProductionOrder]

    def orders_by_day(self) -> Dict[date, List[ProductionOrder]]:
        grouped: Dict[date, List[ProductionOrder]] = {}
        for order in self.orders:
            grouped.setdefault(order.date, []).append(order)
        return grouped

    def filter_by_date_range(self, start: Optional[date], end: Optional[date]) -> "ProductionPlan":
        filtered = []
        for order in self.orders:
            if start and order.date < start:
                continue
            if end and order.date > end:
                continue
            filtered.append(order)
        return ProductionPlan(filtered)

    def validate(self, plant: Plant) -> None:
        errors: List[str] = []
        for order in self.orders:
            if order.product_id not in plant.products:
                errors.append(f"Produto desconhecido: {order.product_id}")
            if order.machine_id not in plant.machines:
                errors.append(f"Equipamento desconhecido: {order.machine_id}")
        if errors:
            raise ValueError("\n".join(errors))


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Data inválida no plano de produção: '{value}'") from exc


def _parse_orders(items: Iterable[Dict]) -> List[ProductionOrder]:
    orders: List[ProductionOrder] = []
    for item in items:
        order_date = _parse_date(item["date"])
        quantity = float(item.get("quantity", 0.0))
        if quantity < 0:
            raise ValueError(f"Quantidade negativa informada para {item}")
        orders.append(
            ProductionOrder(
                date=order_date,
                product_id=item["product_id"],
                machine_id=item["machine_id"],
                quantity=quantity,
            )
        )
    return orders


def load_plan(path: Path | str) -> ProductionPlan:
    """Load production orders from a JSON file."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    orders = _parse_orders(data.get("orders", []))
    orders.sort(key=lambda order: (order.date, order.product_id, order.machine_id))
    return ProductionPlan(orders)
