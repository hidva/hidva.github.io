---
title: "C++ 异常与 longjmp: 没有想象中那么美好"
hidden: false
tags: ["C++"]
---

在完成 [C++ 异常与 longjmp]({{site.url}}/2023/05/08/cppexception/) 这篇引子以及原型开发验证之后, 我立马投入到将其实战到我们项目中去, 毕竟我们同学已经深受这个折磨很久了. 我随便举个例子, 我们定义了 `HOLO_TRY_BEGIN`/`HOLO_TRY_END`, `GPOS_HOLO_TRY`/`GPOS_HOLO_CATCH_EX`/`GPOS_HOLO_CATCH_END`, `HOLO_PG_TRY`/`HOLO_PG_CATCH`/`HOLO_PG_END_TRY`/`HOLO_PG_END_TRY_WITHOUT_RETRY_EXCEPTION`/`HOLO_PG_CATCH_AND_RETHROW_WHEN_ERROR`, `TABLE_INFO_TRY`/`TABLE_INFO_END_TRY` 等等异常处理宏; 同时我们也开发了一大堆 clang-tidy 规则来检测相应的异常误用情况. 天下苦 longjmp 久已. 这篇文章记录着在实战过程遇到若干坑以及解决方案.

## __builtin_frame_address


```
           | 高地址
+----------+
|          |
|    f1    |
|          |
+----------+
|          |
|    f2    | PG_TRY pg_sigsetjmp()
|          |
+----------+
|          |
|    f3    |
|          |
+----------+
|          |
|    f4    |
|          |
+----------+
|          |
|    f5    | pg_siglongjmp()
|          |
+----------+
           | 底地址
```

如上图所示, 设想 f1 调用 f2, f2 调用 f3, ... , f4 调用了 f5; 我们在 f2 处执行了 PG_TRY, 其使用了 pg_sigsetjmp 注册了一个 pg_sigjmp_buf 并将其保存到 PG_exception_stack 全局变量中; 在 f5 处中调用了 elog(ERROR), 其执行了 pg_siglongjmp(PG_exception_stack) 触发了 force unwind; 在 force unwind 时, 针对栈上每一个函数, 判断 `_Unwind_GetCFA (context) >= f2_pg_sigjmp_buf.sp` 是否成立, 若成立则是时候停止 force unwind 了, 此时 `_Unwind_GetCFA (context)` 返回的是栈上每一个函数对应 rsp 寄存器的值. 预期情况应该是: 我们会依次执行 f5, f4, f3 局部变量的析构, 之后将控制流交给 f2 的 PG_CATCH(). 但实际上我跑起来之后却发现实际情况是: 我们依次执行了 f5, f4, f3, f2 局部变量的析构, 之后控制流又一次回到了 f2 的 PG_CATCH() ..

原因是我们在 pg_sigsetjmp 使用了 `__builtin_frame_address(0)` 作为 f2 对应 f2_pg_sigjmp_buf.sp 的值; 按照 gcc/clang 实现, 当函数中存在 __builtin_frame_address 调用时, 编译器总会为该函数保留 frame-pointer, 即该函数在任何优化级别下都不会开启 `fomit-frame-pointer` 优化, 同时 `__builtin_frame_address(0)` 返回的是 rbp 寄存器的值. 此时 force unwind 过程是:

1. 判断 f5 函数栈帧对应 rsp 寄存器 f5.rsp >= f2_pg_sigjmp_buf.sp 是否成立, 由于 f5.rsp < f2_pg_sigjmp_buf.sp, 所以执行 f5 局部变量的析构,
2. 判断 f4.rsp >= f2_pg_sigjmp_buf.sp 是否成立, 执行 f4 局部变量的析构.
3. 判断 f3.rsp >= f2_pg_sigjmp_buf.sp 是否成立, 执行 f3 局部变量的析构.
4. 判断 f2.rsp >= f2_pg_sigjmp_buf.sp 是否成立, 由于这里 f2_pg_sigjmp_buf.sp 的值是 f2.rbp, 而且 f2.rsp < f2.rbp, 所以执行了 f2 局部变量的析构.
5. 判断 f1.rsp >= f2_pg_sigjmp_buf.sp 是否成立, 不成立, 终止 force unwind. 控制流回到 f2 PG_CATCH 处.

