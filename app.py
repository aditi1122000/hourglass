"""Hourglass - a tiny time-logging + productivity-reward Streamlit app."""

from datetime import date, timedelta

import streamlit as st

import auth
import db
import rewards

st.set_page_config(page_title="Hourglass", page_icon="⏳", layout="centered")


def show_logo(width=60):
    with open("assets/logo.svg") as f:
        svg = f.read()
    st.markdown(
        f'<div style="text-align:center">{svg.replace("width=\"100\" height=\"140\"", f"width=\"{width}\"")}</div>',
        unsafe_allow_html=True,
    )


def login_screen():
    show_logo(width=90)
    st.markdown("<h1 style='text-align:center'>Hourglass</h1>", unsafe_allow_html=True)
    st.caption("Log your time. Earn tokens. Grow a tree.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in / Sign up")

    if submitted:
        username = username.strip()
        if not username or not password:
            st.error("Please enter a username and password.")
            return

        existing = db.get_user_by_username(username)
        if existing is None:
            user = db.create_user(username, auth.hash_password(password))
            st.session_state["user"] = {"id": user["id"], "username": user["username"]}
            st.rerun()
        elif auth.verify_password(password, existing["password_hash"]):
            st.session_state["user"] = {"id": existing["id"], "username": existing["username"]}
            st.rerun()
        else:
            st.error("Incorrect password.")


def award_token_if_earned(user_id, log_date):
    logs = db.get_logs_for_date(user_id, log_date)
    day_logs = [
        {"hours": float(l["hours"]), "is_productive": bool(l["categories"]["is_productive"])}
        for l in logs
    ]
    total_hours, productive_hours, _ = rewards.compute_productivity(day_logs)
    already_awarded = db.get_token_for_date(user_id, log_date) is not None
    if rewards.should_award_token(total_hours, productive_hours, already_awarded):
        db.award_token(user_id, log_date)
        st.toast("You earned a token for hitting the 35% productivity threshold!", icon="\U0001FA99")


def logging_page(user_id):
    categories = db.get_categories(user_id)

    with st.expander("+ Add a new category"):
        with st.form("new_category_form", clear_on_submit=True):
            name = st.text_input("Category name")
            description = st.text_input("Description (optional)")
            is_productive = st.checkbox("Counts as productive?")
            if st.form_submit_button("Add category"):
                if name.strip():
                    db.create_category(user_id, name.strip(), description.strip(), is_productive)
                    st.rerun()
                else:
                    st.error("Category name is required.")

    if not categories:
        st.info("Add a category above to start logging time.")
        return

    category_names = [c["name"] for c in categories]
    selected_category_name = st.selectbox("Category", category_names, key="selected_category")
    selected_category = next(c for c in categories if c["name"] == selected_category_name)

    with st.expander(f"+ Add a sub-category to {selected_category_name}"):
        with st.form("new_subcategory_form", clear_on_submit=True):
            sub_name = st.text_input("Sub-category name")
            sub_description = st.text_input("Sub-category description (optional)")
            if st.form_submit_button("Add sub-category"):
                if sub_name.strip():
                    db.create_sub_category(selected_category["id"], sub_name.strip(), sub_description.strip())
                    st.rerun()
                else:
                    st.error("Sub-category name is required.")

    sub_categories = db.get_sub_categories(selected_category["id"])
    sub_options = ["None"] + [s["name"] for s in sub_categories]
    selected_sub_name = st.selectbox("Sub-category (optional)", sub_options)
    selected_sub = next((s for s in sub_categories if s["name"] == selected_sub_name), None)

    with st.form("log_form", clear_on_submit=True):
        log_date = st.date_input("Date", value=date.today())
        hours = st.number_input("Hours", min_value=0.0, step=0.5, format="%.2f")
        note = st.text_input("Note (optional)")
        if st.form_submit_button("Log time"):
            if hours <= 0:
                st.error("Hours must be greater than 0.")
            else:
                db.create_log(
                    user_id,
                    selected_category["id"],
                    selected_sub["id"] if selected_sub else None,
                    log_date,
                    hours,
                    note.strip() or None,
                )
                award_token_if_earned(user_id, log_date)
                st.rerun()

    st.divider()
    st.subheader("Today's productivity")
    today_logs = db.get_logs_for_date(user_id, date.today())
    today_pure = [
        {"hours": float(l["hours"]), "is_productive": bool(l["categories"]["is_productive"])}
        for l in today_logs
    ]
    total_hours, productive_hours, pct = rewards.compute_productivity(today_pure)
    st.write(f"Productive: **{productive_hours:.2f}h** / Total: **{total_hours:.2f}h** ({pct * 100:.0f}%)")
    st.progress(min(pct / rewards.PRODUCTIVITY_THRESHOLD, 1.0))
    st.caption(f"Threshold to earn a token today: {rewards.PRODUCTIVITY_THRESHOLD * 100:.0f}%")

    token_balance = db.get_unredeemed_token_count(user_id)
    st.metric("Unredeemed tokens", token_balance)

    st.divider()
    st.subheader("History")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=6), key="history_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="history_end")

    history = db.get_logs_for_range(user_id, start_date, end_date)
    if history:
        rows = [
            {
                "Date": h["log_date"],
                "Category": h["categories"]["name"] if h.get("categories") else "",
                "Sub-category": h["sub_categories"]["name"] if h.get("sub_categories") else "",
                "Hours": h["hours"],
                "Note": h.get("note") or "",
            }
            for h in history
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No logs in this date range yet.")


def redeem_page(user_id):
    token_balance = db.get_unredeemed_token_count(user_id)
    redemption_count = db.get_redemption_count(user_id)
    stage = rewards.tree_stage_from_redemptions(redemption_count)
    emoji = rewards.tree_emoji_from_redemptions(redemption_count)

    st.subheader("Your tree")
    st.markdown(f"<div style='font-size:96px;text-align:center'>{emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>Stage: <b>{stage}</b></p>", unsafe_allow_html=True)

    st.metric("Unredeemed tokens", token_balance)

    if token_balance > 0:
        if st.button("Redeem 1 token \U0001FA99"):
            token = db.get_unredeemed_tokens(user_id)[0]
            db.redeem_token(user_id, token["id"])
            st.rerun()
    else:
        st.caption("Earn a token by hitting the 35% productivity threshold on a day you log time.")


def main():
    if "user" not in st.session_state:
        login_screen()
        return

    user = st.session_state["user"]

    with st.sidebar:
        show_logo(width=60)
        st.markdown(f"**{user['username']}**")
        page = st.radio("Navigate", ["Log Time", "Redeem"])
        if st.button("Log out"):
            del st.session_state["user"]
            st.rerun()

    st.title("Hourglass")

    if page == "Log Time":
        logging_page(user["id"])
    else:
        redeem_page(user["id"])


if __name__ == "__main__":
    main()
