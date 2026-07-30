# Sistema de Backup (Banco de Dados + Mídia) — Spec Genérica

> Template de especificação para implementação via Claude Code em qualquer aplicação Django +
> Postgres (ou adaptável a outro stack com banco relacional + storage de arquivos locais).
> Extraído e generalizado a partir de uma implementação real (app `manutencao/`, projeto
> Arretado CRM), incluindo os problemas encontrados de fato durante a implementação e a
> configuração — não é só teoria, é o que quebrou e como foi resolvido.
>
> Antes de usar: substitua os placeholders entre `<>` pelos valores reais do seu projeto
> (nome do app, campos de config, nomes de model) e ajuste os padrões arquiteturais
> (nome do mixin de auditoria, padrão de singleton, etc.) para os já estabelecidos no seu
> próprio `CLAUDE.md`/convenções de projeto, se existirem. Esta spec assume que o projeto já
> tem: autenticação por token, um padrão de "config singleton" (`Config.get()`), e algum
> sistema de notificação (WhatsApp/email/Slack) já abstraído atrás de uma função tipo
> `notificar()`. Se não tiver, adapte ou remova essas partes.

---

## O que é

Rotina automática de backup do **banco de dados relacional** e de qualquer pasta de **arquivos
enviados por usuário** (uploads, PDFs gerados, imagens), com envio para armazenamento externo
(via `rclone`, agnóstico de provedor) e alerta automático caso o backup não rode ou saia
corrompido.

Regra de ouro: **qualquer sistema que tenha um "ledger" ou tabela que seja fonte única da
verdade de algo financeiro/operacional (saldo, estoque, pedidos) tem essa criticidade elevada**
— perda de dados aí não é recuperável por reimportação ou reconstrução a partir de outro lugar.
Se seu projeto tem esse tipo de tabela, documente aqui quais são, para deixar claro o motivo
da criticidade.

Princípios (ajuste conforme as convenções do seu projeto):
- **Sem orquestrador pesado (Celery/Airflow) se o projeto já não usa um** — cron +
  management command é suficiente e mais simples de depurar para uma rotina diária.
- **Nada hardcoded** — caminhos, retenção, credenciais de destino (exceto segredos, que vão
  em variável de ambiente) configuráveis via um singleton de configuração.
- **Nunca lança exceção que derruba o processo principal** — se o envio externo falhar, o
  backup local já está garantido; se o alerta falhar, isso é só logado.
- **Quem faz o backup nunca é quem alerta** — separar os dois comandos (fazer vs. verificar)
  evita ruído (alerta de "backup ok" todo dia) e dá uma fonte única de verdade sobre o estado
  atual, independente de quando o backup rodou.

---

## App / Módulo

Criar um módulo dedicado (ex.: `manutencao/`, `ops/`, `infra/` — não misturar com um app de
domínio de negócio nem com o app de notificações, que deve ser específico do canal).

```
<app>/
├── models.py                          ← ConfiguracaoBackup (singleton) + TelefoneAlertaBackup (ou equivalente)
├── serializers.py
├── views.py                           ← ViewSets de config/telefones (GET/PATCH, CRUD) — opcional, útil se já existe um padrão de admin via API
├── urls.py
├── admin.py
└── management/
    └── commands/
        ├── fazer_backup.py            ← dump do banco + arquivos + envio externo + rotação
        └── verificar_backup.py        ← checagem de idade/integridade + alerta
```

---

## Modelo de configuração (singleton)

Sempre acessado via `ConfiguracaoBackup.get()` — nunca instanciado diretamente (mesmo padrão
de qualquer outro singleton já estabelecido no projeto).

| Campo | Tipo | Exemplo de padrão | Descrição |
|---|---|---|---|
| `ativo` | bool | `True` | Liga/desliga a rotina sem mexer no cron |
| `pasta_backup_db` | string | `/var/backups/<app>/db` | Onde salvar os dumps |
| `pasta_backup_arquivos` | string | `/var/backups/<app>/arquivos` | Onde salvar o tar.gz de uploads |
| `retencao_local_dias` | int | `14` | Quantos dias manter backup local |
| `retencao_remota_dias` | int | `90` | Quantos dias manter no storage externo |
| `rclone_remote` | string | `backup-remoto` | Nome do remote configurado no `rclone config` |
| `rclone_pasta_remota` | string | `<projeto>-backups` | Pasta/bucket raiz no storage externo |
| `envio_externo_ativo` | bool | `True` | Liga/desliga só o envio externo (mantém local mesmo assim) |
| `horas_limite_alerta` | int | `26` | Idade máxima aceitável do backup mais recente antes de alertar (dê folga sobre o intervalo do cron, não o valor exato) |
| `tamanho_minimo_kb` | int | `1` | Tamanho mínimo pra considerar o dump válido (detecta backup vazio/corrompido) |

