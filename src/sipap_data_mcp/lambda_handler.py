"""AWS Lambda handler for SIPAP Data MCP.

Provides Lambda entry point for JSON-RPC 2.0 MCP requests.
"""

import asyncio
import json
import os
import boto3
from typing import Any

from sipap_data_mcp.server import SIPAPDataMCP

# Global event loop for Lambda container reuse
# This event loop persists across Lambda invocations (warm starts)
_event_loop: asyncio.AbstractEventLoop | None = None

# Initialize server (singleton for Lambda container reuse)
_server: SIPAPDataMCP | None = None


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create persistent event loop for Lambda container.

    Creates event loop once on cold start, reuses on warm starts.
    The loop is never closed during Lambda container lifetime.

    Returns:
        Event loop instance
    """
    global _event_loop

    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
        print("Created new event loop for Lambda container")

    return _event_loop


def get_db_credentials() -> tuple[str, str]:
    """Fetch database credentials from Secrets Manager.

    Returns:
        Tuple of (username, password)
    """
    credentials_arn = os.environ.get("POSTGRES_CREDENTIALS_ARN")
    if not credentials_arn:
        # Fallback to environment variables if no secret ARN
        return (
            os.environ.get("POSTGRES_USER", "sipap_readonly"),
            os.environ.get("POSTGRES_PASSWORD", "")
        )

    try:
        sm_client = boto3.client("secretsmanager")
        response = sm_client.get_secret_value(SecretId=credentials_arn)
        credentials = json.loads(response["SecretString"])
        return (credentials.get("username", "sipap_readonly"),
                credentials.get("password", ""))
    except Exception as e:
        print(f"Warning: Failed to fetch credentials from Secrets Manager: {e}")
        return (os.environ.get("POSTGRES_USER", "sipap_readonly"),
                os.environ.get("POSTGRES_PASSWORD", ""))


def get_server() -> SIPAPDataMCP:
    """Get or create MCP server instance.

    Reuses server instance across Lambda invocations for connection pooling.

    Returns:
        Initialized SIPAPDataMCP server
    """
    global _server

    if _server is None:
        # Get configuration from environment variables (AWS Lambda environment)
        db_host = os.environ.get("POSTGRES_HOST", "localhost")
        db_port = int(os.environ.get("POSTGRES_PORT", "5432"))
        db_name = os.environ.get("POSTGRES_DB", "sipap_dev")

        # Fetch database credentials from Secrets Manager
        db_user, db_password = get_db_credentials()

        # Build Redis URL from endpoint
        redis_endpoint = os.environ.get("REDIS_ENDPOINT", "localhost:6379")
        redis_ssl = os.environ.get("REDIS_SSL", "false").lower() == "true"
        redis_protocol = "rediss" if redis_ssl else "redis"
        redis_url = f"{redis_protocol}://{redis_endpoint}/0"

        # Create server
        _server = SIPAPDataMCP(
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            redis_url=redis_url
        )

        # Get persistent event loop (never closed during container lifetime)
        loop = get_event_loop()

        # Setup connections using persistent loop
        loop.run_until_complete(_server._setup())
        print("MCP server initialized with persistent event loop")

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
