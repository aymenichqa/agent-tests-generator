# 🧪 Value IT — Agentic Test Case Generation

Agent IA de génération de cas de tests QA à partir d'une spécification fonctionnelle, avec workflow multi-agents **LangGraph**.

## 📸 Aperçu

| Dashboard Angular | Agents LangGraph | Rapport généré |
|-------------------|------------------|----------------|
| ![Dashboard](./screens/dashboard-home.png) | ![Agents](./screens/agents-page.png) | ![Rapport](./screens/rapport-validation.png) |

> 👉 Ajoute tes captures d'écran dans le dossier `screens/` pour illustrer la vitrine.

## 🏗️ Architecture

Le workflow est orchestré par un **graphe LangGraph** déterministe :

```text
Spécification (MD/PDF)
        │
        ▼
Pipeline d'analyse (Reader → Cleaner → Chunking → SpecAnalyzer → SpecParser)
        │
        ▼
Supervisor LangGraph
        │
        ├─► Requirement Agent  (extraction des exigences)
        ├─► TestDesign Agent   (conception des cas de tests)
        ├─► Coverage Agent     (vérification de la couverture)
        ├─► Review Agent       (revue qualité)
        └─► StoreMemory Agent  (persistance — stub)
        │
        ▼
Rapport QA (Markdown / JSON)
```

## 🤖 Agents implémentés (`src/agents/`)

| Agent | Fichier | Rôle | Modèle LLM |
|-------|---------|------|------------|
| Supervisor | `supervisor.py` | Orchestration et routage déterministe | — (déterministe) |
| Requirement | `requirement.py` | Extraction des exigences fonctionnelles | qwen/qwen3.6-35b-a3b |
| TestDesign | `test_design.py` | Conception des scénarios de tests (cas nominaux, limites, erreurs) | qwen/qwen3.6-35b-a3b |
| Coverage | `coverage.py` | Vérification de la couverture des exigences | qwen/qwen3.6-35b-a3b |
| Review | `review.py` | Revue qualité des cas de tests générés | google/gemma-4-26b-a4b |
| StoreMemory | `store_memory.py` | Persistance en mémoire (stub) | — |

### Infrastructure partagée

- `base.py` — classe de base `AgentBase`
- `executor.py` — exécution LLM avec retry/backoff
- `router.py` — routage des modèles par type de tâche
- `registry.py` — registre des agents par `NodeType`
- `node_executor.py` — exécution d'un nœud LangGraph avec traçage

## 📁 Structure du dépôt

```text
agent-tests-vitrine/
├── README.md                 # Ce fichier
├── ARCHITECTURE.md           # Guide d'architecture détaillé
├── ROADMAP.md                # Feuille de route
├── .env.example              # Exemple de configuration (à renommer .env)
├── pyproject.toml            # Dépendances Python (Poetry)
├── .gitignore                # Fichiers exclus du dépôt
├── screens/                  # Captures d'écran de la vitrine
│   ├── dashboard-home.png
│   ├── agents-page.png
│   └── rapport-validation.png
├── docs/                     # Documentation complémentaire
└── src/
    ├── agents/               # 6 agents LangGraph + infrastructure
    ├── graph/                # StateGraph + conditions de routage
    ├── models/               # Modèles Pydantic / dataclasses
    ├── llm/                  # Client LLM, settings, exceptions
    └── prompts/              # Prompts des agents
```

## 🚀 Installation rapide

```bash
# Cloner le dépôt
git clone https://github.com/TA_USERNAME/agent-tests-vitrine.git
cd agent-tests-vitrine

# Installer les dépendances
poetry install

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec ta clé API LLM

# Lancer l'API (si conservée)
poetry run uvicorn src.api.main:app --reload --port 8000
```

## 🗺️ Roadmap

Voir `ROADMAP.md` pour les phases prévues (RAG, API complète, dashboard Angular, multi-provider LLM, etc.).

---

Construit avec ❤️ par Aymen Ichqarrane — Value IT