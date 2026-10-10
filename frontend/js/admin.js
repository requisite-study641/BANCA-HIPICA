/* Banca Hípica P2P — módulo de administración (CRUD, carga, resolución y auditoría). */
"use strict";

const Admin = (() => {
  let duelTypesCache = [];
  const filters = { topups: "PENDING", withdrawals: "PENDING" };

  const guard = () => App.user && App.user.role === "admin";
  const q = (sel) => document.querySelector(sel);

  function kpi(label, value, sub = "") {
    return `
      <div class="card card-tight">
        <p class="text-[10px] uppercase tracking-wide text-slate-400">${label}</p>
        <p class="text-lg font-extrabold text-slate-900 money leading-tight">${value}</p>
        ${sub ? `<p class="text-[11px] text-slate-500">${sub}</p>` : ""}
      </div>`;
  }

  /* ══════════════ 1. Tipos de duelo (CRUD) ══════════════ */
  async function loadDuelTypes() {
    duelTypesCache = await API.get("/duel-types");
    q("#duel-types-admin-list").innerHTML = duelTypesCache.length
      ? duelTypesCache.map((t) => `
        <div class="card card-tight">
          <div class="flex justify-between items-start gap-2">
            <div class="min-w-0">
              <p class="font-bold text-sm text-slate-900">${esc(t.name)}</p>
              <p class="text-[11px] text-slate-500">${esc(t.description || "Sin descripción")}</p>
              <p class="text-[11px] font-bold text-emerald-700 mt-1">⚙ ${esc(RULE_LABEL[t.logic_rule] || t.logic_rule)}</p>
            </div>
            <div class="flex gap-1 shrink-0">
              <button class="btn btn-ghost btn-sm" title="Modificar" data-action="edit-duel-type" data-id="${t.id}">✏️</button>
              <button class="btn btn-danger btn-sm" title="Eliminar" data-action="delete-duel-type" data-id="${t.id}">🗑</button>
            </div>
          </div>
        </div>`).join("")
      : emptyState("No hay tipos de duelo. Crea el primero con el formulario.");
  }

  function resetDuelTypeForm() {
    q("#duel-type-form").reset();
    q("#duel-type-id").value = "";
    q("#duel-type-form-title").textContent = "Nuevo tipo de duelo";
    q("#duel-type-save-btn").textContent = "Crear";
  }

  async function saveDuelType() {
    const id = q("#duel-type-id").value;
    const payload = {
      name: q("#duel-type-name").value.trim(),
      logic_rule: q("#duel-type-rule").value,
      description: q("#duel-type-description").value.trim(),
    };
    if (payload.name.length < 3) { toast("El nombre necesita 3 caracteres o más.", "err"); return; }
    try {
      if (id) {
        await API.put(`/admin/duel-types/${id}`, payload);
        toast("Tipo de duelo modificado.");
      } else {
        await API.post("/admin/duel-types", payload);
        toast("Tipo de duelo creado.");
      }
      resetDuelTypeForm();
      await loadDuelTypes();
    } catch (err) { toast(err.message, "err"); }
  }

  function editDuelType(id) {
    const t = duelTypesCache.find((x) => x.id === id);
    if (!t) return;
    q("#duel-type-id").value = t.id;
    q("#duel-type-name").value = t.name;
    q("#duel-type-rule").value = t.logic_rule;
    q("#duel-type-description").value = t.description || "";
    q("#duel-type-form-title").textContent = `Modificar tipo #${t.id}`;
    q("#duel-type-save-btn").textContent = "Guardar cambios";
    q("#duel-type-form").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function deleteDuelType(id) {
    if (!confirm("¿Eliminar este tipo de duelo?")) return;
    try {
      await API.del(`/admin/duel-types/${id}`);
      toast("Tipo de duelo eliminado.");
      if (String(q("#duel-type-id").value) === String(id)) resetDuelTypeForm();
      await loadDuelTypes();
    } catch (err) { toast(err.message, "err"); }
  }

  /* ══════════════ 2. Carga de cartelera ══════════════ */
  async function loadRaces() {
    const races = await API.get("/races");
    const container = q("#races-admin-list");
    if (!races.length) {
      container.innerHTML = emptyState("La cartelera está vacía. Sube el archivo oficial (reporte INH o CSV).");
      return;
    }
    const byRace = {};
    races.forEach((r) => { (byRace[r.race_number] = byRace[r.race_number] || []).push(r); });

    container.innerHTML = Object.keys(byRace)
      .sort((a, b) => Number(a) - Number(b))
      .map((raceNumber) => {
        const rows = byRace[raceNumber];
        return `
        <div class="card">
          <div class="flex items-center justify-between mb-2">
            <p class="font-bold text-sm text-slate-900">🏁 Carrera ${raceNumber}</p>
            <span class="text-[11px] text-slate-500">${esc(rows[0].race_datetime || "")} · ${rows.length} caballos</span>
          </div>
          <ul class="divide-y divide-slate-100">
            ${rows.map((h) => `
              <li class="flex items-center justify-between py-1.5 text-sm">
                <span><b class="text-slate-700">N.º ${h.horse_number}</b> —${esc(h.horse_name)}</span>
                <button class="btn btn-danger btn-sm" title="Quitar de la cartelera"
                        data-action="delete-race" data-id="${h.id}">🗑</button>
              </li>`).join("")}
          </ul>
        </div>`;
      }).join("");
  }

  async function uploadRaces() {
    const input = q("#race-file");
    const file = input.files && input.files[0];
    if (!file) { toast("Selecciona primero el archivo (reporte INH, CSV o Excel .xlsx/.xls).", "err"); return; }
    const btn = q("#upload-race-btn");
    btn.disabled = true;
    btn.textContent = "Procesando…";
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await API.upload("/admin/races/upload", fd);

      const raceList = (res.races || [])
        .map((r) => `#${r.race_number} · ${esc(r.datetime)} · ${r.horses} ejemplares`)
        .join("<br>");
      q("#upload-result").innerHTML = `
        <div class="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800 space-y-1">
          <p class="font-bold">✅ ${esc(res.detail)}</p>
          <p>
            Formato: <b>${esc(res.format_label || res.format || "—")}</b> ·
            Codificación: <b>${esc(res.encoding || "—")}</b><br>
            Nuevas: <b>${res.imported}</b> · Actualizadas: <b>${res.updated}</b> ·
            Total ejemplares: <b>${res.total_rows}</b>
          </p>
          ${raceList ? `<p class="border-t border-emerald-200 pt-1">Carreras importadas:<br>${raceList}</p>` : ""}
        </div>`;
      toast(`Importación masiva OK: ${res.total_rows} ejemplares ✓`);
      input.value = "";
      await loadRaces();
    } catch (err) {
      const detail = err.detail;
      if (detail && Array.isArray(detail.errors)) {
        const list = detail.errors
          .slice(0, 20)
          .map((e) => `<li>${esc(e)}</li>`)
          .join("");
        const more = detail.errors.length > 20
          ? `<li>… y ${detail.errors.length - 20} error(es) más</li>` : "";
        q("#upload-result").innerHTML = `
          <div class="rounded-xl bg-red-50 border border-red-200 p-3 text-xs text-red-700 space-y-1">
            <p class="font-bold">⚠ ${esc(detail.message || "Errores de importación")}</p>
            <ul class="list-disc pl-4 space-y-0.5">${list}${more}</ul>
          </div>`;
      } else {
        q("#upload-result").innerHTML =
          `<div class="rounded-xl bg-red-50 border border-red-200 p-3 text-xs font-bold text-red-700">⚠ ${esc(err.message)}</div>`;
      }
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "⬆ Procesar archivo";
    }
  }

  async function deleteRace(id) {
    if (!confirm("¿Eliminar esta entrada de la cartelera?")) return;
    try {
      await API.del(`/admin/races/${id}`);
      toast("Entrada eliminada.");
      await loadRaces();
    } catch (err) { toast(err.message, "err"); }
  }

  /* ══════════════ 3. Resolver duelos ══════════════ */
  function predictedWinner(duel) {
    if (duel.logic_rule === "LOWEST_HORSE_NUMBER") return Math.min(duel.horse_creator, duel.horse_opponent);
    if (duel.logic_rule === "HIGHEST_HORSE_NUMBER") return Math.max(duel.horse_creator, duel.horse_opponent);
    return null;
  }

  function duelSideSummary(d) {
    return `N.º ${d.horse_creator} vs N.º ${d.horse_opponent}`;
  }

  function officialOutcomeClient(posMap, duel) {
    const pa = posMap[duel.horse_creator];
    const pb = posMap[duel.horse_opponent];
    if (pa && pb) {
      if (pa < pb) {
        return {
          winner: duel.horse_creator,
          note: `N.º ${duel.horse_creator} llegó ${pa}° y N.º ${duel.horse_opponent} ${pb}°.`,
        };
      }
      return {
        winner: duel.horse_opponent,
        note: `N.º ${duel.horse_opponent} llegó ${pb}° y N.º ${duel.horse_creator} ${pa}°.`,
      };
    }
    if (pa) return { winner: duel.horse_creator, note: `N.º ${duel.horse_opponent} quedó fuera del top 5 (no clasificado).` };
    if (pb) return { winner: duel.horse_opponent, note: `N.º ${duel.horse_creator} quedó fuera del top 5 (no clasificado).` };
    return { winner: null, note: "Ninguno clasificó en el top 5 → reembolso sin comisión." };
  }

  function resolveCard(duel, officialByRace = {}) {
    const pot = Math.round(duel.stake * 2 * 100) / 100;
    const commission = Math.round(pot * 0.05 * 100) / 100;
    const payout = Math.round((pot - commission) * 100) / 100;
    const isTie = duel.logic_rule === "TIE_REFUND";
    const isOfficialRule = duel.logic_rule === "OFFICIAL_FINISH";
    const isNumericRule =
      duel.logic_rule === "LOWEST_HORSE_NUMBER" || duel.logic_rule === "HIGHEST_HORSE_NUMBER";
    const predicted = predictedWinner(duel);

    const official = officialByRace[duel.race_number] || null;
    const posMap = official
      ? Object.fromEntries(official.map((o) => [o.horse_number, o.position]))
      : null;
    const suggestion = posMap ? officialOutcomeClient(posMap, duel) : null;
    const officialLine = official
      ? `<p class="text-[11px] text-slate-600 my-1">🏁 Marcador oficial: ${official
          .map((o) => `${o.position}° N.º ${o.horse_number}`)
          .join(" · ")}</p>`
      : "";

    let winnerField;
    if (isOfficialRule) {
      if (!official) {
        winnerField = `<p class="text-xs font-bold text-red-600">⛔ Sin marcador oficial: registra el 1° al 5° lugar de la carrera ${duel.race_number} en «Resultados oficiales».</p>`;
      } else if (suggestion.winner) {
        winnerField = `<p class="text-xs font-bold text-emerald-700">🏆 Según el marcador oficial gana el caballo N.º ${suggestion.winner}. ${esc(suggestion.note)}</p>`;
      } else {
        winnerField = `<p class="text-xs font-bold text-amber-700">⚠ ${esc(suggestion.note)}</p>`;
      }
    } else if (isTie) {
      winnerField = '<p class="text-xs text-slate-500">Regla de empate: al resolver se reembolsa el 100 % a ambos, sin comisión.</p>';
    } else {
      const preselect = !isNumericRule && suggestion && suggestion.winner ? suggestion.winner : predicted;
      winnerField = `
      <div>
        <label class="label" for="winner-${duel.id}">Caballo ganador oficial</label>
        <select id="winner-${duel.id}" class="select" data-winner-for="${duel.id}">
          <option value="${duel.horse_creator}" ${preselect === duel.horse_creator ? "selected" : ""}>
            N.º ${duel.horse_creator} — ${esc(duel.horse_creator_name)}
          </option>
          <option value="${duel.horse_opponent}" ${preselect === duel.horse_opponent ? "selected" : ""}>
            N.º ${duel.horse_opponent} — ${esc(duel.horse_opponent_name)}
          </option>
        </select>
        ${!suggestion && predicted !== null ? `<p class="text-[11px] text-emerald-700 font-bold mt-1">⚙ La regla calcula el ganador: N.º ${predicted}</p>` : ""}
        ${suggestion ? `<p class="text-[11px] text-slate-500 mt-1">💡 ${esc(suggestion.note)}</p>` : ""}
      </div>`;
    }

    const resolveDisabled = isOfficialRule && !official;
    let resolveLabel = isTie
      ? "Declarar empate y reembolsar"
      : `Resolver · pagar ${fmt(payout)} al ganador`;
    if (isOfficialRule && official && suggestion && !suggestion.winner) {
      resolveLabel = "Reembolsar · ambos fuera del top 5";
    }

    return `
    <article class="card">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-bold text-sm text-slate-900">Duelo #${duel.id} · ${esc(duel.duel_type_name)}</p>
          <p class="text-[11px] text-slate-500">Carrera ${duel.race_number} · ${esc(RULE_LABEL[duel.logic_rule] || duel.logic_rule)}</p>
        </div>
        ${badge(duel.status)}
      </div>
      ${officialLine}
      <p class="text-xs text-slate-700 my-2">
        <b>N.º ${duel.horse_creator} ${esc(duel.horse_creator_name)}</b> (${esc(duel.creator_username)})
        vs <b>N.º ${duel.horse_opponent} ${esc(duel.horse_opponent_name)}</b> (${esc(duel.acceptor_username || "—")})
      </p>
      <div class="rounded-xl bg-slate-50 border border-slate-200 p-2 text-xs grid grid-cols-3 gap-1 text-center mb-3">
        <div><p class="text-slate-400 uppercase text-[9px]">Stake</p><b class="money">${fmt(duel.stake)}</b></div>
        <div><p class="text-slate-400 uppercase text-[9px]">Pozo</p><b class="money">${fmt(pot)}</b></div>
        <div><p class="text-slate-400 uppercase text-[9px]">Comisión 5 %</p><b class="money">${fmt(commission)}</b></div>
      </div>
      <div class="space-y-2">
        ${winnerField}
        <div>
          <label class="label" for="note-${duel.id}">Nota de resolución (opcional)</label>
          <input id="note-${duel.id}" class="input" data-note-for="${duel.id}" placeholder="Ej. Resultado oficial de la carrera" />
        </div>
        <button class="btn btn-primary" data-action="resolve-duel" data-id="${duel.id}" ${resolveDisabled ? "disabled" : ""}>
          ✅ ${resolveLabel}
        </button>
      </div>
    </article>`;
  }

  async function loadResolve() {
    const [active, open, resolved] = await Promise.all([
      API.get("/admin/duels?status=ACTIVE"),
      API.get("/admin/duels?status=OPEN"),
      API.get("/admin/duels?status=RESOLVED"),
    ]);

    const officialByRace = {};
    const raceNumbers = [...new Set(active.map((d) => d.race_number))];
    await Promise.all(
      raceNumbers.map(async (n) => {
        try {
          const data = await API.get(`/admin/races/${n}/official-results`);
          if (data.results && data.results.length) officialByRace[n] = data.results;
        } catch (_) { /* carrera sin marcador o no disponible */ }
      })
    );

    q("#resolve-list").innerHTML = active.length
      ? active.map((d) => resolveCard(d, officialByRace)).join("")
      : emptyState("No hay duelos activos pendientes de resolución.");

    q("#resolve-open-list").innerHTML = open.length
      ? open.map((d) => `
        <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100">
          <span>#${d.id} · Carrera ${d.race_number} · ${esc(duelSideSummary(d))}</span>
          <b class="money">${fmt(d.stake)}</b>
        </div>`).join("")
      : '<p class="text-xs text-slate-400">Sin duelos abiertos.</p>';

    q("#resolve-resolved-list").innerHTML = resolved.length
      ? resolved.map((d) => `
        <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100">
          <span>#${d.id} · ${esc(d.winner_username || "Empate/reembolso")} · <span class="text-emerald-700">comisión ${fmt(d.commission_amount)}</span></span>
          <b class="money">${fmt(d.pot)}</b>
        </div>`).join("")
      : '<p class="text-xs text-slate-400">Aún no hay duelos resueltos.</p>';
  }

  async function resolveDuel(id, btn) {
    const inOfficial = btn.closest && btn.closest("#official-status");
    const winnerSel = inOfficial ? null : document.querySelector(`[data-winner-for="${id}"]`);
    const noteEl = inOfficial ? null : document.querySelector(`[data-note-for="${id}"]`);
    const body = {};
    if (winnerSel) body.winner_horse_number = Number(winnerSel.value);
    if (noteEl && noteEl.value.trim()) body.note = noteEl.value.trim();

    btn.disabled = true;
    try {
      const res = await API.post(`/admin/duels/${id}/resolve`, body);
      if (res.commission > 0) {
        toast(`Duelo #${id} resuelto ✓ Pozo ${fmt(res.pot)} → comisión ${fmt(res.commission)}, ganador ${fmt(res.payout)}.`);
      } else {
        toast(`Duelo #${id} resuelto ✓ Reembolso sin comisión (escrow devuelto).`);
      }
      await Promise.all([loadResolve(), refreshMe()]);
      if (App.view === "admin-results") await loadOfficialResults();
    } catch (err) {
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }

  /* ══════════════ 4. Recargas y retiros ══════════════ */
  async function loadRequests() {
    const [topups, withdrawals] = await Promise.all([
      API.get(`/admin/topups?status=${filters.topups}`),
      API.get(`/admin/withdrawals?status=${filters.withdrawals}`),
    ]);

    q("#topups-admin-list").innerHTML = topups.length
      ? topups.map((r) => `
        <article class="card card-tight">
          <div class="flex justify-between items-start gap-2">
            <div class="text-xs min-w-0">
              <p class="font-bold text-sm text-slate-900">${esc(r.username)} · <span class="money">${fmt(r.amount)}</span></p>
              <p class="text-slate-500">Ref ${esc(r.reference)} · desde ${esc(r.wallet_phone)}</p>
              <p class="text-slate-400">${esc(r.created_at || "")}</p>
            </div>
            ${badge(r.status)}
          </div>
          ${r.status === "PENDING" ? `
          <div class="grid grid-cols-2 gap-2 mt-2">
            <button class="btn btn-primary btn-sm" data-action="approve-topup" data-id="${r.id}">✓ Aprobar y abonar</button>
            <button class="btn btn-danger btn-sm" data-action="reject-topup" data-id="${r.id}">✕ Rechazar</button>
          </div>` : ""}
        </article>`).join("")
      : emptyState("Sin recargas para este filtro.");

    q("#withdrawals-admin-list").innerHTML = withdrawals.length
      ? withdrawals.map((r) => `
        <article class="card card-tight">
          <div class="flex justify-between items-start gap-2">
            <div class="text-xs min-w-0">
              <p class="font-bold text-sm text-slate-900">${esc(r.username)} · <span class="money">${fmt(r.amount)}</span></p>
              <p class="text-slate-500">Destino ${esc(r.destination_phone)}</p>
              <p class="text-slate-400">${esc(r.created_at || "")}</p>
            </div>
            ${badge(r.status)}
          </div>
          ${r.status === "PENDING" ? `
          <div class="grid grid-cols-2 gap-2 mt-2">
            <button class="btn btn-primary btn-sm" data-action="pay-withdrawal" data-id="${r.id}">✓ Marcar pagado</button>
            <button class="btn btn-danger btn-sm" data-action="reject-withdrawal" data-id="${r.id}">✕ Rechazar (reembolsar)</button>
          </div>` : ""}
        </article>`).join("")
      : emptyState("Sin retiros para este filtro.");
  }

  async function reloadRequests() { await loadRequests(); }

  /* ══════════════ 5. Banco ══════════════ */
  async function loadBank() {
    const bank = await API.get("/bank").catch(() => null);
    if (bank) {
      q("#bank-name").value = bank.bank_name || "";
      q("#bank-phone").value = bank.phone || "";
      q("#bank-id").value = bank.id_number || "";
      q("#bank-type").value = bank.account_type || "";
      q("#bank-holder").value = bank.holder_name || "";
    }
  }

  async function saveBank() {
    try {
      await API.put("/admin/bank", {
        bank_name: q("#bank-name").value.trim(),
        phone: q("#bank-phone").value.trim(),
        id_number: q("#bank-id").value.trim(),
        account_type: q("#bank-type").value.trim(),
        holder_name: q("#bank-holder").value.trim(),
      });
      toast("Datos bancarios guardados ✓");
    } catch (err) { toast(err.message, "err"); }
  }

  /* ══════════════ 6. Auditoría ══════════════ */
  async function loadAudit() {
    const [audit, users] = await Promise.all([
      API.get("/admin/audit"),
      API.get("/admin/users"),
    ]);

    q("#audit-kpis").innerHTML = [
      kpi("Usuarios", audit.users.count, `Balances: ${fmt(audit.users.total_balance)}`),
      kpi("Duelos resueltos", audit.duels.resolved, `Volumen: ${fmt(audit.duels.resolved_volume)}`),
      kpi("Comisiones 5 %", fmt(audit.duels.commissions), `Pagado a ganadores: ${fmt(audit.duels.payouts_to_winners)}`),
      kpi("Escrow retenido", fmt(audit.escrow.total_held), `Abiertos ${fmt(audit.escrow.held_open)} · Activos ${fmt(audit.escrow.held_active)}`),
      kpi("Recargas aprobadas", fmt(audit.payments.topups_approved_volume), `Pendientes: ${fmt(audit.payments.topups_pending_volume)}`),
      kpi("Retiros pagados", fmt(audit.payments.withdrawals_paid_volume), `Pendientes: ${fmt(audit.payments.withdrawals_pending_volume)}`),
    ].join("");

    q("#audit-commissions").innerHTML = `
      <div class="flex justify-between"><span class="text-slate-500">Duelos abiertos / activos / resueltos</span><b>${audit.duels.open} / ${audit.duels.active} / ${audit.duels.resolved}</b></div>
      <div class="flex justify-between"><span class="text-slate-500">Volumen resuelto (pozos)</span><b class="money">${fmt(audit.duels.resolved_volume)}</b></div>
      <div class="flex justify-between text-emerald-700"><span>Comisión retenida (5 %)</span><b class="money">${fmt(audit.duels.commissions)}</b></div>
      <div class="flex justify-between"><span class="text-slate-500">Abonado a ganadores (95 %)</span><b class="money">${fmt(audit.duels.payouts_to_winners)}</b></div>`;

    q("#audit-users-list").innerHTML = users.length
      ? users.map((u) => `
        <div class="card card-tight flex items-center justify-between text-sm">
          <div>
            <p class="font-bold text-slate-900">${esc(u.username)}</p>
            <p class="text-[11px] text-slate-400">${u.role === "admin" ? "Administrador" : "Usuario"} · #${u.id}</p>
          </div>
          <b class="money text-emerald-700">${fmt(u.balance)}</b>
        </div>`).join("")
      : emptyState("No hay cuentas registradas.");
  }

  /* ══════════════ 7. Resultados oficiales (1° al 5°) ══════════════ */
  let officialRacesCache = [];

  function officialHorseOptions(raceNumber) {
    return officialRacesCache
      .filter((r) => r.race_number === Number(raceNumber))
      .map((h) => `<option value="${h.horse_number}">N.º ${h.horse_number} — ${esc(h.horse_name)}</option>`)
      .join("");
  }

  async function loadOfficialResults() {
    officialRacesCache = await API.get("/races");
    const sel = q("#official-race-select");
    const previous = sel.value;
    const raceNumbers = [...new Set(officialRacesCache.map((r) => r.race_number))]
      .sort((a, b) => a - b);
    sel.innerHTML = raceNumbers.length
      ? raceNumbers.map((n) => {
          const first = officialRacesCache.find((r) => r.race_number === n);
          return `<option value="${n}">Carrera ${n} · ${esc(first.race_datetime || "")}</option>`;
        }).join("")
      : '<option value="">La cartelera está vacía</option>';
    if (previous && raceNumbers.includes(Number(previous))) sel.value = previous;
    await refreshOfficialDetail();
  }

  async function refreshOfficialDetail() {
    const raceNumber = Number(q("#official-race-select").value);
    const statusEl = q("#official-status");
    if (!raceNumber) {
      statusEl.innerHTML = emptyState("Selecciona una carrera con cartelera cargada.");
      return;
    }

    const options = officialHorseOptions(raceNumber);
    [1, 2, 3, 4, 5].forEach((p) => { q(`#official-horse${p}`).innerHTML = options; });

    let data = null;
    try {
      data = await API.get(`/admin/races/${raceNumber}/official-results`);
    } catch (err) {
      statusEl.innerHTML = `<div class="card text-center text-sm text-red-600">⚠ ${esc(err.message)}</div>`;
      return;
    }

    (data.results || []).forEach((r) => {
      const select = q(`#official-horse${r.position}`);
      if (select && Array.from(select.options).some((o) => Number(o.value) === r.horse_number)) {
        select.value = String(r.horse_number);
      }
    });

    const markerCard = data.has_results
      ? `<div class="card">
          <div class="flex items-center justify-between mb-2">
            <p class="font-bold text-sm text-slate-900">🏁 Marcador guardado — Carrera ${data.race_number}</p>
            <span class="badge badge-resolved">1° al 5° registrados</span>
          </div>
          <ol class="text-sm space-y-1">
            ${data.results.map((r) => `<li><b>${r.position}°</b> — N.º ${r.horse_number} ·${esc(r.horse_name)}</li>`).join("")}
          </ol>
          <p class="text-[11px] text-slate-500 mt-2">
            Cualquier caballo fuera de esta lista quedó <b>fuera del marcador (no clasificado / perdedor)</b>.
          </p>
        </div>`
      : `<div class="card text-center text-sm text-slate-500">
          ⚠ Sin marcador oficial registrado para la carrera ${data.race_number}.
          Completa los 5 lugares y guarda.
        </div>`;

    const duelsHtml = (data.active_duels || []).length
      ? data.active_duels.map((d) => officialDuelCard(d)).join("")
      : emptyState("No hay duelos activos en esta carrera.");

    statusEl.innerHTML = `${markerCard}
      <div>
        <h3 class="font-bold text-slate-900 text-sm mb-2">Duelos activos de la carrera</h3>
        <div class="space-y-2">${duelsHtml}</div>
      </div>`;
  }

  function officialDuelCard(d) {
    const isNumeric = d.logic_rule === "LOWEST_HORSE_NUMBER" || d.logic_rule === "HIGHEST_HORSE_NUMBER";
    let action = "";
    if (d.has_results) {
      if (isNumeric) {
        action = `<button class="btn btn-ghost btn-sm" data-action="resolve-duel" data-id="${d.duel_id}">
          ✅ Resolver por regla numérica
        </button>`;
      } else if (d.suggested_winner_horse) {
        action = `<button class="btn btn-primary btn-sm" data-action="resolve-duel" data-id="${d.duel_id}">
          ✅ Resolver · gana N.º ${d.suggested_winner_horse}
        </button>`;
      } else if (d.logic_rule === "TIE_REFUND") {
        action = `<button class="btn btn-warn btn-sm" data-action="resolve-duel" data-id="${d.duel_id}">
          ↩ Reembolsar (empate)
        </button>`;
      } else {
        action = `<button class="btn btn-warn btn-sm" data-action="resolve-duel" data-id="${d.duel_id}">
          ↩ Reembolsar · ambos fuera del top 5
        </button>`;
      }
    }
    const noteClass = d.suggested_winner_horse ? "text-emerald-700 font-bold" : "text-slate-500";
    return `
    <article class="card card-tight">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="font-bold text-sm text-slate-900">Duelo #${d.duel_id} · ${esc(d.duel_type)}</p>
          <p class="text-[11px] text-slate-500">${esc(RULE_LABEL[d.logic_rule] || d.logic_rule)} · Pozo ${fmt(d.pot)}</p>
        </div>
        <span class="badge badge-active">Activo</span>
      </div>
      <p class="text-xs text-slate-700 my-2">
        <b>N.º ${d.horse_creator} ${esc(d.horse_creator_name)}</b> (${esc(d.creator_username)})
        vs <b>N.º ${d.horse_opponent} ${esc(d.horse_opponent_name)}</b> (${esc(d.acceptor_username || "—")})
      </p>
      <p class="text-xs ${noteClass}">💡 ${esc(d.note)}</p>
      ${action ? `<div class="mt-2">${action}</div>` : ""}
    </article>`;
  }

     async function saveOfficialResults() {
     const raceNumber = Number(q("#official-race-select").value);
     if (!raceNumber) { toast("Selecciona una carrera.", "err"); return; }
     
     const positions = [];
     for (let i = 1; i <= 5; i++) {
       const horse = Number(q(`#official-horse${i}`).value);
       const pos = Number(q(`#official-pos${i}`).value);
       if (!horse || !pos) {
         toast("Seleccione un caballo y una posición para cada fila.", "err");
         return;
       }
       positions.push({ position: pos, horse_number: horse });
     }
     
     // Se permiten empates: se eliminó la validación de caballo distinto por lugar.
     
     try {
       const res = await API.post(`/admin/races/${raceNumber}/official-results`, { positions });
       toast(`${res.detail} · Duelos activos: ${res.active_duels.length}.`);
       await Promise.all([refreshOfficialDetail(), loadResolve()]);
     } catch (err) {
       toast(err.message, "err");
     }
   }


  function switchRequestTab(which) {
    const topups = which === "topups";
    q("#panel-topups").classList.toggle("hidden", !topups);
    q("#panel-withdrawals").classList.toggle("hidden", topups);
    q("#tab-topups").classList.toggle("bg-white", topups);
    q("#tab-topups").classList.toggle("shadow", topups);
    q("#tab-topups").classList.toggle("text-slate-500", !topups);
    q("#tab-withdrawals").classList.toggle("bg-white", !topups);
    q("#tab-withdrawals").classList.toggle("shadow", !topups);
    q("#tab-withdrawals").classList.toggle("text-slate-500", topups);
    loadRequests().catch((e) => toast(e.message, "err"));
  }

  /* ══════════════ Enlaces de eventos ══════════════ */
  function bind() {
    // CRUD de tipos de duelo.
    q("#duel-type-form").addEventListener("submit", (e) => { e.preventDefault(); saveDuelType(); });
    q("#duel-type-cancel-btn").addEventListener("click", resetDuelTypeForm);

    // Cartelera.
    const uploadBtn = document.getElementById("upload-race-btn");
    if (uploadBtn) uploadBtn.onclick = () => uploadRaces();
    q("#refresh-races").addEventListener("click", () => loadRaces().catch((e) => toast(e.message, "err")));

    // Resolver y auditoría.
    q("#refresh-resolve").addEventListener("click", () => loadResolve().catch((e) => toast(e.message, "err")));
    q("#refresh-audit").addEventListener("click", () => loadAudit().catch((e) => toast(e.message, "err")));

    // Banco.
    q("#bank-form").addEventListener("submit", (e) => { e.preventDefault(); saveBank(); });

    // Resultados oficiales (1° al 5° lugar).
    q("#official-form").addEventListener("submit", (e) => {
      e.preventDefault();
      saveOfficialResults();
    });
    q("#official-race-select").addEventListener("change", () => {
      refreshOfficialDetail().catch((e) => toast(e.message, "err"));
    });
    q("#refresh-official").addEventListener("click", () => {
      loadOfficialResults().catch((e) => toast(e.message, "err"));
    });

    // Pestañas y filtros de recargas/retiros.
    q("#tab-topups").addEventListener("click", () => switchRequestTab("topups"));
    q("#tab-withdrawals").addEventListener("click", () => switchRequestTab("withdrawals"));
    document.querySelectorAll(".req-filter").forEach((btn) => {
      btn.addEventListener("click", () => {
        filters[btn.dataset.kind] = btn.dataset.status;
        document.querySelectorAll(`.req-filter[data-kind="${btn.dataset.kind}"]`)
          .forEach((b) => b.classList.toggle("active", b === btn));
        loadRequests().catch((e) => toast(e.message, "err"));
      });
    });

    // Delegación de acciones exclusivas del administrador.
    document.addEventListener("click", async (event) => {
      const el = event.target.closest("[data-action]");
      if (!el || !guard()) return;
      const action = el.dataset.action;
      const id = Number(el.dataset.id);
      const adminActions = [
        "edit-duel-type", "delete-duel-type", "delete-race", "resolve-duel",
        "approve-topup", "reject-topup", "pay-withdrawal", "reject-withdrawal"
      ];

      if (!adminActions.includes(action)) return;

      try {
        if (action === "edit-duel-type") editDuelType(id);
        else if (action === "delete-duel-type") await deleteDuelType(id);
        else if (action === "delete-race") await deleteRace(id);
        else if (action === "resolve-duel") await resolveDuel(id, el);
        else if (action === "approve-topup") {
          await API.post(`/admin/topups/${id}/approve`, {});
          toast("Recarga aprobada ✓");
          await loadRequests();
        } else if (action === "reject-topup") {
          await API.post(`/admin/topups/${id}/reject`, {});
          toast("Recarga rechazada.");
          await loadRequests();
        } else if (action === "pay-withdrawal") {
          await API.post(`/admin/withdrawals/${id}/pay`, {});
          toast("Retiro marcado como pagado ✓");
          await loadRequests();
        } else if (action === "reject-withdrawal") {
          await API.post(`/admin/withdrawals/${id}/reject`, {});
          toast("Retiro rechazado y fondos devueltos.");
          await loadRequests();
        }
      } catch (err) {
        toast(err.message, "err");
      }
    });
  }

  // ══════════════ Exportación pública del módulo ══════════════
  const publicApi = {
    bind,
    loadDuelTypes,
    loadRaces,
    uploadRaces,
    loadResolve,
    loadRequests,
    loadBank,
    loadAudit,
    loadOfficialResults
  };
  window.Admin = publicApi;
  return publicApi;
})();