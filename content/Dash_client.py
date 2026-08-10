"""
Client for the OCT-T1 dashboard's stateless figure-generation API.

Fetches Plotly figures from the live dashboard so these notebooks mirror it
exactly (sizing, modebar, and each figure's own side option panel).
"""

import requests
import plotly.graph_objects as go
import plotly.io as pio
import ipywidgets as widgets
from IPython.display import display, HTML

pio.renderers.default = "plotly_mimetype"

# Matches the dashboard's own default view (opticnerve_core.py DEFAULTS).
DEFAULT_STAT = 'R2m'
DEFAULT_MODE = 'avg'
DEFAULT_MAC = 'All_1_3_gcc'
DEFAULT_DISC = 'All_um_'
DEFAULT_BAND = 'T1_mean_015'

# Mirrors oct_t1_dashboard_only/opticnerve_core.py FIG_SIZE and app.py's
# PNG_SCALE/GRAPH_CFG so these figures match the dashboard panels exactly
# (size + modebar). Duplicated rather than imported: separate repo.
FIG_SIZE = {"fig1": (393, 285), "fig2": (638, 285), "fig3": (638, 285)}
FIG_NAME = {"fig1": "fig01_T1_profile", "fig2": "fig02_regression", "fig3": "fig03_OCT_maps"}
PNG_SCALE = 600 / 96
MODEBAR_REMOVE = ["select2d", "lasso2d", "zoom2d", "pan2d", "zoomIn2d",
                  "zoomOut2d", "autoScale2d", "resetScale2d"]

# Option lists for the side panels below. Mirrors opticnerve_core.py's
# MAC_METRICS/DISC_METRICS/T1_BANDS + NAMES/BAND_LABEL (duplicated for the
# same reason as FIG_SIZE: separate repo, no shared import).
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


def _graph_cfg(figid):
    w, h = FIG_SIZE[figid]
    return dict(scrollZoom=False, displaylogo=False, displayModeBar=False, responsive=False,
                modeBarButtonsToRemove=MODEBAR_REMOVE,
                toImageButtonOptions=dict(format="png", filename=FIG_NAME[figid],
                                          width=w, height=h, scale=PNG_SCALE))


# One-time style injection: the dashboard rounds Fig 3's sector-stat chips via
# plain CSS (Plotly has no border-radius option for annotation bgcolor boxes),
# and its sidebar look (background, label sizing) is likewise plain CSS. Both
# apply directly here since these are live Plotly.js/ipywidgets instances in
# the notebook's own browser page.
display(HTML("""<style>
g.annotation rect { rx:6px; ry:6px; }
.onp-panel { font-family:Arial,Helvetica,sans-serif; background:#fff; border:1px solid #ddd;
             border-radius:6px; padding:6px 8px; margin-left:0px; width:150px;
             box-sizing:border-box; overflow:hidden; gap:6px !important;
             --jp-widgets-inline-height: 18px; }
.onp-panel > * { margin:0 !important; }
.onp-panel .onp-title { font-size:12px; font-weight:bold; color:#333; }
.onp-panel .onp-lbl { font-size:10px; color:#555; }
.onp-panel select { font-size:10px !important; border-radius:4px; border:1px solid #ccc; color:#111;
             height:18px !important; padding:0 2px !important; }
.onp-panel .widget-dropdown { width:100% !important; height:18px !important; }
.onp-subjlist { display:grid; grid-template-columns:repeat(2, auto); grid-gap:0px 8px; margin-bottom:0; }
.onp-subjlist .widget-checkbox { width:auto; height:14px; min-height:14px; margin:0; }
.onp-subjlist .widget-checkbox input[type=checkbox] { width:10px; height:10px; margin:0 3px 0 0; }
.onp-subjlist .widget-checkbox label { font-size:10px; line-height:14px; color:#1a5fb4; width:auto; }
</style>"""))


