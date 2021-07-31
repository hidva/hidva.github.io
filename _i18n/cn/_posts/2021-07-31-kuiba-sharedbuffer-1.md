---
title: "深入浅出 KuiBaDB: 使用 SharedBuffer"
hidden: false
tags: ["KuiBaDB"]
---

在 2021-07-04 23:47 的时候, KuiBaDB 正式跑通了 COPY 链路, 第一次串通了 MVCC, SharedBuffer, Column Storage, SuperVersion 等模块. 本文是 "从 KuiBaDB SharedBuffer 到 Linux address_space" 系列第一篇.

截止目前为止, KuiBaDB 中最让我觉得有趣的便是 SharedBuffer. KuiBaDB SharedBuffer 基于 PostgreSQL shared buffer 组件对应的原理实现. SharedBuffer 类似于 Linux 的 Page Cache, 通过对磁盘上的数据, 在内存中建立一个局部 cache 来加速对磁盘上数据的访问. SharedBuffer 在内存中的 cache 类似于一个具有最大容量限制的 `HashMap<K, V>`. 当用户请求获取 k 对应的 value 时, SharedBuffer 会首先查看内存中的 HashMap 中是否已经有了 k, 若有, 则意味着 k 对应的磁盘内容已经缓存在内存中, 此时将内存 cache 中对应的值直接返回用户. 避免从磁盘中读取. 若内存中 HashMap 找不到 k, 则意味着 k 对应的值尚在磁盘中, 并未加载进来. 此时会首先查看 HashMap 是否已经到达最大容量限制, 若是, 则意味着我们应该首先将某些内容从内存中 cache 淘汰出去, 此时若这些被淘汰项已经在内存中被更改过, 则会首先将最新内容持久化到磁盘之后, 再从内存 cache 中移除出去. 之后将 k 的值从磁盘中加载到内存并返回给用户.

SharedBuffer 被用在 PostgreSQL 很多模块中. 比如 heap table 内容的管理, PG 将 heap table 按照 BLCKSZ 大小切分为若干 block, 每 RELSEG_SIZE block 对应着一个物理文件. 因此对于 heap table, 当给定其内一个 block number N 时, 便可通过 `N / RELSEG_SIZE` 得到其所在文件, 通过 `(N % RELSEG_SIZE) * BLCKSZ` 得到其在文件内的偏移. 在 PG 中用于管理 heap table 的 shared buffer bufmgr.c 中, Key 便是 block number N, value 便是 block number 对应 block 的内容. 当其他模块请求获取 block number N 对应的内容时, PG 这里会首先查看 N 是否已经在 bufmgr.c 管理的 shared buffer 中, 若在则直接返回. 否则, 则将 N 对应内容从磁盘中加载到 bufmgr.c 管理的 shared buffer 中. 除此之外, 在 clog, pg_subtrans 等组件中, 也使用了 shared buffer 思想进行管理. clog, pg_subtrans 基于 PG slru.c 模块构建, 类似于 bufmgr.c 管理的 share buffer 是对 heap file 等文件在内存中的 cache 一样. slru.c 同样使用了 SharedBuffer 思想实现了另外一些文件的 cache. 这些文件按照固定大小(BLCKSZ)分隔成块, 固定数目(SLRU_PAGES_PER_SEGMENT)的块会组织成一个 segment, 一个 segment 对应着一个物理文件, 归属于同一类的 segment 所包含的块(又称为 page)会被编号(一般是从 0 开始), 即 slru 接口中常见的 pageno. 根据 pageno 可以定位 pageno 所在文件路径, 以及在文件中的偏移:

```c++
segno = pageno / SLRU_PAGES_PER_SEGMENT;
filepath = sprintf("%s/%04X", SlruCtlData::Dir, segno);
fileoff = (pageno % SLRU_PAGES_PER_SEGMENT) * BLCKSZ;
```

在 slru.c 管理的 shared buffer 中, Key 便是 pageno, Value 则是 pageno 对应 page 的内容. 可以看到这里 slru.c, bufmgr.c 功能相似, 如果在 C++ 中, 我们可能会使用一个模板类 `SharedBuffer<K, V>`, 之后 slru 使用 `SharedBuffer<Pageno, Page>`, 而 bufmgr 使用 `SharedBuffer<BlockNo, Block>`. 很明显 PostgreSQL 没有这么做, 在 slru.c, bufmgr.c 中具有很多功能相似的重复代码. 而且 PG 结合了 slru.c 的使用场景, 并没有像 bufmgr.c 中, 为 shared buffer 中每一项搞个细粒度锁, slru.c 管理的 shared buffer 中, 为了省事只用了一把大锁, 即访问 slru.c shared buffer 中不同的项这一行为也会被串行化.

