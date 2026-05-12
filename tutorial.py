#!/usr/bin/env python3
"""
FAIR-5G Tutorial Mode — Demonstração Educacional
=================================================
Serve uma interface web em localhost:5055.
Nenhum comando real é executado — tudo é simulado.

Uso:
    python3 tutorial.py
    python3 tutorial.py --no-browser
"""
import sys, threading, time, webbrowser
from pathlib import Path

try:
    from flask import Flask, Response
    FLASK_OK = True
except ImportError:
    FLASK_OK = False

PORT      = 5055
REPO_ROOT = Path(__file__).resolve().parent

# ─────────────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>FAIR-5G · Tutorial</title>
<style>
:root{
  --bg:#0d1117;--surf:#161b22;--surf2:#21262d;
  --bord:rgba(255,255,255,.08);--text:#e6edf3;--muted:#7d8590;--dim:#484f58;
  --cyan:#2dd4bf;--amber:#f59e0b;--blue:#60a5fa;--purple:#a78bfa;
  --green:#2ea043;--red:#f85149;--orange:#e5742d;
  --mono:'JetBrains Mono','Fira Code','Cascadia Code',monospace;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:var(--mono);
     font-size:13px;height:100vh;display:flex;flex-direction:column;overflow:hidden;}

/* ── header ── */
header{padding:9px 20px;border-bottom:1px solid var(--bord);background:var(--surf);
       display:flex;align-items:center;gap:10px;flex-shrink:0;}
.logo{font-size:15px;font-weight:700;color:var(--cyan);letter-spacing:1px;}
.hbadge{font-size:10px;padding:2px 9px;border-radius:4px;transition:all .3s;
        background:rgba(45,212,191,.1);color:var(--cyan);border:1px solid rgba(45,212,191,.25);}
.hbadge.run{background:rgba(96,165,250,.1);color:var(--blue);border-color:rgba(96,165,250,.25);}
.hbadge.done{background:rgba(46,160,67,.1);color:#3fb950;border-color:rgba(46,160,67,.25);}
.speed-wrap{margin-left:auto;display:flex;align-items:center;gap:5px;}
.slbl{font-size:10px;color:var(--muted);}
.spd{font-size:11px;padding:3px 9px;border-radius:4px;cursor:pointer;
     border:1px solid var(--bord);background:transparent;color:var(--muted);transition:all .15s;}
.spd.on{background:var(--surf2);color:var(--text);border-color:var(--blue);}
.spd:hover:not(.on){border-color:var(--muted);}
#btn-start{margin-left:8px;padding:4px 14px;border-radius:5px;cursor:pointer;
           font-size:11px;font-weight:600;background:var(--cyan);color:#0d1117;
           border:none;transition:opacity .15s;font-family:var(--mono);}
#btn-start:hover{opacity:.85;}
#btn-start:disabled{opacity:.35;cursor:default;}
.htime{font-size:10px;color:var(--dim);margin-left:4px;min-width:38px;}

/* ── main layout ── */
.layout{display:flex;flex:1;overflow:hidden;}

/* ── left: steps + terminal ── */
.left{width:375px;flex-shrink:0;display:flex;flex-direction:column;border-right:1px solid var(--bord);}

.steps-box{padding:12px 14px;border-bottom:1px solid var(--bord);}
.steps-hdr{font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:9px;}
.srow{display:flex;align-items:flex-start;gap:9px;padding:7px 0;
      border-bottom:1px solid rgba(255,255,255,.04);}
.srow:last-child{border-bottom:none;}
.sico{width:20px;height:20px;border-radius:50%;border:1.5px solid var(--dim);flex-shrink:0;
      margin-top:1px;display:flex;align-items:center;justify-content:center;font-size:10px;transition:all .3s;}
.sico.run{border-color:var(--blue);color:var(--blue);background:rgba(96,165,250,.12);
          animation:blink 1.1s ease-in-out infinite;}
.sico.done{border-color:var(--green);background:var(--green);color:#fff;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.sbody{flex:1;min-width:0;}
.stitle{font-size:11px;font-weight:600;color:var(--text);}
.sconcept{font-size:9.5px;color:var(--muted);line-height:1.6;margin-top:4px;
          max-height:0;overflow:hidden;transition:max-height .4s ease;}
.srow.active .sconcept{max-height:130px;}

.pbar{height:2px;background:var(--bord);margin:8px 14px 0;border-radius:1px;}
.pfill{height:100%;background:var(--cyan);border-radius:1px;width:0%;transition:width .6s ease;}

.log-wrap{flex:1;overflow:hidden;display:flex;flex-direction:column;min-height:0;}
.log-hdr{padding:7px 14px;font-size:9px;color:var(--muted);letter-spacing:2px;
         text-transform:uppercase;border-bottom:1px solid var(--bord);}
#log{flex:1;overflow-y:auto;padding:8px 14px;font-size:10px;line-height:1.75;}
#log .ok    {color:#3fb950;}
#log .info  {color:var(--blue);}
#log .cmd   {color:var(--purple);}
#log .warn  {color:var(--amber);}
#log .err   {color:var(--red);}
#log .build {color:var(--muted);}
#log .dim   {color:var(--dim);}
#log .hi    {color:var(--cyan);}
#log .prompt{color:var(--cyan);font-weight:700;}
#log .sep   {color:#21262d;}
#log .ts    {color:#30363d;}

/* ── right: topology + metrics ── */
.right{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative;}
.topo-wrap{flex:1;position:relative;overflow:hidden;
  background:radial-gradient(ellipse at 50% 45%,rgba(45,212,191,.035) 0%,transparent 68%);}
#topo{display:block;width:100%;height:100%;}

/* tooltip */
#tip{position:absolute;pointer-events:none;background:var(--surf);
     border:1px solid var(--bord);border-radius:5px;padding:5px 11px;
     font-size:10.5px;color:var(--text);white-space:nowrap;opacity:0;
     transition:opacity .12s;z-index:20;max-width:300px;line-height:1.4;}

/* detail panel */
#dpanel{position:absolute;top:0;right:0;bottom:46px;width:265px;
        background:var(--surf);border-left:1px solid var(--bord);
        transform:translateX(100%);transition:transform .28s ease;
        overflow-y:auto;z-index:30;display:flex;flex-direction:column;}
#dpanel.open{transform:translateX(0);}
.dp-hdr{padding:12px 14px;border-bottom:1px solid var(--bord);
        display:flex;align-items:center;gap:8px;flex-shrink:0;}
.dp-name{font-size:13px;font-weight:700;flex:1;}
.dp-x{cursor:pointer;background:transparent;border:none;color:var(--muted);
      font-size:14px;padding:2px 5px;border-radius:3px;}
.dp-x:hover{background:var(--surf2);color:var(--text);}
.dp-body{padding:14px;display:flex;flex-direction:column;gap:11px;}
.dp-sub{font-size:9.5px;color:var(--muted);margin-top:-5px;}
.dp-desc{font-size:10.5px;color:var(--text);line-height:1.65;}
.dp-fields{display:flex;flex-direction:column;gap:5px;}
.dp-f{display:flex;gap:8px;align-items:flex-start;}
.dp-fk{font-size:9px;color:var(--muted);min-width:66px;padding-top:1px;
       text-transform:uppercase;letter-spacing:.5px;flex-shrink:0;}
