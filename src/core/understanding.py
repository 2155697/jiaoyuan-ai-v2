"""
教员AI顾问 - 理解层

理解层负责将用户问题映射到教员的思维框架：
- 问题类型判断：分类到教员的问题类型体系
- 认知图谱检索：从知识图谱检索相关方法论
- 框架匹配：匹配最合适的教员思维框架

执行流程（理解层主入口）：
1. 判断问题类型（串行）
2. 匹配思维框架（串行）
3. 检索认知图谱（可与毛选检索并行）
4. 检索毛选相关段落

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from cognitive_graph import CognitiveGraph
from llm_client import OllamaClient
from maoxuan_retriever import MaoxuanRetriever
from models import (
    CaseNode, ConceptNode, FrameworkNode, FrameworkType, MethodNode,
    ProblemProfile, ProblemType, QuoteNode, UserIntent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 问题类型判断器
# ============================================================================

class ProblemTyper:
    """
    问题类型判断器：将用户问题分类到教员的问题类型体系

    两层判断：
    1. 规则层：基于关键词和认知阶段快速匹配
    2. LLM层：基于完整上下文深度判断
    """

    # 问题类型定义（教员思维的问题分类法）
    PROBLEM_TYPES: Dict[ProblemType, Dict[str, Any]] = {
        ProblemType.CONTRADICTION_ANALYSIS: {
            "description": "矛盾分析问题 — 用户面临两难选择或多个冲突因素",
            "indicators": ["纠结", "两难", "冲突", "矛盾", "A还是B", "既想", "又怕", "但是", "却"],
            "keywords": ["矛盾", "冲突", "纠结", "两难", "平衡", "取舍", "权衡"],
            "methodology": "矛盾论 — 区分主要矛盾和次要矛盾，抓主要矛盾",
        },
        ProblemType.INVESTIGATION_RESEARCH: {
            "description": "调查研究问题 — 用户需要收集信息、了解情况",
            "indicators": ["不了解", "不清楚", "想知道", "怎么了解", "调研", "情况", "信息"],
            "keywords": ["调查", "了解", "信息", "情况", "数据", "研究"],
            "methodology": "没有调查就没有发言权 — 实地考察、数据分析",
        },
        ProblemType.PHASE_ASSESSMENT: {
            "description": "阶段判断问题 — 用户需要判断自己所处的阶段",
            "indicators": ["阶段", "时期", "现在怎么办", "走到哪了", "接下来", "还要多久"],
            "keywords": ["阶段", "时期", "进度", "位置", "状态"],
            "methodology": "持久战三阶段 — 战略防御、战略相持、战略反攻",
        },
        ProblemType.STRATEGY_SELECTION: {
            "description": "策略选择问题 — 用户需要在多个方案中选择",
            "indicators": ["选哪个", "方案", "策略", "方法", "怎么干", "如何做", "途径"],
            "keywords": ["选择", "方案", "策略", "方法", "路径", "计划"],
            "methodology": "实事求是 — 根据实际情况选择最优策略",
        },
        ProblemType.CONFIDENCE_BUILDING: {
            "description": "信心建设问题 — 用户缺乏信心、需要鼓励",
            "indicators": ["害怕", "没信心", "怀疑自己", "做不到", "太难了", "不可能"],
            "keywords": ["害怕", "信心", "怀疑", "困难", "坚持", "勇气"],
            "methodology": "战略上藐视敌人，战术上重视敌人 — 建立必胜信念",
        },
        ProblemType.METHODOLOGY_LEARNING: {
            "description": "方法论学习 — 用户想学习教员的思维方法",
            "indicators": ["怎么分析", "怎么思考", "教员怎么做", "方法论", "思维方式"],
            "keywords": ["分析", "思考", "方法", "思维", "学习", "理解"],
            "methodology": "教授方法论而非给答案 — 授人以渔",
        },
    }

    def __init__(self, llm_client: OllamaClient):
        """
        初始化问题类型判断器

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def classify(self, user_intent: UserIntent) -> ProblemType:
        """
        判断问题类型

        两层判断：
        1. 规则层：基于关键词和认知阶段快速匹配
        2. LLM层：基于完整上下文深度判断

        Args:
            user_intent: 用户意图（感知层输出）

        Returns:
            ProblemType问题类型

        耗时目标: <1000ms
        """
        # 第一层：规则判断
        rule_type = self._rule_based_classify(user_intent)
        if rule_type:
            logger.debug("Problem type by rule: %s", rule_type.value)
            return rule_type

        # 第二层：LLM判断
        try:
            return await self._llm_classify(user_intent)
        except Exception as e:
            logger.warning("LLM problem classification failed: %s", e)
            return ProblemType.STRATEGY_SELECTION  # 默认类型

    def _rule_based_classify(self, user_intent: UserIntent) -> Optional[ProblemType]:
        """
        基于关键词规则快速判断问题类型

        Args:
            user_intent: 用户意图

        Returns:
            问题类型，若无高置信度匹配则返回None
        """
        scores: Dict[ProblemType, int] = {}

        for ptype, config in self.PROBLEM_TYPES.items():
            score = 0
            # 关键词匹配
            for indicator in config["indicators"]:
                if indicator in user_intent.raw_input:
                    score += 2
            # 情绪匹配
            if ptype == ProblemType.CONFIDENCE_BUILDING and user_intent.emotion.value in [
                "anxious", "frustrated", "overwhelmed",
            ]:
                score += 2
            if ptype == ProblemType.CONTRADICTION_ANALYSIS and user_intent.emotion.value in [
                "confused", "hesitant",
            ]:
                score += 1
            if score > 0:
                scores[ptype] = score

        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] >= 3:  # 阈值
                return best[0]

        return None

    async def _llm_classify(self, user_intent: UserIntent) -> ProblemType:
        """
        使用LLM深度判断问题类型

        Args:
            user_intent: 用户意图

        Returns:
            ProblemType问题类型
        """
        prompt = f"""你是一个问题分析专家。请判断以下用户问题属于哪种类型，只输出类型名称。

用户输入：{user_intent.raw_input}
用户情绪：{user_intent.emotion.value}
认知阶段：{user_intent.cognitive_stage.value}
关键词：{', '.join(user_intent.keywords)}

可选类型：
- contradiction_analysis: 矛盾分析（面临两难选择、冲突因素）
- investigation_research: 调查研究（需要了解情况、收集信息）
- phase_assessment: 阶段判断（需要判断自己所处阶段）
- strategy_selection: 策略选择（需要在多个方案中选择）
- confidence_building: 信心建设（缺乏信心、需要鼓励）
- methodology_learning: 方法论学习（想学习思维方法）

只输出类型名称（不要其他内容）："""

        response = await self.llm.generate(
            prompt=prompt,
            options={"temperature": 0.3, "num_ctx": 2048},
            thinking=False,
        )

        content = response.get("response", "").strip().lower()

        type_mapping = {
            "contradiction_analysis": ProblemType.CONTRADICTION_ANALYSIS,
            "contradiction": ProblemType.CONTRADICTION_ANALYSIS,
            "矛盾": ProblemType.CONTRADICTION_ANALYSIS,
            "investigation_research": ProblemType.INVESTIGATION_RESEARCH,
            "investigation": ProblemType.INVESTIGATION_RESEARCH,
            "调查": ProblemType.INVESTIGATION_RESEARCH,
            "phase_assessment": ProblemType.PHASE_ASSESSMENT,
            "phase": ProblemType.PHASE_ASSESSMENT,
            "阶段": ProblemType.PHASE_ASSESSMENT,
            "strategy_selection": ProblemType.STRATEGY_SELECTION,
            "strategy": ProblemType.STRATEGY_SELECTION,
            "选择": ProblemType.STRATEGY_SELECTION,
            "confidence_building": ProblemType.CONFIDENCE_BUILDING,
            "confidence": ProblemType.CONFIDENCE_BUILDING,
            "信心": ProblemType.CONFIDENCE_BUILDING,
            "methodology_learning": ProblemType.METHODOLOGY_LEARNING,
            "methodology": ProblemType.METHODOLOGY_LEARNING,
            "方法": ProblemType.METHODOLOGY_LEARNING,
        }

        for key, ptype in type_mapping.items():
            if key in content:
                return ptype

        return ProblemType.STRATEGY_SELECTION


