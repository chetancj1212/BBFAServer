# BBFA Server — Docker Deployment Guide 🚀

This guide explains how to deploy the BBFA AI Server on any machine using Docker.

## 📦 Option 1: The "Portable" Method (Best for ZIP/Offline)

_No source code or internet required on the target machine._

### 🛠️ 1. On your Main Machine (with Models)

1. Build the image:
   ```powershell
   cd server
   docker build -t bbfa-server .
   ```
2. Export the image to a file:
   ```powershell
   docker save -o bbfa-server-image.tar bbfa-server
   ```
3. Move `bbfa-server-image.tar` to your new device (USB/Drive).

### 🚀 2. On the New Device

1. Load the image from the file:
   ```powershell
   docker load -i bbfa-server-image.tar
   ```
2. Run the server:
   ```powershell
   docker run -d --name bbfa-server -p 8700:8700 -v bbfa-data:/app/data bbfa-server
   ```

---

## 🏗️ Option 2: The "Build" Method (Requires models in weights/)

_Best if you already moved the source code to the other machine._

1. **Copy your `weights` folder** into `server/weights/`.
2. **Build and Run**:
   ```powershell
   cd server
   docker build -t bbfa-server .
   docker run -d --name bbfa-server -p 8700:8700 -v bbfa-data:/app/data bbfa-server
   ```

---

## 🚦 Verification & Management

- **Logs**: `docker logs -f bbfa-server` (Check for "Startup complete")
- **API Health**: [http://localhost:8700/](http://localhost:8700/)
- **Models Status**: [http://localhost:8700/models](http://localhost:8700/models)

### Common Commands:

- **Stop**: `docker stop bbfa-server`
- **Start**: `docker start bbfa-server`
- **Delete**: `docker rm -f bbfa-server`

---

_Note: The first run (without bundled models) downloads ~185MB of AI weights to the local volume._
