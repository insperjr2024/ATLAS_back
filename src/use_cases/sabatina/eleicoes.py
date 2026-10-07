"""Montar, abrir, fechar e ler eleições da sabatina (visão da diretoria).

Ciclo: `rascunho` (edita nome, percentual e candidatos) -> `aberta` (congela
quem vota, recebe votos) -> `fechada` (apuração). Sem volta em nenhum passo.

Voto anônimo (2026-10-07): ninguém, nem a diretoria, vê quem votou em quem.
O que sai daqui é sempre agregado: participação (quem já votou e quem falta,
sem o conteúdo do voto), a corrida em tempo real enquanto aberta e os
números da apuração quando fechada. Não existe rota que devolva o voto
individual, e a tabela `sabatina_voto` só é lida pra somar.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.sabatina_repository import (
    SabatinaCandidatoRepository,
    SabatinaEleicaoRepository,
    SabatinaVotoRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc
from src.utils.sabatina_apuracao import apurar


class EleicaoRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    percentual_aprovacao: int = Field(ge=1, le=100)
    candidato_ids: List[int]


def _pessoas(usuario_repo: UsuarioRepository) -> Dict[int, dict]:
    return {
        u.id: {"usuario_id": u.id, "nome": u.nome, "posicao": u.posicao, "status": u.status}
        for u in usuario_repo.get_all()
    }


class _Base:
    def __init__(self, db: Session):
        self.db = db
        self.eleicao_repo = SabatinaEleicaoRepository(db)
        self.candidato_repo = SabatinaCandidatoRepository(db)
        self.voto_repo = SabatinaVotoRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def _eleicao_ou_erro(self, eleicao_id: int):
        eleicao = self.eleicao_repo.get_by_id(eleicao_id)
        if not eleicao:
            raise RegraDeNegocioError("Eleição não encontrada")
        return eleicao

    def serializar(self, eleicao, pessoas: Optional[Dict[int, dict]] = None) -> dict:
        pessoas = pessoas if pessoas is not None else _pessoas(self.usuario_repo)
        candidatos = self.candidato_repo.get_by_eleicao(eleicao.id)
        votos = self.voto_repo.get_by_eleicao(eleicao.id)
        votaram = {v.eleitor_id for v in votos}
        eleitores = list(eleicao.eleitores_ids or [])

        def pessoa(uid: int) -> dict:
            p = pessoas.get(uid) or {"usuario_id": uid, "nome": f"Usuário {uid}", "posicao": None}
            return {"usuario_id": uid, "nome": p["nome"], "posicao": p["posicao"]}

        dados = {
            "id": eleicao.id,
            "nome": eleicao.nome,
            "percentual_aprovacao": eleicao.percentual_aprovacao,
            "status": eleicao.status,
            "criado_em": eleicao.criado_em,
            "aberta_em": eleicao.aberta_em,
            "fechada_em": eleicao.fechada_em,
            "candidatos": [{"id": c.id, **pessoa(c.usuario_id)} for c in candidatos],
            "total_eleitores": len(eleitores),
            "total_votos": len(votos),
            "pendentes": [pessoa(uid) for uid in eleitores if uid not in votaram],
            "resultado": None,
        }
        if eleicao.status == "fechada":
            resultado = apurar(candidatos, votos, eleicao.percentual_aprovacao)
            for linha in resultado["candidatos"]:
                linha.update(pessoa(linha["usuario_id"]))
            dados["resultado"] = resultado
        return dados


class ListEleicoesUseCase(_Base):
    def execute(self) -> list[dict]:
        pessoas = _pessoas(self.usuario_repo)
        return [self.serializar(e, pessoas) for e in self.eleicao_repo.get_todas()]


class GetEleicaoUseCase(_Base):
    def execute(self, eleicao_id: int) -> dict:
        return self.serializar(self._eleicao_ou_erro(eleicao_id))


class GetGraficosEleicaoUseCase(_Base):
    """Os números por trás dos gráficos da diretoria, sem identidade de
    eleitor. Serve a corrida em tempo real (eleição aberta) e os gráficos
    extras depois da apuração (fechada).

    O que vai: a contagem por candidato (a mesma conta da apuração, só que
    parcial enquanto aberta), participação por posição em quantidade e a
    linha do tempo dos votos (quando cada voto entrou, em quem e com que
    peso). A linha do tempo não leva a posição de quem votou de propósito:
    cruzada com a lista de pendentes, ela entregaria o voto de quem é único
    na posição.
    """

    def execute(self, eleicao_id: int) -> dict:
        eleicao = self._eleicao_ou_erro(eleicao_id)
        if eleicao.status == "rascunho":
            raise RegraDeNegocioError("Esta eleição ainda não foi aberta.")
        pessoas = _pessoas(self.usuario_repo)
        candidatos = self.candidato_repo.get_by_eleicao(eleicao.id)
        votos = self.voto_repo.get_by_eleicao(eleicao.id)

        parcial = apurar(candidatos, votos, eleicao.percentual_aprovacao)
        for linha in parcial["candidatos"]:
            p = pessoas.get(linha["usuario_id"]) or {}
            linha["nome"] = p.get("nome", f"Usuário {linha['usuario_id']}")

        # Participação por posição: quantos eleitores de cada posição já
        # votaram. Só quantidades, e pela posição ATUAL da pessoa (a mesma
        # régua pros dois lados da fração), não pela gravada no voto.
        votaram = {v.eleitor_id for v in votos}
        por_posicao: Dict[str, dict] = {}
        for uid in eleicao.eleitores_ids or []:
            posicao = (pessoas.get(uid) or {}).get("posicao") or "sem_posicao"
            faixa = por_posicao.setdefault(posicao, {"posicao": posicao, "total": 0, "votaram": 0})
            faixa["total"] += 1
            if uid in votaram:
                faixa["votaram"] += 1

        linha_do_tempo = [
            {"em": v.criado_em, "candidato_id": v.candidato_id, "peso": v.peso}
            for v in sorted(votos, key=lambda v: (v.criado_em, v.id))
        ]

        return {
            "status": eleicao.status,
            "aberta_em": eleicao.aberta_em,
            "fechada_em": eleicao.fechada_em,
            "total_eleitores": len(eleicao.eleitores_ids or []),
            "parcial": parcial,
            "por_posicao": sorted(por_posicao.values(), key=lambda f: -f["total"]),
            "linha_do_tempo": linha_do_tempo,
        }


def _validar_candidatos(usuario_repo: UsuarioRepository, ids: List[int]) -> None:
    if not ids:
        raise RegraDeNegocioError("Escolha pelo menos um candidato.")
    if len(set(ids)) != len(ids):
        raise RegraDeNegocioError("A mesma pessoa aparece duas vezes entre os candidatos.")
    conhecidos = {u.id for u in usuario_repo.get_all()}
    faltando = [i for i in ids if i not in conhecidos]
    if faltando:
        raise RegraDeNegocioError("Candidato não encontrado entre os membros.")


class CreateEleicaoUseCase(_Base):
    def execute(self, request: EleicaoRequest, current_user) -> dict:
        _validar_candidatos(self.usuario_repo, request.candidato_ids)
        eleicao = self.eleicao_repo.create(
            nome=request.nome.strip(),
            percentual_aprovacao=request.percentual_aprovacao,
            status="rascunho",
            eleitores_ids=[],
            criado_por=getattr(current_user, "id", None),
        )
        self.candidato_repo.substituir(eleicao.id, request.candidato_ids)
        return self.serializar(eleicao)


class UpdateEleicaoUseCase(_Base):
    def execute(self, eleicao_id: int, request: EleicaoRequest) -> dict:
        eleicao = self._eleicao_ou_erro(eleicao_id)
        if eleicao.status != "rascunho":
            raise RegraDeNegocioError("Só dá pra editar uma eleição que ainda não foi aberta.")
        _validar_candidatos(self.usuario_repo, request.candidato_ids)
        eleicao = self.eleicao_repo.update(
            eleicao_id, nome=request.nome.strip(), percentual_aprovacao=request.percentual_aprovacao
        )
        self.candidato_repo.substituir(eleicao_id, request.candidato_ids)
        return self.serializar(eleicao)


class DeleteEleicaoUseCase(_Base):
    """Apaga em qualquer status (a pedido, 2026-10-06). Candidatos e votos
    vão junto pelo `ON DELETE CASCADE`; a tela pede o nome digitado quando
    há voto a perder."""

    def execute(self, eleicao_id: int) -> None:
        self._eleicao_ou_erro(eleicao_id)
        self.eleicao_repo.delete(eleicao_id)


class AbrirEleicaoUseCase(_Base):
    """Congela quem vota: todo membro ativo que não é candidato. A partir daqui
    a cédula aparece pra essas pessoas."""

    def execute(self, eleicao_id: int) -> dict:
        eleicao = self._eleicao_ou_erro(eleicao_id)
        if eleicao.status != "rascunho":
            raise RegraDeNegocioError("Esta eleição já foi aberta.")
        candidatos = {c.usuario_id for c in self.candidato_repo.get_by_eleicao(eleicao_id)}
        if not candidatos:
            raise RegraDeNegocioError("Escolha pelo menos um candidato antes de abrir.")
        eleitores = sorted(
            u.id for u in self.usuario_repo.get_ativos() if u.ativo and u.id not in candidatos
        )
        if not eleitores:
            raise RegraDeNegocioError("Não há ninguém pra votar nesta eleição.")
        eleicao = self.eleicao_repo.update(
            eleicao_id, status="aberta", aberta_em=agora_utc(), eleitores_ids=eleitores
        )
        return self.serializar(eleicao)


class FecharEleicaoUseCase(_Base):
    def execute(self, eleicao_id: int) -> dict:
        eleicao = self._eleicao_ou_erro(eleicao_id)
        if eleicao.status != "aberta":
            raise RegraDeNegocioError("Só uma eleição aberta pode ser fechada.")
        eleicao = self.eleicao_repo.update(eleicao_id, status="fechada", fechada_em=agora_utc())
        return self.serializar(eleicao)
