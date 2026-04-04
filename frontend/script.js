/**
 * Terraform AI Assistant - Optimized Frontend
 * Premium look with 60fps performance
 */

// =========================================
// Constants
// =========================================
const API_URL = 'http://localhost:8001';
const MAX_RETRIES = 2;
const TOAST_DURATION = 3000;

// =========================================
// State
// =========================================
const state = {
  isGenerating: false,
  currentCode: '',
  provider: 'aws',
  abortController: null
};

// =========================================
// DOM Cache - single lookup
// =========================================
const cache = {};

function $(selector) {
  if (!cache[selector]) {
    cache[selector] = document.querySelector(selector);
  }
  return cache[selector];
}

function $$(selector) {
  if (!cache[`all-${selector}`]) {
    cache[`all-${selector}`] = document.querySelectorAll(selector);
  }
  return cache[`all-${selector}`];
}

// =========================================
// Init
// =========================================
document.addEventListener('DOMContentLoaded', () => {
  init();
});

function init() {
  // Clear cache on page load
  Object.keys(cache).forEach(key => delete cache[key]);

  initTextarea();
  initCloudSelector();
  initInput();
  initKeyboard();
  updateCharCount();

  // Preload fonts
  document.fonts.ready.then(() => {
    document.body.classList.add('fonts-loaded');
  });
}

// =========================================
// Textarea - Debounced resize
// =========================================
function initTextarea() {
  const textarea = $('#prompt-input');
  if (!textarea) return;

  let resizeTimeout;
  const resize = () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = requestAnimationFrame(() => {
      textarea.style.height = 'auto';
      const max = 300;
      const h = Math.min(textarea.scrollHeight, max);
      textarea.style.height = h + 'px';
    });
  };

  textarea.addEventListener('input', () => {
    resize();
    updateCharCount();
  });

  resize();
}

// =========================================
// Cloud Selector
// =========================================
function initCloudSelector() {
  const buttons = $$('.cloud-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') return;

      buttons.forEach(b => {
        b.setAttribute('aria-pressed', 'false');
        b.classList.remove('active');
      });
      btn.setAttribute('aria-pressed', 'true');
      btn.classList.add('active');
      state.provider = btn.dataset.provider;
    });
  });
}

// =========================================
// Input with Debounced Validation
// =========================================
function initInput() {
  const input = $('#prompt-input');
  if (!input) return;

  let validateTimeout;
  input.addEventListener('input', () => {
    clearTimeout(validateTimeout);
    validateTimeout = setTimeout(validateRealtime, 300);
    updateCharCount();
  });
}

function validateRealtime() {
  const input = $('#prompt-input');
  if (!input) return;

  const result = validatePrompt(input.value);

  if (result.valid || !input.value.trim()) {
    input.style.borderColor = '';
    input.style.boxShadow = '';
  } else {
    input.style.borderColor = '#ef4444';
    input.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
  }
}

function updateCharCount() {
  const input = $('#prompt-input');
  const counter = $('#char-current');
  if (input && counter) {
    const len = input.value.length;
    counter.textContent = len;
    const pct = len / 1000 * 100;
    counter.style.color = pct > 90 ? '#f59e0b' : pct >= 100 ? '#ef4444' : '';
  }
}

// =========================================
// Keyboard
// =========================================
function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !state.isGenerating) {
      e.preventDefault();
      generateTerraform();
    }
    if (e.key === 'Escape' && !state.isGenerating && document.activeElement === $('#prompt-input')) {
      e.preventDefault();
      clearOutput();
    }
  });
}