.dp-fv{font-size:10px;color:var(--text);line-height:1.55;word-break:break-all;}
.dp-spec{background:rgba(45,212,191,.06);border:1px solid rgba(45,212,191,.2);
         border-left:3px solid var(--cyan);border-radius:4px;padding:7px 10px;
         font-size:9.5px;color:var(--cyan);line-height:1.5;}
.dp-slbl{font-size:8px;text-transform:uppercase;letter-spacing:.5px;opacity:.6;margin-bottom:2px;}

/* metrics bar */
.mbar{display:flex;border-top:1px solid var(--bord);flex-shrink:0;height:46px;}
.mcard{flex:1;padding:6px 12px;border-right:1px solid var(--bord);
       display:flex;flex-direction:column;justify-content:center;}
.mcard:last-child{border-right:none;}
.mlbl{font-size:8px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;margin-bottom:2px;}
.mval{font-size:12px;font-weight:600;color:var(--muted);}
.mval.ok{color:#3fb950;} .mval.err{color:var(--red);}

::-webkit-scrollbar{width:3px;}
::-webkit-scrollbar-thumb{background:#21262d;border-radius:2px;}
</style>
</head>
<body>

<header>
  <span class="logo">FAIR-5G</span>
  <span class="hbadge" id="hbadge">Tutorial · Baseline</span>
  <div class="speed-wrap">
    <span class="slbl">velocidade</span>
    <button class="spd on"  onclick="setSpd(1,this)">1×</button>
    <button class="spd"     onclick="setSpd(2,this)">2×</button>
    <button class="spd"     onclick="setSpd(4,this)">4×</button>
    <button id="btn-start"  onclick="startTutorial()">▶  Iniciar</button>
    <span class="htime" id="htime">00:00</span>
  </div>
</header>

<div class="layout">

  <!-- ── esquerda ── -->
  <div class="left">
    <div class="steps-box">
      <div class="steps-hdr">Progresso — 5 Passos</div>
      <div id="sc"></div>
    </div>
    <div class="pbar"><div class="pfill" id="prog"></div></div>
    <div class="log-wrap">
      <div class="log-hdr">Terminal</div>
      <div id="log"></div>
    </div>
  </div>

  <!-- ── direita ── -->
  <div class="right">
    <div class="topo-wrap">
      <svg id="topo"></svg>
      <div id="tip"></div>
      <div id="dpanel">
        <div class="dp-hdr">
          <span class="dp-name" id="dp-name">—</span>
          <button class="dp-x" onclick="closeDP()">✕</button>
        </div>
        <div class="dp-body" id="dp-body"></div>
      </div>
    </div>
    <div class="mbar">
      <div class="mcard"><div class="mlbl">UE1 Probe</div>   <div class="mval" id="m0">—</div></div>
      <div class="mcard"><div class="mlbl">UE2 Probe</div>   <div class="mval" id="m1">—</div></div>
      <div class="mcard"><div class="mlbl">UE1 Latência</div><div class="mval" id="m2">—</div></div>
      <div class="mcard"><div class="mlbl">UE2 Latência</div><div class="mval" id="m3">—</div></div>
      <div class="mcard"><div class="mlbl">AMF Sessions</div><div class="mval" id="m4">—</div></div>
    </div>
  </div>

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
// ═══════════════════════════════════════════
//  DEFINIÇÃO DOS PASSOS
// ═══════════════════════════════════════════
const STEPS = [
  { n:1, title:"Limpeza do ambiente",
    concept:"Remove resíduos de execuções anteriores: containers Containernet (mn.*), interface veth-sdn e regras iptables duplicadas. Garante estado inicial determinístico — fundamento de reprodutibilidade." },
  { n:2, title:"Núcleo 5G — Open5GS",
    concept:"Instancia 23 containers via Docker Compose: db, nrf, amf, smf1, smf2, upf1, upf2 e serviços auxiliares. Dois pares SMF/UPF garantem isolamento entre fatias (3GPP TS 23.501)." },
  { n:3, title:"Registro de subscribers",
    concept:"Popula o MongoDB com dois UEs: IMSI, chaves K/OPc e S-NSSAI por fatia. O S-NSSAI (SST + SD) é o identificador que vincula cada UE à sua fatia no registro com o AMF." },
  { n:4, title:"Configuração runtime dos UEs",
    concept:"Inspeciona o IP dinâmico do container gnb e gera os YAMLs do UERANSIM com gnbSearchList correto. Sem automação, esse passo quebraria a cada nova execução." },
  { n:5, title:"SDN — ONOS + Containernet",
    concept:"Sobe o ONOS (aguarda API via retry loop ~9 tentativas), ativa apps OpenFlow/fwd, e instancia topologia Mininet com switch OVS e dois UEs que se conectam via UERANSIM." },
];

// ═══════════════════════════════════════════
//  TOPOLOGIA — NODOS + DETALHES
// ═══════════════════════════════════════════
const ND = {
  ue1:{lbl:"UE 1",    sub:"UERANSIM",      col:"#2dd4bf",x:.07,y:.28,
    tip:"UE 1 — dispositivo emulado da Fatia 1 (S-NSSAI sst=1, sd=000001)",
    det:{sub:"UERANSIM v3.2.6 · mn.ue1",
      desc:"Emula um dispositivo 5G usando UERANSIM. Conecta ao gNB via N1/N2 e estabelece sessão PDU com UPF1. IP na rede emulada 10.33.33.200; IP da sessão PDU no pool do UPF1 (10.45.x.x).",
      fields:[{k:"Container",v:"mn.ue1"},{k:"IP emulado",v:"10.33.33.200/24"},{k:"Pool PDU",v:"10.45.0.0/16 (UPF1)"},{k:"S-NSSAI",v:"sst=1, sd=000001"},{k:"Config",v:"configs/runtime/ue1.yaml"}],
      spec:"3GPP TS 23.501 §5.15 — Network Slicing"}},
  ue2:{lbl:"UE 2",    sub:"UERANSIM",      col:"#f59e0b",x:.07,y:.72,
    tip:"UE 2 — dispositivo emulado da Fatia 2 (S-NSSAI sst=1, sd=000002)",
    det:{sub:"UERANSIM v3.2.6 · mn.ue2",
      desc:"Segundo UE emulado, Fatia 2. Compartilha o gNB com UE1, mas AMF seleciona SMF2/UPF2 pelo S-NSSAI. Isolamento garante que degradação no UE1 não impacte o UE2.",
      fields:[{k:"Container",v:"mn.ue2"},{k:"IP emulado",v:"10.33.33.201/24"},{k:"Pool PDU",v:"10.46.0.0/16 (UPF2)"},{k:"S-NSSAI",v:"sst=1, sd=000002"},{k:"Config",v:"configs/runtime/ue2.yaml"}],
      spec:"3GPP TS 23.501 §5.15 — Network Slicing"}},
  gnb:{lbl:"gNB",     sub:"UERANSIM/RAN",  col:"#60a5fa",x:.24,y:.50,
    tip:"gNodeB — estação rádio base 5G NR (IP dinâmico: 10.33.33.17)",
    det:{sub:"UERANSIM gNB · container: gnb",
      desc:"Emula a estação base 5G NR. Aceita conexões dos UEs via NGAP e encaminha ao AMF. IP atribuído dinamicamente pelo Docker (ex: 10.33.33.17) — por isso o render_ue_configs.sh é necessário antes de subir os UEs.",
      fields:[{k:"Container",v:"gnb"},{k:"IP dinâmico",v:"10.33.33.17 (exemplo)"},{k:"Protocolo",v:"N1/N2 — NGAP/SCTP"},{k:"Dependência",v:"render_ue_configs.sh"}],
      spec:"3GPP TS 38.300 — NR; NG-RAN"}},
  onos:{lbl:"ONOS",   sub:"SDN Controller",col:"#a78bfa",x:.42,y:.14,
    tip:"ONOS — controlador SDN que programa o OVS via OpenFlow 1.3",
    det:{sub:"onosproject/onos:2.7 · onos-controller",
      desc:"Controlador SDN que programa regras de encaminhamento no OVS. A FAIR-5G ativa apps openflow e fwd via REST API. O loop de retry (até 60 tentativas a cada ~2s) é esperado — ONOS demora ~20s para inicializar completamente.",
      fields:[{k:"Container",v:"onos-controller"},{k:"REST API",v:"http://localhost:8181"},{k:"OpenFlow",v:"porta 6653"},{k:"Apps",v:"openflow, fwd"}],
      spec:"ONF OpenFlow 1.3 · ONOS 2.7"}},
  ovs:{lbl:"OVS",     sub:"OpenFlow Switch",col:"#60a5fa",x:.42,y:.50,
    tip:"Open vSwitch — switch virtual que separa o tráfego das fatias por flow rules",
    det:{sub:"Open vSwitch · s1 (Containernet)",
      desc:"Switch OpenFlow criado pelo Containernet (s1). Faz bridge entre rede emulada e rede Docker do núcleo (br-ogs). Recebe regras do ONOS que encaminham UE1→UPF1 e UE2→UPF2. A separação de fluxos no OVS é o mecanismo central do fatiamento no plano de dados.",
      fields:[{k:"Bridge Docker",v:"br-ogs"},{k:"Controlador",v:"ONOS via OpenFlow"},{k:"Separação",v:"flow rules por S-NSSAI"}],
      spec:"Open vSwitch 3.x · ONF OpenFlow 1.3"}},
  amf:{lbl:"AMF",     sub:"5G Core",        col:"#60a5fa",x:.58,y:.50,
    tip:"AMF — gerencia registro, autenticação e seleção de fatia dos UEs",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: amf",
      desc:"Access and Mobility Management Function: ponto de entrada do núcleo. Processa Registration Request, autentica via AUSF/UDM e seleciona a SMF correta pelo S-NSSAI do UE. Compartilhado entre fatias — o isolamento real ocorre no SMF/UPF.",
      fields:[{k:"Container",v:"amf"},{k:"NGAP",v:"porta 38412 (SCTP)"},{k:"SBI",v:"HTTP/2 porta 7777"},{k:"Startup",v:"4.7s após compose up"}],
      spec:"3GPP TS 29.518 — AMF Services"}},
  smf1:{lbl:"SMF₁",   sub:"Slice 1",        col:"#2dd4bf",x:.74,y:.28,
    tip:"SMF₁ — gerencia sessão PDU do UE1 e configura UPF1 via PFCP",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: smf1",
      desc:"Session Management Function exclusiva da Fatia 1. Estabelece sessão PDU do UE1, aloca IP do pool 10.45.0.0/16 e configura UPF1 via PFCP. Instância separada do SMF2 — falhas não se propagam entre fatias.",
      fields:[{k:"Container",v:"smf1"},{k:"PFCP",v:"porta 8805 (UDP)"},{k:"Pool IP",v:"10.45.0.0/16"},{k:"Startup",v:"7.2s após compose up"}],
      spec:"3GPP TS 29.502 — SMF Services"}},
  upf1:{lbl:"UPF₁",   sub:"Slice 1",        col:"#2dd4bf",x:.90,y:.28,
    tip:"UPF₁ — plano de dados da Fatia 1, encaminha pacotes do UE1 via GTP-U",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: upf1",
      desc:"User Plane Function da Fatia 1. Encaminha pacotes do UE1 via GTP-U. Recebe instruções do SMF1 via PFCP. Opera na sub-rede 10.45.0.0/16. No cenário de estresse, é este UPF que sofre degradação — sem afetar UPF2.",
      fields:[{k:"Container",v:"upf1"},{k:"GTP-U",v:"porta 2152 (UDP)"},{k:"Sub-rede",v:"10.45.0.0/16"},{k:"Startup",v:"2.7s após compose up"}],
      spec:"3GPP TS 29.244 — PFCP; GTP-U"}},
  smf2:{lbl:"SMF₂",   sub:"Slice 2",        col:"#f59e0b",x:.74,y:.72,
    tip:"SMF₂ — gerencia sessão PDU do UE2 e configura UPF2 via PFCP",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: smf2",
      desc:"Session Management Function da Fatia 2. Configuração espelhada do SMF1, mas com pool de IPs e UPF distintos. O plano de controle da Fatia 2 é completamente independente — não apenas roteamento diferente, mas instância separada do processo.",
      fields:[{k:"Container",v:"smf2"},{k:"PFCP",v:"porta 8805 (UDP)"},{k:"Pool IP",v:"10.46.0.0/16"},{k:"Startup",v:"6.4s após compose up"}],
      spec:"3GPP TS 29.502 — SMF Services"}},
  upf2:{lbl:"UPF₂",   sub:"Slice 2",        col:"#f59e0b",x:.90,y:.72,
    tip:"UPF₂ — plano de dados da Fatia 2, encaminha pacotes do UE2 via GTP-U",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: upf2",
      desc:"User Plane Function da Fatia 2. Opera na sub-rede 10.46.0.0/16. O cenário de isolamento valida que pacotes do UE1 nunca atravessam o UPF2 — o OVS garante essa separação com as flow rules do ONOS.",
      fields:[{k:"Container",v:"upf2"},{k:"GTP-U",v:"porta 2152 (UDP)"},{k:"Sub-rede",v:"10.46.0.0/16"},{k:"Startup",v:"2.1s após compose up"}],
      spec:"3GPP TS 29.244 — PFCP; GTP-U"}},
  db:{lbl:"MongoDB",  sub:"open5gs-db",     col:"#60a5fa",x:.58,y:.17,
    tip:"MongoDB — banco de subscribers: IMSI, K, OPc e S-NSSAI por UE",
    det:{sub:"mongo:6.0 · container: db",
      desc:"Armazena o registro de assinantes: IMSI, K, OPc e S-NSSAI. Populado pelo seed_subscribers.sh (2 upserts). UDM consulta este banco durante autenticação. Primeiro container a subir (2.1s).",
      fields:[{k:"Container",v:"db"},{k:"Porta",v:"27017"},{k:"Volume",v:"open5gs_db_data"},{k:"Seed",v:"processed=2, upserts=2"}],
      spec:"3GPP TS 29.503 — UDM Data Model"}},
  nrf:{lbl:"NRF",     sub:"NF Registry",    col:"#60a5fa",x:.58,y:.83,
    tip:"NRF — catálogo de funções de rede ativas (DNS interno do núcleo 5G)",
    det:{sub:"gradiant/open5gs:v2.7.5 · container: nrf",
      desc:"Network Repository Function: catálogo de todas as VNFs ativas. AMF consulta NRF para descobrir o SMF correto para cada fatia. Segundo container a subir (2.7s) — os outros dependem dele para se registrar.",
      fields:[{k:"Container",v:"nrf"},{k:"SBI",v:"HTTP/2 porta 7777"},{k:"Startup",v:"2.7s — sobe antes do AMF"}],
      spec:"3GPP TS 29.510 — NRF Services"}},
  prometheus:{lbl:"Prometheus",sub:"metrics:9090",col:"#e5742d",x:.74,y:.50,
    tip:"Prometheus — coleta métricas dos containers a cada 15s (porta 9090)",
    det:{sub:"prom/prometheus:v2.51 · container: prometheus",
      desc:"Coleta métricas dos containers do núcleo. Backend do módulo metrics.py (snapshot/watch/report). Dados persistidos em volume Docker para comparação entre execuções.",
      fields:[{k:"Container",v:"prometheus"},{k:"Porta",v:"9090"},{k:"Volume",v:"open5gs_prometheus_data"},{k:"Startup",v:"7.7s após compose up"}],
      spec:"OpenMetrics / Prometheus data model"}},
  grafana:{lbl:"Grafana",sub:"dashboard:3000",col:"#e5742d",x:.90,y:.50,
    tip:"Grafana — dashboards de métricas em localhost:3000 (admin/grafana)",
    det:{sub:"grafana/grafana:10.3 · container: grafana",
      desc:"Dashboards pré-configurados: latência por fatia, sessions AMF, throughput UPF. Último container a subir (8.1s) pois depende do Prometheus.",
      fields:[{k:"Container",v:"grafana"},{k:"Porta",v:"3000"},{k:"Acesso",v:"http://localhost:3000"},{k:"Login",v:"admin / admin"},{k:"Startup",v:"8.1s — último a subir"}],
      spec:"Grafana Labs OSS"}},
};

