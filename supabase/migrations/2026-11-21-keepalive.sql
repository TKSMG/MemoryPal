-- Keep-alive: the free plan paused the project on ~2026-11-21 even though the
-- GitHub keep-alive pinged every 3 days, because those pings were refused
-- (the public key can't read sync_records) and Supabase wants "a few user
-- requests to the database each day". This gives the public key one harmless
-- query that succeeds: it returns the time and touches no data.
-- Safe to run more than once.

create or replace function public.keepalive()
returns timestamptz
language sql
stable
security invoker
set search_path = ''
as $$ select now() $$;

revoke all on function public.keepalive() from public;
grant execute on function public.keepalive() to anon, authenticated;
