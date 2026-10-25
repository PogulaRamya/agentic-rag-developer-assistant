from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import create_app
from app.agent import DeveloperAgent
from app.settings import Settings
from app.models import Plan, GroundedAnswer, RankedIds
from app.retrieval import DemoRetriever
from app.cleaning import clean_html,chunk_text
from app.bigquery import bounded_query

def test_cleaning_keeps_code_and_removes_script():
    value=clean_html('<p>Hello</p><pre>x = 1\nprint(x)</pre><script>danger()</script>')
    assert 'x = 1\nprint(x)' in value and 'danger' not in value

def test_chunk_overlap_and_tail():
    class Tokenizer:
        def encode(self,text,**kw):
            return SimpleNamespace(offsets=[(i,i+1) for i in range(len(text))])
    assert list(chunk_text('abcdefghij',Tokenizer(),size=4,overlap=1)) == ['abcd','defg','ghij']
    assert list(chunk_text('',Tokenizer())) == []
    with pytest.raises(ValueError):list(chunk_text('x',Tokenizer(),size=4,overlap=4))

@pytest.mark.parametrize('tag',["python; DROP TABLE x", "x' OR 1=1", "x y"])
def test_tag_rejects_sql_syntax(tag):
    with pytest.raises(ValidationError):Plan(route='trend',query='q',tag=tag)

def test_trend_months_bounded():
    with pytest.raises(ValidationError):Plan(route='trend',query='q',months=37)

def test_budget_stops_before_execution():
    client=Mock()
    client.query.return_value.total_bytes_processed=1001
    with pytest.raises(ValueError):bounded_query(client,'SELECT 1',[],1000)
    assert client.query.call_count == 1
    assert client.query.call_args.kwargs['job_config'].dry_run

def test_budget_submits_with_cap():
    client=Mock()
    client.query.return_value.total_bytes_processed=10
    bounded_query(client,'SELECT 1',[],1000)
    assert client.query.call_count == 2
    assert client.query.call_args.kwargs['job_config'].maximum_bytes_billed == 1000

def test_demo_retrieves_original_fixture():
    a=DeveloperAgent(Settings(),DemoRetriever())
    out=a.run('Remove duplicates from a Python list')
    assert out['plan'].route=='retrieval'
    assert out['citations'][0]['id']=='demo-python-dedup'
    assert out['citations'][0]['source_url'] is None
    assert 'demo_lexical_retrieve' in out['trace']

def test_demo_trend_does_not_invent_results():
    out=DeveloperAgent(Settings(),DemoRetriever()).run('Show Python popularity trends')
    assert out['plan'].route=='trend' and out['trend']['rows']==[]
    assert out['insufficient_evidence']

def test_empty_evidence_abstains():
    out=DeveloperAgent(Settings(),DemoRetriever()).run('quantum zebras')
    assert out['insufficient_evidence'] and out['citations']==[]

def test_unknown_source_id_rejected():
    a=DeveloperAgent(Settings(),DemoRetriever(),llm=Mock())
    a.llm.with_structured_output.return_value.invoke.return_value=GroundedAnswer(
        answer='Unsupported claim [made-up]',source_ids=['made-up'])
    out=a.answer({'plan':Plan(route='retrieval',query='x'),'question':'x',
        'evidence':[{'id':'real','text':'evidence'}],'trace':[]})
    assert out['insufficient_evidence'] and out['citations']==[]

def test_rerank_filters_foreign_and_duplicate_ids():
    a=DeveloperAgent(Settings(),DemoRetriever(),llm=Mock())
    a.llm.with_structured_output.return_value.invoke.return_value=RankedIds(ids=['b','fake','b','a'])
    out=a.rerank({'question':'x','candidates':[{'id':'a'},{'id':'b'}],'trace':[]})
    assert [d['id'] for d in out['evidence']]==['b','a']

def test_api_auth_validation_and_demo():
    with TestClient(create_app(Settings(api_key='local-key'))) as c:
        assert c.get('/').status_code==200
        assert c.get('/health').json()['mode']=='demo'
        assert c.post('/ask',json={'question':'Python list duplicates'}).status_code==401
        assert c.post('/ask',headers={'X-API-Key':'local-key'},json={'question':'x'}).status_code==422
        result=c.post('/ask',headers={'X-API-Key':'local-key'},json={'question':'Python list duplicates'})
        assert result.status_code==200 and result.json()['citations']

def test_backend_errors_do_not_leak_details():
    agent=Mock()
    agent.run.side_effect=RuntimeError('secret-backend-password')
    with TestClient(create_app(Settings(),agent)) as c:
        response=c.post('/ask',json={'question':'Some question'})
        assert response.status_code==503 and 'secret-backend-password' not in response.text

def test_production_fails_closed(monkeypatch):
    monkeypatch.setenv('APP_MODE','production')
    monkeypatch.delenv('API_KEY',raising=False)
    with pytest.raises(ValueError):Settings.from_env()

def test_candidate_set_cannot_be_reported_as_reviewed():
    from evaluation.validate_set import load
    rows=load('evaluation/candidates.jsonl')
    assert len(rows)==200 and len({r['intent_id'] for r in rows})==50
    with pytest.raises(ValueError):
        load('evaluation/candidates.jsonl',require_reviewed=True)

def test_full_mocked_model_retrieval_route():
    class FakeModel:
        def with_structured_output(self,schema):
            if schema is Plan:
                return SimpleNamespace(invoke=lambda _:Plan(route='retrieval',query='Python list duplicates'))
            if schema is RankedIds:
                return SimpleNamespace(invoke=lambda _:RankedIds(ids=['demo-python-dedup']))
            return SimpleNamespace(invoke=lambda _:GroundedAnswer(
                answer='Use dict.fromkeys for hashable values. [demo-python-dedup]',
                source_ids=['demo-python-dedup']))
    result=DeveloperAgent(Settings(),DemoRetriever(),llm=FakeModel()).run('Python list duplicates')
    assert result['trace']==['route:retrieval','hybrid_retrieve','rerank','answer']
    assert not result['insufficient_evidence']
