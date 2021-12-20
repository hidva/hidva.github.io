---
title: "C++ memory order: load(SeqCst) VS fetch_add(0, SeqCst)"
hidden: false
tags:
 -
   "JustForFun"
---

在阅读 tokio 代码时, 发现一个很奇怪的地方, fetch_add(0):

```rust
let state = State(self.state.fetch_add(0, SeqCst));
```

就很好奇为啥不是直接 `load(SeqCst)`, 还要 fetch_add(0) 一把? 翻了下修改历史, 背后原来是有[故事](https://github.com/tokio-rs/tokio/issues/1768)的, 简单来说就是这块代码一开始就是 load(SeqCst) 的, 后来发现会导致一个很奇怪的 bug, 所以特意改成了 fetch_add(0), 但却(我)没说(看)清(懂)为啥改了 fetch_add(0) 就没有问题了. 考虑到 rust 使用了C++ 定义的 memory model, 特意翻了之前的 [从 C++20 标准来看 memory order: 1]({{site.url}}/2020/09/15/cpp20-memory-order-1/) 找到了一个可能的解答:

> An implementation should ensure that the last value (in modification order) assigned by an atomic or synchronization operation will become visible to all other threads in a finite period of time. Implementations should make atomic stores visible to atomic loads within a reasonable amount of time.
>
> Atomic read-modify-write operations shall always read the last value (in the modification order) written before the write associated with the read-modify-write operation.

即 Load() 不保证能看到最新值, 但是 Read-Modify-Write 会保证能看到最新值. 回到 tokio 这个场景, 在之前使用 Load 的版本中会存在如下会导致 bug 的时序, 导致了 thread1.1 创建的 task 永远不会执行:


```
thread1                     thread2
                        1. cell.fetch_sub(1, SeqCst), 退出 search 状态, 此后 cell = 0
                        2. 在检查一次有没有 task 要干, 没有则 go to sleep.

1. 创建一个 task 扔到执行队列中.
1. cell.load(0, SeqCst), 看到的 cell 仍然是 1!
   所以认为 thread2 还没有执行 fetch_sub 退出
   search 状态, 认为第 1 步创建的 task 能被
   thread2.2 看到,
```

好奇看了下 fetch_add(0), load() 在 x86 上的汇编表示:

```
load():                               # @load()
        mov     rax, qword ptr [rip + z]
        ret
fetch_add0():                        # @fetch_add0()
        mfence
        mov     rax, qword ptr [rip + z]
        ret
```

由于 x86 提供了 strong hardware memory model, 所以其 load(SeqCst) 仅是一条普通的 mov 指令, 确实有可能会看不到哪些仍位于其他 CPU store buffer 等处的修改. 但 fetch_add(0) 则会先 mfence 同步一下, 确保接下来的 mov 能看到其他 CPU 修改的最新值. 相关细节感兴趣地可以参考 [你应该了解的 memory barrier 背后细节]({{site.url}}/2018/12/05/whymb/).

到了此处, 忽然想到 io-uring 中也存在类似的现象, 当开启 SQ poll thread 时, liburing 使用 load(Relaxed) 语义来读取 kernel sq poll thread 是否设置了 IORING_SQ_NEED_WAKEUP. 所以会不会有一种情况, kernel sq poll thread 设置了 need wakeup, 但 liburing load(Relaxed) 由于看到的不是最新值而认为 sq poll thread 并未 sleep...