**Credenciais do banco não entram nesse model** — já existem na config de conexão do
framework (ex.: `settings.DATABASES['default']` no Django); o comando de backup deve lê-las
de lá, nunca duplicá-las.

### Modelo de telefone/contato de alerta

Mesmo padrão de qualquer outra tabela de "destinatários internos de alerta" que já exista no
projeto (equipe interna, nunca cliente/usuário final):

| Campo | Descrição |
|---|---|
| `nome` | Identificação de quem recebe |
| `contato` | Telefone/e-mail/webhook, conforme o canal de notificação do projeto |
| `ativo` | Se `False`, não recebe mais (histórico preservado) |

---

## Comando 1 — `fazer_backup`

Roda todo o processo de backup. Preferir a linguagem/framework do projeto (não bash puro) —
assim toda a configuração vem do banco em vez de variáveis hardcoded num script `.sh`, e o
comando reaproveita a config de conexão do banco que o próprio framework já tem.

### Passo a passo

1. Carregar a config singleton. Se desativada, logar e sair sem erro.
2. Ler credenciais do banco da config de conexão do framework. A senha deve ser passada via
   variável de ambiente do subprocesso (ex.: `PGPASSWORD` para Postgres) — **nunca** na linha
   de comando (apareceria em `ps aux`/histórico de processos).
3. Criar as pastas de destino se não existirem.
4. Rodar o dump do banco (`pg_dump -Fc` para Postgres — formato customizado, comprimido,
   permite restore seletivo; equivalente para outros bancos) gerando um arquivo com timestamp.
5. Compactar a pasta de uploads/arquivos num `.tar.gz` com timestamp, usando a biblioteca
   padrão da linguagem (`tarfile` em Python) — **evitar depender do binário `tar` do sistema
   via subprocess**, para não introduzir uma dependência externa desnecessária num passo que
   a stdlib já resolve.
6. Rotação local: apagar arquivos mais antigos que a retenção configurada, nas duas pastas.
7. Se o envio externo estiver ativo **e** o binário `rclone` existir **e** o remote estiver
   de fato configurado (checar antes de tentar usar, não assumir):
   - Copiar os arquivos recém-criados para o remote/pasta configurados.
   - Rotação remota: apagar do remote o que passou da retenção remota.
   - Qualquer falha aqui deve ser **logada como warning, nunca lançar exceção** — o backup
     local já está seguro, o processo principal (cron) não deve falhar por causa disso.
8. Logar resumo final: tamanho dos arquivos gerados, se o envio externo funcionou ou não.
9. **Nunca disparar alerta/notificação daqui, nem em sucesso nem em falha** — separar
   claramente "fazer o backup" de "verificar se o backup está saudável" (comando 2). Isso
   evita notificação de "tudo ok" todo dia (ruído que as pessoas aprendem a ignorar, o que é
   pior que não ter alerta nenhum) e mantém uma fonte única de verdade sobre o estado atual.

### Tratamento de erro

Se o dump do banco falhar (código de retorno != 0), o comando deve:
- Logar a saída de erro completa do subprocesso.
- Sair com código de saída != 0 (ex.: `raise CommandError(...)` no Django), para aparecer
  destacado no log do cron.

---

## Comando 2 — `verificar_backup`

### Passo a passo

1. Carregar a config singleton.
2. Buscar o arquivo de dump mais recente na pasta configurada.
3. Se não existir nenhum → problema: "nenhum backup encontrado".
4. Se o mais recente tiver mais de `horas_limite_alerta` horas → problema: "backup
   desatualizado".
5. Se o tamanho do arquivo for menor que `tamanho_minimo_kb` → problema: "backup suspeito de
   vazio/corrompido".
6. Se houver problema:
   - Montar mensagem identificando qual checagem falhou + timestamp do backup mais recente
     encontrado (ou "nenhum", se for o caso).
   - Notificar cada destinatário ativo cadastrado.
   - Se não houver nenhum destinatário ativo cadastrado, logar warning (sem quebrar o comando
     — backup indetectável não deveria travar um cron, só ficar registrado no log).
7. Se estiver tudo certo, só logar sucesso — **sem notificação de confirmação diária**.

