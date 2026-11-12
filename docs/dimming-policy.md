# Política de brilho de repouso

O modelo treinado estima a quantidade média de ativações de uma zona na
próxima janela de 15 minutos e a chance de haver ao menos uma ativação.
A política em `config/dimming_policy.json` usa **essa chance**, não a contagem
diretamente, para escolher o PWM de repouso:

| Chance prevista | Nível | PWM de 8 bits |
| --- | --- | ---: |
| Menor que 5% | Baixo | 10/255 |
| De 5% até menos de 30% | Padrão | 20/255 |
| A partir de 30% | Alto | 40/255 |

O PWM alto foi ajustado para 40 após comparação visual na maquete. Mantivemos
o limite baixo de 5% e adotamos 30% para o alto após uma comparação
exploratória em cenários sintéticos. Os relatórios anteriores, inclusive
[`holdout-evaluation.md`](holdout-evaluation.md), registram a política
**10/20/50 com limites 5%/25%** e não comprovam o desempenho da política
atual em um teste independente. Ela ainda não foi avaliada em circulação
real. O percentual de probabilidade
e o valor de PWM são grandezas diferentes. PWM não mede diretamente consumo
elétrico.

`load_policy()` valida o JSON, inclusive a ordem crescente dos PWM e dos
limites. `level_for_probability()` decide baixo, padrão ou alto;
`pwm_for_probability()` devolve o número correspondente. Uma probabilidade
inválida é rejeitada. O módulo não consulta a API nem altera o firmware.
Depois de escolher o PWM por zona, `rest_pwm_by_luminaire()` aplica o maior
pedido aos LEDs que pertencem a várias zonas, usando o mapa da maquete em
`config/maquette_topology.json`.

Exemplo: se `PoissonModel.predict()` devolver chance 0,18, a política escolhe
`standard`, PWM 20/255. Se devolver 0,32, escolhe `high`, PWM 40/255.
Mudar esses valores no JSON não altera os pesos do modelo, pois o modelo
aprende a prever ativações, não valores de PWM. Quando a política chegar ao
ESP32, é necessário gravar o firmware com o cabeçalho gerado atualizado.

Este arquivo descreve apenas o **repouso**. No firmware, o sensor ativo
continua tendo alvo 255/255 e a subida e descida mantêm o fade testado na
maquete. LEDs compartilhados por zonas usam o maior nível solicitado. Se
faltar horário válido ou histórico suficiente para a previsão, o repouso
fica em 20/255.

Comparamos os limites baixos de 5%, 10% e 15% nos dias de validação e
escolhemos 5% para a configuração inicial. Os resultados históricos com
o corte alto anterior de 25% e PWM 50 estão em
[`dimming-validation.md`](dimming-validation.md) e por LED em
[`luminaire-validation.md`](luminaire-validation.md).
