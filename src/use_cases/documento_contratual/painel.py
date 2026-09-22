"""A aba Contratos: painel cross-projeto de documentos jurídicos em andamento
(§ Contratos, 2026-09-21).

⭐ Diferente do Repositório (`repositorio.py`, só arquivado) — aqui é fila de
trabalho: quem tem contrato em andamento, o que espera aprovação da
Valentina (Jurídico), o que já foi mandado pro cliente. Cada linha ainda
abre a tela de documento que já existe; este painel é só o ponto de entrada
cross-projeto, não duplica nada da tela em si.

⚠ O recorte de QUEM VÊ O QUÊ mora aqui, não no router — depende de LINHA
(vendedor/coordenador DESTE projeto), não só de permissão global. Mesmo
formato de `ListarAprovacoesUseCase` (`monitoramento/aprovacoes.py`): o use
case recebe `usuario` direto e filtra ele mesmo, em vez do padrão do resto
de `documento_contratual` (permissão pura no router) — ali é sempre "pode
ou não fazer X num documento só"; aqui é "quais LINHAS de uma lista".
"""

from typing import List

from sqlalchemy.orm import Session

from src.middlewares.authorization import eh_diretoria_de_projetos, usuario_tem_permissao
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.utils.status_documento_contratual import ROTULO_TIPO


class PainelContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.membros = ProjetoMembroRepository(db)
        self.vendedores = ProjetoVendedorRepository(db)
        self.frentes = ProjetoFrenteRepository(db)

    def execute(self, usuario) -> List[dict]:
        documentos = self.documentos.list_para_painel()
        visiveis = self._filtrar_visiveis(usuario, documentos)

        # Em lote — a Kanban filtra por frente, e uma consulta por card
        # (potencialmente centenas) seria o mesmo N+1 que `serializar_
        # projeto_resumo` evita em lote pro Kanban de projetos. Institucional
        # (`projeto_id` nulo) fica de fora — não tem frente pra buscar.
        projeto_ids = list({d.projeto_id for d in visiveis if d.projeto_id})
        frentes_por_projeto: dict = {pid: [] for pid in projeto_ids}
        for frente in self.frentes.get_by_projetos(projeto_ids):
            frentes_por_projeto[frente.projeto_id].append(frente.frente_id)

        return [self._serializar(d, frentes_por_projeto.get(d.projeto_id, [])) for d in visiveis]

    def _ve_tudo(self, usuario) -> bool:
        # ⭐ 2026-09-22 — a pedido: as duas caixas de "elaborar contrato"
        # também abrem a aba inteira (vê tudo) — a restrição delas é só na
        # hora de EDITAR (endpoints de ação em `documentos_contratuais.py`),
        # não na listagem.
        return (
            eh_diretoria_de_projetos(usuario)
            or usuario_tem_permissao(usuario, self.db, "pode_editar_documento_juridico")
            or usuario_tem_permissao(usuario, self.db, "pode_elaborar_contratos_proprios")
            or usuario_tem_permissao(usuario, self.db, "pode_elaborar_qualquer_contrato")
        )

    def _filtrar_visiveis(self, usuario, documentos):
        if self._ve_tudo(usuario):
            return documentos

        projeto_ids = list({d.projeto_id for d in documentos if d.projeto_id})
        vendedor_de = {
            v.projeto_id
            for v in self.vendedores.get_by_projetos(projeto_ids)
            if v.usuario_id == usuario.id
        }
        coordenador_de = {
            m.projeto_id
            for m in self.membros.get_by_projetos(projeto_ids, apenas_atuais=True)
            if m.usuario_id == usuario.id and m.papel == "coordenador"
        }

        return [
            d
            for d in documentos
            if (d.tipo == "contrato" and d.projeto_id in vendedor_de)
            or (d.tipo == "tep" and d.projeto_id in coordenador_de)
        ]

    def _serializar(self, documento, frente_ids: List[int]) -> dict:
        return {
            "id": documento.id,
            "projeto_id": documento.projeto_id,
            # Institucional (`projeto_id` nulo): nome/cliente são os campos
            # digitados no próprio documento, não um projeto de verdade.
            "projeto_nome": documento.projeto.nome if documento.projeto_id else documento.nome_projeto_externo,
            "cliente": documento.projeto.cliente if documento.projeto_id else documento.cliente_externo,
            "frente_ids": frente_ids,
            "tipo": documento.tipo,
            "tipo_rotulo": ROTULO_TIPO.get(documento.tipo, "Documento"),
            "status": documento.status,
            # A Kanban precisa disto pra saber se um `aguardando_
            # preenchimento` já está confirmado (2ª coluna) ou não (1ª) —
            # mesma régua de `indiceDaEtapaDocumento` no front.
            "confirmado": documento.confirmado,
            "ultima_versao": self.versoes.ultima_versao(documento.id) or None,
            "criado_em": documento.criado_em,
            "atualizado_em": documento.atualizado_em,
        }
