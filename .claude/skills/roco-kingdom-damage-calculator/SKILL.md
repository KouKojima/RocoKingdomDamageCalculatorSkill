---
name: roco-kingdom-damage-calculator
description: Calculate PvP damage for the game 洛克王国 (Roco Kingdom). Use this skill whenever the user asks about 洛克王国 damage calculation, PvP伤害计算, 属性克制, type effectiveness, 技能威力, or wants to compare pet stats and battle outcomes. Also trigger when the user mentions Roco Kingdom combat mechanics, 克制关系, 本系加成, STAB, 能力等级, or any related game mechanic questions — even if they don't explicitly say "damage calculator".
---

# 洛克王国PvP伤害计算器

帮助用户计算洛克王国PvP对战的伤害，包括属性计算、克制关系、技能效果等。

## 快速使用

加载根目录以了解内容

使用 伤害计算公式.md 进行计算，数据文件在根目录中。

### 搜索技巧

不要直接一口气加载文件，先用grep '名字' 或者类似的指令抓取，抓取后阅读周边的信息，比如上下20行，这样更好

### 搜索宠物/技能

观察根目录文件名以了解

### 计算伤害

最少需要指定进攻方、防御方、技能

## 核心公式

详细公式说明见根目录的 "伤害计算公式.md"(必读) 。

## 属性克制速查

18种属性间的克制关系存储在 `属性克制查询.json` 中。

## 角色特性（必查）

查询SlimmedDataSet.json。

## 性格效果

25种性格的效果存储在 `性格查询.json` 中。每种性格提升一项属性+20%，降低一项属性-10%。

## 数据文件

自己看根目录下的文件名字推断

## 注意事项

- 个体值范围0-60，最多分配到3个属性，没提到默认0，提到了默认60。如果用户提到的是78910中的任何一个值，则自动映射6倍，并告知用户。
- 状态类和防御类技能不造成伤害（除非有特别描述，比如【听桥】）
- 大部分时候必须使用上面提到的 搜索技巧，不要一次性读完所有文件
- 玩家表明精灵名字的时候可能存在typo，需要自行甄别，建议加载SlimmedDataSet.json的name字段以便获取所有名字