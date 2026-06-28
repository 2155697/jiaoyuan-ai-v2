"""
教员AI顾问 - 推理层（核心层）

推理层是整个架构的核心，包含四大引擎：
1. CoTEngine: 思维链引擎 — 利用Qwen3 Thinking模式进行深度推理
2. SocraticEngine: 苏格拉底提问引擎 — 生成引导性问题序列
3. ContradictionAnalyzer: 矛盾分析引擎 — 识别和分析矛盾
4. PhaseAssessor: 阶段判断引擎 — 评估用户所处阶段

四大引擎并行+串行组合执行：
- CoT和专项分析引擎并行
- 苏格拉底提问依赖CoT结果（串行）

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from llm_client import OllamaClient
from models import (
    CognitiveStage, ContradictionAnalysis, FiveLayerAnalysis,
    FrameworkType, PhaseAssessment, PhaseType, ProblemProfile,
    ProblemType, ReasoningResult, SocraticQuestion, QuestionType,
    UserIntent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 思维链引擎 (CoTEngine)
# ============================================================================

class CoTEngine:
    """
    思维链引擎：利用Qwen3的Thinking模式进行深度推理

    核心创新：不是直接生成答案，而是生成"推理过程+关键洞察"
    利用Qwen3的<think>标签获取内部思考过程，节省一次LLM调用。
    """

    # 思维链推理Prompt模板
    COT_PROMPT = """【角色定义】
你是教员（毛泽东）的思维模型。你不是在回答一个关于历史的问题，而是在用教员的思维方式帮助一位同志分析问题。

你的核心方法：
1. 先调查研究 — 了解实际情况，不先入为主
2. 抓主要矛盾 — 在复杂问题中找到最关键的
3. 看两面 — 任何事物都有正面和反面
4. 分阶段 — 事物发展有阶段，要判断处在哪个阶段
5. 实事求是 — 从实际出发，不空讲道理

【当前问题】
用户说：{user_input}

用户的情绪状态：{emotion}
用户所处的认知阶段：{cognitive_stage}
问题类型：{problem_type}
适用思维框架：{framework}

【相关方法论】
{related_methods}

【相关毛选段落】
{maoxuan_refs}

【推理指令】
请用教员的思维方式进行内部推理。注意：
1. 不要直接给答案，要思考用户真正的问题是什么
2. 分析这个问题的主要矛盾是什么
3. 判断用户处于什么阶段（防御/相持/反攻）
4. 思考应该提什么样的问题来引导用户自己找到答案
5. 如果适用五层分析框架，分析目标→方案→环节→需求→因素→评估

请输出以下内容：
1. 关键洞察（3-5个要点）
2. 推理链条（你是如何思考的）

