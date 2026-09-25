// =====================================================

// GUARDNET-AI CONTENT SCRIPT

// FINAL STABLE MULTIMODAL VERSION

//

// FEATURES:

// - Instagram caption/comment text detection

// - Image detection

// - Video frame / poster detection

// - OCR + Visual AI via background.js

// - Per-content result lock

// - LOW / MEDIUM / HIGH

// - FULL result is authoritative and may correct FAST

// - Popup stays until content changes / scroll / close

// - Instagram SPA support

// - MutationObserver

// - Duplicate protection

// =====================================================

console.log("======================================");

console.log("🛡️ GUARDNET-AI CONTENT SCRIPT AKTIF");

console.log("======================================");

// =====================================================

// CONFIGURATION

// =====================================================

const INITIAL_SCAN_DELAY = 100;

const MUTATION_SCAN_DELAY = 150;

const SCROLL_SCAN_DELAY = 150;

const PAGE_CHECK_INTERVAL = 500;

const MIN_IMAGE_WIDTH = 180;

const MIN_IMAGE_HEIGHT = 180;

const VIEWPORT_MARGIN = 500;

const MAX_MEDIA_PER_SCAN = 1;

const MAX_TEXT_LENGTH = 12000;

const MAX_CONTEXT_LENGTH = 8000;

const VIDEO_FRAME_WIDTH = 1000;

// Popup TIDAK auto hide

const POPUP_DURATION = 0;

// =====================================================

// STATE

// =====================================================

const processedTexts =

    new Set();

const processedImages =

    new Set();

const processingImages =

    new Set();

const processedVideos =

    new Set();

const receivedResults =

    new Set();

const pendingImages =

    new Map();

// Per-content result lock

const contentLocks =

    new Map();

// imageUrl -> contentKey

const mediaContentMap =

    new Map();

// Current visible content

let currentContentKey =

    null;

let currentBestRisk =

    "NONE";

let currentBestScore =

    0;

// -----------------------------------------------------

// ANALYSIS GENERATION / STALE RESULT PROTECTION

// -----------------------------------------------------

// Setiap perpindahan content membuat generasi baru.

// Response dari content lama tidak boleh ditampilkan.

let analysisGeneration =

    0;

let activeContentGeneration =

    null;

// Loading state agar pengguna langsung mendapat feedback saat AI bekerja.

let loadingContentKey = null;

let loadingGeneration = null;

// Timers

let scanTimeout =

    null;

let scrollScanTimeout =

    null;

let popupTimer =

    null;

// Runtime state

let scanRunning =

    false;

let observerStarted =

    false;

let messageListenerStarted =

    false;

let lastPageUrl =

    window.location.href;

// =====================================================

// RISK PRIORITY

// =====================================================

function getRiskPriority(risk) {

    const level =

        String(

            risk || ""

        )

            .trim()

            .toUpperCase();

    if (level === "HIGH") {

        return 3;

    }

    if (level === "MEDIUM") {

        return 2;

    }

    if (level === "LOW") {

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

        .replace(/\u200B/g, " ")

        .replace(/\u00A0/g, " ")

        .replace(/\s+/g, " ")

        .trim();

}

// =====================================================

// LIMIT TEXT

// =====================================================

function limitText(text) {

    const normalized =

        normalizeText(text);

    if (!normalized) {

        return "";

    }

    return normalized.substring(

        0,

        MAX_TEXT_LENGTH

    );

}

// =====================================================

// STABLE HASH

// =====================================================

function makeStableKey(value) {

    const text =

        String(

            value || ""

        );

    let hash =

        2166136261;

    for (

        let i = 0;

        i < text.length;

        i++

    ) {

        hash ^=

            text.charCodeAt(i);

        hash +=

            (hash << 1) +

            (hash << 4) +

            (hash << 7) +

            (hash << 8) +

            (hash << 24);

    }

    return (

        hash >>> 0

    ).toString(16);

}

// =====================================================

// CHECK GUARDNET ELEMENT

// =====================================================

function isGuardNetElement(element) {

    if (!element) {

        return false;

    }

    try {

        if (

            element.nodeType !==

            Node.ELEMENT_NODE

        ) {

            return false;

        }

        if (

            element.id ===

            "guardnet-result"

        ) {

            return true;

        }

        if (

            element.id ===

            "guardnet-popup-style"

        ) {

            return true;

        }

        if (

            element.closest &&

            element.closest(

                "#guardnet-result"

            )

        ) {

            return true;

        }

        return false;

    } catch (error) {

        return false;

    }

}

// =====================================================

// CHECK USEFUL CONTAINER

// =====================================================

function isUsefulContainer(element) {

    if (!element) {

        return false;

    }

    if (

        isGuardNetElement(element)

    ) {

        return false;

    }

    const tag =

        String(

            element.tagName || ""

        ).toLowerCase();

    if (

        tag === "script" ||

        tag === "style" ||

        tag === "noscript"

    ) {

        return false;

    }

    return true;

}

// =====================================================

// GET ARTICLE / DIALOG

// =====================================================

function getContentRoot(element) {

    if (!element) {

        return null;

    }

    try {

        const root =

            element.closest &&

            (

                element.closest(

                    "article"

                ) ||

                element.closest(

                    '[role="dialog"]'

                )

            );

        return (

            root ||

            element

        );

    } catch (error) {

        return element;

    }

}

// =====================================================

// GET ELEMENT CONTENT KEY

// =====================================================

function getElementContentKey(element) {

    try {

        if (!element) {

            return (

                "page:" +

                makeStableKey(

                    window.location.href

                )

            );

        }

        const root =

            getContentRoot(

                element

            );

        if (!root) {

            return (

                "page:" +

                makeStableKey(

                    window.location.href

                )

            );

        }

        // -------------------------------------------------

        // PRIORITAS 1: PERMALINK POST / REEL

        // -------------------------------------------------

        // URL media video dapat berubah. Permalink post/reel

        // jauh lebih stabil sebagai identitas content.

        try {

            const links =

                Array.from(

                    root.querySelectorAll(

                        "a[href]"

                    )

                );

            for (

                const link

                of links

            ) {

                const href =

                    String(

                        link.href ||

                        link.getAttribute("href") ||

                        ""

                    ).trim();

                if (!href) {

                    continue;

                }

                try {

                    const parsed =

                        new URL(

                            href,

                            window.location.origin

                        );

                    const pathname =

                        parsed.pathname

                            .replace(

                                /\/+$/,

                                ""

                            );

                    if (

                        /^\/(p|reel|reels|tv)\//i.test(

                            pathname

                        )

                    ) {

                        return (

                            "content:url:" +

                            makeStableKey(

                                pathname

                            )

                        );

                    }

                } catch (urlError) {

                    // lanjut

                }

            }

        } catch (linkError) {

            // fallback

        }

        // -------------------------------------------------

        // PRIORITAS 2: TEXT + MEDIA FALLBACK

        // -------------------------------------------------

        let media =

            "";

        try {

            const mediaNode =

                root.querySelector(

                    "img[src], video[src], video[poster]"

                );

            if (mediaNode) {

                media =

                    mediaNode.currentSrc ||

                    mediaNode.src ||

                    mediaNode.poster ||

                    "";

            }

        } catch (mediaError) {

            media = "";

        }

        const text =

            normalizeText(

                root.innerText ||

                root.textContent ||

                ""

            ).substring(

                0,

                700

            );

        const raw =

            window.location.pathname +

            (

                media

                    ? (

                        "|MEDIA|" +

                        media

                    )

                    : (

                        "|TEXT|" +

                        text

                    )

            );

        return (

            "content:" +

            makeStableKey(

                raw

            )

        );

    } catch (error) {

        return (

            "page:" +

            makeStableKey(

                window.location.href

            )

        );

    }

}

// =====================================================

// GET MOST VISIBLE CONTENT

// =====================================================

// =====================================================

