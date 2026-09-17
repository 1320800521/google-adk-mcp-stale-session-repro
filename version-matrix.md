# Version matrix

Verified by XBSTACK on 2026-09-17 with a deterministic local Streamable HTTP MCP harness.

| google-adk | First call | Server-side session removed | `create_session()` reuses cached client session | Cached retry | New session manager |
|---|---|---|---|---|---|
| 2.7.1 | success | simulated | yes | `McpError: Session terminated` | success |
| 2.8.0 | success | simulated | yes | `McpError: Session terminated` | success |
| 2.9.1 | success | simulated | yes | `McpError: Session terminated` | success |

The harness deliberately clears only the MCP server's in-memory session registry while leaving the local HTTP service available. This reproduces the important failure boundary from `google/adk-python#7060`: the remote side has lost the protocol session, but the ADK client still owns and reuses a cached `ClientSession` object.

This does **not** claim that local process state clearing is identical to every Cloud Run scale-to-zero event. It is a deterministic reproduction of the same client-side stale-session cache behavior without requiring a Google Cloud account.
