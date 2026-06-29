"""教员AI顾问 - 主引擎（JiaoyuanEngine）v3.1.0

优化版本：五层认知架构压缩为 2 次 LLM 调用，大幅提升响应速度。
- 感知+理解：规则引擎（0ms，无需 LLM）
- 推理：1 次 LLM 调用（生成矛盾分析+苏格拉底提问）
- 表达：1 次流式 LLM 调用（生成回复）

作者: AI系统架构师
版本: 3.1.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from llm_client import OllamaClient
from models import (
    UserIntent,
    ProblemProfile,
    ReasoningResult,
    EngineConfig,
    ProblemType,
    FrameworkType,
    CognitiveStage,
    EmotionType,
    SocraticQuestion,
    QuestionType,
    ContradictionAnalysis,
    PhaseAssessment,
    PhaseType,
)
from memory import MemoryLayer
from cognitive_graph import CognitiveGraph
from maoxuan_retriever import MaoxuanRetriever

logger = logging.getLogger("jiaoyuan.engine")


class JiaoyuanEngine:
    """教员AI顾问主引擎 - 优化版认知架构编排器"""

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()

        self.llm_client = OllamaClient(
            base_url=self.config.ollama_host,
            model=self.config.model_name,
            timeout=self.config.llm_timeout_seconds,
        )

        self.cognitive_graph = CognitiveGraph()
        self.cognitive_graph.load_builtin_data()
        self.maoxuan_retriever = MaoxuanRetriever()
        self._sessions: Dict[str, MemoryLayer] = {}

        logger.info(
            "JiaoyuanEngine v3.1.0 initialized: model=%s, thinking=%s",
            self.config.model_name,
            self.config.enable_thinking_mode,
        )

    def _get_session(self, session_id: str, user_id: str) -> MemoryLayer:
        """获取或创建会话记忆"""
        session_key = f"{user_id}:{session_id}"

        if session_key not in self._sessions:
            self._sessions[session_key] = MemoryLayer(
                user_id=user_id,
                profiles_dir=self.config.profiles_dir,
                max_full_turns=self.config.max_full_turns,
            )
            logger.debug("Created new session: %s", session_key)

        return self._sessions[session_key]

    # ========================================================================
    # 优化：规则引擎快速提取（替代 LLM 调用）
    # ========================================================================
    def _rule_perceive(self, user_input: str) -> UserIntent:
        """规则感知：0ms，无需 LLM"""
        text = user_input.strip()

        # 情绪规则识别
        emotion = EmotionType.CONFUSED
        if any(k in text for k in ["焦虑", "担心", "害怕", "急"]):
            emotion = EmotionType.ANXIOUS
        elif any(k in text for k in ["迷茫", "不知道", "不清楚", "困惑"]):
            emotion = EmotionType.CONFUSED
        elif any(k in text for k in ["生气", "愤怒", "不公平", "恨"]):
            emotion = EmotionType.FRUSTRATED
        elif any(k in text for k in ["想", "希望", "期待", "梦想"]):
            emotion = EmotionType.HOPEFUL
        elif any(k in text for k in ["犹豫", "纠结", "选", "怎么办"]):
            emotion = EmotionType.HESITANT
        elif any(k in text for k in ["压力", "累", "受不了", "崩溃"]):
            emotion = EmotionType.OVERWHELMED
        elif any(k in text for k in ["坚定", "决心", "一定", "必须"]):
            emotion = EmotionType.DETERMINED

        # 认知阶段规则识别
        stage = CognitiveStage.PROBLEM_STATEMENT
        if any(k in text for k in ["怎么办", "如何", "怎么", "选择", "选"]):
            stage = CognitiveStage.DECISION_STRUGGLE
        elif any(k in text for k in ["信息", "了解", "搜索", "查", "调查"]):
            stage = CognitiveStage.INFORMATION_SEEKING
        elif any(k in text for k in ["方法", "技巧", "学习", "提升", "进步"]):
            stage = CognitiveStage.OPTION_EXPLORATION
        elif any(k in text for k in ["决定", "行动", "做", "执行", "开始"]):
            stage = CognitiveStage.ACTION_CONFIRMATION
        elif any(k in text for k in ["总结", "回顾", "反思", "经验", "教训"]):
            stage = CognitiveStage.REFLECTION

        # 提取关键词（简单分词）
        import re
        words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        keywords = list(set([w for w in words if len(w) >= 2 and len(w) <= 6]))[:8]

        # 提取主题（前10字或第一个实体）
        topic = text[:10] if len(text) <= 10 else text[:10] + "..."

        return UserIntent(
            topic=topic,
            keywords=keywords,
            entities=[],
            domain="general",
            emotion=emotion,
            emotion_intensity=0.6,
            emotional_subtext="",
            underlying_concern="",
            cognitive_stage=stage,
            implicit_needs=[],
            surface_request=text,
            deep_need="",
            cognitive_cycle_position={},
            raw_input=text,
            input_length=len(text),
        )

    def _rule_understand(self, user_input: str, user_intent: UserIntent) -> ProblemProfile:
        """规则理解：0ms，无需 LLM，根据关键词匹配框架"""
        text = user_input.lower()

        # 问题类型规则匹配
        problem_type = ProblemType.CONTRADICTION_ANALYSIS
        if any(k in text for k in ["矛盾", "冲突", "两难", "对立", "斗争"]):
            problem_type = ProblemType.CONTRADICTION_ANALYSIS
        elif any(k in text for k in ["调查", "了解", "真实", "情况", "研究", "考察"]):
            problem_type = ProblemType.INVESTIGATION_RESEARCH
        elif any(k in text for k in ["阶段", "形势", "趋势", "判断", "评估", "分析"]):
            problem_type = ProblemType.PHASE_ASSESSMENT
        elif any(k in text for k in ["策略", "方法", "路线", "方针", "计划", "方案"]):
            problem_type = ProblemType.STRATEGY_SELECTION
        elif any(k in text for k in ["信心", "勇气", "害怕", "退缩", "坚持", "放弃"]):
            problem_type = ProblemType.CONFIDENCE_BUILDING
        elif any(k in text for k in ["学习", "理论", "方法", "认识", "思想", "思维"]):
            problem_type = ProblemType.METHODOLOGY_LEARNING

        # 框架规则匹配
        framework = FrameworkType.CONTRADICTION_THEORY
        if problem_type == ProblemType.CONTRADICTION_ANALYSIS:
            framework = FrameworkType.CONTRADICTION_THEORY
        elif problem_type == ProblemType.INVESTIGATION_RESEARCH:
            framework = FrameworkType.INVESTIGATION_METHOD
        elif problem_type == ProblemType.PHASE_ASSESSMENT:
            framework = FrameworkType.PROTRACTED_WAR
        elif problem_type == ProblemType.STRATEGY_SELECTION:
            framework = FrameworkType.MASS_LINE
        elif problem_type == ProblemType.CONFIDENCE_BUILDING:
            framework = FrameworkType.INDEPENDENT_THINKING
        elif problem_type == ProblemType.METHODOLOGY_LEARNING:
            framework = FrameworkType.FIVE_LAYER_ANALYSIS

        return ProblemProfile(
            problem_type=problem_type,
            framework=framework,
            framework_confidence=0.7,
            related_methods=[],
            related_concepts=[],
            related_cases=[],
            related_quotes=[],
            maoxuan_refs=[],
        )

    # ========================================================================
    # 优化：单次 LLM 调用完成推理
    # ========================================================================
    async def _single_reasoning(
        self,
        user_input: str,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
    ) -> ReasoningResult:
        """单次 LLM 调用完成全部推理：矛盾分析 + 阶段判断 + 苏格拉底提问"""

        prompt = f"""你是教员思维分析专家。请分析用户问题，输出 JSON 格式的分析结果。

