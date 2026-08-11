# Hourglass ⏳

<img src="assets/logo.svg" width="80" alt="Hourglass logo" />

A deliberately simple personal time-logging app. Log hours against categories,
hit a 35% "productive time" threshold on a given day, and you earn a token.
Spend tokens to grow a little virtual tree. No LLM/API calls at runtime --
every bit of logic is plain, deterministic Python.

## Features

- **Login**: enter any username + password. First time you use a username, an
  account is created automatically (password is stored as a bcrypt hash,
  never in plaintext). Existing usernames must match their password.
- **Time logging**: log hours per day against a category (and optional
  sub-category), with categories/sub-categories creatable inline. Every new
  user starts with three seeded categories: `Work` (productive), `Content`
  (productive), `Fun` (not productive).
- **Tokens**: if a day's productive hours are >= 35% of that day's total
  logged hours, you earn exactly one token for that day (never more than one
  per user per day, even if you keep logging).
- **Redeem**: spend a token to grow your tree one stage: seed -> sprout ->
  sapling -> tree -> blooming tree.

## Project layout

- `app.py` -- Streamlit UI / entrypoint
- `auth.py` -- password hashing (passlib/bcrypt)
- `db.py` -- all Supabase reads/writes, isolated from the rest of the app
- `rewards.py` -- pure business logic (threshold %, token award decision,
  tree stage from redemption count) -- no DB dependency, fully unit-testable
- `schema.sql` -- table definitions for Supabase Postgres
- `assets/logo.svg` -- hand-authored logo
- `tests/test_rewards.py` -- unit tests for `rewards.py`

## Run it locally

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your Supabase credentials, see below
streamlit run app.py
```

## Set up your own Supabase project

This app needs its own, brand-new Supabase project -- don't reuse another
project's credentials.

1. Go to [dashboard.new.supabase.com](https://dashboard.new.supabase.com) and
   create a **New Project** (pick an org, name, database password, region).
2. Once it's provisioned, open **Project Settings > API**.
3. Copy the **Project URL** into `SUPABASE_URL` in your `.env`.
4. Copy the **service_role** secret key into `SUPABASE_SERVICE_ROLE_KEY` in
   your `.env`.
   - The app uses the service-role key by default because it does its own
     app-level login (not Supabase Auth) and needs to read/write freely on
     behalf of whichever user is logged in. This is fine for a small personal
     app, but the service-role key bypasses Row Level Security entirely --
     keep it secret and never ship it to a browser/client.
   - If you'd rather use the more restricted `anon`/`publishable` key
     instead, you can set `SUPABASE_ANON_KEY` (or `SUPABASE_PUBLISHABLE_KEY`)
     and point `db.py`'s `create_client` call at it -- but you'll then need
     to write Row Level Security policies yourself so each user can only
     read/write their own rows, since the app no longer has an elevated key.
5. Open the **SQL Editor** in the Supabase dashboard, paste in the contents
   of `schema.sql` from this repo, and run it. It only uses
   `CREATE TABLE IF NOT EXISTS`, so it's safe to re-run.

## Run the tests

```bash
pytest
```

`tests/test_rewards.py` covers the pure logic in `rewards.py` only, so it
runs without any Supabase connection or credentials.

## Deploy on Streamlit Community Cloud

1. Push this repo to a GitHub repository (this local repo has no remote
   configured yet -- add one, e.g. `git remote add origin <your-repo-url>`,
   then `git push -u origin main`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app**, pick this repo/branch, and set the main file path to
   `app.py`.
4. Before (or after) deploying, open the app's **Settings > Secrets** and add
   your Supabase credentials in TOML format:

   ```toml
   SUPABASE_URL = "https://your-project-ref.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
   ```

5. Deploy. Streamlit Community Cloud injects these secrets as environment
   variables, which `db.py` reads the same way it does locally via
   `python-dotenv` + `os.environ`.
