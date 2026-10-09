const promptBox = document.getElementById('prompt-box');
const aiResponse = document.getElementById('ai-response');
const deviceList = document.getElementById('device-list');
const taskList = document.getElementById('task-list');
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const sendButton = document.getElementById('ask-ai-btn');
const modelStatus = document.getElementById('model-status');
const memoryStatus = document.getElementById('memory-status');
const archerForm = document.getElementById('archer-form');
const archerPrompt = document.getElementById('archer-prompt');
const archerMode = document.getElementById('archer-mode');
const archerButton = document.getElementById('generate-archer-btn');
const archerStatus = document.getElementById('archer-status');
const archerMessage = document.getElementById('archer-message');
const archerPreview = document.getElementById('archer-preview');
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
const taskRunsContainer = document.getElementById('task-runs');
const taskStreamStatus = document.getElementById('task-stream-status');
const taskRuns = new Map();
let taskEventSource = null;
let instagramAccountId = null;
let activeSocialPlatform = socialPlatform.value;
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
        ? `Connected to the official Instagram API. Granted: ${status.scopes.join(', ')}. The access token stays in this Orion process and is cleared when the server restarts.`
        : 'Connect an Instagram Business or Creator account using Meta’s official sign-in. Orion requests profile/media, publishing, comments, and messaging permissions.'
      : 'Set ORION_INSTAGRAM_APP_ID and ORION_INSTAGRAM_APP_SECRET from your Meta developer app, and configure the callback URL shown in the setup guide.';
    document.getElementById('instagram-connect').disabled = !status.configured;
    return status;
  } catch (error) {
    instagramStatus.textContent = `Instagram status unavailable: ${error.message}`;
    instagramStatus.classList.add('offline');
    setInstagramControls(false);
    return null;
  }
}

async function loadInstagramProfileAndMedia() {
  instagramActionStatus.textContent = 'Loading Instagram profile and recent media...';
  try {
    const [profile, media] = await Promise.all([
      fetchJson('/api/instagram/profile'),
      fetchJson('/api/instagram/media?limit=20'),
    ]);
    const username = document.createElement('strong');
    username.textContent = profile.username ? `@${profile.username}` : 'Instagram profile';
    const details = document.createElement('span');
    details.textContent = ` · ${profile.account_type || 'Professional'} · ${profile.media_count ?? 0} posts`;
    instagramProfile.replaceChildren(username, details);
    renderInstagramMedia(media.data || []);
    instagramActionStatus.textContent = 'Profile and media loaded.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not load Instagram profile/media: ${error.message}`;
  }
}

function renderInstagramMedia(items) {
  instagramMedia.replaceChildren();
  const heading = document.createElement('h4');
  heading.textContent = 'Recent media';
  instagramMedia.append(heading);
  if (!items.length) {
    instagramMedia.append(document.createTextNode('No media returned by Instagram.'));
    return;
  }
  for (const item of items) {
    const card = document.createElement('article');
    card.className = 'instagram-item';
    if (item.media_url && item.media_type === 'VIDEO') {
      const video = document.createElement('video');
      video.src = item.media_url;
      video.controls = true;
      video.preload = 'metadata';
      video.className = 'instagram-media-preview';
      card.append(video);
    } else if (item.media_url && item.media_type !== 'VIDEO') {
      const image = document.createElement('img');
      image.src = item.media_url;
      image.alt = item.caption || 'Instagram post';
      image.loading = 'lazy';
      image.className = 'instagram-media-preview';
      card.append(image);
    }
    const summary = document.createElement('p');
    summary.textContent = `${item.media_type || 'MEDIA'} · ${item.timestamp || ''} · ${item.comments_count ?? 0} comments${item.caption ? ` · ${item.caption}` : ''}`;
    card.append(summary);
    if (item.permalink) {
      const link = document.createElement('a');
      link.href = item.permalink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Open on Instagram ↗';
      card.append(link);
    }
    const commentsButton = document.createElement('button');
    commentsButton.className = 'secondary-button';
    commentsButton.type = 'button';
    commentsButton.textContent = 'View comments';
    commentsButton.addEventListener('click', () => loadInstagramComments(item.id, card));
    card.append(commentsButton);
    instagramMedia.append(card);
  }
}

