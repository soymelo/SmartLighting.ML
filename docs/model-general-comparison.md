# Comparação do modelo geral com o modelo por zona

Queremos saber se uma zona cadastrada depois pode usar a previsão sem precisar
retreinar. A regressão atual usa a identidade `Z01`–`Z06` como entrada e não
aceita um ID novo. A variante geral remove **somente** essa entrada; preserva
a regressão de Poisson, a biblioteca de treino, hora, fim de semana e contagem
dos 30 minutos anteriores. Assim, um ID novo não muda o cálculo se os demais
dados de entrada forem iguais. A topologia continua necessária para agrupar
detecções por zona e combinar os pedidos dos LEDs.

Usamos os CSVs **sintéticos já preparados** para `development` e
`persistent_activity`, sem gerar outros eventos. Ambos os modelos foram
ajustados nos primeiros 21 dias e avaliados nos sete dias seguintes. Fixamos
o histórico de 30 minutos, escolhido em análise anterior, e a política de
repouso já definida: PWM 10 se chance < 5%, PWM 20 até menos de 25% e PWM 50
a partir de 25%. A comparação é exploratória: a escolha dos 30 minutos e dos
limites já considerou esses dias de validação. Não usamos os 14 dias finais
nem o cenário `holdout`.

| Cenário | Modelo | Brier ↓ | MAE ↓ | Janelas de zona ativas iniciadas em PWM 10 | LED-janelas ativas iniciadas em PWM 10 | PWM médio por LED-janela |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | Por zona | 0,10965 | 0,233 | 17 | 45 | 22,21 |
| Desenvolvimento | Geral | 0,11014 | 0,235 | 15 | 52 | 21,57 |
| Atividade persistente | Por zona | 0,10888 | 0,249 | 15 | 46 | 23,31 |
| Atividade persistente | Geral | 0,10930 | 0,249 | 18 | 64 | 22,52 |

**Brier** mede o erro da chance prevista de ocorrer alguma ativação; **MAE**
mede o erro médio na quantidade prevista. Menor é melhor nas duas métricas.
O modelo geral perdeu um pouco de precisão probabilística nos dois cenários.
No cenário persistente, 64 LED-janelas ativas começaram em PWM 10 com o geral,
contra 46 com o modelo por zona. Em uma mesma janela, um evento pode marcar
mais de um LED como ativo. A média de PWM é apenas uma média dos alvos de
repouso, não uma medida de potência ou economia de energia.

## Teste de zona inédita

Para simular uma zona ausente do treino, repetimos o experimento seis vezes.
Em cada repetição, excluímos **todos** os exemplos de uma zona dos 21 dias
de treino; ajustamos o modelo geral com as outras cinco zonas e prevemos a
zona excluída nos sete dias de validação. Depois reunimos as previsões das
seis repetições. Assim, cada previsão abaixo é para uma zona que o respectivo
modelo nunca viu durante o treino. Esse teste não usa o cenário `holdout`:
"zona excluída" aqui descreve somente o procedimento de comparação.

| Cenário | Brier na zona inédita ↓ | Janelas de zona em PWM 10 | Destas, quantas tiveram movimento | Janelas em PWM 50 |
| --- | ---: | ---: | ---: | ---: |
| Desenvolvimento | 0,11045 | 625 | 16 | 312 |
| Atividade persistente | 0,10952 | 716 | 18 | 528 |

O resultado mostra que a variante geral **consegue executar e escolher os
três níveis** para uma zona cujo ID não participou do treino, com erro próximo
ao observado nas zonas conhecidas desses cenários. Isso não prova que servirá
com a mesma precisão em qualquer rua: as seis zonas foram produzidas pelas
mesmas hipóteses sintéticas. Uma topologia real muito diferente pode exigir
revisão do modelo ou novos dados de treino.

Nos primeiros 30 minutos após iniciar uma zona, ainda não existe todo o
histórico que esse modelo exige. O comportamento proposto para a futura
integração é PWM 20 até completar duas janelas de 15 minutos; depois a
previsão poderá escolher 10, 20 ou 50. Essa regra de inicialização **ainda
não está implementada no firmware**. Juntar 30 minutos fornece uma entrada
para a previsão; não retreina os pesos nem ensina sozinho um padrão próprio
da zona nova.

Os comandos no README recriam `data/compared/development.json` e
`data/compared/persistent_activity.json`, com métricas completas, decisões
por zona e por LED e resultados individuais das seis zonas excluídas.

## Decisão após a comparação

Adotamos o **modelo geral** para a futura integração porque aceitar novas
zonas sem retreinar a cada cadastro é um objetivo do projeto. A pequena perda
observada nas métricas foi aceita como compromisso explícito; ela não permite
afirmar que o modelo geral seja superior em precisão. `train_general.py`
exporta os pesos ajustados com os primeiros 28 dias de cada cenário, sem
consultar os 14 dias finais. `zone_rest.py` usa PWM 20 enquanto faltar o
histórico de 30 minutos e, após completá-lo, aplica a previsão geral e os
limites de 5%/25%. Ambos ainda funcionam apenas em Python.
