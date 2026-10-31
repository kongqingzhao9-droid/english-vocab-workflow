-- Execute after setup.sql. Tests anon, a different authenticated user, and the sole owner.
-- Test mutations are rolled back. A failed check raises an error.
begin;
select set_config('vocab.test_owner', (select user_id::text from vocab_kit_private.owner), true);
set local role anon;
do $$ begin
  begin perform * from public.vocab_kit_library; raise exception 'FAIL: anon can read library';
  exception when insufficient_privilege then null; end;
  begin perform * from public.vocab_kit_state; raise exception 'FAIL: anon can read state';
  exception when insufficient_privilege then null; end;
  begin insert into public.vocab_kit_state(word) values ('__security_probe__');
    raise exception 'FAIL: anon can write'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-000000000001","role":"authenticated"}', true);
set local role authenticated;
do $$ declare n integer; begin
  if public.vocab_kit_is_owner() then raise exception 'FAIL: stranger is owner'; end if;
  if exists(select 1 from public.vocab_kit_library) or exists(select 1 from public.vocab_kit_state) then
    raise exception 'FAIL: stranger reads private data'; end if;
  update public.vocab_kit_state set stars=5; get diagnostics n=row_count;
  if n<>0 then raise exception 'FAIL: stranger updates state'; end if;
  delete from public.vocab_kit_state; get diagnostics n=row_count;
  if n<>0 then raise exception 'FAIL: stranger deletes state'; end if;
  begin insert into public.vocab_kit_state(word) values ('__security_probe__');
    raise exception 'FAIL: stranger inserts state'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select set_config('request.jwt.claims', json_build_object('sub',current_setting('vocab.test_owner'),'role','authenticated')::text, true);
set local role authenticated;
do $$ begin
  if not public.vocab_kit_is_owner() then raise exception 'FAIL: owner rejected'; end if;
  if not exists(select 1 from public.vocab_kit_library) then raise exception 'FAIL: owner cannot read'; end if;
  insert into public.vocab_kit_state(word,stars) values ('__security_probe__',3);
  update public.vocab_kit_state set stars=4 where word='__security_probe__';
  if not exists(select 1 from public.vocab_kit_state where word='__security_probe__' and stars=4) then
    raise exception 'FAIL: owner write failed'; end if;
  delete from public.vocab_kit_state where word='__security_probe__';
end $$;
reset role;
rollback;
select 'PASS: anonymous denied; other user denied; owner read/write works; test changes rolled back' as result;
