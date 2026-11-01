# Topologia de referência da maquete

Esta tabela descreve a topologia cadastrada no banco de dados da
SmartLighting.Api.

Os nomes `S01`–`S06` e `Z01`–`Z06` são identificadores neutros dos cenários
simulados. Correspondem aos nomes **Sensor 1**–**Sensor 6** e **Zone 1**–**Zone 6**
da maquete, mas não são os GUIDs da API. Os GUIDs não são entradas do modelo.

| Cenário | Cadastro | ESP32 | Slot do sensor | LEDs associados à zona |
| --- | --- | --- | ---: | --- |
| S01 / Z01 | Sensor 1 / Zone 1 | A | 1 | LED 1, 2, 9, 10 |
| S02 / Z02 | Sensor 2 / Zone 2 | A | 2 | LED 2, 3, 4 |
| S03 / Z03 | Sensor 3 / Zone 3 | A | 3 | LED 3, 4, 5, 6 |
| S04 / Z04 | Sensor 4 / Zone 4 | B | 1 | LED 4, 5, 6, 7 |
| S05 / Z05 | Sensor 5 / Zone 5 | B | 2 | LED 6, 7, 8, 9 |
| S06 / Z06 | Sensor 6 / Zone 6 | B | 3 | LED 1, 8, 9, 10 |

ESP32 A: `63E7E2AF-FAE6-4D75-83AB-F13D946C84F0`.
ESP32 B: `CFB1584F-7B40-466D-89D8-8E4CDB34E49A`.

| LED | ESP32 | Slot | Zonas associadas |
| --- | --- | ---: | --- |
| 1 | A | 1 | 1, 6 |
| 2 | A | 2 | 1, 2 |
| 3 | A | 3 | 2, 3 |
| 4 | A | 4 | 2, 3, 4 |
| 5 | A | 5 | 3, 4 |
| 6 | B | 1 | 3, 4, 5 |
| 7 | B | 2 | 4, 5 |
| 8 | B | 3 | 5, 6 |
| 9 | B | 4 | 1, 5, 6 |
| 10 | B | 5 | 1, 6 |

São **6 sensores, 6 zonas, 10 LEDs físicos e 23 vínculos zona–LED**. Cada zona
tem um sensor nesta maquete, mas a preparação dos dados deverá aceitar vários
sensores na mesma zona. Um LED pode pertencer a várias zonas. Quando houver
previsões diferentes para esse LED, o brilho de repouso será o **maior** nível
solicitado pelas zonas associadas. Uma detecção imediata continua tendo
prioridade e leva o LED ao nível máximo.

Alguns LEDs de A são associados a zonas cujo sensor está em B, e vice-versa.
O firmware já troca estados de movimento por UART para o controle imediato.
Antes de implementar o brilho preditivo, precisamos decidir como as previsões
ou contagens recentes cruzarão os dois ESP32. Pacotes repetidos de estado ativo
não podem ser contados como novas ativações.

Os cenários atuais reproduzem apenas a **estrutura** de um sensor por zona.
As taxas de ativação e os multiplicadores horários continuam hipóteses não
calibradas; nenhuma taxa do banco ou de fonte externa foi extraída para eles.
