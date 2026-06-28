"""
教员AI顾问 - 记忆层

记忆层管理三种记忆：
1. DialogueMemory: 对话历史记忆（滑动窗口+摘要）
2. UserProfileDB: 跨对话用户画像（JSON持久化）
3. CognitiveTracker: 认知状态追踪（目标→方案→环节→需求→因素→评估循环）

特性：
- 对话历史：滑动窗口管理，超窗对话自动摘要
- 用户画像：JSON文件持久化，跨对话可用
- 认知追踪：教员思维的核心循环追踪
- 异步持久化，不阻塞主流程

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from models import (
    CognitiveState, DialogueTurn, ReasoningResult,
    UserIntent, UserProfile,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 对话历史记忆
# ============================================================================

class DialogueMemory:
    """
    对话历史记忆：管理当前对话的完整上下文

    使用滑动窗口 + 摘要机制管理上下文长度：
    - 最近N轮完整保留（默认10轮）
    - 更早的对话用摘要替代
    - 总token数控制在合理范围内
    """

    def __init__(
        self,
        max_full_turns: int = 10,
        max_context_tokens: int = 8000,
    ):
        """
        初始化对话历史记忆

        Args:
            max_full_turns: 保留完整轮次的最大数量
            max_context_tokens: 最大上下文token数
        """
        self.max_full_turns = max_full_turns
        self.max_context_tokens = max_context_tokens
        self.turns: List[DialogueTurn] = []
        self.summary: str = ""
        self._lock = asyncio.Lock()

        logger.debug(
            "DialogueMemory initialized: max_full_turns=%d",
            max_full_turns,
        )

    async def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        reasoning_result: Optional[ReasoningResult] = None,
    ) -> None:
        """
        添加一轮对话

        Args:
            user_input: 用户输入
            assistant_response: 助手回复
            reasoning_result: 推理结果（可选）
        """
        async with self._lock:
            turn = DialogueTurn(
                user_input=user_input,
                assistant_response=assistant_response,
                timestamp=time.time(),
                reasoning_result=reasoning_result,
            )
            self.turns.append(turn)

            # 如果超出窗口，生成摘要
            if len(self.turns) > self.max_full_turns:
                await self._summarize_older_turns()

    async def _summarize_older_turns(self) -> None:
        """将超出窗口的老对话生成摘要"""
        older_turns = self.turns[:-self.max_full_turns]
        self.turns = self.turns[-self.max_full_turns:]

        # 简化摘要：直接拼接关键信息
        key_points = []
        for turn in older_turns:
            key_points.append(f"- 用户：{turn.user_input[:50]}...")
            key_points.append(f"  回复：{turn.assistant_response[:50]}...")

        if key_points:
            self.summary += "\n".join(key_points) + "\n"

    def get_context(self, max_turns: int = 10) -> str:
        """
        获取格式化的对话上下文

        格式：
        [历史摘要]
        {summary}

        [最近对话]
        用户: ...
        教员: ...

        Args:
            max_turns: 最大轮次数

        Returns:
            格式化的对话上下文字符串
        """
        parts = []

        # 摘要部分
        if self.summary:
            parts.append(f"[历史摘要]\n{self.summary}")

        # 最近对话
        recent_turns = self.turns[-max_turns:]
        if recent_turns:
            parts.append("[最近对话]")
            for i, turn in enumerate(recent_turns, 1):
                parts.append(f"用户: {turn.user_input}")
                parts.append(f"教员: {turn.assistant_response}")

        return "\n".join(parts)

    def get_recent_history(self, n: int = 5) -> List[Dict[str, str]]:
        """
        获取最近N轮对话历史

        Args:
            n: 轮次数

        Returns:
            对话历史列表
        """
        return [
            {"user": t.user_input, "assistant": t.assistant_response}
            for t in self.turns[-n:]
        ]

    def clear(self) -> None:
        """清空对话记忆"""
        self.turns = []
        self.summary = ""

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_turns": len(self.turns),
            "full_turns": len(self.turns),
            "summary_length": len(self.summary),
        }


# ============================================================================
# 用户画像数据库
# ============================================================================

class UserProfileDB:
    """
    用户画像数据库：本地JSON文件存储

    存储在 data/profiles/{user_id}.json
    每次对话结束后更新用户画像
    """

    def __init__(self, profiles_dir: str = "data/profiles"):
        """
        初始化用户画像数据库

        Args:
            profiles_dir: 用户画像存储目录
        """
        self.profiles_dir = profiles_dir
        os.makedirs(profiles_dir, exist_ok=True)

    def _get_profile_path(self, user_id: str) -> str:
        """获取用户画像文件路径"""
        safe_id = user_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.profiles_dir, f"{safe_id}.json")

    def load(self, user_id: str) -> Optional[UserProfile]:
        """
        加载用户画像

        Args:
            user_id: 用户ID

        Returns:
            UserProfile或None
        """
        profile_path = self._get_profile_path(user_id)
        if not os.path.exists(profile_path):
            return None

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容旧格式
            if "cognitive_preferences" not in data:
                data["cognitive_preferences"] = {}
            if "thinking_patterns" not in data:
                data["thinking_patterns"] = {}

            return UserProfile(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Failed to load profile for %s: %s", user_id, e)
            return None

    def save(self, profile: UserProfile) -> None:
        """
        保存用户画像

        Args:
            profile: 用户画像
        """
        profile_path = self._get_profile_path(profile.user_id)
        os.makedirs(os.path.dirname(profile_path) or ".", exist_ok=True)

        profile.updated_at = time.time()

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)

        logger.debug("Profile saved for user %s", profile.user_id)

    def create_default(self, user_id: str) -> UserProfile:
        """
        创建默认用户画像

        Args:
            user_id: 用户ID

        Returns:
            默认用户画像
        """
        return UserProfile(
            user_id=user_id,
            created_at=time.time(),
            updated_at=time.time(),
            decision_style="unknown",
            common_confusion_areas=[],
            thinking_patterns={},
            cognitive_preferences={},
            total_dialogues=0,
            total_turns=0,
            avg_session_length=0.0,
            key_insights=[],
            feedback_history=[],
        )

    async def update_from_dialogue(
        self,
        user_id: str,
        dialogue_turns: List[DialogueTurn],
    ) -> None:
        """
        从对话历史中更新用户画像（异步）

        Args:
            user_id: 用户ID
            dialogue_turns: 对话轮次列表
        """
        if not dialogue_turns:
            return

        profile = self.load(user_id) or self.create_default(user_id)

        # 更新统计
        profile.total_turns += len(dialogue_turns)
        profile.total_dialogues += 1

        # 更新平均会话长度
        total_sessions = profile.total_dialogues
        profile.avg_session_length = (
            (profile.avg_session_length * (total_sessions - 1) + len(dialogue_turns))
            / total_sessions
        )

        self.save(profile)
        logger.info("Profile updated for user %s", user_id)


# ============================================================================
# 认知状态追踪器
# ============================================================================

class CognitiveTracker:
    """
    认知状态追踪器：追踪用户在问题解决循环中的位置

    教员思维的核心循环：
    目标(Goal) → 方案(Plan) → 环节(Steps) → 需求(Needs) → 因素(Factors) → 评估(Assessment)
                              ↑_________________________________________________↓

    这个循环是无限的，每一轮评估后回到目标（或调整目标）。
    """

    CYCLE_STAGES = ["goal", "plan", "steps", "needs", "factors", "assessment"]

    def __init__(self):
        """初始化认知状态追踪器"""
        self.current_stage: str = "goal"
        self.stage_progress: Dict[str, Dict[str, Any]] = {
            stage: {"completed": False, "notes": ""}
            for stage in self.CYCLE_STAGES
        }
        self.loop_count: int = 0
        self.history: List[Dict[str, Any]] = []

    def update(self, user_intent: UserIntent, reasoning_result: ReasoningResult) -> None:
        """
        根据当前对话更新认知状态

        更新逻辑：
        1. 根据用户意图判断当前所处阶段
        2. 标记已完成的阶段
        3. 记录阶段转换
        4. 判断是否完成一个大循环

        Args:
            user_intent: 用户意图
            reasoning_result: 推理结果
        """
        # 根据认知阶段和对话内容推断当前所处循环位置
        stage_mapping = {
            "problem_statement": "goal",
            "information_seeking": "needs",
            "option_exploration": "plan",
            "decision_struggle": "factors",
            "action_confirmation": "assessment",
            "reflection": "assessment",
        }

        inferred_stage = stage_mapping.get(user_intent.cognitive_stage.value, "goal")
        self.current_stage = inferred_stage

        # 更新进度（基于认知循环位置）
        for stage, completed in (user_intent.cognitive_cycle_position or {}).items():
            if stage in self.stage_progress:
                if completed and not self.stage_progress[stage]["completed"]:
                    self.stage_progress[stage]["completed"] = True
                    self.history.append({
                        "stage": stage,
                        "completed_at": time.time(),
                        "loop": self.loop_count,
                    })

        # 检查是否完成一个完整循环
        if all(self.stage_progress[s]["completed"] for s in self.CYCLE_STAGES):
            self.loop_count += 1
            # 重置进度，开始新循环
            for stage in self.CYCLE_STAGES:
                self.stage_progress[stage]["completed"] = False
                self.stage_progress[stage]["notes"] = ""

            self.history.append({
                "event": "loop_completed",
                "loop": self.loop_count,
                "timestamp": time.time(),
            })

    def get_current_focus(self) -> str:
        """
        获取当前应该聚焦的阶段

        Returns:
            当前阶段名称
        """
        for stage in self.CYCLE_STAGES:
            if not self.stage_progress[stage]["completed"]:
                return stage
        return "assessment"

    def get_progress_summary(self) -> str:
        """
        获取进度摘要

        Returns:
            进度摘要字符串
        """
        completed = sum(
            1 for s in self.CYCLE_STAGES
            if self.stage_progress[s]["completed"]
        )
        focus = self.get_current_focus()
        return f"第{self.loop_count + 1}轮循环，已完成{completed}/6个阶段，当前聚焦：{focus}"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "current_stage": self.current_stage,
            "stage_progress": self.stage_progress,
            "loop_count": self.loop_count,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveTracker":
        """从字典反序列化"""
        tracker = cls()
        tracker.current_stage = data.get("current_stage", "goal")
        tracker.stage_progress = data.get("stage_progress", tracker.stage_progress)
        tracker.loop_count = data.get("loop_count", 0)
        tracker.history = data.get("history", [])
        return tracker


# ============================================================================
# 记忆层统一入口
# ============================================================================

class MemoryLayer:
    """
    记忆层：整合对话记忆、用户画像、认知追踪的统一入口

    用法：
        memory = MemoryLayer(user_id="user_123")
        context = memory.get_context()
        memory.add_turn("用户输入", "助手回复")
        memory.update_cognitive_tracker(user_intent, reasoning_result)
        await memory.persist()
    """

    def __init__(
        self,
        user_id: str = "anonymous",
        profiles_dir: str = "data/profiles",
        max_full_turns: int = 10,
    ):
        """
        初始化记忆层

        Args:
            user_id: 用户ID
            profiles_dir: 用户画像存储目录
            max_full_turns: 对话窗口保留完整轮次
        """
        self.user_id = user_id
        self.dialogue_memory = DialogueMemory(max_full_turns=max_full_turns)
        self.user_profile_db = UserProfileDB(profiles_dir)
        self.cognitive_tracker = CognitiveTracker()

        # 加载用户画像
        self.user_profile = self.user_profile_db.load(user_id)
        if self.user_profile is None:
            self.user_profile = self.user_profile_db.create_default(user_id)
            self.user_profile_db.save(self.user_profile)

        logger.info(
            "MemoryLayer initialized: user=%s, profile_exists=%s",
            user_id, self.user_profile is not None,
        )

    def get_context(self) -> Dict[str, Any]:
        """
        获取增强的上下文信息

        Returns:
            上下文字典：
            {
                "dialogue_context": str,      # 对话历史上下文
                "user_profile": UserProfile,   # 用户画像
                "cognitive_state": str,        # 认知状态摘要
                "cognitive_tracker": Dict,     # 认知追踪器数据
                "history": List[Dict],         # 最近对话记录
            }
        """
        return {
            "dialogue_context": self.dialogue_memory.get_context(),
            "user_profile": self.user_profile,
            "cognitive_state": self.cognitive_tracker.get_progress_summary(),
            "cognitive_tracker": self.cognitive_tracker.to_dict(),
            "history": self.dialogue_memory.get_recent_history(n=5),
        }

    async def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        reasoning_result: Optional[ReasoningResult] = None,
    ) -> None:
        """
        添加对话轮次

        Args:
            user_input: 用户输入
            assistant_response: 助手回复
            reasoning_result: 推理结果（可选）
        """
        await self.dialogue_memory.add_turn(user_input, assistant_response, reasoning_result)

    def update_cognitive_tracker(
        self,
        user_intent: UserIntent,
        reasoning_result: ReasoningResult,
    ) -> None:
        """
        更新认知追踪器

        Args:
            user_intent: 用户意图
            reasoning_result: 推理结果
        """
        self.cognitive_tracker.update(user_intent, reasoning_result)

    async def persist(self) -> None:
        """持久化用户画像（对话结束后异步调用）"""
        await self.user_profile_db.update_from_dialogue(
            self.user_id, self.dialogue_memory.turns,
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "user_id": self.user_id,
            "dialogue": self.dialogue_memory.get_stats(),
            "cognitive": {
                "current_stage": self.cognitive_tracker.current_stage,
                "loop_count": self.cognitive_tracker.loop_count,
            },
            "profile": {
                "total_dialogues": self.user_profile.total_dialogues if self.user_profile else 0,
                "total_turns": self.user_profile.total_turns if self.user_profile else 0,
            },
        }
