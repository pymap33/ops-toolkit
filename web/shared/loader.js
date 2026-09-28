// Shared Pyodide/manifest loading logic used by every tool page in web/.
// Paths are relative to the *calling page's* URL, so every tool page must
// live directly under web/ (one level below the repo root).

export async function loadPackage(pyodide) {
  const manifestRes = await fetch("../opstoolkit/manifest.json");
  if (!manifestRes.ok) {
    throw new Error("opstoolkit/manifest.json not found -- run scripts/generate_manifest.py and commit it.");
  }
  const manifest = await manifestRes.json();

  pyodide.FS.mkdirTree("/ops_pkg/opstoolkit");
  pyodide.FS.mkdirTree("/ops_pkg/data");
  for (const f of manifest.modules) {
    const res = await fetch(`../opstoolkit/${f}`);
    pyodide.FS.writeFile(`/ops_pkg/opstoolkit/${f}`, await res.text());
  }
  for (const f of manifest.data) {
    const res = await fetch(`../data/${f}`);
    pyodide.FS.writeFile(`/ops_pkg/data/${f}`, await res.text());
  }
  pyodide.runPython(`
import sys
sys.path.insert(0, "/ops_pkg")
import opstoolkit
`);
}

export function money(x) {
  return x.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function pct(x) {
  return (x * 100).toFixed(2) + "%";
}
