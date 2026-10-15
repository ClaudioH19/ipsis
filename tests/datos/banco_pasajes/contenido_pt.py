"""Conteúdo do banco de passagens em português: mesmos documentos, fatos e cifras do banco em espanhol.

Perguntas formais (``q``) e informais (``p``, como se escreve num chat). Consumido por ``generar_fuentes.py``.
"""
from __future__ import annotations

IDIOMA = "pt"
UNIDADES = ("Ciências", "Engenharia")


def _doc(archivo, titulo, intro, tema, items, hechos, propios):
    return dict(archivo=archivo, titulo=titulo, intro=intro, tema=tema, items=items, hechos=hechos, propios=propios)


GENERALES = [
    "Esta seção («{H}») descreve as regras aplicáveis e complementa o disposto nas demais seções do "
    "documento. Quando houver diferença entre a regra geral e a regra particular, prevalece a regra particular. "
    "As dúvidas de interpretação são resolvidas consultando a unidade responsável antes de iniciar qualquer "
    "trâmite.",
    "A unidade responsável mantém um registro das solicitações recebidas e de seu resultado. Esse registro é "
    "revisado a cada semestre para detectar atrasos, trâmites repetidos e erros frequentes nos formulários. Os "
    "achados são informados à direção e incorporados na próxima versão deste documento.",
    "Os formulários estão no portal interno e devem ser preenchidos por completo. Um formulário incompleto, com "
    "rasuras ou sem a assinatura correspondente é devolvido sem tramitar, e o prazo é contado a partir da data "
    "em que a versão corrigida é recebida. Recomenda-se guardar uma cópia de cada documento apresentado.",
    "Quem precisar de orientação pode ir ao balcão de atendimento no horário habitual ou escrever para o e-mail "
    "da unidade. As consultas são respondidas por ordem de chegada e, salvo casos urgentes, não são atendidas "
    "por telefone. As respostas por e-mail não substituem a resolução formal do trâmite.",
    "As situações não previstas neste documento são analisadas caso a caso. A unidade responsável pode pedir "
    "antecedentes adicionais, e a decisão é comunicada por escrito junto com seus fundamentos. Se a pessoa "
    "interessada não concordar, pode pedir uma revisão à direção dentro do período fixado pelo regulamento geral.",
    "Toda a informação entregue é tratada com reserva e usada apenas para o trâmite em andamento. Os dados "
    "pessoais são conservados pelo tempo que a norma de arquivo exige e depois eliminados de forma segura. As "
    "cópias impressas ficam no arquivo central e não podem ser retiradas sem autorização.",
    "As mudanças nesta seção são publicadas com pelo menos um mês de antecedência e comunicadas por e-mail "
    "institucional. Enquanto uma nova versão não entrar em vigor, aplica-se a anterior. As solicitações "
    "apresentadas antes da mudança são resolvidas com as regras vigentes na data de apresentação.",
    "O descumprimento reiterado destas regras pode gerar uma observação no registro da pessoa. As observações "
    "são eliminadas após um ano sem novas faltas. A unidade responsável avisa com antecedência antes de "
    "registrar qualquer observação e permite apresentar defesa.",
    "Quando o trâmite exige a intervenção de mais de uma unidade, a unidade que o recebe coordena as gestões e "
    "mantém a pessoa interessada informada. Não é necessário apresentar os mesmos documentos mais de uma vez, "
    "desde que se indique o número da solicitação original.",
    "Os prazos que caem em dia não útil passam para o dia útil seguinte. Os períodos de recesso institucional, "
    "como as férias de inverno e as de fim de ano, não contam nos prazos enquanto os escritórios estiverem "
    "fechados.",
    "Para facilitar a revisão, pede-se anexar os documentos em formato PDF, com boa resolução e em um único "
    "arquivo por solicitação. Os arquivos ilegíveis ou que superem o tamanho permitido pelo portal são devolvidos "
    "para correção.",
    "As capacitações sobre este procedimento são realizadas no início de cada semestre e ficam gravadas na "
    "intranet. A presença é voluntária, mas é especialmente recomendada para quem tramita pela primeira vez ou "
    "teve solicitações rejeitadas.",
]

DOCS = []

