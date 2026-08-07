"""Quem pode ocupar cada papel na equipe de um projeto (§6.3).

Coordenador é estrito: só quem É coordenador na plataforma (§3). Consultor
aceita posição igual ou acima na hierarquia (diretor > gerente > coordenador
> consultor) — um coordenador que também atua como consultor num outro
projeto pode ocupar essa vaga, nunca o contrário (consultor não vira
coordenador de um projeto sem ser promovido de posição de verdade, isso é o
§10). Diretoria e gerência só ocupam vaga como consultor; como coordenador,
nunca.

Nada aqui olha os OUTROS projetos da pessoa de propósito: coordenador e
consultor podem estar alocados em quantos projetos forem necessários — a
validação é sempre dentro do projeto que está sendo salvo.
"""

from src.utils.exceptions import RegraDeNegocioError

# Espelha `POSICOES_ELEGIVEIS_CONSULTOR` de `MemberPicker.tsx`.
POSICOES_ELEGIVEIS_CONSULTOR = ("consultor", "coordenador", "gerente", "diretor")

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

    # Depois da checagem por membro (papel/posição de CADA um) — checagem
    # agregada primeiro escondia o motivo de verdade quando a equipe de
    # teste também não tinha consultor: toda entrada inválida virava "falta
    # consultor" em vez do erro específico daquele membro.
    for membro in equipe:
        if membro.papel not in ("coordenador", "consultor"):
            raise RegraDeNegocioError(f"Papel inválido: {membro.papel}")

        usuario = usuario_repository.get_by_id(membro.usuario_id)
        if not usuario:
            raise RegraDeNegocioError(f"Usuário {membro.usuario_id} não encontrado")

        if membro.papel == "coordenador":
            if usuario.posicao != "coordenador":
                raise RegraDeNegocioError(
                    f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                    f"e não pode entrar como coordenador do projeto — esse papel é "
                    f"só de quem tem a posição {ROTULO_POSICAO['coordenador']}."
                )
        elif usuario.posicao not in POSICOES_ELEGIVEIS_CONSULTOR:
            raise RegraDeNegocioError(
                f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                f"e não pode entrar como consultor do projeto."
            )

    consultores = [m for m in equipe if m.papel == "consultor"]
    if len(consultores) == 0:
        raise RegraDeNegocioError("O projeto precisa de pelo menos 1 consultor")
