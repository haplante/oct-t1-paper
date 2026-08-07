"""
Client for the OCT-T1 dashboard's stateless figure-generation API.

Fetches Plotly figures from the live dashboard so these notebooks mirror it
exactly (sizing, modebar, and Figure 2's click-to-exclude interaction).
"""

import requests
import plotly.graph_objects as go
import plotly.io as pio
import ipywidgets as widgets
from IPython.display import display, HTML

pio.renderers.default = "plotly_mimetype"

# Matches the dashboard's own default view (opticnerve_core.py DEFAULTS).
# These figures show only that default view, exactly like the dashboard's
# figure panels themselves show no controls (the dashboard's stat/model/
# sector controls live in its sidebar, not in the figure panels).
DEFAULT_STAT = 'R2m'
DEFAULT_MODE = 'avg'
DEFAULT_MAC = 'All_1_3_gcc'
DEFAULT_BAND = 'T1_mean_015'

# Mirrors oct_t1_dashboard_only/opticnerve_core.py FIG_SIZE and app.py's
# PNG_SCALE/GRAPH_CFG so these figures match the dashboard panels exactly
# (size + modebar). Duplicated rather than imported: separate repo.
FIG_SIZE = {"fig1": (555, 402), "fig2": (638, 285), "fig3": (638, 285)}
FIG_NAME = {"fig1": "fig01_T1_profile", "fig2": "fig02_regression", "fig3": "fig03_OCT_maps"}
PNG_SCALE = 600 / 96
MODEBAR_REMOVE = ["select2d", "lasso2d", "zoom2d", "pan2d", "zoomIn2d",
                  "zoomOut2d", "autoScale2d", "resetScale2d"]


def _graph_cfg(figid):
    w, h = FIG_SIZE[figid]
    return dict(scrollZoom=False, displaylogo=False, displayModeBar=False, responsive=False,
                modeBarButtonsToRemove=MODEBAR_REMOVE,
                toImageButtonOptions=dict(format="png", filename=FIG_NAME[figid],
                                          width=w, height=h, scale=PNG_SCALE))


# The dashboard rounds Fig 3's sector-stat chips (Plotly annotation bgcolor
# boxes) the same way: plain CSS, since Plotly has no border-radius option
# for them. Unlike the dashboard's static export, this widget is a live
# Plotly.js instance in the notebook's own browser page, so CSS applies
# directly — this is a one-time style injection, not per-figure.
display(HTML("<style>g.annotation rect{rx:6px;ry:6px}</style>"))


class OpticNerveClient:
    """Client for the dashboard's stateless figure-generation API."""

    def __init__(self, base_url="https://oct-t1-dashboard.onrender.com"):
        self.base_url = base_url
        self._fig2_excluded = set()

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

    # ========================================================================
    # VISUALIZATIONS METHODS
    # ========================================================================

    def to_figure_widget(self, response, figid):
        """Wrap a generate_plots/update_plots response in a FigureWidget,
        configured with the same modebar the dashboard uses for that panel."""
        fig = go.FigureWidget(response["figure"])
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

    def create_fig1_interface(self):
        """Build and display the Figure 1 panel (no controls, matches the dashboard)."""
        out = widgets.Output()
        self._render_into(out, 'fig1')
        display(out)
        return out

    def create_fig2_interface(self):
        """Build and display the Figure 2 panel (no controls, matches the
        dashboard). Clicking a point excludes it from the regression, exactly
        like the dashboard; click it again to put it back."""
        out = widgets.Output()

        def on_point_click(trace, points, state):
            if not points.point_inds:
                return
            subj, _tok, ghost = trace.customdata[points.point_inds[0]]
            if ghost:
                self._fig2_excluded = {t for t in self._fig2_excluded
                                        if t != subj and not t.startswith(f"{subj}.")}
            else:
                self._fig2_excluded.add(subj)
            render()

        def render():
            fig = self._render_into(out, 'fig2', stat=DEFAULT_STAT, mode=DEFAULT_MODE, mac=DEFAULT_MAC,
                                     exclude=",".join(sorted(self._fig2_excluded)))
            if fig is not None:
                for trace in fig.data:
                    if trace.customdata is not None:
                        trace.on_click(on_point_click)

        render()
        display(out)
        return out

    def create_fig3_interface(self):
        """Build and display the Figure 3 panel (no controls, matches the dashboard)."""
        out = widgets.Output()
        self._render_into(out, 'fig3', stat=DEFAULT_STAT, mode=DEFAULT_MODE, band=DEFAULT_BAND)
        display(out)
        return out
