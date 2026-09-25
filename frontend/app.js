// ============================================================

// GUARDNET-AI FRONTEND

// APP.JS - FINAL REPORT DETAIL PAGE NAVIGATION

// ============================================================

const API_BASE_URL = "http://127.0.0.1:8000";

let lastAnalysis = null;
let reportsCache = [];
let casesCache = [];
let reportRefreshTimer = null;

// ============================================================
// HELPER
// ============================================================

const $ = (id) => document.getElementById(id);
function escapeHtml(value) {
    const div = document.createElement("div");

    div.textContent = value ?? "";

    return div.innerHTML;

}

function formatDate(value) {

    if (!value) {

        return "-";

    }

    const date = new Date(value);


    if (Number.isNaN(date.getTime())) {

        return String(value);

    }

    return date.toLocaleString("id-ID", {

        dateStyle: "medium",

        timeStyle: "short"

    });

}

function riskClass(value) {

    const risk =

        String(value || "low")

            .toLowerCase();

    return [

        "low",

        "medium",

        "high"

    ].includes(risk)

        ? risk

        : "low";

}

function getReportSite(report) {
    const site =
        report?.site &&
        typeof report.site === "object"
            ? report.site
            : {};

    return {
        content_url:
            report?.content_url ||
            report?.source_url ||
            site.content_url ||
            site.source_url ||
            "-",

        platform:
            report?.platform ||
            site.platform ||
            "-",

        content_type:
            report?.content_type ||
            site.content_type ||
            "-"
    };
}


function getReportIndicators(report) {
    if (Array.isArray(report?.detected_indicators)) {
        return report.detected_indicators;
    }

    if (Array.isArray(report?.indicators)) {
        return report.indicators;
    }

    if (Array.isArray(report?.analysis?.final?.indicators)) {
        return report.analysis.final.indicators;
    }

    return [];
}

function showError(message) {


    const box = $("errorBox");

    if (!box) {

        return;

    }
    box.textContent =

        message || "Terjadi kesalahan.";


    box.style.display = "block";

}

function hideError() {

    const box = $("errorBox");

    if (!box) {

        return;

    }

    box.textContent = "";

    box.style.display = "none";

}

function setLoading(active) {

    const loading = $("loading");

    const button =

        $("analyzeButton");


    if (loading) {


        loading.style.display =

            active

                ? "flex"

                : "none";

    }

    if (button) {

        button.disabled = active;
        button.textContent =
            active

                ? "Menganalisis..."

                : "🔍 Analisis Content";

    }

}
async function readJson(response) {

    const text =

        await response.text();

    if (!text) {

        return {};

    }

    try {

        return JSON.parse(text);

    } catch {

        return {

            detail: text

        };

    }

}

function setTextIfExists(

    id,

    value

) {

    const element = $(id);

    if (!element) {

        return;

    }

    element.textContent =

        value == null

            ? "-"

            : String(value);

}

// ============================================================
// PAGE TITLE
// ===========================================================

const pageTitles = {

    dashboardPage:

        "Dashboard",

    analysisPage:

        "Analisis Content",

    resultPage:

        "Hasil Analisis",

    casesPage:

        "Daftar Kasus",


    reportsPage:

        "Pelaporan",

    reportDetailPage:

        "Detail Laporan"

};

// ============================================================
// CREATE DETAIL PAGE AUTOMATICALLY
// ============================================================

function ensureReportDetailPage() {

    let page =

        $("reportDetailPage");

    if (page) {

        return page;

    }

    page =

        document.createElement("section");

    page.id =

        "reportDetailPage";

    page.className =

        "page";

    page.innerHTML = `

        <div

            id="reportDetailContent"

            class="report-detail-content"

        ></div>

    `;

    const main =

        document.querySelector(".main");

    if (main) {

        main.appendChild(page);

    } else {

        document.body.appendChild(page);

    }

    return page;

}

// ===========================================================
// NAVIGATION
// ==========================================================

function openPage(pageId) {

    if (!pageId) {

        return;

    }

    // Pastikan halaman detail tersedia

    if (

        pageId ===

        "reportDetailPage"

    ) {

        ensureReportDetailPage();

    }

    document

        .querySelectorAll(".page")

        .forEach((page) => {


            page.classList.toggle(

                "active",

                page.id === pageId

            );


        });

    document

        .querySelectorAll(".page-section")

        .forEach((page) => {


            page.classList.toggle(

                "active",

                page.id === pageId

            );


        });

    // Reset posisi halaman

    // BUKAN scroll ke detail.

    window.scrollTo({

        top: 0,

        behavior: "auto"

    });

    const main =

        document.querySelector(".main");

    if (main) {

        main.scrollTop = 0;

    }

    document

        .querySelectorAll(

            ".nav-btn, .nav-item"

        )

        .forEach((button) => {

            const target =

                button.dataset.page ||

                button.getAttribute(

                    "data-target"

                ) ||

                button

                    .getAttribute("href")

                    ?.replace("#", "");

            button.classList.toggle(

                "active",

                target === pageId

            );

        });

    const pageTitle =

        $("pageTitle");

    if (pageTitle) {

        pageTitle.textContent =

            pageTitles[pageId] ||

            "GuardNet-AI";

    }

    if (

        pageId ===

        "dashboardPage"

    ) {
        loadDashboard();

    }

    if (

        pageId ===

        "casesPage"
    ) {
        loadCases();

    }

    if (

        pageId ===

        "reportsPage"

    ) {

        loadReports();

    }

    closeSidebar();

}

function showPage(pageId) {


    openPage(pageId);

}

// ============================================================
// SIDEBAR
// ============================================================
function closeSidebar() {

    $("sidebar")

        ?.classList

        .remove("open");

    $("overlay")

        ?.classList

        .remove("open");

    $("sidebarOverlay")

        ?.classList

        .remove("open");

}

function toggleSidebar() {

    $("sidebar")

        ?.classList

        .toggle("open");

    $("overlay")

        ?.classList

        .toggle("open");



    $("sidebarOverlay")

        ?.classList

        .toggle("open");

}

// ============================================================
// IMAGE PREVIEW
// ============================================================

