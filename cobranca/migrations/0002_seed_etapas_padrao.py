from django.db import migrations

ETAPAS_SEED = [
    (-12, (
        'Oi, {primeiro_nome}! Tudo bem? 😊\n'
        'Passando para lembrar que o saldo do seu evento *{tipo_evento}* de *{data_evento}* '
        '({numero_evento}) deve ser quitado até *{data_limite}*.\n'
        '💰 Saldo: *R$ {saldo}*\n'
        'Pix: {chave_pix} ({favorecido_pix})\n'
        'Se já tiver pago, é só desconsiderar. Qualquer dúvida, estamos por aqui! 🍬\n'
        '— {empresa}'
    )),
    (-9, (
        'Oi, {primeiro_nome}! Faltam só {dias_para_limite} dias para o prazo do saldo do seu '
        'evento ({numero_evento}) 🗓️\n'
        '💰 *R$ {saldo}* até *{data_limite}*\n'
        'Pix: {chave_pix}\n'
        'Depois de pagar, envie o comprovante por aqui para darmos baixa. Obrigado! 💛'
    )),
    (-7, (
        'Bom dia, {primeiro_nome}! ☀️\n'
        'Hoje é o último dia para quitar o saldo do seu evento de *{data_evento}*.\n'
        '💰 *R$ {saldo}* · Pix: {chave_pix}\n'
        'Assim que recebermos, seguimos com tudo certinho para o seu dia! 🎉'
    )),
    (-6, (
        'Oi, {primeiro_nome}. Ainda não identificamos o pagamento do saldo do evento '
        '{numero_evento}, que venceu em {data_limite}.\n'
        '💰 Valor em aberto: *R$ {saldo}*\n'
        'Pix: {chave_pix} ({favorecido_pix})\n'
        'Se já pagou, pode nos enviar o comprovante? Pode ter sido só um desencontro 🙏'
    )),
    (-3, (
        'Olá, {primeiro_nome}. O saldo de *R$ {saldo}* do seu evento de *{data_evento}* está '
        'em aberto há {dias_em_atraso} dias.\n'
        'Para garantirmos a produção e a entrega no prazo, precisamos da quitação o quanto antes.\n'
        'Pix: {chave_pix}\n'
        'Se precisar combinar outra forma, fale com a gente pelo {telefone_empresa}.'
    )),
    (3, (
        'Olá, {primeiro_nome}. Consta em aberto o valor de *R$ {saldo}* referente ao evento '
        '{numero_evento} ({data_evento}), vencido em {data_limite}.\n'
        'Pedimos que regularize ou entre em contato pelo {telefone_empresa} para combinarmos '
        'a melhor forma.\n'
        'Pix: {chave_pix}\n'
        'Agradecemos a compreensão. — {empresa}'
    )),
]


def seed_etapas(apps, schema_editor):
    EtapaRegua = apps.get_model('cobranca', 'EtapaRegua')
    if EtapaRegua.objects.exists():
        return
    for dias, mensagem in ETAPAS_SEED:
        EtapaRegua.objects.create(dias=dias, mensagem=mensagem, ativo=True)


def no_op(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cobranca', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_etapas, no_op),
    ]