class OpticNerveClient:
    """Client for the dashboard's stateless figure-generation API."""

    def __init__(self, base_url="https://oct-t1-dashboard.onrender.com"):
        self.base_url = base_url
        self._subjects = None

    # ========================================================================
    # API Query Methods
    # ========================================================================

    def _post(self, figid, params):
        payload = {"figid": figid, **params}
        try:
            resp = requests.post(f"{self.base_url}/api/generate_plots", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"❌ Error generating plots: {e}")
            return None

    def generate_plots(self, figid, **params):
        """Generate a figure via the API."""
        return self._post(figid, params)

    def update_plots(self, figid, **params):
        """Update the figure with new parameters."""
        return self._post(figid, params)

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
    # VISUALIZATIONS METHODS
    # ========================================================================

    def to_figure_widget(self, response, figid):
        """Wrap a generate_plots/update_plots response in a FigureWidget,
        configured with the same modebar the dashboard uses for that panel.
        Resized to FIG_SIZE so that dict is the one place to change a
        figure's on-page size (the dashboard always sends its own native size)."""
        fig = go.FigureWidget(response["figure"])
        w, h = FIG_SIZE[figid]
        fig.update_layout(width=w, height=h)
        fig._config = _graph_cfg(figid)
        return fig

    def _render_into(self, out, figid, **params):
        """Fetch + draw figid into out. Returns the new FigureWidget, or None."""
        response = self.generate_plots(figid, **params)
        with out:
            out.clear_output(wait=True)
            if not response:
                print("Could not load the figure.")
                return None
            fig = self.to_figure_widget(response, figid)
            display(fig)
            return fig

    def _panel(self, title, rows, figid):
        """A side option panel styled like the dashboard's sidebar, sized to
        match the figure's own height so the two sit flush with no scrollbar.
        `rows` is a list of (label, widget) pairs."""
        tight = widgets.Layout(height="14px", margin="0", padding="0")
        children = [widgets.HTML(f"<div class='onp-title'>{title}</div>", layout=tight)]
        for label, w in rows:
            children.append(widgets.HTML(f"<div class='onp-lbl'>{label}</div>", layout=tight))
            children.append(w)
        height = FIG_SIZE[figid][1]
        box = widgets.VBox(children, layout=widgets.Layout(
            align_items="stretch", height=f"{height}px", overflow="hidden"))
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

    def create_fig1_interface(self):
        """Figure 1 panel: subject exclusion only."""
        out = widgets.Output()
        subj_grid, subj_boxes = self._subject_checklist()

        def render(*_):
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            self._render_into(out, 'fig1', exclude=exclude)

        self._observe_all(subj_boxes, render)
        render()
        display(widgets.HBox([out, self._panel("Figure 1 options", [("Subjects", subj_grid)], "fig1")]))
        return out

    def create_fig2_interface(self):
        """Figure 2 panel: subject exclusion, macula sector, disc sector, T1
        sector. Clicking a point toggles that subject's checkbox in the panel
        (and vice versa) — the checkbox is the single source of truth for
        who's excluded, exactly like the dashboard's sidebar checklist."""
        out = widgets.Output()
        subj_grid, subj_boxes = self._subject_checklist()
        mac_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in MAC_OPTIONS], value=DEFAULT_MAC,
                                  layout=widgets.Layout(width="100%"))
        disc_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in DISC_OPTIONS], value=DEFAULT_DISC,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))
        band_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in BAND_OPTIONS], value=DEFAULT_BAND,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))

        def on_point_click(trace, points, state):
            if not points.point_inds:
                return
            subj, _tok, ghost = trace.customdata[points.point_inds[0]]
            subj_boxes[subj].value = bool(ghost)   # ghost point clicked -> re-include; live point clicked -> exclude

        def render(*_):
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            fig = self._render_into(out, 'fig2', stat=DEFAULT_STAT, mode=DEFAULT_MODE,
                                     mac=mac_w.value, disc=disc_w.value, band=band_w.value, exclude=exclude)
            if fig is not None:
                for trace in fig.data:
                    if trace.customdata is not None:
                        trace.on_click(on_point_click)

        self._observe_all(subj_boxes, render)
        mac_w.observe(render, names='value')
        disc_w.observe(render, names='value')
        band_w.observe(render, names='value')
        render()
        panel = self._panel("Figure 2 options", [("Subjects", subj_grid), ("Macula sector", mac_w),
                                                  ("Disc sector", disc_w), ("T1 sector", band_w)], "fig2")
        display(widgets.HBox([out, panel]))
        return out

    def create_fig3_interface(self):
        """Figure 3 panel: subject exclusion and T1 sector. (No OCT-sector
        control here: unlike Figure 2, both maps' sectors are drawn together
        in fixed layout, so there's nothing for it to switch.)"""
        out = widgets.Output()
        subj_grid, subj_boxes = self._subject_checklist()
        band_w = widgets.Dropdown(options=[(lbl, val) for val, lbl in BAND_OPTIONS], value=DEFAULT_BAND,
                                   layout=widgets.Layout(width="100%", height="18px", margin="0", padding="0"))

        def render(*_):
            exclude = ",".join(sorted(s for s, b in subj_boxes.items() if not b.value))
            self._render_into(out, 'fig3', stat=DEFAULT_STAT, mode=DEFAULT_MODE,
                               band=band_w.value, exclude=exclude)

        self._observe_all(subj_boxes, render)
        band_w.observe(render, names='value')
        render()
        panel = self._panel("Figure 3 options", [("Subjects", subj_grid), ("T1 sector", band_w)], "fig3")
        display(widgets.HBox([out, panel]))
        return out
