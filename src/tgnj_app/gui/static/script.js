// List your fields in the exact order you want to move through them
const formOrder = [
  "sku_group",
  "item_id",
  "shape",
  "weight",
  "length",
  "width",
  "depth",
];

function capitalize(str) {
  if (!str) return "";
  return str.slice(0, 1).toUpperCase() + str.slice(1);
}

function setupKeyboardNavigation() {
  formOrder.forEach((id, index) => {
    const input = document.getElementById(id);

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        if (index < formOrder.length - 1) {
          const nextField = document.getElementById(formOrder[index + 1]);
          nextField.focus();
          nextField.select();
        } else {
          handleFormSubmit(event);
        }
      }
    });
  });
}

async function setItemId(data) {
  if (!data || data.length === 0) {
    document.getElementById("item_id").value = 1;
    return;
  }
  document.getElementById("item_id").value = data[data.length - 1].sku_id + 1;
}

async function loadItemsByGroup(sku_group) {
  if (!sku_group) return;
  try {
    const response = await fetch(`/api/getData/${sku_group}`);
    const data = await response.json();
    console.log("got the data!");
    renderTable(data);
    setItemId(data);
    document.getElementById("shape").value =
      `${data[data.length - 1].shape.charAt(0).toUpperCase() + data[data.length - 1].shape.slice(1)}`;
    scrollToEnd();
  } catch (error) {
    console.error("error loading items: ", error);
  }
}

async function renderTable(data) {
  const tbody = document.getElementById("display-table-body");
  tbody.innerHTML = "";
  if (!data || data.length === 0) {
    tbody.innerHTML = `<tr class = "table-row" style=""= ><td colspan = '7' style = 'text-align:center;'>No items found in this group.</td></tr>`;
    return;
  }
  counter = 0;
  data.forEach((item) => {
    counter++;
    const row = document.createElement("tr");
    const formattedId = String(item.sku_id).padStart(3, "0");
    row.classList.add("table-row");
    if (counter == data.length) {
      row.id = "last-row";
    }
    if (counter % 2 === 0) {
      row.classList.add("alt-row");
    }
    let etsyStatusHtml = '<span class="badge badge-unlisted" style="opacity:0.6;">Unlisted</span>';
    let actionBtnHtml = `<span class="delete-button" title="Delete Item" onclick="deleteItem('${item.sku_group}',${item.sku_id})"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" class="delete-icon"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg></span>`;

    if (item.status === 'SOLD') {
      const soldPrice = item.sold_price ? `$${Number(item.sold_price).toFixed(2)}` : '';
      const channel = item.sold_channel ? `(${item.sold_channel})` : '';
      etsyStatusHtml = `<span class="badge badge-sold">🔴 Sold ${soldPrice} ${channel}</span>`;
      actionBtnHtml = `<button class="hdr-btn" style="padding:2px 8px; font-size:0.75rem;" title="Restore to Stock" onclick="restoreItemUI('${item.sku_group}',${item.sku_id})">↩️ Restore</button>`;
    } else if (item.etsy_listing_id || item.status === 'LISTED_ETSY') {
      const listingId = item.etsy_listing_id || '';
      const etsyLink = listingId ? `https://www.etsy.com/listing/${listingId}` : 'https://www.etsy.com/your/shops/me/tools/listings';
      etsyStatusHtml = `<a href="${etsyLink}" target="_blank" class="badge badge-listed" style="text-decoration:none;" onclick="event.stopPropagation();">🧡 Listed #${listingId} ↗</a>`;
      actionBtnHtml = `<button class="hdr-btn" style="padding:2px 8px; font-size:0.75rem; border-color:#e74c3c; color:#e74c3c;" title="Mark as Sold" onclick="markSoldUI('${item.sku_group}',${item.sku_id})">🏷️ Sold</button> ${actionBtnHtml}`;
    } else {
      actionBtnHtml = `<button class="hdr-btn" style="padding:2px 8px; font-size:0.75rem; border-color:#e74c3c; color:#e74c3c;" title="Mark as Sold" onclick="markSoldUI('${item.sku_group}',${item.sku_id})">🏷️ Sold</button> ${actionBtnHtml}`;
    }

    row.innerHTML = `
    <td><strong>${item.sku_group}-${formattedId}</strong></td>
    <td contenteditable="true" onblur="editItem('${item.sku_group}',${item.sku_id},'shape',this.innerText)">${item.shape}</td>
    <td contenteditable="true" onblur="editItem('${item.sku_group}',${item.sku_id},'weight',this.innerText)">${Number(item.weight).toFixed(2)}</td>
    <td contenteditable="true" onblur="editItem('${item.sku_group}',${item.sku_id},'length',this.innerText)">${item.length}</td>
    <td contenteditable="true" onblur="editItem('${item.sku_group}',${item.sku_id},'width',this.innerText)">${item.width}</td>
    <td contenteditable="true" onblur="editItem('${item.sku_group}',${item.sku_id},'depth',this.innerText)">${item.depth}</td>
    <td>${etsyStatusHtml}</td>
    <td class="deleteCol" onclick="event.stopPropagation();" style="display:flex; align-items:center; gap:6px; justify-content:center;">${actionBtnHtml}</td>
    `;
    tbody.appendChild(row);
  });
}

