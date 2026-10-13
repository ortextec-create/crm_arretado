from django.test import TestCase

# Create your tests here.


class MontarLoggingTests(TestCase):
    """config/logging_config.py (ver LOGGING.md)."""

    def test_sem_log_dir_so_console(self):
        from config.logging_config import montar_logging
        cfg = montar_logging(None)
        self.assertEqual(list(cfg['handlers']), ['console'])
        self.assertEqual(cfg['root']['handlers'], ['console'])

    def test_log_dir_valido_monta_arquivos(self):
        import os
        import tempfile
        from config.logging_config import montar_logging
        d = tempfile.mkdtemp()
        cfg = montar_logging(d, 'INFO')
        self.assertEqual(set(cfg['handlers']), {'console', 'arquivo', 'arquivo_erros'})
        self.assertEqual(cfg['handlers']['arquivo']['filename'], os.path.join(d, 'arretado.log'))
        self.assertEqual(cfg['handlers']['arquivo_erros']['level'], 'ERROR')

    def test_log_dir_inexistente_ou_sem_escrita_cai_para_console(self):
        import os
        import tempfile
        from config.logging_config import montar_logging
        cfg = montar_logging('/caminho/que/nao/existe')
        self.assertEqual(list(cfg['handlers']), ['console'])
        if os.geteuid() != 0:  # root ignora permissão
            d = tempfile.mkdtemp()
            os.chmod(d, 0o500)
            cfg = montar_logging(d)
            self.assertEqual(list(cfg['handlers']), ['console'])

    def test_nivel_invalido_vira_info(self):
        from config.logging_config import montar_logging
        self.assertEqual(montar_logging(None, 'verbose')['root']['level'], 'INFO')

    def test_dictconfig_grava_erro_nos_dois_arquivos_e_info_so_no_geral(self):
        import logging
        import logging.config
        import os
        import tempfile
        from config.logging_config import montar_logging
        d = tempfile.mkdtemp()
        try:
            logging.config.dictConfig(montar_logging(d, 'INFO'))
            lg = logging.getLogger('teste.logging')
            lg.info('mensagem-info')
            lg.error('mensagem-erro')
            for h in logging.getLogger().handlers:
                h.flush()
            geral = open(os.path.join(d, 'arretado.log'), encoding='utf-8').read()
            erros = open(os.path.join(d, 'arretado-erros.log'), encoding='utf-8').read()
            self.assertIn('mensagem-info', geral)
            self.assertIn('mensagem-erro', geral)
            self.assertIn('mensagem-erro', erros)
            self.assertNotIn('mensagem-info', erros)
        finally:
            from django.conf import settings
            for h in list(logging.getLogger().handlers):
                h.close()
            logging.config.dictConfig(settings.LOGGING)
