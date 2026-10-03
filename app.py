"""Streamlit entry point for the ops room dashboard: who is likely to go over 55 hours by Sunday, and where."""
import html

import pandas as pd

import streamlit as st

from src.dataset import apply_upload, code_version, content_hash, load_bundled
from src.export import predictions_csv
from src.forecast import CAP
from src.notes import CATEGORY_LABELS, PILE
from src.pipeline import run
from src.validate import FILE_NAMES, check_file

st.set_page_config(page_title="Overtime watch", layout="wide", initial_sidebar_state="collapsed")

HIGH_LEVELS = ["High", "Over"]      # 50%+ risk (or already over the cap): a card with a Resolve button
MAX_OVERLAPS = 20

CSS = """
<style>
.block-container {max-width: 1100px; padding-top: 1.5rem;}
.tiles {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 0.5rem 0 1rem;}
.tile {border: 1px solid rgba(128,128,128,.3); border-radius: 12px; padding: 10px 14px;}
.tile b {display: block; font-size: 1.8rem; line-height: 1.2;}
.tile span {font-size: .85rem; opacity: .75;}
.tile.red {background: rgba(220,38,38,.12); border-color: rgba(220,38,38,.5);}
.tile.amber {background: rgba(245,158,11,.14); border-color: rgba(245,158,11,.5);}
.card {border: 1px solid rgba(128,128,128,.3); border-left: 6px solid #9ca3af; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; scroll-margin-top: 80px;}
.card.high {border-left-color: #dc2626; background: rgba(220,38,38,.10);}
.card.flag {border-left-color: #f59e0b; background: rgba(245,158,11,.12);}
.card:target {outline: 3px solid #dc2626; outline-offset: 2px;}
.card .top {display: flex; justify-content: space-between; align-items: center; gap: 10px;}
.card .name {font-weight: 700; font-size: 1.05rem;}
.card .badge {font-weight: 700; border-radius: 999px; padding: 2px 12px; color: #fff; white-space: nowrap; background: #9ca3af;}
.card.high .badge {background: #dc2626;}
.card.flag .badge {background: #d97706;}
.card .sub {font-size: .85rem; opacity: .8; margin-top: 2px;}
.card .stats {display: flex; flex-wrap: wrap; gap: 6px 22px; margin: 8px 0 4px;}
.card .stats div b {display: block; font-size: 1.15rem;}
.card .stats div span {font-size: .75rem; opacity: .7;}
.tag {display: inline-block; font-size: .72rem; font-weight: 700; border-radius: 6px; padding: 1px 7px; margin-left: 6px; background: rgba(128,128,128,.25); text-decoration: none;}
.tag.esc {background: #dc2626; color: #fff !important;}
.tag.rev {background: #f59e0b; color: #1f2937 !important;}
a.tag.esc:hover {background: #b91c1c;}
.legs {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin: 8px 0 2px;}
.leg {border: 1px solid rgba(128,128,128,.3); border-radius: 8px; padding: 6px 10px; font-size: .85rem;}
.leg b {display: block;}
.card.low {border-left-color: #9ca3af;}
.card.compact {padding: 8px 12px; margin-bottom: 6px;}
.card .line {font-size: .85rem; opacity: .85; margin-top: 2px;}
details.why {margin-top: 8px;}
details.why summary {cursor: pointer; display: inline-block; list-style: none; border: 1px solid rgba(128,128,128,.55); border-radius: 8px; padding: 2px 11px; font-size: .82rem; font-weight: 600;}
details.why summary::-webkit-details-marker {display: none;}
details.why[open] summary {background: rgba(128,128,128,.18);}
details.why .whybody {font-size: .88rem; margin-top: 6px;}
details.why .head {font-weight: 600; margin-bottom: 4px;}
details.why ul {margin: 4px 0 0; padding-left: 1.1rem;}
details.why li {margin-bottom: 3px;}
.pill {display: inline-block; font-size: .75rem; font-weight: 700; border-radius: 999px; padding: 1px 9px; margin: 0 4px 3px 0; color: #fff; background: #6b7280;}
.pill.client {background: #2563eb;} .pill.operational {background: #dc2626;} .pill.absence {background: #d97706;} .pill.none {background: #6b7280;}
/* a person's box drawn by Streamlit, so the buttons sit inside it: same look as the HTML boxes, buttons side by side even on a phone */
[class*="st-key-card_"] {border: 1px solid rgba(128,128,128,.3) !important; border-left: 6px solid #9ca3af !important; border-radius: 12px !important; padding: 12px 14px; margin-bottom: 10px;}
[class*="st-key-card_high_"] {border-left-color: #dc2626 !important; background: rgba(220,38,38,.10);}
[class*="st-key-card_flag_"] {border-left-color: #f59e0b !important; background: rgba(245,158,11,.12);}
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap: .5rem !important;}
[class*="st-key-card_"] [data-testid="stColumn"] {min-width: 0 !important; flex: 0 0 auto !important; width: auto !important;}
[class*="st-key-card_high_"] .badge {background: #dc2626;}
[class*="st-key-card_flag_"] .badge {background: #d97706;}
.card.cardbody {border: 0; background: none; padding: 0; margin: 0 0 6px; border-radius: 0;}
.status {opacity: .8; margin: -0.4rem 0 0.6rem;}
.stButton button {padding: 0.15rem 0.9rem; min-height: 2rem;}
/* message that drops in at the top for about two seconds, then goes away (two copies so it replays on every click) */
@keyframes dropA {0% {transform: translate(-50%, -140%); opacity: 0;} 9% {transform: translate(-50%, 0); opacity: 1;} 78% {transform: translate(-50%, 0); opacity: 1;} 100% {transform: translate(-50%, -140%); opacity: 0; visibility: hidden;}}
@keyframes dropB {0% {transform: translate(-50%, -140%); opacity: 0;} 9% {transform: translate(-50%, 0); opacity: 1;} 78% {transform: translate(-50%, 0); opacity: 1;} 100% {transform: translate(-50%, -140%); opacity: 0; visibility: hidden;}}
.notice {position: fixed; top: 10px; left: 50%; z-index: 1000000; width: min(92vw, 560px); box-sizing: border-box; background: #065f46; color: #fff;
         padding: 10px 16px; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,.35); font-size: .95rem; text-align: center;
         transform: translate(-50%, -140%); opacity: 0; animation: dropA 2.6s ease forwards;}
.notice.b {animation-name: dropB;}
</style>
"""