输出格式：
关键洞察：
- 洞察1：...
- 洞察2：...
推理链条：...
"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化思维链引擎

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def reason(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
        memory_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行思维链推理

        流程：
        1. 构建推理Prompt
        2. 调用Qwen3 with thinking mode
        3. 解析thinking内容
        4. 返回结构化推理结果

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像
            memory_context: 记忆上下文

        Returns:
            推理结果字典：{reasoning_chain, key_insights, thinking_content}

        耗时目标: <5000ms（主要耗时）
        """
        prompt = self._build_reasoning_prompt(user_intent, problem_profile, memory_context)

        # 调用LLM with thinking mode
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.7,
                "num_ctx": 8192,
                "top_p": 0.95,
                "top_k": 20,
            },
            thinking=True,
        )

        # 解析thinking和response
        thinking_content = response.get("thinking", "")
        response_content = response.get("message", {}).get("content", "")

        # 提取关键洞察
        insights = self._extract_insights(thinking_content, response_content)

        logger.debug(
            "CoT reasoning: thinking=%d chars, response=%d chars, insights=%d",
            len(thinking_content), len(response_content), len(insights),
        )

        return {
            "reasoning_chain": thinking_content or response_content,
            "key_insights": insights,
            "thinking_content": thinking_content,
        }

    def _build_reasoning_prompt(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
        memory_context: Dict[str, Any],
    ) -> str:
        """
        构建思维链推理Prompt

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像
            memory_context: 记忆上下文

        Returns:
            推理Prompt字符串
        """
        # 格式化相关方法论
        methods_str = "\n".join([
            f"- [{m.name}] {m.description}"[:200]
            for m in problem_profile.related_methods[:5]
        ]) or "无"

        # 格式化毛选引用
        refs_str = "\n".join([
            f"- 《{r.source}》：{r.text}"[:200]
            for r in problem_profile.maoxuan_refs[:3]
        ]) or "无"

        # 获取对话上下文
        history = memory_context.get("history", [])
        recent_history = ""
        if history:
            recent = history[-3:]
            recent_history = "\n".join([
                f"用户: {h.get('user', '')}" for h in recent
            ])

        return self.COT_PROMPT.format(
            user_input=user_intent.raw_input,
            emotion=user_intent.emotion.value,
            emotional_subtext=user_intent.emotional_subtext,
            cognitive_stage=user_intent.cognitive_stage.value,
            problem_type=problem_profile.problem_type.value,
            framework=problem_profile.framework.value,
            related_methods=methods_str,
            maoxuan_refs=refs_str,
            history=recent_history,
        )

    def _extract_insights(self, thinking: str, response: str) -> List[str]:
        """
        从thinking和response中提取关键洞察点

        Args:
            thinking: 思考内容
            response: 响应内容

        Returns:
            关键洞察列表
        """
        insights = []
        combined = thinking + "\n" + response

        # 匹配 "洞察" 或 "要点" 开头的行
        for line in combined.split("\n"):
            line = line.strip()
            if line.startswith("-") and any(kw in line for kw in [
                "洞察", "矛盾", "阶段", "关键", "主要", "实质", "核心", "根本",
                "问题", "方向", "策略", "方法", "重点",
            ]):
                insight = line.lstrip("- ").strip()
                if len(insight) > 5 and len(insight) < 200:
                    insights.append(insight)
            elif "关键洞察" in line or "核心要点" in line:
                # 下一行可能是洞察
                continue

        # 去重并限制数量
        seen = set()
        unique_insights = []
        for i in insights:
            key = i[:20]
            if key not in seen:
                seen.add(key)
                unique_insights.append(i)

        return unique_insights[:5]


# ============================================================================
# 苏格拉底提问引擎 (SocraticEngine)
# ============================================================================

class SocraticEngine:
    """
    苏格拉底提问引擎：生成引导性问题序列

    核心原则：
    1. 不给直接答案
    2. 通过提问引导用户自己思考
    3. 问题层层递进，形成问题链
    4. 每个问题有明确的目的

    提问类型：
    - clarify: 澄清概念
    - challenge_assumption: 挑战假设
    - explore_consequence: 探索后果
    - find_evidence: 寻找证据
    - reframe_perspective: 转换视角
    """

    # 苏格拉底提问生成Prompt模板
    SOCRATIC_PROMPT = """【角色定义】
你是教员，你正在和一位同志讨论问题。你的风格是：
- 不给直接答案，通过提问引导对方自己思考
- 问题简短有力，一针见血
- 用教员的语言风格（比喻、辩证、肯定句式）

【提问原则】
1. 每个问题都要有明确的目的（澄清/挑战假设/探索后果/找证据/转换视角）
2. 问题要层层递进，从浅入深
3. 问题要针对用户的实际情况，不要空泛
4. 问题数量控制在3-5个

【提问类型定义】
- clarify: 澄清概念 — 帮助用户明确关键概念的含义
- challenge_assumption: 挑战假设 — 揭示用户潜在的假设
- explore_consequence: 探索后果 — 引导用户思考可能的结果
- find_evidence: 寻找证据 — 要求用户用事实支撑观点
- reframe_perspective: 转换视角 — 帮助用户从不同角度看待问题

【当前情境】
用户说：{user_input}
用户情绪：{emotion}
问题类型：{problem_type}
适用框架：{framework}

【你的推理洞察】
{key_insights}

【提问指令】
请生成3-5个引导性问题。要求：
1. 第一个问题要澄清概念或了解情况（clarify）
2. 第二个问题要挑战用户的某个假设（challenge_assumption）
3. 第三个问题要引导用户思考后果（explore_consequence）
4. 如果适用，第四个问题要转换视角（reframe_perspective）
5. 问题要有教员的语言风格：简短有力，善用比喻

请以JSON格式输出：
{{"questions": [
  {{"question": "...", "type": "clarify", "purpose": "...", "target_insight": "..."}},
  {{"question": "...", "type": "challenge_assumption", "purpose": "...", "target_insight": "..."}},
  {{"question": "...", "type": "explore_consequence", "purpose": "...", "target_insight": "..."}}
]}}

重要：只输出JSON，不要给答案或分析。问题要像教员在说话。"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化苏格拉底提问引擎

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def generate_questions(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
        reasoning_result: Dict[str, Any],
    ) -> List[SocraticQuestion]:
        """
        生成苏格拉底式提问序列

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像
            reasoning_result: 思维链推理结果

        Returns:
            苏格拉底提问列表

        耗时目标: <2000ms
        """
        prompt = self._build_question_prompt(user_intent, problem_profile, reasoning_result)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.8,
                    "num_ctx": 4096,
                    "top_p": 0.95,
                    "top_k": 20,
                },
                thinking=False,
            )

            content = response.get("message", {}).get("content", "")
            questions = self._parse_questions(content)

            if questions:
                logger.debug("Generated %d socratic questions", len(questions))
                return questions

        except Exception as e:
            logger.warning("LLM socratic question generation failed: %s", e)

        # Fallback: 使用模板生成问题
        return self._generate_template_questions(user_intent, problem_profile)

    def _build_question_prompt(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
        reasoning_result: Dict[str, Any],
    ) -> str:
        """
        构建苏格拉底提问生成Prompt

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像
            reasoning_result: 推理结果

        Returns:
            Prompt字符串
        """
        insights = reasoning_result.get("key_insights", [])
        insights_str = "\n".join([f"- {i}" for i in insights[:5]]) or "无"

        return self.SOCRATIC_PROMPT.format(
            user_input=user_intent.raw_input,
            emotion=user_intent.emotion.value,
            problem_type=problem_profile.problem_type.value,
            framework=problem_profile.framework.value,
            key_insights=insights_str,
        )

    def _parse_questions(self, content: str) -> List[SocraticQuestion]:
        """
        解析LLM输出的提问序列

        Args:
            content: LLM响应内容

        Returns:
            提问列表
        """
        questions = []

        # 尝试JSON解析
        try:
            data = json.loads(content.strip())
            if "questions" in data:
                for q in data["questions"]:
                    try:
                        qtype = QuestionType(q.get("type", "clarify"))
                    except ValueError:
                        qtype = QuestionType.CLARIFY

                    questions.append(SocraticQuestion(
                        question=q.get("question", ""),
                        type=qtype,
                        purpose=q.get("purpose", ""),
                        target_insight=q.get("target_insight", ""),
                        priority=3,
                    ))
                return questions
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "questions" in data:
                    for q in data["questions"]:
                        try:
                            qtype = QuestionType(q.get("type", "clarify"))
                        except ValueError:
                            qtype = QuestionType.CLARIFY
                        questions.append(SocraticQuestion(
                            question=q.get("question", ""),
                            type=qtype,
                            purpose=q.get("purpose", ""),
                            target_insight=q.get("target_insight", ""),
                        ))
                    return questions
            except json.JSONDecodeError:
                pass

        # 尝试匹配JSON对象
        json_match = re.search(r'\{\s*"questions"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                for q in data.get("questions", []):
                    questions.append(SocraticQuestion(
                        question=q.get("question", ""),
                        type=QuestionType(q.get("type", "clarify")),
                        purpose=q.get("purpose", ""),
                        target_insight=q.get("target_insight", ""),
                    ))
                return questions
            except (json.JSONDecodeError, ValueError):
                pass

        return questions

    def _generate_template_questions(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
    ) -> List[SocraticQuestion]:
        """
        使用模板生成问题（fallback）

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像

        Returns:
            提问列表
        """
        topic = user_intent.topic or "这件事"
        questions = []

        # 问题1: 澄清
        questions.append(SocraticQuestion(
            question=f"你说的'{topic}'，具体指的是什么？能举个例子吗？",
            type=QuestionType.CLARIFY,
            purpose=f"澄清'{topic}'的具体含义",
            target_insight=f"让用户明确{topic}的实质",
            priority=1,
        ))

        # 问题2: 挑战假设
        questions.append(SocraticQuestion(
            question=f"你为什么觉得{topic}非这样做不可？如果换一种方式呢？",
            type=QuestionType.CHALLENGE_ASSUMPTION,
            purpose="挑战用户的潜在假设",
            target_insight="让用户意识到自己可能有思维定势",
            priority=2,
        ))

        # 问题3: 探索后果
        questions.append(SocraticQuestion(
            question=f"如果按你说的去做，最好的结果是什么？最坏的结果呢？",
            type=QuestionType.EXPLORE_CONSEQUENCE,
            purpose="引导用户思考不同选择的结果",
            target_insight="让用户全面评估风险",
            priority=3,
        ))

        return questions


# ============================================================================
# 矛盾分析引擎 (ContradictionAnalyzer)
# ============================================================================

class ContradictionAnalyzer:
    """
    矛盾分析引擎：识别和分析矛盾

    教员矛盾论的核心应用：
    1. 矛盾存在于一切事物的发展过程中
    2. 主要矛盾决定事物的发展方向
    3. 矛盾的主要方面决定事物的性质
    4. 矛盾双方在一定条件下可以转化
    """

    # 矛盾分析Prompt模板
    CONTRADICTION_PROMPT = """【角色定义】
你是教员，你擅长用矛盾论分析问题。《矛盾论》是你的核心方法论。

矛盾论的核心要点：
1. 矛盾存在于一切事物的发展过程中
2. 主要矛盾决定事物的发展方向 — 要抓主要矛盾
3. 矛盾的主要方面决定事物的性质
4. 矛盾双方在一定条件下可以转化
5. 要具体问题具体分析 — 矛盾的普遍性+特殊性

【当前问题】
用户说：{user_input}

【分析指令】
请用矛盾论分析这个问题：
1. 主要矛盾：什么是这个问题的核心冲突？
2. 矛盾的双方：A面和B面分别是什么？
3. 主要方面：目前哪一面占主导？
4. 转化条件：需要什么条件才能使矛盾向有利方向转化？
5. 解决方向：应该朝哪个方向努力？

请以JSON格式输出：
{{"primary_contradiction": "...", "aspects": {{"A": "...", "B": "..."}}, "secondary_contradictions": ["..."], "dominant_aspect": "...", "transformation_conditions": ["..."], "resolution_direction": "..."}}"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化矛盾分析引擎

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def analyze(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
    ) -> ContradictionAnalysis:
        """
        执行矛盾分析

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像

        Returns:
            ContradictionAnalysis矛盾分析结果

        耗时目标: <2000ms
        """
        prompt = self.CONTRADICTION_PROMPT.format(user_input=user_intent.raw_input)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.5, "num_ctx": 4096},
                thinking=False,
            )

            content = response.get("message", {}).get("content", "")
            result = self._extract_json(content)

            if result:
                return ContradictionAnalysis(
                    primary_contradiction=result.get("primary_contradiction", ""),
                    secondary_contradictions=result.get("secondary_contradictions", []),
                    aspects=result.get("aspects", {}),
                    dominant_aspect=result.get("dominant_aspect", ""),
                    transformation_conditions=result.get("transformation_conditions", []),
                    resolution_direction=result.get("resolution_direction", ""),
                )

        except Exception as e:
            logger.warning("LLM contradiction analysis failed: %s", e)

        # Fallback: 基于规则的分析
        return self._rule_based_analysis(user_intent)

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应中提取JSON"""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'\{[^{}]*"primary_contradiction"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _rule_based_analysis(self, user_intent: UserIntent) -> ContradictionAnalysis:
        """基于规则的矛盾分析（fallback）"""
        text = user_intent.raw_input

        # 识别矛盾关键词
        contradiction_markers = ["但是", "然而", "不过", "却", "虽然", "尽管",
                                  "纠结", "两难", "矛盾", "冲突",
                                  "既想", "又怕", "一方面", "另一方面"]

        has_contradiction = any(m in text for m in contradiction_markers)

        if has_contradiction:
            return ContradictionAnalysis(
                primary_contradiction=f"从用户的描述来看，在'{user_intent.topic}'上存在内在冲突",
                secondary_contradictions=["理想与现实的冲突", "短期利益与长期发展的冲突"],
                aspects={
                    "A": "用户想要的方向或目标",
                    "B": "现实中的限制或担忧",
                },
                dominant_aspect="需要进一步分析确定",
                transformation_conditions=["增强自身实力", "改变外部条件", "调整目标预期"],
                resolution_direction="先调查研究，了解实际情况，再抓主要矛盾",
            )

        return ContradictionAnalysis(
            primary_contradiction=f"在'{user_intent.topic}'上，需要进一步分析是否存在内在矛盾",
            aspects={},
            transformation_conditions=["深入了解情况", "分析利弊得失"],
            resolution_direction="建议先做调查研究，再分析矛盾",
        )


# ============================================================================
# 阶段判断引擎 (PhaseAssessor)
# ============================================================================

class PhaseAssessor:
    """
    阶段判断引擎：评估用户所处的阶段

    参考持久战三阶段理论：
    - 战略防御：刚发现问题，力量不足
    - 战略相持：双方力量均衡，需要坚持
    - 战略反攻：力量充足，可以主动出击
    """

    # 阶段定义
    PHASE_DEFINITIONS: Dict[PhaseType, Dict[str, Any]] = {
        PhaseType.STRATEGIC_DEFENSE: {
            "name": "战略防御",
            "description": "问题刚出现，自身力量不足，需要了解情况、积蓄力量",
            "characteristics": ["刚发现问题", "力量不足", "需要了解情况", "处于被动", "信息不够"],
            "key_tasks": ["调查研究", "了解情况", "积蓄力量", "建立基础"],
            "transition_signals": ["情况了解清楚", "力量有所积蓄", "找到突破口"],
        },
        PhaseType.STRATEGIC_STALEMATE: {
            "name": "战略相持",
            "description": "双方力量均衡，需要坚持、等待时机、积蓄力量",
            "characteristics": ["力量均衡", "僵持不下", "需要耐心", "消耗战", "拉锯状态"],
            "key_tasks": ["坚持既定方针", "等待时机", "积蓄力量", "寻找突破口"],
            "transition_signals": ["力量对比变化", "出现新机遇", "积累足够"],
        },
        PhaseType.STRATEGIC_COUNTEROFFENSIVE: {
            "name": "战略反攻",
            "description": "力量充足，可以主动出击，解决问题",
            "characteristics": ["力量充足", "主动权在手", "时机成熟", "可以出击", "优势明显"],
            "key_tasks": ["主动出击", "一举突破", "扩大战果", "巩固胜利"],
            "transition_signals": ["问题基本解决", "需要巩固成果", "进入新阶段"],
        },
    }

    # 阶段判断Prompt模板
    PHASE_PROMPT = """【角色定义】
你是教员，你擅长用持久战的三阶段理论分析形势。

持久战三阶段：
1. 战略防御 — 敌强我弱，保存实力，了解情况
   - 特征：被动、防守、力量不足
   - 任务：调查研究、积蓄力量、建立基础

2. 战略相持 — 力量均衡，僵持不下
   - 特征：拉锯、消耗、需要耐心
   - 任务：坚持方针、等待时机、寻找突破口

3. 战略反攻 — 我强敌弱，主动出击
   - 特征：主动、进攻、时机成熟
   - 任务：一举突破、扩大战果、巩固胜利

【当前问题】
用户说：{user_input}

【分析指令】
请判断用户当前处于哪个阶段：
1. 分析用户的力量状况（资源、能力、信息、信心）
2. 分析问题的难度和当前态势
3. 判断处于三阶段中的哪个阶段
4. 该阶段的关键任务是什么
5. 进入下一阶段的信号是什么

请以JSON格式输出：
{{"current_phase": "strategic_defense/strategic_stalemate/strategic_counteroffensive", "phase_characteristics": ["..."], "key_tasks": ["..."], "transition_signals": ["..."], "assessment": "..."}}"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化阶段判断引擎

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def assess(
        self,
        user_intent: UserIntent,
        dialogue_history: List[Dict[str, str]],
    ) -> PhaseAssessment:
        """
        评估用户当前所处阶段

        Args:
            user_intent: 用户意图
            dialogue_history: 对话历史

        Returns:
            PhaseAssessment阶段评估结果

        耗时目标: <1500ms
        """
        prompt = self.PHASE_PROMPT.format(user_input=user_intent.raw_input)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.5, "num_ctx": 4096},
                thinking=False,
            )

            content = response.get("message", {}).get("content", "")
            result = self._extract_json(content)

            if result:
                phase_str = result.get("current_phase", "strategic_defense")
                try:
                    phase = PhaseType(phase_str)
                except ValueError:
                    phase = PhaseType.STRATEGIC_DEFENSE

                return PhaseAssessment(
                    current_phase=phase,
                    phase_characteristics=result.get("phase_characteristics", []),
                    key_tasks=result.get("key_tasks", []),
                    transition_signals=result.get("transition_signals", []),
                    assessment=result.get("assessment", ""),
                )

        except Exception as e:
            logger.warning("LLM phase assessment failed: %s", e)

        # Fallback: 基于规则的判断
        return self._rule_based_assessment(user_intent)

    def _rule_based_assessment(self, user_intent: UserIntent) -> PhaseAssessment:
        """基于规则的评估"""
        text = user_intent.raw_input
        emotion = user_intent.emotion

        # 根据情绪和关键词判断阶段
        defense_signals = ["不知道", "迷茫", "刚", "开始", "不了解", "怕", "担心"]
        stalemate_signals = ["坚持", "等待", "僵持", "煎熬", "熬", "耐心"]
        counteroffensive_signals = ["准备", "决定", "行动", "出击", "突破", "解决"]

        defense_score = sum(1 for s in defense_signals if s in text)
        stalemate_score = sum(1 for s in stalemate_signals if s in text)
        counteroffensive_score = sum(1 for s in counteroffensive_signals if s in text)

        if emotion in [EmotionType.CONFUSED, EmotionType.ANXIOUS]:
            defense_score += 2
        elif emotion == EmotionType.DETERMINED:
            counteroffensive_score += 2
        elif emotion == EmotionType.HESITANT:
            stalemate_score += 1

        scores = [
            (PhaseType.STRATEGIC_DEFENSE, defense_score),
            (PhaseType.STRATEGIC_STALEMATE, stalemate_score),
            (PhaseType.STRATEGIC_COUNTEROFFENSIVE, counteroffensive_score),
        ]
        best_phase = max(scores, key=lambda x: x[1])[0]

        phase_config = self.PHASE_DEFINITIONS[best_phase]
        return PhaseAssessment(
            current_phase=best_phase,
            phase_characteristics=phase_config["characteristics"][:3],
            key_tasks=phase_config["key_tasks"][:3],
            transition_signals=phase_config["transition_signals"][:2],
            assessment=f"从用户的描述来看，目前处于{best_phase.value}阶段，需要{'积蓄力量' if best_phase == PhaseType.STRATEGIC_DEFENSE else '坚持等待' if best_phase == PhaseType.STRATEGIC_STALEMATE else '主动出击'}",
        )

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应中提取JSON"""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        import re
        for pattern in [
            r'```json\s*(\{.*?\})\s*```',
            r'\{[^{}]*"current_phase"[^{}]*\}',
        ]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1) if match.groups() else match.group())
                except json.JSONDecodeError:
                    continue
        return None


