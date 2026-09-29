"""Представления магазина: каталог, корзина, оформление и история заказов.

Представления отвечают только за HTTP: разбирают форму, вызывают функцию
из ``store.services`` и показывают результат. Логики склада здесь нет.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store import services
from store.exceptions import StoreError
from store.forms import CartForm, CartUpdateForm, OrderForm
from store.models import Category, Order, Product

PRODUCTS_PER_PAGE = 12


def _active_products():
    """Товары в продаже вместе с категорией и остатком."""
    return Product.objects.filter(is_active=True).select_related('category', 'stock')


def home(request):
    """Главная: новинки и список категорий."""
    return render(request, 'store/home.html', {
        'categories': Category.objects.all(),
        'products': _active_products().order_by('-created_at')[:8],
    })


def product_list(request, category=None):
    """Каталог с фильтром по категории, поиском и пагинацией."""
    products = _active_products()
    if category:
        products = products.filter(category=category)
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    page = Paginator(products, PRODUCTS_PER_PAGE).get_page(request.GET.get('page'))
    return render(request, 'store/product_list.html', {
        'products': page,
        'page_obj': page,
        'categories': Category.objects.all(),
        'current_category': category,
        'query': query,
    })


def category_detail(request, slug):
    """Каталог, отфильтрованный по категории."""
    return product_list(request, category=get_object_or_404(Category, slug=slug))


def product_detail(request, pk):
    """Карточка товара."""
    product = get_object_or_404(_active_products(), pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})


@login_required
def add_to_cart(request):
    """Добавить товар в корзину (форма в карточке товара или отдельная страница)."""
    form = CartForm(request.POST or None, initial={'product': request.GET.get('product')})
    if request.method == 'POST' and form.is_valid():
        product = form.cleaned_data['product']
        try:
            services.add_to_cart(request.user, product, form.cleaned_data['quantity'])
        except StoreError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f'«{product}» добавлен в корзину.')
            return redirect('cart')
    return render(request, 'store/add_to_cart.html', {'form': form})


@login_required
def cart_detail(request):
    """Содержимое корзины."""
    cart = services.get_cart(request.user)
    return render(request, 'store/cart.html', {'cart': cart, 'items': services.get_cart_items(request.user)})


@login_required
@require_POST
def cart_update(request, product_id):
    """Изменить количество товара в корзине."""
    product = get_object_or_404(Product.objects.select_related('stock'), pk=product_id)
    form = CartUpdateForm(request.POST)
    if form.is_valid():
        try:
            services.set_cart_quantity(request.user, product, form.cleaned_data['quantity'])
        except StoreError as error:
            messages.warning(request, str(error))
    return redirect('cart')


@login_required
@require_POST
def cart_remove(request, product_id):
    """Удалить товар из корзины."""
    services.remove_from_cart(request.user, get_object_or_404(Product, pk=product_id))
    return redirect('cart')


@login_required
def checkout(request):
    """Оформление заказа из корзины."""
    items = services.get_cart_items(request.user)
    if not items:
        messages.info(request, 'Корзина пуста.')
        return redirect('product_list')

    form = OrderForm(request.POST or None, initial=OrderForm.initial_for(request.user))
    if request.method == 'POST' and form.is_valid():
        try:
            order = services.create_order(request.user, form.cleaned_data)
        except StoreError as error:
            messages.error(request, str(error))
            return redirect('cart')
        messages.success(request, f'Заказ №{order.pk} оформлен!')
        return redirect(order)
    return render(request, 'store/checkout.html', {
        'form': form, 'cart': services.get_cart(request.user), 'items': items,
    })


@login_required
def order_list(request):
    """История покупок с фильтром: все, отправленные, ожидающие отправки."""
    show = request.GET.get('show')
    orders = {
        'sent': services.get_sent_orders,
        'pending': services.get_pending_orders,
    }.get(show, services.get_user_orders)(request.user)
    return render(request, 'store/order_list.html', {'orders': orders, 'show': show})


@login_required
def order_detail(request, pk):
    """Страница заказа покупателя."""
    order = get_object_or_404(services.get_user_orders(request.user), pk=pk)
    can_cancel = services.can_change_status(order.status, Order.Status.CANCELLED)
    return render(request, 'store/order_detail.html', {'order': order, 'can_cancel': can_cancel})


@login_required
@require_POST
def order_cancel(request, pk):
    """Отменить свой заказ."""
    order = get_object_or_404(services.get_user_orders(request.user), pk=pk)
    try:
        services.cancel_order(order)
    except StoreError as error:
        messages.error(request, str(error))
    else:
        messages.info(request, f'Заказ №{order.pk} отменён.')
    return redirect(order)