async function editItem(sku_group, sku_id, property, value) {
  payload = {};
  payload[property] = value;
  document.getElementById("weight").focus();
  success = await fetch(`/api/editItem/${sku_group}/${sku_id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  liveLoadGroup();
}

let debounceTimer;
function liveLoadGroup() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    const input = document.getElementById("sku_group");
    const groupCode = input.value.trim().toUpperCase();

    if (groupCode.length > 0) {
      await loadItemsByGroup(groupCode);
      input.value = groupCode;
    } else {
      document.getElementById("display-table-body").innerHTML = "";
    }
  }, 300);
}

async function deleteItem(sku_group, sku_id) {
  if (confirm(`are you sure you wanna delete item ${sku_group}-${sku_id}`)) {
    success = await fetch(`/api/deleteItem/${sku_group}/${sku_id}`, {
      method: "DELETE",
    });
  }
  liveLoadGroup();
}

async function markSoldUI(sku_group, sku_id) {
  const formattedId = String(sku_id).padStart(3, "0");
  const priceStr = prompt(`Mark ${sku_group}-${formattedId} as SOLD?\nEnter sale price ($ USD):`, "12.99");
  if (priceStr === null) return; // User cancelled
  const price = parseFloat(priceStr) || 0.0;
  const channel = prompt("Enter sales channel (e.g. Offline, Etsy, Instagram):", "Offline") || "Offline";

  try {
    const res = await fetch(`/api/markSold/${sku_group}/${sku_id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ price, channel })
    });
    if (res.ok) {
      liveLoadGroup();
    } else {
      alert('Error marking item as sold.');
    }
  } catch (e) {
    alert('Error marking item as sold: ' + e);
  }
}

async function restoreItemUI(sku_group, sku_id) {
  const formattedId = String(sku_id).padStart(3, "0");
  if (!confirm(`Restore ${sku_group}-${formattedId} back to active inventory?`)) return;
  try {
    const res = await fetch(`/api/restoreItem/${sku_group}/${sku_id}`, {
      method: 'POST'
    });
    if (res.ok) {
      liveLoadGroup();
    } else {
      alert('Error restoring item.');
    }
  } catch (e) {
    alert('Error restoring item: ' + e);
  }
}

async function handleFormSubmit() {
  const payload = {
    sku_group: document.getElementById("sku_group").value,
    sku_id: parseInt(document.getElementById("item_id").value),
    shape: document.getElementById("shape").value.toLowerCase(),
    weight: parseFloat(document.getElementById("weight").value),
    length: parseInt(document.getElementById("length").value),
    width: parseInt(document.getElementById("width").value),
    depth: parseInt(document.getElementById("depth").value),
  };

  for (const key in payload) {
    if (Object.hasOwnProperty.call(payload, key)) {
      if (!payload[key] || payload[key].length === 0) {
        alert("enter all fields!");
        return;
      }
    }
  }
  fetch(`/api/addItem`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
    },
    body: JSON.stringify(payload),
  });
  document.getElementById("weight").value = "";
  document.getElementById("length").value = "";
  document.getElementById("width").value = "";
  document.getElementById("depth").value = "";
  liveLoadGroup();
  document.getElementById("weight").focus();
  item_id = document.getElementById("item_id");
  item_id.value = String(Number(item_id.value) + 1);
}

function scrollToEnd() {
  const row = document.getElementById("last-row");
  if (row) row.scrollIntoView({ behaviour: "smooth", block: "end" });
}

async function getDbPath() {
  response = await fetch("api/getDbPath", {
    method: "GET",
  });
  data = await response.json();
  db_field = document.getElementById("db_path");
  db_field.innerText = data["db_Path"];
}

