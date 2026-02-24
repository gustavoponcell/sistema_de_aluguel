"""Centralized UI strings for consistent communication."""

from __future__ import annotations

from rental_manager.domain.models import ProductKind
from rental_manager.version import __app_name__

APP_NAME = __app_name__

TITLE_WARNING = "Atenção"
TITLE_ERROR = "Erro"
TITLE_SUCCESS = "Sucesso"
TITLE_CONFIRMATION = "Confirmação"

TERM_ORDER = "Pedido"
TERM_ORDER_PLURAL = "Pedidos"
TERM_ORDER_LOWER = "pedido"
TERM_ORDER_PLURAL_LOWER = "pedidos"
TERM_ITEM = "Item"
TERM_RENTAL = "Aluguel"
TERM_SALE = "Venda"
TERM_SERVICE = "Serviço"

LABEL_STOCK_TOTAL = "Total"
LABEL_STOCK_IN_USE = "Reservado/Em uso"
LABEL_STOCK_AVAILABLE = "Disponível"
LABEL_STOCK_TYPE = "Tipo"


def product_kind_label(kind: ProductKind | str) -> str:
    if isinstance(kind, ProductKind):
        normalized = kind.value
    else:
        normalized = str(kind)
    if normalized == ProductKind.SERVICE.value:
        return TERM_SERVICE
    if normalized == ProductKind.SALE.value:
        return TERM_SALE
    return TERM_RENTAL
