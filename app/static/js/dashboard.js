requireAuth();
renderSidebar("properties");

const container = document.getElementById("properties-container");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function loadProperties(search = "") {
  try {
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    const properties = await apiFetch(`/api/properties${qs}`);

    if (properties.length === 0) {
      container.innerHTML = search
        ? `<div class="empty-state">No properties match "${escapeHtml(search)}".</div>`
        : `<div class="empty-state">No properties yet. Add your first one below — takes ten seconds.</div>`;
      return;
    }

    container.innerHTML = `<div class="property-grid">${properties.map(p => `
      <div class="property-card">
        <div data-open="${p.id}" style="cursor:pointer;">
          <h3>${escapeHtml(p.name)}</h3>
          <div class="city">${escapeHtml(p.city || "")}${p.address ? " · " + escapeHtml(p.address) : ""}</div>
        </div>
        <div class="card-actions">
          <button class="icon-btn" data-edit-prop="${p.id}" title="Edit">${ICONS.edit}</button>
          <button class="icon-btn danger" data-delete-prop="${p.id}" title="Delete">${ICONS.trash}</button>
        </div>
      </div>
    `).join("")}</div>`;

    container.querySelectorAll("[data-open]").forEach(el => {
      el.addEventListener("click", () => {
        window.location.href = `/static/property.html?id=${el.dataset.open}`;
      });
    });

    container.querySelectorAll("[data-edit-prop]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        editProperty(properties.find(p => String(p.id) === btn.dataset.editProp));
      });
    });

    container.querySelectorAll("[data-delete-prop]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteProperty(btn.dataset.deleteProp);
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="error-msg">${escapeHtml(err.message)}</div>`;
  }
}

async function editProperty(current) {
  const result = await openModal({
    title: "Edit property",
    fields: [
      { name: "name", label: "Name", value: current.name, required: true },
      { name: "city", label: "City", value: current.city || "" },
      { name: "address", label: "Address", value: current.address || "" },
    ],
    submitLabel: "Save changes",
  });
  if (!result) return;

  try {
    await apiFetch(`/api/properties/${current.id}`, { method: "PUT", body: JSON.stringify(result) });
    showToast("Property updated");
    loadProperties(document.getElementById("search-properties").value);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteProperty(id) {
  const ok = await confirmModal(
    "This permanently deletes the property along with all its rooms, tenants, and rent history. This can't be undone.",
    "Delete"
  );
  if (!ok) return;

  try {
    await apiFetch(`/api/properties/${id}`, { method: "DELETE" });
    showToast("Property deleted");
    loadProperties(document.getElementById("search-properties").value);
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("search-properties").addEventListener(
  "input",
  debounce((e) => loadProperties(e.target.value), 300)
);

document.getElementById("add-property-btn").addEventListener("click", async () => {
  const result = await openModal({
    title: "Add a property",
    fields: [
      { name: "name", label: "Name", value: "", required: true },
      { name: "city", label: "City", value: "" },
      { name: "address", label: "Address", value: "" },
    ],
    submitLabel: "Add property",
  });
  if (!result) return;

  try {
    await apiFetch("/api/properties", {
      method: "POST",
      body: JSON.stringify({
        name: result.name,
        city: result.city || null,
        address: result.address || null,
      }),
    });
    showToast("Property added");
    loadProperties();
  } catch (err) {
    showToast(err.message, true);
  }
});

(async function init() {
  const hasAccess = await initBilling();
  if (hasAccess) loadProperties();
})();
