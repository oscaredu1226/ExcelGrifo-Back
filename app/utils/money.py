from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import re


TWOPLACES = Decimal("0.01")
MONTO_BAJO_MAXIMO = Decimal("10.00")


def normalize_money(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None

    cleaned = re.sub(r"[^0-9,\.\-]", "", text)
    if not cleaned or cleaned in {"-", ".", ","}:
        return None

    if "," in cleaned and "." in cleaned:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        cleaned = cleaned.replace(thousands_separator, "")
        cleaned = cleaned.replace(decimal_separator, ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return Decimal(cleaned).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def money_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(TWOPLACES, rounding=ROUND_HALF_UP):.2f}"
