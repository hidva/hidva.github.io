---
title: "Jemalloc Profile 背后的数学原理"
hidden: false
tags: ["JustForFun"]
---

Jemalloc Profile 是一个非常有用的功能, 对于一次内存分配, jemalloc 会以一定几率决定是否对这次内存分配进行采样, 如果决定采样, 此时 jemalloc 会保存此次内存分配若干上下文信息, 如堆栈等. 之后可以周期性让 Jemalloc 将其保存的采样信息 dump 到指定文件, 通过文件中记录的采样信息结合 jeprof 等工具我们可以很直观地看出哪些堆栈是内存分配热点, 哪些堆栈仍持有着大块内存等信息. 我一开始以为这里面做法很简单直观, 无非就是在内存分配时使用随机数生成器生成一个随机数, 之后结合用户配置的采样概率决定是否对本次内存分配采样; 比如用户配置对 5% 的内存分配进行采样, 那么我们可以使用随机数生成器生成一个 `[0, 100)` 的数字 N, 之后仅当 N < 5 的时候我们才对内存分配进行采样. 但偶然扫了眼 jemalloc profile 实现, 才发现我太幼稚了!

为了理解 jemalloc profile 实现, 首先我们要建立一个简单的数学模型. 对于一次内存分配, 我们令事件 A 表示对此次内存分配进行采样, 事件 B 表示对此次内存分配不进行采样, P(A) 表示事件 A 发生的概率, P(A) + P(B) = 1. 基于此对于每一次内存分配, 我们定义一个随机变量 I, I 值为 1 对应着事件 A; I 值为 0 对应着事件 B; 那么 $P_I(1) = P(A); P_I(0) = P(B)$. I 的期望 $E[I] = 1 * P_I(1) + 0 * P_I(0) = P_I(1)$, 二阶矩 $E[I^2] = 1^2 * P_I(1) + 0^2 * P_I(0) = E[I]$.

对于一个特定的堆栈 SB, 其上有 $S_1, S_2, \cdots, S_n$ 次内存分配, 这些内存分配有的被采样保存下来了, 其他的没有被采样保存; 现在问题是, 我们应该如何设计采样决策使得我们可以根据采样得到的内存分配信息更精确地推断出 $\sum_iS_i$. 举例现在堆栈 SB 上有 7 次内存分配, 其大小分配是 100, 200, 300, 400, 500, 600, 700 字节, 共 2800 字节; 假设我们只采样了第 1 次与第 3 次, 那么从采样结果看堆栈 SB 上共分配了 100 + 300 = 400 字节; 在将采样结果展示给用户之前, 我们还是希望能对这个采样结果做些处理, 使得用户能知道自己在堆栈 SB 上共分配了 2800 字节(或者是近似的值), 而不是简单地把 400 字节显示给用户看.

记每次内存分配对应的随机变量 $I_1, I_2, \cdots, I_n$ 表示着内存分配是否被采样, 这些随机变量之后相互独立. 令随机变量 Y 为:

$$ Y=\sum_i S_i I_i \frac{1}{\mathrm{E}[I_i]} $$

此时 Y 的期望为(这块如果忘了, 可以翻一下概率论):

$$ E[Y] = \sum_i S_i \mathrm{E}[I_i] \frac{1}{\mathrm{E}[I_i]} = \sum_i S_i $$

可以看到 Y 的期望正是我们想要的堆栈 SB 上内存分配总大小. 即 Y 是 $\sum_i S_i$ 一个很好的估计. 这意味着如果我们以概率 P 决定是否对一个内存分配进行采样, 那么在我们决定采样之后, 通过累加本次采样内存分配大小 $S_j$: $\sum_j \frac{S_j}{P}$ 便得到了随机变量 Y 的一个取值, 这个取值是对堆栈 SB 上内存分配总大小的一个估计值. 这也是 jemalloc prof_malloc_sample_object() 中:

```c
// 由于 jeprof 将内存分配大小划分为 size class, 即 jeprof 一次内存分配大小取值
// 来自于一个有限可数集合 sz_index2size_tab.
// 这里 szind 即是本次内存分配大小在数组 sz_index2size_tab 中对应的下标.
// prof_unbiased_sz[szind] = sz_index2size_tab[szind] / P,
// 这里 P 是用户配置的采样概率.
// curbytes_unbiased 便是随机变量 Y 的一个取值.
size_t shifted_unbiased_cnt = prof_shifted_unbiased_cnt[szind];
size_t unbiased_bytes = prof_unbiased_sz[szind];
tctx->cnts.curobjs++;
tctx->cnts.curobjs_shifted_unbiased += shifted_unbiased_cnt;
tctx->cnts.curbytes += usize;
tctx->cnts.curbytes_unbiased += unbiased_bytes;
```

