from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField('название', max_length=255, unique=True)
    slug = models.SlugField('slug', max_length=255, unique=True)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category_detail', args=[self.slug])


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products', verbose_name='категория'
    )
    name = models.CharField('название', max_length=255)
    description = models.TextField('описание', blank=True)
    price = models.DecimalField(
        'цена', max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))]
    )
    image = models.ImageField('изображение', upload_to='products/', blank=True)
    is_active = models.BooleanField('в продаже', default=True)
    created_at = models.DateTimeField('создан', auto_now_add=True)

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.pk])

    @property
    def in_stock(self):
        """Сколько штук осталось на складе (0, если записи об остатке нет)."""
        stock = getattr(self, 'stock', None)
        return stock.quantity if stock else 0


class StockBalance(models.Model):
    """Остаток товара на складе. Одна запись на товар."""

    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name='stock', verbose_name='товар'
    )
    quantity = models.PositiveIntegerField('количество', default=0)
    updated_at = models.DateTimeField('обновлено', auto_now=True)

    class Meta:
        verbose_name = 'остаток'
        verbose_name_plural = 'остатки на складе'

    def __str__(self):
        return f'{self.product}: {self.quantity} шт.'


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='cart', verbose_name='пользователь',
    )
    created_at = models.DateTimeField('создана', auto_now_add=True)

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'

    def __str__(self):
        return f'Корзина {self.user}'

    def add_item(self, product, quantity=1):
        """Добавить товар. Итоговое количество не может превысить остаток.

        Возвращает количество, которое реально лежит в корзине после добавления.
        """
        item, _ = self.items.get_or_create(product=product, defaults={'quantity': 0})
        item.quantity = min(item.quantity + quantity, product.in_stock)
        if item.quantity <= 0:
            item.delete()
            return 0
        item.save(update_fields=['quantity'])
        return item.quantity

    def set_quantity(self, product, quantity):
        if quantity <= 0:
            self.items.filter(product=product).delete()
            return 0
        quantity = min(quantity, product.in_stock)
        self.items.update_or_create(product=product, defaults={'quantity': quantity})
        return quantity

    def remove_item(self, product):
        self.items.filter(product=product).delete()

    def clear(self):
        self.items.all().delete()

    @property
    def total(self):
        return sum((item.total for item in self.items.select_related('product')), Decimal('0'))

    @property
    def count(self):
        return self.items.aggregate(s=models.Sum('quantity'))['s'] or 0


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name='корзина')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='товар')
    quantity = models.PositiveIntegerField('количество', default=1)
    added_at = models.DateTimeField('добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'позиция корзины'
        verbose_name_plural = 'позиции корзины'
        ordering = ['added_at']
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product'),
        ]

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def total(self):
        return self.product.price * self.quantity


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Передан в доставку'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='orders', verbose_name='покупатель',
    )
    status = models.CharField('статус', max_length=20, choices=Status.choices, default=Status.NEW)
    # Данные получателя и адрес копируются в заказ: если клиент потом
    # изменит профиль, история заказов останется прежней.
    last_name = models.CharField('фамилия', max_length=150)
    first_name = models.CharField('имя', max_length=150)
    middle_name = models.CharField('отчество', max_length=150, blank=True)
    email = models.EmailField('email')
    phone = models.CharField('телефон', max_length=16)
    postal_code = models.CharField('индекс', max_length=6, blank=True)
    city = models.CharField('город', max_length=100)
    street = models.CharField('улица', max_length=150)
    house = models.CharField('дом', max_length=20)
    apartment = models.CharField('квартира', max_length=20, blank=True)
    comment = models.TextField('комментарий', blank=True)
    total = models.DecimalField('сумма', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('создан', auto_now_add=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True)

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.pk}'

    def get_absolute_url(self):
        return reverse('order_detail', args=[self.pk])

    @property
    def recipient(self):
        return ' '.join(p for p in (self.last_name, self.first_name, self.middle_name) if p)

    @property
    def address(self):
        parts = [self.postal_code, self.city, self.street, f'д. {self.house}']
        if self.apartment:
            parts.append(f'кв. {self.apartment}')
        return ', '.join(p for p in parts if p)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='заказ')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='товар')
    price = models.DecimalField('цена на момент заказа', max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField('количество')

    class Meta:
        verbose_name = 'позиция заказа'
        verbose_name_plural = 'позиции заказа'

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def total(self):
        return self.price * self.quantity
