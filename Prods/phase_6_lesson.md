# Phase 6: Local Database Threading & Concurrency

Continuing our roadmap, Phase 6 addresses a critical production bottleneck: **The "Database is Locked" Error**.

When scaling a FastAPI server, we use multiple "Workers" (e.g., Uvicorn workers). If two students scan their faces at the exact same millisecond, two separate Python workers try to open the local `attendance.db` file and write a record simultaneously. By default, SQLite crashes when this happens.

Here is how your `server-vino` architecture solves this in `database/attendance.py`.

## The Goal

Understand the specific SQLite `PRAGMA` commands used in `database/attendance.py` that transform a simple local file into a production-ready, concurrent database capable of handling massive student foot traffic.

---

### Step 1: The Concurrency Problem

By default, SQLite uses a `rollback journal`. When Python Worker A writes to the database, SQLite rigidly locks the entire `.db` file. If Python Worker B tries to read or write at that exact moment, Worker B gets a fatal `sqlite3.OperationalError: database is locked`.

If we didn't fix this, your production server would drop attendance records during busy morning rush hours.

### Step 2: Write-Ahead Logging (WAL Mode)

Look at line 46 of `server-vino/database/attendance.py`:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

This is the magic switch. **WAL** stands for Write-Ahead Logging.

Instead of locking the main `.db` file, SQLite creates a new invisible file called `attendance.db-wal`.
When Worker A writes a new attendance record, it quickly appends it to the end of the `-wal` file without touching the main database.
Because the main file isn't locked, Worker B can simultaneously read data from the main database without crashing!

Eventually, SQLite automatically merges the `-wal` file into the main database in the background (a process called "checkpointing").

### Step 3: The Busy Timeout

Even with WAL mode, what happens if Worker A and Worker B try to **write** to the `-wal` file at the exact same millisecond?
Look at line 47:

```python
conn.execute("PRAGMA busy_timeout=30000")
```

By default, if SQLite detects another worker writing, it instantly throws an error and crashes the request.

By setting `busy_timeout=30000` (30 seconds), you are telling SQLite: "If the database is currently busy writing a face scan, don't crash. Just politely wait in a queue for up to 30 seconds until the other worker finishes."

Because writing a single row takes 0.001 seconds, Worker B simply waits 1 millisecond and then successfully inserts its data. The user never notices a delay.

### Step 4: The Connection Timeout

Look at line 286:

```python
conn = sqlite3.connect(self.database_path, timeout=30.0, check_same_thread=False)
```

1. `timeout=30.0`: reinforces the 30-second queue waiting period for the Python driver.
2. `check_same_thread=False`: Tells Python not to panic if different asynchronous FastAPI tasks share the same database connection pool.

---

### Phase 6 Summary

1. Standard SQLite crashes during simultaneous writes.
2. `journal_mode=WAL` enables concurrent Reading and Writing by appending data to a temporary log file.
3. `busy_timeout` forces Python workers to wait in a 30-second queue instead of crashing when simultaneous writes occur.
4. Your server can now handle hundreds of simultaneous face scans without dropping a single attendance record.