const LINKS=[
  {s:"ue1", d:"gnb",        col:"#2dd4bf"},
  {s:"ue2", d:"gnb",        col:"#f59e0b"},
  {s:"gnb", d:"ovs",        col:"#60a5fa"},
  {s:"onos",d:"ovs",        col:"#a78bfa",dash:true},
  {s:"ovs", d:"amf",        col:"#60a5fa"},
  {s:"amf", d:"smf1",       col:"#2dd4bf"},
  {s:"smf1",d:"upf1",       col:"#2dd4bf"},
  {s:"amf", d:"smf2",       col:"#f59e0b"},
  {s:"smf2",d:"upf2",       col:"#f59e0b"},
  {s:"amf", d:"db",         col:"#21262d"},
  {s:"amf", d:"nrf",        col:"#21262d"},
  {s:"amf", d:"prometheus", col:"#21262d",dash:true},
  {s:"prometheus",d:"grafana",col:"#21262d",dash:true},
];

// ═══════════════════════════════════════════
//  SIMULAÇÃO — eventos fixos, sem execução real
//  t = ms a partir do início do passo (velocidade 1×)
// ═══════════════════════════════════════════
const SIM=[
  // ── INTRO ──────────────────────────────────────────────────────────────
  {step:0,t:200, line:"╔══════════════════════════════════════════════════╗",cls:"sep"},
  {step:0,t:300, line:"║          FAIR-5G — Modo Tutorial                ║",cls:"hi"},
  {step:0,t:400, line:"╚══════════════════════════════════════════════════╝",cls:"sep"},
  {step:0,t:600, line:""},
  {step:0,t:800, line:"Este tutorial demonstra o fluxo completo de",cls:"dim"},
  {step:0,t:950, line:"provisionamento do ambiente FAIR-5G baseline.",cls:"dim"},
  {step:0,t:1100,line:""},
  {step:0,t:1200,line:"O que será demonstrado:",cls:"info"},
  {step:0,t:1400,line:"  1. Limpeza do ambiente anterior",cls:"dim"},
  {step:0,t:1550,line:"  2. Subida do núcleo 5G (Open5GS, 23 containers)",cls:"dim"},
  {step:0,t:1700,line:"  3. Registro de subscribers no MongoDB",cls:"dim"},
  {step:0,t:1850,line:"  4. Geração de configs runtime para os UEs",cls:"dim"},
  {step:0,t:2000,line:"  5. Camada SDN — ONOS + Containernet + UERANSIM",cls:"dim"},
  {step:0,t:2200,line:""},
  {step:0,t:2300,line:"Clique nos nós da topologia para ver detalhes.",cls:"dim"},
  {step:0,t:2500,line:""},
  {step:0,t:2700,line:"Iniciando em 3...",cls:"warn"},
  {step:0,t:3500,line:"Iniciando em 2...",cls:"warn"},
  {step:0,t:4300,line:"Iniciando em 1...",cls:"warn"},
  {step:0,t:5000,done:true},

  // ── PASSO 1: Pre-clean ─────────────────────────────────────────────────
  {step:1,t:0,   sep:true},
  {step:1,t:100, line:"[PASSO 1/5] Limpeza do ambiente",cls:"hi"},
  {step:1,t:300, line:""},
  {step:1,t:400, line:"Antes de qualquer execução, garantimos que não",cls:"dim"},
  {step:1,t:550, line:"existem resíduos de rodadas anteriores.",cls:"dim"},
  {step:1,t:700, line:""},
  {step:1,t:800, line:"[v0] Repo: /home/user/open5gs-mininet",cls:"dim"},
  {step:1,t:1000,line:"[v0] Pre-clean: removendo resíduos do Containernet (mn.*), veth e iptables...",cls:"info"},
  {step:1,t:1400,line:"$ sudo docker rm -f $(sudo docker ps -aq --filter 'name=^mn\\.') 2>/dev/null || true",cls:"cmd"},
  {step:1,t:2000,line:"$ sudo ip link delete veth-sdn 2>/dev/null || true",cls:"cmd"},
  {step:1,t:2500,line:"$ while sudo iptables -D DOCKER-USER -j ACCEPT 2>/dev/null; do :; done",cls:"cmd"},
  {step:1,t:3200,line:""},
  {step:1,t:3300,line:"✓ Nenhum container mn.* encontrado.",cls:"ok"},
  {step:1,t:3600,line:"✓ Interface veth-sdn removida.",cls:"ok"},
  {step:1,t:3900,line:"✓ Regras DOCKER-USER limpas.",cls:"ok"},
  {step:1,t:4200,line:""},
  {step:1,t:4300,line:"[Conceito] Idempotência: executar o pipeline",cls:"dim"},
  {step:1,t:4450,line:"múltiplas vezes produz sempre o mesmo resultado.",cls:"dim"},
  {step:1,t:4650,line:"A limpeza inicial é o que garante isso.",cls:"dim"},
  {step:1,t:5000,done:true},

  // ── PASSO 2: Docker Compose up ─────────────────────────────────────────
  {step:2,t:0,   sep:true},
  {step:2,t:100, line:"[PASSO 2/5] Núcleo 5G — Open5GS",cls:"hi"},
  {step:2,t:300, line:""},
  {step:2,t:400, line:"O núcleo 5G é composto por VNFs (Virtual Network",cls:"dim"},
  {step:2,t:550, line:"Functions) em containers Docker. Para fatiamento,",cls:"dim"},
  {step:2,t:700, line:"instanciamos dois pares SMF/UPF independentes.",cls:"dim"},
  {step:2,t:900, line:""},
  {step:2,t:1000,line:"[v0] Subindo Open5GS via compose file...",cls:"info"},
  {step:2,t:1200,line:"$ sudo docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file .env up -d --build --remove-orphans",cls:"cmd"},
  {step:2,t:1700,line:""},
  {step:2,t:1800,line:"[+] Building 1.4s (4/4)",cls:"build"},
  {step:2,t:2100,line:"  ✔ Image webui:v2.7.5             Built    2.5s",cls:"ok"},
  {step:2,t:2350,line:"  ✔ Network open5gs                Created  0.1s",cls:"ok"},
  {step:2,t:2550,line:"  ✔ Volume open5gs_db_data         Created  0.0s",cls:"ok"},
  {step:2,t:2700,line:"  ✔ Volume open5gs_db_config       Created  0.0s",cls:"ok"},
  {step:2,t:2850,line:"  ✔ Volume open5gs_prometheus_data Created  0.0s",cls:"ok"},
  // db
  {step:2,t:3100,pulse:["db"]},
  {step:2,t:3500,line:"  ✔ Container db                   Started  2.1s",cls:"ok",node_on:"db"},
  // nrf
  {step:2,t:3700,pulse:["nrf"]},
  {step:2,t:4100,line:"  ✔ Container nrf                  Started  2.7s",cls:"ok",node_on:"nrf"},
  // upf1, upf2
  {step:2,t:4300,pulse:["upf1","upf2"]},
  {step:2,t:4700,line:"  ✔ Container upf1                 Started  2.7s",cls:"ok",node_on:"upf1"},
  {step:2,t:4900,line:"  ✔ Container upf2                 Started  2.1s",cls:"ok",node_on:"upf2"},
  // outros auxiliares
  {step:2,t:5100,line:"  ✔ Container blackbox             Started  2.7s",cls:"build"},
  // amf
  {step:2,t:5300,pulse:["amf"]},
  {step:2,t:6000,line:"  ✔ Container amf                  Started  4.7s",cls:"ok",node_on:"amf"},
  // auxiliares
  {step:2,t:6200,line:"  ✔ Container udm                  Started  5.8s",cls:"build"},
  {step:2,t:6350,line:"  ✔ Container nssf                 Started  5.4s",cls:"build"},
  {step:2,t:6500,line:"  ✔ Container ausf                 Started  5.4s",cls:"build"},
  // smf2
  {step:2,t:6700,pulse:["smf2"]},
  {step:2,t:7300,line:"  ✔ Container smf2                 Started  6.4s",cls:"ok",node_on:"smf2"},
  // mais auxiliares
  {step:2,t:7500,line:"  ✔ Container udr                  Started  6.8s",cls:"build"},
  {step:2,t:7650,line:"  ✔ Container pcf                  Started  7.2s",cls:"build"},
  {step:2,t:7800,line:"  ✔ Container bsf                  Started  7.2s",cls:"build"},
  // smf1
  {step:2,t:7900,pulse:["smf1"]},
  {step:2,t:8400,line:"  ✔ Container smf1                 Started  7.2s",cls:"ok",node_on:"smf1"},
  // prometheus, gnb, grafana
  {step:2,t:8500,pulse:["prometheus"]},
  {step:2,t:8700,line:"  ✔ Container webui                Started  3.6s",cls:"build"},
  {step:2,t:8900,line:"  ✔ Container prometheus           Started  7.7s",cls:"ok",node_on:"prometheus"},
  {step:2,t:9000,pulse:["gnb"]},
  {step:2,t:9200,line:"  ✔ Container gnb                  Started  7.6s",cls:"ok",node_on:"gnb"},
  {step:2,t:9350,pulse:["grafana"]},
  {step:2,t:9700,line:"  ✔ Container grafana              Started  8.1s",cls:"ok",node_on:"grafana"},
  {step:2,t:9900,line:"[+] up 23/23",cls:"build"},
  {step:2,t:10200,line:""},
  {step:2,t:10300,line:"✓ Núcleo 5G operacional — 23 containers ativos.",cls:"ok"},
  {step:2,t:10600,line:""},
  {step:2,t:10700,line:"[Conceito] O NRF é o primeiro a subir (2.7s) pois",cls:"dim"},
  {step:2,t:10850,line:"todos os outros dependem dele para se registrar.",cls:"dim"},
  {step:2,t:11050,line:"O grafana é o último (8.1s) pois depende do prometheus.",cls:"dim"},
  {step:2,t:11400,done:true},

  // ── PASSO 3: Seed subscribers ──────────────────────────────────────────
  {step:3,t:0,   sep:true},
  {step:3,t:100, line:"[PASSO 3/5] Registro de subscribers",cls:"hi"},
  {step:3,t:300, line:""},
  {step:3,t:400, line:"Cada UE precisa estar cadastrado no núcleo com",cls:"dim"},
  {step:3,t:550, line:"seu IMSI, chaves K/OPc e S-NSSAI antes de poder",cls:"dim"},
  {step:3,t:700, line:"realizar o registro. O seed é idempotente.",cls:"dim"},
  {step:3,t:900, line:""},
  {step:3,t:1000,line:"[v0] Seed subscribers (idempotente)...",cls:"info"},
  {step:3,t:1300,line:"[seed] Waiting for Mongo to respond...",cls:"info"},
  {step:3,t:2200,line:"[seed] Mongo is ready.",cls:"ok"},
  {step:3,t:2500,line:"[seed] Copying seed file into container...",cls:"info"},
  {step:3,t:3000,line:"Successfully copied 2.38kB (transferred 4.1kB) to db:/tmp/subscribers.js",cls:"dim"},
  {step:3,t:3500,line:"[seed] Applying subscribers seed...",cls:"info"},
  {step:3,t:4100,line:"[seed] subscribers processed=2  upserts=2",cls:"ok"},
  {step:3,t:4400,line:"[seed] Done.",cls:"ok"},
  {step:3,t:4700,line:""},
  {step:3,t:4800,line:"✓ UE1 e UE2 registrados com S-NSSAIs distintos.",cls:"ok"},
  {step:3,t:5100,line:""},
  {step:3,t:5200,line:"[Conceito] O S-NSSAI (sst=1, sd=000001 vs sd=000002)",cls:"dim"},
  {step:3,t:5350,line:"é o que determina, no momento do registro, qual",cls:"dim"},
  {step:3,t:5500,line:"par SMF/UPF o AMF irá selecionar para cada UE.",cls:"dim"},
  {step:3,t:5800,done:true},

  // ── PASSO 4: Render configs ────────────────────────────────────────────
  {step:4,t:0,   sep:true},
  {step:4,t:100, line:"[PASSO 4/5] Configuração runtime dos UEs",cls:"hi"},
  {step:4,t:300, line:""},
  {step:4,t:400, line:"O UERANSIM precisa do IP do container gnb para",cls:"dim"},
  {step:4,t:550, line:"conectar. Como o Docker atribui IPs dinamicamente,",cls:"dim"},
  {step:4,t:700, line:"geramos os YAMLs em tempo de execução.",cls:"dim"},
  {step:4,t:900, line:""},
  {step:4,t:1000,line:"[v0] Renderizando configs runtime do UE (gnbSearchList)...",cls:"info"},
  {step:4,t:1300,line:"$ ./scripts/render_ue_configs.sh",cls:"cmd"},
  {step:4,t:1800,line:"[render] gnb ip: 10.33.33.17",cls:"ok"},
  {step:4,t:2200,pulse:["ue1"]},
  {step:4,t:2300,line:"[render] gerado: configs/runtime/ue1.yaml",cls:"ok",node_on:"ue1"},
  {step:4,t:2600,pulse:["ue2"]},
  {step:4,t:2800,line:"[render] gerado: configs/runtime/ue2.yaml",cls:"ok",node_on:"ue2"},
  {step:4,t:3200,line:""},
  {step:4,t:3300,line:"✓ gnbSearchList → 10.33.33.17 em ue1.yaml e ue2.yaml",cls:"ok"},
  {step:4,t:3600,line:""},
  {step:4,t:3700,line:"[Conceito] Sem automação, qualquer reinicialização",cls:"dim"},
  {step:4,t:3850,line:"do Docker poderia mudar o IP do gnb, quebrando",cls:"dim"},
  {step:4,t:4000,line:"silenciosamente os UEs na próxima execução.",cls:"dim"},
  {step:4,t:4300,done:true},

  // ── PASSO 5: SDN ──────────────────────────────────────────────────────
  {step:5,t:0,   sep:true},
  {step:5,t:100, line:"[PASSO 5/5] SDN — ONOS + Containernet",cls:"hi"},
  {step:5,t:300, line:""},
  {step:5,t:400, line:"Agora conectamos os UEs ao núcleo via SDN.",cls:"dim"},
  {step:5,t:550, line:"O ONOS leva ~20s para inicializar — o loop de",cls:"dim"},
  {step:5,t:700, line:"retry abaixo é comportamento normal esperado.",cls:"dim"},
  {step:5,t:900, line:""},
  {step:5,t:1000,line:"[v0] Subindo SDN + UEs (Containernet + ONOS)...",cls:"info"},
  {step:5,t:1300,line:"Usando CONFIG_DIR: /home/user/open5gs-mininet/configs/runtime",cls:"dim"},
  {step:5,t:1700,line:"Configurando Controlador ONOS...",cls:"info"},
  {step:5,t:2000,line:"Iniciando container ONOS (novo)...",cls:"info"},
  {step:5,t:2400,line:"Aguardando API do ONOS iniciar...",cls:"info"},
  // retry loop fiel ao log real (9 tentativas)
  {step:5,t:2800,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:3050,line:"Tentativa 1/60",cls:"dim"},
  {step:5,t:3900,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:4150,line:"Tentativa 2/60",cls:"dim"},
  {step:5,t:5000,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:5250,line:"Tentativa 3/60",cls:"dim"},
  {step:5,t:6100,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:6350,line:"Tentativa 4/60",cls:"dim"},
  {step:5,t:7200,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:7450,line:"Tentativa 5/60",cls:"dim"},
  {step:5,t:7800,pulse:["onos"]},
  {step:5,t:8300,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:8550,line:"Tentativa 6/60",cls:"dim"},
  {step:5,t:9400,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:9650,line:"Tentativa 7/60",cls:"dim"},
  {step:5,t:10200,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:10450,line:"Tentativa 8/60",cls:"dim"},
  {step:5,t:10900,line:"Ativando App via API: org.onosproject.openflow",cls:"warn"},
  {step:5,t:11100,line:"Tentativa 9/60",cls:"dim"},
  {step:5,t:11600,line:"ONOS API pronta e Apps ativados.",cls:"ok",node_on:"onos"},
  {step:5,t:12000,line:"Ativando App via API: org.onosproject.fwd",cls:"info"},
  {step:5,t:12500,line:"Configurando Cabos Virtuais...",cls:"info"},
  {step:5,t:12900,line:"Buscando ponte para rede: open5gs",cls:"dim"},
  {step:5,t:13300,line:"Ponte encontrada: br-ogs",cls:"ok"},
  {step:5,t:13700,line:"Iniciando Topologia Mininet...",cls:"info"},
  {step:5,t:14100,line:"*** Adicionando Controlador",cls:"dim"},
  {step:5,t:14400,pulse:["ovs"]},
  {step:5,t:14500,line:"*** Adicionando Switch",cls:"dim"},
  {step:5,t:14900,line:"*** Adicionando UE1",cls:"dim"},
  {step:5,t:15200,line:"ue1: kwargs {'ip': '10.33.33.200/24', 'privileged': True, 'volumes': ['/configs/runtime:/UERANSIM/config:ro']}",cls:"dim"},
  {step:5,t:15450,line:"ue1: update resources {}",cls:"dim"},
  {step:5,t:15700,line:"*** Adicionando UE2",cls:"dim"},
  {step:5,t:16000,line:"ue2: kwargs {'ip': '10.33.33.201/24', 'privileged': True, 'volumes': ['/configs/runtime:/UERANSIM/config:ro']}",cls:"dim"},
  {step:5,t:16250,line:"ue2: update resources {}",cls:"dim"},
  {step:5,t:16600,line:"*** Conectando Componentes",cls:"dim",node_on:"ovs"},
  {step:5,t:17000,line:"*** Iniciando a Rede",cls:"dim"},
  {step:5,t:17300,line:"*** Configuring hosts",cls:"dim"},
  {step:5,t:17500,line:"ue1  ue2",cls:"dim"},
  {step:5,t:17800,line:"*** Starting controller",cls:"dim"},
  {step:5,t:18000,line:"c0",cls:"dim"},
  {step:5,t:18300,line:"*** Starting 1 switches",cls:"dim"},
  {step:5,t:18600,line:"s1 ...",cls:"dim"},
  {step:5,t:19000,line:"Iniciando Conexao 5G (UERANSIM)...",cls:"info"},
  {step:5,t:19800,line:"ue1 iniciado. Log: /tmp/ue1.log",cls:"ok"},
  {step:5,t:20500,line:"ue2 iniciado. Log: /tmp/ue2.log",cls:"ok"},
  {step:5,t:21100,line:""},
  {step:5,t:21200,line:"Ambiente Pronto (Mininet)",cls:"ok"},
  {step:5,t:21500,line:"Logs: ue1 sh -c \"tail -f /tmp/ue1.log\"",cls:"dim"},
  {step:5,t:21800,line:"Ping básico: ue1 ping -c 3 10.33.33.201",cls:"dim"},
  {step:5,t:22100,line:""},
  {step:5,t:22200,line:"*** Starting CLI:",cls:"dim"},
  {step:5,t:22500,line:"containernet>",cls:"prompt"},
  {step:5,t:23000,done:true},
];

