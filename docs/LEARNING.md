# ShopAgent-OS — Learning Log

This file tracks architecture decisions, concepts, and interview prep as the project is built. It's for understanding, not just documentation.

## Phase 1 — Local MVP

### Step 1: FastAPI backend scaffold
- **FastAPI chosen for:** Pydantic-native validation (same typed-data idea LangGraph state reuses later), async support (LLM/vector DB calls are I/O-bound), auto-generated `/docs`.
- **Layer boundary:** FastAPI owns the HTTP boundary only (routing, validation, auth, CORS). LangGraph owns agent orchestration only and knows nothing about HTTP — it's invoked by FastAPI, never the reverse. This lets the same agent be called from a CLI or test with zero FastAPI involvement.

### Step 2: Mock store data
- `products.json` / `orders.json` / `policies.md` stand in for a real backend. The rest of the app (search, tools, agent) doesn't know or care whether data comes from a file, Postgres, or Shopify — that's the point of the `StoreAdapter` pattern (formalized in Phase 8).
- Policies are Markdown (prose), not JSON, because they'll be chunked and semantically searched (RAG) later — JSON structure would fight against that.

### Step 3: Product search (deterministic filtering)
- Plain field filtering (`category`, `price`, `color`, keyword substring) — no ML, no embeddings.
- **Search vs. RAG distinction:** structured filtering works when data has clean fields to filter on (price, category). RAG is for unstructured prose with no field to filter on (policy text). Don't reach for RAG when a `WHERE` clause equivalent already solves the problem.
- Query understanding (turning "red running shoes under $80" into `keyword="running", color="red", max_price=80`) is deliberately kept separate from the filtering function itself — one does NLP/LLM work, the other is pure deterministic logic, and mixing them would make filtering untestable without an LLM.

### Concept: Schema matching across different store backends
**Problem:** Shopify/WooCommerce/custom stores each use different field names and shapes for the same concept (`title` vs `name`, nested `variants[0].price` vs flat `price`, `inventory_quantity` vs boolean `in_stock`).

**Solution — canonical schema + adapters (anti-corruption layer pattern):**
- Define one internal `Product`/`Order` schema (Pydantic model) that search, the agent, and the LLM prompt are always written against.
- Each backend gets an adapter whose only job is translating its native format into that canonical shape. `search_products()` never changes when a new backend is added — only a new adapter is written.

**Is ML used for the field mapping itself?**
- For *documented* platforms (Shopify, WooCommerce): no — hand-written deterministic mapping, because the schema is known, fixed, and mistakes here affect price/stock correctness. ML would trade certainty for nothing.
- For *unknown* custom stores (`CustomStoreAdapter` onboarding): yes, in practice — embedding similarity between field names, or an LLM proposing a mapping from a data sample. This is the real field of "schema matching" (classic algorithms: Cupid, Similarity Flooding, COMA; modern default: LLM-proposed mapping).
- **Critical rule:** ML/LLM-assisted mapping is used once, at integration setup time, with a human confirming it. The approved mapping is then saved as fixed, deterministic code/config — it never re-runs the ML step live per request. Same principle as "the LLM never queries the database directly": non-deterministic models draft configuration, they don't make live decisions in a path touching money, inventory, or orders.

### Candidate tools for future CustomStoreAdapter (Phase 8/9) — not used yet
Evaluated three real PyPI packages for automated schema matching, verified against actual PyPI metadata:
- **Valentine** — column-to-column matching between two tabular datasets (pandas DataFrames), string + embedding-based. Good fit for: merchant uploads a flat CSV/DB export with unknown headers, we propose column mappings with confidence scores for human confirmation.
- **pyJedAI** — despite looking similar, its real purpose is **Entity Resolution** (are two records the same real-world entity, e.g. de-duping two product catalogs), not column/schema matching. Different problem: rows vs. columns.
- **schema-matching** (XGBoost + sentence-transformers) — closest actual fit to "match column meanings across tables," but pulls in PyTorch via sentence-transformers — a heavy dependency for a capability with no current use case.

