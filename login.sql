\set customer_id random(1, 1000)

SELECT customer_id, name, email
FROM customers
WHERE customer_id = :customer_id;
