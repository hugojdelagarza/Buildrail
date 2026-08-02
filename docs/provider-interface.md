# Buildrail Provider Interface

The Provider Gateway is the single abstraction the Core Engine and all
skills use to reach an AI model. No other component may import a vendor
SDK or branch on a vendor-specific type. This document is the complete
contract: request/response shapes, capabilities, error model, retries,
and accounting.

## 1. Design Stance: Sync, Not Async

Buildrail is a single-developer, local-first CLI running one skill (or
one pipeline step) at a time in this design horizon — there is no
concurrent multi-request workload yet that would justify an async
interface. The Provider Gateway is **synchronous**: a call blocks until
a response (or a fully-buffered stream, see §5) is available.

This is a deliberate simplicity choice, not an oversight: async
correctness (cancellation, backpressure, concurrent adapter state) is
real cost, and nothing in the current roadmap needs concurrent provider
calls. If a future phase introduces parallel pipeline steps that
genuinely need concurrent provider access, that's the point to revisit
this — not before.

## 2. `ProviderRequest`

```json
{
  "messages": [
    { "role": "system", "content": [{ "type": "text", "text": "You are a code reviewer." }] },
    { "role": "user", "content": [{ "type": "text", "text": "Review this diff: ..." }] }
  ],
  "capability_tier": "default",
  "structured_output_schema": null,
  "max_output_tokens": 4096,
  "temperature": 0.2,
  "stream": false
}
```

- **`messages`** — role + content turns. `content` is a list of typed
  parts (`text` today; `image` for multimodal, §6), not a bare string,
  so multimodal input doesn't require a breaking schema change later.
- **`capability_tier`**, not a model name — see §3.
- **`structured_output_schema`** — an optional JSON Schema the response
  must conform to (§4).
- **`stream`** — whether the caller wants incremental output (§5).
- Sampling params (`temperature`, `max_output_tokens`) are generic and
  optional; an adapter maps them to its provider's actual parameters
  and ignores what doesn't apply.

Tool/function calling is **not included** in this version of the
interface. No current roadmap phase needs a skill to make multi-step,
model-driven tool calls — code review and doc generation are
single-shot (possibly structured-output) requests. Adding tool-calling
support later means adding a `tools` field and a new message content
type; it does not require redesigning `messages` or `ProviderResponse`,
so deferring it now is safe, not a trap.

## 3. Capability Tiers, Not Model Names

**The question:** should a skill's request name a concrete model
(`"claude-sonnet-5"`), or something more abstract?

- *Naming a concrete model* is simple and predictable, but it directly
  violates provider neutrality (`CLAUDE.md` rule 2) — a skill asking for
  `"claude-sonnet-5"` cannot run against a user configured for a
  different vendor at all, defeating the point of the Gateway.
- *An abstract capability tier* (e.g. `"default"`, `"fast"`,
  `"high-reasoning"`) lets a skill express *what it needs* without
  knowing what's available. Project config maps each tier to a concrete
  provider + model. A skill author never names a vendor.

**Decision:** capability tiers. A skill's manifest or request may name a
tier; the active provider's config resolves the tier to a concrete
model. `docs/skills.md` §3's `provider_capabilities_required` (e.g.
`text-completion`, `vision`) is the complementary, capability-*kind*
axis — tiers are about cost/quality tradeoffs among models that already
support the required capability kind.

## 4. `ProviderResponse`

```json
{
  "content": "...",
  "structured_output": null,
  "model_used": "claude-sonnet-5",
  "finish_reason": "stop",
  "usage": { "input_tokens": 1820, "output_tokens": 640, "total_tokens": 2460 },
  "cost_estimate": { "amount": 0.014, "currency": "USD", "basis": "advisory" }
}
```

- **`structured_output`** — populated (and schema-validated by the
  Gateway, not left to the skill) only when the request set
  `structured_output_schema`; kept separate from `content` so a skill
  never has to re-parse text to get structured data.
- **`cost_estimate`** — always labeled `"basis": "advisory"`. Pricing
  tables live outside the core (a small per-adapter config, not hardcoded
  logic) because prices change on a schedule the Gateway doesn't control.
  This number is for run-level reporting and budget awareness in an
  artifact's `provider_usage` (`docs/artifacts.md` §4) — never treated as
  billing-grade.
- A `raw_provider_response` field exists for Core Engine diagnostics and
  logging only. Skills must never read it — doing so would silently
  reintroduce a provider-specific dependency the rest of this design
  exists to prevent.

