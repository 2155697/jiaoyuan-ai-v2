"""
教员AI顾问 - 认知图谱

基于NetworkX的轻量级认知图谱，存储教员的思维方法论。
区别于事实型知识图谱，认知图谱存储的是"教员如何思考问题"的方法论。

特性：
- 纯内存操作（NetworkX DiGraph），无需图数据库
- 节点类型：Method, Concept, Case, Framework, Quote
- 关系类型：applies_to, contains, relates_to, demonstrates, prerequisite, leads_to
- 内置教员核心思维方法数据
- 关键词+语义混合检索

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from models import (
    CaseNode, ConceptNode, FrameworkNode, GraphData, GraphEntity,
    GraphRelation, MethodNode, NodeType, QuoteNode, RelationType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 内置认知图谱数据 —— 教员核心思维方法论
# ============================================================================

DEFAULT_ENTITIES: List[Dict[str, Any]] = [
    # ========== 方法论节点 (Method) ==========
    {
        "id": "method_contradiction_analysis",
        "type": "Method",
        "name": "矛盾分析法",
        "description": "区分主要矛盾和次要矛盾，抓住主要矛盾，分析矛盾双方及转化条件",
        "source": "《矛盾论》1937",
        "original_text": "研究任何过程，如果是存在着两个以上矛盾的复杂过程的话，就要用全力找出它的主要矛盾。捉住了这个主要矛盾，一切问题就迎刃而解了。",
        "application": "面对复杂问题、多重选择、两难困境时",
        "conditions": "问题涉及多个冲突因素，需要理清主次",
        "steps": [
            "1. 列出问题中的所有矛盾",
            "2. 判断主要矛盾和次要矛盾",
            "3. 抓住主要矛盾",
            "4. 分析矛盾的主要方面和次要方面",
            "5. 寻找矛盾转化的条件",
        ],
        "keywords": ["矛盾", "主要矛盾", "次要矛盾", "对立统一", "转化条件"],
    },
    {
        "id": "method_investigation",
        "type": "Method",
        "name": "调查研究法",
        "description": "没有调查就没有发言权，一切结论产生于调查情况的末尾，而不是在它的先头",
        "source": "《反对本本主义》1930",
        "original_text": "没有调查，没有发言权。",
        "application": "不了解情况、信息不足、需要决策前",
        "conditions": "对问题不了解或了解不充分时",
        "steps": [
            "1. 确定调查目的和范围",
            "2. 深入实际收集第一手资料",
            "3. 分析收集到的数据和情况",
            "4. 从事实中得出结论",
            "5. 根据结论制定行动方案",
        ],
        "keywords": ["调查", "研究", "实际", "情况", "数据", "了解"],
    },
    {
        "id": "method_class_analysis",
        "type": "Method",
        "name": "阶级分析法",
        "description": "分析社会各阶级的经济地位和政治态度，确定敌友关系",
        "source": "《中国社会各阶级的分析》1925",
        "original_text": "谁是我们的敌人？谁是我们的朋友？这个问题是革命的首要问题。",
        "application": "分析利益相关方、确定联盟和对立面",
        "conditions": "涉及多方利益和复杂人际关系",
        "steps": [
            "1. 识别所有利益相关方",
            "2. 分析各方的立场和利益诉求",
            "3. 确定哪些是支持力量",
            "4. 确定哪些是反对力量",
            "5. 确定哪些是可以争取的中间力量",
        ],
        "keywords": ["阶级", "利益", "立场", "分析", "敌友", "力量"],
    },
    {
        "id": "method_primary_contradiction",
        "type": "Method",
        "name": "抓主要矛盾法",
        "description": "在复杂问题中抓住最关键的矛盾，集中精力解决",
        "source": "《矛盾论》",
        "original_text": "不能把过程中所有的矛盾平均看待，必须把它们区别为主要的和次要的两类。",
        "application": "资源有限、需要优先级排序时",
        "conditions": "多个问题同时存在，需要确定优先解决哪个",
        "steps": [
            "1. 列出所有待解决的问题",
            "2. 评估每个问题对整体目标的影响程度",
            "3. 找出影响最大的那个问题（主要矛盾）",
            "4. 集中资源解决主要矛盾",
            "5. 主要矛盾解决后，次要矛盾会迎刃而解",
        ],
        "keywords": ["主要矛盾", "优先", "集中", "关键", "重点"],
    },
    {
        "id": "method_both_sides_analysis",
        "type": "Method",
        "name": "两面分析法",
        "description": "分析事物的正面和反面，有利因素和不利因素，防止片面性",
        "source": "《论持久战》",
        "original_text": "事物都是一分为二的。",
        "application": "需要全面看待问题，防止片面乐观或悲观",
        "conditions": "对事物只有单面认识时，需要全面分析",
        "steps": [
            "1. 列出事物的有利因素",
            "2. 列出事物的不利因素",
            "3. 分析有利和不利因素的对比关系",
            "4. 判断哪方面占主导",
            "5. 思考如何发挥有利因素、克服不利因素",
        ],
        "keywords": ["两面", "正反", "利弊", "全面", "一分为二"],
    },
    {
        "id": "method_five_layer",
        "type": "Method",
        "name": "五层分析法",
        "description": "从目标、方案、环节、需求、因素、评估六个层次逐层分析问题",
        "source": "教员工作方法总结",
        "original_text": "做任何工作，都要先定目标，再想办法，再分步骤，再看条件，再评难度。",
        "application": "制定计划、分解复杂任务、系统分析问题",
        "conditions": "需要系统性分析一个问题或制定计划时",
        "steps": [
            "1. 目标层：明确最终目标是什么",
            "2. 方案层：有哪些可行方案",
            "3. 环节层：方案包含哪些具体步骤",
            "4. 需求层：每个步骤需要什么条件",
            "5. 因素层：影响成败的关键因素是什么",
            "6. 评估层：整体把握有多大",
        ],
        "keywords": ["目标", "方案", "环节", "需求", "因素", "评估"],
    },
    {
        "id": "method_strategic_retreat",
        "type": "Method",
        "name": "战略退却",
        "description": "在力量不足时主动退却，保存实力，等待时机",
        "source": "《中国革命战争的战略问题》1936",
        "original_text": "战略退却，是劣势军队处在优势军队进攻面前，因为顾到不能迅速地击破其进攻，为了保存军力，待机破敌，而采取的一个有计划的战略步骤。",
        "application": "处于劣势、力量不足时",
        "conditions": "面对强大对手或困难，正面硬拼不利",
        "steps": [
            "1. 客观评估敌我力量对比",
            "2. 承认暂时的劣势",
            "3. 主动退却，保存核心实力",
            "4. 在退却中积蓄力量",
            "5. 等待时机反攻",
        ],
        "keywords": ["退却", "保存实力", "等待时机", "战略", "劣势"],
    },
    {
        "id": "method_united_front",
        "type": "Method",
        "name": "统一战线",
        "description": "团结一切可以团结的力量，建立最广泛的同盟",
        "source": "《论反对日本帝国主义的策略》1935",
        "original_text": "组织千千万万的民众，调动浩浩荡荡的革命军。",
        "application": "需要争取支持、建立合作时",
        "conditions": "面对强大挑战，自身力量不足",
        "steps": [
            "1. 识别所有可能的同盟者",
            "2. 找出共同的利益和目标",
            "3. 主动联络和团结",
            "4. 求同存异，包容不同",
            "5. 建立合作机制和信任",
        ],
        "keywords": ["团结", "联合", "同盟", "合作", "统一战线"],
    },
    {
        "id": "method_seek_truth",
        "type": "Method",
        "name": "实事求是",
        "description": "从实际出发，理论联系实际，在实践中检验和发展真理",
        "source": "《改造我们的学习》1941",
        "original_text": "'实事'就是客观存在着的一切事物，'是'就是客观事物的内部联系，即规律性，'求'就是我们去研究。",
        "application": "一切需要从实际出发的情况",
        "conditions": "容易陷入空想、理论脱离实际时",
        "steps": [
            "1. 客观认识当前实际情况",
            "2. 从事实中找出规律",
            "3. 根据规律制定行动方案",
            "4. 在实践中检验方案",
            "5. 根据实践结果修正认识",
        ],
        "keywords": ["实际", "求是", "规律", "客观", "实践"],
    },
    {
        "id": "method_mass_line",
        "type": "Method",
        "name": "群众路线",
        "description": "从群众中来，到群众中去，集中起来，坚持下去",
        "source": "《关于领导方法的若干问题》1943",
        "original_text": "在我党的一切实际工作中，凡属正确的领导，必须是从群众中来，到群众中去。",
        "application": "需要凝聚团队、发动群众力量时",
        "conditions": "需要动员多方力量完成目标",
        "steps": [
            "1. 深入群众，了解真实情况",
            "2. 集中群众智慧和意见",
            "3. 形成方案和决策",
            "4. 回到群众中宣传和执行",
            "5. 在执行中继续听取反馈",
        ],
        "keywords": ["群众", "路线", "集中", "民主", "领导"],
    },
    # ========== 概念节点 (Concept) ==========
    {
        "id": "concept_primary_contradiction",
        "type": "Concept",
        "name": "主要矛盾",
        "description": "在复杂事物的发展过程中处于支配地位、对事物发展起决定作用的矛盾",
        "source": "《矛盾论》",
        "definition": "主要矛盾是指在复杂事物的发展过程中，处于支配地位，对事物发展起决定作用的矛盾。主要矛盾的存在和发展，规定或影响着其他矛盾的存在和发展。",
        "related_methods": ["method_contradiction_analysis", "method_primary_contradiction"],
        "keywords": ["主要矛盾", "支配", "决定作用"],
    },
    {
        "id": "concept_secondary_contradiction",
        "type": "Concept",
        "name": "次要矛盾",
        "description": "处于从属地位、受主要矛盾支配和影响的矛盾",
        "source": "《矛盾论》",
        "definition": "次要矛盾处于从属地位，对事物发展不起决定作用，但其解决会影响主要矛盾的解决。",
        "related_methods": ["method_contradiction_analysis"],
        "keywords": ["次要矛盾", "从属", "影响"],
    },
    {
        "id": "concept_contradiction_aspects",
        "type": "Concept",
        "name": "矛盾的主要方面",
        "description": "在矛盾双方中起主导作用的方面，决定事物的性质",
        "source": "《矛盾论》",
        "definition": "矛盾着的两方面中，必有一方面是主要的，他方面是次要的。矛盾的主要方面决定事物的性质。",
        "related_methods": ["method_contradiction_analysis"],
        "keywords": ["矛盾方面", "主导", "性质"],
    },
    {
        "id": "concept_strategic_defense",
        "type": "Concept",
        "name": "战略防御",
        "description": "敌强我弱时的第一阶段，以保存实力、了解情况为主要任务",
        "source": "《论持久战》1938",
        "definition": "在力量对比敌强我弱的情况下，采取守势战略，主要任务是保存实力、了解情况、积蓄力量。",
        "related_methods": ["method_strategic_retreat"],
        "keywords": ["防御", "保存实力", "敌强我弱", "第一阶段"],
    },
    {
        "id": "concept_strategic_stalemate",
        "type": "Concept",
        "name": "战略相持",
        "description": "力量均衡时的第二阶段，以坚持和等待时机为主要任务",
        "source": "《论持久战》",
        "definition": "双方力量趋于均衡，进入僵持阶段，主要任务是坚持既定方针、等待有利时机。",
        "related_methods": [],
        "keywords": ["相持", "均衡", "坚持", "等待"],
    },
    {
        "id": "concept_strategic_counteroffensive",
        "type": "Concept",
        "name": "战略反攻",
        "description": "我强敌弱时的第三阶段，以主动出击、一举突破为主要任务",
        "source": "《论持久战》",
        "definition": "力量对比转为我有优势时，采取攻势战略，主要任务是主动出击、扩大战果。",
        "related_methods": [],
        "keywords": ["反攻", "进攻", "优势", "主动"],
    },
    {
        "id": "concept_seek_truth_from_facts",
        "type": "Concept",
        "name": "实事求是",
        "description": "从客观实际出发，探求事物的内部联系及其规律性",
        "source": "《改造我们的学习》",
        "definition": "实事求是的本质是从客观存在的事物出发，研究事物的内在联系和规律，作为行动的指南。",
        "related_methods": ["method_seek_truth"],
        "keywords": ["实际", "规律", "客观", "求是"],
    },
    {
        "id": "concept_mass_line",
        "type": "Concept",
        "name": "群众路线",
        "description": "一切为了群众，一切依靠群众，从群众中来，到群众中去",
        "source": "《论联合政府》1945",
        "definition": "群众路线是中国共产党的根本工作路线，核心是把群众的意见集中起来，化为系统的意见，又到群众中坚持下去。",
        "related_methods": ["method_mass_line"],
        "keywords": ["群众", "依靠", "集中", "民主"],
    },
    {
        "id": "concept_dialectical",
        "type": "Concept",
        "name": "辩证法",
        "description": "关于自然、社会和思维发展的最一般规律的学说",
        "source": "《矛盾论》",
        "definition": "辩证法的核心是用联系、发展、全面的观点看问题，承认矛盾是事物发展的根本动力。",
        "related_methods": ["method_contradiction_analysis", "method_both_sides_analysis"],
        "keywords": ["辩证", "发展", "联系", "矛盾", "全面"],
    },
    {
        "id": "concept_investigation",
        "type": "Concept",
        "name": "没有调查就没有发言权",
        "description": "一切结论产生于调查情况的末尾，而不是在它的先头",
        "source": "《反对本本主义》",
        "definition": "在任何决策之前，必须先进行深入调查研究，了解实际情况，否则没有资格发表意见和做出决策。",
        "related_methods": ["method_investigation"],
        "keywords": ["调查", "发言权", "实际", "了解"],
    },
    # ========== 框架节点 (Framework) ==========
    {
        "id": "framework_five_layer",
        "type": "Framework",
        "name": "五层分析框架",
        "description": "目标→方案→环节→需求→因素→评估的完整分析框架",
        "source": "教员工作方法总结",
        "layers": ["goal", "plan", "steps", "needs", "factors", "assessment"],
        "layer_descriptions": {
            "goal": "目标层：明确最终要达到的目标",
            "plan": "方案层：有哪些可行的实现方案",
            "steps": "环节层：方案包含哪些具体步骤",
            "needs": "需求层：每个步骤需要什么资源和条件",
            "factors": "因素层：影响成败的关键因素是什么",
            "assessment": "评估层：对整体把握程度的评估",
        },
        "keywords": ["五层", "分析框架", "目标", "方案", "评估"],
    },
    {
        "id": "framework_contradiction",
        "type": "Framework",
        "name": "矛盾分析框架",
        "description": "识别矛盾→区分主次→分析双方→寻找转化条件的完整框架",
        "source": "《矛盾论》",
        "layers": ["identify", "prioritize", "analyze", "transform"],
        "layer_descriptions": {
            "identify": "识别矛盾：找出问题中存在的所有矛盾",
            "prioritize": "区分主次：判断主要矛盾和次要矛盾",
            "analyze": "分析双方：分析矛盾的两个方面",
            "transform": "寻找转化条件：思考如何推动矛盾向有利方向转化",
        },
        "keywords": ["矛盾", "框架", "主次", "转化"],
    },
    {
        "id": "framework_protracted_war",
        "type": "Framework",
        "name": "持久战三阶段框架",
        "description": "战略防御→战略相持→战略反攻的三阶段分析框架",
        "source": "《论持久战》",
        "layers": ["defense", "stalemate", "counteroffensive"],
        "layer_descriptions": {
            "defense": "战略防御：力量不足时保存实力、了解情况",
            "stalemate": "战略相持：力量均衡时坚持方针、等待时机",
            "counteroffensive": "战略反攻：力量充足时主动出击、扩大战果",
        },
        "keywords": ["持久战", "三阶段", "防御", "相持", "反攻"],
    },
    {
        "id": "framework_three_big_tools",
        "type": "Framework",
        "name": "三大法宝",
        "description": "统一战线、武装斗争、党的建设——中国革命的三大法宝",
        "source": "《〈共产党人〉发刊词》1939",
        "layers": ["united_front", "armed_struggle", "party_building"],
        "layer_descriptions": {
            "united_front": "统一战线：团结一切可以团结的力量",
            "armed_struggle": "武装斗争：以斗争求团结",
            "party_building": "党的建设：保持先进性和战斗力",
        },
        "keywords": ["三大法宝", "统一战线", "斗争", "建设"],
    },
    # ========== 案例节点 (Case) ==========
    {
        "id": "case_long_march",
        "type": "Case",
        "name": "长征中的战略转移",
        "description": "第五次反围剿失败后，红军进行战略转移，保存革命火种",
        "source": "《中国革命战争的战略问题》",
        "method_used": "method_strategic_retreat",
        "lesson": "力量不足时要果断转移，保存实力比硬拼更重要。战略退却不是失败，是为了更好的进攻。",
        "historical_context": "1934年，第五次反围剿失败，红军被迫进行战略转移，历时两年，行程二万五千里。",
        "keywords": ["长征", "战略转移", "保存实力", "退却"],
    },
    {
        "id": "case_protracted_war",
        "type": "Case",
        "name": "抗日战争持久战",
        "description": "面对强大的日本侵略者，教员提出持久战理论，将战争分为三个阶段",
        "source": "《论持久战》",
        "method_used": "method_contradiction_analysis",
        "lesson": "面对强大的敌人，不要急于求胜，要做好长期斗争的准备。事物发展有阶段，要判断所处阶段采取不同策略。",
        "historical_context": "1938年，抗日战争全面爆发，面对亡国论和速胜论两种极端观点，教员提出持久战理论。",
        "keywords": ["抗日", "持久战", "三阶段", "战略"],
    },
    {
        "id": "case_hunan_report",
        "type": "Case",
        "name": "湖南农民运动考察报告",
        "description": "教员深入湖南五县实地考察32天，掌握第一手资料后写出著名报告",
        "source": "《湖南农民运动考察报告》1927",
        "method_used": "method_investigation",
        "lesson": "做决策之前必须深入实际调查研究，掌握第一手资料。没有调查就没有发言权。",
        "historical_context": "1927年，农民运动受到各方质疑，教员亲自到湖南五县考察32天，写下这篇著名报告。",
        "keywords": ["湖南", "农民运动", "调查", "考察"],
    },
    {
        "id": "case_jinggangshan",
        "type": "Case",
        "name": "井冈山根据地",
        "description": "在敌强我弱的情况下，选择敌人力量薄弱的农村建立根据地",
        "source": "《中国的红色政权为什么能够存在？》1928",
        "method_used": "method_strategic_retreat",
        "lesson": "敌强我弱时不要和敌人在其优势领域硬拼，要找到敌人的薄弱环节，在那里建立自己的优势。",
        "historical_context": "1927年大革命失败后，教员率领秋收起义余部上井冈山，开创农村包围城市的道路。",
        "keywords": ["井冈山", "根据地", "农村", "包围城市"],
    },
    {
        "id": "case_xian_incident",
        "type": "Case",
        "name": "西安事变和平解决",
        "description": "抓住主要矛盾转变的时机，促成抗日民族统一战线",
        "source": "《论反对日本帝国主义的策略》",
        "method_used": "method_united_front",
        "lesson": "当主要矛盾发生变化时，要及时调整策略。次要矛盾服从主要矛盾，团结一切可以团结的力量。",
        "historical_context": "1936年，西安事变爆发，中国共产党从民族大义出发，促成事变和平解决，建立抗日民族统一战线。",
        "keywords": ["西安事变", "统一战线", "主要矛盾", "团结"],
    },
    # ========== 引用节点 (Quote) ==========
    {
        "id": "quote_contradiction_primary",
        "type": "Quote",
        "name": "抓主要矛盾",
        "description": "关于抓住主要矛盾的经典论述",
        "text": "研究任何过程，如果是存在着两个以上矛盾的复杂过程的话，就要用全力找出它的主要矛盾。捉住了这个主要矛盾，一切问题就迎刃而解了。",
        "source": "《矛盾论》",
        "context": "教员论述如何分析复杂问题时提出",
        "applicable_situations": ["面临多个问题需要排序", "资源有限需要集中", "问题复杂理不清头绪"],
        "keywords": ["主要矛盾", "迎刃而解", "全力"],
    },
    {
        "id": "quote_no_investigation",
        "type": "Quote",
        "name": "没有调查就没有发言权",
        "description": "关于调查研究的经典论述",
        "text": "没有调查，没有发言权。你对于某个问题没有调查，就停止你对于某个问题的发言权。",
        "source": "《反对本本主义》",
        "context": "批评教条主义，强调调查研究的重要性",
        "applicable_situations": ["不了解情况就做决策", "凭空发表意见", "需要收集信息"],
        "keywords": ["调查", "发言权", "实际"],
    },
    {
        "id": "quote_despise_enemy",
        "type": "Quote",
        "name": "战略上藐视敌人",
        "description": "关于信心和策略的经典论述",
        "text": "战略上要藐视敌人，战术上要重视敌人。",
        "source": "《关于正确处理人民内部矛盾的问题》1957",
        "context": "论述对待敌人的态度和策略",
        "applicable_situations": ["缺乏信心", "面对强大对手", "需要保持信心同时认真对待"],
        "keywords": ["战略", "藐视", "战术", "重视", "信心"],
    },
    {
        "id": "quote_who_is_friend",
        "type": "Quote",
        "name": "谁是我们的朋友",
        "description": "关于分清敌友的经典论述",
        "text": "谁是我们的敌人？谁是我们的朋友？这个问题是革命的首要问题。",
        "source": "《中国社会各阶级的分析》",
        "context": "开篇提出，强调分清敌友是首要问题",
        "applicable_situations": ["需要分析利益相关方", "确定支持者和反对者", "人际关系复杂"],
        "keywords": ["敌人", "朋友", "首要问题", "分析"],
    },
    {
        "id": "quote_star_fire",
        "type": "Quote",
        "name": "星星之火可以燎原",
        "description": "关于坚持和信心的经典论述",
        "text": "它是站在海岸遥望海中已经看得见桅杆尖头了的一只航船，它是立于高山之巅远看东方已见光芒四射喷薄欲出的一轮朝日，它是躁动于母腹中的快要成熟了的一个婴儿。",
        "source": "《星星之火，可以燎原》1930",
        "context": "回答林彪等人的悲观思想，阐明革命高潮快要到来",
        "applicable_situations": ["需要鼓励坚持", "感到前途渺茫", "需要信心"],
        "keywords": ["星星之火", "燎原", "希望", "坚持"],
    },
    {
        "id": "quote_serve_people",
        "type": "Quote",
        "name": "为人民服务",
        "description": "关于宗旨的经典论述",
        "text": "我们的共产党和共产党所领导的八路军、新四军，是革命的队伍。我们这个队伍完全是为着解放人民的，是彻底地为人民的利益工作的。",
        "source": "《为人民服务》1944",
        "context": "纪念张思德同志的讲话",
        "applicable_situations": ["讨论宗旨和价值观", "团队建设", "服务精神"],
        "keywords": ["为人民服务", "宗旨", "利益"],
    },
    {
        "id": "quote_practice",
        "type": "Quote",
        "name": "实践论核心观点",
        "description": "关于认识和实践关系的经典论述",
        "text": "实践、认识、再实践、再认识，这种形式，循环往复以至无穷，而实践和认识之每一循环的内容，都比较地进到了高一级的程度。",
        "source": "《实践论》1937",
        "context": "论述认识和实践的辩证关系",
        "applicable_situations": ["理论脱离实际", "需要实践检验", "学习成长"],
        "keywords": ["实践", "认识", "循环", "发展"],
    },
]

DEFAULT_RELATIONS: List[Dict[str, Any]] = [
    # 五层分析框架包含关系
    {"id": "rel_1", "type": "contains", "source": "framework_five_layer", "target": "method_five_layer"},
    {"id": "rel_2", "type": "contains", "source": "framework_five_layer", "target": "method_seek_truth"},
    # 矛盾分析框架包含关系
    {"id": "rel_3", "type": "contains", "source": "framework_contradiction", "target": "method_contradiction_analysis"},
    {"id": "rel_4", "type": "contains", "source": "framework_contradiction", "target": "method_primary_contradiction"},
    {"id": "rel_5", "type": "contains", "source": "framework_contradiction", "target": "method_both_sides_analysis"},
    # 概念关联
    {"id": "rel_6", "type": "relates_to", "source": "concept_primary_contradiction", "target": "concept_secondary_contradiction"},
    {"id": "rel_7", "type": "relates_to", "source": "concept_primary_contradiction", "target": "concept_contradiction_aspects"},
    # 方法论应用
    {"id": "rel_8", "type": "applies_to", "source": "method_contradiction_analysis", "target": "framework_contradiction"},
    {"id": "rel_9", "type": "applies_to", "source": "method_investigation", "target": "framework_five_layer"},
    {"id": "rel_10", "type": "applies_to", "source": "method_strategic_retreat", "target": "framework_protracted_war"},
    # 案例演示
    {"id": "rel_11", "type": "demonstrates", "source": "case_long_march", "target": "method_strategic_retreat"},
    {"id": "rel_12", "type": "demonstrates", "source": "case_protracted_war", "target": "method_contradiction_analysis"},
    {"id": "rel_13", "type": "demonstrates", "source": "case_hunan_report", "target": "method_investigation"},
    {"id": "rel_14", "type": "demonstrates", "source": "case_jinggangshan", "target": "method_strategic_retreat"},
    {"id": "rel_15", "type": "demonstrates", "source": "case_xian_incident", "target": "method_united_front"},
    # 引用关系
    {"id": "rel_16", "type": "quotes", "source": "method_contradiction_analysis", "target": "quote_contradiction_primary"},
    {"id": "rel_17", "type": "quotes", "source": "method_investigation", "target": "quote_no_investigation"},
    {"id": "rel_18", "type": "quotes", "source": "method_class_analysis", "target": "quote_who_is_friend"},
    # 概念-方法关联
    {"id": "rel_19", "type": "relates_to", "source": "concept_primary_contradiction", "target": "method_contradiction_analysis"},
    {"id": "rel_20", "type": "relates_to", "source": "concept_seek_truth_from_facts", "target": "method_seek_truth"},
    {"id": "rel_21", "type": "relates_to", "source": "concept_mass_line", "target": "method_mass_line"},
    # 阶段转化
    {"id": "rel_22", "type": "transforms_to", "source": "concept_strategic_defense", "target": "concept_strategic_stalemate"},
    {"id": "rel_23", "type": "transforms_to", "source": "concept_strategic_stalemate", "target": "concept_strategic_counteroffensive"},
    # 持久战框架包含
    {"id": "rel_24", "type": "contains", "source": "framework_protracted_war", "target": "concept_strategic_defense"},
    {"id": "rel_25", "type": "contains", "source": "framework_protracted_war", "target": "concept_strategic_stalemate"},
    {"id": "rel_26", "type": "contains", "source": "framework_protracted_war", "target": "concept_strategic_counteroffensive"},
    # 三大法宝框架
    {"id": "rel_27", "type": "contains", "source": "framework_three_big_tools", "target": "method_united_front"},
    {"id": "rel_28", "type": "contains", "source": "framework_three_big_tools", "target": "method_class_analysis"},
    # 前置条件
    {"id": "rel_29", "type": "prerequisite", "source": "method_investigation", "target": "method_contradiction_analysis"},
    {"id": "rel_30", "type": "prerequisite", "source": "method_contradiction_analysis", "target": "method_primary_contradiction"},
    # 辩证法概念关联
    {"id": "rel_31", "type": "relates_to", "source": "concept_dialectical", "target": "method_contradiction_analysis"},
    {"id": "rel_32", "type": "relates_to", "source": "concept_dialectical", "target": "concept_primary_contradiction"},
    # 群众路线关联
    {"id": "rel_33", "type": "relates_to", "source": "concept_mass_line", "target": "method_united_front"},
    # 实事求是关联调查研究
    {"id": "rel_34", "type": "relates_to", "source": "concept_seek_truth_from_facts", "target": "concept_investigation"},
    # 引用关联
    {"id": "rel_35", "type": "quotes", "source": "framework_protracted_war", "target": "quote_star_fire"},
    {"id": "rel_36", "type": "quotes", "source": "method_seek_truth", "target": "quote_practice"},
]


# ============================================================================
# 认知图谱类
# ============================================================================

class CognitiveGraph:
    """
    教员思维方法认知图谱

    使用NetworkX DiGraph存储，纯内存操作，无需图数据库。
    内置了教员的核心思维方法论数据。

    用法：
        # 创建并加载内置数据
        graph = CognitiveGraph()
        graph.load_builtin_data()

        # 检索方法
        methods = graph.retrieve_methods("矛盾分析", ["矛盾", "纠结"], top_k=5)

        # 检索相关节点
        related = graph.retrieve_related("method_contradiction_analysis", "demonstrates")
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化认知图谱

        Args:
            data_dir: 数据目录（用于持久化），None则不持久化
        """
        self.data_dir = data_dir
        self.graph: nx.DiGraph = nx.DiGraph()
        self.entity_index: Dict[str, Dict[str, Any]] = {}  # id -> entity data
        self.keyword_index: Dict[str, List[str]] = {}  # keyword -> entity ids
        self._loaded = False

        logger.info("CognitiveGraph initialized (data_dir=%s)", data_dir)

    def load_builtin_data(self) -> None:
        """加载内置的教员思维方法论数据"""
        if self._loaded:
            return

        logger.info("Loading %d entities and %d relations...",
                     len(DEFAULT_ENTITIES), len(DEFAULT_RELATIONS))

        # 添加实体节点
        for entity in DEFAULT_ENTITIES:
            self._add_entity(entity)

        # 添加关系边
        for relation in DEFAULT_RELATIONS:
            self._add_relation(relation)

        self._build_keyword_index()
        self._loaded = True

        logger.info(
            "CognitiveGraph loaded: %d nodes, %d edges, %d keywords indexed",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
            len(self.keyword_index),
        )

    def _add_entity(self, entity: Dict[str, Any]) -> None:
        """添加实体到图谱"""
        eid = entity["id"]
        self.graph.add_node(eid, **entity)
        self.entity_index[eid] = entity

    def _add_relation(self, relation: Dict[str, Any]) -> None:
        """添加关系到图谱"""
        rid = relation["id"]
        source = relation["source"]
        target = relation["target"]
        rel_type = relation["type"]
        props = relation.get("properties", {})

        if source in self.graph and target in self.graph:
            self.graph.add_edge(source, target, id=rid, type=rel_type, **props)
        else:
            logger.warning(
                "Skipping relation %s: source=%s or target=%s not found",
                rid, source, target,
            )

    def _build_keyword_index(self) -> None:
        """构建关键词倒排索引"""
        self.keyword_index = {}
        for eid, entity in self.entity_index.items():
            for kw in entity.get("keywords", []):
                self.keyword_index.setdefault(kw, []).append(eid)

    def retrieve_methods(
        self,
        problem_type: str,
        keywords: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        检索相关方法论

        使用关键词匹配+关系扩展的混合策略：
        1. 关键词直接匹配
        2. 问题类型映射到相关节点
        3. 沿关系扩展获取相关节点
        4. 按相关度排序

        Args:
            problem_type: 问题类型（如"contradiction_analysis"）
            keywords: 用户关键词列表
            top_k: 返回数量

        Returns:
            相关方法论节点列表
        """
        if not self._loaded:
            self.load_builtin_data()

        candidate_scores: Dict[str, float] = {}

        # 策略1：关键词匹配
        for kw in keywords:
            for indexed_kw, entity_ids in self.keyword_index.items():
                if kw in indexed_kw or indexed_kw in kw:
                    for eid in entity_ids:
                        candidate_scores[eid] = candidate_scores.get(eid, 0) + 1.0

        # 策略2：问题类型映射
        type_mapping = {
            "contradiction_analysis": [
                "method_contradiction_analysis", "method_primary_contradiction",
                "method_both_sides_analysis", "framework_contradiction",
                "concept_primary_contradiction",
            ],
            "investigation_research": [
                "method_investigation", "concept_investigation",
                "case_hunan_report",
            ],
            "phase_assessment": [
                "framework_protracted_war", "method_strategic_retreat",
                "concept_strategic_defense", "concept_strategic_stalemate",
                "concept_strategic_counteroffensive",
            ],
            "strategy_selection": [
                "framework_five_layer", "method_five_layer",
                "method_class_analysis", "method_united_front",
            ],
            "confidence_building": [
                "quote_star_fire", "quote_despise_enemy",
                "case_protracted_war",
            ],
            "methodology_learning": [
                "framework_five_layer", "framework_contradiction",
                "concept_dialectical", "concept_seek_truth_from_facts",
            ],
        }

        for mapped_id in type_mapping.get(problem_type, []):
            if mapped_id in self.entity_index:
                candidate_scores[mapped_id] = candidate_scores.get(mapped_id, 0) + 2.0

        # 策略3：沿关系扩展（1跳）
        expanded_scores = dict(candidate_scores)
        for eid, score in list(candidate_scores.items()):
            if eid in self.graph:
                for neighbor in nx.all_neighbors(self.graph, eid):
                    if neighbor in self.entity_index:
                        expanded_scores[neighbor] = expanded_scores.get(neighbor, 0) + score * 0.5

        # 过滤Method类型，按分数排序
        method_results = []
        for eid, score in sorted(expanded_scores.items(), key=lambda x: -x[1]):
            entity = self.entity_index.get(eid)
            if entity and entity.get("type") in ("Method", "Framework", "Concept", "Quote"):
                result = dict(entity)
                result["relevance_score"] = min(score, 10.0)
                method_results.append(result)
            if len(method_results) >= top_k:
                break

        return method_results

    def retrieve_related(
        self,
        node_id: str,
        relation_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索相关节点

        Args:
            node_id: 起始节点ID
            relation_type: 关系类型过滤，None表示所有类型

        Returns:
            相关节点列表
        """
        if not self._loaded:
            self.load_builtin_data()

        if node_id not in self.graph:
            return []

        results = []
        for _, target, edge_data in self.graph.out_edges(node_id, data=True):
            if relation_type is None or edge_data.get("type") == relation_type:
                entity = self.entity_index.get(target)
                if entity:
                    result = dict(entity)
                    result["relation"] = edge_data.get("type", "")
                    results.append(result)

        return results

    def retrieve_by_keywords(
        self,
        keywords: List[str],
        node_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        通过关键词检索节点

        Args:
            keywords: 关键词列表
            node_types: 节点类型过滤
            top_k: 返回数量

        Returns:
            匹配节点列表
        """
        if not self._loaded:
            self.load_builtin_data()

        scores: Dict[str, float] = {}
        for kw in keywords:
            for indexed_kw, entity_ids in self.keyword_index.items():
                if kw in indexed_kw or indexed_kw in kw:
                    for eid in entity_ids:
                        scores[eid] = scores.get(eid, 0) + 1.0

        results = []
        for eid, score in sorted(scores.items(), key=lambda x: -x[1]):
            entity = self.entity_index.get(eid)
            if entity:
                if node_types is None or entity.get("type") in node_types:
                    result = dict(entity)
                    result["relevance_score"] = min(score, 10.0)
                    results.append(result)
            if len(results) >= top_k:
                break

        return results

    def get_framework(self, framework_name: str) -> Optional[Dict[str, Any]]:
        """
        获取思维框架详情

        Args:
            framework_name: 框架名称或ID

        Returns:
            框架节点数据
        """
        if not self._loaded:
            self.load_builtin_data()

        # 尝试ID直接查找
        if framework_name in self.entity_index:
            return dict(self.entity_index[framework_name])

        # 尝试名称查找
        for eid, entity in self.entity_index.items():
            if entity.get("name") == framework_name or entity.get("type") == "Framework":
                if framework_name in eid or framework_name in entity.get("name", ""):
                    return dict(entity)

        return None

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        获取实体详情

        Args:
            entity_id: 实体ID

        Returns:
            实体数据
        """
        return self.entity_index.get(entity_id)

    def search(
        self,
        query: str,
        top_k: int = 5,
        node_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        综合搜索

        Args:
            query: 搜索查询
            top_k: 返回数量
            node_types: 节点类型过滤

        Returns:
            搜索结果列表
        """
        if not self._loaded:
            self.load_builtin_data()

        # 简单关键词提取
        keywords = [w for w in query.split() if len(w) >= 2]
        if not keywords:
            keywords = [query]

        return self.retrieve_by_keywords(keywords, node_types, top_k)

    def get_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        if not self._loaded:
            self.load_builtin_data()

        node_types = {}
        for _, data in self.graph.nodes(data=True):
            ntype = data.get("type", "unknown")
            node_types[ntype] = node_types.get(ntype, 0) + 1

        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "keyword_index_size": len(self.keyword_index),
            "loaded": self._loaded,
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出图谱为字典"""
        if not self._loaded:
            self.load_builtin_data()

        entities = []
        for _, data in self.graph.nodes(data=True):
            entities.append(dict(data))

        relations = []
        for source, target, data in self.graph.edges(data=True):
            rel = dict(data)
            rel["source"] = source
            rel["target"] = target
            relations.append(rel)

        return {
            "entities": entities,
            "relations": relations,
            "metadata": {"version": "1.0.0", "description": "教员思维方法论认知图谱"},
        }

    def save_to_file(self, filepath: str) -> None:
        """保存图谱到JSON文件"""
        data = self.to_dict()
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("CognitiveGraph saved to %s", filepath)

    def load_from_file(self, filepath: str) -> None:
        """从JSON文件加载图谱"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.graph.clear()
        self.entity_index.clear()
        self.keyword_index.clear()

        for entity in data.get("entities", []):
            self._add_entity(entity)

        for relation in data.get("relations", []):
            self._add_relation(relation)

        self._build_keyword_index()
        self._loaded = True

        logger.info("CognitiveGraph loaded from %s: %d nodes, %d edges",
                     filepath, self.graph.number_of_nodes(), self.graph.number_of_edges())
