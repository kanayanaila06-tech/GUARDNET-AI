(() => {
  'use strict';

  const PREFIX = '[GuardNet-AI]';
  const MIN_MEDIA_SIZE = 180;
  const SCAN_DELAY = 500;
  const VIDEO_WIDTH = 900;

  let currentKey = null;
  let generation = 0;
  let timer = null;
  let popup = null;
  const sent = new Set();

  function log(...args) { console.log(PREFIX, ...args); }

  function text(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function key(value) {
    return text(value).slice(0, 500);
  }

  function rootOf(element) {
    return element?.closest?.('article') || element?.closest?.('[role="dialog"]') || element;
  }

  function contentKey(root) {
    const link = root?.querySelector?.('a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]');
    if (link?.href) return link.href.split('?')[0];
    return `${location.pathname}|${key(root?.innerText).slice(0, 120)}`;
  }

  function visible(root) {
    if (!root) return false;
    const r = root.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight && r.width > 0 && r.height > 0;
  }

  function findPost() {
    const articles = [...document.querySelectorAll('article')].filter(visible);
    if (articles.length) {
      const center = innerHeight / 2;
      return articles.sort((a, b) => {
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();
        return Math.abs((ar.top + ar.bottom) / 2 - center) - Math.abs((br.top + br.bottom) / 2 - center);
      })[0];
    }
    const dialog = document.querySelector('[role="dialog"]');
    return visible(dialog) ? dialog : null;
  }

  function media(root) {
    const nodes = [...(root?.querySelectorAll?.('img,video') || [])];
    return nodes.find(el => {
      const r = el.getBoundingClientRect();
      return r.width >= MIN_MEDIA_SIZE && r.height >= MIN_MEDIA_SIZE && visible(el);
    }) || null;
  }

  function detectedText(root) {
    return key(root?.innerText || '');
  }

  function send(message) {
    try {
      if (!chrome?.runtime?.id) return false;
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) log('Runtime:', chrome.runtime.lastError.message);
        else if (response) log('Background:', response);
      });
      return true;
    } catch (e) {
      log('sendMessage error:', e.message);
      return false;
    }
  }

  function ensureStyle() {
    if (document.getElementById('guardnet-simple-style')) return;
    const s = document.createElement('style');
    s.id = 'guardnet-simple-style';
    s.textContent = `
      #guardnet-simple-popup{position:fixed;z-index:2147483647;right:24px;top:90px;width:330px;background:#1f1f1f;color:#fff;border:1px solid #666;border-radius:14px;padding:16px;font:14px Arial,sans-serif;box-shadow:0 10px 35px rgba(0,0,0,.35)}
      #guardnet-simple-popup .head{font-weight:700;font-size:17px;margin-bottom:12px}
      #guardnet-simple-popup .close{float:right;border:0;background:transparent;color:#fff;font-size:20px;cursor:pointer}
      #guardnet-simple-popup .risk{font-weight:800;font-size:22px;margin:8px 0}
      #guardnet-simple-popup .muted{color:#ccc;line-height:1.45}
      #guardnet-simple-popup.high .risk{color:#ff5252}#guardnet-simple-popup.medium .risk{color:#ffb020}#guardnet-simple-popup.low .risk{color:#59d98e}
    `;
    document.documentElement.appendChild(s);
  }

  function showLoading(type) {
    ensureStyle();
    if (!popup) {
      popup = document.createElement('div');
      popup.id = 'guardnet-simple-popup';
      document.body.appendChild(popup);
    }
    popup.className = '';
    popup.innerHTML = `<button class="close" aria-label="Tutup">×</button><div class="head">🛡️ GuardNet-AI</div><div class="risk">Menganalisis...</div><div class="muted">Pemeriksaan ${type === 'video' ? 'video' : 'konten'} sedang berjalan.</div>`;
    popup.querySelector('.close').onclick = () => { popup.remove(); popup = null; };
  }

  function showResult(result) {
    ensureStyle();
    if (!popup) { popup = document.createElement('div'); popup.id = 'guardnet-simple-popup'; document.body.appendChild(popup); }
    const risk = text(result?.risk_level || result?.risk || 'low').toUpperCase();
    const score = Number(result?.score ?? result?.final_score ?? 0);
    const indicators = Array.isArray(result?.detected_indicators) ? result.detected_indicators : [];
    popup.className = risk.toLowerCase();
    popup.innerHTML = `<button class="close" aria-label="Tutup">×</button><div class="head">🛡️ GuardNet-AI</div><div class="risk">${risk}</div><div class="muted">Skor: ${(Number.isFinite(score) ? score : 0).toFixed(2)}</div><div class="muted">${indicators.length ? `Indikator: ${indicators.slice(0,4).map(x => text(x)).join(', ')}` : 'Tidak ada indikator yang dikembalikan.'}</div>`;
    popup.querySelector('.close').onclick = () => { popup.remove(); popup = null; };
  }

  function showError(message) {
    ensureStyle();
    if (!popup) { popup = document.createElement('div'); popup.id = 'guardnet-simple-popup'; document.body.appendChild(popup); }
    popup.className = '';
    popup.innerHTML = `<button class="close" aria-label="Tutup">×</button><div class="head">🛡️ GuardNet-AI</div><div class="risk">Analisis gagal</div><div class="muted">${text(message) || 'Terjadi kesalahan saat menghubungi backend.'}</div>`;
    popup.querySelector('.close').onclick = () => { popup.remove(); popup = null; };
  }

  function captureVideo(video) {
    try {
      if (!video.videoWidth || !video.videoHeight) return null;
      const ratio = Math.min(1, VIDEO_WIDTH / video.videoWidth);
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(video.videoWidth * ratio));
      canvas.height = Math.max(1, Math.round(video.videoHeight * ratio));
      const ctx = canvas.getContext('2d', { willReadFrequently: false });
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/jpeg', 0.72);
    } catch (e) {
      log('Video frame gagal:', e.message);
      return null;
    }
  }

  function analyze(root) {
    const ck = contentKey(root);
    if (!ck) return;
    if (ck !== currentKey) {
      currentKey = ck;
      generation += 1;
    }
    const gen = generation;
    const m = media(root);
    const bodyText = detectedText(root);
    const job = `${ck}|${m?.currentSrc || m?.src || 'text'}|${gen}`;
    if (sent.has(job)) return;
    sent.add(job);

    if (m?.tagName === 'IMG') {
      const src = m.currentSrc || m.src;
      if (!src) return;
      showLoading('gambar');
      send({ action: 'ocrImage', imageUrl: src, url: location.href, detectedText: bodyText, contentKey: ck, analysisGeneration: gen, sourceType: 'image' });
      return;
    }

    if (m?.tagName === 'VIDEO') {
      const frame = captureVideo(m);
      if (frame) {
        showLoading('video');
        send({ action: 'videoFrame', frameData: frame, url: location.href, detectedText: bodyText, contentKey: ck, analysisGeneration: gen });
        return;
      }
    }

    if (bodyText.length >= 10) {
      showLoading('teks');
      send({ action: 'analyzeContent', text: bodyText.slice(0, 6000), url: location.href, contentKey: ck, analysisGeneration: gen });
    }
  }

  function scan() {
    const root = findPost();
    if (root) analyze(root);
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(scan, SCAN_DELAY);
  }

  chrome.runtime.onMessage.addListener(message => {
    if (!message) return;
    if (message.contentKey && message.contentKey !== currentKey) return;
    if (message.analysisGeneration != null && message.analysisGeneration !== generation) return;

    if (message.action === 'analysisResult' || message.action === 'ocrResult') {
      if (!message.success) { showError(message.error); return; }
      const result = message.result;
      if (!result || typeof result !== 'object') { showError('Backend tidak mengembalikan hasil analisis.'); return; }
      showResult(result);
    }
  });

  let lastUrl = location.href;
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  addEventListener('scroll', schedule, { passive: true });
  setInterval(() => { if (location.href !== lastUrl) { lastUrl = location.href; currentKey = null; generation += 1; sent.clear(); schedule(); } }, 500);
  setTimeout(scan, 500);
  log('Simple Stable Content aktif.');
})();