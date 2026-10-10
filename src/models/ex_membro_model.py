"""Ex-membros em destaque do SITE INSTITUCIONAL (2026-10-09, a pedido).

A seção "Ex-membros" de insperjunior.com era uma lista fixa no código do
site: cada novo ex-membro era um PR. Agora a lista mora aqui e a diretoria
edita pela aba Institucional do ATLAS (caixa `pode_acessar_institucional`).
O site lê por uma rota PÚBLICA só de leitura (`/publico/ex-membros`): quem
visita o site não tem conta no ATLAS, então a leitura não pode exigir login
— ver `routers/institucional.py`.

⚠ Tudo aqui é conteúdo PÚBLICO por definição (é o que vai pro site). Nada
de e-mail, WhatsApp ou qualquer dado que o ex-membro não tenha dado pra
publicar. O serializador público lista campo a campo o que sai.

Textos em dois idiomas (o site tem PT/EN): os campos `_en` são opcionais e,
vazios, o site mostra o PT.

A foto fica no banco (`LargeBinary`), não em disco: o Railway não tem disco
persistente, e é o mesmo caminho que `usuario.foto` e o arquivo de contratos
já seguem. Entra sempre como JPEG já redimensionado pelo use case (lado
maior ≤ 900px), então ~50–150 KB por pessoa. `foto_versao` sobe a cada troca
pra furar o cache do navegador na URL pública da foto.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.sql import func
from src.database.database import Base


class ExMembroModel(Base):
    __tablename__ = "ex_membro"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    cargo_pt = Column(String(150), nullable=False)
    cargo_en = Column(String(150), nullable=True)
    area_pt = Column(String(150), nullable=True)
    area_en = Column(String(150), nullable=True)
    empresa = Column(String(150), nullable=False)
    #: Só quando o nome muda em inglês (ex.: "Empreendedorismo" → "Entrepreneurship").
    empresa_en = Column(String(150), nullable=True)
    depoimento_pt = Column(Text, nullable=True)
    depoimento_en = Column(Text, nullable=True)
    linkedin = Column(String(300), nullable=True)
    foto = Column(LargeBinary, nullable=True)
    foto_versao = Column(Integer, nullable=False, default=0, server_default="0")
    #: Ordem de exibição no site (menor primeiro). Os 8 primeiros PUBLICADOS
    #: vão pro carrossel; o resto só aparece em "Ver todos" — regra do site.
    ordem = Column(Integer, nullable=False, default=0, server_default="0", index=True)
    #: Desmarcado = continua cadastrado, mas sai do site (e da rota pública).
    publicado = Column(Boolean, nullable=False, default=True, server_default="1")
    criado_por = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
