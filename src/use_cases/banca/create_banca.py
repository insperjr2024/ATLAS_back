from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_repository import BancaRepository
from src.use_cases.banca.excecao_choque import checar_choque
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.repositories.frente_repository import FrenteRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class CreateBancaRequest(BaseModel):
    nome_projeto: str
    escopo_id: int
    data_hora: datetime
    consultor_ids: List[int] = []
    frente_ids: List[int] = []
    #: Só a diretoria define — ver `require_diretor` no use case.
    piso_minimo_override: Optional[int] = None


class CreateBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.frente_repository = FrenteRepository(db)

    def execute(self, request: CreateBancaRequest, coordenador_id: int, eh_diretor: bool = False):
        for consultor_id in request.consultor_ids:
            if not self.usuario_repository.get_by_id(consultor_id):
                raise RegraDeNegocioError(f"Usuário {consultor_id} não encontrado")

        for frente_id in request.frente_ids:
            if not self.frente_repository.get_by_id(frente_id):
                raise RegraDeNegocioError(f"Frente {frente_id} não encontrada")

        if request.piso_minimo_override is not None and not eh_diretor:
            raise RegraDeNegocioError("Só a diretoria pode definir o piso mínimo de uma banca")

        # 🔒 §8: duas bancas no mesmo horário não passam — nem por esta porta.
        #
        # ⚠ Esta rota é a do módulo legado e ficou de fora da regra por
        # esquecimento, não por decisão: dava para criar uma banca em cima de
        # outra sem nenhuma recusa, enquanto o cronograma barrava a mesma coisa.
        #
        # Sem escopo vendido não há exceção possível (o pedido é do par
        # escopo+horário), então aqui o choque sempre bloqueia. É o
        # conservador certo: a banca legada não tem projeto de onde derivar
        # quem pediria a liberação.
        checar_choque(self.db, request.data_hora, banca_repository=self.repository)

        banca = self.repository.create(
            nome_projeto=request.nome_projeto,
            escopo_id=request.escopo_id,
            coordenador_id=coordenador_id,
            data_hora=request.data_hora,
            piso_minimo_override=request.piso_minimo_override,
        )

        for consultor_id in request.consultor_ids:
            self.equipe_projeto_repository.create(banca_id=banca.id, usuario_id=consultor_id)

        for frente_id in request.frente_ids:
            self.banca_frente_repository.create(banca_id=banca.id, frente_id=frente_id)

        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            # Esta rota é a do módulo legado: cria banca sem escopo vendido.
            # Quem costura banca a escopo é PUT /escopos-projeto/{id}/banca.
            "projeto_escopo_ids": [],
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "piso_minimo_override": banca.piso_minimo_override,
            "consultor_ids": request.consultor_ids,
            "frente_ids": request.frente_ids
        }