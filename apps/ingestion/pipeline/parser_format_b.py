"""
Stage 4 — Format B Parser

Responsibilities:
  - Extract price snapshots from FORMAT_B normalized text.
  - Correlate commodity blocks with categories listed in the page footer.
  - Resolve market and commodity entities via the Entity Resolver.
  - Skip CALABARZON regional summary pages and Cigarette Monitoring.
  - Return a list of PriceSnapshot instances (unsaved).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import transaction

from apps.ingestion.models import SourceDocument
from apps.markets.models import Market
from apps.prices.models import CommodityCategory, PriceSnapshot
from apps.ingestion.pipeline.resolver import resolve_market, resolve_commodity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for price lines
# 1. Missing:  Name - - -
# 2. Range:    Name min - max avg prev
# 3. Single:   Name single avg prev
# ---------------------------------------------------------------------------
RE_MISSING = re.compile(r'^(.*?)\s+-\s+-\s+-$')
RE_RANGE   = re.compile(r'^(.*?)\s+([\d,.]+)\s*-\s*([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)$')
RE_SINGLE  = re.compile(r'^(.*?)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)$')


def parse_decimal(val_str: str) -> Optional[Decimal]:
    """Convert a string like '1,200.50' to Decimal, or None if invalid."""
    if not val_str or val_str == '-':
        return None
    clean = val_str.replace(',', '').strip()
    try:
        return Decimal(clean)
    except InvalidOperation:
        return None


def parse_format_b(source_document: SourceDocument) -> list[PriceSnapshot]:
    """
    Parse a FORMAT_B document into PriceSnapshot records.
    Returns a list of unsaved PriceSnapshot objects.
    """
    if not source_document.normalized_text:
        return []

    # Cache categories for fast case-insensitive lookup
    category_cache: dict[str, CommodityCategory] = {
        c.name.lower(): c for c in CommodityCategory.objects.all()
    }

    snapshots: list[PriceSnapshot] = []
    seen_keys = set()

    # Split by the normalizer's page markers
    # Format: <<<PAGE 1>>>\nline1\nline2...
    pages = source_document.normalized_text.split('<<<PAGE ')

    for page_chunk in pages:
        if not page_chunk.strip():
            continue

        # Split lines and drop empty ones
        lines = [line.strip() for line in page_chunk.split('\n') if line.strip()]
        if not lines:
            continue

        # First line is usually "1>>>" due to the split. Remove it from analysis.
        if lines[0].endswith('>>>'):
            lines = lines[1:]

        # 1. Find the footer to locate Market and Categories
        dpi_idx = -1
        for i, line in enumerate(lines):
            if "Daily Price Index" in line:
                dpi_idx = i
                break

        if dpi_idx == -1:
            # Not a standard FORMAT_B page, skip
            continue

        if dpi_idx + 2 >= len(lines):
            # Malformed footer
            continue

        market_name_raw = lines[dpi_idx + 1]
        
        # 2. Skip explicitly ignored pages
        skip_markers = ['CALABARZON', 'Region IV-A', 'Cigarette']
        if any(m.lower() in market_name_raw.lower() for m in skip_markers):
            continue

        # 3. Resolve Market
        market = resolve_market(market_name_raw, source_document=source_document)
        if not market:
            # If we don't know the market, we can't save prices for it.
            # resolve_market already logged the UnknownEntity.
            logger.warning("Unresolved market '%s' on document %s, skipping page.", market_name_raw, source_document.pk)
            continue

        # 4. Extract Category List from footer (appears after Address)
        # Footer layout: Daily Price Index -> Market Name -> Address -> Category 1 -> Category 2...
        footer_categories_raw = lines[dpi_idx + 3:]
        page_categories = []
        for raw_cat in footer_categories_raw:
            cat = category_cache.get(raw_cat.lower())
            if cat:
                page_categories.append(cat)
            else:
                # Store None so the list length matches the COMMODITY blocks,
                # even if we can't resolve the category itself.
                page_categories.append(None)

        # 5. Parse the body blocks
        # We iterate lines until "Notes:" which starts the footer.
        body_lines = []
        for line in lines:
            if line.startswith("Notes:"):
                break
            body_lines.append(line)

        cat_index = -1
        current_category = None

        for line in body_lines:
            if line.startswith("COMMODITY"):
                cat_index += 1
                if cat_index < len(page_categories):
                    current_category = page_categories[cat_index]
                else:
                    current_category = None
                continue

            # Skip header lines inside a block if they repeated
            if "PRICE RANGE" in line or "PREVAILING" in line:
                continue

            # It's a price line. Attempt to parse it.
            price_min = None
            price_max = None
            avg_price = None
            prev_price = None
            commodity_raw = None

            m_range = RE_RANGE.match(line)
            m_single = RE_SINGLE.match(line)
            m_missing = RE_MISSING.match(line)

            if m_range:
                commodity_raw = m_range.group(1).strip()
                price_min = parse_decimal(m_range.group(2))
                price_max = parse_decimal(m_range.group(3))
                avg_price = parse_decimal(m_range.group(4))
                prev_price = parse_decimal(m_range.group(5))
            elif m_single:
                commodity_raw = m_single.group(1).strip()
                val = parse_decimal(m_single.group(2))
                price_min = val
                price_max = val
                avg_price = parse_decimal(m_single.group(3))
                prev_price = parse_decimal(m_single.group(4))
            elif m_missing:
                commodity_raw = m_missing.group(1).strip()
                # All prices remain None
            else:
                # Unrecognised line format (e.g. subheader or malformed text)
                continue

            # Clean up commodity name if PyPDF missed a space
            if commodity_raw:
                commodity = resolve_commodity(
                    commodity_raw,
                    category=current_category,
                    source_document=source_document,
                )
                
                if commodity:
                    key = (market.pk, commodity.pk)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    
                    # Determine data quality flag
                    if price_min is None and avg_price is None and prev_price is None:
                        data_quality = PriceSnapshot.QUALITY_PROVISIONAL
                    else:
                        data_quality = PriceSnapshot.QUALITY_VERIFIED

                    snapshot = PriceSnapshot(
                        source_document=source_document,
                        survey_date=source_document.publication_date,
                        market=market,
                        commodity=commodity,
                        price_min=price_min,
                        price_max=price_max,
                        average_price=avg_price,
                        prevailing_price=prev_price,
                        data_quality=data_quality,
                    )
                    snapshots.append(snapshot)

    return snapshots
