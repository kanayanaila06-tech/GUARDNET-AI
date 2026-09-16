# ============================================================
# GUARDNET-AI PAYMENT SERVICE - FINAL
# ============================================================
#
# Fungsi:
# - Generate payment hash
# - Generate image hash
# - Normalize payment data
# - Detect QR / QRIS
# - Parse QRIS EMV payload
# - Validate QRIS CRC
# - Detect acquirer / provider
# - Detect bank / e-wallet
# - Detect nomor rekening / nomor HP
# - Detect nominal pembayaran
# - Build payment evidence
# - Calculate payment evidence score
# - Verify payment evidence
#
# CATATAN:
# CRC valid hanya membuktikan integritas payload QR.
# CRC TIDAK membuktikan kepemilikan merchant.
#
# QRIS:
# - NMID disimpan sebagai NMID, BUKAN nomor rekening.
# - Acquirer identifier disimpan secara terpisah.
# - Destination bank tidak disimpulkan dari NMID/acquirer.
# ============================================================

import hashlib
import re
from typing import Optional, Dict, List, Any

import cv2
import numpy as np


# ============================================================
# QRIS CONSTANTS
# ============================================================

QRIS_GUI = "ID.CO.QRIS"
QRIS_AID = "A000000677010111"

TAG_PAYLOAD_FORMAT = "00"
TAG_POINT_OF_INITIATION = "01"
TAG_MERCHANT_ACCOUNT = "26"
TAG_MERCHANT_CATEGORY = "52"
TAG_TRANSACTION_CURRENCY = "53"
TAG_TRANSACTION_AMOUNT = "54"
TAG_COUNTRY = "58"
TAG_MERCHANT_NAME = "59"
TAG_MERCHANT_CITY = "60"
TAG_CRC = "63"


# ============================================================
# PAYMENT STATUS
# ============================================================

STATUS_DETECTED = "detected"
STATUS_UNVERIFIED = "unverified"
STATUS_MATCHED = "matched"
STATUS_CONFLICT = "conflict"
STATUS_INVALID = "invalid"


# ============================================================
# ACQUIRER MAPPING
# ============================================================

ACQUIRER_MAP = {
    "COM.GO-JEK.WWW": "GO-JEK",
}


def identify_acquirer(
    identifier: Optional[str],
) -> Optional[str]:
    """
    Mengubah acquirer identifier menjadi nama provider.

    Jika identifier belum dikenali, return None.
    Identifier asli tetap disimpan sebagai evidence.
    """

    if not identifier:
        return None

    normalized = str(identifier).strip().upper()

    return ACQUIRER_MAP.get(normalized)


# ============================================================
# HASH UTILITIES
# ============================================================

def normalize_payment_data(
    payment_data: str,
) -> str:

    if not payment_data:
        return ""

    data = str(payment_data).strip().lower()
    data = re.sub(r"\s+", "", data)

    return data


def generate_payment_hash(
    data: str,
) -> str:

    normalized_data = normalize_payment_data(data)

    if not normalized_data:
        return ""

    return hashlib.sha256(
        normalized_data.encode("utf-8")
    ).hexdigest()


def generate_image_hash(
    image_bytes: bytes,
) -> str:

    if not image_bytes:
        return ""

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# ============================================================
# CRC-16 / CCITT-FALSE
# ============================================================

def calculate_crc16_ccitt_false(
    data: str,
) -> str:

    crc = 0xFFFF

    for byte in data.encode("utf-8"):

        crc ^= byte << 8

        for _ in range(8):

            if crc & 0x8000:

                crc = (
                    (crc << 1) ^ 0x1021
                ) & 0xFFFF

            else:

                crc = (
                    crc << 1
                ) & 0xFFFF

    return f"{crc:04X}"


def validate_qr_crc(
    payload: str,
) -> Dict[str, Any]:

    if not payload:

        return {
            "available": False,
            "valid": False,
            "expected_crc": "",
            "actual_crc": "",
        }

    payload = str(payload).strip()

    crc_match = re.search(
        r"6304([0-9A-Fa-f]{4})$",
        payload,
    )

    if not crc_match:

        return {
            "available": False,
            "valid": False,
            "expected_crc": "",
            "actual_crc": "",
        }

    actual_crc = (
        crc_match.group(1)
        .upper()
    )

    crc_input = payload[:-4]

    expected_crc = (
        calculate_crc16_ccitt_false(
            crc_input
        )
    )

    return {
        "available": True,
        "valid": actual_crc == expected_crc,
        "expected_crc": expected_crc,
        "actual_crc": actual_crc,
    }


# ============================================================
# EMVCo TLV PARSER
# ============================================================

