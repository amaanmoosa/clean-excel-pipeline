"""
clean_excel.py — messy spreadsheet in, polished workbook out
============================================================
Fixes three common messes in one pass:
    1. removes duplicate rows based on email addresses
    2. capitalizes every name correctly (Smith, O'Neill, McDonald, Garcia-Lopez)
    3. converts all phone numbers to the international E.164 standard
... then exports a styled, boardroom-ready Excel file.

Setup:  pip install pandas openpyxl phonenumbers
Run:    python clean_excel.py
"""

import re
import pandas as pd
import phonenumbers
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── configuration ────────────────────────────────────────────────────
INPUT_FILE     = "messy_data.xlsx"
OUTPUT_FILE    = "cleaned_data.xlsx"
EMAIL_COLUMN   = "email"
PHONE_COLUMN   = "phone"
NAME_COLUMNS   = ("first_name", "last_name")
DEFAULT_REGION = "US"            # used when a number has no country code

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ── 0 · load ─────────────────────────────────────────────────────────
def load_sheet(path: str) -> pd.DataFrame:
    """Read everything as text — leading zeros and raw formats survive."""
    df = pd.read_excel(path, dtype=str)
    df.columns = (df.columns
                    .str.strip()
                    .str.lower()
                    .str.replace(r"[^a-z0-9]+", "_", regex=True)
                    .str.strip("_"))
    return df


# ── 1 · duplicate emails ─────────────────────────────────────────────
def dedupe_by_email(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize emails, drop blanks + invalids, keep first occurrence."""
    df = df.copy()
    df[EMAIL_COLUMN] = df[EMAIL_COLUMN].fillna("").str.strip().str.lower()
    df = df[df[EMAIL_COLUMN].str.fullmatch(EMAIL_RE)]        # valid only
    return df.drop_duplicates(subset=EMAIL_COLUMN, keep="first")


# ── 2 · name capitalization ──────────────────────────────────────────
SEPARATORS = re.compile(r"([\s\-'’]+)")

def smart_capitalize(name):
    """Title-case a name token by token, preserving its separators."""
    if pd.isna(name) or not str(name).strip():
        return None
    tokens = SEPARATORS.split(str(name).strip())     # separators are kept
    for i, tok in enumerate(tokens):
        if i % 2 or not tok:                         # skip separators
            continue
        if tok.lower().startswith("mc") and len(tok) > 2:
            tokens[i] = "Mc" + tok[2:].capitalize()  # mcdonald → McDonald
        else:
            tokens[i] = tok.capitalize()             # GARCIA → Garcia
    return "".join(tokens)


def format_name_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in NAME_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(smart_capitalize)
    return df


# ── 3 · phone numbers → E.164 ────────────────────────────────────────
def to_e164(value, region: str = DEFAULT_REGION):
    """'(415) 555-2671' → '+14155552671'. Unparseable/invalid → blank."""
    if pd.isna(value) or not str(value).strip():
        return None
    text = re.sub(r"\.0$", "", str(value).strip())   # Excel numeric quirk
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None                                  # give up cleanly
    if not phonenumbers.is_valid_number(number):
        return None                                  # never guess
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def normalize_phones(df: pd.DataFrame) -> pd.DataFrame:
    df[PHONE_COLUMN] = df[PHONE_COLUMN].map(to_e164)
    return df


# ── 4 · polished export ──────────────────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="111827")
BAND_FILL   = PatternFill("solid", fgColor="F3F4F6")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT   = Font(name="Calibri", size=11, color="111827")
GRID        = Side(style="thin", color="E5E7EB")
CELL_BORDER = Border(left=GRID, right=GRID, top=GRID, bottom=GRID)


def export_polished(df: pd.DataFrame, path: str) -> None:
    """Write the workbook — then make it look hand-crafted."""
    out = df.rename(columns=lambda c: c.replace("_", " ").title())

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name="Cleaned Data")
        ws = writer.sheets["Cleaned Data"]

        for c, col in enumerate(out.columns, start=1):            # header row
            cell = ws.cell(row=1, column=c)
            cell.fill, cell.font = HEADER_FILL, HEADER_FONT
            cell.alignment = Alignment(vertical="center")
            sample = out[col].dropna().astype(str).head(100)
            width = max([len(str(col)), *(len(v) for v in sample)]) + 4
            ws.column_dimensions[get_column_letter(c)].width = min(width, 42)

        for r in range(2, len(out) + 2):                          # body
            for c in range(1, len(out.columns) + 1):
                cell = ws.cell(row=r, column=c)
                cell.font, cell.border = BODY_FONT, CELL_BORDER
                if r % 2 == 0:                                    # banded rows
                    cell.fill = BAND_FILL

        ws.row_dimensions[1].height = 24
        ws.freeze_panes = "A2"                    # header follows the scroll
        ws.auto_filter.ref = ws.dimensions        # one-click filtering
        ws.sheet_properties.tabColor = "10B981"


# ── run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"→ loading {INPUT_FILE} …")
    raw = load_sheet(INPUT_FILE)
    before = len(raw)

    clean = dedupe_by_email(raw)
    print(f"✓ email dedupe — {before} → {len(clean)} rows")

    clean = format_name_columns(clean)
    print(f"✓ name columns — {', '.join(c for c in NAME_COLUMNS if c in clean.columns)}")

    clean = normalize_phones(clean).reset_index(drop=True)
    valid = clean[PHONE_COLUMN].notna().sum()
    print(f"✓ phone numbers — {valid} valid · {len(clean) - valid} blanked")

    export_polished(clean, OUTPUT_FILE)
    print(f"✓ exported — {OUTPUT_FILE} · styled & filtered")
