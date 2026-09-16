from typing import Optional, Set

from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository


def serializar_usuario(
    usuario,
    projetos_alocados: int = 0,
    posicoes_responsaveis_por_vendas: Optional[Set[str]] = None,
):
    """`projetos_alocados` é a carga atual da pessoa (§7.3), usada na hora de
    montar a equipe de um projeto. O padrão 0 vale para quem acabou de ser
    cadastrado e ainda não entrou em projeto nenhum.

    `posicoes_responsaveis_por_vendas` vem de fora (`PosicaoPermissaoRepository.
    get_posicoes_com_permissao`) pra não virar uma query por pessoa quando
    `ListUsuariosUseCase` serializa a lista inteira.
    """
    posicoes_vendas = posicoes_responsaveis_por_vendas or set()
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email_insper": usuario.email_insper,
        "posicao": usuario.posicao,
        "status": usuario.status,
        "ativo": usuario.ativo,
        # ⭐ 2026-09-16 — substitui `usuario.coordenador_vendas`: "coordenador
        # de vendas" virou cargo de verdade, escolhido em `posicao`.
        #
        # ⭐ 2026-09-16 — substitui `usuario.bdr`. A ÚNICA situação em que a
        # pessoa acumula duas posições: a principal (sempre "consultor" na
        # prática) e esta, opcional. Ver `usuario_model.py`.
        "cargo_extra": usuario.cargo_extra,
        # Computado (posição base OU `cargo_extra`, permissão `pode_
        # responsavel_por_vendas`) — quem tem isto entra na lista "quem vendeu
        # o projeto" do cadastro. Substitui o antigo `bdr`/`coordenador_
        # vendas` crus, que o front filtrava sozinho.
        "responsavel_por_vendas": (
            usuario.posicao in posicoes_vendas or usuario.cargo_extra in posicoes_vendas
        ),
        "semestre_graduacao": usuario.semestre_graduacao,
        # ⭐ "ainda não fez o primeiro acesso": a tela de Membros marca essas
        # linhas e oferece o reenvio da senha provisória.
        "senha_provisoria": usuario.senha_provisoria,
        "projetos_alocados": projetos_alocados,
        "foto": usuario.foto,
    }


class GetUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.posicao_permissao_repository = PosicaoPermissaoRepository(db)

    def execute(self, usuario_id: int):
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        alocados = self.membro_repository.contar_ativos_por_usuario()
        posicoes_vendas = self.posicao_permissao_repository.get_posicoes_com_permissao(
            "pode_responsavel_por_vendas"
        )
        return serializar_usuario(usuario, alocados.get(usuario.id, 0), posicoes_vendas)


class ListUsuariosUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.posicao_permissao_repository = PosicaoPermissaoRepository(db)

    def execute(self, posicao: Optional[str] = None, apenas_ativos: bool = False):
        """⭐ 2026-09-05, corrigido a pedido: `desligado` não some mais daqui.

        Até aqui, só `desligado` desaparecia da lista — a tela de Membros
        promete, pro `ex_membro` E pro `desligado` (mesmo texto, os dois
        juntos): "a participação em projetos passados permanece íntegra".
        Excluir `desligado` daqui quebrava essa promessa por baixo dos panos:
        toda tela que resolve nome a partir de `GET /usuarios` (equipe do
        projeto, tarefas, histórico, avaliações...) parava de achar a pessoa
        e caía no fallback "Usuário {id}" — o nome sumia de todo lugar onde
        ela já tinha participado, mesmo a plataforma dizendo o contrário.

        `ex_membro` nunca teve esse problema porque nunca foi filtrado aqui;
        `desligado` passa a ter o MESMO tratamento — a única saída continua
        sendo `apenas_ativos=True`, pra quem realmente só quer gente ativa."""
        usuarios = self.repository.get_all()
        if posicao:
            usuarios = [u for u in usuarios if u.posicao == posicao]
        if apenas_ativos:
            usuarios = [u for u in usuarios if u.status == "ativo"]
        # Uma consulta agregada para a lista inteira, não uma por pessoa.
        alocados = self.membro_repository.contar_ativos_por_usuario()
        posicoes_vendas = self.posicao_permissao_repository.get_posicoes_com_permissao(
            "pode_responsavel_por_vendas"
        )
        return [
            serializar_usuario(u, alocados.get(u.id, 0), posicoes_vendas) for u in usuarios
        ]