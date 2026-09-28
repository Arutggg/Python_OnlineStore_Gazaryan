from django.db import transaction

from store.models import Order, OrderItem, StockBalance


class OutOfStockError(Exception):
    """Товара на складе меньше, чем в корзине."""

    def __init__(self, problems):
        self.problems = problems  # [(product, в корзине, на складе), ...]
        super().__init__('Недостаточно товара на складе')


@transaction.atomic
def create_order(user, data):
    """Оформить заказ из корзины пользователя.

    Остатки блокируются (SELECT ... FOR UPDATE), поэтому два покупателя
    не смогут одновременно купить последнюю единицу товара.
    """
    items = list(user.cart.items.select_related('product'))
    if not items:
        raise ValueError('Корзина пуста')

    stocks = StockBalance.objects.select_for_update().in_bulk(
        [i.product_id for i in items], field_name='product_id'
    )
    problems = [
        (i.product, i.quantity, stocks[i.product_id].quantity if i.product_id in stocks else 0)
        for i in items
        if i.product_id not in stocks or stocks[i.product_id].quantity < i.quantity
    ]
    if problems:
        raise OutOfStockError(problems)

    order = Order.objects.create(user=user, **data)
    OrderItem.objects.bulk_create(
        OrderItem(order=order, product=i.product, price=i.product.price, quantity=i.quantity)
        for i in items
    )
    for i in items:
        stock = stocks[i.product_id]
        stock.quantity -= i.quantity
        stock.save(update_fields=['quantity', 'updated_at'])

    order.total = sum(i.product.price * i.quantity for i in items)
    order.save(update_fields=['total'])
    user.cart.clear()
    return order


@transaction.atomic
def cancel_order(order):
    """Отменить новый заказ и вернуть товары на склад."""
    if order.status != Order.Status.NEW:
        raise ValueError('Отменить можно только новый заказ')
    for item in order.items.all():
        stock, _ = StockBalance.objects.select_for_update().get_or_create(product=item.product)
        stock.quantity += item.quantity
        stock.save(update_fields=['quantity', 'updated_at'])
    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status', 'updated_at'])
