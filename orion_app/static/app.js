// Orion The Warrior - Enhanced Application Engine
const promptBox = document.getElementById('prompt-box');
const aiResponse = document.getElementById('ai-response');
const deviceList = document.getElementById('device-list');
const taskList = document.getElementById('task-list');
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const sendButton = document.getElementById('ask-ai-btn');
const modelStatus = document.getElementById('model-status');
const modelSelector = document.getElementById('model-selector');
const memoryStatus = document.getElementById('memory-status');
const exportChatBtn = document.getElementById('export-chat-btn');
const archerForm = document.getElementById('archer-form');
const archerPrompt = document.getElementById('archer-prompt');
const archerMode = document.getElementById('archer-mode');
const archerButton = document.getElementById('generate-archer-btn');
const archerStatus = document.getElementById('archer-status');
const archerMessage = document.getElementById('archer-message');
const archerPreview = document.getElementById('archer-preview');

// Device Control View Elements
const deviceRegisterForm = document.getElementById('device-register-form');
const devRegName = document.getElementById('dev-reg-name');
const devRegKind = document.getElementById('dev-reg-kind');
const devRegStatus = document.getElementById('dev-reg-status');
const taskEnqueueForm = document.getElementById('task-enqueue-form');
const taskTargetDevice = document.getElementById('task-target-device');
const taskDescription = document.getElementById('task-description');
const taskEnqueueStatus = document.getElementById('task-enqueue-status');
const devicesManagerGrid = document.getElementById('devices-manager-grid');
const interactiveTaskTable = document.getElementById('interactive-task-table');
const refreshDevicesBtn = document.getElementById('refresh-devices-btn');
const taskQueueFilters = document.getElementById('task-queue-filters');

// AI Studio View Elements
const studioArcherForm = document.getElementById('studio-archer-form');
const studioArcherPrompt = document.getElementById('studio-archer-prompt');
const studioArcherRatio = document.getElementById('studio-archer-ratio');
const studioArcherMode = document.getElementById('studio-archer-mode');
const studioGenerateBtn = document.getElementById('studio-generate-btn');
const studioArcherStatus = document.getElementById('studio-archer-status');
const studioGenerateStatus = document.getElementById('studio-generate-status');
const studioPreviewBox = document.getElementById('studio-preview-box');
const studioPreviewImg = document.getElementById('studio-preview-img');
const studioDownloadBtn = document.getElementById('studio-download-btn');
const studioOpenBtn = document.getElementById('studio-open-btn');
const galleryGrid = document.getElementById('gallery-grid');
const refreshGalleryBtn = document.getElementById('refresh-gallery-btn');

// Lightbox Modal Elements
const imageModal = document.getElementById('image-modal');
const modalImg = document.getElementById('modal-img');
const modalCaption = document.getElementById('modal-caption');
const closeModalBtn = document.getElementById('close-modal-btn');

// Social Hub Elements
const MEMORY_KEY = 'orion-conversation-id';
const conversationId = getConversationId();
const SOCIAL_DRAFT_KEY = 'orion-social-draft:';
const socialPlatform = document.getElementById('social-platform');
const socialRecipient = document.getElementById('social-recipient');
const socialDraft = document.getElementById('social-draft');
const socialDraftStatus = document.getElementById('social-draft-status');
const instagramStatus = document.getElementById('instagram-status');
const instagramNotice = document.getElementById('instagram-notice');
const instagramConnectionState = document.getElementById('instagram-connection-state');
const instagramActionStatus = document.getElementById('instagram-action-status');
const instagramProfile = document.getElementById('instagram-profile');
const instagramMedia = document.getElementById('instagram-media');
const instagramInbox = document.getElementById('instagram-inbox');
const instagramInsights = document.getElementById('instagram-insights');

// Task Activity Elements
const taskRunsContainer = document.getElementById('task-runs');
const taskStreamStatus = document.getElementById('task-stream-status');
const taskClearBtn = document.getElementById('task-clear-btn');
const taskRuns = new Map();
let taskEventSource = null;
let instagramAccountId = null;
let activeSocialPlatform = socialPlatform ? socialPlatform.value : 'whatsapp';
let activeTaskFilter = 'all';
let currentDevicesCache = [];
let currentTasksCache = [];

// Sidebar live terminal
const sidebarTermBody = document.getElementById('sidebar-terminal-body');
const termClearBtn = document.getElementById('term-clear-btn');
const termScrollBtn = document.getElementById('term-scroll-btn');
const termLiveDot = document.getElementById('term-live-dot');
let termAutoScroll = true;
// Track how many log entries we've already printed per run (avoid duplicates on full snapshots)
const termRunLogCounts = new Map();

const socialPlatforms = {
  whatsapp: { name: 'WhatsApp', url: 'https://web.whatsapp.com/' },
  discord: { name: 'Discord', url: 'https://discord.com/app' },
  instagram: { name: 'Instagram', url: 'https://www.instagram.com/' },
};

function getConversationId() {
  let id = localStorage.getItem(MEMORY_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(MEMORY_KEY, id);
  }
  return id;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }

  return response.json();
}

/* ==========================================================================
   SYSTEM TELEMETRY
   ========================================================================== */
