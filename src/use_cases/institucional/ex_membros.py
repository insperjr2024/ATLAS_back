"""Ex-membros em destaque do site. Ver `models/ex_membro_model.py`.

Dois leitores, dois serializadores:

- `serializar_publico` — o que o SITE recebe, sem login. Lista campo a campo
  de propósito: é a única barreira entre a tabela e a internet, então nada
  entra aqui por `__dict__`/`vars()`. Hoje tudo na tabela é publicável, mas
  o dia em que alguém acrescentar um campo interno ele não vaza sozinho.
- `serializar_admin` — o que a aba Institucional recebe. Hoje é o público
  mais `publicado`/`criado_em`/`atualizado_em`.

A foto não vai no JSON (nem em base64): sai por rota própria, como imagem,
pra o navegador cachear. Pública (`/publico/ex-membros/{id}/foto`) só pra
quem está publicado; a aba Institucional usa a autenticada.
"""

import io
import json
from pathlib import Path
from typing import List, Optional

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.ex_membro_model import ExMembroModel
from src.repositories.ex_membro_repository import ExMembroRepository
from src.utils.exceptions import RegraDeNegocioError

# ─── Foto ───────────────────────────────────────────────────────────────────

#: Lado maior da foto guardada. O site mostra 108px no card e ~480px no modal
#: (retina dobra), então 900 sobra sem virar megabyte.
FOTO_LADO_MAXIMO = 900
FOTO_QUALIDADE_JPEG = 86
#: Upload bruto. É gordura: 1,6 MB era a maior foto que o site tinha.
FOTO_TAMANHO_MAXIMO_UPLOAD = 8 * 1024 * 1024
FOTO_MIME = "image/jpeg"


def normalizar_foto(conteudo: bytes) -> bytes:
    """Qualquer imagem que o Pillow abra → JPEG RGB com lado ≤ 900px.

    PNG com transparência ganha fundo branco (o site exibe em círculo sobre
    fundo claro). EXIF de rotação é aplicado antes, senão foto de celular
    chega deitada."""
    if len(conteudo) > FOTO_TAMANHO_MAXIMO_UPLOAD:
        raise RegraDeNegocioError("A foto é grande demais (máximo 8 MB).")
    try:
        imagem = Image.open(io.BytesIO(conteudo))
        imagem.load()
    except (UnidentifiedImageError, OSError):
        raise RegraDeNegocioError("O arquivo não é uma imagem válida (use JPG ou PNG).")

    from PIL import ImageOps

    imagem = ImageOps.exif_transpose(imagem) or imagem
    if imagem.mode in ("RGBA", "LA", "P"):
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        fundo.paste(imagem.convert("RGBA"), mask=imagem.convert("RGBA").split()[-1])
        imagem = fundo
    else:
        imagem = imagem.convert("RGB")
    imagem.thumbnail((FOTO_LADO_MAXIMO, FOTO_LADO_MAXIMO))

    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=FOTO_QUALIDADE_JPEG, optimize=True)
    return saida.getvalue()


# ─── Serialização ───────────────────────────────────────────────────────────

def _limpar(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def serializar_publico(m: ExMembroModel) -> dict:
    """⚠ Lista explícita. Nada de `vars(m)` — ver docstring do módulo."""
    return {
        "id": m.id,
        "nome": m.nome,
        "cargo_pt": m.cargo_pt,
        "cargo_en": m.cargo_en,
        "area_pt": m.area_pt,
        "area_en": m.area_en,
        "empresa": m.empresa,
        "empresa_en": m.empresa_en,
        "depoimento_pt": m.depoimento_pt,
        "depoimento_en": m.depoimento_en,
        "linkedin": m.linkedin,
        "ordem": m.ordem,
        # `tem_foto` em vez dos bytes: o site monta a URL da foto a partir do
        # id, e `foto_versao` entra na URL pra furar o cache quando ela troca.
        "tem_foto": m.foto is not None,
        "foto_versao": m.foto_versao,
    }


def serializar_admin(m: ExMembroModel) -> dict:
    dados = serializar_publico(m)
    dados.update(
        {
            "publicado": m.publicado,
            "criado_em": m.criado_em.isoformat() if m.criado_em else None,
            "atualizado_em": m.atualizado_em.isoformat() if m.atualizado_em else None,
        }
    )
    return dados


# ─── Leitura ────────────────────────────────────────────────────────────────

class ListarPublicadosUseCase:
    """A rota pública do site."""

    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self) -> List[dict]:
        return [serializar_publico(m) for m in self.repository.listar_publicados()]


