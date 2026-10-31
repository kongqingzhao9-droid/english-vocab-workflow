-- PRIVATE: execute only in your own Supabase SQL Editor. New independent installation.
begin;
create schema if not exists vocab_kit_private;
revoke all on schema vocab_kit_private from public, anon, authenticated;
create table if not exists vocab_kit_private.owner (
  id boolean primary key default true check (id),
  user_id uuid not null unique references auth.users(id)
);
alter table vocab_kit_private.owner enable row level security;
revoke all on vocab_kit_private.owner from public, anon, authenticated;

do $owner$
begin
  if not exists(select 1 from auth.users where id='__OWNER_ID__'::uuid and email_confirmed_at is not null and coalesce(is_anonymous,false)=false) then
    raise exception 'Create a confirmed email user in Authentication / Users first';
  end if;
  if exists(select 1 from vocab_kit_private.owner where user_id <> '__OWNER_ID__'::uuid) then
    raise exception 'Owner already configured; refusing ownership transfer';
  end if;
  insert into vocab_kit_private.owner(id,user_id) values(true,'__OWNER_ID__'::uuid) on conflict(id) do nothing;
end;
$owner$;

-- This function exposes only an ownership boolean, never the owner ID or vocabulary.
create or replace function public.vocab_kit_is_owner() returns boolean
language sql stable security definer set search_path = ''
as $$ select exists (select 1 from vocab_kit_private.owner where user_id = (select auth.uid())); $$;
revoke all on function public.vocab_kit_is_owner() from public, anon;
grant execute on function public.vocab_kit_is_owner() to authenticated;

create table if not exists public.vocab_kit_library (
  id boolean primary key default true check(id),
  payload jsonb not null check(jsonb_typeof(payload->'vocab') = 'array' and jsonb_typeof(payload->'sentences') = 'array'),
  updated_at timestamptz not null default now()
);
create table if not exists public.vocab_kit_state (
  word text primary key,
  stars smallint not null default 0 check (stars between 0 and 5),
  archived boolean not null default false,
  deleted boolean not null default false,
  updated_at timestamptz not null default now()
);
alter table public.vocab_kit_library enable row level security;
alter table public.vocab_kit_state enable row level security;
revoke all on public.vocab_kit_library, public.vocab_kit_state from public, anon, authenticated;
grant select on public.vocab_kit_library to authenticated;
grant select, insert, update, delete on public.vocab_kit_state to authenticated;

-- Remove all prior policies on these new tables so an old permissive policy cannot remain.
do $policies$
declare p record;
begin
  for p in select tablename, policyname from pg_policies where schemaname = 'public'
    and tablename in ('vocab_kit_library', 'vocab_kit_state') loop
    execute format('drop policy %I on public.%I', p.policyname, p.tablename);
  end loop;
end;
$policies$;
create policy library_owner on public.vocab_kit_library for select to authenticated
  using ((select public.vocab_kit_is_owner()));
create policy state_owner on public.vocab_kit_state for all to authenticated
  using ((select public.vocab_kit_is_owner())) with check ((select public.vocab_kit_is_owner()));

create or replace function vocab_kit_private.state_time() returns trigger
language plpgsql set search_path = '' as $$
begin new.updated_at := clock_timestamp(); return new; end;
$$;
revoke all on function vocab_kit_private.state_time() from public, anon, authenticated;
drop trigger if exists private_state_time on public.vocab_kit_state;
create trigger private_state_time before insert or update on public.vocab_kit_state
for each row execute function vocab_kit_private.state_time();

insert into public.vocab_kit_library(id,payload) values(true,'{"vocab":[],"sentences":[]}'::jsonb)
on conflict(id) do nothing;
commit;
select 'PRIVATE_PREPARED' as result,
  jsonb_array_length(payload->'vocab') as words,
  jsonb_array_length(payload->'sentences') as sentences
from public.vocab_kit_library;
