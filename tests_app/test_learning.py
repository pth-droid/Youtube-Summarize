import json
from pathlib import Path

import pytest

from tests_app.learning_fixture import fixture
from distill.models import Evidence, KnowledgeUnit, Transcript, validate_bundle, validate_grounding
from distill.pipeline import (Pipeline, PipelineCancelled, PipelineError, constrain_source_ids,
                                      invalid_source_ids, prepare_source, quote_mismatch_feedback, source_windows)
from distill.renderer import render_page


def test_quote_repair_points_to_exact_original_without_changing_evidence():
    unit = KnowledgeUnit(id="u1", title="Heat", summary="Heat changes rate", status="source",
                         evidence=[Evidence(snippet_ids=["s000001"], quote="Heat increased the rate")])
    body = {"snippets": [{"id": "s000001", "text": "Heat increases the reaction rate."}]}
    repair = quote_mismatch_feedback(type("Result", (), {"units": [unit], "relationships": []})(), body)
    assert repair == [{"item_id": "u1", "source_ids": ["s000001"],
                       "rejected_quote": "Heat increased the rate",
                       "exact_source_words": "Heat increases the reaction rate."}]


class SemanticFixtureProvider:
    """Contract fixture: preserves spans and implements staged test output only."""
    name="test"
    model="contract-fixture"
    max_input_chars=36000

    def __init__(self):self.calls=[]

    def generate(self,prompt,schema,work_dir,progress=None):
        self.calls.append(schema["title"])
        body=json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n",1)[1])[0]
        def unit(uid,title,evidence,children=None):
            return {"id":uid,"title":title,"summary":"The source's stated idea.","explanation":"Saved detail.","kind":"concept","status":"source","evidence":evidence,"child_ids":children or []}
        if schema["title"]=="Extraction":
            ss=body["snippets"]
            return {"units":[unit("leaf","Source idea",[{"snippet_ids":[ss[0]["id"]],"quote":ss[0]["text"][:120]}])],"sections":[{"id":"section","title":"Source section","snippet_ids":[s["id"] for s in ss],"unit_ids":["leaf"]}],"relationships":[],"limitations":[]}
        if schema["title"]=="GroundingReview":return {"issues":[],"limitations":[]}
        if schema["title"]=="Synthesis":
            input_units=body["units"]
            return {"main_question":"What does the source explain?","main_conclusion":"The source connects its ideas.","main_conclusion_evidence":input_units[0]["evidence"],"units":[unit("parent","Source model",input_units[0]["evidence"],[u["id"] for u in input_units])],"relationships":[],"limitations":[]}
        if schema["title"]=="PresentationPlan":return {"visuals":[{"id":"overview","type":"concept_map","title":"Major ideas","reader_question":"What connects them?","rationale":"Orient around the source model","node_ids":body["overview_ids"],"relationship_ids":[],"section_ids":[]}],"reading_order":["overview"]}
        raise AssertionError(schema["title"])


def test_long_windows_cover_every_snippet_without_truncation():
    source,_,_=fixture()
    source=Transcript.model_validate({**source.model_dump(),"snippets":[{"id":f"s{i}","text":f"Paragraph {i}: "+"material "*50} for i in range(450)],"content_hash":""})
    windows=source_windows(source,5000)
    assert len(windows)>20
    assert {s.id for window in windows for s in window}=={s.id for s in source.snippets}
    assert all(windows[i][-1].id==windows[i+1][0].id for i in range(len(windows)-1))


def test_large_plain_text_retains_order_and_known_span():
    text="word "*4000
    source=Transcript(source_id="long",snippets=[{"id":"long","text":text,"start":40,"end":90,"timing_basis":"caption"}])
    prepared=prepare_source(source)
    assert " ".join(s.text for s in prepared.snippets).split()==text.split()
    assert all(s.start==40 and s.end==90 for s in prepared.snippets)
    assert prepared.metadata["large_snippets_split"]


