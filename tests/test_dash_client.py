import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "content"))

from Dash_client import OpticNerveClient


def _fake_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


@patch("Dash_client.requests.post")
def test_generate_plots_posts_figid_and_params(mock_post):
    mock_post.return_value = _fake_response({"figid": "fig2", "figure": {"data": [], "layout": {}}})
    client = OpticNerveClient(base_url="http://example.test")
    result = client.generate_plots("fig2", stat="Rm", mode="lme")
    mock_post.assert_called_once_with(
        "http://example.test/api/generate_plots",
        json={"figid": "fig2", "stat": "Rm", "mode": "lme"},
        timeout=30,
    )
    assert result["figid"] == "fig2"


@patch("Dash_client.requests.post")
def test_update_plots_is_the_same_call_as_generate_plots(mock_post):
    mock_post.return_value = _fake_response({"figid": "fig3", "figure": {"data": [], "layout": {}}})
    client = OpticNerveClient(base_url="http://example.test")
    client.update_plots("fig3", band="T1_mean_05")
    mock_post.assert_called_once_with(
        "http://example.test/api/generate_plots",
        json={"figid": "fig3", "band": "T1_mean_05"},
        timeout=30,
    )


def test_to_figure_widget_wraps_the_figure_key():
    client = OpticNerveClient()
    widget = client.to_figure_widget({"figure": {"data": [], "layout": {"title": "t"}}})
    assert widget.layout.title.text == "t"


@patch("Dash_client.requests.post")
def test_generate_plots_returns_none_and_prints_on_http_error(mock_post, capsys):
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    mock_post.return_value = resp
    client = OpticNerveClient(base_url="http://example.test")
    result = client.generate_plots("fig1")
    assert result is None
    assert "Error" in capsys.readouterr().out


@patch("Dash_client.requests.post")
def test_generate_plots_returns_none_and_prints_on_connection_error(mock_post, capsys):
    mock_post.side_effect = requests.ConnectionError("refused")
    client = OpticNerveClient(base_url="http://example.test")
    result = client.generate_plots("fig1")
    assert result is None
    assert "Error" in capsys.readouterr().out
