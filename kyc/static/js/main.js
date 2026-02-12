let stream = null;
let SESSION_ID = null;
let actualFacingMode = null;
let livenessCompleted = false;
let livenessListenerAttached = false;

const params = new URLSearchParams(window.location.search);
const TENANT_SLUG = window.TENANT_SLUG || params.get("tenant") || params.get("tenant_slug");
const CUSTOMER_ID = window.CUSTOMER_ID || params.get("customer_id");

const flowSteps = [
    { id: "welcome", title: "Welcome" },
    { id: "citizenship", title: "Residency" },
    { id: "document", title: "Document Selection" },
    { id: "guide", title: "Document Guide" },
    { id: "personal", title: "Personal Info" },
    { id: "address", title: "Address" },
    { id: "contact", title: "Contact" },
    { id: "capture", title: "Document Capture" },
    { id: "liveness", title: "Selfie and Liveness" },
    { id: "review", title: "Review" },
    { id: "submit", title: "Submit" },
    { id: "processing", title: "Processing" },
    { id: "complete", title: "Complete" },
];

const stepScreens = {
    welcome: "welcomeScreen",
    citizenship: "citizenshipScreen",
    document: "documentScreen",
    guide: "guideScreen",
    personal: "personalScreen",
    address: "addressScreen",
    contact: "contactScreen",
    capture: "captureScreen",
    liveness: "livenessScreen",
    review: "reviewScreen",
    submit: "submitScreen",
    processing: "processingScreen",
    complete: "completionScreen",
};

const documentOptions = [
    {
        id: "driver_license",
        label: "Driver License",
        citizenship: ["japanese"],
        needsBack: true,
        guide: "Please prepare your driver license (front and back).",
    },
    {
        id: "my_number",
        label: "My Number Card",
        citizenship: ["japanese"],
        needsBack: true,
        guide: "Please prepare your My Number card (front and back).",
    },
    {
        id: "passport",
        label: "Passport",
        citizenship: ["japanese", "foreign"],
        needsBack: false,
        guide: "Please prepare your passport photo page.",
    },
    {
        id: "residence_card",
        label: "Residence Card",
        citizenship: ["foreign"],
        needsBack: true,
        guide: "Please prepare your residence card (front and back).",
    },
];

const documentFields = {
    driver_license: [
        { id: "license_number", label: "License number", type: "text" },
        { id: "issue_date", label: "Issue date", type: "date" },
        { id: "expiry_date", label: "Expiry date", type: "date" },
    ],
    my_number: [
        { id: "my_number", label: "My Number", type: "text" },
    ],
    passport: [
        { id: "passport_number", label: "Passport number", type: "text" },
        { id: "passport_expiry", label: "Passport expiry", type: "date" },
    ],
    residence_card: [
        { id: "residence_status", label: "Residence status", type: "text" },
        { id: "residence_card_number", label: "Residence card number", type: "text" },
        { id: "residence_card_expiry", label: "Residence card expiry", type: "date" },
    ],
};

const flowData = {
    citizenship_type: null,
    document_type: null,
    document_needs_back: false,
    customer: {},
    document: {
        document_type: null,
        document_data: {},
    },
};

let currentStepIndex = 0;
let captureStep = "front";
let capturedImages = { front: null, back: null, selfie: null };
let capturedPaths = { front: null, back: null, selfie: null };

function showScreen(screenId) {
    document.querySelectorAll("[data-screen]").forEach((screen) => {
        screen.classList.toggle("active", screen.id === screenId);
        screen.classList.toggle("hidden", screen.id !== screenId);
    });
}

function updateProgress() {
    const progress = document.getElementById("stepProgress");
    const label = document.getElementById("stepLabel");
    const title = document.getElementById("stepTitle");
    const total = flowSteps.length;
    const percent = Math.round(((currentStepIndex + 1) / total) * 100);

    if (progress) {
        progress.style.width = `${percent}%`;
    }
    if (label) {
        label.textContent = `Step ${currentStepIndex + 1} of ${total}`;
    }
    if (title) {
        title.textContent = flowSteps[currentStepIndex].title;
    }
}

function setStep(index, screenOverride) {
    currentStepIndex = Math.max(0, Math.min(index, flowSteps.length - 1));
    updateProgress();
    const stepId = flowSteps[currentStepIndex].id;
    const screenId = screenOverride || stepScreens[stepId];
    showScreen(screenId);
}

async function startFlow() {
    const started = await startSession();
    if (!started) {
        return;
    }
    setStep(1);
}

