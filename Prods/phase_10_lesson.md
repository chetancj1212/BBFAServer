# Phase 10: Centralized Logging Rotation

This phase marks the end of **Part 2: Security, Data, & Payload Handling**. We must discuss a critical issue that frequently takes down production servers after a few months of smooth operation: **Disk Space Exhaustion from Logs**.

Currently, in `server-vino/config/logging_config.py`, the server is configured to print logs specifically to the console `stdout`.

## The Goal

Understand the danger of infinite log files in a 24/7 FastAPI server, and learn how to implement `RotatingFileHandler` to automatically manage debug files without manual intervention.

---

### Step 1: The Infinite File Danger

When you deploy this server and leave it running for 6 months, every single API request, error, and database operation generates a string of text.

If you simply redirect console output to a file like `server_debug.log`, that file will grow continuously. Over a few months of heavy university traffic, that single `.log` file could swell to 50 GB or 100 GB.
When the hard drive hits 100% capacity, Linux/Windows will freeze, the database will corrupt, and the server will violently crash.

### Step 2: The Solution (RotatingFileHandler)

Python's built-in `logging` module offers a production-grade solution.

Right now, your config looks like this:

```python
"handlers": {
    "console": {
        "class": "logging.StreamHandler",
        "level": "INFO",
        ...
    }
}
```

To prevent the hard drive from filling up, we add a **Rotating File Handler** to the configuration:

```python
"handlers": {
    "console": { ... },
    "file": {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": "server_debug.log",
        "maxBytes": 10485760,  # 10 Megabytes
        "backupCount": 5,      # Keep 5 historical backup files
        "level": "INFO",
        "formatter": "default"
    }
}
```

### Step 3: How Rotation Works in Practice

With the configuration above, here is what happens when thousands of students scan their faces:

1. The server writes logs to `server_debug.log`.
2. As soon as `server_debug.log` reaches exactly 10 Megabytes in size, Python instantly renames it to `server_debug.log.1`.
3. Python creates a fresh, empty `server_debug.log` and continues writing uninterrupted.
4. When the new file hits 10MB, the older file `server_debug.log.1` is renamed to `server_debug.log.2`, and `server_debug.log.1` is freshly archived.
5. **The Deletion**: Because we set `backupCount: 5`, once Python reaches `server_debug.log.5`, the absolute oldest log file is **automatically deleted forever**.

### Step 4: Level Propagation

Look at line 42 in `logging_config.py`.

```python
if env == "production":
    config["handlers"]["console"]["level"] = "WARNING"
```

During local testing, you want to see `INFO` messages like "Student John authenticated".
In a true production environment, `INFO` logs generate too much noise. The code automatically throttles the log level up to `WARNING` when the `ENVIRONMENT` variable is set to production.
This means only Errors and Warnings are written to the disk, saving immense amounts of I/O operations and CPU cycles.

---

### Phase 10 Summary

1.  Infinite log files will eventually crash any 24/7 API server by filling the hard drive.
2.  `RotatingFileHandler` automatically chunks log files into manageable sizes (e.g., 10MB) and automatically deletes old files to guarantee log file space never exceeds 50MB total.
3.  Production environments should suppress standard `INFO` messages to reduce wear-and-tear on the disk drive and CPU.
