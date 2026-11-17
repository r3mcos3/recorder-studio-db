import { LitElement, html, css, nothing, repeat, classMap } from "./vendor/lit.js";

/* ---------- small helpers ---------- */
const ICONS = {
  database: "M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.59 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4m0 2c3.87 0 6 1.5 6 2s-2.13 2-6 2-6-1.5-6-2 2.13-2 6-2m6 12c0 .5-2.13 2-6 2s-6-1.5-6-2v-2.23C7.61 15.55 9.72 16 12 16s4.39-.45 6-1.23z",
  list: "M3 13h2v-2H3zm0 4h2v-2H3zm0-8h2V7H3zm4 4h14v-2H7zm0 4h14v-2H7zM7 7v2h14V7z",
  broom: "M19.36 2.72l1.42 1.42-5.72 5.71c1.07 1.54 1.22 3.39.32 4.59L9.06 8.12c1.2-.9 3.05-.75 4.59.32zM5.93 17.57c-2.01-2.01-3.24-4.41-3.58-6.65l4.88-2.09 7.44 7.44-2.09 4.88c-2.24-.34-4.64-1.57-6.65-3.58",
  link: "M10.59 13.41c.41.39.41 1.03 0 1.42-.39.39-1.03.39-1.42 0a5.003 5.003 0 0 1 0-7.07l3.54-3.54a5.003 5.003 0 0 1 7.07 0 5.003 5.003 0 0 1 0 7.07l-1.49 1.49c.01-.82-.12-1.64-.4-2.42l.47-.48a2.982 2.982 0 0 0 0-4.24 2.982 2.982 0 0 0-4.24 0l-3.53 3.53a2.982 2.982 0 0 0 0 4.24m2.82-4.24c.39-.39 1.03-.39 1.42 0a5.003 5.003 0 0 1 0 7.07l-3.54 3.54a5.003 5.003 0 0 1-7.07 0 5.003 5.003 0 0 1 0-7.07l1.49-1.49c-.01.82.12 1.64.4 2.43l-.47.47a2.982 2.982 0 0 0 0 4.24 2.982 2.982 0 0 0 4.24 0l3.53-3.53a2.982 2.982 0 0 0 0-4.24.973.973 0 0 1 0-1.42",
  cog: "M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97s-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1a.5.5 0 0 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1s.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64z",
  swap: "M21 9l-4-4v3H3v2h14v3M7 11l-4 4 4 4v-3h14v-2H7z",
  chevron: "M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z",
  search: "M9.5 3A6.5 6.5 0 0 1 16 9.5c0 1.61-.59 3.09-1.56 4.23l.27.27h.79l5 5-1.5 1.5-5-5v-.79l-.27-.27A6.52 6.52 0 0 1 9.5 16 6.5 6.5 0 0 1 3 9.5 6.5 6.5 0 0 1 9.5 3m0 2C7 5 5 7 5 9.5S7 14 9.5 14 14 12 14 9.5 12 5 9.5 5",
  refresh: "M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 0 0-8 8 8 8 0 0 0 8 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18a6 6 0 0 1-6-6 6 6 0 0 1 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4z",
  trash: "M19 4h-3.5l-1-1h-5l-1 1H5v2h14M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6z",
  warn: "M13 14h-2V9h2m0 9h-2v-2h2M1 21h22L12 2z",
  check: "M21 7L9 19l-5.5-5.5 1.41-1.41L9 16.17 19.59 5.59z",
  power: "M16.56 5.44l-1.45 1.45A5.97 5.97 0 0 1 18 12a6 6 0 0 1-6 6 6 6 0 0 1-6-6c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.96 7.96 0 0 0 4 12a8 8 0 0 0 8 8 8 8 0 0 0 8-8c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
};
const icon = (name, size = 20) =>
  html`<svg viewBox="0 0 24 24" width=${size} height=${size} aria-hidden="true"><path fill="currentColor" d=${ICONS[name]}></path></svg>`;

const fmtNum = (n) => new Intl.NumberFormat().format(n ?? 0);
const fmtBytes = (b) => {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), u.length - 1);
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
};
const fmtPct = (p) => (!p ? "–" : p < 0.1 ? "<0.1%" : `${p < 10 ? p.toFixed(1) : Math.round(p)}%`);
const ago = (iso) => {
  if (!iso) return "never";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
};

const fmtDay = (d) => (d == null ? "" : d >= 365 ? "over a year" : d >= 60 ? `${Math.round(d / 30)} months` : d === 1 ? "1 day" : `${d} days`);
const ALERT_NAMES = { disk_low: "Disk space is low", disk_filling: "The database is filling the disk", db_growth: "The database is growing fast" };

const TABS = [
  ["overview", "Overview", "database"],
  ["entities", "Entities", "list"],
  ["maintenance", "Maintenance", "broom"],
  ["orphans", "Orphans", "link"],
  ["migration", "Migration", "swap"],
  ["settings", "Settings", "cog"],
];

class RecorderStudioPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    _tab: { state: true },
    _data: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _busy: { state: true },
    _search: { state: true },
    _domain: { state: true },
    _status: { state: true },
    _sort: { state: true },
    _open: { state: true },
    _pending: { state: true },
    _dialog: { state: true },
    _toast: { state: true },
    _form: { state: true },
    _migration: { state: true },
    _sources: { state: true },
    _paste: { state: true },
    _filePath: { state: true },
    _merge: { state: true },
    _topBy: { state: true },
    _alertForm: { state: true },
  };

  constructor() {
    super();
    this._tab = "overview";
    this._data = null;
    this._loading = true;
    this._search = "";
    this._domain = "";
    this._status = "all";
    this._sort = "name";
    this._open = new Set();
    this._pending = new Map();
    this._dialog = null;
    this._toast = null;
    this._form = null;
    this._migration = null;
    this._sources = null;
    this._paste = "";
    this._filePath = "";
    this._merge = false;
    this._topBy = "records";
    this._alertForm = null;
    this._started = false;
    this._lastFull = 0;
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._started) {
      this._started = true;
      this._start();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopped = true;
    clearTimeout(this._liveTimer);
  }

  connectedCallback() {
    super.connectedCallback();
    if (this._started && this._stopped) {
      this._stopped = false;
      this._live();
    }
  }

  async _start() {
    await this._refresh();
    this._live();
  }

  /**
   * Keeps the data live: every cycle runs a cheap analysis (record counts) and reloads the state; the expensive
   * per-table sizes are refreshed every 10 minutes. It pauses while the tab is hidden, while an action is running or
   * a dialog is open, and slows down by itself when an analysis takes long.
   */
  async _live() {
    clearTimeout(this._liveTimer);
    if (this._stopped) return;
    let delay = 30000;
    const idle = document.visibilityState === "visible" && !this._busy && !this._dialog;
    if (idle && this._data?.sqlite !== false) {
      const t0 = Date.now();
      try {
        const needFull = Date.now() - this._lastFull > 600000;
        await this._ws("analyze", { light: !needFull });
        if (needFull) this._lastFull = Date.now();
        await this._refresh({ silent: true });
      } catch (err) {
        /* transient (restart, reconnect): try again next cycle */
      }
      delay = Math.max(30000, (Date.now() - t0) * 10);
    } else if (idle) {
      await this._refresh({ silent: true });
    }
    this._liveTimer = setTimeout(() => this._live(), delay);
  }

  /* ---------- data ---------- */
  async _ws(type, payload = {}) {
    return this.hass.connection.sendMessagePromise({ type: `recorder_studio/${type}`, ...payload });
  }

  async _refresh({ silent = false } = {}) {
    if (!silent) this._loading = true;
    try {
      this._data = await this._ws("get_state");
      this._error = null;
      if (!silent || !this._form) {
        // a silent (background) refresh must not overwrite what the user is typing in Settings
        const o = this._data.options;
        this._form = { ...o, rules_text: this._data.rules_text };
        const a = this._data.alerts;
        this._alertForm = { enabled: a.enabled, free_percent: a.free_percent, growth_percent: a.growth_percent };
      }
    } catch (err) {
      if (!silent) this._error = err?.message || String(err);
    }
    this._loading = false;
  }

  async _run(label, fn, { success } = {}) {
    this._busy = label;
    try {
      const res = await fn();
      if (success) this._notify(typeof success === "function" ? success(res) : success);
      return res;
    } catch (err) {
      this._notify(err?.message || String(err), "error");
      return undefined;
    } finally {
      this._busy = null;
    }
  }

  _notify(text, kind = "ok") {
    this._toast = { text, kind };
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (this._toast = null), 5000);
  }

  get _ro() {
    return !!this._data?.read_only;
  }
  get _summary() {
    return this._data?.summary;
  }
  get _entities() {
    return (this._data?.tree || []).flatMap((d) => d.entities.map((e) => ({ ...e, device: d.name })));
  }
  _isRecorded(e) {
    return this._pending.has(e.entity_id) ? this._pending.get(e.entity_id) : e.recorded;
  }

  /* ---------- actions ---------- */
  _toggle(ids, recorded) {
    const next = new Map(this._pending);
    const byId = new Map(this._entities.map((e) => [e.entity_id, e]));
    for (const id of ids) {
      if (byId.get(id)?.recorded === recorded) next.delete(id);
      else next.set(id, recorded);
    }
    this._pending = next;
  }

  async _savePending() {
    const on = [...this._pending].filter(([, v]) => v).map(([k]) => k);
    const off = [...this._pending].filter(([, v]) => !v).map(([k]) => k);
    await this._run(
      "save",
      async () => {
        if (on.length) await this._ws("set_recorded", { entity_ids: on, recorded: true });
        if (off.length) await this._ws("set_recorded", { entity_ids: off, recorded: false });
        this._pending = new Map();
        await this._refresh();
      },
      { success: `Saved ${on.length + off.length} change(s). Restart Home Assistant to apply.` }
    );
  }

  async _dismiss(ids, reset = false) {
    await this._run(
      "dismiss",
      async () => {
        await this._ws("dismiss_suggestions", { entity_ids: ids, reset });
        await this._refresh({ silent: true });
      },
      { success: reset ? "Dismissed suggestions are shown again." : "Suggestion hidden." }
    );
  }

  async _saveAlerts() {
    await this._run(
      "alerts",
      async () => {
        await this._ws("save_alerts", { ...this._alertForm });
        await this._refresh();
      },
      { success: "Alert settings saved. They apply immediately, no restart needed." }
    );
  }

  async _analyze() {
    await this._run(
      "analyze",
      async () => {
        await this._ws("analyze");
        this._lastFull = Date.now();
        await this._refresh();
      },
      { success: "Database analysed." }
    );
  }

  /**
   * The recorder runs a purge as a queued task that can take a minute on a large database, so analyse repeatedly
   * until the expected number of records is gone (or, without an expectation, the count changed and settled).
   * Returns true when the purge was seen to finish, false on timeout.
   */
  async _followUp(expected = 0) {
    const start = this._summary?.total_records ?? null;
    let last = start;
    let changed = false;
    const deadline = Date.now() + 150000;
    let wait = 2000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, wait));
      wait = 5000;
      await this._ws("analyze", { light: true });
      await this._refresh({ silent: true });
      const now = this._summary?.total_records ?? null;
      if (expected > 0 && start !== null && now !== null && start - now >= expected * 0.98) return true;
      if (expected === 0 && changed && now === last) return true;
      if (now !== last) changed = true;
      last = now;
    }
    return false;
  }

  /** How fresh is the newest Home Assistant backup? Shown in purge dialogs; never blocks anything. */
  async _backupNote() {
    let b;
    try {
      b = await this._ws("backup_status");
    } catch (err) {
      b = { known: false };
    }
    if (!b.known) return { tone: "warn", text: "Could not check whether a backup exists. Make sure you have a recent one: a purge cannot be undone." };
    if (!b.count) return { tone: "warn", text: "No Home Assistant backup was found. Make one first: a purge cannot be undone." };
    if (b.age_hours > 24) return { tone: "warn", text: `Your latest backup is ${ago(b.last)}. Consider making a fresh one first: a purge cannot be undone.` };
    return { tone: "ok", text: `Latest backup: ${ago(b.last)}.` };
  }

  /** Opens a confirmation dialog; `onConfirm` runs only after explicit confirmation. */
  _confirm({ title, body, impact, confirmLabel, phrase, danger = true, warning = null, onConfirm }) {
    this._dialog = { title, body, impact, confirmLabel, phrase, danger, warning, typed: "", onConfirm };
  }

  async _askPurge(kind, entityIds = [], label = "") {
    let impact = null;
    if (kind !== "retention") {
      if (!this._summary) {
        this._notify("Analyse the database first, so the impact of the purge can be shown.", "error");
        return;
      }
      impact = await this._run("preview", () => this._ws("preview_purge", { kind, entity_ids: entityIds }));
      if (!impact) return;
      if (impact.records === 0) {
        this._notify("Nothing to purge: there are no records for the selected entities.");
        return;
      }
    }
    const warning = await this._backupNote();
    const keep = this._data.options.purge_keep_days;
    const byId = new Map(this._entities.map((e) => [e.entity_id, e]));
    const stillRecorded = entityIds.filter((id) => byId.get(id) && this._isRecorded(byId.get(id))).length;
    const live = stillRecorded
      ? ` ${stillRecorded === entityIds.length ? (entityIds.length === 1 ? "This entity is" : "These entities are") : `${stillRecorded} of them are`} still being recorded, so new history starts building up again right away.`
      : "";
    const texts = {
      retention: [`Purge older than ${keep} days`, `All history older than ${keep} days is permanently deleted, for every entity.`],
      excluded: ["Purge excluded entities", "The full history of all currently excluded entities is permanently deleted, regardless of the retention setting."],
      entities: [`Purge ${label || "entities"}`, `The full history of ${entityIds.length === 1 ? "this entity" : `these ${entityIds.length} entities`} is permanently deleted, regardless of the retention setting.${live}`],
    }[kind];
    this._confirm({
      title: texts[0],
      body: texts[1],
      impact: impact && `${fmtNum(impact.entities)} ${impact.entities === 1 ? "entity" : "entities"} · ${fmtNum(impact.records)} records · ≈ ${fmtBytes(impact.approx_bytes)}`,
      confirmLabel: "Purge permanently",
      warning,
      phrase: kind === "entities" && entityIds.length === 1 ? null : "PURGE",
      onConfirm: () =>
        this._run(
          "purge",
          async () => {
            await this._ws("purge", { kind, entity_ids: entityIds, confirm: true, repack: false });
            this._notify("Purge queued. The statistics refresh automatically when it has finished…");
            return this._followUp(impact?.records || 0);
          },
          { success: (done) => (done ? "Purge finished. The statistics are up to date." : "The purge is still running. The statistics update by themselves.") }
        ),
    });
  }

  _askRepack() {
    this._confirm({
      title: "Repack database",
      body: "Rewrites the SQLite file to reclaim disk space. It needs free space of about the database size and can block the recorder for several minutes. Retention is applied at the same time.",
      confirmLabel: "Repack",
      danger: false,
      onConfirm: () => this._run("repack", () => this._ws("repack", { confirm: true }), { success: "Repack queued." }),
    });
  }

  _askRestart() {
    this._confirm({
      title: "Restart Home Assistant",
      body: "Home Assistant validates the configuration first and will refuse to restart on errors. All automations pause for a minute or two.",
      confirmLabel: "Restart now",
      danger: false,
      onConfirm: () => this._run("restart", () => this._ws("restart", { confirm: true }), { success: "Restarting…" }),
    });
  }

  /* ---------- render: shell ---------- */
  render() {
    if (this._loading && !this._data) return html`<div class="center">Loading…</div>`;
    if (this._error && !this._data) return html`<div class="center err">${icon("warn", 32)}<p>${this._error}</p><button class="btn" @click=${this._refresh}>Retry</button></div>`;
    const d = this._data;
    const orphanCount = this._summary?.orphan_exclusions?.length || 0;
    return html`
      <header>
        <div class="title">
          ${icon("database", 26)}
          <h1>Recorder Studio</h1>
          <span class="ver">v${d.version}</span>
        </div>
        ${d.db_files?.total ? html`<span class="chip-size" title="Database file + WAL + SHM">${icon("database", 16)} ${fmtBytes(d.db_files.total)}</span>` : nothing}
        <div class="grow"></div>
      </header>

      ${d.read_only ? html`<div class="banner info">${icon("check")}<span><b>Read-only mode.</b> Statistics and the entity list work; saving, purging, repacking, restarting and migration are disabled.</span></div>` : nothing}
      ${d.sqlite === false ? html`<div class="banner error">${icon("warn")} The recorder does not use SQLite. This integration only supports SQLite.</div>` : nothing}
      ${d.pending_restart && !d.read_only
        ? html`<div class="banner warn">${icon("warn")}<span>Changes are saved to <code>${d.yaml_file}</code> but only apply after a restart.</span>
            <button class="btn small" @click=${this._askRestart}>${icon("power", 16)} Restart</button></div>`
        : nothing}
      ${d.config.state !== "active" && !d.read_only
        ? html`<div class="banner info">${icon("swap")}<span>This file is not active yet: <code>configuration.yaml</code> does not include it.</span>
            <button class="btn small" ?disabled=${!!this._busy} @click=${this._setup}>Set up</button></div>`
        : nothing}

      <nav role="tablist">
        ${TABS.map(
          ([id, label, ic]) => html`<button role="tab" aria-selected=${this._tab === id} class=${classMap({ tab: true, on: this._tab === id })} @click=${() => { this._tab = id; if (id === "migration" && !this._sources) this._loadSources(); }}>
            ${icon(ic, 18)}<span>${label}</span>${id === "orphans" && orphanCount ? html`<b class="badge">${orphanCount}</b>` : nothing}
          </button>`
        )}
      </nav>

      <main>${this._renderTab()}</main>
      ${this._pending.size ? this._renderSaveBar() : nothing}
      ${this._dialog ? this._renderDialog() : nothing}
      ${this._toast ? html`<div class="toast ${this._toast.kind}" role="status">${this._toast.text}</div>` : nothing}
    `;
  }

  _renderTab() {
    return { overview: () => this._tOverview(), entities: () => this._tEntities(), maintenance: () => this._tMaintenance(), orphans: () => this._tOrphans(), migration: () => this._tMigration(), settings: () => this._tSettings() }[this._tab]();
  }

  /* ---------- Overview ---------- */
  _tOverview() {
    const s = this._summary;
    if (!s) {
      return html`<div class="card empty">${icon("database", 40)}<h2>No statistics yet</h2><p>Analyse the database to see record counts and a size breakdown. The analysis is read-only.</p>
        ${this._data.db_files?.total ? html`<p class="size-now"><b>${fmtBytes(this._data.db_files.total)}</b> on disk${this._filesText()}</p>` : nothing}
        <button class="btn primary" @click=${this._analyze} ?disabled=${!!this._busy}>${icon("search", 18)} Analyse database</button></div>`;
    }
    const pct = s.total_records ? Math.round((s.obsolete_records / s.total_records) * 100) : 0;
    const bySize = this._topBy === "size" && s.top_sizes?.length;
    const top = bySize ? s.top_sizes : s.top_entities;
    const max = top[0]?.[1] || 1;
    const excluded = new Set(this._entities.filter((e) => !e.recorded).map((e) => e.entity_id));
    const active = this._data.alerts?.active || [];
    return html`
      ${s.error ? html`<div class="banner error">${icon("warn")} ${s.error}</div>` : nothing}
      ${active.length ? html`<div class="note warn">${icon("warn", 18)}<span><b>Alert:</b> ${active.map((a) => ALERT_NAMES[a] || a).join(" · ")}. Details under Settings &gt; System &gt; Repairs.</span></div>` : nothing}
      <div class="stats">
        ${this._stat("Total records", fmtNum(s.total_records), `${fmtNum(s.entity_count)} entities in database`)}
        ${this._stat("Current", fmtNum(s.current_records), "from recorded entities", "good")}
        ${this._stat("Obsolete", fmtNum(s.obsolete_records), `${pct}% — from ${fmtNum(s.excluded_with_records)} excluded entities`, s.obsolete_records ? "warn" : "")}
        ${this._stat("Database size", fmtBytes(this._data.db_files?.total ?? s.db_size_bytes), this._filesText() || "incl. WAL and SHM files")}
      </div>
      <div class="grid2">
        <section class="card">
          <h2>${bySize ? "Size per entity" : "Records per entity"} <small>top ${top.length}${bySize ? " · estimate" : ""}</small></h2>
          <div class="chips seg" role="group" aria-label="Rank by">
            <button class=${classMap({ chip: true, on: !bySize })} @click=${() => (this._topBy = "records")}>Records</button>
            <button class=${classMap({ chip: true, on: !!bySize })} ?disabled=${!s.top_sizes?.length} @click=${() => (this._topBy = "size")} title="Records plus attribute data, estimated">Size</button>
          </div>
          <ul class="bars">
            ${top.map(
              ([id, n, p]) => html`<li class=${classMap({ ex: excluded.has(id) })} title=${excluded.has(id) ? "Excluded, still has history" : id}>
                <span class="lbl">${id}</span>
                <span class="bar"><i style="width:${Math.max(2, (n / max) * 100)}%"></i></span>
                <span class="val">${bySize ? `≈ ${fmtBytes(n)}` : fmtNum(n)} <b>${fmtPct(p)}</b></span>
              </li>`
            )}
          </ul>
          ${bySize && !s.has_attr_sizes ? html`<p class="muted">Attribute sizes are still being measured; until then this is based on record counts.</p>` : nothing}
        </section>
        <section class="card">
          <h2>Composition</h2>
          <div class="donut-wrap">
            <div class="donut" style="--p:${pct}" role="img" aria-label="${pct}% obsolete"><span>${100 - pct}%<small>current</small></span></div>
            <ul class="legend">
              <li><i class="c1"></i>Current <b>${fmtNum(s.current_records)}</b></li>
              <li><i class="c2"></i>Obsolete <b>${fmtNum(s.obsolete_records)}</b></li>
            </ul>
          </div>
          <p class="muted">Analysed ${ago(s.generated_at)} · <span class="mono">${s.db_path || ""}</span></p>
          <button class="btn" @click=${this._analyze} ?disabled=${!!this._busy}>${icon("refresh", 18)} Re-analyse</button>
          ${s.obsolete_records ? html`<button class="btn danger-o" @click=${() => (this._tab = "maintenance")}>Clean up obsolete…</button>` : nothing}
        </section>
      </div>
      ${this._suggestionCard()}
      <div class="grid2 even">${this._growthCard(s)}${this._busiestCard(s)}</div>
      ${this._sizeCard(s)}`;
  }

  /* ---------- Overview: suggestions, growth ---------- */
  _suggestionCard() {
    const sg = this._data.suggestions;
    if (!sg) return nothing;
    const safe = sg.items.filter((i) => !i.warn && this._pending.get(i.entity_id) !== false);
    return html`<section class="card">
      <h2>Suggestions ${sg.items.length ? html`<small>could save ≈ ${fmtBytes(sg.save_bytes)} (${sg.save_percent}% of the data)</small>` : nothing}</h2>
      ${sg.items.length
        ? html`<p class="muted">Entities that look like noise: diagnostic or technical values that take up a lot of space. These are suggestions based on names, categories and size; you decide. History of entities you exclude stays until you purge it.</p>
          <ul class="sugg">
            ${sg.items.map((i) => {
              const queued = this._pending.get(i.entity_id) === false;
              return html`<li class=${classMap({ check: !!i.warn })}>
                <div class="sg-main">
                  <b>${i.name}</b> <code>${i.entity_id}</code>
                  <div class="tags">${i.reasons.map((r) => html`<span>${r}</span>`)}</div>
                  ${i.warn ? html`<div class="sg-warn">${icon("warn", 14)} ${i.warn}</div>` : nothing}
                </div>
                <div class="sg-size">${i.bytes ? html`≈ ${fmtBytes(i.bytes)}` : nothing}<small>${fmtPct(i.percent)}</small></div>
                <div class="sg-act">
                  <button class=${classMap({ btn: true, small: true, primary: !queued })} ?disabled=${this._ro || queued} @click=${() => this._toggle([i.entity_id], false)}>${queued ? "Queued" : "Exclude"}</button>
                  <button class="icon-btn" title="Hide this suggestion" aria-label="Hide ${i.entity_id}" ?disabled=${this._ro || !!this._busy} @click=${() => this._dismiss([i.entity_id])}>${icon("close", 18)}</button>
                </div>
              </li>`;
            })}
          </ul>
          <div class="row">
            ${safe.length ? html`<button class="btn" ?disabled=${this._ro} @click=${() => this._toggle(safe.map((i) => i.entity_id), false)}>Exclude the ${safe.length} without warning</button>` : nothing}
            ${sg.dismissed ? html`<button class="btn ghost" ?disabled=${this._ro || !!this._busy} @click=${() => this._dismiss([], true)}>Show ${sg.dismissed} hidden again</button>` : nothing}
          </div>
          <p class="muted">Excluding is saved with the bar at the bottom; Home Assistant needs a restart to apply it.</p>`
        : html`<p class="muted">${icon("check", 16)} Nothing stands out right now. ${sg.dismissed ? html`<button class="link" @click=${() => this._dismiss([], true)}>Show ${sg.dismissed} hidden</button>` : nothing}</p>`}
    </section>`;
  }

  _growthCard(s) {
    const g = this._data.growth;
    if (!g) return nothing;
    const pts = g.points || [];
    let chart = nothing;
    if (pts.length >= 2) {
      const sizes = pts.map((p) => p.size);
      const lo = Math.min(...sizes);
      const hi = Math.max(...sizes);
      const span = hi - lo || 1;
      const xy = pts.map((p, i) => [(i / (pts.length - 1)) * 300, 70 - ((p.size - lo) / span) * 60]);
      const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      chart = html`<svg class="chart" viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label="Database size over ${pts.length} days, from ${fmtBytes(sizes[0])} to ${fmtBytes(sizes[sizes.length - 1])}">
          <polygon points="0,80 ${line} 300,80" class="area"></polygon><polyline points=${line} class="ln"></polyline></svg>
        <div class="axis"><span>${pts[0].d}</span><span>${fmtBytes(lo)} – ${fmtBytes(hi)}</span><span>${pts[pts.length - 1].d}</span></div>`;
    }
    let trendText;
    if (g.growth_per_day == null) trendText = html`The trend shows up after a few days of history (${g.snapshots} ${g.snapshots === 1 ? "snapshot" : "snapshots"} so far).`;
    else if (g.growth_per_day > 0 && g.days_to_full != null) trendText = html`The file grows about <b>${fmtBytes(g.growth_per_day)}</b> per day; at that pace the disk is full in <b>${fmtDay(g.days_to_full)}</b>.`;
    else if (g.growth_per_day > 0) trendText = html`The file grows about <b>${fmtBytes(g.growth_per_day)}</b> per day.`;
    else trendText = html`The file size is stable.`;
    return html`<section class="card">
      <h2>Growth</h2>
      <p class="fact"><b>${fmtNum(g.recent_total)}</b> records in the last 24 hours${g.bytes_per_day ? html` · about <b>${fmtBytes(g.bytes_per_day)}</b> per day` : nothing}.</p>
      ${chart}
      <p class="muted">${trendText}</p>
      ${g.disk_total ? html`<p class="muted">Disk: ${fmtBytes(g.disk_free)} free of ${fmtBytes(g.disk_total)} (${Math.round((g.disk_free * 100) / g.disk_total)}%).</p>` : nothing}
    </section>`;
  }

  _busiestCard(s) {
    const top = s.top_recent || [];
    const max = top[0]?.[1] || 1;
    return html`<section class="card">
      <h2>Busiest in the last 24 hours</h2>
      ${top.length
        ? html`<ul class="bars">${top.map(([id, n]) => html`<li title=${id}><span class="lbl">${id}</span><span class="bar"><i style="width:${Math.max(2, (n / max) * 100)}%"></i></span><span class="val">${fmtNum(n)}</span></li>`)}</ul>
          <p class="muted">What is being written right now, regardless of purges: about ${fmtNum(Math.round((top[0][1] / 24) * 10) / 10)} records per hour for the busiest entity.</p>`
        : html`<p class="muted">No recent records found.</p>`}
    </section>`;
  }
  _filesText() {
    const f = this._data.db_files;
    if (!f?.total) return "";
    return ` · db ${fmtBytes(f.db)}${f.wal ? ` · WAL ${fmtBytes(f.wal)}` : ""}${f.shm ? ` · SHM ${fmtBytes(f.shm)}` : ""}`.replace(/^ · /, "");
  }

  _sizeCard(s) {
    const tables = s.tables || [];
    if (!tables.length && !s.free_bytes) return nothing;
    const total = tables.reduce((a, t) => a + t.bytes, 0) || 1;
    const max = tables[0]?.bytes || 1;
    return html`<section class="card">
      <h2>Size by table <small>${fmtBytes(total)} incl. indexes</small></h2>
      <ul class="bars">
        ${tables.slice(0, 8).map((t) => html`<li><span class="lbl" title=${t.name}>${t.name}</span><span class="bar"><i style="width:${Math.max(2, (t.bytes / max) * 100)}%"></i></span><span class="val">${fmtBytes(t.bytes)} <b>${fmtPct((t.bytes / total) * 100)}</b></span></li>`)}
      </ul>
      ${s.free_bytes ? html`<p class="muted">Unused space inside the file: <b>${fmtBytes(s.free_bytes)}</b>${s.free_bytes > 0 ? " — a repack returns this to the disk (Maintenance tab)." : ""}</p>` : nothing}
    </section>`;
  }

  _stat(label, value, sub, tone = "") {
    return html`<div class="card stat ${tone}"><div class="k">${label}</div><div class="v">${value}</div><div class="s">${sub}</div></div>`;
  }

  /* ---------- Entities ---------- */
  _filteredTree() {
    const q = this._search.trim().toLowerCase();
    const out = [];
    for (const dev of this._data.tree) {
      let ents = dev.entities.filter((e) => {
        if (this._domain && e.domain !== this._domain) return false;
        const rec = this._isRecorded(e);
        if (this._status === "recorded" && !rec) return false;
        if (this._status === "excluded" && rec) return false;
        if (this._status === "history" && !( !rec && e.records > 0)) return false;
        if (!q) return true;
        return e.entity_id.toLowerCase().includes(q) || e.name.toLowerCase().includes(q) || e.platform.toLowerCase().includes(q) || dev.name.toLowerCase().includes(q);
      });
      if (!ents.length) continue;
      if (this._sort === "records") ents = [...ents].sort((a, b) => b.records - a.records);
      if (this._sort === "size") ents = [...ents].sort((a, b) => b.bytes - a.bytes);
      out.push({ ...dev, entities: ents, records: ents.reduce((a, e) => a + e.records, 0), percent: ents.reduce((a, e) => a + e.percent, 0), bytes: ents.reduce((a, e) => a + (e.bytes || 0), 0) });
    }
    if (this._sort === "records") out.sort((a, b) => b.records - a.records);
    if (this._sort === "size") out.sort((a, b) => b.bytes - a.bytes);
    return out;
  }

  _tEntities() {
    const domains = [...new Set(this._entities.map((e) => e.domain))].sort();
    const tree = this._filteredTree();
    const filtering = !!(this._search || this._domain || this._status !== "all");
    const total = tree.reduce((a, d) => a + d.entities.length, 0);
    const chips = [["all", "All"], ["recorded", "Recorded"], ["excluded", "Excluded"], ["history", "Excluded with history"]];
    return html`
      <div class="toolbar card">
        <label class="search">${icon("search", 18)}<input type="search" placeholder="Search entity, name, device or platform…" .value=${this._search} @input=${(e) => (this._search = e.target.value)} /></label>
        <select aria-label="Domain" .value=${this._domain} @change=${(e) => (this._domain = e.target.value)}>
          <option value="">All domains</option>${domains.map((d) => html`<option value=${d} ?selected=${d === this._domain}>${d}</option>`)}
        </select>
        <select aria-label="Sort" .value=${this._sort} @change=${(e) => (this._sort = e.target.value)}>
          <option value="name" ?selected=${this._sort === "name"}>Sort by name</option><option value="records" ?selected=${this._sort === "records"}>Sort by share of database</option><option value="size" ?selected=${this._sort === "size"}>Sort by estimated size</option>
        </select>
        <div class="chips">${chips.map(([id, l]) => html`<button class=${classMap({ chip: true, on: this._status === id })} @click=${() => (this._status = id)}>${l}</button>`)}</div>
        <div class="count">${fmtNum(total)} entities in ${tree.length} devices
          ${filtering ? html`<button class="link" @click=${() => { this._search = ""; this._domain = ""; this._status = "all"; }}>Clear filters</button>` : nothing}
          ${total ? html`<span class="bulk"><button class="link" @click=${() => this._toggle(tree.flatMap((d) => d.entities.map((e) => e.entity_id)), true)}>Record all shown</button> · <button class="link" @click=${() => this._toggle(tree.flatMap((d) => d.entities.map((e) => e.entity_id)), false)}>Exclude all shown</button></span>` : nothing}
        </div>
      </div>
      ${!this._summary ? html`<div class="hint">Record counts are shown after the first <button class="link" @click=${this._analyze}>database analysis</button>.</div>` : nothing}
      ${tree.length ? repeat(tree, (d) => d.device_id, (d) => this._device(d, filtering)) : html`<div class="card empty"><p>No entities match your filters.</p></div>`}`;
  }

  _device(dev, forceOpen) {
    const open = forceOpen || this._open.has(dev.device_id);
    const full = this._data.tree.find((d) => d.device_id === dev.device_id) || dev; // unfiltered: purge never silently skips entities
    const ids = dev.entities.map((e) => e.entity_id);
    const rec = dev.entities.filter((e) => this._isRecorded(e)).length;
    const state = rec === ids.length ? "all" : rec === 0 ? "none" : "mixed";
    return html`<section class="card dev">
      <div class="dev-head" @click=${() => { const n = new Set(this._open); n.has(dev.device_id) ? n.delete(dev.device_id) : n.add(dev.device_id); this._open = n; }}>
        <span class=${classMap({ chev: true, open })}>${icon("chevron", 20)}</span>
        <div class="dev-name"><b>${dev.name}</b><small>${ids.length} entities · ${rec} recorded${dev.records ? ` · ${fmtNum(dev.records)} records (${fmtPct(dev.percent)} of database)` : ""}${dev.bytes ? ` · ≈ ${fmtBytes(dev.bytes)}` : ""}</small></div>
        ${dev.device_id !== "__no_device__"
          ? html`<button class="icon-btn" title=${full.records ? `Purge the history of all ${full.entities.length} entities of this device` : "No records to purge (analyse first)"} aria-label="Purge ${dev.name}" ?disabled=${this._ro || !full.records}
              @click=${(e) => { e.stopPropagation(); this._askPurge("entities", full.entities.filter((x) => x.records).map((x) => x.entity_id), `device ${dev.name}`); }}>${icon("trash", 18)}</button>`
          : nothing}
        <div class="sw-wrap" @click=${(e) => e.stopPropagation()}>
          ${this._switch(state, `Record all entities of ${dev.name}`, () => this._toggle(ids, state !== "all"))}
        </div>
      </div>
      ${open ? html`<ul class="ents">${dev.entities.map((e) => this._entity(e))}</ul>` : nothing}
    </section>`;
  }

  _entity(e) {
    const rec = this._isRecorded(e);
    const changed = this._pending.has(e.entity_id);
    return html`<li class=${classMap({ ent: true, off: !rec, changed })}>
      <div class="ent-name"><span>${e.name}</span><code>${e.entity_id}</code></div>
      <span class="plat">${e.platform}</span>
      <span class="recs" title="Share of all records in the database">${e.records ? html`${fmtNum(e.records)} <b>${fmtPct(e.percent)}</b>` : "–"}</span>
      <span class="esize" title="Estimated space in the database: records plus attribute data">${e.bytes ? `≈ ${fmtBytes(e.bytes)}` : ""}</span>
      <button class="icon-btn" title=${e.records ? "Purge the history of this entity" : "No records to purge"} aria-label="Purge ${e.entity_id}" ?disabled=${this._ro || !e.records} @click=${() => this._askPurge("entities", [e.entity_id], e.entity_id)}>${icon("trash", 18)}</button>
      ${this._switch(rec ? "all" : "none", `Record ${e.entity_id}`, () => this._toggle([e.entity_id], !rec))}
    </li>`;
  }

  _switch(state, label, onClick) {
    return html`<button role="switch" aria-checked=${state === "all" ? "true" : state === "mixed" ? "mixed" : "false"} aria-label=${label} class="sw ${state}" ?disabled=${this._ro} title=${this._ro ? "Read-only mode" : ""} @click=${onClick}><i></i></button>`;
  }

  _renderSaveBar() {
    const n = this._pending.size;
    const off = [...this._pending.values()].filter((v) => !v).length;
    return html`<div class="savebar" role="region" aria-label="Unsaved changes">
      <span><b>${n}</b> unsaved change${n > 1 ? "s" : ""} · ${off} to exclude, ${n - off} to record</span>
      <span class="grow"></span>
      <button class="btn" @click=${() => (this._pending = new Map())} ?disabled=${!!this._busy}>Discard</button>
      <button class="btn primary" @click=${this._savePending} ?disabled=${!!this._busy}>${this._busy === "save" ? "Saving…" : "Save changes"}</button>
    </div>`;
  }

  /* ---------- Maintenance ---------- */
  _tMaintenance() {
    const s = this._summary;
    const keep = this._data.options.purge_keep_days;
    const excludedIds = this._entities.filter((e) => !e.recorded).map((e) => e.entity_id);
    return html`<div class="warnbox">${icon("warn")}<span><b>Purges cannot be undone.</b> Make a full Home Assistant backup first. Every destructive action asks for confirmation and shows its impact.</span></div>
      <div class="actions">
        ${this._action("Purge by retention", `Delete history older than ${keep} days for all entities (the retention setting).`, "Purge…", () => this._askPurge("retention"), true)}
        ${this._action("Purge excluded entities", `Delete the entire history of ${fmtNum(excludedIds.length)} excluded entities${s ? ` (${fmtNum(s.obsolete_records)} records)` : ""}. Ignores retention.`, "Purge excluded…", () => this._askPurge("excluded"), true, !s ? "Analyse the database first" : "")}
        ${this._action("Repack database", "Rewrite the SQLite file to reclaim disk space after large purges.", "Repack…", () => this._askRepack())}
        ${this._action("Restart Home Assistant", "Needed to apply recorder configuration changes.", "Restart…", () => this._askRestart())}
      </div>`;
  }
  _action(title, text, label, fn, danger = false, disabledReason = "") {
    return html`<div class="card action"><div><h3>${title}</h3><p>${text}</p></div>
      <button class=${classMap({ btn: true, "danger-o": danger })} title=${disabledReason} ?disabled=${this._ro || !!this._busy || !!disabledReason} @click=${fn}>${label}</button></div>`;
  }

  /* ---------- Orphans ---------- */
  _tOrphans() {
    const list = this._summary?.orphan_exclusions;
    if (!this._summary) return html`<div class="card empty"><p>Analyse the database first to detect orphaned exclusions.</p><button class="btn primary" @click=${this._analyze}>Analyse database</button></div>`;
    if (!list.length) return html`<div class="card empty">${icon("check", 40)}<h2>No orphaned exclusions</h2><p>Every excluded entity still exists.</p></div>`;
    return html`<div class="card">
      <h2>${list.length} orphaned exclusion${list.length > 1 ? "s" : ""}</h2>
      <p class="muted">These entities are excluded but no longer exist in Home Assistant and have no history. Removing them tidies <code>${this._data.yaml_file}</code>.</p>
      <ul class="plain">${list.map((id) => html`<li><code>${id}</code></li>`)}</ul>
      <button class="btn danger-o" ?disabled=${this._ro} @click=${() => this._confirm({ title: "Remove orphaned exclusions", body: `${list.length} entries will be removed from the exclusion list. Nothing is deleted from the database.`, confirmLabel: "Remove", onConfirm: () => this._run("orph", async () => { await this._ws("remove_orphans"); await this._refresh(); }, { success: "Removed. Restart to apply." }) })}>${icon("trash", 18)} Remove all ${list.length}</button>
    </div>`;
  }

  /* ---------- Migration ---------- */
  async _previewMigration(source, text) {
    const res = await this._run("mig", () => this._ws("migration_preview", { source, ...(text !== undefined ? { text } : {}) }));
    if (res) {
      this._migration = { source, text, ...res };
      this._merge = false;
    }
  }

  async _loadSources() {
    const res = await this._run("mig", () => this._ws("migration_sources"));
    if (res) this._sources = res.sources;
  }

  /** Banner shortcut: go to Migration and open the activation preview (diff) straight away. */
  async _setup() {
    this._tab = "migration";
    if (!this._sources) this._loadSources();
    const c = this._data.config;
    const source = c.imported ? "configuration" : c.legacy_file_present ? "legacy" : null;
    if (!source) {
      this._notify("Nothing to import was found; configuration.yaml can still be activated from the Migration tab.");
      return;
    }
    await this._previewMigration(source);
    await this.updateComplete;
    this.renderRoot.querySelector("#mig-preview")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  _tMigration() {
    const c = this._data.config;
    const m = this._migration;
    const stateText = { active: "Active: configuration.yaml already includes this file.", absent: "No recorder: key in configuration.yaml.", inline: "Inline recorder: block found in configuration.yaml.", other_include: `recorder: includes ${c.include_target}.`, invalid: "recorder: block could not be parsed." }[c.state];
    return html`<div class="card">
        <h2>Current situation</h2>
        <p class="status ${c.state === "active" ? "ok" : ""}">${c.state === "active" ? icon("check", 18) : icon("warn", 18)} ${stateText}</p>
        <ol class="steps">
          <li class=${c.state === "active" ? "done" : ""}><b>1 · Import</b> existing exclusions into Recorder Studio (nothing is changed on disk except <code>${this._data.yaml_file}</code>).</li>
          <li class=${c.state === "active" ? "done" : ""}><b>2 · Activate</b>: configuration.yaml is backed up, the old block is commented out and <code>recorder: !include ${this._data.yaml_file}</code> is added.</li>
          <li><b>3 · Restart</b> Home Assistant.</li>
        </ol>
      </div>
      <div class="card">
        <h2>Import from</h2>
        <p class="muted">Recorder Studio looks for recorder settings in your configuration folder: configuration.yaml, the file it includes, GUI Recorder and any other YAML file such as packages. Files are only read, never changed.</p>
        ${this._sources === null ? html`<p class="muted">Searching…</p>` : this._sources.length ? html`<ul class="sources">${this._sources.map((x) => html`<li>
            <div class="grow"><b>${x.label}</b><br /><span class="muted">${fmtNum(x.excluded)} excluded ${x.excluded === 1 ? "entity" : "entities"}${x.note ? ` · ${x.note}` : ""}</span></div>
            <button class="btn" ?disabled=${!!this._busy} @click=${() => this._previewMigration(x.id)}>Preview import</button>
          </li>`)}</ul>` : html`<p class="muted">No recorder settings were found automatically. Use one of the options below.</p>`}
        <div class="row"><button class="btn ghost" ?disabled=${!!this._busy} @click=${this._loadSources}>${icon("refresh", 18)} Search again</button></div>
        <h3>Another file</h3>
        <div class="row">
          <input class="grow" type="text" placeholder="path in the config folder, e.g. packages/recorder.yaml" .value=${this._filePath} @input=${(e) => (this._filePath = e.target.value)} />
          <button class="btn" ?disabled=${!this._filePath.trim() || !!this._busy} @click=${() => this._previewMigration(`file:${this._filePath.trim()}`)}>Preview import</button>
        </div>
        <h3>Paste YAML</h3>
        <textarea rows="6" placeholder="recorder:&#10;  exclude:&#10;    entities:&#10;      - sensor.example" .value=${this._paste} @input=${(e) => (this._paste = e.target.value)}></textarea>
        <div class="row"><button class="btn" ?disabled=${!this._paste.trim() || !!this._busy} @click=${() => this._previewMigration("paste", this._paste)}>Preview import</button></div>
      </div>
      ${m ? html`<div class="card" id="mig-preview">
        <h2>Preview: ${m.label}</h2>
        <p><b>${fmtNum(m.import.excluded_count)}</b> excluded entities found. ${this._merge ? "They are added to your current exclusions." : "By default they replace the current Recorder Studio exclusion list."}</p>
        ${m.current_excluded ? html`<label class="inline"><input type="checkbox" .checked=${this._merge} @change=${(e) => (this._merge = e.target.checked)} /> Add to my current ${fmtNum(m.current_excluded)} exclusions instead of replacing them</label>` : nothing}
        ${m.note ? html`<p class="status">${icon("warn", 18)} ${m.note}</p>` : nothing}
        ${m.import.warnings.length ? html`<ul class="warnings">${m.import.warnings.map((w) => html`<li>${icon("warn", 16)} ${w}</li>`)}</ul>` : nothing}
        <button class="btn primary" ?disabled=${this._ro || !!this._busy} @click=${() => this._confirm({ title: "Import configuration", body: this._merge ? `Adds the ${m.import.excluded_count} imported exclusions to your current ones.` : `Replaces the current exclusions with ${m.import.excluded_count} imported ones.`, confirmLabel: "Import", danger: false, onConfirm: async () => { const r = await this._run("mig", () => this._ws("migration_import", { source: m.source, ...(m.text !== undefined ? { text: m.text } : {}), merge: this._merge, confirm: true }), { success: "Imported." }); if (r) { this._migration = null; await this._refresh(); } } })}>Import now</button>
        ${m.diff ? html`<h3>Activation diff (configuration.yaml)</h3><pre class="diff">${m.diff.split("\n").map((l) => html`<span class=${l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : ""}>${l}\n</span>`)}</pre>
          <button class="btn danger-o" ?disabled=${this._ro || !!this._busy} @click=${() => this._confirm({ title: "Activate in configuration.yaml", body: "A backup of configuration.yaml is created first. The recorder block is replaced by an include; a restart is needed.", confirmLabel: "Activate", danger: false, onConfirm: async () => { const r = await this._run("mig", () => this._ws("migration_activate", { confirm: true }), { success: (x) => `Activated. Backup: ${x.backup || "none"}` }); if (r) { this._migration = null; await this._refresh(); } } })}>Activate include</button>` : nothing}
      </div>` : nothing}`;
  }

  /* ---------- Settings ---------- */
  _tSettings() {
    const f = this._form;
    const set = (k, v) => (this._form = { ...f, [k]: v });
    const dirty = JSON.stringify(f) !== JSON.stringify({ ...this._data.options, rules_text: this._data.rules_text });
    return html`<div class="card form">
      <h2>Recorder options</h2>
      <label>Keep history (days)<input type="number" min="1" max="3650" .value=${String(f.purge_keep_days)} @input=${(e) => set("purge_keep_days", Number(e.target.value))} /></label>
      <label>Commit interval (seconds)<input type="number" min="0" max="86400" .value=${String(f.commit_interval)} @input=${(e) => set("commit_interval", Number(e.target.value))} /></label>
      <label class="inline"><input type="checkbox" .checked=${f.auto_purge} @change=${(e) => set("auto_purge", e.target.checked)} /> Auto purge (nightly)</label>
      <label class="inline"><input type="checkbox" .checked=${f.auto_repack} @change=${(e) => set("auto_repack", e.target.checked)} /> Auto repack (after purge)</label>
      <h2>Manual rules</h2>
      <p class="muted">Optional YAML for domain, glob and event-type rules. Individual entities are managed on the Entities tab.</p>
      <textarea rows="7" spellcheck="false" placeholder="exclude:\n  entity_globs:\n    - sensor.*_uptime" .value=${f.rules_text} @input=${(e) => set("rules_text", e.target.value)}></textarea>
      <div class="row"><button class="btn primary" ?disabled=${this._ro || !dirty || !!this._busy} @click=${() => this._run("save", async () => { await this._ws("save_settings", { ...f }); await this._refresh(); }, { success: "Settings saved. Restart to apply." })}>Save settings</button>
      <button class="btn" ?disabled=${!dirty} @click=${() => (this._form = { ...this._data.options, rules_text: this._data.rules_text })}>Reset</button></div>
    </div>
    ${this._alertForm ? this._alertsCard() : nothing}
    <div class="card">
      <h3>About</h3>
      <p class="hint">Recorder Studio <b>v${this._data.version}</b> · SQLite · <a href="https://github.com/r3mcos3/recorder-studio/releases" target="_blank" rel="noopener">Release notes</a> · <a href="https://github.com/r3mcos3/recorder-studio/issues" target="_blank" rel="noopener">Report an issue</a></p>
    </div>`;
  }

  _alertsCard() {
    const a = this._alertForm;
    const set = (k, v) => (this._alertForm = { ...a, [k]: v });
    const saved = this._data.alerts;
    const dirty = a.enabled !== saved.enabled || a.free_percent !== saved.free_percent || a.growth_percent !== saved.growth_percent;
    const active = saved.active || [];
    return html`<div class="card form">
      <h2>Alerts</h2>
      <p class="muted">Recorder Studio checks the database every few hours, also while this panel is closed, and raises an alert under <b>Settings &gt; System &gt; Repairs</b> when the disk runs low or the database grows fast. The alert disappears by itself when the problem is gone. No restart needed.</p>
      <label class="inline"><input type="checkbox" .checked=${a.enabled} @change=${(e) => set("enabled", e.target.checked)} /> Raise alerts</label>
      <label>Alert when free disk space drops below (%)<input type="number" min="1" max="90" .value=${String(a.free_percent)} ?disabled=${!a.enabled} @input=${(e) => set("free_percent", Number(e.target.value))} /></label>
      <label>Alert when the database grew more than this in a week (%)<input type="number" min="5" max="1000" .value=${String(a.growth_percent)} ?disabled=${!a.enabled} @input=${(e) => set("growth_percent", Number(e.target.value))} /></label>
      ${active.length ? html`<p class="status">${icon("warn", 18)} Active now: ${active.map((x) => ALERT_NAMES[x] || x).join(", ")}</p>` : html`<p class="status ok">${icon("check", 18)} No alerts active.</p>`}
      <div class="row"><button class="btn primary" ?disabled=${this._ro || !dirty || !!this._busy} @click=${this._saveAlerts}>Save alert settings</button>
      <button class="btn" ?disabled=${!dirty} @click=${() => (this._alertForm = { enabled: saved.enabled, free_percent: saved.free_percent, growth_percent: saved.growth_percent })}>Reset</button></div>
    </div>`;
  }

  /* ---------- Dialog ---------- */
  _renderDialog() {
    const d = this._dialog;
    const ok = !d.phrase || d.typed === d.phrase;
    const close = () => (this._dialog = null);
    return html`<div class="overlay" @click=${close} @keydown=${(e) => e.key === "Escape" && close()}>
      <div class="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dlg-title" @click=${(e) => e.stopPropagation()}>
        <div class="dlg-head ${d.danger ? "danger" : ""}">${icon(d.danger ? "warn" : "check", 24)}<h2 id="dlg-title">${d.title}</h2></div>
        <p>${d.body}</p>
        ${d.impact ? html`<div class="impact">${d.impact}</div>` : nothing}
        ${d.warning ? html`<div class="note ${d.warning.tone}" role="note">${icon(d.warning.tone === "ok" ? "check" : "warn", 18)}<span>${d.warning.text}</span></div>` : nothing}
        ${d.phrase ? html`<label class="typed"><span>Type <b>${d.phrase}</b> to confirm</span><input autofocus autocomplete="off" .value=${d.typed} @input=${(e) => (this._dialog = { ...d, typed: e.target.value })} /></label>` : nothing}
        <div class="row end">
          <button class="btn" @click=${close}>Cancel</button>
          <button class=${classMap({ btn: true, danger: d.danger, primary: !d.danger })} ?disabled=${!ok} @click=${() => { close(); d.onConfirm(); }}>${d.confirmLabel}</button>
        </div>
      </div>
    </div>`;
  }

  /* ---------- styles ---------- */
  static styles = css`
    :host { display: block; min-height: 100%; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); --rs-radius: var(--ha-card-border-radius, 12px); --rs-ok: var(--success-color, #43a047); --rs-warn: var(--warning-color, #f9a825); --rs-err: var(--error-color, #db4437); --rs-line: var(--divider-color, rgba(127,127,127,.25)); --rs-muted: var(--secondary-text-color); padding-bottom: 80px; box-sizing: border-box; }
    * { box-sizing: border-box; }
    header, nav, main, .banner { max-width: 1100px; margin-inline: auto; padding-inline: 16px; }
    header { display: flex; align-items: center; gap: 12px; padding-block: 16px 8px; }
    .title { display: flex; align-items: center; gap: 10px; color: var(--primary-color); } h1 { margin: 0; font-size: 1.5rem; font-weight: 500; color: var(--primary-text-color); } .ver { color: var(--rs-muted); font-size: .8rem; }
    .size-now { color: var(--primary-text-color); } .grow { flex: 1; } .chip-size { display: inline-flex; align-items: center; gap: 6px; margin-left: 8px; padding: 3px 12px; border-radius: 999px; border: 1px solid var(--rs-line); font-size: .85rem; font-variant-numeric: tabular-nums; } code, .mono { font-family: ui-monospace, Menlo, monospace; font-size: .82em; } code { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); padding: 1px 5px; border-radius: 4px; }
    h2 { font-size: 1.05rem; font-weight: 500; margin: 0 0 12px; } h2 small { color: var(--rs-muted); font-weight: 400; margin-left: 6px; } h3 { margin: 0 0 4px; font-size: 1rem; font-weight: 500; }
    .muted { color: var(--rs-muted); font-size: .9rem; } .center { display: grid; place-items: center; gap: 8px; min-height: 60vh; text-align: center; } .center.err { color: var(--rs-err); }
    .card { background: var(--card-background-color, #fff); border-radius: var(--rs-radius); border: 1px solid var(--rs-line); padding: 16px; margin-bottom: 12px; box-shadow: var(--ha-card-box-shadow, none); }
    .empty { text-align: center; padding: 32px 16px; color: var(--rs-muted); } .empty h2 { color: var(--primary-text-color); }
    /* buttons */
    .btn { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--rs-line); background: transparent; color: var(--primary-text-color); padding: 8px 14px; border-radius: 999px; font: inherit; font-size: .9rem; cursor: pointer; min-height: 38px; }
    .btn:hover:not(:disabled) { background: color-mix(in srgb, var(--primary-text-color) 7%, transparent); } .btn:disabled { opacity: .45; cursor: not-allowed; }
    .btn.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); } .btn.primary:hover:not(:disabled) { filter: brightness(1.1); background: var(--primary-color); }
    .btn.danger { background: var(--rs-err); border-color: var(--rs-err); color: #fff; } .btn.danger:hover:not(:disabled) { background: var(--rs-err); filter: brightness(1.1); }
    .btn.danger-o { color: var(--rs-err); border-color: color-mix(in srgb, var(--rs-err) 50%, transparent); } .btn.ghost { border-color: transparent; } .btn.small { min-height: 30px; padding: 4px 12px; }
    .link { background: none; border: 0; color: var(--primary-color); font: inherit; cursor: pointer; padding: 0; text-decoration: underline; }
    .icon-btn { background: none; border: 0; color: var(--rs-muted); cursor: pointer; padding: 6px; border-radius: 50%; display: grid; place-items: center; } .icon-btn:hover:not(:disabled) { color: var(--rs-err); background: color-mix(in srgb, var(--rs-err) 12%, transparent); } .icon-btn:disabled { opacity: .25; cursor: default; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; } .row.end { justify-content: flex-end; }
    /* banners */
    .banner { display: flex; align-items: center; gap: 10px; padding-block: 10px; margin-block: 8px; border-radius: var(--rs-radius); } .banner > span { flex: 1; }
    .banner.warn, .banner.info, .banner.error { max-width: 1068px; padding-inline: 14px; margin-inline: 16px; } @media (min-width: 1100px) { .banner.warn, .banner.info, .banner.error { margin-inline: auto; } }
    .banner.warn { background: color-mix(in srgb, var(--rs-warn) 18%, transparent); border: 1px solid color-mix(in srgb, var(--rs-warn) 50%, transparent); }
    .banner.info { background: color-mix(in srgb, var(--primary-color) 12%, transparent); border: 1px solid color-mix(in srgb, var(--primary-color) 40%, transparent); }
    .banner.error { background: color-mix(in srgb, var(--rs-err) 15%, transparent); border: 1px solid var(--rs-err); }
    /* tabs */
    nav { display: flex; gap: 4px; overflow-x: auto; border-bottom: 1px solid var(--rs-line); scrollbar-width: none; } nav::-webkit-scrollbar { display: none; }
    .tab { display: inline-flex; align-items: center; gap: 6px; background: none; border: 0; border-bottom: 2px solid transparent; color: var(--rs-muted); padding: 12px 14px; font: inherit; cursor: pointer; white-space: nowrap; }
    .tab.on { color: var(--primary-color); border-bottom-color: var(--primary-color); } .tab:hover { color: var(--primary-text-color); }
    .badge { background: var(--rs-warn); color: #000; border-radius: 999px; font-size: .7rem; padding: 1px 7px; }
    main { padding-top: 16px; }
    /* overview */
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 12px; } .stat { margin: 0; } .stat .k { color: var(--rs-muted); font-size: .85rem; } .stat .v { font-size: 1.9rem; font-weight: 500; margin: 4px 0; font-variant-numeric: tabular-nums; } .stat .s { color: var(--rs-muted); font-size: .8rem; } .stat.good .v { color: var(--rs-ok); } .stat.warn .v { color: var(--rs-warn); }
    .grid2 { display: grid; grid-template-columns: 3fr 2fr; gap: 12px; } @media (max-width: 800px) { .grid2 { grid-template-columns: 1fr; } }
    .bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; } .bars li { display: grid; grid-template-columns: minmax(80px, 34%) 1fr auto; gap: 10px; align-items: center; font-size: .85rem; }
    .bars .lbl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, monospace; font-size: .78rem; } .bar { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); border-radius: 4px; height: 10px; overflow: hidden; } .bar i { display: block; height: 100%; background: var(--primary-color); border-radius: 4px; } .bars .ex .bar i { background: var(--rs-warn); } .bars .ex .lbl::after { content: " ⚑"; } .val { font-variant-numeric: tabular-nums; color: var(--rs-muted); min-width: 110px; text-align: right; } .val b, .recs b { color: var(--primary-text-color); font-weight: 500; display: inline-block; min-width: 44px; }
    .donut-wrap { display: flex; align-items: center; gap: 20px; margin-bottom: 12px; flex-wrap: wrap; } .donut { --c1: var(--primary-color); --c2: var(--rs-warn); width: 130px; height: 130px; border-radius: 50%; background: conic-gradient(var(--c2) calc(var(--p) * 1%), var(--c1) 0); display: grid; place-items: center; position: relative; } .donut::before { content: ""; position: absolute; inset: 18px; background: var(--card-background-color, #fff); border-radius: 50%; } .donut span { position: relative; font-size: 1.4rem; font-weight: 500; text-align: center; } .donut small { display: block; font-size: .7rem; color: var(--rs-muted); font-weight: 400; }
    .legend { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; font-size: .9rem; } .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; } .legend .c1 { background: var(--primary-color); } .legend .c2 { background: var(--rs-warn); } .legend b { margin-left: 6px; font-variant-numeric: tabular-nums; }
    /* entities */
    .toolbar { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; position: sticky; top: 0; z-index: 3; } @media (max-width: 700px) { .toolbar { grid-template-columns: 1fr 1fr; position: static; } .search { grid-column: 1 / -1; } }
    .toolbar .chips, .toolbar .count { grid-column: 1 / -1; } .search { display: flex; align-items: center; gap: 8px; border: 1px solid var(--rs-line); border-radius: 999px; padding: 0 14px; color: var(--rs-muted); } .search input { flex: 1; border: 0; background: none; color: var(--primary-text-color); font: inherit; padding: 10px 0; outline: none; min-width: 0; } .search:focus-within { border-color: var(--primary-color); }
    select, input[type=number], input[type=text], textarea { background: var(--card-background-color, transparent); color: var(--primary-text-color); border: 1px solid var(--rs-line); border-radius: 8px; padding: 9px 10px; font: inherit; min-width: 0; }
    .chips { display: flex; gap: 6px; flex-wrap: wrap; } .chip { border: 1px solid var(--rs-line); background: none; color: var(--primary-text-color); border-radius: 999px; padding: 4px 12px; font: inherit; font-size: .85rem; cursor: pointer; } .chip.on { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
    .count { color: var(--rs-muted); font-size: .85rem; display: flex; gap: 12px; flex-wrap: wrap; } .bulk { margin-left: auto; } .hint { color: var(--rs-muted); font-size: .85rem; margin: 0 4px 10px; }
    .dev { padding: 0; overflow: hidden; } .dev-head { display: flex; align-items: center; gap: 8px; padding: 12px 14px; cursor: pointer; } .dev-head:hover { background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); }
    .chev { display: grid; transition: transform .15s; color: var(--rs-muted); } .chev.open { transform: rotate(90deg); } .dev-name { flex: 1; min-width: 0; display: flex; flex-direction: column; } .dev-name b { font-weight: 500; overflow: hidden; text-overflow: ellipsis; } .dev-name small { color: var(--rs-muted); }
    .ents { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rs-line); } .ent { display: grid; grid-template-columns: 1fr 90px 150px 84px 34px 48px; gap: 8px; align-items: center; padding: 8px 14px 8px 42px; border-bottom: 1px solid var(--rs-line); } .ent:last-child { border-bottom: 0; }
    .ent.off .ent-name span { text-decoration: line-through; opacity: .6; } .ent.changed { background: color-mix(in srgb, var(--primary-color) 9%, transparent); box-shadow: inset 3px 0 var(--primary-color); }
    .ent-name { display: flex; flex-direction: column; min-width: 0; } .ent-name span, .ent-name code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .ent-name code { background: none; padding: 0; color: var(--rs-muted); } .plat { color: var(--rs-muted); font-size: .8rem; overflow: hidden; text-overflow: ellipsis; } .recs { text-align: right; font-variant-numeric: tabular-nums; color: var(--rs-muted); font-size: .85rem; }
    @media (max-width: 640px) { .ent { grid-template-columns: 1fr 34px 48px; padding-left: 16px; } .plat, .recs, .esize { display: none; } }
    .sw { width: 44px; height: 24px; border-radius: 999px; border: 0; background: color-mix(in srgb, var(--primary-text-color) 28%, transparent); position: relative; cursor: pointer; padding: 0; transition: background .15s; flex: none; } .sw i { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform .15s; box-shadow: 0 1px 3px rgba(0,0,0,.35); }
    .sw.all { background: var(--primary-color); } .sw.all i { transform: translateX(20px); } .sw.mixed { background: var(--rs-warn); } .sw.mixed i { transform: translateX(10px); } .sw:disabled { opacity: .55; cursor: not-allowed; } .sw:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .savebar { position: fixed; left: 50%; transform: translateX(-50%); bottom: 16px; z-index: 10; display: flex; align-items: center; gap: 10px; width: min(760px, calc(100% - 24px)); padding: 10px 14px; background: var(--card-background-color, #fff); border: 1px solid var(--primary-color); border-radius: 999px; box-shadow: 0 6px 24px rgba(0,0,0,.28); font-size: .9rem; } @media (max-width: 600px) { .savebar { border-radius: 16px; flex-wrap: wrap; } }
    .esize { text-align: right; font-variant-numeric: tabular-nums; color: var(--rs-muted); font-size: .8rem; white-space: nowrap; }
    /* suggestions, growth, notes */
    .grid2.even { grid-template-columns: 1fr 1fr; } @media (max-width: 800px) { .grid2.even { grid-template-columns: 1fr; } }
    .chips.seg { margin: -4px 0 10px; }
    .sugg { list-style: none; margin: 0 0 8px; padding: 0; display: grid; gap: 8px; } .sugg li { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 10px 12px; border: 1px solid var(--rs-line); border-radius: 10px; } .sugg li.check { border-style: dashed; }
    .sg-main { min-width: 0; overflow-wrap: anywhere; } .sg-main code { color: var(--rs-muted); background: none; padding: 0; margin-left: 4px; }
    .tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; } .tags span { font-size: .75rem; color: var(--rs-muted); border: 1px solid var(--rs-line); border-radius: 999px; padding: 1px 8px; }
    .sg-warn { display: flex; align-items: flex-start; gap: 6px; margin-top: 6px; font-size: .8rem; color: var(--rs-warn); }
    .sg-size { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; white-space: nowrap; } .sg-size small { display: block; color: var(--rs-muted); font-weight: 400; } .sg-act { display: flex; align-items: center; gap: 4px; }
    @media (max-width: 640px) { .sugg li { grid-template-columns: 1fr auto; } .sg-size { grid-column: 1; text-align: left; } .sg-size small { display: inline; margin-left: 6px; } .sg-act { grid-row: 1 / span 2; grid-column: 2; flex-direction: column; } }
    .fact { margin: 0 0 8px; } .chart { width: 100%; height: 90px; display: block; } .chart .area { fill: color-mix(in srgb, var(--primary-color) 18%, transparent); } .chart .ln { fill: none; stroke: var(--primary-color); stroke-width: 2; vector-effect: non-scaling-stroke; }
    .axis { display: flex; justify-content: space-between; color: var(--rs-muted); font-size: .72rem; margin-bottom: 8px; font-variant-numeric: tabular-nums; }
    .note { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-radius: 8px; margin: 8px 0; font-size: .9rem; } .note.warn { background: color-mix(in srgb, var(--rs-warn) 16%, transparent); border: 1px solid color-mix(in srgb, var(--rs-warn) 45%, transparent); } .note.ok { background: color-mix(in srgb, var(--rs-ok) 12%, transparent); border: 1px solid color-mix(in srgb, var(--rs-ok) 40%, transparent); } .note svg { flex: none; margin-top: 1px; }
    main > .note { margin-top: 0; margin-bottom: 12px; }
    /* maintenance */
    .warnbox { display: flex; gap: 10px; align-items: center; padding: 12px 14px; border-radius: var(--rs-radius); margin-bottom: 12px; background: color-mix(in srgb, var(--rs-err) 12%, transparent); border: 1px solid color-mix(in srgb, var(--rs-err) 45%, transparent); }
    .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; } @media (max-width: 420px) { .actions { grid-template-columns: 1fr; } } .action { display: flex; gap: 14px; align-items: center; justify-content: space-between; margin: 0; } .action p { margin: 0; color: var(--rs-muted); font-size: .88rem; } .action .btn { flex: none; }
    ul.plain { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 4px; max-height: 340px; overflow: auto; }
    /* migration */
    .status { display: flex; align-items: center; gap: 8px; margin: 0 0 12px; color: var(--rs-warn); } .status.ok { color: var(--rs-ok); }
    .steps { list-style: none; padding-left: 0; display: grid; gap: 8px; color: var(--primary-text-color); } .steps li.done { color: var(--rs-muted); }
    .sources { list-style: none; margin: 0 0 8px; padding: 0; display: grid; gap: 8px; } .sources li { display: flex; gap: 12px; align-items: center; justify-content: space-between; padding: 10px 12px; border: 1px solid var(--rs-line); border-radius: 10px; } .sources .grow { min-width: 0; overflow-wrap: anywhere; }
    label.inline { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
    .warnings { list-style: none; padding: 0; display: grid; gap: 6px; color: var(--rs-warn); font-size: .9rem; } .warnings li { display: flex; gap: 6px; align-items: flex-start; }
    h3 { margin-top: 16px; } .diff { background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); border-radius: 8px; padding: 12px; overflow: auto; font-size: .78rem; line-height: 1.5; max-height: 320px; margin: 8px 0 12px; } .diff .add { color: var(--rs-ok); } .diff .del { color: var(--rs-err); }
    /* settings */
    .form { display: grid; gap: 12px; max-width: 640px; } .form label { display: grid; gap: 4px; font-size: .88rem; color: var(--rs-muted); } .form label.inline { display: flex; align-items: center; gap: 8px; color: var(--primary-text-color); } textarea { font-family: ui-monospace, monospace; font-size: .82rem; width: 100%; resize: vertical; }
    /* dialog + toast */
    .overlay { position: fixed; inset: 0; z-index: 20; background: rgba(0,0,0,.55); display: grid; place-items: center; padding: 16px; }
    .dialog { background: var(--card-background-color, #fff); color: var(--primary-text-color); border-radius: 16px; padding: 20px; width: min(480px, 100%); box-shadow: 0 12px 48px rgba(0,0,0,.4); } .dlg-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; } .dlg-head h2 { margin: 0; } .dlg-head.danger { color: var(--rs-err); } .dlg-head.danger h2 { color: var(--primary-text-color); }
    .impact { background: color-mix(in srgb, var(--rs-err) 12%, transparent); border-radius: 8px; padding: 10px 12px; font-weight: 500; font-variant-numeric: tabular-nums; margin: 8px 0; } .typed { display: grid; gap: 6px; margin-top: 12px; font-size: .9rem; } .typed input { border: 1px solid var(--rs-line); border-radius: 8px; padding: 9px 10px; font: inherit; background: transparent; color: inherit; }
    .toast { position: fixed; z-index: 30; bottom: 88px; left: 50%; transform: translateX(-50%); background: #323232; color: #fff; padding: 10px 18px; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.4); max-width: calc(100% - 32px); } .toast.error { background: var(--rs-err); }
    button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  `;
}

customElements.define("recorder-studio-panel", RecorderStudioPanel);
