/* 信息详情页 —— 占位，尚未实现。
 *
 * 待实现内容（见 docs/system-design.md 第 7.2 节与 docs/development-plan.md 阶段 3 / 4）：
 *   - loadItem()     ：取 ?id → API.detail(id)；404 或参数缺失时回落 id=1
 *   - render(it)     ：写入 #dCode #dName #dType #dIcon #dIconBox #dPublish
 *                      #dPublishRow #dCategory #dTimeLabel #dTime #dPlace #dDesc
 *                      #dAvatar #dPublisher #dContactMask #dContactFull
 *   - applyStatus()  ：#dStatus 文案与配色、#dResolveBtn 的禁用态与 #dResolveText
 *   - revealContact()：隐藏按钮、展开 #dContactRevealed 面板并提示
 *   - markResolved() ：API.resolve(id) 后用返回数据重新渲染
 *
 * 不复刻的旧行为：页面内嵌数据对象、?id=new 特殊值、localStorage 的
 * campusResolved / campusNewItem。脱敏串由服务端返回 masked。
 *
 * 依赖的接口：GET /api/items/{id}、POST /api/items/{id}/resolve（当前均返回 501）
 */