# ============================================================================
# 框架匹配器
# ============================================================================

class FrameworkMatcher:
    """
    框架匹配器：将用户问题匹配到最合适的教员思维框架

    框架匹配逻辑：
    1. 根据problem_type筛选候选框架
    2. 根据关键词匹配度排序
    3. 结合LLM判断最终选择
    """

    # 框架定义
    FRAMEWORKS: Dict[FrameworkType, Dict[str, Any]] = {
        FrameworkType.FIVE_LAYER_ANALYSIS: {
            "name": "五层分析框架",
            "description": "目标→方案→环节→需求→因素→评估",
            "applicable_types": [
                ProblemType.STRATEGY_SELECTION,
                ProblemType.CONTRADICTION_ANALYSIS,
                ProblemType.INVESTIGATION_RESEARCH,
            ],
            "trigger_keywords": ["怎么做", "方案", "计划", "目标", "步骤", "评估"],
        },
        FrameworkType.CONTRADICTION_THEORY: {
            "name": "矛盾论",
            "description": "区分主要矛盾和次要矛盾，矛盾的主要方面和次要方面",
            "applicable_types": [
                ProblemType.CONTRADICTION_ANALYSIS,
            ],
            "trigger_keywords": ["矛盾", "纠结", "两难", "冲突", "取舍", "权衡"],
        },
        FrameworkType.PROTRACTED_WAR: {
            "name": "持久战理论",
            "description": "战略防御→战略相持→战略反攻的三阶段论",
            "applicable_types": [
                ProblemType.PHASE_ASSESSMENT,
                ProblemType.CONFIDENCE_BUILDING,
            ],
            "trigger_keywords": ["阶段", "长期", "坚持", "持久战", "进度", "状态"],
        },
        FrameworkType.INVESTIGATION_METHOD: {
            "name": "调查研究方法",
            "description": "没有调查就没有发言权，从实际出发",
            "applicable_types": [
                ProblemType.INVESTIGATION_RESEARCH,
            ],
            "trigger_keywords": ["了解", "调查", "实际情况", "数据", "信息"],
        },
        FrameworkType.MASS_LINE: {
            "name": "群众路线",
            "description": "从群众中来，到群众中去，集中力量",
            "applicable_types": [
                ProblemType.STRATEGY_SELECTION,
                ProblemType.CONFIDENCE_BUILDING,
            ],
            "trigger_keywords": ["团队", "大家", "群众", "力量", "支持", "合作"],
        },
        FrameworkType.INDEPENDENT_THINKING: {
            "name": "独立思考",
            "description": "实事求是，反对教条主义",
            "applicable_types": [
                ProblemType.METHODOLOGY_LEARNING,
                ProblemType.CONFIDENCE_BUILDING,
            ],
            "trigger_keywords": ["思考", "分析", "独立", "判断", "思维"],
        },
    }

    def __init__(self, llm_client: OllamaClient):
        """
        初始化框架匹配器

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def match(self, user_intent: UserIntent, problem_type: ProblemType) -> FrameworkType:
        """
        匹配最适合的思维框架

        Args:
            user_intent: 用户意图
            problem_type: 问题类型

        Returns:
            FrameworkType思维框架类型

        耗时目标: <1000ms
        """
        # 第一层：基于问题类型和关键词的候选框架排序
        candidates = self._get_candidates(problem_type, user_intent.keywords)

        if candidates and candidates[0]["score"] >= 3:
            logger.debug("Framework matched by rule: %s", candidates[0]["framework"].value)
            return candidates[0]["framework"]

        # 第二层：LLM判断
        try:
            return await self._llm_match(user_intent, problem_type, candidates)
        except Exception as e:
            logger.warning("LLM framework match failed: %s", e)

        # Fallback: 返回得分最高的候选
        return candidates[0]["framework"] if candidates else FrameworkType.FIVE_LAYER_ANALYSIS

    def _get_candidates(
        self,
        problem_type: ProblemType,
        keywords: List[str],
    ) -> List[Dict[str, Any]]:
        """
        获取候选框架列表（按匹配分数排序）

        Args:
            problem_type: 问题类型
            keywords: 关键词列表

        Returns:
            候选框架列表，每项包含framework和score
        """
        candidates = []

        for fw_type, config in self.FRAMEWORKS.items():
            score = 0

            # 问题类型匹配
            if problem_type in config["applicable_types"]:
                score += 3

            # 关键词匹配
            for kw in keywords:
                if any(tk in kw for tk in config["trigger_keywords"]):
                    score += 2

            candidates.append({"framework": fw_type, "score": score, "name": config["name"]})

        candidates.sort(key=lambda x: -x["score"])
        return candidates

    async def _llm_match(
        self,
        user_intent: UserIntent,
        problem_type: ProblemType,
        candidates: List[Dict[str, Any]],
    ) -> FrameworkType:
        """
        使用LLM进行框架匹配

        Args:
            user_intent: 用户意图
            problem_type: 问题类型
            candidates: 候选框架列表

        Returns:
            FrameworkType
        """
        candidate_str = "\n".join([
            f"- {c['framework'].value}: {c['name']}" for c in candidates[:3]
        ])

        prompt = f"""你是教员思维框架匹配专家。请为以下问题选择最合适的分析框架。

