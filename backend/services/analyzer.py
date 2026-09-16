# ============================================================
# GUARDNET-AI
# TEXT ANALYZER
# FINAL - CONTEXT AWARE + PROMOTION AWARE + EXPLAINABLE
# ============================================================
# Analisis:
# - Caption
# - OCR
# - ASR
# - Komentar
# - Gambling terms
# - Promotion terms
# - Payment terms
# - Referral / entity
# - Context combination
#
# Prinsip:
# 1. Satu kata umum tidak langsung dianggap judi.
# 2. Kombinasi gambling + promotion/payment/registration sangat kuat.
# 3. Pola promosi dapat terdeteksi walau kata "judi" tidak muncul.
# 4. Konteks edukasi/anti-judi tidak dinaikkan menjadi HIGH.
# 5. Hasil selalu menjelaskan evidence yang benar-benar ditemukan.
# ============================================================

import re
from typing import Any, Dict, List


# ============================================================
# GAMBLING TERMS
# ============================================================

GAMBLING_TERMS = [
    "judi online", "judi daring", "judi", "perjudian",
    "slot online", "slot gacor", "slot", "slots",
    "casino online", "casino", "kasino online", "kasino",
    "togel online", "togel",
    "betting", "taruhan",
    "gacor", "scatter", "maxwin", "max win",
    "jackpot", "payout", "winrate", "win rate", "rtp",
    "free spin", "freespin", "spin gratis", "spin bonus",
    "permainan slot", "game slot", "mesin slot", "slot game",
    "mahjong ways", "mahjong slot", "mahjong",
    "pragmatic play", "pg soft", "pgsoft",
    "sweet bonanza", "starlight princess",
]


# ============================================================
# PROMOTION TERMS
# ============================================================

PROMOTIONAL_TERMS = [
    "bonus deposit", "bonus harian", "bonus mingguan", "bonus member",
    "bonus besar", "bonus", "promo", "promosi",
    "menang besar", "menang mudah", "menang terus", "kemenangan",
    "cuan besar", "cuan",
    "saldo gratis", "uang gratis", "hadiah besar",
    "deposit sekarang", "minimal deposit", "deposit murah", "deposit",
    "withdrawal", "withdraw", "pencairan",
    "daftar sekarang", "daftar", "registrasi", "register",
    "klik link", "klik disini", "klik di sini",
    "link alternatif", "link di bio", "link",
    "member baru", "new member", "cashback",
    "top up", "topup",
    "referral code", "kode referral", "kode referal", "referral",
    "ajak teman", "undang teman",
    "klaim bonus", "claim bonus", "hadiah", "reward",
    "akses sekarang", "main sekarang", "coba sekarang",
]


# ============================================================
# PAYMENT TERMS
# ============================================================

PAYMENT_TERMS = [
    "deposit", "withdrawal", "withdraw", "qris",
    "top up", "topup", "transfer", "rekening",
    "dana", "ovo", "gopay", "shopeepay",
    "bank", "ewallet", "e-wallet",
]


# ============================================================
# STRONG GAMBLING / PROMOTION PATTERNS
# ============================================================

STRONG_PATTERNS = [
    r"\bjudi\s+online\b",
    r"\bjudi\s+daring\b",
    r"\bslot\s+online\b",
    r"\bslot\s+gacor\b",
    r"\bslot\s+terpercaya\b",
    r"\bsitus\s+slot\b",
    r"\bsitus\s+judi\b",
    r"\blink\s+judi\b",
    r"\blink\s+slot\b",
    r"\bdaftar\s+slot\b",
    r"\bdaftar\s+judi\b",
    r"\bcasino\s+online\b",
    r"\bkasino\s+online\b",
    r"\btogel\s+online\b",
    r"\bsitus\s+togel\b",
    r"\bmain\s+slot\b",
    r"\bmain\s+judi\b",
    r"\bmain\s+togel\b",
    r"\bpromo\s+slot\b",
    r"\bpromo\s+judi\b",
    r"\bpromo\s+togel\b",
    r"\bbonus\s+slot\b",
    r"\bbonus\s+judi\b",
    r"\bbonus\s+togel\b",
    r"\bdeposit\s+slot\b",
    r"\bdeposit\s+judi\b",
    r"\bdeposit\s+togel\b",
    r"\bslot\s+gacor\s+maxwin\b",
    r"\brtp\s+gacor\b",
    r"\bwinrate\s+slot\b",
    r"\bjackpot\s+slot\b",
    r"\bpayout\s+slot\b",
    r"\bgame\s+slot\b",
    r"\bslot\s+game\b",
    r"\bpermainan\s+slot\b",
    r"\bmahjong\s+slot\b",
    r"\bfree\s*spin\b",
    r"\bfreespin\b",
]