class ListarTodosUseCase:
    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self) -> List[dict]:
        return [serializar_admin(m) for m in self.repository.listar_todos()]


class GetFotoUseCase:
    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int, *, apenas_publicado: bool) -> bytes:
        m = self.repository.get_by_id(ex_membro_id)
        if not m or m.foto is None or (apenas_publicado and not m.publicado):
            raise RegraDeNegocioError("Foto não encontrada")
        return m.foto


# ─── Escrita ────────────────────────────────────────────────────────────────

class ExMembroRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    cargo_pt: str = Field(min_length=2, max_length=150)
    cargo_en: Optional[str] = Field(default=None, max_length=150)
    area_pt: Optional[str] = Field(default=None, max_length=150)
    area_en: Optional[str] = Field(default=None, max_length=150)
    empresa: str = Field(min_length=1, max_length=150)
    empresa_en: Optional[str] = Field(default=None, max_length=150)
    depoimento_pt: Optional[str] = None
    depoimento_en: Optional[str] = None
    linkedin: Optional[str] = Field(default=None, max_length=300)
    publicado: bool = True


def _normalizar_linkedin(valor: Optional[str]) -> Optional[str]:
    valor = _limpar(valor)
    if not valor:
        return None
    if not valor.lower().startswith(("http://", "https://")):
        valor = "https://" + valor.lstrip("/")
    if "linkedin.com/" not in valor.lower():
        raise RegraDeNegocioError("O link do LinkedIn precisa ser um endereço linkedin.com.")
    return valor


def _campos(request: ExMembroRequest) -> dict:
    return {
        "nome": request.nome.strip(),
        "cargo_pt": request.cargo_pt.strip(),
        "cargo_en": _limpar(request.cargo_en),
        "area_pt": _limpar(request.area_pt),
        "area_en": _limpar(request.area_en),
        "empresa": request.empresa.strip(),
        "empresa_en": _limpar(request.empresa_en),
        "depoimento_pt": _limpar(request.depoimento_pt),
        "depoimento_en": _limpar(request.depoimento_en),
        "linkedin": _normalizar_linkedin(request.linkedin),
        "publicado": request.publicado,
    }


class CriarExMembroUseCase:
    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, request: ExMembroRequest, criado_por: Optional[int]) -> dict:
        # Novo entra no FIM: quem cadastra depois escolhe a posição arrastando.
        registro = self.repository.create(
            **_campos(request), ordem=self.repository.proxima_ordem(), criado_por=criado_por
        )
        return serializar_admin(registro)


class EditarExMembroUseCase:
    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int, request: ExMembroRequest) -> dict:
        registro = self.repository.update(ex_membro_id, **_campos(request))
        if not registro:
            raise RegraDeNegocioError("Ex-membro não encontrado")
        return serializar_admin(registro)


class PublicarExMembroUseCase:
    """Liga/desliga `publicado` sem mexer no resto — o botão rápido da lista."""

    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int, publicado: bool) -> dict:
        registro = self.repository.update(ex_membro_id, publicado=publicado)
        if not registro:
            raise RegraDeNegocioError("Ex-membro não encontrado")
        return serializar_admin(registro)


class ApagarExMembroUseCase:
    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int) -> None:
        if not self.repository.delete(ex_membro_id):
            raise RegraDeNegocioError("Ex-membro não encontrado")


