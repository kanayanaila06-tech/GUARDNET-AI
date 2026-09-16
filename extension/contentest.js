// =====================================================
// GUARDNET-AI CONTENT SCRIPT
// FINAL - FAST + STABLE + LOW/MEDIUM/HIGH
// CAPTION + COMMENT + OCR
// POPUP AUTO HIDE ON SCROLL
// =====================================================

console.log("======================================");
console.log("🛡️ GuardNet-AI Content Script aktif");
console.log("======================================");


// =====================================================
// CONFIGURATION
// =====================================================

const INITIAL_SCAN_DELAY = 1200;
const MUTATION_SCAN_DELAY = 500;
const SCROLL_SCAN_DELAY = 700;

const MIN_IMAGE_WIDTH = 180;
const MIN_IMAGE_HEIGHT = 180;

const POPUP_DURATION = 6500;

const MAX_OCR_IMAGES_PER_SCAN = 3;


// =====================================================
// STATE
// =====================================================

const processedTexts = new Set();
const processedImages = new Set();
const processingImages = new Set();

let scanTimeout = null;
let scrollScanTimeout = null;

let popupTimer = null;

let currentBestRisk = "none";

let scanRunning = false;

let observerStarted = false;


// =====================================================
// RISK PRIORITY
// =====================================================

function getRiskPriority(risk) {

    const level = String(risk || "low").toLowerCase();

    if (level === "high") {
        return 3;
    }

    if (level === "medium") {
        return 2;
    }

    if (level === "low") {
        return 1;
    }

    return 0;
}


// =====================================================
// NORMALIZE TEXT
// =====================================================

function normalizeText(text) {

    if (!text) {
        return "";
    }

    return String(text)
        .replace(/\s+/g, " ")
        .trim();

}


// =====================================================
// CHECK GUARDNET ELEMENT
// =====================================================

function isGuardNetElement(element) {

    if (!element) {
        return false;
    }

    if (element.nodeType !== Node.ELEMENT_NODE) {
        return false;
    }

    if (
        element.id === "guardnet-result" ||
        element.closest?.("#guardnet-result")
    ) {
        return true;
    }

    return false;
}


// =====================================================
// TEXT CONTAINER CHECK
// =====================================================

function isUsefulTextContainer(element) {

    if (!element) {
        return false;
    }

    if (isGuardNetElement(element)) {
        return false;
    }

    const tagName =
        String(element.tagName || "").toLowerCase();

    if (
        tagName === "script" ||
        tagName === "style" ||
        tagName === "noscript"
    ) {
        return false;
    }

    return true;
}


// =====================================================
// ANALYZE TEXT
// =====================================================

function analyzeText(text) {

    const normalizedText =
        normalizeText(text);

    if (!normalizedText) {
        return;
    }

    if (normalizedText.length < 3) {
        return;
    }

    if (
        normalizedText ===
        "GuardNet-AI"
    ) {
        return;
    }

    // Hindari teks yang sama dikirim berulang kali
    if (processedTexts.has(normalizedText)) {
        return;
    }

    processedTexts.add(normalizedText);

    console.log(
        "GuardNet-AI: Teks ditemukan:",
        normalizedText
    );


    // =================================================
    // KIRIM KE BACKGROUND
    // =================================================

    chrome.runtime.sendMessage(
        {
            action: "analyzeContent",
            text: normalizedText,
            url: window.location.href
        }
    )
    .then(() => {

        console.log(
            "GuardNet-AI: Teks berhasil dikirim ke background."
        );

    })
    .catch((error) => {

        console.error(
            "GuardNet-AI Text Error:",
            error?.message || error
        );

        // Kalau gagal kirim, izinkan scan ulang
        processedTexts.delete(normalizedText);

    });

}


// =====================================================
// GET TEXT AREAS
// =====================================================