# 1. Reembolsos por tipo de pessoal --------------------------------------------------------------------
DOCS.append(_doc(
    "regulamento_reembolsos.md", "Regulamento de reembolso de despesas",
    "Este regulamento estabelece como são solicitados, aprovados e pagos os reembolsos de despesas feitas em "
    "nome da instituição. As regras dependem do tipo de vínculo da pessoa, por isso cada seção trata de um grupo "
    "diferente. Antes de gastar, convém confirmar a qual grupo se pertence.",
    "os reembolsos de despesas",
    [
        ("Servidores efetivos", "servidores efetivos", dict(a=30, b="pela chefia direta", c=10, d="350.000", m="transferência para a conta de pagamento de salários")),
        ("Servidores contratados", "servidores contratados", dict(a=20, b="pela chefia direta", c=12, d="250.000", m="transferência para a conta de pagamento de salários")),
        ("Prestadores de serviço", "prestadores de serviço", dict(a=15, b="pela direção administrativa", c=25, d="150.000", m="transferência para a conta bancária informada no contrato")),
        ("Estagiários", "estagiários", dict(a=7, b="pelo tutor do estágio", c=15, d="60.000", m="cheque administrativo retirado na tesouraria")),
        ("Professores horistas", "professores horistas", dict(a=45, b="pela direção do departamento", c=20, d="200.000", m="transferência para a conta bancária registrada no departamento")),
        ("Convidados externos", "convidados externos", dict(a=10, b="pela unidade que fez o convite", c=30, d="500.000", m="cheque nominal emitido pela tesouraria")),
    ],
    [
        ("temprano", "Para {S}, o pedido de reembolso deve ser apresentado em até {a} dias úteis a partir da data da despesa.",
         "Para {S}, o pedido de reembolso deve ser apresentado em até {a} dias úteis",
         "Quantos dias úteis existem para apresentar o pedido de reembolso para {S}?",
         "até quantos dias depois da compra dá pra pedir o reembolso sendo {S}?"),
        ("temprano", "Para {S}, o pedido é aprovado {b}.",
         "Para {S}, o pedido é aprovado {b}",
         "Quem aprova o pedido de reembolso para {S}?",
         "quem tem q aprovar meu reembolso sendo {S}?"),
        ("tardio", "Para {S}, o reembolso é pago em no máximo {c} dias úteis após a aprovação.",
         "Para {S}, o reembolso é pago em no máximo {c} dias úteis",
         "Em quantos dias úteis é pago o reembolso para {S}?",
         "quanto tempo demora pra cair o dinheiro do reembolso para {S}?"),
        ("tardio", "Para {S}, o limite por prestação de contas é de {d} pesos.",
         "Para {S}, o limite por prestação de contas é de {d} pesos",
         "Qual é o limite por prestação de contas para {S}?",
         "qual o máximo q posso prestar de uma vez como {S}?"),
        ("tardio", "Para {S}, o pagamento é feito por {m}.",
         "Para {S}, o pagamento é feito por {m}",
         "Como é pago o reembolso para {S}?",
         "de q jeito me pagam o reembolso sendo {S}?"),
    ],
    [
        "Um reembolso só procede quando a despesa foi feita no cumprimento de uma função da instituição e está "
        "respaldada por recibo ou nota fiscal em nome da instituição. Despesas pessoais, gorjetas e multas não são "
        "reembolsadas em nenhum caso, ainda que tenham ocorrido durante uma missão.",
        "A prestação de contas é montada com o formulário de reembolso, os comprovantes originais e uma breve "
        "explicação do motivo de cada despesa. Os comprovantes são colados em folhas tamanho carta, ordenados por "
        "data, e entregues ou digitalizados conforme indique o portal.",
        "Se o valor prestado superar o limite vigente, a diferença deve ser tramitada como uma solicitação "
        "separada, com autorização prévia da direção administrativa. Dividir uma despesa em várias prestações para "
        "evitar o limite é considerado uma falta.",
    ],
))