## 5. Streaming

The interface declares streaming as a capability (`stream: true` on the
request, a chunk-iterator return type) because retrofitting it later
would change the Gateway's function signature for every caller.

**What's actually built now:** only non-streaming. Piping a live token
stream through the subprocess skill protocol (`docs/skills.md` §5) means
either a chunked-transfer or event-stream protocol over the local
loopback endpoint — real complexity with no current consumer (there's no
TUI or UI yet that would render incremental tokens; a CLI printing a
final result is sufficient for every skill in the roadmap so far).

So: the shape exists in the spec so it isn't a breaking change later;
the implementation is non-streaming end-to-end until a concrete
consumer (e.g. a future interactive UI) justifies the added protocol
complexity.

## 6. Multimodal Support

A message's `content` is a list of typed parts:

```json
{ "role": "user", "content": [
  { "type": "text", "text": "What's in this diagram?" },
  { "type": "image", "ref": "artifact:20260802-.../003-diagram" }
]}
```

`image.ref` points to an artifact or a local file — never an inline
base64 blob in the request the skill constructs, keeping requests small
and keeping the actual bytes under the Artifact Store's provenance
tracking. Whether a given provider/model can actually accept an image is
a capability check (§7), not something the message schema enforces.

## 7. Provider Capabilities

Each adapter exposes a static descriptor the Core Engine can check
before ever making a call:

```json
{
  "supports_streaming": true,
  "supports_structured_output": true,
  "supports_vision": true,
  "supports_tools": false,
  "max_context_tokens": 200000,
  "capability_tiers": ["fast", "default", "high-reasoning"]
}
```

This is what lets `docs/skills.md`'s `provider_capabilities_required`
validation happen *before* a skill runs: "this skill needs vision, the
configured provider doesn't support it" is a clear pre-flight error, not
a confusing failure three layers deep in an adapter.

## 8. Error Model

Every adapter's errors are normalized into one of these before they
ever reach the Core Engine or a skill — nothing downstream branches on
a vendor exception type:

| Error | Retryable | Meaning |
|---|---|---|
| `AuthenticationError` | No | Missing/invalid credentials |
| `InvalidRequestError` | No | Malformed request, unsupported capability, schema too large |
| `ContentFilterError` | No | Provider refused/filtered the response |
| `RateLimitError` | Yes | Throttled; may include `retry_after` |
| `ProviderUnavailableError` | Yes | Timeout, 5xx, transient network failure |
| `UnknownProviderError` | No (default) | Fallback wrapper; preserves raw detail for diagnostics only |

## 9. Retry Behavior

Retry policy lives in the **Gateway**, not in adapters and not in
skills — one place to reason about backoff, so behavior is consistent
regardless of provider and skills never reimplement retry loops.

- Only `RateLimitError` and `ProviderUnavailableError` are retried.
- Exponential backoff with jitter; a config-controlled max attempt count
  (default: 3).
- `retry_after` from a `RateLimitError`, when the provider supplies it,
  takes precedence over the computed backoff delay.
- Every other error category surfaces to the caller immediately.

## 10. Usage Tracking and Token Accounting

- Every `ProviderResponse.usage` is recorded in the producing artifact's
  `provider_usage` metadata (`docs/artifacts.md` §4) **and** aggregated
  by the Gateway into the run's manifest, so "total cost of this run"
  never requires summing across every artifact by hand.
- Pre-flight token estimation (`count_tokens(request) -> int`) is an
  **optional** adapter capability — some provider SDKs expose an
  accurate counter, some don't. When unavailable, the Gateway falls back
  to a rough heuristic (characters ÷ 4) and labels the estimate as
  approximate. This is a real accuracy gap; it's accepted here rather
  than solved because getting it exactly right requires provider-specific
  tokenizers, which is precisely the kind of vendor coupling this
  interface exists to avoid at the core.

## 11. What a Concrete Adapter Must Implement

- `capabilities() -> ProviderCapabilities`
- `complete(request: ProviderRequest) -> ProviderResponse`
- `count_tokens(request) -> int | None` (optional)
- Mapping from its own vendor errors into §8's error taxonomy.

Nothing else. Adding a provider is adding one module implementing this
surface and registering it in config — by construction, this can never
require a change to the Core Engine, `docs/skills.md`'s protocol, or any
existing skill, which is the concrete test of "AI providers are
interchangeable" (`CLAUDE.md` rule 2).
