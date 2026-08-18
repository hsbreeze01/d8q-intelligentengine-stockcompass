from buy.cache import DicStockFactory


def test_load_handles_empty_table_without_keyerror():
    f = DicStockFactory()
    f.load()
    assert f.data.empty is True
    assert f.isExist('600000') is False