async function loadSystemTelemetry() {
  try {
    const data = await fetchJson('/api/system/metrics');
    // Dashboard strip
    if (document.getElementById('telem-cpu-val')) {
      const cpuVal = data.cpu?.usage_percent ?? 0;
      document.getElementById('telem-cpu-val').textContent = `${cpuVal}%`;
      document.getElementById('telem-cpu-bar').style.width = `${Math.min(100, cpuVal)}%`;
    }
    if (document.getElementById('telem-ram-val')) {
      const ramVal = data.memory?.usage_percent ?? 0;
      document.getElementById('telem-ram-val').textContent = `${ramVal}%`;
      document.getElementById('telem-ram-bar').style.width = `${Math.min(100, ramVal)}%`;
    }
    if (document.getElementById('telem-disk-val')) {
      const diskVal = data.disk?.usage_percent ?? 0;
      document.getElementById('telem-disk-val').textContent = `${diskVal}%`;
      document.getElementById('telem-disk-bar').style.width = `${Math.min(100, diskVal)}%`;
    }
    if (document.getElementById('telem-uptime-val')) {
      document.getElementById('telem-uptime-val').textContent = data.uptime?.formatted || 'Active';
      document.getElementById('telem-os-val').textContent = `${data.platform?.system || 'Host'} · Python ${data.platform?.python_version || ''}`;
    }
    // Sidebar stats
    if (document.getElementById('sb-cpu-val')) {
      document.getElementById('sb-cpu-val').textContent = `${data.cpu?.usage_percent ?? 0}%`;
      document.getElementById('sb-ram-val').textContent = `${data.memory?.usage_percent ?? 0}%`;
      document.getElementById('sb-uptime-val').textContent = data.uptime?.formatted || '--';
    }
  } catch (error) {
    // Graceful silent ignore on telemetry error
  }
}

async function loadLauncherState() {
  const badge = document.getElementById('diag-launcher-state');
  if (!badge) return;
  try {
    const info = await fetchJson('/api/launcher/status');
    if (info.attached) {
      badge.textContent = `BAT LINK · ACTIVE (${info.lines_ingested}L)`;
      badge.className = 'diag-launcher-state connected';
      badge.title = `Launcher session attached. Log: ${info.log_path}`;
    } else if (info.log_exists) {
      badge.textContent = `BAT LINK · READY (${info.lines_ingested}L)`;
      badge.className = 'diag-launcher-state connected';
      badge.title = `Launcher log detected. Log: ${info.log_path}`;
    } else {
      badge.textContent = 'BAT LINK · STANDBY';
      badge.className = 'diag-launcher-state';
      badge.title = 'start_orion.bat log not detected yet. Run start_orion.bat to link output.';
    }
  } catch (err) {
    badge.textContent = 'BAT LINK · --';
    badge.className = 'diag-launcher-state';
  }
}

setInterval(loadSystemTelemetry, 4000);
loadSystemTelemetry();
setInterval(loadLauncherState, 5000);
loadLauncherState();

/* ==========================================================================
   SIDEBAR TASK MANAGER
   ========================================================================== */
const taskmanBody  = document.getElementById('taskman-body');
const taskmanCount = document.getElementById('taskman-proc-count');

async function loadProcessList() {
  if (!taskmanBody) return;
  try {
    const data = await fetchJson('/api/system/processes?limit=30');
    if (!data.available) {
      taskmanBody.innerHTML = '<div class="tm-placeholder">psutil unavailable</div>';
      return;
    }

    if (taskmanCount) taskmanCount.textContent = `${data.total} proc`;

    const procs = data.processes || [];
    if (!procs.length) {
      taskmanBody.innerHTML = '<div class="tm-placeholder">No processes found</div>';
      return;
    }

    const rows = procs.map(p => {
      // CPU colour class
      const cpuCls = p.cpu >= 20 ? 'hot' : p.cpu >= 5 ? 'warm' : '';
      // Status colour class
      const stCls  = p.status === 'running' ? 'running'
                   : (p.status === 'stopped' || p.status === 'zombie') ? 'stopped' : '';
      const cpuStr  = p.cpu > 0 ? `${p.cpu}%` : '0%';
      const memStr  = p.mem_mb >= 1000 ? `${(p.mem_mb / 1024).toFixed(1)}G`
                                       : `${p.mem_mb}M`;
      return `<div class="tm-row">
        <span class="tm-name" title="${p.name} [PID ${p.pid}]">${p.name}</span>
        <span class="tm-cpu ${cpuCls}">${cpuStr}</span>
        <span class="tm-mem">${memStr}</span>
        <span class="tm-status ${stCls}">${p.status}</span>
      </div>`;
    });

    taskmanBody.innerHTML = rows.join('');
  } catch (_) {
    if (taskmanBody) taskmanBody.innerHTML = '<div class="tm-placeholder">Error loading processes</div>';
  }
}

setInterval(loadProcessList, 4000);
loadProcessList();

/* ==========================================================================
   ZARA — Backup offline chatbot JS
   ========================================================================== */
const zaraMessages    = document.getElementById('zara-messages');
const zaraForm        = document.getElementById('zara-form');
const zaraPrompt      = document.getElementById('zara-prompt');
const zaraSendBtn     = document.getElementById('zara-send-btn');
const zaraModelSel    = document.getElementById('zara-model-selector');
const zaraModelStatus = document.getElementById('zara-model-status');
const zaraClearBtn    = document.getElementById('zara-clear-btn');

async function loadZaraStatus() {
  if (!zaraModelStatus) return;
  try {
    const data = await fetchJson('/api/zara/status');
    if (zaraModelStatus) zaraModelStatus.textContent = data.status_text || (data.ollama_reachable ? `✨ ${data.model}` : 'Offline');
    if (zaraModelSel && data.installed_models?.length) {
      const current = zaraModelSel.value || data.model;
      zaraModelSel.innerHTML = data.installed_models
        .map(m => `<option value="${m}" ${m === current ? 'selected' : ''}>${m}</option>`)
        .join('');
    }
  } catch (_) {
    if (zaraModelStatus) zaraModelStatus.textContent = 'Zara offline';
  }
}

function addZaraMessage(role, text, pending = false) {
  if (!zaraMessages) return null;
  const div = document.createElement('div');
  div.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;
  if (pending) div.classList.add('pending-message');
  const author = document.createElement('span');
  author.className = 'message-author' + (role !== 'user' ? ' zara-author' : '');
  author.textContent = role === 'user' ? 'YOU' : 'ZARA ✨';
  const body = document.createElement('div');
  body.className = 'message-body';
  body.innerHTML = renderMarkdown(text);
  div.append(author, body);
  zaraMessages.append(div);
  zaraMessages.scrollTop = zaraMessages.scrollHeight;
  return div;
}

