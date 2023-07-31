---
title: "概率导论:1-2"
hidden: true
tags: [数学]
---

# 第 1 章, 样本空间与概率

若干集合运算公式

$$
S \cap (T \cup U) = (S \cap T) \cup (S \cap U)
$$

$$
S \cup (T \cap U) = (S \cup T) \cap (S \cup U)
$$

$$
A \cup B = A \cup (A^c \cap B)
$$

$$
A \cup B \cup C = A \cup (A ^ c \cap B) \cup (A ^ c \cap B ^ c \cap C)
$$

1.2.4 概率模型, 试验, 试验结果, 事件, 样本空间; 概率律以及概率公理. 概率若干公式:

该公式表示 2 个事件至少有一个发生的概率:

$$
P (A \cup B) = P(A) + P(B) - P (A \cap B)
$$


该公式表示 2 个事件仅有 1 个发生的概率:

$$
P ((A \cap B ^ c) \cup (A ^ c \cap B)) = P(A) + P(B) - 2P(A \cap B)
$$


$$
P(A \cup B \cup C) = P(A) + P(A ^ c \cap B) + P(A ^ c \cap B ^ c \cap C)
$$

邦费罗尼不等式:

$$
P(A_1 \cap A_2 \cap \cdots \cap A_n) >= P(A_1) + P(A_2) + \cdots + P(A_n) - (n - 1)
$$

条件概率, $ P(A|B) = \frac{P(A \cap B)}{P (B)} $, 这个公式是人为定义的, 不是推断出来的. 条件概率也满足概率公理, 所以条件概率也是概率律.

$$
P(A \cup B | Z) = P(A|Z) + P(B|Z) - P(A \cap B|Z)
$$

例 1.9, "飞机没有出现, 雷达报警" 是 $P(A^c \cap B)$, 我以为是 $P(B|A^c)$

例 1.11, $P(A_1) = \frac{12}{15}$, 我一开始不理解 "先假定学生 1 已经选定了位子" 对不对, 即我们在 '先假定' 这个前提下求得 $P(A_1) = \frac{12}{15}$ 是否正确的. 这里举例说明,

Q: 假设现在有 2 排, 每排 4 个位置, 求学生 1,2 选择不同排的概率?

A: 这里用序贯树形图表示:

{% mermaid %}
graph LR
  a[ ]-->|A1|b1[ ]
  a-->|A2|b2[ ]
  b1-->|B1|c1[ ]
  b1-->|B2|c2[ ]
  b2-->|B1|d1[ ]
  b2-->|B2|d2[ ]
{% endmermaid %}

此时 A1 为学生 1 选择了第一排, A2 为学生 1 选择了第二排; B1 为学生 2 选择了第一排, B2 为学生 2 选择了第二排. 则学生 1, 2 选择不同排的概率为

$$
\begin{align}
P(A_1 \cap B_2) + P(A_2 \cap B_1) &= P(B_2|A_1) * P(A_1) + P(B_1 | A_2) * P(A_2) \\
 &= \frac{1}{2} * \frac{4}{7} + \frac{1}{2} * \frac{4}{7} \\
 &= \frac{4}{7}
\end{align}
$$

1.4 全概率定理; 贝叶斯准则, 因果推理, 先验概率, 后验概率;

条件概率的全概率公式, 此时 $C_1, \cdots, C_n$ 为 n 个互不相容的事件, 并且形成了样本空间的一个分割. 另 A, B 是两个事件, 满足 $P(B \cap C_i) > 0$ 对一切 i 成立. 公式:

$$
P(A|B) = \sum_{i=1}^n {P(C_i | B) P (A | B \cap C_i)}
$$

1.5.1 见独立性结论. 已知 $P(A \cap B) = P(A) \cdot P(B)$, 可得 $P(A \cap B^c) = P(A) \cdot P(B^c)$, 即事件 A 与 B 独立意味着事件 A 与事件 $B^c$ 也独立.

1.5.2 相互独立. A, B, C, D 相互独立意味着一个小组中任意事件的出现与否不影响另一组事件; 即 $P(A \cup B| C \cap D) = P(A \cup B)$. 同时也意味着 $A \cup B$, C, D 相互独立. 同时也意味着 $P(A \cap B | C) = P (A|C) \cdot P(B|C)$

1.5.4 独立试验序列, 伯努利试验序列, 二项系数, 二项概率, 二项公式; 见习题 47 了解杨辉三角与二项系数.

1.6 多项系数, 计数法汇总; 例 1.32 中的分割是对字母位置做分割, 而不是对字母分割.

# 第二章, 离散随机变量

2.1 随机变量是试验结果的一个实值函数, 试验结果搜对应的数称为随机变量的取值. '与随机变量相关的主要概念', '与离散随机变量相关的概念'.

2.2 分布列刻画了随机变量的取值概率. 伯努利随机变量, 二项随机变量, 几何随机变量, 泊松随机变量;

当 n 很大时, p 很小, 并且 $\lambda=np$ 时, 如下公式成立:
$$
e^{-\lambda} \frac{\lambda^k}{k!} \approx \frac{n!}{k!(n-k)!}p^k(1-p)^{n-k}
$$

2.3 线性函数, 若随机变量 Y = g(X) = a * X + b, 其中 a, b 是常数. 对任意 Y = g(x) 都有:

