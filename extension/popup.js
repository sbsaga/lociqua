const $ = id => document.getElementById(id);
const message = value => { $("message").textContent = value || ""; };
let page = null;
async function request(path, options = {}) {
  const {baseUrl, token} = await chrome.storage.session.get(["baseUrl", "token"]);
  if (!baseUrl || !token) throw new Error("Configure the Lociqua URL and a short-lived access token first.");
  const response = await fetch(baseUrl.replace(/\/$/, "") + path, { ...options, headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(options.headers || {})} });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "Lociqua request failed");
  return body;
}
async function activePage() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id || !tab.url?.startsWith("http")) throw new Error("Open a normal HTTP(S) page before capturing evidence.");
  const [{result}] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => ({title: document.title.slice(0, 500), selection: String(window.getSelection() || "").slice(0, 2000), url: location.href})});
  return result;
}
async function initialise() {
  const stored = await chrome.storage.session.get(["baseUrl", "token"]);
  $("baseUrl").value = stored.baseUrl || "";
  if (!stored.baseUrl || !stored.token) return;
  page = await activePage(); $("page").textContent = `Page: ${page.url}`;
  const data = await request(`/api/source-policies?domain=${encodeURIComponent(new URL(page.url).hostname)}`);
  const policies = data.source_policies || [];
  if (!policies.length) throw new Error("This domain has no approved browser-capture source policy. Ask a Lociqua owner to approve it.");
  policies.forEach(item => { const option = document.createElement("option"); option.value = item.id; option.textContent = `${item.name} — ${item.domain}`; $("policy").append(option); });
  $("name").value = page.title || ""; $("description").value = page.selection || "";
  $("setup").classList.add("hidden"); $("capture").classList.remove("hidden");
}
$("saveSetup").onclick = async () => { try { const url = new URL($("baseUrl").value); if (url.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(url.hostname)) throw new Error("Use HTTPS except for local development."); await chrome.storage.session.set({baseUrl: url.origin, token: $("token").value.trim()}); await initialise(); } catch (error) { message(error.message); } };
$("captureButton").onclick = async () => { try { if (!page) throw new Error("Page information is unavailable."); const fields = {}; ["name", "website", "phone", "address", "city", "description"].forEach(key => { const value = $(key).value.trim(); if (value) fields[key] = value; }); if (!fields.name) throw new Error("Company name is required."); if (!confirm("Save only these confirmed fields and this page URL to Lociqua?")) return; const data = await request("/api/evidence/capture", {method: "POST", body: JSON.stringify({source_policy_id: $("policy").value, capture_url: page.url, fields})}); message(`Saved evidence ${data.evidence_id}. It is pending review.`); $("captureButton").disabled = true; } catch (error) { message(error.message); } };
initialise().catch(error => message(error.message));
