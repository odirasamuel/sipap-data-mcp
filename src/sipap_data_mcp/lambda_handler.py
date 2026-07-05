"""AWS Lambda handler for SIPAP Data MCP.

Provides Lambda entry point for JSON-RPC 2.0 MCP requests.
"""

import json
import os
from typing import Any

from sipap_data_mcp.server import SIPAPDataMCP

# Initialize server (singleton for Lambda container reuse)
_server: SIPAPDataMCP | None = None


def get_server() -> SIPAPDataMCP:
    """Get or create MCP server instance.

    Reuses server instance across Lambda invocations for connection pooling.

    Returns:
        Initialized SIPAPDataMCP server
    """
    global _server

    if _server is None:
        # Get configuration from environment variables
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = int(os.environ.get("DB_PORT", "5432"))
        db_name = os.environ.get("DB_NAME", "sipap")
        db_user = os.environ.get("DB_USER", "sipap_readonly")
        db_password = os.environ.get("DB_PASSWORD", "")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

        # Create server
        _server = SIPAPDataMCP(
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            redis_url=redis_url
        )

        # Setup connections (async operations run synchronously)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_server._setup())
        loop.close()

    return _server


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler function.

    Processes JSON-RPC 2.0 requests from API Gateway or direct invocation.

    Args:
        event: Lambda event (API Gateway proxy format or direct JSON-RPC)
        context: Lambda context object

    Returns:
        API Gateway response or direct JSON-RPC response
    """
    # Get server instance
    server = get_server()

    # Extract request body
    if "body" in event:
        # API Gateway proxy format
        if isinstance(event["body"], str):
            request_data = json.loads(event["body"])
        else:
            request_data = event["body"]
    else:
        # Direct invocation
        request_data = event

    # Handle request via MCP server
    response = server.handle_request(request_data)

    # Return response
    if "body" in event:
        # API Gateway proxy format
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(response)
        }
    # Direct invocation
    return response
