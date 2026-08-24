from django.core.validators import RegexValidator
from django.db import models

validar_cor_hex = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Informe uma cor no formato hexadecimal, ex: #AE4A2A.',
)

validar_cnpj_formatado = RegexValidator(
    regex=r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$',
    message='Informe o CNPJ formatado, ex: 12.345.678/0001-90.',
)


def _campo_cor():
    return models.CharField(max_length=7, blank=True, default='', validators=[validar_cor_hex])


class Empresa(models.Model):
    """
    Uma linha por empresa (CNPJ) atendida pelo mesmo deploy/banco — multi-tenant por
    linha (ver MULTIEMPRESA.md). Campo vazio em qualquer cor cai no valor default do
    token CSS correspondente, então a empresa padrao=True pode nascer sem nenhuma cor
    cadastrada e a UI renderiza exatamente como hoje.
    """

    nome = models.CharField(max_length=80)
    subtitulo = models.CharField(max_length=80, blank=True, default='')
    razao_social = models.CharField(max_length=160, blank=True, default='')
    cnpj = models.CharField(max_length=18, blank=True, default='', validators=[validar_cnpj_formatado])
    padrao = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    # Fase 5 do multi-empresa (MULTIEMPRESA.md) — slugs de rota (ver Sidebar.jsx) que
    # a Sidebar esconde pra esta empresa. Nunca hardcodar nome de empresa aqui — é a
    # empresa quem lista, pelo painel, os módulos que não usa. Matriz nasce [] (menu
    # atual completo, UI preservada); é só filtro de UI, não é permissão (App.jsx
    # mantém todas as rotas registradas).
    modulos_ocultos = models.JSONField(default=list, blank=True)

    # Branding — cada campo corresponde a um token CSS (ver tabela em MULTIEMPRESA.md)
    cor_fundo = _campo_cor()
    cor_surface = _campo_cor()
    cor_surface_alt = _campo_cor()
    cor_borda = _campo_cor()
    cor_texto = _campo_cor()
    cor_muted = _campo_cor()
    cor_primaria = _campo_cor()
    cor_primaria_texto = _campo_cor()
    cor_acento = _campo_cor()
    cor_sidebar = _campo_cor()
    cor_sidebar_texto = _campo_cor()
    cor_sidebar_ativo = _campo_cor()

    logo_horizontal = models.ImageField(upload_to='empresas/', null=True, blank=True)
    logo_negativo = models.ImageField(upload_to='empresas/', null=True, blank=True)
    logo_simbolo = models.ImageField(upload_to='empresas/', null=True, blank=True)
    # Campo preparatório — nenhum gerador de PDF lê daqui nesta entrega (ver MULTIEMPRESA.md)
    timbre = models.FileField(upload_to='empresas/', null=True, blank=True)

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['-padrao', 'nome']
        constraints = [
            models.UniqueConstraint(fields=['padrao'], condition=models.Q(padrao=True), name='uniq_empresa_padrao'),
            models.UniqueConstraint(fields=['cnpj'], condition=~models.Q(cnpj=''), name='uniq_empresa_cnpj'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_padrao(cls):
        return cls.objects.get(padrao=True)