**Key limitation for our case:** all three assume flat tabular input. Shopify/WooCommerce APIs return nested JSON (e.g. `variants[0].price`), which none of these tools handle natively — an LLM-proposed mapping (human-confirmed, then frozen into deterministic adapter code) is the better mechanical fit for nested API sources. These packages become relevant only for the flat-CSV/DB-export flavor of `CustomStoreAdapter`, and only when that component actually gets built — not before.

### LLM-proposed schema mapping (Groq) — implemented in `backend/app/adapters/llm_schema_matcher.py`
Makes the earlier schema-matching discussion concrete: given one sample record from an unknown source, ask the LLM to propose which canonical field (`id`, `name`, `price`, `category`, `in_stock`, `description`) each source field maps to, with a confidence score and reasoning — a human reviews low-confidence proposals before they become permanent adapter code.

Key implementation decisions:
- `canonical_field` is typed `Optional[Literal[...]]` in the Pydantic response model — constrains the LLM's answer space at the schema level, not just via prompt wording.
- Groq's `response_format={"type": "json_object"}` is *best-effort* JSON mode (guarantees parseable JSON, not a specific shape). Only GPT-OSS and Qwen models on Groq support *strict* schema mode (guaranteed shape). Either way, **Pydantic validates the response after the fact** — never trust an LLM's "structured" output blindly, even when explicitly asked for a JSON shape; validate it like any other untrusted external response.
- `temperature=0` — this is a classification-like task, not creative generation; want the most reproducible answer.

**Real bugs hit and fixed while wiring this up (worth remembering):**
1. **Secret leaked into the wrong file.** The real Groq API key was pasted into `backend/.env.example` (a template meant to be committed) instead of `backend/.env` (git-ignored). Caught before any commit happened by checking `git status`/`git ls-files`. Lesson: `.env.example` must only ever contain empty/placeholder values, and it's worth a `git status` check after handling any secret, since `.gitignore` only protects the exact filename `.env` — a similarly-named file like `.env.example` gets no protection at all.
2. **`groq` SDK / `httpx` version mismatch.** Pinning `groq==0.11.0` without pinning `httpx` let pip install the newest `httpx` (0.28.1), which had removed a constructor argument (`proxies`) that the old `groq` SDK still passed internally → `TypeError` at client construction. Fixed by upgrading `groq` to the current release (1.7.0) rather than pinning `httpx` backward. Lesson: version mismatches between a thin SDK wrapper and its own HTTP dependency are a common source of confusing errors that have nothing to do with your code's logic.
3. **Model ID no longer exists.** `llama-3.3-70b-versatile` (a real Groq model as of its docs at some point) returned `404 model_not_found` for this account — Groq's lineup had shifted to `openai/gpt-oss-*` and Qwen models. Fixed by calling `client.models.list()` to get the *live* list directly from the API instead of trusting a docs page or a remembered model name. Lesson: for any LLM provider, hardcoded model IDs go stale — providers deprecate and rename models on their own schedule; a robust integration should tolerate or verify this rather than assume a name from a tutorial still works.

### Step 5 (in progress): Policy chunking with a structure-aware + fallback strategy
`backend/app/services/policy_rag.py` — `chunk_policies()` handles two realistic shapes of policy documents:
- **Structure-aware chunking** (`_chunk_by_heading`): splits on `## ` markdown headings via `re.split()` with a capturing group — the captured heading text is preserved in the split result, alternating with the content that follows it. Best quality when a document has natural section boundaries.
- **Fixed-size chunking with overlap** (`_chunk_fixed_size`): fallback for documents with no detectable structure (a real possibility — many stores just paste one long paragraph). Slides a window of `chunk_size` characters forward by `chunk_size - overlap` each step, so the tail of one chunk reappears at the head of the next — this prevents a sentence that falls exactly on a cut boundary from losing meaning in every chunk it appears in.
- Every chunk gets a `store_id` tag regardless of which strategy produced it — chunking is a per-store operation (each store has its own policy text), and this is the field that will let a future vector store isolate one store's chunks from another's (see multi-tenancy note below).
- Document **format** (PDF/HTML/docx) vs. document **structure** (headings vs. wall of text) are different problems — format normalization ("loading") is deferred to Phase 8/9 when real stores are onboarded; structure-handling was worth solving now since even our own mock pipeline would break on a headingless doc otherwise.