async function askZara() {
  if (!zaraPrompt || !zaraSendBtn) return;
  const msg = zaraPrompt.value.trim();
  if (!msg) return;
  zaraPrompt.value = '';
  zaraSendBtn.disabled = true;
  addZaraMessage('user', msg);
  const pendingDiv = addZaraMessage('assistant', '…', true);

  try {
    // Switch model if selector changed
    const chosenModel = zaraModelSel ? zaraModelSel.value : '';
    if (chosenModel) {
      await fetchJson('/api/zara/status');  // lightweight ping; model switch via env only for now
    }

    const resp = await fetch('/api/zara/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, message: msg }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let done = false;
    while (!done) {
      const { value, done: streamDone } = await reader.read();
      done = streamDone;
      if (!value) continue;
      const lines = decoder.decode(value).split('\n').filter(l => l.trim());
      for (const line of lines) {
        let event;
        try { event = JSON.parse(line); } catch { continue; }
        if (event.type === 'delta') {
          fullText += event.content;
          if (pendingDiv) {
            pendingDiv.querySelector('.message-body').innerHTML = renderMarkdown(fullText);
            zaraMessages.scrollTop = zaraMessages.scrollHeight;
          }
        } else if (event.type === 'done') {
          fullText = event.message || fullText;
          if (pendingDiv) {
            pendingDiv.classList.remove('pending-message');
            pendingDiv.querySelector('.message-body').innerHTML = renderMarkdown(fullText);
          }
        } else if (event.type === 'error') {
          if (pendingDiv) pendingDiv.querySelector('.message-body').innerHTML = `<p class="error-text">⚠️ ${event.message}</p>`;
        }
      }
    }
  } catch (err) {
    if (pendingDiv) pendingDiv.querySelector('.message-body').innerHTML = `<p class="error-text">⚠️ ${err.message}</p>`;
  } finally {
    zaraSendBtn.disabled = false;
    zaraPrompt.focus();
  }
}

if (zaraForm) {
  zaraForm.addEventListener('submit', e => { e.preventDefault(); askZara(); });
  if (zaraPrompt) {
    zaraPrompt.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askZara(); }
    });
  }
}

if (zaraClearBtn) {
  zaraClearBtn.addEventListener('click', async () => {
    if (!window.confirm("Clear Zara's conversation memory?")) return;
    await fetchJson(`/api/zara/memory/${encodeURIComponent(conversationId)}`, { method: 'DELETE' }).catch(() => {});
    if (zaraMessages) {
      zaraMessages.innerHTML = '';
      addZaraMessage('assistant', "Memory wiped! 🧹 Fresh start — what's on your mind? 😊");
    }
  });
}

setInterval(loadZaraStatus, 8000);
loadZaraStatus();

/* ==========================================================================
   MARKDOWN & CHAT RENDERING
   ========================================================================== */
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks: ```code```
  html = html.replace(/```([\s\S]*?)```/g, (match, p1) => {
    return `<pre><code>${p1.trim()}</code></pre>`;
  });

  // Inline code: `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic: *text*
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Bullet items
  html = html.replace(/(?:^|\n)[-*]\s+([^\n]+)/g, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, '');

  const paragraphs = html.split(/\n{2,}/).map(para => {
    para = para.trim();
    if (para.startsWith('<pre>') || para.startsWith('<ul>')) return para;
    return `<p>${para.replace(/\n/g, '<br>')}</p>`;
  });

  return paragraphs.join('');
}

function addMessage(role, text, pending = false) {
  const message = document.createElement('div');
  message.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;
  if (pending) message.classList.add('pending-message');

  const author = document.createElement('span');
  author.className = 'message-author';
  author.textContent = role === 'user' ? 'YOU' : 'NICO';

  const content = document.createElement('div');
  content.className = 'message-body';
  content.innerHTML = renderMarkdown(text);
  message.append(author, content);

  if (role !== 'user' && !pending) {
    const footer = document.createElement('div');
    footer.className = 'msg-footer';
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-msg-btn';
    copyBtn.type = 'button';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(text);
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
    });
    footer.append(copyBtn);
    message.append(footer);
  }

  chatMessages.append(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return message;
}

async function loadConversation() {
  const result = await fetchJson(
    `/api/assistant/memory/${encodeURIComponent(conversationId)}?limit=100`
  );
  for (const message of result.messages) {
    addMessage(message.role, message.content);
  }
  if (result.count) {
    renderMemoryStatus(result.count, result.limit);
  }
}

function renderMemoryStatus(count, limit) {
  memoryStatus.textContent = `LOCAL MEMORY · ${count.toLocaleString()} / ${limit.toLocaleString()}`;
}

async function clearMemory() {
  if (!window.confirm('Clear this conversation from Orion’s local memory?')) return;
  try {
    const result = await fetchJson(`/api/assistant/memory/${encodeURIComponent(conversationId)}`, {
      method: 'DELETE',
    });
    chatMessages.replaceChildren();
    addMessage('assistant', "Memory cleared. I'm ready for a fresh start.");
    aiResponse.textContent = '';
    renderMemoryStatus(0, result.limit);
  } catch (error) {
    aiResponse.textContent = `Could not clear local memory: ${error.message}`;
  }
}

