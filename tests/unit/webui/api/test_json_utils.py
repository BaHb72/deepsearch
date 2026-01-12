import pytest

from apps.api.api.utils.json_utils import sanitize_for_json


def test_sanitize_for_json_handles_dataframe_with_nan_and_inf():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")

    df = pd.DataFrame(dict(a=[1, np.nan, np.float32(3)], b=[np.inf, -np.inf, 0]))

    result = sanitize_for_json(df)

    assert result == [
        {"a": 1.0, "b": None},
        {"a": None, "b": None},
        {"a": 3.0, "b": 0.0},
    ]
