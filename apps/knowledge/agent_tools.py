"""Registers the RAG tool in the agent's registry (imported from KnowledgeConfig.ready)."""
from apps.agent.tools import register_tool
from apps.knowledge.services import retrieval_service

SUPPORTED_LANGUAGES = ["ar", "en"]


@register_tool(
    "search_policies",
    "Search the store's policy documents and FAQ (returns, exchanges, refunds, shipping and delivery, "
    "payment methods, warranty, common questions). Use it for ANY question about store rules; never "
    "answer those from memory. Do not use it for a specific order or ticket.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A short search query with the key details, e.g. 'return after 10 days'.",
            },
            "language": {
                "type": "string",
                "enum": SUPPORTED_LANGUAGES,
                "description": "Language of the customer's message.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def search_policies(customer, query, language=None) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        language = customer.preferred_language
    results = retrieval_service.search(query, language=language)
    if not results:
        return {
            "found": False,
            "message": "No relevant policy passage was found. Do not guess; offer to open a support ticket.",
        }
    return {
        "found": True,
        "passages": [
            {
                "source": item.title,
                "section": item.section or None,
                "text": item.content,
                "score": round(item.score, 3),
            }
            for item in results
        ],
    }
