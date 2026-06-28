"""
教员AI顾问 - 主引擎（JiaoyuanEngine）

五层认知架构的统一编排层：
感知(Perception) → 理解(Understanding) → 推理(Reasoning) → 记忆(Memory) → 表达(Expression)

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

# 导入五层架构
from perception import PerceptionLayer
from understanding import UnderstandingLayer
from reasoning import ReasoningLayer
from memory import MemoryLayer, DialogueMemory
from expression import ExpressionLayer
from models import (
    UserIntent,
    ProblemProfile,
    ReasoningResult,
    EngineConfig,
    EmotionType,
)
from llm_client import OllamaClient
from cognitive_graph import CognitiveGraph
from maoxuan_retriever import MaoxuanRetriever

# ============================================================================
# 日志配置
# ============================================================================

logger = logging.getLogger("jiaoyuan.engine")


# ============================================================================
# 主引擎
# ============================================================================

class JiaoyuanEngine:
    """
    教员AI顾问主引擎 - 五层认知架构编排器

    架构流程：
    1. 感知层(Perception): 语义解析 + 情感探测 + 意图分类
    2. 理解层(Understanding): 问题类型判断 + 认知图谱检索 + 框架匹配
    3. 推理层(Reasoning): 思维链 + 苏格拉底提问 + 矛盾分析 + 阶段判断
    4. 记忆层(Memory): 对话历史 + 用户画像 + 认知状态追踪
    5. 表达层(Expression): 教员语言DNA + 语气调节 + 格式控制

    Args:
        config: 引擎配置（模型名、Ollama地址等）

    Example:
        engine = JiaoyuanEngine()
        result = await engine.chat("我想创业但迷茫", session_id="s1")
        print(result["response"])
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        """
        初始化引擎，创建五层架构实例

        耗时目标: <3s（不包含模型加载）
        """
        self.config = config or EngineConfig()

        # LLM客户端
        self.llm_client = OllamaClient(
            base_url=self.config.ollama_host,
            model=self.config.model_name,
            timeout=self.config.llm_timeout_seconds,
        )

        # 认知图谱（教员思维方法知识图谱）
        self.cognitive_graph = CognitiveGraph()
        self.cognitive_graph.load_builtin_data()

        # 毛选知识库检索
        self.maoxuan_retriever = MaoxuanRetriever()

        # 五层认知架构
        self.perception = PerceptionLayer(rule_first=True)
        self.understanding = UnderstandingLayer()
        self.reasoning = ReasoningLayer()
        self.memory = MemoryLayer(
            max_full_turns=self.config.max_full_turns,
            profiles_dir=self.config.profiles_dir,
        )
        self.expression = ExpressionLayer()

        # 会话管理
        self._sessions: Dict[str, DialogueMemory] = {}

        logger.info(
            "JiaoyuanEngine initialized: model=%s, thinking=%s",
            self.config.model_name,
            self.config.enable_thinking_mode,
        )

    def _get_session(self, session_id: str, user_id: str) -> DialogueMemory:
        """
        获取或创建会话记忆

        Args:
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            DialogueMemory实例
        """
        session_key = f"{user_id}:{session_id}"

        if session_key not in self._sessions:
            self._sessions[session_key] = DialogueMemory(
                max_full_turns=self.config.max_full_turns,
                user_id=user_id,
                session_id=session_id,
            )
            logger.debug("Created new session: %s", session_key)

        return self._sessions[session_key]

    def _build_expression_messages(
        self,
        reasoning_result: ReasoningResult,
        user_intent: UserIntent,
    ) -> list:
        """
        构建表达层的LLM消息列表

        将推理结果转化为教员风格的回复提示。

        Args:
            reasoning_result: 推理结果
            user_intent: 用户意图

        Returns:
            消息列表，用于LLM调用
        """
        # 苏格拉底提问
        questions_text = "\n".join([
            f"{i+1}. [{q.type.value}] {q.question}"
            for i, q in enumerate(reasoning_result.socratic_questions[:5])
        ])

        # 矛盾分析
        contradiction_text = ""
        if reasoning_result.contradiction_analysis:
            ca = reasoning_result.contradiction_analysis
            contradiction_text = f"""
主要矛盾：{ca.primary_contradiction or '未明确'}
矛盾两面：{chr(10).join(ca.both_sides) if ca.both_sides else '待分析'}
"""

        # 阶段判断
        phase_text = ""
        if reasoning_result.phase_assessment:
            pa = reasoning_result.phase_assessment
            phase_text = f"当前阶段：{pa.current_phase.value}"

        # 构建上下文
        context = f"""用户情绪：{user_intent.emotion.value}
问题主题：{user_intent.topic}
认知阶段：{user_intent.cognitive_stage.value}

问题类型：{reasoning_result.problem_type.value}
适用框架：{reasoning_result.framework.value}

关键洞察：
{chr(10).join([f"- {insight}" for insight in reasoning_result.key_insights[:5]])}

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

        return [
            {"role": "system", "content": "你是教员，用教员的思维方式和语言风格回复。"},
            {"role": "user", "content": context},
        ]

    # ========================================================================
    # 主入口 - 普通版本
    # ========================================================================

    async def chat(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """
        主入口：完整的五层处理流程

        处理流程：
        1. 加载记忆上下文
        2. 感知层分析
        3. 理解层理解问题
        4. 推理层深度推理
        5. 表达层生成回复
        6. 保存对话到记忆

        Args:
            user_input: 用户输入
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            结果字典，包含：
            - response: 最终回复文本
            - thinking: 思考过程
            - user_intent: 用户意图分析
            - problem_profile: 问题画像
            - reasoning_result: 推理结果
            - processing_time_ms: 总耗时
            - layer_timings: 各层耗时

        总耗时目标: <10s（MacBook M2）
        """
        total_start = time.time()
        layer_timings: Dict[str, int] = {}

        logger.info("Chat: user=%s, session=%s, input=%s", user_id, session_id, user_input[:50])

        try:
            # ================================================================
            # Step 1: 加载记忆上下文
            # ================================================================
            memory = self._get_session(session_id, user_id)
            memory_context = memory.get_context()

            # ================================================================
            # Step 2: 感知层
            # ================================================================
            p_start = time.time()
            user_intent = await self.perception.perceive(
                user_input, dialogue_history=memory_context.get("history", []),
            )
            layer_timings["perception"] = int((time.time() - p_start) * 1000)

            # ================================================================
            # Step 3: 理解层
            # ================================================================
            u_start = time.time()
            problem_profile = await self.understanding.understand(user_intent)
            layer_timings["understanding"] = int((time.time() - u_start) * 1000)

            # ================================================================
            # Step 4: 推理层（核心）
            # ================================================================
            r_start = time.time()
            reasoning_result = await self.reasoning.reason(
                user_intent, problem_profile, memory_context,
            )
            layer_timings["reasoning"] = int((time.time() - r_start) * 1000)

            # ================================================================
            # Step 5: 表达层
            # ================================================================
            e_start = time.time()
            response_text = await self.expression.express(reasoning_result, user_intent)
            layer_timings["expression"] = int((time.time() - e_start) * 1000)

            # ================================================================
            # Step 6: 保存对话到记忆
            # ================================================================
            m_start = time.time()
            await memory.add_turn(user_input, response_text, reasoning_result)
            memory.update_cognitive_tracker(user_intent, reasoning_result)
            asyncio.create_task(memory.persist())
            layer_timings["memory"] = int((time.time() - m_start) * 1000)

            # 计算总耗时
            total_time = int((time.time() - total_start) * 1000)

            logger.info(
                "Chat complete: total=%dms (P:%d U:%d R:%d E:%d M:%d)",
                total_time,
                layer_timings.get("perception", 0),
                layer_timings.get("understanding", 0),
                layer_timings.get("reasoning", 0),
                layer_timings.get("expression", 0),
                layer_timings.get("memory", 0),
            )

            return {
                "response": response_text,
                "thinking": reasoning_result.thinking_content,
                "user_intent": {
                    "topic": user_intent.topic,
                    "emotion": user_intent.emotion.value,
                    "cognitive_stage": user_intent.cognitive_stage.value,
                    "keywords": user_intent.keywords,
                },
                "problem_profile": {
                    "type": problem_profile.problem_type.value,
                    "framework": problem_profile.framework.value,
                },
                "reasoning_result": {
                    "key_insights": reasoning_result.key_insights,
                    "socratic_questions": [
                        {"q": q.question, "type": q.type.value}
                        for q in reasoning_result.socratic_questions
                    ],
                    "reasoning_time_ms": reasoning_result.reasoning_time_ms,
                },
                "processing_time_ms": total_time,
                "layer_timings": layer_timings,
            }

        except Exception as e:
            logger.exception("Chat processing failed: %s", e)
            return {
                "response": "同志，这个问题我需要再想想。你能再说详细一点吗？",
                "thinking": "",
                "error": str(e),
                "processing_time_ms": int((time.time() - total_start) * 1000),
                "layer_timings": layer_timings,
            }

    # ========================================================================
    # 主入口 - 流式版本（带思考进度条）
    # ========================================================================

    async def chat_stream(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式版本主入口 - 带5步思考进度指示

        流式输出消息类型：
        - {"type": "progress", "step": N, "total": 5, "label": "...", "detail": "..."}  # 进度更新
        - {"type": "thinking_chunk", "content": "..."}  # 单行thinking内容
        - {"type": "content", "content": "..."}  # 回复内容（逐token流式）
        - {"type": "done", "response": "...", "thinking": "...", "questions": [...]}  # 完成

        Args:
            user_input: 用户输入
            session_id: 会话ID
            user_id: 用户ID

        Yields:
            内容块字典
        """
        import time
        total_start = time.time()

        logger.info("Chat stream: user=%s, session=%s", user_id, session_id)

        try:
            # =====================================================================
            # Step 1: 感知层
            # =====================================================================
            yield {"type": "progress", "step": 1, "total": 5, "label": "感知分析", "detail": "分析用户意图和情绪状态..."}

            memory = self._get_session(session_id, user_id)
            memory_context = memory.get_context()

            user_intent = await self.perception.perceive(
                user_input, dialogue_history=memory_context.get("history", []),
            )
            yield {"type": "progress", "step": 1, "total": 5, "label": "感知分析", "detail": f"主题：{user_intent.topic}，情绪：{user_intent.emotion.value}"}

            # =====================================================================
            # Step 2: 理解层
            # =====================================================================
            yield {"type": "progress", "step": 2, "total": 5, "label": "理解问题", "detail": "匹配教员思维框架..."}

            problem_profile = await self.understanding.understand(user_intent)
            yield {"type": "progress", "step": 2, "total": 5, "label": "理解问题", "detail": f"问题类型：{problem_profile.problem_type.value}，适用框架：{problem_profile.framework.value}"}

            # =====================================================================
            # Step 3: 推理层
            # =====================================================================
            yield {"type": "progress", "step": 3, "total": 5, "label": "深度推理", "detail": "思维链推理+矛盾分析+阶段判断..."}

            reasoning_result = await self.reasoning.reason(
                user_intent, problem_profile, memory_context,
            )
            yield {"type": "progress", "step": 3, "total": 5, "label": "深度推理", "detail": f"识别{len(reasoning_result.socratic_questions)}个关键问题，矛盾分析完成"}

            # thinking内容分行发送
            if reasoning_result.thinking_content:
                thinking_lines = [l.strip() for l in reasoning_result.thinking_content.split('\n') if l.strip()]
                for line in thinking_lines[:20]:  # 最多20行
                    yield {"type": "thinking_chunk", "content": line}

            # =====================================================================
            # Step 4: 表达层（真正的LLM流式）
            # =====================================================================
            yield {"type": "progress", "step": 4, "total": 5, "label": "生成回复", "detail": "教员风格表达中..."}

            expression_messages = self._build_expression_messages(reasoning_result, user_intent)
            full_response = ""
            async for chunk in self.llm_client.chat_stream(expression_messages):
                if chunk["type"] == "thinking":
                    yield {"type": "thinking_chunk", "content": chunk["content"]}
                elif chunk["type"] == "content":
                    full_response += chunk["content"]
                    yield {"type": "content", "content": chunk["content"]}
                elif chunk["type"] == "done":
                    break

            # =====================================================================
            # Step 5: 完成
            # =====================================================================
            yield {"type": "progress", "step": 5, "total": 5, "label": "完成", "detail": ""}

            # 保存对话
            await memory.add_turn(user_input, full_response, reasoning_result)
            memory.update_cognitive_tracker(user_intent, reasoning_result)
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
    # 健康检查与统计
    # ========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
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
        """获取引擎统计信息"""
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
        """关闭引擎，释放资源"""
        await self.llm_client.close()
        logger.info("JiaoyuanEngine closed")

    async def __aenter__(self) -> "JiaoyuanEngine":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()