function setupImagePreview() {

    const input =

        $("contentFile");


    const preview =

        $("preview");



    if (!input || !preview) {

        return;

    }

    input.addEventListener(

        "change",

        () => {


            const file =

                input.files?.[0];



            if (!file) {


                preview.style.display =

                    "none";


                preview.removeAttribute(

                    "src"

                );


                return;

            }

            if (

                !file.type.startsWith(

                    "image/"

                )

            ) {

                preview.style.display =

                    "none";

                showError(

                    "File harus berupa gambar."

                );

                return;

            }

            hideError();

            const reader =

                new FileReader();

            reader.onload =

                (event) => {

                    preview.src =

                        event.target.result;

                    preview.style.display =

                        "block";

                };

            reader.readAsDataURL(

                file

            );

        }

    );

}
// ============================================================
// FULL MULTIMODAL ANALYSIS
// ============================================================

async function analyzeFullContent() {

    const input =

        $("contentFile");

    const file =

        input?.files?.[0];

    if (!file) {

        showError(

            "Silakan upload gambar content terlebih dahulu."

        );

        openPage(

            "analysisPage"

        );

        return;

    }

    if (

        !file.type.startsWith(

            "image/"

        )

    ) {

        showError(

            "Format file harus JPG, JPEG, PNG, atau WEBP."

        );

        return;

    }

    hideError();

    setLoading(true);

    const platform =

        $("platform")?.value ||

        "other";

    const contentType =

        $("contentType")?.value ||

        "image";

    const contentUrl =

        $("contentUrl")

            ?.value

            .trim() ||

        "";

    const detectedText =

        $("detectedText")

            ?.value

            .trim() ||

        "";

    try {

        const formData =

            new FormData();

        formData.append(

            "file",
            file,
            file.name

        );

        const params =

            new URLSearchParams();

        params.set(

            "platform",
            platform

        );

        params.set(

            "content_type",
            contentType

        );

        if (contentUrl) {
            params.set(

                "content_url",

                contentUrl

            );

        }

        if (detectedText) {

            params.set(

                "detected_text",

                detectedText

            );

        }

        console.log(

            "GuardNet-AI: Mengirim /analyze-full..."

        );

        const response =

            await fetch(

                `${API_BASE_URL}/analyze-full?${params.toString()}`,

                {

                    method: "POST",

                    body: formData

                }

            );

        const data =

            await readJson(

                response

            );

        console.log(

            "GuardNet-AI FULL RESULT:",

            data

        );

        if (!response.ok) {


            throw new Error(

                data.detail ||

                data.message ||

                `Analisis gagal. HTTP ${response.status}`

            );

        }

        lastAnalysis =

            data;

        lastAnalysis.platform =

            data.platform ||

            platform;

        lastAnalysis.content_url =

            data.content_url ||

            contentUrl;

        lastAnalysis.original_file_name =

            file.name;

        displayAnalysisResult(

            lastAnalysis

        );

        openPage(

            "resultPage"

        );

        await Promise.allSettled([

            loadDashboard(),

            loadCases(),

            loadReports()

        ]);

    } catch (error) {

        console.error(

            "GuardNet-AI Analysis Error:",

            error

        );

        showError(

            `Terjadi kesalahan: ${error.message}`

        );

        openPage(

            "analysisPage"

        );

    } finally {


        setLoading(false);

    }

}
// ============================================================
// TEXT ANALYSIS
// ============================================================

async function analyzeContent() {

    const detectedText =

        $("detectedText")

            ?.value

            .trim() ||

        "";

    if (!detectedText) {

        showError(

            "Masukkan teks content atau upload gambar."

        );


        openPage(

            "analysisPage"

        );


        return;

    }



    hideError();


    setLoading(true);



    try {


        const params =

            new URLSearchParams();



        params.set(

            "platform",

            $("platform")?.value ||

            "other"

        );



        params.set(

            "content_type",

            $("contentType")?.value ||

            "text"

        );



        params.set(

            "detected_text",

            detectedText

        );



        const contentUrl =

            $("contentUrl")

                ?.value

                .trim() ||

            "";



        if (contentUrl) {


            params.set(

                "content_url",

                contentUrl

            );

        }



        const contentResponse =

            await fetch(

                `${API_BASE_URL}/contents?${params.toString()}`,

                {

                    method: "POST"

                }

            );



        const contentData =

            await readJson(

                contentResponse

            );



        if (!contentResponse.ok) {


            throw new Error(

                contentData.detail ||

                `Gagal menyimpan content. HTTP ${contentResponse.status}`

            );

        }



        const contentId =

            contentData.content_id;



        if (!contentId) {


            throw new Error(

                "Content ID tidak ditemukan."

            );

        }



        const response =

            await fetch(

                `${API_BASE_URL}/analyze?content_id=${encodeURIComponent(contentId)}`,

                {

                    method: "POST"

                }

            );



        const data =

            await readJson(

                response

            );



        if (!response.ok) {


            throw new Error(

                data.detail ||

                `Analisis gagal. HTTP ${response.status}`

            );

        }



        data.platform =

            $("platform")?.value ||

            "other";



        data.content_url =

            contentUrl;



        lastAnalysis =

            data;



        displayAnalysisResult(

            data

        );



        openPage(

            "resultPage"

        );



        await Promise.allSettled([

            loadDashboard(),

            loadCases(),

            loadReports()

        ]);



    } catch (error) {


        console.error(

            "Text Analysis Error:",

            error

        );



        showError(

            `Terjadi kesalahan: ${error.message}`

        );



    } finally {


        setLoading(false);

    }

}



// ============================================================

// DISPLAY ANALYSIS RESULT

// ============================================================


