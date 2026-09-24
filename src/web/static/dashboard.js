/**
 * TigerGraph CrimeLab - Agentic Fraud Investigation Workbench Client
 * High-Density Operations Console with Interactive Canvas Graph,
 * Timeline Velocity Stream, Real-Time Evidence Sandbox & FinCEN SAR Filing
 */

let allCases = [];
let currentCase = null;
let currentFilter = "all";
let searchQuery = "";
let currentCaseMeta = null;

// Canvas & Graph State
let canvas, ctx;
let nodes = [];
let links = [];
let particles = [];
let animationFrameId = null;
let isPhysicsPaused = false;

// Zoom & Pan State
let zoomLevel = 1.0;
let panOffset = { x: 0, y: 0 };
let isPanning = false;
let panStart = { x: 0, y: 0 };
let draggedNode = null;
let hoveredNode = null;
let selectedNode = null;

// Audit Trail Log
const auditLogs = [];

document.addEventListener("DOMContentLoaded", () => {
    initCanvas();
    setupEventListeners();
    loadDashboardData();
});

// -----------------------------------------------------------------------------
// Data Loading & Initialization
// -----------------------------------------------------------------------------
async function loadDashboardData() {
    await loadStats();
    await loadCases();
    if (allCases.length > 0) {
        selectCase(allCases[0].case_id);
    }
}

async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        document.getElementById("kpi-cases").innerText = data.total_cases || "20";
        document.getElementById("kpi-fraud").innerText = data.fraud_confirmed || "0";
        document.getElementById("kpi-uncertain").innerText = data.uncertain || "0";
        document.getElementById("kpi-legit").innerText = data.cleared_legitimate || "0";
        document.getElementById("kpi-sar").innerText = data.sar_filings_count || "0";
        document.getElementById("kpi-exposure").innerText = `$${(data.total_exposure_usd || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;
    } catch (err) {
        console.error("Failed to load KPI stats:", err);
    }
}

async function loadCases() {
    try {
        const res = await fetch("/api/cases");
        allCases = await res.json();
        renderCaseList();
    } catch (err) {
        console.error("Failed to load case list:", err);
    }
}

// -----------------------------------------------------------------------------
// Case Navigator & Triage Stream
// -----------------------------------------------------------------------------
function renderCaseList() {
    const container = document.getElementById("cases-list");
    container.innerHTML = "";

    const query = searchQuery.toLowerCase().trim();
    const filtered = allCases.filter(c => {
        // Filter pills
        if (currentFilter !== "all" && c.verdict !== currentFilter) {
            return false;
        }
        // Search query
        if (query) {
            const matchId = (c.case_id || "").toLowerCase().includes(query);
            const matchCard = (c.card_id || "").toLowerCase().includes(query);
            const matchCust = (c.customer_id || "").toLowerCase().includes(query);
            const matchPattern = (c.pattern || "").toLowerCase().includes(query);
            if (!matchId && !matchCard && !matchCust && !matchPattern) return false;
        }
        return true;
    });

    document.getElementById("filtered-case-count").innerText = `${filtered.length} ALERTS`;

    filtered.forEach(c => {
        const item = document.createElement("div");
        const isSelected = currentCase && currentCase.case_id === c.case_id;
        item.className = `case-item-card ${isSelected ? "active" : ""}`;
        item.onclick = () => selectCase(c.case_id);

        const verdict = c.verdict || "uncertain";
        const scoreDisplay = c.risk_score !== null ? `Score: ${c.risk_score.toFixed(2)}` : "Disputed";
        const exposureDisplay = c.exposure_usd > 0 ? `$${c.exposure_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "$0.00";
        
        // Mini progress bar width based on risk score or verdict
        let barPercent = 40;
        let barColor = "var(--threat-warning)";
        if (verdict === "fraud") {
            barPercent = 95;
            barColor = "var(--threat-danger)";
        } else if (verdict === "legitimate") {
            barPercent = 10;
            barColor = "var(--threat-success)";
        } else if (c.risk_score) {
            barPercent = Math.min(100, Math.max(10, c.risk_score * 100));
        }

        item.innerHTML = `
            <div class="case-item-top">
                <span class="case-id-code">${c.case_id}</span>
                <span class="chip-status ${verdict}">${verdict}</span>
            </div>
            <div class="case-item-tokens">${c.card_id} • ${c.customer_id}</div>
            <div class="case-item-typology">${(c.pattern || c.trigger_type || "unclassified").replace(/_/g, " ")}</div>
            <div class="case-item-footer">
                <div class="risk-bar-track">
                    <div class="risk-bar-fill" style="width: ${barPercent}%; background: ${barColor};"></div>
                </div>
                <span class="exposure-amount" style="color: ${c.exposure_usd > 0 ? 'var(--threat-danger)' : 'var(--text-muted)'}">${exposureDisplay}</span>
            </div>
        `;
        container.appendChild(item);
    });
}

