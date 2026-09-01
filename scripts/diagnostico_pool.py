"""Reproduz — e mede — a falha "deu erro, mas foi criado".

O sintoma: a pessoa cria uma banca (ou uma tarefa), a tela mostra "O servidor
não conseguiu concluir esta ação" e o registro **está lá** quando ela recarrega.

São duas coisas diferentes, e o script testa as duas separadamente porque
consertar a segunda não faz a primeira deixar de existir.

**1. A janela.** Todo `create` do projeto faz isto:

    db.add(...) -> db.commit()   <- GRAVOU, e devolveu a conexão ao pool
                   db.refresh()  <- precisa pegar OUTRA conexão

Entre as duas linhas a request fica **sem** conexão. Se o pool estiver cheio
nesse instante, o `refresh()` estoura com `TimeoutError`: a linha já está no
banco e a request morre com 500. É literalmente o que a pessoa viu. A janela
dura microssegundos, então o teste **injeta** a falta de conexão exatamente
ali (ver `teste_janela`) em vez de esperar a corrida cair do lado certo.

**2. Quem enchia o pool.** O envio de e-mail segurava uma sessão durante a
chamada ao Resend (timeout de 15s), em 4 threads, contra um pool de 5 conexões
para a instância inteira. Com mais alguém usando a plataforma, o pool zerava.
Este é o teste antes/depois: o `antigo` reproduz o código de antes da correção,
o `novo` chama a função de verdade.

⚠ **Relógio encurtado, mecanismo idêntico.** O pool tem o mesmo tamanho da
produção (POOL_SIZE + MAX_OVERFLOW), mas `pool_timeout` cai de 30s para 3s e
o "envio" dorme 6s em vez dos até 15s do Resend — senão cada rodada levaria
mais de meio minuto. Nada além da escala do tempo muda.

⚠ **Escreve no banco do `DATABASE_URL`.** Cria uma tarefa por rodada (é
justamente o que precisa ser observado) e apaga tudo no fim. Rodar contra o
banco local, nunca contra produção.

    python scripts/diagnostico_pool.py
"""

import os
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import src.database.database as database  # noqa: E402
from src.config.config import get_settings  # noqa: E402
from src.database.database import MAX_OVERFLOW, POOL_SIZE  # noqa: E402
from src.repositories.usuario_repository import UsuarioRepository  # noqa: E402

#: Quanto o "Resend" demora. Maior que POOL_TIMEOUT de propósito: é o que faz
#: a request que espera desistir em vez de só ficar lenta.
ENVIO_SEGUNDOS = 6
POOL_TIMEOUT = 3
#: Uma por thread do `_executor` de `enviar_email_notificacao`.
THREADS_DE_EMAIL = 4
#: ⭐ A quinta conexão. Os 4 e-mails sozinhos deixam uma sobrando, e é
#: justamente ela que qualquer outra pessoa usando a plataforma no mesmo
#: instante ocupa — uma request segura a conexão do início ao fim. Sem isto o
#: script não reproduz nada, e a conclusão errada seria "o pool dá conta".
REQUESTS_CONCORRENTES = 1

CAPACIDADE = POOL_SIZE + MAX_OVERFLOW
TITULO = "DIAGNOSTICO POOL (apagar)"


# ------------------------------------------------------------------ apoio


def _engine_apertado():
    """O pool da produção, com o relógio encurtado."""
    return create_engine(
        get_settings().DATABASE_URL,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_pre_ping=True,
    )


def _contexto(db):
    """Um projeto com board, um diretor e um consultor — o mínimo para o POST."""
    linha = db.execute(
        text(
            "select p.id, c.id from projeto p "
            "join tarefa_coluna c on c.projeto_id = p.id "
            "where p.arquivado_em is null order by p.id, c.ordem limit 1"
        )
    ).first()
    diretor = db.execute(
        text(
            "select id from usuario where posicao = 'diretor_projetos' "
            "and ativo order by id limit 1"
        )
    ).scalar()
    consultor = db.execute(
        text("select id from usuario where ativo order by id limit 1")
    ).scalar()
    return linha, diretor, consultor


def _ler_contexto(Session):
    """Lê os ids ANTES de qualquer carga.

    Separado de `_criar_tarefa` de propósito: com o pool saturado esta leitura
    também estoura, e o teste morreria montando o cenário em vez de medi-lo.
    """
    db = Session()
    try:
        return _contexto(db)
    finally:
        db.close()