def parse_emv_tlv(
    payload: str,
) -> Dict[str, Any]:

    result = {
        "success": False,
        "fields": {},
        "errors": [],
    }

    if not payload:

        result["errors"].append(
            "Payload QR kosong."
        )

        return result

    payload = str(payload).strip()

    index = 0
    fields = {}

    while index < len(payload):

        if index + 4 > len(payload):

            result["errors"].append(
                f"Payload berhenti pada posisi {index}."
            )

            break

        tag = payload[
            index:index + 2
        ]

        length_text = payload[
            index + 2:index + 4
        ]

        if not length_text.isdigit():

            result["errors"].append(
                f"Length tag {tag} tidak valid."
            )

            break

        length = int(length_text)

        start = index + 4
        end = start + length

        if end > len(payload):

            result["errors"].append(
                f"Value tag {tag} melebihi panjang payload."
            )

            break

        value = payload[
            start:end
        ]

        fields[tag] = value

        index = end

    result["fields"] = fields

    result["success"] = (
        index == len(payload)
        and len(fields) > 0
    )

    return result


# ============================================================
# QRIS MERCHANT ACCOUNT INFORMATION
# ============================================================

def extract_qris_merchant_account(
    fields: Dict[str, str],
) -> Dict[str, Any]:
    """
    Mencari Merchant Account Information tag 26-51.

    Output:
    - GUI
    - NMID
    - merchant PAN
    - acquirer
    - acquirer identifier
    """

    result = {
        "detected": False,
        "tag": None,
        "gui": None,
        "merchant_pan": None,
        "nmid": None,
        "acquirer": None,
        "acquirer_identifier": None,
        "fields": {},
    }

    merchant_accounts = []

    # ========================================================
    # SCAN MERCHANT ACCOUNT INFORMATION
    # ========================================================

    for tag in range(26, 52):

        tag_key = f"{tag:02d}"

        value = fields.get(tag_key)

        if not value:
            continue

        nested = parse_emv_tlv(value)

        if not nested.get("success"):
            continue

        nested_fields = nested.get(
            "fields",
            {},
        )

        gui = nested_fields.get("00")

        if not gui:
            continue

        gui_upper = (
            str(gui)
            .strip()
            .upper()
        )

        account_item = {
            "tag": tag_key,
            "gui": gui,
            "fields": nested_fields,
        }

        merchant_accounts.append(
            account_item
        )

        # ====================================================
        # QRIS MERCHANT ACCOUNT
        # ====================================================

        if (
            QRIS_GUI in gui_upper
            or QRIS_AID in value.upper()
        ):

            result["detected"] = True

            result["tag"] = tag_key

            result["gui"] = gui

            result["fields"] = nested_fields

            # ------------------------------------------------
            # QRIS NMID
            # ------------------------------------------------
            #
            # Pada payload pengujian:
            #
            # 51
            # 00 = ID.CO.QRIS.WWW
            # 02 = ID1024351844245
            #
            # Maka subtag 02 diprioritaskan.
            # ------------------------------------------------

            result["nmid"] = (
                nested_fields.get("02")
                or nested_fields.get("01")
            )

            # ------------------------------------------------
            # Merchant PAN / identifier fallback
            # ------------------------------------------------

            result["merchant_pan"] = (
                nested_fields.get("01")
                or nested_fields.get("02")
            )

            continue

        # ====================================================
        # CANDIDATE ACQUIRER
        # ====================================================

        if not result["acquirer_identifier"]:

            identifier = (
                str(gui).strip()
            )

            result[
                "acquirer_identifier"
            ] = identifier

            mapped = identify_acquirer(
                identifier
            )

            if mapped:

                result["acquirer"] = mapped

    # ========================================================
    # FALLBACK ACQUIRER
    # ========================================================
    #
    # Contoh payload:
    #
    # 26...
    # 00 = COM.GO-JEK.WWW
    #
    # 51...
    # 00 = ID.CO.QRIS.WWW
    #
    # Maka:
    # acquirer_identifier = COM.GO-JEK.WWW
    # acquirer = GO-JEK
    # ========================================================

    if result["detected"]:

        for account in merchant_accounts:

            gui = account.get("gui")

            if not gui:
                continue

            mapped = identify_acquirer(
                gui
            )

            if mapped:

                result[
                    "acquirer"
                ] = mapped

                result[
                    "acquirer_identifier"
                ] = str(gui).strip()

                break

    return result


# ============================================================
# QRIS PAYLOAD PARSER
# ============================================================

