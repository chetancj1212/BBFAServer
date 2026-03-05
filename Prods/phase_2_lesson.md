# Phase 2: CORS, Middleware, & Rate Limiting

Now that your server is booted securely behind a Cloudflare Tunnel (Phase 1), anyone on the internet can try to send it HTTP requests. How does FastAPI filter the good traffic from the bad traffic before it even reaches your AI models?

This happens in the **Middleware layer**. Middleware consists of functions that run _before_ your actual route logic executes.

## 1. CORS (Cross-Origin Resource Sharing)

Look at `server-vino/config/cors.py` and `server-vino/middleware/cors.py`.

**The Problem:**
If your server is hosted at `https://api.chetancj.in`, and a malicious website `https://evil-hacker.com` tries to inject a script that makes a background AJAX request to your server, the browser will block it. Why? Because the "Origin" (`evil-hacker.com`) does not match the server's domain.

**The Solution:**
You have to explicitly tell FastAPI which frontend URLs are allowed to talk to it.

Notice in `cors.py`:

```python
"allow_origins": [
    "http://localhost:3000",
    "http://localhost:5173",
],
"allow_origin_regex": r"https?://(.*\.ngrok-free\.dev|.*\.chetancj\.in)",
```

This is a robust production setup.

1. `allow_origins`: You explicitly allow `localhost:3000` so your React Native or React web panel can talk to the server while you are coding locally.
2. `allow_origin_regex`: You use Regular Expressions to allow _any_ subdomain of `chetancj.in`. This means if your frontend is hosted at `panel.chetancj.in`, the server accepts the request.

If a request comes from `random-website.com`, the FastAPI CORS Middleware intercepts it and immediately returns a `403 Forbidden` error, saving your AI models from processing unauthorized traffic.

## 2. Rate Limiting & DDoS Protection (SlowAPI)

Look at `server-vino/middleware/rate_limit.py`.

**The Problem:**
Face recognition requires heavy CPU matrix multiplication. If a student wrote a python script to hit your `/scan-face` endpoint 1,000 times per second, your server's CPU would instantly jump to 100%, causing the server to crash for everyone else. This is a Denial of Service (DoS) attack.

**The Solution:**
You are using a library called `slowapi`.

```python
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
```

1. **The Key:** `get_remote_address` extracts the IP address of the student making the request.
2. **The Limit:** Later in the code, you will see route decorators like `@limiter.limit("3/minute")`.
3. **The Result:** If an IP address tries to hit an endpoint 4 times in one minute, the `slowapi` middleware intercepts the 4th request and immediately returns a `429 Too Many Requests` status code.

The heavy AI code is completely protected.

---

### Phase 2 Summary

Before a request ever touches `scrfd_10g.onnx`:

1. Cloudflare encrypts and tunnels the connection. (Phase 1)
2. Uvicorn hands the network bytes to a free Python Worker. (Phase 1)
3. CORS Middleware checks if the website making the request is in your `allow_origins` list.
4. SlowAPI Middleware checks if the IP address has exceeded its speed limit.

Only if all of these conditions pass does FastAPI allow the data to move forward into your Python route handlers!
