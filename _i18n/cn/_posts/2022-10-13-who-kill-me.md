---
title: "Coredump 未解之谜: 为什么 r14 为 0?"
hidden: false
tags: ["C++"]
---

干活的时候, 同事又塞了个 coredump, 咋一看比较直观 r14 寄存器为 0, 导致 SIGSEGV.

```
   0x00007f54b0335cf0 <+0>:     push   r15
   0x00007f54b0335cf2 <+2>:     push   r14
   0x00007f54b0335cf4 <+4>:     push   r13
   0x00007f54b0335cf6 <+6>:     push   r12
   0x00007f54b0335cf8 <+8>:     push   rbx
   0x00007f54b0335cf9 <+9>:     mov    r14,QWORD PTR [rdi]
   0x00007f54b0335cfc <+12>:    test   r14,r14
   0x00007f54b0335cff <+15>:    je     0x7f54b0335d07 <A+23>
   0x00007f54b0335d01 <+17>:    add    QWORD PTR [r14],0xffffffffffffffff
   0x00007f54b0335d05 <+21>:    je     0x7f54b0335d11 <A+33>
   0x00007f54b0335d07 <+23>:    pop    rbx
   0x00007f54b0335d08 <+24>:    pop    r12
   0x00007f54b0335d0a <+26>:    pop    r13
   0x00007f54b0335d0c <+28>:    pop    r14
   0x00007f54b0335d0e <+30>:    pop    r15
   0x00007f54b0335d10 <+32>:    ret
=> 0x00007f54b0335d11 <+33>:    mov    rbx,QWORD PTR [r14+0x30]
```

```
(gdb) i r r14
r14            0x0                 0
```

习惯性地将对应汇编使用 [as2cfg](https://hidva.com/g?u=github.com/hidva/as2cfg) 转换为控制流图:

![]({{site.url}}/assets/hos-lw-core.jpg)

就发现很奇怪的地方, 如控制流图所示, crash 所处控制流块只有一个入边, 即当 crash 在 rip=0x7f54b0335d11 时, 当时 CPU 的情况一定是:

1. 执行了 `0x7f54b0335d01 add QWORD PTR [r14],0xffffffffffffffff`
2. 执行了 `0x7f54b0335d05 je 0x7f54b0335d11`;
3. 执行 `0x7f54b0335d11 mov rbx,QWORD PTR [r14+0x30]`;

在执行 0x7f54b0335d11 时由于 r14 = 0 crash 了. 问题是如果 r14 = 0, 在执行 0x7f54b0335d01 时就应该 crash 啊! 我第一反应是 gdb 出 bug 了?! 众所周知, gdb 是通过读取 coredump NOTE segment 来得到 crash 点各个线程各个寄存器的信息; 所以我使用了 lief project 直接解析下 coredump, 还顺便帮 lief project 修复了个 bug [Use Segment::file_offset() instead of Binary::virtual_address_to_offset() for parsing note segment](https://github.com/lief-project/LIEF/issues/808). lief 读取出来的信息如下所示:

```
Name:                            CORE
Type:                            PRSTATUS
Description:                     [0b 00 00 00 00 00 00 00 00 00 00 00 0b 00 00 00 ...]
Siginfo:        11 - 0 - 0
Current Signal: 11
Pending signal: 0
Signal held:    0
PID:            64
PPID:           1
PGRP:           1
SID:            1
utime:          1900:826000
stime:          36:865000
cutime:         23225:806195
cstime:         23782:825399
Registers:
X86_64_R15    : 0x7f5536455510
X86_64_R14    : 0
X86_64_R13    : 0x7f5520e18030
X86_64_R12    : 0x7f5520e18030
X86_64_RBP    : 0x7f4e906a89f0
X86_64_RBX    : 0x7f4e906a89c0
X86_64_R11    : 0
X86_64_R10    : 0x7f4df48b8f00
X86_64_R9     : 0x7f54b2456a80
X86_64_R8     : 0x7f53f744ce90
X86_64_RAX    : 0x7f54b0cd9a08
X86_64_RCX    : 0x2
X86_64_RDX    : 0x7f4e906a8b30
X86_64_RSI    : 0x7f4e90803bf0
X86_64_RDI    : 0x7f4e906a8a38
X86_64__      : 0xffffffffffffffff
X86_64_RIP    : 0x7f54b0335d11
X86_64_CS     : 0x33
X86_64_EFLAGS : 0x10246
X86_64_RSP    : 0x7f55227fcd10
X86_64_SS     : 0x2b
```

r14 确实为 0, 我有点慌了. 不过 lief 确实显示了一个值得注意的地方:

```bash
Name:                            CORE
Type:                            SIGINFO
Description:                     [0b 00 00 00 00 00 00 00 fa ff ff ff 00 00 00 00 ...]
Signo:          11
Code:           0   # 这里 lief 把 Code/Errno 搞混了, 实际上 Errno = 0, Code = -6
Errno:          -6

# Description 的全部内容:
$od -A d -t xI ~/tmp/hos-lw-core/siginfo.desc.txt
0000000 0000000b 00000000 fffffffa 00000000
0000016 00000019 00000000 00000000 00000000
0000032 00000000 00000000 00000000 00000000
*
0000128
```

从 kernel code 中可以看到 `Core = -6` 意味着信号是用户触发的, 如上 `00000019 00000000` 记录了发送方 pid=0x19, uid=0x0.

```
/*
 * si_code values
 * Digital reserves positive values for kernel-generated signals.
 */
#define SI_USER		0		/* sent by kill, sigsend, raise */
#define SI_KERNEL	0x80		/* sent by the kernel from somewhere */
#define SI_QUEUE	-1		/* sent by sigqueue */
#define SI_TIMER	-2		/* sent by timer expiration */
#define SI_MESGQ	-3		/* sent by real time mesq state change */
#define SI_ASYNCIO	-4		/* sent by AIO completion */
#define SI_SIGIO	-5		/* sent by queued SIGIO */
#define SI_TKILL	-6		/* sent by tkill system call */
#define SI_DETHREAD	-7		/* sent by execve() killing subsidiary threads */
#define SI_ASYNCNL	-60		/* sent by glibc async name lookup completion */

#define SI_FROMUSER(siptr)	((siptr)->si_code <= 0)
```

考虑到 linux pid namespace 的存在, 单单这里记录的 pid=0x19, 由于缺少对应的 pid namespace, 所以并不能确认是哪个进程. 根据 kernel code 可知这里 pid=0x19 是调用 tkill 的进程当前的 pid namespace X. 设 crash 进程所处 namespace 为 Y, 根据 kernel kill 以及 pid 可见性规则, 这里 X 要么是 Y, 要么是 Y 的祖先. 不想写了, 现在一堆的疑问:

- 具体是谁发送了 SIGSEGV 信号???

- 无论是谁发送了 SIGSEGV 信号, rip=0x7f54b0335d11, r14=0 这种组合都不应该出现啊!
