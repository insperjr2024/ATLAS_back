import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.storage import pasta_pdi
from src.utils.validar_arquivo_pdi import validar_arquivo_pdi


def pode_enviar_pdi(pasta, mentorado_id: int, current_user, db: Session) -> bool:
    """Diretoria sempre pode (inclusive substituir um envio de encontro, se
    precisar corrigir). Fora isso, só o mentor do mentorado — e só nas pastas
    tipo "encontro": o PDI inicial é upado exclusivamente pela diretoria.
    A checagem é por PASTA (não por item) — todo item de uma pasta segue a
    mesma regra de quem pode enviar."""
    if current_user.posicao in ("diretor", "gerente"):
        return True
    if pasta.tipo != "encontro":
        return False
    vinculo = DesempenhoMentoriaRepository(db).first_by(mentor_id=current_user.id, mentorado_id=mentorado_id)
    return vinculo is not None


class UploadPdiEnvioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.item_repository = DesempenhoPdiItemRepository(db)
        self.pasta_repository = DesempenhoPdiPastaRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)

    def execute(self, item_id: int, mentorado_id: int, arquivo: UploadFile, current_user) -> dict:
        item = self.item_repository.get_by_id(item_id)
        if not item:
            raise RegraDeNegocioError("Item de PDI não encontrado")
        pasta = self.pasta_repository.get_by_id(item.pasta_id)
        if not pasta:
            raise RegraDeNegocioError("Pasta de PDI não encontrada")

        if not pode_enviar_pdi(pasta, mentorado_id, current_user, self.db):
            raise RegraDeNegocioError("Você não tem permissão para enviar neste item")

        conteudo = arquivo.file.read()
        extensao = validar_arquivo_pdi(arquivo.filename or "", conteudo, item.tipo_arquivo)

        pasta_disco = pasta_pdi()
        nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
        (pasta_disco / nome_arquivo).write_bytes(conteudo)

        # Reenviar substitui: apaga o arquivo antigo do disco e faz upsert na
        # linha (mesmo par item+mentorado nunca tem 2 envios ao mesmo tempo).
        anterior = self.envio_repository.get_por_item_e_mentorado(item_id, mentorado_id)
        if anterior:
            arquivo_antigo = pasta_disco / anterior.arquivo_path
            envio = self.envio_repository.update(
                anterior.id,
                enviado_por=current_user.id,
                arquivo_path=nome_arquivo,
                arquivo_nome=(arquivo.filename or "arquivo").strip(),
            )
            if arquivo_antigo.exists():
                arquivo_antigo.unlink()
        else:
            envio = self.envio_repository.create(
                item_id=item_id,
                mentorado_id=mentorado_id,
                enviado_por=current_user.id,
                arquivo_path=nome_arquivo,
                arquivo_nome=(arquivo.filename or "arquivo").strip(),
            )

        return {
            "item_id": envio.item_id,
            "mentorado_id": envio.mentorado_id,
            "arquivo_nome": envio.arquivo_nome,
            "enviado_em": envio.enviado_em,
        }
