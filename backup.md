# Sistema de Backup (Banco de Dados + Mídia)

> Documento de referência/spec para implementação via Claude Code na VPS.
> Para padrões técnicos gerais, ver `CLAUDE.md`. Segue o mesmo formato de `FRETE.md`/`CONTRATO.md`/`FINANCEIRO.md`.
> Status: **implementado** (fases 1-5, commit `0cf1479`) — envio externo configurado com
> **Backblaze B2** em 30/jul/2026 (não Google Drive; ver "Envio externo" abaixo).
> Revisado em jul/2026 contra o `CLAUDE.md` atual (pós-Estoque fases 1-8 e Financeiro fases 0-7):
> alinhado aos padrões consolidados de `TelefoneAlerta*`, autenticação em configs singleton e auditoria.

---

## O que é

Rotina automática de backup do **banco de dados PostgreSQL** e da pasta `media/` (fotos de
produtos, PDFs de orçamentos/contratos, imagens de inspiração, arquivos de notas fiscais
importadas), com envio para armazenamento externo (Google Drive via `rclone`) e alerta
automático via WhatsApp caso o backup não rode ou saia corrompido.

A criticidade cresceu com os módulos recentes: o banco agora guarda **dois ledgers imutáveis**
(`estoque.MovimentoEstoque` e `financeiro.MovimentoFinanceiro`) que são fonte única da verdade
de saldo físico e financeiro — perda de dados aqui não é recuperável por reimportação.

Segue os mesmos princípios do resto do projeto:
- **Sem Celery** — tudo via `management commands` + `cron`, igual a `lembrar_aniversarios`,
  `alertar_eventos`, `alertar_estoque_baixo`, `gerar_contas_recorrentes`.
- **Resale-first** — nenhum caminho, retenção ou telefone hardcoded; tudo configurável via
  singleton (`ConfiguracaoBackup`), mesmo padrão de `ConfiguracaoEntrega`, `ConfiguracaoEstoque`,
  `ConfiguracaoFinanceira`.
- **Nunca lança exceção que derruba o processo principal** — se o envio externo falhar, o
  backup local já está garantido; se o alerta falhar, isso é só logado.

---

## App

Criar um novo app Django: **`manutencao/`**

Não faz sentido colocar isso em `notificacoes/` (que é especificamente sobre o canal WhatsApp)
nem em nenhum app de canal de venda. `manutencao/` é o lugar certo para rotinas operacionais
de infraestrutura que possam crescer no futuro (ex.: limpeza de logs, verificação de saúde de
integrações — ver também a pendência de observabilidade nº 5 do `CLAUDE.md`).

```
manutencao/
├── models.py                          ← ConfiguracaoBackup (singleton) + TelefoneAlertaBackup
├── serializers.py                     ← ConfiguracaoBackupSerializer + TelefoneAlertaBackupSerializer
├── views.py                           ← ConfiguracaoBackupViewSet (GET/PATCH) + TelefoneAlertaBackupViewSet (CRUD)
├── urls.py                            ← router registrado em config/urls.py como /api/v1/manutencao/
├── admin.py                           ← registrar os dois models no Django Admin
└── management/
    └── commands/
        ├── fazer_backup.py            ← dump do banco + media + envio externo + rotação
        └── verificar_backup.py        ← checagem de idade/integridade + alerta WhatsApp
```

Adicionar `'manutencao'` em `INSTALLED_APPS` (`config/settings.py`).

---

## Modelos de dados

### `manutencao.ConfiguracaoBackup` (singleton)

Sempre acessado via `ConfiguracaoBackup.get()` — nunca instanciado diretamente (mesmo padrão
de `ConfiguracaoEstoque.get()` / `ConfiguracaoFinanceira.get()`).

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `ativo` | BooleanField | `True` | Liga/desliga a rotina sem precisar mexer no cron |
| `pasta_backup_db` | CharField | `/var/backups/arretado/db` | Onde salvar os `.dump` |
| `pasta_backup_media` | CharField | `/var/backups/arretado/media` | Onde salvar os `.tar.gz` de mídia |
| `retencao_local_dias` | PositiveIntegerField | `14` | Quantos dias manter backup local |
| `retencao_remota_dias` | PositiveIntegerField | `90` | Quantos dias manter no Google Drive |
| `rclone_remote` | CharField | `backup-remoto` | Nome do remote configurado no `rclone config` |
| `rclone_pasta_remota` | CharField | `arretado-backups` | Pasta raiz dentro do Google Drive |
| `envio_externo_ativo` | BooleanField | `True` | Liga/desliga só o envio pro Drive (mantém local mesmo assim) |
| `horas_limite_alerta` | PositiveIntegerField | `26` | Idade máxima aceitável do backup mais recente antes de alertar |
| `tamanho_minimo_kb` | PositiveIntegerField | `1` | Tamanho mínimo pra considerar o `.dump` válido (detecta backup vazio/corrompido) |
| `atualizado_em` | DateTimeField (auto_now) | — | — |

