// =====================================================
// GUARDNET-AI BACKGROUND SERVICE WORKER
// FINAL STABLE VERSION - OCR VIDEO FRAME FIX
//
// TEXT
// IMAGE
// VIDEO FRAME
//   ↓
// /analyze-full
//   ↓
// CASE
//   ↓
// EVIDENCE
//   ↓
// REPORT
// =====================================================

 
const API_URL = "http://127.0.0.1:8000";

 

const REQUEST_TIMEOUT = 60000;

 

/**

 * Convert a canvas data URL directly into a Blob.

 * This avoids fetch(data:) and therefore removes a needless fetch failure path.

 */

function dataUrlToBlob(dataUrl) {

    if (typeof dataUrl !== "string" || !dataUrl.startsWith("data:")) {

        throw new Error("frameData bukan Data URL yang valid.");

    }

 

    const commaIndex = dataUrl.indexOf(",");

 

    if (commaIndex === -1) {

        throw new Error("Format Data URL frame tidak valid.");

    }

 

    const header = dataUrl.slice(0, commaIndex);

    const data = dataUrl.slice(commaIndex + 1);

 

    const mimeMatch = header.match(/^data:([^;,]+)/i);

    const mimeType = mimeMatch?.[1] || "image/jpeg";

 

    try {

        if (/;base64/i.test(header)) {

            const binary = atob(data);

            const bytes = new Uint8Array(binary.length);

 

            for (let i = 0; i < binary.length; i++) {

                bytes[i] = binary.charCodeAt(i);

            }

 

            return new Blob([bytes], { type: mimeType });

        }

 

        return new Blob(

            [decodeURIComponent(data)],

            { type: mimeType }

        );

    } catch (error) {

        throw new Error(

            `Gagal decode frame video: ${error.message}`

        );

    }

}

 

/**

 * Fetch an Instagram CDN image from the extension context.

 * credentials are omitted because the CDN URL already contains the

 * required signed/query parameters.

 */

async function fetchInstagramImage(imageUrl) {

    if (!imageUrl || typeof imageUrl !== "string") {

        throw new Error("URL gambar Instagram kosong.");

    }

 

    let response;

 

    try {

        response = await fetchWithTimeout(

            imageUrl,

            {

                method: "GET",

                credentials: "omit",

                cache: "no-store"

            },

            30000

        );

    } catch (error) {

        throw new Error(

            `Failed to fetch gambar Instagram CDN: ${error.message}`

        );

    }

 

    if (!response.ok) {

        throw new Error(

            `Gagal mengambil gambar Instagram. HTTP ${response.status}`

        );

    }

 

    const blob = await response.blob();

 

    if (!blob || !blob.size) {

        throw new Error("Gambar Instagram kosong.");

    }

 

    return blob;

}

 

 

 

console.log("🛡️ GuardNet-AI Background aktif");

 

 

 

// =====================================================

 

// FETCH WITH TIMEOUT

 

// =====================================================

 

 

 

async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT) {

 

    const controller = new AbortController();

 

 

 

    const timer = setTimeout(() => {

 

        controller.abort();

 

    }, timeout);

 

 

 

    try {

 

        return await fetch(url, {

 

            ...options,

 

            signal: controller.signal

 

        });

 

    } catch (error) {

 

        if (error.name === "AbortError") {

 

            throw new Error("Request ke backend timeout.");

 

        }

 

        throw error;

 

    } finally {

 

        clearTimeout(timer);

 

    }

 

}

 

 

 

// =====================================================

 

// SEND RESULT TO TAB

 

// =====================================================

 

 

 

async function sendResultToTab(tabId, action, payload) {

 

    if (tabId === undefined || tabId === null) {

 

        return;

 

    }

 

 

 

    try {

 

        await chrome.tabs.sendMessage(tabId, {

 

            action,

 

            ...payload

 

        });

 

    } catch (error) {

 

        console.warn(

 

            "GuardNet-AI: Gagal mengirim hasil ke tab:",

 

            error.message

 

        );

 

    }

 

}

 

 

 

