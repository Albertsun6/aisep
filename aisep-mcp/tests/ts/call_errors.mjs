// T34 driver: argv[2] = JSON {command, args, cwd, env, calls: [[tool, arguments], ...]}. Prints one JSON line per call:
// {tool, threw: <error message or null>, isError, code}. Uses the TS SDK v1 Client.callTool, which validates
// structuredContent against the tool's outputSchema also when isError is true (docs/mcp-interface.md §5.0).
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const spec = JSON.parse(process.argv[2]);
const transport = new StdioClientTransport({ command: spec.command, args: spec.args, cwd: spec.cwd, env: spec.env, stderr: "ignore" });
const client = new Client({ name: "aisep-t34", version: "0.0.0" });
await client.connect(transport);
await client.listTools(); // caches the output schemas the client validates against
for (const [tool, args] of spec.calls) {
  try {
    const r = await client.callTool({ name: tool, arguments: args });
    console.log(JSON.stringify({ tool, threw: null, isError: !!r.isError, code: r.structuredContent?.error?.code ?? null }));
  } catch (e) {
    console.log(JSON.stringify({ tool, threw: String(e?.message ?? e), isError: null, code: null }));
  }
}
await client.close();
