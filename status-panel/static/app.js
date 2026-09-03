"use strict";

const app = document.getElementById("app");
const state = {
  status: null,
  models: null,
  events: [],
  statusError: false,
  modelsError: false,
};

const serviceOrder = [
  ["gateway", "网关", "127.0.0.1:8317"],
  ["agent", "Agent", "127.0.0.1:8642"],
  ["studio", "Studio", "127.0.0.1:8648"],
  ["antigravity", "Antigravity", "本机模型目录"],
];

const groupOrder = ["Gemini", "Claude", "GPT / Other"];

const emptySummary = {
  total: 0,
  available: 0,
  new: 0,
  unavailable: 0,
  mismatch: 0,
};

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function overallStatusText(value) {
  if (value === "healthy") return "一切正常";
  if (value === "attention") return "基本正常";
  if (value === "error") return "需要注意";
  return "读取中";
}

function serviceStatusText(value) {
  if (value === "healthy") return "正常";
  if (value === "attention") return "异常";
  if (value === "error") return "离线";
  return "读取中";
}

function modelStatusText(value) {
  if (value === "available") return "可用";
  if (value === "new") return "新发现";
  if (value === "mismatch") return "配置不一致";
  return "暂不可用";
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function relativeTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 172800) return "昨天";
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

async function getJson(path) {
  const response = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function sectionTitle(eyebrow, title, note) {
  const row = node("div", "section-heading");
  const copy = node("div", "section-heading-copy");
  copy.append(node("p", "eyebrow", eyebrow), node("h2", null, title));
  row.append(copy, node("span", "section-note", note));
  return row;
}

function modelSummaryParts(summary) {
  return [
    ["", `${summary.total} 个模型`],
    ["good", `${summary.available} 可用`],
    ["new", `${summary.new} 新发现`],
    ["warn", `${summary.mismatch} 不一致`],
    ["quiet", `${summary.unavailable} 暂不可用`],
  ];
}

function shortModelSummary(response) {
  const summary = response?.summary || emptySummary;
  const items = [];
  if (summary.available) items.push(`${summary.available} 可用`);
  if (summary.new) items.push(`${summary.new} 新发现`);
  if (summary.unavailable) items.push(`${summary.unavailable} 暂不可用`);
  if (summary.mismatch) items.push(`${summary.mismatch} 不一致`);
  return items.length ? items.join(" · ") : "等待模型目录";
}

function topbarBlock() {
  const current = state.statusError ? "error" : state.status?.overall || "unknown";
  const header = node("header", "topbar");

  const brand = node("div", "brand-lockup");
  brand.append(
    node("div", "mark", "H"),
    (() => {
      const copy = node("div", "brand-copy");
      copy.append(node("span", "brand-name", "Hermes 状态"), node("span", "brand-sub", "本地只读面板"));
      return copy;
    })(),
  );

  const overall = node("div", `overall-inline state-${current}`);
  overall.append(node("span", "status-dot"));
  const overallCopy = node("div", "overall-copy");
  overallCopy.append(
    node("span", "overall-label", overallStatusText(current)),
    node("span", "topbar-summary", shortModelSummary(state.models)),
  );
  overall.append(overallCopy);

  const actions = node("nav", "topbar-actions");
  actions.setAttribute("aria-label", "快捷入口");
  actions.append(
    node(
      "span",
      "last-check",
      state.status?.checked_at ? `最后检查 ${formatTime(state.status.checked_at)}` : "最后检查 —",
    ),
  );
  const studio = node("a", "action-link primary", "打开 Studio");
  studio.href = "http://127.0.0.1:8648/";
  const dashboard = node("a", "action-link secondary", "打开 Hermes 后台");
  dashboard.href = "http://127.0.0.1:9119/";
  actions.append(studio, dashboard);

  header.append(brand, overall, actions);
  return header;
}

function connectionsBlock() {
  const section = node("section", "connections-section");
  section.append(sectionTitle("连接状态", "四项连接", "悬停或聚焦查看地址与检查时间"));
  const panel = node("div", "connection-panel");
  const strip = node("div", "connection-strip");
  for (const [key, label, address] of serviceOrder) {
    const service = state.status?.services?.[key];
    const current = service?.status || "unknown";
    const item = node("article", `connection-item state-${current}`);
    const checked = state.status?.checked_at ? formatTime(state.status.checked_at) : "—";
    const tooltip = `${address} · 最后检查 ${checked}`;
    item.tabIndex = 0;
    item.setAttribute("role", "group");
    item.setAttribute("aria-label", `${label}，${serviceStatusText(current)}，${tooltip}`);
    item.dataset.tooltip = tooltip;
    item.title = tooltip;
    item.append(node("span", "connection-dot"));
    const copy = node("div", "connection-copy");
    copy.append(node("span", "connection-name", label), node("span", "connection-status", serviceStatusText(current)));
    item.append(copy);
    strip.append(item);
  }
  panel.append(strip);
  section.append(panel);
  return section;
}

function groupForModel(model) {
  const source = `${model.provider || ""} ${model.name || ""} ${model.id || ""}`.toLowerCase();
  if (source.includes("gemini")) return "Gemini";
  if (source.includes("claude")) return "Claude";
  return "GPT / Other";
}

function detailField(label, value, code) {
  const field = node("div", "detail-field");
  const valueNode = node("dd", code ? "code" : null, value || "—");
  field.append(node("dt", null, label), valueNode);
  return field;
}

function detailsBlock(model) {
  const details = node("div", "model-details");
  const grid = node("dl", "details-grid");
  grid.append(
    detailField("模型 ID", model.id, true),
    detailField("Live Catalog", model.liveCatalog || model.live),
    detailField("Studio", model.studio || model.visible),
    detailField("首次发现", formatTime(model.first_seen)),
    detailField("最后检查", formatTime(model.last_seen)),
  );
  details.append(grid);
  return details;
}

function modelRow(model) {
  const status = model.status || "unavailable";
  const item = node("details", "model-row");
  const summary = node("summary", "model-row-summary");
  summary.append(
    node("span", `model-status-dot ${status}`),
    node("span", "model-name", model.name || model.id || "未命名模型"),
    node("span", `model-state ${status}`, modelStatusText(status)),
    node("span", "model-chevron", "⌄"),
  );
  item.append(summary, detailsBlock(model));
  return item;
}

function modelsBlock() {
  const response = state.models;
  const summary = response?.summary || emptySummary;
  const panel = node("section", "panel models-panel");
  panel.append(
    sectionTitle(
      "模型状态",
      "模型",
      response?.checked_at ? `更新于 ${formatTime(response.checked_at)}` : "等待读取",
    ),
  );

  const totals = node("div", "model-summary");
  for (const [className, text] of modelSummaryParts(summary)) {
    totals.append(node("span", `summary-item ${className}`.trim(), text));
  }
  panel.append(totals);

  if (state.modelsError) {
    panel.append(node("p", "empty", "模型目录暂时无法读取，正在等待下一次本地检查。"));
    return panel;
  }

  const rows = response?.models || [];
  if (!rows.length) {
    panel.append(node("p", "empty", "模型目录暂未返回数据。"));
    return panel;
  }

  const groups = new Map(groupOrder.map((group) => [group, []]));
  for (const model of rows) groups.get(groupForModel(model)).push(model);

  const groupList = node("div", "model-groups");
  for (const group of groupOrder) {
    const models = groups.get(group);
    if (!models.length) continue;
    const groupSection = node("section", "model-group");
    const heading = node("div", "model-group-heading");
    heading.append(node("h3", null, group), node("span", "model-group-count", `${models.length} 个`));
    const list = node("div", "model-list");
    for (const model of models) list.append(modelRow(model));
    groupSection.append(heading, list);
    groupList.append(groupSection);
  }
  panel.append(groupList);
  return panel;
}

function eventsBlock() {
  const panel = node("aside", "panel events-panel");
  panel.append(sectionTitle("状态变化", "最近提醒", "最多 3 条"));
  const events = state.events.slice(0, 3);
  if (!events.length) {
    panel.append(node("p", "empty", "暂无需要注意的变化"));
    return panel;
  }
  const list = node("ol", "event-list");
  for (const event of events) {
    const item = node("li", "event-item");
    const copy = node("div", "event-copy");
    copy.append(node("strong", "event-title", event.title || "状态发生变化"), node("time", "event-time", relativeTime(event.time)));
    item.append(node("span", "event-dot"), copy);
    list.append(item);
  }
  panel.append(list);
  return panel;
}

function render() {
  if (!app) return;
  const page = node("div", "page");
  const main = node("div", "content-grid");
  main.append(modelsBlock(), eventsBlock());
  const footer = node("footer", "page-footer");
  footer.append(
    node("span", null, "数据来自本机服务与本地模型目录"),
    (() => {
      const link = node("a", null, "只读 · 127.0.0.1");
      link.href = "http://127.0.0.1:9120/";
      return link;
    })(),
  );
  page.append(topbarBlock(), connectionsBlock(), main, footer);
  app.replaceChildren(page);
}

async function loadStatus() {
  try {
    state.status = await getJson("/api/status");
    state.statusError = false;
  } catch {
    state.statusError = true;
  }
  render();
}

async function loadModels() {
  try {
    state.models = await getJson("/api/models");
    state.modelsError = false;
  } catch {
    state.modelsError = true;
  }
  render();
}

async function loadEvents() {
  try {
    const response = await getJson("/api/events");
    state.events = Array.isArray(response.events) ? response.events.slice(0, 3) : [];
  } catch {
    // Keep the last successful reminder list.
  }
  render();
}

document.title = "Hermes 状态面板";
render();
void loadStatus();
void loadModels();
void loadEvents();
window.setInterval(() => void loadStatus(), 15_000);
window.setInterval(() => void loadModels(), 60_000);
window.setInterval(() => void loadEvents(), 30_000);
