-- Créer des index pour accélérer les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_dow_hour ON orders (order_dow, order_hour_of_day);
CREATE INDEX IF NOT EXISTS idx_order_products_order_id ON order_products_prior (order_id);
CREATE INDEX IF NOT EXISTS idx_order_products_product_id ON order_products_prior (product_id);
CREATE INDEX IF NOT EXISTS idx_order_products_reordered ON order_products_prior (reordered);
CREATE INDEX IF NOT EXISTS idx_products_aisle_dept ON products (aisle_id, department_id);

-- Créer des vues matérialisées pour les requêtes fréquentes et complexes
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_order_counts AS
SELECT p.product_id, p.product_name, COUNT(*) as order_count
FROM order_products_prior opp
JOIN products p ON opp.product_id = p.product_id
GROUP BY p.product_id, p.product_name;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_product_history AS
SELECT o.user_id, opp.product_id, COUNT(*) as purchase_count
FROM orders o
JOIN order_products_prior opp ON o.order_id = opp.order_id
GROUP BY o.user_id, opp.product_id;

-- Procédure pour rafraîchir les vues matérialisées (à exécuter périodiquement)
CREATE OR REPLACE PROCEDURE refresh_materialized_views()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_product_order_counts;
    REFRESH MATERIALIZED VIEW mv_user_product_history;
END;
$$;

-- Fonction pour obtenir les produits d'un utilisateur
CREATE OR REPLACE FUNCTION get_user_products(user_id_param INTEGER)
RETURNS TABLE (product_name TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT p.product_name
    FROM orders o
    JOIN order_products_prior opp ON o.order_id = opp.order_id
    JOIN products p ON opp.product_id = p.product_id
    WHERE o.user_id = user_id_param
    ORDER BY p.product_name;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour les recommandations
CREATE OR REPLACE FUNCTION get_recommendations(user_id_param INTEGER)
RETURNS TABLE (product_name TEXT, frequency FLOAT) AS $$
BEGIN
    RETURN QUERY
    WITH user_products AS (
        SELECT DISTINCT opp.product_id
        FROM orders o
        JOIN order_products_prior opp ON o.order_id = opp.order_id
        WHERE o.user_id = user_id_param
    ),
    user_aisles AS (
        SELECT DISTINCT p.aisle_id
        FROM user_products up
        JOIN products p ON up.product_id = p.product_id
    ),
    potential_products AS (
        SELECT p.product_id, p.product_name, COUNT(*) as frequency
        FROM orders o
        JOIN order_products_prior opp ON o.order_id = opp.order_id
        JOIN products p ON opp.product_id = p.product_id
        WHERE p.aisle_id IN (SELECT aisle_id FROM user_aisles)
        AND p.product_id NOT IN (SELECT product_id FROM user_products)
        AND o.user_id != user_id_param
        GROUP BY p.product_id, p.product_name
        HAVING COUNT(*) > 10
    )
    SELECT product_name, frequency
    FROM potential_products
    ORDER BY frequency DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;