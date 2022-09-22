---
title: "使用 jegdb 来调试内存相关 crash"
hidden: false
tags: ["C++"]
---

这周我值班, 然后值班的时候有个同事找过来让帮忙排查个 coredump; 当时稀里糊涂一起看了下, 正好又有值班上的事情就被打断了. 等忙完了手头上的事情之后忽然又想起了这个 coredump:

![]({{site.url}}/assets/20220922020201.jpg)

咋一看, 这个 coredump 原因很明显, PostgreSQL MemoryContext 结构体被写坏了:

```c++
(gdb) p *(AllocSetContext*)0x7fe20cc44000
$3 = {
  header = {
    type = T_AllocSetContext,
    isReset = false,
    allowInCritSection = false,
    methods = 0x7fe20cc44000,  /* 特征1: 指向自身 */
  },
  blocks = 0x7fe20cc440d8,
  freelist = {0x7fe20cc44170, 0x7fe20cc44100, 0x0, 0x709240 <AllocSetMethods> /* 特征2 */, 0x7fe20cc44300, 0x7fe20cc441f0, 0x0, 0x0, 0x0, 0x0, 0x0},
}
```

而且如标注, 几处被写坏的位置也有比较明显的特征. 如果对 PG MemoryContext 分配/释放链路信手捏来的话, 很容易根据这个特征反推当时发生了什么: `freelist[3] = 0x709240 <AllocSetMethods>` 意味着 0x7fe20cc44000 曾经出现在 `freelist[3]` 中; `freelist[3]` 存放着长度为 64 字节的 free AllocChunk, 这些 AllocChunk 通过 AllocChunk::aset 字段连成一个单链表. 之后别人调用了 palloc(size), 32 < size <= 64, 即对应着 `freelist[3]`. 此时如代码所示:

```C
// 这里 fidx = 3
// 此时 AllocSetAlloc 会从 freelist[3] 取出 0x7fe20cc44000, chunk = 0x7fe20cc44000;
// 这里 AllocSetAlloc 认为 0x7fe20cc44000 是个 free AllocChunk
chunk = set->freelist[fidx];
if (chunk != NULL)
{
    Assert(chunk->size >= size);

    // 并将 chunk->aset, 即 AllocSetAlloc 认为的下一个 free AllocChunk,
    // 但实际上是 `((AllocSetContext*)0x7fe20cc44000)->methods`
    // 写入到 freelist[3] 中, 这导致了 freelist[3] 变为了 `0x709240 <AllocSetMethods>`.
    set->freelist[fidx] = (AllocChunk) chunk->aset;

    // 这导致了 `((AllocSetContext*)0x7fe20cc44000)->methods` 被赋值为了 0x7fe20cc44000
    chunk->aset = (void *) set;
}
```

那么为什么 0x7fe20cc44000 会出现在 `freelist[3]` 中呢? 一种可能是 double pfree, 比如如下链路:

1. pfree(p1), p1 是之前 palloc(size1), 32 < size1 <= 64 的返回值; 此时 pg 会把 p1 放入 `freelist[3]` 中,
2. pfree(p1), double pfree, 此时 pg 会把 p1 再次放入 `freelist[3]` 中,
3. p2 = palloc(size2), 32 < size2 <= 64, 此时 p2 = p1, AllocSetAlloc 执行了 `chunk->aset = (void *) set`, 即 `chunk->aset = 0x7fe20cc44000`.
4. p3 = palloc(size3), 32 < size3 <= 64, 此时 p3 = p1, AllocSetAlloc 执行了 `set->freelist[fidx] = (AllocChunk) chunk->aset`, 将 0x7fe20cc44000 写入到了 `freelist[3]` 中.

