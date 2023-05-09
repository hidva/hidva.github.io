#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <unwind.h>
#include <stdint.h>


#define _HOLO_NOEXCEPT


jmp_buf buf;
uintptr_t jmpbuf_sp;
struct _Unwind_Exception g_ex;

static _Unwind_Reason_Code
holo_unwind_stop (int version, _Unwind_Action actions,
  _Unwind_Exception_Class exc_class,
  struct _Unwind_Exception *exc_obj,
  struct _Unwind_Context *context, void *stop_parameter) _HOLO_NOEXCEPT {
  uintptr_t context_sp = (_Unwind_Ptr) _Unwind_GetCFA (context);
  int do_longjmp = (actions & _UA_END_OF_STACK) || (context_sp >= jmpbuf_sp);
  if (!do_longjmp) {
    return _URC_NO_REASON;
  }
  longjmp(buf, 1);
  ::abort();
  return _URC_NO_REASON;
}

static void
holo_longjmp_unwind_cleanup (_Unwind_Reason_Code, struct _Unwind_Exception *) _HOLO_NOEXCEPT
{
  puts("holo_longjmp_unwind_cleanup");
  ::abort();
}


static void holo_longjmp(jmp_buf env, int val)  {  // 不能标记为 Noexcept, 否则会 core.
  g_ex.exception_class = 0;
  g_ex.exception_cleanup = &holo_longjmp_unwind_cleanup;
  _Unwind_ForcedUnwind(&g_ex, holo_unwind_stop, nullptr);
  ::abort();
}


static int f1_i = 33;

void f1() {
  if (f1_i > 3) {
    puts("longjmp from f1");
    holo_longjmp(buf, 1);
  } else {
    throw 33;  // 不加这一行, f2/f3 甚至都没有 `.cfi_personality 0x3,__gxx_personality_v0` 与 lsda 指示, 不知道什么情况
  }
 return;
}

struct S {
  S(const char* n):
    name(n) {}
  ~S() {
    printf("S::~S n=%s\n", name);
  }
  const char* name;
};

void f2() {
  S s("f2");
  f1();
}

// void f3() __attribute__((nothrow)) ;
void f3() {  // noexcept 会阻塞 force unwind, 即如果这里调用 pthread_exit 也会有问题.
  S s("f3");
  f2();
}

int main() {
  jmpbuf_sp =  (uintptr_t) __builtin_frame_address(0);
  if (setjmp(buf) == 0) {
    f3();
    return 0;
  }
  puts("main: exception");
  return 1;
}
