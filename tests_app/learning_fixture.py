"""Small authored fixture for offline browser and contract verification."""
from pathlib import Path

from visual_learning.models import Evidence, KnowledgeModel, KnowledgeUnit, PresentationPlan, Relationship, Snippet, SourceSection, Transcript, Visual
from visual_learning.renderer import render_page


def fixture(language="vi"):
    texts = ["Heat starts the roasting process. Greater heat increases reaction speed.",
             "Development time changes aroma. A longer roast can reduce some acidity, but coffee origin also matters.",
             "Light and dark roast are choices. Light roast preserves more origin character; dark roast brings stronger roast flavors.",
             "First apply heat, then observe color, then stop the roast. This is a simplified process, not a universal recipe."]
    source = Transcript(source_id="fixture", video_id="L_Guz73e6fw", title="Reader interaction fixture — not a real video summary", language="en", origin="authored_test_fixture", snippets=[Snippet(id=f"s{i+1}",text=text,start=i*60,end=i*60+50,timing_basis="speech") for i,text in enumerate(texts)])
    def evidence(i):return [Evidence(snippet_ids=[f"s{i+1}"],quote=texts[i])]
    titles = ["Nhiệt và tốc độ phản ứng", "Thời gian phát triển", "Lựa chọn mức rang", "Quy trình quan sát"] if language=="vi" else ["Heat and reaction speed","Development time","Roast choices","Observation process"]
    summaries=["Nhiệt cao hơn làm phản ứng diễn ra nhanh hơn (reaction speed).","Thời gian phát triển (development time) ảnh hưởng đến hương thơm và một phần độ chua.","Light roast và dark roast tạo trải nghiệm khác nhau.","Gia nhiệt → quan sát màu → dừng rang."] if language=="vi" else texts
    units=[KnowledgeUnit(id=f"u{i+1}",title=titles[i],summary=summaries[i],explanation=texts[i],kind="concept",evidence=evidence(i),technical_terms=["reaction speed"] if i==0 else [],child_ids=["example"] if i==1 else [],caveats=["Coffee origin also matters."] if i==1 else []) for i in range(4)]
    units.append(KnowledgeUnit(id="example",title="Origin changes the result",summary="Coffee origin can change the apparent acidity.",kind="example",evidence=evidence(1)))
    rels=[Relationship(id="r1",source="u1",target="u2",label="supports the roasting conditions",kind="relates_to",status="inference",explanation="Heat and time are related process variables; the source does not give a universal formula.",evidence=evidence(0))]
    sections=[SourceSection(id=f"sec{i+1}",title=titles[i],snippet_ids=[f"s{i+1}"],unit_ids=[f"u{i+1}"]) for i in range(4)]
    knowledge=KnowledgeModel(source_id=source.source_id,language=language,main_question="Điều gì thay đổi khi chúng ta thay đổi cách rang cà phê?" if language=="vi" else "What changes when we change coffee roasting?",main_conclusion="Nhiệt, thời gian và nguyên liệu cùng định hình kết quả. Đây là dữ liệu kiểm thử được viết sẵn." if language=="vi" else "Heat, time, and origin shape the result. This is authored test data.",overview_ids=["u1","u2","u3","u4"],units=units,relationships=rels,sections=sections,source_coverage=[s.id for s in source.snippets],limitations=["Authored fixture; citations do not describe the linked video."])
    plan=PresentationPlan(visuals=[Visual(id="overview",type="concept_map",title="Các yếu tố chính" if language=="vi" else "Major factors",reader_question="Các ý tưởng liên kết thế nào?" if language=="vi" else "How do the ideas connect?",rationale="Major concepts and explicit connection",node_ids=knowledge.overview_ids,relationship_ids=["r1"]),Visual(id="compare",type="comparison",title="So sánh lựa chọn" if language=="vi" else "Compare choices",reader_question="Điều kiện của từng ý tưởng là gì?" if language=="vi" else "What conditions belong to each idea?",rationale="Cross-record comparison",node_ids=["u2","u3"]),Visual(id="timeline",type="timeline",title="Dòng thời gian nguồn" if language=="vi" else "Source timeline",reader_question="Các ý tưởng xuất hiện ở đâu?" if language=="vi" else "Where do the ideas occur?",rationale="Source navigation",section_ids=[s.id for s in sections])],reading_order=["overview","compare","timeline"])
    return source,knowledge,plan


if __name__=="__main__":
    source,knowledge,plan=fixture()
    path=render_page(source,knowledge,plan,Path(".feasibility/reader-fixture/page.html"))
    print(path.resolve())
