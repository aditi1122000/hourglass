"""Thin wrapper around the Supabase client. All Supabase reads/writes for the
app live here so the rest of the app never talks to the client directly.
"""

import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DEFAULT_CATEGORIES = [
    {"name": "Work", "description": "Work-related tasks", "is_productive": True},
    {"name": "Content", "description": "Content creation / learning", "is_productive": True},
    {"name": "Fun", "description": "Leisure and entertainment", "is_productive": False},
]

_client = None


def get_client():
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client


# ---- users ----------------------------------------------------------------

def get_user_by_username(username):
    res = get_client().table("users").select("*").eq("username", username).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def create_user(username, password_hash):
    res = get_client().table("users").insert(
        {"username": username, "password_hash": password_hash}
    ).execute()
    user = res.data[0]
    seed_default_categories(user["id"])
    return user


# ---- categories -------------------------------------------------------------

def seed_default_categories(user_id):
    rows = [
        {
            "user_id": user_id,
            "name": c["name"],
            "description": c["description"],
            "is_productive": c["is_productive"],
        }
        for c in DEFAULT_CATEGORIES
    ]
    get_client().table("categories").insert(rows).execute()


def get_categories(user_id):
    res = (
        get_client()
        .table("categories")
        .select("*")
        .eq("user_id", user_id)
        .order("name")
        .execute()
    )
    return res.data or []


def create_category(user_id, name, description, is_productive):
    res = get_client().table("categories").insert(
        {
            "user_id": user_id,
            "name": name,
            "description": description,
            "is_productive": is_productive,
        }
    ).execute()
    return res.data[0]


# ---- sub-categories ---------------------------------------------------------

def get_sub_categories(category_id):
    res = (
        get_client()
        .table("sub_categories")
        .select("*")
        .eq("category_id", category_id)
        .order("name")
        .execute()
    )
    return res.data or []


def create_sub_category(category_id, name, description):
    res = get_client().table("sub_categories").insert(
        {"category_id": category_id, "name": name, "description": description}
    ).execute()
    return res.data[0]


# ---- logs -------------------------------------------------------------------

def create_log(user_id, category_id, sub_category_id, log_date, hours, note):
    res = get_client().table("logs").insert(
        {
            "user_id": user_id,
            "category_id": category_id,
            "sub_category_id": sub_category_id,
            "log_date": str(log_date),
            "hours": hours,
            "note": note,
        }
    ).execute()
    return res.data[0]


def get_logs_for_date(user_id, log_date):
    res = (
        get_client()
        .table("logs")
        .select("*, categories(name, is_productive), sub_categories(name)")
        .eq("user_id", user_id)
        .eq("log_date", str(log_date))
        .execute()
    )
    return res.data or []


def get_logs_for_range(user_id, start_date, end_date):
    res = (
        get_client()
        .table("logs")
        .select("*, categories(name, is_productive), sub_categories(name)")
        .eq("user_id", user_id)
        .gte("log_date", str(start_date))
        .lte("log_date", str(end_date))
        .order("log_date", desc=True)
        .execute()
    )
    return res.data or []


# ---- tokens -------------------------------------------------------------------

def get_token_for_date(user_id, log_date):
    res = (
        get_client()
        .table("tokens")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", str(log_date))
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def award_token(user_id, log_date):
    res = get_client().table("tokens").insert(
        {"user_id": user_id, "log_date": str(log_date)}
    ).execute()
    return res.data[0]


def get_unredeemed_tokens(user_id):
    res = (
        get_client()
        .table("tokens")
        .select("*")
        .eq("user_id", user_id)
        .eq("redeemed", False)
        .order("awarded_at")
        .execute()
    )
    return res.data or []


def get_unredeemed_token_count(user_id):
    return len(get_unredeemed_tokens(user_id))


# ---- redemptions ---------------------------------------------------------------

def redeem_token(user_id, token_id):
    get_client().table("tokens").update({"redeemed": True}).eq("id", token_id).execute()
    res = get_client().table("redemptions").insert(
        {"user_id": user_id, "token_id": token_id}
    ).execute()
    return res.data[0]


def get_redemption_count(user_id):
    res = (
        get_client()
        .table("redemptions")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return res.count or 0