# 2. Garantia de equipamentos -----------------------------------------------------------------------------
DOCS.append(_doc(
    "garantia_equipamentos.md", "Política de garantia de equipamentos institucionais",
    "Esta política explica o que a garantia cobre nos equipamentos que a instituição entrega a seu pessoal e "
    "como se solicita o serviço. Cada tipo de equipamento tem condições próprias, descritas em uma seção "
    "diferente. Os prazos contam a partir da data de entrega registrada na ata.",
    "a garantia dos equipamentos",
    [
        ("Notebooks", "notebooks", dict(n=24, c="falhas de placa, tela e bateria", x="derramamento de líquidos e golpes", s="na oficina do prédio central", d=5)),
        ("Impressoras", "impressoras", dict(n=12, c="falhas do mecanismo de tração do papel", x="o uso de tinta ou toner não original", s="na oficina do prédio de oficinas", d=10)),
        ("Projetores", "projetores", dict(n=18, c="falhas da placa e da óptica", x="o desgaste da lâmpada", s="no depósito de audiovisual", d=7)),
        ("Tablets", "tablets", dict(n=12, c="falhas da tela sensível ao toque e do carregamento", x="telas quebradas por quedas", s="na oficina do prédio central", d=3)),
        ("Monitores", "monitores", dict(n=36, c="pixels defeituosos e falhas da fonte interna", x="riscos na tela", s="no depósito de audiovisual", d=8)),
        ("Roteadores", "roteadores", dict(n=48, c="falhas da fonte de alimentação e das portas", x="danos por descargas elétricas", s="no escritório de redes", d=2)),
    ],
    [
        ("temprano", "Para {S}, a garantia dura {n} meses a partir da data de entrega.",
         "Para {S}, a garantia dura {n} meses",
         "Quantos meses dura a garantia para {S}?",
         "por quanto tempo {S} ficam na garantia?"),
        ("temprano", "Para {S}, a garantia cobre {c}.",
         "Para {S}, a garantia cobre {c}",
         "O que a garantia cobre para {S}?",
         "q problemas consertam de graça em {S}?"),
        ("tardio", "Para {S}, a garantia não cobre {x}.",
         "Para {S}, a garantia não cobre {x}",
         "O que a garantia não cobre para {S}?",
         "em q casos perco a garantia de {S}?"),
        ("tardio", "Para {S}, o serviço técnico atende {s}.",
         "Para {S}, o serviço técnico atende {s}",
         "Onde atende o serviço técnico para {S}?",
         "pra onde levo {S} pra consertar?"),
        ("tardio", "Para {S}, o equipamento de reposição é entregue em até {d} dias úteis.",
         "Para {S}, o equipamento de reposição é entregue em até {d} dias úteis",
         "Em quantos dias úteis é entregue o equipamento de reposição para {S}?",
         "quanto tempo demoram pra me dar outro enquanto consertam {S}?"),
    ],
    [
        "Para fazer valer a garantia, a pessoa deve informar a falha pelo portal de suporte, indicando o número de "
        "patrimônio do equipamento. O serviço técnico registra a entrada e entrega um comprovante com a data e o "
        "diagnóstico inicial.",
        "O pessoal não deve abrir nem consertar os equipamentos por conta própria. A manipulação interna, a troca "
        "de peças ou a instalação de software não autorizado anulam a garantia e podem obrigar a repor o "
        "equipamento a cargo do centro de custos da unidade.",
        "Ao terminar a garantia, o equipamento passa ao regime de manutenção, cobrado do centro de custos da "
        "unidade conforme o catálogo de serviços técnicos vigente. A unidade pode pedir a baixa do equipamento se "
        "o custo do conserto superar a metade de seu valor.",
    ],
))

# 3. Licenças e permissões -----------------------------------------------------------------------------------
DOCS.append(_doc(
    "regulamento_licencas.md", "Regulamento de licenças e permissões do pessoal",
    "Este regulamento regula as licenças remuneradas a que o pessoal tem direito e os trâmites para solicitá-las. "
    "Cada tipo de licença tem sua própria seção, com as condições que a distinguem. As licenças não solicitadas "
    "dentro do prazo podem ser perdidas.",
    "as licenças do pessoal",
    [
        ("Licença-casamento", "a licença-casamento", dict(a=5, p=30, doc="a certidão de casamento", q="pela diretoria de pessoas", d="não é descontado")),
        ("Licença pelo nascimento de um filho", "a licença pelo nascimento de um filho", dict(a=5, p=15, doc="a certidão de nascimento", q="pela chefia direta", d="não é descontado")),
        ("Licença por falecimento de um familiar", "a licença por falecimento de um familiar", dict(a=7, p=2, doc="a certidão de óbito", q="pela chefia direta", d="não é descontado")),
        ("Licença para estudos", "a licença para estudos", dict(a=10, p=60, doc="o comprovante de matrícula", q="pela diretoria de pessoas", d="é descontado proporcionalmente")),
        ("Licença por doença de um filho menor", "a licença por doença de um filho menor", dict(a=10, p=3, doc="o atestado médico do menor", q="pela chefia direta", d="não é descontado")),
        ("Licença para trâmites pessoais", "a licença para trâmites pessoais", dict(a=3, p=5, doc="um comprovante da diligência realizada", q="pela chefia direta", d="é descontado das férias")),
    ],
    [
        ("temprano", "Para {S}, são concedidos {a} dias de licença por ano.",
         "Para {S}, são concedidos {a} dias de licença",
         "Quantos dias de licença são concedidos para {S}?",
         "quantos dias eu ganho em {S}?"),
        ("temprano", "Para {S}, o pedido deve ser apresentado com {p} dias de antecedência.",
         "Para {S}, o pedido deve ser apresentado com {p} dias de antecedência",
         "Com quantos dias de antecedência se solicita {S}?",
         "com quanta antecedência tenho q pedir {S}?"),
        ("tardio", "Para {S}, exige-se como comprovante {doc}.",
         "Para {S}, exige-se como comprovante {doc}",
         "Que documento se exige como comprovante para {S}?",
         "q papel tenho q levar pra {S}?"),
        ("tardio", "Para {S}, a licença é autorizada {q}.",
         "Para {S}, a licença é autorizada {q}",
         "Quem autoriza {S}?",
         "quem tem q dar o ok pra {S}?"),
        ("tardio", "Para {S}, o tempo de licença {d}.",
         "Para {S}, o tempo de licença {d}",
         "O tempo de licença é descontado para {S}?",
         "descontam do meu salário por {S}?"),
    ],
    [
        "As licenças são solicitadas pelo portal de pessoas, anexando o formulário assinado pela chefia. A "
        "diretoria de pessoas confirma o recebimento por e-mail e registra a licença no sistema de ponto.",
        "Os dias de licença são contados em dias corridos, salvo indicação em contrário na seção. Uma licença que "
        "começa em dia não útil conta a partir do dia útil seguinte, e não podem ser acumuladas licenças de tipos "
        "diferentes no mesmo período sem autorização expressa.",
        "A licença não utilizada dentro do ano civil não se acumula nem é compensada em dinheiro. Quem mudar de "
        "unidade conserva os dias pendentes, e a nova chefia recebe um relatório com o saldo no momento da "
        "transferência.",
    ],
))

