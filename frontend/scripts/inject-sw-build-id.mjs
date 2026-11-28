// Replaces __BUILD_ID__ in dist/sw.js with the git short SHA (or a
// timestamp fallback when git is unavailable). Fails the build if the
// placeholder survives — a worker with a literal __BUILD_ID__ would
// share one cache name across deploys and updates would stop working.
import { execSync } from 'node:child_process';
import fs from 'node:fs';

const p = 'dist/sw.js';
let id = process.env.BUILD_ID;
if (!id) {
  try {
    id = execSync('git rev-parse --short HEAD').toString().trim();
  } catch {
    id = Date.now().toString(36);
  }
}
const src = fs.readFileSync(p, 'utf8');
if (!src.includes('__BUILD_ID__')) {
  throw new Error('dist/sw.js has no __BUILD_ID__ placeholder to replace');
}
fs.writeFileSync(p, src.replaceAll('__BUILD_ID__', id));
console.log(`sw.js BUILD_ID=${id}`);
