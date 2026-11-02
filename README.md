# SmartLighting.ML — dimerização adaptativa

Este é o projeto de Machine Learning do TCC SmartLighting. O objetivo é
prever a quantidade de novas ativações de sensores por zona nos próximos
15 minutos e usar a previsão para escolher um brilho de repouso na maquete.
O movimento continua prioritário no firmware.

**Estado atual:** geração reproduzível de dados simulados, preparação das
janelas de 15 minutos, avaliação de regras simples e treinamento de uma
regressão de Poisson em Python. Os parâmetros treinados são salvos em JSON,
mas ainda não há implementação do cálculo em C++ nem controle por ML no ESP32.
Os eventos gerados não
são medições reais e não são inseridos no banco operacional da API.

## Por que simular

A maquete não consegue reproduzir semanas de circulação residencial. Os três
cenários em `scenarios/` são hipóteses declaradas, com seis sensores e seis zonas
de nomes neutros. A correspondência estrutural com a maquete, incluindo os
10 LEDs e seus vínculos com as zonas, está em
[`docs/maquette-topology.md`](docs/maquette-topology.md). Esse mapa veio dos
cadastros no banco de dados da SmartLighting.Api. As taxas de ativação e os
multiplicadores horários ainda não foram medidos nem
calibrados com uma fonte externa. O cenário `holdout` foi reservado para uma
avaliação posterior e não deve ser usado para escolher características ou
parâmetros do modelo. A origem e a justificativa de cada parâmetro estão em
[`docs/scenario-assumptions.md`](docs/scenario-assumptions.md).

Os arquivos `sensor_events.csv` contêm somente os instantes em que houve
ativação. A preparação das janelas de 15 minutos também cria linhas com
contagem zero: a ausência de evento é uma observação necessária para aprender
e avaliar períodos de baixa circulação.

Em `development` e `holdout`, os eventos são amostrados por hora de uma
distribuição de Poisson, com taxas definidas por sensor, horário, fim de semana
e uma pequena variação diária. O cenário `persistent_activity` conserva essas
taxas básicas, mas sorteia as ativações a cada 15 minutos e adiciona períodos
temporários de maior circulação por zona.
Essa distribuição é uma **hipótese de geração**, não uma observação sobre
moradores. A hora local simulada usa deslocamento fixo UTC-03:00.

## Gerar os dados

Requer Python 3.11 ou superior. O ambiente `.venv` do projeto usa Python 3.13.
Na raiz de `SmartLighting.ML`, instale a dependência de ML no ambiente virtual,
confira o interpretador e execute:

```powershell
.\.venv\Scripts\python.exe -m pip install scikit-learn==1.9.1
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

Para gerar o cenário adicional de atividade persistente, execute separadamente:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.generate --scenario scenarios/persistent_activity.json --start-local 2026-08-01 --days 42 --seed 42 --output-dir data/generated/persistent_activity
.\.venv\Scripts\python.exe -m smartlighting_ml.prepare --scenario scenarios/persistent_activity.json --input-dir data/generated/persistent_activity --output-dir data/processed/persistent_activity
```

Esses comandos criam um conjunto separado; não substituem `development`.
O estado simulado de maior circulação não é gravado nos exemplos do modelo.

## Preparar janelas e exemplos

Depois de gerar `development`, execute:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.prepare --scenario scenarios/development.json --input-dir data/generated/development --output-dir data/processed/development
```

O mesmo comando aceita `holdout.json` e `data/generated/holdout`, quando esse
cenário for gerado. A saída contém `windows.csv` (uma linha por zona e intervalo,
inclusive zeros), `examples.csv` (hora local, dia da semana, ativações nos
15, 30 e 60 minutos anteriores e alvo dos próximos 15 minutos) e `metadata.json`.
Cada exemplo começa depois de uma hora completa de histórico. As colunas
anteriores usam somente janelas encerradas antes de `prediction_at_utc`.
Os dados preparados também são ignorados pelo Git e não entram no banco da API.

## Avaliar regras de referência

Após preparar `development` e `persistent_activity`, compare três regras usando
os primeiros 28 dias locais para calcular médias e os 14 dias seguintes para
teste. O comando só lê os CSVs existentes; não gera novos eventos ou exemplos:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate --input-dir data/processed/development --input-dir data/processed/persistent_activity --train-days 28
```

As regras são: `zero` (sempre prevê zero), `zona_hora` (média de ativações e
frequência de janelas ativas por zona e hora calculadas **somente no treino**)
e `ultima_janela` (repete a contagem dos 15 minutos anteriores). O relatório
mostra MAE e RMSE para a contagem, e Brier para a probabilidade de ocorrer ao
menos uma ativação. Mostra também recall, precisão e proporção de alertas com
limiar **ilustrativo de 20%** de probabilidade. Esse limiar ainda não define
brilho ou segurança; será revisto na etapa de controle da maquete.

Todas as métricas se referem a dados simulados. Um MAE baixo isoladamente pode
favorecer a regra `zero`, porque a maioria das janelas está vazia. Por isso,
compare também a antecipação de atividade e quantos alertas cada regra produz.
Os resultados desta execução estão em
[`docs/baseline-evaluation.md`](docs/baseline-evaluation.md).
O plano futuro de apresentação com o cálculo no ESP32 está em
[`docs/firmware-demo-plan.md`](docs/firmware-demo-plan.md).

## Treinar e comparar o ML

Depois de preparar os dois cenários, execute um treinamento independente para
cada um. Não use o cenário `holdout` nesta etapa.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.train --input-dir data/processed/development --output-dir models/development
.\.venv\Scripts\python.exe -m smartlighting_ml.train --input-dir data/processed/persistent_activity --output-dir models/persistent_activity
```

O programa usa 21 dias para ajustar modelos candidatos, 7 dias para escolher
o histórico de 15, 30, 60 ou 15+30+60 minutos pelo menor Brier, e os 14 dias
finais para comparar o escolhido com `zero` e `zona_hora`. Depois da escolha,
ajusta novamente o modelo com os primeiros 28 dias. A hora, a zona e se é fim
de semana entram em todas as alternativas. Os últimos 14 dias não escolhem
parâmetros. `report.json` guarda as métricas; `model.json` guarda os pesos
para inspeção e uma futura conversão para o firmware. Ambos ficam em
`models/`, ignorado pelo Git. O treino usa `scikit-learn`; a fórmula de previsão
permanece explícita em Python para futura conversão ao ESP32. Os resultados e
suas limitações estão em
[`docs/model-evaluation.md`](docs/model-evaluation.md).

## Testar

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes acima verificam o gerador, o preparador, a avaliação e o modelo.

## Próximas etapas

1. Conferir a topologia cadastrada na API antes da integração ao firmware.
2. Medir o custo de alertas extras e de atividade não antecipada para escolher
   o limite de brilho na maquete; os 20% atuais são apenas um corte de análise.
3. Fazer a avaliação final com o cenário `holdout` sem usá-lo para ajustes.
4. Converter o cálculo do modelo para C++ e validar igualdade com Python.
5. Integrar o modelo ao firmware e testar a maquete com a API desligada.

Resultados em dados simulados demonstrarão o método e o funcionamento do
sistema; não serão apresentados como precisão medida em um condomínio real.