# 4. Compras por faixa de valor ------------------------------------------------------------------------------
DOCS.append(_doc(
    "manual_compras.md", "Manual de compras e contratações",
    "Este manual define como se compram bens e serviços conforme o valor. Quanto maior o valor, mais "
    "cotações e mais níveis de aprovação. Cada modalidade de compra é explicada em uma seção com as exigências "
    "que lhe correspondem.",
    "as compras",
    [
        ("Compras menores", "compras menores", dict(m=10, b="pela chefia da unidade", k=1, p=3, doc="o recibo ou a nota fiscal")),
        ("Compras diretas", "compras diretas", dict(m=100, b="pela direção administrativa", k=2, p=7, doc="a ordem de compra assinada")),
        ("Cotação formal", "compras por cotação formal", dict(m=500, b="pela direção administrativa", k=3, p=15, doc="o quadro comparativo de cotações")),
        ("Licitação privada", "licitações privadas", dict(m=1000, b="pelo comitê de compras", k=3, p=30, doc="a ata de avaliação de propostas")),
        ("Licitação pública", "licitações públicas", dict(m=5000, b="pelo comitê de compras", k=5, p=60, doc="o edital de licitação aprovado")),
        ("Compras de emergência", "compras de emergência", dict(m=300, b="pela reitoria", k=1, p=2, doc="o relatório de justificativa da emergência")),
    ],
    [
        ("temprano", "Para {S}, o valor máximo é de {m} UF.",
         "Para {S}, o valor máximo é de {m} UF",
         "Qual é o valor máximo para {S}?",
         "até quantas UF posso gastar em {S}?"),
        ("temprano", "Para {S}, a compra é aprovada {b}.",
         "Para {S}, a compra é aprovada {b}",
         "Quem aprova a compra para {S}?",
         "quem assina as {S}?"),
        ("tardio", "Para {S}, exigem-se no mínimo {k} cotações.",
         "Para {S}, exigem-se no mínimo {k} cotações",
         "Quantas cotações se exigem no mínimo para {S}?",
         "quantas cotações preciso juntar para {S}?"),
        ("tardio", "Para {S}, o prazo máximo do processo é de {p} dias úteis.",
         "Para {S}, o prazo máximo do processo é de {p} dias úteis",
         "Qual é o prazo máximo do processo para {S}?",
         "quanto demora o trâmite todo para {S}?"),
        ("tardio", "Para {S}, o documento de encerramento é {doc}.",
         "Para {S}, o documento de encerramento é {doc}",
         "Qual é o documento de encerramento para {S}?",
         "q papel fecha o trâmite de {S}?"),
    ],
    [
        "Antes de iniciar qualquer compra, a unidade deve verificar se há orçamento disponível em seu centro de "
        "custos. A direção administrativa pode rejeitar solicitações sem disponibilidade, mesmo que cumpram o "
        "restante das exigências deste manual.",
        "Os fornecedores devem estar inscritos no cadastro institucional e não ter dívidas tributárias nem "
        "sanções vigentes. A inscrição é renovada a cada ano apresentando os antecedentes legais e tributários "
        "atualizados.",
        "É proibido dividir uma compra em várias para ficar abaixo de um limite. A direção administrativa revisa "
        "mensalmente as compras repetidas ao mesmo fornecedor e pode reclassificá-las na modalidade que "
        "corresponda ao valor total.",
    ],
))

