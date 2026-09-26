const test = require("node:test");
const assert = require("node:assert");
const { longestStreak } = require("./index.js");
test("counts consecutive days", () => assert.equal(longestStreak(["2026-01-01", "2026-01-02", "2026-01-04"]), 2));
test("empty list is zero", () => assert.equal(longestStreak([]), 0));
