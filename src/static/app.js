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

const FX_RATE = 86.50;

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
      icon.className = "fa-solid fa-moon text-blue-600";
    }
    if (label) {
      label.textContent = "Dark";
    }
  } else {
    body.classList.remove("light-theme");
    if (icon) {
      icon.className = "fa-solid fa-sun text-amber-500";
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
    if (icon) icon.className = "fa-solid fa-moon text-blue-600";
    if (label) label.textContent = "Dark";
  } else {
    localStorage.setItem("apex_theme", "dark");
    if (icon) icon.className = "fa-solid fa-sun text-amber-500";
    if (label) label.textContent = "Bright";
  }
}

/* ==========================================================================
   Valuation Currency Switcher (INR / USD / Dual)
   ========================================================================== */

function setCurrencyMode(mode) {
  currencyMode = mode;
  document.querySelectorAll("[id^='curr-']").forEach(btn => {
    btn.className = "px-2.5 py-1 rounded font-medium text-[var(--text-muted)] hover:text-[var(--text-main)]";
  });
  const activeBtn = document.getElementById(`curr-${mode.toLowerCase()}`);
  if (activeBtn) {
    activeBtn.className = "px-2.5 py-1 rounded font-medium text-blue-600 bg-blue-500/10 border border-blue-500/30";
  }
  if (currentCustomerData) {
    renderLedger(currentCustomerData.profile, currentCustomerData.transactions);
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

function renderLedger(profile, transactions) {
  const accountContainer = document.getElementById("account-cards-container");
  if (!accountContainer) return;
  accountContainer.innerHTML = "";

  (profile.accounts || []).forEach(acc => {
    const card = document.createElement("div");
    card.className = "p-3 rounded-lg bg-[var(--bg-strip)] border border-[var(--border-color)] flex items-center justify-between";
    
    const balInr = acc.balance_inr !== undefined ? acc.balance_inr : acc.balance;
    const formattedBal = formatCurrency(balInr, acc.currency);
    
    const holdBadge = acc.hold_amount > 0 
      ? `<span class="text-[10px] text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30 font-mono block mt-1">Under Hold: ${formatCurrency(acc.hold_amount)}</span>` 
      : "";

    card.innerHTML = `
      <div>
        <div class="text-xs font-semibold text-[var(--text-main)]">${acc.type}</div>
        <div class="text-[10px] text-[var(--text-muted)] font-mono mt-0.5">${acc.account_id} • ${acc.currency}</div>
      </div>
      <div class="text-right">
        <div class="text-xs font-bold text-emerald-600 font-mono">${formattedBal}</div>
        ${holdBadge}
      </div>
    `;
    accountContainer.appendChild(card);
  });

  // Cards
  const cardsContainer = document.getElementById("registered-cards-container");
  if (cardsContainer) {
    cardsContainer.innerHTML = "";
    (profile.cards || []).forEach(c => {
      const isFrozen = c.status.toLowerCase().includes("frozen");
      const statusClass = isFrozen 
        ? "text-rose-600 bg-rose-500/10 border-rose-500/30" 
        : "text-emerald-600 bg-emerald-500/10 border-emerald-500/30";
      
      const div = document.createElement("div");
      div.className = "flex items-center justify-between p-2 rounded-lg bg-[var(--bg-strip)] border border-[var(--border-color)] text-xs";
      div.innerHTML = `
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-credit-card text-[var(--text-muted)] text-xs"></i>
          <div>
            <div class="text-[var(--text-main)] font-medium text-xs font-mono">${c.masked_number}</div>
            <div class="text-[10px] text-[var(--text-muted)]">${c.network || 'RuPay'}</div>
          </div>
        </div>
        <span class="text-[10px] px-2 py-0.5 rounded border font-mono font-medium ${statusClass}">${c.status}</span>
      `;
      cardsContainer.appendChild(div);
    });
  }

  // Transactions
  const txContainer = document.getElementById("transactions-container");
  if (txContainer) {
    txContainer.innerHTML = "";
    (transactions || []).forEach(t => {
      const div = document.createElement("div");
      div.className = "p-2 rounded bg-[var(--bg-strip)] border border-[var(--border-color)] flex items-center justify-between text-xs";
      
      const amtInr = t.amount_inr !== undefined ? t.amount_inr : t.amount;
      const isCredit = amtInr > 0;
      const amtColor = isCredit ? "text-emerald-600" : "text-[var(--text-main)]";
      const prefix = isCredit ? "+" : "";
      
      div.innerHTML = `
        <div class="truncate max-w-[190px]">
          <div class="font-medium text-[var(--text-main)] truncate text-[11px]">${t.description}</div>
          <div class="text-[10px] text-[var(--text-muted)] font-mono">${t.date.slice(0, 10)} • ${t.payment_mode || 'UPI'}</div>
        </div>
        <div class="text-right">
          <div class="font-semibold font-mono text-[11px] ${amtColor}">${prefix}${formatCurrency(Math.abs(amtInr))}</div>
          <div class="text-[9px] text-[var(--text-muted)] truncate max-w-[95px] font-mono">${t.utr_ref || t.status}</div>
        </div>
      `;
      txContainer.appendChild(div);
    });
  }
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
    list.innerHTML = `<p class="text-[var(--text-muted)] text-center py-4 text-xs font-mono">No conversations yet.</p>`;
    return;
  }
  conversations.forEach(c => {
    const row = document.createElement("div");
    const active = c.id === currentConversationId;
    row.className = "history-item group flex items-center gap-1 rounded-lg px-2.5 py-2 cursor-pointer border " +
      (active ? "bg-blue-500/10 border-blue-500/30" : "border-transparent hover:bg-[var(--bg-strip)]");
    row.innerHTML = `
      <i class="fa-regular fa-message text-[10px] text-[var(--text-muted)]"></i>
      <span class="flex-1 truncate text-[12px] text-[var(--text-main)]">${escapeHtml(c.title)}</span>
      <button title="Rename" class="hist-btn text-[var(--text-muted)] hover:text-blue-500 px-1"><i class="fa-solid fa-pen text-[10px]"></i></button>
      <button title="Delete" class="hist-btn text-[var(--text-muted)] hover:text-rose-500 px-1"><i class="fa-solid fa-trash text-[10px]"></i></button>
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
    btn.className = "quick-prompt-btn font-mono";
    btn.innerHTML = `<i class="fa-solid fa-play text-blue-500 text-[9px]"></i><span>${escapeHtml(p.label)}</span>`;
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
  div.className = "flex gap-3 text-xs";
  div.innerHTML = `
    <div class="w-8 h-8 rounded bg-blue-600/10 border border-blue-600/30 flex items-center justify-center font-bold text-xs text-blue-600 flex-shrink-0 font-mono">AC</div>
    <div class="chat-bubble-bot rounded-lg p-4 max-w-2xl leading-relaxed shadow-sm">
      <p class="text-[12px] leading-relaxed text-[var(--text-main)]">
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
  document.getElementById("benchmark-toggle-btn")?.classList.toggle("bg-blue-600", isBenchmarkMode);
  document.getElementById("benchmark-toggle-btn")?.classList.toggle("text-white", isBenchmarkMode);
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
  div.className = "flex gap-3 justify-end text-xs";
  div.innerHTML = `
    <div class="chat-bubble-user rounded-lg p-3 max-w-lg leading-relaxed text-[12px] shadow-sm whitespace-pre-wrap">${escapeHtml(text)}</div>
    <div class="w-8 h-8 rounded bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 font-mono">
      <i class="fa-solid fa-user text-[11px]"></i>
    </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addLoader(label) {
  const container = document.getElementById("messages-container");
  const loader = document.createElement("div");
  loader.className = "flex gap-3 text-xs";
  loader.innerHTML = `
    <div class="w-8 h-8 rounded bg-blue-600/10 border border-blue-600/30 flex items-center justify-center text-blue-600 flex-shrink-0">
      <i class="fa-solid fa-spinner fa-spin text-xs"></i>
    </div>
    <div class="chat-bubble-bot rounded-lg p-3 text-[var(--text-muted)] flex items-center gap-1 font-mono text-[11px]">
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
  div.className = "p-3 text-xs text-rose-500 bg-rose-500/10 border border-rose-500/30 rounded-lg font-mono";
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
    <div class="mt-2.5 p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 text-[11px] font-mono flex items-center gap-2">
      <i class="fa-solid fa-circle-check text-emerald-500"></i>
      <span><strong>${escapeHtml((a.action || a.tool || "Action").replace(/_/g, " "))}:</strong> ${escapeHtml(a.message || a.status || "Completed")}</span>
    </div>`).join("");
}

function renderAgentResponse(data, animate) {
  const container = document.getElementById("messages-container");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "flex gap-3 text-xs";
  div.innerHTML = `
    <div class="w-8 h-8 rounded bg-blue-600/10 border border-blue-600/30 flex items-center justify-center font-bold text-xs text-blue-600 flex-shrink-0 font-mono">AC</div>
    <div class="chat-bubble-bot rounded-lg p-4 max-w-2xl leading-relaxed shadow-sm">
      <div class="markdown-body text-[var(--text-main)]"></div>
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
  loader.className = "p-3 text-xs text-center text-blue-600 bg-blue-500/10 border border-blue-500/30 rounded-lg font-mono animate-pulse";
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
  card.className = "bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-4 shadow-lg space-y-3";

  card.innerHTML = `
    <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-2.5 text-xs font-mono">
      <span class="font-bold text-[var(--text-main)] flex items-center gap-2">
        <i class="fa-solid fa-code-compare text-blue-600"></i> Comparative Benchmark: Memory Value Attribution
      </span>
      <span class="text-[var(--text-muted)]">Account: ${data.customer_name}</span>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
      <!-- Stateless Left -->
      <div class="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/5 space-y-2">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-rose-600 text-xs font-mono">Stateless Legacy Bot</span>
          <span class="text-[9px] bg-rose-500/10 text-rose-600 px-2 py-0.5 rounded border border-rose-500/30 font-mono">Context: 0%</span>
        </div>
        <p class="text-[var(--text-main)] leading-relaxed text-[11px]">${escapeHtml(data.stateless.reply)}</p>
        <div class="text-[10px] text-[var(--text-muted)] font-mono pt-1">
          Outcome: Demanded redundant forms and branch visit.
        </div>
      </div>

      <!-- Hindsight Right -->
      <div class="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-emerald-600 text-xs font-mono">Hindsight Memory-Augmented</span>
          <span class="text-[9px] bg-emerald-500/10 text-emerald-600 px-2 py-0.5 rounded border border-emerald-500/30 font-mono font-bold">${data.hindsight.context_score}</span>
        </div>
        <p class="text-[var(--text-main)] leading-relaxed text-[11px]">${escapeHtml(data.hindsight.reply)}</p>
        <div class="text-[10px] text-emerald-600 font-mono pt-1">
          Outcome: Instant STP resolution via verified memory bank.
        </div>
      </div>
    </div>

    <div class="p-2.5 rounded bg-[var(--bg-strip)] border border-[var(--border-color)] text-[11px] text-[var(--text-muted)] font-mono">
      <strong class="text-blue-600">Audit Takeaway:</strong> ${data.comparison_summary[1]}
    </div>
  `;
  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