// ═══════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════
let speed     = 1;
let timers    = [];
let online    = new Set();
let pulsing   = new Set();
let pktTmrs   = [];
let animDone  = false;
let W = 0, H = 0;

// ═══════════════════════════════════════════
//  TOPOLOGIA D3
// ═══════════════════════════════════════════
const svg = d3.select("#topo");
const lg  = svg.append("g").attr("id","ll");
const pg  = svg.append("g").attr("id","lp");
const ng  = svg.append("g").attr("id","ln");
const NW=74, NH=40, R=5;

function px(n){return n.x*W;} function py(n){return n.y*H;}

function drawTopo(){
  const rc=document.getElementById("topo").getBoundingClientRect();
  W=rc.width; H=rc.height;
  if(!W||!H) return;

  // slice bands
  svg.selectAll(".sb").remove();
  [[.07,.08,.38,"#2dd4bf"],[.07,.54,.38,"#f59e0b"]].forEach(([_,yf,hf,c])=>{
    svg.insert("rect",":first-child").attr("class","sb")
      .attr("x",0).attr("y",H*yf).attr("width",W).attr("height",H*hf)
      .attr("fill",c).attr("opacity",.025);
  });
  svg.selectAll(".sl").remove();
  [["SLICE 1","#2dd4bf",H*.1],["SLICE 2","#f59e0b",H*.57]].forEach(([t,c,y])=>{
    svg.append("text").attr("class","sl").attr("x",8).attr("y",y).text(t)
      .attr("fill",c).attr("opacity",.2).attr("font-size",8)
      .attr("font-weight",700).attr("letter-spacing",2.5).attr("font-family","monospace");
  });

  // links
  lg.selectAll("*").remove();
  LINKS.forEach(l=>{
    const s=ND[l.s],d=ND[l.d];
    lg.append("line").attr("id","lk-"+l.s+"-"+l.d)
      .attr("x1",px(s)).attr("y1",py(s)).attr("x2",px(d)).attr("y2",py(d))
      .attr("stroke",l.col).attr("stroke-width",1.5).attr("stroke-opacity",.1)
      .attr("stroke-dasharray",l.dash?"5,4":null);
  });

  // nodes
  ng.selectAll("*").remove();
  Object.entries(ND).forEach(([k,n])=>{
    const g=ng.append("g").attr("id","nd-"+k)
      .attr("transform",`translate(${px(n)-NW/2},${py(n)-NH/2})`)
      .style("cursor","pointer");
    g.append("rect").attr("class","nr").attr("width",NW).attr("height",NH)
      .attr("rx",R).attr("fill","#161b22").attr("stroke",n.col)
      .attr("stroke-width",1).attr("opacity",.2);
    g.append("circle").attr("class","ns")
      .attr("cx",NW-8).attr("cy",8).attr("r",3.5).attr("fill","#21262d");
    g.append("text").attr("class","nl").attr("x",NW/2).attr("y",NH/2-5)
      .attr("text-anchor","middle").attr("dominant-baseline","central")
      .attr("fill","#e6edf3").attr("font-size",12).attr("font-weight",500)
      .attr("font-family","monospace").attr("opacity",.2).text(n.lbl);
    g.append("text").attr("class","ns2").attr("x",NW/2).attr("y",NH/2+8)
      .attr("text-anchor","middle").attr("dominant-baseline","central")
      .attr("fill",n.col).attr("font-size",8.5)
      .attr("font-family","monospace").attr("opacity",.1).text(n.sub);
    // hit area
    g.append("rect").attr("width",NW).attr("height",NH).attr("rx",R)
      .attr("fill","transparent")
      .on("mouseover",ev=>showTip(ev,n.tip))
      .on("mousemove",ev=>moveTip(ev))
      .on("mouseout", ()=>hideTip())
      .on("click",    ()=>showDP(k,n));
  });
  online.forEach(k=>_online(k));
  pulsing.forEach(k=>_pulse(k));
}