function displayAnalysisResult(data) {


    if (!data) {

        return;

    }



    const risk =

        riskClass(

            data.risk_level ||

            data.final_risk ||

            data.analysis

                ?.final

                ?.risk_level

        );



    const riskBox =

        $("riskBox");



    if (riskBox) {


        riskBox.classList.remove(

            "risk-low",

            "risk-medium",

            "risk-high"

        );



        riskBox.classList.add(

            `risk-${risk}`

        );

    }



    setTextIfExists(

        "riskLevel",

        risk.toUpperCase()

    );



    setTextIfExists(

        "caseId",

        data.case_id ||

        "-"

    );



    setTextIfExists(

        "contentId",

        data.content_id ||

        "-"

    );



    const score =

        data.score ??

        data.final_score ??

        data.analysis

            ?.final

            ?.score ??

        0;



    setTextIfExists(

        "score",

        typeof score === "number"

            ? score.toFixed(2)

            : score

    );



    setTextIfExists(

        "resultPlatform",

        data.platform ||

        $("platform")

            ?.value ||

        "-"

    );



    setTextIfExists(

        "ocrResult",

        data.ocr_text ||

        data.ocr?.ocr_text ||

        "Tidak ada teks OCR yang terdeteksi."

    );



    setTextIfExists(

        "description",

        data.description ||

        "Tidak ada deskripsi."

    );



    renderIndicators(

        data.detected_indicators ||

        data.analysis

            ?.final

            ?.indicators ||

        []

    );



    renderLatestPayment(

        data.payment

    );



    setTextIfExists(

        "resultUrl",

        data.content_url ||

        $("contentUrl")

            ?.value ||

        "-"

    );



    setTextIfExists(

        "resultReportId",

        data.report_id ||

        "-"

    );



    setTextIfExists(

        "resultReportStatus",

        data.report_status ||

        "-"

    );



    setTextIfExists(

        "evidenceStatus",

        data.evidence_status ||

        data.evidence

            ?.integrity_status ||

        "-"

    );

}



// ============================================================

// INDICATORS

// ============================================================


function renderIndicators(

    indicators

) {


    const list =

        $("indicatorList");



    if (!list) {

        return;

    }



    list.innerHTML = "";



    if (

        !Array.isArray(indicators) ||

        indicators.length === 0

    ) {


        list.innerHTML = `

            <span class="chip">

                Tidak ditemukan indikator.

            </span>

        `;


        return;

    }



    indicators.forEach(

        (indicator) => {


            const chip =

                document.createElement(

                    "span"

                );



            chip.className =

                "chip";



            chip.textContent =

                indicator;



            list.appendChild(

                chip

            );

        }

    );

}



// ============================================================

// PAYMENT RESULT

// ============================================================


function renderLatestPayment(

    payment

) {


    const resultPage =

        $("resultPage");



    if (!resultPage) {

        return;

    }



    let panel =

        $("latestPaymentPanel");



    if (!panel) {


        panel =

            document.createElement(

                "div"

            );



        panel.id =

            "latestPaymentPanel";



        panel.className =

            "detail-section";



        const card =

            resultPage.querySelector(

                ".card"

            );



        if (card) {


            card.appendChild(

                panel

            );

        }

    }



    if (

        !payment ||

        !payment.payment_detected

    ) {


        panel.innerHTML = `

            <h4>

                💳 Payment Intelligence

            </h4>


            <div class="empty">

                Tidak ada payment indicator

                yang terdeteksi pada content ini.

            </div>

        `;


        return;

    }



    const payments =

        Array.isArray(

            payment.payments

        )

            ? payment.payments

            : [];



    panel.innerHTML = `

        <div class="row">


            <h4 style="margin-bottom:0">

                💳 Payment Intelligence

            </h4>


            <span class="badge">

                ${escapeHtml(

                    payment.verification_status ||

                    "unverified"

                )}

            </span>


        </div>


        <div

            class="payment-grid"

            style="margin-top:12px"

        >


            <div>

                <span>

                    Payment Type

                </span>


                <strong>

                    ${escapeHtml(

                        payment.payment_type ||

                        "unknown"

                    )}

                </strong>

            </div>


            <div>

                <span>

                    QR Detected

                </span>


                <strong>

                    ${

                        payment.qr_detected

                            ? "Ya"

                            : "Tidak"

                    }

                </strong>

            </div>


            <div>

                <span>

                    Jumlah Kandidat

                </span>


                <strong>

                    ${payments.length}

                </strong>

            </div>


            <div>

                <span>

                    Verification

                </span>


                <strong>

                    ${

                        String(

                            payment.verification_status ||

                            ""

                        ).toLowerCase() ===

                        "verified"

                            ? "Verified"

                            : "Menunggu validasi"

                    }

                </strong>

            </div>


        </div>

    `;

}



// ============================================================

// DASHBOARD

// ============================================================


async function loadDashboard() {


    try {


        const response =

            await fetch(

                `${API_BASE_URL}/dashboard`

            );



        const data =

            await readJson(

                response

            );



        if (!response.ok) {


            throw new Error(

                data.detail ||

                `Dashboard gagal dimuat. HTTP ${response.status}`

            );

        }



        const total =

            data.total_cases ??

            data.total ??

            0;



        const summary =

            data.risk_summary ||

            data.risk_counts ||

            {};



        setTextIfExists(

            "totalCases",

            total

        );



        setTextIfExists(

            "highRisk",

            summary.high ??

            data.high_risk ??

            0

        );



        setTextIfExists(

            "mediumRisk",

            summary.medium ??

            data.medium_risk ??

            0

        );



        setTextIfExists(

            "lowRisk",

            summary.low ??

            data.low_risk ??

            0

        );



    } catch (error) {


        console.error(

            "Dashboard Error:",

            error

        );

    }

}



// ============================================================

// CASES

// ============================================================


async function loadCases() {


    const list =

        $("caseList");



    if (!list) {

        return;

    }



    list.innerHTML = `

        <div class="loading-state">

            Memuat daftar kasus...

        </div>

    `;



    try {


        const response =

            await fetch(

                `${API_BASE_URL}/cases`

            );



        const data =

            await readJson(

                response

            );



        if (!response.ok) {


            throw new Error(

                data.detail ||

                `Cases gagal dimuat. HTTP ${response.status}`

            );

        }



        casesCache =

            Array.isArray(data)

                ? data

                : (

                    data.cases ||

                    data.items ||

                    []

                );



        renderCases(

            casesCache

        );



    } catch (error) {


        console.error(

            "Cases Error:",

            error

        );



        list.innerHTML = `

            <div class="empty">

                Gagal memuat daftar kasus.

                <br>

                <small>

                    ${escapeHtml(

                        error.message

                    )}

                </small>

            </div>

        `;

    }

}



