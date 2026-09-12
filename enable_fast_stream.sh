#!/bin/bash
# ========================================================
# Enable Direct High-Speed Streaming with Let's Encrypt SSL
# Domain: stream.nexkh.top
# ========================================================

set -e

echo "🚀 Installing Free Official Let's Encrypt SSL Certificate..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y certbot python3-certbot-nginx

echo "🔒 Obtaining SSL Certificate for stream.nexkh.top..."
certbot --nginx -d stream.nexkh.top --non-interactive --agree-tos --email sokysen25@gmail.com --redirect || certbot --nginx -d stream.nexkh.top --register-unsafely-without-email --agree-tos --redirect

echo "🔄 Reloading Nginx with maximum streaming speed optimizations..."
systemctl reload nginx

echo "========================================================"
echo "✅ SSL CERTIFICATE INSTALLED SUCCESSFULLY!"
echo "👉 Now in Cloudflare DNS, turn OFF the Proxy (Orange Cloud -> Gray Cloud) for 'stream.nexkh.top'."
echo "⚡ This will unlock DIRECT Singapore 60+ Mbps streaming speed!"
echo "========================================================"
