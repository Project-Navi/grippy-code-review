# Knowledge Graph

Grippy builds a knowledge graph of your codebase that persists across PRs. It tracks files, reviews, findings, rules, and authors as graph nodes connected by typed edges --- giving Grippy memory that most AI code review tools either lack entirely or lock behind paid tiers ($20--38/seat/month at CodeRabbit, Greptile, and Qodo).

## Data Model

The graph stores 5 node types and 6 edge relationships:

### Nodes

| Type | Represents | Created when |
|---|---|---|
| `FILE` | Source code file | Codebase indexing |
| `REVIEW` | Single PR review run | Review starts |
| `FINDING` | Code issue or recommendation | Review extraction |
| `RULE` | Deterministic security rule | First rule match |
| `AUTHOR` | PR submitter | PR event |

### Edges

| Relationship | Direction | Meaning |
|---|---|---|
| `IMPORTS` | file → file | Python import dependency |
| `FOUND_IN` | finding → file | Finding location |
| `VIOLATES` | finding → rule | Finding matched a security rule |
| `PRODUCED` | review → finding | Review generated this finding |
| `TOUCHED` | review → file | File was in the PR diff |
| `AUTHORED` | author → review | Author submitted the reviewed PR |

## Pipeline Integration

The graph integrates at 4 points in the review pipeline. All are non-fatal --- if any fail, the review proceeds without graph context.

**Phase 1: Codebase Indexing.** After embedding the repo into LanceDB, Grippy walks Python files, extracts imports via `ast.parse`, and upserts `FILE` nodes with `IMPORTS` edges. This builds the dependency graph.

**Phase 2: Review Start.** Creates `AUTHOR` and `REVIEW` nodes, then `TOUCHED` edges for each file in the PR diff. This establishes the audit trail before the LLM runs.

**Phase 3: Pre-Review Context.** The context builder queries the graph for three signals:
- **Blast radius** --- walks `IMPORTS` edges incoming to changed files to find dependent modules
- **Recurring findings** --- checks for prior `FOUND_IN` edges on touched files
- **Author risk** --- traverses author → reviews → findings to aggregate historical severity patterns

These are formatted and injected into the LLM prompt as `<graph-context>` (capped at 2,000 chars).

**Phase 4: Post-Review Persistence.** After the review completes, findings are persisted as `FINDING` nodes with `FOUND_IN`, `PRODUCED`, and (where applicable) `VIOLATES` edges. History observations are appended to touched file nodes.

## Technical Details

- **Storage:** SQLite with WAL journal mode, foreign key enforcement, and 5-second busy timeout. Lives at `$GRIPPY_DATA_DIR/navi-graph.db`.
- **Deterministic IDs:** Node IDs are `TYPE:sha256[:12]`, edge IDs are full SHA-256 of the canonical triple. Same input always produces the same ID.
- **Bounded traversal:** BFS walks enforce `max_depth`, `max_nodes`, and `max_edges` limits. Returns a `TraversalReceipt` explaining any truncation.
- **Observations:** Append-only atomic facts on nodes (e.g., file review history). Normalized and deduplicated by content.
- **No vectors in graph:** The graph is structural only. Vector embeddings stay in the LanceDB codebase index.
- **Future-portable:** The `GraphStore` protocol allows swapping SQLite for a remote backend (e.g., Cloudflare D1) without changing business logic.
