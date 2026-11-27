// Test-only (tests/acceptance/test_diagram_bpmn.py): read each BPMN 2.0 XML file named on the command line with
// bpmn-moddle (pinned in tools/bpmn-check/package-lock.json; the parser bpmn-js imports with) and print one JSON
// object {file: {"warnings": [...], "rootElements": [...], "error": null | "..."}} on stdout. Not on any runtime path.
'use strict';
const fs = require('fs');
const { BpmnModdle } = require('bpmn-moddle');

(async () => {
  const out = {};
  for (const file of process.argv.slice(2)) {
    try {
      const { rootElement, warnings } = await new BpmnModdle().fromXML(fs.readFileSync(file, 'utf8'));
      out[file] = { warnings: warnings.map((w) => String(w.message)), error: null,
        rootElements: (rootElement.rootElements || []).map((e) => e.$type) };
    } catch (e) {
      out[file] = { warnings: [], rootElements: [], error: String(e && e.message || e) };
    }
  }
  process.stdout.write(JSON.stringify(out));
})();
