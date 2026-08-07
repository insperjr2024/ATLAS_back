from datetime import time
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.grade_horaria_repository import GradeHorariaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError

#: As 6 faixas da grade do Insper (§11). A tela desenha exatamente estas, e o
#: backend recusa qualquer outra — sem isso, um cliente errado poderia gravar
#: "aula das 3h às 4h" e ninguém veria.
#:
#: Se um dia entrar curso com horário diferente, é acrescentar aqui: a coluna
#: guarda o horário de verdade, não o índice da faixa.
FAIXAS_INSPER: List[tuple[time, time]] = [
    (time(7, 30), time(9, 30)),
    (time(9, 45), time(11, 45)),
    (time(12, 0), time(14, 0)),
    (time(14, 15), time(16, 15)),
    (time(16, 30), time(18, 30)),
    (time(19, 0), time(21, 0)),
]

DIAS_VALIDOS = range(5)  # 0 = segunda … 4 = sexta


class FaixaRequest(BaseModel):
    dia_semana: int
    hora_inicio: time
    hora_fim: time


class SalvarGradeRequest(BaseModel):
    #: O estado FINAL do quadro. Lista vazia é válida e significa "não tenho
    #: aula nenhuma" — diferente de nunca ter preenchido.
    faixas: List[FaixaRequest]
    semestre_id: Optional[int] = None


def _serializar(faixa) -> dict:
    return {
        "dia_semana": faixa.dia_semana,
        "hora_inicio": faixa.hora_inicio.strftime("%H:%M"),
        "hora_fim": faixa.hora_fim.strftime("%H:%M"),
    }


#: Teto realista de horários livres em comum num time.
#:
#: A grade tem 30 células (5 dias × 6 faixas), mas ninguém chega perto disso:
#: um consultor com 10 aulas já derruba para 20, e a interseção de várias
#: pessoas cai rápido. Medir contra 30 faria todo time parecer ruim — a escala
#: é calibrada por 20, que é o que o núcleo observa na prática.
TETO_LIVRES_EM_COMUM = 20

#: Faixas de leitura do resultado. Um horário livre em comum já basta para a
#: reunião semanal acontecer (§6.4), então 1 não é "ruim" — é "apertado".
TEORES = [
    (16, "alta", "Muita folga para marcar reunião"),
    (11, "boa", "Boa janela de horários"),
    (6, "media", "Dá para marcar, com opções limitadas"),
    (1, "baixa", "Quase não sobra horário — combinar vai ser difícil"),
    (0, "nenhuma", "Não há nenhum horário livre para todos ao mesmo tempo"),
]


def _teor(livres: int) -> tuple[str, str]:
    for minimo, chave, texto in TEORES:
        if livres >= minimo:
            return chave, texto
    return "nenhuma", ""