用户输入：{user_input}
问题主题：{user_intent.topic}
用户情绪：{user_intent.emotion.value}
认知阶段：{user_intent.cognitive_stage.value}
问题类型：{problem_profile.problem_type.value}
适用框架：{problem_profile.framework.value}

请输出以下 JSON（不要其他内容）：
{{
  "key_insights": ["洞察1", "洞察2", "洞察3"],
  "primary_contradiction": "主要矛盾描述",
  "aspects": {{"方面A": "描述", "方面B": "描述"}},
  "current_phase": "strategic_defense|strategic_stalemate|strategic_counteroffensive",
  "socratic_questions": [
    {{"question": "提问1", "type": "clarify"}},
    {{"question": "提问2", "type": "challenge_assumption"}},
    {{"question": "提问3", "type": "explore_consequence"}},
    {{"question": "提问4", "type": "find_evidence"}},
    {{"question": "提问5", "type": "reframe_perspective"}}
  ]
}}

要求：
1. 用教员矛盾分析法找出主要矛盾
2. 判断当前处于持久战哪个阶段
3. 苏格拉底提问要层层递进，引导用户自己思考
4. 总字数控制在 300 字以内"""

        messages = [
            {"role": "system", "content": "你是教员思维分析专家，用 JSON 输出分析结果。"},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm_client.chat(messages)
            content = response.get("content", "")

            # 提取 JSON
            import json, re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {}

            # 构建 ReasoningResult
            questions_data = data.get("socratic_questions", [])
            socratic_questions = []
            for q in questions_data[:5]:
                q_type_str = q.get("type", "clarify")
                q_type = QuestionType.CLARIFY
                if q_type_str == "challenge_assumption":
                    q_type = QuestionType.CHALLENGE_ASSUMPTION
                elif q_type_str == "explore_consequence":
                    q_type = QuestionType.EXPLORE_CONSEQUENCE
                elif q_type_str == "find_evidence":
                    q_type = QuestionType.FIND_EVIDENCE
                elif q_type_str == "reframe_perspective":
                    q_type = QuestionType.REFRAME_PERSPECTIVE

                socratic_questions.append(SocraticQuestion(
                    question=q.get("question", "请详细说说？"),
                    type=q_type,
                    purpose="引导用户深入思考",
                    target_insight="",
                    priority=1,
                ))

            phase_str = data.get("current_phase", "strategic_stalemate")
            phase = PhaseType.STRATEGIC_STALEMATE
            if phase_str == "strategic_defense":
                phase = PhaseType.STRATEGIC_DEFENSE
            elif phase_str == "strategic_counteroffensive":
                phase = PhaseType.STRATEGIC_COUNTEROFFENSIVE

            return ReasoningResult(
                reasoning_chain="",
                key_insights=data.get("key_insights", ["需要进一步分析"]),
                socratic_questions=socratic_questions,
                contradiction_analysis=ContradictionAnalysis(
                    primary_contradiction=data.get("primary_contradiction", "需要进一步分析"),
                    secondary_contradictions=[],
                    aspects=data.get("aspects", {}),
                    transformation_conditions=[],
                    resolution_direction=data.get("resolution_direction", "需要进一步分析"),
                ),
                phase_assessment=PhaseAssessment(
                    current_phase=phase,
                    phase_confidence=0.6,
                    key_tasks=[],
                    transition_signals=[],
                    assessment="",
                ),
                five_layer_analysis=None,
                reasoning_time_ms=0,
                thinking_content="",
                model_used=self.config.model_name,
            )

        except Exception as e:
            logger.warning("Single reasoning failed: %s, falling back to default", e)
            # 回退：返回默认结果，避免 None 导致后续处理错误
            return ReasoningResult(
                reasoning_chain="",
                key_insights=["抓住主要矛盾", "分析形势阶段", "制定斗争策略"],
                socratic_questions=[
                    SocraticQuestion(
                        question="你说的这个问题的核心是什么？能具体说说吗？",
                        type=QuestionType.CLARIFY,
                        purpose="澄清问题",
                        target_insight="",
                        priority=1,
                    ),
                    SocraticQuestion(
                        question="你为什么觉得这个问题非这样做不可？",
                        type=QuestionType.CHALLENGE_ASSUMPTION,
                        purpose="挑战假设",
                        target_insight="",
                        priority=1,
                    ),
                    SocraticQuestion(
                        question="如果按你说的去做，最好的结果是什么？最坏的呢？",
                        type=QuestionType.EXPLORE_CONSEQUENCE,
                        purpose="探索后果",
                        target_insight="",
                        priority=1,
                    ),
                ],
                contradiction_analysis=ContradictionAnalysis(
                    primary_contradiction="需要进一步分析",
                    secondary_contradictions=[],
                    aspects={},
                    transformation_conditions=[],
                    resolution_direction="需要进一步分析",
                ),
                phase_assessment=PhaseAssessment(
                    current_phase=PhaseType.STRATEGIC_STALEMATE,
                    phase_confidence=0.5,
                    key_tasks=[],
                    transition_signals=[],
                    assessment="",
                ),
                five_layer_analysis=None,
                reasoning_time_ms=0,
                thinking_content="",
                model_used=self.config.model_name,
            )

    # ========================================================================
    # 优化：流式生成回复
    # ========================================================================
    async def _stream_response(
        self,
        reasoning_result: ReasoningResult,
        user_intent: UserIntent,
        problem_profile: ProblemProfile,
    ) -> AsyncGenerator[str, None]:
        """流式生成教员风格回复"""

        questions_text = "\n".join([
            f"{i+1}. [{q.type.value}] {q.question}"
            for i, q in enumerate(reasoning_result.socratic_questions[:5])
        ])

        contradiction_text = ""
        if reasoning_result.contradiction_analysis:
            ca = reasoning_result.contradiction_analysis
            aspects_str = ""
            if ca.aspects:
                aspects_str = "\n".join([f"- {k}: {v}" for k, v in ca.aspects.items()])
            contradiction_text = f"主要矛盾：{ca.primary_contradiction or '未明确'}\n矛盾两面：{aspects_str or '待分析'}"

        phase_text = ""
        if reasoning_result.phase_assessment:
            pa = reasoning_result.phase_assessment
            phase_text = f"当前阶段：{pa.current_phase.value}"

        key_insights_str = "\n".join([f"- {insight}" for insight in reasoning_result.key_insights[:5]])

        context = f"""用户情绪：{user_intent.emotion.value}