async function loadInstagramComments(mediaId, container) {
  try {
    const result = await fetchJson(`/api/instagram/media/${encodeURIComponent(mediaId)}/comments`);
    let list = container.querySelector('.instagram-comment-list');
    if (!list) {
      list = document.createElement('div');
      list.className = 'instagram-comment-list';
      container.append(list);
    }
    list.replaceChildren();
    for (const comment of result.data || []) {
      const row = document.createElement('div');
      row.className = 'instagram-comment';
      const text = document.createElement('p');
      text.textContent = `@${comment.username || 'user'}: ${comment.text || ''}`;
      const reply = document.createElement('form');
      reply.className = 'instagram-inline-reply';
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 2000;
      input.placeholder = 'Reply to this comment';
      input.required = true;
      const submit = document.createElement('button');
      submit.className = 'secondary-button';
      submit.type = 'submit';
      submit.textContent = 'Reply';
      reply.append(input, submit);
      reply.addEventListener('submit', async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
          await fetchJson(`/api/instagram/comments/${encodeURIComponent(comment.id)}/replies`, {
            method: 'POST',
            body: JSON.stringify({ message: input.value }),
          });
          input.value = '';
          instagramActionStatus.textContent = 'Instagram comment reply sent.';
        } catch (error) {
          instagramActionStatus.textContent = `Could not reply to comment: ${error.message}`;
        } finally {
          submit.disabled = false;
        }
      });
      row.append(text, reply);
      list.append(row);
    }
    if (!result.data?.length) list.textContent = 'No comments returned for this post.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not load comments: ${error.message}`;
  }
}

async function loadInstagramInbox() {
  instagramActionStatus.textContent = 'Loading Instagram conversations...';
  try {
    const result = await fetchJson('/api/instagram/conversations');
    instagramInbox.replaceChildren();
    const heading = document.createElement('h4');
    heading.textContent = 'Conversations';
    instagramInbox.append(heading);
    for (const conversation of result.data || []) {
      const button = document.createElement('button');
      button.className = 'instagram-conversation secondary-button';
      button.type = 'button';
      button.textContent = `Conversation · ${conversation.updated_time || conversation.id}`;
      button.addEventListener('click', () => loadInstagramConversation(conversation.id));
      instagramInbox.append(button);
    }
    if (!result.data?.length) instagramInbox.append(document.createTextNode('No conversations returned.'));
    instagramActionStatus.textContent = 'Instagram inbox loaded.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not load Instagram inbox: ${error.message}`;
  }
}

async function loadInstagramConversation(conversationId) {
  try {
    const result = await fetchJson(`/api/instagram/conversations/${encodeURIComponent(conversationId)}/messages`);
    const messages = result.messages?.data || result.data || [];
    const list = document.createElement('div');
    list.className = 'instagram-message-list';
    let recipientId = '';
    for (const message of messages) {
      const row = document.createElement('p');
      const sender = message.from?.username || message.from?.id || 'Instagram user';
      row.textContent = `${sender}: ${message.message || '[attachment]'}`;
      list.append(row);
      if (message.from?.id && message.from.id !== instagramAccountId) recipientId = message.from.id;
    }
    instagramInbox.append(list);
    if (recipientId) document.getElementById('instagram-recipient-id').value = recipientId;
    instagramActionStatus.textContent = 'Conversation loaded. Instagram messaging API policy limits replies to eligible conversations.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not load conversation: ${error.message}`;
  }
}

