# Política provisória de brilho de repouso

O modelo treinado estima a quantidade média de ativações de uma zona na
próxima janela de 15 minutos e a chance de haver ao menos uma ativação.
A política em `config/dimming_policy.json` usa **essa chance**, não a contagem
diretamente, para escolher o PWM de repouso:

| Chance prevista | Nível | PWM de 8 bits |
| --- | --- | ---: |
| Menor que 10% | Baixo | 10/255 |
| De 10% até menos de 25% | Padrão | 20/255 |
| A partir de 25% | Alto | 50/255 |

Os limites de 10% e 25% são **provisórios** e não vieram do treino, do banco
da API nem de uma medição da maquete. O valor padrão 20/255 já foi considerado
adequado nos testes visuais iniciais. Os valores 10 e 50 aguardam teste físico.
Esses números representam a razão do PWM; não medem diretamente a claridade
percebida nem o consumo elétrico.

`load_policy()` valida o JSON, inclusive a ordem crescente dos PWM e dos
limites. `level_for_probability()` decide baixo, padrão ou alto;
`pwm_for_probability()` devolve o número correspondente. Uma probabilidade
inválida é rejeitada. O módulo não consulta a API nem altera o firmware.

Exemplo: se `PoissonModel.predict()` devolver chance 0,18, a política escolhe
`standard`, PWM 20/255. Se devolver 0,28, escolhe `high`, PWM 50/255.
Mudar esses valores no JSON não altera os pesos do modelo, pois o modelo
aprende a prever ativações, não valores de PWM. Quando a política chegar ao
ESP32, será necessário publicar a configuração atualizada na placa.

Este arquivo descreve apenas o **repouso**. No firmware atual, o sensor ativo
continua tendo alvo 255/255 e a subida e descida mantêm o fade testado na
maquete. Na futura integração, LEDs compartilhados por zonas deverão usar o
maior nível de repouso solicitado. Se faltar horário válido para a previsão,
o padrão proposto é o nível intermediário de 20/255.

Antes de fixar os limites, compararemos várias combinações somente nos dias
de validação e observaremos quantas janelas ativas ficariam em nível baixo e
quanto tempo o repouso ficaria alto. Depois, o teste físico deve confirmar se
10/20/50 são visualmente adequados. Ainda não há medição de economia, conforto
ou segurança para atribuir uma vantagem operacional a esta política.
