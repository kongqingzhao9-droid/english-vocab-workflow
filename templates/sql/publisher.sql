-- One-time, narrow publishing capability. Contains only a SHA256 digest, never the secret.
begin;
create table if not exists vocab_kit_private.publisher (
  id boolean primary key default true check(id),
  token_hash text not null,
  owner_id uuid not null references auth.users(id)
);
alter table vocab_kit_private.publisher enable row level security;
revoke all on vocab_kit_private.publisher from public, anon, authenticated;
insert into vocab_kit_private.publisher(id,token_hash,owner_id)
select true, '__TOKEN_HASH__', user_id from vocab_kit_private.owner
on conflict(id) do update set token_hash=excluded.token_hash, owner_id=excluded.owner_id;
do $$ begin
  if not exists(select 1 from vocab_kit_private.publisher) then raise exception 'Private owner missing'; end if;
end $$;

create or replace function vocab_kit_private.check_publisher(p_token text) returns void
language plpgsql security definer set search_path='' as $$
begin
  if p_token is null or length(p_token)<>64 or not exists(
    select 1 from vocab_kit_private.publisher p join vocab_kit_private.owner o on o.user_id=p.owner_id
    where p.token_hash=encode(sha256(convert_to(p_token,'UTF8')),'hex')
  ) then raise exception 'Publisher authorization denied' using errcode='42501'; end if;
end $$;
revoke all on function vocab_kit_private.check_publisher(text) from public,anon,authenticated;

create or replace function public.vocab_kit_publish_status(p_token text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare doc jsonb;
begin
  perform vocab_kit_private.check_publisher(p_token);
  select payload into strict doc from public.vocab_kit_library where id=true;
  return jsonb_build_object('hash',encode(sha256(convert_to(doc::text,'UTF8')),'hex'),
    'words',jsonb_array_length(doc->'vocab'),'sentences',jsonb_array_length(doc->'sentences'));
end $$;

create or replace function public.vocab_kit_publish(p_token text,p_payload jsonb,p_expected_hash text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare old_doc jsonb; old_hash text; k text;
begin
  perform vocab_kit_private.check_publisher(p_token);
  if p_payload is null or octet_length(p_payload::text)>5000000
    or jsonb_typeof(p_payload->'vocab') is distinct from 'array'
    or jsonb_typeof(p_payload->'sentences') is distinct from 'array'
    or exists(select 1 from jsonb_object_keys(p_payload) x where x not in ('vocab','sentences'))
  then raise exception 'Invalid library payload'; end if;
  select payload into strict old_doc from public.vocab_kit_library where id=true for update;
  old_hash:=encode(sha256(convert_to(old_doc::text,'UTF8')),'hex');
  if old_hash is distinct from p_expected_hash then raise exception 'Cloud library changed; refusing overwrite' using errcode='40001'; end if;
  -- Preserve every previously published entry and its position. Only append is allowed.
  foreach k in array array['vocab','sentences'] loop
    if jsonb_array_length(p_payload->k)<jsonb_array_length(old_doc->k) or exists(
      select 1 from jsonb_array_elements(old_doc->k) with ordinality a(entry,n)
      where entry is distinct from (p_payload->k)->(n::int-1)
    ) then raise exception 'Append only: existing entries must remain unchanged'; end if;
  end loop;
  if exists(select 1 from jsonb_array_elements(p_payload->'vocab') v
      where jsonb_typeof(v) is distinct from 'object' or coalesce(v->>'word','')!~'^[A-Za-z][A-Za-z ''’\-]*$'
        or jsonb_typeof(v->'order') is distinct from 'number')
    or exists(select 1 from jsonb_array_elements(p_payload->'vocab') v group by lower(v->>'word') having count(*)>1)
    or exists(select 1 from jsonb_array_elements(p_payload->'sentences') s where coalesce(s->>'id','')!~'^[0-9]+$')
    or exists(select 1 from jsonb_array_elements(p_payload->'sentences') s group by s->>'id' having count(*)>1)
  then raise exception 'Invalid or duplicate entries'; end if;
  if p_payload is distinct from old_doc then
    update public.vocab_kit_library set payload=p_payload, updated_at=clock_timestamp() where id=true;
  end if;
  -- No reads or writes of vocab_kit_state: learning progress is untouched.
  return public.vocab_kit_publish_status(p_token);
end $$;
revoke all on function public.vocab_kit_publish_status(text), public.vocab_kit_publish(text,jsonb,text) from public,anon,authenticated;
grant execute on function public.vocab_kit_publish_status(text), public.vocab_kit_publish(text,jsonb,text) to anon,authenticated;
commit;
select 'PUBLISHER_READY' as result;
