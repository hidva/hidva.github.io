---
title: "C++ 异常与 longjmp: 尘埃落定"
hidden: false
tags: ["C++"]
---

站在代码终于成功合入的背景下, 开始心平气和地回顾整个 C++ 异常与 longjmp 开发过程中一些细节. 系列文章:

- [C++ 异常与 longjmp: 缘起]({{site.url}}/2023/05/08/cppexception/)
- [C++ 异常与 longjmp: 没有想象中那么美好]({{site.url}}/2023/05/22/cppexception2/)
- [C++ 异常与 longjmp: 比想象中还要遭]({{site.url}}/2023/05/23/cppexception3/)
- [C++ 异常与 longjmp: 尘埃落定]({{site.url}}/2023/05/29/cppexception4/)

## Catch force unwind

如 [这里]({{site.url}}/2023/05/22/cppexception2/#catch-all) 所示, 一开始我们虽然支持 catch force unwind, 但要求必须要 rethrow, 不然会碰到我们主动检测逻辑, 会 abort:

```c++
static void pg_sjlj_ex_cleanup(_Unwind_Reason_Code _c, struct _Unwind_Exception *_e)
{
  // 如果你 core 在这里, bt 看下当前堆栈, 看下你的栈顶函数是否有个
  // catch (...) {  }
  // 其中 catch ... 中未 rethrow 异常, 这是个很不好的编程习惯, 在 catch ... 中加个 rethrow 就可以修复
  // 这个 core.
  abort();
}
```

首先 `catch(...)` 但不 throw 确实是个不好的习惯, 这会导致同样基于 force unwind 实现的 pthread_exit 也无法正常工作:

```c++
void *print_numbers(void *arg) {
  try {
    pthread_exit(NULL);
  } catch (...) {
    return NULL;  // 触发 pthread_exit 'FATAL: exception not rethrown', 之后 abort.
  }
  return NULL;
}

int main() {
    pthread_t thread1;
    pthread_create(&thread1, NULL, print_numbers, NULL);
    pthread_join(thread1, NULL);
    return 0;
}
```

另外 C++ Exception Handle ABI 规范也强调 force unwind 总应该被 rethrow, 不应该被 catch 吞掉:

> A runtime is not allowed to catch an exception if the _UA_FORCE_UNWIND flag was passed to the personality routine. During phase 2, indicates that no language is allowed to "catch" the exception. This flag is set while unwinding the stack for longjmp or during thread cancellation. User-defined code in a catch clause may still be executed, but the catch clause must resume unwinding with a call to _Unwind_Resume when finished.

但我们目前还是有一些 `catch(...)` 但是却没 rethrow 的, 所以策略不得不调整为先支持不带 rethrow 的 `catch(...)`, 之后再慢慢给那些 `catch(...)` 加上 rethrow, 最后再禁止掉这种支持. 如下我们总结下 pg_sjlj_ex_cleanup 中必须要做的一些清理逻辑:

### error_context_stack

error_context_stack 必须置为 NULL. 当 pg_sjlj_ex_cleanup 执行时, error_context_stack 中的回调已经执行了, 此时应该另 error_context_stack = NULL 避免二次执行. 不然设想如下代码:

```c++
try {
  // SPI_execute 内部会注册一个 error context cb _SPI_error_callback,
  // 如果在注册 cb 之后触发了 elog(ERROR), 此时会执行一下 _SPI_error_callback
  SPI_execute();
} catch (...) {
  // elog(ERROR) 之后, 流程走到这里.
}
// elog(WARN) 也会触发 error_context_stack 执行, 如果 pg_sjlj_ex_cleanup 未
// 令 error_context_stack = NULL, 会导致这里再次执行 _SPI_error_callback, 可能会 use-after-free
elog(WARN, "hello");
```

### FlushErrorState

FlushErrorState 也必须调用, 想象如下场景:

```c++
TEST_F(HgElogUnitTest, CatchLongjmp) {
  PG_TRY();
  {
    for (int i = 0; i < 32; ++i) {
      try {
        // 这里会递增 errordata_stack_depth
        elog(ERROR, "CatchLongjmp i=%d", i);
      } catch (...) {
        std::cerr << "catch CatchLongjmp. i=" << i << std::endl;
        // pg_sjlj_ex_cleanup() 在这里调用, 如果此时不重置 errordata_stack_depth,
        // 会导致 errordata_stack_depth 一直递增, 触发 PANIC:
        // `ereport(PANIC, (errmsg_internal("ERRORDATA_STACK_SIZE exceeded")));`
      }
    }
  }
  PG_CATCH();
  { abort(); }
  PG_END_TRY();
}
```

同理既然调用了 FlushErrorState(), 那么也别忘了先将 errordata 栈上最顶层 error log 输出到文件中, 不然就导致 error log 莫名丢失, 增大问题排查难度. 但此时并不能调用 EmitErrorReport 来将 error log 输出到文件, 因为 EmitErrorReport 会将 error data 发送给 client, 可能会污染连接中的数据流. 而且这种被 Catch 的 `elog(ERROR)` 也没必要给用户看了.

### nested force unwind

还记得我们之前做的 [uncaught exception 到 longjmp]({{site.url}}/2023/05/08/cppexception/) 这个功能么?

> C++ 未关联到 catch 的异常会触发 std::terminate 调用终止当前进程; 在对 C++ ABI 中异常处理流程有所了解之后, 在 PG 这个背景下, 我们可以在遇到 C++ uncaught exception 之后, 不触发 terminate, 而是将控制流转向最近的 PG_TRY 处, 即在此之后 PG_TRY 行为上就等同于 C++ try 语句了. 这样便能避免 uncaught exception 导致进程终止.

想象一个如下场景:

```c++
PG_TRY();
{
  try {
    elog(ERROR, "hello");
  } catch (...) {
    throw std::runtime_error("oh");
  }
}
PG_CATCH();
{
  auto* ed = CopyErrorData();  // #2
  FreeErrorData(ed);  // make ED away
}
PG_END_TRY();
```

这里执行流是:

1. `elog(ERROR, "hello")` 触发 force unwind, 被 `catch(...)` 抓住, 针对如上 `catch(...)` 编译器生成的代码类似:

   ```c++
   __cxa_begin_catch(e);
   SCOPE_EXIT {
    // 注册一个局部变量, 这个局部变量析构时会执行 __cxa_end_catch.
    __cxa_end_catch();  // #1
   };
   throw std::runtime_error("oh");
   ```

2. throw 没有对应的 catch clause, 会触发到 _Unwind_RaiseException() `elog(ERROR, "oh")`, `elog(ERROR` 会递增 errordata_stack_depth, 之后又会来次 force unwind, 所以会首先执行第 1 部 `#1` 处的 `__cxa_end_catch`, 之后流程走我们的 pg_sjlj_ex_cleanup, 再到 FlushErrorState 将 errordata_stack_depth 重置为 -1.
3. 这导致了我们在 `#2` 处拿不到 ErrorData!

所以 pg_sjlj_ex_cleanup 中并不能无脑执行 errordata_stack_depth, 我们应该引入一个 epoch 概念, 每次 force unwind 递增 epoch, pg_sjlj_ex_cleanup 首先判断其对应的 epoch 与全局 epoch 是否一致, 如果不一致, 表明有 nested force unwind 发生, 此时不应该清理 errordata 栈. 最终实现逻辑:

```c++
static struct _Unwind_Exception pg_sjlj_ex0;
static struct _Unwind_Exception pg_sjlj_ex1;
static struct _Unwind_Exception* pg_sjlj_ex_p = NULL;

void pg_siglongjmp(pg_sigjmp_buf* env)
{
  if (pg_sjlj_ex_p == &pg_sjlj_ex0) {
    pg_sjlj_ex_p = &pg_sjlj_ex1;
  } else {
    pg_sjlj_ex_p = &pg_sjlj_ex0;
  }
  pg_sjlj_ex_p->exception_class = 0;
  pg_sjlj_ex_p->exception_cleanup = &pg_sjlj_ex_cleanup;
  // Triggering a force unwind causes the destruction of C++ local variables to be performed.
  _Unwind_ForcedUnwind(pg_sjlj_ex_p, pg_sjlj_unwind_stop, env);
  abort();
}

static void pg_sjlj_ex_cleanup(_Unwind_Reason_Code _c, struct _Unwind_Exception *_e)
{
  error_context_stack = NULL;
  if (_e != pg_sjlj_ex_p) {  // 表明 nested force unwind 发生.
    return;
  }
  FlushErrorState();
}
```

幸好这里不会有 nested-nested-force-unwind, 不然我们还得整个 pg_sjlj_ex2, pg_sjlj_ex3, ...

## C++ Exception 转换为 errordata

还是 [uncaught exception 到 longjmp]({{site.url}}/2023/05/08/cppexception/) 这个功能, 对于 uncaught exception, 我当时以为我们拿不到此时异常对象详细信息, 所能做的无非就是把抛异常的堆栈打印出来:

```c++
elog(ERROR, "uncaught exception. stacktrace=%s", current_stack_trace().c_str());
// elog(ERROR) 会触发 longjmp 到最近的 PG_TRY
```

后来忽然意识到, 在我们在 [这里]({{site.url}}/2023/05/22/cppexception2/#memory-leak) 增加 `__cxa_begin_catch()` 调用之后, 是可以通过 `std::current_exception` 拿到当前异常对象, 之后再通过 `std::rethrow_exception()` 重新抛出异常, 之后便可以将异常对象转换为对应的 errordata 了.

```c++
// ExcInfo 类似于 PG ErrorData.
static void current_exc_info(ExcInfo* exc_info) noexcept {
  try {
    std::rethrow_exception(std::current_exception());
  } catch (const 业务异常类型1& e) {
    // 业务处理逻辑
  } catch (const 业务异常类型2& e) {
    // 业务处理逻辑
  } catch (const std::exception& e) {
    exc_info->message = e.what();
    exc_info->sqlerrcode = ERRCODE_INTERNAL_ERROR;
  } catch (...) {
    exc_info->message = "Unkown exception occurred";
    exc_info->sqlerrcode = ERRCODE_INTERNAL_ERROR;
    exc_info->detail = current_stack_trace();  // 保存此时堆栈, 便于问题排查.
  }
}

ExcInfo exc_info;
__cxxabiv1::__cxa_begin_catch(e);
SCOPE_EXIT {
  __cxxabiv1::__cxa_end_catch();
};
current_exc_info(&exc_info);

// 此时会触发 force unwind, 完成上面 cxa_end_catch 以及 exc_info 的析构.
ereport(ERROR, (
  errcode(exc_info.sqlerrcode),
  errmsg("%s", exc_info.message.c_str()),
  errdetail("%s", exc_info.detail.c_str())
))
```

## clang CXXEHABI 实现特色

clang/libc++abi 实现了 C++ Exception Handle ABI, 其并不支持 rethrow force unwind, 这导致了如上 [pthread_exit](https://hidva.com/g?u=https://godbolt.org/z/boe3oh7EW) 例子执行会 abort:

```
libc++abi: terminating due to uncaught foreign exception
```

实际上, libc++abi 一开始是支持 rethrow force unwind, 但是在 2012 一个 [patch](https://hidva.com/g?u=https://reviews.llvm.org/rG47cb854818ed51d591f58552c6e681a2ad372bf8) 中移除了这一支持... 咱也不支持为啥, 咱问了也没人搭理=.

但严格来说, 这一实现是遵循 ABI 的, 毕竟 ABI 规定:

> _Unwind_Resume should not be used to implement rethrowing. To the unwinding runtime, the catch code that rethrows was a handler, and the previous unwinding session was terminated before entering it. Rethrowing is implemented by calling _Unwind_RaiseException again with the same exception object.

实际上反而是 GNU/libstdc++ 并没遵循这一行为, 如 `__cxa_rethrow` --> `_Unwind_Resume_or_Rethrow` --> `_Unwind_Resume` 所示; 不过 libgcc 定义了 _LIBUNWIND_STD_ABI, _LIBUNWIND_STD_ABI 宏存在时, 会遵循这里约束, 使用 _Unwind_RaiseException. 但 _LIBUNWIND_STD_ABI 在 x86/arm 上都没有定义.

## gnu CXXEHABI 实现特色

gcc libstdc++ 的问题是其在 rethrow foregin exception 时总是自增 `std::uncaught_exceptions()` 计数值, 如我在这里[讨论](https://hidva.com/g?u=https://gcc.gnu.org/pipermail/libstdc++/2023-May/056016.html)所示:

> For native exceptions, it is reasonable to increment uncaughtExceptions in __cxa_rethrow
> because __cxa_begin_catch performs the corresponding decrement operation.
> However, for foreign exceptions, __cxa_begin_catch does not perform the decrement operation on uncaughtExceptions,
> and in fact, no function will decrement uncaughtExceptions at this point.
> This causes uncaughtExceptions to be incremented every time a foreign exception is rethrown,
> as shown in https://godbolt.org/z/G6fKrjEvM
>
> I also wanted to note that clang libc++ only increments uncaughtExceptions for native exceptions,
> as shown in the code snippet below:
>
> ```
> void __cxa_rethrow() {
>   __cxa_eh_globals* globals = __cxa_get_globals();
>   __cxa_exception* exception_header = globals->caughtExceptions;
>   if (NULL == exception_header)
>     std::terminate();      // throw; called outside of a exception handler
>   bool native_exception = __isOurExceptionClass(&exception_header->unwindHeader);
>   if (native_exception) {
>     exception_header->handlerCount = -exception_header->handlerCount;
>     globals->uncaughtExceptions += 1;
>   } else  // this is a foreign exception {
>     globals->caughtExceptions = 0;
>   }
> }
```

同样咱也不支持为啥, 咱问了也没人搭理=. 惨哦.