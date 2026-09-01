"""Confere o calendário base dos escopos, contra o banco de verdade.

Roda DEPOIS de `alembic upgrade head`. Não escreve nada — só lê e compara.

São três checagens, e a do meio é a que teria pegado o bug original:

1. **Carga** — todo escopo aponta para um calendário que EXISTE na frente dele.
   Um rótulo órfão não daria erro em lugar nenhum: simplesmente não casaria com
   dia algum, e o escopo passaria a contar a semana de avaliação de ninguém.

2. ⭐ **Coerência do payload** — a faixa que o cronograma desenha
   (`faixas_derivadas[tipo=escopo].fim`) tem de bater com o número que a tabela
   de escopos mostra ao lado dela (`escopos[].fim_janela`). Eram duas
   contas com calendários diferentes, e a faixa fechava até 12 dias antes.

3. **Isolamento** — o calendário de um escopo não inclui dia de outra frente.
   É o que prova que a escolha realmente escolhe, em vez de somar tudo.

Uso:  python scripts/conferir_calendario.py
"""

import os
import sys

# O console do Windows abre em cp1252 e engasga com acento — e um script de
# conferência que quebra na hora de imprimir "está tudo certo" é pior do que
# não existir.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.database.database import SessionLocal  # noqa: E402
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository  # noqa: E402
from src.repositories.frente_repository import FrenteRepository  # noqa: E402
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository  # noqa: E402
from src.repositories.projeto_repository import ProjetoRepository  # noqa: E402
from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase  # noqa: E402
from src.utils.calendario_variante import do_escopo  # noqa: E402


def main():
    db = SessionLocal()
    problemas = 0

    frentes = {f.id: f for f in FrenteRepository(db).get_all()}
    registros = DiaNaoLetivoRepository(db).get_all()
    semestre_ids = {d.semestre_id for d in registros}

    print("=" * 74)
    print("1 · CARGA — todo escopo aponta para um calendário que existe")
    print("=" * 74)
    for projeto in ProjetoRepository(db).get_all():
        for escopo in ProjetoEscopoRepository(db).get_by_projeto(projeto.id):
            frente = frentes.get(escopo.frente_id)
            nomes = set()
            for semestre_id in semestre_ids:
                nomes |= set(
                    DiaNaoLetivoRepository(db).listar_variantes(semestre_id, escopo.frente_id)
                )
            valido = escopo.calendario in nomes if nomes else escopo.calendario is None
            if not valido:
                problemas += 1
                print(
                    f"  FALHA projeto {projeto.id} escopo {escopo.id} "
                    f"({frente.nome if frente else '?'}): calendário "
                    f"{escopo.calendario!r} não existe na frente "
                    f"(disponíveis: {sorted(nomes) or ['(único)']})"
                )
    if problemas == 0:
        print("  ok   todos os escopos apontam para um calendário existente")

    print()
    print("=" * 74)
    print("2 · COERÊNCIA — a faixa desenhada bate com o número da tabela")
    print("=" * 74)
    divergentes = 0
    for projeto in ProjetoRepository(db).get_all():
        dados = GetCronogramaUseCase(db).execute(projeto.id)
        if not dados:
            continue
        da_tabela = {e["id"]: e.get("fim_janela") for e in dados["escopos"]}
        for faixa in dados["faixas_derivadas"]:
            if faixa["tipo"] != "escopo":
                continue
            escopo_id = faixa["projeto_escopo_id"]
            esperado = da_tabela.get(escopo_id)
            if esperado != faixa["fim"]:
                divergentes += 1
                problemas += 1
                print(
                    f"  FALHA projeto {projeto.id} escopo {escopo_id}: "
                    f"faixa termina {faixa['fim']}, tabela diz {esperado}"
                )
    if divergentes == 0:
        print("  ok   faixa e tabela concordam em todos os escopos")

    print()
    print("=" * 74)
    print("3 · ISOLAMENTO — o calendário de um escopo não tem dia de outra frente")
    print("=" * 74)
    vazados = 0
    for projeto in ProjetoRepository(db).get_all():
        for escopo in ProjetoEscopoRepository(db).get_by_projeto(projeto.id):
            for dia in do_escopo(registros, escopo):
                de_outra_frente = dia.frente_id is not None and dia.frente_id != escopo.frente_id
                de_outro_curso = (
                    dia.frente_id == escopo.frente_id and dia.variante != escopo.calendario
                )
                if de_outra_frente or de_outro_curso:
                    vazados += 1
                    problemas += 1
                    print(
                        f"  FALHA projeto {projeto.id} escopo {escopo.id}: {dia.data} "
                        f"é de frente={dia.frente_id} variante={dia.variante!r}"
                    )
    if vazados == 0:
        print("  ok   nenhum escopo enxerga dia de outra frente ou de outro curso")

    print()
    print("=" * 74)
    print("FIM DA JANELA DE CADA ESCOPO — para conferir na tela")
    print("=" * 74)
    print(f"{'proj':>5} {'escopo':>7} {'frente':>10} {'calendário':>26} {'fim':>12}")
    print("-" * 74)
    for projeto in ProjetoRepository(db).get_all():
        dados = GetCronogramaUseCase(db).execute(projeto.id)
        if not dados:
            continue
        for e in dados["escopos"]:
            if not e.get("fim_janela"):
                continue
            frente = frentes.get(e["frente_id"])
            print(
                f"{projeto.id:>5} {e['id']:>7} {(frente.nome if frente else '?'):>10} "
                f"{str(e.get('calendario') or '(único da frente)'):>26} "
                f"{str(e['fim_janela']):>12}"
            )

    db.close()
    print()
    if problemas:
        print(f"FALHOU: {problemas} problema(s) encontrado(s).")
        sys.exit(1)
    print("ok   Tudo certo.")


if __name__ == "__main__":
    main()
