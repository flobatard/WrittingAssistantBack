✍️ Writing Assistant : L'IA au service de la narration

Writing Assistant est un environnement d'écriture créative "Scrivener-like", conçu pour les auteurs modernes qui souhaitent allier le confort du Markdown à la puissance de l'Intelligence Artificielle. Plus qu'un simple éditeur, c'est un compagnon de route capable de comprendre l'intégralité d'un manuscrit pour répondre à des questions complexes sur l'intrigue, les personnages ou la cohérence du récit.
🏗️ Une Architecture "RAG-Native"

Le cœur du projet repose sur un système de RAG (Retrieval-Augmented Generation). Contrairement à une IA classique qui oublie le début du livre au fur et à mesure de l'écriture, Writing Assistant indexe chaque paragraphe de manière sémantique.

    Stockage Hybride : Les textes sont persistés de manière robuste dans PostgreSQL (via SQLAlchemy async), tandis que leur "sens" est extrait et stocké dans ChromaDB, une base de données vectorielle locale.

    Vectorisation à la demande : Un service dédié découpe le Markdown en morceaux (chunks) et les projette dans un espace vectoriel. Chaque livre possède sa propre collection, isolée par modèle d'embedding, garantissant une précision chirurgicale lors des recherches de contexte.

💻 Le Stack Technique
Backend : La performance avec FastAPI

L'API est propulsée par FastAPI, exploitant l'asynchronisme complet de Python pour garantir une réactivité maximale.

    Orchestration : Gestion fine des schémas via Pydantic.

    Migrations : Suivi rigoureux de l'évolution de la base de données avec Alembic.

    Conteneurisation : Un écosystème Docker complet (Postgres, ChromaDB, API) pour un déploiement et un développement simplifiés.

Frontend : L'avant-garde avec Angular 21

Le client est une application Angular 21 de dernière génération, utilisant les composants Standalone et les Signals pour une gestion d'état fluide et moderne.

    Expérience d'écriture : Intégration de Monaco Editor (le moteur derrière VS Code) pour offrir une coloration syntaxique Markdown et une sensation de frappe professionnelle.

    Performance (SSR) : Utilisation d'Angular Universal (Server-Side Rendering) pour optimiser le premier rendu et le SEO.

    Interface : Un design split-view (Éditeur / Chat IA) pensé pour la productivité, utilisant SCSS et la méthodologie BEM.

🔐 Sécurité et Interopérabilité

Le projet adopte une approche SSO Agnostique basée sur le standard OpenID Connect (OIDC). En utilisant Keycloak en développement, l'application est prête à être connectée à n'importe quel fournisseur d'identité (Auth0, Okta, etc.) sans modification du code source. Le flux d'authentification privilégie la sécurité avec le support du protocole PKCE, protégeant les échanges même dans un environnement navigateur.
🚀 En résumé

Writing Assistant n'est pas qu'un outil d'écriture ; c'est une vitrine technologique mêlant IA générative, développement asynchrone et architecture logicielle robuste. C’est la preuve qu’on peut construire un outil métier complexe tout en restant sur les versions les plus récentes et performantes des frameworks actuels.