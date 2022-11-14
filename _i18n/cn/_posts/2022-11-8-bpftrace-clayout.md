---
title: "bpftrace, 与 C++"
hidden: false
tags: ["C++"]
---

这篇文章总结下 bpftrace 以及相关工具, bpftrace 帮助我在日常值班, 双11大促(就比如刚刚结束的双 11 一峰), 时快速定位了不少问题. 关于 bpftrace 介绍, 一句话是 bpftrace 可以以极低开销查看运行时进程的状态, 比如函数执行阶段某个局部变量的值等. 这篇文章注重介绍 C++ 程序如何通过 bpftrace 追踪, 而不会过多介绍 bpftrace 基本操作.

## 问题

比如你想追踪如下程序运行时 `S.x` 的值:

```C++
#include <stdio.h>
#include <unistd.h>

struct X {
  virtual ~X() {}

  int x1;
};

struct S : public X {
  S() : x(0) {}

  S(const S &other) : x(other.x) {}

  S f(int y, int z) {
    printf("output from a.out: this.x=%d y=%d z=%d\n", x, y, z);
    x += (y + z);
    return *this;
  }

  int x;
};

int main(int argc, char **argv) {
  S s;
  int i = 0;
  while (1) {
    s.f(i, i);
    ++i;
    sleep(1);
    // break;
  }
  return 0;
}
```

便可以通过如下 bpftrace 脚本:

```
// t.bt
#include "struct.h"  // 其中存放着 S 的定义.

u:/apsara/zhanyi.ww/tmp/bphtrace/a.out:_ZN1S1fEii {
  printf("output from bpftrace: ret=%p this.x=%d y=%d z=%d\n", (int32*)arg0, ((struct S*)arg1)->x, arg2, arg3)
}
```

之后使用 bpftrace 便能查看进程运行时的状态:

```
bpftrace  -c ./trace t.bt
Attaching 1 probe...
output from a.out: this.x=0 y=0 z=0
output from bpftrace: ret=0x7ffff3044610 this.x=0 y=0 z=0
output from a.out: this.x=0 y=1 z=1
output from bpftrace: ret=0x7ffff3044610 this.x=0 y=1 z=1
...
```

发现点问题了么? bpftrace 需要知道 C++ 中 `S` 的内存布局是怎样的, 不然没法解引用.

对于 C 语言, 以及简单地 C++ 结构, 我们可以手写生成. 但对于涉及较多 C++ 特性, 比如 vtable 的结构, 手写很容易生成错误的内存布局, 还是以如上 `S` 为例, 可能会直观地认为 S 等同于如下 C 结构:

```c++
struct X {
  void** __vTABLE__;
  int x1;
  // padding: 4byte. 众所周知, 这里会有 4 字节 padding
}

struct S {
  struct X __parent0;
  // ERROR: 这里 X.x1 与 x 中夹杂着 4 byte padding.
  int x;
}
```

但并不是! 正确的布局 C 结构如下:

```C++
struct S {
  void* __vTABLE__;
  int x1;
  // x1 与 x 之间没有 padding.
  int x;
};
```

而且在双 11 大促值班过程那种紧张需要快速定位问题的背景下, 也不会给太多时间让你手写一下类的详细布局. 所以我们需要一个工具能将 C++ 类布局翻译成具有相同内存布局的 C 结构.

## bpftrace 0.16