class ReordenarRequest(BaseModel):
    #: Todos os ids, na ordem final. Mandar a lista inteira (e não "mova o 7
    #: pra posição 2") deixa o estado do front e do banco idênticos num
    #: passo só, sem contas de deslocamento nos dois lados.
    ids: List[int]


class ReordenarExMembrosUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ExMembroRepository(db)

    def execute(self, request: ReordenarRequest) -> List[dict]:
        atuais = {m.id: m for m in self.repository.listar_todos()}
        if sorted(request.ids) != sorted(atuais):
            raise RegraDeNegocioError(
                "A lista está desatualizada (alguém cadastrou ou removeu alguém). Recarregue a página."
            )
        for posicao, ex_membro_id in enumerate(request.ids):
            atuais[ex_membro_id].ordem = posicao
        self.db.commit()
        return [serializar_admin(m) for m in self.repository.listar_todos()]


class AtualizarFotoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int, conteudo: bytes) -> dict:
        registro = self.repository.get_by_id(ex_membro_id)
        if not registro:
            raise RegraDeNegocioError("Ex-membro não encontrado")
        registro.foto = normalizar_foto(conteudo)
        registro.foto_versao = (registro.foto_versao or 0) + 1
        self.db.commit()
        self.db.refresh(registro)
        return serializar_admin(registro)


class RemoverFotoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ExMembroRepository(db)

    def execute(self, ex_membro_id: int) -> dict:
        registro = self.repository.get_by_id(ex_membro_id)
        if not registro:
            raise RegraDeNegocioError("Ex-membro não encontrado")
        registro.foto = None
        registro.foto_versao = (registro.foto_versao or 0) + 1
        self.db.commit()
        self.db.refresh(registro)
        return serializar_admin(registro)


# ─── Importação dos 13 que já estavam no site ───────────────────────────────

#: Os ex-membros que o site tinha hardcoded quando esta aba nasceu, com as
#: fotos já no tamanho final. Gerado a partir do repositório do site
#: (Consulting_front: alumniCarousel.tsx + i18n/pages/contactAlumni.ts).
PASTA_INICIAIS = Path(__file__).resolve().parents[2] / "institucional" / "ex_membros_iniciais"


class ImportarIniciaisUseCase:
    """Botão "Importar os ex-membros atuais do site", pra a aba não nascer
    vazia e ninguém precisar redigitar 13 depoimentos. Pula quem já existe
    (pelo nome), então rodar duas vezes não duplica."""

    def __init__(self, db: Session):
        self.repository = ExMembroRepository(db)

    def execute(self, criado_por: Optional[int]) -> dict:
        arquivo = PASTA_INICIAIS / "dados.json"
        if not arquivo.exists():
            raise RegraDeNegocioError("Os dados iniciais não estão disponíveis neste servidor.")
        dados = json.loads(arquivo.read_text(encoding="utf-8"))

        importados, pulados = 0, 0
        ordem = self.repository.proxima_ordem()
        for item in sorted(dados, key=lambda d: d.get("ordem", 0)):
            if self.repository.existe_nome(item["nome"]):
                pulados += 1
                continue
            foto = None
            nome_foto = item.get("foto")
            if nome_foto:
                caminho = PASTA_INICIAIS / "fotos" / nome_foto
                if caminho.exists():
                    foto = caminho.read_bytes()
            self.repository.create(
                nome=item["nome"],
                cargo_pt=item["cargo_pt"],
                cargo_en=item.get("cargo_en"),
                area_pt=item.get("area_pt"),
                area_en=item.get("area_en"),
                empresa=item["empresa"],
                empresa_en=item.get("empresa_en"),
                depoimento_pt=item.get("depoimento_pt"),
                depoimento_en=item.get("depoimento_en"),
                linkedin=item.get("linkedin"),
                foto=foto,
                foto_versao=1 if foto else 0,
                ordem=ordem,
                publicado=True,
                criado_por=criado_por,
            )
            ordem += 1
            importados += 1
        return {"importados": importados, "pulados": pulados}