class GradeHorariaUseCase:
    """A grade de aulas do próprio membro (§11).

    Cada um mexe só na sua: não há parâmetro de usuário em lugar nenhum, o id
    vem sempre do token. Visão da diretoria sobre a grade dos outros é
    funcionalidade à parte, e ainda não existe.
    """

    def __init__(self, db: Session):
        self.repository = GradeHorariaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def _resolver_semestre(self, semestre_id: Optional[int]) -> int:
        if semestre_id is not None:
            return semestre_id
        semestre = self.semestre_repository.get_ativo()
        if not semestre:
            raise RegraDeNegocioError(
                "Nenhuma gestão ativa. A diretoria precisa abrir o semestre antes."
            )
        return semestre.id

    def listar(self, usuario_id: int, semestre_id: Optional[int] = None) -> dict:
        semestre_id = self._resolver_semestre(semestre_id)
        faixas = self.repository.get_by_usuario(usuario_id, semestre_id)
        return {
            "semestre_id": semestre_id,
            "faixas": [_serializar(f) for f in faixas],
        }

    def compatibilidade(
        self, usuario_ids: List[int], semestre_id: Optional[int] = None
    ) -> dict:
        """Em que faixas TODOS os escolhidos estão livres ao mesmo tempo (§11).

        📐 Quem não preencheu a grade conta como livre, e vai em `sem_grade`
        para a tela avisar. Ausência de linha quer dizer "não sei", e tratar
        como ocupado inventaria conflito que talvez não exista — mas deixar
        isso escondido faria a diretoria confiar num número que não se apoia
        em nada.
        """
        semestre_id = self._resolver_semestre(semestre_id)
        ids = sorted(set(usuario_ids))

        if not ids:
            return {
                "semestre_id": semestre_id,
                "livres_em_comum": [],
                "total_livres": 0,
                "teto": TETO_LIVRES_EM_COMUM,
                "percentual": 0,
                "teor": "nenhuma",
                "teor_texto": "Escolha ao menos um consultor.",
                "sem_grade": [],
                "considerados": [],
            }

        ocupadas: dict[int, set[tuple[int, time]]] = {uid: set() for uid in ids}
        for uid in ids:
            for faixa in self.repository.get_by_usuario(uid, semestre_id):
                ocupadas[uid].add((faixa.dia_semana, faixa.hora_inicio))

        sem_grade = [uid for uid in ids if not ocupadas[uid]]

        livres = [
            {
                "dia_semana": dia,
                "hora_inicio": inicio.strftime("%H:%M"),
                "hora_fim": fim.strftime("%H:%M"),
            }
            for dia in DIAS_VALIDOS
            for inicio, fim in FAIXAS_INSPER
            if all((dia, inicio) not in ocupadas[uid] for uid in ids)
        ]

        teor, teor_texto = _teor(len(livres))
        # ⚠ Se NINGUÉM preencheu, a conta dá 30 de 30 e o teor sai "alta" —
        # o número mais alto possível vindo de zero informação. Um aviso ao
        # lado não conserta isso: quem bate o olho lê o número, não a nota de
        # rodapé. Então não há teor nenhum a mostrar.
        if len(sem_grade) == len(ids):
            teor, teor_texto = (
                "desconhecida",
                "Ninguém do time preencheu a grade — não dá para comparar horários.",
            )
        return {
            "semestre_id": semestre_id,
            "livres_em_comum": livres,
            "total_livres": len(livres),
            "teto": TETO_LIVRES_EM_COMUM,
            "percentual": min(100, round(len(livres) / TETO_LIVRES_EM_COMUM * 100)),
            "teor": teor,
            "teor_texto": teor_texto,
            "sem_grade": sem_grade,
            "considerados": ids,
        }

    def salvar(self, usuario_id: int, request: SalvarGradeRequest) -> dict:
        semestre_id = self._resolver_semestre(request.semestre_id)

        vistas: set[tuple[int, time]] = set()
        para_gravar: List[tuple[int, time, time]] = []

        for faixa in request.faixas:
            if faixa.dia_semana not in DIAS_VALIDOS:
                raise RegraDeNegocioError(
                    "A grade vai de segunda a sexta — dia inválido recebido."
                )
            if (faixa.hora_inicio, faixa.hora_fim) not in FAIXAS_INSPER:
                raise RegraDeNegocioError(
                    f"{faixa.hora_inicio:%H:%M}–{faixa.hora_fim:%H:%M} não é uma das "
                    "faixas da grade do Insper."
                )
            chave = (faixa.dia_semana, faixa.hora_inicio)
            # A mesma célula marcada duas vezes violaria a unique e derrubaria
            # a gravação inteira. Ignorar é mais gentil que recusar: o estado
            # final que a pessoa quis é o mesmo.
            if chave in vistas:
                continue
            vistas.add(chave)
            para_gravar.append((faixa.dia_semana, faixa.hora_inicio, faixa.hora_fim))

        self.repository.substituir(usuario_id, semestre_id, para_gravar)
        return self.listar(usuario_id, semestre_id)