async function setDbPath() {
  dbPathInput = document.getElementById("db_path");
  if (!dbPathInput.innerHTML || dbPathInput.innerHTML.length === 0) {
    alert("Enter a db Path");
    getDbPath();
    return;
  }
  payload = {
    db_Path: dbPathInput.innerHTML,
  };
  try {
    response = await fetch("api/setDbPath", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      if (response.status === 404) {
        alert("no database found at provided path, please verify path");
        getDbPath();
      }
    }
    getDbPath();
    liveLoadGroup();
  } catch (error) {
    console.error(error);
  }
}

async function makePrintPdf() {
  sku_group = document.getElementById("sku_group").value;
  const printWindow = window.open(`api/printPdf/${sku_group}`, "_blank");
  if (printWindow) {
    printWindow.focus();
  }
}

async function extractData() {
  try {
    sku_group = document.getElementById("sku_group").value;
    const response = await fetch(`/api/getCsvData/${sku_group}`);
    const data = await response.text();
    if (!data.trim()) {
      console.error("no data found");
      return;
    }
    await navigator.clipboard.writeText(data);
    const btn = document.getElementById("extract-btn");
    const originalText = btn.textContent;
    btn.textContent = "✅ Copied!";

    setTimeout(() => {
      btn.textContent = originalText;
    }, 2000);
  } catch (err) {
    console.error("copy failed");
  }
}

window.onload = () => {
  getDbPath();
  loadTursoConfig();
  setupKeyboardNavigation();
  group = document.getElementById("sku_group").value;
  if (!group || group.length === 0) {
    document.getElementById("sku_group").focus();
  } else {
    loadItemsByGroup(group);
    document.getElementById("weight").focus();
  }
};

// ── Turso Sync UI ────────────────────────────────────────────────

async function loadTursoConfig() {
  try {
    const res = await fetch('/api/getTursoConfig');
    const data = await res.json();
    if (data.turso_url) {
      document.getElementById('turso_url').value = data.turso_url;
    }
    if (data.turso_token) {
      document.getElementById('turso_token').value = data.turso_token;
    }
    if (data.configured) {
      setSyncStatus('configured', '☁ Sync enabled');
    } else {
      setSyncStatus('idle', '');
    }
  } catch (e) {
    console.error('loadTursoConfig error:', e);
  }
}

async function saveTursoConfig() {
  const url = document.getElementById('turso_url').value.trim();
  const token = document.getElementById('turso_token').value.trim();
  if (!url || !token) return;  // don't save incomplete config
  try {
    await fetch('/api/setTursoConfig', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turso_url: url, turso_token: token }),
    });
    setSyncStatus('configured', '☁ Sync enabled');
  } catch (e) {
    console.error('saveTursoConfig error:', e);
  }
}

async function refreshMainTableUI() {
  const btn = document.getElementById('refresh-tbl-btn');
  if (btn) {
    btn.textContent = '🔄 Refreshing...';
    btn.style.opacity = '0.7';
  }
  const groupInput = document.getElementById("sku_group");
  const group = groupInput ? groupInput.value.trim().toUpperCase() : "";
  if (group) {
    await refreshTableOnly(group);
  } else {
    // If no group typed in form, load default or prompt
    const tbody = document.getElementById("display-table-body");
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center muted-text" style="padding:1rem;">Type a SKU Group (e.g. LP, G2) in the form to view items.</td></tr>`;
  }
  setTimeout(() => {
    if (btn) {
      btn.textContent = '🔄 Refresh Table';
      btn.style.opacity = '1';
    }
  }, 400);
}

async function refreshTableOnly(sku_group) {
  const groupInput = document.getElementById("sku_group");
  const group = sku_group || (groupInput ? groupInput.value.trim().toUpperCase() : "");
  if (!group) return;
  try {
    const response = await fetch(`/api/getData/${group}`);
    const data = await response.json();
    renderTable(data);
    scrollToEnd();

    // Update title bar count
    const titleEl = document.getElementById('table-title');
    if (titleEl) {
      titleEl.textContent = `📋 Inventory Table — Group ${group} (${data.length} items)`;
    }

    // Auto-update next available item_id if user is NOT currently typing in form fields
    const isFormFocused = formOrder.some(
      (id) => document.activeElement && document.activeElement.id === id
    );
    if (!isFormFocused) {
      setItemId(data);
    }
  } catch (error) {
    console.error("error refreshing table: ", error);
  }
}


let isSyncing = false;

