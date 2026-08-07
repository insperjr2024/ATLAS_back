"""Gera VOLUME para testar o monitoramento com um núcleo cheio.

O `seed.py` cria um núcleo pequeno — 8 pessoas e alguns projetos —, bom para
ver cada caso de regra isolado e ruim para responder "como esta tela fica com
60 consultores?". Cards que cabem numa lista de 7 linhas viram parede de texto
com 60, e gargalo só aparece quando há gente suficiente para haver fila.

⭐ **A distribuição de carga é o ponto, não a quantidade.** Um lote em que todo
consultor tem 2 projetos deixa a capacidade zerada em todas as frentes e o card
não mostra nada. Aqui a carga é proposital:

    ~35% com 1 projeto ..... sobra 1 vaga  -> capacidade > 0 na tela
    ~45% com 2 projetos .... no limite     -> "Quantidade ideal"
    ~20% com 3 projetos .... acima         -> "Carga alta" e demanda alta

Business fica com mais gente que as outras, como acontece na empresa.

Tudo que ele cria leva o prefixo `VOL-` (projetos) ou o domínio `@volume.local`
(pessoas). O `--limpar` apaga só o que tem essas marcas — nada do `seed.py` é
tocado.

⚠ **Não é idempotente, e por isso ele se recusa a rodar duas vezes.** A carga
de cada pessoa é sorteada e depois descontada do que ela já tem; numa segunda
passada o desconto muda e sai um punhado de projetos novos em cima dos
anteriores. Rodar `--limpar` antes de gerar de novo é o caminho, e o script
avisa em vez de deixar o banco crescer sem ninguém notar.

    venv/Scripts/python -m scripts.seed_volume
    venv/Scripts/python -m scripts.seed_volume --limpar
"""

import random
import sys
from datetime import date, datetime, time, timedelta

from sqlalchemy import func

from src.database.database import Base, SessionLocal
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_model import BancaModel
from src.models.cargo_model import CargoModel
from src.models.escopo_model import EscopoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.utils.senha import hash_senha

MARCA_PROJETO = "VOL-"
DOMINIO = "@volume.local"
SENHA = "Volume@123"

TOTAL_CONSULTORES = 60
TOTAL_COORDENADORES = 16

#: Quantos projetos cada fatia de consultor carrega. As chaves somam 1.0.
#: Sem a fatia de 1 projeto, a capacidade de consultor fica zero em toda frente
#: e o card novo não teria o que mostrar.
CARGA_CONSULTOR = [(1, 0.35), (2, 0.45), (3, 0.20)]

#: Business concentra mais gente. Os pesos são relativos, não precisam somar 1.
PESO_FRENTE = {"Business": 0.45, "Tech": 0.27, "Direito": 0.16, "Engenharia de Processos": 0.12}

#: Fração dos projetos que nasce atrasada, e como.
FATIA_ATRASADA = 0.35

#: Quantos meses de entregas passadas gerar. Casa com `MESES_DE_TENDENCIA` do
#: monitoramento: menos que isso deixa as primeiras barras do gráfico vazias e
#: dá a impressão de que o núcleo não entregava nada até pouco tempo atrás.
MESES_DE_HISTORICO = 6

#: Como o quadro de tarefas de cada projeto nasce. As frações somam 1.0.
#:
#: ⚠ **Sem tarefa nenhuma, TODO projeto do lote aparecia como "nunca recebeu
#: tarefa"** na aba de Execução — 43 das 50 linhas com problema, o que não é um
#: núcleo, é um gerador incompleto. A distribuição abaixo deixa a maioria com
#: quadro saudável e reserva os dois casos ruins para a minoria, que é o que
#: torna a tela útil para avaliar decisão de layout.
QUADRO = [
    ("saudavel", 0.60),   # tarefas ativas, prazos no futuro
    ("com_vencida", 0.22),  # tarefas ativas, algumas com prazo estourado
    ("zerado", 0.10),     # tudo em coluna que encerra -> "quadro zerado"
    ("sem_tarefa", 0.08),  # nunca recebeu tarefa
]

#: As colunas do kanban nascem POR PROJETO (a diretoria edita dentro de cada
#: um), então o lote precisa criar as suas. (chave, nome, cor, ordem, encerra)
COLUNAS = [
    ("a_fazer", "A fazer", "#9CA3AF", 0, False),
    ("em_andamento", "Em andamento", "#3B82F6", 1, False),
    ("validacao", "Validação", "#F59E0B", 2, False),
    ("concluido", "Concluído", "#10B981", 3, True),
    ("cancelado", "Cancelado", "#EF4444", 4, True),
]

