---
title: 异步编程模式
tags: [开发经验]
---

## 异步编程模式

再说异步编程模式之前, 先了解一下, golang 是如何解决异步的; 按我理解, golang 是通过协程来解决异步的, 协程是什么呢, 协程就是一个逻辑执行流, 具有自己的当前指令指针, 以及局部变量这些状态. 协程必须运行在一个真实的线程中. 当协程执行到可能会阻塞的操作时, 此时 golang 运行时会在协程提交操作请求之后, 将协程置为挂起状态并从当前线程中移除, 当前线程继续运行其他协程; 另一方面 golang 运行时会检测协程提交的异步操作是否完成, 并在检测到异步操作完成之后, 更新之前被挂起的协程的一些状态, 比如将异步操作的结果赋值给协程相应的局部变量等, 然后选择一个线程执行协程. 即从协程的角度来看, 协程是串行执行的.

所以可以参考 golang 的路子来异步编程, 可以使用 folly 提供的 Promise/Future 工具. 具体实践参考百度 Bigpipe(如果以后开源了的话) 中 AsyncPubPipelet 以及 Queue 类的实现. 以 AsyncPubPipelet 为例, AsyncPubPipelet 一个抽象链接有如下几个阶段:

1.  根据用户请求查询元信息服务获取用户数据所在副本组.
2.  再次查询元信息服务获取副本组当前主节点信息.
3.  与主节点建立 tcp 链接.
4.  按照写数据协议建立握手.
5.  写用户数据.
6.  出错关闭.

对应于代码如下:

```CPP
void AsyncPubPipelet::StartConn() {
    cli_ = NewEvbCli(iothd_);
    meta_->GetPipelet(opt_.Pipelet(), BPMeta::DONT_USE_CACHE).via(iothd_)
            .then(&AsyncPubPipelet::OnPipeletInfo, this)
            .then(&AsyncPubPipelet::OnBrokerGrp, this)
            .via(nullptr)
            .then(&AsyncPubPipelet::OnBPPipeline, this)
            .then(&AsyncPubPipelet::OnConnResp, this);
    return ;
}
```

有如下几种机制来检测抽象链接的存活性.

-   定时器, 会在抽象链接第 3 阶段建立链接之后安装一个定时器, 周期性触发一次, 触发逻辑中检测当前未被响应的请求是否超时. 如下:

    ```CPP
    // OnTick() 会周期性调用.
    template <typename R, typename W>
    void IOHelper<R, W>::OnTick() {
        StartTick();
        if (reqs_.size() <= 0 || !ioopt_->HasReqTO()) {
            return ;
        }
        auto now = std::chrono::steady_clock::now();
        auto reqb = reqs_.front().first;
        if (now > reqb && (now - reqb) > ioopt_->ReqTO()) {
            Reset(folly::make_exception_wrapper<std::runtime_error>("ReqTimeout"));
        }
        return ;
    }
    ```

-   每次写链接时都会检测是否出错. 如下:

    ```CPP
    folly::Future<folly::Unit> wf;
    // SendItem 使用了 facebook/folly AsyncSocket, facebook/wangle Pipeline, 会确保一旦一次 write 出错,
    // 后续所有 write 都会出错.
    for (auto &&data : unsnd) {
        unack_.emplace_back(/* 无关紧要的参数们 */, std::move(data));
        wf = SendItem(unack_.back());
    }
    // 若 wf 出错, 则会调用 onError 回调.
    wf.onError([this] (folly::exception_wrapper ex) -> folly::Unit {
        Reset(std::move(ex));
        return folly::unit;
    });
    return ;
    ```

-   利用 facebook/wangle 提供的 Pipeline 机制来检测, 如:

    ```CPP
    void readEOF(Context*) override {
        aplt_->Reset(folly::make_exception_wrapper<std::runtime_error>("ReadEOF"));
        return ;
    }
    void readException(Context*, folly::exception_wrapper e) override {
        aplt_->Reset(std::move(e));
        return ;
    }
    ```

以上任一环节出错都会进入 Reset() 逻辑, Reset 会:

```CPP
// Reset() 中某些操作, 比如下面的 pipeline close, 以及上面的逻辑链接存活检测机制都会触发嵌套 Reset 调用, 这里需要
// 覆盖这种 case.
void StartRst() noexcept {
    rst_ = true;
    return ;
}
void EndRst() noexcept {
    rst_ = false;
    return ;
}
bool IsInRst() const noexcept {
    return rst_;
}

template <typename R, typename W>
void IOHelper<R, W>::Reset(folly::exception_wrapper ex) {
    if (IsInRst()) {
        // 嵌套 Reset() 调用, 不做任何操作, 直接返回.
        return ;
    }
    // 开始 Reset 过程.
    StartRst();
    // 停止定时器, 在此调用之后, OnTick() 会确保不会再被调用.
    StopTick();
    if (cli_ && cli_->getPipeline()) {
        ppln_ = nullptr;
        cli_->getPipeline()->close().then([this, ex=std::move(ex)] () mutable {
            OnConnClose(std::move(ex));
        });
        return ;
    }
    OnConnClose(std::move(ex));
    return ;
}

template <typename R, typename W>
void IOHelper<R, W>::OnConnClose(folly::exception_wrapper ex) {
    EndRst();
    ++currty_;
    if (!ShouldNewConn(ex)) {
        DoClose({});
        return ;
    }
    if (ioopt_->HasRetryCnt() && currty_ > ioopt_->RetryCnt()) {
        DoClose(folly::make_exception_wrapper<std::runtime_error>("NoRetryTimes"));
        return ;
    }
    if (ioopt_->HasRtyInt()) {
        iothd_->timer().scheduleTimeoutFn([this] () {StartConn();}, ioopt_->RtyInt());
    } else {
        StartConn();
    }
    return ;
}
```

综上而言, Reset 会首先关闭当前逻辑链接相关资源, 比如定时器, TCP 链接等; 此后预期是当前逻辑链接不会再有任何活动产生, 比如不会再有 OnTick(), OnRead(), OnWriteSuccess(), OnWriteFail() 等回调产生. 实际上 facebook/wangle 这里存在一处设计缺陷, 会导致即使 pipeline 被 close() 了, 仍然会有 OnRead() 回调产生, 详情见[这里](https://github.com/facebook/wangle/pull/136). 在当前逻辑链接关闭之后, 根据配置判断是否需要建立新链接, 以及是否需要立即建立新链接, 还是睡眠一段时间之后再建立新链接.

关于被异步调用的回调中的内存管理; 如上 DoClose() 中会执行资源清理操作, 比如 `delete this` 等. 实现会确保 DoClose() 仅会在 OnConnClose() 中被调用. 并且如上所述在 OnConnClose() 被调用时, 不会再有任何 callback 产生了. 因此这里当 callback 被调用时, this 执行的内存一定是有效的; 反之若 this 被 delete 时, 一定不会再有 callback 产生了.

但某些场景下, 不能确保在 OnConnClose() 调用时不再有新回调的产生, 如此可用到另外一种内存管理方式: `weak_ptr` + `version`. 具体来说就是在构造 callback 时, callback 内部需要存放当前实例的 weakptr, 以及当前的版本. 同时在上述 Reset() 逻辑中需要自增当前版本. 大致如下:

```CPP
struct DoneHelper {
    DoneHelper(uint64_t v, std::shared_ptr<Queue> &&sp):
        connver(v), q(std::move(sp)) {}
public:
    uint64_t connver;
    std::weak_ptr<Queue> q;
};

struct AckDone: public DoneHelper, google::protobuf::Closure {
    using DoneHelper::DoneHelper;
    void Run() override;
};

// 根据当前实例状态构造 callback.
auto done = folly::make_unique<AckDone>(connver_, shared_from_this());
stub.delete_message(&done->cont, &req, done->resp.get(), done.get());

void Queue::Reset(folly::exception_wrapper ex) {
    // ...
    ++connver_;  // Reset() 时自增当前版本.
    // ...
}

void Queue::AckDone::Run() {
    SCOPE_EXIT {
        delete this;
    };
    auto sq = q.lock();
    if (!sq) {
        return ;
    }
    sq->iothd_.evb->runInEventBaseThread(
    // 虽然这里需要缩进一下, 但是明感觉不缩进更顺眼一点.
    [wq=std::move(q), v=connver, i=start, s=size, r=std::move(resp)] () mutable {
        auto sq = wq.lock();
        if (!sq || sq->connver_ != v) {
            return ;
        }
        // 此时表明实例仍然存活, 并且未被 Reset(), 即本次 callback 仍然有效.
        sq->DoAck(std::move(r), i, s);
    });
    return ;
}
```
