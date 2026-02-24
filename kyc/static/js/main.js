let stream = null;
let SESSION_ID = null;
let actualFacingMode = null;
let livenessCompleted = false;
let livenessListenerAttached = false;
let waitingForVisibleSelfieStart = false;
let livenessAutoStarted = false;

const params = new URLSearchParams(window.location.search);
const TENANT_SLUG = window.TENANT_SLUG || params.get("tenant") || params.get("tenant_slug");
const CUSTOMER_ID = window.CUSTOMER_ID || params.get("customer_id");
const IS_PHONE = window.matchMedia("(max-width: 640px)").matches;
const IS_NARROW_PHONE = window.matchMedia("(max-width: 430px)").matches;
const DEBUG_MODE = (params.get("debug") || "").toLowerCase();
const DEBUG_AUTOSTART = ["1", "true", "yes"].includes((params.get("autostart") || "").toLowerCase());
const KYC_I18N = window.KYC_I18N || {};
const KYC_LABELS = KYC_I18N.labels || {};
const KYC_STEP_TITLES = KYC_I18N.steps || {};
const KYC_DOCUMENTS = KYC_I18N.documents || {};
const KYC_DOCUMENT_GUIDES = KYC_I18N.documentGuides || {};
const KYC_FIELD_LABELS = KYC_I18N.fieldLabels || {};
const KYC_CAPTURE_TEXT = KYC_I18N.captureText || {};
const KYC_STATUS_TEXT = KYC_I18N.statusText || {};
const KYC_REVIEW_TEXT = KYC_I18N.reviewText || {};
const KYC_COMPLETION_TEXT = KYC_I18N.completionText || {};
const KYC_CAMERA_TEXT = KYC_I18N.cameraText || {};
const KYC_MISC_TEXT = KYC_I18N.miscText || {};
const KYC_INPUT_TEXT = KYC_I18N.inputText || {};
const KYC_LANG_RESUME_KEY = "kyc_lang_resume_v1";

function tKyc(dict, key, fallback) {
    return (dict && dict[key]) || fallback;
}

function normalizeDateTextValue(v) {
    const raw = String(v || "").trim().replace(/\//g, "-").replace(/\./g, "-");
    const m = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) return raw;
    const yyyy = m[1];
    const mm = m[2].padStart(2, "0");
    const dd = m[3].padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function applySmallScreenDateInputFallback(root = document) {
    if (!IS_NARROW_PHONE || !root || !root.querySelectorAll) return;

    root.querySelectorAll('input[type="date"]').forEach((input) => {
        if (input.dataset.dateFallbackApplied === "1") return;
        input.dataset.dateFallbackApplied = "1";
        input.classList.add("date-fallback-text");
        // Keep native date picker on iPhone-sized screens; only improve focus/scroll behavior.
        input.addEventListener("focus", () => {
            setTimeout(() => {
                input.scrollIntoView({ behavior: "smooth", block: "center" });
            }, 50);
        });
    });
}

function snapshotFormValues() {
    const values = {};
    document.querySelectorAll("input[id], select[id], textarea[id]").forEach((el) => {
        if (!el.id) return;
        if (el.type === "checkbox" || el.type === "radio") {
            values[el.id] = !!el.checked;
            return;
        }
        values[el.id] = el.value;
    });
    return values;
}

function restoreFormValues(values) {
    if (!values || typeof values !== "object") return;
    Object.entries(values).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.type === "checkbox" || el.type === "radio") {
            el.checked = !!value;
            return;
        }
        el.value = value == null ? "" : value;
    });
}

function captureGuideFromDocumentType() {
    const sel = documentOptions.find(o => o.id === flowData.document_type);
    const gt = document.getElementById("guideTitle");
    const gb = document.getElementById("guideBody");
    if (sel && gt) gt.textContent = sel.label;
    if (sel && gb) gb.textContent = sel.guide;
}

window.saveKycFlowForLanguageSwitch = function saveKycFlowForLanguageSwitch() {
    try {
        const activeScreen = document.querySelector("[data-screen].active");
        const payload = {
            pathname: window.location.pathname,
            search: window.location.search,
            savedAt: Date.now(),
            currentStepIndex,
            activeScreenId: activeScreen ? activeScreen.id : null,
            SESSION_ID,
            livenessCompleted,
            captureStep,
            flowData,
            capturedPaths,
            capturedTiltPaths,
            tiltCaptureIndex,
            formValues: snapshotFormValues(),
        };
        sessionStorage.setItem(KYC_LANG_RESUME_KEY, JSON.stringify(payload));
    } catch (e) {
        console.warn("Failed to save flow state for language switch:", e);
    }
};

function restoreKycFlowAfterLanguageSwitch() {
    try {
        const raw = sessionStorage.getItem(KYC_LANG_RESUME_KEY);
        if (!raw) return false;
        sessionStorage.removeItem(KYC_LANG_RESUME_KEY);
        const data = JSON.parse(raw);
        if (!data || data.pathname !== window.location.pathname || data.search !== window.location.search) return false;
        if (Date.now() - Number(data.savedAt || 0) > 15 * 60 * 1000) return false;

        if (typeof data.currentStepIndex === "number") currentStepIndex = data.currentStepIndex;
        if (typeof data.SESSION_ID === "string" || data.SESSION_ID === null) SESSION_ID = data.SESSION_ID;
        livenessCompleted = !!data.livenessCompleted;
        if (typeof data.captureStep === "string") captureStep = data.captureStep;
        if (data.flowData && typeof data.flowData === "object") {
            flowData.citizenship_type = data.flowData.citizenship_type ?? flowData.citizenship_type;
            flowData.document_type = data.flowData.document_type ?? flowData.document_type;
            flowData.document_needs_back = !!data.flowData.document_needs_back;
            flowData.customer = data.flowData.customer || {};
            flowData.document = data.flowData.document || { document_type: null, document_data: {} };
        }
        if (data.capturedPaths && typeof data.capturedPaths === "object") capturedPaths = data.capturedPaths;
        if (Array.isArray(data.capturedTiltPaths)) capturedTiltPaths = data.capturedTiltPaths;
        if (typeof data.tiltCaptureIndex === "number") tiltCaptureIndex = data.tiltCaptureIndex;

        if (flowData.citizenship_type) {
            const kanaField = document.getElementById("kanaField");
            if (kanaField) kanaField.classList.toggle("hidden", flowData.citizenship_type !== "japanese");
            renderDocumentOptions();
        }
        if (flowData.document_type) {
            renderDocumentFields(flowData.document_type);
            captureGuideFromDocumentType();
        }

        setStep(
            Math.max(0, Math.min(Number(data.currentStepIndex || 0), flowSteps.length - 1)),
            typeof data.activeScreenId === "string" ? data.activeScreenId : undefined
        );
        restoreFormValues(data.formValues);
        return true;
    } catch (e) {
        console.warn("Failed to restore flow state after language switch:", e);
        return false;
    }
}