TITULOS_TAREFA = [
    "Levantar dados do cliente", "Montar apresentação", "Rodar entrevistas",
    "Consolidar planilha", "Revisar escopo", "Preparar material da banca",
    "Validar hipóteses", "Escrever relatório", "Ajustar cronograma",
    "Mapear concorrentes", "Fechar diagnóstico", "Alinhar com o cliente",
]

PRIMEIROS = [
    "Alice", "Bento", "Carla", "Davi", "Elisa", "Felipe", "Gabriela", "Heitor",
    "Isabel", "Joana", "Kaio", "Larissa", "Murilo", "Natália", "Otávio", "Paula",
    "Quésia", "Renato", "Sabrina", "Tiago", "Ursula", "Vinícius", "Yara", "Zeca",
    "Aline", "Breno", "Cecília", "Diego", "Elton", "Fabiana", "Gustavo", "Helena",
]
ULTIMOS = [
    "Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Fonseca", "Gomes",
    "Henrique", "Ibrahim", "Ju­queira", "Klein", "Lacerda", "Moraes", "Nunes",
    "Oliveira", "Pacheco", "Queiroz", "Ramires", "Siqueira", "Teixeira",
]
CLIENTES = [
    "Mercado Vila Nova", "Clínica Bem Viver", "Transportes Andrade", "Café Girassol",
    "Óticas Central", "Academia Impulso", "Escola Semear", "Pet Shop Amigo",
    "Construtora Horizonte", "Livraria Página", "Studio Vertex", "Padaria Aurora",
    "Auto Peças Rota", "Floricultura Jardim", "Marcenaria Cedro", "Gráfica Rápida",
]


def nomes_unicos(quantidade, usados, rnd):
    """Combina nome e sobrenome sem repetir — o nome vira o identificador
    visual na tela, e dois iguais confundem a leitura das tabelas."""
    saida = []
    while len(saida) < quantidade:
        nome = f"{rnd.choice(PRIMEIROS)} {rnd.choice(ULTIMOS)}"
        if nome not in usados:
            usados.add(nome)
            saida.append(nome)
    return saida


def sortear_frente(frentes, rnd):
    return rnd.choices(list(frentes), weights=[PESO_FRENTE[f] for f in frentes])[0]


def carga_sorteada(rnd):
    return rnd.choices(
        [q for q, _ in CARGA_CONSULTOR], weights=[p for _, p in CARGA_CONSULTOR]
    )[0]


def limpar(db):
    """Apaga só o que tem as marcas. Ordem inversa das dependências."""
    projetos = db.query(ProjetoModel).filter(ProjetoModel.nome.like(f"{MARCA_PROJETO}%")).all()
    ids = [p.id for p in projetos]
    if ids:
        escopos = db.query(ProjetoEscopoModel).filter(ProjetoEscopoModel.projeto_id.in_(ids)).all()
        escopo_ids = [e.id for e in escopos]
        if escopo_ids:
            vinculos = (
                db.query(BancaEscopoModel)
                .filter(BancaEscopoModel.projeto_escopo_id.in_(escopo_ids))
                .all()
            )
            banca_ids = {v.banca_id for v in vinculos}
            for v in vinculos:
                db.delete(v)
            db.flush()
            for b in db.query(BancaModel).filter(BancaModel.id.in_(banca_ids)).all():
                db.delete(b)
        # Tarefa aponta para coluna, então sai antes dela.
        for t in db.query(TarefaModel).filter(TarefaModel.projeto_id.in_(ids)).all():
            db.delete(t)
        db.flush()
        for c in db.query(TarefaColunaModel).filter(TarefaColunaModel.projeto_id.in_(ids)).all():
            db.delete(c)
        for e in escopos:
            db.delete(e)
        db.flush()

        # ⭐ **Quem mais aponta para `projeto` é DESCOBERTO, não listado.**
        # Escrever a lista à mão envelhece: já quebrou duas vezes, primeiro com
        # `tarefa_coluna` e depois com `projeto_status_historico`, que veio do
        # agendador de status da `main`. Varrer o metadata pega também a próxima
        # tabela que alguém criar.
        for tabela in reversed(Base.metadata.sorted_tables):
            for fk in tabela.foreign_keys:
                if fk.column.table.name == "projeto":
                    db.execute(
                        tabela.delete().where(tabela.c[fk.parent.name].in_(ids))
                    )
                    break

        # ⚠ `flush` obrigatório antes de apagar os projetos: sem `relationship`
        # declarada, o SQLAlchemy não deduz a ordem e pode mandar o DELETE do
        # projeto primeiro — a FK barra e a limpeza falha no meio.
        db.flush()
        for p in projetos:
            db.delete(p)
        db.flush()

    pessoas = db.query(UsuarioModel).filter(UsuarioModel.email_insper.like(f"%{DOMINIO}")).all()
    pids = [u.id for u in pessoas]
    if pids:
        # Mesma varredura de metadata, com uma distinção que importa: nem toda
        # referência a usuário é POSSE.
        #
        #   coluna obrigatória  -> a linha existe por causa da pessoa
        #                          (vínculo com frente, participação em projeto)
        #                          e vai embora com ela.
        #   coluna opcional     -> a linha é de outra coisa e só REGISTRA quem
        #                          mexeu (`alterado_por`, `criado_por`). Apagar
        #                          levaria junto histórico de projeto que não é
        #                          do lote; então some só a autoria.
        for tabela in reversed(Base.metadata.sorted_tables):
            if tabela.name == "usuario":
                continue
            for fk in tabela.foreign_keys:
                if fk.column.table.name != "usuario":
                    continue
                coluna = tabela.c[fk.parent.name]
                if coluna.nullable:
                    db.execute(tabela.update().where(coluna.in_(pids)).values({coluna: None}))
                else:
                    db.execute(tabela.delete().where(coluna.in_(pids)))
        db.flush()
        for u in pessoas:
            db.delete(u)

    db.commit()
    print(f"removidos: {len(projetos)} projetos e {len(pessoas)} pessoas do lote de volume")


