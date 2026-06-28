"""
教员AI顾问 - 感知层

感知层负责捕获用户输入的深层信息：
- 语义解析：提取主题、关键词、实体
- 情感探测：识别情绪状态和强度
- 意图分类：判断认知阶段和隐含需求

三个子模块并行执行，总耗时目标 < 2000ms。

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from llm_client import OllamaClient
from models import (
    CognitiveStage, EmotionType, IntentClassificationResult,
    SemanticParseResult, EmotionDetectionResult, UserIntent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 领域映射
# ============================================================================

DOMAIN_KEYWORDS = {
    "创业": ["创业", "生意", "项目", "公司", "产品", "开店", "投资", "融资", "商业模式"],
    "职场": ["工作", "职业", "升职", "跳槽", "薪资", "面试", "简历", "同事", "领导", "加班"],
    "学习": ["读书", "学习", "考试", "技能", "提升", "知识", "专业", "考研", "证书"],
    "人际": ["关系", "沟通", "团队", "领导", "同事", "朋友", "家庭", "父母", "恋爱"],
    "决策": ["选择", "决定", "纠结", "犹豫", "担心", "选哪个", "怎么办", "如何"],
    "困境": ["困难", "危机", "压力", "焦虑", "迷茫", "失败", "挫折", "瓶颈", "低谷"],
    "健康": ["健康", "身体", "锻炼", "减肥", "睡眠", "饮食", "疾病", "心理"],
    "财务": ["钱", "理财", "投资", "债务", "储蓄", "收入", "支出", "房价"],
}


# ============================================================================
# 语义解析器
# ============================================================================

class SemanticParser:
    """
    语义解析器：提取主题、关键词、命名实体和所属领域

    使用LLM进行结构化提取，同时配合规则进行领域映射。
    """

    # 语义解析Prompt模板
    SEMANTIC_PARSE_PROMPT = """你是一个语义解析专家。请从用户输入中提取关键信息，以JSON格式输出。

要求：
1. topic: 核心主题，10字以内，概括用户谈论的核心内容
2. keywords: 提取3-8个关键词，包括名词、动词和关键概念
3. entities: 涉及的领域、行业、人名、组织名等实体
4. domain: 所属领域，只能从以下选择：创业、职场、学习、人际、决策、困境、健康、财务、general

用户输入：{user_input}

