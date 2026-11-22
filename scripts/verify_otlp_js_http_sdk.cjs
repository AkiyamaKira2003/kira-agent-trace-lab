/* Optional official JS SDK OTLP/HTTP JSON interoperability proof.
 * Synthetic, loopback-only. Never instruments an owner application or invokes
 * any recorded tool. Install pinned optional dependencies in ignored artifacts/.
 */
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { createRequire } = require('node:module');
const project = path.resolve(__dirname, '..');
const lab = path.join(project, 'artifacts', 'atl004di_js_otlp_http');
const runName = process.argv[2] || 'capture_01';
if (!/^capture_[a-z0-9_-]{2,40}$/.test(runName)) {
  throw new Error('Choose a synthetic output name like capture_02');
}
if (!fs.existsSync(path.join(lab, 'node_modules'))) {
  throw new Error('Install the documented optional pinned OpenTelemetry SDK packages first');
}
const outputDir = path.join(lab, runName);
if (fs.existsSync(outputDir)) {
  if (fs.readdirSync(outputDir).length > 0) throw new Error('Refusing to overwrite prior capture');
} else {
  fs.mkdirSync(outputDir);
}

const sdkRequire = createRequire(path.join(lab, 'synthetic-sdk-root.cjs'));
const api = sdkRequire('@opentelemetry/api');
const { NodeTracerProvider, BatchSpanProcessor } = sdkRequire('@opentelemetry/sdk-trace-node');
const { OTLPTraceExporter } = sdkRequire('@opentelemetry/exporter-trace-otlp-http');
const { resourceFromAttributes } = sdkRequire('@opentelemetry/resources');
const required = [
  '@opentelemetry/api',
  '@opentelemetry/sdk-trace-node',
  '@opentelemetry/exporter-trace-otlp-http',
  '@opentelemetry/resources',
];
const versions = Object.fromEntries(required.map(id => [
  id,
  JSON.parse(fs.readFileSync(path.join(lab, 'node_modules', ...id.split('/'), 'package.json'), 'utf8')).version,
]));
const expectedVersions = {
  '@opentelemetry/api':'1.9.0',
  '@opentelemetry/sdk-trace-node':'2.12.0',
  '@opentelemetry/exporter-trace-otlp-http':'0.300.0',
  '@opentelemetry/resources':'2.12.0',
};
if (JSON.stringify(versions) !== JSON.stringify(expectedVersions)) {
  throw new Error('Unexpected SDK versions; do not compare unpinned exporter behavior');
}

let batches = [];
const server = http.createServer((req, res) => {
  if (req.method !== 'POST' || req.url !== '/v1/traces') {
    res.writeHead(404); res.end(); return;
  }
  if (['authorization', 'cookie', 'proxy-authorization'].some(h => h in req.headers)) {
    res.writeHead(400); res.end('Unexpected inherited authentication headers'); return;
  }
  const chunks = [];
  let bytes = 0;
  let oversized = false;
  req.on('data', chunk => {
    if (oversized) return;
    bytes += chunk.length;
    if (bytes > 512 * 1024) {
      oversized = true;
      chunks.length = 0;
      res.writeHead(413);
      res.end('Synthetic payload exceeds the test limit');
      return;
    }
    chunks.push(chunk);
  });
  req.on('end', () => {
    if (oversized) return;
    const raw = Buffer.concat(chunks);
    batches.push({
      method: req.method,
      url: req.url,
      contentType: req.headers['content-type'] || '',
      contentEncoding: req.headers['content-encoding'] || '',
      body: raw.toString('utf8'),
    });
    res.writeHead(200, {'Content-Type':'application/json'});
    res.end('{}');
  });
});

