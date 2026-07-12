from rest_framework.pagination import PageNumberPagination


class PadraoPagination(PageNumberPagination):
    """Pagina 20 por padrão, mas respeita ?page_size= enviado pelo frontend."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
