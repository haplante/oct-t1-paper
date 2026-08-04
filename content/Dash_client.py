import requests
import plotly.graph_objects as go
import ipywidgets as widgets
from IPython.display import display, HTML

STAT_OPTIONS = [('R²', 'R2m'), ('R', 'Rm')]
MODE_OPTIONS = [('Average + OLS', 'avg'), ('LME', 'lme')]
MAC_OPTIONS = ['All_1_3_gcc', 'All_3_6_gcc', 'All_field_gcc']
BAND_OPTIONS = [('0–15 mm', 'T1_mean_015'), ('0–5 mm', 'T1_mean_05'),
                ('5–10 mm', 'T1_mean_510'), ('10–15 mm', 'T1_mean_1015')]

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

    def to_figure_widget(self, response):
        """Wrap a generate_plots/update_plots response in a FigureWidget."""
        return go.FigureWidget(response["figure"])

    def _render_into(self, out, figid, **params):
        response = self.generate_plots(figid, **params)
        with out:
            out.clear_output(wait=True)
            if response:
                display(self.to_figure_widget(response))
            else:
                print("Could not load the figure.")

    def create_fig1_interface(self):
        """Build and display the Figure 1 interface (redraw button)."""
        out = widgets.Output()
        button = widgets.Button(description='Redraw')
        button.on_click(lambda _: self._render_into(out, 'fig1'))
        self._render_into(out, 'fig1')

        main_container = widgets.VBox([button, out])
        display(main_container)
        return main_container

    def create_fig2_interface(self):
        """Build and display the Figure 2 interface (statistic/model/sector controls)."""
        stat = widgets.Dropdown(options=STAT_OPTIONS, value='R2m', description='Statistic:')
        mode = widgets.Dropdown(options=MODE_OPTIONS, value='avg', description='Model:')
        mac = widgets.Dropdown(options=MAC_OPTIONS, value='All_1_3_gcc', description='Macula sector:')
        out = widgets.Output()

        def render(_=None):
            self._render_into(out, 'fig2', stat=stat.value, mode=mode.value, mac=mac.value)

        for control in (stat, mode, mac):
            control.observe(render, names='value')
        render()

        main_container = widgets.VBox([widgets.HBox([stat, mode, mac]), out])
        display(main_container)
        return main_container

    def create_fig3_interface(self):
        """Build and display the Figure 3 interface (statistic/model/band controls)."""
        stat = widgets.Dropdown(options=STAT_OPTIONS, value='R2m', description='Statistic:')
        mode = widgets.Dropdown(options=MODE_OPTIONS, value='avg', description='Model:')
        band = widgets.Dropdown(options=BAND_OPTIONS, value='T1_mean_015', description='T1 band:')
        out = widgets.Output()

        def render(_=None):
            self._render_into(out, 'fig3', stat=stat.value, mode=mode.value, band=band.value)

        for control in (stat, mode, band):
            control.observe(render, names='value')
        render()

        main_container = widgets.VBox([widgets.HBox([stat, mode, band]), out])
        display(main_container)
        return main_container
