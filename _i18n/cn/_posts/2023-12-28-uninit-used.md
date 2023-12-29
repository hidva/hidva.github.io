---
title: "初始化! 初始化! 又是未初始化!"
hidden: false
tags: ["C++"]
---

最近我的一个 CR 反反复复跑了好几轮测试, 每一轮测试都有零星几个测试失败, 每次失败的测试也都不一样, 而且从我 CR 内容上也可以分析到与这些测试毫无关系, 所以我一直信誓旦旦地给测试小姐姐强调不是我的问题, 测试小姐姐就去找 case owner 去排查 case 不稳定的问题. 但考虑到我的 CR 就一直没有跑成功过一轮测试, 而且测试小姐姐被我也折腾烦了:

> @盏一 请再仔细确定一下是否跟你的改动有关

我开始灰溜溜地二分下我的 CR 看看是否真的是我改动引起的== 但万万没想到, 还真的是:

```diff
  public:
-  Transaction()
+  Transaction(private_tag)
     : Transaction(0,
@@ -176,7 +176,7 @@ class TransactionManager {
     : tablet_(std::move(tablet)),
-      dummy_trans_(make_lw_shared<Transaction>()),
+      dummy_trans_(make_lw_shared<Transaction>(Transaction::private_tag{})),
       default_initial_timeout_(default_initial_timeout),
```

