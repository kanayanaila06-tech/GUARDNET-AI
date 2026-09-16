# ============================================================


# GUARDNET-AI PAYMENT SERVICE


# ============================================================


#


# Fungsi:


# - Generate payment hash


# - Generate image hash


# - Normalize payment data


# - Detect QR / QRIS


# - Parse QRIS EMV payload


# - Validate QRIS CRC


# - Detect bank / e-wallet


# - Detect nomor rekening / nomor HP


# - Detect nominal pembayaran


# - Build payment evidence


# - Calculate payment evidence score


# - Verify payment evidence


#


# STATUS:


# detected   -> payment ditemukan


# unverified -> belum tervalidasi secara eksternal


# matched    -> cocok dengan evidence sebelumnya


# conflict   -> berbeda dengan evidence sebelumnya


# invalid    -> data tidak valid


#


# CATATAN:


# Validasi CRC hanya memvalidasi integritas payload QR.


# CRC TIDAK membuktikan bahwa QRIS benar-benar milik merchant


# tertentu. Verifikasi kepemilikan merchant membutuhkan sumber


# resmi/PJP/transaction-side verification.


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


 


 


def identify_acquirer(identifier: Optional[str]) -> Optional[str]:


    """


    Mengubah acquirer identifier menjadi nama provider jika


    identifier tersebut dikenali.


 


    Jika belum dikenali, fungsi mengembalikan None.


    Identifier mentah tetap disimpan sebagai evidence.


    """


 


    if not identifier:


        return None


 


    normalized = str(identifier).strip().upper()


 


    return ACQUIRER_MAP.get(normalized)


 


 


# ============================================================


# HASH UTILITIES


# ============================================================


 


def normalize_payment_data(payment_data: str) -> str:


    if not payment_data:


        return ""


 


    data = str(payment_data).strip().lower()


    data = re.sub(r"\s+", "", data)


 


    return data


 


 


def generate_payment_hash(data: str) -> str:


    normalized_data = normalize_payment_data(data)


 


    if not normalized_data:


        return ""


 


    return hashlib.sha256(


        normalized_data.encode("utf-8")


    ).hexdigest()


 


 


def generate_image_hash(image_bytes: bytes) -> str:


    if not image_bytes:


        return ""


 


    return hashlib.sha256(image_bytes).hexdigest()


 


 


# ============================================================


# CRC-16 / CCITT-FALSE


# ============================================================


 


def calculate_crc16_ccitt_false(data: str) -> str:


    crc = 0xFFFF


 


    for byte in data.encode("utf-8"):


        crc ^= byte << 8


 


        for _ in range(8):


            if crc & 0x8000:


                crc = ((crc << 1) ^ 0x1021) & 0xFFFF


            else:


                crc = (crc << 1) & 0xFFFF


 


    return f"{crc:04X}"


 


 


def validate_qr_crc(payload: str) -> Dict[str, Any]:


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


 


    actual_crc = crc_match.group(1).upper()


    crc_input = payload[:-4]


 


    expected_crc = calculate_crc16_ccitt_false(crc_input)


 


    return {


        "available": True,


        "valid": actual_crc == expected_crc,


        "expected_crc": expected_crc,


        "actual_crc": actual_crc,


    }


 


 


# ============================================================


# EMVCo TLV PARSER


# ============================================================


 


