# Проект: Сайт интернет-магазина

**Имя Фамилия:** Арутюн Газарян
**Логин на GitHub:** [Arutggg](https://github.com/Arutggg)
**E-mail:** arutyun.gaz@bk.ru

---

Backend интернет-магазина на Django и PostgreSQL. Это первая часть учебного проекта.

![Каталог](docs/screenshots/catalog.png)

## Что умеет

- **Каталог.** Категории, поиск, пагинация, карточка товара: название, изображение, описание, цена и остаток.
- **Корзина.** Добавление, изменение количества, удаление. **Положить в корзину больше, чем есть на складе, нельзя.** Это проверяется в форме, в `Cart.add_item` и ещё раз при оформлении заказа, с блокировкой строк `SELECT … FOR UPDATE`.
- **Заказ.** Данные получателя и адрес подставляются из профиля. Остатки списываются в одной транзакции, а цена фиксируется на момент покупки.
- **Личный кабинет.** ФИО (фамилия, имя, отчество отдельными полями), контакты, несколько адресов доставки, история покупок и статусы заказов. Новый заказ можно отменить, и товар вернётся на склад.
- **Регистрация, вход и выход.** Выход работает через POST, как требует Django 5.
- **Админка.** Тема `django-admin-interface`, превью фото, остатки прямо в карточке товара, смена статуса заказа из списка.
- **Management-команды** для загрузки товаров и выгрузки остатков.

## Структура базы данных

Схема и описание нормализации лежат в [docs/database.md](docs/database.md). Там же исходник для draw.io: [docs/db_schema.drawio](docs/db_schema.drawio).

![Схема БД](docs/db_schema.png)

## Запуск

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # укажите свои данные PostgreSQL
```

Создайте базу в PostgreSQL (`psql -U postgres`):

```sql
CREATE DATABASE online_store;
CREATE USER store_user WITH PASSWORD 'store_pass';
ALTER DATABASE online_store OWNER TO store_user;
```

Затем выполните:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --clear
python manage.py load_goods       # демо-товары с картинками и остатками
python manage.py runserver
```

Сайт будет на http://localhost:8000/, админка на http://localhost:8000/admin/.

## Команды для товаров и остатков

```bash
# Загрузка товаров. По умолчанию берётся store/fixtures/goods.json
python manage.py load_goods
python manage.py load_goods path/to/goods.json --add   # прибавить к остаткам, а не заменить
python manage.py load_goods store/fixtures/data.json   # фикстуру Django команда передаст в loaddata

# Выгрузка остатков (команды export_product_residue и unload_product_residue одинаковые)
python manage.py export_product_residue                       # JSON в консоль
python manage.py export_product_residue -o residue.csv --format csv
python manage.py unload_product_residue --only-available
python manage.py export_product_residue --format fixture -o stock.json   # потом можно загрузить через loaddata

# Стандартные команды Django
python manage.py dumpdata store.Category store.Product store.StockBalance --indent 2 -o data.json
python manage.py loaddata data.json
```

Формат `goods.json`:

```json
{
  "categories": [{"name": "Чай", "slug": "tea"}],
  "products": [
    {"name": "Сенча", "category": "tea", "description": "...", "price": 890,
     "quantity": 25, "image": "images/product_1.png"}
  ]
}
```

Путь `image` указывается относительно JSON-файла. Картинка копируется в `media/products/`.

## Тесты

```bash
python manage.py test
```

Тестами покрыто:
- ограничение корзины по остатку;
- списание остатков при заказе;
- повторная проверка остатка при оформлении;
- отмена заказа;
- доступ к чужому заказу;
- регистрация и выход;
- обе команды.

## Структура проекта

```
online_store/     настройки и корневые URL
users/            модель User (AbstractUser + отчество, телефон), Address, регистрация, личный кабинет
store/            Category, Product, StockBalance, Cart, CartItem, Order, OrderItem
  services.py     оформление и отмена заказа (транзакции, блокировка остатков)
  management/     load_goods, export_product_residue, unload_product_residue
  fixtures/       демо-данные (goods.json, data.json, картинки)
templates/        base.html, вход, выход, регистрация
docs/             схема БД и скриншоты
```

## Стек

Python 3.11+, Django 5.2, PostgreSQL 16, psycopg 3, django-admin-interface, Pillow.
