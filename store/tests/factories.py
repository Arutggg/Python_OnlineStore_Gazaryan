"""Хелперы для создания тестовых данных."""

from decimal import Decimal

from store.models import Category, Product, StockBalance
from users.models import User

ORDER_DATA = {
    'last_name': 'Иванов', 'first_name': 'Иван', 'middle_name': 'Иванович',
    'email': 'ivan@example.com', 'phone': '+79990000000',
    'postal_code': '101000', 'city': 'Москва', 'street': 'Тверская',
    'house': '1', 'apartment': '5', 'comment': '',
}


def make_user(username='ivan', **fields):
    """Создать пользователя с паролем pass12345!."""
    return User.objects.create_user(username, password='pass12345!', **fields)


def make_category(name='Чай', slug='tea'):
    """Создать категорию."""
    return Category.objects.create(name=name, slug=slug)


def make_product(name='Сенча', price='100.00', stock=5, category=None, **fields):
    """Создать товар с остатком ``stock`` (None — без записи об остатке)."""
    product = Product.objects.create(
        category=category or Category.objects.first() or make_category(),
        name=name, price=Decimal(price), **fields,
    )
    if stock is not None:
        StockBalance.objects.create(product=product, quantity=stock)
    return Product.objects.select_related('stock').get(pk=product.pk)
