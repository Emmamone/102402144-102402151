/* 服务端接口的唯一出口。
 *
 * 约定（见 docs/coding-standards.md 第 5.2 节）：页面脚本里**不得**直接出现
 * fetch，所有请求都经由本文件。
 */

var API_BASE = '/api';

/**
 * 发起请求并把响应解析成 JSON。
 * 非 2xx 时抛出带 message / status 的 Error，由调用方决定如何提示。
 */
function apiRequest(path, options) {
  return fetch(API_BASE + path, options).then(function (response) {
    return response
      .json()
      .catch(function () {
        return {};
      })
      .then(function (body) {
        if (!response.ok) {
          var message = (body && (body.message || body.detail)) || '请求失败';
          var error = new Error(typeof message === 'string' ? message : '请求失败');
          error.status = response.status;
          throw error;
        }
        return body;
      });
  });
}

var API = {
  /**
   * 取首页「最新信息」列表。
   *
   * @param {string} type 'all' / 'seek' / 'find'，省略时为 'all'
   * @returns {Promise<{count: number, items: Array}>} count 是当前筛选下的真实条数
   *
   * 已实现。服务端只返回首页该显示的条目（不含只在搜索页出现的 7、8 号），
   * 并已按顺序排好，前端拿到直接渲染即可，不要再排序或过滤。
   */
  home: function (type) {
    return apiRequest('/items/home?type=' + encodeURIComponent(type || 'all'));
  },

  /**
   * 搜索物品。
   *
   * @param {string} keyword 关键词，空串表示不按关键词过滤
   * @param {string} type    'all' / 'seek' / 'find'
   * @returns {Promise<{count: number, items: Array}>}
   *
   * 尚未实现（后端返回 501）。匹配由服务端做（对搜索索引文本做子串匹配），
   * 前端不要再对 data-keywords 做一次匹配，否则会变成双重过滤。
   */
  search: function (keyword, type) {
    return apiRequest(
      '/items/search?q=' + encodeURIComponent(keyword || '') + '&type=' + encodeURIComponent(type || 'all')
    );
  },

  /**
   * 取单条物品的完整详情。
   *
   * @param {number|string} id 物品 id（正整数）
   * @returns {Promise<Object>} DetailItem：含 code、publisher、masked、contact 等
   *          只在这里才出现的字段
   *
   * 尚未实现（后端返回 501，id 不存在时会是 404）。404 时调用方应回落到 id=1。
   * 不再有 'new' 这个特殊值——新发布的信息有真实 id。
   */
  detail: function (id) {
    return apiRequest('/items/' + encodeURIComponent(id));
  },

  /**
   * 发布一条信息。
   *
   * @param {Object} payload {name, type, category, time, place, desc, contact}
   * @returns {Promise<Object>} 完整 DetailItem，含服务端生成的 id
   *
   * 尚未实现（后端返回 501）。状态、图标、发布者、头像、脱敏串、搜索索引、发布时间
   * 全部由服务端补全，**前端不要传这些字段**。成功后拿返回的 id 跳
   * success.html?id=<id>。
   */
  create: function (payload) {
    return apiRequest('/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  /**
   * 把一条信息标记为已解决。
   *
   * @param {number|string} id 物品 id
   * @returns {Promise<Object>} 更新后的 DetailItem（status 为 resolved）
   *
   * 尚未实现（后端返回 501）。服务端幂等：对已解决的条目重复调用不报错。
   */
  resolve: function (id) {
    return apiRequest('/items/' + encodeURIComponent(id) + '/resolve', { method: 'POST' });
  }
};
