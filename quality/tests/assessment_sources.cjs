// Run the same controller functions in a JSDOM global scope for isolated tests.
// Production modules remain scoped to a React-owned context; no eval is shipped.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');

function readAssessmentSource(name) {
  let source = fs.readFileSync(path.join(root, name), 'utf8');
  if (name.includes('/assessment/engine/') && !name.endsWith('/index.js')) {
    source = source.replace(/^export function \w+\(ctx\) \{\r?\n/m, '')
      .replace(/^\s*const \{[\s\S]*?\} = ctx;\r?\n/m, '').replace(/\}\s*$/, '')
      .replace(/ctx\.disposed/g, 'false').replace(/ctx\./g, '');
  }
  return source;
}

function loadUtility(name) {
  const scope = { module: { exports: {} }, setTimeout, clearTimeout, setInterval, clearInterval };
  scope.document = { getElementById: () => null };
  scope.window = scope;
  const source = readAssessmentSource(name);
  if (name.endsWith('/pdf.js')) new Function('window', 'document', source)(scope, scope.document);
  else new Function('module', 'exports', source)(scope.module, scope.module.exports);
  return name.endsWith('/pdf.js') ? scope.MapPdfExport : scope.module.exports;
}

module.exports = { readAssessmentSource, loadUtility };
