# Avaliação inicial de regras simples

> **Registro histórico.** A tabela e os exemplos abaixo foram calculados com
> a curva horária anterior. Os novos resultados da mesma rotina aparecem na
> seção final; não compare métricas de períodos de teste diferentes como se
> fossem uma disputa direta com o ML.

Esta avaliação estabelece referências **antes** do treinamento de Machine
Learning. Usa os conjuntos sintéticos de `development` e
`persistent_activity`, gerados com início em 2026-08-01, 42 dias e semente 42.
Os metadados de cada conjunto registram a identificação exata do cenário.
Não usa `holdout`.

Para reproduzir, depois de gerar e preparar os dois cenários:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m smartlighting_ml.evaluate --input-dir data/processed/development --input-dir data/processed/persistent_activity --train-days 28
```

Os primeiros 28 dias locais (16.104 exemplos) servem para calcular a regra por
zona e hora. Os 14 dias seguintes, a partir de 2026-08-29 (8.064 exemplos),
servem somente para teste. Escolhemos 28 + 14 porque os dados gerados cobrem
42 dias: são quatro semanas anteriores e duas posteriores, incluindo dias
úteis e fins de semana nos dois períodos. **Quatorze dias não são um tamanho
ideal comprovado.** A ordem cronológica evita usar respostas futuras para
calcular a regra avaliada. As três regras recebem os mesmos exemplos de teste:

| Regra | Contagem prevista | Probabilidade usada para sinalizar atividade |
| --- | --- | --- |
| `zero` | Sempre 0 | Sempre 0 |
| `zona_hora` | Média da contagem da mesma zona e hora no treino | Fração de janelas ativas da mesma zona e hora no treino |
| `ultima_janela` | Repete a contagem dos 15 minutos anteriores | 1 se a janela anterior teve alguma ativação; senão, 0 |

MAE e RMSE medem erro na **quantidade** de ativações; menor é melhor. RMSE
penaliza mais os erros grandes. Brier mede o erro da **probabilidade** de haver
ao menos uma ativação na próxima janela; menor é melhor. Recall indica qual
fração das janelas com atividade recebeu um alerta, e precisão indica qual
fração dos alertas correspondeu a atividade. Para essas duas medidas e a taxa
de alertas, usamos provisoriamente probabilidade de **20%** como limiar: se a
regra estima pelo menos 20 chances em 100 de haver alguma ativação na próxima
janela, marcamos aquela janela como alertada. Isso **não** significa 20% de
brilho, 20% das pessoas ou 20% de erro. Não é um limite de segurança. Precisão é indefinida
para `zero`, que nunca alerta.

## Resultados do teste

| Cenário | Regra | MAE ↓ | RMSE ↓ | Brier ↓ | Recall ↑ | Precisão ↑ | Janelas alertadas |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | `zero` | 0,138 | 0,407 | 0,125 | 0,0% | — | 0,0% |
| Desenvolvimento | `zona_hora` | 0,224 | 0,370 | 0,103 | 34,4% | 26,8% | 16,0% |
| Desenvolvimento | `ultima_janela` | 0,228 | 0,520 | 0,202 | 18,7% | 18,7% | 12,5% |
| Atividade persistente | `zero` | 0,157 | 0,457 | 0,137 | 0,0% | — | 0,0% |
| Atividade persistente | `zona_hora` | 0,250 | 0,413 | 0,110 | 47,3% | 25,8% | 25,0% |
| Atividade persistente | `ultima_janela` | 0,254 | 0,568 | 0,215 | 21,3% | 21,3% | 13,7% |

No teste, 12,5% das janelas de desenvolvimento e 13,7% das janelas de
atividade persistente tiveram ao menos uma ativação. Isso explica por que
`zero` apresenta o menor MAE: acertar muitas janelas vazias compensa, nessa
métrica, todas as falhas nos períodos ativos. Seu recall de 0% mostra o limite
operacional dessa regra.

`zona_hora` obteve Brier e RMSE menores que as outras regras nos dois cenários.
`ultima_janela` isolada não foi uma boa previsão: repetir exatamente a última
contagem é uma regra grosseira, e sua probabilidade 0 ou 1 não é calibrada.
Isso **não prova** que as contagens recentes sejam inúteis quando combinadas
com hora e zona. O próximo experimento deve testar essa combinação e comparar
históricos de 15, 30 e 60 minutos no mesmo período de teste.

Para tornar recall e precisão concretos: no teste de `persistent_activity`,
**1.101** das 8.064 janelas tiveram ao menos uma ativação. A regra `zona_hora`
alertou em **2.016** janelas: **521** eram realmente ativas, **1.495** ficaram
vazias e **580** janelas ativas não foram alertadas. Portanto, recall é
`521 / 1.101 = 47,3%` e precisão é `521 / 2.016 = 25,8%`. A regra
`ultima_janela` alertou em **1.102** janelas, acertou **235** e deixou de
alertar **866** janelas ativas. Esses alertas são apenas classificações no
relatório; ainda não comandam luminárias.

Esses resultados se referem somente aos cenários sintéticos declarados.
Ainda não medem economia de energia, percepção visual, segurança da maquete
nem desempenho de um modelo de ML no ESP32.

## Reexecução após revisar a curva horária

Recriamos os dois conjuntos com 42 dias e semente 42. A regra `zona_hora`
foi calculada nos primeiros 28 dias e testada nos 14 dias seguintes. O
limiar ilustrativo de alerta permaneceu em 20%; ele não controla o PWM.

| Cenário | Regra | MAE ↓ | RMSE ↓ | Brier ↓ | Recall ↑ | Precisão ↑ | Janelas alertadas |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | `zero` | 0,135 | 0,405 | 0,121 | 0,0% | — | 0,0% |
| Desenvolvimento | `zona_hora` | 0,223 | 0,373 | 0,102 | 33,2% | 23,1% | 17,4% |
| Desenvolvimento | `ultima_janela` | 0,233 | 0,531 | 0,207 | 14,7% | 14,7% | 12,1% |
| Atividade persistente | `zero` | 0,155 | 0,442 | 0,139 | 0,0% | — | 0,0% |
| Atividade persistente | `zona_hora` | 0,251 | 0,404 | 0,114 | 41,7% | 23,8% | 24,3% |
| Atividade persistente | `ultima_janela` | 0,250 | 0,554 | 0,219 | 20,9% | 20,9% | 13,9% |

Os novos modelos gerais foram comparados em sete dias de validação, conforme
`model-selection.md`. Para afirmar vantagem do ML sobre `zona_hora`, ambos
precisam ser avaliados nos mesmos exemplos e com a mesma separação temporal.
