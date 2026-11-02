# Comparação provisória dos limites de repouso

Este relatório mostra **decisões simuladas por zona e janela**, não o brilho
executado no ESP32. Usamos os CSVs sintéticos existentes, com início em
2026-08-01 e semente 42. Para cada cenário, ajustamos a regressão de Poisson
com os dias locais 1–21 e histórico de 30 minutos, selecionado na avaliação
anterior. Aplicamos os três limites aos mesmos 7 dias de validação, de
2026-08-22 a 2026-08-28. Os 14 dias finais e `holdout` não foram usados nesta
comparação. Como esses 7 dias já serviram para escolher o histórico de 30
minutos, os números aqui são exploratórios, não uma prova independente.

Níveis aceitos para a maquete: PWM baixo 10, padrão 20 e alto 50, todos numa
escala de 0 a 255. O limite alto ficou fixo em **25% de chance prevista**.
Comparamos apenas onde começa o nível baixo: abaixo de **5%, 10% ou 15% de
chance prevista**. A regra fixa anterior teria PWM de
repouso 20 em todas as 4.032 janelas de cada cenário.

Exemplo com chance prevista de **8%**: se o limite baixo for 5%, a zona fica
no padrão PWM 20; se for 10% ou 15%, fica no baixo PWM 10. Com chance prevista
de **27%**, fica no alto PWM 50 nos três casos. Esses percentuais são limites
para a previsão, não 5%, 10% ou 15% de luminosidade.

| Cenário | PWM 10 se chance prevista < | Janelas em PWM 10 | Janelas em PWM 20 | Janelas em PWM 50 | Janelas ativas que ficaram em PWM 10 | Média de PWM por zona-janela |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | 5% | 662 | 3.080 | 290 | 17 de 542 (3,1%) | 20,52 |
| Desenvolvimento | 10% | 1.879 | 1.863 | 290 | 123 de 542 (22,7%) | 17,50 |
| Desenvolvimento | 15% | 2.887 | 855 | 290 | 273 de 542 (50,4%) | 15,00 |
| Atividade persistente | 5% | 660 | 2.872 | 500 | 15 de 544 (2,8%) | 22,08 |
| Atividade persistente | 10% | 1.272 | 2.260 | 500 | 52 de 544 (9,6%) | 20,57 |
| Atividade persistente | 15% | 2.589 | 943 | 500 | 219 de 544 (40,3%) | 17,30 |

“Janelas ativas que ficaram em PWM 10” responde: entre todas as janelas em
que **houve pelo menos uma ativação**, quantas teriam começado no repouso
baixo. Por exemplo, no cenário persistente com limite de 10%, foram 52 das
544 janelas ativas. Dentro das 1.272 janelas colocadas em PWM 10, 52 tiveram
movimento, cerca de 4,1%. O sensor ainda elevaria a luz quando detectasse a
passagem; o valor baixo se refere apenas ao repouso anterior.

A média de PWM é somente a média aritmética das decisões **por zona-janela**.
Não é consumo em watts ou economia: algumas luminárias pertencem a mais de
uma zona, o firmware usa fade e a resposta imediata do sensor vai a 255.
Por isso, uma média menor que 20 não prova economia elétrica. Com limite de
10%, o cenário persistente até tem média 20,57, acima do padrão fixo 20,
porque as 500 janelas em PWM 50 compensam parte do tempo em PWM 10.

O limite de 15% aumenta bastante o número de janelas em repouso baixo, mas
também coloca nele mais janelas com movimento. O de 5% evita muitas dessas
situações, porém mantém mais tempo no padrão e pode elevar a média devido às
janelas altas. **Nenhum dos três limites de probabilidade foi escolhido como
definitivo.** O limite alto de 25% também é provisório. Os níveis PWM 10/20/50
permanecem os escolhidos para a maquete.

## Arquivos para inspeção

Os comandos no README criam, em `data/evaluated/development/` e
`data/evaluated/persistent_activity/`, dois arquivos por cenário:

- `window_decisions.csv`: 12.096 linhas. São as mesmas 4.032 janelas repetidas
  para os três limites baixos. Filtre `low_below_probability` antes de contar
  janelas ou examinar uma zona. `prediction_at_local` indica o início local da
  janela prevista; `activity_probability` e `rest_pwm` mostram a decisão.
  `observed_next_15m_count` é a resposta histórica, usada somente para avaliar.
- `summary.json`: contagens e proporções por nível, além da média aritmética de
  PWM por zona-janela e comparação com o repouso fixo 20.

Esses arquivos ficam ignorados pelo Git, mas podem ser reproduzidos. O JSON
`config/dimming_policy.json` continua com o limite baixo provisório de 10% e
não foi alterado por esta avaliação.

Para a próxima análise por LED, `zone_windows.py` reúne as seis decisões do
mesmo horário e limite em um grupo completo. A leitura confere que há os mesmos
horários em todos os candidatos e que mudar o limite não alterou a previsão
nem a resposta histórica. O cálculo do PWM final por LED usará esses grupos
na etapa seguinte.
