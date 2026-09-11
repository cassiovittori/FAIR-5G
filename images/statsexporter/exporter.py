#!/usr/bin/env python3
"""Exportador Prometheus de metricas de recurso por container.

Por que existe, em vez de usar cAdvisor:
o cAdvisor identifica containers Docker lendo a camada de escrita em
/var/lib/docker/<driver>/. O Docker 29 introduziu o driver de armazenamento
"overlayfs" (distinto do classico "overlay2"), cujo layout o cAdvisor nao
reconhece. O efeito observado em 2026-09-10 foi que ele coleta as metricas de
cgroup normalmente (19387 series), mas nao consegue associa-las a NOMES de
container: todas saem rotuladas apenas por id="/system.slice/docker-<hash>.scope".
Sem o nome nao ha como distinguir upf1 de upf2, o que inviabiliza a analise por
fatia. Testado com cAdvisor v0.49.1 e v0.52.1, com --docker_only, com o socket
do Docker montado e com metricas de disco desabilitadas — o comportamento
persiste, pois a falha ocorre na criacao do handler do container.

Este exportador le a mesma fonte que o `docker stats` (a API do Docker), que
sempre conhece o nome do container, e portanto independe do driver de
armazenamento. Isso tambem torna a FAIR-5G reproduzivel em ambientes com
qualquer driver, sem exigir configuracao especial do hospedeiro.

Metricas expostas (compativeis com os nomes do cAdvisor onde faz sentido):
  fair5g_container_cpu_percent{name}          uso de CPU em % de um nucleo
  fair5g_container_memory_bytes{name}         memoria residente
  fair5g_container_memory_percent{name}       memoria relativa ao limite
  fair5g_container_net_rx_bytes_total{name}   bytes recebidos (contador)
  fair5g_container_net_tx_bytes_total{name}   bytes transmitidos (contador)
  fair5g_container_up{name}                   1 se em execucao
"""
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import requests_unixsocket

SOCKET = "http+unix://%2Fvar%2Frun%2Fdocker.sock"
INTERVALO = 5

_sessao = requests_unixsocket.Session()
_amostra = {}
_lock = threading.Lock()


def _listar_containers():
    r = _sessao.get(f"{SOCKET}/containers/json", timeout=10)
    r.raise_for_status()
    return [
        (c["Id"], c["Names"][0].lstrip("/"))
        for c in r.json()
    ]


def _stats(cid):
    # stream=false devolve uma unica leitura ja com o delta de CPU calculado
    # entre duas amostras internas do daemon.
    r = _sessao.get(f"{SOCKET}/containers/{cid}/stats?stream=false", timeout=15)
    r.raise_for_status()
    return r.json()


def _cpu_percent(s):
    try:
        cpu = s["cpu_stats"]
        pre = s["precpu_stats"]
        d_total = cpu["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
        d_sys = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        n = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage") or [1])
        if d_sys > 0 and d_total > 0:
            return (d_total / d_sys) * n * 100.0
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    return 0.0


def _memoria(s):
    try:
        m = s["memory_stats"]
        uso = m.get("usage", 0)
        # desconta o page cache, aproximando o working set do cAdvisor
        cache = (m.get("stats") or {}).get("inactive_file", 0)
        return max(uso - cache, 0), m.get("limit", 0)
    except (KeyError, TypeError):
        return 0, 0


def _rede(s):
    rx = tx = 0
    for iface in (s.get("networks") or {}).values():
        rx += iface.get("rx_bytes", 0)
        tx += iface.get("tx_bytes", 0)
    return rx, tx


def _coletar():
    global _amostra
    while True:
        novo = {}
        try:
            for cid, nome in _listar_containers():
                try:
                    s = _stats(cid)
                except Exception:
                    continue
                mem, limite = _memoria(s)
                rx, tx = _rede(s)
                novo[nome] = {
                    "cpu": _cpu_percent(s),
                    "mem": mem,
                    "mem_pct": (mem / limite * 100.0) if limite else 0.0,
                    "rx": rx,
                    "tx": tx,
                }
        except Exception as e:
            print(f"[statsexporter] falha ao listar containers: {e}", flush=True)
        with _lock:
            _amostra = novo
        time.sleep(INTERVALO)


def _render():
    with _lock:
        dados = dict(_amostra)
    linhas = [
        "# HELP fair5g_container_cpu_percent Uso de CPU do container em % de um nucleo",
        "# TYPE fair5g_container_cpu_percent gauge",
    ]
    for nome, v in dados.items():
        linhas.append(f'fair5g_container_cpu_percent{{name="{nome}"}} {v["cpu"]:.4f}')
    linhas += [
        "# HELP fair5g_container_memory_bytes Memoria residente do container",
        "# TYPE fair5g_container_memory_bytes gauge",
    ]
    for nome, v in dados.items():
        linhas.append(f'fair5g_container_memory_bytes{{name="{nome}"}} {v["mem"]}')
    linhas += [
        "# HELP fair5g_container_memory_percent Memoria relativa ao limite do container",
        "# TYPE fair5g_container_memory_percent gauge",
    ]
    for nome, v in dados.items():
        linhas.append(f'fair5g_container_memory_percent{{name="{nome}"}} {v["mem_pct"]:.4f}')
    linhas += [
        "# HELP fair5g_container_net_rx_bytes_total Bytes recebidos pelo container",
        "# TYPE fair5g_container_net_rx_bytes_total counter",
    ]
    for nome, v in dados.items():
        linhas.append(f'fair5g_container_net_rx_bytes_total{{name="{nome}"}} {v["rx"]}')
    linhas += [
        "# HELP fair5g_container_net_tx_bytes_total Bytes transmitidos pelo container",
        "# TYPE fair5g_container_net_tx_bytes_total counter",
    ]
    for nome, v in dados.items():
        linhas.append(f'fair5g_container_net_tx_bytes_total{{name="{nome}"}} {v["tx"]}')
    linhas += [
        "# HELP fair5g_container_up Container em execucao",
        "# TYPE fair5g_container_up gauge",
    ]
    for nome in dados:
        linhas.append(f'fair5g_container_up{{name="{nome}"}} 1')
    return "\n".join(linhas) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urllib.parse.urlparse(self.path).path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        corpo = _render().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=_coletar, daemon=True).start()
    print("[statsexporter] escutando em :9200/metrics", flush=True)
    HTTPServer(("0.0.0.0", 9200), Handler).serve_forever()
