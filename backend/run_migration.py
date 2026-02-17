"""
Run the database migration to create print_requests tables
"""
import mysql.connector
from config import Config


def run_migration():
    """Run the migration SQL script"""
    try:
        # Connect to cloud database
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            ssl_disabled=False
        )
        
        cursor = connection.cursor()
        
        # Read the migration file
        with open('../database/migration_001_print_requests.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Remove the USE DGSpace line since we're already connected to the right database
        sql_script = sql_script.replace('USE DGSpace;', '')
        
        # Split by semicolon and execute each statement
        statements = sql_script.split(';')
        
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--') and len(statement) > 10:
                print(f"Executing: {statement[:80]}...")
                cursor.execute(statement)
        
        connection.commit()
        
        # Verify tables were created
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print("\n✅ Migration completed successfully!")
        print("\n📊 Current tables in database:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Check if print_requests table has correct structure
        cursor.execute("DESCRIBE print_requests")
        columns = cursor.fetchall()
        
        print("\n📋 print_requests table structure:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")
        
        cursor.close()
        connection.close()
        
        print("\n🎉 Database is ready for 3D print requests!")
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔧 Running database migration for print requests...")
    print(f"📍 Target database: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    print()
    run_migration()
