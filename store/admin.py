from django.contrib import admin
from django.utils.html import format_html

from store.models import Cart, CartItem, Category, Order, OrderItem, Product, StockBalance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class StockInline(admin.StackedInline):
    model = StockBalance
    can_delete = False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'name', 'category', 'price', 'in_stock', 'is_active')
    list_display_links = ('thumb', 'name')
    list_filter = ('category', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'description')
    inlines = [StockInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'stock')

    @admin.display(description='фото')
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', obj.image.url)
        return '—'

    @admin.display(description='на складе')
    def in_stock(self, obj):
        return obj.in_stock


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'updated_at')
    list_editable = ('quantity',)
    search_fields = ('product__name',)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'price', 'quantity')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'recipient', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    search_fields = ('id', 'user__username', 'last_name', 'email', 'phone')
    readonly_fields = ('total', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
