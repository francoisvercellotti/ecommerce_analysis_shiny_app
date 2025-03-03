# Produits les plus commandés
top_products_query = """
SELECT p.product_name, COUNT(*) as order_count
FROM order_products_prior opp
JOIN products p ON opp.product_id = p.product_id
GROUP BY p.product_name
ORDER BY order_count DESC
LIMIT 20
"""

# Heures de commande les plus populaires
hour_distribution_query = """
SELECT order_hour_of_day, COUNT(*) as order_count
FROM orders
GROUP BY order_hour_of_day
ORDER BY order_hour_of_day
"""

# Taux de réachat par département
reorder_rate_by_dept_query = """
SELECT d.department,
       COUNT(*) as order_count,
       SUM(opp.reordered) as reorder_count,
       SUM(opp.reordered)::float / COUNT(*) as reorder_rate
FROM order_products_prior opp
JOIN products p ON opp.product_id = p.product_id
JOIN departments d ON p.department_id = d.department_id
GROUP BY d.department
ORDER BY reorder_rate DESC
"""

# Distribution des commandes par jour de la semaine
dow_orders_query = """
SELECT order_dow, COUNT(*) as order_count
FROM orders
GROUP BY order_dow
ORDER BY order_dow
"""

# Taille moyenne du panier par heure de la journée
basket_size_hour_query = """
WITH order_sizes AS (
    SELECT o.order_id, o.order_hour_of_day, COUNT(opp.product_id) as basket_size
    FROM orders o
    JOIN order_products_prior opp ON o.order_id = opp.order_id
    GROUP BY o.order_id, o.order_hour_of_day
)
SELECT order_hour_of_day, AVG(basket_size) as avg_basket_size
FROM order_sizes
GROUP BY order_hour_of_day
ORDER BY order_hour_of_day
"""

# Produits fréquemment achetés ensemble
product_pairs_query = """
WITH product_pairs AS (
    SELECT a.product_id as product_id_1,
           b.product_id as product_id_2,
           COUNT(*) as pair_count
    FROM order_products_prior a
    JOIN order_products_prior b
        ON a.order_id = b.order_id AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    ORDER BY pair_count DESC
    LIMIT 20
)
SELECT p1.product_name as product_1,
       p2.product_name as product_2,
       pp.pair_count
FROM product_pairs pp
JOIN products p1 ON pp.product_id_1 = p1.product_id
JOIN products p2 ON pp.product_id_2 = p2.product_id
ORDER BY pp.pair_count DESC
"""