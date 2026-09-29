"""Тесты моделей клиента."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from users.models import Address, User, join_full_name


class JoinFullNameTest(SimpleTestCase):
    """Сборка ФИО."""

    def test_skips_empty_parts(self):
        self.assertEqual(join_full_name('Иванов', 'Иван', 'Иванович'), 'Иванов Иван Иванович')
        self.assertEqual(join_full_name('Иванов', 'Иван'), 'Иванов Иван')
        self.assertEqual(join_full_name('', ''), '')


class UserModelTest(TestCase):
    """Пользователь."""

    def test_full_name(self):
        user = User.objects.create_user('ivan', last_name='Иванов', first_name='Иван', middle_name='Иванович')
        self.assertEqual(user.full_name, 'Иванов Иван Иванович')

    def test_full_name_falls_back_to_username(self):
        self.assertEqual(User.objects.create_user('ivan').full_name, 'ivan')

    def test_phone_validation(self):
        user = User(username='ivan', phone='12-34')
        user.set_password('pass12345!')
        with self.assertRaises(ValidationError):
            user.full_clean()


class AddressModelTest(TestCase):
    """Адреса доставки."""

    def setUp(self):
        self.user = User.objects.create_user('ivan')

    def add(self, **fields):
        """Добавить адрес пользователю."""
        data = {'city': 'Москва', 'street': 'Тверская', 'house': '1'}
        return Address.objects.create(user=self.user, **{**data, **fields})

    def test_str(self):
        address = self.add(postal_code='101000', region='Москва', apartment='5')
        self.assertEqual(str(address), '101000, Москва, Москва, Тверская, д. 1, кв. 5')

    def test_first_address_becomes_default(self):
        self.assertTrue(self.add().is_default)
        self.assertEqual(self.user.default_address, self.user.addresses.get())

    def test_only_one_default(self):
        first = self.add()
        second = self.add(street='Арбат', is_default=True)
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertEqual(self.user.default_address, second)

    def test_no_addresses(self):
        self.assertIsNone(self.user.default_address)
