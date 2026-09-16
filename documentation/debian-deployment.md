# Debian Deployment Tutorial — Simple Recipes

This tutorial covers deploying Simple Recipes on a Debian (12 "Bookworm" or later) server, configuring it as a **systemd service** that starts automatically on boot, and setting up **Nginx as a reverse proxy with HTTPS** via Let's Encrypt.

---

## Prerequisites

- A Debian server with a public IP address
- A domain name pointing to that IP (required for HTTPS)
- Root or sudo access

---

## 1. Install Docker and Docker Compose

Follow the official Docker documentation for Debian:

> **https://docs.docker.com/engine/install/debian/**

Make sure `docker compose` (v2 plugin) is available after installation:

```bash
docker compose version
```

---

## 2. Deploy the application

Create a dedicated system user that owns the application directory and belongs to the `docker` group:

```bash
sudo useradd -r -m -d /opt/simple-recipes -s /bin/bash recipes
sudo usermod -aG docker recipes
```

Clone the repository and set up the environment **as that user**:

```bash
sudo -u recipes git clone https://github.com/<org>/simple-recipes.git /opt/simple-recipes
sudo -u recipes bash -c 'cd /opt/simple-recipes && make env'
```

Review `/opt/simple-recipes/.env` as root and adjust `PORT` if needed (default: `8080`):

```bash
sudo nano /opt/simple-recipes/.env
```

> The data directory is persisted via the Docker volume defined in `docker-compose.yml`.  
> To use a custom path (NAS, external drive…), edit the `volumes:` section before the first start.

---

## 3. Create a systemd service

Create the unit file `/etc/systemd/system/simple-recipes.service`:

```ini
[Unit]
Description=Simple Recipes
Documentation=https://github.com/<org>/simple-recipes
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=recipes
Group=recipes
WorkingDirectory=/opt/simple-recipes
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable simple-recipes
sudo systemctl start simple-recipes

# Verify
sudo systemctl status simple-recipes
```

The application now listens on `127.0.0.1:8080` and will restart automatically
after every reboot. It is deliberately **not** reachable from the network
directly: all traffic goes through the Nginx reverse proxy configured below, so
the session cookie is never sent over plain HTTP.

---

## 4. Install and configure Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```

Create the virtual host `/etc/nginx/sites-available/simple-recipes`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name recipes.example.com;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        # $remote_addr, not $proxy_add_x_forwarded_for: a client-supplied
        # X-Forwarded-For must never reach the application, or anyone could
        # spoof their IP and defeat the login rate limiter.
        proxy_set_header   X-Forwarded-For   $remote_addr;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_read_timeout 60s;
        proxy_send_timeout 60s;

        client_max_body_size 20M;
    }
}
```

Enable it and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/simple-recipes /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Enable HTTPS with Let's Encrypt (Certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d recipes.example.com
```

Certbot will:
1. Obtain a certificate from Let's Encrypt
2. Automatically update your Nginx configuration to add TLS directives and redirect HTTP → HTTPS

The resulting configuration will look like:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name recipes.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name recipes.example.com;

    ssl_certificate     /etc/letsencrypt/live/recipes.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/recipes.example.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Tell browsers to never speak plain HTTP to this host again.
    # Add "; preload" only once you are sure every subdomain serves HTTPS.
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        # $remote_addr, not $proxy_add_x_forwarded_for: a client-supplied
        # X-Forwarded-For must never reach the application, or anyone could
        # spoof their IP and defeat the login rate limiter.
        proxy_set_header   X-Forwarded-For   $remote_addr;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_read_timeout 60s;
        proxy_send_timeout 60s;

        client_max_body_size 20M;
    }
}
```

### Security settings

Review these `.env` values before going live:

```env
# Required, at least 32 characters. The application refuses to start otherwise.
# Generate one with:
#   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
SECRET_KEY=<a-long-random-value>

# Adds the Secure flag to the session cookie and sends HSTS. Keep it true
# behind HTTPS.
COOKIE_SECURE=true

# Reject requests whose Host header is not yours.
ALLOWED_HOSTS=recipes.example.com

# Keep the API documentation closed to anonymous visitors.
ENABLE_DOCS=false

# The Docker network the reverse proxy reaches the container from. uvicorn
# only honours X-Forwarded-For coming from these addresses. Never use "*".
FORWARDED_ALLOW_IPS=172.16.0.0/12
```

Then restart the service:

```bash
sudo systemctl restart simple-recipes
```

### Certificate renewal

Certbot installs a systemd timer that renews certificates automatically. Verify it is active:

```bash
sudo systemctl status certbot.timer
```

To test a dry-run renewal:

```bash
sudo certbot renew --dry-run
```

---

## Quick reference

```bash
sudo systemctl start   simple-recipes   # Start
sudo systemctl stop    simple-recipes   # Stop
sudo systemctl restart simple-recipes   # Restart
sudo systemctl status  simple-recipes   # Status

sudo journalctl -u simple-recipes -f    # Live logs
sudo -u recipes docker compose -f /opt/simple-recipes/docker-compose.yml logs -f  # App logs
```

---

## 7. Keeping the deployment secure

- **Dependencies.** `make audit` runs `pip-audit` against the pinned
  requirements; CI runs the same check on every push. Rebuild and redeploy when
  it reports a fix.
- **Backups.** Everything lives in the bind-mounted data directory: the SQLite
  database under `db/` and one folder per recipe under `recipes/`. Back up the
  whole directory; it contains password hashes, so protect it accordingly.
- **Accounts.** The first account to register becomes administrator. Approve new
  accounts from `/admin/users`, and use **Suspendre** there to cut off a
  compromised account — it invalidates that user's live sessions immediately.
- **Static assets.** `/static/js/*.js` and `/static/css/*.css` are served
  without cache busting. After deploying a new version, hard-reload once (or add
  a version query string) so browsers do not mix new HTML with old JavaScript.