function getTextAreas() {

    const areas = [];

    // Instagram post
    const articles =
        document.querySelectorAll("article");

    articles.forEach((article) => {

        if (
            !isUsefulTextContainer(article)
        ) {
            return;
        }

        areas.push(article);

    });


    // Instagram comment dialog
    const dialogs =
        document.querySelectorAll(
            '[role="dialog"]'
        );

    dialogs.forEach((dialog) => {

        if (
            !isUsefulTextContainer(dialog)
        ) {
            return;
        }

        areas.push(dialog);

    });


    // Jika article/dialog tidak ditemukan
    if (areas.length === 0) {

        const main =
            document.querySelector("main");

        if (
            main &&
            isUsefulTextContainer(main)
        ) {
            areas.push(main);
        }

    }

    return areas;
}


// =====================================================
// DETECT TEXT
// =====================================================

function detectText() {

    const areas =
        getTextAreas();

    console.log(
        "GuardNet-AI: Total area teks:",
        areas.length
    );


    areas.forEach((area) => {

        if (!area) {
            return;
        }

        if (
            isGuardNetElement(area)
        ) {
            return;
        }

        const text =
            area.innerText || "";

        if (!text.trim()) {
            return;
        }

        analyzeText(text);

    });

}


// =====================================================
// GET IMAGE URL
// =====================================================

function getImageUrl(img) {

    if (!img) {
        return null;
    }

    return (
        img.currentSrc ||
        img.src ||
        img.getAttribute("src") ||
        null
    );

}


// =====================================================
// VALID IMAGE FOR OCR
// =====================================================

function isValidImageForOCR(img) {

    if (!img) {
        return false;
    }

    if (
        img.closest?.("#guardnet-result")
    ) {
        return false;
    }

    if (!img.complete) {
        return false;
    }

    const width =
        img.naturalWidth || 0;

    const height =
        img.naturalHeight || 0;

    if (
        width < MIN_IMAGE_WIDTH ||
        height < MIN_IMAGE_HEIGHT
    ) {
        return false;
    }

    const imageUrl =
        getImageUrl(img);

    if (!imageUrl) {
        return false;
    }

    if (
        imageUrl === "data:," ||
        imageUrl.startsWith("data:image/gif")
    ) {
        return false;
    }


    // =================================================
    // JANGAN OCR FOTO PROFIL / AVATAR
    // =================================================

    const alt =
        String(img.alt || "")
            .toLowerCase();

    if (
        alt.includes("profile picture") ||
        alt.includes("profile photo") ||
        alt.includes("profil") ||
        alt.includes("avatar")
    ) {
        return false;
    }


    // =================================================
    // JANGAN OCR GAMBAR YANG TERLALU KECIL
    // =================================================

    const rect =
        img.getBoundingClientRect();

    if (
        rect.width < 100 ||
        rect.height < 100
    ) {
        return false;
    }

    return true;
}


// =====================================================
// CHECK IMAGE NEAR VIEWPORT
// =====================================================

function isImageNearViewport(img) {

    if (!img) {
        return false;
    }

    const rect =
        img.getBoundingClientRect();

    const viewportHeight =
        window.innerHeight ||
        document.documentElement.clientHeight;

    const margin = 500;

    if (
        rect.bottom < -margin
    ) {
        return false;
    }

    if (
        rect.top >
        viewportHeight + margin
    ) {
        return false;
    }

    return true;
}


// =====================================================
// ANALYZE IMAGE
// =====================================================

function analyzeImage(img) {

    if (
        !isValidImageForOCR(img)
    ) {
        return;
    }

    if (
        !isImageNearViewport(img)
    ) {
        return;
    }

    const imageUrl =
        getImageUrl(img);

    if (!imageUrl) {
        return;
    }


    // Sudah pernah diproses
    if (
        processedImages.has(imageUrl)
    ) {
        return;
    }


    // Sedang diproses
    if (
        processingImages.has(imageUrl)
    ) {
        return;
    }


    // Batasi jumlah OCR aktif
    if (
        processingImages.size >=
        MAX_OCR_IMAGES_PER_SCAN
    ) {
        return;
    }


    processingImages.add(imageUrl);


    console.log(
        "GuardNet-AI: Gambar valid untuk OCR:",
        {
            width: img.naturalWidth,
            height: img.naturalHeight
        }
    );


    // =================================================
    // KIRIM KE BACKGROUND
    // =================================================

    chrome.runtime.sendMessage(
        {
            action: "ocrImage",
            imageUrl: imageUrl,
            url: window.location.href
        }
    )
    .then(() => {

        console.log(
            "GuardNet-AI: Permintaan OCR berhasil dikirim."
        );

    })
    .catch((error) => {

        console.error(
            "GuardNet-AI OCR Error:",
            error?.message || error
        );

        processingImages.delete(
            imageUrl
        );

    });

}


