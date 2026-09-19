import streamlit as st
import pandas as pd
import datetime
# ---------------- SQLITE BACKEND (embedded) ----------------
import sqlite3
import json
from pathlib import Path
import smtplib
from email.message import EmailMessage

DB_PATH = Path(__file__).with_name("shopzone.db")

# ---------------- EMAIL NOTIFICATIONS ----------------
ADMIN_EMAIL = "gokulmk932@gmail.com"

def send_admin_email(subject, body):
    """Send ShopZone notifications to the owner using Gmail SMTP.
    Credentials must be stored in Streamlit Secrets, never in source code.
    """
    try:
        gmail_user = st.secrets.get("GMAIL_USER", "")
        gmail_app_password = st.secrets.get("GMAIL_APP_PASSWORD", "")
        if not gmail_user or not gmail_app_password:
            return False, (
                "Gmail Secrets missing. Add GMAIL_USER and "
                "GMAIL_APP_PASSWORD in Streamlit Secrets."
            )

        msg = EmailMessage()
        msg["From"] = gmail_user
        msg["To"] = ADMIN_EMAIL
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(gmail_user, gmail_app_password)
            server.send_message(msg)
        return True, "Email sent"
    except Exception as exc:
        return False, str(exc)


def gmail_setup_status():
    """Return notification setup status without exposing the secret."""
    try:
        gmail_user = st.secrets.get("GMAIL_USER", "")
        gmail_app_password = st.secrets.get("GMAIL_APP_PASSWORD", "")
        if gmail_user and gmail_app_password:
            return True, f"Gmail notification is configured for {ADMIN_EMAIL}."
        return False, "Gmail notification is not configured yet."
    except Exception:
        return False, "Gmail notification is not configured yet."


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            image TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            UNIQUE(username, product_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            image TEXT,
            UNIQUE(username, product_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            username TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            order_date TEXT NOT NULL,
            items_json TEXT NOT NULL,
            subtotal REAL NOT NULL,
            delivery REAL NOT NULL,
            total REAL NOT NULL,
            payment TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def seed_demo_users():
    conn = get_connection()
    cur = conn.cursor()
    users = [
        ("admin", "admin123"),
        ("gokul", "1234"),
    ]
    for username, password in users:
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, created_at) VALUES (?, ?, datetime('now'))",
            (username, password),
        )
    conn.commit()
    conn.close()


def register_user(username, password):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, datetime('now'))",
            (username.strip(), password),
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"Database error: {e}"


def login_user(username, password):
    conn = get_connection()
    row = conn.execute(
        "SELECT username FROM users WHERE username = ? AND password = ?",
        (username.strip(), password),
    ).fetchone()
    conn.close()
    return row is not None


def product_dict(product):
    return {
        "id": str(product["id"]),
        "Product": str(product["Product"]),
        "Category": str(product.get("Category", "")),
        "Price": float(product["Price"]),
        "Image": str(product.get("Image", "")),
    }


def load_cart(username):
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_id, product, category, price, image, quantity FROM cart WHERE username = ? ORDER BY id",
        (username,),
    ).fetchall()
    conn.close()

    items = []
    for row in rows:
        base = {
            "id": row["product_id"],
            "Product": row["product"],
            "Category": row["category"],
            "Price": row["price"],
            "Image": row["image"],
        }
        for _ in range(max(1, row["quantity"])):
            items.append(base.copy())
    return items


def add_to_cart(username, product, quantity=1):
    p = product_dict(product)
    conn = get_connection()
    existing = conn.execute(
        "SELECT quantity FROM cart WHERE username = ? AND product_id = ?",
        (username, p["id"]),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE cart SET quantity = quantity + ? WHERE username = ? AND product_id = ?",
            (int(quantity), username, p["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO cart
               (username, product_id, product, category, price, image, quantity)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, p["id"], p["Product"], p["Category"], p["Price"], p["Image"], int(quantity)),
        )
    conn.commit()
    conn.close()


def set_cart(username, items):
    clear_cart(username)
    for item in items:
        add_to_cart(username, item, 1)


def remove_cart_item(username, product_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM cart WHERE username = ? AND product_id = ?",
        (username, str(product_id)),
    )
    conn.commit()
    conn.close()


def update_cart_quantity(username, product_id, quantity):
    quantity = int(quantity)
    conn = get_connection()
    if quantity <= 0:
        conn.execute(
            "DELETE FROM cart WHERE username = ? AND product_id = ?",
            (username, str(product_id)),
        )
    else:
        conn.execute(
            "UPDATE cart SET quantity = ? WHERE username = ? AND product_id = ?",
            (quantity, username, str(product_id)),
        )
    conn.commit()
    conn.close()


def clear_cart(username):
    conn = get_connection()
    conn.execute("DELETE FROM cart WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def load_wishlist(username):
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_id, product, category, price, image FROM wishlist WHERE username = ? ORDER BY id",
        (username,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["product_id"],
            "Product": row["product"],
            "Category": row["category"],
            "Price": row["price"],
            "Image": row["image"],
        }
        for row in rows
    ]


def add_to_wishlist(username, product):
    p = product_dict(product)
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO wishlist
           (username, product_id, product, category, price, image)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (username, p["id"], p["Product"], p["Category"], p["Price"], p["Image"]),
    )
    conn.commit()
    conn.close()


def remove_wishlist(username, product_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM wishlist WHERE username = ? AND product_id = ?",
        (username, str(product_id)),
    )
    conn.commit()
    conn.close()


def get_saved_address(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT name, phone, address, city, pincode FROM addresses WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "name": row["name"],
        "phone": row["phone"],
        "address": row["address"],
        "city": row["city"],
        "pincode": row["pincode"],
    }


def save_address(username, name, phone, address, city, pincode):
    conn = get_connection()
    conn.execute(
        """INSERT INTO addresses (username, name, phone, address, city, pincode, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(username) DO UPDATE SET
             name=excluded.name, phone=excluded.phone, address=excluded.address,
             city=excluded.city, pincode=excluded.pincode, updated_at=datetime('now')""",
        (username, name.strip(), phone.strip(), address.strip(), city.strip(), pincode.strip()),
    )
    conn.commit()
    conn.close()


