from sqlalchemy.orm import Session
from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.composicao_banca import ComposicaoBancaChecker
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
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.banca_repository = BancaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)

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
            self.vendedor_repository,
        ):
            raise RegraDeNegocioError("Você não pode se candidatar à banca do seu próprio grupo")

        candidaturas_existentes = self.repository.get_by_banca(request.banca_id)
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5

        if len(candidaturas_existentes) >= vagas:
            raise RegraDeNegocioError("Não é possível se candidatar: banca lotada")

        # ⭐ §8, os TETOS por frente da combinação (2026-09-02). O teto acima é
        # global — quantos cabem na banca — e deixava passar a banca cheia de
        # uma frente só, que é exatamente o que a matriz de Configurações
        # existe para evitar. Combinação sem configuração cai em `SEM_TETO` e
        # nada muda para ela.
        recusa = self._recusa_por_composicao(banca, candidaturas_existentes, usuario_id)
        if recusa:
            raise RegraDeNegocioError(f"Não é possível se candidatar: {recusa}")

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

    def _recusa_por_composicao(self, banca, candidaturas, usuario_id: int):
        """A frase de recusa dos tetos por frente, ou `None` quando cabe.

        ⚠ Vale para as DUAS portas desta rota: a inscrição do próprio e a
        alocação feita pela diretoria são o mesmo use case, com `usuario_id`
        diferente. O push automático da semana NÃO passa por aqui — ele grava
        candidatura direto no repositório, e por isso ganhou a mesma guarda no
        próprio bloco de preenchimento (`push_alocacao_automatica`).
        """
        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        if not vinculos:
            # Banca legada, sem frente vinculada: não há combinação, não há
            # regra. O teto global acima continua sendo o que a segura.
            return None
        regras = ResolverComposicaoUseCase(self.db).para([v.frente_id for v in vinculos])
        return ComposicaoBancaChecker(self.db).recusa_por_teto(
            banca, regras, {c.usuario_id for c in candidaturas}, usuario_id
        )