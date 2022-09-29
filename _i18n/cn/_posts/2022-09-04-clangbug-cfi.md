---
title: "backtrace() crash: 从 CFI 说起"
hidden: false
tags: ["C++"]
---

最近我们线上一种 crash 出现的频次逐渐升高, 具有完全一致的堆栈, 即在 `_M_deallocate()` 时收到了 SIGUSR2 信号, 信号里面调用了 backtrace(), backtrace() 触发了 SIGSEGV 导致了 crash.

```
#0  x86_64_fallback_frame_state (context=0x7fc3f69fa3b0, context=0x7fc3f69fa3b0, fs=0x7fc3f69fa4a0) at ./md-unwind-support.h:63
#1  uw_frame_state_for (context=context@entry=0x7fc3f69fa3b0, fs=fs@entry=0x7fc3f69fa4a0) at ../../../libgcc/unwind-dw2.c:1265
#2  0x00007fc400b36078 in _Unwind_Backtrace (trace=0x7fc40064ee10 <backtrace_helper>, trace_argument=0x7fc3f69fa660) at ../../../libgcc/unwind.inc:302
#3  0x00007fc40064ef86 in backtrace () from /lib64/libc.so.6
#4  0x00007fc4050f2120 in hologram::os::StackTrace::StackTrace (this=0x7fc3f69fa6d0, back_trace_now=<optimized out>)
#5  0x00007fc4050f3b28 in hologram::os::stacktrace (out=..., skip_frames=0, show_location=false)
#6  0x0000000000233dbb in hologram::flow::SegfaultHandler (sig=11, info=<optimized out>, ctx=<optimized out>)
#7  <signal handler called>
#8  x86_64_fallback_frame_state (context=0x7fc3f69fb880, context=0x7fc3f69fb880, fs=0x7fc3f69fb970) at ./md-unwind-support.h:63
#9  uw_frame_state_for (context=context@entry=0x7fc3f69fb880, fs=fs@entry=0x7fc3f69fb970) at ../../../libgcc/unwind-dw2.c:1265
#10 0x00007fc400b36078 in _Unwind_Backtrace (trace=0x7fc40064ee10 <backtrace_helper>, trace_argument=0x7fc3f69fbb30) at ../../../libgcc/unwind.inc:302
#11 0x00007fc40064ef86 in backtrace () from /lib64/libc.so.6
#12 0x00007fc4050f213e in hologram::os::StackTrace::BackTrace (this=0x7fc3f3001238)
#13 <signal handler called>  # SIGUSR2
#14 std::_Vector_base<unsigned char, std::allocator<unsigned char> >::_M_deallocate (this=<optimized out>, __p=0x7fc3f31f1d90 "\034\275e\216\301\177", __n=<optimized out>)
#15 std::_Vector_base<unsigned char, std::allocator<unsigned char> >::~_Vector_base (this=0x7fc3f69fc9c8)
#16 std::vector<unsigned char, std::allocator<unsigned char> >::~vector (this=0x7fc3f69fc9c8)
#17 boost::dynamic_bitset<unsigned char, std::allocator<unsigned char> >::~dynamic_bitset (this=0x7fc3f69fc9c8)
#18 A::D::~D (this=0x7fc3f69fc9a8)
#19 A::B::~B (this=0x7fc3f69fc9a8)
#20 0xb943000000000000 in ?? ()
#21 0x00007fab02bc9600 in ?? ()
#22 0xbf490000000005c9 in ?? ()
#23 0x0000000000000000 in ?? ()
```

如 holo 论文所示, holo 是基于 C++20 协程构建的, 而 C++20 协程并不支持抢占式调度, 可能会出现某段逻辑一直执行, 不主动让出线程, 导致其他任务不能执行. 为了能及时诊断这种情况, 我们调度系统会周期性检测所有工作线程运行情况, 如果发现某一线程一直在执行一个任务, 则调度系统会给这个线程来个 SIGUSR2 信号, 工作线程在 SIGUSR2 信号回调中调用 backtrace 保存下当前堆栈便于后续研发同学针对性修复. 所以如上堆栈进一步解释, 在工作线程执行 `#14 _M_deallocate` 时, 调度系统发现这个工作线程一直在执行着一个任务, 所以给他发送了个 SIGUSR2 信号; 之后工作线程在 SIGUSR2 信号回调中执行了 backtrace, 没想到 backtrace SIGSEGV 了.

