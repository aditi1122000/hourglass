-- Hourglass schema. Run this in the Supabase SQL editor for your project.
-- Safe to re-run: every statement uses IF NOT EXISTS.

create extension if not exists pgcrypto;

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists categories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    name text not null,
    description text,
    is_productive boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists sub_categories (
    id uuid primary key default gen_random_uuid(),
    category_id uuid not null references categories (id) on delete cascade,
    name text not null,
    description text,
    created_at timestamptz not null default now()
);

create table if not exists logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    category_id uuid not null references categories (id) on delete cascade,
    sub_category_id uuid references sub_categories (id) on delete set null,
    log_date date not null,
    hours numeric not null check (hours > 0),
    note text,
    created_at timestamptz not null default now()
);

create table if not exists tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    log_date date not null,
    awarded_at timestamptz not null default now(),
    redeemed boolean not null default false,
    unique (user_id, log_date)
);

create table if not exists redemptions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete cascade,
    token_id uuid not null references tokens (id) on delete cascade,
    redeemed_at timestamptz not null default now()
);

create index if not exists idx_categories_user on categories (user_id);
create index if not exists idx_sub_categories_category on sub_categories (category_id);
create index if not exists idx_logs_user_date on logs (user_id, log_date);
create index if not exists idx_tokens_user_date on tokens (user_id, log_date);
create index if not exists idx_redemptions_user on redemptions (user_id);
