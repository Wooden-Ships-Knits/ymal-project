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
  assert.deepEqual(popup.offers(source, added, ['pumpkin-black'], 3), [
    'crew-black',
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('never offers another colorway of what was just added', () => {
  const justAdded = { handle: 'crew-red', style: 'CREW CHUNKY' };
  assert.deepEqual(popup.offers(source, justAdded, ['crew-red'], 3), [
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('skips anything already in the cart', () => {
  assert.deepEqual(popup.offers(source, added, ['pumpkin-black', 'crew-black'], 3), [
    'crew-navy',
    'cardi-black',
    'hoodie-grey',
  ]);
});

test.it('never offers the product that was just added', () => {
  const self = { handles: ['pumpkin-black', 'cardi-black'], styles: ['PUMPKIN CREW', 'CARDI CHUNKY'] };
  assert.deepEqual(popup.offers(self, added, [], 3), ['cardi-black']);
});

test.it('stops at the slot count', () => {
  assert.deepEqual(popup.offers(source, added, [], 2), ['crew-black', 'cardi-black']);
});

test.it('handles a product with no Featured list', () => {
  assert.deepEqual(popup.offers({ handles: [], styles: [] }, added, [], 3), []);
  assert.deepEqual(popup.offers(null, added, [], 3), []);
});

test.it('treats an unknown style as its own', () => {
  // A template from before styles were sent: nothing is dropped as a duplicate.
  const old = { handles: ['a', 'b'], styles: [] };
  assert.deepEqual(popup.offers(old, added, [], 3), ['a', 'b']);
});
