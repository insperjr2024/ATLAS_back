from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.projeto.get_projeto import serializar_projeto_resumo
from src.utils.exceptions import RegraDeNegocioError


class MembroEquipeRequest(BaseModel):
    usuario_id: int
    papel: str  # "coordenador" | "consultor"


class CreateProjetoRequest(BaseModel):
    nome: str
    cliente: str
    descricao: Optional[str] = None
    link_proposta: Optional[str] = None
    frente_ids: List[int] = Field(min_length=1, max_length=2)
    dias_ambientacao: int = 5
    equipe: List[MembroEquipeRequest]
    dia_reuniao_padrao: Optional[int] = None

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

    def execute(self, request: CreateProjetoRequest, criado_por: int):
        for frente_id in request.frente_ids:
            if not self.frente_catalogo.get_by_id(frente_id):
                raise RegraDeNegocioError(f"Frente {frente_id} não encontrada")

        coordenadores = [m for m in request.equipe if m.papel == "coordenador"]
        consultores = [m for m in request.equipe if m.papel == "consultor"]
        if len(coordenadores) != 1:
            raise RegraDeNegocioError("O projeto precisa de exatamente 1 coordenador")
        if not (2 <= len(consultores) <= 3):
            raise RegraDeNegocioError("O projeto precisa de 2 a 3 consultores")

        for membro in request.equipe:
            if not self.usuario_repository.get_by_id(membro.usuario_id):
                raise RegraDeNegocioError(f"Usuário {membro.usuario_id} não encontrado")

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

        for frente_id in request.frente_ids:
            self.frente_repository.create(projeto_id=projeto.id, frente_id=frente_id)

        hoje = date.today()
        for membro in request.equipe:
            self.membro_repository.create(
                projeto_id=projeto.id,
                usuario_id=membro.usuario_id,
                papel=membro.papel,
                entrou_em=hoje,
            )

        self.historico_repository.create(
            projeto_id=projeto.id,
            status_anterior=None,
            status_novo="vendido",
            alterado_por=criado_por,
        )

        return serializar_projeto_resumo(projeto, self.frente_repository, self.membro_repository)
