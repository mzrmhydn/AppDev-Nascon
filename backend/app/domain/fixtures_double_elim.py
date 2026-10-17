# Double-elimination bracket: winners tree, losers bracket wiring, grand final + bracket reset (FR-1.3, spec §5.7-D).
# Reuses the single-elim helpers; WR1 seeding and byes are identical to single elimination.
from app.domain.fixtures_common import bad_request
from app.domain.fixtures_single_elim import (apply_results, bracket_size, first_round, link, new_match,
                                             set_winner)


def generate_double_elim(teams, params):
    if not isinstance(params, dict):
        raise bad_request(["params"])
    reset = params.get("bracket_reset", False)
    if type(reset) is not bool:
        raise bad_request(["bracket_reset"])

    size = bracket_size(len(teams))  # >= 4 because n >= 3
    k = size.bit_length() - 1        # log2(size)

    # 1. Winners bracket: the single-elim tree with prefix WR.
    winners = [first_round(teams, "WR", "winners")]
    for r in range(2, k + 1):
        winners.append([new_match(f"WR{r}M{i}", "winners", r, i) for i in range(1, size // 2 ** r + 1)])
    for r in range(1, k):
        for m in winners[r - 1]:
            i = m["index"]
            m["winner_to"] = link(f"WR{r + 1}M{(i + 1) // 2}", "home" if i % 2 == 1 else "away")

    # 2. Losers bracket: rounds 2j-1 and 2j have size / 2^(j+1) matches, j = 1..k-1.
    losers = []
    for j in range(1, k):
        count = size // 2 ** (j + 1)
        for r in (2 * j - 1, 2 * j):
            losers.append([new_match(f"LR{r}M{i}", "losers", r, i) for i in range(1, count + 1)])

    # LR1 Mm <- losers of WR1 M(2m-1) (home) and WR1 M(2m) (away)
    for m in winners[0]:
        i = m["index"]
        m["loser_to"] = link(f"LR1M{(i + 1) // 2}", "home" if i % 2 == 1 else "away")
    # WR(j+1) Mi loser -> LR(2j) Mi away (so the WR final loser lands in the LB final's away slot)
    for j in range(1, k):
        for m in winners[j]:
            m["loser_to"] = link(f"LR{2 * j}M{m['index']}", "away")
    # LR(2j-1) Mi winner -> LR(2j) Mi home
    # LR(2j) Mi winner -> LR(2j+1) M(ceil(i/2)), home if i odd else away
    for lr in losers:
        for m in lr:
            r, i = m["round"], m["index"]
            if r % 2 == 1:
                m["winner_to"] = link(f"LR{r + 1}M{i}", "home")
            elif r < 2 * (k - 1):
                m["winner_to"] = link(f"LR{r + 1}M{(i + 1) // 2}", "home" if i % 2 == 1 else "away")

    # 3. Grand final: WR champion (home) vs LR champion (away).
    gf1 = new_match("GF1", "grand_final", 1, 1)
    winners[-1][0]["winner_to"] = link("GF1", "home")
    losers[-1][0]["winner_to"] = link("GF1", "away")
    grand_final = [gf1]
    if reset:
        gf2 = new_match("GF2", "grand_final", 2, 1)
        gf2["conditional"] = True
        gf2["required"] = None
        gf1["winner_to"] = link("GF2", "home")
        gf1["loser_to"] = link("GF2", "away")
        grand_final.append(gf2)

    all_matches = [m for rnd in winners + losers for m in rnd] + grand_final
    by_id = {m["match_id"]: m for m in all_matches}
    for m in winners[0]:
        if m["bye"]:
            set_winner(by_id, m, m["home"])
    apply_results(by_id, params.get("results", []))

    if reset and gf1["winner"] is not None:
        # GF2 is played only if the losers-bracket champion (GF1.away) won GF1.
        grand_final[1]["required"] = gf1["winner"] == gf1["away"]

    return {
        "format": "double_elim",
        "bracket_size": size,
        "bracket_reset": reset,
        "winners": [{"round": r + 1, "matches": rnd} for r, rnd in enumerate(winners)],
        "losers": [{"round": r + 1, "matches": rnd} for r, rnd in enumerate(losers)],
        "grand_final": grand_final,
    }
