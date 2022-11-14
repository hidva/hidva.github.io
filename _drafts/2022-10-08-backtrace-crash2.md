一开始以为是一样的问题, 但看了下, CFI 是正确的, 另外 coredump 位置是访问 f, 但从as2cfg上看, 所有路径都会访问 r14, 如果真的是 r14 寄存器问题, 早就该 coredump 了. 也即时刻 t1 时, r14 指向地址可以访问, 时刻 t2 时, r14 指向地址不可以访问了??

这让我想起了一桩一直悬而未决的问题, https://ticket.alibaba-inc.com/goc-ticket/ticket/2022083000000000743?page=1 as2cfg r14 = 0, 难不成是 CPU 问题?

```
>>> for note in core.notes:
...    if note.type_core == lief.ELF.NOTE_TYPES_CORE.PRSTATUS:
...       details = note.details
...       print(details)
...
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

LIEF 的一个 bug. 还帮助了 https://github.com/lief-project/LIEF/issues/808

梳理了下 libunwind 相关逻辑, 可以看到 r14 预期指向着一块 mmap 地址, 起始地址 x, 长度 y.

https://aone.alibaba-inc.com/v2/project/1024050/bug/44696040

=====

/Users/zhanyi.ww/project/alibaba/note/wp/2022-10-03.md 总结排查
delete ptr
jemalloc new crash
