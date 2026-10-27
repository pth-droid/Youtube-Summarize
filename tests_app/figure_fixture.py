"""Authored coffee roasting and extraction fixture for figure contracts and browser checks.

The passages are written for tests; they are not a summary of a real video and their
numbers are teaching examples, not measurements.
"""
from pathlib import Path

from distill.models import (Chapter, Evidence, FigurePlan, KnowledgeModel, KnowledgeUnit, LecturePart, LecturePlan, LectureSlide,
                            PresentationPlan, Relationship, Snippet, SourceSection, Transcript, Visual)

TEXTS = [
    "Green coffee is charged into the drum at about 200°C and the bean temperature falls to a turning point near 90°C after about one and a half minutes.",
    "The drum passes heat to beans that touch it by conduction, hot air carries heat by convection, and the hot drum wall or a halogen lamp adds radiant heat.",
    "During drying, moisture in the bean falls from about 11 percent toward 2 percent and leaves as steam through the exhaust.",
    "Around 150°C, at roughly four and a half minutes, the beans turn yellow and Maillard reactions begin.",
    "Sugars such as sucrose break down, chlorogenic acids degrade, and brown melanoidins and carbon dioxide form.",
    "Steam and carbon dioxide build pressure inside the bean until the cell walls crack: first crack, near 196°C at about nine minutes.",
    "After first crack the bean expands and becomes more porous; development continues until the drop at about 210°C and eleven minutes.",
    "More airflow increases convective heat transfer and carries moisture and smoke out of the drum.",
    "More convective heat raises the rate of rise, and more gas power raises the rate of rise too.",
    "A higher rate of rise shortens the time to first crack.",
    "In espresso, the pump builds about nine bar, which pushes hot water through the compacted coffee puck.",
    "Pre-infusion wets the puck at low pressure for about eight seconds before full pressure.",
    "Water first washes solubles from particle surfaces, then dissolves them more slowly from inside the particles.",
    "If water finds a channel through a crack in the puck, it rushes through and most of the coffee is under-extracted.",
    "A shot of about 36 grams usually runs in about 28 seconds.",
    "Brewing control charts place extraction yields of about 18 to 22 percent and strength of about 1.15 to 1.35 percent as the usual target.",
]

UNITS = [  # id, kind, title, summary, passage
    ("charge", "step", "Nạp hạt và điểm chuyển", "Nạp hạt ở khoảng 200°C; nhiệt độ hạt xuống điểm chuyển gần 90°C sau khoảng 1 phút 30.", 0),
    ("heat", "mechanism", "Ba đường truyền nhiệt", "Trống dẫn nhiệt, khí nóng đối lưu, thành trống hoặc đèn halogen bức xạ nhiệt vào hạt.", 1),
    ("drying", "step", "Giai đoạn sấy", "Độ ẩm của hạt giảm từ khoảng 11% xuống gần 2% và thoát ra dưới dạng hơi nước.", 2),
    ("maillard", "mechanism", "Vàng hạt và phản ứng Maillard", "Khoảng 150°C, ở phút thứ 4,5, hạt chuyển vàng và phản ứng Maillard bắt đầu.", 3),
    ("chemistry", "mechanism", "Hợp chất mất đi và sinh ra", "Sucrose phân hủy, axit chlorogenic suy giảm, melanoidin và CO₂ hình thành.", 4),
    ("crack", "mechanism", "Áp suất trong hạt và nứt lần 1", "Hơi nước và CO₂ tạo áp suất trong hạt đến khi thành tế bào nứt, gần 196°C ở phút thứ 9.", 5),
    ("development", "step", "Phát triển và ra lò", "Sau nứt lần 1 hạt nở và xốp hơn; ra lò ở khoảng 210°C, phút thứ 11.", 6),
    ("airflow", "concept", "Lưu lượng gió", "Gió nhiều hơn làm tăng truyền nhiệt đối lưu và đưa ẩm, khói ra khỏi trống.", 7),
    ("exhaust", "concept", "Thoát ẩm và khói", "Ẩm và khói được gió mang ra khỏi trống.", 7),
    ("convection", "mechanism", "Truyền nhiệt đối lưu", "Nhiệt đối lưu nhiều hơn làm tốc độ tăng nhiệt cao hơn.", 8),
    ("gas", "concept", "Công suất gas", "Tăng gas cũng làm tốc độ tăng nhiệt cao hơn.", 8),
    ("ror", "concept", "Tốc độ tăng nhiệt (RoR)", "Tốc độ tăng nhiệt độ hạt theo thời gian.", 8),
    ("first_crack_time", "concept", "Thời gian đến nứt lần 1", "RoR cao hơn làm hạt đến nứt lần 1 sớm hơn.", 9),
    ("pressure", "mechanism", "Áp suất 9 bar", "Bơm tạo khoảng 9 bar, đẩy nước nóng qua bánh cà phê đã nén.", 10),
    ("preinfusion", "step", "Ngâm trước", "Ngâm trước làm ướt bánh cà phê ở áp suất thấp khoảng 8 giây.", 11),
    ("dissolve", "mechanism", "Rửa bề mặt rồi khuếch tán", "Nước rửa chất tan trên bề mặt hạt bột trước, rồi hòa tan chậm hơn từ bên trong.", 12),
    ("channel", "mechanism", "Nước xuyên kênh", "Nước tìm được kênh qua vết nứt sẽ chảy nhanh; phần lớn cà phê bị chiết thiếu.", 13),
    ("shot", "example", "Một shot 36 g trong 28 giây", "Một shot khoảng 36 g thường chảy trong khoảng 28 giây.", 14),
    ("control_chart", "concept", "Biểu đồ kiểm soát pha", "Mục tiêu thường là hiệu suất chiết 18–22% và nồng độ 1,15–1,35% TDS.", 15),
]

