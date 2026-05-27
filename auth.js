let currentUser = null;

function showAuthMessage(message, type = "error") {
    const box = document.getElementById("auth-message");
    if (!box) return;
    box.textContent = message;
    box.className = `auth-notice ${type === "success" ? "auth-notice-success" : "auth-notice-error"}`;
}

function clearAuthMessage() {
    const box = document.getElementById("auth-message");
    if (!box) return;
    box.textContent = "";
    box.className = "auth-notice hidden";
}

function setAuthMode(mode) {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const resetForm = document.getElementById("reset-form");
    const loginTab = document.getElementById("show-login-tab");
    const registerTab = document.getElementById("show-register-tab");
    const resetPanel = document.getElementById("auth-reset-panel");
    if (!loginForm || !registerForm || !resetForm || !loginTab || !registerTab || !resetPanel) return;
    const loginActive = mode === "login";
    const registerActive = mode === "register";
    const resetActive = mode === "reset";

    loginForm.classList.toggle("hidden", !loginActive);
    registerForm.classList.toggle("hidden", !registerActive);
    resetForm.classList.toggle("hidden", !resetActive);
    loginTab.classList.toggle("is-active", loginActive);
    registerTab.classList.toggle("is-active", registerActive);
    resetPanel.classList.toggle("hidden", resetActive);
    clearAuthMessage();
}

function showAppShell() {
    document.getElementById("auth-screen")?.classList.add("hidden");
    document.getElementById("app-shell")?.classList.remove("hidden");
}

function showAuthScreen() {
    document.getElementById("app-shell")?.classList.add("hidden");
    document.getElementById("auth-screen")?.classList.remove("hidden");
}

function updateAuthenticatedUser(user) {
    currentUser = user;
    setText("current-user-name", user.full_name);
    setText("current-user-email", user.email);
}

async function handleLogin(event) {
    event.preventDefault();
    clearAuthMessage();
    try {
        const result = await fetchJson("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: document.getElementById("login-email").value.trim(),
                password: document.getElementById("login-password").value,
            }),
        });
        if (!result.token) {
            showAuthMessage("Login failed: No token received. Try again.");
            return;
        }
        storeSession(result.token);
        currentUser = result.user;
        try {
            await bootstrapAuthenticatedApp();
        } catch (bootstrapError) {
            console.error("Bootstrap error:", bootstrapError);
            showAuthMessage(`Login successful but app loading failed: ${bootstrapError.message}`);
            // Still show the app shell even if bootstrap fails
            showAppShell();
        }
    } catch (error) {
        console.error("Login error:", error);
        showAuthMessage(error.message || "Login failed. Please check your email and password.");
    }
}

async function handleRegister(event) {
    event.preventDefault();
    clearAuthMessage();
    try {
        const result = await fetchJson("/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                full_name: document.getElementById("register-name").value.trim(),
                email: document.getElementById("register-email").value.trim(),
                password: document.getElementById("register-password").value,
            }),
        });
        storeSession(result.token);
        currentUser = result.user;
        await bootstrapAuthenticatedApp();
    } catch (error) {
        showAuthMessage(error.message);
    }
}

async function handleResetPassword(event) {
    event.preventDefault();
    clearAuthMessage();

    const email = document.getElementById("reset-email").value.trim();
    const newPassword = document.getElementById("reset-password").value;
    const confirmPassword = document.getElementById("reset-confirm").value;

    if (newPassword !== confirmPassword) {
        showAuthMessage("New password aur confirm password match nahi kar rahe.");
        return;
    }

    try {
        const result = await fetchJson("/auth/reset-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email,
                new_password: newPassword,
            }),
        });
        document.getElementById("reset-form")?.reset();
        setAuthMode("login");
        showAuthMessage(result.message, "success");
    } catch (error) {
        showAuthMessage(error.message || "Password reset failed.");
    }
}

async function handleLogout(callApi = true) {
    stopDashboardRefresh();
    if (callApi && authToken) {
        try {
            await fetchJson("/auth/logout", { method: "POST" });
        } catch (error) {
            // Ignore logout failures.
        }
    }
    clearSession();
    currentUser = null;
    destroyCharts();
    showAuthScreen();
    setAuthMode("login");
}
