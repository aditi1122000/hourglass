# Design notes: from 3-tab dashboard to a single-focus "Today" home

## Before

Logging in dropped you straight into `st.tabs(["📝 Log Time", "📊 Insights", "🎁 Redeem"])`.
All three tab labels rendered with equal visual weight the instant you landed,
and the content of all three tabs actually executed every run (Streamlit renders
every tab body, just hides the inactive ones with CSS) -- so Insights' Supabase
queries and chart-building ran even when you only wanted to log an hour.
Three rounds of prior work (tab styling, spacing, a research-based Insights/Redeem
visual redesign, native theming) all patched *within* that structure without ever
questioning whether a 3-way tab bar was the right first moment.

## After

Login now lands on **Today only**: a hero showing today's productive % and token
count, then the one thing you're actually here to do (log time), then a
collapsed history expander. Insights and Redeem are still one click away, via a
`st.segmented_control` pill row -- visually much lighter than a bordered tab bar
(closer to Things3's muted sidebar list or Duolingo's compact bottom nav than to
a dashboard's tab strip) -- but they don't compete for attention on arrival, and
their page functions no longer execute (and hit the database) unless selected.

Concretely, inside the old "Log Time" tab:
- The today's-progress card moved from *after* the form to *before* it, so you
  see where you stand before being asked to act.
- The category/sub-category pickers and the log-time form are grouped into one
  bordered container -- a single visual "this is the action" block, instead of
  loose controls floating above a separate form.
- The history expander stays collapsed and last, exactly as before.

This is a navigation/flow change, not a component-styling change: `today_page`,
`insights_page`, and `redeem_page` keep their existing internal visual designs
from the prior round untouched. No new dependency was added -- `st.segmented_control`
is native Streamlit (already available in the installed version), chosen over
`st.navigation`/`st.Page` specifically because it composes as one flat `if/elif`
in `main()` rather than a multipage shell, and is directly testable with
`streamlit.testing.v1.AppTest`.
