#!/bin/bash
# Установка LaunchAgent для TON Monitor

set -e

PLIST_SRC="/Users/micronova/.openclaw/workspace/openclaw-ton-skill/com.openclaw.ton-monitor.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.openclaw.ton-monitor.plist"
LOG_DIR="$HOME/Library/Logs"

# Проверяем что пароль указан
if [ -z "$WALLET_PASSWORD" ]; then
    echo "❌ Укажите пароль в переменной WALLET_PASSWORD"
    echo "   Пример: WALLET_PASSWORD=xxx ./install-launchagent.sh"
    exit 1
fi

# Создаём директорию для логов
mkdir -p "$LOG_DIR"

# Создаём plist с паролем
cat > "$PLIST_DST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.ton-monitor</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/micronova/.openclaw/workspace/openclaw-ton-skill/scripts/monitor.py</string>
        <string>start</string>
    </array>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/Users/micronova/Library/Python/3.9/bin</string>
        <key>WALLET_PASSWORD</key>
        <string>${WALLET_PASSWORD}</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/ton-monitor.log</string>
    
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/ton-monitor.log</string>
    
    <key>WorkingDirectory</key>
    <string>/Users/micronova/.openclaw/workspace/openclaw-ton-skill</string>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

# Права
chmod 600 "$PLIST_DST"

echo "✅ LaunchAgent установлен: $PLIST_DST"
echo ""
echo "Команды:"
echo "  launchctl load $PLIST_DST     # Запустить"
echo "  launchctl unload $PLIST_DST   # Остановить"
echo "  tail -f $LOG_DIR/ton-monitor.log  # Логи"
