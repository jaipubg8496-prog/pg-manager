// Small shared helper used by every page. Keeps token handling and API
// calls in one place so we're not repeating fetch boilerplate everywhere.

const API_BASE = ""; // same origin — FastAPI serves both the API and these static files

// Catch anything that would otherwise fail completely silently — a button
// that "does nothing" when clicked is almost always one of these two cases
// with no visible feedback. Surfacing them as a toast makes bugs like that
// diagnosable from a screenshot instead of needing DevTools every time.
window.addEventListener("error", (e) => {
  if (typeof showToast === "function") {
    showToast("Something went wrong: " + e.message, true);
  }
});
window.addEventListener("unhandledrejection", (e) => {
  if (typeof showToast === "function") {
    const msg = e.reason && e.reason.message ? e.reason.message : String(e.reason);
    showToast("Something went wrong: " + msg, true);
  }
});

function getToken() {
  return localStorage.getItem("pg_token");
}

function setToken(token) {
  localStorage.setItem("pg_token", token);
}

function clearToken() {
  localStorage.removeItem("pg_token");
}

function logout() {
  clearToken();
  window.location.href = "/static/login.html";
}

// Redirect to login if there's no token. Call this at the top of every
// protected page's script.
function requireAuth() {
  if (!getToken()) {
    window.location.href = "/static/login.html";
  }
}

/**
 * Wrapper around fetch() that attaches the bearer token and handles
 * a 401 (expired/invalid token) by bouncing back to login.
 */
async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  headers["Authorization"] = `Bearer ${getToken()}`;
  if (options.body && !(options.body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(API_BASE + path, { ...options, headers });

  if (response.status === 401) {
    clearToken();
    window.location.href = "/static/login.html";
    throw new Error("Not authenticated");
  }

  if (response.status === 402) {
    // Trial/subscription lapsed. The backend is the source of truth here —
    // this just makes sure the UI reflects it even if the page-load check
    // in initBilling() somehow missed it (e.g. it expired mid-session).
    const body = await response.json().catch(() => ({}));
    showPaywall();
    throw new Error(body.detail || "Subscription required");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }

  if (response.status === 204) return null;
  return response.json();
}

function formatCurrency(amount) {
  return "Rs. " + Number(amount).toLocaleString("en-IN");
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

// ---------- Icons (inline SVG, kept minimal — no external icon library needed) ----------

const ICONS = {
  edit: `<svg viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>`,
  search: `<svg viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
  logout: `<svg viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>`,
};

// ---------- Toast ----------

function showToast(message, isError = false) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const toast = document.createElement("div");
  toast.className = "toast" + (isError ? " error" : "");
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

// ---------- Debounce (for live search inputs) ----------

function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Opens a small centered modal built from a field spec and resolves with the
 * submitted values, or null if the person cancels. Used everywhere we'd
 * otherwise reach for a plain browser prompt() — feels far more like a real
 * product than a JS confirm dialog.
 *
 * fields: [{ name, label, type: 'text'|'number'|'date'|'textarea', value, required }]
 */
function openModal({ title, fields, submitLabel = "Save" }) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const fieldsHtml = fields.map(f => {
      const val = f.value ?? "";
      if (f.type === "textarea") {
        return `<label for="modal-${f.name}">${f.label}</label>
          <textarea id="modal-${f.name}" rows="3" ${f.required ? "required" : ""}>${val}</textarea>`;
      }
      if (f.type === "select") {
        const opts = (f.options || []).map(o =>
          `<option value="${o.value}" ${String(o.value) === String(val) ? "selected" : ""}>${o.label}</option>`
        ).join("");
        return `<label for="modal-${f.name}">${f.label}</label>
          <select id="modal-${f.name}" ${f.required ? "required" : ""}>${opts}</select>`;
      }
      return `<label for="modal-${f.name}">${f.label}</label>
        <input type="${f.type || 'text'}" id="modal-${f.name}" value="${val}" ${f.required ? "required" : ""}>`;
    }).join("");

    overlay.innerHTML = `
      <div class="modal-box">
        <h2>${title}</h2>
        <form id="modal-form">
          ${fieldsHtml}
          <div class="modal-actions">
            <button type="button" class="ghost" id="modal-cancel">Cancel</button>
            <button type="submit" class="primary" style="margin-top:0;">${submitLabel}</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(overlay);

    const close = (result) => {
      overlay.remove();
      resolve(result);
    };

    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(null); });
    overlay.querySelector("#modal-cancel").addEventListener("click", () => close(null));
    overlay.querySelector("#modal-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const result = {};
      fields.forEach(f => {
        result[f.name] = document.getElementById(`modal-${f.name}`).value;
      });
      close(result);
    });

    overlay.querySelector("input, textarea")?.focus();
  });
}

