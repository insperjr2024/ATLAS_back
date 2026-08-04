"""Smoke test da Prioridade 1 direto contra a API rodando.

Complementa o `pytest`, que cobre só o núcleo de cálculo (dias úteis,
contagem, status de banca e tarefa). Aqui o alvo são as regras que só
aparecem com HTTP + banco: permissão, recorte de visão e as travas.

    uvicorn src.app:app --port 8000        # num terminal
    uv run python -m scripts.seed          # dados da demo
    python3 scripts/smoke_api.py           # noutro

É idempotente: limpa as tarefas e reuniões do Alfa antes de recriar.
"""
import json
import urllib.request

BASE = "http://localhost:8000"


def call(metodo, caminho, token=None, corpo=None):
    req = urllib.request.Request(
        BASE + caminho, method=metodo,
        data=json.dumps(corpo).encode() if corpo is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        try:
            return e.code, json.loads(texto)
        except Exception:
            return e.code, texto


def login(email):
    _, d = call("POST", "/auth/login", corpo={"email_insper": email, "senha": "atlas123"})
    return d["access_token"]


def ok(cond, msg):
    print(f"  {'✅' if cond else '❌'} {msg}")
    return cond


falhas = 0


def checar(cond, msg):
    global falhas
    if not ok(cond, msg):
        falhas += 1


ana = login("ana@al.insper.edu.br")
dani = login("dani@al.insper.edu.br")
gil = login("gil@gmail.com")
bia = login("bia@gmail.com")

_, projetos = call("GET", "/projetos", dani)
alfa = next(p["id"] for p in projetos if p["nome"] == "Projeto Alfa")
beta = next(p["id"] for p in projetos if p["nome"] == "Projeto Beta")

print("\n=== F7 · Tarefas ===")
_, tarefas_antigas = call("GET", f"/projetos/{alfa}/tarefas", ana)
for t_antiga in tarefas_antigas:
    call("DELETE", f"/tarefas/{t_antiga['id']}", ana)

st, t1 = call("POST", f"/projetos/{alfa}/tarefas", ana,
              {"titulo": "Levantar concorrentes", "responsavel_id": 5, "prazo": "2026-07-28"})
checar(st == 200 and t1["vencida"] is True, f"prazo passado → vencida=True (got {t1.get('vencida')})")

st, t2 = call("POST", f"/projetos/{alfa}/tarefas", ana,
              {"titulo": "Rodar entrevistas", "responsavel_id": 6, "prazo": "2026-08-20"})
checar(st == 200 and t2["vencida"] is False, f"prazo futuro → vencida=False (got {t2.get('vencida')})")

# As colunas do kanban são dados (configuráveis pela diretoria), não ENUM.
st, colunas = call("GET", "/tarefas-colunas", ana)
checar(st == 200 and len(colunas) >= 2, f"colunas do kanban vêm da API ({len(colunas)})")
em_andamento = next(c for c in colunas if c["nome"] == "Em andamento")
concluido = next(c for c in colunas if c["encerra_tarefa"])

st, _ = call("PATCH", f"/tarefas/{t1['id']}", ana, {"coluna_id": 99999})
checar(st == 422, f"coluna inexistente → 422 (got {st})")

st, movida = call("PATCH", f"/tarefas/{t1['id']}", ana, {"coluna_id": em_andamento["id"]})
checar(st == 200 and movida["coluna_id"] == em_andamento["id"], "mover no kanban")

st, so_titulo = call("PATCH", f"/tarefas/{t1['id']}", ana, {"titulo": "Levantar concorrentes v2"})
checar(so_titulo["movida_em"] == movida["movida_em"],
       "renomear NÃO mexe em movida_em (só mudança de status conta)")

st, concluida = call("PATCH", f"/tarefas/{t1['id']}", ana, {"coluna_id": concluido["id"]})
checar(concluida["vencida"] is False,
       "em coluna que ENCERRA, com prazo passado → vencida=False")

# Só a diretoria configura as colunas (§3).
st, _ = call("POST", "/tarefas-colunas", ana, {"nome": "Teste", "cor": "#8B5CF6"})
checar(st == 403, f"coordenadora não cria coluna → 403 (got {st})")

print("\n=== F8 · Reuniões ===")
# Idempotente: limpa as reuniões do Alfa antes, para rodar quantas vezes quiser.
_, existentes = call("GET", f"/projetos/{alfa}/reunioes", ana)
for r_antiga in existentes["reunioes"]:
    call("DELETE", f"/reunioes/{r_antiga['id']}", ana)

st, r = call("POST", f"/projetos/{alfa}/reunioes", ana, {"data_reuniao": "2026-08-05"})
checar(st == 200, f"registrar reunião (got {st})")
st, _ = call("POST", f"/projetos/{alfa}/reunioes", ana, {"data_reuniao": "2026-08-05"})
checar(st == 422, f"mesma data duas vezes → 422 (got {st})")
st, lista = call("GET", f"/projetos/{alfa}/reunioes", ana)
checar(lista["tem_reuniao_esta_semana"] is True, "tem_reuniao_esta_semana=True")
st, movida_r = call("PATCH", f"/reunioes/{r['id']}", ana, {"data_reuniao": "2026-08-06"})
checar(st == 200 and movida_r["data_reuniao"] == "2026-08-06", "mover a reunião de quarta p/ quinta")

print("\n=== F9 · Calendário geral ===")
st, eventos = call("GET", "/calendario/eventos?inicio=2026-07-01&fim=2026-09-30", bia)
tipos = {e["tipo"] for e in eventos}
checar(st == 200, "consultora acessa (sem recorte de visão, §6.5)")
checar({"banca", "kickoff", "reuniao"} <= tipos, f"agrega múltiplos tipos: {sorted(tipos)}")
nomes = {e["projeto_nome"] for e in eventos}
checar("Projeto Beta" in nomes, "consultora vê evento de projeto que NÃO é dela (Beta)")
st, so_banca = call("GET", "/calendario/eventos?inicio=2026-07-01&fim=2026-09-30&tipos=banca", bia)
checar(all(e["tipo"] == "banca" for e in so_banca), "filtro por tipo isola")

print("\n=== F10 · Monitoramento ===")
st, _ = call("GET", "/monitoramento/visao-geral", bia)
checar(st == 403, f"consultora bloqueada no monitoramento → 403 (got {st})")

st, vg = call("GET", "/monitoramento/visao-geral", dani)
checar(st == 200, "diretora acessa")
placar = vg["placar_gestao"]
checar(placar["percentual"] < 100,
       f"placar NÃO é 100% — a banca atrasada do Beta conta ({placar['percentual']}%)")
checar(vg["kpis"]["atrasados"] >= 1, f"KPI atrasados={vg['kpis']['atrasados']}")
motivos = [i["motivo"] for i in vg["atencao_agora"]]
checar(any("venceu" in m for m in motivos), f"motivo explícito: {motivos[:3]}")

st, at = call("GET", "/monitoramento/atrasos", dani)
checar(len(at["por_projeto"]) >= 1, "aba Atrasos lista o Beta")
checar(len(at["por_coordenador"]) >= 1, "atrasos por coordenador")

st, al = call("GET", "/monitoramento/alocacao", dani)
checar(len(al["consultores"]) > 0, "carga por consultor")

st, ex = call("GET", "/monitoramento/execucao", dani)
checar(len(ex["tarefas"]) > 0, "execução: tabela de tarefas")

print("\n=== §7.5 · O gerente fica travado na própria frente ===")
_, vg_dani = call("GET", "/monitoramento/visao-geral", dani)
_, vg_gil = call("GET", "/monitoramento/visao-geral", gil)
checar(vg_dani["kpis"]["total"] > vg_gil["kpis"]["total"],
       f"diretora vê {vg_dani['kpis']['total']}, gerente Business vê {vg_gil['kpis']['total']}")
# Gil tenta forçar a frente Direito (do Beta) — deve continuar vendo só a dele.
_, forcado = call("GET", "/monitoramento/visao-geral?frente_id=2", gil)
checar(forcado["kpis"]["total"] == vg_gil["kpis"]["total"],
       "gerente forçando ?frente_id de outra frente não amplia a visão")

print(f"\n{'✅ TUDO PASSOU' if falhas == 0 else f'❌ {falhas} FALHA(S)'}")
raise SystemExit(1 if falhas else 0)
