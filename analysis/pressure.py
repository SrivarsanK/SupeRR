"""SupeRR Selector S2, Round 1: who performs best under pressure?

Run:  python analysis/pressure.py            -> writes analysis/out/*.csv and prints the top 10s
      python analysis/pressure.py --check    -> also runs the sensitivity and reliability checks

Method in one paragraph: rebuild the match state before every ball, score each ball with a 0-1 pressure
index, call the top quarter of balls "high pressure", value every ball against what an average player does
in the same context (format, innings, over, pressure or not), then run a batter-versus-bowler Elo over the
high-pressure balls in date order. Players are ranked by that pressure Elo; an Elo over normal balls, the
shrunk value per 100 balls (level), lift and consistency are reported next to it as evidence.
"""
import os
import sys
from functools import lru_cache

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "..", "data", "6af458274c1e8_data_pack", "Data Pack")
OUT = os.path.join(HERE, "out")

PRESSURE_QUANTILE = 0.75   # top 25% of balls by pressure index are "high pressure"
WICKET_RUNS = 6.0          # runs a dismissal is worth; tested at 4 and 8 in --check
SHRINK_BALLS = 100         # empirical-Bayes prior: 100 balls of league-average play
MIN_PRESSURE_BALLS = 120
MIN_PRESSURE_MATCHES = 12
ACTIVE_SINCE = "2025-01-01"
ELO_K = 2.0                # per-ball step; 2 gave the best split-half reliability of 2, 4 and 8
NOT_BOWLER_WICKET = {"RunOut", "Retire Out", "Obstructing the field", "Obstracting the field"}


def load():
    b = pd.read_csv(os.path.join(PACK, "ball_by_ball.csv"), low_memory=False)
    m = pd.read_csv(os.path.join(PACK, "matches.csv"))
    c = pd.read_csv(os.path.join(PACK, "competitions.csv"))
    m = m.merge(c[["comp_id", "comp_name", "match_format"]], on="comp_id", how="left")
    m["is_ipl"] = m.comp_name.str.startswith("IPL")
    b = b[b.innings <= 2].merge(  # super overs (innings 3, 4) are left out
        m[["match_id", "match_date", "is_ipl", "knock_out", "revised_target", "second_inn_revised_overs"]], on="match_id")
    return b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)


