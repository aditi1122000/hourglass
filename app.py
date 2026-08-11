"""Hourglass - a tiny time-logging + productivity-reward Streamlit app."""

import random
from datetime import date, timedelta

import altair as alt
import streamlit as st

import auth
import db
import insights
import rewards

st.set_page_config(page_title="Hourglass", page_icon="⏳", layout="centered")

# Brand palette, lifted straight from assets/logo.svg.
BRAND_INDIGO = "#2E2A5C"
BRAND_AMBER = "#F2B94D"
BRAND_ACCENT = "#E4572E"
BRAND_GRAY = "#9a9a95"

# Validated categorical hues (fixed order -- never cycled), used for the
# hours-by-category chart. Slots 7/2/4 already echo the brand's
# indigo/orange/amber, so no separate brand re-derivation was needed.
CATEGORY_PALETTE = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]

SPINNER_MESSAGES = [
    "Sharpening pencils...",
    "Convincing the tree to grow faster...",
    "Counting productive minutes...",
    "Untangling the hourglass sand...",
    "Bribing the productivity gremlins...",
    "Consulting the sundial...",
    "Watering yesterday's effort...",
    "Filing hours into neat little piles...",
    "Polishing today's timeline...",
    "Waking up the token vault...",
    "Doing the math so you don't have to...",
    "Nudging the sand grains along...",
    "Reticulating splines (productively)...",
    "Checking in with your inner squirrel...",
]

CELEBRATION_MESSAGES = [
    "Token earned! Your tree just felt that.",
    "35%+ productive -- nicely done. Token unlocked!",
    "Hourglass approves. One token, freshly minted.",
]


def spin(message=None):
    return st.spinner(message or random.choice(SPINNER_MESSAGES))


