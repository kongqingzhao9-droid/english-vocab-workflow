// Maintainer test: node tests/test_database.cjs [path-to-pglite-module]
const { PGlite } = require(process.argv[2] || '@electric-sql/pglite');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const owner = '22222222-2222-4222-8222-222222222222', token = '1'.repeat(64);
const schema = fs.readFileSync(path.join(root, 'templates/sql/schema.sql'), 'utf8').replaceAll('__OWNER_ID__', owner);
const publisher = fs.readFileSync(path.join(root, 'templates/sql/publisher.sql'), 'utf8').replaceAll('__TOKEN_HASH__', crypto.createHash('sha256').update(token).digest('hex'));
(async () => {
  const db = new PGlite();
  try {
    await db.exec(`create role anon; create role authenticated;
      create schema auth;
      create table auth.users(id uuid primary key,email_confirmed_at timestamptz,is_anonymous boolean default false);
      insert into auth.users values('${owner}',now(),false);
      create function auth.uid() returns uuid language sql stable as
      $$ select nullif(coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb->>'sub','')::uuid $$;
      grant usage on schema auth to anon,authenticated;
      grant execute on function auth.uid() to anon,authenticated;`);
    await db.exec(schema); await db.exec(publisher);
    await db.exec(fs.readFileSync(path.join(root, 'templates/sql/verify.sql'), 'utf8'));
    let checks = 1;
    const rpc = async (name, args) => {
      await db.exec('set role anon');
      try { return (await db.query(`select public.${name}(${args.map((_,i)=>'$'+(i+1)).join(',')}) as value`, args)).rows[0].value; }
      finally { await db.exec('reset role'); }
    };
    const status = () => rpc('vocab_kit_publish_status', [token]);
    const publish = (payload, hash) => rpc('vocab_kit_publish', [token, payload, hash]);
    let current = await status(); assert.equal(current.words, 0); checks++;
    await assert.rejects(rpc('vocab_kit_publish_status', ['0'.repeat(64)])); checks++;
    let payload = {vocab:[{word:'sustain',order:1}],sentences:[]};
    await assert.rejects(rpc('vocab_kit_publish', ['0'.repeat(64), payload, current.hash])); checks++;
    current = await publish(payload, current.hash); assert.equal(current.words, 1); checks++;
    await db.exec(`select set_config('request.jwt.claims','{"sub":"${owner}","role":"authenticated"}',false); set role authenticated;
      insert into public.vocab_kit_state(word,stars,archived,deleted) values('sustain',5,true,true); reset role;`);
    const unchanged = await publish(payload, current.hash); assert.equal(unchanged.hash, current.hash); checks++;
    payload.vocab.push({word:'reluctant',order:2}); current = await publish(payload, current.hash); assert.equal(current.words, 2); checks++;
    const progress = (await db.query('select * from public.vocab_kit_state')).rows[0];
    assert.equal(progress.stars, 5); assert.equal(progress.archived, true); assert.equal(progress.deleted, true); checks++;
    const modified = JSON.parse(JSON.stringify(payload)); modified.vocab[0].word = 'changed';
    await assert.rejects(publish(modified, current.hash)); checks++;
    await assert.rejects(publish({vocab:[],sentences:[]}, current.hash)); checks++;
    await assert.rejects(publish(payload, 'stale-hash')); checks++;
    await db.exec(schema); await db.exec(publisher);
    assert.equal((await status()).words, 2); assert.equal((await db.query('select stars from public.vocab_kit_state')).rows[0].stars, 5); checks++;
    console.log(`PASS ${checks} database scenarios: role permissions, empty start, scoped upload, bad key, idempotency, append-only conflicts, concurrency guard, state preservation and setup rerun.`);
  } finally { await db.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