function getMostVisibleContentKey() {

    try {

        const elements =

            Array.from(

                document.querySelectorAll(

                    "article, [role='dialog']"

                )

            ).filter(

                element =>

                    !isGuardNetElement(

                        element

                    )

            );

        if (!elements.length) {

            return (

                "page:" +

                makeStableKey(

                    window.location.href

                )

            );

        }

        let best =

            null;

        let bestArea =

            0;

        for (

            const element

            of elements

        ) {

            try {

                const rect =

                    element.getBoundingClientRect();

                const visibleWidth =

                    Math.max(

                        0,

                        Math.min(

                            rect.right,

                            window.innerWidth

                        ) -

                        Math.max(

                            rect.left,

                            0

                        )

                    );

                const visibleHeight =

                    Math.max(

                        0,

                        Math.min(

                            rect.bottom,

                            window.innerHeight

                        ) -

                        Math.max(

                            rect.top,

                            0

                        )

                    );

                const area =

                    visibleWidth *

                    visibleHeight;

                if (

                    area >

                    bestArea

                ) {

                    bestArea =

                        area;

                    best =

                        element;

                }

            } catch (error) {

                continue;

            }

        }

        if (best) {

            return getElementContentKey(

                best

            );

        }

        return (

            "page:" +

            makeStableKey(

                window.location.href

            )

        );

    } catch (error) {

        return (

            "page:" +

            makeStableKey(

                window.location.href

            )

        );

    }

}

// =====================================================

// GET DETECTED TEXT FROM ELEMENT

// =====================================================

function getDetectedTextForElement(

    element

) {

    try {

        const root =

            getContentRoot(

                element

            );

        if (!root) {

            return "";

        }

        return normalizeText(

            root.innerText ||

            root.textContent ||

            ""

        ).substring(

            0,

            MAX_CONTEXT_LENGTH

        );

    } catch (error) {

        return "";

    }

}

// =====================================================

// GET TEXT AREAS

// =====================================================

function getTextAreas() {

    const areas =

        [];

    try {

        document

            .querySelectorAll(

                "article"

            )

            .forEach(

                article => {

                    if (

                        isUsefulContainer(

                            article

                        )

                    ) {

                        areas.push({

                            element:

                                article,

                            type:

                                "caption"

                        });

                    }

                }

            );

        document

            .querySelectorAll(

                '[role="dialog"]'

            )

            .forEach(

                dialog => {

                    if (

                        isUsefulContainer(

                            dialog

                        )

                    ) {

                        areas.push({

                            element:

                                dialog,

                            type:

                                "comment"

                        });

                    }

                }

            );

    } catch (error) {

        console.error(

            "[GuardNet-AI] getTextAreas error:",

            error

        );

    }

    return areas;

}

// =====================================================

// SAFE SEND MESSAGE

// =====================================================

function safeSendMessage(

    message

) {

    try {

        if (

            typeof chrome ===

            "undefined" ||

            !chrome.runtime ||

            !chrome.runtime.id

        ) {

            console.warn(

                "[GuardNet-AI] Extension context tidak valid."

            );

            return false;

        }

        chrome.runtime.sendMessage(

            message,

            response => {

                try {

                    if (

                        chrome.runtime.lastError

                    ) {

                        console.warn(

                            "[GuardNet-AI] Runtime:",

                            chrome.runtime.lastError.message

                        );

                        return;

                    }

                    if (response) {

                        console.log(

                            "[GuardNet-AI] Background response:",

                            response

                        );

                    }

                } catch (error) {

                    console.warn(

                        "[GuardNet-AI] Response error:",

                        error

                    );

                }

            }

        );

        return true;

    } catch (error) {

        console.error(

            "[GuardNet-AI] Send message error:",

            error

        );

        return false;

    }

}

// =====================================================

// ANALYZE TEXT

// =====================================================

// =====================================================

// MEDIA-FIRST OPTIMIZATION

// =====================================================

// Instagram post yang memiliki gambar/video sudah dianalisis lewat

// /analyze-full. Teks/caption dikirim sebagai detected_text di request

// tersebut, sehingga request text-only terpisah hanya menambah latency

// dan dapat menyebabkan hasil async bertabrakan.

function elementHasAnalyzableMedia(element) {

    if (!element) {

        return false;

    }

    try {

        const root =

            element.closest?.("article, [role='dialog']") ||

            element;

        if (!root) {

            return false;

        }

        const image =

            root.querySelector?.("img");

        if (image && isValidImage(image)) {

            return true;

        }

        const video =

            root.querySelector?.("video");

        if (video && isNearViewport(video)) {

            return true;

        }

    } catch (error) {

        // Jangan membuat scanning berhenti hanya karena struktur DOM Instagram berubah.

    }

    return false;

}

function analyzeText(

    text,

    sourceType = "unknown",

    element = null

) {

    const normalized =

        limitText(

            text

        );

    if (!normalized) {

        return;

    }

    if (

        normalized.length <

        3

    ) {

        return;

    }

    // Media-first: caption/txt akan ikut dikirim bersama /analyze-full.

    if (elementHasAnalyzableMedia(element)) {

        console.log(

            "[GuardNet-AI] Text-only dilewati: konten memiliki media; teks akan ikut /analyze-full."

        );

        return;

    }

    const contentKey =

        getElementContentKey(

            element

        );

    const textKey =

        contentKey +

        "|" +

        sourceType +

        "|" +

        normalized;

    if (

        processedTexts.has(

            textKey

        )

    ) {

        return;

    }

    processedTexts.add(

        textKey

    );

    console.log(

        "[GuardNet-AI] Text ditemukan:",

        {

            sourceType,

            contentKey,

            text:

                normalized.substring(

                    0,

                    200

                )

        }

    );

    showGuardNetLoading(contentKey, "text");

    const success =

        safeSendMessage({

            action:

                "analyzeContent",

            text:

                normalized,

            url:

                window.location.href,

            sourceType:

                sourceType,

            contentKey:

                contentKey,

            analysisGeneration:

                analysisGeneration

        });

    if (!success) {

        processedTexts.delete(

            textKey

        );

        clearGuardNetLoading(contentKey);

    }

}

// =====================================================

// DETECT TEXT

// =====================================================

function detectText() {

    const areas =

        getTextAreas();

    console.log(

        "[GuardNet-AI] Total text area:",

        areas.length

    );

    for (

        const areaInfo

        of areas

    ) {

        if (!areaInfo) {

            continue;

        }

        const element =

            areaInfo.element;

        if (!element) {

            continue;

        }

        if (

            isGuardNetElement(

                element

            )

        ) {

            continue;

        }

        try {

            const rect =

                element.getBoundingClientRect();

            if (

                rect.bottom <

                -VIEWPORT_MARGIN ||

                rect.top >

                window.innerHeight +

                VIEWPORT_MARGIN

            ) {

                continue;

            }

        } catch (error) {

            // tetap lanjut

        }

        const text =

            element.innerText ||

            element.textContent ||

            "";

        if (

            !text.trim()

        ) {

            continue;

        }

        analyzeText(

            text,

            areaInfo.type,

            element

        );

    }

}

// =====================================================

// GET IMAGE URL

// =====================================================

function getImageUrl(

    img

) {

    if (!img) {

        return "";

    }

    try {

        return (

            img.currentSrc ||

            img.src ||

            ""

        ).trim();

    } catch (error) {

        return "";

    }

}

// =====================================================

// IMAGE VALIDATION

// =====================================================

function isValidImage(

    img

) {

    if (!img) {

        return false;

    }

    try {

        if (

            img.tagName

                ?.toLowerCase() !==

            "img"

        ) {

            return false;

        }

        const width =

            img.naturalWidth ||

            img.width ||

            0;

        const height =

            img.naturalHeight ||

            img.height ||

            0;

        if (

            width <

            MIN_IMAGE_WIDTH

        ) {

            return false;

        }

        if (

            height <

            MIN_IMAGE_HEIGHT

        ) {

            return false;

        }

        if (

            isGuardNetElement(

                img

            )

        ) {

            return false;

        }

        return true;

    } catch (error) {

        return false;

    }

}

