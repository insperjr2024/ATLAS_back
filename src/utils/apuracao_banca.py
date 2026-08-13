"""⭐ O resultado da banca sai do VOTO de quem assistiu (§8), não de uma caneta.

Antes, `banca.resultado` era uma string que alguém digitava — e, na prática,
ninguém digitava: a função existia no front sem nenhum chamador, e as bancas
realizadas ficavam todas sem veredito. Agora quem decide é a maioria dos
avaliadores que estiveram lá.

Função pura de propósito: quem chama carrega os votos e passa. É o mesmo
contrato de `banca_nota.py` e `janela_escopo.py`, e é o que torna as regras de
borda abaixo testáveis sem banco.

⚠ **Não confundir com a NOTA.** `banca_nota.calcular_nota_final` faz a média
das notas por critério e mede QUÃO BEM o trabalho foi feito. O voto responde
outra pergunta, binária: este trabalho pode ir ao cliente? São dimensões
diferentes — dá para ir bem na nota e reprovar por um problema pontual.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

#: O que a apuração pode devolver em `motivo`, para a tela dizer por que ainda
#: não há veredito em vez de mostrar um vazio mudo.
MAIORIA = "maioria"
EMPATE = "empate"
SEM_VOTOS = "sem_votos"
AGUARDANDO = "aguardando"


@dataclass(frozen=True)
class Apuracao:
    """O veredito e a conta que o produziu."""

    #: "aprovada" | "nao_aprovada" | None (ainda não há veredito)
    resultado: Optional[str]
    aprovacoes: int
    reprovacoes: int
    #: Quantos votos se espera receber — o tamanho do eleitorado.
    esperados: int
    motivo: str

    @property
    def decidida(self) -> bool:
        return self.resultado is not None

    @property
    def recebidos(self) -> int:
        return self.aprovacoes + self.reprovacoes


def apurar(
    votos: Iterable[bool],
    esperados: int,
    prazo_vencido: bool = False,
) -> Apuracao:
    """A maioria decide. Duas bordas, e as duas são decisões, não acidentes.

    ⭐ **EMPATE → não aprovada.** `resultado` é um GATE: é ele que abre a
    entrega ao cliente (§5.5). O default seguro de um gate é fechado. Empate
    significa que a banca não formou consenso de que o trabalho está
    entregável — tratar isso como aprovação abriria a porta ao cliente por
    ausência de acordo, que é o oposto do que o §8 pede.

    Duas alternativas foram consideradas e recusadas:

    - *o coordenador desempata* — ele é explicitamente NÃO-avaliador da própria
      banca ("ninguém avalia o próprio grupo"); dar-lhe o voto de minerva sobre
      o próprio projeto inverteria a regra;
    - *empate aprova* — faz o gate abrir sozinho, e o §5.5 existe para o
      contrário.

    ⭐ **ZERO VOTOS → não decide.** Silêncio não é veredito. Derivar "reprovada"
    puniria o projeto pela omissão dos avaliadores; derivar "aprovada" abriria
    a entrega sem ninguém ter dito que o trabalho presta. Fica `None`, a banca
    aparece na fila "Bancas sem resultado" do Monitoramento, e é exatamente
    para isso que o override da diretoria existe.

    `prazo_vencido` separa "ainda estão votando" de "acabou e ninguém votou":
    antes do prazo, faltar voto é AGUARDANDO; depois, é SEM_VOTOS.
    """
    lista = list(votos)
    aprovacoes = sum(1 for v in lista if v)
    reprovacoes = len(lista) - aprovacoes

    def montar(resultado, motivo):
        return Apuracao(
            resultado=resultado,
            aprovacoes=aprovacoes,
            reprovacoes=reprovacoes,
            esperados=esperados,
            motivo=motivo,
        )

    if not lista:
        return montar(None, SEM_VOTOS if prazo_vencido else AGUARDANDO)

    # ⚠ Enquanto houver voto pendente e prazo aberto, não se decide — um 2×0
    # com dois votos por vir pode virar 2×2. Decidir cedo seria decidir com
    # meia urna.
    if not prazo_vencido and len(lista) < esperados:
        return montar(None, AGUARDANDO)

    if aprovacoes > reprovacoes:
        return montar("aprovada", MAIORIA)
    if reprovacoes > aprovacoes:
        return montar("nao_aprovada", MAIORIA)
    return montar("nao_aprovada", EMPATE)


def votos_por_avaliador(avaliacoes) -> dict:
    """Um membro, um voto — mesmo que existam duas avaliações dele.

    ⚠ **Não é hipótese.** Nada impede duas linhas de `avaliacao` para o mesmo
    par (avaliador, banca): não há UNIQUE na tabela e o front cria a avaliação
    ao abrir o formulário, então abrir duas vezes basta. Sem esta redução, um
    avaliador contaria duas vezes na apuração — foi exatamente o que apareceu
    no primeiro teste contra a base: 4×2 com eleitorado de 3 pessoas.

    Pior que inflar a contagem: `recebidos` passaria de `esperados` e a pessoa
    duplicada decidiria a banca sozinha.

    Vence o **envio mais recente** — se alguém enviou de novo, é a segunda
    manifestação que vale. `submetida_em` nulo perde para qualquer data.
    """
    from datetime import datetime

    escolhidos = {}
    for a in avaliacoes:
        atual = escolhidos.get(a.avaliador_id)
        quando = a.submetida_em or datetime.min
        if atual is None or quando >= (atual.submetida_em or datetime.min):
            escolhidos[a.avaliador_id] = a
    return escolhidos


def eleitorado(candidaturas, votantes_com_voto: Iterable[int]) -> int:
    """Quantos votos esta banca espera receber.

    ⭐ **Quem vota é quem ESTEVE LÁ.** `candidatura.confirmado` é marcado no ato
    de registrar a realização — quem foi escalado e faltou não deve voto a
    ninguém, e contá-lo como abstenção-contra puniria o projeto pela falta de
    outra pessoa.

    ⚠ Duas bordas que o número puro de confirmados não cobre:

    1. **Ninguém foi confirmado.** `RegistrarRealizacaoBancaUseCase` só grava
       presença quando a lista vem preenchida; com `presentes=None` ninguém
       fica `confirmado` e a banca ficaria sem eleitorado — nenhuma apuração
       jamais fecharia. Nesse caso vale a lista inteira de candidatos, que é a
       melhor aproximação disponível de quem esteve lá.
    2. **Alguém votou sem estar confirmado.** O voto existe e não se joga fora;
       o eleitorado precisa acomodá-lo, senão `recebidos > esperados` e o
       gatilho "todos votaram" nunca dispara.
    """
    confirmados = {c.usuario_id for c in candidaturas if getattr(c, "confirmado", False)}
    if not confirmados:
        confirmados = {c.usuario_id for c in candidaturas}
    return len(confirmados | set(votantes_com_voto))