def esc(x):
    return html.escape(str(x))


def attr(x):
    return html.escape(str(x), quote=True)


def join_days(days):
    short = [d[:3] for d in days]
    return short[0] if len(short) == 1 else ", ".join(short[:-1]) + " and " + short[-1]


@st.cache_data(show_spinner="Checking the data and running the model...", max_entries=8)
def cached_run(data_hash, version, _bundle):
    # `version` is the fingerprint of the source files: after a new deploy an old cached result is not reused
    return run(_bundle)


def init_state():
    if "bundle" not in st.session_state:
        st.session_state.bundle = load_bundled()
        st.session_state.source = "the bundled example data"
        st.session_state.messages = []
        st.session_state.uploader_key = 0


def notify(action, who=None):
    """Drop-down message at the top for a moment. This is a placeholder: nothing is actually sent yet."""
    detail = f"{action}, {who}" if who else action
    st.session_state.notice_n = st.session_state.get("notice_n", 0) + 1
    css = "notice b" if st.session_state.notice_n % 2 else "notice"
    st.markdown(f'<div class="{css}" role="status">Sent message to supervisor: {esc(detail)} (sent by internal tool or email)</div>', unsafe_allow_html=True)


def site_text(site_ids, labels):
    return ", ".join(labels.get(s, s) for s in site_ids) if site_ids else "none yet"


