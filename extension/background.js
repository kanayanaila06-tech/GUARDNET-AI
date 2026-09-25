'use strict';

// ============================================================
// GUARDNET-AI BACKGROUND V3
// FAST + FULL ASYNC
// ============================================================
// Alur:
//
// content.js
//    ↓
// background.js
//    ↓
// /analyze-fast
//    ↓
// popup FAST
//    ↓
// LOW  → selesai
// MEDIUM/HIGH → /analyze-full di background
//
// FULL TIDAK MENAHAN HASIL FAST.
// ============================================================

const API_URL = 'http://127.0.0.1:8000';

const FAST_TIMEOUT = 8000;
const FULL_TIMEOUT = 45000;
const IMAGE_TIMEOUT = 8000;

const activeJobs = new Set();

// Cache download gambar yang sedang berlangsung / sudah selesai.
// Tujuannya mencegah image URL yang sama di-download berkali-kali.
const imageBlobCache = new Map();

// ============================================================
// FETCH WITH TIMEOUT
// ============================================================

function fetchWithTimeout(url, options = {}, timeout = FULL_TIMEOUT) {
    const controller = new AbortController();

    const timer = setTimeout(() => {
        controller.abort();
    }, timeout);

    return fetch(url, {
        ...options,
        signal: controller.signal
    })
        .catch(error => {
            if (error.name === 'AbortError') {
                throw new Error('Backend timeout.');
            }

            throw error;
        })
        .finally(() => {
            clearTimeout(timer);
        });
}


// ============================================================
// JSON FETCH
// ============================================================

async function jsonFetch(
    url,
    options = {},
    timeout = FULL_TIMEOUT
) {
    const response = await fetchWithTimeout(
        url,
        options,
        timeout
    );

    const raw = await response.text();

    let data = {};

    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        throw new Error(
            `Backend bukan JSON (HTTP ${response.status}).`
        );
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.message ||
            `HTTP ${response.status}`
        );
    }

    return data;
}


// ============================================================
// SEND RESULT TO CONTENT.JS
// ============================================================

async function sendToTab(
    tabId,
    action,
    payload = {}
) {
    if (tabId == null) {
        return;
    }

    try {
        await chrome.tabs.sendMessage(
            tabId,
            {
                action,
                ...payload
            }
        );
    } catch (error) {
        console.warn(
            '[GuardNet-AI] sendToTab:',
            error.message
        );
    }
}


// ============================================================
// DATA URL → BLOB
// ============================================================

function dataUrlToBlob(dataUrl) {
    if (
        typeof dataUrl !== 'string' ||
        !dataUrl.startsWith('data:')
    ) {
        throw new Error(
            'Frame video tidak valid.'
        );
    }

    const comma = dataUrl.indexOf(',');

    if (comma < 0) {
        throw new Error(
            'Data URL frame rusak.'
        );
    }

    const header = dataUrl.slice(
        0,
        comma
    );

    const data = dataUrl.slice(
        comma + 1
    );

    const mime =
        (
            header.match(
                /^data:([^;,]+)/i
            ) || []
        )[1] ||
        'image/jpeg';

    if (
        /;base64/i.test(header)
    ) {
        const binary = atob(data);

        const bytes =
            new Uint8Array(
                binary.length
            );

        for (
            let i = 0;
            i < binary.length;
            i++
        ) {
            bytes[i] =
                binary.charCodeAt(i);
        }

        return new Blob(
            [bytes],
            {
                type: mime
            }
        );
    }

    return new Blob(
        [
            decodeURIComponent(data)
        ],
        {
            type: mime
        }
    );
}


// ============================================================
// DOWNLOAD IMAGE
// ============================================================

