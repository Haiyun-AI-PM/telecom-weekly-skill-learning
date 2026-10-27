# -*- coding: utf-8 -*-
"""独立复算：只读取 week-a.json 的原始分子/分母，不引用任何既有结论。
运行：python3 recompute.py
"""
import json, itertools
from fractions import Fraction as F

P = "week-a.json"
d = json.load(open(P, encoding="utf-8"))
prior, cur = d["prior"], d["current"]

def f(x):  # 原始计数
    return {k: x[k] for k in ("leads", "effective_contacts", "appointments", "orders")}

A, B = f(prior), f(cur)

print("=== 0. 原始输入（逐字取自 %s） ===" % d["source_id"])
print("prior  %s %s" % (prior["period"], A))
print("current%s %s" % (cur["period"], B))

print("\n=== 1. 逐级嵌套校验（同周漏斗必须单调不增） ===")
for tag, x in (("prior", A), ("current", B)):
    L, E, P_, O = x["leads"], x["effective_contacts"], x["appointments"], x["orders"]
    print("%s: ec<=leads %s (%d<=%d) | appt<=ec %s (%d<=%d) | orders<=appt %s (%d<=%d)"
          % (tag, E <= L, E, L, P_ <= E, P_, E, O <= P_, O, P_))

print("\n=== 2. 四个率（精确分数 + 小数，分子分母全部列出） ===")
def rates(x):
    L, E, P_, O = x["leads"], x["effective_contacts"], x["appointments"], x["orders"]
    return {
        "触达率=有效沟通/线索": (F(E, L), E, L),
        "预约率=预约/有效沟通": (F(P_, E), P_, E),
        "办理率=办理/预约": (F(O, P_), O, P_),
        "整体办理率=办理/线索": (F(O, L), O, L),
    }
ra, rb = rates(A), rates(B)
for k in ra:
    va, na, da = ra[k]; vb, nb, db = rb[k]
    pp = (vb - va) * 100
    rel = (vb / va - 1) * 100
    print("%s\n   prior %d/%d = %s = %.6f%%\n   current %d/%d = %s = %.6f%%\n   差 %+.4f pp | 相对 %+.4f%% (未四舍五入)"
          % (k, na, da, va, float(va)*100, nb, db, vb, float(vb)*100, float(pp), float(rel)))

print("\n=== 3. 四个数量的变化（绝对量与相对变化） ===")
for k in ("leads", "effective_contacts", "appointments", "orders"):
    d_abs = B[k] - A[k]
    rel = (F(B[k], A[k]) - 1) * 100 if A[k] else None
    print("%-20s %4d -> %4d  Δ %+4d  %s" % (k, A[k], B[k], d_abs,
          ("%+.4f%%" % float(rel)) if rel is not None else "分母为0，不计算相对变化"))

print("\n=== 4. 一致性校验：分母不变时，率的相对变化 = 分子数量的相对变化 ===")
print("触达率相对 %.4f%% vs 有效沟通数相对 %.4f%%  (分母均200)"
      % (float((rb['触达率=有效沟通/线索'][0]/ra['触达率=有效沟通/线索'][0]-1)*100),
         float((F(B['effective_contacts'], A['effective_contacts'])-1)*100)))
print("整体办理率相对 %.4f%% vs 办理数相对 %.4f%%  (分母均200)"
      % (float((rb['整体办理率=办理/线索'][0]/ra['整体办理率=办理/线索'][0]-1)*100),
         float((F(B['orders'], A['orders'])-1)*100)))

print("\n=== 5. 办理量两级分解（先预约数、再办理率；对预约/办理两段在有效沟通后闭合） ===")
# 第一级：预约数 50->40，按上一期办理率 25/50
step1 = F(A["appointments"], 1) * F(A["orders"], A["appointments"])   # 50*0.5 = 25
mid   = F(B["appointments"], 1) * F(A["orders"], A["appointments"])   # 40*0.5 = 20
end   = F(B["appointments"], 1) * F(B["orders"], B["appointments"])   # 40*0.4 = 16
print("起点 50预约 x 50%% = %s 单" % step1)
print("预约数改按新值 40 x 上一期50%% = %s 单  -> 预约量效应 %+d 单" % (mid, mid - step1))
print("办理率改按新值 40 x 40%% = %s 单       -> 转化率效应 %+d 单" % (end, end - mid))
print("合计 %+d 单，实际办理 %d->%d 差 %+d 单，残差 %d" % ((mid-step1)+(end-mid), A["orders"], B["orders"], B["orders"]-A["orders"], (B["orders"]-A["orders"])-((mid-step1)+(end-mid))))

