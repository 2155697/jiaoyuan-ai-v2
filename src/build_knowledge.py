import chromadb
import json
import os

def main():
    project_dir = os.path.join(os.path.dirname(__file__), '..')
    chroma_path = os.path.join(project_dir, 'knowledge', 'chroma_db')
    data_path = os.path.join(project_dir, 'data', 'maoxuan_articles.json')

    if not os.path.exists(data_path):
        print("错误: 先运行 extract_pdf.py")
        return

    print("构建知识库...")
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    try:
        chroma_client.delete_collection("maoxuan")
    except:
        pass
    collection = chroma_client.create_collection("maoxuan")

    with open(data_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    docs, metas, ids, idx = [], [], [], 0
    for article in articles:
        text = article['text']
        sentences = [s.strip() for s in text.split('。') if len(s.strip()) > 10]
        para, cnt = "", 0
        for s in sentences:
            para += s + "。"
            cnt += 1
            if cnt >= 5 or len(para) > 500:
                if len(para) > 100:
                    docs.append(para)
                    metas.append({"title": article['title'], "volume": str(article['volume'])})
                    ids.append(f"d{idx}")
                    idx += 1
                para, cnt = "", 0
        if para and len(para) > 100:
            docs.append(para)
            metas.append({"title": article['title'], "volume": str(article['volume'])})
            ids.append(f"d{idx}")
            idx += 1

    print(f"存入{len(docs)}个片段...")
    for i in range(0, len(docs), 100):
        e = min(i+100, len(docs))
        collection.add(documents=docs[i:e], metadatas=metas[i:e], ids=ids[i:e])
        print(f"  {e}/{len(docs)}")

    print(f"\n知识库构建完成! 共{len(docs)}条记录")

if __name__ == "__main__":
    main()
