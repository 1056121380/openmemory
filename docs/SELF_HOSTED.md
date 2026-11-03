# Self-Hosted Deployment Guide (Docker / VPS / NAS)

For users who want a centralized 24/7 private memory hub accessible from multiple laptops, workstations, or mobile devices, OpenMemory can be hosted via Docker, VPS, or NAS.

---

## 1. Quick Start with Docker Compose

1. Clone your repo or copy `docker-compose.yml` and `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env to set your secure tokens
   ```

2. Start the service:
   ```bash
   docker compose up -d
   ```

3. Open your browser at `http://localhost:8080` (or `http://<your-host-ip>:8080`) to access the Web Review Console.

---

## 2. Docker Compose Configuration

```yaml
version: "3.8"

services:
  openmemory:
    image: openmemory:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: openmemory-hub
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - HUB_QUERY_TOKEN=${HUB_QUERY_TOKEN:-}
      - HUB_INGEST_TOKENS=${HUB_INGEST_TOKENS:-}
      - OPENMEMORY_DATA_DIR=/app/data
    volumes:
      - ./data:/app/data
```

---

## 3. Deployment on Private NAS (Synology, QNAP, Unraid)

- Mount a persistent directory (e.g. `/docker/openmemory/data` or `/opt/openmemory/data`) to `/app/data` inside the container.
- Map port `8080` to any available host port.
- Access via your local network IP or your **Tailscale** private IP for secure off-site access without exposing public ports.

---

## 4. Reverse Proxy & HTTPS (Nginx / Caddy / Traefik)

### Caddy Example:
```caddy
memory.yourdomain.internal {
    reverse_proxy localhost:8080
}
```

### Nginx Example:
```nginx
server {
    listen 80;
    server_name memory.yourdomain.internal;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
