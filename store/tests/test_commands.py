"""Тесты management-команд загрузки товаров и выгрузки остатков."""

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from store.management.commands.export_product_residue import collect_residue, render_residue
from store.models import Product, StockBalance
from store.tests.factories import make_product

MEDIA_TMP = tempfile.mkdtemp()


def run(*args):
    """Выполнить команду и вернуть её вывод."""
    out = StringIO()
    call_command(*args, stdout=out, stderr=StringIO())
    return out.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class LoadGoodsTest(TestCase):
    """Команда load_goods."""

    def write_json(self, data):
        """Сохранить данные во временный JSON и вернуть путь."""
        path = Path(tempfile.mkdtemp()) / 'goods.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def test_default_file(self):
        run('load_goods')
        self.assertEqual(Product.objects.count(), 8)
        honey = Product.objects.get(name='Мёд гречишный')
        self.assertEqual(honey.in_stock, 12)
        self.assertTrue(honey.image.name.startswith('products/'))

    def test_if_empty_skips_when_products_exist(self):
        make_product()
        self.assertIn('пропускаю', run('load_goods', '--if-empty'))
        self.assertEqual(Product.objects.count(), 1)

    def test_update_and_add_mode(self):
        path = self.write_json({
            'categories': [{'name': 'Чай', 'slug': 'tea'}],
            'products': [{'name': 'Сенча', 'category': 'tea', 'price': 100, 'quantity': 5}],
        })
        run('load_goods', path)
        run('load_goods', path, '--add')
        self.assertEqual(Product.objects.get().in_stock, 10)
        run('load_goods', path)
        self.assertEqual(Product.objects.get().in_stock, 5)

    def test_bad_data(self):
        path = self.write_json({'products': [{'name': 'X', 'category': 'nope', 'price': 1}]})
        with self.assertRaises(CommandError):
            run('load_goods', path)
        with self.assertRaises(CommandError):
            run('load_goods', '/no/such/file.json')

    def test_django_fixture_goes_to_loaddata(self):
        make_product(stock=7)
        fixture = Path(tempfile.mkdtemp()) / 'data.json'
        call_command('dumpdata', 'store.Category', 'store.Product', 'store.StockBalance', output=str(fixture))
        Product.objects.all().delete()
        run('load_goods', str(fixture))
        self.assertEqual(StockBalance.objects.get().quantity, 7)


class ExportResidueTest(TestCase):
    """Команды export_product_residue и unload_product_residue."""

    def setUp(self):
        make_product('Сенча', stock=3)
        make_product('Пиала', stock=0)

    def test_collect_and_render(self):
        rows = collect_residue(only_available=True)
        self.assertEqual([row['product'] for row in rows], ['Сенча'])
        self.assertTrue(render_residue(rows, 'csv').startswith('product_id,product,'))

    def test_json_to_stdout(self):
        rows = json.loads(run('export_product_residue'))
        self.assertEqual({row['product']: row['quantity'] for row in rows}, {'Сенча': 3, 'Пиала': 0})

    def test_alias_and_file_output(self):
        path = Path(tempfile.mkdtemp()) / 'residue.csv'
        run('unload_product_residue', '--format', 'csv', '-o', str(path))
        self.assertIn('Сенча', path.read_text(encoding='utf-8'))

    def test_fixture_format(self):
        data = json.loads(run('export_product_residue', '--format', 'fixture'))
        self.assertEqual({item['model'] for item in data}, {'store.stockbalance'})
