/* Optional two-POST OpenTelemetry JS HTTP JSON completeness proof.
 * Synthetic spans only; no owner application, tool execution or external traffic.
 * Requires the previously pinned, ignored artifacts/atl004di_js_otlp_http SDK.
 */
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const {createRequire} = require('node:module');

const root = path.resolve(__dirname, '..');
const sdkDir = path.join(root, 'artifacts', 'atl004di_js_otlp_http');
const labDir = path.join(root, 'artifacts', 'atl004dk_multi_post_20261122');
const name = process.argv[2] || 'batch_01';
if (!/^batch_[a-z0-9_-]{2,40}$/.test(name)) {
  throw new Error('Expected a new synthetic name like batch_01');
}
const versions = {
  '@opentelemetry/api': '1.9.0',
  '@opentelemetry/sdk-trace-node': '2.12.0',
  '@opentelemetry/exporter-trace-otlp-http': '0.300.0',
  '@opentelemetry/resources': '2.12.0',
};
for (const [pkg, expected] of Object.entries(versions)) {
  const filename = path.join(sdkDir, 'node_modules', ...pkg.split('/'), 'package.json');
  if (!fs.existsSync(filename) || JSON.parse(fs.readFileSync(filename, 'utf8')).version !== expected) {
    throw new Error('Pinned optional SDK dependency missing or incompatible');
  }
}
const requireSdk = createRequire(path.join(sdkDir, 'synthetic-sdk-root.cjs'));
const api = requireSdk('@opentelemetry/api');
const {NodeTracerProvider, BatchSpanProcessor} = requireSdk('@opentelemetry/sdk-trace-node');
const {OTLPTraceExporter} = requireSdk('@opentelemetry/exporter-trace-otlp-http');
const {resourceFromAttributes} = requireSdk('@opentelemetry/resources');
fs.mkdirSync(labDir, {recursive:true});
const outputDir = path.join(labDir, name);
fs.mkdirSync(outputDir, {recursive:false}); // fail closed on any prior run

const requests = [];
let receiverError = false;
const server = http.createServer((req, res) => {
  if (req.method !== 'POST' || req.url !== '/v1/traces' || requests.length >= 2
      || ['authorization', 'cookie', 'proxy-authorization'].some(k => k in req.headers)) {
    receiverError = true;
    res.writeHead(400); res.end(); return;
  }
  req.setTimeout(5000, () => { receiverError = true; req.destroy(); });
  const parts = [];
  let count = 0;
  let tooLarge = false;
  req.on('data', chunk => {
    count += chunk.length;
    if (count > 512 * 1024) {
      if (!tooLarge) {
        tooLarge = true;
        receiverError = true;
        res.writeHead(413); res.end();
      }
    } else {
      parts.push(chunk);
    }
  });
  req.on('end', () => {
    if (tooLarge) return;
    const body = Buffer.concat(parts);
    requests.push({
      body,
      type: req.headers['content-type'] || '',
      encoding: req.headers['content-encoding'] || '',
    });
    res.writeHead(200, {'Content-Type':'application/json'});
    res.end('{}');
  });
});

