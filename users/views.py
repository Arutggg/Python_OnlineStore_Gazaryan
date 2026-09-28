from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.forms import AddressForm, ProfileForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Добро пожаловать! Аккаунт создан.')
        return redirect('home')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile(request):
    """Личный кабинет: данные, адреса, последние заказы."""
    orders = request.user.orders.prefetch_related('items__product')[:5]
    return render(request, 'users/profile.html', {
        'addresses': request.user.addresses.all(),
        'orders': orders,
    })


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Данные сохранены.')
        return redirect('profile')
    return render(request, 'users/form.html', {'form': form, 'title': 'Личные данные'})


@login_required
def address_add(request):
    form = AddressForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, 'Адрес добавлен.')
        return redirect(request.GET.get('next') or 'profile')
    return render(request, 'users/form.html', {'form': form, 'title': 'Новый адрес'})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Адрес обновлён.')
        return redirect('profile')
    return render(request, 'users/form.html', {'form': form, 'title': 'Редактирование адреса'})


@login_required
@require_POST
def address_delete(request, pk):
    get_object_or_404(request.user.addresses, pk=pk).delete()
    messages.info(request, 'Адрес удалён.')
    return redirect('profile')