$$
P_Y(y) = \sum_{\{x|g(x)=y\}}P_X(x)
$$

2.4 期望, 均值和方差

期望 $E[X] = \sum_x xP_X(x)$.

二阶矩 $E[X^2]$. n阶矩 $E[X^n]$.

方差 $var(X)=E[(X-E[X])^2]$ . 标准差 $\sigma_X=\sqrt{var(X)}$.

随机变量的函数的期望 $E[g(X)] = \sum_xg(x)P_X(x)$

Y = aX+b, $E[Y] = aE[X] + b$. $var(Y) = a^2 var(X)$

用矩表达的方差公式 $var(X) = E[X^2] - (E[X])^2$

伯努利随机变量的均值与方差 $E[X] = p$, $E[X^2] = p$, $var(X) = p(1-p)$

离散均匀随机变量. $E[X] = \frac{a+b}{2}$, $var(X)=\frac{(b-a)(b - a +2)}{12}$

泊松随机变量. $E[X] = \lambda$, $var(X) = \lambda$

2.5 多个随机变量的联合分布列

$P_{X,Y}(x,y) = P(X=x, Y=y) = P({X=x} \cap {Y=y})$

边缘分布列 $P_X(x) = \sum_y P_{X,Y}(x,y)$, $P_Y(y) = \sum_x P_{X,Y}(x,y)$

多个随机变量的函数, Z=g(X,Y).

$$P_Z(z) = \sum_{\{(x,y) | g(x, y) = z\}} P_{X,Y}(x,y) $$

$$ E[g(X,Y)] = \sum_x \sum_y g(x,y) P_{X,Y}(x,y) $$

$$ E[aX+bY+c] = aE[X] + bE[Y] + c $$

$$ P_{X,Y,Z}(x,y,z) = P(X=x, Y=y, Z=z) $$

$$ P_{X,Y}(x,y) = \sum_x P_{X,Y,Z}(x,y,z) $$

$$ P_{X}(x) = \sum_y \sum_x P_{X,Y,Z}(x,y,z) $$

$$ E[g(X,Y,Z)] = \sum_x \sum_y \sum_z g(x,y,z) P_{X,Y, Z}(x,y,z) $$

$$ E[a_1X_1+a_2X_2+ \cdots + a_nX_n] = a_1E[X_1] + a_2E[X_2] + \cdots + a_nE[X_n]$$

$ E[X + Y + Z] = E[X] + E[Y] + E[Z] $, 这里 X, Y, Z 可以是任何形式; 所以有: $E[(1+X)^2] = E[1 + X^2 + 2X] = E[1] + E[X^2] + 2E[X]$.

2.6 条件

随机变量 X 相对事件 A 的条件分布列:

$$
P_{X|A}(x) = \frac{P(X=x \cap A)}{P(A)}
$$

$$
P_{X|Y}(x|y) = \frac{P_{X,Y}(x,y)}{P_Y(y)}
$$

$$
P_X(x) = \sum_y P_Y(y)P_{X|Y}(x|y)
$$

设 $A_1, \cdots, A_n$ 是一组互不相容的事件, 并且形成样本空间的一个分割, 假定 $P(A_i) > 0$ 对一切 i 成立, 则:

$$
P_X(x) = \sum_{i=1}^nP(A_i)P_{X|A_i}(x)
$$

$$
P_{X|B}(x) = \sum_{i=1}^nP(A_i|B)P_{X|A_i \cap B}(x)
$$

条件期望的小结

$$
E[X|A] = \sum_x x P_{X|A}(x)
$$

$$
E[g(X)|A] = \sum_x g(x) P_{X|A}(x)
$$

$$
E[X|Y=y] = \sum_x x P_{X|Y}(x|y)
$$

设 $A_1, \cdots, A_n$ 是一组互不相容的事件, 并且形成样本空间的一个分割, 假定 $P(A_i) > 0$ 对一切 i 成立, 则:


$$
E[X] = \sum_{i=1}^nP(A_i)E[X|A_i]
$$

$$
E[X|B] = \sum_{i=1}^nP(A_i|B)E[X|A_i \cap B]
$$

$$
E[X] = \sum_{y}P_Y(y)E[X|Y=y]
$$

例 2.17

$$
E[X] = \sum_{k=1}^\infty k (1-p)^{k-1}p = \frac{1}{p}
$$

$$
var(X) = \sum_{k=1}^\infty (k - E[X])^2 (1-p)^{k-1}p = \frac{1-p}{p^2}
$$

2.7 独立性

随机变量之间的相互独立性, 直观上, X, Y 相互独立意味着 Y 的取值不会提供 X 取值的信息.

$$
P_{X,Y}(x,y) = P_X(x)P_Y(y), 任意 x, y
$$

$$
E[XY] = E[X]E[Y]
$$

X, Y 独立意味着 g(X), h(Y) 独立.
$$
E[g(X)h(Y)] = E[g(X)]E[h(Y)]
$$

$$
var(X+Y) = var(X) + var(Y)
$$

给定事件 A 的条件下, 随机变量的条件独立性

$$
P_{X,Y|A}(x,y) = P_{X|A}(x)P_{Y|A}(y). 任意 x, y
$$

例 2.21, 样本均值的期望与方差. 据此可以看出样本均值是随机变量公共期望的一个好的估计.