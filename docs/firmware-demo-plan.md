# Plano futuro de demonstração do ML na maquete

Este documento registra uma proposta para a apresentação à banca. **O modo de
demonstração e o modelo no ESP32 ainda não foram implementados.**

## O que existe hoje

- O firmware busca a topologia na API, mantém a última topologia válida na
  flash e envia telemetria. O controle imediato dos sensores funciona na
  placa sem esperar a API.
- `Serial` via USB é usada para mensagens a 115200 baud. Uma segunda UART liga
  as duas placas e transmite estados de movimento ativo/liberado; enquanto um
  sensor está ativo, sua mensagem pode ser repetida.
- O Web e a API possuem uma página/rota `/ml/demo` da experiência antiga de
  anomalias em janelas de cinco minutos. Essa rota consulta resultados; não
  envia comandos ao firmware e não representa o novo modelo de dimerização.

## Demonstração proposta

1. Demonstrar uma ativação física do sensor elevando imediatamente a
   luminária ao nível máximo. Essa prioridade vale também com a API desligada.
2. Em um modo de demonstração **explicitamente identificado**, permitir que
   um comando local pelo monitor serial USB avance um relógio simulado em
   passos de 15 minutos. O ESP32 receberá contagens da janela encerrada,
   executará localmente o modelo e mostrará a previsão e o novo brilho de
   repouso. Uma sequência inicial pode preencher o histórico necessário sem
   exigir que a banca espere 30 minutos reais.
3. Esperar terminar o acionamento imediato do sensor antes de observar o
   brilho de repouso. Como LEDs pertencem a várias zonas, mostrar também a
   previsão por zona e aplicar o maior nível solicitado ao LED compartilhado.
4. Repetir com a API desligada para demonstrar que ela não executa a
   inferência. A topologia válida deve ter sido recebida e armazenada antes.

O comando local pode ser digitado no monitor serial; um botão físico pode
executar a mesma ação depois de conferir disponibilidade de GPIO. **Não há
necessidade de criar um botão no Web para essa demonstração.** Essa alternativa
exigiria um novo caminho de comandos Web → API → ESP32 e dependeria da API
durante o teste.

## Trabalho necessário no firmware

- Contar somente novas ativações confirmadas dos sensores. Mensagens repetidas
  de estado ativo na UART não podem virar novos eventos.
- Compartilhar com a outra placa as contagens relevantes por zona e o avanço
  da janela simulada. O protocolo UART atual só compartilha estados de
  movimento; precisa ser ampliado para manter as placas coerentes.
- Manter o cálculo normal em tempo real separado do modo de demonstração. No
  funcionamento normal, as janelas passam a cada 15 minutos reais; comandos
  de demonstração não devem alterar o relógio ou o histórico operacional.
- Executar o modelo localmente, definir um brilho padrão seguro quando faltar
  horário ou histórico e preservar a prioridade do sensor sobre a previsão.

Os níveis de repouso escolhidos para a maquete são PWM 10/20/50, com limite
baixo de 5% e alto de 25% de chance prevista. A forma exata do comando de
demonstração ainda será definida.