if (exportChatBtn) {
  exportChatBtn.addEventListener('click', async () => {
    try {
      const data = await fetchJson(`/api/assistant/memory/${encodeURIComponent(conversationId)}/export?format=markdown`);
      const blob = new Blob([data.content], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `orion-chat-${conversationId.slice(0, 8)}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      alert(`Could not export chat: ${error.message}`);
    }
  });
}

async function askAi() {
  const prompt = promptBox.value.trim();
  if (!prompt) {
    promptBox.focus();
    return;
  }
  sendButton.disabled = true;
  sendButton.textContent = 'Nico is thinking...';
  addMessage('user', prompt);
  promptBox.value = '';
  const pendingMessage = addMessage('assistant', 'Consulting local models & telemetry...', true);
  const bodyEl = pendingMessage.querySelector('.message-body');
  try {
    const response = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, message: prompt }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let reply = '';
    let completed = false;
    let paintQueued = false;
    const flushReply = () => {
      bodyEl.innerHTML = renderMarkdown(reply);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      paintQueued = false;
    };
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === 'delta') {
          reply += event.content;
          if (!paintQueued) {
            paintQueued = true;
            requestAnimationFrame(flushReply);
          }
        } else if (event.type === 'error') {
          throw new Error(event.message);
        } else if (event.type === 'done') {
          completed = true;
          renderMemoryStatus(event.memory_count, event.memory_limit);
          if (event.tools_used?.length) {
            const liveData = document.createElement('span');
            liveData.className = 'message-source';
            liveData.textContent = `LIVE TOOLS · ${event.tools_used.join(' · ')}`;
            pendingMessage.append(liveData);
          }
          aiResponse.textContent = event.message;

          // Add copy button once done
          const footer = document.createElement('div');
          footer.className = 'msg-footer';
          const copyBtn = document.createElement('button');
          copyBtn.className = 'copy-msg-btn';
          copyBtn.type = 'button';
          copyBtn.textContent = 'Copy';
          copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(reply);
            copyBtn.textContent = 'Copied!';
            setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
          });
          footer.append(copyBtn);
          pendingMessage.append(footer);
        }
      }
    }
    if (paintQueued) flushReply();
    if (!completed) throw new Error('Nico’s response stream ended unexpectedly.');
    pendingMessage.classList.remove('pending-message');
  } catch (error) {
    bodyEl.innerHTML = `<p class="error-text">Connection issue: ${error.message}</p>`;
    aiResponse.textContent = error.message;
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Send message';
    promptBox.focus();
  }
}

async function loadModelStatus() {
  try {
    const status = await fetchJson('/api/assistant/status');
    modelStatus.textContent = status.available
      ? status.installed
        ? `● ${status.model} ready`
        : `● Ollama online · install ${status.model}`
      : '● Ollama offline';
    modelStatus.classList.toggle('online', status.available && status.installed);
    modelStatus.classList.toggle('offline', !status.available || !status.installed);

    if (modelSelector && status.installed_models) {
      modelSelector.replaceChildren();
      if (!status.installed_models.length) {
        const opt = document.createElement('option');
        opt.value = status.model;
        opt.textContent = status.model;
        modelSelector.append(opt);
      } else {
        for (const m of status.installed_models) {
          const opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          if (m === status.model || m.startsWith(status.model)) opt.selected = true;
          modelSelector.append(opt);
        }
      }
    }
  } catch (error) {
    modelStatus.textContent = `● Status unavailable: ${error.message}`;
    modelStatus.classList.add('offline');
  }
}

if (modelSelector) {
  modelSelector.addEventListener('change', async () => {
    try {
      const chosen = modelSelector.value;
      if (!chosen) return;
      await fetchJson('/api/ollama/model', {
        method: 'POST',
        body: JSON.stringify({ model: chosen }),
      });
      await loadModelStatus();
    } catch (error) {
      alert(`Could not switch model: ${error.message}`);
    }
  });
}

/* ==========================================================================
   DEVICE MANAGEMENT & AUTOMATION PIPELINE
   ========================================================================== */
function renderDevices(devices) {
  currentDevicesCache = devices;
  if (deviceList) {
    deviceList.innerHTML = devices
      .map((device) =>
        `<li><strong>${device.name}</strong> · ${device.kind} · <span class="${device.status}">${device.status}</span></li>`
      )
      .join('');
  }

  // Populate target device selector in task form
  if (taskTargetDevice) {
    taskTargetDevice.replaceChildren();
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = 'Select target device...';
    taskTargetDevice.append(defaultOpt);
    for (const d of devices) {
      const opt = document.createElement('option');
      opt.value = d.id;
      opt.textContent = `${d.name} (${d.kind})`;
      taskTargetDevice.append(opt);
    }
  }

  // Populate interactive devices grid
  if (devicesManagerGrid) {
    devicesManagerGrid.replaceChildren();
    if (!devices.length) {
      devicesManagerGrid.innerHTML = '<p class="chat-hint">No registered devices found.</p>';
      return;
    }
    for (const d of devices) {
      const card = document.createElement('div');
      card.className = 'device-card';
      card.innerHTML = `
        <div class="device-card-header">
          <strong>${d.name}</strong>
          <span class="device-kind-badge">${d.kind}</span>
        </div>
        <div>
          <span class="device-status-badge ${d.status}">${d.status.toUpperCase()}</span>
          <small class="chat-hint" style="display:block; margin-top:4px;">ID: ${d.id}</small>
        </div>
        <div class="device-card-actions">
          <button class="secondary-button ping-dev-btn" type="button" data-id="${d.id}">Ping</button>
          <button class="secondary-button btn-danger del-dev-btn" type="button" data-id="${d.id}">Delete</button>
        </div>
      `;
      card.querySelector('.ping-dev-btn').addEventListener('click', () => pingDevice(d.id));
      card.querySelector('.del-dev-btn').addEventListener('click', () => deleteDevice(d.id));
      devicesManagerGrid.append(card);
    }
  }
}

function renderTasks(tasks) {
  currentTasksCache = tasks;
  if (taskList) {
    taskList.innerHTML = tasks
      .map((task) => `<li><strong>${task.task}</strong> · <span class="task-badge ${task.status}">${task.status}</span></li>`)
      .join('');
  }

  if (interactiveTaskTable) {
    interactiveTaskTable.replaceChildren();
    const filtered = activeTaskFilter === 'all'
      ? tasks
      : tasks.filter(t => t.status === activeTaskFilter);

    if (!filtered.length) {
      interactiveTaskTable.innerHTML = `<p class="chat-hint">No tasks in '${activeTaskFilter}' state.</p>`;
      return;
    }

    for (const t of filtered) {
      const row = document.createElement('div');
      row.className = 'task-row';
      row.innerHTML = `
        <div class="task-row-info">
          <strong>${t.task}</strong>
          <div>
            <span class="task-badge ${t.status}">${t.status.replace('_', ' ')}</span>
            <small class="chat-hint">Device: ${t.device_id} · Created: ${new Date(t.created_at).toLocaleTimeString()}</small>
          </div>
        </div>
        <div class="task-row-actions">
          ${t.status === 'queued' ? `<button class="secondary-button start-task-btn" type="button">Start</button>` : ''}
          ${t.status !== 'completed' ? `<button class="secondary-button complete-task-btn" type="button">Complete</button>` : ''}
          <button class="secondary-button btn-danger del-task-btn" type="button">Delete</button>
        </div>
      `;
      if (row.querySelector('.start-task-btn')) {
        row.querySelector('.start-task-btn').addEventListener('click', () => updateTaskStatus(t.id, 'in_progress'));
      }
      if (row.querySelector('.complete-task-btn')) {
        row.querySelector('.complete-task-btn').addEventListener('click', () => updateTaskStatus(t.id, 'completed'));
      }
      row.querySelector('.del-task-btn').addEventListener('click', () => deleteTask(t.id));
      interactiveTaskTable.append(row);
    }
  }
}

async function loadDashboard() {
  const [devices, tasks] = await Promise.all([
    fetchJson('/api/devices'),
    fetchJson('/api/tasks'),
  ]);
  renderDevices(devices);
  renderTasks(tasks);
}

async function pingDevice(deviceId) {
  try {
    await fetchJson(`/api/devices/${deviceId}/ping`, { method: 'POST' });
    await loadDashboard();
  } catch (error) {
    alert(`Could not ping device: ${error.message}`);
  }
}

async function deleteDevice(deviceId) {
  if (!confirm('Are you sure you want to remove this device and its associated tasks?')) return;
  try {
    await fetchJson(`/api/devices/${deviceId}`, { method: 'DELETE' });
    await loadDashboard();
  } catch (error) {
    alert(`Could not delete device: ${error.message}`);
  }
}

async function updateTaskStatus(taskId, status) {
  try {
    await fetchJson(`/api/tasks/${taskId}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
    await loadDashboard();
  } catch (error) {
    alert(`Could not update task status: ${error.message}`);
  }
}

async function deleteTask(taskId) {
  try {
    await fetchJson(`/api/tasks/${taskId}`, { method: 'DELETE' });
    await loadDashboard();
  } catch (error) {
    alert(`Could not delete task: ${error.message}`);
  }
}

if (deviceRegisterForm) {
  deviceRegisterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = devRegName.value.trim();
    const kind = devRegKind.value;
    if (!name) return;
    devRegStatus.textContent = 'Registering device...';
    try {
      await fetchJson('/api/devices', {
        method: 'POST',
        body: JSON.stringify({ name, kind }),
      });
      devRegName.value = '';
      devRegStatus.textContent = 'Device registered successfully!';
      setTimeout(() => { devRegStatus.textContent = ''; }, 3000);
      await loadDashboard();
    } catch (err) {
      devRegStatus.textContent = `Error: ${err.message}`;
    }
  });
}

if (taskEnqueueForm) {
  taskEnqueueForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const deviceId = taskTargetDevice.value;
    const task = taskDescription.value.trim();
    if (!deviceId || !task) return;
    taskEnqueueStatus.textContent = 'Enqueueing task...';
    try {
      await fetchJson('/api/tasks', {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, task }),
      });
      taskDescription.value = '';
      taskEnqueueStatus.textContent = 'Task queued successfully!';
      setTimeout(() => { taskEnqueueStatus.textContent = ''; }, 3000);
      await loadDashboard();
    } catch (err) {
      taskEnqueueStatus.textContent = `Error: ${err.message}`;
    }
  });
}

