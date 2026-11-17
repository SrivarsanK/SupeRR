"""Build the Round 1 methodology report: python analysis/report.py -> analysis/report/report.pdf

Every number in the report is computed here from the data pack (via pressure.py), so the PDF can be rebuilt
from scratch. Run `python analysis/pressure.py --check` first: the reliability table reads out/checks.txt.
"""
import io
import json
import os
import re
import shutil
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import pressure as P  # noqa: E402
from notes import NOTES  # noqa: E402

DIR = os.path.join(P.HERE, "report")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
INK, GREY, ACCENT = "#1a1a1a", "#9a9a9a", "#c2185b"

plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": GREY, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none"})


def svg(fig):
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()[buf.getvalue().index("<svg"):]


def chart_pressure_by_over(b):
    share = b.groupby(["innings", "over"]).hp.mean().unstack(0) * 100
    fig, ax = plt.subplots(figsize=(6.4, 2.3))
    ax.plot(share.index + 1, share[1], color=GREY, lw=2, label="Batting first")
    ax.plot(share.index + 1, share[2], color=ACCENT, lw=2, label="Chasing")
    ax.set_xlabel("Over")
    ax.set_ylabel("High-pressure balls (%)")
    ax.set_xticks(range(1, 21, 2))
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc="upper left")
    return svg(fig)


def chart_elo(top, title):
    t = top.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    y = range(len(t))
    ax.hlines(y, t.normal_elo, t.pressure_elo, color="#d9d9d9", lw=3)
    ax.scatter(t.normal_elo, y, color=GREY, s=28, zorder=3, label="Normal Elo")
    ax.scatter(t.pressure_elo, y, color=ACCENT, s=28, zorder=3, label="Pressure Elo")
    ax.set_yticks(list(y))
    ax.set_yticklabels([p for p in t.player])
    ax.axvline(1500, color="#e6e6e6", lw=1, zorder=0)
    ax.set_xlabel(title)
    ax.legend(frameon=False, loc="lower right")
    return svg(fig)


def roles(b, top, role):
    pid = "striker_id" if role == "bat" else "bowler_id"
    d = b[b.bat_ball] if role == "bat" else b[b.legal]
    teams = pd.read_csv(os.path.join(P.PACK, "teams.csv")).drop_duplicates("team_id").set_index("team_id").team_name
    out = {}
    for i in top.head(10).index:
        mine = d[d[pid] == i]
        hp = mine[mine.hp]
        ipl = mine[mine.is_ipl].sort_values("match_date")
        last = ipl.iloc[-1] if len(ipl) else None
        out[i] = {
            "death": round(100 * (hp.over >= 15).mean()),
            "chase": round(100 * (hp.innings == 2).mean()),
            "ipl": round(100 * hp.is_ipl.mean()),
            "pos": int(mine.batting_order.mode()[0]) if role == "bat" else None,
            "style": mine.batting_type.mode()[0] if role == "bat" else mine.bowling_type.mode()[0],
            "kind": mine.pace_or_spin.mode()[0],
            "team": teams.get(last["batting_team_id" if role == "bat" else "bowling_team_id"]) if last is not None else None,
            "last_ipl": str(last.match_date)[:4] if last is not None else None,
        }
    return out


def names():
    teams = pd.read_csv(os.path.join(P.PACK, "teams.csv")).drop_duplicates("team_id").set_index("team_id").team_name
    m = pd.read_csv(os.path.join(P.PACK, "matches.csv")).merge(pd.read_csv(os.path.join(P.PACK, "competitions.csv")), on="comp_id")
    return teams, m.set_index("match_id")


