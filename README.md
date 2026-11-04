# SmartLighting.ML — dimerização adaptativa

Este é o projeto de Machine Learning do TCC SmartLighting. O objetivo é
prever a quantidade de novas ativações de sensores por zona nos próximos
15 minutos e usar a previsão para escolher um brilho de repouso na maquete.
O movimento continua prioritário no firmware.

**Estado atual:** geração reproduzível de dados simulados, preparação das
janelas de 15 minutos, avaliação de regras simples e treinamento de uma
regressão de Poisson em Python. Após comparar as variantes, adotamos um
**modelo geral sem identidade de zona** para a futura integração. Uma política
em Python transforma a chance prevista em três níveis de repouso e usa PWM 20
enquanto faltar histórico. Os pesos são salvos em JSON, mas ainda não há
implementação do cálculo em C++ nem controle por ML no ESP32. Os eventos
gerados não são medições reais e não entram no banco operacional da API.

## Por que simular

A maquete não consegue reproduzir semanas de circulação residencial. Os três
cenários em `scenarios/` são hipóteses declaradas, com seis sensores e seis zonas
de nomes neutros. A correspondência estrutural com a maquete, incluindo os
10 LEDs e seus vínculos com as zonas, está em
[`docs/maquette-topology.md`](docs/maquette-topology.md). Esse mapa veio dos
cadastros no banco de dados da SmartLighting.Api. As taxas de ativação e os
multiplicadores horários ainda não foram medidos nem
calibrados com uma fonte externa. O cenário `holdout` foi reservado para a
avaliação final e não foi usado para escolher características ou parâmetros do
modelo. A origem e a justificativa de cada parâmetro estão em
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
Os resultados são ignorados pelo Git porque podem ser recriados. O `holdout`
foi gerado com semente `20261104` após a escolha dos pesos e limites.

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