// -----------------------------------------------------------------------------
// Case Selection & Dossier Presentation
// -----------------------------------------------------------------------------
async function selectCase(caseId) {
    try {
        const res = await fetch(`/api/cases/${caseId}`);
        if (!res.ok) return;
        currentCase = await res.json();
        currentCaseMeta = allCases.find(x => x.case_id === caseId) || {};

        renderCaseList();
        renderDossier(currentCase, currentCaseMeta);
        loadGraph(caseId);
        loadTimeline(caseId);

        addAuditLog(`Loaded intelligence dossier for case ${caseId} (${currentCaseMeta.customer_id || ""})`);
    } catch (err) {
        console.error("Failed to select case:", err);
    }
}

function renderDossier(data, meta) {
    const c = data.case || {};
    const sar = data.sar || {};
    const nba = data.next_best_actions || {};

    // 1. Headline Banner
    document.getElementById("view-case-id").innerText = `${data.case_id} — ${(c.pattern || meta.trigger_type || "SUSPICIOUS ACTIVITY").replace(/_/g, " ").toUpperCase()}`;

    const statusTag = document.getElementById("view-status-tag");
    const verdict = c.verdict || "uncertain";
    statusTag.className = `badge-verdict ${verdict}`;
    statusTag.innerText = `VERDICT: ${verdict.toUpperCase()}`;
    if (verdict === "fraud") {
        statusTag.style.background = "var(--threat-danger-bg)";
        statusTag.style.color = "var(--threat-danger)";
        statusTag.style.borderColor = "rgba(239, 68, 68, 0.4)";
    } else if (verdict === "legitimate") {
        statusTag.style.background = "var(--threat-success-bg)";
        statusTag.style.color = "var(--threat-success)";
        statusTag.style.borderColor = "rgba(16, 185, 129, 0.4)";
    } else {
        statusTag.style.background = "var(--threat-warning-bg)";
        statusTag.style.color = "var(--threat-warning)";
        statusTag.style.borderColor = "rgba(245, 158, 11, 0.4)";
    }

    const patternTag = document.getElementById("view-pattern-tag");
    patternTag.innerText = `PATTERN: ${(c.pattern || "none").replace(/_/g, " ").toUpperCase()}`;

    const channelTag = document.getElementById("view-channel-tag");
    channelTag.innerText = (meta.trigger_type === "customer_report" ? "ONLINE DISPUTE" : (meta.trigger_type === "risk_score" ? "ML ALERT GATE" : "ANALYST ESCALATION")).toUpperCase();

    document.getElementById("view-cust-id").innerText = meta.customer_id || "--";
    document.getElementById("view-card-id").innerText = meta.card_id || "--";
    document.getElementById("view-txn-id").innerText = meta.flagged_txn_id || "--";
    document.getElementById("view-opened-date").innerText = meta.opened_at || "--";
    
    const triggerDescEl = document.getElementById("view-trigger-desc");
    if (meta.trigger_text) {
        triggerDescEl.style.display = "block";
        triggerDescEl.innerText = `Alert Signal: "${meta.trigger_text}"`;
    } else {
        triggerDescEl.style.display = "none";
    }

    // 2. Radial Gauge & Meters
    const prob = c.fraud_probability !== undefined ? c.fraud_probability : 0.0;
    const probPercent = Math.round(prob * 100);
    document.getElementById("view-fraud-prob").innerText = `${probPercent}%`;
    
    const gaugeBar = document.getElementById("gauge-prob-bar");
    const circumference = 2 * Math.PI * 40; // 251.2
    const offset = circumference - (prob * circumference);
    gaugeBar.style.strokeDashoffset = offset;
    gaugeBar.style.stroke = prob >= 0.7 ? "var(--threat-danger)" : (prob >= 0.3 ? "var(--threat-warning)" : "var(--threat-success)");

    const scoreVal = meta.risk_score !== null && meta.risk_score !== undefined ? meta.risk_score.toFixed(2) : "--";
    document.getElementById("view-model-score").innerText = scoreVal;
    document.getElementById("view-exposure").innerText = `$${(c.exposure_usd || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

    // 3. Next-Best Actions Deck
    renderActionsDeck("initial-actions-deck", nba.initial || []);
    renderActionsDeck("final-actions-deck", nba.final || []);
    document.getElementById("what-changed-text").innerText = nba.what_changed || "Pre-evidence initial assessment aligns with standard operational guidelines.";

    // Update Right Panel Sign-off Console
    const topFinalAction = (nba.final && nba.final.length > 0) ? nba.final[0] : null;
    const signoffRoute = topFinalAction ? topFinalAction.route : "auto";
    const routeEl = document.getElementById("signoff-route-badge");
    routeEl.innerText = signoffRoute.toUpperCase();
    routeEl.className = `route-badge route-${signoffRoute}`;

    const exposureVal = c.exposure_usd || 0;
    document.getElementById("signoff-threshold-text").innerText = exposureVal > 2500 ? "> $2,500 (L2 Fraud Manager Approval)" : "≤ $2,500 (Auto / L1 Lead Approval)";

    // 4. Evidence Ledger (Tab 3)
    const ledger = document.getElementById("evidence-ledger");
    ledger.innerHTML = "";
    const evidenceList = c.evidence || [];
    document.getElementById("evidence-claims-count").innerText = `${evidenceList.length} Grounding Claims`;

    evidenceList.forEach(e => {
        const row = document.createElement("div");
        row.className = "evidence-card-entry";
        row.innerHTML = `
            <div class="evidence-header-line">
                <span class="evidence-src-pill">TIGERGRAPH · ${e.source}</span>
                <span class="evidence-ref-tag">${e.ref}</span>
            </div>
            <div class="evidence-claim-text">${e.claim}</div>
        `;
        ledger.appendChild(row);
    });

    // 5. FinCEN SAR Regulatory Dossier (Tab 5)
    renderSARDossier(sar, data.case_id, c);
}

function renderActionsDeck(containerId, actions) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    if (!actions || actions.length === 0) {
        container.innerHTML = `<div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); padding: 0.5rem;">No actions recommended</div>`;
        return;
    }

    actions.forEach(a => {
        const ticket = document.createElement("div");
        ticket.className = "action-ticket-card";
        ticket.innerHTML = `
            <div class="action-ticket-top">
                <span class="action-code-title">${a.action}</span>
                <span class="route-badge route-${a.route}">${a.route}</span>
            </div>
            <div class="action-policy-reason">${a.reason}</div>
        `;
        container.appendChild(ticket);
    });
}

