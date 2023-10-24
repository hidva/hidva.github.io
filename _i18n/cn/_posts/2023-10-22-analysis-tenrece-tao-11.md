---
title: "陶哲轩实分析: 黎曼积分"
hidden: false
tags: ["数学"]
---


> 这是我关于实分析学习总结的第一篇文章，为了便于读者了解背景和快速进入主题，我认为有必要先介绍一下这篇文章的风格和如何使用。
>
> 首先，我为什么会选择学习数学？一方面是因为看到了[Jemalloc Profile背后的数学原理]({{site.url}}/2023/08/04/jemalloc-prof-math/)所展示的数学的强大和实用性，另一方面则是被[Polar Code（极化码）具体原理是怎样的](https://hidva.com/g?u=https://www.zhihu.com/question/31656512/answer/53891038)回答所展示的数学对生产力的推动所吸引。为此，我制定了一个全面的数学学习计划，从实分析开始到随机过程。我期望这种学习能给我在日常工作中带来新的视角和启示。
>
> 对于这种通过教材进行的系统学习，其知识密度非常大，我无法将整本书的内容都复制过来。因此，在总结过程中，我只会展示书本上没有提到的地方，这些是我自己的思考和对原文的延伸。这可能导致整篇总结看起来非常零散和琐碎。因此，建议读者仅将此总结作为参考，在阅读书籍时遇到不懂的地方可以查看此总结中是否有可以解答疑惑的小节。
>
> 我个人在数学学习中注重对概念的理解，同时将定理/命题视为连接概念的桥梁，而证明过程则是从一组概念开始，通过一系列命题搭建的桥梁最终到达另一组概念。就像我和我的同事戏称的那样：或许自动证明并不需要那么繁琐的过程，如果我们首先建立一张大的数学知识图谱，其中概念作为图中的顶点，定理作为边，那么自动证明就是给定起点/终点的一次寻路过程。
>
> 实分析学习使用的教材: 陶哲轩实分析, 第三版; 使用的习题答案集: [analysis-tenrece-tao-3rd](https://christangdt.home.blog/analysis/analysis-tenrece-tao-3rd-ed/)

引理 11.1.4; 这里 "有界的", "有界区间" 的概念让我懵了一刹那. "有界的" 定义在定义 9.1.22, "有界区间" 在例 9.1.3;

----

定义 11.1.10, 若 P 是 I 的划分, 则意味着如下情况均成立:

- P 是有限集合.
- P 中各元素均是有界区间.
- P 中各元素互不相交.
- $\cup P = I$, 这里 $\cup P$定义在公理 3.11, 指 P 中元素形成的并集.

同样若如上情况均成立也意味着 P 是 I 的一个划分.

----

定理 11.1.13 的证明,

首先证明当 n = 0, 1, 2, 3 时 P(n) 成立, 以 n = 3 为例, 此时 I 被划分为了 $I_1, I_2, I_3$; 令 $I_1.l$ 为左端点, $I_1.r$ 为右端点; 这里不失一般性, 假设 $I_1, I_2, I_3$ 是按照左端点从小到大排序的情况, 这里暂时不考虑空集, 则易证 $I_1.r = I_2.l, I_2.r = I_3.l$, 此时明显 $
|I| = |I_1| + |I_2| + |I_3|
$. 若 $I_1, I_2, I_3$ 中有空集存在, 以 $I_3$ 为空集为例, 则易证 $I_1, I_2$ 是 I 的划分, 即 $
|I| = |I_1| + |I_2| + |I_3|
$ 仍然成立.

之后运用命题 2.2.14 强归纳法, 即已知命题 11.1.13 对所有小于 n + 1 情况成立, 证明此时 P(n + 1) 也成立. 考虑 $P = I_1, I_2, ... I_{n+1}$ 是 I 的划分, 对于任一 $I_i$, 若 $I_i$ 为空, 则可证明 $P \setminus \{I_i\}$ 也是 I 的一个分布, 且其基数小于 n + 1, 即由 P(m) 对 $m < n + 1$ 情况成立可知 $
|I| = \sum_{J \in P \setminus \{I_i\}}|J| = \sum_{J \in P} |J|
$, 即此时 P(n + 1) 成立.

下面假设 $I_i$ 全不为空, 构造集合 $P_1 = \{I_j, I_j.r < I_i.r\}$, $P_2 = \{I_j, I_j.r \gt I_i.r\}$, 此时 $P_1, P_2$ 是 P 的真子集, $card(P_1) < card(P), card(P_2) < card(P)$, 并且 $\cup P_1, \cup P_2, I_i$ 是 I 的一个划分, 即 $
|I| = |\cup P_1| + |\cup P_2| + |I_i|
$. 同时 $P_1$ 是 $\cup P_1$ 的一个划分, $P_2$ 是 $\cup P_2$ 的一个划分, 即 $
|\cup P_1| = \sum_{j \in P_1} |j|
$, 即 $
|I| = \sum_{j \in P_1} |j| + \sum_{j \in P_2} |j| + |I_i| = \sum_{J \in P} |J|
$, P(n + 1) 成立.

----

注 11.2.2, 对原文如下描述的进一步说明:

> 当 E 是空集时, 每一个实数 c 都是 f 在 E 上的常数值

首先看下常数值函数的定义, 若 f 是 E 上的常数值函数 f(x) = c, 则对于 E 中任意 e1, e2, f(e1) 等于 f(e2) 等于 c; 反过来说, 便是不存在 e1 属于 E, 且 f(e1) 不等于 c; 当 E 为空集时, 对于任意实数 c, 都很明显不存在元素 e1(因为这时 E 为空!), f(e1) 不等于 c.

----

引理 11.3.3 的证明, 关于 $\overline{\int_I f} \ge \underline{\int_I f}$ 的证明,

这里我使用的是反证法, 假设 $\overline{\int_I f} \lt \underline{\int_I f}$, 即 $$
\underline{\int_I f} > inf\{p.c. \int_I g\}
$$, 则意味着存在分段函数函数 g, g 从上方控制 f, $\overline{\int_I f} \le p.c. \int_I g \lt \underline{\int_I f}$; 对于任意分段函数函数 h, h 从下方控制了 f, 此时可知 $h(x) <= f(x) <= g(x), x \in I$, 根据定理 11.2.16(e) 可知 $p.c. \int_I h \le p.c. \int_I g$, 即 $$
p.c. \int_I g \ge sup\{p.c. \int_I h\}
$$, 这与 $p.c. \int_I g \lt \underline{\int_I f}$ 矛盾. QED.

----

引理 11.3.7, 我的证法: 对于任意 g, g 从上方控制了 f, g 在 I 上关于划分 P1 是分段常数函数, f 在 I 上关于划分 P2 是分段常数函数, 令 P = P1 # P2, 则 g, f 是 I 上关于 P 的分段常数函数, $p.c. \int_I f = p.c. \int_P f, p.c. \int_I g = p.c. \int_P g$, 由命题 11.2.6(e) 结合 g(x) >= f(x) 可知 $p.c. \int_I g \ge p.c. \int_I f$ 对于任意 g 成立. 所以 $p.c. \int_I f \le \overline{\int_I f}$. 同时 f 也从上方控制了 f, 即 $p.c. \int_I f \ge \overline{\int_I f}$, 所以 $p.c. \int_I f = \overline{\int_I f}$. 同理 $p.c. \int_I f = \underline{\int_I f}$. QED.

写到这里想到搞复杂了, 由于 f 从上方/下方控制了 f, 所以 $\overline{\int_I f} \le p.c. \int_I f \le \underline{\int_I f}$, 结合引理 11.3.3 可知 $p.c. \int_I f = \overline{\int_I f} = \underline{\int_I f}$.

----

命题 11.3.12 的证明,

令 $S_1 = \{ \int_I g, g 是分段常数函数, 并从上方控制了 f \}, S_2=\{ U(f, P) \}$, 对于 $\forall e2, e2 \in S_2, e2 = U(f, P_1)$, 可以定义分段函数 $g(x) = sup_{x \in J} f(x), J \in P_1$, 可知 g 是 I 上关于 P1 的分段函数, 且 $\int_I g = U(f, P_1)$; 即 $S_2 \subseteq S_1$, 所以 $inf(S2) \ge inf(S1)$.

对于任意 e1 是 I 上关于划分 P2 的分段常数函数, e1 从上方控制了 f, 此时可以很方便地构造出分段常数函数 $e2(x) = sup_{x \in J} f(x), J \in P_2, e1(x) >= e2(x), \int_I e2 = U(f, P_2), \int_I e1 \ge \int_I e2 \ge inf(S2)$, 所以 $inf(S1) >= inf(S2)$. 即 inf(S1) 等于 inf(S2). 同理可证 sup(S1) = sup(S2).

----

命题 11.4.1(a) 原文证法解析:

由于 $\int_I f = inf\{\int_I \overline f\}, $对于任意 $\epsilon \gt 0$, 存在 $\overline f$, $\overline f$ 分段常数函数, 并且 $\overline f$ 从上方控制了 f, 且 $\int_I \overline f \lt \int_I f + \epsilon$. 同理存在 $\underline f$, 分段常数, 并从下方控制了 f, $\int_I \underline f \gt \int_I f - \epsilon$; 即:

$$\int_I f - \epsilon \lt \int_I \underline f \le \int_I f \le \int_I \overline f \lt \int_I f + \epsilon$$
$$\int_I g - \epsilon \lt \int_I \underline g \le \int_I g \le \int_I \overline g \lt \int_I g + \epsilon$$

且 $\overline f + \overline g$ 是分段常数函数, 并从上方控制了 f + g; $\underline f + \underline g$ 是分段常数函数, 并从下方控制了 f + g; 即

$$\int_I f + \int_I g - 2\epsilon \lt \int_I \underline f + \int_I \underline g = \int_I {\underline f + \underline g} \le \underline{\int_I f + g} \le \overline{\int_I f + g} \le \int_I {\overline f + \overline g} = \int_I \overline f + \int_I \overline g \lt \int_I f + \int_I g + 2\epsilon $$


----

命题 11.4.1.zy1, 这种带有 'zy1' 后缀的命题都是未在原文出现, 是我自己脑补出来的命题, 设 A, B, C 三个集合, 若对于 A 中任意 a, B 中任意 b, C 中存在 c, c <= a + b; 同时对于 C 中任意 c, A 中存在 a, B 中存在 b, c <= a + b, 求证 sup(C) <= sup(A) + sup(B); inf(C) <= inf(A) + inf(B).

证明: 对于任意 c 属于 C, A 中存在 a, B 中存在 b, c <= a + b, 结合 a <= sup(A), b <= sup(B), 可知 c <= sup(A) + sup(B), 所以 sup(C) <= sup(A) + sup(B).

至于 inf(C) <= inf(A) + inf(B), 反证假设 inf(C) > inf(A) + inf(B), 即 $inf(C) = inf(A) + inf(B) + \epsilon1 + \epsilon2, \epsilon1 > 0, \epsilon2 > 0$. 此时 A 中存在 a, $a < inf(A) + \epsilon1$, B 中存在 b, $b < inf(B) + \epsilon2$, C 中存在 c, $c \le a + b \lt inf(A) + inf(B) + \epsilon1 + \epsilon2$, 即 $c \lt inf(C)$, 矛盾.

命题 11.4.1.zy2, 将命题 11.4.1.a.zy1 中的 "<= 换成 ">=", 则同样成立.

----

命题 11.4.1.zy4, 若 P1, P2 是有界区间 I 的划分, P2 比 P1 更细, 则 $\forall J \in P_1, P_J = \{J_2 \in P_2, J_2 \subseteq J\}$ 构成了 J 的一个划分.

这里主要证明, 对于 $\forall x \in J, x \in \cup P_J$, 假设 $x \notin \cup P_J$, 即在 P2 中存在了某个元素 J3, $x \in J_3, J_3 \nsubseteq J, J_3 \in P_2, \exists J_4 \in P_1, J_3 \subseteq J_4, x \in J \cap J_4$, 这里 J, J4 都是 P1 的元素, 其不可能相交, 矛盾QED.

----

命题 11.4.1.zy3, 考虑 U(f, P1), U(f, P2), P2 比 P1 更精细, 则 U(f, P2) <= U(f, P1), L(f, P2) >= L(f, P1).

证明: $
U(f, P_1) = \sum_{J \in P_1}{sup_{x \in J} f(x) |J|} = \sum_{J \in P_1}{sup_{x \in J} f(x) (|J_1| + |J_2| + \cdots + |J_n|)}
$, 这里 J1, J2, ..., Jn 属于 P2, 他们组成了对 J 的划分, 结合 $sup_{x \in J} f(x) \ge sup_{x \in J_i} f(x)$, 很明显可以得到结论.

----

命题 11.4.1(a) 我的证法解析: 观察 $S_1 = \{U(f, P_1)\}, S_2=\{U(g, P_2)\}, S_3=\{U(f + g, P)\}$, 对于 $
\forall e1 \in S_1, e2 \in S_2, e1 = U(f, P_1), e2 = U(g, P_2); U(f, P_1 \unicode{x23} P_2) \le e1, U(g, P_1 \unicode{x23} P_2) \le e2; U(f + g, P_1 \unicode{x23} P_2) \le U(f, P_1) + U(g, P_2)$, 即 $\exists e3 \in S_3, e3 \le e1 + e2
$, 所以 inf(S3) <= inf(S1) + inf(S2), 即 $\overline{\int_I f + g} \le \overline{\int_I f} + \overline{\int_I g}$. 同理最终可完成证明, 很明显原文证法更直观一些...


----

命题 11.4.1(h) $\forall \epsilon > 0, \exists \overline f, \int_I \overline f \lt \overline{\int_I f} + \epsilon, \int_I \overline f = \int_J \overline f + \int_K \overline f, \int_J \overline f \ge \overline{\int_J f}, \overline{\int_J f} + \overline{\int_K f} \le \overline{\int_I f}$, 最终可证:

$$\overline{\int_J f} + \overline{\int_K f} = \int_I f$$
$$\underline{\int_J f} + \underline{\int_K f} = \int_I f$$

考虑 $\underline{\int_J f} \le \overline{\int_J f}, \underline{\int_K f} \le \overline{\int_K f}$, 所以可得 $\underline{\int_J f} = \overline{\int_J f}, \underline{\int_K f} = \overline{\int_K f}$


----

命题 11.4.3, 首先看下原文证法, 其主要点在于令 $h1(x) = max(\overline f, \overline g) - max(\underline f, \underline g)$, 对于 I 中任意 x, 此时有如下情况:

$$
h1(x) = \left\{
\begin{array}{l}
\overline f - \underline f & & \overline f(x) \ge \overline g(x), \underline f(x) \ge \underline g(x) \\
\overline f - \underline g \le \overline f - \underline f & & \overline f(x) \ge \overline g(x), \underline f(x) \le \underline g(x) \\
\overline g - \underline f \le \overline g - \underline g & & \overline f(x) \le \overline g(x), \underline f(x) \ge \underline g(x) \\
\overline g - \underline g & & \overline f(x) \le \overline g(x), \underline f(x) \le \underline g(x)
\end{array}
\right.
$$

即要么 $h1(x) \le \overline f - \underline f$, 要么 $h1(x) \le \overline g - \underline g$, 即 $h1(x) \le (\overline f - \underline f) + (\overline g - \underline g)$

----

命题 11.4.3.zy1, 设 an, bn 两个序列, inf(an) = sup(bn), 则 an >= bn, 对于任意 n 成立. 且对于 $
\forall \epsilon > 0, \exists a_i, b_j, |a_i - b_j| \le \epsilon
$.

关于这个定理, 我本来以为可以推出 an 与 bn 等价, 但后来想了个反例: an = 1, 2, 3, ...; bn = 1, -1, -2, -3, ...

证明, 对于 $\forall \epsilon1 > 0, \exists b_j, b_j > sup(b_n) - \epsilon1; \forall \epsilon2 > 0, \exists a_i, a_i < inf(a_n) + \epsilon2$. 此时 $a_i - b_j < \epsilon1 + \epsilon2$. QED.

关于该命题, 将序列两个集合, 也可以得到同样的结果.

----

命题 11.4.3.zy2, 设 an, bn 两个序列, sup(bn) <= inf(an), 若对于 $
\forall \epsilon > 0, \exists a_i, b_j, |a_i - b_j| \le \epsilon
$, 则 sup(bn) = inf(an).

证明, 对于 $\forall \epsilon > 0, a_i \le b_j + \epsilon$, 即 $inf(a_n) \le a_i \le b_j + \epsilon \le sup(b_n) + \epsilon$ 恒成立, 即 $inf(a_n) \le sup(b_n)$, 所以 QED.

关于该命题, 将序列两个集合, 也可以得到同样的结果.

----

命题 11.4.3.zy3, 设 f 是定义在有界区间 I, 值域为 R 的函数, f 黎曼可积, 则对于任意 $\epsilon > 0$, 存在 I 上划分 P, 使得 $U(f,P) - L(f,P) \le \epsilon$,

证: 据命题 11.4.3.zy1 可知$\exists U(f, P1), L(f, P2); U(f,P1) - L(f,P2) \le \epsilon$, 令 P = P1 # P2, 可知 $U(f, P) - L(f,P) \le U(f,P1) - L(f,P2) \le \epsilon$.

进一步可推, 对于任意比 P 更精细的划分 P1, 如上命题也成立.

----

命题 11.4.3.zy4, 设 f 是定义在有界区间 I, 值域为 R 的函数, 若对于 $\forall \epsilon > 0, \exists P, U(f, P) - L(f, P) \le \epsilon$, 那么 f 黎曼可积.

证: 可直接从命题 11.4.3.zy2 推出.

----

命题 11.4.3, 我的证法, 主要利用 命题 11.4.3.zy3, 命题 11.4.3.zy4; 已知 f 在 I 上黎曼可积, 所以存在 I 上划分 P1, $U(f, P1) - L(f, P1) \le \epsilon, \forall \epsilon > 0$, 存在 I 上划分 P2, $U(g, P2) - L(g, P2) \le \epsilon, \forall \epsilon > 0$; 令 P = P1 # P2, 则 $U(f, P) - L(f, P) \le \epsilon, U(g, P) - L(g, P) \le \epsilon$ 即:

$$
\left\{
\begin{aligned}
\sum_{J \in P}(sup_{x \in J} f(x) - inf_{x \in J} f(x))|J| \le \epsilon1 \\
\sum_{J \in P}(sup_{x \in J} g(x) - inf_{x \in J} g(x))|J| \le \epsilon2
\end{aligned}
\right.
$$

同时由于

$$
sup(max(f, g)) = max(sup(f(x)), sup(g(x))) \\
inf(max(f, g)) \ge max(inf(f(x)), inf(g(x)))
$$

可推出:

$$
sup(max(f, g)) - inf(max(f, g)) \le max(sup(f), sup(g)) - max(inf(f), inf(g)) \\
\le (sup(f) - inf(f)) + (sup(g) - inf(g))
$$

即:

$$
\sum_{J \in P}(sup(max(f, g) - inf(max(f, g)))) |J| \le \epsilon1 + \epsilon2
$$

----

命题 11.4.5 原文证法说明:

> 类似地, 我们可以假设 $\overline{f_+}(x) \le M_1$

这是因为, 对于 $\forall \overline{f_+}, min(\overline{f_+}, M1) \le \overline{f_+}, \int_I min(\overline{f_+}, M1) \le \int_I \overline{f_+}$, 这里 $min(\overline{f_+}, M1)$ 也从上方控制了 $f_+$.

> 关于其他三个函数的结论可以类似地证明

在我们已知 $f_{+}g_+$ 是黎曼可积之后, 意味着 $\forall f, g; f(x) \ge 0, g(x) \ge 0, \forall x \in I$, 若 f, g 黎曼可积, 则 fg 也黎曼可积. 现在考虑 $f_+g_-$ 情况, 此时 $g_-(x) \le 0, \forall x \in I$, 令 $g' = -g_-, g'(x) \ge 0, \forall x \in I$, 由于 $g_-$ 可积, 结合命题 11.4.1(b) 可知 $g'$ 也可积, 可知 $f_+g'$ 也可积, 从而 $f_+g_- = -f_+g'$ 也可积.

----

习题 11.4.3, 我的证法. 这个证法我感觉有点太学究了...

使用数学归纳法, 令 Q(n) 表示对于基数为 n 的划分 P 命题成立. 由定理 11.4.1(h) 可知 Q(1), Q(2) 成立. 现在假设 Q(N) 成立, 证 Q(N+1) 也成立. 这里暂不考虑 P 中包含空集情况.

由于 P 中不包含空集, 则对于 P 中任意不同的元素 J1, J2 其不会具有相同的左端点或者右端点. 可以使用反证法, 假设 J1, J2 具有相同的左端点, 则由于 J1, J2 均不为空, J1, J2 必相交, 这与划分定义矛盾.

在 P 上定义序关系, $J1 \le J2 <=> J1.l \le J2.l$, 则易证 $\le$ 是 P 上的偏序关系, P 此时是全序的, 根据习题 9.5.8 可知 P 是良序集. 所以可以定义, 定义域为自然数集, 值域为 P 的映射 f, f(0) 为 P 中最小元素, f(1) 为 $P \setminus {f(0)}$ 的最小元素, 以此类推. 易证此时 f 是双射. 之后定义如下集合, $f(\unicode{x23}P - 1)$ 为 P 中最大元素:

$$
P_1 = \{f(\#P - 1)\} \\
P_2 = P \setminus P_1
$$

则易证 $I \setminus P1$ 是有界区间, P2 是区间 $I \setminus P1$ 的一个划分, #(P2) = N, 考虑到我们假设 Q(N) 成立, 所以 $\int_{I \setminus P1} f = \sum_{J \in P_2} \int_J f$; 同时 P1, P2 是 I 的划分, 据命题 11.4.1(h) 可知 $\int_I f = \int_{P_1} f + \int_{P_2} f = \int_{P_1} f + \sum_{J \in P_2} \int_J f = \sum_{J \in P} \int_J f$

对于 P 中包含空集的情况, 此时若 I 为空集, 则很明显命题成立. 若 I 不为空集, 令 $P1 = \{J \in P, J \neq \emptyset\}$, 则 P1 是 I 的一个划分, $\int_I f = \sum_{J \in P1} \int_J f = \sum_{J \in P} \int_J f$.

----

命题 11.5.1, 根据命题 11.4.3.zy4, 只要 $\forall \epsilon > 0$, 我们可以找到划分 P, 使得 $U(f, P) - L(f, P) \le \epsilon$ 即可证明 f 是可积的. 由于 f 一致连续, 即对于 $
\frac{\epsilon}{|I|}
$(115111),$
\exists \delta, |x_1 - x_2| \le \delta, |f(x_1) - f(x_2)| \le \frac{\epsilon}{|I|}
$ 成立. 以 I 为 `[a, b]` 形式为例, 定义划分 $P = \{[a, a + \delta), [a + \delta, a + 2\delta), \cdots, [b - \delta, b] \}$, 此时 $
\unicode{x23}(P) = \left \lceil{\frac{|I|}{\delta}}\right \rceil
$, 由于对于 P 中任意元素 J, f 在 J 上也一致连续, 根据命题 9.6.7 可知 $
\exists X_{max}, X_{min}; f(X_{max}) = sup(f_{|J}); f(X_{min}) = inf(f_{|J})
$; 观察此时 $
U(f, P) - L(f, P) = \sum_{J \in P}(sup(f) - inf(f)) |J|, sup(f) - inf(f) \le \frac{\epsilon}{|I|}, U(f, P) - L(f, P) \le \epsilon
$. QED.

115111: 此时只考虑 $$
|I| > 0
$$ 的情况, 当 $$
|I| = 0
$$ 时意味着 I 为空集或者单点集, 此时结论很明显


----

命题 11.5.3, 我一开始想法是连续有界可以推出一致连续, 但后来找了个反例 $f(x) = sin(\frac{1}{x}), x \in [0, 1)$.

之后另一个想法是, f 在 (a, b) 上连续有界, 则 $\lim_{x \to a} f$ 存在, 之后可以构造:

$$
F(x) = \left\{
\begin{array}{ll}
\lim_{x \to a} f & x = a \\
f(x) & x \in (a, b) \\
\lim_{x \to b} f & x = b
\end{array}
\right.
$$

很明显 F 可积从而推出 f 可积. 但问题是 $\lim_{x \to a} f$ 不一定存在, 反例也是上面的 $sin(\frac{1}{x})$...

----

命题 11.6.1, 基本思想是设 P 是 I 的划分, $P = \{J_1, J_2, \cdots, J_n\}, J_1.l < J_2.l < J_3.l < \cdots < J_n.l$, 此时可观察到这里 $
sup(f_{|J_1}) = inf(f_{|J_2})
$, 现在我们只考虑最简单的情况 $
|J_1| = |J_2| = \cdots = |J_n|
$, 那么 $
U(f,P) - L(f,P) = (sup(f) - inf(f)) |J_1|
$, 对于 $
\forall \epsilon > 0, |J_1| <= \frac{\epsilon}{sup(f) - inf(f)}, U(f,P) - L(f,P) \le \epsilon
$, QED.

----

习题 11.8.3, 我很好奇为啥要求 $\alpha$ 单调递增, 看了下这里 (a), (b), (c) 的证明对 $\alpha$ 没有任何要求, (d) 之后确实要求 $\alpha$ 单调递增.

----

习题 11.8.4, 使用我对定理 11.5.1 证明即可, 只不过将证明过程中的 $
|I|
$ 换成 $\alpha[I]$ 即可.

----

习题 11.8.5, 这里首先证明对于任意 $\overline f$, $\overline f$ 是 `[-1, 1]` 上关于划分 P 的分段常数函数, $\overline f$ 从上方控制了 f, $p.c. \int_I \overline f dsgn \ge 2f(0)$. 证明:

对于划分 P, 可知$\exists J_0 \in P, 0 \in J_0$; 此时 J0 要么是单点集 `[0, 0]`; 要么是非单点集, 此时存在 `a > 0, b > 0`, `(-a, b)` 位于 J0 中. 先假设 J0 是单点集 `[0, 0]`, 易证 P 是比划分 `{[-1, 0), [0, 0], (0, 1]}` 更精细的划分; 根据命题 11.4.1.zy4可知, P 存在一个子集 P1 是区间 `[-1, 0)` 的划分, 同样存在一个子集 P2 是 `(0, 1]` 的划分. 依据习题 11.1.3, 区间 `[-1, 0)` 在划分 P1 中一定存在形如 `[c1, 0)`, `(c1, 0)` 的区间, c1 位于 `[-1, 0)` 中. 同理 P2 中也一定存在形如 `(0, c2]`, `(0, c2)`, c2 位于 `(0, 1]` 的区间.

$p.c. \int_I \overline f dsgn = \overline{f_{c1}} + \overline{f_{c2}}$, 这里 $\overline{f_{c1}}, \overline{f_{c2}}$ 是 $\overline f$ 在 `(c1, 0)`, `(0, c2)` 上的常数值, 此时可证 $\overline{f_{c1}} \ge f(0), \overline{f_{c2}} \ge f(0)$. 使用反证法假设 $\overline{f_{c1}} \lt f(0), f(0) - \overline{f_{c1}} = \epsilon1, \epsilon1 \gt 0$, 即 $\forall x' \in (c1, 0), f(x') \le \overline{f_{c1}} \lt f(0), f(0) - f(x') \ge \epsilon1$ 因为 f(x) 在 0 点连续, 即 $
\exists \delta, \forall x' \in (-\delta, 0), |f(x') - f(0)| \le \frac{\epsilon1}{2}
$. 所以在 $
\forall x' \in (max(-\delta, c1), 0), f(0) - f(x') \ge \epsilon1, |f(x') - f(0)| \le \frac{\epsilon1}{2}
$ 同时成立, 矛盾! 所以 $\overline{f_{c1}} \ge f(0)$. 所以 $p.c. \int_I \overline f dsgn \ge 2f(0)$.

对于 J0 是非单点集情况, 更简单了, 这里不再赘述. 之后再证明 $\forall \epsilon \gt 0, \exists \overline f, p.c.\int_I \overline f dsgn \le 2f(0) + \epsilon$ 这样便可完成证明 $\overline{\int_I fdsgn} = 2f(0)$. 证明: f(x) 在 x=0 处连续, 即 $
\exists \delta \gt 0, \forall x' \in (-\delta, \delta), |f(x') - f(0)| \le \frac{\epsilon}{2}
$, 以此构建划分 $P=\{[-1, -\delta],(-\delta, 0), [0, 0], (0, \delta), [\delta, 1]\}$, $\overline f$ 是 P 上分段常数, 从上方控制了 f, $\overline{f_{(-\delta, 0)}} = f(0) + \frac{\epsilon}{2}, \overline{f_{(0, \delta)}} = f(0) + \frac{\epsilon}{2}$, $\overline{f_{(-\delta, 0)}}$ 是 $\overline f$ 在 $(-\delta, 0)$ 上的常数值; 可知 $p.c. \int_I \overline f dsgn = 2f(0) + \epsilon$.

同理可证 $\underline{\int_I fdsgn} = 2f(0)$. 最终得 $\int_I fdsgn = 2f(0)$.

从证明过程可以看到这里只要求 f 在 0 点连续即可得到同样的结论.

----

定理 11.9.4, 这里 F 是 f 的原函数, f 黎曼可积, 如定义 11.3.4 所示, 有界是可积的前提条件, 即可积必有界, f 有界; 按照习题 10.2.6, 习题 10.2.7 可知 F 一致连续且 F 是 Lipschitz continuous function.

----

习题 11.9.2.zy1, 设 $f: I \to R$, I 有界区间, 若 $\forall x \in I, f'(x) = 0$, 那么 $f(x) = c$, 即 $\forall x_1, x_2 \in I, f(x_1) = f(x_2) = c$. 反证:

假设 $
\exists x_1, x_2 \in I, f(x_1) \ne f(x_2), f|_{[x_1, x_2]}
$ 满足推论 10.2.9 条件, 所以 $\exists x_0 \in (x_1, x_2), f'(x_0) = \frac{f(x_1) - f(x_2)}{x_1 - x_2} \ne 0$. 矛盾 QED.

----

习题 11.9.2, 令 $H(x) = F(x) - G(x)$, 由于 F, G 可微, 据定理 10.1.12(f) 可知 H 可微, 且 $H'(x) = F'(x) - G'(x) = 0$, 据习题 11.9.2.zy1可知 $H(x) = C$, 所以 QED.

----

习题 11.9.1, 问题关键是要搞清楚 f(x) 在有理数 r 附近的情形, 由习题 9.8.5 可知

$$
\left\{
\begin{array}{ll}
f(x) \ge f(r) + g(r) & x \gt r \\
f(x) \le f(r) - g(r') & x \lt r, r' \in (x, r), r' \in Q \\
\end{array}
\right.
$$

假设 F(x) 在 r 处可微, 即 $\lim_{x \to r} \frac{F(x) - F(r)}{x - r}$ 存在, 其值设为 L. 因为 r 是 `(r, 1]` 的附着点, 所以存在序列 $X_n, \lim_{n \to +\infty} X_n = r; \forall n, X_n \in (r, 1]$, 则 $\lim_{n \to +\infty} \frac{F(X_n) - F(r)}{X_n - r} = L, \frac{F(X_n) - F(r)}{X_n - r} = \frac{\int_r^{X_n} f}{X_n - r}$, 由于 $f(X_n) \ge f(r) + g(r)$, 所以 $\frac{F(X_n) - F(r)}{X_n - r} \ge \frac{(f(r) + g(r))(X_n - r)}{X_n - r} = f(r) + g(r)$. 同理令 $$
Y_n, \forall n, Y_n \in [0, r), \lim_{n \to +\infty} Y_n = r$$, $$
\frac{F(Y_n) - F(r)}{Y_n - r} = \frac{\int_{Y_n}^r f}{r - Y_n} \le \frac{(f(r) - g(r'))(r - Y_n)}{r - Y_n} = f(r) - g(r')
$$. 意味着 $f(r) + g(r) \le L \le f(r) - g(r')$, 这样的 L 不存在, QED!

----

习题 11.9.3, 这里只证明可微意味着连续. 证明: F(x) 在 $x=x_0$ 处可微, 即 $\lim_{x \to x_0} \frac{F(x) - F(x_0)}{x - x_0}$ 存在, 设其值为 L, 即:

$$
\lim_{x \to x_0, x \in (a, x_0)} \frac{F(x) - F(x_0)}{x - x_0} = \lim_{x \to x_0, x \in (x_0, b)} \frac{F(x) - F(x_0)}{x - x_0} = L
$$

考虑 $\forall x \in (x_0, b), \frac{F(x) - F(x_0)}{x - x_0} = \frac{\int_{x_0}^x f}{x - x0}$, 因为 f 单调递增, 即 $\int_{x_0}^x f \ge f(x_0)(x - x_0), \frac{F(x) - F(x_0)}{x - x_0} \ge f(x_0), L \ge f(x_0)$. 同理由 $\lim_{x \to x_0, x \in (a, x_0)} \frac{F(x) - F(x_0)}{x - x_0} = L$ 可知 $L \le f(x_0), L = f(x_0)$.

假设 f 在 $x_0$ 处不连续, 这意味着:

$$
\left\{
\begin{array}{lr}
\exists \epsilon1 \gt 0, f(y) \gt f(x_0) + \epsilon1, \forall y \gt x_0 & (1) \\
\exists \epsilon2 \gt 0, f(y) \lt f(x_0) - \epsilon2, \forall y \lt x_0 & (2)
\end{array}
\right.
$$

(1)(2) 至少有一个成立. 可以反证假设 (1)(2) 都不成立, 以 (1) 不成立为例, 此时意味着 $\forall \epsilon \gt 0, \exists y \gt x_0, f(y') \le f(y) \le f(x_0) + \epsilon, \forall y' \in (x_0, y)$, 即 $f(x_0+) = f(x_0)$. 即 (1)(2) 都不成立可以推出 $f(x_0+) = f(x_0) = f(x_0-)$, 结合命题 9.5.3 可知 f 在 $x_0$ 处连续.

以 (1) 成立为例, 已知 $\lim_{y \to x_0, y \in (x_0, b)} \frac{F(y) - F(x_0)}{y - x_0} = f(x_0)$. 由于 $x_0$ 是 $(x_0, b]$ 的附着点, 所以存在序列 $X_n, \lim_{n \to +\infty} X_n = x_0; \forall n, X_n \in (x_0, b]$. $\frac{F(X_n) - F(x_0)}{X_n - x_0} = \frac{\int_{x_0}^{X_n} f}{X_n - x_0} \gt \frac{(f(x_0) + \epsilon1)(X_n - x_0)}{X_n - x_0} = f(x_0) + \epsilon1$, 依据定理 6.4.13 可知 $f(x_0) = \lim_{n \to +\infty}\frac{F(X_n) - F(x_0)}{X_n - x_0} \ge f(x_0) + \epsilon1$, 矛盾!

----

定理 11.10.2 在 $C_J\alpha[J] = \int_J C_J \alpha'$ 证明上, 我是使用了命题 11.10.1, 令 $F = f = C_J, F' = 0, G = \alpha$ 代入命题 11.10.1 可得.

----

习题 11.10.4, 我暂时没有做出来, 主要点在于若 $\phi$ 单调递减, 那么 11.8 中 "f 在 I 上关于 $\alpha$ 是黎曼-斯蒂尔杰斯可积" 这一概念的定义是否还有意义?! 毕竟在 $\alpha$ 单调递增时, 命题 11.4.1.zy3 仍然是成立的, 即随着划分越来越精细, $p.c.\int_I gd\alpha$ 越来越小, 这时取 $inf\{p.c.\int_I gd\alpha\}$ 也不是很突兀. 但当 $\phi$ 单调递减时, 即随着划分越来越精细, $p.c.\int_I gd\alpha$ 越来越大... 关于黎曼-斯蒂尔杰斯可积, 仍待通过其他资料加深理解..

----

习题 11.10.3, 这里假设我们已经解出了 '习题 11.10.4', 那么可以令 $h(y) = -y, g(x) = f(h(x))$, 此时 h(y) 单调递减, 可套入命题 11.10.7 解.
