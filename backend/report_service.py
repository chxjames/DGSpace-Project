"""
report_service.py
-----------------
Handles all database operations for the weekly report feature.

Responsibilities:
  - Import normalised rows from sheet_service into print_logs_raw / print_logs_normalized
  - Aggregate weekly KPI metrics (Volume, Material, Capacity, Staffing)
  - Retrieve raw log rows for the admin inspection page

This module does NOT call Google Sheets — that is sheet_service.py's job.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from database import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _week_bounds(week_str: str) -> tuple[datetime, datetime]:
    """
    Convert 'YYYY-WW' (ISO week) to (monday_00:00:00, sunday_23:59:59).

    Examples:
        '2026-05' → 2026-01-26 00:00:00  →  2026-02-01 23:59:59
        '2026-10' → 2026-03-02 00:00:00  →  2026-03-08 23:59:59

    Raises ValueError on bad format.
    """
    try:
        year, week = week_str.split('-')
        # ISO week: Monday is day 1
        monday = datetime.strptime(f'{year}-W{int(week):02d}-1', '%G-W%V-%u')
    except Exception:
        raise ValueError(
            f"Invalid week format '{week_str}'. Expected 'YYYY-WW', e.g. '2026-10'."
        )
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def _custom_bounds(from_date: str, to_date: str) -> tuple[datetime, datetime]:
    """
    Convert 'YYYY-MM-DD' strings to (start_00:00:00, end_23:59:59).
    Raises ValueError on bad format or if from > to.
    """
    try:
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end   = datetime.strptime(to_date,   '%Y-%m-%d')
    except Exception:
        raise ValueError(
            f"Invalid date format. Expected 'YYYY-MM-DD', got '{from_date}' / '{to_date}'."
        )
    if start > end:
        raise ValueError('from_date must be on or before to_date.')
    end = end.replace(hour=23, minute=59, second=59)
    return start, end


def _current_week_str() -> str:
    """Return the current ISO week as 'YYYY-WW'."""
    now = datetime.utcnow()
    return f'{now.isocalendar()[0]}-{now.isocalendar()[1]:02d}'


def _last_week_str() -> str:
    """Return last week's ISO week as 'YYYY-WW'."""
    last = datetime.utcnow() - timedelta(weeks=1)
    return f'{last.isocalendar()[0]}-{last.isocalendar()[1]:02d}'


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------

