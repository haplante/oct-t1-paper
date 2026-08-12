"""
Client for the OCT-T1 dashboard's standalone figure pages.

Each figure is embedded as an <iframe> of the dashboard's own /figure/<figid>
page (app.py serves these specifically for article embedding). The page runs
the dashboard's real plotly.js in its own document, so it renders identically
to the dashboard by construction — none of Thebe's plotly/ipywidgets rendering
machinery is involved in drawing the figure. The ipywidgets side panel drives
the figure by rewriting the iframe's query string; the page reads its params
from the URL and re-renders itself.
"""

import itertools
import requests
import ipywidgets as widgets
from IPython.display import display, Javascript
from urllib.parse import urlencode
from html import escape as _esc
import json as _json

# Matches the dashboard's own default view (opticnerve_core.py DEFAULTS).
DEFAULT_MAC = 'All_1_3_gcc'
DEFAULT_DISC = 'All_um_'
DEFAULT_BAND = 'T1_mean_015'

# On-page iframe size per figure. The /figure/<figid> page scales its native
# canvas to fit whatever box it gets (object-fit:contain style), so this only
# chooses display size — the render itself is always the dashboard's own.
# Fixed px on purpose: percentage widths resolve circularly through Thebe's
# widget wrappers and overflow the grid column. The MyST article column is a
# fixed 765px, so every figure is 765 - panel(150+6 margin) - 0px gap - 2px
# slack = 607: figure + panel spans the column exactly, the 2px keeps rounding
# from raising a horizontal scrollbar. Change the gap in _show and this must
# change with it.
# fig2 is shorter than the others on purpose: its left subplot's y-axis title
# draws ~10px outside the canvas (Plotly quirk, HANDOFF item 4). A shorter box
# makes the page's contain-scale height-limited, centering the canvas with side
# margins that give the overhanging title room instead of clipping it.
FIG_SIZE = {"fig1": (607, 441), "fig2": (607, 256), "fig3": (607, 285)}

# Option lists for the side panels below. Mirrors opticnerve_core.py's
# MAC_METRICS/DISC_METRICS/T1_BANDS + NAMES/BAND_LABEL (duplicated:
# separate repo, no shared import).
MAC_OPTIONS = [
    ("All_1_3_gcc", "GCC All (1–3 mm)"), ("All_3_6_gcc", "GCC All (3–6 mm)"),
    ("All_field_gcc", "GCC All Field"), ("Center_1_gcc", "GCC Center (1 mm)"),
    ("N_1_3_gcc", "GCC N (1–3 mm)"), ("S_1_3_gcc", "GCC S (1–3 mm)"),
    ("T_1_3_gcc", "GCC T (1–3 mm)"), ("I_1_3_gcc", "GCC I (1–3 mm)"),
    ("N_3_6_gcc", "GCC N (3–6 mm)"), ("S_3_6_gcc", "GCC S (3–6 mm)"),
    ("T_3_6_gcc", "GCC T (3–6 mm)"), ("I_3_6_gcc", "GCC I (3–6 mm)"),
]
DISC_OPTIONS = [
    ("All_um_", "RNFL Overall"), ("TS_um_", "RNFL TS"), ("ST_um_", "RNFL ST"),
    ("SN_um_", "RNFL SN"), ("NS_um_", "RNFL NS"), ("NI_um_", "RNFL NI"),
    ("IN_um_", "RNFL IN"), ("IT_um_", "RNFL IT"), ("TI_um_", "RNFL TI"),
]
BAND_OPTIONS = [
    ("T1_mean_015", "0–15 mm"), ("T1_mean_05", "0–5 mm"),
    ("T1_mean_510", "5–10 mm"), ("T1_mean_1015", "10–15 mm"),
]

