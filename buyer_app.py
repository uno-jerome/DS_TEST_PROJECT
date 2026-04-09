import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
import random
import re
from datetime import datetime, timedelta
from database import setup_database, get_session_connection, close_session_connection
from services import buyer_data_service as buyer_data
from services import buyer_state_service as buyer_state
from services import buyer_utils
from services.format_utils import parse_price_input, format_price_display
from security_utils import (
    hash_password,
    needs_password_upgrade,
    validate_password_strength,
    verify_password,
)

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

SHOP_START_TS = time.perf_counter()
db_setup_start = time.perf_counter()
setup_database()
logger.info(
    "Shop DB setup check complete",
    extra={"duration_seconds": round(time.perf_counter() - db_setup_start, 3)},
)

Image = None
try:
    from PIL import Image as PILImage
    Image = PILImage
except Exception:
    Image = None

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

PALETTE_DARKEST = "#091413"
PALETTE_DARK = "#285A48"
PALETTE_PRIMARY = "#408A71"
PALETTE_MINT = "#B0E4CC"
PALETTE_TEXT = "#E8FFF5"
SHOP_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop_state.json")
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
MIN_ORDER_ID = 100000000000
MAX_ORDER_ID = 999999999999
MAX_ORDER_ID_ATTEMPTS = 30
SHOP_READ_SESSION = "shop-read"
SHOP_AUTH_SESSION = "shop-auth"
EYE_ICON_FALLBACK = "👁"


def load_eye_toggle_icons():
    if Image is None:
        return None, None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    open_icon_path = os.path.join(script_dir, "open_eye.png")
    closed_icon_path = os.path.join(script_dir, "closed_eye.png")

    try:
        open_icon_img = Image.open(open_icon_path)
        closed_icon_img = Image.open(closed_icon_path)
    except Exception:
        return None, None

    open_icon = ctk.CTkImage(light_image=open_icon_img, dark_image=open_icon_img, size=(12, 12))
    closed_icon = ctk.CTkImage(light_image=closed_icon_img, dark_image=closed_icon_img, size=(12, 12))
    return open_icon, closed_icon


OPEN_EYE_ICON, CLOSED_EYE_ICON = load_eye_toggle_icons()

current_customer = {
    "id": None,
    "username": None,
    "email": None,
    "name": None,
    "contact": None,
    "address": None
}

def default_shop_state():
    return buyer_state.default_shop_state()

def load_shop_state():
    return buyer_state.load_shop_state(SHOP_STATE_FILE)

def save_shop_state():
    if not buyer_state.save_shop_state(SHOP_STATE_FILE, shop_state):
        logger.warning("Could not save shop state")

def get_current_cart_owner_key():
    owner_email = str(current_customer.get("email") or "").strip().lower()
    return owner_email

def persist_login_preference(login_identifier, remember_me_enabled):
    normalized_identifier = str(login_identifier or "").strip()
    if remember_me_enabled:
        shop_state["remember_me"] = True
        shop_state["remembered_login_identifier"] = normalized_identifier
        shop_state["remembered_email"] = normalized_identifier
    else:
        shop_state["remember_me"] = False
        shop_state["remembered_login_identifier"] = ""
        shop_state["remembered_email"] = ""
    save_shop_state()

def restore_login_preference():
    remember_flag = bool(shop_state.get("remember_me", False))
    remembered_identifier = str(
        shop_state.get("remembered_login_identifier", shop_state.get("remembered_email", "")) or ""
    ).strip()

    remember_me_var.set(remember_flag)
    if remember_flag and remembered_identifier:
        login_email_var.set(remembered_identifier)


def looks_like_phone_identifier(value):
    raw_value = str(value or "").strip()
    if not raw_value or "@" in raw_value:
        return False

    allowed_chars = set("0123456789+ -()")
    if any(char not in allowed_chars for char in raw_value):
        return False

    digit_count = sum(1 for char in raw_value if char.isdigit())
    return digit_count >= 10


def build_contact_login_variants(value):
    digits_only = "".join(char for char in str(value or "") if char.isdigit())
    if not digits_only:
        return []

    variants = {digits_only}
    if digits_only.startswith("63") and len(digits_only) == 12:
        variants.add("0" + digits_only[2:])
        variants.add(digits_only[2:])
    elif digits_only.startswith("0") and len(digits_only) == 11:
        variants.add("63" + digits_only[1:])
        variants.add(digits_only[1:])
    elif len(digits_only) == 10:
        variants.add("63" + digits_only)
        variants.add("0" + digits_only)

    return sorted(variant for variant in variants if variant)


def generate_unique_order_id(conn):
    for _ in range(MAX_ORDER_ID_ATTEMPTS):
        generated_order_id = random.randint(MIN_ORDER_ID, MAX_ORDER_ID)
        if not buyer_data.order_id_exists(conn, generated_order_id):
            return generated_order_id
    raise RuntimeError("Could not generate a unique order ID. Please try checkout again.")

def persist_cart_cache_for_current_user():
    owner_key = get_current_cart_owner_key()
    if not owner_key:
        return

    cached_items = []
    for item in cart_items:
        try:
            item_price = float(item.get("price", 0))
            item_quantity = int(item.get("quantity", 0))
            if item_quantity <= 0 or item_price < 0:
                continue
            cached_items.append({
                "item_id": str(item.get("item_id", "")),
                "name": str(item.get("name", "")),
                "price": item_price,
                "quantity": item_quantity
            })
        except (TypeError, ValueError):
            continue

    cart_cache = shop_state.setdefault("cart_cache", {})
    cart_cache[owner_key] = cached_items
    save_shop_state()

def restore_cart_cache_for_current_user():
    owner_key = get_current_cart_owner_key()
    cart_items.clear()

    if not owner_key:
        refresh_cart_display(save_cache=False)
        return

    cart_cache = shop_state.get("cart_cache", {})
    saved_items = cart_cache.get(owner_key, [])

    for item in saved_items:
        try:
            item_id = str(item.get("item_id", "")).strip()
            item_name = str(item.get("name", "")).strip()
            item_price = float(item.get("price", 0))
            item_quantity = int(item.get("quantity", 0))

            if not item_id or not item_name or item_quantity <= 0 or item_price < 0:
                continue

            cart_items.append({
                "item_id": item_id,
                "name": item_name,
                "price": item_price,
                "quantity": item_quantity,
                "subtotal": item_price * item_quantity
            })
        except (TypeError, ValueError):
            continue

    refresh_cart_display(save_cache=False)