def core(x, role):
    """The headline figures for a set of balls: one batter's (bat) or one bowler's (bowl)."""
    n = x.ball.sum()
    if role == "bat":
        outs = x.bat_out.sum()
        return {"Balls": n, "Runs": x.runs.sum(), "Strike rate": 100 * x.runs.sum() / n,
                "Balls per dismissal": n / outs if outs else None, "Dot balls": (x.runs == 0).mean(),
                "Boundary balls": (x.is_four | x.is_six).mean(), "Runs above average per 100 balls": 100 * x.bat_val.sum() / n}
    legal = x[x.legal]
    w = x.bowl_wkt.sum()
    return {"Balls": n, "Wickets": w, "Economy": 6 * x.conceded.sum() / n, "Balls per wicket": n / w if w else None,
            "Dot balls": (legal.conceded == 0).mean(), "Boundary balls": (legal.is_four | legal.is_six).mean(),
            "Runs saved per 100 balls": 100 * x.bowl_val.sum() / n}


def pool_ranks(b, top, role):
    """Rank of every qualified player's high-pressure figures among all qualified players (1 = best)."""
    if role == "bat":
        d, pid, lower = b[b.bat_ball & b.hp].assign(ball=1), "striker_id", ["Dot balls"]
    else:
        d, pid, lower = b[b.hp].assign(ball=b.legal.astype(int)), "bowler_id", ["Economy", "Balls per wicket", "Boundary balls"]
    d = d[d[pid].isin(top.index)]
    m = pd.DataFrame({i: core(x, role) for i, x in d.groupby(pid)}).T.astype(float)
    r = m.rank(ascending=False, method="min")
    r[lower] = m[lower].rank(method="min")  # for these, smaller is better
    assert len(r) == len(top)
    return r


def order_line(i, top):
    """His pressure-Elo gap to the players ranked either side: what decides his place in the order."""
    pos, elo = top.index.get_loc(i), top.pressure_elo.to_numpy()
    gaps = []
    if pos > 0:
        gaps.append(f"{elo[pos - 1] - elo[pos]:.2f} Elo below #{pos} {top.player.iloc[pos - 1]}")
    if pos + 1 < len(top):
        gaps.append(f"{elo[pos] - elo[pos + 1]:.2f} above #{pos + 2} {top.player.iloc[pos + 1]}")
    return ", ".join(gaps)


def profile(b, player_id, role):
    """Everything the player page shows: pressure against normal, pressure splits, years, best pressure match."""
    teams, matches = names()
    if role == "bat":
        d = b[b.bat_ball & (b.striker_id == player_id)].assign(ball=1)
        val, opp = "bat_val", "bowling_team_id"
    else:
        d = b[b.bowler_id == player_id].assign(ball=b.legal.astype(int))
        val, opp = "bowl_val", "batting_team_id"

    hp = d[d.hp]
    rate = (lambda x: 100 * x.runs.sum() / x.ball.sum()) if role == "bat" else (lambda x: 6 * x.conceded.sum() / x.ball.sum())
    first, second = ("Batting first", "Chasing") if role == "bat" else ("Bowling first", "Defending a total")
    cuts = [(second, hp.innings == 2), (first, hp.innings == 1), ("Overs 16-20", hp.over >= 15),
            ("Overs 1-15", hp.over < 15), ("IPL", hp.is_ipl), ("T20I", ~hp.is_ipl)]
    if role == "bat":
        cuts += [("v pace", hp.pace_or_spin == "Pace"), ("v spin", hp.pace_or_spin == "Spin")]
    else:
        cuts += [("v right-handers", hp.batting_type == "RHB"), ("v left-handers", hp.batting_type == "LHB")]
    splits = [(label, int(hp[m].ball.sum()), rate(hp[m])) for label, m in cuts if hp[m].ball.sum() >= 30]
    year = hp.match_date.str[:4]
    years = [(y, int(g.ball.sum()), 100 * g[val].sum() / g.ball.sum()) for y, g in hp.groupby(year) if g.ball.sum() >= 20]

    pm = hp.groupby("match_id").agg(value=(val, "sum"), balls=("ball", "sum"), runs=("runs" if role == "bat" else "conceded", "sum"),
                                    outs=("bat_out" if role == "bat" else "bowl_wkt", "sum"), opp=(opp, "first"))
    top = pm.sort_values("value", ascending=False).iloc[0]
    mi = matches.loc[top.name]
    best = {"date": mi.match_date, "comp": mi.comp_name, "opp": teams.get(top.opp), "runs": int(top.runs),
            "balls": int(top.balls), "outs": int(top.outs), "value": top.value}
    return {"pressure": core(hp, role), "normal": core(d[~d.hp], role), "splits": splits, "years": years, "best": best,
            "matches": hp.match_id.nunique()}