async function startSession() {
    try {
        const res = await fetch("/session/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tenant_slug: TENANT_SLUG, customer_id: CUSTOMER_ID }),
        });
        const data = await res.json();
        if (!data.success) {
            showStatus("error", "Failed to start session.");
            return false;
        }
        SESSION_ID = data.session_id;
        return true;
    } catch (err) {
        showStatus("error", `Session start failed: ${err.message}`);
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
    const container = document.getElementById("documentOptions");
    if (!container) {
        return;
    }

    const options = documentOptions.filter((option) => option.citizenship.includes(flowData.citizenship_type));
    container.innerHTML = options
        .map(
            (option) => `
            <button class="rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50" onclick="selectDocument('${option.id}')">
                ${option.label}
            </button>
        `,
        )
        .join("");
}

function selectDocument(docId) {
    const selection = documentOptions.find((option) => option.id === docId);
    if (!selection) {
        return;
    }

    flowData.document_type = docId;
    flowData.document_needs_back = selection.needsBack;
    flowData.document.document_type = docId;
    flowData.document.document_data = {};

    const guideTitle = document.getElementById("guideTitle");
    const guideBody = document.getElementById("guideBody");
    if (guideTitle) {
        guideTitle.textContent = selection.label;
    }
    if (guideBody) {
        guideBody.textContent = selection.guide;
    }

    renderDocumentFields(docId);
    setStep(3);
}

function goToPersonalInfo() {
    setStep(4);
}

function renderDocumentFields(docId) {
    const container = document.getElementById("documentSpecificFields");
    if (!container) {
        return;
    }

    const fields = documentFields[docId] || [];
    container.innerHTML = fields
        .map(
            (field) => `
            <div>
                <label class="text-xs font-semibold text-slate-600">${field.label}</label>
                <input id="doc_${field.id}" type="${field.type}" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
            </div>
        `,
        )
        .join("");
}

function savePersonalInfo() {
    const fullName = document.getElementById("fullName").value.trim();
    if (!fullName) {
        showStatus("error", "Full name is required.");
        return;
    }

    flowData.customer.full_name = fullName;
    flowData.customer.full_name_kana = document.getElementById("fullNameKana").value.trim();
    flowData.customer.date_of_birth = document.getElementById("dateOfBirth").value;
    flowData.customer.gender = document.getElementById("gender").value;
    flowData.customer.nationality = document.getElementById("nationality").value.trim();
    flowData.customer.citizenship_type = flowData.citizenship_type;

    const fields = documentFields[flowData.document_type] || [];
    fields.forEach((field) => {
        const fieldInput = document.getElementById(`doc_${field.id}`);
        if (!fieldInput) {
            return;
        }
        const value = fieldInput.value.trim();
        if (!value) {
            return;
        }
        flowData.document.document_data[field.id] = value;

        if (field.id === "residence_status") {
            flowData.document.residence_status = value;
        }
        if (field.id === "residence_card_number") {
            flowData.document.residence_card_number = value;
        }
        if (field.id === "residence_card_expiry") {
            flowData.document.residence_card_expiry = value;
        }
    });

    setStep(5);
}

function saveAddressInfo() {
    flowData.customer.postal_code = document.getElementById("postalCode").value.trim();
    flowData.customer.prefecture = document.getElementById("prefecture").value.trim();
    flowData.customer.city = document.getElementById("city").value.trim();
    flowData.customer.street_address = document.getElementById("streetAddress").value.trim();
    setStep(6);
}

function saveContactInfo() {
    flowData.customer.email = document.getElementById("email").value.trim();
    flowData.customer.phone = document.getElementById("phone").value.trim();
    flowData.customer.external_ref = document.getElementById("externalRef").value.trim();

    setStep(7);
    startDocumentCapture();
}

function startDocumentCapture() {
    captureStep = "front";
    showCaptureScreen();
}

function showCaptureScreen() {
    setStep(7, "captureScreen");
    updateCaptureUI();
    document.getElementById("previewContainer").classList.remove("active");
    document.getElementById("cameraContainer").classList.add("active");
    startCamera();
}

function updateCaptureUI() {
    const title = document.getElementById("captureTitle");
    const subtitle = document.getElementById("captureSubtitle");
    const instructions = document.getElementById("instructions");
    const guideBox = document.getElementById("guideBox");

    if (captureStep === "selfie") {
        if (title) title.textContent = "Capture your selfie";
        if (subtitle) subtitle.textContent = "Make sure your face is centered and clear.";
        if (instructions) instructions.textContent = "Position your face within the frame";
        if (guideBox) guideBox.classList.add("selfie");
        return;
    }

    if (captureStep === "back") {
        if (title) title.textContent = "Capture the back of your document";
        if (subtitle) subtitle.textContent = "Make sure the back side is clear and readable.";
        if (instructions) instructions.textContent = "Position the back within the frame";
    } else {
        if (title) title.textContent = "Capture the front of your document";
        if (subtitle) subtitle.textContent = "Make sure all details are clear and readable.";
        if (instructions) instructions.textContent = "Position the front within the frame";
    }

    if (guideBox) guideBox.classList.remove("selfie");
}