# 5. Laboratórios ------------------------------------------------------------------------------------------------
DOCS.append(_doc(
    "protocolo_laboratorios.md", "Protocolo de uso de laboratórios",
    "Este protocolo fixa as condições de segurança e uso dos laboratórios da instituição. Cada laboratório tem "
    "riscos diferentes, por isso suas regras são descritas em seções separadas. Todo usuário deve ler a seção do "
    "laboratório antes de sua primeira visita.",
    "os laboratórios",
    [
        ("Laboratório de química", "o laboratório de química", dict(a=20, e="jaleco, óculos de proteção e luvas de nitrila", r="a técnica do laboratório de química", h="8h30 às 18h00", p=48)),
        ("Laboratório de biologia", "o laboratório de biologia", dict(a=24, e="jaleco, máscara e luvas de látex", r="o encarregado de biossegurança", h="8h00 às 17h30", p=72)),
        ("Laboratório de física", "o laboratório de física", dict(a=30, e="calçado fechado e óculos de segurança", r="o monitor do laboratório de física", h="9h00 às 19h00", p=24)),
        ("Laboratório de eletrônica", "o laboratório de eletrônica", dict(a=18, e="pulseira antiestática e óculos de segurança", r="o técnico eletrônico", h="9h00 às 20h00", p=24)),
        ("Laboratório de informática", "o laboratório de informática", dict(a=40, e="nenhum, mas é proibido entrar com alimentos", r="o administrador de redes", h="8h00 às 22h00", p=12)),
        ("Laboratório de materiais", "o laboratório de materiais", dict(a=15, e="capacete, calçado de segurança e protetores auriculares", r="o engenheiro de manutenção", h="8h30 às 17h00", p=96)),
    ],
    [
        ("temprano", "Para {S}, a lotação máxima é de {a} pessoas.",
         "Para {S}, a lotação máxima é de {a} pessoas",
         "Qual é a lotação máxima para {S}?",
         "quantas pessoas podem ficar ao mesmo tempo para {S}?"),
        ("temprano", "Para {S}, o horário de atendimento é das {h}.",
         "Para {S}, o horário de atendimento é das {h}",
         "Qual é o horário de atendimento para {S}?",
         "q horas abre e fecha {S}?"),
        ("tardio", "Para {S}, o equipamento de proteção obrigatório inclui {e}.",
         "Para {S}, o equipamento de proteção obrigatório inclui {e}",
         "Que equipamento de proteção é obrigatório para {S}?",
         "o q tenho q vestir pra usar {S}?"),
        ("tardio", "Para {S}, o responsável pela segurança é {r}.",
         "Para {S}, o responsável pela segurança é {r}",
         "Quem é o responsável pela segurança para {S}?",
         "com quem falo se rolar algum problema em {S}?"),
        ("tardio", "Para {S}, a reserva deve ser feita com {p} horas de antecedência.",
         "Para {S}, a reserva deve ser feita com {p} horas de antecedência",
         "Com quantas horas de antecedência se reserva {S}?",
         "com quanto tempo antes tenho q reservar {S}?"),
    ],
    [
        "Ninguém pode trabalhar sozinho em um laboratório fora do horário de atendimento. As exceções exigem "
        "autorização escrita do responsável e aviso prévio ao segurança, que registra a hora de entrada e de "
        "saída.",
        "Os resíduos são separados conforme as instruções de cada laboratório e depositados nos recipientes "
        "rotulados. Nunca se despejam substâncias no ralo sem autorização. Os resíduos perigosos são recolhidos "
        "por uma empresa externa autorizada uma vez por mês.",
        "Todo acidente, ainda que pareça menor, é informado imediatamente ao responsável e registrado no livro de "
        "incidentes do laboratório. Os kits de primeiros socorros e os chuveiros de emergência são revisados todo "
        "mês e seu estado é anotado em uma lista de verificação.",
    ],
))

