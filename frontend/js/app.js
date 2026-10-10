/* Banca Hípica P2P — núcleo de la SPA: auth, navegación y vistas de usuario. */
"use strict";

/* ───────────────────── Estado y Mapa de Condiciones ───────────────────── */
let _toastTimer = null;
let globalDuelTypes = [];
let currentRaceEntries = [];
let globalAvailableDuels = [];
let pendingAcceptDuelId = null;
let _delegationBound = false;

const INDIVIDUAL_CONDITIONS = {
  1: { creator: "Ganas si llega 1.º", acceptor: "Ganas si Tu Caballo NO llega en 1.er lugar" },
  2: { creator: "Ganas si llega 1.º o 2.º", acceptor: "Ganas si Tu Caballo SI llega entre los primeros 2" },
  3: { creator: "Ganas si llega 1.º, 2.º o 3.º", acceptor: "Ganas si Tu Caballo SI llega entre los primeros 3" },
  4: { creator: "Ganas si llega 1.º, 2.º, 3.º o 4.º", acceptor: "Ganas si llega 5.º o peor" },
  5: { creator: "Ganas si entra en la pizarra (top 5)", acceptor: "Ganas si queda fuera de la pizarra (6.º o peor)" }
};

/* ───────────────────────── Utilidades ───────────────────────── */
const $ = (sel) => document.querySelector(sel); const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function fmt(value) {
  const n = Number(value || 0);
  return "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function emptyState(message) {
  return `<div class="p-8 text-center text-slate-400 font-medium text-sm">${esc(message)}</div>`;
}

function toast(message, type = "ok") {
  const el = $("#toast");
  if (!el) return;
  el.textContent = message;
  el.className = type;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), 3400);
}

const STATUS_BADGE = {
  OPEN: '<span class="badge badge-open">Abierto</span>',
  ACTIVE: '<span class="badge badge-active">Activo</span>',
  RESOLVED: '<span class="badge badge-resolved">Resuelto</span>',
  PENDING: '<span class="badge badge-pending">Pendiente</span>',
  APPROVED: '<span class="badge badge-approved">Aprobada</span>',
  REJECTED: '<span class="badge badge-rejected">Rechazada</span>',
  PAID: '<span class="badge badge-paid">Pagada</span>',
};
const badge = (status) => STATUS_BADGE[status] || `<span class="badge">${esc(status)}</span>`;

const RULE_LABEL = {
  LOWEST_HORSE_NUMBER: "Gana el menor número",
  HIGHEST_HORSE_NUMBER: "Gana el mayor número",
  MANUAL: "Ganador manual (admin)",
  TIE_REFUND: "Empate ⇒ reembolso",
  OFFICIAL_FINISH: "Según posiciones oficiales (top 5)",
};

/* ───────────────────────── Estado y navegación ───────────────────────── */
const App = { user: null, view: "dashboard" };

const NAV_ITEMS = [
  { id: "dashboard", icon: "🏠", label: "Inicio", admin: false },
  { id: "create-duel", icon: "⚔️", label: "Crear", admin: false },
  { id: "available", icon: "📜", label: "Abiertos", admin: false },
  { id: "my-duels", icon: "🎯", label: "Mis duelos", admin: false },
  { id: "topup", icon: "💳", label: "Recarga", admin: false },
  { id: "withdraw", icon: "💸", label: "Retiro", admin: false },
  { id: "admin-duel-types", icon: "🧩", label: "Tipos", admin: true },
  { id: "admin-races", icon: "📁", label: "Cartelera", admin: true },
  { id: "admin-results", icon: "🏁", label: "Llegada", admin: true },
  { id: "admin-resolve", icon: "✅", label: "Resolver", admin: true },
  { id: "admin-requests", icon: "💰", label: "Pagos", admin: true },
  { id: "admin-bank", icon: "🏦", label: "Banco", admin: true },
  { id: "admin-audit", icon: "📊", label: "Auditoría", admin: true },
];

const VIEW_LOADERS = {
  dashboard: loadDashboard,
  "create-duel": loadCreateDuel,
  available: loadAvailable,
  "my-duels": loadMyDuels,
  topup: loadTopup,
  withdraw: loadWithdraw,
  "admin-duel-types": () => window.Admin && Admin.loadDuelTypes(),
  "admin-races": () => window.Admin && Admin.loadRaces(),
  "admin-results": () => window.Admin && Admin.loadOfficialResults(),
  "admin-resolve": () => window.Admin && Admin.loadResolve(),
  "admin-requests": () => window.Admin && Admin.loadRequests(),
  "admin-bank": () => window.Admin && Admin.loadBank(),
  "admin-audit": () => window.Admin && Admin.loadAudit(),
};

