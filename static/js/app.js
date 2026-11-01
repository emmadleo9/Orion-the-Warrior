const API_BASE = "http://127.0.0.1:8000";

const els = {
  cpu: document.getElementById("cpu"),
  ram: document.getElementById("ram"),
  disk: document.getElementById("disk"),
  status: document.getElementById("status"),
  cpuFill: document.getElementById("cpu-fill"),
  ramFill: document.getElementById("ram-fill"),
  diskFill: document.getElementById("disk-fill"),
  logs: document.getElementById("logs"),
  uptime: document.getElementById("uptime"),
};

let logCount = 0;

function fmt(n) {
  return Number(n).toFixed(1);
}

function addLog(text, type = "ok") {
  const now = new Date();
  const time = now.toLocaleTimeString("en-US", { hour12: false });
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<span class="time">[${time}]</span>${text}`;
  els.logs.prepend(entry);
  logCount++;
  if (logCount > 120) {
    const last = els.logs.lastElementChild;
    if (last) last.remove();
  }
}

async function fetchSystem() {
  try {
    const res = await fetch(`${API_BASE}/api/system`, { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    const cpu = data.cpu_percent ?? data.cpu ?? 0;
    const ram = data.memory_percent ?? data.ram_percent ?? data.memory ?? 0;
    const disk = data.disk_percent ?? data.disk ?? 0;
    const status = data.status ?? "online";
    const uptime = data.uptime ?? "";

    els.cpu.textContent = fmt(cpu) + "%";
    els.ram.textContent = fmt(ram) + "%";
    els.disk.textContent = fmt(disk) + "%";
    els.status.textContent = status.toUpperCase();
    if (els.uptime) els.uptime.textContent = uptime;

    els.cpuFill.style.width = Math.min(100, Math.max(0, cpu)) + "%";
    els.ramFill.style.width = Math.min(100, Math.max(0, ram)) + "%";
    els.diskFill.style.width = Math.min(100, Math.max(0, disk)) + "%";

    if (cpu > 80) addLog(`High CPU: ${fmt(cpu)}%`, "warn");
    if (ram > 85) addLog(`High RAM: ${fmt(ram)}%`, "warn");
    if (disk > 90) addLog(`High Disk: ${fmt(disk)}%`, "err");
  } catch (err) {
    addLog(`System fetch failed: ${err.message}`, "err");
  }
}

function init() {
  fetchSystem();
  setInterval(fetchSystem, 2000);
  addLog("Orion dashboard connected to http://127.0.0.1:8000/api/system");
}

document.addEventListener("DOMContentLoaded", init);
