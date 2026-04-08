import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import random
import csv
import time
from datetime import datetime, timedelta
from database import connectDB, setup_database, get_session_connection, close_session_connection
from services import admin_data_service as admin_data
from services.format_utils import parse_price_input, format_price_display
from security_utils import (
    hash_password,
    needs_password_upgrade,
    validate_password_strength,
    verify_password,
)

APP_START_TS = time.perf_counter()
db_setup_start = time.perf_counter()
setup_database()
print(f"[startup] Admin DB setup check: {time.perf_counter() - db_setup_start:.3f}s")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

PALETTE_DARKEST = "#091413"
PALETTE_DARK = "#285A48"
PALETTE_PRIMARY = "#408A71"
PALETTE_MINT = "#B0E4CC"
PALETTE_TEXT = "#E8FFF5"
MAX_ADMIN_LOGIN_ATTEMPTS = 5
ADMIN_LOCK_MINUTES = 15

window = ctk.CTk()
window.title("Inventory System")
window.configure(fg_color=PALETTE_DARKEST)

def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width / 2) - (width / 2)
    y = (screen_height / 2) - (height / 2)
    win.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

center_window(window, 1180, 820)
window.minsize(1080, 720)
try:
    window.state("zoomed")
except tk.TclError:
    pass

# Hide main window initially for the gatekeeper
window.withdraw()

# --- Admin Login Gatekeeper ---
login_window = ctk.CTkToplevel(window)
login_window.title("Admin Log In")
center_window(login_window, 450, 450)
login_window.resizable(False, False)
login_window.attributes("-topmost", True)
login_window.configure(fg_color=PALETTE_DARK)
header_font=ctk.CTkFont(size=20, weight="bold")

def check_login(event=None):
    username = username_entry.get()
    password = password_entry.get()
    
    if not username.strip() or not password.strip():
        messagebox.showwarning("Error", "Please enter both username and password.")
        return

    cursor.connection.ping()
    cursor.execute(
        """
        SELECT id, username, password, COALESCE(failed_login_count, 0),
               COALESCE(account_locked, 0), locked_until
        FROM users
        WHERE username = %s
        """,
        (username.strip(),),
    )
    user = cursor.fetchone()

    if not user:
        messagebox.showerror("Error", "Invalid username or password.")
        return

    user_id, _, stored_password_hash, failed_count, account_locked, locked_until = user
    current_time = datetime.now()

    if account_locked and locked_until and locked_until > current_time:
        remaining_minutes = int((locked_until - current_time).total_seconds() // 60) + 1
        messagebox.showerror(
            "Account Locked",
            f"Too many failed attempts. Try again in {remaining_minutes} minute(s).",
        )
        return

    if not verify_password(password, stored_password_hash):
        new_failed_count = int(failed_count or 0) + 1
        if new_failed_count >= MAX_ADMIN_LOGIN_ATTEMPTS:
            lock_until = current_time + timedelta(minutes=ADMIN_LOCK_MINUTES)
            cursor.execute(
                """
                UPDATE users
                SET failed_login_count=%s, last_failed_login=%s, account_locked=1, locked_until=%s
                WHERE id=%s
                """,
                (new_failed_count, current_time, lock_until, user_id),
            )
            conn.commit()
            messagebox.showerror(
                "Account Locked",
                f"Too many failed attempts. Account locked for {ADMIN_LOCK_MINUTES} minutes.",
            )
        else:
            cursor.execute(
                """
                UPDATE users
                SET failed_login_count=%s, last_failed_login=%s
                WHERE id=%s
                """,
                (new_failed_count, current_time, user_id),
            )
            conn.commit()
            remaining_attempts = MAX_ADMIN_LOGIN_ATTEMPTS - new_failed_count
            messagebox.showerror("Error", f"Invalid username or password. {remaining_attempts} attempt(s) left.")
        return

    if needs_password_upgrade(stored_password_hash):
        upgraded_password = hash_password(password)
        cursor.execute(
            """
            UPDATE users
            SET password=%s, failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
            WHERE id=%s
            """,
            (upgraded_password, user_id),
        )
    else:
        cursor.execute(
            """
            UPDATE users
            SET failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
            WHERE id=%s
            """,
            (user_id,),
        )
    conn.commit()

    messagebox.showinfo("Success", "Welcome, Admin!")
    login_window.destroy()  # Close the login screen
    refreshTable()          # Ensure latest data on login
    try:
        refresh_orders()    # Refresh orders list too
    except NameError:
        pass                # Ignore if refresh_orders isn't defined yet
    window.deiconify()      # Show the Main Inventory System

login_frame = ctk.CTkFrame(login_window, fg_color=PALETTE_DARK, corner_radius=0)
login_frame.pack(padx=0, pady=0, fill="both", expand=True)

login_card = ctk.CTkFrame(login_frame, fg_color=PALETTE_DARK, border_width=2, border_color=PALETTE_PRIMARY, corner_radius=18)
login_card.pack(padx=20, pady=20, fill="both", expand=True)

ctk.CTkLabel(login_card, text="Admin Log In", text_color=PALETTE_MINT, font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(26, 6))
ctk.CTkLabel(login_card, text="Please log in to continue", font=ctk.CTkFont(family="Segoe UI", size=14), text_color="#8FC9B4").pack(pady=(0, 24))

username_entry = ctk.CTkEntry(
    login_card,
    width=320,
    height=48,
    placeholder_text="Username",
    corner_radius=10,
    border_width=1,
    fg_color="#214739",
    border_color=PALETTE_PRIMARY,
    text_color=PALETTE_MINT,
    placeholder_text_color="#7FB8A3"
)
username_entry.pack(pady=(0, 16))

password_entry = ctk.CTkEntry(
    login_card,
    show="•",
    width=320,
    height=48,
    placeholder_text="Password",
    corner_radius=10,
    border_width=1,
    fg_color="#214739",
    border_color=PALETTE_PRIMARY,
    text_color=PALETTE_MINT,
    placeholder_text_color="#7FB8A3"
)
password_entry.pack(pady=(0, 28))

ctk.CTkButton(
    login_card,
    text="Login",
    fg_color=PALETTE_MINT,
    hover_color="#93D8BD",
    text_color=PALETTE_DARKEST,
    font=ctk.CTkFont(family="Segoe UI", weight="bold", size=15),
    command=check_login,
    width=320,
    height=48,
    corner_radius=10
).pack(pady=(0, 20))

login_window.bind('<Return>', check_login)
# ------------------------------

# Create Tabview instead of Notebook
notebook = ctk.CTkTabview(
    window,
    width=1160,
    height=800,
    corner_radius=15,
    fg_color=PALETTE_DARKEST,
    segmented_button_fg_color=PALETTE_DARK,
    segmented_button_unselected_color=PALETTE_DARK,
    segmented_button_unselected_hover_color=PALETTE_PRIMARY,
    segmented_button_selected_color=PALETTE_PRIMARY,
    segmented_button_selected_hover_color=PALETTE_DARK,
    text_color=PALETTE_MINT
)
notebook.pack(expand=True, fill="both", padx=10, pady=(4, 10))
try:
    notebook._segmented_button.configure(font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), height=38)
