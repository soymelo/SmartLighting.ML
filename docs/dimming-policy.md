# Política de brilho de repouso

O modelo treinado estima a quantidade média de ativações de uma zona na
próxima janela de 15 minutos e a chance de haver ao menos uma ativação.
A política em `config/dimming_policy.json` usa **essa chance**, não a contagem
diretamente, para escolher o PWM de repouso:

| Chance prevista | Nível | PWM de 8 bits |
| --- | --- | ---: |
| Menor que 5% | Baixo | 10/255 |
| De 5% até menos de 25% | Padrão | 20/255 |
| A partir de 25% | Alto | 50/255 |

Os níveis PWM 10/20/50 foram aceitos para a maquete. Escolhemos os **limites
de probabilidade** de 5% e 25% após comparar decisões nos dados sintéticos
de validação. O corte baixo de 5% reduz as janelas ativas que começam em PWM
10 em relação às alternativas de 10% e 15%. O corte alto de 25% foi mantido;
não o comparamos com outras alternativas. A política ainda não foi avaliada
no teste final reservado nem em circulação real. O percentual de probabilidade
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
`standard`, PWM 20/255. Se devolver 0,28, escolhe `high`, PWM 50/255.
Mudar esses valores no JSON não altera os pesos do modelo, pois o modelo
aprende a prever ativações, não valores de PWM. Quando a política chegar ao
ESP32, será necessário publicar a configuração atualizada na placa.

Este arquivo descreve apenas o **repouso**. No firmware atual, o sensor ativo
continua tendo alvo 255/255 e a subida e descida mantêm o fade testado na
maquete. Na futura integração, LEDs compartilhados por zonas deverão usar o
maior nível de repouso solicitado. Se faltar horário válido para a previsão,
o padrão proposto é o nível intermediário de 20/255. O mesmo padrão é usado
em Python durante os primeiros 30 minutos de uma zona, até haver histórico
suficiente para o modelo geral. Essa regra ainda não foi integrada ao firmware.

Comparamos os limites baixos de 5%, 10% e 15% nos dias de validação e
escolhemos 5% para a configuração. Os resultados por zona estão em
[`dimming-validation.md`](dimming-validation.md) e por LED em
[`luminaire-validation.md`](luminaire-validation.md).
