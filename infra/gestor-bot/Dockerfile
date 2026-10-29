FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Fortaleza \
    LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:pt \
    LC_ALL=pt_BR.UTF-8 \
    DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium xvfb x11vnc novnc websockify supervisor \
      locales tzdata fonts-liberation fonts-noto-color-emoji ca-certificates dbus-x11 \
    && sed -i 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen && locale-gen \
    && ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY supervisord.conf /etc/supervisor/conf.d/gestor-bot.conf
COPY start-vnc.sh start-chromium.sh watchdog-chromium.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-vnc.sh /usr/local/bin/start-chromium.sh /usr/local/bin/watchdog-chromium.sh

HEALTHCHECK --interval=60s --timeout=15s --start-period=120s --retries=3 \
  CMD python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1:9222/json/version', timeout=8).read()" || exit 1

VOLUME /perfil
EXPOSE 6080
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
