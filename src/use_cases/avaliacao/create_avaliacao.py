from sqlalchemy.orm import Session
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.exceptions import RegraDeNegocioError
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta


class CreateAvaliacaoRequest(BaseModel):
    banca_id: int
    formulario_id: int
    status: str = "rascunho"
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None
    # Bloco 1 do formulário — ver o docstring de AvaliacaoModel.
    nome_avaliador: Optional[str] = None
    tipo_avaliador: Optional[str] = None
    projeto_avaliado: Optional[str] = None
    escopo_avaliado_id: Optional[int] = None
    escopo_avaliado_outro: Optional[str] = None


class CreateAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)

    def execute(self, request: CreateAvaliacaoRequest, avaliador_id: int):
        banca = self.banca_repository.get_by_id(request.banca_id)

        # 🔒 Só quem foi ESCALADO para esta banca avalia (§8).
        #
        # ⚠ Não era checado — qualquer pessoa logada podia criar uma avaliação
        # para qualquer banca. Um estranho ao projeto deixaria nota e feedback
        # numa banca de outro time, e a pessoa avaliada não teria como saber
        # que aquela opinião não vinha de quem esteve lá.
        candidaturas = self.candidatura_repository.get_by_banca(request.banca_id)
        if not any(c.usuario_id == avaliador_id for c in candidaturas):
            raise RegraDeNegocioError(
                "Você não foi escalado para esta banca e não pode avaliá-la"
            )

        if banca and banca.realizado_em:
            prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
            if datetime.now() > prazo:
                raise RegraDeNegocioError(
                    "O prazo de 2 dias para avaliar esta banca já passou"
                )

        # ⭐ A avaliação nasce carimbada com a SESSÃO em curso (§9). Carimbar na
        # criação, e não na submissão, é o que faz um rascunho aberto durante a
        # 1ª banca e enviado depois continuar pertencendo à 1ª — se o carimbo
        # fosse no envio, esse voto migraria para a 2ª sem ninguém pedir.
        corrente = self.sessao_repository.get_corrente(request.banca_id)
        sessao = corrente.numero if corrente else 1

        # 🔒 Uma avaliação por pessoa por sessão, e enviada não se retoma.
        #
        # 📐 Barra só o que JÁ FOI SUBMETIDO. Rascunho duplicado continua
        # podendo nascer — o front cria a avaliação ao abrir o formulário, e
        # quem abre duas vezes não está tentando burlar nada.
        ja_enviou = any(
            a.avaliador_id == avaliador_id and a.status == "submetida"
            for a in self.repository.get_by_banca(request.banca_id, sessao)
        )
        if ja_enviou:
            raise RegraDeNegocioError(
                "Você já enviou sua avaliação desta banca — não pode ser refeita"
            )

        avaliacao = self.repository.create(
            banca_id=request.banca_id,
            avaliador_id=avaliador_id,
            formulario_id=request.formulario_id,
            sessao=sessao,
            status=request.status,
            comentario_feedback=request.comentario_feedback,
            submetida_em=request.submetida_em,
            nome_avaliador=request.nome_avaliador,
            tipo_avaliador=request.tipo_avaliador,
            projeto_avaliado=request.projeto_avaliado,
            escopo_avaliado_id=request.escopo_avaliado_id,
            escopo_avaliado_outro=request.escopo_avaliado_outro,
        )
        return {
            "id": avaliacao.id,
            "banca_id": avaliacao.banca_id,
            "avaliador_id": avaliacao.avaliador_id,
            "formulario_id": avaliacao.formulario_id,
            "status": avaliacao.status,
            "nome_avaliador": avaliacao.nome_avaliador,
            "tipo_avaliador": avaliacao.tipo_avaliador,
            "projeto_avaliado": avaliacao.projeto_avaliado,
            "escopo_avaliado_id": avaliacao.escopo_avaliado_id,
            "escopo_avaliado_outro": avaliacao.escopo_avaliado_outro,
        }