# Recovery pattern

The upstream client behavior is still under discussion, so this directory does not claim to contain an official Google ADK fix. It documents the containment pattern verified by the XBSTACK experiment.

## Containment

When a call fails because the remote MCP protocol session has been lost:

1. distinguish protocol/session-loss from an ordinary tool execution error;
2. discard the cached `ClientSession` / session manager state;
3. establish a fresh MCP session;
4. retry only operations that are safe to retry;
5. keep business idempotency and side-effect protection outside the MCP retry loop.

In the current test harness, replacing the stale `MCPSessionManager` with a fresh manager restores successful tool calls on google-adk 2.7.1, 2.8.0 and 2.9.1.

This is a verified workaround boundary, not an upstream patch. Track the official issue before adopting any internal monkey patch:

- https://github.com/google/adk-python/issues/7060