// ── css pulse animation ──────────────────
const ks=document.createElement("style");
ks.textContent="@keyframes np{0%,100%{stroke-opacity:1}50%{stroke-opacity:.2}}";
document.head.appendChild(ks);

function _pulse(k){
  d3.select("#nd-"+k+" .nr")
    .attr("opacity",.55).style("animation","np 0.85s ease-in-out infinite");
}
function _online(k){
  const n=ND[k]; if(!n) return;
  const g=d3.select("#nd-"+k);
  g.select(".nr").transition().duration(500)
    .attr("opacity",1).style("animation","none");
  g.select(".ns").transition().duration(400).attr("fill","#2ea043");
  g.select(".nl").transition().duration(500).attr("opacity",1);
  g.select(".ns2").transition().duration(500).attr("opacity",.8);
  LINKS.forEach(l=>{
    if((l.s===k||l.d===k)&&online.has(l.s)&&online.has(l.d))
      d3.select(`#lk-${l.s}-${l.d}`).transition().duration(600).attr("stroke-opacity",.35);
  });
}
function nodePulse(k){pulsing.add(k); _pulse(k);}
function nodeOnline(k){online.add(k); pulsing.delete(k); _online(k);}

// ── tooltip ──────────────────────────────
const tip=document.getElementById("tip");
function showTip(ev,txt){tip.textContent=txt;tip.style.opacity=1;moveTip(ev);}
function moveTip(ev){
  const b=document.querySelector(".topo-wrap").getBoundingClientRect();
  let x=ev.clientX-b.left+12, y=ev.clientY-b.top-38;
  if(x+305>b.width) x=ev.clientX-b.left-310;
  tip.style.left=x+"px"; tip.style.top=y+"px";
}
function hideTip(){tip.style.opacity=0;}

