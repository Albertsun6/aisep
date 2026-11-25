// ELK graph (JSON) on stdin -> laid-out ELK graph (JSON) on stdout. Called by aisep/diagram.py; holds no options of
// its own: every layout option, including elk.randomSeed, comes from the caller so the output is reproducible.
'use strict';
const ELK = require('elkjs/lib/elk.bundled.js');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  new ELK().layout(JSON.parse(input))
    .then((g) => { process.stdout.write(JSON.stringify(g)); })
    .catch((e) => { process.stderr.write(String(e && e.stack || e) + '\n'); process.exit(1); });
});