def test_grounding_rejects_invented_and_reordered_evidence():
    source,knowledge,_=fixture()
    unit=knowledge.units[0].model_copy(deep=True)
    unit.evidence=[Evidence(snippet_ids=["s1"],quote="Invented quotation")]
    with pytest.raises(ValueError,match="quote"):validate_grounding(source,[unit],[])
    unit.evidence=[Evidence(snippet_ids=["s2","s1"],quote=source.snippets[1].text)]
    with pytest.raises(ValueError,match="original order"):validate_grounding(source,[unit],[])


def test_export_is_self_contained_and_source_cannot_escape_script(tmp_path):
    source,knowledge,plan=fixture()
    data=source.model_dump();data["snippets"][0]["text"]+=' </script><img src=x onerror=alert(1)>'
    data["content_hash"]="";source=Transcript.model_validate(data)
    knowledge.units[0].evidence[0].quote=source.snippets[0].text
    source.metadata={"secret":"DO_NOT_EXPORT_THIS"}
    page=render_page(source,knowledge,plan,tmp_path/"page.html").read_text(encoding="utf-8")
    assert "<script src=" not in page and "<link" not in page
    assert "DO_NOT_EXPORT_THIS" not in page
    embedded=page.split('<script type="application/json" id="learning-data">',1)[1].split("</script>",1)[0]
    assert "</script>" not in embedded
    assert json.loads(embedded)["source"]["snippets"][0]["text"]==source.snippets[0].text
    assert 'lang="vi"' in page and "Khám phá" in page


def test_pipeline_checkpoints_restore_without_new_model_calls(tmp_path):
    source,_,_=fixture()
    provider=SemanticFixtureProvider()
    result=Pipeline(provider).run(source,{"language":"en"},tmp_path)
    assert Path(result["page_path"]).is_file()
    calls=len(provider.calls)
    Pipeline(provider).run(source,{"language":"en"},tmp_path)
    assert len(provider.calls)==calls
    knowledge=json.loads(Path(result["knowledge_path"]).read_text(encoding="utf-8"))
    assert set(knowledge["source_coverage"])=={s.id for s in source.snippets}
    assert all(u["id"] in knowledge["units"][-1]["child_ids"] for u in knowledge["units"][:-1])


def test_pipeline_larger_input_covers_and_bounds_every_request(tmp_path):
    original,_,_=fixture()
    source=Transcript.model_validate({**original.model_dump(),"snippets":[{"id":f"s{i}","text":f"This section {i} states an important idea. "+"Evidence from the source. "*20} for i in range(280)],"content_hash":""})
    provider=SemanticFixtureProvider()
    pipeline=Pipeline(provider);result=pipeline.run(source,{"language":"vi"},tmp_path)
    record=json.loads(Path(result["generation_path"]).read_text(encoding="utf-8"))
    assert record["source_snippets"]==record["covered_snippets"]==280
    assert all(r["characters"]<=r["limit"] for r in record["request_sizes"])
    assert provider.calls.count("Extraction")>5


def test_cancellation_stops_before_provider_and_source_survives(tmp_path):
    source,_,_=fixture();provider=SemanticFixtureProvider()
    with pytest.raises(PipelineCancelled):Pipeline(provider).run(source,{},tmp_path,cancelled=lambda:True)
    assert provider.calls==[] and (tmp_path/"source.json").exists()


def test_invalid_outputs_are_repaired_only_three_times(tmp_path):
    source,_,_=fixture()
    class InvalidProvider(SemanticFixtureProvider):
        def generate(self,*args,**kwargs):self.calls.append("invalid");return {"units":[]}
    provider=InvalidProvider()
    with pytest.raises(PipelineError,match="three attempts"):Pipeline(provider).run(source,{},tmp_path)
    assert len(provider.calls)==3


