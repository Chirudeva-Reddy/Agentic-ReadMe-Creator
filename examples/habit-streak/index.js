// habit-streak: longest run of consecutive days in a list of ISO dates.
function longestStreak(dates) {
  const days = [...new Set(dates)].map(d => Date.parse(d) / 864e5).sort((a, b) => a - b);
  let best = 0, run = 0;
  days.forEach((d, i) => { run = i && d - days[i - 1] === 1 ? run + 1 : 1; best = Math.max(best, run); });
  return best;
}
module.exports = { longestStreak };
if (require.main === module) console.log("Longest streak:", longestStreak(process.argv.slice(2)), "days");