def save_order(order):
    conn = get_connection()
    conn.execute(
        """INSERT INTO orders
           (order_id, username, order_date, items_json, subtotal, delivery, total,
            payment, name, phone, address, city, pincode, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            order["order_id"],
            order["username"],
            order["date"],
            json.dumps(order["items"], ensure_ascii=False),
            float(order["subtotal"]),
            float(order["delivery"]),
            float(order["total"]),
            order["payment"],
            order["name"],
            order["phone"],
            order["address"],
            order["city"],
            order["pincode"],
            order["status"],
        ),
    )
    conn.commit()
    conn.close()


def cancel_order(username, order_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status = ? WHERE username = ? AND order_id = ? AND status NOT IN ('Cancelled', 'Delivered')",
        ("Cancelled", username, str(order_id)),
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def load_orders(username):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM orders WHERE username = ? ORDER BY id DESC",
        (username,),
    ).fetchall()
    conn.close()

    orders = []
    for row in rows:
        orders.append({
            "order_id": row["order_id"],
            "username": row["username"],
            "date": row["order_date"],
            "items": json.loads(row["items_json"]),
            "subtotal": row["subtotal"],
            "delivery": row["delivery"],
            "total": row["total"],
            "payment": row["payment"],
            "name": row["name"],
            "phone": row["phone"],
            "address": row["address"],
            "city": row["city"],
            "pincode": row["pincode"],
            "status": row["status"],
        })
    return orders



create_tables()
seed_demo_users()

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="ShopZone",
    page_icon="🛍️",
    layout="wide"
)

# ---------------- SESSION STATE ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "cart" not in st.session_state:
    st.session_state.cart = []

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

if "orders" not in st.session_state:
    st.session_state.orders = []

if "checkout" not in st.session_state:
    st.session_state.checkout = False

if "order_success" not in st.session_state:
    st.session_state.order_success = None

if "saved_address" not in st.session_state:
    st.session_state.saved_address = None

if "selected_product" not in st.session_state:
    st.session_state.selected_product = None

if "quantity" not in st.session_state:
    st.session_state.quantity = 1

if "page" not in st.session_state:
    st.session_state.page = "🏠 Home"

if "product_search_from_home" not in st.session_state:
    st.session_state.product_search_from_home = ""

if "home_category" not in st.session_state:
    st.session_state.home_category = ""

# ShopZone opening splash - S logo only
if "splash_done" not in st.session_state:
    st.session_state.splash_done = False

# Process redirect before showing splash again.
if st.query_params.get("splash") == "done":
    st.session_state.splash_done = True
    st.query_params.clear()

if not st.session_state.splash_done and st.session_state.get("logged_in", False) is False:
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
        background:#ffe500 !important;
    }
    .sz-splash {
        min-height:92vh;
        display:flex;
        align-items:center;
        justify-content:center;
        background:#ffe500;
    }
    .sz-s-logo {
        width:132px;
        height:132px;
        border-radius:34px;
        background:#2874f0;
        color:#ffe500;
        display:flex;
        align-items:center;
        justify-content:center;
        font-family:Arial,sans-serif;
        font-size:92px;
        font-weight:900;
        font-style:italic;
        line-height:1;
        box-shadow:0 14px 35px rgba(0,0,0,.18);
        animation:sz-pop .45s ease-out;
    }
    @keyframes sz-pop {
        from { transform:scale(.72); opacity:.2; }
        to { transform:scale(1); opacity:1; }
    }
    </style>
    <div class="sz-splash"><div class="sz-s-logo">S</div></div>
    <meta http-equiv="refresh" content="1.2;url=?splash=done">
    """, unsafe_allow_html=True)
    st.stop()

# =========================================================
# LOGIN / REGISTER PAGE
# =========================================================

