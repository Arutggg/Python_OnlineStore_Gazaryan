from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.forms import CartForm, CartUpdateForm, OrderForm
from store.models import Cart, Category, Order, Product
from store.services import OutOfStockError, cancel_order, create_order


def _products():
    return Product.objects.filter(is_active=True).select_related('category', 'stock')


def home(request):
    return render(request, 'store/home.html', {
        'categories': Category.objects.all(),
        'products': _products().order_by('-created_at')[:8],
    })


def product_list(request, category=None):
    products = _products()
    if category:
        products = products.filter(category=category)
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    page = Paginator(products, 12).get_page(request.GET.get('page'))
    return render(request, 'store/product_list.html', {
        'products': page,
        'page_obj': page,
        'categories': Category.objects.all(),
        'current_category': category,
        'query': query,
    })


def category_detail(request, slug):
    return product_list(request, category=get_object_or_404(Category, slug=slug))


def product_detail(request, pk):
    product = get_object_or_404(_products(), pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})


@login_required
def add_to_cart(request):
    if request.method == 'POST':
        form = CartForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            requested = form.cleaned_data['quantity']
            cart, _ = Cart.objects.get_or_create(user=request.user)
            before = cart.items.filter(product=product).values_list('quantity', flat=True).first() or 0
            after = cart.add_item(product, requested)
            if after - before < requested:
                messages.warning(
                    request, f'«{product}»: на складе {product.in_stock} шт., в корзине теперь {after}.'
                )
            else:
                messages.success(request, f'«{product}» добавлен в корзину.')
            return redirect('cart')
    else:
        form = CartForm(initial={'product': request.GET.get('product'), 'quantity': 1})
    return render(request, 'store/add_to_cart.html', {'form': form})


@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product', 'product__stock')
    return render(request, 'store/cart.html', {'cart': cart, 'items': items})


@login_required
@require_POST
def cart_update(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product.objects.select_related('stock'), pk=product_id)
    form = CartUpdateForm(request.POST)
    if form.is_valid():
        wanted = form.cleaned_data['quantity']
        got = cart.set_quantity(product, wanted)
        if got < wanted:
            messages.warning(request, f'«{product}»: на складе только {product.in_stock} шт.')
    return redirect('cart')


@login_required
@require_POST
def cart_remove(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    cart.items.filter(product_id=product_id).delete()
    return redirect('cart')


def _checkout_initial(user):
    initial = {
        'last_name': user.last_name, 'first_name': user.first_name,
        'middle_name': user.middle_name, 'email': user.email, 'phone': user.phone,
    }
    address = user.default_address
    if address:
        initial.update({
            f: getattr(address, f)
            for f in ('postal_code', 'city', 'street', 'house', 'apartment')
        })
    return initial


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product', 'product__stock')
    if not items:
        messages.info(request, 'Корзина пуста.')
        return redirect('product_list')

    form = OrderForm(request.POST or None, initial=_checkout_initial(request.user))
    if request.method == 'POST' and form.is_valid():
        try:
            order = create_order(request.user, form.cleaned_data)
        except OutOfStockError as e:
            for product, wanted, left in e.problems:
                messages.error(request, f'«{product}»: в корзине {wanted}, на складе {left}.')
            return redirect('cart')
        messages.success(request, f'Заказ №{order.pk} оформлен!')
        return redirect(order)
    return render(request, 'store/checkout.html', {'form': form, 'cart': cart, 'items': items})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related('items__product')
    return render(request, 'store/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(request.user.orders.prefetch_related('items__product'), pk=pk)
    return render(request, 'store/order_detail.html', {'order': order})


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(request.user.orders, pk=pk)
    try:
        cancel_order(order)
        messages.info(request, f'Заказ №{order.pk} отменён.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(order)
