from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    r'^\+?\d{10,15}$', 'Телефон в формате +79991234567'
)


class User(AbstractUser):
    """Клиент магазина. Фамилия, имя, email уже есть в AbstractUser."""

    middle_name = models.CharField('отчество', max_length=150, blank=True)
    phone = models.CharField(
        'телефон', max_length=16, blank=True, validators=[phone_validator]
    )

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'

    @property
    def full_name(self):
        parts = (self.last_name, self.first_name, self.middle_name)
        return ' '.join(p for p in parts if p) or self.username

    @property
    def default_address(self):
        return self.addresses.filter(is_default=True).first() or self.addresses.first()


class Address(models.Model):
    """Адрес доставки клиента. У клиента может быть несколько адресов."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='addresses',
        verbose_name='пользователь',
    )
    postal_code = models.CharField('индекс', max_length=6, blank=True)
    region = models.CharField('регион', max_length=100, blank=True)
    city = models.CharField('город', max_length=100)
    street = models.CharField('улица', max_length=150)
    house = models.CharField('дом', max_length=20)
    apartment = models.CharField('квартира', max_length=20, blank=True)
    is_default = models.BooleanField('основной', default=False)

    class Meta:
        verbose_name = 'адрес'
        verbose_name_plural = 'адреса'
        ordering = ['-is_default', 'id']

    def __str__(self):
        parts = [self.postal_code, self.region, self.city, self.street, f'д. {self.house}']
        if self.apartment:
            parts.append(f'кв. {self.apartment}')
        return ', '.join(p for p in parts if p)

    def save(self, *args, **kwargs):
        # первый адрес или отмеченный как основной — единственный основной
        if not self.user.addresses.exclude(pk=self.pk).exists():
            self.is_default = True
        if self.is_default:
            self.user.addresses.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
