-- MemoryPal AI rate limits, 20 October 2026.
--
-- Paste this into the Supabase SQL editor and run it once, before deploying
-- the updated "ai" Edge Function. It is safe to run again, drops nothing and
-- changes no existing counts. supabase/schema.sql already holds the same
-- changes for new projects. The function falls back to the older
-- ai_usage_take() until this has been run.
--
-- On top of each person's daily allowance it adds:
-- 1. A per-person limit per minute, so one person can't use the Gemini key's
--    whole per-minute quota (about 15 on the free tier) at once.
-- 2. A count for everyone together, per day and per minute, so the app stops
--    with a clear message before the key's shared free-tier quota runs out.
--    Gemini resets its daily quota at midnight Pacific time, so this daily
--    count does too (each person's own allowance still resets at midnight UTC).

alter table public.ai_usage add column if not exists minute_start timestamptz;
alter table public.ai_usage add column if not exists minute_count integer not null default 0;

create table if not exists public.ai_usage_total (
  day          date        primary key,
  count        integer     not null default 0 check (count >= 0),
  minute_start timestamptz,
  minute_count integer     not null default 0
);

alter table public.ai_usage_total enable row level security;
revoke all on public.ai_usage_total from anon, authenticated;

-- Count one request if it fits every limit. A limit of 0 or less is off,
-- except p_daily, which must be at least 1. Returns {"used": <the person's
-- count today>} or {"refused": "daily" | "minute" | "total_daily" |
-- "total_minute"}. The person's row is locked first, then everyone's, so two
-- requests at once can't both take the last place.
create or replace function public.ai_usage_take_limited(
  p_user uuid,
  p_daily integer,
  p_per_minute integer,
  p_total_daily integer,
  p_total_per_minute integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  today date := (now() at time zone 'utc')::date;
  gemini_day date := (now() at time zone 'America/Los_Angeles')::date;
  this_minute timestamptz := date_trunc('minute', now());
  mine public.ai_usage;
  everyone public.ai_usage_total;
  used integer;
begin
  if p_user is null or p_daily is null or p_daily < 1 then
    return jsonb_build_object('refused', 'daily');
  end if;

  insert into public.ai_usage (user_id, day, count) values (p_user, today, 0)
  on conflict (user_id, day) do nothing;
  select * into mine from public.ai_usage where user_id = p_user and day = today for update;
  if mine.count >= p_daily then
    return jsonb_build_object('refused', 'daily');
  end if;
  if coalesce(p_per_minute, 0) > 0 and mine.minute_start = this_minute and mine.minute_count >= p_per_minute then
    return jsonb_build_object('refused', 'minute');
  end if;

  insert into public.ai_usage_total (day, count) values (gemini_day, 0)
  on conflict (day) do nothing;
  select * into everyone from public.ai_usage_total where day = gemini_day for update;
  if coalesce(p_total_daily, 0) > 0 and everyone.count >= p_total_daily then
    return jsonb_build_object('refused', 'total_daily');
  end if;
  if coalesce(p_total_per_minute, 0) > 0 and everyone.minute_start = this_minute and everyone.minute_count >= p_total_per_minute then
    return jsonb_build_object('refused', 'total_minute');
  end if;

  update public.ai_usage_total
  set count = count + 1,
      minute_count = case when minute_start = this_minute then minute_count + 1 else 1 end,
      minute_start = this_minute
  where day = gemini_day;

  update public.ai_usage
  set count = count + 1,
      minute_count = case when minute_start = this_minute then minute_count + 1 else 1 end,
      minute_start = this_minute
  where user_id = p_user and day = today
  returning count into used;
  return jsonb_build_object('used', used);
end;
$$;

-- Give one back when the request failed on the AI provider's side (busy or
-- an error), so people aren't charged for answers they never got. The
-- per-minute counts stay, so failed requests can't be retried in a tight loop.
create or replace function public.ai_usage_refund(p_user uuid)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.ai_usage
  set count = greatest(count - 1, 0)
  where user_id = p_user and day = (now() at time zone 'utc')::date;
  update public.ai_usage_total
  set count = greatest(count - 1, 0)
  where day = (now() at time zone 'America/Los_Angeles')::date;
$$;

revoke all on function public.ai_usage_take_limited(uuid, integer, integer, integer, integer) from public, anon, authenticated;
revoke all on function public.ai_usage_refund(uuid) from public, anon, authenticated;
grant execute on function public.ai_usage_take_limited(uuid, integer, integer, integer, integer) to service_role;
grant execute on function public.ai_usage_refund(uuid) to service_role;