O mesmo comando aceita `holdout.json` e `data/generated/holdout`. A saída contém
`windows.csv` (uma linha por zona e intervalo,
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

## Treinar o modelo geral

O modelo usa hora local, fim de semana e ativações dos últimos 30 minutos.
Ele não usa a identidade da zona como entrada: uma zona nova pode receber
previsões após reunir o histórico necessário. Escolhemos essa estrutura para
permitir novas topologias sem retreinar a cada cadastro. Na validação
sintética, sua precisão ficou próxima da alternativa com pesos por zona,
com pequena perda aceita em troca dessa flexibilidade. Isso não comprova
precisão em ruas reais.

Usando os exemplos preparados, ajuste os pesos gerais com os primeiros 28
dias. O comando registra também a métrica dos sete dias de validação,
calculada com um ajuste separado dos primeiros 21 dias. **Não consulta** os
14 dias finais nem o cenário `holdout`:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.train --input-dir data/processed/development --output-dir models/development
.\.venv\Scripts\python.exe -m smartlighting_ml.train --input-dir data/processed/persistent_activity --output-dir models/persistent_activity
```

Cada diretório recebe `model.json` com os pesos gerais e `report.json` com a
origem e a validação. Os IDs das zonas de treino são registrados apenas como
proveniência: **não são entradas do modelo geral**. Esses arquivos são
recriáveis e ignorados pelo Git. O treino usa `scikit-learn`; a ordem dos pesos
fica explícita no JSON para a futura conversão ao ESP32.

### Comparação cruzada e pesos escolhidos

Com os dois cenários preparados, compare modelos treinados separadamente nos
primeiros 21 dias sobre **as mesmas janelas** dos sete dias seguintes de cada
cenário. Os pesos exportados com 28 dias não são usados nessa validação, pois
já foram ajustados com esses sete dias. O comando não acessa os 14 dias finais
nem o cenário `holdout`:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.compare_models
```

O relatório reproduzível fica em `data/evaluated/model_comparison.json`.
Escolhemos os pesos gerais treinados em `persistent_activity`, conforme a
análise em [`docs/model-selection.md`](docs/model-selection.md). Para congelar
esses pesos e criar previsões de referência para a implementação em C++:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.export_firmware
```

`config/firmware_model.json` guarda os pesos escolhidos; `config/firmware_reference.json`
guarda oito entradas e seus resultados esperados em Python. Ambos são
versionados. Ainda não executam no ESP32: serão usados para conferir se a
futura implementação em C++ produz as mesmas probabilidades e decisões PWM.

Para experimentar uma decisão com os pesos exportados, consulte as opções do
comando:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.zone_rest --help
```

O comando aceita qualquer ID de zona apenas para identificar a saída; o ID
não entra no cálculo do modelo geral. Informe o caminho de `model.json` e
quantos minutos de histórico estão disponíveis. Com menos de 30 minutos,
retorna PWM 20; com histórico completo, informe também hora local, dia da
semana (0 para segunda, 6 para domingo) e ativações dos últimos 30 minutos.
Este é um teste em Python: a contagem das janelas e essa regra de início ainda
precisam ser implementadas no firmware.

## Escolher o brilho de repouso em Python

Os níveis definidos para a maquete ficam em
[`config/dimming_policy.json`](config/dimming_policy.json): PWM baixo `10`,
padrão `20` e alto `50`, numa escala de 0 a 255. A política
usa a **chance de pelo menos uma ativação nos próximos 15 minutos**, produzida
por `PoissonModel.predict()`: abaixo de 5% escolhe baixo; de 5% até menos
de 25%, padrão; a partir de 25%, alto. Escolhemos esses limites após a análise
exploratória dos sete dias de validação sintética. Eles já foram avaliados no
`holdout` sintético, mas não em circulação real.
Para experimentar **uma probabilidade informada manualmente**, sem ler os CSVs
nem percorrer as janelas:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.dimming_policy --probability 0.18
```

Esse exemplo retorna `20/255` e não lista janelas. Para ver a decisão de cada
janela, use a avaliação abaixo. A previsão e a decisão ficam separadas:
alterar os níveis ou os limites no JSON não exige treinar novamente o ML,
mas exigirá repetir a avaliação do controle. O firmware ainda utiliza
repouso fixo `20/255`, movimento com alvo `255/255` e o fade atual. O próximo
passo é levar a política escolhida para a futura integração. Veja
[`docs/dimming-policy.md`](docs/dimming-policy.md).

## Ver as decisões por janela

Com os exemplos já preparados e o relatório de treino de cada cenário,
compare os limites de **chance prevista** de 5%, 10% e 15% usados para escolher o
repouso baixo, mantendo o limite alto de 25% do JSON. O limite configurado
após essa comparação é 5%; as três alternativas permanecem no relatório
para mostrar a decisão. Esses
percentuais são probabilidades, não valores de PWM. O programa **não gera novos
eventos** nem usa os 14 dias finais ou
o cenário `holdout`. Reajusta o modelo nos primeiros 21 dias e mostra somente
as decisões dos 7 dias seguintes:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate_dimming --input-dir data/processed/development --training-report models/development/report.json --output-dir data/evaluated/development
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate_dimming --input-dir data/processed/persistent_activity --training-report models/persistent_activity/report.json --output-dir data/evaluated/persistent_activity
```

Cada diretório recebe `window_decisions.csv` e `summary.json`. No CSV, filtre
`low_below_probability` para ver um candidato por vez. Cada linha identifica
zona, horário local, contagens anteriores, previsão, repouso escolhido e o
resultado histórico dos 15 minutos seguintes. Essa última coluna serve apenas
para avaliação; ela ainda não existiria no momento de uma previsão real. O
resumo conta quantas janelas ficaram em cada nível e quantas tiveram movimento.
Os arquivos são recriáveis e ignorados pelo Git. O resumo identifica o modelo
geral que produziu as decisões; o relatório por LED rejeita resumos antigos
sem essa identificação. Resultados e limites da comparação estão em
[`docs/dimming-validation.md`](docs/dimming-validation.md).

## Combinar pedidos das zonas por LED

[`config/maquette_topology.json`](config/maquette_topology.json) representa os
dez LEDs, seus dispositivos, slots e vínculos com as seis zonas cadastradas na
API. Usa IDs neutros (`L01`–`L10` e `Z01`–`Z06`), sem depender dos GUIDs do
banco. `rest_pwm_by_luminaire()` escolhe o **maior PWM** pedido pelas zonas de
cada LED. A função também aceita outra topologia no mesmo formato.

Para conferir um conjunto de pedidos sem gerar CSV nem treinar o modelo:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.topology --zone-pwm Z01=10 --zone-pwm Z02=10 --zone-pwm Z03=20 --zone-pwm Z04=50 --zone-pwm Z05=10 --zone-pwm Z06=20
```

Nesse exemplo, o LED `L04` recebe `50/255` porque está ligado a Z02, Z03 e
Z04, que pediram 10, 20 e 50. O comando exige um PWM para cada zona; uma zona
ausente ou desconhecida é rejeitada. O mesmo cálculo é usado no relatório por
LED; ainda não foi integrado ao firmware.

Para preparar esse relatório, `zone_windows.py` lê o CSV de decisões por zona
e reúne as seis zonas do mesmo horário e do mesmo par de limites. Ele rejeita
zonas ausentes ou repetidas, horários com lacunas e previsões que mudem entre
os candidatos. Para conferir os grupos dos dois cenários:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.zone_windows --input data/evaluated/development/window_decisions.csv
.\.venv\Scripts\python.exe -m smartlighting_ml.zone_windows --input data/evaluated/persistent_activity/window_decisions.csv
```

Cada cenário deve apresentar 672 horários de 15 minutos, três candidatos e
2.016 grupos de seis zonas. Esse comando apenas lê e verifica os dados; não
altera o ML treinado.

Para aplicar o maior pedido de cada zona aos dez LEDs da maquete e criar o
relatório dos sete dias de validação:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate_luminaires --input-dir data/evaluated/development --output-dir data/evaluated/development
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate_luminaires --input-dir data/evaluated/persistent_activity --output-dir data/evaluated/persistent_activity
```

Cada diretório recebe `luminaire_decisions.csv`, com uma linha por candidato,
horário e LED, e `luminaire_summary.json`, com as contagens gerais e por LED.
O campo `observed_any_associated_activation` indica se houve movimento em
alguma zona associada ao LED durante os 15 minutos previstos; é conhecido
somente na avaliação histórica. Os arquivos são recriáveis e ignorados pelo
Git. A metodologia e os resultados estão em
[`docs/luminaire-validation.md`](docs/luminaire-validation.md).

## Testar

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes acima verificam o gerador, o preparador, a avaliação, o modelo, a
política de brilho e os vínculos entre zonas e LEDs.

## Avaliação final no cenário reservado

Esta avaliação usa **somente** os pesos já escolhidos em
`config/firmware_model.json` e a política já definida. Não treina novamente,
não escolhe outros limites e não usa o resultado para modificar o modelo.
Para reproduzir o conjunto e os relatórios locais:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.generate --scenario scenarios/holdout.json --start-local 2026-08-01 --days 42 --seed 20261104 --output-dir data/generated/holdout
.\.venv\Scripts\python.exe -m smartlighting_ml.prepare --scenario scenarios/holdout.json --input-dir data/generated/holdout --output-dir data/processed/holdout
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate_holdout
```

`data/evaluated/holdout/` recebe `window_decisions.csv` por zona,
`luminaire_decisions.csv` por LED e `final_report.json` com as métricas,
proveniência, semente e comparação com o alvo fixo PWM 20. Esses arquivos
gerados são ignorados pelo Git; os resultados e limites da conclusão estão em
[`docs/holdout-evaluation.md`](docs/holdout-evaluation.md). O preparador começa
os exemplos após uma hora de histórico para manter as mesmas colunas dos
outros cenários. Por isso são 24.168 janelas de zona avaliadas, e não 24.192.
O firmware deverá usar PWM 20 enquanto faltar histórico suficiente.

## Próximas etapas

1. Converter o cálculo do modelo para C++ e conferir as oito referências em
   `config/firmware_reference.json`.
2. Integrar o modelo ao firmware e testar a maquete com a API desligada.

Resultados em dados simulados demonstrarão o método e o funcionamento do
sistema; não serão apresentados como precisão medida em um condomínio real.