def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width / 2) - (width / 2)
    y = (screen_height / 2) - (height / 2)
    win.geometry(f'{width}x{height}+{int(x)}+{int(y)}')


def maximize_window(win):
    try:
        win.state("zoomed")
        return
    except tk.TclError:
        pass

    try:
        win.attributes("-zoomed", True)
        return
    except tk.TclError:
        pass

    try:
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        win.geometry(f"{screen_width}x{screen_height}+0+0")
    except Exception:
        pass


shop = ctk.CTk()
shop.withdraw()
shop.title("E-Commerce User Storefront")
center_window(shop, 1260, 840)
shop.minsize(1100, 760)
shop.configure(fg_color=PALETTE_DARKEST)

auth_win = ctk.CTkToplevel(shop)
auth_win.configure(fg_color=PALETTE_DARK)
auth_win.title("Welcome to ITC Tech Store")
center_window(auth_win, 450, 550)
auth_win.attributes("-topmost", True)

auth_notebook = ctk.CTkTabview(
    auth_win,
    width=400,
    height=450,
    corner_radius=15,
    fg_color=PALETTE_DARK,
    segmented_button_fg_color=PALETTE_DARKEST,
    segmented_button_unselected_color=PALETTE_DARKEST,
    segmented_button_unselected_hover_color=PALETTE_PRIMARY,
    segmented_button_selected_color=PALETTE_PRIMARY,
    segmented_button_selected_hover_color=PALETTE_DARK,
    text_color=PALETTE_MINT
)
auth_notebook.pack(padx=14, pady=14, fill="both", expand=True)

login_tab = auth_notebook.add("Login")
register_tab = auth_notebook.add("Register")

login_email_var = tk.StringVar()
login_pw_var = tk.StringVar()
remember_me_var = tk.BooleanVar(value=False)
login_hint_var = tk.StringVar(value="")

reg_email_var = tk.StringVar()
reg_username_var = tk.StringVar()
reg_pw_var = tk.StringVar()
reg_name_var = tk.StringVar()
reg_contact_var = tk.StringVar()

shop_state = load_shop_state()

auth_session_start = time.perf_counter()
if get_session_connection(SHOP_AUTH_SESSION):
    logger.info(
        "Shop auth session ready",
        extra={"duration_ms": round((time.perf_counter() - auth_session_start) * 1000, 1)},
    )
else:
    logger.warning("Shop auth session unavailable; will retry on login")

MAIN_FONT = ("Segoe UI", 10)
TITLE_FONT = ("Segoe UI", 16, "bold")
BTN_BG = "#0e62a0"
BTN_FG = "white"