用户问题：{user_intent.raw_input}
问题类型：{problem_type.value}
用户情绪：{user_intent.emotion.value}

候选框架：
{candidate_str}

只输出框架名称（不要其他内容）："""

        response = await self.llm.generate(
            prompt=prompt,
            options={"temperature": 0.3, "num_ctx": 2048},
            thinking=False,
        )

        content = response.get("response", "").strip().lower()

        for fw_type in FrameworkType:
            if fw_type.value in content:
                return fw_type

        # Fallback: 返回最高分的候选
        return candidates[0]["framework"] if candidates else FrameworkType.FIVE_LAYER_ANALYSIS


# ============================================================================
# 认知图谱检索器
# ============================================================================

class KGRetriever:
    """
    认知图谱检索器：封装CognitiveGraph的检索接口

    为理解层提供简化的检索接口。
    """

    def __init__(self, cognitive_graph: CognitiveGraph):
        """
        初始化认知图谱检索器

        Args:
            cognitive_graph: 认知图谱实例
        """
        self.kg = cognitive_graph

    async def retrieve(
        self,
        query: str,
        problem_type: str,
        framework: str,
        keywords: List[str],
        top_k: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        检索认知图谱

        Args:
            query: 查询文本
            problem_type: 问题类型
            framework: 思维框架
            keywords: 关键词
            top_k: 返回数量

        Returns:
            检索结果字典
        """
        # 检索相关方法论
        methods = self.kg.retrieve_methods(problem_type, keywords, top_k=top_k)

        return {
            "methods": methods,
            "scores": {m.get("id", ""): m.get("relevance_score", 0) for m in methods},
        }


