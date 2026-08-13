import { useEffect, useState } from 'react';

/** CSS media so'rovini React holatiga bog'laydi. SSR'da `false` qaytaradi. */
export function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  );

  useEffect(() => {
    const list = window.matchMedia(query);
    const onChange = (): void => setMatches(list.matches);
    onChange();
    list.addEventListener('change', onChange);
    return () => list.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/**
 * Telefon kengligi. Jadval kartaga, ikki ustun bitta ustunga aylanadigan chegara —
 * `--nav-w` bilan bir qatorda ikkinchi ustun sig'maydigan nuqta.
 */
export const useNarrow = (): boolean => useMedia('(max-width: 720px)');