def handle_login():
    login_start = time.perf_counter()
    login_identifier = login_email_var.get().strip()
    pw = login_pw_var.get().strip()
    login_hint_var.set("")
    if not login_identifier or not pw:
        messagebox.showwarning("Error", "Please enter your username, email, or phone and password", parent=auth_win)
        return

    try:
        conn = get_session_connection(SHOP_AUTH_SESSION)
        if not conn:
            messagebox.showerror("Error", "Database connection is unavailable.", parent=auth_win)
            return

        normalized_identifier = login_identifier.strip()
        user = buyer_data.fetch_customer_for_email_or_username(conn, normalized_identifier)

        if not user and looks_like_phone_identifier(normalized_identifier):
            contact_variants = build_contact_login_variants(normalized_identifier)
            matching_customers = buyer_data.fetch_customers_by_contact_variants(conn, contact_variants)
            if len(matching_customers) > 1:
                login_hint_var.set("This phone number has multiple accounts. Use your email or username to log in.")
                return
            user = matching_customers[0] if matching_customers else None

        if not user:
            messagebox.showerror("Login Failed", "Invalid username, email, phone, or password", parent=auth_win)
            return

        customer_id, db_username, db_email, db_name, db_contact, db_address, db_password_hash, failed_count, account_locked, locked_until = user
        current_time = datetime.now()

        if account_locked and locked_until and locked_until > current_time:
            remaining_minutes = int((locked_until - current_time).total_seconds() // 60) + 1
            messagebox.showerror(
                "Account Locked",
                f"Too many failed attempts. Try again in {remaining_minutes} minute(s).",
                parent=auth_win,
            )
            return

        if not verify_password(pw, db_password_hash):
            new_failed_count = int(failed_count or 0) + 1
            if new_failed_count >= MAX_LOGIN_ATTEMPTS:
                lock_until = current_time + timedelta(minutes=LOGIN_LOCK_MINUTES)
                buyer_data.mark_customer_login_locked(conn, customer_id, new_failed_count, current_time, lock_until)
                conn.commit()
                messagebox.showerror(
                    "Account Locked",
                    f"Too many failed attempts. Account locked for {LOGIN_LOCK_MINUTES} minutes.",
                    parent=auth_win,
                )
            else:
                buyer_data.mark_customer_login_failed(conn, customer_id, new_failed_count, current_time)
                conn.commit()
                remaining_attempts = MAX_LOGIN_ATTEMPTS - new_failed_count
                messagebox.showerror(
                    "Login Failed",
                    f"Invalid username, email, phone, or password. {remaining_attempts} attempt(s) left.",
                    parent=auth_win,
                )
            return

        if needs_password_upgrade(db_password_hash):
            upgraded_hash = hash_password(pw)
            buyer_data.reset_customer_login_status(conn, customer_id, upgraded_hash)
        else:
            buyer_data.reset_customer_login_status(conn, customer_id)
        conn.commit()

        current_customer['id'] = customer_id
        current_customer['username'] = db_username
        current_customer['email'] = db_email
        current_customer['name'] = db_name
        current_customer['contact'] = db_contact
        current_customer['address'] = db_address

        persist_login_preference(normalized_identifier, remember_me_var.get())
        
        checkout_name_lbl.configure(text=f"{current_customer['name']}")
        checkout_email_lbl.configure(text=f"{current_customer['email']}")
        checkout_contact_lbl.configure(text=f"{current_customer['contact']}")
        checkout_addr_lbl.configure(text=f"{current_customer['address']}")

        auth_win.configure(cursor="watch")
        auth_win.update_idletasks()
        try:
            filter_products()
            restore_cart_cache_for_current_user()
        finally:
            auth_win.configure(cursor="")

        auth_win.withdraw()
        shop.deiconify()
        maximize_window(shop)
        shop.update_idletasks()
        shop.lift()
        shop.focus_force()
        logger.debug(
            "Buyer login flow completed",
            extra={"duration_ms": round((time.perf_counter() - login_start) * 1000, 1)},
        )
    except Exception as e:
        messagebox.showerror("Error", f"Database error: {e}", parent=auth_win)

def handle_register():
    email = reg_email_var.get().strip().lower()
    username = reg_username_var.get().strip()
    pw = reg_pw_var.get().strip()
    name = reg_name_var.get().strip()
    contact_raw = reg_contact_var.get().strip()
    address = reg_addr_text.get("1.0", tk.END).strip()
    
    if not email or not username or not pw or not name or not contact_raw or not address:
        messagebox.showwarning("Error", "Please fill out all fields", parent=auth_win)
        return

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        messagebox.showwarning(
            "Error",
            "Username must be 3-50 characters and use only letters, numbers, dot, underscore, or dash.",
            parent=auth_win,
        )
        return
        
    if "@" not in email or "." not in email:
        messagebox.showwarning("Error", "Invalid email format", parent=auth_win)
        return
        
    if len(contact_raw) != 10 or not contact_raw.isdigit():
        messagebox.showwarning("Error", "Contact number must be exactly 10 digits", parent=auth_win)
        return

    password_ok, password_message = validate_password_strength(pw)
    if not password_ok:
        messagebox.showwarning("Weak Password", password_message, parent=auth_win)
        return
        
    contact = "+63" + contact_raw
    contact_variants = build_contact_login_variants(contact)
    hashed_pw = hash_password(pw)
    
    try:
        conn = get_session_connection(SHOP_AUTH_SESSION)
        if not conn:
            messagebox.showerror("Error", "Database connection is unavailable.", parent=auth_win)
            return

        if buyer_data.customer_exists_by_email(conn, email):
            messagebox.showerror("Error", "Email is already registered", parent=auth_win)
            return

        if buyer_data.customer_exists_by_username(conn, username):
            messagebox.showerror("Error", "Username is already taken", parent=auth_win)
            return

        if buyer_data.customer_exists_by_contact_variants(conn, contact_variants):
            messagebox.showerror("Error", "Contact number is already registered", parent=auth_win)
            return

        buyer_data.insert_customer(conn, email, username, hashed_pw, name, contact, address)
        conn.commit()
        
        messagebox.showinfo("Success", "Registration complete! You can now log in.", parent=auth_win)
        auth_notebook.set("Login")
        login_email_var.set(username)
        login_pw_var.set("")
    except Exception as e:
        messagebox.showerror("Error", f"Registration error: {e}", parent=auth_win)

ctk.CTkLabel(login_tab, text="Welcome Back!", font=ctk.CTkFont(size=26, weight="bold"), text_color=PALETTE_MINT).pack(pady=(20, 20))
ctk.CTkLabel(login_tab, text="Username, Email, or Phone", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).pack(anchor="w", padx=40)

login_email_entry = ctk.CTkEntry(login_tab, textvariable=login_email_var, width=320, height=45, corner_radius=10, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, placeholder_text="Enter username, email, or phone", placeholder_text_color="#7FB8A3")
login_email_entry.pack(padx=40, pady=(5,10))
ctk.CTkLabel(login_tab, text="Password", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).pack(anchor="w", padx=40, pady=(15, 5))
login_password_row = ctk.CTkFrame(login_tab, fg_color="transparent")
login_password_row.pack(padx=40, pady=(5,10), fill="x")
login_password_entry = ctk.CTkEntry(login_password_row, textvariable=login_pw_var, show="*", width=250, height=45, corner_radius=10, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, placeholder_text_color="#7FB8A3")
login_password_entry.pack(fill="x", expand=True)


def set_password_toggle_icon(toggle_button, is_visible):
    if OPEN_EYE_ICON and CLOSED_EYE_ICON:
        toggle_button.configure(image=OPEN_EYE_ICON if is_visible else CLOSED_EYE_ICON, text="")
    else:
        toggle_button.configure(image=None, text=EYE_ICON_FALLBACK)


def toggle_login_password_visibility():
    if login_password_entry.cget("show") == "":
        login_password_entry.configure(show="*")
        login_password_toggle_btn.configure(fg_color=PALETTE_DARKEST)
        set_password_toggle_icon(login_password_toggle_btn, False)
    else:
        login_password_entry.configure(show="")
        login_password_toggle_btn.configure(fg_color=PALETTE_PRIMARY)
        set_password_toggle_icon(login_password_toggle_btn, True)


login_password_toggle_btn = ctk.CTkButton(
    login_password_row,
    text="",
    image=CLOSED_EYE_ICON,
    width=20,
    height=20,
    corner_radius=6,
    fg_color=PALETTE_DARKEST,
    hover_color=PALETTE_DARK,
    text_color=PALETTE_TEXT,
    font=ctk.CTkFont(size=9),
    command=toggle_login_password_visibility,
)
login_password_toggle_btn.place(relx=1.0, rely=0.5, x=-14, anchor="e")
set_password_toggle_icon(login_password_toggle_btn, False)

login_hint_label = ctk.CTkLabel(
    login_tab,
    textvariable=login_hint_var,
    text_color="#FFD166",
    font=ctk.CTkFont(size=12),
    wraplength=320,
    justify="left",
)
login_hint_label.pack(anchor="w", padx=40, pady=(2, 0))


def clear_login_inline_hint(event=None):
    if login_hint_var.get():
        login_hint_var.set("")
    return None

ctk.CTkCheckBox(
    login_tab,
    text="Remember Me",
    variable=remember_me_var,
    onvalue=True,
    offvalue=False,
    text_color=PALETTE_TEXT,
    fg_color=PALETTE_PRIMARY,
    hover_color=PALETTE_DARK,
    checkmark_color=PALETTE_MINT
).pack(anchor="w", padx=40, pady=(8, 0))
ctk.CTkButton(login_tab, text="Log In", font=ctk.CTkFont(size=16, weight="bold"), command=handle_login, width=320, height=50, corner_radius=10, fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST).pack(pady=24)


def handle_login_enter(event=None):
    if auth_notebook.get() == "Login":
        handle_login()
        return "break"
    return None


login_email_entry.bind("<Return>", handle_login_enter)
login_password_entry.bind("<Return>", handle_login_enter)
login_email_entry.bind("<KeyRelease>", clear_login_inline_hint)
login_password_entry.bind("<KeyRelease>", clear_login_inline_hint)
auth_win.bind("<Return>", handle_login_enter)

restore_login_preference()

ctk.CTkLabel(register_tab, text="Email:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=0, column=0, sticky="e", padx=10, pady=10)
ctk.CTkEntry(register_tab, textvariable=reg_email_var, width=240, height=35, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT).grid(row=0, column=1)

ctk.CTkLabel(register_tab, text="Username:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="e", padx=10, pady=10)
ctk.CTkEntry(register_tab, textvariable=reg_username_var, width=240, height=35, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT).grid(row=1, column=1)

ctk.CTkLabel(register_tab, text="Password:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=2, column=0, sticky="e", padx=10, pady=10)
register_password_row = ctk.CTkFrame(register_tab, fg_color="transparent")
register_password_row.grid(row=2, column=1, sticky="ew")
reg_password_entry = ctk.CTkEntry(register_password_row, textvariable=reg_pw_var, show="*", width=240, height=35, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT)
reg_password_entry.pack(fill="x", expand=True)


def toggle_register_password_visibility():
    if reg_password_entry.cget("show") == "":
        reg_password_entry.configure(show="*")
        register_password_toggle_btn.configure(fg_color=PALETTE_DARKEST)
        set_password_toggle_icon(register_password_toggle_btn, False)
    else:
        reg_password_entry.configure(show="")
        register_password_toggle_btn.configure(fg_color=PALETTE_PRIMARY)
        set_password_toggle_icon(register_password_toggle_btn, True)


register_password_toggle_btn = ctk.CTkButton(
    register_password_row,
    text="",
    image=CLOSED_EYE_ICON,
    width=20,
    height=20,
    corner_radius=6,
    fg_color=PALETTE_DARKEST,
    hover_color=PALETTE_DARK,
    text_color=PALETTE_TEXT,
    font=ctk.CTkFont(size=9),
    command=toggle_register_password_visibility,
)
register_password_toggle_btn.place(relx=1.0, rely=0.5, x=-11, anchor="e")
set_password_toggle_icon(register_password_toggle_btn, False)

ctk.CTkLabel(register_tab, text="Full Name:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="e", padx=10, pady=10)
ctk.CTkEntry(register_tab, textvariable=reg_name_var, width=240, height=35, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT).grid(row=3, column=1)

ctk.CTkLabel(register_tab, text="Contact (+63):", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=4, column=0, sticky="e", padx=10, pady=10)
reg_contact_entry = ctk.CTkEntry(register_tab, textvariable=reg_contact_var, width=240, height=35, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT)
reg_contact_entry.grid(row=4, column=1)

ctk.CTkLabel(register_tab, text="Address:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=5, column=0, sticky="ne", padx=10, pady=10)
reg_addr_text = ctk.CTkTextbox(register_tab, width=240, height=80, corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, border_width=1, text_color=PALETTE_MINT)
reg_addr_text.grid(row=5, column=1, pady=10)

ctk.CTkButton(register_tab, text="Create Account", font=ctk.CTkFont(size=15, weight="bold"), fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, command=handle_register, width=240, height=45, corner_radius=10).grid(row=6, columnspan=2, pady=15)


cart_items = []
subtotal_var = tk.DoubleVar(value=0.0)
vat_var = tk.DoubleVar(value=0.0)
grand_total_var = tk.DoubleVar(value=0.0)
subtotal_display_var = tk.StringVar(value="PHP 0.00")
vat_display_var = tk.StringVar(value="PHP 0.00")
grand_total_display_var = tk.StringVar(value="PHP 0.00")
payment_method_var = tk.StringVar(value="Cash")
first_product_load_logged = False

def load_products(search_term="", category="All Categories"):
    global first_product_load_logged

    load_start = time.perf_counter()
    loaded_rows_count = 0

    existing_rows = products_tree.get_children()
    if existing_rows:
        products_tree.delete(*existing_rows)
        
    try:
        conn = get_session_connection(SHOP_READ_SESSION)
        if not conn:
            messagebox.showerror("Database Error", "Database connection is unavailable.")
            return

        results = buyer_data.fetch_available_products(conn, search_term, category)
        loaded_rows_count = len(results)
        
        for array in results:
            display_values = (array[0], array[1], format_price_display(array[2]), array[3], array[4])
            products_tree.insert(parent='', index='end', iid=array[0], values=display_values, tag="orow")
        
        products_tree.tag_configure('orow', background="#16362B", foreground=PALETTE_MINT)
    except Exception as e:
        messagebox.showerror("Database Error", f"Error fetching products: {e}")
    finally:
        if not first_product_load_logged:
            elapsed_ms = (time.perf_counter() - load_start) * 1000
            logger.debug(
                "Shop first product load completed",
                extra={"duration_ms": round(elapsed_ms, 1), "rows_loaded": loaded_rows_count},
            )
            first_product_load_logged = True

def filter_products():
    term = search_entry.get().strip()
    cat = shop_category_var.get()
    load_products(term, cat)


def show_product_details(show_warning=True):
    try:
        selected_item = products_tree.selection()[0]
    except IndexError:
        if show_warning:
            messagebox.showwarning("Product Details", "Please select a product first.")
        return

    item_id = str(products_tree.item(selected_item)["values"][0])
    read_conn = get_session_connection(SHOP_READ_SESSION)
    if not read_conn:
        if show_warning:
            messagebox.showerror("Product Details", "Database connection is unavailable.")
        return

    try:
        product_details = buyer_data.fetch_product_details(read_conn, item_id)
    except Exception:
        product_details = None
    if not product_details:
        if show_warning:
            messagebox.showerror("Product Details", "Could not load product details.")
        return

    details_win = ctk.CTkToplevel(shop)
    details_win.title(f"Product Details - {product_details['name']}")
    center_window(details_win, 920, 560)
    details_win.configure(fg_color=PALETTE_DARK)
    details_win.transient(shop)
    details_win.bind("<Escape>", lambda event: details_win.destroy())

    container = ctk.CTkFrame(details_win, fg_color=PALETTE_DARK, corner_radius=12)
    container.pack(fill="both", expand=True, padx=16, pady=16)
    container.grid_columnconfigure(0, weight=0)
    container.grid_columnconfigure(1, weight=1)
    container.grid_rowconfigure(0, weight=1)

    image_column = ctk.CTkFrame(container, fg_color=PALETTE_DARKEST, corner_radius=10)
    image_column.grid(row=0, column=0, sticky="n", padx=(0, 14), pady=(8, 4))

    image_square = ctk.CTkFrame(image_column, width=320, height=320, fg_color=PALETTE_DARK, corner_radius=8)
    image_square.pack(padx=12, pady=12)
    image_square.pack_propagate(False)

    image_preview_label = ctk.CTkLabel(
        image_square,
        text="",
        fg_color="transparent",
        text_color="#8FC9B4",
        wraplength=280,
        justify="center",
    )
    image_preview_label.pack(expand=True)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    resolved_image_path = buyer_utils.resolve_product_image_path(product_details.get("image_path"), script_dir)
    if resolved_image_path and Image is not None:
        try:
            preview_image = Image.open(resolved_image_path)
            preview_image.thumbnail((300, 300))
            preview_ctk_image = ctk.CTkImage(
                light_image=preview_image,
                dark_image=preview_image,
                size=(preview_image.width, preview_image.height),
            )
            image_preview_label.configure(image=preview_ctk_image, text="")
            image_preview_label.image = preview_ctk_image
        except Exception:
            image_preview_label.configure(image=None, text="Image file was found but could not be rendered.")
    elif resolved_image_path and Image is None:
        image_preview_label.configure(image=None, text="Image preview unavailable in this Python runtime.")
    else:
        image_preview_label.configure(image=None, text="No product image available.")

    info_column = ctk.CTkFrame(container, fg_color=PALETTE_DARKEST, corner_radius=10)
    info_column.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)

    ctk.CTkLabel(info_column, text=product_details["name"], font=ctk.CTkFont(size=24, weight="bold"), text_color=PALETTE_MINT).pack(anchor="w", padx=12, pady=(12, 4))
    ctk.CTkLabel(info_column, text=f"ID: {product_details['item_id']}   |   Category: {product_details['category']}", font=ctk.CTkFont(size=13), text_color=PALETTE_TEXT).pack(anchor="w", padx=12)
    ctk.CTkLabel(info_column, text=f"Price: P {float(product_details['price']):,.2f}   |   Stock: {product_details['quantity']}", font=ctk.CTkFont(size=15, weight="bold"), text_color=PALETTE_MINT).pack(anchor="w", padx=12, pady=(6, 10))

    ctk.CTkLabel(info_column, text="Description", font=ctk.CTkFont(size=15, weight="bold"), text_color=PALETTE_TEXT).pack(anchor="w", padx=12)
    description_textbox = ctk.CTkTextbox(
        info_column,
        height=250,
        fg_color=PALETTE_DARK,
        border_color=PALETTE_PRIMARY,
        border_width=1,
        text_color=PALETTE_MINT,
    )
    description_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 12))
    description_textbox.insert("1.0", product_details.get("description") or "No description available yet.")
    description_textbox.configure(state="disabled")

    actions_frame = ctk.CTkFrame(info_column, fg_color="transparent")
    actions_frame.pack(fill="x", padx=12, pady=(0, 12))

    def add_from_details():
        add_to_cart()
        details_win.destroy()

    ctk.CTkButton(
        actions_frame,
        text="Add To Cart",
        fg_color=PALETTE_MINT,
        hover_color=PALETTE_PRIMARY,
        text_color=PALETTE_DARKEST,
        font=ctk.CTkFont(size=13, weight="bold"),
        width=140,
        height=40,
        command=add_from_details,
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        actions_frame,
        text="Close",
        fg_color=PALETTE_PRIMARY,
        hover_color=PALETTE_DARKEST,
        text_color=PALETTE_TEXT,
        font=ctk.CTkFont(size=13, weight="bold"),
        width=120,
        height=40,
        command=details_win.destroy,
    ).pack(side="left")

def add_to_cart():
    try:
        selected_item = products_tree.selection()[0]
        item_values = products_tree.item(selected_item)['values']
        
        item_id = str(item_values[0])
        name = str(item_values[1])
        price = parse_price_input(item_values[2])
        available_qty = int(item_values[3])
        
        try:
            buy_qty = int(qty_entry.get())
        except ValueError:
            messagebox.showwarning("Error", "Please enter a valid number for quantity.")
            return
            
        if buy_qty <= 0:
            messagebox.showwarning("Error", "Quantity must be greater than zero.")
            return
            
        if buy_qty > available_qty:
            messagebox.showwarning("Error", "Not enough stock available!")
            return
            
        existing_cart_item = next((item for item in cart_items if item['item_id'] == item_id), None)
        if existing_cart_item:
            new_quantity = existing_cart_item['quantity'] + buy_qty
            if new_quantity > available_qty:
                messagebox.showwarning("Error", "Not enough stock available for combined quantity!")
                return
            existing_cart_item['quantity'] = new_quantity
            existing_cart_item['subtotal'] = existing_cart_item['price'] * new_quantity
            action_message = f"Updated {name} quantity to {new_quantity}."
        else:
            cart_items.append({
                'item_id': item_id,
                'name': name,
                'price': price,
                'quantity': buy_qty,
                'subtotal': price * buy_qty
            })
            action_message = f"Added {buy_qty}x {name} to cart."
        
        refresh_cart_display()
        messagebox.showinfo("Cart", action_message)
        qty_entry.delete(0, tk.END)
        qty_entry.insert(0, "1")
        
    except IndexError:
        messagebox.showwarning("Error", "Please select a product from the list to add.")

def refresh_cart_display(save_cache=True):
    existing_rows = cart_tree.get_children()
    if existing_rows:
        cart_tree.delete(*existing_rows)
        
    total = 0.0
    for idx, item in enumerate(cart_items):
        cart_tree.insert(parent='', index='end', iid=str(idx), values=(item['name'], f"PHP {item['price']:,.2f}", item['quantity'], f"PHP {item['subtotal']:,.2f}"))
        total += item['subtotal']
            
    subtotal_var.set(round(total, 2))
    subtotal_display_var.set(f"PHP {total:,.2f}")
        
    vat = total * 0.12
    vat_var.set(round(vat, 2))
    vat_display_var.set(f"PHP {vat:,.2f}")
        
    grand_total = total + vat
    grand_total_var.set(round(grand_total, 2))
    grand_total_display_var.set(f"PHP {grand_total:,.2f}")

    if save_cache:
        persist_cart_cache_for_current_user()

def remove_from_cart(require_confirmation=False):
    try:
        selected_item = cart_tree.selection()[0]
        idx = int(selected_item)
        removed_name = cart_items[idx]['name']

        if require_confirmation:
            decision = messagebox.askyesno("Remove Item", f"Remove '{removed_name}' from your cart?")
            if not decision:
                return

        del cart_items[idx]
        refresh_cart_display()
        messagebox.showinfo("Cart Update", f"Removed {removed_name} from the cart.")
    except (IndexError, ValueError):
        messagebox.showwarning("Error", "Please select an item in your cart to remove.")


def remove_from_cart_with_prompt(event=None):
    remove_from_cart(require_confirmation=True)
    return "break"

def clear_cart():
    if not cart_items:
        return
    decision =messagebox.askquestion("Clear Cart", "Are you sure you want to remove all items from your cart?")
    if decision == 'yes':
        cart_items.clear()
        refresh_cart_display()
        messagebox.showinfo("Cart Update", "Cart has been cleared.")

def show_digital_receipt(filename):
    receipt_win = ctk.CTkToplevel(shop)
    receipt_win.title("Digital Receipt")
    receipt_win.geometry("400x500")
    receipt_win.configure(fg_color=PALETTE_DARK)
    receipt_win.bind("<Escape>", lambda event: receipt_win.destroy())
    
    txt = ctk.CTkTextbox(receipt_win, font=("Courier", 10), fg_color=PALETTE_DARKEST, text_color=PALETTE_MINT)
    txt.pack(fill="both", expand=True, padx=20, pady=20)
    
    try:
        with open(filename, "r") as file:
            content = file.read()
            txt.insert("1.0", content)
            txt.configure(state="disabled")
    except Exception as e:
        txt.insert("1.0", f"Error loading receipt: {e}")
        
    ctk.CTkButton(receipt_win, text="Close Receipt", fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=12), command=receipt_win.destroy).pack(pady=10)
    
    receipt_win.grab_set()
    shop.wait_window(receipt_win)

def checkout():
    if not cart_items:
        messagebox.showwarning("Cart Empty", "You must add items to the cart before checking out.")
        return
        
    payment_method = payment_method_var.get()
    if not payment_method:
        messagebox.showwarning("Details Needed", "Please select a payment method.")
        return
        
    customer_email = current_customer['email']
    customer_username = current_customer['username']
    customer_name = current_customer['name']
    customer_address = current_customer['address']
    contact_number = current_customer['contact']

    if not customer_email or not customer_name:
        messagebox.showwarning("Session Required", "Please log in again before checking out.")
        return

    conn = None
    try:
        checkout_button.configure(state="disabled", text="Processing Checkout...")
    except Exception:
        pass
    shop.update_idletasks()
    
    try:
        conn = get_session_connection(SHOP_AUTH_SESSION)
        if not conn:
            messagebox.showerror("Checkout Error", "Database connection is unavailable.")
            return

        subtotal = subtotal_var.get()
        vat = vat_var.get()
        grand_total = grand_total_var.get()

        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = generate_unique_order_id(conn)

        order_id = buyer_data.create_order(
            conn,
            order_id,
            customer_name,
            customer_username,
            customer_email,
            contact_number,
            customer_address,
            subtotal,
            vat,
            grand_total,
            payment_method,
            order_date,
            "Pending",
        )
        
        for item in cart_items:
            buyer_data.insert_order_item(conn, order_id, item['item_id'], item['quantity'], item['price'])
            
            stock_rows_updated = buyer_data.decrement_stock(conn, item['item_id'], item['quantity'])
            if stock_rows_updated != 1:
                raise ValueError(
                    f"Not enough stock left for '{item['name']}'. Please refresh and review your cart."
                )
            
        conn.commit()
        
        receipt_filename = f"receipt_ORD{order_id}.txt"
        try:
            receipt_filename = buyer_utils.write_receipt_file(
                order_id,
                customer_name,
                customer_email,
                contact_number,
                customer_address,
                subtotal,
                vat,
                grand_total,
                payment_method,
                order_date,
                cart_items,
            )
        except Exception as receipt_error:
            logger.error("Could not write receipt file", extra={"error": str(receipt_error)})
        
        show_digital_receipt(receipt_filename)
        
        messagebox.showinfo("Success", "Checkout successful! Receipt generated. Thank you for your order.")
        
        cart_items.clear()
        refresh_cart_display()
        search_entry.delete(0, tk.END)
        shop_category_var.set("All Categories")
        shop.after_idle(filter_products)
        
    except Exception as e:
        if conn:
            conn.rollback()
        messagebox.showerror("Checkout Error", f"An error occurred during checkout: {e}")
    finally:
        try:
            checkout_button.configure(state="normal", text="Checkout")
        except Exception:
            pass

def my_orders():
    email = current_customer['email']
    if not email:
        messagebox.showerror("Error", "You must be logged in to view your orders.")
        return

    try:
        conn = get_session_connection(SHOP_AUTH_SESSION)
        if not conn:
            messagebox.showerror("Database Error", "Database connection is unavailable.")
            return

        results = buyer_data.fetch_customer_orders(conn, email)
        
        if results:
            history_win = ctk.CTkToplevel(shop)
            history_win.title(f"Order History - {current_customer['name']}")
            center_window(history_win, 600, 350)
            history_win.configure(fg_color=PALETTE_DARK)
            
            ctk.CTkLabel(history_win, text=f"Order History", text_color=PALETTE_MINT, font=("Segoe UI", 14, "bold"), fg_color=PALETTE_DARK).pack(pady=10)
            
            tree = ttk.Treeview(history_win, columns=("ID", "Date", "Total", "Status"), show="headings", height=8)
            tree.heading("ID", text="ID")
            tree.heading("Date", text="Date")
            tree.heading("Total", text="Total")
            tree.heading("Status", text="Status")
            
            tree.column("ID", width=80)
            tree.column("Date", width=150)
            tree.column("Total", width=100)
            tree.column("Status", width=120)
            
            for row in results:
                display_row = (row[0], row[1], format_price_display(row[2]), row[3])
                tree.insert("", "end", values=display_row)
                
            tree.pack(fill="both", expand=True, padx=20, pady=10)
            ctk.CTkButton(history_win, text="Close", command=history_win.destroy, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=12), width=90).pack(pady=10)
            
        else:
            messagebox.showinfo("No Orders Found", "You haven't placed any orders yet.")
    except Exception as e:
        messagebox.showerror("Database Error", f"Could not retrieve orders: {e}")

def logout():
    decision =messagebox.askyesno("Logout", "Are you sure you want to log out?")
    if decision:
        shop.withdraw()
        
        current_customer['id'] = None
        current_customer['username'] = None
        current_customer['email'] = None
        current_customer['name'] = None
        current_customer['contact'] = None
        current_customer['address'] = None
        
        cart_items.clear()
        refresh_cart_display(save_cache=False)
        
        login_pw_var.set("")
        if auth_win.winfo_exists():
            auth_notebook.set("Login")
            auth_win.deiconify()
            auth_win.lift()
            auth_win.focus_force()


header_frame = ctk.CTkFrame(shop, fg_color=PALETTE_DARK, height=60, corner_radius=0)
header_frame.pack(fill="x")
ctk.CTkLabel(header_frame, text="Store Dashboard", font=ctk.CTkFont(size=24, weight="bold"), text_color=PALETTE_MINT).pack(side="left", padx=20, pady=10)

ctk.CTkButton(header_frame, text="Log Out", fg_color="#A63D3D", hover_color="#8A2F2F", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=12, weight="bold"), command=logout, width=80).pack(side="right", padx=10, pady=15)
ctk.CTkButton(header_frame, text="My Orders", fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, font=ctk.CTkFont(size=12, weight="bold"), command=my_orders, width=100).pack(side="right", padx=10, pady=15)

