"""Quem pode ocupar cada papel na equipe de um projeto (§6.3).

A posição na plataforma (§3) e o papel no projeto são a mesma dimensão aqui:
coordenador coordena, consultor consulta. Diretoria e gerência acompanham o
projeto pelo recorte de visão, sem ocupar vaga na equipe.

Nada aqui olha os OUTROS projetos da pessoa de propósito: coordenador e
consultor podem estar alocados em quantos projetos forem necessários — a
validação é sempre dentro do projeto que está sendo salvo.
"""

from src.utils.exceptions import RegraDeNegocioError

# papel no projeto → posição que o usuário precisa ter para ocupá-lo
POSICAO_EXIGIDA_POR_PAPEL = {
    "coordenador": "coordenador",
    "consultor": "consultor",
}

ROTULO_POSICAO = {
    "diretor": "diretor(a)",
    "gerente": "gerente de frente",
    "coordenador": "coordenador(a)",
    "consultor": "consultor(a)",
}


def validar_equipe(equipe, usuario_repository):
    """Valida a equipe inteira antes de gravar qualquer linha.

    Roda por completo em `create_projeto` e `update_equipe_projeto` para os
    dois caminhos dizerem exatamente a mesma coisa.
    """
    coordenadores = [m for m in equipe if m.papel == "coordenador"]
    if len(coordenadores) != 1:
        raise RegraDeNegocioError("O projeto precisa de exatamente 1 coordenador")

    for membro in equipe:
        posicao_exigida = POSICAO_EXIGIDA_POR_PAPEL.get(membro.papel)
        if posicao_exigida is None:
            raise RegraDeNegocioError(f"Papel inválido: {membro.papel}")

        usuario = usuario_repository.get_by_id(membro.usuario_id)
        if not usuario:
            raise RegraDeNegocioError(f"Usuário {membro.usuario_id} não encontrado")

        if usuario.posicao != posicao_exigida:
            raise RegraDeNegocioError(
                f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                f"e não pode entrar como {membro.papel} do projeto — esse papel é "
                f"só de quem tem a posição {ROTULO_POSICAO[posicao_exigida]}."
            )
