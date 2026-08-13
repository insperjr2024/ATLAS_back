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

São QUATRO, e cada uma tem um bloqueio concreto atrás:

1. **Pedidos de dias de ajuste** (§8) — o coordenador não consegue pintar
   além da janela enquanto não houver resposta.
2. **Atrasos sem justificativa** (§7.4) — o projeto fica vermelho no
   monitoramento sem que ninguém saiba o porquê.
3. **Solicitações de entrada em projeto** — alguém pediu para entrar e está
   parado esperando; o projeto segue com a vaga aberta.
4. **Bancas realizadas sem resultado** (§5.5) — a banca aconteceu e ninguém
   registrou o veredito.

⚠ Havia uma quinta, "entregas sem classificação", removida em 2026-08-12 junto
com o atraso de entrega nos insights: sem a métrica que separava interno de
agenda do cliente, a classificação deixou de mudar qualquer número.

⚠ **A fila mostra as quatro SEMPRE**, mesmo vazias — quem abre precisa saber o
que esta tela cobre, e uma tela que só aparece quando há problema não ensina
ninguém a confiar nela. Quem decide isso é o front; o backend sempre devolve
as quatro chaves.
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
from src.use_cases.banca.excecao_choque import ListarExcecoesChoquePendentesUseCase
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

    def execute(self, current_user=None, referencia: Optional[date] = None) -> dict:
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
        entradas = self._solicitacoes_de_entrada(current_user)
        sem_resultado = self._bancas_sem_resultado(escopos, por_id, nomes_escopo)
        # ⭐ §8: quem quer marcar banca num horário já ocupado pede aqui, e a
        # diretoria decide. Antes o bloqueio existia sem via de exceção — a
        # regra era anunciada e não havia como cumpri-la.
        choques = ListarExcecoesChoquePendentesUseCase(self.db).execute()

        # ⚠ Havia aqui uma quinta fila, `entregas_sem_classificacao`: as
        # entregas atrasadas ainda não marcadas como atraso interno ou por
        # agenda do cliente. Removida em 2026-08-12, junto com o que lhe dava
        # sentido — o atraso de ENTREGA saiu dos insights, e com ele a métrica
        # que separava os dois tipos. A fila continuava cobrando da diretoria
        # uma classificação que não mudava mais número nenhum.
        return {
            "dias_de_ajuste": dias,
            "atrasos_sem_justificativa": atrasos,
            "solicitacoes_de_entrada": entradas,
            "bancas_sem_resultado": sem_resultado,
            "excecoes_de_choque": choques,
            # O total é servido pronto porque o badge da aba precisa dele antes
            # de qualquer render — somar no front daria a mesma conta em dois
            # lugares, e é a que sai errada quando nasce uma fila nova.
            "total": len(dias) + len(atrasos) + len(entradas) + len(sem_resultado) + len(choques),
        }

    def _solicitacoes_de_entrada(self, current_user) -> List[dict]:
        """Quem pediu para entrar num projeto e ainda espera resposta.

        ⭐ Passa no critério da fila com folga: tem uma PESSOA parada do outro
        lado, e o projeto segue com a vaga aberta. Vivia só na tela "Vagas em
        projetos" — quem não passasse por lá não sabia que alguém esperava.

        Delega para `listar_do_coordenador`, que é o mesmo caminho da tela de
        Vagas: o recorte de quem pode responder é regra de negócio e não pode
        ter duas implementações. Filtra só os pendentes — os já respondidos
        seguem visíveis lá, como histórico.
        """
        if current_user is None:
            return []

        from src.use_cases.solicitacao_projeto.solicitacao_projeto import (
            SolicitacaoProjetoUseCase,
        )

        pedidos = SolicitacaoProjetoUseCase(self.db).listar_do_coordenador(current_user)
        return [p for p in pedidos if p["status"] == "pendente"]

    def _bancas_sem_resultado(self, escopos, por_id, nomes_escopo) -> List[dict]:
        """§5.5: a banca aconteceu e ninguém registrou o veredito.

        ⭐ **Esta fila virou o bloqueio mais duro do sistema.** Enquanto não há
        veredito, a entrega ao cliente NÃO libera (`RegistrarEntregaEscopoUseCase`):
        o escopo fica parado esperando alguém agir. O caminho normal é o voto
        dos avaliadores, que apura sozinho; o que cai aqui é o que o voto não
        resolveu — ninguém votou e o prazo venceu — e só a diretoria destrava,
        registrando o resultado à mão.

        Só bancas de escopo (as legadas, sem vínculo, não têm projeto para
        cobrar) e só de projeto vivo — o recorte de `execute`.
        """
        por_escopo = {}
        for escopo in escopos:
            banca = self.banca_repository.get_by_projeto_escopo(escopo.id)
            if not banca or not banca.realizado_em or banca.resultado:
                continue
            # Uma banca pode cobrir vários escopos: uma linha por banca.
            por_escopo.setdefault(banca.id, (banca, escopo))

        linhas = []
        for banca, escopo in por_escopo.values():
            projeto = por_id.get(escopo.projeto_id)
            linhas.append(
                {
                    "banca_id": banca.id,
                    "projeto_id": escopo.projeto_id,
                    "projeto_nome": projeto.nome if projeto else "",
                    "escopo_nome": nomes_escopo.get(escopo.id, "escopo"),
                    "realizado_em": banca.realizado_em,
                }
            )
        # A mais antiga primeiro: é a que está esperando há mais tempo.
        return sorted(linhas, key=lambda x: x["realizado_em"])

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