if (refreshDevicesBtn) {
  refreshDevicesBtn.addEventListener('click', loadDashboard);
}

if (taskQueueFilters) {
  taskQueueFilters.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      taskQueueFilters.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeTaskFilter = chip.dataset.filter;
      renderTasks(currentTasksCache);
    });
  });
}

/* ==========================================================================
   ARCHER IMAGE GENERATION & AI STUDIO
   ========================================================================== */
async function generateArcherImage(event) {
  event.preventDefault();
  const prompt = archerPrompt.value.trim();
  if (!prompt) {
    archerPrompt.focus();
    return;
  }
  archerButton.disabled = true;
  archerButton.textContent = 'Archer is generating...';
  archerMessage.textContent = 'Generating your image. Offline generation can take a few minutes on CPU.';
  try {
    const result = await fetchJson('/api/archer/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt, mode: archerMode.value }),
    });
    archerPreview.src = `${result.url}?t=${Date.now()}`;
    archerPreview.hidden = false;
    archerMessage.textContent = `Image generated ${result.mode === 'offline' ? 'offline' : 'online'} using ${result.model || result.source}.`;
    loadGallery();
  } catch (error) {
    archerMessage.textContent = `Archer generation failed: ${error.message}`;
  }
  archerButton.disabled = false;
  archerButton.textContent = 'Generate Via Archer';
}

async function loadArcherStatus() {
  try {
    const status = await fetchJson('/api/archer/status');
    const label = status.offline_ready
      ? `OFFLINE READY · ${status.model}`
      : `ONLINE MODE AVAILABLE · ${status.model} not installed`;
    archerStatus.textContent = label;
    archerStatus.classList.toggle('online', status.offline_ready);
    archerStatus.classList.toggle('offline', !status.offline_ready);
    if (studioArcherStatus) {
      studioArcherStatus.textContent = label;
      studioArcherStatus.classList.toggle('online', status.offline_ready);
    }
  } catch (error) {
    archerStatus.textContent = `Archer status unavailable: ${error.message}`;
    archerStatus.classList.add('offline');
  }
}