def parse_qris_payload(
    payload: str,
) -> Dict[str, Any]:

    result = {

        "is_qris": False,

        "technical_status": "unverifiable",

        "crc": {},

        "payload_format": None,

        "point_of_initiation": None,

        "merchant_category": None,

        "transaction_currency": None,

        "transaction_amount": None,

        "merchant_name": None,

        "merchant_city": None,

        "country": None,

        "nmid": None,

        "acquirer": None,

        "acquirer_identifier": None,

        "merchant_account": {},

        "fields": {},

        "reasons": [],
    }

    if not payload:

        result["reasons"].append(
            "Payload QR kosong."
        )

        return result

    payload = str(payload).strip()

    # ========================================================
    # TLV PARSE
    # ========================================================

    tlv = parse_emv_tlv(payload)

    if not tlv.get("success"):

        result["reasons"].extend(
            tlv.get("errors", [])
        )

        return result

    fields = tlv.get(
        "fields",
        {}
    )

    result["fields"] = fields

    # ========================================================
    # BASIC EMV FIELDS
    # ========================================================

    result["payload_format"] = (
        fields.get(
            TAG_PAYLOAD_FORMAT
        )
    )

    result["point_of_initiation"] = (
        fields.get(
            TAG_POINT_OF_INITIATION
        )
    )

    result["merchant_category"] = (
        fields.get(
            TAG_MERCHANT_CATEGORY
        )
    )

    result["transaction_currency"] = (
        fields.get(
            TAG_TRANSACTION_CURRENCY
        )
    )

    result["transaction_amount"] = (
        fields.get(
            TAG_TRANSACTION_AMOUNT
        )
    )

    result["merchant_name"] = (
        fields.get(
            TAG_MERCHANT_NAME
        )
    )

    result["merchant_city"] = (
        fields.get(
            TAG_MERCHANT_CITY
        )
    )

    result["country"] = (
        fields.get(
            TAG_COUNTRY
        )
    )

    # ========================================================
    # MERCHANT ACCOUNT
    # ========================================================

    merchant_account = (
        extract_qris_merchant_account(
            fields
        )
    )

    result[
        "merchant_account"
    ] = merchant_account

    result["nmid"] = (
        merchant_account.get(
            "nmid"
        )
    )

    result["acquirer"] = (
        merchant_account.get(
            "acquirer"
        )
    )

    result[
        "acquirer_identifier"
    ] = merchant_account.get(
        "acquirer_identifier"
    )

    # ========================================================
    # QRIS IDENTIFICATION
    # ========================================================

    is_qris = bool(
        merchant_account.get(
            "detected"
        )
    )

    if QRIS_AID in payload.upper():

        is_qris = True

    result["is_qris"] = is_qris

    if not is_qris:

        result[
            "technical_status"
        ] = "unverifiable"

        result["reasons"].append(
            "Payload QR tidak menunjukkan "
            "struktur QRIS yang dapat diverifikasi."
        )

        return result

    # ========================================================
    # CRC
    # ========================================================

    crc_result = validate_qr_crc(
        payload
    )

    result["crc"] = crc_result

    if not crc_result["available"]:

        result[
            "technical_status"
        ] = "unverifiable"

        result["reasons"].append(
            "CRC QRIS tidak tersedia atau "
            "format payload tidak lengkap."
        )

    elif crc_result["valid"]:

        result[
            "technical_status"
        ] = "technically_valid"

        result["reasons"].append(
            "Struktur QRIS terbaca dan CRC valid."
        )

    else:

        result[
            "technical_status"
        ] = "invalid"

        result["reasons"].append(
            "CRC QRIS tidak sesuai dengan payload."
        )

    return result


# ============================================================
# QR IMAGE PREPROCESSING
# ============================================================

def generate_qr_image_variants(
    image: np.ndarray,
) -> List[np.ndarray]:

    variants = []

    if image is None:
        return variants

    # Original
    variants.append(image)

    try:

        # Grayscale
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        variants.append(gray)

        # Enlarged
        enlarged = cv2.resize(
            gray,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC,
        )

        variants.append(enlarged)

        # OTSU
        _, otsu = cv2.threshold(
            enlarged,
            0,
            255,
            cv2.THRESH_BINARY
            + cv2.THRESH_OTSU,
        )

        variants.append(otsu)

        # Adaptive threshold
        adaptive = cv2.adaptiveThreshold(
            enlarged,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )

        variants.append(adaptive)

    except Exception as error:

        print(
            "QR PREPROCESSING ERROR:",
            error,
        )

    return variants


# ============================================================
# QR DETECTOR
# ============================================================