def span(start, end):
    text = f"{start:%a %d %b %H:%M} to {end:%H:%M}"
    return text + (f" ({end:%a})" if end.date() != start.date() else "")


def reason_index(res):
    """person_key -> that person's sorted notes (newest first); None when no notes are loaded."""
    if res.reasons is None:
        return None
    return {k: g for k, g in res.reasons.groupby("person_key")}


def why_body(person_key, res, index):
    """What the 'Why the hours happened' box shows: this week's notes, or the last four weeks if there are none this week."""
    if index is None:
        return ""
    mine = index.get(person_key)
    if mine is None or mine.empty:
        body = '<div class="head">No supervisor notes for this person.</div>'
    else:
        this = mine[mine["this_week"]]
        recent = mine[mine["shift_date"] >= res.week_start - pd.Timedelta(days=28)]
        count = lambda d: f"{len(d)} note{'s' if len(d) != 1 else ''}"
        if (this["category"] != "nothing_useful").any():
            shown, head = this, f"This week ({count(this)})"
        elif (recent["category"] != "nothing_useful").any():
            shown = recent
            head = ("Nothing useful this week. " if len(this) else "No note this week. ") + f"Last 4 weeks ({count(recent)})"
        else:
            shown, head = recent, "No useful supervisor notes in the last 4 weeks."
        body = f'<div class="head">{esc(head)}</div>'
        if len(shown):
            useful = shown[shown["category"] != "nothing_useful"]
            counts = useful["category"].value_counts()
            body += "".join(f'<span class="pill {PILE.get(c, "none")}">{esc(CATEGORY_LABELS.get(c, c))} · {n}</span>' for c, n in counts.items())
            blank = len(shown) - len(useful)
            if blank:
                body += f'<span class="pill none">Nothing useful · {blank}</span>'
            items = "".join(f"<li>{esc(f'{r.shift_date:%a %d %b}')} · {esc(site_text([r.site_id], res.site_labels))} · <b>{esc(CATEGORY_LABELS.get(r.category, r.category))}</b>"
                            f" — “{esc(r.note)}”</li>" for r in useful.head(3).itertuples())
            if items:
                body += f"<ul>{items}</ul>"
    return f'<div class="whybody">{body}</div>'


def why_html(person_key, res, index):
    """The same box as an open-in-place control, for the compact boxes (a pop-up for each of 185 people would be heavy)."""
    body = why_body(person_key, res, index)
    return f'<details class="why"><summary>Why the hours happened</summary>{body}</details>' if body else ""


def card(p, res, css="high", index=None, compact=False, shell=True):
    """The HTML of one person's box. shell=False gives the contents only, for a box that Streamlit draws around buttons."""
    labels = res.site_labels
    over = p.hours_so_far > CAP
    badge = f"Over by {p.hours_so_far - CAP:.1f} h" if over else (f"{p.risk_score:.0%} risk" if res.status == "model" else "Over")
    ids = " · ".join(p.employee_ids)
    flag = f' <a class="tag esc" href="#esc-{attr(p.person_key)}">2 records, see Escalations</a>' if len(p.employee_ids) > 1 else ""
    aka = f" (also recorded as {', '.join(p.also_known_as)})" if p.also_known_as else ""
    sub = esc(ids) + (f" · {esc(p.role)}" if p.role else "") + flag
    primary = f"Primary site: {esc(site_text(p.primary_sites, labels))}" if p.primary_sites else ""
    worked = f"Worked this week: {esc(site_text(p.sites_worked, labels))}"
    if compact:
        line = f"{p.hours_so_far:.1f} h so far" + (f" · {p.usual_hours_to_go:.1f} usual hours still to come" if res.status == "model" else "")
        return (f'<div class="card {css} compact"><div class="top"><span class="name">{esc(p.name)}</span>'
                f'<span class="badge">{esc(badge)}</span></div><div class="sub">{sub}</div>'
                f'<div class="line">{esc(line)}</div>{why_html(p.person_key, res, index)}</div>')
    usual = (f'<div><b>{p.usual_shifts_left:.1f}</b><span>usual shifts left this week</span></div>'
             f'<div><b>{p.usual_hours_to_go:.1f}</b><span>usual hours still to come</span></div>' if res.status == "model" else "")
    root = f"card {css}" if shell else "card cardbody"
    return (f'<div class="{root}"><div class="top"><span class="name">{esc(p.name)}{esc(aka)}</span>'
            f'<span class="badge">{esc(badge)}</span></div><div class="sub">{sub}</div>'
            f'<div class="sub">{primary}{" · " if primary else ""}{worked}</div>'
            f'<div class="stats"><div><b>{p.hours_so_far:.1f}</b><span>hours so far</span></div>'
            f'<div><b>{int(p.shifts_so_far)}</b><span>shifts so far</span></div>'
            f'<div><b>{p.hours_left:.1f}</b><span>hours left to {CAP}</span></div>{usual}</div></div>')


