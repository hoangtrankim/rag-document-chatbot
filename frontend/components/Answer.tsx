import { Fragment } from "react";

type Props = { text: string; onCite: (n: number) => void; validNumbers: Set<number> };

/** Renders an answer: paragraphs, "- " bullet lists, **bold**, and [n] citation chips. */
export default function Answer({ text, onCite, validNumbers }: Props) {
  const blocks = text.split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        const isList = lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l) || !l.trim());
        if (isList) {
          return (
            <ul key={i}>
              {lines.filter((l) => l.trim()).map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*([-*]|\d+\.)\s+/, ""), onCite, validNumbers)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {inline(l, onCite, validNumbers)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

function inline(line: string, onCite: (n: number) => void, valid: Set<number>) {
  return line.split(/(\[\d+\]|\*\*[^*]+\*\*)/g).map((part, i) => {
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite && valid.has(Number(cite[1]))) {
      const n = Number(cite[1]);
      return (
        <button key={i} className="cite" onClick={() => onCite(n)} title={`Show source ${n}`}>
          {n}
        </button>
      );
    }
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}
