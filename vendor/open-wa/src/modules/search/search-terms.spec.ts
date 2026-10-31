import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { searchTermCount } from './search-terms';

const chars = (...codePoints: number[]): string => String.fromCodePoint(...codePoints);

describe('searchTermCount', () => {
  it('counts a run of letters or digits as one word and ASCII punctuation as a separator', () => {
    expect(searchTermCount('hello')).toBe(1);
    expect(searchTermCount('hello world')).toBe(2);
    expect(searchTermCount('a.b.c')).toBe(3);
    expect(searchTermCount('user@example.com')).toBe(3);
    expect(searchTermCount('2024-10-14')).toBe(3);
  });

  it('counts a whitespace-separated word said again once', () => {
    expect(searchTermCount('hi hi hi')).toBe(1);
    expect(searchTermCount('a.b a.b')).toBe(2);
  });

  it('counts a word with no letter or digit as one', () => {
    expect(searchTermCount('!!!')).toBe(1);
  });

  it('keeps the words of non-Latin text whole', () => {
    expect(searchTermCount('привет мир')).toBe(2);
    expect(searchTermCount('こんにちは')).toBe(1);
  });

  it('keeps an ordinary sentence of a script with vowel signs and joiners under the 32-word limit', () => {
    // Combining marks and joiners between letters add no word, as the index splits on them too.
    expect(searchTermCount('मैं आज शाम को बाज़ार जाकर कुछ ताज़ी सब्ज़ियाँ और फल खरीदूँगा')).toBeLessThanOrEqual(32);
    expect(searchTermCount('نمی\u200Cخواهم')).toBe(2);
    expect(searchTermCount('క్రమం తెలుగు')).toBeLessThanOrEqual(8);
    // A mark or a symbol that stands alone, or a run of them, still counts.
    expect(searchTermCount(chars(0x0301))).toBe(1);
    expect(searchTermCount(chars(0x1f923).repeat(10))).toBe(5);
    expect(searchTermCount(`${chars(0x1f923)}${chars(0xb7)}`.repeat(10))).toBe(10);
  });

  it('counts a character the index may split on, or glue, one by one', () => {
    // A letter its tokenizer still splits on, a private-use character and an emoji its Unicode table
    // predates: each is a word of its own between separators or next to a letter.
    for (const c of [chars(0x1cf2), chars(0xe000), chars(0x1f923), chars(0x1f3fb)]) {
      expect(searchTermCount(`${c}.`.repeat(40))).toBeGreaterThanOrEqual(40);
      expect(searchTermCount(`a${c}`.repeat(40))).toBeGreaterThanOrEqual(40);
    }
  });

  describe('against the bundled SQLite', () => {
    let ds: DataSource;
    beforeAll(async () => {
      ds = new DataSource({ type: 'better-sqlite3', database: ':memory:' });
      await ds.initialize();
      await ds.query('CREATE VIRTUAL TABLE glue USING fts5(body)');
      await ds.query("CREATE VIRTUAL TABLE glue_tokens USING fts5vocab(glue, 'instance')");
      await ds.query('CREATE VIRTUAL TABLE split USING fts5(body)');
      await ds.query("CREATE VIRTUAL TABLE split_tokens USING fts5vocab(split, 'instance')");
      // Every code point but the surrogates, generated inside SQLite: c.c is two tokens when the index
      // treats c as part of a word, and aca is two when it treats c as a separator.
      const codePoints = 'WITH RECURSIVE n(c) AS (SELECT 1 UNION ALL SELECT c + 1 FROM n WHERE c < 1114111)';
      await ds.query(
        `${codePoints} INSERT INTO glue (rowid, body) SELECT c, char(c) || '.' || char(c) FROM n WHERE c NOT BETWEEN 55296 AND 57343`,
      );
      await ds.query(
        `${codePoints} INSERT INTO split (rowid, body) SELECT c, 'a' || char(c) || 'a' FROM n WHERE c NOT BETWEEN 55296 AND 57343`,
      );
    }, 60_000);
    afterAll(() => ds.destroy());

    const undercounted = async (table: string, text: (c: string) => string): Promise<string[]> => {
      const tokens = await ds.query<{ cp: number; n: number }[]>(
        `SELECT doc AS cp, count(*) AS n FROM ${table} GROUP BY doc`,
      );
      // Whitespace never reaches the count inside a word: the query is split on it first.
      const notSpace = (row: { cp: number }): boolean => !/\s/u.test(String.fromCodePoint(row.cp));
      return tokens
        .filter(notSpace)
        .filter(row => searchTermCount(text(String.fromCodePoint(row.cp))) < row.n)
        .map(row => row.cp.toString(16));
    };

    it('never counts fewer words than the index finds around a character it treats as part of a word', async () => {
      expect(await undercounted('glue_tokens', c => `${c}.${c}`)).toEqual([]);
    }, 60_000);

    it('never counts fewer words than the index finds around a character it treats as a separator', async () => {
      expect(await undercounted('split_tokens', c => `a${c}a`)).toEqual([]);
    }, 60_000);

    // Strings of every kind of character at once, because a stretch of them is what the count has to
    // bound: a glued mark between letters joins them, a separator next to it does not, and the
    // two alternate. The same words are not run twice, as the count does not run them.
    it('never counts fewer words than the index finds in a string mixing every kind of character', async () => {
      await ds.query('CREATE VIRTUAL TABLE mixed USING fts5(body)');
      await ds.query("CREATE VIRTUAL TABLE mixed_tokens USING fts5vocab(mixed, 'instance')");
      const pieces = [
        'a',
        'b',
        'k',
        '7',
        chars(0xe9),
        chars(0x915),
        '.',
        '-',
        "'",
        ' ',
        ' ',
        '/',
        chars(0x93e),
        chars(0x301),
        chars(0x902),
        chars(0x200c),
        chars(0x200d),
        chars(0xb7),
        chars(0x2014),
        chars(0x2026),
        chars(0x201c),
        chars(0x1e4ee),
        chars(0x11300),
        chars(0x1abf),
        chars(0x1f923),
        chars(0x1f3fb),
        chars(0xe000),
        chars(0x1cf2),
        chars(0x19b0),
      ];
      let seed = 20241014;
      const next = (limit: number): number => {
        seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
        return seed % limit;
      };
      const samples: string[] = [];
      for (let i = 0; i < 400; i++) {
        const raw = Array.from({ length: 1 + next(40) }, () => pieces[next(pieces.length)]).join('');
        samples.push([...new Set(raw.trim().split(/\s+/))].join(' '));
      }
      for (const [i, text] of samples.entries()) {
        await ds.query('INSERT INTO mixed (rowid, body) VALUES (?, ?)', [i + 1, text]);
      }
      const found = await ds.query<{ doc: number; n: number }[]>(
        'SELECT doc, count(*) AS n FROM mixed_tokens GROUP BY doc',
      );
      const tokens = new Map(found.map(row => [row.doc, row.n]));
      const undercounts = samples
        .map((text, i) => ({ text, i, n: tokens.get(i + 1) ?? 0 }))
        .filter(({ text, n }) => text.trim() !== '' && searchTermCount(text) < n)
        .map(({ text, n }) => `${JSON.stringify(text)} counted ${searchTermCount(text)}, index finds ${n}`);
      expect(undercounts).toEqual([]);
    }, 60_000);

    it('counts a sentence of marked letters as the index splits it, not once more for every mark', async () => {
      const sentences = [
        'मैं आज शाम को बाज़ार जाकर कुछ ताज़ी सब्ज़ियाँ और फल खरीदूँगा',
        'నేను ఈ రోజు సాయంత్రం మార్కెట్‌కు వెళ్లి తాజా కూరగాయలు కొంటాను',
      ];
      await ds.query('CREATE VIRTUAL TABLE sentences USING fts5(body)');
      await ds.query("CREATE VIRTUAL TABLE sentences_tokens USING fts5vocab(sentences, 'instance')");
      for (const [i, text] of sentences.entries()) {
        await ds.query('INSERT INTO sentences (rowid, body) VALUES (?, ?)', [i + 1, text]);
      }
      const found = await ds.query<{ doc: number; n: number }[]>(
        'SELECT doc, count(*) AS n FROM sentences_tokens GROUP BY doc',
      );
      for (const [i, text] of sentences.entries()) {
        const n = found.find(row => row.doc === i + 1)?.n ?? 0;
        expect(searchTermCount(text)).toBeGreaterThanOrEqual(n);
        // Close to what the index finds, and well under the limit the route enforces.
        expect(searchTermCount(text)).toBeLessThanOrEqual(Math.ceil(n * 1.3));
      }
    }, 60_000);
  });
});
