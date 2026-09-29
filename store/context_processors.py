"""Контекст-процессоры магазина."""

from store.services import get_cart_count


def cart(request):
    """Добавить в шаблоны количество товаров в корзине (для счётчика в шапке)."""
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    return {'cart_count': get_cart_count(request.user)}
