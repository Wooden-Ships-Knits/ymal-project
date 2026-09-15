/*
 * Inspired By Your Views - the rules that decide what the row shows.
 *
 * Pure functions only, no browser. The storefront script also fetches and
 * renders, but these are the decisions that can quietly show the wrong thing:
 * which products are candidates, which are excluded, and what order they
 * appear in.
 *
 * Run:  node --test frontend/storefront/tests/ymal-inspired.test.js
 *
 * Name the file, not the folder: Node 24 treats the argument as a file
 * pattern and does not expand a bare folder path.
 *
 * No dependencies - node:test and node:assert ship with Node.
 */
const test = require('node:test');
const assert = require('node:assert/strict');

const ibyv = require('../assets/ymal-inspired.js');

const letters = (s) => s.split('');

test.describe('candidates', () => {
  test.it('takes at most 4 from each source, in source order', () => {
    const sources = [letters('abcde'), letters('fg')];
    assert.deepEqual(ibyv.candidates(sources, 4), letters('abcdfg'));
  });

  test.it('keeps the first occurrence of a duplicate', () => {
    // Two viewed products often recommend the same thing.
    assert.deepEqual(ibyv.candidates([letters('ab'), letters('bc')], 4), letters('abc'));
  });

  test.it('ignores empty and missing sources', () => {
    // A source is empty when that product's Featured list had nothing
    // eligible, or its fetch failed.
    assert.deepEqual(ibyv.candidates([[], null, letters('ab'), undefined], 4), letters('ab'));
  });

  test.it('returns nothing for no history', () => {
    assert.deepEqual(ibyv.candidates([], 4), []);
  });
});

test.describe('exclude', () => {
  test.it('drops viewed, in-cart and current products', () => {
    const excluded = new Set(['b', 'd']);
    assert.deepEqual(ibyv.exclude(letters('abcde'), excluded), letters('ace'));
  });

  test.it('leaves the input untouched when nothing is excluded', () => {
    assert.deepEqual(ibyv.exclude(letters('abc'), new Set()), letters('abc'));
  });
});

test.describe('seededOrder', () => {
  const twenty = letters('abcdefghijklmnopqrst');

  test.it('is the same order for the same seed', () => {
    // Shuffle once per visit: the seed lives for the visit, so every page load
    // in that visit must produce the identical row.
    assert.deepEqual(ibyv.seededOrder(twenty, 'visit-1'), ibyv.seededOrder(twenty, 'visit-1'));
  });

  test.it('is a reordering, never adds or drops a product', () => {
    const ordered = ibyv.seededOrder(twenty, 'visit-1');
    assert.deepEqual([...ordered].sort(), [...twenty].sort());
  });

  test.it('differs between visits', () => {
    assert.notDeepEqual(ibyv.seededOrder(twenty, 'visit-1'), ibyv.seededOrder(twenty, 'visit-2'));
  });

  test.it('actually shuffles rather than returning the input order', () => {
    assert.notDeepEqual(ibyv.seededOrder(twenty, 'visit-1'), twenty);
  });

  test.it('keeps existing products in the same relative order as history grows', () => {
    // Viewing another product adds candidates mid-visit. The products already
    // on show must not jump around - new ones slot in between them.
    const before = ibyv.seededOrder(letters('abcdefghij'), 'visit-1');
    const after = ibyv.seededOrder(letters('abcdefghijklmn'), 'visit-1');
    const survivors = after.filter((h) => before.includes(h));
    assert.deepEqual(survivors, before);
  });

  test.it('does not mutate its input', () => {
    const input = letters('abcdef');
    ibyv.seededOrder(input, 'visit-1');
    assert.deepEqual(input, letters('abcdef'));
  });
});

test.describe('plan', () => {
  test.it('combines, excludes and orders in one step', () => {
    const planned = ibyv.plan({
      sources: [letters('abcd'), letters('cdef')],
      perSource: 4,
      excluded: new Set(['a', 'f']),
      seed: 'visit-1',
    });
    assert.deepEqual([...planned].sort(), letters('bcde'));
    assert.deepEqual(planned, ibyv.seededOrder(letters('bcde'), 'visit-1'));
  });

  test.it('is empty when everything is excluded', () => {
    const planned = ibyv.plan({
      sources: [letters('ab')],
      perSource: 4,
      excluded: new Set(['a', 'b']),
      seed: 'visit-1',
    });
    assert.deepEqual(planned, []);
  });
});