之前说过, glibc pthread_exit 也是基于 force unwind 实现, 与我们不同的是, pthread_exit 这里是从 sigjmp_buf 结构中提取出 rsp 寄存器的值, 之后判断 `_Unwind_GetCFA(context) >= sigjmp_buf.rsp`, 我们也应该这样做, 但问题是, 拿不到 _jmpbuf_sp 的实现:

```c++
// pthread_exit force unwind 终止逻辑判断
if ((actions & _UA_END_OF_STACK) ||
        (void *) (_Unwind_Ptr) _Unwind_GetCFA (_context) >=
                _jmpbuf_sp(buf->cancel_jmp_buf[0].jmp_buf))
    do_longjump = 1;
```

最终解决方案: 通过 holo_get_sp 拿到 rsp 寄存器的值, 使用其作为 pg_sigjmp_buf.sp 的值, 这样与 pthread_exit 逻辑保持一致, 正确性兼容性上也更安心点.

```c++
#if defined(__aarch64__) || defined(__aarch64)
static __attribute__((always_inline)) uintptr_t holo_get_sp() {
	uintptr_t rsp;
	__asm__("mov %0, sp" : "=r" (sp));
	return rsp;
}
#elif defined(__x86_64__)
static __attribute__((always_inline)) uintptr_t holo_get_sp() {
	uintptr_t rsp;
	__asm__("movq %%rsp, %0" : "=r" (rsp));
	return rsp;
}
#else
#error "unsupport arch"
#endif

#define pg_sigsetjmp(out, savemask) ({	\
	pg_sigjmp_buf* _out = out;	\
	int _savemask = savemask;	\
	_out->sp = holo_get_sp();	\
	sigsetjmp(_out->jb, _savemask);	})
```

## PG_TRY 函数局部变量未析构

```c++
PG_TRY();
{
  D d("do you want build a snowman");
  // 预期是这里 d.~D() 析构应该执行, 但实际上没有.
  throw 33;
}
PG_CATCH();
{
}
PG_END_TRY();
```

原因其实已经体现在上面 force unwind 描述中了, 继续以上面那个调用图为例, 这里局部变量 d 位于函数 f2 中; 此时 force unwind 过程在判断 `f2.rsp >= f2_pg_sigjmp_buf.sp` 之后, 直接将控制流指向了 PG_CATCH 处, 因此未执行 d 的析构. 针对这个问题, 我第一想法是看看 pthread_exit 怎么做的, 难道下面的 d 也不会析构?

```c++
void* thread_main(void*) {
  D d("I never see you anymore")
  pthread_exit(NULL);
}
```

当然实测是析构的, 分析了原因, 是因为 pthread 中线程入口是 start_thread(), 其实现大致是:

```c++
int not_first_call = setjmp (unwind_buf.cancel_jmp_buf);
if (!not_first_call) {
  // 保存 unwind_buf 到 pthread 线程结构中,
  // 后续 pthread_exit 会执行 force unwind, 终点是这里的 unwind_buf
  THREAD_SETMEM (pd, cleanup_jmp_buf, &unwind_buf);
  ret = pd->start_routine (pd->arg);  // 调用我们的 thread_main 函数.
}
```

参考着 pthread 的做法, 我们也可以对 PG_TRY 宏做出如下调整:

```c++
#ifndef __cplusplus
// C 语言时, 继续用原来的宏.
#define PG_TRY() _PG_TRY()
#define PG_CATCH() _PG_CATCH()
#else
// C++ 时, 引入一个 lambda 使得实际上的业务逻辑发生在这个 lambda 内.
// 这达成的效果就是 setjmp 调用发生在业务逻辑调用者处, 确保业务逻辑中的局部变量的析构可以执行.
// 这里使用 pg_noinline 确保 lambda 不会被内联.
struct EarlyReturnFromPGTry { int _i = 33; };
#define PG_TRY()	\
	_PG_TRY();	\
	[&] () pg_noinline -> EarlyReturnFromPGTry {
#define PG_CATCH()	\
		return EarlyReturnFromPGTry{}; \
	} () ;	\
	_PG_CATCH()
#endif
```

