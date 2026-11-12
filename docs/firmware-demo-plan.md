# Plano de demonstração do ML na maquete

Este documento registra uma proposta para a apresentação à banca. **O modelo
já foi integrado ao ESP32; o comando de avanço artificial de janelas ainda
não foi implementado.** Os pesos exportados atualmente são anteriores à curva
horária revisada; treinar novamente em Python não atualiza a placa.

## O que existe hoje

- O firmware busca a topologia na API, mantém a última topologia válida na
  flash e envia telemetria. O controle imediato dos sensores funciona na
  placa sem esperar a API.
- O firmware conta novas ativações por zona, mantém as últimas janelas,
  calcula a previsão localmente e informa no monitor serial a chance e o PWM
  de repouso por zona e LED. A comunicação entre placas distingue o evento
  único de ativação das mensagens repetidas de estado ativo.
- `Serial` via USB é usada para mensagens a 115200 baud. Uma segunda UART liga
  as duas placas e transmite estados de movimento e a nova ativação.
- O Web e a API possuem uma página/rota `/ml/demo` da experiência antiga de
  anomalias em janelas de cinco minutos. Essa rota consulta resultados; não
  envia comandos ao firmware e não representa o novo modelo de dimerização.

## Demonstração proposta

1. Demonstrar uma ativação física do sensor elevando imediatamente a
   luminária ao nível máximo. Essa prioridade vale também com a API desligada.
2. Em um modo de demonstração **explicitamente identificado**, permitir que
   um comando local pelo monitor serial USB avance um relógio simulado em
   passos de 15 minutos. Essa parte ainda precisaria ser implementada. Hoje,
   a demonstração da previsão depende de janelas reais completas ou de
   registros prévios capturados no monitor serial.
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

## Trabalho restante para o avanço artificial

- Fazer as duas placas avançarem a mesma janela simulada sem contar mensagens
  repetidas como novos eventos. A contagem normal por zona já foi integrada;
  falta definir o protocolo e a separação do modo de demonstração.
- Manter o cálculo normal em tempo real separado do modo de demonstração. No
  funcionamento normal, as janelas passam a cada 15 minutos reais; comandos
  de demonstração não devem alterar o relógio ou o histórico operacional.
- Verificar com a maquete o funcionamento das duas placas quando a API estiver
  indisponível. Sem horário válido ou histórico suficiente, o repouso fica no
  PWM padrão 20 e os sensores continuam operando.

Os níveis de repouso configurados são PWM 10/20/40, com limite baixo de 5% e
alto de 30% de chance prevista. A forma exata do comando de demonstração
ainda será definida.
