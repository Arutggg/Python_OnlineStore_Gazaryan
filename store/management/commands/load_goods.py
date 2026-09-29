"""Команда загрузки товаров и остатков из JSON."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from store.models import Category, Product, StockBalance

DEFAULT_FILE = Path(settings.BASE_DIR) / 'store' / 'fixtures' / 'goods.json'


class Command(BaseCommand):
    """Загрузка товаров: простой формат или фикстура Django."""

    help = (
        'Загрузить товары и остатки из JSON. Понимает два формата: '
        'фикстуру Django (передаётся в loaddata) и простой формат '
        '{"categories": [...], "products": [...]}'
    )

    def add_arguments(self, parser):
        """Аргументы: путь к файлу и флаг --add."""
        parser.add_argument('file', nargs='?', default=str(DEFAULT_FILE), help='путь к JSON')
        parser.add_argument(
            '--add', action='store_true', help='прибавить количество к остатку, а не заменить его',
        )
        parser.add_argument(
            '--if-empty', action='store_true', help='ничего не делать, если товары уже есть (для автозапуска)',
        )

    def handle(self, file, add, if_empty, **options):
        """Прочитать файл и загрузить данные."""
        if if_empty and Product.objects.exists():
            self.stdout.write('Товары уже загружены, пропускаю.')
            return
        path = Path(file)
        if not path.exists():
            raise CommandError(f'Файл не найден: {path}')
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise CommandError(f'Некорректный JSON: {error}')

        if isinstance(data, list):  # результат dumpdata — отдаём стандартной команде
            call_command('loaddata', str(path), verbosity=options['verbosity'])
            return

        self.base_dir = path.parent
        with transaction.atomic():
            categories = self._load_categories(data.get('categories', []))
            created, updated = self._load_products(data.get('products', []), categories, add)
        self.stdout.write(self.style.SUCCESS(f'Готово: создано {created}, обновлено {updated} товаров.'))

    def _load_categories(self, items):
        """Создать или обновить категории. Вернуть словарь slug → Category."""
        categories = {}
        for item in items:
            slug = item.get('slug') or slugify(item['name'], allow_unicode=True)
            categories[slug], _ = Category.objects.update_or_create(slug=slug, defaults={'name': item['name']})
        return categories

    def _load_products(self, items, categories, add):
        """Создать или обновить товары и их остатки. Вернуть (создано, обновлено)."""
        created = updated = 0
        for number, item in enumerate(items, 1):
            product, is_new = Product.objects.update_or_create(
                name=item['name'], defaults=self._product_fields(number, item, categories),
            )
            created += is_new
            updated += not is_new

            stock, _ = StockBalance.objects.get_or_create(product=product)
            quantity = int(item.get('quantity', 0))
            stock.quantity = stock.quantity + quantity if add else quantity
            stock.save()
            self.stdout.write(f'  {product.name}: {stock.quantity} шт.')
        return created, updated

    def _product_fields(self, number, item, categories):
        """Проверить запись товара и подготовить поля модели."""
        try:
            slug = item['category']
            fields = {
                'category': categories.get(slug) or Category.objects.get(slug=slug),
                'description': item.get('description', ''),
                'price': Decimal(str(item['price'])),
            }
        except (KeyError, Category.DoesNotExist, InvalidOperation) as error:
            raise CommandError(f'Товар №{number}: ошибка в данных ({error!r})')
        if item.get('image'):
            fields['image'] = self._copy_image(item['image'])
        return fields

    def _copy_image(self, value):
        """Скопировать картинку, лежащую рядом с JSON, в MEDIA_ROOT/products/.

        Если такого файла нет, значение считается уже готовым путём в хранилище.
        """
        source = self.base_dir / value
        if not source.is_file():
            return value
        name = f'products/{source.name}'
        if not default_storage.exists(name):
            with source.open('rb') as file:
                name = default_storage.save(name, File(file))
        return name
