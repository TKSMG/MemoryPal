-- 0.52.0: a set's details (exam date, AI style, teacher's questions) sync as
-- "deck:<set name>" records. Builds that still sync cards through Supabase
-- need the table to accept that kind. Safe to run more than once.

alter table public.sync_records drop constraint if exists sync_records_kind_check;
alter table public.sync_records
  add constraint sync_records_kind_check
  check (kind in ('card', 'capture', 'deck', 'settings', 'activity', 'practiced'));

alter table public.sync_records drop constraint if exists sync_records_key_kind;
alter table public.sync_records
  add constraint sync_records_key_kind
  check (key ~ '^(card|capture|deck|settings|activity|practiced):' and split_part(key, ':', 1) = kind) not valid;
