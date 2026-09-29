"""Тесты моделей магазина."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from store import services
from store.exceptions import InsufficientStockError
from store.models import Cart, CartItem, Category, Order, OrderItem, Product, StockBalance
from store.tests.factories import ORDER_DATA, make_category, make_product, make_user


class CategoryModelTest(TestCase):
    """Категория."""

    def test_str_and_url(self):
        category = make_category()
        self.assertEqual(str(category), 'Чай')
        self.assertEqual(category.get_absolute_url(), '/category/tea/')

    def test_name_is_unique(self):
        make_category()
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='Чай', slug='tea-2')

    def test_category_with_products_cannot_be_deleted(self):
        product = make_product()
        with self.assertRaises(ProtectedError):
            product.category.delete()


class ProductModelTest(TestCase):
    """Товар."""

    def test_fields_and_str(self):
        product = make_product(description='Зелёный чай')
        self.assertEqual(str(product), 'Сенча')
        self.assertEqual(product.price, Decimal('100.00'))
        self.assertEqual(product.description, 'Зелёный чай')
        self.assertTrue(product.is_active)
        self.assertEqual(product.get_absolute_url(), f'/products/{product.pk}/')

    def test_in_stock_without_stock_record_is_zero(self):
        self.assertEqual(make_product(stock=None).in_stock, 0)

    def test_negative_price_is_invalid(self):
        product = make_product(price='-1')
        with self.assertRaises(ValidationError):
            product.full_clean()


class StockBalanceModelTest(TestCase):
    """Остатки на складе."""

    def test_stock_balance(self):
        """Сценарий из задания: остаток не уходит в минус, лишнее в корзину не попадает."""
        product = make_product(price='10', stock=10)
        customer = make_user('customer', email='test@example.com')

        services.add_to_cart(customer, product, quantity=3)
        services.create_order(customer, ORDER_DATA)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 7)

        with self.assertRaises(InsufficientStockError):
            services.add_to_cart(customer, product, quantity=8)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 7)
        self.assertFalse(CartItem.objects.filter(cart__user=customer).exists())

    def test_quantity_cannot_be_negative_in_db(self):
        product = make_product()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockBalance.objects.filter(product=product).update(quantity=-1)

    def test_one_stock_record_per_product(self):
        product = make_product()
        with self.assertRaises(IntegrityError):
            StockBalance.objects.create(product=product, quantity=1)

    def test_str(self):
        self.assertEqual(str(make_product(stock=3).stock), 'Сенча: 3 шт.')


class CartModelTest(TestCase):
    """Корзина и её позиции."""

    def setUp(self):
        self.user = make_user()
        self.cart = Cart.objects.create(user=self.user)

    def test_total_and_count(self):
        tea = make_product('Сенча', '100.00')
        cup = make_product('Пиала', '250.50')
        CartItem.objects.create(cart=self.cart, product=tea, quantity=2)
        CartItem.objects.create(cart=self.cart, product=cup, quantity=1)
        self.assertEqual(self.cart.total, Decimal('450.50'))
        self.assertEqual(self.cart.count, 3)

    def test_empty_cart(self):
        self.assertEqual(self.cart.total, 0)
        self.assertEqual(self.cart.count, 0)

    def test_product_only_once_in_cart(self):
        product = make_product()
        CartItem.objects.create(cart=self.cart, product=product)
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(cart=self.cart, product=product)

    def test_one_cart_per_user(self):
        with self.assertRaises(IntegrityError):
            Cart.objects.create(user=self.user)

    def test_item_total_and_str(self):
        item = CartItem.objects.create(cart=self.cart, product=make_product(price='99.90'), quantity=3)
        self.assertEqual(item.total, Decimal('299.70'))
        self.assertEqual(str(item), 'Сенча × 3')


class OrderModelTest(TestCase):
    """Заказ и его позиции."""

    def setUp(self):
        self.user = make_user()

    def make_order(self, status=Order.Status.NEW):
        """Создать заказ с заданным статусом."""
        return Order.objects.create(user=self.user, status=status, **ORDER_DATA)

    def test_default_status_is_new(self):
        self.assertEqual(self.make_order().status, Order.Status.NEW)

    def test_recipient_and_address(self):
        order = self.make_order()
        self.assertEqual(order.recipient, 'Иванов Иван Иванович')
        self.assertEqual(order.address, '101000, Москва, Тверская, д. 1, кв. 5')

    def test_str_and_url(self):
        order = self.make_order()
        self.assertEqual(str(order), f'Заказ №{order.pk}')
        self.assertEqual(order.get_absolute_url(), f'/orders/{order.pk}/')

    def test_sent_and_pending_querysets(self):
        new = self.make_order()
        paid = self.make_order(Order.Status.PAID)
        shipped = self.make_order(Order.Status.SHIPPED)
        delivered = self.make_order(Order.Status.DELIVERED)
        self.make_order(Order.Status.CANCELLED)
        self.assertCountEqual(Order.objects.sent(), [shipped, delivered])
        self.assertCountEqual(Order.objects.pending(), [new, paid])

    def test_newest_first(self):
        first, second = self.make_order(), self.make_order()
        self.assertEqual(list(Order.objects.all()), [second, first])

    def test_order_item_keeps_price(self):
        product = make_product(price='100.00')
        item = OrderItem.objects.create(order=self.make_order(), product=product, price=product.price, quantity=2)
        Product.objects.filter(pk=product.pk).update(price=Decimal('500.00'))
        item.refresh_from_db()
        self.assertEqual(item.total, Decimal('200.00'))

    def test_ordered_product_cannot_be_deleted(self):
        product = make_product()
        OrderItem.objects.create(order=self.make_order(), product=product, price=product.price, quantity=1)
        with self.assertRaises(ProtectedError):
            product.delete()
