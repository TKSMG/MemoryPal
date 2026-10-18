-- MemoryPal AI notes and questions: a daily allowance per person, 18 October 2026.
--
-- Paste this into the Supabase SQL editor and run it once (before deploying
-- the "ai" Edge Function, see supabase/functions/ai/README.md). It is safe to
-- run again, drops nothing and changes no other data. supabase/schema.sql
-- already holds the same changes for new projects.
--
-- One row per person per day (UTC) counts their AI requests. Only the Edge
-- Function writes it, with the service role: Row Level Security is on and
-- there are no policies, so signed-in people can't read or change counts.

create table if not exists public.ai_usage (
  user_id uuid    not null references auth.users (id) on delete cascade,
  day     date    not null,
  count   integer not null default 0 check (count >= 0),
  primary key (user_id, day)
);

alter table public.ai_usage enable row level security;
revoke all on public.ai_usage from anon, authenticated;

-- Count one request and say whether it fits in today's allowance, in one
-- atomic statement (two requests at once can't both take the last one).
-- Returns the new count, or null when the person has used `p_limit` today.
create or replace function public.ai_usage_take(p_user uuid, p_limit integer)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  used integer;
begin
  if p_user is null or p_limit is null or p_limit < 1 then
    return null;
  end if;
  insert into public.ai_usage as u (user_id, day, count)
  values (p_user, (now() at time zone 'utc')::date, 1)
  on conflict (user_id, day) do update
    set count = u.count + 1
    where u.count < p_limit
  returning u.count into used;
  return used;
end;
$$;

-- Give one back when the request failed on the AI provider's side (busy or
-- an error), so people aren't charged for answers they never got.
create or replace function public.ai_usage_refund(p_user uuid)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.ai_usage
  set count = greatest(count - 1, 0)
  where user_id = p_user and day = (now() at time zone 'utc')::date;
$$;

revoke all on function public.ai_usage_take(uuid, integer) from public, anon, authenticated;
revoke all on function public.ai_usage_refund(uuid) from public, anon, authenticated;
grant execute on function public.ai_usage_take(uuid, integer) to service_role;
grant execute on function public.ai_usage_refund(uuid) to service_role;
