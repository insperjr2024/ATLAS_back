"""A aba de cronograma inteira numa ida só.

O front não sabe a janela de meses antes de saber as datas, e não sabe quais
dias são cinzas antes de saber a janela — clássico ovo-e-galinha. Resolvido
aqui: o backend calcula a janela, resolve os dias não úteis dela e devolve
tudo junto.
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import (
    CronogramaEtapaRepository,
    CronogramaMarcoRepository,
)
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository
from src.use_cases.projeto_escopo.get_escopos_projeto import ListEscoposProjetoUseCase
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.dias_uteis import somar_dias_uteis
from src.utils.janela_escopo import calcular_janela

#: Teto de segurança: uma data digitada como 2099 não pode renderizar 900
#: blocos de mês e congelar a aba.


class GetCronogramaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.projeto_repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.etapa_repository = CronogramaEtapaRepository(db)
        self.marco_repository = CronogramaMarcoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.reuniao_repository = ReuniaoSemanalRepository(db)

    def execute(self, projeto_id: int, referencia: Optional[date] = None):
        projeto = self.projeto_repository.get_by_id(projeto_id)
        if not projeto:
            return None

        referencia = referencia or date.today()
        escopos_serializados = ListEscoposProjetoUseCase(self.db).execute(projeto_id, referencia)
        escopos = self.escopo_repository.get_by_projeto(projeto_id)
        etapas = self.etapa_repository.get_by_escopos([e.id for e in escopos])
        marcos = self.marco_repository.get_by_projeto(projeto_id)
        bancas = self.banca_repository.get_by_projeto_escopos([e.id for e in escopos])
        reunioes = self.reuniao_repository.get_by_projeto(projeto_id)
        janelas_pausa = derivar_janelas_pausa(
            self.historico_repository.get_by_projeto(projeto_id), referencia
        )

        inicio, fim = self._janela(projeto, escopos, etapas, marcos, bancas, referencia)
        semestre = self.semestre_repository.get_ativo()
        dias_nao_letivos = self.dia_nao_letivo_repository.get_por_intervalo(inicio, fim)

        etapas_por_escopo = {}
        for etapa in etapas:
            etapas_por_escopo.setdefault(etapa.projeto_escopo_id, []).append(
                {
                    "id": etapa.id,
                    "projeto_escopo_id": etapa.projeto_escopo_id,
                    "nome": etapa.nome,
                    "cor": etapa.cor,
                    "data_inicio": etapa.data_inicio,
                    "data_fim": etapa.data_fim,
                    "status": etapa.status,
                    "ordem": etapa.ordem,
                }
            )

        return {
            "projeto_id": projeto_id,
            "data_kickoff": projeto.data_kickoff,
            "escopos": [
                {**e, "etapas": etapas_por_escopo.get(e["id"], [])} for e in escopos_serializados
            ],
            "marcos": [
                {
                    "id": m.id,
                    "projeto_id": m.projeto_id,
                    "projeto_escopo_id": m.projeto_escopo_id,
                    "tipo": m.tipo,
                    "data": m.data,
                    "nota": m.nota,
                }
                for m in marcos
            ],
            # ⭐ As reuniões vêm junto porque elas são MARCAÇÕES DO CRONOGRAMA
            # agora — a aba Reuniões deixou de existir e é aqui que a reunião
            # inicial de cada escopo e a reunião geral do projeto são marcadas.
            # Sem elas no payload, o que o usuário acabou de marcar sumia da
            # tela até o próximo F5.
            #
            # `tipo` é derivado do vínculo, nunca gravado: um campo próprio
            # poderia divergir de `projeto_escopo_id`, que é quem manda.
            "reunioes": [
                {
                    "id": r.id,
                    "projeto_id": r.projeto_id,
                    "projeto_escopo_id": r.projeto_escopo_id,
                    "data_reuniao": r.data_reuniao,
                    "observacoes": r.observacoes,
                    "tipo": "inicial" if r.projeto_escopo_id else "geral",
                    "registrado_por": r.registrado_por,
                }
                for r in reunioes
            ],
            # Ambientação e pausas são DERIVADAS, não etapas gravadas — vêm
            # calculadas daqui para o front não reimplementar `somar_dias_uteis`
            # em TypeScript.
            # A ambientação é do PROJETO, não de um escopo, então conta apenas
            # os dias que valem para todas as frentes. Usar o calendário de uma
            # frente aqui faria a ambientação do mesmo projeto terminar em datas
            # diferentes conforme o escopo que estivesse selecionado na tela.
            # ⚠ A faixa do escopo não recebe mais as bancas: ela virou a JANELA
            # (reunião inicial + vendidos + ajustados), que é previsão e não
            # depende de a banca ter data.
            "faixas_derivadas": self._faixas_derivadas(
                projeto,
                escopos,
                [d.data for d in dias_nao_letivos if d.frente_id is None],
                janelas_pausa,
            ),
            "janela": {"inicio": inicio, "fim": fim},
            # A gestão corrente, à parte da janela. A janela é larga de
            # propósito (o ano corrente e o seguinte, para a navegação ser
            # livre); o semestre é o recorte que interessa por padrão — é o
            # período em que o projeto de fato acontece.
            "semestre": (
                {"nome": semestre.nome, "inicio": semestre.inicio, "fim": semestre.fim}
                if semestre
                else None
            ),
            # 📐 Cada dia carrega a FRENTE dona. O calendário acadêmico deixou
            # de ser um só: cada frente abrange cursos diferentes e cada curso
            # tem as suas semanas de avaliação. `frente_id` nulo é feriado, que
            # vale para todas.
            #
            # Vem tudo numa lista só, e não agrupado por frente, porque o
            # projeto sinérgico precisa enxergar as duas frentes ao mesmo tempo
            # para avisar quando uma etapa pisa no dia não útil da outra.
            "dias_nao_uteis": [
                {
                    "data": d.data,
                    "tipo": d.tipo,
                    "descricao": d.descricao,
                    "frente_id": d.frente_id,
                }
                for d in dias_nao_letivos
            ],
        }

    def _janela(self, projeto, escopos, etapas, marcos, bancas, referencia):
        """O ano corrente inteiro mais o seguinte — navegação livre.

        Antes a janela ia do primeiro ao último marco do projeto com um mês de
        folga, e isso amarrava a navegação a onde alguém tinha parado de
        pintar: para chegar em novembro era preciso pintar outubro antes. Pior,
        o seletor de meses do export só oferecia o que estava dentro dessa
        janela apertada.

        Agora o limite é o calendário, não o conteúdo. Um projeto que começou
        antes do ano corrente puxa o início para trás, para o histórico dele não
        sumir da tela.
        """
        candidatas: List[date] = [referencia]
        if projeto.data_kickoff:
            candidatas.append(projeto.data_kickoff)
        if projeto.data_inicio_ambientacao:
            candidatas.append(projeto.data_inicio_ambientacao)
        for e in escopos:
            candidatas += [
                d for d in (e.data_inicio, e.data_entrega_planejada, e.data_entrega_real) if d
            ]
        for e in etapas:
            candidatas += [e.data_inicio, e.data_fim]
        for m in marcos:
            candidatas.append(m.data)
        for b in bancas:
            if b.data_hora:
                candidatas.append(b.data_hora.date())

        ano_base = min(min(candidatas).year, referencia.year)
        return date(ano_base, 1, 1), date(referencia.year + 1, 12, 31)

    def _faixas_derivadas(self, projeto, escopos, dias_nao_letivos, janelas_pausa=()):
        faixas = []

        # ⭐ A JANELA DE CADA ESCOPO: da reunião inicial (`data_inicio`, §5.4)
        # até *vendidos + ajustados* dias úteis depois dela.
        #
        # ⚠ Antes esta faixa ia até a DATA DA BANCA, e por isso sumia enquanto
        # a banca não tivesse data — justamente quando ela é mais útil. A faixa
        # é **previsão**, não consequência: ela mostra até onde o escopo cabe
        # no que foi prometido, e é dentro dela que a banca precisa caber (§9),
        # não o contrário.
        #
        # Derivada, nunca gravada: mover a reunião inicial ou aprovar dias de
        # ajuste redesenha o retângulo sozinho.
        for escopo in escopos:
            janela = calcular_janela(
                escopo.data_inicio,
                escopo.dias_uteis_vendidos,
                escopo.dias_uteis_ajustados,
                dias_nao_letivos,
                janelas_pausa=janelas_pausa,
            )
            if not janela.aberta:
                continue

            ajuste = (
                f" + {escopo.dias_uteis_ajustados} ajustados"
                if escopo.dias_uteis_ajustados
                else ""
            )
            faixas.append(
                {
                    "tipo": "escopo",
                    "projeto_escopo_id": escopo.id,
                    "inicio": janela.data_inicio,
                    "fim": janela.fim,
                    "rotulo": (
                        f"Janela do escopo ({escopo.dias_uteis_vendidos} vendidos{ajuste})"
                    ),
                }
            )

        # A ambientação: kickoff + N dias úteis (§5.3) — ou `data_inicio_ambientacao`
        # + N dias úteis, quando o coordenador corrigiu que ela começou antes do
        # kickoff (ver `UpdateInicioAmbientacaoUseCase`).
        inicio_ambientacao = projeto.data_inicio_ambientacao or projeto.data_kickoff
        if inicio_ambientacao and projeto.dias_ambientacao > 0:
            try:
                fim = somar_dias_uteis(
                    inicio_ambientacao, projeto.dias_ambientacao, dias_nao_letivos
                )
                faixas.append(
                    {
                        "tipo": "ambientacao",
                        "projeto_escopo_id": None,
                        "inicio": inicio_ambientacao,
                        "fim": fim,
                        "rotulo": f"Ambientação ({projeto.dias_ambientacao} dias úteis)",
                    }
                )
            except ValueError:
                pass  # calendário carregado errado — a faixa some, o resto segue

        # As pausas entre escopos: o vão entre a entrega de um e o início do
        # próximo. É o "tempo parado" que o §7.1 quer visível.
        # Só existe pausa se houver um escopo entregue E outro esperando para
        # começar; a faixa vai do dia seguinte à entrega até hoje.
        ha_escopo_esperando = any(not e.data_inicio for e in escopos)
        ultima_entrega = max(
            (e.data_entrega_real for e in escopos if e.data_entrega_real), default=None
        )
        if ha_escopo_esperando and ultima_entrega:
            # ⚠ A faixa fecha quando o PRÓXIMO escopo começa, não em `hoje`.
            #
            # Com três escopos — um entregue, um já em curso e um esperando —
            # a condição acima continua verdadeira, e a faixa ia da entrega do
            # primeiro até hoje, ATRAVESSANDO o escopo do meio que está sendo
            # trabalhado. O cronograma pintava "Parado entre escopos" por cima
            # de trabalho em andamento, e contradizia o "tempo parado" que o
            # Monitoramento reporta para o mesmo projeto — que fecha o vão na
            # reunião inicial do escopo seguinte.
            comecou_depois = [
                e.data_inicio
                for e in escopos
                if e.data_inicio and e.data_inicio > ultima_entrega
            ]
            fim_da_pausa = (
                min(comecou_depois) - timedelta(days=1) if comecou_depois else date.today()
            )
            inicio_da_pausa = ultima_entrega + timedelta(days=1)
            # Escopo que começou no dia seguinte à entrega não deixa vão nenhum.
            if fim_da_pausa >= inicio_da_pausa:
                faixas.append(
                    {
                        "tipo": "pausa",
                        "projeto_escopo_id": None,
                        "inicio": inicio_da_pausa,
                        "fim": fim_da_pausa,
                        "rotulo": "Parado entre escopos",
                    }
                )

        return faixas