function buildNav() {
  const isAdmin = App.user && App.user.role === "admin";
  const items = NAV_ITEMS.filter((n) => !n.admin || isAdmin);
  const navContainer = $("#nav-items");
  if (navContainer) {
    navContainer.innerHTML = items.map((n) => `
      <button data-nav="${n.id}" data-nav-btn="${n.id}"
        class="shrink-0 flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl text-[10px] font-bold text-slate-500">
        <span class="text-lg leading-none">${n.icon}</span>${n.label}
      </button>`).join("");
  }
}

function showView(viewId) {
  if (!VIEW_LOADERS[viewId]) return;
  if (App.user && App.user.role !== "admin" && viewId.startsWith("admin-")) return;
  App.view = viewId;
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${viewId}`));
  $$("[data-nav-btn]").forEach((b) => {
    const on = b.dataset.navBtn === viewId;
    b.classList.toggle("bg-emerald-50", on);
    b.classList.toggle("text-emerald-700", on);
    b.classList.toggle("text-slate-500", !on);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
  Promise.resolve(VIEW_LOADERS[viewId]()).catch((e) => toast(e.message, "err"));
}

/* ───────────────────────── Autenticación ───────────────────────── */
function updateBalance(value) {
  if (!App.user) return;
  App.user.balance = value;
  API.setSession(API.token(), App.user);
  const headerBal = $("#header-balance"); if (headerBal) headerBal.textContent = fmt(value);
  const dash = $("#dash-balance"); if (dash) dash.textContent = fmt(value);
  const wd = $("#withdraw-balance"); if (wd) wd.textContent = fmt(value);
}

async function refreshMe(silent = true) {
  try {
    const me = await API.get("/auth/me");
    App.user = me;
    API.setSession(API.token(), me);
    const userEl = $("#header-user");
    if (userEl) userEl.textContent = `${me.username} · ${me.role === "admin" ? "Administrador" : "Usuario"}`;
    updateBalance(me.balance);
    return me;
  } catch (e) {
    if (!silent) throw e;
    return null;
  }
}

function showAuth() {
  $("#auth-screen")?.classList.remove("hidden");
  $("#app")?.classList.add("hidden");
}

async function enterApp(user) {
  App.user = user;
  $("#auth-screen")?.classList.add("hidden");
  $("#app")?.classList.remove("hidden");
  const userEl = $("#header-user");
  if (userEl) userEl.textContent = `${user.username} · ${user.role === "admin" ? "Administrador" : "Usuario"}`;
  updateBalance(user.balance);
  buildNav();
  showView("dashboard");
}

function endSession(message) {
  API.clearSession();
  App.user = null;
  showAuth();
  if (message) toast(message, "info");
}

function bindAuth() {
  $("#tab-login")?.addEventListener("click", () => {
    $("#login-form")?.classList.remove("hidden");
    $("#register-form")?.classList.add("hidden");
    $("#tab-login")?.classList.add("bg-white", "shadow");
    $("#tab-login")?.classList.remove("text-slate-500");
    $("#tab-register")?.classList.remove("bg-white", "shadow");
    $("#tab-register")?.classList.add("text-slate-500");
  });

  $("#tab-register")?.addEventListener("click", () => {
    $("#register-form")?.classList.remove("hidden");
    $("#login-form")?.classList.add("hidden");
    $("#tab-register")?.classList.add("bg-white", "shadow");
    $("#tab-register")?.classList.remove("text-slate-500");
    $("#tab-login")?.classList.remove("bg-white", "shadow");
    $("#tab-login")?.classList.add("text-slate-500");
  });

  $("#login-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await API.post("/auth/login", {
        username: $("#login-username").value.trim(),
        password: $("#login-password").value,
      });
      API.setSession(data.token, data.user);
      toast(`Bienvenido, ${data.user.username}`);
      await enterApp(data.user);
    } catch (err) { toast(err.message, "err"); }
  });

  $("#register-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await API.post("/auth/register", {
        username: $("#reg-username").value.trim(),
        password: $("#reg-password").value,
      });
      API.setSession(data.token, data.user);
      toast("Cuenta creada con balance $0.00. ¡Recarga para jugar!");
      await enterApp(data.user);
    } catch (err) { toast(err.message, "err"); }
  });

  $("#logout-btn")?.addEventListener("click", async () => {
    await API.logout();
    endSession("Sesión cerrada.");
  });

  window.addEventListener("auth:expired", () => endSession("Tu sesión expiró. Entra de nuevo."));
}

/* ───────────────────── Plantillas compartidas de tarjetas ───────────────────── */
function duelCard(duel, actionsHtml = "") {
  const youCreator = App.user && duel.creator_id === App.user.id;
  
  const isMorocha = Boolean(duel.horse_creator_2 || duel.horse_opponent_2);
  const isMatchup = !isMorocha && duel.horse_creator !== duel.horse_opponent;

  let matchupHtml = "";

  if (isMorocha) {
    const sideCreator = `
      <div>N.º ${duel.horse_creator} · ${esc(duel.horse_creator_name)}</div>
      <div>N.º ${duel.horse_creator_2} · ${esc(duel.horse_creator_2_name)}</div>
    `;
    const sideOpponent = `
      <div>N.º ${duel.horse_opponent} · ${esc(duel.horse_opponent_name)}</div>
      <div>N.º ${duel.horse_opponent_2} · ${esc(duel.horse_opponent_2_name)}</div>
    `;

    matchupHtml = `
      <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-2 my-3 text-center">
        <div class="rounded-xl bg-slate-50 border border-slate-200 py-2 px-1">
          <p class="text-[10px] uppercase text-slate-400 font-bold">${youCreator ? "Mis Caballos" : "Rival (Creador)"}</p>
          <div class="text-xs font-bold leading-tight text-slate-800 space-y-1 mt-1">${sideCreator}</div>
        </div>
        <span class="font-black text-slate-300">VS</span>
        <div class="rounded-xl bg-emerald-50/70 border border-emerald-200 py-2 px-1">
          <p class="text-[10px] uppercase text-emerald-700 font-bold">${youCreator ? "Caballos Rivales" : "TUS CABALLOS (Si aceptas)"}</p>
          <div class="text-xs font-bold leading-tight text-emerald-950 space-y-1 mt-1">${sideOpponent}</div>
        </div>
      </div>
    `;
  } else if (isMatchup) {
    matchupHtml = `
      <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-2 my-3 text-center">
        <div class="rounded-xl bg-slate-50 border border-slate-200 py-2 px-1">
          <p class="text-[10px] uppercase text-slate-400 font-bold">${youCreator ? "Tu Caballo" : "Rival (Creador)"}</p>
          <p class="text-xs font-bold leading-tight text-slate-800 mt-0.5">N.º ${duel.horse_creator} · ${esc(duel.horse_creator_name)}</p>
        </div>
        <span class="font-black text-slate-300">VS</span>
        <div class="rounded-xl bg-emerald-50/70 border border-emerald-200 py-2 px-1">
          <p class="text-[10px] uppercase text-emerald-700 font-bold">${youCreator ? "Caballo Rival" : "TU CABALLO (Si aceptas)"}</p>
          <p class="text-xs font-bold leading-tight text-emerald-950 mt-0.5">N.º ${duel.horse_opponent} · ${esc(duel.horse_opponent_name)}</p>
        </div>
      </div>
    `;
  } else {
    const condConfig = INDIVIDUAL_CONDITIONS[duel.duel_type_id] || {
      creator: "Apuestas A FAVOR de la condición oficial",
      acceptor: "Apuestas EN CONTRA de la condición oficial"
    };

    const conditionText = youCreator ? condConfig.creator : condConfig.acceptor;
    const badgeText = youCreator ? "TU APUESTA (A FAVOR)" : "TU CONDICIÓN DE VICTORIA (SI ACEPTAS)";
    const bgClass = youCreator 
      ? "bg-amber-50/70 border-amber-200 text-amber-900" 
      : "bg-emerald-50/70 border-emerald-200 text-emerald-900";

    matchupHtml = `
      <div class="my-3 text-center">
        <div class="rounded-xl border py-2.5 px-3 ${bgClass}">
          <p class="text-[10px] uppercase font-bold tracking-wider opacity-80">${badgeText}</p>
          <p class="text-sm font-black mt-0.5">N.º ${duel.horse_creator} — ${esc(duel.horse_creator_name)}</p>
          <p class="text-xs font-semibold mt-1 opacity-90">🎯 ${conditionText}</p>
        </div>
      </div>
    `;
  }

  const winner = duel.winner_username
    ? `<p class="text-xs font-bold text-emerald-700 mt-1">🏆 Ganador: ${esc(duel.winner_username)} (caballo N.º ${duel.winner_horse_number}) · ${fmt(duel.payout_amount)}</p>`
    : "";

  return `
  <article class="card">
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="font-bold text-slate-900 text-sm">${esc(duel.duel_type_name)}</p>
        <p class="text-[11px] text-slate-500">Carrera ${duel.race_number} · ${esc(duel.race_datetime || "—")} · ${esc(RULE_LABEL[duel.logic_rule] || duel.logic_rule || "")}</p>
      </div>
      ${badge(duel.status)}
    </div>

    ${matchupHtml}

    <div class="flex items-center justify-between text-xs text-slate-600 mb-2">
      <span>👤 Creado por <b>${esc(duel.creator_username)}</b>${duel.acceptor_username ? ` vs <b>${esc(duel.acceptor_username)}</b>` : ""}</span>
      <span>Stake <b class="money">${fmt(duel.stake)}</b> · Pozo <b class="money">${fmt(duel.pot)}</b></span>
    </div>
    ${winner}
    ${actionsHtml ? `<div class="mt-3">${actionsHtml}</div>` : ""}
  </article>`;
}

/* ───────────────────────── Vistas de usuario ───────────────────────── */
async function loadDashboard() {
  await refreshMe();
  const duels = await API.get("/duels/mine");
  const recent = duels.slice(0, 3);
  const dashEl = $("#dash-duels");
  if (dashEl) {
    dashEl.innerHTML = recent.length
      ? recent.map((d) => duelCard(d)).join("")
      : emptyState("Aún no tienes duelos. ¡Crea el primero! ⚔️");
  }
}

async function loadCreateDuel() {
  const [types, races] = await Promise.all([
    API.get("/duel-types"),
    API.get("/races"),
  ]);

  globalDuelTypes = types;

  const typeSel = $("#duel-type-select");
  if (typeSel) {
    typeSel.innerHTML = types.length
      ? types.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("")
      : '<option value="">No hay tipos de duelo disponibles</option>';
  }

  const raceSelect = $("#race-select");
  if (!races || races.length === 0) {
    if (raceSelect) raceSelect.innerHTML = `<option value="">La cartelera está vacía (espera la carga del admin)</option>`;
    currentRaceEntries = [];
    renderHorseSelects();
    return;
  }

  const racesByNumber = {};
  races.forEach((r) => {
    if (!racesByNumber[r.race_number]) racesByNumber[r.race_number] = [];
    racesByNumber[r.race_number].push(r);
  });

  const uniqueRaceNumbers = Object.keys(racesByNumber).sort((a, b) => Number(a) - Number(b));
  if (raceSelect) {
    raceSelect.innerHTML = uniqueRaceNumbers
      .map((rNum) => {
        const first = racesByNumber[rNum][0];
        return `<option value="${rNum}">Carrera ${rNum} · ${esc(first.race_datetime || "")}</option>`;
      })
      .join("");
  }

  currentRaceEntries = racesByNumber[uniqueRaceNumbers[0]] || [];

  updateDuelTypeDescription();
  renderHorseSelects();

  if (typeSel) {
    typeSel.onchange = () => {
      updateDuelTypeDescription();
      renderHorseSelects();
    };
  }

  if (raceSelect) {
    raceSelect.onchange = () => {
      const rNum = raceSelect.value;
      currentRaceEntries = racesByNumber[rNum] || [];
      renderHorseSelects();
    };
  }
}

function updateDuelTypeDescription() {
  const typeSel = $("#duel-type-select");
  if (!typeSel) return;
  const typeId = Number(typeSel.value);
  const type = globalDuelTypes.find((t) => t.id === typeId);
  const descEl = $("#duel-type-hint");
  if (descEl && type) {
    descEl.textContent = `${type.description || "Sin descripción"} (${RULE_LABEL[type.logic_rule] || type.logic_rule})`;
  }
}

function renderHorseSelects() {
  let container = $("#horses-select-container");
  if (!container) {
    const firstSelect = $("#horse-my-select");
    if (firstSelect) container = firstSelect.closest(".grid");
  }
  if (!container) return;

  const typeSel = $("#duel-type-select");
  if (!typeSel) return;
  const typeId = Number(typeSel.value);
  const selectedType = globalDuelTypes.find((t) => t.id === typeId);

  const defaultOption = `<option value="" disabled selected>-- Selecciona un caballo --</option>`;
  const horseOptions = defaultOption + currentRaceEntries
    .map((e) => `<option value="${e.horse_number}">N.º ${e.horse_number} — ${esc(e.horse_name)}</option>`)
    .join("");

  if (!selectedType) return;

  if (selectedType.is_morocha) {
    container.className = "grid grid-cols-2 gap-3";
    container.innerHTML = `
      <div class="col-span-2 font-bold text-xs text-slate-500 uppercase tracking-wider mb-1">Mis Caballos</div>
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">MI CABALLO 1</label>
        <select id="horse-my-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">MI CABALLO 2</label>
        <select id="horse-my-2-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
      <div class="col-span-2 font-bold text-xs text-slate-500 uppercase tracking-wider mt-2 mb-1">Caballos Rivales</div>
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">CABALLO RIVAL 1</label>
        <select id="horse-rival-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">CABALLO RIVAL 2</label>
        <select id="horse-rival-2-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
    `;
  } else if (selectedType.is_matchup) {
    container.className = "grid grid-cols-2 gap-3";
    container.innerHTML = `
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">TU CABALLO</label>
        <select id="horse-my-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">CABALLO RIVAL</label>
        <select id="horse-rival-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
    `;
  } else {
    container.className = "grid grid-cols-1 gap-3";
    container.innerHTML = `
      <div>
        <label class="block text-xs font-semibold text-slate-600 mb-1">TU CABALLO</label>
        <select id="horse-my-select" class="w-full border border-slate-200 rounded-xl p-2.5 text-sm bg-white" required>${horseOptions}</select>
      </div>
    `;
  }

  // Exclusión inteligente de caballos seleccionados
  const selects = container.querySelectorAll("select");
  selects.forEach((select) => {
    select.addEventListener("change", handleHorseSelectExclusion);
  });
}

async function loadAvailable() {
  const duels = await API.get("/duels/available");
  globalAvailableDuels = duels;

  const availEl = $("#available-list");
  if (availEl) {
    availEl.innerHTML = duels.length
      ? duels.map((d) => duelCard(d, `
          <button class="btn btn-primary w-full py-2.5 rounded-xl font-bold text-sm bg-emerald-600 text-white hover:bg-emerald-700" data-action="accept-duel" data-id="${d.id}">
            ⚡ Aceptar y retener ${fmt(d.stake)}
          </button>`)).join("")
      : emptyState("No hay duelos abiertos ahora mismo. 🏇");
  }
}

async function loadMyDuels() {
  const duels = await API.get("/duels/mine");
  const myDuelsEl = $("#my-duels-list");
  if (myDuelsEl) {
    myDuelsEl.innerHTML = duels.length
      ? duels.map((d) => {
          const canCancel = d.status === "OPEN" && d.creator_id === App.user.id;
          const actions = canCancel
            ? `<button class="btn btn-danger w-full py-2 rounded-xl text-xs font-bold bg-rose-600 text-white hover:bg-rose-700" data-action="cancel-duel" data-id="${d.id}">✕ Cancelar duelo (reembolsar)</button>`
            : "";
          return duelCard(d, actions);
        }).join("")
      : emptyState("Todavía no participas en ningún duelo.");
  }
}

async function loadTopup() {
  const [bank, history] = await Promise.all([
    API.get("/bank").catch(() => null),
    API.get("/payments/topups"),
  ]);
  const bankEl = $("#bank-info-topup");
  if (bankEl) {
    bankEl.innerHTML = bank && bank.bank_name
      ? `
        <p class="font-bold text-slate-800">🏦 ${esc(bank.bank_name)} — ${esc(bank.account_type)}</p>
        <p><b>Teléfono:</b> ${esc(bank.phone)}</p>
        <p><b>Cédula:</b> ${esc(bank.id_number)}</p>
        <p><b>Titular:</b> ${esc(bank.holder_name)}</p>`
      : '<p class="text-xs text-amber-600 font-bold">⚠ Aún no hay datos bancarios configurados por el administrador.</p>';
  }

  const topupHistEl = $("#topup-history");
  if (topupHistEl) {
    topupHistEl.innerHTML = history.length
      ? history.map((r) => `
        <div class="card card-tight flex items-center justify-between gap-2">
          <div class="text-xs">
            <p class="font-bold text-slate-800 money">${fmt(r.amount)} · Ref ${esc(r.reference)}</p>
            <p class="text-slate-500">${esc(r.created_at || "")} · desde ${esc(r.wallet_phone)}</p>
          </div>
          ${badge(r.status)}
        </div>`).join("")
      : emptyState("No has reportado recargas.");
  }
}

async function loadWithdraw() {
  await refreshMe();
  const history = await API.get("/payments/withdrawals");
  const wdHistEl = $("#withdraw-history");
  if (wdHistEl) {
    wdHistEl.innerHTML = history.length
      ? history.map((r) => `
        <div class="card card-tight flex items-center justify-between gap-2">
          <div class="text-xs">
            <p class="font-bold text-slate-800 money">${fmt(r.amount)} → ${esc(r.destination_phone)}</p>
            <p class="text-slate-500">${esc(r.created_at || "")}</p>
          </div>
          ${badge(r.status)}
        </div>`).join("")
      : emptyState("No has solicitado retiros.");
  }
}

/* ───────────────────── Modal de Confirmación de Aceptación ───────────────────── */
function openAcceptModal(duel) {
  pendingAcceptDuelId = duel.id;
  const modal = document.getElementById("confirm-modal");
  const content = document.getElementById("modal-summary-content");
  if (!modal || !content) return;

  const userBalance = App.user ? App.user.balance : 0;
  const hasEnoughBalance = userBalance >= duel.stake;

  let conditionDetail = "";

  if (duel.horse_creator_2 || duel.horse_opponent_2) {
    // 1. MOROCHA (2 vs 2)
    conditionDetail = `
      <div class="p-3 rounded-xl bg-emerald-50 border border-emerald-200 space-y-1">
        <p class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider">TUS CABALLOS (SI ACEPTAS)</p>
        <p class="font-bold text-emerald-950 text-sm">N.º ${duel.horse_opponent} (${esc(duel.horse_opponent_name)}) y N.º ${duel.horse_opponent_2} (${esc(duel.horse_opponent_2_name)})</p>
        <p class="text-emerald-700 text-xs font-medium">🎯 Ganas si cualquiera de tus 2 caballos llega antes que los del rival.</p>
      </div>`;
  } else if (duel.horse_creator !== duel.horse_opponent) {
    // 2. MARCAS (1 vs 1)
    conditionDetail = `
      <div class="p-3 rounded-xl bg-emerald-50 border border-emerald-200 space-y-1">
        <p class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider">TU CABALLO vs RIVAL (SI ACEPTAS)</p>
        <p class="font-bold text-emerald-950 text-sm">N.º ${duel.horse_opponent} (${esc(duel.horse_opponent_name)}) vs N.º ${duel.horse_creator} (${esc(duel.horse_creator_name)})</p>
        <p class="text-emerald-700 text-xs font-semibold mt-1">🎯 Ganas si el N.º ${duel.horse_opponent} (${esc(duel.horse_opponent_name)}) llega antes que el N.º ${duel.horse_creator}.</p>
      </div>`;
  } else {
    // 3. INDIVIDUAL (1 solo caballo)
    const condConfig = INDIVIDUAL_CONDITIONS[duel.duel_type_id] || { acceptor: "Ganas si Tu Caballo cumple la condición opuesta" };
    conditionDetail = `
      <div class="p-3 rounded-xl bg-emerald-50 border border-emerald-200 space-y-1">
        <p class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider">TU CONDICIÓN DE VICTORIA (SI ACEPTAS)</p>
        <p class="font-bold text-emerald-950 text-sm">N.º ${duel.horse_creator} — ${esc(duel.horse_creator_name)}</p>
        <p class="text-emerald-700 text-xs font-semibold mt-1">🎯 ${condConfig.acceptor}</p>
      </div>`;
  }

  const netPayout = duel.stake * 2 * 0.95;

  content.innerHTML = `
    <div class="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-200">
      <div>
        <p class="font-bold text-slate-800 text-sm">${esc(duel.duel_type_name || "Duelo")}</p>
        <p class="text-slate-500 text-xs">Carrera N.º ${duel.race_number} · Creado por <b>${esc(duel.creator_username || "Usuario")}</b></p>
      </div>
      <span class="font-black text-slate-800 text-sm">${fmt(duel.stake)}</span>
    </div>

    ${conditionDetail}

    <div class="space-y-1.5 p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-xs">
      <div class="flex justify-between text-slate-600">
        <span>Tu Saldo Actual:</span>
        <span class="font-semibold text-slate-800">${fmt(userBalance)}</span>
      </div>
      <div class="flex justify-between text-slate-600">
        <span>Stake a Retener (Escrow):</span>
        <span class="font-semibold text-amber-700">-${fmt(duel.stake)}</span>
      </div>
      <div class="flex justify-between font-bold text-slate-800 pt-1 border-t border-slate-200">
        <span>Pozo Estimado (Si ganas):</span>
        <span class="text-emerald-700">${fmt(netPayout)} (Neto)</span>
      </div>
    </div>

    ${
      !hasEnoughBalance
        ? `<div class="p-2.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl font-medium text-center space-y-2 text-xs">
            <p>⚠️ Saldo insuficiente para aceptar este duelo.</p>
            <button type="button" data-nav="topup" class="btn bg-rose-600 text-white hover:bg-rose-700 py-1 px-3 text-xs w-full rounded-lg font-bold">
              Recargar Saldo
            </button>
           </div>`
        : ""
    }
  `;

  const confirmBtn = document.getElementById("confirm-accept-btn");
  if (confirmBtn) {
    confirmBtn.disabled = !hasEnoughBalance;
    confirmBtn.classList.toggle("opacity-50", !hasEnoughBalance);
  }

  modal.classList.remove("hidden");
}

function closeAcceptModal() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.classList.add("hidden");
  pendingAcceptDuelId = null;
}

/* ───────────────────── Delegación de Eventos ───────────────────── */
function bindDelegation() {
  if (_delegationBound) return;
  _delegationBound = true;

  document.getElementById("close-modal-btn")?.addEventListener("click", closeAcceptModal);
  document.getElementById("cancel-modal-btn")?.addEventListener("click", closeAcceptModal);

  document.getElementById("confirm-accept-btn")?.addEventListener("click", async () => {
    if (!pendingAcceptDuelId) return;
    const btn = document.getElementById("confirm-accept-btn");
    btn.disabled = true;

    try {
      const duel = await API.post(`/duels/${pendingAcceptDuelId}/accept`, {});
      toast(`¡Duelo #${duel.id} aceptado! Retuviste ${fmt(duel.stake)} en escrow.`);
      closeAcceptModal();
      await refreshMe();
      await loadAvailable();
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  });

  document.addEventListener("click", async (event) => {
    const navEl = event.target.closest("[data-nav]");
    if (navEl) {
      closeAcceptModal();
      showView(navEl.dataset.nav);
      return;
    }

    const actionEl = event.target.closest("[data-action]");
    if (!actionEl) return;
    const action = actionEl.dataset.action;
    const id = Number(actionEl.dataset.id);

    if (action === "accept-duel") {
      const duel = globalAvailableDuels.find((d) => d.id === id);
      if (duel) {
        openAcceptModal(duel);
      } else {
        toast("No se pudo obtener la información del duelo", "err");
      }
    } else if (action === "cancel-duel") {
      if (!confirm("¿Cancelar este duelo y recuperar tu stake en escrow?")) return;
      actionEl.disabled = true;
      try {
        await API.post(`/duels/${id}/cancel`);
        toast("Duelo cancelado; stake reembolsado.");
        await refreshMe();
        await loadMyDuels();
      } catch (err) {
        toast(err.message, "err");
      } finally {
        actionEl.disabled = false;
      }
    }
  });
}