def inject_css():
    st.markdown(
        f"""
        <style>
        .stat-card {{
            background: #ffffff08;
            border: 1px solid #80808022;
            border-left: 4px solid {BRAND_INDIGO};
            border-radius: 8px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
        }}
        .stat-card .stat-label {{
            font-size: 0.8rem;
            opacity: 0.7;
            margin-bottom: 0.15rem;
        }}
        .stat-card .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def stat_card(col, label, value, icon=""):
    with col:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">{icon} {label}</div>
                <div class="stat-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_logo(width=60):
    with open("assets/logo.svg") as f:
        svg = f.read()
    st.markdown(
        f'<div style="text-align:center">{svg.replace("width=\"100\" height=\"140\"", f"width=\"{width}\"")}</div>',
        unsafe_allow_html=True,
    )


def login_screen():
    show_logo(width=90)
    st.markdown(
        f"<h1 style='text-align:center;color:{BRAND_INDIGO}'>Hourglass ⏳</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Log your hours. Cross the 35% productive line. Grow a tree. Repeat. 🌱")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("✨ Log in / Sign up")

    if submitted:
        username = username.strip()
        if not username or not password:
            st.error("A username and password are both required to get started.")
            return

        with spin():
            existing = db.get_user_by_username(username)
            if existing is None:
                user = db.create_user(username, auth.hash_password(password))
                st.session_state["user"] = {"id": user["id"], "username": user["username"]}
                st.rerun()
            elif auth.verify_password(password, existing["password_hash"]):
                st.session_state["user"] = {"id": existing["id"], "username": existing["username"]}
                st.rerun()
            else:
                st.error("That password doesn't match this username. Try again?")


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
        return True
    return False


def logging_page(user_id):
    if st.session_state.pop("celebrate_token", False):
        st.balloons()
        st.success(random.choice(CELEBRATION_MESSAGES), icon="\U0001FA99")

    categories = db.get_categories(user_id)

    with st.expander("➕ Add a new category"):
        with st.form("new_category_form", clear_on_submit=True):
            name = st.text_input("Category name")
            description = st.text_input("Description (optional)")
            is_productive = st.checkbox("Counts as productive?")
            if st.form_submit_button("Add category"):
                if name.strip():
                    with spin():
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

    with st.expander(f"➕ Add a sub-category to {selected_category_name}"):
        with st.form("new_subcategory_form", clear_on_submit=True):
            sub_name = st.text_input("Sub-category name")
            sub_description = st.text_input("Sub-category description (optional)")
            if st.form_submit_button("Add sub-category"):
                if sub_name.strip():
                    with spin():
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
        if st.form_submit_button("📝 Log time"):
            if hours <= 0:
                st.error("Hours must be greater than 0.")
            else:
                with spin():
                    db.create_log(
                        user_id,
                        selected_category["id"],
                        selected_sub["id"] if selected_sub else None,
                        log_date,
                        hours,
                        note.strip() or None,
                    )
                    awarded = award_token_if_earned(user_id, log_date)
                if awarded:
                    st.session_state["celebrate_token"] = True
                st.rerun()

    st.divider()
    st.subheader("🔥 Today's productivity")
    today_logs = db.get_logs_for_date(user_id, date.today())
    today_pure = [
        {"hours": float(l["hours"]), "is_productive": bool(l["categories"]["is_productive"])}
        for l in today_logs
    ]
    total_hours, productive_hours, pct = rewards.compute_productivity(today_pure)
    st.write(f"Productive: **{productive_hours:.2f}h** / Total: **{total_hours:.2f}h** ({pct * 100:.0f}%)")
    st.progress(min(pct / rewards.PRODUCTIVITY_THRESHOLD, 1.0))
    st.caption(f"Cross {rewards.PRODUCTIVITY_THRESHOLD * 100:.0f}% today to earn a token.")

    token_balance = db.get_unredeemed_token_count(user_id)
    st.metric("🎟️ Unredeemed tokens", token_balance)

    st.divider()
    st.subheader("📜 History")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=6), key="history_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="history_end")

    with spin():
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
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("No logs in this date range yet. Time to make some history! ⏳")


def _category_color_map(categories):
    """Stable name -> hex mapping by creation order, so a category's color
    never changes just because the selected date range changes what's
    present in a given chart."""
    ordered = sorted(categories, key=lambda c: c["created_at"])
    color_map = {}
    for i, cat in enumerate(ordered):
        if i < len(CATEGORY_PALETTE):
            color_map[cat["name"]] = CATEGORY_PALETTE[i]
    return color_map


def insights_page(user_id):
    st.subheader("📊 Insights")

    with spin("Counting productive minutes..."):
        all_logs_raw = db.get_all_logs(user_id)
    total_hours_all_time = sum(float(l["hours"]) for l in all_logs_raw)
    total_tokens_all_time = db.get_total_token_count(user_id)
    redemption_count = db.get_redemption_count(user_id)
    tree_stage = rewards.tree_stage_from_redemptions(redemption_count)
    tree_emoji = rewards.tree_emoji_from_redemptions(redemption_count)

    daily_pure = [
        {
            "log_date": date.fromisoformat(l["log_date"]) if isinstance(l["log_date"], str) else l["log_date"],
            "hours": float(l["hours"]),
            "is_productive": bool(l["categories"]["is_productive"]),
        }
        for l in all_logs_raw
    ]
    daily_rows = insights.daily_productive_series(daily_pure)
    if daily_rows:
        streak_start = min(r["log_date"] for r in daily_rows)
        flags = insights.build_daily_threshold_flags(daily_rows, streak_start, date.today())
        streak = insights.current_streak(flags)
    else:
        streak = 0

    inject_css()
    c1, c2, c3, c4 = st.columns(4)
    stat_card(c1, "Total hours logged", f"{total_hours_all_time:.1f}h", "⏳")
    stat_card(c2, "Tokens earned", total_tokens_all_time, "🎟️")
    stat_card(c3, f"Tree: {tree_stage}", tree_emoji, "🌳")
    stat_card(c4, "Day streak (35%+)", streak, "🔥")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=13), key="insights_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="insights_end")

    with spin("Sorting hours into neat little piles..."):
        ranged_logs = db.get_logs_for_range(user_id, start_date, end_date)

    if not ranged_logs:
        st.caption("No logs in this date range yet -- log some time to see charts here.")
        return

    show_sub = st.checkbox("Break down by sub-category")
    categories = db.get_categories(user_id)
    color_map = _category_color_map(categories)

    def group_label(l):
        if show_sub and l.get("sub_categories"):
            return f"{l['categories']['name']} / {l['sub_categories']['name']}"
        return l["categories"]["name"] if l.get("categories") else "Unknown"

    bar_rows = [
        {"log_date": l["log_date"], "group": group_label(l), "hours": float(l["hours"])}
        for l in ranged_logs
    ]
    bar_rows = insights.fold_to_top_groups(bar_rows, "group")

    present_groups = {r["group"] for r in bar_rows}
    ordered_names = [name for name in color_map if name in present_groups]
    domain, range_ = [], []
    for name in ordered_names:
        domain.append(name)
        range_.append(color_map[name])
    if insights.OTHER_LABEL in present_groups or show_sub:
        # Sub-category labels ("Category / Sub") aren't in color_map -- fall
        # back to the palette by position for anything not directly mapped.
        for group in sorted(present_groups - set(domain)):
            domain.append(group)
            range_.append(BRAND_GRAY if group == insights.OTHER_LABEL else CATEGORY_PALETTE[len(domain) % len(CATEGORY_PALETTE)])

    st.markdown("**Hours by category**" + (" / sub-category" if show_sub else ""))
    bar_chart = (
        alt.Chart(alt.Data(values=bar_rows))
        .mark_bar(cornerRadius=2)
        .encode(
            x=alt.X("log_date:T", title="Date"),
            y=alt.Y("hours:Q", title="Hours", stack="zero"),
            color=alt.Color("group:N", title="Category", scale=alt.Scale(domain=domain, range=range_)),
            tooltip=["log_date:T", "group:N", "hours:Q"],
        )
        .properties(height=280)
    )
    st.altair_chart(bar_chart, width="stretch")

    st.markdown("**Daily productive %**")
    pct_rows = [
        {"log_date": str(r["log_date"]), "pct": r["pct"] * 100}
        for r in daily_rows
        if start_date <= r["log_date"] <= end_date
    ]
    threshold_pct = rewards.PRODUCTIVITY_THRESHOLD * 100
    line = (
        alt.Chart(alt.Data(values=pct_rows))
        .mark_line(point=True, strokeWidth=2, color=BRAND_INDIGO)
        .encode(
            x=alt.X("log_date:T", title="Date"),
            y=alt.Y("pct:Q", title="Productive %", scale=alt.Scale(domain=[0, 100])),
            tooltip=["log_date:T", "pct:Q"],
        )
    )
    threshold_rule = (
        alt.Chart(alt.Data(values=[{"threshold": threshold_pct}]))
        .mark_rule(color=BRAND_ACCENT, strokeDash=[6, 4], strokeWidth=2)
        .encode(y="threshold:Q")
    )
    st.altair_chart((line + threshold_rule).properties(height=280), width="stretch")
    st.caption(f"Dashed line marks the {threshold_pct:.0f}% productive threshold that earns a token.")


def redeem_page(user_id):
    token_balance = db.get_unredeemed_token_count(user_id)
    redemption_count = db.get_redemption_count(user_id)
    stage = rewards.tree_stage_from_redemptions(redemption_count)
    emoji = rewards.tree_emoji_from_redemptions(redemption_count)

    st.subheader("🎁 Your tree")
    st.markdown(f"<div style='font-size:96px;text-align:center'>{emoji}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='text-align:center'>Stage: <b style='color:{BRAND_INDIGO}'>{stage}</b></p>",
        unsafe_allow_html=True,
    )

    st.metric("🎟️ Unredeemed tokens", token_balance)

    if token_balance > 0:
        if st.button("Redeem 1 token \U0001FA99"):
            with spin("Convincing the tree to grow faster..."):
                token = db.get_unredeemed_tokens(user_id)[0]
                db.redeem_token(user_id, token["id"])
            st.rerun()
    else:
        st.caption("Earn a token by hitting the 35% productivity threshold on a day you log time. 🌱")


def main():
    inject_css()

    if "user" not in st.session_state:
        login_screen()
        return

    user = st.session_state["user"]

    with st.sidebar:
        show_logo(width=60)
        st.markdown(f"**{user['username']}**")
        page = st.radio("Navigate", ["📝 Log Time", "📊 Insights", "🎁 Redeem"])
        if st.button("Log out"):
            del st.session_state["user"]
            st.rerun()

    st.markdown(f"<h1 style='color:{BRAND_INDIGO}'>Hourglass ⏳</h1>", unsafe_allow_html=True)

    if page == "📝 Log Time":
        logging_page(user["id"])
    elif page == "📊 Insights":
        insights_page(user["id"])
    else:
        redeem_page(user["id"])


if __name__ == "__main__":
    main()