/** Simple styled confirmation, replacing browser confirm() for a consistent look. */
function confirmModal(message, confirmLabel = "Delete") {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-box" style="max-width: 360px;">
        <h2>Are you sure?</h2>
        <p style="color: var(--ink-soft); font-size: 0.92rem;">${message}</p>
        <div class="modal-actions">
          <button type="button" class="ghost" id="confirm-cancel">Cancel</button>
          <button type="button" class="primary" id="confirm-ok" style="margin-top:0; background: var(--overdue);">${confirmLabel}</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    const close = (result) => { overlay.remove(); resolve(result); };
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(false); });
    overlay.querySelector("#confirm-cancel").addEventListener("click", () => close(false));
    overlay.querySelector("#confirm-ok").addEventListener("click", () => close(true));
  });
}

/**
 * Renders the shared sidebar into an element with id="sidebar-root".
 * `active` is one of: "properties" (extend this list as you add pages).
 */
async function renderSidebar(active) {
  const root = document.getElementById("sidebar-root");
  if (!root) return;

  let owner = null;
  try {
    owner = await apiFetch("/api/auth/me");
  } catch (e) {
    return; // requireAuth() already handles the redirect on 401
  }

  root.innerHTML = `
    <div class="brand">PG Manager</div>
    <nav>
      <a href="/static/dashboard.html" class="${active === 'properties' ? 'active' : ''}">Properties</a>
    </nav>
    <div class="owner-info">
      Signed in as<br><strong>${owner.name}</strong>
      <div style="display:flex; gap:14px; margin-top: 8px;">
        <button id="edit-profile-btn">Edit profile</button>
        <button id="logout-btn">${ICONS.logout} Log out</button>
      </div>
    </div>
  `;
  document.getElementById("logout-btn").addEventListener("click", logout);
  document.getElementById("edit-profile-btn").addEventListener("click", () => editProfile(owner));
}

async function editProfile(owner) {
  const result = await openModal({
    title: "Edit profile",
    fields: [
      { name: "name", label: "Name", value: owner.name, required: true },
      { name: "phone", label: "Phone", value: owner.phone, required: true },
    ],
    submitLabel: "Save changes",
  });
  if (!result) return;

  try {
    await apiFetch("/api/auth/me", { method: "PUT", body: JSON.stringify(result) });
    showToast("Profile updated");
    // Re-render the sidebar so the new name shows immediately.
    const active = document.querySelector(".sidebar nav a.active") ? "properties" : "";
    renderSidebar(active);
  } catch (err) {
    showToast(err.message, true);
  }
}

// ================= Billing: trial banner + paywall + Razorpay checkout =================
//
// The backend (require_active_subscription) is the real gate — every data
// endpoint returns 402 once the trial/subscription lapses. This code just
// makes the UI reflect that: a slim banner while on trial, and a blurred
// lockout with a "Subscribe" card once access is actually cut off.

let _cachedSubStatus = null;

/**
 * Call this once, right after requireAuth(), on every protected page —
 * before loading any page data. Returns true if the owner still has access,
 * so the calling page knows whether it's worth loading data at all.
 */
