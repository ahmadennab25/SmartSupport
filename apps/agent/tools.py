"""Tools the single support agent can call.

Every handler receives the authenticated `customer` from the server, never from the model,
so the agent can only read and change the data of the person it is talking to.
New tools (e.g. the RAG `search_policies` tool) are added with @register_tool.
"""
import inspect
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from apps.orders.services import order_service
from apps.tickets.models import Ticket
from apps.tickets.services import ticket_service
from apps.tickets.services.ticket_service import TicketError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., dict]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_REGISTRY: dict[str, Tool] = {}


def register_tool(name: str, description: str, parameters: dict):
    def decorator(func):
        _REGISTRY[name] = Tool(name, description, parameters, func)
        return func

    return decorator


def get_tool_schemas() -> list[dict]:
    return [tool.schema() for tool in _REGISTRY.values()]


def get_tool_names() -> list[str]:
    return list(_REGISTRY)


def _object(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


ORDER_NUMBER = {"type": "string", "description": "The order number, e.g. 1025."}
TICKET_REFERENCE = {"type": "string", "description": "Ticket reference such as TKT-000012."}


@register_tool(
    "lookup_order",
    "Get the status, shipping, payment and items of ONE order of the current customer.",
    _object({"order_number": ORDER_NUMBER}, ["order_number"]),
)
def lookup_order(customer, order_number) -> dict:
    order = order_service.get_customer_order(customer, order_number)
    if order is None:
        return {
            "found": False,
            "message": "No order with this number was found for this customer.",
        }
    return {"found": True, "order": order_service.describe_order(order)}


@register_tool(
    "list_my_orders",
    "List the current customer's most recent orders (use when they do not know the order number).",
    _object({}, []),
)
def list_my_orders(customer) -> dict:
    orders = order_service.list_customer_orders(customer)
    return {"orders": [order_service.describe_order(o, include_items=False) for o in orders]}


@register_tool(
    "create_support_ticket",
    "Open a support ticket for a complaint or problem. Priority is set automatically.",
    _object(
        {
            "subject": {"type": "string", "description": "Short title of the problem."},
            "description": {
                "type": "string",
                "description": "What happened, in the customer's own details.",
            },
            "category": {"type": "string", "enum": list(Ticket.Category.values)},
            "order_number": {
                "type": "string",
                "description": "Related order number, if the problem is about an order.",
            },
        },
        ["subject", "description", "category"],
    ),
)
def create_support_ticket(customer, subject, description, category="other", order_number=None) -> dict:
    ticket, created = ticket_service.create_ticket(
        customer, subject, description, category=category, order_number=order_number
    )
    result = {"created": created, "ticket": ticket_service.describe_ticket(ticket)}
    if not created:
        result["note"] = "An open ticket for this order and category already exists; it was reused."
    return result


@register_tool(
    "get_ticket_status",
    "Check one ticket by reference, or list the customer's open tickets when no reference is given.",
    _object({"ticket_reference": TICKET_REFERENCE}, []),
)
def get_ticket_status(customer, ticket_reference=None) -> dict:
    if ticket_reference not in (None, ""):
        ticket = ticket_service.get_customer_ticket(customer, ticket_reference)
        if ticket is None:
            return {"found": False, "message": "No ticket with this reference was found for this customer."}
        return {"found": True, "ticket": ticket_service.describe_ticket(ticket)}
    tickets = ticket_service.list_customer_tickets(customer)
    return {"open_tickets": [ticket_service.describe_ticket(t) for t in tickets]}


@register_tool(
    "add_ticket_update",
    "Add new information from the customer to one of their open tickets.",
    _object(
        {
            "ticket_reference": TICKET_REFERENCE,
            "message": {"type": "string", "description": "The new information."},
        },
        ["ticket_reference", "message"],
    ),
)
def add_ticket_update(customer, ticket_reference, message) -> dict:
    ticket = ticket_service.add_customer_update(customer, ticket_reference, message)
    return {"updated": True, "ticket": ticket_service.describe_ticket(ticket)}


@register_tool(
    "escalate_to_human",
    "Hand the case to a human support agent. Use an existing ticket reference if there is one.",
    _object(
        {
            "reason": {"type": "string", "description": "Why a human is needed."},
            "ticket_reference": TICKET_REFERENCE,
            "order_number": ORDER_NUMBER,
        },
        ["reason"],
    ),
)
def escalate_to_human(customer, reason, ticket_reference=None, order_number=None) -> dict:
    ticket = ticket_service.escalate_to_human(
        customer, reason, reference=ticket_reference, order_number=order_number
    )
    return {
        "escalated": True,
        "ticket": ticket_service.describe_ticket(ticket),
        "message": "A human agent will follow up with the customer.",
    }


def execute_tool(name: str, raw_arguments: str | None, customer) -> dict:
    """Run a tool call coming from the model. Always returns a JSON-safe dict, never raises."""
    tool = _REGISTRY.get(name)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        arguments = json.loads(raw_arguments) if raw_arguments else {}
    except json.JSONDecodeError:
        return {"error": "Tool arguments were not valid JSON."}
    if not isinstance(arguments, dict):
        return {"error": "Tool arguments must be a JSON object."}
    try:
        inspect.signature(tool.handler).bind(customer, **arguments)
    except TypeError as exc:
        logger.warning("Bad arguments for tool %s: %s", name, exc)
        return {"error": "Invalid or missing tool arguments."}
    try:
        return tool.handler(customer, **arguments)
    except TicketError as exc:
        return {"error": str(exc)}
    except Exception:
        logger.exception("Tool %s failed", name)
        return {"error": "Internal error while running the tool."}

from . import catalog_tools  # noqa: F401  (registers the search_products tool)