async function loadInstagramInsights() {
  instagramActionStatus.textContent = 'Loading Instagram insights...';
  try {
    const result = await fetchJson('/api/instagram/insights?period=day');
    instagramInsights.replaceChildren();
    const heading = document.createElement('h4');
    heading.textContent = 'Account insights';
    instagramInsights.append(heading);
    for (const metric of result.data || []) {
      const item = document.createElement('p');
      item.textContent = `${metric.title || metric.name}: ${JSON.stringify(metric.values || metric.total_value || [])}`;
      instagramInsights.append(item);
    }
    if (!result.data?.length) instagramInsights.append(document.createTextNode('No insight metrics returned.'));
    instagramActionStatus.textContent = 'Instagram insights loaded.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not load insights: ${error.message}`;
  }
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

function setTelegramControls(status) {
  telegramConnected = Boolean(status.connected);
  telegramLoginForm.hidden = telegramConnected || !status.configured || status.proxy_error || status.waiting_for_code;
  telegramCodeForm.hidden = telegramConnected || !status.waiting_for_code;
  telegramPasswordForm.hidden = telegramConnected || !status.waiting_for_password;
  document.getElementById('telegram-refresh').disabled = !status.configured || Boolean(status.proxy_error);
  document.getElementById('telegram-import-all').disabled = !telegramConnected;
  document.getElementById('telegram-disconnect').hidden = !telegramConnected;
  telegramConnectionState.textContent = telegramConnected ? 'CONNECTED' : 'NOT CONNECTED';
  telegramConnectionState.classList.toggle('connected', telegramConnected);
  telegramSendButton.disabled = !telegramConnected || !selectedTelegramChat || telegramArchiveMode;
  telegramMessageInput.disabled = telegramSendButton.disabled;
}

async function loadTelegramStatus() {
  try {
    const status = await fetchJson('/api/telegram/status');
    telegramStatus.textContent = status.connected
      ? `CONNECTED · ${status.user?.username ? `@${status.user.username}` : status.user?.first_name || 'Telegram account'}`
      : status.proxy_error
        ? 'TELEGRAM PROXY SETTINGS INVALID'
        : status.configured
          ? status.waiting_for_password
            ? 'TWO-STEP VERIFICATION REQUIRED'
            : status.waiting_for_code
              ? 'LOGIN CODE SENT'
              : status.session_exists
                ? 'SAVED SESSION · REFRESH CHATS TO RECONNECT'
                : 'READY TO CONNECT'
          : 'TELEGRAM API SETUP REQUIRED';
    telegramStatus.classList.toggle('online', status.connected);
    telegramStatus.classList.toggle('offline', !status.configured || Boolean(status.proxy_error));
    setTelegramControls(status);
    telegramProxyClear.hidden = !status.proxy_configured && !status.proxy_error && !status.proxy_saved_count;
    telegramProxyCount.textContent = `${status.proxy_saved_count || 0} saved`;
    telegramNotice.textContent = status.proxy_error
      ? status.proxy_error
      : status.configured
        ? `Orion keeps your Telegram authorization session locally. Use Import all chats, messages & media to archive accessible history and download available attachments. Your login code and 2-step password are never stored.${status.proxy_configured ? ` A ${status.proxy_type} proxy is configured locally.` : ' If your network blocks Telegram, add an MTProto proxy link below or configure a SOCKS5, SOCKS4, or HTTP proxy locally.'}`
        : 'Create your Telegram API credentials at my.telegram.org/apps, then set ORION_TELEGRAM_API_ID and ORION_TELEGRAM_API_HASH before starting Orion. Credentials and the authorized session stay on this computer.';
    await loadTelegramDialogs(!status.connected);
    await loadTelegramImportStatus();
    await loadTelegramProxies();
    return status;
  } catch (error) {
    telegramStatus.textContent = `Telegram status unavailable: ${error.message}`;
    telegramStatus.classList.add('offline');
    telegramActionStatus.textContent = `Could not check Telegram status: ${error.message}`;
    return null;
  }
}

function renderDevices(devices) {
  deviceList.innerHTML = devices
    .map((device) =>
      `<li><strong>${device.name}</strong> · ${device.kind} · <span>${device.status}</span></li>`
    )
    .join('');
}

function renderTasks(tasks) {
  taskList.innerHTML = tasks
    .map((task) => `<li><strong>${task.task}</strong> · ${task.status}</li>`)
    .join('');
}

async function loadDashboard() {
  const [devices, tasks] = await Promise.all([
    fetchJson('/api/devices'),
    fetchJson('/api/tasks'),
  ]);
  renderDevices(devices);
  if (tasks.length || !devices.length) {
    renderTasks(tasks);
    return;
  }

  const task = await fetchJson('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({
      device_id: devices[0].id,
      task: 'Sync messaging apps and review alerts',
    }),
  });
  renderTasks([task]);
}

