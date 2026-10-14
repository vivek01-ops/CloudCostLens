/* Attach the per-session CSRF token to every state-changing fetch() call.
   The token is rendered into <meta name="csrf-token">; the server validates it
   against the signed session cookie. Loaded from <head> before any other script. */
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta || !meta.content) return;
  var token = meta.content;
  var safe = { GET: 1, HEAD: 1, OPTIONS: 1, TRACE: 1 };
  var orig = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    var method = init.method;
    if (!method && input && typeof input === 'object' && input.method) method = input.method;
    method = (method || 'GET').toUpperCase();
    if (!safe[method]) {
      var source = init.headers || (input && typeof input === 'object' ? input.headers : undefined);
      var headers = new Headers(source || {});
      if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', token);
      init.headers = headers;
    }
    return orig(input, init);
  };
})();
