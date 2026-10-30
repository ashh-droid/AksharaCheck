/*
 * Letter rules for the in-browser text checker, the same idea as the scanner's
 * broken-letter detector: a vowel sign, nukta or virama needs a consonant
 * before it, and a sign must come from the same script as its letter.
 * Covers Devanagari and Kannada.
 */

export type LetterProblem = { index: number; title: string; hint: string; character: string };

type Kind = 'cons' | 'vowel' | 'matra' | 'nukta' | 'virama' | 'mod' | 'joiner' | 'other' | 'none';
type Info = { type: Kind; script?: 'deva' | 'knda' };

export const codepoint = (ch: string) => ch.codePointAt(0) || 0;
const within = (c: number, a: number, b: number) => c >= a && c <= b;

function classify(ch: string | undefined): Info {
  if (!ch) return { type: 'none' };
  const c = codepoint(ch);
  if (c === 0x200c || c === 0x200d) return { type: 'joiner' };
  if (within(c, 0x0900, 0x097f)) {
    const script = 'deva' as const;
    if (within(c, 0x0915, 0x0939) || within(c, 0x0958, 0x095f) || within(c, 0x0978, 0x097f)) return { type: 'cons', script };
    if (within(c, 0x0904, 0x0914) || within(c, 0x0960, 0x0961) || within(c, 0x0972, 0x0977) || c === 0x093d) return { type: 'vowel', script };
    if (within(c, 0x093a, 0x093b) || within(c, 0x093e, 0x094c) || within(c, 0x094e, 0x094f) || within(c, 0x0955, 0x0957) || within(c, 0x0962, 0x0963))
      return { type: 'matra', script };
    if (c === 0x093c) return { type: 'nukta', script };
    if (c === 0x094d) return { type: 'virama', script };
    if (within(c, 0x0900, 0x0903)) return { type: 'mod', script };
    return { type: 'other', script };
  }
  if (within(c, 0x0c80, 0x0cff)) {
    const script = 'knda' as const;
    if (within(c, 0x0c95, 0x0cb9) || within(c, 0x0cdd, 0x0cde)) return { type: 'cons', script };
    if (within(c, 0x0c85, 0x0c94) || within(c, 0x0ce0, 0x0ce1) || c === 0x0cbd) return { type: 'vowel', script };
    if (within(c, 0x0cbe, 0x0ccc) || within(c, 0x0cd5, 0x0cd6) || within(c, 0x0ce2, 0x0ce3)) return { type: 'matra', script };
    if (c === 0x0cbc) return { type: 'nukta', script };
    if (c === 0x0ccd) return { type: 'virama', script };
    if (within(c, 0x0c80, 0x0c83) || c === 0x0cf3) return { type: 'mod', script };
    return { type: 'other', script };
  }
  return { type: 'none' };
}

const MARK_NAMES: Partial<Record<Kind, string>> = { matra: 'vowel sign', nukta: 'nukta', virama: 'virama', mod: 'sign' };
const SCRIPT_NAMES = { deva: 'Devanagari', knda: 'Kannada' };
const onCircle = (ch: string) => '◌' + ch;
// Vowel signs typed onto a vowel letter where a single letter exists.
const VOWEL_FIXES: Record<string, string> = { 'अा': 'आ', 'अो': 'ओ', 'अौ': 'औ', 'अॅ': 'ॲ', 'अॉ': 'ऑ', 'एे': 'ऐ', 'ಒೌ': 'ಔ' };
// Two signs typed where one exists.
const TWO_SIGN_FIXES: Record<string, string> = { 'ाे': 'ो', 'ाै': 'ौ', 'ेे': 'ै' };

function describe(ch: string | undefined) {
  if (ch === undefined) return 'the start of the text';
  if (ch === ' ' || ch === ' ') return 'a space';
  if (ch === '\n') return 'a line break';
  if (/\p{Nd}/u.test(ch)) return 'a number';
  if (/\p{P}/u.test(ch)) return `the “${ch}”`;
  if (/\p{Script=Latin}/u.test(ch)) return 'a Latin letter';
  return `“${ch}”`;
}

export function checkText(text: string): LetterProblem[] {
  const chars = Array.from(text);
  const problems: LetterProblem[] = [];
  let prev: Info = { type: 'none' };
  chars.forEach((ch, i) => {
    const cur = classify(ch);
    const before = chars[i - 1];
    const add = (title: string, hint: string) => problems.push({ index: i, title, hint, character: ch });
    if (['joiner', 'none', 'other', 'cons', 'vowel'].includes(cur.type)) {
      prev = cur;
      return;
    }
    const name = MARK_NAMES[cur.type] || 'sign';
    const shown = onCircle(ch);
    const hasBase = prev.type === 'cons' || prev.type === 'nukta';
    if (prev.script && cur.script && prev.script !== cur.script) {
      add(`${shown} is a ${SCRIPT_NAMES[cur.script]} ${name} on a ${SCRIPT_NAMES[prev.script]} letter`, 'A sign must come from the same script as its letter. This often happens when text is copied between documents.');
    } else if (cur.type === 'matra') {
      if (hasBase || (prev.type === 'matra' && (before + ch).normalize('NFC').length === 1)) {
        // fine: a consonant, or a two-part vowel sign typed in two pieces
      } else if (prev.type === 'vowel') {
        const fix = VOWEL_FIXES[before + ch];
        add(`${shown} is attached to the vowel ${before}`, fix ? `Type the single letter ${fix} instead.` : 'Vowel signs go on consonants, not on vowel letters.');
      } else if (prev.type === 'mod') {
        const base = chars[i - 2];
        add(
          `${shown} comes after ${onCircle(before)}`,
          classify(base).type === 'cons' ? `Type the vowel sign first: ${base}${ch}${before}, not ${base}${before}${ch}.` : 'Type the vowel sign before the other sign.',
        );
      } else if (prev.type === 'matra') {
        const fix = TWO_SIGN_FIXES[before + ch];
        add(
          `Two vowel signs in a row: ${onCircle(before)} and ${shown}`,
          fix ? `Together they look like ${onCircle(fix)}. Type that single sign instead.` : 'A consonant takes one vowel sign. One of them is probably a typing mistake.',
        );
      } else {
        add(`${shown} has nothing to attach to`, `A vowel sign must come right after a consonant. Here it follows ${describe(before)}.`);
      }
    } else if (cur.type === 'nukta') {
      if (prev.type !== 'cons') {
        const base = prev.type === 'matra' ? chars[i - 2] : undefined;
        add(
          `${shown} is in the wrong place`,
          base && classify(base).type === 'cons'
            ? `The nukta goes straight after its consonant: ${base}${ch}${before}, not ${base}${before}${ch}.`
            : `The nukta goes straight after a consonant. Here it follows ${describe(before)}.`,
        );
      }
    } else if (cur.type === 'virama') {
      if (!hasBase) add(`${shown} has nothing to attach to`, `The virama (halant) must come right after a consonant. Here it follows ${describe(before)}.`);
    } else if (cur.type === 'mod') {
      if (!(hasBase || prev.type === 'matra' || prev.type === 'vowel'))
        add(`${shown} has nothing to attach to`, `Anusvara, chandrabindu and visarga follow a letter or a vowel sign. Here it follows ${describe(before)}.`);
    }
    prev = cur;
  });
  return problems.slice(0, 30);
}
