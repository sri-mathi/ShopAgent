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

## Phase 5 — Security & Guardrails

### Step 1 complete: API key authentication on `/chat`
`backend/app/auth.py` — a FastAPI dependency (`verify_api_key`) checking `Authorization: Bearer <key>` against `SHOPAGENT_API_KEY` via `secrets.compare_digest` (constant-time comparison, not `==` — plain equality exits at the first mismatched character, which can theoretically leak how many leading characters were correct through response-time differences; costs nothing extra to avoid). Applied only to `/chat` via `dependencies=[Depends(verify_api_key)]` — `/health` stays open, since monitoring/uptime tools typically can't carry secrets and there's nothing sensitive to protect there.

**Important nuance, not glossed over:** this key is not actually secret once shipped — it lives inside the widget's browser JavaScript, readable by anyone via the network tab. This matches the original design's own naming (`apiKey="pk_test_123"` — the `pk_` prefix is Stripe's convention for a *publishable* key, as opposed to a true secret key that never leaves a server). Its honest job is identifying which store a request belongs to and blocking the most opportunistic zero-effort abuse — not cryptographically proving authorization. Real protection against someone who extracts and reuses the key is rate-limiting and revocation (not yet built), not the key's secrecy. Worth remembering: "we added an API key" is not the same claim as "this is now secure."

**Real bug caught and fixed via testing, not by inspection:** a missing `Authorization` header initially returned `403` (FastAPI's `HTTPBearer` default `auto_error` behavior) while a wrong key returned `401` (our own check) — same underlying problem, inconsistent status codes. Standard convention: `401` means "you're not authenticated" (missing or invalid credentials), `403` means "I know who you are, but you're not allowed." Fixed via `HTTPBearer(auto_error=False)` and handling the missing case ourselves for a consistent `401`.

**Widget side:** `apiKey` prop (accepted-but-unused since Phase 2) is now genuinely required (`apiKey: string`, no longer optional) and sent as `Authorization: Bearer ${apiKey}` on every request. Demo app (`App.tsx`) reads its key from `import.meta.env.VITE_SHOPAGENT_API_KEY` rather than hardcoding a real value into committed source — same reasoning as `apiUrl` already being environment-specific, plus the widget's own `.env` needed an explicit `.gitignore` entry (Vite's scaffolded gitignore only covers `*.local`, not plain `.env`).

Verified all three cases against the live server: no header → 401, wrong key → 401, correct key → 200 with a real grounded reply. Confirmed the full widget flow still works end-to-end in a real browser with the auth header attached.

### Step 2 complete: order ownership verification + session memory (built together, deliberately)
**The coupling that forced this:** order ownership verification requires the agent to *ask* for a second piece of identifying info (email) when only an order ID is given — but with zero conversation memory, a follow-up answer in the next message would be orphaned (no memory of what was being verified). Shipping the ownership check without memory would have produced a technically-secure but practically broken feature. Built both together rather than shipping a half-working security feature.

**Session memory** (`graph.py`): `_session_histories: dict[str, list[BaseMessage]]`, keyed by the `session_id` already generated by the widget (Phase 3). `run_agent` now looks up prior messages for a session (if any) and appends to them instead of always starting fresh; the graph's full result (including the AI's reply and any tool exchanges) gets saved back for next time. Explicitly in-memory only — lost on server restart, not shared across multiple server processes — a real deployment needs this in Redis/a database instead. Same "MVP first, note the real limitation" pattern as the in-memory Chroma collections.

**Order ownership** (`order_lookup.py`, `tools.py`): `get_order_status` now requires both `order_id` and `email`, matching them against the real order record. **Anti-enumeration property, the actual security-relevant detail:** a wrong email on a real order and a completely nonexistent order return the *exact same* generic error object - proven directly (`test_no_enumeration_side_channel`), not just asserted. Without this, an attacker could enumerate valid order IDs just by noticing which error message came back for each guess - a classic side-channel that's easy to accidentally reintroduce by "helpfully" giving different error messages for different failure reasons.