async function startCamera() {
    try {
        const video = document.getElementById("video");

        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }
        video.srcObject = null;

        const constraints = {
            video: {
                facingMode: captureStep === "selfie" ? "user" : { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
        };

        stream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = stream;

        const videoTrack = stream.getVideoTracks()[0];
        const settings = videoTrack.getSettings();
        actualFacingMode = settings.facingMode;

        if (actualFacingMode === "environment") {
            video.classList.add("no-mirror");
        } else {
            video.classList.remove("no-mirror");
        }

        await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error("Video load timeout")), 10000);
            video.onloadedmetadata = () => {
                clearTimeout(timeout);
                video.play().then(resolve).catch(reject);
            };
        });

        setupCaptureButton();
    } catch (error) {
        let errorMessage = "Camera access failed: ";
        if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
            errorMessage = "Camera permission denied. Please allow camera access in your browser settings.";
        } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
            errorMessage = "No camera found on your device.";
        } else if (error.name === "NotReadableError" || error.name === "TrackStartError") {
            errorMessage = "Camera is already in use by another application.";
        } else {
            errorMessage += error.message;
        }
        showStatus("error", errorMessage);
    }
}

function setupCaptureButton() {
    const captureBtn = document.getElementById("captureBtn");
    captureBtn.onclick = capturePhoto;
}

function capturePhoto() {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageData = canvas.toDataURL("image/jpeg", 0.95);
    capturedImages[captureStep] = imageData;

    document.getElementById("cameraContainer").classList.remove("active");
    document.getElementById("previewContainer").classList.add("active");
    document.getElementById("previewImage").src = imageData;
}

function retakePhoto() {
    document.getElementById("previewContainer").classList.remove("active");
    document.getElementById("cameraContainer").classList.add("active");
}

async function confirmPhoto() {
    if (!SESSION_ID) {
        showStatus("error", "Missing session. Please restart verification.");
        return;
    }

    const imageData = capturedImages[captureStep];
    showStatus("loading", "Uploading image...");

    try {
        const response = await fetch("/capture/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: SESSION_ID,
                tenant_slug: TENANT_SLUG,
                image: imageData,
                type: captureStep,
            }),
        });

        const data = await response.json();
        if (!data.success) {
            showStatus("error", data.error || "Capture failed.");
            return;
        }

        capturedPaths[captureStep] = data.filename;
        hideStatus();
        document.getElementById("previewContainer").classList.remove("active");

        if (captureStep === "front" && flowData.document_needs_back) {
            captureStep = "back";
            updateCaptureUI();
            document.getElementById("cameraContainer").classList.add("active");
            startCamera();
            return;
        }

        if (captureStep === "front" || captureStep === "back") {
            stopCamera();
            goToLiveness();
            return;
        }

        if (captureStep === "selfie") {
            stopCamera();
            renderReview();
            setStep(9);
        }
    } catch (error) {
        showStatus("error", `Upload failed: ${error.message}`);
    }
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
    }
}

function goToLiveness() {
    setStep(8);
}

async function startLivenessDetection() {
    if (!SESSION_ID) {
        showStatus("error", "Missing session. Please restart verification.");
        return;
    }

    const w = window.open(
        `/liveness?session_id=${encodeURIComponent(SESSION_ID)}`,
        "livenessWindow",
        "width=520,height=820",
    );

    if (!w) {
        showStatus("error", "Popup blocked. Allow popups for this site and try again.");
        return;
    }

    showStatus("loading", "Starting liveness detection...");

    try {
        await fetch("/start-liveness/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: SESSION_ID, tenant_slug: TENANT_SLUG }),
        });
    } catch (e) {
        console.log("start-liveness failed:", e);
    }

    if (livenessListenerAttached) return;
    livenessListenerAttached = true;

    window.addEventListener(
        "message",
        async (event) => {
            try {
                if (!event.data || event.data.type !== "liveness_result") return;

                const result = event.data.data || {};
                result.session_id = SESSION_ID;

                await fetch("/liveness-result", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ...result, tenant_slug: TENANT_SLUG, customer_id: CUSTOMER_ID }),
                });

                if (result.verified) {
                    livenessCompleted = true;
                    showStatus("success", `Liveness verified. Confidence: ${result.confidence}%`);
                    setTimeout(() => proceedAfterLiveness(), 1200);
                } else {
                    showStatus("error", "Liveness verification failed. Please try again.");
                    setTimeout(() => hideStatus(), 2000);
                }
            } catch (e) {
                console.log("Liveness handler error:", e);
                showStatus("error", "Failed to save liveness result.");
            } finally {
                livenessListenerAttached = false;
            }
        },
        { once: true },
    );
}

