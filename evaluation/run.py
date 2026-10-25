"""Evaluate a reviewed 200-question set against production API; never fabricate scores."""
import argparse
import json
import os
from pathlib import Path
import httpx
from ragas import EvaluationDataset,evaluate
from ragas.metrics import Faithfulness,LLMContextRecall
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic
from evaluation.validate_set import load

def retrieval_metrics(expected,retrieved):
    relevant=set(map(str,expected))
    unique=list(dict.fromkeys(map(str,retrieved)))[:6]
    recall=len(relevant & set(unique))/len(relevant)
    rr=next((1/(i+1) for i,item in enumerate(unique) if item in relevant),0.0)
    return recall,rr

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',required=True)
    p.add_argument('--url',default='http://127.0.0.1:8000')
    p.add_argument('--output',default='artifacts/evaluation')
    a=p.parse_args()
    questions=load(a.dataset,require_reviewed=True)
    samples=[];scores=[]
    with httpx.Client(timeout=240,headers={'X-API-Key':os.environ['API_KEY']}) as client:
        for row in questions:
            response=client.post(a.url+'/ask',json={'question':row['question']})
            response.raise_for_status()
            answer=response.json()
            if answer['mode']!='production' or answer['route']!='retrieval':
                raise ValueError('Golden retrieval evaluation requires production retrieval answers')
            docs=answer['retrieved_contexts']
            samples.append({'user_input':row['question'],'response':answer['answer'],
                            'retrieved_contexts':[d['text'] for d in docs],'reference':row['reference']})
            recall,rr=retrieval_metrics(row['expected_answer_ids'],[d['answer_id'] for d in docs])
            scores.append({'id':row['id'],'recall_at_6':recall,'reciprocal_rank':rr})
    judge=LangchainLLMWrapper(ChatAnthropic(model=os.environ['CLAUDE_MODEL'],
        api_key=os.environ['ANTHROPIC_API_KEY'],temperature=0,max_tokens=3000))
    result=evaluate(EvaluationDataset.from_list(samples),
                    metrics=[Faithfulness(),LLMContextRecall()],llm=judge,raise_exceptions=True)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    result.to_pandas().to_csv(out/'ragas.csv',index=False)
    (out/'retrieval.json').write_text(json.dumps(scores,indent=2))
    (out/'summary.json').write_text(json.dumps({'n':len(scores),
        'recall_at_6':sum(r['recall_at_6'] for r in scores)/len(scores),
        'mrr_at_6':sum(r['reciprocal_rank'] for r in scores)/len(scores)},indent=2))
    print(result)

if __name__=='__main__':main()