function renderCases(cases) {


    const list =

        $("caseList");



    if (!list) {

        return;

    }



    list.innerHTML = "";



    if (

        !Array.isArray(cases) ||

        cases.length === 0

    ) {


        list.innerHTML = `

            <div class="empty">

                Belum ada kasus terdeteksi.

            </div>

        `;


        return;

    }



    cases.forEach(

        (item) => {


            const risk =

                riskClass(

                    item.risk_level ||

                    item.risk

                );



            const caseId =

                item.case_id ||

                item.id ||

                "-";



            const url =

                item.content_url ||

                item.source_url ||

                "-";



            const platform =

                item.platform ||

                "-";



            const created =

                item.created_at ||

                item.detected_at ||

                item.timestamp;



            const card =

                document.createElement(

                    "div"

                );



            card.className =

                "case-card";



            card.innerHTML = `

                <div class="case-header">


                    <div>


                        <strong>

                            ${escapeHtml(

                                caseId

                            )}

                        </strong>


                        <div class="muted">

                            ${escapeHtml(

                                platform

                            )}

                        </div>


                    </div>


                    <span class="risk-badge ${risk}">

                        ${risk.toUpperCase()}

                    </span>


                </div>


                <div class="case-url">

                    ${escapeHtml(url)}

                </div>


                <div class="case-meta">

                    ${escapeHtml(

                        formatDate(created)

                    )}

                </div>

            `;



            card.addEventListener(

                "click",

                () => {


                    showCaseDetail(

                        item

                    );

                }

            );



            list.appendChild(

                card

            );

        }

    );

}



// ============================================================

// CASE DETAIL

// ============================================================


function showCaseDetail(item) {


    if (!item) {

        return;

    }



    const risk =

        riskClass(

            item.risk_level ||

            item.risk

        );



    const indicators =

        Array.isArray(

            item.detected_indicators

        )

            ? item.detected_indicators

            : [];



    alert(

        [

            `Case ID: ${

                item.case_id ||

                item.id ||

                "-"

            }`,


            `Risk: ${

                risk.toUpperCase()

            }`,


            `Platform: ${

                item.platform ||

                "-"

            }`,


            `URL: ${

                item.content_url ||

                item.source_url ||

                "-"

            }`,


            `Indikator: ${

                indicators.join(", ") ||

                "-"

            }`

        ].join("\n")

    );

}



// ============================================================

// REPORTING

// ============================================================


async function loadReports() {


    const list =

        $("reportList");



    if (!list) {

        return;

    }



    list.innerHTML = `

        <div class="loading-state">

            Memuat data pelaporan...

        </div>

    `;



    try {


        const response =

            await fetch(

                `${API_BASE_URL}/reports`

            );



        const data =

            await readJson(

                response

            );



        if (!response.ok) {


            throw new Error(

                data.detail ||

                `Reports gagal dimuat. HTTP ${response.status}`

            );

        }



        reportsCache =

            Array.isArray(data)

                ? data

                : (

                    data.reports ||

                    data.items ||

                    []

                );



        renderReportSummary(

            reportsCache

        );



        renderReports(

            reportsCache

        );



    } catch (error) {


        console.error(

            "Reports Error:",

            error

        );



        reportsCache = [];



        renderReportSummary(

            []

        );



        list.innerHTML = `

            <div class="empty">

                Gagal memuat data pelaporan.

                <br>

                <small>

                    ${escapeHtml(

                        error.message

                    )}

                </small>

            </div>

        `;

    }

}



// ============================================================

// REPORT SUMMARY

// ============================================================


function renderReportSummary(

    reports

) {


    const total =

        reports.length;



    const high =

        reports.filter(

            (report) =>

                String(

                    report.risk_level ||

                    ""

                ).toLowerCase() ===

                "high"

        ).length;



    const medium =

        reports.filter(

            (report) =>

                String(

                    report.risk_level ||

                    ""

                ).toLowerCase() ===

                "medium"

        ).length;



    let verifiedPayment = 0;



    reports.forEach(

        (report) => {


            const payments =

                Array.isArray(

                    report.payments

                )

                    ? report.payments

                    : [];



            verifiedPayment +=

                payments.filter(

                    (payment) =>

                        String(

                            payment.verification_status ||

                            ""

                        ).toLowerCase() ===

                        "verified"

                ).length;

        }

    );



    setTextIfExists(

        "reportTotal",

        total

    );



    setTextIfExists(

        "reportHigh",

        high

    );



    setTextIfExists(

        "reportMedium",

        medium

    );



    setTextIfExists(

        "reportPayment",

        verifiedPayment

    );

}



// ============================================================


// ============================================================
// REPORT PACKAGE DOWNLOAD
// ============================================================
async function downloadReportPackage(reportId) {
    if (!reportId || reportId === "-") {
        showError("Report ID tidak ditemukan.");
        return;
    }

    try {
        hideError();

        const response = await fetch(
            `${API_BASE_URL}/reports/${encodeURIComponent(reportId)}/package`
        );

        if (!response.ok) {
            let message = `Gagal membuat Report Package. HTTP ${response.status}`;
            try {
                const data = await response.json();
                message = data.detail || data.message || message;
            } catch (_) {}
            throw new Error(message);
        }

        const blob = await response.blob();
        const disposition =
            response.headers.get("Content-Disposition") || "";

        let filename = `GuardNetAI_Report_${reportId}.zip`;
        const filenameMatch =
            disposition.match(/filename="?([^"]+)"?/i);

        if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
        }

        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        console.log(
            "GuardNet-AI: Report Package berhasil di-download.",
            filename
        );
    } catch (error) {
        console.error("Report Package Error:", error);
        showError(`Gagal download Report Package: ${error.message}`);
    }
}

// REPORT LIST

// ============================================================


