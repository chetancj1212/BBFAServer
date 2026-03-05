# Phase 9: The Local Database Threading & Concurrency

Rounding out **Part 2: Security, Data, & Payload Handling**, we look at the most common reason Python backends crash in production: **Database Deadlocks**.

In Phase 6, we briefly touched on how multi-worker deployments cause multiple Python processes to try and open the `attendance.db` file at the exact same time. If two students scan their faces at the same millisecond, standard SQLite triggers a fatal `sqlite3.OperationalError: database is locked` error.

Let's dive deeper into exactly how `server-vino/database/attendance.py` defends against this.

## The Goal

Understand SQLite Write-Ahead Logging (WAL), connection timeout queues, and how Context Managers cleanly open and close database streams to prevent memory leaks and permanent file locking.

---

### Step 1: The PRAGMA Defense (WAL Mode)

Look at `_configure_pragmas` in `database/attendance.py`.

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

1.  **WAL (Write-Ahead Logging)**: Instead of locking the entire `attendance.db` file when writing, SQLite creates a temporary, invisible `attendance.db-wal` log file. Python Worker A quickly appends its new record to the end of the `-wal` file. This means **Worker B can simultaneously read from the main database** without being blocked! Later, SQLite silently merges the `-wal` file into the main database in the background.
2.  **Busy Timeout**: If Worker A and Worker B try to write to the `-wal` file at the exact same microsecond, `busy_timeout=30000` tells Worker B to wait politely in a queue for up to 30 seconds instead of instantly crashing. Since a SQLite write takes `~0.001` seconds, Worker B simply waits a millisecond and succeeds.

### Step 2: Connection Pooling Flags

Look at line 286:

```python
conn = sqlite3.connect(
    self.database_path, timeout=30.0, check_same_thread=False
)
```

1.  **timeout=30.0**: Enforces the 30-second waiting-in-line rule at the Python level.
2.  **check_same_thread=False**: FastAPI revolves around asynchronous Tasks (`async def`). These tasks frequently jump across different CPU threads. By default, SQLite panics if Thread X opens a connection but Thread Y tries to use it. Setting this to `False` tells SQLite "I know what I'm doing, let FastAPI juggle the threads."

### Step 3: The Context Manager (`_get_connection`)

Look closely at the `@contextmanager` decorator around line 280.

```python
@contextmanager
def _get_connection(self):
    conn = None
    try:
        conn = sqlite3.connect(...)
        yield conn
    except Exception as e:
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()
```

This is incredibly important for production servers.
If your Python code crashes in the middle of a database write (e.g., you accidentally divide by zero), the connection to the `.db` file normally stays open FOREVER. The file becomes permanently locked ("zombie connection"), and you have to restart the entire server to fix it.

By using the `with self._get_connection() as conn:` syntax throughout the file, we guarantee that the `finally: conn.close()` block will **always execute**, securely slamming the database connection shut, even if the surrounding Python code crashes and burns violently.

---

### Phase 9 Summary

1.  Use `PRAGMA journal_mode=WAL` to allow simultaneous database reads and writes via temporary log files.
2.  Use `PRAGMA busy_timeout` to force competing workers to wait in a 30-second queue instead of crashing.
3.  Set `check_same_thread=False` to allow FastAPI's asynchronous tasks to safely juggle the database connection.
4.  Always wrap database connections in `try/finally` context managers to ensure the file securely unlocks even if Python crashes.
