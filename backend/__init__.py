"""校园失物招领 —— 服务层。

分层约定（见 docs/coding-standards.md 第 4.1 节）：

- ``main.py``       路由声明、依赖装配、静态挂载
- ``db.py``         连接管理、建表 DDL
- ``schemas.py``    请求与响应模型（校验）
- ``serialize.py``  行 → 响应对象的转换（纯函数）
- ``seed.py``       幂等写入演示数据
"""
