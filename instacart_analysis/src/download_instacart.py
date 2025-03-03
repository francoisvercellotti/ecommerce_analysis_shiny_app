import os
import kagglehub
import zipfile
import shutil

# Créer le dossier data s'il n'existe pas
os.makedirs("./data", exist_ok=True)

# Télécharger le dataset
print("Téléchargement du dataset Instacart...")
path = kagglehub.dataset_download("yasserh/instacart-online-grocery-basket-analysis-dataset")
print(f"Dataset téléchargé dans : {path}")

# Vérifier le contenu du répertoire téléchargé
print(f"Contenu du répertoire téléchargé:")
for file in os.listdir(path):
    print(f"- {file}")
    file_path = os.path.join(path, file)

    # Si c'est un fichier zip, l'extraire
    if file.endswith('.zip'):
        print(f"Extraction de {file}...")
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall("./data")
    # Sinon, copier directement le fichier vers data
    elif os.path.isfile(file_path) and file.endswith('.csv'):
        print(f"Copie de {file} vers ./data...")
        shutil.copy(file_path, os.path.join("./data", file))

# Vérifier si des sous-dossiers contiennent des fichiers CSV
for root, dirs, files in os.walk(path):
    for file in files:
        if file.endswith('.csv'):
            src_path = os.path.join(root, file)
            dest_path = os.path.join("./data", file)
            print(f"Copie de {src_path} vers {dest_path}...")
            shutil.copy(src_path, dest_path)

# Lister les fichiers dans le dossier data
print("\nFichiers disponibles dans ./data:")
files_in_data = os.listdir("./data")
for file in files_in_data:
    print(f"- {file}")

if not files_in_data:
    print("Aucun fichier trouvé dans ./data. Copie manuelle des fichiers...")
    # Copie manuelle depuis l'emplacement du cache
    all_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            all_files.append((os.path.join(root, file), file))

    for src_path, filename in all_files:
        if os.path.isfile(src_path):
            print(f"Copie de {src_path} vers ./data/{filename}...")
            shutil.copy(src_path, os.path.join("./data", filename))

    # Vérifier à nouveau
    print("\nFichiers disponibles dans ./data après copie manuelle:")
    for file in os.listdir("./data"):
        print(f"- {file}")

print("\nTéléchargement et extraction terminés. Les données sont prêtes à être importées dans PostgreSQL.")