def detect_qr_from_image(
    image_bytes: bytes,
) -> dict:

    empty_result = {

        "success": False,

        "qr_detected": False,

        "qr_data": "",

        "normalized_data": "",

        "data_hash": "",

        "payment_type": "unknown",

        "verification_status":
            STATUS_UNVERIFIED,

        "qris": {},

        "message": "",
    }

    if not image_bytes:

        empty_result[
            "message"
        ] = "Gambar kosong."

        return empty_result

    try:

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:

            empty_result[
                "message"
            ] = (
                "Gambar tidak dapat dibaca."
            )

            return empty_result

        detector = cv2.QRCodeDetector()

        detected_data = ""

        variants = (
            generate_qr_image_variants(
                image
            )
        )

        # ====================================================
        # SINGLE QR
        # ====================================================

        for variant in variants:

            if detected_data:
                break

            try:

                decoded, points, _ = (
                    detector.detectAndDecode(
                        variant
                    )
                )

                if decoded:

                    detected_data = (
                        decoded.strip()
                    )

            except Exception:

                continue

        # ====================================================
        # MULTI QR
        # ====================================================

        if not detected_data:

            for variant in variants:

                if detected_data:
                    break

                try:

                    result = (
                        detector.detectAndDecodeMulti(
                            variant
                        )
                    )

                    if len(result) == 4:

                        (
                            retval,
                            decoded_info,
                            points,
                            _,
                        ) = result

                        if (
                            retval
                            and decoded_info
                        ):

                            for item in decoded_info:

                                if item:

                                    detected_data = (
                                        str(item)
                                        .strip()
                                    )

                                    break

                except Exception:

                    continue

        # ====================================================
        # QR TIDAK TERDETEKSI
        # ====================================================

        if not detected_data:

            return {
                **empty_result,
                "success": True,
                "message":
                    "QR tidak terdeteksi.",
            }

        # ====================================================
        # NORMALIZATION + HASH
        # ====================================================

        normalized_data = (
            normalize_payment_data(
                detected_data
            )
        )

        data_hash = (
            generate_payment_hash(
                normalized_data
            )
        )

        # ====================================================
        # QRIS PARSER
        # ====================================================

        qris_result = (
            parse_qris_payload(
                detected_data
            )
        )

        is_qris = qris_result.get(
            "is_qris",
            False,
        )

        payment_type = (
            "qris"
            if is_qris
            else "qr"
        )

        # ====================================================
        # VERIFICATION STATUS
        # ====================================================

        if is_qris:

            technical_status = (
                qris_result.get(
                    "technical_status",
                    "unverifiable",
                )
            )

            if (
                technical_status
                == "invalid"
            ):

                verification_status = (
                    STATUS_INVALID
                )

            else:

                # Technically valid does NOT
                # mean merchant ownership verified.
                verification_status = (
                    STATUS_UNVERIFIED
                )

        else:

            verification_status = (
                STATUS_UNVERIFIED
            )

        return {

            "success": True,

            "qr_detected": True,

            "qr_data": detected_data,

            "normalized_data":
                normalized_data,

            "data_hash":
                data_hash,

            "payment_type":
                payment_type,

            "verification_status":
                verification_status,

            "qris":
                qris_result,

            "message": (
                "QRIS berhasil terdeteksi."
                if is_qris
                else "QR payment berhasil terdeteksi."
            ),
        }

    except Exception as error:

        print(
            "PAYMENT QR ERROR:",
            str(error),
        )

        return {
            **empty_result,
            "message":
                f"QR detector gagal: {error}",
        }


# ============================================================
# PHONE NUMBER
# ============================================================

PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+62|62|0)"
    r"(?:8\d{8,12})"
    r"(?!\d)"
)


def detect_phone_numbers(
    text: str,
) -> list:

    if not text:
        return []

    matches = (
        PHONE_PATTERN.findall(
            str(text)
        )
    )

    results = []

    for number in matches:

        normalized = re.sub(
            r"[^\d+]",
            "",
            number,
        )

        if normalized not in results:

            results.append(
                normalized
            )

    return results


# ============================================================
# PAYMENT CONTEXT
# ============================================================

PAYMENT_CONTEXT_TERMS = {

    "qris",

    "rekening",

    "rek",

    "transfer",

    "bank",

    "dana",

    "ovo",

    "gopay",

    "go pay",

    "shopeepay",

    "linkaja",

    "payment",

    "pembayaran",

    "bayar",

    "deposit",

    "top up",

    "topup",

    "nomor rekening",

    "no rekening",

    "no. rekening",

    "nomor dana",

    "nomor ovo",

    "nomor gopay",
}


def has_payment_context(
    text: str,
) -> bool:

    if not text:
        return False

    text_lower = str(
        text
    ).lower()

    return any(
        term in text_lower
        for term in PAYMENT_CONTEXT_TERMS
    )


def detect_payment_keywords(
    text: str,
) -> list:

    if not text:
        return []

    text_lower = str(
        text
    ).lower()

    keywords = []

    for term in sorted(
        PAYMENT_CONTEXT_TERMS,
        key=len,
        reverse=True,
    ):

        if term in text_lower:

            if term not in keywords:

                keywords.append(term)

    return keywords


# ============================================================
# BANK DETECTION
# ============================================================

BANK_TERMS = {

    "bca": "BCA",

    "bank central asia": "BCA",

    "bri": "BRI",

    "bank rakyat indonesia": "BRI",

    "bni": "BNI",

    "bank negara indonesia": "BNI",

    "mandiri": "Mandiri",

    "bank mandiri": "Mandiri",

    "btn": "BTN",

    "bank tabungan negara": "BTN",

    "cimb": "CIMB",

    "cimb niaga": "CIMB",

    "danamon": "Danamon",

    "permata": "Permata",

    "maybank": "Maybank",

    "bank jateng": "Bank Jateng",

    "bank jatim": "Bank Jatim",
}


