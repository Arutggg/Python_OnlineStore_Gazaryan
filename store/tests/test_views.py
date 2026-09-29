"""Интеграционные тесты страниц магазина: запрос → ответ."""

from django.test import TestCase
from django.urls import reverse

from store import services
from store.models import Order, StockBalance
from store.tests.factories import ORDER_DATA, make_product, make_user


class CatalogViewsTest(TestCase):
    """Каталог и карточка товара доступны без входа."""

    def setUp(self):
        self.product = make_product(description='Травянистый вкус', stock=3)

    def test_home(self):
        self.assertContains(self.client.get(reverse('home')), 'Сенча')

    def test_product_list_shows_attributes(self):
        response = self.client.get(reverse('product_list'))
        self.assertContains(response, 'Сенча')
        self.assertContains(response, '100 ₽')
        self.assertContains(response, 'Осталось 3 шт.')

    def test_search(self):
        make_product('Пиала')
        response = self.client.get(reverse('product_list'), {'q': 'сенч'})
        self.assertContains(response, 'Сенча')
        self.assertNotContains(response, 'Пиала')

    def test_category(self):
        response = self.client.get(self.product.category.get_absolute_url())
        self.assertContains(response, 'Сенча')

    def test_product_detail(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'Травянистый вкус')
        self.assertContains(response, '100,00 ₽')
        self.assertContains(response, 'Войдите, чтобы купить')

    def test_missing_and_hidden_products_404(self):
        hidden = make_product('Скрытый', is_active=False)
        self.assertEqual(self.client.get(reverse('product_detail', args=[999])).status_code, 404)
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)


class CartViewsTest(TestCase):
    """Корзина через HTTP."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=3)
        self.client.force_login(self.user)

    def test_cart_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('cart'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('cart')}")

    def test_add_to_cart(self):
        response = self.client.post(reverse('add_to_cart'), {'product': self.product.pk, 'quantity': 2})
        self.assertRedirects(response, reverse('cart'))
        self.assertEqual(services.get_cart_count(self.user), 2)

    def test_add_more_than_stock_shows_error(self):
        response = self.client.post(reverse('add_to_cart'), {'product': self.product.pk, 'quantity': 10})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'запрошено 10, на складе 3')
        self.assertEqual(services.get_cart_count(self.user), 0)

    def test_add_to_cart_page(self):
        self.assertContains(self.client.get(reverse('add_to_cart')), 'Добавить в корзину')

    def test_cart_page(self):
        services.add_to_cart(self.user, self.product, 2)
        response = self.client.get(reverse('cart'))
        self.assertContains(response, 'Сенча')
        self.assertContains(response, 'Итого: 200,00 ₽')

    def test_update_and_remove(self):
        services.add_to_cart(self.user, self.product, 1)
        self.client.post(reverse('cart_update', args=[self.product.pk]), {'quantity': 3})
        self.assertEqual(services.get_cart_count(self.user), 3)

        response = self.client.post(reverse('cart_update', args=[self.product.pk]), {'quantity': 9}, follow=True)
        self.assertContains(response, 'на складе 3')
        self.assertEqual(services.get_cart_count(self.user), 3)

        self.client.post(reverse('cart_remove', args=[self.product.pk]))
        self.assertEqual(services.get_cart_count(self.user), 0)

    def test_remove_requires_post(self):
        self.assertEqual(self.client.get(reverse('cart_remove', args=[self.product.pk])).status_code, 405)


class OrderViewsTest(TestCase):
    """Оформление заказа и история покупок."""

    def setUp(self):
        self.user = make_user(last_name='Иванов', first_name='Иван', email='ivan@example.com')
        self.product = make_product(stock=3)
        self.client.force_login(self.user)

    def test_checkout_with_empty_cart_redirects(self):
        self.assertRedirects(self.client.get(reverse('checkout')), reverse('product_list'))

    def test_checkout_prefills_profile(self):
        services.add_to_cart(self.user, self.product, 1)
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'value="Иванов"')
        self.assertContains(response, 'value="ivan@example.com"')

    def test_checkout_creates_order(self):
        services.add_to_cart(self.user, self.product, 2)
        response = self.client.post(reverse('checkout'), ORDER_DATA)
        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(StockBalance.objects.get(product=self.product).quantity, 1)

    def test_checkout_invalid_form(self):
        services.add_to_cart(self.user, self.product, 1)
        response = self.client.post(reverse('checkout'), {**ORDER_DATA, 'email': 'not-an-email'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_checkout_when_stock_ran_out(self):
        services.add_to_cart(self.user, self.product, 2)
        StockBalance.objects.filter(product=self.product).update(quantity=0)
        response = self.client.post(reverse('checkout'), ORDER_DATA, follow=True)
        self.assertRedirects(response, reverse('cart'))
        self.assertContains(response, 'на складе 0')

    def test_order_history_and_filters(self):
        services.add_to_cart(self.user, self.product, 1)
        order = services.create_order(self.user, ORDER_DATA)
        self.assertContains(self.client.get(reverse('order_list')), f'№{order.pk}')
        self.assertContains(self.client.get(reverse('order_list'), {'show': 'pending'}), f'№{order.pk}')
        self.assertNotContains(self.client.get(reverse('order_list'), {'show': 'sent'}), f'№{order.pk}')

    def test_order_detail_shows_status(self):
        services.add_to_cart(self.user, self.product, 1)
        order = services.create_order(self.user, ORDER_DATA)
        response = self.client.get(order.get_absolute_url())
        self.assertContains(response, 'Новый')
        self.assertContains(response, 'Отменить заказ')

    def test_cancel_order(self):
        services.add_to_cart(self.user, self.product, 1)
        order = services.create_order(self.user, ORDER_DATA)
        self.client.post(reverse('order_cancel', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_cannot_cancel_shipped_order(self):
        services.add_to_cart(self.user, self.product, 1)
        order = services.ship_order(services.create_order(self.user, ORDER_DATA))
        self.assertNotContains(self.client.get(order.get_absolute_url()), 'Отменить заказ')
        response = self.client.post(reverse('order_cancel', args=[order.pk]), follow=True)
        self.assertContains(response, 'Нельзя сменить статус')

    def test_foreign_order_is_404(self):
        services.add_to_cart(self.user, self.product, 1)
        order = services.create_order(self.user, ORDER_DATA)
        self.client.force_login(make_user('petr'))
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(reverse('order_cancel', args=[order.pk])).status_code, 404)


class AdminTest(TestCase):
    """Владелец магазина управляет товарами, заказами и клиентами."""

    def setUp(self):
        self.admin = make_user('admin', is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.product = make_product()

    def test_admin_pages_open(self):
        for name in ['store_product_changelist', 'store_order_changelist', 'store_stockbalance_changelist',
                     'store_category_changelist', 'users_user_changelist', 'store_product_add']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'admin:{name}')).status_code, 200)

    def test_ship_action(self):
        customer = make_user('customer')
        services.add_to_cart(customer, self.product, 1)
        order = services.create_order(customer, ORDER_DATA)
        self.client.post(reverse('admin:store_order_changelist'), {
            'action': 'mark_shipped', '_selected_action': [order.pk],
        })
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)

    def test_forbidden_transition_action_keeps_status(self):
        customer = make_user('customer')
        services.add_to_cart(customer, self.product, 1)
        order = services.create_order(customer, ORDER_DATA)
        self.client.post(reverse('admin:store_order_changelist'), {
            'action': 'mark_delivered', '_selected_action': [order.pk],
        })
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)