def parse_emv_tlv(payload: str) -> Dict[str, Any]:


    result = {


        "success": False,


        "fields": {},


        "errors": [],


    }


 


    if not payload:


        result["errors"].append("Payload QR kosong.")


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


 


        tag = payload[index:index + 2]


        length_text = payload[index + 2:index + 4]


 


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


 


        value = payload[start:end]


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


    Mencari Merchant Account Information pada tag 26-51.


 


    Data yang diekstrak:


    - GUI


    - NMID / merchant identifier


    - merchant PAN / fallback identifier


    - acquirer identifier jika terdapat pada GUI


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


 


    # Simpan semua Merchant Account Information yang terbaca.


    merchant_accounts = []


 


    for tag in range(26, 52):


 


        tag_key = f"{tag:02d}"


        value = fields.get(tag_key)


 


        if not value:


            continue


 


        nested = parse_emv_tlv(value)


 


        if not nested.get("success"):


            continue


 


        nested_fields = nested.get("fields", {})


        gui = nested_fields.get("00")


 


        if not gui:


            continue


 


        gui_upper = str(gui).upper()


 


        account_item = {


            "tag": tag_key,


            "gui": gui,


            "fields": nested_fields,


        }


 


        # ----------------------------------------------------


        # QRIS Merchant Account


        # ----------------------------------------------------


 


        if (


            QRIS_GUI in gui_upper


            or QRIS_AID in value.upper()


        ):


            result["detected"] = True


            result["tag"] = tag_key


            result["gui"] = gui


            result["fields"] = nested_fields


 


            # Pada payload QRIS yang diuji, NMID berada


            # pada subtag 02. Subtag 01 digunakan sebagai


            # fallback agar parser tetap kompatibel.


            result["nmid"] = (


                nested_fields.get("02")


                or nested_fields.get("01")


            )


 


            result["merchant_pan"] = (


                nested_fields.get("01")


                or nested_fields.get("02")


            )


 


            merchant_accounts.append(account_item)


 


            # Jangan langsung return. Masih perlu mencari


            # acquirer identifier pada account information lain.


            continue


 


        # ----------------------------------------------------


        # Candidate Acquirer


        # ----------------------------------------------------


 


        merchant_accounts.append(account_item)


 


        if not result["acquirer_identifier"]:


            result["acquirer_identifier"] = gui


 


            mapped = identify_acquirer(gui)


 


            if mapped:


                result["acquirer"] = mapped


 


    # --------------------------------------------------------


    # Jika QRIS ditemukan tetapi acquirer belum ditemukan,


    # coba gunakan GUI dari Merchant Account Information


    # non-QRIS sebagai identifier.


    # --------------------------------------------------------


 


    if result["detected"] and not result["acquirer_identifier"]:


 


        for account in merchant_accounts:


 


            gui = account.get("gui")


 


            if not gui:


                continue


 


            gui_upper = str(gui).upper()


 


            if QRIS_GUI in gui_upper:


                continue


 


            result["acquirer_identifier"] = gui


 


            mapped = identify_acquirer(gui)


 


            if mapped:


                result["acquirer"] = mapped


 


            break


 


    return result


 


 


# ============================================================


# QRIS PARSER


# ============================================================


 


