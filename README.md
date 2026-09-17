# Google ADK × MCP stale-session recovery repro

This repository reproduces the stale MCP session failure reported in `google/adk-python#7060` without requiring Google Cloud Run.

## What is being tested

A Streamable HTTP MCP client successfully creates and caches a session. The test server then deletes only its in-memory MCP session registry while keeping the HTTP service alive. This models the important boundary of a scale-to-zero/server-restart event: the transport endpoint is reachable again, but the server no longer knows the old MCP session ID.

The test then checks whether `MCPSessionManager.create_session()` creates a new session or returns the previously cached `ClientSession`.

## XBSTACK result — 2026-09-17

| google-adk | first call | stale call | cached session reused | cached retry | fresh manager |
|---|---|---|---|---|---|
| 2.7.1 | success | `McpError: Session terminated` | yes | fails | success |
| 2.8.0 | success | `McpError: Session terminated` | yes | fails | success |
| 2.9.1 | success | `McpError: Session terminated` | yes | fails | success |

The same failure shape was reproduced on all three versions tested.

## Run

```bash
bash run.sh
```

A successful reproduction prints `REPRO_CONFIRMED` for each tested ADK version.

## What this proves

The experiment confirms that a client-side cached MCP session can remain reusable according to the local transport check even after the remote MCP server has lost the protocol session. Re-entering `create_session()` on the same manager returns the cached dead session and the next tool call fails again. Creating a fresh manager establishes a working new session.

This is broader than Cloud Run. Any infrastructure that can restart or replace an MCP server instance while the client process survives can create the same class of mismatch: server-side protocol state disappears while client-side transport/session objects remain cached.

## What this does not prove

This local harness does not claim to reproduce every Cloud Run lifecycle detail, load-balancer behavior, or network timing. It deliberately isolates the session-lifecycle boundary so the client cache behavior can be tested deterministically.

It also does not claim that every tool error should invalidate an MCP session. Application-level tool errors and transport/protocol-session loss must be distinguished to avoid unnecessary reconnects.

## Production mitigation

Until the upstream behavior is changed, the safe recovery pattern is:

1. detect a protocol/session-loss failure separately from a normal tool-result error;
2. invalidate or discard the cached client session;
3. create a fresh MCP session;
4. retry only operations that are safe to retry;
5. keep idempotency and business-side-effect protection outside the retry loop.

## Evidence

- Upstream issue: https://github.com/google/adk-python/issues/7060
- Version results: [`version-matrix.md`](./version-matrix.md)
- Repro source: [`repro/repro.py`](./repro/repro.py)
- Machine-readable result snapshots: [`logs/`](./logs/)

## XBSTACK article

A full production analysis will be linked here after the site article passes XBSTACK's search-demand, duplication, bilingual, content-quality, and release gates.
