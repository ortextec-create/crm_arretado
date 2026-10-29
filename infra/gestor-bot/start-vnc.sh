#!/bin/sh
# Senha vem de VNC_PASSWORD (variável de ambiente; nunca no repo).
set -e
[ -n "$VNC_PASSWORD" ] || { echo "VNC_PASSWORD não definida" >&2; exit 1; }
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASSWORD" /root/.vnc/passwd >/dev/null
# aguarda o Xvfb
for i in $(seq 1 30); do [ -e /tmp/.X11-unix/X99 ] && break; sleep 1; done
exec x11vnc -display :99 -rfbauth /root/.vnc/passwd -rfbport 5900 -localhost -forever -shared -noxdamage