def _criar_tarefa(Session, contexto):
    """O POST de verdade, pela API, com o pool trocado pelo apertado."""
    from fastapi.testclient import TestClient

    from src.app import app
    from src.utils.token import criar_access_token

    (projeto_id, coluna_id), diretor_id, consultor_id = contexto

    original = database.SessionLocal
    # `get_db` lê o global do módulo a cada request — trocá-lo põe a API
    # inteira no pool apertado.
    database.SessionLocal = Session
    try:
        cliente = TestClient(app, raise_server_exceptions=False)
        inicio = time.monotonic()
        resposta = cliente.post(
            "/projetos/%s/tarefas" % projeto_id,
            headers={"Authorization": "Bearer %s" % criar_access_token(diretor_id)},
            json={
                "titulo": TITULO,
                "responsavel_id": consultor_id,
                "prazo": "2030-12-31",
                "coluna_id": coluna_id,
            },
        )
        return resposta.status_code, time.monotonic() - inicio, consultor_id
    finally:
        database.SessionLocal = original


def _limpar(Session):
    """Conta o que ficou no banco e apaga. O número é o resultado do teste."""
    db = Session()
    try:
        gravou = db.execute(
            text("select count(*) from tarefa where titulo = :t"), {"t": TITULO}
        ).scalar()
        db.execute(text("delete from tarefa where titulo = :t"), {"t": TITULO})
        db.commit()
        return bool(gravou)
    finally:
        db.close()


# ------------------------------------------------ teste 1: a janela do commit


def teste_janela():
    """Tira a conexão no exato instante do `commit()` e vê onde a request morre.

    ⭐ **A falha é injetada, não sorteada** — e essa é a diferença entre um
    teste e uma tentativa. O `after_commit` arma um gatilho; o primeiro
    `checkout` de conexão depois dele recebe o mesmo `TimeoutError` que o pool
    cheio devolveria. Em produção quem arma é outra pessoa usando a plataforma
    no milissegundo errado.

    O que está sendo verificado não é o pool (isso é o teste 2) — é a
    **consequência**: se a conexão falta logo depois do `commit()`, o que
    acontece com a linha que acabou de ser gravada e com a resposta HTTP.
    """
    from sqlalchemy import exc as sa_exc

    engine = _engine_apertado()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    contexto = _ler_contexto(Session)
    armado = {"sim": False, "disparou": False}

    def armar(_sessao):
        armado["sim"] = True

    def negar_conexao(*_args):
        if not armado["sim"] or armado["disparou"]:
            return
        armado["disparou"] = True
        armado["sim"] = False
        raise sa_exc.TimeoutError(
            "QueuePool limit of size %s overflow %s reached, connection timed "
            "out, timeout %s.00 (injetado por diagnostico_pool)"
            % (POOL_SIZE, MAX_OVERFLOW, POOL_TIMEOUT)
        )

    event.listen(Session, "after_commit", armar)
    event.listen(engine, "checkout", negar_conexao)
    try:
        status, segundos, _ = _criar_tarefa(Session, contexto)
    finally:
        event.remove(Session, "after_commit", armar)
        event.remove(engine, "checkout", negar_conexao)

    gravou = _limpar(Session)
    engine.dispose()
    return {
        "nome": "conexao indisponivel logo apos o commit",
        "status": status,
        "gravou": gravou,
        "segundos": segundos,
        "disparou": armado["disparou"],
    }


# ------------------------------------------- teste 2: antes/depois do e-mail


def _dorme_mandando_email():
    time.sleep(ENVIO_SEGUNDOS)


class SenderLento:
    """No lugar do Resend: mesma duração, sem mandar e-mail de verdade."""

    def enviar(self, destino, assunto, corpo_texto, corpo_html):
        _dorme_mandando_email()


def _envio_antigo(usuario_id, Session):
    """O código de antes da correção: uma sessão aberta durante todo o envio."""
    db = Session()
    try:
        usuario = UsuarioRepository(db).get_by_id(usuario_id)
        if usuario is None or not usuario.ativo:
            return
        _dorme_mandando_email()
    finally:
        db.close()