// =====================================================

// NEAR VIEWPORT

// =====================================================

function isNearViewport(

    element

) {

    if (!element) {

        return false;

    }

    try {

        const rect =

            element.getBoundingClientRect();

        return (

            rect.bottom >=

                -VIEWPORT_MARGIN &&

            rect.top <=

                window.innerHeight +

                VIEWPORT_MARGIN &&

            rect.right >=

                -VIEWPORT_MARGIN &&

            rect.left <=

                window.innerWidth +

                VIEWPORT_MARGIN

        );

    } catch (error) {

        return false;

    }

}

// =====================================================

// ANALYZE IMAGE

// =====================================================

function analyzeImage(

    img

) {

    if (

        !isValidImage(

            img

        )

    ) {

        return;

    }

    if (

        !isNearViewport(

            img

        )

    ) {

        return;

    }

    const imageUrl =

        getImageUrl(

            img

        );

    if (!imageUrl) {

        return;

    }

    const contentKey =

        getElementContentKey(

            img

        );

    mediaContentMap.set(

        imageUrl,

        contentKey

    );

    if (

        processedImages.has(

            imageUrl

        )

    ) {

        return;

    }

    if (

        processingImages.has(

            imageUrl

        )

    ) {

        return;

    }

    if (

        processingImages.size >=

        MAX_MEDIA_PER_SCAN

    ) {

        return;

    }

    processingImages.add(

        imageUrl

    );

    pendingImages.set(

        imageUrl,

        Date.now()

    );

    const detectedText =

        getDetectedTextForElement(

            img

        );

    console.log(

        "[GuardNet-AI] Image dikirim:",

        {

            contentKey,

            imageUrl:

                imageUrl.substring(

                    0,

                    150

                )

        }

    );

    showGuardNetLoading(contentKey, "media");

    const success =

        safeSendMessage({

            action:

                "ocrImage",

            imageUrl:

                imageUrl,

            url:

                window.location.href,

            sourceType:

                "image",

            detectedText:

                detectedText,

            contentKey:

                contentKey,

            analysisGeneration:

                analysisGeneration

        });

    if (!success) {

        processingImages.delete(

            imageUrl

        );

        pendingImages.delete(

            imageUrl

        );

        clearGuardNetLoading(contentKey);

    }

}

// =====================================================

// GET VIDEO POSTER

// =====================================================

function getVideoPoster(

    video

) {

    if (!video) {

        return "";

    }

    try {

        return String(

            video.poster ||

            ""

        ).trim();

    } catch (error) {

        return "";

    }

}

// =====================================================

// CAPTURE VIDEO FRAME

// =====================================================

function captureVideoFrame(

    video

) {

    if (!video) {

        return;

    }

    if (

        !isNearViewport(

            video

        )

    ) {

        return;

    }

    const contentKey =

        getElementContentKey(

            video

        );

    const detectedText =

        getDetectedTextForElement(

            video

        );

    try {

        if (

            video.readyState >=

                2 &&

            video.videoWidth >

                0 &&

            video.videoHeight >

                0

        ) {

            const sourceWidth =

                video.videoWidth;

            const sourceHeight =

                video.videoHeight;

            let width =

                VIDEO_FRAME_WIDTH;

            let height =

                Math.round(

                    sourceHeight *

                    (

                        width /

                        sourceWidth

                    )

                );

            if (

                height >

                VIDEO_FRAME_WIDTH

            ) {

                height =

                    VIDEO_FRAME_WIDTH;

                width =

                    Math.round(

                        sourceWidth *

                        (

                            height /

                            sourceHeight

                        )

                    );

            }

            const canvas =

                document.createElement(

                    "canvas"

                );

            canvas.width =

                width;

            canvas.height =

                height;

            const ctx =

                canvas.getContext(

                    "2d"

                );

            if (ctx) {

                ctx.drawImage(

                    video,

                    0,

                    0,

                    width,

                    height

                );

                const frameData =

                    canvas.toDataURL(

                        "image/jpeg",

                        0.78

                    );

                if (

                    frameData

                ) {

                    const videoKey =

                        video.currentSrc ||

                        video.src ||

                        contentKey;

                    if (

                        processedVideos.has(

                            videoKey

                        )

                    ) {

                        return;

                    }

                    processedVideos.add(

                        videoKey

                    );

                    showGuardNetLoading(contentKey, "video");

                    safeSendMessage({

                        action:

                            "videoFrame",

                        frameData:

                            frameData,

                        url:

                            window.location.href,

                        detectedText:

                            detectedText,

                        contentKey:

                            contentKey,

                        analysisGeneration:

                            analysisGeneration

                    });

                    console.log(

                        "[GuardNet-AI] Video frame dikirim."

                    );

                    return;

                }

            }

        }

    } catch (error) {

        console.warn(

            "[GuardNet-AI] Video frame gagal:",

            error

        );

    }

    // =================================================

    // ONE RETRY FOR VIDEO FRAME

    // =================================================

    // Coba sekali lagi setelah metadata/frame tersedia.

    if (

        !video.dataset.guardnetRetryScheduled

    ) {

        video.dataset.guardnetRetryScheduled = "1";

        setTimeout(

            () => {

                try {

                    video.dataset.guardnetRetryScheduled = "0";

                    captureVideoFrame(video);

                } catch (error) {

                    console.warn(

                        "[GuardNet-AI] Video retry gagal:",

                        error

                    );

                }

            },

            700

        );

        return;

    }

    // =================================================

    // NO POSTER OCR FALLBACK

    // =================================================

    // Poster Instagram/CDN sering tidak dapat di-fetch dari service worker.

    // Gunakan frame video asli sebagai sumber analisis agar tidak muncul

    // error OCR "Failed to fetch" dan tidak membuat request tambahan.

    console.log(

        "[GuardNet-AI] Video frame belum tersedia; poster OCR dilewati."

    );

}

// =====================================================

// DETECT IMAGES

// =====================================================

function detectImages() {

    const roots =

        Array.from(

            document.querySelectorAll(

                "article, [role='dialog']"

            )

        ).filter(

            element =>

                !isGuardNetElement(

                    element

                )

        );

    let count =

        0;

    for (

        const root

        of roots

    ) {

        if (

            count >=

            MAX_MEDIA_PER_SCAN

        ) {

            break;

        }

        const images =

            Array.from(

                root.querySelectorAll(

                    "img"

                )

            );

        for (

            const img

            of images

        ) {

            if (

                count >=

                MAX_MEDIA_PER_SCAN

            ) {

                break;

            }

            if (

                !isValidImage(

                    img

                )

            ) {

                continue;

            }

            if (

                !isNearViewport(

                    img

                )

            ) {

                continue;

            }

            analyzeImage(

                img

            );

            count++;

        }

    }

}

// =====================================================

// DETECT VIDEOS

// =====================================================

function detectVideos() {

    const videos =

        Array.from(

            document.querySelectorAll(

                "article video, [role='dialog'] video"

            )

        );

    for (

        const video

        of videos

    ) {

        if (

            !isNearViewport(

                video

            )

        ) {

            continue;

        }

        const videoKey =

            video.currentSrc ||

            video.src ||

            video.poster ||

            getElementContentKey(

                video

            );

        if (

            processedVideos.has(

                videoKey

            )

        ) {

            continue;

        }

        captureVideoFrame(

            video

        );

    }

}

// =====================================================

// MAIN SCAN

// =====================================================

function scanContent() {

    if (

        scanRunning

    ) {

        return;

    }

    scanRunning =

        true;

    try {

        updateVisibleContent();

        // Media-first mengurangi request ganda dan membuat hasil final lebih konsisten.

        detectImages();

        detectVideos();

        detectText();

    } catch (error) {

        console.error(

            "[GuardNet-AI] scanContent error:",

            error

        );

    } finally {

        scanRunning =

            false;

    }

}

// =====================================================

// SCHEDULE SCAN

// =====================================================

