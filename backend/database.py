import mysql.connector
from mysql.connector import Error, pooling
from config import Config

# ---------------------------------------------------------------------------
# Connection-pool based Database helper
#
# Each public method borrows a connection from the pool, uses it, and returns
# it immediately — so the pool is never exhausted and stale-connection errors
# are handled transparently with one automatic retry.
# ---------------------------------------------------------------------------

_POOL_SIZE = 5          # simultaneous connections kept open
_POOL_NAME = "dgspace_pool"

def _make_pool():
    return pooling.MySQLConnectionPool(
        pool_name=_POOL_NAME,
        pool_size=_POOL_SIZE,
        pool_reset_session=True,
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        ssl_disabled=True,
        auth_plugin='mysql_native_password',
        connection_timeout=10,
    )

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = _make_pool()
        print(f"[OK] MySQL connection pool '{_POOL_NAME}' created (size={_POOL_SIZE})")
    return _pool


class Database:
    """Thin wrapper around a MySQLConnectionPool.

    The legacy `db.connection` attribute and `db.connect()` / `db.disconnect()`
    are kept for backward-compat (some code checks `db.connection.is_connected()`).
    """

    def __init__(self):
        # Kept only for backward-compat checks; pool handles real connections.
        self.connection = None

    # ------------------------------------------------------------------
    # backward-compat: callers that do `if not db.connection or not db.connection.is_connected()`
    # just need this to stop raising; the pool takes care of actual reconnects.
    # ------------------------------------------------------------------
    def connect(self):
        try:
            _get_pool()          # ensure pool exists / re-create if needed
            self.connection = type('_Compat', (), {'is_connected': lambda s: True})()
        except Exception as e:
            print(f"[ERROR] Pool init failed: {e}")

    def disconnect(self):
        pass   # pool manages its own connections

    # ------------------------------------------------------------------
    # internal: borrow a connection, run fn(conn), return connection
    # One automatic retry on OperationalError (e.g. stale pooled connection).
    # ------------------------------------------------------------------
    def _run(self, fn):
        pool = _get_pool()
        conn = pool.get_connection()
        try:
            return fn(conn)
        except Error as e:
            # If the pooled connection was stale, retry once with a fresh one
            if e.errno in (2006, 2013, 2055):   # CR_SERVER_GONE / LOST / DISCONNECTED
                conn.close()
                conn = pool.get_connection()
                return fn(conn)
            raise
        finally:
            try:
                conn.close()    # returns connection back to pool
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API (unchanged signatures)
    # ------------------------------------------------------------------
    def execute_query(self, query, params=None):
        """Execute INSERT / UPDATE / DELETE. Returns lastrowid or None."""
        def _fn(conn):
            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                conn.commit()
                return cursor.lastrowid
            except Error as e:
                conn.rollback()
                print(f"[ERROR] execute_query: {e}")
                return None
            finally:
                cursor.close()
        try:
            return self._run(_fn)
        except Exception as e:
            print(f"[ERROR] execute_query (pool): {e}")
            return None

    def fetch_one(self, query, params=None):
        """Fetch a single row as dict, or None."""
        def _fn(conn):
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                return cursor.fetchone()
            except Error as e:
                print(f"[ERROR] fetch_one: {e}")
                return None
            finally:
                cursor.close()
        try:
            return self._run(_fn)
        except Exception as e:
            print(f"[ERROR] fetch_one (pool): {e}")
            return None

    def fetch_all(self, query, params=None):
        """Fetch all rows as list of dicts, or None."""
        def _fn(conn):
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                return cursor.fetchall()
            except Error as e:
                print(f"[ERROR] fetch_all: {e}")
                return None
            finally:
                cursor.close()
        try:
            return self._run(_fn)
        except Exception as e:
            print(f"[ERROR] fetch_all (pool): {e}")
            return None


# Single global instance — usage is identical to before
db = Database()