/* ───────────────────── Calculadora y Exclusiones ───────────────────── */
function updatePayoutCalculator() {
  const stakeInput = document.getElementById("stake-input");
  const calcContainer = document.getElementById("payout-calculator");
  const potEl = document.getElementById("calc-pot");
  const feeEl = document.getElementById("calc-fee");
  const netEl = document.getElementById("calc-net");

  if (!stakeInput || !calcContainer) return;

  const stake = parseFloat(stakeInput.value);

  if (isNaN(stake) || stake <= 0) {
    calcContainer.classList.add("hidden");
    return;
  }

  const pot = stake * 2;
  const fee = pot * 0.05;
  const netPayout = pot - fee;

  if (potEl) potEl.textContent = fmt(pot);
  if (feeEl) feeEl.textContent = `-${fmt(fee)}`;
  if (netEl) netEl.textContent = fmt(netPayout);

  calcContainer.classList.remove("hidden");
}

function handleHorseSelectExclusion() {
  const container = document.getElementById("horses-select-container");
  if (!container) return;

  const selects = Array.from(container.querySelectorAll("select"));
  const selectedValues = selects.map((s) => s.value).filter((val) => val && val !== "0");

  selects.forEach((currentSelect) => {
    const currentValue = currentSelect.value;
    Array.from(currentSelect.options).forEach((option) => {
      if (!option.value || option.value === "0") return;
      const isSelectedElsewhere = selectedValues.includes(option.value) && option.value !== currentValue;
      option.disabled = isSelectedElsewhere;
    });
  });
}