function scheduleScan(

    delay = MUTATION_SCAN_DELAY

) {

    try {

        if (

            scanTimeout

        ) {

            clearTimeout(

                scanTimeout

            );

        }

        scanTimeout =

            setTimeout(

                () => {

                    scanTimeout =

                        null;

                    scanContent();

                },

                delay

            );

    } catch (error) {

        console.error(

            "[GuardNet-AI] scheduleScan error:",

            error

        );

    }

}

// =====================================================

// SCHEDULE SCROLL SCAN

// =====================================================

function scheduleScrollScan() {

    try {

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

                    scrollScanTimeout =

                        null;

                    updateVisibleContent();

                    scanContent();

                },

                SCROLL_SCAN_DELAY

            );

    } catch (error) {

        console.error(

            "[GuardNet-AI] scheduleScrollScan error:",

            error

        );

    }

}

// =====================================================

// UPDATE VISIBLE CONTENT

// =====================================================

function updateVisibleContent() {

    try {

        const visibleKey =

            getMostVisibleContentKey();

        if (!currentContentKey) {

            currentContentKey =

                visibleKey;

            analysisGeneration += 1;

            activeContentGeneration =

                analysisGeneration;

            return;

        }

        if (

            visibleKey !==

            currentContentKey

        ) {

            const oldKey =

                currentContentKey;

            console.log(

                "[GuardNet-AI] Pindah content:",

                {

                    old:

                        oldKey,

                    new:

                        visibleKey,

                    oldGeneration:

                        analysisGeneration

                }

            );

            // -------------------------------------------------

            // INVALIDATE SEMUA RESPONSE ASYNC DARI CONTENT LAMA

            // -------------------------------------------------

            analysisGeneration += 1;

            activeContentGeneration =

                analysisGeneration;

            hideGuardNetResult();

            currentContentKey =

                visibleKey;

            currentBestRisk =

                "NONE";

            currentBestScore =

                0;

            // Hanya hasil milik content BARU yang boleh tampil.

            const locked =

                contentLocks.get(

                    visibleKey

                );

            if (

                locked &&

                locked.result

            ) {

                currentBestRisk =

                    locked.risk;

                currentBestScore =

                    locked.score;

                const generationAtRestore =

                    analysisGeneration;

                setTimeout(

                    () => {

                        if (

                            generationAtRestore !==

                            analysisGeneration

                        ) {

                            return;

                        }

                        if (

                            getMostVisibleContentKey() ===

                            visibleKey

                        ) {

                            showGuardNetResult(

                                locked.result

                            );

                        }

                    },

                    30

                );

            }

        }

    } catch (error) {

        console.error(

            "[GuardNet-AI] updateVisibleContent error:",

            error

        );

    }

}

// =====================================================

// RESET PAGE STATE

// =====================================================

// =====================================================

function resetForNewPage() {

    hideGuardNetResult();

    processedTexts.clear();

    processedImages.clear();

    processingImages.clear();

    processedVideos.clear();

    receivedResults.clear();

    pendingImages.clear();

    mediaContentMap.clear();

    currentContentKey =

        null;

    currentBestRisk =

        "NONE";

    currentBestScore =

        0;

    loadingContentKey = null;

    loadingGeneration = null;

    // Semua response yang masih berjalan dari halaman lama

    // dianggap stale.

    analysisGeneration += 1;

    activeContentGeneration =

        analysisGeneration;

    // Jangan hapus contentLocks.

    // Supaya result content yang masih relevan

    // bisa digunakan kembali selama SPA berjalan.

}

// =====================================================

// CHECK PAGE CHANGE

// =====================================================

function checkPageChange() {

    try {

        const currentUrl =

            window.location.href;

        if (

            currentUrl !==

            lastPageUrl

        ) {

            console.log(

                "[GuardNet-AI] URL berubah."

            );

            lastPageUrl =

                currentUrl;

            resetForNewPage();

            scheduleScan(

                INITIAL_SCAN_DELAY

            );

        }

    } catch (error) {

        console.error(

            "[GuardNet-AI] checkPageChange error:",

            error

        );

    }

}

// =====================================================

// EXTRACT ANALYSIS RESULT

// =====================================================

function extractAnalysisResult(

    raw

) {

    if (!raw) {

        return null;

    }

    let result = {

        ...raw

    };

    const finalData =

        raw.analysis?.final ||

        raw.final ||

        null;

    const visualData =

        raw.analysis?.visual ||

        raw.visual ||

        null;

    const textData =

        raw.analysis?.text ||

        raw.text ||

        null;

    if (

        raw.risk_level

    ) {

        result.risk_level =

            raw.risk_level;

    } else if (

        finalData?.risk_level

    ) {

        result.risk_level =

            finalData.risk_level;

    } else if (

        visualData?.risk_level

    ) {

        result.risk_level =

            visualData.risk_level;

    } else if (

        textData?.risk_level

    ) {

        result.risk_level =

            textData.risk_level;

    }

    if (

        raw.score !==

        undefined

    ) {

        result.score =

            Number(

                raw.score || 0

            );

    } else if (

        finalData?.score !==

        undefined

    ) {

        result.score =

            Number(

                finalData.score || 0

            );

    } else if (

        visualData?.score !==

        undefined

    ) {

        result.score =

            Number(

                visualData.score || 0

            );

    } else {

        result.score =

            Number(

                textData?.score || 0

            );

    }

    if (

        !Array.isArray(

            result.detected_indicators

        )

    ) {

        if (

            Array.isArray(

                finalData?.detected_indicators

            )

        ) {

            result.detected_indicators =

                finalData.detected_indicators;

        } else if (

            Array.isArray(

                visualData?.detected_indicators

            )

        ) {

            result.detected_indicators =

                visualData.detected_indicators;

        } else if (

            Array.isArray(

                textData?.detected_indicators

            )

        ) {

            result.detected_indicators =

                textData.detected_indicators;

        } else {

            result.detected_indicators =

                [];

        }

    }

    if (

        !result.description

    ) {

        result.description =

            finalData?.description ||

            raw.description ||

            "";

    }

    return result;

}

// =====================================================

// STORE CONTENT RESULT

// =====================================================

function storeContentResult(

    contentKey,

    result,

    stage = "full"

) {

    if (

        !contentKey ||

        !result

    ) {

        return;

    }

    contentLocks.set(

        contentKey,

        {

            risk:

                result.risk_level,

            score:

                Number(

                    result.score || 0

                ),

            result:

                result,
            stage:

                String(stage || "full").toLowerCase(),

            updatedAt:

                Date.now()

        }

    );

}

// =====================================================

// HANDLE RESULT

// =====================================================


