---
title: "C++ 异常与 longjmp"
hidden: false
tags: ["C++"]
---

在解决这个 [C++ 异常与抓栈死锁]({{site.url}}/2023/05/02/recursive-mutex-is-not-recursive/) 问题时, 调研了 C++ 异常机制实现, 看到 C++ ABI 中提到了一嘴:

> "forced" unwinding (such as caused by longjmp or thread termination).

有点惊喜, 这正好能解决一个困扰我们很久的一个问题.

## 问题

首先介绍下 PostgreSQL 中的异常处理机制, PG 基于 setjmp/longjmp 实现了错误处理, 其大概姿势:

```c++
// PG_TRY 会使用 setjmp() 注册一个 jmpbuf, 保存在全局变量 PG_exception_stack 中.
PG_TRY();
{
  // elog(ERROR) 负责抛出异常, 其会执行 longjmp(PG_exception_stack)
  elog(ERROR, "...");
  // ...
}
PG_CATCH();  // setjmp 另一个分支.
{
  // 这里对应着 setjmp 另一个分支, elog(ERROR) longjmp 之后, 控制流指向这里.
  // ...
}
PG_END_TRY();
```

这套机制在 C 语言背景下工作地很好, 但当和 C++ 结合在一起使用时, 就有了问题: elog(ERROR) 触发的 longjmp 不会执行 stack unwinding, 导致 C++ 局部变量的析构无法执行:

```c++
const char* f() {
  auto str = std::string("do you wanna build a snowman");
  // 如果 relation_open 调用链中某处执行了 elog(ERROR),
  // 此时触发的 longjmp 会跳出 f 之外, 导致 str 的析构函数不会执行, 导致内存泄漏.
  auto ret = relation_open(relid, AccessShareLock);
}
```

PG 自身文档也特别说明了:

> If calling backend functions from C++ code, be sure that the C++ call stack contains only plain old data structures (POD).  This is necessary because backend errors generate a distant longjmp() that does not properly unroll a C++ call stack with non-POD objects.

目前在 Greenplum 中, 其优化器 ORCA 是通过 C++ 编写, GP 是通过一个 wrapper 层来隔离 C/C++ 边界, 所有可能会被 ORCA 访问的 PG C 接口都必须通过 wrapper 来调用, 如 gpdbwrappers.cpp 文件所示:

```c++
void
gpdb::FreeAttrStatsSlot(AttStatsSlot *sslot)
{
  // GP_WRAP_START 等同于 PG_TRY.
  GP_WRAP_START;
  {
    free_attstatsslot(sslot);
    return;
  }
  // GP_WRAP_END 等同于 PG_CATCH, 会将抓到的 elog(ERROR) 转化为 C++ throw 语句.
  GP_WRAP_END;
}
```

## longjmp 触发 stack unwind

如果我们能让 longjmp 触发一次栈展开，从而完成 C++ 局部变量的析构，那么在 PostgreSQL 中使用 C++ 就会变得简单许多，而且 gpdbwrappers.cpp 和其定义的 wrap 也就不再必要了。幸运的是，C++ ABI 定义了 _Unwind_ForcedUnwind 接口，可以实现这一功能，正如其举例所示：

> Example: longjmp_unwind()
>
> The expected implementation of longjmp_unwind() is as follows. The setjmp() routine will have saved the state to be restored in its customary place, including the frame pointer. The longjmp_unwind() routine will call _Unwind_ForcedUnwind with a stop function that compares the frame pointer in the context record with the saved frame pointer. If equal, it will restore the setjmp() state as customary, and otherwise it will return _URC_NO_REASON or _URC_END_OF_STACK.

另外 pthread_exit 也是利用 _Unwind_ForcedUnwind 实现, 毕竟在 pthread 终止线程时, 其不确定其线程栈上是否有 C++ 栈, 是否有 C++ 局部变量析构需要执行. 与 PG 这里情况更相似的是 pthread_cleanup_push/pthread_cleanup_pop, pthread_cleanup_push 在 C++ 环境中是通过局部变量来实现, 在 C 环境是通过 setjmp/longjmp 实现的, 如:

```c
#ifdef __cplusplus
#  define pthread_cleanup_push(routine, arg) \
  do {									      \
    __pthread_cleanup_class __clframe (routine, arg)
#else
# define pthread_cleanup_push(routine, arg) \
  do {									      \
    __pthread_unwind_buf_t __cancel_buf;				      \
    void (*__cancel_routine) (void *) = (routine);			      \
    void *__cancel_arg = (arg);						      \
    int __not_first_call = __sigsetjmp_cancel (__cancel_buf.__cancel_jmp_buf, \
					       0);			      \
    if (__glibc_unlikely (__not_first_call))				      \
      {									      \
	__cancel_routine (__cancel_arg);				      \
	__pthread_unwind_next (&__cancel_buf);				      \
	/* NOTREACHED */						      \
      }									      \
									      \
    __pthread_register_cancel (&__cancel_buf);
#endif
```

在 pthread_exit 时, 通过调用 _Unwind_ForcedUnwind 完成了栈上注册的所有 cleanup handler 的执行. 参考着 pthread_exit 中代码, longjmp 时执行 stack unwind 逻辑也不是很复杂, 20 行代码左右, 完整代码可参考 [pg_siglongjmp, pg_sjlj_unwind_stop](https://github.com/postgres/postgres/commit/1a9a2790430f256d9d0cc371249e43769d93eb8e).

这里遗留一个问题, 即 'TODO old pthread cleanup handle'. 设想我们在栈 SP1 中执行 setjmp, 在栈 SP2 中执行了 longjmp 跳回到 SP1, 此时 glibc 会调用 pthread_cleanup_upto 清理 [SP1, SP2] 期间注册的 pthread old cleanup handler; 如果我们将 longjmp 改为 pg_siglongjmp, 此时会执行 stack unwind, 使得 longjmp 最终也是在 SP1 栈上执行的, 导致一些 pthread old cleanup handler 不会执行. 这个问题可以解, 目前看没有解的必要, 主要是这个 pthread old cleanup handle 不是上面所说 pthread_cleanup_push 注册的 cleanup, 是一种很老的, 已经废弃了的 handle, 这种 old cleanup 通过 '_pthread_cleanup_push_defer' 注册, 目前互联网上已经找不到关于它的资料了..

## uncaught exception 到 longjmp

众所周知, C++ 未关联到 catch 的异常会触发 std::terminate 调用终止当前进程; 在对 C++ ABI 中异常处理流程有所了解之后, 在 PG 这个背景下, 我们可以在遇到 C++ uncaught exception 之后, 不触发 terminate, 而是将控制流转向最近的 PG_TRY 处, 即在此之后 PG_TRY 行为上就等同于 C++ try 语句了. 这样便能避免 uncaught exception 导致进程终止. 这块实现逻辑很简单:

```c++
// 如 ABI 规定: _Unwind_RaiseException 是 throw/std::rethrow_exception/rethrow 的入口
_Unwind_Reason_Code _Unwind_RaiseException (struct _Unwind_Exception *e)
{
  static auto orig_func = reinterpret_cast<decltype(&_Unwind_RaiseException)>(dlsym(RTLD_NEXT, "_Unwind_RaiseException"));
  _Unwind_Reason_Code ret = orig_unwind(e);
  // At this point, the exception thrown by C++ does not have a corresponding catch handler.
  if (!pthread_equal(pthread_self(), MyPthreadId))
    return ret;  // 非 PG 主线程抛出的异常, 不做处理, 仍会触发 std::terminate
  elog(ERROR, "uncaught exception. stacktrace=%s", current_stack_trace().c_str());
  // elog(ERROR) 会触发 longjmp 到最近的 PG_TRY
  // 这里会输出 uncaught exception 对应的堆栈, 对应 uncaught exception 处理原则还是抓到一个修复一个.
  abort();
  return ret;
}
```
