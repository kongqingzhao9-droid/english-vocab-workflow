(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const cfg = window.APP_CONFIG || {};
  let client, mounted = false, busy = false, generation = 0;
  const storageKey = 'vocab_kit_auth_' + (cfg.supabaseUrl || '').replace(/\W/g, '_');
  function lock(message) {
    generation++;
    if (window.disposeVocabApp) window.disposeVocabApp();
    $('appMain').hidden = $('privateNav').hidden = $('accountBar').hidden = true;
    $('authPanel').hidden = false;
    $('modal').replaceChildren(); $('mask').classList.remove('show'); $('ctx').style.display = 'none';
    document.body.classList.remove('paged'); document.documentElement.classList.remove('paged');
    $('password').value = '';
    $('authMessage').textContent = message;
  }
  async function load() {
    if (busy) return;
    busy = true;
    const version = generation;
    try {
      const { data: { user }, error } = await client.auth.getUser();
      if (error || !user) throw Error('登录已失效，请重新登录。');
      const owner = await client.rpc('vocab_kit_is_owner');
      if (owner.error || owner.data !== true) throw Error('该账号没有访问此词库的权限。');
      if (version !== generation) return;
      if (mounted) return;
      $('authMessage').textContent = '正在读取私人词库…';
      const result = await client.from('vocab_kit_library').select('payload').eq('id', true).single();
      if (result.error || !result.data?.payload) throw Error('词库读取失败，请检查网络或首次配置。');
      window.VocabSync.configure(client);
      const remote = await window.VocabSync.fetchAll();
      if (version !== generation) return;
      await window.startVocabApp(result.data.payload, remote);
      $('authPanel').hidden = true;
      $('appMain').hidden = $('privateNav').hidden = $('accountBar').hidden = false;
      mounted = true;
      $('password').value = '';
    } catch (error) {
      lock(error.message || '暂时无法登录，请稍后重试。');
      if (mounted) location.reload();
    } finally { busy = false; }
  }
  $('loginForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!client) return;
    $('loginButton').disabled = true;
    $('authMessage').textContent = '正在登录…';
    try {
      const { error } = await client.auth.signInWithPassword({ email: $('email').value.trim(), password: $('password').value });
      $('password').value = '';
      if (error) throw Error('登录失败，请检查邮箱、密码和网络。');
      await load();
    } catch (error) { $('authMessage').textContent = error.message; }
    finally { $('loginButton').disabled = false; }
  });
  $('logoutButton').addEventListener('click', async () => {
    lock('正在退出…');
    try { await client.auth.signOut({ scope: 'local' }); }
    finally {
      localStorage.removeItem(storageKey);
      localStorage.removeItem(storageKey + '-code-verifier');
      location.reload();
    }
  });
  async function boot() {
    try {
      if (!window.supabase || !cfg.supabaseUrl || !cfg.supabaseAnonKey) throw Error('尚未配置私人网站。请先在电脑 Codex 中完成初始化。');
      if ('serviceWorker' in navigator && location.protocol !== 'file:') await navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' });
      client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storageKey },
        global: { fetch: (input, init = {}) => fetch(input, { ...init, cache: 'no-store' }) }
      });
      client.auth.onAuthStateChange(event => {
        if (event === 'SIGNED_OUT') { lock('已退出，请重新登录。'); if (mounted) location.reload(); }
        if (event === 'SIGNED_IN') setTimeout(load, 0);
      });
      const { data: { session } } = await client.auth.getSession();
      if (session) await load(); else $('authMessage').textContent = '请登录后查看私人词库。';
      window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && mounted) load(); });
      window.addEventListener('vocab-auth-error', load);
    } catch (error) { lock(error.message || '初始化失败，请刷新重试。'); }
  }
  boot();
})();
