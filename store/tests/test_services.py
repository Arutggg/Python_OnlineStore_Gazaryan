"""Unit-тесты бизнес-логики из store.services.

Функции вызываются напрямую, без HTTP-запросов, форм и авторизации.
"""

from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from store import services
from store.exceptions import EmptyCartError, InsufficientStockError, OrderStatusError
from store.models import Order, StockBalance
from store.tests.factories import ORDER_DATA, make_product, make_user


class StatusTransitionsTest(SimpleTestCase):
    """Правила смены статуса — чистая функция, база не нужна."""

    def test_allowed(self):
        for current, new in [
            (Order.Status.NEW, Order.Status.PAID),
            (Order.Status.NEW, Order.Status.SHIPPED),
            (Order.Status.NEW, Order.Status.CANCELLED),
            (Order.Status.PAID, Order.Status.SHIPPED),
            (Order.Status.SHIPPED, Order.Status.DELIVERED),
        ]:
            with self.subTest(current=current, new=new):
                self.assertTrue(services.can_change_status(current, new))

    def test_forbidden(self):
        for current, new in [
            (Order.Status.SHIPPED, Order.Status.CANCELLED),
            (Order.Status.DELIVERED, Order.Status.NEW),
            (Order.Status.CANCELLED, Order.Status.PAID),
            (Order.Status.NEW, Order.Status.DELIVERED),
            (Order.Status.NEW, Order.Status.NEW),
        ]:
            with self.subTest(current=current, new=new):
                self.assertFalse(services.can_change_status(current, new))

    def test_error_message_lists_problems(self):
        error = InsufficientStockError([('Сенча', 5, 3)])
        self.assertEqual(str(error), '«Сенча»: запрошено 5, на складе 3')


class CartServiceTest(TestCase):
    """Добавление в корзину, изменение и получение содержимого."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=3)

    def test_get_cart_creates_once(self):
        self.assertEqual(services.get_cart(self.user), services.get_cart(self.user))

    def test_add_to_cart(self):
        item = services.add_to_cart(self.user, self.product, 2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(services.get_cart_count(self.user), 2)

    def test_add_same_product_sums_quantity(self):
        services.add_to_cart(self.user, self.product, 1)
        item = services.add_to_cart(self.user, self.product, 2)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(services.get_cart_items(self.user).count(), 1)

    def test_add_more_than_stock_raises_and_keeps_cart(self):
        services.add_to_cart(self.user, self.product, 2)
        with self.assertRaises(InsufficientStockError) as ctx:
            services.add_to_cart(self.user, self.product, 2)
        self.assertEqual(ctx.exception.problems, [(self.product, 4, 3)])
        self.assertEqual(services.get_cart_count(self.user), 2)

    def test_add_product_without_stock_record(self):
        with self.assertRaises(InsufficientStockError):
            services.add_to_cart(self.user, make_product('Без остатка', stock=None), 1)

    def test_add_non_positive_quantity(self):
        with self.assertRaises(ValueError):
            services.add_to_cart(self.user, self.product, 0)

    def test_set_quantity(self):
        services.add_to_cart(self.user, self.product, 1)
        self.assertEqual(services.set_cart_quantity(self.user, self.product, 3).quantity, 3)
        with self.assertRaises(InsufficientStockError):
            services.set_cart_quantity(self.user, self.product, 4)
        self.assertEqual(services.get_cart_count(self.user), 3)

    def test_set_zero_removes_item(self):
        services.add_to_cart(self.user, self.product, 1)
        self.assertIsNone(services.set_cart_quantity(self.user, self.product, 0))
        self.assertEqual(services.get_cart_count(self.user), 0)

    def test_remove_from_cart(self):
        services.add_to_cart(self.user, self.product, 1)
        services.remove_from_cart(self.user, self.product)
        self.assertFalse(services.get_cart_items(self.user).exists())

    def test_cart_items_are_isolated_between_users(self):
        other = make_user('petr')
        services.add_to_cart(self.user, self.product, 1)
        self.assertFalse(services.get_cart_items(other).exists())
        self.assertEqual(services.get_cart_count(other), 0)


class CreateOrderTest(TestCase):
    """Оформление заказа."""

    def setUp(self):
        self.user = make_user()
        self.tea = make_product('Сенча', '100.00', stock=5)
        self.cup = make_product('Пиала', '300.00', stock=2)

    def test_creates_order_with_items_and_total(self):
        services.add_to_cart(self.user, self.tea, 2)
        services.add_to_cart(self.user, self.cup, 1)
        order = services.create_order(self.user, ORDER_DATA)

        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.total, Decimal('500.00'))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.recipient, 'Иванов Иван Иванович')

    def test_decrements_stock_and_clears_cart(self):
        services.add_to_cart(self.user, self.tea, 5)
        services.create_order(self.user, ORDER_DATA)
        self.assertEqual(StockBalance.objects.get(product=self.tea).quantity, 0)
        self.assertEqual(services.get_cart_count(self.user), 0)

    def test_empty_cart(self):
        with self.assertRaises(EmptyCartError):
            services.create_order(self.user, ORDER_DATA)

    def test_stock_dropped_after_adding_to_cart(self):
        """Пока товар лежал в корзине, его раскупили — заказ не создаётся."""
        services.add_to_cart(self.user, self.tea, 3)
        StockBalance.objects.filter(product=self.tea).update(quantity=1)
        with self.assertRaises(InsufficientStockError) as ctx:
            services.create_order(self.user, ORDER_DATA)
        self.assertEqual(ctx.exception.problems, [(self.tea, 3, 1)])
        self.assertFalse(Order.objects.exists())
        self.assertEqual(StockBalance.objects.get(product=self.tea).quantity, 1)
        self.assertEqual(services.get_cart_count(self.user), 3)

    def test_price_is_fixed_at_purchase(self):
        services.add_to_cart(self.user, self.tea, 1)
        order = services.create_order(self.user, ORDER_DATA)
        self.tea.price = Decimal('999.00')
        self.tea.save()
        self.assertEqual(order.items.get().price, Decimal('100.00'))


class OrderStatusServiceTest(TestCase):
    """Отправка, отмена и выборки заказов."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=5)
        services.add_to_cart(self.user, self.product, 2)
        self.order = services.create_order(self.user, ORDER_DATA)

    def test_ship_order_changes_status(self):
        services.ship_order(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)

    def test_cancel_returns_goods_to_stock(self):
        services.cancel_order(self.order)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(StockBalance.objects.get(product=self.product).quantity, 5)

    def test_cannot_cancel_shipped_order(self):
        services.ship_order(self.order)
        with self.assertRaises(OrderStatusError):
            services.cancel_order(self.order)
        self.assertEqual(StockBalance.objects.get(product=self.product).quantity, 3)

    def test_cannot_cancel_twice(self):
        services.cancel_order(self.order)
        with self.assertRaises(OrderStatusError):
            services.cancel_order(self.order)
        self.assertEqual(StockBalance.objects.get(product=self.product).quantity, 5)

    def test_sent_and_pending_orders(self):
        services.add_to_cart(self.user, self.product, 1)
        second = services.create_order(self.user, ORDER_DATA)
        services.ship_order(self.order)

        self.assertEqual(list(services.get_sent_orders(self.user)), [self.order])
        self.assertEqual(list(services.get_pending_orders(self.user)), [second])
        self.assertEqual(services.get_user_orders(self.user).count(), 2)

    def test_orders_are_isolated_between_users(self):
        self.assertFalse(services.get_user_orders(make_user('petr')).exists())
