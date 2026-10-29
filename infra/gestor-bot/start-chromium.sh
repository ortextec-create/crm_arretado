#!/bin/sh
for i in $(seq 1 30); do [ -e /tmp/.X11-unix/X99 ] && break; sleep 1; done
# trava de perfil deixada por queda anterior
rm -f /perfil/SingletonLock /perfil/SingletonSocket /perfil/SingletonCookie
exec chromium \
  --no-sandbox \
  --remote-debugging-port=9222 \
  --user-data-dir=/perfil \
  --load-extension=/extensao \
  --disable-extensions-except=/extensao \
  --no-first-run --no-default-browser-check \
  --start-maximized --window-size=1366,900 \
  --disable-dev-shm-usage \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows \
  --lang=pt-BR \
  https://gestordepedidos.ifood.com.br
