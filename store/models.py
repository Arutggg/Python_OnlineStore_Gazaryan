"""Модели магазина: каталог, склад, корзина и заказы.

Бизнес-логика (добавление в корзину, оформление заказа, смена статуса)
находится в ``store.services``, модели отвечают только за хранение данных.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from users.models import AddressFields, join_full_name


class Category(models.Model):
    """Категория товаров."""

    name = models.CharField('название', max_length=255, unique=True)
    slug = models.SlugField('slug', max_length=255, unique=True)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Страница категории в каталоге."""
        return reverse('category_detail', args=[self.slug])


class Product(models.Model):
    """Товар каталога."""

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
        """Карточка товара."""
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
    """Корзина покупателя. У каждого пользователя одна корзина."""

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

    @property
    def total(self):
        """Стоимость всех товаров в корзине."""
        return sum((item.total for item in self.items.select_related('product')), Decimal('0'))

    @property
    def count(self):
        """Общее количество единиц товара в корзине."""
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0


class CartItem(models.Model):
    """Позиция корзины: товар и его количество."""

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
        """Стоимость позиции по текущей цене товара."""
        return self.product.price * self.quantity


class OrderQuerySet(models.QuerySet):
    """Выборки заказов по состоянию доставки."""

    def sent(self):
        """Заказы, переданные в доставку или уже доставленные."""
        return self.filter(status__in=Order.SENT_STATUSES)

    def pending(self):
        """Заказы, которые ещё не отправлены покупателю."""
        return self.filter(status__in=Order.PENDING_STATUSES)


class Order(AddressFields):
    """Заказ покупателя.

    ФИО, контакты и адрес копируются в заказ при оформлении: если клиент
    потом изменит профиль, история заказов останется прежней.
    """

    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Передан в доставку'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'

    SENT_STATUSES = (Status.SHIPPED, Status.DELIVERED)
    PENDING_STATUSES = (Status.NEW, Status.PAID)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders', verbose_name='покупатель',
    )
    status = models.CharField('статус', max_length=20, choices=Status.choices, default=Status.NEW)
    last_name = models.CharField('фамилия', max_length=150)
    first_name = models.CharField('имя', max_length=150)
    middle_name = models.CharField('отчество', max_length=150, blank=True)
    email = models.EmailField('email')
    phone = models.CharField('телефон', max_length=16)
    comment = models.TextField('комментарий', blank=True)
    total = models.DecimalField('сумма', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('создан', auto_now_add=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.pk}'

    def get_absolute_url(self):
        """Страница заказа в личном кабинете."""
        return reverse('order_detail', args=[self.pk])

    @property
    def recipient(self):
        """ФИО получателя."""
        return join_full_name(self.last_name, self.first_name, self.middle_name)


class OrderItem(models.Model):
    """Позиция заказа. Цена фиксируется на момент покупки."""

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
        """Стоимость позиции."""
        return self.price * self.quantity