function renderSARDossier(sar, caseId, c) {
    const container = document.getElementById("sar-dossier-content");
    if (sar.file) {
        container.innerHTML = `
            <div class="sar-watermark-strip">
                <span>FinCEN Form 111 Suspicious Activity Report</span>
                <span>REGULATORY FILING STATUS: MANDATORY FILING SUBMITTED</span>
            </div>
            <div class="sar-fields-grid">
                <div class="sar-field-item">
                    <span class="sar-field-k">CASE TRACKING ID:</span>
                    <span class="sar-field-v">${caseId}</span>
                </div>
                <div class="sar-field-item">
                    <span class="sar-field-k">ACTIVITY DATES:</span>
                    <span class="sar-field-v">${(sar.activity_dates || []).join(" to ") || "2016-12-01"}</span>
                </div>
                <div class="sar-field-item">
                    <span class="sar-field-k">TOTAL EXPOSURE:</span>
                    <span class="sar-field-v" style="color: var(--threat-danger);">$${(sar.total_amount_usd || 0).toLocaleString(undefined, {minimumFractionDigits: 2})} USD</span>
                </div>
                <div class="sar-field-item" style="grid-column: span 3;">
                    <span class="sar-field-k">PRIMARY SUBJECT ENTITIES & CARDS:</span>
                    <span class="sar-field-v">${(sar.subjects || []).join(", ") || "Unknown Syndicate Ring"}</span>
                </div>
            </div>
            <div>
                <div style="font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                    SECTION V — SUSPICIOUS ACTIVITY NARRATIVE (OFFICIAL FinCEN SUBMISSION):
                </div>
                <div class="sar-narrative-terminal" id="sar-narrative-text">${sar.narrative}</div>
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="sar-watermark-strip" style="color: var(--text-muted); border-color: var(--border-subtle); background: rgba(255,255,255,0.02);">
                <span>Regulatory Filing Assessment</span>
                <span>STATUS: NO FILING REQUIRED</span>
            </div>
            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; font-style: italic; padding: 1rem 0;">
                Under Bank Fraud Policy v1.0 Section 3a, this case does not warrant an official FinCEN Form 111 Suspicious Activity Report.
                <br><br>
                <strong>Evaluation Rationale:</strong> ${sar.reason || "Loss exposure is below mandatory regulatory reporting thresholds and no multi-entity syndicate ring was discovered during TigerGraph GSQL graph traversal."}
            </p>
        `;
    }
}