except Exception:
    pass

inventory_tab = notebook.add("Inventory Management")
orders_tab = notebook.add("Orders Management")
admin_tab = notebook.add("Admin Management")

orders_tab.configure(fg_color=PALETTE_DARKEST)
admin_tab.configure(fg_color=PALETTE_DARKEST)

style = ttk.Style()
style.theme_use('default')
style.theme_use('default')
style.configure("Treeview.Heading", font=("Segoe UI", 12, "bold"), background=PALETTE_DARK, foreground=PALETTE_MINT)
style.configure("Treeview", font=("Segoe UI", 12), rowheight=46, background="#0F231D", foreground=PALETTE_MINT, fieldbackground="#0F231D")
style.map("Treeview", background=[('selected', PALETTE_PRIMARY)], foreground=[('selected', PALETTE_TEXT)])

placeholderArray = ['', '', '', '', '']
numeric='1234567890'
alpha='ABCDEFGHIJKLMNOPQRSTUVWXYZ'

for i in range(0,5):
    placeholderArray[i] = tk.StringVar() 
    
# hide
# functions = def  functions():

conn = get_session_connection("admin-ui") or connectDB()
if not conn:
    messagebox.showerror("Database Error", "Could not connect to the database.")
    raise SystemExit(1)
cursor = conn.cursor()

# reading the data from sqlyog
def read():
    return admin_data.fetch_all_stocks(conn)
def refreshTable():
        for data in my_Tree.get_children():
            my_Tree.delete(data)
        for array in read():
            qty = int(array[3])
            formatted_price = format_price_display(array[2])
            tag = "orow"
            if qty == 0:
                tag = "out_of_stock"
            elif qty <= 5:
                tag = "low_stock"

            display_row = (array[0], array[1], formatted_price, array[3], array[4], array[5])
            my_Tree.insert(parent='', index='end', iid=array[0], values=display_row, tag=tag)
            
        my_Tree.tag_configure('orow', background="#16362B", foreground=PALETTE_MINT)
        my_Tree.tag_configure('low_stock', background=PALETTE_DARK, foreground=PALETTE_TEXT)
        my_Tree.tag_configure('out_of_stock', background="#4D2D2D", foreground=PALETTE_TEXT)
    
    
# generate unique id 
def generateID():
    itemId=''
    for i in range(0,3):
        randno=random.randrange(0,(len(numeric)-1))
        itemId=itemId+str(numeric[randno])
    rando=random.randrange(0, (len(alpha)-1))
    itemId= itemId + '-' + str(alpha[randno])
    print("Generated: " + itemId)
    setph(itemId,0) 
# uhm
def setph(word, num):
    for ph in range(0,5):
        if ph == num:
            placeholderArray[ph].set(word)

def format_price_field(event=None):
    raw_price = placeholderArray[2].get().strip()
    if not raw_price:
        return
    try:
        numeric_price = parse_price_input(raw_price)
        placeholderArray[2].set(format_price_display(numeric_price))
    except ValueError:
        # Keep user input untouched if still invalid.
        pass


def clear_product_details_fields():
    try:
        descriptionTextbox.delete("1.0", tk.END)
        imagePathVar.set("")
    except Exception:
        pass


def load_product_details(item_id):
    clear_product_details_fields()
    if not item_id:
        return

    try:
        row = admin_data.fetch_product_details(conn, item_id)
        if not row:
            return

        descriptionTextbox.insert("1.0", row[0] or "")
        imagePathVar.set(row[1] or "")
    except Exception as detail_error:
        print("Could not load product details:", detail_error)


def save_product_details(item_id):
    if not item_id:
        return

    description = descriptionTextbox.get("1.0", tk.END).strip()
    image_path = imagePathVar.get().strip()
    admin_data.save_product_details(conn, item_id, description, image_path)


