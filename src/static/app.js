/**
 * BharatApex AI | Conversational banking terminal front-end.
 * Login (one customer per session), persistent chat history,
 * Account Overview, INR/USD/Dual display and dark/bright theme.
 */

let currentCustomerId = null;
let currentCustomerData = null;
let currentConversationId = null;
let conversations = [];
let isBenchmarkMode = false;
let isSending = false;
let currencyMode = "INR"; // "INR", "USD", or "DUAL"

const FX_RATE = 94.11;

const quickPromptsByCustomer = {
  "CUST-IN-101": [
    { label: "SWIFT wire on hold?", text: "Why is my $5,000 SWIFT wire from Silicon Valley Bank on hold?" },
    { label: "My balances", text: "What is my live account balance across NRE checking and USD reserve?" },
    { label: "Convert $1,200", text: "Convert $1,200 USD to INR at today's interbank rate" },
    { label: "IFSC & UPI ID", text: "What is my IFSC code and linked UPI ID?" }
  ],
  "CUST-IN-102": [
    { label: "Weekend settlement", text: "Where is my weekend Soundbox & QR collection of ₹3,85,000? I need it for Monday dispatches." },
    { label: "NACH fee waiver", text: "Can you waive my ₹350 NACH mandate return fee as a courtesy?" },
    { label: "Block my card", text: "Block my RuPay business card immediately, I left it at my Begum Bazaar shop." },
    { label: "FD rates", text: "What are the latest 3-year Fixed Deposit interest rates for MSME?" }
  ],
  "CUST-IN-103": [
    { label: "AMC charge", text: "Why was ₹250 debited for card maintenance? Can you reverse it?" },
    { label: "Dispute a charge", text: "I did not authorize the ₹899 international cloud charge, please refund me." },
    { label: "Unblock card", text: "Please unblock my RuPay card right now." },
    { label: "UPI limits", text: "Can I transfer money via UPI to my brother? What are the limits?" }
  ]
};

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  await bootstrapSession();
});

/* ==========================================================================
   API helper: any 401 sends the user back to the login screen
   ========================================================================== */

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    showLogin();
    throw new Error("unauthenticated");
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ==========================================================================
   Login / logout (one customer per login; log out to switch)
   ========================================================================== */

function showLogin() {
  currentCustomerId = null;
  currentCustomerData = null;
  currentConversationId = null;
  document.getElementById("login-overlay")?.classList.remove("hidden");
  const pw = document.getElementById("login-password");
  if (pw) pw.value = "";
  document.getElementById("login-username")?.focus();
}

function hideLogin() {
  document.getElementById("login-overlay")?.classList.add("hidden");
}

async function bootstrapSession() {
  try {
    const me = await api("/api/auth/me");
    await enterApp(me);
  } catch (_) {
    showLogin();
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");
  errEl.classList.add("hidden");
  btn.disabled = true;
  btn.textContent = "Signing in...";
  try {
    const me = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("login-username").value,
        password: document.getElementById("login-password").value
      })
    });
    document.getElementById("login-form").reset();
    await enterApp(me);
  } catch (err) {
    errEl.textContent = err.message || "Sign-in failed";
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
}

async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* ignore */ }
  document.getElementById("messages-container").innerHTML = "";
  document.getElementById("history-list").innerHTML = "";
  showLogin();
}

async function enterApp(me) {
  currentCustomerId = me.customer_id;
  hideLogin();
  document.getElementById("header-user-name").textContent = me.name;
  renderQuickPrompts(me.customer_id);
  await refreshOverview();
  await loadConversations(true);
}

/* ==========================================================================
   Account Overview
   ========================================================================== */

async function refreshOverview() {
  try {
    const data = await api("/api/overview");
    currentCustomerData = data;
    renderCustomerHeader(data.profile);
    renderLedger(data.profile, data.transactions);
    renderStatCards(data.profile, data.transactions);
  } catch (err) {
    if (err.message !== "unauthenticated") console.error("Overview error:", err);
  }
}

function renderCustomerHeader(profile) {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set("customer-name-display", profile.name);
  set("customer-tier-display", profile.tier);
  set("customer-city-display", profile.city || "Hyderabad");
  set("customer-upi-display", profile.upi_id || "VPA Linked");
  set("customer-avatar", profile.name.split(" ").map(n => n[0]).join(""));
}

