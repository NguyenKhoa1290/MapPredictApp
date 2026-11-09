import { installCore } from './core.js';
import { installLayers } from './layers.js';
import { installPersistence } from './persistence.js';
import { installAssistant } from './assistant.js';
import { installPdf } from './pdf.js';

/** Own every browser resource for one mounted React assessment workspace. */
export function createAssessmentRuntime(root, navigate) {
  const nativeWindow = window;
  const nativeDocument = document;
  const listeners = [], timeouts = new Set(), intervals = new Set(), urls = new Set();
  const previousGlobals = new Map();
  const requests = new AbortController();
  const ctx = { disposed: false, navigate };
  const elements = new Map([...root.querySelectorAll('[id]')].map(node => [node.id, node]));
  const listen = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    listeners.push(() => target.removeEventListener(type, handler, options));
  };
  const windowScope = new Proxy(nativeWindow, {
    get(target, key) {
      if (key === 'addEventListener') return (type, handler, options) => listen(target, type, handler, options);
      const value = Reflect.get(target, key, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
    set(target, key, value) {
      if (!previousGlobals.has(key)) previousGlobals.set(key, Object.getOwnPropertyDescriptor(target, key));
      return Reflect.set(target, key, value);
    },
  });
  const documentScope = new Proxy(nativeDocument, {
    get(target, key) {
      if (key === 'body') return root;
      if (key === 'getElementById') return id => root.querySelector(`[id=${JSON.stringify(String(id))}]`)
        || (ctx.disposed ? elements.get(id) : null);
      if (key === 'querySelector') return selector => root.querySelector(selector);
      if (key === 'querySelectorAll') return selector => root.querySelectorAll(selector);
      if (key === 'addEventListener') return (type, handler, options) =>
        listen(['visibilitychange', 'fullscreenchange'].includes(type) ? target : root, type, handler, options);
      const value = Reflect.get(target, key, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
  const urlScope = new Proxy(URL, {
    get(target, key) {
      if (key === 'createObjectURL') return blob => {
        const url = URL.createObjectURL(blob); urls.add(url); return url;
      };
      if (key === 'revokeObjectURL') return url => { urls.delete(url); URL.revokeObjectURL(url); };
      return Reflect.get(target, key);
    },
  });
  Object.assign(ctx, {
    window: windowScope, document: documentScope, URL: urlScope,
    L: nativeWindow.L, Basemaps: nativeWindow.Basemaps,
    WorkspaceStore: nativeWindow.WorkspaceStore, WorkspaceHistory: nativeWindow.WorkspaceHistory,
    ColorAdjustments: nativeWindow.ColorAdjustments,
    $: id => documentScope.getElementById(id),
    setTimeout(handler, delay, ...args) {
      const id = nativeWindow.setTimeout(() => {
        timeouts.delete(id); if (!ctx.disposed) handler(...args);
      }, delay);
      timeouts.add(id); return id;
    },
    clearTimeout(id) { timeouts.delete(id); nativeWindow.clearTimeout(id); },
    setInterval(handler, delay, ...args) {
      const id = nativeWindow.setInterval(() => { if (!ctx.disposed) handler(...args); }, delay);
      intervals.add(id); return id;
    },
    clearInterval(id) { intervals.delete(id); nativeWindow.clearInterval(id); },
    async fetch(input, options = {}) {
      const controller = new AbortController();
      const abort = () => controller.abort();
      const signals = [requests.signal, options.signal].filter(Boolean);
      const detach = () => signals.forEach(signal => signal.removeEventListener('abort', abort));
      for (const signal of signals) {
        if (signal.aborted) abort();
        else signal.addEventListener('abort', abort, { once: true, signal: controller.signal });
      }
      try {
        const response = await nativeWindow.fetch(input, { ...options, signal: controller.signal });
        for (const method of ['json', 'text', 'blob', 'arrayBuffer']) {
          if (typeof response[method] !== 'function') continue;
          const read = response[method].bind(response);
          response[method] = async (...args) => { try { return await read(...args); } finally { detach(); } };
        }
        return response;
      } catch (error) { detach(); throw error; }
    },
  });
  const controller = {
    state: ctx,
    setActive(active) {
      if (!active) void nativeWindow.workspacePersistence?.flush();
      else requestAnimationFrame(() => { if (!ctx.disposed) ctx.map?.invalidateSize({ pan: false }); });
    },
    dispose() {
      if (ctx.disposed) return;
      const persistence = nativeWindow.workspacePersistence;
      const saving = persistence?.flush();
      ctx.disposed = true;
      requests.abort();
      ctx.mapRequestController?.abort();
      listeners.forEach(remove => remove());
      timeouts.forEach(id => nativeWindow.clearTimeout(id));
      intervals.forEach(id => nativeWindow.clearInterval(id));
      ctx.map?.remove();
      urls.forEach(url => URL.revokeObjectURL(url));
      root.querySelectorAll('.assistant-root, .assistant-history-bar').forEach(node => node.remove());
      void Promise.resolve(saving).finally(() => persistence?.close());
      for (const [key, descriptor] of previousGlobals) {
        if (descriptor) Object.defineProperty(nativeWindow, key, descriptor);
        else delete nativeWindow[key];
      }
      if (nativeWindow.assessmentRuntime === controller) delete nativeWindow.assessmentRuntime;
    },
  };
  try {
    installLayers(ctx);
    installCore(ctx);
    installPersistence(ctx);
    installPdf(ctx);
    installAssistant(ctx);
    nativeWindow.assessmentRuntime = controller;
    return controller;
  } catch (error) {
    controller.dispose();
    throw error;
  }
}