function skipLiveness() {
    if (confirm("Skipping liveness detection may reduce security. Continue anyway?")) {
        livenessCompleted = false;
        proceedAfterLiveness();
    }
}

function proceedAfterLiveness() {
    hideStatus();
    captureStep = "selfie";
    updateCaptureUI();
    setStep(8, "captureScreen");
    document.getElementById("cameraContainer").classList.add("active");
    document.getElementById("previewContainer").classList.remove("active");
    startCamera();
}

function renderReview() {
    const summary = document.getElementById("reviewSummary");
    if (!summary) {
        return;
    }

    const docInfo = documentOptions.find((option) => option.id === flowData.document_type);
    const docLabel = docInfo ? docInfo.label : flowData.document_type || "";

    summary.innerHTML = `
        <div class="space-y-3">
            <div><strong>Citizenship:</strong> ${flowData.citizenship_type || ""}</div>
            <div><strong>Document:</strong> ${docLabel}</div>
            <div><strong>Full name:</strong> ${flowData.customer.full_name || ""}</div>
            <div><strong>Date of birth:</strong> ${flowData.customer.date_of_birth || ""}</div>
            <div><strong>Nationality:</strong> ${flowData.customer.nationality || ""}</div>
            <div><strong>Address:</strong> ${flowData.customer.prefecture || ""} ${flowData.customer.city || ""} ${flowData.customer.street_address || ""}</div>
            <div><strong>Contact:</strong> ${flowData.customer.email || ""} ${flowData.customer.phone || ""}</div>
            <div><strong>Document images:</strong> ${capturedPaths.front ? "Front" : ""} ${capturedPaths.back ? "Back" : ""}</div>
            <div><strong>Selfie:</strong> ${capturedPaths.selfie ? "Captured" : "Pending"}</div>
            <div><strong>Liveness:</strong> ${livenessCompleted ? "Completed" : "Skipped"}</div>
        </div>
    `;
}

async function submitFlow() {
    setStep(10);

    try {
        const submitRes = await fetch("/session/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: SESSION_ID,
                tenant_slug: TENANT_SLUG,
                customer: flowData.customer,
                document: flowData.document,
            }),
        });
        const submitData = await submitRes.json();
        if (!submitData.success) {
            showStatus("error", submitData.error || "Submission failed.");
            return;
        }
    } catch (error) {
        showStatus("error", `Submission failed: ${error.message}`);
        return;
    }

    setStep(11);
    await verifyIdentity();
}

async function verifyIdentity() {
    try {
        const response = await fetch("/verify/submit/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: SESSION_ID,
                tenant_slug: TENANT_SLUG,
                customer_id: CUSTOMER_ID,
                front_image: capturedPaths.front,
                back_image: capturedPaths.back,
                selfie_image: capturedPaths.selfie,
                liveness_verified: livenessCompleted,
            }),
        });

        const data = await response.json();
        showCompletion(data);
    } catch (error) {
        showCompletion({ success: false, error: error.message });
    }
}

function showCompletion(data) {
    const resultIcon = document.getElementById("resultIcon");
    const resultTitle = document.getElementById("resultTitle");
    const resultMessage = document.getElementById("resultMessage");
    const resultDetails = document.getElementById("resultDetails");

    if (data && data.success) {
        resultIcon.textContent = "OK";
        resultTitle.textContent = "Submission received";
        resultMessage.textContent = "Your verification is submitted. Our team will review it soon.";
        resultDetails.innerHTML = `
            <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left text-sm text-slate-700">
                <div><strong>AI check:</strong> ${data.verified ? "Verified" : "Needs review"}</div>
                <div><strong>Confidence:</strong> ${data.confidence ? data.confidence.toFixed(1) + "%" : "N/A"}</div>
                <div><strong>Liveness:</strong> ${livenessCompleted ? "Completed" : "Skipped"}</div>
            </div>
        `;
    } else {
        resultIcon.textContent = "Review";
        resultTitle.textContent = "Submission received";
        resultMessage.textContent = "We received your verification. Our team will review it manually.";
        resultDetails.innerHTML = "";
    }

    setStep(12);
}

function showStatus(type, message) {
    const statusEl = document.getElementById("statusMessage");
    statusEl.className = `status-message active ${type}`;
    statusEl.innerHTML = type === "loading" ? `<div class="spinner"></div>${message}` : message;
}

function hideStatus() {
    document.getElementById("statusMessage").classList.remove("active");
}

function startOver() {
    location.reload();
}

window.addEventListener("beforeunload", () => {
    stopCamera();
});

window.addEventListener("DOMContentLoaded", () => {
    setStep(0);
});
