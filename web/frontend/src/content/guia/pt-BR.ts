import type { GuiaContent } from './types'

export const ptBR: GuiaContent = {
  steps: {
    notice: {
      title: 'Um ambiente por vez',
      body: 'A VM comporta um único ambiente: enquanto houver um sendo criado, ativo ou sendo encerrado, a criação de outro é recusada, inclusive se ele for de outro usuário. Encerre o atual antes de criar o próximo.',
    },
    items: [
      {
        id: 'bootstrap',
        title: 'Confira o ambiente base (bootstrap)',
        body: [
          'Antes do primeiro uso, a VM precisa das dependências do testbed. A tela de Bootstrap verifica quatro itens: Docker, Mininet (`mn`), Containernet/OpenFlow e a imagem Docker do UE.',
          'Enquanto algum item estiver pendente, as telas do Pesquisador levam de volta ao Bootstrap. Lá você roda a instalação e acompanha o log dela.',
        ],
      },
      {
        id: 'criar',
        title: 'Crie um ambiente',
        body: [
          'Em "Criar ambiente", informe um nome (opcional), a quantidade de fatias e quantos UEs cada fatia terá, e clique em "Criar ambiente".',
          'Para não preencher tudo de novo: "Duplicar" (na lista ou no detalhe de um ambiente) copia a configuração de um ambiente anterior; um template é uma configuração com nome que você salva para reutilizar; um rascunho é o formulário salvo pela metade — ao sair da página com alterações, a ferramenta pergunta se você quer salvá-lo. Templates e rascunhos ficam em "Modelos".',
        ],
        links: [
          { to: '/pesquisador/novo', label: 'Criar ambiente' },
          { to: '/pesquisador/modelos', label: 'Modelos' },
        ],
      },
      {
        id: 'acompanhar',
        title: 'Acompanhe a subida',
        body: [
          'Depois de criar, você vai para o Monitoramento. O status passa de `starting` (sendo criado) para `running` (ativo) quando a subida termina com sucesso.',
          'Se a subida falhar ou passar de 15 minutos, a ferramenta derruba sozinha o que chegou a subir (o status passa por `stopping`) e o ambiente termina como `error`. O log da criação fica no fim da tela de Monitoramento e no detalhe do ambiente.',
        ],
      },
      {
        id: 'metricas',
        title: 'Leia as métricas',
        body: [
          'Com o ambiente ativo, o Monitoramento se atualiza a cada 5 segundos e os gráficos mostram os últimos 15 minutos. O seletor de fatia filtra os gráficos.',
          '"Visão geral": UEs conectados ao AMF e, por fatia, a quantidade de UEs, o ping (ok / sem resposta), o RTT, as sessões PDU no SMF, os pacotes/s que entram e saem da UPF, o AMBR agregado (↓/↑, em Mbps) e o índice de QoS.',
          '"Latência e perda": RTT, jitter e perda de pacotes de cada UE, e o tráfego na UPF. "Plano de controle": registros e autenticações no AMF, assinantes registrados por fatia, sessões PDU e QoS flows no SMF e na UPF. "Saúde dos NFs": se AMF, SMF, UPF e PCF estão no ar e quanta memória usam.',
        ],
        links: [{ to: '/pesquisador/monitoramento', label: 'Monitoramento' }],
      },
      {
        id: 'encerrar',
        title: 'Encerre o ambiente',
        body: [
          'Use "Parar" no Monitoramento ou em "Ambiente ativo". O status vai para `stopping` enquanto o ambiente é derrubado — o log do encerramento aparece no Monitoramento — e termina em `stopped`.',
          'Encerrar não apaga nada do histórico: o ambiente continua na lista, com a configuração usada e o log da criação.',
        ],
      },
      {
        id: 'rever',
        title: 'Reveja depois',
        body: [
          'Em "Todos os ambientes" você busca por ID ou nome e filtra por status, data de criação e número de fatias. O detalhe de cada ambiente mostra horários, duração, a configuração usada, o total de UEs e o log da criação, além de "Duplicar" e "Salvar como template".',
        ],
        links: [{ to: '/pesquisador/ambientes', label: 'Todos os ambientes' }],
      },
    ],
  },

  fields: {
    items: [
      {
        id: 'slices',
        title: 'Quantidade de fatias',
        body: [
          'De 1 a 8, padrão 2. Cada fatia é um S-NSSAI próprio (SST 1 e SD igual ao número da fatia em hexadecimal: `000001`, `000002`…) com um par SMF/UPF só dela e uma faixa de IPs própria para as sessões PDU: a fatia N usa `10.(44+N).0.0/16` — a fatia 1 fica com `10.45.0.0/16`.',
          'Cada fatia recebe um perfil de QoS. Os perfis se alternam: fatias ímpares usam o de índice 9 (tipo eMBB) e fatias pares o de índice 2 (tipo URLLC). Os valores de AMBR de cada fatia aparecem no Monitoramento. AMF, NRF, NSSF, PCF e o gNB são compartilhados por todas as fatias.',
          'Por que no máximo 8: acima de 9 o SD em hexadecimal passaria a ter letras (a–f), formato que não foi testado nos leitores de configuração do Open5GS e do UERANSIM.',
        ],
      },
      {
        id: 'ues',
        title: 'UEs por fatia',
        body: [
          'De 1 a 4 por fatia, padrão 1. Use "Mesma quantidade em todas" para um valor único ou "Definir por fatia" para concentrar carga em uma fatia e observar outra.',
          'O limite de 4 é metodológico, não técnico: cada UE é um container rodando o `nr-ue` do UERANSIM, que usa um único núcleo e o satura sob carga. Acima disso a VM satura e as medições passam a refletir disputa por CPU, não o comportamento da fatia. O aviso de total elevado de UEs é só um alerta e não impede a criação.',
          'O AMBR é agregado por fatia: todos os UEs de uma fatia passam pelo mesmo meter no switch, então competem entre si pelo limite dela (cenário intra-slice). Com um UE, ele se chama `ue<N>`; com mais, `ue<N>_1`, `ue<N>_2`…',
        ],
      },
      {
        id: 'nome',
        title: 'Nome do ambiente',
        body: [
          'Opcional, até 60 caracteres. É só um rótulo para achar o ambiente depois: não muda a configuração e não entra nos templates. Sem nome, o ambiente aparece como "Ambiente — N fatias".',
        ],
      },
    ],
    example: {
      id: 'exemplo',
      title: 'Exemplo: 2 fatias com 3 e 1 UEs',
      body: [
        'São 4 UEs no total. Os IPs na rede de acesso seguem uma numeração global e sequencial a partir de `10.34.0.200`, na ordem das fatias: `ue1_1` = `10.34.0.200`, `ue1_2` = `10.34.0.201`, `ue1_3` = `10.34.0.202` e `ue2` = `10.34.0.203`.',
        'Os três UEs da fatia 1 dividem o AMBR da fatia 1; o UE da fatia 2 tem o da fatia 2 só para ele.',
      ],
    },
    isolation: {
      id: 'isolamento',
      title: 'Isolamento',
      body: [
        'Os UEs ficam na rede de acesso (`10.34.0.0/24`) e o core em outra rede (`10.33.33.0/24`). O gNB está nas duas, mas faz a ponte na camada de aplicação, sem rotear pacotes entre elas; o Blackbox (que mede o ping) também está nas duas, e ambos rodam com `ip_forward=0`.',
        'No switch OpenFlow, cada UE só tem permissão para falar com o gNB (e responder às sondas do Blackbox); tráfego para as faixas das outras fatias é descartado, e o resto também. Dentro de cada UPF, regras de firewall descartam o que sai da sessão PDU de uma fatia em direção às outras fatias ou ao plano de gerência do core.',
        'Por isso um UE não pinga outro UE, nem de outra fatia nem da mesma: é proposital.',
      ],
    },
  },

  glossary: [
    { id: 'ue', term: 'UE', full: 'User Equipment', body: 'O dispositivo do usuário (o "celular"). Aqui cada UE é emulado pelo UERANSIM em um container da topologia Mininet.', where: 'Monitoramento: card "UEs conectados" e coluna "UEs" de cada fatia.' },
    { id: 'gnb', term: 'gNB', full: 'next generation NodeB', body: 'A estação rádio base do 5G. Neste testbed há um único gNB, emulado pelo UERANSIM e compartilhado pelas fatias; é a ponte entre a rede de acesso dos UEs e o core.' },
    { id: 'core', term: 'Core 5G', full: '5G Core (5GC)', body: 'O conjunto de funções de rede que autentica os UEs, cria as sessões e encaminha o tráfego. Aqui é o Open5GS, rodando em containers Docker.' },
    { id: 'amf', term: 'AMF', full: 'Access and Mobility Management Function', body: 'Recebe o registro e conduz a autenticação dos UEs. É única e compartilhada pelas fatias.', where: 'Monitoramento: aba "Plano de controle" e "Saúde dos NFs".' },
    { id: 'smf', term: 'SMF', full: 'Session Management Function', body: 'Cria e gerencia as sessões PDU e controla a UPF. Há uma SMF por fatia.', where: 'Monitoramento: coluna "Sessões" e gráficos de sessões e QoS flows.' },
    { id: 'upf', term: 'UPF', full: 'User Plane Function', body: 'Encaminha o tráfego de usuário das sessões PDU (túneis GTP-U vindos do gNB). Há uma UPF por fatia, cada uma com sua faixa de IPs.', where: 'Monitoramento: colunas "UPF entrada/saída (pkt/s)".' },
    { id: 'nrf', term: 'NRF', full: 'Network Repository Function', body: 'O "catálogo" do core: as funções de rede se registram nele e o consultam para descobrir umas às outras.' },
    { id: 'pcf', term: 'PCF', full: 'Policy Control Function', body: 'Fornece as regras de política, como as de QoS, aplicadas às sessões.', where: 'Monitoramento: aba "Saúde dos NFs".' },
    { id: 'nssf', term: 'NSSF', full: 'Network Slice Selection Function', body: 'Ajuda a escolher qual fatia (S-NSSAI) atende cada UE.' },
    { id: 's-nssai', term: 'S-NSSAI', full: 'Single Network Slice Selection Assistance Information', body: 'O identificador de uma fatia: SST (Slice/Service Type, o tipo de serviço) mais SD (Slice Differentiator, que distingue fatias do mesmo tipo). Aqui todas usam SST 1 e o SD é o número da fatia em hexadecimal.' },
    { id: 'slice', term: 'Fatia de rede', full: 'Network Slice', body: 'Uma rede lógica com recursos e regras próprios sobre a mesma infraestrutura física. Aqui cada fatia tem SMF/UPF, faixa de IPs, perfil de QoS e meter próprios.', where: 'Formulário de criação: "Quantidade de fatias".' },
    { id: 'pdu-session', term: 'Sessão PDU', full: 'PDU Session', body: 'A conexão de dados entre o UE e a rede externa, passando pela UPF da fatia. Ao estabelecê-la, o UE recebe um IP da faixa da fatia (no UERANSIM, na interface `uesimtun0`).', where: 'Monitoramento: coluna "Sessões".' },
    { id: 'qos-flow', term: 'QoS Flow', body: 'A menor granularidade de QoS dentro de uma sessão PDU: o tráfego de um QoS flow recebe o mesmo tratamento.', where: 'Monitoramento: gráficos "QoS flows" do SMF e da UPF.' },
    { id: '5qi', term: '5QI', full: '5G QoS Identifier', body: 'Número que indica as características de QoS de um fluxo (prioridade, atraso, perda tolerados). Aqui as fatias alternam entre os índices 9 e 2.', where: 'Monitoramento: coluna "QoS".' },
    { id: 'ambr', term: 'AMBR', full: 'Aggregate Maximum Bit Rate (Session-AMBR)', body: 'Taxa máxima agregada de uma sessão. Aqui o limite vale para a fatia inteira: os UEs dela compartilham o mesmo meter no switch.', where: 'Monitoramento: coluna "AMBR agregado ↓ / ↑ (Mbps)".' },
    { id: 'sdn', term: 'SDN', full: 'Software-Defined Networking', body: 'Rede em que o controle (quem decide o encaminhamento) fica em um controlador separado dos switches. Aqui o controlador é o ONOS.' },
    { id: 'openflow', term: 'OpenFlow', body: 'Protocolo que o controlador SDN usa para instalar regras nos switches. O switch do testbed fala OpenFlow 1.3.' },
    { id: 'ovs', term: 'OVS', full: 'Open vSwitch', body: 'Switch virtual que liga os UEs à rede de acesso e aplica as regras OpenFlow (flows e meters) instaladas pelo ONOS.' },
    { id: 'flow-meter', term: 'Flow e Meter', body: 'Flow é uma regra do switch (casa campos do pacote e diz o que fazer com ele). Meter é um limitador de taxa que os flows podem referenciar. Aqui os flows fazem o isolamento e cada fatia tem um meter com o seu AMBR.' },
    { id: 'onos', term: 'ONOS', full: 'Open Network Operating System', body: 'O controlador SDN do testbed. Roda em container, com os apps de OpenFlow e de encaminhamento ativados; os flows e meters das fatias são instalados pela API REST dele.' },
    { id: 'mininet', term: 'Mininet / Containernet', body: 'Mininet emula uma rede (switches, enlaces, hosts) em uma só máquina; o Containernet é a extensão que usa containers Docker como hosts. É assim que os UEs são ligados ao switch OVS.' },
    { id: 'ueransim', term: 'UERANSIM', body: 'Simulador de código aberto de UE e gNB 5G. Fornece o gNB e cada UE do testbed (processo `nr-ue`).' },
    { id: 'open5gs', term: 'Open5GS', body: 'Implementação de código aberto do core 5G (AMF, SMF, UPF, NRF, PCF, NSSF…), usada aqui em containers.' },
    { id: 'prometheus', term: 'Prometheus', body: 'Banco de séries temporais que coleta as métricas das funções de rede e do Blackbox a cada 10 segundos. É a fonte do Monitoramento.' },
    { id: 'blackbox', term: 'Blackbox exporter', body: 'Exportador do Prometheus que faz sondagens ativas. Aqui envia ICMP (ping) para o IP de cada UE na rede de acesso, de onde saem ping, RTT, jitter e perda.', where: 'Monitoramento: coluna "Ping" e aba "Latência e perda".' },
    { id: 'rtt', term: 'RTT', full: 'Round-Trip Time', body: 'Tempo de ida e volta de um pacote. Aqui é o tempo do ping do Blackbox até o UE, pela rede de acesso — não passa pela sessão PDU nem pela UPF.', where: 'Monitoramento: coluna "RTT (ms)" e gráfico de latência.' },
    { id: 'jitter', term: 'Jitter', body: 'Variação do atraso. Aqui é o desvio padrão do RTT de cada UE em janelas de 30 segundos.', where: 'Monitoramento: gráfico "Jitter do RTT".' },
    { id: 'packet-loss', term: 'Perda de pacotes', full: 'Packet loss', body: 'Proporção de pacotes que não chegam. Aqui é a porcentagem de sondas do Blackbox sem resposta em janelas de 30 segundos.', where: 'Monitoramento: gráfico "Perda de pacotes".' },
    { id: 'bootstrap', term: 'Bootstrap', body: 'Preparação inicial da VM: instala Docker, Mininet/Containernet e a imagem do UE. Só depois dele é possível criar ambientes.' },
  ],

  faq: [
    {
      id: 'segundo-ambiente',
      q: 'Por que não consigo criar um segundo ambiente?',
      a: ['A VM comporta um ambiente por vez. Enquanto houver um sendo criado, ativo ou sendo encerrado — seu ou de outro usuário — a criação de outro é recusada. Encerre o atual (ou espere ele terminar de subir ou de encerrar) e tente de novo.'],
    },
    {
      id: 'starting-error',
      q: 'O ambiente ficou em `starting` por muito tempo ou virou `error`. O que fazer?',
      a: [
        'Abra o log da criação (no Monitoramento ou no detalhe do ambiente) para ver onde parou. Se a subida passar de 15 minutos ou falhar, a ferramenta derruba o que chegou a subir e marca o ambiente como `error`. Se já houver um ambiente no ar fora da ferramenta (por exemplo, subido pela linha de comando), a subida é recusada e o ambiente vira `error` sem derrubar nada.',
        'Se o backend reiniciar no meio do caminho, ao voltar ele confere os ambientes presos em `starting` ou `stopping` pelos logs: o que já terminou recebe o status final, e o que ainda está dentro do prazo continua sendo acompanhado.',
        'Se sobrarem resíduos (containers, redes) de uma tentativa que falhou, use "Forçar limpeza" na barra superior.',
      ],
    },
    {
      id: 'metricas-vazias',
      q: 'Por que no início as métricas aparecem vazias ou instáveis?',
      a: [
        'O Monitoramento só busca métricas depois que o ambiente fica `running`. Elas vêm do Prometheus, que coleta a cada 10 segundos, e perda, jitter e pacotes/s são calculados sobre janelas de 30 segundos — então os primeiros pontos levam alguns ciclos para aparecer e se estabilizar. "—" significa que ainda não há valor.',
      ],
    },
    {
      id: 'duplicar-template-rascunho',
      q: 'O que muda entre "Duplicar", template e rascunho?',
      a: [
        '"Duplicar" copia a configuração de um ambiente que já existiu para um formulário novo (o nome vem com "(cópia)").',
        'Um template é uma configuração com nome e descrição que fica salva até você excluí-la; sirva-se dela em "Começar de um template" ou em Modelos > Usar. O nome do template não vira nome do ambiente.',
        'Um rascunho é o formulário salvo pela metade quando você sai da página. Continue em Modelos > Continuar; ele é apagado quando o ambiente é criado a partir dele.',
      ],
    },
    {
      id: 'limites',
      q: 'Por que o limite é de 4 UEs por fatia e 8 fatias?',
      a: [
        'UEs: cada UE é um processo `nr-ue` do UERANSIM que usa um único núcleo e o satura sob carga. Acima de 4 a VM satura e as medições passam a mostrar disputa por CPU, não o comportamento da fatia. É um limite metodológico, não do Open5GS.',
        'Fatias: o SD de cada fatia é o número dela em hexadecimal; acima de 9 surgiriam letras (a–f), formato não testado no Open5GS e no UERANSIM.',
      ],
    },
    {
      id: 'varias-linhas',
      q: 'Por que os gráficos de uma fatia têm várias linhas?',
      a: ['RTT, jitter e perda são medidos por UE. Quando a fatia tem mais de um UE, cada um vira uma linha: todas com a cor da fatia, mas com traços diferentes, e a legenda "Fatia N · UE k". Sessões e pacotes/s na UPF são por fatia e têm uma linha só.'],
    },
    {
      id: 'ambr-agregado',
      q: 'O que significa "AMBR agregado"?',
      a: ['Que o limite de banda é da fatia, não de cada UE: todos os UEs da fatia passam pelo mesmo meter no switch e competem pelo mesmo limite. Assim um UE que consome muito pode tirar banda dos outros da mesma fatia, sem afetar as outras fatias.'],
    },
    {
      id: 'historico',
      q: 'Encerrar o ambiente apaga o histórico?',
      a: ['Não. O ambiente continua em "Todos os ambientes" com a configuração usada, os horários e o log da criação, e pode ser duplicado ou salvo como template. Os arquivos de log também continuam na VM.'],
    },
    {
      id: 'idioma',
      q: 'Como troco o idioma?',
      a: ['Pelo seletor de idioma (ícone de idiomas) no rodapé da barra lateral. A escolha fica guardada no seu navegador; sem escolha salva, vale o idioma do navegador.'],
    },
    {
      id: 'logs',
      q: 'Onde ficam os logs de cada ambiente?',
      a: [
        'Na ferramenta: o log da criação fica no detalhe do ambiente e no Monitoramento; o log do encerramento aparece no Monitoramento enquanto o ambiente é encerrado.',
        'Na VM, dentro do repositório: `runs/<run_id>/up.log` e `runs/<run_id>/down.log`. A limpeza forçada grava em `logs/cleanup.log` e o bootstrap em `logs/bootstrap.log`.',
      ],
    },
    {
      id: 'ping-ue-ue',
      q: 'Por que um UE não consegue pingar outro UE?',
      a: ['É proposital. As regras do switch só deixam cada UE falar com o gNB (e responder às sondas do Blackbox), como no 5G real, em que dois UEs não se alcançam diretamente em nível IP. Tráfego para outras fatias também é descartado dentro das UPFs.'],
    },
    {
      id: 'rtt-mede',
      q: 'O RTT do Monitoramento mede o caminho pela fatia?',
      a: ['Não. É o ping do Blackbox até o IP do UE na rede de acesso, pelo switch, sem passar pela sessão PDU nem pela UPF. Ele mostra se o UE está alcançável e a latência desse trecho; o tráfego pela fatia aparece nos gráficos de pacotes/s da UPF.'],
    },
    {
      id: 'forcar-limpeza',
      q: 'Para que serve "Forçar limpeza"?',
      a: ['Roda o encerramento do testbed mesmo quando nenhum ambiente aparece como ativo, para remover containers, redes e resíduos do Mininet que tenham ficado no ar. Se houver um ambiente ativo, ele é encerrado pelo caminho normal. Não roda enquanto um ambiente está sendo criado ou encerrado.'],
    },
    {
      id: 'outros-usuarios',
      q: 'Outros usuários veem meus ambientes e templates?',
      a: ['Não: cada usuário vê só os próprios ambientes, templates e rascunhos. O limite de um ambiente por vez, porém, vale para a VM inteira.'],
    },
  ],
}