请直接输出JSON，不要其他内容：
{{"topic": "...", "keywords": [...], "entities": [...], "domain": "..."}}"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化语义解析器

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def parse(self, user_input: str) -> SemanticParseResult:
        """
        解析用户输入的语义内容

        Args:
            user_input: 用户原始输入

        Returns:
            SemanticParseResult语义解析结果

        耗时目标: <500ms
        """
        if not user_input or not user_input.strip():
            return SemanticParseResult(
                topic="未知",
                keywords=[],
                entities=[],
                domain="general",
            )

        try:
            prompt = self.SEMANTIC_PARSE_PROMPT.format(user_input=user_input)
            response = await self.llm.generate(
                prompt=prompt,
                options={"temperature": 0.3, "num_ctx": 2048},
                thinking=False,
            )

            content = response.get("response", "")

            # 解析JSON
            result = self._extract_json(content)
            if result:
                return SemanticParseResult(
                    topic=result.get("topic", "未知") or "未知",
                    keywords=result.get("keywords", []),
                    entities=result.get("entities", []),
                    domain=result.get("domain", "general") or "general",
                )

        except Exception as e:
            logger.warning("LLM semantic parse failed: %s, using fallback", e)

        # Fallback: 基于规则的解析
        return self._rule_based_parse(user_input)

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应内容中提取JSON"""
        # 尝试直接解析
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从文本中提取JSON对象
        json_match = re.search(r'\{[^{}]*"topic"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _rule_based_parse(self, user_input: str) -> SemanticParseResult:
        """基于规则的语义解析（fallback）"""
        # 提取关键词（简单分词）
        words = re.findall(r'[\u4e00-\u9fff]{2,}', user_input)
        keywords = list(set([w for w in words if len(w) >= 2]))[:8]

        # 领域映射
        domain = self._extract_domain(keywords)

        # 主题（取前10字）
        topic = user_input[:10] if len(user_input) <= 10 else user_input[:10] + "..."

        return SemanticParseResult(
            topic=topic,
            keywords=keywords,
            entities=[],
            domain=domain,
        )

    def _extract_domain(self, keywords: List[str]) -> str:
        """根据关键词映射到领域分类"""
        domain_scores: Dict[str, int] = {}
        for domain, domain_keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if any(dk in kw for dk in domain_keywords))
            if score > 0:
                domain_scores[domain] = score

        if domain_scores:
            return max(domain_scores.items(), key=lambda x: x[1])[0]
        return "general"


# ============================================================================
# 情感探测器
# ============================================================================

class EmotionDetector:
    """
    情感探测器：识别用户情绪状态和潜台词

    两层检测策略：
    1. 规则层：关键词匹配（快速路径，<100ms）
    2. LLM层：深度情绪分析（慢速路径，<1500ms）
    """

    # 情绪关键词映射
    EMOTION_KEYWORDS: Dict[EmotionType, List[str]] = {
        EmotionType.CONFUSED: ["迷茫", "不知道", "不确定", "困惑", "纠结", "不清楚", "怎么办", "到底"],
        EmotionType.ANXIOUS: ["担心", "焦虑", "怕", "紧张", "不安", "着急", "恐慌", "压力山大"],
        EmotionType.FRUSTRATED: ["失败", "受挫", "太难了", "不行", "卡住了", "碰壁", "灰心", "失望"],
        EmotionType.DETERMINED: ["决定了", "一定要", "坚持", "不放弃", "干", "拼了", "豁出去"],
        EmotionType.HOPEFUL: ["期待", "希望", "看好", "有机会", "相信", "憧憬", "向往"],
        EmotionType.HESITANT: ["犹豫", "纠结", "摇摆", "拿不定", "想试试", "担心", "怕"],
        EmotionType.OVERWHELMED: ["压力", "太大", "受不了", "撑不住", " overload", "忙不过来", "太多"],
    }

    # 情感探测Prompt模板
    EMOTION_DETECT_PROMPT = """你是一个情绪分析专家。请分析用户输入中的情绪状态和潜在担忧，以JSON格式输出。

用户输入：{user_input}

请分析：
1. emotion: 主导情绪，从以下选择：confused(迷茫), anxious(焦虑), frustrated(挫败), determined(坚定), hopeful(期待), hesitant(犹豫), overwhelmed(压力山大)
2. emotion_intensity: 情绪强度（0.0-1.0）
3. emotional_subtext: 情绪潜台词——用户在情绪层面真正想表达什么（50字以内）
4. underlying_concern: 潜在担忧——用户担心什么（50字以内）