def evaluate_qris_data_quality(

    fields: Dict[str, str],

    merchant_account: Dict[str, Any],

    crc_result: Dict[str, Any],

) -> Dict[str, Any]:

    """Evaluate QRIS technical/data quality without claiming ownership."""

    checks = {

        "payload_format_present": bool(fields.get(TAG_PAYLOAD_FORMAT)),

        "payload_format_supported": fields.get(TAG_PAYLOAD_FORMAT) in {"01"},

        "point_of_initiation_present": bool(fields.get(TAG_POINT_OF_INITIATION)),

        "currency_idr": fields.get(TAG_TRANSACTION_CURRENCY) == "360",

        "country_indonesia": str(fields.get(TAG_COUNTRY) or "").upper() == "ID",

        "merchant_name_present": bool(fields.get(TAG_MERCHANT_NAME)),

        "merchant_city_present": bool(fields.get(TAG_MERCHANT_CITY)),

        "merchant_category_present": bool(fields.get(TAG_MERCHANT_CATEGORY)),

        "merchant_account_present": bool(merchant_account.get("detected")),

        "nmid_present": bool(merchant_account.get("nmid")),

        "acquirer_identifier_present": bool(merchant_account.get("acquirer_identifier")),

        "crc_available": bool(crc_result.get("available")),

        "crc_valid": bool(crc_result.get("valid")) if crc_result.get("available") else False,

    }

    reasons=[]

    if not checks["payload_format_present"]:

        reasons.append("Payload Format Indicator tidak tersedia.")

    elif not checks["payload_format_supported"]:

        reasons.append("Payload Format Indicator bukan format QRIS yang diharapkan.")

    if not checks["point_of_initiation_present"]:

        reasons.append("Point of Initiation Method tidak tersedia.")

    if not checks["currency_idr"]:

        reasons.append("Kode mata uang payload bukan 360 (IDR).")

    if not checks["country_indonesia"]:

        reasons.append("Country Code payload bukan ID.")

    if not checks["merchant_name_present"]:

        reasons.append("Merchant Name tidak tersedia.")

    if not checks["merchant_city_present"]:

        reasons.append("Merchant City tidak tersedia.")

    if not checks["merchant_account_present"]:

        reasons.append("Merchant Account Information QRIS tidak ditemukan.")

    if not checks["nmid_present"]:

        reasons.append("NMID tidak ditemukan pada Merchant Account Information.")

    if not checks["acquirer_identifier_present"]:

        reasons.append("Acquirer Identifier tidak berhasil diidentifikasi.")

    if not checks["crc_available"]:

        reasons.append("CRC tidak tersedia atau format payload tidak lengkap.")

    elif not checks["crc_valid"]:

        reasons.append("CRC payload tidak valid.")


    critical=("currency_idr","country_indonesia","merchant_account_present","crc_valid")

    if any(not checks[k] for k in critical):

        status="suspicious"

    elif not checks["nmid_present"] or not checks["acquirer_identifier_present"]:

        status="needs_review"

    elif reasons:

        status="needs_review"

    else:

        status="technically_consistent"

    return {"status":status,"checks":checks,"reasons":reasons}



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


 


        # New QRIS fields


        "nmid": None,


        "acquirer": None,


        "acquirer_identifier": None,


 


        "merchant_account": {},


        "fields": {},

        "technical_checks": {},

        "data_quality_status": "unverifiable",


        "reasons": [],


    }


 


    if not payload:


        result["reasons"].append("Payload QR kosong.")


        return result


 


    payload = str(payload).strip()


 


    tlv = parse_emv_tlv(payload)


 


    if not tlv.get("success"):


        result["reasons"].extend(


            tlv.get("errors", [])


        )


        return result


 


    fields = tlv.get("fields", {})


    result["fields"] = fields


 


    # --------------------------------------------------------


    # Basic EMV fields


    # --------------------------------------------------------


 


    result["payload_format"] = fields.get(


        TAG_PAYLOAD_FORMAT


    )


 


    result["point_of_initiation"] = fields.get(


        TAG_POINT_OF_INITIATION


    )


 


    result["merchant_category"] = fields.get(


        TAG_MERCHANT_CATEGORY


    )


 


    result["transaction_currency"] = fields.get(


        TAG_TRANSACTION_CURRENCY


    )


 


    result["transaction_amount"] = fields.get(


        TAG_TRANSACTION_AMOUNT


    )


 


    result["merchant_name"] = fields.get(


        TAG_MERCHANT_NAME


    )


 


    result["merchant_city"] = fields.get(


        TAG_MERCHANT_CITY


    )


 


    result["country"] = fields.get(


        TAG_COUNTRY


    )


 


    # --------------------------------------------------------


    # Merchant Account Information


    # --------------------------------------------------------


 


    merchant_account = extract_qris_merchant_account(


        fields


    )


 


    result["merchant_account"] = merchant_account


 


    result["nmid"] = merchant_account.get("nmid")


    result["acquirer"] = merchant_account.get("acquirer")


    result["acquirer_identifier"] = merchant_account.get(


        "acquirer_identifier"


    )


 


    # --------------------------------------------------------


    # QRIS identification


    # --------------------------------------------------------


 


    is_qris = bool(


        merchant_account.get("detected")


    )


 


    if QRIS_AID in payload.upper():


        is_qris = True


 


    result["is_qris"] = is_qris


 


    if not is_qris:


        result["technical_status"] = "unverifiable"


        result["reasons"].append(


            "Payload QR tidak menunjukkan struktur QRIS "


            "yang dapat diverifikasi."


        )


        return result


 


    # --------------------------------------------------------


    # CRC


    # --------------------------------------------------------


 


    crc_result = validate_qr_crc(payload)


    result["crc"] = crc_result


 


    if not crc_result["available"]:


 


        result["technical_status"] = "unverifiable"


 


        result["reasons"].append(


            "CRC QRIS tidak tersedia atau format payload "


            "tidak lengkap."


        )


 


    elif crc_result["valid"]:


 


        result["technical_status"] = "technically_valid"


 


        result["reasons"].append(


            "Struktur QRIS terbaca dan CRC valid."


        )


 


    else:


 


        result["technical_status"] = "invalid"


 


        result["reasons"].append(


            "CRC QRIS tidak sesuai dengan payload."


        )


 


    # --------------------------------------------------------

    # DATA QUALITY / CONSISTENCY

    # --------------------------------------------------------

    quality = evaluate_qris_data_quality(

        fields=fields,

        merchant_account=merchant_account,

        crc_result=crc_result,

    )

    result["data_quality_status"] = quality["status"]

    result["technical_checks"] = quality["checks"]

    for reason in quality["reasons"]:

        if reason not in result["reasons"]:

            result["reasons"].append(reason)


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


 


    variants.append(image)


 


    try:


 


        gray = cv2.cvtColor(


            image,


            cv2.COLOR_BGR2GRAY,


        )


 


        variants.append(gray)


 


        enlarged = cv2.resize(


            gray,


            None,


            fx=2.0,


            fy=2.0,


            interpolation=cv2.INTER_CUBIC,


        )


 


        variants.append(enlarged)


 


        _, otsu = cv2.threshold(


            enlarged,


            0,


            255,


            cv2.THRESH_BINARY + cv2.THRESH_OTSU,


        )


 


        variants.append(otsu)


 


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


        print("QR PREPROCESSING ERROR:", error)


 


    return variants


 


 


