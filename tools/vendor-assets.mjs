import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const destination = join(root, "automation_inspector", "www");
const assets = [
  ["@fontsource-variable/dm-sans/files/dm-sans-latin-wght-normal.woff2", "fonts/dm-sans.woff2"],
  ["@fontsource-variable/source-code-pro/files/source-code-pro-latin-wght-normal.woff2", "fonts/source-code-pro.woff2"],
  ["@fontsource-variable/dm-sans/LICENSE", "licenses/dm-sans.txt"],
  ["@fontsource-variable/source-code-pro/LICENSE", "licenses/source-code-pro.txt"],
  ["lucide-static/LICENSE", "licenses/lucide.txt"],
];
const icons = [
  "workflow", "layers", "square-terminal", "sliders-horizontal", "eye-off", "undo-2",
  "search", "refresh-cw", "sun", "moon", "chevron-down", "external-link", "activity",
  "shield-check", "list-filter", "circle-alert", "inbox",
];
for (const icon of icons) assets.push([`lucide-static/icons/${icon}.svg`, `icons/${icon}.svg`]);
for (const [source, target] of assets) {
  const output = join(destination, target);
  await mkdir(dirname(output), { recursive: true });
  await copyFile(join(root, "node_modules", source), output);
}
console.log(`Vendored ${assets.length} font, icon, and license assets.`);