/* ==========================================================================
   Theme Management: Institutional Corporate Dark vs. Executive Bright
   ========================================================================== */

function initTheme() {
  const savedTheme = localStorage.getItem("apex_theme") || "dark";
  const body = document.body;
  const icon = document.getElementById("theme-icon");
  const label = document.getElementById("theme-label");

  if (savedTheme === "light") {
    body.classList.add("light-theme");
    if (icon) {
      icon.className = "fa-solid fa-moon";
    }
    if (label) {
      label.textContent = "Dark";
    }
  } else {
    body.classList.remove("light-theme");
    if (icon) {
      icon.className = "fa-solid fa-sun";
    }
    if (label) {
      label.textContent = "Bright";
    }
  }
}

function toggleTheme() {
  const body = document.body;
  const isLight = body.classList.toggle("light-theme");
  const icon = document.getElementById("theme-icon");
  const label = document.getElementById("theme-label");

  if (isLight) {
    localStorage.setItem("apex_theme", "light");
    if (icon) icon.className = "fa-solid fa-moon";
    if (label) label.textContent = "Dark";
  } else {
    localStorage.setItem("apex_theme", "dark");
    if (icon) icon.className = "fa-solid fa-sun";
    if (label) label.textContent = "Bright";
  }
}

/* ==========================================================================
   Valuation Currency Switcher (INR / USD / Dual)
   ========================================================================== */

function setCurrencyMode(mode) {
  currencyMode = mode;
  document.querySelectorAll("[id^='curr-']").forEach(btn => {
    btn.className = "curr-chip";
  });
  const activeBtn = document.getElementById(`curr-${mode.toLowerCase()}`);
  if (activeBtn) {
    activeBtn.className = "curr-chip curr-chip-active";
  }
  if (currentCustomerData) {
    renderLedger(currentCustomerData.profile, currentCustomerData.transactions);
    renderStatCards(currentCustomerData.profile, currentCustomerData.transactions);
  }
}

function formatCurrency(amountInr, currencyOriginal = "INR") {
  const inrFormatted = "₹" + amountInr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const usdVal = amountInr / FX_RATE;
  const usdFormatted = "$" + usdVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  if (currencyMode === "USD") return usdFormatted;
  if (currencyMode === "DUAL") return `${inrFormatted} [${usdFormatted}]`;
  return inrFormatted;
}

/* ==========================================================================
   Speech Recognition
   ========================================================================== */

function startMicInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition is not supported in this browser. Please use keyboard input.");
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = "en-IN";
  recognition.start();
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    document.getElementById("message-input").value = transcript;
    sendMessage(transcript);
  };
}

/* ---- Small formatting helpers for the redesigned widgets ---- */

function maskId(val) {
  const s = String(val || "");
  return s.length > 6 ? "•••• " + s.slice(-4) : s;
}

function statusPillClass(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("hold") || s.includes("pending") || s.includes("progress")) return "pill pill-warn";
  if (s.includes("fail") || s.includes("revers") || s.includes("bounce")) return "pill pill-neg";
  return "pill pill-pos";
}

