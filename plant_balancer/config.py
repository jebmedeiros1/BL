from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

from .models import Machine, MachineGroup, Plant, Product, RecipeStep, Resource


def _load_resources(config: Dict) -> Dict[str, Resource]:
    resources = {}
    for item in config.get("resources", []):
        resource = Resource(id=item["id"], name=item.get("name", item["id"]), unit=item.get("unit", ""))
        resources[resource.id] = resource
    return resources


def _load_machine_groups(config: Dict) -> Dict[str, MachineGroup]:
    groups = {}
    for item in config.get("machine_groups", []):
        group = MachineGroup(id=item["id"], name=item.get("name", item["id"]))
        groups[group.id] = group
    return groups


def _load_machines(config: Dict, groups: Iterable[str]) -> Dict[str, Machine]:
    machines: Dict[str, Machine] = {}
    for item in config.get("machines", []):
        group_id = item.get("group_id")
        if group_id not in groups:
            raise ValueError(f"Machine '{item.get('id')}' references unknown group '{group_id}'")
        capacity = {key: float(value) for key, value in item.get("capacity", {}).items()}
        machine = Machine(id=item["id"], name=item.get("name", item["id"]), group_id=group_id, capacity=capacity)
        machines[machine.id] = machine
    return machines


def _load_recipe_steps(step_items: Iterable[Dict]) -> Iterable[RecipeStep]:
    steps = []
    for step in step_items:
        target = step.get("target")
        if target not in {"group", "machine", "order_machine"}:
            raise ValueError(f"Unsupported target '{target}' in recipe step '{step.get('name')}'")
        allocation = step.get("allocation")
        if allocation is not None:
            allocation = {key: float(value) for key, value in allocation.items()}
        capacity_usage = {key: float(value) for key, value in step.get("capacity_usage", {}).items()}
        resource_changes = {key: float(value) for key, value in step.get("resource_changes", {}).items()}
        recipe_step = RecipeStep(
            name=step.get("name", ""),
            target=target,
            machine_id=step.get("machine_id"),
            group_id=step.get("group_id"),
            required_group=step.get("required_group"),
            allocation=allocation,
            capacity_usage=capacity_usage,
            resource_changes=resource_changes,
        )
        steps.append(recipe_step)
    return steps


def _load_products(config: Dict) -> Dict[str, Product]:
    products: Dict[str, Product] = {}
    for item in config.get("products", []):
        steps = list(_load_recipe_steps(item.get("steps", [])))
        product = Product(id=item["id"], name=item.get("name", item["id"]), unit=item.get("unit", ""), steps=steps)
        products[product.id] = product
    return products


def load_plant(path: Path | str) -> Plant:
    """Load the full plant configuration from a JSON file."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as fp:
        config = json.load(fp)
    resources = _load_resources(config)
    groups = _load_machine_groups(config)
    machines = _load_machines(config, groups)
    products = _load_products(config)
    return Plant(resources=resources, machine_groups=groups, machines=machines, products=products)
