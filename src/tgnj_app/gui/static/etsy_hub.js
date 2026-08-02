// Etsy Operations Hub JavaScript

document.addEventListener('DOMContentLoaded', () => {
  fetchShopStats();
  fetchRecentOrdersLog();
  loadSkuGroupsDropdown();
});

async function loadSkuGroupsDropdown() {
  try {
    const res = await fetch('/api/getSkuGroups');
    const groups = await res.json();
    const select = document.getElementById('bulk_group');
    if (!select) return;

    let html = '<option value="ALL">ALL SKU GROUPS</option>';
    groups.forEach(g => {
      html += `<option value="${g}">${g}</option>`;
    });
    select.innerHTML = html;
  } catch (e) {
    console.log("Error loading SKU groups:", e);
  }
}

async function fetchShopStats() {
  try {
    const res = await fetch('/api/etsy/liveStats');
    const data = await res.json();

    document.getElementById('stat-active-count').textContent = data.active || 0;
    document.getElementById('stat-draft-count').textContent = data.draft || 0;
    document.getElementById('stat-unlisted-count').textContent = data.unlisted || 0;

    const badge = document.getElementById('shop-conn-badge');
    if (data.connected) {
      badge.textContent = 'Connected (TakshGems Live API)';
      badge.className = 'badge badge-listed';
    } else {
      badge.textContent = 'Disconnected (Requires OAuth)';
      badge.className = 'badge badge-sold';
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

function exportVelaCsvHub() {
  window.location.href = `/api/exportCsv/etsy?status=ALL`;
}

function reauthEtsyHub() {
  connectEtsy();
}

async function fetchRecentOrdersLog() {
  try {
    const res = await fetch('/api/getDataByStatus/SOLD');
    const data = await res.json();
    const tbody = document.getElementById('orders-log-tbody');

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

async function runBulkPublisher() {
  const targetGroup = document.getElementById('bulk_group').value.trim().toUpperCase();
  const fixedPrice = parseFloat(document.getElementById('bulk_fixed_price').value || 12.99);

  if (!confirm(`Bulk publish unlisted items in group '${targetGroup}' to Etsy?`)) return;

  const progressContainer = document.getElementById('bulk-progress-container');
  const progressBar = document.getElementById('bulk-progress-bar');
  const progressText = document.getElementById('bulk-progress-text');

  progressContainer.style.display = 'block';
  progressBar.style.width = '10%';
  progressText.textContent = 'Fetching unlisted items...';

  try {
    const res = await fetch(`/api/getDataByStatus/IN_STOCK`);
    const allStock = await res.json();

    const itemsToPublish = allStock.filter(item => {
      if (targetGroup !== 'ALL' && item.sku_group.toUpperCase() !== targetGroup) return false;
      return !item.etsy_listing_id;
    });

    if (itemsToPublish.length === 0) {
      alert(`No unlisted items found for group '${targetGroup}'.`);
      progressContainer.style.display = 'none';
      return;
    }

    let completed = 0;
    for (let i = 0; i < itemsToPublish.length; i++) {
      const item = itemsToPublish[i];
      const formattedId = String(item.sku_id).padStart(3, "0");
      progressText.textContent = `Publishing ${item.sku_group}-${formattedId} (${i + 1}/${itemsToPublish.length})...`;
      
      try {
        await fetch(`/api/etsy/pushListing/${item.sku_group}/${item.sku_id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ price: fixedPrice })
        });
        completed++;
      } catch (err) {
        console.log(`Failed pushing ${item.sku_group}-${item.sku_id}:`, err);
      }

      const percent = Math.round(((i + 1) / itemsToPublish.length) * 100);
      progressBar.style.width = `${percent}%`;
    }

    progressText.textContent = `Completed! Created ${completed} draft listings with S3 photos.`;
    alert(`Bulk Publish Complete! Successfully published ${completed} items to Etsy.`);
    fetchShopStats();
  } catch (e) {
    alert('Bulk publish error: ' + e);
  }
}