// =====================================================
// DETECT IMAGES
// =====================================================

function detectImagesForOCR() {

    const images = [];

    // =================================================
    // 1. IMAGE DALAM ARTICLE
    // =================================================

    const articles =
        document.querySelectorAll(
            "article"
        );

    articles.forEach((article) => {

        article
            .querySelectorAll("img")
            .forEach((img) => {

                if (
                    !images.includes(img)
                ) {
                    images.push(img);
                }

            });

    });


    // =================================================
    // 2. IMAGE DALAM COMMENT DIALOG
    // =================================================

    const dialogs =
        document.querySelectorAll(
            '[role="dialog"]'
        );

    dialogs.forEach((dialog) => {

        dialog
            .querySelectorAll("img")
            .forEach((img) => {

                if (
                    !images.includes(img)
                ) {
                    images.push(img);
                }

            });

    });


    // =================================================
    // 3. FALLBACK
    // =================================================

    if (
        images.length === 0
    ) {

        document
            .querySelectorAll("main img")
            .forEach((img) => {

                if (
                    !images.includes(img)
                ) {
                    images.push(img);
                }

            });

    }


    console.log(
        "GuardNet-AI: Total gambar ditemukan:",
        images.length
    );


    let validCount = 0;


    // =================================================
    // PROSES GAMBAR
    // =================================================

    for (
        const img of images
    ) {

        if (
            !isValidImageForOCR(img)
        ) {
            continue;
        }

        if (
            !isImageNearViewport(img)
        ) {
            continue;
        }

        validCount++;

        if (
            processingImages.size >=
            MAX_OCR_IMAGES_PER_SCAN
        ) {
            break;
        }

        analyzeImage(img);

    }


    console.log(
        "GuardNet-AI: Gambar valid untuk OCR:",
        validCount
    );

}


// =====================================================
// SCAN CONTENT
// =====================================================

function scanContent() {

    if (scanRunning) {
        return;
    }

    scanRunning = true;


    try {

        console.log(
            "GuardNet-AI: Melakukan scanning..."
        );


        // =================================================
        // TEXT
        // =================================================

        detectText();


        // =================================================
        // IMAGE OCR
        // =================================================

        detectImagesForOCR();


    } catch (error) {

        console.error(
            "GuardNet-AI Scan Error:",
            error
        );

    } finally {

        scanRunning = false;

    }

}


// =====================================================
// SCHEDULE SCAN
// =====================================================

function scheduleScan(
    delay = MUTATION_SCAN_DELAY
) {

    if (scanTimeout) {
        clearTimeout(
            scanTimeout
        );
    }

    scanTimeout =
        setTimeout(
            () => {

                scanContent();

            },
            delay
        );

}


// =====================================================
// SCROLL SCAN
// =====================================================

function scheduleScrollScan() {

    if (
        scrollScanTimeout
    ) {
        clearTimeout(
            scrollScanTimeout
        );
    }

    scrollScanTimeout =
        setTimeout(
            () => {

                scanContent();

            },
            SCROLL_SCAN_DELAY
        );

}


// =====================================================
// HIDE POPUP
// =====================================================

function hideGuardNetResult() {

    const popup =
        document.getElementById(
            "guardnet-result"
        );

    if (!popup) {
        return;
    }

    popup.classList.add(
        "guardnet-hide"
    );


    setTimeout(
        () => {

            if (
                popup &&
                popup.parentNode
            ) {
                popup.remove();
            }

        },
        180
    );


    clearTimeout(
        popupTimer
    );

    currentBestRisk =
        "none";

}