/* ───────────────────── Formularios y Acciones ───────────────────── */
function bindForms() {
  const stakeInput = $("#stake-input");
  if (stakeInput) {
    stakeInput.addEventListener("input", updatePayoutCalculator);
  }

  $("#create-duel-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const duelTypeId = Number($("#duel-type-select").value);
    const raceNumber = Number($("#race-select").value);
    const stake = Number($("#stake-input").value);

    const selectedType = globalDuelTypes.find((t) => t.id === duelTypeId);
    if (!selectedType) {
      toast("Selecciona un tipo de duelo válido.", "err");
      return;
    }

    const elMy = $("#horse-my-select");
    const elRival = $("#horse-rival-select");
    const elMy2 = $("#horse-my-2-select");
    const elRival2 = $("#horse-rival-2-select");

    const horseCreator = elMy && elMy.value ? Number(elMy.value) : null;
    const horseOpponent = elRival && elRival.value ? Number(elRival.value) : null;
    const horseCreator2 = elMy2 && elMy2.value ? Number(elMy2.value) : null;
    const horseOpponent2 = elRival2 && elRival2.value ? Number(elRival2.value) : null;

    if (selectedType.is_morocha) {
      if (!raceNumber || !horseCreator || !horseOpponent || !horseCreator2 || !horseOpponent2) {
        toast("Debes seleccionar los 4 caballos para la modalidad MOROCHA.", "err");
        return;
      }
      const selectedSet = new Set([horseCreator, horseOpponent, horseCreator2, horseOpponent2]);
      if (selectedSet.size < 4) {
        toast("Los 4 caballos seleccionados para MOROCHA deben ser distintos entre sí.", "err");
        return;
      }
    } else if (selectedType.is_matchup) {
      if (!raceNumber || !horseCreator || !horseOpponent) {
        toast("Debes seleccionar Tu Caballo y el Caballo Rival.", "err");
        return;
      }
      if (horseCreator === horseOpponent) {
        toast("Elige dos caballos distintos.", "err");
        return;
      }
    } else {
      if (!raceNumber || !horseCreator) {
        toast("Debes seleccionar Tu Caballo.", "err");
        return;
      }
    }

    if (!stake || stake <= 0) {
      toast("Ingresa un monto de apuesta (stake) válido.", "err");
      return;
    }

    try {
      const payload = {
        duel_type_id: duelTypeId,
        race_number: raceNumber,
        horse_creator: horseCreator,
        horse_opponent: (selectedType.is_matchup || selectedType.is_morocha) ? horseOpponent : horseCreator,
        stake,
      };

      if (selectedType.is_morocha) {
        payload.horse_creator_2 = horseCreator2;
        payload.horse_opponent_2 = horseOpponent2;
      }

      const duel = await API.post("/duels/create", payload);
      $("#stake-input").value = "";
      
      const calcContainer = document.getElementById("payout-calculator");
      if (calcContainer) calcContainer.classList.add("hidden");

      toast(`¡Duelo #${duel.id} publicado! Stake de ${fmt(duel.stake)} en escrow.`);
      await refreshMe();
      showView("my-duels");
    } catch (err) {
      toast(err.message, "err");
    }
  });

  $("#topup-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await API.post("/payments/topup", {
        amount: Number($("#topup-amount").value),
        reference: $("#topup-reference").value.trim(),
        wallet_phone: $("#topup-phone").value.trim(),
      });
      e.target.reset();
      toast(`Reporte #${r.id} enviado. Espera aprobación de la casa.`);
      await loadTopup();
    } catch (err) {
      toast(err.message, "err");
    }
  });

  $("#withdraw-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await API.post("/payments/withdraw", {
        amount: Number($("#withdraw-amount").value),
        destination_phone: $("#withdraw-phone").value.trim(),
      });
      e.target.reset();
      toast(`Retiro #${r.id} solicitado: ${fmt(r.amount)} retenidos.`);
      await loadWithdraw();
    } catch (err) {
      toast(err.message, "err");
    }
  });

  $("#refresh-available")?.addEventListener("click", () => loadAvailable().catch((e) => toast(e.message, "err")));
  $("#refresh-my-duels")?.addEventListener("click", () => loadMyDuels().catch((e) => toast(e.message, "err")));
}

/* ───────────────────────────── Arranque ───────────────────────────── */
async function init() {
  bindAuth();
  bindForms();
  bindDelegation();
  if (window.Admin) Admin.bind();

  const tkn = API.token();
  if (tkn) {
    try {
      const me = await API.get("/auth/me");
      API.setSession(tkn, me);
      await enterApp(me);
      return;
    } catch (_) { API.clearSession(); }
  }
  showAuth();
}

document.addEventListener("DOMContentLoaded", init);