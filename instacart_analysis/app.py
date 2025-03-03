from shiny import App, ui, render, reactive
import shinyswatch
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import logging
import time
from functools import lru_cache

# Configuration du logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("instacart_app")

# Chargement des variables d'environnement
load_dotenv()

# --- Création globale de l'engine ---
try:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    engine = create_engine(connection_string, pool_size=10, max_overflow=20)
    logger.info("Engine créé avec succès")
except Exception as e:
    logger.error(f"Erreur lors de la création de l'engine: {e}")
    raise

def get_connection():
    return engine

# --- Fonction de requête avec cache pour les requêtes sans paramètres ---
@lru_cache(maxsize=32)
def run_query_no_params(query, timeout=30):
    start_time = time.time()
    logger.info(f"Exécution de la requête (cache activé): {query[:100]}...")
    try:
        with get_connection().connect() as conn:
            result = pd.read_sql(query, conn)
            elapsed = time.time() - start_time
            logger.info(f"Requête terminée en {elapsed:.2f} secondes, {len(result)} lignes récupérées")
            return result
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Erreur dans la requête après {elapsed:.2f} secondes: {e}")
        raise

def run_query(query, params=None, timeout=30):
    """
    Si aucun paramètre n'est fourni, on utilise le cache (via run_query_no_params).
    Sinon, on exécute la requête sans mise en cache.
    """
    if params is None:
        return run_query_no_params(query, timeout)
    else:
        start_time = time.time()
        logger.info(f"Exécution de la requête avec paramètres: {query[:100]}... | params: {params}")
        try:
            with get_connection().connect() as conn:
                result = pd.read_sql(query, conn, params=params)
                elapsed = time.time() - start_time
                logger.info(f"Requête terminée en {elapsed:.2f} secondes, {len(result)} lignes récupérées")
                return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Erreur dans la requête (avec paramètres) après {elapsed:.2f} secondes: {e}")
            raise

# Import des requêtes SQL de manière sécurisée
try:
    from sql.queries import (
        top_products_query,
        hour_distribution_query,
        reorder_rate_by_dept_query,
        dow_orders_query,
        basket_size_hour_query
    )
    logger.info("Requêtes SQL importées avec succès")
except Exception as e:
    logger.error(f"Erreur lors de l'importation des requêtes SQL: {e}")
    # Définir des requêtes par défaut simples en cas d'erreur d'importation
    top_products_query = """
        SELECT p.product_name, COUNT(*) as order_count
        FROM order_products_prior opp
        JOIN products p ON opp.product_id = p.product_id
        GROUP BY p.product_name
        ORDER BY order_count DESC
        LIMIT 20
    """
    hour_distribution_query = """
        SELECT order_hour_of_day, COUNT(*) as order_count
        FROM orders
        GROUP BY order_hour_of_day
        ORDER BY order_hour_of_day
    """
    reorder_rate_by_dept_query = """
        SELECT d.department,
               SUM(opp.reordered)::float / COUNT(*) as reorder_rate
        FROM order_products_prior opp
        JOIN products p ON opp.product_id = p.product_id
        JOIN departments d ON p.department_id = d.department_id
        GROUP BY d.department
        ORDER BY reorder_rate DESC
    """
    dow_orders_query = """
        SELECT order_dow, COUNT(*) as order_count
        FROM orders
        GROUP BY order_dow
        ORDER BY order_dow
    """
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

