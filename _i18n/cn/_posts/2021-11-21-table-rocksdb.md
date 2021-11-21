---
title: "开脑洞地为 rocksdb 引入 orc 替换 sst"
hidden: false
tags:
 -
   "KuiBaDB"
---

## 问题定义

开发 KuiBaDB 的由头之一是想论证我自己脑补的一个[列存模型]({{site.url}}/2021/04/25/kuiba-column-storage/), 这个列存模型受 hologres 论文中列存启发, 结合我自己的 PG 背景, 移除了 delete map, 转而为列存每一行加个 xmin, xmax 字段来表示行的事务信息, 从而可以判断行是否已经删除. 但在了解 [Spanner]({{site.url}}/2021/11/10/spanner/) 之后, 结合 KuiBaDB 开发经验, 对 PG 事务模型在高并发扩展性下的效果有点怀疑. 主要集中在时刻维护着一个运行中事务列表, 快照通过这个运行中事务列表表示, 通过这个运行中事务列表作可见性判断, 事务中的数据直接写到存储中这几点. 举个极端例子, 10000 个事务同时写入, 每个事务写入 10 行, 这 10w 行会写入到 heap table 中, 一方面这 1w 个事务在写入时会竞争 heap table shared buffer 上的锁, 另外一方面, 这时启动第 10001 事务 select, 10001 事务持有的快照中包含了正在进行中的 1w 事务的 xid, 而且 heap table 10w 行数据对 10001 事务也是可见的, 10001 事务需要扫描这 10w 行数据, 然后针对每一行根据其快照判断这行对自身事务是否可见. 在 hologres 论文中提到的 HSAP 高并发场景, 这一情况将会进一步恶化.

在 Greenplum 中, 这一情况好像更不妙了. Greenplum 支持分布式事务, 每一个分布式事务在参与的 segment 上有一个对应的 PG 单机事务, segment 上维护者 PG 单机事务 xid 到分布式事务 gxid 的映射. master 端维护着运行中的分布式事务集合, 对于 select, 其首先根据 master 维护的正在运行中分布式事务的集合构造出分布式快照 global snapshot; 之后 select 计划下发到 segment 上后, 再会根据 segment 上正在运行中的 PG 单机事务集合构造出一个 local snapshot; 之后在扫描数据时, 对于每一行需要根据 local snapshot 判断其可见性; 同时还需要根据 segment 上维护的单机事务 xid 到 gxid 的映射找出这一行对应的 gxid, 再根据 global snapshot 判断这一行的可见性.

在 Spanner 事务模型中, 快照只是由单个 timestamp 标识, 快照的生成也不需要节点之间进行交互, 粗糙一点的话直接用最新的 timestamp 即可. 在扫描数据时, 可见性判断也只是根据行插入的 timestamp 与快照 timestamp 比较一下. 而且进行中的事务造成的写入并不会写到表文件中, 而是暂存起来, 这部分数据对其他事务完全不可见.

业界知名的 OceanBase, CockroachDB, TiDB 都是采用 Spanner 这种事务模型. 这些数据库在存储上也都有一个共性, 后端都是使用了 KV 存储, 非常类似于 rocksdb, 此时表主键作为 key, value 存放着行的其他列按照特定编码生成的字节数组. 这类数据库的删除操作也都有一个共性, 删除并不是像 PG 一样在原有行标记一下, 而是写入一个新的 K-V 项, 新 K-V 项与被删除行具有相同的 K 值, 但具有特殊的标记意味着新 K-V 项的语义是删除了 K. hologres 的行存其实也是类似的做法. 也即如果想基于行存实现 Spanner 事务模型, 那么我们可以像上面那些业界主流数据库一样, 使用 rocksdb 类似的 KV 存储实现行存就成. 但俺想整列存.

有一点需要更正, 在 TiDB, CockroachDB 中, KV 存储层对 schema 完全无感知, KV 存储层视 Value 就是纯粹的字节流, 并不清楚 Value 包含哪些列. 在 OceanBase 中, 根据公开文档以及代码, 其 KV 存储层会感知 schema, 其知晓 Value 部分有哪些列组成. OceanBase SST 具有宏块, 微块的概念, 如 ObRowWriter::append_store_row() 所示微块会根据 schema 采用列式存储数据, 并会对列进行各种编码操作.

所以现在的问题是如何基于列式存储模型实现 Spanner 那种事务模型. OceanBase 中的做法是在微块级别应用列式存储. CockroachDB 不支持列存. TiDB 的列存 TiFlash 使用了 DeltaTree + TiFlash 列存, 我个人认为 DeltaTree 就是个小 rocksdb; 当用户删除一行时, 会往 DeltaTree 新增一个 KV 项, 这个 KV 项具有特殊标记也表明是对 K 的删除; 在 select 时, 对于 TiFlash 列存吐出的行都要在 DeltaTree 中检测下行是否被删除了; 还是有点麻烦的不是么==

