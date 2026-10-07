from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_nota_repository import DesempenhoAvaliacaoNotaRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_formulario_secao_repository import DesempenhoFormularioSecaoRepository
from src.repositories.desempenho_lote_formulario_repository import DesempenhoLoteFormularioRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_formulario.get_formulario import GetDesempenhoFormularioUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc


class CriterioInput(BaseModel):
    id: Optional[int] = None
    label: str
    descricao: Optional[str] = None
    tipo_resposta: Literal["nota", "texto"] = "nota"
    limite_caracteres: Optional[int] = None


class SecaoInput(BaseModel):
    id: Optional[int] = None
    titulo: str
    descricao: Optional[str] = None
    criterios: List[CriterioInput]


class UpdateDesempenhoFormularioRequest(BaseModel):
    nota_geral_titulo: Optional[str] = None
    nota_geral_descricao: Optional[str] = None
    comentarios_titulo: Optional[str] = None
    comentarios_descricao: Optional[str] = None
    comentarios_aviso: Optional[str] = None
    secoes: Optional[List[SecaoInput]] = None
    #: Com lote aberto usando a versão vigente (2026-10-06, a pedido): `True`
    #: edita no lugar (vale pro lote em andamento); `False` congela a versão
    #: atual pros lotes abertos e a edição vale só pra lotes futuros. Sem
    #: lote aberto o valor não importa; com lote aberto e sem o campo, a
    #: tela precisa perguntar antes (erro `lotes_abertos`).
    aplicar_em_abertos: Optional[bool] = None


class ListLotesAbertosDoFormularioUseCase:
    """Lotes abertos do tipo que ainda usam a versão vigente deste (tipo,
    papel): os que uma edição afetaria. Lote que já tem versão congelada
    pro papel fica de fora, já está protegido."""

    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_formulario_repo = DesempenhoLoteFormularioRepository(db)

    def execute(self, tipo: str, papel: str) -> list[dict]:
        return [
            {"id": lote.id, "nome": lote.nome}
            for lote in self.lote_repo.get_abertos_agora()
            if lote.tipo == tipo and self.lote_formulario_repo.formulario_id_de(lote.id, papel) is None
        ]