async function getImageBlob(
    imageUrl
) {
    if (!imageUrl) {
        throw new Error(
            'URL gambar kosong.'
        );
    }

    // --------------------------------------------------------
    // Jika image sedang/sudah di-download, gunakan promise
    // yang sama.
    // --------------------------------------------------------

    if (
        imageBlobCache.has(imageUrl)
    ) {
        return imageBlobCache.get(
            imageUrl
        );
    }

    const promise =
        (async () => {
            const response =
                await fetchWithTimeout(
                    imageUrl,
                    {
                        cache: 'force-cache',
                        credentials: 'omit'
                    },
                    IMAGE_TIMEOUT
                );

            if (!response.ok) {
                throw new Error(
                    `Gambar HTTP ${response.status}`
                );
            }

            const blob =
                await response.blob();

            if (
                !blob ||
                !blob.size
            ) {
                throw new Error(
                    'Gambar kosong.'
                );
            }

            return blob;
        })();

    imageBlobCache.set(
        imageUrl,
        promise
    );

    try {
        return await promise;
    } catch (error) {
        // Kalau gagal, hapus cache supaya
        // request berikutnya masih bisa mencoba lagi.
        imageBlobCache.delete(
            imageUrl
        );

        throw error;
    }
}


// ============================================================
// LIMIT CACHE
// ============================================================

function cleanupImageCache() {
    const MAX_CACHE = 30;

    if (
        imageBlobCache.size <=
        MAX_CACHE
    ) {
        return;
    }

    const removeCount =
        imageBlobCache.size -
        MAX_CACHE;

    let count = 0;

    for (
        const key of imageBlobCache.keys()
    ) {
        imageBlobCache.delete(key);

        count++;

        if (
            count >= removeCount
        ) {
            break;
        }
    }
}


// ============================================================
// CALL ANALYSIS ENDPOINT
// ============================================================

async function callAnalysis(
    endpoint,
    blob,
    message,
    contentType,
    timeout
) {
    if (!blob) {
        throw new Error(
            'Media kosong.'
        );
    }

    const form =
        new FormData();

    form.append(
        'file',
        blob,
        contentType === 'video'
            ? 'guardnet-frame.jpg'
            : 'guardnet-image.jpg'
    );

    const params =
        new URLSearchParams({
            platform:
                'instagram',

            content_type:
                contentType,

            content_url:
                message.url || '',

            detected_text:
                String(
                    message.detectedText ||
                    ''
                ).slice(
                    0,
                    12000
                )
        });

    return jsonFetch(
        `${API_URL}${endpoint}?${params.toString()}`,
        {
            method: 'POST',
            body: form
        },
        timeout
    );
}


// ============================================================
// SEND FAST RESULT
// ============================================================

async function sendFastResult(
    tabId,
    message,
    result,
    type
) {
    await sendToTab(
        tabId,
        'ocrResult',
        {
            success: true,

            result,

            contentKey:
                message.contentKey ||
                null,

            analysisGeneration:
                message.analysisGeneration ??
                null,

            imageUrl:
                message.imageUrl ||
                '',

            stage:
                'fast',

            mediaType:
                type
        }
    );
}


// ============================================================
// SEND FULL RESULT
// ============================================================

async function sendFullResult(
    tabId,
    message,
    result,
    type
) {
    await sendToTab(
        tabId,
        'ocrResult',
        {
            success: true,

            result,

            contentKey:
                message.contentKey ||
                null,

            analysisGeneration:
                message.analysisGeneration ??
                null,

            imageUrl:
                message.imageUrl ||
                '',

            stage:
                'full',

            mediaType:
                type
        }
    );
}


// ============================================================
// RUN MEDIA JOB
// ============================================================