function handleAnalysisResult(

    rawResult,

    message = {}

) {

    const result =

        extractAnalysisResult(

            rawResult

        );

    if (!result) {

        return;

    }

    // Jika message membawa generation, validasi juga.

    // Background script yang belum meneruskan generation tetap

    // dilindungi oleh contentKey di bawah.

    if (

        message &&

        message.analysisGeneration !== undefined &&

        Number(message.analysisGeneration) !==

            Number(analysisGeneration)

    ) {

        console.log(

            "[GuardNet-AI] Result generation lama dibuang:",

            {

                received:

                    message.analysisGeneration,

                current:

                    analysisGeneration

            }

        );

        return;

    }

    let risk =

        String(

            result.risk_level ||

            "LOW"

        )

            .trim()

            .toUpperCase();

    if (

        ![

            "LOW",

            "MEDIUM",

            "HIGH"

        ].includes(

            risk

        )

    ) {

        risk =

            "LOW";

    }

    result.risk_level =

        risk;

    let score =

        Number(

            result.score || 0

        );

    if (

        !Number.isFinite(

            score

        )

    ) {

        score =

            0;

    }

    result.score =

        score;

    // =================================================

    // CONTENT KEY

    // =================================================

    let contentKey =

        result.contentKey ||

        result.content_key ||

        message.contentKey ||

        message.content_key ||

        null;

    if (

        !contentKey &&

        message.imageUrl

    ) {

        contentKey =

            mediaContentMap.get(

                message.imageUrl

            );

    }

    if (

        !contentKey &&

        result.imageUrl

    ) {

        contentKey =

            mediaContentMap.get(

                result.imageUrl

            );

    }

    if (

        !contentKey &&

        result.image_url

    ) {

        contentKey =

            mediaContentMap.get(

                result.image_url

            );

    }

    // JANGAN pernah menganggap result async sebagai milik

    // content yang sedang terlihat hanya karena contentKey hilang.

    // Fallback seperti itu dapat mencampurkan hasil post lama

    // dengan post baru saat user scroll cepat.

    if (!contentKey) {

        console.warn(

            "[GuardNet-AI] Result dibuang: contentKey tidak ada.",

            {

                action:

                    message.action

            }

        );

        return;

    }

    result.contentKey =

        contentKey;

    // -------------------------------------------------

    // CRITICAL: VALIDASI SEBELUM MENYIMPAN

    // -------------------------------------------------

    // Result content lama boleh tetap disimpan sebagai cache,

    // tetapi tidak boleh mempengaruhi content yang sedang aktif.

    const visibleKeyBeforeStore =

        getMostVisibleContentKey();

    if (

        visibleKeyBeforeStore !==

        contentKey

    ) {

        console.log(

            "[GuardNet-AI] Result stale dibuang sebelum UI:",

            {

                resultContentKey:

                    contentKey,

                visibleContentKey:

                    visibleKeyBeforeStore,

                generation:

                    analysisGeneration

            }

        );

        return;

    }

    // =================================================

    // LOCK EXISTING RESULT

    // =================================================

    const existing =

        contentLocks.get(

            contentKey

        );

    if (existing) {

        const existingStage =

            String(

                existing.stage ||

                    "full"

            ).toLowerCase();

        const incomingStage =

            String(

                message.stage ||

                    "full"

            ).toLowerCase();

        // FULL adalah hasil final/authoritative.

        // FULL boleh mengoreksi hasil FAST, termasuk MEDIUM -> LOW

        // atau HIGH -> LOW untuk content yang sama.

        if (

            incomingStage === "full" &&

            existingStage !== "full"

        ) {

            console.log(

                "[GuardNet-AI] FULL mengoreksi hasil FAST:",

                {

                    existing:

                        existing.risk,

                    incoming:

                        risk,

                    existingStage,

                    incomingStage

                }

            );

        } else if (

            incomingStage !== "full" &&

            existingStage === "full"

        ) {

            console.log(

                "[GuardNet-AI] FAST diabaikan karena FULL sudah tersedia."

            );

            return;

        } else {

            const oldPriority =

                getRiskPriority(

                    existing.risk

                );

            const newPriority =

                getRiskPriority(

                    risk

                );

            if (

                newPriority <

                oldPriority

            ) {

                console.log(

                    "[GuardNet-AI] Result lebih rendah diabaikan:",

                    {

                        existing:

                            existing.risk,

                        incoming:

                            risk,

                        stage:

                            incomingStage

                    }

                );

                return;

            }

            if (

                newPriority ===

                    oldPriority &&

                score <=

                    Number(

                        existing.score ||

                            0

                    )

            ) {

                console.log(

                    "[GuardNet-AI] Result score lebih kecil/sama diabaikan."

                );

                return;

            }

        }

    }

    // =================================================

    // SAVE BEST RESULT

    // =================================================

    storeContentResult(

        contentKey,

        result,

        message.stage || "full"

    );

    currentContentKey =

        contentKey;

    currentBestRisk =

        risk;

    currentBestScore =

        score;

    // =================================================

    // RESULT KEY

    // =================================================

    const resultKey =

        [

            contentKey,

            risk,

            score.toFixed(4),

            result.case_id ||

                "",

            result.content_id ||

                "",

            result.report_id ||

                "",

            JSON.stringify(

                result.detected_indicators ||

                []

            )

        ].join("|");

    if (

        receivedResults.has(

            resultKey

        )

    ) {

        return;

    }

    receivedResults.add(

        resultKey

    );

    // =================================================

    // ONLY SHOW CURRENT VISIBLE CONTENT

    // =================================================

    const visibleKey =

        getMostVisibleContentKey();

    if (

        visibleKey !==

        contentKey

    ) {

        console.log(

            "[GuardNet-AI] Result bukan content yang sedang terlihat."

        );

        return;

    }

    // FINAL IDENTITY CHECK: jangan tampilkan hasil jika konten aktif

    // sudah berubah setelah asynchronous analysis selesai.

    if (getMostVisibleContentKey() !== contentKey) {

        console.log(

            "[GuardNet-AI] UI result dibatalkan: visible content berubah.",

            {

                resultContentKey: contentKey,

                visibleContentKey: getMostVisibleContentKey(),

                generation: analysisGeneration

            }

        );

        return;

    }
    showGuardNetResult(
        result,
        message.imageUrl ||
        result.imageUrl ||
        result.image_url ||
        "",
        message.stage || "full"
    );

}

// =====================================================

// GET INDICATORS

// =====================================================

function getIndicators(

    result

) {

    if (!result) {

        return [];

    }

    let indicators =

        result.detected_indicators;

    if (

        !Array.isArray(

            indicators

        )

    ) {

        if (

            typeof indicators ===

            "string"

        ) {

            indicators =

                indicators

                    .split(",")

                    .map(

                        item =>

                            item.trim()

                    )

                    .filter(Boolean);

        } else {

            indicators =

                [];

        }

    }

    return indicators;

}

// =====================================================