def detect_bank(
    text: str,
) -> list:

    if not text:
        return []

    text_lower = str(
        text
    ).lower()

    results = []
    seen = set()

    for keyword, bank_name in (
        BANK_TERMS.items()
    ):

        if keyword in text_lower:

            if bank_name in seen:
                continue

            seen.add(
                bank_name
            )

            results.append({

                "payment_type":
                    "bank",

                "provider":
                    bank_name,

                "verification_status":
                    STATUS_UNVERIFIED,
            })

    return results


# ============================================================
# E-WALLET DETECTION
# ============================================================

EWALLET_TERMS = {

    "dana": "DANA",

    "ovo": "OVO",

    "gopay": "GoPay",

    "go pay": "GoPay",

    "shopeepay": "ShopeePay",

    "linkaja": "LinkAja",
}


def detect_ewallet(
    text: str,
) -> list:

    if not text:
        return []

    text_lower = str(
        text
    ).lower()

    results = []
    seen = set()

    for keyword, provider in (
        EWALLET_TERMS.items()
    ):

        if keyword in text_lower:

            if provider in seen:
                continue

            seen.add(
                provider
            )

            results.append({

                "payment_type":
                    "e_wallet",

                "provider":
                    provider,

                "verification_status":
                    STATUS_UNVERIFIED,
            })

    return results


# ============================================================
# ACCOUNT NUMBER
# ============================================================

ACCOUNT_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\d[\s.-]?){8,19}\d"
    r"(?!\d)"
)


PAYMENT_LABEL_PATTERNS = {

    "account_number": [

        re.compile(
            r"(?i)"
            r"(?:no\.?|nomor)"
            r"\s*(?:rekening|rek)"
            r"\s*[:\-]?\s*"
            r"((?:\d[\s.-]?){8,20})"
        ),

        re.compile(
            r"(?i)"
            r"(?:rekening|rek)"
            r"\s*[:\-]?\s*"
            r"((?:\d[\s.-]?){8,20})"
        ),
    ],

    "account_name": [

        re.compile(
            r"(?i)"
            r"(?:atas\s+nama|a/?n|nama\s+rekening)"
            r"\s*[:\-]\s*"
            r"([A-Za-z][A-Za-z .,'-]{2,100})"
        ),
    ],
}


def normalize_account_number(
    value: str,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\D",
        "",
        str(value),
    )


def detect_account_numbers(
    text: str,
    require_context: bool = True,
) -> list:

    if not text:
        return []

    text_value = str(text)

    if (
        require_context
        and not has_payment_context(text_value)
    ):
        return []

    results = []
    seen = set()

    # ========================================================
    # HANYA DETEKSI REKENING JIKA ADA LABEL REKENING
    # ========================================================

    for pattern in PAYMENT_LABEL_PATTERNS["account_number"]:

        for match in pattern.findall(text_value):

            number = normalize_account_number(match)

            if not (8 <= len(number) <= 20):
                continue

            if number in seen:
                continue

            seen.add(number)
            results.append(number)

    return results
def detect_account_name(
    text: str,
) -> Optional[str]:

    if not text:
        return None

    for pattern in (
        PAYMENT_LABEL_PATTERNS[
            "account_name"
        ]
    ):

        match = pattern.search(
            str(text)
        )

        if not match:
            continue

        value = re.sub(
            r"\s+",
            " ",
            match.group(1).strip(),
        )

        if value:
            return value

    return None


# ============================================================
# AMOUNT
# ============================================================

AMOUNT_PATTERNS = [

    re.compile(
        r"(?i)"
        r"(?:rp|idr)"
        r"\s*[\.:]?\s*"
        r"\d{1,3}"
        r"(?:[.,]\d{3})+"
        r"(?:[.,]\d{1,2})?"
    ),

    re.compile(
        r"(?i)"
        r"(?:rp|idr)"
        r"\s*\d+"
    ),

    re.compile(
        r"(?i)"
        r"(?<!\w)"
        r"\d+(?:[.,]\d+)?"
        r"\s*"
        r"(?:k|rb|ribu|jt|juta)"
    ),
]


def normalize_amount(
    value: str,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip(),
    )


def detect_amounts(
    text: str,
) -> list:

    if not text:
        return []

    results = []
    seen = set()

    for pattern in AMOUNT_PATTERNS:

        for match in pattern.findall(
            str(text)
        ):

            amount = (
                normalize_amount(
                    match
                )
            )

            key = amount.lower()

            if (
                amount
                and key not in seen
            ):

                seen.add(key)

                results.append(
                    amount
                )

    return results


# ============================================================
# PAYMENT SCORE
# ============================================================

def calculate_payment_score(
    qr_detected: bool,
    banks: list,
    ewallets: list,
    account_numbers: list,
    phone_numbers: list,
    payment_keywords: list,
    amounts: list,
) -> float:

    score = 0.0

    if qr_detected:
        score += 0.45

    if banks:
        score += 0.25

    if ewallets:
        score += 0.20

    if account_numbers:
        score += 0.25

    if phone_numbers:
        score += 0.12

    if payment_keywords:

        score += min(
            len(payment_keywords)
            * 0.05,
            0.20,
        )

    if amounts:
        score += 0.08

    return round(
        min(score, 1.0),
        4,
    )