def _envio_novo(usuario_id, Session):
    """O código de agora — o de verdade, importado do módulo."""
    from src.use_cases.notificacao import enviar_email_notificacao

    enviar_email_notificacao.enviar(
        notificacao_id=-1,  # inexistente: o carimbo vira no-op, o resto roda igual
        usuario_id=usuario_id,
        tipo="banca_remarcada",
        titulo="Diagnóstico de pool",
        corpo=None,
        rota=None,
        sender=SenderLento(),
        session_factory=Session,
    )


def _request_concorrente(_usuario_id, Session):
    """Outra pessoa usando a plataforma no mesmo instante.

    Não muda entre os dois modos: uma request sempre segura a conexão dela
    enquanto responde. É o pano de fundo contra o qual o envio é medido.
    """
    db = Session()
    try:
        db.execute(text("select count(*) from projeto"))
        time.sleep(ENVIO_SEGUNDOS)
    finally:
        db.close()


def teste_carga(nome, envio):
    """Manda e-mail em 4 threads e tenta criar uma tarefa no meio."""
    from src.use_cases.notificacao import enviar_email_notificacao

    engine = _engine_apertado()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    chave_original = enviar_email_notificacao.get_settings
    enviar_email_notificacao.get_settings = lambda: type(
        "S", (), {"RESEND_API_KEY": "diagnostico", "FRONTEND_URL": "http://localhost:5173"}
    )
    try:
        contexto = _ler_contexto(Session)
        consultor_id = contexto[2]

        threads = [
            threading.Thread(target=envio, args=(consultor_id, Session), daemon=True)
            for _ in range(THREADS_DE_EMAIL)
        ] + [
            threading.Thread(
                target=_request_concorrente, args=(consultor_id, Session), daemon=True
            )
            for _ in range(REQUESTS_CONCORRENTES)
        ]
        for t in threads:
            t.start()
        time.sleep(1.5)  # tempo de todas chegarem no envio

        status, segundos, _ = _criar_tarefa(Session, contexto)
        for t in threads:
            t.join()

        gravou = _limpar(Session)
        return {"nome": nome, "status": status, "gravou": gravou, "segundos": segundos}
    finally:
        enviar_email_notificacao.get_settings = chave_original
        engine.dispose()


# ------------------------------------------------------------------ saída


def _linha(r):
    return "%-46s %6s %8s %7.1fs" % (
        r["nome"],
        r["status"],
        "SIM" if r["gravou"] else "nao",
        r["segundos"],
    )


def main():
    print("Pool: %s + %s overflow (%s conexoes), timeout %ss" % (
        POOL_SIZE, MAX_OVERFLOW, CAPACIDADE, POOL_TIMEOUT))
    print()

    print("1) A JANELA — o sintoma que apareceu na tela")
    print("%-46s %6s %8s %8s" % ("", "POST", "gravou", "tempo"))
    janela = teste_janela()
    print(_linha(janela))
    if janela["status"] >= 500 and janela["gravou"]:
        print("   ok   500 na tela e a linha no banco: e exatamente o relato.")
    else:
        print("   --   nao reproduziu (gatilho disparou: %s)." % janela["disparou"])
    print()

    print("2) A CAUSA — o e-mail segurando conexao, antes e depois")
    print("%-46s %6s %8s %8s" % ("", "POST", "gravou", "tempo"))
    antigo = teste_carga("antigo (sessao aberta durante o envio)", _envio_antigo)
    print(_linha(antigo))
    novo = teste_carga("novo   (sessao fechada antes do envio)", _envio_novo)
    print(_linha(novo))
    print()

    if antigo["status"] >= 500:
        print("   ok   com o codigo antigo o pool zera e o POST nao passa.")
    else:
        print("   --   o antigo passou nesta rodada; aumente ENVIO_SEGUNDOS.")
    if novo["status"] < 400:
        print("   ok   com o codigo novo o mesmo POST passa, mesma carga.")
    else:
        print("   FALHOU: o novo tambem quebrou.")
        sys.exit(1)

    print()
    print("A janela do teste 1 continua existindo: o que a correcao tira e a")
    print("saturacao que a torna alcancavel. Fechar a janela de vez exige um")
    print("commit unico por use case (ver o comentario em base_repository.py).")


if __name__ == "__main__":
    main()