# ============================================================
# PROMOTION CONTEXT PATTERNS
# ============================================================
# Ini penting untuk kasus:
# "slot" + "bonus" + "daftar"
# atau:
# "gacor" + "link" + "deposit"
# tanpa kata "judi".
# ============================================================

PROMOTION_CONTEXT_PATTERNS = [
    (r"\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b.*\b(bonus|promo|promosi)\b",
     "permainan judi + promosi"),
    (r"\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b.*\b(deposit|top\s*up)\b",
     "permainan judi + pembayaran"),
    (r"\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b.*\b(daftar|register|registrasi)\b",
     "permainan judi + pendaftaran"),
    (r"\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b.*\b(link|klik|bio)\b",
     "permainan judi + tautan"),
    (r"\b(bonus|promo|promosi)\b.*\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b",
     "promosi + permainan judi"),
    (r"\b(deposit|top\s*up)\b.*\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b",
     "pembayaran + permainan judi"),
    (r"\b(daftar|register|registrasi)\b.*\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b",
     "pendaftaran + permainan judi"),
    (r"\b(link|klik|bio)\b.*\b(slot|slots|gacor|scatter|maxwin|jackpot|rtp|casino|togel)\b",
     "tautan + permainan judi"),
    (r"\b(menang|menang besar|cuan)\b.*\b(slot|slots|gacor|casino|togel)\b",
     "klaim kemenangan + permainan judi"),
    (r"\b(slot|casino|togel)\b.*\b(menang|cuan|hadiah)\b",
     "permainan judi + klaim keuntungan"),
]


# ============================================================
# GAME / MULTIPLIER PATTERNS
# ============================================================

GAME_PATTERNS = [
    r"\bpengali\s+x?\d+\b",
    r"\bx\d+\s*(?:pengali|multiplier)?\b",
    r"\b\d+x\s*(?:pengali|multiplier)?\b",
    r"\bscatter\s+x?\d+\b",
    r"\bfree\s*spin\b",
    r"\bfreespin\b",
    r"\bbonus\s+x?\d+\b",
    r"\bmenang\s+x?\d+\b",
    r"\b\d+\s*x\s*(?:bonus|menang|kemenangan)\b",
]


# ============================================================
# ANTI GAMBLING / EDUCATIONAL CONTEXT
# ============================================================

ANTI_GAMBLING_PHRASES = [
    "bahaya judi online", "bahaya judi",
    "hindari judi online", "hindari judi",
    "jangan berjudi", "jangan percaya judi",
    "dilarang perjudian", "dilarang judi",
    "memberantas judi", "pemberantasan judi",
    "penindakan terhadap judi", "penindakan judi",
    "edukasi bahaya judi", "dampak judi",
    "kecanduan judi", "kerugian akibat judi",
    "stop judi online", "tolak judi online",
    "laporkan judi online", "lapor judi online",
]


# ============================================================
# SUSPICIOUS ENTITIES
# ============================================================

SUSPICIOUS_ENTITIES = [
    "bod14", "intan34", "danwd88", "nospola",
]

KNOWN_ENTITY_PATTERNS = [
    r"\bbod14\b", r"\bintan34\b", r"\bdanwd88\b", r"\bnospola\b",
]