# ============================================================
# PAYMENT EVIDENCE
# ============================================================

def build_payment_evidence(
    qr_result: dict,
    banks: list,
    ewallets: list,
    account_numbers: list,
    account_name: Optional[str],
    phone_numbers: list,
    amounts: list,
    payment_keywords: list,
) -> list:

    evidence = []

    # ========================================================
    # QR / QRIS
    # ========================================================

    if qr_result.get(
        "qr_detected"
    ):

        if (
            qr_result.get(
                "payment_type"
            )
            == "qris"
        ):

            evidence.append(
                "QRIS"
            )

            qris = (
                qr_result.get(
                    "qris",
                    {}
                )
                or {}
            )

            merchant_name = (
                qris.get(
                    "merchant_name"
                )
            )

            merchant_city = (
                qris.get(
                    "merchant_city"
                )
            )

            nmid = (
                qris.get(
                    "nmid"
                )
            )

            acquirer = (
                qris.get(
                    "acquirer"
                )
            )

            acquirer_identifier = (
                qris.get(
                    "acquirer_identifier"
                )
            )

            technical_status = (
                qris.get(
                    "technical_status"
                )
            )

            # Merchant
            if merchant_name:

                evidence.append(
                    f"Merchant QRIS: "
                    f"{merchant_name}"
                )

            # City
            if merchant_city:

                evidence.append(
                    f"Kota QRIS: "
                    f"{merchant_city}"
                )

            # NMID
            if nmid:

                evidence.append(
                    f"NMID: {nmid}"
                )

            # Acquirer
            if acquirer:

                evidence.append(
                    f"Acquirer: "
                    f"{acquirer}"
                )

            # Acquirer Identifier
            if acquirer_identifier:

                evidence.append(
                    "Acquirer Identifier: "
                    f"{acquirer_identifier}"
                )

            # Technical status
            if technical_status:

                evidence.append(
                    "Status QRIS: "
                    f"{technical_status}"
                )

            # CRC
            crc = (
                qris.get(
                    "crc",
                    {}
                )
                or {}
            )

            if crc.get(
                "available"
            ):

                evidence.append(
                    "CRC: "
                    + (
                        "valid"
                        if crc.get(
                            "valid"
                        )
                        else "invalid"
                    )
                )

        else:

            evidence.append(
                "QR payment"
            )

    # ========================================================
    # BANK
    # ========================================================

    for bank in banks:

        provider = bank.get(
            "provider"
        )

        if provider:

            evidence.append(
                provider
            )

    # ========================================================
    # E-WALLET
    # ========================================================

    for wallet in ewallets:

        provider = wallet.get(
            "provider"
        )

        if provider:

            evidence.append(
                provider
            )

    # ========================================================
    # ACCOUNT
    # ========================================================

    for account_number in (
        account_numbers
    ):

        evidence.append(
            "Nomor rekening: "
            f"{account_number}"
        )

    if account_name:

        evidence.append(
            "Atas nama: "
            f"{account_name}"
        )

    # ========================================================
    # PHONE
    # ========================================================

    for phone in phone_numbers:

        evidence.append(
            "Nomor HP pembayaran: "
            f"{phone}"
        )

    # ========================================================
    # AMOUNT
    # ========================================================

    for amount in amounts:

        evidence.append(
            "Nominal: "
            f"{amount}"
        )

    # ========================================================
    # PAYMENT KEYWORDS
    # ========================================================

    existing_lower = {
        str(item).lower()
        for item in evidence
    }

    for keyword in payment_keywords:

        if (
            keyword.lower()
            not in existing_lower
        ):

            evidence.append(
                "Payment context: "
                f"{keyword}"
            )

    return list(
        dict.fromkeys(
            evidence
        )
    )


# ============================================================
# MAIN PAYMENT DETECTOR
# ============================================================