// AI Studio Generation
if (studioArcherForm) {
  studioArcherForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const prompt = studioArcherPrompt.value.trim();
    if (!prompt) return;
    const [w, h] = studioArcherRatio.value.split('x').map(Number);
    const mode = studioArcherMode.value;

    studioGenerateBtn.disabled = true;
    studioGenerateBtn.textContent = 'Generating artwork...';
    studioGenerateStatus.textContent = 'Archer synthesis in progress. Please wait...';

    try {
      const result = await fetchJson('/api/archer/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt, width: w, height: h, mode }),
      });
      studioPreviewImg.src = `${result.url}?t=${Date.now()}`;
      studioDownloadBtn.href = result.url;
      studioDownloadBtn.download = `archer_${Date.now()}.png`;
      studioOpenBtn.onclick = () => openImageModal(result.url, prompt);
      studioPreviewBox.hidden = false;
      studioGenerateStatus.textContent = `Art synthesized successfully (${result.mode})!`;
      loadGallery();
    } catch (err) {
      studioGenerateStatus.textContent = `Generation error: ${err.message}`;
    } finally {
      studioGenerateBtn.disabled = false;
      studioGenerateBtn.textContent = 'Generate Artwork';
    }
  });
}

// Style preset chips
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const current = studioArcherPrompt.value.trim();
    const preset = btn.dataset.preset;
    studioArcherPrompt.value = current ? `${current}, ${preset}` : preset;
    studioArcherPrompt.focus();
  });
});

// Gallery Management
async function loadGallery() {
  if (!galleryGrid) return;
  try {
    const images = await fetchJson('/api/archer/gallery');
    galleryGrid.replaceChildren();
    if (!images.length) {
      galleryGrid.innerHTML = '<p class="chat-hint">No artworks in gallery yet. Generate one above!</p>';
      return;
    }
    for (const item of images) {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      const sizeKb = Math.round(item.size_bytes / 1024);
      const dateStr = new Date(item.created_at).toLocaleDateString();
      card.innerHTML = `
        <div class="gallery-thumb-wrapper">
          <img class="gallery-thumb" src="${item.url}" alt="${item.filename}" loading="lazy" />
        </div>
        <div class="gallery-meta">
          <span>${dateStr}</span>
          <span>${sizeKb} KB</span>
        </div>
        <div class="gallery-card-actions">
          <button class="secondary-button view-art-btn" type="button">Enlarge</button>
          <a class="secondary-button" href="${item.url}" download="${item.filename}">Save</a>
          <button class="secondary-button btn-danger del-art-btn" type="button">Delete</button>
        </div>
      `;
      card.querySelector('.gallery-thumb-wrapper').addEventListener('click', () => openImageModal(item.url, item.filename));
      card.querySelector('.view-art-btn').addEventListener('click', () => openImageModal(item.url, item.filename));
      card.querySelector('.del-art-btn').addEventListener('click', async () => {
        if (!confirm(`Delete image ${item.filename}?`)) return;
        try {
          await fetchJson(`/api/archer/images/${item.filename}`, { method: 'DELETE' });
          loadGallery();
        } catch (err) {
          alert(`Error deleting image: ${err.message}`);
        }
      });
      galleryGrid.append(card);
    }
  } catch (error) {
    galleryGrid.innerHTML = `<p class="chat-hint">Could not load gallery: ${error.message}</p>`;
  }
}

if (refreshGalleryBtn) {
  refreshGalleryBtn.addEventListener('click', loadGallery);
}

function openImageModal(url, caption = '') {
  if (!imageModal) return;
  modalImg.src = url;
  modalCaption.textContent = caption;
  imageModal.hidden = false;
  imageModal.removeAttribute('hidden');
}

function closeImageModal() {
  if (!imageModal) return;
  imageModal.hidden = true;
  imageModal.setAttribute('hidden', '');
  if (modalImg) modalImg.removeAttribute('src');
}

if (closeModalBtn) {
  closeModalBtn.addEventListener('click', closeImageModal);
}
if (imageModal) {
  imageModal.addEventListener('click', (e) => {
    if (e.target === imageModal) closeImageModal();
  });
}

/* ==========================================================================
   NAVIGATION
   ========================================================================== */
document.querySelectorAll('.nav[data-view]').forEach((button) => {
  button.addEventListener('click', () => {
    const selectedView = button.dataset.view;
    document.querySelectorAll('.app-view').forEach((view) => {
      view.hidden = view.id !== selectedView;
    });
    document.querySelectorAll('.nav[data-view]').forEach((navButton) => {
      navButton.classList.toggle('active', navButton === button);
    });
    if (selectedView === 'devices-view') loadDashboard();
    if (selectedView === 'ai-studio-view') loadGallery();
  });
});

/* ==========================================================================
   LIVE TASKS MONITOR
   ========================================================================== */

/**
 * Append a single line to the sidebar live terminal.
 * @param {string} text - The text to display.
 * @param {string} [cssClass=''] - Extra class(es) on the line element for colour coding.
 * @param {Date|null} [ts=null] - Timestamp; defaults to now.
 */
function addTermLine(text, cssClass = '', ts = null) {
  if (!sidebarTermBody) return;
  const when = ts ? new Date(ts) : new Date();
  const timeStr = when.toTimeString().slice(0, 8); // HH:MM:SS

  const line = document.createElement('div');
  line.className = `term-line${cssClass ? ' ' + cssClass : ''}`;

  const timeEl = document.createElement('span');
  timeEl.className = 'term-time';
  timeEl.textContent = timeStr;

  const textEl = document.createElement('span');
  textEl.className = 'term-text';
  textEl.textContent = text;

  line.append(timeEl, textEl);
  sidebarTermBody.append(line);

  if (termAutoScroll) {
    sidebarTermBody.scrollTop = sidebarTermBody.scrollHeight;
  }
}

/**
 * Called on every SSE run update — prints only NEW log entries to the terminal.
 * @param {Object} run - The task-run object from the SSE stream.
 */