// ── detail panel ─────────────────────────
function showDP(k,n){
  document.getElementById("dp-name").textContent=n.lbl;
  document.getElementById("dp-name").style.color=n.col;
  const d=n.det;
  document.getElementById("dp-body").innerHTML=`
    <div class="dp-sub">${d.sub}</div>
    <div class="dp-desc">${d.desc}</div>
    <div class="dp-fields">${d.fields.map(f=>`
      <div class="dp-f">
        <span class="dp-fk">${f.k}</span>
        <span class="dp-fv">${f.v}</span>
      </div>`).join("")}</div>
    <div class="dp-spec">
      <div class="dp-slbl">Especificação</div>${d.spec}
    </div>`;
  document.getElementById("dpanel").classList.add("open");
}
function closeDP(){document.getElementById("dpanel").classList.remove("open");}
document.addEventListener("click",e=>{
  const p=document.getElementById("dpanel");
  if(p.classList.contains("open")&&!p.contains(e.target)&&!e.target.closest("#ln"))
    closeDP();
});

// ═══════════════════════════════════════════
//  STEPS UI
// ═══════════════════════════════════════════
const sc=document.getElementById("sc");
STEPS.forEach(s=>{
  sc.insertAdjacentHTML("beforeend",`
    <div class="srow" id="sr-${s.n}">
      <div class="sico" id="si-${s.n}">${s.n}</div>
      <div class="sbody">
        <div class="stitle">${s.title}</div>
        <div class="sconcept">${s.concept}</div>
      </div>
    </div>`);
});
function stepRun(n){
  document.querySelectorAll(".srow").forEach(r=>r.classList.remove("active"));
  document.getElementById("sr-"+n)?.classList.add("active");
  const i=document.getElementById("si-"+n);
  if(i){i.className="sico run";i.textContent="►";}
}
function stepDone(n){
  document.getElementById("sr-"+n)?.classList.remove("active");
  const i=document.getElementById("si-"+n);
  if(i){i.className="sico done";i.textContent="✓";}
  document.getElementById("prog").style.width=(n/5*100)+"%";
}

