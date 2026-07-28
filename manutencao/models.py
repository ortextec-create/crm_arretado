from django.db import models


class ConfiguracaoBackup(models.Model):
    """Singleton — sempre acessado via ConfiguracaoBackup.get()."""

    ativo = models.BooleanField(default=True)
    pasta_backup_db = models.CharField(max_length=255, default='/var/backups/arretado/db')
    pasta_backup_media = models.CharField(max_length=255, default='/var/backups/arretado/media')
    retencao_local_dias = models.PositiveIntegerField(default=14)
    retencao_remota_dias = models.PositiveIntegerField(default=90)
    rclone_remote = models.CharField(max_length=100, default='backup-remoto')
    rclone_pasta_remota = models.CharField(max_length=255, default='arretado-backups')
    envio_externo_ativo = models.BooleanField(default=True)
    horas_limite_alerta = models.PositiveIntegerField(default=26)
    tamanho_minimo_kb = models.PositiveIntegerField(default=1)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Backup'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Configuração de Backup'


class TelefoneAlertaBackup(models.Model):
    """Telefones internos da equipe que recebem alerta de falha de backup (não é cliente/fornecedor)."""

    numero = models.CharField(max_length=30)
    nome = models.CharField('Nome/label (opcional)', max_length=100, blank=True, default='')
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Telefone de Alerta de Backup'
        verbose_name_plural = 'Telefones de Alerta de Backup'
        ordering = ['nome', 'numero']

    def __str__(self):
        return f'{self.nome} ({self.numero})' if self.nome else self.numero
