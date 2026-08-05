"""Smoke test da Avaliação de Desempenho direto contra a API rodando.

    uvicorn src.app:app --port 8000               # num terminal
    .venv/bin/python -m scripts.seed              # dados da demo (se ainda não tiver rodado)
    .venv/bin/python -m scripts.seed_desempenho   # formulários de desempenho
    python3 scripts/smoke_api_desempenho.py       # noutro terminal

Cobre: abertura de lote, formulário seed, fila do usuário, submissão +
duplicidade, pendências, cascata de finalização, mentoria e recorte de acesso
ao relatório.
"""
import json
import urllib.request
from datetime import datetime, timedelta

BASE = "http://localhost:8000"


def call(metodo, caminho, token=None, corpo=None):
    req = urllib.request.Request(
        BASE + caminho,
        method=metodo,
        data=json.dumps(corpo, default=str).encode() if corpo is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
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


falhas = 0


def checar(cond, msg):
    global falhas
    print(f"  {'✅' if cond else '❌'} {msg}")
    if not cond:
        falhas += 1


dani = login("dani@al.insper.edu.br")  # diretor
ana_token = login("ana@al.insper.edu.br")  # coordenador do Alfa
bia_token = login("bia@gmail.com")  # consultora do Alfa
caio_token = login("caio@icloud.com")  # consultor do Alfa

_, usuarios = call("GET", "/usuarios", token=dani)
por_email = {u["email_insper"]: u for u in usuarios}
ana = por_email["ana@al.insper.edu.br"]
bia = por_email["bia@gmail.com"]
caio = por_email["caio@icloud.com"]

_, projetos = call("GET", "/projetos", token=dani)
alfa = next(p for p in projetos if p["nome"] == "Projeto Alfa")

agora = datetime.now()

print("1. Criar lote periódico cobrindo o Projeto Alfa")
status, lote = call(
    "POST",
    "/desempenho/lotes",
    token=dani,
    corpo={
        "nome": "Periódica smoke test",
        "tipo": "periodico",
        "data_inicio": (agora - timedelta(days=1)).isoformat(),
        "data_fim": (agora + timedelta(days=30)).isoformat(),
        "projeto_ids": [alfa["id"]],
    },
)
checar(status == 200, f"lote periódico criado (status={status})")
checar(lote["aberto"] is True, "lote nasce aberto (dentro da janela de datas)")
lote_id = lote["id"]

print("\n2. Formulário periodico/consultor tem 3 seções / 7 critérios")
status, formulario = call("GET", "/desempenho/formularios/periodico/consultor", token=bia_token)
total_criterios = sum(len(s["criterios"]) for s in formulario["secoes"])
checar(status == 200 and len(formulario["secoes"]) == 3 and total_criterios == 7, "3 seções, 7 critérios")

print("\n3. Fila da Bia inclui Ana (coordenadora) e Caio (consultor)")
status, fila_bia = call("GET", f"/usuarios/{bia['id']}/desempenho/fila", token=bia_token)
avaliados_bia = {item["avaliado_id"] for item in fila_bia}
checar(status == 200 and {ana["id"], caio["id"]} <= avaliados_bia, "Ana e Caio na fila da Bia")

print("\n4. Bia avalia Ana (coordenadora) — depois repete e recebe 422")
item_ana = next(item for item in fila_bia if item["avaliado_id"] == ana["id"])
_, formulario_coord = call("GET", "/desempenho/formularios/periodico/coordenador", token=bia_token)
criterios_coord = [c["id"] for s in formulario_coord["secoes"] for c in s["criterios"]]
payload_avaliacao = {
    "lote_id": lote_id,
    "avaliado_id": ana["id"],
    "nota_geral": 4,
    "comentarios": "Ótima liderança, ponto de melhoria: comunicação de prazos.",
    "notas": [{"criterio_id": cid, "nota": 4} for cid in criterios_coord],
}
status, resultado = call("POST", "/desempenho/avaliacoes", token=bia_token, corpo=payload_avaliacao)
checar(status == 200, f"Bia avaliou Ana (status={status}) — {resultado if status != 200 else ''}")

status_dup, resultado_dup = call("POST", "/desempenho/avaliacoes", token=bia_token, corpo=payload_avaliacao)
checar(status_dup == 422, f"repetir a mesma avaliação dá 422 (status={status_dup})")

print("\n5. Pendências do lote não mostram mais o par Bia→Ana como faltante")
status, pendencias = call("GET", f"/desempenho/lotes/{lote_id}/pendencias", token=dani)
par_bia_ana = next(p for p in pendencias if p["avaliador_id"] == bia["id"] and p["avaliado_id"] == ana["id"])
checar(par_bia_ana["respondida"] is True, "par Bia→Ana marcado como respondido")

print("\n6. Criar lote de finalização do mesmo projeto dispara a cascata (2.2)")
status, lote_final = call(
    "POST",
    "/desempenho/lotes",
    token=dani,
    corpo={
        "nome": "Finalização smoke test",
        "tipo": "finalizacao",
        "data_inicio": (agora - timedelta(days=1)).isoformat(),
        "data_fim": (agora + timedelta(days=10)).isoformat(),
        "projeto_ids": [alfa["id"]],
    },
)
checar(status == 200, f"lote de finalização criado (status={status})")
status, lotes_todos = call("GET", "/desempenho/lotes?abertos=false", token=dani)
lote_periodico_atualizado = next(l for l in lotes_todos if l["id"] == lote_id)
checar(alfa["id"] not in lote_periodico_atualizado["projeto_ids"], "projeto Alfa saiu do lote periódico (cascata)")

print("\n7. Mentoria: Ana mentora de Bia (idempotente — pode já existir de uma rodada anterior)")
status, mentoria = call(
    "POST", "/desempenho/mentorias", token=dani, corpo={"mentor_id": ana["id"], "mentorado_id": bia["id"]}
)
checar(status in (200, 422), f"mentoria criada ou já existente (status={status})")
status, mentorados_ana = call("GET", f"/usuarios/{ana['id']}/desempenho/mentorados", token=ana_token)
checar(status == 200 and any(m["mentorado_id"] == bia["id"] for m in mentorados_ana), "Ana vê Bia como mentorada")

print("\n8. Caio (não-mentor) não pode ver o relatório da Bia")
status, _ = call("GET", f"/usuarios/{bia['id']}/desempenho/relatorio", token=caio_token)
checar(status == 403, f"Caio recebe 403 ao tentar ver relatório da Bia (status={status})")

print("\n9. Ana (mentora) pode ver o relatório da Bia")
status, _ = call("GET", f"/usuarios/{bia['id']}/desempenho/relatorio", token=ana_token)
checar(status == 200, f"Ana (mentora) vê o relatório da Bia (status={status})")

print(f"\n{'✅ tudo passou' if falhas == 0 else f'❌ {falhas} falha(s)'}")
