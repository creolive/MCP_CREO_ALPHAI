# DEV-076 曲面反馈补充计划

采用brainstorming明确的离线范围，用户已授权继续整合；用writing-plans及executing-plans执行。

设计：不猜SDK枚举值、不从本机头文件存在性推断已加载worker能力；静态能力保留注册enabled，新增机器可读SDK条件并明确enabled含义，动态可用性留接手。组状态仅修错误reason，不改测量值/阈值/预算。修剪提示提供可能原因，不输出未经测量的交线字段。

1. 原件逐字节归档、DEV-076登记，对照已有成果与本地源码。
2. 提取生产group_state_decide原函数到测试编译目录，C++夹具只代替测量结构，不代替判定逻辑，覆盖边界可用/不可用、gap缺失、open/closed/micro_gap/overlap。先红后绿修reason。
3. SDK条件、修剪提示与能力限制同步；以专项单测、无Toolkit的C++执行和当前SDK组合编译验证。
4. 更新逐项映射/接手/能力边界与证据，单次独立最终审查，提交当前分支，保留用户dirty文档。

Review Focus: 不把开放弧推断当定因；不凭常量猜测解除SDK门控；reason与open_edges一致且不改变四态；不以本机SDK代替loaded worker；历史原件与用户内容保持。

完成：1—4全部执行；生产C++判定先红后绿；117专项与无Git同专项通过、SDK编译/样式成功；独立审查无发现。验收及取舍见feedback-0.18.4-surface-2026-11-08/ACCEPTANCE.md。