def person_box(p, res, index, css, resolve=False):
    """One person's box with, inside it, the Why pop-up and (for people at 50%+) the Resolve button side by side."""
    with st.container(border=True, key=f"card_{css}_{p.person_key}"):
        st.markdown(card(p, res, css, shell=False), unsafe_allow_html=True)
        slots = (["why"] if index is not None else []) + (["resolve"] if resolve else [])
        if slots:
            cols = st.columns(len(slots))
            for col, slot in zip(cols, slots):
                if slot == "why":
                    with col.popover("Why the hours happened"):
                        st.markdown(why_body(p.person_key, res, index), unsafe_allow_html=True)
                elif col.button("Resolve", key=f"resolve_{p.person_key}"):
                    notify("resolving an overtime person", p.name)


def tiles(res):
    p = res.people
    high = p[p["level"].isin(HIGH_LEVELS)]
    sites_hit = len({s for lst in high["sites_worked"] for s in lst})
    dup_items = 0 if res.duplicates is None else len(res.duplicates)
    over_items = 0 if res.overlaps_current is None else len(res.overlaps_current)
    open_n = 0 if res.open_shifts is None else len(res.open_shifts)
    first = "went over the cap" if res.status == "week_complete" else ("at 50%+ risk of going over" if res.status == "model" else "already over the cap")
    items = [("red" if len(high) else "", len(high), f"people {first}"),
             ("amber" if sites_hit else "", sites_hit, "sites affected"),
             ("amber" if dup_items + over_items else "", dup_items + over_items, "records to escalate"),
             ("amber" if open_n else "", open_n, "open or missing clock-outs")]
    st.markdown('<div class="tiles">' + "".join(f'<div class="tile {c}"><b>{n}</b><span>{esc(t)}</span></div>' for c, n, t in items) + "</div>", unsafe_allow_html=True)