GENERIC_CODE_PATTERN = (
    r"\b(?:kode|code|referral|referal)"
    r"(?:\s+(?:referral|referal))?"
    r"\s*[:\-]?\s*"
    r"([a-zA-Z]{2,15}\d{1,6})\b"
)

REFERRAL_PATTERNS = [
    r"\breferral\s+code\b",
    r"\breferral\b",
    r"\breferal\b",
    r"\bkode\s+referral\b",
    r"\bkode\s+referal\b",
    r"\bgunakan\s+kode\b",
    r"\bpakai\s+kode\b",
    r"\bkode\s+[a-zA-Z0-9]+\b",
]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text).lower()

    # Perbaikan OCR yang aman.
    typo_replacements = {
        "judi0nline": "judi online",
        "judi0nlin": "judi online",
        "sl0t": "slot",
        "sl0ts": "slots",
        "gac0r": "gacor",
        "gacorr": "gacor",
        "gaccor": "gacor",
        "scater": "scatter",
        "scattar": "scatter",
        "scatt er": "scatter",
        "maxwln": "maxwin",
        "maxw1n": "maxwin",
        "dep0sit": "deposit",
        "b0nus": "bonus",
        "pr0mo": "promo",
        "pr0mosi": "promosi",
        "reg1ster": "register",
        "reg1strasi": "registrasi",
        "ref er ral": "referral",
        "referr al": "referral",
        "fr33spin": "freespin",
    }

    for old, new in typo_replacements.items():
        text = text.replace(old, new)

    # Normalisasi pemisah umum OCR: "s l o t" -> "slot".
    text = re.sub(r"\bs\s*[-_.]?\s*l\s*[-_.]?\s*o\s*[-_.]?\s*t\b", "slot", text)
    text = re.sub(r"\bj\s*[-_.]?\s*u\s*[-_.]?\s*d\s*[-_.]?\s*i\b", "judi", text)

    # Spasi whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# TERM MATCHING
# ============================================================

def find_terms(text: str, terms: List[str]) -> List[str]:
    if not text:
        return []

    found = []
    spans = []

    for term in sorted(terms, key=len, reverse=True):
        pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        start, end = match.start(), match.end()
        if any(
            (start >= old_start and end <= old_end)
            or (old_start >= start and old_end <= end)
            for old_start, old_end in spans
        ):
            continue

        spans.append((start, end))
        found.append(match.group(0).lower())

    # Pertahankan urutan kemunculan.
    pairs = []
    for term in found:
        match = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)
        pairs.append((match.start() if match else 10**9, term))
    pairs.sort()
    return [term for _, term in pairs]


# ============================================================
# PATTERN MATCHING
# ============================================================

def find_pattern_matches(text: str, patterns: List[str]) -> List[str]:
    if not text:
        return []

    results = []
    for pattern in patterns:
        try:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = match.group(0).strip().lower()
                if value and value not in results:
                    results.append(value)
        except re.error:
            continue
    return results


def find_context_patterns(text: str) -> List[str]:
    if not text:
        return []

    results = []
    for pattern, label in PROMOTION_CONTEXT_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            if label not in results:
                results.append(label)
    return results


# ============================================================
# ENTITY
# ============================================================

def find_entities(raw_text: str, normalized_text: str) -> List[str]:
    found = []
    raw = str(raw_text or "").lower()

    for pattern in KNOWN_ENTITY_PATTERNS:
        for match in re.findall(pattern, raw, flags=re.IGNORECASE):
            value = str(match).lower()
            if value not in found:
                found.append(value)

    for match in re.finditer(GENERIC_CODE_PATTERN, raw, flags=re.IGNORECASE):
        if not match.groups():
            continue
        value = match.group(1).strip().lower()
        if value in {"abc123", "abc1234", "test123", "code123", "kode123"}:
            continue
        if value not in found:
            found.append(value)

    return found


# ============================================================
# SCORE
# ============================================================

