#!/bin/bash
# ========================================================
# Automated 1-Click Setup for Telegram Video Stream Server
# OS: Ubuntu 22.04 / 24.04 (DigitalOcean, Linode, Hetzner, etc.)
# ========================================================

set -e

echo "========================================================"
echo "🚀 Telegram Video Stream Server - 1-Click Auto Setup"
echo "========================================================"

# 1. Check or Configure .env
mkdir -p /root/tg-stream-player
cd /root/tg-stream-player

if [ -f .env ]; then
    echo "⚙️ Found existing .env configuration."
    source .env || true
fi

if [ -z "$BOT_TOKEN" ] || [ -z "$API_ID" ] || [ -z "$BIN_CHANNEL" ] || [ -z "$FQDN" ]; then
    echo ""
    echo "📝 សូមបញ្ចូលព័ត៌មាន Bot និង Domain សម្រាប់ Server ថ្មីនេះ៖"
    echo "--------------------------------------------------------"
    
    read -p "1. បញ្ចូល Domain/Subdomain (ឧទាហរណ៍: stream.nexkh.top): " INPUT_DOMAIN < /dev/tty
    INPUT_DOMAIN=${INPUT_DOMAIN#https://}
    INPUT_DOMAIN=${INPUT_DOMAIN#http://}
    INPUT_DOMAIN=${INPUT_DOMAIN%/}
    
    read -p "2. បញ្ចូល Telegram BOT_TOKEN (ពី @BotFather): " INPUT_BOT_TOKEN < /dev/tty
    read -p "3. បញ្ចូល API_ID (ពី my.telegram.org): " INPUT_API_ID < /dev/tty
    read -p "4. បញ្ចូល API_HASH (ពី my.telegram.org): " INPUT_API_HASH < /dev/tty
    read -p "5. បញ្ចូល Bin Channel ID (ឧទាហរណ៍: -1003909046470): " INPUT_BIN_CHANNEL < /dev/tty
    read -p "6. បញ្ចូល Email សម្រាប់ចុះឈ្មោះ SSL (ឧទាហរណ៍: admin@gmail.com): " INPUT_EMAIL < /dev/tty
    read -p "7. បញ្ចូល Telegram User ID របស់ម្ចាស់ (សម្រាប់ចាក់សោប្រើបានតែម្ចាស់ - ចុច Enter បើចង់ទុកចំហ): " INPUT_OWNER_ID < /dev/tty
    
    cat << EOF > .env
API_ID=${INPUT_API_ID}
API_HASH=${INPUT_API_HASH}
BOT_TOKEN=${INPUT_BOT_TOKEN}
BIN_CHANNEL=${INPUT_BIN_CHANNEL}
PORT=8080
HOST=127.0.0.1
FQDN=https://${INPUT_DOMAIN}
OWNER_ID=${INPUT_OWNER_ID}
EOF

    DOMAIN="${INPUT_DOMAIN}"
    SSL_EMAIL="${INPUT_EMAIL:-admin@${INPUT_DOMAIN}}"
else
    DOMAIN=$(echo "$FQDN" | sed -e 's|^[^/]*//||' -e 's|/.*$||')
    SSL_EMAIL="admin@${DOMAIN}"
fi

echo "✅ Configuration saved for domain: ${DOMAIN}"

# 2. Configure 2GB Swap (Prevents Out-Of-Memory on 512MB/1GB RAM VPS)
if [ ! -f /swapfile ]; then
    echo "📦 Configuring 2GB Swap Memory..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "✅ Swap Memory configured."
fi

# 3. Update System & Install Essentials
echo "🔄 Installing dependencies (Python, Nginx, Git, Certbot)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-pip python3-venv git nginx curl certbot python3-certbot-nginx build-essential libffi-dev

# 4. Clone or Update Repo
if [ ! -f "server.py" ]; then
    echo "📥 Cloning project from GitHub..."
    git clone https://github.com/sensoky25/tg-stream-player.git temp_repo
    cp -rn temp_repo/* .
    cp -rn temp_repo/.* . 2>/dev/null || true
    rm -rf temp_repo
fi

# 5. Virtual Environment & Python Requirements
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install cryptg || true

# 6. Setup Systemd Service (24/7 Auto-restart)
echo "🔧 Setting up Systemd 24/7 background service..."
cat << 'EOF' > /etc/systemd/system/tgstream.service
[Unit]
Description=Telegram High-Speed Video Stream Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/tg-stream-player
ExecStart=/root/tg-stream-player/venv/bin/python3 /root/tg-stream-player/server.py
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tgstream
systemctl restart tgstream

# 7. Configure Nginx with Video Streaming Optimizations & SSD Slice Cache
echo "🌐 Configuring Nginx Reverse Proxy & SSD Slice Cache for ${DOMAIN}..."

# Setup Cache Directory
mkdir -p /var/cache/nginx/tgstream
chown -R www-data:www-data /var/cache/nginx/tgstream
chmod -R 755 /var/cache/nginx/tgstream

# Global Cache Zone configuration
cat << 'EOF' > /etc/nginx/conf.d/tg_stream_cache.conf
proxy_cache_path /var/cache/nginx/tgstream 
    levels=1:2 
    keys_zone=tg_stream_cache:50m 
    max_size=20g 
    inactive=14d 
    use_temp_path=off;
EOF

cat << EOF > /etc/nginx/sites-available/${DOMAIN}
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 0;

    # 🎥 High-Speed Video Byte-Range Slice Cache (Anti-FloodWait & High Concurrent Stream)
    location /stream/ {
        slice 2m;

        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_set_header Range \$slice_range;

        proxy_cache tg_stream_cache;
        proxy_cache_key \$uri\$slice_range;
        proxy_cache_valid 200 206 14d;

        proxy_ignore_headers X-Accel-Buffering Expires Cache-Control Set-Cookie;
        proxy_hide_header X-Accel-Buffering;

        proxy_cache_lock on;
        proxy_cache_lock_timeout 60s;
        proxy_cache_lock_age 60s;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_revalidate on;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;

        # CORS Headers
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Range, Origin, Content-Type, Accept" always;
        add_header Access-Control-Expose-Headers "Content-Range, Content-Length, Accept-Ranges" always;

        # Cache Hit/Miss Inspection Header
        add_header X-Cache-Status \$upstream_cache_status always;
    }

    # 📱 Web Player, Mini App Dashboard & REST APIs (No Caching)
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_set_header Range \$http_range;
        proxy_set_header If-Range \$http_if_range;

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# 8. Firewall (Open ports before running certbot)
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw allow 22/tcp || true
ufw allow 22022/tcp || true

# 9. Obtain Official Let's Encrypt SSL Certificate
echo "🔒 Securing ${DOMAIN} with Let's Encrypt SSL..."
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${SSL_EMAIL}" --redirect || {
    echo "⚠️ Certbot could not verify immediately. Please ensure DNS A-record points to this VPS IP."
}

echo "========================================================"
echo "🎉 SETUP COMPLETED SUCCESSFULLY!"
echo "📍 Domain: https://${DOMAIN}"
echo "🚀 Status: Running 24/7 under systemd (tgstream.service)"
echo "⚡ Cloudflare Tip: Set DNS Proxy to 'DNS only' (Gray Cloud) for max speed!"
echo "========================================================"
