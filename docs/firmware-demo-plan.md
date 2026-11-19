# Demonstração do ML na maquete

O modelo já foi integrado ao ESP32. Os pesos de `persistent_activity` com a
curva horária revisada foram exportados para `config/firmware_model.json` e para
`SmartLighting.Firmware/src/Control/ActivityModelWeights.h`. O firmware usa
5%/30% e PWM 10/20/40. A demonstração da previsão pode usar janelas reais
completas ou registros previamente capturados no monitor serial. O firmware
não possui comando para avançar artificialmente as janelas.

## Recursos disponíveis

- O firmware busca a topologia na API, mantém a última topologia válida na
  flash e envia telemetria. O controle imediato dos sensores funciona na
  placa sem esperar a API.
- O firmware conta novas ativações por zona, mantém as últimas janelas,
  calcula a previsão localmente e informa no monitor serial a chance e o PWM
  de repouso por zona e LED. A comunicação entre placas distingue o evento
  único de ativação das mensagens repetidas de estado ativo.
- `Serial` via USB é usada para mensagens a 115200 baud. Uma segunda UART liga
  as duas placas e transmite estados de movimento e a nova ativação.
- A Web e a API permanecem responsáveis pela configuração, pelo recebimento
  da telemetria e pela visualização. A inferência do modelo de dimerização é
  executada localmente nos dois controladores.

## Sequência de apresentação

1. Demonstrar uma ativação física do sensor elevando imediatamente a
   luminária ao nível máximo. Essa prioridade vale também com a API desligada.
2. Mostrar no monitor serial uma previsão calculada após duas janelas reais
   completas de 15 minutos ou apresentar um registro anterior, identificado
   como tal. Explicar a contagem recente, a chance prevista e o PWM escolhido.
3. Esperar terminar o acionamento imediato do sensor antes de observar o
   brilho de repouso. Como LEDs pertencem a várias zonas, mostrar também a
   previsão por zona e aplicar o maior nível solicitado ao LED compartilhado.
4. Repetir com a API desligada para demonstrar que ela não executa a
   inferência. A topologia válida deve ter sido recebida e armazenada antes.

Ao demonstrar sem a API, confirmar antes que as placas receberam e armazenaram
uma topologia válida. Sem horário válido ou histórico suficiente, o repouso
fica no PWM padrão 20 e os sensores continuam operando. Os níveis de repouso
configurados são PWM 10/20/40, com limites de 5% e 30% de chance prevista.