def calculate_score(
    gambling_found: List[str],
    promotional_found: List[str],
    strong_found: List[str],
    payment_found: List[str],
    anti_found: List[str],
    entity_found: List[str],
    referral_found: List[str],
    game_found: List[str],
    context_found: List[str],
) -> float:
    gambling_count = len(gambling_found)
    promotion_count = len(promotional_found)
    payment_count = len(payment_found)
    strong_count = len(strong_found)
    entity_count = len(entity_found)
    referral_count = len(referral_found)
    game_count = len(game_found)
    context_count = len(context_found)

    # Score berbasis evidence, bukan sekadar jumlah kata.
    score = 0.0

    # Evidence gambling.
    if gambling_count:
        score += min(0.42, 0.18 * gambling_count)

    # Evidence promosi.
    if promotion_count:
        score += min(0.24, 0.08 * promotion_count)

    # Strong phrase.
    if strong_count:
        score += min(0.38, 0.30 + 0.04 * (strong_count - 1))

    # Konteks promosi judi tanpa harus ada kata "judi".
    if context_count:
        score += min(0.42, 0.26 + 0.06 * (context_count - 1))

    # Game/multiplier.
    if game_count:
        score += min(0.16, 0.08 * game_count)

    # Payment hanya sinyal penguat, bukan bukti judi sendirian.
    if payment_count:
        score += min(0.10, 0.05 * payment_count)

    # Referral/entity.
    if referral_count:
        score += 0.08
    if entity_count:
        score += min(0.10, 0.05 * entity_count)

    # Kombinasi sangat kuat.
    if gambling_count >= 1 and promotion_count >= 1:
        score = max(score, 0.78)

    if gambling_count >= 1 and payment_count >= 1:
        score = max(score, 0.82)

    if gambling_count >= 1 and promotion_count >= 1 and payment_count >= 1:
        score = max(score, 0.93)

    if context_count >= 1 and (promotion_count >= 1 or payment_count >= 1):
        score = max(score, 0.84)

    if context_count >= 2:
        score = max(score, 0.90)

    if strong_count >= 1:
        score = max(score, 0.90)

    if strong_count >= 2:
        score = max(score, 0.96)

    if entity_count >= 1 and gambling_count >= 1:
        score = max(score, 0.90)

    if entity_count >= 1 and referral_count >= 1:
        score = max(score, 0.80)

    # Anti-gambling hanya menurunkan jika tidak ada bukti promosi yang kuat.
    if anti_found and strong_count == 0 and context_count == 0:
        if gambling_count <= 1 and promotion_count <= 1:
            score = min(score, 0.20)

    return round(min(score, 0.99), 3)


# ============================================================
# INDICATORS
# ============================================================

def build_indicators(
    gambling_found: List[str],
    promotional_found: List[str],
    payment_found: List[str],
    strong_found: List[str],
    entity_found: List[str],
    referral_found: List[str],
    game_found: List[str],
    context_found: List[str],
) -> List[str]:
    indicators = []

    for group in (
        gambling_found,
        promotional_found,
        payment_found,
        strong_found,
        context_found,
        referral_found,
        game_found,
    ):
        for item in group:
            item = str(item).strip()
            if item and item not in indicators:
                indicators.append(item)

    for entity in entity_found:
        label = f"entity:{entity}"
        if label not in indicators:
            indicators.append(label)

    return indicators


# ============================================================
# DESCRIPTION
# ============================================================