async function initBilling() {
  try {
    const sub = await apiFetch("/api/billing/status");
    _cachedSubStatus = sub;

    if (!sub.is_active) {
      showPaywall(sub);
      return false;
    }

    if (sub.status === "trial") {
      showTrialBanner(sub);
    }
    return true;
  } catch (e) {
    // If the status check itself fails for some other reason, don't block
    // the whole page on it — just skip the banner/paywall for this load.
    return true;
  }
}

function showTrialBanner(sub) {
  document.querySelectorAll(".trial-banner").forEach(el => el.remove());
  const main = document.querySelector(".main");
  if (!main) return;

  const banner = document.createElement("div");
  banner.className = "trial-banner";
  banner.innerHTML = `
    <span>${sub.days_left} day${sub.days_left === 1 ? "" : "s"} left in your free trial.</span>
    <button id="trial-subscribe-btn" class="small brick">Subscribe — Rs. ${sub.price_rupees}/month</button>
  `;
  main.prepend(banner);
  document.getElementById("trial-subscribe-btn").addEventListener("click", () => startCheckout());
}

function showPaywall(sub) {
  document.querySelectorAll(".paywall-overlay").forEach(el => el.remove());
  document.querySelector(".main")?.classList.add("locked-blur");
  document.querySelector(".trial-banner")?.remove();

  const price = sub?.price_rupees ?? 499;

  const overlay = document.createElement("div");
  overlay.className = "paywall-overlay";
  overlay.innerHTML = `
    <div class="paywall-card">
      <h2>Your free trial has ended</h2>
      <p>Subscribe to keep tracking rent, tenants, and vacancies for your properties.</p>
      <div class="paywall-price">Rs. ${price}<span>/month</span></div>
      <button id="paywall-subscribe-btn" class="primary" style="width:auto; padding: 12px 28px;">Subscribe now</button>
      <button id="paywall-logout-btn" class="ghost" style="margin-top:14px;">Log out</button>
    </div>
  `;
  document.body.appendChild(overlay);
  document.getElementById("paywall-subscribe-btn").addEventListener("click", () => startCheckout());
  document.getElementById("paywall-logout-btn").addEventListener("click", logout);
}

function clearPaywall() {
  document.querySelectorAll(".paywall-overlay").forEach(el => el.remove());
  document.querySelector(".main")?.classList.remove("locked-blur");
  document.querySelector(".trial-banner")?.remove();
}

async function startCheckout() {
  if (typeof Razorpay === "undefined") {
    showToast("Payment couldn't load. Check your internet connection and try again.", true);
    return;
  }

  let order;
  try {
    order = await apiFetch("/api/billing/create-order", { method: "POST" });
  } catch (err) {
    showToast(err.message, true);
    return;
  }

  const owner = await apiFetch("/api/auth/me").catch(() => null);

  const razorpay = new Razorpay({
    key: order.key_id,
    order_id: order.order_id,
    amount: order.amount_paise,
    currency: order.currency,
    name: "PG Manager",
    description: "Monthly subscription",
    prefill: owner ? { name: owner.name, email: owner.email, contact: owner.phone } : {},
    theme: { color: "#7A2E2E" },
    // Restrict checkout to UPI only, and prefer the "intent" flow — this is
    // what opens an installed app (PhonePe, GPay, Paytm) directly to approve
    // the payment, rather than showing a card/netbanking form. "collect" is
    // kept too as a fallback for desktop, where it sends a payment request
    // the person approves inside their UPI app instead of an app redirect.
    method: {
      upi: true,
      card: false,
      netbanking: false,
      wallet: false,
      emi: false,
      paylater: false,
    },
    handler: async function (response) {
      try {
        await apiFetch("/api/billing/verify", {
          method: "POST",
          body: JSON.stringify({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          }),
        });
        showToast("Subscription activated — thank you!");
        clearPaywall();
        window.location.reload();
      } catch (err) {
        showToast(err.message, true);
      }
    },
    modal: {
      ondismiss: function () {
        showToast("Payment cancelled.", true);
      },
    },
  });

  razorpay.on("payment.failed", function () {
    showToast("Payment failed. No charge was applied — try again.", true);
  });

  razorpay.open();
}