RELATIONSHIPS = [  # id, source, target, label, passage
    ("air_convection", "airflow", "convection", "tăng truyền nhiệt đối lưu", 7),
    ("air_exhaust", "airflow", "exhaust", "mang ẩm và khói ra", 7),
    ("convection_ror", "convection", "ror", "làm RoR tăng", 8),
    ("gas_ror", "gas", "ror", "làm RoR tăng", 8),
    ("ror_first_crack", "ror", "first_crack_time", "rút ngắn thời gian đến nứt lần 1", 9),
]


def figure_fixture():
    source = Transcript(source_id="coffee-figures", video_id="L_Guz73e6fw", title="Coffee process fixture — authored test data", language="en",
                        origin="authored_test_fixture",
                        snippets=[Snippet(id=f"s{i + 1}", text=text, start=i * 30, end=i * 30 + 25, timing_basis="speech") for i, text in enumerate(TEXTS)])
    evidence = lambda i: [Evidence(snippet_ids=[f"s{i + 1}"], quote=TEXTS[i])]
    units = [KnowledgeUnit(id=uid, kind=kind, title=title, summary=summary, explanation=TEXTS[i], evidence=evidence(i))
             for uid, kind, title, summary, i in UNITS]
    relationships = [Relationship(id=rid, source=a, target=b, label=label, kind="causes", evidence=evidence(i))
                     for rid, a, b, label, i in RELATIONSHIPS]
    roast = [uid for uid, *_rest, i in UNITS if i < 10]
    brew = [uid for uid, *_rest, i in UNITS if i >= 10]
    sections = [SourceSection(id="roasting", title="Rang cà phê", snippet_ids=[f"s{i + 1}" for i in range(10)], unit_ids=roast),
                SourceSection(id="extraction", title="Chiết xuất espresso", snippet_ids=[f"s{i + 1}" for i in range(10, 16)], unit_ids=brew)]
    chapters = [Chapter(id="chapter_01", title="Rang cà phê", section_ids=["roasting"], unit_ids=["heat", "crack", "chemistry", "airflow"], depth="expert", detail="detailed"),
                Chapter(id="chapter_02", title="Chiết xuất espresso", section_ids=["extraction"], unit_ids=["pressure", "dissolve", "channel"], depth="expert", detail="detailed")]
    knowledge = KnowledgeModel(source_id=source.source_id, language="vi", main_question="Nhiệt, gió và áp suất làm thay đổi hạt cà phê và ly espresso thế nào?",
                               main_conclusion="Rang là chuỗi biến đổi theo pha do nhiệt và gió điều khiển; chiết xuất là dòng nước qua bánh cà phê dưới áp suất. Đây là dữ liệu kiểm thử được viết sẵn.",
                               main_conclusion_evidence=evidence(1), overview_ids=["heat", "crack", "chemistry", "airflow", "pressure", "dissolve", "channel"],
                               units=units, relationships=relationships, sections=sections, chapters=chapters,
                               source_coverage=[s.id for s in source.snippets], limitations=["Authored fixture; numbers are teaching examples, not measurements."])
    presentation = PresentationPlan(visuals=[Visual(id="overview", type="causal_graph", title="Các thông số và tác động", reader_question="Thông số nào ảnh hưởng đến RoR?",
                                                    rationale="Stated causes", node_ids=["airflow", "convection", "gas", "ror", "first_crack_time"],
                                                    relationship_ids=["air_convection", "convection_ror", "gas_ror", "ror_first_crack"])])
    return source, knowledge, presentation


