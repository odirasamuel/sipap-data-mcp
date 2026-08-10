"""AWS Lambda handler for SIPAP Data MCP.

Provides Lambda entry point for JSON-RPC 2.0 MCP requests.
"""

import asyncio
import json
import logging
import os
import boto3
from typing import Any

from sipap_data_mcp.server import SIPAPDataMCP

# Configure structured logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set log level from environment variable (default: INFO)
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

# Initialize logger for this module
logger = logging.getLogger(__name__)

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
        logger.info("Created new event loop for Lambda container")

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
        logger.warning(f"Failed to fetch credentials from Secrets Manager: {e}", exc_info=True)
        return (os.environ.get("POSTGRES_USER", "sipap_readonly"),
                os.environ.get("POSTGRES_PASSWORD", ""))


def get_server() -> SIPAPDataMCP:
    """Get or create MCP server instance.

    Reuses server instance across Lambda invocations for connection pooling.
    Ensures database connections are established and maintained.

    Returns:
        Initialized SIPAPDataMCP server
    """
    global _server

    if _server is None:
        # COLD START: Create new server and establish connections
        logger.info("Cold start: Creating new MCP server")

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

        logger.info(f"Connecting to database: {db_host}:{db_port}/{db_name} (user: {db_user})")
        logger.info(f"Connecting to Redis: {redis_url}")

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
        logger.info("MCP server initialized with persistent connections")
    else:
        # WARM START: Verify connections are still alive
        logger.info("Warm start: Reusing existing MCP server")

        # Check if database pool is still connected
        if _server.db_client is None or _server.db_client._pool is None:
            logger.warning("Database connection lost, reconnecting...")
            loop = get_event_loop()
            loop.run_until_complete(_server._setup())
            logger.info("Database connection re-established")

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
    logger.info(f"Lambda invocation started (request_id: {context.aws_request_id})")

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

    # Log the JSON-RPC request
    logger.info(
        f"Received JSON-RPC request",
        extra={
            "method": request_data.get("method"),
            "id": request_data.get("id"),
            "params": request_data.get("params", {}).get("name")  # Tool name
        }
    )
    logger.debug(f"Full request: {json.dumps(request_data, indent=2)}")

    # Handle request via MCP server
    try:
        response = server.handle_request(request_data)

        # Log response summary
        if "result" in response:
            result = response["result"]
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    if isinstance(first_content, dict) and "text" in first_content:
                        try:
                            data = json.loads(first_content["text"])
                            if isinstance(data, dict):
                                logger.info(f"Response: {data.get('count', 0)} results returned")
                        except:
                            pass

        logger.debug(f"Full response: {json.dumps(response, indent=2)}")

    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        raise

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
