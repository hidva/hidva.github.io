---
title: "C 语言: Call to a function without a prototype"
hidden: false
tags: ["C++"]
---

上周我一同事找我看一个很有意思的问题, 一个 bool 返回值函数总是返回 true. 简化为如下例子:

```c
// 1.c
bool _is_valid_jsonb_with_schema() {
    // 简化后的例子, 实际 _is_valid_jsonb_with_schema 的逻辑有点复杂.
    return false;
}

// 2.c
void is_valid_jsonb_with_schema() {
    // 同样简化后表示
    if (_is_valid_jsonb_with_schema()) {
        puts("hello");  // print hello!
    } else {
        puts("world");
    }
}
```

就感觉很诡异, 使用 [as2cfg](https://hidva.com/g?u=https://github.com/hidva/as2cfg) 看下 _is_valid_jsonb_with_schema 的汇编控制流, 如下控制流移除了无关紧要的代码块:

![as2cfg]({{site.url}}/assets/20220723.as2cfg.png)

根据 [相关 ABI 标准]({{site.url}}/2019/12/09/behindcall/) 可知 rax 寄存器存放着函数的返回值. 如上控制流高亮处, eax 值来自于 ebp, ebp 有 0x7f245b644a28
xor ebp,ebp, 0x7f245b644b26 setne bpl 两处赋值; 其中 0x7f245b644a28 处 xor 会将 ebp 设置为 0; 0x7f245b644b26 处 setne 会根据之前 cmp 指令结果设置 bpl 寄存器, 即 ebp 的低八位,

![register]({{site.url}}/assets/20220723.reg.jpg)

根据 x86 语义, setne 只会修改 ebp 寄存器低 8 bit, 并不会更改其他 bit.

```
   0x4004e0 <+0>:     push   rbp
   0x4004e1 <+1>:     mov    rbp,rsp
   0x4004e4 <+4>:     mov    ebp,0xffffffff
   0x4004e9 <+9>:     cmp    ebp,0x20
   0x4004ec <+12>:    setne  bpl
=> 0x4004f0 <+16>:    xor    eax,eax
   0x4004f2 <+18>:    pop    rbp
   0x4004f3 <+19>:    ret
```

如上小例子中, 在 setne 之后, ebp 值为 0xffffff01, 可以看到 setne 只修改了 ebp 寄存器 8bit.

所以现在发现了一个疑点, 在 _is_valid_jsonb_with_schema 控制流中, 存在一个控制流执行了 setne bpl, mov eax, ebp; 如果在进入 _is_valid_jsonb_with_schema 时, ebp 高 24bit 未清零, 那么即使 setne bpl 将 ebp 低 8bit 设置为 0, 那么 _is_valid_jsonb_with_schema 返回时 eax 值呈现的情况是: 高 24bit 不为0, 低 8bit 为 0. 现在就看 is_valid_jsonb_with_schema 怎么使用 _is_valid_jsonb_with_schema 返回之后 eax 的值了, 如果 is_valid_jsonb_with_schema 使用 al, 即 eax 的低 8 bit, 那么没啥问题; 但使用了 eax 整体, 那么此时 eax != 0 将始终成立. 而且实际上看了下 is_valid_jsonb_with_schema 汇编结果, 其确实是使用了 eax 寄存器! 那么为什么呢?! 也即在 is_valid_jsonb_with_schema 所在源文件 2.c 中其认为 sizeof(bool) = 4, 但 _is_valid_jsonb_with_schema 所在源 1.c 中认为 sizeof(bool) = 1.

然后忽然想起来 C 语言类型检查非常弱, 它是支持函数未声明就使用的. grep 下 _is_valid_jsonb_with_schema, 其确实没有过声明, 而且加上声明之后确实就没有问题了..

![]({{site.url}}/assets/20220723.decl.png)

事后我同事信誓旦旦给我说他明明声明了! 然后我们俩一起看了下代码:

![]({{site.url}}/assets/20220723.4.jpg)

好吧, C 语言这么弱智的心智负担应该会有对应的 warning 选项啊:

```
$/apsara/alicpp/built/clang-11/clang-11/bin/clang -O2 -ggdb -fPIC -c -o main.o main.c
main.c:4:9: warning: implicit declaration of function 'f' is invalid in C99 [-Wimplicit-function-declaration]
        return f(r,r,r,r,r,r);
               ^
1 warning generated.
```

holo 所有代码统一使用了 `-Wall -Wextra -Werror` 应该直接编译出错了啊. 再次编译下看下编译选项:

```
#override CFLAGS+= -msse4.2
override CFLAGS += -msse4.2 -std=c11 -fPIC -w -fvisibility=hidden
```

`-w`...
