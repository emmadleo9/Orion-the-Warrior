const promptBox = document.getElementById('prompt-box');
const aiResponse = document.getElementById('ai-response');
const deviceList = document.getElementById('device-list');
const taskList = document.getElementById('task-list');

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  return response.json();
}

async function loadDevices() {
  const devices = await fetchJson('/api/devices');
  deviceList.innerHTML = devices
    .map((device) => `<li><strong>${device.name}</strong> · ${device.kind} · ${device.status}</li>`)
    .join('');
}

async function loadTasks() {
  const tasks = await fetchJson('/api/tasks');
  taskList.innerHTML = tasks
    .map((task) => `<li><strong>${task.task}</strong> · ${task.status}</li>`)
    .join('');
}

async function askAi() {
  const prompt = promptBox.value.trim();
  if (!prompt) {
    aiResponse.textContent = 'Please enter a prompt for Nico de Angelo.';
    return;
  }

  const result = await fetchJson('/api/assistant/respond', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });

  aiResponse.textContent = result.message;
}

async function generateImage() {
  const prompt = promptBox.value.trim() || 'A warrior scene with a futuristic command center';
  const result = await fetchJson('/api/assistant/generate-image', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });

  aiResponse.textContent = `Image generated: ${result.path}`;
}

async function seedTask() {
  const devices = await fetchJson('/api/devices');
  if (!devices.length) return;

  const firstDevice = devices[0];
  await fetchJson('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({
      device_id: firstDevice.id,
      task: 'Sync messaging apps and review alerts',
    }),
  });

  await loadTasks();
}

document.getElementById('ask-ai-btn').addEventListener('click', askAi);
document.getElementById('generate-image-btn').addEventListener('click', generateImage);

loadDevices();
loadTasks();
seedTask();
