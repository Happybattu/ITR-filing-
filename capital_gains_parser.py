"""
capital_gains_parser.py
Reads a broker's capital gains / Tax P&L export (CSV or Excel — Zerodha
Console, Groww, Upstox, ICICI Direct etc. all export similar tables with
different column names) and produces STCG/LTCG totals for equity shares
and equity mutual funds, ready to feed into tax_calculator.TaxInputs.

IMPORTANT LIMITATIONS (v1):
- Assumes listed equity / equity MF (111A short-term, 112A long-term).
  Debt funds, unlisted shares, property etc. are NOT handled — those
  have different holding-period thresholds and tax treatment.
- Does NOT apply LTCG grandfathering (Jan 31, 2018 cost step-up) for
  shares bought before that date — if you have pre-2018 holdings,
  your actual LTCG may differ from what this reports. Flagged as a
  warning when such trades are detected.
- Holding period > 365 days = long-term. This is correct for listed
  equity/equity MF but wrong for other asset classes.
"""

import pandas as pd
from datetime import datetime


# Column name variants seen across broker exports — extend as you hit new formats
COLUMN_ALIASES = {
    "symbol": ["symbol", "scrip name", "stock name", "instrument", "security name", "isin"],
    "buy_date": ["buy date", "purchase date", "date of purchase", "entry date", "buy_date"],
    "sell_date": ["sell date", "sale date", "date of sale", "exit date", "sell_date"],
    "quantity": ["qty", "quantity", "shares", "no of shares"],
    "buy_value": ["buy value", "purchase value", "buy amount", "cost of acquisition", "buy price"],
    "sell_value": ["sell value", "sale value", "sell amount", "sale consideration", "sell price"],
    "realized_pnl": ["realized p&l", "realised p&l", "profit/loss", "profit", "pnl", "p&l", "taxable profit"],
    "holding_type": ["period of holding", "term", "st/lt", "type"],
}

GRANDFATHER_CUTOFF = datetime(2018, 1, 31)
LTCG_HOLDING_DAYS = 365


def _normalize_columns(df: pd.DataFrame) -> dict:
    """Map actual dataframe columns to our canonical field names."""
    mapping = {}
    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                mapping[field] = lower_cols[alias]
                break
    return mapping


def _find_header_row(raw_df: pd.DataFrame) -> int | None:
    """Broker exports often have a few title/summary rows before the real
    header. Scan the first 15 rows for one that matches known column names."""
    for idx in range(min(15, len(raw_df))):
        row_values = [str(v).strip().lower() for v in raw_df.iloc[idx].tolist()]
        hits = 0
        for aliases in COLUMN_ALIASES.values():
            if any(v in aliases for v in row_values):
                hits += 1
        if hits >= 3:  # at least 3 recognizable columns = likely the header
            return idx
    return None


def _load_table(file_path: str, sheet_name=None) -> pd.DataFrame:
    if file_path.lower().endswith((".xlsx", ".xls")):
        # pd.read_excel treats sheet_name=None as "read ALL sheets" and
        # returns a dict of {sheet_name: DataFrame} instead of a single
        # DataFrame — that's what was hitting raw.iloc[idx] below and
        # throwing "'dict' object has no attribute 'iloc'".
        # Default to the first sheet unless the caller asks for a specific one.
        effective_sheet = sheet_name if sheet_name is not None else 0
        raw = pd.read_excel(file_path, sheet_name=effective_sheet, header=None)
        if isinstance(raw, dict):
            # Still possible if caller passes a list of sheet names/indices.
            raw = next(iter(raw.values()))
    else:
        raw = pd.read_csv(file_path, header=None)

    header_row = _find_header_row(raw)
    if header_row is None:
        raise ValueError("Couldn't locate a recognizable header row in this file.")

    df = raw.iloc[header_row + 1:].copy()
    df.columns = raw.iloc[header_row]
    return df.reset_index(drop=True)


def parse_broker_pnl(file_path: str, sheet_name=None) -> dict:
    """
    Returns:
        {
          "stcg_total": float,
          "ltcg_total": float,
          "trade_count": int,
          "warnings": [str, ...],
          "trades": [ {symbol, buy_date, sell_date, pnl, term}, ... ]
        }
    """
    warnings = []
    df = _load_table(file_path, sheet_name=sheet_name)
    colmap = _normalize_columns(df)

    required = ["sell_date", "realized_pnl"]
    missing = [f for f in required if f not in colmap]
    if missing:
        raise ValueError(
            f"Missing required column(s): {missing}. "
            f"Detected columns: {list(colmap.keys())}. "
            "Open the file and check header names, or extend COLUMN_ALIASES."
        )

    stcg_total = 0.0
    ltcg_total = 0.0
    trades = []
    pre_2018_count = 0
    unparsed_rows = 0

    for _, row in df.iterrows():
        try:
            pnl = pd.to_numeric(row[colmap["realized_pnl"]], errors="coerce")
            if pd.isna(pnl):
                continue

            sell_date = pd.to_datetime(row[colmap["sell_date"]], errors="coerce", dayfirst=True)
            buy_date = None
            if "buy_date" in colmap:
                buy_date = pd.to_datetime(row[colmap["buy_date"]], errors="coerce", dayfirst=True)

            # Determine term: prefer explicit holding_type column, else compute from dates
            term = None
            if "holding_type" in colmap:
                raw_term = str(row[colmap["holding_type"]]).strip().lower()
                if "long" in raw_term or raw_term in ("lt", "ltcg"):
                    term = "LT"
                elif "short" in raw_term or raw_term in ("st", "stcg"):
                    term = "ST"

            if term is None and buy_date is not None and pd.notna(buy_date) and pd.notna(sell_date):
                holding_days = (sell_date - buy_date).days
                term = "LT" if holding_days > LTCG_HOLDING_DAYS else "ST"
                if buy_date < GRANDFATHER_CUTOFF and term == "LT":
                    pre_2018_count += 1

            if term is None:
                unparsed_rows += 1
                continue

            if term == "LT":
                ltcg_total += float(pnl)
            else:
                stcg_total += float(pnl)

            trades.append({
                "symbol": str(row[colmap["symbol"]]) if "symbol" in colmap else "",
                "buy_date": str(buy_date.date()) if buy_date is not None and pd.notna(buy_date) else "",
                "sell_date": str(sell_date.date()) if pd.notna(sell_date) else "",
                "pnl": round(float(pnl), 2),
                "term": term,
            })
        except Exception:
            unparsed_rows += 1
            continue

    if pre_2018_count:
        warnings.append(
            f"{pre_2018_count} long-term trade(s) were bought before Jan 31, 2018 — "
            "LTCG grandfathering isn't applied here, so actual taxable gain may be lower "
            "than shown. Check these manually."
        )
    if unparsed_rows:
        warnings.append(f"{unparsed_rows} row(s) couldn't be classified and were skipped — review the source file.")
    if not trades:
        warnings.append("No valid trades were parsed — check the file format and column headers.")

    return {
        "stcg_total": round(stcg_total, 2),
        "ltcg_total": round(ltcg_total, 2),
        "trade_count": len(trades),
        "warnings": warnings,
        "trades": trades,
    }


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("Usage: python3 capital_gains_parser.py <path-to-broker-pnl.csv|xlsx>")
    else:
        result = parse_broker_pnl(sys.argv[1])
        print(json.dumps(result, indent=2))