const flowSteps = [
    { id: "welcome",    title: tKyc(KYC_STEP_TITLES, "welcome", "Welcome") },
    { id: "citizenship",title: tKyc(KYC_STEP_TITLES, "citizenship", "Residency") },
    { id: "document",   title: tKyc(KYC_STEP_TITLES, "document", "Document Selection") },
    { id: "guide",      title: tKyc(KYC_STEP_TITLES, "guide", "Document Guide") },
    { id: "personal",   title: tKyc(KYC_STEP_TITLES, "personal", "Personal Info") },
    { id: "address",    title: tKyc(KYC_STEP_TITLES, "address", "Address") },
    { id: "contact",    title: tKyc(KYC_STEP_TITLES, "contact", "Contact") },
    { id: "capture",    title: tKyc(KYC_STEP_TITLES, "capture", "Document Capture") },
    { id: "tilt",       title: tKyc(KYC_STEP_TITLES, "tilt", "Card Thickness Check") },
    { id: "liveness",   title: tKyc(KYC_STEP_TITLES, "liveness", "Selfie and Liveness") },
    { id: "review",     title: tKyc(KYC_STEP_TITLES, "review", "Review") },
    { id: "submit",     title: tKyc(KYC_STEP_TITLES, "submit", "Submit") },
    { id: "processing", title: tKyc(KYC_STEP_TITLES, "processing", "Processing") },
    { id: "complete",   title: tKyc(KYC_STEP_TITLES, "complete", "Complete") },
];

const stepScreens = {
    welcome:    "welcomeScreen",
    citizenship:"citizenshipScreen",
    document:   "documentScreen",
    guide:      "guideScreen",
    personal:   "personalScreen",
    address:    "addressScreen",
    contact:    "contactScreen",
    capture:    "captureScreen",
    tilt:       "tiltScreen",
    liveness:   "livenessScreen",
    review:     "reviewScreen",
    submit:     "submitScreen",
    processing: "processingScreen",
    complete:   "completionScreen",
};

const documentOptions = [
    { id:"driver_license", label:tKyc(KYC_DOCUMENTS, "driver_license", "Driver License"),   citizenship:["japanese"],         needsBack:true,  guide:tKyc(KYC_DOCUMENT_GUIDES, "driver_license", "Please prepare your driver license (front and back).") },
    { id:"my_number",      label:tKyc(KYC_DOCUMENTS, "my_number", "My Number Card"),         citizenship:["japanese"],         needsBack:true,  guide:tKyc(KYC_DOCUMENT_GUIDES, "my_number", "Please prepare your My Number card (front and back).") },
    { id:"passport",       label:tKyc(KYC_DOCUMENTS, "passport", "Passport"),                 citizenship:["japanese","foreign"],needsBack:false, guide:tKyc(KYC_DOCUMENT_GUIDES, "passport", "Please prepare your passport photo page.") },
    { id:"residence_card", label:tKyc(KYC_DOCUMENTS, "residence_card", "Residence Card"),     citizenship:["foreign"],          needsBack:true,  guide:tKyc(KYC_DOCUMENT_GUIDES, "residence_card", "Please prepare your residence card (front and back).") },
];

const documentFields = {
    driver_license:  [ { id:"license_number", label:tKyc(KYC_FIELD_LABELS, "license_number", "License number"), type:"text" }, { id:"issue_date",  label:tKyc(KYC_FIELD_LABELS, "issue_date", "Issue date"),  type:"date" }, { id:"expiry_date", label:tKyc(KYC_FIELD_LABELS, "expiry_date", "Expiry date"), type:"date" } ],
    my_number:       [ { id:"my_number",      label:tKyc(KYC_FIELD_LABELS, "my_number", "My Number"),      type:"text" } ],
    passport:        [ { id:"passport_number",label:tKyc(KYC_FIELD_LABELS, "passport_number", "Passport number"),type:"text" }, { id:"passport_expiry",label:tKyc(KYC_FIELD_LABELS, "passport_expiry", "Passport expiry"),type:"date" } ],
    residence_card:  [ { id:"residence_status",label:tKyc(KYC_FIELD_LABELS, "residence_status", "Residence status"),type:"text" }, { id:"residence_card_number",label:tKyc(KYC_FIELD_LABELS, "residence_card_number", "Residence card number"),type:"text" }, { id:"residence_card_expiry",label:tKyc(KYC_FIELD_LABELS, "residence_card_expiry", "Residence card expiry"),type:"date" } ],
};

const flowData = {
    citizenship_type: null,
    document_type: null,
    document_needs_back: false,
    customer: {},
    document: { document_type: null, document_data: {} },
};

let currentStepIndex = 0;
let captureStep = "front";
let capturedImages = { front:null, back:null, selfie:null };
let capturedPaths  = { front:null, back:null, selfie:null };
let capturedTiltPaths = [];
let tiltCaptureIndex = 0;
let cardDetected = false;
let detectionInterval = null;
let lastCaptureAt = 0;
let confirmUnlockAt = 0;

const TILT_DIRECTIONS = [
    {
        id: "tilt_top",
        label: tKyc(KYC_CAPTURE_TEXT, "tiltStepTitle", "Thickness check: Top edge visible"),
        instruction: tKyc(KYC_CAPTURE_TEXT, "tiltInstructionTop", "Tilt card backward — show TOP edge"),
        hint: tKyc(KYC_CAPTURE_TEXT, "tiltHintTop", "Hold the card and tilt the top edge away from you so the thickness is visible."),
        check: ({ beta }) => beta >= -45 && beta <= -15,
    },
];
const TILT_FRAME_TARGET = TILT_DIRECTIONS.length;
let orientationHandler = null;

function currentTiltDirection() {
    return TILT_DIRECTIONS[Math.min(tiltCaptureIndex, TILT_FRAME_TARGET - 1)];
}

function setTiltInstruction(text, goodAngle) {
    const el = document.getElementById("instructions");
    if (!el) return;
    el.textContent = text;
    el.classList.remove("success", "warning");
    if (!IS_PHONE && goodAngle) el.classList.add("success");
}

function showScreen(screenId) {
    document.querySelectorAll("[data-screen]").forEach(s => {
        s.classList.toggle("active", s.id === screenId);
        s.classList.toggle("hidden", s.id !== screenId);
    });
}

function updateProgress() {
    const total   = flowSteps.length;
    const percent = Math.round(((currentStepIndex + 1) / total) * 100);
    const prog    = document.getElementById("stepProgress");
    const label   = document.getElementById("stepLabel");
    const title   = document.getElementById("stepTitle");
    if (prog)  prog.style.width  = `${percent}%`;
    if (label) label.textContent = `${tKyc(KYC_LABELS, "step", "Step")} ${currentStepIndex + 1} ${tKyc(KYC_LABELS, "of", "of")} ${total}`;
    if (title) title.textContent = flowSteps[currentStepIndex].title;
}

function setStep(index, screenOverride) {
    currentStepIndex = Math.max(0, Math.min(index, flowSteps.length - 1));
    updateProgress();
    const stepId   = flowSteps[currentStepIndex].id;
    const screenId = screenOverride || stepScreens[stepId];
    showScreen(screenId);
}

async function startFlow() {
    const ok = await startSession();
    if (ok) setStep(1);
}

async function startSession() {
    try {
        const res  = await fetch("/session/start", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ tenant_slug:TENANT_SLUG, customer_id:CUSTOMER_ID }) });
        const data = await res.json();
        if (!data.success) { showStatus("error",tKyc(KYC_STATUS_TEXT, "failedStartSession", "Failed to start session.")); return false; }
        SESSION_ID = data.session_id;
        return true;
    } catch (err) {
        showStatus("error", `${tKyc(KYC_STATUS_TEXT, "sessionStartFailedPrefix", "Session start failed:")} ${err.message}`);
        return false;
    }
}

function selectCitizenship(type) {
    flowData.citizenship_type = type;
    document.getElementById("kanaField").classList.toggle("hidden", type !== "japanese");
    renderDocumentOptions();
    setStep(2);
}

function renderDocumentOptions() {
    const c = document.getElementById("documentOptions");
    if (!c) return;
    const opts = documentOptions.filter(o => o.citizenship.includes(flowData.citizenship_type));
    c.innerHTML = opts.map(o => `<button class="rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50" onclick="selectDocument('${o.id}')">${o.label}</button>`).join("");
}

