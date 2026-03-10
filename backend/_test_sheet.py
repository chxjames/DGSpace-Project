import sys
sys.path.insert(0, '.')
from sheet_service import SheetService

svc = SheetService()
rows = svc.fetch_sheet_rows()
print(f'Total rows: {len(rows)}')
print('Keys:', list(rows[0].keys()) if rows else 'empty')
print('\\nFirst 2 rows:')
for row in rows[:2]:
    for k, v in row.items():
        if v: print(f'  {k!r}: {v!r}')
    print('  ---')