def build_description(
    risk_level: str,
    gambling_found: List[str],
    promotional_found: List[str],
    payment_found: List[str],
    entity_found: List[str],
    referral_found: List[str],
    anti_found: List[str],
    context_found: List[str],
) -> str:
    if risk_level == "high":
        if context_found and not gambling_found:
            return (
                "Terdapat pola promosi permainan judi online berdasarkan "
                "kombinasi indikator permainan, promosi, pendaftaran, "
                "tautan, pembayaran, atau klaim keuntungan."
            )
        return (
            "Terdapat indikasi kuat promosi atau aktivitas judi online "
            "berdasarkan kombinasi istilah perjudian dan indikator "
            "promosi, pembayaran, referral, atau pola kontekstual."
        )

    if risk_level == "medium":
        return (
            "Terdapat indikator yang mencurigakan dan berkaitan dengan "
            "perjudian atau promosi, tetapi bukti belum cukup kuat untuk "
            "dikategorikan sebagai risiko tinggi."
        )

    if anti_found:
        return (
            "Teks berkaitan dengan judi tetapi terdeteksi dalam konteks "
            "edukasi, peringatan, pencegahan, atau pelaporan."
        )

    if promotional_found:
        return (
            "Ditemukan istilah promosi, tetapi belum terdapat konteks "
            "yang cukup untuk mengaitkannya dengan judi online."
        )

    if entity_found:
        return (
            "Ditemukan entity atau kode yang mencurigakan, tetapi belum "
            "terdapat bukti cukup untuk mengaitkannya dengan judi online."
        )

    return "Tidak ditemukan indikasi kuat aktivitas judi online."


# ============================================================
# MAIN ANALYZER
# ============================================================

def analyze_text(text: Any) -> Dict[str, Any]:
    raw_text = str(text or "")
    normalized = normalize_text(raw_text)

    empty_evidence = {
        "gambling_terms": [],
        "promotional_terms": [],
        "strong_patterns": [],
        "payment_terms": [],
        "suspicious_entities": [],
        "referral_patterns": [],
        "game_patterns": [],
        "promotion_context": [],
        "anti_gambling_terms": [],
    }

    if not normalized:
        return {
            "status": "success",
            "risk_level": "low",
            "score": 0.0,
            "detected_indicators": [],
            "description": "Tidak ditemukan teks untuk dianalisis.",
            "evidence": empty_evidence,
            "normalized_text": "",
        }

    gambling_found = find_terms(normalized, GAMBLING_TERMS)
    promotional_found = find_terms(normalized, PROMOTIONAL_TERMS)
    strong_found = find_pattern_matches(normalized, STRONG_PATTERNS)
    payment_found = find_terms(normalized, PAYMENT_TERMS)
    anti_found = find_terms(normalized, ANTI_GAMBLING_PHRASES)
    entity_found = find_entities(raw_text, normalized)
    referral_found = find_pattern_matches(normalized, REFERRAL_PATTERNS)
    game_found = find_pattern_matches(normalized, GAME_PATTERNS)
    context_found = find_context_patterns(normalized)

    score = calculate_score(
        gambling_found=gambling_found,
        promotional_found=promotional_found,
        strong_found=strong_found,
        payment_found=payment_found,
        anti_found=anti_found,
        entity_found=entity_found,
        referral_found=referral_found,
        game_found=game_found,
        context_found=context_found,
    )

    if score >= 0.75:
        risk_level = "high"
    elif score >= 0.35:
        risk_level = "medium"
    else:
        risk_level = "low"

    indicators = build_indicators(
        gambling_found=gambling_found,
        promotional_found=promotional_found,
        payment_found=payment_found,
        strong_found=strong_found,
        entity_found=entity_found,
        referral_found=referral_found,
        game_found=game_found,
        context_found=context_found,
    )

    description = build_description(
        risk_level=risk_level,
        gambling_found=gambling_found,
        promotional_found=promotional_found,
        payment_found=payment_found,
        entity_found=entity_found,
        referral_found=referral_found,
        anti_found=anti_found,
        context_found=context_found,
    )

    return {
        "status": "success",
        "risk_level": risk_level,
        "score": score,
        "detected_indicators": indicators,
        "description": description,
        "evidence": {
            "gambling_terms": gambling_found,
            "promotional_terms": promotional_found,
            "strong_patterns": strong_found,
            "payment_terms": payment_found,
            "suspicious_entities": entity_found,
            "referral_patterns": referral_found,
            "game_patterns": game_found,
            "promotion_context": context_found,
            "anti_gambling_terms": anti_found,
        },
        "normalized_text": normalized,
    }
