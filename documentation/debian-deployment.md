# Debian Deployment Tutorial — Simple Recipes

This tutorial covers deploying Simple Recipes on a Debian (12 "Bookworm" or later) server, configuring it as a **systemd service** that starts automatically on boot, and setting up **Nginx as a reverse proxy with HTTPS** via Let's Encrypt.

---

## Prerequisites

- A Debian server with a public IP address
- A domain name pointing to that IP (required for HTTPS)
- Root or sudo access

---

## 1. Install Docker and Docker Compose

```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

sudo systemctl enable --now docker
```

---

## 2. Deploy the application

```bash
sudo mkdir -p /opt/simple-recipes
sudo git clone https://github.com/<org>/simple-recipes.git /opt/simple-recipes
cd /opt/simple-recipes

# Generate the .env file (SECRET_KEY is auto-generated)
make env
```

Review `/opt/simple-recipes/.env` and adjust `PORT` if needed (default: `8080`).

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

The application is now accessible at `http://<server-ip>:8080` and will restart automatically after every reboot.

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
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
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

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_read_timeout 60s;
        proxy_send_timeout 60s;

        client_max_body_size 20M;
    }
}
```

### Cookie security

When behind HTTPS, enable the `Secure` flag on the session cookie by updating `.env`:

```env
COOKIE_SECURE=true
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
docker compose -f /opt/simple-recipes/docker-compose.yml logs -f  # App logs
```
