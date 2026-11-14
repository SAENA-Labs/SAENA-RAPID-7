"use strict";
(() => {
  const id = document.getElementById("report-id");
  const token = document.getElementById("access-token");
  const status = document.getElementById("status");
  const report = document.getElementById("report");
  const loadButton = document.getElementById("load");
  let generation = 0, controller = null;
  function cancel() {
    generation += 1;
    if (controller) controller.abort();
    controller = null; loadButton.disabled = false;
    report.replaceChildren(); report.hidden = true;
    report.removeAttribute("aria-busy");
  }
  function clear() {
    cancel(); token.value = ""; id.value = "";
    status.textContent = "보고서 ID와 임시 토큰을 입력해 주세요.";
  }
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function list(items) {
    const node = element("ul");
    for (const item of items) node.append(element("li", item));
    return node;
  }
  function validate(data) {
    if (!data || data.scope !== "offline_supplied_html" || typeof data.tenant_id !== "string" ||
        !Number.isInteger(data.expected_page_count) || !Number.isInteger(data.measured_page_count) ||
        data.expected_page_count < 1 || data.expected_page_count > 1000 || data.measured_page_count < 0 ||
        !Array.isArray(data.measured_pages) || !Array.isArray(data.unmeasured_pages) ||
        data.measured_pages.length !== data.measured_page_count ||
        data.measured_page_count + data.unmeasured_pages.length !== data.expected_page_count ||
        !Array.isArray(data.warnings) || !Array.isArray(data.limitations)) throw new Error("shape");
    let findings = 0;
    for (const p of data.measured_pages) {
      if (!p || p.measurement !== "supplied_html_only" || typeof p.page_url !== "string" ||
          typeof p.evidence_ref !== "string" || typeof p.html_sha256 !== "string" ||
          !Array.isArray(p.findings) || !Array.isArray(p.unknown)) throw new Error("shape");
      findings += p.findings.length;
      for (const f of p.findings) {
        if (!f || typeof f.detail !== "string" || typeof f.code !== "string" ||
            !["info", "review"].includes(f.level) || !Array.isArray(f.lines)) throw new Error("shape");
      }
    }
    if (findings > 4096) throw new Error("shape");
    return data;
  }
  function render(data) {
    const fragment = document.createDocumentFragment();
    const summary = element("section", undefined, "summary");
    summary.append(element("h2", "진단 범위"), element("p", "고객: " + data.tenant_id));
    const counts = element("div", undefined, "counts");
    for (const [label, value] of [["전체 대상", data.expected_page_count], ["HTML 진단", data.measured_page_count], ["미측정", data.unmeasured_pages.length]]) {
      const box = element("div", undefined, "count");
      box.append(element("span", label), element("strong", String(value))); counts.append(box);
    }
    summary.append(counts); fragment.append(summary);
    if (data.unmeasured_pages.length) {
      const missing = element("section", undefined, "missing");
      missing.append(element("h2", "미측정 페이지"), element("p", "자료가 없어 판단하지 않았습니다. 문제없음으로 간주하지 않습니다."), list(data.unmeasured_pages)); fragment.append(missing);
    }
    for (const p of data.measured_pages) {
      const card = element("section", undefined, "page");
      card.append(element("h3", p.page_url), element("span", "제공된 HTML만 진단", "tag"));
      if (!p.findings.length) card.append(element("p", "제공된 HTML에서 표시할 진단 항목이 없습니다. 실제 검색 적격성이나 성과를 확인한 것은 아닙니다."));
      for (const f of p.findings) {
        const finding = element("div", undefined, "finding");
        finding.append(element("span", f.level === "review" ? "검토 필요" : "정보", "tag"), element("strong", f.code), element("p", f.detail), element("p", "근거 줄: " + (f.lines.join(", ") || "해당 없음"), "detail")); card.append(finding);
      }
      const evidence = element("details"); evidence.append(element("summary", "근거와 확인되지 않은 상태"));
      evidence.append(element("p", "참조: " + p.evidence_ref), element("p", "HTML 해시: " + p.html_sha256), element("p", "제공된 HTTP 상태: " + (p.supplied_http_status ?? "미제공")), element("h3", "확인되지 않음"), list(p.unknown)); card.append(evidence); fragment.append(card);
    }
    const limits = element("section", undefined, "summary");
    limits.append(element("h2", "해석 시 주의사항"), list(data.limitations));
    if (data.warnings.length) limits.append(element("h3", "자료 경고"), list(data.warnings));
    fragment.append(limits); report.replaceChildren(fragment); report.hidden = false;
  }
  const errors = {401:"토큰이 없거나 유효하지 않습니다. 새 임시 토큰을 확인해 주세요.",403:"이 보고서를 읽을 권한이 없습니다.",404:"보고서를 찾을 수 없거나 접근할 수 없습니다.",503:"보고서 자료를 안전하게 확인할 수 없습니다. 관리자 확인이 필요합니다."};
  document.getElementById("load").addEventListener("click", async () => {
    cancel(); const current = generation;
    const reportId = id.value.trim(); let bearer = token.value.trim();
    token.value = "";
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(reportId) || !bearer || bearer.length > 16384) {
      bearer = ""; status.textContent = "올바른 보고서 ID와 임시 토큰을 입력해 주세요."; return;
    }
    controller = new AbortController(); const signal = controller.signal; loadButton.disabled = true;
    status.textContent = "승인된 보고서를 확인하고 있습니다…"; report.setAttribute("aria-busy", "true");
    try {
      const request = fetch("/v1/html-audit-reports/" + encodeURIComponent(reportId), {method:"GET", headers:{Authorization:"Bearer " + bearer}, credentials:"omit", cache:"no-store", redirect:"error", signal});
      bearer = "";
      const response = await request;
      if (current !== generation) return;
      if (!response.ok) { status.textContent = errors[response.status] || "보고서를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요."; return; }
      if (!response.headers.get("content-type")?.startsWith("application/json")) throw new Error("shape");
      const reader = response.body.getReader(); const chunks = []; let size = 0;
      while (true) {
        const {done, value} = await reader.read(); if (done) break;
        size += value.byteLength;
        if (size > 8 * 1024 * 1024) { await reader.cancel(); throw new Error("size"); }
        chunks.push(value);
      }
      if (current !== generation) return;
      const bytes = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
      const data = validate(JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(bytes)));
      if (current !== generation) return;
      render(data); status.textContent = "진단 보고서를 표시했습니다. 실제 검색·인용 성과 보고서가 아닙니다.";
    } catch (error) {
      if (current !== generation) return;
      status.textContent = error.name === "AbortError" ? "요청을 취소했습니다." : "연결 또는 보고서 형식을 확인할 수 없습니다. 다시 시도해 주세요.";
    } finally {
      bearer = "";
      if (current === generation) { controller = null; loadButton.disabled = false; report.removeAttribute("aria-busy"); }
    }
  });
  document.getElementById("clear").addEventListener("click", () => { clear(); id.focus(); });
  for (const input of [id, token]) input.addEventListener("input", () => { cancel(); status.textContent = "입력한 정보로 새로 조회해 주세요."; });
  for (const input of [id, token]) input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); document.getElementById("load").click(); } });
  window.addEventListener("pagehide", clear); window.addEventListener("pageshow", clear);
})();
