from decimal import Decimal, ROUND_HALF_UP

def round_time(t: float) -> float:
    return float(Decimal(str(t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