### Concept: Multi-tenancy in RAG (isolating each store's data)
Since the widget passes a `storeId` per request, retrieval must be scoped to that store only. Two standard approaches:
- **Shared vector collection + metadata filter** (`WHERE store_id = X`) — simpler ops, but a missed filter anywhere is a cross-tenant data leak.
- **Separate collection per store** — isolated by construction, safer default, more collections to manage at scale.
Decision: lean toward per-store collections when this is actually implemented (Phase 8, alongside `StoreAdapter`), since a data leak between stores is a serious trust failure, not just a bug. For now (one mock store), the cheap forward-compatible move is just threading `store_id` through function signatures/chunk metadata today, without building real per-tenant storage yet.

### Step 5 complete: Embeddings + Chroma vector search
Model: `all-MiniLM-L6-v2` (sentence-transformers, 384-dim, chosen for speed/simplicity over `bge-small` since retrieval-tuning advantages don't show up at 5 chunks/store). Vector DB: Chroma, in-process, `hnsw:space: cosine` to match the embedding model's normalized vectors.

Verified end-to-end with real queries:
- "can I return this item" → top match "Return Policy" (0.652), second "Refund Policy" (0.366) — semantic match, not keyword overlap (neither query word appears verbatim in the policy text).
- "do you ship internationally" → matched "Shipping Policy" (0.455) even though the actual policy answer is "no" — retrieval finds *relevant* text, it doesn't judge whether the answer is favorable; phrasing the actual answer from that grounded text is the LLM's job (Step 6+).
- "what is the weather today" → zero results — the `min_similarity=0.3` cutoff correctly rejected an unrelated query instead of returning the "closest but still irrelevant" chunk. This is the grounding guardrail working, not just a theoretical design.

Known gap, deferred on purpose (same pattern as order lookup's missing ownership check): `load_policy_text()` always reads the single mock `policies.md` regardless of `store_id` — correct for one store, a placeholder for real multi-store lookup later.

### Concept: purpose-built decision APIs vs. general LLM classification (not adopted — noted for later)
Encountered `~typesafe/jev-latest` on OpenRouter: not a chat model — a "Decisions API" that takes a `state` (text/object) plus typed `questions` and returns calibrated answers (`noul` = yes/no probability, `choice` = pick from options, `score` = position on a rubric), explicitly for routing/ranking/verification rather than free-text generation.

Directly relevant in shape to problems we have: intent routing (a `choice` call) and future guardrails/human-handoff (`noul`/`score` calls). Not adopted for Phase 1 because: (1) it's a 6-day-old alpha endpoint with zero shown usage — unproven; (2) it's a proprietary non-standard API shape, not the OpenAI-compatible interface the rest of the LLM layer uses — adopting it for core routing would be real vendor lock-in, conflicting with the project's "keep the LLM layer provider-independent" principle; (3) it would shortcut past the actual learning goal of Step 6 (understanding conditional routing/tool-calling ourselves). Worth revisiting later, once mature, purely as a comparison point: general-purpose LLM + prompt vs. purpose-built calibrated classifier, for routing/guardrail-style decisions specifically.

### Step 6 complete: LangGraph tool-calling agent
`backend/app/agent/tools.py` wraps the three existing services as LangChain `@tool`-decorated functions (thin wrappers, business logic stays in `services/`). `backend/app/agent/graph.py` wires them into the canonical ReAct-style graph: `agent` node (LLM with tools bound via `ChatGroq(...).bind_tools()`) → conditional edge (`tools_condition` prebuilt: does the last AI message request a tool call?) → `tools` node (`ToolNode` prebuilt, executes the call) → loops back to `agent` so the LLM sees the result and produces a final grounded answer.

Design decisions:
- `store_id` is hardcoded inside the tool wrapper (not an LLM-fillable parameter) — the model should never decide tenant/security-scoping values; those come from trusted request context. Same principle as the deferred order-ownership check.
- System prompt explicitly instructs "answer using only tool results, never invent details" — belt-and-suspenders on top of the structural fact that tools are the only path to real data.

**Two real bugs hit and fixed (both instructive, not just noise):**
1. **Tool description didn't match the actual data schema.** Asked "red running shoes under $80," the LLM called `search_products(category="running shoes", ...)` — but our real categories are `shoes`/`electronics`/`home`/`fitness`; "running" is a *tag*, not a category. Silent zero-result failure, no crash, just wrong behavior. Fixed by constraining `category` to `Literal["shoes", "electronics", "home", "fitness"]` in the tool's type hint — same lesson as constraining `canonical_field` in the schema-matcher: restrict the LLM's answer space at the schema level, don't just hope the prompt wording is clear enough.
2. **Empty tool results crashed the whole agent.** An empty list `[]` returned from a tool became the `ToolMessage`'s `content` as a literal Python list object (not text) — Groq's API rejects tool-role messages whose content is an empty list or non-string. This isn't just a fluke of this one query — it would crash on *any* legitimately empty result ("no products found" is a normal, valid outcome). Fixed by having every tool explicitly return `json.dumps(result)` — a string, always — rather than relying on the framework to auto-serialize Python objects into message content. Reinforces something already true structurally: tool output is *text* handed to the LLM, so tools should own producing that text themselves rather than trusting an implicit framework conversion.

Verified against all three flagship examples from the project's original design conversation ("Where is my order ORD1001?", "red running shoes under $80", a return-policy question) — all three produced correct, grounded answers end-to-end.

### Step 7 complete: `/chat` FastAPI endpoint — Phase 1 core pipeline done
`POST /chat` — thin wrapper: `ChatRequest{message}` in, `run_agent(message)` called, `ChatResponse{reply}` out. Two decisions worth remembering:
- **Plain `def`, not `async def`.** `run_agent()` is synchronous under the hood (Groq's SDK does blocking HTTP calls). Declaring the endpoint `async def` while calling blocking code inside it would freeze FastAPI's single event loop for every concurrent request during each LLM call — worse than just using `def`, which FastAPI automatically runs in a thread pool. Async only helps when the code inside is *also* genuinely async — it's not a blanket performance switch.
- **Broad `except Exception` at the API boundary**, returning a fixed generic message. This is the outermost edge of the whole system; letting a raw exception escape here risks leaking internal details (stack traces, paths, partial API responses) to whoever's calling the endpoint. Deliberate boundary hygiene, not defensive over-coding.

Verified: real chat request returns a grounded answer, missing `message` field returns FastAPI's automatic 422 validation error, `/health` still works alongside it.

**This completes Phase 1's original 9-step roadmap**: FastAPI scaffold → mock data → product search → policy RAG → order tool → LangGraph tool-calling agent → chat API. End-to-end flow now matches the architecture sketched in the very first message of this project.

## Phase 1 Wrap-up — Interview Questions (whole pipeline)

**Basic**
1. What are the 4 layers of ShopAgent-OS's architecture, and what does each one own?
2. What's the concrete difference between a "workflow" and an "agent" in this codebase specifically (point to the actual mechanism)?
3. Why does the LLM never touch `products.json`/`orders.json`/`policies.md` directly?
4. What are the three tools the agent has, and what does each one do?
5. Why is chunking necessary before embedding a document for RAG?

**Intermediate**
1. Trace "Can I return my order ORD1004?" end-to-end — does the agent need one tool call or two to answer this *correctly* (hint: ORD1004 is cancelled)?
2. Why was real per-store data isolation (`StoreAdapter`) deliberately deferred instead of built during Phase 1?
3. Two different bugs (schema mapping, product search) were both fixed by constraining an LLM's output space with types rather than prompt wording alone — what's the general lesson?
4. Why is `store_id` hardcoded in the tool wrapper instead of being an agent-decided value?
5. What would you have to change to swap Groq for a different LLM provider today? What wouldn't need to change?

**Architecture**
1. Walk through the full request lifecycle from the (not-yet-built) widget down to the LLM and back, naming every layer and file involved.
2. List at least 3 gaps in this system that were deliberately deferred rather than fixed, and why each was deferred rather than fixed now.
3. If 100 concurrent users hit `/chat` right now, what would actually happen? (Consider: FastAPI's thread pool for sync `def` endpoints, and the module-level `_collection_cache`/`_embedding_model` singletons in `policy_rag.py` — are they safe under concurrent access on a cold start?)

## Interview Questions — Step 6

**Basic**
1. What does `tools_condition` actually check to decide whether to route to the `tools` node or `END`?
2. Why does `ToolNode` loop back to `agent` instead of going straight to `END`?
3. Why must a tool's return value be JSON-serialized to a string rather than returned as a raw Python object?
4. What's the difference between the system prompt's "don't invent details" instruction and the structural fact that tools are the only source of real data? Why have both?
5. Why is `openai/gpt-oss-20b`'s lack of parallel tool-calling support irrelevant to this agent's design?

**Intermediate**
1. Why is `store_id` hardcoded inside the tool wrapper instead of exposed as an LLM-fillable parameter?
2. Walk through why `category="running shoes"` produced a silent empty result rather than an error — where exactly did that mismatch happen?
3. What would happen if the system prompt were removed entirely — what's the actual risk, concretely?
4. Why does `MessagesState`'s reducer (`add_messages`) matter here — what would break if state updates replaced the list instead of appending to it?

**Architecture**
1. Trace the exact node-by-node path through the graph for "Where is my order ORD1001?" — which nodes fire, in what order, and what does the state look like after each one?
2. This agent can only call one tool per user turn (gpt-oss-20b has no parallel tool-calling). What's a realistic question that would need *two* tool calls to answer well, and how would the current graph handle it (or fail to)?
3. If we wanted to add a fourth tool tomorrow (say, a "check discount code" tool), what exactly would need to change, and what wouldn't?

## Interview Questions — Steps 4-5

**Basic**
1. Why does `get_order_status()` return `{"error": ...}` instead of raising an exception when an order isn't found?
2. What does `normalize_embeddings=True` do, and why does it matter for cosine similarity?
3. Why is `all-MiniLM-L6-v2` a reasonable choice here instead of a larger model like `all-mpnet-base-v2`?
4. What does the `_embedding_model`/`_collection_cache` module-level caching avoid re-doing on every call?
5. What does `min_similarity` protect against, concretely?

**Intermediate**
1. Why is `store_id` threaded through `chunk_policies`/`retrieve_policy` even though it's not really used yet?
2. What's the tradeoff between fixed-size chunking with overlap and heading-based chunking? When would you pick each?
3. Chroma returns "distance," not "similarity" — what's the conversion, and why does the cosine-space configuration matter for that conversion to be correct?
4. Why wasn't a "generate the final answer" step built into `policy_rag.py` itself?
5. What security gap exists in the order lookup tool today, and why was it deliberately left for later rather than fixed now?

**Architecture**
1. Why is per-store vector isolation (metadata filter vs. separate collections) a harder problem than per-store SQL row filtering would be, and which approach was chosen here and why?
2. Trace what happens, end to end, if a user asks "can I return my order" — which functions get called, in what order, and where does the LLM enter the picture (or not) at each stage?
3. If we swapped Chroma for Qdrant later, which files would need to change, and which wouldn't? Why?

## Interview Questions — Steps 1-3

**Basic**
1. What is FastAPI responsible for in this architecture, and what is it explicitly *not* responsible for?
2. Why is `products.json` read via a path relative to the file's own location instead of a relative string like `"data/products.json"`?
3. What's the difference between structured filtering (Step 3) and RAG?
4. Why does `search_products()` always enforce `in_stock`, even if the caller didn't ask for it?
5. Why is `policies.md` a Markdown file instead of JSON?

**Intermediate**
1. Why is "parsing the user's natural language into filters" kept separate from the filtering function itself?
2. What problem does the `StoreAdapter` pattern solve, concretely?
3. Why wasn't the `StoreAdapter` abstraction built in Step 2/3, even though we know Shopify is coming later?
4. What's the difference between a *shape* mismatch and a *capability* mismatch between two store backends? Give an example of each.
5. Why shouldn't schema-matching ML run live, per-request, instead of once at setup time?

**Architecture**
1. Trace the layers a request passes through for "Where is my order ORD1001?" and explain why the LLM never touches order data directly.
2. If we swapped `products.json` for a real Shopify store tomorrow, which files would need to change, and which would stay untouched? Why?
3. What's the tradeoff between a fully deterministic adapter (hand-written) and an ML-assisted one, and when is each the right choice?
