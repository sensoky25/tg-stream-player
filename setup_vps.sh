#!/bin/bash
# ========================================================
# Automated High-Speed Setup for Telegram Stream Server
# OS: Ubuntu 22.04 / 24.04 (DigitalOcean Singapore)
# ========================================================

set -e

echo "========================================================"
echo "🚀 Starting High-Speed Stream Server Setup on Singapore VPS..."
echo "========================================================"

# 1. Configure 2GB Swap (Prevents Out-Of-Memory on 512MB RAM VPS)
if [ ! -f /swapfile ]; then
    echo "📦 Creating 2GB Swap Memory..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "✅ Swap Memory configured."
fi

# 2. Update System and Install Essentials
echo "🔄 Updating system packages and installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-pip python3-venv git nginx curl ufw build-essential libffi-dev

# 3. Setup Project Directory
echo "📁 Setting up Project in /root/tg-stream-player..."
mkdir -p /root/tg-stream-player
cd /root/tg-stream-player

# Clone or pull repo
if [ -d ".git" ]; then
    git pull origin main
else
    git clone https://github.com/sensoky25/tg-stream-player.git .
fi

# 4. Create Virtual Environment & Install Requirements with C acceleration (cryptg)
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install cryptg || true

# 5. Create .env Configuration
echo "⚙️ Creating .env configuration..."
cat << 'EOF' > .env
API_ID=38606693
API_HASH=4784d8963ea114bcd26dd59d84f997ad
BOT_TOKEN=8445405147:AAH51CWfNzBADynBFcGV1yHb5gcraKCnlfY
BIN_CHANNEL=-1003909046470
PORT=8080
HOST=127.0.0.1
FQDN=https://stream.nexkh.top
EOF

# 6. Create Systemd Service (Auto-starts on reboot, runs 24/7)
echo "🔧 Setting up Systemd Service (tgstream)..."
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

# 7. Configure Nginx Reverse Proxy with Video Streaming Optimizations
echo "🌐 Configuring Nginx Reverse Proxy for stream.nexkh.top..."
cat << 'EOF' > /etc/nginx/sites-available/stream.nexkh.top
server {
    listen 80;
    listen [::]:80;
    server_name stream.nexkh.top;

    # Maximum file upload/request buffer
    client_max_body_size 0;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        # WebSocket & Streaming Headers
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # HTTP 206 Partial Content & Video Seeking Support
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;

        # Disable Buffering for Instant Zero-Latency Video Streaming
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/stream.nexkh.top /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# 8. Firewall Configuration
ufw allow 'Nginx Full' || true
ufw allow 22/tcp || true

echo "========================================================"
echo "🎉 SETUP COMPLETED SUCCESSFULLY!"
echo "📍 Server IP: 157.245.201.238 (Singapore)"
echo "🚀 Status: tgstream service is RUNNING 24/7"
echo "========================================================"
