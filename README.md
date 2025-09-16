# Simulador de balanço de fábrica

Este projeto contém um modelo simples em Python que permite simular o balanço diário de uma fábrica de celulose e papel. A partir de uma configuração de equipamentos, recursos e receitas, e de um plano de produção para os próximos dias, o simulador calcula como cada máquina é utilizada e qual é o balanço dos principais insumos e utilidades.

## Requisitos


## Estrutura dos dados

### Arquivo de configuração (`plant_config.json`)

O arquivo em `data/plant_config.json` descreve:

- **Recursos**: materiais e utilidades rastreados pelo balanço, incluindo unidade de medida.
- **Grupos de máquinas**: agrupamentos lógicos de equipamentos semelhantes (digestores, caldeiras, turbo geradores, etc.).
- **Máquinas**: equipamentos com respectivos grupos e capacidades diárias por tipo de recurso/capacidade.
- **Produtos**: receitas com uma ou mais etapas. Cada etapa indica o equipamento utilizado, o consumo ou geração de recursos e a utilização da capacidade da máquina. Valores positivos representam consumo; valores negativos representam geração.

### Plano de produção (`production_plan_7d.json`)

O arquivo em `data/production_plan_7d.json` é um exemplo de planejamento para sete dias consecutivos. Cada entrada indica a data, o produto, a máquina final associada à ordem e a quantidade planejada.

Para outras janelas (por exemplo 15 dias), basta criar um arquivo com as novas datas e quantidades.

## Execução

Para gerar um relatório do comportamento da fábrica:

```bash
python -m plant_balancer.cli --config data/plant_config.json --plan data/production_plan_7d.json
```

Opções adicionais:

- `--start-date` e `--end-date`: filtram o plano para um intervalo específico.
- `--output`: grava o relatório em um arquivo de texto.
- `--decimals`: define o número de casas decimais mostradas nas tabelas.

O relatório apresenta, para cada dia, as quantidades produzidas, o uso de cada máquina (comparado à capacidade declarada) e o balanço dos recursos. Na parte final, há um resumo consolidado com totais acumulados e os maiores picos de utilização.


## Estruturação de novas receitas

Para adicionar um novo produto ou ajustar consumos:

1. Inclua/edite o produto em `plant_config.json` definindo as etapas e respectivos consumos/geraçőes.
2. Atualize o plano de produção com ordens para o novo produto.
3. Execute novamente o simulador para ver o impacto no balanço.

## Testes

Os testes automatizados podem ser executados com:

```bash
pytest
```