async function run() {
  let provider;
  try {
    await new Promise((resolve, reject) => {
      server.once('error',reject);
      server.listen(0,'127.0.0.1',resolve);
    });
    const address = server.address();
    if (address.address !== '127.0.0.1') throw new Error('receiver bound beyond loopback');
    const exporter = new OTLPTraceExporter({
      url:'http://127.0.0.1:' + address.port + '/v1/traces',
      timeoutMillis:3000,
      headers: {'x-atl004di-synthetic': '1'},
    });
    let spanCounter = 0;
    const generator = {
      generateTraceId:()=> '1234567890abcdef1234567890abcdef',
      generateSpanId:()=> {
        spanCounter += 1;
        return ('0000000000000000' + spanCounter.toString(16)).slice(-16);
      },
    };
    provider = new NodeTracerProvider({
      idGenerator: generator,
      resource: resourceFromAttributes({'service.name':'atl004di-synthetic'}),
      spanProcessors:[new BatchSpanProcessor(exporter, {
        maxExportBatchSize: 20,
        scheduledDelayMillis: 30000,
        exportTimeoutMillis: 4000,
      })],
    });
    provider.register();
    const tracer = api.trace.getTracer('synthetic-atl004di', '1.0');
    const parent = tracer.startSpan('synthetic-parent', {
      startTime: [1700000000, 0],
    });
    api.context.with(api.trace.setSpan(api.context.active(), parent), () => {
      const fileSpan = tracer.startSpan('execute_tool files.read', {
        startTime:[1700000000,0],
        attributes: {
          'gen_ai.operation.name': 'execute_tool',
          'gen_ai.tool.name': 'files.read',
          'gen_ai.tool.call.arguments':JSON.stringify({path:'/synthetic/readme.txt'}),
        },
      });
      fileSpan.end([1700000000,1000000]);
      const docsSpan = tracer.startSpan('execute_tool docs.search', {
        startTime:[1700000000,2000000],
        attributes: {
          'gen_ai.operation.name':'execute_tool',
          'gen_ai.tool.name':'docs.search',
          'gen_ai.tool.call.arguments':JSON.stringify({query:'synthetic only'}),
        },
      });
      docsSpan.end([1700000000,3000000]);
    });
    parent.end([1700000000,4000000]);
    let flushTimer;
    try {
      await Promise.race([
        provider.forceFlush(),
        new Promise((_, reject)=>{
          flushTimer = setTimeout(()=>reject(new Error('export flush timeout')),7000);
        }),
      ]);
    } finally {
      clearTimeout(flushTimer);
    }
    if (batches.length !== 1) throw new Error('expected exactly one exporter HTTP POST; got '+batches.length);
    const b = batches[0];
    if (!b.contentType.toLowerCase().startsWith('application/json')) {
      throw new Error('expected official OTLP http/json, got '+b.contentType);
    }
    if (b.contentEncoding) throw new Error('unexpected compression: '+b.contentEncoding);
    const doc = JSON.parse(b.body);
    const scopes = doc.resourceSpans?.flatMap(r=>r.scopeSpans||[]) || [];
    const spans = scopes.flatMap(s=>s.spans||[]);
    const tools = spans.filter(s=>s.attributes?.some(a=>a.key==='gen_ai.operation.name' && a.value?.stringValue==='execute_tool'));
    if (tools.length !== 2) throw new Error('not exactly 2 exported synthetic tool spans');
    const resourceKeys = (doc.resourceSpans[0].resource?.attributes||[]).map(a=>a.key).sort();
    if (JSON.stringify(resourceKeys) !== JSON.stringify(['service.name'])) {
      throw new Error('Refusing to publish a payload containing unexpected environment-derived resource attributes');
    }
    for(const s of tools) {
      if (!/^[0-9a-f]{32}$/i.test(s.traceId) || !/^[0-9a-f]{16}$/i.test(s.spanId)) {
        throw new Error('actual JS exporter emitted unexpected trace/span ID format');
      }
    }
    const actualPath = path.join(outputDir, 'captured-official-js-otlp.json');
    fs.writeFileSync(actualPath, JSON.stringify(doc,null,2)+'\n', {flag:'wx'});
    const argsPath = path.join(outputDir, 'captured-request-metadata.json');
    fs.writeFileSync(argsPath, JSON.stringify({method:b.method,url:b.url,contentType:b.contentType,
      contentEncoding:b.contentEncoding,receivedBytes:Buffer.byteLength(b.body),
      payloadSha256:crypto.createHash('sha256').update(b.body).digest('hex'),
      packageVersions:versions}, null,2)+'\n',{flag:'wx'});
    const code = [
      'import json,sys',
      'from pathlib import Path',
      'sys.path.insert(0,sys.argv[1])',
      'from agent_trace_lab.otlp import import_otlp',
      'from agent_trace_lab.schema import load_suite,SuiteError',
      'doc=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))',
      'p=load_suite(Path(sys.argv[1])/"examples"/"suite.json")["policy"]',
      'r=import_otlp(doc,policy=p,case_id="js_sdk_live_http",expected="deny")',
      'case=r["cases"][0]',
      'assert case["expected"]=="deny" and "task_authorization" not in case',
      'assert case["trace"]==[{"tool":"files.read","arguments":{"path":"/synthetic/readme.txt"}},{"tool":"docs.search","arguments":{"query":"synthetic only"}}]',
      'import subprocess',
      'source=Path(sys.argv[2])',
      'output=source.parent/"cli-valid-output.json"',
      'command=[sys.executable,"-m","agent_trace_lab","import-otlp",str(source),"--policy-suite",str(Path(sys.argv[1])/"examples"/"suite.json"),"--case-id","js_sdk_live_http","--expected","deny","--output",str(output)]',
      'good=subprocess.run(command,cwd=sys.argv[1],capture_output=True,text=True,timeout=15)',
      'assert good.returncode==0 and output.exists(),good.stderr',
      'assert json.loads(output.read_text(encoding="utf-8"))["cases"][0]["trace"]==case["trace"]',
      'from copy import deepcopy',
      'bad=deepcopy(doc)',
      'bad["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"]="bad-value"',
      'marker="SYNTHETIC_PRIVATE_004DI_DO_NOT_ECHO"',
      'bad["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"][2]["value"]={"stringValue":json.dumps({"path":marker})}',
      'try:import_otlp(bad,policy=p,case_id="invalid",expected="allow")',
      'except SuiteError:pass',
      'else:raise AssertionError("invalid ID was accepted")',
      'bad_file=source.parent/"synthetic-invalid.json"',
      'bad_file.write_text(json.dumps(bad),encoding="utf-8")',
      'no_write=source.parent/"cli-invalid-must-not-write.json"',
      'bad_command=[sys.executable,"-m","agent_trace_lab","import-otlp",str(bad_file),"--policy-suite",str(Path(sys.argv[1])/"examples"/"suite.json"),"--case-id","invalid","--expected","allow","--output",str(no_write)]',
      'failed=subprocess.run(bad_command,cwd=sys.argv[1],capture_output=True,text=True,timeout=15)',
      'assert failed.returncode==2 and marker not in failed.stdout+failed.stderr and "Traceback" not in failed.stderr',
      'assert not no_write.exists(),"invalid import published a partial file"',
      'for r in bad["resourceSpans"]:',
      '  for sc in r.get("scopeSpans",[]):',
      '    sc["spans"]=[s for s in sc.get("spans",[]) if not any(a.get("key")=="gen_ai.operation.name" and a.get("value",{}).get("stringValue")=="execute_tool" for a in s.get("attributes",[]))]',
      'try:import_otlp(bad,policy=p,case_id="empty",expected="allow")',
      'except SuiteError:pass',
      'else:raise AssertionError("empty trace accepted")',
      'print("PY_IMPORT_PASS=2 recorded synthetic calls; good CLI PASS; bad CLI exit 2 with no leak/output; no-tool rejected")',
    ].join('\n');
    const python = spawnSync('python',['-c',code,project,actualPath],{
      cwd:project,encoding:'utf8',timeout:15000,windowsHide:true,
    });
    if(python.status!==0 || python.error) {
      throw new Error('Python importer validation failed: '+(python.stderr||python.error));
    }
    console.log(python.stdout.trim());
    console.log(JSON.stringify({receiver:'127.0.0.1',
      contentType:b.contentType,spans:spans.length,toolSpans:tools.length,
      traceId:tools[0].traceId,spanId:tools[0].spanId,
      versions,hash:crypto.createHash('sha256').update(b.body).digest('hex')},null,2));
  } finally {
    try {
      if (provider) await provider.shutdown();
    } finally {
      if (server.listening) {
        await new Promise(resolve => server.close(resolve));
      }
    }
  }
}
run().catch(error => { console.error(error); process.exitCode=1; });
