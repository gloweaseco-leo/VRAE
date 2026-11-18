import net from 'node:net';
const mode=process.argv[2];
if(mode==='early') { process.stderr.write('synthetic-secret-never-persist');process.exitCode=7; }
else if(mode==='normal') process.exitCode=0;
else if(mode==='alive') setInterval(()=>{},1000);
else if(mode==='endpoint-closed') {
  const server=net.createServer();
  server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>{
    process.stderr.write(`DevTools listening on ws://127.0.0.1:${port}/devtools/browser/synthetic\n`);
  });});
  setInterval(()=>{},1000);
} else if(mode==='endpoint') {
  const server=net.createServer(s=>s.end());
  server.listen(0,'127.0.0.1',()=>process.stderr.write(`DevTools listening on ws://127.0.0.1:${server.address().port}/devtools/browser/synthetic\n`));
} else throw Error('UNKNOWN_FIXTURE');
