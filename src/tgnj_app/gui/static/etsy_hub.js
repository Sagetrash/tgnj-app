// Etsy Operations Hub JavaScript

document.addEventListener('DOMContentLoaded', () => {
  fetchShopStats();
  fetchRecentOrdersLog();
  loadSkuGroupsDropdown();

  const groupSelect = document.getElementById('bulk_group');
  if (groupSelect) {
    groupSelect.addEventListener('change', loadBulkPreview);
  }

  const selectAll = document.getElementById('bulk-select-all');
  if (selectAll) {
    selectAll.addEventListener('change', (e) => toggleSelectAll(e.target.checked));
  }

  const gemName = document.getElementById('bulk_gemstone_name');
  if (gemName) {
    gemName.addEventListener('input', () => {
      updateTitlePreviews();
      updatePublishButtonState();
    });
  }
});

async function loadSkuGroupsDropdown() {
  try {
    const res = await fetch('/api/getSkuGroups');
    const groups = await res.json();
    const select = document.getElementById('bulk_group');
    if (!select) return;

    let html = '<option value="" disabled selected>Select a SKU Group</option>';
    groups.forEach(g => {
      html += `<option value="${g}">${g}</option>`;
    });
    select.innerHTML = html;
  } catch (e) {
    console.log("Error loading SKU groups:", e);
  }
}

async function loadBulkPreview() {
  const group = document.getElementById('bulk_group').value;
  if (!group) return;

  const tbody = document.getElementById('bulk-preview-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading...</td></tr>';
  }

  try {
    const showListed = document.getElementById('bulk-show-listed-cb')?.checked || false;

    const res = await fetch(`/api/getDataByStatus/${showListed ? 'ALL' : 'IN_STOCK'}`);
    const allStock = await res.json();

    const itemsToPublish = allStock.filter(item => {
      if (item.sku_group !== group) return false;
      if (!showListed && (item.etsy_listing_id || item.status === 'LISTED_ETSY')) return false;
      return true;
    });

    const previewSection = document.getElementById('bulk-preview-section');
    const previewTitle = document.getElementById('bulk-preview-title');

    if (itemsToPublish.length === 0) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center">No stones found for this group.</td></tr>';
        if (previewSection) previewSection.style.display = 'block';
        if (previewTitle) previewTitle.textContent = '📋 Preview: 0 stones loaded';
        updateSelectedCount();
        return;
    }

    if (previewSection) previewSection.style.display = 'block';
    if (previewTitle) previewTitle.textContent = `📋 Preview: ${itemsToPublish.length} stones loaded`;

    let html = '';
    itemsToPublish.forEach(item => {
      const formattedId = String(item.sku_id).padStart(3, "0");
      const weight = item.weight || '';
      const shape = item.shape || '';
      const l = item.length || 0;
      const w = item.width || 0;
      const d = item.depth || 0;
      const dims = (l || w || d) ? `${l}x${w}x${d}` : '';
      const sku = `${item.sku_group}-${formattedId}`;
      const escapedItem = encodeURIComponent(JSON.stringify({sku_group: item.sku_group, sku_id: item.sku_id}));
      const isAlreadyListed = Boolean(item.etsy_listing_id || item.status === 'LISTED_ETSY');
      const listingId = item.etsy_listing_id || '';
      const etsyLink = listingId ? `https://www.etsy.com/listing/${listingId}` : '#';

      const checkboxHtml = isAlreadyListed 
        ? `<span class="badge badge-listed" style="font-size:0.75rem;">Listed</span>` 
        : `<input type="checkbox" class="bulk-item-checkbox" onchange="updateSelectedCount()" data-item="${escapedItem}" checked>`;

      const titleCellHtml = isAlreadyListed
        ? `<a href="${etsyLink}" target="_blank" style="color:#a6e3a1; font-weight:600; text-decoration:underline;">🧡 Listed on Etsy (Draft #${listingId}) ↗</a>`
        : `<span class="title-preview"></span>`;

      html += `
        <tr data-weight="${weight}" data-shape="${shape}" data-sku-group="${item.sku_group}" data-sku-id="${item.sku_id}" ${isAlreadyListed ? 'style="opacity:0.7;"' : ''}>
          <td>${checkboxHtml}</td>
          <td><strong>${sku}</strong></td>
          <td>${weight}</td>
          <td>${shape}</td>
          <td>${dims}</td>
          <td id="photo-status-${sku}">⏳</td>
          <td>${titleCellHtml}</td>
        </tr>
      `;
    });
    
    if (tbody) {
      tbody.innerHTML = html;
      updateTitlePreviews();
      updateSelectedCount();

      // Batch check photos via backend
      checkS3PhotosBatch(itemsToPublish);
    }
  } catch (e) {
    console.log("Error loading bulk preview:", e);
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error loading preview</td></tr>';
  }
}

