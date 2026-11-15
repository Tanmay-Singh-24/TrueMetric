/** A tiny pixel-art icon drawn from rows of text: "#" is a filled pixel. */
export function PixelIcon({ rows, size }: { rows: string[]; size: number }) {
  const width = rows[0].length;
  return (
    <svg
      viewBox={`0 0 ${width} ${rows.length}`}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {rows.flatMap((row, y) =>
        [...row].map((pixel, x) =>
          pixel === "#" ? <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} /> : null,
        ),
      )}
    </svg>
  );
}

export const SUN = [
  "...#...",
  ".#...#.",
  "..###..",
  "#.###.#",
  "..###..",
  ".#...#.",
  "...#...",
];

export const MOON = [
  "..###..",
  ".##....",
  "##.....",
  "##.....",
  "##.....",
  ".##....",
  "..###..",
];
