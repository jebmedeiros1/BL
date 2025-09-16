from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project package is importable when running tests from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plant_balancer.config import load_plant
from plant_balancer.plan import load_plan
from plant_balancer.simulator import simulate


@pytest.fixture(scope="module")
def simulation_result():
    plant = load_plant("data/plant_config.json")
    plan = load_plan("data/production_plan_7d.json")
    return simulate(plant, plan.orders)


def test_simulation_has_seven_days(simulation_result):
    assert len(simulation_result.days) == 7
    assert simulation_result.days[0].date.isoformat() == "2023-09-18"


def test_first_day_balances(simulation_result):
    day = simulation_result.days[0]
    assert day.product_quantities["celulose_mercado"] == pytest.approx(400.0)
    assert day.product_quantities["papel_revestido"] == pytest.approx(320.0)
    assert day.product_quantities["papel_nao_revestido"] == pytest.approx(280.0)
    assert day.product_quantities["vapor_recuperacao"] == pytest.approx(2000.0)
    assert day.product_quantities["vapor_forca"] == pytest.approx(1600.0)
    assert day.product_quantities["turbogeracao"] == pytest.approx(1500.0)

    assert day.resource_balance["vapor_alta"] == pytest.approx(-28.0)
    assert day.resource_balance["vapor_baixa"] == pytest.approx(541.0)
    assert day.resource_balance["licor_negro"] == pytest.approx(28.0)
    assert day.resource_balance["celulose_secada"] == pytest.approx(-400.0)
    assert day.resource_balance["papel"] == pytest.approx(-600.0)
    assert not day.capacity_alerts()


def test_machine_usage_distribution(simulation_result):
    day = simulation_result.days[0]
    digestor_usage = day.machine_usage["dig1"]
    assert digestor_usage.capacity_used["chip_throughput"] == pytest.approx(250.0)

    bleaching_usage = day.machine_usage["btcmp"]
    assert bleaching_usage.capacity_used["bleaching"] == pytest.approx(1000.0)

    paper_machine_usage = day.machine_usage["mp1"]
    assert paper_machine_usage.capacity_used["paper_output"] == pytest.approx(320.0)


def test_overall_balances(simulation_result):
    totals = simulation_result.overall_resource_balance()
    assert totals["celulose_secada"] == pytest.approx(-2800.0)
    assert totals["papel"] == pytest.approx(-4200.0)
    assert totals["vapor_alta"] == pytest.approx(-196.0)

    product_totals = simulation_result.overall_product_quantities()
    assert product_totals["celulose_mercado"] == pytest.approx(2800.0)
    assert product_totals["papel_revestido"] == pytest.approx(2240.0)
    assert product_totals["papel_nao_revestido"] == pytest.approx(1960.0)
