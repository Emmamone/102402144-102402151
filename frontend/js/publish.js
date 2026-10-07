/* 发布信息页 —— 占位，尚未实现。
 *
 * 待实现内容（见 docs/system-design.md 第 7.2 节与 docs/development-plan.md 阶段 4）：
 *   - setType() / setCat() / clearError()：类型与类别的切换、错误清除
 *   - submitForm()：**校验逻辑与错误文案逐字保留**（6 个必填项、去空格判空、
 *                   border-rose-400 / border-slate-200 切换、统一提示
 *                   「请完善标红的必填项」、平滑滚动到第一个出错字段），
 *                   仅把成功分支改为 API.create(payload) → 跳 success.html?id=<新id>
 *
 * 不复刻的旧行为：localStorage 的 campusNewItem、前端的 formatDateTime
 * （发布时间由服务端生成）、无网络失败路径（新增提示「发布失败，请稍后重试」）。
 *
 * 依赖的接口：POST /api/items（当前返回 501）
 */