async function runMediaJob(
    message,
    tabId,
    type
) {
    const contentKey =
        String(
            message.contentKey ||
            ''
        );

    if (!contentKey) {
        console.warn(
            '[GuardNet-AI] Media job dibatalkan: contentKey kosong.'
        );

        return;
    }

    // --------------------------------------------------------
    // Satu konten = satu FAST job aktif.
    // --------------------------------------------------------

    const mediaIdentity =
        type === 'video'
            ? `video|${contentKey}`
            : `image|${contentKey}|${message.imageUrl || ''}`;

    if (
        activeJobs.has(
            mediaIdentity
        )
    ) {
        console.log(
            '[GuardNet-AI] Duplicate job dilewati:',
            mediaIdentity
        );

        return;
    }

    activeJobs.add(
        mediaIdentity
    );

    const startedAt =
        performance.now();

    console.log(
        '[GuardNet-AI] FAST START:',
        {
            contentKey,
            type
        }
    );

    try {

        // ====================================================
        // 1. AMBIL MEDIA
        // ====================================================

        let blob;

        if (
            type === 'video'
        ) {
            blob =
                dataUrlToBlob(
                    message.frameData
                );
        } else {
            blob =
                await getImageBlob(
                    message.imageUrl
                );
        }

        const mediaReadyAt =
            performance.now();

        console.log(
            '[GuardNet-AI] MEDIA READY:',
            `${(
                mediaReadyAt -
                startedAt
            ).toFixed(0)} ms`
        );


        // ====================================================
        // 2. FAST ANALYSIS
        // ====================================================

        const fastResult =
            await callAnalysis(
                '/analyze-fast',
                blob,
                message,
                type,
                FAST_TIMEOUT
            );

        const fastFinishedAt =
            performance.now();

        const fastRisk =
            String(
                fastResult?.risk_level ||
                'low'
            )
                .trim()
                .toLowerCase();

        console.log(
            '[GuardNet-AI] FAST DONE:',
            {
                contentKey,

                risk:
                    fastRisk,

                totalMs:
                    (
                        fastFinishedAt -
                        startedAt
                    ).toFixed(0),

                analysisMs:
                    (
                        fastFinishedAt -
                        mediaReadyAt
                    ).toFixed(0)
            }
        );


        // ====================================================
        // 3. KIRIM HASIL FAST KE POPUP
        // ====================================================

        await sendFastResult(
            tabId,
            message,
            fastResult,
            type
        );


        // ====================================================
        // 4. LOW = SELESAI
        // ====================================================

        if (
            fastRisk !== 'medium' &&
            fastRisk !== 'high'
        ) {
            console.log(
                '[GuardNet-AI] LOW → FULL dilewati:',
                contentKey
            );

            return;
        }


        // ====================================================
        // 5. MEDIUM/HIGH → FULL
        // ====================================================
        //
        // FAST sudah dikirim ke popup.
        // Sekarang FULL berjalan sebagai proses lanjutan.
        // Popup tidak perlu menunggu FULL.
        // ====================================================

        console.log(
            '[GuardNet-AI] FULL START:',
            {
                contentKey,
                risk: fastRisk
            }
        );

        try {

            const fullStartedAt =
                performance.now();

            const fullResult =
                await callAnalysis(
                    '/analyze-full',
                    blob,
                    message,
                    type,
                    FULL_TIMEOUT
                );

            const fullFinishedAt =
                performance.now();

            console.log(
                '[GuardNet-AI] FULL DONE:',
                {
                    contentKey,

                    risk:
                        fullResult?.risk_level ||
                        fullResult?.analysis?.final?.risk_level ||
                        'unknown',

                    fullMs:
                        (
                            fullFinishedAt -
                            fullStartedAt
                        ).toFixed(0)
                }
            );

            await sendFullResult(
                tabId,
                message,
                fullResult,
                type
            );

        } catch (fullError) {

            // ------------------------------------------------
            // FAST tetap dianggap valid.
            // Jangan menghapus hasil FAST hanya karena FULL
            // gagal/timeout.
            // ------------------------------------------------

            console.error(
                '[GuardNet-AI] FULL gagal:',
                fullError
            );

            await sendToTab(
                tabId,
                'ocrResult',
                {
                    success: false,

                    error:
                        fullError.message ||
                        'Analisis lanjutan gagal.',

                    contentKey:
                        contentKey,

                    analysisGeneration:
                        message.analysisGeneration ??
                        null,

                    imageUrl:
                        message.imageUrl ||
                        '',

                    stage:
                        'full',

                    fastAvailable:
                        true
                }
            );
        }

    } catch (error) {

        console.error(
            '[GuardNet-AI] FAST gagal:',
            error
        );

        await sendToTab(
            tabId,
            'ocrResult',
            {
                success: false,

                error:
                    error.message ||
                    'Analisis gagal.',

                contentKey:
                    contentKey,

                analysisGeneration:
                    message.analysisGeneration ??
                    null,

                imageUrl:
                    message.imageUrl ||
                    '',

                stage:
                    'fast'
            }
        );

    } finally {

        activeJobs.delete(
            mediaIdentity
        );

        cleanupImageCache();

        console.log(
            '[GuardNet-AI] JOB FINISH:',
            contentKey
        );
    }
}