问题主题：{user_intent.topic}
认知阶段：{user_intent.cognitive_stage.value}

问题类型：{problem_profile.problem_type.value}
适用框架：{problem_profile.framework.value}

关键洞察：
{key_insights_str}

苏格拉底提问（层层递进引导思考）：
{questions_text}

{contradiction_text}

{phase_text}

请用教员的语言风格回复：
1. 句长控制在20字以内，多用短句
2. 适当使用战争/自然比喻
3. 使用辩证句式（"一方面...另一方面..."）
4. 先通过1-3个提问引导用户自己思考
5. 再给出分析，最后给予鼓励
6. 总字数300-500字
"""

        messages = [
            {"role": "system", "content": "你是教员，用教员的思维方式和语言风格回复。"},
            {"role": "user", "content": context},
        ]

        async for chunk in self.llm_client.chat_stream(messages):
            if chunk["type"] == "content":
                yield chunk["content"]
            elif chunk["type"] == "thinking":
                # 修复：thinking 内容也作为回复内容输出，避免"问了没出结果"
                yield chunk["content"]
            elif chunk["type"] == "done":
                break

    # ========================================================================
    # 优化后的流式聊天接口
    # ========================================================================
    async def chat_stream(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """优化版流式聊天：2 次 LLM 调用（1次分析 + 1次流式生成）"""
        total_start = time.time()

        logger.info("Chat stream: user=%s, session=%s, input=%s", user_id, session_id, user_input[:50])

        try:
            yield {"type": "progress", "step": 1, "total": 5, "percent": 5, "label": "感知分析", "detail": "分析用户意图..."}

            memory = self._get_session(session_id, user_id)
            memory_context = memory.get_context()

            # 优化：规则感知（0ms）
            user_intent = self._rule_perceive(user_input)
            yield {"type": "progress", "step": 1, "total": 5, "percent": 10, "label": "感知分析", "detail": f"主题：{user_intent.topic}，情绪：{user_intent.emotion.value}"}

            yield {"type": "progress", "step": 2, "total": 5, "percent": 15, "label": "理解问题", "detail": "匹配思维框架..."}

            # 优化：规则理解（0ms）
            problem_profile = self._rule_understand(user_input, user_intent)
            yield {"type": "progress", "step": 2, "total": 5, "percent": 20, "label": "理解问题", "detail": f"框架：{problem_profile.framework.value}"}

            yield {"type": "progress", "step": 3, "total": 5, "percent": 25, "label": "深度推理", "detail": "生成分析..."}

            # 优化：单次 LLM 完成推理
            reasoning_result = await self._single_reasoning(user_input, user_intent, problem_profile)
            yield {"type": "progress", "step": 3, "total": 5, "percent": 35, "label": "深度推理", "detail": f"识别{len(reasoning_result.socratic_questions)}个关键问题"}

            # 优化：流式生成回复（第2次 LLM 调用）
            yield {"type": "progress", "step": 4, "total": 5, "percent": 40, "label": "生成回复", "detail": "教员正在思考..."}
            full_response = ""
            async for content in self._stream_response(reasoning_result, user_intent, problem_profile):
                full_response += content
                yield {"type": "content", "content": content}

            yield {"type": "progress", "step": 5, "total": 5, "percent": 100, "label": "完成", "detail": ""}

            # 异步保存记忆（不阻塞）
            asyncio.create_task(memory.add_turn(user_input, full_response, reasoning_result))
            asyncio.create_task(memory.persist())

            total_time = int((time.time() - total_start) * 1000)
            yield {
                "type": "done",
                "content": "",
                "response": full_response,
                "thinking": reasoning_result.thinking_content,
                "questions": [{"q": q.question, "type": q.type.value} for q in reasoning_result.socratic_questions],
                "processing_time_ms": total_time,
            }

        except Exception as e:
            logger.exception("Stream processing failed: %s", e)
            yield {
                "type": "error",
                "content": str(e),
            }

    # ========================================================================
    # 兼容旧版非流式接口
    # ========================================================================
    async def chat(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """非流式聊天接口（兼容旧版）"""
        total_start = time.time()
        full_response = ""

        try:
            async for chunk in self.chat_stream(user_input, session_id, user_id):
                if chunk["type"] == "content":
                    full_response += chunk["content"]
                elif chunk["type"] == "error":
                    return {
                        "response": "同志，这个问题我需要再想想。",
                        "thinking": "",
                        "error": chunk["content"],
                        "processing_time_ms": int((time.time() - total_start) * 1000),
                    }

            return {
                "response": full_response,
                "thinking": "",
                "processing_time_ms": int((time.time() - total_start) * 1000),
            }

        except Exception as e:
            logger.exception("Chat processing failed: %s", e)
            return {
                "response": "同志，这个问题我需要再想想。你能再说详细一点吗？",
                "thinking": "",
                "error": str(e),
                "processing_time_ms": int((time.time() - total_start) * 1000),
            }

    async def health_check(self) -> Dict[str, Any]:
        llm_healthy = await self.llm_client.health_check()
        kg_stats = self.cognitive_graph.get_stats()
        mx_stats = self.maoxuan_retriever.get_stats()

        return {
            "status": "healthy" if llm_healthy else "degraded",
            "llm": {"healthy": llm_healthy, "model": self.config.model_name},
            "cognitive_graph": kg_stats,
            "maoxuan": mx_stats,
            "sessions": len(self._sessions),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "config": {
                "model": self.config.model_name,
                "thinking_mode": self.config.enable_thinking_mode,
                "max_context": self.config.max_context_tokens,
            },
            "sessions": len(self._sessions),
            "cognitive_graph": self.cognitive_graph.get_stats(),
            "maoxuan": self.maoxuan_retriever.get_stats(),
        }

    async def close(self) -> None:
        await self.llm_client.close()
        logger.info("JiaoyuanEngine closed")

    async def __aenter__(self) -> "JiaoyuanEngine":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
