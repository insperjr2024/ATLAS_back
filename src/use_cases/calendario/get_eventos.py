"""O calendário geral (§6.5) — bancas + kickoffs + reuniões + entregas.

Recorta por posição, igual ao resto da plataforma (`aplicar_recorte_visao`,
§3): diretor vê tudo (e pode filtrar por frente), gerente só a(s) própria(s)
frente(s), coordenador/consultor só os projetos em que estão alocados.

O §6.5 original dizia "acessível a todos, sem recorte" — decisão revista
depois: só faz sentido ver o portfólio inteiro pra quem já enxerga tudo em
qualquer outra tela (a diretoria). Pra quem está em 2-3 projetos, ver as
bancas/kickoffs/reuniões de todo mundo é ruído, não utilidade.

O que o recorte ainda protege por fora: o DETALHE do projeto
(`GET /projetos/{id}`) continua com `exigir_acesso_ao_projeto`. Por isso a
resposta aqui já traz o nome do projeto — para o front abrir um modal com o
que já tem, em vez de navegar para um 404.
"""

from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.banca_model import BancaModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_model import ReuniaoSemanalModel
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.utils.banca_status import calcular_status_banca


class GetEventosCalendarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, current_user, inicio: date, fim: date, tipos: Optional[List[str]] = None) -> List[dict]:
        eventos: List[dict] = []
        quer = lambda t: not tipos or t in tipos  # noqa: E731

        query_projetos = aplicar_recorte_visao(self.db.query(ProjetoModel), current_user, self.db)
        projetos = {p.id: p for p in query_projetos.all()}
        catalogo = {e.id: e.nome for e in self.catalogo_repository.get_all()}

        escopos = {
            e.id: e
            for e in self.db.query(ProjetoEscopoModel).all()
        }

        def nome_escopo(escopo) -> str:
            if escopo is None:
                return ""
            return escopo.nome_customizado or catalogo.get(escopo.escopo_id, "escopo")

        if quer("banca"):
            # `data_hora` é DateTime: comparar com o `date` puro cortaria as
            # bancas do último dia marcadas depois da meia-noite. Daí o
            # fim do dia explícito.
            fim_do_dia = datetime.combine(fim, time.max)
            bancas = (
                self.db.query(BancaModel)
                .filter(BancaModel.data_hora.isnot(None))
                .filter(BancaModel.data_hora >= datetime.combine(inicio, time.min))
                .filter(BancaModel.data_hora <= fim_do_dia)
                .all()
            )
            # Uma banca pode cobrir vários escopos: o evento é UM só, com os
            # nomes juntos no título.
            escopos_da_banca = BancaEscopoRepository(self.db).get_escopo_ids_por_banca(
                [b.id for b in bancas]
            )
            for b in bancas:
                cobertos = [escopos.get(eid) for eid in escopos_da_banca.get(b.id, [])]
                cobertos = [e for e in cobertos if e]
                # Banca ligada a um projeto fora do recorte: some da lista. A
                # legada sem projeto (`cobertos` vazio) não tem como recortar,
                # então continua visível a todos como sempre foi.
                if cobertos and cobertos[0].projeto_id not in projetos:
                    continue
                projeto = projetos.get(cobertos[0].projeto_id) if cobertos else None
                nomes = " + ".join(nome_escopo(e) for e in cobertos)
                eventos.append(
                    {
                        "tipo": "banca",
                        "data": b.data_hora,
                        # Banca legada não tem projeto — cai no texto livre.
                        "projeto_id": projeto.id if projeto else None,
                        "projeto_nome": projeto.nome if projeto else b.nome_projeto,
                        "titulo": f"Banca: {nomes or b.nome_projeto}",
                        "referencia_id": b.id,
                        "status": calcular_status_banca(b.data_hora, b.realizado_em),
                    }
                )

        if quer("kickoff"):
            for p in projetos.values():
                if p.data_kickoff and inicio <= p.data_kickoff <= fim:
                    eventos.append(
                        {
                            "tipo": "kickoff",
                            "data": p.data_kickoff,
                            "projeto_id": p.id,
                            "projeto_nome": p.nome,
                            "titulo": f"Kickoff: {p.nome}",
                            "referencia_id": p.id,
                            "status": None,
                        }
                    )

        if quer("reuniao"):
            reunioes = (
                self.db.query(ReuniaoSemanalModel)
                .filter(ReuniaoSemanalModel.data_reuniao >= inicio)
                .filter(ReuniaoSemanalModel.data_reuniao <= fim)
                .all()
            )
            for r in reunioes:
                # Fora do recorte de visão: não aparece.
                if r.projeto_id not in projetos:
                    continue
                projeto = projetos[r.projeto_id]
                # O escopo da reunião entra no título: é ele que diz de onde
                # saiu a `data_inicio` de quem começou naquela semana (§5.4).
                sobre = nome_escopo(escopos.get(r.projeto_escopo_id)) if r.projeto_escopo_id else ""
                eventos.append(
                    {
                        "tipo": "reuniao",
                        "data": r.data_reuniao,
                        "projeto_id": r.projeto_id,
                        "projeto_nome": projeto.nome,
                        "titulo": (
                            f"Reunião semanal: {projeto.nome}"
                            + (f" · {sobre}" if sobre else "")
                        ),
                        "referencia_id": r.id,
                        "status": None,
                    }
                )

        if quer("entrega"):
            for escopo in escopos.values():
                # A real quando existe; senão a planejada. Usar as duas
                # duplicaria a pílula no mesmo escopo.
                data = escopo.data_entrega_real or escopo.data_entrega_planejada
                if not data or not (inicio <= data <= fim):
                    continue
                # Fora do recorte de visão: não aparece.
                if escopo.projeto_id not in projetos:
                    continue
                projeto = projetos[escopo.projeto_id]
                eventos.append(
                    {
                        "tipo": "entrega",
                        "data": data,
                        "projeto_id": escopo.projeto_id,
                        "projeto_nome": projeto.nome,
                        "titulo": f"Entrega: {nome_escopo(escopo)}",
                        "referencia_id": escopo.id,
                        "status": "realizada" if escopo.data_entrega_real else "planejada",
                    }
                )

        # "prova" ainda NÃO é gerado aqui de propósito. A tentativa inicial
        # escopava pela frente do PROJETO em que a pessoa está alocada, o que é
        # errado, porque prova é do CURSO da pessoa, não do projeto em que ela
        # trabalha (o exemplo que derrubou isso: um consultor de engenharia
        # alocado num projeto de Business continua tendo prova de engenharia).
        # E `frente` também não é o mesmo que `curso`: uma frente cobre vários
        # cursos. Falta a plataforma ter de onde tirar o curso de cada usuário
        # antes de este bloco voltar a existir.

        eventos.sort(key=lambda e: (str(e["data"]), e["tipo"]))
        return eventos
