"""⭐ A fila da diretoria — tudo que espera uma decisão dela, num lugar só.

O problema que isto resolve não é de dado, é de descoberta: as decisões da
diretoria estavam espalhadas por três telas diferentes, cada uma exigindo que
ela lembrasse de passar lá. O pedido de dias vivia num card da Visão geral, a
justificativa de atraso na aba Atrasos, e a classificação de entrega em lugar
nenhum. Fila que ninguém sabe que existe é fila parada — foi assim que dois
pedidos ficaram semanas represados sem ninguém notar.

⚠ **Nem toda ação restrita à diretoria é uma aprovação.** Criar formulário,
configurar coluna do kanban e excluir usuário também exigem `require_diretor`,
e nenhuma delas entra aqui: são coisas que ela FAZ quando quer, não coisas que
esperam por ela. O critério desta fila é ter alguém do outro lado bloqueado
enquanto ela não responde.

São três, e cada uma tem um bloqueio concreto atrás:

1. **Pedidos de dias de ajuste** (§8) — o coordenador não consegue pintar
   além da janela enquanto não houver resposta.
2. **Atrasos sem justificativa** (§7.4) — o projeto fica vermelho no
   monitoramento sem que ninguém saiba o porquê.
3. **Entregas atrasadas sem classificação** (§7.4) — sem dizer se o atraso foi
   interno ou do cliente, a métrica de atraso da área mistura os dois.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo
from src.utils.atraso_monitoramento import calcular_atraso_projeto


class ListarAprovacoesPendentesUseCase:
    """Monta a fila. Sem recorte de visão: a diretoria enxerga tudo (§3)."""

    def __init__(self, db: Session):
        self.db = db
        self.projeto_repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.reajuste_repository = CronogramaReajusteRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, referencia: Optional[date] = None) -> dict:
        hoje = referencia or date.today()

        # Arquivado e finalizado saem da fila: decidir sobre projeto encerrado
        # não destrava ninguém, e a lista precisa caber numa tela.
        projetos = [
            p
            for p in self.db.query(ProjetoModel).all()
            if p.status != "finalizado" and not getattr(p, "arquivado_em", None)
        ]
        por_id = {p.id: p for p in projetos}
        escopos = self.escopo_repository.get_by_projetos(list(por_id))
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        nomes_escopo = {e.id: nome_do_escopo(e, catalogo) for e in escopos}
        nomes_usuario = {u.id: u.nome for u in self.usuario_repository.get_all()}

        dias = self._dias_de_ajuste(escopos, por_id, nomes_escopo, nomes_usuario)
        atrasos = self._atrasos_sem_justificativa(projetos, escopos, nomes_escopo, hoje)
        entregas = self._entregas_sem_classificacao(escopos, por_id, nomes_escopo)

        return {
            "dias_de_ajuste": dias,
            "atrasos_sem_justificativa": atrasos,
            "entregas_sem_classificacao": entregas,
            # O total é servido pronto porque o badge da aba precisa dele antes
            # de qualquer render — somar no front daria a mesma conta em dois
            # lugares, e é a que sai errada quando nasce uma quarta fila.
            "total": len(dias) + len(atrasos) + len(entregas),
        }

    def _dias_de_ajuste(self, escopos, por_id, nomes_escopo, nomes_usuario) -> List[dict]:
        """§8: o coordenador pediu, a janela não cresce até ela responder."""
        linhas = []
        for escopo in escopos:
            pendente = self.reajuste_repository.get_pendente_do_escopo(escopo.id)
            if not pendente:
                continue
            projeto = por_id.get(escopo.projeto_id)
            linhas.append(
                {
                    "id": pendente.id,
                    "projeto_id": escopo.projeto_id,
                    "projeto_nome": projeto.nome if projeto else "",
                    "escopo_nome": nomes_escopo.get(escopo.id, "escopo"),
                    "dias_solicitados": pendente.dias_solicitados,
                    "dias_vendidos": escopo.dias_uteis_vendidos,
                    "dias_ajustados": escopo.dias_uteis_ajustados,
                    "motivo": pendente.motivo,
                    "solicitado_por": pendente.solicitado_por,
                    "solicitado_por_nome": nomes_usuario.get(pendente.solicitado_por),
                    "criado_em": pendente.criado_em,
                }
            )
        return sorted(linhas, key=lambda x: x["criado_em"])

    def _atrasos_sem_justificativa(self, projetos, escopos, nomes_escopo, hoje: date) -> List[dict]:
        """§7.4: o alerta é automático, o porquê é ela quem digita."""
        por_projeto: dict = {}
        for e in escopos:
            por_projeto.setdefault(e.projeto_id, []).append(e)
        # `mapa_por_escopo` e não a lista: a banca passou a cobrir vários
        # escopos (tabela de junção), e a pergunta aqui é sempre "qual a banca
        # DESTE escopo".
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        ja_justificados = {
            j.projeto_id
            for j in self.justificativa_repository.get_by_projetos([p.id for p in projetos])
        }

        linhas = []
        for projeto in projetos:
            if projeto.id in ja_justificados:
                continue
            atraso = calcular_atraso_projeto(
                projeto.id,
                por_projeto.get(projeto.id, []),
                bancas,
                nomes_escopo,
                referencia=hoje,
            )
            if not atraso.atrasado:
                continue
            linhas.append(
                {
                    "projeto_id": projeto.id,
                    "projeto_nome": projeto.nome,
                    "status": projeto.status,
                    "dias_totais": atraso.dias_totais,
                    "motivos": [m.descricao for m in atraso.motivos],
                }
            )
        # O mais atrasado primeiro: é o que mais precisa de explicação.
        return sorted(linhas, key=lambda x: -x["dias_totais"])

    def _entregas_sem_classificacao(self, escopos, por_id, nomes_escopo) -> List[dict]:
        """§7.4: atraso interno e atraso por agenda do cliente contam diferente
        na métrica da área — e só ela pode dizer qual foi."""
        linhas = []
        for escopo in escopos:
            entregue = escopo.data_entrega_real
            prometida = escopo.data_entrega_planejada
            if not entregue or not prometida or entregue <= prometida:
                continue
            if escopo.tipo_atraso_entrega:
                continue
            projeto = por_id.get(escopo.projeto_id)
            linhas.append(
                {
                    "escopo_id": escopo.id,
                    "projeto_id": escopo.projeto_id,
                    "projeto_nome": projeto.nome if projeto else "",
                    "escopo_nome": nomes_escopo.get(escopo.id, "escopo"),
                    "data_prometida": prometida,
                    "data_entrega": entregue,
                    "dias_de_atraso": (entregue - prometida).days,
                }
            )
        return sorted(linhas, key=lambda x: -x["dias_de_atraso"])
