
import streamlit as st
import sqlite3
from datetime import datetime
import urllib.request
import urllib.error
import json

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="Campus Exchange",
    page_icon="🎓",
    layout="wide"
)

DB_NAME = "campus_exchange.db"

# ---------------- DATABASE ----------------

def get_connection():
    return sqlite3.connect(DB_NAME)

def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            price REAL DEFAULT 0,
            exchange_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            requester TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

setup_database()

# ---------------- DATABASE FUNCTIONS ----------------

def add_item(student, title, category, description,
             price, exchange_type, condition):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO items
        (student, title, category, description, price,
         exchange_type, condition, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        student, title, category, description, price,
        exchange_type, condition,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()

def get_items():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, student, title, category, description,
               price, exchange_type, condition, created_at
        FROM items
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows

def send_request(item_id, requester, message):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO requests
        (item_id, requester, message, status, created_at)
        VALUES (?, ?, ?, 'Pending', ?)
    """, (
        item_id, requester, message,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()

def get_requests():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT requests.id, requests.item_id, items.title,
               items.student, requests.requester,
               requests.message, requests.status,
               requests.created_at
        FROM requests
        JOIN items ON requests.item_id = items.id
        ORDER BY requests.id DESC
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows

def update_request(request_id, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE requests SET status = ? WHERE id = ?",
        (status, request_id)
    )

    conn.commit()
    conn.close()

# ---------------- AI HELPERS ----------------

def ask_local_ai(prompt):
    """Try a free local Ollama model, if available."""
    data = json.dumps({
        "model": "gemma3:1b",
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")

    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "").strip()
    except Exception:
        return None

def create_description(title, category, condition):
    prompt = (
        "Write a short, honest marketplace description in 2 or 3 sentences "
        "for a college student. Do not invent specifications. "
        f"Item: {title}. Category: {category}. Condition: {condition}."
    )

    result = ask_local_ai(prompt)

    if result:
        return result

    return (
        f"{title} is a {category.lower()} item in {condition.lower()} "
        "condition. Contact the student to confirm its details and "
        "arrange an exchange on campus."
    )

def recommend_items(user_need, items):
    """Try AI matching, then use keyword matching as a fallback."""
    prompt = (
        "You help college students find reusable items on campus. "
        "Based only on the listings below, recommend relevant item IDs "
        "for this student's need. Never invent an item. If nothing matches, "
        "say no suitable listing was found.\n\n"
        f"Student need: {user_need}\n\nListings:\n"
    )

    for item in items:
        prompt += (
            f"ID {item[0]}: {item[2]}, category {item[3]}, "
            f"description {item[4]}, type {item[6]}, "
            f"price Rs. {item[5]}\n"
        )

    prompt += "\nGive a short, helpful answer."

    result = ask_local_ai(prompt)

    if result:
        return result

    words = set(user_need.lower().split())
    matches = []

    for item in items:
        searchable = (
            str(item[2]) + " " + str(item[3]) + " "
            + str(item[4])
        ).lower()

        if any(word in searchable for word in words
               if len(word) > 2):
            matches.append(item)

    if matches:
        answer = "Here are possible matches:\n\n"
        for item in matches[:5]:
            answer += (
                f"- **{item[2]}** (ID {item[0]}), "
                f"{item[6]}, Rs. {item[5]:.2f}\n\n"
            )
        return answer

    return (
        "I couldn't find a clear keyword match. Try a more specific "
        "search, such as 'Python textbook' or 'scientific calculator'."
    )

# ---------------- SIDEBAR ----------------

st.sidebar.title("🎓 Campus Exchange")
st.sidebar.caption("Reuse • Exchange • Save")

student_name = st.sidebar.text_input(
    "Your student name",
    placeholder="Enter your name"
).strip()

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Browse Items",
        "Add Item",
        "My Requests",
        "AI Assistant",
        "Dashboard"
    ]
)

# ---------------- HOME ----------------

if page == "Home":
    st.title("🎓 Campus Exchange")
    st.subheader("Your campus. Your community. Less waste.")

    st.write(
        "A student marketplace to sell, exchange, borrow, "
        "or donate reusable college items."
    )

    items = get_items()
    requests = get_requests()

    col1, col2, col3 = st.columns(3)

    col1.metric("Items Listed", len(items))
    col2.metric("Exchange Requests", len(requests))
    col3.metric(
        "Completed Requests",
        sum(1 for r in requests if r[6] == "Completed")
    )

    st.divider()
    st.subheader("What can you do here?")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📚 Find Items")
        st.write(
            "Search for books, lab records, stationery, "
            "calculators, and other student essentials."
        )

    with col2:
        st.markdown("### ♻️ Reuse and Share")
        st.write(
            "Give useful items a second life and help "
            "fellow students save money."
        )

    st.info(
        "Getting started: enter your name in the sidebar, "
        "then choose Add Item or Browse Items."
    )

# ---------------- ADD ITEM ----------------

elif page == "Add Item":
    st.title("➕ Add a Campus Item")

    if not student_name:
        st.warning("Enter your name in the sidebar first.")
    else:
        with st.form("add_item_form"):
            title = st.text_input("Item name")
            category = st.selectbox(
                "Category",
                [
                    "Books",
                    "Lab Records",
                    "Stationery",
                    "Electronics",
                    "College Supplies",
                    "Other"
                ]
            )

            condition = st.selectbox(
                "Condition",
                ["New", "Like New", "Good", "Used"]
            )

            exchange_type = st.selectbox(
                "How do you want to share it?",
                ["Sell", "Exchange", "Borrow", "Donate"]
            )

            if exchange_type == "Sell":
                price = st.number_input(
                    "Price (₹)", min_value=0.0, value=50.0,
                    step=10.0
                )
            else:
                price = 0.0
                st.caption("Price will be set to ₹0 for this option.")

            description = st.text_area(
                "Description",
                placeholder="Describe the item honestly..."
            )

            generate = st.form_submit_button(
                "✨ Suggest Description with AI"
            )

            submit = st.form_submit_button("Publish Item")

        if generate:
            if title:
                st.session_state["suggested_description"] = (
                    create_description(title, category, condition)
                )
                st.info(
                    "Suggested description: "
                    + st.session_state["suggested_description"]
                )
                st.caption(
                    "Copy the suggestion into the Description field "
                    "before publishing."
                )
            else:
                st.warning("Enter the item name first.")

        if submit:
            if not title.strip():
                st.error("Please enter an item name.")
            else:
                add_item(
                    student_name, title.strip(), category,
                    description.strip(), price, exchange_type, condition
                )
                st.success("Your item has been published!")
                st.rerun()

# ---------------- BROWSE ITEMS ----------------

elif page == "Browse Items":
    st.title("🔎 Browse Campus Items")

    items = get_items()

    if not items:
        st.info("No items listed yet. Be the first to add an item!")
    else:
        search = st.text_input("Search by item name or keyword")

        categories = sorted(set(item[3] for item in items))
        selected_category = st.selectbox(
            "Filter by category",
            ["All"] + categories
        )

        types = sorted(set(item[6] for item in items))
        selected_type = st.selectbox(
            "Filter by exchange type",
            ["All"] + types
        )

        filtered = []

        for item in items:
            matches_search = (
                search.lower() in (
                    str(item[2]) + " " + str(item[4])
                ).lower()
            )
            matches_category = (
                selected_category == "All"
                or item[3] == selected_category
            )
            matches_type = (
                selected_type == "All"
                or item[6] == selected_type
            )

            if matches_search and matches_category and matches_type:
                filtered.append(item)

        st.write(f"Found {len(filtered)} item(s).")

        for item in filtered:
            with st.container(border=True):
                st.subheader(item[2])
                st.caption(
                    f"Item ID: {item[0]} | Posted by: {item[1]}"
                )

                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Category:** {item[3]}")
                    st.write(f"**Condition:** {item[7]}")
                    st.write(f"**Type:** {item[6]}")

                with col2:
                    st.write(f"**Price:** ₹{item[5]:.2f}")
                    st.write(f"**Description:** {item[4] or 'Not provided'}")

                if student_name and student_name == item[1]:
                    st.caption("This is your listing.")
                elif student_name:
                    with st.form(f"request_{item[0]}"):
                        message = st.text_input(
                            "Message to the student",
                            placeholder="I am interested in this item."
                        )

                        request_button = st.form_submit_button(
                            "Send Exchange Request"
                        )

                        if request_button:
                            send_request(
                                item[0], student_name,
                                message.strip()
                            )
                            st.success("Request sent!")
                            st.rerun()
                else:
                    st.caption(
                        "Enter your name in the sidebar to request an item."
                    )

# ---------------- MY REQUESTS ----------------

elif page == "My Requests":
    st.title("📩 Exchange Requests")

    if not student_name:
        st.warning("Enter your name in the sidebar first.")
    else:
        requests = get_requests()

        incoming = [
            r for r in requests if r[3] == student_name
        ]
        outgoing = [
            r for r in requests if r[4] == student_name
        ]

        st.subheader("Requests for My Items")

        if not incoming:
            st.info("You have no incoming requests.")
        else:
            for r in incoming:
                with st.container(border=True):
                    st.write(f"**Item:** {r[2]} (ID {r[1]})")
                    st.write(f"**Requested by:** {r[4]}")
                    st.write(f"**Message:** {r[5] or 'No message'}")
                    st.write(f"**Status:** {r[6]}")

                    if r[6] == "Pending":
                        col1, col2 = st.columns(2)

                        if col1.button(
                            "Accept",
                            key=f"accept_{r[0]}"
                        ):
                            update_request(r[0], "Accepted")
                            st.rerun()

                        if col2.button(
                            "Reject",
                            key=f"reject_{r[0]}"
                        ):
                            update_request(r[0], "Rejected")
                            st.rerun()

                    elif r[6] == "Accepted":
                        if st.button(
                            "Mark as Completed",
                            key=f"complete_{r[0]}"
                        ):
                            update_request(r[0], "Completed")
                            st.rerun()

        st.subheader("Requests I Sent")

        if not outgoing:
            st.info("You have not sent any requests.")
        else:
            for r in outgoing:
                st.write(
                    f"- **{r[2]}** — Owner: {r[3]} — "
                    f"Status: {r[6]}"
                )

# ---------------- AI ASSISTANT ----------------

elif page == "AI Assistant":
    st.title("🤖 Campus Exchange Assistant")

    st.write(
        "Tell me what you need, and I will help you look "
        "through the current campus listings."
    )

    st.caption(
        "For genuine language-model responses, install Ollama "
        "and download the Gemma 3 1B model. Otherwise, keyword "
        "matching is used as a fallback."
    )

    user_need = st.text_input(
        "What are you looking for?",
        placeholder="Example: I need a Python textbook"
    )

    if st.button("Find Recommendations"):
        if user_need.strip():
            with st.spinner("Checking available listings..."):
                answer = recommend_items(user_need, get_items())
            st.markdown(answer)
        else:
            st.warning("Please describe what you need.")

    st.divider()
    st.subheader("Other things you can ask")

    st.write("- Help me find engineering textbooks.")
    st.write("- Find stationery available for donation.")
    st.write("- Help me write a description for a used calculator.")

# ---------------- DASHBOARD ----------------

elif page == "Dashboard":
    st.title("📊 Campus Exchange Dashboard")

    items = get_items()
    requests = get_requests()

    total_items = len(items)
    total_requests = len(requests)
    completed = sum(1 for r in requests if r[6] == "Completed")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Listings", total_items)
    col2.metric("Total Requests", total_requests)
    col3.metric("Completed Exchanges", completed)

    st.subheader("Items by Category")

    if items:
        category_counts = {}

        for item in items:
            category_counts[item[3]] = (
                category_counts.get(item[3], 0) + 1
            )

        st.bar_chart(category_counts)
    else:
        st.info("Add items to see marketplace statistics.")

    st.subheader("Recent Listings")

    for item in items[:5]:
        st.write(
            f"- {item[2]} | {item[3]} | "
            f"{item[6]} | ₹{item[5]:.2f}"
        )

    st.caption(
        "This is a prototype dashboard. Listings and requests "
        "are stored locally in SQLite."
    )