def test_bundle_rejects_missing_coverage_and_false_causal_visual():
    source,knowledge,plan=fixture()
    knowledge.source_coverage.pop()
    with pytest.raises(ValueError,match="coverage"):validate_bundle(source,knowledge,plan)
    knowledge.source_coverage=[s.id for s in source.snippets]
    plan.visuals[0].type="causal_graph"
    with pytest.raises(ValueError,match="causes"):validate_bundle(source,knowledge,plan)


def test_compact_section_ranges_expand_exact_source_coverage(tmp_path):
    source,_,_=fixture()
    class RangeProvider(SemanticFixtureProvider):
        def generate(self,prompt,schema,work_dir,progress=None):
            value=super().generate(prompt,schema,work_dir,progress)
            if schema["title"]=="Extraction":
                ids=value["sections"][0]["snippet_ids"]
                value["sections"][0].update(snippet_ids=[ids[0]],range_end=ids[-1])
            return value
    result=Pipeline(RangeProvider()).run(source,{},tmp_path)
    knowledge=json.loads(Path(result["knowledge_path"]).read_text(encoding="utf-8"))
    assert knowledge["sections"][0]["snippet_ids"]==[s.id for s in source.snippets]


def test_cached_window_cannot_falsely_claim_complete_coverage(tmp_path):
    source,_,_=fixture();provider=SemanticFixtureProvider()
    Pipeline(provider).run(source,{},tmp_path)
    path=tmp_path/"checkpoints"/"extraction_0000.json"
    record=json.loads(path.read_text(encoding="utf-8"));record["data"]["sections"][0]["snippet_ids"].pop()
    path.write_text(json.dumps(record),encoding="utf-8")
    calls=len(provider.calls)
    with pytest.raises(PipelineError,match="does not match this window"):Pipeline(provider).run(source,{},tmp_path)
    assert len(provider.calls)==calls


def test_review_repairs_reversed_cause_once_and_reviews_again(tmp_path):
    source=Transcript(source_id="cause",snippets=[{"id":"s1","text":"Heat causes degradation."}])
    class RepairProvider(SemanticFixtureProvider):
        def generate(self,prompt,schema,work_dir,progress=None):
            body=json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n",1)[1])[0]
            if schema["title"]=="Extraction":
                self.calls.append("Extraction");e=[{"snippet_ids":["s1"],"quote":"Heat causes degradation."}]
                units=[{"id":uid,"title":title,"summary":title,"evidence":e} for uid,title in [("heat","Heat"),("degradation","Degradation")]]
                return {"units":units,"relationships":[{"id":"cause","source":"degradation","target":"heat","kind":"causes","label":"causes","evidence":e}],"sections":[{"id":"one","title":"Mechanism","snippet_ids":["s1"],"unit_ids":["heat","degradation"]}]}
            if schema["title"]=="GroundingReview":
                self.calls.append("GroundingReview")
                bad=[i for i in body["items"] if i.get("kind")=="causes" and i["source"].endswith("_degradation")]
                return {"issues":[{"item_id":i["id"],"verdict":"contradicted","reason":"The source says heat causes degradation; reverse the direction."} for i in bad],"limitations":[]}
            if schema["title"]=="GroundingCorrections":
                self.calls.append("GroundingCorrections");r=body["relationships"][0]
                return {"units":[],"relationships":[{**r,"source":r["target"],"target":r["source"]}]}
            return super().generate(prompt,schema,work_dir,progress)
    provider=RepairProvider();result=Pipeline(provider).run(source,{},tmp_path)
    knowledge=json.loads(Path(result["knowledge_path"]).read_text(encoding="utf-8"))
    cause=knowledge["relationships"][0]
    assert cause["source"].endswith("_heat") and cause["target"].endswith("_degradation")
    assert cause["status"]=="source" and not cause["caveats"]
    assert provider.calls.count("GroundingCorrections")==1 and provider.calls.count("GroundingReview")>=3


