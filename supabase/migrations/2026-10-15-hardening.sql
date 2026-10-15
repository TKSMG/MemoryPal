-- MemoryPal cloud sync hardening, 15 October 2026.
--
-- Paste this into the Supabase SQL editor and run it once. It is safe to run
-- again, drops nothing and changes no data. supabase/schema.sql already holds
-- the same changes for new projects.
--
-- 1. A key must start with its kind ("card:...", "settings:profile").
-- 2. One person's uploads take turns when checking the storage allowance.
-- 3. The allowance is now 20,000 records / 25 MB of JSON per person.

-- 1. Keys match their kind. Added NOT VALID, then checked against existing
-- rows; if an old row breaks the rule, the check still applies to every new
-- write and a notice says so (find those rows with the query at the end).
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'sync_records_key_kind') then
    alter table public.sync_records
      add constraint sync_records_key_kind
      check (key ~ '^(card|capture|settings|activity|practiced):' and split_part(key, ':', 1) = kind) not valid;
  end if;
  begin
    alter table public.sync_records validate constraint sync_records_key_kind;
  exception when check_violation then
    raise notice 'sync_records has older rows whose key does not match their kind; new writes are checked.';
  end;
end;
$$;

-- 2 and 3. The storage allowance, replacing the earlier version in place (the
-- triggers that call it stay as they are).
create or replace function public.sync_records_quota()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text, 0));
  if exists (
    select 1
    from (select distinct user_id from changed) as who
    where (select count(*) from public.sync_records s where s.user_id = who.user_id) > 20000
       or (select coalesce(sum(octet_length(s.data::text)), 0) from public.sync_records s where s.user_id = who.user_id) > 25 * 1024 * 1024
  ) then
    raise exception 'MemoryPal storage limit reached' using errcode = 'P0001', hint = 'storage_limit';
  end if;
  return null;
end;
$$;

-- Afterwards, these should both return no rows:
--   select user_id, key, kind from public.sync_records
--   where not (key ~ '^(card|capture|settings|activity|practiced):' and split_part(key, ':', 1) = kind);
--
--   select user_id, count(*), sum(octet_length(data::text)) from public.sync_records
--   group by user_id having count(*) > 20000 or sum(octet_length(data::text)) > 25 * 1024 * 1024;
-- (An account already over the new allowance can still sign in and pull, but
-- its uploads are refused.)