// =========================================
// Validation
// =========================================
function validatePrompt(prompt) {
  const trimmed = prompt.trim();

  if (!trimmed) return { valid: false, message: 'Describe your infrastructure' };
  if (trimmed.length < 5) return { valid: false, message: 'Too short (min 5 chars)' };
  if (trimmed.length > 1000) return { valid: false, message: 'Too long (max 1000 chars)' };

  // Check for code patterns
  const patterns = [
    /terraform\s*{/i,
    /provider\s*["']/i,
    /resource\s*["']/i,
    /variable\s*{/i,
    /output\s*{/i,
    /module\s*{/i,
    /data\s*{/i,
    /locals\s*{/i,
    /```/g
  ];

  if (patterns.some(r => r.test(trimmed))) {
    return { valid: false, message: 'Remove code blocks, use plain description' };
  }

  return { valid: true };
}

// =========================================
// API
// =========================================
async function generateTerraform() {
  if (state.isGenerating) return;

  const prompt = $('#prompt-input').value.trim();
  const validation = validatePrompt(prompt);

  if (!validation.valid) {
    showToast(validation.message, 'error');
    return;
  }

  if (state.abortController) state.abortController.abort();
  state.abortController = new AbortController();

  setLoading(true);
  hideError();
  clearOutput();

  try {
    const result = await requestWithRetry(prompt, state.provider);
    state.currentCode = result.code;
    displayResult(result);
    showToast('Generated successfully!', 'success');
  } catch (error) {
    handleError(error);
  } finally {
    setLoading(false);
    state.abortController = null;
  }
}

async function requestWithRetry(prompt, provider, attempt = 0) {
  try {
    return await makeRequest(prompt, provider);
  } catch (error) {
    if (attempt < MAX_RETRIES && isRetryable(error)) {
      await delay(1000 * (attempt + 1));
      return requestWithRetry(prompt, provider, attempt + 1);
    }
    throw error;
  }
}

async function makeRequest(prompt, provider) {
  const res = await fetch(`${API_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, cloud_provider: provider }),
    signal: state.abortController?.signal
  });

  const data = await res.json();

  if (!res.ok) {
    if (res.status === 422) {
      const msg = Array.isArray(data.detail) ? data.detail[0].msg : data.detail || 'Invalid input';
      throw new Error(msg);
    }
    if (res.status === 429) throw new Error('Rate limit exceeded');
    if (res.status >= 500) throw new Error('Service unavailable');
    throw new Error(data.detail || `HTTP ${res.status}`);
  }

  if (!data.success) throw new Error(data.message || 'Generation failed');
  return data;
}

function isRetryable(error) {
  const msgs = ['failed to fetch', 'networkerror', 'etimedout', 'econnreset', 'abort'];
  return msgs.some(m => error.message.toLowerCase().includes(m));
}

// =========================================
// UI State
// =========================================
function setLoading(loading) {
  state.isGenerating = loading;

  const btn = $('#generate-btn');
  if (btn) {
    btn.disabled = loading;
    btn.classList.toggle('loading', loading);
  }

  const input = $('#prompt-input');
  if (input) {
    input.disabled = loading;
    input.setAttribute('aria-busy', loading);
  }

  document.body.style.cursor = loading ? 'wait' : 'default';

  if (!loading && input) {
    setTimeout(() => input.focus(), 50);
  }
}

function displayResult(data) {
  const output = $('#output');
  const codeEl = $('#code-output');
  const stats = $('#code-stats');

  if (!output || !codeEl) return;

  // Highlight syntax (simplified, debounced)
  const highlighted = highlightSyntax(data.code);
  codeEl.innerHTML = highlighted;
  state.currentCode = data.code;

  // Update stats
  if (stats) {
    const lines = data.code.split('\n').length;
    const size = formatBytes(data.code.length);
    stats.innerHTML = `
      <span class="stat">
        <svg viewBox="0 0 16 16" fill="currentColor"><path d="M2 3.5A1.5 1.5 0 013.5 2h1.735a4.966 4.966 0 0110 4.185V3.5a.5.5 0 01-.5-.5h-.235l-.627 1.855c-.055.167-.232.254-.423.254h-.408a.5.5 0 01-.5-.5V3.5z"/></svg>
        <span>${lines} lines</span>
      </span>
      <span class="stat">
        <svg viewBox="0 0 16 16" fill="currentColor"><path d="M.5 9.9a.5.5 0 01.5.5v2.5a1 1 0 001 1h12a1 1 0 001-1v-2.5a.5.5 0 01.5-.5h4a.5.5 0 010 1h-4z"/></svg>
        <span>${size}</span>
      </span>
    `;
  }

  output.style.display = 'block';
  output.classList.add('fade-in');

  // Scroll on mobile
  if (window.innerWidth < 768) {
    requestAnimationFrame(() => {
      output.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
}

// Fast syntax highlighting (optimized regex)
function highlightSyntax(code) {
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Single pass with reduced patterns
  return escaped
    .replace(/(#.*$)/gm, '<span class="comment">$1</span>')
    .replace(/\b(var|output|resource|provider|terraform|module|data|locals)\b/g, '<span class="keyword">$1</span>')
    .replace(/\b(aws|azurerm|google)\b/g, '<span class="provider">$1</span>')
    .replace(/"(.*?)"/g, '<span class="string">"$1"</span>')
    .replace(/\b(true|false|null)\b/g, '<span class="boolean">$1</span>')
    .replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
    .replace(/(=|{|}|<=|>=|!=|==)/g, '<span class="operator">$1</span>');
}

// =========================================
// Actions
// =========================================
function copyCode() {
  if (!state.currentCode) {
    showToast('No code to copy', 'error');
    return;
  }

  navigator.clipboard.writeText(state.currentCode)
    .then(() => showToast('Copied!', 'success'))
    .catch(() => showToast('Copy failed', 'error'));
}

function downloadCode() {
  if (!state.currentCode) {
    showToast('No code to download', 'error');
    return;
  }

  const blob = new Blob([state.currentCode], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `main-${state.provider}-${Date.now()}.tf`;
  a.click();

  URL.revokeObjectURL(url);
  showToast('Downloaded!', 'success');
}

function clearOutput() {
  const output = $('#output');
  const code = $('#code-output');

  if (output) output.style.display = 'none';
  if (code) {
    code.textContent = '';
    code.innerHTML = '';
  }
  state.currentCode = '';

  const input = $('#prompt-input');
  if (input) input.focus();
}

// =========================================
// Error & Toast
// =========================================
function showError(msg) {
  const el = $('#error-message');
  if (!el) return;

  el.textContent = msg;
  el.style.display = 'block';
  el.style.animation = 'none';
  requestAnimationFrame(() => el.style.animation = '');
  setTimeout(hideError, 5000);
}

function hideError() {
  const el = $('#error-message');
  if (el) el.style.display = 'none';
}

function handleError(error) {
  console.error('Error:', error);

  let msg = error.message || 'Unexpected error';
  const lower = msg.toLowerCase();

  if (lower.includes('failed to fetch') || lower.includes('networkerror')) {
    msg = 'Cannot connect. Is the backend running?';
  } else if (lower.includes('etimedout') || lower.includes('timeout')) {
    msg = 'Request timeout. Try a shorter description.';
  } else if (lower.includes('rate limit')) {
    msg = 'Rate limited. Wait 60 seconds.';
  } else if (lower.includes('service unavailable') || lower.includes('502')) {
    msg = 'AI service busy. Try again.';
  }

  showError(msg);
  showToast(msg, 'error');
}

function showToast(message, type = 'info') {
  const toast = $('#toast');
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast ${type}`;

  // Trigger reflow
  toast.offsetHeight;
  toast.classList.add('show');

  setTimeout(() => toast.classList.remove('show'), TOAST_DURATION);
}

// =========================================
// Utilities
// =========================================
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Expose for debugging
if (typeof window !== 'undefined') {
  window.TerraformAI = { validatePrompt, clearOutput, generate: generateTerraform };
}