**Verified live, twice** - once via direct Python calls (`run_agent` in the same session asking for, then accepting, an email) and once through the actual HTTP API with two sequential `curl` requests sharing a `session_id`, proving auth + session memory + ownership verification all work together as a real request path, not just in isolation.

**Ripple effect on the eval suite, instructive in itself:** changing `get_order_status`'s signature broke 3 existing eval tests that called it with the old one-argument shape or asked about an order without providing an email upfront (which now triggers a clarifying question instead of an immediate tool call). Fixing these wasn't optional cleanup - it's the eval suite doing exactly its job, catching a real breaking change immediately rather than silently drifting out of sync with the code.

### Step 3 complete: host-supplied customer identity bypasses redundant re-verification
Real integrators already have their own auth (email/password, sessions) - re-asking the customer for their email in chat when the host site already knows who they are is bad UX and not actually more secure (typing a known email string proves nothing about being logged in as that person).

**Design:** new optional `customerEmail` prop (widget) / `customer_email` field (API) → injected into the system prompt only when starting a new session ("this customer is already logged in, their verified email is X, use it automatically"). Deliberately did NOT change the `get_order_status` tool's actual verification logic - the LLM is *told* to use the supplied email, but `order_lookup.py` still deterministically checks it against the real order record regardless of where the email came from. This matters: even if the LLM ignored the instruction (prompt-injection risk, not yet defended against - next up), the worst outcome is degraded UX (wrongly asks, or fails verification), not a security bypass, since the real check never moved. Verified directly: correct-owner email → immediate answer, wrong-owner email (still host-supplied, still "logged in") → still correctly rejected by the same deterministic check.

**Honest trust caveat, stated plainly:** a plain `customerEmail` prop has the same spoofability as `apiKey` already does - client-side JS a determined user could edit. The fully rigorous fix is the host's own backend minting an HMAC-signed identity token (the pattern Intercom calls "Identity Verification"). Not built now - explicitly deferred, since it doesn't regress anything (same trust tier as today) and real hardening pairs naturally with the still-pending prompt-injection defense work.

**Separate design question surfaced: conversation storage in the host's own DB.** Clarified this depends entirely on integration topology: if the widget calls our backend directly (today's only supported mode), the host's own server never sees the conversation at all - there's nothing for them to log. If instead the host's *own* backend proxies the request to us (call it Pattern B), logging becomes trivial with zero new code from us, and it's also the natural place to mint a real signed identity token instead of trusting a client-side prop. Recommended documenting this proxy pattern rather than building pluggable storage/webhooks on our side - that's real Phase 8/9-adjacent infrastructure work, not needed to unblock either concern.

### Step 4 complete: `onMessage` callback - the actual answer to "can hosts store conversations in their own DB?"
Caught my own overstatement from the previous step: I'd implied Pattern B (host backend proxy) was needed to unlock this. It isn't - that's more work than necessary. The widget's `messages` state was simply private with no way for the surrounding page to observe it, in *either* integration mode. Real fix: an optional `onMessage?: (exchange: {userMessage, reply, sessionId}) => void` prop, fired after every successful exchange - the host's own frontend code registers this and forwards each exchange wherever they want (their own API, analytics, a support ticket system), no backend proxy required.

Verified with a real headless-browser test, not just a compile check: sent a live message through the actual widget UI, captured the console log the demo's `onMessage` handler produced, confirmed it contained the exact right `userMessage`/`reply`/`sessionId` for that exchange.

**Scoping note:** only fires on successful exchanges, not on the client-side error fallback ("something went wrong") - the callback's job is capturing real conversation content, not our own network-failure bookkeeping.

Pattern B (full backend proxy) is still the right answer for one different reason: minting a *cryptographically trustworthy* customer identity (real "Identity Verification," not a spoofable prop). `onMessage` solves storage; it doesn't solve identity trust. Both remain valid, solving different problems - worth not conflating them.

