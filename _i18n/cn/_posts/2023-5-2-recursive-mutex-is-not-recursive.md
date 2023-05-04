---
title: "递归锁并不递归"
hidden: false
tags: ["C++"]
---

日常测试时遇到了一个死锁堆栈, 堆栈很明确, 就是异常机制与 hos 信号内抓栈机制死锁了, 关于 hos 信号内抓栈机制可以参见 [backtrace() crash: 从 CFI 说起]({{site.url}}/2022/09/04/clangbug-cfi/) 了解相关背景.

```
#0  0x00007fa122b99f4d in __lll_lock_wait () at /lib64/libpthread.so.0
#1  0x00007fa122b95d1d in _L_lock_840 () at /lib64/libpthread.so.0
#2  0x00007fa122b95c3a in pthread_mutex_lock () at /lib64/libpthread.so.0
#3  0x00007fa1228fb3df in dl_iterate_phdr () at /lib64/libc.so.6
#12 0x00007fa125532a11 in unw_backtrace (buffer=0x61c000150360, size=64) at mi/backtrace.c:69
#13 0x00007fa1247447bd in backtrace () at /apsara/alicpp/built/clang-13/clang-13/lib64/clang/13/lib/libclang_rt.asan-x86_64.so
#18 0x00007fa122b9b100 in <signal handler called> () at /lib64/libpthread.so.0
#19 0x00007fa122b99f4d in __lll_lock_wait () at /lib64/libpthread.so.0
#20 0x00007fa122b95d1d in _L_lock_840 () at /lib64/libpthread.so.0
#21 0x00007fa122b95c3a in pthread_mutex_lock () at /lib64/libpthread.so.0
#22 0x00007fa1228fb3df in dl_iterate_phdr () at /lib64/libc.so.6
#26 0x00007fa122db883e in _Unwind_RaiseException (exc=0x60d000030fe0) at ../../../libgcc/unwind.inc:93
#27 0x00007fa123350b86 in __cxa_throw () at /usr/local/lib64/libstdc++.so.6
#28 0x000000000042a25e in TestThrow(int) (i=21) at ../../cpp_coro/holo/hos/common/test/stack_trace_test.cc:40
```

但问题很奇怪, 因为当时确认过 dl_iterate_phdr 内使用的锁是 recurisve lock, 按理说不应该出现上图堆栈式死锁.

```C
int
__dl_iterate_phdr (int (*callback) (struct dl_phdr_info *info,
            size_t size, void *data), void *data)
{
  __rtld_lock_lock_recursive (GL(dl_load_write_lock));  // dl_load_write_lock 是 pthread recursive lock
  // ...
}
```

看了下 dl_load_write_lock 当时状态, 有点奇怪: `__lock=2` 意味着某次 pthread_mutex_lock(l) 发现 l 当前已经被人持有了, 于是将 l.__lock 状态改为 2 表明当前 l 上有 waiter, 但此时 owner 应该记录着持有锁 tid, 而不应该是 0.

```c
$2234 = {
  __data = {
    // 0 表明锁未被任何人持有.
    // 1 表明锁被持有着, 但没有 waiter.
    // 2 表明锁被持有着, 与此同时, 有一些 waiter 在等待着锁.
    __lock = 2,
    __count = 0,
    __owner = 0,  // owner 记录着持有着 tid. 0 表明锁未被任何人持有.
    __nusers = 0,
    __kind = 1,  // kind=1, 意味着这确实是个 recursive mutex
    __spins = 0,
    __list = {
      __prev = 0x0,
      __next = 0x0
    }
  }
}
```

分析了下 pthread_mutex_lock recursive 时实现, 简化如下, 明显可见, pthread recursive lock 支持递归, 但不支持重入...

```c
// 这里执行加锁逻辑. 即 CAS mutex.__lock 从 0 到 1, 在必要时调用 futex 等待.
// 当 LLL_MUTEX_LOCK_OPTIMIZED 返回时, 意味着当前线程成功将 mutex.lock 置为了 1,
// 即当前线程拿到了锁.
LLL_MUTEX_LOCK_OPTIMIZED (mutex);
assert (mutex->__data.__owner == 0);
mutex->__data.__count = 1;  // 在这里收到信号, 进入信号处理函数, 再次加锁, 便会陷入如上堆栈式死锁.
mutex->__data.__owner = id;
```


后续关于 '异常机制' 与 'hos 信号内抓栈机制' 死锁的解法, 根据 itanium ABI 中关于异常机制实现的规范, 结合 llvm/gcc 对这套规范的实现, 可以看到在 `throw Exception` 时会首先递增 `std::uncaught_exceptions`, 之后才会做 stack unwinding. 所以我们的抓栈逻辑加了针对 std::uncaught_exceptions 的判断, 仅当 uncaught_exceptions == 0 时才抓栈, 这样便能规避掉死锁.
