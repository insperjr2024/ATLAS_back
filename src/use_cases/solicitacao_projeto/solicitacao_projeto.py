"""Declaração de interesse: o consultor pede para entrar num projeto.

O fluxo é: o consultor vê os projetos com vaga, escreve por que quer entrar,
e o COORDENADOR daquele projeto aceita ou recusa. Aceitar já inclui a pessoa
na equipe.

Quem responde:

- o COORDENADOR do projeto — poder novo e estreito: ele não ganha
  `pode_editar_equipe`, só aceita quem pediu para entrar no projeto dele;
- quem já tem `pode_editar_equipe` (gerência e diretoria), desde que enxergue
  o projeto. Aqui não há poder novo: quem já podia montar a equipe inteira
  evidentemente pode aceitar um pedido.

⚠ O recorte por frente do gerente vem de `pode_ver_projeto`, o mesmo do resto
do sistema — não é reimplementado aqui.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.solicitacao_projeto_model import SolicitacaoProjetoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.middlewares.authorization import pode_ver_projeto, usuario_tem_permissao
from src.utils.exceptions import RegraDeNegocioError
from src.use_cases.notificacao.registrar_notificacao import registrar

#: Teto de projetos por consultor. É o mesmo limiar que o §7.3 usa para marcar
#: gargalo — quem está em 3 já aparece com o alerta no seletor de equipe.
MAX_PROJETOS_POR_CONSULTOR = 3

#: Status que não aceitam gente nova: o projeto acabou ou está congelado.
STATUS_FECHADOS = {"finalizado", "pausado"}


class CriarSolicitacaoRequest(BaseModel):
    projeto_id: int
    justificativa: str


class ResponderSolicitacaoRequest(BaseModel):
    aprovar: bool
    resposta: Optional[str] = None


class SolicitacaoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.frente_repository = FrenteRepository(db)

    # ------------------------------------------------------------------ #
    # Leitura                                                             #
    # ------------------------------------------------------------------ #

    def _pendentes_do_usuario(self, usuario_id: int) -> set:
        return {
            s.projeto_id
            for s in self.db.query(SolicitacaoProjetoModel)
            .filter(
                SolicitacaoProjetoModel.usuario_id == usuario_id,
                SolicitacaoProjetoModel.status == "pendente",
            )
            .all()
        }

    def _projetos_do_usuario(self, usuario_id: int) -> set:
        """Onde a pessoa está HOJE — para o "você já está neste projeto"."""
        return {
            m.projeto_id
            for m in self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        }

    def _carga(self, usuario_id: int) -> int:
        """A carga oficial do §7.3 — projeto finalizado ou arquivado não conta.

        📐 Vem de `contar_ativos_por_usuario`, o mesmo contador que a tela de
        montar equipe usa. Contar aqui na mão daria um número diferente do que
        a diretoria vê no monitoramento, para a mesma pessoa.
        """
        return self.membro_repository.contar_ativos_por_usuario().get(usuario_id, 0)

    def listar_vagas(self, usuario_id: int) -> dict:
        """Os projetos que ainda cabem gente, do ponto de vista de quem olha.

        📐 Devolve TODOS os projetos abertos, marcando cada um com o motivo de
        não poder pedir (`impedimento`), em vez de esconder. Sumir da lista
        sem explicação é o tipo de coisa que gera "por que não aparece o
        projeto X?" — e ninguém sabe responder.
        """
        projetos = [
            p
            for p in self.repository.get_all()
            if not p.arquivado_em and p.status not in STATUS_FECHADOS
        ]
        vinculos = self.membro_repository.get_by_projetos([p.id for p in projetos], apenas_atuais=True)

        consultores: dict = {}
        coordenadores: dict = {}
        for v in vinculos:
            if v.papel == "consultor":
                consultores.setdefault(v.projeto_id, []).append(v.usuario_id)
            else:
                coordenadores[v.projeto_id] = v.usuario_id

        # As frentes de cada projeto, numa consulta só. É o que dá ao
        # candidato a primeira ideia do que o projeto é, antes de abrir.
        nomes_frente = {f.id: f.nome for f in self.frente_repository.get_all()}
        frentes_por_projeto: dict = {}
        for v in self.db.query(ProjetoFrenteModel).filter(
            ProjetoFrenteModel.projeto_id.in_([p.id for p in projetos] or [0])
        ):
            frentes_por_projeto.setdefault(v.projeto_id, []).append(nomes_frente.get(v.frente_id))

        meus = self._projetos_do_usuario(usuario_id)
        pendentes = self._pendentes_do_usuario(usuario_id)
        minha_carga = self._carga(usuario_id)
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}

        saida = []
        for p in projetos:
            alocados = len(consultores.get(p.id, []))
            vagas = max(0, (p.max_consultores or 0) - alocados)

            if p.id in meus:
                impedimento = "Você já está neste projeto"
            elif p.id in pendentes:
                impedimento = "Você já tem um pedido em análise aqui"
            elif vagas == 0:
                impedimento = "Sem vaga: o projeto já está com o time completo"
            elif minha_carga >= MAX_PROJETOS_POR_CONSULTOR:
                impedimento = (
                    f"Você já está em {minha_carga} projetos, o limite para não virar gargalo"
                )
            else:
                impedimento = None

            saida.append(
                {
                    "id": p.id,
                    "nome": p.nome,
                    "cliente": p.cliente,
                    "descricao": p.descricao,
                    "status": p.status,
                    "frentes": sorted(n for n in frentes_por_projeto.get(p.id, []) if n),
                    "coordenador_id": coordenadores.get(p.id),
                    "coordenador_nome": nomes.get(coordenadores.get(p.id)),
                    "consultores": [nomes.get(uid) for uid in consultores.get(p.id, [])],
                    "alocados": alocados,
                    "max_consultores": p.max_consultores,
                    "vagas": vagas,
                    "impedimento": impedimento,
                }
            )

        saida.sort(key=lambda p: (p["impedimento"] is not None, -p["vagas"], p["nome"]))
        return {"projetos": saida, "minha_carga": minha_carga, "teto": MAX_PROJETOS_POR_CONSULTOR}

    def _pode_responder(self, projeto_id: int, current_user) -> bool:
        """Coordenador do projeto, ou quem já monta equipe e enxerga o projeto."""
        vinculos = self.membro_repository.get_by_projeto(projeto_id, apenas_atuais=True)
        if any(
            v.usuario_id == current_user.id and v.papel == "coordenador" for v in vinculos
        ):
            return True
        return usuario_tem_permissao(
            current_user, self.db, "pode_editar_equipe"
        ) and pode_ver_projeto(projeto_id, current_user, self.db)

    def listar_do_coordenador(self, current_user) -> List[dict]:
        """Os pedidos que ESTA pessoa pode responder.

        Para o coordenador, são os projetos dele. Para gerência e diretoria,
        todos os que elas enxergam — o gerente fica na própria frente porque
        `pode_ver_projeto` já aplica esse recorte.
        """
        coordenados = {
            m.projeto_id
            for m in self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == current_user.id,
                ProjetoMembroModel.papel == "coordenador",
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        }
        meus = set(coordenados)
        if usuario_tem_permissao(current_user, self.db, "pode_editar_equipe"):
            meus.update(
                p.id
                for p in self.repository.get_all()
                if pode_ver_projeto(p.id, current_user, self.db)
            )
        if not meus:
            return []
        meus = list(meus)

        pedidos = (
            self.db.query(SolicitacaoProjetoModel)
            .filter(SolicitacaoProjetoModel.projeto_id.in_(meus))
            .order_by(SolicitacaoProjetoModel.criado_em.desc())
            .all()
        )
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}
        projetos = {p.id: p for p in self.repository.get_all()}
        cargas = self.membro_repository.contar_ativos_por_usuario()

        return [
            {
                "id": s.id,
                "projeto_id": s.projeto_id,
                "projeto_nome": projetos[s.projeto_id].nome if s.projeto_id in projetos else "—",
                "usuario_id": s.usuario_id,
                "usuario_nome": nomes.get(s.usuario_id),
                "carga_do_solicitante": cargas.get(s.usuario_id, 0),
                "justificativa": s.justificativa,
                "status": s.status,
                "criado_em": s.criado_em,
                "respondido_em": s.respondido_em,
                "respondido_por_nome": nomes.get(s.respondido_por),
                "resposta": s.resposta,
            }
            for s in pedidos
        ]

    # ------------------------------------------------------------------ #
    # Escrita                                                             #
    # ------------------------------------------------------------------ #

    def criar(self, usuario_id: int, request: CriarSolicitacaoRequest) -> dict:
        if not request.justificativa.strip():
            raise RegraDeNegocioError("Escreva por que você quer entrar neste projeto.")

        projeto = self.repository.get_by_id(request.projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado")
        if projeto.arquivado_em or projeto.status in STATUS_FECHADOS:
            raise RegraDeNegocioError("Este projeto não está aceitando gente nova.")

        vinculos = self.membro_repository.get_by_projeto(projeto.id, apenas_atuais=True)
        if any(v.usuario_id == usuario_id for v in vinculos):
            raise RegraDeNegocioError("Você já faz parte deste projeto.")

        alocados = sum(1 for v in vinculos if v.papel == "consultor")
        if alocados >= (projeto.max_consultores or 0):
            raise RegraDeNegocioError("Este projeto já está com o time completo.")

        if request.projeto_id in self._pendentes_do_usuario(usuario_id):
            raise RegraDeNegocioError("Você já tem um pedido em análise para este projeto.")

        carga = self._carga(usuario_id)
        if carga >= MAX_PROJETOS_POR_CONSULTOR:
            raise RegraDeNegocioError(
                f"Você já está em {carga} projetos, que é o limite. "
                "Saia de um antes de pedir para entrar em outro."
            )

        solicitacao = SolicitacaoProjetoModel(
            projeto_id=request.projeto_id,
            usuario_id=usuario_id,
            justificativa=request.justificativa.strip(),
            status="pendente",
            criado_em=datetime.now(),
        )
        self.db.add(solicitacao)
        self.db.commit()
        self.db.refresh(solicitacao)

        coordenador = next((v for v in vinculos if v.papel == "coordenador"), None)
        if coordenador:
            usuario = self.usuario_repository.get_by_id(usuario_id)
            # `registrar` direto, e não `notificar`: aquele helper é dos
            # eventos de banca e só sabe carregar `banca_id`.
            registrar(
                self.db,
                usuario_id=coordenador.usuario_id,
                tipo="solicitacao_projeto",
                titulo=(
                    f"{usuario.nome if usuario else 'Alguém'} quer entrar no projeto "
                    f"{projeto.nome}."
                ),
                corpo=solicitacao.justificativa,
                projeto_id=projeto.id,
                rota="/projetos/solicitacoes",
                chave_dedup=f"solicitacao_projeto:{solicitacao.id}",
            )

        return {"id": solicitacao.id, "status": solicitacao.status}

    def responder(self, solicitacao_id: int, current_user, request: ResponderSolicitacaoRequest) -> dict:
        solicitacao = self.db.get(SolicitacaoProjetoModel, solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Pedido não encontrado")
        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Este pedido já foi respondido.")

        if not self._pode_responder(solicitacao.projeto_id, current_user):
            raise RegraDeNegocioError(
                "Só o coordenador do projeto, a gerência da frente ou a diretoria "
                "respondem a este pedido."
            )
        vinculos = self.membro_repository.get_by_projeto(solicitacao.projeto_id, apenas_atuais=True)

        if request.aprovar:
            # ⚠ Rechecar aqui, e não só na criação: entre pedir e responder,
            # a gerência pode ter preenchido o time por outro caminho.
            projeto = self.repository.get_by_id(solicitacao.projeto_id)
            alocados = sum(1 for v in vinculos if v.papel == "consultor")
            if alocados >= (projeto.max_consultores or 0):
                raise RegraDeNegocioError(
                    "O time encheu depois que o pedido foi feito. "
                    "Aumente o limite de consultores do projeto ou recuse."
                )
            if any(v.usuario_id == solicitacao.usuario_id for v in vinculos):
                raise RegraDeNegocioError("Esta pessoa já entrou no projeto por outro caminho.")

            self.membro_repository.create(
                projeto_id=solicitacao.projeto_id,
                usuario_id=solicitacao.usuario_id,
                papel="consultor",
                entrou_em=datetime.now(),
            )

        solicitacao.status = "aprovada" if request.aprovar else "recusada"
        solicitacao.respondido_por = current_user.id
        solicitacao.respondido_em = datetime.now()
        solicitacao.resposta = (request.resposta or "").strip() or None
        self.db.commit()

        projeto = self.repository.get_by_id(solicitacao.projeto_id)
        aviso = (
            f"Seu pedido para entrar no projeto {projeto.nome} foi aceito. Bem-vindo(a)!"
            if request.aprovar
            else f"Seu pedido para entrar no projeto {projeto.nome} não foi aceito."
        )
        if solicitacao.resposta:
            aviso += f" Motivo: {solicitacao.resposta}"
        registrar(
            self.db,
            usuario_id=solicitacao.usuario_id,
            tipo="solicitacao_projeto",
            titulo=aviso,
            projeto_id=solicitacao.projeto_id,
            chave_dedup=f"resposta_solicitacao_projeto:{solicitacao.id}",
        )

        return {"id": solicitacao.id, "status": solicitacao.status}

    def cancelar(self, solicitacao_id: int, usuario_id: int) -> dict:
        """O próprio solicitante desiste. Só enquanto está pendente."""
        solicitacao = self.db.get(SolicitacaoProjetoModel, solicitacao_id)
        if not solicitacao or solicitacao.usuario_id != usuario_id:
            raise RegraDeNegocioError("Pedido não encontrado")
        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Este pedido já foi respondido.")
        self.db.delete(solicitacao)
        self.db.commit()
        return {"ok": True}

    def listar_meus(self, usuario_id: int) -> List[dict]:
        pedidos = (
            self.db.query(SolicitacaoProjetoModel)
            .filter(SolicitacaoProjetoModel.usuario_id == usuario_id)
            .order_by(SolicitacaoProjetoModel.criado_em.desc())
            .all()
        )
        projetos = {p.id: p for p in self.repository.get_all()}
        return [
            {
                "id": s.id,
                "projeto_id": s.projeto_id,
                "projeto_nome": projetos[s.projeto_id].nome if s.projeto_id in projetos else "—",
                "status": s.status,
                "justificativa": s.justificativa,
                "resposta": s.resposta,
                "criado_em": s.criado_em,
                "respondido_em": s.respondido_em,
            }
            for s in pedidos
        ]
