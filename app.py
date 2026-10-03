"""Streamlit entry point for the ops room dashboard: who is likely to go over 55 hours by Sunday, and where."""
import html

import streamlit as st

from src.dataset import apply_upload, content_hash, load_bundled
from src.export import predictions_csv
from src.forecast import CAP
from src.pipeline import run
from src.report import ESCALATION_EMAIL, duplicate_line, mailto, overlap_line
from src.validate import FILE_NAMES, check_file

st.set_page_config(page_title="Overtime watch", layout="wide", initial_sidebar_state="collapsed")

HIGH_LEVELS = ["High", "Over"]      # only people at 50%+ risk (or already over the cap) are listed
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
.card .sub {font-size: .85rem; opacity: .8; margin-top: 2px;}
.card .stats {display: flex; flex-wrap: wrap; gap: 6px 22px; margin: 8px 0 4px;}
.card .stats div b {display: block; font-size: 1.15rem;}
.card .stats div span {font-size: .75rem; opacity: .7;}
.card .note {font-size: .9rem; margin-top: 4px;}
.tag {display: inline-block; font-size: .72rem; font-weight: 700; border-radius: 6px; padding: 1px 7px; margin-left: 6px; background: rgba(128,128,128,.25); text-decoration: none;}
.tag.esc {background: #dc2626; color: #fff !important;}
.tag.rev {background: #f59e0b; color: #1f2937 !important;}
a.tag.esc:hover {background: #b91c1c;}
.btn {display: inline-block; text-decoration: none !important; font-weight: 600; font-size: .85rem; border-radius: 8px; padding: 5px 14px; border: 1px solid #dc2626; color: #dc2626 !important; margin-top: 8px;}
.btn.solid {background: #dc2626; color: #fff !important;}
.legs {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin: 8px 0 2px;}
.leg {border: 1px solid rgba(128,128,128,.3); border-radius: 8px; padding: 6px 10px; font-size: .85rem;}
.leg b {display: block;}
.status {opacity: .8; margin: -0.4rem 0 0.6rem;}
.stButton button {padding: 0.15rem 0.9rem; min-height: 2rem;}
</style>
"""


def esc(x):
    return html.escape(str(x))


def attr(x):
    return html.escape(str(x), quote=True)


def join_days(days):
    short = [d[:3] for d in days]
    return short[0] if len(short) == 1 else ", ".join(short[:-1]) + " and " + short[-1]


@st.cache_data(show_spinner="Checking the data and running the model...")
def cached_run(data_hash, _bundle):
    return run(_bundle)


def init_state():
    if "bundle" not in st.session_state:
        st.session_state.bundle = load_bundled()
        st.session_state.source = "the bundled example data"
        st.session_state.messages = []
        st.session_state.uploader_key = 0


def site_text(site_ids, labels):
    return ", ".join(labels.get(s, s) for s in site_ids) if site_ids else "none yet"


def span(start, end):
    text = f"{start:%a %d %b %H:%M} to {end:%H:%M}"
    return text + (f" ({end:%a})" if end.date() != start.date() else "")


def card(p, res):
    labels = res.site_labels
    over = p.hours_so_far > CAP
    badge = f"Over by {p.hours_so_far - CAP:.1f} h" if over else (f"{p.risk_score:.0%} risk" if res.status == "model" else "Over")
    ids = " · ".join(p.employee_ids)
    flag = f' <a class="tag esc" href="#esc-{attr(p.person_key)}">2 records, see Escalations</a>' if len(p.employee_ids) > 1 else ""
    aka = f" (also recorded as {', '.join(p.also_known_as)})" if p.also_known_as else ""
    sub = esc(ids) + (f" · {esc(p.role)}" if p.role else "") + flag
    primary = f"Primary site: {esc(site_text(p.primary_sites, labels))}" if p.primary_sites else ""
    worked = f"Worked this week: {esc(site_text(p.sites_worked, labels))}"
    if over:
        note = f"Already over the {CAP}-hour cap by {p.hours_so_far - CAP:.1f} hours."
    elif res.status == "model":
        more = "less than one more usual shift" if p.shifts_left < 1 else f"about {p.shifts_left} more usual shift{'s' if p.shifts_left != 1 else ''}"
        note = f"{p.hours_left:.1f} hours left before {CAP}: {more} (usual shift {p.usual_shift_hours:.1f} h)."
    else:
        note = ""
    return (f'<div class="card high"><div class="top"><span class="name">{esc(p.name)}{esc(aka)}</span>'
            f'<span class="badge">{esc(badge)}</span></div><div class="sub">{sub}</div>'
            f'<div class="sub">{primary}{" · " if primary else ""}{worked}</div>'
            f'<div class="stats"><div><b>{p.hours_so_far:.1f}</b><span>hours so far</span></div>'
            f'<div><b>{int(p.shifts_so_far)}</b><span>shifts so far</span></div>'
            f'<div><b>{p.hours_left:.1f}</b><span>hours left to {CAP}</span></div></div>'
            f'<div class="note">{esc(note)}</div></div>')


def escalation_items(res):
    """Duplicate and overlap items for this week, each with its text and a ready-made report link."""
    names = res.people.set_index("person_key")["name"] if res.people is not None else {}
    labels = res.site_labels
    dup_items, over_items = [], []
    if res.duplicates is not None:
        for r in res.duplicates.itertuples():
            line = duplicate_line(r.names, r.employee_ids, r.evidence, r.severity)
            title = " / ".join(n for n in r.names if isinstance(n, str)) or " / ".join(r.employee_ids)
            dup_items.append((r, line, mailto(f"Possible duplicate employee record: {title}", [line])))
    if res.overlaps_current is not None and len(res.overlaps_current):
        cur = res.overlaps_current.copy()
        cur["rank"] = cur["severity"].map({"High": 0, "Medium": 1})
        for r in cur.sort_values(["rank", "overlap_hours"], ascending=[True, False]).itertuples():
            who = names.get(r.person_key, r.person_key)
            line = overlap_line(who, labels.get(r.site_a, r.site_a), r.start_a, r.end_a, labels.get(r.site_b, r.site_b),
                                r.start_b, r.end_b, r.overlap_hours, r.severity, r.different_province)
            over_items.append((r, who, line, mailto(f"Possible overlapping shifts: {who}", [line])))
    return dup_items, over_items


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


def flagged_section(res):
    p = res.people
    st.subheader("Who is likely to go over " + str(CAP) + " hours by Sunday" if res.status == "model" else "Who is over " + str(CAP) + " hours")
    if res.status == "model":
        st.caption("Only people at 50% risk or higher are shown. predictions.csv also includes lower-risk people.")
    sites = res.sites.sort_values(["high_risk", "working"], ascending=False)
    options = ["All sites"] + list(sites["site"])
    by_label = dict(zip(sites["site"], sites["site_id"]))
    choice = st.selectbox("Site", options, label_visibility="collapsed") if len(options) > 1 else "All sites"
    if choice != "All sites":
        sid = by_label[choice]
        p = p[p["sites_worked"].apply(lambda lst: sid in lst) | p["primary_sites"].apply(lambda lst: sid in lst)]
    hot = p[p["level"].isin(HIGH_LEVELS)]
    if hot.empty:
        st.success("Nobody is " + ("at 50% risk or higher" if res.status == "model" else "over") + ("" if choice == "All sites" else " at this site") + ".")
    for row in hot.itertuples():
        st.markdown(card(row, res), unsafe_allow_html=True)
        if st.button("Resolve", key=f"resolve_{row.person_key}"):
            st.toast("Resolve is not connected to anything yet.")


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
    dup_items, over_items = escalation_items(res)
    if not dup_items and not over_items and (res.overlaps is None or res.overlaps.empty):
        return
    st.subheader("Escalations")
    st.caption("These are indicators for review, not findings. Bank and tax numbers are compared behind the scenes and never shown.")
    if dup_items or over_items:
        lines = [x[1] for x in dup_items] + [x[2] for x in over_items]
        subject = f"Overtime watch escalations, week of {res.week_start:%d %b %Y}"
        st.markdown(f'<a class="btn solid" href="{attr(mailto(subject, lines))}">Escalate all ({len(lines)})</a>'
                    f'<div class="sub" style="margin-top:4px">Opens an email to {esc(ESCALATION_EMAIL)} with the details filled in. '
                    f'Nothing is sent until you press send in your email app.</div>', unsafe_allow_html=True)
    if dup_items:
        st.markdown("**People with more than one employee record**")
        for r, line, link in dup_items:
            tag = '<span class="tag esc">Escalate</span>' if r.severity == "Escalate" else '<span class="tag rev">Review</span>'
            title = " / ".join(n for n in r.names if isinstance(n, str)) or " / ".join(r.employee_ids)
            st.markdown(f'<div class="card high" id="esc-{attr(r.person_key)}"><span class="name">{esc(title)}</span>{tag}'
                        f'<div class="sub">Records: {esc(" · ".join(r.employee_ids))}</div><div class="sub">Evidence: {esc(r.evidence)}</div>'
                        f'<a class="btn" href="{attr(link)}">Report</a></div>', unsafe_allow_html=True)
    if res.overlaps is not None and len(res.overlaps):
        st.markdown("**Shifts that overlap in time (potential: two places at once)**")
        st.caption(f"{len(res.overlaps)} overlapping pairs in all the data, {int((res.overlaps.severity == 'High').sum())} of them at sites in different provinces. "
                   f"{len(over_items)} this week" + (f" (showing {MAX_OVERLAPS})." if len(over_items) > MAX_OVERLAPS else "."))
        labels = res.site_labels
        for r, who, line, link in over_items[:MAX_OVERLAPS]:
            high = r.severity == "High"
            tag = f'<span class="tag {"esc" if high else "rev"}">{esc(r.severity)}</span>'
            where = " · different provinces" if r.different_province else ""
            st.markdown(
                f'<div class="card {"high" if high else "flag"}"><div class="top"><span class="name">{esc(who)}</span>{tag}</div>'
                f'<div class="sub">{r.overlap_hours:.2f} h overlap{esc(where)}</div>'
                f'<div class="legs"><div class="leg"><b>{esc(labels.get(r.site_a, r.site_a))}</b>{esc(span(r.start_a, r.end_a))}</div>'
                f'<div class="leg"><b>{esc(labels.get(r.site_b, r.site_b))}</b>{esc(span(r.start_b, r.end_b))}</div></div>'
                f'<a class="btn" href="{attr(link)}">Report</a></div>', unsafe_allow_html=True)
        if not over_items:
            st.caption("None this week.")


def checks_section(res):
    with st.expander("Data checks and how the prediction works"):
        for level, text in st.session_state.messages:
            getattr(st, level)(text)
        for w in res.warnings:
            st.warning(w)
        q = res.quality
        if q:
            st.write(f"{q['shifts']:,} shifts read over {res.n_weeks} weeks · {q['overnight']:,} overnight · "
                     f"{q['excluded']:,} excluded (no usable clock times) · {q['over_12h_flagged']:,} longer than 12 hours (counted, flagged).")
        if res.open_shifts is not None and len(res.open_shifts):
            st.write("Open or missing clock-outs this week:")
            st.dataframe(res.open_shifts.fillna("missing").rename(columns={"shift_id": "Shift", "employee_id": "Employee", "site_id": "Site", "shift_date": "Date",
                                                                          "clock_in_time": "In", "clock_out_time": "Out"}), hide_index=True, width="stretch")
        m = res.model
        if res.status == "model":
            n_high = int(res.people["level"].isin(HIGH_LEVELS).sum())
            st.write(f"Method: {m['method']}. Hours are attributed to the day on which most of a shift was worked. "
                     f"predictions.csv flags {int(res.predictions['will_breach'].sum())} employee IDs at a score of {m['threshold']:.2f} or more, the cut-off that best balances "
                     f"catching breachers against false alarms on past weeks (catching breachers counts more). This page lists only the {n_high} people at 50% or more.")
            pooled = m["pooled_pr_auc"]
            st.write(f"On past weeks the model ranked breachers better than the simple projection in {pooled['folds_won']} of {pooled['folds']} test weeks "
                     f"(PR-AUC {pooled['model']:.2f} against {pooled['b3']:.2f}).")
            folds = m["folds"].assign(test_week=m["folds"]["test_week"].dt.strftime("%d %b"))
            st.dataframe(folds.rename(columns={"test_week": "Test week", "train_weeks": "Train weeks", "test_breaches": "Breachers",
                                               "pr_auc_model": "PR-AUC model", "pr_auc_b3": "PR-AUC simple projection"}).round(2), hide_index=True, width="stretch")


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Overtime watch")
    try:
        init_state()
    except ValueError as exc:
        st.error(f"The bundled data could not be loaded: {exc}")
        return
    res = cached_run(content_hash(st.session_state.bundle), st.session_state.bundle)

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
    checks_section(res)


main()