main_frame = ctk.CTkFrame(shop, fg_color="transparent", corner_radius=0)
main_frame.pack(fill="both", expand=True, padx=20, pady=20)

left_frame = ctk.CTkFrame(main_frame, fg_color=PALETTE_DARK, corner_radius=10)
left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

ctk.CTkLabel(left_frame, text="Shopping Menu", text_color=PALETTE_MINT, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))

filter_frame = ctk.CTkFrame(left_frame, fg_color="transparent", corner_radius=15)
filter_frame.pack(fill="x", padx=10)

ctk.CTkLabel(filter_frame, text="Search:", text_color=PALETTE_TEXT).pack(side="left", padx=(10, 5))
search_entry = ctk.CTkEntry(filter_frame, width=150, height=40, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT)
search_entry.pack(side="left", padx=5)


def focus_search_entry(event=None):
    search_entry.focus_set()
    search_entry.select_range(0, tk.END)
    return "break"


shop.bind("<Control-f>", focus_search_entry)
shop.bind("<Control-F>", focus_search_entry)

ctk.CTkLabel(filter_frame, text="Category:", text_color=PALETTE_TEXT).pack(side="left", padx=(10, 5))
shop_category_var = ctk.StringVar(value="All Categories")
shop_category_combo = ctk.CTkOptionMenu(filter_frame, variable=shop_category_var, width=160, 
                                   values=["All Categories", "Mainstream Laptops", "Premium Laptops", "Gaming Laptops", "Peripherals"],
                                   fg_color=PALETTE_DARKEST, button_color=PALETTE_PRIMARY, button_hover_color=PALETTE_DARK,
                                   text_color=PALETTE_TEXT)
