import base64
import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://dof.gob.mx/indicadores.php"
OUT_FILE = "latest-rate.json"


def fetch_rate():
    resp = requests.get(
        URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; cambio-usd-mxn-bot/1.0)"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n")

    date_match = re.search(r"Tipo de Cambio y Tasas al\s+(\d{2}/\d{2}/\d{4})", text)
    if not date_match:
        raise RuntimeError("Não encontrei o padrão de data 'Tipo de Cambio y Tasas al DD/MM/YYYY' na página do DOF.")
    date_br = date_match.group(1)
    day, month, year = date_br.split("/")
    date_iso = f"{year}-{month}-{day}"

    # Look for "DOLAR" label followed (within a few lines) by a decimal number.
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    rate = None
    for i, line in enumerate(lines):
        if line.upper() == "DOLAR":
            for j in range(i + 1, min(i + 4, len(lines))):
                m = re.match(r"^\$?\s*([\d]+\.[\d]+)$", lines[j].replace(",", ""))
                if m:
                    rate = float(m.group(1))
                    break
            if rate is not None:
                break
    if rate is None:
        raise RuntimeError("Não encontrei um valor numérico logo após o rótulo 'DOLAR' na página do DOF.")

    # Sanity check: FIX rate should plausibly sit between 10 and 30 MXN per USD.
    if not (10.0 <= rate <= 30.0):
        raise RuntimeError(f"Valor extraído ({rate}) fora da faixa plausível (10-30). Abortando por segurança.")

    return date_iso, rate


def main():
    try:
        date_iso, rate = fetch_rate()
    except Exception as exc:
        print(f"ERRO ao buscar/parsear cotação do DOF: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "date": date_iso,
        "rate": rate,
        "source": "dof",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"OK: {date_iso} -> {rate}")


if __name__ == "__main__":
    main()