def rr_2026(b):
    s = b[b.is_ipl & (b.match_date >= "2026-01-01") & b.hp]
    teams = pd.read_csv(os.path.join(P.PACK, "teams.csv")).drop_duplicates("team_id").set_index("team_id").team_name
    bat = s[s.bat_ball].groupby(s.batting_team_id.map(teams)).bat_val.agg(["sum", "size"])
    bowl = s.groupby(s.bowling_team_id.map(teams)).agg(val=("bowl_val", "sum"), balls=("legal", "sum"))  # wides count too
    bat_rank = (100 * bat["sum"] / bat["size"]).rank(ascending=False).astype(int)
    bowl_rank = (bowl.val / bowl.balls).rank(ascending=False).astype(int)
    phase = pd.cut(s.over, [-1, 5, 14, 19], labels=["Powerplay", "Middle", "Death"])
    econ = lambda m: 6 * s[m].groupby(phase[m], observed=True).conceded.sum() / s[m].groupby(phase[m], observed=True).legal.sum()  # noqa: E731
    rr = s.bowling_team_id.map(teams) == "Rajasthan Royals"
    league = pd.Series(True, index=s.index)
    return {"bat_rank": bat_rank["Rajasthan Royals"], "bowl_rank": bowl_rank["Rajasthan Royals"],
            "rr_econ": econ(rr).round(1), "lg_econ": econ(league).round(1), "rr_balls": int(s[rr].legal.sum())}


def fmt(k, v):
    if v is None:
        return "-"
    if k in ("Dot balls", "Boundary balls"):
        return f"{v:.0%}"
    if k in ("Balls", "Runs", "Wickets"):
        return f"{int(v):,}"
    if "per 100" in k:
        return f"{v:+.0f}"
    return f"{v:.1f}"


def facts(rank, r, pr, role, tag, note, rk, pool, order):
    """One player's profile as display strings: the PDF card and the dashboard both render from this."""
    p, n, bb = pr["pressure"], pr["normal"], pr["best"]
    day = pd.Timestamp(bb["date"])
    what = (f"{bb['runs']} off {bb['balls']} pressure balls" if role == "bat"
            else f"{bb['outs']} for {bb['runs']} in {bb['balls']} pressure balls")
    return {"rank": rank, "name": r.player, "tag": tag, "elo": int(round(r.pressure_elo)), "normalElo": int(round(r.normal_elo)),
            "matches": int(pr["matches"]), "good": int(round(100 * r.consistency)), "note": note, "pool": pool, "order": order,
            "unit": "Strike rate" if role == "bat" else "Economy",
            "measure": "runs above average" if role == "bat" else "runs saved",
            "figures": [[k, fmt(k, p[k]), fmt(k, n[k]), None if pd.isna(rk[k]) else int(rk[k])] for k in p],
            "splits": [[label, balls, f"{v:.0f}" if role == "bat" else f"{v:.1f}"] for label, balls, v in pr["splits"]],
            "years": [[y, n_, int(round(v))] for y, n_, v in pr["years"]],
            "best": f"{what} against {bb['opp']}, {bb['comp']}, {day.day} {day:%b %Y}"}


