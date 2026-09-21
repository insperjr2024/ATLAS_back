from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.posicao_permissao.get_posicao_permissao import serializar_posicao_permissao
from src.utils.exceptions import CODIGO_ULTIMO_ADMINISTRADOR, RegraDeNegocioError


class UpdatePosicaoPermissaoRequest(BaseModel):
    #: ⭐ 2026-09-16, a pedido — só cargo criado pela tela (`e_padrao=False`)
    #: pode ser renomeado. O SLUG (`posicao`, a chave que `usuario.posicao` e
    #: `usuario.cargo_extra` referenciam) nunca muda aqui, só o rótulo.
    nome: Optional[str] = None
    pode_criar_projeto: Optional[bool] = None
    pode_editar_equipe: Optional[bool] = None
    pode_gerir_membros: Optional[bool] = None
    pode_marcar_kickoff: Optional[bool] = None
    pode_definir_cronograma: Optional[bool] = None
    pode_criar_tarefa: Optional[bool] = None
    pode_mover_editar_tarefa: Optional[bool] = None
    pode_ver_proprios_projetos: Optional[bool] = None
    pode_ver_monitoramento: Optional[bool] = None
    pode_administrar_desempenho: Optional[bool] = None
    pode_editar_formularios_desempenho: Optional[bool] = None
    pode_administrar_configuracoes: Optional[bool] = None
    pode_ver_todos_projetos: Optional[bool] = None
    pode_ver_dashboard_bancas: Optional[bool] = None
    pode_ver_historico_projetos: Optional[bool] = None
    pode_ver_tarefas_gerais: Optional[bool] = None
    pode_ver_cronogramas_gerais: Optional[bool] = None
    pode_configurar_colunas: Optional[bool] = None
    pode_aprovar_pedidos: Optional[bool] = None
    pode_administrar_permissoes: Optional[bool] = None
    pode_gerir_calendarios_base: Optional[bool] = None
    pode_responsavel_por_vendas: Optional[bool] = None
    pode_coordenar_vendas: Optional[bool] = None
    pode_gerar_documento_juridico: Optional[bool] = None
    pode_editar_documento_juridico: Optional[bool] = None
    pode_marcar_documento_assinado: Optional[bool] = None
    pode_ver_repositorio_contratos: Optional[bool] = None
    pode_ver_painel_contratos: Optional[bool] = None
    pode_importar_documento_antigo: Optional[bool] = None
    pode_solicitar_tep: Optional[bool] = None


class UpdatePosicaoPermissaoUseCase:
    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def _garantir_administrador_remanescente(self, posicao: str, data: dict):
        """⭐ A plataforma nunca pode ficar sem quem edite permissões.

        `pode_administrar_permissoes` é a única caixa que se auto-tranca: ela
        é o que dá acesso a ESTA tela, então desligar a última deixa a
        plataforma num estado que a própria plataforma não conserta — só
        mexendo no banco à mão.

        A regra não é "sobrar uma POSIÇÃO com a caixa", e sim sobrar uma
        PESSOA: posição marcada sem ninguém ativo dentro dela é uma porta que
        não abre. A diretoria pode continuar tirando a caixa de si mesma, o
        que é legítimo (delegar e sair), desde que outra pessoa ativa fique
        com ela.
        """
        if data.get("pode_administrar_permissoes") is not False:
            return

        restantes = [
            p.posicao
            for p in self.repository.get_all()
            if p.posicao != posicao and p.pode_administrar_permissoes
        ]
        if restantes and any(
            u.status == "ativo" for u in self.usuario_repository.get_por_posicoes(*restantes)
        ):
            return

        raise RegraDeNegocioError(
            "Esta é a última posição com pessoas ativas que podem editar permissões. "
            "Desmarcar deixaria a plataforma sem ninguém capaz de reabrir esta tela — "
            "conceda a permissão a outra posição antes de tirá-la desta.",
            codigo=CODIGO_ULTIMO_ADMINISTRADOR,
        )

    def execute(self, posicao: str, request: UpdatePosicaoPermissaoRequest):
        data = request.model_dump(exclude_unset=True)

        if "nome" in data:
            registro_atual = self.repository.get_by_posicao(posicao)
            if not registro_atual:
                return None
            if registro_atual.e_padrao:
                raise RegraDeNegocioError(
                    "Os 6 cargos padrão da plataforma não podem ser renomeados."
                )
            nome = data["nome"].strip()
            if not nome:
                raise RegraDeNegocioError("Informe um nome para o cargo")
            data["nome"] = nome

        self._garantir_administrador_remanescente(posicao, data)
        registro = self.repository.update(posicao, **data)
        if not registro:
            return None
        return serializar_posicao_permissao(registro)
