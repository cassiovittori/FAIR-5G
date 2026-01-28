#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/configs/network-slicing"
OUT_DIR="$REPO_ROOT/configs/runtime"

mkdir -p "$OUT_DIR"

GNB_IP="$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gnb)"
if [[ -z "$GNB_IP" ]]; then
  echo "[render] Não consegui obter IP do container gnb."
  exit 1
fi

echo "[render] gnb ip: $GNB_IP"

render_one () {
  local src="$1"
  local out="$2"

  # substitui bloco gnbSearchList por um único item (ip do gnb)
  awk -v ip="$GNB_IP" '
    BEGIN {inlist=0}
    /^gnbSearchList:/ {
      print "gnbSearchList:"
      print "  - " ip
      inlist=1
      next
    }
    inlist==1 {
      # pula linhas de lista (começam com espaço + "-")
      if ($0 ~ /^[[:space:]]*-[[:space:]]*/) next
      # se acabou a lista, volta a imprimir normalmente
      inlist=0
    }
    {print}
  ' "$src" > "$out"
}

render_one "$SRC_DIR/ue1.yaml" "$OUT_DIR/ue1.yaml"
render_one "$SRC_DIR/ue2.yaml" "$OUT_DIR/ue2.yaml"

echo "[render] gerado: $OUT_DIR/ue1.yaml"
echo "[render] gerado: $OUT_DIR/ue2.yaml"