function appendTaskToTerminal(run) {
  const previousCount = termRunLogCounts.get(run.id) || 0;
  const logs = run.logs || [];

  // Print any lifecycle status change header when the run is brand new
  if (previousCount === 0) {
    addTermLine(`▶ [${run.category.toUpperCase()}] ${run.title}`, 'running', run.started_at);
  }

  // Print only the new log entries since last update
  const newEntries = logs.slice(previousCount);
  for (const entry of newEntries) {
    const lvl = (entry.level || 'info').toLowerCase();
    addTermLine(entry.message, `log-${lvl}`, entry.timestamp);
  }
  termRunLogCounts.set(run.id, logs.length);

  // Print completion line
  if ((run.status === 'completed' || run.status === 'failed') && previousCount < logs.length + 1) {
    const doneClass = run.status === 'completed' ? 'completed' : 'failed';
    const doneIcon = run.status === 'completed' ? '✓' : '✗';
    addTermLine(`${doneIcon} ${run.status.toUpperCase()} — ${run.title}`, doneClass, run.completed_at || undefined);
  }
}

function updateTaskRun(run) {
  // Feed the live sidebar terminal console
  appendTaskToTerminal(run);

  taskRuns.set(run.id, run);
  const orderedRuns = [...taskRuns.values()]
    .sort((left, right) => right.started_at.localeCompare(left.started_at));
  const counts = orderedRuns.reduce((totals, item) => {
    totals[item.status] = (totals[item.status] || 0) + 1;
    return totals;
  }, {});
  document.getElementById('task-running-count').textContent = counts.running || 0;
  document.getElementById('task-completed-count').textContent = counts.completed || 0;
  document.getElementById('task-failed-count').textContent = counts.failed || 0;
  taskRunsContainer.replaceChildren();
  if (!orderedRuns.length) {
    const emptyState = document.createElement('p');
    emptyState.className = 'chat-hint';
    emptyState.textContent = 'No tracked operations yet. Start a chat, generate an image, or manage devices.';
    taskRunsContainer.append(emptyState);
    return;
  }
  for (const item of orderedRuns) {
    const card = document.createElement('article');
    card.className = 'task-run';
    const heading = document.createElement('div');
    heading.className = 'task-run-heading';
    const title = document.createElement('h4');
    title.textContent = item.title;
    const status = document.createElement('span');
    status.className = `task-run-status ${item.status}`;
    status.textContent = item.status.toUpperCase();
    heading.append(title, status);
    const metadata = document.createElement('p');
    metadata.className = 'task-run-meta';
    metadata.textContent = `${item.category.toUpperCase()} · Started ${new Date(item.started_at).toLocaleString()}${item.completed_at ? ` · Ended ${new Date(item.completed_at).toLocaleTimeString()}` : ''}`;
    const log = document.createElement('ol');
    log.className = 'task-run-log';
    for (const entry of item.logs) {
      const line = document.createElement('li');
      line.className = `task-log-entry ${entry.level}`;
      const time = document.createElement('time');
      time.dateTime = entry.timestamp;
      time.textContent = new Date(entry.timestamp).toLocaleTimeString();
      const message = document.createElement('span');
      message.textContent = entry.message;
      line.append(time, message);
      log.append(line);
    }
    card.append(heading, metadata, log);
    taskRunsContainer.append(card);
  }
}

async function loadTaskRuns() {
  try {
    const runs = await fetchJson('/api/task-runs?limit=50');
    taskRuns.clear();
    runs.forEach(updateTaskRun);
    taskStreamStatus.textContent = taskEventSource?.readyState === EventSource.OPEN
      ? 'LIVE · STREAM CONNECTED'
      : 'History refreshed';
    taskStreamStatus.classList.toggle('online', taskEventSource?.readyState === EventSource.OPEN);
    taskStreamStatus.classList.toggle('offline', taskEventSource?.readyState !== EventSource.OPEN);
  } catch (error) {
    taskStreamStatus.textContent = `Could not load task history: ${error.message}`;
    taskStreamStatus.classList.add('offline');
  }
}

function connectTaskStream() {
  if (!window.EventSource) {
    taskStreamStatus.textContent = 'Live streaming is not supported by this browser.';
    taskStreamStatus.classList.add('offline');
    if (termLiveDot) termLiveDot.classList.add('disconnected');
    return;
  }
  taskEventSource = new EventSource('/api/task-runs/events');
  taskEventSource.addEventListener('open', () => {
    taskStreamStatus.textContent = 'LIVE · STREAM CONNECTED';
    taskStreamStatus.classList.remove('offline');
    taskStreamStatus.classList.add('online');
    if (termLiveDot) termLiveDot.classList.remove('disconnected');
  });
  taskEventSource.addEventListener('snapshot', (event) => {
    taskRuns.clear();
    JSON.parse(event.data).forEach(updateTaskRun);
  });
  taskEventSource.addEventListener('message', (event) => {
    updateTaskRun(JSON.parse(event.data));
  });
  taskEventSource.addEventListener('error', () => {
    taskStreamStatus.textContent = 'Reconnecting to live activity...';
    taskStreamStatus.classList.remove('online');
    taskStreamStatus.classList.add('offline');
    if (termLiveDot) termLiveDot.classList.add('disconnected');
  });
}

// Sidebar live terminal controls
if (termClearBtn && sidebarTermBody) {
  termClearBtn.addEventListener('click', () => {
    sidebarTermBody.replaceChildren();
    addTermLine('Console output cleared.', 'system-msg');
  });
}

if (termScrollBtn) {
  termScrollBtn.addEventListener('click', () => {
    termAutoScroll = !termAutoScroll;
    termScrollBtn.classList.toggle('active', termAutoScroll);
    termScrollBtn.title = termAutoScroll ? 'Autoscroll enabled' : 'Autoscroll paused';
    if (termAutoScroll && sidebarTermBody) {
      sidebarTermBody.scrollTop = sidebarTermBody.scrollHeight;
    }
  });
}

if (taskClearBtn) {
  taskClearBtn.addEventListener('click', async () => {
    try {
      await fetchJson('/api/task-runs/clear', { method: 'POST' });
      await loadTaskRuns();
    } catch (err) {
      alert(`Could not clear finished runs: ${err.message}`);
    }
  });
}

document.getElementById('task-refresh').addEventListener('click', loadTaskRuns);

