#!/bin/bash
# ========================================================
# Script: manage_clients.sh
# Purpose: List, monitor, or remove clients on the VPS
# ========================================================

ACTION=$1

show_help() {
    echo "========================================================"
    echo "👥 ឧបករណ៍គ្រប់គ្រងអតិថិជន (Client Manager)"
    echo "========================================================"
    echo "ការប្រើប្រាស់:"
    echo "  bash manage_clients.sh list             # មើលបញ្ជីភ្ញៀវទាំងអស់"
    echo "  bash manage_clients.sh status <name>    # មើល Status របស់ភ្ញៀវ"
    echo "  bash manage_clients.sh restart <name>   # Restart Bot របស់ភ្ញៀវ"
    echo "  bash manage_clients.sh remove <name>    # លុបភ្ញៀវចេញពី VPS"
    echo "========================================================"
}

if [ -z "$ACTION" ] || [ "$ACTION" == "list" ]; then
    echo "========================================================"
    echo "📋 បញ្ជីអតិថិជនដែលកំពុងរត់លើ VPS នេះ:"
    echo "========================================================"
    echo "[1] Server មេ (Default):"
    systemctl is-active tgstream &>/dev/null && echo "    ⚡ Status: ✅ RUNNING" || echo "    ⚡ Status: ❌ STOPPED"
    grep -E "FQDN|PORT" /root/tg-stream-player/.env 2>/dev/null | sed 's/^/    /' || true
    echo ""

    COUNT=2
    if [ -d "/root/tg-clients" ]; then
        for dir in /root/tg-clients/*; do
            if [ -d "$dir" ]; then
                CID=$(basename "$dir")
                echo "[$COUNT] អតិថិជន: $CID"
                systemctl is-active "tgstream-${CID}" &>/dev/null && echo "    ⚡ Status: ✅ RUNNING" || echo "    ⚡ Status: ❌ STOPPED"
                grep -E "FQDN|PORT" "$dir/.env" 2>/dev/null | sed 's/^/    /' || true
                echo ""
                COUNT=$((COUNT + 1))
            fi
        done
    fi
    exit 0
fi

CLIENT_NAME=$2

if [ -z "$CLIENT_NAME" ]; then
    echo "❌ សូមបញ្ជាក់ឈ្មោះសម្គាល់អតិថិជន (ឧ. bash manage_clients.sh restart client2)"
    exit 1
fi

SERVICE_NAME="tgstream-${CLIENT_NAME}"

case "$ACTION" in
    status)
        systemctl status "$SERVICE_NAME"
        ;;
    restart)
        systemctl restart "$SERVICE_NAME"
        echo "✅ បាន Restart សេវាកម្ម $SERVICE_NAME រួចរាល់!"
        ;;
    remove)
        read -p "⚠️ តើបងពិតជាចង់លុបអតិថិជន $CLIENT_NAME មែនទេ? (y/n): " CONFIRM
        if [ "$CONFIRM" == "y" ]; then
            systemctl stop "$SERVICE_NAME" || true
            systemctl disable "$SERVICE_NAME" || true
            rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
            systemctl daemon-reload
            
            # Remove Nginx
            DOMAIN=$(grep "FQDN=" "/root/tg-clients/${CLIENT_NAME}/.env" | cut -d'=' -f2 | sed 's|https://||' | sed 's|http://||')
            if [ -n "$DOMAIN" ]; then
                rm -f "/etc/nginx/sites-enabled/${DOMAIN}"
                rm -f "/etc/nginx/sites-available/${DOMAIN}"
                nginx -t && systemctl reload nginx || true
            fi

            rm -rf "/root/tg-clients/${CLIENT_NAME}"
            echo "🗑️ បានលុបអតិថិជន $CLIENT_NAME ចេញពីប្រព័ន្ធរួចរាល់!"
        else
            echo "បានបោះបង់។"
        fi
        ;;
    *)
        show_help
        ;;
esac
