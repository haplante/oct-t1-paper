import requests
import plotly.graph_objects as go


class OpticNerveClient:
    """Client for the dashboard's stateless figure-generation API."""

    def __init__(self, base_url="http://127.0.0.1:8050"):
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