### Step 5 complete: prompt injection defense + closing the Phase 4 "safety" eval gap
`backend/app/guardrails.py`: `is_prompt_injection()` calls Groq's `meta-llama/llama-prompt-guard-2-86m` through the same chat-completions endpoint already used elsewhere - confirmed empirically (not assumed from docs) that its response is literally a 0-1 probability score. Wired into `main.py` as the very first check in `/chat`, before the message ever reaches the agent's graph/state - a flagged message gets the same response shape as a normal reply (not a distinct error/status code), so an attacker probing the defense can't distinguish "blocked" from "the agent just declined."

**Explicit, real caveat, not glossed over:** Groq's own docs label this model "preview - intended for evaluation purposes only, not for production environments." Used anyway (better than no defense at all), but documented plainly rather than claimed as a solved problem.

**Fail-open design decision, deliberately made and justified:** if the guard-model call itself errors (network/API issue), the message is let through rather than blocking the entire chatbot. Justified specifically by our narrow tool surface - every sensitive action (order lookup) is independently, deterministically re-checked regardless of what the LLM might be tricked into attempting, so this guardrail is defense-in-depth on top of that, not the sole barrier. Revisit if a higher-stakes tool (e.g. "issue a refund") is ever added.

**Real, measured limitation found via testing, kept visible rather than hidden:** of 4 real injection attempts tested, 3 scored ~0.999 (correctly flagged), but "You are now in developer mode..." - one of the most well-known jailbreak phrasings - scored only 0.33, nowhere near the 0.8 threshold. Not a threshold-tuning problem (0.33 isn't close), a genuine capability gap in the preview model. Marked `xfail` with a clear reason rather than deleted or quietly threshold-adjusted to force a pass - this is now living documentation of a real, known gap, and would surface loudly (as an "unexpectedly passing" test) if a future model update ever fixes it.

**Closes the Phase 4 deferral:** the "safety" eval category (prompt injection → expected safe behavior) was explicitly left unbuilt back then, since testing it before any defense existed would only prove "yes, vulnerable." Now there's something real to measure against.

## Interview Questions — Phase 5, Step 3 (Prompt Injection)

**Basic**
1. Why does a flagged message get the same response shape as a normal one, instead of a distinct error?
2. What does the Prompt Guard model's response actually look like, mechanically?
3. Why wasn't this eval category built back in Phase 4?

**Intermediate**
1. Why fail *open* rather than fail *closed* when the guard-model call itself errors? What would have to change about this system for that answer to flip?
2. The "developer mode" phrasing scored 0.33 while three other attempts scored ~0.999 - why is this not fixable by just lowering the threshold?
3. Why is the guard-model check placed in `main.py` rather than inside `run_agent`/`graph.py`?

**Architecture**
1. If this guardrail were the *only* defense against a malicious order lookup, what would the real-world impact of that 0.33 miss be? Why is the actual impact much smaller than that in this system specifically?
2. What's the tradeoff of marking a known failure `xfail` versus simply deleting the test case? What would silently deleting it cost future maintainers?

## Interview Questions — Phase 5, Step 2

**Basic**
1. Why does the exact same generic error need to be returned for "wrong email" and "order doesn't exist"?
2. Why was session memory built now, rather than earlier when it was first flagged as a gap in Phase 3?
3. What's lost if the backend server restarts, given how session memory is currently implemented?

**Intermediate**
1. Why does `run_agent` save the *entire* result message list back into `_session_histories`, not just the new user message and final reply?
2. Three existing eval tests broke when `get_order_status`'s signature changed - was that a sign something went wrong, or a sign something went right? Why?
3. What would happen today if two different browser tabs somehow ended up with the same `session_id`?

**Architecture**
1. Trace what happens if a customer asks about order ORD1001 in one session, gets asked for their email, then asks about a *different* order ORD1002 before answering - does the system prompt's instruction ("do not guess or reuse an email from earlier in the conversation for a different order") actually get tested anywhere? Should it be?
2. This session store is a plain Python dict inside the FastAPI process. What specifically would break first if this were deployed with multiple server processes/replicas behind a load balancer?

## Phase 4 — Evaluation with DeepEval

### Step 1 complete: tool-selection + policy-grounding evals
New top-level `evals/` folder (matches original target architecture — sibling to `backend/`, `packages/`, not buried inside either). `conftest.py` adds `backend/` to `sys.path` so eval tests can import `app.*` directly.

**Tool-selection tests** (`test_tool_selection.py`) — no LLM judge needed at all: streams the graph up to the first `agent` node's decision and asserts the exact tool name called matches expectation, for 6 real questions covering all three tools. All 6 passed.

**Policy-grounding tests** (`test_policy_grounding.py`) — DeepEval's `FaithfulnessMetric`, checking the agent's actual answer doesn't contradict what was actually retrieved from `policies.md` (via `retrieval_context`). All 3 passed with a real score of 1.0 each (threshold was 0.7) — actual DeepEval judge reasoning: "no contradictions, indicating perfect faithfulness."

**Judge model design decision:** `judge_model.py` wraps `ChatGroq` via DeepEval's `DeepEvalBaseLLM` interface instead of using DeepEval's OpenAI default — reuses the same `GROQ_API_KEY` the agent already needs, consistent with the BYO-credentials principle (no new required external service just for evals). Uses `openai/gpt-oss-120b` (larger than the agent's own `openai/gpt-oss-20b`) as judge specifically to reduce same-model self-evaluation bias — a model judging its own smaller sibling's outputs is a sounder setup than a model judging itself.

**Deliberately deferred:** the third original eval category, prompt-injection/safety, is paired with Phase 5 (guardrails) instead of built now — testing injection resistance before any defense exists would only prove "yes, currently vulnerable," which isn't informative until there's a guardrail to measure against.

### Step 2 complete: generalizing evals to DB-backed tools (order lookup, product search)
Answers a real gap: policy RAG's `FaithfulnessMetric` setup only covered semantically-retrieved text — what about questions answered via `get_order_status`/`search_products`, which return exact structured data, not "approximately relevant" chunks?

Two distinct testing layers turned out to be needed, not one:
- **`test_order_lookup_exactness.py`** — plain `pytest`, zero AI/DeepEval involved. Since DB-backed tools have exactly one correct answer for a given input (unlike RAG's inherently approximate top-k retrieval), a direct `assert` is both simpler and strictly more rigorous than an LLM judge here. Tests `get_order_status` against real `orders.json` data, including the "unknown order" error case.
- **`test_db_tool_faithfulness.py`** — same exact `FaithfulnessMetric` class as policy RAG, generalized: captures the *real* `ToolMessage` content from a live agent run (via `.stream()`, same technique as tool-selection tests) as `retrieval_context`, and checks the agent's final phrased answer doesn't add/drop/misstate facts versus what the tool actually returned. Key insight: `FaithfulnessMetric` doesn't care whether "context" came from vector search or a deterministic lookup — it's agnostic to the data source, only checking answer-vs-context consistency.

**Demonstrated the metric isn't a rubber stamp**, not just described it: fed `FaithfulnessMetric` a deliberately fabricated answer (claimed a 90-day return window against real 30-day policy text) — scored 0.0, with the judge's reasoning correctly naming the exact contradictions. Contrasted against all real agent answers scoring 1.0.

All 4 new tests + original 9 pass (13 total across the eval suite).

## Interview Questions — Phase 4, Step 1

**Basic**
1. Why does the tool-selection test need no LLM judge, while the grounding test does?
2. What does the `FaithfulnessMetric` actually check, concretely?
3. Why did we wrap `ChatGroq` as a judge instead of using DeepEval's default OpenAI judge?

**Intermediate**
1. Why use a *larger* Groq model as judge instead of reusing the same `openai/gpt-oss-20b` the agent itself uses?
2. Why is testing prompt-injection safety before Phase 5 guardrails exist not very informative?
3. What would a failing faithfulness score (e.g. 0.3) actually indicate about the agent's behavior?

**Architecture**
1. `evals/` imports from `app.*` via a `sys.path` hack in `conftest.py` rather than the eval suite being installed as a proper dependency of the backend package — what's the tradeoff here, and when would this become a real problem?

## Phase 3 — Observability with Langfuse

### Step 1 complete: LangGraph tracing via Langfuse's LangChain integration
Used Langfuse's own published skill (`github.com/langfuse/skills`) as a reference — verified it was a legitimate vendor-published skill (real repo, real SKILL.md, consistent with their actual docs) before following any of it, treating it as a resource to evaluate rather than instructions to blindly execute.

**Implementation:**
- `graph.py`: Langfuse's `CallbackHandler` is wired in conditionally — only activates if both `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set; otherwise a clear console notice and the agent runs identically without tracing. Verified both paths work (with and without keys).
- `run_agent()` now takes an optional `session_id`, passed through as `config={"run_name": ..., "metadata": {"langfuse_session_id": ...}}`. `session_id` is generated once per widget mount (`crypto.randomUUID()`) in `ShopAgent.tsx` and sent with every `/chat` request.
- **Real gap surfaced by this work, not previously noted:** the backend has no multi-turn conversation memory at all — every request is a fresh `[System, Human]` message pair. `session_id` only *groups* independent traces for visualization in Langfuse's Sessions view; it does not give the agent actual memory of prior messages. Real conversation memory is a separate, deeper architectural gap, out of scope for "add tracing."
- **Real dependency bug found and fixed:** `langfuse.langchain.CallbackHandler` requires the full `langchain` meta-package, not just `langchain-core`/`langchain-groq` (which we already had) — import failed with `ModuleNotFoundError` until `langchain` was installed explicitly.

**Self-audit performed (per the skill's required loop — run it, fetch the real trace back, check against live best-practices doc, don't just assume it worked):** used `langfuse-cli` (via `npx`) to fetch the actual trace's observations after a real test request. Confirmed: span hierarchy correctly mirrors the actual graph execution (`agent → tools_condition/generation → tools/tool-call → agent → generation`), `GENERATION`/`TOOL` types auto-assigned correctly, token usage captured automatically — all via the framework integration, no manual instrumentation needed.

**Two gaps found and deliberately deferred, not silently ignored:**
1. Root trace input/output is the full raw LangChain message dump (readability issue in the dashboard), not a clean question/answer pair. Proper fix needs a manual span wrapper + `propagate_attributes()` — real added complexity for a cosmetic issue; deferred.
2. Cost isn't calculated (tokens are, cost is `null`) — Groq's `openai/gpt-oss-20b` likely isn't in Langfuse's default pricing catalog; fixable via a dashboard setting, not code.

Also noted for later: mock customer PII (email) currently flows into trace data unmasked — harmless with fake data, a real Phase 5 (guardrails) concern once real customer data exists.

## Phase 2 — React Widget

### Step 1 complete: Vite + React + TS scaffold, `<ShopAgent />` component
`packages/react/` — Vite scaffold (chose Vite over Next.js: no need for SSR/routing in an embeddable chat widget; near-instant HMR via esbuild). Monorepo layout confirmed: `backend/` and `packages/react/` side by side in one repo, matching the original target architecture.

`ShopAgent.tsx`: `ShopAgentProps` mirrors the original widget API (`apiKey`, `apiUrl`, `storeId`) even though `apiKey`/`storeId` aren't wired to anything yet (no backend auth/multi-tenancy exists yet either — same honest-placeholder pattern as `store_id` in the agent tools). Optimistic UI update (append the user's message before the network call resolves). Inline styles instead of a CSS file/classes — deliberate, since this component will eventually be embedded on arbitrary third-party store pages via `<script>` tag, and class-based CSS risks colliding with the host page's own styles.

**Verified in a real headless browser (Playwright), not just "should work":** initial render screenshot confirmed the chat UI; a real end-to-end message ("Where is order ORD1001?") was sent and a correct, grounded reply rendered.

**Two real bugs found and fixed via that browser test:**
1. **CORS blocked the request** (`localhost:5173` widget → `127.0.0.1:8010` API, different origins). Fixed with `CORSMiddleware(allow_origins=["*"])`. Worth remembering the reasoning, since it inverts the usual advice: normally wildcard CORS in production is a smell, but ShopAgent-OS is an embeddable widget meant to run on arbitrary, unknown store domains — there's no fixed origin list to enumerate. The real access-control boundary here has to be the API key check (Phase 5), not CORS; CORS and API-key auth solve different problems, and this architecture leans on the latter.
2. **Raw Markdown leaking into the UI** (`**ORD1001**` shown literally, since the widget doesn't render Markdown but the LLM naturally produces it). Fixed by explicitly instructing the system prompt to reply in plain text — simpler and more proportionate right now than adding a Markdown-rendering dependency to the widget, which is a reasonable thing to revisit during later UI polish.

### Follow-up: floating launcher pattern (fixed-position overlay, not inline)
Corrected an architectural gap, not just cosmetics: the widget originally rendered inline in the page flow. Real embeddable widgets must float as an overlay regardless of where they're mounted in a host page's DOM — fixed with `position: fixed; bottom; right; zIndex: 999999` on an outer wrapper containing a launcher button (`isOpen` toggles a chat panel above it) and, when open, the existing chat panel. Verified in a real browser across all 4 states (closed → open → message sent and grounded reply shown → closed again) with a simulated "host page" (`App.tsx` now has real surrounding content) to prove the float-over-content behavior, not just the widget in isolation. Conversation state (`messages`) persists across close/reopen since only visibility toggles, not the component's state — the right behavior for a chat widget.

### Follow-up: design polish — icon library + configurable brand color
Added `react-icons` (Feather set: `FiMessageCircle`, `FiX`, `FiSend`) instead of emoji characters for the launcher/close/send icons. Added an optional `primaryColor` prop (default `#6366F1`) threaded through every accent surface (launcher, header, user bubbles, send button) — this isn't cosmetic polish alone, it's a real requirement for a white-label embeddable widget: every store owner has different brand colors, so a single hardcoded accent color would look out of place on most real sites. Also added an empty-state welcome message so the panel doesn't render as a bare white box before the first message. Verified with a deliberately different color (`#16A34A`, green) in the demo app to prove the prop actually re-themes the whole component, not just visually inspecting the default.

## Interview Questions — Phase 2, Step 1

**Basic**
1. Why Vite instead of Next.js for this widget specifically?
2. Why are `apiKey` and `storeId` accepted as props but not used anywhere yet?
3. What does "optimistic UI update" mean, and where does it happen in `ShopAgent.tsx`?
4. What is a CORS preflight request, and what was actually missing that caused it to fail?
5. Why did Markdown syntax show up literally in the chat bubble instead of rendering as bold text?

**Intermediate**
1. Why is `allow_origins=["*"]` arguably the *correct* choice here rather than a shortcut, given what this widget is for?
2. Why use inline styles instead of a CSS file for this component?
3. What's the tradeoff between fixing the Markdown issue via the system prompt vs. adding a Markdown-rendering library to the widget?
4. What would break if the `finally` block were removed from `sendMessage`?

**Architecture**
1. If a store owner embeds this widget via a plain `<script>` tag (not React) as described in the original brief, what would need to exist that doesn't yet?
2. Trace what "access control" actually means for this system once Phase 5's API keys exist — what stops Store A's widget from reading Store B's data, concretely?

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
