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
    console.log("data sent!");
  } catch (error) {
    console.error("error loading items: ", error);
  }
}
function deleteItem(sku_group, sku_id) {
  success = fetch(`/api/deleteItem/${sku_group}/${sku_id}`, {
    method: "DELETE",
  });
  liveLoadGroup();
}

async function renderTable(data) {
  const tbody = document.getElementById("display-table-body");
  tbody.innerHTML = "";
  if (!data || data.length === 0) {
    tbody.innerHTML =
      "<tr><td colspan = '5' style = 'text-align:center;'>No items found in this group.</td></tr>";
    return;
  }
  data.forEach((item) => {
    const row = document.createElement("tr");

    const formattedId = String(item.sku_id).padStart(3, "0");

    row.innerHTML = `
    <td>${item.sku_group}-${formattedId}</td>
    <td>${item.shape}</td>
    <td>${item.weight.toFixed(2)}</td>
    <td>${item.length}</td>
    <td>${item.width}</td>
    <td>${item.depth}</td>
    <td><button onclick="deleteItem('${item.sku_group}',${item.sku_id})">😻</button></td>
    `;
    tbody.appendChild(row);
  });
}

let debounceTimer;

function liveLoadGroup() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    const input = document.getElementById("sku_group");
    const groupCode = input.value.trim().toUpperCase();

    if (groupCode.length > 0) {
      await loadItemsByGroup(groupCode);
    } else {
      document.getElementById("display-table-body").innerHTML = "";
    }
  }, 300);
}

async function handleFormSubmit() {
  console.log("pressed submit");
  document.getElementById("weight").focus();
  const payload = {
    sku_group: document.getElementById("sku_group").value,
    sku_id: document.getElementById("item_id").value,
    shape: document.getElementById("shape").value,
    weight: document.getElementById("weight").value,
    length: document.getElementById("length").value,
    width: document.getElementById("width").value,
    depth: document.getElementById("depth").value,
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

window.onload = () => {
  setupKeyboardNavigation();
  group = document.getElementById("sku_group").value;
  document.getElementById("sku_group").focus();
  loadItemsByGroup(group);
};
