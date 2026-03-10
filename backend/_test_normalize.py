import sys
sys.path.insert(0, '.')
from sheet_service import parse_print_time, SheetService

svc = SheetService()
rows = svc.fetch_sheet_rows()
print(f"Total rows: {len(rows)}")

errors = []
for i, row in enumerate(rows):
    nr = svc.normalize_row(row, i + 2, {})
    if nr['error_reason']:
        errors.append((i + 2, nr['error_reason']))

print(f"OK: {len(rows)-len(errors)}  |  error_reason: {len(errors)}\n")
print("All error rows:")
for row_num, reason in errors:
    print(f"  Row {row_num}: {reason}")

print("\n=== Unique failed print_time values ===")
failed_times = set()
for row in rows:
    raw = row.get('Print time (HH:MM)', '')
    if raw and parse_print_time(raw) is None:
        failed_times.add(repr(raw))
for v in sorted(failed_times):
    print(f"  {v}")
