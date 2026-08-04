"""O calendário geral (§6.5) — bancas + kickoffs + reuniões + entregas.

🔓 **Esta é a única consulta de projeto do sistema SEM recorte de visão**, e
é deliberado: o §6.5 diz "acessível a todos". Todo o resto da plataforma
recorta por posição (F2), então quem revisar este arquivo depois vai sentir
falta do `aplicar_recorte_visao` e ficar tentado a "consertar". Não é bug.

O que o recorte ainda protege: o DETALHE do projeto (`GET /projetos/{id}`)
continua com `exigir_acesso_ao_projeto`. Por isso a resposta aqui já traz o
nome do projeto — para o front abrir um modal com o que já tem, em vez de
navegar para um 404.
"""

from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.banca_model import BancaModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_model import ReuniaoSemanalModel
from src.repositories.escopo_repository import EscopoRepository
from src.utils.banca_status import calcular_status_banca


class GetEventosCalendarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, inicio: date, fim: date, tipos: Optional[List[str]] = None) -> List[dict]:
        eventos: List[dict] = []
        quer = lambda t: not tipos or t in tipos  # noqa: E731

        projetos = {p.id: p for p in self.db.query(ProjetoModel).all()}
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
            for b in bancas:
                escopo = escopos.get(b.projeto_escopo_id)
                projeto = projetos.get(escopo.projeto_id) if escopo else None
                eventos.append(
                    {
                        "tipo": "banca",
                        "data": b.data_hora,
                        # Banca legada não tem projeto — cai no texto livre.
                        "projeto_id": projeto.id if projeto else None,
                        "projeto_nome": projeto.nome if projeto else b.nome_projeto,
                        "titulo": f"Banca — {nome_escopo(escopo) or b.nome_projeto}",
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
                            "titulo": f"Kickoff — {p.nome}",
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
                projeto = projetos.get(r.projeto_id)
                eventos.append(
                    {
                        "tipo": "reuniao",
                        "data": r.data_reuniao,
                        "projeto_id": r.projeto_id,
                        "projeto_nome": projeto.nome if projeto else "",
                        "titulo": f"Reunião semanal — {projeto.nome if projeto else ''}",
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
                projeto = projetos.get(escopo.projeto_id)
                eventos.append(
                    {
                        "tipo": "entrega",
                        "data": data,
                        "projeto_id": escopo.projeto_id,
                        "projeto_nome": projeto.nome if projeto else "",
                        "titulo": f"Entrega — {nome_escopo(escopo)}",
                        "referencia_id": escopo.id,
                        "status": "realizada" if escopo.data_entrega_real else "planejada",
                    }
                )

        eventos.sort(key=lambda e: (str(e["data"]), e["tipo"]))
        return eventos