请直接输出JSON：
{{"emotion": "...", "emotion_intensity": 0.0, "emotional_subtext": "...", "underlying_concern": "..."}}"""

    def __init__(self, llm_client: OllamaClient, rule_first: bool = True):
        """
        初始化情感探测器

        Args:
            llm_client: Ollama LLM客户端
            rule_first: 是否优先使用规则检测
        """
        self.llm = llm_client
        self.rule_first = rule_first

    async def detect(self, user_input: str, context: str = "") -> EmotionDetectionResult:
        """
        检测用户情绪状态

        Args:
            user_input: 用户原始输入
            context: 对话上下文（可选）

        Returns:
            EmotionDetectionResult情感探测结果

        耗时目标: <800ms（规则命中）/ <1500ms（LLM分析）
        """
        if not user_input or not user_input.strip():
            return EmotionDetectionResult(
                emotion=EmotionType.CONFUSED,
                emotion_intensity=0.3,
            )

        # 第一层：规则检测
        rule_result = self._rule_based_detect(user_input)

        # 如果规则命中且置信度高，直接返回
        if self.rule_first and rule_result and rule_result.emotion_intensity > 0.5:
            logger.debug("Emotion detected by rule: %s (%.2f)",
                         rule_result.emotion, rule_result.emotion_intensity)
            return rule_result

        # 第二层：LLM深度分析
        try:
            prompt = self.EMOTION_DETECT_PROMPT.format(user_input=user_input)
            response = await self.llm.generate(
                prompt=prompt,
                options={"temperature": 0.3, "num_ctx": 2048},
                thinking=False,
            )

            content = response.get("response", "")
            result = self._extract_json(content)

            if result:
                emotion_str = result.get("emotion", "confused").lower()
                try:
                    emotion = EmotionType(emotion_str)
                except ValueError:
                    emotion = self._map_emotion_string(emotion_str)

                intensity = float(result.get("emotion_intensity", 0.5))

                return EmotionDetectionResult(
                    emotion=emotion,
                    emotion_intensity=intensity,
                    emotional_subtext=result.get("emotional_subtext", ""),
                    underlying_concern=result.get("underlying_concern", ""),
                )

        except Exception as e:
            logger.warning("LLM emotion detection failed: %s", e)

        # Fallback: 返回规则检测结果或默认值
        return rule_result or EmotionDetectionResult(
            emotion=EmotionType.CONFUSED,
            emotion_intensity=0.3,
        )

    def _rule_based_detect(self, user_input: str) -> Optional[EmotionDetectionResult]:
        """
        基于关键词规则快速检测情绪

        Args:
            user_input: 用户输入

        Returns:
            检测结果，若无匹配则返回None
        """
        scores: Dict[EmotionType, int] = {}

        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in user_input)
            if score > 0:
                scores[emotion] = score

        if not scores:
            return None

        # 选择得分最高的情绪
        best_emotion = max(scores.items(), key=lambda x: x[1])
        emotion, score = best_emotion

        # 根据匹配数计算强度
        max_possible = len(self.EMOTION_KEYWORDS[emotion])
        intensity = min(score / max(max_possible * 0.3, 1), 1.0)

        # 生成潜台词
        subtexts = {
            EmotionType.CONFUSED: "表面上说问题，实际是不知道方向",
            EmotionType.ANXIOUS: "表面上说担心，实际是害怕不好的结果",
            EmotionType.FRUSTRATED: "遇到了困难，感到无力",
            EmotionType.DETERMINED: "已经做了决定，想要支持和确认",
            EmotionType.HOPEFUL: "看到了可能性，想要抓住机会",
            EmotionType.HESITANT: "在多个选项之间摇摆不定",
            EmotionType.OVERWHELMED: "事情太多，感到力不从心",
        }

        return EmotionDetectionResult(
            emotion=emotion,
            emotion_intensity=round(intensity, 2),
            emotional_subtext=subtexts.get(emotion, ""),
            underlying_concern="",
        )

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应内容中提取JSON"""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'\{[^{}]*"emotion"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _map_emotion_string(self, s: str) -> EmotionType:
        """将情绪字符串映射到枚举"""
        mapping = {
            "迷茫": EmotionType.CONFUSED,
            "confused": EmotionType.CONFUSED,
            "焦虑": EmotionType.ANXIOUS,
            "anxious": EmotionType.ANXIOUS,
            "挫败": EmotionType.FRUSTRATED,
            "frustrated": EmotionType.FRUSTRATED,
            "frustration": EmotionType.FRUSTRATED,
            "坚定": EmotionType.DETERMINED,
            "determined": EmotionType.DETERMINED,
            "期待": EmotionType.HOPEFUL,
            "hopeful": EmotionType.HOPEFUL,
            "犹豫": EmotionType.HESITANT,
            "hesitant": EmotionType.HESITANT,
            "压力": EmotionType.OVERWHELMED,
            "overwhelmed": EmotionType.OVERWHELMED,
        }
        return mapping.get(s, EmotionType.CONFUSED)


# ============================================================================
# 意图分类器
# ============================================================================

