# Architecture

Ce document décrit l'architecture réelle du projet (vérifiée sur le commit `4e31a67`, branche `phase8-multi-specs`). Il ne mentionne que ce qui est implémenté et fonctionnel aujourd'hui.

---

## Vue d'ensemble

```
Spec (MD/PDF)
       │
       ▼
┌──────────────┐
│   Analysis   │  Reader → Cleaner → ChunkingManager → SpecAnalyzer(LLM) → SpecParser
│              │  Modèle : qwen/qwen3.6-35b-a3b
│              │  Seuil chunking auto : 25 600 tokens (32k × 0.8)
└──────────────┘
       │
       ▼
┌──────────────┐
│    Agents    │  6 agents orchestrés par LangGraph
│              │  Supervisor (déterministe) → Requirement → TestDesign → Coverage
│              │  → Review → StoreMemory (stub)
└──────────────┘
       │
       ▼
┌──────────────┐
│   Reports    │  Rapports Markdown + JSON dans validation/reports/
└──────────────┘
       │
       ▼
┌──────────────┐
│  Validation  │  CLI, métriques, campagnes reproductibles
└──────────────┘
```

---

## Couches détaillées

### 1. LLM (`src/llm/`)

| Fichier | Rôle |
|---|---|
| `settings.py` | Lecture et validation des variables d'environnement. Whitelist `ia.sofiasolutions.io` obligatoire — pas de bypass. |
| `client.py` | Client unique découplé d'OpenAI, injecté via `Settings` |
| `exceptions.py` | Traduction propre des erreurs API |

### 2. Analysis (`src/analysis/`)

Pipeline complet : `Reader → Cleaner → ChunkingManager → SpecAnalyzer → SpecParser`

