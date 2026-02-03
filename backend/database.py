import mysql.connector
from mysql.connector import Error
from config import Config

class Database:
    def __init__(self):
        self.connection = None
        
    def connect(self):
        """Create database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME
            )
            if self.connection.is_connected():
                print(f"✅ Connected to MySQL database: {Config.DB_NAME}")
                return self.connection
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return None
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("✅ Database connection closed")
    
    def execute_query(self, query, params=None):
        """Execute a query that modifies data (INSERT, UPDATE, DELETE)"""
        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"❌ Error executing query: {e}")
            self.connection.rollback()
            return None
        finally:
            cursor.close()
    
    def fetch_one(self, query, params=None):
        """Fetch a single row"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchone()
            return result
        except Error as e:
            print(f"❌ Error fetching data: {e}")
            return None
        finally:
            cursor.close()
    
    def fetch_all(self, query, params=None):
        """Fetch all rows"""
        cursor = self.connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return results
        except Error as e:
            print(f"❌ Error fetching data: {e}")
            return None
        finally:
            cursor.close()

# Create a global database instance
db = Database()