**Decisão consciente — sem controle de repetição/dedup no alerta:** diferente de outros
sistemas de alerta do projeto que possam ter (ex.: "não repetir esse alerta por N dias"),
aqui **o alerta deve repetir todo dia enquanto o backup estiver quebrado**, de propósito.
Backup quebrado é o único tipo de problema de um sistema que fica completamente invisível até
o dia em que se precisa dele — a insistência diária é a característica desejada, não ruído a
ser suprimido. Não adicionar controle de repetição "pra não incomodar".

---

## Cron

```bash
# Backup de madrugada (fora do horário de pico de uso)
0 3 * * * cd <caminho-do-projeto> && <venv>/bin/python manage.py fazer_backup >> <log> 2>&1

# Verificação algumas horas depois — dê folga suficiente pra alguém agir no mesmo dia útil
0 8 * * * cd <caminho-do-projeto> && <venv>/bin/python manage.py verificar_backup >> <log> 2>&1
```

---

## Envio externo via `rclone`

`rclone` é agnóstico de provedor (Google Drive, S3-compatíveis como Backblaze B2/Cloudflare
R2/Wasabi, Dropbox, SFTP, etc.) — a escolha do provedor é de negócio/custo, não técnica. Duas
famílias de autenticação, com implicações práticas diferentes para automação:

- **OAuth por navegador** (Google Drive, Dropbox, OneDrive): o passo `rclone authorize
  "<provider>"` abre um fluxo OAuth que **precisa de navegador**. Se o ambiente de produção é
  headless (VPS sem GUI, a maioria), esse passo tem que ser feito numa máquina com navegador e
  o token resultante copiado para o servidor — fácil de começar e esquecer de terminar (o
  remote fica com `client_id`/`client_secret` mas sem `token`, e o envio simplesmente nunca
  funciona, silenciosamente, até alguém notar).
- **API key simples** (Backblaze B2, S3-compatíveis em geral): autenticação por
  `account`/`key` (ou `access_key_id`/`secret_access_key`), configurável 100% via linha de
  comando, sem navegador:
  ```bash
  rclone config create <nome-do-remote> b2 account=<keyID> key=<applicationKey>
  ```
  **Recomendação**: prefira esse tipo de provedor quando o servidor de produção for headless
  — remove uma classe inteira de "configuração começada e nunca terminada".

### Verificar antes de confiar

Depois de criar o remote, sempre confirmar conectividade de verdade antes de considerar
concluído — não basta o `rclone config create` não ter dado erro:
```bash
rclone lsd <remote>:              # lista pastas/buckets visíveis com essa credencial
rclone copy <arquivo-teste> <remote>:<pasta>/
rclone lsl <remote>:<pasta>/      # confirma que chegou
```

### Cuidado: `rclone.conf` pode estar criptografado

O arquivo de config do rclone (`~/.config/rclone/rclone.conf`, ou `/root/.config/rclone/` se
rodando como root) pode ter uma senha de criptografia configurada
(`# Encrypted rclone configuration File` / `RCLONE_ENCRYPT_V0:` no topo do arquivo). Se isso
não for esperado, **qualquer comando `rclone` roda numa VPS sem terminal interativo vai falhar
silenciosamente** (tenta ler a senha do stdin, recebe EOF, e comandos que só checam a saída —
sem checar o código de retorno — podem interpretar isso como "nenhum remote configurado" em
vez de erro).

Antes de configurar um remote novo, sempre checar:
```bash
head -c 60 ~/.config/rclone/rclone.conf   # se aparecer "Encrypted rclone configuration File", está protegido
rclone listremotes                         # se pedir senha e travar, confirma o problema
```

Se estiver criptografado e a automação (cron) precisar rodar sem intervenção humana, duas
opções, nessa ordem de preferência:
1. **Remover a criptografia**, se o arquivo já tem permissão restrita a nível de sistema
   operacional (ex.: `600 root:root`) equivalente à proteção que a senha adicionaria — a
   senha nesse caso não agrega proteção real, só complica a automação. Extrair o conteúdo
   decriptado com `RCLONE_CONFIG_PASS=<senha> rclone config dump` (formato JSON) e reescrever
   o arquivo em texto plano (formato INI, uma seção `[nome-do-remote]` por remote) é mais
   confiável do que o menu interativo `rclone config` → `s` → `u`, que em algumas versões do
   rclone não completa de forma previsível quando alimentado via pipe/stdin não-interativo.
2. Manter a criptografia e passar `RCLONE_CONFIG_PASS` como variável de ambiente no próprio
   cron (mesmo nível de exposição de qualquer segredo em variável de ambiente de um cron job
   que já rode como root/usuário de sistema restrito).

