from django.core.management.base import BaseCommand, CommandError

from atendimento.models import TokenExtensao
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Gera um token para a extensão de Chrome (impresso uma única vez).'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, action='append', required=True)
        parser.add_argument('--nome', required=True)

    def handle(self, *args, **opts):
        empresas = list(Empresa.objects.filter(pk__in=opts['empresa']))
        if len(empresas) != len(set(opts['empresa'])):
            raise CommandError('Empresa(s) inexistente(s).')
        obj, token = TokenExtensao.criar(opts['nome'], empresas)
        self.stdout.write(f'Token #{obj.id} ({obj.nome}) — guarde agora, não será exibido de novo:')
        self.stdout.write(token)