```python
class ConfiguracaoBackup(models.Model):
    # campos acima...

    class Meta:
        verbose_name = 'Configuração de Backup'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

**Credenciais do banco** (`DB_NAME`, `DB_USER`, etc.) **não** entram nesse model — já existem
em `config/settings.py` via `.env` (`DATABASES['default']`), e o comando `fazer_backup` deve
lê-las de lá (`django.conf.settings.DATABASES['default']`), nunca duplicá-las.

### `manutencao.TelefoneAlertaBackup`

Mesmo padrão consolidado de `TelefoneAlertaEvento` / `TelefoneAlertaEstoque` /
`TelefoneAlertaFinanceiro` — telefones internos da equipe que recebem o alerta de falha
(nunca cliente/fornecedor). **Não** usar TextField com vírgulas na `ConfiguracaoBackup`
(padrão descartado em revisão de jul/2026 para manter consistência com os outros módulos).

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | CharField | Identificação de quem recebe (ex.: "Fobs", "Cozinha") |
| `telefone` | CharField | Formato internacional sem `+` (ex.: `5586999999999`) |
| `ativo` | BooleanField | Se `False`, não recebe mais (histórico preservado) |

### Endpoints

```
GET/PATCH            /api/v1/manutencao/configuracao-backup/1/       ← exige login
GET/POST             /api/v1/manutencao/telefones-alerta/            ← exige login
GET/PATCH/DELETE     /api/v1/manutencao/telefones-alerta/{id}/       ← exige login · DELETE audita registro_excluido
```

**Autenticação e auditoria (padrão pós-Auditoria, obrigatório):**
- Todas as rotas exigem login (`IsAuthenticated`) — mesmo padrão adotado para
  `ConfiguracaoWhatsApp` (que exige login até no GET) e `ConfiguracaoIA`. A config de backup
  expõe caminhos do servidor; não pode ficar `AllowAny`.
- `PATCH` na `ConfiguracaoBackup` audita `config_backup_alterada` via
  `auditoria/utils.py::registrar()` — mesmo padrão de `config_ia_alterada`.
- `DELETE` de `TelefoneAlertaBackup` usa o `AuditoriaDestroyMixin` genérico.

Sem tela de frontend nesta primeira entrega (ver "Fora de escopo") — configurar via Django
Admin ou API.

---

## Comando 1 — `python manage.py fazer_backup`

Roda todo o processo de backup. Deve ser **Python puro via Django** (não bash), usando
`subprocess` apenas para chamar `pg_dump` e `rclone` — assim toda a configuração vem do
banco (`ConfiguracaoBackup.get()`) em vez de variáveis hardcoded num script `.sh`.

### Passo a passo

1. Carregar `cfg = ConfiguracaoBackup.get()`. Se `cfg.ativo == False`, logar e sair sem erro.
2. Ler credenciais do banco de `settings.DATABASES['default']` (`NAME`, `USER`, `HOST`, `PORT`).
   A senha deve ser passada via variável de ambiente `PGPASSWORD` no `subprocess.run(..., env=...)`
   — **nunca** na linha de comando (apareceria em `ps aux`).
3. Criar as pastas de `cfg.pasta_backup_db` / `cfg.pasta_backup_media` se não existirem
   (`Path.mkdir(parents=True, exist_ok=True)`).
4. Rodar `pg_dump -Fc` gerando `crm_db_{timestamp}.dump` em `cfg.pasta_backup_db`.
5. Compactar `settings.MEDIA_ROOT` em `media_{timestamp}.tar.gz` dentro de
   `cfg.pasta_backup_media`, usando o módulo `tarfile` da biblioteca padrão do Python —
   não usar subprocess/`shutil.which('tar')`. Isso cobre fotos de produtos, PDFs gerados,
   imagens de inspiração e os arquivos de nota fiscal importados pelo Estoque.
6. Rotação local: apagar arquivos mais antigos que `cfg.retencao_local_dias` em ambas as pastas.
7. Se `cfg.envio_externo_ativo` e o binário `rclone` existir (`shutil.which('rclone')`) e o
   remote `cfg.rclone_remote` estiver configurado (`rclone listremotes`):
   - `rclone copy` do `.dump` e do `.tar.gz` recém-criados para
     `{rclone_remote}:{rclone_pasta_remota}/db/` e `.../media/`.
   - Rotação remota: `rclone delete --min-age {retencao_remota_dias}d` nas duas pastas.
   - Qualquer falha aqui deve ser **logada como warning**, nunca lançar exceção — o backup
     local já está seguro.
8. Logar resumo final: tamanho dos arquivos gerados, se o envio externo funcionou ou não.
9. **Nunca chamar `notificar()` daqui, nem em sucesso nem em falha** — quem diagnostica e
   alerta é o `verificar_backup`, rodando depois, separadamente. Fonte única de verdade sobre
   "o backup está ok ou não", e evita WhatsApp de "backup ok" todo dia (ruído).

### Tratamento de erro

Se `pg_dump` falhar (retorno != 0), o comando deve:
- Logar o `stderr` completo.
- Sair com código de saída != 0 (`raise CommandError(...)`), para aparecer no log do cron.

---

## Comando 2 — `python manage.py verificar_backup`

Protótipo funcional já existe (feito na sessão de jul/2026 no Claude Web) — adaptar para ler
configuração de `ConfiguracaoBackup.get()` e telefones de `TelefoneAlertaBackup` em vez de
argumentos de linha de comando / `.env`.

### Passo a passo

1. Carregar `cfg = ConfiguracaoBackup.get()`.
2. Buscar o arquivo `crm_db_*.dump` mais recente em `cfg.pasta_backup_db`.
3. Se não existir nenhum → problema: "nenhum backup encontrado".
4. Se o mais recente tiver mais de `cfg.horas_limite_alerta` horas → problema: "backup
   desatualizado".
5. Se o tamanho do arquivo for menor que `cfg.tamanho_minimo_kb` → problema: "backup
   suspeito de vazio/corrompido".
6. Se houver problema:
   - Montar mensagem de alerta (identificando qual das 3 checagens falhou + timestamp).
   - Para cada `TelefoneAlertaBackup` com `ativo=True`, chamar
     `notificacoes.servico.notificar(telefone, mensagem, tipo='backup')`.
   - Se não houver telefone ativo cadastrado, logar warning (sem quebrar o comando).
7. Se estiver tudo certo, só logar sucesso — sem WhatsApp de confirmação diária.

**Decisão consciente — sem `AlertaBackupEnviado`:** diferente de `AlertaEventoEnviado` /
`AlertaEstoqueEnviado` / `AlertaFinanceiroEnviado`, aqui **não** há controle de repetição —
enquanto o backup estiver quebrado, o alerta repete todo dia de propósito. Backup quebrado é
o único problema do sistema que fica invisível até o dia em que se precisa dele; a
insistência diária é desejada, não ruído. Não "corrigir" isso adicionando dedup.

### Alteração necessária em `notificacoes/models.py`

Adicionar `('backup', 'Alerta de Backup')` em `HistoricoMensagem.TIPO_CHOICES` — nota: a
lista atual já cresceu além do snapshot original (inclui `orcamento`, `alerta_vencimento`,
etc.); apenas **acrescentar** o novo choice, sem tocar nos existentes. Rodar
`makemigrations notificacoes` + `migrate` (deixar o Django gerar o número da migration a
partir do estado real do banco na VPS — não fabricar o arquivo manualmente).

---

## Cron

```bash
# Backup às 03:00 todo dia
0 3 * * * cd /var/www/crm_arretado && venv/bin/python manage.py fazer_backup >> /var/log/arretado/backup.log 2>&1

