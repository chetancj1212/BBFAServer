# Phase 1: The Boot Sequence, Uvicorn, & Cloudflare Tunnels

Let's dive into the absolute foundational layer of your server. How does it turn on, and how does data from thousands of miles away securely reach your Python code?

## 1. The Startup Script

Look at `start-backend-cloudflare.bat`. It executes two distinct commands simultaneously:

1. `python main.py` (Starts Uvicorn on your local machine)
2. `cloudflared tunnel run bbfa-backend` (Starts the Cloudflare daemon)

Why two commands? Because your laptop is sitting behind a router firewall. Your router blocks all incoming traffic by default to protect you. Without Cloudflare, no one outside your house could reach your server.

## 2. The Cloudflare Tunnel (Zero Trust Networking)

A traditional server requires "Port Forwarding"—poking a hole in your router's firewall so traffic can come in. **Cloudflare Tunnels work entirely differently.**

1. `cloudflared` initiates an _outbound_ connection from your laptop to Cloudflare's massive edge network.
2. Because it's an outbound connection, your router allows it.
3. This creates a secure, encrypted "tunnel" between your laptop and Cloudflare.
4. When a student goes to `https://api.chetancj.in`, they are actually hitting a Cloudflare data center somewhere in the world.
5. Cloudflare handles the SSL certificate (HTTPS), decrypts the request, and pumps the raw HTTP data down the tunnel _into_ your laptop on port `8700`.

**Architecture Diagram:**

```mermaid
graph LR
    A[Student Mobile App] -->|HTTPS Requests| B(Cloudflare Servers)
    B -->|Encrypted Outbound Tunnel| C[cloudflared daemon on your laptop]
    C -->|Localhost Port 8700| D[Uvicorn Python Server]
```

## 3. Uvicorn & ASGI

Now, let's look at the bottom of `server-vino/main.py`:

```python
if __name__ == "__main__":
    workers = int(os.environ.get("WORKERS", "1"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(
        "main:app" if workers > 1 else app,
        host=host,
        port=8700,
        ...
    )
```

Why do we use `uvicorn` to run a FastAPI app?
Python was historically built around **WSGI** (Web Server Gateway Interface), which operates synchronously. This means if one student's request took 5 seconds to process, Student #2 had to wait 5 seconds before their request even started.

FastAPI is built on **ASGI** (Asynchronous Server Gateway Interface). Uvicorn is an ASGI web server.
It uses an "Event Loop". When Student #1's request is waiting for the AI model to finish, the Uvicorn server _pauses_ that function and immediately accepts Student #2's request.

**This is critical for production.** Without ASGI, your face recognition server would completely freeze under heavy traffic.

## 4. Multi-Worker Architecture

Notice the `workers = int(os.environ.get("WORKERS", "1"))` logic in `main.py`.

Python has a notorious limitation called the **GIL** (Global Interpreter Lock). Because of the GIL, a single Python process can only utilize exactly **one CPU core** at a time, no matter how async the code is. Your i5 processor has 4 physical cores, but standard Python will only ever use 1.

By setting the environment variable `WORKERS=4`, Uvicorn will spawn 4 entirely separate Python processes running your server. This bypasses the GIL and allows you to utilize 100% of your CPU for handling multiple face recognition requests simultaneously.

### Experiment:

1. Open `server-vino/start-backend-cloudflare.bat`.
2. Change the python command to force multiple workers: `set WORKERS=4 && python main.py`
3. Try running it. You will see Uvicorn boot up 4 separate worker processes in your terminal!
