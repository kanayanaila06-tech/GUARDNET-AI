from services.analyzer import analyze_text


tests = [
    "judi online daftar sekarang",
    "slot gacor bonus besar",
    "KASINO DAFTAR SEKARANG BONUS BESAR",
    "kasino",
    "slot",
    "wd",
    "bonus",
    "produk fashion terbaru",
]


for text in tests:

    print("\n")
    print("=" * 70)
    print("TEST:", text)
    print("=" * 70)

    result = analyze_text(text)

    print("RISK:", result["risk_level"])
    print("SCORE:", result["score"])
    print("INDICATORS:")
    
    for indicator in result["detected_indicators"]:
        print("-", indicator)