def add_state(b):
    """Match situation before each ball, and the pressure index."""
    b["legal"] = ~b.extras_type.isin(["wide", "Overstep"])
    b["total"] = b.runs + b.extras1_runs + b.extras_2_runs  # checked: reproduces 98% of "won by N runs" margins
    g = b.groupby(["match_id", "innings"])
    b["score"] = g.total.cumsum() - b.total
    b["wkts"] = g.is_wicket.cumsum() - b.is_wicket
    b["balls"] = g.legal.cumsum() - b.legal
    first = b[b.innings == 1].groupby("match_id").total.sum().rename("first_total")
    b = b.join(first, on="match_id")
    b["target"] = b.revised_target.fillna(b.first_total + 1)
    b["max_balls"] = np.where(b.innings == 2, b.second_inn_revised_overs.fillna(120), 120)  # revised overs are stored in balls
    left = (b.max_balls - b.balls).clip(lower=1)
    b["rrr"] = np.where(b.innings == 2, (b.target - b.score) * 6 / left, np.nan)

    # Collapse: wickets lost beyond what is normal at this point of an innings.
    stage = (b.balls // 6).clip(upper=19)
    b["over"] = stage
    exp_wk = b.groupby(["innings", stage]).wkts.transform("mean")
    collapse = ((b.wkts - exp_wk) / 3).clip(0, 1)
    time = (b.balls / b.max_balls).clip(0, 1)
    rate = ((b.rrr - 6) / 9).clip(0, 1)                      # 6 an over is routine, 15 is extreme
    alive = (b.target - b.score > 0) & (b.rrr <= 18)         # a chase needing 18+ an over is over, not tense
    chase = alive * (0.5 * rate + 0.2 * collapse + 0.3 * time)
    setting = 0.5 * collapse + 0.5 * time
    b["pi"] = (np.where(b.innings == 2, chase, setting) * np.where(b.knock_out == 1, 1.1, 1.0)).clip(0, 1)
    return b


def add_values(b, q=PRESSURE_QUANTILE, wicket_runs=WICKET_RUNS):
    """Value of each ball to the batter and to the bowler, in runs above an average player in the same context."""
    b["hp"] = b.pi >= b.pi.quantile(q)
    ctx = [b.is_ipl, b.innings, b.over, b.hp]

    b["bat_ball"] = b.extras_type != "wide"
    b["bat_out"] = b.is_wicket & (b.dismissed_player_id == b.striker_id) & (b.dismissal_type != "Retire Out")
    faced = b[b.bat_ball]
    exp_r = faced.groupby([faced.is_ipl, faced.innings, faced.over, faced.hp]).runs.mean().rename("exp_r")
    exp_o = faced.groupby([faced.is_ipl, faced.innings, faced.over, faced.hp]).bat_out.mean().rename("exp_o")

    charged = b.extras_type.isin(["wide", "Overstep"])       # byes and leg-byes are not the bowler's
    b["conceded"] = b.runs + np.where(charged, b.extras1_runs + b.extras_2_runs, 0)
    b["bowl_wkt"] = b.is_wicket & ~b.dismissal_type.isin(NOT_BOWLER_WICKET)
    exp_c = b.groupby(ctx).conceded.mean().rename("exp_c")
    exp_w = b.groupby(ctx).bowl_wkt.mean().rename("exp_w")

    keys = pd.MultiIndex.from_arrays(ctx)
    for s in (exp_r, exp_o, exp_c, exp_w):
        b[s.name] = s.reindex(keys).to_numpy()

    # Opposition strength: how far each team's bowling / batting sits from context average, per ball.
    bowl_team_adj = (b.runs - b.exp_r).where(b.bat_ball).groupby(b.bowling_team_id).transform("mean")
    bat_team_adj = (b.conceded - b.exp_c).groupby(b.batting_team_id).transform("mean")
    b["bat_val"] = np.where(b.bat_ball, (b.runs - b.exp_r - bowl_team_adj) - wicket_runs * (b.bat_out - b.exp_o), 0.0)
    b["bowl_val"] = (b.exp_c + bat_team_adj - b.conceded) + wicket_runs * (b.bowl_wkt - b.exp_w)
    # Duel score for Elo: the batter's share of the ball, 0.5 = par for the context, a wicket is about 0.
    any_out = b.bowl_wkt | b.bat_out
    duel = (b.conceded - b.exp_c) - wicket_runs * (any_out - any_out.groupby(ctx).transform("mean"))
    b["duel"] = (0.5 + duel / 12).clip(0, 1)
    return b.sort_values(["match_date", "match_id", "innings", "innings_ball_num"])


def elo(d, k=ELO_K):
    """Ball-by-ball Elo in date order: beating a highly rated opponent moves a rating more than beating a weak one."""
    bat, bowl = {}, {}
    for striker, bowler, s in zip(d.striker_id.to_numpy(), d.bowler_id.to_numpy(), d.duel.to_numpy()):
        rb, rw = bat.get(striker, 1500.0), bowl.get(bowler, 1500.0)
        step = k * (s - 1 / (1 + 10 ** ((rw - rb) / 400)))
        bat[striker], bowl[bowler] = rb + step, rw - step
    return {"bat": pd.Series(bat), "bowl": pd.Series(bowl)}


@lru_cache(maxsize=1)
def not_signable():
    """Players RR cannot sign at the 2027 auction, so they are not ranked (they still count as opponents).

    Everyone who has played for Pakistan (not eligible for the IPL), plus players retired from the IPL.
    """
    m = pd.read_csv(os.path.join(PACK, "competition_team_player_mapping.csv"))
    retired_from_ipl = {1318}  # Andre Russell: retired from the IPL on 30 Nov 2025, now KKR's power coach
    return frozenset(m[m.team_name.isin(["Pakistan", "Pakistan A"])].player_id) | retired_from_ipl


def rate(b, role, min_balls=MIN_PRESSURE_BALLS):
    pid, name, val = ("striker_id", "striker_name", "bat_val") if role == "bat" else ("bowler_id", "bowler_name", "bowl_val")
    # A bowler owns his wides and no-balls (runs and value) but only legal balls count as balls bowled.
    d = b[b.bat_ball].assign(ball=1) if role == "bat" else b.assign(ball=b.legal.astype(int))
    hp, normal = d[d.hp], d[~d.hp]
    r = pd.DataFrame({
        "player": d.groupby(pid)[name].last(),
        "hp_balls": hp.groupby(pid).ball.sum(),
        "hp_matches": hp.groupby(pid).match_id.nunique(),
        "hp_value": hp.groupby(pid)[val].sum(),
        "normal_balls": normal.groupby(pid).ball.sum(),
        "normal_value": normal.groupby(pid)[val].sum(),
        "last_match": d.groupby(pid).match_date.max(),
        "ipl_hp_balls": hp[hp.is_ipl].groupby(pid).ball.sum(),
    }).fillna({"hp_balls": 0, "hp_matches": 0, "hp_value": 0, "normal_balls": 0, "normal_value": 0, "ipl_hp_balls": 0})
    # Runs above average per 100 balls, shrunk towards 0 so small samples cannot top the list.
    r["level"] = 100 * r.hp_value / (r.hp_balls + SHRINK_BALLS)
    r["normal_level"] = 100 * r.normal_value / (r.normal_balls + SHRINK_BALLS)
    r["lift"] = r.level - r.normal_level
    per_match = hp.groupby([pid, "match_id"]).agg(sum=(val, "sum"), balls=("ball", "sum"))
    per_match = per_match[per_match["balls"] >= 3]
    won = (per_match["sum"] > 0).groupby(level=0).agg(["sum", "size"])
    r["consistency"] = ((won["sum"] + 5) / (won["size"] + 10)).reindex(r.index)  # prior: 10 matches at 50%

    if role == "bat":
        r["hp_runs"] = hp.groupby(pid).runs.sum()
        r["hp_sr"] = 100 * r.hp_runs / r.hp_balls
        r["hp_outs"] = hp.groupby(pid).bat_out.sum()
        r["normal_sr"] = 100 * normal.groupby(pid).runs.sum() / r.normal_balls
    else:
        r["hp_econ"] = 6 * hp.groupby(pid).conceded.sum() / r.hp_balls
        r["hp_wkts"] = hp.groupby(pid).bowl_wkt.sum()
        r["normal_econ"] = 6 * normal.groupby(pid).conceded.sum() / r.normal_balls

    e = r[(r.hp_balls >= min_balls) & (r.hp_matches >= MIN_PRESSURE_MATCHES) & (r.last_match >= ACTIVE_SINCE)
          & ~r.index.isin(not_signable())].copy()
    e["pressure_elo"] = elo(b[b.hp])[role].reindex(e.index)
    e["normal_elo"] = elo(b[~b.hp])[role].reindex(e.index)
    e["elo_gap"] = e.pressure_elo - e.normal_elo
    e = e.sort_values("pressure_elo", ascending=False)
    e.insert(0, "rank", range(1, len(e) + 1))
    return e


def build(q=PRESSURE_QUANTILE, wicket_runs=WICKET_RUNS):
    return add_values(add_state(load()), q, wicket_runs)


def checks(b, bat, bowl):
    """Sensitivity to the two judgement calls, and split-half reliability of the rating."""
    lines = []
    top = {"bat": set(bat.head(10).index), "bowl": set(bowl.head(10).index)}
    for label, kw in (("pressure = top 20% of balls", {"q": 0.80}), ("pressure = top 30% of balls", {"q": 0.70}),
                      ("wicket worth 4 runs", {"wicket_runs": 4.0}), ("wicket worth 8 runs", {"wicket_runs": 8.0})):
        alt = build(**kw)
        for role in ("bat", "bowl"):
            kept = len(top[role] & set(rate(alt, role).head(10).index))
            lines.append(f"{label:30} {role:5} top-10 names kept: {kept}/10")
    # Split-half: rate players separately on odd and even matches; a skill that is real should correlate.
    odd = b.match_id.rank(method="dense") % 2 == 1
    for role in ("bat", "bowl"):
        a, c = rate(b[odd], role, MIN_PRESSURE_BALLS // 2), rate(b[~odd], role, MIN_PRESSURE_BALLS // 2)
        both = a.join(c, lsuffix="_a", rsuffix="_b", how="inner")
        lines.append(f"split-half correlation {role:5} n={len(both):3}  pressure_elo r={both.pressure_elo_a.corr(both.pressure_elo_b):.2f}  "
                     f"level r={both.level_a.corr(both.level_b):.2f}  lift r={both.lift_a.corr(both.lift_b):.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    b = build()
    # Self-check: values are relative to context average, so they must sum to ~0 over all balls.
    assert abs(b.bat_val.sum() / len(b)) < 1e-6 and abs(b.bowl_val.sum() / len(b)) < 1e-6
    assert (b.rrr[b.innings == 1].isna()).all() and b.hp.mean() < 0.3 and abs(b.duel.mean() - 0.5) < 0.02
    os.makedirs(OUT, exist_ok=True)
    bat, bowl = rate(b, "bat"), rate(b, "bowl")
    bat.round(3).to_csv(os.path.join(OUT, "batters.csv"))
    bowl.round(3).to_csv(os.path.join(OUT, "bowlers.csv"))
    b[["match_id", "innings", "over", "pi", "hp", "is_ipl", "runs", "conceded", "bat_ball", "bat_out", "bowl_wkt", "legal"]].to_csv(
        os.path.join(OUT, "balls.csv"), index=False)
    pd.set_option("display.width", 250)
    print(f"balls {len(b)}, high-pressure {b.hp.sum()} ({b.hp.mean():.0%}), threshold PI >= {b.pi.quantile(PRESSURE_QUANTILE):.2f}")
    print(f"eligible batters {len(bat)}, bowlers {len(bowl)}")
    print(bat.head(15)[["rank", "player", "hp_balls", "hp_matches", "hp_sr", "normal_sr", "hp_outs", "level", "consistency", "normal_elo", "pressure_elo"]].round(2).to_string())
    print(bowl.head(15)[["rank", "player", "hp_balls", "hp_matches", "hp_econ", "normal_econ", "hp_wkts", "level", "consistency", "normal_elo", "pressure_elo"]].round(2).to_string())
    if "--check" in sys.argv:
        report = checks(b, bat, bowl)
        open(os.path.join(OUT, "checks.txt"), "w").write(report)
        print(report)
