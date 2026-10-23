import { app } from "../../scripts/app.js";

// Settings dialog entries. The key is POSTed to the local ComfyUI server and stored in a 0600 file;
// it is never a node widget (widget values end up in workflow JSON and media metadata).
const MASK = "••••••••";
const DEFAULT_BASE = "https://api.modelsite.ai";
let ready = false;

async function post(body) {
  const r = await fetch("/modelsite/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    app.extensionManager.toast.add({ severity: "error", summary: "Modelsite", detail: e.error || `HTTP ${r.status}`, life: 6000 });
    return null;
  }
  return r.json();
}

app.registerExtension({
  name: "Modelsite.Settings",
  settings: [
    {
      id: "Modelsite.BaseUrl",
      name: "API base URL",
      type: "text",
      defaultValue: DEFAULT_BASE,
      category: ["Modelsite", "Connection", "BaseUrl"],
      tooltip: "Leave the default unless you were given another address. Reload the page after changing it to refresh the model list.",
      onChange: async (v) => {
        if (!ready || !v) return;
        const st = await post({ base_url: v });
        if (st) app.extensionManager.toast.add({ severity: "success", summary: "Modelsite", detail: "Base URL saved. Reload the page to refresh the model list.", life: 5000 });
      },
    },
    {
      id: "Modelsite.ApiKey",
      name: "API key",
      type: "text",
      defaultValue: "",
      attrs: { type: "password", autocomplete: "off" },
      category: ["Modelsite", "Connection", "ApiKey"],
      tooltip: "Paste your Modelsite API key (starts with sk-ms-). It is stored on this machine only and is never saved into workflows.",
      onChange: async (v) => {
        if (!ready || !v || v === MASK) return;
        const st = await post({ api_key: v });
        if (st) {
          app.extensionManager.setting.set("Modelsite.ApiKey", MASK);
          app.extensionManager.toast.add({ severity: "success", summary: "Modelsite", detail: "API key saved.", life: 5000 });
        }
      },
    },
  ],
  async setup() {
    try {
      const st = await (await fetch("/modelsite/config")).json();
      if (st.key_set) await app.extensionManager.setting.set("Modelsite.ApiKey", MASK);
      if (st.base_url) await app.extensionManager.setting.set("Modelsite.BaseUrl", st.base_url);
    } catch (e) {
      console.warn("[Modelsite] could not read settings", e);
    }
    ready = true;
  },
});
