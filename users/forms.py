"""Формы регистрации и личного кабинета."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from users.models import Address, User


class RegisterForm(UserCreationForm):
    """Регистрация: логин, ФИО, email, телефон и пароль."""

    email = forms.EmailField(label='Email', required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'last_name', 'first_name', 'middle_name', 'email', 'phone')


class ProfileForm(forms.ModelForm):
    """Редактирование личных данных."""

    class Meta:
        model = User
        fields = ('last_name', 'first_name', 'middle_name', 'email', 'phone')


class AddressForm(forms.ModelForm):
    """Адрес доставки."""

    class Meta:
        model = Address
        fields = ('postal_code', 'region', 'city', 'street', 'house', 'apartment', 'is_default')