# ============================================================================
# 五层分析框架引擎 (FiveLayerAnalyzer)
# ============================================================================

class FiveLayerAnalyzer:
    """
    五层分析框架引擎：目标→方案→环节→需求→因素→评估

    教员思维的核心方法论，对用户的问题进行逐层分析。
    """

    # 五层分析Prompt模板
    FIVE_LAYER_PROMPT = """【角色定义】
你是教员，你擅长用五层分析框架帮同志分析问题。

五层分析框架：
1. 目标层 — 最终要达到的目标是什么？
2. 方案层 — 有哪些可行的实现方案？
3. 环节层 — 方案包含哪些具体步骤？
4. 需求层 — 每个步骤需要什么资源和条件？
5. 因素层 — 影响成败的关键因素是什么？
6. 评估层 — 对整体把握有多大？难度如何？

【当前问题】
用户说：{user_input}

【分析指令】
请用五层分析框架分析这个问题，对每一层给出分析，并对因素难度进行1-10分评估。

请以JSON格式输出：
{{"goal": "...", "plan": "...", "steps": ["..."], "needs": ["..."], "factors": ["..."], "assessment": "...", "difficulty_rating": {{"因素1": 5, "因素2": 8}}, "missing_layers": ["..."]}}

missing_layers: 用户尚未明确或缺失的层次。"""

    def __init__(self, llm_client: OllamaClient):
        """
        初始化五层分析框架引擎

        Args:
            llm_client: Ollama LLM客户端
        """
        self.llm = llm_client

    async def analyze(
        self,
        user_intent: UserIntent,
        dialogue_history: List[Dict[str, str]],
    ) -> FiveLayerAnalysis:
        """
        执行五层分析

        Args:
            user_intent: 用户意图
            dialogue_history: 对话历史

        Returns:
            FiveLayerAnalysis五层分析结果

        耗时目标: <3000ms
        """
        prompt = self.FIVE_LAYER_PROMPT.format(user_input=user_intent.raw_input)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.5, "num_ctx": 4096},
                thinking=False,
            )

            content = response.get("message", {}).get("content", "")
            result = self._extract_json(content)

            if result:
                return FiveLayerAnalysis(
                    goal=result.get("goal", ""),
                    plan=result.get("plan", ""),
                    steps=result.get("steps", []),
                    needs=result.get("needs", []),
                    factors=result.get("factors", []),
                    assessment=result.get("assessment", ""),
                    difficulty_rating=result.get("difficulty_rating", {}),
                    missing_layers=result.get("missing_layers", []),
                )

        except Exception as e:
            logger.warning("LLM five-layer analysis failed: %s", e)

        # Fallback: 生成空分析
        return self._empty_analysis()

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应中提取JSON"""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        import re
        for pattern in [
            r'```json\s*(\{.*?\})\s*```',
            r'\{[^{}]*"goal"[^{}]*\}',
        ]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1) if match.groups() else match.group())
                except json.JSONDecodeError:
                    continue
        return None

    def _empty_analysis(self) -> FiveLayerAnalysis:
        """生成空分析（fallback）"""
        return FiveLayerAnalysis(
            goal="需要进一步澄清",
            plan="",
            steps=[],
            needs=[],
            factors=[],
            assessment="信息不足，需要更多了解",
            missing_layers=["goal", "plan", "steps", "needs", "factors", "assessment"],
        )


# ============================================================================
# 推理层统一入口 (ReasoningLayer)
# ============================================================================

class ReasoningLayer:
    """
    推理层：整合四大推理引擎的统一入口

    执行策略：
    - CoT思维链（必做）
    - 根据问题类型选择专项分析引擎（与CoT并行）
    - 苏格拉底提问（依赖CoT结果，串行）

    总耗时目标: <7000ms
    """

    def __init__(self, llm_client: OllamaClient):
        """
        初始化推理层

        Args:
            llm_client: Ollama LLM客户端
        """
        self.cot_engine = CoTEngine(llm_client)
        self.socratic_engine = SocraticEngine(llm_client)
        self.contradiction_analyzer = ContradictionAnalyzer(llm_client)
        self.phase_assessor = PhaseAssessor(llm_client)
        self.five_layer_analyzer = FiveLayerAnalyzer(llm_client)

        logger.info("ReasoningLayer initialized")

    async def reason(
        self,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
        memory_context: Dict[str, Any],
    ) -> ReasoningResult:
        """
        推理层主入口

        执行流程：
        1. CoT思维链（必做）
        2. 根据问题类型，并行执行专项分析
        3. 苏格拉底提问（依赖CoT结果）

        Args:
            user_intent: 用户意图
            problem_profile: 问题画像
            memory_context: 记忆上下文

        Returns:
            ReasoningResult推理结果

        总耗时目标: <7000ms
        """
        import time
        start_time = time.time()

        # 步骤1: CoT思维链（必做）
        cot_task = self.cot_engine.reason(user_intent, problem_profile, memory_context)

        # 步骤2: 根据问题类型选择专项分析（与CoT并行）
        analysis_tasks = [cot_task]  # CoT总是第一个

        if problem_profile.problem_type == ProblemType.CONTRADICTION_ANALYSIS:
            analysis_tasks.append(
                self.contradiction_analyzer.analyze(user_intent, problem_profile)
            )

        if problem_profile.problem_type == ProblemType.PHASE_ASSESSMENT:
            dialogue_history = memory_context.get("history", [])
            analysis_tasks.append(
                self.phase_assessor.assess(user_intent, dialogue_history)
            )

        # 五层分析适用于所有问题类型
        dialogue_history = memory_context.get("history", [])
        analysis_tasks.append(
            self.five_layer_analyzer.analyze(user_intent, dialogue_history)
        )

        # 并行执行所有分析
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        # 解析结果
        cot_result = results[0]
        if isinstance(cot_result, Exception):
            logger.error("CoT reasoning failed: %s", cot_result)
            cot_result = {"reasoning_chain": "", "key_insights": [], "thinking_content": ""}

        # 解析专项分析结果
        contradiction_result = None
        phase_result = None
        five_layer_result = None

        idx = 1
        if problem_profile.problem_type == ProblemType.CONTRADICTION_ANALYSIS:
            if idx < len(results) and not isinstance(results[idx], Exception):
                contradiction_result = results[idx]
            idx += 1

        if problem_profile.problem_type == ProblemType.PHASE_ASSESSMENT:
            if idx < len(results) and not isinstance(results[idx], Exception):
                phase_result = results[idx]
            idx += 1

        # 五层分析总是最后一个
        if idx < len(results) and not isinstance(results[idx], Exception):
            five_layer_result = results[idx]

        # 步骤3: 苏格拉底提问（依赖CoT结果）
        questions = await self.socratic_engine.generate_questions(
            user_intent, problem_profile, cot_result,
        )

        elapsed = int((time.time() - start_time) * 1000)

        return ReasoningResult(
            reasoning_chain=cot_result.get("reasoning_chain", ""),
            key_insights=cot_result.get("key_insights", []),
            socratic_questions=questions,
            contradiction_analysis=contradiction_result if not isinstance(contradiction_result, Exception) else None,
            phase_assessment=phase_result if not isinstance(phase_result, Exception) else None,
            five_layer_analysis=five_layer_result if not isinstance(five_layer_result, Exception) else None,
            reasoning_time_ms=elapsed,
            thinking_content=cot_result.get("thinking_content", ""),
        )