function selectDocument(docId) {
    const sel = documentOptions.find(o => o.id === docId);
    if (!sel) return;
    flowData.document_type     = docId;
    flowData.document_needs_back = sel.needsBack;
    flowData.document.document_type = docId;
    flowData.document.document_data = {};
    const gt = document.getElementById("guideTitle");
    const gb = document.getElementById("guideBody");
    if (gt) gt.textContent = sel.label;
    if (gb) gb.textContent = sel.guide;
    renderDocumentFields(docId);
    setStep(3);
}

function goToPersonalInfo() { setStep(4); }

function renderDocumentFields(docId) {
    const c = document.getElementById("documentSpecificFields");
    if (!c) return;
    const fields = documentFields[docId] || [];
    c.innerHTML = fields.map(f => `<div><label class="text-xs font-semibold text-slate-600">${f.label}</label><input id="doc_${f.id}" type="${f.type}" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm"></div>`).join("");
    applySmallScreenDateInputFallback(c);
}

function savePersonalInfo() {
    const fullName = document.getElementById("fullName").value.trim();
    if (!fullName) { showStatus("error",tKyc(KYC_STATUS_TEXT, "fullNameRequired", "Full name is required.")); return; }
    flowData.customer.full_name       = fullName;
    flowData.customer.full_name_kana  = document.getElementById("fullNameKana").value.trim();
    flowData.customer.date_of_birth   = document.getElementById("dateOfBirth").value;
    flowData.customer.gender          = document.getElementById("gender").value;
    flowData.customer.nationality     = document.getElementById("nationality").value.trim();
    flowData.customer.citizenship_type= flowData.citizenship_type;
    (documentFields[flowData.document_type] || []).forEach(f => {
        const el = document.getElementById(`doc_${f.id}`);
        if (!el) return;
        const v = el.value.trim();
        if (!v) return;
        flowData.document.document_data[f.id] = v;
        if (f.id === "residence_status")       flowData.document.residence_status = v;
        if (f.id === "residence_card_number")   flowData.document.residence_card_number = v;
        if (f.id === "residence_card_expiry")   flowData.document.residence_card_expiry = v;
    });
    setStep(5);
}

function saveAddressInfo() {
    flowData.customer.postal_code    = document.getElementById("postalCode").value.trim();
    flowData.customer.prefecture     = document.getElementById("prefecture").value.trim();
    flowData.customer.city           = document.getElementById("city").value.trim();
    flowData.customer.street_address = document.getElementById("streetAddress").value.trim();
    setStep(6);
}

function saveContactInfo() {
    flowData.customer.email        = document.getElementById("email").value.trim();
    flowData.customer.phone        = document.getElementById("phone").value.trim();
    flowData.customer.external_ref = document.getElementById("externalRef").value.trim();
    setStep(7);
    startDocumentCapture();
}

function startDocumentCapture() {
    stopOrientationGuidance();
    captureStep = "front";
    livenessAutoStarted = false;
    capturedTiltPaths = [];
    tiltCaptureIndex  = 0;
    showCaptureScreen();
}

function showCaptureScreen() {
    setStep(7, "captureScreen");
    document.getElementById("previewContainer").classList.remove("active");
    updateCaptureUI();
    startCamera();
}

/* ─────────────────────────────────────────────────────────────────────────────
 * injectTiltFrameSVG — draws a trapezoid border inside .illustrated-card
 *
 * Shape (bird's-eye / looking down at tilted card):
 *
 *      ←── narrow ──→        ← top (far away from camera)
 *     /              \
 *    /                \
 *   ←──── wide ────────→     ← bottom (close to camera)
 *
 * Top edge: amber (shows thickness)
 * Sides + bottom: white
 * ───────────────────────────────────────────────────────────────────────────── */
