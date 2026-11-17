"""Why each player is on the list, keyed by player_id. Written from the numbers in his profile (report.profile).

report.py refuses to build if a top-10 player has no note, so a changed list can never print a stale note.
"""
NOTES = {
    # Batters
    6396: "The highest pressure Elo in the data, and he gets there without needing a lift: his strike rate is 178 in both "
          "columns. What changes is the value. Under pressure he gets out less often (every 21 balls against 19) and his runs "
          "are worth 47 above average per 100 balls, against 30 normally. He is at his most dangerous at the death (203 in "
          "overs 16-20) and against pace (190), and every year from 2022 to 2026 is positive.",
    7897: "The biggest jump between normal and pressure in the top ten, 21 Elo points. On normal balls he is an average scorer "
          "(135, +1 per 100 balls). Under pressure he scores at 164 with more boundaries and fewer dots, worth +38 per 100 "
          "balls. Most of that work is in chases (432 of 689 balls), every year is positive, and 2026 is his biggest sample yet.",
    1699: "The highest strike rate under pressure in the top ten (187) and the most value per ball (+53 per 100). He gets out "
          "at the same rate either way, about once every 23 balls, so the extra speed costs nothing. The concern is the "
          "trend: his pressure value has dropped every year, from +86 in 2022 to +2 in 2026, so the rating leans on his "
          "older seasons.",
    4755: "Faster and harder to dismiss under pressure: 163 against 149, and out every 24 balls against 22. Unusually for a "
          "big hitter he scores as well against spin (166) as against pace (162), which is what the middle overs of a chase "
          "need. 2026 was his best pressure year, +59 per 100 balls over 164 balls.",
    2756: "The sharpest change on the list. On normal balls he is below average (-17 per 100); under pressure he is +53, "
          "strikes at 174 and is dismissed only once every 38 balls, against every 15 normally. All of it comes in the IPL, "
          "and he is strongest at the death, 214 in overs 16-20. The sample is small (339 balls), but every year points the "
          "same way.",
    4260: "Picked for consistency rather than lift. His pressure value (+32 per 100 balls) is close to his normal value "
          "(+27), and 74% of his pressure matches were above average, the best record among these ten batters. He is better "
          "setting a total (171) than chasing (156) and scores at 204 at the death. The cost is his wicket: under pressure "
          "he goes every 20 balls instead of every 27.",
    3647: "A chaser. Under pressure in chases he scores at 187, and at 223 in overs 16-20. His value rises from +9 per 100 "
          "balls normally to +43 under pressure. Two things hold him back: the smallest sample in the top ten (303 balls in "
          "27 matches), and he is dismissed a little more often under pressure (every 20 balls against 25).",
    2639: "Turns a below-average normal record (-3 per 100 balls) into +31 under pressure, mainly by cutting dot balls from "
          "37% to 30%. He is far better setting a total (193) than chasing (155), and far better against pace (187) than "
          "spin (141). Every year is positive, with 2024 and 2025 the strongest.",
    6676: "Here on recent form. His pressure value was negative from 2022 to 2024, then +9 in 2025 and +86 in 2026, a year "
          "that includes 115 off 49 pressure balls against Zimbabwe. Almost all of his pressure balls are T20Is (306 of "
          "358) and batting first; in chases he has only 54 balls at a strike rate of 109. He also has the weakest "
          "match-by-match record in the top ten (51% good matches). This pick backs the trend.",
    6726: "A death hitter: 267 of his 497 pressure balls come in overs 16-20, at 175. Normally he is dismissed every 12 "
          "balls; under pressure every 21, and that alone moves his value from -9 to +29 per 100 balls. 2026 was his first "
          "negative pressure year (-10 over 70 balls), and he is only half an Elo point ahead of Jos Buttler in 11th.",
    # Bowlers
    781: "Clear first. Under pressure he concedes 5.6 an over against 7.3 normally, takes a wicket every 17 balls instead of "
         "28, and 43% of his pressure balls are dots. 72% of his pressure matches were above average, the best of these ten "
         "bowlers, and every year is positive, with 2025 and 2026 the strongest. Left-handers find him hardest: 4.9 an over.",
    4722: "The biggest pressure workload in the data: 831 balls in 71 matches and 64 wickets. His economy does not move (7.4 "
          "either way) but his wicket rate does, one every 13 balls under pressure against 22. The caveat is where he does "
          "it: 5.7 an over in T20Is, 8.6 in the IPL.",
    2933: "Here for level, not lift. His normal record (+30 runs saved per 100 balls) is the best of these ten, and he stays "
          "close to it under pressure (+28), mostly at the death: 323 of his 509 pressure balls are in overs 16-20. He "
          "concedes slightly more under pressure (7.5 against 7.2) but takes a wicket every 15 balls against 24. 2026 was "
          "below average (-7).",
    3298: "Already at RR, so this is a case for keeping him. He is one of two seamers here who get better under pressure: 8.5 "
          "an over against 9.2, a wicket every 12 balls against 20, and +23 runs saved per 100 balls against -5. Two thirds "
          "of his pressure balls are at the death. His record in the data runs from 2024, and 2025 was a dip (-6).",
    4101: "A middle-overs bowler. 366 of his 465 pressure balls come before the 16th over, at 6.1 an over, and he gives away "
          "fewer boundaries under pressure (11% against 15%). Overall he is better under pressure than normally (6.9 against "
          "7.7). He should not bowl the death: 9.5 an over in overs 16-20.",
    3644: "A wicket-taker: 50 pressure wickets, one every 13 balls against 19 normally, and he concedes less under pressure "
          "(7.6 against 8.2). He is far better when his side bowls first (6.2) than when defending a total (9.0), and 2026 "
          "was a weak year (-23).",
    4373: "A death bowler: 396 of his 533 pressure balls are in overs 16-20. His economy is the same either way (7.8), but he "
          "takes a wicket every 14 balls under pressure against 25. Most of it is in T20Is (389 balls); in the IPL he has gone "
          "at 9.7 an over, and he has bowled almost no pressure balls in 2026.",
    6256: "After Rashid, the biggest pressure workload of any spinner here (724 balls, 52 wickets). He concedes less under "
          "pressure (7.4 against 8.3) and 43% of his pressure balls are dots. Very hard to score off when his side bowls "
          "first (5.7), expensive when defending (9.0), and 2026 was below average (-14).",
    2681: "The best wicket rate in the list: one every 8.8 balls under pressure, against 20 normally. That turns a "
          "below-average normal record (-1 runs saved per 100 balls) into +30 under pressure. All of it is in T20Is; he has "
          "no IPL matches in the data.",
    2417: "The tightest bowler here after Narine: 5.9 an over under pressure against 8.0 normally, and only 7% of his pressure "
          "balls go for four or six (17% normally). Almost all of his pressure overs come before the 16th. The weakness is "
          "wickets, 12 in 210 balls, and his sample is the smallest of the ten bowlers.",
}
