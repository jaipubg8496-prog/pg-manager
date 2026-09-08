requireAuth();
renderSidebar("properties");

const params = new URLSearchParams(window.location.search);
const propertyId = params.get("id");

if (!propertyId) {
  window.location.href = "/static/dashboard.html";
}

let rentSearch = "";
let rentStatusFilter = "";
let complaintStatusFilter = "";

// Default the due-date input to the 5th of next month.
(function setDefaultDueDate() {
  const now = new Date();
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 5);
  document.getElementById("due-date-input").value = nextMonth.toISOString().slice(0, 10);
})();

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function statusBadge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

// ---------- Property name + edit ----------

let currentProperty = null;

async function loadPropertyName() {
  currentProperty = await apiFetch(`/api/properties/${propertyId}`);
  document.getElementById("property-name").textContent = currentProperty.name;
}

document.getElementById("edit-property-btn").addEventListener("click", async () => {
  const result = await openModal({
    title: "Edit property",
    fields: [
      { name: "name", label: "Name", value: currentProperty.name, required: true },
      { name: "city", label: "City", value: currentProperty.city || "" },
      { name: "address", label: "Address", value: currentProperty.address || "" },
    ],
    submitLabel: "Save changes",
  });
  if (!result) return;

  try {
    await apiFetch(`/api/properties/${propertyId}`, { method: "PUT", body: JSON.stringify(result) });
    showToast("Property updated");
    loadPropertyName();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------- Rent status dashboard ----------

async function loadRentStatus() {
  const container = document.getElementById("rent-table-container");
  try {
    const qs = new URLSearchParams();
    if (rentSearch) qs.set("search", rentSearch);
    if (rentStatusFilter) qs.set("status", rentStatusFilter);

    const data = await apiFetch(`/api/properties/${propertyId}/rent-status?${qs.toString()}`);

    document.getElementById("stat-pending").textContent = formatCurrency(data.total_pending_amount);
    document.getElementById("stat-vacant").textContent = data.vacant_beds;

    if (data.tenants.length === 0) {
      container.innerHTML = `<div class="empty-state">No tenants match the current search/filter.</div>`;
      return;
    }

    container.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Tenant</th>
            <th>Due date</th>
            <th class="num">Due</th>
            <th class="num">Paid</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${data.tenants.map(row => {
            const c = row.rent_cycle;
            const isSettled = c && c.status === "paid";
            return `
              <tr>
                <td>${escapeHtml(row.tenant_name)}</td>
                <td>${c ? formatDate(c.due_date) : "—"}</td>
                <td class="num">${c ? formatCurrency(c.amount_due) : "—"}</td>
                <td class="num">${c ? formatCurrency(c.amount_paid) : "—"}</td>
                <td>${c ? statusBadge(c.status) : `<span style="color:var(--ink-soft); font-size:0.85rem;">no cycle yet</span>`}</td>
                <td>
                  <div class="row-actions">
                    ${c && !isSettled ? `<button class="small" data-remind="${c.id}">WhatsApp</button>
                    <button class="small brick" data-markpaid="${c.id}" data-due="${c.amount_due}">Mark paid</button>` : ""}
                    <button class="small" data-moveout="${row.tenant_id}">Move out</button>
                    <button class="icon-btn" data-edit-tenant="${row.tenant_id}" title="Edit">${ICONS.edit}</button>
                    <button class="icon-btn danger" data-delete-tenant="${row.tenant_id}" title="Delete">${ICONS.trash}</button>
                  </div>
                </td>
              </tr>`;
          }).join("")}
        </tbody>
      </table>
    `;

    container.querySelectorAll("[data-remind]").forEach(btn => {
      btn.addEventListener("click", () => sendReminder(btn.dataset.remind));
    });
    container.querySelectorAll("[data-markpaid]").forEach(btn => {
      btn.addEventListener("click", () => markPaid(btn.dataset.markpaid, btn.dataset.due));
    });
    container.querySelectorAll("[data-edit-tenant]").forEach(btn => {
      btn.addEventListener("click", () => editTenant(btn.dataset.editTenant));
    });
    container.querySelectorAll("[data-moveout]").forEach(btn => {
      btn.addEventListener("click", () => moveOutTenant(btn.dataset.moveout));
    });
    container.querySelectorAll("[data-delete-tenant]").forEach(btn => {
      btn.addEventListener("click", () => deleteTenant(btn.dataset.deleteTenant));
    });
  } catch (err) {
    container.innerHTML = `<div class="error-msg">${escapeHtml(err.message)}</div>`;
  }
}

async function sendReminder(cycleId) {
  try {
    const data = await apiFetch(`/api/rent-cycles/${cycleId}/reminder-text`);
    window.open(data.whatsapp_link, "_blank");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function markPaid(cycleId, amountDue) {
  const result = await openModal({
    title: "Mark rent as paid",
    fields: [
      { name: "amount_paid", label: "Amount received (Rs.)", type: "number", value: amountDue, required: true },
    ],
    submitLabel: "Confirm payment",
  });
  if (!result) return;

  const amount = Number(result.amount_paid);
  if (Number.isNaN(amount) || amount <= 0) {
    showToast("Enter a valid amount.", true);
    return;
  }

  try {
    await apiFetch(`/api/rent-cycles/${cycleId}/mark-paid`, {
      method: "POST",
      body: JSON.stringify({ amount_paid: amount }),
    });
    showToast("Payment recorded");
    loadRentStatus();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function editTenant(tenantId) {
  const tenant = await apiFetch(`/api/tenants/${tenantId}`);
  const result = await openModal({
    title: "Edit tenant",
    fields: [
      { name: "name", label: "Name", value: tenant.name, required: true },
      { name: "phone", label: "Phone", value: tenant.phone, required: true },
      { name: "monthly_rent", label: "Monthly rent (Rs.)", type: "number", value: tenant.monthly_rent, required: true },
    ],
    submitLabel: "Save changes",
  });
  if (!result) return;
  result.monthly_rent = Number(result.monthly_rent);

  try {
    await apiFetch(`/api/tenants/${tenantId}`, { method: "PUT", body: JSON.stringify(result) });
    showToast("Tenant updated");
    loadRentStatus();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function moveOutTenant(tenantId) {
  const result = await openModal({
    title: "Move tenant out",
    fields: [
      { name: "move_out_date", label: "Move-out date", type: "date", value: new Date().toISOString().slice(0, 10), required: true },
    ],
    submitLabel: "Confirm move-out",
  });
  if (!result) return;

  try {
    await apiFetch(`/api/tenants/${tenantId}/move-out`, { method: "PUT", body: JSON.stringify(result) });
    showToast("Tenant moved out — bed is now vacant");
    loadRentStatus();
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteTenant(tenantId) {
  const ok = await confirmModal(
    "This permanently removes the tenant and their rent/complaint history. Use 'Move out' instead if they're just leaving — delete is for cleaning up mistaken entries.",
    "Delete"
  );
  if (!ok) return;

  try {
    await apiFetch(`/api/tenants/${tenantId}`, { method: "DELETE" });
    showToast("Tenant deleted");
    loadRentStatus();
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("generate-cycles-btn").addEventListener("click", async () => {
  const dueDate = document.getElementById("due-date-input").value;
  if (!dueDate) {
    showToast("Pick a due date first.", true);
    return;
  }
  try {
    await apiFetch(`/api/properties/${propertyId}/rent-cycles/generate?due_date=${dueDate}`, {
      method: "POST",
    });
    showToast("Rent cycles generated");
    loadRentStatus();
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("search-tenants").addEventListener(
  "input",
  debounce((e) => { rentSearch = e.target.value; loadRentStatus(); }, 300)
);

document.getElementById("status-filters").addEventListener("click", (e) => {
  const btn = e.target.closest(".filter-pill");
  if (!btn) return;
  document.querySelectorAll("#status-filters .filter-pill").forEach(c => c.classList.remove("active"));
  btn.classList.add("active");
  rentStatusFilter = btn.dataset.status;
  loadRentStatus();
});

// ---------- Rooms & beds ----------

async function loadRooms() {
  const container = document.getElementById("rooms-container");

  try {
    const rooms = await apiFetch(`/api/properties/${propertyId}/rooms`);

    if (rooms.length === 0) {
      container.innerHTML = `<div class="empty-state">No rooms yet. Add one to get started.</div>`;
      return;
    }

    container.innerHTML = rooms.map(room => `
      <div class="room-block">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong>Room ${escapeHtml(room.room_number)}</strong>
            ${room.room_type ? `<span style="color: var(--ink-soft);"> · ${escapeHtml(room.room_type)}</span>` : ""}
            <span style="color: var(--ink-soft);"> · ${formatCurrency(room.monthly_rent)}/month</span>
          </div>
          <div class="row-actions">
            <button class="small" data-add-bed="${room.id}">+ Bed</button>
            <button class="icon-btn" data-edit-room="${room.id}" title="Edit">${ICONS.edit}</button>
            <button class="icon-btn danger" data-delete-room="${room.id}" title="Delete">${ICONS.trash}</button>
          </div>
        </div>
        <div class="beds">
          ${room.beds.map(b => `
            <span class="bed-chip ${b.status}">
              Bed ${escapeHtml(b.bed_label)} · ${b.status}
              ${b.status === "vacant" ? `<button class="icon-btn danger" style="padding:0 0 0 4px; width:auto; height:auto;" data-delete-bed="${b.id}" title="Remove bed">${ICONS.trash}</button>` : ""}
            </span>
          `).join("")}
        </div>
      </div>
    `).join("");

    container.querySelectorAll("[data-edit-room]").forEach(btn => {
      const room = rooms.find(r => String(r.id) === btn.dataset.editRoom);
      btn.addEventListener("click", () => editRoom(room));
    });
    container.querySelectorAll("[data-delete-room]").forEach(btn => {
      btn.addEventListener("click", () => deleteRoom(btn.dataset.deleteRoom));
    });
    container.querySelectorAll("[data-add-bed]").forEach(btn => {
      btn.addEventListener("click", () => addBed(btn.dataset.addBed));
    });
    container.querySelectorAll("[data-delete-bed]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteBed(btn.dataset.deleteBed);
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="error-msg">${escapeHtml(err.message)}</div>`;
  }
}

async function editRoom(room) {
  const result = await openModal({
    title: "Edit room",
    fields: [
      { name: "room_number", label: "Room number", value: room.room_number, required: true },
      { name: "room_type", label: "Type", value: room.room_type || "" },
      { name: "monthly_rent", label: "Monthly rent (Rs.)", type: "number", value: room.monthly_rent, required: true },
    ],
    submitLabel: "Save changes",
  });
  if (!result) return;
  result.monthly_rent = Number(result.monthly_rent);

  try {
    await apiFetch(`/api/rooms/${room.id}`, { method: "PUT", body: JSON.stringify(result) });
    showToast("Room updated");
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteRoom(roomId) {
  const ok = await confirmModal(
    "This removes the room and all its beds. Rooms with an active tenant can't be deleted — move them out first.",
    "Delete"
  );
  if (!ok) return;

  try {
    await apiFetch(`/api/rooms/${roomId}`, { method: "DELETE" });
    showToast("Room deleted");
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function addBed(roomId) {
  try {
    await apiFetch(`/api/rooms/${roomId}/beds`, { method: "POST" });
    showToast("Bed added");
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteBed(bedId) {
  try {
    await apiFetch(`/api/beds/${bedId}`, { method: "DELETE" });
    showToast("Bed removed");
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("add-room-btn").addEventListener("click", async () => {
  const result = await openModal({
    title: "Add a room",
    fields: [
      { name: "room_number", label: "Room number", value: "", required: true },
      { name: "room_type", label: "Type (e.g. double)", value: "" },
      { name: "monthly_rent", label: "Monthly rent (Rs.)", type: "number", value: "", required: true },
      { name: "num_beds", label: "Number of beds", type: "number", value: "1", required: true },
    ],
    submitLabel: "Add room",
  });
  if (!result) return;

  try {
    await apiFetch(`/api/properties/${propertyId}/rooms`, {
      method: "POST",
      body: JSON.stringify({
        room_number: result.room_number,
        room_type: result.room_type || null,
        monthly_rent: Number(result.monthly_rent),
        num_beds: Number(result.num_beds) || 1,
      }),
    });
    showToast("Room added");
    loadRooms();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------- Add tenant ----------

document.getElementById("add-tenant-btn").addEventListener("click", async () => {
  let vacantBeds = [];
  try {
    const rooms = await apiFetch(`/api/properties/${propertyId}/rooms`);
    rooms.forEach(room => {
      room.beds.filter(b => b.status === "vacant").forEach(b => {
        vacantBeds.push({ value: b.id, label: `Room ${room.room_number} — Bed ${b.bed_label}` });
      });
    });
  } catch (err) {
    showToast(err.message, true);
    return;
  }

  if (vacantBeds.length === 0) {
    showToast("No vacant beds — add a room first.", true);
    return;
  }

  const result = await openModal({
    title: "Add a tenant",
    fields: [
      { name: "bed_id", label: "Vacant bed", type: "select", options: vacantBeds, required: true },
      { name: "name", label: "Name", value: "", required: true },
      { name: "phone", label: "Phone", value: "", required: true },
      { name: "move_in_date", label: "Move-in date", type: "date", value: new Date().toISOString().slice(0, 10), required: true },
      { name: "monthly_rent", label: "Monthly rent (Rs.)", type: "number", value: "", required: true },
    ],
    submitLabel: "Add tenant",
  });
  if (!result) return;

  try {
    await apiFetch(`/api/properties/${propertyId}/tenants`, {
      method: "POST",
      body: JSON.stringify({
        bed_id: Number(result.bed_id),
        name: result.name,
        phone: result.phone,
        move_in_date: result.move_in_date,
        monthly_rent: Number(result.monthly_rent),
      }),
    });
    showToast("Tenant added");
    loadRooms();
    loadRentStatus();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------- Complaints ----------

async function loadComplaints() {
  const container = document.getElementById("complaints-container");
  try {
    const qs = complaintStatusFilter ? `?status=${complaintStatusFilter}` : "";
    const complaints = await apiFetch(`/api/properties/${propertyId}/complaints${qs}`);

    if (complaints.length === 0) {
      container.innerHTML = `<div class="empty-state">No complaints logged.</div>`;
      return;
    }

    const tenants = await apiFetch(`/api/properties/${propertyId}/tenants`);
    const tenantMap = Object.fromEntries(tenants.map(t => [t.id, t.name]));

    container.innerHTML = complaints.map(c => `
      <div class="complaint-item">
        <div class="desc">
          <div class="tenant-tag">${escapeHtml(tenantMap[c.tenant_id] || "Unknown tenant")} · ${formatDate(c.created_at)}</div>
          ${escapeHtml(c.description)}
        </div>
        <div class="actions">
          ${statusBadge(c.status)}
          ${c.status === "open"
            ? `<button class="small" data-resolve="${c.id}">Resolve</button>`
            : `<button class="small" data-reopen="${c.id}">Reopen</button>`}
          <button class="icon-btn danger" data-delete-complaint="${c.id}" title="Delete">${ICONS.trash}</button>
        </div>
      </div>
    `).join("");

    container.querySelectorAll("[data-resolve]").forEach(btn => {
      btn.addEventListener("click", () => updateComplaintStatus(btn.dataset.resolve, "resolved"));
    });
    container.querySelectorAll("[data-reopen]").forEach(btn => {
      btn.addEventListener("click", () => updateComplaintStatus(btn.dataset.reopen, "open"));
    });
    container.querySelectorAll("[data-delete-complaint]").forEach(btn => {
      btn.addEventListener("click", () => deleteComplaint(btn.dataset.deleteComplaint));
    });
  } catch (err) {
    container.innerHTML = `<div class="error-msg">${escapeHtml(err.message)}</div>`;
  }
}

async function updateComplaintStatus(id, status) {
  try {
    await apiFetch(`/api/complaints/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
    showToast(status === "resolved" ? "Marked resolved" : "Reopened");
    loadComplaints();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteComplaint(id) {
  const ok = await confirmModal("This can't be undone.", "Delete");
  if (!ok) return;
  try {
    await apiFetch(`/api/complaints/${id}`, { method: "DELETE" });
    showToast("Complaint deleted");
    loadComplaints();
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("complaint-filters").addEventListener("click", (e) => {
  const btn = e.target.closest(".filter-pill");
  if (!btn) return;
  document.querySelectorAll("#complaint-filters .filter-pill").forEach(c => c.classList.remove("active"));
  btn.classList.add("active");
  complaintStatusFilter = btn.dataset.status;
  loadComplaints();
});

document.getElementById("add-complaint-btn").addEventListener("click", async () => {
  let tenantOptions = [];
  try {
    const tenants = await apiFetch(`/api/properties/${propertyId}/tenants?status=active`);
    tenantOptions = tenants.map(t => ({ value: t.id, label: t.name }));
  } catch (err) {
    showToast(err.message, true);
    return;
  }

  if (tenantOptions.length === 0) {
    showToast("No active tenants to log a complaint against.", true);
    return;
  }

  const result = await openModal({
    title: "Log a complaint",
    fields: [
      { name: "tenant_id", label: "Tenant", type: "select", options: tenantOptions, required: true },
      { name: "description", label: "Complaint", type: "textarea", value: "", required: true },
    ],
    submitLabel: "Log complaint",
  });
  if (!result) return;

  try {
    await apiFetch("/api/complaints", {
      method: "POST",
      body: JSON.stringify({
        tenant_id: Number(result.tenant_id),
        description: result.description,
      }),
    });
    showToast("Complaint logged");
    loadComplaints();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------- Tabs ----------

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- Init ----------

(async function init() {
  const hasAccess = await initBilling();
  if (!hasAccess) {
    document.getElementById("property-name").textContent = "Subscription required";
    return; // billing.js already shows the paywall over the blurred page
  }
  loadPropertyName();
  loadRentStatus();
  loadRooms();
  loadComplaints();
})();