class UpdateDesempenhoFormularioUseCase:
    """Edita textos e, se `secoes` vier no request, substitui a árvore
    inteira de seções/critérios daquele formulário — upsert por `id`
    (presente = atualiza, ausente = cria) e remove o que não veio na lista."""

    def __init__(self, db: Session):
        self.db = db
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.secao_repo = DesempenhoFormularioSecaoRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)
        self.nota_repo = DesempenhoAvaliacaoNotaRepository(db)
        self.lote_formulario_repo = DesempenhoLoteFormularioRepository(db)

    def execute(self, tipo: str, papel: str, request: UpdateDesempenhoFormularioRequest) -> Optional[dict]:
        formulario = self.formulario_repo.vigente(tipo, papel)
        if not formulario:
            return None

        abertos = ListLotesAbertosDoFormularioUseCase(self.db).execute(tipo, papel)
        if abertos:
            if request.aplicar_em_abertos is None:
                raise RegraDeNegocioError(
                    "Há lote aberto usando este formulário: "
                    + ", ".join(a["nome"] for a in abertos)
                    + ". Diga se a mudança vale pro que está em andamento ou só pra futuros.",
                    codigo="lotes_abertos",
                )
            if request.aplicar_em_abertos is False:
                return self._congelar_e_criar_vigente(formulario, abertos, request, tipo, papel)

        textos = request.dict(exclude_unset=True, exclude={"secoes", "aplicar_em_abertos"})
        if textos:
            self.formulario_repo.update(formulario.id, **textos)

        if request.secoes is not None:
            secoes_atuais = {s.id: s for s in self.secao_repo.get_by_formulario(formulario.id)}
            ids_mantidos = set()
            self._recusar_remocao_de_criterio_respondido(formulario.id, request.secoes)

            for ordem, secao_in in enumerate(request.secoes):
                if secao_in.id and secao_in.id in secoes_atuais:
                    secao = self.secao_repo.update(
                        secao_in.id, titulo=secao_in.titulo, descricao=secao_in.descricao, ordem=ordem
                    )
                else:
                    secao = self.secao_repo.create(
                        formulario_id=formulario.id,
                        titulo=secao_in.titulo,
                        descricao=secao_in.descricao,
                        ordem=ordem,
                    )
                ids_mantidos.add(secao.id)

                criterios_atuais = {c.id: c for c in self.criterio_repo.get_by_secao(secao.id)}
                criterio_ids_mantidos = set()
                for ordem_c, criterio_in in enumerate(secao_in.criterios):
                    if criterio_in.id and criterio_in.id in criterios_atuais:
                        criterio = self.criterio_repo.update(
                            criterio_in.id,
                            label=criterio_in.label,
                            descricao=criterio_in.descricao,
                            tipo_resposta=criterio_in.tipo_resposta,
                            limite_caracteres=criterio_in.limite_caracteres,
                            ordem=ordem_c,
                        )
                    else:
                        criterio = self.criterio_repo.create(
                            secao_id=secao.id,
                            label=criterio_in.label,
                            descricao=criterio_in.descricao,
                            tipo_resposta=criterio_in.tipo_resposta,
                            limite_caracteres=criterio_in.limite_caracteres,
                            ordem=ordem_c,
                        )
                    criterio_ids_mantidos.add(criterio.id)

                for criterio_id in set(criterios_atuais) - criterio_ids_mantidos:
                    self.criterio_repo.delete(criterio_id)

            for secao_id in set(secoes_atuais) - ids_mantidos:
                self.secao_repo.delete(secao_id)

        return GetDesempenhoFormularioUseCase(self.db).execute(tipo, papel)

    def _recusar_remocao_de_criterio_respondido(self, formulario_id: int, secoes_in) -> None:
        """Editar no lugar não pode apagar critério que já tem resposta: a
        nota aponta pra ele. Quem precisa tirar o critério escolhe "só pra
        futuros", que congela esta versão pro lote aberto."""
        ids_que_ficam = {c.id for sec in secoes_in for c in sec.criterios if c.id}
        atuais = [c for s in self.secao_repo.get_by_formulario(formulario_id) for c in self.criterio_repo.get_by_secao(s.id)]
        removidos = [c for c in atuais if c.id not in ids_que_ficam]
        com_resposta = self.nota_repo.criterios_com_resposta([c.id for c in removidos])
        if com_resposta:
            nomes = ", ".join(f'"{c.label}"' for c in removidos if c.id in com_resposta)
            raise RegraDeNegocioError(
                f"O critério {nomes} já tem respostas no lote em andamento e não pode ser removido "
                "aplicando ao lote. Escolha \"só para lotes futuros\" pra tirá-lo."
            )

    def _congelar_e_criar_vigente(self, antigo, abertos, request, tipo, papel) -> Optional[dict]:
        """"Só pra futuros": a linha de hoje vira a versão congelada dos
        lotes abertos (as respostas já dadas apontam pros critérios dela), e
        uma linha nova, já com a edição, passa a ser a vigente."""
        for lote in abertos:
            self.lote_formulario_repo.create(lote_id=lote["id"], papel=papel, formulario_id=antigo.id)
        self.formulario_repo.update(antigo.id, vigente=False, congelado_em=agora_utc())

        textos = request.dict(exclude_unset=True, exclude={"secoes", "aplicar_em_abertos"})
        novo = self.formulario_repo.create(
            tipo=tipo,
            papel=papel,
            nota_geral_titulo=textos.get("nota_geral_titulo", antigo.nota_geral_titulo),
            nota_geral_descricao=textos.get("nota_geral_descricao", antigo.nota_geral_descricao),
            comentarios_titulo=textos.get("comentarios_titulo", antigo.comentarios_titulo),
            comentarios_descricao=textos.get("comentarios_descricao", antigo.comentarios_descricao),
            comentarios_aviso=textos.get("comentarios_aviso", antigo.comentarios_aviso),
            vigente=True,
        )
        # Sem `secoes` no request, a nova versão nasce como cópia da antiga.
        secoes_in = request.secoes
        if secoes_in is None:
            secoes_in = [
                SecaoInput(
                    titulo=s.titulo,
                    descricao=s.descricao,
                    criterios=[
                        CriterioInput(
                            label=c.label,
                            descricao=c.descricao,
                            tipo_resposta=c.tipo_resposta,
                            limite_caracteres=c.limite_caracteres,
                        )
                        for c in self.criterio_repo.get_by_secao(s.id)
                    ],
                )
                for s in self.secao_repo.get_by_formulario(antigo.id)
            ]
        # Os ids do request são da versão antiga: aqui tudo nasce novo.
        for ordem, secao_in in enumerate(secoes_in):
            secao = self.secao_repo.create(
                formulario_id=novo.id, titulo=secao_in.titulo, descricao=secao_in.descricao, ordem=ordem
            )
            for ordem_c, criterio_in in enumerate(secao_in.criterios):
                self.criterio_repo.create(
                    secao_id=secao.id,
                    label=criterio_in.label,
                    descricao=criterio_in.descricao,
                    tipo_resposta=criterio_in.tipo_resposta,
                    limite_caracteres=criterio_in.limite_caracteres,
                    ordem=ordem_c,
                )
        return GetDesempenhoFormularioUseCase(self.db).execute(tipo, papel)