---

## Restauração (procedimento manual — não automatizar)

**Não crie um management command de restauração.** Restauração é rara, arriscada e se
beneficia de ser um comando explícito digitado conscientemente no momento, não algo que possa
ser disparado por engano (um clique errado numa automação, um comando digitado no terminal
errado). Documente os comandos exatos aqui, prontos para copiar/colar quando precisar, mas
não os encapsule numa abstração que reduza a fricção de rodar.

**Banco de dados** (parar a aplicação antes de restaurar, religar depois — evita a aplicação
escrever no banco no meio da restauração):
```bash
<parar o serviço da aplicação>
PGPASSWORD='<senha>' pg_restore -h <host> -p <porta> -U <usuário> -d <nome-do-banco> \
  --clean --if-exists --no-owner <caminho-do-dump>
<religar o serviço da aplicação>
```
- `--clean --if-exists`: recria as tabelas do zero a partir do dump, em vez de tentar mesclar
  com o estado atual (evita erro de "já existe" e garante que o banco final é exatamente o
  snapshot, não uma mistura)
- `--no-owner`: evita erro se o "dono" das tabelas no dump divergir do usuário do banco no
  ambiente de restauração (comum ao restaurar em outro servidor)

**Arquivos/uploads:**
```bash
tar xzf <caminho-do-tar.gz> -C <diretório-raiz-do-projeto>/ --overwrite
```

**Se o backup local também não existir** (perda total do servidor), baixar do storage
externo primeiro:
```bash
rclone copy <remote>:<pasta-remota>/db/ <pasta-local-db>/
rclone copy <remote>:<pasta-remota>/arquivos/ <pasta-local-arquivos>/
```

**Para achar o backup certo:**
```bash
ls -t <pasta-local-db>/*.dump | head -1     # mais recente, local
rclone lsl <remote>:<pasta-remota>/db/       # no storage externo, com data de cada um
```

---

## O Que NÃO Fazer

- Não usar um orquestrador pesado (Celery/Airflow) se o projeto inteiro já roda em cron +
  management commands — não introduza uma dependência nova só para esta rotina.
- Não hardcodar caminhos, retenção ou destinatários de alerta no código — tudo vem da config
  singleton / tabela de destinatários.
- Não instanciar a config singleton diretamente — sempre pelo método `.get()`.
- Não guardar destinatários de alerta como texto livre com separador (`"111,222,333"`) —
  usar uma tabela própria, um registro por destinatário, com campo `ativo`.
- Não deixar os endpoints de configuração como acesso público — expõem caminhos de servidor
  e (indiretamente) a topologia do backup; exigir autenticação.
- Não colocar senha de banco na linha de comando do `pg_dump`/`pg_restore` — sempre variável
  de ambiente do subprocesso.
- Não disparar notificação de "backup ok" todo dia — só alertar em caso de problema.
- Não fazer o comando de backup também alertar — responsabilidade exclusiva do comando de
  verificação, separado.
- Não adicionar controle de repetição/dedup ao alerta de backup quebrado — a repetição diária
  enquanto durar o problema é intencional.
- Não usar o binário `tar` do sistema via subprocess para compactar arquivos — usar a
  biblioteca padrão da linguagem.
- Não incluir arquivos de segredo (`.env`, chaves de API, certificados privados) no backup —
  storage externo de backup não é lugar de segredo em texto plano; backup de segredos é
  procedimento manual separado, com ferramenta apropriada (cofre de segredos, gpg, etc.).
- Não criar um management command de restauração automatizada — ver seção "Restauração"
  acima.
- Não assumir que `rclone config create`/qualquer comando `rclone` funcionou só porque não
  deu erro — sempre confirmar com uma checagem de leitura de verdade (`rclone lsd`/`lsl`)
  antes de considerar a configuração concluída.

---

## Fora de escopo (sugestão de corte para uma primeira entrega)

- Tela de frontend para editar a configuração (usar admin do framework ou API direta).
- Criptografia dos próprios arquivos de backup antes do envio externo (`gpg`/`age`) — avaliar
  separadamente conforme sensibilidade dos dados e política de segurança do projeto.
- Restauração automatizada via comando — ver "O Que NÃO Fazer".
- Backup incremental/contínuo (ex.: WAL archiving do PostgreSQL) — avaliar apenas se o volume
  de dados/mudanças justificar; um dump diário completo é suficiente para a maioria dos casos.
- Múltiplos destinos de armazenamento externo simultâneos.