function renderReports(

    reports

) {


    const list =

        $("reportList");



    if (!list) {

        return;

    }



    list.innerHTML = "";



    if (

        !Array.isArray(reports) ||

        reports.length === 0

    ) {


        list.innerHTML = `

            <div class="empty">

                Belum ada laporan.

            </div>

        `;


        return;

    }



    reports.forEach(

        (report) => {


            const risk =

                riskClass(

                    report.risk_level

                );



            const reportId =

                report.id ??

                report.report_id ??

                "-";



            const caseId =

                report.case_id ||

                "-";



            const site = getReportSite(report);

            const url =
                site.content_url;

            const platform =
                site.platform;



            const status =

                report.status ||

                "draft";



            const indicators = getReportIndicators(report);



            const payments =

                Array.isArray(

                    report.payments

                )

                    ? report.payments

                    : [];



            const verifiedPayments = payments.filter(

        (payment) =>

            String(

                payment.verification_status ||

                "unverified"

            ).toLowerCase() === "verified"

    );



            const card =

                document.createElement(

                    "div"

                );



            card.className =

                "report-card";



            card.innerHTML = `


                <div class="report-card-header">


                    <div>


                        <div class="report-title">

                            Laporan #${escapeHtml(

                                reportId

                            )}

                        </div>


                        <div class="muted">

                            Case ID:

                            ${escapeHtml(

                                caseId

                            )}

                        </div>


                    </div>


                    <span class="risk-badge ${risk}">

                        ${risk.toUpperCase()}

                    </span>


                </div>



                <div class="report-site">


                    <strong>

                        🌐 Situs Terdeteksi

                    </strong>


                    <div>

                        ${escapeHtml(url)}

                    </div>


                </div>



                <div class="report-info-grid">


                    <div>


                        <span>

                            Platform

                        </span>


                        <strong>

                            ${escapeHtml(

                                platform

                            )}

                        </strong>


                    </div>



                    <div>


                        <span>

                            Status

                        </span>


                        <strong>

                            ${escapeHtml(

                                status

                            )}

                        </strong>


                    </div>



                    <div>


                        <span>

                            Indikator

                        </span>


                        <strong>

                            ${indicators.length}

                        </strong>


                    </div>



                    <div>


                        <span>

                            Payment Verified

                        </span>


                        <strong>

                            ${verifiedPayments.length}

                        </strong>


                    </div>


                </div>



                <div class="report-footer">


                    <span>

                        ${escapeHtml(

                            formatDate(

                                report.created_at ||

                                report.detected_at

                            )

                        )}

                    </span>



                    <div style="display:flex; gap:8px; flex-wrap:wrap;">

                        <button
                            type="button"
                            class="report-package-btn"
                            style="cursor:pointer;"
                        >
                            📦 Download Package
                        </button>

                        <button
                            type="button"
                            class="report-detail-btn"
                        >
                            Lihat Detail →
                        </button>

                    </div>


                </div>

            `;



            const packageButton =
                card.querySelector(
                    ".report-package-btn"
                );

            packageButton?.addEventListener(
                "click",
                (event) => {
                    event.stopPropagation();
                    downloadReportPackage(reportId);
                }
            );


            const button =

                card.querySelector(

                    ".report-detail-btn"

                );



            button?.addEventListener(

                "click",

                (event) => {


                    event.stopPropagation();


                    renderReportDetail(

                        report

                    );

                }

            );



            // Klik seluruh card juga membuka detail

            card.addEventListener(

                "click",

                () => {


                    renderReportDetail(

                        report

                    );

                }

            );



            list.appendChild(

                card

            );

        }

    );

}



// ============================================================

// REPORT DETAIL PAGE

// ============================================================


