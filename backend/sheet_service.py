"""
sheet_service.py
----------------
Handles all Google Sheets interaction for the weekly report feature.

Responsibilities:
  - Authenticate via Service Account (gspread + google-auth)
  - Fetch all rows from the configured Sheet tab
  - Parse raw print-time strings into minutes (parse_print_time)
  - Normalise each row into a typed dict (normalize_row)

This module does NOT touch the database — that is report_service.py's job.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import Config

logger = logging.getLogger(__name__)

# Read-only scope is sufficient
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# ---------------------------------------------------------------------------
# parse_print_time
# ---------------------------------------------------------------------------

def parse_print_time(raw: str) -> Optional[float]:
    """
    Convert a raw gspread print-time string to total minutes (float).

    Supported formats (gspread returns the exact cell string):
        '8:13:00'   → 493  (H:MM:SS — seconds ignored, only H and M used)
        '1:12:00'   → 72
        '2:05'      → 125  (H:MM)
        ':26'       → 26   (:MM — hours omitted)
        '32'        → 32   (plain integer = minutes)
        '55.5'      → 55.5 (decimal = minutes)
        '1 hour 13' → 73   (text format)
        '2 hours 5' → 125

    Returns None if the string cannot be parsed.
    """
    if not raw or not str(raw).strip():
        return None

    s = str(raw).strip()

    # Strip trailing AM/PM (gspread may return '8:13:00 AM' for time-formatted cells)
    s = re.sub(r'\s*[AaPp][Mm]\s*$', '', s).strip()

    # Reject Excel/Sheets "zero date" sentinel: '12/31/1899 ...' or '1899-12-31 ...'
    # These appear when a time-formatted cell is empty and Sheets returns the epoch origin.
    if re.match(r'^(12/31/1899|1899-12-31)\b', s):
        return None

    # 1. H:MM:SS  (e.g. '8:13:00')
    m = re.match(r'^(\d+):(\d+):(\d+)$', s)
    if m:
        hours, minutes = int(m.group(1)), int(m.group(2))
        return float(hours * 60 + minutes)

    # 2. H:MM  (e.g. '2:05')
    m = re.match(r'^(\d+):(\d+)$', s)
    if m:
        hours, minutes = int(m.group(1)), int(m.group(2))
        return float(hours * 60 + minutes)

    # 3. :MM  (e.g. ':26')
    m = re.match(r'^:(\d+)$', s)
    if m:
        return float(int(m.group(1)))

    # 4. Text: 'N hour(s) M' or 'N hr M'  (e.g. '1 hour 13', '2 hours 5')
    m = re.match(r'^(\d+)\s*hours?\s+(\d+)$', s, re.IGNORECASE)
    if m:
        hours, minutes = int(m.group(1)), int(m.group(2))
        return float(hours * 60 + minutes)

    # 5. Text: 'N hour(s)' with no minutes  (e.g. '2 hours')
    m = re.match(r'^(\d+)\s*hours?$', s, re.IGNORECASE)
    if m:
        return float(int(m.group(1)) * 60)

    # 6. Pure number (integer or decimal) = minutes  (e.g. '32', '55.5')
    m = re.match(r'^(\d+(?:\.\d+)?)$', s)
    if m:
        return float(m.group(1))

    return None


# ---------------------------------------------------------------------------
# _parse_datetime_flexible
# ---------------------------------------------------------------------------

def _parse_datetime_flexible(raw: str) -> Optional[datetime]:
    """
    Try several common date/time formats gspread might return.
    Returns None if none match.
    """
    if not raw or not str(raw).strip():
        return None

    s = str(raw).strip()

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M',
        '%m/%d/%Y',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# _parse_float_safe
# ---------------------------------------------------------------------------

def _parse_float_safe(raw) -> Optional[float]:
    """Return float or None; strips units like 'g', 'grams', whitespace."""
    if raw is None or str(raw).strip() == '':
        return None
    s = re.sub(r'[a-zA-Z\s]', '', str(raw).strip())
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# SheetService
# ---------------------------------------------------------------------------

class SheetService:
    """
    Wraps gspread for reading the DGSpace print-log Google Sheet.

    Typical usage:
        svc = SheetService()
        rows = svc.fetch_sheet_rows()                          # List[dict]
        slicer_map = {'student@x.edu': 63.0, ...}
        normalized = [svc.normalize_row(r, i+2, slicer_map)
                      for i, r in enumerate(rows)]
    """

    def __init__(self):
        self._gc: Optional[gspread.Client] = None

    # ------------------------------------------------------------------
    # connect / auth
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """
        Authenticate with Google using the Service Account JSON file.
        Raises FileNotFoundError or google.auth.exceptions.* on failure.
        """
        creds = Credentials.from_service_account_file(
            Config.SERVICE_ACCOUNT_JSON_PATH,
            scopes=_SCOPES,
        )
        self._gc = gspread.authorize(creds)
        logger.info("SheetService: authenticated with Service Account")

    # ------------------------------------------------------------------
    # fetch_sheet_rows
    # ------------------------------------------------------------------

    def fetch_sheet_rows(self) -> list[dict]:
        """
        Return all data rows as a list of dicts keyed by column header.
        Row order matches the Sheet (first data row = index 2 in Sheets).

        Raises RuntimeError if not yet connected.
        Raises gspread.exceptions.* on API errors.
        """
        if self._gc is None:
            self.connect()

        sheet_id  = Config.GOOGLE_SHEET_ID
        tab_name  = Config.GOOGLE_SHEET_TAB_NAME

        spreadsheet = self._gc.open_by_key(sheet_id)
        worksheet   = spreadsheet.worksheet(tab_name)

        # Some sheets have blank/duplicate header columns (e.g. helper columns).
        # Use get_all_values() + manual dict-building to avoid GSpreadException.
        all_values = worksheet.get_all_values()
        if not all_values:
            return []

        headers = all_values[0]
        rows = []
        for row_values in all_values[1:]:
            # Pad short rows to header length
            padded = row_values + [''] * (len(headers) - len(row_values))
            row_dict = {}
            for h, v in zip(headers, padded):
                if h:  # skip blank headers entirely
                    row_dict[h] = v
            rows.append(row_dict)

        logger.info(
            "SheetService: fetched %d rows from sheet '%s' tab '%s'",
            len(rows), sheet_id, tab_name
        )
        return rows

    # ------------------------------------------------------------------
    # normalize_row
    # ------------------------------------------------------------------

    def normalize_row(
        self,
        row: dict,
        row_index: int,
        slicer_map: dict[str, float],
    ) -> dict:
        """
        Convert a raw gspread row dict into a typed, normalised dict.

        Parameters
        ----------
        row         : raw dict from get_all_records()
        row_index   : 1-based Sheet row number (header = 1, first data = 2)
        slicer_map  : {student_email: slicer_time_minutes} from print_requests

        Returns a dict with both raw values and parsed values, plus:
          error_flag    : True if any parse failure occurred
          error_reason  : comma-joined list of failure descriptions
        """
        col = Config.SHEET_COLUMN_MAP
        errors = []

        def _get(field: str) -> str:
            """Safe column lookup — returns '' if header not in row."""
            header = col.get(field, '')
            return str(row.get(header, '') or '').strip()

        # ---- raw strings ------------------------------------------------
        student_email_raw  = _get('student_email')
        student_name_raw   = _get('student_name')
        operator_name_raw  = _get('operator_name')
        printer_name_raw   = _get('printer_name')
        print_time_raw     = _get('print_time_raw')
        material_used_raw  = _get('material_used_g')
        started_at_raw     = _get('started_at')
        is_finished_raw    = _get('is_finished')
        actual_finish_raw  = _get('actual_finish')
        error_1_raw        = _get('error_1')
        error_2_raw        = _get('error_2')
        file_name_raw      = _get('file_name')

        # ---- parse print time -------------------------------------------
        print_time_minutes = parse_print_time(print_time_raw)
        if print_time_raw and print_time_minutes is None:
            errors.append(f"print_time_raw='{print_time_raw}' could not be parsed")

        # ---- parse material ---------------------------------------------
        material_used_g = _parse_float_safe(material_used_raw)
        if material_used_raw and material_used_g is None:
            errors.append(f"material_used_g='{material_used_raw}' could not be parsed")
        if material_used_g is not None and material_used_g <= 0:
            errors.append(f"material_used_g={material_used_g} is <= 0 (anomaly, written anyway)")

        # ---- parse datetimes --------------------------------------------
        started_at    = _parse_datetime_flexible(started_at_raw)
        actual_finish = _parse_datetime_flexible(actual_finish_raw)

        if started_at_raw and started_at is None:
            errors.append(f"started_at='{started_at_raw}' could not be parsed")

        # ---- slicer time from print_requests ----------------------------
        student_email_lower = student_email_raw.lower()
        slicer_time_minutes = slicer_map.get(student_email_lower)

        # ---- finished_at priority ---------------------------------------
        # Priority: 1 > 2 > 3 > None
        finished_at = None
        if actual_finish is not None:
            finished_at = actual_finish                                    # 1. staff hand-fill
        elif started_at and slicer_time_minutes:
            finished_at = started_at + timedelta(minutes=slicer_time_minutes)  # 2. Cura estimate
        elif started_at and print_time_minutes:
            finished_at = started_at + timedelta(minutes=print_time_minutes)   # 3. Sheet P col

        # ---- is_finished ------------------------------------------------
        is_finished: Optional[int] = None
        if is_finished_raw:
            v = is_finished_raw.lower()
            if v in ('yes', 'true', '1', 'y', 'done', 'finished'):
                is_finished = 1
            elif v in ('no', 'false', '0', 'n', 'not done', 'unfinished'):
                is_finished = 0
            # else: leave as None (unknown value)

        # ---- raw JSON for audit trail -----------------------------------
        raw_json = json.dumps(row, ensure_ascii=False, default=str)

        return {
            # identifiers
            'row_index':            row_index,
            # raw strings (for print_logs_raw)
            'student_email':        student_email_raw,
            'student_name':         student_name_raw,
            'operator_name':        operator_name_raw,
            'printer_name':         printer_name_raw,
            'print_time_raw':       print_time_raw,
            'material_used_raw':    material_used_raw,
            'started_at_raw':       started_at_raw,
            'is_finished_raw':      is_finished_raw,
            'actual_finish_raw':    actual_finish_raw,
            'error_1_raw':          error_1_raw,
            'error_2_raw':          error_2_raw,
            'file_name_raw':        file_name_raw,
            'raw_json':             raw_json,
            # parsed values (for print_logs_normalized)
            'student_email_norm':   student_email_lower or None,
            'print_time_minutes':   print_time_minutes,
            'slicer_time_minutes':  slicer_time_minutes,
            'material_used_g':      material_used_g,
            'slicer_material_g':    None,   # populated by report_service if available
            'started_at':           started_at,
            'finished_at':          finished_at,
            'is_finished':          is_finished,
            'error_1':              error_1_raw or None,
            'error_2':              error_2_raw or None,
            'file_name':            file_name_raw or None,
            # quality flags
            'error_flag':           1 if errors else 0,
            'error_reason':         ', '.join(errors) if errors else None,
        }
