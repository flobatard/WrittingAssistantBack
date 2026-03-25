# Writing Assistant — API Backend

API FastAPI pour une application d'écriture créative assistée par IA, inspirée de Scrivener. L'utilisateur rédige son livre en Markdown ; le texte est persisté en PostgreSQL puis vectorisé dans ChromaDB pour alimenter un système RAG capable de répondre à des questions sur l'histoire.

## Stack technique

| Couche | Technologie |
|---|---|
| API | FastAPI (async) |
| Base de données relationnelle | PostgreSQL 16 + SQLAlchemy 2 (asyncpg) |
| Orchestration IA / chunking | LangChain (`MarkdownTextSplitter`) |
| Base vectorielle | ChromaDB (persistance locale) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) |

## Structure du projet

```
WrittingAssistantBack/
├── app/
│   ├── main.py              # Point d'entrée FastAPI (lifespan + routeurs)
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (variables d'environnement)
│   │   └── database.py      # Moteur SQLAlchemy async + dépendance get_db
│   ├── models/
│   │   └── book.py          # ORM SQLAlchemy — table `books`
│   ├── schemas/
│   │   └── book.py          # Schémas Pydantic (Create / Update / Read)
│   ├── routers/
│   │   └── books.py         # Endpoints CRUD + vectorisation
│   └── services/
│       └── rag.py           # vectorize_book() — chunking + ingestion ChromaDB
├── migrations/              # Scripts de migration Alembic
│   ├── env.py               # Configuration Alembic (async + création DB auto)
│   └── versions/            # Fichiers de migration générés
├── chroma_data/             # Données ChromaDB (gitignorées)
├── docker-compose.yml       # PostgreSQL + API conteneurisés
├── requirements.txt
├── .env.example
└── Dockerfile
```

## Démarrage rapide

### Prérequis

- Docker & Docker Compose **ou** Python 3.12+ avec un PostgreSQL accessible

### Avec Docker Compose (recommandé)

```bash
cp .env.example .env
docker-compose up -d db      # Démarrer PostgreSQL
docker-compose up -d chromadb     # Démarrer PostgreSQL
bash scripts/init.sh         # Créer la DB + appliquer les migrations
docker-compose up --build    # Démarrer l'API
```

L'API est disponible sur `http://localhost:8000`.
La documentation Swagger est accessible sur `http://localhost:8000/docs`.

### En local (développement)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Éditer .env avec les coordonnées PostgreSQL

bash scripts/init.sh         # Créer la DB + appliquer les migrations
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

Copier `.env.example` en `.env` et adapter les valeurs :

| Variable | Valeur par défaut | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant` | Connexion PostgreSQL |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | Dossier de persistance ChromaDB |
| `APP_ENV` | `development` | Environnement applicatif |

## Endpoints

### Livres — CRUD

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/` | Créer un livre (titre + contenu Markdown) |
| `GET` | `/books/` | Lister tous les livres |
| `GET` | `/books/{id}` | Récupérer un livre par ID |
| `PUT` | `/books/{id}` | Mettre à jour un livre |
| `DELETE` | `/books/{id}` | Supprimer un livre |

### RAG — Vectorisation

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/{id}/vectorize` | Découper le Markdown en chunks et les indexer dans ChromaDB |

La réponse de `/vectorize` retourne :

```json
{
  "collection_name": "book_1_sentence_transformers_all_MiniLM_L6_v2",
  "chunks_count": 42
}
```

## Modèle de données

```python
class Book(Base):
    id: int                        # Clé primaire
    title: str                     # Titre du livre
    content: str                   # Contenu Markdown brut
    embedding_model_used: str|None # Modèle utilisé pour la vectorisation
    created_at: datetime
    updated_at: datetime
```

## Pipeline RAG

1. `POST /books/` — sauvegarde le texte Markdown en PostgreSQL
2. `POST /books/{id}/vectorize` :
   - Découpe le contenu via `MarkdownTextSplitter` (chunk_size=500, overlap=50)
   - Crée ou met à jour une collection ChromaDB nommée `book_{id}_{embedding_model}`
   - Met à jour le champ `embedding_model_used` sur le livre

Chaque collection ChromaDB est isolée par combinaison livre + modèle d'embedding.

## Base de données

Gérée par **Alembic**. Les tables ne sont jamais créées automatiquement au démarrage.

```bash
# Appliquer toutes les migrations
alembic upgrade head

# Générer une nouvelle migration après modification d'un modèle
alembic revision --autogenerate -m "description"
```

## Scripts

| Script | Description |
|---|---|
| `bash scripts/init.sh` | Crée la base (si absente) puis applique `alembic upgrade head` |
| `bash scripts/drop.sh` | Supprime la base (demande confirmation) |
| `python scripts/init_db.py` | Crée la base uniquement |
| `python scripts/drop_db.py` | Supprime la base uniquement |

Tous les scripts lisent la configuration depuis `DATABASE_URL` (via `app.core.config`).