def card(f):
    figs = table([(k, a, b, "-" if rank is None else rank) for k, a, b, rank in f["figures"]],
                 ["", "Under pressure", "Normal", f"Rank of {f['pool']}"])
    splits = table(f["splits"], ["Under pressure", "Balls", f["unit"]])
    years = " · ".join(f"{y}: {v:+d} ({n} balls)" for y, n, v in f["years"])
    return f"""<div class="card"><h3>{f['rank']}. {f['name']}</h3>
<p class="meta">{f['tag']} · Pressure Elo {f['elo']} (normal {f['normalElo']}) · {f['matches']} matches · {f['good']}% good matches</p>
<p>{f['note']}</p>
<div class="two">{figs}{splits}</div>
<p class="small"><b>Place in the order:</b> {f['order']}.</p>
<p class="small"><b>By year</b>, {f['measure']} per 100 pressure balls: {years}</p>
<p class="small"><b>Best pressure match:</b> {f['best']}.</p></div>"""


def checks_table():
    rows, split = [], {}
    for line in open(os.path.join(P.OUT, "checks.txt")).read().splitlines():
        m = re.match(r"(.+?)\s+(bat|bowl)\s+top-10 names kept: (\d+)/10", line)
        if m:
            rows.append((m.group(1).strip(), m.group(2), m.group(3)))
        m = re.match(r"split-half correlation (bat|bowl).*pressure_elo r=([-\d.]+)\s+level r=([-\d.]+)", line)
        if m:
            split[m.group(1)] = (m.group(2), m.group(3))
    table = {}
    for label, role, kept in rows:
        table.setdefault(label, {})[role] = kept
    return table, split