class IntentClassifier:
    """
    意图分类器：判断用户当前的认知阶段和真实意图

    区分表面请求和深层需求，评估用户在认知循环中的位置。
    """

    # 认知阶段关键词特征
    STAGE_KEYWORDS: Dict[CognitiveStage, List[str]] = {
        CognitiveStage.PROBLEM_STATEMENT: ["迷茫", "不知道", "困惑", "怎么办", "很烦", "难受", "有问题"],
        CognitiveStage.INFORMATION_SEEKING: ["有什么建议", "怎么做", "如何", "请教", "想知道", "了解一下"],
        CognitiveStage.OPTION_EXPLORATION: ["选哪个", "A还是B", "哪个好", "比较", "优缺点", "纠结"],
        CognitiveStage.DECISION_STRUGGLE: ["担心", "怕", "如果", "万一", "会不会", "但是", "可是"],
        CognitiveStage.ACTION_CONFIRMATION: ["准备", "打算", "决定了", "准备做", "想试试", "计划"],
        CognitiveStage.REFLECTION: ["回顾", "总结", "想想", "当初", "后来", "结果", "经验"],
    }

    # 意图分类Prompt模板
    INTENT_CLASSIFY_PROMPT = """你是一个认知阶段分析专家。请判断用户在问题解决循环中的位置，以JSON格式输出。

用户输入：{user_input}

请判断：
1. cognitive_stage: 认知阶段，从以下选择
   - problem_statement: 问题陈述（"我很迷茫"）
   - information_seeking: 信息寻求（"有什么建议"）
   - option_exploration: 选项探索（"A和B哪个好"）
   - decision_struggle: 决策挣扎（"我担心..."）
   - action_confirmation: 行动确认（"我准备这样做"）
   - reflection: 反思总结（"我做对了"）

2. surface_request: 表面请求（用户说了什么，30字以内）
3. deep_need: 深层需求（用户真正需要什么但没说出来，50字以内）
4. implicit_needs: 隐含需求列表（用户可能需要但未表达的需求，3-5个）
5. cognitive_cycle_position: 用户在"目标→方案→环节→需求→因素→评估"循环中的位置
   {{"goal": true/false, "plan": true/false, "steps": true/false, "needs": true/false, "factors": true/false, "assessment": true/false}}
   true表示用户已经涉及或完成该阶段，false表示尚未涉及

请直接输出JSON：
{{"cognitive_stage": "...", "surface_request": "...", "deep_need": "...", "implicit_needs": [...], "cognitive_cycle_position": {{...}}}}"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化意图分类器

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def classify(
        self,
        user_input: str,
        dialogue_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentClassificationResult:
        """
        分类用户当前认知阶段

        Args:
            user_input: 用户原始输入
            dialogue_history: 对话历史（可选）

        Returns:
            IntentClassificationResult意图分类结果

        耗时目标: <1000ms
        """
        if not user_input or not user_input.strip():
            return IntentClassificationResult(
                cognitive_stage=CognitiveStage.PROBLEM_STATEMENT,
                surface_request="",
                deep_need="",
            )

        try:
            prompt = self.INTENT_CLASSIFY_PROMPT.format(user_input=user_input)
            response = await self.llm.generate(
                prompt=prompt,
                options={"temperature": 0.3, "num_ctx": 2048},
                thinking=False,
            )

            content = response.get("response", "")
            result = self._extract_json(content)

            if result:
                stage_str = result.get("cognitive_stage", "problem_statement")
                try:
                    stage = CognitiveStage(stage_str)
                except ValueError:
                    stage = CognitiveStage.PROBLEM_STATEMENT

                cycle_pos = result.get("cognitive_cycle_position", {})
                # 确保所有键都存在
                default_pos = {"goal": False, "plan": False, "steps": False,
                               "needs": False, "factors": False, "assessment": False}
                default_pos.update(cycle_pos)

                return IntentClassificationResult(
                    cognitive_stage=stage,
                    surface_request=result.get("surface_request", ""),
                    deep_need=result.get("deep_need", ""),
                    implicit_needs=result.get("implicit_needs", []),
                    cognitive_cycle_position=default_pos,
                )

        except Exception as e:
            logger.warning("LLM intent classification failed: %s", e)

        # Fallback: 基于规则的分类
        return self._rule_based_classify(user_input)

    def _rule_based_classify(self, user_input: str) -> IntentClassificationResult:
        """基于规则的意图分类"""
        scores: Dict[CognitiveStage, int] = {}

        for stage, keywords in self.STAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in user_input)
            if score > 0:
                scores[stage] = score

        if scores:
            best_stage = max(scores.items(), key=lambda x: x[1])[0]
        else:
            best_stage = CognitiveStage.PROBLEM_STATEMENT

        return IntentClassificationResult(
            cognitive_stage=best_stage,
            surface_request=user_input[:30],
            deep_need="需要进一步分析",
            implicit_needs=[],
            cognitive_cycle_position={
                "goal": False, "plan": False, "steps": False,
                "needs": False, "factors": False, "assessment": False,
            },
        )

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应内容中提取JSON"""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试匹配更大范围的JSON
        json_match = re.search(r'\{.*"cognitive_stage".*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None


# ============================================================================
# 感知层统一入口
# ============================================================================

class PerceptionLayer:
    """
    感知层：整合语义解析、情感探测、意图分类的统一入口

    三个子模块并行执行，总耗时目标 < 2000ms。
    """

    def __init__(self, llm_client: OllamaClient, rule_first: bool = True):
        """
        初始化感知层

        Args:
            llm_client: Ollama LLM客户端
            rule_first: 是否优先使用规则检测（情感探测）
        """
        self.semantic_parser = SemanticParser(llm_client)
        self.emotion_detector = EmotionDetector(llm_client, rule_first=rule_first)
        self.intent_classifier = IntentClassifier(llm_client)

        logger.info("PerceptionLayer initialized (rule_first=%s)", rule_first)

    async def perceive(
        self,
        user_input: str,
        dialogue_history: Optional[List[Dict[str, str]]] = None,
    ) -> UserIntent:
        """
        感知层主入口：并行执行所有感知任务

        并行执行：
        - SemanticParser.parse()
        - EmotionDetector.detect()
        - IntentClassifier.classify()

        Args:
            user_input: 用户原始输入
            dialogue_history: 对话历史（可选）

        Returns:
            UserIntent结构化用户意图

        总耗时目标: <2000ms（并行后）
        """
        import time
        start_time = time.time()

        # 并行执行三个感知任务
        semantic_task = self.semantic_parser.parse(user_input)
        emotion_task = self.emotion_detector.detect(user_input)
        intent_task = self.intent_classifier.classify(user_input, dialogue_history)

        semantic, emotion, intent = await asyncio.gather(
            semantic_task, emotion_task, intent_task,
            return_exceptions=True,
        )

        # 处理异常
        if isinstance(semantic, Exception):
            logger.error("Semantic parse failed: %s", semantic)
            semantic = SemanticParseResult(topic="未知", keywords=[], entities=[], domain="general")
        if isinstance(emotion, Exception):
            logger.error("Emotion detect failed: %s", emotion)
            emotion = EmotionDetectionResult(emotion=EmotionType.CONFUSED, emotion_intensity=0.3)
        if isinstance(intent, Exception):
            logger.error("Intent classify failed: %s", intent)
            intent = IntentClassificationResult(
                cognitive_stage=CognitiveStage.PROBLEM_STATEMENT,
                surface_request="",
                deep_need="",
            )

        elapsed = int((time.time() - start_time) * 1000)
        logger.info("PerceptionLayer completed in %dms", elapsed)

        return UserIntent(
            # 语义解析
            topic=semantic.topic,
            keywords=semantic.keywords,
            entities=semantic.entities,
            domain=semantic.domain,
            # 情感探测
            emotion=emotion.emotion,
            emotion_intensity=emotion.emotion_intensity,
            emotional_subtext=emotion.emotional_subtext,
            underlying_concern=emotion.underlying_concern,
            # 意图分类
            cognitive_stage=intent.cognitive_stage,
            implicit_needs=intent.implicit_needs,
            surface_request=intent.surface_request,
            deep_need=intent.deep_need,
            cognitive_cycle_position=intent.cognitive_cycle_position,
            # 原始输入
            raw_input=user_input,
            input_length=len(user_input),
        )