async function flush(provider) {
  let timer;
  try {
    await Promise.race([
      provider.forceFlush(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('bounded synthetic flush timed out')), 7000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function toolSpans(doc) {
  return (doc.resourceSpans || []).flatMap(r => r.scopeSpans || [])
    .flatMap(s => s.spans || [])
    .filter(s => (s.attributes || []).some(
      a => a.key === 'gen_ai.operation.name' && a.value?.stringValue === 'execute_tool'));
}

async function main() {
  let provider;
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    const addr = server.address();
    if (addr.address !== '127.0.0.1') throw new Error('receiver is not loopback only');
    let nextSpan = 0;
    provider = new NodeTracerProvider({
      idGenerator: {
        generateTraceId: () => '1234567890abcdef1234567890abcdef',
        generateSpanId: () => ('0000000000000000' + (++nextSpan).toString(16)).slice(-16),
      },
      resource: resourceFromAttributes({'service.name':'atl004dk-synthetic'}),
      spanProcessors: [new BatchSpanProcessor(new OTLPTraceExporter({
        url: 'http://127.0.0.1:' + addr.port + '/v1/traces',
        timeoutMillis: 3000,
        headers: {'x-atl004dk-synthetic': '1'},
      }), {maxExportBatchSize:20, scheduledDelayMillis:30000, exportTimeoutMillis:4000})],
    });
    provider.register();
    const tracer = api.trace.getTracer('atl004dk-synthetic');
    const parent = tracer.startSpan('synthetic-parent', {startTime:[1700000000,0]});
    function recorded(name, args, startNs) {
      api.context.with(api.trace.setSpan(api.context.active(), parent), () => {
        const span = tracer.startSpan('execute_tool ' + name, {
          startTime:[1700000000,startNs],
          attributes:{
            'gen_ai.operation.name':'execute_tool',
            'gen_ai.tool.name':name,
            'gen_ai.tool.call.arguments': JSON.stringify(args),
          },
        });
        span.end([1700000000,startNs + 1000000]);
      });
    }
    recorded('files.read', {path:'/synthetic/readme.txt'}, 1000000);
    await flush(provider);
    if (requests.length !== 1 || receiverError) throw new Error('first export was not one HTTP POST');
    recorded('docs.search', {query:'synthetic only'}, 3000000);
    parent.end([1700000000,5000000]);
    await flush(provider);
    if (requests.length !== 2 || receiverError) throw new Error('second export was not one HTTP POST');

    const docs = requests.map((r, i) => {
      if (!r.type.toLowerCase().startsWith('application/json') || r.encoding) {
        throw new Error('exporter did not transmit plain OTLP/HTTP JSON');
      }
      const doc = JSON.parse(r.body.toString('utf8'));
      const tools = toolSpans(doc);
      if (tools.length !== 1) throw new Error('expected one tool span per actual HTTP POST');
      for (const resource of doc.resourceSpans || []) {
        const keys = (resource.resource?.attributes || []).map(a => a.key);
        if (JSON.stringify(keys) !== JSON.stringify(['service.name'])) {
          throw new Error('unknown resource attributes must not be recorded');
        }
      }
      for (const tool of tools) {
        if (!/^[0-9a-f]{32}$/i.test(tool.traceId) || !/^[0-9a-f]{16}$/i.test(tool.spanId)) {
          throw new Error('invalid exporter trace/span IDs');
        }
      }
      const file = path.join(outputDir, 'http-post-' + (i + 1) + '.json');
      fs.writeFileSync(file, JSON.stringify(doc, null, 2) + '\n', {flag:'wx'});
      return doc;
    });
    if (toolSpans(docs[0])[0].traceId.toLowerCase() !== toolSpans(docs[1])[0].traceId.toLowerCase()) {
      throw new Error('two POSTs did not belong to the same synthetic trace');
    }
    const assembled = {resourceSpans: docs.flatMap(d => d.resourceSpans || [])};
    fs.writeFileSync(path.join(outputDir, 'explicitly-assembled.json'),
      JSON.stringify(assembled, null, 2) + '\n', {flag:'wx'});
    fs.writeFileSync(path.join(outputDir, 'receipt.json'), JSON.stringify({
      requests: requests.length,
      contentTypes: requests.map(r => r.type),
      payloadSha256: requests.map(r => crypto.createHash('sha256').update(r.body).digest('hex')),
      packageVersions: versions,
      exporterGeneratedTraceId: toolSpans(docs[0])[0].traceId,
      testOnly: true,
      completenessProvedOnlyForControlledTwoFlushSequence: true,
    }, null, 2) + '\n', {flag:'wx'});

    const check = String.raw`
import copy,json,subprocess,sys
from pathlib import Path
from agent_trace_lab.otlp import import_otlp
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite
root=Path(sys.argv[1]); output=Path(sys.argv[2])
policy=load_suite(root/'examples'/'suite.json')['policy']
first=load_json_document(output/'http-post-1.json')
second=load_json_document(output/'http-post-2.json')
combined=load_json_document(output/'explicitly-assembled.json')
def parsed(doc):
    result=import_otlp(doc,policy=policy,case_id='two_http_posts',expected='deny')
    assert 'task_authorization' not in result['cases'][0]
    return result['cases'][0]['trace']
assert parsed(first)==[{'tool':'files.read','arguments':{'path':'/synthetic/readme.txt'}}]
assert parsed(second)==[{'tool':'docs.search','arguments':{'query':'synthetic only'}}]
assert parsed(combined)==parsed(first)+parsed(second)
try: parsed([first,second])
except SuiteError: pass
else: raise AssertionError('undocumented list-of-batches accepted')
def cli(src,dst):
    return subprocess.run([sys.executable,'-m','agent_trace_lab','import-otlp',str(src),
      '--policy-suite',str(root/'examples'/'suite.json'),'--case-id','two_http_posts',
      '--expected','deny','--output',str(dst)],cwd=root,capture_output=True,text=True,timeout=15)
partial=output/'one-post-cli.json'
p=cli(output/'http-post-1.json',partial)
assert p.returncode==0 and len(load_json_document(partial)['cases'][0]['trace'])==1,p.stderr
full=output/'two-post-cli.json'
p=cli(output/'explicitly-assembled.json',full)
assert p.returncode==0 and load_json_document(full)['cases'][0]['trace']==parsed(combined),p.stderr
replay=copy.deepcopy(combined)
replay['resourceSpans'][1]['scopeSpans'][0]['spans'][0]['spanId']=replay['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['spanId']
assert replay['resourceSpans'][1]['scopeSpans'][0]['spans'][0]['spanId'] == replay['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['spanId']
bad=output/'duplicate-batch.json'; bad.write_text(json.dumps(replay),encoding='utf-8')
failed=output/'bad-must-not-write.json'
p=cli(bad,failed)
assert p.returncode==2 and not failed.exists() and 'Traceback' not in p.stderr,p.stderr
print('MULTI_POST_PROOF_PASS: 2 actual POSTs; each imports 1, explicit assembly imports 2; duplicate rejected; no grants inferred')
`;
    const result = spawnSync('python', ['-c', check, root, outputDir], {
      cwd: root, encoding:'utf8', timeout:20000, windowsHide:true,
    });
    if (result.error || result.status !== 0) {
      throw new Error('Offline importer / CLI proof failed: ' + (result.stderr || result.error));
    }
    console.log(result.stdout.trim());
    console.log(JSON.stringify({
      status:'TWO_REAL_HTTP_POSTS_VERIFIED',
      receiver:'127.0.0.1',
      requests:requests.length,
      perPostToolCounts:docs.map(d=>toolSpans(d).length),
      combinedToolCount:toolSpans(assembled).length,
      payloadHashes:requests.map(r=>crypto.createHash('sha256').update(r.body).digest('hex')),
      versions,
    }));
  } finally {
    try {
      if (provider) await provider.shutdown();
    } finally {
      if (server.listening) await new Promise(resolve=>server.close(resolve));
    }
  }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
