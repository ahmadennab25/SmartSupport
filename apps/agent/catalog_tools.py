"""The `search_products` tool. Imported at the end of apps/agent/tools.py so it is always registered."""
from apps.orders.services import product_service

from .tools import register_tool


@register_tool(
    "search_products",
    "Search the store's product catalog by keyword. Pass 1 to 3 key words (product name or type), "
    "optionally in both Arabic and English, e.g. 'headphones سماعات'. Returns name, price and "
    "availability. Use it for 'do you sell X', prices and stock; never answer those from memory.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "1 to 3 key words, e.g. 'wireless mouse' or 'iphone'.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def search_products(customer, query) -> dict:
    products = product_service.search_products(query)
    if not products:
        return {
            "found": False,
            "message": (
                "No product matching this search is in the catalog. Do not say or imply that the store "
                "sells it; offer to pass the request to the team (support ticket)."
            ),
        }
    return {"found": True, "products": [product_service.describe_product(p) for p in products]}
