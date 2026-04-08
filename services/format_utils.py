def parse_price_input(raw_price):
    cleaned_price = str(raw_price).replace(",", "").replace("₱", "").replace("P", "").strip()
    if not cleaned_price:
        raise ValueError("Price is empty")
    return float(cleaned_price)


def format_price_display(value):
    try:
        numeric_value = float(str(value).replace(",", "").replace("₱", "").replace("P", "").strip())
        if numeric_value.is_integer():
            return f"{int(numeric_value):,}"
        return f"{numeric_value:,.2f}"
    except Exception:
        return str(value)
