-- MemoryPal sync moves to Google Drive, 20 October 2026.
--
-- Paste this into the Supabase SQL editor and run it once, before releasing
-- the apps that sync through Google Drive. It is safe to run again, drops
-- nothing and changes no other data. supabase/schema.sql already holds the
-- same function for new projects.
--
-- When a profile connects Google Drive, the apps merge its records from
-- sync_records into the drive and then call this to remove them here, so
-- the MemoryPal cloud keeps only the account.

-- Moving to Google Drive: once a profile's records are in the person's own
-- drive, the apps remove them from here. Only the caller's own rows, and
-- for an account with an authenticator app only after its code.
create or replace function public.delete_my_sync_records()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'not signed in';
  end if;
  if coalesce(auth.jwt()->>'aal', 'aal1') <> 'aal2' and private.has_verified_second_step() then
    raise exception 'second step required' using errcode = '42501';
  end if;
  delete from public.sync_records where user_id = auth.uid();
end;
$$;

revoke all on function public.delete_my_sync_records() from public, anon;
grant execute on function public.delete_my_sync_records() to authenticated;
