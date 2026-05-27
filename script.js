const HISTORY_LIMIT = 15;

let vitalChart = null;
let analytics24Chart = null;
let kChart = null;
let reportRiskChart = null;
let reportLoaded = false;
let dashboardIntervalId = null;
let isDashboardUpdating = false;

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function escapeHtml(value = "") {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function isCriticalRisk(risk) {
    return typeof risk === "string" && risk.includes("CRITICAL");
}

function destroyCharts() {
    [vitalChart, analytics24Chart, kChart, reportRiskChart].forEach((chart) => {
        if (chart) chart.destroy();
    });
    vitalChart = null;
    analytics24Chart = null;
    kChart = null;
    reportRiskChart = null;
    reportLoaded = false;
}

function stopDashboardRefresh() {
    if (dashboardIntervalId) {
        window.clearInterval(dashboardIntervalId);
        dashboardIntervalId = null;
    }
}

function initChart() {
    const canvas = document.getElementById("vitalChart");
    if (!canvas) return;
    if (vitalChart) vitalChart.destroy();
    vitalChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "HR", borderColor: "#3b82f6", data: [], tension: 0.3, fill: false },
                { label: "SpO2", borderColor: "#06b6d4", data: [], tension: 0.3, fill: false },
                { label: "BP Sys", borderColor: "#ef4444", data: [], borderDash: [5, 5], tension: 0.3, fill: false },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { min: 40, max: 200 } },
            animation: false,
        },
    });
}

function updatePatientInfo(name, id) {
    setText("sidebar-patient-name", name);
    setText("sidebar-patient-id", `Patient ID: ${id}`);
    setText("dashboard-patient-name", name);
    setText("dashboard-patient-id", `ID: ${id}`);
}

function updatePredictionCard(data) {
    const predCard = document.getElementById("prediction-alert-card");
    const predText = document.getElementById("pred-text");
    const predIcon = document.getElementById("pred-icon");
    const predBadge = document.getElementById("pred-badge");
    if (!predCard || !predText || !predIcon || !predBadge) return;

    if (data.prediction === 1) {
        predCard.style.borderColor = "#f59e0b";
        predText.textContent = "Warning: High risk predicted in 30 mins!";
        predText.className = "mt-1 text-center text-sm font-bold italic leading-tight text-orange-600";
        predIcon.textContent = "Warning";
        predBadge.textContent = "FUTURE RISK";
        predBadge.className = "mt-3 rounded-full bg-orange-500 px-4 py-1 text-[10px] font-black text-white";
    } else if (data.prediction === 2) {
        predCard.style.borderColor = "#dc2626";
        predText.textContent = "Immediate emergency detected!";
        predText.className = "mt-1 text-center text-sm font-bold italic leading-tight text-red-600";
        predIcon.textContent = "Alert";
        predBadge.textContent = "CRITICAL NOW";
        predBadge.className = "mt-3 rounded-full bg-red-600 px-4 py-1 text-[10px] font-black text-white animate-pulse";
    } else {
        predCard.style.borderColor = "#10b981";
        predText.textContent = "Trends look normal for next 30 mins.";
        predText.className = "mt-1 text-center text-sm font-bold italic leading-tight text-slate-500";
        predIcon.textContent = "OK";
        predBadge.textContent = "STABLE";
        predBadge.className = "mt-3 rounded-full bg-green-500 px-4 py-1 text-[10px] font-black text-white";
    }
}

function updateRiskCard(data) {
    const card = document.getElementById("ai-status-card");
    const riskText = document.getElementById("risk-level");
    if (!card || !riskText) return;
    if (isCriticalRisk(data.risk) || data.prediction === 2) {
        card.classList.add("animate-critical");
        riskText.textContent = "CRITICAL ALERT";
        riskText.style.color = "#dc2626";
    } else if (data.prediction === 1) {
        card.classList.remove("animate-critical");
        riskText.textContent = "WARNING";
        riskText.style.color = "#d97706";
    } else {
        card.classList.remove("animate-critical");
        riskText.textContent = "STABLE";
        riskText.style.color = "#16a34a";
    }
}