function injectTiltFrameSVG(container) {
    const existing = container.querySelector("svg.tilt-frame");
    if (existing) existing.remove();

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("tilt-frame");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("preserveAspectRatio", "none");

    const roundedPath = (points, radius = 2.4) => {
        const len = points.length;
        const norm = (v) => {
            const l = Math.hypot(v.x, v.y) || 1;
            return { x: v.x / l, y: v.y / l };
        };
        const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
        const corners = points.map((curr, i) => {
            const prev = points[(i - 1 + len) % len];
            const next = points[(i + 1) % len];
            const toPrev = norm({ x: prev.x - curr.x, y: prev.y - curr.y });
            const toNext = norm({ x: next.x - curr.x, y: next.y - curr.y });
            const localR = Math.min(radius, dist(curr, prev) * 0.22, dist(curr, next) * 0.22);
            return {
                curr,
                pin: { x: curr.x + toPrev.x * localR, y: curr.y + toPrev.y * localR },
                pout: { x: curr.x + toNext.x * localR, y: curr.y + toNext.y * localR },
            };
        });

        let d = `M ${corners[0].pout.x} ${corners[0].pout.y}`;
        for (let i = 1; i < len; i += 1) {
            d += ` L ${corners[i].pin.x} ${corners[i].pin.y}`;
            d += ` Q ${corners[i].curr.x} ${corners[i].curr.y} ${corners[i].pout.x} ${corners[i].pout.y}`;
        }
        d += ` L ${corners[0].pin.x} ${corners[0].pin.y}`;
        d += ` Q ${corners[0].curr.x} ${corners[0].curr.y} ${corners[0].pout.x} ${corners[0].pout.y} Z`;
        return d;
    };

    // Front card (main frame)
    const tl = { x: 12, y: 26 };
    const tr = { x: 88, y: 26 };
    const br = { x: 80, y: 78 };
    const bl = { x: 20, y: 78 };

    // Depth only for sides/bottom so top edge stays "flat 2D"
    const depth = { x: 2.2, y: -4.2 };
    const btl = { x: tl.x + depth.x, y: tl.y + depth.y };
    const btr = { x: tr.x - depth.x, y: tr.y + depth.y };
    const bbr = { x: br.x - depth.x, y: br.y + depth.y };
    const bbl = { x: bl.x + depth.x, y: bl.y + depth.y };

    const shadow = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    shadow.setAttribute("points", `${bl.x + 1},${bl.y + 1.4} ${br.x + 1},${br.y + 1.4} ${br.x - 3},${br.y + 5.4} ${bl.x + 4},${bl.y + 5.4}`);
    shadow.setAttribute("fill", "rgba(2,6,23,0.15)");

    const sideDepthLeft = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    sideDepthLeft.setAttribute("points", `${btl.x},${btl.y} ${tl.x},${tl.y} ${bl.x},${bl.y} ${bbl.x},${bbl.y}`);
    sideDepthLeft.setAttribute("fill", "rgba(255,255,255,0.06)");

    const sideDepthRight = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    sideDepthRight.setAttribute("points", `${btr.x},${btr.y} ${tr.x},${tr.y} ${br.x},${br.y} ${bbr.x},${bbr.y}`);
    sideDepthRight.setAttribute("fill", "rgba(255,255,255,0.06)");

    const bottomDepth = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    bottomDepth.setAttribute("points", `${bl.x},${bl.y} ${br.x},${br.y} ${bbr.x},${bbr.y} ${bbl.x},${bbl.y}`);
    bottomDepth.setAttribute("fill", "rgba(255,255,255,0.06)");

    const frontFace = document.createElementNS("http://www.w3.org/2000/svg", "path");
    frontFace.setAttribute("d", roundedPath([tl, tr, br, bl], 3.0));
    frontFace.setAttribute("fill", "rgba(255,255,255,0.06)");
    frontFace.setAttribute("stroke", "none");

    // Rounded perimeter for realistic card corners.
    const borderPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    borderPath.setAttribute("d", roundedPath([tl, tr, br, bl], 3.2));
    borderPath.setAttribute("fill", "none");
    borderPath.setAttribute("stroke", "rgba(255,255,255,0.98)");
    borderPath.setAttribute("stroke-width", "2.55");
    borderPath.setAttribute("stroke-linejoin", "round");
    borderPath.setAttribute("stroke-linecap", "round");

    // 3D top thickness face (yellow) so the upper edge reads as real depth.
    const topThicknessFace = document.createElementNS("http://www.w3.org/2000/svg", "path");
    topThicknessFace.setAttribute("d", roundedPath([btl, btr, tr, tl], 1.8));
    topThicknessFace.setAttribute("fill", "rgba(251,191,36,0.50)");
    topThicknessFace.setAttribute("stroke", "rgba(251,191,36,0.98)");
    topThicknessFace.setAttribute("stroke-width", "1.15");
    topThicknessFace.setAttribute("stroke-linejoin", "round");

    const topRearLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    topRearLine.setAttribute("x1", btl.x);
    topRearLine.setAttribute("y1", btl.y);
    topRearLine.setAttribute("x2", btr.x);
    topRearLine.setAttribute("y2", btr.y);
    topRearLine.setAttribute("stroke", "rgba(255,255,255,0.88)");
    topRearLine.setAttribute("stroke-width", "1.25");
    topRearLine.setAttribute("stroke-linecap", "round");

    // Front top edge should remain white; yellow is only the thickness band.
    const topHighlight = document.createElementNS("http://www.w3.org/2000/svg", "line");
    topHighlight.setAttribute("x1", tl.x + 1.2);
    topHighlight.setAttribute("y1", tl.y);
    topHighlight.setAttribute("x2", tr.x - 1.2);
    topHighlight.setAttribute("y2", tr.y);
    topHighlight.setAttribute("stroke", "rgba(255,255,255,0.97)");
    topHighlight.setAttribute("stroke-width", "2.55");
    topHighlight.setAttribute("stroke-linecap", "round");

    const gloss = document.createElementNS("http://www.w3.org/2000/svg", "path");
    gloss.setAttribute("d", `M ${tl.x + 7} ${tl.y + 10.5} L ${tr.x - 10} ${tr.y + 10.5}`);
    gloss.setAttribute("fill", "none");
    gloss.setAttribute("stroke", "rgba(255,255,255,0.38)");
    gloss.setAttribute("stroke-width", "1.2");
    gloss.setAttribute("stroke-linecap", "round");

    // More realistic card information layout.
    const infoGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const makeInfoLine = (x1, y1, x2, y2, alpha = 0.46, w = 1.15) => {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", x1);
        line.setAttribute("y1", y1);
        line.setAttribute("x2", x2);
        line.setAttribute("y2", y2);
        line.setAttribute("stroke", `rgba(255,255,255,${alpha})`);
        line.setAttribute("stroke-width", String(w));
        line.setAttribute("stroke-linecap", "round");
        return line;
    };
    [
        makeInfoLine(24, 36.5, 58, 36.5, 0.52, 1.2),
        makeInfoLine(24, 42.5, 56, 42.5, 0.48, 1.15),
        makeInfoLine(24, 48.5, 54, 48.5, 0.44, 1.1),
        makeInfoLine(24, 54.5, 50, 54.5, 0.40, 1.05),
        makeInfoLine(24, 62.5, 74, 62.5, 0.36, 1.0),
    ].forEach((line) => infoGroup.appendChild(line));

    const accentDots = document.createElementNS("http://www.w3.org/2000/svg", "g");
    [28, 31.5, 35].forEach((x) => {
        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("cx", String(x));
        dot.setAttribute("cy", "30.8");
        dot.setAttribute("r", "0.85");
        dot.setAttribute("fill", "rgba(255,255,255,0.55)");
        accentDots.appendChild(dot);
    });

    const ptl = { x: 60, y: 39 };
    const ptr = { x: 73.5, y: 39 };
    const pbr = { x: 70, y: 61.5 };
    const pbl = { x: 56.5, y: 61.5 };
    const photoFrame = document.createElementNS("http://www.w3.org/2000/svg", "path");
    photoFrame.setAttribute("d", roundedPath([ptl, ptr, pbr, pbl], 1.4));
    photoFrame.setAttribute("fill", "rgba(251,191,36,0.72)");
    photoFrame.setAttribute("stroke", "rgba(251,191,36,0.98)");
    photoFrame.setAttribute("stroke-width", "1.15");
    photoFrame.setAttribute("stroke-linejoin", "round");

    // Simple custom user icon: small head circle + larger lower semicircle.
    const userIcon = document.createElementNS("http://www.w3.org/2000/svg", "g");
    userIcon.setAttribute("fill", "rgba(15,23,42,0.64)");

    const userHead = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    userHead.setAttribute("cx", "64.9");
    userHead.setAttribute("cy", "47.2");
    userHead.setAttribute("r", "2.15");

    const userBody = document.createElementNS("http://www.w3.org/2000/svg", "path");
    userBody.setAttribute("d", "M60.6 54.7a4.3 4.3 0 0 1 8.6 0v1.55h-8.6z");

    userIcon.appendChild(userHead);
    userIcon.appendChild(userBody);

    svg.appendChild(shadow);
    svg.appendChild(sideDepthLeft);
    svg.appendChild(sideDepthRight);
    svg.appendChild(bottomDepth);
    svg.appendChild(topThicknessFace);
    svg.appendChild(topRearLine);
    svg.appendChild(frontFace);
    svg.appendChild(borderPath);
    svg.appendChild(topHighlight);
    svg.appendChild(infoGroup);
    svg.appendChild(accentDots);
    svg.appendChild(photoFrame);
    svg.appendChild(userIcon);
    svg.appendChild(gloss);
    container.appendChild(svg);
}

/* ─────────────────────────────────────────────────────────────────────────────
 * updateCaptureUI — sets all overlay text/graphics for the current captureStep
 *
 * GUIDE ILLUSTRATION LOGIC:
 *   - tilt  → always show (both mobile and desktop)
 *   - selfie → always hide (use oval guide-box on desktop; no illustration)
 *   - front/back → show on mobile (CSS already shows it); hide on desktop
 * ───────────────────────────────────────────────────────────────────────────── */