// =====================================================

 

// MESSAGE LISTENER

 

// =====================================================

 

 

 

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

 

    console.log(

 

        "GuardNet-AI: Message diterima:",

 

        message?.action

 

    );

 

 

 

    const tabId = sender.tab?.id;

 

 

 

    // =============================================

 

    // TEXT

 

    // =============================================

 

 

 

    if (message?.action === "analyzeContent") {

 

        sendResponse({

 

            success: true,

 

            accepted: true

 

        });

 

 

 

        analyzeContent(

 

            message.text,

 

            message.url

 

        )

 

            .then(async (result) => {

 

                await sendResultToTab(

 

                    tabId,

 

                    "analysisResult",

 

                    {

 

                        success: true,

 

                        result,

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            })

 

            .catch(async (error) => {

 

                console.error(

 

                    "GuardNet-AI Text Error:",

 

                    error

 

                );

 

 

 

                await sendResultToTab(

 

                    tabId,

 

                    "analysisResult",

 

                    {

 

                        success: false,

 

                        error: error.message,

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            });

 

 

 

        return true;

 

    }

 

 

 

    // =============================================

 

    // IMAGE

 

    // =============================================

 

 

 

    if (message?.action === "ocrImage") {

 

        sendResponse({

 

            success: true,

 

            accepted: true

 

        });

 

 

 

        // -------------------------------------------------

 

        // PENTING:

 

        // Poster video tidak diproses sebagai URL CDN.

 

        // Video harus menggunakan frameData melalui videoFrame.

 

        // Ini mencegah "Failed to fetch" dari URL poster Instagram.

 

        // -------------------------------------------------

 

        if (message.sourceType === "video-poster") {

 

            console.log(

 

                "GuardNet-AI: video-poster diabaikan; gunakan videoFrame."

 

            );

 

 

 

            sendResultToTab(

 

                tabId,

 

                "ocrResult",

 

                {

 

                    success: false,

 

                    skipped: true,

 

                    error: "Video poster dilewati. Gunakan video frame.",

 

                    imageUrl: message.imageUrl,

 

                    contentKey: message.contentKey || null,

 

                    analysisGeneration: message.analysisGeneration ?? null

 

                }

 

            );

 

 

 

            return true;

 

        }

 

 

 

        analyzeImage(

 

            message.imageUrl,

 

            message.url,

 

            message.detectedText || ""

 

        )

 

            .then(async (result) => {

 

                await sendResultToTab(

 

                    tabId,

 

                    "ocrResult",

 

                    {

 

                        success: true,

 

                        result,

 

                        imageUrl: message.imageUrl,

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            })

 

            .catch(async (error) => {

 

                console.error(

 

                    "GuardNet-AI Image Error:",

 

                    error

 

                );

 

 

 

                await sendResultToTab(

 

                    tabId,

 

                    "ocrResult",

 

                    {

 

                        success: false,

 

                        error: error.message,

 

                        imageUrl: message.imageUrl,

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            });

 

 

 

        return true;

 

    }

 

 

 

    // =============================================

 

    // VIDEO FRAME

 

    // =============================================

 

 

 

    if (message?.action === "videoFrame") {

 

        sendResponse({

 

            success: true,

 

            accepted: true

 

        });

 

 

 

        analyzeVideoFrame(

 

            message.frameData,

 

            message.url,

 

            message.detectedText || ""

 

        )

 

            .then(async (result) => {

 

                await sendResultToTab(

 

                    tabId,

 

                    "ocrResult",

 

                    {

 

                        success: true,

 

                        result,

 

                        imageUrl: "video-frame",

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            })

 

            .catch(async (error) => {

 

                console.error(

 

                    "GuardNet-AI Video Frame Error:",

 

                    error

 

                );

 

 

 

                await sendResultToTab(

 

                    tabId,

 

                    "ocrResult",

 

                    {

 

                        success: false,

 

                        error: error.message,

 

                        imageUrl: "video-frame",

 

                        contentKey: message.contentKey || null,

 

                        analysisGeneration: message.analysisGeneration ?? null

 

                    }

 

                );

 

            });

 

 

 

        return true;

 

    }

 

 

 

    console.warn(

 

        "GuardNet-AI: Action tidak dikenal:",

 

        message?.action

 

    );

 

 

 

    return false;

 

});

 

 

 

// =====================================================

 

// TEXT ANALYSIS

 

// =====================================================

 

 

 

async function analyzeContent(textContent, pageUrl) {

 

    if (!textContent) {

 

        throw new Error("Teks content kosong.");

 

    }

 

 

 

    const params = new URLSearchParams();

 

 

 

    params.set("platform", "instagram");

 

    params.set("content_type", "text");

 

    params.set("content_url", pageUrl || "");

 

    params.set("detected_text", textContent);

 

 

 

    const response = await fetchWithTimeout(

 

        `${API_URL}/contents?${params.toString()}`,

 

        {

 

            method: "POST"

 

        }

 

    );

 

 

 

    if (!response.ok) {

 

        throw new Error(

 

            `Gagal menyimpan content. Status: ${response.status}`

 

        );

 

    }

 

 

 

    const data = await response.json();

 

 

 

    if (!data.content_id) {

 

        throw new Error(

 

            "Backend tidak mengembalikan content_id."

 

        );

 

    }

 

 

 

    return await analyzeSavedContent(data.content_id);

 

}

 

 

 

// =====================================================

 

// ANALYZE SAVED CONTENT

 

// =====================================================

 

 

 

async function analyzeSavedContent(contentId) {

 

    if (!contentId) {

 

        throw new Error("content_id tidak tersedia.");

 

    }

 

 

 

    const params = new URLSearchParams();

 

    params.set("content_id", contentId);

 

 

 

    const response = await fetchWithTimeout(

 

        `${API_URL}/analyze?${params.toString()}`,

 

        {

 

            method: "POST"

 

        }

 

    );

 

 

 

    if (!response.ok) {

 

        const errorText = await response.text();

 

 

 

        throw new Error(

 

            `Analisis gagal. Status: ${response.status}. ${errorText}`

 

        );

 

    }

 

 

 

    return await response.json();

 

}

 

 

 

// =====================================================

 

// IMAGE ANALYSIS

 

// =====================================================

 

 

 

async function analyzeImage(

 

    imageUrl,

 

    pageUrl,

 

    detectedText = ""

 

) {

 

    if (!imageUrl) {

 

        throw new Error("URL gambar kosong.");

 

    }

 

 

 

    console.log("======================================");

 

    console.log("🛡️ GUARDNET-AI: FULL IMAGE ANALYSIS");

 

    console.log("Image:", imageUrl);

 

    console.log("Context:", detectedText);

 

    console.log("======================================");

 

 

 

    // URL image hanya dipakai untuk image biasa.

 

    // Video TIDAK masuk ke sini.

 

    const imageResponse = await fetchWithTimeout(

 

        imageUrl,

 

        {},

 

        30000

 

    );

 

 

 

    if (!imageResponse.ok) {

 

        throw new Error(

 

            `Gagal mengambil gambar. Status: ${imageResponse.status}`

 

        );

 

    }

 

 

 

    const imageBlob = await imageResponse.blob();

 

 

 

    if (!imageBlob.size) {

 

        throw new Error("Gambar kosong.");

 

    }

 

 

 

    return await sendFullAnalysis(

 

        imageBlob,

 

        pageUrl,

 

        detectedText,

 

        "image",

 

        "guardnet-instagram-image.jpg"

 

    );

 

}

 

 

 

// =====================================================

 

// VIDEO FRAME ANALYSIS

 

// =====================================================

 

 

 

async function analyzeVideoFrame(

 

    frameData,

 

    pageUrl,

 

    detectedText = ""

 

) {

 

    if (!frameData) {

 

        throw new Error("Frame video kosong.");

 

    }

 

 

 

    console.log("======================================");

 

    console.log("🛡️ GUARDNET-AI: VIDEO FRAME ANALYSIS");

 

    console.log("Context:", detectedText);

 

    console.log("Frame type:", typeof frameData);

 

    console.log("======================================");

 

 

 

    // =================================================

 

    // DATA URL → BLOB

 

    // =================================================

 

    // Tidak melakukan fetch ke URL CDN Instagram.

 

    // frameData berasal langsung dari canvas content.js.

 

 

 

    let frameResponse;

 

 

 

    try {

 

        frameResponse = await fetch(frameData);

 

    } catch (error) {

 

        throw new Error(

 

            `Gagal membaca frame video: ${error.message}`

 

        );

 

    }

 

 

 

    if (!frameResponse.ok) {

 

        throw new Error(

 

            `Gagal membaca frame video. Status: ${frameResponse.status}`

 

        );

 

    }

 

 

 

    const frameBlob = await frameResponse.blob();

 

 

 

    if (!frameBlob.size) {

 

        throw new Error("Frame video kosong.");

 

    }

 

 

 

    console.log(

 

        "GuardNet-AI: Frame video berhasil menjadi blob:",

 

        frameBlob.size,

 

        "bytes"

 

    );

 

 

 

    return await sendFullAnalysis(

 

        frameBlob,

 

        pageUrl,

 

        detectedText,

 

        "video",

 

        "guardnet-instagram-video-frame.jpg"

 

    );

 

}

 

 

 

// =====================================================

 

// FULL ANALYSIS

 

// =====================================================

 

 

 

async function sendFullAnalysis(

 

    imageBlob,

 

    pageUrl,

 

    detectedText,

 

    contentType,

 

    filename

 

) {

 

    const formData = new FormData();

 

 

 

    formData.append(

 

        "file",

 

        imageBlob,

 

        filename

 

    );

 

 

 

    const params = new URLSearchParams();

 

 

 

    params.set("platform", "instagram");

 

    params.set("content_type", contentType);

 

    params.set("content_url", pageUrl || "");

 

    params.set("detected_text", detectedText || "");

 

 

 

    console.log(

 

        "🛡️ GuardNet-AI: POST /analyze-full"

 

    );

 

 

 

    console.log("Content Type:", contentType);

 

    console.log(

 

        "Detected Text Length:",

 

        (detectedText || "").length

 

    );

 

 

 

    const response = await fetchWithTimeout(

 

        `${API_URL}/analyze-full?${params.toString()}`,

 

        {

 

            method: "POST",

 

            body: formData

 

        },

 

        60000

 

    );

 

 

 

    let result;

 

 

 

    try {

 

        result = await response.json();

 

    } catch (error) {

 

        throw new Error(

 

            `Backend bukan JSON. HTTP ${response.status}`

 

        );

 

    }

 

 

 

    if (!response.ok) {

 

        throw new Error(

 

            result.detail ||

 

            result.message ||

 

            `Full analysis gagal. Status: ${response.status}`

 

        );

 

    }

 

 

 

    console.log("======================================");

 

    console.log("🛡️ HASIL FULL ANALYSIS GUARDNET-AI");

 

    console.log("Risk:", result.risk_level);

 

    console.log("Score:", result.score);

 

    console.log("Visual:", result.analysis?.visual);

 

    console.log("Text:", result.analysis?.text);

 

    console.log("Final:", result.analysis?.final);

 

    console.log("OCR:", result.ocr_text);

 

    console.log("Indicators:", result.detected_indicators);

 

    console.log("Evidence:", result.evidence);

 

    console.log("Case ID:", result.case_id);

 

    console.log("Content ID:", result.content_id);

 

    console.log("Report ID:", result.report_id);

 

    console.log("Report Status:", result.report_status);

 

    console.log("======================================");

 

 

 

    result.imageUrl =

 

        contentType === "video"

 

            ? "video-frame"

 

            : pageUrl || "";

 

 

 

    result.source_url = pageUrl || "";

 

 

 

    return result;

 

}