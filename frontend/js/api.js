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
  /* 首页「最新信息」列表（已实现） */
  home: function (type) {
    return apiRequest('/items/home?type=' + encodeURIComponent(type || 'all'));
  },

  /* 以下四个接口后端已按设计注册路径，但尚未实现（当前返回 501）。
   * 对应的页面同样是占位状态，实现顺序见 docs/development-plan.md。 */
  search: function (keyword, type) {
    return apiRequest(
      '/items/search?q=' + encodeURIComponent(keyword || '') + '&type=' + encodeURIComponent(type || 'all')
    );
  },
  detail: function (id) {
    return apiRequest('/items/' + encodeURIComponent(id));
  },
  create: function (payload) {
    return apiRequest('/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },
  resolve: function (id) {
    return apiRequest('/items/' + encodeURIComponent(id) + '/resolve', { method: 'POST' });
  }
};
