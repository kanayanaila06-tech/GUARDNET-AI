import pytesseract
from PIL import Image

image = Image.open("test.jpg")

text = pytesseract.image_to_string(
    image,
    config="--psm 6"
)

print("HASIL OCR:")
print(text)