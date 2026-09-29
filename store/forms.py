"""Формы магазина."""

from django import forms

from store.models import Order, Product


class CartForm(forms.Form):
    """Добавление товара в корзину. Остаток проверяет services.add_to_cart."""

    product = forms.ModelChoiceField(
        label='Товар', queryset=Product.objects.filter(is_active=True).select_related('stock')
    )
    quantity = forms.IntegerField(label='Количество', min_value=1, initial=1)


class CartUpdateForm(forms.Form):
    """Изменение количества товара в корзине (0 — удалить)."""

    quantity = forms.IntegerField(min_value=0)


class OrderForm(forms.ModelForm):
    """Данные получателя и адрес. Корзина берётся из request.user, а не из формы."""

    RECIPIENT_FIELDS = ('last_name', 'first_name', 'middle_name', 'email', 'phone')
    ADDRESS_FIELDS = ('postal_code', 'city', 'street', 'house', 'apartment')

    class Meta:
        model = Order
        fields = (
            'last_name', 'first_name', 'middle_name', 'email', 'phone',
            'postal_code', 'city', 'street', 'house', 'apartment', 'comment',
        )
        widgets = {'comment': forms.Textarea(attrs={'rows': 3})}

    @classmethod
    def initial_for(cls, user):
        """Начальные значения из профиля и основного адреса пользователя."""
        initial = {field: getattr(user, field) for field in cls.RECIPIENT_FIELDS}
        address = user.default_address
        if address:
            initial.update({field: getattr(address, field) for field in cls.ADDRESS_FIELDS})
        return initial