第二个问题是, 我们应该如何选择概率 P 使得随机变量 Y 对 $\sum_i S_i$ 的估计更精确, 换而言之即是 Y 的方差 var(Y) 尽可能小:

$$
\begin{align}
Var(Y) &= Var(\sum_i S_i I_i \frac{1}{E[I_i]})  \\
=& \sum_i Var(S_i I_i \frac{1}{E[I_i]}) \tag{1.1} \label{gongshi11} \\
=& \sum_i \frac{S_i^2}{E[I_i]^2} Var(I_i) \\
=& \sum_i \frac{S_i^2}{E[I_i]^2} Var(I_i) \\
=& \sum_i \frac{S_i^2}{E[I_i]^2} E[I_i](1 - E[I_i]) \tag{1.2} \label{gongshi12} \\
=& \sum_i S_i^2 \frac{1 - E[I_i]}{E[I_i]}.
\end{align}
$$

如上公式 $\ref{gongshi11}$ 推导用到了定理: 对于相互独立的随机变量 X, Y 有 $var(X+Y) = var(X) + var(Y)$. 如上公式 $\ref{gongshi12}$ 推导用到了定理 $var(X) = E[X^2] - (E[X])^2$, 对于我们这里的随机变量 I 有 $E[I^2] = E[I]$

第一种选择概率 P 的方式, 即使我们开头提到的, 由用户配置一个比较大的数 N, 之后对于每次分配有 $\frac{1}{N}$ 的概率被采样. 在此情况下, 随机变量 I 的期望 $E[I] = \frac{1}{N}$, 随机变量 Y 的方差 var(Y) :

$$ var(Y) = \sum_i S_i^2 \frac{1 - \frac{1}{N}}{\frac{1}{N}}  = (N-1) \sum_i S_i^2.$$

可以看到 N 越大, 方差越大, 即 Y 对 $\sum_i S_i$ 的估计精度越差.

另一种选择概率 P 的方式, 也是 jemalloc 当前使用的方式, 由用户配置一个值 R, 之后每个字节有 $\frac{1}{R}$ 的概率被采样, 对于一个大小为 Z 的内存分配, 只要其内 1 个字节决定被采样, 那么便对本次内存分配进行采样. 因此此时 $P(A) = 1-(1-\frac{1}{R})^{Z}$. 此时 $E[I] = P(A)$. 方差 var(Y):

$$
var(Y) = \sum_i S_i^2 \frac{(1-\frac{1}{R})^{S_i}}{1-(1-\frac{1}{R})^{S_i}}
$$

考虑到在 R 相当大的情况时, 公式 $(1-\frac{1}{R})^{S_i} \approx e^{-S_i/R}$ 成立. 所以 $var(Y) \approx \sum_i S_i^2 \frac{e^{-S_i/R}}{1 - e^{-S_i/R}}$. 此时我们分如下几种情况来讨论 var(Y), 如下 Z 为某次内存分配大小:

- 当 Z 远小于 R 时, 此时 $e^{-Z/R} \approx 1 - Z/R$. 进一步 Z 对应的那些 $S_i$ 有 $S_i^2 \frac{e^{-S_i/R}}{1 - e^{-S_i/R}} \approx S_i(R-S_i) \approx S_i R$.

- 当 Z 与 R 相近时, 此时 $\frac{e^{-Z/R}}{1 - e^{-Z/R}} \approx 1$. 进一步 Z 对应的那些 $S_i$ 有 $S_i^2 \frac{e^{-S_i/R}}{1 - e^{-S_i/R}} \approx S_i^2$.

- 当 Z 远大于 R 时, 此时 $\frac{e^{-Z/R}}{1 - e^{-Z/R}} \approx 0$. 进一步 Z 对应的那些 $S_i$ 有 $S_i^2 \frac{e^{-S_i/R}}{1 - e^{-S_i/R}} \approx 0$.

所以综合可以看出, 当前 jemalloc 使用的方式产生的方差 var(Y) 相对较小.

## prof_do_unbias

如上所示, 我们已知 curbytes_unbiased 已经是随机变量 Y 的一个取值了, 即已经是 $\sum_i S_i$ 的一个估计了, 即在 prof dump 时, jeprof 直接输出 curbytes_unbiased 即可. 为何还要经过 prof_do_unbias() 再做一次处理? 这是因为
