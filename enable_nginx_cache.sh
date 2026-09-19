#!/bin/bash
# ========================================================
# Script: enable_nginx_cache.sh
# Purpose: Enable Nginx Byte-Range Slice Cache on VPS
#          Solves Telegram Rate Limit / FloodWait & Video Buffering
# ========================================================

set -e

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}========================================================${NC}"
echo -e "${CYAN}🚀 Telegram Stream Server - Nginx Slice Cache Activator${NC}"
echo -e "${CYAN}========================================================${NC}"

# 1. Check Root Privileges
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}❌ Error: សូមដំណើរការ Script នេះជា Root (sudo bash enable_nginx_cache.sh)${NC}"
    exit 1
fi

# 2. Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    echo -e "${RED}❌ Error: មិនទាន់ឃើញ Nginx ត្រូវបានដំឡើងនៅលើ Server នេះឡើយ!${NC}"
    exit 1
fi

# 3. Create Cache Directory on VPS SSD
CACHE_DIR="/var/cache/nginx/tgstream"
echo -e "${YELLOW}📁 [1/4] កំពុងរៀបចំទីតាំងផ្ទុក Cache: ${CACHE_DIR}...${NC}"
mkdir -p "$CACHE_DIR"
chown -R www-data:www-data "$CACHE_DIR"
chmod -R 755 "$CACHE_DIR"
echo -e "${GREEN}✅ ទីតាំង Cache រួចរាល់។${NC}"

# 4. Create Global Cache Configuration in /etc/nginx/conf.d/
CONF_CACHE="/etc/nginx/conf.d/tg_stream_cache.conf"
echo -e "${YELLOW}⚙️ [2/4] កំពុងកំណត់ Global Cache Zone (/etc/nginx/conf.d/tg_stream_cache.conf)...${NC}"