# Liste des jours pour affichage
days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# UI - Interface utilisateur avec indicateurs de chargement
app_ui = ui.page_fluid(
    ui.panel_title("Instacart Market Basket Analysis"),
    ui.navset_tab(
        # Vue d'ensemble
        ui.nav_panel(
            "Vue d'ensemble",
            ui.page_sidebar(
                ui.sidebar(
                    ui.h4("Filtres"),
                    ui.input_slider("min_orders", "Nombre min. de commandes", 1, 20, 5),
                    ui.hr(),
                    ui.p("Cette page présente une vue d'ensemble des données Instacart.")
                ),
                # Contenu principal
                ui.h3("Vue d'ensemble des données"),
                ui.layout_columns(
                    ui.value_box(
                        "Nombre total de commandes",
                        ui.output_text("total_orders"),
                        showcase=ui.tags.i(class_="fa fa-shopping-cart")
                    ),
                    ui.value_box(
                        "Nombre total d'utilisateurs",
                        ui.output_text("total_users"),
                        showcase=ui.tags.i(class_="fa fa-users")
                    )
                ),
                ui.layout_columns(
                    ui.value_box(
                        "Nombre total de produits",
                        ui.output_text("total_products"),
                        showcase=ui.tags.i(class_="fa fa-cube")
                    ),
                    ui.value_box(
                        "Nombre moyen de produits par commande",
                        ui.output_text("avg_products"),
                        showcase=ui.tags.i(class_="fa fa-balance-scale")
                    )
                ),
                ui.h4("Distribution du nombre de commandes par utilisateur"),
                ui.output_ui("order_distribution")
            )
        ),
        # Analyse temporelle
        ui.nav_panel(
            "Analyse temporelle",
            ui.h3("Analyse temporelle des commandes"),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Distribution des commandes par jour de la semaine"),
                    ui.output_ui("dow_distribution")
                ),
                ui.card(
                    ui.card_header("Distribution des commandes par heure"),
                    ui.output_ui("hour_distribution")
                )
            ),
            ui.card(
                ui.card_header("Heatmap des commandes par jour et heure"),
                ui.output_ui("heatmap_distribution")
            )
        ),
        # Produits populaires
        ui.nav_panel(
            "Produits populaires",
            ui.h3("Analyse des produits les plus populaires"),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Top 20 des produits les plus commandés"),
                    ui.output_ui("top_products")
                ),
                ui.card(
                    ui.card_header("Produits avec le taux de réachat le plus élevé"),
                    ui.output_ui("reorder_rate")
                )
            )
        ),
        # Analyse par catégorie
        ui.nav_panel(
            "Analyse par catégorie",
            ui.h3("Analyse par catégorie de produits"),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Nombre de commandes par rayon"),
                    ui.output_ui("aisle_orders")
                ),
                ui.card(
                    ui.card_header("Nombre de commandes par département"),
                    ui.output_ui("dept_orders")
                )
            ),
            ui.card(
                ui.card_header("Taux de réachat par département"),
                ui.output_ui("dept_reorder")
            )
        ),
        # Comportements d'achat
        ui.nav_panel(
            "Comportements d'achat",
            ui.h3("Analyse des comportements d'achat"),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Taille moyenne du panier par jour de la semaine"),
                    ui.output_ui("basket_size_dow")
                ),
                ui.card(
                    ui.card_header("Taille moyenne du panier par heure de la journée"),
                    ui.output_ui("basket_size_hour")
                )
            )
        ),
        # Recommandations
        ui.nav_panel(
            "Recommandations",
            ui.h3("Recommandations d'achat"),
            ui.page_sidebar(
                ui.sidebar(
                    ui.h4("Paramètres"),
                    ui.input_select("user_id", "Sélectionner un utilisateur", {}),
                    ui.hr(),
                    ui.h4("Produits déjà achetés"),
                    ui.output_ui("user_products")
                ),
                # Contenu principal
                ui.h4("Produits recommandés"),
                ui.output_ui("recommendations"),
                # Indicateur de chargement
                ui.HTML('<div id="loading-recommendations" class="text-center mt-3 d-none"><i class="fa fa-spinner fa-spin fa-3x"></i><p>Calcul des recommandations en cours...</p></div>'),
                ui.tags.script("""
                $(document).on('shiny:outputinvalidated', function(event) {
                    if(event.name === 'recommendations') {
                        $('#loading-recommendations').removeClass('d-none');
                    }
                });
                $(document).on('shiny:value', function(event) {
                    if(event.name === 'recommendations') {
                        $('#loading-recommendations').addClass('d-none');
                    }
                });
                """)
            )
        )
    ),
    ui.p("© 2025 - Analyse des données Instacart", class_="text-center text-muted pt-3"),
    theme=shinyswatch.theme.superhero()
)

