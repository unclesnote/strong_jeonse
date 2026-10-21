import fs from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),site=path.join(root,'backend/site');
// Preserve frontend originals; only recreate known generated build directories.
await fs.rm(path.join(site,'public'),{recursive:true,force:true});await fs.cp(path.join(root,'public'),path.join(site,'public'),{recursive:true});
await fs.rename(path.join(site,'public/index.html'),path.join(site,'public/map.html'));
await fs.copyFile(path.join(root,'public/competition-config.json'),path.join(site,'competition-config.json'));
await fs.copyFile(path.join(root,'.openai/hosting.json'),path.join(site,'.openai/hosting.json'));
const helper=process.env.SITES_BUILD_HELPER;if(!helper)throw Error('Set SITES_BUILD_HELPER to the Sites plugin scripts/build-site.mjs path.');
const result=spawnSync(process.execPath,[helper],{cwd:site,stdio:'inherit',env:process.env});if(result.status!==0)process.exit(result.status||1);
await fs.rm(path.join(root,'dist'),{recursive:true,force:true});await fs.cp(path.join(site,'dist'),path.join(root,'dist'),{recursive:true});console.log('Hosted Worker built in dist/');
