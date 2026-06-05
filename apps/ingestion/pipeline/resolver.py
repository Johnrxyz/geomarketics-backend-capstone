"""
Stage 4 — Entity Resolver

Responsibilities:
  - Resolve a raw market name string → canonical Market record
  - Resolve a raw commodity name string → canonical Commodity record
  - Check aliases before exact-name fallback (to catch abbreviations first)
  - Log UnknownEntity when no match is found
  - Deduplicate: increment occurrence_count if the same unknown was already logged

Resolution order:
  1. MarketAlias / CommodityAlias  (case-insensitive)
  2. Market.name / Commodity.name  (case-insensitive, optionally filtered by category)
  3. → None  (logs UnknownEntity)

Note: The resolver performs DB queries. It is designed to be called inside a
Django request/management-command context with an active DB connection.
Keep this module free of HTTP/view concerns.
"""

from __future__ import annotations

from typing import Optional

from django.db.models import F


def resolve_market(raw_name: str, source_document=None):
    """
    Resolve a raw string to a canonical Market.

    Args:
        raw_name: The market name as it appeared in the PDF.
        source_document: SourceDocument instance (for UnknownEntity logging).

    Returns:
        Market instance, or None if not resolved.
    """
    # Import inside function to avoid circular import at module level
    from apps.markets.models import Market, MarketAlias, UnknownEntity

    raw_stripped = raw_name.strip()

    # 1. Alias lookup (case-insensitive)
    try:
        alias = MarketAlias.objects.select_related('market').get(
            alias__iexact=raw_stripped
        )
        return alias.market
    except MarketAlias.DoesNotExist:
        pass

    # 2. Exact name match (case-insensitive)
    try:
        return Market.objects.get(name__iexact=raw_stripped)
    except Market.DoesNotExist:
        pass

    # 3. Not found — log or bump UnknownEntity
    _log_unknown(
        entity_type=UnknownEntity.ENTITY_MARKET,
        raw_name=raw_stripped,
        source_document=source_document,
    )
    return None


def resolve_commodity(raw_name: str, category=None, source_document=None):
    """
    Resolve a raw string to a canonical Commodity.

    Args:
        raw_name: The commodity name as it appeared in the PDF.
        category: CommodityCategory instance (narrows lookup when supplied).
        source_document: SourceDocument instance (for UnknownEntity logging).

    Returns:
        Commodity instance, or None if not resolved.
    """
    from apps.markets.models import UnknownEntity
    from apps.prices.models import Commodity, CommodityAlias

    raw_stripped = raw_name.strip()

    # 1. Alias lookup (case-insensitive)
    alias_qs = CommodityAlias.objects.select_related('commodity__category').filter(
        alias__iexact=raw_stripped
    )
    if category:
        alias_qs = alias_qs.filter(commodity__category=category)
    alias = alias_qs.first()
    if alias:
        return alias.commodity

    # 2. Exact name match (case-insensitive)
    commodity_qs = Commodity.objects.filter(name__iexact=raw_stripped)
    if category:
        commodity_qs = commodity_qs.filter(category=category)
    commodity = commodity_qs.first()
    if commodity:
        return commodity

    # 3. Not found — log or bump UnknownEntity
    _log_unknown(
        entity_type=UnknownEntity.ENTITY_COMMODITY,
        raw_name=raw_stripped,
        source_document=source_document,
    )
    return None


def _log_unknown(entity_type: str, raw_name: str, source_document=None) -> None:
    """
    Create an UnknownEntity record if this (entity_type, raw_name) pair has not
    been seen before, or increment occurrence_count if it has.
    """
    from apps.markets.models import UnknownEntity

    obj, created = UnknownEntity.objects.get_or_create(
        entity_type=entity_type,
        raw_name=raw_name,
        defaults={
            'source_document': source_document,
            'resolution_status': UnknownEntity.STATUS_UNRESOLVED,
            'occurrence_count': 1,
        }
    )
    if not created:
        # Bump the count and update last_seen (handled by auto_now=True)
        UnknownEntity.objects.filter(pk=obj.pk).update(
            occurrence_count=F('occurrence_count') + 1
        )
