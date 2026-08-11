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

CELEBRATION_MESSAGES = [
    "Token earned! Your tree just felt that.",
    "35%+ productive -- nicely done. Token unlocked!",
    "Hourglass approves. One token, freshly minted.",
]


def inject_css():
    # Fonts, brand colors, and base widget styling come from
    # .streamlit/config.toml's [theme] block. What stays here is everything
    # that theme can't express: gradients, shadows, and accent blocks that
    # give the flat bordered-box look real depth, plus a couple of small
    # custom markup rows.
    st.markdown(
        f"""
        <style>
        .takeaway-line {{
            font-size: 1.02rem;
            margin: 0.25rem 0 0.75rem 0;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: {SPACE_MD};
        }}

        /* Subtle top-of-page wash instead of flat white everywhere. */
        .stApp {{
            background: linear-gradient(180deg, {BRAND_AMBER}14 0%, #FFFFFF 420px);
        }}

        /* Gradient hero band behind the app header (scoped via
        st.container(key="hero_band") so it never leaks onto other rows). */
        .st-key-hero_band {{
            background: linear-gradient(135deg, {BRAND_INDIGO} 0%, #4B3F8C 55%, #6C4AA6 100%);
            border-radius: 24px;
            padding: 1.5rem 1.75rem 1.25rem 1.75rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 16px 36px -16px {BRAND_INDIGO}73;
        }}
        .st-key-hero_band h2 {{
            color: #FFFFFF !important;
            margin-bottom: 0 !important;
        }}
        .st-key-hero_band .hero-user {{
            color: rgba(255,255,255,0.85) !important;
        }}
        .st-key-hero_band [data-testid="stBaseButton-secondary"] {{
            background: rgba(255,255,255,0.14) !important;
            border: 1px solid rgba(255,255,255,0.5) !important;
            color: #FFFFFF !important;
        }}
        .st-key-hero_band [data-testid="stBaseButton-secondary"]:hover {{
            background: rgba(255,255,255,0.28) !important;
        }}

        /* Accent-block metric tiles instead of flat bordered boxes. */
        div[data-testid="stMetric"] {{
            background: linear-gradient(160deg, #FFFFFF 0%, {BRAND_AMBER}26 100%) !important;
            border: 1px solid {BRAND_AMBER}66 !important;
            border-radius: 18px !important;
            box-shadow: 0 10px 24px -16px {BRAND_INDIGO}59 !important;
            padding: 0.9rem 1.1rem 0.6rem 1.1rem !important;
        }}
        div[data-testid="stMetricValue"] {{
            background: linear-gradient(90deg, {BRAND_INDIGO}, {BRAND_ACCENT});
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        /* Today's two hero metrics get extra size -- they're the one thing
        this screen wants you to see first. Scoped so it doesn't also blow
        out Insights' narrower 4-up metric row. */
        .st-key-today_hero div[data-testid="stMetricValue"] {{
            font-size: 3rem;
        }}

        /* Gradient primary buttons with real lift, in place of flat fills. */
        [data-testid="stBaseButton-primaryFormSubmit"],
        [data-testid="stBaseButton-primary"] {{
            background: linear-gradient(135deg, {BRAND_INDIGO} 0%, #4B3F8C 100%) !important;
            border: none !important;
            box-shadow: 0 12px 26px -12px {BRAND_INDIGO}8c;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        [data-testid="stBaseButton-primaryFormSubmit"]:hover,
        [data-testid="stBaseButton-primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 16px 30px -12px {BRAND_INDIGO}a3;
        }}

        /* Depth for every bordered container: soft shadow + rounder corners
        instead of a flat 1px border doing all the work. */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 20px !important;
            box-shadow: 0 14px 32px -22px {BRAND_INDIGO}66;
        }}

        /* Login card: same shadow/gradient treatment as the rest. */
        [data-testid="stForm"] {{
            background: linear-gradient(180deg, #FFFFFF 0%, {BRAND_AMBER}12 100%);
            border-radius: 22px !important;
            box-shadow: 0 22px 48px -22px {BRAND_INDIGO}66;
            padding: 1.75rem 1.75rem 1.25rem 1.75rem;
        }}

        /* Login hero stage: a bold gradient landing moment (matching
        hero_band's language) instead of a bare logo floating on white --
        this is the very first thing anyone sees, so it carries the same
        visual weight as Today's hero band. */
        .st-key-login_hero {{
            background: linear-gradient(135deg, {BRAND_INDIGO} 0%, #4B3F8C 50%, {BRAND_ACCENT} 100%);
            border-radius: 28px;
            padding: 2.25rem 1.5rem 2.5rem 1.5rem;
            text-align: center;
            box-shadow: 0 24px 50px -18px {BRAND_INDIGO}80;
            margin-bottom: 1.25rem;
        }}
        .login-badge-circle {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 108px;
            height: 108px;
            border-radius: 50%;
            background: #FFFFFF;
            box-shadow: 0 14px 30px -10px rgba(0,0,0,0.35);
            margin-bottom: 0.75rem;
        }}
        .login-hero-title {{
            color: #FFFFFF !important;
            font-size: 2.6rem !important;
            margin: 0.25rem 0 0.5rem 0 !important;
        }}
        .login-hero-tagline {{
            color: rgba(255,255,255,0.9) !important;
            font-size: 1.05rem;
            margin: 0;
        }}

        /* Redeem stage: the tree is the emotional payoff of the whole app,
        so it gets its own dedicated backdrop -- not just a bordered box --
        the same way the login hero and Today's metrics got a stronger
        treatment than a flat card. */
        .st-key-redeem_stage {{
            background: radial-gradient(circle at top, {BRAND_AMBER}33 0%, #FFFFFF 55%),
                linear-gradient(180deg, #FFFDF7 0%, #FFFFFF 100%);
            border-radius: 28px;
            padding: 2rem 1.5rem 1.75rem 1.5rem;
            box-shadow: 0 22px 48px -20px {BRAND_INDIGO}59;
        }}

        /* Glowing radial backdrop + soil "ground" behind the Redeem tree
        hero, sized up so the tree reads as the centerpiece of the page. */
        .tree-hero-glow {{
            position: relative;
            display: flex;
            justify-content: center;
            align-items: flex-end;
            height: 250px;
        }}
        .tree-hero-glow::before {{
            content: "";
            position: absolute;
            top: 0;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: radial-gradient(circle, {BRAND_AMBER}80 0%, {BRAND_AMBER}00 72%);
        }}
        .redeem-ground {{
            position: absolute;
            bottom: 8px;
            width: 190px;
            height: 32px;
            border-radius: 50%;
            background: radial-gradient(ellipse, {BRAND_INDIGO}38 0%, transparent 75%);
            z-index: 0;
        }}
        .tree-hero-glow .tree-emoji {{
            position: relative;
            z-index: 1;
            font-size: 190px;
            line-height: 1;
            filter: drop-shadow(0 18px 24px {BRAND_INDIGO}59);
        }}

        /* Graphic growth stepper: seed -> sprout -> sapling -> tree ->
        blooming tree, with the current stage highlighted -- redemption
        progress made visible, not just a sentence of text. */
        .stage-track {{
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 380px;
            margin: 0.5rem auto 0 auto;
        }}
        .stage-track::before {{
            content: "";
            position: absolute;
            top: 50%;
            left: 10%;
            right: 10%;
            height: 4px;
            background: linear-gradient(90deg, {BRAND_AMBER}, {BRAND_INDIGO});
            opacity: 0.3;
            transform: translateY(-50%);
            border-radius: 4px;
            z-index: 0;
        }}
        .stage-dot {{
            position: relative;
            z-index: 1;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            background: #FFFFFF;
            border: 3px solid #e7e3d8;
            opacity: 0.45;
        }}
        .stage-dot.done {{
            border-color: {BRAND_INDIGO};
            opacity: 0.85;
        }}
        .stage-dot.current {{
            border-color: {BRAND_ACCENT};
            box-shadow: 0 0 0 6px {BRAND_AMBER}40;
            opacity: 1;
            transform: scale(1.25);
            background: linear-gradient(160deg, #FFFFFF 0%, {BRAND_AMBER}33 100%);
        }}

        /* Forest gallery: each fully-grown tree gets its own shadowed chip
        instead of a flat row of emoji text. */
        .forest-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
        }}
        .forest-chip {{
            font-size: 2.3rem;
            line-height: 1;
            background: linear-gradient(160deg, #FFFFFF 0%, {BRAND_AMBER}26 100%);
            border-radius: 16px;
            padding: 0.5rem 0.7rem;
            box-shadow: 0 10px 22px -14px {BRAND_INDIGO}66;
        }}

        /* Shared bold section heading, used wherever a plain chart title
        needs the same typographic weight Today's hero numbers get. */
        .section-heading {{
            font-family: "Fraunces", serif;
            color: {BRAND_INDIGO};
            font-weight: 700;
            font-size: 1.2rem;
            margin: 0 0 0.75rem 0;
        }}

        /* Insights stats strip + chart cards: the same gradient/shadow
        panel language as Today's hero metrics, so Insights doesn't read as
        a visually weaker sibling page. */
        .st-key-insights_stats_strip {{
            background: linear-gradient(160deg, #FFFFFF 0%, {BRAND_AMBER}1f 100%);
            border-radius: 22px;
            padding: 1.25rem 1rem 0.5rem 1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 16px 34px -22px {BRAND_INDIGO}55;
        }}
        .st-key-heatmap_card,
        .st-key-rank_chart_card,
        .st-key-bar_chart_card,
        .st-key-line_chart_card {{
            background: linear-gradient(160deg, #FFFFFF 0%, {BRAND_AMBER}14 100%);
            border-radius: 20px;
            padding: 1.25rem 1.25rem 0.75rem 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 14px 32px -22px {BRAND_INDIGO}66;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_logo(width=60, badge=False):
    with open("assets/logo.svg") as f:
        svg = f.read().replace('width="100" height="140"', f'width="{width}"')
    inner = f'<div class="login-badge-circle">{svg}</div>' if badge else svg
    st.markdown(f'<div style="text-align:center">{inner}</div>', unsafe_allow_html=True)


def login_screen():
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        with st.container(key="login_hero"):
            show_logo(width=76, badge=True)
            st.markdown("<h1 class='login-hero-title'>Hourglass ⏳</h1>", unsafe_allow_html=True)
            st.markdown(
                "<p class='login-hero-tagline'>Log hours, cross 35% productive, grow a tree. 🌱</p>",
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

            with st.spinner("Logging in..."):
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
                with st.spinner():
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
                with st.spinner():
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
    with st.container(key="today_hero"):
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
                    with st.spinner("Saving..."):
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

        with st.spinner():
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
    with st.spinner("Loading..."):
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
    with st.container(key="insights_stats_strip"):
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
        .properties(height=160)
    )
    with st.container(key="heatmap_card"):
        st.markdown("<p class='section-heading'>Your last ~12 weeks at a glance</p>", unsafe_allow_html=True)
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

    with st.spinner():
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
        .properties(height=max(36 * len(rank_data), 90))
    )
    with st.container(key="rank_chart_card"):
        st.markdown("<p class='section-heading'>Total hours (ranked)</p>", unsafe_allow_html=True)
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
        .properties(height=280)
    )
    with st.container(key="bar_chart_card"):
        st.markdown(f"<p class='section-heading'>{bar_title}</p>", unsafe_allow_html=True)
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
    with st.container(key="line_chart_card"):
        st.markdown("<p class='section-heading'>Daily productive %</p>", unsafe_allow_html=True)
        st.altair_chart(
            (line + threshold_rule).properties(height=280),
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
    stage_index = rewards.TREE_STAGES.index(stage)

    # Graphic stepper across every named growth stage -- this is the
    # redemption-progress payoff made visible at a glance, not just a line
    # of text saying how many redemptions are left.
    stage_dots = []
    for i, stage_name in enumerate(rewards.TREE_STAGES):
        if i < stage_index:
            dot_class = "done"
        elif i == stage_index:
            dot_class = "current"
        else:
            dot_class = ""
        stage_dots.append(f"<div class='stage-dot {dot_class}'>{rewards.TREE_EMOJI[stage_name]}</div>")
    stage_track_html = f"<div class='stage-track'>{''.join(stage_dots)}</div>"

    with st.container(key="redeem_stage"):
        st.markdown(
            f"<div class='tree-hero-glow'><div class='redeem-ground'></div>"
            f"<span class='tree-emoji'>{emoji}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(stage_track_html, unsafe_allow_html=True)
        st.markdown(
            f"<p style='text-align:center;font-size:1.2rem;margin:1rem 0 0.25rem 0'>"
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
                    with st.spinner("Redeeming..."):
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
        st.markdown("<p class='section-heading'>Your forest so far</p>", unsafe_allow_html=True)
        forest_chips = "".join(f"<div class='forest-chip'>{t}</div>" for t in past_trees)
        st.markdown(f"<div class='forest-grid'>{forest_chips}</div>", unsafe_allow_html=True)
        st.caption(f"{len(past_trees)} tree{'s' if len(past_trees) != 1 else ''} fully grown and planted.")
    else:
        st.caption("Grow your first full tree to start your forest \U0001F333")


NAV_OPTIONS = ["🏠 Today", "📊 Insights", "🎁 Redeem"]


def main():
    # Login and the authenticated view use different st.columns() shapes
    # ([1,2,1] vs [4,1]). Streamlit's frontend reconciles a run's elements by
    # structural position, not by which branch produced them, so a single
    # shared st.empty() container isn't enough to prevent the two shapes'
    # content from briefly overlapping mid-transition: the incoming branch's
    # first column can get painted into the DOM slot the outgoing branch's
    # first column occupied, before that slot is cleared. Giving each branch
    # its own placeholder -- and explicitly emptying the *other* one first --
    # forces an immediate clear delta so the two shapes never share a slot.
    login_slot = st.empty()
    app_slot = st.empty()

    if "user" not in st.session_state:
        app_slot.empty()
        with login_slot.container():
            inject_css()
            login_screen()
        return

    login_slot.empty()
    with app_slot.container():
        inject_css()

        user = st.session_state["user"]
        style_metric_cards(border_left_color=BRAND_ACCENT, box_shadow=False)

        with st.container(key="hero_band"):
            header_left, header_right = st.columns([4, 1])
            with header_left:
                st.markdown("<h2 style='margin-bottom:0'>⏳ Hourglass</h2>", unsafe_allow_html=True)
            with header_right:
                st.markdown(
                    f"<p class='hero-user' style='text-align:right;margin-bottom:0.25rem'>{user['username']}</p>",
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