function updateCaptureUI() {
    const get = id => document.getElementById(id);
    const cameraContainer = get("cameraContainer");
    const title         = get("captureTitle");
    const subtitle      = get("captureSubtitle");
    const instructions  = get("instructions");
    const guideBox      = get("guideBox");
    const modeLabel     = get("cameraModeLabel");
    const liveTitle     = get("cameraLiveTitle");
    const liveSub       = get("cameraLiveSubtitle");
    const warnText      = get("cameraWarningText");
    const card          = get("illustratedCard");
    const arrow         = get("directionArrow");
    const facePlaceholder = get("cardPhotoPlaceholder");
    const illustration  = get("guideIllustration");

    if (cameraContainer) {
        cameraContainer.classList.remove("document-mode", "tilt-mode", "selfie-mode");
    }

    /* ── reset card classes ── */
    if (card) {
        card.classList.remove("mode-tilt","mode-selfie","tilt-left","tilt-right","tilt-top");
        // Remove any injected tilt SVG when leaving tilt mode
        const oldSvg = card.querySelector("svg.tilt-frame");
        if (oldSvg) oldSvg.remove();
    }

    /* ── reset arrow ── */
    if (arrow) { arrow.classList.remove("left","right","top"); arrow.textContent=""; arrow.style.opacity="0"; }

    /* ── hide face placeholder by default, tilt hides it too ── */
    if (facePlaceholder) facePlaceholder.style.display = "none";

    /* ── reset illustration classes (don't touch display yet) ── */
    if (illustration) illustration.classList.remove("tilt-mode");

    /* ══════════════════════ TILT ══════════════════════ */
    if (captureStep === "tilt") {
        if (cameraContainer) cameraContainer.classList.add("tilt-mode");
        const tilt = currentTiltDirection();

        if (title) {
            const dots = Array.from({length:TILT_FRAME_TARGET}).map((_,i)=>i<tiltCaptureIndex?"●":"○").join(" ");
            title.textContent = `${tilt.label}  ${dots}`;
        }
        if (subtitle)      subtitle.textContent   = tilt.hint;
        if (modeLabel)     modeLabel.textContent  = tKyc(KYC_CAPTURE_TEXT, "cameraMode", "Camera Mode1");
        if (liveTitle)     liveTitle.textContent  = tKyc(KYC_CAPTURE_TEXT, "tiltLiveTitle", "Tilt");
        if (liveSub)       liveSub.textContent    = tKyc(KYC_CAPTURE_TEXT, "tiltLiveSubtitle", "Thickness at the top of the card.");
        if (warnText)      warnText.textContent   = tKyc(KYC_CAPTURE_TEXT, "tiltWarn", "Align your card with the guide and show top edge.");
        if (instructions)  { instructions.textContent = tKyc(KYC_CAPTURE_TEXT, "tiltInstructionTopLower", "Tilt backward — show top edge."); instructions.classList.remove("success","warning"); }

        if (card) {
            card.classList.add("mode-tilt");
            // Inject SVG trapezoid: wide bottom (near camera), narrow top (far away)
            // This matches the perspective of looking down at a tilted card
            injectTiltFrameSVG(card);
        }

        if (illustration) {
            illustration.classList.add("tilt-mode");
            /* Force visible on ALL screen sizes for tilt — overrides everything */
            illustration.style.display = "block";
        }

        if (guideBox) {
            // Hide the outer frame in tilt mode; keep only the inner card overlay.
            guideBox.style.display = "none";
        }
        return;
    }

    /* ══════════════════════ SELFIE ══════════════════════ */
    if (captureStep === "selfie") {
        if (cameraContainer) cameraContainer.classList.add("selfie-mode");
        if (title)        title.textContent      = tKyc(KYC_CAPTURE_TEXT, "selfieTitle", "Capture your selfie");
        if (subtitle)     subtitle.textContent   = tKyc(KYC_CAPTURE_TEXT, "selfieSubtitle", "Make sure your face is centered and clear.");
        if (instructions) instructions.textContent = tKyc(KYC_CAPTURE_TEXT, "selfieInstruction", "Position your face within the frame");
        if (modeLabel)    modeLabel.textContent  = tKyc(KYC_CAPTURE_TEXT, "selfieModeLabel", "Selfie mode");
        if (liveTitle)    liveTitle.textContent  = tKyc(KYC_CAPTURE_TEXT, "selfieLiveTitle", "Capture selfie");
        if (liveSub)      liveSub.textContent    = tKyc(KYC_CAPTURE_TEXT, "selfieLiveSubtitle", "Center your face and hold still.");
        if (warnText)     warnText.textContent   = tKyc(KYC_CAPTURE_TEXT, "selfieWarn", "Use good lighting and avoid blur.");
        if (card)         card.classList.add("mode-selfie");
        if (guideBox)     {
            guideBox.style.display = "";
            guideBox.classList.remove("tilt");
            guideBox.classList.add("selfie");
        }
        if (instructions) instructions.classList.remove("success","warning");

        /* Selfie: HIDE illustration, guide-box oval used instead */
        if (illustration) illustration.style.display = "none";
        return;
    }

    /* ══════════════════════ FRONT / BACK ══════════════════════ */
    const isBack = captureStep === "back";
    if (cameraContainer) cameraContainer.classList.add("document-mode");
    if (title)        title.textContent      = isBack ? tKyc(KYC_CAPTURE_TEXT, "docBackTitle", "Capture the back of your document") : tKyc(KYC_CAPTURE_TEXT, "docFrontTitle", "Capture the front of your document");
    if (subtitle)     subtitle.textContent   = isBack ? tKyc(KYC_CAPTURE_TEXT, "docBackSubtitle", "Make sure the back side is clear and readable.") : tKyc(KYC_CAPTURE_TEXT, "docFrontSubtitle", "Make sure all details are clear and readable.");
    if (instructions) instructions.textContent = isBack ? tKyc(KYC_CAPTURE_TEXT, "docBackInstruction", "Position the back within the frame") : tKyc(KYC_CAPTURE_TEXT, "docFrontInstruction", "Position the front within the frame");
    if (modeLabel)    modeLabel.textContent  = tKyc(KYC_CAPTURE_TEXT, "documentModeLabel", "Document mode");
    if (liveTitle)    liveTitle.textContent  = isBack ? tKyc(KYC_CAPTURE_TEXT, "docBackLiveTitle", "Capture back side") : tKyc(KYC_CAPTURE_TEXT, "docFrontLiveTitle", "Capture front side");
    if (liveSub)      liveSub.textContent    = isBack ? tKyc(KYC_CAPTURE_TEXT, "docBackLiveSubtitle", "Place the back of your ID clearly.") : tKyc(KYC_CAPTURE_TEXT, "docFrontLiveSubtitle", "Place the front of your ID clearly.");
    if (warnText)     warnText.textContent   = tKyc(KYC_CAPTURE_TEXT, "docWarn", "Avoid glare and keep all corners visible.");
    if (guideBox)     {
        guideBox.style.display = "";
        guideBox.classList.remove("selfie","tilt");
    }
    if (instructions) instructions.classList.remove("success","warning");

    /* Front: show FACE placeholder */
    if (!isBack && facePlaceholder) facePlaceholder.style.display = "flex";

    /*
     * Front/back illustration:
     *   - Mobile: CSS already shows it (display:block in @media). Don't override.
     *   - Desktop: leave it hidden (display:none default). Don't override.
     * So we reset the inline style to "" which lets CSS decide.
     */
    if (illustration) illustration.style.display = "";
}

/* ─────────────────────────────────────────────────────────────────────────────
 * startCamera — ALWAYS uses rear camera for document/tilt, front for selfie.
 * Retry chain: exact → ideal → any.
 * Mirror: rear camera = NEVER mirrored. Front camera = mirrored.
 * ───────────────────────────────────────────────────────────────────────────── */