KuiBaDB 中, 参考了 bufmgr.c shared buffer 的链路, 将 SharedBuffer 模板化实现, 并作为一个公共组件, 可被其他模块使用. SharedBuffer 定义:

```rust
// V, 定义了要交由 SharedBuffer 管理的值类型.
// E, 定义了 SharedBuffer 内项的淘汰策略.
// 即当 shared buffer 到达最大容量限制时, 该选择哪些项从 shared buffer 中淘汰出去.
// 当前 sb.rs 中已经内置了一些淘汰策略, 可直接使用.
pub struct SharedBuffer<V: Value, E: EvictPolicy> {
    //...
}

impl<V: Value, E: EvictPolicy> SharedBuffer<V, E> {
    // 获取 k 对应的项. 这里若 k 已经在内存中, 则直接返回. 否则会调用 Value::load() 接口从磁盘中加载.
    // 若 k 尚未在内存中, 并且 shared buffer 已经到达最大容量, 则此时会按照 E 指定的策略, 选择一个被
    // 淘汰的项, 若该项在内存中被修改过, 则首先调用 Value::store() 将该项写入到磁盘, 之后从 shared buffer
    // 中移除该项.
    pub fn read(&self, k: &V::K, loadctx: &V::LoadCtx) -> anyhow::Result<SlotPinGuard<V, E>>;

    // 将 shared buffer 中所有在内存中被修改的项调用 Value::store() 写入到磁盘中.
    // 一般在 checkpointer 中使用该接口.
    pub fn flushall(&self, force: bool) -> anyhow::Result<()>
}

pub trait Value: std::marker::Sized {
    type LoadCtx;
    type CommonData;
    type K: SBK;
    fn load(k: &Self::K, ctx: &Self::LoadCtx, dat: &Self::CommonData) -> anyhow::Result<Self>;
    fn store(&self, k: &Self::K, ctx: &Self::CommonData, force: bool) -> anyhow::Result<()>;
}
```

在后来 linux 内核学习中, 可以看到与 KuiBaDB SharedBuffer 功能最类似的 linux address_space 也是采用了类似的做法, linux address_space 被用作 swap cache, page cache 等众多组件中. address_space 通过函数指针实现了模板类似的效果:

```c++
struct address_space {
    /* ... */
    struct address_space_operations *a_ops;
}

struct address_space_operations {
    // 类似于 Value::store()
    int (*writepage)(struct page *page, struct writeback_control *wbc);
    // 类似于 Value::load()
    int (*readpage)(struct file *, struct page *);
    /* ... */
}
```

KuiBaDB SharedBuffer 当前被用在 KuiBaDB 多个组件中, 比如用作 SuperVersion 的管理, 用在 MVCC 的管理, 以及用作 slru 的底层实现等, 关于 SharedBuffer 的使用参考这些模块的使用姿势即可, 这里不做过多介绍. 之前说过 PG slru.c 由于为了省事, 直接使用了一把大锁来管理 slru.c 所有项, 使得访问不同项的操作会被串行化, 也正是由于串行化, 使得 PG 在事务提交标记 clog 时不得不引入 group commit 来降低锁冲突, 提升事务吞吐量. 而在 KuiBaDB 中, slru 背后使用了 SharedBuffer 作为底层实现, SharedBuffer 为其内管理的每一项引入了细粒度读写锁. 同时参考了 PG write hint 链路的思想, KuiBaDB SharedBuffer 支持在受限的场景内, 在仅持有着项的 read lock 时更改项的内容. 基于 KuiBaDB SharedBuffer 提供的能力, 结合原子 CAS 操作, KuiBaDB 支持并行地在 clog 中标记事务提交状态的操作:

```rust
self.g.d.writable_load(xid_to_pageno(xid), |buff| {
    let byteval = &buff.0[byteno];
    let mut state = byteval.load(Relaxed);
    loop {
        let newstate = (state & andbits) | orbits;
        let res = byteval.compare_exchange_weak(state, newstate, Relaxed, Relaxed);
        match res {
            Ok(_) => break,
            Err(s) => state = s,
        }
    }
})
```

关于 clog 的细节, 以及这里代码每一行的意义会在另一篇文章中介绍.
