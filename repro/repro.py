import asyncio
import json
import multiprocessing as mp
import socket
import sys
import time
from dataclasses import asdict, dataclass

from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    StreamableHTTPConnectionParams,
)
from mcp.server.fastmcp import FastMCP

HOST = "127.0.0.1"
PORT = 8766
MCP_URL = f"http://{HOST}:{PORT}/mcp"
SESSION_IDLE_TIMEOUT_SECONDS = 1800.0


@dataclass
class Result:
    adk_version: str
    first_call_ok: bool
    stale_call_failed: bool
    cached_session_reused: bool
    cached_retry_failed: bool
    fresh_manager_call_ok: bool
    stale_error_type: str | None
    stale_error_message: str | None
    cached_retry_error_type: str | None
    cached_retry_error_message: str | None


def run_server() -> None:
    server = FastMCP(
        "xbstack-stale-session-repro",
        host=HOST,
        port=PORT,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=False,
        session_idle_timeout=SESSION_IDLE_TIMEOUT_SECONDS,
        log_level="ERROR",
    )

    @server.tool()
    def ping(value: str = "ok") -> str:
        return f"pong:{value}"

    @server.tool()
    def drop_server_sessions() -> str:
        manager = server.session_manager
        count = len(manager._server_instances)
        manager._server_instances.clear()
        manager._session_owners.clear()
        return f"dropped:{count}"

    server.run(transport="streamable-http")


def wait_for_port(timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"MCP test server did not start on {HOST}:{PORT}")


def err(exc: BaseException) -> tuple[str, str]:
    message = str(exc).replace("\n", " ")
    return type(exc).__name__, message[:600]


async def run_case() -> Result:
    import google.adk

    params = StreamableHTTPConnectionParams(
        url=MCP_URL,
        timeout=3.0,
        sse_read_timeout=10.0,
        terminate_on_close=True,
    )

    manager = MCPSessionManager(params)
    first_session = None
    stale_error = None
    retry_error = None
    first_call_ok = False
    stale_call_failed = False
    cached_session_reused = False
    cached_retry_failed = False
    fresh_manager_call_ok = False

    try:
        first_session = await manager.create_session()
        first_result = await first_session.call_tool("ping", {"value": "first"})
        first_call_ok = not bool(getattr(first_result, "isError", False))

        reset_result = await first_session.call_tool("drop_server_sessions", {})
        if bool(getattr(reset_result, "isError", False)):
            raise RuntimeError("failed to clear server-side MCP session state")

        try:
            await first_session.call_tool("ping", {"value": "stale"})
        except BaseException as exc:  # noqa: BLE001 - the repro intentionally records the exact failure shape.
            stale_call_failed = True
            stale_error = err(exc)

        cached_session = await manager.create_session()
        cached_session_reused = cached_session is first_session

        try:
            retry_result = await cached_session.call_tool("ping", {"value": "cached-retry"})
            cached_retry_failed = bool(getattr(retry_result, "isError", False))
        except BaseException as exc:  # noqa: BLE001
            cached_retry_failed = True
            retry_error = err(exc)
    finally:
        await manager.close()

    fresh_manager = MCPSessionManager(params)
    try:
        fresh_session = await fresh_manager.create_session()
        fresh_result = await fresh_session.call_tool("ping", {"value": "fresh-manager"})
        fresh_manager_call_ok = not bool(getattr(fresh_result, "isError", False))
    finally:
        await fresh_manager.close()

    return Result(
        adk_version=getattr(google.adk, "__version__", "unknown"),
        first_call_ok=first_call_ok,
        stale_call_failed=stale_call_failed,
        cached_session_reused=cached_session_reused,
        cached_retry_failed=cached_retry_failed,
        fresh_manager_call_ok=fresh_manager_call_ok,
        stale_error_type=stale_error[0] if stale_error else None,
        stale_error_message=stale_error[1] if stale_error else None,
        cached_retry_error_type=retry_error[0] if retry_error else None,
        cached_retry_error_message=retry_error[1] if retry_error else None,
    )


def main() -> int:
    ctx = mp.get_context("spawn")
    process = ctx.Process(target=run_server, daemon=True)
    process.start()
    try:
        wait_for_port()
        result = asyncio.run(run_case())
        payload = asdict(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        expected = (
            result.first_call_ok
            and result.stale_call_failed
            and result.cached_session_reused
            and result.cached_retry_failed
            and result.fresh_manager_call_ok
        )
        if not expected:
            print(
                "REPRO_NOT_CONFIRMED: observed behavior did not match the stale-session cache failure shape.",
                file=sys.stderr,
            )
            return 2

        print("REPRO_CONFIRMED")
        return 0
    finally:
        process.terminate()
        process.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
