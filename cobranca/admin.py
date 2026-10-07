from django.contrib import admin

from .models import (
    ConfiguracaoCobranca, EtapaRegua, PausaCobranca, LigacaoCobranca, EnvioCobranca,
)

admin.site.register(ConfiguracaoCobranca)
admin.site.register(EtapaRegua)
admin.site.register(PausaCobranca)
admin.site.register(LigacaoCobranca)
admin.site.register(EnvioCobranca)
