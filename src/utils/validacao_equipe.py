"""Quem pode ocupar cada papel na equipe de um projeto (§6.3).

Os dois papéis aceitam posição igual ou acima na hierarquia ATÉ gerente
(gerente > coordenador > consultor) — 2026-08-07: um gerente que também
coordena projeto na prática (ex.: Murilo) pode ocupar a vaga de coordenador
sem precisar virar "coordenador" de posição de verdade, o que trocaria as
permissões dele de gerente pelas de coordenador. **Diretor fica de fora das
duas listas de propósito**: supervisiona, não é alocado na equipe de
execução de projeto nenhum. O que NUNCA abre, pra ninguém, é o sentido
inverso: consultor não vira coordenador de projeto sem ser promovido de
posição de verdade — isso é o §10, não uma vaga de equipe.

Coordenador e gerente continuam elegíveis à cadeira de consultor: o que
2026-08-12 fechou foi o AUTOATENDIMENTO — eles não pedem para entrar em
projeto (ver `solicitacao_projeto.py`), mas a gestão pode alocá-los como
consultor normalmente.

Nada aqui olha os OUTROS projetos da pessoa de propósito: coordenador e
consultor podem estar alocados em quantos projetos forem necessários — a
validação é sempre dentro do projeto que está sendo salvo. A escala de
`situacao_carga` é recomendação da diretoria, não teto.

**A equipe pode estar vazia** (2026-08-13). Antes exigia-se 1 coordenador e
pelo menos 1 consultor já no cadastro, e isso invertia a ordem real das
coisas: o projeto é vendido antes de o time existir, e quem cadastrava era
obrigado a inventar nomes só para o formulário passar — nomes que depois
ficavam no histórico de `projeto_membro` como se aquelas pessoas tivessem
mesmo participado (§10 não deixa reescrever isso). O time é montado depois,
em Vagas ou na Visão geral, e a mesma regra vale lá: dá para salvar só o
coordenador, só consultores, ou ninguém.

**Mais de um coordenador é permitido** (2026-08-20, pedido direto) — projeto
grande às vezes divide a coordenação entre duas pessoas. O que continua
barrado é o que é erro de verdade — posição que não cabe no papel, e a
mesma pessoa ocupando os dois papéis no mesmo projeto.
"""

from src.utils.exceptions import RegraDeNegocioError

# Espelha `POSICOES_ELEGIVEIS_CONSULTOR`/`POSICOES_ELEGIVEIS_COORDENADOR` de
# `MemberPicker.tsx`. Diretor fica de fora das duas — só supervisiona.
POSICOES_ELEGIVEIS_CONSULTOR = ("consultor", "coordenador", "gerente")
POSICOES_ELEGIVEIS_COORDENADOR = ("coordenador", "gerente")

ROTULO_POSICAO = {
    "diretor_projetos": "diretor(a) de projetos",
    "diretor_pessoas": "diretor(a) de gestão de pessoas",
    "diretor": "diretor(a)",
    "gerente": "gerente de frente",
    "coordenador": "coordenador(a)",
    "consultor": "consultor(a)",
}


def validar_equipe(equipe, usuario_repository, max_consultores=None):
    """Valida a equipe inteira antes de gravar qualquer linha.

    Roda por completo em `create_projeto` e `update_equipe_projeto` para os
    dois caminhos dizerem exatamente a mesma coisa. Equipe vazia passa — ver
    a docstring do módulo.
    """
    coordenadores = [m for m in equipe if m.papel == "coordenador"]

    # Teto de consultores: só entra se o chamador passar o número, porque
    # `create_projeto` grava `max_consultores` na mesma chamada em que valida
    # a equipe (não dá pra ler de volta um projeto que ainda não existe).
    if max_consultores is not None:
        consultores = [m for m in equipe if m.papel == "consultor"]
        if len(consultores) > max_consultores:
            raise RegraDeNegocioError(
                f"A equipe tem {len(consultores)} consultores, mas o teto do projeto é "
                f"{max_consultores}. Aumente o teto ou tire alguém antes de salvar."
            )

    # Depois da checagem por membro (papel/posição de CADA um) — checagem
    # agregada primeiro escondia o motivo de verdade: toda entrada inválida
    # virava o erro agregado em vez do erro específico daquele membro.
    for membro in equipe:
        if membro.papel not in ("coordenador", "consultor"):
            raise RegraDeNegocioError(f"Papel inválido: {membro.papel}")

        usuario = usuario_repository.get_by_id(membro.usuario_id)
        if not usuario:
            raise RegraDeNegocioError(f"Usuário {membro.usuario_id} não encontrado")

        if membro.papel == "coordenador":
            if usuario.posicao not in POSICOES_ELEGIVEIS_COORDENADOR:
                raise RegraDeNegocioError(
                    f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                    f"e não pode entrar como coordenador do projeto."
                )
        elif usuario.posicao not in POSICOES_ELEGIVEIS_CONSULTOR:
            raise RegraDeNegocioError(
                f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                f"e não pode entrar como consultor do projeto."
            )

    # A mesma pessoa nos dois papéis. Só o front barrava isso; com a equipe
    # podendo ser montada aos poucos, em telas diferentes, a chance de o
    # coordenador voltar como consultor numa segunda passada cresceu — e o
    # resultado seriam duas linhas ativas de `projeto_membro` para a mesma
    # pessoa, que a contagem de consultores alocados leria como duas.
    ids_consultores = {m.usuario_id for m in equipe if m.papel == "consultor"}
    for coordenador in coordenadores:
        if coordenador.usuario_id in ids_consultores:
            usuario = usuario_repository.get_by_id(coordenador.usuario_id)
            nome = usuario.nome if usuario else coordenador.usuario_id
            raise RegraDeNegocioError(
                f"{nome} não pode ser coordenador e consultor do mesmo projeto."
            )
