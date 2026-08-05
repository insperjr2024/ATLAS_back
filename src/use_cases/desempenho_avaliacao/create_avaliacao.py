from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_nota_repository import DesempenhoAvaliacaoNotaRepository
from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.use_cases.desempenho_avaliacao.get_fila import GetFilaUsuarioUseCase
from src.utils.desempenho_fila import calcular_pares_lote, deduplicar_pares
from src.utils.desempenho_lote import esta_aberto
from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_desempenho_nota import validar_desempenho_nota


class NotaInput(BaseModel):
    criterio_id: int
    nota: Optional[int] = None
    resposta_texto: Optional[str] = None


class CreateDesempenhoAvaliacaoRequest(BaseModel):
    lote_id: int
    avaliado_id: int
    nota_geral: int
    comentarios: str
    notas: List[NotaInput]


class CreateDesempenhoAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.avaliacao_nota_repo = DesempenhoAvaliacaoNotaRepository(db)
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)

    def execute(self, request: CreateDesempenhoAvaliacaoRequest, avaliador_id: int) -> dict:
        lote = self.lote_repo.get_by_id(request.lote_id)
        if not lote:
            raise RegraDeNegocioError("Lote não encontrado")
        if not esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim):
            raise RegraDeNegocioError(f'O formulário "{lote.nome}" não está aberto para avaliações')

        if avaliador_id == request.avaliado_id:
            raise RegraDeNegocioError("Você não pode avaliar a si mesmo")

        # Regra 2.3: o par precisa estar na fila esperada do lote.
        projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote.id)
        membros = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=True)
        agregados = deduplicar_pares(calcular_pares_lote(membros))
        chave = (avaliador_id, request.avaliado_id)
        if chave not in agregados:
            raise RegraDeNegocioError("Você não está habilitado a avaliar esta pessoa neste lote")
        form_type = agregados[chave]["form_type"]

        if self.avaliacao_repo.existe_par(lote.id, avaliador_id, request.avaliado_id):
            raise RegraDeNegocioError("Você já avaliou esta pessoa neste lote")

        if not 1 <= request.nota_geral <= 5:
            raise RegraDeNegocioError("A nota geral deve estar entre 1 e 5")

        formulario = self.formulario_repo.first_by(tipo=lote.tipo, papel=form_type)
        if not formulario:
            raise RegraDeNegocioError(f"Nenhum formulário configurado para {lote.tipo}/{form_type}")

        criterios = {c.id: c for c in self.criterio_repo.get_by_formulario(formulario.id)}
        notas_por_criterio = {n.criterio_id: n for n in request.notas}
        if set(notas_por_criterio) != set(criterios):
            raise RegraDeNegocioError("Todos os critérios do formulário devem ser respondidos")
        for criterio_id, criterio in criterios.items():
            entrada = notas_por_criterio[criterio_id]
            validar_desempenho_nota(criterio, entrada.nota, entrada.resposta_texto)

        avaliacao = self.avaliacao_repo.create(
            lote_id=lote.id,
            formulario_id=formulario.id,
            avaliador_id=avaliador_id,
            avaliado_id=request.avaliado_id,
            nota_geral=request.nota_geral,
            comentarios=request.comentarios,
        )
        self.avaliacao_nota_repo.bulk_create(
            [
                {
                    "avaliacao_id": avaliacao.id,
                    "criterio_id": n.criterio_id,
                    "nota": n.nota,
                    "resposta_texto": n.resposta_texto,
                }
                for n in request.notas
            ]
        )

        # Regra 2.4: o front decide se volta pra escolha de tipo ou finaliza
        # com base no que sobrar aqui.
        fila_restante = GetFilaUsuarioUseCase(self.db).execute(avaliador_id)

        return {
            "avaliacao": {
                "id": avaliacao.id,
                "lote_id": avaliacao.lote_id,
                "formulario_id": avaliacao.formulario_id,
                "avaliador_id": avaliacao.avaliador_id,
                "avaliado_id": avaliacao.avaliado_id,
                "nota_geral": avaliacao.nota_geral,
                "comentarios": avaliacao.comentarios,
            },
            "proxima_pendencia": fila_restante[0] if fila_restante else None,
        }
