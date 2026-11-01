# SmartLighting.ML — dimerização adaptativa

Este é o novo projeto de Machine Learning do TCC SmartLighting. O objetivo é
prever a quantidade de novas ativações de sensores por zona nos próximos
15 minutos e usar a previsão para escolher um brilho de repouso na maquete.
O movimento continua prioritário no firmware.

**Estado atual:** geração reproduzível de dados simulados e preparação das
janelas de 15 minutos. Ainda não há treinamento, métricas de previsão, modelo
exportado nem controle por ML no ESP32. Os eventos gerados não são medições
reais e não são inseridos no banco operacional da API.

## Por que simular

A maquete não consegue reproduzir semanas de circulação residencial. Os dois
cenários em `scenarios/` são hipóteses declaradas, com seis sensores e seis zonas
de nomes neutros. A correspondência estrutural com a maquete, incluindo os
10 LEDs e seus vínculos com as zonas, está em
[`docs/maquette-topology.md`](docs/maquette-topology.md). Esse mapa veio dos
cadastros no banco de dados da SmartLighting.Api. As taxas de ativação e os
multiplicadores horários ainda não foram medidos nem
calibrados com uma fonte externa. O cenário `holdout` foi reservado para uma
avaliação posterior e não deve ser usado para escolher características ou
parâmetros do modelo.

Os arquivos `sensor_events.csv` contêm somente os instantes em que houve
ativação. A preparação das janelas de 15 minutos também cria linhas com
contagem zero: a ausência de evento é uma observação necessária para aprender
e avaliar períodos de baixa circulação.

Os eventos são amostrados por hora de uma distribuição de Poisson, com taxas
definidas por sensor, horário, fim de semana e uma pequena variação diária.
Essa distribuição é uma **hipótese de geração**, não uma observação sobre
moradores. A hora local simulada usa deslocamento fixo UTC-03:00.

## Gerar os dados

Requer Python 3.11 ou superior. O ambiente `.venv` do projeto usa Python 3.13.
Na raiz de `SmartLighting.ML`, confira o interpretador e execute:

```powershell
.\.venv\Scripts\python.exe --version
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.generate --scenario scenarios/development.json --start-local 2026-08-01 --days 42 --seed 42 --output-dir data/generated/development
```

Cada diretório recebe `sensor_events.csv` e `metadata.json`. Os metadados
registram a semente e a identificação dos parâmetros do cenário. Depois de
alterar qualquer JSON, gere novamente seus eventos antes de preparar as
janelas; o preparador rejeita dados gerados com outra versão do cenário.
Os resultados são ignorados pelo Git porque podem ser recriados. Deixe o
cenário `holdout` reservado até a etapa de avaliação final.

## Preparar janelas e exemplos

Depois de gerar `development`, execute:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.prepare --scenario scenarios/development.json --input-dir data/generated/development --output-dir data/processed/development
```

O mesmo comando aceita `holdout.json` e `data/generated/holdout`, quando esse
cenário for gerado. A saída contém `windows.csv` (uma linha por zona e intervalo,
inclusive zeros), `examples.csv` (hora local, dia da semana, ativações nos
15 e 60 minutos anteriores e alvo dos próximos 15 minutos) e `metadata.json`.
Cada exemplo começa depois de uma hora completa de histórico. As colunas
anteriores usam somente janelas encerradas antes de `prediction_at_utc`.
Os dados preparados também são ignorados pelo Git e não entram no banco da API.

## Testar

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes acima verificam o comportamento do gerador e do preparador.

## Próximas etapas

1. Conferir a topologia cadastrada na API antes da integração ao firmware.
2. Revisar taxas e distribuição de zeros nos cenários simulados.
3. Treinar e comparar uma referência simples com um modelo de regressão.
4. Avaliar em períodos e cenários separados do treinamento.
5. Exportar parâmetros para C++ e validar igualdade de previsões com Python.
6. Integrar o modelo ao firmware e testar a maquete com a API desligada.

Resultados em dados simulados demonstrarão o método e o funcionamento do
sistema; não serão apresentados como precisão medida em um condomínio real.