如上两行改动会引起 case 随机大面积失败. 这里 private_tag 就是一个很简单的 `struct private_tag{}`. 使用 [hidva/as2cfg](https://hidva.com/g?u=https://github.com/hidva/as2cfg) 分析了下 TransactionManager 构造函数汇编代码, 瞧出来了端倪. 在此改动之前, dummy_trans_ 相关构造逻辑:

```asm
0x0000000000190728 <+120>:  mov    edi,0x250
0x000000000019072d <+125>:  call   0x37b640 <_Znwm@plt>  # 分配空间
0x0000000000190732 <+130>:  mov    rbp,rax
0x0000000000190735 <+133>:  mov    rdi,rax
0x0000000000190738 <+136>:  add    rdi,0x10
0x000000000019073c <+140>:  vxorps xmm0,xmm0,xmm0  # 对分配出的空间执行 memset(0) 操作
0x0000000000190740 <+144>:  vmovups ZMMWORD PTR [rax+0x210],zmm0
0x000000000019074a <+154>:  vmovups ZMMWORD PTR [rax+0x200],zmm0
0x0000000000190751 <+161>:  vmovups ZMMWORD PTR [rax+0x1c0],zmm0
0x0000000000190758 <+168>:  vmovups ZMMWORD PTR [rax+0x180],zmm0
0x000000000019075f <+175>:  vmovups ZMMWORD PTR [rax+0x140],zmm0
0x0000000000190766 <+182>:  vmovups ZMMWORD PTR [rax+0x100],zmm0
0x000000000019076d <+189>:  vmovups ZMMWORD PTR [rax+0xc0],zmm0
0x0000000000190774 <+196>:  vmovups ZMMWORD PTR [rax+0x80],zmm0
0x000000000019077b <+203>:  vmovups ZMMWORD PTR [rax+0x40],zmm0
0x0000000000190782 <+210>:  vmovups ZMMWORD PTR [rax],zmm0
0x0000000000190788 <+216>:  vzeroupper
0x000000000019078b <+219>:  call   0x190ce0 <_ZN7niagara11TransactionC2Ev>  # 调用 Transaction()
```

有一处奇怪的是, `make_lw_shared<Transaction>()` 就等同于 `new Transaction()`, 代码中没有手动 memset(0) 过, 为啥这里生成的汇编会有这种效果? 而在此改动之后:

```asm
0x0000000000190728 <+120>:  mov    edi,0x250
0x000000000019072d <+125>:  call   0x37b600 <_Znwm@plt>  # 分配空间
0x0000000000190732 <+130>:  mov    rbp,rax
0x0000000000190735 <+133>:  mov    QWORD PTR [rax],0x0
0x000000000019073c <+140>:  mov    rdi,rax
0x000000000019073f <+143>:  add    rdi,0x10  # 调用 Transaction()
0x0000000000190743 <+147>:  call   0x190ca0 <_ZN7niagara11TransactionC2ENS0_11private_tagE>
```

很明显, 改动之后没有了 memset(0) 操作; 那问题很明确了, 八成是 Transaction 类存在未初始化成员了. 这让我想起来了去年我们 clang11 升 clang13 也遇到过使用未初始化成员问题, 当时也是折腾了好久...

在解决这个未初始化便使用的成员之后, 另外一个问题是: 为啥 `new Transaction()` 在 Release/Debug 模式都会生成 memset(0) 操作?

```c++
class S {
  long i;
  long j;
public:
  // S() = default;  // 这一行有没有都不影响生成结果.
}

S* f1() {
  // 生成汇编如下: 带有 memset(0) 操作.
  // mov     edi, 16
  // call    operator new(unsigned long)
  // pxor    xmm0, xmm0
  // movups  XMMWORD PTR [rax], xmm0
  return new S();
}
```

而且奇怪的是: 我们显式定义了 `S()` 便不会有 memset(0) 生成.

```c++
class S {
  long i;
  long j;
public:
  S(int)  {}
  S(): S(33) {}
  // S() {}  // 这样也不会有 memset(0)
};

S* f1() {
  // 生成汇编如下:
  // mov     edi, 16
  // jmp     operator new(unsigned long)
  return new S();
}
```

这又得去翻 C++ reference 来了解这一现象产生的缘由了:

> if T is a class type with no default constructor or with a user-declared(until C++11)user-provided or deleted(since C++11) default constructor, the object is default-initialized;

解释了为啥 `S() {}` 存在时不会有 memset(0)

> if T is a class type with a default constructor that is not user-declared(until C++11)neither user-provided nor deleted(since C++11) (that is, it may be a class with an implicitly-defined or defaulted default constructor), the object is zero-initialized.

解释了为啥 `S() = default` 时会有 memset(0).

但等等, 在我们代码中, Transaction 是有 `Transaction() {}` 的啊! 为啥还是会有 memset(0) 效果??? 这时因为 `make_lw_shared<Transaction>()` 并不是直接 `new Transaction()`, 而是 `new shared_ptr_no_esft<Transaction>()`, 而 shared_ptr_no_esft 定义:

```c++
template <typename T>
struct shared_ptr_no_esft {
  shared_ptr_counter_type _count = 0;
  T _value;
public:
  shared_ptr_no_esft() = default;
  template <typename... A>
  shared_ptr_no_esft(A&&... a) : _value(std::forward<A>(a)...) {}
}
```

因此在我改动之前, 在 new 分配内存时, 是调用 `new shared_ptr_no_esft<Transaction>()`, 编译器此时行为:
1. 先调用 malloc() 分配内存.
2. memset(0); 由于 shared_ptr_no_esft() = default 命中了 zero-initialized 规则.
3. 执行 shared_ptr_no_esft 成员初始化 -> 初始化 Transaction 成员.

在我给 Transction(private_tag) 构造加了个参数之后, 此时分配内存变为了: `new shared_ptr_no_esft<Transaction>(private_tag)`. 编译器行为:
1. 先调用 malloc() 分配内存.
2. 直接调用 shared_ptr_no_esft(private_tag) 构造函数, 不会 memset(0).

## 后记

很明显, 这又是和 [C++ 的心智负担 -- Integral promotion]({{site.url}}/2022/03/28/badcpp/), [C++: is_move_constructible?]({{site.url}}/2023/02/15/cpp-move/) 等等一样, 又是一个不得不让人在写代码时时刻惦记着的心智负担: '啊, 我给类加了个成员, 可一定要记得加个初始化啊!'. 看来我们的 clang-tidy 又要有的忙了..

