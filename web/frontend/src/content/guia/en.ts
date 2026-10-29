import type { GuiaContent } from './types'

export const en: GuiaContent = {
  steps: {
    notice: {
      title: 'One environment at a time',
      body: 'The VM holds a single environment: while one is being created, active or being stopped, creating another is refused, even if it belongs to another user. Stop the current one before creating the next.',
    },
    items: [
      {
        id: 'bootstrap',
        title: 'Check the base environment (bootstrap)',
        body: [
          'Before first use, the VM needs the testbed dependencies. The Bootstrap screen checks four items: Docker, Mininet (`mn`), Containernet/OpenFlow and the UE Docker image.',
          'While any item is pending, the Researcher screens send you back to Bootstrap. There you run the installation and follow its log.',
        ],
      },
      {
        id: 'criar',
        title: 'Create an environment',
        body: [
          'In "Create environment", enter a name (optional), the number of slices and how many UEs each slice will have, then click "Create environment".',
          'To avoid filling everything in again: "Duplicate" (in the list or on an environment\'s details) copies the configuration of a previous environment; a template is a named configuration you save for reuse; a draft is a half-filled form — when you leave the page with changes, the tool asks whether you want to save it. Templates and drafts live in "Templates".',
        ],
        links: [
          { to: '/pesquisador/novo', label: 'Create environment' },
          { to: '/pesquisador/modelos', label: 'Templates' },
        ],
      },
      {
        id: 'acompanhar',
        title: 'Follow the bring-up',
        body: [
          'After creating, you go to Monitoring. The status moves from `starting` (being created) to `running` (active) when the bring-up finishes successfully.',
          'If the bring-up fails or takes longer than 15 minutes, the tool tears down whatever came up on its own (the status goes through `stopping`) and the environment ends as `error`. The creation log is at the bottom of the Monitoring screen and on the environment\'s details.',
        ],
      },
      {
        id: 'metricas',
        title: 'Read the metrics',
        body: [
          'With the environment active, Monitoring refreshes every 5 seconds and the charts show the last 15 minutes. The slice selector filters the charts.',
          '"Overview": UEs connected to the AMF and, per slice, the number of UEs, ping (ok / no response), RTT, PDU sessions on the SMF, packets/s in and out of the UPF, aggregate AMBR (↓/↑, in Mbps) and the QoS index.',
          '"Latency and loss": RTT, jitter and packet loss for each UE, and UPF traffic. "Control plane": registrations and authentications on the AMF, registered subscribers per slice, PDU sessions and QoS flows on the SMF and UPF. "NF health": whether AMF, SMF, UPF and PCF are up and how much memory they use.',
        ],
        links: [{ to: '/pesquisador/monitoramento', label: 'Monitoring' }],
      },
      {
        id: 'encerrar',
        title: 'Stop the environment',
        body: [
          'Use "Stop" in Monitoring or in "Active Environments". The status goes to `stopping` while the environment is torn down — the stop log shows up in Monitoring — and ends as `stopped`.',
          'Stopping deletes nothing from the history: the environment stays in the list, with the configuration used and the creation log.',
        ],
      },
      {
        id: 'rever',
        title: 'Review later',
        body: [
          'In "All environments" you search by ID or name and filter by status, creation date and number of slices. Each environment\'s details show times, duration, the configuration used, the total number of UEs and the creation log, plus "Duplicate" and "Save as template".',
        ],
        links: [{ to: '/pesquisador/ambientes', label: 'All environments' }],
      },
    ],
  },

  fields: {
    items: [
      {
        id: 'slices',
        title: 'Number of slices',
        body: [
          'From 1 to 8, default 2. Each slice is its own S-NSSAI (SST 1 and SD equal to the slice number in hexadecimal: `000001`, `000002`…) with its own SMF/UPF pair and its own IP range for PDU sessions: slice N uses `10.(44+N).0.0/16` — slice 1 gets `10.45.0.0/16`.',
          'Each slice gets a QoS profile. Profiles alternate: odd slices use index 9 (eMBB-like) and even slices index 2 (URLLC-like). Each slice\'s AMBR values are shown in Monitoring. The AMF, NRF, NSSF, PCF and the gNB are shared by all slices.',
          'Why at most 8: above 9 the hexadecimal SD would start containing letters (a–f), a format that was never tested in the Open5GS and UERANSIM configuration parsers.',
        ],
      },
      {
        id: 'ues',
        title: 'UEs per slice',
        body: [
          'From 1 to 4 per slice, default 1. Use "Same amount in all" for a single value or "Set per slice" to concentrate load on one slice and observe another.',
          'The limit of 4 is methodological, not technical: each UE is a container running UERANSIM\'s `nr-ue`, which uses a single core and saturates it under load. Beyond that the VM saturates and measurements start reflecting CPU contention, not slice behaviour. The high-total-UEs warning is just an alert and does not block creation.',
          'The AMBR is aggregate per slice: every UE in a slice goes through the same meter on the switch, so they compete with each other for that slice\'s limit (intra-slice scenario). With one UE it is named `ue<N>`; with more, `ue<N>_1`, `ue<N>_2`…',
        ],
      },
      {
        id: 'nome',
        title: 'Environment name',
        body: [
          'Optional, up to 60 characters. It is just a label to find the environment later: it does not change the configuration and is not stored in templates. Without a name, the environment shows up as "Environment — N slices".',
        ],
      },
    ],
    example: {
      id: 'exemplo',
      title: 'Example: 2 slices with 3 and 1 UEs',
      body: [
        'That is 4 UEs in total. Access-network IPs follow a global, sequential numbering starting at `10.34.0.200`, in slice order: `ue1_1` = `10.34.0.200`, `ue1_2` = `10.34.0.201`, `ue1_3` = `10.34.0.202` and `ue2` = `10.34.0.203`.',
        'The three UEs in slice 1 share slice 1\'s AMBR; the UE in slice 2 has slice 2\'s all to itself.',
      ],
    },
    isolation: {
      id: 'isolamento',
      title: 'Isolation',
      body: [
        'UEs live on the access network (`10.34.0.0/24`) and the core on another network (`10.33.33.0/24`). The gNB sits on both, but bridges them at the application layer, without routing packets between them; the Blackbox (which measures ping) is also on both, and both run with `ip_forward=0`.',
        'On the OpenFlow switch, each UE is only allowed to talk to the gNB (and answer the Blackbox probes); traffic to the other slices\' ranges is dropped, and so is everything else. Inside each UPF, firewall rules drop whatever leaves one slice\'s PDU session towards other slices or the core\'s management plane.',
        'That is why a UE cannot ping another UE, whether in another slice or the same one: it is by design.',
      ],
    },
  },

  glossary: [
    { id: 'ue', term: 'UE', full: 'User Equipment', body: 'The user\'s device (the "phone"). Here each UE is emulated by UERANSIM in a container of the Mininet topology.', where: 'Monitoring: "Connected UEs" card and each slice\'s "UEs" column.' },
    { id: 'gnb', term: 'gNB', full: 'next generation NodeB', body: 'The 5G base station. This testbed has a single gNB, emulated by UERANSIM and shared by the slices; it bridges the UEs\' access network and the core.' },
    { id: 'core', term: '5G Core', full: '5G Core (5GC)', body: 'The set of network functions that authenticates UEs, creates sessions and forwards traffic. Here it is Open5GS, running in Docker containers.' },
    { id: 'amf', term: 'AMF', full: 'Access and Mobility Management Function', body: 'Receives UE registrations and drives their authentication. There is a single AMF, shared by the slices.', where: 'Monitoring: "Control plane" and "NF health" tabs.' },
    { id: 'smf', term: 'SMF', full: 'Session Management Function', body: 'Creates and manages PDU sessions and controls the UPF. There is one SMF per slice.', where: 'Monitoring: "Sessions" column and the sessions and QoS flows charts.' },
    { id: 'upf', term: 'UPF', full: 'User Plane Function', body: 'Forwards the user traffic of PDU sessions (GTP-U tunnels from the gNB). There is one UPF per slice, each with its own IP range.', where: 'Monitoring: "UPF in/out (pkt/s)" columns.' },
    { id: 'nrf', term: 'NRF', full: 'Network Repository Function', body: 'The core\'s "catalogue": network functions register with it and query it to discover each other.' },
    { id: 'pcf', term: 'PCF', full: 'Policy Control Function', body: 'Provides the policy rules, such as QoS rules, applied to sessions.', where: 'Monitoring: "NF health" tab.' },
    { id: 'nssf', term: 'NSSF', full: 'Network Slice Selection Function', body: 'Helps choose which slice (S-NSSAI) serves each UE.' },
    { id: 's-nssai', term: 'S-NSSAI', full: 'Single Network Slice Selection Assistance Information', body: 'A slice\'s identifier: SST (Slice/Service Type, the kind of service) plus SD (Slice Differentiator, which tells apart slices of the same type). Here every slice uses SST 1 and the SD is the slice number in hexadecimal.' },
    { id: 'slice', term: 'Network slice', full: 'Network Slice', body: 'A logical network with its own resources and rules over the same physical infrastructure. Here each slice has its own SMF/UPF, IP range, QoS profile and meter.', where: 'Creation form: "Number of slices".' },
    { id: 'pdu-session', term: 'PDU session', full: 'PDU Session', body: 'The data connection between the UE and the external network, through the slice\'s UPF. When it is established the UE gets an IP from the slice\'s range (in UERANSIM, on the `uesimtun0` interface).', where: 'Monitoring: "Sessions" column.' },
    { id: 'qos-flow', term: 'QoS Flow', body: 'The finest QoS granularity inside a PDU session: traffic in a QoS flow gets the same treatment.', where: 'Monitoring: SMF and UPF "QoS flows" charts.' },
    { id: '5qi', term: '5QI', full: '5G QoS Identifier', body: 'A number that sets the QoS characteristics of a flow (priority, tolerated delay and loss). Here slices alternate between indexes 9 and 2.', where: 'Monitoring: "QoS" column.' },
    { id: 'ambr', term: 'AMBR', full: 'Aggregate Maximum Bit Rate (Session-AMBR)', body: 'The maximum aggregate rate of a session. Here the limit applies to the whole slice: its UEs share the same meter on the switch.', where: 'Monitoring: "Aggregate AMBR ↓ / ↑ (Mbps)" column.' },
    { id: 'sdn', term: 'SDN', full: 'Software-Defined Networking', body: 'Networking where control (who decides forwarding) lives in a controller separate from the switches. Here the controller is ONOS.' },
    { id: 'openflow', term: 'OpenFlow', body: 'The protocol an SDN controller uses to install rules on switches. The testbed switch speaks OpenFlow 1.3.' },
    { id: 'ovs', term: 'OVS', full: 'Open vSwitch', body: 'The virtual switch that connects the UEs to the access network and applies the OpenFlow rules (flows and meters) installed by ONOS.' },
    { id: 'flow-meter', term: 'Flow and Meter', body: 'A flow is a switch rule (it matches packet fields and says what to do with the packet). A meter is a rate limiter that flows can reference. Here flows enforce isolation and each slice has a meter with its AMBR.' },
    { id: 'onos', term: 'ONOS', full: 'Open Network Operating System', body: 'The testbed\'s SDN controller. It runs in a container with the OpenFlow and forwarding apps enabled; the slices\' flows and meters are installed through its REST API.' },
    { id: 'mininet', term: 'Mininet / Containernet', body: 'Mininet emulates a network (switches, links, hosts) on a single machine; Containernet is the extension that uses Docker containers as hosts. That is how the UEs are attached to the OVS switch.' },
    { id: 'ueransim', term: 'UERANSIM', body: 'An open-source 5G UE and gNB simulator. It provides the testbed\'s gNB and every UE (the `nr-ue` process).' },
    { id: 'open5gs', term: 'Open5GS', body: 'An open-source implementation of the 5G core (AMF, SMF, UPF, NRF, PCF, NSSF…), used here in containers.' },
    { id: 'prometheus', term: 'Prometheus', body: 'A time-series database that scrapes metrics from the network functions and the Blackbox every 10 seconds. It is the source for Monitoring.' },
    { id: 'blackbox', term: 'Blackbox exporter', body: 'A Prometheus exporter that runs active probes. Here it sends ICMP (ping) to each UE\'s IP on the access network, which yields ping, RTT, jitter and loss.', where: 'Monitoring: "Ping" column and "Latency and loss" tab.' },
    { id: 'rtt', term: 'RTT', full: 'Round-Trip Time', body: 'The time for a packet to go and come back. Here it is the Blackbox ping time to the UE over the access network — it does not go through the PDU session or the UPF.', where: 'Monitoring: "RTT (ms)" column and latency chart.' },
    { id: 'jitter', term: 'Jitter', body: 'Delay variation. Here it is the standard deviation of each UE\'s RTT over 30-second windows.', where: 'Monitoring: "RTT jitter" chart.' },
    { id: 'packet-loss', term: 'Packet loss', full: 'Packet loss', body: 'The share of packets that do not arrive. Here it is the percentage of Blackbox probes without a reply over 30-second windows.', where: 'Monitoring: "Packet loss" chart.' },
    { id: 'bootstrap', term: 'Bootstrap', body: 'The VM\'s initial setup: installs Docker, Mininet/Containernet and the UE image. Environments can only be created after it.' },
  ],

  faq: [
    {
      id: 'segundo-ambiente',
      q: 'Why can\'t I create a second environment?',
      a: ['The VM holds one environment at a time. While one is being created, active or being stopped — yours or another user\'s — creating another is refused. Stop the current one (or wait for it to finish coming up or stopping) and try again.'],
    },
    {
      id: 'starting-error',
      q: 'The environment stayed in `starting` for a long time or turned into `error`. What now?',
      a: [
        'Open the creation log (in Monitoring or on the environment\'s details) to see where it stopped. If the bring-up takes longer than 15 minutes or fails, the tool tears down what came up and marks the environment as `error`. If an environment is already up outside the tool (for example, started from the command line), the bring-up is refused and the environment becomes `error` without tearing anything down.',
        'If the backend restarts midway, on its way back it checks environments stuck in `starting` or `stopping` against their logs: those that already finished get their final status, and those still within the time limit keep being followed.',
        'If leftovers (containers, networks) from a failed attempt remain, use "Force cleanup" in the top bar.',
      ],
    },
    {
      id: 'metricas-vazias',
      q: 'Why are the metrics empty or unstable at first?',
      a: [
        'Monitoring only fetches metrics once the environment is `running`. They come from Prometheus, which scrapes every 10 seconds, and loss, jitter and packets/s are computed over 30-second windows — so the first points take a few cycles to show up and settle. "—" means there is no value yet.',
      ],
    },
    {
      id: 'duplicar-template-rascunho',
      q: 'What is the difference between "Duplicate", a template and a draft?',
      a: [
        '"Duplicate" copies the configuration of an environment that already existed into a new form (the name comes with "(copy)").',
        'A template is a configuration with a name and description that stays saved until you delete it; use it from "Start from a template" or Templates > Use. The template name does not become the environment name.',
        'A draft is the half-filled form saved when you leave the page. Continue it from Templates > Continue; it is deleted once an environment is created from it.',
      ],
    },
    {
      id: 'limites',
      q: 'Why the limits of 4 UEs per slice and 8 slices?',
      a: [
        'UEs: each UE is a UERANSIM `nr-ue` process that uses a single core and saturates it under load. Beyond 4 the VM saturates and measurements start showing CPU contention, not slice behaviour. It is a methodological limit, not an Open5GS one.',
        'Slices: each slice\'s SD is its number in hexadecimal; above 9 letters (a–f) would appear, a format not tested in Open5GS and UERANSIM.',
      ],
    },
    {
      id: 'varias-linhas',
      q: 'Why do a slice\'s charts have several lines?',
      a: ['RTT, jitter and loss are measured per UE. When the slice has more than one UE, each becomes a line: all with the slice\'s colour, but with different dashes, and the legend "Slice N · UE k". Sessions and UPF packets/s are per slice and have a single line.'],
    },
    {
      id: 'ambr-agregado',
      q: 'What does "aggregate AMBR" mean?',
      a: ['That the bandwidth limit belongs to the slice, not to each UE: every UE in the slice goes through the same meter on the switch and competes for the same limit. So a UE that consumes a lot can take bandwidth from others in the same slice, without affecting other slices.'],
    },
    {
      id: 'historico',
      q: 'Does stopping the environment delete its history?',
      a: ['No. The environment stays in "All environments" with the configuration used, the times and the creation log, and can be duplicated or saved as a template. The log files also remain on the VM.'],
    },
    {
      id: 'idioma',
      q: 'How do I change the language?',
      a: ['With the language selector (languages icon) at the bottom of the sidebar. The choice is stored in your browser; with no saved choice, the browser language applies.'],
    },
    {
      id: 'logs',
      q: 'Where are each environment\'s logs?',
      a: [
        'In the tool: the creation log is on the environment\'s details and in Monitoring; the stop log shows up in Monitoring while the environment is being stopped.',
        'On the VM, inside the repository: `runs/<run_id>/up.log` and `runs/<run_id>/down.log`. Force cleanup writes to `logs/cleanup.log` and bootstrap to `logs/bootstrap.log`.',
      ],
    },
    {
      id: 'ping-ue-ue',
      q: 'Why can\'t a UE ping another UE?',
      a: ['By design. The switch rules only let each UE talk to the gNB (and answer the Blackbox probes), as in real 5G, where two UEs do not reach each other directly at the IP level. Traffic to other slices is also dropped inside the UPFs.'],
    },
    {
      id: 'rtt-mede',
      q: 'Does the RTT in Monitoring measure the path through the slice?',
      a: ['No. It is the Blackbox ping to the UE\'s IP on the access network, through the switch, without going through the PDU session or the UPF. It shows whether the UE is reachable and the latency of that segment; traffic through the slice shows up in the UPF packets/s charts.'],
    },
    {
      id: 'forcar-limpeza',
      q: 'What is "Force cleanup" for?',
      a: ['It runs the testbed teardown even when no environment shows as active, to remove containers, networks and Mininet leftovers that stayed up. If an environment is active, it is stopped the normal way. It does not run while an environment is being created or stopped.'],
    },
    {
      id: 'outros-usuarios',
      q: 'Can other users see my environments and templates?',
      a: ['No: each user only sees their own environments, templates and drafts. The one-environment-at-a-time limit, however, applies to the whole VM.'],
    },
  ],
}