## 如何解决

而我的脑洞也受到了 OB 的启发, 通过给 rocksdb 加入行的语义, 此时 rocksdb K 是 primary key, V 是列按照指定规则编码后的值, rocksdb 是知道 V 有哪些列的, 并且其也能解析出 V 中列. rocksdb DB 配置可以指定是使用 SST 还是 ORC 作为后端存储, 还是同时使用 ORC + SST. 若指定了使用 ORC, 则在 Flush Memtable 时便会扫描 memtable 所有行, 然后转储为 orc. 此时 compaction 的输入/输出也都是 orc 格式. 若同时使用了 ORC + SST, 则 flush memtable 时会基于一份 memtable 生成 SST/ORC 存储, 这时通过一个 VersionEdit 来将新生成的 SST/ORC 文件原子性加入到 Version 中. 也即同时启用 ORC+SST 时, ORC, SST 中的数据总是完全一致的. 此时 compaction 可以选择使用 SST 或者 ORC, 之后生成 SST + ORC. 在同时启用 SST + ORC 的情况下, 我们可以根据查询特征自适应选择使用 SST 还是 ORC, 反正这俩总是一致的. 对于 ORC, 除用户列之外, 还有有一个元数据列, 类似于 ObRowHeader, 这个元数据列编码了 timestamp, value_type 信息. 当然为了 ORC 更好的压缩编码, 或许将 timestamp, value_type 分成两个列存储最合适.

关于 schema 的管理, 准备采用 PG pg_attribute 那套 schema 管理, 即表 schema 包含如下内容, 我们这里有个限定条件, 当列加入到表之后, 其便只能被 drop, 即只有 Col::attisdropped 字段能改变, 其他字段无法改变.:

```rust
type Col struct {
    attnum: u16,
    attname: str,
    atttypid: Oid,
    attlen: i16,
    attalign: u8,
    atttypmod: i32,
    attnotnull: bool,
    attisdropped: bool,
}

type Schema struct {
    cols: Vec<Col>,
}
```

之后当一行数据插入到 memtable 中时, 这行数据中也编码着当前列的总数目是多少, 就类似于 PG 中的 t_infomask2, 存放着 number of attributes. 这一信息也会持久化到 SST + ORC 中, 在 ORC 中, 也可以专门用个元数据列, 考虑到这列的值基本上都是一样的, 在 ORC RLE 编码下, 压缩效果应该很不错. 或者进一步限定下, 对于一个特定的 memtable, 一个特定的 sst 文件, 一个特定的 orc 文件, 他们中的每一行都具有相同的列数目; 即 alter table add column 时会触发 memtable 的切换. 在 flush memtable 同时我们也会将 `Schema.cols[..number_of_attrs]` 编码到 sst/orc 文件中, 这样对 sst/orc 文件的解析不需要表 schema 信息. 在 compaction 时, 若输入文件具有相同的 number_of_attrs 则意味着这些文件具有相同的 schema, 此时生成的 sst/orc 文件也是这个 schema. 若输入文件具有不同的 number_of_attrs, 比如文件 input1.orc number_of_attrs=3 input2.orc number_of_attrs=7 则意味着在 input1 之后用户又新增了 3 列, 在 compaction 时会认为 input1 也存在这 3 列, 只不过值都为 null; input1, input2 生成的 result.orc number_of_attrs=7, 具有与 input2.orc 一样的 schema. 没错我们 alter table add column 新增的列必须 nullable, 而且原有行只能为 null, alter table add column 不会触发表数据的重写, Spanner 也正是这么做的!

集成到 KuiBaDB 中的姿势, 一个表对应着一个 rocksdb, 之后还有一个特殊的 rocksdb meta rocksdb 存放着一些元信息, 即把 kb_class, kb_attribute, kb_type 的信息都塞到这个 meta rocksdb 中. 为了避免 opened rocksdb 实例过多导致 oom 等问题, 可以通过 SharedBuffer 管理 rocksdb, 这样我们可以配置下最多允许同时 opened rocksdb 实例数目. 当 open table tA 时若发现 shared buffer 容量已经满, 则选择一个不常用的 table tB, 淘汰 tb, 即关闭 tb rocksdb 实例, 之后再次 open table tA. 当然 meta rocksdb 总是 opened 的.

## 效果如何

如上内容尚且都是属于脑洞, 也是我接下来休息日的目标==