# Verificação às 08:00 (folga de 5h sobre o backup, e sobra o dia todo pra alguém agir)
0 8 * * * cd /var/www/crm_arretado && venv/bin/python manage.py verificar_backup >> /var/log/arretado/verificar_backup.log 2>&1
```

Criar `/var/log/arretado/` se ainda não existir (`mkdir -p /var/log/arretado`).

---

## Configuração externa necessária (feita manualmente, fora do código)

**Decisão tomada em 30/jul/2026: Backblaze B2, não Google Drive.** Um remote `Arretado` tipo
`drive` chegou a ser criado (client_id/client_secret), mas ficou sem token — o passo
`rclone authorize "drive"` exige navegador, e a VPS é headless. B2 usa autenticação por
`account`/`key` (API key simples), sem esse problema — por isso a troca.

1. Instalar `rclone` na VPS: `curl https://rclone.org/install.sh | sudo bash`
2. Criar conta na Backblaze (https://www.backblaze.com/), criar um bucket (ex.:
   `arretado-backups`) e uma Application Key restrita a esse bucket (gera `keyID` +
   `applicationKey`).
3. Criar o remote com o **mesmo nome** salvo em `ConfiguracaoBackup.rclone_remote` (padrão:
   `backup-remoto`) — não precisa de navegador nem senha interativa:
   ```bash
   rclone config create backup-remoto b2 account=<keyID> key=<applicationKey>
   ```
