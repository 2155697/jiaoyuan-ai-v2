import json
import os

def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    json_path = os.path.join(data_dir, "maoxuan_articles.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        total = sum(a.get("word_count", 0) for a in articles)
        print("Knowledge base: %d articles, %d chars" % (len(articles), total))
        return
    all_a = []
    for vol in [1,2,3,4]:
        p = os.path.join(data_dir, "maoxuan_vol%d.pdf" % vol)
        if not os.path.exists(p): continue
        print("Processing vol %d..." % vol)
        try:
            import fitz
            doc = fitz.open(p)
            text = ""
            for page in doc:
                text += page.get_text()
            paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]
            combined = "\n".join(paragraphs[:100])
            all_a.append({"volume": vol, "title": "Vol %d" % vol, "text": combined, "word_count": len(combined)})
            print("  Extracted (%d chars)" % len(text))
        except Exception as e:
            print("  Skipped: %s" % e)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_a, f, ensure_ascii=False, indent=2)
    total = sum(a["word_count"] for a in all_a)
    print("Done! %d articles, %d chars" % (len(all_a), total))

if __name__ == "__main__":
    main()
