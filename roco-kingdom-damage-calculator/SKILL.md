---
name: roco-kingdom-damage-calculator
description: Calculate PvP damage for the game 洛克王国 (Roco Kingdom). Use this skill whenever the user asks about 洛克王国 damage calculation, PvP伤害计算, 属性克制, type effectiveness, 技能威力, or wants to compare pet stats and battle outcomes. Also trigger when the user mentions Roco Kingdom combat mechanics, 克制关系, 本系加成, STAB, 能力等级, or any related game mechanic questions — even if they don't explicitly say "damage calculator".
---

# 洛克王国PvP伤害计算器

帮助用户计算洛克王国PvP对战的伤害，包括属性计算、克制关系、技能效果等。

## 快速使用

使用 `scripts/damage_calc.py` 脚本进行计算，数据文件在 `assets/` 目录中。

```bash
PYTHONIOENCODING=utf-8 D:/anaconda/envs/env_12/python.exe scripts/damage_calc.py [选项]
```

### 搜索宠物/技能

```bash
# 搜索宠物
python scripts/damage_calc.py --search-pet 火

# 搜索技能
python scripts/damage_calc.py --search-skill 光
```

### 计算伤害

最少需要指定进攻方、防御方、技能和双方属性:

```bash
python scripts/damage_calc.py \
    --attacker 火神 --defender 水灵 \
    --skill 火焰箭 \
    --attacker-types 火 龙 --defender-types 水
```

如果宠物的属性已在 `assets/宠物属性映射.json` 中记录，可省略 `--attacker-types` / `--defender-types`。

### 完整参数示例

```bash
python scripts/damage_calc.py \
    --attacker 火神 --defender 水灵 \
    --skill 火焰箭 \
    --attacker-types 火 龙 --defender-types 水 \
    --personality 逞强 \
    --defender-personality 平和 \
    --attacker-ivs 10 10 10 0 0 0 \
    --defender-ivs 0 0 0 0 0 0 \
    --atk-boost 0.7 \
    --power-multiplier 2 \
    --weather rain \
    --critical \
    --verbose
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--attacker` | 进攻方宠物名 | (必填) |
| `--defender` | 防御方宠物名 | (必填) |
| `--skill` | 技能名 | (必填) |
| `--attacker-types` | 进攻方属性(1-2个) | 从映射查找 |
| `--defender-types` | 防御方属性(1-2个) | 从映射查找 |
| `--personality` | 进攻方性格 | 平和 |
| `--defender-personality` | 防御方性格 | 平和 |
| `--attacker-ivs` | 进攻方个体值(6个) | 0 0 0 0 0 0 |
| `--defender-ivs` | 防御方个体值(6个) | 0 0 0 0 0 0 |
| `--atk-boost` | 我方攻击提升 | 0 |
| `--atk-reduction` | 我方攻击降低 | 0 |
| `--def-boost` | 敌方防御提升 | 0 |
| `--def-reduction` | 敌方防御降低 | 0 |
| `--power-multiplier` | 对应倍率 | 1 |
| `--power-bonus` | 威力加成 | 0 |
| `--power-buff` | 威力提升buff | 1 |
| `--weather` | 天气 (none/rain) | none |
| `--damage-reductions` | 减伤百分比列表 | 无 |
| `--critical` | 暴击 | 否 |
| `--verbose` | 详细输出 | 否 |
| `--json` | JSON输出 | 否 |

## 核心公式

详细公式说明见 `references/formula.md`。关键要点:

- **属性值**: HP = `(1.7×种族+0.85×个体+70)×(1+性格)+100`，其他 = `(1.1×种族+0.55×个体+10)×(1+性格)+50`
- **伤害**: `(攻/防×0.9) × (威力×倍率+加成) × 能力等级 × buff × 本系 × 克制 × 天气 × (1-减伤)`
- **能力等级**: `(1+攻提升+敌防降低) / (1+攻降低+敌防提升)`
- **本系加成**: 技能属性匹配宠物属性时1.25倍
- **克制**: 单克制2倍，双属性都克制3倍，被抵抗0.5倍
- **暴击**: 1.5倍伤害

## 属性克制速查

18种属性间的克制关系存储在 `assets/属性克制查询.json` 中。若需要口头解释克制关系，读取该文件。

## 性格效果

25种性格的效果存储在 `assets/性格查询.json` 中。每种性格提升一项属性+20%，降低一项属性-10%。

## 数据文件

| 文件 | 内容 |
|------|------|
| `assets/属性克制查询.json` | 18种属性的攻击/防御克制关系 |
| `assets/性格查询.json` | 25种性格的属性增减 |
| `assets/洛克王国全宠物种族值完整版_S1.csv` | 全宠物种族值 |
| `assets/洛克王国全技能库完整版_S1.csv` | 全技能库 |
| `assets/宠物属性映射.json` | 宠物名→属性映射(持续扩充) |

## 注意事项

- 技能库中"地"属性对应克制表中的"土"，脚本已自动处理
- 宠物属性映射文件尚不完整，缺失时需用户通过 `--attacker-types` / `--defender-types` 指定
- 个体值范围0-10，最多分配到3个属性
- 状态类和防御类技能不造成伤害