def detect_payment(
    image_bytes: bytes,
    detected_text: Optional[str] = None,
) -> dict:

    # ========================================================
    # EMPTY IMAGE
    # ========================================================

    if not image_bytes:

        return {

            "payment_detected": False,

            "payment_score": 0.0,

            "payment_type":
                "unknown",

            "qr_detected": False,

            "qr_data": "",

            "qr_data_hash": "",

            "provider": None,

            "account_name": None,

            "account_numbers": [],

            "phone_numbers": [],

            "amounts": [],

            "payment_keywords": [],

            "verification_status":
                STATUS_UNVERIFIED,

            "image_hash": "",

            "evidence": [],

            "payments": [],

            "qris": {},
        }

    # ========================================================
    # IMAGE HASH
    # ========================================================

    image_hash = (
        generate_image_hash(
            image_bytes
        )
    )

    # ========================================================
    # QR DETECTION
    # ========================================================

    qr_result = (
        detect_qr_from_image(
            image_bytes
        )
    )

    payments = []

    # ========================================================
    # QR / QRIS
    # ========================================================

    if qr_result.get(
        "qr_detected"
    ):

        qris_data = (
            qr_result.get(
                "qris"
            )
            or {}
        )

        payments.append({

            "payment_type":
                qr_result.get(
                    "payment_type",
                    "qr",
                ),

            "data_hash":
                qr_result.get(
                    "data_hash",
                    "",
                ),

            "qr_data":
                qr_result.get(
                    "qr_data",
                    "",
                ),

            "verification_status":
                qr_result.get(
                    "verification_status",
                    STATUS_UNVERIFIED,
                ),

            "image_hash":
                image_hash,

            "qris":
                qris_data,
        })

    # ========================================================
    # OCR / TEXT
    # ========================================================

    text = (
        detected_text
        or ""
    ).strip()

    banks = []

    ewallets = []

    phone_numbers = []

    account_numbers = []

    account_name = None

    amounts = []

    payment_keywords = []

    if (
        text
        and has_payment_context(
            text
        )
    ):

        banks = detect_bank(
            text
        )

        ewallets = detect_ewallet(
            text
        )

        phone_numbers = (
            detect_phone_numbers(
                text
            )
        )

        account_numbers = (
            detect_account_numbers(
                text
            )
        )

        account_name = (
            detect_account_name(
                text
            )
        )

        amounts = detect_amounts(
            text
        )

        payment_keywords = (
            detect_payment_keywords(
                text
            )
        )

        # ----------------------------------------------------
        # Banks
        # ----------------------------------------------------

        for bank in banks:

            payments.append(
                bank
            )

        # ----------------------------------------------------
        # E-wallet
        # ----------------------------------------------------

        for wallet in ewallets:

            payments.append(
                wallet
            )

        # ----------------------------------------------------
        # Phone
        # ----------------------------------------------------

        for phone in phone_numbers:

            payments.append({

                "payment_type":
                    "phone",

                "phone_number":
                    phone,

                "verification_status":
                    STATUS_UNVERIFIED,
            })

        # ----------------------------------------------------
        # Bank Account
        # ----------------------------------------------------

        for account_number in (
            account_numbers
        ):

            payments.append({

                "payment_type":
                    "bank_account",

                "account_number":
                    account_number,

                "account_name":
                    account_name,

                "verification_status":
                    STATUS_UNVERIFIED,
            })

    # ========================================================
    # UNIQUE PAYMENTS
    # ========================================================

    unique_payments = []

    seen_keys = set()

    for payment in payments:

        key = (

            payment.get(
                "payment_type"
            ),

            payment.get(
                "data_hash"
            ),

            payment.get(
                "provider"
            ),

            payment.get(
                "phone_number"
            ),

            payment.get(
                "account_number"
            ),
        )

        if key in seen_keys:
            continue

        seen_keys.add(
            key
        )

        unique_payments.append(
            payment
        )

    payments = (
        unique_payments
    )

    # ========================================================
    # PAYMENT DETECTED
    # ========================================================

    payment_detected = bool(
        payments
    )

    payment_type = "unknown"

    if payments:

        payment_type = (
            payments[0].get(
                "payment_type",
                "unknown",
            )
        )

    qr_detected = bool(
        qr_result.get(
            "qr_detected",
            False,
        )
    )

    # ========================================================
    # PAYMENT SCORE
    # ========================================================

    payment_score = (
        calculate_payment_score(

            qr_detected=
                qr_detected,

            banks=
                banks,

            ewallets=
                ewallets,

            account_numbers=
                account_numbers,

            phone_numbers=
                phone_numbers,

            payment_keywords=
                payment_keywords,

            amounts=
                amounts,
        )
    )

    # ========================================================
    # EVIDENCE
    # ========================================================

    evidence = (
        build_payment_evidence(

            qr_result=
                qr_result,

            banks=
                banks,

            ewallets=
                ewallets,

            account_numbers=
                account_numbers,

            account_name=
                account_name,

            phone_numbers=
                phone_numbers,

            amounts=
                amounts,

            payment_keywords=
                payment_keywords,
        )
    )

    # ========================================================
    # PROVIDER
    # ========================================================

    provider = None

    if banks:

        provider = (
            banks[0].get(
                "provider"
            )
        )

    elif ewallets:

        provider = (
            ewallets[0].get(
                "provider"
            )
        )

    elif (
        qr_result.get(
            "payment_type"
        )
        == "qris"
    ):

        qris_provider = (
            qr_result
            .get(
                "qris",
                {}
            )
            .get(
                "acquirer"
            )
        )

        provider = (
            qris_provider
            or "QRIS"
        )

    # ========================================================
    # QRIS RESULT
    # ========================================================

    qris_result = (
        qr_result.get(
            "qris",
            {},
        )
        or {}
    )

    # ========================================================
    # VERIFICATION
    # ========================================================

    if payment_detected:

        verification_status = (
            STATUS_UNVERIFIED
        )

        if (

            qr_detected

            and qr_result.get(
                "payment_type"
            )
            == "qris"

            and qr_result.get(
                "verification_status"
            )
            == STATUS_INVALID

        ):

            verification_status = (
                STATUS_INVALID
            )

    else:

        verification_status = (
            STATUS_UNVERIFIED
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {

        "payment_detected":
            payment_detected,

        "payment_score":
            payment_score,

        "payment_type":
            payment_type,

        "qr_detected":
            qr_detected,

        "qr_data":
            qr_result.get(
                "qr_data",
                "",
            ),

        "qr_data_hash":
            qr_result.get(
                "data_hash",
                "",
            ),

        "provider":
            provider,

        "account_name":
            account_name,

        "account_numbers":
            account_numbers,

        "phone_numbers":
            phone_numbers,

        "amounts":
            amounts,

        "payment_keywords":
            payment_keywords,

        "verification_status":
            verification_status,

        "image_hash":
            image_hash,

        "evidence":
            evidence,

        "payments":
            payments,

        "qris":
            qris_result,
    }

    # ========================================================
    # CONSOLE LOG
    # ========================================================

    print(
        "\n=========================================="
    )

    print(
        "GUARDNET-AI PAYMENT DETECTOR"
    )

    print(
        "=========================================="
    )

    print(
        "Payment Detected:",
        payment_detected,
    )

    print(
        "Payment Type:",
        payment_type,
    )

    print(
        "QR Detected:",
        qr_detected,
    )

    print(
        "Provider:",
        provider,
    )

    print(
        "Payment Count:",
        len(payments),
    )

    print(
        "Payment Score:",
        payment_score,
    )

    print(
        "Banks:",
        [
            item.get(
                "provider"
            )
            for item in banks
        ],
    )

    print(
        "E-Wallets:",
        [
            item.get(
                "provider"
            )
            for item in ewallets
        ],
    )

    print(
        "Account Numbers:",
        account_numbers,
    )

    print(
        "Phone Numbers:",
        phone_numbers,
    )

    print(
        "Amounts:",
        amounts,
    )

    print(
        "Payment Keywords:",
        payment_keywords,
    )

    # ========================================================
    # QRIS INFORMATION
    # ========================================================

    print(
        "QRIS Status:",
        qris_result.get(
            "technical_status"
        ),
    )

    print(
        "QRIS Merchant:",
        qris_result.get(
            "merchant_name"
        ),
    )

    print(
        "QRIS City:",
        qris_result.get(
            "merchant_city"
        ),
    )

    print(
        "QRIS NMID:",
        qris_result.get(
            "nmid"
        ),
    )

    print(
        "QRIS Acquirer:",
        qris_result.get(
            "acquirer"
        ),
    )

    print(
        "QRIS Acquirer Identifier:",
        qris_result.get(
            "acquirer_identifier"
        ),
    )

    print(
        "QRIS CRC:",
        qris_result.get(
            "crc",
            {},
        ),
    )

    print(
        "Evidence:",
        evidence,
    )

    print(
        "Image Hash:",
        image_hash,
    )

    print(
        "Verification:",
        verification_status,
    )

    print(
        "=========================================="
    )

    return result


# ============================================================
# VERIFY PAYMENT
# ============================================================

def verify_payment(
    original_payment: dict,
    current_payment: dict,
) -> dict:

    if not original_payment:

        return {

            "valid": False,

            "status":
                STATUS_INVALID,

            "message":
                "Payment evidence awal tidak tersedia.",
        }

    if not current_payment:

        return {

            "valid": False,

            "status":
                STATUS_INVALID,

            "message":
                "Payment baru tidak tersedia.",
        }

    # ========================================================
    # ORIGINAL HASH
    # ========================================================

    original_hash = (

        original_payment.get(
            "data_hash",
            "",
        )

        or original_payment.get(
            "qr_data_hash",
            "",
        )

        or ""
    )

    # ========================================================
    # CURRENT HASH
    # ========================================================

    current_hash = (

        current_payment.get(
            "data_hash",
            "",
        )

        or current_payment.get(
            "qr_data_hash",
            "",
        )

        or ""
    )

    if not original_hash:

        return {

            "valid": False,

            "status":
                STATUS_INVALID,

            "message":
                "Hash payment awal tidak tersedia.",
        }

    if not current_hash:

        return {

            "valid": False,

            "status":
                STATUS_INVALID,

            "message":
                "Hash payment baru tidak tersedia.",
        }

    # ========================================================
    # MATCH
    # ========================================================

    if original_hash == current_hash:

        return {

            "valid": True,

            "status":
                STATUS_MATCHED,

            "original_hash":
                original_hash,

            "current_hash":
                current_hash,

            "message":
                "Payment sesuai dengan evidence awal.",
        }

    # ========================================================
    # CONFLICT
    # ========================================================

    return {

        "valid": False,

        "status":
            STATUS_CONFLICT,

        "original_hash":
            original_hash,

        "current_hash":
            current_hash,

        "message":
            "Payment berbeda dengan evidence awal.",
    }