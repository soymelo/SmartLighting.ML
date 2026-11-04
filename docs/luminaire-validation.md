# Validação exploratória do repouso por LED

Este relatório aplica aos LEDs da [topologia da maquete](maquette-topology.md)
as decisões por zona descritas em [dimming-validation.md](dimming-validation.md).
Os dados são **sintéticos** e cobrem os sete dias de validação de 22 a 28 de
agosto de 2026. Os 14 dias finais não foram usados nesta análise por LED,
mas já foram consultados na avaliação anterior de regras de referência. O
cenário `holdout` continua reservado. Como a validação já orientou escolhas
anteriores, estes resultados são exploratórios.

Para cada horário de 15 minutos e cada candidato de limite baixo, reunimos
os pedidos PWM das seis zonas. Um LED associado a mais de uma zona recebe o
**maior** pedido. Exemplo: se suas zonas pedem 10, 20 e 50, o LED recebe 50.
O relatório registra também se pelo menos uma zona ligada ao LED teve
ativação durante os 15 minutos seguintes. Essa informação posterior serve
apenas para avaliação; não participa da decisão de brilho.

Cada candidato tem 672 horários × 10 LEDs = **6.720 LED-janelas**. As três
alternativas de limite baixo (5%, 10% e 15% de probabilidade prevista) usam
exatamente as mesmas previsões e os mesmos eventos. O limite alto permanece
em 25%; os níveis possíveis de repouso são PWM 10, 20 e 50, na escala 0–255.

| Cenário | Repouso baixo se chance < | LED-janelas PWM 10 | PWM 20 | PWM 50 | LED-janelas ativas iniciadas em PWM 10 | PWM médio por LED-janela |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | 5% | 970 | 5.076 | 674 | 52 de 1.829 | 21,57 |
| Desenvolvimento | 10% | 2.926 | 3.120 | 674 | 406 de 1.829 | 18,65 |
| Desenvolvimento | 15% | 4.569 | 1.477 | 674 | 869 de 1.829 | 16,21 |
| Atividade persistente | 5% | 1.089 | 4.703 | 928 | 64 de 1.815 | 22,52 |
| Atividade persistente | 10% | 1.849 | 3.943 | 928 | 128 de 1.815 | 21,39 |
| Atividade persistente | 15% | 4.114 | 1.678 | 928 | 730 de 1.815 | 18,02 |

Uma **LED-janela ativa** significa que houve ao menos uma ativação em qualquer
zona ligada àquele LED. Assim, uma mesma ativação pode marcar vários LEDs
como ativos. No cenário persistente com limite baixo escolhido de 5%, 64 das 1.815
LED-janelas ativas começariam em PWM 10; nos outros casos ativos, o repouso
seria 20 ou 50. O sensor continuaria levando a iluminação ao máximo durante
a detecção, conforme o controle do firmware. O relatório só examina o repouso
planejado no início da janela.

O maior pedido entre zonas altera o resultado físico. Por exemplo, no cenário
persistente com limite de 5%, havia 690 **janelas de zona** em PWM 10, mas
1.089 **LED-janelas** em PWM 10; são quantidades com denominadores diferentes
(4.032 janelas de zona contra 6.720 LED-janelas), portanto não devem ser
comparadas como se a diferença fosse causada apenas pelo compartilhamento.
O CSV por LED mostra, para cada LED, os pedidos de suas zonas e o alvo final.

A média da tabela é aritmética: soma dos alvos PWM dividida pelas 6.720
LED-janelas. Ela pode ser comparada numericamente ao alvo fixo PWM 20, mas
**não é consumo de energia nem porcentagem de economia**. Não modelamos
potência real em função do PWM, o tempo de transição suave, a permanência
em PWM 255 após detecção nem o circuito elétrico. Portanto, ainda não há
medição de economia. O relatório mostra o compromisso entre usar mais vezes
PWM 10 e iniciar mais LED-janelas com movimento nesse nível. Escolhemos **5%**
como limite baixo para reduzir essas ocorrências e mantivemos **25%** como
limite alto. Os resultados continuam restritos à validação sintética; a
política escolhida ainda não passou pela avaliação final reservada.

## Arquivos e reprodução

Após executar os comandos do README, cada diretório `data/evaluated/<cenário>/`
contém:

- `luminaire_decisions.csv`: uma linha por limite, horário e LED. Registra
  `zone_pwm_requests`, `rest_pwm` e as ativações observadas nas zonas ligadas.
- `luminaire_summary.json`: contagens gerais e individuais de cada LED,
  inclusive quantas LED-janelas ativas começaram em PWM 10 e o PWM médio.

Os arquivos gerados ficam fora do Git e podem ser recriados. O código do
relatório lê a topologia informada no comando; o modelo não incorpora os
GUIDs ou o número de LEDs da maquete. Uma topologia diferente pode ser
avaliada com outras associações entre zonas e LEDs. O modelo geral aceita IDs
de zonas inéditas após haver histórico suficiente; a integração ao firmware
ainda está pendente.