// CREATE POPUP STYLES

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

            top: 20px;

            right: 20px;

            width: 370px;

            max-width:

                calc(100vw - 40px);

            background:

                #ffffff;

            border:

                2px solid #222222;

            border-radius:

                16px;

            box-shadow:

                0 10px 35px

                rgba(0,0,0,0.25);

            z-index:

                2147483647;

            font-family:

                Arial, sans-serif;

            color:

                #222222;

            overflow:

                hidden;

            box-sizing:

                border-box;

            animation:

                guardnetSlideIn

                0.22s ease-out;

        }

        #guardnet-result.guardnet-hide {

            opacity:

                0;

            transform:

                translateY(-10px);

            transition:

                all 0.18s ease;

        }

        .guardnet-header {

            display:

                flex;

            align-items:

                center;

            gap:

                10px;

            padding:

                15px 16px;

            border-bottom:

                1px solid #eeeeee;

        }

        .guardnet-icon {

            font-size:

                25px;

        }

        .guardnet-title {

            flex:

                1;

            display:

                flex;

            flex-direction:

                column;

            gap:

                3px;

        }

        .guardnet-title strong {

            font-size:

                16px;

        }

        .guardnet-title span {

            font-size:

                13px;

            font-weight:

                700;

        }

        .guardnet-close {

            border:

                none;

            background:

                transparent;

            font-size:

                25px;

            line-height:

                1;

            cursor:

                pointer;

            color:

                #666666;

            padding:

                3px 6px;

        }

        .guardnet-body {

            padding:

                15px 16px;

        }

        .guardnet-risk-box {

            display:

                flex;

            align-items:

                center;

            justify-content:

                space-between;

            padding:

                12px;

            border-radius:

                10px;

            margin-bottom:

                12px;

            background:

                #f7f7f7;

        }

        .guardnet-risk-label {

            font-size:

                13px;

            color:

                #666666;

        }

        .guardnet-risk-value {

            font-size:

                18px;

            font-weight:

                800;

        }

        .guardnet-score {

            margin-bottom:

                12px;

            font-size:

                13px;

        }

        .guardnet-score strong {

            font-size:

                15px;

        }

        .guardnet-section-title {

            font-size:

                12px;

            font-weight:

                800;

            margin-top:

                13px;

            margin-bottom:

                7px;

            text-transform:

                uppercase;

        }

        .guardnet-indicators {

            display:

                flex;

            flex-wrap:

                wrap;

            gap:

                6px;

        }

        .guardnet-indicator {

            display:

                inline-block;

            padding:

                5px 8px;

            background:

                #f1f1f1;

            border-radius:

                7px;

            font-size:

                11px;

            word-break:

                break-word;

        }

        .guardnet-description {

            font-size:

                13px;

            line-height:

                1.5;

            color:

                #444444;

        }

        .guardnet-source {

            margin-top:

                12px;

            font-size:

                11px;

            color:

                #777777;

        }

        .guardnet-meta {

            margin-top:

                13px;

            padding-top:

                10px;

            border-top:

                1px solid #eeeeee;

            display:

                flex;

            flex-direction:

                column;

            gap:

                4px;

            font-size:

                10px;

            color:

                #777777;

        }

        .guardnet-footer {

            padding:

                10px 16px;

            background:

                #fafafa;

            font-size:

                10px;

            color:

                #777777;

        }

        .guardnet-loading-box {

            display: flex;

            flex-direction: column;

            align-items: center;

            gap: 8px;

            padding: 18px 12px;

            border-radius: 12px;

            background: #eff6ff;

            text-align: center;

        }

        .guardnet-loading-box strong {

            font-size: 15px;

        }

        .guardnet-loading-box span {

            font-size: 12px;

            line-height: 1.45;

            color: #4b5563;

        }

        .guardnet-spinner {

            width: 30px;

            height: 30px;

            border: 3px solid #dbeafe;

            border-top-color: #2563eb;

            border-radius: 50%;

            animation: guardnetSpin 0.8s linear infinite;

        }

        .guardnet-progress-list {

            display: flex;

            flex-direction: column;

            gap: 6px;

            margin-top: 13px;

            padding: 11px 12px;

            border-radius: 10px;

            background: #f8fafc;

            font-size: 12px;

            color: #475569;

        }

        .guardnet-progress-list div:first-child {

            color: #15803d;

        }

        @keyframes guardnetSpin {

            to {

                transform: rotate(360deg);

            }

        }

        @keyframes guardnetSlideIn {

            from {

                opacity:

                    0;

                transform:

                    translateY(-12px);

            }

            to {

                opacity:

                    1;

                transform:

                    translateY(0);

            }

        }

    `;

    document.head.appendChild(

        style

    );

}

// =====================================================

// HIDE POPUP

// =====================================================

function hideGuardNetResult() {

    try {

        if (

            popupTimer

        ) {

            clearTimeout(

                popupTimer

            );

            popupTimer =

                null;

        }

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

                try {

                    if (

                        popup &&

                        popup.parentNode

                    ) {

                        popup.remove();

                    }

                } catch (error) {

                    // ignore

                }

            },

            180

        );

    } catch (error) {

        console.error(

            "[GuardNet-AI] hide popup error:",

            error

        );

    }

}

// =====================================================

// RISK ICON

// =====================================================

function getRiskIcon(

    risk

) {

    if (

        risk === "HIGH"

    ) {

        return "🚨";

    }

    if (

        risk === "MEDIUM"

    ) {

        return "⚠️";

    }

    return "🛡️";

}

// =====================================================

// RISK TITLE

// =====================================================

function getRiskTitle(

    risk

) {

    if (

        risk === "HIGH"

    ) {

        return "TERINDIKASI KUAT IKLAN JUDI ONLINE";

    }

    if (

        risk === "MEDIUM"

    ) {

        return "TERINDIKASI IKLAN JUDI ONLINE";

    }

    return "TIDAK DITEMUKAN INDIKATOR KUAT";

}

// =====================================================

// RISK EXPLANATION FOR NON-TECHNICAL USERS

// =====================================================

function getRiskExplanation(risk) {

    if (risk === "HIGH") {

        return "Konten memiliki indikator kuat yang mengarah pada promosi atau aktivitas judi online. Hasil tetap perlu diverifikasi sebelum tindakan lebih lanjut.";

    }

    if (risk === "MEDIUM") {

        return "Konten memiliki beberapa indikator yang mengarah pada promosi atau aktivitas judi online dan disarankan untuk diperiksa lebih lanjut.";

    }

    return "Belum ditemukan indikator kuat yang mengarah pada promosi judi online berdasarkan analisis saat ini.";

}

// =====================================================

// RISK COLOR

// =====================================================

function getRiskColor(

    risk

) {

    if (

        risk === "HIGH"

    ) {

        return "#dc2626";

    }

    if (

        risk === "MEDIUM"

    ) {

        return "#d97706";

    }

    return "#16a34a";

}

// =====================================================

// ESCAPE HTML

// =====================================================

function escapeHtml(

    value

) {

    return String(

        value ??

        ""

    )

        .replace(

            /&/g,

            "&amp;"

        )

        .replace(

            /</g,

            "&lt;"

        )

        .replace(

            />/g,

            "&gt;"

        )

        .replace(

            /"/g,

            "&quot;"

        )

        .replace(

            /'/g,

            "&#039;"

        );

}

// =====================================================

// SHOW ANALYSIS LOADING POPUP

// =====================================================

function showGuardNetLoading(contentKey, sourceType = "media") {

    if (!contentKey) {

        return;

    }

    // Jangan membuat ulang loading popup untuk request yang sama.

    if (

        loadingContentKey === contentKey &&

        Number(loadingGeneration) === Number(analysisGeneration) &&

        document.getElementById("guardnet-result")

    ) {

        return;

    }

    loadingContentKey = contentKey;

    loadingGeneration = analysisGeneration;

    const oldPopup = document.getElementById("guardnet-result");

    if (oldPopup) {

        oldPopup.remove();

    }

    const popup = document.createElement("div");

    popup.id = "guardnet-result";

    popup.dataset.contentKey = String(contentKey);

    popup.dataset.analysisGeneration = String(analysisGeneration);

    const sourceLabel = sourceType === "text"

        ? "Teks"

        : sourceType === "video"

            ? "Video"

            : "Gambar";

    popup.innerHTML = `

        <div class="guardnet-header">

            <div class="guardnet-icon">🛡️</div>

            <div class="guardnet-title">

                <strong>GuardNet-AI</strong>

                <span style="color:#2563eb;">SEDANG MENGANALISIS</span>

            </div>

            <button class="guardnet-close" type="button" aria-label="Tutup">×</button>

        </div>

        <div class="guardnet-body">

            <div class="guardnet-loading-box">

                <div class="guardnet-spinner" aria-hidden="true"></div>

                <strong>Mohon tunggu...</strong>

                <span>Analisis cepat sedang berjalan. Hasil final akan menyusul.</span>

            </div>

            <div class="guardnet-progress-list">

                <div>✓ Konten ditemukan</div>

                <div>⏳ Visual AI + OCR</div>

                <div>⏳ Teks + konteks konten</div>

                <div>⏳ Pemeriksaan pembayaran</div>

            </div>

            <div class="guardnet-description">

                Hasil <b>LOW, MEDIUM, atau HIGH</b> akan muncul setelah seluruh analisis selesai.

            </div>

        </div>

        <div class="guardnet-footer">

            Jangan tutup atau pindah konten jika ingin melihat hasil analisis ini.

        </div>

    `;

    document.body.appendChild(popup);

    const closeButton = popup.querySelector(".guardnet-close");

    if (closeButton) {

        closeButton.addEventListener("click", event => {

            event.preventDefault();

            event.stopPropagation();

            hideGuardNetResult();

            loadingContentKey = null;

            loadingGeneration = null;

        });

    }

}

// =====================================================

// CLEAR LOADING STATE

// =====================================================

function clearGuardNetLoading(contentKey = null) {

    if (

        contentKey &&

        loadingContentKey &&

        loadingContentKey !== contentKey

    ) {

        return;

    }

    loadingContentKey = null;

    loadingGeneration = null;

}

// =====================================================

// SHOW RESULT POPUP

// =====================================================

function showGuardNetResult(
    rawResult,
    imageUrl = "",
    stage = "full"
) {

    const result =

        extractAnalysisResult(

            rawResult

        );

    if (!result) {

        return;

    }

    const risk =

        String(

            result.risk_level ||

            "LOW"

        )

            .trim()

            .toUpperCase();

    if (

        ![

            "LOW",

            "MEDIUM",

            "HIGH"

        ].includes(

            risk

        )

    ) {

        return;

    }

    const score =

        Number(

            result.score || 0

        );
    // Fast result replaces loading. Full result is authoritative and may
    // correct FAST (including HIGH -> LOW) for the same content.
    if (stage !== "full") {
        const popupNow = document.getElementById("guardnet-result");
        if (popupNow?.dataset?.analysisStage === "full") {
            return;
        }
    }

    currentBestRisk =
        risk;

    currentBestScore =

        score;

    createPopupStyles();

    const oldPopup =

        document.getElementById(

            "guardnet-result"

        );

    if (oldPopup) {

        oldPopup.remove();

    }

    const popup =

        document.createElement(

            "div"

        );

    popup.id =

        "guardnet-result";

    popup.dataset.contentKey =

        String(currentContentKey || result.contentKey || "");

    popup.dataset.analysisGeneration =

        String(analysisGeneration);

    popup.dataset.analysisStage =

        String(stage);

    const color =

        getRiskColor(

            risk

        );

    const indicators =

        getIndicators(

            result

        );

    const indicatorHtml =

        indicators.length

            ? indicators

                .slice(

                    0,

                    10

                )

                .map(

                    item =>

                        `

                            <span

                                class="guardnet-indicator"

                            >

                                ${escapeHtml(

                                    item

                                )}

                            </span>

                        `

                )

                .join("")

            : `

                <span

                    class="guardnet-indicator"

                >

                    Tidak ada indikator tambahan

                </span>

            `;

    popup.innerHTML = `

        <div class="guardnet-header">

            <div

                class="guardnet-icon"

            >

                ${getRiskIcon(

                    risk

                )}

            </div>

            <div

                class="guardnet-title"

            >

                <strong>

                    GuardNet-AI

                </strong>

                <span

                    style="

                        color:${color};

                    "

                >

                    ${getRiskTitle(

                        risk

                    )}

                </span>

            </div>

            <button

                class="guardnet-close"

                type="button"

                aria-label="Tutup"

            >

                ×

            </button>

        </div>

        <div class="guardnet-body">

            <div

                class="guardnet-risk-box"

            >

                <span

                    class="guardnet-risk-label"

                >

                    Risk Level

                </span>

                <strong

                    class="guardnet-risk-value"

                    style="

                        color:${color};

                    "

                >

                    ${escapeHtml(

                        risk

                    )}

                </strong>

            </div>

            <div

                class="guardnet-score"

            >

                <span>

                    Tingkat Risiko:

                </span>

                <strong>

                    ${Number.isFinite(score)

                        ? `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`

                        : "0%"}

                </strong>

            </div>

            <div

                class="guardnet-section-title"

            >

                Indikator Terdeteksi

            </div>

            <div

                class="guardnet-indicators"

            >

                ${indicatorHtml}

            </div>

            <div

                class="guardnet-section-title"

            >

                Kesimpulan Sederhana

            </div>

            <div

                class="guardnet-description"

            >

                ${escapeHtml(

                    getRiskExplanation(risk)

                )}

            </div>

            <div

                class="guardnet-section-title"

            >

                Detail Analisis

            </div>

            <div

                class="guardnet-description"

            >

                ${escapeHtml(

                    result.description ||

                    "Analisis multimodal GuardNet-AI telah selesai."

                )}

            </div>

            ${

                imageUrl

                    ? `

                        <div

                            class="guardnet-source"

                        >

                            🖼️ Media dianalisis menggunakan OCR + Visual AI

                        </div>

                    `

                    : `

                        <div

                            class="guardnet-source"

                        >

                            📝 Teks dianalisis menggunakan Text AI

                        </div>

                    `

            }

            <div

                class="guardnet-meta"

            >

                <span>

                    Case ID:

                    ${escapeHtml(

                        result.case_id ||

                        "-"

                    )}

                </span>

                <span>

                    Content ID:

                    ${escapeHtml(

                        result.content_id ||

                        "-"

                    )}

                </span>

                <span>

                    Report ID:

                    ${escapeHtml(

                        result.report_id ||

                        "-"

                    )}

                </span>

            </div>

        </div>

        <div

            class="guardnet-footer"

        >

            GuardNet-AI • Deteksi Keamanan Digital

        </div>

    `;

    document.body.appendChild(

        popup

    );

    const closeButton =

        popup.querySelector(

            ".guardnet-close"

        );

    if (closeButton) {

        closeButton.addEventListener(

            "click",

            event => {

                event.preventDefault();

                event.stopPropagation();

                hideGuardNetResult();

            }

        );

    }

    // =================================================

    // NO AUTO HIDE

    // =================================================

    if (

        POPUP_DURATION > 0

    ) {

        popupTimer =

            setTimeout(

                () => {

                    hideGuardNetResult();

                },

                POPUP_DURATION

            );

    }

    console.log(

        "🛡️ GuardNet-AI Popup:",

        {

            risk,

            score,

            indicators,

            caseId:

                result.case_id,

            reportId:

                result.report_id

        }

    );

}

// =====================================================

// MESSAGE LISTENER

// =====================================================

function setupMessageListener() {

    if (

        messageListenerStarted

    ) {

        return;

    }

    messageListenerStarted =

        true;

    try {

        chrome.runtime.onMessage.addListener(

            (

                message,

                sender,

                sendResponse

            ) => {

                try {

                    if (!message) {

                        return;

                    }

                    // =================================

                    // FULL ANALYSIS

                    // =================================

                    if (

                        message.action ===

                        "analysisResult"

                    ) {

                        console.log(

                            "======================================"

                        );

                        console.log(

                            "🛡️ FULL ANALYSIS DITERIMA"

                        );

                        console.log(

                            "======================================"

                        );

                        if (

                            message.imageUrl

                        ) {

                            processingImages.delete(

                                message.imageUrl

                            );

                            pendingImages.delete(

                                message.imageUrl

                            );

                            processedImages.add(

                                message.imageUrl

                            );

                        }

                        if (

                            !message.success

                        ) {

                            console.error(

                                "[GuardNet-AI] Analysis Error:",

                                message.error

                            );

                            return;

                        }

                        const result =

                            message.result;

                        if (!result) {

                            return;

                        }

                        console.log(

                            "[GuardNet-AI] Full result:",

                            result

                        );

                        console.log(

                            "[GuardNet-AI] Analysis keys:",

                            result.analysis

                                ? Object.keys(result.analysis)

                                : []

                        );

                        console.log(

                            "[GuardNet-AI] OCR:",

                            result.ocr_text ||

                            result.analysis?.ocr ||

                            result.ocr

                        );

                        console.log(

                            "[GuardNet-AI] Evidence:",

                            result.evidence ||

                            result.analysis?.evidence ||

                            result.analysis?.evidence_fusion

                        );

                        if (

                            message.imageUrl &&

                            message.contentKey

                        ) {

                            mediaContentMap.set(

                                message.imageUrl,

                                message.contentKey

                            );

                        }

                        clearGuardNetLoading(

                            message.contentKey ||

                            result.contentKey ||

                            result.content_key ||

                            null

                        );                        console.log(

                            "[GuardNet-AI] STAGE RECEIVED:",

                            message.stage,

                            "RISK:",

                            result.risk_level,

                            "SCORE:",

                            result.score

                        );

                        handleAnalysisResult(

                            result,

                            message

                        );

                        if (

                            typeof sendResponse ===

                            "function"

                        ) {

                            sendResponse({

                                success:

                                    true

                            });

                        }

                        return true;

                    }

                    // =================================

                    // OCR RESULT

                    // =================================

                    if (

                        message.action ===

                        "ocrResult"

                    ) {

                        console.log(

                            "[GuardNet-AI] OCR result diterima."

                        );

                        if (

                            message.imageUrl

                        ) {

                            processingImages.delete(

                                message.imageUrl

                            );

                            pendingImages.delete(

                                message.imageUrl

                            );

                            processedImages.add(

                                message.imageUrl

                            );

                        }

                        if (
                            !message.success
                        ) {
                            console.error(
                                "[GuardNet-AI] OCR Error:",
                                 message.error
                        );

                        clearGuardNetLoading(
                             message.contentKey || null
                        );

                        return;
                    }

                        const result =

                            message.result;

                        if (!result) {

                            return;

                        }

                        handleAnalysisResult(

                            result,

                            message

                        );

                        if (

                            typeof sendResponse ===

                            "function"

                        ) {

                            sendResponse({

                                success:

                                    true

                            });

                        }

                        return true;

                    }

                    // =================================

                    // ANALYSIS ERROR

                    // =================================

                    if (

                        message.action ===

                        "analysisError"

                    ) {

                        console.error(

                            "[GuardNet-AI] Analysis error:",

                            message.error

                        );

                        return;

                    }

                } catch (error) {

                    console.error(

                        "[GuardNet-AI] Message listener error:",

                        error

                    );

                }

            }

        );

        console.log(

            "[GuardNet-AI] Message listener aktif."

        );

    } catch (error) {

        console.error(

            "[GuardNet-AI] Message listener gagal:",

            error

        );

    }

}

// =====================================================

// MUTATION OBSERVER

// =====================================================

function startObserver() {

    if (

        observerStarted

    ) {

        return;

    }

    if (

        !document.body

    ) {

        return;

    }

    observerStarted =

        true;

    try {

        const observer =

            new MutationObserver(

                mutations => {

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

                            !mutation.addedNodes ||

                            !mutation.addedNodes.length

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

                            const isContentNode =

                                element.matches?.(

                                    "article, img, video, [role='dialog']"

                                ) ||

                                element.querySelector?.(

                                    "article, img, video, [role='dialog']"

                                ) ||

                                element.closest?.(

                                    "article, [role='dialog']"

                                );

                            if (

                                isContentNode

                            ) {

                                shouldScan =

                                    true;

                                break;

                            }

                        }

                        if (

                            shouldScan

                        ) {

                            break;

                        }

                    }

                    if (

                        shouldScan

                    ) {

                        scheduleScan(

                            MUTATION_SCAN_DELAY

                        );

                    }

                }

            );

        observer.observe(

            document.body,

            {

                childList:

                    true,

                subtree:

                    true

            }

        );

        console.log(

            "[GuardNet-AI] MutationObserver aktif."

        );

    } catch (error) {

        observerStarted =

            false;

        console.error(

            "[GuardNet-AI] Observer error:",

            error

        );

    }

}

// =====================================================

// HISTORY API - INSTAGRAM SPA

// =====================================================

function setupHistoryListener() {

    try {

        const originalPushState =

            history.pushState;

        const originalReplaceState =

            history.replaceState;

        history.pushState =

            function () {

                const result =

                    originalPushState.apply(

                        this,

                        arguments

                    );

                setTimeout(

                    () => {

                        checkPageChange();

                        updateVisibleContent();

                        scheduleScan(

                            300

                        );

                    },

                    100

                );

                return result;

            };

        history.replaceState =

            function () {

                const result =

                    originalReplaceState.apply(

                        this,

                        arguments

                    );

                setTimeout(

                    () => {

                        checkPageChange();

                        updateVisibleContent();

                        scheduleScan(

                            300

                        );

                    },

                    100

                );

                return result;

            };

        window.addEventListener(

            "popstate",

            () => {

                checkPageChange();

                updateVisibleContent();

                scheduleScan(

                    300

                );

            }

        );

        console.log(

            "[GuardNet-AI] History listener aktif."

        );

    } catch (error) {

        console.error(

            "[GuardNet-AI] History listener error:",

            error

        );

    }

}

// =====================================================

// SCROLL

// =====================================================

function setupScrollListener() {

    window.addEventListener(

        "scroll",

        () => {

            // Popup langsung hilang dan invalidasi response lama.

            hideGuardNetResult();

            // Segera pindahkan identity/generation sebelum scan baru.

            updateVisibleContent();

            // Debounce singkat agar scroll cepat tetap responsif.

            scheduleScrollScan();

        },

        {

            passive:

                true

        }

    );

}

// =====================================================

// VISIBILITY

// =====================================================

function setupVisibilityListener() {

    document.addEventListener(

        "visibilitychange",

        () => {

            if (

                document.visibilityState ===

                "visible"

            ) {

                updateVisibleContent();

                scheduleScan(

                    300

                );

            }

        }

    );

}

// =====================================================

// PERIODIC PAGE CHECK

// =====================================================

function startPageCheck() {

    setInterval(

        () => {

            try {

                checkPageChange();

                updateVisibleContent();

            } catch (error) {

                console.error(

                    "[GuardNet-AI] Page check error:",

                    error

                );

            }

        },

        PAGE_CHECK_INTERVAL

    );

}

// =====================================================

// INITIAL SCAN

// =====================================================

function startInitialScan() {

    setTimeout(

        () => {

            try {

                updateVisibleContent();

                scanContent();

            } catch (error) {

                console.error(

                    "[GuardNet-AI] Initial scan error:",

                    error

                );

            }

        },

        INITIAL_SCAN_DELAY

    );

}

// =====================================================

// INITIALIZE

// =====================================================

function initializeGuardNet() {

    try {

        console.log(

            "=============================================="

        );

        console.log(

            "🛡️ GuardNet-AI FINAL CONTENT SCRIPT"

        );

        console.log(

            "Multimodal Detection: ENABLED"

        );

        console.log(

            "Image Detection: ENABLED"

        );

        console.log(

            "Video Detection: ENABLED"

        );

        console.log(

            "OCR: ENABLED"

        );

        console.log(

            "Visual AI: ENABLED"

        );

        console.log(

            "Text Analysis: ENABLED"

        );

        console.log(

            "Per-Content Risk Lock: ENABLED"

        );

        console.log(

            "Popup Auto Hide: DISABLED"

        );

        console.log(

            "=============================================="

        );

        lastPageUrl =

            window.location.href;

        currentContentKey =

            getMostVisibleContentKey();

        createPopupStyles();

        setupMessageListener();

        startObserver();

        setupHistoryListener();

        setupScrollListener();

        setupVisibilityListener();

        startPageCheck();

        startInitialScan();

        console.log(

            "[GuardNet-AI] Initialization selesai."

        );

    } catch (error) {

        console.error(

            "[GuardNet-AI] Initialization gagal:",

            error

        );

    }

}

// =====================================================

// START

// =====================================================

if (

    document.readyState ===

    "loading"

) {

    document.addEventListener(

        "DOMContentLoaded",

        initializeGuardNet,

        {

            once:

                true

        }

    );

} else {

    initializeGuardNet();

}

// =====================================================

// DEBUG API

// =====================================================

try {

    window.GuardNetAI = {

        getState:

            () => ({

                currentContentKey,

                currentBestRisk,

                currentBestScore,

                processedTexts:

                    processedTexts.size,

                processedImages:

                    processedImages.size,

                processingImages:

                    processingImages.size,

                processedVideos:

                    processedVideos.size,

                receivedResults:

                    receivedResults.size,

                contentLocks:

                    contentLocks.size,

                mediaContentMap:

                    mediaContentMap.size,

                url:

                    window.location.href

            }),

        scan:

            () => {

                scanContent();

            },

        reset:

            () => {

                resetForNewPage();

            },

        hidePopup:

            () => {

                hideGuardNetResult();

            }

    };

} catch (error) {

    console.warn(

        "[GuardNet-AI] Debug API gagal."

    );

}

// =====================================================

// END

// =====================================================

console.log(
    "🛡️ GuardNet-AI Content Script FINAL siap."

);