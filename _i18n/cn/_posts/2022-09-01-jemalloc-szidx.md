---
title: "jemalloc 代码精读 0: sz_size2index_compute"
hidden: false
tags: ["C++"]
---

为了便于内存管理, jemalloc 引入 size class 的概念, 在 jemalloc 内部只支持分配 size classes 指定的 size 字节. 默认情况下, jemalloc 支持的 size class 有 8byte, 16byte, 32byte, 64byte 等等; 即 jemalloc 内部不支持分配一个大小为 33byte 的内存块. 在 jemalloc 处理用户内存分配请求时, 会将用户需要的字节数对齐到一个最近的 size class 上, 比如用户调用了 malloc(48), 那么 jemalloc 内部会分配 64 字节.

jemalloc size class 实现上在我看来非常巧妙, jemalloc 并没有硬编码出一个 size class table, 而是首先定义了一组 size class table 应该满足的特征, 之后基于此结合用户输入动态生成了 size class table. 与此同时, jemalloc 其他模块在与 size class 打交道时, 都是基于这组特征进行, 并没有依赖任何硬编码/预设信息; 换句话说, 用户可以手动更改 SC_LG_NGROUP, SC_LG_TINY_MIN, LG_QUANTUM 等宏定义, 按照自己业务特征, 生成一份与众不同的 size class table.

sz_size2index(size) 函数的语义很简单, 返回最近一个 >= size 的 size class 在 size class table 中的索引. 我在第一次看到这个函数的时候, 就想到了 `size_t sz_index2size_tab[SC_NSIZES]`, 这个全局变量按照 size class 从小到大的顺序保存了 size class table 的内容. 从语义上讲, sz_size2index 一种正确实现如下所示:

```c++
szind_t my_sz_size2index(size_t size) {
  auto array_start = std::begin(sz_index2size_tab);
  auto ptr = std::lower_bound(array_start, std::end(sz_index2size_tab), size);
  return std::distance(array_start, ptr);
}
```

而 jemalloc 的实现如下所示, 咋一看, 很是复杂, 完全没有 my_sz_size2index 看起来简洁明了:

```c
static inline szind_t
sz_size2index_compute(size_t size) {
	if (unlikely(size > SC_LARGE_MAXCLASS)) {
		return SC_NSIZES;
	}

	if (size == 0) {
		return 0;
	}
#if (SC_NTINY != 0)
	if (size <= (ZU(1) << SC_LG_TINY_MAXCLASS)) {
		szind_t lg_tmin = SC_LG_TINY_MAXCLASS - SC_NTINY + 1;
		szind_t lg_ceil = lg_floor(pow2_ceil_zu(size));
		return (lg_ceil < lg_tmin ? 0 : lg_ceil - lg_tmin);
	}
#endif
	{
		szind_t x = lg_floor((size<<1)-1);
		szind_t shift = (x < SC_LG_NGROUP + LG_QUANTUM) ? 0 :
		    x - (SC_LG_NGROUP + LG_QUANTUM);
		szind_t grp = shift << SC_LG_NGROUP;

		szind_t lg_delta = (x < SC_LG_NGROUP + LG_QUANTUM + 1)
		    ? LG_QUANTUM : x - SC_LG_NGROUP - 1;

		size_t delta_inverse_mask = ZU(-1) << lg_delta;
		szind_t mod = ((((size-1) & delta_inverse_mask) >> lg_delta)) &
		    ((ZU(1) << SC_LG_NGROUP) - 1);

		szind_t index = SC_NTINY + grp + mod;
		return index;
	}
}
```

