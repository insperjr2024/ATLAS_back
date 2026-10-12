"""Lista (e, com --aplicar, apaga) respostas de avaliação periódica fora da
regra de escopo em andamento. Ver `use_cases/desempenho_avaliacao/limpar_periodica.py`.

    uv run python -m scripts.limpar_avaliacoes_periodicas            # só lista
    uv run python -m scripts.limpar_avaliacoes_periodicas --aplicar  # apaga

Usa o banco do DATABASE_URL do ambiente.
"""

import sys

from src.database.database import SessionLocal
from src.use_cases.desempenho_avaliacao.limpar_periodica import LimparAvaliacoesForaDaPeriodicaUseCase


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    db = SessionLocal()
    try:
        linhas = LimparAvaliacoesForaDaPeriodicaUseCase(db).execute(aplicar=aplicar)
    finally:
        db.close()
    for linha in linhas:
        print(f"lote {linha['lote_id']} · {linha['avaliador']} -> {linha['avaliado']} · {linha['motivo']} (avaliação {linha['avaliacao_id']})")
    print(f"\n{len(linhas)} resposta(s) fora da regra" + (" apagada(s)." if aplicar else ". Nada foi apagado (rode com --aplicar)."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
