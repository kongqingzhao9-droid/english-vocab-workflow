// node tests/test_browser.cjs [path-to-playwright-module]
const {chromium}=require(process.argv[2] || 'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),site=path.join(root,'templates/site');
const owner='22222222-2222-4222-8222-222222222222',stranger='33333333-3333-4333-8333-333333333333';
const host='a'.repeat(20)+'.supabase.co';
const jwt=sub=>[Buffer.from('{}').toString('base64url'),Buffer.from(JSON.stringify({sub,exp:Math.floor(Date.now()/1000)+3600})).toString('base64url'),'test'].join('.');
const entry=(word,order)=>({word,order,phonetic:'/test/',pos:'v.',defEn:'<img src=x onerror="window.INJECTED=true">',meanings:['测试释义'],usage:'Synthetic test usage',example:'This example is only for software testing.',exampleCn:'这是软件测试用例。',prefix:'',root:'整体记忆',suffix:'',synonyms:[],derivatives:[],phrase:'',stars:0,archived:false});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,serviceWorkers:'block'});
  const page=await context.newPage(),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
  let payload={vocab:[],sentences:[]},states=[],failWrite=false,expired=false;
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.hostname==='vocab-kit.test'){
    let name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    let file=path.join(site,name);if(!fs.existsSync(file))return route.fulfill({status:404,body:'Not found'});
    let body=fs.readFileSync(file);
    if(name==='index.html')body=body.toString().replaceAll('__SUPABASE_URL__','https://'+host);
    if(name==='config.js')body='window.APP_CONFIG='+JSON.stringify({supabaseUrl:'https://'+host,supabaseAnonKey:jwt('anon')});
    return route.fulfill({contentType:name.endsWith('.html')?'text/html':'text/javascript',body});
   }
   assert.equal(url.hostname,host,'No external services contacted during this test');calls.push(url.pathname);
   const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   const other=(req.headers().authorization||'').includes(jwt(stranger));
   if(url.pathname==='/auth/v1/token'){
    const body=req.postDataJSON();if(body.password==='wrong')return json({error:'invalid_grant',error_description:'Invalid login'},400);
    const id=body.email==='stranger@example.invalid'?stranger:owner;
    return json({access_token:jwt(id),refresh_token:'synthetic-refresh',expires_in:3600,token_type:'bearer',user:{id,email:body.email,aud:'authenticated',role:'authenticated'}});
   }
   if(url.pathname==='/auth/v1/user')return expired?json({message:'Expired'},401):json({id:other?stranger:owner,aud:'authenticated',role:'authenticated'});
   if(url.pathname==='/auth/v1/logout')return json({});
   if(url.pathname==='/rest/v1/rpc/vocab_kit_is_owner')return json(!other);
   if(url.pathname==='/rest/v1/vocab_kit_library')return json({payload});
   if(url.pathname==='/rest/v1/vocab_kit_state'){
    if(req.method()==='GET')return json(states);
    if(failWrite)return json({message:'temporary failure'},503);
    const row=req.postDataJSON();states=states.filter(x=>x.word!==row.word).concat({...row,updated_at:new Date().toISOString()});return json(null,201);
   }
   throw Error('Unexpected API path '+url.pathname);
  });
  const login=async(email='owner@example.invalid',password='test-only')=>{await page.fill('#email',email);await page.fill('#password',password);await page.click('#loginButton')};
  await page.goto('http://vocab-kit.test/');await page.locator('#authMessage').filter({hasText:'请登录'}).waitFor();
  assert.equal(await page.locator('#appMain').isVisible(),false);assert(!calls.some(x=>x.startsWith('/rest/')));
  await login('owner@example.invalid','wrong');await page.locator('#authMessage').filter({hasText:'登录失败'}).waitFor();
  await login('stranger@example.invalid');await page.locator('#authMessage').filter({hasText:'没有访问'}).waitFor();
  assert(!calls.includes('/rest/v1/vocab_kit_library'));
  await login();await page.locator('#grid .empty').waitFor();assert((await page.locator('#grid').innerText()).includes('从这里开始'));
  for(const mode of ['review','search','sentences','memorize']){await page.click('[data-mode="'+mode+'"]');}
  fs.mkdirSync(path.join(root,'.local/qa/screenshots'),{recursive:true});
  await page.screenshot({path:path.join(root,'.local/qa/screenshots/empty-mobile.png')});
  for(const width of [320,390,1180]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow at '+width)}
  await page.screenshot({path:path.join(root,'.local/qa/screenshots/empty-desktop.png')});
  payload={vocab:[entry('sustain',1),entry('reluctant',2)],sentences:[{id:1,original:'Learners who practise regularly build confidence.',translation:'经常练习的学习者会建立信心。',main:'Learners build confidence.',clauses:['who practise regularly 修饰 learners。']}]};
  await page.reload();await page.locator('#grid .cell').first().click();assert.equal(await page.locator('#modal img').count(),0);assert.equal(await page.evaluate(()=>window.INJECTED),undefined);
  await page.click('[data-star="3"]');await page.locator('#syncNotice').filter({hasText:'已同步'}).waitFor();assert.equal(states[0].stars,3);
  failWrite=true;await page.click('[data-star="4"]');await page.locator('#syncNotice').filter({hasText:'未保存'}).waitFor();assert.equal(states[0].stars,3);failWrite=false;
  await page.click('#actDone');await page.locator('#mask.show').waitFor({state:'hidden'});assert(states[0].archived);
  await page.reload();await page.locator('#grid .cell.archived').waitFor();
  await page.click('[data-mode="sentences"]');await page.locator('.sent-preview').click();assert((await page.locator('#modal').innerText()).includes('结构简析'));await page.click('#closeBtn');
  await page.click('[data-mode="search"]');await page.fill('#searchInput','reluctant');await page.locator('#searchMain .cell').click({button:'right'});await page.click('#ctxDelete');await page.locator('#syncNotice').filter({hasText:'已同步'}).waitFor();assert(states.some(x=>x.word==='reluctant'&&x.deleted));
  const keys=await page.evaluate(()=>Object.keys(localStorage));assert(keys.every(x=>x.startsWith('vocab_kit_auth_')));
  await page.click('#logoutButton');await page.locator('#authPanel').waitFor();assert.equal(await page.locator('#appMain').isVisible(),false);assert(!(await page.locator('body').innerText()).includes('sustain'));
  await login();await page.locator('#grid .cell').first().waitFor();expired=true;await page.evaluate(()=>window.dispatchEvent(new Event('vocab-auth-error')));await page.locator('#authPanel').waitFor();assert.equal(await page.locator('#appMain').isVisible(),false);
  assert.deepEqual(errors,[]);console.log('PASS: login gate, stranger denial, empty start, mobile/desktop layout, word/sentence cards, XSS escaping, stars, failed save, archive/delete persistence, logout and expired session. APIs simulated; no production access.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1});
