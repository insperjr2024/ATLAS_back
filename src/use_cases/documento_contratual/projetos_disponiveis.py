"""A lista de projetos do passo "escolher projeto" do assistente de Novo
Contrato (§ Contratos, 2026-09-22).

⭐ Não é `GET /projetos` (recortado por `aplicar_recorte_visao`, só amplia
com `pode_ver_todos_projetos` — ver o docstring de lá, "a única caixa que
muda quais projetos aparecem"). Aqui o critério é o mesmo de
`_pode_abrir_documento`/`_pode_elaborar_por_caixa_nova` no router: quem tem
`pode_elaborar_qualquer_contrato` abre documento em QUALQUER projeto, então
a lista tem que mostrar todos — senão a caixa existe mas a tela nunca deixa
usar (a pessoa nem enxerga o projeto pra escolher).
"""

from typing import List

from sqlalchemy.orm import Session

from src.middlewares.authorization import eh_diretoria_de_projetos, usuario_tem_permissao
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository


class ProjetosDisponiveisParaDocumentoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.projetos = ProjetoRepository(db)
        self.vendedores = ProjetoVendedorRepository(db)

    def execute(self, usuario, tipo: str) -> List[dict]:
        candidatos = [
            p for p in self.projetos.get_all() if not p.institucional and p.arquivado_em is None
        ]

        if eh_diretoria_de_projetos(usuario) or usuario_tem_permissao(
            usuario, self.db, "pode_elaborar_qualquer_contrato"
        ):
            return self._serializar(candidatos)

        # NDA/Uso de Imagem/Aditivo com `pode_responsavel_por_vendas`: mesma
        # caixa irrestrita que `_pode_abrir_documento` usa pra estes tipos —
        # não recorta por projeto.
        if tipo in ("nda", "uso_imagem", "aditivo") and usuario_tem_permissao(
            usuario, self.db, "pode_responsavel_por_vendas"
        ):
            return self._serializar(candidatos)

        # Contrato de Prestação com `pode_criar_projeto`: mesma caixa
        # irrestrita que `_pode_abrir_documento` usa pra este tipo.
        if tipo == "contrato" and usuario_tem_permissao(usuario, self.db, "pode_criar_projeto"):
            return self._serializar(candidatos)

        # TEP e o resto: só quem `pode_elaborar_contratos_proprios` E vendeu
        # o projeto — a mesma dupla de `_pode_elaborar_por_caixa_nova`.
        if usuario_tem_permissao(usuario, self.db, "pode_elaborar_contratos_proprios"):
            vendidos = {v.projeto_id for v in self.vendedores.filter_by(usuario_id=usuario.id)}
            return self._serializar([p for p in candidatos if p.id in vendidos])

        return []

    def _serializar(self, projetos) -> List[dict]:
        return [{"id": p.id, "nome": p.nome, "cliente": p.cliente} for p in projetos]