class ReportService:

    # ------------------------------------------------------------------
    # import_from_sheet
    # ------------------------------------------------------------------

    def import_from_sheet(self, normalized_rows: list[dict]) -> dict:
        """
        Persist a list of normalised rows (from SheetService.normalize_row)
        into print_logs_raw + print_logs_normalized.

        Uses a single batch_id UUID for the whole import run.
        UPSERT strategy: keyed on row_index — re-running the sync with the
        same sheet data is idempotent.

        Returns:
            {
                'batch_id': str,
                'total':    int,
                'success':  int,
                'failed':   int,   # DB-level failures (not parse errors)
                'warnings': int,   # rows with error_flag=1 (parse issues)
            }
        """
        batch_id = str(uuid.uuid4())
        success = failed = warnings = 0

        for row in normalized_rows:
            try:
                # ---- 1. UPSERT print_logs_raw ---------------------------
                raw_sql = """
                    INSERT INTO print_logs_raw (
                        batch_id, row_index,
                        student_email, student_name, operator_name, printer_name,
                        print_time_raw, material_used_raw,
                        started_at_raw, is_finished_raw, actual_finish_raw,
                        error_1_raw, error_2_raw, file_name_raw, raw_json
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        batch_id         = VALUES(batch_id),
                        student_email    = VALUES(student_email),
                        student_name     = VALUES(student_name),
                        operator_name    = VALUES(operator_name),
                        printer_name     = VALUES(printer_name),
                        print_time_raw   = VALUES(print_time_raw),
                        material_used_raw= VALUES(material_used_raw),
                        started_at_raw   = VALUES(started_at_raw),
                        is_finished_raw  = VALUES(is_finished_raw),
                        actual_finish_raw= VALUES(actual_finish_raw),
                        error_1_raw      = VALUES(error_1_raw),
                        error_2_raw      = VALUES(error_2_raw),
                        file_name_raw    = VALUES(file_name_raw),
                        raw_json         = VALUES(raw_json),
                        imported_at      = CURRENT_TIMESTAMP
                """
                raw_params = (
                    batch_id, row['row_index'],
                    row.get('student_email'),   row.get('student_name'),
                    row.get('operator_name'),   row.get('printer_name'),
                    row.get('print_time_raw'),  row.get('material_used_raw'),
                    row.get('started_at_raw'),  row.get('is_finished_raw'),
                    row.get('actual_finish_raw'),
                    row.get('error_1_raw'),     row.get('error_2_raw'),
                    row.get('file_name_raw'),   row.get('raw_json'),
                )
                db.execute_query(raw_sql, raw_params)

                # ---- 2. Get the raw_log_id for the FK ------------------
                raw_log = db.fetch_one(
                    "SELECT id FROM print_logs_raw WHERE row_index = %s",
                    (row['row_index'],)
                )
                raw_log_id = raw_log['id'] if raw_log else None

                # ---- 3. UPSERT print_logs_normalized -------------------
                # Convert datetimes to strings for MySQL
                def _dt(d: Optional[datetime]) -> Optional[str]:
                    return d.strftime('%Y-%m-%d %H:%M:%S') if d else None

                norm_sql = """
                    INSERT INTO print_logs_normalized (
                        raw_log_id, batch_id, row_index,
                        student_email, student_name, operator_name, printer_name,
                        print_time_raw, print_time_minutes, slicer_time_minutes,
                        started_at, finished_at,
                        material_used_g, slicer_material_g,
                        is_finished, error_1, error_2, file_name,
                        error_flag, error_reason
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        raw_log_id          = VALUES(raw_log_id),
                        batch_id            = VALUES(batch_id),
                        student_email       = VALUES(student_email),
                        student_name        = VALUES(student_name),
                        operator_name       = VALUES(operator_name),
                        printer_name        = VALUES(printer_name),
                        print_time_raw      = VALUES(print_time_raw),
                        print_time_minutes  = VALUES(print_time_minutes),
                        slicer_time_minutes = VALUES(slicer_time_minutes),
                        started_at          = VALUES(started_at),
                        finished_at         = VALUES(finished_at),
                        material_used_g     = VALUES(material_used_g),
                        slicer_material_g   = VALUES(slicer_material_g),
                        is_finished         = VALUES(is_finished),
                        error_1             = VALUES(error_1),
                        error_2             = VALUES(error_2),
                        file_name           = VALUES(file_name),
                        error_flag          = VALUES(error_flag),
                        error_reason        = VALUES(error_reason),
                        updated_at          = CURRENT_TIMESTAMP
                """
                norm_params = (
                    raw_log_id, batch_id, row['row_index'],
                    row.get('student_email_norm'), row.get('student_name'),
                    row.get('operator_name'),       row.get('printer_name'),
                    row.get('print_time_raw'),      row.get('print_time_minutes'),
                    row.get('slicer_time_minutes'),
                    _dt(row.get('started_at')),     _dt(row.get('finished_at')),
                    row.get('material_used_g'),     row.get('slicer_material_g'),
                    row.get('is_finished'),
                    row.get('error_1'),             row.get('error_2'),
                    row.get('file_name'),
                    row.get('error_flag', 0),       row.get('error_reason'),
                )
                db.execute_query(norm_sql, norm_params)

                success += 1
                if row.get('error_flag'):
                    warnings += 1

            except Exception as e:
                failed += 1
                logger.error(
                    "import_from_sheet: failed on row_index=%s: %s",
                    row.get('row_index'), e
                )

        logger.info(
            "import_from_sheet complete — batch=%s total=%d success=%d failed=%d warnings=%d",
            batch_id, len(normalized_rows), success, failed, warnings
        )
        return {
            'batch_id': batch_id,
            'total':    len(normalized_rows),
            'success':  success,
            'failed':   failed,
            'warnings': warnings,
        }

    # ------------------------------------------------------------------
    # get_slicer_map
    # ------------------------------------------------------------------

    def get_slicer_map(self) -> dict[str, float]:
        """
        Build a {student_email: slicer_time_minutes} dict from print_requests.
        When multiple requests exist for the same email, the most recent non-null
        slicer_time_minutes wins.
        """
        rows = db.fetch_all(
            """
            SELECT student_email, slicer_time_minutes, slicer_material_g
            FROM print_requests
            WHERE slicer_time_minutes IS NOT NULL
            ORDER BY created_at DESC
            """
        )
        slicer_map: dict[str, float] = {}
        for r in (rows or []):
            email = (r.get('student_email') or '').lower()
            if email and email not in slicer_map:
                slicer_map[email] = float(r['slicer_time_minutes'])
        return slicer_map

    # ------------------------------------------------------------------
    # get_weekly_report
    # ------------------------------------------------------------------

    def get_weekly_report(self, week: Optional[str] = None,
                          from_date: Optional[str] = None,
                          to_date: Optional[str] = None) -> dict:
        """
        Return aggregated KPI data for a date range.

        Priority:
          1. Custom range: from_date + to_date ('YYYY-MM-DD')
          2. ISO week:     week ('YYYY-WW')
          3. Default:      last week

        Returns a dict with 4 KPI groups:
            volume    — total jobs, finished/unfinished counts
            material  — total grams used, average per job
            capacity  — total print hours, per-printer breakdown
            staffing  — jobs per operator, hours per operator
        """
        if from_date and to_date:
            monday, sunday = _custom_bounds(from_date, to_date)
        else:
            if not week:
                week = _last_week_str()
            monday, sunday = _week_bounds(week)
        params = (monday, sunday)

        # ---- Volume KPIs ------------------------------------------------
        volume_row = db.fetch_one(
            """
            SELECT
                COUNT(*)                                    AS total_jobs,
                SUM(CASE WHEN is_finished = 1 THEN 1 ELSE 0 END) AS finished_jobs,
                SUM(CASE WHEN is_finished = 0 THEN 1 ELSE 0 END) AS unfinished_jobs,
                SUM(CASE WHEN is_finished IS NULL THEN 1 ELSE 0 END) AS unknown_status_jobs
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            """,
            params
        ) or {}

        # ---- Material KPIs ----------------------------------------------
        material_row = db.fetch_one(
            """
            SELECT
                ROUND(SUM(material_used_g), 2)             AS total_material_g,
                ROUND(AVG(material_used_g), 2)             AS avg_material_per_job_g,
                ROUND(SUM(slicer_material_g), 2)           AS total_slicer_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND material_used_g IS NOT NULL
            """,
            params
        ) or {}

        # ---- Capacity KPIs (per printer) --------------------------------
        printer_rows = db.fetch_all(
            """
            SELECT
                COALESCE(printer_name, '(unknown)')         AS printer_name,
                COUNT(*)                                    AS jobs,
                ROUND(SUM(print_time_minutes) / 60.0, 2)   AS print_hours,
                ROUND(AVG(print_time_minutes), 2)           AS avg_print_minutes,
                ROUND(SUM(material_used_g), 2)              AS total_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            GROUP BY printer_name
            ORDER BY jobs DESC
            """,
            params
        ) or []

        total_print_hours = db.fetch_one(
            """
            SELECT ROUND(SUM(print_time_minutes) / 60.0, 2) AS total_print_hours
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            """,
            params
        ) or {}

        # ---- Staffing KPIs (per operator) -------------------------------
        operator_rows = db.fetch_all(
            """
            SELECT
                COALESCE(operator_name, '(unknown)')        AS operator_name,
                COUNT(*)                                    AS jobs_handled,
                ROUND(SUM(print_time_minutes) / 60.0, 2)   AS print_hours_handled,
                ROUND(SUM(material_used_g), 2)              AS material_used_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            GROUP BY operator_name
            ORDER BY jobs_handled DESC
            """,
            params
        ) or []

        return {
            'week':     week,
            'period': {
                'from': monday.strftime('%Y-%m-%d'),
                'to':   sunday.strftime('%Y-%m-%d'),
            },
            'volume': {
                'total_jobs':          int(volume_row.get('total_jobs') or 0),
                'finished_jobs':       int(volume_row.get('finished_jobs') or 0),
                'unfinished_jobs':     int(volume_row.get('unfinished_jobs') or 0),
                'unknown_status_jobs': int(volume_row.get('unknown_status_jobs') or 0),
            },
            'material': {
                'total_material_g':         _f(material_row.get('total_material_g')),
                'avg_material_per_job_g':   _f(material_row.get('avg_material_per_job_g')),
                'total_slicer_material_g':  _f(material_row.get('total_slicer_material_g')),
            },
            'capacity': {
                'total_print_hours': _f(total_print_hours.get('total_print_hours')),
                'by_printer':        [
                    {k: (_f(v) if k != 'printer_name' and k != 'jobs' else v)
                     for k, v in r.items()}
                    for r in printer_rows
                ],
            },
            'staffing': {
                'by_operator': [
                    {k: (_f(v) if k != 'operator_name' and k != 'jobs_handled' else v)
                     for k, v in r.items()}
                    for r in operator_rows
                ],
            },
        }

    # ------------------------------------------------------------------
    # get_monthly_report
    # ------------------------------------------------------------------

    def get_monthly_report(self, month: Optional[str] = None) -> dict:
        """
        Return monthly aggregated stats for a given month (YYYY-MM).
        Includes: KPI totals, week-by-week breakdown, by_printer, by_operator.
        Defaults to last month if omitted.
        """
        if not month:
            now = datetime.utcnow()
            first = now.replace(day=1)
            last_month = first - timedelta(days=1)
            month = last_month.strftime('%Y-%m')

        try:
            year, mon = month.split('-')
            year, mon = int(year), int(mon)
        except Exception:
            raise ValueError(f"Invalid month format '{month}'. Expected 'YYYY-MM', e.g. '2026-03'.")

        from calendar import monthrange
        first_day = datetime(year, mon, 1, 0, 0, 0)
        last_day  = datetime(year, mon, monthrange(year, mon)[1], 23, 59, 59)
        params = (first_day, last_day)

        # ---- Overall totals ----
        totals = db.fetch_one(
            """
            SELECT
                COUNT(*)                                                           AS total_jobs,
                SUM(CASE WHEN is_finished=1 THEN 1 ELSE 0 END)                    AS finished_jobs,
                SUM(CASE WHEN is_finished=0 THEN 1 ELSE 0 END)                    AS unfinished_jobs,
                ROUND(SUM(print_time_minutes) / 60.0, 2)                          AS total_print_hours,
                ROUND(SUM(material_used_g), 2)                                    AS total_material_g,
                ROUND(AVG(material_used_g), 2)                                    AS avg_material_g,
                SUM(CASE WHEN (error_1='TRUE' OR error_1='1')
                           OR (error_2='TRUE' OR error_2='1') THEN 1 ELSE 0 END)  AS total_errors
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            """,
            params
        ) or {}

        # ---- Week-by-week breakdown ----
        # Get distinct ISO weeks that fall in this month
        week_rows = db.fetch_all(
            """
            SELECT
                YEAR(started_at)                                                         AS iso_year,
                WEEK(started_at, 3)                                                      AS iso_week,
                COUNT(*)                                                                 AS total_jobs,
                SUM(CASE WHEN is_finished=1 THEN 1 ELSE 0 END)                          AS finished_jobs,
                ROUND(SUM(print_time_minutes) / 60.0, 2)                                AS print_hours,
                ROUND(SUM(material_used_g), 2)                                          AS total_material_g,
                SUM(CASE WHEN (error_1='TRUE' OR error_1='1')
                           OR (error_2='TRUE' OR error_2='1') THEN 1 ELSE 0 END)        AS errors
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            GROUP BY iso_year, iso_week
            ORDER BY iso_year, iso_week
            """,
            params
        ) or []

        by_week = []
        for r in week_rows:
            iso_year = int(r['iso_year'])
            iso_week = int(r['iso_week'])
            week_str = f"{iso_year}-{iso_week:02d}"
            # Compute Mon-Sun bounds for display label
            monday = datetime.strptime(f'{iso_year}-W{iso_week:02d}-1', '%G-W%V-%u')
            sunday = monday + timedelta(days=6)
            by_week.append({
                'week':        week_str,
                'label':       f"W{iso_week:02d}  ({monday.strftime('%b %d')} – {sunday.strftime('%b %d')})",
                'total_jobs':  int(r['total_jobs'] or 0),
                'finished_jobs': int(r['finished_jobs'] or 0),
                'print_hours': _f(r['print_hours']),
                'total_material_g': _f(r['total_material_g']),
                'errors':      int(r['errors'] or 0),
            })

        # ---- By printer ----
        by_printer = db.fetch_all(
            """
            SELECT
                COALESCE(printer_name, '(unknown)')          AS printer_name,
                COUNT(*)                                     AS jobs,
                ROUND(SUM(print_time_minutes) / 60.0, 2)    AS print_hours,
                ROUND(SUM(material_used_g), 2)               AS total_material_g,
                ROUND(AVG(material_used_g), 2)               AS avg_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND material_used_g IS NOT NULL
            GROUP BY printer_name
            ORDER BY jobs DESC
            """,
            params
        ) or []

        # ---- By operator ----
        by_operator = db.fetch_all(
            """
            SELECT
                COALESCE(operator_name, '(unknown)')         AS operator_name,
                COUNT(*)                                     AS jobs,
                ROUND(SUM(print_time_minutes) / 60.0, 2)    AS print_hours,
                ROUND(SUM(material_used_g), 2)               AS total_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            GROUP BY operator_name
            ORDER BY jobs DESC
            """,
            params
        ) or []

        return {
            'month':  month,
            'period': {
                'from': first_day.strftime('%Y-%m-%d'),
                'to':   last_day.strftime('%Y-%m-%d'),
            },
            'totals': {
                'total_jobs':       int(totals.get('total_jobs') or 0),
                'finished_jobs':    int(totals.get('finished_jobs') or 0),
                'unfinished_jobs':  int(totals.get('unfinished_jobs') or 0),
                'total_print_hours': _f(totals.get('total_print_hours')),
                'total_material_g': _f(totals.get('total_material_g')),
                'avg_material_g':   _f(totals.get('avg_material_g')),
                'total_errors':     int(totals.get('total_errors') or 0),
            },
            'by_week':     by_week,
            'by_printer':  [dict(r) for r in by_printer],
            'by_operator': [dict(r) for r in by_operator],
        }

    # ------------------------------------------------------------------
    # get_raw_logs
    # ------------------------------------------------------------------

    def get_raw_logs(self, week: Optional[str] = None) -> list[dict]:
        """
        Return raw log rows for the given ISO week, for admin inspection.
        Rows with error_flag=1 are included and should be highlighted in UI.
        Defaults to last week.
        """
        if not week:
            week = _last_week_str()

        monday, sunday = _week_bounds(week)

        rows = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.batch_id,
                n.student_email, n.student_name,
                n.operator_name, n.printer_name,
                n.print_time_raw, n.print_time_minutes, n.slicer_time_minutes,
                n.started_at, n.finished_at,
                n.material_used_g, n.slicer_material_g,
                n.is_finished, n.error_1, n.error_2, n.file_name,
                n.error_flag, n.error_reason,
                n.imported_at, n.updated_at,
                r.raw_json
            FROM print_logs_normalized n
            LEFT JOIN print_logs_raw r ON r.id = n.raw_log_id
            WHERE n.started_at BETWEEN %s AND %s
            ORDER BY n.row_index ASC
            """,
            (monday, sunday)
        ) or []

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # get_printer_detail
    # ------------------------------------------------------------------

    def get_printer_detail(self, printer_name: str, week: Optional[str] = None) -> dict:
        """Return job list + summary stats for one printer in a given week."""
        if not week:
            week = _last_week_str()
        monday, sunday = _week_bounds(week)

        summary = db.fetch_one(
            """
            SELECT
                COUNT(*)                                        AS total_jobs,
                SUM(CASE WHEN is_finished=1 THEN 1 ELSE 0 END) AS finished_jobs,
                ROUND(SUM(print_time_minutes)/60.0, 2)         AS total_print_hours,
                ROUND(SUM(material_used_g), 2)                 AS total_material_g
            FROM print_logs_normalized
            WHERE printer_name = %s AND started_at BETWEEN %s AND %s
            """,
            (printer_name, monday, sunday)
        ) or {}

        jobs = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.student_name, n.student_email,
                n.operator_name, n.print_time_minutes, n.material_used_g,
                n.started_at, n.finished_at, n.is_finished,
                n.error_1, n.error_2, n.file_name,
                n.error_flag, n.error_reason,
                pr.request_id AS request_id
            FROM print_logs_normalized n
            LEFT JOIN print_requests pr
                ON LOWER(pr.student_email) = LOWER(n.student_email)
                AND DATE(pr.created_at) = DATE(n.started_at)
            WHERE n.printer_name = %s AND n.started_at BETWEEN %s AND %s
            ORDER BY n.started_at ASC
            """,
            (printer_name, monday, sunday)
        ) or []

        return {
            'printer_name': printer_name,
            'week': week,
            'period': {'from': monday.strftime('%Y-%m-%d'), 'to': sunday.strftime('%Y-%m-%d')},
            'summary': {
                'total_jobs':       int(summary.get('total_jobs') or 0),
                'finished_jobs':    int(summary.get('finished_jobs') or 0),
                'total_print_hours': _f(summary.get('total_print_hours')),
                'total_material_g': _f(summary.get('total_material_g')),
            },
            'jobs': [dict(r) for r in jobs],
        }

    # ------------------------------------------------------------------
    # get_operator_detail
    # ------------------------------------------------------------------

    def get_operator_detail(self, operator_name: str, week: Optional[str] = None) -> dict:
        """Return job list + summary stats for one operator in a given week."""
        if not week:
            week = _last_week_str()
        monday, sunday = _week_bounds(week)

        summary = db.fetch_one(
            """
            SELECT
                COUNT(*)                                        AS total_jobs,
                SUM(CASE WHEN is_finished=1 THEN 1 ELSE 0 END) AS finished_jobs,
                ROUND(SUM(print_time_minutes)/60.0, 2)         AS total_print_hours,
                ROUND(SUM(material_used_g), 2)                 AS total_material_g
            FROM print_logs_normalized
            WHERE operator_name = %s AND started_at BETWEEN %s AND %s
            """,
            (operator_name, monday, sunday)
        ) or {}

        jobs = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.student_name, n.student_email,
                n.printer_name, n.print_time_minutes, n.material_used_g,
                n.started_at, n.finished_at, n.is_finished,
                n.error_1, n.error_2, n.file_name,
                n.error_flag, n.error_reason,
                pr.request_id AS request_id
            FROM print_logs_normalized n
            LEFT JOIN print_requests pr
                ON LOWER(pr.student_email) = LOWER(n.student_email)
                AND DATE(pr.created_at) = DATE(n.started_at)
            WHERE n.operator_name = %s AND n.started_at BETWEEN %s AND %s
            ORDER BY n.started_at ASC
            """,
            (operator_name, monday, sunday)
        ) or []

        return {
            'operator_name': operator_name,
            'week': week,
            'period': {'from': monday.strftime('%Y-%m-%d'), 'to': sunday.strftime('%Y-%m-%d')},
            'summary': {
                'total_jobs':        int(summary.get('total_jobs') or 0),
                'finished_jobs':     int(summary.get('finished_jobs') or 0),
                'total_print_hours': _f(summary.get('total_print_hours')),
                'total_material_g':  _f(summary.get('total_material_g')),
            },
            'jobs': [dict(r) for r in jobs],
        }

    # ------------------------------------------------------------------
    # get_materials_report
    # ------------------------------------------------------------------

    def get_materials_report(self, week: Optional[str] = None) -> dict:
        """Return material usage breakdown by printer and per-job list."""
        if not week:
            week = _last_week_str()
        monday, sunday = _week_bounds(week)
        params = (monday, sunday)

        totals = db.fetch_one(
            """
            SELECT
                COUNT(*)                        AS total_jobs,
                ROUND(SUM(material_used_g), 2)  AS total_material_g,
                ROUND(AVG(material_used_g), 2)  AS avg_material_g,
                ROUND(MAX(material_used_g), 2)  AS max_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND material_used_g IS NOT NULL AND material_used_g > 0
            """,
            params
        ) or {}

        by_printer = db.fetch_all(
            """
            SELECT
                COALESCE(printer_name, '(unknown)')    AS printer_name,
                COUNT(*)                               AS jobs,
                ROUND(SUM(material_used_g), 2)         AS total_material_g,
                ROUND(AVG(material_used_g), 2)         AS avg_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND material_used_g IS NOT NULL AND material_used_g > 0
            GROUP BY printer_name
            ORDER BY total_material_g DESC
            """,
            params
        ) or []

        by_operator = db.fetch_all(
            """
            SELECT
                COALESCE(operator_name, '(unknown)')   AS operator_name,
                COUNT(*)                               AS jobs,
                ROUND(SUM(material_used_g), 2)         AS total_material_g,
                ROUND(AVG(material_used_g), 2)         AS avg_material_g
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND material_used_g IS NOT NULL AND material_used_g > 0
            GROUP BY operator_name
            ORDER BY total_material_g DESC
            """,
            params
        ) or []

        jobs = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.student_name, n.printer_name,
                n.operator_name, n.material_used_g, n.print_time_minutes,
                n.started_at, n.is_finished, n.file_name,
                pr.request_id AS request_id
            FROM print_logs_normalized n
            LEFT JOIN print_requests pr
                ON LOWER(pr.student_email) = LOWER(n.student_email)
                AND DATE(pr.created_at) = DATE(n.started_at)
            WHERE n.started_at BETWEEN %s AND %s
              AND n.material_used_g IS NOT NULL AND n.material_used_g > 0
            ORDER BY n.material_used_g DESC
            """,
            params
        ) or []

        return {
            'week': week,
            'period': {'from': monday.strftime('%Y-%m-%d'), 'to': sunday.strftime('%Y-%m-%d')},
            'totals': {
                'total_jobs':      int(totals.get('total_jobs') or 0),
                'total_material_g': _f(totals.get('total_material_g')),
                'avg_material_g':  _f(totals.get('avg_material_g')),
                'max_material_g':  _f(totals.get('max_material_g')),
            },
            'by_printer':  [dict(r) for r in by_printer],
            'by_operator': [dict(r) for r in by_operator],
            'jobs': [dict(r) for r in jobs],
        }

    # ------------------------------------------------------------------
    # get_errors_report
    # ------------------------------------------------------------------

    def get_errors_report(self, week: Optional[str] = None) -> dict:
        """Return error summary across all printers + per-job error list."""
        if not week:
            week = _last_week_str()
        monday, sunday = _week_bounds(week)
        params = (monday, sunday)

        totals = db.fetch_one(
            """
            SELECT
                COUNT(*)                                             AS total_jobs,
                SUM(CASE WHEN error_1='TRUE' OR error_1='1' THEN 1 ELSE 0 END) AS error_1_count,
                SUM(CASE WHEN error_2='TRUE' OR error_2='1' THEN 1 ELSE 0 END) AS error_2_count,
                SUM(CASE WHEN (error_1='TRUE' OR error_1='1')
                           OR (error_2='TRUE' OR error_2='1') THEN 1 ELSE 0 END) AS jobs_with_error
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            """,
            params
        ) or {}

        by_printer = db.fetch_all(
            """
            SELECT
                COALESCE(printer_name, '(unknown)')  AS printer_name,
                COUNT(*)                             AS total_jobs,
                SUM(CASE WHEN error_1='TRUE' OR error_1='1'
                           OR error_2='TRUE' OR error_2='1' THEN 1 ELSE 0 END) AS error_jobs
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
            GROUP BY printer_name
            ORDER BY error_jobs DESC, total_jobs DESC
            """,
            params
        ) or []

        error_jobs = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.student_name, n.printer_name,
                n.operator_name, n.started_at, n.print_time_minutes,
                n.error_1, n.error_2, n.file_name, n.is_finished
            FROM print_logs_normalized n
            WHERE n.started_at BETWEEN %s AND %s
              AND (n.error_1='TRUE' OR n.error_1='1'
                OR n.error_2='TRUE' OR n.error_2='1')
            ORDER BY n.started_at ASC
            """,
            params
        ) or []

        # Incomplete jobs: started but NOT finished and no error flag
        # These may be fixable/reprint candidates — tracked separately
        incomplete_jobs = db.fetch_all(
            """
            SELECT
                n.id, n.row_index, n.student_name, n.printer_name,
                n.operator_name, n.started_at, n.print_time_minutes,
                n.material_used_g, n.file_name,
                n.error_1, n.error_2
            FROM print_logs_normalized n
            WHERE n.started_at BETWEEN %s AND %s
              AND n.is_finished = 0
              AND NOT (n.error_1='TRUE' OR n.error_1='1'
                    OR n.error_2='TRUE' OR n.error_2='1')
            ORDER BY n.started_at ASC
            """,
            params
        ) or []

        # Add incomplete count to totals
        totals_row = db.fetch_one(
            """
            SELECT COUNT(*) AS incomplete_count
            FROM print_logs_normalized
            WHERE started_at BETWEEN %s AND %s
              AND is_finished = 0
              AND NOT (error_1='TRUE' OR error_1='1'
                    OR error_2='TRUE' OR error_2='1')
            """,
            params
        ) or {}

        return {
            'week': week,
            'period': {'from': monday.strftime('%Y-%m-%d'), 'to': sunday.strftime('%Y-%m-%d')},
            'totals': {
                'total_jobs':       int(totals.get('total_jobs') or 0),
                'jobs_with_error':  int(totals.get('jobs_with_error') or 0),
                'error_1_count':    int(totals.get('error_1_count') or 0),
                'error_2_count':    int(totals.get('error_2_count') or 0),
                'incomplete_count': int(totals_row.get('incomplete_count') or 0),
            },
            'by_printer':       [dict(r) for r in by_printer],
            'error_jobs':       [dict(r) for r in error_jobs],
            'incomplete_jobs':  [dict(r) for r in incomplete_jobs],
        }


# ---------------------------------------------------------------------------
# module-level helper
# ---------------------------------------------------------------------------

def _f(v) -> Optional[float]:
    """Safely cast DB decimal/None to float."""
    return float(v) if v is not None else None
