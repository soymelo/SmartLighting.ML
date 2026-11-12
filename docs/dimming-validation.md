# Comparação dos limites de repouso

> **Registro histórico.** A tabela e a análise seguintes usam a curva
> horária antiga e a política PWM 10/20/50 com corte alto de 25%. A reexecução
> com os cenários revisados e PWM 10/20/40 está na seção final.

Este relatório mostra **decisões simuladas por zona e janela**, não o brilho
executado no ESP32. Usamos os CSVs sintéticos existentes, com início em
2026-08-01 e semente 42. Para cada cenário, ajustamos a regressão de Poisson
geral com os dias locais 1–21 e histórico de 30 minutos. Aplicamos os três
limites aos mesmos 7 dias de validação, de
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
| Desenvolvimento | 5% | 592 | 3.100 | 340 | 15 de 542 (2,8%) | 21,06 |
| Desenvolvimento | 10% | 1.780 | 1.912 | 340 | 118 de 542 (21,8%) | 18,12 |
| Desenvolvimento | 15% | 2.785 | 907 | 340 | 255 de 542 (47,0%) | 15,62 |
| Atividade persistente | 5% | 690 | 2.812 | 530 | 18 de 544 (3,3%) | 22,23 |
| Atividade persistente | 10% | 1.143 | 2.359 | 530 | 37 de 544 (6,8%) | 21,11 |
| Atividade persistente | 15% | 2.602 | 900 | 530 | 224 de 544 (41,2%) | 17,49 |

“Janelas ativas que ficaram em PWM 10” responde: entre todas as janelas em
que **houve pelo menos uma ativação**, quantas teriam começado no repouso
baixo. Por exemplo, no cenário persistente com limite escolhido de 5%, foram
18 das 544 janelas ativas. Dentro das 690 janelas colocadas em PWM 10, 18
tiveram movimento, cerca de 2,6%. O sensor ainda elevaria a luz quando detectasse a
passagem; o valor baixo se refere apenas ao repouso anterior.

A média de PWM é somente a média aritmética das decisões **por zona-janela**.
Não é consumo em watts ou economia: algumas luminárias pertencem a mais de
uma zona, o firmware usa fade e a resposta imediata do sensor vai a 255.
Por isso, uma média menor que 20 não prova economia elétrica. Com limite de
5%, o cenário persistente tem média 22,23, acima do padrão fixo 20,
porque as 530 janelas em PWM 50 compensam parte do tempo em PWM 10.

O limite de 15% aumenta bastante o número de janelas em repouso baixo, mas
também coloca nele mais janelas com movimento. O de 5% evita muitas dessas
situações, porém mantém mais tempo no padrão e pode elevar a média devido às
janelas altas. Após analisar também os resultados por LED, escolhemos **5%**
para o limite baixo e mantivemos **25%** para o limite alto. Essa é a política
configurada para a maquete, ainda sem avaliação final reservada ou medições de
circulação real. Os níveis PWM 10/20/50 permanecem os escolhidos.

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
`config/dimming_policy.json` foi atualizado para o limite baixo escolhido de
5%. O CSV desta comparação preserva as três alternativas, inclusive 10% e 15%.

Para a [análise por LED](luminaire-validation.md), `zone_windows.py` reúne as
seis decisões do mesmo horário e limite em um grupo completo. A leitura
confere que há os mesmos horários em todos os candidatos e que mudar o limite
não alterou a previsão nem a resposta histórica. O relatório por LED aplica
o maior PWM solicitado pelas zonas associadas a cada luminária.

## Reexecução com a curva e a política atuais

Regeramos os dois cenários com 42 dias e semente 42. Em cada um, o modelo
geral foi treinado nos primeiros 21 dias e avaliado nos sete dias seguintes.
Cada linha contém 4.032 janelas de zona. O corte alto é 30%, o PWM alto é 40
e apenas o corte baixo varia. Os 14 dias finais e `holdout` não entraram.

| Cenário | Baixo abaixo de | PWM 10 | PWM 20 | PWM 40 | Janelas ativas em PWM 10 | PWM médio por zona-janela |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | 5% | 719 | 3.313 | 0 | 16 de 497 | 18,22 |
| Desenvolvimento | 10% | 1.487 | 2.545 | 0 | 70 de 497 | 16,31 |
| Desenvolvimento | 15% | 3.024 | 1.008 | 0 | 278 de 497 | 12,50 |
| Atividade persistente | 5% | 365 | 3.440 | 227 | 5 de 561 | 20,22 |
| Atividade persistente | 10% | 1.341 | 2.464 | 227 | 64 de 561 | 17,80 |
| Atividade persistente | 15% | 2.469 | 1.336 | 227 | 212 de 561 | 15,00 |

O limite atualmente configurado é **5%**. Assim, no cenário persistente, 5
das 561 janelas com atividade começariam em repouso baixo; o sensor ainda
reagiria à detecção. A média desta tabela é por zona, não por LED e não mede
energia. As decisões reproduzíveis estão em `data/evaluated/<cenário>/`.
