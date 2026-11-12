import {readFile} from 'node:fs/promises';
const r=JSON.parse(await readFile(process.argv[2],'utf8'));
console.log(JSON.stringify({counts:r.counts,last:r.assertions.slice(-4),error:r.infrastructureError},null,2));
