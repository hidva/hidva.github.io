---
title: "C++ 异常与 longjmp: 比想象中还要遭"
hidden: false
tags: ["C++"]
---

继在写完 [C++ 异常与 longjmp: 没有想象中那么美好]({{site.url}}/2023/05/22/cppexception2/), 并且跑通了 Debug 模式测试之后, 我当时真的以为 '好的, 这一切到此为止了', 可以发起 Code Review 了. 但万万没想到, 在 Release 模式下测试跪了. 唉, 从 [C++ 异常与 longjmp]({{site.url}}/2023/05/08/cppexception/), [C++ 异常与 longjmp: 没有想象中那么美好]({{site.url}}/2023/05/22/cppexception2/), 再到本篇 [C++ 异常与 longjmp: 比想象中还要遭]({{site.url}}/2023/05/23/cppexception3/), 我的心情也如这标题一般...

具体来说, 见附录 bad_code.cpp, 该代码在 `clang O2` 以上会运行报错, 在 `gcc`/`clang O1` 下均没有问题, 可以见这里 [godbolt](https://godbolt.org/z/sWxa7ccff) 运行结果. 报错原因, 我总结了下, 本质原因是 clang 在编译期分析出 `test_d` 中的 throw 没有对应的 catch, 并且这里最终总会 throw. 所以她认为 `test_d` 中 `d` 的析构不会执行, 这个也合理, 按照 C++ 标准, 对于 uncaught exceptions, 标准规定行为是 Implementation defined:

> In some situations exception handling must be abandoned for less subtle error handling techniques. [ Note: These situations are:
> [...]
> - when the exception handling mechanism cannot find a handler for a thrown exception (15.3), or [...]
>
> In such cases, std::terminate() is called (18.8.3). In the situation where no matching handler is found, it is implementation-defined whether or not the stack is unwound before std::terminate() is called.


进一步她认为 `CxxExNoCatch` 中的 `cnt` 未被修改过, 使得 `abort_assert_eq(cnt, 33 + 1)` 被优化为 `abort_assert_eq(0, 33 + 1)`. 最终使得 CxxExNoCatch 编译之后控制流图如下所示:

![CxxExNoCatch CFG]({{site.url}}/assets/cppexception3.1.png)

可以看到这里总会调用 abort_assert_eq 中的 abort! 编译器她可真是太 6 了, 我是没想到我的 `test_d` 是个递归函数, clang 她都能分析出 test_d 最终会异常. 另外 test_d 位于 PG_TRY noinline lambda 之后, clang 居然也能编译期分析出来 `CxxExNoCatch` 中的 `cnt` 不会被修改... 学无止境学无止境啊!

## 后记

针对这一问题, 我最终改动只是在给测试 case 加个 `[[clang::optnone]]` 标记.

```diff
-#define NO_CATCH_TEST_F(x, y) void y()
+#define NO_CATCH_TEST_F(x, y) [[clang::optnone]] void y()
```

对于业务代码, 考虑到业务代码应该不会无脑 throw, 其 throw 总是在一定分支下执行的, 应该不会遇到 clang 这个优化问题, 所以没做处理.

![我承认]({{site.url}}/assets/cppexception3.3.jpg)



## 附录

```c++
// bad_code.cpp
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <unwind.h>
#include <stdint.h>
#include <dlfcn.h>
#include <string>
#include <iostream>
#include <memory>
#include <cxxabi.h>

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


typedef struct pg_sigjmp_buf {
        sigjmp_buf jb;
        uintptr_t sp;
} pg_sigjmp_buf;
// pg_sigsetjmp must be a macro, even a pg_attribute_always_inline can cause pg_siglongjmp to jump to the wrong position.
#define pg_sigsetjmp(out, savemask) ({  \
        pg_sigjmp_buf* _out = out;      \
        int _savemask = savemask;       \
        _out->sp = holo_get_sp();       \
        sigsetjmp(_out->jb, _savemask); })
extern void pg_siglongjmp(pg_sigjmp_buf* env);
pg_sigjmp_buf *PG_exception_stack;

#define PG_TRY()  \
  do { \
    pg_sigjmp_buf *save_exception_stack = PG_exception_stack; \
    pg_sigjmp_buf local_sigjmp_buf; \
    if (pg_sigsetjmp(&local_sigjmp_buf, 0) == 0) \
    { \
      PG_exception_stack = &local_sigjmp_buf;   \
      [&] () __attribute__((noinline)) {

#define PG_CATCH()      \
      } (); \
    } \
    else \
    { \
      PG_exception_stack = save_exception_stack; \

#define PG_END_TRY()  \
    } \
    PG_exception_stack = save_exception_stack; \
  } while (0)


template <typename T, typename L>
void abort_assert_eq(const T& left, const L& right) {
  if (left != right) {
    std::cerr << "abort_assert_eq FAILED! left=" << left << " right=" << right << std::endl;
    abort();
  }
}


struct D {
  std::unique_ptr<std::string> data;
  int* cnt = nullptr;

 public:
  D(std::string d) : data(std::make_unique<std::string>(std::move(d))) {}
  ~D() {
    std::cerr << "D::~D; cnt=" << *cnt << "[@" << cnt << "] data=" << *data << std::endl;
    ++(*cnt);
  }
};

void test_d(int i, int* cnt) {
  D d(std::to_string(i) + " test_d");
  d.cnt = cnt;
  if (i <= 0) {
    throw 33;
    return;
  }
  test_d(i - 1, cnt);
}


#define NO_CATCH_TEST_F(x, y) void y()

NO_CATCH_TEST_F(HgElogUnitTest, CxxExNoCatch) {
  int cnt = 0;
  bool catched = false;
  PG_TRY();
  { test_d(33, &cnt); }
  PG_CATCH();
  {
    catched = true;
  }
  PG_END_TRY();
  abort_assert_eq(catched, true);
  abort_assert_eq(cnt, 33 + 1);
}

#define RUN_NO_CATCH_TEST(x)                                             \
  do {                                                                   \
    std::cerr << "RUN_NO_CATCH_TEST begin: " << #x << std::endl;         \
    x();                                                                 \
    abort_assert_eq(std::uncaught_exceptions(), 0);                      \
    abort_assert_eq(static_cast<bool>(std::current_exception()), false); \
    std::cerr << "RUN_NO_CATCH_TEST end: " << #x << std::endl;           \
  } while (0)

int main() {
  RUN_NO_CATCH_TEST(CxxExNoCatch);
  return 0;
}


static _Unwind_Reason_Code
pg_sjlj_unwind_stop (int version,
        _Unwind_Action actions,
        _Unwind_Exception_Class exc_class,
        struct _Unwind_Exception *exc_obj,
        struct _Unwind_Context *context,
        void *stop_parameter)
{
        pg_sigjmp_buf* env = (pg_sigjmp_buf*)stop_parameter;
        uintptr_t context_sp = (_Unwind_Ptr) _Unwind_GetCFA (context);
        int do_longjmp = (actions & _UA_END_OF_STACK) || (context_sp >= env->sp);
        fprintf(stderr, "pg_sjlj_unwind_stop; context_sp=%lx envsp=%lx actions=%d do_longjmp=%d\n", context_sp, env->sp, actions, do_longjmp);
        if (do_longjmp)
                siglongjmp(env->jb, 1);
        return _URC_NO_REASON;
}

static void pg_sjlj_ex_cleanup(_Unwind_Reason_Code _c, struct _Unwind_Exception *_e)
{
        abort();
}
static struct _Unwind_Exception pg_sjlj_ex;
void pg_siglongjmp(pg_sigjmp_buf* env)
{
        pg_sjlj_ex.exception_class = 0;
        pg_sjlj_ex.exception_cleanup = &pg_sjlj_ex_cleanup;
        // Triggering a force unwind causes the destruction of C++ local variables to be performed.
        _Unwind_ForcedUnwind(&pg_sjlj_ex, pg_sjlj_unwind_stop, env);
        abort();
}

__attribute__((no_sanitize("address"))) _Unwind_Reason_Code _Unwind_RaiseException (struct _Unwind_Exception *e)
{
        static auto orig_unwind = reinterpret_cast<decltype(&_Unwind_RaiseException)>(
                dlsym(RTLD_NEXT, "_Unwind_RaiseException"));
        _Unwind_Reason_Code ret = orig_unwind(e);
        // At this point, the exception thrown by C++ does not have a corresponding catch handler.
        // if (!is_main_thread())
        //         return ret;
        __cxxabiv1::__cxa_begin_catch(e);
        __cxxabiv1::__cxa_end_catch();
        pg_siglongjmp(PG_exception_stack);
        abort();
        return ret;
}
```