// =====================================================
// RISK ICON
// =====================================================

function getRiskIcon(
    riskLevel
) {

    if (
        riskLevel === "high"
    ) {
        return "🔴";
    }

    if (
        riskLevel === "medium"
    ) {
        return "🟡";
    }

    return "🟢";

}


// =====================================================
// RISK TITLE
// =====================================================

function getRiskTitle(
    riskLevel
) {

    if (
        riskLevel === "high"
    ) {
        return "RISIKO TINGGI";
    }

    if (
        riskLevel === "medium"
    ) {
        return "RISIKO SEDANG";
    }

    return "RISIKO RENDAH";

}


// =====================================================
// RISK COLOR
// =====================================================

function getRiskColor(
    riskLevel
) {

    if (
        riskLevel === "high"
    ) {
        return "#dc2626";
    }

    if (
        riskLevel === "medium"
    ) {
        return "#d97706";
    }

    return "#16a34a";

}


// =====================================================
// CREATE POPUP STYLE
// =====================================================

function createPopupStyles() {

    if (
        document.getElementById(
            "guardnet-popup-style"
        )
    ) {
        return;
    }


    const style =
        document.createElement(
            "style"
        );

    style.id =
        "guardnet-popup-style";


    style.textContent = `
        #guardnet-result {
            position: fixed;
            top: 24px;
            right: 24px;
            width: 370px;
            max-width: calc(100vw - 32px);

            background:
                linear-gradient(
                    145deg,
                    #ffffff 0%,
                    #f8fafc 100%
                );

            color: #111827;

            border-radius: 18px;

            border: 1px solid
                rgba(0,0,0,0.08);

            box-shadow:
                0 20px 50px
                rgba(0,0,0,0.22);

            overflow: hidden;

            z-index: 2147483647;

            font-family:
                Arial,
                Helvetica,
                sans-serif;

            animation:
                guardnet-popup-in
                0.25s
                ease-out;

            transition:
                opacity
                0.18s
                ease,
                transform
                0.18s
                ease;
        }

        #guardnet-result.guardnet-hide {
            opacity: 0;
            transform:
                translateY(-12px)
                scale(0.97);
        }

        #guardnet-result
        .guardnet-header {
            padding: 16px 18px;

            color: white;

            display: flex;

            align-items: center;

            justify-content:
                space-between;

            background:
                linear-gradient(
                    135deg,
                    #111827,
                    #374151
                );
        }

        #guardnet-result
        .guardnet-brand {
            display: flex;

            align-items: center;

            gap: 10px;

            font-size: 16px;

            font-weight: 700;
        }

        #guardnet-result
        .guardnet-shield {
            width: 34px;
            height: 34px;

            border-radius: 10px;

            display: flex;

            align-items: center;

            justify-content: center;

            background:
                rgba(255,255,255,0.15);

            font-size: 19px;
        }

        #guardnet-result
        .guardnet-risk-badge {
            padding:
                6px 10px;

            border-radius: 999px;

            font-size: 11px;

            font-weight: 800;

            letter-spacing:
                0.4px;

            color: white;
        }

        #guardnet-result
        .guardnet-body {
            padding: 18px;
        }

        #guardnet-result
        .guardnet-risk-row {
            display: flex;

            align-items: center;

            gap: 12px;

            margin-bottom: 15px;
        }

        #guardnet-result
        .guardnet-risk-icon {
            width: 48px;
            height: 48px;

            border-radius: 14px;

            display: flex;

            align-items: center;

            justify-content: center;

            font-size: 24px;

            background: #f3f4f6;
        }

        #guardnet-result
        .guardnet-risk-text {
            flex: 1;
        }

        #guardnet-result
        .guardnet-risk-label {
            font-size: 11px;

            color: #6b7280;

            margin-bottom: 3px;

            text-transform:
                uppercase;

            letter-spacing:
                0.5px;
        }

        #guardnet-result
        .guardnet-risk-value {
            font-size: 19px;

            font-weight: 800;
        }

        #guardnet-result
        .guardnet-score {
            font-size: 12px;

            color: #6b7280;

            margin-top: 2px;
        }

        #guardnet-result
        .guardnet-section {
            margin-top: 13px;

            padding-top: 13px;

            border-top:
                1px solid #e5e7eb;
        }

        #guardnet-result
        .guardnet-section-title {
            font-size: 11px;

            font-weight: 800;

            color: #6b7280;

            text-transform:
                uppercase;

            letter-spacing:
                0.5px;

            margin-bottom: 6px;
        }

        #guardnet-result
        .guardnet-indicators {
            font-size: 13px;

            line-height: 1.5;

            color: #374151;

            word-break: break-word;
        }

        #guardnet-result
        .guardnet-description {
            font-size: 13px;

            line-height: 1.55;

            color: #374151;
        }

        #guardnet-result
        .guardnet-footer {
            padding:
                10px 18px 14px;

            font-size: 10px;

            color: #9ca3af;

            text-align: center;
        }

        @keyframes guardnet-popup-in {
            from {
                opacity: 0;
                transform:
                    translateY(-14px)
                    scale(0.96);
            }

            to {
                opacity: 1;
                transform:
                    translateY(0)
                    scale(1);
            }
        }

        @media (max-width: 600px) {
            #guardnet-result {
                top: 12px;
                right: 12px;
                width:
                    calc(100vw - 24px);
            }
        }
    `;


    document.head.appendChild(
        style
    );

}


