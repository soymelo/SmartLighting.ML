# Escolha dos pesos para o firmware

> **Registro histórico.** A tabela e a decisão abaixo usam a curva horária
> anterior e a política PWM 10/20/50 com limites 5%/25%. Os resultados do
> novo treino estão na seção final. Os pesos em `config/firmware_model.json`
> ainda são os antigos; o treino novo não foi exportado para o ESP32.

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

Na avaliação histórica, escolhemos o modelo treinado em **atividade persistente**
para o firmware. Ele
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
entradas calculadas com esses pesos e a política então vigente de 5%/25%, para
conferir o cálculo em C++. O modelo e os resultados continuam limitados às hipóteses
dos cenários sintéticos; a maquete verificará a execução física, não a precisão
em uma rua real.

## Novo treino com a curva horária revisada

Os dois cenários agora compartilham a mesma curva horária revisada. Geramos
novamente 42 dias com semente 42. Para esta comparação, ajustamos cada modelo
nos dias 1–21 e avaliamos ambos nos mesmos dias 22–28 de cada cenário: 4.032
janelas de zona por cenário. A política analisada é PWM 10/20/40, com baixo
abaixo de 5% e alto a partir de 30% de chance prevista. O teste final de 14
dias e o `holdout` não participaram da comparação.

| Cenário avaliado | Treinado em | Brier ↓ | MAE ↓ | Janelas PWM 10 (ativas) | Janelas PWM 40 (ativas) | PWM médio por zona-janela |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | Desenvolvimento | 0,10308 | 0,22457 | 719 (16) | 0 (0) | 18,22 |
| Desenvolvimento | Atividade persistente | 0,10352 | 0,23941 | 376 (5) | 197 (51) | 20,04 |
| Atividade persistente | Desenvolvimento | 0,11382 | 0,24033 | 720 (17) | 0 (0) | 18,21 |
| Atividade persistente | Atividade persistente | 0,11345 | 0,25500 | 365 (5) | 227 (67) | 20,22 |

Na validação de desenvolvimento, 497 janelas tiveram atividade; na de
atividade persistente, 561. Cada modelo obteve Brier ligeiramente menor no
próprio cenário. O modelo de desenvolvimento nunca pediu PWM 40 nessas
janelas. O modelo persistente pediu PWM 40 inclusive em algumas janelas que
acabaram vazias. Isso é um compromisso entre repouso preventivo e tempo em
brilho mais alto, não evidência de economia elétrica. Os pesos finais
reajustados nos primeiros 28 dias estão em `models/development/model.json` e
`models/persistent_activity/model.json`; escolher e exportar um deles para o
firmware exige uma decisão separada. O relatório reproduzível está em
`data/evaluated/model_comparison.json`.

### Comparação direta com uma regra simples

Na mesma divisão de 21 dias de treino e sete de validação, recalculamos a
regra `zona_hora` de `evaluate.py` e o modelo geral treinado no próprio
cenário. A regra simples usa a identidade da zona e a hora, mas ignora as
ativações recentes; o modelo geral usa hora e histórico recente, sem a
identidade da zona.

| Cenário avaliado | Brier de `zona_hora` ↓ | Brier do ML geral ↓ |
| --- | ---: | ---: |
| Desenvolvimento | 0,10443 | 0,10308 |
| Atividade persistente | 0,11423 | 0,11345 |

O ML teve Brier ligeiramente menor nos dois cenários, mas a diferença é
pequena e foi medida somente em dados sintéticos. Essa comparação não prova
precisão em uma zona real nem vantagem energética.