function renderLedger(profile, transactions) {
  const accountContainer = document.getElementById("account-cards-container");
  if (!accountContainer) return;
  accountContainer.innerHTML = "";

  (profile.accounts || []).forEach(acc => {
    const card = document.createElement("div");
    card.className = "wallet-tile";

    const balInr = acc.balance_inr !== undefined ? acc.balance_inr : acc.balance;
    const formattedBal = formatCurrency(balInr, acc.currency);

    const holdBadge = acc.hold_amount > 0
      ? `<span class="hold-badge">Under Hold: ${formatCurrency(acc.hold_amount)}</span>`
      : "";

    card.innerHTML = `
      <div class="wt-left">
        <div class="wt-type">${acc.type}</div>
        <div class="wt-meta mono">${maskId(acc.account_id)} • ${acc.currency}</div>
      </div>
      <div class="wt-right">
        <div class="wt-bal mono">${formattedBal}</div>
        ${holdBadge}
      </div>`;
    accountContainer.appendChild(card);
  });

  // Cards
  const cardsContainer = document.getElementById("registered-cards-container");
  if (cardsContainer) {
    cardsContainer.innerHTML = "";
    (profile.cards || []).forEach(c => {
      const isFrozen = c.status.toLowerCase().includes("frozen");
      const statusClass = isFrozen ? "pill-neg" : "pill-pos";

      const div = document.createElement("div");
      div.className = "regcard";
      div.innerHTML = `
        <div class="rc-left">
          <i class="fa-solid fa-credit-card rc-ico"></i>
          <div>
            <div class="rc-num mono">${c.masked_number}</div>
            <div class="rc-net">${c.network || 'RuPay'}</div>
          </div>
        </div>
        <span class="pill ${statusClass}">${c.status}</span>`;
      cardsContainer.appendChild(div);
    });
  }

  // Transactions (Recent Activities table)
  const txContainer = document.getElementById("transactions-container");
  if (txContainer) {
    txContainer.innerHTML = "";
    (transactions || []).forEach(t => {
      const div = document.createElement("div");
      div.className = "tx-row";

      const amtInr = t.amount_inr !== undefined ? t.amount_inr : t.amount;
      const isCredit = amtInr > 0;
      const prefix = isCredit ? "+" : "";

      div.innerHTML = `
        <div class="tx-main">
          <span class="tx-ico">${(t.description || "T").trim().charAt(0).toUpperCase()}</span>
          <div class="tx-info">
            <div class="tx-desc">${t.description}</div>
            <div class="tx-meta mono">${t.date.slice(0, 10)} • ${t.payment_mode || 'UPI'} • ${t.utr_ref || t.status}</div>
          </div>
        </div>
        <div class="tx-side">
          <div class="tx-amt mono ${isCredit ? "tx-credit" : ""}">${prefix}${formatCurrency(Math.abs(amtInr))}</div>
          <span class="pill ${statusPillClass(t.status)}">${t.status}</span>
        </div>`;
      txContainer.appendChild(div);
    });
  }
}

/* ==========================================================================
   Stat cards + Cash Flow chart (derived from the same /api/overview data)
   ========================================================================== */

function renderStatCards(profile, transactions) {
  if (!profile) return;
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const accounts = profile.accounts || [];
  const balOf = acc => (acc.balance_inr !== undefined ? acc.balance_inr : (acc.balance || 0));
  const total = accounts.reduce((s, a) => s + balOf(a), 0);

  // Hero card: masked primary account + total relationship balance
  const primary = accounts[0];
  if (primary) set("stat-balance-account", maskId(primary.account_id));
  set("stat-balance-value", formatCurrency(total));

  // Savings / deposit card (first INR account)
  const savings = accounts.find(a => (a.currency || "INR") === "INR") || primary;
  if (savings) {
    set("stat-savings-name", `${savings.type} • ${maskId(savings.account_id)}`);
    set("stat-savings-value", formatCurrency(balOf(savings)));
  }

  // Forex wallet card (USD holdings)
  const forex = accounts.find(a => (a.currency || "") === "USD");
  if (forex) {
    set("stat-forex-name", `${forex.type || "Forex Wallet"} • USD Reserve`);
    set("stat-forex-value", formatCurrency(balOf(forex)));
  }

  // Net-flow pill derived from the latest transactions
  let credits = 0, debits = 0;
  (transactions || []).forEach(t => {
    const a = t.amount_inr !== undefined ? t.amount_inr : (t.amount || 0);
    if (a > 0) credits += a; else debits += Math.abs(a);
  });
  const net = credits - debits;
  const base = credits + debits;
  const pct = base ? Math.abs((net / base) * 100) : 0;
  const pill = document.getElementById("stat-balance-pill");
  if (pill) {
    pill.classList.toggle("pct-neg", net < 0);
    set("stat-balance-pill-text", `${net >= 0 ? "+" : "−"}${pct.toFixed(1)}% vs last cycle`);
  }

  renderCashflow(transactions);
}