def browse_product_image():
    chosen_file = filedialog.askopenfilename(
        title="Select Product Image",
        filetypes=[
            ("Image Files", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
            ("All Files", "*.*"),
        ],
    )
    if chosen_file:
        imagePathVar.set(chosen_file)

# the inputed data would be place in sqlyog/database
def add():
    itemId = str(itemIdEntry.get())  # get the item id from the entry
    name = str(nameEntry.get())  # get the name from the entry
    price = str(priceEntry.get())  # get the price from the entry
    quanti = str(quantiEntry.get())  # get the quantity from the entry
    cat = str(categoryCombo.get())  # get the category from the entry

    # Check if all fields are filled
    if not(itemId and itemId.strip()) or not(name and name.strip()) or not(price and price.strip()) or not(quanti and quanti.strip()) or not(cat and cat.strip()):
        messagebox.showwarning("", "Please fill up all entries")
        return

    # Check if itemId format is valid
    if len(itemId) < 5 or not(itemId[3] == '-') or not(itemId[:3].isdigit()) or not(itemId[4].isalpha()):
        messagebox.showwarning("", "Invalid Item Id")
        return

    try:
        price_value = parse_price_input(price)
    except ValueError:
        messagebox.showwarning("", "Invalid price. Please enter a valid number.")
        return

    try:
        quanti = int(quanti)  
    except ValueError:
        messagebox.showwarning("", "Invalid quantity. Please enter a valid positive number.")
        return
        
    if price_value < 0 or int(quanti) < 0:
        messagebox.showwarning("", "Price and Quantity cannot be negative.")
        return

    try:
        checkItemNo = admin_data.fetch_stock_by_item_id(conn, itemId)
        if len(checkItemNo) > 0:
            messagebox.showwarning("", "Item Id already used")
            return
        else:
            admin_data.insert_stock(conn, itemId, name, price_value, quanti, cat)

        save_product_details(itemId)
        conn.commit()
        for num in range(0, 5):
            setph('', (num))
        clear_product_details_fields()
    except Exception as e:
        print(e)
        messagebox.showwarning("", "Error while saving ref: " + str(e))
        return

    refreshTable()
    
def update():
    selectedItemId = ''
    try:
        selectedItem = my_Tree.selection()[0]
        selectedItemId = str(my_Tree.item(selectedItem)['values'][0])
    except:
        messagebox.showwarning("", "Please select a data row")
    print(selectedItemId)
    itemId = str(itemIdEntry.get())
    name = str(nameEntry.get())
    price = str(priceEntry.get())
    quanti = str(quantiEntry.get())
    cat = str(categoryCombo.get())
    if not(itemId and itemId.strip()) or not(name and name.strip()) or not(price and price.strip()) or not(quanti and quanti.strip()) or not(cat and cat.strip()):
        messagebox.showwarning("","Please fill up all entries")
        return
    if(selectedItemId!=itemId):
        messagebox.showwarning("","You can't change Item ID")
        return

    try:
        price_value = parse_price_input(price)
    except ValueError:
        messagebox.showwarning("", "Invalid price. Please enter a valid number.")
        return

    try:
        quanti_value = int(quanti)
    except ValueError:
        messagebox.showwarning("", "Invalid quantity. Please enter a valid positive number.")
        return

    if price_value < 0 or quanti_value < 0:
        messagebox.showwarning("", "Price and Quantity cannot be negative.")
        return

    try:
        admin_data.update_stock(conn, itemId, name, price_value, quanti_value, cat)
        save_product_details(itemId)
        conn.commit()
        for num in range(0,5):
            setph('',(num))
        clear_product_details_fields()
    except Exception as err:
        messagebox.showwarning("","Error occured ref: "+str(err))
        return
    refreshTable()
     
# delete 
def delete():
    try:
        if(my_Tree.selection()[0]):
            decision =messagebox.askquestion("Delete", "Delete the selected data?")
            if(decision != 'yes'):
                return
            else:
                selectedItem = my_Tree.selection()[0]
                # Because iid is the full tuple string representation in this old setup, we get value from Treeview:
                itemId = str(my_Tree.item(selectedItem)['values'][0])
                
                try:
                    # SAFETY CHECK: Don't delete if it is part of a pending/processing order
                    active_orders_count = admin_data.count_active_orders_for_item(conn, itemId)
                    
                    if active_orders_count > 0:
                        messagebox.showwarning("Delete Prevented", "Cannot delete this item because it is currently part of an active order (Pending, Processing, or Shipped). Please resolve the order first.")
                        return

                    admin_data.delete_stock_and_details(conn, itemId)
                    conn.commit()
                    messagebox.showinfo("","Data has been successfully deleted")
                    clear_product_details_fields()
                except Exception as e:
                    messagebox.showinfo("","Sorry, an error occured: " + str(e))
                refreshTable()
    except:
        messagebox.showwarning("", "Please select a data row")

# select function
def select():
    try:
        selectedItem = my_Tree.selection()[0]
        itemId = str(my_Tree.item(selectedItem)['values'][0])
        name = str(my_Tree.item(selectedItem)['values'][1])
        price = str(my_Tree.item(selectedItem)['values'][2])
        quanti = str(my_Tree.item(selectedItem)['values'][3])
        cat = str(my_Tree.item(selectedItem)['values'][4])
        setph(itemId,0)
        setph(name,1)
        setph(price,2) 
        setph(quanti,3)
        setph(cat,4)
        load_product_details(itemId)
    except:
        messagebox.showwarning("", "Please select a data row")

# find function
def find():
    itemId = str(itemIdEntry.get())
    name = str(nameEntry.get())
    price = str(priceEntry.get())
    normalized_price = price.replace(",", "").replace("₱", "").strip()
    quanti = str(quantiEntry.get())
    cat = str(categoryCombo.get())
    if not any([itemId.strip(), name.strip(), normalized_price, quanti.strip(), cat.strip()]):
        messagebox.showwarning("","Please fill up one of the entries")
        return

    result = admin_data.search_stocks(conn, itemId, name, normalized_price, quanti, cat)
    try:
        for num in range(0,5):
            setph(result[0][num],(num))
        load_product_details(str(result[0][0]))
    except:
        messagebox.showwarning("","No data found")

def clear():
    for num in range(0,5):
        setph('',(num))
    clear_product_details_fields()
# export as excel function
def exportExcel():
    dataraw = admin_data.fetch_stocks_for_export(conn)
    date = str(datetime.now())
    date = date.replace(' ', '_')
    date = date.replace(':', '-')
    dateFinal = date[0:16]
    with open("stocks_"+dateFinal+".csv",'a',newline='') as f:
        w = csv.writer(f, dialect='excel')
        for record in dataraw:
            w.writerow(record)
    print("saved: stocks_"+dateFinal+".csv")
    # Keep shared admin connection open for the whole UI session.
    messagebox.showinfo("","Excel file downloaded")

frame = ctk.CTkFrame(inventory_tab, fg_color=PALETTE_DARK, corner_radius=16)
frame.pack(pady=(8, 10), padx=16, fill="x")

frame.grid_columnconfigure(0, weight=1)

manageFrame = ctk.CTkFrame(frame, fg_color="transparent")
manageFrame.grid(row=0, column=0, padx=16, pady=(10, 6), sticky="ew")

entriesFrame = ctk.CTkFrame(frame, fg_color="transparent")
entriesFrame.grid(row=1, column=0, padx=16, pady=(6, 10), sticky="ew")
entriesFrame.grid_columnconfigure(1, weight=1)
entriesFrame.grid_columnconfigure(3, weight=1)

detailsFrame = ctk.CTkFrame(frame, fg_color="transparent")
detailsFrame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
detailsFrame.grid_columnconfigure(1, weight=1)
detailsFrame.grid_columnconfigure(3, weight=1)

btnColor = PALETTE_PRIMARY

for column_index in range(7):
    manageFrame.grid_columnconfigure(column_index, weight=1)

saveBtn = ctk.CTkButton(manageFrame, text="Save", height=38, fg_color=btnColor, text_color=PALETTE_TEXT, command=add, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
updateBtn = ctk.CTkButton(manageFrame, text="Update", height=38, fg_color=btnColor, text_color=PALETTE_TEXT, command=update, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
deleteBtn = ctk.CTkButton(manageFrame, text="Delete", height=38, fg_color=btnColor, text_color=PALETTE_TEXT, command=delete, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
selectBtn = ctk.CTkButton(manageFrame, text="Select", height=38, fg_color=btnColor, text_color=PALETTE_TEXT, command=select, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
findBtn = ctk.CTkButton(manageFrame, text="Find", height=38, fg_color=btnColor, text_color=PALETTE_TEXT, command=find, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
clearBtn = ctk.CTkButton(manageFrame, text="Clear", height=38, fg_color=PALETTE_DARKEST, hover_color=PALETTE_DARK, text_color=PALETTE_TEXT, command=clear, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
exportBtn = ctk.CTkButton(manageFrame, text="Export CSV / Excel", height=38, fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, command=exportExcel, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)

saveBtn.grid(row=0, column=0, padx=(0, 6), pady=4, sticky="ew")
updateBtn.grid(row=0, column=1, padx=6, pady=4, sticky="ew")
deleteBtn.grid(row=0, column=2, padx=6, pady=4, sticky="ew")
selectBtn.grid(row=0, column=3, padx=6, pady=4, sticky="ew")
findBtn.grid(row=0, column=4, padx=6, pady=4, sticky="ew")
clearBtn.grid(row=0, column=5, padx=6, pady=4, sticky="ew")
exportBtn.grid(row=0, column=6, padx=(6, 0), pady=4, sticky="ew")

itemIdLabel = ctk.CTkLabel(entriesFrame, text="Item ID", anchor="e", width=100, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
nameLabel = ctk.CTkLabel(entriesFrame, text="Name", anchor="e", width=100, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
priceLabel = ctk.CTkLabel(entriesFrame, text="Price", anchor="e", width=100, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
quantiLabel = ctk.CTkLabel(entriesFrame, text="Quantity", anchor="e", width=100, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
categoryLabel = ctk.CTkLabel(entriesFrame, text="Category", anchor="e", width=100, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))

itemIdLabel.grid(row=0, column=0, padx=(0, 10), pady=8, sticky="e")
priceLabel.grid(row=0, column=2, padx=(10, 10), pady=8, sticky="e")
nameLabel.grid(row=1, column=0, padx=(0, 10), pady=8, sticky="e")
quantiLabel.grid(row=1, column=2, padx=(10, 10), pady=8, sticky="e")
categoryLabel.grid(row=2, column=0, padx=(0, 10), pady=8, sticky="e")

categoryArray = ["Mainstream Laptops", "Premium Laptops", "Gaming Laptops", "Peripherals"]

itemIdEntry = ctk.CTkEntry(entriesFrame, textvariable=placeholderArray[0], height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
nameEntry = ctk.CTkEntry(entriesFrame, textvariable=placeholderArray[1], height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
priceEntry = ctk.CTkEntry(entriesFrame, textvariable=placeholderArray[2], height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
quantiEntry = ctk.CTkEntry(entriesFrame, textvariable=placeholderArray[3], height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
categoryCombo = ctk.CTkComboBox(entriesFrame, variable=placeholderArray[4], values=categoryArray, height=40, corner_radius=8, state="readonly", fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, button_color=PALETTE_PRIMARY, button_hover_color=PALETTE_DARK, text_color=PALETTE_TEXT)

itemIdEntry.grid(row=0, column=1, padx=(0, 16), pady=8, sticky="ew")
priceEntry.grid(row=0, column=3, padx=(0, 0), pady=8, sticky="ew")
nameEntry.grid(row=1, column=1, padx=(0, 16), pady=8, sticky="ew")
quantiEntry.grid(row=1, column=3, padx=(0, 0), pady=8, sticky="ew")
categoryCombo.grid(row=2, column=1, padx=(0, 16), pady=8, sticky="ew")

priceEntry.bind("<FocusOut>", format_price_field)

# Item ID is generated by the system, so keep it read-only in the UI.
itemIdEntry.configure(state="disabled")

generateidBtn = ctk.CTkButton(entriesFrame, text="Generate ID", width=180, height=40, fg_color=btnColor, text_color=PALETTE_TEXT, command=generateID, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), corner_radius=10)
generateidBtn.grid(row=2, column=3, padx=(0, 0), pady=8, sticky="e")

ctk.CTkLabel(detailsFrame, text="Product Details (Buyer View)", text_color=PALETTE_MINT, font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

ctk.CTkLabel(detailsFrame, text="Description", anchor="e", width=110, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(row=1, column=0, padx=(0, 10), pady=6, sticky="ne")
descriptionTextbox = ctk.CTkTextbox(detailsFrame, height=70, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, border_width=1, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=12), corner_radius=8)
descriptionTextbox.grid(row=1, column=1, columnspan=3, padx=(0, 0), pady=6, sticky="ew")

imagePathVar = tk.StringVar()
ctk.CTkLabel(detailsFrame, text="Image Path", anchor="e", width=110, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(row=2, column=0, padx=(0, 10), pady=6, sticky="e")
imagePathEntry = ctk.CTkEntry(detailsFrame, textvariable=imagePathVar, height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, font=ctk.CTkFont(family="Segoe UI", size=12), corner_radius=8)
imagePathEntry.grid(row=2, column=1, columnspan=2, padx=(0, 8), pady=6, sticky="ew")
ctk.CTkButton(detailsFrame, text="Browse", width=120, height=40, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARK, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=12, weight="bold"), command=browse_product_image, corner_radius=8).grid(row=2, column=3, padx=(0, 0), pady=6, sticky="e")

inventoryTableFrame = ctk.CTkFrame(inventory_tab, fg_color="transparent")
inventoryTableFrame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

my_Tree = ttk.Treeview(inventoryTableFrame, show='headings', height=12)

my_Tree["columns"] = ("Product ID", "Name", "Price", "Quantity", "Category", "Date")
my_Tree.column("#0", width=0, stretch=False)
my_Tree.column("Product ID", anchor="w", width=110)
my_Tree.column("Name", anchor="w", width=230)
my_Tree.column("Price", anchor="w", width=100)
my_Tree.column("Quantity", anchor="center", width=90)
my_Tree.column("Category", anchor="w", width=170)
my_Tree.column("Date", anchor="w", width=160)
my_Tree.heading("Product ID", text="Product ID", anchor="w")
my_Tree.heading("Name", text="Name", anchor="w")
my_Tree.heading("Price", text="Price", anchor="w")
my_Tree.heading("Quantity", text="Quantity", anchor="center")
my_Tree.heading("Category", text="Category", anchor="w")
my_Tree.heading("Date", text="Date", anchor="w")
my_Tree.tag_configure("orow", background="#16362B", foreground=PALETTE_MINT)

inventoryTreeScrollbar = ctk.CTkScrollbar(
    inventoryTableFrame,
    orientation="vertical",
    command=my_Tree.yview,
    fg_color=PALETTE_DARKEST,
    button_color=PALETTE_PRIMARY,
    button_hover_color=PALETTE_MINT,
)
my_Tree.configure(yscrollcommand=inventoryTreeScrollbar.set)

my_Tree.pack(side="left", fill="both", expand=True)
inventoryTreeScrollbar.pack(side="right", fill="y", padx=(6, 0))

refreshTable()

# --- Orders Management Tab Structure ---
orders_top_frame = ctk.CTkFrame(orders_tab, fg_color="transparent", corner_radius=0)
orders_top_frame.pack(fill="x", pady=(12, 4), padx=22)

orders_tree = ttk.Treeview(orders_tab, show='headings', height=12)
orders_tree['columns'] = ("Order ID", "Customer Name", "Total Amount", "Date", "Status")
orders_tree.column("#0", width=0, stretch=False)
orders_tree.column("Order ID", anchor='w', width=100)
orders_tree.column("Customer Name", anchor='w', width=150)
orders_tree.column("Total Amount", anchor='w', width=100)
orders_tree.column("Date", anchor='w', width=150)
orders_tree.column("Status", anchor='w', width=100)

orders_tree.heading("Order ID", text="Order ID", anchor='w')
orders_tree.heading("Customer Name", text="Customer Name", anchor='w')
orders_tree.heading("Total Amount", text="Total Amount", anchor='w')
orders_tree.heading("Date", text="Date", anchor='w')
orders_tree.heading("Status", text="Status", anchor='w')

orders_tree.tag_configure('orow', background="#16362B", foreground=PALETTE_MINT)
orders_tree.pack(fill="both", expand=True, padx=22, pady=(6, 16))

def refresh_orders():
    order_search_entry.delete(0, 'end')
    order_status_combo.set("All")
    filter_orders()

def logout():
    decision =messagebox.askquestion("Logout", "Are you sure you want to logout?")
    if decision == 'yes':
        window.withdraw() # Hide main app
        login_window.deiconify() # Reshow login screen
        username_entry.delete(0, 'end')
        password_entry.delete(0, 'end')
        username_entry.focus()

def filter_orders():
    term = order_search_entry.get().strip()
    status = order_status_combo.get()
    
    for data in orders_tree.get_children():
        orders_tree.delete(data)
        
    try:
        results = admin_data.fetch_filtered_orders(conn, term, status)
        for array in results:
            display_values = (array[0], array[1], format_price_display(array[2]), array[3], array[4])
            orders_tree.insert(parent='', index='end', iid=array[0], values=display_values, tag="orow")
    except Exception as e:
        print("Could not load filtered orders:", e)

def update_order_status():
    try:
        selected_item = orders_tree.selection()[0]
        order_id = str(orders_tree.item(selected_item)['values'][0])
        current_status = str(orders_tree.item(selected_item)['values'][4])

        if current_status in ['Completed', 'Cancelled']:
            messagebox.showwarning("Error", f"Order is already {current_status} and cannot be changed.")
            return

        status_win = ctk.CTkToplevel(window)
        status_win.title("Update Status")
        center_window(status_win, 340, 220)
        status_win.configure(fg_color=PALETTE_DARK)

        ctk.CTkLabel(status_win, text=f"Update Order #{order_id}", text_color=PALETTE_MINT, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 8))
        ctk.CTkLabel(status_win, text="Select Status", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=13)).pack(pady=(0, 6))

        status_var = tk.StringVar(value=(current_status if current_status != 'Pending' else 'Processing'))
        status_combo = ttk.Combobox(status_win, textvariable=status_var, values=["Processing", "Shipped", "Completed", "Cancelled"], state="readonly", width=22)
        status_combo.pack(pady=8)

        def save_status():
            new_status = status_var.get().strip()
            if not new_status:
                messagebox.showwarning("Error", "Select a status.", parent=status_win)
                return

            try:
                if new_status == 'Cancelled':
                    restock_items = admin_data.fetch_order_items_for_restock(conn, order_id)
                    admin_data.restock_items(conn, restock_items)

                admin_data.update_order_status(conn, order_id, new_status)
                conn.commit()

                refresh_orders()
                if new_status == 'Cancelled':
                    refreshTable()

                messagebox.showinfo("Success", f"Order #{order_id} marked as {new_status}.", parent=status_win)
                status_win.destroy()
            except Exception as err:
                messagebox.showerror("Error", f"Could not update status: {err}", parent=status_win)

        ctk.CTkButton(status_win, text="Save Status", width=160, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, corner_radius=8, text_color=PALETTE_TEXT, font=ctk.CTkFont(weight="bold"), command=save_status).pack(pady=14)

    except Exception:
        messagebox.showwarning("Error", "Please select an order from the list first.")

def view_order_details():
    try:
        selected_item = orders_tree.selection()[0]
        order_id = str(orders_tree.item(selected_item)['values'][0])
        customer_name = str(orders_tree.item(selected_item)['values'][1])

        # Fetch extra order details
        order_info = admin_data.fetch_order_header(conn, order_id)
        if not order_info:
            messagebox.showerror("Error", "Could not fetch order details.")
            return
            
        c_name, c_contact, c_address, vat, grand_total, pay_method, o_date, status = order_info
        
        # Create a popup to show the items for this order
        details_window = ctk.CTkToplevel(window)
        details_window.title(f"Order Details - #{order_id}")
        details_window.geometry("600x500")
        details_window.configure(fg_color="#f4f4f4")
        
        # Top Frame: Customer & Shipping Info
        info_frame = ctk.CTkFrame(details_window,  fg_color="#f4f4f4", corner_radius=15)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(info_frame, text=f"Name: {c_name}", fg_color="#f4f4f4").grid(row=0, column=0, sticky="w", padx=10, pady=2)
        ctk.CTkLabel(info_frame, text=f"Contact: {c_contact or 'N/A'}", fg_color="#f4f4f4").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        ctk.CTkLabel(info_frame, text=f"Payment: {pay_method or 'N/A'}", fg_color="#f4f4f4").grid(row=0, column=1, sticky="w", padx=10, pady=2)
        ctk.CTkLabel(info_frame, text=f"Date: {o_date}", fg_color="#f4f4f4").grid(row=1, column=1, sticky="w", padx=10, pady=2)
        ctk.CTkLabel(info_frame, text=f"Address: {c_address or 'N/A'}", fg_color="#f4f4f4", wraplength=400, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        # Middle Frame: Items Ordered
        items_frame = ctk.CTkFrame(details_window,  fg_color="#f4f4f4", corner_radius=15)
        items_frame.pack(fill="both", expand=True, padx=10)
        
        # Create Treeview for items
        items_tree = ttk.Treeview(items_frame, show='headings', height=8)
        items_tree['columns'] = ("Item ID", "Name", "Quantity", "Price", "Subtotal")
        items_tree.column("Item ID", anchor='w', width=80)
        items_tree.column("Name", anchor='w', width=180)
        items_tree.column("Quantity", anchor='w', width=60)
        items_tree.column("Price", anchor='w', width=80)
        items_tree.column("Subtotal", anchor='w', width=100)

        items_tree.heading("Item ID",  anchor='w')
        items_tree.heading("Name",  anchor='w')
        items_tree.heading("Quantity",  anchor='w')
        items_tree.heading("Price",  anchor='w')
        items_tree.heading("Subtotal",  anchor='w')

        items_tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Fetch the items from the database
        results = admin_data.fetch_order_detail_items(conn, order_id)
        for row in results:
            formatted_row = (
                row[0],
                row[1],
                row[2],
                format_price_display(row[3]),
                format_price_display(row[4])
            )
            items_tree.insert("", "end", values=formatted_row)
        
        # Bottom Frame: Payment Summary
        summary_frame = ctk.CTkFrame(details_window, fg_color="#e8e8e8", relief="groove", corner_radius=15)
        summary_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        
        ctk.CTkLabel(summary_frame, text=f"Status: {status}", font=("Arial", 10, "bold"), fg_color="#e8e8e8").pack(side="left", padx=10, pady=10)
        
        totals_container = ctk.CTkFrame(summary_frame, fg_color="#e8e8e8", corner_radius=15)
        totals_container.pack(side="right", padx=10)
        
        ctk.CTkLabel(totals_container, text=f"VAT (12%): ₱ {float(vat or 0):,.2f}", fg_color="#e8e8e8").grid(row=0, column=0, sticky="e", pady=2)
        ctk.CTkLabel(totals_container, text=f"GRAND TOTAL: ₱ {float(grand_total or 0):,.2f}", font=("Arial", 12, "bold"), text_color="red", fg_color="#e8e8e8").grid(row=1, column=0, sticky="e", pady=2)

        # Print/View Receipt Button
        def view_txt_receipt():
            filename = f"receipt_ORD{order_id}.txt"
            if not os.path.exists(filename):
                messagebox.showwarning("Not Found", f"Receipt {filename} is missing.")
                return
            
            receipt_win = ctk.CTkToplevel(details_window)
            receipt_win.title(f"Receipt Printout - #{order_id}")
            receipt_win.geometry("400x500")

            txt = ctk.CTkTextbox(receipt_win, width=360, height=420)
            txt.pack(fill="both", expand=True, padx=20, pady=20)
            
            with open(filename, "r") as file:
                txt.insert("1.0", file.read())
                txt.configure(state="disabled")

        ctk.CTkButton(summary_frame, text="View Receipt", fg_color="#53d769", text_color='white', command=view_txt_receipt, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), corner_radius=10).pack(side="right", padx=20, pady=10)

    except Exception as e:
        messagebox.showwarning("Error", f"Could not view details: {e}")

# Order Filter Row
order_filter_frame = ctk.CTkFrame(orders_top_frame, fg_color=PALETTE_DARK, corner_radius=12)
order_filter_frame.pack(fill="x")

ctk.CTkLabel(order_filter_frame, text="Search Order ID:", fg_color="transparent", text_color=PALETTE_TEXT).pack(side="left", padx=(14, 6), pady=8)
order_search_entry = ctk.CTkEntry(order_filter_frame, width=220, height=38, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT)
order_search_entry.pack(side="left", padx=6, pady=8)

order_status_combo = ctk.CTkComboBox(
    order_filter_frame,
    values=["All", "Pending", "Processing", "Shipped", "Completed", "Cancelled"],
    width=170,
    height=38,
    corner_radius=8,
    state="readonly",
    fg_color=PALETTE_DARK,
    border_color=PALETTE_PRIMARY,
    button_color=PALETTE_PRIMARY,
    button_hover_color=PALETTE_DARKEST,
    text_color=PALETTE_TEXT
)
order_status_combo.set("All")
order_status_combo.pack(side="left", padx=6, pady=8)

ctk.CTkButton(order_filter_frame, text="Filter", width=100, height=36, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, command=filter_orders).pack(side="left", padx=6, pady=8)
ctk.CTkButton(order_filter_frame, text="Refresh", width=100, height=36, fg_color=PALETTE_DARK, hover_color=PALETTE_PRIMARY, text_color=PALETTE_TEXT, command=refresh_orders).pack(side="left", padx=6, pady=8)
ctk.CTkButton(order_filter_frame, text="Update Status", width=130, height=36, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, command=update_order_status).pack(side="right", padx=(6, 10), pady=8)
ctk.CTkButton(order_filter_frame, text="View Details", width=120, height=36, fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, command=view_order_details).pack(side="right", padx=6, pady=8)

refresh_orders()

def update_admin_password():
    username = admin_user_entry.get().strip()
    old_pw = admin_old_pw_entry.get().strip()
    new_pw = admin_new_pw_entry.get().strip()

    if not username or not old_pw or not new_pw:
        messagebox.showwarning("Error", "Please fill in all fields.")
        return

    password_ok, password_message = validate_password_strength(new_pw)
    if not password_ok:
        messagebox.showwarning("Weak Password", password_message)
        return

    try:
        existing_user = admin_data.fetch_admin_user(conn, username)
        if existing_user and verify_password(old_pw, existing_user[1]):
            new_hash = hash_password(new_pw)
            admin_data.update_user_password(conn, existing_user[0], new_hash)
            conn.commit()
            messagebox.showinfo("Success", f"Password updated for {username}.") 
            admin_user_entry.delete(0, 'end')
            admin_old_pw_entry.delete(0, 'end')
            admin_new_pw_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", "Invalid username or old password.")  
    except Exception as e:
        messagebox.showwarning("Error", str(e))

admin_panel = ctk.CTkFrame(admin_tab, fg_color="transparent")
admin_panel.pack(fill="both", expand=True, padx=24, pady=(10, 16))
admin_panel.grid_columnconfigure(0, weight=1)
admin_panel.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(
    admin_panel,
    text="Admin Security Center",
    text_color=PALETTE_MINT,
    font=ctk.CTkFont(size=22, weight="bold")
).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 2))

ctk.CTkLabel(
    admin_panel,
    text="Manage admin credentials and create sub-admin accounts.",
    text_color="#8FC9B4",
    font=ctk.CTkFont(size=13)
).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 14))

update_frame = ctk.CTkFrame(
    admin_panel,
    fg_color=PALETTE_DARK,
    corner_radius=16,
    border_width=1,
    border_color=PALETTE_PRIMARY
)
update_frame.grid(row=2, column=0, sticky="nsew", padx=(8, 10), pady=(0, 8), ipadx=14, ipady=12)
update_frame.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(update_frame, text="Update Admin Password", text_color=PALETTE_MINT, font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(6, 4), sticky="w")
ctk.CTkLabel(update_frame, text="Change credentials for an existing admin.", text_color="#9FD7C3", font=ctk.CTkFont(size=12)).grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 12), sticky="w")

ctk.CTkLabel(update_frame, text="Username:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, padx=(10, 8), pady=8, sticky="e")
admin_user_entry = ctk.CTkEntry(update_frame, width=260, corner_radius=8, height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13))
admin_user_entry.grid(row=2, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkLabel(update_frame, text="Old Password:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, padx=(10, 8), pady=8, sticky="e")
admin_old_pw_entry = ctk.CTkEntry(update_frame, width=260, show="*", corner_radius=8, height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13))
admin_old_pw_entry.grid(row=3, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkLabel(update_frame, text="New Password:", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, padx=(10, 8), pady=8, sticky="e")
admin_new_pw_entry = ctk.CTkEntry(update_frame, width=260, show="*", corner_radius=8, height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13))
admin_new_pw_entry.grid(row=4, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkButton(update_frame, text="Update Password", width=180, height=40, fg_color=PALETTE_PRIMARY, hover_color=PALETTE_DARKEST, text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold"), corner_radius=8, command=update_admin_password).grid(row=5, column=0, columnspan=2, padx=10, pady=(14, 6), sticky="w")

# Create Subordinate Admin Section
create_frame = ctk.CTkFrame(
    admin_panel,
    fg_color=PALETTE_DARK,
    corner_radius=16,
    border_width=1,
    border_color=PALETTE_PRIMARY
)
create_frame.grid(row=2, column=1, sticky="nsew", padx=(10, 8), pady=(0, 8), ipadx=14, ipady=12)
create_frame.grid_columnconfigure(1, weight=1)

def create_sub_admin():
    new_user = sub_user_entry.get().strip()
    new_pw = sub_pw_entry.get().strip()
    conf_pw = sub_conf_pw_entry.get().strip()
    
    if not new_user or not new_pw or not conf_pw:
        messagebox.showwarning("Error", "Please fill in all fields.")
        return
        
    if new_pw != conf_pw:
        messagebox.showwarning("Error", "Passwords do not match.")
        return

    password_ok, password_message = validate_password_strength(new_pw)
    if not password_ok:
        messagebox.showwarning("Weak Password", password_message)
        return
        
    new_hash = hash_password(new_pw)
    
    try:
        if admin_data.admin_exists(conn, new_user):
            messagebox.showwarning("Error", "Username already exists.")
        else:
            admin_data.insert_admin_user(conn, new_user, new_hash, 'admin')
            conn.commit()
            messagebox.showinfo("Success", f"Subordinate Admin '{new_user}' created successfully.")

            sub_user_entry.delete(0, 'end')
            sub_pw_entry.delete(0, 'end')
            sub_conf_pw_entry.delete(0, 'end')
    except Exception as e:
        messagebox.showwarning("Error", str(e))

ctk.CTkLabel(create_frame, text="Create Sub-Admin", text_color=PALETTE_MINT, font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(6, 4), sticky="w")
ctk.CTkLabel(create_frame, text="Add a new admin account for delegated tasks.", text_color="#9FD7C3", font=ctk.CTkFont(size=12)).grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 12), sticky="w")

ctk.CTkLabel(create_frame, text="Username:", fg_color="transparent", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, padx=(10, 8), pady=8, sticky="e")
sub_user_entry = ctk.CTkEntry(create_frame, width=220, height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
sub_user_entry.grid(row=2, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkLabel(create_frame, text="Password:", fg_color="transparent", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, padx=(10, 8), pady=8, sticky="e")
sub_pw_entry = ctk.CTkEntry(create_frame, width=220, show="*", height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
sub_pw_entry.grid(row=3, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkLabel(create_frame, text="Confirm Password:", fg_color="transparent", text_color=PALETTE_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, padx=(10, 8), pady=8, sticky="e")
sub_conf_pw_entry = ctk.CTkEntry(create_frame, width=220, show="*", height=40, fg_color=PALETTE_DARKEST, border_color=PALETTE_PRIMARY, text_color=PALETTE_MINT, font=ctk.CTkFont(family="Segoe UI", size=13), corner_radius=8)
sub_conf_pw_entry.grid(row=4, column=1, padx=(8, 10), pady=8, sticky="ew")

ctk.CTkButton(create_frame, text="Create Sub-Admin", width=180, height=40, fg_color=PALETTE_MINT, hover_color=PALETTE_PRIMARY, text_color=PALETTE_DARKEST, font=ctk.CTkFont(size=13, weight="bold"), command=create_sub_admin).grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(14, 6))

# ---------------------------------------

# false mean di resizable or na mamaximize yung window
def on_admin_app_close():
    close_session_connection("admin-ui")
    try:
        conn.close()
    except Exception:
        pass
    window.destroy()

window.protocol("WM_DELETE_WINDOW", on_admin_app_close)
window.resizable(True, True)
print(f"[startup] Admin UI ready: {time.perf_counter() - APP_START_TS:.3f}s")
window.mainloop() 
 
