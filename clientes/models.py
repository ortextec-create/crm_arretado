from django.db import models
from django.core.validators import RegexValidator


class Cliente(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
        ('N', 'Prefiro não informar'),
    ]

    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('bloqueado', 'Bloqueado'),
    ]

    # Dados pessoais
    nome = models.CharField(max_length=150)
    cpf = models.CharField(
        max_length=14,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r'^\d{3}\.\d{3}\.\d{3}-\d{2}$', 'CPF inválido. Use o formato 000.000.000-00')]
    )
    email = models.EmailField(unique=True, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, null=True, blank=True)

    # Contato
    telefone_principal = models.CharField(max_length=20)
    telefone_secundario = models.CharField(max_length=20, null=True, blank=True)

    # Controle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')
    observacoes = models.TextField(blank=True, default='')

    # Identidades externas (Fase 2)
    ifood_customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    anotaai_customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Timestamps
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['nome']),
            models.Index(fields=['telefone_principal']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.nome} ({self.telefone_principal})'

    @property
    def iniciais(self):
        partes = self.nome.strip().split()
        if len(partes) >= 2:
            return (partes[0][0] + partes[-1][0]).upper()
        return partes[0][:2].upper() if partes else '??'

    @property
    def tem_integracao_ifood(self):
        return bool(self.ifood_customer_id)

    @property
    def tem_integracao_anotaai(self):
        return bool(self.anotaai_customer_id)


class Endereco(models.Model):
    TIPO_CHOICES = [
        ('entrega', 'Entrega'),
        ('cobranca', 'Cobrança'),
        ('residencial', 'Residencial'),
        ('comercial', 'Comercial'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='enderecos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='entrega')
    apelido = models.CharField(max_length=50, blank=True, default='', help_text='Ex: Casa, Trabalho')

    cep = models.CharField(max_length=9)
    logradouro = models.CharField(max_length=200)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, default='')
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)

    principal = models.BooleanField(default=False)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Endereço'
        verbose_name_plural = 'Endereços'
        ordering = ['-principal', '-criado_em']

    def __str__(self):
        return f'{self.logradouro}, {self.numero} - {self.bairro}, {self.cidade}/{self.estado}'

    def save(self, *args, **kwargs):
        if self.principal:
            Endereco.objects.filter(cliente=self.cliente, principal=True).exclude(pk=self.pk).update(principal=False)
        super().save(*args, **kwargs)

    @property
    def endereco_completo(self):
        comp = f', {self.complemento}' if self.complemento else ''
        return f'{self.logradouro}, {self.numero}{comp} - {self.bairro}, {self.cidade}/{self.estado} - CEP: {self.cep}'


class TagCliente(models.Model):
    clientes = models.ManyToManyField(Cliente, related_name='tags', blank=True)
    nome = models.CharField(max_length=50, unique=True)
    cor = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ['nome']

    def __str__(self):
        return self.nome