4. Cadastrar os `TelefoneAlertaBackup` da equipe (Django Admin ou API) e revisar a
   `ConfiguracaoBackup` (confirmar que `rclone_remote`/`rclone_pasta_remota` batem com o
   nome do bucket criado no passo 2).

**Nota sobre `rclone.conf`:** por padrão o arquivo (`/root/.config/rclone/rclone.conf`) não é
criptografado. Se em algum momento ele estiver protegido por senha (`RCLONE_ENCRYPT_V0` no
topo do arquivo), o cron não vai conseguir ler as credenciais sem essa senha disponível no
ambiente — como o arquivo já é `600 root:root` (mesmo nível de proteção do crontab, que
também é `600`), a senha extra não agrega proteção real e só complica o cron. Preferir manter
sem criptografia; se precisar remover uma senha existente, use `rclone config dump` (com
`RCLONE_CONFIG_PASS` no ambiente) pra extrair o conteúdo decriptado e reescrever o arquivo em
texto plano, em vez do menu interativo `rclone config` → `s` → `u` (nesta versão do rclone,
1.60.1, esse fluxo interativo via stdin não completa de forma confiável em modo não-interativo).

---

## Restauração (procedimento manual)

Não existe (nem deve existir) um management command `restaurar_backup` — ver "O Que NÃO
Fazer". Restauração é rara e arriscada o bastante para exigir um comando explícito digitado
na hora, não algo automatizável que alguém dispare sem querer.

**Banco de dados** (parar a aplicação antes, religar depois):
```bash
sudo systemctl stop arretado
PGPASSWORD='<senha do DB_USER>' pg_restore -h <DB_HOST> -p <DB_PORT> -U <DB_USER> -d <DB_NAME> \
  --clean --if-exists --no-owner /var/backups/arretado/db/crm_db_TIMESTAMP.dump
sudo systemctl start arretado
```
- `--clean --if-exists` recria as tabelas do zero a partir do dump (evita erro de "já existe"
  e garante que o banco fica igual ao snapshot, não uma mistura do estado atual com o restaurado)
- `--no-owner` evita erro se o owner do banco divergir entre ambientes
- Credenciais vêm de `settings.DATABASES['default']` (mesmas usadas por `fazer_backup.py`)

**Mídia:**
```bash
tar xzf /var/backups/arretado/media/media_TIMESTAMP.tar.gz -C <BASE_DIR>/ --overwrite
```
O `.tar.gz` já contém uma pasta `media/` dentro (`tarfile.add(..., arcname='media')` em
`fazer_backup.py`), então extrair na raiz do projeto recria `MEDIA_ROOT` corretamente.

**Se o backup local também tiver sumido** (ex.: perda total da VPS), baixar do B2 primeiro:
```bash
rclone copy backup-remoto:<rclone_pasta_remota>/db/ /var/backups/arretado/db/
rclone copy backup-remoto:<rclone_pasta_remota>/media/ /var/backups/arretado/media/
```

