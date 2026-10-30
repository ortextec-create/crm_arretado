# gestor-bot — Chromium autônomo com a extensão iFood Chat (PoC)

Roda a `extensao-ifood-chat/` num Chromium dentro de Docker na VPS (Xvfb + x11vnc + noVNC),
sem PC na loja. Não toca no CRM nem na extensão. O noVNC escuta **só em 127.0.0.1:6080**.

> Usa Chromium (Debian), não o Google Chrome: o Chrome oficial ignora `--load-extension`.

## Subir

```bash
cd /var/www/crm_arretado/infra/gestor-bot
cp .env.example .env && nano .env      # defina VNC_PASSWORD (o .env é ignorado pelo git)
docker compose up -d --build
```

Limite de memória: 1,8 GB (era 1,2 GB; Chromium sofreu OOM-kill em 30/out/2026 e a página mostrou "Something went wrong while displaying this webpage") (`mem_limit` no compose). O supervisor reinicia o Chromium se cair;
`restart: unless-stopped` reinicia o container.

## Autorrecuperação e alerta

- `watchdog-chromium.sh` (supervisord) consulta `127.0.0.1:9222` (porta de depuração, só dentro do
  container) a cada 30 s e mata o Chromium após 3 falhas seguidas; o supervisord sobe de novo.
- `HEALTHCHECK` do Dockerfile usa a mesma porta (`docker ps` mostra healthy/unhealthy).
- O alerta de extensão offline vive no CRM: cron `*/5 * * * * manage.py verificar_extensao`
  (WhatsApp para `TelefoneAlertaAtendimento`, API `/api/v1/atendimento/telefones-alerta/`).
- O watchdog não cobre extensão parada/iFood deslogado com o Chromium vivo — só o alerta.

## Abrir o noVNC (túnel SSH)

No seu PC:

```bash
ssh -L 6080:127.0.0.1:6080 root@2.25.142.171
```

Depois abra http://127.0.0.1:6080/vnc.html e informe a `VNC_PASSWORD`.

## Primeiro login e configuração da extensão

1. No noVNC, faça login no Gestor de Pedidos (https://gestordepedidos.ifood.com.br). O perfil
   fica no volume `gestor-bot-perfil`, então a sessão sobrevive a restarts.
2. Clique no ícone da extensão "Ortex – iFood Chat" (puzzle na barra) → informe a URL do CRM
   (`https://arretado.ortex.solutions`) e o token (`python manage.py gerar_token_extensao
   --empresa <id> --nome "gestor-bot"`).
3. Designe a aba do Gestor como aba da extensão, como no fluxo normal (ver
   `extensao-ifood-chat/README.md`). Confira em Atendimento → Extensão se aparece online.

Mantenha `chat_ativo` e o modo seguro como estão até validar; esta PoC não altera nada disso.

## Atualizar a extensão

```bash
cd /var/www/crm_arretado && git pull origin main
docker compose -f infra/gestor-bot/docker-compose.yml restart
```

(a pasta é bind mount read-only; o restart recarrega o Chromium com a versão nova.)

## Logs

```bash
docker compose -f infra/gestor-bot/docker-compose.yml logs -f
docker exec gestor-bot supervisorctl status
docker exec gestor-bot supervisorctl restart chromium
```

## Parar / apagar

```bash
docker compose down            # mantém o perfil (login)
docker compose down -v         # apaga também o perfil
```

## Observações

- `--no-sandbox` é necessário porque o Chromium roda como root no container; o container não
  expõe nada além do loopback.
- Nenhuma porta nova é aberta para a internet. Confira com `ss -tlnp | grep 6080`
  (deve mostrar `127.0.0.1:6080`).
- Resolução fixa 1366x900 (Xvfb).
