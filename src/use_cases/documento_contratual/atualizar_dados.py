"""Editar os dados de um documento jurídico (§ Contratos).

⭐ 2026-09-16 — porta de `PATCH /contratos/{id}` (`contratos-backend/src/app.py`).

⚠ **Duas janelas de edição, não uma.** Quem preencheu (BDR, Coordenador de
Vendas, Diretor de Vendas, Diretora de Projetos — depende do tipo) só corrige
a própria digitação enquanto o documento ainda está "aguardando
preenchimento" e NÃO foi confirmado. Confirmado, a edição vira função de
quem pode gerir o contrato (diretoria ou `pode_elaborar_contratos_proprios`/
`pode_elaborar_qualquer_contrato`, ver `_pode_gerir_documento` no router),
que pode mexer em qualquer status até o cliente aprovar — é o caminho normal
de corrigir algo depois de um "pedido de alteração".

`pode_editar_livre` é quem o ROUTER decidiu que É essa segunda pessoa —
mesmo padrão de `eh_gestao` em `create_candidatura.py`: a permissão fina por
tipo/posse de projeto mora no router, que é onde se sabe quem está chamando;
aqui só a MÁQUINA DE ESTADOS importa.
"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_documento_contratual import STATUS_DADOS_TRAVADOS


class AtualizarDadosDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, documento_id: int, dados: Dict[str, Any], pode_editar_livre: bool = False):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")

        if documento.status in STATUS_DADOS_TRAVADOS:
            raise RegraDeNegocioError(
                "O cliente já aprovou este documento — os dados não podem mais ser editados."
            )

        if not pode_editar_livre:
            if documento.status != "aguardando_preenchimento":
                raise RegraDeNegocioError(
                    "Só quem preencheu pode editar, e só enquanto o documento está "
                    '"aguardando preenchimento". Depois de confirmado, a edição é com o Jurídico.'
                )
            if documento.confirmado:
                raise RegraDeNegocioError(
                    "Este documento já foi confirmado — peça ao Jurídico para editar."
                )

        return self.documentos.update(documento_id, dados=dados)