function renderCashflow(transactions) {
  const chart = document.getElementById("cashflow-chart");
  if (!chart) return;
  const txs = (transactions || []).slice(0, 16).reverse();
  const amounts = txs.map(t => Math.abs(t.amount_inr !== undefined ? t.amount_inr : (t.amount || 0)));
  const max = Math.max(...amounts, 1);
  chart.innerHTML = "";
  txs.forEach(t => {
    const amtInr = t.amount_inr !== undefined ? t.amount_inr : (t.amount || 0);
    const isCredit = amtInr > 0;
    const bar = document.createElement("div");
    bar.className = "cf-bar " + (isCredit ? "cf-in" : "cf-out");
    bar.style.height = Math.max(6, Math.round((Math.abs(amtInr) / max) * 100)) + "%";
    bar.title = `${t.date.slice(0, 10)} • ${t.description} (${formatCurrency(Math.abs(amtInr))})`;
    chart.appendChild(bar);
  });
}

/* ==========================================================================
   Chat History panel (ChatGPT-style)
   ========================================================================== */

async function loadConversations(openLatest = false) {
  try {
    conversations = await api("/api/conversations");
  } catch (_) { return; }
  renderHistory();
  if (openLatest && conversations.length) {
    await openConversation(conversations[0].id);
  } else if (openLatest) {
    startBlankChat();
  }
}

function renderHistory() {
  const list = document.getElementById("history-list");
  if (!list) return;
  list.innerHTML = "";
  if (!conversations.length) {
    list.innerHTML = `<p class="hist-empty">No conversations yet.</p>`;
    return;
  }
  conversations.forEach(c => {
    const row = document.createElement("div");
    const active = c.id === currentConversationId;
    row.className = "history-item" + (active ? " active" : "");
    row.innerHTML = `
      <i class="fa-regular fa-message hi-ico"></i>
      <span class="hi-title">${escapeHtml(c.title)}</span>
      <button title="Rename" class="hist-btn hist-rename"><i class="fa-solid fa-pen"></i></button>
      <button title="Delete" class="hist-btn hist-delete"><i class="fa-solid fa-trash"></i></button>
    `;
    row.onclick = () => openConversation(c.id);
    const [renameBtn, deleteBtn] = row.querySelectorAll(".hist-btn");
    renameBtn.onclick = (e) => { e.stopPropagation(); renameConversation(c.id, c.title); };
    deleteBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(c.id); };
    list.appendChild(row);
  });
}

async function openConversation(id) {
  try {
    const msgs = await api(`/api/conversations/${id}/messages`);
    currentConversationId = id;
    const container = document.getElementById("messages-container");
    container.innerHTML = "";
    if (!msgs.length) renderWelcomeMessage();
    msgs.forEach(m => m.role === "user" ? appendUserMessage(m.content) : renderAgentResponse(m, false));
    container.scrollTop = container.scrollHeight;
    renderHistory();
  } catch (err) {
    if (err.message !== "unauthenticated") console.error(err);
  }
}

function startBlankChat() {
  currentConversationId = null;
  const container = document.getElementById("messages-container");
  container.innerHTML = "";
  renderWelcomeMessage();
  renderHistory();
  document.getElementById("message-input")?.focus();
}

async function newChat() {
  // Only creates a row once the first message is sent (avoids empty chats piling up).
  startBlankChat();
}

