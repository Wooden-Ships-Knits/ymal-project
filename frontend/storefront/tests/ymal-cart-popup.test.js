/*
 * The add to cart popup - which products it offers.
 *
 * The browser half fetches and renders; this is the decision that can quietly
 * show the wrong thing.
 *
 * Run:  node --test frontend/storefront/tests/ymal-cart-popup.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');

const popup = require('../assets/ymal-cart-popup.js');

const source = {
  handles: ['crew-black', 'crew-navy', 'cardi-black', 'hoodie-grey'],
  styles: ['CREW CHUNKY', 'CREW CHUNKY', 'CARDI CHUNKY', 'HOODIE COTTON'],
};
const added = { handle: 'pumpkin-black', style: 'PUMPKIN CREW' };

test.it('offers the Featured list in order, one per style', () => {
  // crew-navy is dropped: same style as crew-black, a colorway of it.
  assert.deepEqual(popup.offers(source, added, ['pumpkin-black'], 3, null), [
    'crew-black',
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('never offers another colorway of what was just added', () => {
  const justAdded = { handle: 'crew-red', style: 'CREW CHUNKY' };
  assert.deepEqual(popup.offers(source, justAdded, ['crew-red'], 3, null), [
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('skips anything already in the cart', () => {
  assert.deepEqual(popup.offers(source, added, ['pumpkin-black', 'crew-black'], 3, null), [
    'crew-navy',
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('never offers the product that was just added', () => {
  const self = { handles: ['pumpkin-black', 'cardi-black'], styles: ['PUMPKIN CREW', 'CARDI CHUNKY'] };
  assert.deepEqual(popup.offers(self, added, [], 3, null), ['cardi-black']);
});

test.it('stops at the slot count', () => {
  assert.deepEqual(popup.offers(source, added, [], 2, null), ['crew-black', 'cardi-black']);
});

test.it('handles a product with no Featured list', () => {
  assert.deepEqual(popup.offers({ handles: [], styles: [] }, added, [], 3, null), []);
  assert.deepEqual(popup.offers(null, added, [], 3, null), []);
});

test.it('treats an unknown style as its own', () => {
  // A template from before styles were sent: nothing is dropped as a duplicate.
  const old = { handles: ['a', 'b'], styles: [] };
  assert.deepEqual(popup.offers(old, added, [], 3, null), ['a', 'b']);
});

test.describe('shuffled', () => {
  // A fixed sequence stands in for Math.random, so "shuffled" is testable.
  const fixed = (values) => {
    let i = 0;
    return () => values[i++ % values.length];
  };

  test.it('does not simply return the list in order', () => {
    const wide = {
      handles: ['a', 'b', 'c', 'd', 'e', 'f'],
      styles: ['A', 'B', 'C', 'D', 'E', 'F'],
    };
    const shown = popup.offers(wide, added, [], 3, fixed([0.9, 0.1, 0.7, 0.3, 0.5]));
    assert.notDeepEqual(shown, ['a', 'b', 'c']);
    assert.equal(shown.length, 3);
    assert.equal(new Set(shown).size, 3);
  });

  test.it('still applies every rule after shuffling', () => {
    const wide = {
      handles: ['crew-black', 'crew-navy', 'cardi-black', 'pumpkin-black'],
      styles: ['CREW CHUNKY', 'CREW CHUNKY', 'CARDI CHUNKY', 'PUMPKIN CREW'],
    };
    for (const seed of [0.1, 0.4, 0.6, 0.9]) {
      const shown = popup.offers(wide, added, ['pumpkin-black'], 3, () => seed);
      // Never the added product, never both colorways of one style.
      assert.ok(!shown.includes('pumpkin-black'));
      assert.ok(!(shown.includes('crew-black') && shown.includes('crew-navy')));
    }
  });

  test.it('shuffle keeps every item and mutates nothing', () => {
    const input = [1, 2, 3, 4, 5];
    const out = popup.shuffle(input, fixed([0.2, 0.8, 0.5, 0.1]));
    assert.deepEqual([...out].sort(), [1, 2, 3, 4, 5]);
    assert.deepEqual(input, [1, 2, 3, 4, 5]);
  });
});
