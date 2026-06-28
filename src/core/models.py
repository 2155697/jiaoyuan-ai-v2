"""
教员AI顾问 - 数据模型定义

使用Pydantic v2定义五层认知架构中的所有数据模型，
确保类型安全、序列化支持和数据验证。

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 枚举定义
# ============================================================================

class EmotionType(str, Enum):
    """情绪类型枚举 —— 基于教员语境的情绪分类"""
    CONFUSED = "confused"           # 迷茫
    ANXIOUS = "anxious"             # 焦虑
    FRUSTRATED = "frustrated"       # 挫败
    DETERMINED = "determined"       # 坚定
    HOPEFUL = "hopeful"             # 期待
    HESITANT = "hesitant"           # 犹豫
    OVERWHELMED = "overwhelmed"     # 压力山大


class CognitiveStage(str, Enum):
    """认知阶段枚举 —— 用户在问题解决循环中的位置"""
    PROBLEM_STATEMENT = "problem_statement"         # 问题陈述
    INFORMATION_SEEKING = "information_seeking"     # 信息寻求
    OPTION_EXPLORATION = "option_exploration"       # 选项探索
    DECISION_STRUGGLE = "decision_struggle"         # 决策挣扎
    ACTION_CONFIRMATION = "action_confirmation"     # 行动确认
    REFLECTION = "reflection"                       # 反思总结


class ProblemType(str, Enum):
    """问题类型枚举 —— 教员思维的问题分类法"""
    CONTRADICTION_ANALYSIS = "contradiction_analysis"       # 矛盾分析
    INVESTIGATION_RESEARCH = "investigation_research"       # 调查研究
    PHASE_ASSESSMENT = "phase_assessment"                   # 阶段判断
    STRATEGY_SELECTION = "strategy_selection"               # 策略选择
    CONFIDENCE_BUILDING = "confidence_building"             # 信心建设
    METHODOLOGY_LEARNING = "methodology_learning"           # 方法论学习


class FrameworkType(str, Enum):
    """思维框架枚举 —— 教员的核心思维框架"""
    FIVE_LAYER_ANALYSIS = "five_layer_analysis"         # 五层分析框架
    CONTRADICTION_THEORY = "contradiction_theory"       # 矛盾论
    PROTRACTED_WAR = "protracted_war"                   # 持久战理论
    INVESTIGATION_METHOD = "investigation_method"       # 调查研究方法
    MASS_LINE = "mass_line"                             # 群众路线
    INDEPENDENT_THINKING = "independent_thinking"       # 独立思考


class QuestionType(str, Enum):
    """苏格拉底提问类型枚举"""
    CLARIFY = "clarify"                             # 澄清概念
    CHALLENGE_ASSUMPTION = "challenge_assumption"   # 挑战假设
    EXPLORE_CONSEQUENCE = "explore_consequence"     # 探索后果
    FIND_EVIDENCE = "find_evidence"                 # 寻找证据
    REFRAME_PERSPECTIVE = "reframe_perspective"     # 转换视角


class PhaseType(str, Enum):
    """持久战阶段枚举"""
    STRATEGIC_DEFENSE = "strategic_defense"                     # 战略防御
    STRATEGIC_STALEMATE = "strategic_stalemate"                 # 战略相持
    STRATEGIC_COUNTEROFFENSIVE = "strategic_counteroffensive"   # 战略反攻


class NodeType(str, Enum):
    """认知图谱节点类型枚举"""
    METHOD = "Method"           # 方法论
    CONCEPT = "Concept"         # 概念
    CASE = "Case"               # 案例
    FRAMEWORK = "Framework"     # 框架
    QUOTE = "Quote"             # 引用


class RelationType(str, Enum):
    """认知图谱关系类型枚举"""
    APPLIES_TO = "applies_to"           # 适用于
    CONTAINS = "contains"               # 包含
    RELATES_TO = "relates_to"           # 关联
    DEMONSTRATES = "demonstrates"       # 演示
    PREREQUISITE = "prerequisite"       # 前置条件
    LEADS_TO = "leads_to"               # 导致
    QUOTES = "quotes"                   # 引用
    PRECEDES = "precedes"               # 先于
    OPPOSES = "opposes"                 # 对立
    TRANSFORMS_TO = "transforms_to"     # 转化为


class DecisionStyle(str, Enum):
    """决策风格枚举"""
    ANALYTICAL = "analytical"   # 分析型
    INTUITIVE = "intuitive"     # 直觉型
    DEPENDENT = "dependent"     # 依赖型
    AVOIDANT = "avoidant"       # 回避型
    UNKNOWN = "unknown"         # 未知


# ============================================================================
# 感知层数据模型
# ============================================================================

class SemanticParseResult(BaseModel):
    """语义解析结果"""
    topic: str = Field(description="核心主题（10字以内）")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    entities: List[str] = Field(default_factory=list, description="命名实体列表")
    domain: str = Field(default="general", description="所属领域")


class EmotionDetectionResult(BaseModel):
    """情感探测结果"""
    emotion: EmotionType = Field(description="主导情绪类型")
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="情绪强度")
    emotional_subtext: str = Field(default="", description="情绪潜台词")
    underlying_concern: str = Field(default="", description="潜在担忧")


class IntentClassificationResult(BaseModel):
    """意图分类结果"""
    cognitive_stage: CognitiveStage = Field(description="当前认知阶段")
    surface_request: str = Field(description="表面请求")
    deep_need: str = Field(description="深层需求")
    implicit_needs: List[str] = Field(default_factory=list, description="隐含需求列表")
    cognitive_cycle_position: Dict[str, bool] = Field(
        default_factory=lambda: {
            "goal": False, "plan": False, "steps": False,
            "needs": False, "factors": False, "assessment": False
        },
        description="认知循环位置"
    )


class UserIntent(BaseModel):
    """
    感知层输出的结构化用户意图

    整合了语义解析、情感探测和意图分类的三重分析结果，
    作为后续各层的统一输入。
    """
    # 语义解析
    topic: str = Field(description="核心主题")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    entities: List[str] = Field(default_factory=list, description="命名实体")
    domain: str = Field(default="general", description="所属领域")

    # 情感探测
    emotion: EmotionType = Field(description="主导情绪")
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="情绪强度")
    emotional_subtext: str = Field(default="", description="情绪潜台词")
    underlying_concern: str = Field(default="", description="潜在担忧")

    # 意图分类
    cognitive_stage: CognitiveStage = Field(description="认知阶段")
    implicit_needs: List[str] = Field(default_factory=list, description="隐含需求")
    surface_request: str = Field(description="表面请求")
    deep_need: str = Field(description="深层需求")
    cognitive_cycle_position: Dict[str, bool] = Field(
        default_factory=dict, description="认知循环位置"
    )

    # 原始输入
    raw_input: str = Field(description="原始用户输入")
    input_length: int = Field(default=0, description="输入长度")

    @field_validator("emotion_intensity")
    @classmethod
    def clamp_intensity(cls, v: float) -> float:
        """确保情绪强度在0-1范围内"""
        return max(0.0, min(1.0, v))


# ============================================================================
# 理解层数据模型
# ============================================================================

class CognitiveNode(BaseModel):
    """认知图谱节点"""
    id: str = Field(description="节点唯一ID")
    type: NodeType = Field(description="节点类型")
    name: str = Field(description="节点名称")
    description: str = Field(default="", description="节点描述")
    source: str = Field(default="", description="来源著作/讲话")
    original_text: str = Field(default="", description="原文摘录")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    relevance_score: float = Field(default=0.0, description="相关度分数")


class MethodNode(CognitiveNode):
    """方法论节点"""
    application: str = Field(default="", description="应用场景")
    conditions: str = Field(default="", description="使用条件")
    steps: List[str] = Field(default_factory=list, description="操作步骤")
    examples: List[str] = Field(default_factory=list, description="经典案例")


class ConceptNode(CognitiveNode):
    """概念节点"""
    definition: str = Field(default="", description="概念定义")
    related_methods: List[str] = Field(default_factory=list, description="相关方法")


class CaseNode(CognitiveNode):
    """案例节点"""
    method_used: str = Field(default="", description="使用的方法")
    lesson: str = Field(default="", description="经验教训")
    historical_context: str = Field(default="", description="历史背景")


class FrameworkNode(CognitiveNode):
    """框架节点"""
    layers: List[str] = Field(default_factory=list, description="框架层次")
    layer_descriptions: Dict[str, str] = Field(default_factory=dict, description="层次描述")


class QuoteNode(CognitiveNode):
    """引用节点"""
    text: str = Field(default="", description="引用文本")
    context: str = Field(default="", description="上下文")
    applicable_situations: List[str] = Field(default_factory=list, description="适用情境")


class MaoxuanRef(BaseModel):
    """毛选引用"""
    source: str = Field(description="出处（篇名）")
    text: str = Field(description="引用文本")
    relevance_score: float = Field(default=0.0, description="相关度分数")
    chapter: str = Field(default="", description="章节")
    year: str = Field(default="", description="年份")


class ProblemProfile(BaseModel):
    """
    理解层输出的问题画像

    将用户问题映射到教员的思维框架，包含问题类型、
    适用框架和相关知识图谱节点。
    """
    problem_type: ProblemType = Field(description="问题类型")
    framework: FrameworkType = Field(description="主要思维框架")
    framework_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="框架匹配置信度")

    # 认知图谱检索结果
    related_methods: List[MethodNode] = Field(default_factory=list, description="相关方法论")
    related_concepts: List[ConceptNode] = Field(default_factory=list, description="相关概念")
    related_cases: List[CaseNode] = Field(default_factory=list, description="相关案例")
    related_quotes: List[QuoteNode] = Field(default_factory=list, description="相关引用")

    # 毛选引用
    maoxuan_refs: List[MaoxuanRef] = Field(default_factory=list, description="毛选引用")

    # 匹配分数
    relevance_scores: Dict[str, float] = Field(default_factory=dict, description="相关度分数")

    # 分析摘要
    problem_summary: str = Field(default="", description="问题摘要")


# ============================================================================
# 推理层数据模型
# ============================================================================

class SocraticQuestion(BaseModel):
    """
    苏格拉底式提问

    每个问题都有明确的类型、目的和期望洞察，
    用于引导用户自己找到答案。
    """
    question: str = Field(description="问题文本")
    type: QuestionType = Field(description="提问类型")
    purpose: str = Field(description="提问目的说明")
    target_insight: str = Field(description="期望用户得到的洞察")
    priority: int = Field(default=3, ge=1, le=5, description="优先级（1最高）")

    @field_validator("priority")
    @classmethod
    def clamp_priority(cls, v: int) -> int:
        """确保优先级在1-5范围内"""
        return max(1, min(5, v))


class ContradictionAnalysis(BaseModel):
    """
    矛盾分析结果

    基于教员《矛盾论》的核心方法论：
    抓主要矛盾，分析矛盾双方，寻找转化条件。
    """
    primary_contradiction: str = Field(description="主要矛盾描述")
    secondary_contradictions: List[str] = Field(default_factory=list, description="次要矛盾列表")
    aspects: Dict[str, str] = Field(default_factory=dict, description="矛盾双方（A面/B面）")
    dominant_aspect: str = Field(default="", description="目前主导的方面")
    transformation_conditions: List[str] = Field(default_factory=list, description="转化条件")
    resolution_direction: str = Field(description="解决方向")


class PhaseAssessment(BaseModel):
    """
    阶段评估结果

    基于持久战三阶段理论：
    战略防御 → 战略相持 → 战略反攻
    """
    current_phase: PhaseType = Field(description="当前阶段")
    phase_characteristics: List[str] = Field(default_factory=list, description="阶段特征")
    key_tasks: List[str] = Field(default_factory=list, description="关键任务")
    transition_signals: List[str] = Field(default_factory=list, description="进入下一阶段的信号")
    assessment: str = Field(default="", description="总体评估（教员风格的一句话）")


class FiveLayerAnalysis(BaseModel):
    """
    五层分析框架结果

    教员思维的核心方法论：
    目标 → 方案 → 环节 → 需求 → 因素 → 评估
    """
    goal: str = Field(description="目标层：用户的目标是什么")
    plan: str = Field(description="方案层：打算怎么实现")
    steps: List[str] = Field(default_factory=list, description="环节层：具体步骤")
    needs: List[str] = Field(default_factory=list, description="需求层：每一步的条件")
    factors: List[str] = Field(default_factory=list, description="因素层：影响成败的关键")
    assessment: str = Field(description="评估层：有多大把握")
    difficulty_rating: Dict[str, int] = Field(
        default_factory=dict, description="各环节难度评估（1-10）"
    )
    missing_layers: List[str] = Field(
        default_factory=list, description="用户尚未明确的层次"
    )


class ReasoningResult(BaseModel):
    """
    推理层输出的完整推理结果

    整合了四大引擎的输出：思维链、苏格拉底提问、
    矛盾分析和阶段评估。
    """
    # 思维链推理
    reasoning_chain: str = Field(default="", description="推理链条（内部使用）")
    key_insights: List[str] = Field(default_factory=list, description="关键洞察")

    # 苏格拉底提问
    socratic_questions: List[SocraticQuestion] = Field(
        default_factory=list, description="苏格拉底提问序列"
    )

    # 专项分析
    contradiction_analysis: Optional[ContradictionAnalysis] = Field(
        default=None, description="矛盾分析结果"
    )
    phase_assessment: Optional[PhaseAssessment] = Field(
        default=None, description="阶段评估结果"
    )
    five_layer_analysis: Optional[FiveLayerAnalysis] = Field(
        default=None, description="五层分析结果"
    )

    # 元数据
    reasoning_time_ms: int = Field(default=0, description="推理耗时(ms)")
    thinking_content: str = Field(default="", description="Qwen3 Thinking原始输出")
    model_used: str = Field(default="qwen3:8b", description="使用的模型")


# ============================================================================
# 记忆层数据模型
# ============================================================================

class DialogueTurn(BaseModel):
    """单轮对话记录"""
    user_input: str = Field(description="用户输入")
    assistant_response: str = Field(description="助手回复")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp(), description="时间戳")
    reasoning_result: Optional[ReasoningResult] = Field(default=None, description="推理结果")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class UserProfile(BaseModel):
    """
    用户画像 —— 跨对话持久化的用户认知档案

    记录用户的决策风格、认知偏好和思维特征，
    用于个性化回复。
    """
    user_id: str = Field(description="用户ID")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())

    # 决策风格
    decision_style: DecisionStyle = Field(default=DecisionStyle.UNKNOWN)

    # 常见困惑领域
    common_confusion_areas: List[str] = Field(default_factory=list)

    # 思维模式特征
    thinking_patterns: Dict[str, Any] = Field(default_factory=dict, description="""
    思维模式特征:
    - tendency_to_generalize: 是否容易过度概括
    - catastrophizing: 是否容易灾难化思维
    - black_white_thinking: 是否非黑即白
    - overthinking: 是否过度思考
    """)

    # 认知偏好
    cognitive_preferences: Dict[str, str] = Field(default_factory=dict, description="""
    认知偏好:
    - learning_style: 学习风格
    - communication_style: 沟通风格
    - problem_approach: 问题处理方式
    """)

    # 对话统计
    total_dialogues: int = Field(default=0)
    total_turns: int = Field(default=0)
    avg_session_length: float = Field(default=0.0)

    # 关键洞察
    key_insights: List[str] = Field(default_factory=list)

    # 用户反馈
    feedback_history: List[Dict[str, Any]] = Field(default_factory=list)

    # 用户基本信息（可选）
    nickname: str = Field(default="", description="用户昵称")
    notes: str = Field(default="", description="备注")


class CognitiveState(BaseModel):
    """
    认知状态 —— 用户在问题解决循环中的实时位置

    追踪用户在 目标→方案→环节→需求→因素→评估 循环中的进度。
    """
    current_stage: str = Field(default="goal", description="当前所处阶段")
    stage_progress: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "goal": {"completed": False, "notes": ""},
            "plan": {"completed": False, "notes": ""},
            "steps": {"completed": False, "notes": ""},
            "needs": {"completed": False, "notes": ""},
            "factors": {"completed": False, "notes": ""},
            "assessment": {"completed": False, "notes": ""},
        }
    )
    loop_count: int = Field(default=0, description="已完成的大循环次数")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="阶段转换历史")


class MemoryContext(BaseModel):
    """记忆层输出的增强上下文"""
    dialogue_context: str = Field(description="对话历史上下文")
    user_profile: UserProfile = Field(description="用户画像")
    cognitive_state: CognitiveState = Field(description="认知状态")
    history: List[Dict[str, str]] = Field(default_factory=list, description="最近对话记录")


# ============================================================================
# 表达层数据模型
# ============================================================================

class ResponseFormat(BaseModel):
    """回复格式规范"""
    resonance: str = Field(description="情境共鸣开头")
    questions: List[str] = Field(description="引导性问题")
    analysis: str = Field(description="简要分析")
    ending: str = Field(description="鼓励结尾")
    total_length: int = Field(description="总长度")


# ============================================================================
# 引擎输出数据模型
# ============================================================================

class EngineOutput(BaseModel):
    """
    主引擎输出 —— 一次完整对话的处理结果

    包含最终回复和完整的中间结果，用于调试和分析。
    """
    # 最终回复
    response: str = Field(description="最终自然语言回复")

    # 各层输出（用于调试和分析）
    user_intent: Optional[UserIntent] = Field(default=None, description="感知层输出")
    problem_profile: Optional[ProblemProfile] = Field(default=None, description="理解层输出")
    reasoning_result: Optional[ReasoningResult] = Field(default=None, description="推理层输出")

    # 元数据
    session_id: str = Field(description="会话ID")
    user_id: str = Field(description="用户ID")
    processing_time_ms: int = Field(default=0, description="总处理时间(ms)")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

    # 性能指标
    layer_timings: Dict[str, int] = Field(
        default_factory=dict, description="各层耗时(ms)"
    )


class StreamChunk(BaseModel):
    """流式输出块"""
    chunk_type: str = Field(description="块类型: thinking/content/done/error")
    content: str = Field(description="内容")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


# ============================================================================
# 配置数据模型
# ============================================================================

class EngineConfig(BaseModel):
    """引擎配置"""
    # LLM配置
    ollama_host: str = Field(default="http://localhost:11434")
    model_name: str = Field(default="qwen3:8b")
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    default_top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    default_top_k: int = Field(default=20, ge=1, le=100)
    max_context_tokens: int = Field(default=8192)

    # 超时配置
    llm_timeout_seconds: int = Field(default=30)
    max_total_response_time: int = Field(default=10)

    # 认知图谱配置
    cognitive_graph_dir: str = Field(default="data/cognitive_graph")

    # 毛选检索配置
    maoxuan_db_dir: str = Field(default="data/maoxuan/chroma_db")
    maoxuan_top_k: int = Field(default=3)

    # 记忆层配置
    profiles_dir: str = Field(default="data/profiles")
    max_full_turns: int = Field(default=10)

    # 表达层配置
    response_min_length: int = Field(default=100)
    response_max_length: int = Field(default=500)
    target_sentence_length: int = Field(default=20)

    # 性能配置
    enable_streaming: bool = Field(default=True)
    enable_thinking_mode: bool = Field(default=True)
    max_socratic_questions: int = Field(default=5)


# ============================================================================
# 认知图谱数据模型
# ============================================================================

class GraphEntity(BaseModel):
    """图谱实体（存储用）"""
    id: str = Field(description="实体ID")
    type: str = Field(description="实体类型")
    name: str = Field(description="实体名称")
    properties: Dict[str, Any] = Field(default_factory=dict, description="属性")
    keywords: List[str] = Field(default_factory=list, description="关键词")


class GraphRelation(BaseModel):
    """图谱关系（存储用）"""
    id: str = Field(description="关系ID")
    type: str = Field(description="关系类型")
    source: str = Field(description="源实体ID")
    target: str = Field(description="目标实体ID")
    properties: Dict[str, Any] = Field(default_factory=dict, description="属性")


class GraphData(BaseModel):
    """完整图谱数据（用于序列化）"""
    entities: List[GraphEntity] = Field(default_factory=list)
    relations: List[GraphRelation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="1.0.0")