async function startCamera() {
    const video     = document.getElementById("video");
    const container = document.getElementById("cameraContainer");

    if (container) container.classList.add("active");
    document.body.classList.add("camera-active");

    /* Stop any existing stream */
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    video.srcObject = null;

    const isSelfie = captureStep === "selfie";

    const attempts = isSelfie
        ? [
            { video:{ facingMode:{ exact:"user" }, width:{ideal:1280}, height:{ideal:720} } },
            { video:{ facingMode:{ ideal:"user" }, width:{ideal:1280}, height:{ideal:720} } },
            { video:{ width:{ideal:1280}, height:{ideal:720} } },
          ]
        : [
            { video:{ facingMode:{exact:"environment"}, width:{ideal:1920}, height:{ideal:1080} } }, // best on phone
            { video:{ facingMode:{ideal:"environment"}, width:{ideal:1280}, height:{ideal:720}  } }, // fallback
            { video:{ width:{ideal:1280}, height:{ideal:720} } },                                     // last resort
          ];

    let lastErr = null;
    for (const c of attempts) {
        try { stream = await navigator.mediaDevices.getUserMedia(c); break; }
        catch (e) {
            lastErr = e; stream = null;
            if (e.name === "NotReadableError" || e.name === "TrackStartError") break;
        }
    }

    if (!stream) {
        const permissionState = await getCameraPermissionState();
        showStatus("error", getCameraErrorMessage(lastErr, permissionState));
        document.body.classList.remove("camera-active");
        if (container) container.classList.remove("active");
        return;
    }

    video.srcObject = stream;

    /* Detect actual facing mode */
    const track    = stream.getVideoTracks()[0];
    const settings = track.getSettings();
    actualFacingMode = settings.facingMode;

    /* Mirror rule: ONLY mirror when using the front/user camera */
    const useFront = isSelfie && actualFacingMode !== "environment";
    if (useFront) {
        video.classList.remove("no-mirror"); /* front cam: mirror (default CSS) */
    } else {
        video.classList.add("no-mirror");    /* rear cam: never mirror */
    }

    try {
        await new Promise((res, rej) => {
            const t = setTimeout(() => rej(new Error("Video load timeout")), 10000);
            video.onloadedmetadata = () => { clearTimeout(t); video.play().then(res).catch(rej); };
        });
    } catch (e) {
        showStatus("error", `${tKyc(KYC_CAMERA_TEXT, "cameraFailedStart", "Camera failed to start:")} ${e.message}`);
        stopCamera();
        return;
    }

    updateCaptureUI();
    setupCaptureButton();
}

async function getCameraPermissionState() {
    try {
        if (!navigator.permissions || !navigator.permissions.query) return null;
        const result = await navigator.permissions.query({ name: "camera" });
        return result.state || null;
    } catch (_) {
        return null;
    }
}

function getCameraErrorMessage(error, permissionState = null) {
    if (!error) return tKyc(KYC_CAMERA_TEXT, "cameraAccessFailed", "Camera access failed.");
    if (!window.isSecureContext) return tKyc(KYC_CAMERA_TEXT, "cameraNeedsHttps", "Camera requires a secure page (HTTPS).");
    if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        if (permissionState === "granted") {
            return tKyc(KYC_CAMERA_TEXT, "cameraBlockedSession", "Camera is blocked by the current tab/session. Close other camera screens and try again.");
        }
        return tKyc(KYC_CAMERA_TEXT, "cameraPermissionDenied", "Camera permission denied. Please allow camera access in your browser settings.");
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") return tKyc(KYC_CAMERA_TEXT, "noCameraFound", "No camera found on your device.");
    if (error.name === "NotReadableError" || error.name === "TrackStartError") return tKyc(KYC_CAMERA_TEXT, "cameraInUse", "Camera is already in use by another application.");
    if (error.name === "OverconstrainedError" || error.name === "ConstraintNotSatisfiedError") return tKyc(KYC_CAMERA_TEXT, "cameraConstraintsUnsupported", "Camera constraints are not supported on this device. Please try again.");
    return `${tKyc(KYC_CAMERA_TEXT, "cameraErrorPrefix", "Camera error:")} ${error.message || tKyc(KYC_CAMERA_TEXT, "unknownError", "Unknown error.")}`;
}

function setupCaptureButton() {
    const btn = document.getElementById("captureBtn");
    if (!btn) return;
    btn.onclick     = e => { e.preventDefault(); capturePhoto(); };
    btn.onpointerup = null;
    btn.ontouchend  = null;
}

function capturePhoto() {
    const video  = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const ctx    = canvas.getContext("2d");

    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;

    /* Mirror the canvas only for selfie with front cam */
    const mirrorCapture = captureStep === "selfie" && actualFacingMode !== "environment";
    if (mirrorCapture) {
        ctx.save();
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.restore();
    } else {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    }

    const imageData   = canvas.toDataURL("image/jpeg", 0.95);
    capturedImages[captureStep] = imageData;
    lastCaptureAt  = Date.now();
    confirmUnlockAt= lastCaptureAt + 1200;

    document.getElementById("cameraContainer").classList.remove("active");
    document.getElementById("previewContainer").classList.add("active");
    document.getElementById("previewImage").src = imageData;
    document.body.classList.add("camera-active");

    const confirmBtn = document.getElementById("confirmBtn");
    const retakeBtn  = document.getElementById("retakeBtn");
    if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.style.opacity = "0.65"; }
    if (retakeBtn)  retakeBtn.disabled = false;

    setTimeout(() => {
        const b = document.getElementById("confirmBtn");
        if (b && document.getElementById("previewContainer").classList.contains("active")) {
            b.disabled = false; b.style.opacity = "";
        }
    }, 1200);
}

function retakePhoto() {
    document.getElementById("previewContainer").classList.remove("active");
    document.getElementById("cameraContainer").classList.add("active");
    document.body.classList.add("camera-active");
}

async function confirmPhoto() {
    if (!document.getElementById("previewContainer").classList.contains("active")) return;
    if (Date.now() - lastCaptureAt < 700) return;
    if (Date.now() < confirmUnlockAt) return;
    if (!SESSION_ID) { showStatus("error",tKyc(KYC_STATUS_TEXT, "missingSessionRestart", "Missing session. Please restart verification.")); return; }

    const imageData  = capturedImages[captureStep];
    const uploadType = captureStep === "tilt" ? currentTiltDirection().id : captureStep;
    showStatus("loading",tKyc(KYC_STATUS_TEXT, "uploadingImage", "Uploading image..."));

    try {
        const res  = await fetch("/capture/", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ session_id:SESSION_ID, tenant_slug:TENANT_SLUG, image:imageData, type:uploadType }) });
        const data = await res.json();
        if (!data.success) { showStatus("error", data.error || tKyc(KYC_STATUS_TEXT, "captureFailed", "Capture failed.")); return; }

        if (captureStep === "tilt") capturedTiltPaths.push(data.filename);
        else capturedPaths[captureStep] = data.filename;

        hideStatus();
        document.getElementById("previewContainer").classList.remove("active");

        if (captureStep === "front" && flowData.document_needs_back) {
            captureStep = "back";
            document.getElementById("cameraContainer").classList.add("active");
            updateCaptureUI();
            startCamera();
            return;
        }

        if (captureStep === "front" || captureStep === "back") {
            stopCamera();
            goToTiltGuide();
            return;
        }

        if (captureStep === "tilt") {
            tiltCaptureIndex++;
            showStatus("success",`${tKyc(KYC_STATUS_TEXT, "tiltCapturedPrefix", "Tilt")} ${tiltCaptureIndex}/${TILT_FRAME_TARGET} ${tKyc(KYC_STATUS_TEXT, "capturedSuffix", "captured.")}`);
            await new Promise(r => setTimeout(r, 700));
            if (tiltCaptureIndex < TILT_FRAME_TARGET) {
                hideStatus();
                document.getElementById("cameraContainer").classList.add("active");
                updateCaptureUI();
                startCamera();
                return;
            }
            hideStatus();
            stopOrientationGuidance();
            stopCamera();
            goToLiveness();
            return;
        }

        if (captureStep === "selfie") { stopCamera(); renderReview(); setStep(10); }

    } catch (e) { showStatus("error",`${tKyc(KYC_STATUS_TEXT, "uploadFailedPrefix", "Upload failed:")} ${e.message}`); }
}

function stopCamera() {
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    stopOrientationGuidance();
    const c = document.getElementById("cameraContainer");
    if (c) c.classList.remove("active");
    document.getElementById("previewContainer").classList.remove("active");
    document.body.classList.remove("camera-active");
}

