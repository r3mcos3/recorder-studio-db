// Gives the Recorder Studio panel a minimal `hass` object. Its websocket calls become POSTs to the add-on backend.
// URLs stay relative so they work behind the Home Assistant ingress path prefix.
import "./recorder-studio-panel.js";

const hass = {
  connection: {
    async sendMessagePromise(msg) {
      const r = await fetch("api/command", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(msg) });
      let body = {};
      try { body = await r.json(); } catch (_) { /* non-JSON error page */ }
      if (!r.ok) throw { code: body.code || "http_" + r.status, message: body.message || r.statusText };
      return body.result;
    },
  },
};

const panel = document.querySelector("recorder-studio-panel");
panel.narrow = window.innerWidth < 700;
panel.hass = hass;
window.addEventListener("resize", () => { panel.narrow = window.innerWidth < 700; });
