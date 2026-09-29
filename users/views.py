"""Регистрация и личный кабинет покупателя."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.services import get_user_orders
from users.forms import AddressForm, ProfileForm, RegisterForm

RECENT_ORDERS_LIMIT = 5


def register(request):
    """Регистрация нового покупателя с автоматическим входом."""
    if request.user.is_authenticated:
        return redirect('profile')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        messages.success(request, 'Добро пожаловать! Аккаунт создан.')
        return redirect('home')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile(request):
    """Личный кабинет: личные данные, адреса и последние заказы."""
    return render(request, 'users/profile.html', {
        'addresses': request.user.addresses.all(),
        'orders': get_user_orders(request.user)[:RECENT_ORDERS_LIMIT],
    })


@login_required
def profile_edit(request):
    """Редактирование ФИО и контактов."""
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Данные сохранены.')
        return redirect('profile')
    return render(request, 'users/form.html', {'form': form, 'title': 'Личные данные'})


@login_required
def address_form(request, pk=None):
    """Добавление (без ``pk``) или редактирование адреса доставки."""
    address = get_object_or_404(request.user.addresses, pk=pk) if pk else None
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        form.instance.user = request.user
        form.save()
        messages.success(request, 'Адрес сохранён.')
        return redirect('profile')
    title = 'Редактирование адреса' if address else 'Новый адрес'
    return render(request, 'users/form.html', {'form': form, 'title': title})


@login_required
@require_POST
def address_delete(request, pk):
    """Удаление адреса доставки."""
    get_object_or_404(request.user.addresses, pk=pk).delete()
    messages.info(request, 'Адрес удалён.')
    return redirect('profile')