/* ==========================================================================
   SOCIAL HUB & INSTAGRAM
   ========================================================================== */
function loadSocialDraft(platform) {
  const saved = localStorage.getItem(`${SOCIAL_DRAFT_KEY}${platform}`);
  if (!saved) {
    socialRecipient.value = '';
    socialDraft.value = '';
    socialDraftStatus.textContent = 'No saved draft for this platform.';
    return;
  }
  const draft = JSON.parse(saved);
  socialRecipient.value = draft.recipient || '';
  socialDraft.value = draft.text || '';
  socialDraftStatus.textContent = 'Saved draft loaded from this browser.';
}

function saveSocialDraft(platform = socialPlatform.value) {
  localStorage.setItem(
    `${SOCIAL_DRAFT_KEY}${platform}`,
    JSON.stringify({ recipient: socialRecipient.value.trim(), text: socialDraft.value })
  );
  socialDraftStatus.textContent = `Draft saved locally for ${socialPlatforms[platform].name}.`;
}

function openSocialPlatform(platform) {
  const service = socialPlatforms[platform];
  if (service) window.open(service.url, '_blank', 'noopener,noreferrer');
}

function setInstagramControls(connected) {
  document.getElementById('instagram-connect').hidden = connected;
  document.getElementById('instagram-disconnect').hidden = !connected;
  document.getElementById('instagram-refresh').hidden = !connected;
  document.getElementById('instagram-load-profile').hidden = !connected;
  document.getElementById('instagram-load-insights').hidden = !connected;
  document.getElementById('instagram-load-inbox').hidden = !connected;
  document.getElementById('instagram-publish-form').hidden = !connected;
  document.getElementById('instagram-message-form').hidden = !connected;
  instagramConnectionState.textContent = connected ? 'CONNECTED' : 'NOT CONNECTED';
  instagramConnectionState.classList.toggle('connected', connected);
}

async function loadInstagramStatus() {
  try {
    const status = await fetchJson('/api/instagram/status');
    instagramAccountId = status.user_id;
    instagramStatus.textContent = status.connected
      ? `CONNECTED · ${status.user_id}`
      : status.configured
        ? 'READY TO CONNECT'
        : 'META APP SETUP REQUIRED';
    instagramStatus.classList.toggle('online', status.connected);
    instagramStatus.classList.toggle('offline', !status.configured);
    setInstagramControls(status.connected);
    instagramNotice.textContent = status.configured
      ? status.connected
        ? `Connected to the official Instagram API. Granted: ${status.scopes.join(', ')}. Tokens stay in-memory only.`
        : 'Connect an Instagram Business or Creator account using Meta’s official sign-in.'
      : 'Set ORION_INSTAGRAM_APP_ID and ORION_INSTAGRAM_APP_SECRET to enable Instagram integration.';
    document.getElementById('instagram-connect').disabled = !status.configured;
    return status;
  } catch (error) {
    instagramStatus.textContent = `Instagram status unavailable: ${error.message}`;
    instagramStatus.classList.add('offline');
    setInstagramControls(false);
    return null;
  }
}

document.querySelectorAll('.open-social').forEach((button) => {
  button.addEventListener('click', () => openSocialPlatform(button.dataset.platform));
});
document.getElementById('social-draft-form').addEventListener('submit', (event) => {
  event.preventDefault();
  saveSocialDraft();
});
socialPlatform.addEventListener('change', () => {
  saveSocialDraft(activeSocialPlatform);
  activeSocialPlatform = socialPlatform.value;
  loadSocialDraft(socialPlatform.value);
});
document.getElementById('open-draft-platform').addEventListener('click', () => {
  openSocialPlatform(socialPlatform.value);
});

// Instagram actions
document.getElementById('instagram-connect').addEventListener('click', () => {
  window.location.assign('/api/instagram/connect');
});
document.getElementById('instagram-disconnect').addEventListener('click', async () => {
  try {
    await fetchJson('/api/instagram/connection', { method: 'DELETE' });
    instagramProfile.replaceChildren();
    instagramMedia.replaceChildren();
    instagramInbox.replaceChildren();
    instagramInsights.replaceChildren();
    instagramActionStatus.textContent = 'Instagram disconnected.';
    await loadInstagramStatus();
  } catch (error) {
    instagramActionStatus.textContent = `Could not disconnect: ${error.message}`;
  }
});
document.getElementById('instagram-refresh').addEventListener('click', async () => {
  try {
    await fetchJson('/api/instagram/refresh', { method: 'POST' });
    instagramActionStatus.textContent = 'Instagram access refreshed.';
    await loadInstagramStatus();
  } catch (error) {
    instagramActionStatus.textContent = `Could not refresh: ${error.message}`;
  }
});

/* ==========================================================================
   FORM LISTENERS & BOOTSTRAP
   ========================================================================== */
chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  askAi();
});
promptBox.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
archerForm.addEventListener('submit', generateArcherImage);
document.getElementById('clear-memory-btn').addEventListener('click', clearMemory);

// Initialize all modules
loadModelStatus();
loadArcherStatus();
loadConversation().catch((error) => {
  addMessage('assistant', `Could not load local memory: ${error.message}`);
});
loadDashboard().catch((error) => {
  aiResponse.textContent = `Could not load Orion dashboard data: ${error.message}`;
});
loadTaskRuns();
connectTaskStream();
loadGallery();
try {
  loadSocialDraft(socialPlatform.value);
} catch (error) {}
loadInstagramStatus();

const instagramCallback = new URLSearchParams(window.location.search);
if (instagramCallback.get('view') === 'social') {
  document.querySelector('.nav[data-view="social-view"]').click();
  if (instagramCallback.get('instagram') === 'connected') {
    instagramActionStatus.textContent = 'Instagram connected successfully!';
  } else if (instagramCallback.get('instagram') === 'error') {
    instagramActionStatus.textContent = `Instagram connection failed: ${instagramCallback.get('detail') || 'authorization was not completed'}`;
  }
  window.history.replaceState({}, document.title, '/');
}
