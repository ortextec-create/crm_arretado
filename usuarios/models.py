import secrets

from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


def gerar_token():
    """Token de sessão — 64 chars hex (256 bits), regenerado a cada login."""
    return secrets.token_hex(32)


ROLE_CHOICES = [
    ('admin',     'Administrador'),
    ('gerente',   'Gerente'),
    ('atendente', 'Atendente'),
]

PERMS_DEFAULT = {
    'admin': {
        'ver_clientes': True, 'criar_clientes': True, 'editar_clientes': True,
        'excluir_clientes': True, 'bloquear_clientes': True,
        'ver_integracoes': True, 'config_integracoes': True,
        'ver_dashboard': True, 'gerenciar_tags': True, 'gerenciar_usuarios': True,
    },
    'gerente': {
        'ver_clientes': True, 'criar_clientes': True, 'editar_clientes': True,
        'excluir_clientes': False, 'bloquear_clientes': True,
        'ver_integracoes': True, 'config_integracoes': False,
        'ver_dashboard': True, 'gerenciar_tags': True, 'gerenciar_usuarios': False,
    },
    'atendente': {
        'ver_clientes': True, 'criar_clientes': False, 'editar_clientes': False,
        'excluir_clientes': False, 'bloquear_clientes': False,
        'ver_integracoes': False, 'config_integracoes': False,
        'ver_dashboard': False, 'gerenciar_tags': False, 'gerenciar_usuarios': False,
    },
}


class Usuario(models.Model):
    name       = models.CharField('Nome completo', max_length=150)
    email      = models.EmailField('E-mail', unique=True)
    role       = models.CharField('Perfil', max_length=20, choices=ROLE_CHOICES, default='atendente')
    password   = models.CharField('Senha (hash)', max_length=256)
    perms      = models.JSONField('Permissões', default=dict)
    ativo      = models.BooleanField('Ativo', default=True)
    last_login = models.DateTimeField('Último acesso', null=True, blank=True)
    auth_token = models.CharField(
        'Token de sessão', max_length=64, unique=True, null=True, blank=True, editable=False,
    )
    criado_em  = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_role_display()})'

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password)

    # Compatibilidade com DRF (Usuario não herda de AbstractBaseUser)
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def save(self, *args, **kwargs):
        # Garante que perms sempre tenha todas as chaves do perfil
        if not self.perms and self.role in PERMS_DEFAULT:
            self.perms = dict(PERMS_DEFAULT[self.role])
        super().save(*args, **kwargs)
