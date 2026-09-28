from decimal import Decimal
from io import StringIO
import json

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from store.models import Cart, Category, Order, Product, StockBalance
from store.services import OutOfStockError, cancel_order, create_order
from users.models import User

ORDER_DATA = {
    'last_name': 'Иванов', 'first_name': 'Иван', 'middle_name': '', 'email': 'i@example.com',
    'phone': '+79990000000', 'postal_code': '101000', 'city': 'Москва', 'street': 'Тверская',
    'house': '1', 'apartment': '', 'comment': '',
}


class StoreTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ivan', password='pass12345!')
        cat = Category.objects.create(name='Чай', slug='tea')
        self.product = Product.objects.create(category=cat, name='Сенча', price=Decimal('100.00'))
        StockBalance.objects.create(product=self.product, quantity=3)
        self.cart = Cart.objects.create(user=self.user)


class CartTests(StoreTestCase):
    def test_add_item_is_limited_by_stock(self):
        self.assertEqual(self.cart.add_item(self.product, 2), 2)
        self.assertEqual(self.cart.add_item(self.product, 5), 3)
        self.assertEqual(self.cart.count, 3)
        self.assertEqual(self.cart.total, Decimal('300.00'))

    def test_add_to_cart_view_rejects_more_than_stock(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse('add_to_cart'), {'product': self.product.pk, 'quantity': 10})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'На складе только 3')
        self.assertEqual(self.cart.count, 0)

    def test_cart_requires_login(self):
        r = self.client.get(reverse('cart'))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('cart')}")


class OrderTests(StoreTestCase):
    def test_create_order_decrements_stock_and_clears_cart(self):
        self.cart.add_item(self.product, 2)
        order = create_order(self.user, ORDER_DATA)
        self.assertEqual(order.total, Decimal('200.00'))
        self.assertEqual(order.items.get().price, Decimal('100.00'))
        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, 1)
        self.assertEqual(self.cart.count, 0)

    def test_create_order_fails_if_stock_dropped(self):
        self.cart.add_item(self.product, 3)
        StockBalance.objects.filter(product=self.product).update(quantity=1)
        with self.assertRaises(OutOfStockError):
            create_order(self.user, ORDER_DATA)
        self.assertFalse(Order.objects.exists())

    def test_cancel_returns_goods(self):
        self.cart.add_item(self.product, 3)
        order = create_order(self.user, ORDER_DATA)
        cancel_order(order)
        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, 3)
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_checkout_view_and_history(self):
        self.client.force_login(self.user)
        self.cart.add_item(self.product, 1)
        r = self.client.post(reverse('checkout'), ORDER_DATA)
        order = Order.objects.get()
        self.assertRedirects(r, order.get_absolute_url())
        self.assertContains(self.client.get(reverse('order_list')), f'№{order.pk}')

    def test_user_cannot_see_foreign_order(self):
        self.cart.add_item(self.product, 1)
        order = create_order(self.user, ORDER_DATA)
        other = User.objects.create_user('petr', password='pass12345!')
        self.client.force_login(other)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)


class PagesTests(StoreTestCase):
    def test_catalog_pages(self):
        self.assertContains(self.client.get(reverse('product_list')), 'Сенча')
        self.assertContains(self.client.get(self.product.get_absolute_url()), '100,00')
        self.assertEqual(self.client.get(reverse('product_detail', args=[999])).status_code, 404)

    def test_register_and_profile(self):
        r = self.client.post(reverse('register'), {
            'username': 'new', 'last_name': 'Петров', 'first_name': 'Пётр', 'middle_name': 'Петрович',
            'email': 'p@example.com', 'phone': '+79991112233',
            'password1': 'Sup3rSecret!', 'password2': 'Sup3rSecret!',
        })
        self.assertRedirects(r, reverse('home'))
        self.assertContains(self.client.get(reverse('profile')), 'Петров Пётр Петрович')

    def test_logout_by_post(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.post(reverse('logout')), 'Вы вышли')


class CommandTests(StoreTestCase):
    def test_export_product_residue(self):
        out = StringIO()
        call_command('export_product_residue', stdout=out)
        self.assertEqual(json.loads(out.getvalue())[0]['quantity'], 3)

    def test_load_goods(self):
        call_command('load_goods', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 9)
        self.assertEqual(Product.objects.get(name='Мёд гречишный').in_stock, 12)
