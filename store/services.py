"""Бизнес-логика магазина.

Функции не зависят от HTTP-запроса, форм и шаблонов: на вход получают
пользователя, модели и обычные значения, а ошибки сообщают исключениями
из ``store.exceptions``. Поэтому их удобно вызывать из представлений,
админки, management-команд и unit-тестов.
"""

from django.db import transaction
from django.db.models import Sum

from store.exceptions import EmptyCartError, InsufficientStockError, OrderStatusError
from store.models import Cart, CartItem, Order, OrderItem, StockBalance

# Разрешённые переходы статусов заказа: из какого статуса в какие можно перейти.
STATUS_TRANSITIONS = {
    Order.Status.NEW: {Order.Status.PAID, Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
}


# ---------- корзина ----------

def get_cart(user):
    """Вернуть корзину пользователя, создав её при первом обращении."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_cart_items(user):
    """Позиции корзины пользователя вместе с товарами и остатками."""
    return CartItem.objects.filter(cart__user=user).select_related('product', 'product__stock')


def get_cart_count(user):
    """Сколько единиц товара лежит в корзине пользователя."""
    return CartItem.objects.filter(cart__user=user).aggregate(total=Sum('quantity'))['total'] or 0


def _check_stock(product, quantity):
    """Бросить InsufficientStockError, если на складе меньше ``quantity``."""
    if quantity > product.in_stock:
        raise InsufficientStockError([(product, quantity, product.in_stock)])


def add_to_cart(user, product, quantity=1):
    """Добавить товар в корзину.

    Итоговое количество товара в корзине не может превышать остаток на
    складе, иначе бросается InsufficientStockError и корзина не меняется.
    Возвращает позицию корзины.
    """
    if quantity < 1:
        raise ValueError('Количество должно быть положительным')
    cart = get_cart(user)
    item = cart.items.filter(product=product).first()
    new_quantity = (item.quantity if item else 0) + quantity
    _check_stock(product, new_quantity)
    if item:
        item.quantity = new_quantity
        item.save(update_fields=['quantity'])
        return item
    return cart.items.create(product=product, quantity=new_quantity)


def set_cart_quantity(user, product, quantity):
    """Установить количество товара в корзине; 0 удаляет позицию."""
    if quantity <= 0:
        remove_from_cart(user, product)
        return None
    _check_stock(product, quantity)
    item, _ = get_cart(user).items.update_or_create(product=product, defaults={'quantity': quantity})
    return item


def remove_from_cart(user, product):
    """Удалить товар из корзины пользователя."""
    CartItem.objects.filter(cart__user=user, product=product).delete()


# ---------- заказы ----------

@transaction.atomic
def create_order(user, data):
    """Оформить заказ из корзины пользователя и списать остатки.

    ``data`` — данные получателя и адрес (поля модели Order).
    Остатки блокируются через SELECT ... FOR UPDATE, поэтому два покупателя
    не смогут одновременно купить последнюю единицу товара.
    """
    items = list(get_cart_items(user))
    if not items:
        raise EmptyCartError()

    stocks = StockBalance.objects.select_for_update().in_bulk(
        [item.product_id for item in items], field_name='product_id'
    )
    problems = []
    for item in items:
        available = stocks[item.product_id].quantity if item.product_id in stocks else 0
        if available < item.quantity:
            problems.append((item.product, item.quantity, available))
    if problems:
        raise InsufficientStockError(problems)

    order = Order.objects.create(
        user=user, total=sum(item.total for item in items), **data
    )
    OrderItem.objects.bulk_create(
        OrderItem(order=order, product=item.product, price=item.product.price, quantity=item.quantity)
        for item in items
    )
    for item in items:
        stock = stocks[item.product_id]
        stock.quantity -= item.quantity
        stock.save(update_fields=['quantity', 'updated_at'])

    CartItem.objects.filter(cart__user=user).delete()
    return order


def can_change_status(current, new):
    """Проверить, допустим ли переход заказа из статуса ``current`` в ``new``."""
    return new in STATUS_TRANSITIONS.get(current, set())


@transaction.atomic
def change_order_status(order, new_status):
    """Сменить статус заказа с проверкой допустимости перехода.

    При отмене товары возвращаются на склад.
    """
    if not can_change_status(order.status, new_status):
        raise OrderStatusError(
            f'Нельзя сменить статус «{order.get_status_display()}» '
            f'на «{Order.Status(new_status).label}»'
        )
    if new_status == Order.Status.CANCELLED:
        _return_to_stock(order)
    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    return order


def ship_order(order):
    """Передать заказ в доставку."""
    return change_order_status(order, Order.Status.SHIPPED)


def cancel_order(order):
    """Отменить заказ и вернуть товары на склад."""
    return change_order_status(order, Order.Status.CANCELLED)


def _return_to_stock(order):
    """Вернуть на склад все товары заказа."""
    for item in order.items.all():
        stock, _ = StockBalance.objects.select_for_update().get_or_create(product=item.product)
        stock.quantity += item.quantity
        stock.save(update_fields=['quantity', 'updated_at'])


def get_user_orders(user):
    """Все заказы пользователя, новые сверху."""
    return Order.objects.filter(user=user).prefetch_related('items__product')


def get_sent_orders(user):
    """Отправленные заказы пользователя."""
    return get_user_orders(user).sent()


def get_pending_orders(user):
    """Заказы пользователя, которые ещё не отправлены."""
    return get_user_orders(user).pending()
