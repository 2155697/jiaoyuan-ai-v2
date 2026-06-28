import json
import os

def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    json_path = os.path.join(data_dir, 'maoxuan_articles.json')
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        total = sum(a.get('word_count', 0) for a in articles)
        print(f"已有知识库: {len(articles)}篇, {total}字")
        return
    all_a = []
    for vol in [1,2,3,4]:
        p = os.path.join(data_dir, f'maoxuan_vol{vol}.pdf')
        if not os.path.exists(p):
            continue
        print(f"处理第{vol}卷...")
        try:
            import fitz
            doc = fitz.open(p)
            text = ""
            for page in doc:
                text += page.get_text()
            paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]
            combined = '\n'.join(paragraphs[:100])
            all_a.append({"volume": vol, "title": f"第{vol}卷", "text": combined, "word_count": len(combined)})
            print(f"  已提取({len(text)}字)")
        except Exception as e:
            print(f"  跳过: {e}")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_a, f, ensure_ascii=False, indent=2)
    total = sum(a['word_count'] for a in all_a)
    print(f"\n完成! 共{len(all_a)}篇, {total}字")

if __name__ == "__main__":
    main()