def table(rows, head):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def build():
    b = P.build()
    bat, bowl = P.rate(b, "bat"), P.rate(b, "bowl")
    f = b[b.bat_ball]
    hp, nm = f[f.hp], f[~f.hp]
    ko = b.groupby("knock_out").hp.mean()
    death1 = b[(b.innings == 1) & (b.over >= 15)].hp.mean()
    chase_mid = b[(b.innings == 2) & b.over.between(6, 14)].hp.mean()
    rr = rr_2026(b)
    rb, rw = roles(b, bat, "bat"), roles(b, bowl, "bowl")
    checks, split = checks_table()
    t20i_only = [top.player[i] for top, rr_ in ((bat, rb), (bowl, rw)) for i in top.head(10).index if rr_[i]["ipl"] == 0]
    n_ipl, n_t20i = b[b.is_ipl].match_id.nunique(), b[~b.is_ipl].match_id.nunique()
    threshold = b.pi.quantile(P.PRESSURE_QUANTILE)

    picks = table([(i + 1, bat.player.iloc[i], bowl.player.iloc[i]) for i in range(10)],
                  ["Rank", "Batter", "Bowler"])

    bat_rows = [(int(r["rank"]), r.player, int(r.hp_balls), int(r.hp_matches), f"{r.hp_sr:.0f}", f"{r.normal_sr:.0f}",
                 int(r.hp_outs), f"{100 * r.consistency:.0f}%", f"{r.normal_elo:.0f}", f"<b>{r.pressure_elo:.0f}</b>")
                for _, r in bat.head(10).iterrows()]
    bowl_rows = [(int(r["rank"]), r.player, int(r.hp_balls), int(r.hp_matches), f"{r.hp_econ:.2f}", f"{r.normal_econ:.2f}",
                  int(r.hp_wkts), f"{100 * r.consistency:.0f}%", f"{r.normal_elo:.0f}", f"<b>{r.pressure_elo:.0f}</b>")
                 for _, r in bowl.head(10).iterrows()]

    def bat_role(x):
        if x["pos"] >= 6 or x["death"] >= 45:
            return "Finisher"
        return "Middle order, chases" if x["chase"] >= 60 else "Middle order"

    def bowl_role(x):
        if x["team"] == "Rajasthan Royals":
            return "Already at RR: keep"
        if x["death"] >= 50:
            return "Death overs"
        return "Middle overs" if "Spin" in x["kind"] else "New ball and middle"

    for top in (bat, bowl):
        missing = [top.player[i] for i in top.head(10).index if i not in NOTES]
        assert not missing, f"write a note in notes.py for {missing}"

    def tag(x, role):
        side = f"Last IPL side: {x['team']} ({x['last_ipl']})" if x["team"] else "No IPL matches in the data"
        return f"{bat_role(x) if role == 'bat' else bowl_role(x)} · {side}"

    rk_bat, rk_bowl = pool_ranks(b, bat, "bat"), pool_ranks(b, bowl, "bowl")
    f_bat = [facts(int(r["rank"]), r, profile(b, i, "bat"), "bat", tag(rb[i], "bat"), NOTES[i],
                   rk_bat.loc[i], len(bat), order_line(i, bat)) for i, r in bat.head(10).iterrows()]
    f_bowl = [facts(int(r["rank"]), r, profile(b, i, "bowl"), "bowl", tag(rw[i], "bowl"), NOTES[i],
                    rk_bowl.loc[i], len(bowl), order_line(i, bowl)) for i, r in bowl.head(10).iterrows()]
    cards_bat, cards_bowl = "".join(map(card, f_bat)), "".join(map(card, f_bowl))

    pretty = {"pressure = top 20% of balls": "Pressure = top 20% of balls (I use 25%)",
              "pressure = top 30% of balls": "Pressure = top 30% of balls",
              "wicket worth 4 runs": "A wicket worth 4 runs (I use 6)", "wicket worth 8 runs": "A wicket worth 8 runs"}
    check_rows = [(pretty.get(label, label), f"{v.get('bat', '-')}/10", f"{v.get('bowl', '-')}/10") for label, v in checks.items()]
    econ = rr["rr_econ"], rr["lg_econ"]

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Reliable under pressure</title>
<style>
@page {{ size: A4; margin: 18mm 18mm 20mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; color: {INK}; font-size: 10pt; line-height: 1.5; margin: 0; }}
h1 {{ font-size: 20pt; margin: 0 0 4pt; font-weight: 600; }}
h2 {{ font-size: 13pt; margin: 20pt 0 6pt; font-weight: 600; break-after: avoid; }}
h3 {{ font-size: 10.5pt; margin: 12pt 0 4pt; font-weight: 600; break-after: avoid; }}
p {{ margin: 0 0 7pt; }}
.sub {{ color: #555; margin-bottom: 14pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; break-inside: avoid; }}
th {{ text-align: left; font-weight: 600; border-bottom: 1px solid {INK}; padding: 3pt 6pt 3pt 0; }}
td {{ border-bottom: 1px solid #e3e3e3; padding: 3pt 6pt 3pt 0; }}
ul {{ margin: 0 0 8pt; padding-left: 14pt; }} li {{ margin-bottom: 3pt; }}
.fig {{ margin: 4pt 0 10pt; break-inside: avoid; }} .fig svg {{ width: 100%; height: auto; }}
.note {{ font-size: 9pt; color: #555; }}
.page {{ break-before: page; }}
.card {{ break-inside: avoid; border-top: 1px solid #d0d0d0; padding-top: 8pt; margin-top: 12pt; }}
.card h3 {{ margin: 0 0 2pt; font-size: 11pt; }}
.card table {{ margin: 2pt 0 5pt; font-size: 8.5pt; }}
.card th, .card td {{ padding: 1.5pt 6pt 1.5pt 0; }}
.meta {{ color: #555; font-size: 8.5pt; margin-bottom: 5pt; }}
.small {{ font-size: 8.5pt; margin-bottom: 3pt; }}
.two {{ display: grid; grid-template-columns: 1.5fr 1fr; gap: 16pt; align-items: start; }}
h2.group {{ font-size: 11.5pt; margin-top: 14pt; }}
</style></head><body>

<h1>Reliable under pressure</h1>
<p class="sub">SupeRR Selector Season 2, Round 1. IPL and T20I ball-by-ball data, 2022 to 2026.</p>

<p>I scored every ball in the data pack for how much pressure the batting side was under, then rated each player on the
high-pressure balls only, using a batter-against-bowler Elo. These are my two lists.</p>
{picks}

<p>Ratings come from {len(b):,} balls in {n_ipl} IPL and {n_t20i} T20I matches. Everything below can be rebuilt from the
data pack with two Python scripts (last section).</p>

<h2>1. What counts as pressure</h2>
<p>Pressure is about the state of the match before the ball is bowled, not about what happens on it. I rebuilt the score,
wickets, legal balls and target for every delivery and combined three signals into a pressure index from 0 to 1.</p>
<ul>
<li><b>Required rate</b> (chases only). Six an over counts as routine and fifteen as extreme, scaled in between. A chase
that needs more than 18 an over, or is already won, scores zero: the result is no longer in doubt.</li>
<li><b>Collapse</b>. Wickets lost compared with the average for that over and innings. Three wickets above par is the maximum.</li>
<li><b>Time left</b>. How far through the innings the ball is. The same situation is harder to fix with four balls left
than with forty.</li>
</ul>
<p>Chasing: 0.5 required rate + 0.2 collapse + 0.3 time. Batting first: 0.5 collapse + 0.5 time, because there is no
target yet. Knockout matches get a 10% uplift. The top quarter of balls by index (index of {threshold:.2f} or more) are
high pressure; that is {int(b.hp.sum()):,} balls.</p>

<h3>Does it pick out different situations?</h3>
{table([("Balls", f"{len(nm):,}", f"{len(hp):,}"),
        ("Balls per wicket", f"{1 / nm.bat_out.mean():.1f}", f"{1 / hp.bat_out.mean():.1f}"),
        ("Strike rate", f"{100 * nm.runs.mean():.1f}", f"{100 * hp.runs.mean():.1f}"),
        ("Dot balls", f"{(nm.runs == 0).mean():.0%}", f"{(hp.runs == 0).mean():.0%}"),
        ("Boundary balls", f"{(nm.is_four | nm.is_six).mean():.0%}", f"{(hp.is_four | hp.is_six).mean():.0%}")],
       ["", "Normal balls", "High-pressure balls"])}
<p>Wickets fall {hp.bat_out.mean() / nm.bat_out.mean() - 1:.0%} more often under pressure, and the scoring rate
does not drop. Pressure also turns up
where cricket sense says it should: {death1:.0%} of balls in overs 16-20 of a first innings, {chase_mid:.0%} of the middle
overs of a chase, and {ko[1]:.0%} of balls in knockout games against {ko[0]:.0%} in league games.</p>
<div class="fig">{chart_pressure_by_over(b)}</div>

<h2>2. How players are rated</h2>
<h3>Value of each ball</h3>
<p>A strike rate of 160 in the 19th over of a chase is not the same as 160 in the powerplay. So each ball is first compared
with what an average player did in the same context: same format (IPL or T20I), innings, over and pressure band. The
batter's value is runs above that average, minus 6 runs for a dismissal above the average rate. The bowler's value is the
mirror image: runs saved, plus 6 runs a wicket. Byes and leg-byes are not charged to the bowler; wides and no-balls are.</p>

<h3>Pressure Elo</h3>
<p>Every high-pressure ball is a duel. The batter scores 0.5 for an average ball, more for a good one, close to 0 if out;
the bowler gets the rest. Both start at 1500, and ratings move after each ball in date order. The expected score depends
on the rating gap, so runs off a top bowler count for more than runs off a weak one, and the same for wickets. The step
size is small (K = 2 a ball) because one ball tells you little; of the step sizes I tried (2, 4 and 8), 2 gave the most
repeatable ratings.</p>

<h3>Baseline</h3>
<p>The same Elo run on normal balls gives each player's usual level. The tables show both, so you can see who rises and
who simply keeps their level. The ranking itself uses the pressure Elo, because the brief asks who delivers most when it
matters, not who improves the most.</p>

<h3>Fair comparisons</h3>
<ul>
<li><b>Sample size.</b> At least {P.MIN_PRESSURE_BALLS} high-pressure balls across {P.MIN_PRESSURE_MATCHES} or more matches.
Elo itself starts everyone at 1500 and only moves them with evidence, so short records stay close to average.</li>
<li><b>Active players.</b> At least one match since January 2025.</li>
<li><b>Players RR can sign.</b> Pakistan internationals are left out of the rankings because IPL teams cannot sign them.
They still count as opponents in everyone else's ratings. Without this rule Sufiyan Muqeem and Abrar Ahmed would be 2nd
and 5th among bowlers. Andre Russell is left out for the same reason: he retired from the IPL in November 2025. He would
otherwise be 6th among batters.</li>
<li><b>IPL and T20I.</b> Both are used. Averages are set separately for each, and the Elo rewards beating strong
opponents, so runs against weaker T20I attacks count for less.</li>
<li><b>Match context.</b> Rain-revised targets and overs are used for the chase. Super overs are left out.</li>
</ul>
<p>That leaves {len(bat)} batters and {len(bowl)} bowlers who qualify.</p>

<h2 class="page">3. Top 10 batters</h2>
{table(bat_rows, ["#", "Batter", "Pressure balls", "Matches", "SR pressure", "SR normal", "Outs", "Good matches*", "Normal Elo", "Pressure Elo"])}
<p class="note">*Share of matches (3+ pressure balls) where his pressure balls were worth more than average, pulled towards 50% when there are few matches.</p>
<div class="fig">{chart_elo(bat, "Batting Elo")}</div>
<p>Tim David is top without a pressure lift: his strike rate is the same either way, and he does it against strong attacks.
Namboori Tilak Varma, Shashank Singh, Shivam Dube and Azmatullah Omarzai gain 18 to 21 Elo points when the pressure is on.
Klaasen and Shreyas Iyer simply hold their usual high level.</p>

<h2 class="page">4. Top 10 bowlers</h2>
{table(bowl_rows, ["#", "Bowler", "Pressure balls", "Matches", "Econ pressure", "Econ normal", "Wkts", "Good matches*", "Normal Elo", "Pressure Elo"])}
<p class="note">*Share of matches (3+ pressure balls) where his pressure balls were worth more than average, pulled towards 50% when there are few matches.</p>
<div class="fig">{chart_elo(bowl, "Bowling Elo")}</div>
<p>Six of the ten are spinners. Narine is clear at the top. Bumrah, Mustafizur and Varun Chakravarthy are here for their
level, not a jump: their normal Elo is a little higher, and Santner's is the same. Archer and Taskin Ahmed are the seamers
whose Elo rises under pressure.</p>

<h2 class="page">5. Player profiles</h2>
<p>Why each player is on the list. Each profile compares his high-pressure balls with his normal balls, and the "Rank of"
column places his high-pressure figure among every qualified player ({len(bat)} batters, {len(bowl)} bowlers). Rank 1 is
best; for a batter's dot balls, and a bowler's economy, balls per wicket and boundary balls, the lowest number ranks
first. "Place in the order" gives his pressure-Elo gap to the players either side, which is what sets his rank; for the
10th player it is the margin over the first player left out. The profile also splits the
pressure balls by situation, shows every year with at least 20 pressure balls, and names his best pressure match.
"Runs above average" (batters) and "runs saved" (bowlers) are the ball values from section 2, per 100 balls. Roles follow
simple rules on the data: a batter is a finisher if he usually bats at 6 or lower or takes 45% or more of his pressure
balls in overs 16-20; a bowler is a death bowler if half or more of his pressure balls are in overs 16-20.</p>
<h2 class="group">Batters</h2>
{cards_bat}
<h2 class="group page">Bowlers</h2>
{cards_bowl}

<h2 class="page">6. What this means for RR</h2>
<p>RR's own 2026 IPL season, rated the same way, ranked {rr['bat_rank']} of 10 for batting under pressure and
{rr['bowl_rank']} of 10 for bowling under pressure. The bowling gap was in the middle overs: {econ[0]['Middle']} an over
under pressure against a league average of {econ[1]['Middle']}. At the death RR conceded {econ[0]['Death']} against
{econ[1]['Death']}, a little better than average. ({rr['rr_balls']} high-pressure balls, so treat this as a direction, not a verdict.)</p>
<p>So the most useful signings are bowlers who can hold the middle overs while a chase is still alive, and that is
where the spinners on this list do most of their work.</p>

<p class="note">Retention lists for IPL 2027 were not public when I wrote this, so whether a player reaches the auction is
not known yet.</p>

<h2>7. Reliability and limitations</h2>
<h3>Do the lists hold if I change the judgement calls?</h3>
{table(check_rows, ["Change", "Batters still in top 10", "Bowlers still in top 10"])}
<h3>Is it a real skill or luck?</h3>
<p>I split the matches into two halves (odd and even) and rated players on each half separately. If pressure performance
is a skill, the two ratings should agree. For batters the pressure Elo correlates at {split['bat'][0]} across halves, against
{split['bat'][1]} for a simple runs-above-average score. For bowlers it is {split['bowl'][0]} against {split['bowl'][1]}.</p>
<ul>
<li>The batting list is reasonably stable. The bowling list is not: Narine is clear, and ranks 2 to 10 sit within six Elo points.</li>
<li>Ranks 4 to 10 in both lists are within a few Elo points of each other.</li>
<li>Elo moves further with more balls, so it favours players with long records over short, strong ones.</li>
<li>{" and ".join(t20i_only)} {"has" if len(t20i_only) == 1 else "have"} no IPL matches in the data, so {"his rating comes" if len(t20i_only) == 1 else "their ratings come"}
from T20Is only. The opponent adjustment helps, but there is less evidence than for IPL regulars.</li>
<li>In a first innings the time signal alone puts the last two overs above the threshold, whatever the score. Those overs
are hard to bat in, but the label is automatic there.</li>
<li>The data has no fielding positions, field settings or Impact Player tactics, and 2022 to 2026 is a short window.</li>
</ul>

<h2>8. How to reproduce</h2>
<p><code>python analysis/pressure.py --check</code> rebuilds the match state, the ratings and the checks, and writes every
eligible player to <code>batters.csv</code> and <code>bowlers.csv</code>. <code>python analysis/report.py</code> builds this
report. Both use only the data pack, pandas, numpy and matplotlib.</p>
</body></html>"""
    os.makedirs(DIR, exist_ok=True)
    page = os.path.join(DIR, "report.html")
    open(page, "w", encoding="utf-8").write(html)
    pdf = os.path.join(DIR, "report.pdf")
    edge_profile = os.path.join(DIR, ".edge-profile")  # own profile, so an open Edge window cannot swallow the print job
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={edge_profile}",
                    f"--print-to-pdf={pdf}", "file:///" + page.replace(os.sep, "/")], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    shutil.rmtree(edge_profile, ignore_errors=True)
    assert os.path.getsize(pdf) > 20000, "PDF looks empty"
    print("wrote", pdf)

    # Data for the dashboard page (dashboard/index.html is written by hand and reads this), plus the PDF it links to.
    share = b.groupby(["innings", "over"]).hp.mean().unstack(0) * 100
    data = {"bat": f_bat, "bowl": f_bowl, "byOver": {"first": share[1].round(1).tolist(), "chase": share[2].round(1).tolist()},
            "rr": {"phases": list(rr["rr_econ"].index), "rr": rr["rr_econ"].tolist(), "league": rr["lg_econ"].tolist()},
            "cut": {role: [[r.player, round(float(r.pressure_elo), 2)] for _, r in top.head(12).iterrows()]
                    for role, top in (("bat", bat), ("bowl", bowl))}}
    dash_dir = os.path.join(P.HERE, "..", "dashboard")
    open(os.path.join(dash_dir, "players.js"), "w", encoding="utf-8").write("window.RR = " + json.dumps(data) + ";\n")
    shutil.copy(pdf, os.path.join(dash_dir, "report.pdf"))
    print("wrote", os.path.join(dash_dir, "players.js"))


if __name__ == "__main__":
    build()