function goToLiveness() {
    stopOrientationGuidance();
    setStep(9);
    if (!livenessAutoStarted) {
        livenessAutoStarted = true;
        setTimeout(() => {
            startLivenessDetection();
        }, 180);
    }
}

function goToTiltCapture() {
    captureStep      = "tilt";
    tiltCaptureIndex = 0;
    setStep(8, "captureScreen");
    updateCaptureUI();
    document.getElementById("cameraContainer").classList.add("active");
    document.getElementById("previewContainer").classList.remove("active");
    startOrientationGuidance();
    startCamera();
}

function goToTiltGuide()  { stopOrientationGuidance(); hideStatus(); setStep(8, "tiltScreen"); }
function startTiltCapture(){ goToTiltCapture(); }

async function startLivenessDetection() {
    if (capturedTiltPaths.length < TILT_FRAME_TARGET) {
        showStatus("error",`${tKyc(KYC_STATUS_TEXT, "tiltCheckRequiredPrefix", "Tilt check required. Please capture")} ${TILT_FRAME_TARGET} ${tKyc(KYC_STATUS_TEXT, "tiltPhotosFirstSuffix", "tilt photos first.")}`);
        setTimeout(() => goToTiltGuide(), 900);
        return;
    }
    if (!SESSION_ID) { showStatus("error",tKyc(KYC_STATUS_TEXT, "missingSessionRestart", "Missing session. Please restart verification.")); return; }

    const w = window.open(`/liveness?session_id=${encodeURIComponent(SESSION_ID)}`,"livenessWindow","width=520,height=820");
    if (!w) { showStatus("error",tKyc(KYC_STATUS_TEXT, "popupBlocked", "Popup blocked. Allow popups for this site and try again.")); return; }

    showStatus("loading",tKyc(KYC_STATUS_TEXT, "startingLiveness", "Starting liveness detection..."));
    try { await fetch("/start-liveness/", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ session_id:SESSION_ID, tenant_slug:TENANT_SLUG }) }); } catch(e){}

    if (livenessListenerAttached) return;
    livenessListenerAttached = true;

    window.addEventListener("message", async event => {
        try {
            if (!event.data || event.data.type !== "liveness_result") return;
            const result = { ...event.data.data, session_id:SESSION_ID };
            await fetch("/liveness-result", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ ...result, tenant_slug:TENANT_SLUG, customer_id:CUSTOMER_ID }) });
            if (result.verified) {
                livenessCompleted = true;
                showStatus("success",`${tKyc(KYC_STATUS_TEXT, "livenessVerifiedConfidence", "Liveness verified. Confidence:")} ${result.confidence}%`);
                setTimeout(() => proceedAfterLivenessWhenVisible(), 900);
            } else {
                showStatus("error",tKyc(KYC_STATUS_TEXT, "livenessVerificationFailed", "Liveness verification failed. Please try again."));
                setTimeout(() => hideStatus(), 2000);
            }
        } catch(e) { showStatus("error",tKyc(KYC_STATUS_TEXT, "failedSaveLiveness", "Failed to save liveness result.")); }
        finally { livenessListenerAttached = false; }
    }, { once:true });
}

function proceedAfterLivenessWhenVisible() {
    if (document.visibilityState === "visible") {
        proceedAfterLiveness();
        return;
    }
    if (waitingForVisibleSelfieStart) return;
    waitingForVisibleSelfieStart = true;
    showStatus("info",tKyc(KYC_STATUS_TEXT, "returnToVerificationTab", "Return to this verification tab to continue selfie capture."));
    const onVisibility = () => {
        if (document.visibilityState !== "visible") return;
        document.removeEventListener("visibilitychange", onVisibility);
        waitingForVisibleSelfieStart = false;
        proceedAfterLiveness();
    };
    document.addEventListener("visibilitychange", onVisibility);
}

function skipLiveness() {
    if (capturedTiltPaths.length < TILT_FRAME_TARGET) {
        showStatus("error",`${tKyc(KYC_STATUS_TEXT, "tiltCheckRequiredPrefix", "Tilt check required. Please capture")} ${TILT_FRAME_TARGET} ${tKyc(KYC_STATUS_TEXT, "tiltPhotosFirstSuffix", "tilt photos first.")}`);
        setTimeout(() => goToTiltGuide(), 900);
        return;
    }
    if (confirm(tKyc(KYC_MISC_TEXT, "confirmSkipLiveness", "Skipping liveness detection may reduce security. Continue anyway?"))) {
        livenessAutoStarted = true;
        livenessCompleted = false;
        proceedAfterLiveness();
    }
}

function proceedAfterLiveness() {
    waitingForVisibleSelfieStart = false;
    stopOrientationGuidance();
    hideStatus();
    captureStep = "selfie";
    updateCaptureUI();
    setStep(9,"captureScreen");
    document.getElementById("cameraContainer").classList.add("active");
    document.getElementById("previewContainer").classList.remove("active");
    startCamera();
}

async function startOrientationGuidance() {
    stopOrientationGuidance();
    if (!window.DeviceOrientationEvent || captureStep !== "tilt") return;
    cardDetected = false;

    try {
        if (typeof window.DeviceOrientationEvent.requestPermission === "function") {
            const perm = await window.DeviceOrientationEvent.requestPermission();
            if (perm !== "granted") return;
        }
    } catch(e) { return; }

    startCardDetection();

    orientationHandler = event => {
        if (captureStep !== "tilt") return;
        const tilt = currentTiltDirection();
        if (!tilt) return;
        const beta  = Number(event.beta  || 0);
        const gamma = Number(event.gamma || 0);
        const el    = document.getElementById("instructions");

        if (!cardDetected) {
            setTiltInstruction(tKyc(KYC_CAPTURE_TEXT, "holdCardCenterTilt", "Hold card clearly in the center, then tilt as instructed."), false);
            if (el && !IS_PHONE) el.classList.add("warning");
            return;
        }
        const good = tilt.check({ beta, gamma });
        if (good) { setTiltInstruction(IS_PHONE ? tKyc(KYC_CAPTURE_TEXT, "angleLooksGoodTapSnap", "Angle looks good. Tap Snap.") : tKyc(KYC_CAPTURE_TEXT, "goodAngleDetectedTapSnap", "Good angle detected. Tap Snap now."), true); return; }
        setTiltInstruction(tilt.instruction, false);
        if (el && !IS_PHONE) el.classList.add("warning");
    };

    window.addEventListener("deviceorientation", orientationHandler, true);
}

function stopOrientationGuidance() {
    if (orientationHandler) { window.removeEventListener("deviceorientation", orientationHandler, true); orientationHandler = null; }
    if (detectionInterval)  { clearInterval(detectionInterval); detectionInterval = null; }
    cardDetected = false;
}

function startCardDetection() {
    if (detectionInterval) { clearInterval(detectionInterval); detectionInterval = null; }
    const video = document.getElementById("video");
    if (!video) return;
    const canvas = document.createElement("canvas");
    const ctx    = canvas.getContext("2d");
    if (!ctx) return;

    detectionInterval = setInterval(() => {
        if (captureStep !== "tilt" || !video.videoWidth || !video.videoHeight) { cardDetected = false; return; }
        canvas.width = 320; canvas.height = 240;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const img  = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        let score  = 0;
        for (let y = 40; y < 200; y += 4) {
            for (let x = 40; x < 280; x += 4) {
                const i  = (y * canvas.width + x) * 4;
                const ir = i + 4;
                const id = ((y+1) * canvas.width + x) * 4;
                const p  = img[i]+img[i+1]+img[i+2];
                score += Math.abs(p - (img[ir]+img[ir+1]+img[ir+2])) + Math.abs(p - (img[id]+img[id+1]+img[id+2]));
            }
        }
        cardDetected = score > 70000;
    }, 500);
}

