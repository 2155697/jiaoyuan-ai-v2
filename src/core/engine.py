"""
教员AI顾问 - 主引擎（编排层）

五层认知架构的统一编排入口：
1. 感知层(Perception) → 理解层(Understanding) → 推理层(Reasoning) → 记忆层(Memory) → 表达层(Expression)
2. 支持完整的五层处理流程和流式处理
3. 并发对话支持
4. 完整的性能计时和日志记录

用法：
    engine = JiaoyuanEngine()
    result = await engine.chat("我想创业但不知道做什么", session_id="s1", user_id="u1")
    print(result["response"])

    # 流式调用
    async for chunk in engine.chat_stream("...", session_id="s1", user_id="u1"):
        print(chunk["content"], end="")

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from cognitive_graph import CognitiveGraph
from expression import ExpressionLayer
from llm_client import OllamaClient
from maoxuan_retriever import MaoxuanRetriever
from memory import MemoryLayer
from models import EngineConfig, EngineOutput, ReasoningResult, StreamChunk, UserIntent
from perception import PerceptionLayer
from reasoning import ReasoningLayer
from understanding import UnderstandingLayer

logger = logging.getLogger(__name__)


# ============================================================================
# 主引擎
# ============================================================================

class JiaoyuanEngine:
    """
    教员AI顾问主引擎：编排五层认知架构

    五层处理流程：
    1. 记忆层加载上下文（session_id + user_id）
    2. 感知层分析用户输入
    3. 理解层理解问题
    4. 推理层深度推理
    5. 表达层生成回复
    6. 保存对话到记忆

    性能目标：
    - 单轮对话总耗时 < 10秒（MacBook M2）
    - 内存占用 < 2GB（不含模型）
    - 支持并发对话
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        """
        初始化教员AI顾问主引擎

        Args:
            config: 引擎配置，None则使用默认配置
        """
        self.config = config or EngineConfig()

        # 初始化LLM客户端
        self.llm_client = OllamaClient(
            base_url=self.config.ollama_host,
            model=self.config.model_name,
            timeout=self.config.llm_timeout_seconds,
        )

        # 初始化认知图谱
        self.cognitive_graph = CognitiveGraph(
            data_dir=self.config.cognitive_graph_dir,
        )
        self.cognitive_graph.load_builtin_data()

        # 初始化毛选检索器
        self.maoxuan_retriever = MaoxuanRetriever(
            db_path=self.config.maoxuan_db_dir,
        )

        # 初始化五层
        self.perception = PerceptionLayer(self.llm_client, rule_first=True)
        self.understanding = UnderstandingLayer(
            self.llm_client, self.cognitive_graph, self.maoxuan_retriever,
        )
        self.reasoning = ReasoningLayer(self.llm_client)
        self.expression = ExpressionLayer()

        # 会话管理
        self._sessions: Dict[str, MemoryLayer] = {}

        logger.info(
            "JiaoyuanEngine initialized: model=%s, thinking=%s",
            self.config.model_name,
            self.config.enable_thinking_mode,
        )

    def _get_session(self, session_id: str, user_id: str) -> MemoryLayer:
        """
        获取或创建会话

        Args:
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            MemoryLayer实例
        """
        key = f"{user_id}:{session_id}"
        if key not in self._sessions:
            self._sessions[key] = MemoryLayer(
                user_id=user_id,
                profiles_dir=self.config.profiles_dir,
                max_full_turns=self.config.max_full_turns,
            )
            logger.debug("Created new session: %s", key)
        return self._sessions[key]

    async def chat(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """
        主入口：完整的五层处理流程

        Args:
            user_input: 用户输入
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            处理结果字典：
            {
                "response": str,           # 最终回复
                "thinking": str,           # 推理过程（debug用）
                "user_intent": Dict,       # 感知层输出
                "problem_profile": Dict,   # 理解层输出
                "reasoning_result": Dict,  # 推理层输出
                "processing_time_ms": int, # 总处理时间
                "layer_timings": Dict,     # 各层耗时
            }
        """
        import time
        total_start = time.time()
        layer_timings: Dict[str, int] = {}

        logger.info("Chat: user=%s, session=%s, input='%s...'",
                     user_id, session_id, user_input[:30])

        try:
            # ================================================================
            # Step 1: 加载记忆上下文
            # ================================================================
            memory = self._get_session(session_id, user_id)
            memory_context = memory.get_context()

            # ================================================================
            # Step 2: 感知层分析
            # ================================================================
            step_start = time.time()
            user_intent = await self.perception.perceive(
                user_input, dialogue_history=memory_context.get("history", []),
            )
            layer_timings["perception"] = int((time.time() - step_start) * 1000)
            logger.info("[L1感知] topic=%s, emotion=%s, stage=%s (%dms)",
                         user_intent.topic, user_intent.emotion.value,
                         user_intent.cognitive_stage.value,
                         layer_timings["perception"])

            # ================================================================
            # Step 3: 理解层理解问题
            # ================================================================
            step_start = time.time()
            problem_profile = await self.understanding.understand(user_intent)
            layer_timings["understanding"] = int((time.time() - step_start) * 1000)
            logger.info("[L2理解] type=%s, framework=%s, methods=%d, maoxuan=%d (%dms)",
                         problem_profile.problem_type.value,
                         problem_profile.framework.value,
                         len(problem_profile.related_methods),
                         len(problem_profile.maoxuan_refs),
                         layer_timings["understanding"])

            # ================================================================
            # Step 4: 推理层深度推理
            # ================================================================
            step_start = time.time()
            reasoning_result = await self.reasoning.reason(
                user_intent, problem_profile, memory_context,
            )
            layer_timings["reasoning"] = int((time.time() - step_start) * 1000)
            logger.info("[L3推理] questions=%d, insights=%d, thinking=%d chars (%dms)",
                         len(reasoning_result.socratic_questions),
                         len(reasoning_result.key_insights),
                         len(reasoning_result.thinking_content),
                         layer_timings["reasoning"])

            # ================================================================
            # Step 5: 表达层生成回复
            # ================================================================
            step_start = time.time()
            response_text = await self.expression.express(reasoning_result, user_intent)
            layer_timings["expression"] = int((time.time() - step_start) * 1000)
            logger.info("[L5表达] response=%d chars (%dms)",
                         len(response_text), layer_timings["expression"])

            # ================================================================
            # Step 6: 保存对话到记忆
            # ================================================================
            await memory.add_turn(user_input, response_text, reasoning_result)
            memory.update_cognitive_tracker(user_intent, reasoning_result)

            # 异步持久化用户画像（不阻塞）
            asyncio.create_task(memory.persist())

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

    async def chat_stream(
        self,
        user_input: str,
        session_id: str = "default",
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式版本的主入口

        流式处理流程：
        1. 先同步完成感知层、理解层、推理层（这些不能流式）
        2. 表达层使用LLM流式输出生成回复

        Args:
            user_input: 用户输入
            session_id: 会话ID
            user_id: 用户ID

        Yields:
            内容块字典：
            - {"type": "thinking", "content": "..."}  # 推理过程
            - {"type": "status", "content": "..."}     # 状态更新
            - {"type": "content", "content": "..."}    # 回复内容
            - {"type": "done", "content": "..."}       # 完成
        """
        import time
        total_start = time.time()

        logger.info("Chat stream: user=%s, session=%s", user_id, session_id)

        try:
            # 先完成前三层（非流式）
            yield {"type": "status", "content": "感知分析中..."}

            memory = self._get_session(session_id, user_id)
            memory_context = memory.get_context()

            # 感知层
            user_intent = await self.perception.perceive(
                user_input, dialogue_history=memory_context.get("history", []),
            )
            yield {"type": "status", "content": f"理解问题中...（主题：{user_intent.topic}）"}

            # 理解层
            problem_profile = await self.understanding.understand(user_intent)
            yield {"type": "status", "content": "深度推理中..."}

            # 推理层
            reasoning_result = await self.reasoning.reason(
                user_intent, problem_profile, memory_context,
            )

            # 输出thinking内容
            if reasoning_result.thinking_content:
                yield {
                    "type": "thinking",
                    "content": reasoning_result.thinking_content,
                }

            yield {"type": "status", "content": "生成回复中..."}

            # 使用表达层生成最终回复
            # 非流式：先生成完整回复
            response_text = await self.expression.express(reasoning_result, user_intent)

            # 模拟流式输出（逐字输出）
            chunk_size = 4  # 每次4个字符
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield {"type": "content", "content": chunk}
                await asyncio.sleep(0.01)  # 小延迟模拟流式效果

            # 保存对话
            await memory.add_turn(user_input, response_text, reasoning_result)
            memory.update_cognitive_tracker(user_intent, reasoning_result)
            asyncio.create_task(memory.persist())

            total_time = int((time.time() - total_start) * 1000)
            yield {
                "type": "done",
                "content": "",
                "processing_time_ms": total_time,
            }

        except Exception as e:
            logger.exception("Stream processing failed: %s", e)
            yield {
                "type": "error",
                "content": str(e),
            }

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

    async def __aenter__(self) -> JiaoyuanEngine:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()