看了下 commit log, sz_size2index_compute 是 2017-5 引入, sz_index2size_tab 是 2017-12 引入, 所以我当时一个想法是: 是不是在引入 sz_index2size_tab 之后忘了替换 sz_size2index_compute 的实现了? 我之前走读 postgres 的时候也遇到过好几次这种情况; 如我之前给 postgres 做的一次提交 [Improve and cleanup ProcArrayAdd(), ProcArrayRemove()](https://hidva.com/g?u=https://github.com/postgres/postgres/commit/d8e950d3ae7b33a2064a4fb39b7829334b0b47bc), 就是在引入一个更高效的组件之后忘了以此改进某些原有链路的实现.

所以我当时有点兴奋... 可以给 jemalloc 混个 PR 了= 当然在 PR 之前需要测试一下两个函数性能差异, 对于 jemalloc 这种基础组件来说, 可读性要求弱于性能要求. 然后测试结果令我震惊, jemalloc sz_size2index_compute 是 my_sz_size2index 的一倍多! 这强烈引起了我的好奇, 如下也会一行行的解释 sz_size2index_compute; 在此之前还需要加深对 jemalloc size class table 的认知, 之前提到了 jemalloc 并没有硬编码 size class table, 而是定义了一组特征, 基于特征生成了 size class table, 如下会介绍这组特征, 以及基于特征推测出来的定理. jemalloc 定义的 size class table 模版如下所示, 这里提到的 size class table 即 sz_index2size_tab, 从小到大存放着 size class 的值.

```
Tiny size classes:
- Count: LG_QUANTUM - SC_LG_TINY_MIN.
- Sizes:
    1 << SC_LG_TINY_MIN
    1 << (SC_LG_TINY_MIN + 1)
    1 << (SC_LG_TINY_MIN + 2)
    ...
    1 << (LG_QUANTUM - 1)

Initial pseudo-group:
- Count: SC_NGROUP
- Sizes:
    (lg_delta = 1 << LG_QUANTUM)
    1 * (1 << LG_QUANTUM)
    2 * (1 << LG_QUANTUM)
    3 * (1 << LG_QUANTUM)
    ...
    SC_NGROUP * (1 << LG_QUANTUM)

Regular group 0:
- Count: SC_NGROUP
- Sizes:
  (relative to lg_base of LG_QUANTUM + SC_LG_NGROUP and lg_delta of
  lg_base - SC_LG_NGROUP)
    (1 << lg_base) + 1 * (1 << lg_delta)
    (1 << lg_base) + 2 * (1 << lg_delta)
    (1 << lg_base) + 3 * (1 << lg_delta)
    ...
    (1 << lg_base) + SC_NGROUP * (1 << lg_delta) [ == (1 << (lg_base + 1)) ]

Regular group 1:
- Count: SC_NGROUP
- Sizes:
  (relative to lg_base of LG_QUANTUM + SC_LG_NGROUP + 1 and lg_delta of
  lg_base - SC_LG_NGROUP)
    (1 << lg_base) + 1 * (1 << lg_delta)
    (1 << lg_base) + 2 * (1 << lg_delta)
    (1 << lg_base) + 3 * (1 << lg_delta)
    ...
    (1 << lg_base) + SC_NGROUP * (1 << lg_delta) [ == (1 << (lg_base + 1)) ]

...

Regular group N:
- Count: SC_NGROUP
- Sizes:
  (relative to lg_base of LG_QUANTUM + SC_LG_NGROUP + N and lg_delta of
  lg_base - SC_LG_NGROUP)
    (1 << lg_base) + 1 * (1 << lg_delta)
    (1 << lg_base) + 2 * (1 << lg_delta)
    (1 << lg_base) + 3 * (1 << lg_delta)
    ...
    (1 << lg_base) + SC_NGROUP * (1 << lg_delta) [ == (1 << (lg_base + 1)) ]
```

可以看到 tiny size classes 中 size class 均是 2 的 n 次方, 并且每个 size class 是前一个的 2 倍; 即在 size class table 中, 当下标 i 对应着 tiny size class 时, `sz_index2size_tab[i] = 2 ** (i + k)`, k = SC_LG_TINY_MIN. 基于这个信息我们分析下 sz_size2index_compute 当 `size <= (ZU(1) << SC_LG_TINY_MAXCLASS)` 链路, 此时 size 一定是个 tiny size class; 我们现在要求 i, 满足 sz_index2size_tab[i] 是最小的 >= size 的值, 即 `2 ** (i + k)` 是最小的满足 >= size 的值. `lg_ceil = lg_floor(pow2_ceil_zu(size))`, 根据 lg_floor/pow2_ceil_zu 实现可以看到这里 `2 ** lg_ceil` 是最小的 >= size 的值. 即 i + k = lg_ceil, 即 i = lg_ceil - SC_LG_TINY_MIN, 这里 lg_tmin = SC_LG_TINY_MIN, 即 i = lg_ceil - lg_tmin.

接下来看下非 tiny size class 的情况, 这里令 k1 = SC_LG_NGROUP, k2 = LG_QUANTUM; 非 tiny size class 可以每 SC_NGROUP 划分为一组, 此时各组 size class 值如下所示:

```
Initial pseudo-group: [size_class01, size_class02, ,,, 2 ** (k1 + k2 + 0)]
Regular group 0     : [size_class11, size_class12, ,,, 2 ** (k1 + k2 + 1)]
Regular group 1     : [size_class21, size_class22, ,,, 2 ** (k1 + k2 + 2)]
Regular group 2     : [size_class31, size_class32, ,,, 2 ** (k1 + k2 + 3)]
...
```

可以看到每组最后一个 size class 总是 `2 ** (k1 + k2 + shift)`, 这里 shift 从 0 开始, 以 1 递增. 结合着 sz_size2index_compute 源码:

```c
// 这里 2 ** x 是最小的 >= size 的值,
x = lg_floor((size<<1)-1);
// 此时表明 size 位于 2 ** (k1 + k2 + shift) 对应的组 G 中,
shift = (x < SC_LG_NGROUP + LG_QUANTUM) ? 0 : x - (SC_LG_NGROUP + LG_QUANTUM);
// grp 表明了 size 所在组 G 前面有 grp 个 size class,
// 即 G 中第一个 size class 在 size class table 的下标是 grp + SC_NTINY
grp = shift << SC_LG_NGROUP;
```

之后再看下每个组内各个 size class 值有什么特征, 以 Regular group 0 为例, 其内各个 size class 值 = `(1 << lg_base) + M * (1 << lg_delta)`, M 从 1 开始, 以 1 递增; 换成二进制可能更方便一点, 一个特定的组 size class 值如下:

```
 |<---M-->|<-L bits->|
10......0010.........0
10......0100.........0
10......0110.........0
10......1000.........0
...
```

结合着 sz_size2index_compute 代码:

```
// 这里 lg_delta 即每个组 G 对应的 L 取值.
size_t delta_inverse_mask = ZU(-1) << lg_delta;
// mod 即 M 的值了.
szind_t mod = ((((size-1) & delta_inverse_mask) >> lg_delta)) & ((ZU(1) << SC_LG_NGROUP) - 1);
```

Q: 为什么这里不直接使用 `(size & delta_inverse_mask) >> lg_delta`, 而是 `size - 1`?

A: 将 size 带入组中第一个 size class `0b10......0010.........0` 便可晓得为啥. 以 size = `0b10......0010.........0` 为例, 若直接使用 `size`, 那么 mod = 1, 不符合预期了.

最终 `SC_NTINY + grp + mod` 便是 sz_size2index_compute 应该返回的值了. 可以看到, 虽然 sz_index2size_tab 可读性较弱, 但其效率确实非常强的, 仅需要寥寥几个位运算便完成了目标.


## 后语

一直对 jemalloc 背后细节很是好奇, 也一直有空就瞅瞅代码, 直至今日, 总算把 jemalloc 整体链路走读了一遍. 正如当时过完 [linux scheduler]({{site.url}}/2022/01/13/pelt/), 有种醍醐灌顶的清明感啊一样. 对 jemalloc 背后细节的了解掌握又一次让我享受到了这一滋味.