**Achar o `TIMESTAMP` certo:**
```bash
ls -t /var/backups/arretado/db/*.dump | head -1      # local, mais recente
rclone lsl backup-remoto:<rclone_pasta_remota>/db/     # no B2, com data de cada um
```

---

## Fases de Implementação

### Fase 1 — App e models
- Criar app `manutencao/`, registrar em `INSTALLED_APPS`.
- `ConfiguracaoBackup` + `TelefoneAlertaBackup` + migration + `admin.py`.
- Serializers + ViewSets (com `IsAuthenticated` e auditoria conforme seção de endpoints) +
  rota em `config/urls.py`.

### Fase 2 — Comando `fazer_backup`
- Implementar dump do banco + tar de mídia (`tarfile`) + rotação local.
- Testar manualmente na VPS: `python manage.py fazer_backup`, conferir arquivos gerados.

### Fase 3 — Envio externo (rclone)
- Implementar a chamada ao `rclone` dentro do mesmo comando (`subprocess`, com tratamento de
  erro que não derruba o comando).
- Configurar `rclone` na VPS (passo manual) e testar o envio de ponta a ponta.

### Fase 4 — Comando `verificar_backup` + alerta
- Adaptar o protótipo para ler de `ConfiguracaoBackup` / `TelefoneAlertaBackup`.
- Adicionar `'backup'` em `HistoricoMensagem.TIPO_CHOICES` + migration.
- Testar cenário de falha forçada (ex.: `cfg.horas_limite_alerta = 0` temporariamente) para
  confirmar que o WhatsApp chega.

### Fase 5 — Cron
- Adicionar as duas linhas de cron na VPS.
- Rodar por pelo menos 2-3 dias e conferir os logs antes de considerar concluído.

---

## O Que NÃO Fazer

- Não usar Celery — comando + cron, como todo o resto do projeto.
- Não hardcodar caminhos, retenção ou telefones no código — configuração vem de
  `ConfiguracaoBackup.get()`, telefones de `TelefoneAlertaBackup`.
- Não instanciar `ConfiguracaoBackup()` diretamente — sempre `.get()`.
- Não guardar telefones como TextField com vírgulas — usar o model `TelefoneAlertaBackup`
  (padrão `TelefoneAlertaEvento`/`TelefoneAlertaEstoque`/`TelefoneAlertaFinanceiro`).
- Não deixar os endpoints de `manutencao/` como `AllowAny` — exigem login, e alterações de
  config são auditadas (`config_backup_alterada`).
- Não chamar `zapi_client` diretamente — sempre `notificacoes.servico.notificar()`.
- Não colocar a senha do banco na linha de comando do `pg_dump` (usar `PGPASSWORD` via `env=`
  no `subprocess`).
- Não disparar WhatsApp de "backup ok" todo dia — só alertar em caso de problema.
- Não fazer o `fazer_backup` chamar `notificar()` — responsabilidade exclusiva do
  `verificar_backup`.
- Não adicionar dedup de alerta (`AlertaBackupEnviado`) — repetição diária enquanto quebrado
  é decisão consciente (ver Comando 2).
- Não usar subprocess/`tar` do sistema para compactar a mídia — usar `tarfile` (stdlib).
- Não incluir o `.env` no backup — contém chaves (Z-API, futura `ANTHROPIC_API_KEY`); o Drive
  não é lugar de segredo em texto plano. Guardar cópia do `.env` é procedimento manual
  separado, fora deste sistema.

---

## Fora de escopo (não implementar nesta rodada)

- Tela de frontend para editar `ConfiguracaoBackup`/`TelefoneAlertaBackup` (por ora, Django
  Admin ou API direta). Se decidirem construir, seguir o padrão da seção "Alertas de Evento"
  em `Configuracoes.jsx`.
- Criptografia dos arquivos de backup antes do envio ao Drive (`gpg`/`age`).
- Backup do `.env` e de arquivos de configuração do servidor (Nginx, systemd) — procedimento
  manual separado.
- Restauração automatizada via comando (`restaurar_backup`) — restauração é manual
  (`pg_restore` direto, documentado).
- Backup incremental/contínuo (WAL archiving do PostgreSQL) — a rotina diária via `pg_dump` é
  suficiente para o volume atual.
- Múltiplos destinos de armazenamento externo simultâneos.
