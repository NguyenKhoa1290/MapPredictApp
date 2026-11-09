// Compatibility names for existing browser assertions; production uses a scoped controller.
async function exposeAssessmentState(page) {
  const fs = require('node:fs'), path = require('node:path');
  const keys = new Set();
  for (const name of ['core', 'layers']) {
    const source = fs.readFileSync(path.join(__dirname, '../../frontend/src/pages/assessment/engine', name + '.js'), 'utf8');
    for (const match of source.matchAll(/ctx\.([\w$]+)\s*=/g)) keys.add(match[1]);
  }
  await page.addInitScript(keys => {
    window.$ = id => document.getElementById(id);
    for (const key of keys.filter(key => key !== '$')) {
      Object.defineProperty(window, key, {
        configurable: true,
        get() { return window.assessmentRuntime?.state[key]; },
        set(value) { if (window.assessmentRuntime) window.assessmentRuntime.state[key] = value; },
      });
    }
  }, [...keys]);
}
module.exports = { exposeAssessmentState };