if not st.session_state.logged_in:

    st.markdown(
        """
        <style>
        .main {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }

        .login-title {
    text-align: center;
    font-size: 42px;
    font-weight: bold;
    color: #1f2937;
    margin-top: 50px;
}

.login-subtitle {
    text-align: center;
    font-size: 18px;
    color: #6b7280;
    margin-bottom: 30px;
}
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="login-title">🛒 ShopZone</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="login-subtitle">Your Smart Online Shopping Store</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:

        tab1, tab2 = st.tabs(
            ["🔐 Login", "📝 Create Account"]
        )

        # ---------------- LOGIN ----------------
        with tab1:

            st.markdown("### Welcome Back 👋")

            username = st.text_input(
                "Username",
                key="login_username"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button(
                "🚀 Login",
                use_container_width=True
            ):

                if login_user(username, password):

                    st.session_state.logged_in = True
                    st.session_state.username = username

                    st.success("Login successful!")
                    st.rerun()

                else:
                    st.error("❌ Invalid username or password")

            st.info("Demo Login: gokul / 1234")

        # ---------------- REGISTER ----------------
        with tab2:

            st.markdown("### Create Your Account ✨")

            new_username = st.text_input(
                "Create Username",
                key="register_username"
            )

            new_password = st.text_input(
                "Create Password",
                type="password",
                key="register_password"
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                key="confirm_password"
            )

            if st.button(
                "✨ Create Account",
                use_container_width=True
            ):

                if not new_username or not new_password:
                    st.warning("Please fill all fields.")

                elif new_password != confirm_password:
                    st.error("❌ Passwords do not match.")

                

                else:
                    created, message = register_user(new_username, new_password)
                    if created:
                        st.success("✅ Account created successfully!")
                        st.info("Now go to Login and sign in.")
                    else:
                        st.error(f"❌ {message}")


# =========================================================
# MAIN WEBSITE AFTER LOGIN
# =========================================================

else:

    # ---------------- LOAD USER DATA FROM DATABASE ----------------
    # SQLite is the permanent backend. Session state only holds the current screen.
    st.session_state.cart = load_cart(st.session_state.username)
    st.session_state.wishlist = load_wishlist(st.session_state.username)
    st.session_state.orders = load_orders(st.session_state.username)
    st.session_state.saved_address = get_saved_address(st.session_state.username)

    # ---------------- SHOPPING UI STYLE ----------------
    st.markdown(
        """
        <style>
        .block-container { padding-top: .6rem; padding-left: 1.2rem; padding-right: 1.2rem; max-width: 1500px; }
        [data-testid="stSidebar"] { background:#ffffff; }
        .topbar { background:#2874f0; padding:10px 18px 14px; border-radius:0 0 14px 14px; color:white; margin-bottom:8px; }
        .brand-row { display:flex; align-items:center; gap:10px; }
        .brand-logo { width:42px; height:42px; border-radius:11px; background:#ffe500; color:#2874f0; display:flex; align-items:center; justify-content:center; font-size:30px; font-weight:900; font-style:italic; }
        .brand-name { font-size:26px; font-weight:800; line-height:1; }
        .brand-sub { font-size:11px; opacity:.9; margin-top:3px; }
        .top-search { background:white; color:#777; border-radius:8px; padding:13px 18px; margin-top:12px; font-size:16px; box-shadow:0 1px 3px rgba(0,0,0,.15); }
        .service-strip { display:flex; gap:10px; overflow:hidden; margin:10px 0; }
        .service-card { background:#fff; border:1px solid #e4e7eb; border-radius:14px; padding:12px 18px; min-width:145px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,.05); }
        .service-card b { display:block; color:#172337; font-size:15px; margin-top:5px; }
        .address-bar { background:#f5f8fc; border:1px solid #e1e7ef; border-radius:10px; padding:12px 15px; color:#263445; margin-bottom:10px; }
        .category-strip { background:#fff; border-bottom:1px solid #e5e7eb; display:flex; gap:25px; padding:8px 12px 12px; overflow:hidden; }
        .cat { min-width:85px; text-align:center; color:#424b57; font-size:14px; }
        .cat-icon { font-size:30px; display:block; }
        .cat-active { border-bottom:3px solid #2874f0; padding-bottom:8px; }
        .home-section { background:white; border:1px solid #e7eaf0; border-radius:12px; padding:16px; margin-top:14px; }
        .offer-banner { background:linear-gradient(110deg,#fff1a8,#ffffff); border:1px solid #ffe27a; border-radius:12px; padding:20px; }
        .offer-banner h2 { margin:0; color:#172337; }
        .offer-banner p { margin:6px 0 0; color:#5b6573; }
        .product-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:12px; min-height:360px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
        /* Product grid alignment */
        .shopzone-product-image {
            height:190px;
            width:100%;
            display:flex;
            align-items:center;
            justify-content:center;
            overflow:hidden;
            border-radius:9px;
            background:#f8f9fb;
            margin-bottom:10px;
        }
        .shopzone-product-image img {
            width:100%;
            height:190px;
            object-fit:contain;
            display:block;
        }
        .shopzone-no-image { font-size:48px; }
        .shopzone-product-title {
            height:52px;
            overflow:hidden;
            display:-webkit-box;
            -webkit-line-clamp:2;
            -webkit-box-orient:vertical;
            font-size:17px;
            line-height:1.35;
            font-weight:700;
            color:#172337;
            margin-top:2px;
        }
        .shopzone-product-category {
            height:24px;
            overflow:hidden;
            color:#7a8492;
            font-size:13px;
            line-height:24px;
            margin-bottom:2px;
        }
        .shopzone-product-price {
            height:40px;
            display:flex;
            align-items:center;
            font-size:24px;
            line-height:1;
            font-weight:800;
            color:#172337;
        }
        .shopzone-product-rating {
            height:34px;
            display:flex;
            align-items:center;
            color:#4b5563;
            font-size:13px;
            margin-bottom:5px;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            height:100%;
            border-radius:12px;
            background:#fff;
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            height:100%;
        }
        </style>
        """, unsafe_allow_html=True
    )

    # ---------------- SHOPZONE TOP HEADER ----------------
    st.markdown(
        """
        <div class="topbar">
          <div class="brand-row">
            <div class="brand-logo">S</div>
            <div><div class="brand-name">ShopZone</div><div class="brand-sub">Smart shopping for everyone</div></div>
          </div>
          <div class="top-search">🔍 &nbsp; Search for products, brands and more</div>
        </div>
        <div class="service-strip">
          <div class="service-card">🛍️<b>ShopZone</b></div>
          <div class="service-card">🏷️<b>Deals</b></div>
          <div class="service-card">✈️<b>Travel</b></div>
          <div class="service-card">🛒<b>Grocery</b></div>
        </div>
        <div class="address-bar">🏠 <b>HOME</b> &nbsp; Deliver to <b>Paramakudi, 623707</b> &nbsp;⌄</div>
        <div class="category-strip">
          <div class="cat cat-active"><span class="cat-icon">🛍️</span>For You</div>
          <div class="cat"><span class="cat-icon">👕</span>Fashion</div>
          <div class="cat"><span class="cat-icon">📱</span>Mobiles</div>
          <div class="cat"><span class="cat-icon">💻</span>Electronics</div>
          <div class="cat"><span class="cat-icon">💄</span>Beauty</div>
          <div class="cat"><span class="cat-icon">🏠</span>Home</div>
        </div>
        """, unsafe_allow_html=True
    )

    # ---------------- SIDEBAR ----------------
    with st.sidebar:

        st.markdown("## 🛒 ShopZone")

        st.write(
            f"Welcome, **{st.session_state.username}** 👋"
        )

        st.divider()

        cart_count = len(st.session_state.cart)

        menu_options = [
            "🏠 Home",
            "🛍️ Products",
            "🔎 Product Details",
            f"🛒 Cart ({cart_count})",
            "❤️ Wishlist",
            "📦 My Orders",
            "👤 Profile"
        ]
        if st.session_state.get("order_success"):
            menu_options.insert(0, "🎉 Order Success")

        # Keep the selected page after button clicks/reruns.
        if st.session_state.page not in menu_options:
            st.session_state.page = "🏠 Home"

        menu = st.radio(
            "MENU",
            menu_options,
            index=menu_options.index(st.session_state.page)
        )
        st.session_state.page = menu

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.cart = []
            st.session_state.wishlist = []
            st.session_state.page = "🏠 Home"
            st.session_state.selected_product = None
            st.rerun()


    # =====================================================
    # HOME / DASHBOARD
    # =====================================================

    if menu == "🏠 Home":

        # ---------- HOME SEARCH ----------
        st.markdown("""
        <style>
        .home-hero {
            background: linear-gradient(105deg,#2874f0,#1557c0);
            color:white; border-radius:14px; padding:28px 32px;
            margin-bottom:14px;
        }
        .home-hero h1 { margin:0; font-size:34px; }
        .home-hero p { margin:7px 0 0; opacity:.92; font-size:16px; }
        .deal-title { font-size:22px; font-weight:800; margin:18px 0 10px; color:#172337; }
        .home-note { color:#5b6573; font-size:14px; }
        </style>
        """, unsafe_allow_html=True)

        # Real interactive search field
        home_search = st.text_input(
            "🔎 Search",
            placeholder="Search for products, brands and more...",
            label_visibility="collapsed",
            key="home_search"
        )

        if home_search.strip():
            st.session_state.page = "🛍️ Products"
            st.session_state.product_search_from_home = home_search.strip()
            st.rerun()

        st.markdown("""
        <div class="home-hero">
          <h1>Welcome to ShopZone 🛍️</h1>
          <p>Discover great products, exciting deals and easy shopping — all in one place.</p>
        </div>
        """, unsafe_allow_html=True)

        # ---------- CATEGORY BUTTONS ----------
        st.markdown('<div class="deal-title">🛍️ Shop by Category</div>', unsafe_allow_html=True)

        categories_home = [
            ("👕", "Fashion"),
            ("📱", "Mobiles"),
            ("💻", "Electronics"),
            ("💄", "Beauty"),
            ("🏠", "Home"),
            ("🎮", "Gaming"),
        ]

        cat_cols = st.columns(6)
        for i, (icon, name) in enumerate(categories_home):
            with cat_cols[i]:
                if st.button(f"{icon}\n{name}", key=f"home_cat_{i}", use_container_width=True):
                    st.session_state.page = "🛍️ Products"
                    st.session_state.home_category = name
                    st.rerun()

        # ---------- OFFER BANNER ----------
        st.markdown("""
        <div class="offer-banner" style="margin-top:16px;">
          <h2>🔥 Mega Shopping Deals</h2>
          <p>Save more on your favourite products. Explore today's best picks on ShopZone.</p>
        </div>
        """, unsafe_allow_html=True)

        b1, b2, b3 = st.columns(3)
        with b1:
            st.info("🚚 **Fast Delivery**\n\nGet your products delivered quickly.")
        with b2:
            st.success("💰 **Best Prices**\n\nFind great value across categories.")
        with b3:
            st.warning("🔒 **Secure Shopping**\n\nSimple and secure checkout.")

        # ---------- DEALS FROM PRODUCTS CSV ----------
        try:
            home_df = pd.read_csv("products.csv")
            if "id" not in home_df.columns:
                home_df.insert(0, "id", range(1, len(home_df) + 1))
            home_df["Price"] = pd.to_numeric(home_df["Price"], errors="coerce")
            home_df = home_df.dropna(subset=["Price"])

            st.markdown('<div class="deal-title">⚡ Deals of the Day</div>', unsafe_allow_html=True)

            deal_items = home_df.head(4).to_dict("records")
            deal_cols = st.columns(4)

            for i, product in enumerate(deal_items):
                with deal_cols[i]:
                    with st.container(border=True):
                        st.image(product["Image"], use_container_width=True)
                        st.markdown(f"**{product['Product']}**")
                        st.caption(product["Category"])
                        st.markdown(f"### ₹{float(product['Price']):,.0f}")
                        st.write("⭐ 4.5  •  Best Seller")

                        if st.button(
                            "View Product",
                            key=f"home_view_{product['id']}",
                            use_container_width=True
                        ):
                            st.session_state.selected_product = product
                            st.session_state.quantity = 1
                            st.session_state.page = "🔎 Product Details"
                            st.rerun()

            # ---------- RECOMMENDED ----------
            st.markdown('<div class="deal-title">⭐ Recommended for You</div>', unsafe_allow_html=True)

            recommended = home_df.tail(min(4, len(home_df))).to_dict("records")
            rec_cols = st.columns(4)

            for i, product in enumerate(recommended):
                with rec_cols[i]:
                    with st.container(border=True):
                        st.image(product["Image"], use_container_width=True)
                        st.markdown(f"**{product['Product']}**")
                        st.caption(product["Category"])
                        st.markdown(f"### ₹{float(product['Price']):,.0f}")

                        if st.button(
                            "🛒 Add to Cart",
                            key=f"home_cart_{product['id']}",
                            use_container_width=True,
                            type="primary"
                        ):
                            add_to_cart(st.session_state.username, product, 1)
                            st.success("Added to cart! ✅")

        except FileNotFoundError:
            st.warning("products.csv not found. Add products.csv beside app.py.")

        # ---------- PERSONAL SHOPPING SUMMARY ----------
        st.markdown('<div class="deal-title">🧾 Your ShopZone</div>', unsafe_allow_html=True)

        s1, s2, s3 = st.columns(3)
        with s1:
            if st.button(f"🛒 Cart  •  {len(st.session_state.cart)}", use_container_width=True):
                st.session_state.page = f"🛒 Cart ({len(st.session_state.cart)})"
                st.rerun()
        with s2:
            if st.button(f"❤️ Wishlist  •  {len(st.session_state.wishlist)}", use_container_width=True):
                st.session_state.page = "❤️ Wishlist"
                st.rerun()
        with s3:
            if st.button(f"📦 Orders  •  {len(st.session_state.orders)}", use_container_width=True):
                st.session_state.page = "📦 My Orders"
                st.rerun()

    # =====================================================
    # PRODUCTS
    # =====================================================

    elif menu == "🛍️ Products":

        st.title("🛍️ All Products")

        st.write(
            "Find your favourite products, compare prices and add them to your cart."
        )

        # ---------------- LOAD CSV ----------------

        try:
            products_df = pd.read_csv("products.csv")

            # If products.csv does not have an id column, create one automatically.
            if "id" not in products_df.columns:
                products_df.insert(0, "id", range(1, len(products_df) + 1))

            # Clean price values so cart calculations work reliably.
            products_df["Price"] = pd.to_numeric(
                products_df["Price"], errors="coerce"
            )
            products_df = products_df.dropna(subset=["Price"])

        except FileNotFoundError:

            st.error(
                "❌ products.csv file not found!"
            )

            st.info(
                "Make sure products.csv is inside the same folder as app.py."
            )

            st.stop()

        # ---------------- SEARCH + CATEGORY + SORT ----------------

        categories = ["All Categories"] + sorted(
            products_df["Category"].dropna().astype(str).unique().tolist()
        )

        home_search_value = st.session_state.get("product_search_from_home", "")
        home_category_value = st.session_state.get("home_category", "")

        # Match Home category to the actual CSV category values without changing products.csv.
        category_match = ""
        if home_category_value:
            wanted = home_category_value.strip().lower()
            exact = [c for c in categories if str(c).strip().lower() == wanted]
            if exact:
                category_match = exact[0]
            else:
                partial = [c for c in categories if wanted in str(c).strip().lower() or str(c).strip().lower() in wanted]
                if partial:
                    category_match = partial[0]

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            search = st.text_input(
                "🔎 Search Products",
                value=home_search_value,
                placeholder="Search for a product...",
                key="products_search"
            )

        with col2:
            default_category = category_match if category_match in categories else "All Categories"
            selected_category = st.selectbox(
                "📂 Category",
                categories,
                index=categories.index(default_category),
                key="products_category"
            )

        with col3:
            sort_option = st.selectbox(
                "↕️ Sort",
                ["Recommended", "Price: Low to High", "Price: High to Low"],
                key="products_sort"
            )

        # One-click reset of Home filters.
        if st.button("✖️ Clear Filters", key="clear_product_filters"):
            st.session_state.product_search_from_home = ""
            st.session_state.home_category = ""
            st.session_state.products_search = ""
            st.session_state.products_category = "All Categories"
            st.session_state.products_sort = "Recommended"
            st.rerun()

        # ---------------- FILTER ----------------

        filtered_df = products_df.copy()

        if search:

            filtered_df = filtered_df[
                filtered_df["Product"]
                .str.contains(
                    search,
                    case=False,
                    na=False
                )
            ]

        if selected_category != "All Categories":

            filtered_df = filtered_df[
                filtered_df["Category"].astype(str)
                == str(selected_category)
            ]

        if sort_option == "Price: Low to High":
            filtered_df = filtered_df.sort_values("Price", ascending=True)
        elif sort_option == "Price: High to Low":
            filtered_df = filtered_df.sort_values("Price", ascending=False)

        # Once the filter has been consumed, clear Home-only values so normal navigation stays clean.
        st.session_state.product_search_from_home = ""
        st.session_state.home_category = ""

        st.divider()

        st.write(
            f"**{len(filtered_df)} product(s) found**"
        )

        # ---------------- PRODUCT CARDS ----------------

        if len(filtered_df) == 0:

            st.warning(
                "😕 No products found."
            )

        else:

            products_list = filtered_df.to_dict(
                orient="records"
            )

            # Clean 5-column product grid with equal visual alignment.
            # The fixed image/title areas keep price + buttons on the same horizontal lines.
            for start in range(0, len(products_list), 5):

                row = products_list[start:start + 5]
                columns = st.columns(5, gap="small")

                for col, product in zip(columns, row):
                    with col:
                        # Use a real Streamlit bordered container so the complete card
                        # (including buttons) belongs to one visual block.
                        with st.container(border=True):

                            # Fixed image area prevents different source-image ratios
                            # from pushing the text/buttons out of alignment.
                            image_url = str(product.get("Image", "")).strip()
                            if image_url:
                                st.markdown(
                                    f"""<div class=\"shopzone-product-image\">
                                        <img src=\"{image_url}\" alt=\"{product['Product']}\" />
                                    </div>""",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    '<div class="shopzone-product-image shopzone-no-image">📦</div>',
                                    unsafe_allow_html=True,
                                )

                            # Fixed title area keeps the price/rating rows aligned.
                            title = str(product["Product"])
                            st.markdown(
                                f'<div class="shopzone-product-title">{title}</div>',
                                unsafe_allow_html=True,
                            )

                            category = str(product.get("Category", ""))
                            st.markdown(
                                f'<div class="shopzone-product-category">{category}</div>',
                                unsafe_allow_html=True,
                            )

                            price = product["Price"]
                            price_text = (
                                f"₹{price:,.0f}"
                                if isinstance(price, (int, float))
                                else f"₹{price}"
                            )
                            st.markdown(
                                f'<div class="shopzone-product-price">{price_text}</div>',
                                unsafe_allow_html=True,
                            )

                            st.markdown(
                                '<div class="shopzone-product-rating">⭐ 4.5 &nbsp;•&nbsp; Best Seller</div>',
                                unsafe_allow_html=True,
                            )

                            # Keep all action buttons at the same vertical position.
                            if st.button(
                                "🛒 Add to Cart",
                                key=f"cart_{product['id']}",
                                use_container_width=True,
                            ):
                                add_to_cart(st.session_state.username, product, 1)
                                st.success("Added to cart!")

                            if st.button(
                                "👁️ View Details",
                                key=f"details_{product['id']}",
                                use_container_width=True,
                            ):
                                st.session_state.selected_product = product
                                st.session_state.quantity = 1
                                st.session_state.page = "🔎 Product Details"
                                st.rerun()

                            if st.button(
                                "❤️ Wishlist",
                                key=f"wish_{product['id']}",
                                use_container_width=True,
                            ):
                                if str(product["id"]) not in [
                                    str(item["id"])
                                    for item in st.session_state.wishlist
                                ]:
                                    add_to_wishlist(st.session_state.username, product)
                                    st.success("Added to wishlist!")
                                else:
                                    st.info("Already in wishlist.")


    # =====================================================
    # PRODUCT DETAILS
    # =====================================================

    elif menu == "🔎 Product Details":

        product = st.session_state.selected_product

        if product is None:
            st.info("👈 Select a product from the Products page to view its details.")
            if st.button("🛍️ Browse Products", type="primary"):
                st.session_state.page = "🛍️ Products"
                st.rerun()
        else:
            # ---------- STEP 3: PROFESSIONAL PRODUCT DETAILS ----------
            product_price = float(product.get("Price", 0))
            product_name = str(product.get("Product", "Product"))
            category = str(product.get("Category", ""))
            image = str(product.get("Image", ""))

            st.markdown(
                f'<div class="pz-breadcrumb">Home  ›  {category}  ›  {product_name}</div>',
                unsafe_allow_html=True
            )

            left, right = st.columns([1.05, 1.25], gap="large")

            with left:
                if image.strip():
                    st.image(image, use_container_width=True)
                else:
                    st.info("No product image available.")

                w1, w2 = st.columns(2)
                with w1:
                    if st.button(
                        "❤️ Wishlist",
                        key=f"detail_wish_{product.get('id')}",
                        use_container_width=True
                    ):
                        if str(product["id"]) not in [
                            str(item["id"]) for item in st.session_state.wishlist
                        ]:
                            add_to_wishlist(st.session_state.username, product)
                            st.session_state.wishlist = load_wishlist(st.session_state.username)
                            st.success("Added to wishlist! ❤️")
                        else:
                            st.info("Already in wishlist.")

                with w2:
                    if st.button(
                        "← Back to Products",
                        key="detail_back",
                        use_container_width=True
                    ):
                        st.session_state.page = "🛍️ Products"
                        st.rerun()

            with right:
                st.markdown(
                    f'<div class="pz-title">{product_name}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="pz-sub">{category} &nbsp; • &nbsp; ShopZone Verified Product</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    '<span style="background:#388e3c;color:white;padding:4px 8px;border-radius:5px;font-weight:700;">⭐ 4.5</span> '
                    '<span style="color:#667085;">&nbsp; Best Seller</span>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<div class="pz-price">₹{product_price:,.0f}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    '<span class="pz-offer">✓ Special price available</span>',
                    unsafe_allow_html=True
                )

                st.markdown("""
                <div class="pz-box">
                    <h4>🚚 Delivery</h4>
                    <div class="pz-feature">📦 Fast delivery available</div>
                    <div class="pz-feature">📍 Delivery address can be added at checkout</div>
                    <div class="pz-feature">↩️ Easy order support</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("""
                <div class="pz-box">
                    <h4>🛡️ ShopZone Protection</h4>
                    <div class="pz-feature">🔒 Secure payment</div>
                    <div class="pz-feature">✅ Trusted shopping experience</div>
                    <div class="pz-feature">📞 Customer support</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### 🔢 Quantity")
                q1, q2, q3 = st.columns([1, 1, 1])

                with q1:
                    if st.button("➖", key="detail_minus", use_container_width=True):
                        st.session_state.quantity = max(
                            1, int(st.session_state.quantity) - 1
                        )
                        st.rerun()

                with q2:
                    st.markdown(
                        f'<div style="text-align:center;font-size:20px;font-weight:800;padding:7px;border:1px solid #e5e7eb;border-radius:8px;">{int(st.session_state.quantity)}</div>',
                        unsafe_allow_html=True
                    )

                with q3:
                    if st.button("➕", key="detail_plus", use_container_width=True):
                        st.session_state.quantity = int(st.session_state.quantity) + 1
                        st.rerun()

                quantity = max(1, int(st.session_state.quantity))
                total = product_price * quantity

                st.markdown(
                    f'<div class="pz-total">Total: ₹{total:,.0f}</div>',
                    unsafe_allow_html=True
                )

                a1, a2 = st.columns(2)

                with a1:
                    if st.button(
                        "🛒 Add to Cart",
                        key=f"detail_add_cart_{product.get('id')}",
                        type="primary",
                        use_container_width=True
                    ):
                        add_to_cart(
                            st.session_state.username,
                            product,
                            quantity
                        )
                        st.session_state.cart = load_cart(st.session_state.username)
                        st.success(f"Added {quantity} item(s) to cart! 🛒")

                with a2:
                    if st.button(
                        "⚡ Buy Now",
                        key=f"detail_buy_{product.get('id')}",
                        use_container_width=True
                    ):
                        add_to_cart(
                            st.session_state.username,
                            product,
                            quantity
                        )
                        st.session_state.cart = load_cart(st.session_state.username)
                        st.session_state.checkout = True
                        st.session_state.page = f"🛒 Cart ({len(st.session_state.cart)})"
                        st.rerun()

            st.markdown("---")

            d1, d2 = st.columns([1.5, 1])

            with d1:
                st.markdown("### 📝 Product Description")
                st.write(
                    f"Explore the {product_name} available on ShopZone. "
                    "Check the price, choose your required quantity and place your order securely."
                )

                st.markdown("### ✨ Highlights")
                st.markdown("""
                - ⭐ Highly rated product
                - 💰 Competitive ShopZone price
                - 🚚 Fast delivery support
                - 🔒 Secure checkout
                - 🛒 Easy add-to-cart and Buy Now
                """)

            with d2:
                st.markdown("### 📦 Order Summary")
                st.markdown(
                    f"""
                    <div class="pz-trust">
                    <b>Product</b><br>{product_name}<br><br>
                    <b>Category</b><br>{category}<br><br>
                    <b>Quantity</b><br>{quantity}<br><br>
                    <b>Amount</b><br>₹{total:,.0f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


    # =====================================================
    # CART + CHECKOUT
    # =====================================================

    elif menu.startswith("🛒 Cart"):

        st.markdown("""
        <style>
        .cart-head {
            background:linear-gradient(135deg,#2874f0,#1557c0);
            color:#fff; border-radius:14px; padding:22px 26px;
            margin-bottom:18px;
        }
        .cart-head h1 { margin:0; font-size:30px; }
        .cart-head p { margin:6px 0 0; opacity:.92; }
        .cart-card {
            border:1px solid #e2e5e9; border-radius:14px;
            padding:16px; background:#fff; margin-bottom:12px;
        }
        .cart-product-name { font-size:18px; font-weight:750; color:#172337; margin-bottom:4px; }
        .cart-category { color:#7b8490; font-size:13px; margin-bottom:8px; }
        .cart-price { font-size:20px; font-weight:800; color:#172337; }
        .summary-card {
            border:1px solid #e2e5e9; border-radius:14px;
            padding:20px; background:#fff; position:sticky; top:10px;
        }
        .summary-total { font-size:25px; font-weight:850; color:#172337; }
        .checkout-box {
            border:1px solid #dfe4ea; border-radius:14px;
            padding:20px; background:#fff; margin-top:14px;
        }
        .checkout-step {
            font-size:18px; font-weight:800; color:#172337;
            margin-bottom:12px;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="cart-head">
          <h1>🛒 Shopping Cart</h1>
          <p>Review your items, choose quantities and checkout securely.</p>
        </div>
        """, unsafe_allow_html=True)

        cart = st.session_state.cart

        if not cart:
            st.markdown("""
            <div class="cart-card" style="text-align:center;padding:45px 20px;">
              <div style="font-size:55px;">🛍️</div>
              <h2>Your cart is empty</h2>
              <p style="color:#6b7280;">Add products from ShopZone and they will appear here.</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🛍️ Continue Shopping", type="primary", use_container_width=True):
                st.session_state.page = "🛍️ Products"
                st.session_state.checkout = False
                st.rerun()

        else:
            # Group the repeated database rows into product + quantity.
            grouped = {}
            for item in cart:
                pid = str(item["id"])
                if pid not in grouped:
                    grouped[pid] = dict(item)
                    grouped[pid]["quantity"] = 0
                grouped[pid]["quantity"] += 1

            cart_items = list(grouped.values())
            subtotal = sum(float(item["Price"]) * int(item["quantity"]) for item in cart_items)
            delivery = 0 if subtotal >= 999 else 49
            total = subtotal + delivery

            left, right = st.columns([1.75, 1], gap="large")

            with left:
                st.markdown(f"### 🛍️ Your Items ({sum(int(i['quantity']) for i in cart_items)})")

                for item in cart_items:
                    pid = str(item["id"])
                    qty = int(item["quantity"])
                    unit_price = float(item["Price"])
                    item_total = unit_price * qty

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1.0, 2.6, 1.25])

                        with c1:
                            image = item.get("Image", "")
                            if image:
                                st.image(image, use_container_width=True)

                        with c2:
                            st.markdown(f'<div class="cart-product-name">{item["Product"]}</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="cart-category">{item.get("Category", "Product")}</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="cart-price">₹{unit_price:,.0f}</div>', unsafe_allow_html=True)
                            st.caption("⭐ 4.5 • Best Seller")

                        with c3:
                            st.markdown(f"**Item Total**  \n₹{item_total:,.0f}")
                            q1, q2, q3 = st.columns([1, 1, 1])
                            with q1:
                                if st.button("➖", key=f"qty_minus_{pid}", use_container_width=True):
                                    update_cart_quantity(st.session_state.username, pid, qty - 1)
                                    st.rerun()
                            with q2:
                                st.markdown(f"<div style='text-align:center;font-weight:800;font-size:18px;padding-top:5px'>{qty}</div>", unsafe_allow_html=True)
                            with q3:
                                if st.button("➕", key=f"qty_plus_{pid}", use_container_width=True):
                                    update_cart_quantity(st.session_state.username, pid, qty + 1)
                                    st.rerun()

                            if st.button("🗑️ Remove", key=f"remove_cart_{pid}", use_container_width=True):
                                remove_cart_item(st.session_state.username, pid)
                                st.rerun()

            with right:
                st.markdown("<div class='summary-card'>", unsafe_allow_html=True)
                st.markdown("### 💳 Price Details")
                st.write(f"Items ({sum(int(i['quantity']) for i in cart_items)}) ........ ₹{subtotal:,.0f}")
                if delivery == 0:
                    st.write("Delivery ..................... FREE")
                else:
                    st.write("Delivery ..................... ₹49")
                st.divider()
                st.markdown(f"<div class='summary-total'>Total: ₹{total:,.0f}</div>", unsafe_allow_html=True)
                if delivery == 0:
                    st.success("🎉 You unlocked FREE delivery!")
                else:
                    st.caption("🚚 Free delivery on orders above ₹999")
                st.markdown("</div>", unsafe_allow_html=True)

                st.write("")
                if st.button("🧹 Clear Cart", use_container_width=True):
                    clear_cart(st.session_state.username)
                    st.session_state.checkout = False
                    st.rerun()

                if not st.session_state.checkout:
                    if st.button("⚡ Proceed to Checkout", type="primary", use_container_width=True):
                        st.session_state.checkout = True
                        st.rerun()

            # ---------------- CHECKOUT ----------------
            if st.session_state.checkout:
                st.markdown("---")
                st.markdown("<div class='checkout-box'>", unsafe_allow_html=True)
                st.markdown("<div class='checkout-step'>1️⃣ Delivery Address</div>", unsafe_allow_html=True)

                saved = get_saved_address(st.session_state.username)
                st.session_state.saved_address = saved

                place_order = False
                customer_name = phone = city = pincode = address = ""

                if saved:
                    customer_name = saved["name"]
                    phone = saved["phone"]
                    address = saved["address"]
                    city = saved["city"]
                    pincode = saved["pincode"]

                    st.markdown(f"""
                    <div style="background:#f5f9ff;border:1px solid #d7e5f8;border-radius:12px;padding:16px;margin-bottom:16px;">
                      <div style="font-size:13px;color:#6b7280;margin-bottom:5px;">DELIVER TO</div>
                      <div style="font-size:18px;font-weight:800;color:#172337;">{customer_name} &nbsp; • &nbsp; {phone}</div>
                      <div style="margin-top:7px;color:#374151;">{address}</div>
                      <div style="margin-top:4px;color:#374151;">{city} - {pincode}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info("📍 This saved Profile address will be used automatically for this order.")
                    if st.button("✏️ Change Delivery Address", use_container_width=True, key="change_checkout_address"):
                        st.session_state.page = "👤 Profile"
                        st.session_state.checkout = False
                        st.rerun()

                    st.markdown("<div class='checkout-step'>2️⃣ Payment Method</div>", unsafe_allow_html=True)
                    payment = st.radio(
                        "Choose payment",
                        ["💵 Cash on Delivery", "📱 UPI", "💳 Credit / Debit Card"],
                        horizontal=True,
                        key="checkout_payment_saved",
                    )

                    st.markdown("<div class='checkout-step'>3️⃣ Final Order Summary</div>", unsafe_allow_html=True)
                    st.write(f"Subtotal: ₹{subtotal:,.0f}")
                    st.write(f"Delivery: {'FREE' if delivery == 0 else '₹49'}")
                    st.markdown(f"### Payable Amount: ₹{total:,.0f}")
                    st.caption("🔒 Demo checkout — no real payment will be charged.")
                    place_order = st.button("✅ Place Order", type="primary", use_container_width=True, key="place_saved_address_order")

                else:
                    st.warning("📍 No delivery address is saved in your Profile yet.")
                    st.write("Save your address once in **Profile → Delivery Address**. Checkout will then use it automatically.")
                    if st.button("👤 Add Address in Profile", type="primary", use_container_width=True, key="add_profile_address_checkout"):
                        st.session_state.page = "👤 Profile"
                        st.session_state.checkout = False
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

                if place_order and saved:
                    clean_phone = phone.strip()
                    clean_pin = pincode.strip()
                    if not clean_phone.isdigit() or len(clean_phone) != 10:
                        st.error("❌ Your saved Profile mobile number is invalid. Please update it in Profile.")
                    elif not clean_pin.isdigit() or len(clean_pin) != 6:
                        st.error("❌ Your saved Profile pincode is invalid. Please update it in Profile.")
                    else:
                        order_items = []
                        for item in cart_items:
                            for _ in range(int(item["quantity"])):
                                order_items.append({
                                    "id": item["id"],
                                    "Product": item["Product"],
                                    "Category": item.get("Category", ""),
                                    "Price": float(item["Price"]),
                                    "Image": item.get("Image", ""),
                                })

                        order = {
                            "order_id": "SZ" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[-12:],
                            "username": st.session_state.username,
                            "date": datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p"),
                            "items": order_items,
                            "subtotal": subtotal,
                            "delivery": delivery,
                            "total": total,
                            "payment": payment,
                            "name": customer_name,
                            "phone": clean_phone,
                            "address": address,
                            "city": city,
                            "pincode": clean_pin,
                            "status": "Order Placed",
                        }
                        save_order(order)

                        product_lines = "\n".join(
                            f"- {item['Product']} | Qty: 1 | ₹{item['Price']:,.2f}"
                            for item in order_items
                        )
                        order_email_body = f"""ShopZone - Order Confirmed\n\nOrder ID: {order['order_id']}\nDate: {order['date']}\nUsername: {order['username']}\nCustomer: {order['name']}\nPhone: {order['phone']}\n\nDelivery Address:\n{order['address']}\n{order['city']} - {order['pincode']}\n\nProducts:\n{product_lines}\n\nSubtotal: ₹{order['subtotal']:,.2f}\nDelivery: ₹{order['delivery']:,.2f}\nTotal: ₹{order['total']:,.2f}\nPayment: {order['payment']}\nStatus: {order['status']}\n"""
                        send_admin_email("ShopZone - Order Confirmed | " + order["order_id"], order_email_body)

                        clear_cart(st.session_state.username)
                        st.session_state.cart = []
                        st.session_state.checkout = False
                        st.session_state.orders = load_orders(st.session_state.username)
                        st.session_state.order_success = order
                        st.session_state.page = "🎉 Order Success"
                        st.rerun()

    elif menu == "❤️ Wishlist":

        st.title("❤️ My Wishlist")

        if len(st.session_state.wishlist) == 0:

            st.info(
                "Your wishlist is empty."
            )

        else:

            for item in st.session_state.wishlist:

                col1, col2 = st.columns(
                    [1, 3]
                )

                with col1:

                    st.image(
                        item["Image"],
                        width=120
                    )

                with col2:

                    st.subheader(
                        item["Product"]
                    )

                    st.write(
                        f"₹{float(item['Price']):,.2f}"
                    )

                    if st.button(
                        "🛒 Add to Cart",
                        key=f"wishcart_{item['id']}"
                    ):

                        add_to_cart(
                            st.session_state.username,
                            item,
                            1
                        )

                        st.success("Added to cart!")

                st.divider()


    # =====================================================
    # ORDER SUCCESS ANIMATION
    # =====================================================

    elif menu == "🎉 Order Success":
        success_order = st.session_state.order_success
        if success_order:
            item_count = sum(int(x.get("quantity", 1)) if isinstance(x, dict) else 1 for x in success_order.get("items", []))

            st.markdown("""
            <style>
            .sz-success-screen{
                min-height:72vh; margin:-1rem -1rem 0; padding:55px 18px 45px;
                background:linear-gradient(180deg,#67df79 0%,#72df80 100%);
                border-radius:0 0 28px 28px; position:relative; overflow:hidden;
                display:flex; flex-direction:column; align-items:center; justify-content:center;
                text-align:center;
            }
            .sz-radar{position:relative;width:320px;height:320px;margin:0 auto 26px;}
            .sz-ring{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border-radius:50%;border:11px solid rgba(255,255,255,.78);box-sizing:border-box;}
            .sz-ring.r1{width:150px;height:150px;background:rgba(255,255,255,.10);}
            .sz-ring.r2{width:225px;height:225px;border-color:rgba(255,255,255,.65);background:rgba(255,255,255,.10);}
            .sz-ring.r3{width:300px;height:300px;border-color:rgba(255,255,255,.90);background:rgba(255,255,255,.04);}
            .sz-core{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:115px;height:115px;border-radius:50%;background:#67df79;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 18px rgba(255,255,255,.12);}
            .sz-check{font-size:66px;color:white;font-weight:900;line-height:1;transform:scale(0);animation:szPop .65s .45s forwards cubic-bezier(.2,.9,.3,1.3);}
            .sz-bolt{position:absolute;color:#ffd51c;font-size:35px;font-weight:900;text-shadow:0 2px 5px rgba(0,0,0,.10);animation:szFloat 1.8s infinite ease-in-out;}
            .sz-b1{left:20px;top:105px}.sz-b2{right:15px;top:70px;font-size:44px;animation-delay:.25s}.sz-b3{right:52px;bottom:58px;font-size:30px;animation-delay:.5s}.sz-b4{left:48px;bottom:55px;font-size:28px;animation-delay:.8s}
            .sz-success-heading{font-size:34px;font-weight:850;color:#fff;margin:2px 0 8px;text-shadow:0 2px 8px rgba(0,0,0,.10);}
            .sz-success-message{font-size:17px;color:rgba(255,255,255,.96);margin-bottom:22px;}
            .sz-order-pill{background:rgba(255,255,255,.94);color:#17351d;border-radius:14px;padding:12px 22px;font-size:15px;font-weight:750;box-shadow:0 8px 24px rgba(0,0,0,.10);}
            @keyframes szPop{to{transform:scale(1)}}
            @keyframes szFloat{0%,100%{transform:translateY(0) rotate(-8deg)}50%{transform:translateY(-18px) rotate(8deg)}}
            @keyframes szPulse{0%{transform:translate(-50%,-50%) scale(.82);opacity:.5}70%{transform:translate(-50%,-50%) scale(1.03);opacity:1}100%{transform:translate(-50%,-50%) scale(.82);opacity:.5}}
            .sz-ring.r3{animation:szPulse 1.7s infinite ease-in-out}
            @media(max-width:700px){.sz-success-screen{min-height:78vh}.sz-radar{width:285px;height:285px}.sz-ring.r3{width:270px;height:270px}.sz-ring.r2{width:205px;height:205px}.sz-ring.r1{width:138px;height:138px}.sz-success-heading{font-size:28px}}
            </style>
            <div class="sz-success-screen">
              <div class="sz-radar">
                <div class="sz-ring r3"></div><div class="sz-ring r2"></div><div class="sz-ring r1"></div>
                <div class="sz-core"><div class="sz-check">✓</div></div>
                <div class="sz-bolt sz-b1">ϟ</div><div class="sz-bolt sz-b2">⚡</div><div class="sz-bolt sz-b3">ϟ</div><div class="sz-bolt sz-b4">⚡</div>
              </div>
              <div class="sz-success-heading">Order Placed Successfully!</div>
              <div class="sz-success-message">Your order has been confirmed 🎉</div>
              <div class="sz-order-pill">Order ID: __ORDER_ID__ &nbsp; • &nbsp; ₹__TOTAL__</div>
            </div>
            """.replace("__ORDER_ID__", str(success_order["order_id"])).replace("__TOTAL__", f"{float(success_order['total']):,.0f}"), unsafe_allow_html=True)

            # Browser-generated success chime. Autoplay may be blocked by browser policy.
            st.markdown("""
            <audio autoplay>
              <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=" type="audio/wav">
            </audio>
            """, unsafe_allow_html=True)

            c1,c2,c3=st.columns([1,2,1])
            with c2:
                if st.button("📦 View My Orders", use_container_width=True, type="primary", key="success_view_orders"):
                    st.session_state.order_success = None
                    st.session_state.page = "📦 My Orders"
                    st.rerun()
                if st.button("🛍️ Continue Shopping", use_container_width=True, key="success_continue"):
                    st.session_state.order_success = None
                    st.session_state.page = "🏠 Home"
                    st.rerun()

    # =====================================================
    # ORDERS
    # =====================================================

    elif menu == "📦 My Orders":

        st.title("📦 My Orders")

        # =====================================================
        # ORDER SUCCESS CARD + SUCCESS SOUND
        # =====================================================
        if st.session_state.order_success:
            success_order = st.session_state.order_success
            success_items = success_order.get("items", [])
            item_count = sum(int(x.get("quantity", 1)) if isinstance(x, dict) else 1 for x in success_items)

            st.markdown("""
            <style>
            .sz-success-wrap{
                max-width:760px;margin:12px auto 28px;padding:34px 34px 28px;
                background:linear-gradient(180deg,#ffffff 0%,#f8fffa 100%);
                border:1px solid #d7f0dc;border-radius:20px;
                box-shadow:0 12px 35px rgba(0,0,0,.10);text-align:center;
            }
            .sz-success-icon{
                width:82px;height:82px;margin:0 auto 16px;border-radius:50%;
                background:#0b8f3d;color:#fff;display:flex;align-items:center;
                justify-content:center;font-size:48px;font-weight:800;
                box-shadow:0 8px 22px rgba(11,143,61,.25);
            }
            .sz-success-title{font-size:30px;font-weight:800;color:#172337;margin-bottom:7px;}
            .sz-success-sub{font-size:16px;color:#5b6472;margin-bottom:22px;}
            .sz-success-info{
                display:grid;grid-template-columns:repeat(3,1fr);gap:12px;
                margin:20px 0 24px;text-align:left;
            }
            .sz-info-box{background:#f4f7fb;border-radius:12px;padding:14px 16px;}
            .sz-info-label{font-size:12px;color:#7b8491;margin-bottom:4px;}
            .sz-info-value{font-size:16px;font-weight:750;color:#172337;}
            .sz-success-note{font-size:14px;color:#52606d;margin-top:6px;}
            @media(max-width:700px){
                .sz-success-wrap{padding:25px 16px;}
                .sz-success-info{grid-template-columns:1fr;}
                .sz-success-title{font-size:25px;}
            }
            </style>
            <div class="sz-success-wrap">
                <div class="sz-success-icon">✓</div>
                <div class="sz-success-title">Order Placed Successfully!</div>
                <div class="sz-success-sub">Thank you for shopping with <b>ShopZone</b> 🎉</div>
                <div class="sz-success-info">
                    <div class="sz-info-box"><div class="sz-info-label">ORDER ID</div><div class="sz-info-value">#{order_id}</div></div>
                    <div class="sz-info-box"><div class="sz-info-label">ITEMS</div><div class="sz-info-value">{item_count}</div></div>
                    <div class="sz-info-box"><div class="sz-info-label">TOTAL PAID</div><div class="sz-info-value">₹{total:,.0f}</div></div>
                </div>
                <div class="sz-success-note">🚚 Your order has been confirmed and will be processed shortly.</div>
            </div>
            """.format(
                order_id=success_order["order_id"],
                item_count=item_count,
                total=float(success_order["total"]),
            ), unsafe_allow_html=True)

            # Short success chime. Browser autoplay rules may block it; the fallback button below
            # lets the user replay it with a direct click.
            st.markdown("""
            <audio id="shopzone-success-sound" autoplay>
                <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=" type="audio/wav">
            </audio>
            <script>
            // Try a browser-generated success chime without requiring an external audio file.
            (function(){
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const play = () => {
                        const now = ctx.currentTime;
                        [[659,0],[784,.16],[988,.32],[1319,.48]].forEach(([freq,delay])=>{
                            const o=ctx.createOscillator(), g=ctx.createGain();
                            o.type='sine'; o.frequency.value=freq;
                            g.gain.setValueAtTime(0.0001, now+delay);
                            g.gain.exponentialRampToValueAtTime(0.16, now+delay+0.015);
                            g.gain.exponentialRampToValueAtTime(0.0001, now+delay+0.25);
                            o.connect(g); g.connect(ctx.destination);
                            o.start(now+delay); o.stop(now+delay+0.27);
                        });
                    };
                    if(ctx.state === 'suspended') ctx.resume().then(play); else play();
                } catch(e) {}
            })();
            </script>
            """, unsafe_allow_html=True)

            sound_col, shop_col = st.columns(2)
            with sound_col:
                if st.button("🔊 Play Success Sound", use_container_width=True, key="play_success_sound"):
                    st.markdown("""
                    <script>
                    (function(){
                        const C=new (window.AudioContext||window.webkitAudioContext)();
                        const n=C.currentTime;
                        [[659,0],[784,.16],[988,.32],[1319,.48]].forEach(([f,d])=>{
                            const o=C.createOscillator(),g=C.createGain();o.type='sine';o.frequency.value=f;
                            g.gain.setValueAtTime(.0001,n+d);g.gain.exponentialRampToValueAtTime(.18,n+d+.015);
                            g.gain.exponentialRampToValueAtTime(.0001,n+d+.25);o.connect(g);g.connect(C.destination);
                            o.start(n+d);o.stop(n+d+.27);
                        });
                    })();
                    </script>
                    """, unsafe_allow_html=True)
            with shop_col:
                if st.button("🛍️ Continue Shopping", use_container_width=True, key="continue_after_order"):
                    st.session_state.order_success = None
                    st.session_state.page = "🏠 Home"
                    st.rerun()

            st.markdown("---")

        user_orders = st.session_state.orders

        if not user_orders:
            st.info("You don't have any orders yet.")
            st.write("Your completed orders will appear here.")
        else:
            for order in reversed(user_orders):
                with st.container(border=True):

                    top1, top2 = st.columns(2)

                    with top1:
                        st.subheader(f"🧾 Order #{order['order_id']}")
                        st.caption(f"Placed on {order['date']}")

                    with top2:
                        st.success(f"✅ {order['status']}")

                    st.divider()

                    for item in order["items"]:
                        item_col1, item_col2, item_col3 = st.columns([1, 3, 1])

                        with item_col1:
                            st.image(item["Image"], width=80)

                        with item_col2:
                            st.write(f"**{item['Product']}**")
                            st.caption(item["Category"])

                        with item_col3:
                            st.write(f"₹{float(item['Price']):,.2f}")

                    st.divider()
                    st.write(f"💳 Payment: **{order['payment']}**")
                    st.write(
                        f"📍 Delivery: **{order['city']} - {order['pincode']}**"
                    )
                    st.markdown(f"### Total: ₹{order['total']:,.2f}")

                    # Cancel order option for active orders.
                    if order.get("status") not in ["Cancelled", "Delivered"]:
                        cancel_key = f"cancel_{order['order_id']}"
                        if st.button("❌ Cancel Order", key=cancel_key, use_container_width=True):
                            st.session_state[f"confirm_cancel_{order['order_id']}"] = True
                            st.rerun()

                        if st.session_state.get(f"confirm_cancel_{order['order_id']}", False):
                            st.warning("Are you sure you want to cancel this order?")
                            c_yes, c_no = st.columns(2)
                            with c_yes:
                                if st.button("Yes, Cancel Order", key=f"yes_{order['order_id']}", use_container_width=True):
                                    if cancel_order(st.session_state.username, order['order_id']):
                                        st.session_state.orders = load_orders(st.session_state.username)
                                        st.session_state.order_success = None
                                        st.session_state[f"confirm_cancel_{order['order_id']}"] = False
                                        st.success("Order cancelled successfully.")
                                        st.rerun()
                            with c_no:
                                if st.button("Keep Order", key=f"no_{order['order_id']}", use_container_width=True):
                                    st.session_state[f"confirm_cancel_{order['order_id']}"] = False
                                    st.rerun()

    # =====================================================
    # PROFILE
    # =====================================================

    elif menu == "👤 Profile":

        st.title("👤 My Profile")
        st.write(f"**Username:** {st.session_state.username}")
        st.write("**Account:** Active ✅")

        st.divider()
        st.subheader("📍 Delivery Address")
        st.caption("Save your address here once. Checkout will automatically use this address for every order.")

        saved = get_saved_address(st.session_state.username) or {
            "name": "", "phone": "", "address": "", "city": "", "pincode": ""
        }

        with st.form("profile_address_form"):
            p1, p2 = st.columns(2)
            with p1:
                profile_name = st.text_input("Full Name", value=saved["name"], placeholder="Enter your name")
                profile_phone = st.text_input("Mobile Number", value=saved["phone"], max_chars=10, placeholder="10 digit mobile number")
                profile_city = st.text_input("City", value=saved["city"], placeholder="Enter city")
            with p2:
                profile_pincode = st.text_input("Pincode", value=saved["pincode"], max_chars=6, placeholder="6 digit pincode")
                profile_address = st.text_area("Full Address", value=saved["address"], height=110, placeholder="House / Street / Area")

            save_profile_address = st.form_submit_button("💾 Save Delivery Address", type="primary", use_container_width=True)

        if save_profile_address:
            clean_phone = profile_phone.strip()
            clean_pin = profile_pincode.strip()
            if not all([profile_name.strip(), clean_phone, profile_city.strip(), clean_pin, profile_address.strip()]):
                st.error("❌ Please fill all address fields.")
            elif not clean_phone.isdigit() or len(clean_phone) != 10:
                st.error("❌ Please enter a valid 10-digit mobile number.")
            elif not clean_pin.isdigit() or len(clean_pin) != 6:
                st.error("❌ Please enter a valid 6-digit pincode.")
            else:
                save_address(st.session_state.username, profile_name, clean_phone, profile_address, profile_city, clean_pin)
                st.session_state.saved_address = get_saved_address(st.session_state.username)

                address_email_body = f"""ShopZone - New Delivery Address Saved\n\nUsername: {st.session_state.username}\nName: {profile_name.strip()}\nPhone: {clean_phone}\nAddress: {profile_address.strip()}\nCity: {profile_city.strip()}\nPincode: {clean_pin}\n"""
                send_admin_email("ShopZone - New Delivery Address Saved", address_email_body)

                st.success("✅ Delivery address saved! Checkout will use this address automatically.")
                st.rerun()

        if st.session_state.saved_address:
            a = st.session_state.saved_address
            st.markdown(f"""
            <div style="background:#f5f9ff;border:1px solid #d7e5f8;border-radius:12px;padding:16px;margin-top:16px;">
              <div style="font-weight:800;font-size:17px;color:#172337;">📍 Saved Address</div>
              <div style="margin-top:8px;"><b>{a['name']}</b> • {a['phone']}</div>
              <div style="margin-top:5px;color:#374151;">{a['address']}</div>
              <div style="margin-top:4px;color:#374151;">{a['city']} - {a['pincode']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.subheader("🛒 Shopping Summary")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Cart Items", len(st.session_state.cart))
        with col2:
            st.metric("Wishlist Items", len(st.session_state.wishlist))



