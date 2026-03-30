#!/bin/bash
echo "=== Atualizando dados WAF Manole ==="
echo "[1/2] Ingerindo dados..."
cd "$(dirname "$0")"
python3 scripts/ingest_data.py
echo "[2/2] Verificando Grafana..."
docker ps | grep grafana-waf || docker-compose up -d
echo "=== Concluido! Acesse http://$(hostname -I | awk '{print $1}'):3000 ==="
