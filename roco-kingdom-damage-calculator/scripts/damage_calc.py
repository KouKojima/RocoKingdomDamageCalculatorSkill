#!/usr/bin/env python3
"""洛克王国PvP伤害计算器

用法:
    python damage_calc.py --search-pet 火
    python damage_calc.py --search-skill 光
    python damage_calc.py --attacker 火神 --defender 水灵 --skill 火焰箭 \
        --attacker-types 火 --defender-types 水
    python damage_calc.py --attacker 火神 --defender 水灵 --skill 火焰箭 \
        --attacker-types 火 龙 --defender-types 水 \
        --personality 逞强 --atk-boost 0.7 --weather rain --critical --verbose
"""

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── 常量与映射 ──────────────────────────────────────────────────────────────

# 性格JSON属性名 -> 内部键
PERSONALITY_STAT_MAP = {
    "生命": "hp", "物攻": "atk", "物防": "def",
    "魔攻": "spa", "魔防": "spd", "速度": "spe",
}

# CSV列名 -> 内部键
CSV_STAT_MAP = {
    "精力": "hp", "攻击": "atk", "防御": "def",
    "魔攻": "spa", "魔抗": "spd", "速度": "spe",
}

INTERNAL_STAT_DISPLAY = {
    "hp": "生命", "atk": "物攻", "def": "物防",
    "spa": "魔攻", "spd": "魔防", "spe": "速度",
}

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]

# 技能CSV中"地" → 属性JSON中"土"
TYPE_ALIASES = {"地": "土"}

# 技能类型 -> (攻击属性, 防御属性)
SKILL_CATEGORY_STAT = {
    "物攻": ("atk", "def"),
    "魔攻": ("spa", "spd"),
}

PERSONALITY_FAVOR = 0.2
PERSONALITY_UNFAVOR = -0.1

# 属性公式系数
HP_RACE, HP_IV, HP_BASE, HP_FLAT = 1.7, 0.85, 70, 100
OTHER_RACE, OTHER_IV, OTHER_BASE, OTHER_FLAT = 1.1, 0.55, 10, 50

# 克制倍率
STRONG_MULT = 2.0
BOTH_STRONG_MULT = 3.0
WEAK_MULT = 0.5

STAB_MULT = 1.25
CRIT_MULT = 1.5
RAIN_WATER_MULT = 1.5

# 18种合法属性
VALID_TYPES = [
    "普通", "草", "火", "水", "光", "土", "冰", "龙",
    "电", "毒", "虫", "武", "翼", "萌", "幽", "恶", "机械", "幻",
]


# ── 数据类 ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PetRace:
    name: str
    hp: int; atk: int; def_: int; spa: int; spd: int; spe: int; total: int


@dataclass(frozen=True)
class SkillInfo:
    name: str
    type_: str       # 规范化后的属性名
    category: str    # 物攻/魔攻/状态/防御
    energy: int
    power: int
    description: str


@dataclass
class BattleMods:
    atk_boost: float = 0.0
    atk_reduction: float = 0.0
    def_boost: float = 0.0
    def_reduction: float = 0.0
    power_multiplier: float = 1.0   # 对应倍率
    power_bonus: float = 0.0        # 威力加成
    power_buff: float = 1.0         # 威力提升buff
    weather: str = "none"           # none / rain
    damage_reductions: List[float] = field(default_factory=list)
    is_critical: bool = False


@dataclass
class DamageResult:
    damage: int
    is_critical: bool
    effectiveness: float
    stab: bool
    ability_level: float
    weather_mult: float
    reduction_factor: float
    breakdown: dict


# ── 数据加载 ────────────────────────────────────────────────────────────────

def _assets_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def normalize_type(name: str) -> str:
    return TYPE_ALIASES.get(name, name)