function renderReportDetail(

    report

) {


    if (!report) {

        return;

    }



    // ========================================================

    // PENTING:

    // Detail dibuat sebagai HALAMAN TERPISAH.

    // Tidak lagi append ke reportsPage.

    // Tidak lagi scrollIntoView().

    // ========================================================


    ensureReportDetailPage();



    const detail =

        $("reportDetailContent");



    if (!detail) {


        console.error(

            "GuardNet-AI: reportDetailContent tidak ditemukan."

        );


        return;

    }



    const risk =

        riskClass(

            report.risk_level

        );



    const site = getReportSite(report);


    const indicators = getReportIndicators(report);



    const payments =

        Array.isArray(

            report.payments

        )

            ? report.payments

            : [];



    const verifiedPayments = payments.filter(

        (payment) =>

            String(

                payment.verification_status ||

                "unverified"

            ).toLowerCase() === "verified"

    );


    const paymentCandidates = payments;



    const evidence =

        report.evidence ||

        {};



    const imageHash =

        evidence.image_hash ||

        report.image_hash ||

        "-";



    const ocrHash =

        evidence.ocr_hash ||

        report.ocr_hash ||

        "-";



    const integrity =

        evidence.integrity_status ||

        report.integrity_status ||

        "-";



    const evidenceId =

        evidence.evidence_id ||

        report.evidence_id ||

        "-";



    const detectedAt =

        evidence.detected_at ||

        report.detected_at ||

        report.created_at;



    detail.innerHTML = `


        <div class="report-detail-card">



            <!-- =================================================

                 HEADER

            ================================================= -->


            <div class="detail-header">


                <div>


                    <h3>

                        📋 Detail Pelaporan

                    </h3>


                    <p>

                        Informasi lengkap

                        hasil deteksi GuardNet-AI

                    </p>


                </div>



                <span class="risk-badge ${risk}">

                    ${risk.toUpperCase()}

                </span>


            </div>



            <!-- =================================================

                 INFORMASI SITUS

            ================================================= -->


            <section class="detail-section">


                <h4>

                    🌐 Informasi Situs

                </h4>



                <div class="detail-grid">



                    <div class="detail-item">


                        <span>

                            URL Content

                        </span>


                        <strong>

                            ${escapeHtml(

                                site.content_url

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Platform

                        </span>


                        <strong>

                            ${escapeHtml(

                                site.platform

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Content Type

                        </span>


                        <strong>

                            ${escapeHtml(

                                site.content_type

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Case ID

                        </span>


                        <strong>

                            ${escapeHtml(

                                report.case_id ||

                                "-"

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Report ID

                        </span>


                        <strong>

                            ${escapeHtml(

                                report.id ??

                                report.report_id ??

                                "-"

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Risk Level

                        </span>


                        <strong>

                            ${risk.toUpperCase()}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Status

                        </span>


                        <strong>

                            ${escapeHtml(

                                report.status ||

                                "draft"

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Waktu Deteksi

                        </span>


                        <strong>

                            ${escapeHtml(

                                formatDate(

                                    detectedAt

                                )

                            )}

                        </strong>


                    </div>



                </div>


            </section>



            <!-- =================================================

                 INDIKATOR

            ================================================= -->


            <section class="detail-section">


                <h4>

                    🚨 Indikator Terdeteksi

                </h4>



                <div class="indicator-detail-list">


                    ${

                        indicators.length


                            ? indicators

                                .map(

                                    (indicator) => `

                                        <span class="chip">

                                            ${escapeHtml(

                                                indicator

                                            )}

                                        </span>

                                    `

                                )

                                .join("")


                            : `

                                <div class="empty">

                                    Tidak ada indikator.

                                </div>

                            `

                    }


                </div>


            </section>



            <!-- =================================================

                 PAYMENT

            ================================================= -->


            <section class="detail-section">



                <div class="section-heading-row">


                    <div>


                        <h4>

                            💳 Payment Teridentifikasi

                        </h4>


                        <p class="muted">

                            Semua kandidat payment

                            ditampilkan. Hanya payment

                            berstatus verified yang

                            dianggap terkonfirmasi.

                        </p>


                    </div>



                    <span class="payment-count">


                        ${verifiedPayments.length}


                        Verified


                    </span>


                </div>



                ${

                    paymentCandidates.length


                        ? paymentCandidates

                            .map(

                                (payment) =>

                                    renderPaymentCard(

                                        payment

                                    )

                            )

                            .join("")


                        : `

                            <div class="payment-empty">


                                <strong>

                                    Belum ada payment

                                    yang terverifikasi.

                                </strong>


                                <p>

                                    Kandidat payment

                                    tidak otomatis dianggap

                                    valid sebelum proses

                                    validasi.

                                </p>



                                ${

                                    payments.length


                                        ? `

                                            <small>

                                                ${payments.length}

                                                kandidat payment

                                                ditemukan dan

                                                menunggu validasi.

                                            </small>

                                        `


                                        : ""

                                }


                            </div>

                        `

                }


            </section>



            <!-- =================================================

                 EVIDENCE

            ================================================= -->


            <section class="detail-section">


                <h4>

                    🧾 Evidence

                </h4>



                <div class="detail-grid">



                    <div class="detail-item">


                        <span>

                            Evidence ID

                        </span>


                        <strong>

                            ${escapeHtml(

                                evidenceId

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Integrity

                        </span>


                        <strong>

                            ${escapeHtml(

                                integrity

                            )}

                        </strong>


                    </div>



                    <div class="detail-item full">


                        <span>

                            Image SHA-256

                        </span>


                        <strong

                            class="hash-value"

                        >

                            ${escapeHtml(

                                imageHash

                            )}

                        </strong>


                    </div>



                    <div class="detail-item full">


                        <span>

                            OCR SHA-256

                        </span>


                        <strong

                            class="hash-value"

                        >

                            ${escapeHtml(

                                ocrHash

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Evidence Timestamp

                        </span>


                        <strong>

                            ${escapeHtml(

                                formatDate(

                                    detectedAt

                                )

                            )}

                        </strong>


                    </div>



                    <div class="detail-item">


                        <span>

                            Source URL

                        </span>


                        <strong>

                            ${escapeHtml(

                                evidence.source_url ||
                                site.content_url ||
                                "-"

                            )}

                        </strong>


                    </div>



                </div>


            </section>



            <!-- =================================================

                 BACK BUTTON

            ================================================= -->


            <div class="report-detail-actions" style="display:flex; gap:10px; flex-wrap:wrap;">

                <button
                    type="button"
                    class="back-button"
                    id="backToReportsButton"
                >
                    ← Kembali ke Pelaporan
                </button>

                <button
                    type="button"
                    class="report-package-btn"
                    id="downloadReportPackageButton"
                    style="cursor:pointer;"
                >
                    📦 Download Report Package
                </button>

            </div>



        </div>

    `;



    // ========================================================

    // EVENT TOMBOL KEMBALI

    // ========================================================


    const backButton =

        $("backToReportsButton");



    if (backButton) {

        backButton.addEventListener(
            "click",
            backToReports
        );

    }

    const packageButton =
    $("downloadReportPackageButton");

if (packageButton) {

    packageButton.addEventListener(
        "click",
        () => {

            downloadReportPackage(
                report.report_id ||
                report.id
            );

        }
    );

}


    // ========================================================

    // INI YANG MEMINDAHKAN HALAMAN

    // BUKAN SCROLL

    // ========================================================


    openPage(

        "reportDetailPage"

    );

}



// ============================================================

// PAYMENT CARD

// ============================================================


