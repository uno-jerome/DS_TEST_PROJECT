import json
import os
from urllib.parse import unquote, urlparse


def parse_specs_lines(specs_raw):
    if not specs_raw:
        return []

    try:
        parsed_specs = json.loads(specs_raw)
        if isinstance(parsed_specs, dict):
            return [f"{key}: {value}" for key, value in parsed_specs.items()]
        if isinstance(parsed_specs, list):
            return [str(item) for item in parsed_specs if str(item).strip()]
    except Exception:
        pass

    return [line.strip() for line in str(specs_raw).splitlines() if line.strip()]


def resolve_product_image_path(raw_path, script_dir):
    image_path = str(raw_path or "").strip().strip('"').strip("'")
    if not image_path:
        return ""

    candidate_paths = []

    # Support file:// URIs and decode URL-encoded local paths.
    if image_path.lower().startswith("file://"):
        parsed_uri = urlparse(image_path)
        decoded_path = unquote(parsed_uri.path or "")
        if os.name == "nt" and decoded_path.startswith("/"):
            decoded_path = decoded_path[1:]
        if decoded_path:
            candidate_paths.append(decoded_path)

    candidate_paths.append(image_path)

    if not os.path.isabs(image_path):
        candidate_paths.append(os.path.join(script_dir, image_path))
        candidate_paths.append(os.path.join(script_dir, "images", image_path))
        candidate_paths.append(os.path.join(script_dir, "assets", image_path))

    seen_paths = set()
    for candidate in candidate_paths:
        normalized = os.path.normpath(os.path.expanduser(candidate))
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        if os.path.exists(normalized):
            return normalized

    return ""


def write_receipt_file(order_id, customer_name, email, contact, address, subtotal, vat, grand_total, payment, date_str, cart_items):
    filename = f"receipt_ORD{order_id}.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write("=========================================\n")
        file.write("            ITC TECH STORE               \n")
        file.write("=========================================\n")
        file.write(f"Order ID : #{order_id}\n")
        file.write(f"Date     : {date_str}\n")
        file.write(f"Customer : {customer_name}\n")
        file.write(f"Email    : {email}\n")
        file.write(f"Contact  : {contact}\n")

        # Format address string nicely if it's long.
        addr_line = str(address or "").replace("\n", " ")
        file.write(f"Address  : {addr_line}\n")
        file.write(f"Payment  : {payment}\n")
        file.write("-----------------------------------------\n")
        file.write(f"{'Item':<20} | {'Qty':<5} | {'Price':<10}\n")
        file.write("-----------------------------------------\n")

        for item in cart_items:
            item_name = str(item.get("name", ""))
            item_qty = int(item.get("quantity", 0))
            item_price = float(item.get("price", 0))
            name_short = (item_name[:17] + "..") if len(item_name) > 19 else item_name
            file.write(f"{name_short:<20} | {item_qty:<5} | P{item_price:>10,.2f}\n")

        file.write("-----------------------------------------\n")
        file.write(f"Subtotal    : P {float(subtotal):>10,.2f}\n")
        file.write(f"12% VAT     : P {float(vat):>10,.2f}\n")
        file.write(f"GRAND TOTAL : P {float(grand_total):>10,.2f}\n")
        file.write("=========================================\n")
        file.write("        Thank you for shopping!          \n")

    return filename
