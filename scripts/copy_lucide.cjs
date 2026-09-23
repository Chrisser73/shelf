/* Make the pinned Lucide browser bundle available without a public CDN. */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const source = path.join(root, 'node_modules', 'lucide', 'dist', 'umd', 'lucide.min.js');
const destination = path.join(root, 'static', 'vendor', 'lucide-1.47.0.min.js');

if (!fs.existsSync(source)) {
  throw new Error('Lucide is not installed. Run the project dependency install first.');
}
fs.copyFileSync(source, destination);
console.log('Copied Lucide 1.47.0 to static/vendor');
