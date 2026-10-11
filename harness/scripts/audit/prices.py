"""Price table (ASSUMPTION: list-price equivalents; both accounts are subscription-billed).

Claude figures: Anthropic list prices as of 2026-06 with the documented cache multipliers
(read 0.1x, 5-minute write 1.25x, 1-hour write 2x). Codex figures are assumed tiers; Codex
reports no cache-write tokens. Edit here, never inline in a report.
"""
PRICE = {  # $/1M: fresh input, cache read, cache write 5m, cache write 1h, output
    "claude-opus-5": (5.00, 0.50, 6.25, 10.00, 25.00),
    "claude-sonnet-5": (2.00, 0.20, 2.50, 4.00, 10.00),
    "claude-haiku-4-5": (1.00, 0.10, 1.25, 2.00, 5.00),
    "claude-fable-5-1": (10.00, 0.25, 12.50, 20.00, 50.00),
    "claude-opus-5-5": (5.00, 0.50, 6.25, 10.00, 25.00),  # AUDIT ALIAS = opus-5 rates
    "claude-sonnet-5-5": (2.00, 0.20, 2.50, 4.00, 10.00),  # AUDIT ALIAS = sonnet-5 rates
    "claude-haiku-4-5-20251001": (1.00, 0.10, 1.25, 2.00, 5.00),  # AUDIT ALIAS
    "gpt-5.6-sol": (10.00, 1.00, 10.00, 10.00, 40.00),
    "gpt-5.6-terra": (2.50, 0.25, 2.50, 2.50, 10.00),
    "gpt-5.6-luna": (0.50, 0.05, 0.50, 0.50, 2.00),
}


def cost_usd(model, fresh, cached, w5, w1, out, list_price=False):
    p = PRICE.get(model)
    if not p:
        return 0.0
    if list_price:
        return ((fresh + cached + w5 + w1) * p[0] + out * p[4]) / 1e6
    return (fresh * p[0] + cached * p[1] + w5 * p[2] + w1 * p[3] + out * p[4]) / 1e6