shop_category_combo.pack(side="left", padx=5)

ctk.CTkButton(filter_frame, text="Filter", command=filter_products, width=80, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), corner_radius=10, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT).pack(side="left", padx=10)

products_tree = ttk.Treeview(left_frame, columns=("ID", "Name", "Price", "Qty", "Category"), show='headings', height=13)
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background=PALETTE_DARK, foreground=PALETTE_MINT)
style.configure("Treeview", font=("Segoe UI", 11), rowheight=38, background="#0F231D", foreground=PALETTE_MINT, fieldbackground="#0F231D")
style.map('Treeview', background=[('selected', PALETTE_PRIMARY)], foreground=[('selected', PALETTE_TEXT)])

products_tree.heading("ID", text="ID")
products_tree.heading("Name", text="Name")
products_tree.heading("Price", text="Price")
products_tree.heading("Qty", text="Qty")
products_tree.heading("Category", text="Category")

products_tree.column("ID", width=80)
products_tree.column("Name", width=180)
products_tree.column("Price", width=80)
products_tree.column("Qty", width=60)
products_tree.column("Category", width=120)
products_tree.pack(fill="both", expand=True, padx=10, pady=10)
products_tree.bind("<Double-1>", lambda event: show_product_details(show_warning=False))

add_frame = ctk.CTkFrame(left_frame, fg_color="transparent", corner_radius=15)
add_frame.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(add_frame, text="Qty:", text_color=PALETTE_TEXT).pack(side="left", padx=(10, 5))
qty_entry = ctk.CTkEntry(add_frame, width=50, height=40, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT)
qty_entry.insert(0, "1")
qty_entry.pack(side="left", padx=5)
ctk.CTkButton(add_frame,  fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, font=ctk.CTkFont(weight="bold"), text="Add to Cart", command=add_to_cart, width=120).pack(side="left", padx=10)
ctk.CTkButton(add_frame, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, font=ctk.CTkFont(weight="bold"), text="View Details", command=show_product_details, width=120).pack(side="left", padx=4)

