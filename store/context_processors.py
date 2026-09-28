from django.db.models import Sum

from store.models import CartItem


def cart(request):
    """Количество товаров в корзине — для счётчика в шапке."""
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    count = CartItem.objects.filter(cart__user=request.user).aggregate(s=Sum('quantity'))['s']
    return {'cart_count': count or 0}