实际上, 在[这个PR](https://github.com/iovisor/bpftrace/pull/2034)的加持下, 最新版本的 bpftrace, 实测 v0.16.0, 已经支持解析 binary 中的调试信息来计算字段偏移. 继续以如上例子举例, 在 bpftrace 0.16 下, bpftrace 脚本可以直接写为:

```bpftrace
// 这里并不需要任何关于 S 的声明. bpftrace 会解析 a.out 中的调试信息, 来计算 `S::x` 的偏移.
u:/apsara/zhanyi.ww/tmp/bphtrace/a.out:_ZN1S1fEii {
  printf("output from bpftrace: ret=%p this.x=%d y=%d z=%d\n", (int32*)arg0, ((struct S*)arg1)->x, arg2, arg3)
}
```

他甚至来支持模板形式, 比如:

```bpftrace
// 这里 S 是个模板类. bpftrace 会解析 trace2 中的调试信息来计算 `S<long>::x` 的偏移
u:/tmp/x/trace2:_ZN1SIlE1fEii {
  printf("output from bpftrace: ret=%p this.x=%d y=%d z=%d\n", (int32*)arg0, ((struct S<long>*)arg1)->x, arg2, arg3)
}
```

还是挺酷的.

## clayout

但 bpftrace 不支持跨 so 类型引用的情况:

```c++
// x.h
struct X {
  virtual ~X();

  int x1;
};

struct S : public X {
  S();

  S(const S &other);

  int x;
};

// X.cc
#include <stdio.h>
#include "x.h"

X::~X() {}

S::S(): x(0) {}

S::S(const S &other) : x(other.x) {}

// trace.cc
#include <stdio.h>
#include <unistd.h>

#include "x.h"


S a_long_function(S& input, int y, int z) {
  printf("output from a.out: this.x=%d y=%d z=%d\n", input.x, y, z);
  input.x += (y + z);
  return input;
}

int main(int argc, char **argv) {
  S s;
  int i = 0;
  while (1) {
    a_long_function(s, i, i);
    ++i;
    sleep(1);
    // break;
  }
  return 0;
}
```

```bash
$ clang++ -O0 -g X.cc -fPIC -shared -o libHidvaTest.so
$ clang++ -O0 -g trace.cc -L. -lHidvaTest -o trace
```

此时由于 clang 默认开启的 `-fstandalone-debug` 优化:

> -fstandalone-debug Clang supports a number of optimizations to reduce the size of debug information in the binary. They work based on the assumption that the debug type information can be spread out over multiple compilation units. Specifically, the optimizations are:
>
> will only emit type info for a dynamic C++ class in the module that contains the vtable for the class.

考虑到 S/X 类的 vtable 定义在 libHidvaTest.so 中, trace binary 中并不会包含 S/X 的详细信息, 只是会包含一个 DW_AT_declaration:

```
readelf --debug-dump=info trace
 <1><c4>: Abbrev Number: 6 (DW_TAG_structure_type)
    <c5>   DW_AT_name        : (indirect string, offset: 0x3f): S
    <c9>   DW_AT_declaration : 1
```

这就导致了 bpftrace 也无法从 trace binary 的调试信息中计算出字段的偏移:

```bpftrace
u:/tmp/x/3/trace:_Z15a_long_functionR1Sii {
  printf("output from bpftrace: ret=%p this.x=%d y=%d z=%d\n", (int32*)arg0, ((struct S*)arg1)->x, arg2, arg3)
}
```

```
$ bpftrace t.bt -c ./trace
t.bt:2:78-99: ERROR: Struct/union of type 'struct S' does not contain a field named 'x'
  printf("output from bpftrace: ret=%p this.x=%d y=%d z=%d\n", (int32*)arg0, ((struct S*)arg1)->x, arg2, arg3)
```


[clayout](https://hidva.com/g?u=https://github.com/hidva/clayout), 会通过解析一个或多个 shared library/binary .debug_info/.debug_type section 中记录的 dwarf 信息来将 C++/Rust 类翻译成具有相同内存布局的 C 结构. ~~直接吃编译器嚼好的结果更香更准确.~~ 还是以如上例子:

```
# clayout 会读取 trace, libHidvaTest.so 中的 dwarf debuginfo.
# 并生成 struct.h, struct.c
$ clayout -i trace -i libHidvaTest.so -o struct S

# struct.h 中包含 S 的详细布局.
# struct.c 中只是包含一些 assert, 用于校验生成的 S 结构对不对. 建议在使用 struct.h 之前编译执行下断言,
$ gcc struct.c && ./a.out  # 编译执行
```

```c
// struct.h 的内容如下所示, 可以看到 clayout 生成的 struct.h 会正确处理 vtable 相关
// Generated by hidva/clayout! 大吉大利!
#pragma once
#include <linux/types.h>
struct HidvaStruct2 {
  void** __mem1;
  int x1;
} __attribute__((__packed__));


struct S {
  struct HidvaStruct2 __parent0;
  int x;
} __attribute__((__packed__));
```

## 后记

我好想写 rust 啊, 虽说语言只是工具, 但这个工具好让人上瘾啊.