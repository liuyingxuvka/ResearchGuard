"""Preserve the precision the source actually supplied through the documented route."""
import json
import shutil

import pytest

from research_tree_support import EVERGIVEN
from researchguard.cli import main
from researchguard.logic.provenance import ProvenanceError, ProvenanceRecord


@pytest.mark.parametrize('date', ['2021', '2021-04', '2021-04-30'])
def test_provenance_keeps_partial_calendar_precision(date):
    record = ProvenanceRecord(origin_kind='external_source', source_id='s', quote='Original words', source_date=date)
    assert record.source_date == date


@pytest.mark.parametrize('date', ['0000', '2021-00', '2021-13', '2021-02-29', '2021-4', 'April 2021'])
def test_invalid_partial_dates_are_still_refused(date):
    with pytest.raises(ProvenanceError, match='ISO-8601'):
        ProvenanceRecord(origin_kind='external_source', source_id='s', quote='Original words', source_date=date)


def test_documented_month_source_can_be_synced_and_evaluated(tmp_path, capsys):
    candidate = tmp_path / 'evergiven-copy'
    shutil.copytree(EVERGIVEN, candidate)
    source = candidate / 'source.yaml'
    quote = 'The Suez blockage alone doubled Asia-Europe spot rates in April 2021.'
    assert main(['source', 'add-anchor', str(source), '--source-id', 'src-lloyds', '--anchor-id', 'anc-lloyds',
                 '--quote', quote, '--locator', "Lloyd's List, April 2021", '--title', "Lloyd's List",
                 '--date', '2021-04', '--output', str(source)]) == 0
    capsys.readouterr()
    assert main(['sync', str(candidate)]) == 0
    capsys.readouterr()
    assert main(['status', str(candidate), '--json']) == 0
    status = json.loads(capsys.readouterr().out)
    assert not any(error.startswith('model_invalid:logic') for error in status['errors'])
    assert any(row['id'] == 'src-lloyds' and '2021-04' in row['identity'] for row in status['sources'])
    assert status['models']['logic']['status'] == 'ok'
