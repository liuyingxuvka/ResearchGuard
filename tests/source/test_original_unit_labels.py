"""Exact source labels need no physical dictionary; conversion still does."""
from types import SimpleNamespace

import pytest

from researchguard.source.readings import CaptureScreen, Grid


def check_cell(tmp_path, quote, unit='widgets per session'):
    path = tmp_path / 'source.csv'
    path.write_text('period,value\nrowA,10\n')
    cap = {'unit': unit}
    grid = Grid('table', path, cap)
    anchor = SimpleNamespace(anchor_id='a', source_id='table', text=quote)
    screen = object.__new__(CaptureScreen)
    screen.lines, screen.colour, screen.errors, screen.warnings = [], {}, [], []
    screen.quoted, screen.anchors, screen.tables = {}, {'a': anchor}, {'table': grid}
    screen.check_table_anchor(anchor, grid, cap, 'anchor:a')
    return screen


@pytest.mark.parametrize('quote,colour', [
    ('rowA 10 widgets per session', 'G'),
    ('rowA 12 widgets per session', 'R'),
    ('rowA 10 credits per session', '.'),
    ('rowA 10 kg', '.'),
    ('rowA 10', 'G'),
])
def test_original_label_is_an_identity_not_a_conversion(tmp_path, quote, colour):
    screen = check_cell(tmp_path, quote)
    assert screen.lines[0][1] == colour, screen.lines
    if colour == 'G':
        assert 'no unit conversion' in screen.lines[0][2]


def test_raw_label_reader_does_not_register_a_unit():
    from researchguard.source.readings import unit_info
    assert unit_info('widgets per session') is None


def test_a_quote_cannot_supply_a_missing_original_unit(tmp_path):
    assert check_cell(tmp_path, 'rowA 10 kg', unit='').lines[0][1] == '.'


@pytest.mark.parametrize('value', [10, 20])
def test_unknown_quote_unit_is_grey_even_when_the_bare_number_differs(tmp_path, value):
    text = f'rowA {value} furlongs'
    assert check_cell(tmp_path, text, unit='kg').lines[0][1] == '.'


@pytest.mark.parametrize('label', ['q', 'qq'])
def test_unknown_short_unit_cannot_disappear_into_a_bare_number(tmp_path, label):
    assert check_cell(tmp_path, f'rowA 10 {label}', unit='kg').lines[0][1] == '.'


@pytest.mark.parametrize('phrase', ['in total', 'as recorded', 'of them'])
def test_ordinary_continuation_does_not_supply_a_unit(tmp_path, phrase):
    assert check_cell(tmp_path, f'rowA 10 {phrase}', unit='kg').lines[0][1] == 'G'


def test_unreadable_percentage_symbol_is_not_dropped_without_the_unit_owner(tmp_path, monkeypatch):
    import researchguard.source.readings as readings
    monkeypatch.setattr(readings, 'unit_info', lambda label: None)
    assert check_cell(tmp_path, 'rowA 10%', unit='widgets').lines[0][1] == '.'


@pytest.mark.parametrize('quoted, unit, expected', [('50%', '1', 'G'), ('25%', '1', 'R'),
                                                  ('500 g', 'kg', 'G'), ('250 g', 'kg', 'R')])
def test_conversion_scales_the_written_numeric_precision(tmp_path, quoted, unit, expected):
    path = tmp_path / 'fraction.csv'
    path.write_text('period,value\nrowA,0.5\n')
    cap = {'unit': unit}
    grid = Grid('table', path, cap)
    anchor = SimpleNamespace(anchor_id='a', source_id='table', text='rowA ' + quoted)
    screen = object.__new__(CaptureScreen)
    screen.lines, screen.colour, screen.errors, screen.warnings = [], {}, [], []
    screen.quoted, screen.anchors, screen.tables = {}, {'a': anchor}, {'table': grid}
    screen.check_table_anchor(anchor, grid, cap, 'anchor:a')
    assert screen.lines[0][1] == expected, screen.lines


def test_csv_unit_row_is_read_from_original_without_manual_capture_hint(tmp_path):
    path = tmp_path / 'mass.csv'
    path.write_text('period,value\nunit,kg\nrowA,0.5\n')
    grid = Grid('table', path, {})
    assert grid.columns[0].unit == 'kg' and grid.columns[0].unit_label == 'kg'
    anchor = SimpleNamespace(anchor_id='a', source_id='table', text='rowA 500 g')
    screen = object.__new__(CaptureScreen)
    screen.lines, screen.colour, screen.errors, screen.warnings = [], {}, [], []
    screen.quoted, screen.anchors, screen.tables = {}, {'a': anchor}, {'table': grid}
    screen.check_table_anchor(anchor, grid, {}, 'anchor:a')
    assert screen.lines[0][1] == 'G', screen.lines