function updateVitalsChart(data) {
    if (!vitalChart) return;
    if (vitalChart.data.labels.length >= HISTORY_LIMIT) {
        vitalChart.data.labels.shift();
        vitalChart.data.datasets.forEach((dataset) => dataset.data.shift());
    }
    vitalChart.data.labels.push(data.timestamp);
    vitalChart.data.datasets[0].data.push(data.hr);
    vitalChart.data.datasets[1].data.push(data.spo2);
    vitalChart.data.datasets[2].data.push(data.bp_sys);
    vitalChart.update("none");
}

function renderHistoryRows(history) {
    const historyBody = document.getElementById("history-body");
    if (!historyBody) return;
    historyBody.innerHTML = history.map((row) => `
        <tr>
            <td class="py-2">${escapeHtml(row.timestamp)}</td>
            <td>${escapeHtml(row.hr)} bpm</td>
            <td>${escapeHtml(row.spo2)}%</td>
            <td>${escapeHtml(row.bp_sys)}/${escapeHtml(row.bp_dia)}</td>
            <td><span class="rounded px-2 py-1 text-[10px] font-bold ${isCriticalRisk(row.risk) ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}">${escapeHtml(row.risk)}</span></td>
        </tr>
    `).join("");
}

function normalizeHistory(history) {
    return history.map((entry) => ({
        timestamp: entry.timestamp || "",
        hr: Number(entry.hr),
        spo2: Number(entry.spo2),
        bp_sys: Number(entry.bp_sys),
        bp_dia: Number(entry.bp_dia),
        risk: entry.risk || "STABLE",
    }));
}

function generateDummyHistory() {
    const history = [];
    const now = Date.now();
    for (let i = 23; i >= 0; i -= 1) {
        const dt = new Date(now - i * 60 * 60 * 1000);
        history.push({
            timestamp: dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            hr: 70 + Math.round(Math.random() * 30),
            spo2: 92 + Math.round(Math.random() * 8),
            bp_sys: 110 + Math.round(Math.random() * 25),
            bp_dia: 70 + Math.round(Math.random() * 15),
            risk: "STABLE",
        });
    }
    return history;
}

async function updateDashboard() {
    if (isDashboardUpdating || !authToken) return;
    isDashboardUpdating = true;
    try {
        const [latest, history] = await Promise.all([
            fetchJson("/vitals/latest"),
            fetchJson("/vitals/history?limit=5"),
        ]);
        updatePredictionCard(latest);
        updateRiskCard(latest);
        setText("hr-val", latest.hr);
        setText("spo2-val", latest.spo2);
        setText("bp-sys", latest.bp_sys);
        setText("bp-dia", latest.bp_dia);
        setText("conf-score", `${latest.conf}%`);
        setText("activity-tag", `Activity: ${latest.activity}`);
        updateVitalsChart(latest);
        renderHistoryRows(history);
        setText("connection-status", "System Online");
    } catch (error) {
        console.error("Dashboard update failed:", error);
        setText("connection-status", "Data Load Failed");
        // Don't throw - allow app to continue with retry on next interval
    } finally {
        isDashboardUpdating = false;
    }
}

