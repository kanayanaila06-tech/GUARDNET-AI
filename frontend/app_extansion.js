'use strict';

const API_URL = 'http://127.0.0.1:8000';
const TIMEOUT = 45000;
const activeJobs = new Set();

function timeoutFetch(url, options = {}, ms = TIMEOUT) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return fetch(url, { ...options, signal: controller.signal })
    .catch(error => {
      if (error.name === 'AbortError') throw new Error('Request backend timeout.');
      throw error;
    })
    .finally(() => clearTimeout(timer));
}

function dataUrlToBlob(dataUrl) {
  if (typeof dataUrl !== 'string' || !dataUrl.startsWith('data:')) throw new Error('Frame video tidak valid.');
  const comma = dataUrl.indexOf(',');
  if (comma < 0) throw new Error('Data URL frame rusak.');
  const header = dataUrl.slice(0, comma);
  const data = dataUrl.slice(comma + 1);
  const mime = (header.match(/^data:([^;,]+)/i) || [])[1] || 'image/jpeg';
  if (/;base64/i.test(header)) {
    const binary = atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: mime });
  }
  return new Blob([decodeURIComponent(data)], { type: mime });
}

async function jsonFetch(url, options) {
  const response = await timeoutFetch(url, options);
  const raw = await response.text();
  let data = {};
  try { data = raw ? JSON.parse(raw) : {}; } catch { throw new Error(`Backend bukan JSON (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  return data;
}

async function send(tabId, action, payload) {
  if (tabId == null) return;
  try { await chrome.tabs.sendMessage(tabId, { action, ...payload }); } catch (e) { console.warn('[GuardNet-AI] sendMessage:', e.message); }
}

async function analyzeFull(blob, pageUrl, detectedText, contentType) {
  if (!blob || !blob.size) throw new Error('Media kosong.');
  const form = new FormData();
  form.append('file', blob, contentType === 'video' ? 'guardnet-video.jpg' : 'guardnet-image.jpg');
  const params = new URLSearchParams({
    platform: 'instagram',
    content_type: contentType,
    content_url: pageUrl || '',
    detected_text: detectedText || ''
  });
  return jsonFetch(`${API_URL}/analyze-full?${params}`, { method: 'POST', body: form });
}

async function imageJob(message) {
  if (!message.imageUrl) throw new Error('URL gambar kosong.');
  const key = `image|${message.contentKey}|${message.imageUrl}`;
  if (activeJobs.has(key)) return { skipped: true };
  activeJobs.add(key);
  try {
    const response = await timeoutFetch(message.imageUrl, {}, 30000);
    if (!response.ok) throw new Error(`Gagal mengambil gambar (HTTP ${response.status}).`);
    const blob = await response.blob();
    return await analyzeFull(blob, message.url, message.detectedText, 'image');
  } finally { activeJobs.delete(key); }
}

async function videoJob(message) {
  if (!message.frameData) throw new Error('Frame video kosong.');
  const key = `video|${message.contentKey}`;
  if (activeJobs.has(key)) return { skipped: true };
  activeJobs.add(key);
  try {
    const blob = dataUrlToBlob(message.frameData);
    return await analyzeFull(blob, message.url, message.detectedText, 'video');
  } finally { activeJobs.delete(key); }
}

async function textJob(message) {
  const text = String(message.text || '').trim();
  if (!text) throw new Error('Teks kosong.');
  const key = `text|${message.contentKey}|${text.slice(0, 200)}`;
  if (activeJobs.has(key)) return { skipped: true };
  activeJobs.add(key);
  try {
    const params = new URLSearchParams({ platform: 'instagram', content_type: 'text', content_url: message.url || '', detected_text: text.slice(0, 6000) });
    return jsonFetch(`${API_URL}/contents?${params}`, { method: 'POST' }).then(data => {
      if (!data.content_id) throw new Error('Backend tidak mengembalikan content_id.');
      return jsonFetch(`${API_URL}/analyze?content_id=${encodeURIComponent(data.content_id)}`, { method: 'POST' });
    });
  } finally { activeJobs.delete(key); }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const tabId = sender.tab?.id;
  if (!message?.action) return false;

  let task;
  if (message.action === 'ocrImage') task = imageJob(message);
  else if (message.action === 'videoFrame') task = videoJob(message);
  else if (message.action === 'analyzeContent') task = textJob(message);
  else return false;

  sendResponse({ success: true, accepted: true });
  task.then(result => {
    if (result?.skipped) return;
    return send(tabId, message.action === 'analyzeContent' ? 'analysisResult' : 'ocrResult', {
      success: true,
      result,
      contentKey: message.contentKey || null,
      analysisGeneration: message.analysisGeneration ?? null
    });
  }).catch(error => send(tabId, message.action === 'analyzeContent' ? 'analysisResult' : 'ocrResult', {
    success: false,
    error: error.message,
    contentKey: message.contentKey || null,
    analysisGeneration: message.analysisGeneration ?? null
  }));

  return true;
});

console.log('[GuardNet-AI] Simple Stable Background aktif.');