同理 MemoryContextReset 之后再 pfree 也会导致类似的情况. 我个人认为我们同学应该不会犯 double pfree 这种愚蠢问题, 不过 MemoryContextReset 之后再 pfree 比较隐晦, 倒是很有可能. 之前做 Greenplum 时也遇到过类似情况. 我个人一直不太喜欢 PG MemoryContext 设计, 太过于不直观; 之前也给 Greenplum 修复过 MemoryContext 导致的 memory leak, crash 问题; 如 [Fix memory leak in ao_truncate_replay](https://hidva.com/g?u=https://github.com/greenplum-db/gpdb/pull/11210) 等.

老规矩, 遇到内存相关 crash, 我一般习惯先用 [jegdb.py](https://hidva.com/g?u=https://github.com/hidva/hidva.github.io/blob/dev/_drafts/jegdb.py) 看下 jemalloc 对相关地址维护的 metadata 是否自洽:

```bash
>>> hex(int(jegdb.rtree_leaf_elm_bits_extent_get(int(jegdb.rtree_lookup(0x7fe20cc44000))).address))
'0x7fe2da83a180'
>>>
# 0x7fe2da83a180 是地址 0x7fe20cc44000 对应的 extent 结构, jemalloc 使用这个结构记录相关元信息.
(gdb) p *(struct extent_s*)0x7fe2da83a180
$5 = {
  e_bits = 8796101472256,
  e_addr = 0x7fe20cc44000,
  {
    # jemalloc 认为 0x7fe20cc44000 是个 8192 字节的内存块, 符合预期
    e_size_esn = 8192,
    e_bsize = 8192
  },
  {
    # 下面 slab = 1, szind = 32, 即这个内存块用于承担 8192 这个 small size class 的内存分配
    # bitmap 全 0 意味着 0x7fe20cc44000 尚未 free. 符合预期
    e_slab_data = {
      bitmap = {0, 0, 0, 0, 0, 0, 0, 0}
    },
  }
}
(gdb) pi
>>> jegdb.desc_e_bits(8796101472256)
arena_ind = 0
slab = 1
committed = 1
dumpable = 1
zeroed = 1
state = 0
szind = 32
nfree = 0
bin_shard = 0
sn = 2
```

从 jemalloc metadata 看没啥问题, 导致 crash 最有可能的原因还是 "MemoryContextReset 之后再 pfree" 这一项了; 意味着某处曾经持有了从 MemoryContext 0x7fe20cc44000 中 palloc(size) 分配出来的地址 p, 32 < size <= 64, 之后在 MemoryContext 0x7fe20cc44000 Reset 之后又 pfree(p). p 的取值范围在 `[0x7fe20cc44000 + 0x100 + 0x10, 0x7fe20cc44000 - 0x40]` 间. 用 jegdb.find 在内存中找下 p 曾经在哪些内存处出现过吧:

``` python
# jegdb.find 会在 arena_ind 对应 arena 分配的所有内存块, 按照 sizechar 指示解释内存块,
# 比如 `+8` 意味着将内存块视为 `unsigned long`, `-4` 意味着将内存块视为 `signed int`,
# 之后若解释后内存的值位于 [left, right] 范围内, 则保存该处内存的地址并返回.
# arena_ind = None 会在所有 arena 分配的内存块中寻找.
# 这里我们使用 arena_ind = 0 即可, 并且 PG 是单线程进程; 但考虑到我们加了好多多线程逻辑, 不确定
# 是否是其他线程行为导致的, 索性 arena_ind = None
>>> jegdb.find(left=0x7fe20cc44000 + 0x100 + 0x10, right=0x7fe20cc46000 - 0x40, sizechar=+8, arena_ind=None)
[..., 140338785644640, 140608853524488, 140608853524552, ...]
```

经过漫长的反复查找...

```python
>>> hex(140338785644640)
'0x7fa32b777060'
# find_alloc_chunk_header 会从 addr 向低地址遍历, 试图找到 addr 所对应 AllocChunk header
>>> find_alloc_chunk_header(addr=0x7fa32b777060)
140338785644624
>>> hex(140338785644624)
'0x7fa32b777050'
(gdb) x/2xg 0x7fa32b777050
0x7fa32b777050:	0x0000000000000010	0x00007fa32b76a000
(gdb) p *(AllocSetContext*)0x00007fa32b76a000
$6 = {
  header = {
    type = T_AllocSetContext,
  }
  # ...
}
(gdb) x/xg 0x7fa32b777060
0x7fa32b777060:	0x7fe20cc44110
```

顺着上面思路继续逆着查找...

```
>>> jegdb.find(0x7fa32b777060,0x7fa32b777060, 8)
[140338785644616]
(gdb) p/x 140338785644616
$9 = 0x7fa32b777048
>>> find_alloc_chunk_header(0x7fa32b777048)
140338785644600
>>> hex(140338785644600)
'0x7fa32b777038'
(gdb) x/2xg 0x7fa32b777038
0x7fa32b777038:	0x0000000000000008	0x00007fa32b76a000
```

继续...

```
>>> jegdb.find(0x7fa32b777048,0x7fa32b777048, 8)
[140338785592936, 140338785592976]
(gdb) p/x 140338785592936
$10 = 0x7fa32b76a668
(gdb) p/x 140338785592976
$11 = 0x7fa32b76a690
>>> hex(find_alloc_chunk_header(0x7fa32b76a668))
'0x7fa32b76a500'
>>> hex(find_alloc_chunk_header(0x7fa32b76a690))
'0x7fa32b76a500'
(gdb) x/2xg 0x7fa32b76a500
0x7fa32b76a500:	0x0000000000000200	0x00007fa32b76a000
(gdb) p *(Node*)0x7fa32b76a510
$17 = {
  type = T_AggState
}
(gdb) p *(AggState*)0x7fa32b76a510
```

AggState!!! 总算碰到一个比较眼熟的了; 之前给 Greenplum 做 [FastDecimal TPCH 打榜]({{site.url}}/2020/01/16/optimizer/)时对 PG/GP Agg 链路略有涉猎; 众所周知, AggState 中维护着多个 ExprContext, 并且各自具有不同的生命周期, 比如 tmpcontext 会在每一行之后 reset, aggcontexts 的生命周期会稍微长一点等. 这估计又是谁在实现 Agg 时错误地使用了 ExprContext, 根据 AggState 中的信息最终找到了是某个三方插件创建 transvalue 时, 将 transvalue 放在了 tmpcontext 中, 而 tmpcontext 每一行之后 Reset, 但同时这个第三方插件在 final 阶段又 pfree transvalue 导致的问题.

## 后语

还是挺幸运的, 这个 crash 现场还比较新, 内存中的痕迹大部分都还在, 还有迹可循... 但实际上也是走了很多地弯路, 尝试了各种姿势.
