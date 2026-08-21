#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const installScript = join(__dirname, '..', 'install.py');

const proc = spawn('python3', [installScript, ...process.argv.slice(2)], {
  stdio: 'inherit'
});

proc.on('exit', (code) => {
  process.exit(code ?? 0);
});