function updateTitlePreviews() {
  const gemNameInput = document.getElementById('bulk_gemstone_name');
  const gemName = gemNameInput ? gemNameInput.value.trim() : '';
  const rows = document.querySelectorAll('#bulk-preview-tbody tr');

  rows.forEach(row => {
    const weight = row.getAttribute('data-weight');
    const shape = row.getAttribute('data-shape');
    const titleCell = row.querySelector('.title-preview');
    if (titleCell) {
      if (gemName) {
        titleCell.textContent = `${weight} Ct.Natural High Quality ${gemName} Loose Gemstone ${shape} Cabochon For Jewelry Making`;
      } else {
        titleCell.textContent = 'Please enter gemstone name';
      }
    }
  });
}

function toggleSelectAll(checked) {
  const checkboxes = document.querySelectorAll('.bulk-item-checkbox');
  checkboxes.forEach(cb => cb.checked = checked);
  updateSelectedCount();
}

function updateSelectedCount() {
  const checkboxes = document.querySelectorAll('.bulk-item-checkbox:checked');
  const countBadge = document.getElementById('bulk-selected-count');
  if (countBadge) {
    countBadge.textContent = checkboxes.length;
  }
  updatePublishButtonState();
}

function updatePublishButtonState() {
  const checkboxes = document.querySelectorAll('.bulk-item-checkbox:checked');
  const gemNameInput = document.getElementById('bulk_gemstone_name');
  const btn = document.getElementById('bulk-push-btn');
  
  if (btn) {
    const gemName = gemNameInput ? gemNameInput.value.trim() : '';
    btn.disabled = checkboxes.length === 0 || gemName === '';
  }
}

async function checkS3PhotosBatch(items) {
  try {
    const payload = items.map(item => ({sku_group: item.sku_group, sku_id: item.sku_id}));
    const res = await fetch('/api/etsy/checkPhotos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: payload })
    });
    if (res.ok) {
      const data = await res.json();
      const results = data.results || {};
      for (const [sku, status] of Object.entries(results)) {
        const cell = document.getElementById(`photo-status-${sku}`);
        if (!cell) continue;
        if (status.a && status.b) {
          cell.textContent = '📷📷';
        } else if (status.a) {
          cell.textContent = '📷⚠️';
        } else {
          cell.textContent = '⚠️⚠️';
        }
      }
    }
  } catch (e) {
    console.log('Error checking photos:', e);
  }
}