# Side-panel styling (background, label sizing) — the figures themselves are
# iframes and need no CSS from here.
_INJECTED_CSS = """
.onp-fig-grid.onp-fig-grid.onp-fig-grid { display:grid !important; align-items:stretch !important;
             width:fit-content !important; margin-left:auto !important; margin-right:auto !important;
             overflow:visible !important; }
/* Lumino sporadically inflates the frame's inner .widget-html-content past the
   frame's fixed FIG_SIZE box (317px around a 285px iframe), which raised a
   scrollbar on the grid. The iframe is exactly FIG_SIZE, so clipping the frame
   to its own box loses nothing and neutralizes whatever the wrapper does.
   align-self:center: the row is as tall as the taller of figure and panel, so
   when the panel wins the figure sits centered with even white bands above and
   below instead of being stuck to the top. */
   margin:0: ipywidgets' own `.jupyter-widgets { margin:2px }` shrinks the frame's
   border-box to 4px narrower than the iframe it holds, and the overflow:hidden
   above then slices those 4px off the figure's right edge. */
.onp-frame { overflow:hidden !important; align-self:center !important; margin:0 !important; }
.onp-frame iframe { border:0; display:block; border-radius:6px; }
/* The output area's height exactly equals the row height, so browser-zoom
   rounding can tip it into a phantom scrollbar. Class tripled because Thebe's
   own rule beats a plain !important (same fight as .onp-fig-grid below). */
.jp-OutputArea-output.jp-OutputArea-output.jp-OutputArea-output:has(.onp-fig-grid) {
             overflow:visible !important; }
.onp-sync { display:none !important; }
/* No height here and none set inline (see _panel): the panel's content height is
   its own contribution to the grid row, so the row ends up as tall as whichever
   of figure/panel is taller and align-items:stretch grows the shorter one to
   match. Never a percentage height -- that feeds back into the row's own height
   and, when the first layout pass runs before this CSS lands on Binder, locks
   the row at ~500px next to 285px figures. */
.onp-panel { font-family:Arial,Helvetica,sans-serif; background:#fff; border:1px solid #ddd;
             border-radius:6px; padding:6px 8px; margin:0 6px 0 0 !important; width:150px;
             box-sizing:border-box; overflow:hidden; gap:6px !important;
             --jp-widgets-inline-height: 18px; }
.onp-panel > * { margin:0 !important; }
/* Styled like the dashboard sidebar's .btnrow buttons; margin-top:auto pins it
   to the bottom of the panel with whatever breathing room is left. */
.onp-panel .onp-reset { margin-top:auto !important; width:100%; height:20px;
             background:#fff; color:#333; border:1px solid #bbb; border-radius:4px;
             font-size:11px; cursor:pointer; }
.onp-panel .onp-reset:hover { background:#e6e6ea; }
.onp-panel .onp-title { font-size:12px; font-weight:bold; color:#333; }
.onp-panel .onp-lbl { font-size:10px; color:#555; }
.onp-panel select { font-size:10px !important; border-radius:4px; border:1px solid #ccc; color:#111;
             height:18px !important; padding:0 2px !important; background:#fff !important; }
.onp-panel .widget-dropdown { width:100% !important; height:18px !important; background:#fff !important; }
.onp-subjlist { display:grid; grid-template-columns:repeat(2, auto); grid-gap:0px 8px; margin-bottom:0; }
.onp-subjlist .widget-checkbox { width:auto; height:14px; min-height:14px; margin:0; }
.onp-subjlist .widget-checkbox input[type=checkbox] { width:10px; height:10px; margin:0 3px 0 0; }
.onp-subjlist .widget-checkbox label { font-size:10px; line-height:14px; color:#1a5fb4; width:auto; }
"""
# display(HTML(...)) with a <style> tag gets its <style> stripped by Jupyter's
# HTML sanitizer in the Thebe/MyST embed; a script-created <style> element
# sidesteps that (script output isn't sanitized the same way).
display(Javascript(f"""
(function() {{
    if (document.getElementById('onp-injected-style')) return;
    var s = document.createElement('style');
    s.id = 'onp-injected-style';
    s.textContent = {_json.dumps(_INJECTED_CSS)};
    document.head.appendChild(s);
}})();
"""))

