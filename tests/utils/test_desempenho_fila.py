"""Fila de quem avalia quem dentro do escopo de um lote (regra 2.3):
coordenador avalia os consultores do projeto (e outro coordenador, se houver
mais de um); consultor avalia o(s) coordenador(es) e os outros consultores.
Pares repetidos em 2+ projetos do mesmo lote colapsam numa entrada só (regra
2.7 precisa ver todos os projetos)."""

from datetime import datetime
from types import SimpleNamespace

from src.utils.desempenho_fila import (
    DATA_COORDENADOR_AVALIA_COORDENADOR,
    calcular_pares_lote,
    deduplicar_pares,
)


def membro(projeto_id: int, usuario_id: int, papel: str) -> SimpleNamespace:
    return SimpleNamespace(projeto_id=projeto_id, usuario_id=usuario_id, papel=papel)


class TestCalcularParesLote:
    def test_coordenador_avalia_todos_os_consultores_do_projeto(self):
        time = [
            membro(1, 10, "coordenador"),
            membro(1, 20, "consultor"),
            membro(1, 30, "consultor"),
        ]
        pares = calcular_pares_lote(time)
        de_coordenador = [p for p in pares if p.avaliador_id == 10]
        assert {p.avaliado_id for p in de_coordenador} == {20, 30}
        assert all(p.form_type == "consultor" for p in de_coordenador)

    def test_consultor_avalia_coordenador_e_outros_consultores(self):
        time = [
            membro(1, 10, "coordenador"),
            membro(1, 20, "consultor"),
            membro(1, 30, "consultor"),
        ]
        pares = calcular_pares_lote(time)
        de_consultor_20 = [p for p in pares if p.avaliador_id == 20]
        avaliados = {p.avaliado_id: p.form_type for p in de_consultor_20}
        assert avaliados == {10: "coordenador", 30: "consultor"}

    def test_dois_coordenadores_simultaneos_se_avaliam_mutuamente(self):
        """2026-09-16, a pedido: projeto grande pode ter 2 coordenadores
        (`validacao_equipe.py`), e agora os dois entram na fila um do
        outro — deixou de ser tratado como "o mesmo papel"."""
        time = [membro(1, 10, "coordenador"), membro(1, 11, "coordenador")]
        pares = calcular_pares_lote(time)
        assert {(p.avaliador_id, p.avaliado_id, p.form_type) for p in pares} == {
            (10, 11, "coordenador"),
            (11, 10, "coordenador"),
        }

    def test_lote_anterior_a_regra_nao_inclui_par_coordenador_coordenador(self):
        """2026-09-18, corrigido: a regra nasceu em 16/09 — um lote aberto
        antes disso (a Finalização da BLEND I, 09/09) não pode cobrar de dois
        coordenadores uma avaliação mútua que não existia quando eles
        preencheram a própria fila."""
        time = [membro(1, 10, "coordenador"), membro(1, 11, "coordenador")]
        antes_da_regra = datetime(2026, 9, 9, 15, 0)

        pares = calcular_pares_lote(time, antes_da_regra)

        assert pares == []

    def test_lote_no_dia_da_regra_ja_inclui_o_par(self):
        time = [membro(1, 10, "coordenador"), membro(1, 11, "coordenador")]

        pares = calcular_pares_lote(time, DATA_COORDENADOR_AVALIA_COORDENADOR)

        assert {(p.avaliador_id, p.avaliado_id) for p in pares} == {(10, 11), (11, 10)}

    def test_sem_data_do_lote_assume_a_regra_atual(self):
        """`None` é só pra quem quer testar a fila em si, sem lote de
        verdade — mantém o comportamento de antes da correção."""
        time = [membro(1, 10, "coordenador"), membro(1, 11, "coordenador")]

        pares = calcular_pares_lote(time, None)

        assert {(p.avaliador_id, p.avaliado_id) for p in pares} == {(10, 11), (11, 10)}

    def test_regra_nao_afeta_par_coordenador_consultor_em_lote_antigo(self):
        """A correção é só do par coordenador↔coordenador — coordenador
        continuar avaliando consultor (e vice-versa) sempre existiu."""
        time = [
            membro(1, 10, "coordenador"),
            membro(1, 20, "consultor"),
        ]
        antes_da_regra = datetime(2026, 9, 9, 15, 0)

        pares = calcular_pares_lote(time, antes_da_regra)

        assert {(p.avaliador_id, p.avaliado_id) for p in pares} == {(10, 20), (20, 10)}

    def test_ninguem_avalia_a_si_mesmo(self):
        time = [membro(1, 10, "coordenador"), membro(1, 20, "consultor")]
        pares = calcular_pares_lote(time)
        assert all(p.avaliador_id != p.avaliado_id for p in pares)

    def test_projetos_diferentes_nao_se_misturam(self):
        time = [
            membro(1, 10, "coordenador"),
            membro(1, 20, "consultor"),
            membro(2, 30, "coordenador"),
            membro(2, 40, "consultor"),
        ]
        pares = calcular_pares_lote(time)
        assert (10, 40) not in {(p.avaliador_id, p.avaliado_id) for p in pares}
        assert (30, 20) not in {(p.avaliador_id, p.avaliado_id) for p in pares}


class TestDeduplicarPares:
    def test_par_em_dois_projetos_vira_uma_entrada_com_os_dois_projetos(self):
        time = [
            membro(1, 10, "coordenador"),
            membro(1, 20, "consultor"),
            membro(2, 10, "coordenador"),
            membro(2, 20, "consultor"),
        ]
        pares = calcular_pares_lote(time)
        agregados = deduplicar_pares(pares)
        assert agregados[(10, 20)]["form_type"] == "consultor"
        assert sorted(agregados[(10, 20)]["projeto_ids"]) == [1, 2]

    def test_par_em_um_projeto_so_tem_uma_entrada_com_um_projeto(self):
        time = [membro(1, 10, "coordenador"), membro(1, 20, "consultor")]
        agregados = deduplicar_pares(calcular_pares_lote(time))
        assert agregados[(10, 20)]["projeto_ids"] == [1]
