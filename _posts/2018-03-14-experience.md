---
title: 开发经验
tags: [开发经验]
---

## 启发式究竟是什么意思?


我一直不太懂 "启发式" 是啥意思?! 比如说算法导论中在介绍不相交集合时引入的 "加权合并启发式策略" 等等.

最近在学习 vivaldi algorithm 中感觉对 "启发式" 有点了解了; 按我理解带有启发式字样的算法随着时间的推移其运行效果将会越好; 就像 vivaldi 算法随着时间推移每个节点掌握的网络拓扑就越精准, 效果就越好.


## 要使用 HTTP Cache-Control


注意使用 HTTP Cache-Control 首部来控制 http 行为, 不然可能会有预料之外的效果; 比如 chrome 就可能会直接 from disk cache 而不会发送请求!


## 代码风格: 简洁高效赏心悦目


要时刻明确与坚持自己的代码风格.

## 层次化也是模块化


之前认为所有的架构设计都可以归纳为模块化, 层次化; 现在意识到层次化中的层次也是模块的一种, 底层向高层呈现的接口也就是底层标识模块的接口. 所以层次化也是模块化.

即所有的架构设计都可以归纳为模块化, 模块之间通过明确的接口语义通信, 在使用模块提供的接口时无需了解模块的实现细节.

## 注意 fdatasync 的写放大

fdatasync 每次刷盘是以 pagesize 为最小单位进行(可能是 4 KB), 那么在进行一些小数据的写入的时候, 每次刷盘都会放大为 4 KB, 从而使得 IO 出现瓶颈.

## 磁盘分区要对齐 pagesize

在对磁盘进行分区的时候, 如果不进行pagesize的对齐, 会导致fdatasync的性能大幅下降, 所以要先检查磁盘分区是否已进行pagesize对齐.

## 记住那些闪光点

应该在博客中记录下自己平时遇到过的经典 BUG; 以及开发中一些闪光点, 比如之前的 mysql JSON 调优, storm PIPEQ 调优等. 一方面这个东西今后用作回顾也算不错. 另一方面在面试时可能会被问过遇到的最经典的 bug.


## 安全编码意识很重要

曾经我以为那些远程溢出漏洞都是一些很愚蠢的程序猿写出来的. 现在我倒是觉得溢出真是防不胜防啊! 如下代码, 摘自[rocksdb.gb 中 block.go](https://github.com/pp-qq/rocksdb.go/blob/master/rockstable/block.go):

```go
k_end := offset + unshared
if unshared <= 0 {
	k = anchor[:shared]
} else if shared <= 0 {
	k = this.data[offset:k_end]
}
```

如果 go 在 index expression 时未进行下标范围检测, 那么由于溢出的存在, `k_end` 可能是个负值, 导致在 `this.data[offset:k_end]` 时会访问到非法内存.