// =====================================================
// SHOW RESULT POPUP
// =====================================================

function showGuardNetResult(
    result
) {

    if (!result) {
        return;
    }


    const riskLevel =
        String(
            result.risk_level ||
            "low"
        ).toLowerCase();


    const priority =
        getRiskPriority(
            riskLevel
        );


    const currentPriority =
        getRiskPriority(
            currentBestRisk
        );


    // =================================================
    // JANGAN BIARKAN LOW MENIMPA HIGH
    // =================================================

    if (
        priority < currentPriority
    ) {
        console.log(
            "GuardNet-AI: Hasil diabaikan karena risiko lebih rendah."
        );

        return;
    }


    // =================================================
    // SIMPAN RISIKO TERBAIK
    // =================================================

    currentBestRisk =
        riskLevel;


    createPopupStyles();


    // Hapus popup lama
    const oldPopup =
        document.getElementById(
            "guardnet-result"
        );

    if (oldPopup) {
        oldPopup.remove();
    }


    clearTimeout(
        popupTimer
    );


    // =================================================
    // DATA
    // =================================================

    const icon =
        getRiskIcon(
            riskLevel
        );

    const title =
        getRiskTitle(
            riskLevel
        );

    const color =
        getRiskColor(
            riskLevel
        );


    const score =
        result.score !== undefined
            ? result.score
            : 0;


    const indicators =
        Array.isArray(
            result.detected_indicators
        )
            ? result.detected_indicators
                .join(", ")
            : (
                result.detected_indicators ||
                "Tidak ada indikator."
            );


    const description =
        result.description ||
        "Tidak ada keterangan.";


    // =================================================
    // CREATE POPUP
    // =================================================

    const box =
        document.createElement(
            "div"
        );

    box.id =
        "guardnet-result";


    // =================================================
    // HEADER
    // =================================================

    const header =
        document.createElement(
            "div"
        );

    header.className =
        "guardnet-header";


    const brand =
        document.createElement(
            "div"
        );

    brand.className =
        "guardnet-brand";


    const shield =
        document.createElement(
            "div"
        );

    shield.className =
        "guardnet-shield";

    shield.textContent =
        "🛡️";


    const brandText =
        document.createElement(
            "span"
        );

    brandText.textContent =
        "GuardNet-AI";


    brand.appendChild(
        shield
    );

    brand.appendChild(
        brandText
    );


    const badge =
        document.createElement(
            "div"
        );

    badge.className =
        "guardnet-risk-badge";

    badge.textContent =
        title;

    badge.style.background =
        color;


    header.appendChild(
        brand
    );

    header.appendChild(
        badge
    );


    // =================================================
    // BODY
    // =================================================

    const body =
        document.createElement(
            "div"
        );

    body.className =
        "guardnet-body";


    // =================================================
    // RISK ROW
    // =================================================

    const riskRow =
        document.createElement(
            "div"
        );

    riskRow.className =
        "guardnet-risk-row";


    const riskIcon =
        document.createElement(
            "div"
        );

    riskIcon.className =
        "guardnet-risk-icon";

    riskIcon.textContent =
        icon;


    const riskText =
        document.createElement(
            "div"
        );

    riskText.className =
        "guardnet-risk-text";


    const riskLabel =
        document.createElement(
            "div"
        );

    riskLabel.className =
        "guardnet-risk-label";

    riskLabel.textContent =
        "Status Deteksi";


    const riskValue =
        document.createElement(
            "div"
        );

    riskValue.className =
        "guardnet-risk-value";

    riskValue.textContent =
        title;

    riskValue.style.color =
        color;


    const scoreElement =
        document.createElement(
            "div"
        );

    scoreElement.className =
        "guardnet-score";

    scoreElement.textContent =
        `Skor analisis: ${score}`;


    riskText.appendChild(
        riskLabel
    );

    riskText.appendChild(
        riskValue
    );

    riskText.appendChild(
        scoreElement
    );


    riskRow.appendChild(
        riskIcon
    );

    riskRow.appendChild(
        riskText
    );


    body.appendChild(
        riskRow
    );


    // =================================================
    // INDICATORS
    // =================================================

    const indicatorSection =
        document.createElement(
            "div"
        );

    indicatorSection.className =
        "guardnet-section";


    const indicatorTitle =
        document.createElement(
            "div"
        );

    indicatorTitle.className =
        "guardnet-section-title";

    indicatorTitle.textContent =
        "Indikator Terdeteksi";


    const indicatorText =
        document.createElement(
            "div"
        );

    indicatorText.className =
        "guardnet-indicators";

    indicatorText.textContent =
        indicators;


    indicatorSection.appendChild(
        indicatorTitle
    );

    indicatorSection.appendChild(
        indicatorText
    );


    body.appendChild(
        indicatorSection
    );


    // =================================================
    // DESCRIPTION
    // =================================================

    const descriptionSection =
        document.createElement(
            "div"
        );

    descriptionSection.className =
        "guardnet-section";


    const descriptionTitle =
        document.createElement(
            "div"
        );

    descriptionTitle.className =
        "guardnet-section-title";

    descriptionTitle.textContent =
        "Keterangan";


    const descriptionText =
        document.createElement(
            "div"
        );

    descriptionText.className =
        "guardnet-description";

    descriptionText.textContent =
        description;


    descriptionSection.appendChild(
        descriptionTitle
    );

    descriptionSection.appendChild(
        descriptionText
    );


    body.appendChild(
        descriptionSection
    );


    // =================================================
    // FOOTER
    // =================================================

    const footer =
        document.createElement(
            "div"
        );

    footer.className =
        "guardnet-footer";

    footer.textContent =
        "GuardNet-AI • Deteksi keamanan digital";


    // =================================================
    // ASSEMBLE
    // =================================================

    box.appendChild(
        header
    );

    box.appendChild(
        body
    );

    box.appendChild(
        footer
    );


    document.body.appendChild(
        box
    );


    console.log(
        "🛡️ GuardNet-AI: Popup ditampilkan:",
        result
    );


    // =================================================
    // AUTO HIDE
    // =================================================

    popupTimer =
        setTimeout(
            () => {

                hideGuardNetResult();

            },
            POPUP_DURATION
        );

}


// =====================================================
// RECEIVE RESULT FROM BACKGROUND
// =====================================================

chrome.runtime.onMessage.addListener(
    (
        message,
        sender,
        sendResponse
    ) => {

        if (!message) {
            return;
        }


        // =================================================
        // HASIL ANALISIS TEKS
        // =================================================

        if (
            message.action ===
            "analysisResult"
        ) {

            if (
                !message.success
            ) {

                console.error(
                    "GuardNet-AI Text Error:",
                    message.error
                );

                return;
            }


            console.log(
                "HASIL ANALISIS GUARDNET-AI:",
                message.result
            );


            showGuardNetResult(
                message.result
            );

            return;
        }


        // =================================================
        // HASIL OCR
        // =================================================

        if (
            message.action ===
            "ocrResult"
        ) {

            if (
                !message.success
            ) {

                console.error(
                    "GuardNet-AI OCR Error:",
                    message.error
                );

                if (
                    message.imageUrl
                ) {
                    processingImages.delete(
                        message.imageUrl
                    );
                }

                return;
            }


            if (
                message.imageUrl
            ) {

                processingImages.delete(
                    message.imageUrl
                );

                processedImages.add(
                    message.imageUrl
                );

            }


            console.log(
                "HASIL OCR + ANALISIS GUARDNET-AI:",
                message.result
            );


            showGuardNetResult(
                message.result
            );

            return;
        }

    }
);


