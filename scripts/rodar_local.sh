#!/bin/bash
# Sobe o backend apontado pro Postgres LOCAL (~/atlas_local_db), nunca pra
# produção. O .env do projeto continua intocado (aponta pro Supabase de
# produção) — este script só troca DATABASE_URL na hora, via variável de
# ambiente, que tem prioridade sobre o .env.
#
# Antes de rodar pela primeira vez num dia, garanta que o Postgres local
# está de pé:
#   /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/atlas_local_db/data -l ~/atlas_local_db/logfile -o "-p 5544" start
#
# Pra derrubar depois:
#   /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/atlas_local_db/data stop

set -e
cd "$(dirname "$0")/.."

export DATABASE_URL="postgresql://postgres@localhost:5544/atlas_local"

echo "Backend local -> $DATABASE_URL"
.venv/bin/python -m uvicorn src.app:app --port 8000 --reload
