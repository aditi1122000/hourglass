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
            height: 100%;
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
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] {{
            background-color: {BRAND_INDIGO};
            border-color: {BRAND_INDIGO};
        }}
        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
            background-color: {BRAND_ACCENT};
            border-color: {BRAND_ACCENT};
            color: white;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 1.75rem;
        }}
        .stTabs [aria-selected="true"] {{
            color: {BRAND_INDIGO};
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
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        show_logo(width=72)
        st.markdown(
            f"<h2 style='text-align:center;color:{BRAND_INDIGO};margin-bottom:0'>Hourglass ⏳</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;opacity:0.7;margin-top:0.25rem'>"
            "Log hours, cross 35% productive, grow a tree. 🌱</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "✨ Log in / Sign up", type="primary", width="stretch"
            )

        if submitted:
            username = username.strip()
            if not username or not password:
                st.warning("A username and password are both required to get started.", icon="🙈")
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
                    st.warning("That password doesn't match this username. Try again?", icon="🔒")


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


def _new_category_form(user_id):
    with st.form("new_category_form", clear_on_submit=True):
        name = st.text_input("Category name")
        description = st.text_input("Description (optional)")
        is_productive = st.checkbox("Counts as productive?")
        if st.form_submit_button("Add category", type="primary"):
            if name.strip():
                with spin():
                    db.create_category(user_id, name.strip(), description.strip(), is_productive)
                st.rerun()
            else:
                st.warning("Category name is required.", icon="🙈")


def _new_sub_category_form(category):
    with st.form("new_subcategory_form", clear_on_submit=True):
        sub_name = st.text_input("Sub-category name")
        sub_description = st.text_input("Sub-category description (optional)")
        if st.form_submit_button("Add sub-category", type="primary"):
            if sub_name.strip():
                with spin():
                    db.create_sub_category(category["id"], sub_name.strip(), sub_description.strip())
                st.rerun()
            else:
                st.warning("Sub-category name is required.", icon="🙈")


def logging_page(user_id):
    if st.session_state.pop("celebrate_token", False):
        st.balloons()
        st.success(random.choice(CELEBRATION_MESSAGES), icon="\U0001FA99")

    categories = db.get_categories(user_id)

    if not categories:
        st.info("Add a category to start logging time.")
        with st.popover("➕ Add a category"):
            _new_category_form(user_id)
        return

    category_names = [c["name"] for c in categories]
    cat_col, cat_add_col, sub_col, sub_add_col = st.columns([3, 1, 3, 1])
    with cat_col:
        selected_category_name = st.selectbox("Category", category_names, key="selected_category")
    selected_category = next(c for c in categories if c["name"] == selected_category_name)
    with cat_add_col:
        st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
        with st.popover("➕", help="Add a new category"):
            _new_category_form(user_id)

    sub_categories = db.get_sub_categories(selected_category["id"])
    sub_options = ["None"] + [s["name"] for s in sub_categories]
    with sub_col:
        selected_sub_name = st.selectbox("Sub-category", sub_options)
    selected_sub = next((s for s in sub_categories if s["name"] == selected_sub_name), None)
    with sub_add_col:
        st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
        with st.popover("➕", help=f"Add a sub-category to {selected_category_name}"):
            _new_sub_category_form(selected_category)

    with st.form("log_form", clear_on_submit=True):
        d_col, h_col, n_col = st.columns([2, 1, 3])
        with d_col:
            log_date = st.date_input("Date", value=date.today())
        with h_col:
            hours = st.number_input("Hours", min_value=0.0, step=0.5, format="%.2f")
        with n_col:
            note = st.text_input("Note (optional)")
        submitted = st.form_submit_button("📝 Log time", type="primary", width="stretch")
        if submitted:
            if hours <= 0:
                st.warning("Hours must be greater than 0.", icon="🙈")
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

    today_logs = db.get_logs_for_date(user_id, date.today())
    today_pure = [
        {"hours": float(l["hours"]), "is_productive": bool(l["categories"]["is_productive"])}
        for l in today_logs
    ]
    total_hours, productive_hours, pct = rewards.compute_productivity(today_pure)
    token_balance = db.get_unredeemed_token_count(user_id)

    with st.container(border=True):
        pcol, mcol = st.columns([3, 1])
        with pcol:
            st.caption(
                f"🔥 Today: **{productive_hours:.2f}h** productive / **{total_hours:.2f}h** logged "
                f"-- cross {rewards.PRODUCTIVITY_THRESHOLD * 100:.0f}% to earn a token"
            )
            st.progress(min(pct / rewards.PRODUCTIVITY_THRESHOLD, 1.0))
        with mcol:
            st.metric("🎟️ Tokens", token_balance)

    with st.expander("📜 History"):
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

    st.write("")
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=13), key="insights_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="insights_end")
    with col3:
        st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        show_sub = st.checkbox("By sub-category")

    with spin("Sorting hours into neat little piles..."):
        ranged_logs = db.get_logs_for_range(user_id, start_date, end_date)

    if not ranged_logs:
        st.caption("No logs in this date range yet -- log some time to see charts here.")
        return

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

    bar_title = "Hours by category" + (" / sub-category" if show_sub else "")
    bar_chart = (
        alt.Chart(alt.Data(values=bar_rows))
        .mark_bar(cornerRadius=2)
        .encode(
            x=alt.X("log_date:T", title="Date"),
            y=alt.Y("hours:Q", title="Hours", stack="zero"),
            color=alt.Color("group:N", title="Category", scale=alt.Scale(domain=domain, range=range_)),
            tooltip=["log_date:T", "group:N", "hours:Q"],
        )
        .properties(height=280, title=bar_title)
    )
    st.altair_chart(bar_chart, width="stretch")

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
    st.altair_chart(
        (line + threshold_rule).properties(height=280, title="Daily productive %"),
        width="stretch",
    )
    st.caption(f"Dashed line marks the {threshold_pct:.0f}% productive threshold that earns a token.")


def redeem_page(user_id):
    token_balance = db.get_unredeemed_token_count(user_id)
    redemption_count = db.get_redemption_count(user_id)
    stage = rewards.tree_stage_from_redemptions(redemption_count)
    emoji = rewards.tree_emoji_from_redemptions(redemption_count)

    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:140px;text-align:center;line-height:1.15'>{emoji}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;font-size:1.1rem;margin-bottom:1rem'>"
            f"Stage: <b style='color:{BRAND_INDIGO}'>{stage}</b></p>",
            unsafe_allow_html=True,
        )

        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            if token_balance > 0:
                if st.button("Redeem 1 token \U0001FA99", type="primary", width="stretch"):
                    with spin("Convincing the tree to grow faster..."):
                        token = db.get_unredeemed_tokens(user_id)[0]
                        db.redeem_token(user_id, token["id"])
                    st.rerun()
            else:
                st.caption(
                    "Earn a token by hitting the 35% productivity threshold "
                    "on a day you log time. 🌱"
                )

        plural = "s" if token_balance != 1 else ""
        st.markdown(
            f"<p style='text-align:center;opacity:0.7;margin-top:0.75rem'>"
            f"🎟️ {token_balance} unredeemed token{plural}</p>",
            unsafe_allow_html=True,
        )


def main():
    inject_css()

    if "user" not in st.session_state:
        login_screen()
        return

    user = st.session_state["user"]

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.markdown(
            f"<h2 style='color:{BRAND_INDIGO};margin-bottom:0'>⏳ Hourglass</h2>",
            unsafe_allow_html=True,
        )
    with header_right:
        st.markdown(
            f"<p style='text-align:right;opacity:0.7;margin-bottom:0.25rem'>{user['username']}</p>",
            unsafe_allow_html=True,
        )
        if st.button("Log out", width="stretch"):
            del st.session_state["user"]
            st.rerun()

    tab_log, tab_insights, tab_redeem = st.tabs(["📝 Log Time", "📊 Insights", "🎁 Redeem"])
    with tab_log:
        logging_page(user["id"])
    with tab_insights:
        insights_page(user["id"])
    with tab_redeem:
        redeem_page(user["id"])


if __name__ == "__main__":
    main()