right_frame = ctk.CTkScrollableFrame(main_frame, fg_color=PALETTE_DARK, corner_radius=10, width=520)
right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

ctk.CTkLabel(right_frame, text="Shopping Cart", text_color=PALETTE_MINT, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))

cart_tree = ttk.Treeview(right_frame, columns=("Name", "Price", "Qty", "Subtotal"), show='headings', height=7)
cart_tree.heading("Name", text="Name")
cart_tree.heading("Price", text="Price")
cart_tree.heading("Qty", text="Qty")
cart_tree.heading("Subtotal", text="Subtotal")

cart_tree.column("Name", width=150)
cart_tree.column("Price", width=70)
cart_tree.column("Qty", width=50)
cart_tree.column("Subtotal", width=80)
cart_tree.pack(fill="both", expand=True, padx=10, pady=10)
cart_tree.bind("<Delete>", remove_from_cart_with_prompt)

cart_action_frame = ctk.CTkFrame(right_frame, fg_color="transparent", corner_radius=15)
cart_action_frame.pack(fill="x", padx=10)
ctk.CTkButton(cart_action_frame,  fg_color="#ff4c4c", hover_color="#cc0000", text="Remove", command=remove_from_cart, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), corner_radius=10).pack(side="left", padx=5)
ctk.CTkButton(cart_action_frame,  fg_color=PALETTE_DARKEST, hover_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, text="Clear", command=clear_cart, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), corner_radius=10).pack(side="right", padx=5)

