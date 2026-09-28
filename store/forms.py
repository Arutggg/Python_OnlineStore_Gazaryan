from django import forms

from store.models import Order, Product


class CartForm(forms.Form):
    """Добавление товара в корзину."""

    product = forms.ModelChoiceField(
        label='Товар', queryset=Product.objects.filter(is_active=True).select_related('stock')
    )
    quantity = forms.IntegerField(label='Количество', min_value=1, initial=1)

    def clean(self):
        data = super().clean()
        product, quantity = data.get('product'), data.get('quantity')
        if product and quantity and quantity > product.in_stock:
            raise forms.ValidationError(f'На складе только {product.in_stock} шт.')
        return data


class CartUpdateForm(forms.Form):
    quantity = forms.IntegerField(min_value=0)


class OrderForm(forms.ModelForm):
    """Оформление заказа. Корзина берётся из request.user, а не из формы."""

    class Meta:
        model = Order
        fields = (
            'last_name', 'first_name', 'middle_name', 'email', 'phone',
            'postal_code', 'city', 'street', 'house', 'apartment', 'comment',
        )
        widgets = {'comment': forms.Textarea(attrs={'rows': 3})}
