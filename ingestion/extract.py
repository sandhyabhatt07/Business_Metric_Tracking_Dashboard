"""Extractors: pull rows out of each source system, changing as little as possible.

Cleaning happens later, in dbt staging models. Here we only flatten structures and keep provenance.
"""

import csv
import json
import sqlite3
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

APP_TABLES = ["accounts", "users", "subscriptions", "invoices", "experiment_assignments", "events"]
FX_CURRENCIES = ["EUR", "GBP", "AUD", "INR"]
CRM_PAGE_SIZE = 500


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "metrics-pipeline"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


# --- App DB -------------------------------------------------------------------------------------

def extract_app_table(db_path: Path, table: str, received_from: datetime | None = None,
                      received_to: datetime | None = None) -> list[dict]:
    """Full extract of an App DB table; `events` can be limited to a `received_at` window."""
    if table not in APP_TABLES:
        raise ValueError(f"unknown app table {table!r}")
    sql, params = f"SELECT * FROM {table}", []
    if table == "events" and received_from is not None:
        sql += " WHERE received_at >= ? AND received_at < ?"
        params = [received_from.strftime("%Y-%m-%d %H:%M:%S"), received_to.strftime("%Y-%m-%d %H:%M:%S")]
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params)]


# --- CRM ----------------------------------------------------------------------------------------

def _crm_pages(source: str) -> Iterator[dict]:
    """Follow `paging.next.after` cursors, from an HTTP API or from saved pages on disk."""
    after = None
    while True:
        if _is_url(source):
            query = urllib.parse.urlencode({"limit": CRM_PAGE_SIZE, **({"after": after} if after else {})})
            page = _get_json(f"{source.rstrip('/')}/companies?{query}")
        else:
            n = 1 if after is None else int(after) // CRM_PAGE_SIZE + 1
            page = json.loads((Path(source) / f"companies_page_{n:04d}.json").read_text())
        yield page
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            return


def extract_crm(source: str) -> list[dict]:
    rows = []
    for page in _crm_pages(source):
        for rec in page["results"]:
            props = rec["properties"]
            rows.append({"crm_company_id": rec["id"], **{k: _str_or_none(v) for k, v in props.items()},
                         "_raw": json.dumps(rec, separators=(",", ":"))})
    return rows


def _str_or_none(v):
    return None if v is None else str(v)


# --- Ad spend CSV -------------------------------------------------------------------------------

def extract_ad_spend(folder: Path) -> list[dict]:
    """Every row of every monthly export, as text, tagged with the file it came from."""
    rows = []
    for path in sorted(folder.glob("ad_spend_*.csv")):
        with path.open(newline="") as fh:
            for line_no, r in enumerate(csv.DictReader(fh), start=2):
                rows.append({k.lower(): v for k, v in r.items()} | {"_source_file": path.name,
                                                                      "_source_line": line_no})
    return rows


# --- FX API -------------------------------------------------------------------------------------

def _month_starts(start: date, end: date) -> Iterator[date]:
    d = date(start.year, start.month, 1)
    while d <= end:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def extract_fx(source: str, start: date, end: date) -> list[dict]:
    """USD-based daily rates, one row per (date, currency).

    With an http(s) source this calls a Frankfurter-compatible API, e.g. https://api.frankfurter.dev/v1
    """
    rows = []
    for m in _month_starts(start, end):
        if _is_url(source):
            m_end = min(date(m.year + (m.month == 12), m.month % 12 + 1, 1).toordinal() - 1, end.toordinal())
            rng = f"{max(m, start).isoformat()}..{date.fromordinal(m_end).isoformat()}"
            body = _get_json(f"{source.rstrip('/')}/{rng}?from=USD&to={','.join(FX_CURRENCIES)}")
        else:
            path = Path(source) / f"usd_rates_{m.year}_{m.month:02d}.json"
            if not path.exists():
                continue
            body = json.loads(path.read_text())
        for day, rates in body["rates"].items():
            if not (start.isoformat() <= day <= end.isoformat()):
                continue
            for cur, rate in rates.items():
                rows.append({"rate_date": day, "base_currency": body["base"], "currency": cur,
                             "rate": str(rate)})
    return rows