async function askAi() {
  const prompt = promptBox.value.trim();
  if (!prompt) {
    promptBox.focus();
    return;
  }

  addMessage('user', prompt);
  promptBox.value = '';
  sendButton.disabled = true;
  sendButton.textContent = 'Nico is thinking...';
  const pendingMessage = addMessage('assistant', 'Thinking...', true);

  try {
    const response = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt, conversation_id: conversationId }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    if (!response.body) throw new Error('Streaming is not supported by this browser.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let reply = '';
    let completed = false;
    let paintQueued = false;
    const flushReply = () => {
      pendingMessage.querySelector('p').textContent = reply;
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
            liveData.textContent = `LIVE DATA · ${event.tools_used.join(' · ')}`;
            pendingMessage.append(liveData);
          }
          aiResponse.textContent = event.message;
        }
      }
    }
    if (paintQueued) flushReply();
    if (!completed) throw new Error('Nico’s response stream ended unexpectedly.');
    pendingMessage.classList.remove('pending-message');
  } catch (error) {
    pendingMessage.querySelector('p').textContent = `Connection issue: ${error.message}`;
    aiResponse.textContent = error.message;
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Send message';
    promptBox.focus();
  }
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

function addMessage(role, text, pending = false) {
  const message = document.createElement('div');
  message.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;
  if (pending) message.classList.add('pending-message');

  const author = document.createElement('span');
  author.className = 'message-author';
  author.textContent = role === 'user' ? 'YOU' : 'NICO';

  const content = document.createElement('p');
  content.textContent = text;
  message.append(author, content);
  chatMessages.append(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return message;
}

async function loadModelStatus() {
  try {
    const status = await fetchJson('/api/assistant/status');
    modelStatus.textContent = status.available
      ? status.installed
        ? `● ${status.model} ready · live tools enabled`
        : `● Ollama online · install ${status.model}`
      : '● Ollama offline';
    modelStatus.classList.toggle('online', status.available && status.installed);
    modelStatus.classList.toggle('offline', !status.available || !status.installed);
  } catch (error) {
    modelStatus.textContent = `● Status unavailable: ${error.message}`;
    modelStatus.classList.add('offline');
  }
}

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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, mode: archerMode.value }),
    });
    archerPreview.src = `${result.url}?t=${Date.now()}`;
    archerPreview.hidden = false;
    archerMessage.textContent = `Image generated ${result.mode === 'offline' ? 'offline' : 'online'} using ${result.model || result.source}.`;
  } catch (error) {
    archerMessage.textContent = `Archer generation failed: ${error.message}`;
  }
  archerButton.disabled = false;
  archerButton.textContent = 'Generate Via Archer';
}

async function loadArcherStatus() {
  try {
    const status = await fetchJson('/api/archer/status');
    archerStatus.textContent = status.offline_ready
      ? `OFFLINE READY · ${status.model}`
      : `ONLINE MODE AVAILABLE · ${status.model} not installed`;
    archerStatus.classList.toggle('online', status.offline_ready);
    archerStatus.classList.toggle('offline', !status.offline_ready);
  } catch (error) {
    archerStatus.textContent = `Archer status unavailable: ${error.message}`;
    archerStatus.classList.add('offline');
  }
}

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
document.querySelectorAll('.nav[data-view]').forEach((button) => {
  button.addEventListener('click', () => {
    const selectedView = button.dataset.view;
    document.querySelectorAll('.app-view').forEach((view) => {
      view.hidden = view.id !== selectedView;
    });
    document.querySelectorAll('.nav[data-view]').forEach((navButton) => {
      navButton.classList.toggle('active', navButton === button);
    });
  });
});
document.querySelectorAll('.open-social').forEach((button) => {
  button.addEventListener('click', () => openSocialPlatform(button.dataset.platform));
});
document.getElementById('social-draft-form').addEventListener('submit', (event) => {
  event.preventDefault();
  try {
    saveSocialDraft();
  } catch (error) {
    socialDraftStatus.textContent = `Could not save this browser draft: ${error.message}`;
  }
});
socialPlatform.addEventListener('change', () => {
  try {
    saveSocialDraft(activeSocialPlatform);
    activeSocialPlatform = socialPlatform.value;
    loadSocialDraft(socialPlatform.value);
  } catch (error) {
    socialDraftStatus.textContent = `Could not load this browser draft: ${error.message}`;
  }
});
document.getElementById('open-draft-platform').addEventListener('click', () => {
  openSocialPlatform(socialPlatform.value);
});
function updateTaskRun(run) {
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
    emptyState.textContent = 'No tracked operations yet. Start a chat, generate an image, or use an Instagram action.';
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
    return;
  }
  taskEventSource = new EventSource('/api/task-runs/events');
  taskEventSource.addEventListener('open', () => {
    taskStreamStatus.textContent = 'LIVE · STREAM CONNECTED';
    taskStreamStatus.classList.remove('offline');
    taskStreamStatus.classList.add('online');
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
  });
}

