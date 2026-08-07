from sqlalchemy.orm import Session
from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.equipe_banca import membros_da_banca
from src.utils.exceptions import RegraDeNegocioError


class CreateCandidaturaRequest(BaseModel):
    banca_id: int
    confirmado: bool = False
    #: Alocar OUTRA pessoa. Só a diretoria — o router faz a checagem, porque é
    #: lá que se sabe quem está chamando. Sem isto, cada um só se inscreve.
    usuario_id: Optional[int] = None


class CreateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, request: CreateCandidaturaRequest, usuario_id: int):
        banca = self.banca_repository.get_by_id(request.banca_id)
        if not banca:
            raise RegraDeNegocioError("Banca não encontrada")

        # Quem fecha a inscrição é a REALIZAÇÃO, não o calendário: uma banca
        # `atrasada` (venceu e não aconteceu) continua aceitando gente, porque
        # ela ainda vai acontecer. Antes da F5 a data passada bloqueava.
        status = calcular_status_banca(banca.data_hora, banca.realizado_em)
        if not aceita_inscricao(status):
            if status == "realizada":
                raise RegraDeNegocioError("Não é possível se candidatar: esta banca já foi realizada")
            raise RegraDeNegocioError("Não é possível se candidatar: esta banca ainda não tem data marcada")

        # Ninguém avalia o próprio grupo: nem quem coordena, nem quem está na
        # equipe do projeto desta banca.
        #
        # ⚠ Antes isto lia só `equipe_projeto`, a tabela legada preenchida à
        # mão na tela de bancas. Banca marcada pelo CRONOGRAMA não escreve
        # nela, e os consultores do projeto conseguiam se inscrever na própria
        # banca. `membros_da_banca` junta as duas fontes.
        if usuario_id in membros_da_banca(
            banca,
            self.banca_escopo_repository,
            self.escopo_repository,
            self.membro_repository,
            self.equipe_projeto_repository,
        ):
            raise RegraDeNegocioError("Você não pode se candidatar à banca do seu próprio grupo")

        candidaturas_existentes = self.repository.get_by_banca(request.banca_id)
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5

        if len(candidaturas_existentes) >= vagas:
            raise RegraDeNegocioError("Não é possível se candidatar: banca lotada")

        candidatura = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=usuario_id,
            criado_em=datetime.now(),
            confirmado=request.confirmado
        )
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }