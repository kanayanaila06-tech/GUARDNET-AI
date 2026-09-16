// =====================================================
// GUARDNET-AI CONTENT SCRIPT
// REALTIME + AUTONOMOUS + FAST + STABLE
// =====================================================

console.log("🔥 GUARDNET-AI CONTENT SCRIPT AKTIF");


// =====================================================
// KONFIGURASI
// =====================================================

// Jeda debounce scanning.
// Jika ada banyak perubahan DOM sekaligus,
// sistem menunggu sebentar sebelum melakukan scan.
const API_SCAN_DELAY = 400;

// Scan pertama setelah halaman siap.
const INITIAL_SCAN_DELAY = 1500;

// Minimum ukuran gambar untuk OCR.
const MIN_IMAGE_WIDTH = 300;
const MIN_IMAGE_HEIGHT = 300;

// Maksimal jumlah teks yang disimpan dalam memory.
const MAX_PROCESSED_TEXTS = 1000;

// Maksimal jumlah URL gambar yang disimpan dalam memory.
const MAX_PROCESSED_IMAGES = 500;

// Jeda minimum antar scan otomatis.
const MIN_SCAN_INTERVAL = 300;


// =====================================================
// PENYIMPANAN DATA
// =====================================================

const processedTexts = new Set();

const processedImages = new Set();

const processingImages = new Set();


// =====================================================
// STATE SCANNING
// =====================================================

let scanTimeout = null;

let scanRunning = false;

let lastScanTime = 0;

let observerStarted = false;


// =====================================================
// POPUP
// =====================================================

let guardNetPopup = null;

let popupCloseTimeout = null;


// =====================================================
// STATE HALAMAN
// =====================================================

let currentPageUrl =
    window.location.href;


// =====================================================
// NORMALISASI TEKS
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
// BATASI UKURAN SET
// =====================================================

function limitSetSize(set, maxSize) {

    if (!set) {
        return;
    }

    while (set.size > maxSize) {

        const firstValue =
            set.values().next().value;

        if (firstValue === undefined) {
            break;
        }

        set.delete(firstValue);
    }

}


// =====================================================
// CEK ELEMEN GUARDNET
// =====================================================

function isGuardNetElement(node) {

    if (!node) {
        return false;
    }

    if (
        node.nodeType !==
        Node.ELEMENT_NODE
    ) {
        return false;
    }

    if (
        node.id ===
        "guardnet-result"
    ) {
        return true;
    }

    if (
        typeof node.closest ===
        "function"
    ) {

        const guardNetParent =
            node.closest(
                "#guardnet-result"
            );

        if (guardNetParent) {
            return true;
        }
    }

    return false;

}


// =====================================================
// VALIDASI GAMBAR OCR
// =====================================================

function isValidImageForOCR(img) {

    if (!img) {
        return false;
    }


    // Pastikan elemen benar-benar IMG.
    if (
        img.tagName !==
        "IMG"
    ) {
        return false;
    }


    // Gambar belum selesai load.
    if (!img.complete) {
        return false;
    }


    const width =
        img.naturalWidth || 0;

    const height =
        img.naturalHeight || 0;


    if (
        width === 0 ||
        height === 0
    ) {

        return false;

    }


    // Gambar terlalu kecil.
    if (
        width < MIN_IMAGE_WIDTH ||
        height < MIN_IMAGE_HEIGHT
    ) {

        return false;

    }


    const imageUrl =
        img.currentSrc ||
        img.src ||
        img.getAttribute("src") ||
        "";


    if (!imageUrl) {
        return false;
    }


    // Placeholder.
    if (
        imageUrl === "data:," ||
        imageUrl.startsWith(
            "data:image/gif"
        )
    ) {

        return false;

    }


    // Jangan OCR profile picture/avatar.
    const alt =
        String(
            img.alt || ""
        ).toLowerCase();


    if (
        alt.includes(
            "profile picture"
        ) ||
        alt.includes(
            "profile photo"
        ) ||
        alt.includes(
            "profil"
        ) ||
        alt.includes(
            "avatar"
        )
    ) {

        return false;

    }


    // Jangan OCR gambar yang jelas merupakan icon.
    const role =
        String(
            img.getAttribute("role") || ""
        ).toLowerCase();


    if (
        role === "presentation"
    ) {

        return false;

    }


    return true;

}


// =====================================================
// AMBIL URL GAMBAR
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
// CEK URL HALAMAN
// =====================================================

function updateCurrentPageUrl() {

    const newUrl =
        window.location.href;


    if (
        newUrl !==
        currentPageUrl
    ) {

        currentPageUrl =
            newUrl;


        console.log(
            "GuardNet-AI: URL halaman berubah:",
            currentPageUrl
        );

    }

}


// =====================================================
// ANALISIS TEKS
// =====================================================

function analyzeText(text) {

    const normalizedText =
        normalizeText(text);


    if (!normalizedText) {
        return;
    }


    // Jangan analisis teks yang sama berkali-kali.
    if (
        processedTexts.has(
            normalizedText
        )
    ) {

        return;

    }


    processedTexts.add(
        normalizedText
    );


    limitSetSize(
        processedTexts,
        MAX_PROCESSED_TEXTS
    );


    updateCurrentPageUrl();


    console.log(
        "GuardNet-AI: Teks ditemukan:",
        normalizedText
    );


    try {

        const messagePromise =
            chrome.runtime.sendMessage({

                action:
                    "analyzeContent",

                text:
                    normalizedText,

                url:
                    currentPageUrl

            });


        if (
            messagePromise &&
            typeof messagePromise.catch ===
                "function"
        ) {

            messagePromise.catch(
                (error) => {

                    console.warn(
                        "GuardNet-AI: Gagal mengirim analisis teks:",
                        error?.message ||
                        error
                    );

                }
            );

        }

    } catch (error) {

        console.warn(
            "GuardNet-AI: Error saat mengirim teks:",
            error
        );

    }

}


// =====================================================
// DETEKSI TEKS INSTAGRAM
// =====================================================

function detectText() {

    const articles =
        document.querySelectorAll(
            "article"
        );


    if (!articles.length) {

        console.log(
            "GuardNet-AI: Belum menemukan article."
        );

        return;

    }


    let detectedArticles = 0;


    articles.forEach(
        (article) => {

            if (!article) {
                return;
            }


            // Jangan membaca popup GuardNet.
            if (
                isGuardNetElement(
                    article
                )
            ) {

                return;

            }


            const text =
                article.innerText ||
                "";


            if (!text.trim()) {
                return;
            }


            detectedArticles++;


            analyzeText(
                text
            );

        }
    );


    console.log(
        "GuardNet-AI: Article dianalisis:",
        detectedArticles
    );

}


// =====================================================
// ANALISIS GAMBAR
// =====================================================

function analyzeImage(img) {

    if (
        !isValidImageForOCR(
            img
        )
    ) {

        return;

    }


    const imageUrl =
        getImageUrl(img);


    if (!imageUrl) {
        return;
    }


    // Sudah pernah diproses.
    if (
        processedImages.has(
            imageUrl
        )
    ) {

        return;

    }


    // Sedang diproses.
    if (
        processingImages.has(
            imageUrl
        )
    ) {

        return;

    }


    processingImages.add(
        imageUrl
    );


    updateCurrentPageUrl();


    console.log(
        "GuardNet-AI: Gambar valid untuk OCR:",
        {
            width:
                img.naturalWidth,

            height:
                img.naturalHeight,

            url:
                imageUrl
        }
    );


    try {

        const messagePromise =
            chrome.runtime.sendMessage({

                action:
                    "ocrImage",

                imageUrl:
                    imageUrl,

                url:
                    currentPageUrl

            });


        if (
            messagePromise &&
            typeof messagePromise.catch ===
                "function"
        ) {

            messagePromise.catch(
                (error) => {

                    processingImages.delete(
                        imageUrl
                    );

                    console.warn(
                        "GuardNet-AI: Gagal mengirim OCR:",
                        error?.message ||
                        error
                    );

                }
            );

        }

    } catch (error) {

        processingImages.delete(
            imageUrl
        );


        console.warn(
            "GuardNet-AI: Error saat mengirim OCR:",
            error
        );

    }

}


// =====================================================
// DETEKSI GAMBAR INSTAGRAM
// =====================================================

function detectImagesForOCR() {

    const articles =
        document.querySelectorAll(
            "article"
        );


    if (!articles.length) {
        return;
    }


    let totalImages = 0;

    let validImages = 0;


    articles.forEach(
        (article) => {

            if (
                isGuardNetElement(
                    article
                )
            ) {

                return;

            }


            const images =
                article.querySelectorAll(
                    "img"
                );


            images.forEach(
                (img) => {

                    if (!img) {
                        return;
                    }


                    totalImages++;


                    // Gambar belum selesai load.
                    if (!img.complete) {

                        img.addEventListener(
                            "load",
                            () => {

                                analyzeImage(
                                    img
                                );

                            },
                            {
                                once: true
                            }
                        );

                        return;

                    }


                    // Gambar sudah siap.
                    if (
                        !isValidImageForOCR(
                            img
                        )
                    ) {

                        return;

                    }


                    validImages++;


                    analyzeImage(
                        img
                    );

                }
            );

        }
    );


    console.log(
        "GuardNet-AI: Gambar ditemukan:",
        totalImages,
        "| Valid OCR:",
        validImages
    );

}


// =====================================================
// SCAN SEMUA KONTEN
// =====================================================

function scanContent() {

    if (scanRunning) {

        console.log(
            "GuardNet-AI: Scan masih berjalan, dilewati."
        );

        return;

    }


    const now =
        Date.now();


    // Mencegah scan terlalu rapat.
    if (
        now - lastScanTime <
        MIN_SCAN_INTERVAL
    ) {

        return;

    }


    scanRunning = true;

    lastScanTime =
        now;


    try {

        updateCurrentPageUrl();


        console.log(
            "🔎 GuardNet-AI: Melakukan REALTIME scanning..."
        );


        // =============================================
        // TEXT DETECTION
        // =============================================

        detectText();


        // =============================================
        // IMAGE / OCR DETECTION
        // =============================================

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
// DEBOUNCE SCAN
// =====================================================

function scheduleScan() {

    if (scanTimeout) {

        clearTimeout(
            scanTimeout
        );

    }


    scanTimeout =
        setTimeout(
            () => {

                scanTimeout = null;

                scanContent();

            },
            API_SCAN_DELAY
        );

}


// =====================================================
// CEK MUTATION RELEVAN
// =====================================================

function mutationContainsRelevantContent(
    node
) {

    if (!node) {
        return false;
    }


    if (
        node.nodeType !==
        Node.ELEMENT_NODE
    ) {

        return false;

    }


    // Jangan trigger dari popup GuardNet.
    if (
        isGuardNetElement(
            node
        )
    ) {

        return false;

    }


    // Jika node langsung berupa article.
    if (
        node.matches &&
        node.matches(
            "article"
        )
    ) {

        return true;

    }


    // Jika node mengandung article.
    if (
        node.querySelector &&
        node.querySelector(
            "article"
        )
    ) {

        return true;

    }


    // Jika node mengandung gambar.
    if (
        node.matches &&
        node.matches(
            "img"
        )
    ) {

        return true;

    }


    if (
        node.querySelector &&
        node.querySelector(
            "img"
        )
    ) {

        return true;

    }


    return false;

}


// =====================================================
// MUTATION OBSERVER
// =====================================================
//
// MutationObserver menjadi trigger utama realtime.
//
// Artinya:
// - Tidak perlu scroll.
// - Tidak perlu klik.
// - Ketika Instagram memasukkan konten baru ke DOM,
//   GuardNet-AI otomatis menjadwalkan scanning.
// =====================================================

const observer =
    new MutationObserver(
        (mutations) => {

            let shouldScan = false;


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
                        mutationContainsRelevantContent(
                            node
                        )
                    ) {

                        shouldScan =
                            true;

                        break;

                    }

                }


                if (shouldScan) {
                    break;
                }

            }


            if (shouldScan) {

                console.log(
                    "GuardNet-AI: Konten baru terdeteksi oleh MutationObserver."
                );


                scheduleScan();

            }

        }
    );


// =====================================================
// AKTIFKAN OBSERVER
// =====================================================

function startObserver() {

    if (
        observerStarted
    ) {

        return;

    }


    if (!document.body) {

        console.warn(
            "GuardNet-AI: document.body belum tersedia."
        );

        return;

    }


    observer.observe(
        document.body,
        {
            childList: true,
            subtree: true
        }
    );


    observerStarted =
        true;


    console.log(
        "🟢 GuardNet-AI: MutationObserver REALTIME aktif."
    );

}


// =====================================================
// TUNGGU DOCUMENT BODY
// =====================================================

if (document.body) {

    startObserver();

} else {

    document.addEventListener(
        "DOMContentLoaded",
        startObserver,
        {
            once: true
        }
    );

}


// =====================================================
// SCAN PERTAMA
// =====================================================

setTimeout(
    () => {

        console.log(
            "🚀 GuardNet-AI: Initial realtime scan dimulai."
        );


        scanContent();

    },
    INITIAL_SCAN_DELAY
);


// =====================================================
// TUTUP POPUP SAAT SCROLL
// =====================================================
//
// PENTING:
// Scroll sekarang HANYA untuk menutup popup.
//
// Scroll TIDAK memanggil scheduleScan().
//
// Realtime detection dilakukan oleh:
// 1. Initial Scan
// 2. MutationObserver
// 3. Image load event
// =====================================================

window.addEventListener(
    "scroll",
    () => {

        closeGuardNetPopup();

    },
    {
        passive: true
    }
);


// =====================================================
// TUTUP POPUP
// =====================================================

function closeGuardNetPopup() {

    if (popupCloseTimeout) {

        clearTimeout(
            popupCloseTimeout
        );

        popupCloseTimeout = null;

    }


    if (
        guardNetPopup &&
        guardNetPopup.isConnected
    ) {

        guardNetPopup.style.animation =
            "guardnetFadeOut 0.18s ease forwards";


        popupCloseTimeout =
            setTimeout(
                () => {

                    if (
                        guardNetPopup &&
                        guardNetPopup.isConnected
                    ) {

                        guardNetPopup.remove();

                    }

                    guardNetPopup = null;

                    popupCloseTimeout =
                        null;

                },
                180
            );

    }


    const oldPopup =
        document.getElementById(
            "guardnet-result"
        );


    if (
        oldPopup &&
        oldPopup !== guardNetPopup
    ) {

        oldPopup.remove();

    }

}


// =====================================================
// TERIMA HASIL DARI BACKGROUND
// =====================================================

chrome.runtime.onMessage.addListener(
    (message) => {

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

            if (!message.success) {

                console.error(
                    "GuardNet-AI Text Error:",
                    message.error
                );

                return;

            }


            console.log(
                "✅ HASIL ANALISIS TEKS GUARDNET-AI:",
                message.result
            );


            // Popup hanya sebagai notifikasi.
            // Data utama nantinya tetap disimpan backend.
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

            if (!message.success) {

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


            console.log(
                "✅ HASIL OCR + ANALISIS GUARDNET-AI:",
                message.result
            );


            // Tandai gambar selesai.
            if (
                message.imageUrl
            ) {

                processedImages.add(
                    message.imageUrl
                );


                processingImages.delete(
                    message.imageUrl
                );


                limitSetSize(
                    processedImages,
                    MAX_PROCESSED_IMAGES
                );

            }


            showGuardNetResult(
                message.result
            );


            return;

        }

    }
);


// =====================================================
// TAMPILKAN HASIL GUARDNET-AI
// =====================================================

function showGuardNetResult(
    result
) {

    if (!result) {
        return;
    }


    // =================================================
    // HAPUS POPUP LAMA
    // =================================================

    if (
        guardNetPopup &&
        guardNetPopup.isConnected
    ) {

        guardNetPopup.remove();

    }


    const oldResult =
        document.getElementById(
            "guardnet-result"
        );


    if (oldResult) {
        oldResult.remove();
    }


    // =================================================
    // RISK LEVEL
    // =================================================

    const riskLevel =
        String(
            result.risk_level ||
            "low"
        ).toLowerCase();


    let riskColor =
        "#35d07f";

    let riskGlow =
        "rgba(53, 208, 127, 0.35)";

    let icon =
        "🟢";


    if (
        riskLevel ===
        "medium"
    ) {

        riskColor =
            "#ffb020";

        riskGlow =
            "rgba(255, 176, 32, 0.35)";

        icon =
            "🟡";

    }


    if (
        riskLevel ===
        "high"
    ) {

        riskColor =
            "#ff4d5e";

        riskGlow =
            "rgba(255, 77, 94, 0.35)";

        icon =
            "🔴";

    }


    // =================================================
    // INDIKATOR
    // =================================================

    const indicators =
        Array.isArray(
            result.detected_indicators
        )
            ? result.detected_indicators
            : [];


    // =================================================
    // CONTAINER
    // =================================================

    const box =
        document.createElement(
            "div"
        );


    box.id =
        "guardnet-result";


    // =================================================
    // STYLE ANIMATION
    // =================================================

    const style =
        document.createElement(
            "style"
        );


    style.textContent = `

        @keyframes guardnetSlideIn {

            0% {
                opacity: 0;
                transform:
                    translateY(-18px)
                    scale(0.96);
            }

            100% {
                opacity: 1;
                transform:
                    translateY(0)
                    scale(1);
            }

        }


        @keyframes guardnetFadeOut {

            0% {
                opacity: 1;
                transform:
                    translateY(0);
            }

            100% {
                opacity: 0;
                transform:
                    translateY(-10px);
            }

        }


        #guardnet-result {

            position: fixed !important;

            top: 22px !important;

            right: 22px !important;

            width: 390px !important;

            max-width:
                calc(100vw - 30px) !important;

            box-sizing:
                border-box !important;

            z-index:
                2147483647 !important;

            font-family:
                Arial,
                Helvetica,
                sans-serif !important;

            animation:
                guardnetSlideIn
                0.3s
                cubic-bezier(.2,.8,.2,1)
                forwards;

            pointer-events:
                auto !important;
        }


        #guardnet-result * {

            box-sizing:
                border-box !important;

        }


        #guardnet-result
        .guardnet-card {

            position:
                relative;

            overflow:
                hidden;

            padding:
                20px;

            border-radius:
                20px;

            color:
                #ffffff;

            background:
                linear-gradient(
                    145deg,
                    #151a2e 0%,
                    #101426 55%,
                    #0c1020 100%
                );

            border:
                1px solid
                rgba(255,255,255,0.13);

            box-shadow:
                0 20px 50px
                rgba(0,0,0,0.45),

                0 0 30px
                ${riskGlow};

            backdrop-filter:
                blur(14px);

            -webkit-backdrop-filter:
                blur(14px);
        }


        #guardnet-result
        .guardnet-accent {

            position:
                absolute;

            top:
                0;

            left:
                0;

            width:
                100%;

            height:
                4px;

            background:
                linear-gradient(
                    90deg,
                    ${riskColor},
                    #4da6ff
                );
        }


        #guardnet-result
        .guardnet-header {

            display:
                flex;

            align-items:
                center;

            gap:
                12px;

            margin-bottom:
                18px;
        }


        #guardnet-result
        .guardnet-logo {

            width:
                42px;

            height:
                42px;

            display:
                flex;

            align-items:
                center;

            justify-content:
                center;

            border-radius:
                13px;

            font-size:
                21px;

            background:
                linear-gradient(
                    135deg,
                    #2f80ed,
                    #56ccf2
                );

            box-shadow:
                0 8px 20px
                rgba(47,128,237,0.35);
        }


        #guardnet-result
        .guardnet-title {

            flex:
                1;
        }


        #guardnet-result
        .guardnet-title-main {

            font-size:
                18px;

            font-weight:
                800;

            letter-spacing:
                -0.3px;

            color:
                #ffffff;
        }


        #guardnet-result
        .guardnet-title-sub {

            margin-top:
                2px;

            font-size:
                11px;

            color:
                rgba(255,255,255,0.55);
        }


        #guardnet-result
        .guardnet-risk {

            display:
                flex;

            align-items:
                center;

            justify-content:
                space-between;

            padding:
                13px 14px;

            margin-bottom:
                13px;

            border-radius:
                13px;

            background:
                rgba(255,255,255,0.06);

            border:
                1px solid
                rgba(255,255,255,0.08);
        }


        #guardnet-result
        .guardnet-risk-left {

            display:
                flex;

            align-items:
                center;

            gap:
                9px;

            font-size:
                14px;

            font-weight:
                600;
        }


        #guardnet-result
        .guardnet-risk-dot {

            width:
                10px;

            height:
                10px;

            border-radius:
                50%;

            background:
                ${riskColor};

            box-shadow:
                0 0 12px
                ${riskColor};
        }


        #guardnet-result
        .guardnet-risk-value {

            color:
                ${riskColor};

            font-weight:
                800;

            letter-spacing:
                0.5px;
        }


        #guardnet-result
        .guardnet-score {

            font-size:
                13px;

            color:
                rgba(255,255,255,0.65);
        }


        #guardnet-result
        .guardnet-section {

            margin-top:
                13px;
        }


        #guardnet-result
        .guardnet-label {

            margin-bottom:
                7px;

            font-size:
                11px;

            font-weight:
                700;

            text-transform:
                uppercase;

            letter-spacing:
                0.8px;

            color:
                rgba(255,255,255,0.45);
        }


        #guardnet-result
        .guardnet-description {

            padding:
                12px 13px;

            border-radius:
                12px;

            font-size:
                13px;

            line-height:
                1.55;

            color:
                rgba(255,255,255,0.88);

            background:
                rgba(255,255,255,0.055);

            border-left:
                3px solid
                ${riskColor};
        }


        #guardnet-result
        .guardnet-indicators {

            display:
                flex;

            flex-wrap:
                wrap;

            gap:
                6px;
        }


        #guardnet-result
        .guardnet-indicator {

            padding:
                5px 9px;

            border-radius:
                999px;

            font-size:
                11px;

            color:
                rgba(255,255,255,0.85);

            background:
                rgba(255,255,255,0.07);

            border:
                1px solid
                rgba(255,255,255,0.09);
        }


        #guardnet-result
        .guardnet-no-indicator {

            font-size:
                12px;

            color:
                rgba(255,255,255,0.55);
        }


        #guardnet-result
        .guardnet-close {

            width:
                100%;

            margin-top:
                18px;

            padding:
                11px 15px;

            border:
                none;

            border-radius:
                12px;

            cursor:
                pointer;

            color:
                #ffffff;

            font-size:
                13px;

            font-weight:
                800;

            background:
                linear-gradient(
                    135deg,
                    #2678e8,
                    #35a1ff
                );

            box-shadow:
                0 8px 18px
                rgba(38,120,232,0.25);

            transition:
                transform 0.15s ease,
                filter 0.15s ease;
        }


        #guardnet-result
        .guardnet-close:hover {

            filter:
                brightness(1.08);

            transform:
                translateY(-1px);
        }


        #guardnet-result
        .guardnet-close:active {

            transform:
                translateY(1px);
        }


        @media (max-width: 600px) {

            #guardnet-result {

                top:
                    12px !important;

                right:
                    12px !important;

                width:
                    calc(100vw - 24px) !important;
            }

        }

    `;


    // =================================================
    // MASUKKAN STYLE
    // =================================================

    document.documentElement.appendChild(
        style
    );


    // =================================================
    // ACCENT
    // =================================================

    const accent =
        document.createElement(
            "div"
        );

    accent.className =
        "guardnet-accent";


    // =================================================
    // HEADER
    // =================================================

    const header =
        document.createElement(
            "div"
        );

    header.className =
        "guardnet-header";


    const logo =
        document.createElement(
            "div"
        );

    logo.className =
        "guardnet-logo";

    logo.textContent =
        "🛡️";


    const title =
        document.createElement(
            "div"
        );

    title.className =
        "guardnet-title";


    const titleMain =
        document.createElement(
            "div"
        );

    titleMain.className =
        "guardnet-title-main";

    titleMain.textContent =
        "GuardNet-AI";


    const titleSub =
        document.createElement(
            "div"
        );

    titleSub.className =
        "guardnet-title-sub";

    titleSub.textContent =
        "Analisis Keamanan Digital";


    title.appendChild(
        titleMain
    );

    title.appendChild(
        titleSub
    );


    header.appendChild(
        logo
    );

    header.appendChild(
        title
    );


    // =================================================
    // RISK
    // =================================================

    const riskBox =
        document.createElement(
            "div"
        );

    riskBox.className =
        "guardnet-risk";


    const riskLeft =
        document.createElement(
            "div"
        );

    riskLeft.className =
        "guardnet-risk-left";


    const riskDot =
        document.createElement(
            "span"
        );

    riskDot.className =
        "guardnet-risk-dot";


    const riskText =
        document.createElement(
            "span"
        );

    riskText.textContent =
        `${icon} Risiko`;


    const riskValue =
        document.createElement(
            "span"
        );

    riskValue.className =
        "guardnet-risk-value";

    riskValue.textContent =
        riskLevel.toUpperCase();


    riskLeft.appendChild(
        riskDot
    );

    riskLeft.appendChild(
        riskText
    );

    riskLeft.appendChild(
        riskValue
    );


    riskBox.appendChild(
        riskLeft
    );


    // =================================================
    // SCORE
    // =================================================

    if (
        result.score !== undefined &&
        result.score !== null
    ) {

        const score =
            document.createElement(
                "span"
            );

        score.className =
            "guardnet-score";

        score.textContent =
            `Skor ${result.score}`;


        riskBox.appendChild(
            score
        );

    }


    // =================================================
    // DESCRIPTION
    // =================================================

    const descriptionSection =
        document.createElement(
            "div"
        );

    descriptionSection.className =
        "guardnet-section";


    const descriptionLabel =
        document.createElement(
            "div"
        );

    descriptionLabel.className =
        "guardnet-label";

    descriptionLabel.textContent =
        "Kesimpulan";


    const description =
        document.createElement(
            "div"
        );

    description.className =
        "guardnet-description";

    description.textContent =
        result.description ||
        "Tidak ada keterangan.";


    descriptionSection.appendChild(
        descriptionLabel
    );

    descriptionSection.appendChild(
        description
    );


    // =================================================
    // INDICATOR
    // =================================================

    const indicatorSection =
        document.createElement(
            "div"
        );

    indicatorSection.className =
        "guardnet-section";


    const indicatorLabel =
        document.createElement(
            "div"
        );

    indicatorLabel.className =
        "guardnet-label";

    indicatorLabel.textContent =
        "Indikator Terdeteksi";


    const indicatorContainer =
        document.createElement(
            "div"
        );

    indicatorContainer.className =
        "guardnet-indicators";


    if (
        indicators.length > 0
    ) {

        indicators.forEach(
            (item) => {

                const tag =
                    document.createElement(
                        "span"
                    );

                tag.className =
                    "guardnet-indicator";

                tag.textContent =
                    String(item);

                indicatorContainer.appendChild(
                    tag
                );

            }
        );

    } else {

        const noIndicator =
            document.createElement(
                "span"
            );

        noIndicator.className =
            "guardnet-no-indicator";

        noIndicator.textContent =
            "Tidak ditemukan indikasi kuat.";

        indicatorContainer.appendChild(
            noIndicator
        );

    }


    indicatorSection.appendChild(
        indicatorLabel
    );

    indicatorSection.appendChild(
        indicatorContainer
    );


    // =================================================
    // CLOSE BUTTON
    // =================================================

    const closeButton =
        document.createElement(
            "button"
        );

    closeButton.className =
        "guardnet-close";

    closeButton.textContent =
        "Tutup";


    closeButton.addEventListener(
        "click",
        () => {

            closeGuardNetPopup();

        }
    );


    // =================================================
    // CARD
    // =================================================

    const card =
        document.createElement(
            "div"
        );

    card.className =
        "guardnet-card";


    card.appendChild(
        accent
    );

    card.appendChild(
        header
    );

    card.appendChild(
        riskBox
    );

    card.appendChild(
        descriptionSection
    );

    card.appendChild(
        indicatorSection
    );

    card.appendChild(
        closeButton
    );


    // =================================================
    // MASUKKAN CARD
    // =================================================

    box.appendChild(
        card
    );


    if (document.body) {

        document.body.appendChild(
            box
        );

        guardNetPopup =
            box;

    }


    console.log(
        "GuardNet-AI: Popup hasil ditampilkan.",
        result
    );

}


// =====================================================
// FINAL STATUS
// =====================================================

console.log(
    "🛡️ GuardNet-AI Content Script REALTIME FINAL siap."
);