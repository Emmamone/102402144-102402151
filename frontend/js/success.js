/* 发布成功页 —— 占位，尚未实现。
 *
 * 待实现内容（见 docs/system-design.md 第 7.2 节与 docs/development-plan.md 阶段 4）：
 *   - fillSummary()：读 ?id → API.detail(id) 渲染 #sName #sType #sTimeLabel
 *                    #sTime #sPlace #sContact（用服务端返回的 masked）#sPublish
 *   - 无 ?id 或请求失败时，沿用现有的固定兜底摘要，保证直接打开该页不空白
 *   - 「查看详情」链接改为动态指向 detail.html?id=<真实id>（复用 common.js 的 maskContact 仅用于兜底摘要）
 *
 * 不复刻的旧行为：从 localStorage 读 campusNewItem；固定写死的 detail.html?id=new。
 *
 * 依赖的接口：GET /api/items/{id}（当前返回 501）
 */