EarlyReturnFromPGTry 存在的意义? 考虑如下代码:

```c++
void f() {
  PG_TRY();
  {
    puts("Come on let’s go and play!");
    return ;
  }
  PG_CATCH();
  {
    puts("come out the door!");
    return ;
  }
  PG_END_TRY();
  abort();  // 在我们改动之前, 这里 abort 无论如何都是执行不到的.
}
```

在我们改动之后, PG_TRY 内的 `return` 只是退出 PG_TRY 内的 lambda, 之后执行流接着执行函数 f 下一条语句: abort! 即我们对 PG_TRY 的改动改变了 PG_TRY 对外语义以及行为, 所以我们显式令 lambda 返回 EarlyReturnFromPGTry 类型, 确保已有代码代码中, 与新 PG_TRY 语义不兼容的地方可以编译报错.

## memory leak

还记得之前我们对 _Unwind_RaiseException 的 hook 么? 目的是为了在遇到未被 catch 的异常时, 将控制流指向到最近的 PG_TRY 处, 而不是 terminate 掉. 如之前的文章所示, 在原型中这块的实现是:

```c++
AVOID_ASAN _Unwind_Reason_Code _Unwind_RaiseException (struct _Unwind_Exception *e)
{
	static auto orig_unwind = reinterpret_cast<decltype(&_Unwind_RaiseException)>(
		dlsym(RTLD_NEXT, "_Unwind_RaiseException"));
	_Unwind_Reason_Code ret = orig_unwind(e);
	// At this point, the exception thrown by C++ does not have a corresponding catch handler.
	if (!is_main_thread())
		return ret;
	elog(ERROR, "uncaught exception with stacktrace ...");
	abort();
	return ret;
}
```

这其实是不符合 C++ 异常 ABI 描述的. 我们 `elog(ERROR` 开始的部分算是对这个 uncaught exception 的处理, 按照 C++ 异常 ABI 描述要求, 是需要增加 __cxa_begin_catch 等调用的:

```c++
__cxxabiv1::__cxa_begin_catch(e);
__cxxabiv1::__cxa_end_catch();
elog(ERROR, "uncaught exception with stacktrace ...");
```

不然就会出现:

```c++
PG_TRY() { throw 33; }
PG_CATCH() {}
PG_END_TRY();

// 在没有 __cxa_begin_catch 等调用时, 如下 assert 会失败.
// 并且会有内存泄漏.
assert(std::uncaught_exceptions() == 0);
assert(static_cast<bool>(std::current_exception()) == false);
```

## catch all

force unwind 要支持 catch all. 需求来自于如下场景, 考虑一个新同学, 在他其不了解 PG 异常模型前提下, 其可能会写出如下 "正确的" 代码:

```c++
auto* p = new int(33);
try {
  // ...
} catch (...) {
  delete p;
  throw;
}
```

在不考虑 try 内链路可能 elog(ERROR) 从而触发 PG longjmp 情况下, 如上代码确实是正确的; 但如果考虑了 elog(ERROR) PG longjmp, 并且 PG longjmp 触发的 force unwind 无法被 `catch(...)` 抓住, 那么如上代码就可能会导致内存泄漏. 幸运的是我们这里的 force unwind 天然支持能被 `catch(...)` 抓住. 只不过这里必须要 throw 再次抛出去, 如果忘记 throw 会触发我们的主动检测逻辑, 然后 abort 掉. 之所以必须要 throw 出去, 主要是 pg 事务模型相关原因, 这里不加以详述.

## arm

哈哈, arm 与 x86_64 遵循同样的 C++ 异常 ABI 规范. 所以如上实现没啥需要改动的.

## 后记

虽然标题中带了 '没有想象中那么美好', 但实际效果还是挺美好的. 我想, 自此之后, 我们终于脱离了 longjmp 这个苦坑.