"""buysafe's fee on a sale: the single source of truth. The listing form's live
payout line, the "How the fee works" table and the landing page (via
export_fee_schedule) all come from here. Money is whole naira.

One rate applies to the whole price, picked by the tier the price falls in.
The tiers are data so they can move to settings or the admin later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

MIN_PRICE = 2_000  # a sale must be worth more than the flat fee
MAX_PRICE = 50_000_000

# Checked in order; the first tier whose `below` is above the price applies.
FEE_TIERS = [
    {
        "key": "flat",
        "below": 10_000,
        "fixed": 1_500,
        "percent": None,
        "label": "Under ₦10,000",
        "rate_label": "flat fee",
        "short_label": "Flat ₦1,500",
        "tag": "FLAT",
    },
    {
        "key": "pct15",
        "below": 20_000,
        "fixed": None,
        "percent": 15,
        "label": "₦10,000 – ₦19,999",
        "rate_label": "15%",
        "short_label": "15%",
        "tag": "15%",
    },
    {
        "key": "pct10",
        "below": None,
        "fixed": None,
        "percent": 10,
        "label": "₦20,000 and above",
        "rate_label": "10%",
        "short_label": "10%",
        "tag": "10%",
    },
]

# The "price at the next tier" tip shows from this price up, within a
# percentage tier, when pricing at the next tier's start pays the seller more.
NEXT_TIER_TIP_FROM = 17_000


@dataclass(frozen=True)
class FeeQuote:
    price: int
    fee: int
    payout: int  # what the seller receives
    tier_key: str
    rate_label: str
    tip: str | None

    def as_dict(self):
        return asdict(self)


def naira(amount: int) -> str:
    return f"₦{amount:,}"


def _round_half_up(numerator: int, denominator: int) -> int:
    return (numerator * 2 + denominator) // (denominator * 2)


def _tier_for(price: int) -> dict:
    return next(t for t in FEE_TIERS if t["below"] is None or price < t["below"])


def _fee(tier: dict, price: int) -> int:
    return tier["fixed"] if tier["fixed"] is not None else _round_half_up(price * tier["percent"], 100)


def _tip(tier: dict, price: int, payout: int) -> str | None:
    if tier["fixed"] is not None:
        share = _round_half_up(tier["fixed"] * 100, price)
        return f"Items under {naira(tier['below'])} have a flat {naira(tier['fixed'])} fee. That’s {share}% of this price."
    if tier["below"] is not None and price >= NEXT_TIER_TIP_FROM:
        next_price = tier["below"]
        next_tier = _tier_for(next_price)
        alt_payout = next_price - _fee(next_tier, next_price)
        if alt_payout > payout:
            return (
                f"At {naira(next_price)} the fee drops to {next_tier['rate_label']}, so you’d receive "
                f"{naira(alt_payout)} ({naira(alt_payout - payout)} more than now)."
            )
    return None


def tier_key_for(price: int) -> str:
    return _tier_for(price)["key"]


def calculate_fee(price: int) -> FeeQuote:
    """The fee and payout for a whole-naira price (MIN_PRICE to MAX_PRICE)."""
    tier = _tier_for(price)
    fee = _fee(tier, price)
    payout = price - fee
    return FeeQuote(price, fee, payout, tier["key"], tier["rate_label"], _tip(tier, price, payout))


def fee_schedule() -> dict:
    """The tiers as the "How the fee works" table shows them."""
    return {
        "min_price": MIN_PRICE,
        "max_price": MAX_PRICE,
        "tiers": [
            {k: t[k] for k in ("key", "label", "short_label", "tag", "below", "fixed", "percent")} for t in FEE_TIERS
        ],
    }