async function renameConversation(id, current) {
  const title = prompt("Rename conversation:", current);
  if (title === null || !title.trim()) return;
  try {
    await api(`/api/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title: title.trim() }) });
    await loadConversations();
  } catch (err) { alert(err.message); }
}

async function deleteConversation(id) {
  if (!confirm("Delete this conversation? This cannot be undone.")) return;
  try {
    await api(`/api/conversations/${id}`, { method: "DELETE" });
    const wasOpen = id === currentConversationId;
    await loadConversations();
    if (wasOpen) {
      if (conversations.length) await openConversation(conversations[0].id);
      else startBlankChat();
    }
  } catch (err) { alert(err.message); }
}

/* ==========================================================================
   Quick prompts + welcome
   ========================================================================== */

function renderQuickPrompts(custId) {
  const container = document.getElementById("quick-prompts-container");
  if (!container) return;
  container.innerHTML = "";
  (quickPromptsByCustomer[custId] || []).forEach(p => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quick-prompt-btn";
    btn.innerHTML = `<i class="fa-solid fa-play qp-ico"></i><span>${escapeHtml(p.label)}</span>`;
    btn.onclick = () => sendMessage(p.text);
    container.appendChild(btn);
  });
}

function renderWelcomeMessage() {
  const container = document.getElementById("messages-container");
  if (!container || !currentCustomerData) return;
  const profile = currentCustomerData.profile;
  const first = profile.name.split(" ")[0];
  const div = document.createElement("div");
  div.className = "msg-row";
  div.innerHTML = `
    <div class="msg-avatar">AC</div>
    <div class="chat-bubble-bot resp-bubble">
      <p class="msg-text">
        Namaste, <strong>${escapeHtml(first)}</strong>! I'm your ClientCare assistant. I can check balances and transactions,
        block or unblock your card, handle disputes, fee waivers, SWIFT/FIRC holds, forex conversions and more.
        What can I help you with today?
      </p>
    </div>`;
  container.appendChild(div);
}

function toggleBenchmarkMode() {
  isBenchmarkMode = !isBenchmarkMode;
  document.getElementById("benchmark-banner")?.classList.toggle("hidden", !isBenchmarkMode);
  document.getElementById("benchmark-toggle-btn")?.classList.toggle("bench-active", isBenchmarkMode);
}

/* ==========================================================================
   Chat
   ========================================================================== */

function handleSendMessage(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById("message-input");
  const text = input ? input.value.trim() : "";
  if (text) sendMessage(text);
}

async function sendMessage(text) {
  text = (text || "").trim();
  if (!text || isSending) return;
  const input = document.getElementById("message-input");
  if (input) input.value = "";

  isSending = true;
  setSendingState(true);
  appendUserMessage(text);
  try {
    if (isBenchmarkMode) await runBenchmark(text);
    else await runStandardChat(text);
  } finally {
    isSending = false;
    setSendingState(false);
    input?.focus();
  }
}

function setSendingState(busy) {
  const btn = document.getElementById("send-btn");
  const input = document.getElementById("message-input");
  if (btn) { btn.disabled = busy; btn.classList.toggle("opacity-60", busy); }
  if (input) input.disabled = busy;
}

function appendUserMessage(text) {
  const container = document.getElementById("messages-container");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "msg-row user-row";
  div.innerHTML = `
    <div class="chat-bubble-user user-bubble">${escapeHtml(text)}</div>
    <div class="msg-avatar msg-avatar-user"><i class="fa-solid fa-user"></i></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addLoader(label) {
  const container = document.getElementById("messages-container");
  const loader = document.createElement("div");
  loader.className = "msg-row";
  loader.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid fa-spinner fa-spin"></i></div>
    <div class="chat-bubble-bot resp-bubble thinking-bubble">
      <span>${label}</span><span class="typing-dots"><i></i><i></i><i></i></span>
    </div>`;
  container.appendChild(loader);
  container.scrollTop = container.scrollHeight;
  return loader;
}

async function runStandardChat(message) {
  const loader = addLoader("Thinking");
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ conversation_id: currentConversationId, message })
    });
    loader.remove();
    currentConversationId = data.conversation.id;
    renderAgentResponse(data, true);
    await Promise.all([refreshOverview(), loadConversations()]);
  } catch (err) {
    loader.remove();
    if (err.message !== "unauthenticated") renderErrorBubble(err.message);
  }
}

function renderErrorBubble(msg) {
  const container = document.getElementById("messages-container");
  const div = document.createElement("div");
  div.className = "msg-error";
  div.textContent = `Something went wrong: ${msg}. Please try again.`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function parseMarkdown(text) {
  if (!text) return "";
  let escaped = escapeHtml(text);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");

  const out = [];
  let list = null; // "ul" | "ol"
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };

  for (const line of escaped.split("\n")) {
    const t = line.trim();
    let m;
    if ((m = t.match(/^(?:[-*•]\s+)(.*)$/))) {
      if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${m[1]}</li>`);
    } else if ((m = t.match(/^\d+[.)]\s+(.*)$/))) {
      if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${m[1]}</li>`);
    } else if ((m = t.match(/^#{1,4}\s+(.*)$/))) {
      closeList();
      out.push(`<p><strong>${m[1]}</strong></p>`);
    } else {
      closeList();
      if (t) out.push(`<p>${t}</p>`);
    }
  }
  closeList();
  return out.join("");
}

function actionBadgeHtml(actions) {
  return (actions || []).filter(a => a && a.success).map(a => `
    <div class="action-badge">
      <i class="fa-solid fa-circle-check ab-ico"></i>
      <span><strong>${escapeHtml((a.action || a.tool || "Action").replace(/_/g, " "))}:</strong> ${escapeHtml(a.message || a.status || "Completed")}</span>
    </div>`).join("");
}

function renderAgentResponse(data, animate) {
  const container = document.getElementById("messages-container");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "msg-row";
  div.innerHTML = `
    <div class="msg-avatar">AC</div>
    <div class="chat-bubble-bot resp-bubble">
      <div class="markdown-body"></div>
      <div class="action-badges"></div>
    </div>`;
  container.appendChild(div);
  const body = div.querySelector(".markdown-body");
  const badges = div.querySelector(".action-badges");
  const finish = () => {
    body.innerHTML = parseMarkdown(data.reply || data.content || "");
    badges.innerHTML = actionBadgeHtml(data.actions);
    container.scrollTop = container.scrollHeight;
  };
  if (!animate) { finish(); return; }

  // Quick word-by-word reveal so replies feel like a live chat.
  const words = (data.reply || "").split(/(\s+)/);
  let i = 0, shown = "";
  const step = () => {
    const chunk = Math.max(1, Math.ceil(words.length / 90));
    shown += words.slice(i, i + chunk).join("");
    i += chunk;
    body.innerHTML = parseMarkdown(shown);
    container.scrollTop = container.scrollHeight;
    if (i < words.length) setTimeout(step, 18); else finish();
  };
  step();
}

/* ==========================================================================
   Benchmark (stateless bot vs memory-augmented agent)
   ========================================================================== */

async function runBenchmark(message) {
  const container = document.getElementById("messages-container");
  const loader = document.createElement("div");
  loader.className = "bench-loader";
  loader.textContent = "Running benchmark: stateless bot vs. memory-augmented agent...";
  container.appendChild(loader);
  try {
    const data = await api("/api/benchmark", { method: "POST", body: JSON.stringify({ message }) });
    loader.remove();
    renderBenchmarkCard(data);
    await refreshOverview();
  } catch (err) {
    loader.remove();
    if (err.message !== "unauthenticated") renderErrorBubble(err.message);
  }
}

function renderBenchmarkCard(data) {
  const container = document.getElementById("messages-container");
  if (!container) return;

  const card = document.createElement("div");
  card.className = "bench-card";

  card.innerHTML = `
    <div class="bench-head">
      <span class="bench-title"><i class="fa-solid fa-code-compare"></i> Comparative Benchmark: Memory Value Attribution</span>
      <span class="bench-cust mono">Account: ${data.customer_name}</span>
    </div>

    <div class="bench-grid">
      <!-- Stateless Left -->
      <div class="bench-col bench-neg">
        <div class="bench-col-head">
          <span class="bench-col-name">Stateless Legacy Bot</span>
          <span class="pill pill-neg mono">Context: 0%</span>
        </div>
        <p class="bench-reply">${escapeHtml(data.stateless.reply)}</p>
        <div class="bench-outcome">Outcome: Demanded redundant forms and branch visit.</div>
      </div>

      <!-- Hindsight Right -->
      <div class="bench-col bench-pos">
        <div class="bench-col-head">
          <span class="bench-col-name">Hindsight Memory-Augmented</span>
          <span class="pill pill-pos mono">${data.hindsight.context_score}</span>
        </div>
        <p class="bench-reply">${escapeHtml(data.hindsight.reply)}</p>
        <div class="bench-outcome bench-outcome-pos">Outcome: Instant STP resolution via verified memory bank.</div>
      </div>
    </div>

    <div class="bench-take"><strong>Audit Takeaway:</strong> ${data.comparison_summary[1]}</div>
  `;
  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
