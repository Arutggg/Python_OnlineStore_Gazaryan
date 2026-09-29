"""Команда выгрузки остатков товаров на складе."""

import csv
import io
import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import StockBalance


def collect_residue(only_available=False):
    """Остатки товаров в виде списка словарей, отсортированного по названию."""
    stocks = StockBalance.objects.select_related('product__category').order_by('product__name')
    if only_available:
        stocks = stocks.filter(quantity__gt=0)
    return [{
        'product_id': stock.product_id,
        'product': stock.product.name,
        'category': stock.product.category.name,
        'price': str(stock.product.price),
        'quantity': stock.quantity,
        'updated_at': timezone.localtime(stock.updated_at).isoformat(timespec='seconds'),
    } for stock in stocks]


def render_residue(rows, fmt):
    """Превратить строки остатков в текст JSON или CSV."""
    if fmt == 'csv':
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ['product_id'])
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()
    return json.dumps(rows, ensure_ascii=False, indent=2) + '\n'


class Command(BaseCommand):
    """Выгрузка остатков в JSON, CSV или фикстуру Django."""

    help = 'Выгрузить остатки товаров на складе в JSON или CSV'

    def add_arguments(self, parser):
        """Аргументы: файл, формат, фильтр по наличию."""
        parser.add_argument('-o', '--output', help='файл для записи (по умолчанию — в консоль)')
        parser.add_argument(
            '--format', dest='fmt', choices=['json', 'csv', 'fixture'], default='json',
            help='fixture — формат dumpdata, его можно загрузить обратно через loaddata',
        )
        parser.add_argument('--only-available', action='store_true', help='только товары с остатком > 0')

    def handle(self, output, fmt, only_available, **options):
        """Собрать остатки и записать их в файл или консоль."""
        if fmt == 'fixture':
            call_command('dumpdata', 'store.StockBalance', indent=2, output=output, stdout=self.stdout)
            return

        rows = collect_residue(only_available)
        text = render_residue(rows, fmt)
        if not output:
            self.stdout.write(text, ending='')
            return
        Path(output).write_text(text, encoding='utf-8')
        self.stderr.write(self.style.SUCCESS(f'Выгружено {len(rows)} позиций в {output}'))
