"""Тесты регистрации, входа и личного кабинета."""

from django.test import TestCase
from django.urls import reverse

from users.models import Address, User

REGISTER_DATA = {
    'username': 'petr', 'last_name': 'Петров', 'first_name': 'Пётр', 'middle_name': 'Петрович',
    'email': 'petr@example.com', 'phone': '+79991112233',
    'password1': 'Sup3rSecret!', 'password2': 'Sup3rSecret!',
}


class AuthTest(TestCase):
    """Регистрация, вход и выход."""

    def test_register_saves_user_and_logs_in(self):
        response = self.client.post(reverse('register'), REGISTER_DATA)
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(username='petr')
        self.assertEqual((user.last_name, user.middle_name, user.phone), ('Петров', 'Петрович', '+79991112233'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_register_password_mismatch(self):
        response = self.client.post(reverse('register'), {**REGISTER_DATA, 'password2': 'other'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_login_and_logout(self):
        User.objects.create_user('petr', password='Sup3rSecret!')
        response = self.client.post(reverse('login'), {'username': 'petr', 'password': 'Sup3rSecret!'})
        self.assertRedirects(response, reverse('home'))
        self.assertContains(self.client.post(reverse('logout')), 'Вы вышли')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_password(self):
        User.objects.create_user('petr', password='Sup3rSecret!')
        response = self.client.post(reverse('login'), {'username': 'petr', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class ProfileTest(TestCase):
    """Личный кабинет."""

    def setUp(self):
        self.user = User.objects.create_user('petr', last_name='Петров', first_name='Пётр')
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('profile')).status_code, 302)

    def test_profile_page(self):
        self.assertContains(self.client.get(reverse('profile')), 'Петров Пётр')

    def test_edit_profile(self):
        self.client.post(reverse('profile_edit'), {
            'last_name': 'Сидоров', 'first_name': 'Пётр', 'middle_name': '', 'email': 'p@e.com', 'phone': '',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Сидоров')

    def test_address_crud(self):
        data = {'city': 'Москва', 'street': 'Тверская', 'house': '1'}
        self.client.post(reverse('address_add'), data)
        address = Address.objects.get(user=self.user)

        self.client.post(reverse('address_edit', args=[address.pk]), {**data, 'house': '2'})
        address.refresh_from_db()
        self.assertEqual(address.house, '2')

        self.client.post(reverse('address_delete', args=[address.pk]))
        self.assertFalse(Address.objects.exists())

    def test_foreign_address_is_404(self):
        other = User.objects.create_user('ivan')
        address = Address.objects.create(user=other, city='Москва', street='Арбат', house='1')
        self.assertEqual(self.client.get(reverse('address_edit', args=[address.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('address_delete', args=[address.pk])).status_code, 404)
