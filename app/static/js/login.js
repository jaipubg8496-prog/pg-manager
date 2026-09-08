// If already logged in, skip straight to the dashboard.
if (getToken()) {
  window.location.href = "/static/dashboard.html";
}

const tabLogin = document.getElementById("tab-login");
const tabSignup = document.getElementById("tab-signup");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const errorBox = document.getElementById("error-box");

function showError(message) {
  errorBox.textContent = message;
  errorBox.style.display = "block";
}
function hideError() {
  errorBox.style.display = "none";
}

tabLogin.addEventListener("click", () => {
  tabLogin.classList.add("active");
  tabSignup.classList.remove("active");
  loginForm.style.display = "block";
  signupForm.style.display = "none";
  hideError();
});

tabSignup.addEventListener("click", () => {
  tabSignup.classList.add("active");
  tabLogin.classList.remove("active");
  signupForm.style.display = "block";
  loginForm.style.display = "none";
  hideError();
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  // The login endpoint expects OAuth2's standard form encoding, not JSON —
  // "username" is the field name FastAPI's OAuth2PasswordRequestForm expects,
  // even though we're treating it as an email.
  const body = new URLSearchParams();
  body.append("username", document.getElementById("login-email").value);
  body.append("password", document.getElementById("login-password").value);

  try {
    const res = await fetch("/api/auth/login", { method: "POST", body });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    setToken(data.access_token);
    window.location.href = "/static/dashboard.html";
  } catch (err) {
    showError(err.message);
  }
});

signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  const payload = {
    name: document.getElementById("signup-name").value,
    email: document.getElementById("signup-email").value,
    phone: document.getElementById("signup-phone").value,
    password: document.getElementById("signup-password").value,
  };

  try {
    const res = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Signup failed");
    }
    // Auto-login after successful signup for a smoother first-run experience.
    const loginBody = new URLSearchParams();
    loginBody.append("username", payload.email);
    loginBody.append("password", payload.password);
    const loginRes = await fetch("/api/auth/login", { method: "POST", body: loginBody });
    const loginData = await loginRes.json();
    setToken(loginData.access_token);
    window.location.href = "/static/dashboard.html";
  } catch (err) {
    showError(err.message);
  }
});

// ---------- Google Sign-In ----------
// The client ID lives server-side (.env) so this file never hardcodes it.
// If GOOGLE_CLIENT_ID isn't set, the backend reports enabled:false and we
// simply leave the Google button hidden — the email/password form still works.

async function initGoogleSignIn() {
  try {
    const res = await fetch("/api/auth/google-client-id");
    const { google_client_id, enabled } = await res.json();
    if (!enabled) return;

    // The Google script loads with async/defer, so it may not be ready yet —
    // poll briefly instead of checking once and giving up.
    const googleReady = await waitFor(() => typeof google !== "undefined" && google.accounts, 3000);
    if (!googleReady) return;

    document.getElementById("google-signin-container").style.display = "block";

    google.accounts.id.initialize({
      client_id: google_client_id,
      callback: handleGoogleCredential,
    });

    google.accounts.id.renderButton(document.getElementById("google-signin-button"), {
      type: "standard",
      theme: "outline",
      size: "large",
      width: 320,
      text: "continue_with",
    });
  } catch (e) {
    // Google button just stays hidden if this fails — not worth blocking the page over.
  }
}

function waitFor(conditionFn, timeoutMs) {
  return new Promise((resolve) => {
    const start = Date.now();
    (function check() {
      if (conditionFn()) return resolve(true);
      if (Date.now() - start > timeoutMs) return resolve(false);
      setTimeout(check, 100);
    })();
  });
}

async function handleGoogleCredential(response) {
  hideError();
  try {
    const res = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Google sign-in failed");
    }
    const data = await res.json();
    setToken(data.access_token);
    window.location.href = "/static/dashboard.html";
  } catch (err) {
    showError(err.message);
  }
}

initGoogleSignIn();