ROAST = {"figures": [
    {"id": "roast_timeline", "type": "process", "title": "Một mẻ rang theo từng giai đoạn", "reader_question": "Khi nhiệt độ hạt tăng, bên trong hạt và các hợp chất thay đổi ra sao?",
     "caption": "Kéo thanh thời gian để xem hạt, nhiệt độ và hợp chất ở cùng một thời điểm.", "unit_ids": ["charge", "drying", "maillard", "crack", "development", "chemistry"],
     "process": {"axis": "time", "axis_label": "Thời gian rang", "axis_unit": "", "subject": "bean", "subject_label": "Hạt cà phê",
                 "phases": [{"id": "drying", "label": "Sấy", "start": 0, "end": 270, "note": "Độ ẩm giảm từ khoảng 11% xuống gần 2%, thoát ra thành hơi nước.", "unit_ids": ["drying"]},
                            {"id": "maillard", "label": "Maillard", "start": 270, "end": 540, "note": "Hạt chuyển vàng ở khoảng 150°C; phản ứng Maillard tạo màu nâu.", "unit_ids": ["maillard"]},
                            {"id": "development", "label": "Phát triển", "start": 540, "end": 660, "note": "Sau nứt lần 1 hạt nở, xốp hơn; ra lò ở khoảng 210°C.", "unit_ids": ["development"]}],
                 "events": [{"at": 90, "label": "Điểm chuyển", "unit_ids": ["charge"]}, {"at": 270, "label": "Vàng hạt", "unit_ids": ["maillard"]},
                            {"at": 540, "label": "Nứt lần 1", "unit_ids": ["crack"]}, {"at": 660, "label": "Ra lò", "unit_ids": ["development"]}],
                 "series": [{"id": "bt", "label": "Nhiệt độ hạt", "unit": "°C", "provenance": "source", "unit_ids": ["charge", "maillard", "crack", "development"],
                             "points": [{"x": 90, "y": 90}, {"x": 270, "y": 150}, {"x": 540, "y": 196}, {"x": 660, "y": 210}]},
                            {"id": "ror", "label": "RoR", "unit": "°C/min", "provenance": "illustrative", "unit_ids": ["ror"],
                             "points": [{"x": 90, "y": 22}, {"x": 200, "y": 17}, {"x": 330, "y": 12}, {"x": 450, "y": 9}, {"x": 560, "y": 6}, {"x": 660, "y": 4}]}],
                 "states": [{"phase_id": "drying", "caption": "Hạt xanh còn nhiều nước, đặc và nhỏ.", "unit_ids": ["drying"],
                             "properties": [{"key": "moisture", "label": "Độ ẩm", "level": 3, "text": "11% → 2%"}, {"key": "color", "label": "Màu", "level": 0, "text": ""}, {"key": "volume", "label": "Thể tích", "level": 1, "text": ""}]},
                            {"phase_id": "maillard", "caption": "Hạt vàng rồi nâu dần, áp suất hơi nước tăng bên trong.", "unit_ids": ["maillard", "crack"],
                             "properties": [{"key": "moisture", "label": "Độ ẩm", "level": 1, "text": ""}, {"key": "color", "label": "Màu", "level": 2, "text": ""}, {"key": "pressure", "label": "Áp suất trong hạt", "level": 2, "text": ""}]},
                            {"phase_id": "development", "caption": "Thành tế bào nứt, hạt nở và xốp hơn.", "unit_ids": ["crack", "development"],
                             "properties": [{"key": "color", "label": "Màu", "level": 3, "text": ""}, {"key": "volume", "label": "Thể tích", "level": 4, "text": ""}, {"key": "cracks", "label": "Vết nứt", "level": 2, "text": ""}, {"key": "porosity", "label": "Độ xốp", "level": 3, "text": ""}]}],
                 "compounds": [{"name": "Sucrose", "levels": [4, 3, 1], "note": "", "unit_ids": ["chemistry"]},
                               {"name": "Axit chlorogenic", "levels": [4, 3, 2], "note": "", "unit_ids": ["chemistry"]},
                               {"name": "Melanoidin", "levels": [0, 2, 4], "note": "", "unit_ids": ["chemistry"]},
                               {"name": "CO₂", "levels": [0, 1, 4], "note": "", "unit_ids": ["chemistry", "crack"]}]}},
    {"id": "roaster", "type": "apparatus", "title": "Nhiệt và gió đi qua máy rang trống", "reader_question": "Nhiệt đến hạt bằng những đường nào, và gió mang gì ra?",
     "caption": "", "unit_ids": ["heat", "airflow", "exhaust"],
     "apparatus": {"template": "drum_roaster", "parts": [
         {"slot": "drum", "label": "Trống quay", "note": "Thành trống nóng dẫn nhiệt vào hạt chạm vào nó.", "unit_ids": ["heat"]},
         {"slot": "bean_mass", "label": "Khối hạt", "note": "", "unit_ids": ["heat"]},
         {"slot": "burner", "label": "Đầu đốt gas", "note": "", "unit_ids": ["gas"]},
         {"slot": "radiant_element", "label": "Đèn halogen", "note": "Bức xạ nhiệt trực tiếp lên hạt.", "unit_ids": ["heat"]},
         {"slot": "air_inlet", "label": "Cửa gió vào", "note": "", "unit_ids": ["airflow"]},
         {"slot": "damper", "label": "Van gió", "note": "Điều chỉnh lưu lượng gió qua trống.", "unit_ids": ["airflow"]},
         {"slot": "bt_probe", "label": "Đầu dò nhiệt độ hạt (BT)", "note": "", "unit_ids": ["charge"]},
         {"slot": "et_probe", "label": "Đầu dò nhiệt độ khí (ET)", "note": "", "unit_ids": ["heat"]}],
      "flows": [{"path": "flame_to_drum", "kind": "conduction", "label": "Lửa nung trống", "unit_ids": ["heat"]},
                {"path": "drum_to_beans", "kind": "conduction", "label": "Trống dẫn nhiệt vào hạt", "unit_ids": ["heat"]},
                {"path": "hot_air", "kind": "convection", "label": "Khí nóng đối lưu", "unit_ids": ["heat", "airflow"]},
                {"path": "radiant_heat", "kind": "radiation", "label": "Bức xạ từ đèn halogen", "unit_ids": ["heat"]},
                {"path": "bean_moisture", "kind": "gas", "label": "Hơi nước rời hạt", "unit_ids": ["drying"]},
                {"path": "exhaust_path", "kind": "air", "label": "Gió mang ẩm và khói ra", "unit_ids": ["exhaust"]}]}},
    {"id": "roast_levers", "type": "what_if", "title": "Nếu chỉnh gió hoặc gas", "reader_question": "Tăng gió hay tăng gas thì RoR và thời gian đến nứt lần 1 thay đổi theo chiều nào?",
     "caption": "", "unit_ids": ["airflow", "gas", "ror", "first_crack_time"],
     "what_if": {"levers": [{"unit_id": "airflow", "label": "Gió"}, {"unit_id": "gas", "label": "Gas"}],
                 "effects": [{"relationship_id": "air_convection", "direction": "increases"}, {"relationship_id": "air_exhaust", "direction": "increases"},
                             {"relationship_id": "convection_ror", "direction": "increases"}, {"relationship_id": "gas_ror", "direction": "increases"},
                             {"relationship_id": "ror_first_crack", "direction": "decreases"}]}},
    {"id": "scales", "type": "scale_ladder", "title": "Cùng một quá trình ở nhiều cỡ", "reader_question": "Nhiệt và áp suất tác động ở những thang kích thước nào?",
     "caption": "", "unit_ids": ["heat", "crack", "chemistry"],
     "scale_ladder": {"levels": [{"scale": "Trống · khoảng 1 m", "title": "Máy rang", "summary": "Lửa, gió và trống quay truyền nhiệt vào cả mẻ.", "unit_ids": ["heat"]},
                                 {"scale": "Hạt · khoảng 1 cm", "title": "Hạt cà phê", "summary": "Hạt mất nước, đổi màu và nở ra.", "unit_ids": ["drying", "development"]},
                                 {"scale": "Tế bào · micromet", "title": "Thành tế bào", "summary": "Áp suất hơi nước và CO₂ làm thành tế bào nứt.", "unit_ids": ["crack"]},
                                 {"scale": "Phân tử · nanomet", "title": "Hợp chất", "summary": "Đường và axit phân hủy; melanoidin hình thành.", "unit_ids": ["chemistry"]}]}},
]}

