"""Migrate database from local MySQL to Aiven cloud"""
import mysql.connector
from mysql.connector import Error
from config import Config

# Source (local database)
SOURCE_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change if needed
    'password': input("Enter LOCAL MySQL root password: "),
    'database': 'DGSpace'
}

# Destination (Aiven cloud)
DEST_CONFIG = {
    'host': Config.DB_HOST,
    'port': Config.DB_PORT,
    'user': Config.DB_USER,
    'password': Config.DB_PASSWORD,
    'database': Config.DB_NAME,
    'ssl_disabled': False
}

def migrate_database():
    """Migrate database schema and data from local to cloud"""
    source_conn = None
    dest_conn = None
    
    try:
        # Connect to source
        print("🔗 Connecting to LOCAL database...")
        source_conn = mysql.connector.connect(**SOURCE_CONFIG)
        source_cursor = source_conn.cursor()
        
        # Connect to destination
        print("🔗 Connecting to CLOUD database...")
        dest_conn = mysql.connector.connect(**DEST_CONFIG)
        dest_cursor = dest_conn.cursor()
        
        # Get all tables
        source_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in source_cursor.fetchall()]
        
        print(f"\n📊 Found {len(tables)} tables to migrate: {tables}\n")
        
        # Migrate each table
        for table in tables:
            print(f"📦 Migrating table: {table}")
            
            # Get CREATE TABLE statement
            source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_statement = source_cursor.fetchone()[1]
            
            # Create table in destination
            try:
                dest_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                dest_cursor.execute(create_statement)
                print(f"  ✅ Created table structure")
            except Error as e:
                print(f"  ❌ Error creating table: {e}")
                continue
            
            # Copy data
            source_cursor.execute(f"SELECT * FROM `{table}`")
            rows = source_cursor.fetchall()
            
            if rows:
                # Get column count
                column_count = len(source_cursor.description)
                placeholders = ', '.join(['%s'] * column_count)
                insert_query = f"INSERT INTO `{table}` VALUES ({placeholders})"
                
                dest_cursor.executemany(insert_query, rows)
                dest_conn.commit()
                print(f"  ✅ Copied {len(rows)} rows")
            else:
                print(f"  ℹ️  Table is empty")
        
        print(f"\n🎉 Migration complete!")
        print(f"✅ All {len(tables)} tables migrated successfully")
        
        # Show final stats
        dest_cursor.execute("SHOW TABLES")
        dest_tables = dest_cursor.fetchall()
        print(f"\n📊 Cloud database now has {len(dest_tables)} tables:")
        for table in dest_tables:
            dest_cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
            count = dest_cursor.fetchone()[0]
            print(f"  - {table[0]}: {count} rows")
        
    except Error as e:
        print(f"\n❌ Migration error: {e}")
    
    finally:
        if source_conn and source_conn.is_connected():
            source_cursor.close()
            source_conn.close()
            print("\n🔒 Closed local database connection")
        
        if dest_conn and dest_conn.is_connected():
            dest_cursor.close()
            dest_conn.close()
            print("🔒 Closed cloud database connection")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 DGSpace Database Migration Tool")
    print("   Local MySQL → Aiven Cloud MySQL")
    print("=" * 60)
    print()
    migrate_database()