def gerar(db):
    rnd = random.Random(20260806)  # fixo: com o banco limpo, sai sempre igual
    hoje = date.today()

    # Ver o aviso no topo do arquivo: uma segunda passada não repete o cenário,
    # ela SOMA um lote menor por cima. Melhor barrar do que deixar o banco
    # crescer a cada execução distraída.
    ja_existem = (
        db.query(ProjetoModel).filter(ProjetoModel.nome.like(f"{MARCA_PROJETO}%")).count()
    )
    if ja_existem:
        sys.exit(
            f"Já existem {ja_existem} projetos do lote de volume.\n"
            "Rode `--limpar` antes de gerar de novo."
        )

    frentes = {f.nome: f for f in db.query(FrenteModel).all()}
    if not frentes:
        sys.exit("Rode o seed.py antes: não há frentes cadastradas.")
    catalogo = db.query(EscopoModel).all()
    if not catalogo:
        sys.exit("Rode o seed.py antes: não há escopos no catálogo.")

    cargo_membro = db.query(CargoModel).filter(CargoModel.nome == "Membro").first()
    cargo_coord = (
        db.query(CargoModel).filter(CargoModel.nome == "Coordenador").first() or cargo_membro
    )
    criador = db.query(UsuarioModel).filter(UsuarioModel.posicao == "diretor").first()
    if not criador:
        sys.exit("Rode o seed.py antes: não há diretor para constar como criador.")

    existentes = {u.nome for u in db.query(UsuarioModel).all()}

    def garantir_pessoas(posicao, alvo, cargo):
        atuais = (
            db.query(UsuarioModel)
            .filter(UsuarioModel.posicao == posicao, UsuarioModel.status == "ativo")
            .all()
        )
        faltam = max(0, alvo - len(atuais))
        novos = []
        for i, nome in enumerate(nomes_unicos(faltam, existentes, rnd)):
            frente = sortear_frente(frentes, rnd)
            u = UsuarioModel(
                nome=nome,
                email_insper=f"{posicao[:4]}{i:03d}{DOMINIO}",
                senha_hash=hash_senha(SENHA),
                cargo_id=cargo.id if cargo else None,
                posicao=posicao,
                status="ativo",
                ativo=True,
            )
            db.add(u)
            db.flush()
            db.add(UsuarioFrenteModel(usuario_id=u.id, frente_id=frentes[frente].id))
            novos.append(u)
        return atuais + novos

    consultores = garantir_pessoas("consultor", TOTAL_CONSULTORES, cargo_membro)
    coordenadores = garantir_pessoas("coordenador", TOTAL_COORDENADORES, cargo_coord)
    db.flush()

    # ⚠ Desconta o que a pessoa JÁ carrega. Sem isto, os consultores que o
    # seed.py criou (e que já estão em projetos) recebem a cota inteira por
    # cima e terminam com 7 ou 8 projetos — número que não existe na vida real
    # e que contradiz a distribuição prometida no topo deste arquivo.
    carga_atual = dict(
        db.query(ProjetoMembroModel.usuario_id, func.count(ProjetoMembroModel.id))
        .join(ProjetoModel, ProjetoModel.id == ProjetoMembroModel.projeto_id)
        .filter(
            ProjetoMembroModel.papel == "consultor",
            ProjetoMembroModel.saiu_em.is_(None),
            ProjetoModel.status != "finalizado",
            ProjetoModel.arquivado_em.is_(None),
        )
        .group_by(ProjetoMembroModel.usuario_id)
        .all()
    )

    # Cada consultor entra numa fila com tantas entradas quantos projetos ainda
    # FALTAM para ele. Embaralhar e fatiar monta as equipes sem que ninguém
    # apareça duas vezes no mesmo projeto.
    fila = []
    for c in consultores:
        faltam = carga_sorteada(rnd) - carga_atual.get(c.id, 0)
        fila += [c.id] * max(0, faltam)
    rnd.shuffle(fila)

    equipes = []
    i = 0
    while i < len(fila):
        equipe = []
        for cid in fila[i : i + 3]:
            if cid not in equipe:
                equipe.append(cid)
        if equipe:
            equipes.append(equipe)
        i += 2 if len(equipe) < 3 else 3

    carga_coord = {c.id: 0 for c in coordenadores}
    criados = 0

    for n, equipe in enumerate(equipes):
        # O menos carregado pega o próximo — espalha em vez de lotar os
        # primeiros, e deixa alguns com vaga livre para a capacidade não zerar.
        coord_id = min(carga_coord, key=lambda k: carga_coord[k])
        carga_coord[coord_id] += 1

        atrasado = rnd.random() < FATIA_ATRASADA
        frente = sortear_frente(frentes, rnd)
        kickoff = hoje - timedelta(days=rnd.randint(20, 90))

        projeto = ProjetoModel(
            nome=f"{MARCA_PROJETO}{n + 1:03d} {rnd.choice(CLIENTES)}",
            cliente=rnd.choice(CLIENTES),
            descricao="Projeto gerado para teste de volume.",
            status=rnd.choice(["em_andamento", "em_andamento", "validacao_bancas", "ambientacao"]),
            dias_ambientacao=5,
            data_kickoff=kickoff,
            dia_reuniao_padrao=rnd.randint(1, 5),
            criado_por=criador.id,
        )
        db.add(projeto)
        db.flush()
        db.add(ProjetoFrenteModel(projeto_id=projeto.id, frente_id=frentes[frente].id))
        db.add(
            ProjetoMembroModel(
                projeto_id=projeto.id, usuario_id=coord_id, papel="coordenador", entrou_em=kickoff
            )
        )
        for cid in equipe:
            db.add(
                ProjetoMembroModel(
                    projeto_id=projeto.id, usuario_id=cid, papel="consultor", entrou_em=kickoff
                )
            )

        # ⭐ Escopos ANTERIORES já entregues. Sem eles o banco não tinha uma
        # única `data_entrega_real`, e dois cards da Visão geral ficavam vazios
        # sem que ninguém soubesse se era falta de dado ou defeito: a tendência
        # de entregas (que agora abre 6 meses) e o tempo parado entre escopos.
        #
        # As datas se espalham pelos últimos MESES_DE_HISTORICO meses para o
        # gráfico mensal ter barra em todos eles, e não um pico solto no fim.
        entregues = rnd.randint(0, 2)
        for k in range(entregues):
            dias_atras = rnd.randint(20, MESES_DE_HISTORICO * 30)
            entrega = hoje - timedelta(days=dias_atras)
            planejada = entrega - timedelta(days=rnd.randint(-8, 8))  # alguns atrasados
            db.add(
                ProjetoEscopoModel(
                    projeto_id=projeto.id,
                    escopo_id=rnd.choice(catalogo).id,
                    frente_id=frentes[frente].id,
                    dias_uteis_vendidos=rnd.choice([10, 15, 20]),
                    status="entregue",
                    data_inicio=entrega - timedelta(days=rnd.randint(25, 60)),
                    data_entrega_planejada=planejada,
                    data_entrega_real=entrega,
                )
            )

        # TEMPO PARADO: escopo entregue + próximo na fila SEM `data_inicio` e
        # nenhum rodando. É a combinação exata que `_tempo_parado` procura —
        # com um escopo em curso o projeto não conta como parado, e é por isso
        # que o card vivia vazio.
        parado = entregues > 0 and rnd.random() < 0.25
        escopo = ProjetoEscopoModel(
            projeto_id=projeto.id,
            escopo_id=rnd.choice(catalogo).id,
            frente_id=frentes[frente].id,
            dias_uteis_vendidos=rnd.choice([10, 15, 20, 25]),
            status="nao_iniciado" if parado else "em_andamento",
            data_inicio=None if parado else kickoff + timedelta(days=5),
            # Atraso de ENTREGA: planejada no passado e sem entrega real.
            data_entrega_planejada=(
                hoje - timedelta(days=rnd.randint(1, 25))
                if atrasado
                else hoje + timedelta(days=rnd.randint(5, 40))
            ),
        )
        db.add(escopo)
        db.flush()

        # Atraso de BANCA: data passada e `realizado_em` vazio — é o pilar do
        # §7.4. Metade dos atrasados leva os dois motivos, para a tela ter
        # projeto com mais de uma causa.
        if atrasado and rnd.random() < 0.5:
            quando = datetime.combine(hoje - timedelta(days=rnd.randint(2, 20)), time(14, 0))
            realizado = None
        else:
            quando = datetime.combine(hoje + timedelta(days=rnd.randint(2, 20)), time(14, 0))
            realizado = None
        banca = BancaModel(
            nome_projeto=projeto.nome,
            escopo_id=escopo.escopo_id,
            coordenador_id=coord_id,
            data_hora=quando,
            realizado_em=realizado,
        )
        db.add(banca)
        db.flush()
        db.add(BancaEscopoModel(banca_id=banca.id, projeto_escopo_id=escopo.id))

        # --- quadro de tarefas -------------------------------------------
        colunas = {}
        for chave, nome_col, cor, ordem, encerra in COLUNAS:
            c = TarefaColunaModel(
                projeto_id=projeto.id,
                chave=chave,
                nome=nome_col,
                cor=cor,
                ordem=ordem,
                encerra_tarefa=encerra,
            )
            db.add(c)
            colunas[chave] = c
        db.flush()

        perfil = rnd.choices([p for p, _ in QUADRO], weights=[w for _, w in QUADRO])[0]
        if perfil != "sem_tarefa":
            abertas = ["a_fazer", "em_andamento", "validacao"]
            for _ in range(rnd.randint(3, 7)):
                # "Zerado" é o projeto que terminou o lote e não recebeu o
                # próximo: tudo em coluna que encerra, nada ativo.
                chave = (
                    rnd.choice(["concluido", "cancelado"])
                    if perfil == "zerado"
                    else rnd.choice(abertas)
                )
                vencida = perfil == "com_vencida" and rnd.random() < 0.4
                prazo = hoje + timedelta(days=rnd.randint(2, 21))
                if vencida:
                    prazo = hoje - timedelta(days=rnd.randint(1, 12))
                criada = hoje - timedelta(days=rnd.randint(1, 30))
                db.add(
                    TarefaModel(
                        projeto_id=projeto.id,
                        titulo=rnd.choice(TITULOS_TAREFA),
                        responsavel_id=rnd.choice(equipe),
                        prazo=prazo,
                        coluna_id=colunas[chave].id,
                        criado_por=coord_id,
                        criado_em=datetime.combine(criada, time(9, 0)),
                        movida_em=datetime.combine(criada, time(9, 0)),
                    )
                )

        # --- reuniões ------------------------------------------------------
        # A maioria dos projetos se reuniu nesta semana; alguns não, que é o
        # que a coluna "não distribuiu na semana" precisa mostrar.
        if rnd.random() < 0.75:
            segunda = hoje - timedelta(days=hoje.weekday())
            db.add(
                ReuniaoSemanalModel(
                    projeto_id=projeto.id,
                    data_reuniao=segunda + timedelta(days=rnd.randint(0, 4)),
                    registrado_por=coord_id,
                )
            )

        criados += 1

    db.commit()
    print(f"consultores ativos: {len(consultores)}")
    print(f"coordenadores ativos: {len(coordenadores)}")
    print(f"projetos criados: {criados}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        if "--limpar" in sys.argv:
            limpar(db)
        else:
            gerar(db)
    finally:
        db.close()
