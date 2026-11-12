# Hipóteses dos cenários simulados

Este documento registra como foram definidos `scenarios/development.json`,
`scenarios/holdout.json` e `scenarios/persistent_activity.json`. Eles servem
para desenvolver e testar o método de previsão de
**novas ativações de sensores por zona nos próximos 15 minutos**.
Uma ativação pode ser causada por qualquer movimento detectado; o gerador não
distingue pedestres, carros ou outras causas.

## Origem dos dados e limites

- A estrutura de seis sensores, seis zonas e suas associações com as luminárias
  veio dos cadastros no banco de dados da SmartLighting.Api. A correspondência
  está em [maquette-topology.md](maquette-topology.md). Os códigos `S01`–`S06` e
  `Z01`–`Z06` são nomes neutros, não os GUIDs do banco.
- **Todos os valores de circulação dos três JSONs são hipóteses ilustrativas.**
  Não vieram de medições da maquete, do banco da API nem de uma contagem de rua
  residencial. Não há evidência para afirmar que uma zona real recebe mais
  passagens que outra ou que o pico real ocorre exatamente às 19h.
- A maquete pode ser demonstrada em qualquer horário. Por isso, os cenários
  geram ativações nas 24 horas.

Resultados nesses dados demonstram a execução e a comparação dos métodos no
cenário definido. Não estimam precisão ou economia em uma rua real.

## Como cada número afeta a simulação

Para cada sensor e hora local, o gerador calcula uma taxa média por hora:

```text
taxa = base_events_per_hour × hour_multipliers[hora]
       × fator_de_fim_de_semana × fator_do_dia
```

O fator de fim de semana vale `weekend_multiplier` aos sábados e domingos e
`1` nos demais dias. O fator do dia é sorteado uma vez por dia no intervalo
`1 - daily_variation` até `1 + daily_variation`. Depois, o gerador sorteia a
quantidade de ativações de cada sensor em cada hora usando distribuição de
Poisson e distribui seus instantes dentro dessa hora. O número é uma **média
esperada**, não uma garantia de que ocorrerá uma ativação.

| Propriedade | Desenvolvimento | Holdout | Motivo da escolha |
| --- | --- | --- | --- |
| `scenario_id` | `development` | `holdout` | Identificar a origem de cada arquivo sem misturar os cenários. |
| `description` | Declara a simulação | Declara a reserva | Evitar apresentar hipóteses como medições. |
| `utc_offset_hours` | `-3` | `-3` | Representar a hora local da maquete; é um deslocamento fixo, sem calendário de fuso. |
| `hour_multipliers` | 24 valores | 24 valores | Posição 0 = 00h e posição 19 = 19h; multiplicam a taxa básica do sensor. |
| `weekend_multiplier` | `0.85` | `1.10` | Testar hipóteses distintas: menos circulação nos fins de semana no desenvolvimento e mais no cenário reservado. Nenhuma delas foi medida. |
| `daily_variation` | `0.20` | `0.30` | Impedir que dias equivalentes tenham exatamente a mesma taxa; o fator diário varia de 0,80 a 1,20 ou de 0,70 a 1,30. |
| `sensors` | Seis pares sensor/zona | Os mesmos seis pares | Espelhar a estrutura atual da maquete sem prender o gerador aos GUIDs. |
| `base_events_per_hour` | 0,45 a 0,80 | 0,50 a 0,80 | Criar zonas com intensidades diferentes para testar a preparação por zona. A ordem e os valores não representam posição física nem fluxo observado. |

Os 24 multiplicadores foram desenhados como uma curva **ilustrativa**:

| Horas locais | Desenvolvimento | Ideia representada |
| --- | --- | --- |
| 00h–05h | 0,09 a 0,40 | Circulação baixa na madrugada e início gradual às 05h. |
| 06h–09h | 0,80 a 1,30 | Aumento hipotético pela manhã. |
| 10h–16h | 0,75 a 1,05 | Circulação intermediária. |
| 17h–21h | 1,35 a 2,00 | Pico hipotético no início da noite; máximo às 19h. |
| 22h–23h | 0,45 a 0,80 | Redução hipotética no fim da noite. |

