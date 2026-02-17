"""Sync local MySQL database to Aiven cloud"""
import mysql.connector
from mysql.connector import Error
from config import Config
import getpass

def sync_database():
    """Sync all data from local MySQL to Aiven cloud"""
    
    print("=" * 70)
    print("🔄 DGSpace Database Sync: Local → Cloud")
    print("=" * 70)
    print()
    
    # Get local credentials
    print("📋 Local MySQL Configuration:")
    local_host = input("  Host (default: localhost): ").strip() or "localhost"
    local_port = input("  Port (default: 3306): ").strip() or "3306"
    local_user = input("  Username (default: root): ").strip() or "root"
    local_password = getpass.getpass("  Password: ")
    local_db = input("  Database name (default: DGSpace): ").strip() or "DGSpace"
    
    print()
    print("☁️  Cloud MySQL Configuration:")
    print(f"  Host: {Config.DB_HOST}")
    print(f"  Port: {Config.DB_PORT}")
    print(f"  User: {Config.DB_USER}")
    print(f"  Database: {Config.DB_NAME}")
    print()
    
    source_conn = None
    dest_conn = None
    
    try:
        # Connect to local database
        print("🔗 Connecting to LOCAL database...")
        source_conn = mysql.connector.connect(
            host=local_host,
            port=int(local_port),
            user=local_user,
            password=local_password,
            database=local_db
        )
        print("✅ Connected to local database")
        
        # Connect to cloud database
        print("🔗 Connecting to CLOUD database...")
        dest_conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            ssl_disabled=False
        )
        print("✅ Connected to cloud database")
        print()
        
        source_cursor = source_conn.cursor()
        dest_cursor = dest_conn.cursor()
        
        # Get all tables
        source_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in source_cursor.fetchall()]
        
        print(f"📊 Found {len(tables)} tables to sync: {', '.join(tables)}")
        print()
        
        # Sync each table
        for table in tables:
            print(f"📦 Syncing table: {table}")
            
            # Get table structure
            source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_statement = source_cursor.fetchone()[1]
            
            # Drop and recreate table in cloud
            try:
                dest_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                dest_cursor.execute(create_statement)
                print(f"  ✅ Table structure synced")
            except Error as e:
                print(f"  ❌ Error creating table: {e}")
                continue
            
            # Get all data
            source_cursor.execute(f"SELECT * FROM `{table}`")
            rows = source_cursor.fetchall()
            
            if rows:
                # Get column info
                column_count = len(source_cursor.description)
                placeholders = ', '.join(['%s'] * column_count)
                insert_query = f"INSERT INTO `{table}` VALUES ({placeholders})"
                
                # Insert data
                try:
                    dest_cursor.executemany(insert_query, rows)
                    dest_conn.commit()
                    print(f"  ✅ Synced {len(rows)} rows")
                except Error as e:
                    print(f"  ❌ Error inserting data: {e}")
                    dest_conn.rollback()
            else:
                print(f"  ℹ️  Table is empty (no data to sync)")
            
            print()
        
        # Show final stats
        print("=" * 70)
        print("🎉 Sync Complete!")
        print("=" * 70)
        print()
        print("☁️  Cloud database now contains:")
        
        for table in tables:
            # Get counts from both databases
            source_cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            local_count = source_cursor.fetchone()[0]
            
            dest_cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            cloud_count = dest_cursor.fetchone()[0]
            
            status = "✅" if local_count == cloud_count else "⚠️"
            print(f"  {status} {table}: {cloud_count} rows (local: {local_count})")
        
        print()
        print("🌐 Your partner can now access the cloud database!")
        print(f"   Host: {Config.DB_HOST}")
        print(f"   Port: {Config.DB_PORT}")
        print(f"   Database: {Config.DB_NAME}")
        
    except Error as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure local MySQL is running")
        print("2. Check username and password")
        print("3. Verify database name exists")
        
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
    sync_database()
