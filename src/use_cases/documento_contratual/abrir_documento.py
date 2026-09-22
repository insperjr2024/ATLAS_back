"""Abrir um documento jurídico novo dentro de um projeto (§ Contratos).

⭐ 2026-09-16 — porta de `AvancarStatusUseCase.tipos_disponiveis`/`criar_contrato`
(`contratos-backend`), adaptado: a "pasta" é o próprio `ProjetoModel` do
ATLAS (não existe mais uma pasta separada), e a herança de dados cai para
"em branco" quando não há Contrato de Prestação na plataforma para herdar
— a Coleta de Dados (upload de .docx com extração automática) ainda não foi
portada, então não há um segundo lugar de onde puxar.
"""

from typing import List

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.dados_documento_contratual import montar_dados_iniciais
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_documento_contratual import (
    TIPO_RAIZ,
    TIPOS_ADICIONAIS,
    TipoDocumentoContratual,
    StatusDocumentoContratual,
    ordenar_por_tipo,
)


class AbrirDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.projetos = ProjetoRepository(db)
        self.documentos = DocumentoContratualRepository(db)

    def tipos_disponiveis(self, projeto_id: int) -> List[str]:
        """Tipos que ainda podem ser abertos neste projeto.

        - o projeto nasce sem nenhum documento — o Contrato de Prestação é a
          raiz, mas não é pré-requisito: um projeto institucional (sem venda
          — ex.: Uso de Imagem de um ex-membro pro site) pode nunca ter um
          Contrato de Prestação e ainda assim precisar de NDA/Uso de
          Imagem/Aditivo;
        - um documento de cada tipo por projeto (a constraint
          `uq_documento_contratual_projeto_tipo` já garante isso no banco;
          aqui é só o que se OFERECE pra abrir);
        - o TEP não depende do Contrato de Prestação existir — projetos cujo
          PS foi tratado fora da plataforma também precisam ser encerrados
          com TEP. Quem pode de fato abrir é checado no router, não aqui.
        """
        existentes = {d.tipo for d in self.documentos.list_by_projeto(projeto_id)}

        disponiveis = []
        if TIPO_RAIZ.value not in existentes:
            disponiveis.append(TIPO_RAIZ.value)
        for tipo in TIPOS_ADICIONAIS:
            if tipo.value in existentes:
                continue
            disponiveis.append(tipo.value)
        return [str(t) for t in ordenar_por_tipo(disponiveis)]

    def execute(self, projeto_id: int, tipo: str):
        projeto = self.projetos.get_by_id(projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado.")

        try:
            TipoDocumentoContratual(tipo)
        except ValueError:
            raise RegraDeNegocioError(f'Tipo de documento desconhecido: "{tipo}".')

        if tipo not in self.tipos_disponiveis(projeto_id):
            raise RegraDeNegocioError(
                f'Não é possível iniciar um documento do tipo "{tipo}" neste projeto agora.'
            )

        raiz = None
        if tipo != TIPO_RAIZ.value:
            raiz = self.documentos.get_by_projeto_e_tipo(projeto_id, TIPO_RAIZ.value)
        dados_iniciais = montar_dados_iniciais(
            tipo, raiz.dados if raiz else None, projeto.nome
        )

        return self.documentos.create(
            projeto_id=projeto_id,
            tipo=tipo,
            status=StatusDocumentoContratual.AGUARDANDO_PREENCHIMENTO.value,
            dados=dados_iniciais,
            confirmado=False,
        )
