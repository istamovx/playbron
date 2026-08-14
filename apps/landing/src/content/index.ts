import { ru } from './ru';
import { uz, type Content } from './uz';

export type Lang = 'uz' | 'ru';

export const CONTENT: Record<Lang, Content> = { uz, ru };

/** Til almashtirgich uchun — yorliq va o'sha sahifaning boshqa tildagi manzili. */
export const LANGS: { code: Lang; label: string; href: string }[] = [
  { code: 'uz', label: 'UZ', href: '/' },
  { code: 'ru', label: 'RU', href: '/ru/' },
];

export type { Content, MockStation, StationState } from './uz';
