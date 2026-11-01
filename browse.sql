\set product_id random_zipfian(1, 500, 1.5)

SELECT product_id, name, category, price, stock_quantity
FROM products
WHERE product_id = :product_id;

SELECT product_id, name, price
FROM products
WHERE category = (SELECT category FROM products WHERE product_id = :product_id)
LIMIT 10;
