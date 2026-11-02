# Validação exploratória do repouso por LED

Este relatório aplica aos LEDs da [topologia da maquete](maquette-topology.md)
as decisões por zona descritas em [dimming-validation.md](dimming-validation.md).
Os dados são **sintéticos** e cobrem os sete dias de validação de 22 a 28 de
agosto de 2026. O teste final de 14 dias e o cenário `holdout` continuam
reservados. Como a validação já orientou escolhas anteriores, estes resultados
são exploratórios.

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
| Desenvolvimento | 5% | 678 | 5.321 | 721 | 45 de 1.829 | 22,21 |
| Desenvolvimento | 10% | 2.654 | 3.345 | 721 | 329 de 1.829 | 19,27 |
| Desenvolvimento | 15% | 4.332 | 1.667 | 721 | 793 de 1.829 | 16,77 |
| Atividade persistente | 5% | 790 | 4.926 | 1.004 | 46 de 1.815 | 23,31 |
| Atividade persistente | 10% | 1.807 | 3.909 | 1.004 | 117 de 1.815 | 21,79 |
| Atividade persistente | 15% | 3.885 | 1.831 | 1.004 | 674 de 1.815 | 18,70 |

Uma **LED-janela ativa** significa que houve ao menos uma ativação em qualquer
zona ligada àquele LED. Assim, uma mesma ativação pode marcar vários LEDs
como ativos. No cenário persistente com limite baixo de 10%, 117 das 1.815
LED-janelas ativas começariam em PWM 10; nos outros casos ativos, o repouso
seria 20 ou 50. O sensor continuaria levando a iluminação ao máximo durante
a detecção, conforme o controle do firmware. O relatório só examina o repouso
planejado no início da janela.

O maior pedido entre zonas altera o resultado físico. Por exemplo, no cenário
persistente com limite de 10%, havia 1.272 **janelas de zona** em PWM 10, mas
1.807 **LED-janelas** em PWM 10; são quantidades com denominadores diferentes
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
avaliada se usar as mesmas zonas para as quais há previsões. Zonas inéditas
exigem uma regra explícita de funcionamento, ainda pendente.