# Two-way bridge between the option panels (ipywidgets, this page) and the
# figure iframes (the dashboard's /figure pages, cross-origin — postMessage is
# the only channel that crosses that boundary):
#   panel -> figure: render() swaps a hidden .onp-push span; this observer
#     forwards its query into the grid's iframe, so the page re-renders in
#     place instead of the iframe reloading.
#   figure -> panel: the figure page posts {opticnerve, params} after every
#     in-figure click; clicking the matching subject checkboxes notifies the
#     kernel widgets, keeping the checkbox the single source of truth. The
#     resulting kernel render pushes params the figure already has, which its
#     receive() treats as a no-op — so this cannot loop.
# Both directions are point-to-point: a figure only ever drives the panel in its
# own grid, and vice versa. The three figures are independent views, each with
# its own cohort and its own Reset.
display(Javascript("""
(function() {
    if (window.__onpBridge) return;
    window.__onpBridge = true;

    new MutationObserver(function () {
        document.querySelectorAll('.onp-push').forEach(function (n) {
            if (n._sent) return; n._sent = true;
            var grid = n.closest('.onp-fig-grid');
            var f = grid && grid.querySelector('iframe');
            if (!f || !f.contentWindow) return;
            var params = {};
            new URLSearchParams(n.dataset.query || '').forEach(function (v, k) { params[k] = v; });
            f.contentWindow.postMessage({opticnerve: true, params: params}, '*');
        });
    }).observe(document.body, {childList: true, subtree: true});

    window.addEventListener('message', function (e) {
        var d = e.data || {};
        if (!d.opticnerve || !d.params || typeof d.params.exclude !== 'string') return;
        var excl = d.params.exclude.split(',').filter(Boolean);
        // Only the panel belonging to the figure that sent this: each figure now
        // holds its own cohort (the /figure pages no longer share a
        // BroadcastChannel -- see app.py's ?sync=1). Matching on e.source rather
        // than d.figid means a message from anything that is not one of our
        // figure iframes -- the dashboard embed included -- reaches no panel.
        var grid = null;
        document.querySelectorAll('.onp-fig-grid').forEach(function (g) {
            var f = g.querySelector('iframe');
            if (f && f.contentWindow === e.source) grid = g;
        });
        var list = grid && grid.querySelector('.onp-subjlist');
        if (!list) return;
        list.querySelectorAll('.widget-checkbox').forEach(function (cb) {
            var input = cb.querySelector('input');
            // ipywidgets prefixes the label with a zero-width space, which
            // trim() does not remove -- strip zero-width chars explicitly.
            var subj = cb.textContent.replace(/[\\u200b-\\u200d\\ufeff]/g, '').trim();
            var want = excl.indexOf(subj) === -1;
            if (input && input.checked !== want) input.click();
        });
    });
})();
"""))


