"""
教员AI顾问 - 表达层

表达层将推理结果转化为"教员风格"的自然语言回复：
1. LanguageDNA: 教员语言风格DNA（句长、比喻、句式）
2. ToneAdjuster: 语气调节器（根据情绪调整）
3. FormatController: 格式控制器（回复结构）

回复格式：
- 开头：称呼 + 情境共鸣
- 提问：1-2个引导性问题（核心）
- 分析：简要分析（比喻、辩证句式）
- 结尾：鼓励 + 开放

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any, Dict, List, Optional

from models import (
    ContradictionAnalysis, EmotionType, FiveLayerAnalysis,
    PhaseAssessment, ReasoningResult, SocraticQuestion, UserIntent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 教员语言风格DNA
# ============================================================================

class LanguageDNA:
    """
    教员语言风格DNA：编码教员的语言特征

    基于毛选原文和教员讲话的语言特征：
    1. 句长特征：平均20字/句，短句为主
    2. 比喻特征：大量使用战争比喻、自然比喻
    3. 句式特征：辩证句式、肯定句式
    4. 称呼特征："同志"、"我们"、"大家"
    5. 语气特征：坚定、鼓舞、启发
    """

    # 比喻模板库
    METAPHOR_TEMPLATES: Dict[str, List[str]] = {
        "war": [
            "这就像打仗，{situation}是{phase}阶段",
            "要讲究{strategy}，不能{wrong_action}",
            "{challenge}是{enemy}，我们要{tactic}",
            "这是场{scale}的{war_type}，{action}才能{tactic}",
            "面对{challenge}，要{strategy}，不要{wrong_action}",
        ],
        "nature": [
            "事物发展就像{natural_process}，{current}是{stage}",
            "{situation}不是一天形成的，要{patience}",
            "{goal}就像{destination}，{action}才能到达",
            "{situation}好比{metaphor}，{action}才能{result}",
            "天要下雨，娘要嫁人，{situation}要{action}",
        ],
    }

    # 辩证句式模板
    DIALECTICAL_PATTERNS: List[str] = [
        "既要看到{positive}，也要看到{negative}",
        "不是{wrong}，而是{right}",
        "表面上看{surface}，实际上{reality}",
        "一方面{aspect_a}，另一方面{aspect_b}",
        "从短期看{short_term}，从长远看{long_term}",
    ]

    # 肯定句式模板
    AFFIRMATIVE_PATTERNS: List[str] = [
        "{conclusion}，这是确定的",
        "{action}，没有别的出路",
        "{situation}，{judgment}",
        "只要{condition}，就一定{result}",
        "{action}，这是唯一的办法",
    ]

    # 战争比喻词汇
    WAR_WORDS: List[str] = [
        "打仗", "战斗", "战线", "阵地", "进攻", "防御",
        "战略", "战术", "战役", "冲锋", "突围", "阻击",
        "游击", "正规战", "持久战", "速决战", "歼灭战",
    ]

    # 自然比喻词汇
    NATURE_WORDS: List[str] = [
        "水流", "种子", "大树", "风雨", "太阳", "道路",
        "山峰", "河流", "大海", "航船", "朝日", "婴儿",
        "种子", "火苗", "星星", "春天", "寒冬", "黎明",
    ]

    # 辩证词汇
    DIALECTICAL_WORDS: List[str] = [
        "两面", "矛盾", "转化", "发展", "变化",
        "对立", "统一", "主次", "因果", "条件",
    ]

    def __init__(self):
        """初始化语言DNA"""
        pass

    def apply(self, text: str, tone: str = "encouraging") -> str:
        """
        将普通文本转化为教员风格

        处理流程：
        1. 调整句长（拆分长句）
        2. 插入比喻
        3. 应用辩证句式
        4. 添加称呼
        5. 增强节奏感

        Args:
            text: 原始文本
            tone: 语气基调

        Returns:
            教员风格文本

        耗时目标: <500ms
        """
        if not text:
            return text

        # 1. 调整句长
        text = self._adjust_sentence_length(text)

        # 2. 插入比喻（适度）
        if random.random() < 0.3:
            text = self._insert_metaphor(text)

        # 3. 增强节奏感
        text = self._enhance_rhythm(text)

        return text

    def _adjust_sentence_length(self, text: str) -> str:
        """调整句长：拆分长句，增加短句"""
        sentences = re.split(r'([。！？；\.\n])', text)
        result = []

        for i, s in enumerate(sentences):
            if s in '。！？；.\n':
                result.append(s)
                continue

            # 如果句子超过35字，尝试拆分
            if len(s) > 35:
                # 尝试按逗号拆分
                parts = s.split('，')
                if len(parts) >= 2 and all(len(p) > 5 for p in parts):
                    # 合理拆分
                    mid = len(parts) // 2
                    first_half = '，'.join(parts[:mid])
                    second_half = '，'.join(parts[mid:])
                    if len(first_half) > 10 and len(second_half) > 10:
                        result.append(first_half + '。')
                        result.append(second_half)
                    else:
                        result.append(s)
                else:
                    result.append(s)
            else:
                result.append(s)

        return ''.join(result)

    def _insert_metaphor(self, text: str) -> str:
        """在适当位置插入比喻"""
        lines = text.split('\n')
        result = []

        for line in lines:
            if len(line) > 20 and random.random() < 0.3:
                # 随机选择一个自然比喻
                metaphor = random.choice(self.METAPHOR_TEMPLATES["nature"])
                filled = metaphor.format(
                    natural_process="种子发芽",
                    current="现在的情况",
                    stage="萌芽阶段",
                    situation=line[:15] if len(line) > 15 else line,
                    patience="有耐心",
                    goal="目标",
                    destination="远方的山",
                    action="一步步走",
                    metaphor="爬山",
                    result="看到风景",
                )
                result.append(line)
                result.append(filled)
            else:
                result.append(line)

        return '\n'.join(result)

    def _enhance_rhythm(self, text: str) -> str:
        """增强节奏感"""
        # 在适当位置添加停顿
        text = re.sub(r'([。！？])\s*', r'\1\n', text)
        return text

    def generate_war_metaphor(self, situation: str, phase: str) -> str:
        """生成战争比喻"""
        template = random.choice(self.METAPHOR_TEMPLATES["war"])
        return template.format(
            situation=situation,
            phase=phase,
            strategy="灵活机动",
            wrong_action="硬拼",
            challenge="困难",
            enemy="纸老虎",
            tactic="逐步击破",
            scale="小规模",
            war_type="遭遇战",
            action="集中力量",
        )

    def generate_nature_metaphor(self, situation: str, stage: str) -> str:
        """生成自然比喻"""
        template = random.choice(self.METAPHOR_TEMPLATES["nature"])
        return template.format(
            natural_process="种子发芽",
            current=situation,
            stage=stage,
            situation=situation,
            patience="有耐心",
            goal="目标",
            destination="远方的山",
            action="一步步走",
            metaphor="爬山",
            result="看到风景",
        )


# ============================================================================
# 语气调节器
# ============================================================================

class ToneAdjuster:
    """
    语气调节器：根据用户状态调整回复语气

    调节策略：
    - 迷茫时 → 启发+鼓励
    - 焦虑时 → 坚定+安抚
    - 坚定时 → 严肃+提醒
    - 犹豫时 → 启发+推动
    - 挫败时 → 鼓励+共情
    - 期待时 → 肯定+引导
    """

    TONE_MAP: Dict[str, Dict[str, Any]] = {
        "confused": {
            "style": "启发+鼓励",
            "openings": ["先不要急", "慢慢来", "我们一起来看", "这个情况嘛"],
            "keywords": ["想清楚", "搞明白", "理一理", "一步步来"],
            "pace": "slow",
        },
        "anxious": {
            "style": "坚定+安抚",
            "openings": ["不要怕", "别急", "冷静一下", "听我说"],
            "keywords": ["能行", "有办法", "会好的", "没问题"],
            "pace": "steady",
        },
        "determined": {
            "style": "严肃+提醒",
            "openings": ["有这个决心很好", "方向对了", "但是要注意"],
            "keywords": ["但要注意", "别忘了", "还要看到", "不要大意"],
            "pace": "moderate",
        },
        "hesitant": {
            "style": "启发+推动",
            "openings": ["这个要你自己判断", "关键是", "想想看"],
            "keywords": ["想想看", "你说呢", "是不是", "对不对"],
            "pace": "slow",
        },
        "frustrated": {
            "style": "鼓励+共情",
            "openings": ["受挫是正常的", "谁都会遇到困难", "不要灰心"],
            "keywords": ["坚持", "再试", "不放弃", "没关系"],
            "pace": "slow",
        },
        "hopeful": {
            "style": "肯定+引导",
            "openings": ["这个势头很好", "有希望", "方向对了"],
            "keywords": ["继续保持", "下一步", "要注意", "再接再厉"],
            "pace": "moderate",
        },
        "overwhelmed": {
            "style": "安抚+分解",
            "openings": ["先不要急", "事情要一件一件做", "把大问题拆开"],
            "keywords": ["分解", "一步一步", "不急", "慢慢来"],
            "pace": "slow",
        },
    }

    def __init__(self):
        """初始化语气调节器"""
        pass

    def adjust(
        self,
        base_text: str,
        emotion: EmotionType,
        emotion_intensity: float,
    ) -> str:
        """
        根据情绪调整语气

        Args:
            base_text: 原始文本
            emotion: 情绪类型
            emotion_intensity: 情绪强度

        Returns:
            调整后的文本
        """
        if not base_text:
            return base_text

        tone_config = self.TONE_MAP.get(emotion.value)
        if not tone_config:
            return base_text

        # 根据强度调整
        intensity_factor = min(emotion_intensity, 1.0)

        # 添加开头语（高情绪强度时）
        if intensity_factor > 0.6 and tone_config["openings"]:
            opening = random.choice(tone_config["openings"])
            if not base_text.startswith(opening):
                # 在第一句话前添加
                lines = base_text.split('\n')
                if lines:
                    lines[0] = opening + "，" + lines[0].lstrip('，')
                base_text = '\n'.join(lines)

        # 调整节奏（根据pace）
        if tone_config["pace"] == "slow":
            # 慢节奏：多使用逗号、句号
            base_text = self._slow_down(base_text)

        return base_text

    def _slow_down(self, text: str) -> str:
        """降低语速节奏"""
        # 在长句中添加停顿
        text = re.sub(r'(.{15,20}[,，])', r'\1\n', text)
        return text


# ============================================================================
# 格式控制器
# ============================================================================

class FormatController:
    """
    格式控制器：控制回复的结构和格式

    回复格式（教员风格）：
    1. 开头：称呼 + 情境共鸣（"同志啊，你这个情况..."）
    2. 提问：1-2个引导性问题（核心）
    3. 分析：简要分析（比喻、辩证句式）
    4. 结尾：鼓励 + 开放（"你觉得呢？"）
    """

    # 称呼列表
    ADDRESS_FORMS: List[str] = ["同志", "我们", "大家"]

    # 情境共鸣模板
    RESONANCE_TEMPLATES: Dict[str, List[str]] = {
        "confused": [
            "你现在这个状态，让我想起很多同志在转折时期的困惑",
            "这种迷茫的感觉，很多同志都有过",
            "你现在的情况，在革命过程中很常见",
        ],
        "anxious": [
            "你的担心我理解，面对这样的情况确实不容易",
            "这个焦虑的心情，说明你对这件事很上心",
            "不要怕，很多同志都经历过这样的时刻",
        ],
        "frustrated": [
            "受挫是正常的，革命哪有一帆风顺的",
            "遇到困难说明你在做实事，不要怕",
            "这个挫折是暂时的，关键是总结经验",
        ],
        "determined": [
            "你这个决心很好，有了决心事情就成了一半",
            "有这个态度，事情就有了方向",
            "坚定信念很重要，但也要看到困难",
        ],
        "hesitant": [
            "拿不定主意是正常的，说明你在认真思考",
            "犹豫说明你在权衡，这是好事",
            "这个选择确实不容易，要仔细想",
        ],
        "hopeful": [
            "这个势头很好，要保持下去",
            "看到希望了，这是好的开始",
            "你这个方向是对的，继续走下去",
        ],
        "overwhelmed": [
            "事情多是事实，但要一件一件来",
            "压力大说明责任大，但要分清主次",
            "不要急，把大问题拆开就小了",
        ],
    }

    # 鼓励结尾模板
    ENDING_TEMPLATES: Dict[str, List[str]] = {
        "confused": ["慢慢来，想清楚就好办。你觉得呢？", "理一理，思路就会清晰。你说呢？"],
        "anxious": ["不要怕，有办法的。你怎么看？", "稳住，一步一步来。你说呢？"],
        "frustrated": ["坚持下去，曙光就在前面。你觉得呢？", "不要灰心，总结经验再来。你说呢？"],
        "determined": ["有这个决心就好，但要注意方法。你说呢？", "方向对了，关键是执行。你觉得呢？"],
        "hesitant": ["仔细想想，不急着下结论。你怎么看？", "权衡利弊，选准了再干。你说呢？"],
        "hopeful": ["继续保持，事情会越来越好。你觉得呢？", "有希望，但不要放松警惕。你说呢？"],
        "overwhelmed": ["一件一件来，总能做完的。你觉得呢？", "分清主次，先解决主要矛盾。你说呢？"],
    }

    def __init__(self):
        """初始化格式控制器"""
        pass

    def format_response(
        self,
        reasoning_result: ReasoningResult,
        user_intent: UserIntent,
    ) -> str:
        """
        格式化最终回复

        Args:
            reasoning_result: 推理结果
            user_intent: 用户意图

        Returns:
            格式化回复
        """
        parts = []

        # 1. 情境共鸣开头
        resonance = self._generate_resonance(user_intent)
        if resonance:
            parts.append(resonance)

        # 2. 引导性问题（从苏格拉底提问中选择最重要的1-2个）
        questions = reasoning_result.socratic_questions[:2]
        for q in questions:
            parts.append(f"{q.question}")

        # 3. 简要分析
        analysis = self._generate_analysis(reasoning_result, user_intent)
        if analysis:
            parts.append(analysis)

        # 4. 结尾
        ending = self._generate_ending(user_intent)
        if ending:
            parts.append(ending)

        return "\n\n".join(parts)

    def _generate_resonance(self, user_intent: UserIntent) -> str:
        """生成情境共鸣开头"""
        emotion = user_intent.emotion.value
        templates = self.RESONANCE_TEMPLATES.get(emotion, self.RESONANCE_TEMPLATES["confused"])
        resonance = random.choice(templates)

        # 添加称呼
        address = random.choice(self.ADDRESS_FORMS)
        return f"{address}啊，{resonance}。"

    def _generate_analysis(
        self,
        reasoning_result: ReasoningResult,
        user_intent: UserIntent,
    ) -> str:
        """生成简要分析"""
        analysis_parts = []

        # 从矛盾分析中提取
        if reasoning_result.contradiction_analysis:
            ca = reasoning_result.contradiction_analysis
            if ca.primary_contradiction:
                analysis_parts.append(
                    f"这件事的核心是{ca.primary_contradiction}。"
                )
            if ca.aspects:
                aspects_str = "和".join([f"{k}面是{v}" for k, v in list(ca.aspects.items())[:2]])
                analysis_parts.append(f"一方面{aspects_str}，要看到两面。")

        # 从阶段评估中提取
        if reasoning_result.phase_assessment:
            pa = reasoning_result.phase_assessment
            if pa.assessment:
                analysis_parts.append(pa.assessment)

        # 从五层分析中提取
        if reasoning_result.five_layer_analysis:
            fl = reasoning_result.five_layer_analysis
            if fl.missing_layers:
                analysis_parts.append(
                    f"目前{'、'.join(fl.missing_layers[:2])}还需要进一步明确。"
                )

        # 如果没有专项分析，使用关键洞察
        if not analysis_parts and reasoning_result.key_insights:
            insight = reasoning_result.key_insights[0]
            analysis_parts.append(f"{insight}。")

        return "".join(analysis_parts) if analysis_parts else ""

    def _generate_ending(self, user_intent: UserIntent) -> str:
        """生成鼓励+开放结尾"""
        emotion = user_intent.emotion.value
        templates = self.ENDING_TEMPLATES.get(emotion, self.ENDING_TEMPLATES["confused"])
        return random.choice(templates)


# ============================================================================
# 表达层统一入口
# ============================================================================

class ExpressionLayer:
    """
    表达层：整合语言DNA、语气调节、格式控制

    执行流程：
    1. 格式控制器：组装回复结构
    2. 语言DNA：应用教员语言风格
    3. 语气调节器：根据用户情绪调整
    4. 后处理：确保长度、格式

    总耗时目标: <1000ms（纯文本处理，不调用LLM）
    """

    def __init__(self):
        """初始化表达层"""
        self.language_dna = LanguageDNA()
        self.tone_adjuster = ToneAdjuster()
        self.format_controller = FormatController()

        logger.info("ExpressionLayer initialized")

    async def express(
        self,
        reasoning_result: ReasoningResult,
        user_intent: UserIntent,
    ) -> str:
        """
        表达层主入口

        Args:
            reasoning_result: 推理结果
            user_intent: 用户意图

        Returns:
            最终自然语言回复
        """
        import time
        start_time = time.time()

        # 步骤1: 格式化回复结构
        response = self.format_controller.format_response(reasoning_result, user_intent)

        # 步骤2: 应用教员语言DNA
        response = self.language_dna.apply(response, tone=user_intent.emotion.value)

        # 步骤3: 根据情绪调整语气
        response = self.tone_adjuster.adjust(
            response, user_intent.emotion, user_intent.emotion_intensity,
        )

        # 步骤4: 后处理
        response = self._post_process(response)

        elapsed = int((time.time() - start_time) * 1000)
        logger.info("ExpressionLayer completed in %dms", elapsed)

        return response

    def _post_process(self, text: str) -> str:
        """
        后处理：确保格式正确

        - 控制总长度（100-500字）
        - 确保段落分明
        - 去除多余空行
        - 检查标点符号
        """
        if not text:
            return text

        # 去除多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 确保段落间有空行
        text = re.sub(r'([^\n])\n([^\n])', r'\1\n\n\2', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 控制长度
        if len(text) > 500:
            # 截断到最近的自然断点
            truncated = text[:500]
            last_period = max(truncated.rfind('。'), truncated.rfind('？'), truncated.rfind('！'))
            if last_period > 400:
                text = text[:last_period + 1]
            else:
                text = truncated + "..."

        if len(text) < 50:
            text += "你觉得呢？"

        # 确保结尾有标点
        text = text.rstrip()
        if text and text[-1] not in '。！？.!?':
            text += '。'

        return text
