export function stringifyJson(value) {
  if (!value || typeof value !== "object" || !Object.keys(value).length) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

export function diffJsonLines(oldText, newText) {
  const oldLines = oldText ? oldText.split("\n") : [];
  const newLines = newText ? newText.split("\n") : [];
  const rows = oldLines.length;
  const cols = newLines.length;
  const lcs = Array.from({ length: rows + 1 }, () => Array(cols + 1).fill(0));

  for (let row = 1; row <= rows; row += 1) {
    for (let col = 1; col <= cols; col += 1) {
      if (oldLines[row - 1] === newLines[col - 1]) {
        lcs[row][col] = lcs[row - 1][col - 1] + 1;
      } else {
        lcs[row][col] = Math.max(lcs[row - 1][col], lcs[row][col - 1]);
      }
    }
  }

  const left = [];
  const right = [];
  let row = rows;
  let col = cols;

  while (row > 0 || col > 0) {
    if (row > 0 && col > 0 && oldLines[row - 1] === newLines[col - 1]) {
      left.unshift({ text: oldLines[row - 1], type: "unchanged" });
      right.unshift({ text: newLines[col - 1], type: "unchanged" });
      row -= 1;
      col -= 1;
    } else if (col > 0 && (row === 0 || lcs[row][col - 1] >= lcs[row - 1][col])) {
      left.unshift({ text: "", type: "empty" });
      right.unshift({ text: newLines[col - 1], type: "added" });
      col -= 1;
    } else {
      left.unshift({ text: oldLines[row - 1], type: "removed" });
      right.unshift({ text: "", type: "empty" });
      row -= 1;
    }
  }

  return { left, right };
}