# ============================================================================
# 理解层统一入口
# ============================================================================

class UnderstandingLayer:
    """
    理解层：整合问题类型判断、框架匹配、认知图谱检索

    执行流程：
    1. 判断问题类型
    2. 匹配思维框架
    3. 检索认知图谱
    4. 检索毛选相关段落

    总耗时目标: <3000ms
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        cognitive_graph: CognitiveGraph,
        maoxuan_retriever: MaoxuanRetriever,
    ):
        """
        初始化理解层

        Args:
            llm_client: Ollama LLM客户端
            cognitive_graph: 认知图谱实例
            maoxuan_retriever: 毛选检索器实例
        """
        self.problem_typer = ProblemTyper(llm_client)
        self.framework_matcher = FrameworkMatcher(llm_client)
        self.kg_retriever = KGRetriever(cognitive_graph)
        self.maoxuan_retriever = maoxuan_retriever

        logger.info("UnderstandingLayer initialized")

    async def understand(self, user_intent: UserIntent) -> ProblemProfile:
        """
        理解层主入口

        Args:
            user_intent: 用户意图（感知层输出）

        Returns:
            ProblemProfile问题画像
        """
        import time
        start_time = time.time()

        # 步骤1：判断问题类型
        problem_type = await self.problem_typer.classify(user_intent)
        logger.debug("Problem type: %s", problem_type.value)

        # 步骤2：匹配思维框架
        framework = await self.framework_matcher.match(user_intent, problem_type)
        logger.debug("Framework: %s", framework.value)

        # 步骤3+4：并行检索认知图谱和毛选
        kg_task = self.kg_retriever.retrieve(
            query=user_intent.topic,
            problem_type=problem_type.value,
            framework=framework.value,
            keywords=user_intent.keywords,
            top_k=5,
        )
        maoxuan_task = self.maoxuan_retriever.retrieve(
            query=user_intent.raw_input,
            top_k=3,
        )

        kg_results, maoxuan_results = await asyncio.gather(
            kg_task, maoxuan_task,
            return_exceptions=True,
        )

        if isinstance(kg_results, Exception):
            logger.error("KG retrieval failed: %s", kg_results)
            kg_results = {"methods": [], "scores": {}}

        if isinstance(maoxuan_results, Exception):
            logger.error("Maoxuan retrieval failed: %s", maoxuan_results)
            maoxuan_results = []

        elapsed = int((time.time() - start_time) * 1000)
        logger.info("UnderstandingLayer completed in %dms", elapsed)

        # 组装问题画像
        return ProblemProfile(
            problem_type=problem_type,
            framework=framework,
            framework_confidence=0.8,  # TODO: 从匹配器获取置信度
            related_methods=[
                MethodNode(**m) for m in kg_results.get("methods", [])
                if m.get("type") == "Method"
            ],
            related_concepts=[
                ConceptNode(**m) for m in kg_results.get("methods", [])
                if m.get("type") == "Concept"
            ],
            related_cases=[
                CaseNode(**m) for m in kg_results.get("methods", [])
                if m.get("type") == "Case"
            ],
            related_quotes=[
                QuoteNode(**m) for m in kg_results.get("methods", [])
                if m.get("type") == "Quote"
            ],
            maoxuan_refs=maoxuan_results if isinstance(maoxuan_results, list) else [],
            relevance_scores=kg_results.get("scores", {}),
            problem_summary=f"{user_intent.topic}（{user_intent.domain}领域）- {problem_type.value}",
        )
