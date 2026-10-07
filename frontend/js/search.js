/* 搜索结果页 —— 占位，尚未实现。
 *
 * 待实现内容（见 docs/system-design.md 第 7.2 节与 docs/development-plan.md 阶段 3）：
 *   - runSearch()   ：API.search(kw, currentType) → renderCard(item, 'search') 渲染
 *   - setFilter() / onSubmitSearch() / quickSearch()
 *   - #resultCount 取接口的 count；count === 0 时切换到 #emptyState
 *   - 保留 #kw 的默认值「校园卡」与 #kwEcho 的前端回显
 *
 * 依赖的接口：GET /api/items/search（后端已注册，当前返回 501）
 *
 * 页面脚本的约定：函数必须是全局函数声明（页面里有行内 onclick），
 * 请求一律走 js/api.js，不要直接用 fetch。
 */
