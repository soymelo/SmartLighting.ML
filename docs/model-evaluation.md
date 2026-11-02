# Treinamento de regressão

Este experimento usa **somente dados sintéticos**, com cenários e sementes
declarados. Não mede fluxo de uma rua real. Os eventos começaram em 2026-08-01
e cobrem 42 dias por cenário; `holdout` segue reservado. Cada exemplo representa
uma zona e um intervalo de 15 minutos. Em uma janela sem eventos, a resposta
correta de contagem é zero.

## Como a comparação foi feita

1. Nos dias 1–21, ajustamos quatro modelos candidatos. Todos recebem zona,
   hora e indicação de fim de semana. A diferença é o histórico de ativações:
   últimos 15, 30, 60 ou os três intervalos juntos.
2. Nos dias 22–28, medimos o Brier e escolhemos o menor. Brier mede a qualidade
   da chance estimada de haver ao menos uma ativação; quanto menor, melhor.
3. Ajustamos a alternativa escolhida outra vez, agora com os dias 1–28.
4. Nos dias 29–42, comparamos uma vez esse modelo com `zona_hora` e `zero`.
   São os mesmos 8.064 exemplos finais usados na avaliação anterior.

São 12.072 exemplos para o primeiro ajuste, 4.032 para validação e 16.104 para
o ajuste final. Os 14 dias finais têm 8.064 exemplos. A divisão por tempo evita
que uma resposta futura entre no treinamento. As contagens de 30 e 60 minutos
são calculadas somente com janelas já encerradas.

A regressão de Poisson estima uma **média de ativações** na próxima janela.
Exemplo: média 0,4 significa uma expectativa estatística de 0,4 ativação, não
que ocorrerá uma fração de passagem. A chance derivada de haver pelo menos uma
ativação é `1 - exp(-média)`. Esta conversão assume que uma distribuição de
Poisson descreve a contagem; episódios reais podem violar essa suposição.
O treinamento usa `scikit-learn==1.9.1` (`PoissonRegressor`) e uma penalidade
pequena para evitar pesos extremos. A versão inicial deste experimento usava
um otimizador Adam escrito no projeto; o ajuste foi substituído pela
biblioteca, mantendo as entradas, a divisão dos dias e a fórmula de previsão.
Os pesos salvos ainda não foram executados no ESP32. O JSON registra a versão
da biblioteca e a ordem exata das entradas, necessárias para reproduzir a
previsão em C++.

Exemplo com o modelo ajustado para `persistent_activity`: na zona simulada
Z02, às 21h de um dia útil, zero ativações nos 30 minutos anteriores produzem
média prevista de 0,208 ativação e chance de 18,8% para a próxima janela.
Três ativações anteriores produzem média de 0,283 e chance de 24,7%. Assim,
o histórico recente muda a previsão; a hora e a zona também continuam
importantes. Essa passagem pelo corte ilustrativo de 20% ainda não muda o LED,
pois a regra de brilho não foi definida nem integrada ao firmware.

## Escolha do histórico na validação

| Cenário | 15 min | 30 min | 60 min | 15+30+60 min | Escolhido |
| --- | ---: | ---: | ---: | ---: | --- |
| Desenvolvimento, Brier | 0,10975 | **0,10965** | 0,10967 | 0,10966 | 30 min |
| Atividade persistente, Brier | 0,10910 | **0,10888** | 0,10903 | 0,10908 | 30 min |

A diferença é pequena. Esses números indicam que 30 minutos foi a melhor das
quatro opções **nessa validação sintética**, não que seja um intervalo ótimo
para qualquer rua. Como 60 minutos não ajudou aqui, o modelo escolhido precisa
guardar apenas duas janelas anteriores. A preparação ainda usa uma hora para
permitir comparar todas as alternativas de forma igual.

## Resultado nos 14 dias finais

| Cenário | Regra | MAE ↓ | RMSE ↓ | Brier ↓ | Janelas ativas antecipadas | Alertas corretos | Janelas alertadas |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | `zero` | 0,138 | 0,407 | 0,125 | 0,0% | — | 0,0% |
| Desenvolvimento | `zona_hora` | 0,224 | 0,370 | 0,103 | 34,4% | 26,8% | 16,0% |
| Desenvolvimento | `ml_poisson` | 0,226 | 0,370 | **0,102** | 34,2% | 26,8% | 15,9% |
| Atividade persistente | `zero` | 0,157 | 0,457 | 0,137 | 0,0% | — | 0,0% |
| Atividade persistente | `zona_hora` | **0,250** | 0,413 | 0,110 | **47,3%** | 25,8% | 25,0% |
| Atividade persistente | `ml_poisson` | 0,252 | **0,411** | **0,109** | 41,2% | **29,1%** | 19,3% |

MAE e RMSE medem erro na quantidade de ativações. Brier mede erro da
probabilidade de alguma ativação. “Janelas ativas antecipadas” é recall:
das janelas que tiveram movimento, quantas receberam chance de pelo menos
20%. “Alertas corretos” é precisão: dos alertas, quantos tiveram movimento.
“Janelas alertadas” indica frequência de chance estimada acima de 20%, **não**
uma ordem enviada ao LED. Esse corte de 20% é ilustrativo e não define brilho.

No cenário persistente, houve **1.101 janelas ativas**. A regra `zona_hora`
alertou em 2.016 janelas: 521 alertas corretos, 1.495 alertas que terminaram
sem movimento e 580 janelas ativas sem alerta. O ML alertou em **1.559**:
**454** corretos, **1.105** que terminaram vazios e **647** janelas ativas sem
alerta. Portanto, reduziu 390 alertas vazios, mas deixou de antecipar 67
janelas ativas adicionais. Os sensores ainda reagiriam imediatamente quando
houvesse movimento, independentemente da previsão.

## O que podemos concluir

O histórico de 30 minutos acrescentou um sinal pequeno nos cenários simulados.
O ML teve Brier e RMSE ligeiramente menores no teste persistente, mas MAE e
recall piores que `zona_hora`. **Ainda não há evidência suficiente para afirmar
que o ML produz melhor iluminação ou economia de energia.** É preciso medir
o brilho na maquete, definir quanto custa um período preventivamente claro
e quanto custa uma atividade não antecipada. Só então poderemos transformar
probabilidade em níveis de repouso e escolher limites. Um alerta que termina
vazio não significa que a probabilidade estava “errada”: eventos incertos
podem deixar de ocorrer. Na avaliação, porém, ele conta como alerta sem
atividade e teria custo de energia se elevasse o brilho.

Os arquivos reproduzíveis estão em `models/development/` e
`models/persistent_activity/`. `report.json` contém os valores completos da
validação e do teste; `model.json` contém os pesos ajustados. Os diretórios
`models/` e `data/` são ignorados pelo Git porque podem ser recriados pelos
comandos do README.

## Comparação com o otimizador manual anterior

Repetimos os dois treinos com os **mesmos CSVs**, períodos e candidatos. Os
dois métodos escolheram 30 minutos de histórico. No teste final, o Brier de
`development` foi 0,102214396 com Adam manual e 0,102214397 com
scikit-learn. No cenário persistente, foi 0,109297637 nos dois métodos quando
arredondado a nove casas decimais. Recall, precisão e proporção de alertas
ficaram iguais nas duas execuções. As pequenas diferenças numéricas decorrem
do algoritmo de ajuste dos pesos; elas não mudam a conclusão do experimento.
Os números antigos foram preservados localmente em `models/manual/`, pasta
ignorada pelo Git. O código do otimizador manual continua recuperável no
commit anterior.