async function syncNow() {
  if (isSyncing) return;
  isSyncing = true;
  const btn = document.getElementById('sync-btn');
  btn.textContent = 'Syncing...';
  btn.style.opacity = '0.6';
  btn.style.pointerEvents = 'none';

  try {
    const res = await fetch('/api/runSync', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      const msg = data && data.message ? data.message : '✕ Sync failed';
      setSyncStatus('error', msg);
    } else {
      setSyncStatus('ok', `↑${data.pushed} ↓${data.pulled}`);
      if (data.pulled > 0 || data.pushed > 0) {
        refreshTableOnly();
      }
    }
  } catch (e) {
    setSyncStatus('error', '✕ Sync failed');
  } finally {
    isSyncing = false;
    btn.textContent = 'Sync';
    btn.style.opacity = '1';
    btn.style.pointerEvents = 'auto';
  }
}

function setSyncStatus(state, text) {
  const el = document.getElementById('sync-status');
  el.textContent = text;
  el.className = 'sync-status sync-status--' + state;
}

let lastSeenPullTime = null;

async function pollSyncStatus() {
  try {
    const res = await fetch('/api/getSyncStatus');
    const data = await res.json();
    if (data.configured && data.last_push) {
      const ts = new Date(data.last_push + 'Z').toLocaleTimeString();
      setSyncStatus('ok', `☁ ${ts}`);
    }
    if (data.last_pull && data.last_pull !== lastSeenPullTime) {
      if (lastSeenPullTime !== null) {
        refreshTableOnly();
      }
      lastSeenPullTime = data.last_pull;
    }
  } catch (e) { /* silent */ }
}

// ________________________ Settings Modal & Etsy Config ________________________

function openSettingsModal() {
  const modal = document.getElementById('settings-modal');
  if (modal) {
    modal.classList.add('active');
    loadEtsyConfig();
    loadTursoConfigUI();
    loadDbPathUI();
  }
}

function closeSettingsModal() {
  const modal = document.getElementById('settings-modal');
  if (modal) {
    modal.classList.remove('active');
  }
}

function closeModalOnOverlay(event) {
  if (event.target && event.target.id === 'settings-modal') {
    closeSettingsModal();
  }
}

async function loadEtsyConfig() {
  try {
    const res = await fetch('/api/etsy/config');
    const data = await res.json();
    if (data.api_key) document.getElementById('etsy_key').value = data.api_key;
    if (data.shared_secret) document.getElementById('etsy_shared_secret').value = data.shared_secret;
    if (data.shop_id) document.getElementById('etsy_shop_id').value = data.shop_id;
  } catch (e) { /* silent */ }
}

async function saveEtsyConfig() {
  const api_key = document.getElementById('etsy_key').value.trim();
  const shared_secret = document.getElementById('etsy_shared_secret').value.trim();
  const shop_id = document.getElementById('etsy_shop_id').value.trim();
  try {
    await fetch('/api/etsy/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key, shared_secret, shop_id })
    });
    alert('Etsy credentials saved successfully!');
  } catch (e) {
    alert('Failed to save Etsy credentials: ' + e);
  }
}

async function connectEtsy() {
  await saveEtsyConfig();
  try {
    const res = await fetch('/api/etsy/auth', { method: 'POST' });
    const data = await res.json();
    if (data.auth_url) {
      window.open(data.auth_url, '_blank');
    } else {
      alert(data.message || 'Error generating Etsy auth URL');
    }
  } catch (e) {
    alert('Etsy auth failed: ' + e);
  }
}

async function loadTursoConfigUI() {
  try {
    const res = await fetch('/api/getTursoConfig');
    const data = await res.json();
    if (data.turso_url) document.getElementById('turso_url').value = data.turso_url;
    if (data.turso_token) document.getElementById('turso_token').value = data.turso_token;
  } catch (e) { /* silent */ }
}

async function saveTursoConfigUI() {
  const turso_url = document.getElementById('turso_url').value.trim();
  const turso_token = document.getElementById('turso_token').value.trim();
  try {
    await fetch('/api/saveTursoConfig', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turso_url, turso_token })
    });
    alert('Turso config saved successfully!');
  } catch (e) {
    alert('Failed to save Turso config: ' + e);
  }
}

async function loadDbPathUI() {
  try {
    const res = await fetch('/api/getDbPath');
    const data = await res.json();
    const dbPath = data.db_Path || data.db_path;
    if (dbPath) document.getElementById('db_path_input').value = dbPath;
  } catch (e) { /* silent */ }
}

async function saveDbPathUI() {
  const db_path = document.getElementById('db_path_input').value.trim();
  try {
    await fetch('/api/setDbPath', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ db_path: db_path, db_Path: db_path })
    });
    alert('Database path updated!');
  } catch (e) {
    alert('Failed to update DB path: ' + e);
  }
}

