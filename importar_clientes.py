"""
Script de importação de clientes — Arretado Doces CRM
Lê o arquivo clientes.xlsx e insere via API REST /api/v1/clientes/

Uso:
    python importar_clientes.py
    python importar_clientes.py --api-url http://meu-servidor/api/v1 --dry-run

Dependências:
    pip install pandas openpyxl requests
"""

import argparse
import re
import sys

import pandas as pd
import requests

# ── Configuração padrão ────────────────────────────────────────────────────────
DEFAULT_API_URL = "http://localhost:8000/api/v1"
EXCEL_FILE      = "clientes.xlsx"

# E-mails genéricos usados como placeholder no sistema de origem — serão ignorados
EMAILS_PLACEHOLDER = {
    "arretadodoces@gmail.com",
    "arretadodocesadm@gmail.com",
}

# CPF inválido (cliente consumidor genérico) — linha será pulada
CPF_INVALIDO = "000.000.000-00"


# ── Helpers ────────────────────────────────────────────────────────────────────

def formatar_cpf(raw: str) -> str | None:
    """Recebe '394.685.003-06' ou '39468500306' e devolve '394.685.003-06' ou None."""
    if not raw or pd.isna(raw):
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return None  # CNPJ ou inválido → ignorar


def eh_cnpj(raw: str) -> bool:
    if not raw or pd.isna(raw):
        return False
    return "/" in str(raw)


def limpar_email(raw: str) -> str | None:
    if not raw or pd.isna(raw):
        return None
    email = str(raw).strip().lower()
    if email in EMAILS_PLACEHOLDER or "@" not in email:
        return None
    return email


def limpar_telefone(raw: str) -> str | None:
    if not raw or pd.isna(raw):
        return None
    t = str(raw).strip()
    return t if t else None


def limpar_nome(raw: str) -> str | None:
    if not raw or pd.isna(raw):
        return None
    n = str(raw).strip()
    return n if n else None


def extrair_cidade(raw: str) -> str | None:
    """'Teresina (PI)' → 'Teresina'"""
    if not raw or pd.isna(raw):
        return None
    return re.sub(r"\s*\([A-Z]{2}\)\s*$", "", str(raw)).strip()


def montar_payload(row: pd.Series) -> dict | None:
    """Converte uma linha do DataFrame em payload para a API. Retorna None se a linha deve ser pulada."""
    cpf_raw = str(row.get("CNPJ / CPF", "")).strip()

    # Pula cliente consumidor genérico
    if cpf_raw == CPF_INVALIDO:
        return None

    # Pula empresas (CNPJ)
    if eh_cnpj(cpf_raw):
        return None

    nome = limpar_nome(row.get("Razão Social / Nome Completo"))
    if not nome:
        return None

    telefone = limpar_telefone(row.get("Telefone"))
    if not telefone:
        # telefone_principal é obrigatório no modelo; pula sem telefone
        return None

    cpf = formatar_cpf(cpf_raw)
    email = limpar_email(row.get("E-mail"))

    payload = {
        "nome": nome,
        "telefone_principal": telefone,
        "status": "ativo",
    }
    if cpf:
        payload["cpf"] = cpf
    if email:
        payload["email"] = email

    return payload


# ── Import ─────────────────────────────────────────────────────────────────────

def importar(api_url: str, dry_run: bool):
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Lendo: {EXCEL_FILE}")
    df = pd.read_excel(EXCEL_FILE, dtype=str, header=1, skiprows=[0])
    print(f"  {len(df)} linhas no arquivo\n")

    stats = {"ok": 0, "pulado": 0, "erro": 0, "duplicado": 0}
    erros = []
    pulados = []

    for idx, row in df.iterrows():
        payload = montar_payload(row)

        if payload is None:
            motivo = "CNPJ / CPF inválido ou cliente genérico ou sem telefone"
            stats["pulado"] += 1
            pulados.append({"linha": idx + 3, "nome": row.get("Razão Social / Nome Completo", "?"), "motivo": motivo})
            continue

        if dry_run:
            print(f"  [L{idx+3}] SIMULADO → {payload['nome']} | {payload.get('cpf','sem CPF')} | {payload['telefone_principal']}")
            stats["ok"] += 1
            continue

        try:
            resp = requests.post(f"{api_url}/clientes/", json=payload, timeout=10)

            if resp.status_code == 201:
                dados = resp.json()
                print(f"  ✅ [L{idx+3}] Criado (id={dados['id']}) → {payload['nome']}")
                stats["ok"] += 1

            elif resp.status_code == 400:
                erros_api = resp.json()
                # CPF ou e-mail duplicado
                if "cpf" in erros_api or "email" in erros_api:
                    stats["duplicado"] += 1
                    print(f"  ⚠️  [L{idx+3}] Duplicado → {payload['nome']} | {erros_api}")
                else:
                    stats["erro"] += 1
                    erros.append({"linha": idx + 3, "nome": payload["nome"], "erro": erros_api})
                    print(f"  ❌ [L{idx+3}] Erro 400 → {payload['nome']} | {erros_api}")

            else:
                stats["erro"] += 1
                erros.append({"linha": idx + 3, "nome": payload["nome"], "erro": f"HTTP {resp.status_code}"})
                print(f"  ❌ [L{idx+3}] HTTP {resp.status_code} → {payload['nome']}")

        except requests.exceptions.ConnectionError:
            print(f"\n  💥 Não foi possível conectar em {api_url}. Verifique se o servidor Django está rodando.\n")
            sys.exit(1)

    # ── Resumo ─────────────────────────────────────────────────────────────────
    print("\n" + "═" * 55)
    print("RESUMO DA IMPORTAÇÃO")
    print("═" * 55)
    print(f"  ✅ Inseridos com sucesso : {stats['ok']}")
    print(f"  ⚠️  Duplicados (já existem): {stats['duplicado']}")
    print(f"  ⏭️  Pulados (sem telefone / CNPJ / genérico): {stats['pulado']}")
    print(f"  ❌ Erros                 : {stats['erro']}")
    print("═" * 55)

    if pulados:
        print("\nLinhas puladas:")
        for p in pulados:
            print(f"  L{p['linha']:>3} — {str(p['nome'])[:50]}")

    if erros:
        print("\nErros detalhados:")
        for e in erros:
            print(f"  L{e['linha']:>3} — {e['nome']}: {e['erro']}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa clientes do Excel para o CRM Arretado")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="URL base da API (ex: http://localhost:8000/api/v1)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem fazer POST na API")
    args = parser.parse_args()

    importar(api_url=args.api_url.rstrip("/"), dry_run=args.dry_run)
