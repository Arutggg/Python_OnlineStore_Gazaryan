"""Админ-панель магазина."""

from django.contrib import admin, messages
from django.utils.html import format_html

from store import services
from store.exceptions import StoreError
from store.models import Cart, CartItem, Category, Order, OrderItem, Product, StockBalance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Категории: slug заполняется из названия."""

    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class StockInline(admin.StackedInline):
    """Остаток на складе прямо в карточке товара."""

    model = StockBalance
    can_delete = False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Товары с превью фото и остатком."""

    list_display = ('thumb', 'name', 'category', 'price', 'in_stock', 'is_active')
    list_display_links = ('thumb', 'name')
    list_filter = ('category', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'description')
    inlines = [StockInline]

    def get_queryset(self, request):
        """Подгрузить категорию и остаток одним запросом."""
        return super().get_queryset(request).select_related('category', 'stock')

    @admin.display(description='фото')
    def thumb(self, obj):
        """Миниатюра изображения товара."""
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', obj.image.url)
        return '—'

    @admin.display(description='на складе')
    def in_stock(self, obj):
        """Остаток на складе."""
        return obj.in_stock


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    """Остатки: количество можно править прямо в списке."""

    list_display = ('product', 'quantity', 'updated_at')
    list_editable = ('quantity',)
    search_fields = ('product__name',)


class CartItemInline(admin.TabularInline):
    """Позиции корзины."""

    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Корзины покупателей."""

    list_display = ('user', 'created_at')
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    """Позиции заказа только для чтения."""

    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'price', 'quantity')
    can_delete = False


def _status_action(status, description):
    """Создать действие админки, переводящее выбранные заказы в ``status``."""
    @admin.action(description=description)
    def action(modeladmin, request, queryset):
        done = 0
        for order in queryset:
            try:
                services.change_order_status(order, status)
                done += 1
            except StoreError as error:
                modeladmin.message_user(request, f'{order}: {error}', messages.WARNING)
        if done:
            modeladmin.message_user(request, f'Обновлено заказов: {done}', messages.SUCCESS)

    action.__name__ = f'mark_{status}'
    return action


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Заказы. Статус меняется действиями, чтобы соблюдались правила переходов."""

    list_display = ('__str__', 'user', 'recipient', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__username', 'last_name', 'email', 'phone')
    readonly_fields = ('status', 'total', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    actions = [
        _status_action(Order.Status.PAID, 'Отметить как оплаченные'),
        _status_action(Order.Status.SHIPPED, 'Передать в доставку'),
        _status_action(Order.Status.DELIVERED, 'Отметить как доставленные'),
        _status_action(Order.Status.CANCELLED, 'Отменить (вернуть товар на склад)'),
    ]