| Fichier | Rôle |
|---|---|
| `reading/reader.py` | `TextReader` (.md, .txt) et `PdfReader` (.pdf via pymupdf/pypdf) |
| `cleaning/cleaner.py` | Normalise CRLF, supprime caractères de contrôle, réduit lignes vides |
| `chunking/config.py` | `ChunkingConfig` : seuil = 32k tokens × 0.8 marge = 25 600 tokens |
| `chunking/estimator.py` | `TokenEstimator` : estimation ~4 chars/token |
| `chunking/strategy.py` | 2 stratégies : `FixedSizeChunkingStrategy` (découpage par taille) et `MarkdownSectionStrategy` (découpage par titres ##) |
| `chunking/chunker.py` | `DocumentChunker` : applique la stratégie choisie |
| `chunking/manager.py` | `ChunkingManager.decide(text, force_mode)` : décide DIRECT vs CHUNKED |
| `chunking/merger.py` | `AnalysisMerger` : fusionne N analyses de chunks en une seule `ParsedSpecification` ; dédup en 2 temps (code-first `RGxx-yy`/`Mxx-yy`/`UC_...`/`EX_...`/`IHM...` + clustering cosinus des embeddings en fallback, seuil 0.95) ; garde-fou anti-sur-fusion par codes de message `Mxx-yy` disjoints ; `document_title` prioritaire sur le titre des chunks |
| `analyzer.py` | `SpecAnalyzer` : appelle le LLM avec le system prompt d'analyse |
| `parser.py` | `SpecParser` : transforme le JSON LLM en `ParsedSpecification` ; parse strict puis réparation automatique via `json_repair` si le JSON est malformé |
| `pipeline.py` | `AnalysisPipeline` : orchestre tout le pipeline, gère le chunking avec try/except par chunk ; tire le `document_title` du nom de fichier (prioritaire à la fusion) ; logging/timing par chunk, checkpoints disque et `limit_chunks` (debug) ; `LLM_MAX_RETRIES` configurable |
| `models.py` | `ParsedSpecification`, `ChunkingDecision`, `DocumentChunk`, etc. |
| `exceptions.py` | `DocumentReadError` et autres exceptions du module |

### 3. Agents (`src/agents/`)

6 agents enregistrés dans `AgentRegistry`, 6 nœuds dans le graphe LangGraph.

| Agent | Fichier | Modèle LLM | NodeType | Statut |
|---|---|---|---|---|
| `SupervisorAgent` | `supervisor.py` | Aucun (déterministe) | `SUPERVISOR` | Actif |
| `RequirementAgent` | `requirement.py` | `qwen/qwen3.6-35b-a3b` | `REQUIREMENT` | Actif |
| `TestDesignAgent` | `test_design.py` | `qwen/qwen3.6-35b-a3b` | `TEST_DESIGN` | Actif |
| `CoverageAgent` | `coverage.py` | `qwen/qwen3.6-35b-a3b` | `COVERAGE` | Actif |
| `ReviewAgent` | `review.py` | `google/gemma-4-26b-a4b` | `REVIEW` | Actif |
| `StoreMemoryAgent` | `store_memory.py` | Aucun | `STORE_MEMORY` | Actif (stub — persistance prévue Phase 9) |

Infrastructure partagée :

| Fichier | Rôle |
|---|---|
| `base.py` | `AgentBase` — classe de base (pas d'appel LLM, injection de dépendances) |
| `executor.py` | `AgentExecutor` — exécute les appels LLM avec retry/backoff et fallback |
| `router.py` | `ModelRouter` — associe chaque `TaskType` à un modèle LLM |
| `registry.py` | `AgentRegistry` — associe chaque `NodeType` à une classe d'agent |
| `node_executor.py` | `NodeExecutor` — exécute un nœud LangGraph avec traçage automatique |

**Stubs (4 fichiers, 0 imports dans le repo) :**
- `analysis_agent.py` — prévu pour Phase future
- `business_rules.py` — prévu pour Phase future
- `edge_cases.py` — prévu pour Phase future
- `knowledge.py` — prévu pour Phase future

**Dossier orphelin :** `src/agent/` (sans 's') — vide, jamais importé.

### 4. Workflow (`src/graph/`)

| Fichier | Rôle |
|---|---|
| `workflow.py` | Définit le `StateGraph` LangGraph : START → Supervisor → Agents → END |
| `conditions.py` | `get_next_node(state)` : lit `supervisor_decision.next_node` pour router |

Le Supervisor suit un ordre fixe : `[REQUIREMENT, TEST_DESIGN, COVERAGE, REVIEW, STORE_MEMORY]`. Chaque agent retourne vers le Supervisor après exécution. `STORE_MEMORY` mène à `END`.

### 5. Models (`src/models/`)

| Fichier | Rôle |
|---|---|
| `node_types.py` | `NodeType` (enum, 10 valeurs), `SupervisorDecision`, `ExecutionContext`, `AgentDependencies` |
| `graph_models.py` | `AgentState`, `ExecutionStep` |
| `agent_models.py` | `TestCaseModel`, `TestStepModel`, `TestType`, `TestCaseStatus`, `TestSuiteModel` |

### 6. Reports (`src/reports/`)

| Fichier | Rôle |
|---|---|
| `analysis.py` | `AnalysisReport` (importé par `graph_models.py`) |
| `coverage.py` | `CoverageReport`, `CoverageBreakdown` |
| `requirement.py` | `RequirementReport` |
| `review.py` | `ReviewReport` |
| `test_design.py` | `TestDesignReport` |

### 7. Validation (`validation/`)

| Fichier | Rôle |
|---|---|
| `__main__.py` | Point d'entrée CLI (`--scenario`, `--spec-path`, `--chunk-mode`, `--pages`, `--dry-run`) |
| `config.py` | `ValidationConfig` — configuration de campagne |
| `scenarios.py` | `VALIDATION_SCENARIOS` — 5 scénarios (dont 3 synthétiques Phase 8) |
| `metrics.py` | `collect_metrics()` — pipeline + workflow + métriques LLM + qualité |
| `report.py` | `generate_markdown_report()`, `generate_json_report()` |
| `extract_pages.py` | Extraction de pages PDF pour les scénarios |

---

## Ce qui n'est pas encore implémenté

| Élément | État |
|---|---|
| `src/memory/` | Stub (modèles vides) |
| `src/api/main.py` | Stub (squelette vide) |
| `src/db/` | Vide |
| RAG | Pas implémenté |
| API FastAPI | Pas implémentée |
| Dashboard UI | Pas implémenté |
| Multi-provider LLM | Pas implémenté |
| Dédup sémantique des requirements (`Mxx-yy` comme codes d'exigence) | Partiellement — fusion code-first implémentée ; prompt renforcé en test |

Ces éléments sont prévus dans la roadmap (Phases 9-13) mais ne doivent pas être considérés comme existants.