# 6. Viagens -----------------------------------------------------------------------------------------------------
DOCS.append(_doc(
    "politica_viagens.md", "Política de viagens e diárias",
    "Esta política estabelece como se solicitam e financiam as viagens a trabalho. As condições mudam conforme o "
    "tipo de viagem, e cada uma é detalhada em sua própria seção. Nenhuma viagem pode ser iniciada sem a "
    "autorização correspondente.",
    "as viagens",
    [
        ("Viagens nacionais de ônibus", "viagens nacionais de ônibus", dict(a=5, v="45.000", b="pela chefia direta", s="seguro de acidentes pessoais", r=10)),
        ("Viagens nacionais de avião", "viagens nacionais de avião", dict(a=10, v="65.000", b="pela direção administrativa", s="seguro de acidentes pessoais e de bagagem", r=10)),
        ("Viagens internacionais", "viagens internacionais", dict(a=30, v="180 dólares", b="pela vice-reitoria", s="seguro de assistência em viagem com cobertura médica", r=15)),
        ("Congressos e seminários", "congressos e seminários", dict(a=45, v="120 dólares", b="pela direção de pesquisa", s="seguro de assistência em viagem com cobertura médica", r=20)),
        ("Missões de serviço de um dia", "missões de serviço de um dia", dict(a=3, v="25.000", b="pela chefia direta", s="seguro de acidentes pessoais", r=5)),
        ("Trabalho de campo", "trabalho de campo", dict(a=15, v="55.000", b="pela direção do departamento", s="seguro de acidentes pessoais com cobertura rural", r=7)),
    ],
    [
        ("temprano", "Para {S}, o pedido deve ser apresentado com {a} dias úteis de antecedência.",
         "Para {S}, o pedido deve ser apresentado com {a} dias úteis de antecedência",
         "Com quantos dias úteis de antecedência se solicita {S}?",
         "com quanto tempo antes tenho q pedir {S}?"),
        ("temprano", "Para {S}, a diária é de {v} pesos ou seu equivalente.",
         "Para {S}, a diária é de {v}",
         "De quanto é a diária para {S}?",
         "quanto me dão por dia em {S}?"),
        ("tardio", "Para {S}, a viagem é autorizada {b}.",
         "Para {S}, a viagem é autorizada {b}",
         "Quem autoriza {S}?",
         "a quem peço o ok pra {S}?"),
        ("tardio", "Para {S}, a instituição contrata {s}.",
         "Para {S}, a instituição contrata {s}",
         "Que seguro a instituição contrata para {S}?",
         "q seguro me fazem pra {S}?"),
        ("tardio", "Para {S}, a prestação de contas da viagem deve ser entregue em até {r} dias úteis após o retorno.",
         "Para {S}, a prestação de contas da viagem deve ser entregue em até {r} dias úteis",
         "Em quantos dias úteis deve ser entregue a prestação de contas para {S}?",
         "quantos dias tenho pra prestar contas depois de {S}?"),
    ],
    [
        "As passagens são compradas pela instituição por meio da agência contratada. Não se reembolsam passagens "
        "compradas pela própria pessoa, salvo se a agência não puder atender a solicitação e a direção "
        "administrativa autorizar por escrito.",
        "As diárias cobrem alimentação, transporte local e hospedagem básica. Quando a instituição paga a "
        "hospedagem ou as refeições diretamente, a diária é reduzida na proporção fixada pela tabela anexa de "
        "descontos.",
        "Quem viaja deve deixar informados seu roteiro e um contato de emergência na unidade. As mudanças de "
        "itinerário são avisadas imediatamente à chefia, e os gastos decorrentes de mudanças não autorizadas ficam "
        "a cargo da pessoa.",
    ],
))

