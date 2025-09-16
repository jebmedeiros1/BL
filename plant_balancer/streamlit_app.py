from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import streamlit as st

from .analytics import (
    MACHINE_CAPACITY_CATEGORY,
    PRODUCT_CATEGORY,
    RESOURCE_CATEGORY,
    HourlySeries,
    build_hourly_series,
)
from .config import load_plant
from .models import Plant
from .plan import ProductionPlan, load_plan
from .simulator import SimulationError, simulate

CATEGORY_LABELS: Dict[str, str] = {
    RESOURCE_CATEGORY: "Recursos (balanço)",
    PRODUCT_CATEGORY: "Produção de produtos",
    MACHINE_CAPACITY_CATEGORY: "Capacidade das máquinas",
}

CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    RESOURCE_CATEGORY: "Média horária do balanço de cada recurso (consumo positivo, geração negativa).",
    PRODUCT_CATEGORY: "Produção média por hora para cada produto planejado.",
    MACHINE_CAPACITY_CATEGORY: "Uso médio por hora das capacidades declaradas em cada equipamento.",
}


@dataclass
class LoadedData:
    plant_path: Path
    plan_path: Path
    plant: Plant
    plan: ProductionPlan


def _parse_optional_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    return date.fromisoformat(value)


def _load_inputs(config_path: str, plan_path: str, start: str, end: str) -> LoadedData:
    config = Path(config_path).expanduser()
    if not config.exists():
        st.error(f"Arquivo de configuração não encontrado: {config}")
        st.stop()

    plan_file = Path(plan_path).expanduser()
    if not plan_file.exists():
        st.error(f"Arquivo de plano de produção não encontrado: {plan_file}")
        st.stop()

    try:
        plant = load_plant(config)
    except Exception as exc:
        st.error(f"Erro ao carregar configuração da fábrica: {exc}")
        st.stop()

    try:
        plan = load_plan(plan_file)
    except Exception as exc:
        st.error(f"Erro ao carregar o plano de produção: {exc}")
        st.stop()

    start_date: date | None
    end_date: date | None
    try:
        start_date = _parse_optional_date(start)
    except ValueError:
        st.error(f"Data inicial inválida: {start}")
        st.stop()
    try:
        end_date = _parse_optional_date(end)
    except ValueError:
        st.error(f"Data final inválida: {end}")
        st.stop()

    if start_date and end_date and end_date < start_date:
        st.error("A data final deve ser maior ou igual à data inicial.")
        st.stop()

    if start_date or end_date:
        plan = plan.filter_by_date_range(start_date, end_date)

    if not plan.orders:
        st.warning("Nenhuma ordem encontrada para o período selecionado.")
        st.stop()

    try:
        plan.validate(plant)
    except ValueError as exc:
        st.error(f"Plano inválido: {exc}")
        st.stop()

    return LoadedData(plant_path=config, plan_path=plan_file, plant=plant, plan=plan)


def _series_to_dataframe(series_list: Iterable[HourlySeries]) -> pd.DataFrame:
    data: Dict = {}
    for series in series_list:
        for point in series.points:
            data.setdefault(point.timestamp, {})[series.label] = point.value
    if not data:
        return pd.DataFrame()
    frame = pd.DataFrame.from_dict(data, orient="index").sort_index()
    frame.index.name = "timestamp"
    return frame.fillna(0.0)


def _format_selection_label(series: HourlySeries) -> str:
    if series.unit:
        return f"{series.label} ({series.unit})"
    return series.label


def _build_tabs(series: List[HourlySeries]) -> Dict[str, List[HourlySeries]]:
    grouped: Dict[str, List[HourlySeries]] = {}
    for item in series:
        grouped.setdefault(item.category, []).append(item)
    return grouped


def main() -> None:
    st.set_page_config(page_title="Balanço de Fábrica", layout="wide")
    st.title("Balanço de Fábrica - Visualização Horária")

    st.sidebar.header("Parâmetros da simulação")
    config_path = st.sidebar.text_input("Arquivo de configuração", value="data/plant_config.json")
    plan_path = st.sidebar.text_input("Plano de produção", value="data/production_plan_7d.json")
    start_date = st.sidebar.text_input("Data inicial (AAAA-MM-DD)", value="")
    end_date = st.sidebar.text_input("Data final (AAAA-MM-DD)", value="")

    with st.sidebar.expander("Sobre os dados"):
        st.markdown(
            "Use os arquivos de exemplo do repositório ou informe os caminhos para seus próprios JSONs. "
            "Os valores diários são distribuídos uniformemente entre as 24 horas do dia para construir as séries horárias."
        )

    inputs = _load_inputs(config_path, plan_path, start_date, end_date)

    plant = inputs.plant
    try:
        result = simulate(plant, inputs.plan.orders)
    except SimulationError as exc:
        st.error(f"Não foi possível executar a simulação: {exc}")
        st.stop()

    series = build_hourly_series(result)
    if not series:
        st.warning("Nenhuma série disponível para exibição.")
        st.stop()

    plan_orders = inputs.plan.orders
    period_start = min(order.date for order in plan_orders)
    period_end = max(order.date for order in plan_orders)
    st.markdown(
        f"**Período simulado:** {period_start.isoformat()} até {period_end.isoformat()} "
        f"({len(result.days)} dia{'s' if len(result.days) != 1 else ''})"
    )
    st.markdown(f"**Total de ordens analisadas:** {len(plan_orders)}")

    grouped = _build_tabs(series)
    categories = [category for category in CATEGORY_LABELS if category in grouped]
    if not categories:
        st.warning("Não há dados para as categorias definidas.")
        st.stop()

    tabs = st.tabs([CATEGORY_LABELS[category] for category in categories])

    for tab, category in zip(tabs, categories, strict=False):
        with tab:
            subset = sorted(grouped[category], key=lambda item: item.label)
            description = CATEGORY_DESCRIPTIONS.get(category)
            if description:
                st.caption(description)

            options = [item.id for item in subset]
            labels = {item.id: _format_selection_label(item) for item in subset}
            default_selection = options[: min(3, len(options))]
            selected_ids = st.multiselect(
                "Itens exibidos", options=options, default=default_selection, format_func=lambda value: labels[value], key=f"sel_{category}"
            )
            if not selected_ids:
                st.info("Selecione pelo menos um item para visualizar o gráfico.")
                continue

            chosen = [item for item in subset if item.id in selected_ids]
            data_frame = _series_to_dataframe(chosen)
            if data_frame.empty:
                st.info("Não há dados para os itens selecionados.")
                continue

            st.line_chart(data_frame)
            st.dataframe(data_frame, use_container_width=True)

            totals = pd.DataFrame(
                {
                    "Total no período": [series_item.total() for series_item in chosen],
                },
                index=[labels[series_item.id] for series_item in chosen],
            )
            st.subheader("Totais acumulados no período")
            st.table(totals)
            st.caption(
                "As curvas representam valores médios por hora assumindo uma distribuição uniforme das quantidades diárias."
            )


if __name__ == "__main__":  # pragma: no cover
    main()

