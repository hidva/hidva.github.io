---
title: "在 tokio 上几个失败尝试"
hidden: false
tags:
 -
   "JustForFun"
---

## 问题定义

最近在入门了 linux cfs scheduler, [pelt]({{site.url}}/2022/01/13/pelt/), load balance 这些之后, 忍不住想以 tokio code base 为基础实践一下这几种操作的威力; 希望是能为 [hologres](https://hidva.com/g?u=http://aliyun.com/product/bigdata/hologram) 的 holo os 提提速, 详细细节可参考论文:

> Hologres builds a scheduling framework, referred to as HOS,which provides a user-space thread called execution context to abstract the system thread. Execution contexts are super light weight and can be created and destroyed with negligible cost. HOS cooperatively schedules execution contexts on top the system thread pools with little context switching overhead.

我是这样想的, hologres 主打 HSAP. 这里 S 可以理解为点查点写这类非常轻量, 处理时间比较短暂的请求. A 可以理解为 OLAP 那种分析型, 处理时间比较长的请求; 当前 S, A 流量运行在同一个 holo os 线程池上, 可能会由于所有线程都忙于执行某个大分析查询, 导致影响了 S 吞吐/时延. 我们能不能从 holo os 调度层切入, 来尽量降低分析流量对 S 流量的影响.

如上问题等价于我们现在有一个 tokio runtime, runtime 中的绝大多数 task 一次 task.poll() 执行时间都很短暂, 大概在 200us 左右, 这部分 task 对应着 S 流量; 但偶尔会有部分 task task.poll() 执行约 50ms 左右, 对应着 A 流量; 可以想象如果 runtime 中所有线程都在执行分析流量的 task.poll() 时, 已经在 runqueue 中等待执行的 serving 流量便会收到影响. 为了尝试解决这个问题, 我们首先模拟出这些分析流量, serving 流量; 这里我们使用 tokio 编写了 [workload](https://hidva.com/g?u=https://github.com/KuiBaDB/kbio/blob/exp-rbtree/examples/workload.rs), 充当着 client; [workload-server](https://hidva.com/g?u=https://github.com/hidva/tokio/blob/master/examples/workload-server.rs), 作为 server 端; client 在建立到 server 的连接之后, 会发送 count: u64 到 server, server 收到 count: u64 之后会执行如下循环体之后返回响应给 client, client 统计这一来一回耗时并反复循环.

```rust
let mut s: f64 = 20181218.333333;
let loopcnt = socket.read_u64_le().await;
if let Ok(loopcnt) = loopcnt {
    for i in 1..=loopcnt {
        let i = i as f64;
        let i = i * i;
        let s1 = s * i;
        s = s1 / (s + 7.7);
    }
} else {
    break;
}
```

使用 count=10000 来作为 serving 流量的模拟, 此时循环体大致执行耗时约为 143.20us; 使用 count=10000000 作为分析流量模拟, 此时循环体执行耗时 55.34ms.

## fifo -> min heap

第一个想做的尝试是把 tokio local runqueue 的结构从 fifo 改为 min heap, min heap 按照 task 已经运行的时间 runtime 来排序; tokio 每次会选择 min heap 首元素来执行, 即 runtime 最小的 task. 这里 runtime 就类似于 linux cfs vruntime. 由于 local runqueue 结构与 tokio work stealing 机制耦合比较大, 暂未相应地改造 work stealing 逻辑, 在运行时会将 tokio runtime worker_threads 数目设置为 1, 这样就不需要运行 work stealing 相关逻辑. 具体改动见 [Use BinaryHeap for runqueue](https://hidva.com/g?u=https://github.com/KuiBaDB/kbio/commit/5b1d67065213f834b8d1ab9c24d9e42e26974741), 相关测试结构如下:

client 32 并发,:

| small task | req count | min latency | 90%      | 95%      | 99%       | 99.9%     | 99.99%    |
|------------|-----------|-------------|----------|----------|-----------|-----------|-----------|
| min heap   | 189806    | 148.914us   | 56.961ms | 57.081ms | 58.459ms  | 58.802ms  | 62.816ms  |
| fifo       | 98301     | 147.208us   | 56.988ms | 57.012ms | 111.968ms | 112.032ms | 112.190ms |
| big task   |           |             |          |          |           |           |           |
| min heap   | 3062      | 56.484ms    | 59.230ms | 59.240ms | 59.263ms  | 59.498ms  | 64.503ms  |
| fifo       | 3159      | 55.151ms    | 56.975ms | 56.996ms | 57.033ms  | 57.136ms  | 57.378ms  |

看上去数据还挺好看的, 但其实随着 client 并发的提升, big task 的延迟将不可控制地骤升; 其实也很好理解, 在 linux cfs 中会在每次 tick 更新 vruntime, 若 current vruntime 与 min vruntime 差距超过一定阈值时则触发抢占, 即在 linux cpu runqueue 中各个 task vruntime 差距不会很大. 但由于我们这里无法抢占, 只能在一个 task.poll 返回之后才能更新 task runtime, 会导致 runqueue 中 task 之间 runtime 差距很大, 导致 big task 会被饿死, 比如如下 client=128 的情况:

| small task | req count | min latency | 90%      | 95%      | 99%       | 99.9%     | 99.99%    |
|------------|-----------|-------------|----------|----------|-----------|-----------|-----------|
| min heap   | 2988895   | 144.510us   | 7.760ms | 8.289ms | 14.254ms  | 62.935ms  | 124.301ms  |
| fifo       | 97559     | 149.770us   | 227.740ms | 282.605ms | 282.697ms | 283.197ms | 907.632ms |
| big task   |           |             |           |          |           |           |           |
| min heap   | 108       | 55.220ms    | 7.159s | 7.204s | 14.146s  | 14.148s  | 14.148s  |
| fifo       | 3152      | 55.160ms    | 227.705ms | 282.566ms | 282.695ms  | 283.179ms  | 486.557ms  |



## sysmon

关于 sysmon, tokio 社区早在 2020 年 [A note on blocking](https://hidva.com/g?u=https://tokio.rs/blog/2020-04-preemption#a-note-on-blocking) 中提到过, 不建议实现 sysmon, 主要是不确定新建线程与吞吐之间的关系, 毕竟线程的增加导致同时运行的 task 数目的增多, 如果 task 之间内资源争抢的话, 可能会导致冲突加剧情况变糟. 我的观点是在我们这一场景, task.poll 中一般是纯粹的 cpu 密集型计算, 与其让 thread local runqueue 中的 serving 请求一直等着, 不如拉起一个新线程来赶紧处理下这些 serving 请求, 虽然会由于 context switching 导致 big task task.poll 执行时间变长了一点, 但我觉得可以容忍吧. 具体的实现细节在 [Add sysmon](https://hidva.com/g?u=https://github.com/tokio-rs/tokio/compare/master...hidva:master), 简单描述下改动:

-   我们为每一个 worker thread local runqueue 维护者一个 last access time, 当 worker thread 从 local runqueue 中 pop 一个 task 准备执行, 或者其他 worker thread 从这个 worker thread 偷取任务时, 都会更新 last access time,
-   我们会通过 blocking pool 创建一个 sysmon() 线程, 该线程周期性扫描所有 worker local runqueue 的 last access time, 如果某个 worker thread T last access time 距今已经超出一定阈值, 则表明当前 runtime 已有线程没有能力再处理 T local runqueue 中 task 了, 此时通过 blocking pool 新起一个线程 t2, 并将 T 交由 t2 负责, T 原线程 t1 会在完成当前正在运行的 task task.poll() 返回之后, 检测到 T 的所有权已经移交到 t2 而自动将 t1 还给 blocking pool. 这里通过使用 blocking pool 线程池机制, t2 可能是一个已有的空闲线程. 同时这里会控制 worker thread 最大数目, 如果已有 worker thread 超过配置值, 则 sysmon 不会试图创建新线程.


测试数据如下, 此时 workload-server worker_threads 配置为 4, max_worker_threads 配置为 8; workload client 并发为 128.

| small task                | req count | min latency | 90%       | 95%       | 99%       | 99.9%     | 99.99%    |
|---------------------------|-----------|-------------|-----------|-----------|-----------|-----------|-----------|
| origin (400%CPU)          | 1043237   | 143.208us   | 57.436ms  | 58.821ms  | 60.770ms  | 95.515ms  | 116.752ms |
| sysmon (550%CPU)          | 5576553   | 136.997us   | 5.863ms   | 6.976ms   | 14.206ms  | 21.482ms  | 29.685ms  |
| sysmon + taskset(400%CPU) | 4503207   | 139.924us   | 8.975ms   | 13.071ms  | 17.111ms  | 25.381ms  | 39.538ms  |
| big task                  |           |             |           |           |           |           |           |
| origin (400%CPU)          | 11792     | 55.340ms    | 61.674ms  | 62.651ms  | 106.519ms | 114.619ms | 304.085ms |
| sysmon (550%CPU)          | 12277     | 55.040ms    | 59.911ms  | 60.348ms  | 61.673ms  | 71.539ms  | 360.939ms |
| sysmon + taskset(400%CPU) | 7910      | 55.407ms    | 125.878ms | 138.013ms | 159.462ms | 186.790ms | 350.791ms |

可以看到如预期所示, 在保持相同 cpu 使用率的前提下, 由于抢占了 big task 的执行时间, 导致 big task 的吞吐有一点降低; 但好处也很明显: small task 的吞吐提升了 4 倍.

## ~~未实践: pelt~~

~~到这里, 我其实还有一个大胆的想法, 如 [pelt]({{site.url}}/2022/01/13/pelt/)  linux load balance 可以利用 pelt 统计出来的信息在 cpu 之间做均衡, 最终效果是 cpu 之间具有相似的**权重**负载, 注意这里的权重两字! 在 linux 中权重与进程优先级相关, 举个例子现在系统中有 2 个 cpu, 有 3 个进程 p1.weight = 40, p2.weight=20, p3.weight=20; 现在三个进程各运行了同样的时间 t, 此时内核认为 p1 造成的权重负载是 40 * t, p2, p3 各是 20 * t; 即在内核 load balance 模块眼里 p1 = p2 + p3, 最终均衡效果将是 cpu0 运行着 p1, cpu1 运行着 p2, p3. 既然我们这里没有优先级, 可以认为所有 task 都具有相同的权重; 如果实现了 linux pelt, load balance, 由于所有 task 具有相同的权重, 那么最终的均衡效果将是 task 的个数在各个 cpu 上具有相近的数目;~~ 没想清楚.. 先扔着吧.




