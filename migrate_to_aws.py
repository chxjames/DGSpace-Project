import pymysql

BACKUP_FILE = r'E:\DGSpace-Project-1\dgspace_local_backup_20260325_144643.sql'

conn = pymysql.connect(
    host='donald-garage.ctmea2im0zim.us-west-1.rds.amazonaws.com',
    user='admin',
    password='dongarage',
    database='DGSpace',
    charset='utf8mb4',
    autocommit=True
)
cur = conn.cursor()

# Disable FK checks to avoid table ordering issues
cur.execute("SET FOREIGN_KEY_CHECKS=0;")

# Drop all existing tables to start fresh
print("Dropping existing tables...")
cur.execute("SHOW TABLES;")
tables = [row[0] for row in cur.fetchall()]
for t in tables:
    cur.execute(f"DROP TABLE IF EXISTS `{t}`;")
    print(f"  Dropped: {t}")

with open(BACKUP_FILE, 'r', encoding='utf-16') as f:
    sql = f.read()

# Split statements by semicolon
statements = sql.split(';\n')
ok, fail = 0, 0
for stmt in statements:
    stmt = stmt.strip()
    if not stmt or stmt.startswith('--') or stmt.startswith('/*'):
        continue
    try:
        cur.execute(stmt)
        ok += 1
    except Exception as e:
        msg = str(e)
        if 'already exists' in msg or '1050' in msg:
            print(f'  [SKIP] {msg[:80]}')
        else:
            print(f'  [ERR]  {msg[:120]}')
        fail += 1

# Re-enable FK checks
cur.execute("SET FOREIGN_KEY_CHECKS=1;")

print(f'\nDone: {ok} statements OK, {fail} skipped/errors')
conn.close()