function renderReview() {
    const el = document.getElementById("reviewSummary");
    if (!el) return;
    const doc = documentOptions.find(o => o.id === flowData.document_type);
    el.innerHTML = `<div class="space-y-3">
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "citizenship", "Citizenship")}:</strong> ${flowData.citizenship_type === "japanese" ? tKyc(KYC_REVIEW_TEXT, "citizenshipJapanese", "Japanese") : flowData.citizenship_type === "foreign" ? tKyc(KYC_REVIEW_TEXT, "citizenshipForeign", "Foreign") : (flowData.citizenship_type||"")}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "document", "Document")}:</strong> ${doc?.label||flowData.document_type||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "fullName", "Full name")}:</strong> ${flowData.customer.full_name||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "dateOfBirth", "Date of birth")}:</strong> ${flowData.customer.date_of_birth||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "nationality", "Nationality")}:</strong> ${flowData.customer.nationality||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "address", "Address")}:</strong> ${flowData.customer.prefecture||""} ${flowData.customer.city||""} ${flowData.customer.street_address||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "contact", "Contact")}:</strong> ${flowData.customer.email||""} ${flowData.customer.phone||""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "documentImages", "Document images")}:</strong> ${capturedPaths.front ? tKyc(KYC_REVIEW_TEXT, "front", "Front") : ""} ${capturedPaths.back ? tKyc(KYC_REVIEW_TEXT, "back", "Back") : ""}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "tiltFrames", "Tilt frames")}:</strong> ${capturedTiltPaths.length}/${TILT_FRAME_TARGET}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "selfie", "Selfie")}:</strong> ${capturedPaths.selfie ? tKyc(KYC_REVIEW_TEXT, "captured", "Captured") : tKyc(KYC_REVIEW_TEXT, "pending", "Pending")}</div>
        <div><strong>${tKyc(KYC_REVIEW_TEXT, "liveness", "Liveness")}:</strong> ${livenessCompleted ? tKyc(KYC_REVIEW_TEXT, "completed", "Completed") : tKyc(KYC_REVIEW_TEXT, "skipped", "Skipped")}</div>
    </div>`;
}

async function submitFlow() {
    setStep(11);
    try {
        const r    = await fetch("/session/submit", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ session_id:SESSION_ID, tenant_slug:TENANT_SLUG, customer:flowData.customer, document:flowData.document }) });
        const data = await r.json();
        if (!data.success) { showStatus("error", data.error||tKyc(KYC_STATUS_TEXT, "submissionFailed", "Submission failed.")); return; }
    } catch(e) { showStatus("error",`${tKyc(KYC_STATUS_TEXT, "submissionFailedPrefix", "Submission failed:")} ${e.message}`); return; }
    setStep(12);
    await verifyIdentity();
}

async function verifyIdentity() {
    try {
        const r    = await fetch("/verify/submit/", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ session_id:SESSION_ID, tenant_slug:TENANT_SLUG, customer_id:CUSTOMER_ID, front_image:capturedPaths.front, back_image:capturedPaths.back, selfie_image:capturedPaths.selfie, tilt_images:capturedTiltPaths, liveness_verified:livenessCompleted }) });
        const data = await r.json();
        showCompletion(data);
    } catch(e) { showCompletion({ success:false, error:e.message }); }
}

function showCompletion(data) {
    const icon    = document.getElementById("resultIcon");
    const titleEl = document.getElementById("resultTitle");
    const msgEl   = document.getElementById("resultMessage");
    const detEl   = document.getElementById("resultDetails");

    if (data && data.success) {
        icon.textContent    = "OK";
        titleEl.textContent = tKyc(KYC_COMPLETION_TEXT, "submissionReceived", "Submission received");
        msgEl.textContent   = tKyc(KYC_COMPLETION_TEXT, "submittedReviewSoon", "Your verification is submitted. Our team will review it soon.");
        detEl.innerHTML = `<div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left text-sm text-slate-700">
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "aiCheck", "AI check")}:</strong> ${data.verified?tKyc(KYC_COMPLETION_TEXT, "verified", "Verified"):tKyc(KYC_COMPLETION_TEXT, "needsReview", "Needs review")}</div>
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "confidence", "Confidence")}:</strong> ${data.confidence?data.confidence.toFixed(1)+"%":tKyc(KYC_COMPLETION_TEXT, "na", "N/A")}</div>
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "liveness", "Liveness")}:</strong> ${livenessCompleted?tKyc(KYC_COMPLETION_TEXT, "completed", "Completed"):tKyc(KYC_COMPLETION_TEXT, "skipped", "Skipped")}</div>
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "detectedCard", "Detected card")}:</strong> ${data.detected_card?.label||flowData.document_type||tKyc(KYC_COMPLETION_TEXT, "na", "N/A")}</div>
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "cardPhysicalCheck", "Card physical check")}:</strong> ${data.physical_card_check?.verified?tKyc(KYC_COMPLETION_TEXT, "passed", "Passed"):tKyc(KYC_COMPLETION_TEXT, "needsReview", "Needs review")}</div>
            <div><strong>${tKyc(KYC_COMPLETION_TEXT, "physicalScore", "Physical score")}:</strong> ${data.physical_card_check?.physical_card_score?data.physical_card_check.physical_card_score.toFixed(1)+"%":tKyc(KYC_COMPLETION_TEXT, "na", "N/A")}</div>
        </div>`;
    } else {
        icon.textContent    = tKyc(KYC_COMPLETION_TEXT, "review", "Review");
        titleEl.textContent = tKyc(KYC_COMPLETION_TEXT, "submissionReceived", "Submission received");
        msgEl.textContent   = tKyc(KYC_COMPLETION_TEXT, "receivedManualReview", "We received your verification. Our team will review it manually.");
        detEl.innerHTML     = "";
    }
    setStep(13);
}

function showStatus(type, msg) {
    const el = document.getElementById("statusMessage");
    el.className = `status-message active ${type}`;
    el.innerHTML = type === "loading" ? `<div class="spinner"></div>${msg}` : msg;
}
function hideStatus() { document.getElementById("statusMessage").classList.remove("active"); }
function startOver()  { location.reload(); }

window.addEventListener("beforeunload", () => stopCamera());
window.addEventListener("DOMContentLoaded", async () => {
    applySmallScreenDateInputFallback(document);
    const restored = restoreKycFlowAfterLanguageSwitch();
    if (!restored) setStep(0);
    if (DEBUG_MODE === "liveness") {
        await enterLivenessDebugMode();
    }
});

async function enterLivenessDebugMode() {
    if (!TENANT_SLUG || !CUSTOMER_ID) {
        showStatus("error", tKyc(KYC_MISC_TEXT, "debugNeedsTenantCustomer", "Debug liveness mode requires tenant_slug and customer_id."));
        return;
    }

    showStatus("loading", tKyc(KYC_MISC_TEXT, "startingTempLivenessDebug", "Starting temporary liveness debug mode..."));
    const ok = await startSession();
    if (!ok) return;

    flowData.citizenship_type = flowData.citizenship_type || "japanese";
    flowData.document_type = flowData.document_type || "driver_license";
    flowData.document_needs_back = false;
    capturedTiltPaths = Array.from({ length: TILT_FRAME_TARGET }, (_, i) => `debug_tilt_${i + 1}`);
    tiltCaptureIndex = TILT_FRAME_TARGET;
    setStep(9, "livenessScreen");
    hideStatus();

    if (DEBUG_AUTOSTART) {
        startLivenessDetection();
    }
}
