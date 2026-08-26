#!/usr/bin/env python3
"""
Atualiza data.json com a cotação FIX mais recente do Banco de México
(API SIE, série SF43718) e reconstrói index.html a partir de template.html.

Regra de datas: a API do Banxico rotula cada cotação com a data em que ela
foi *determinada*. O site usa a data de *vigência* (determinação + 1 dia
útil) para casar com a convenção usada nos dados históricos importados do
DOF. Por isso todo ponto novo é deslocado para o próximo dia útil antes de
ser gravado.
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, timedelta

SERIES = "SF43718"
TOKEN = os.environ.get("BANXICO_TOKEN")
URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{}/datos/oportuno?token={}".format(
    SERIES, TOKEN
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(REPO_ROOT, "data.json")
TEMPLATE_PATH = os.path.join(REPO_ROOT, "template.html")
OUTPUT_PATH = os.path.join(REPO_ROOT, "index.html")


def business_day_after(d):
    d = d + timedelta(days=1)
    while d.weekday() >= 5:  # 5=sábado, 6=domingo
        d += timedelta(days=1)
    return d


def fetch_latest():
    if not TOKEN:
        print("BANXICO_TOKEN não configurado.", file=sys.stderr)
        sys.exit(1)
    req = urllib.request.Request(URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    return payload["bmx"]["series"][0]["datos"]


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        history = json.load(f)
    existing_dates = set(p["date"] for p in history)

    datos = fetch_latest()
    added = []
    for d in datos:
        raw = d.get("dato")
        if not raw or raw in ("N/E", "n/e"):
            continue
        day_s, month_s, year_s = d["fecha"].split("/")
        determ_date = date(int(year_s), int(month_s), int(day_s))
        vig_date = business_day_after(determ_date)
        vig_iso = vig_date.isoformat()
        if vig_iso in existing_dates:
            continue
        try:
            rate = float(raw.replace(",", ""))
        except ValueError:
            continue
        history.append({"date": vig_iso, "rate": rate, "source": "banxico"})
        existing_dates.add(vig_iso)
        added.append(vig_iso)

    if not added:
        print("Nenhum ponto novo (já atualizado ou fim de semana/feriado).")
        return

    history.sort(key=lambda p: p["date"])

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()
    rendered = template.replace(
        "__RATE_HISTORY_JSON__", json.dumps(history, ensure_ascii=False)
    )
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)

    print("Pontos adicionados:", added)


if __name__ == "__main__":
    main()