GEM = {
    "biblioteca": {
        "archivos": {"Ciências": "regulamento_biblioteca_ciencias.md", "Engenharia": "regulamento_biblioteca_engenharia.md"},
        "titulo": "Regulamento da biblioteca da Faculdade de {U}",
        "intro": "Este regulamento regula o uso da biblioteca da Faculdade de {U}. Cada serviço é descrito em sua própria seção, com as condições vigentes para estudantes e pessoal da faculdade.",
        "tema": "os serviços da biblioteca",
        "secciones": [
            ("Empréstimo de livros", "o empréstimo de livros",
             [("temprano", "Na Faculdade de {U}, o empréstimo de livros dura {a} dias corridos.", "Na Faculdade de {U}, o empréstimo de livros dura {a} dias corridos",
               "Quantos dias dura o empréstimo de livros na Faculdade de {U}?", "por quantos dias posso levar um livro da biblioteca de {U}?"),
              ("tardio", "Na Faculdade de {U}, cada estudante pode renovar um livro até {b} vezes.", "Na Faculdade de {U}, cada estudante pode renovar um livro até {b} vezes",
               "Quantas vezes se pode renovar um livro na Faculdade de {U}?", "quantas renovações deixam fazer de um livro na biblioteca de {U}?")]),
            ("Empréstimo de notebooks", "o empréstimo de notebooks",
             [("temprano", "Na Faculdade de {U}, o empréstimo de notebooks é concedido por {a} horas.", "Na Faculdade de {U}, o empréstimo de notebooks é concedido por {a} horas",
               "Por quantas horas se empresta um notebook na Faculdade de {U}?", "quantas horas posso usar um notebook da biblioteca de {U}?"),
              ("tardio", "Na Faculdade de {U}, o depósito em garantia por um notebook é de {b} pesos.", "Na Faculdade de {U}, o depósito em garantia por um notebook é de {b} pesos",
               "De quanto é o depósito em garantia por um notebook na Faculdade de {U}?", "quanto dinheiro deixo de garantia por um notebook na biblioteca de {U}?")]),
            ("Salas de estudo", "as salas de estudo",
             [("temprano", "Na Faculdade de {U}, as salas de estudo são reservadas em blocos de {a} horas.", "Na Faculdade de {U}, as salas de estudo são reservadas em blocos de {a} horas",
               "De quantas horas são os blocos de reserva das salas de estudo na Faculdade de {U}?", "por quantas horas posso reservar uma sala de estudo na biblioteca de {U}?"),
              ("tardio", "Na Faculdade de {U}, a reserva de uma sala se perde após {b} minutos de atraso.", "Na Faculdade de {U}, a reserva de uma sala se perde após {b} minutos de atraso",
               "Quantos minutos de atraso fazem perder a reserva de uma sala na Faculdade de {U}?", "quanto posso atrasar antes de tirarem minha sala na biblioteca de {U}?")]),
            ("Multas por atraso", "as multas por atraso",
             [("temprano", "Na Faculdade de {U}, a multa por atraso é de {a} pesos por dia e por livro.", "Na Faculdade de {U}, a multa por atraso é de {a} pesos por dia e por livro",
               "De quanto é a multa diária por atraso na Faculdade de {U}?", "quanto cobram por dia de atraso com um livro na biblioteca de {U}?"),
              ("tardio", "Na Faculdade de {U}, a multa acumulada é suspensa ao chegar a {b} pesos.", "Na Faculdade de {U}, a multa acumulada é suspensa ao chegar a {b} pesos",
               "Em que valor é suspensa a multa acumulada na Faculdade de {U}?", "até quanto pode subir a multa total na biblioteca de {U}?")]),
            ("Reserva de material", "a reserva de material",
             [("temprano", "Na Faculdade de {U}, o material reservado é guardado por {a} dias úteis.", "Na Faculdade de {U}, o material reservado é guardado por {a} dias úteis",
               "Quantos dias úteis é guardado o material reservado na Faculdade de {U}?", "quanto tempo guardam um livro reservado pra mim na biblioteca de {U}?"),
              ("tardio", "Na Faculdade de {U}, cada pessoa pode manter até {b} reservas ativas.", "Na Faculdade de {U}, cada pessoa pode manter até {b} reservas ativas",
               "Quantas reservas ativas são permitidas por pessoa na Faculdade de {U}?", "quantas reservas posso ter ao mesmo tempo na biblioteca de {U}?")]),
        ],
        "valores": {
            "Ciências": [dict(a=14, b=2), dict(a=3, b="50.000"), dict(a=2, b=15), dict(a="300", b="6.000"), dict(a=5, b=3)],
            "Engenharia": [dict(a=21, b=3), dict(a=4, b="80.000"), dict(a=3, b=10), dict(a="500", b="10.000"), dict(a=7, b=5)],
        },
    },
    "titulacion": {
        "archivos": {"Ciências": "regulamento_titulacao_ciencias.md", "Engenharia": "regulamento_titulacao_engenharia.md"},
        "titulo": "Regulamento de titulação da Faculdade de {U}",
        "intro": "Este regulamento descreve as etapas do processo de titulação na Faculdade de {U}. Cada etapa tem sua própria seção, com prazos, responsáveis e requisitos.",
        "tema": "o processo de titulação",
        "secciones": [
            ("Inscrição do tema", "a inscrição do tema",
             [("temprano", "Na Faculdade de {U}, o tema de titulação é inscrito perante {a}.", "Na Faculdade de {U}, o tema de titulação é inscrito perante {a}",
               "Perante quem se inscreve o tema de titulação na Faculdade de {U}?", "aonde vou pra inscrever meu tema de TCC na faculdade de {U}?"),
              ("tardio", "Na Faculdade de {U}, o tema inscrito tem vigência de {b} meses.", "Na Faculdade de {U}, o tema inscrito tem vigência de {b} meses",
               "Quantos meses de vigência tem o tema inscrito na Faculdade de {U}?", "quanto tempo dura inscrito meu tema de TCC na faculdade de {U}?")]),
            ("Banca examinadora", "a banca examinadora",
             [("temprano", "Na Faculdade de {U}, a banca examinadora é integrada por {a} professores.", "Na Faculdade de {U}, a banca examinadora é integrada por {a} professores",
               "Quantos professores integram a banca examinadora na Faculdade de {U}?", "quantos professores tem na minha banca na faculdade de {U}?"),
              ("tardio", "Na Faculdade de {U}, a banca é constituída em até {b} dias úteis após a inscrição.", "Na Faculdade de {U}, a banca é constituída em até {b} dias úteis",
               "Em quantos dias úteis é constituída a banca na Faculdade de {U}?", "quanto demoram pra montar a banca na faculdade de {U}?")]),
            ("Defesa", "a defesa",
             [("temprano", "Na Faculdade de {U}, a defesa é feita perante a banca com no máximo {a} minutos de exposição.", "Na Faculdade de {U}, a defesa é feita perante a banca com no máximo {a} minutos de exposição",
               "Quantos minutos de exposição tem a defesa na Faculdade de {U}?", "quanto tempo tenho pra apresentar minha defesa na faculdade de {U}?"),
              ("tardio", "Na Faculdade de {U}, a nota mínima para aprovar a defesa é {b}.", "Na Faculdade de {U}, a nota mínima para aprovar a defesa é {b}",
               "Qual é a nota mínima para aprovar a defesa na Faculdade de {U}?", "com q nota passo na defesa na faculdade de {U}?")]),
            ("Entrega final", "a entrega final",
             [("temprano", "Na Faculdade de {U}, a versão final do trabalho é entregue em até {a} dias úteis após a defesa.", "Na Faculdade de {U}, a versão final do trabalho é entregue em até {a} dias úteis",
               "Em quantos dias úteis é entregue a versão final depois da defesa na Faculdade de {U}?", "quantos dias tenho pra entregar a versão final na faculdade de {U}?"),
              ("tardio", "Na Faculdade de {U}, o trabalho final é entregue em {b} exemplares impressos.", "Na Faculdade de {U}, o trabalho final é entregue em {b} exemplares impressos",
               "Quantos exemplares impressos do trabalho final são entregues na Faculdade de {U}?", "quantas cópias impressas tenho q deixar na faculdade de {U}?")]),
            ("Certificado de titulação", "o certificado de titulação",
             [("temprano", "Na Faculdade de {U}, o certificado de titulação é emitido em {a} dias úteis.", "Na Faculdade de {U}, o certificado de titulação é emitido em {a} dias úteis",
               "Em quantos dias úteis é emitido o certificado de titulação na Faculdade de {U}?", "quanto demoram pra me dar o certificado de titulação na faculdade de {U}?"),
              ("tardio", "Na Faculdade de {U}, o certificado de titulação custa {b} pesos.", "Na Faculdade de {U}, o certificado de titulação custa {b} pesos",
               "Quanto custa o certificado de titulação na Faculdade de {U}?", "quanto tenho q pagar pelo certificado de titulação na faculdade de {U}?")]),
        ],
        "valores": {
            "Ciências": [dict(a="a coordenação de titulação", b=12), dict(a=3, b=20), dict(a=30, b="5,0"), dict(a=15, b=4), dict(a=10, b="8.000")],
            "Engenharia": [dict(a="a chefia do curso", b=18), dict(a=5, b=30), dict(a=40, b="5,5"), dict(a=20, b=2), dict(a=15, b="12.000")],
        },
    },
}

