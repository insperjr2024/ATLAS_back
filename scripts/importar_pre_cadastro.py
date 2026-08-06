"""Importa os membros do formulário de pré-cadastro (§10) pra dentro do
banco — cada linha da planilha vira um `UsuarioModel` + vínculo de frente.

Nunca apaga nem altera quem já existe: só insere gente nova, tanto os que
outra pessoa já criou localmente (seed, cadastro manual) quanto os que essa
mesma importação já criou numa rodada anterior — a trava é o e-mail.

Também pula os 5 fundadores que reaparecem na planilha (submeteram o mesmo
formulário de pré-cadastro com nome completo e e-mail diferente da conta que
já têm) — mesma lista de exclusão do globo de nomes da tela de login
(`ATLAS_front/src/components/MembersGlobe.tsx`); se um dia aparecer um "José
Saraiva" na planilha, também é pulado por já ter o ponto fixo do polo norte.

Rodar:  .venv/Scripts/python.exe -m scripts.importar_pre_cadastro
Idempotente — rodar de novo não duplica nada.
"""

import re
import unicodedata
from pathlib import Path

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.config import get_settings
from src.models.cargo_model import CargoModel
from src.models.frente_model import FrenteModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.utils.senha import hash_senha

PLANILHA = Path(__file__).resolve().parents[2] / "Pre-cadastro-Plataforma-de-Projetos.xlsx"
SENHA_PADRAO = "atlas123"

# Já têm conta própria — ver o comentário do módulo. Comparado por nome
# normalizado (sem acento/maiúscula), não por e-mail, porque a planilha traz
# um e-mail pessoal diferente do que cada um já usa pra logar.
NOMES_EXCLUIDOS = {
    "heloisa nogueira",
    "henrique montoro",
    "joao baptista",
    "enzo perego",
    "mateus loureiro",
    "jose saraiva",
}

PERFIL_PARA_POSICAO = {
    "Diretora": "diretor",
    "Diretor": "diretor",
    "Gerente": "gerente",
    "Gerente e Coordenador": "gerente",
    "Coordenador": "coordenador",
    "Consultor": "consultor",
}

# Mesmo pareamento posição↔cargo do scripts/seed.py — cargo_id é a dimensão
# do módulo de bancas, mas por padrão nasce alinhado com a posição.
POSICAO_PARA_CARGO = {
    "diretor": "Diretor de Projetos",
    "gerente": "Gerente de Frente",
    "coordenador": "Coordenador",
    "consultor": "Membro",
}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def eh_fundador(nome_completo: str) -> bool:
    partes = set(normalizar(nome_completo).split(" "))
    return any(
        set(excluido.split(" ")).issubset(partes) for excluido in NOMES_EXCLUIDOS
    )


def ler_planilha():
    wb = openpyxl.load_workbook(PLANILHA, data_only=True)
    ws = wb.worksheets[0]
    linhas = []
    for nome, email, perfil, frente in ws.iter_rows(min_row=2, values_only=True):
        if not nome or not email:
            continue
        linhas.append((str(nome).strip(), str(email).strip(), (perfil or "").strip(), (frente or "").strip()))
    return linhas


def executar():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL, connect_args={"charset": "utf8mb4"})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    criados = pulados_fundador = pulados_existente = sem_frente = sem_perfil = 0
    try:
        cargos = {c.nome: c for c in db.query(CargoModel).all()}
        frentes = {f.nome: f for f in db.query(FrenteModel).all()}

        for nome, email, perfil, nome_frente in ler_planilha():
            if eh_fundador(nome):
                pulados_fundador += 1
                print(f"pulado (já tem conta): {nome}")
                continue

            if db.query(UsuarioModel).filter_by(email_insper=email).first():
                pulados_existente += 1
                print(f"pulado (e-mail já cadastrado): {nome} <{email}>")
                continue

            posicao = PERFIL_PARA_POSICAO.get(perfil)
            if not posicao:
                sem_perfil += 1
                print(f"AVISO: perfil desconhecido '{perfil}' em '{nome}' — pulando")
                continue

            usuario = UsuarioModel(
                nome=nome,
                email_insper=email,
                senha_hash=hash_senha(SENHA_PADRAO),
                cargo_id=cargos[POSICAO_PARA_CARGO[posicao]].id,
                posicao=posicao,
                status="ativo",
                ativo=True,
            )
            db.add(usuario)
            db.flush()
            criados += 1

            frente = frentes.get(nome_frente)
            if frente:
                db.add(UsuarioFrenteModel(usuario_id=usuario.id, frente_id=frente.id))
            else:
                sem_frente += 1
                print(f"AVISO: sem frente cadastrada para '{nome_frente}' ({nome}) — vínculo de frente não criado")

        db.commit()
    finally:
        db.close()

    print()
    print(
        f"Criados: {criados} | pulados (já tinham conta): {pulados_fundador} | "
        f"pulados (e-mail já existe): {pulados_existente} | sem frente: {sem_frente} | "
        f"perfil desconhecido: {sem_perfil}"
    )
    print(f"Senha inicial de todos os criados: {SENHA_PADRAO!r} (trocar em \"Esqueci a senha\")")


if __name__ == "__main__":
    executar()