// =====================================================
// AUTO HIDE ON SCROLL
// =====================================================

window.addEventListener(
    "scroll",
    () => {

        // Popup langsung hilang
        hideGuardNetResult();


        // Jangan langsung scan berkali-kali
        scheduleScrollScan();

    },
    {
        passive: true
    }
);


// =====================================================
// MUTATION OBSERVER
// =====================================================

function startObserver() {

    if (
        observerStarted
    ) {
        return;
    }

    if (!document.body) {
        return;
    }


    observerStarted = true;


    const observer =
        new MutationObserver(
            (mutations) => {

                let shouldScan =
                    false;


                for (
                    const mutation
                    of mutations
                ) {

                    if (
                        mutation.type !==
                        "childList"
                    ) {
                        continue;
                    }


                    if (
                        mutation.addedNodes.length ===
                        0
                    ) {
                        continue;
                    }


                    for (
                        const node
                        of mutation.addedNodes
                    ) {

                        if (
                            node.nodeType !==
                            Node.ELEMENT_NODE
                        ) {
                            continue;
                        }


                        if (
                            isGuardNetElement(
                                node
                            )
                        ) {
                            continue;
                        }


                        const element =
                            node;


                        const tag =
                            String(
                                element.tagName ||
                                ""
                            ).toLowerCase();


                        // Perubahan yang kemungkinan berisi konten Instagram
                        if (
                            tag === "article" ||
                            tag === "img" ||
                            tag === "div" ||
                            tag === "section" ||
                            element.querySelector?.(
                                "article, img, [role='dialog']"
                            )
                        ) {

                            shouldScan = true;

                            break;

                        }

                    }


                    if (shouldScan) {
                        break;
                    }

                }


                if (shouldScan) {

                    scheduleScan(
                        MUTATION_SCAN_DELAY
                    );

                }

            }
        );


    observer.observe(
        document.body,
        {
            childList: true,
            subtree: true
        }
    );


    console.log(
        "GuardNet-AI: MutationObserver aktif."
    );

}


// =====================================================
// INITIAL START
// =====================================================

function initializeGuardNet() {

    createPopupStyles();

    startObserver();


    setTimeout(
        () => {

            scanContent();

        },
        INITIAL_SCAN_DELAY
    );


    console.log(
        "🛡️ GuardNet-AI siap mendeteksi."
    );

}


// =====================================================
// START WHEN DOM READY
// =====================================================

if (
    document.readyState ===
    "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeGuardNet,
        {
            once: true
        }
    );

} else {

    initializeGuardNet();

}


// =====================================================
// FINAL STATUS
// =====================================================

console.log(
    "======================================"
);

console.log(
    "🛡️ GuardNet-AI Content Script FINAL"
);

console.log(
    "🟢 LOW | 🟡 MEDIUM | 🔴 HIGH"
);

console.log(
    "💬 Caption + Comment + OCR"
);

console.log(
    "======================================"
);