"""Hourglass - a tiny time-logging + productivity-reward Streamlit app."""

import random
from datetime import date, timedelta

import altair as alt
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

import auth
import db
import insights
import rewards

st.set_page_config(page_title="Hourglass", page_icon="⏳", layout="centered")

# Brand palette, lifted straight from assets/logo.svg. primaryColor/textColor
# in .streamlit/config.toml already carry BRAND_INDIGO app-wide -- these
# constants stay only for the places native theming can't reach: Altair
# chart color scales and the tree/flame accent markup below.
BRAND_INDIGO = "#2E2A5C"
BRAND_AMBER = "#F2B94D"
BRAND_ACCENT = "#E4572E"
BRAND_GRAY = "#9a9a95"

# 8px-grid spacing scale, used wherever a manual layout nudge is unavoidable
# (e.g. vertically aligning a button next to a selectbox).
SPACE_XS = "0.5rem"   # 8px
SPACE_SM = "1rem"     # 16px
SPACE_MD = "1.5rem"   # 24px
SPACE_LG = "2rem"     # 32px

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
    # Colors, button styling, and the active-tab indicator now all come from
    # .streamlit/config.toml's [theme] block. Only layout the theme can't
    # express -- text sizing/spacing for two custom markup rows -- stays here.
    st.markdown(
        f"""
        <style>
        .takeaway-line {{
            font-size: 1.02rem;
            margin: 0.25rem 0 0.75rem 0;
        }}
        .forest-row {{
            font-size: 2.2rem;
            line-height: 1.5;
            letter-spacing: 0.1rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: {SPACE_MD};
        }}
        </style>
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
            "<h2 style='text-align:center;margin-bottom:0'>Hourglass ⏳</h2>",
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


def today_page(user_id):
    if st.session_state.pop("celebrate_token", False):
        st.balloons()
        st.success(random.choice(CELEBRATION_MESSAGES), icon="\U0001FA99")

    token_balance = db.get_unredeemed_token_count(user_id)

    today_logs = db.get_logs_for_date(user_id, date.today())
    today_pure = [
        {"hours": float(l["hours"]), "is_productive": bool(l["categories"]["is_productive"])}
        for l in today_logs
    ]
    total_hours, productive_hours, pct = rewards.compute_productivity(today_pure)

    # Hero first: where you stand today, before anything else asks for input.
    st.caption(date.today().strftime("%A, %B %-d"))
    hcol1, hcol2 = st.columns(2)
    with hcol1:
        st.metric("Productive today", f"{pct * 100:.0f}%", border=True)
    with hcol2:
        st.metric("🎟️ Tokens", token_balance, border=True)
    st.caption(
        f"**{productive_hours:.2f}h** productive / **{total_hours:.2f}h** logged "
        f"-- cross {rewards.PRODUCTIVITY_THRESHOLD * 100:.0f}% to earn a token"
    )
    st.progress(min(pct / rewards.PRODUCTIVITY_THRESHOLD, 1.0))

    if token_balance > 0:
        plural = "s" if token_balance != 1 else ""
        st.info(
            f"🎁 You have {token_balance} token{plural} waiting -- "
            f"switch to **Redeem** above to grow your tree!",
            icon="🎁",
        )

    st.write("")
    categories = db.get_categories(user_id)

    if not categories:
        st.info("Add a category to start logging time.")
        with st.popover("➕ Add a category"):
            _new_category_form(user_id)
        return

    # The one primary action on this screen: log time.
    with st.container(border=True):
        category_names = [c["name"] for c in categories]
        cat_col, cat_add_col, sub_col, sub_add_col = st.columns([3, 1, 3, 1])
        with cat_col:
            selected_category_name = st.selectbox("Category", category_names, key="selected_category")
        selected_category = next(c for c in categories if c["name"] == selected_category_name)
        with cat_add_col:
            st.markdown(f"<div style='height:{SPACE_MD}'></div>", unsafe_allow_html=True)
            with st.popover("➕", help="Add a new category"):
                _new_category_form(user_id)

        sub_categories = db.get_sub_categories(selected_category["id"])
        sub_options = ["None"] + [s["name"] for s in sub_categories]
        with sub_col:
            selected_sub_name = st.selectbox("Sub-category", sub_options)
        selected_sub = next((s for s in sub_categories if s["name"] == selected_sub_name), None)
        with sub_add_col:
            st.markdown(f"<div style='height:{SPACE_MD}'></div>", unsafe_allow_html=True)
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

    st.write("")
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
    past_trees, _current_stage, _current_emoji = rewards.forest_history(redemption_count)

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
    with c1:
        st.metric("Day streak", f"{streak}d {insights.streak_flame(streak)}", border=True)
    with c2:
        st.metric("Total hours logged", f"{total_hours_all_time:.1f}h", icon="⏳", border=True)
    with c3:
        st.metric("Tokens earned", total_tokens_all_time, icon="🎟️", border=True)
    with c4:
        st.metric("Trees grown", len(past_trees), icon="🌲", border=True)

    st.write("")
    heatmap_end = date.today()
    raw_start = heatmap_end - timedelta(days=83)  # ~12 weeks, GitHub-style window
    heatmap_start = raw_start - timedelta(days=(raw_start.weekday() + 1) % 7)  # snap back to a Sunday
    heatmap_rows = insights.build_calendar_heatmap_rows(daily_rows, heatmap_start, heatmap_end)
    heatmap_data = [
        {
            "date": str(r["date"]),
            "week_start": str(r["week_start"]),
            "weekday_label": r["weekday_label"],
            "status": r["status"],
            "pct_label": f"{r['pct'] * 100:.0f}%" if r["pct"] is not None else "No data",
        }
        for r in heatmap_rows
    ]
    status_colors = {"met": "#1baf7a", "missed": "#e8d4d0", "no_data": "#e9e9e6"}
    heatmap_chart = (
        alt.Chart(alt.Data(values=heatmap_data))
        .mark_rect(cornerRadius=2, stroke="white", strokeWidth=2)
        .encode(
            x=alt.X("week_start:O", title=None, axis=alt.Axis(labelAngle=-45, labelFontSize=9)),
            y=alt.Y("weekday_label:N", title=None, sort=insights.CALENDAR_WEEKDAY_ORDER),
            color=alt.Color(
                "status:N",
                title=None,
                scale=alt.Scale(
                    domain=["met", "missed", "no_data"],
                    range=[status_colors["met"], status_colors["missed"], status_colors["no_data"]],
                ),
                legend=alt.Legend(
                    labelExpr="datum.label == 'met' ? '35%+' : datum.label == 'missed' ? '< 35%' : 'No data'"
                ),
            ),
            tooltip=["date:O", "pct_label:N"],
        )
        .properties(height=160, title="Your last ~12 weeks at a glance")
    )
    st.altair_chart(heatmap_chart, width="stretch")

    st.write("")
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=13), key="insights_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="insights_end")
    with col3:
        st.markdown(f"<div style='height:{SPACE_MD}'></div>", unsafe_allow_html=True)
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

    raw_bar_rows = [
        {"log_date": l["log_date"], "group": group_label(l), "hours": float(l["hours"])}
        for l in ranged_logs
    ]
    bar_rows = insights.fold_to_top_groups(raw_bar_rows, "group")

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

    takeaway = insights.category_share_takeaway(raw_bar_rows, "group")
    if takeaway:
        st.markdown(f"<p class='takeaway-line'>💡 {takeaway}</p>", unsafe_allow_html=True)

    totals = insights.group_totals(raw_bar_rows, "group")
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    rank_data = [{"group": name, "hours": hours} for name, hours in ranked]
    rank_chart = (
        alt.Chart(alt.Data(values=rank_data))
        .mark_bar(cornerRadius=3)
        .encode(
            x=alt.X("hours:Q", title="Hours"),
            y=alt.Y("group:N", title=None, sort="-x"),
            color=alt.Color("group:N", legend=None, scale=alt.Scale(domain=domain, range=range_)),
            tooltip=["group:N", "hours:Q"],
        )
        .properties(height=max(36 * len(rank_data), 90), title="Total hours (ranked)")
    )
    st.altair_chart(rank_chart, width="stretch")

    bar_title = "Hours by category" + (" / sub-category" if show_sub else "") + " over time"
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
    if st.session_state.pop("tree_grew", False):
        st.toast("Your tree grew a little! \U0001F331", icon="\U0001F331")

    token_balance = db.get_unredeemed_token_count(user_id)
    redemption_count = db.get_redemption_count(user_id)
    past_trees, stage, emoji = rewards.forest_history(redemption_count)
    remaining = rewards.redemptions_until_full_tree(redemption_count)

    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:140px;text-align:center;line-height:1.15'>{emoji}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;font-size:1.1rem;margin-bottom:0.25rem'>"
            f"Growing: <b style='color:{BRAND_INDIGO}'>{stage}</b></p>",
            unsafe_allow_html=True,
        )
        plural = "s" if remaining != 1 else ""
        st.markdown(
            f"<p style='text-align:center;opacity:0.7;margin-bottom:1rem'>"
            f"{remaining} more redemption{plural} until this tree is fully grown \U0001F333</p>",
            unsafe_allow_html=True,
        )

        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            if token_balance > 0:
                if st.button("Redeem 1 token \U0001FA99", type="primary", width="stretch"):
                    with spin("Convincing the tree to grow faster..."):
                        token = db.get_unredeemed_tokens(user_id)[0]
                        db.redeem_token(user_id, token["id"])
                    st.session_state["tree_grew"] = True
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

    st.write("")
    if past_trees:
        st.markdown("<p style='opacity:0.7;margin-bottom:0.25rem'>Your forest so far</p>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='forest-row'>{''.join(past_trees)}</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(past_trees)} tree{'s' if len(past_trees) != 1 else ''} fully grown and planted.")
    else:
        st.caption("Grow your first full tree to start your forest \U0001F333")


NAV_OPTIONS = ["🏠 Today", "📊 Insights", "🎁 Redeem"]


def main():
    # Everything the app can show -- login or authenticated -- is rendered
    # inside a single st.empty() placeholder so a run only ever has one of
    # the two branches' markup on the page, never a transient mix of both.
    body = st.empty()
    with body.container():
        inject_css()

        if "user" not in st.session_state:
            login_screen()
            return

        user = st.session_state["user"]
        style_metric_cards(border_left_color=BRAND_ACCENT, box_shadow=False)

        header_left, header_right = st.columns([4, 1])
        with header_left:
            st.markdown("<h2 style='margin-bottom:0'>⏳ Hourglass</h2>", unsafe_allow_html=True)
        with header_right:
            st.markdown(
                f"<p style='text-align:right;opacity:0.7;margin-bottom:0.25rem'>{user['username']}</p>",
                unsafe_allow_html=True,
            )
            if st.button("Log out", width="stretch"):
                del st.session_state["user"]
                st.rerun()

        st.write("")
        nav = st.segmented_control(
            "Navigate",
            NAV_OPTIONS,
            default=NAV_OPTIONS[0],
            key="nav_view",
            label_visibility="collapsed",
            required=True,
        )
        st.write("")

        if nav == NAV_OPTIONS[1]:
            insights_page(user["id"])
        elif nav == NAV_OPTIONS[2]:
            redeem_page(user["id"])
        else:
            today_page(user["id"])


if __name__ == "__main__":
    main()