class OpticNerveClient:
    """Embeds the dashboard's standalone /figure/<figid> pages, driven by an
    ipywidgets option panel styled like the dashboard's sidebar."""

    def __init__(self, base_url="https://oct-t1-dashboard.onrender.com"):
        self.base_url = base_url
        self._subjects = None
        self._push_n = itertools.count()

    # ========================================================================
    # API
    # ========================================================================

    def generate_plots(self, figid, **params):
        """Fetch a figure's JSON via the API (used only for subject discovery;
        the figures themselves render in their own iframe)."""
        try:
            resp = requests.post(f"{self.base_url}/api/generate_plots",
                                 json={"figid": figid, **params}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"❌ Error generating plots: {e}")
            return None

    def _all_subjects(self):
        """Subject list, read off Figure 2's per-point customdata (subject IDs
        live in the dashboard's data, not in this repo, so they're discovered
        from a live response instead of being hardcoded here)."""
        if self._subjects is None:
            resp = self.generate_plots('fig2', mac=DEFAULT_MAC, disc=DEFAULT_DISC, band=DEFAULT_BAND)
            subs = set()
            for trace in (resp or {}).get("figure", {}).get("data", []):
                for row in (trace.get("customdata") or []):
                    if row:
                        subs.add(row[0])
            self._subjects = sorted(subs)
        return self._subjects

    # ========================================================================
    # Iframe + panel plumbing
    # ========================================================================

    @staticmethod
    def _query(params):
        q = urlencode({k: v for k, v in params.items() if v})
        return f"?{q}" if q else ""

    def _frame(self, figid, **params):
        """An HTML widget holding the figure iframe (loaded once), plus a hidden
        companion widget (`_sync`) that later renders write new params into —
        the injected bridge above forwards them via postMessage, so the figure
        updates in place instead of the iframe reloading."""
        w = widgets.HTML()
        w.add_class("onp-frame")
        width, height = FIG_SIZE[figid]
        # Explicit height: without it the widget's natural height is at the
        # mercy of Thebe/Lumino layout feedback, which inflated the whole grid
        # row (~500px rows around 285px figures on Binder).
        w.layout = widgets.Layout(height=f"{height}px")
        # width via style (100% of the grid column, capped at native size) so the
        # row can shrink into a narrow article column instead of overflowing —
        # the page scales its canvas to fit whatever box it gets.
        w.value = (f'<iframe src="{self.base_url}/figure/{figid}{self._query(params)}" '
                   f'title="OCT-T1 {figid}" '
                   f'style="width:{width}px;height:{height}px"></iframe>')
        w._sync = widgets.HTML()
        w._sync.add_class("onp-sync")
        return w

    def _retarget(self, out, figid, **params):
        # data-n makes every push unique: an unchanged value would not reach the
        # frontend, and the figure may hold in-figure click state the panel's
        # (identical) params still need to override — e.g. Reset after clicks.
        out._sync.value = (f'<span class="onp-push" data-n="{next(self._push_n)}" '
                           f'data-query="{_esc(self._query(params)[1:])}"></span>')

    def _panel(self, title, rows, on_reset=None):
        """A side option panel styled like the dashboard's sidebar (the grid
        row makes it and the figure the same height, see `_show`).
        `rows` is a list of (label, widget) pairs; `on_reset` adds a
        reset-to-defaults button pinned at the bottom."""
        tight = widgets.Layout(height="14px", margin="0", padding="0")
        children = [widgets.HTML(f"<div class='onp-title'>{title}</div>", layout=tight)]
        for label, w in rows:
            children.append(widgets.HTML(f"<div class='onp-lbl'>{label}</div>", layout=tight))
            children.append(w)
        if on_reset is not None:
            btn = widgets.Button(description="↺ Reset all")
            btn.add_class("onp-reset")
            btn.on_click(on_reset)
            children.append(btn)
        # No explicit height: the grid stretches the panel to the figure's height
        # when it fits, and when its content is taller the row grows to the panel
        # instead of clipping it (the figure then centers itself, see the CSS).
        box = widgets.VBox(children, layout=widgets.Layout(
            align_items="stretch", overflow="hidden"))
        box.add_class("onp-panel")
        return box

    def _subject_checklist(self):
        """A checkbox-per-subject grid (2 columns), checked = included. Looks
        like the dashboard's subject checklist without its per-eye columns."""
        subs = self._all_subjects()
        boxes = {s: widgets.Checkbox(value=True, description=s, indent=False,
                                      layout=widgets.Layout(width="max-content", height="14px", margin="0"))
                 for s in subs}
        grid = widgets.GridBox(list(boxes.values()))
        grid.add_class("onp-subjlist")
        return grid, boxes

    def _observe_all(self, boxes, handler):
        for b in boxes.values():
            b.observe(handler, names='value')

    @staticmethod
    def _resetter(render, subj_boxes, defaults):
        """A reset handler + the guard `render` must check: resetting flips many
        widget values at once, and without the guard each flip would fire its
        observer and refetch the figure N times. `defaults` maps widget -> value."""
        muted = [False]

        def reset(_btn=None):
            muted[0] = True
            try:
                for b in subj_boxes.values():
                    b.value = True
                for w, v in defaults.items():
                    w.value = v
            finally:
                muted[0] = False
            render()

        return muted, reset

    def _show(self, figid, frame, panel):
        # Fixed figure column + auto panel column: the two add up to the article
        # column's width (see FIG_SIZE), so the row spans the page without
        # overflowing it. No gap: the panel sits flush against the figure.
        box = widgets.GridBox([frame, panel, frame._sync], layout=widgets.Layout(
            grid_template_columns=f"{FIG_SIZE[figid][0]}px auto",
            grid_gap="0px"))
        box.add_class("onp-fig-grid")
        display(box)
        return frame

    # ========================================================================
    # Figure interfaces
    # ========================================================================

    def create_fig1_interface(self):
        """Figure 1 panel: subject exclusion only."""
        subj_grid, subj_boxes = self._subject_checklist()
        frame = self._frame('fig1')

        def render(*_):
            if muted[0]:
                return
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            self._retarget(frame, 'fig1', exclude=exclude)

        muted, reset = self._resetter(render, subj_boxes, {})
        self._observe_all(subj_boxes, render)
        panel = self._panel("Figure 1 options", [("Subjects", subj_grid)], on_reset=reset)
        return self._show('fig1', frame, panel)

    def create_fig2_interface(self):
        """Figure 2 panel: subject exclusion, macula sector, disc sector, T1
        sector. Points and band chips are also clickable inside the figure
        itself (the page's own handlers, same as the dashboard)."""
        subj_grid, subj_boxes = self._subject_checklist()
        mac_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in MAC_OPTIONS], value=DEFAULT_MAC,
                                  layout=widgets.Layout(width="100%"))
        disc_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in DISC_OPTIONS], value=DEFAULT_DISC,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))
        band_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in BAND_OPTIONS], value=DEFAULT_BAND,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))
        frame = self._frame('fig2', mac=DEFAULT_MAC, disc=DEFAULT_DISC, band=DEFAULT_BAND)

        def render(*_):
            if muted[0]:
                return
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            self._retarget(frame, 'fig2', mac=mac_w.value, disc=disc_w.value,
                           band=band_w.value, exclude=exclude)

        muted, reset = self._resetter(render, subj_boxes, {
            mac_w: DEFAULT_MAC, disc_w: DEFAULT_DISC, band_w: DEFAULT_BAND})
        self._observe_all(subj_boxes, render)
        mac_w.observe(render, names='value')
        disc_w.observe(render, names='value')
        band_w.observe(render, names='value')
        panel = self._panel("Figure 2 options", [("Subjects", subj_grid), ("Macula sector", mac_w),
                                                  ("Disc sector", disc_w), ("T1 sector", band_w)],
                            on_reset=reset)
        return self._show('fig2', frame, panel)

    def create_fig3_interface(self):
        """Figure 3 panel: subject exclusion and T1 sector. (No OCT-sector
        control here: unlike Figure 2, both maps' sectors are drawn together
        in fixed layout, so there's nothing for it to switch.)"""
        subj_grid, subj_boxes = self._subject_checklist()
        band_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in BAND_OPTIONS], value=DEFAULT_BAND,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))
        frame = self._frame('fig3', band=DEFAULT_BAND)

        def render(*_):
            if muted[0]:
                return
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            self._retarget(frame, 'fig3', band=band_w.value, exclude=exclude)

        muted, reset = self._resetter(render, subj_boxes, {band_w: DEFAULT_BAND})
        self._observe_all(subj_boxes, render)
        band_w.observe(render, names='value')
        panel = self._panel("Figure 3 options", [("Subjects", subj_grid), ("T1 sector", band_w)],
                            on_reset=reset)
        return self._show('fig3', frame, panel)
