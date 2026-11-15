#!/usr/bin/env bash
# Sincroniza o Open Finance. Usado pelo cron (Linux/macOS).
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python -m financas sincronizar >> sincronizacao.log 2>&1
