"""Product catalog search used by the agent's `search_products` tool."""
import re

from django.db.models import Q

from apps.orders.models import Order, Product

MIN_TERM_LENGTH = 3
LOW_STOCK_LIMIT = 5

# Words that carry no product meaning. The model is told to pass keywords, this is only a safety net.
STOP_TERMS = {
    "the", "and", "for", "you", "your", "does", "have", "has", "sell", "selling", "buy", "any", "what",
    "which", "price", "cost", "available", "availability", "how", "much", "there", "got", "can", "get",
    "want", "need", "with", "product", "products", "item", "items",
    "هل", "عندكم", "عندك", "تبيعون", "بتبيعوا", "يوجد", "فيه", "على", "عن", "سعر", "سعره", "ثمن",
    "متوفر", "متوفرة", "بدي", "اريد", "أريد", "ممكن", "منتج", "منتجات",
}


def extract_terms(query: str) -> list[str]:
    """Lower-cased search words: no stop words, no duplicates, at most 6."""
    terms: list[str] = []
    for word in re.findall(r"\w+", (query or "").lower()):
        if len(word) >= MIN_TERM_LENGTH and word not in STOP_TERMS and word not in terms:
            terms.append(word)
    return terms[:6]


def score_text(terms: list[str], text: str) -> int:
    """How many of the search terms appear in the text."""
    text = (text or "").lower()
    return sum(1 for term in terms if term in text)


def _haystack(product: Product) -> str:
    return " ".join([product.name, product.name_ar, product.category, product.sku])


def search_products(query: str, limit: int = 5) -> list[Product]:
    """Active products matching at least one search word, best match first.
    The description is not searched on purpose (generic words would match every product)."""
    terms = extract_terms(query)
    if not terms:
        return []
    condition = Q()
    for term in terms:
        condition |= (
            Q(name__icontains=term)
            | Q(name_ar__icontains=term)
            | Q(category__icontains=term)
            | Q(sku__icontains=term)
        )
    candidates = list(Product.objects.filter(is_active=True).filter(condition))
    candidates.sort(key=lambda product: (-score_text(terms, _haystack(product)), product.name))
    return candidates[:limit]


def availability_label(stock_quantity: int) -> str:
    if stock_quantity <= 0:
        return "out_of_stock"
    return "low_stock" if stock_quantity <= LOW_STOCK_LIMIT else "in_stock"


def describe_product(product: Product) -> dict:
    return {
        "name": product.name,
        "name_ar": product.name_ar or None,
        "sku": product.sku,
        "category": product.category or None,
        "price": f"{product.price:.2f}",
        "currency": Order._meta.get_field("currency").default,
        "availability": availability_label(product.stock_quantity),
    }