// -----------------------------------------------------------------------------
// Timeline Velocity Stream (Tab 2)
// -----------------------------------------------------------------------------
async function loadTimeline(caseId) {
    const container = document.getElementById("timeline-stream");
    const badge = document.getElementById("timeline-count-badge");
    try {
        const res = await fetch(`/api/cases/${caseId}/timeline`);
        if (!res.ok) {
            container.innerHTML = `<div class="timeline-empty-state">No transaction history found for this card.</div>`;
            badge.innerText = "0 Transactions";
            return;
        }
        const data = await res.json();
        const txns = data.timeline || [];
        badge.innerText = `${txns.length} Transactions`;

        if (txns.length === 0) {
            container.innerHTML = `<div class="timeline-empty-state">No transactions recorded for card ${data.card_id}.</div>`;
            return;
        }

        container.innerHTML = "";
        txns.forEach(t => {
            const row = document.createElement("div");
            row.className = `timeline-entry-row ${t.is_affected ? "affected" : (t.is_flagged ? "flagged" : "")}`;
            
            let statusBadge = `<span style="color: var(--text-muted);">NORMAL</span>`;
            if (t.is_affected) {
                statusBadge = `<span style="color: var(--threat-danger); font-weight: 700;">FRAUD ATTRIBUTED</span>`;
            } else if (t.is_flagged) {
                statusBadge = `<span style="color: var(--threat-warning); font-weight: 700;">FLAGGED ALERT</span>`;
            }

            row.innerHTML = `
                <div>${t.ts || "--"}</div>
                <div><strong style="color: #fff;">Txn #${t.txn_id}</strong></div>
                <div style="color: var(--text-secondary);">${t.channel.toUpperCase()} ${t.dist1 ? `· Dist: ${t.dist1}mi` : ''}</div>
                <div style="font-weight: 700; color: ${t.is_affected ? 'var(--threat-danger)' : '#fff'};">$${t.amount.toFixed(2)}</div>
                <div>${statusBadge}</div>
            `;
            container.appendChild(row);
        });

    } catch (err) {
        console.error("Failed to load timeline:", err);
        container.innerHTML = `<div class="timeline-empty-state">Error loading timeline stream.</div>`;
    }
}

// -----------------------------------------------------------------------------
// Interactive Evidence Simulation Sandbox
// -----------------------------------------------------------------------------
async function simulateEvidence(responseString, actionType) {
    if (!currentCase) return;
    const meta = allCases.find(x => x.case_id === currentCase.case_id);
    if (!meta) return;

    addAuditLog(`Simulating ${actionType} for Cardholder ${meta.customer_id}...`);

    const reqBody = {
        case_id: currentCase.case_id,
        flagged_txn_id: meta.flagged_txn_id,
        card_id: meta.card_id,
        customer_id: meta.customer_id,
        trigger_type: meta.trigger_type,
        trigger_text: meta.trigger_text,
        risk_score: meta.risk_score,
        override_customer_response: responseString
    };

    try {
        const res = await fetch("/api/investigate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reqBody)
        });
        currentCase = await res.json();
        renderDossier(currentCase, meta);
        await loadStats();
        await loadCases();
        loadGraph(currentCase.case_id);

        addAuditLog(`Agent updated decision state. Verdict: ${currentCase.case.verdict.toUpperCase()}`);
    } catch (err) {
        console.error("Simulation failed:", err);
    }
}

