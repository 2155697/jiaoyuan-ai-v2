"""教员AI顾问 - 记忆层

记忆层管理三种记忆：
1. DialogueMemory: 对话历史记忆（滑动窗口+摘要）
2. UserProfileDB: 跨对话用户画像（JSON持久化）
3. CognitiveTracker: 认知状态追踪（目标→方案→环节→需求→因素→评估循环）

作者: AI系统架构师
版本: 3.0.1
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from models import (
    CognitiveState, DialogueTurn, ReasoningResult,
    UserIntent, UserProfile, DecisionStyle,
)

logger = logging.getLogger(__name__)


class DialogueMemory:
    """对话历史记忆：管理当前对话的完整上下文"""

    def __init__(
        self,
        max_full_turns: int = 10,
        max_context_tokens: int = 8000,
    ):
        self.max_full_turns = max_full_turns
        self.max_context_tokens = max_context_tokens
        self.turns: List[DialogueTurn] = []
        self.summary: str = ""
        self._lock = asyncio.Lock()

    async def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        reasoning_result: Optional[ReasoningResult] = None,
    ) -> None:
        async with self._lock:
            turn = DialogueTurn(
                user_input=user_input,
                assistant_response=assistant_response,
                timestamp=time.time(),
                reasoning_result=reasoning_result,
            )
            self.turns.append(turn)

            if len(self.turns) > self.max_full_turns:
                await self._summarize_older_turns()

    async def _summarize_older_turns(self) -> None:
        older_turns = self.turns[:-self.max_full_turns]
        self.turns = self.turns[-self.max_full_turns:]

        key_points = []
        for turn in older_turns:
            key_points.append(f"- 用户：{turn.user_input[:50]}...")
            key_points.append(f"  回复：{turn.assistant_response[:50]}...")

        if key_points:
            self.summary += "\n".join(key_points) + "\n"

    def get_context(self, max_turns: int = 10) -> str:
        parts = []
        if self.summary:
            parts.append(f"[历史摘要]\n{self.summary}")

        recent_turns = self.turns[-max_turns:]
        if recent_turns:
            parts.append("[最近对话]")
            for turn in recent_turns:
                parts.append(f"用户: {turn.user_input}")
                parts.append(f"教员: {turn.assistant_response}")

        return "\n".join(parts)

    def get_recent_history(self, n: int = 5) -> List[Dict[str, str]]:
        return [
            {"user": t.user_input, "assistant": t.assistant_response}
            for t in self.turns[-n:]
        ]

    def clear(self) -> None:
        self.turns = []
        self.summary = ""

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_turns": len(self.turns),
            "full_turns": len(self.turns),
            "summary_length": len(self.summary),
        }


class UserProfileDB:
    """用户画像数据库：本地JSON文件存储"""

    def __init__(self, profiles_dir: str = "data/profiles"):
        self.profiles_dir = profiles_dir
        os.makedirs(profiles_dir, exist_ok=True)

    def _get_profile_path(self, user_id: str) -> str:
        safe_id = user_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.profiles_dir, f"{safe_id}.json")

    def load(self, user_id: str) -> Optional[UserProfile]:
        profile_path = self._get_profile_path(user_id)
        if not os.path.exists(profile_path):
            return None

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "cognitive_preferences" not in data:
                data["cognitive_preferences"] = {}
            if "thinking_patterns" not in data:
                data["thinking_patterns"] = {}

            return UserProfile(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Failed to load profile for %s: %s", user_id, e)
            return None

    def save(self, profile: UserProfile) -> None:
        profile_path = self._get_profile_path(profile.user_id)
        os.makedirs(os.path.dirname(profile_path) or ".", exist_ok=True)

        profile.updated_at = time.time()

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)

        logger.debug("Profile saved for user %s", profile.user_id)

    def create_default(self, user_id: str) -> UserProfile:
        """创建默认用户画像 —— 修复：使用枚举替代字符串"""
        return UserProfile(
            user_id=user_id,
            created_at=time.time(),
            updated_at=time.time(),
            decision_style=DecisionStyle.UNKNOWN,  # 修复：枚举替代 "unknown"
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
        if not dialogue_turns:
            return

        profile = self.load(user_id) or self.create_default(user_id)

        profile.total_turns += len(dialogue_turns)
        profile.total_dialogues += 1

        total_sessions = profile.total_dialogues
        profile.avg_session_length = (
            (profile.avg_session_length * (total_sessions - 1) + len(dialogue_turns))
            / total_sessions
        )

        self.save(profile)
        logger.info("Profile updated for user %s", user_id)


class CognitiveTracker:
    """认知状态追踪器"""

    CYCLE_STAGES = ["goal", "plan", "steps", "needs", "factors", "assessment"]

    def __init__(self):
        self.current_stage: str = "goal"
        self.stage_progress: Dict[str, Dict[str, Any]] = {
            stage: {"completed": False, "notes": ""}
            for stage in self.CYCLE_STAGES
        }
        self.loop_count: int = 0
        self.history: List[Dict[str, Any]] = []

    def update(self, user_intent: UserIntent, reasoning_result: ReasoningResult) -> None:
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

        for stage, completed in (user_intent.cognitive_cycle_position or {}).items():
            if stage in self.stage_progress:
                if completed and not self.stage_progress[stage]["completed"]:
                    self.stage_progress[stage]["completed"] = True
                    self.history.append({
                        "stage": stage,
                        "completed_at": time.time(),
                        "loop": self.loop_count,
                    })

        if all(self.stage_progress[s]["completed"] for s in self.CYCLE_STAGES):
            self.loop_count += 1
            for stage in self.CYCLE_STAGES:
                self.stage_progress[stage]["completed"] = False
                self.stage_progress[stage]["notes"] = ""

            self.history.append({
                "event": "loop_completed",
                "loop": self.loop_count,
                "timestamp": time.time(),
            })

    def get_current_focus(self) -> str:
        for stage in self.CYCLE_STAGES:
            if not self.stage_progress[stage]["completed"]:
                return stage
        return "assessment"

    def get_progress_summary(self) -> str:
        completed = sum(
            1 for s in self.CYCLE_STAGES
            if self.stage_progress[s]["completed"]
        )
        focus = self.get_current_focus()
        return f"第{self.loop_count + 1}轮循环，已完成{completed}/6个阶段，当前聚焦：{focus}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "stage_progress": self.stage_progress,
            "loop_count": self.loop_count,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveTracker":
        tracker = cls()
        tracker.current_stage = data.get("current_stage", "goal")
        tracker.stage_progress = data.get("stage_progress", tracker.stage_progress)
        tracker.loop_count = data.get("loop_count", 0)
        tracker.history = data.get("history", [])
        return tracker


class MemoryLayer:
    """记忆层：整合对话记忆、用户画像、认知追踪的统一入口"""

    def __init__(
        self,
        user_id: str = "anonymous",
        profiles_dir: str = "data/profiles",
        max_full_turns: int = 10,
    ):
        self.user_id = user_id
        self.dialogue_memory = DialogueMemory(max_full_turns=max_full_turns)
        self.user_profile_db = UserProfileDB(profiles_dir)
        self.cognitive_tracker = CognitiveTracker()

        self.user_profile = self.user_profile_db.load(user_id)
        if self.user_profile is None:
            self.user_profile = self.user_profile_db.create_default(user_id)
            self.user_profile_db.save(self.user_profile)

        logger.info(
            "MemoryLayer initialized: user=%s, profile_exists=%s",
            user_id, self.user_profile is not None,
        )

    def get_context(self) -> Dict[str, Any]:
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
        await self.dialogue_memory.add_turn(user_input, assistant_response, reasoning_result)

    def update_cognitive_tracker(
        self,
        user_intent: UserIntent,
        reasoning_result: ReasoningResult,
    ) -> None:
        self.cognitive_tracker.update(user_intent, reasoning_result)

    async def persist(self) -> None:
        await self.user_profile_db.update_from_dialogue(
            self.user_id, self.dialogue_memory.turns,
        )

    def get_stats(self) -> Dict[str, Any]:
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
