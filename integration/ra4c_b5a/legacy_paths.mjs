// Relocate legacy browser generated files; read accepted code in place.
// This hook does not modify browser commands, selectors, checks or SQL.
import fs from 'node:fs/promises';
import path from 'node:path';
import {syncBuiltinESMExports} from 'node:module';
const old=path.resolve('docs/03-engineering/ra4c3-pg-read');
const fresh=path.resolve(process.env.B5A_C3_ROOT);
const map=value=>typeof value==='string'&&(value.startsWith(old+path.sep+'evidence'+path.sep)||value.startsWith(old+path.sep+'runtime'+path.sep)||value===old+path.sep+'runtime')?path.join(fresh,path.relative(old,value)):value;
for(const name of ['mkdir','mkdtemp','writeFile','readFile','readdir']){
  const original=fs[name];fs[name]=function(first,...rest){return original.call(this,map(first),...rest)};
}
syncBuiltinESMExports();
