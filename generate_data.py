import psycopg2
from faker import Faker
import random

fake = Faker()

# Konfigurasi koneksi database
conn = psycopg2.connect(
    host="localhost",
    database="benchmark_db",
    user="postgres",
)
cur = conn.cursor()

# Skala data (Scale Factor 1)
NUM_CUSTOMERS = 1000
NUM_PRODUCTS = 500
NUM_ORDERS = 5000

CATEGORIES = ['Electronics', 'Fashion', 'Home & Living', 'Books', 'Sports', 'Beauty']

print("Generating customers...")
customer_ids = []
for _ in range(NUM_CUSTOMERS):
    cur.execute(
        "INSERT INTO customers (name, email, address, city) VALUES (%s, %s, %s, %s) RETURNING customer_id",
        (fake.name(), fake.unique.email(), fake.address(), fake.city())
    )
    customer_ids.append(cur.fetchone()[0])
conn.commit()
print(f"{len(customer_ids)} customers inserted.")

print("Generating products...")
product_ids = []
for _ in range(NUM_PRODUCTS):
    cur.execute(
        "INSERT INTO products (name, category, price, stock_quantity) VALUES (%s, %s, %s, %s) RETURNING product_id",
        (fake.word().capitalize() + " " + fake.word().capitalize(),
         random.choice(CATEGORIES),
         round(random.uniform(5, 500), 2),
         random.randint(0, 1000))
    )
    product_ids.append(cur.fetchone()[0])
conn.commit()
print(f"{len(product_ids)} products inserted.")

print("Generating orders and order_items...")
order_count = 0
item_count = 0
for _ in range(NUM_ORDERS):
    customer_id = random.choice(customer_ids)
    status = random.choice(['pending', 'paid', 'shipped'])

    cur.execute(
        "INSERT INTO orders (customer_id, status, total_amount) VALUES (%s, %s, %s) RETURNING order_id",
        (customer_id, status, 0)
    )
    order_id = cur.fetchone()[0]
    order_count += 1

    # 1-5 item per order
    num_items = random.randint(1, 5)
    total_amount = 0
    for _ in range(num_items):
        product_id = random.choice(product_ids)
        quantity = random.randint(1, 3)
        cur.execute("SELECT price FROM products WHERE product_id = %s", (product_id,))
        price = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, %s, %s)",
            (order_id, product_id, quantity, price)
        )
        total_amount += float(price) * quantity
        item_count += 1

    cur.execute("UPDATE orders SET total_amount = %s WHERE order_id = %s", (total_amount, order_id))

    if order_count % 500 == 0:
        conn.commit()
        print(f"{order_count} orders processed...")

conn.commit()
print(f"Done. {order_count} orders and {item_count} order_items inserted.")

cur.close()
conn.close()
