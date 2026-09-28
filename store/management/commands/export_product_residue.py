import csv
import json
import io
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import StockBalance


class Command(BaseCommand):
    help = 'Выгрузить остатки товаров на складе в JSON или CSV'

    def add_arguments(self, parser):
        parser.add_argument('-o', '--output', help='файл для записи (по умолчанию — в консоль)')
        parser.add_argument('--format', choices=['json', 'csv', 'fixture'], default='json',
                            help='fixture — формат dumpdata, его можно загрузить обратно loaddata')
        parser.add_argument('--only-available', action='store_true', help='только товары с остатком > 0')

    def handle(self, output, format, only_available, **options):
        if format == 'fixture':
            call_command('dumpdata', 'store.StockBalance', indent=2, output=output)
            if output:
                self.stderr.write(self.style.SUCCESS(f'Остатки сохранены в {output}'))
            return

        qs = StockBalance.objects.select_related('product__category').order_by('product__name')
        if only_available:
            qs = qs.filter(quantity__gt=0)
        rows = [{
            'product_id': s.product_id,
            'product': s.product.name,
            'category': s.product.category.name,
            'price': str(s.product.price),
            'quantity': s.quantity,
            'updated_at': timezone.localtime(s.updated_at).isoformat(timespec='seconds'),
        } for s in qs]

        if format == 'csv':
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else ['product_id'])
            writer.writeheader()
            writer.writerows(rows)
            text = buf.getvalue()
        else:
            text = json.dumps(rows, ensure_ascii=False, indent=2) + '\n'

        if output:
            Path(output).write_text(text, encoding='utf-8')
        else:
            self.stdout.write(text, ending='')
        if output:
            self.stderr.write(self.style.SUCCESS(f'Выгружено {len(rows)} позиций в {output}'))
