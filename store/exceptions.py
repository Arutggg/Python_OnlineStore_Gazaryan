"""Исключения бизнес-логики магазина."""


class StoreError(Exception):
    """Базовая ошибка магазина: её текст можно показывать пользователю."""


class InsufficientStockError(StoreError):
    """Запрошено больше товара, чем есть на складе.

    Атрибут ``problems`` — список кортежей (товар, запрошено, доступно).
    """

    def __init__(self, problems):
        """Сохранить список проблем и собрать текст ошибки."""
        self.problems = problems
        super().__init__('; '.join(
            f'«{product}»: запрошено {wanted}, на складе {left}'
            for product, wanted, left in problems
        ))


class EmptyCartError(StoreError):
    """Попытка оформить заказ с пустой корзиной."""

    def __init__(self):
        """Задать стандартный текст ошибки."""
        super().__init__('Корзина пуста')


class OrderStatusError(StoreError):
    """Недопустимая смена статуса заказа."""
