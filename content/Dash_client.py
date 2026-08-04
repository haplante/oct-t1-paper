import requests
import plotly.graph_objects as go


class OpticNerveClient:
    def __init__(self, base_url="http://127.0.0.1:8050"):
        self.base_url = base_url

    def _post(self, figid, params):
        payload = {"figid": figid, **params}
        resp = requests.post(f"{self.base_url}/api/generate_plots", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def generate_plots(self, figid, **params):
        return self._post(figid, params)

    def update_plots(self, figid, **params):
        return self._post(figid, params)

    def to_figure_widget(self, response):
        return go.FigureWidget(response["figure"])