function renderPaymentCard(

    payment

) {


    const paymentType = payment.payment_type || "unknown";

    const provider = payment.provider || "-";

    const accountName = payment.account_name || payment.merchant_name || "-";

    const accountNumber = payment.account_number || "";

    const phoneNumber = payment.phone_number || "";

    const qrDetected = Boolean(payment.qr_detected);

    const verification = String(payment.verification_status || "unverified").toLowerCase();

    const paymentHash = payment.image_hash || "-";

    const merchantName = payment.merchant_name || "-";

    const merchantCity = payment.merchant_city || "-";

    const nmid = payment.nmid || "-";

    const acquirer = payment.acquirer || provider || "-";

    const acquirerIdentifier = payment.acquirer_identifier || "-";

    const crcValid = payment.crc_valid;

    const technicalStatus = payment.qris_technical_status || "-";

    const dataQualityStatus = payment.qris_data_quality_status || "-";

    const authenticityStatus = payment.authenticity_status || "unverified";

    const authenticityReason = payment.authenticity_reason || "";

    const qualityReasons = Array.isArray(payment.qris_quality_reasons)

        ? payment.qris_quality_reasons

        : [];

    const destinationBank = payment.destination_bank || "Tidak tersedia dari payload";

    const paymentScore = payment.payment_score || "-";

    const routingNote = payment.routing_note || "";


    const statusLabel = verification === "verified"

        ? "✓ VERIFIED"

        : verification === "rejected"

            ? "✕ REJECTED"

            : "○ UNVERIFIED";


    const statusClass = verification === "verified"

        ? "verified-badge"

        : verification === "rejected"

            ? "rejected-badge"

            : "pending-badge";


    const paymentId = payment.payment_id || "";


    return `

        <div class="payment-card">

            <div class="payment-card-header">

                <div>

                    <strong>💳 ${escapeHtml(paymentType)}</strong>

                    <div class="muted">${escapeHtml(provider)}</div>

                </div>

                <span class="${statusClass}">${statusLabel}</span>

            </div>


            <div class="payment-grid">

                <div><span>Provider</span><strong>${escapeHtml(provider)}</strong></div>

                <div><span>Acquirer</span><strong>${escapeHtml(acquirer)}</strong></div>

                <div><span>Acquirer Identifier</span><strong>${escapeHtml(acquirerIdentifier)}</strong></div>

                <div><span>Nama Merchant / Pemilik</span><strong>${escapeHtml(accountName)}</strong></div>

                <div><span>Merchant Name</span><strong>${escapeHtml(merchantName)}</strong></div>

                <div><span>Merchant City</span><strong>${escapeHtml(merchantCity)}</strong></div>

                <div><span>NMID</span><strong>${escapeHtml(nmid)}</strong></div>

                <div><span>QRIS</span><strong>${qrDetected ? "Terdeteksi" : "Tidak terdeteksi"}</strong></div>

                <div><span>CRC</span><strong>${crcValid === true ? "Valid" : crcValid === false ? "Invalid" : "Tidak tersedia"}</strong></div>

                <div><span>Status Teknis QRIS</span><strong>${escapeHtml(technicalStatus)}</strong></div>

                <div><span>Data Quality</span><strong>${escapeHtml(dataQualityStatus)}</strong></div>

                <div><span>Authenticity</span><strong>${escapeHtml(authenticityStatus)}</strong></div>

                <div><span>Destination Bank</span><strong>${escapeHtml(destinationBank)}</strong></div>

                <div><span>Verification</span><strong>${escapeHtml(verification)}</strong></div>

                <div><span>Payment Score</span><strong>${escapeHtml(paymentScore)}</strong></div>

                ${accountNumber ? `<div><span>Nomor Rekening</span><strong>${escapeHtml(accountNumber)}</strong></div>` : ""}

                ${phoneNumber ? `<div><span>Nomor Telepon</span><strong>${escapeHtml(phoneNumber)}</strong></div>` : ""}

            </div>


            ${routingNote ? `<div class="muted">${escapeHtml(routingNote)}</div>` : ""}


            ${authenticityReason ? `

                <div class="muted"><strong>Alasan Authenticity:</strong> ${escapeHtml(authenticityReason)}</div>

            ` : ""}


            ${qualityReasons.length ? `

                <div class="muted">

                    <strong>Catatan Data Quality:</strong>

                    <ul style="margin:6px 0 0 18px;">

                        ${qualityReasons.map((reason) => `<li>${escapeHtml(String(reason))}</li>`).join("")}

                    </ul>

                </div>

            ` : ""}


            <div class="payment-hash">

                <span>Payment Image Hash</span>

                <code>${escapeHtml(paymentHash)}</code>

            </div>


            ${paymentId ? `

                <div class="muted">Payment ID: ${escapeHtml(paymentId)}</div>

                ${verification !== "verified" && verification !== "rejected" ? `

                    <div class="payment-actions" style="display:flex;gap:8px;margin-top:12px;">

                        <button type="button" class="btn btn-primary" onclick="validatePayment('${escapeHtml(paymentId)}', true)">✓ Validasi Payment</button>

                        <button type="button" class="btn btn-secondary" onclick="validatePayment('${escapeHtml(paymentId)}', false)">✕ Tolak</button>

                    </div>

                ` : ""}

            ` : ""}

        </div>

    `;

}



// ============================================================

// BACK TO REPORT LIST

// ============================================================


function backToReports() {


    openPage(

        "reportsPage"

    );

}



// ============================================================

// PAYMENT VALIDATION

// ============================================================


async function validatePayment(

    paymentId,

    verified = true

) {


    if (!paymentId) {


        throw new Error(

            "Payment ID tidak ditemukan."

        );

    }



    try {


        const response =

            await fetch(

                `${API_BASE_URL}/payment/${encodeURIComponent(

                    paymentId

                )}/verify?verification_status=${encodeURIComponent(

                    verified ? "verified" : "rejected"

                )}`,

                {

                    method: "PATCH",


                    headers: {

                        "Content-Type":

                            "application/json"

                    },


                    body: JSON.stringify({

                        verified

                    })

                }

            );



        const data =

            await readJson(

                response

            );



        if (!response.ok) {


            throw new Error(

                data.detail ||

                data.message ||

                `Validasi payment gagal. HTTP ${response.status}`

            );

        }



        await loadReports();



        return data;



    } catch (error) {


        console.error(

            "Payment Validation Error:",

            error

        );



        showError(

            error.message

        );



        throw error;

    }

}



// ============================================================

// REPORT SEARCH

// ============================================================


function filterReports(

    keyword

) {


    const query =

        String(

            keyword || ""

        )

        .trim()

        .toLowerCase();



    if (!query) {


        renderReports(

            reportsCache

        );


        return;

    }



    const filtered =

        reportsCache.filter(

            (report) => {


                const indicators = getReportIndicators(report).join(" ");



                const payments =

                    Array.isArray(

                        report.payments

                    )

                        ? report.payments

                            .map(

                                (payment) =>

                                    [

                                        payment.payment_type,

                                        payment.provider,

                                        payment.account_name,

                                        payment.account_number,

                                        payment.phone_number

                                    ].join(" ")

                            )

                            .join(" ")

                        : "";



                const searchable =

                    [

                        report.id,

                        report.report_id,

                        report.case_id,

                        getReportSite(report).platform,

                        getReportSite(report).content_url,

                        report.status,

                        report.risk_level,

                        indicators,

                        payments

                    ]

                    .join(" ")

                    .toLowerCase();



                return searchable.includes(

                    query

                );

            }

        );

    renderReports(

        filtered

    );

}

function setupReportSearch() {

    const input =

        $("reportSearch");



    if (!input) {

        return;

    }



    input.addEventListener(

        "input",

        () => {


            filterReports(

                input.value

            );

        }

    );

}



// ============================================================

// CASE SEARCH

// ============================================================


function filterCases(

    keyword

) {


    const query =

        String(

            keyword || ""

        )

        .trim()

        .toLowerCase();



    if (!query) {


        renderCases(

            casesCache

        );


        return;

    }

    const filtered =

        casesCache.filter(

            (item) => {


                const indicators =

                    Array.isArray(

                        item.detected_indicators

                    )

                        ? item.detected_indicators

                            .join(" ")

                        : "";



                const searchable =

                    [

                        item.case_id,

                        item.id,

                        item.platform,

                        item.content_url,

                        item.risk_level,

                        item.status,

                        indicators

                    ]

                    .join(" ")

                    .toLowerCase();



                return searchable.includes(

                    query

                );

            }

        );


    renderCases(

        filtered

    );

}

function setupCaseSearch() {


    const input =

        $("caseSearch");



    if (!input) {

        return;

    }

    input.addEventListener(

        "input",

        () => {


            filterCases(

                input.value

            );

        }

    );

}

