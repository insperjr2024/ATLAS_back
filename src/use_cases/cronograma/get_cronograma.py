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
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.projeto_escopo.get_escopos_projeto import ListEscoposProjetoUseCase
from src.utils.dias_uteis import somar_dias_uteis

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
            # Ambientação e pausas são DERIVADAS, não etapas gravadas — vêm
            # calculadas daqui para o front não reimplementar `somar_dias_uteis`
            # em TypeScript.
            # A ambientação é do PROJETO, não de um escopo, então conta apenas
            # os dias que valem para todas as frentes. Usar o calendário de uma
            # frente aqui faria a ambientação do mesmo projeto terminar em datas
            # diferentes conforme o escopo que estivesse selecionado na tela.
            "faixas_derivadas": self._faixas_derivadas(
                projeto,
                escopos,
                [d.data for d in dias_nao_letivos if d.frente_id is None],
                self.banca_repository.mapa_por_escopo([e.id for e in escopos]),
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
            # F11 ainda não existe; o campo já vem para o banner do front não
            # precisar mudar de forma depois.
            "reajuste_pendente": None,
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
        if projeto.data_entrega_cliente:
            candidatas.append(projeto.data_entrega_cliente)
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

    def _faixas_derivadas(self, projeto, escopos, dias_nao_letivos, bancas_por_escopo):
        faixas = []

        # ⭐ O PERÍODO DE CADA ESCOPO: da reunião inicial (que é o que preenche
        # `data_inicio`, §5.4) até a banca dele. São as duas pontas que o
        # coordenador crava, e é a janela em que os dias vendidos correm — por
        # isso ela é pintada no calendário, e não só somada na barra de dias.
        #
        # Sem uma das pontas não há faixa: escopo não iniciado não tem período,
        # e banca sem data não tem onde fechar. Derivada, nunca gravada —
        # mover a reunião ou remarcar a banca redesenha a faixa sozinho.
        for escopo in escopos:
            banca = bancas_por_escopo.get(escopo.id)
            fim_banca = banca.data_hora.date() if banca and banca.data_hora else None
            if not escopo.data_inicio or not fim_banca:
                continue
            faixas.append(
                {
                    "tipo": "escopo",
                    "projeto_escopo_id": escopo.id,
                    "inicio": escopo.data_inicio,
                    # Banca marcada ANTES da reunião inicial existe (remarcação
                    # para trás): a faixa vira o dia só, em vez de sumir por
                    # intervalo invertido.
                    "fim": max(fim_banca, escopo.data_inicio),
                    "rotulo": "Período do escopo",
                }
            )

        # A ambientação: kickoff + N dias úteis (§5.3).
        if projeto.data_kickoff and projeto.dias_ambientacao > 0:
            try:
                fim = somar_dias_uteis(
                    projeto.data_kickoff, projeto.dias_ambientacao, dias_nao_letivos
                )
                faixas.append(
                    {
                        "tipo": "ambientacao",
                        "projeto_escopo_id": None,
                        "inicio": projeto.data_kickoff,
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
            faixas.append(
                {
                    "tipo": "pausa",
                    "projeto_escopo_id": None,
                    "inicio": ultima_entrega + timedelta(days=1),
                    "fim": date.today(),
                    "rotulo": "Parado entre escopos",
                }
            )

        return faixas