print("\n=== 6. 三因素逐项代入：六种代入顺序的贡献（检验顺序依赖） ===")
# 以整体办理率(小数)为基数，因素 = 触达率 t, 预约率 a, 办理率 o
t0, t1 = ra["触达率=有效沟通/线索"][0], rb["触达率=有效沟通/线索"][0]
a0, a1 = ra["预约率=预约/有效沟通"][0], rb["预约率=预约/有效沟通"][0]
o0, o1 = ra["办理率=办理/预约"][0], rb["办理率=办理/预约"][0]
base = t0*a0*o0
total = t1*a1*o1 - base
print("基数 t0*a0*o0 = %s = %.6f%%，终值 = %s = %.6f%%，总变 %+.4f pp"
      % (base, float(base)*100, t1*a1*o1, float(t1*a1*o1)*100, float(total)*100))
names = {"t": "触达率", "a": "预约率", "o": "办理率"}
val = {"t": (t0, t1), "a": (a0, a1), "o": (o0, o1)}
rows = []
for perm in itertools.permutations("tao"):
    state = {"t": t0, "a": a0, "o": o0}
    contrib = {}
    for k in perm:
        before = state["t"]*state["a"]*state["o"]
        state[k] = val[k][1]
        after = state["t"]*state["a"]*state["o"]
        contrib[k] = (after - before) * 100
    s = sum(contrib.values())
    rows.append((perm, contrib, s))
    print("顺序 %s : 触达 %+8.4f pp | 预约 %+8.4f pp | 办理 %+8.4f pp | 合计 %+.4f pp | 守恒 %s"
          % ("->".join(names[k] for k in perm), float(contrib["t"]), float(contrib["a"]),
             float(contrib["o"]), float(s), abs(float(s)-float(total*100)) < 1e-9))

print("\n=== 7. 符号贡献占比（以总变 -4.5pp 为分母），验证合计=100% ===")
for perm, contrib, s in rows:
    print("顺序 %s : 触达 %+7.4f%% | 预约 %+7.4f%% | 办理 %+7.4f%% | 合计 %+.4f%%"
          % ("->".join(names[k] for k in perm),
             float(contrib["t"]/ (total*100) *100),
             float(contrib["a"]/ (total*100) *100),
             float(contrib["o"]/ (total*100) *100),
             float(sum(contrib.values())/(total*100)*100)))

print("\n=== 8. 对称(Shapley)归因：对6种顺序取平均，消除顺序依赖 ===")
sh = {"t": F(0), "a": F(0), "o": F(0)}
for perm, contrib, s in rows:
    for k in "tao":
        sh[k] += contrib[k]
for k in "tao":
    sh[k] = sh[k] / 6
print("触达率 %+8.4f pp (占 %+.2f%%)" % (float(sh["t"]), float(sh["t"]/(total*100)*100)))
print("预约率 %+8.4f pp (占 %+.2f%%)" % (float(sh["a"]), float(sh["a"]/(total*100)*100)))
print("办理率 %+8.4f pp (占 %+.2f%%)" % (float(sh["o"]), float(sh["o"]/(total*100)*100)))
print("合计 %+.4f pp" % float(sh["t"]+sh["a"]+sh["o"]))

print("\n=== 9. 反事实：若触达率维持 75%%，预约数与办理数会是多少 ===")
cf_appt = F(A['leads'],1)*t0*a1          # 200*0.75*0.25
print("预约数：200 x 75.0%% x 25.0%% = %s（实际 40）-> 触达改善带来 %s 人" % (cf_appt, F(B['appointments'],1)-cf_appt))
cf_orders = cf_appt*o0                    # *0.5
print("对应办理数（按上一期办理率50%%）：%s，实际 16" % cf_orders)

print("\n=== 10. 缺失与边界（逐字摘自 week-a.json） ===")
print("missing_evidence:", d["missing_evidence"])
for n in d["field_notes"]:
    print("feedback %s: %s | %s" % (n["id"], n["text"], n["evidence_level"]))
print("cohort_rule:", d["cohort_rule"])