function addAuditLog(msg) {
    const stream = document.getElementById("audit-stream");
    const timeStr = new Date().toTimeString().split(" ")[0];
    auditLogs.unshift({ time: timeStr, msg });

    const item = document.createElement("div");
    item.className = "audit-item";
    item.innerHTML = `
        <span class="audit-time">${timeStr}</span>
        <span class="audit-msg">${msg}</span>
    `;
    stream.prepend(item);
}

// -----------------------------------------------------------------------------
// Event Listeners & UI Controls
// -----------------------------------------------------------------------------
function setupEventListeners() {
    // 1. Triage Filter Chips
    document.querySelectorAll(".filter-chip").forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll(".filter-chip").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentFilter = btn.dataset.filter;
            renderCaseList();
        };
    });

    // 2. Search Input
    const searchInput = document.getElementById("case-search-input");
    searchInput.oninput = (e) => {
        searchQuery = e.target.value;
        renderCaseList();
    };

    // Global keyboard shortcut: / or ⌘K
    window.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "k") {
            e.preventDefault();
            searchInput.focus();
        } else if (e.key === "/" && document.activeElement !== searchInput) {
            e.preventDefault();
            searchInput.focus();
        }
    });

    // 3. Dossier Tabs
    document.querySelectorAll(".dossier-tab").forEach(tab => {
        tab.onclick = () => {
            document.querySelectorAll(".dossier-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            tab.classList.add("active");
            const targetId = tab.dataset.tab;
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add("active");

            // Trigger canvas resize if graph tab activated
            if (targetId === "tab-graph") {
                resizeCanvas();
            }
        };
    });

    // 4. Evidence Sandbox Buttons
    document.getElementById("btn-sim-deny").onclick = () => {
        simulateEvidence("Customer states they did not make these purchases and still has the card in their possession.", "Denial of Charge");
    };

    document.getElementById("btn-sim-confirm").onclick = () => {
        simulateEvidence("Customer confirms legitimate travel to the billing region in question and validated the purchase.", "Legitimate Confirmation");
    };

    document.getElementById("btn-sim-timeout").onclick = () => {
        simulateEvidence("No reply received from cardholder within 24 hours of inquiry.", "24h SLA Timeout");
    };

    // 5. SAR Action Buttons
    document.getElementById("btn-copy-sar").onclick = () => {
        const textEl = document.getElementById("sar-narrative-text");
        if (textEl && textEl.innerText) {
            navigator.clipboard.writeText(textEl.innerText);
            alert("FinCEN Suspicious Activity Report Narrative copied to clipboard.");
        } else {
            alert("No SAR narrative required or generated for this case.");
        }
    };

    document.getElementById("btn-download-sar").onclick = () => {
        if (!currentCase || !currentCase.sar) return;
        const blob = new Blob([JSON.stringify(currentCase.sar, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `SAR_${currentCase.case_id}_FinCEN_Form111.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // 6. Officer Sign-off Execution
    document.getElementById("btn-execute-signoff").onclick = () => {
        const feedback = document.getElementById("signoff-feedback");
        const actionCode = currentCase?.next_best_actions?.final?.[0]?.action || "VERIFY_WITH_CUSTOMER";
        feedback.innerText = `Action ${actionCode} recorded in case log.`;
        addAuditLog(`Officer sign-off completed for ${currentCase.case_id}. Action: ${actionCode}`);
        setTimeout(() => { feedback.innerText = ""; }, 4000);
    };

    // 7. Re-evaluate All
    const btnReEval = document.getElementById("btn-re-eval");
    btnReEval.onclick = async () => {
        btnReEval.disabled = true;
        const labelSpan = btnReEval.querySelector("span:last-child");
        if (labelSpan) labelSpan.innerText = "Running...";
        addAuditLog("Re-evaluating 20-alert benchmark suite...");

        try {
            for (const c of allCases) {
                await fetch("/api/investigate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(c)
                });
            }
            await loadStats();
            await loadCases();
            if (currentCase) selectCase(currentCase.case_id);
            addAuditLog("Benchmark execution complete. 20 case outputs updated.");
        } finally {
            btnReEval.disabled = false;
            if (labelSpan) labelSpan.innerText = "Re-Run Benchmark";
        }
    };

    // 8. Canvas Toolbar Controls
    document.getElementById("btn-zoom-in").onclick = () => { zoomLevel = Math.min(2.5, zoomLevel * 1.25); };
    document.getElementById("btn-zoom-out").onclick = () => { zoomLevel = Math.max(0.4, zoomLevel / 1.25); };
    document.getElementById("btn-reset-zoom").onclick = () => { zoomLevel = 1.0; panOffset = { x: 0, y: 0 }; };
    document.getElementById("btn-toggle-physics").onclick = () => {
        isPhysicsPaused = !isPhysicsPaused;
        document.getElementById("btn-toggle-physics").innerText = isPhysicsPaused ? "▶" : "⏸";
    };

    // Close Inspector
    document.getElementById("btn-close-inspector").onclick = () => {
        document.getElementById("node-inspector").classList.remove("open");
        selectedNode = null;
    };
}

// -----------------------------------------------------------------------------
// Interactive Force-Directed Canvas Graph Engine
// -----------------------------------------------------------------------------
function initCanvas() {
    canvas = document.getElementById("graph-canvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Canvas Mouse Events for Zoom, Pan, and Node Dragging
    canvas.addEventListener("wheel", handleCanvasWheel, { passive: false });
    canvas.addEventListener("mousedown", handleCanvasMouseDown);
    canvas.addEventListener("mousemove", handleCanvasMouseMove);
    canvas.addEventListener("mouseup", handleCanvasMouseUp);
    canvas.addEventListener("mouseleave", handleCanvasMouseUp);

    if (!animationFrameId) {
        animationFrameId = requestAnimationFrame(renderGraphStep);
    }
}

function resizeCanvas() {
    if (!canvas || !canvas.parentElement) return;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
}

async function loadGraph(caseId) {
    try {
        const res = await fetch(`/api/cases/${caseId}/graph`);
        if (!res.ok) return;
        const data = await res.json();
        setupNodesAndLinks(data);
    } catch (err) {
        console.error("Failed to load graph nodes:", err);
    }
}

function setupNodesAndLinks(data) {
    const rect = canvas.getBoundingClientRect();
    const width = rect.width || 600;
    const height = rect.height || 450;

    nodes = data.nodes.map((n, i) => {
        const angle = (i / data.nodes.length) * Math.PI * 2;
        const dist = n.type === "case" ? 0 : (n.type === "device" ? 140 : 170 + Math.random() * 40);
        return {
            ...n,
            x: width / 2 + Math.cos(angle) * dist,
            y: height / 2 + Math.sin(angle) * dist,
            vx: 0,
            vy: 0,
            pulse: Math.random() * Math.PI * 2
        };
    });

    const nodeMap = {};
    nodes.forEach(n => nodeMap[n.id] = n);

    links = data.links.map(l => ({
        source: nodeMap[l.source],
        target: nodeMap[l.target],
        relation: l.relation,
        animated: l.animated
    })).filter(l => l.source && l.target);

    // Generate traveling particle packets for animated fraud links
    particles = [];
    links.filter(l => l.animated).forEach(l => {
        particles.push({
            link: l,
            progress: Math.random(),
            speed: 0.008 + Math.random() * 0.005
        });
    });

    panOffset = { x: 0, y: 0 };
    zoomLevel = 1.0;
}

// -----------------------------------------------------------------------------
// Canvas Interactive Events (Pan, Zoom, Drag, Inspect)
// -----------------------------------------------------------------------------
function handleCanvasWheel(e) {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    zoomLevel = Math.max(0.4, Math.min(2.5, zoomLevel * zoomFactor));
}

function getTransformedMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Invert zoom and pan
    const worldX = (mouseX - rect.width / 2 - panOffset.x) / zoomLevel + rect.width / 2;
    const worldY = (mouseY - rect.height / 2 - panOffset.y) / zoomLevel + rect.height / 2;
    return { x: worldX, y: worldY };
}

function handleCanvasMouseDown(e) {
    const pos = getTransformedMousePos(e);

    // Check if clicked a node
    for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        const radius = getNodeRadius(n);
        const dist = Math.hypot(n.x - pos.x, n.y - pos.y);
        if (dist <= radius) {
            draggedNode = n;
            selectedNode = n;
            openNodeInspector(n);
            return;
        }
    }

    // Otherwise pan canvas
    isPanning = true;
    panStart = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
}

function handleCanvasMouseMove(e) {
    const pos = getTransformedMousePos(e);

    if (draggedNode) {
        draggedNode.x = pos.x;
        draggedNode.y = pos.y;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
        return;
    }

    if (isPanning) {
        panOffset.x = e.clientX - panStart.x;
        panOffset.y = e.clientY - panStart.y;
        return;
    }

    // Hover check
    hoveredNode = null;
    for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        const radius = getNodeRadius(n);
        const dist = Math.hypot(n.x - pos.x, n.y - pos.y);
        if (dist <= radius) {
            hoveredNode = n;
            canvas.style.cursor = "pointer";
            return;
        }
    }
    canvas.style.cursor = "grab";
}

function handleCanvasMouseUp() {
    draggedNode = null;
    isPanning = false;
}

function getNodeRadius(n) {
    if (n.type === "case") return 20;
    if (n.type === "customer") return 16;
    if (n.type === "card") return 15;
    if (n.type === "device") return 14;
    if (n.type === "transaction") return 12;
    return 13;
}

function openNodeInspector(node) {
    const drawer = document.getElementById("node-inspector");
    const titleEl = document.getElementById("inspect-node-title");
    const typeEl = document.getElementById("inspect-node-type");
    const propsEl = document.getElementById("inspect-node-props");

    drawer.classList.add("open");
    typeEl.innerText = `${node.type.toUpperCase()} ATTRIBUTES`;
    titleEl.innerText = node.label || node.id;

    propsEl.innerHTML = "";
    const data = node.data || {};
    
    // Standard properties
    Object.entries(data).forEach(([k, v]) => {
        const row = document.createElement("div");
        row.className = "inspector-prop-row";
        row.innerHTML = `
            <span class="prop-k">${k.replace(/_/g, " ").toUpperCase()}</span>
            <span class="prop-v">${v}</span>
        `;
        propsEl.appendChild(row);
    });

    // Degree / connections count
    const connections = links.filter(l => l.source.id === node.id || l.target.id === node.id);
    const connRow = document.createElement("div");
    connRow.className = "inspector-prop-row";
    connRow.innerHTML = `
        <span class="prop-k">GRAPH CONNECTIONS</span>
        <span class="prop-v" style="color: var(--tg-orange);">${connections.length} 1-hop link(s)</span>
    `;
    propsEl.appendChild(connRow);
}

// -----------------------------------------------------------------------------
// Canvas Render Loop with Force Simulation & Particle Glow
// -----------------------------------------------------------------------------
function renderGraphStep() {
    if (!ctx) {
        animationFrameId = requestAnimationFrame(renderGraphStep);
        return;
    }

    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Clear Canvas
    ctx.save();
    ctx.clearRect(0, 0, width, height);

    // Apply Zoom & Pan Transform
    ctx.translate(width / 2 + panOffset.x, height / 2 + panOffset.y);
    ctx.scale(zoomLevel, zoomLevel);
    ctx.translate(-width / 2, -height / 2);

    // Physics Simulation (if not paused and not dragging)
    if (!isPhysicsPaused && nodes.length > 0) {
        // Repulsion
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                let dx = nodes[j].x - nodes[i].x;
                let dy = nodes[j].y - nodes[i].y;
                let dist = Math.hypot(dx, dy) || 1;
                let minDist = 135;
                if (dist < minDist) {
                    let force = (minDist - dist) / dist * 0.05;
                    nodes[i].vx -= dx * force;
                    nodes[i].vy -= dy * force;
                    nodes[j].vx += dx * force;
                    nodes[j].vy += dy * force;
                }
            }
        }

        // Link Spring Forces
        links.forEach(l => {
            let dx = l.target.x - l.source.x;
            let dy = l.target.y - l.source.y;
            let dist = Math.hypot(dx, dy) || 1;
            let targetDist = l.source.type === "case" ? 120 : 90;
            let force = (dist - targetDist) * 0.035;
            l.source.vx += dx / dist * force;
            l.source.vy += dy / dist * force;
            l.target.vx -= dx / dist * force;
            l.target.vy -= dy / dist * force;
        });

        // Center Gravity & Velocity Damping
        nodes.forEach(n => {
            if (n === draggedNode) return;
            n.vx += (width / 2 - n.x) * 0.008;
            n.vy += (height / 2 - n.y) * 0.008;
            n.vx *= 0.84;
            n.vy *= 0.84;
            n.x += n.vx;
            n.y += n.vy;
            n.pulse += 0.04;
        });
    }

    // 1. Draw Links
    links.forEach(l => {
        const isHovered = (hoveredNode && (l.source === hoveredNode || l.target === hoveredNode));
        const isSuspicious = l.animated || (currentCase && currentCase.case && currentCase.case.verdict === "fraud");

        ctx.beginPath();
        ctx.moveTo(l.source.x, l.source.y);
        ctx.lineTo(l.target.x, l.target.y);

        if (isHovered) {
            ctx.strokeStyle = "rgba(249, 115, 22, 0.9)";
            ctx.lineWidth = 2.5;
        } else if (isSuspicious) {
            ctx.strokeStyle = "rgba(239, 68, 68, 0.4)";
            ctx.lineWidth = 1.6;
        } else {
            ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
            ctx.lineWidth = 1.2;
        }
        ctx.stroke();

        // Edge label (drawn if hovered)
        if (isHovered && l.relation) {
            const midX = (l.source.x + l.target.x) / 2;
            const midY = (l.source.y + l.target.y) / 2;
            ctx.fillStyle = "rgba(249, 115, 22, 0.9)";
            ctx.font = "bold 9px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText(l.relation, midX, midY - 4);
        }
    });

    // 2. Draw Traveling Animated Particles along Fraud Links
    particles.forEach(p => {
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;

        const src = p.link.source;
        const tgt = p.link.target;
        const px = src.x + (tgt.x - src.x) * p.progress;
        const py = src.y + (tgt.y - src.y) * p.progress;

        ctx.beginPath();
        ctx.arc(px, py, 3, 0, Math.PI * 2);
        ctx.fillStyle = "var(--tg-orange)";
        ctx.shadowColor = "var(--tg-orange)";
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
    });

    // 3. Draw Nodes
    nodes.forEach(n => {
        const radius = getNodeRadius(n);
        let color = "#38bdf8";

        if (n.type === "case") {
            color = "#f97316";
        } else if (n.type === "customer") {
            color = "#06b6d4";
        } else if (n.type === "card") {
            color = n.alert ? "#ef4444" : "#eab308";
        } else if (n.type === "transaction") {
            color = "#ef4444";
        } else if (n.type === "device") {
            color = "#a855f7";
        } else if (n.type === "prior_case") {
            color = "#10b981";
        }

        const isHovered = (hoveredNode === n);
        const isSelected = (selectedNode === n);

        // Ambient Pulse Halo for Flagged / Fraud Nodes
        if (n.alert || n.type === "case" || isSelected) {
            ctx.beginPath();
            const haloRadius = radius + Math.sin(n.pulse) * 4 + 4;
            ctx.arc(n.x, n.y, haloRadius, 0, Math.PI * 2);
            ctx.fillStyle = (color === "#ef4444") ? "rgba(239, 68, 68, 0.18)" : "rgba(249, 115, 22, 0.18)";
            ctx.fill();
        }

        // Node Circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = "#0c111c";
        ctx.fill();

        ctx.strokeStyle = isHovered || isSelected ? "#fff" : color;
        ctx.lineWidth = isHovered || isSelected ? 3 : 2;
        ctx.stroke();

        // Node Inner Core
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius * 0.65, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // Node Label
        ctx.fillStyle = isHovered || isSelected ? "#fff" : "#cbd5e1";
        ctx.font = isHovered ? "bold 11px 'JetBrains Mono', monospace" : "10px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(n.label || "", n.x, n.y + radius + 13);
    });

    ctx.restore();
    animationFrameId = requestAnimationFrame(renderGraphStep);
}