document.getElementById('task-refresh').addEventListener('click', loadTaskRuns);
loadTaskRuns();
connectTaskStream();
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
    instagramActionStatus.textContent = 'Instagram disconnected from this Orion process.';
    await loadInstagramStatus();
  } catch (error) {
    instagramActionStatus.textContent = `Could not disconnect Instagram: ${error.message}`;
  }
});
document.getElementById('instagram-refresh').addEventListener('click', async () => {
  try {
    await fetchJson('/api/instagram/refresh', { method: 'POST' });
    instagramActionStatus.textContent = 'Instagram access refreshed.';
    await loadInstagramStatus();
  } catch (error) {
    instagramActionStatus.textContent = `Could not refresh Instagram access: ${error.message}`;
  }
});
document.getElementById('instagram-load-profile').addEventListener('click', loadInstagramProfileAndMedia);
document.getElementById('instagram-load-insights').addEventListener('click', loadInstagramInsights);
document.getElementById('instagram-load-inbox').addEventListener('click', loadInstagramInbox);
document.getElementById('instagram-publish-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  instagramActionStatus.textContent = 'Publishing image to Instagram...';
  try {
    const result = await fetchJson('/api/instagram/publish', {
      method: 'POST',
      body: JSON.stringify({
        image_url: document.getElementById('instagram-image-url').value.trim(),
        caption: document.getElementById('instagram-caption').value,
      }),
    });
    instagramActionStatus.textContent = `Instagram published media ID ${result.id || 'successfully'}.`;
    await loadInstagramProfileAndMedia();
  } catch (error) {
    instagramActionStatus.textContent = `Could not publish to Instagram: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});
document.getElementById('instagram-message-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await fetchJson('/api/instagram/messages', {
      method: 'POST',
      body: JSON.stringify({
        recipient_id: document.getElementById('instagram-recipient-id').value.trim(),
        message: document.getElementById('instagram-message-text').value,
      }),
    });
    document.getElementById('instagram-message-text').value = '';
    instagramActionStatus.textContent = 'Instagram message sent.';
  } catch (error) {
    instagramActionStatus.textContent = `Could not send Instagram message: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

loadModelStatus();
loadArcherStatus();
loadConversation().catch((error) => {
  addMessage('assistant', `Could not load local memory: ${error.message}`);
});
loadDashboard().catch((error) => {
  aiResponse.textContent = `Could not load Orion dashboard data: ${error.message}`;
});
try {
  loadSocialDraft(socialPlatform.value);
} catch (error) {
  socialDraftStatus.textContent = `Could not load this browser draft: ${error.message}`;
}
loadInstagramStatus();
const instagramCallback = new URLSearchParams(window.location.search);
if (instagramCallback.get('view') === 'social') {
  document.querySelector('.nav[data-view="social-view"]').click();
  if (instagramCallback.get('instagram') === 'connected') {
    instagramActionStatus.textContent = 'Instagram connected successfully. Choose an account-manager action.';
  } else if (instagramCallback.get('instagram') === 'error') {
    instagramActionStatus.textContent = `Instagram connection failed: ${instagramCallback.get('detail') || 'authorization was not completed'}`;
  }
  window.history.replaceState({}, document.title, '/');
}