EXTRACTION = {"figures": [
    {"id": "shot", "type": "process", "title": "Một shot espresso theo giây", "reader_question": "Áp suất và dòng nước thay đổi thế nào, và chất tan rời hạt bột ra sao?",
     "caption": "", "unit_ids": ["pressure", "preinfusion", "dissolve", "shot"],
     "process": {"axis": "time", "axis_label": "Thời gian chiết", "axis_unit": "", "subject": "particle", "subject_label": "Hạt bột cà phê",
                 "phases": [{"id": "pre", "label": "Ngâm trước", "start": 0, "end": 8, "note": "Làm ướt bánh cà phê ở áp suất thấp.", "unit_ids": ["preinfusion"]},
                            {"id": "full", "label": "Áp suất đầy đủ", "start": 8, "end": 28, "note": "Khoảng 9 bar đẩy nước qua bánh cà phê.", "unit_ids": ["pressure"]}],
                 "events": [{"at": 28, "label": "Dừng ở 36 g", "unit_ids": ["shot"]}],
                 "series": [{"id": "pressure", "label": "Áp suất", "unit": "bar", "provenance": "background", "unit_ids": ["pressure", "preinfusion"],
                             "points": [{"x": 0, "y": 0}, {"x": 2, "y": 2}, {"x": 8, "y": 2.5}, {"x": 11, "y": 9}, {"x": 28, "y": 9}]},
                            {"id": "weight", "label": "Khối lượng ly", "unit": "g", "provenance": "source", "unit_ids": ["shot"],
                             "points": [{"x": 0, "y": 0}, {"x": 28, "y": 36}]}],
                 "states": [{"phase_id": "pre", "caption": "Nước thấm vào hạt bột; chất tan trên bề mặt bắt đầu rời ra.", "unit_ids": ["preinfusion", "dissolve"],
                             "properties": [{"key": "moisture", "label": "Độ ướt", "level": 3, "text": ""}, {"key": "dissolved", "label": "Đã hòa tan", "level": 1, "text": ""}]},
                            {"phase_id": "full", "caption": "Bề mặt đã được rửa; chất tan khuếch tán chậm từ bên trong.", "unit_ids": ["dissolve"],
                             "properties": [{"key": "moisture", "label": "Độ ướt", "level": 4, "text": ""}, {"key": "dissolved", "label": "Đã hòa tan", "level": 3, "text": ""}]}],
                 "compounds": []}},
    {"id": "machine", "type": "apparatus", "title": "Nước, nhiệt và áp suất trong máy espresso", "reader_question": "Nước đi đường nào, và chuyện gì xảy ra khi có kênh?",
     "caption": "", "unit_ids": ["pressure", "channel", "dissolve"],
     "apparatus": {"template": "espresso", "parts": [
         {"slot": "pump", "label": "Bơm", "note": "Tạo khoảng 9 bar.", "unit_ids": ["pressure"]},
         {"slot": "gauge", "label": "Đồng hồ áp suất", "note": "", "unit_ids": ["pressure"]},
         {"slot": "boiler", "label": "Nồi hơi", "note": "", "unit_ids": ["pressure"]},
         {"slot": "shower_screen", "label": "Lưới chia nước", "note": "", "unit_ids": ["pressure"]},
         {"slot": "puck", "label": "Bánh cà phê", "note": "Nước rửa bề mặt rồi khuếch tán từ trong hạt bột.", "unit_ids": ["dissolve"]},
         {"slot": "cup", "label": "Ly espresso", "note": "", "unit_ids": ["shot"]}],
      "flows": [{"path": "to_group", "kind": "water", "label": "Nước nóng tới group", "unit_ids": ["pressure"]},
                {"path": "pressure_on_puck", "kind": "pressure", "label": "Áp suất khoảng 9 bar", "unit_ids": ["pressure"]},
                {"path": "percolation", "kind": "water", "label": "Nước thấm qua bánh cà phê", "unit_ids": ["dissolve"]},
                {"path": "channel", "kind": "water", "label": "Kênh: nước chảy tắt", "unit_ids": ["channel"]},
                {"path": "dissolved_solids", "kind": "material", "label": "Chất tan rời bánh cà phê", "unit_ids": ["dissolve"]},
                {"path": "to_cup", "kind": "water", "label": "Espresso xuống ly", "unit_ids": ["shot"]}]}},
    {"id": "control", "type": "region_map", "title": "Biểu đồ kiểm soát pha", "reader_question": "Ly cà phê nằm ở vùng nào giữa hiệu suất chiết và nồng độ?",
     "caption": "", "unit_ids": ["control_chart"],
     "region_map": {"x_label": "Hiệu suất chiết", "x_unit": "%", "y_label": "Nồng độ", "y_unit": "% TDS", "x_min": 14, "x_max": 26, "y_min": 0.9, "y_max": 1.6,
                    "provenance": "source", "points": [],
                    "regions": [{"label": "Mục tiêu thường gặp", "x_min": 18, "x_max": 22, "y_min": 1.15, "y_max": 1.35, "note": "Hiệu suất 18–22%, nồng độ 1,15–1,35%.", "emphasis": True, "unit_ids": ["control_chart"]},
                                {"label": "Chiết thiếu", "x_min": 14, "x_max": 18, "y_min": 0.9, "y_max": 1.6, "note": "", "emphasis": False, "unit_ids": ["control_chart"]},
                                {"label": "Chiết quá", "x_min": 22, "x_max": 26, "y_min": 0.9, "y_max": 1.6, "note": "", "emphasis": False, "unit_ids": ["control_chart"]}]}},
]}