// ═══════════════════════════════════════════
//  TERMINAL
// ═══════════════════════════════════════════
const logEl=document.getElementById("log");
function addLine(line,cls){
  const d=document.createElement("div");
  if(line===""||line==null){d.innerHTML="&nbsp;";logEl.appendChild(d);return;}
  const s=document.createElement("span");
  s.className=cls||"dim";
  s.textContent=line;
  d.appendChild(s);
  logEl.appendChild(d);
  logEl.scrollTop=logEl.scrollHeight;
  while(logEl.children.length>500) logEl.removeChild(logEl.firstChild);
}
function addSep(){
  const d=document.createElement("div");
  d.innerHTML=`<span class="sep">${"─".repeat(52)}</span>`;
  logEl.appendChild(d);
  logEl.scrollTop=logEl.scrollHeight;
}

// ═══════════════════════════════════════════
//  PACOTES (após ambiente completo)
// ═══════════════════════════════════════════
function firePacket(path,col){
  const pts=path.map(k=>ND[k]).filter(Boolean);
  if(pts.length<2) return;
  const p=pg.append("circle").attr("r",3.5).attr("fill",col)
    .attr("opacity",.9).attr("cx",px(pts[0])).attr("cy",py(pts[0]));
  let tr=p.transition().ease(d3.easeLinear);
  for(let i=1;i<pts.length;i++){
    const dur=Math.hypot(px(pts[i])-px(pts[i-1]),py(pts[i])-py(pts[i-1]))/0.55;
    tr=tr.duration(dur).attr("cx",px(pts[i])).attr("cy",py(pts[i]))
         .transition().ease(d3.easeLinear);
  }
  tr.duration(200).attr("opacity",0).remove();
}
function startPackets(){
  if(animDone) return; animDone=true;
  pktTmrs.push(
    setInterval(()=>firePacket(["ue1","gnb","ovs","amf","smf1","upf1"],"#2dd4bf"),2200),
    setInterval(()=>firePacket(["ue2","gnb","ovs","amf","smf2","upf2"],"#f59e0b"),2700),
  );
  setTimeout(()=>{
    ["m0","m1"].forEach(id=>{const e=document.getElementById(id);e.textContent="● OK";e.className="mval ok";});
    document.getElementById("m2").textContent="0.65 ms";document.getElementById("m2").className="mval ok";
    document.getElementById("m3").textContent="0.67 ms";document.getElementById("m3").className="mval ok";
    document.getElementById("m4").textContent="2";document.getElementById("m4").className="mval ok";
  },1200);
}

