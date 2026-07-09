import type { ReactNode } from "react";

// Design §7 Layout JSON coloring: keys #7c3aed, strings #15803d,
// numbers #b45309, booleans/null #0369a1.
const TOKEN_RE = /("(?:[^"\\]|\\.)*")(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;

function colorize(json: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of json.matchAll(TOKEN_RE)) {
    const [full, str, colon] = match;
    const start = match.index ?? 0;
    if (start > last) nodes.push(json.slice(last, start));
    let color = "#0369a1";
    if (str) color = colon ? "#7c3aed" : "#15803d";
    else if (/^-?\d/.test(full)) color = "#b45309";
    nodes.push(
      <span key={key++} style={{ color }}>
        {str ?? full}
      </span>,
    );
    if (str && colon) nodes.push(colon);
    last = start + full.length;
  }
  nodes.push(json.slice(last));
  return nodes;
}

export function MaterialJson({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2) ?? "null";
  return (
    <pre className="overflow-x-auto rounded-xl bg-[#fbfbfd] p-4 font-mono text-[12px] leading-[1.75] text-body">
      {colorize(json)}
    </pre>
  );
}