// ============================================================
// TEXT-ONLY ANALYSIS
// ============================================================

async function runTextJob(
    message,
    tabId
) {
    const text =
        String(
            message.text ||
            ''
        ).trim();

    if (!text) {
        throw new Error(
            'Teks kosong.'
        );
    }

    const params =
        new URLSearchParams({
            platform:
                'instagram',

            content_type:
                'text',

            content_url:
                message.url ||
                '',

            detected_text:
                text.slice(
                    0,
                    12000
                )
        });

    const content =
        await jsonFetch(
            `${API_URL}/contents?${params.toString()}`,
            {
                method: 'POST'
            },
            10000
        );

    if (
        !content.content_id
    ) {
        throw new Error(
            'Backend tidak mengembalikan content_id.'
        );
    }

    return jsonFetch(
        `${API_URL}/analyze?content_id=${encodeURIComponent(
            content.content_id
        )}`,
        {
            method: 'POST'
        },
        15000
    );
}


// ============================================================
// EXTENSION INSTALLED
// ============================================================

chrome.runtime.onInstalled.addListener(() => {
    console.log(
        '[GuardNet-AI] Extension terpasang / diperbarui.'
    );
});


// ============================================================
// MESSAGE HANDLER
// ============================================================

chrome.runtime.onMessage.addListener(
    (
        message,
        sender,
        sendResponse
    ) => {

        if (
            !message ||
            !message.action
        ) {
            return false;
        }

        const tabId =
            sender.tab?.id;


        // ====================================================
        // PING
        // ====================================================

        if (
            message.action === 'PING'
        ) {
            sendResponse({
                success: true,
                active: true
            });

            return true;
        }


        // ====================================================
        // GET STATUS
        // ====================================================

        if (
            message.action ===
            'GET_STATUS'
        ) {
            sendResponse({
                success: true,
                active: true
            });

            return true;
        }


        // ====================================================
        // IMAGE
        // ====================================================

        if (
            message.action ===
            'ocrImage'
        ) {

            // ACK langsung.
            sendResponse({
                success: true,
                accepted: true
            });

            // Jangan await di listener.
            // Job berjalan asynchronous.
            runMediaJob(
                message,
                tabId,
                'image'
            );

            return true;
        }


        // ====================================================
        // VIDEO FRAME
        // ====================================================

        if (
            message.action ===
            'videoFrame'
        ) {

            sendResponse({
                success: true,
                accepted: true
            });

            runMediaJob(
                message,
                tabId,
                'video'
            );

            return true;
        }


        // ====================================================
        // TEXT ANALYSIS
        // ====================================================

        if (
            message.action ===
            'analyzeContent'
        ) {

            sendResponse({
                success: true,
                accepted: true
            });

            runTextJob(
                message,
                tabId
            )
                .then(
                    result =>
                        sendToTab(
                            tabId,
                            'analysisResult',
                            {
                                success: true,

                                result,

                                contentKey:
                                    message.contentKey ||
                                    null,

                                analysisGeneration:
                                    message.analysisGeneration ??
                                    null,

                                stage:
                                    'full'
                            }
                        )
                )
                .catch(
                    error =>
                        sendToTab(
                            tabId,
                            'analysisResult',
                            {
                                success: false,

                                error:
                                    error.message ||
                                    'Analisis teks gagal.',

                                contentKey:
                                    message.contentKey ||
                                    null,

                                analysisGeneration:
                                    message.analysisGeneration ??
                                    null,

                                stage:
                                    'full'
                            }
                        )
                );

            return true;
        }

        return false;
    }
);


// ============================================================
// START
// ============================================================

console.log(
    '[GuardNet-AI] Background V3 FAST OPTIMIZED aktif.'
);