// ═══════════════════════════════════════════
//  SIMULAÇÃO
// ═══════════════════════════════════════════
function clearTimers(){timers.forEach(clearTimeout);timers=[];}

function runStep(stepN){
  if(stepN>=1) stepRun(stepN);
  const badge=document.getElementById("hbadge");
  badge.className="hbadge run";
  badge.textContent=stepN>=1?`► passo ${stepN}/5`:"► iniciando";

  const evs=SIM.filter(e=>e.step===stepN);
  evs.forEach(ev=>{
    timers.push(setTimeout(()=>{
      if(ev.sep)           addSep();
      if(ev.line!=null)    addLine(ev.line, ev.cls);
      if(ev.pulse)         ev.pulse.forEach(k=>nodePulse(k));
      if(ev.node_on)       nodeOnline(ev.node_on);
      if(ev.done){
        if(stepN>=1) stepDone(stepN);
        if(stepN<5)  setTimeout(()=>runStep(stepN+1), 500/speed);
        else         finish();
      }
    }, ev.t/speed));
  });
}

function finish(){
  const badge=document.getElementById("hbadge");
  badge.textContent="✓ concluído"; badge.className="hbadge done";
  addSep();
  addLine("✓ Ambiente FAIR-5G operacional!","ok");
  addLine("  Slice 1 → UE1 → gNB → OVS → AMF → SMF₁ → UPF₁","dim");
  addLine("  Slice 2 → UE2 → gNB → OVS → AMF → SMF₂ → UPF₂","dim");
  addLine("  Métricas: http://localhost:3000 (Grafana)","dim");
  addLine("  Prometheus: http://localhost:9090","dim");
  startPackets();
}

// ═══════════════════════════════════════════
//  CONTROLES
// ═══════════════════════════════════════════
function setSpd(s,btn){
  speed=s;
  document.querySelectorAll(".spd").forEach(b=>b.classList.remove("on"));
  btn.classList.add("on");
}

function startTutorial(){
  const btn=document.getElementById("btn-start");
  btn.disabled=true;
  document.querySelectorAll(".spd").forEach(b=>b.disabled=true);
  const t0=Date.now();
  setInterval(()=>{
    const s=Math.floor((Date.now()-t0)/1000);
    document.getElementById("htime").textContent=
      String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0");
  },1000);
  runStep(0);
}

// ═══════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════
window.addEventListener("load",   drawTopo);
window.addEventListener("resize", drawTopo);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__)
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.logger.disabled = True

    @app.route("/")
    def index():
        return Response(HTML, mimetype="text/html")

    return app

def run_tutorial_mode(open_browser: bool = True):
    if not FLASK_OK:
        print("[ERRO] Flask não encontrado.")
        print("       pip3 install flask --break-system-packages")
        sys.exit(1)
    print(f"\n[tutorial] http://localhost:{PORT}   (Ctrl+C para encerrar)\n")
    if open_browser:
        def _open():
            time.sleep(1.0)
            webbrowser.open(f"http://localhost:{PORT}")
        threading.Thread(target=_open, daemon=True).start()
    create_app().run(host="0.0.0.0", port=PORT, threaded=True)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-browser", action="store_true")
    run_tutorial_mode(open_browser=not p.parse_args().no_browser)