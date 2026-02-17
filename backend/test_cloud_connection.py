"""Test connection to Aiven cloud MySQL database"""
import mysql.connector
from mysql.connector import Error
from config import Config

print("🔧 Testing Aiven Cloud MySQL Connection...")
print(f"Host: {Config.DB_HOST}")
print(f"Port: {Config.DB_PORT}")
print(f"User: {Config.DB_USER}")
print(f"Database: {Config.DB_NAME}")
print()

try:
    connection = mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        ssl_disabled=False
    )
    
    if connection.is_connected():
        db_info = connection.get_server_info()
        print(f"✅ Successfully connected to MySQL Server version {db_info}")
        
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE();")
        record = cursor.fetchone()
        print(f"✅ Connected to database: {record[0]}")
        
        # Show existing tables
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        if tables:
            print(f"\n📊 Existing tables in {Config.DB_NAME}:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print(f"\n📊 No tables found in {Config.DB_NAME} (fresh database)")
        
        cursor.close()
        connection.close()
        print("\n✅ Connection test successful!")
        
except Error as e:
    print(f"❌ Error connecting to MySQL: {e}")
    print("\nTroubleshooting:")
    print("1. Check that credentials in .env match your Aiven dashboard")
    print("2. Verify SSL is enabled (ssl_disabled=False)")
    print("3. Check firewall/IP whitelist in Aiven console")
