#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$REPO_ROOT/configs/runtime"

shopt -s nullglob
ue_files=("$RUNTIME_DIR"/ue*.yaml)
if [[ ${#ue_files[@]} -eq 0 ]]; then
  echo "[render] Nenhum ue*.yaml em $RUNTIME_DIR — rode scripts/render_slice_configs.py primeiro."
  exit 1
fi

GNB_IP="$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gnb)"
if [[ -z "$GNB_IP" ]]; then
  echo "[render] Não consegui obter IP do container gnb."
  exit 1
fi

echo "[render] gnb ip: $GNB_IP"

patch_gnb_search_list () {
  local target="$1"
  local tmp="${target}.tmp"

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
  ' "$target" > "$tmp"
  mv "$tmp" "$target"
}

for f in "${ue_files[@]}"; do
  patch_gnb_search_list "$f"
  echo "[render] atualizado: $f"
done
