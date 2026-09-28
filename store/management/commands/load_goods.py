import json
from decimal import Decimal
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
    help = (
        'Загрузить товары и остатки из JSON. Понимает два формата: '
        'фикстуру Django (передаётся в loaddata) и простой формат '
        '{"categories": [...], "products": [...]}'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='?', default=str(DEFAULT_FILE), help='путь к JSON')
        parser.add_argument(
            '--add', action='store_true',
            help='прибавить количество к остатку, а не заменить его',
        )

    def handle(self, file, add, **options):
        path = Path(file)
        if not path.exists():
            raise CommandError(f'Файл не найден: {path}')
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise CommandError(f'Некорректный JSON: {e}')

        # Фикстура Django (результат dumpdata) — отдаём стандартной команде
        if isinstance(data, list):
            call_command('loaddata', str(path), verbosity=options['verbosity'])
            return

        self.base_dir = path.parent
        created, updated = self._load(data, add)
        self.stdout.write(self.style.SUCCESS(
            f'Готово: создано {created}, обновлено {updated} товаров.'
        ))

    @transaction.atomic
    def _load(self, data, add):
        categories = {}
        for c in data.get('categories', []):
            slug = c.get('slug') or slugify(c['name'], allow_unicode=True)
            categories[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={'name': c['name']}
            )

        created = updated = 0
        for i, p in enumerate(data.get('products', []), 1):
            try:
                cat_slug = p['category']
                category = categories.get(cat_slug) or Category.objects.get(slug=cat_slug)
                defaults = {
                    'category': category,
                    'description': p.get('description', ''),
                    'price': Decimal(str(p['price'])),
                }
            except (KeyError, Category.DoesNotExist) as e:
                raise CommandError(f'Товар №{i}: нет поля или категории {e}')
            if p.get('image'):
                defaults['image'] = self._image(p['image'])

            product, is_new = Product.objects.update_or_create(name=p['name'], defaults=defaults)
            created += is_new
            updated += not is_new

            stock, _ = StockBalance.objects.get_or_create(product=product)
            qty = int(p.get('quantity', 0))
            stock.quantity = stock.quantity + qty if add else qty
            stock.save()
            self.stdout.write(f'  {product.name}: {stock.quantity} шт.')
        return created, updated

    def _image(self, value):
        """Файл рядом с JSON копируется в MEDIA_ROOT/products/, иначе путь берётся как есть."""
        src = self.base_dir / value
        if not src.is_file():
            return value
        name = f'products/{src.name}'
        if not default_storage.exists(name):
            with src.open('rb') as f:
                name = default_storage.save(name, File(f))
        return name
