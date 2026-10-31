// Private API: no anonymous fallback and no vocabulary/state persisted in browser storage.
(() => {
  let client;
  function configure(value) { client = value; }
  async function fetchAll() {
    if (!client) throw Error('请先登录');
    const map = Object.create(null);
    for (let offset = 0; ; offset += 1000) {
      const { data, error } = await client.from('vocab_kit_state')
        .select('word,stars,archived,deleted,updated_at').order('word').range(offset, offset + 999);
      if (error) throw error;
      for (const row of data) map[row.word] = row;
      if (data.length < 1000) return map;
    }
  }
  async function push(word, stars, archived, deleted) {
    if (!client) throw Error('请先登录');
    const { error } = await client.from('vocab_kit_state')
      .upsert({ word, stars, archived, deleted }, { onConflict: 'word' });
    if (error) throw error;
  }
  window.VocabSync = { configure, fetchAll, push };
})();