# --- Server - Logique de l'application avec gestion d'erreurs et cache ---
def server(input, output, session):
    # Cache manuel pour stocker les résultats de requêtes lourdes
    cache = {}

    # Vue d'ensemble
    @output
    @render.text
    def total_orders():
        try:
            result = run_query("SELECT COUNT(DISTINCT order_id) FROM orders")
            return f"{result.iloc[0, 0]:,}"
        except Exception as e:
            logger.error(f"Erreur dans total_orders: {e}")
            return "Erreur"

    @output
    @render.text
    def total_users():
        try:
            result = run_query("SELECT COUNT(DISTINCT user_id) FROM orders")
            return f"{result.iloc[0, 0]:,}"
        except Exception as e:
            logger.error(f"Erreur dans total_users: {e}")
            return "Erreur"

    @output
    @render.text
    def total_products():
        try:
            result = run_query("SELECT COUNT(*) FROM products")
            return f"{result.iloc[0, 0]:,}"
        except Exception as e:
            logger.error(f"Erreur dans total_products: {e}")
            return "Erreur"

    @output
    @render.text
    def avg_products():
        try:
            query = """
                SELECT AVG(product_count) FROM (
                    SELECT order_id, COUNT(product_id) as product_count
                    FROM order_products_prior
                    GROUP BY order_id
                    LIMIT 10000
                ) as counts
            """
            result = run_query(query)
            return f"{result.iloc[0, 0]:.2f}"
        except Exception as e:
            logger.error(f"Erreur dans avg_products: {e}")
            return "Erreur"

    @output
    @render.ui
    def order_distribution():
        try:
            query = f"""
                SELECT order_count, COUNT(*) as user_count FROM (
                    SELECT user_id, COUNT(*) as order_count
                    FROM orders
                    GROUP BY user_id
                ) as counts
                WHERE order_count >= {input.min_orders()}
                GROUP BY order_count
                ORDER BY order_count
                LIMIT 50
            """
            order_counts = run_query(query)
            fig = px.bar(order_counts, x="order_count", y="user_count",
                         labels={"order_count": "Nombre de commandes", "user_count": "Nombre d'utilisateurs"},
                         title="Nombre d'utilisateurs par nombre de commandes")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans order_distribution: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    # Analyse temporelle
    @output
    @render.ui
    def dow_distribution():
        try:
            dow_orders = run_query(dow_orders_query)
            dow_orders['day_name'] = dow_orders['order_dow'].apply(lambda x: days[x])
            fig = px.bar(dow_orders, x="day_name", y="order_count",
                         labels={"day_name": "Jour de la semaine", "order_count": "Nombre de commandes"},
                         title="Nombre de commandes par jour de la semaine")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans dow_distribution: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def hour_distribution():
        try:
            hour_orders = run_query(hour_distribution_query)
            fig = px.line(hour_orders, x="order_hour_of_day", y="order_count",
                          labels={"order_hour_of_day": "Heure de la journée", "order_count": "Nombre de commandes"},
                          title="Nombre de commandes par heure de la journée")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans hour_distribution: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def heatmap_distribution():
        try:
            heatmap_data = run_query("""
                SELECT order_dow, order_hour_of_day, COUNT(*) as order_count
                FROM orders
                GROUP BY order_dow, order_hour_of_day
            """)
            pivot_df = heatmap_data.pivot_table(index="order_dow", columns="order_hour_of_day", values="order_count", fill_value=0)
            fig = px.imshow(pivot_df,
                            labels=dict(x="Heure de la journée", y="Jour de la semaine", color="Nombre de commandes"),
                            y=[days[i] for i in range(7)],
                            x=[f"{i}h" for i in range(24)],
                            aspect="auto",
                            color_continuous_scale="Viridis")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans heatmap_distribution: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    # Produits populaires
    @output
    @render.ui
    def top_products():
        try:
            top_products_data = run_query(top_products_query)
            fig = px.bar(top_products_data, y="product_name", x="order_count",
                         orientation='h',
                         labels={"product_name": "Produit", "order_count": "Nombre de commandes"},
                         title="Top 20 des produits les plus commandés")
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans top_products: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def reorder_rate():
        try:
            query = """
                SELECT p.product_name,
                       COUNT(*) as order_count,
                       SUM(opp.reordered) as reorder_count,
                       SUM(opp.reordered)::float / COUNT(*) as reorder_rate
                FROM order_products_prior opp
                JOIN products p ON opp.product_id = p.product_id
                GROUP BY p.product_name
                HAVING COUNT(*) > 100
                ORDER BY reorder_rate DESC
                LIMIT 20
            """
            reorder_rate_data = run_query(query)
            fig = px.bar(reorder_rate_data, y="product_name", x="reorder_rate",
                         orientation='h',
                         labels={"product_name": "Produit", "reorder_rate": "Taux de réachat"},
                         title="Top 20 des produits avec le taux de réachat le plus élevé")
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans reorder_rate: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    # Analyse par catégorie
    @output
    @render.ui
    def aisle_orders():
        try:
            query = """
                SELECT a.aisle, COUNT(*) as order_count
                FROM order_products_prior opp
                JOIN products p ON opp.product_id = p.product_id
                JOIN aisles a ON p.aisle_id = a.aisle_id
                GROUP BY a.aisle
                ORDER BY order_count DESC
                LIMIT 20
            """
            aisle_orders_data = run_query(query)
            fig = px.bar(aisle_orders_data, y="aisle", x="order_count",
                         orientation='h',
                         labels={"aisle": "Rayon", "order_count": "Nombre de commandes"},
                         title="Top 20 des rayons les plus populaires")
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans aisle_orders: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def dept_orders():
        try:
            query = """
                SELECT d.department, COUNT(*) as order_count
                FROM order_products_prior opp
                JOIN products p ON opp.product_id = p.product_id
                JOIN departments d ON p.department_id = d.department_id
                GROUP BY d.department
                ORDER BY order_count DESC
            """
            dept_orders_data = run_query(query)
            fig = px.pie(dept_orders_data, values="order_count", names="department",
                         title="Répartition des commandes par département")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans dept_orders: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def dept_reorder():
        try:
            dept_reorder_data = run_query(reorder_rate_by_dept_query)
            fig = px.bar(dept_reorder_data, x="department", y="reorder_rate",
                         labels={"department": "Département", "reorder_rate": "Taux de réachat"},
                         title="Taux de réachat par département")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans dept_reorder: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    # Comportements d'achat - Optimisé
    @output
    @render.ui
    def basket_size_dow():
        try:
            query = """
                WITH order_sizes AS (
                    SELECT o.order_id, o.order_dow, COUNT(opp.product_id) as basket_size
                    FROM orders o
                    JOIN order_products_prior opp ON o.order_id = opp.order_id
                    GROUP BY o.order_id, o.order_dow
                    LIMIT 100000
                )
                SELECT order_dow, AVG(basket_size) as avg_basket_size
                FROM order_sizes
                GROUP BY order_dow
                ORDER BY order_dow
            """
            basket_size_dow_data = run_query(query)
            basket_size_dow_data['day_name'] = basket_size_dow_data['order_dow'].apply(lambda x: days[x])
            fig = px.bar(basket_size_dow_data, x="day_name", y="avg_basket_size",
                         labels={"day_name": "Jour de la semaine", "avg_basket_size": "Taille moyenne du panier"},
                         title="Taille moyenne du panier par jour de la semaine")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans basket_size_dow: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur lors du chargement: {str(e)}</div>")

    @output
    @render.ui
    def basket_size_hour():
        try:
            cache_key = "basket_size_hour"
            if cache_key not in cache:
                logger.info("Exécution de la requête basket_size_hour (pas en cache)")
                basket_size_hour_data = run_query(basket_size_hour_query)
                cache[cache_key] = basket_size_hour_data
            else:
                logger.info("Utilisation du cache pour basket_size_hour")
                basket_size_hour_data = cache[cache_key]
            fig = px.line(basket_size_hour_data, x="order_hour_of_day", y="avg_basket_size",
                          labels={"order_hour_of_day": "Heure de la journée", "avg_basket_size": "Taille moyenne du panier"},
                          title="Taille moyenne du panier par heure de la journée")
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans basket_size_hour: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur lors du chargement: {str(e)}</div>")

    # Recommandations - Corrigé
    @reactive.effect
    def _update_users():
        try:
            users = run_query("SELECT DISTINCT user_id FROM orders LIMIT 100")
            choices = {str(user_id): f"Utilisateur {user_id}" for user_id in users['user_id']}
            ui.update_select("user_id", choices=choices, selected=str(users['user_id'].iloc[0]))
        except Exception as e:
            logger.error(f"Erreur lors du chargement des utilisateurs: {e}")

    @output
    @render.ui
    def user_products():
        if not input.user_id():
            return ui.p("Aucun utilisateur sélectionné")
        try:
            # Requête modifiée pour éviter l'appel à la procédure stockée
            query = """
                SELECT p.product_name
                FROM orders o
                JOIN order_products_prior opp ON o.order_id = opp.order_id
                JOIN products p ON opp.product_id = p.product_id
                WHERE o.user_id = %s
                GROUP BY p.product_name
                ORDER BY COUNT(*) DESC
                LIMIT 20
            """
            user_products_data = run_query(query, params=(input.user_id(),))
            return ui.tags.ul([ui.tags.li(product) for product in user_products_data['product_name']])
        except Exception as e:
            logger.error(f"Erreur dans user_products: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur: {str(e)}</div>")

    @output
    @render.ui
    def recommendations():
        if not input.user_id():
            fig = px.bar()
            return ui.HTML(fig.to_html(full_html=False))
        try:
            cache_key = f"recommendations_{input.user_id()}"
            if cache_key not in cache:
                logger.info(f"Calcul des recommandations pour l'utilisateur {input.user_id()}")
                # Requête remplacée pour éviter l'ambiguïté de colonne
                query = """
                WITH user_products AS (
                    SELECT DISTINCT opp.product_id
                    FROM orders o
                    JOIN order_products_prior opp ON o.order_id = opp.order_id
                    WHERE o.user_id = %s
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
                    AND o.user_id != %s
                    GROUP BY p.product_id, p.product_name
                    HAVING COUNT(*) > 10
                )
                SELECT p.product_name, p.frequency
                FROM potential_products p
                ORDER BY p.frequency DESC
                LIMIT 20
                """
                recommendations_data = run_query(query, params=(input.user_id(), input.user_id()))
                cache[cache_key] = recommendations_data
            else:
                logger.info(f"Utilisation du cache pour les recommandations de l'utilisateur {input.user_id()}")
                recommendations_data = cache[cache_key]

            if recommendations_data.empty:
                return ui.HTML("<div class='alert alert-info'>Aucune recommandation disponible pour cet utilisateur.</div>")

            fig = px.bar(recommendations_data, y="product_name", x="frequency",
                         orientation='h',
                         labels={"product_name": "Produit", "frequency": "Fréquence d'achat"},
                         title="Produits recommandés")
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            return ui.HTML(fig.to_html(full_html=False))
        except Exception as e:
            logger.error(f"Erreur dans recommendations: {e}")
            return ui.HTML(f"<div class='alert alert-danger'>Erreur lors du calcul des recommandations: {str(e)}</div>")

# Création de l'application
app = App(app_ui, server)

if __name__ == "__main__":
    app.run()