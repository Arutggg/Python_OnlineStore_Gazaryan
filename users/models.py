"""Модели клиентов: пользователь и адреса доставки."""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(r'^\+?\d{10,15}$', 'Телефон в формате +79991234567')


def join_full_name(last_name, first_name, middle_name=''):
    """Собрать ФИО из частей, пропуская пустые."""
    return ' '.join(part for part in (last_name, first_name, middle_name) if part)


class AddressFields(models.Model):
    """Общие поля почтового адреса. Используются в Address и в Order."""

    postal_code = models.CharField('индекс', max_length=6, blank=True)
    city = models.CharField('город', max_length=100)
    street = models.CharField('улица', max_length=150)
    house = models.CharField('дом', max_length=20)
    apartment = models.CharField('квартира', max_length=20, blank=True)

    class Meta:
        abstract = True

    def address_parts(self):
        """Вернуть части адреса в порядке записи на конверте."""
        return [self.postal_code, self.city, self.street, f'д. {self.house}',
                f'кв. {self.apartment}' if self.apartment else '']

    @property
    def address(self):
        """Адрес одной строкой."""
        return ', '.join(part for part in self.address_parts() if part)


class User(AbstractUser):
    """Клиент магазина. Фамилия, имя и email наследуются от AbstractUser."""

    middle_name = models.CharField('отчество', max_length=150, blank=True)
    phone = models.CharField('телефон', max_length=16, blank=True, validators=[phone_validator])

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'

    @property
    def full_name(self):
        """ФИО, а если оно не заполнено — логин."""
        return join_full_name(self.last_name, self.first_name, self.middle_name) or self.username

    @property
    def default_address(self):
        """Основной адрес доставки или первый из имеющихся."""
        return self.addresses.filter(is_default=True).first() or self.addresses.first()


class Address(AddressFields):
    """Адрес доставки клиента. У клиента может быть несколько адресов."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='addresses', verbose_name='пользователь',
    )
    region = models.CharField('регион', max_length=100, blank=True)
    is_default = models.BooleanField('основной', default=False)

    class Meta:
        verbose_name = 'адрес'
        verbose_name_plural = 'адреса'
        ordering = ['-is_default', 'id']

    def __str__(self):
        return self.address

    def address_parts(self):
        """Добавить регион после индекса."""
        parts = super().address_parts()
        parts.insert(1, self.region)
        return parts

    def save(self, *args, **kwargs):
        """Сохранить адрес, оставив у клиента ровно один основной."""
        others = self.user.addresses.exclude(pk=self.pk)
        if not others.exists():
            self.is_default = True
        if self.is_default:
            others.update(is_default=False)
        super().save(*args, **kwargs)
