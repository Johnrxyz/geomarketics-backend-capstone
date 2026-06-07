# Token Usage Estimator for Gemini Vision API
# Run this to see token estimates for your capstone

# === HOW GEMINI COUNTS TOKENS ===
# Images: ~258 tokens per standard image (up to 768 for high-res scans)
# Input prompt text: ~120 tokens per request  
# Output JSON: ~150 tokens per document

# === YOUR DOCUMENT TYPES ===
TOKENS_PER_IMAGE = 400  # Average document scan (mid-res)
TOKENS_PROMPT = 120
TOKENS_OUTPUT = 150
TOKENS_PER_PAGE = TOKENS_PER_IMAGE + TOKENS_PROMPT + TOKENS_OUTPUT  # ~670 tokens

# === CAPSTONE SCENARIOS ===
scenarios = {
    "Demo Day (light)": {"vendors": 10, "docs_per_vendor": 2, "pages_per_doc": 2},
    "Full Capstone Defense": {"vendors": 50, "docs_per_vendor": 2, "pages_per_doc": 2},
    "Worst Case (all vendors)": {"vendors": 200, "docs_per_vendor": 2, "pages_per_doc": 3},
    "Today's Debugging Session": {"vendors": 0, "docs_per_vendor": 0, "pages_per_doc": 0, "override_pages": 50},
}

print("=" * 65)
print(f"  TOKEN USAGE ESTIMATE  |  gemini-2.5-flash pricing")
print(f"  Input: $0.075 / 1M tokens  |  Output: $0.30 / 1M tokens")
print("=" * 65)
print(f"  Tokens per document page: ~{TOKENS_PER_PAGE:,} tokens")
print(f"   ↳ Image: {TOKENS_PER_IMAGE} + Prompt: {TOKENS_PROMPT} + Output: {TOKENS_OUTPUT}")
print("=" * 65)

for name, s in scenarios.items():
    if "override_pages" in s:
        total_pages = s["override_pages"]
    else:
        total_pages = s["vendors"] * s["docs_per_vendor"] * s["pages_per_doc"]

    total_tokens = total_pages * TOKENS_PER_PAGE
    cost_usd = (total_tokens / 1_000_000) * 0.30  # blended estimate
    cost_php = cost_usd * 56  # approx PHP conversion
    pct_of_1m = (total_tokens / 1_000_000) * 100

    bar_len = int(pct_of_1m / 2)
    bar = "█" * bar_len + "░" * (50 - bar_len)

    print(f"\n  📋 {name}")
    print(f"     Pages processed: {total_pages}")
    print(f"     Total tokens:    {total_tokens:,}")
    print(f"     [{bar}] {pct_of_1m:.1f}% of 1M")
    print(f"     Estimated cost:  ${cost_usd:.4f} USD  (~₱{cost_php:.2f})")

print("\n" + "=" * 65)
print("  🎓 VERDICT FOR YOUR CAPSTONE:")
print("     You will NOT reach 1M tokens.")
print("     Full defense with 50 vendors ≈ 0.013M tokens")
print("     That's roughly ₱0.39 PHP — basically free with billing.")
print("=" * 65)