# ============================================================


# QR DETECTION


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


        "verification_status": STATUS_UNVERIFIED,


        "qris": {},


        "message": "",


    }


 


    if not image_bytes:


        empty_result["message"] = "Gambar kosong."


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


            empty_result["message"] = (


                "Gambar tidak dapat dibaca."


            )


            return empty_result


 


        detector = cv2.QRCodeDetector()


        detected_data = ""


 


        variants = generate_qr_image_variants(image)


 


        # ----------------------------------------------------


        # Single QR


        # ----------------------------------------------------


 


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


                    detected_data = decoded.strip()


 


            except Exception:


                continue


 


        # ----------------------------------------------------


        # Multi QR


        # ----------------------------------------------------


 


        if not detected_data:


 


            for variant in variants:


 


                if detected_data:


                    break


 


                try:


 


                    result = detector.detectAndDecodeMulti(


                        variant


                    )


 


                    if len(result) == 4:


 


                        retval, decoded_info, points, _ = (


                            result


                        )


 


                        if retval and decoded_info:


 


                            for item in decoded_info:


 


                                if item:


                                    detected_data = (


                                        str(item).strip()


                                    )


                                    break


 


                except Exception:


                    continue


 


        # ----------------------------------------------------


        # Tidak ditemukan


        # ----------------------------------------------------


 


        if not detected_data:


 


            return {


                **empty_result,


                "success": True,


                "message": "QR tidak terdeteksi.",


            }


 


        normalized_data = normalize_payment_data(


            detected_data


        )


 


        data_hash = generate_payment_hash(


            normalized_data


        )


 


        qris_result = parse_qris_payload(


            detected_data


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


 


        if is_qris:


 


            technical_status = qris_result.get(


                "technical_status",


                "unverifiable",


            )


 


            if technical_status == "invalid":


                verification_status = STATUS_INVALID


            else:


                verification_status = STATUS_UNVERIFIED


 


        else:


            verification_status = STATUS_UNVERIFIED


 


        return {


            "success": True,


            "qr_detected": True,


            "qr_data": detected_data,


            "normalized_data": normalized_data,


            "data_hash": data_hash,


            "payment_type": payment_type,


            "verification_status": verification_status,


            "qris": qris_result,


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


            "message": f"QR detector gagal: {error}",


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


 


    matches = PHONE_PATTERN.findall(str(text))


 


    results = []


 


    for number in matches:


 


        normalized = re.sub(


            r"[^\d+]",


            "",


            number,


        )


 


        if normalized not in results:


            results.append(normalized)


 


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


 


    text_lower = str(text).lower()


 


    return any(


        term in text_lower


        for term in PAYMENT_CONTEXT_TERMS


    )


 


 


def detect_payment_keywords(


    text: str,


) -> list:


 


    if not text:


        return []


 


    text_lower = str(text).lower()


 


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


 


    text_lower = str(text).lower()


 


    results = []


    seen = set()


 


    for keyword, bank_name in BANK_TERMS.items():


 


        if keyword in text_lower:


 


            if bank_name in seen:


                continue


 


            seen.add(bank_name)


 


            results.append({


                "payment_type": "bank",


                "provider": bank_name,


                "verification_status": STATUS_UNVERIFIED,


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


 


    text_lower = str(text).lower()


 


    results = []


    seen = set()


 


    for keyword, provider in EWALLET_TERMS.items():


 


        if keyword in text_lower:


 


            if provider in seen:


                continue


 


            seen.add(provider)


 


            results.append({


                "payment_type": "e_wallet",


                "provider": provider,


                "verification_status": STATUS_UNVERIFIED,


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


 


    return re.sub(r"\D", "", str(value))


 


 


def detect_account_numbers(


    text: str,


    require_context: bool = True,


    allow_generic: bool = True,


    excluded_numbers: set | None = None,


) -> list:


 


    if not text:


        return []


 


    text_value = str(text)


    excluded = {


        normalize_account_number(value)


        for value in (excluded_numbers or set())


        if normalize_account_number(value)


    }


 


    if (


        require_context


        and not has_payment_context(text_value)


    ):


        return []


 


    results = []


    seen = set()


 


    for pattern in PAYMENT_LABEL_PATTERNS["account_number"]:


 


        for match in pattern.findall(text_value):


 


            number = normalize_account_number(match)


 


            if not (8 <= len(number) <= 20):


                continue


 


            if number in excluded:


                continue


            if number in seen:


                continue


 


            seen.add(number)


            results.append(number)


 


    if not allow_generic:


        return results


    


    for match in ACCOUNT_PATTERN.findall(text_value):


 


        number = normalize_account_number(match)


 


        if not (8 <= len(number) <= 20):


            continue


 


        if len(set(number)) == 1:


            continue


 


        if number in excluded:


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


 


    for pattern in PAYMENT_LABEL_PATTERNS["account_name"]:


 


        match = pattern.search(str(text))


 


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


 


        for match in pattern.findall(str(text)):


 


            amount = normalize_amount(match)


            key = amount.lower()


 


            if amount and key not in seen:


 


                seen.add(key)


                results.append(amount)


 


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


            len(payment_keywords) * 0.05,


            0.20,


        )


 


    if amounts:


        score += 0.08


 


    return round(min(score, 1.0), 4)


 


 


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


 


    if qr_result.get("qr_detected"):


 


        if qr_result.get("payment_type") == "qris":


 


            evidence.append("QRIS")


 


            qris = qr_result.get("qris", {})


 


            merchant_name = qris.get("merchant_name")


            merchant_city = qris.get("merchant_city")


            nmid = qris.get("nmid")


            acquirer = qris.get("acquirer")


            acquirer_identifier = qris.get(


                "acquirer_identifier"


            )


            technical_status = qris.get(


                "technical_status"


            )


 


            if merchant_name:


                evidence.append(


                    f"Merchant QRIS: {merchant_name}"


                )


 


            if merchant_city:


                evidence.append(


                    f"Kota QRIS: {merchant_city}"


                )


 


            if nmid:


                evidence.append(


                    f"NMID: {nmid}"


                )


 


            if acquirer:


                evidence.append(


                    f"Acquirer: {acquirer}"


                )


 


            if acquirer_identifier:


                evidence.append(


                    f"Acquirer Identifier: "


                    f"{acquirer_identifier}"


                )


 


            if technical_status:


                evidence.append(


                    f"Status QRIS: {technical_status}"


                )


 


            crc = qris.get("crc", {})


 


            if crc.get("available"):


                evidence.append(


                    "CRC: "


                    + (


                        "valid"


                        if crc.get("valid")


                        else "invalid"


                    )


                )


 


        else:


            evidence.append("QR payment")


 


    for bank in banks:


 


        provider = bank.get("provider")


 


        if provider:


            evidence.append(provider)


 


    for wallet in ewallets:


 


        provider = wallet.get("provider")


 


        if provider:


            evidence.append(provider)


 


    for account_number in account_numbers:


 


        evidence.append(


            f"Nomor rekening: {account_number}"


        )


 


    if account_name:


 


        evidence.append(


            f"Atas nama: {account_name}"


        )


 


    for phone in phone_numbers:


 


        evidence.append(


            f"Nomor HP pembayaran: {phone}"


        )


 


    for amount in amounts:


 


        evidence.append(


            f"Nominal: {amount}"


        )


 


    existing_lower = {


        str(item).lower()


        for item in evidence


    }


 


    for keyword in payment_keywords:


 


        if keyword.lower() not in existing_lower:


 


            evidence.append(


                f"Payment context: {keyword}"


            )


 


    return list(dict.fromkeys(evidence))


 


 


# ============================================================


# MAIN PAYMENT DETECTOR


# ============================================================


 


def detect_payment(


    image_bytes: bytes,


    detected_text: Optional[str] = None,


) -> dict:


 


    if not image_bytes:


 


        return {


            "payment_detected": False,


            "payment_score": 0.0,


            "payment_type": "unknown",


            "qr_detected": False,


            "qr_data": "",


            "qr_data_hash": "",


            "provider": None,


            "account_name": None,


            "account_numbers": [],


            "phone_numbers": [],


            "amounts": [],


            "payment_keywords": [],


            "verification_status": STATUS_UNVERIFIED,


            "image_hash": "",


            "evidence": [],


            "payments": [],


            "qris": {},


        }


 


    image_hash = generate_image_hash(image_bytes)


 


    qr_result = detect_qr_from_image(image_bytes)


 


    payments = []


 


    # --------------------------------------------------------


    # QR / QRIS


    # --------------------------------------------------------


 


    if qr_result.get("qr_detected"):


 


        qris_data = qr_result.get("qris") or {}


 


        payments.append({


            "payment_type": qr_result.get(


                "payment_type",


                "qr",


            ),


            "data_hash": qr_result.get(


                "data_hash",


                "",


            ),


            "qr_data": qr_result.get(


                "qr_data",


                "",


            ),


            "verification_status": qr_result.get(


                "verification_status",


                STATUS_UNVERIFIED,


            ),


            "image_hash": image_hash,


            "qris": qris_data,


            "qris_data_quality_status": qris_data.get(

                "data_quality_status",

                "unverifiable",

            ),

            "qris_technical_checks": qris_data.get(

                "technical_checks",

                {},

            ),

            "qris_quality_reasons": qris_data.get(

                "reasons",

                [],

            ),


        })


 


    # --------------------------------------------------------


    # OCR / TEXT


    # --------------------------------------------------------


 


    text = (detected_text or "").strip()


 


    banks = []


    ewallets = []


    phone_numbers = []


    account_numbers = []


    account_name = None


    amounts = []


    payment_keywords = []


 


    if text and has_payment_context(text):


 


        banks = detect_bank(text)


        ewallets = detect_ewallet(text)


        phone_numbers = detect_phone_numbers(text)


        qris_nmid = (


            (qr_result.get("qris") or {}).get("nmid")


            if qr_result.get("qr_detected")


            else None


        )


        account_numbers = detect_account_numbers(


            text,


            allow_generic=not bool(qr_result.get("qr_detected")),


            excluded_numbers={qris_nmid} if qris_nmid else set(),


        )


        account_name = detect_account_name(text)


        amounts = detect_amounts(text)


        payment_keywords = detect_payment_keywords(text)


 


        for bank in banks:


            payments.append(bank)


 


        for wallet in ewallets:


            payments.append(wallet)


 


        for phone in phone_numbers:


 


            payments.append({


                "payment_type": "phone",


                "phone_number": phone,


                "verification_status": STATUS_UNVERIFIED,


            })


 


        for account_number in account_numbers:


 


            payments.append({


                "payment_type": "bank_account",


                "account_number": account_number,


                "account_name": account_name,


                "verification_status": STATUS_UNVERIFIED,


            })


 


    # --------------------------------------------------------


    # Unique payment


    # --------------------------------------------------------


 


    unique_payments = []


    seen_keys = set()


 


    for payment in payments:


 


        key = (


            payment.get("payment_type"),


            payment.get("data_hash"),


            payment.get("provider"),


            payment.get("phone_number"),


            payment.get("account_number"),


        )


 


        if key in seen_keys:


            continue


 


        seen_keys.add(key)


        unique_payments.append(payment)


 


    payments = unique_payments


 


    payment_detected = bool(payments)


 


    payment_type = "unknown"


 


    if payments:


 


        payment_type = payments[0].get(


            "payment_type",


            "unknown",


        )


 


    qr_detected = bool(


        qr_result.get("qr_detected", False)


    )


 


    payment_score = calculate_payment_score(


        qr_detected=qr_detected,


        banks=banks,


        ewallets=ewallets,


        account_numbers=account_numbers,


        phone_numbers=phone_numbers,


        payment_keywords=payment_keywords,


        amounts=amounts,


    )


 


    evidence = build_payment_evidence(


        qr_result=qr_result,


        banks=banks,


        ewallets=ewallets,


        account_numbers=account_numbers,


        account_name=account_name,


        phone_numbers=phone_numbers,


        amounts=amounts,


        payment_keywords=payment_keywords,


    )


 


    # --------------------------------------------------------


    # Provider


    # --------------------------------------------------------


 


    provider = None


 


    if banks:


 


        provider = banks[0].get("provider")


 


    elif ewallets:


 


        provider = ewallets[0].get("provider")


 


    elif qr_result.get("payment_type") == "qris":


 


        qris_provider = (


            qr_result.get("qris", {})


            .get("acquirer")


        )


 


        provider = qris_provider or "QRIS"


 


    # --------------------------------------------------------


    # QRIS result


    # --------------------------------------------------------


 


    qris_result = qr_result.get(


        "qris",


        {},


    )


 


    qris_data_quality_status = qris_result.get(

        "data_quality_status",

        "unverifiable",

    )

    qris_technical_checks = qris_result.get(

        "technical_checks",

        {},

    )

    qris_quality_reasons = qris_result.get(

        "reasons",

        [],

    )



    # --------------------------------------------------------


    # Verification


    # --------------------------------------------------------


 


    if payment_detected:


 


        verification_status = STATUS_UNVERIFIED


 


        if (


            qr_detected


            and qr_result.get("payment_type") == "qris"


            and qr_result.get("verification_status") == STATUS_INVALID


        ):


 


            verification_status = STATUS_INVALID


 


    else:


 


        verification_status = STATUS_UNVERIFIED


 


    # --------------------------------------------------------


    # Final result


    # --------------------------------------------------------


 


    result = {


        "payment_detected": payment_detected,


        "payment_score": payment_score,


        "payment_type": payment_type,


        "qr_detected": qr_detected,


 


        "qr_data": qr_result.get(


            "qr_data",


            "",


        ),


 


        "qr_data_hash": qr_result.get(


            "data_hash",


            "",


        ),


 


        "provider": provider,


 


        "account_name": account_name,


        "account_numbers": account_numbers,


        "phone_numbers": phone_numbers,


        "amounts": amounts,


        "payment_keywords": payment_keywords,


 


        "verification_status": verification_status,


        "image_hash": image_hash,


        "evidence": evidence,


        "payments": payments,


        "qris": qris_result,


        "qris_data_quality_status": qris_data_quality_status,

        "qris_technical_checks": qris_technical_checks,

        "qris_quality_reasons": qris_quality_reasons,


    }


 


    print("\n==========================================")


    print("GUARDNET-AI PAYMENT DETECTOR")


    print("==========================================")


    print("Payment Detected:", payment_detected)


    print("Payment Type:", payment_type)


    print("QR Detected:", qr_detected)


    print("Provider:", provider)


    print("Payment Count:", len(payments))


    print("Payment Score:", payment_score)


 


    print(


        "Banks:",


        [item.get("provider") for item in banks],


    )


 


    print(


        "E-Wallets:",


        [item.get("provider") for item in ewallets],


    )


 


    print("Account Numbers:", account_numbers)


    print("Phone Numbers:", phone_numbers)


    print("Amounts:", amounts)


    print("Payment Keywords:", payment_keywords)


 


    print(


        "QRIS Status:",


        qris_result.get("technical_status"),


    )


 


    print(


        "QRIS Merchant:",


        qris_result.get("merchant_name"),


    )


 


    print(


        "QRIS City:",


        qris_result.get("merchant_city"),


    )


 


    print(


        "QRIS NMID:",


        qris_result.get("nmid"),


    )


 


    print(


        "QRIS Acquirer:",


        qris_result.get("acquirer"),


    )


 


    print(


        "QRIS Acquirer Identifier:",


        qris_result.get("acquirer_identifier"),


    )


 


    print(


        "QRIS CRC:",


        qris_result.get("crc", {}),


    )


 


    print("Evidence:", evidence)


    print("Image Hash:", image_hash)


    print("Verification:", verification_status)


    print("==========================================")


 


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


            "status": STATUS_INVALID,


            "message": (


                "Payment evidence awal tidak tersedia."


            ),


        }


 


    if not current_payment:


 


        return {


            "valid": False,


            "status": STATUS_INVALID,


            "message": (


                "Payment baru tidak tersedia."


            ),


        }


 


    original_hash = (


        original_payment.get("data_hash", "")


        or original_payment.get("qr_data_hash", "")


        or ""


    )


 


    current_hash = (


        current_payment.get("data_hash", "")


        or current_payment.get("qr_data_hash", "")


        or ""


    )


 


    if not original_hash:


 


        return {


            "valid": False,


            "status": STATUS_INVALID,


            "message": (


                "Hash payment awal tidak tersedia."


            ),


        }


 


    if not current_hash:


 


        return {


            "valid": False,


            "status": STATUS_INVALID,


            "message": (


                "Hash payment baru tidak tersedia."


            ),


        }


 


    if original_hash == current_hash:


 


        return {


            "valid": True,


            "status": STATUS_MATCHED,


            "original_hash": original_hash,


            "current_hash": current_hash,


            "message": (


                "Payment sesuai dengan evidence awal."


            ),


        }


 


    return {


        "valid": False,


        "status": STATUS_CONFLICT,


        "original_hash": original_hash,


        "current_hash": current_hash,


        "message": (


            "Payment berbeda dengan evidence awal."


        ),


    }