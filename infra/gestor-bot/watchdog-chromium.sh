#!/bin/sh
# Mata o Chromium se ele parar de responder (travado mas com o processo vivo) — o supervisord
# não enxerga isso e o autorestart só vale quando o processo morre. Ao matar, o supervisord sobe de novo.
# Consulta a porta de depuração (só loopback, dentro do container).
FALHAS=0
LIMITE=3          # falhas seguidas antes de reiniciar (3 x 30 s)
sleep 90          # dá tempo do Chromium subir
while true; do
  if python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1:9222/json/version', timeout=8).read()" >/dev/null 2>&1; then
    FALHAS=0
  else
    FALHAS=$((FALHAS + 1))
    echo "watchdog: Chromium sem resposta ($FALHAS/$LIMITE)"
    if [ "$FALHAS" -ge "$LIMITE" ]; then
      echo "watchdog: reiniciando Chromium"
      pkill -9 -f '/usr/lib/chromium/chromium' || pkill -9 chromium
      FALHAS=0
      sleep 90
    fi
  fi
  sleep 30
done
