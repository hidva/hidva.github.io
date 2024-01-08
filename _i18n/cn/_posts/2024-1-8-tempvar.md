---
title: "小心! 编译器会创建临时对象"
hidden: false
tags: ["C++"]
---

是的! 还是我的一个 CR! 在跑测试时又遇到了一个奇怪的 coredump 问题! 总之我解决了! 最小复现代码是:

```c++
struct Class1 {
  virtual ~Class1() {}
};

struct Class2 : public Class1 {
  virtual ~Class2() {}
};

struct UsefulClass {
  ExecutionContext ec_;
public:
  future<> UsefulWork(const std::shared_ptr<Class1>& batch) {
    auto* batchptr = batch.get();
    // 这块代码是我新改动的, 之前 ec_.Invoke 由外部调用者负责, 我想着 ec
    // 算是类实现细节嘛, 这次就将 Invoke 内置了.
    // 在 lambda 中对于 batch 是 `&batch` 引用捕捉, 还是值捕捉时, 我踌躇了一会
    // 最终还是引用捕捉, 我的想法是: 改动前 UsefulWork 就是接受 `shared_ptr&` 引用类型,
    // 并且整个 UsefulWork 链路都是通过引用来传递的, 意味着外界会保障好生命周期,
    // 那我这里就引用捕捉吧, 还可以省一次 atomic_fetch_add.
    // 我错了! 我不该投机取巧的!
    return ec_.Invoke([&batch, batchptr] () {
      auto* ebatchptr = batch.get();
      DCHECK_EQ(batchptr, ebatchptr);
      // 运行测试, 这里 dcheck 失败!
    });
  }
};

future<> test1(UsefulClass& cls, const std::shared_ptr<Class2>& in) {
  auto fut = cls.UsefulWork(in);
  // usleep(3 * 1000 * 000);
  return fut;
}

TEST_F(UsefulTest) {
  auto cls = UsefulClass();
  auto in = std::make_shared<Class2>();
  co_await test1(cls, in);
  co_return {};
}
```

这里关于 ExecutionContext/Coroutine 细节可以参考我在 cpp-submit 2023 '异步编程与协程在高性能实时数仓Hologres的实践' 演讲:

![cpp-submit-2023-ec]({{site.url}}/assets/tempvar-1.png)

运行测试, 如上 `DCHECK_EQ(batchptr, ebatchptr)` 会失败! 原因后来看也很简单:

```c++
// auto fut = cls.UsefulWork(in);
// 这里 UsefulWork 参数类型是 const std::shared_ptr<Class1>&
// in 参数类型是 const std::shared_ptr<Class2>&
// 因此编译器会翻译为:
{
  const std::shared_ptr<Class1> __tmp_var = in;
  fut = cls.UsefulWork(__tmp_var);
}
// 到这里时, __tmp_var 就已经 dead 了!
return fut;
```

也就是 UsefulWork 中的 batch 都是指向着 `__tmp_var`, 在执行到 `auto* ebatchptr = batch.get()` 时, `__tmp_var` 早凉了. ==又是 const 引用, 在 [C++: is_move_constructible?]({{site.url}}/2023/02/15/cpp-move/) 我就栽过一会:

> 在运行时输出了 “f” 时, 瞬间勾起了我很久的记忆, 那是 2016-12-29 时, 我还刚刚入门 C++ primer, 其中提到过一句话:
>
> 只读左值引用. 只读左值引用可以接受任何可以转换为引用类型的表达式。如：
>
> ```c++
> double d = 3.3;
> const int &ref = d; // OK.此时等同于 int tmp = static_cast<int>（d）； const int &ref = tmp；
> ```

## asan

原因是清楚了! 可是, 我忠实的 AddressSanitizer 卫士呢! 她应该能检测到 `__tmp_var` 凉了, 并且在 `ebatchptr = batch.get()` 告诉我这事实来着. 但是并没有, 如上程序会顺利执行 batch.get(), 只不过由于 `__tmp_var` 凉了导致这里 ebatchptr 是个随机值, 导致了 dcheck 失败. 看了下 [AddressSanitizerUseAfterScope 文档](https://hidva.com/g?u=https://github.com/google/sanitizers/wiki/AddressSanitizerUseAfterScope):

> ```c++
> void f() {
>   int *p;
>   if (b) {
>     __asan_unpoison_stack_memory(x);
>     int x[10];
>     p = x;
>     __asan_poison_stack_memory(x);
>   }
>   *p = 1;
>    __asan_unpoison_stack_memory(frame);
> }
> ```
>
> Before a function returned, its stack memory **need to be unpoisoned** to avoid false reports for non-instrumented code.

明白了, 是这里 `need to unpoisoned` 搞的鬼. 如上程序中在 `auto* ebatchptr = batch.get()` 执行时, test1 已经 return 了, 即执行了 `__asan_unpoison_stack_memory(test1.frame)`, 导致 asan 认为 `__tmp_var` 变量又是 alive 的了. 所以如果我们反注释掉 `usleep` 让 test1 sleep 了一会, 确保 `auto* ebatchptr = batch.get()` 执行时 test1 尚未 return, 那么 asan 便能准确地检测到这一错误.


## 后记

退一步讲, 如果外界调用 UsefulWork 时总是 `co_await UsefulWork()` 那么其实也没有问题的, 因为临时对象会在 full expression 结束时才释放, 即会在 co_await 整体都执行结束时才释放, 即在 UsefulWork 执行期间, 临时对象总是有效的. 但不幸的是恰好有一处老代码并没有使用 co_await 还是传统的 `return UsefulWork().then()`..
