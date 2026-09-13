#!/bin/bash
# ========================================================
# Script: add_client.sh
# Purpose: Add a new client (separate Bot + Subdomain)
# to the existing VPS on a dedicated port & service
# ========================================================

set -e

echo "========================================================"
echo "🚀 បន្ថែមអតិថិជនថ្មី (Add New Client) លើ VPS តែមួយ"
echo "========================================================"

# Check if base tg-stream-player exists
if [ ! -d "/root/tg-stream-player" ]; then
    echo "❌ រកមិនឃើញ Folder មេ /root/tg-stream-player ឡើយ។"
    echo "👉 សូមដំណើរការ setup_vps.sh ជាមុនសិន។"
    exit 1
fi

# 1. Ask for Client Identifier (slug)
echo ""
echo "📝 សូមបញ្ចូលព័ត៌មានអតិថិជនថ្មី៖"
echo "--------------------------------------------------------"
read -p "1. ឈ្មោះសម្គាល់អតិថិជន (ជាអក្សរតូចគ្មានដកឃ្លា ឧ. client2 ឬ phumkhmer): " CLIENT_ID
CLIENT_ID=$(echo "$CLIENT_ID" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]_-')

if [ -z "$CLIENT_ID" ]; then
    echo "❌ ឈ្មោះសម្គាល់អតិថិជនមិនអាចទទេបានទេ។"
    exit 1
fi

CLIENT_DIR="/root/tg-clients/${CLIENT_ID}"
if [ -d "$CLIENT_DIR" ]; then
    echo "⚠️ អតិថិជនឈ្មោះ '${CLIENT_ID}' មានរួចហើយនៅក្នុង ${CLIENT_DIR}!"
    read -p "តើបងចង់កែប្រែទិន្នន័យចាស់ទេ? (y/n): " OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
        echo "បានបោះបង់។"
        exit 0
    fi
fi

# 2. Ask for Domain
read -p "2. បញ្ចូល Domain/Subdomain របស់អតិថិជន (ឧ. stream.phumkhmer.com): " INPUT_DOMAIN
INPUT_DOMAIN=${INPUT_DOMAIN#https://}
INPUT_DOMAIN=${INPUT_DOMAIN#http://}
INPUT_DOMAIN=${INPUT_DOMAIN%/}

if [ -z "$INPUT_DOMAIN" ]; then
    echo "❌ Domain មិនអាចទទេបានទេ។"
    exit 1
fi

# 3. Ask for Telegram Credentials
read -p "3. បញ្ចូល Telegram BOT_TOKEN (ពី @BotFather របស់ភ្ញៀវ): " INPUT_BOT_TOKEN
read -p "4. បញ្ចូល API_ID (ពី my.telegram.org របស់ភ្ញៀវ): " INPUT_API_ID
read -p "5. បញ្ចូល API_HASH (ពី my.telegram.org របស់ភ្ញៀវ): " INPUT_API_HASH
read -p "6. បញ្ចូល Bin Channel ID (ឧ. -100xxxxxxxxxx): " INPUT_BIN_CHANNEL
read -p "7. បញ្ចូល Email សម្រាប់ចុះឈ្មោះ SSL (ឧ. admin@${INPUT_DOMAIN}): " INPUT_EMAIL
INPUT_EMAIL=${INPUT_EMAIL:-admin@${INPUT_DOMAIN}}

# 4. Auto-detect next available port (starting from 8081)
PORT=8081
while ss -tuln | grep -q ":${PORT} "; do
    PORT=$((PORT + 1))
done

echo ""
echo "⚡ កំពុងរៀបចំ Port ស្វ័យប្រវត្តិ៖ ${PORT}"
echo "📁 បង្កើត Folder សម្រាប់ភ្ញៀវ៖ ${CLIENT_DIR}"

mkdir -p "$CLIENT_DIR"
mkdir -p "$CLIENT_DIR/templates"

# Symlink templates so all instances share UI
ln -sf /root/tg-stream-player/templates/* "$CLIENT_DIR/templates/" 2>/dev/null || true

# 5. Create .env for this client
cat << EOF > "$CLIENT_DIR/.env"
API_ID=${INPUT_API_ID}
API_HASH=${INPUT_API_HASH}
BOT_TOKEN=${INPUT_BOT_TOKEN}
BIN_CHANNEL=${INPUT_BIN_CHANNEL}
PORT=${PORT}
HOST=127.0.0.1
FQDN=https://${INPUT_DOMAIN}
SESSION_NAME=session_${CLIENT_ID}
EOF

# 6. Create dedicated Systemd Service for this client
SERVICE_NAME="tgstream-${CLIENT_ID}"
echo "🔧 បង្កើត Systemd Service: /etc/systemd/system/${SERVICE_NAME}.service..."

cat << EOF > "/etc/systemd/system/${SERVICE_NAME}.service"
[Unit]
Description=Telegram Video Stream Server for ${CLIENT_ID}
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${CLIENT_DIR}
EnvironmentFile=${CLIENT_DIR}/.env
ExecStart=/root/tg-stream-player/venv/bin/python3 /root/tg-stream-player/server.py
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

# 7. Configure Nginx for this client's domain
echo "🌐 កំណត់ Nginx Reverse Proxy សម្រាប់ ${INPUT_DOMAIN} (Port ${PORT})..."
cat << EOF > "/etc/nginx/sites-available/${INPUT_DOMAIN}"
server {
    listen 80;
    listen [::]:80;
    server_name ${INPUT_DOMAIN};

    client_max_body_size 0;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
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

ln -sf "/etc/nginx/sites-available/${INPUT_DOMAIN}" /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# 8. Obtain Let's Encrypt SSL
echo "🔒 ដំឡើង Let's Encrypt SSL សម្រាប់ ${INPUT_DOMAIN}..."
certbot --nginx -d "${INPUT_DOMAIN}" --non-interactive --agree-tos --email "${INPUT_EMAIL}" --redirect || {
    echo "⚠️ មិនទាន់អាចដំឡើង SSL បានភ្លាមៗទេ។ សូមប្រាកដថាអតិថិជនបានចង្អុល A-Record ទៅកាន់ IP VPS នេះរួចរាល់ (Proxy: DNS Only)!"
}

echo ""
echo "========================================================"
echo "🎉 បានបន្ថែមអតិថិជនថ្មីជោគជ័យ!"
echo "👤 ឈ្មោះអតិថិជន: ${CLIENT_ID}"
echo "🌐 Domain: https://${INPUT_DOMAIN}"
echo "🔌 Port: ${PORT}"
echo "⚙️ Systemd Service: ${SERVICE_NAME}"
echo "📁 ទីតាំងទិន្នន័យ: ${CLIENT_DIR}"
echo "========================================================"
echo "👉 បញ្ជាពិនិត្យមើលដំណើរការ: systemctl status ${SERVICE_NAME}"
echo "👉 បញ្ជា Restart: systemctl restart ${SERVICE_NAME}"
echo "========================================================"
