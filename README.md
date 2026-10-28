# SmartLighting.ML — dimerização adaptativa

Este é o novo projeto de Machine Learning do TCC SmartLighting. O objetivo é
prever a quantidade de ativações de sensores no próximo intervalo e usar a
previsão para escolher um brilho de repouso na maquete. O movimento continua
prioritário no firmware.

**Estado atual:** somente a primeira etapa está implementada: geração
reproduzível de dados simulados. Ainda não há treinamento, modelo exportado nem
controle por ML no ESP32. Os eventos gerados não são medições reais e não são
inseridos no banco operacional da API.

## Por que simular

A maquete não consegue reproduzir semanas de circulação residencial. Os dois
cenários em `scenarios/` são hipóteses declaradas, com seis sensores de nomes
neutros. A localização e a associação reais de sensores e LEDs serão
confirmadas pela topologia cadastrada na API antes do treinamento. O cenário
`holdout` foi reservado para uma avaliação posterior e não deve ser usado para
escolher características ou parâmetros do modelo.

Os eventos são amostrados por hora de uma distribuição de Poisson, com taxas
definidas por sensor, horário, fim de semana e uma pequena variação diária.
Essa distribuição é uma **hipótese de geração**, não uma observação sobre
moradores. A hora local simulada usa deslocamento fixo UTC-03:00.

## Gerar os dados

Requer Python 3.11 ou superior. Na raiz do projeto, execute:

```powershell
$env:PYTHONPATH = "src"
python -m smartlighting_ml.generate --scenario scenarios/development.json --start-local 2026-08-01 --days 42 --seed 42 --output-dir data/generated/development
python -m smartlighting_ml.generate --scenario scenarios/holdout.json --start-local 2026-09-12 --days 14 --seed 43 --output-dir data/generated/holdout
```

Cada diretório recebe `sensor_events.csv` e `metadata.json`. Os resultados são
ignorados pelo Git porque podem ser gerados novamente a partir dos cenários e
das sementes versionados.

## Testar

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Próximas etapas

1. Confirmar a topologia física de sensores e LEDs.
2. Preparar janelas de tempo usando apenas informações disponíveis antes da previsão.
3. Treinar e comparar uma referência simples com um modelo de regressão.
4. Avaliar em períodos e cenários separados do treinamento.
5. Exportar parâmetros para C++ e validar igualdade de previsões com Python.
6. Integrar o modelo ao firmware e testar a maquete com a API desligada.

Resultados em dados simulados demonstrarão o método e o funcionamento do
sistema; não serão apresentados como precisão medida em um condomínio real.
