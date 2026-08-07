from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.eventos import notificar_alocacao
from src.use_cases.projeto.get_projeto import serializar_projeto_resumo
from src.use_cases.tarefa.colunas import criar_colunas_padrao
from src.use_cases.projeto_escopo.create_escopo_projeto import (
    EscopoVendidoRequest,
    validar_escopo_vendido,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_equipe import validar_equipe


class MembroEquipeRequest(BaseModel):
    usuario_id: int
    papel: str  # "coordenador" | "consultor"


class CreateProjetoRequest(BaseModel):
    nome: str
    cliente: Optional[str] = None
    descricao: Optional[str] = None
    link_proposta: Optional[str] = None
    #: Sem teto: um projeto pode ser vendido para quantas frentes forem
    #: necessárias. Duas ou mais o tornam sinérgico (ver `get_projeto`).
    frente_ids: List[int] = Field(min_length=1)
    dias_ambientacao: int = 5
    equipe: List[MembroEquipeRequest]
    dia_reuniao_padrao: Optional[int] = None
    #: §5.1: "no registro entram (…) escopos com os dias úteis vendidos de
    #: cada um". Opcional para não quebrar quem cria o projeto e adiciona os
    #: escopos depois, na página do projeto.
    escopos: List[EscopoVendidoRequest] = Field(default_factory=list)

    @field_validator("frente_ids")
    @classmethod
    def frentes_unicas(cls, v: List[int]) -> List[int]:
        if len(set(v)) != len(v):
            raise ValueError("Frentes repetidas")
        return v


class CreateProjetoUseCase:
    """O cadastro do §6.3.

    ⚠ Kickoff NÃO entra aqui — o projeto nasce sem ele (§5.1); é marcado
    depois, na página do projeto, e é isso que dispara Vendido → Ambientação.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.frente_catalogo = FrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, request: CreateProjetoRequest, criado_por: int):
        for frente_id in request.frente_ids:
            if not self.frente_catalogo.get_by_id(frente_id):
                raise RegraDeNegocioError(f"Frente {frente_id} não encontrada")

        # Valida os escopos ANTES de gravar qualquer coisa — senão um escopo
        # inválido deixa para trás um projeto meio-criado.
        for escopo in request.escopos:
            validar_escopo_vendido(escopo, request.frente_ids, self.catalogo_repository)

        validar_equipe(request.equipe, self.usuario_repository)

        projeto = self.repository.create(
            nome=request.nome,
            cliente=request.cliente,
            descricao=request.descricao,
            link_proposta=request.link_proposta,
            status="vendido",
            dias_ambientacao=request.dias_ambientacao,
            dia_reuniao_padrao=request.dia_reuniao_padrao,
            criado_por=criado_por,
        )

        # O board nasce com o conjunto padrão de colunas. Sem isto o kanban
        # do projeto novo abriria vazio e não haveria onde a primeira tarefa
        # cair — as colunas são por projeto, não uma configuração global.
        criar_colunas_padrao(self.db, projeto.id)

        for frente_id in request.frente_ids:
            self.frente_repository.create(projeto_id=projeto.id, frente_id=frente_id)

        # A ordem é a do array que chegou — a hierarquia dos 4 clássicos da
        # Business (Merc/Op/Mkt/Fin) já vem aplicada pelo `EscopoPicker` no
        # front, e as setinhas de lá deixam reordenar antes de criar. Aqui
        # só respeita o que foi mandado, sem reinterpretar.
        for indice, escopo in enumerate(request.escopos):
            self.escopo_repository.create(
                projeto_id=projeto.id,
                escopo_id=escopo.escopo_id,
                nome_customizado=(escopo.nome_customizado or "").strip() or None,
                frente_id=escopo.frente_id,
                dias_uteis_vendidos=escopo.dias_uteis_vendidos,
                data_entrega_planejada=escopo.data_entrega_planejada,
                status="nao_iniciado",
                ordem=indice,
            )

        hoje = date.today()
        for membro in request.equipe:
            self.membro_repository.create(
                projeto_id=projeto.id,
                usuario_id=membro.usuario_id,
                papel=membro.papel,
                entrou_em=hoje,
            )
            notificar_alocacao(self.db, projeto, membro.usuario_id)

        self.historico_repository.create(
            projeto_id=projeto.id,
            status_anterior=None,
            status_novo="vendido",
            alterado_por=criado_por,
        )

        return serializar_projeto_resumo(projeto, self.frente_repository, self.membro_repository)
