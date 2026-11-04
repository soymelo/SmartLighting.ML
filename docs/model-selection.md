# Escolha dos pesos para o firmware

Os dois modelos gerais foram treinados com dados **simulados**, sem usar IDs de
zona como entrada. Para comparar os pesos sem favorecer o cenário de origem,
ajustamos um modelo com os dias 1–21 de `development` e outro com os dias 1–21
de `persistent_activity`. Ambos foram avaliados nas mesmas 4.032 janelas dos
dias 22–28 de cada cenário. O teste final de 14 dias e `holdout` não entraram
nesta comparação. Os arquivos exportados com 28 dias só serão usados após a
escolha; avaliá-los nos dias 22–28 contaminaria a validação.

| Cenário avaliado | Modelo treinado em | Brier ↓ | MAE ↓ | Janelas em PWM 10 (ativas) | Janelas em PWM 50 (ativas) | PWM médio por zona-janela |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | Desenvolvimento | 0,11014 | 0,23466 | 592 (15) | 340 (107) | 21,06 |
| Desenvolvimento | Atividade persistente | 0,10954 | 0,24845 | 692 (18) | 529 (154) | 22,22 |
| Atividade persistente | Desenvolvimento | 0,10957 | 0,23515 | 587 (16) | 323 (109) | 20,95 |
| Atividade persistente | Atividade persistente | 0,10930 | 0,24939 | 690 (18) | 530 (164) | 22,23 |

Em `development`, 542 das 4.032 janelas tiveram alguma ativação; em
`persistent_activity`, 544. **Brier** mede o erro da chance prevista de haver
pelo menos uma ativação: menor é melhor. **MAE** mede o erro médio na quantidade
prevista de ativações: menor é melhor. O número entre parênteses é quantas
janelas daquele nível realmente tiveram atividade. PWM 10/20/50 são alvos de
repouso, não medições de consumo ou economia de energia.

Escolhemos o modelo treinado em **atividade persistente** para o firmware. Ele
teve Brier um pouco menor nos dois cenários e colocou mais janelas que acabaram
ativas no repouso alto: 154 contra 107 em `development`, e 164 contra 109 em
`persistent_activity`. A diferença de Brier é pequena, então não afirmamos uma
grande melhora de precisão. O compromisso é claro: ele também escolhe PWM 50
em cerca de 200 janelas adicionais por cenário, tem MAE maior e coloca duas ou
três janelas ativas adicionais em PWM 10. O objetivo do TCC nesta escolha é
antecipar atividade para o repouso preventivo, mantendo o sensor como prioridade
quando ocorre movimento. Não há evidência de economia elétrica nessa tabela.

O arquivo `config/firmware_model.json` contém o ajuste final escolhido com os
primeiros **28 dias** de atividade persistente. Não é o mesmo ajuste de 21 dias
usado para comparar os candidatos. `config/firmware_reference.json` contém oito
entradas calculadas com esses pesos e a política de 5%/25%, para conferir o
futuro cálculo em C++. O modelo e os resultados continuam limitados às hipóteses
dos cenários sintéticos; a maquete verificará a execução física, não a precisão
em uma rua real.
