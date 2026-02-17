"""Import SQL dump file to Aiven cloud database"""
import mysql.connector
from mysql.connector import Error
from config import Config

def import_sql_dump(sql_file_path):
    """Import SQL dump file to cloud database"""
    try:
        print("🔗 Connecting to Aiven cloud database...")
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            ssl_disabled=False
        )
        
        if connection.is_connected():
            print("✅ Connected successfully")
            cursor = connection.cursor()
            
            # Read SQL file (try different encodings)
            print(f"📖 Reading SQL file: {sql_file_path}")
            try:
                with open(sql_file_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
            except UnicodeDecodeError:
                with open(sql_file_path, 'r', encoding='latin-1') as f:
                    sql_content = f.read()
            
            # Split into individual statements
            statements = sql_content.split(';')
            
            print(f"⚙️  Executing {len(statements)} SQL statements...")
            success_count = 0
            
            for i, statement in enumerate(statements, 1):
                statement = statement.strip()
                if statement:
                    try:
                        cursor.execute(statement)
                        success_count += 1
                        if i % 10 == 0:
                            print(f"  Progress: {i}/{len(statements)} statements")
                    except Error as e:
                        # Skip errors for DROP/CREATE DATABASE statements
                        if 'CREATE DATABASE' not in statement and 'USE' not in statement:
                            print(f"  ⚠️  Warning at statement {i}: {e}")
            
            connection.commit()
            print(f"\n✅ Successfully executed {success_count} statements")
            
            # Show tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\n📊 Database now has {len(tables)} tables:")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                count = cursor.fetchone()[0]
                print(f"  - {table[0]}: {count} rows")
            
            cursor.close()
            connection.close()
            print("\n🎉 Import complete!")
            
    except Error as e:
        print(f"❌ Error: {e}")
    except FileNotFoundError:
        print(f"❌ File not found: {sql_file_path}")

if __name__ == "__main__":
    import os
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'dgspace_backup.sql')
    print("=" * 60)
    print("🚀 Import SQL Dump to Aiven Cloud")
    print("=" * 60)
    print()
    import_sql_dump(sql_file)
