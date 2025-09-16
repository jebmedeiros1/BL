from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Optional

from .config import load_plant
from .plan import ProductionPlan, load_plan
from .report import format_simulation_report
from .simulator import SimulationError, simulate


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Data inválida: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulador de balanço de fábrica")
    parser.add_argument("--config", required=True, help="Arquivo JSON com a configuração da fábrica")
    parser.add_argument("--plan", required=True, help="Arquivo JSON com o plano de produção")
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        help="Data inicial (formato ISO AAAA-MM-DD) para filtrar o plano",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        help="Data final (formato ISO AAAA-MM-DD) para filtrar o plano",
    )
    parser.add_argument("--output", help="Arquivo de saída para salvar o relatório gerado")
    parser.add_argument("--decimals", type=int, default=2, help="Número de casas decimais exibidas nos valores")
    return parser


def _filter_plan(plan: ProductionPlan, start: Optional[date], end: Optional[date]) -> ProductionPlan:
    if start or end:
        return plan.filter_by_date_range(start, end)
    return plan


def main(args: Optional[list[str]] = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args=args)

    plant = load_plant(parsed.config)
    plan = load_plan(parsed.plan)
    plan = _filter_plan(plan, parsed.start_date, parsed.end_date)

    try:
        plan.validate(plant)
        result = simulate(plant, plan.orders)
    except (ValueError, SimulationError) as exc:
        parser.error(str(exc))

    report_text = format_simulation_report(result, decimals=parsed.decimals)

    if parsed.output:
        output_path = Path(parsed.output)
        output_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