// ============================================================

// REFRESH FUNCTIONS

// ============================================================

async function refreshDashboard() {


    await loadDashboard();

}

async function refreshCases() {


    await loadCases();

}

async function refreshReports() {


    await loadReports();

}

async function refreshAllData() {


    hideError();

    await Promise.allSettled([

        loadDashboard(),

        loadCases(),

        loadReports()

    ]);

}

// ============================================================

// BACKEND CONNECTION

// ============================================================


async function checkBackendConnection() {

    try {

        const response =

            await fetch(

                `${API_BASE_URL}/dashboard`

            );

        if (!response.ok) {

            throw new Error(

                `Backend HTTP ${response.status}`

            );

        }

        console.log(

            "GuardNet-AI: Backend connected."

        );

        return true;

    } catch (error) {


        console.warn(

            "GuardNet-AI: Backend belum terhubung.",

            error

        );

        return false;

    }

}


function updateConnectionStatus(

    connected

) {

    const element =

        $("connectionStatus");


    if (!element) {

        return;

    }

    if (connected) {

        element.textContent =

            "● Backend Connected";

        element.classList.remove(

            "offline"

        );

        element.classList.add(

            "online"

        );



    } else {

        element.textContent =

            "● Backend Offline";

        element.classList.remove(

            "online"

        );

        element.classList.add(

            "offline"

        );

    }

}

// ============================================================
// REPORT AUTO REFRESH
// ============================================================

function startReportAutoRefresh() {

    if (reportRefreshTimer) {


        clearInterval(

            reportRefreshTimer

        );

    }

    reportRefreshTimer =

        setInterval(

            () => {

                const page =

                    document.querySelector(

                        ".page.active"

                    );



                if (

                    page?.id ===

                    "reportsPage"

                ) {


                    loadReports();

                }


            },

            30000

        );

}



function stopReportAutoRefresh() {

    if (reportRefreshTimer) {


        clearInterval(

            reportRefreshTimer

        );

        reportRefreshTimer =

            null;

    }

}

// ============================================================

// SAFE EVENT BINDING

// ============================================================


function bindClick(

    id,

    handler

) {


    const element =

        $(id);



    if (!element) {

        return;

    }

    element.addEventListener(

        "click",

        handler

    );

}

// ============================================================
// BUTTON COMPATIBILITY
// ============================================================

function setupButtonCompatibility() {

    bindClick(

        "dashboardBtn",

        () => {

            openPage(

                "dashboardPage"

            );

        }

    );

    bindClick(

        "analysisBtn",

        () => {

            openPage(

                "analysisPage"

            );

        }

    );

    bindClick(

        "resultBtn",

        () => {


            openPage(

                "resultPage"

            );

        }

    );

    bindClick(

        "casesBtn",

        () => {

            openPage(

                "casesPage"

            );

            loadCases();

        }

    );

    bindClick(

        "reportsBtn",

        () => {


            openPage(

                "reportsPage"

            );

            loadReports();

        }

    );

}

// ============================================================
// DOM READY
// ============================================================


document.addEventListener(

    "DOMContentLoaded",

    async () => {

        // ----------------------------------------------
        // Pastikan halaman detail tersedia
        // ----------------------------------------------

        ensureReportDetailPage();

        // ----------------------------------------------
        // Setup image
        // ---------------------------------------------

        setupImagePreview();

        // ----------------------------------------------
        // Navigation
        // ----------------------------------------------


        document

            .querySelectorAll(

                ".nav-btn, .nav-item"

            )

            .forEach(

                (button) => {


                    button.addEventListener(

                        "click",

                        (event) => {


                            const target =

                                button.dataset.page ||

                                button.getAttribute(

                                    "data-target"

                                );



                            if (!target) {

                                return;

                            }



                            event.preventDefault();



                            openPage(

                                target

                            );

                        }

                    );

                }

            );



        // ----------------------------------------------

        // Sidebar

        // ----------------------------------------------


        bindClick(

            "menuToggle",

            toggleSidebar

        );



        bindClick(

            "hamburger",

            toggleSidebar

        );



        bindClick(

            "sidebarOverlay",

            closeSidebar

        );



        bindClick(

            "overlay",

            closeSidebar

        );



        // ----------------------------------------------

        // Analysis

        // ----------------------------------------------


        bindClick(

            "analyzeButton",

            analyzeFullContent

        );



        // ----------------------------------------------

        // Refresh

        // ----------------------------------------------


        bindClick(

            "refreshDashboard",

            refreshDashboard

        );



        bindClick(

            "refreshCases",

            refreshCases

        );



        bindClick(

            "refreshReports",

            refreshReports

        );



        // ----------------------------------------------

        // Search

        // ----------------------------------------------


        setupReportSearch();


        setupCaseSearch();



        // ----------------------------------------------

        // Compatibility buttons

        // ----------------------------------------------


        setupButtonCompatibility();



        // ----------------------------------------------

        // Auto refresh reports

        // ----------------------------------------------


        startReportAutoRefresh();



        // ----------------------------------------------

        // Backend

        // ----------------------------------------------


        const connected =

            await checkBackendConnection();



        updateConnectionStatus(

            connected

        );



        // ----------------------------------------------

        // Initial dashboard

        // ----------------------------------------------


        loadDashboard();


    }

);



// ============================================================

// GLOBAL EXPORTS

// ============================================================


window.openPage =

    openPage;



window.showPage =

    showPage;



window.toggleSidebar =

    toggleSidebar;



window.closeSidebar =

    closeSidebar;



window.analyzeFullContent =

    analyzeFullContent;



window.analyzeContent =

    analyzeContent;



window.loadDashboard =

    loadDashboard;



window.loadCases =

    loadCases;



window.loadReports =

    loadReports;



window.refreshDashboard =

    refreshDashboard;



window.refreshCases =

    refreshCases;



window.refreshReports =

    refreshReports;



window.refreshAllData =

    refreshAllData;



window.validatePayment =

    validatePayment;



window.filterReports =

    filterReports;



window.filterCases =

    filterCases;



window.downloadReportPackage =

    downloadReportPackage;


window.backToReports =

    backToReports;



window.checkBackendConnection =

    checkBackendConnection;



window.updateConnectionStatus =

    updateConnectionStatus;