def load_type_effectiveness(path: str = None) -> dict:
    path = path or os.path.join(_assets_dir(), "属性克制查询.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_personalities(path: str = None) -> dict:
    path = path or os.path.join(_assets_dir(), "性格查询.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    result = {}
    for name, mods in raw.items():
        result[name] = {
            "increase": PERSONALITY_STAT_MAP.get(mods["increase"]),
            "decrease": PERSONALITY_STAT_MAP.get(mods["decrease"]),
        }
    return result


def load_pets(path: str = None) -> Dict[str, PetRace]:
    path = path or os.path.join(_assets_dir(), "洛克王国全宠物种族值完整版_S1.csv")
    pets = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["宠物名称"]
            pets[name] = PetRace(
                name=name,
                hp=int(row["精力"]),
                atk=int(row["攻击"]),
                def_=int(row["防御"]),
                spa=int(row["魔攻"]),
                spd=int(row["魔抗"]),
                spe=int(row["速度"]),
                total=int(row["总和"]),
            )
    return pets


def load_skills(path: str = None) -> Dict[str, SkillInfo]:
    path = path or os.path.join(_assets_dir(), "洛克王国全技能库完整版_S1.csv")
    skills = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["技能名称"]
            skills[name] = SkillInfo(
                name=name,
                type_=normalize_type(row["属性"]),
                category=row["类型"],
                energy=int(row["能量消耗"]),
                power=int(row["威力"]),
                description=row["描述"],
            )
    return skills


def load_pet_types(path: str = None) -> Dict[str, List[str]]:
    path = path or os.path.join(_assets_dir(), "宠物属性映射.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 搜索 ────────────────────────────────────────────────────────────────────

def search_pets(pets: Dict[str, PetRace], query: str, limit: int = 20) -> List[str]:
    q = query.lower()
    return [n for n in pets if q in n.lower()][:limit]


def search_skills(skills: Dict[str, SkillInfo], query: str, limit: int = 20) -> List[str]:
    q = query.lower()
    return [n for n in skills if q in n.lower()][:limit]


# ── 属性计算 ────────────────────────────────────────────────────────────────

def compute_hp(race: int, iv: int, pers_mod: float) -> float:
    return (HP_RACE * race + HP_IV * iv + HP_BASE) * (1 + pers_mod) + HP_FLAT


def compute_stat(race: int, iv: int, pers_mod: float) -> float:
    return (OTHER_RACE * race + OTHER_IV * iv + OTHER_BASE) * (1 + pers_mod) + OTHER_FLAT


def get_personality_mods(name: str, personalities: dict) -> Dict[str, float]:
    if name not in personalities:
        return {s: 0.0 for s in STAT_ORDER}
    p = personalities[name]
    mods = {s: 0.0 for s in STAT_ORDER}
    if p["increase"]:
        mods[p["increase"]] = PERSONALITY_FAVOR
    if p["decrease"]:
        mods[p["decrease"]] = PERSONALITY_UNFAVOR
    return mods


def compute_all_stats(
    pet: PetRace, personality: str, ivs: Dict[str, int], personalities: dict
) -> Dict[str, float]:
    pmods = get_personality_mods(personality, personalities)
    stats = {}
    for key in STAT_ORDER:
        race_val = getattr(pet, key if key != "def" else "def_")
        iv_val = ivs.get(key, 0)
        pm = pmods[key]
        if key == "hp":
            stats[key] = compute_hp(race_val, iv_val, pm)
        else:
            stats[key] = compute_stat(race_val, iv_val, pm)
    return stats


# ── 属性克制 ────────────────────────────────────────────────────────────────

def get_attack_effectiveness(
    attack_type: str, defender_types: Tuple[str, ...], type_data: dict
) -> float:
    """计算技能属性对防御方属性的克制倍率。

    对防御方的每个属性:
    - 在 defender_type 的 defense.weak 中 → 2x
    - 在 defender_type 的 defense.resist 中 → 0.5x
    - 否则 → 1x
    双属性防御方: 各自倍率相乘
    """
    attack_type = normalize_type(attack_type)
    mult = 1.0
    for dt in defender_types:
        dt = normalize_type(dt)
        if dt not in type_data:
            continue
        defense = type_data[dt].get("defense", {})
        if attack_type in defense.get("weak", []):
            mult *= STRONG_MULT
        elif attack_type in defense.get("resist", []):
            mult *= WEAK_MULT
    return mult


def check_both_strong(
    attacker_types: Tuple[str, ...], skill_type: str,
    defender_types: Tuple[str, ...], type_data: dict
) -> float:
    """检查双属性都克制规则。

    如果攻击方有两个属性，且另一个属性(非技能属性)对防御方也克制，
    则从2x升级到3x。返回额外倍率: 1.5 (3/2) 如果满足，否则 1.0。
    """
    if len(attacker_types) < 2:
        return 1.0

    # 当前技能属性的克制倍率
    current_eff = get_attack_effectiveness(skill_type, defender_types, type_data)
    if current_eff != STRONG_MULT:
        return 1.0

    # 检查攻击方的另一个属性是否也克制
    for at in attacker_types:
        at = normalize_type(at)
        if at == normalize_type(skill_type):
            continue
        other_eff = get_attack_effectiveness(at, defender_types, type_data)
        if other_eff >= STRONG_MULT:
            return BOTH_STRONG_MULT / STRONG_MULT  # 1.5

    return 1.0


def is_stab(skill_type: str, attacker_types: Tuple[str, ...]) -> bool:
    skill_type = normalize_type(skill_type)
    return any(normalize_type(t) == skill_type for t in attacker_types)


def get_type_effectiveness(
    attacker_types: Tuple[str, ...], skill_type: str,
    defender_types: Tuple[str, ...], type_data: dict
) -> float:
    base = get_attack_effectiveness(skill_type, defender_types, type_data)
    both = check_both_strong(attacker_types, skill_type, defender_types, type_data)
    return base * both


# ── 伤害计算 ────────────────────────────────────────────────────────────────

def calc_ability_level(mods: BattleMods) -> float:
    num = 1 + mods.atk_boost + mods.def_reduction
    den = 1 + mods.atk_reduction + mods.def_boost
    return num / max(den, 0.01)


def calc_damage_reduction(reductions: List[float]) -> float:
    """减伤乘算。每个reduction是减伤百分比，如0.7表示减伤70%。"""
    factor = 1.0
    for r in reductions:
        factor *= (1 - r)
    return factor


def calc_weather(weather: str, skill_type: str) -> float:
    if weather == "rain" and normalize_type(skill_type) == "水":
        return RAIN_WATER_MULT
    return 1.0


def calculate_damage(
    attacker_stats: Dict[str, float],
    defender_stats: Dict[str, float],
    attacker_types: Tuple[str, ...],
    defender_types: Tuple[str, ...],
    skill: SkillInfo,
    mods: BattleMods,
    type_data: dict,
) -> DamageResult:
    if skill.category not in SKILL_CATEGORY_STAT:
        return DamageResult(
            damage=0, is_critical=False, effectiveness=1.0,
            stab=False, ability_level=1.0, weather_mult=1.0,
            reduction_factor=1.0, breakdown={"info": f"技能'{skill.name}'为{skill.category}类，不造成伤害"},
        )

    atk_key, def_key = SKILL_CATEGORY_STAT[skill.category]
    atk_val = attacker_stats[atk_key]
    def_val = max(defender_stats[def_key], 1)

    ad_ratio = atk_val / def_val * 0.9
    power_term = skill.power * mods.power_multiplier + mods.power_bonus
    ability_level = calc_ability_level(mods)
    stab = is_stab(skill.type_, attacker_types)
    stab_mult = STAB_MULT if stab else 1.0
    eff = get_type_effectiveness(attacker_types, skill.type_, defender_types, type_data)
    weather_mult = calc_weather(mods.weather, skill.type_)
    red_factor = calc_damage_reduction(mods.damage_reductions)

    damage = ad_ratio * power_term * ability_level * mods.power_buff * stab_mult * eff * weather_mult * red_factor

    is_crit = mods.is_critical
    if is_crit:
        damage *= CRIT_MULT

    final = max(1, math.floor(damage))

    breakdown = {
        "攻防比": round(ad_ratio, 3),
        "威力项": power_term,
        "能力等级": round(ability_level, 3),
        "威力提升buff": mods.power_buff,
        "本系加成": stab_mult,
        "克制关系": eff,
        "天气影响": weather_mult,
        "减伤系数": round(red_factor, 3),
        "暴击": CRIT_MULT if is_crit else 1.0,
    }

    return DamageResult(
        damage=final, is_critical=is_crit, effectiveness=eff,
        stab=stab, ability_level=ability_level, weather_mult=weather_mult,
        reduction_factor=red_factor, breakdown=breakdown,
    )


# ── 输出格式 ────────────────────────────────────────────────────────────────

def format_result_verbose(
    attacker_name: str, attacker_types: Tuple[str, ...],
    attacker_stats: Dict[str, float], attacker_personality: str,
    defender_name: str, defender_types: Tuple[str, ...],
    defender_stats: Dict[str, float], defender_personality: str,
    skill: SkillInfo, result: DamageResult,
) -> str:
    lines = []
    lines.append("=== 洛克王国伤害计算结果 ===")
    lines.append("")

    # 进攻方
    type_str = "/".join(attacker_types)
    lines.append(f"【进攻方】{attacker_name} ({type_str})  性格: {attacker_personality}")
    stat_parts = [f"{INTERNAL_STAT_DISPLAY[k]}: {attacker_stats[k]:.1f}" for k in STAT_ORDER]
    lines.append("  " + "  ".join(stat_parts))
    lines.append("")

    # 防御方
    type_str = "/".join(defender_types)
    lines.append(f"【防御方】{defender_name} ({type_str})  性格: {defender_personality}")
    stat_parts = [f"{INTERNAL_STAT_DISPLAY[k]}: {defender_stats[k]:.1f}" for k in STAT_ORDER]
    lines.append("  " + "  ".join(stat_parts))
    lines.append("")

    # 技能
    lines.append(f"【技能】{skill.name} ({skill.type_}/{skill.category})  威力: {skill.power}")
    lines.append("")

    # 计算过程
    lines.append("【计算过程】")
    lines.append(f"  攻防比: {result.breakdown['攻防比']}")
    lines.append(f"  威力项: {result.breakdown['威力项']}")
    lines.append(f"  能力等级: {result.breakdown['能力等级']}")
    lines.append(f"  威力提升buff: {result.breakdown['威力提升buff']}")
    stab_label = f"{result.breakdown['本系加成']} (本系)" if result.stab else f"{result.breakdown['本系加成']}"
    lines.append(f"  本系加成: {stab_label}")
    lines.append(f"  克制关系: {result.breakdown['克制关系']}")
    lines.append(f"  天气影响: {result.breakdown['天气影响']}")
    lines.append(f"  减伤系数: {result.breakdown['减伤系数']}")
    if result.is_critical:
        lines.append(f"  暴击: ×{result.breakdown['暴击']}")
    lines.append("")

    lines.append(f"【最终伤害】{result.damage}" + (" (暴击!)" if result.is_critical else ""))

    return "\n".join(lines)


def format_result_json(result: DamageResult) -> str:
    return json.dumps({
        "damage": result.damage,
        "is_critical": result.is_critical,
        "effectiveness": result.effectiveness,
        "stab": result.stab,
        "ability_level": round(result.ability_level, 3),
        "weather_multiplier": result.weather_mult,
        "reduction_factor": round(result.reduction_factor, 3),
        "breakdown": result.breakdown,
    }, ensure_ascii=False, indent=2)


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="洛克王国PvP伤害计算器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 搜索模式
    p.add_argument("--search-pet", metavar="QUERY", help="搜索宠物名称")
    p.add_argument("--search-skill", metavar="QUERY", help="搜索技能名称")

    # 核心参数
    p.add_argument("--attacker", help="进攻方宠物名")
    p.add_argument("--defender", help="防御方宠物名")
    p.add_argument("--skill", help="使用的技能名")
    p.add_argument("--attacker-types", nargs="+", metavar="TYPE", help="进攻方属性(1-2个)")
    p.add_argument("--defender-types", nargs="+", metavar="TYPE", help="防御方属性(1-2个)")

    # 性格
    p.add_argument("--personality", default="平和", help="进攻方性格(默认:平和)")
    p.add_argument("--defender-personality", default="平和", help="防御方性格(默认:平和)")

    # 个体值
    p.add_argument("--attacker-ivs", nargs=6, type=int, metavar="IV",
                   default=[0,0,0,0,0,0], help="进攻方个体值 HP ATK DEF SPA SPD SPE")
    p.add_argument("--defender-ivs", nargs=6, type=int, metavar="IV",
                   default=[0,0,0,0,0,0], help="防御方个体值 HP ATK DEF SPA SPD SPE")

    # 战斗修饰
    p.add_argument("--atk-boost", type=float, default=0, help="我方攻击提升(如0.7=+70%%)")
    p.add_argument("--atk-reduction", type=float, default=0, help="我方攻击降低")
    p.add_argument("--def-boost", type=float, default=0, help="敌方防御提升")
    p.add_argument("--def-reduction", type=float, default=0, help="敌方防御降低")
    p.add_argument("--power-multiplier", type=float, default=1, help="对应倍率(默认1)")
    p.add_argument("--power-bonus", type=float, default=0, help="威力加成")
    p.add_argument("--power-buff", type=float, default=1, help="威力提升buff")
    p.add_argument("--weather", choices=["none", "rain"], default="none", help="天气")
    p.add_argument("--damage-reductions", nargs="*", type=float, default=[],
                   help="减伤百分比列表(如0.7 0.5)")
    p.add_argument("--critical", action="store_true", help="暴击")

    # 输出
    p.add_argument("--json", action="store_true", dest="json_output", help="JSON输出")
    p.add_argument("--verbose", action="store_true", help="详细输出")
    p.add_argument("--data-dir", help="数据文件目录(默认: ../assets/)")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    data_dir = args.data_dir

    # 加载数据
    if data_dir:
        type_data = load_type_effectiveness(os.path.join(data_dir, "属性克制查询.json"))
        personalities = load_personalities(os.path.join(data_dir, "性格查询.json"))
        pets = load_pets(os.path.join(data_dir, "洛克王国全宠物种族值完整版_S1.csv"))
        skills = load_skills(os.path.join(data_dir, "洛克王国全技能库完整版_S1.csv"))
        pet_types = load_pet_types(os.path.join(data_dir, "宠物属性映射.json"))
    else:
        type_data = load_type_effectiveness()
        personalities = load_personalities()
        pets = load_pets()
        skills = load_skills()
        pet_types = load_pet_types()

    # 搜索模式
    if args.search_pet:
        results = search_pets(pets, args.search_pet)
        if not results:
            print(f"未找到包含'{args.search_pet}'的宠物")
        else:
            for name in results:
                p = pets[name]
                print(f"{name}: 精{p.hp} 攻{p.atk} 防{p.def_} 魔攻{p.spa} 魔抗{p.spd} 速{p.spe} 总{p.total}")
        return

    if args.search_skill:
        results = search_skills(skills, args.search_skill)
        if not results:
            print(f"未找到包含'{args.search_skill}'的技能")
        else:
            for name in results:
                s = skills[name]
                print(f"{name}: [{s.type_}/{s.category}] 威力{s.power} 能耗{s.energy} - {s.description}")
        return

    # 伤害计算模式
    if not args.attacker or not args.defender or not args.skill:
        parser.error("伤害计算需要 --attacker, --defender, --skill 参数")

    # 验证宠物
    if args.attacker not in pets:
        print(f"错误: 未找到宠物'{args.attacker}'，使用 --search-pet 搜索")
        sys.exit(1)
    if args.defender not in pets:
        print(f"错误: 未找到宠物'{args.defender}'，使用 --search-pet 搜索")
        sys.exit(1)

    # 验证技能
    if args.skill not in skills:
        print(f"错误: 未找到技能'{args.skill}'，使用 --search-skill 搜索")
        sys.exit(1)

    # 获取属性
    atk_types = args.attacker_types
    if not atk_types:
        if args.attacker in pet_types:
            atk_types = pet_types[args.attacker]
        else:
            print(f"错误: 未指定进攻方属性，且无映射数据。请使用 --attacker-types 指定")
            sys.exit(1)
    atk_types = tuple(normalize_type(t) for t in atk_types)

    def_types = args.defender_types
    if not def_types:
        if args.defender in pet_types:
            def_types = pet_types[args.defender]
        else:
            print(f"错误: 未指定防御方属性，且无映射数据。请使用 --defender-types 指定")
            sys.exit(1)
    def_types = tuple(normalize_type(t) for t in def_types)

    # 验证属性
    for t in atk_types + def_types:
        if t not in VALID_TYPES:
            print(f"错误: 无效属性'{t}'，有效属性: {', '.join(VALID_TYPES)}")
            sys.exit(1)

    # 验证性格
    if args.personality not in personalities:
        print(f"错误: 无效性格'{args.personality}'，可用: {', '.join(personalities.keys())}")
        sys.exit(1)
    if args.defender_personality not in personalities:
        print(f"错误: 无效防御方性格'{args.defender_personality}'")
        sys.exit(1)

    # 构建个体值字典
    atk_ivs = dict(zip(STAT_ORDER, args.attacker_ivs))
    def_ivs = dict(zip(STAT_ORDER, args.defender_ivs))

    # 计算属性
    attacker_stats = compute_all_stats(pets[args.attacker], args.personality, atk_ivs, personalities)
    defender_stats = compute_all_stats(pets[args.defender], args.defender_personality, def_ivs, personalities)

    # 构建战斗修饰
    mods = BattleMods(
        atk_boost=args.atk_boost,
        atk_reduction=args.atk_reduction,
        def_boost=args.def_boost,
        def_reduction=args.def_reduction,
        power_multiplier=args.power_multiplier,
        power_bonus=args.power_bonus,
        power_buff=args.power_buff,
        weather=args.weather,
        damage_reductions=args.damage_reductions,
        is_critical=args.critical,
    )

    skill = skills[args.skill]
    result = calculate_damage(
        attacker_stats, defender_stats, atk_types, def_types,
        skill, mods, type_data,
    )

    # 输出
    if args.json_output:
        print(format_result_json(result))
    elif args.verbose:
        print(format_result_verbose(
            args.attacker, atk_types, attacker_stats, args.personality,
            args.defender, def_types, defender_stats, args.defender_personality,
            skill, result,
        ))
    else:
        crit_str = " (暴击!)" if result.is_critical else ""
        stab_str = " 本系" if result.stab else ""
        eff_str = f" 克制×{result.effectiveness}" if result.effectiveness != 1.0 else ""
        print(f"伤害: {result.damage}{crit_str}{stab_str}{eff_str}")


if __name__ == "__main__":
    main()