# Auto-detect available disk space to prevent filling up small VPS disks (e.g. 10GB Droplets)
FREE_KB=$(df -k "$CACHE_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || df -k / | awk 'NR==2 {print $4}')
FREE_MB=$((FREE_KB / 1024))

if [ "$FREE_MB" -lt 4000 ]; then
    CACHE_MAX_SIZE="2g"
elif [ "$FREE_MB" -lt 8000 ]; then
    CACHE_MAX_SIZE="4g"
elif [ "$FREE_MB" -lt 15000 ]; then
    CACHE_MAX_SIZE="8g"
else
    CACHE_MAX_SIZE="20g"
fi
echo -e "   💾 ពិនិត្យឃើញ Disk សល់ទំហំ: ${CYAN}${FREE_MB} MB${NC} -> កំណត់ Cache Max Size: ${GREEN}${CACHE_MAX_SIZE}${NC}"

cat << EOF > "$CONF_CACHE"
# ========================================================
# Telegram Stream Server - Video Slice Cache Configuration
# Auto-scaled Size: ${CACHE_MAX_SIZE} SSD Storage, 50MB Key Zone
# Inactive: 14 Days (Auto-evict unused video chunks)
# ========================================================
proxy_cache_path /var/cache/nginx/tgstream 
    levels=1:2 
    keys_zone=tg_stream_cache:50m 
    max_size=${CACHE_MAX_SIZE} 
    inactive=14d 
    use_temp_path=off;
EOF

echo -e "${GREEN}✅ បានបង្កើត Global Cache Zone រួចរាល់ (ទំហំ ${CACHE_MAX_SIZE})។${NC}"

# 5. Patch Nginx Site Configurations in /etc/nginx/sites-available/
echo -e "${YELLOW}🔧 [3/4] កំពុងពិនិត្យ និងបន្ថែម Caching ទៅកាន់ Domain Site Configs...${NC}"

SITES_DIR="/etc/nginx/sites-available"
PATCHED_COUNT=0

if [ -d "$SITES_DIR" ]; then
    for site_file in "$SITES_DIR"/*; do
        if [ ! -f "$site_file" ]; then
            continue
        fi

        filename=$(basename "$site_file")
        if [ "$filename" == "default" ]; then
            continue
        fi

        # Check if site contains proxy_pass to tgstream backend (127.0.0.1:808...)
        if grep -qE "proxy_pass http://127\.0\.0\.1:808[0-9]" "$site_file"; then
            echo -e "   👉 កំពុងដំណើរការលើ Domain Site: ${CYAN}${filename}${NC}"

            # Backup original file
            cp "$site_file" "${site_file}.cache_bak"

            # Check if location /stream/ is already configured
            if grep -q "location /stream/" "$site_file"; then
                echo -e "   ℹ️ Domain ${filename} មាន location /stream/ រួចហើយ។ កំពុង Update..."
                # Remove existing location /stream/ block and replace with optimized slice cache
                python3 - << PYEOF
import re

with open("${site_file}", "r", encoding="utf-8") as f:
    content = f.read()

# Extract backend port from existing config
port_match = re.search(r'proxy_pass http://127\.0\.0\.1:(808\d+);', content)
port = port_match.group(1) if port_match else "8080"

# Remove old location /stream/ block
content = re.sub(r'location\s+/stream/\s*\{[^}]*\}', '', content, flags=re.DOTALL)

# Prepare slice cache block
slice_block = f"""
    # 🎥 Video Byte-Range Slice Cache (Anti-FloodWait & High-Speed Direct Streaming)
    location /stream/ {{
        slice 2m;

        proxy_pass http://127.0.0.1:{port};
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

        # Cache Status Header (HIT, MISS, BYPASS, EXPIRED)
        add_header X-Cache-Status \$upstream_cache_status always;
    }}
"""

# Insert before location / {
if "location / {" in content:
    content = content.replace("location / {", slice_block + "\n    location / {", 1)
    with open("${site_file}", "w", encoding="utf-8") as f:
        f.write(content)
PYEOF
            else
                # Insert slice cache block right before location / {
                python3 - << PYEOF
import re

with open("${site_file}", "r", encoding="utf-8") as f:
    content = f.read()

port_match = re.search(r'proxy_pass http://127\.0\.0\.1:(808\d+);', content)
port = port_match.group(1) if port_match else "8080"

slice_block = f"""
    # 🎥 Video Byte-Range Slice Cache (Anti-FloodWait & High-Speed Direct Streaming)
    location /stream/ {{
        slice 2m;

        proxy_pass http://127.0.0.1:{port};
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

        # Cache Status Header (HIT, MISS, BYPASS, EXPIRED)
        add_header X-Cache-Status \$upstream_cache_status always;
    }}
"""

if "location / {" in content:
    content = content.replace("location / {", slice_block + "\n    location / {", 1)
    with open("${site_file}", "w", encoding="utf-8") as f:
        f.write(content)
PYEOF
            fi

            PATCHED_COUNT=$((PATCHED_COUNT + 1))
        fi
    done
fi

# 6. Test Nginx Configuration and Reload
echo -e "${YELLOW}🔍 [4/4] កំពុងផ្ទៀងផ្ទាត់រចនាសម្ព័ន្ធ Nginx (nginx -t)...${NC}"
if nginx -t; then
    echo -e "${GREEN}✅ Nginx Syntax ត្រឹមត្រូវ ១០០%!${NC}"
    systemctl reload nginx
    echo -e "${GREEN}🔄 បាន Reload Nginx ដោយជោគជ័យ (Zero Downtime)!${NC}"
else
    echo -e "${RED}❌ Error: Nginx Syntax មានបញ្ហា! កំពុង Revert ទៅកាន់ Original File វិញ...${NC}"
    for bak in "$SITES_DIR"/*.cache_bak; do
        if [ -f "$bak" ]; then
            orig="${bak%.cache_bak}"
            mv "$bak" "$orig"
        fi
    done
    rm -f "$CONF_CACHE"
    systemctl reload nginx || true
    echo -e "${RED}⚠️ បានត្រឡប់មកកាន់សភាពដើមវិញដោយសុវត្ថិភាព។${NC}"
    exit 1
fi

# Cleanup backups if successful
rm -f "$SITES_DIR"/*.cache_bak 2>/dev/null || true

echo ""
echo -e "${CYAN}========================================================${NC}"
echo -e "${GREEN}🎉 ដំណើរការបើក NGINX SLICE CACHE បានជោគជ័យ ១០០%!${NC}"
echo -e "${CYAN}========================================================${NC}"
echo -e "📊 ព័ត៌មានលម្អិតនៃប្រព័ន្ធ Cache:"
echo -e "   • ទីតាំង Cache: ${CYAN}${CACHE_DIR}${NC}"
echo -e "   • ទំហំផ្ទុកអតិបរមា: ${GREEN}20GB SSD (Auto-clean LRU)${NC}"
echo -e "   • រយៈពេលរក្សាទុក: ${GREEN}14 ថ្ងៃ${NC}"
echo -e "   • ទំហំ Slice Chunk: ${GREEN}2MB ក្នុងមួយចំណែក${NC}"
echo -e "   • Cache Lock: ${GREEN}បើកដំណើរការ (ការពារ Spike Request ទៅ Telegram)${NC}"
echo -e "   • ចំនួន Domains បាន Patch: ${GREEN}${PATCHED_COUNT}${NC}"
echo ""
echo -e "${YELLOW}💡 របៀបសាកល្បង Test មើល Status Cache (HIT / MISS):${NC}"
echo -e "   1. លើកទី ១ (ទាញពី Telegram ដំបូង):"
echo -e "      ${CYAN}curl -I https://YOUR_DOMAIN/stream/YOUR_ID.mp4${NC}"
echo -e "      (Header នឹងចេញ: ${YELLOW}X-Cache-Status: MISS${NC})"
echo -e ""
echo -e "   2. លើកទី ២ (ទាញចេញពី SSD VPS ផ្ទាល់ មិនរំខាន Telegram ឡើយ):"
echo -e "      ${CYAN}curl -I https://YOUR_DOMAIN/stream/YOUR_ID.mp4${NC}"
echo -e "      (Header នឹងចេញ: ${GREEN}X-Cache-Status: HIT${NC} ⚡ លឿនបំផុត)"
echo ""
echo -e "🧹 ពាក្យបញ្ជាសម្រាប់មើលទំហំ Cache ឬលុប Cache បើចង់ Clear:"
echo -e "   • មើលទំហំ Cache:  ${CYAN}du -sh /var/cache/nginx/tgstream${NC}"
echo -e "   • សម្អាត Cache ទាំងអស់: ${CYAN}rm -rf /var/cache/nginx/tgstream/* && systemctl reload nginx${NC}"
echo -e "${CYAN}========================================================${NC}"
