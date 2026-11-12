# Avaliação final do modelo escolhido

> **Registro histórico.** Esta avaliação usou os pesos treinados com a curva
> horária anterior e a política PWM 10/20/50, limites 5%/25%. A curva e a
> política foram revisadas posteriormente. Os novos pesos ainda não foram
> exportados e este resultado não valida a configuração nova. Reutilizar o
> mesmo `holdout` para escolher parâmetros e depois apresentá-lo como teste
> independente comprometeria essa separação.

Antes deste teste, escolhemos os pesos gerais treinados com 28 dias do cenário
`persistent_activity` e fixamos a política: chance menor que 5% → PWM 10,
de 5% a menos de 25% → PWM 20, e a partir de 25% → PWM 50. Esta avaliação
carregou `config/firmware_model.json`; **não treinou novamente** nem alterou
pesos, limites ou topologia após observar o `holdout`.

O `holdout` é outro cenário **simulado**, com curva horária e taxas diferentes.
Foi gerado de 1º de agosto de 2026 por 42 dias, com semente `20261104`, e
produziu 3.923 ativações. A preparação gerou 24.192 janelas de zona. Como os
exemplos começam após uma hora de histórico em cada uma das seis zonas, a
avaliação contém **24.168 janelas de zona** e **4.028 horários**. Aplicar a
topologia de dez LEDs gera **40.280 janelas de LED**.

## Previsão por zona

| Medida | Modelo escolhido | Regra que prevê sempre zero |
| --- | ---: | ---: |
| Brier da chance de atividade ↓ | **0,11867** | 0,14523 |
| MAE da quantidade de ativações ↓ | 0,25880 | **0,16228** |
| RMSE da quantidade de ativações ↓ | **0,40680** | 0,44668 |

**Brier menor** significa que a chance calculada pelo modelo ficou mais próxima
do que ocorreu do que a regra “sempre zero”. **MAE maior** significa que ele
errou mais a quantidade exata, em média. Muitas janelas ficaram vazias, então
sempre dizer zero favorece o MAE, embora essa regra nunca antecipe circulação.
São medidas diferentes e ambas devem aparecer na apresentação.

| Repouso pedido pela zona | Total de janelas | Janelas que depois tiveram ativação |
| --- | ---: | ---: |
| PWM 10 | 4.071 | 160 |
| PWM 20 | 17.127 | 2.532 |
| PWM 50 | 2.970 | 818 |

Houve atividade em 3.510 janelas de zona. Destas, **160 (4,6%)** começaram em
PWM 10. Das 2.970 janelas iniciadas em PWM 50, 818 tiveram atividade e 2.152
ficaram vazias. Isso não significa falha do sensor: ao detectar movimento, o
controle imediato ainda deverá levar o LED ao alvo máximo com o fade.

## Repouso final por LED da maquete

Um LED pode pertencer a várias zonas; seu alvo é o **maior PWM pedido** por
elas. O relatório aplicou essa regra aos dez LEDs da topologia de avaliação.

| Alvo do LED no começo da janela | LED-janelas |
| --- | ---: |
| PWM 10 | 6.294 |
| PWM 20 | 28.732 |
| PWM 50 | 5.254 |
| **Total** | **40.280** |

Em 11.616 LED-janelas houve depois uma ativação em pelo menos uma zona ligada
ao LED. **556 (4,8%)** dessas LED-janelas começaram em PWM 10; 2.704 começaram
em PWM 50. Uma mesma ativação pode marcar vários LEDs associados como ativos,
portanto esses totais não são contagens de pessoas, veículos ou detecções únicas.

O alvo fixo anterior colocaria todas as 40.280 LED-janelas em PWM 20. Com o
modelo, o alvo médio foi **22,35**, ou **2,35 pontos de PWM acima** do fixo.
Logo, este teste **não demonstra redução do alvo médio** na maquete. Ele mostra
repouso baixo em parte das janelas e alto em outras. PWM médio também **não é
energia medida**: faltam corrente, potência, duração do fade e tempo em PWM
255 para calcular consumo ou economia.

## Alcance do resultado

Os arquivos locais `data/evaluated/holdout/window_decisions.csv`,
`luminaire_decisions.csv` e `final_report.json` permitem inspecionar cada
decisão. O relatório registra semente e hashes do cenário, modelo, política e
topologia para reprodução. O modelo já havia sido escolhido quando executamos
o `holdout`; esse conjunto não será usado para reajustar o mesmo modelo e
depois apresentar uma nova medição como independente. O resultado mede o
desempenho **neste cenário sintético**, não a precisão em uma rua residencial
real. Na data desta avaliação, o cálculo ainda não havia sido integrado ao
ESP32; a integração ocorreu posteriormente.
