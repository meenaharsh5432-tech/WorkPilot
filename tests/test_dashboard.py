"""Dashboard regressions: navigation must survive empty and unavailable APIs."""
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

DASHBOARD = Path(__file__).resolve().parents[1] / "frontend" / "dashboard.py"


@pytest.mark.parametrize("offline", [False, True])
def test_dashboard_pages_with_no_data(offline):
    def request(*args, **kwargs):
        if offline:
            raise requests.ConnectionError("offline")
        response = requests.Response()
        response.status_code = 200
        response._content = b"[]"
        return response

    with patch("requests.request", side_effect=request) as mocked:
        app = AppTest.from_file(str(DASHBOARD)).run()
        for page in ("Overview", "Approvals", "Task history", "Analytics"):
            mocked.reset_mock()
            app.sidebar.radio[0].set_value(page).run()
            assert not app.exception
            assert app.title[0].value == page
            assert not any("/steps" in call.args[1] for call in mocked.call_args_list)
        if offline:
            assert app.error