def test_aggregated_review_limitations_remain_valid_on_resume(tmp_path):
    source,_,_=fixture()
    class ManyLimitations(SemanticFixtureProvider):
        def generate(self,prompt,schema,work_dir,progress=None):
            value=super().generate(prompt,schema,work_dir,progress)
            if schema["title"]=="GroundingReview":value["limitations"]=[f"Source limitation {i}" for i in range(20)]
            return value
    provider=ManyLimitations();Pipeline(provider).run(source,{},tmp_path)
    calls=len(provider.calls)
    result=Pipeline(provider).run(source,{},tmp_path)
    assert len(provider.calls)==calls
    record=json.loads(Path(result["generation_path"]).read_text(encoding="utf-8"))
    assert record["usage_scope"]=="current invocation only; usage from earlier cached stages is excluded"
    assert record["cached_stages"] and not record["usage"]


def test_grounding_review_deduplicates_quotes_without_losing_original_passages(tmp_path):
    source = Transcript(source_id="shared-evidence", snippets=[
        {"id": f"s{i}", "text": f"Original passage {i}. " + "source material " * 80}
        for i in range(3)
    ])
    evidence = [Evidence(snippet_ids=[s.id], quote=s.text) for s in source.snippets]
    units = [KnowledgeUnit(id=f"u{i}", title=f"Claim {i}", summary="A source claim.",
                           evidence=evidence) for i in range(14)]
    validate_grounding(source, units, [])
    class ReviewProvider(SemanticFixtureProvider):
        def generate(self, prompt, schema, work_dir, progress=None):
            self.calls.append(schema["title"])
            body = json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n", 1)[1])[0]
            assert {i["id"] for i in body["items"]} == {u.id for u in units}
            assert body["original_passages"] == [{"id": s.id, "text": s.text} for s in source.snippets]
            assert all(e["snippet_ids"] and "quote" not in e for i in body["items"] for e in i["evidence"])
            return {"issues": [], "limitations": []}
    provider = ReviewProvider()
    assert Pipeline(provider)._review(source, units, [], tmp_path) == []
    assert provider.calls == ["GroundingReview"]
    assert all(unit.evidence[0].quote == source.snippets[0].text for unit in units)


def test_source_id_schema_rejects_added_words_and_preserves_custom_import_ids():
    import re
    from distill.models import Extraction
    schema = Extraction.model_json_schema()
    known = constrain_source_ids(schema, {"snippets": [{"id": "s000265.p001", "text": "Original words"}]})
    pattern = schema["$defs"]["Evidence"]["properties"]["snippet_ids"]["items"]["pattern"]
    assert re.fullmatch(pattern, "s000265.p001")
    assert not re.fullmatch(pattern, "s000265 text")
    assert not re.fullmatch(pattern, "s000265 شب")
    assert not re.fullmatch(pattern, "s000265_ID_PLACEHOLDER")
    assert invalid_source_ids({"evidence": [{"snippet_ids": ["s000265 text"]}]}, known) == ["s000265 text"]
    custom = Extraction.model_json_schema()
    constrain_source_ids(custom, {"snippets": [{"id": "original section 1", "text": "Original words"}]})
    assert "pattern" not in custom["$defs"]["Evidence"]["properties"]["snippet_ids"]["items"]


def test_citation_repair_names_actual_missing_ids(tmp_path):
    source, _, _ = fixture()
    class CitationProvider(SemanticFixtureProvider):
        def generate(self, prompt, schema, work_dir, progress=None):
            value = super().generate(prompt, schema, work_dir, progress)
            if schema["title"] == "Extraction":
                if self.calls.count("Extraction") == 1:
                    value["units"][0]["evidence"][0]["snippet_ids"][0] += " text"
                else:
                    assert 'Invalid source IDs: ["s1 text"]' in prompt
            return value
    provider = CitationProvider()
    result = Pipeline(provider).run(source, {}, tmp_path)
    assert Path(result["page_path"]).is_file()
    assert provider.calls.count("Extraction") == 2