当我看到这个堆栈时, 我第一反应是业务代码有问题, 写坏了栈了, 毕竟堆栈中有个很扎眼的 `0xb943000000000000`. 但如堆栈所示, 这时是在执行 `A::B::~B` 析构函数, 从代码上看, 这个析构链路完全是由编译器生成的代码 + STL + boost 代码, 没有丝毫研发介入的机会, 写坏了栈可能性还是太低了. 另外一种可能, 是不是在 SIGUSR2 回调中调用了 backtrace(), 这一链路某个环节把栈写坏了? 但可能性还是太低, 一方面, 信号回调的执行是在 linux 专门分配的一块栈时, 与业务代码栈在两个空间; 另外一方面, 根据 backtrace() 及其链路源码, 可知其入口处会立刻初始化 context, 而 context 在 coredump 中值如下:

```
(gdb) p context
$6 = (struct _Unwind_Context *) 0x7fc3f69fb880
(gdb) p *context
$7 = {
  reg = {0x7fc3f69fbc10, 0x7fc3f69fbc08, 0x7fc3f69fbc18, 0x7fc3f69fc870, 0x7fc3f69fbbf0, 0x7fc3f69fbbe8, 0x7fc3f69fbbf8, 0x0, 0x7fc3f69fbba8, 0x7fc3f69fbbb0, 0x7fc3f69fbbb8, 0x7fc3f69fbbc0, 0x7fc3f69fbbc8, 0x7fc3f69fbbd0, 0x7fc3f69fc878, 0x7fc3f69fbbe0, 0x7fc3f69fc880, 0x0},
  cfa = 0x7fc3f69fc888,
  ra = 0xb943000000000000,  # 又是 0xb943000000000000
  lsda = 0x0,
  bases = {
    tbase = 0x0,
    dbase = 0x0,
    func = 0x7fc35308c710 <A::B::~B()>
  },
  flags = 4611686018427387904,
  version = 0,
  args_size = 0,
  by_value = '\000' <repeats 17 times>
}
```

根据 context.ra = 0xb943000000000000, 可知在 backtrace() 入口获取 context 时, 栈上的内容已经是 '0xb943000000000000', 不可能是 backtrace 链路写入的. 没有思路了, 看看 crash 时栈上都有哪些内容吧, 如果真是被写坏的, 总不能恰好只写坏了 8 个字节, 说不定被写坏处周围有些什么信息呢?

```
(gdb) f 19
#19 A::B::~B (this=0x7fc3f69fc9a8)
(gdb) i r rsp
rsp            0x7fc3f69fc868      0x7fc3f69fc868
(gdb) x/5xg 0x7fc3f69fc868
0x7fc3f69fc868: 0x0000000000000000      0x00007f9ee7fb6c20
0x7fc3f69fc878: 0x00007fc3531377a4      0xb943000000000000
0x7fc3f69fc888: 0x00007fab02bc9600
(gdb) x 0x00007fc3531377a4
0x7fc3531377a4 <A::H::J(std::pair<unsigned long, std::unique_ptr<A::Z, std::default_delete<A::Z> > > const&, unsigned long)::$_2::operator()<unsigned long>(unsigned long&&) const+1188>:    0x8489484024448b48
(gdb) disassemble 0x00007fc3531377a4
   0x00007fc35313779c <+1180>:  mov    rdi,r15
   0x00007fc35313779f <+1183>:  call   0x7fc35308c710 <A::B::~B()>
   0x00007fc3531377a4 <+1188>:  mov    rax,QWORD PTR [rsp+0x40]
```

woc! 从代码上看, 这个 `0x7fc3531377a4` 正好是 'A::B::~B()' 的调用方啊! 即 '0x7fc3531377a4' 才是正确的 return rip, 而不是 gdb/backtrace 认为的 0xb943000000000000. 即正确的 return rip 存放在栈上 '0x7fc3f69fc878' 位置. 但 gdb/backtrace 都认为栈上 '0x7fc3f69fc880' 存放的才是 return rip. gdb/backtrace bug 啦? 总结下目前情况:

```
# A::B::~B() 指令
# prologue 部分
0x7fc35308c710 push r14
0x7fc35308c712 push rbx
0x7fc35308c713 push rax
0x7fc35308c714 mov rbx,rdi
...
0x7fc35308c7bf call 0x7fc35358ca10
0x7fc35308c7c4 mov rdi,QWORD PTR [rbx+0x20]
0x7fc35308c7c8 add rsp,0x8
0x7fc35308c7cc test rdi,rdi  # 在执行 test 之前收到了 SIGUSR2 信号,
```

```
# 出事时栈, f18 代指 f19 的调用方,
# 高地址
|
+---------+
|         | # 0xb943000000000000
+---------+
| f18.rip | # 0x00007fc3531377a4, 即 f19 的 return rip,
+---------+
| f18.r14 | # 0x00007f9ee7fb6c20
+---------+
| f18.rbx | # 0x0000000000000000
+---------+ <---- rsp, 执行 test 之前, rsp 指向这里
| f18.rax |
+---------+ <---- 执行 0x7fc35308c7c8 add 之前, rsp 指向这里.
|
|
# 低地址
```

在执行 0x7fc35308c7cc test 之前时, 理论上, gdb/backtrace() 应该通过 rsp + 0x10 来获取 return rip; 但从 crash 现场上看, gdb/backtrace 都使用了 rsp + 0x18 来获取了错误的 return rip. 看起来就像是 gdb/backtrace 并不知道 0x7fc35308c7c8 处执行了 `add rsp, 0x8`?!

众所周知, gdb/backtrace() 是通过 .eh_frame 中记录的 CFI, Call Frame Info 信息来进行 backtrace 的; 我们可以通过 `readelf -wF` 读取到 `A::B::~B` 的 CFI; 不严谨的说, CFI 中每一行指定了在 LOC 指定的指令处, 如何根据当前 rsp 寄存器的值计算出 return rip, 即 CFA.

```
0003a8a0 0000000000000034 0003a8a4 FDE cie=00000000 pc=0000000000acb710..0000000000acb7f1
   LOC           CFA      rbx   r14   ra
0000000000acb710 rsp+8    u     u     c-8
0000000000acb712 rsp+16   u     u     c-8
0000000000acb713 rsp+24   u     u     c-8
0000000000acb714 rsp+32   c-24  c-16  c-8  #1
0000000000acb7ad rsp+24   c-24  c-16  c-8  
0000000000acb7ae rsp+16   c-24  c-16  c-8
0000000000acb7b0 rsp+8    c-24  c-16  c-8
0000000000acb7b1 rsp+32   c-24  c-16  c-8
0000000000acb7d1 rsp+24   c-24  c-16  c-8
0000000000acb7d2 rsp+16   c-24  c-16  c-8
0000000000acb7d4 rsp+8    c-24  c-16  c-8
0000000000acb7d9 rsp+32   c-24  c-16  c-8
```

以 `0xacb71e <+14>: mov %rax,0x90(%rdi)` 为例, 这里 0xacb71e <= 0xacb7ad, 意味着当 CPU 执行 0xacb71e 这条指令时, unwinder 可以通过 '#1' 处 CFI 记录的信息, 通过将当前 rsp 的值 + 32 - 8 可以得到 return rip.

根据这里的 CFI 记录, 可知当 CPU 执行到 `0x7fc35308c7c8 add`, `0x7fc35308c7cc test`, 对应的 CFI 记录为 `acb7b1 rsp+32`, 怪不得 gdb/backtrace() 都采用了 rsp + 32 - 8 来获取 return rip. 所以现在问题就清晰了, crash 的原因是因为编译器生成的 CFI 记录不全导致的. 那么为什么编译器会生成不全的 CFI 呢? 我根据问题出现链路凝练了一个最小复现代码:

```c++
#define UNW_LOCAL_ONLY
//#include <libunwind.h>
#include <stdint.h>
#include <stdio.h>
#include <signal.h>
#include <execinfo.h>
#include "boost/dynamic_bitset.hpp"

using U = int64_t;
class MIC;
class MI;
class PKD;
class IMK;
using SN = uint64_t;
static const SN KMSN = ((0x1ull << 56) - 1);
enum ValueType : unsigned char {
  HELLO
};

class E {
public:
  virtual size_t GES() const = 0;
  virtual ~E() = default;
};

class PRE : public E {
public:
  virtual ~PRE() {}
  PRE(const std::vector<const MIC*>& icm, bool fr, U uq)
    : icm_(icm), fr_(fr), uq_(uq) {}
 public:
  const std::vector<const MIC*>& icm_;
  bool fr_;
  U uq_;

  mutable boost::dynamic_bitset<uint8_t> sb_;
  mutable boost::dynamic_bitset<uint8_t> nb_;
  mutable bool hnb_ = false;
  mutable size_t size_ = 0;
  mutable std::vector<uint32_t> vlo_;
  mutable bool suq_ = false;
  mutable bool encp_ = true;
};


class Slice {
public:
  Slice() {}
  Slice(const char* p, size_t s): data_(p), size_(s) {}
public:
  const char* data_ = nullptr;
  size_t size_ = 0;
};

class PR {
public:
  struct PRDI {
    size_t cc;
    uint32_t sbl = 0;
    uint32_t nbl = 0;
  };
  ~PR() {
    if (ci_) {
      delete[] ci_;
      ci_ = nullptr;
    }
  }

  PR(const std::vector<const MIC*>& cols, Slice&& row) : cols_(cols), row_(std::move(row)) { }
private:
  const std::vector<const MIC*>& cols_;
  Slice row_;
  PRDI di_;
  mutable const char** ci_ = nullptr;
};


class PKD {
public:
  PKD(const MI* ime_, const Slice& user_key) : ime_(ime_), user_key_(user_key) {}

  ~PKD() {
    if (decb_.data != nullptr) {
      delete[] decb_.data;
    }
  }

private:
  const MI* ime_;
  Slice user_key_;
  std::vector<char*> pk_data_;
  bool decoded_ = false;
  size_t decoded_count_ = 0;
  bool lkfs_ = true;

  struct Buffer {
    char* data = nullptr;
    size_t size = 0;
  };
  Buffer decb_;
};

class PKe {
  const MI* ime_;
  Slice user_key_;
  mutable PKD* decoder_ = nullptr;
  ValueType value_type_ = ValueType::HELLO;
  SN sn_ = KMSN;
public:
  PKe(const MI* im) : ime_(im) {}
  ~PKe() {
    if (decoder_) {
      delete decoder_;
      decoder_ = nullptr;
    }
  }
};

class IMKEnc {
public:
  virtual ~IMKEnc() = default;
  IMKEnc(const MI* imx, const IMK* key)
    : key_(imx),
      data_({}, Slice("", 1)),
      ime_(imx) {}
 private:
  mutable PKe key_;
  mutable PR data_;
  const MI* ime_;
};

class IMKBAD : public PRE, IMKEnc {
public:
  IMKBAD(const MI* imx, const std::vector<const MIC*>& icm, const IMK* key, bool fr, U uq)
    : PRE(icm, fr, uq), IMKEnc(imx, key) {}
  size_t GES() const override {
      return 0;
  }
  ~IMKBAD() = default;
};

static void* frames[256];
int frame_size = 0;

void sig2(int) {
//  frame_size = unw_backtrace(frames, 256);
  frame_size = backtrace(frames, 256);
}

int main() {
  signal(SIGUSR2, sig2);
  auto* p = new IMKBAD(nullptr, {}, nullptr, false, 1);
  p->sb_.resize(1000);
  p->sb_[33] = true;
  delete p;
  return 0;
}
```

如上例子使用 `clang -ggdb -O3 -DNDEBUG  -std=gnu++17  -S  2.cc` 编译可以看到某些 `add rsp` 指令后面没有跟着相应的 cfi 伪指令生成相应的 CFI 记录信息:

```
--
	addq	$8, %rsp
    #! 没有根据 .cfi 指令.
.Ltmp50:
	.loc	12 173 6
	testq	%rdi, %rdi
--
	addq	$8, %rsp
    # 这个倒是生成对应了 cfi 指令.
	.cfi_def_cfa_offset 24
	popq	%rbx
.Ltmp101:
--
```

而使用 g++ 则没有问题. 当然了, 也不能说是 clang 的问题, 本来嘛, 信号调用里面执行 backtrace() 就是非常模糊的事情, .
