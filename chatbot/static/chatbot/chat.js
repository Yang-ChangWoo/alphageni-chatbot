// 상담 라운지 채팅 화면. 모든 텍스트는 textContent로 넣어 HTML이 실행되지 않게 합니다.
(() => {
  const C = window.CHAT;
  const stream = document.getElementById('chat-stream');
  const input = document.getElementById('user-input');
  const sendBtn = document.getElementById('send-button');
  const count = document.getElementById('char-count');
  const showScore = document.getElementById('show-score');
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  let busy = false;

  try { showScore.checked = localStorage.getItem('showScore') === '1'; } catch (e) {}
  showScore.addEventListener('change', () => {
    try { localStorage.setItem('showScore', showScore.checked ? '1' : '0'); } catch (e) {}
    document.querySelectorAll('.score-panel').forEach(p => p.classList.toggle('hidden', !showScore.checked));
  });

  // ------------------------------------------------------------------ DOM 도우미
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function icon(name, cls = 'text-[18px]') { return el('span', 'material-symbols-outlined ' + cls, name); }
  function now() { return new Date().toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' }); }
  function scrollDown() { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }

  // URL은 링크로, 나머지는 글자 그대로
  function linkify(text) {
    const frag = document.createDocumentFragment();
    const re = /https?:\/\/[^\s|)\]]+/g;
    let last = 0, m;
    while ((m = re.exec(text))) {
      frag.append(text.slice(last, m.index));
      const a = el('a', 'text-secondary underline underline-offset-2 break-all hover:text-primary', m[0]);
      a.href = m[0]; a.target = '_blank'; a.rel = 'noopener noreferrer';
      frag.append(a);
      last = m.index + m[0].length;
    }
    frag.append(text.slice(last));
    return frag;
  }

  function chip(label, onClick, { iconName, primary = false } = {}) {
    const b = el('button', primary
      ? 'px-3 py-1.5 rounded-full bg-primary text-on-primary font-label-sm text-label-sm shadow-sm hover:opacity-95 transition-opacity flex items-center gap-1'
      : 'px-3 py-1.5 rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors font-label-sm text-label-sm flex items-center gap-1');
    b.type = 'button';
    if (iconName) b.append(icon(iconName, 'text-[16px]'));
    b.append(label);
    b.addEventListener('click', onClick);
    return b;
  }

  // ------------------------------------------------------------------ 말풍선
  function addUser(text) {
    const wrap = el('div', 'flex items-start gap-space-md max-w-3xl self-end flex-row-reverse animate-fadeIn');
    const av = el('div', 'w-10 h-10 rounded-full bg-primary text-on-primary flex-shrink-0 flex items-center justify-center shadow-sm');
    av.append(icon('person', 'text-[20px]'));
    const col = el('div', 'flex flex-col gap-space-2xs items-end min-w-0');
    const head = el('div', 'flex items-center gap-space-xs flex-row-reverse');
    head.append(el('span', 'font-title-md text-title-md font-bold text-on-surface', '지원자님'),
                el('span', 'font-label-sm text-label-sm text-on-surface-variant', now()));
    const bubble = el('div', 'bg-primary-container text-on-primary px-space-lg py-space-md rounded-2xl shadow-sm rounded-tr-none');
    bubble.append(el('p', 'font-body-md text-body-md leading-relaxed font-medium whitespace-pre-line break-words', text));
    col.append(head, bubble);
    wrap.append(av, col);
    stream.append(wrap);
    scrollDown();
  }

  // badge: {text, cls}
  function addBot(badge, ...nodes) {
    const wrap = el('div', 'flex items-start gap-space-md max-w-4xl animate-fadeIn');
    const av = el('div', 'w-10 h-10 rounded-full bg-primary-container/20 flex-shrink-0 flex items-center justify-center p-0.5 shadow-sm');
    const img = el('img', 'w-full h-full object-contain rounded-full'); img.src = C.mascot; img.alt = '알파지니';
    av.append(img);
    const col = el('div', 'flex flex-col gap-space-xs w-full max-w-3xl min-w-0');
    const head = el('div', 'flex items-center gap-space-xs flex-wrap');
    head.append(el('span', 'font-title-md text-title-md font-bold text-on-surface', '알파지니'));
    if (badge) head.append(el('span', 'font-label-sm text-label-sm font-semibold px-2 py-0.5 rounded-full ' + badge.cls, badge.text));
    head.append(el('span', 'font-label-sm text-label-sm text-on-surface-variant', now()));
    const card = el('div', 'bg-surface-container-lowest text-on-surface p-space-lg md:p-space-xl rounded-2xl rounded-tl-sm card-1 soft-border flex flex-col gap-space-md');
    card.append(...nodes);
    col.append(head, card);
    wrap.append(av, col);
    stream.append(wrap);
    scrollDown();
    return card;
  }

  function addTyping() {
    const p = el('div', 'flex items-center gap-1.5 text-on-surface-variant font-body-sm text-body-sm');
    for (let i = 0; i < 3; i++) {
      const d = el('span', 'w-2 h-2 rounded-full bg-primary-container animate-bounce');
      d.style.animationDelay = (i * 0.15) + 's';
      p.append(d);
    }
    p.append(el('span', 'ml-2', 'FAQ에서 찾는 중이에요'));
    const card = addBot(null, p);
    return card.parentElement.parentElement;
  }

  const BADGE = {
    HIGH: { text: '정확한 답변 · HIGH', cls: 'bg-emerald-50 text-emerald-700' },
    MID: { text: '후보 선택 · MID', cls: 'bg-secondary-fixed text-on-secondary-fixed-variant' },
    LOW: { text: '다시 질문 · LOW', cls: 'bg-primary-fixed text-primary' },
    PICK: { text: '선택한 질문의 답변', cls: 'bg-emerald-50 text-emerald-700' },
    INFO: { text: '안내', cls: 'bg-surface-container text-on-surface-variant' },
  };

  // ------------------------------------------------------------------ 결과 조각
  // 사전 자동 점검 결과: 비속어 제거, 줄임말 확장, 다의어
  function understood(r) {
    const items = [];
    (r.profanity_removed || []).forEach(w => items.push(['block', `비속어 '${w}' 제외`]));
    (r.masked || []).forEach(w => items.push(['visibility_off', `'${w}' 표시만`]));
    (r.abbr_expanded || []).forEach(([a, b]) => items.push(['spellcheck', `${a} → ${b}`]));
    (r.abbr_ambiguous || []).forEach(([a, opts]) => items.push(['alt_route', `${a}: ${opts.join(' / ')} 모두 검색`]));
    if (!items.length) return null;
    const box = el('div', 'flex flex-wrap items-center gap-1.5 font-label-sm text-label-sm');
    box.append(el('span', 'text-on-surface-variant mr-1', '이렇게 이해했어요'));
    items.forEach(([ic, t]) => {
      const c = el('span', 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant');
      c.append(icon(ic, 'text-[14px]'), t);
      box.append(c);
    });
    if (r.normalized && r.normalized !== r.query) {
      const n = el('span', 'w-full text-on-surface-variant mt-0.5');
      n.append('검색 문장: ', el('span', 'text-on-surface font-medium', r.normalized));
      box.append(n);
    }
    return box;
  }

  function scorePanel(r) {
    const p = el('div', 'score-panel rounded-xl bg-surface-container-low p-space-md font-body-sm text-body-sm flex flex-col gap-1.5' + (showScore.checked ? '' : ' hidden'));
    const head = el('div', 'flex items-center gap-1.5 font-label-md text-label-md text-secondary');
    head.append(icon('analytics', 'text-[18px]'), `판정 근거: ${r.reason}`);
    p.append(head);
    p.append(el('div', 'text-on-surface-variant',
      `1위 ${r.top1_score.toFixed(3)} · 1·2위 차 ${r.gap.toFixed(3)} · 기준 HIGH ≥ 0.75 & 차 ≥ 0.05, LOW < 0.43 · ${r.mode.startsWith('embedding+fuzzy') ? '임베딩 0.8 + 퍼지 0.2' : '퍼지 전용(모델 없음)'}`));
    if (r.candidates.length) {
      const t = el('table', 'w-full min-w-[560px] mt-1 tabular-nums');
      const hr = el('tr', 'text-on-surface-variant text-left');
      ['', 'FAQ', '가장 가까운 표현', '최종', '임베딩', '퍼지'].forEach(h => hr.append(el('th', 'font-medium pr-2 py-0.5', h)));
      t.append(hr);
      r.candidates.forEach((c, i) => {
        const tr = el('tr', 'border-t border-[#F5E6E8] align-top');
        [String(i + 1), c.faq_id, c.matched_text, c.score.toFixed(3), c.semantic.toFixed(3), c.fuzzy.toFixed(3)]
          .forEach((v, k) => tr.append(el('td', 'pr-2 py-1' + (k === 2 ? ' text-on-surface' : ' whitespace-nowrap'), v)));
        t.append(tr);
      });
      const sc = el('div', 'overflow-x-auto'); sc.append(t); p.append(sc);
    }
    return p;
  }

  function sourceBox(c) {
    const box = el('div', 'bg-gradient-to-r from-[#fff3f5] to-surface-container-lowest p-space-md rounded-xl flex flex-col gap-space-xs');
    const h = el('span', 'font-label-md text-label-md font-bold text-on-surface flex items-center gap-1');
    h.append(icon('fact_check', 'text-primary text-[18px]'), '출처');
    box.append(h);
    const rows = [['질문 출처', c.source], ['근거 자료', c.evidence]].filter(([, v]) => v);
    if (!rows.length) rows.push(['출처', '등록된 출처 없음']);
    rows.forEach(([k, v]) => {
      const row = el('div', 'bg-surface-container-lowest p-space-sm rounded-lg font-body-sm text-body-sm leading-relaxed text-on-surface-variant flex gap-2');
      row.append(el('span', 'shrink-0 font-semibold text-on-surface', k));
      const val = el('span', 'min-w-0 break-words'); val.append(linkify(v));
      row.append(val);
      box.append(row);
    });
    return box;
  }

  function answerNodes(c) {
    const title = el('div', 'flex items-start gap-2 text-primary font-title-md text-title-md font-bold');
    title.append(icon('lightbulb', 'text-[22px] mt-0.5'), el('span', '', c.rep_question));
    const meta = el('div', 'flex flex-wrap gap-1.5 font-label-sm text-label-sm -mt-1');
    meta.append(el('span', 'px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant', c.category));
    if (c.job_group) meta.append(el('span', 'px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant', c.job_group));
    meta.append(el('span', 'px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant', c.faq_id));
    const ans = el('p', 'font-body-md text-body-md text-on-surface leading-relaxed whitespace-pre-line', c.answer);
    return [title, meta, ans, sourceBox(c)];
  }

  function actions(...chips) {
    const row = el('div', 'flex flex-wrap items-center gap-space-xs');
    row.append(...chips);
    return row;
  }

  function copyChip(c) {
    const b = chip('답변 복사', () => {
      navigator.clipboard.writeText(`Q. ${c.rep_question}\nA. ${c.answer}\n출처: ${c.source}`).then(() => {
        b.lastChild.textContent = '복사했어요';
        setTimeout(() => { b.lastChild.textContent = '답변 복사'; }, 1500);
      });
    }, { iconName: 'content_copy' });
    return b;
  }

  function showAnswer(c, badge, extra = []) {
    addBot(badge, ...answerNodes(c), actions(copyChip(c), ...extra));
  }

  // ------------------------------------------------------------------ 등급별 응답
  function render(r) {
    const und = understood(r);
    const head = und ? [und] : [];

    if (r.grade === 'HIGH') {
      const c = r.candidates[0];
      const others = r.candidates.slice(1);
      const more = others.length ? [chip('다른 비슷한 질문 보기', () => {
        addBot(BADGE.INFO, el('p', 'font-body-md text-body-md', '이 질문들도 비슷해요. 궁금한 걸 눌러 보세요.'),
          candidateGrid(others, r.query));
      }, { iconName: 'list' })] : [];
      addBot(BADGE.HIGH, ...head, ...answerNodes(c), actions(copyChip(c), ...more), scorePanel(r));
    } else if (r.grade === 'MID') {
      const p = el('p', 'font-body-md text-body-md leading-relaxed');
      p.textContent = '비슷한 질문이 몇 개 있어요. 어떤 걸 물어보신 건지 골라 주세요.';
      addBot(BADGE.MID, ...head, p, candidateGrid(r.candidates, r.query),
        actions(chip('모두 아니에요', () => {
          addUser('모두 아니에요');
          askRephrase();
        }, { iconName: 'close' })), scorePanel(r));
    } else {
      const p = el('p', 'font-body-md text-body-md leading-relaxed');
      p.textContent = r.reason.startsWith('비속어')
        ? '질문 내용을 찾지 못했어요. 궁금한 점을 조금 더 구체적으로 적어 주세요.'
        : '질문을 정확히 이해하지 못했어요. 조금 더 구체적으로 다시 질문해 주세요.';
      addBot(BADGE.LOW, ...head, p, categoryNodes(r.categories), scorePanel(r));
    }
  }

  function candidateGrid(cands, query) {
    const grid = el('div', 'grid grid-cols-1 md:grid-cols-3 gap-space-sm');
    const nums = ['looks_one', 'looks_two', 'looks_3'];
    cands.forEach((c, i) => {
      const b = el('button', 'text-left bg-surface-container-low hover:bg-[#FFF3F5] p-space-md rounded-xl flex flex-col gap-space-xs transition-all border border-transparent hover:border-[rgba(240,98,118,0.25)]');
      b.type = 'button';
      const h = el('span', 'font-label-md text-label-md font-bold flex items-center gap-1.5 ' + (i === 1 ? 'text-secondary' : i === 2 ? 'text-tertiary' : 'text-primary'));
      h.append(icon(nums[i] || 'help', 'text-[18px]'), c.category);
      b.append(h, el('span', 'font-body-sm text-body-sm text-on-surface font-medium', c.rep_question));
      if (c.matched_text && c.matched_text !== c.rep_question) {
        const m = el('span', 'font-label-sm text-label-sm text-on-surface-variant border-t border-[#F5E6E8] pt-1.5 mt-0.5');
        m.append(el('span', 'font-semibold', '가장 비슷한 유사질문 '), c.matched_text);
        b.append(m);
      }
      b.addEventListener('click', () => {
        addUser(c.rep_question);
        showAnswer(c, BADGE.PICK);
      });
      grid.append(b);
    });
    return grid;
  }

  function categoryNodes(cats) {
    const wrap = el('div', 'flex flex-col gap-space-xs');
    wrap.append(el('span', 'font-label-md text-label-md text-on-surface', '이런 주제에 답할 수 있어요'));
    const row = el('div', 'flex flex-wrap gap-space-xs');
    (cats || []).forEach(c => row.append(chip(c.name, () => openCategory(c.name), { iconName: c.icon })));
    wrap.append(row);
    return wrap;
  }

  async function openCategory(name) {
    addUser(`${name} 질문 보여줘`);
    try {
      const r = await fetch(C.category + '?name=' + encodeURIComponent(name));
      const d = await r.json();
      const list = el('div', 'flex flex-col gap-space-xs');
      d.questions.forEach(q => {
        const b = el('button', 'text-left px-space-md py-space-sm rounded-xl bg-surface-container-low hover:bg-[#FFF3F5] font-body-sm text-body-sm transition-colors flex items-center gap-2');
        b.type = 'button';
        b.append(icon('chat', 'text-[16px] text-primary'), q.text);
        b.addEventListener('click', () => ask(q.text));
        list.append(b);
      });
      addBot(BADGE.INFO, el('p', 'font-body-md text-body-md', `'${name}' 분야에서 많이 묻는 질문이에요. 눌러서 바로 물어보세요.`), list);
    } catch (e) { error('질문 목록을 불러오지 못했어요.'); }
  }

  function askRephrase() {
    addBot(BADGE.INFO, el('p', 'font-body-md text-body-md leading-relaxed',
      '찾으시는 질문이 없었군요. 상황이나 키워드를 조금 더 넣어서 다시 물어봐 주세요. 예를 들면 "신입 자소서 지원동기 쓰는 법"처럼요.'));
    input.focus();
  }

  function error(msg) {
    const p = el('p', 'font-body-md text-body-md text-error flex items-center gap-1.5');
    p.append(icon('error', 'text-[18px]'), msg);
    addBot(BADGE.INFO, p);
  }

  // ------------------------------------------------------------------ 보내기
  async function ask(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    busy = true; updateInput();
    addUser(text);
    const typing = addTyping();
    try {
      const r = await fetch(C.api, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ q: text }),
      });
      const d = await r.json();
      typing.remove();
      if (!r.ok) error(d.error || '오류가 났어요.');
      else render(d);
    } catch (e) {
      typing.remove();
      error('서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.');
    } finally {
      busy = false; updateInput();
    }
  }

  function updateInput() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 128) + 'px';
    count.textContent = `${input.value.length} / 1000자`;
    sendBtn.disabled = busy || !input.value.trim();
  }

  function send() {
    const t = input.value;
    if (!t.trim() || busy) return;
    input.value = '';
    ask(t);
  }

  input.addEventListener('input', updateInput);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
  sendBtn.addEventListener('click', send);
  document.querySelectorAll('.ask').forEach(b => b.addEventListener('click', () => ask(b.dataset.ask)));
  document.getElementById('mascot').addEventListener('click', () => document.getElementById('mascot-speech').classList.toggle('hidden'));

  // 첫 인사
  const hi = el('p', 'font-body-md text-body-md leading-relaxed');
  hi.textContent = '안녕하세요! 취업 준비하면서 궁금한 점을 편하게 물어보세요.\n직무 탐색, 이력서·자소서, 면접·인적성, 채용공고·지원전략, 경험·포트폴리오, 역량개발 중 어떤 고민이든 괜찮아요.';
  hi.classList.add('whitespace-pre-line');
  addBot(null, hi).classList.replace('card-1', 'shadow-sm');
  window.scrollTo(0, 0);
})();
