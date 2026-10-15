/*
 * The clicked-products list - every product taken from a YMAL block for this
 * cart, sent as "YMAL products" so each one counts as direct revenue.
 *
 * Run:  node --test frontend/storefront/tests/ymal-track.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');

const track = require('../assets/ymal-track.js');

test.it('keeps every product clicked for the cart, in order', () => {
  let list = track.addClicked(null, 'cart-1', 'eryn-cardigan', 20);
  list = track.addClicked(list, 'cart-1', 'rihanna-cardi', 20);
  list = track.addClicked(list, 'cart-1', 'key-west', 20);
  assert.deepEqual(list, {
    cart: 'cart-1',
    handles: ['eryn-cardigan', 'rihanna-cardi', 'key-west'],
  });
});

test.it('a product clicked twice is listed once, as the latest', () => {
  let list = track.addClicked(null, 'cart-1', 'eryn-cardigan', 20);
  list = track.addClicked(list, 'cart-1', 'key-west', 20);
  list = track.addClicked(list, 'cart-1', 'eryn-cardigan', 20);
  assert.deepEqual(list.handles, ['key-west', 'eryn-cardigan']);
});

test.it('a new cart starts a new list', () => {
  // The earlier cart became an order; its clicks are not this cart's.
  const old = { cart: 'cart-1', handles: ['eryn-cardigan'] };
  assert.deepEqual(track.addClicked(old, 'cart-2', 'key-west', 20), {
    cart: 'cart-2',
    handles: ['key-west'],
  });
});

test.it('a click before the cart existed is carried into it', () => {
  // The first click of a visit is what creates the cart.
  const before = track.addClicked(null, '', 'eryn-cardigan', 20);
  assert.deepEqual(track.addClicked(before, 'cart-1', 'key-west', 20), {
    cart: 'cart-1',
    handles: ['eryn-cardigan', 'key-west'],
  });
});

test.it('keeps the newest when the list is full', () => {
  let list = null;
  ['a', 'b', 'c', 'd'].forEach((h) => { list = track.addClicked(list, 'cart-1', h, 3); });
  assert.deepEqual(list.handles, ['b', 'c', 'd']);
});

test.it('survives an unreadable saved value', () => {
  assert.deepEqual(track.addClicked({ handles: 'nonsense' }, 'cart-1', 'key-west', 20).handles, [
    'key-west',
  ]);
});