def load_section(res):
    expanded = res.status == "no_shifts"
    with st.expander("Load or update data", expanded=expanded):
        st.caption(f"Showing: {st.session_state.source}. Upload any of " + ", ".join(FILE_NAMES[k] for k in FILE_NAMES if k != "weekly_summary")
                   + ". For each file, choose whether it overwrites the current file or is added to it. Your changes last for this visit only.")
        files = st.file_uploader("CSV files", type="csv", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
        ready = []
        for f in files:
            rep = check_file(f.name, f.getvalue())
            with st.container(border=True):
                kind = FILE_NAMES.get(rep.kind, "unknown file")
                st.markdown(f"**{esc(f.name)}** → {esc(kind)} · {rep.rows} rows")
                for e in rep.errors:
                    st.error(e)
                for w in rep.warnings:
                    st.warning(w)
                if rep.ok:
                    append = st.checkbox("Append to the current file instead of overwriting it", key=f"append_{f.name}_{f.size}")
                    ready.append((rep.kind, rep.data, "append" if append else "overwrite", f.name))
        if st.button("Apply", type="primary", disabled=not ready):
            st.session_state.bundle = apply_upload(st.session_state.bundle, [(k, d, m) for k, d, m, _ in ready])
            st.session_state.source = "your uploaded data"
            st.session_state.messages = [("success", f"Loaded {n} ({'appended' if m == 'append' else 'overwrote'} {FILE_NAMES[k]}).") for k, _, m, n in ready]
            st.session_state.uploader_key += 1
            st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Reset to the bundled data"):
            st.session_state.bundle, st.session_state.source, st.session_state.messages = load_bundled(), "the bundled example data", []
            st.rerun()
        if c2.button("Clear all data"):
            st.session_state.bundle, st.session_state.source, st.session_state.messages = {}, "no data", []
            st.rerun()
        for level, text in st.session_state.messages:
            getattr(st, level)(text)
        if res.predictions is not None:
            st.download_button("Download predictions.csv", predictions_csv(res), "predictions.csv", "text/csv")
        if res.note_classes is not None:
            st.download_button("Download note_classifications.csv", res.note_classes.to_csv(index=False), "note_classifications.csv", "text/csv")


GROUPS = [("Watch", "30 to 50%", "flag", False), ("Mid", "20 to 30%", "flag", False), ("Low", "0 to 20%", "low", True)]


def flagged_section(res):
    p = res.people
    index = reason_index(res)
    st.subheader("Who is likely to go over " + str(CAP) + " hours by Sunday" if res.status == "model" else "Who is over " + str(CAP) + " hours")
    if res.status == "model":
        st.caption("People at 50% risk or higher are listed here. The drop-downs below hold people at 30 to 50%, 20 to 30% and 0 to 20%. "
                   "predictions.csv includes everyone." + (" Press “Why the hours happened” on a box to see the supervisors' notes." if index is not None else ""))
    sites = res.sites.sort_values(["high_risk", "working"], ascending=False)
    options = ["All sites"] + list(sites["site"])
    by_label = dict(zip(sites["site"], sites["site_id"]))
    choice = st.selectbox("Site", options, label_visibility="collapsed") if len(options) > 1 else "All sites"
    if choice != "All sites":
        sid = by_label[choice]
        p = p[p["sites_worked"].apply(lambda lst: sid in lst) | p["primary_sites"].apply(lambda lst: sid in lst)]
    hot = p[p["band"] == "High"]
    if hot.empty:
        st.success("Nobody is " + ("at 50% risk or higher" if res.status == "model" else "over") + ("" if choice == "All sites" else " at this site") + ".")
    for row in hot.itertuples():
        person_box(row, res, index, "high", resolve=True)
    if res.status == "model":
        for band, title, css, compact in GROUPS:
            group = p[p["band"] == band].sort_values(["risk_score", "hours_so_far"], ascending=False)
            with st.expander(f"People at {title} risk ({len(group)})"):
                if group.empty:
                    st.caption(f"Nobody is at {title} risk" + ("" if choice == "All sites" else " at this site") + ".")
                elif compact:
                    st.markdown("".join(card(row, res, css, index, True) for row in group.itertuples()), unsafe_allow_html=True)
                else:
                    for row in group.itertuples():
                        person_box(row, res, index, css)


def sites_section(res):
    st.subheader("By site")
    if res.sites.empty:
        st.caption("No site information for this week.")
        return
    st.caption("A person counts at every site they worked this week.")
    table = res.sites.sort_values(["high_risk", "working"], ascending=False).rename(
        columns={"site": "Site", "working": "People working", "high_risk": "At 50%+ risk"})
    st.dataframe(table[["Site", "People working", "At 50%+ risk"]], hide_index=True, width="stretch")


def escalations_section(res):
    dups = res.duplicates if res.duplicates is not None else []
    over = res.overlaps_current if res.overlaps_current is not None else []
    if not len(dups) and not len(over) and (res.overlaps is None or res.overlaps.empty):
        return
    names = res.people.set_index("person_key")["name"]
    labels = res.site_labels
    st.subheader("Escalations")
    st.caption("These are indicators for review, not findings. Bank and tax numbers are compared behind the scenes and never shown.")
    total = len(dups) + len(over)
    if total and st.button(f"Escalate all ({total})", type="primary", key="escalate_all"):
        notify(f"resolving all {total} escalations")
    if len(dups):
        st.markdown("**People with more than one employee record**")
        for r in dups.itertuples():
            tag = '<span class="tag esc">Escalate</span>' if r.severity == "Escalate" else '<span class="tag rev">Review</span>'
            title = " / ".join(n for n in r.names if isinstance(n, str)) or " / ".join(r.employee_ids)
            st.markdown(f'<div class="card high" id="esc-{attr(r.person_key)}"><span class="name">{esc(title)}</span>{tag}'
                        f'<div class="sub">Records: {esc(" · ".join(r.employee_ids))}</div><div class="sub">Evidence: {esc(r.evidence)}</div></div>', unsafe_allow_html=True)
            if st.button("Resolve", key=f"resolve_dup_{r.person_key}"):
                notify("resolving a duplicate", title)
    if res.overlaps is not None and len(res.overlaps):
        st.markdown("**Shifts that overlap in time (potential: two places at once)**")
        st.caption(f"{len(res.overlaps)} overlapping pairs in all the data, {int((res.overlaps.severity == 'High').sum())} of them at sites in different provinces. "
                   f"{len(over)} this week" + (f" (showing {MAX_OVERLAPS})." if len(over) > MAX_OVERLAPS else "."))
        if not len(over):
            st.caption("None this week.")
        ordered = over.assign(rank=over["severity"].map({"High": 0, "Medium": 1})).sort_values(["rank", "overlap_hours"], ascending=[True, False]) if len(over) else over
        for i, r in enumerate(ordered.head(MAX_OVERLAPS).itertuples()):
            who = names.get(r.person_key, r.person_key)
            high = r.severity == "High"
            tag = f'<span class="tag {"esc" if high else "rev"}">{esc(r.severity)}</span>'
            where = " · different provinces" if r.different_province else ""
            st.markdown(
                f'<div class="card {"high" if high else "flag"}"><div class="top"><span class="name">{esc(who)}</span>{tag}</div>'
                f'<div class="sub">{r.overlap_hours:.2f} h overlap{esc(where)}</div>'
                f'<div class="legs"><div class="leg"><b>{esc(labels.get(r.site_a, r.site_a))}</b>{esc(span(r.start_a, r.end_a))}</div>'
                f'<div class="leg"><b>{esc(labels.get(r.site_b, r.site_b))}</b>{esc(span(r.start_b, r.end_b))}</div></div></div>', unsafe_allow_html=True)
            if st.button("Resolve", key=f"resolve_overlap_{i}_{r.shift_id_a}_{r.shift_id_b}"):
                notify("resolving a shift overlap", who)


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Overtime watch")
    try:
        init_state()
    except ValueError as exc:
        st.error(f"The bundled data could not be loaded: {exc}")
        return
    res = cached_run(content_hash(st.session_state.bundle), code_version(), st.session_state.bundle)

    if res.cutoff is not None:
        line = f"Data up to {res.cutoff:%a %d %b %Y} · week of {res.week_start:%a %d %b}"
        if res.status == "model":
            line += f" · predicting {join_days(res.predicted_days)}"
        st.markdown(f'<div class="status">{esc(line)} · {esc(st.session_state.source)}</div>', unsafe_allow_html=True)

    load_section(res)
    if res.status == "no_shifts":
        st.info(res.message)
        return
    if res.status == "not_enough_history":
        st.warning(res.message + " Showing hours worked so far this week instead.")
    elif res.status == "week_complete":
        st.info(res.message)
    tiles(res)
    flagged_section(res)
    sites_section(res)
    escalations_section(res)


main()