function closeLogsModal() {
    const modal = document.getElementById("all-records-modal");
    if (modal) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

function toggleAllRecords() {
    let modal = document.getElementById("all-records-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "all-records-modal";
        modal.className = "fixed inset-0 z-[9999] hidden items-center justify-center bg-black bg-opacity-70 p-4";
        modal.innerHTML = `
            <div class="flex w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-gray-300 bg-white shadow-2xl">
                <div class="flex items-center justify-between bg-blue-900 p-4 text-white">
                    <h3 class="text-lg font-bold uppercase tracking-wider">System Health Logs</h3>
                    <button onclick="closeLogsModal()" class="text-3xl leading-none hover:text-red-400">&times;</button>
                </div>
                <div id="extended-logs" class="h-[400px] overflow-y-auto bg-gray-50 p-6 font-mono text-sm"><p class="text-center italic text-gray-500">Fetching records...</p></div>
                <div class="border-t bg-gray-100 p-3 text-right"><button onclick="closeLogsModal()" class="rounded-lg bg-gray-800 px-6 py-2 text-xs font-bold uppercase text-white hover:bg-black">Close</button></div>
            </div>`;
        document.body.appendChild(modal);
    }
    modal.classList.remove("hidden");
    modal.classList.add("flex");

    fetchJson("/vitals/history?limit=50")
        .then((history) => {
            const logBox = document.getElementById("extended-logs");
            if (!logBox) return;
            logBox.innerHTML = history.length ? history.map((row) => `
                <div class="border-b border-gray-200 py-2 font-mono text-[12px]">
                    <span class="text-blue-600">[${escapeHtml(row.timestamp)}]</span>
                    <span class="text-gray-800">HR: ${escapeHtml(row.hr)} | SpO2: ${escapeHtml(row.spo2)}% | BP: ${escapeHtml(row.bp_sys)}/${escapeHtml(row.bp_dia)}</span>
                    - <span class="${isCriticalRisk(row.risk) ? "font-bold text-red-600" : "text-green-600"}">${escapeHtml(row.risk)}</span>
                </div>`).join("") : "No records found.";
        })
        .catch(() => {
            const logBox = document.getElementById("extended-logs");
            if (logBox) logBox.textContent = "Error loading logs.";
        });
}

function showPage(page, element) {
    document.querySelectorAll(".sidebar-nav-item").forEach((item) => item.classList.remove("is-active"));
    if (element) element.classList.add("is-active");
    document.querySelectorAll(".page-content").forEach((content) => content.classList.add("hidden"));
    document.getElementById(page)?.classList.remove("hidden");
    if (page === "analytics-page") loadAnalytics();
    if (page === "reports-page") {
        loadReport();
        loadReports();
    }
    if (page === "contacts-page") loadContacts();
    if (page === "settings-page") loadSettings();
    if (page !== "reports-page") reportLoaded = false;
}

function loadAnalytics() {
    if (analytics24Chart && kChart) return;
    const render = (history) => {
        const labels = history.map((item) => item.timestamp);
        const hrData = history.map((item) => item.hr);
        const spo2Data = history.map((item) => item.spo2);
        const bpData = history.map((item) => item.bp_sys);
        const analyticsCanvas = document.getElementById("analytics24Chart");
        const kCanvas = document.getElementById("kChart");
        if (!analyticsCanvas || !kCanvas) return;
        analytics24Chart = new Chart(analyticsCanvas.getContext("2d"), {
            type: "line",
            data: { labels, datasets: [
                { label: "Heart Rate (bpm)", data: hrData, borderColor: "#3b82f6", tension: 0.3, fill: false },
                { label: "SpO2 (%)", data: spo2Data, borderColor: "#06b6d4", tension: 0.3, fill: false },
                { label: "BP Sys (mmHg)", data: bpData, borderColor: "#ef4444", tension: 0.3, fill: false },
            ]},
            options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales: { y: { min: 40, max: 200 } } },
        });
        const healthIndex = history.map((item) => ((item.hr / 2) + item.spo2 + item.bp_sys / 3).toFixed(1));
        kChart = new Chart(kCanvas.getContext("2d"), {
            type: "bar",
            data: { labels, datasets: [{ label: "Health Index", data: healthIndex, backgroundColor: "#8b5cf6", borderColor: "#6d28d9", borderWidth: 1 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { callbacks: { label: (ctx) => `Index: ${ctx.parsed.y}` } } }, scales: { y: { beginAtZero: true, suggestedMax: 180 } } },
        });
    };
    fetchJson("/vitals/history?limit=24").then((data) => render(normalizeHistory(data))).catch(() => render(generateDummyHistory()));
}

function loadReport() {
    if (reportLoaded) return;
    const render = (history) => {
        const hrValues = history.map((item) => item.hr);
        const spo2Values = history.map((item) => item.spo2);
        const bpSysValues = history.map((item) => item.bp_sys);
        const bpDiaValues = history.map((item) => item.bp_dia);
        const avg = (arr) => (arr.reduce((sum, value) => sum + value, 0) / (arr.length || 1)).toFixed(1);
        const min = (arr) => Math.min(...arr).toFixed(1);
        const max = (arr) => Math.max(...arr).toFixed(1);
        const riskCount = { STABLE: 0, WARNING: 0, CRITICAL: 0 };
        history.forEach((item) => {
            if (item.risk === "CRITICAL" || item.risk === "CRITICAL_NOW") riskCount.CRITICAL += 1;
            else if (item.risk === "WARNING" || item.risk === "CRITICAL_SOON") riskCount.WARNING += 1;
            else riskCount.STABLE += 1;
        });
        document.getElementById("report-summary-cards").innerHTML = `
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><h4 class="mb-2 text-xs font-bold uppercase text-gray-500">HR</h4><p class="text-2xl font-bold text-blue-600">${avg(hrValues)} bpm</p><p class="text-xs text-gray-500">Min ${min(hrValues)} / Max ${max(hrValues)}</p></div>
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><h4 class="mb-2 text-xs font-bold uppercase text-gray-500">SpO2</h4><p class="text-2xl font-bold text-cyan-600">${avg(spo2Values)}%</p><p class="text-xs text-gray-500">Min ${min(spo2Values)} / Max ${max(spo2Values)}</p></div>
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><h4 class="mb-2 text-xs font-bold uppercase text-gray-500">BP Sys/Dia</h4><p class="text-2xl font-bold text-red-600">${avg(bpSysValues)}/${avg(bpDiaValues)}</p><p class="text-xs text-gray-500">Min ${min(bpSysValues)}/${min(bpDiaValues)} / Max ${max(bpSysValues)}/${max(bpDiaValues)}</p></div>
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><h4 class="mb-2 text-xs font-bold uppercase text-gray-500">Alerts</h4><p class="text-2xl font-bold text-green-600">${riskCount.STABLE}</p><p class="text-xs text-gray-500">W:${riskCount.WARNING} | C:${riskCount.CRITICAL}</p></div>`;
        const riskLabels = ["STABLE", "WARNING", "CRITICAL"];
        const riskValues = [riskCount.STABLE, riskCount.WARNING, riskCount.CRITICAL];
        const riskCanvas = document.getElementById("reportRiskChart");
        if (!riskCanvas) return;
        if (reportRiskChart) {
            reportRiskChart.data.labels = riskLabels;
            reportRiskChart.data.datasets[0].data = riskValues;
            reportRiskChart.update();
        } else {
            reportRiskChart = new Chart(riskCanvas.getContext("2d"), {
                type: "bar",
                data: { labels: riskLabels, datasets: [{ label: "Events", data: riskValues, backgroundColor: ["#10b981", "#f59e0b", "#dc2626"], borderWidth: 1 }] },
                options: { responsive: true, maintainAspectRatio: false, animation: { duration: 1000, easing: "easeInOutQuart" }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }, plugins: { legend: { display: false } } },
            });
        }
        setText("report-last-updated", `Last updated: ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`);
        reportLoaded = true;
    };
    fetchJson("/vitals/history?limit=24").then((data) => render(normalizeHistory(data))).catch(() => render(generateDummyHistory()));
}