TRAMPAS = [
    ("regulamento_reembolsos.md", "Qual é o limite por prestação de contas para voluntários?"),
    ("regulamento_reembolsos.md", "Qual é a diária para estagiários?"),
    ("regulamento_reembolsos.md", "Quantos dias úteis têm os estagiários para recorrer da rejeição de um reembolso?"),
    ("garantia_equipamentos.md", "Quantos meses dura a garantia para celulares?"),
    ("garantia_equipamentos.md", "O que a garantia cobre para scanners?"),
    ("garantia_equipamentos.md", "Onde atende o serviço técnico para servidores?"),
    ("regulamento_licencas.md", "Quantos dias de licença são concedidos para a licença por mudança de residência?"),
    ("regulamento_licencas.md", "Quem autoriza a licença por mudança de casa?"),
    ("manual_compras.md", "Qual é o valor máximo para compras de aluguel de imóveis?"),
    ("manual_compras.md", "Quantas cotações se exigem no mínimo para compras internacionais?"),
    ("protocolo_laboratorios.md", "Qual é a lotação máxima do laboratório de astronomia?"),
    ("protocolo_laboratorios.md", "Que equipamento de proteção é obrigatório no laboratório de geologia?"),
    ("politica_viagens.md", "De quanto é a diária para viagens nacionais de trem?"),
    ("politica_viagens.md", "Com quantos dias úteis de antecedência se solicita uma viagem de navio?"),
    ("regulamento_biblioteca_ciencias.md", "Quantos dias dura o empréstimo de livros na Faculdade de Medicina?"),
]
