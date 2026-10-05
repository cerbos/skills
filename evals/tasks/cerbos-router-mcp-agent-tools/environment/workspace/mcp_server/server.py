"""Helpdesk MCP server. Every tool runs with the helpdesk service account."""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from helpdesk import db  # helpdesk database access layer
from auth import OktaTokenVerifier  # verifies the bearer token against Okta's JWKS

mcp = FastMCP("helpdesk", auth=OktaTokenVerifier(audience="api://helpdesk-mcp"))


@mcp.tool
def list_tickets(status: str = "open") -> list[dict]:
    """List tickets by status."""
    return db.list_tickets(status=status)


@mcp.tool
def get_ticket(ticket_id: str) -> dict:
    """Get one ticket with its comments and attachments."""
    return db.get_ticket(ticket_id)


@mcp.tool
def update_ticket(ticket_id: str, status: str | None = None, assignee: str | None = None) -> dict:
    """Change a ticket's status or assignee."""
    return db.update_ticket(ticket_id, status=status, assignee=assignee)


@mcp.tool
def delete_ticket(ticket_id: str) -> str:
    """Permanently delete a ticket."""
    db.delete_ticket(ticket_id)
    return f"deleted {ticket_id}"


@mcp.tool
def delete_customer_attachment(ticket_id: str, attachment_id: str) -> str:
    """Permanently delete a file a customer attached to a ticket."""
    db.delete_attachment(ticket_id, attachment_id)
    return f"deleted {attachment_id}"


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
