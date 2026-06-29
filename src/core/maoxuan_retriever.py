"""
教员AI顾问 - 毛选向量库检索

基于ChromaDB的毛选原文向量检索，使用Sentence-Transformers生成嵌入向量。
支持语义检索，能够找到与用户查询语义相关的毛选段落。

特性：
- 使用ChromaDB轻量级向量数据库
- 基于all-MiniLM-L6-v2模型生成嵌入（约80MB，适合本地运行）
- 支持增量索引构建
- 异步接口

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

from models import MaoxuanRef

logger = logging.getLogger(__name__)


# ============================================================================
# 内置毛选核心段落（默认数据）
# ============================================================================

DEFAULT_MAOXUAN_PASSAGES: List[Dict[str, str]] = [
    {
        "source": "《中国社会各阶级的分析》",
        "chapter": "开篇",
        "year": "1925",
        "text": "谁是我们的敌人？谁是我们的朋友？这个问题是革命的首要问题。中国过去一切革命斗争成效甚少，其基本原因就是因为不能团结真正的朋友，以攻击真正的敌人。",
    },
    {
        "source": "《湖南农民运动考察报告》",
        "chapter": "农民问题的严重性",
        "year": "1927",
        "text": "很短的时间内，将有几万万农民从中国中部、南部和北部各省起来，其势如暴风骤雨，迅猛异常，无论什么大的力量都将压抑不住。他们将冲决一切束缚他们的罗网，朝着解放的路上迅跑。",
    },
    {
        "source": "《星星之火，可以燎原》",
        "chapter": "对时局的估量",
        "year": "1930",
        "text": "它是站在海岸遥望海中已经看得见桅杆尖头了的一只航船，它是立于高山之巅远看东方已见光芒四射喷薄欲出的一轮朝日，它是躁动于母腹中的快要成熟了的一个婴儿。",
    },
    {
        "source": "《反对本本主义》",
        "chapter": "没有调查，没有发言权",
        "year": "1930",
        "text": "没有调查，没有发言权。你对于某个问题没有调查，就停止你对于某个问题的发言权。这不太野蛮了吗？一点也不野蛮。你对那个问题的现实情况和历史情况既然没有调查，不知底里，对于那个问题的发言便一定是瞎说一顿。",
    },
    {
        "source": "《中国革命战争的战略问题》",
        "chapter": "战略退却",
        "year": "1936",
        "text": "战略退却，是劣势军队处在优势军队进攻面前，因为顾到不能迅速地击破其进攻，为了保存军力，待机破敌，而采取的一个有计划的战略步骤。",
    },
    {
        "source": "《矛盾论》",
        "chapter": "主要的矛盾和主要的矛盾方面",
        "year": "1937",
        "text": "研究任何过程，如果是存在着两个以上矛盾的复杂过程的话，就要用全力找出它的主要矛盾。捉住了这个主要矛盾，一切问题就迎刃而解了。",
    },
    {
        "source": "《矛盾论》",
        "chapter": "主要的矛盾和主要的矛盾方面",
        "year": "1937",
        "text": "事物的性质，主要地是由取得支配地位的矛盾的主要方面所规定的。取得支配地位的矛盾的主要方面起了变化，事物的性质也就随着起变化。",
    },
    {
        "source": "《实践论》",
        "chapter": "认识的过程",
        "year": "1937",
        "text": "实践、认识、再实践、再认识，这种形式，循环往复以至无穷，而实践和认识之每一循环的内容，都比较地进到了高一级的程度。这就是辩证唯物论的全部认识论。",
    },
    {
        "source": "《论持久战》",
        "chapter": "问题的提起",
        "year": "1938",
        "text": "战争的伟力之最深厚的根源，存在于民众之中。日本敢于欺负我们，主要的原因在于中国民众的无组织状态。克服了这一缺点，就把日本侵略者置于我们数万万站起来了的人民之前，使它像一匹野牛冲入火阵，我们一声唤也要把它吓一大跳，这匹野牛就非烧死不可。",
    },
    {
        "source": "《论持久战》",
        "chapter": "持久战的三个阶段",
        "year": "1938",
        "text": "这个战争要延长多久呢？要看中国抗日统一战线的实力和中日两国其他许多决定的因素如何而定。如果这些条件不能很快实现，战争就要延长。但结果还是一样，日本必败，中国必胜。只是牺牲会大，要经过一个很痛苦的时期。",
    },
    {
        "source": "《论持久战》",
        "chapter": "兵民是胜利之本",
        "year": "1938",
        "text": "武器是战争的重要的因素，但不是决定的因素，决定的因素是人不是物。力量对比不但是军力和经济力的对比，而且是人力和人心的对比。",
    },
    {
        "source": "《〈共产党人〉发刊词》",
        "chapter": "三大法宝",
        "year": "1939",
        "text": "统一战线，武装斗争，党的建设，是中国共产党在中国革命中战胜敌人的三个法宝，三个主要的法宝。这是中国共产党的伟大成绩，也是中国革命的伟大成绩。",
    },
    {
        "source": "《改造我们的学习》",
        "chapter": "实事求是",
        "year": "1941",
        "text": "'实事'就是客观存在着的一切事物，'是'就是客观事物的内部联系，即规律性，'求'就是我们去研究。我们要从国内外、省内外、县内外、区内外的实际情况出发，从其中引出其固有的而不是臆造的规律性。",
    },
    {
        "source": "《整顿党的作风》",
        "chapter": "反对主观主义",
        "year": "1942",
        "text": "学风问题是领导机关、全体干部、全体党员的思想方法问题，是我们对待马克思列宁主义的态度问题，是全党同志的工作态度问题。",
    },
    {
        "source": "《为人民服务》",
        "chapter": "完全彻底为人民服务",
        "year": "1944",
        "text": "我们的共产党和共产党所领导的八路军、新四军，是革命的队伍。我们这个队伍完全是为着解放人民的，是彻底地为人民的利益工作的。",
    },
    {
        "source": "《论联合政府》",
        "chapter": "党的三大作风",
        "year": "1945",
        "text": "以马克思列宁主义的理论思想武装起来的中国共产党，在中国人民中产生了新的工作作风，这主要的就是理论和实践相结合的作风，和人民群众紧密地联系在一起的作风以及自我批评的作风。",
    },
    {
        "source": "《抗日战争胜利后的时局和我们的方针》",
        "chapter": "针锋相对，寸土必争",
        "year": "1945",
        "text": "凡是反动的东西，你不打，他就不倒。这也和扫地一样，扫帚不到，灰尘照例不会自己跑掉。",
    },
    {
        "source": "《和美国记者安娜·路易斯·斯特朗的谈话》",
        "chapter": "一切反动派都是纸老虎",
        "year": "1946",
        "text": "一切反动派都是纸老虎。看起来，反动派的样子是可怕的，但是实际上并没有什么了不起的力量。从长远的观点看问题，真正强大的力量不是属于反动派，而是属于人民。",
    },
    {
        "source": "《关于正确处理人民内部矛盾的问题》",
        "chapter": "两类不同性质的矛盾",
        "year": "1957",
        "text": "战略上要藐视敌人，战术上要重视敌人。",
    },
    {
        "source": "《关于领导方法的若干问题》",
        "chapter": "群众路线",
        "year": "1943",
        "text": "在我党的一切实际工作中，凡属正确的领导，必须是从群众中来，到群众中去。这就是说，将群众的意见（分散的无系统的意见）集中起来（经过研究，化为集中的系统的意见），又到群众中去作宣传解释，化为群众的意见，使群众坚持下去，见之于行动。",
    },
    {
        "source": "《必须学会做经济工作》",
        "chapter": "艰苦奋斗",
        "year": "1945",
        "text": "我们共产党员无论在什么问题上，一定要能够同群众相结合。如果我们的党员，一生一世坐在房子里不出去，不经风雨，不见世面，这种党员，对于中国人民究竟有什么好处没有呢？一点好处也没有的，我们不需要这样的人做党员。",
    },
    {
        "source": "《中国革命战争的战略问题》",
        "chapter": "战略与战术",
        "year": "1936",
        "text": "为了进攻而防御，为了前进而后退，为了向正面而向侧面，为了走直路而走弯路，是许多事物在发展过程中所不可避免的现象，何况军事运动。",
    },
    {
        "source": "《在延安文艺座谈会上的讲话》",
        "chapter": "文艺为工农兵服务",
        "year": "1942",
        "text": "我们的问题基本上是一个为群众的问题和一个如何为群众的问题。不解决这两个问题，或这两个问题解决得不适当，就会使得我们的文艺工作者和自己的环境、任务不协调，就使得我们的文艺工作者从外部从内部碰到一连串的问题。",
    },
    {
        "source": "《矛盾论》",
        "chapter": "矛盾的普遍性",
        "year": "1937",
        "text": "矛盾存在于一切事物的发展过程中；每一事物的发展过程中存在着自始至终的矛盾运动。没有什么事物是不包含矛盾的，没有矛盾就没有世界。",
    },
    {
        "source": "《矛盾论》",
        "chapter": "矛盾的特殊性",
        "year": "1937",
        "text": "不同质的矛盾，只有用不同质的方法才能解决。过程变化，旧过程和旧矛盾消灭，新过程和新矛盾发生，解决矛盾的方法也因之而不同。",
    },
    {
        "source": "《论反对日本帝国主义的策略》",
        "chapter": "统一战线的必要性",
        "year": "1935",
        "text": "组织千千万万的民众，调动浩浩荡荡的革命军，是今天的革命向反革命进攻的需要。",
    },
    {
        "source": "《丢掉幻想，准备斗争》",
        "chapter": "帝国主义的本性",
        "year": "1949",
        "text": "捣乱，失败，再捣乱，再失败，直至灭亡——这就是帝国主义和世界上一切反动派对待人民事业的逻辑，他们决不会违背这个逻辑的。",
    },
    {
        "source": "《唯心历史观的破产》",
        "chapter": "中国革命发生的原因",
        "year": "1949",
        "text": "世间一切事物中，人是第一个可宝贵的。在共产党领导下，只要有了人，什么人间奇迹也可以造出来。",
    },
    {
        "source": "《关于正确处理人民内部矛盾的问题》",
        "chapter": "百花齐放，百家争鸣",
        "year": "1957",
        "text": "坏事可以变成好事。矛盾着的对立的双方互相斗争的结果，无不在一定条件下互相转化。在这里，条件是重要的。没有一定的条件，斗争着的双方都不会转化。",
    },
    {
        "source": "《学习和时局》",
        "chapter": "总结经验",
        "year": "1944",
        "text": "列宁说，对于具体情况作具体的分析，是'马克思主义的最本质的东西、马克思主义的活的灵魂'。我们许多同志缺乏分析的头脑，对于复杂事物，不愿作反复深入的分析研究，而爱作绝对肯定或绝对否定的简单结论。",
    },
    {
        "source": "《井冈山的斗争》",
        "chapter": "割据地区的现状",
        "year": "1928",
        "text": "在统治阶级内部发生破裂时期，我们的战略可以比较地冒进；在统治阶级政权比较稳定的时候，我们的战略必须是逐渐地推进的。",
    },
]


# ============================================================================
# 毛选向量检索器
# ============================================================================

class MaoxuanRetriever:
    """
    毛选向量库检索器

    基于ChromaDB实现语义检索，使用Sentence-Transformers生成嵌入向量。
    内置30条毛选核心段落作为默认数据。

    用法：
        # 创建并构建索引
        retriever = MaoxuanRetriever(db_path="./data/maoxuan")
        retriever.build_index()  # 使用内置数据

        # 检索
        results = await retriever.retrieve("如何分析矛盾", top_k=3)
        for ref in results:
            print(f"[{ref.source}] {ref.text}")
    """

    def __init__(
        self,
        db_path: str = "./data/maoxuan/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "maoxuan",
    ):
        """
        初始化毛选检索器

        Args:
            db_path: ChromaDB持久化路径
            embedding_model: Sentence-Transformers模型名
            collection_name: ChromaDB集合名
        """
        self.db_path = db_path
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name
        self._collection: Optional[Any] = None
        self._embedding_model: Optional[Any] = None
        self._index_built = False

        # 尝试导入依赖（延迟加载）
        self._chromadb = None
        self._sentence_transformers = None

        logger.info(
            "MaoxuanRetriever initialized: db_path=%s, model=%s",
            db_path, embedding_model,
        )

        # 自动构建索引（如果数据库为空）
        try:
            self._ensure_dependencies()
            collection = self._get_collection()
            if collection.count() == 0:
                logger.info("Maoxuan database empty, auto-building index...")
                self.build_index()
        except Exception as e:
            logger.warning("Auto-build index failed (dependencies may not be installed): %s", e)

    def _ensure_dependencies(self) -> None:
        """确保依赖已导入"""
        if self._chromadb is None:
            try:
                import chromadb
                from chromadb.config import Settings
                self._chromadb = chromadb
                self._chroma_settings = Settings
            except ImportError:
                raise ImportError(
                    "chromadb is required. Install with: pip install chromadb"
                )

        if self._sentence_transformers is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._sentence_transformers = SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )

    def _get_embedding_model(self) -> Any:
        """获取/创建嵌入模型"""
        if self._embedding_model is None:
            self._ensure_dependencies()
            logger.info("Loading embedding model: %s", self.embedding_model_name)
            self._embedding_model = self._sentence_transformers(self.embedding_model_name)
        return self._embedding_model

    def _get_collection(self) -> Any:
        """获取/创建ChromaDB集合"""
        if self._collection is None:
            self._ensure_dependencies()
            os.makedirs(self.db_path, exist_ok=True)

            client = self._chromadb.PersistentClient(
                path=self.db_path,
                settings=self._chroma_settings(anonymized_telemetry=False),
            )

            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "毛泽东选集向量库"},
            )
            logger.debug("ChromaDB collection ready: %s", self.collection_name)

        return self._collection

    def build_index(
        self,
        texts: Optional[List[Dict[str, str]]] = None,
        force_rebuild: bool = False,
    ) -> None:
        """
        构建向量索引

        Args:
            texts: 自定义文本列表，None则使用内置数据
            force_rebuild: 是否强制重建索引
        """
        self._ensure_dependencies()
        collection = self._get_collection()
        model = self._get_embedding_model()

        passages = texts or DEFAULT_MAOXUAN_PASSAGES

        # 检查是否已有数据
        if not force_rebuild:
            existing = collection.count()
            if existing > 0:
                logger.info("Index already exists with %d documents, skipping build", existing)
                self._index_built = True
                return

        logger.info("Building index with %d passages...", len(passages))

        # 准备数据
        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for i, passage in enumerate(passages):
            doc_id = f"maoxuan_{i}"
            text = passage["text"]
            source = passage.get("source", "")

            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                "source": source,
                "chapter": passage.get("chapter", ""),
                "year": passage.get("year", ""),
                "index": i,
            })
            # 预计算embedding
            embedding = model.encode(text).tolist()
            embeddings.append(embedding)

        # 添加到ChromaDB
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        self._index_built = True
        logger.info("Index built: %d passages indexed", len(passages))

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_relevance: float = 0.0,
    ) -> List[MaoxuanRef]:
        """
        语义检索毛选相关段落

        Args:
            query: 查询文本
            top_k: 返回数量
            min_relevance: 最小相关度阈值

        Returns:
            毛选引用列表
        """
        if not self._index_built:
            self.build_index()

        model = self._get_embedding_model()
        collection = self._get_collection()

        # 生成查询向量
        query_embedding = model.encode(query).tolist()

        # 执行检索
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        # 解析结果
        refs = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.5

                # 距离转相似度 (cosine distance -> similarity)
                similarity = 1.0 - distance
                if similarity < min_relevance:
                    continue

                ref = MaoxuanRef(
                    source=metadata.get("source", ""),
                    text=doc,
                    relevance_score=similarity,
                    chapter=metadata.get("chapter", ""),
                    year=metadata.get("year", ""),
                )
                refs.append(ref)

        logger.debug(
            "Maoxuan retrieve: query='%s...', found=%d",
            query[:30], len(refs),
        )
        return refs

    def add_passages(self, passages: List[Dict[str, str]]) -> None:
        """
        增量添加段落

        Args:
            passages: 段落列表，每项包含text, source, chapter, year
        """
        self._ensure_dependencies()
        collection = self._get_collection()
        model = self._get_embedding_model()

        existing_count = collection.count()

        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for i, passage in enumerate(passages):
            doc_id = f"maoxuan_{existing_count + i}"
            text = passage["text"]

            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                "source": passage.get("source", ""),
                "chapter": passage.get("chapter", ""),
                "year": passage.get("year", ""),
                "index": existing_count + i,
            })
            embeddings.append(model.encode(text).tolist())

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        logger.info("Added %d passages to index", len(passages))

    def get_stats(self) -> Dict[str, Any]:
        """获取检索器统计信息"""
        try:
            collection = self._get_collection()
            count = collection.count()
        except Exception:
            count = 0

        return {
            "db_path": self.db_path,
            "embedding_model": self.embedding_model_name,
            "collection_name": self.collection_name,
            "document_count": count,
            "index_built": self._index_built,
        }
