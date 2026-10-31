'use strict';
window.startVocabApp = async function(payload, remote) {
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function clean(value) {
    if (typeof value === 'string') return escape(value);
    if (Array.isArray(value)) return value.map(clean);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, clean(v)]));
    return value;
  }
  if (!Array.isArray(payload.vocab) || !Array.isArray(payload.sentences)) throw Error('词库格式错误');
  const DATA = clean(payload);
  DATA.vocab.forEach((entry, i) => {
    const word = payload.vocab[i].word;
    if (typeof word !== 'string' || !/^[A-Za-z][A-Za-z '\u2019-]*$/.test(word)) throw Error('词库含有不支持的单词格式');
    entry.word = word;
  });
  DATA.sentences.forEach(entry => { if (!/^\d+$/.test(String(entry.id))) throw Error('句子编号格式错误'); });

    let mode = "memorize";
    let query = "";
    let ctxWord = null;
    let page = 1;
    let wordPageSize = 27;
    let sentencePageSize = 1;
    let focusedWord = null;
    let focusedSentence = null;
    const modePositions = {};
    let pageAnimations = [];
    let pageGhost = null;

    function clearPageAnimation() {
      pageAnimations.forEach(a => a.cancel());
      pageAnimations = [];
      if (pageGhost) pageGhost.remove();
      pageGhost = null;
    }

    function totalPages() {
      const count = mode === "sentences" ? DATA.sentences.length : sortedVocab().length;
      return Math.max(1, Math.ceil(count / (mode === "sentences" ? sentencePageSize : wordPageSize)));
    }

    function fitPage(preservePosition = true) {
      if (mode === "search") return;
      const isSent = mode === "sentences";
      const list = isSent ? DATA.sentences.slice().reverse() : sortedVocab();
      const oldSize = isSent ? sentencePageSize : wordPageSize;
      const focused = isSent ? focusedSentence : focusedWord;
      let anchor = preservePosition && focused != null
        ? list.findIndex(v => (isSent ? v.id : v.word) === focused) : -1;
      if (anchor < 0) anchor = (page - 1) * oldSize;
      const pager = document.getElementById("pager");
      document.body.style.setProperty("--pager-height", (pager.getBoundingClientRect().height || 60) + "px");
      const box = document.getElementById(isSent ? "sentList" : "grid");
      const { width, height } = box.getBoundingClientRect();
      if (isSent) sentencePageSize = Math.max(1, Math.floor((height + 10) / 122));
      else {
        const columns = Math.max(1, Math.floor((width + 10) / (window.innerWidth <= 560 ? 100 : 128)));
        const rows = Math.max(1, Math.floor((height + 10) / 86));
        wordPageSize = columns * rows;
        box.style.setProperty("--word-columns", columns);
        box.style.setProperty("--word-rows", rows);
      }
      const size = isSent ? sentencePageSize : wordPageSize;
      if (preservePosition) page = Math.floor(anchor / size) + 1;
      page = Math.min(Math.max(1, page), totalPages());
    }

    function goToPage(value) {
      if (mode === "search") return;
      cancelLongPress();
      hideWordMenu();
      const next = Math.min(totalPages(), Math.max(1, Math.trunc(Number(value)) || page));
      if (next === page) { updatePager(page, totalPages()); return; }
      clearPageAnimation();
      const panel = document.getElementById(mode === "sentences" ? "sentList" : "grid");
      const direction = next > page ? -1 : 1;
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!reduced && panel.animate) {
        const rect = panel.getBoundingClientRect();
        pageGhost = panel.cloneNode(true);
        pageGhost.removeAttribute("id");
        pageGhost.querySelectorAll("[id]").forEach(el => el.removeAttribute("id"));
        pageGhost.setAttribute("aria-hidden", "true");
        pageGhost.classList.add("page-ghost");
        Object.assign(pageGhost.style, { left: rect.left + "px", top: rect.top + "px",
          width: rect.width + "px", height: rect.height + "px" });
        document.body.appendChild(pageGhost);
      }
      page = next;
      focusedWord = null; focusedSentence = null;
      if (mode === "sentences") renderSentences(); else renderSimple();
      window.scrollTo({ top: 0, behavior: "instant" });
      if (pageGhost) {
        const outgoing = pageGhost.animate([
          { transform: "translateX(0) scale(1)", opacity: 1 },
          { transform: `translateX(${direction * 90}px) scale(.96)`, opacity: 0 }
        ], { duration: 240, easing: "ease-in", fill: "forwards" });
        const incoming = panel.animate([
          { transform: `translateX(${-direction * 24}px) scale(.96)`, opacity: .25 },
          { transform: "translateX(0) scale(1)", opacity: 1 }
        ], { duration: 300, easing: "cubic-bezier(.2,.7,.2,1)" });
        pageAnimations = [outgoing, incoming];
        incoming.onfinish = clearPageAnimation;
      }
    }

    function nowMs() { return Date.now(); }

    let state = Object.create(null);
    let deleted = new Set();
    let saving = false, disposed = false;
    DATA.vocab.forEach(v => {
      const row = remote[v.word] || v;
      state[v.word] = { stars: row.stars || 0, archived: !!row.archived };
      if (row.deleted) deleted.add(v.word);
    });
    window.disposeVocabApp = () => {
      disposed = true;
      clearPageAnimation();
      DATA.vocab.length = 0; DATA.sentences.length = 0;
      state = Object.create(null); deleted.clear();
      document.querySelectorAll('#grid,#sentList,#searchMain,#alpha,#modal').forEach(el => el.replaceChildren());
    };
    async function commit(word, patch) {
      if (disposed || saving) return false;
      saving = true;
      const notice = document.getElementById('syncNotice');
      notice.textContent = '正在保存…';
      const next = Object.assign({}, state[word] || { stars: 0, archived: false }, patch);
      const isDeleted = patch.deleted === undefined ? deleted.has(word) : patch.deleted;
      try {
        await VocabSync.push(word, next.stars || 0, !!next.archived, !!isDeleted);
        if (disposed) return false;
        state[word] = next;
        if (isDeleted) deleted.add(word); else deleted.delete(word);
        notice.textContent = '已同步';
        return true;
      } catch (error) {
        notice.textContent = '未保存，请检查网络后重试。';
        if (error.code === '42501' || error.status === 401 || error.status === 403)
          window.dispatchEvent(new Event('vocab-auth-error'));
        return false;
      } finally { saving = false; }
    }
    function getSt(word) { return state[word] || { stars: 0, archived: false }; }
    function withState(v) { return Object.assign({}, v, getSt(v.word)); }

    function starIcons(n, off) {
      let s = "";
      for (let i = 1; i <= 5; i++) s += i <= n ? "★" : "<span class='off'>★</span>";
      return s;
    }

    function sortedVocab() {
      const vs = DATA.vocab.map(withState).filter(v => !deleted.has(v.word));
      if (mode === "memorize") return vs.slice().sort((a, b) => a.order - b.order);
      if (mode === "review")
        return vs.filter(v => v.archived)
          .sort((a, b) => b.stars - a.stars || a.word.localeCompare(b.word));
      const q = query.trim().toLowerCase();
      return vs.filter(v => !q || v.word.toLowerCase().includes(q))
        .sort((a, b) => a.word.localeCompare(b.word));
    }

    function cellHtml(v, locked) {
      const cls = "cell" + (locked ? " archived locked" : "");
      return `<div class="${cls}" data-word="${v.word}">
        <div class="w">${v.word}</div>
        <div class="stars">${starIcons(v.stars)}</div>
      </div>`;
    }

    function renderSimple() {
      const grid = document.getElementById("grid");
      const hint = document.getElementById("modeHint");
      const list = sortedVocab();
      hint.textContent = mode === "memorize"
        ? "按学习时间顺序排列 · 灰色为已背单词（不可查看） · 点击卡片查看详情"
        : "已背单词 · 按星级从高到低排列，同星级按字母顺序 · 点击可查看或调整星级";
      const totalPages = Math.max(1, Math.ceil(list.length / wordPageSize));
      if (page < 1) page = 1;
      if (page > totalPages) page = totalPages;
      if (!list.length) {
        grid.innerHTML = '<div class="empty">' + (mode === 'review' ? '还没有已背单词。完成学习后，它们会出现在这里。' : '你的生词本，从这里开始。<br>上传标注 PDF 后，在电脑 Codex 中发送“收录雅思词汇”；<br>在指定对话里询问新词后，发送“收录其他词汇”。<br>收录完成后刷新本页。') + '</div>';
        setPagerVisible(false);
        return;
      }
      setPagerVisible(true);
      const start = (page - 1) * wordPageSize;
      grid.innerHTML = list.slice(start, start + wordPageSize)
        .map(v => cellHtml(v, mode === "memorize" && v.archived)).join("");
      updatePager(page, totalPages);
    }

    function setPagerVisible(show) {
      document.getElementById("pager").style.display = show ? "" : "none";
    }

    function updatePager(cur, total) {
      const slider = document.getElementById("pageSlider");
      const input = document.getElementById("pageInput");
      const totalEl = document.getElementById("pagerTotal");
      slider.max = total;
      slider.value = cur;
      const pct = total <= 1 ? 100 : ((cur - 1) / (total - 1)) * 100;
      slider.style.background = "linear-gradient(to right, var(--accent) " + pct + "%, var(--border) " + pct + "%)";
      input.max = total;
      input.value = cur;
      totalEl.textContent = "/ " + total;
    }

    function renderSearch() {
      const main = document.getElementById("searchMain");
      const alpha = document.getElementById("alpha");
      const list = sortedVocab();
      if (!list.length) { main.innerHTML = '<div class="empty">没有匹配的单词。</div>'; alpha.innerHTML = ""; return; }
      const groups = {};
      list.forEach(v => {
        const k = /^[a-zA-Z]/.test(v.word) ? v.word[0].toUpperCase() : "#";
        (groups[k] = groups[k] || []).push(v);
      });
      main.innerHTML = Object.keys(groups).sort((a, b) =>
        (a === "#" ? 1 : b === "#" ? -1 : a.localeCompare(b))).map(k =>
        `<div class="group" id="grp-${k}"><h2>${k}</h2>
          <div class="grid">${groups[k].map(v => cellHtml(v, false)).join("")}</div></div>`).join("");
      alpha.innerHTML = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map(c =>
        `<button data-letter="${c}">${c}</button>`).join("");
    }

    function render() {
      if (disposed) return;
      cancelLongPress();
      clearPageAnimation();
      const isSearch = mode === "search";
      const isSent = mode === "sentences";
      document.documentElement.classList.toggle("paged", !isSearch);
      document.body.classList.toggle("paged", !isSearch);
      document.getElementById("searchBar").style.display = isSearch ? "" : "none";
      document.getElementById("searchLayout").style.display = isSearch ? "" : "none";
      document.getElementById("simplePanel").style.display = (isSearch || isSent) ? "none" : "";
      document.getElementById("sentPanel").style.display = isSent ? "" : "none";
      setPagerVisible(!isSearch);
      fitPage();
      document.querySelectorAll(".tab").forEach(t =>
        t.classList.toggle("active", t.dataset.mode === mode));
      if (isSearch) renderSearch();
      else if (isSent) renderSentences();
      else renderSimple();
    }

    function renderSentences() {
      const box = document.getElementById("sentList");
      if (!DATA.sentences.length) {
        box.innerHTML = '<div class="empty">还没有长难句。</div>';
        setPagerVisible(false); return;
      }
      page = Math.min(Math.max(1, page), totalPages());
      setPagerVisible(true);
      updatePager(page, totalPages());
      const start = (page - 1) * sentencePageSize;
      box.innerHTML = DATA.sentences.slice().reverse().slice(start, start + sentencePageSize).map(s => `
        <button class="sent-preview" data-sentence="${s.id}" aria-label="查看长难句全文、翻译与解析">
          <div class="orig">${s.original}</div>
        </button>`).join("");
      box.querySelectorAll(".sent-preview").forEach(card => {
        const text = card.querySelector(".orig");
        card.classList.toggle("truncated", text.scrollHeight > text.clientHeight + 1);
      });
    }

    function openSentence(id) {
      const s = DATA.sentences.find(item => String(item.id) === String(id));
      if (!s) return;
      focusedSentence = s.id;
      const modal = document.getElementById("modal");
      delete modal.dataset.word;
      modal.innerHTML = `<button class="modal-close" id="closeBtn" aria-label="关闭">×</button>
        <div class="sent"><h4>长难句原文</h4><div class="orig">${s.original}</div>
        <h4>中文翻译</h4><div class="trans">${s.translation}</div>
        <h4>结构简析</h4><div class="main">${s.main}</div>
        <ul>${s.clauses.map(c => `<li>${c}</li>`).join("")}</ul></div>`;
      document.getElementById("mask").classList.add("show");
      modal.scrollTop = 0;
      document.getElementById("closeBtn").onclick = closeModal;
    }

    function openModal(word) {
      focusedWord = word;
      const v = withState(DATA.vocab.find(x => x.word === word));
      const modal = document.getElementById("modal");
      modal.innerHTML = `
        <button class="modal-close" id="closeBtn">×</button>
        <div class="head"><span class="mw">${v.word}</span><span class="mp">${v.phonetic}</span>
          <span class="tag">${v.pos}</span></div>
        ${v.phrase ? `<div class="phrase">📎 常用短语：<b>${v.phrase}</b></div>` : ""}
        <h4>英文释义</h4><div class="en def-en">${v.defEn}</div>
        <h4>中文释义 <button class="expand-btn" id="expandCn">展开</button></h4>
        <div id="cnMeanings" style="display:none;">${v.meanings.join("；")}</div>
        <h4>用法</h4><div>${v.usage}</div>
        <h4>例句</h4><div class="en">${v.example}</div><div class="cn">${v.exampleCn}</div>
        <h4>词根词缀</h4>
        ${v.prefix ? `<div><b>前缀</b>：${v.prefix}</div>` : ""}
        <div><b>词根</b>：${v.root}</div>
        ${v.suffix ? `<div><b>后缀</b>：${v.suffix}</div>` : ""}
        ${v.synonyms.length ? `<h4>近义词</h4><div>${v.synonyms.map(s => `<span class="chip">${s}</span>`).join("")}</div>` : ""}
        ${v.derivatives.length ? `<h4>衍生词</h4><div>${v.derivatives.join("；")}</div>` : ""}
        <div class="star-picker">
          <span class="lab">我的星级：</span>
          ${[1,2,3,4,5].map(i => `<button data-star="${i}" class="${i <= v.stars ? 'on' : ''}">★</button>`).join("")}
          <span style="font-size:12px;color:var(--muted)">${v.stars} 星（点同一颗星可清零）</span>
        </div>
        ${(mode === "memorize" && !v.archived)
          ? `<div class="actions"><button class="btn primary" id="actDone">归档到已背</button></div>`
          : ""}`;
      document.getElementById("mask").classList.add("show");
      modal.scrollTop = 0;
      modal.dataset.word = word;

      document.getElementById("closeBtn").onclick = closeModal;
      const cnBtn = document.getElementById("expandCn");
      const cnBox = document.getElementById("cnMeanings");
      if (cnBtn && cnBox) cnBtn.onclick = () => {
        const hidden = cnBox.style.display === "none";
        cnBox.style.display = hidden ? "" : "none";
        cnBtn.textContent = hidden ? "收起" : "展开";
      };
      modal.querySelectorAll(".star-picker button").forEach(b => b.onclick = async () => {
        const n = +b.dataset.star;
        const cur = getSt(word).stars;
        if (!await commit(word, { stars: (cur === n) ? 0 : n })) return;
        render(); openModal(word);
      });
      const done = document.getElementById("actDone");
      if (done) done.onclick = async () => { if (await commit(word, { archived: true })) closeModal(); };
    }
    function closeModal() {
      document.getElementById("mask").classList.remove("show");
      render();
    }

    document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
      if (mode === t.dataset.mode) return;
      if (mode !== "search") {
        const isSent = mode === "sentences";
        const size = isSent ? sentencePageSize : wordPageSize;
        const list = isSent ? DATA.sentences.slice().reverse() : sortedVocab();
        const first = list[(page - 1) * size];
        modePositions[mode] = { page, size, anchor: first ? (isSent ? first.id : first.word) : null };
      }
      hideWordMenu();
      mode = t.dataset.mode;
      const saved = modePositions[mode];
      page = saved ? saved.page : 1;
      focusedWord = null; focusedSentence = null;
      if (saved) {
        if (mode === "sentences") { sentencePageSize = saved.size; focusedSentence = saved.anchor; }
        else { wordPageSize = saved.size; focusedWord = saved.anchor; }
      }
      window.scrollTo(0, 0); render();
    }));

    document.getElementById("grid").addEventListener("click", e => {
      const cell = e.target.closest(".cell");
      if (!cell) return;
      const word = cell.dataset.word;
      const v = withState(DATA.vocab.find(x => x.word === word));
      if (mode === "memorize" && v.archived) return;   // 已背不可查看
      openModal(word);
    });
    document.getElementById("sentList").addEventListener("click", e => {
      const card = e.target.closest(".sent-preview");
      if (card) openSentence(card.dataset.sentence);
    });

    document.getElementById("searchMain").addEventListener("click", e => {
      const cell = e.target.closest(".cell");
      if (cell) openModal(cell.dataset.word);
    });
    document.getElementById("alpha").addEventListener("click", e => {
      const b = e.target.closest("button");
      if (!b) return;
      const el = document.getElementById("grp-" + b.dataset.letter);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    document.getElementById("searchInput").addEventListener("input", e => {
      query = e.target.value; renderSearch();
    });

    document.getElementById("pageSlider").addEventListener("input", e => {
      goToPage(e.target.value);
    });
    document.getElementById("pageInput").addEventListener("change", e => {
      goToPage(e.target.value);
    });
    document.getElementById("pageInput").addEventListener("keydown", e => {
      if (e.key === "Enter") e.target.blur();
    });

    let swipe = null;
    let suppressClickUntil = 0;
    let longPress = null;
    let longPressTimer = null;
    let longPressOpened = false;
    function cancelLongPress() {
      clearTimeout(longPressTimer);
      longPressTimer = null;
      longPress = null;
    }
    function hideWordMenu() {
      document.getElementById("ctx").style.display = "none";
      ctxWord = null;
    }
    function menuCell(target) {
      if (mode !== "search" && mode !== "memorize") return null;
      const cell = target.closest(mode === "search" ? "#searchMain .cell" : "#grid .cell");
      return cell && !document.getElementById("mask").classList.contains("show") ? cell : null;
    }
    function showWordMenu(cell, x, y) {
      ctxWord = cell.dataset.word;
      document.getElementById("ctxUnarchive").style.display = getSt(ctxWord).archived ? "" : "none";
      const ctx = document.getElementById("ctx");
      ctx.style.display = "block";
      const rect = ctx.getBoundingClientRect();
      ctx.style.left = Math.max(8, Math.min(x, window.innerWidth - rect.width - 8)) + "px";
      ctx.style.top = Math.max(8, Math.min(y, window.innerHeight - rect.height - 8)) + "px";
    }
    const swipeBlocked = target => mode === "search" ||
      document.getElementById("mask").classList.contains("show") ||
      !!target.closest("input, button:not(.sent-preview), a, textarea, select, #pager, #ctx, .modal-mask");
    document.addEventListener("touchstart", e => {
      cancelLongPress();
      longPressOpened = false;
      swipe = null;
      if (e.touches.length === 1) {
        const cell = menuCell(e.target);
        if (cell) {
          const { clientX: x, clientY: y } = e.touches[0];
          longPress = { x, y };
          longPressTimer = setTimeout(() => {
            cancelLongPress();
            swipe = null;
            longPressOpened = true;
            showWordMenu(cell, x, y);
          }, 500);
        }
      }
      if (e.touches.length !== 1 || swipeBlocked(e.target)) return;
      const t = e.touches[0];
      swipe = { x: t.clientX, y: t.clientY, time: Date.now(), mode, axis: null };
    }, { passive: true });
    document.addEventListener("touchmove", e => {
      if (longPress && (e.touches.length !== 1 ||
        Math.hypot(e.touches[0].clientX - longPress.x, e.touches[0].clientY - longPress.y) > 10)) cancelLongPress();
      if (!swipe) return;
      if (e.touches.length !== 1) { swipe = null; return; }
      const dx = Math.abs(e.touches[0].clientX - swipe.x), dy = Math.abs(e.touches[0].clientY - swipe.y);
      if (!swipe.axis && Math.max(dx, dy) > 12) swipe.axis = dx > dy * 1.3 ? "x" : "y";
    }, { passive: true });
    document.addEventListener("touchcancel", () => {
      cancelLongPress(); swipe = null;
      if (longPressOpened) suppressClickUntil = Date.now() + 400;
      longPressOpened = false;
    }, { passive: true });
    document.addEventListener("touchend", e => {
      cancelLongPress();
      if (longPressOpened) {
        suppressClickUntil = Date.now() + 400;
        longPressOpened = false;
        swipe = null;
        return;
      }
      const start = swipe;
      swipe = null;
      if (!start || start.axis === "y" || !e.changedTouches.length || start.mode !== mode || swipeBlocked(e.target)) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - start.x, dy = t.clientY - start.y;
      if (Date.now() - start.time > 900 || Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      suppressClickUntil = Date.now() + 400;
      goToPage(page + (dx < 0 ? 1 : -1));
    }, { passive: true });
    document.addEventListener("click", e => {
      if (Date.now() < suppressClickUntil && !e.target.closest("#ctx")) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);

    // 记忆和检索模式：触屏长按或电脑右键。
    document.addEventListener("contextmenu", e => {
      const cell = menuCell(e.target);
      if (!cell) return;
      e.preventDefault();
      cancelLongPress(); swipe = null;
      if (e.pointerType === "touch" || longPressOpened) longPressOpened = true;
      showWordMenu(cell, e.clientX, e.clientY);
    });
    document.getElementById("ctxUnarchive").onclick = async () => {
      if (ctxWord) { if (!await commit(ctxWord, { archived: false })) return; ctxWord = null; }
      document.getElementById("ctx").style.display = "none";
      render();
    };
    document.getElementById("ctxDelete").onclick = async () => {
      if (ctxWord) {
        if (!await commit(ctxWord, { deleted: true })) return;
        ctxWord = null;
      }
      document.getElementById("ctx").style.display = "none";
      render();
    };
    document.addEventListener("click", e => {
      if (!e.target.closest("#ctx")) hideWordMenu();
    });
    document.addEventListener("scroll", () => { cancelLongPress(); hideWordMenu(); }, { passive: true, capture: true });
    window.addEventListener("blur", () => { cancelLongPress(); hideWordMenu(); });
    document.getElementById("mask").addEventListener("click", e => {
      if (e.target === e.currentTarget) closeModal();
    });

    let resizeFrame = 0;
    function scheduleFit() {
      cancelLongPress(); hideWordMenu();
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (mode !== "search") render();
      });
    }
    window.addEventListener("resize", scheduleFit);
    if (window.visualViewport) window.visualViewport.addEventListener("resize", scheduleFit);
    const layoutObserver = new ResizeObserver(scheduleFit);
    layoutObserver.observe(document.querySelector("main"));
    layoutObserver.observe(document.querySelector("header"));
    layoutObserver.observe(document.getElementById("pager"));
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
    render();


};
