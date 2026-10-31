# Roadmap

Ce document liste les étapes réalisées et celles prévues. État vérifié au 2026-08-09.

---

## Réalisé — Phase 0 à Phase 8

### Phase 8 — Multi-Specs + Chunking + Audit (2026-07-28 → 2026-08-09)

**En cours — Étape 2 (related_features / shared_entities) en préparation.** 46 commits sur `phase8-multi-specs` (22 sur Phase 8 seule).

| # | Réalisation | Statut |
|---|---|---|
| 1 | Specs synthétiques créées (LibraryManagement, RoomReservation, LibraryManagement_LONG) | ✅ |
| 2 | `ChunkingManager.decide(force_mode)` — forçage direct/chunks/auto | ✅ |
| 3 | Connexion `--chunk-mode` CLI → pipeline | ✅ |
| 4 | Calcul déterministe des scores de couverture (REQ/RG/EX) | ✅ (fixé en `7ec5dc9`) |
| 5 | Gestion d'erreur par chunk individuel (try/except) | ✅ |
| 6 | `chunk_count` exposé dans les métriques | ✅ |
| 7 | `TestDesignAgent` switché sur `qwen/qwen3.6-35b-a3b` (modèle stable) | ✅ |
| 8 | Audit complet (194 tests, 33 fichiers actifs, whitelist sécurité) | ✅ |
| 9 | Documentation mise à jour (README, ARCHITECTURE, ROADMAP, CHANGELOG, VALIDATION) | ✅ |
| 10 | Test d'intégration chunking sur spec longue réelle (`SPEC_Value_IT.pdf`, 493 pages) | ✅ 55/55 chunks, 0 échec |
| 11 | Mise à jour des 3 tests échoués (mocks obsolètes) | ✅ (suite complète verte le 2026-08-04) |
| 12 | Instrumentation pipeline : logging par chunk, timing, checkpoints disque, `limit_chunks` | ✅ |
| 13 | Dédup sémantique code-first + fallback embeddings dans `AnalysisMerger` | ✅ (business_rules 99.3 % cross-run) |
| 14 | Prompt `requirements` renforcé (citation exacte des IDs source) | ✅ (100 % structuré sur 5 chunks, recall vérifié) |
| 15 | `LLMClient.embed()` + seuil configurable `LLM_MAX_RETRIES` | ✅ |
| ⬜ | **Étape 2 — related_features / shared_entities / KnowledgeAgent** | En préparation |
| ⬜ | Mesure de stabilité cross-run `requirements` sur 55 chunks (nouveau prompt) | À faire |

### Phase 7 — Audit & Corrections (2026-07-28)

**Terminé.** 8 commits, tag `phase7-complete`.

| # | Correctif | Priorité |
|---|---|---|
| 1 | Whitelist de sécurité LLM : `ia.sofiasolutions.io` seule URL autorisée | CRITIQUE |
| 2 | Bug store_memory : le nœud ne s'exécutait jamais (`conditions.py`) | CRITIQUE |
| 3 | Parsing JSON incohérent dans ReviewAgent | HAUTE |
| 4 | Code mort supprimé (`nodes.py` — 85 lignes inutilisées) | MOYENNE |
| 5 | `datetime.now()` sans fuseau horaire (`node_types.py`) | MOYENNE |
| 6 | Classes `Test*` renommées (`TestCase` → `TestCaseModel`, etc.) | BASSE |
| 7 | Accolades dans chaînes JSON gérées (`json_parser.py`) | BASSE |
| 8 | `except Exception` documentés (`metrics.py`) | BASSE |

### Infrastructure (Phase 0 → Phase 6)

| Couche | Détail |
|---|---|
| LLM | `LLMClient`, `Settings` + whitelist sécurité, découplé d'OpenAI |
| Analysis | Reader, Cleaner, SpecAnalyzer, SpecParser, Pipeline |
| Chunking | `ChunkingManager`, 2 stratégies, `AnalysisMerger` |
| Agents | 6 agents (dont StoreMemory stub) + infrastructure (Executor, Router, Registry) |
| Workflow | LangGraph `StateGraph` (Supervisor → 4 agents LLM → StoreMemory → END) |
| Reports | 5 générateurs de rapports |
| Validation | Framework, CLI, scénarios, métriques |
| Tests | 208 tests (hors appels réseau) — suite complète verte |

---

## Prochaines étapes

### Phase 9 — RAG & Mémoire

StoreMemoryAgent devient réel. Le système retient du contexte entre les runs.

**Travail :**
- Implémenter `src/memory/models.py`
- Créer `src/memory/retrieval.py`
- Connecter les agents à la mémoire

### Phase 10 — API HTTP

Exposer le pipeline via FastAPI. Persistance PostgreSQL + pgvector.

**Travail :**
- Implémenter `src/api/main.py`
- Ajouter les modèles Pydantic
- Gérer la persistance

### Phase 11 — Dashboard UI

Interface Angular pour visualiser les résultats et lancer le pipeline.

### Phase 12 — Supervisor LLM

Supervisor piloté par LLM (décisions dynamiques, boucles de correction).

### Phase 13 — Multi-Provider

Supporter plusieurs fournisseurs de LLM.

---

## Métriques (post-Phase 8, 2026-08-09)

| Métrique | Valeur | Source |
|---|---|---|
| Tests collectés | 208 | pytest (hors appels réseau) |
| Tests passants | 208 | pytest |
| Tests échoués | 0 | Suite complète verte (2026-08-09) |
| Ruff violations | 0 | ruff 0.15.21 (règles par défaut) |
| Fichiers actifs | 33 | Audit section 1 |
| Stubs | 6 | Phases 9-13 |
| Code mort | 1 | `src/agent/__init__.py` |
| Sécurité | Whitelist active | `ia.sofiasolutions.io` seul autorisé, 0 bypass |
| Stabilité `business_rules` cross-run | 99.3 % | run3 → run5, seuil 0.95 |