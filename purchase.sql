\set customer_id random(1, 1000)
\set product_id random_gaussian(1, 500, 3.0)
\set quantity random(1, 3)

SELECT price AS product_price FROM products WHERE product_id = :product_id \gset

BEGIN;

INSERT INTO orders (customer_id, status, total_amount)
VALUES (:customer_id, 'pending', :product_price)
RETURNING order_id AS new_order_id \gset

INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
VALUES (:new_order_id, :product_id, :quantity, :product_price);

UPDATE orders
SET total_amount = :product_price * :quantity
WHERE order_id = :new_order_id;

UPDATE products
SET stock_quantity = stock_quantity - :quantity
WHERE product_id = :product_id AND stock_quantity >= :quantity;

COMMIT;
