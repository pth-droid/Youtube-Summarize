"""Explicit live subscription-only feasibility run; never used by unit tests."""
import argparse
import json
import sys
from pathlib import Path

from visual_learning.models import Transcript
from visual_learning.pipeline import Pipeline
from visual_learning.providers import CodexProvider


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--snippets",type=int,default=0)
    parser.add_argument("--output",required=True)
    parser.add_argument("--language",default="vi")
    args=parser.parse_args()
    data=json.loads(Path(args.source).read_text(encoding="utf-8"))
    if args.snippets:
        data["snippets"]=data["snippets"][:args.snippets]
        data["content_hash"]=""
        data["metadata"]["probe_excerpt"]=True
        data["title"] += " (feasibility excerpt)"
    source=Transcript.model_validate(data)
    provider=CodexProvider(timeout_seconds=600)
    result=Pipeline(provider).run(source,{"language":args.language},Path(args.output),progress=lambda stage,details:print(stage,details,flush=True))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
