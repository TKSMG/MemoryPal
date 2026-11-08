/** Serve the web export with every unknown path falling back to index.html. node serve_spa.js DIR [PORT] */
const http = require('http');
const fs = require('fs');
const path = require('path');
const [, , DIR, PORT = '8765'] = process.argv;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.ttf': 'font/ttf', '.json': 'application/json', '.ico': 'image/x-icon' };
http.createServer((req, res) => {
  let file = path.join(DIR, decodeURIComponent(req.url.split('?')[0]));
  if (!file.startsWith(path.resolve(DIR)) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(DIR, 'index.html');
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
}).listen(Number(PORT));
