import base64
import json
import urllib.request


# =====================================================
# KONFIGURASI
# =====================================================

API_URL = "http://127.0.0.1:8000/ocr"
IMAGE_PATH = "test.png"


# =====================================================
# BACA GAMBAR
# =====================================================

with open(IMAGE_PATH, "rb") as image_file:
    image_data = image_file.read()


# =====================================================
# CONVERT KE BASE64
# =====================================================

image_base64 = base64.b64encode(
    image_data
).decode("utf-8")


# =====================================================
# DATA REQUEST
# =====================================================

payload = {
    "image": f"data:image/png;base64,{image_base64}"
}


# =====================================================
# REQUEST KE FASTAPI
# =====================================================

request = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json"
    },
    method="POST"
)


# =====================================================
# KIRIM REQUEST
# =====================================================

print("========================================")
print("TEST API OCR GUARDNET-AI")
print("========================================")

try:

    with urllib.request.urlopen(request) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )


        print()
        print("STATUS:", response.status)

        print()
        print("HASIL RESPONSE:")
        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            )
        )


except Exception as error:

    print()
    print("OCR API ERROR:")
    print(error)