def figure_plans():
    return FigurePlan.model_validate(ROAST), FigurePlan.model_validate(EXTRACTION)


def figure_lecture():
    return LecturePlan(title="Rang và chiết xuất cà phê", objectives=["Giải thích ba đường truyền nhiệt.", "Mô tả dòng nước qua bánh cà phê."],
                       takeaways=["Nhiệt và gió điều khiển các giai đoạn rang.", "Áp suất đẩy nước qua bánh cà phê."],
                       parts=[LecturePart(chapter_id="chapter_01", slides=[LectureSlide(layout="points", title="Nhiệt đến hạt theo ba đường", points=["Dẫn nhiệt", "Đối lưu", "Bức xạ"], unit_ids=["heat"])]),
                              LecturePart(chapter_id="chapter_02", slides=[LectureSlide(layout="points", title="Áp suất và dòng nước", points=["Khoảng 9 bar", "Rửa bề mặt rồi khuếch tán"], unit_ids=["pressure", "dissolve"])])])


if __name__ == "__main__":
    # Pages and decks for the browser checks.
    from distill.renderer import render_lecture, render_page
    out = Path(".feasibility/figure-fixtures")
    source, knowledge, presentation = figure_fixture()
    for name, plan in zip(("roast", "extraction"), figure_plans()):
        render_page(source, knowledge, presentation, out / f"{name}.html", plan)
        render_lecture(source, knowledge, figure_lecture(), out / f"{name}-deck.html", plan)
    print(out.resolve())
