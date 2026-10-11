-- MemoryPal cloud sync: run this once in the Supabase SQL editor.
--
-- Every synced item (a card, a capture, the profile settings, one device's
-- review counts) is one row. Row Level Security means each person can only
-- ever read or change their own rows, whatever the apps do.

create table if not exists public.sync_records (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  key        text        not null check (char_length(key) between 3 and 200),
  kind       text        not null check (kind in ('card', 'capture', 'settings', 'activity', 'practiced')),
  data       jsonb,
  deleted    boolean     not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, key),
  -- One card or note is small; refuse oversized rows outright.
  constraint sync_records_size check (data is null or pg_column_size(data) < 262144)
);

create index if not exists sync_records_user_updated on public.sync_records (user_id, updated_at);

-- The server's clock decides updated_at, never the device's, so pulling
-- "everything changed since X" can't be fooled by a wrong phone clock.
create or replace function public.sync_records_touch()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- clock_timestamp(): the time of this write, not of the transaction start.
  new.updated_at := clock_timestamp();
  if tg_op = 'INSERT' then
    new.user_id := auth.uid();
  else
    new.user_id := old.user_id;
  end if;
  return new;
end;
$$;

drop trigger if exists sync_records_touch on public.sync_records;
create trigger sync_records_touch
  before insert or update on public.sync_records
  for each row execute function public.sync_records_touch();

-- A storage allowance per person, so one account (or a stolen one) can't
-- fill the database. Far above real use: thousands of cards are a few MB.
-- Checked once per write statement (an upload batch), not once per row.
create or replace function public.sync_records_quota()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if exists (
    select 1
    from (select distinct user_id from changed) as who
    where (select count(*) from public.sync_records s where s.user_id = who.user_id) > 50000
       or (select coalesce(sum(pg_column_size(s.data)), 0) from public.sync_records s where s.user_id = who.user_id) > 100 * 1024 * 1024
  ) then
    raise exception 'MemoryPal storage limit reached' using errcode = 'P0001', hint = 'storage_limit';
  end if;
  return null;
end;
$$;

drop trigger if exists sync_records_quota_insert on public.sync_records;
create trigger sync_records_quota_insert
  after insert on public.sync_records
  referencing new table as changed
  for each statement execute function public.sync_records_quota();

drop trigger if exists sync_records_quota_update on public.sync_records;
create trigger sync_records_quota_update
  after update on public.sync_records
  referencing new table as changed
  for each statement execute function public.sync_records_quota();

alter table public.sync_records enable row level security;

drop policy if exists "read own records" on public.sync_records;
create policy "read own records" on public.sync_records
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "add own records" on public.sync_records;
create policy "add own records" on public.sync_records
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "change own records" on public.sync_records;
create policy "change own records" on public.sync_records
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Two-step sign-in, enforced by the database: once someone has added an
-- authenticator app, their data can only be reached with a session that
-- passed that second step (aal2). A stolen password alone is not enough.
-- Signed-in users can't read auth.mfa_factors themselves (querying it from
-- the policy failed every sync with "permission denied"), so a definer
-- function in the unexposed "private" schema answers for them.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.has_verified_second_step()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from auth.mfa_factors
    where user_id = (select auth.uid()) and status = 'verified'
  );
$$;
revoke all on function private.has_verified_second_step() from public, anon;
grant execute on function private.has_verified_second_step() to authenticated;

drop policy if exists "two-step accounts need the second step" on public.sync_records;
create policy "two-step accounts need the second step" on public.sync_records
  as restrictive
  to authenticated
  using ((select auth.jwt()->>'aal') = 'aal2' or not (select private.has_verified_second_step()))
  with check ((select auth.jwt()->>'aal') = 'aal2' or not (select private.has_verified_second_step()));

-- No delete policy: deletions travel as rows with deleted = true, so every
-- device learns about them. Whole accounts are removed with the function below.
revoke all on public.sync_records from anon;
grant select, insert, update on public.sync_records to authenticated;

-- "Delete my account" in the apps (required by the App Store and Google Play
-- for apps with sign-up). Removing the auth user cascades to all their rows.
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'not signed in';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