async function runBulkPublisher() {
  const checkboxes = document.querySelectorAll('.bulk-item-checkbox:checked');
  if (checkboxes.length === 0) return;

  const gemNameInput = document.getElementById('bulk_gemstone_name');
  const priceInput = document.getElementById('bulk_fixed_price');

  const gemstone_name = gemNameInput ? gemNameInput.value.trim() : '';
  const price = priceInput ? parseFloat(priceInput.value) : 12.99;

  if (!gemstone_name) {
    alert("Gemstone name is required.");
    return;
  }
  
  if (isNaN(price) || price <= 0) {
    alert("Valid price is required.");
    return;
  }

  const items = Array.from(checkboxes).map(cb => {
      const data = JSON.parse(decodeURIComponent(cb.getAttribute('data-item')));
      return { sku_group: data.sku_group, sku_id: data.sku_id };
  });

  if (!confirm(`Bulk publish ${items.length} items to Etsy?`)) return;

  const progressContainer = document.getElementById('bulk-progress-container');
  const progressBar = document.getElementById('bulk-progress-bar');
  const progressText = document.getElementById('bulk-progress-text');
  const logArea = document.getElementById('bulk-log');
  
  if (progressContainer) progressContainer.style.display = 'block';
  if (progressBar) progressBar.style.width = '10%';
  if (progressText) progressText.textContent = 'Starting bulk push...';
  if (logArea) logArea.innerHTML = '';
  
  const btn = document.getElementById('bulk-push-btn');
  if (btn) btn.disabled = true;
  const logContainer = document.getElementById('bulk-log-container');
  if (logContainer) logContainer.style.display = 'block';

  appendLog(`Starting bulk upload for ${items.length} items...`, 'info');

  try {
    const res = await fetch('/api/etsy/bulkPush', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items, gemstone_name, price })
    });
    
    if (res.ok) {
        const data = await res.json();
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = `Done! ${data.success || 0} succeeded, ${data.failed || 0} failed.`;
        
        appendLog(`Bulk upload completed: ${data.success || 0} succeeded, ${data.failed || 0} failed out of ${data.total || 0}.`, 'success');
        
        if (data.results) {
            data.results.forEach(result => {
               if (result.status === 'success') {
                   appendLog(`✅ ${result.sku} → Draft #${result.listing_id} created`, 'success');
               } else if (result.status === 'skipped') {
                   appendLog(`ℹ️ ${result.sku} → Already listed on Etsy (Draft #${result.listing_id || 'exist'})`, 'info');
               } else {
                   appendLog(`❌ ${result.sku} → ${result.error || 'Unknown error'}`, 'error');
               }
            });
        }
    } else {
        const errorData = await res.json().catch(() => ({}));
        appendLog(`Server returned error: ${res.status} ${errorData.error || ''}`, 'error');
        if (progressText) progressText.textContent = 'Error during bulk push.';
    }
  } catch (e) {
    console.log("Error running bulk publisher:", e);
    appendLog(`Network or unexpected error: ${e.message}`, 'error');
    if (progressText) progressText.textContent = 'Error during bulk push.';
  }
  
  fetchShopStats();
  updatePublishButtonState();
}

function appendLog(msg, type) {
  const logArea = document.getElementById('bulk-log');
  if (!logArea) return;
  
  const now = new Date();
  const timeStr = now.toLocaleTimeString();
  
  let color = 'inherit';
  if (type === 'success') color = 'green';
  else if (type === 'error') color = 'red';
  
  const line = document.createElement('div');
  line.style.color = color;
  line.textContent = `[${timeStr}] ${msg}`;
  
  logArea.appendChild(line);
  logArea.scrollTop = logArea.scrollHeight;
}

async function fetchShopStats() {
  try {
    const res = await fetch('/api/etsy/liveStats');
    const data = await res.json();

    const activeElem = document.getElementById('stat-active-count');
    if (activeElem) activeElem.textContent = data.active || 0;
    
    const draftElem = document.getElementById('stat-draft-count');
    if (draftElem) draftElem.textContent = data.draft || 0;

    const badge = document.getElementById('shop-conn-badge');
    if (badge) {
        if (data.connected) {
          badge.textContent = 'Connected (TakshGems Live API)';
          badge.className = 'badge badge-listed';
        } else {
          badge.textContent = 'Disconnected (Requires OAuth)';
          badge.className = 'badge badge-sold';
        }
    }
  } catch (e) {
    console.log("Error fetching stats:", e);
  }
}

async function syncEtsyOrdersHub() {
  alert("Syncing orders with Etsy...");
  try {
    const res = await fetch('/api/etsy/syncOrders', { method: 'POST' });
    const data = await res.json();
    alert(data.message || 'Etsy Order Sync Complete');
    fetchShopStats();
    fetchRecentOrdersLog();
  } catch (e) {
    alert('Sync Etsy Orders failed: ' + e);
  }
}

function reauthEtsyHub() {
  if (typeof connectEtsy === 'function') {
      connectEtsy();
  }
}

async function fetchRecentOrdersLog() {
  try {
    const res = await fetch('/api/getDataByStatus/SOLD');
    const data = await res.json();
    const tbody = document.getElementById('orders-log-tbody');
    if (!tbody) return;

    if (!data || data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted-text text-center">No sold receipts synced yet.</td></tr>`;
      return;
    }

    let html = '';
    data.forEach(item => {
      const formattedId = String(item.sku_id).padStart(3, "0");
      html += `
        <tr>
          <td>#REC-${item.id}</td>
          <td>${item.sold_at || item.updated_at || 'Recent'}</td>
          <td>International / USA</td>
          <td><strong>${item.sku_group}-${formattedId}</strong></td>
          <td>$${(item.sold_price || item.etsy_price || 12.99).toFixed(2)}</td>
          <td><span class="badge badge-sold">SOLD (${item.sold_channel || 'Etsy'})</span></td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (e) {
    console.log("Error loading orders log:", e);
  }
}