checkout_frame = ctk.CTkFrame(right_frame, fg_color="transparent", corner_radius=15)
checkout_frame.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(checkout_frame, text="Subtotal:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=0, column=0, sticky="w", pady=(5,0))
ctk.CTkLabel(checkout_frame, textvariable=subtotal_display_var, text_color=PALETTE_MINT, font=ctk.CTkFont(size=14)).grid(row=0, column=1, sticky="w", pady=(5,0))

ctk.CTkLabel(checkout_frame, text="VAT (12%):", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")
ctk.CTkLabel(checkout_frame, textvariable=vat_display_var, text_color=PALETTE_MINT, font=ctk.CTkFont(size=14)).grid(row=1, column=1, sticky="w")

ctk.CTkLabel(checkout_frame, text="Grand Total:", font=ctk.CTkFont(size=18, weight="bold"), text_color=PALETTE_MINT).grid(row=2, column=0, sticky="w", pady=(10,5))
ctk.CTkLabel(checkout_frame, textvariable=grand_total_display_var, font=ctk.CTkFont(size=18, weight="bold"), text_color=PALETTE_MINT).grid(row=2, column=1, sticky="w", pady=(10,5))

payment_frame = ctk.CTkFrame(right_frame, fg_color="transparent", corner_radius=8)
payment_frame.pack(fill="x", padx=10)

ctk.CTkLabel(payment_frame, text="Customer Info:", text_color=PALETTE_MINT, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 10))
payment_combo = ctk.CTkOptionMenu(payment_frame, variable=payment_method_var, values=["Cash", "GCash", "Credit/Debit Card", "PayMaya"], width=180, fg_color=PALETTE_DARK, button_color=PALETTE_PRIMARY, button_hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT)
payment_combo.grid(row=0, column=1, sticky="w", padx=5)

ctk.CTkLabel(payment_frame, text="Name:", text_color=PALETTE_TEXT).grid(row=1, column=0, sticky="w", pady=2, padx=5)
checkout_name_lbl = ctk.CTkLabel(payment_frame, text="[Name]", font=ctk.CTkFont(weight="bold"), text_color=PALETTE_MINT)
checkout_name_lbl.grid(row=1, column=1, sticky="w", padx=5)

ctk.CTkLabel(payment_frame, text="Email:", text_color=PALETTE_TEXT).grid(row=2, column=0, sticky="w", pady=2, padx=5)
checkout_email_lbl = ctk.CTkLabel(payment_frame, text="[Email]", text_color=PALETTE_MINT)
checkout_email_lbl.grid(row=2, column=1, sticky="w", padx=5)

ctk.CTkLabel(payment_frame, text="Contact:", text_color=PALETTE_TEXT).grid(row=3, column=0, sticky="w", pady=2, padx=5)
checkout_contact_lbl = ctk.CTkLabel(payment_frame, text="[Contact]", text_color=PALETTE_MINT)
checkout_contact_lbl.grid(row=3, column=1, sticky="w", padx=5)

ctk.CTkLabel(payment_frame, text="Address:", text_color=PALETTE_TEXT).grid(row=4, column=0, sticky="nw", pady=2, padx=5)
checkout_addr_lbl = ctk.CTkLabel(payment_frame, text="[Address]", wraplength=260, justify="left", text_color=PALETTE_MINT)
checkout_addr_lbl.grid(row=4, column=1, sticky="w", padx=5, pady=2)

checkout_button = ctk.CTkButton(
    right_frame,
    fg_color=PALETTE_MINT,
    hover_color=PALETTE_PRIMARY,
    text_color=PALETTE_DARKEST,
    font=ctk.CTkFont(size=14, weight="bold"),
    text="Checkout",
    command=checkout,
)
checkout_button.pack(fill="x", padx=10, pady=10)

def on_shop_app_close():
    close_session_connection(SHOP_READ_SESSION)
    close_session_connection(SHOP_AUTH_SESSION)
    try:
        auth_win.destroy()
    except Exception:
        pass
    shop.destroy()

shop.protocol("WM_DELETE_WINDOW", on_shop_app_close)
auth_win.protocol("WM_DELETE_WINDOW", on_shop_app_close)

logger.info(
    "Shop UI ready",
    extra={"duration_seconds": round(time.perf_counter() - SHOP_START_TS, 3)},
)
shop.mainloop()