function loadReports() {
    fetchJson("/reports").then((reports) => {
        const container = document.getElementById("reports-container");
        if (!container) return;
        container.innerHTML = reports.length ? reports.map((report) => `
            <div class="flex items-center justify-between rounded-lg bg-gray-50 p-3">
                <div><p class="font-medium text-gray-800">${escapeHtml(report.filename)}</p><p class="text-sm text-gray-500">${escapeHtml(report.description || "No description")}</p><p class="text-xs text-gray-400">Uploaded: ${escapeHtml(new Date(report.uploaded_at).toLocaleString())}</p></div>
                <div class="flex space-x-2"><a href="${buildApiUrl(`/reports/${report.id}`)}" target="_blank" class="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">View PDF</a><button onclick="deleteReport(${Number(report.id)})" class="rounded bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700">Delete</button></div>
            </div>`).join("") : '<p class="text-gray-500 text-sm">No reports uploaded yet.</p>';
    }).catch(() => {
        document.getElementById("reports-container").innerHTML = '<p class="text-red-500 text-sm">Error loading reports.</p>';
    });
}

function deleteReport(reportId) {
    if (!confirm("Are you sure you want to delete this report? This action cannot be undone.")) return;
    fetchJson("/reports/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ report_id: reportId }) })
        .then(() => { alert("Report deleted successfully."); loadReports(); })
        .catch((error) => alert(`Error deleting report: ${error.message}`));
}

async function loadContacts() {
    try {
        const contacts = await fetchJson("/contacts");
        const contactsList = document.getElementById("contacts-list");
        if (!contactsList) return;
        contactsList.innerHTML = contacts.length ? contacts.map((contact) => `
            <div class="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div><p class="font-semibold text-gray-800">${escapeHtml(contact.name)}</p><p class="text-sm text-gray-600">${escapeHtml(contact.phone)} | ${escapeHtml(contact.relationship)}</p></div>
                <button onclick="deleteContact(${Number(contact.id)}, '${escapeHtml(contact.name)}')" class="rounded bg-red-500 px-3 py-1 text-sm text-white hover:bg-red-600">Delete</button>
            </div>`).join("") : '<p class="text-gray-500 text-sm italic">No emergency contacts saved yet. Add contacts above to receive SMS alerts.</p>';
    } catch (error) {
        document.getElementById("contacts-list").innerHTML = '<p class="text-red-500 text-sm">Error loading contacts</p>';
    }
}

async function deleteContact(contactId, contactName) {
    if (!confirm(`Are you sure you want to delete ${contactName} from emergency contacts?`)) return;
    try {
        const result = await fetchJson(`/contacts/${contactId}`, { method: "DELETE" });
        alert(result.message);
        loadContacts();
    } catch (error) {
        alert(`Could not delete contact: ${error.message}`);
    }
}

function setupSettingsForms() {
    const alertForm = document.getElementById("alert-settings-form");
    const patientForm = document.getElementById("patient-info-form");
    if (alertForm && !alertForm.dataset.bound) {
        alertForm.dataset.bound = "true";
        alertForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                await fetchJson("/settings/update", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        sms_alerts: document.getElementById("sms-alerts").checked,
                        sound_alerts: document.getElementById("sound-alerts").checked,
                        vibration: document.getElementById("vibration").checked,
                    }),
                });
                alert("Alert settings saved successfully.");
                await loadSettings();
            } catch (error) {
                alert(`Could not save alert settings: ${error.message}`);
            }
        });
    }
    if (patientForm && !patientForm.dataset.bound) {
        patientForm.dataset.bound = "true";
        patientForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const patient_name = document.getElementById("patient-name").value.trim();
            const patient_id = document.getElementById("patient-id").value.trim();
            if (!patient_name || !patient_id) {
                alert("Please fill in both patient name and ID.");
                return;
            }
            try {
                await fetchJson("/settings/update", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ patient_name, patient_id }),
                });
                alert("Patient information saved successfully.");
                await loadSettings();
            } catch (error) {
                alert(`Could not save patient information: ${error.message}`);
            }
        });
    }
}

