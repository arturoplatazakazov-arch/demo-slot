// Shared bonus-buy pricing for every game's Buy Bonus confirm popup.
//
// A purchase costs bet x cost_multiplier (the bonus_buy product in the game's
// seed) and the backend 400s when the balance can't cover it. With the demo's
// 1 000 000 starting balance and 100x products, the DEFAULT bet is never
// affordable — so the popup quotes the current bet when it can, otherwise the
// highest bet step the balance still covers (the game switches its bet to it
// on confirm), and only reports "not enough balance" when even the minimum
// bet is out of reach.
//
//   const q = BuyBonus.quote({ betSteps, betIndex, balance, multiplier });
//   q.affordable  — false: nothing on the bet ladder can be bought
//   q.betIndex    — bet step the purchase will use (== betIndex unless lowered)
//   q.bet, q.cost — that bet and its price
//   q.lowered     — true when the bet had to be dropped to afford the buy
(function () {
  function quote({ betSteps, betIndex, balance, multiplier }) {
    const steps = betSteps || [];
    const bal = Number(balance) || 0;
    const mult = Number(multiplier) || 0;
    const price = (i) => steps[i] * mult;
    let idx = Math.min(Math.max(0, betIndex | 0), steps.length - 1);
    while (idx > 0 && price(idx) > bal) idx -= 1;
    const affordable = steps.length > 0 && price(idx) <= bal;
    return {
      affordable,
      betIndex: idx,
      bet: steps[idx],
      cost: steps.length ? price(idx) : 0,
      lowered: affordable && idx !== betIndex,
    };
  }

  window.BuyBonus = { quote };
})();
