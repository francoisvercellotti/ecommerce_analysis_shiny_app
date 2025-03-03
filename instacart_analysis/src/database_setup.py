import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

def create_db_engine():
    """Crée et retourne une connexion à la base de données PostgreSQL."""
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    return create_engine(connection_string)

def import_data(data_dir):
    """Importe les données CSV dans PostgreSQL."""
    engine = create_db_engine()

    # Liste des fichiers à importer
    files = {
        'aisles.csv': 'aisles',
        'departments.csv': 'departments',
        'products.csv': 'products',
        'orders.csv': 'orders',
        'order_products__prior.csv': 'order_products_prior',
        'order_products__train.csv': 'order_products_train'
    }

    for file, table_name in files.items():
        file_path = os.path.join(data_dir, file)
        if os.path.exists(file_path):
            print(f"Importation de {file} vers la table {table_name}...")

            # Pour les fichiers volumineux, nous utilisons une approche par chunks
            if file in ['order_products__prior.csv', 'order_products__train.csv', 'orders.csv']:
                chunk_size = 100000
                chunks = pd.read_csv(file_path, chunksize=chunk_size)

                for i, chunk in enumerate(chunks):
                    if i == 0:
                        # Première chunk: remplacer la table existante
                        chunk.to_sql(table_name, engine, if_exists='replace', index=False)
                    else:
                        # Chunks suivantes: ajouter à la table
                        chunk.to_sql(table_name, engine, if_exists='append', index=False)

                    print(f"  Importé chunk {i+1} de {file}")
            else:
                # Pour les petits fichiers, importation en une seule fois
                df = pd.read_csv(file_path)
                df.to_sql(table_name, engine, if_exists='replace', index=False)

            print(f"Importation de {file} terminée.")
        else:
            print(f"Fichier {file_path} introuvable.")

if __name__ == "__main__":
    data_dir = os.getenv("DATA_DIR", "./data")
    import_data(data_dir)
    print("Importation des données terminée.")