async function loadSettings() {
    try {
        const settings = await fetchJson("/settings");
        document.getElementById("sms-alerts").checked = Boolean(settings.sms_alerts);
        document.getElementById("sound-alerts").checked = settings.sound_alerts !== false;
        document.getElementById("vibration").checked = settings.vibration !== false;
        document.getElementById("patient-name").value = settings.patient_name || "Patient";
        document.getElementById("patient-id").value = settings.patient_id || "";
        updatePatientInfo(settings.patient_name || "Patient", settings.patient_id || "");
    } catch (error) {
        console.error("Error loading settings:", error);
    }
}

function setupReportUpload() {
    const uploadForm = document.getElementById("report-upload-form");
    if (!uploadForm || uploadForm.dataset.bound) return;
    uploadForm.dataset.bound = "true";
    uploadForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const fileInput = document.getElementById("report-file");
        const descriptionInput = document.getElementById("report-description");
        if (!fileInput?.files?.[0]) {
            alert("Please select a PDF file to upload.");
            return;
        }
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        formData.append("description", descriptionInput.value);
        try {
            const response = await fetch(buildApiUrl("/reports/upload"), { method: "POST", headers: withAuthHeaders(), body: formData });
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.detail || "Upload failed");
            }
            alert("Report uploaded successfully.");
            descriptionInput.value = "";
            fileInput.value = "";
            loadReports();
        } catch (error) {
            alert(`Could not upload report: ${error.message}`);
        }
    });
}

