# Writing Assistant — API Backend

API FastAPI pour une application d'écriture créative assistée par IA, inspirée de Scrivener. L'utilisateur organise son travail en **sagas** (series), **livres** (books) et **nœuds de manuscrit** (manuscript nodes — un arbre hiérarchique de parties, chapitres, scènes…) rédigés en Markdown. Le contenu est persisté en PostgreSQL puis vectorisé dans ChromaDB pour alimenter un système RAG capable de répondre à des questions sur l'histoire.

## Stack technique

| Couche | Technologie |
|---|---|
| API | FastAPI (async) |
| Base de données relationnelle | PostgreSQL 16 + SQLAlchemy 2 (asyncpg) |
| Authentification | OpenID Connect / JWT (PKCE, compatible Keycloak / Auth0 / Okta) |
| Orchestration IA / chunking | LangChain (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`) |
| Base vectorielle | ChromaDB (client HTTP) |
| Correcteur grammatical | LanguageTool (client HTTP) |
| Migrations | Alembic (async) |

## Structure du projet

```
WrittingAssistantBack/
├── app/
│   ├── main.py                         # Point d'entrée FastAPI (lifespan + routeurs)
│   ├── core/
│   │   ├── auth.py                     # Validation JWT OIDC (cache JWKS)
│   │   ├── config.py                   # Pydantic Settings (variables d'environnement)
│   │   ├── database.py                 # Moteur SQLAlchemy async + dépendance get_db
│   │   └── dependancies.py             # get_book_for_user(), ChatConfig, EmbeddingConfig
│   ├── models/
│   │   ├── book.py                     # ORM — table `books`
│   │   ├── manuscript_node.py          # ORM — table `manuscript_nodes` (arbre auto-référentiel)
│   │   ├── manuscript_node_snapshot.py # ORM — table `manuscript_node_snapshots`
│   │   ├── series.py                   # ORM — table `series`
│   │   ├── conversation.py             # ORM — tables `conversations` + `chat_events`
│   │   ├── book_commit.py              # ORM — table `book_commits`
│   │   └── user.py                     # ORM — table `users`
│   ├── schemas/
│   │   ├── book.py                     # BookCreate / BookUpdate / BookRead
│   │   ├── manuscript_node.py          # ManuscriptNodeCreate / Update / Read
│   │   ├── series.py                   # SeriesCreate / Update / Read
│   │   ├── conversation.py             # Schemas conversations, ChatEventRead, ResumeAgent*
│   │   ├── book_commit.py              # CommitCreate / CommitRead / ManuscriptNodeSnapshotRead
│   │   ├── spellcheck.py               # SpellCheckRequest
│   │   └── user.py                     # UserRead
│   ├── routers/
│   │   ├── auth.py                     # POST /auth/login
│   │   ├── books.py                    # CRUD /books/ + vectorize + query
│   │   ├── manuscript_nodes.py         # CRUD /books/{book_id}/manuscript-nodes/
│   │   ├── series.py                   # CRUD /series/
│   │   ├── chat.py                     # Conversations + chat agentique (stream SSE) + HITL
│   │   ├── book_commits.py             # Versioning par instantané /books_commits/
│   │   ├── spellcheck.py               # Proxy LanguageTool /spellcheck/
│   │   └── dev.py                      # Endpoints de dev (APP_ENV=development uniquement)
│   └── services/
│       ├── rag.py                      # vectorize_book(), query_book()
│       ├── chat.py                     # stream_chat_with_book_history_agentic(), chat_with_book_history_agentic()
│       ├── tools.py                    # make_book_tools() — outils LangChain pour l'agent
│       ├── book_commits.py             # create_commit(), restore_commit()
│       ├── chat_factory.py             # Instanciation LLM (compatible OpenAI)
│       └── embeddings_factory.py       # Instanciation embeddings
├── migrations/                         # Scripts de migration Alembic
│   ├── env.py
│   └── versions/
├── docker-compose.yml                  # PostgreSQL + ChromaDB + LanguageTool + API
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
docker-compose up -d db chromadb languagetool   # Démarrer PostgreSQL + ChromaDB + LanguageTool
bash scripts/init.sh                            # Créer la DB + appliquer les migrations
docker-compose up --build                       # Démarrer l'API
```

L'API est disponible sur `http://localhost:8000`.
La documentation Swagger est accessible sur `http://localhost:8000/docs`.

### En local (développement)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Éditer .env avec les coordonnées PostgreSQL, ChromaDB et LanguageTool

bash scripts/init.sh
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Valeur par défaut | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant` | Connexion PostgreSQL |
| `CHROMA_HOST` | `localhost` | Hôte ChromaDB |
| `CHROMA_PORT` | `8001` | Port ChromaDB |
| `LANGUAGETOOL_HOST` | `localhost` | Hôte LanguageTool |
| `LANGUAGETOOL_PORT` | `8010` | Port LanguageTool |
| `APP_ENV` | `development` | Environnement applicatif (`development` active le router `/dev`) |
| `OIDC_ISSUER_URL` | `http://localhost:8080/realms/writting_assistant` | Fournisseur OIDC (Keycloak par défaut) |
| `OIDC_AUDIENCE` | *(optionnel)* | Claim `aud` du JWT |

## Modèle de données

```
series          ← saga regroupant plusieurs livres
  └── books     ← livre (standalone ou rattaché à une saga, peut être un spin-off)
        ├── manuscript_nodes       ← arbre hiérarchique du manuscrit
        ├── book_commits           ← instantanés du manuscrit (versioning)
        │     └── manuscript_node_snapshots
        └── conversations          ← sessions de chat liées au livre
              └── chat_events      ← événements ordonnés (messages user/IA/outil)
```

### `books`
| Champ | Type | Description |
|---|---|---|
| `series_id` | FK nullable | Saga d'appartenance |
| `parent_book_id` | FK nullable (self) | Lien spin-off → tome parent |
| `position_in_series` | float nullable | Ordre fractionnaire dans la saga |
| `is_spinoff` | bool | `true` pour un spin-off |
| `embedding_model_used` | string nullable | Modèle utilisé lors de la dernière vectorisation |

### `manuscript_nodes`
| Champ | Type | Description |
|---|---|---|
| `front_id` | UUID non-nullable, unique | Identifiant stable côté client. Généré automatiquement par la DB (`gen_random_uuid()`) si absent à la création. Sert de cible FK pour `parent_front_id`. |
| `parent_front_id` | FK UUID nullable (self → `front_id`) | Nœud parent — permet l'imbrication. Mis à `NULL` si le parent est supprimé (`SET NULL`). |
| `node_type` | string | `'part'`, `'chapter'`, `'scene'`, `'interlude'`… |
| `content` | TEXT nullable | Markdown du nœud (`null` pour les nœuds conteneurs comme `'part'`) |
| `position` | float | Fractional indexing parmi les frères/sœurs |
| `is_numbered` | bool | Numérotation affichée |
| `depth_level` | int (défaut 2) | Niveau d'imbrication visuel/logique, maintenu par le client |

### `chat_events`

Table unifiée remplaçant les anciens `chat_messages` + `chat_tool_calls`. Chaque message LangChain de la boucle agentique est stocké comme une ligne, ordonnée par PK `id` (ordre d'insertion).

| Champ | Description |
|---|---|
| `role` | `"user"` \| `"assistant"` \| `"tool"` |
| `content` | Contenu texte (null pour les AIMessages avec uniquement des tool calls) |
| `tool_calls` | JSON `[{id, name, args}]` — présent sur les lignes `role="assistant"` avec appels d'outils |
| `tool_call_id` | ID interne LLM — sur les lignes `role="tool"`, lie le résultat à son appel |
| `tool_name` / `tool_args` | Nom et arguments de l'outil (affichage, lignes `role="tool"`) |
| `status` | `"done"` \| `"pending"` \| `"accepted"` \| `"rejected"` — géré pour le HITL |

## Endpoints

### Sagas

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/series/` | Créer une saga |
| `GET` | `/series/` | Lister les sagas de l'utilisateur |
| `GET` | `/series/{id}` | Détail d'une saga |
| `PUT` | `/series/{id}` | Modifier |
| `DELETE` | `/series/{id}` | Supprimer |

### Livres

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/` | Créer un livre (crée automatiquement un premier chapitre à `position=1000.0`) |
| `GET` | `/books/` | Lister les livres accessibles (publics + les siens) |
| `GET` | `/books/{id}` | Détail d'un livre (inclut la liste des nœuds) |
| `PUT` | `/books/{id}` | Modifier |
| `DELETE` | `/books/{id}` | Supprimer |

### Nœuds de manuscrit

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/{book_id}/manuscript-nodes/` | Créer un nœud |
| `GET` | `/books/{book_id}/manuscript-nodes/` | Lister tous les nœuds (flat, triés par `position`) |
| `GET` | `/books/{book_id}/manuscript-nodes/{node_id}` | Détail d'un nœud (par `id` entier) |
| `PUT` | `/books/{book_id}/manuscript-nodes/{node_id}` | Modifier (par `id` entier) |
| `DELETE` | `/books/{book_id}/manuscript-nodes/{node_id}` | Supprimer (par `id` entier) |
| `GET` | `/books/{book_id}/manuscript-nodes/by-front-id/{front_id}` | Détail d'un nœud (par `front_id` UUID) |
| `PUT` | `/books/{book_id}/manuscript-nodes/by-front-id/{front_id}` | Modifier (par `front_id` UUID) |
| `DELETE` | `/books/{book_id}/manuscript-nodes/by-front-id/{front_id}` | Supprimer (par `front_id` UUID) |
| `PATCH` | `/books/{book_id}/multiple-manuscript-nodes-update` | Créer / modifier / supprimer en batch (updates et deletes identifiés par `front_id`) |

Le front reconstruit l'arbre à partir du champ `parent_front_id` renvoyé. Un nœud appartenant à un autre livre retourne `404`.

### RAG

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/{id}/vectorize` | Vectoriser le manuscrit dans ChromaDB |
| `GET` | `/books/{id}/query?q=...&k=5` | Recherche sémantique brute |

La vectorisation agrège le contenu de tous les nœuds ayant un `content` non null, ordonnés par `position`, puis découpe le texte en chunks (taille=1500, overlap=200).

### Chat agentique / RAG conversationnel

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books/chat/{book_id}/conversations` | Créer une conversation + envoyer le premier message |
| `GET` | `/books/chat/{book_id}/conversations` | Lister les conversations |
| `DELETE` | `/books/chat/{book_id}/conversations/{id}` | Supprimer une conversation |
| `GET` | `/books/chat/{book_id}/conversations/{id}/messages` | Tous les événements d'une conversation |
| `GET` | `/books/chat/{book_id}/conversations/{id}/timeline` | Idem, ordonné par id (usage front-end) |
| `POST` | `/books/chat/{book_id}/conversations/{id}/messages` | Envoyer un message (stream SSE possible) |
| `POST` | `/books/chat/{book_id}/conversations/{id}/resume-agent` | Accepter ou rejeter une proposition HITL |
| `POST` | `/books/chat/{book_id}/conversations/{id}/resume-stream` | Reprendre le stream après une décision HITL |

Les requêtes de chat nécessitent les headers `X-Chat-Provider`, `X-Embedding-Provider` (et optionnellement `X-Chat-API-Key`, `X-Chat-Model`, etc.).

#### Flux Human-In-The-Loop (HITL)

Lorsque l'agent décide de proposer une modification du manuscrit (`propose_node_edit` ou `propose_new_node`) :

1. Le stream émet un événement SSE `human_in_the_loop` avec `db_id` et les arguments de la proposition, puis se ferme.
2. Le client appelle `POST .../resume-agent` avec `tool_call_id=db_id` et `user_decision="accept"|"reject"`.
3. Le client appelle `POST .../resume-stream` — l'agent reprend là où il s'est arrêté.

### Versioning (Book Commits)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/books_commits/{book_id}/commits` | Créer un instantané du manuscrit |
| `GET` | `/books_commits/{book_id}/commits` | Lister les commits |
| `GET` | `/books_commits/{book_id}/commits/{commit_id}` | Détail d'un commit |
| `GET` | `/books_commits/{book_id}/commits/{commit_id}/nodes` | Nœuds sauvegardés dans le commit |
| `POST` | `/books_commits/{book_id}/commits/{commit_id}/restore` | Restaurer le manuscrit à cet état |
| `DELETE` | `/books_commits/{book_id}/commits/{commit_id}` | Supprimer un commit |

Un commit est automatiquement créé avant toute modification HITL acceptée (`create_commit(book, "Pre-AI edit snapshot", db)`).

### Correcteur grammatical (Spellcheck)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/spellcheck/check` | Vérifier un texte via LanguageTool |
| `GET` | `/spellcheck/languages` | Lister les langues supportées |

Ces endpoints nécessitent un token d'authentification.

## Pipeline RAG

1. `POST /books/` — crée le livre + un nœud "First Chapter" à `position=1000.0`
2. L'utilisateur remplit le contenu via `PUT /books/{id}/manuscript-nodes/{node_id}`
3. `POST /books/{id}/vectorize` :
   - Collecte les nœuds avec `content IS NOT NULL`, ordonnés par `position`
   - Concatène : `# {titre}\n\n{contenu}` par nœud
   - Découpe via `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` (chunk_size=1500, overlap=200)
   - Indexe dans ChromaDB (collection `book_{id}_{embedding_model}`)
4. `POST /books/chat/{id}/conversations` — chat RAG agentique avec historique de conversation

## Contrôle d'accès

| Ressource | Règle |
|---|---|
| Series | Privées — `series.user_id == user_id` |
| Book | Public si `user_id IS NULL`, sinon `book.user_id == user_id` |
| ManuscriptNode | Hérite du livre parent via la dépendance `get_book_for_user()` |

L'authentification OIDC est optionnelle sur la plupart des routes (les livres publics restent accessibles sans token). Les endpoints `/spellcheck/` requièrent obligatoirement un token.

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
