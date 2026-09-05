from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository


def serializar_usuario(usuario, projetos_alocados: int = 0):
    """`projetos_alocados` é a carga atual da pessoa (§7.3), usada na hora de
    montar a equipe de um projeto. O padrão 0 vale para quem acabou de ser
    cadastrado e ainda não entrou em projeto nenhum."""
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email_insper": usuario.email_insper,
        "posicao": usuario.posicao,
        "status": usuario.status,
        "ativo": usuario.ativo,
        # Só faz sentido para quem é coordenador; a tela de Membros mostra a
        # opção nesse caso. Fora dele o valor não é usado.
        "coordenador_vendas": usuario.coordenador_vendas,
        # Consultor que também prospecta: entra na lista "quem vendeu o
        # projeto" do cadastro. Fora do consultor o valor não é usado.
        "bdr": usuario.bdr,
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

    def execute(self, usuario_id: int):
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        alocados = self.membro_repository.contar_ativos_por_usuario()
        return serializar_usuario(usuario, alocados.get(usuario.id, 0))


class ListUsuariosUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

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
        return [serializar_usuario(u, alocados.get(u.id, 0)) for u in usuarios]