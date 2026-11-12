# Versão do ML apresentada na maquete

Este é o ponto de partida para ler o projeto e descrevê-lo no TCC. Os números
de circulação usados no treinamento são **sintéticos**, não medições de uma rua
ou da maquete.

## O que está no firmware

- O modelo geral é uma regressão de Poisson treinada com `scikit-learn` nos
  primeiros **28 dias** do cenário `persistent_activity`, com a curva horária
  revisada. Seus 27 pesos estão em `config/firmware_model.json` e no arquivo
  gerado `SmartLighting.Firmware/src/Control/ActivityModelWeights.h`.
- A cada janela completa de 15 minutos, o ESP32 usa a hora local, o indicador
  de fim de semana e as ativações dos últimos 30 minutos de cada zona para
  estimar a chance de ao menos uma ativação nos próximos 15 minutos. O ID da
  zona não entra na fórmula. Sem horário válido ou histórico suficiente, o
  repouso é PWM 20.
- A política em `config/dimming_policy.json` escolhe PWM 10 se a chance for
  menor que 5%, PWM 20 de 5% até menos de 30%, e PWM 40 a partir de 30%.
  Um LED compartilhado recebe o maior pedido de suas zonas. Movimento
  detectado continua tendo prioridade e leva o alvo a PWM 255, com o fade do
  firmware. A previsão roda no ESP32, sem depender da API naquele momento.

## Evidência disponível e seus limites

Na comparação com a curva revisada, cada candidato foi treinado com **21 dias**
e avaliado nos **7 dias seguintes** de cada cenário. O candidato treinado em
`persistent_activity` obteve Brier 0,10352 em `development` e 0,11345 em
`persistent_activity`. A regra simples baseada em zona e hora obteve 0,10443
e 0,11423, respectivamente, quando treinada e avaliada no próprio cenário.
Menor Brier indica melhor previsão probabilística; as diferenças são pequenas
e se referem somente aos dados simulados. A comparação detalhada está na seção
"Novo treino com a curva horária revisada" de [model-selection.md](model-selection.md).

**Essas métricas são da seleção com 21 dias, não uma avaliação independente dos
pesos finais reajustados com 28 dias e gravados no ESP32.** O `holdout` foi
avaliado com uma versão anterior e depois deixou de ser um teste independente
para a configuração atual. Os números antigos de PWM médio não demonstram
economia de energia da versão atual. O teste da maquete verifica a execução do
controle e a reação física dos LEDs, não a precisão em circulação real.

## Onde encontrar os detalhes

- [Hipóteses dos cenários](scenario-assumptions.md): origem e limitações dos
  dados simulados.
- [Escolha dos pesos](model-selection.md): contém a comparação atual na seção
  da curva revisada e também uma tabela histórica, identificada no início.
- [Política de brilho](dimming-policy.md): limites e prioridade do sensor.
- [Topologia da maquete](maquette-topology.md): vínculos entre zonas e LEDs.

Os relatórios [baseline-evaluation.md](baseline-evaluation.md),
[dimming-validation.md](dimming-validation.md),
[luminaire-validation.md](luminaire-validation.md) e
[holdout-evaluation.md](holdout-evaluation.md) registram etapas anteriores.
São material opcional para acompanhar as decisões do desenvolvimento; suas
tabelas não descrevem o desempenho da configuração final.