async function bootstrapAuthenticatedApp() {
    const me = await fetchJson("/auth/me");
    updateAuthenticatedUser(me.user);
    updatePatientInfo(me.settings.patient_name, me.settings.patient_id);
    showAppShell();
    destroyCharts();
    initChart();
    setupSettingsForms();
    setupReportUpload();
    stopDashboardRefresh();
    await loadSettings();
    await updateDashboard();
    dashboardIntervalId = window.setInterval(updateDashboard, 5000);
    const defaultTab = document.querySelector('[data-page="dashboard-page"]');
    if (defaultTab) showPage("dashboard-page", defaultTab);
}

window.addEventListener("load", async () => {
    document.getElementById("show-login-tab")?.addEventListener("click", () => setAuthMode("login"));
    document.getElementById("show-register-tab")?.addEventListener("click", () => setAuthMode("register"));
    document.getElementById("show-reset-link")?.addEventListener("click", () => setAuthMode("reset"));
    document.getElementById("show-reset-panel-button")?.addEventListener("click", () => setAuthMode("reset"));
    document.getElementById("login-form")?.addEventListener("submit", handleLogin);
    document.getElementById("register-form")?.addEventListener("submit", handleRegister);
    document.getElementById("reset-form")?.addEventListener("submit", handleResetPassword);
    document.getElementById("logout-button")?.addEventListener("click", () => handleLogout(true));

    const addContactForm = document.getElementById("add-contact-form");
    if (addContactForm && !addContactForm.dataset.bound) {
        addContactForm.dataset.bound = "true";
        addContactForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const result = await fetchJson("/contacts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: document.getElementById("contact-name").value.trim(),
                        phone: document.getElementById("contact-phone").value.trim(),
                        relationship: document.getElementById("contact-relationship").value,
                    }),
                });
                alert(result.message);
                addContactForm.reset();
                loadContacts();
            } catch (error) {
                alert(`Could not add contact: ${error.message}`);
            }
        });
    }

    setAuthMode("login");
    if (authToken) {
        try {
            await bootstrapAuthenticatedApp();
            return;
        } catch (error) {
            await handleLogout(false);
            showAuthMessage("Previous session invalid ho gaya tha. Please login again.");
        }
    }
    showAuthScreen();
});