Os valores dentro de cada faixa foram escolhidos como hipótese para fazer uma
transição gradual. A Pesquisa Origem e Destino 2023 do Metrô de São Paulo
([página oficial](https://www.metro.sp.gov.br/pesquisa-od/)) ajuda a discutir
horários de deslocamento na região metropolitana, mas não mede ativações dos
sensores da maquete nem determina estes multiplicadores. Nenhuma fonte justifica
cada valor decimal ou comprova a curva de uma rua residencial. No `holdout`, a manhã
é relativamente mais forte, o pico noturno é menos concentrado às 19h e as
taxas por sensor são diferentes. Isso permite verificar a sensibilidade do
método a outra **hipótese simulada**, não sua generalização para dados reais.
O `holdout` permaneceu reservado até a primeira
[`avaliação final`](holdout-evaluation.md). A revisão atual da curva ocorreu
**depois** daquela avaliação; portanto, o mesmo `holdout` já não pode ser
apresentado como teste independente de um novo modelo escolhido agora.

Por exemplo, em um dia útil sem variação diária, `S01` às 19h no cenário de
desenvolvimento tem taxa média `0,80 × 2,00 = 1,60` ativação por hora, ou
`0,40` por intervalo de 15 minutos. Uma janela específica ainda pode ter zero
ativações. Às 03h, a taxa é `0,80 × 0,09 = 0,072` por hora.

## Cenário adicional com atividade persistente

`persistent_activity.json` reutiliza exatamente a curva horária, as taxas por
sensor, o fator de fim de semana e a variação diária de `development.json`.
Assim, a diferença conceitual é a presença de períodos temporários de maior
circulação. Não usamos o `holdout` para escolher esses parâmetros.

O gerador percorre janelas consecutivas de 15 minutos. Cada zona tem um estado
interno independente. Em uma janela calma, pode começar um período movimentado.
Ele persiste pelo número sorteado de janelas, inclusive se cruzar a meia-noite.
Enquanto durar, a taxa daquela zona é multiplicada antes de sortear as
ativações de seus sensores. Sensores na mesma zona compartilham esse estado.
Após o período, há pelo menos uma janela calma antes de um possível novo início.

| Parâmetro | Valor | Interpretação e razão da escolha |
| --- | ---: | --- |
| `start_probability_per_window` | `0.02` | Em cada janela calma, há 2% de chance de iniciar um período movimentado. O limite superior teórico é 1,92 início por dia e zona se todas as 96 janelas estivessem calmas. A escolha cria episódios ocasionais, sem dominar o dia. |
| `min_duration_windows` | `3` | Duração mínima de 45 minutos; após a primeira janela, ainda existem duas janelas com taxa elevada. |
| `max_duration_windows` | `5` | Duração máxima de 75 minutos; limita a persistência a um período curto. |
| `rate_multiplier` | `3.0` | Durante o período, a taxa esperada de ativações triplica. Escolhido para tornar o contraste observável sem eliminar as janelas vazias. |

**Esses números não foram calibrados com dados reais.** São parâmetros
ilustrativos para testar se a contagem recente acrescenta informação além da
hora local. Não significam que uma rua residencial tenha episódios exatamente
nessa frequência, duração ou intensidade.

Por exemplo, `S02` às 19h em um dia útil sem variação diária tem taxa básica
`0,65 × 2,00 × 15/60 = 0,325` ativação esperada por janela. Durante um
período movimentado, a média sobe para `0,975` por janela. A janela ainda
pode ter zero ativações em ambos os estados. Uma sequência recente com várias
ativações pode sugerir ao modelo que o período continua; não é garantia.

O estado interno **não aparece** em `sensor_events.csv`, `windows.csv` nem
`examples.csv`. O modelo terá apenas horário, zona e contagens já
observadas, como o firmware. A semente torna o sorteio reproduzível. O cenário
original permanece disponível para comparar o efeito dessa hipótese.

## O que os zeros significam

Na geração atual, com início em 2026-08-01, 42 dias e semente 42, o cenário
`development` produziu 3.230 ativações em 24.192 janelas por zona; 21.266
janelas (87,9%) tiveram contagem zero. `persistent_activity` produziu 3.788
ativações; 20.842 janelas (86,2%) ficaram vazias. **As janelas vazias são
dados válidos** e não devem ser
removidas ou preenchidas artificialmente.

Uma regra que prevê zero em todas as janelas acertaria a contagem exata em
87,9% das janelas de `development` e 86,2% das de `persistent_activity`, mas
nunca anteciparia atividade. Por isso, além do erro de contagem, avaliamos a
qualidade da probabilidade prevista e as janelas ativas iniciadas em cada
nível de repouso. PWM médio não equivale a consumo elétrico medido.

## Decisões metodológicas

1. Manter a origem sintética visível no CSV, nos metadados e nos resultados.
2. Usar os níveis PWM 10/20/40 definidos para a maquete e avaliar
   separadamente os limites de probabilidade que escolhem cada nível.
3. Comparar a previsão com referências simples, incluindo zero constante e
   uma regra baseada na hora, antes de afirmar vantagem do ML.
4. Comparar o cenário original com `persistent_activity` para avaliar se as
   contagens recentes ajudam a prever a próxima janela. O gerador original
   continua sorteando cada hora sem episódios persistentes explícitos.
5. Não alterar as taxas apenas para reduzir a proporção de zeros ou melhorar
   as métricas. Se houver medições ou uma fonte adequada depois, registrar sua
   origem e criar um cenário calibrado separadamente.
