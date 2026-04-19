/**
 * Fuzzy string matching using Levenshtein distance.
 * Used to match spoken recipient names to saved contacts.
 */

export function levenshtein(a: string, b: string): number {
  const matrix: number[][] = [];
  const al = a.length;
  const bl = b.length;

  for (let i = 0; i <= al; i++) matrix[i] = [i];
  for (let j = 0; j <= bl; j++) matrix[0][j] = j;

  for (let i = 1; i <= al; i++) {
    for (let j = 1; j <= bl; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,     // deletion
        matrix[i][j - 1] + 1,     // insertion
        matrix[i - 1][j - 1] + cost, // substitution
      );
    }
  }

  return matrix[al][bl];
}

export function fuzzyMatch(query: string, candidates: string[], threshold = 0.6): string | null {
  const q = query.toLowerCase().trim();
  let bestMatch: string | null = null;
  let bestScore = 0;

  for (const name of candidates) {
    const n = name.toLowerCase().trim();
    const maxLen = Math.max(q.length, n.length);
    if (maxLen === 0) continue;

    const distance = levenshtein(q, n);
    const similarity = 1 - distance / maxLen;

    if (similarity > bestScore && similarity >= threshold) {
      bestScore = similarity;
      bestMatch = name;
    }
  }

  return bestMatch;
}
