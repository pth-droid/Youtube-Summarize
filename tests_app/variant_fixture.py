"""Authored decks that show every slide composition, for layout checks and visual review.

Four decks share one lecture. Their titles start the rotation at each of the four compositions, so
one-off slides (title, objectives, question, agenda, summary) appear in all four; each deck also
repeats every content kind four times. Text lengths are realistic and some are long on purpose.
"""
import hashlib
from pathlib import Path

from distill.deck_layouts import VARIANTS
from distill.models import Chapter, LectureColumn, LectureEntry, LecturePart, LecturePlan, LectureSlide
from tests_app.figure_fixture import figure_fixture

CHAPTERS = [  # id, title, section, ideas
    ("heat_paths", "Nhiệt đi vào hạt", "roasting", ["heat", "airflow", "convection"]),
    ("inside_bean", "Biến đổi bên trong hạt", "roasting", ["crack", "chemistry", "maillard"]),
    ("water_flow", "Áp suất và dòng nước", "extraction", ["pressure", "dissolve", "preinfusion"]),
    ("brew_targets", "Lỗi chiết và mục tiêu pha", "extraction", ["channel", "control_chart", "shot"]),
]


def points(title, items, ids, notes="Giải thích từng ý theo thứ tự."):
    return LectureSlide(layout="points", title=title, points=items, unit_ids=ids, notes=notes)


def steps(title, items, ids):
    return LectureSlide(layout="steps", title=title, points=items, unit_ids=ids, notes="Đi qua từng bước.")


def compare(title, left, right, ids):
    return LectureSlide(layout="compare", title=title, columns=[LectureColumn(heading=left[0], points=left[1]),
                                                                LectureColumn(heading=right[0], points=right[1])], unit_ids=ids)


def quote(title, items, ids):
    return LectureSlide(layout="quote", title=title, points=items, unit_ids=ids, notes="Đọc trích dẫn rồi giải thích.")


def entries(layout, title, rows, ids):
    return LectureSlide(layout=layout, title=title, entries=[LectureEntry(label=label, text=text) for label, text in rows], unit_ids=ids)


def columns(layout, title, cols, ids):
    return LectureSlide(layout=layout, title=title, columns=[LectureColumn(heading=head, points=points) for head, points in cols], unit_ids=ids)


PARTS = {
    "heat_paths": [
        points("Nhiệt đến hạt theo ba đường", ["Dẫn nhiệt khi hạt chạm thành trống", "Đối lưu qua dòng khí nóng", "Bức xạ từ thành trống hoặc đèn halogen"], ["heat"]),
        steps("Từ lúc nạp hạt đến điểm chuyển", ["Nạp hạt vào trống ở khoảng 200°C", "Nhiệt độ hạt tụt xuống", "Chạm điểm chuyển gần 90°C", "Hạt bắt đầu nóng lên đều"], ["heat"]),
        compare("Gió ít và gió nhiều", ("Gió ít", ["Đối lưu yếu hơn", "Ẩm và khói ở lại lâu"]), ("Gió nhiều", ["Đối lưu mạnh hơn", "Ẩm và khói ra nhanh"]), ["airflow", "convection"]),
        quote("Gió làm hai việc cùng lúc", ["Gió vừa truyền nhiệt vừa làm sạch trống", "Chỉnh gió là chỉnh cả hai"], ["airflow"]),
        columns("columns", "Ba đường truyền nhiệt", [("Dẫn nhiệt", ["Hạt chạm thành trống nóng"]), ("Đối lưu", ["Khí nóng thổi qua khối hạt"]),
                                                     ("Bức xạ", ["Thành trống hoặc đèn halogen tỏa nhiệt"])], ["heat"]),
        points("Những gì cần theo dõi khi tăng gió", ["Tốc độ tăng nhiệt có thể tăng", "Khói thoát nhanh hơn", "Hạt khô nhanh hơn ở đầu mẻ", "Nhiệt độ khí thải thay đổi",
                                                   "Cần ghi lại để so sánh giữa các mẻ"], ["airflow", "convection"]),
    ],
    "inside_bean": [
        points("Áp suất trong hạt dẫn đến nứt lần 1", ["Hơi nước và CO₂ tích tụ bên trong hạt", "Thành tế bào nứt khi áp suất đủ lớn, gần 196°C ở khoảng phút thứ 9 của mẻ rang"], ["crack"]),
        steps("Ba pha của một mẻ rang", ["Sấy: độ ẩm giảm từ khoảng 11% xuống gần 2%", "Maillard: hạt chuyển vàng ở khoảng 150°C", "Phát triển: sau nứt lần 1, ra lò ở khoảng 210°C"], ["maillard", "crack"]),
        compare("Hợp chất mất đi và sinh ra", ("Mất đi", ["Sucrose phân hủy", "Axit chlorogenic suy giảm", "Độ ẩm giảm mạnh"]),
                ("Sinh ra", ["Melanoidin màu nâu", "CO₂ tích tụ trong hạt", "Hương thơm mới"]), ["chemistry"]),
        quote("Nứt lần 1 là một mốc dễ nghe thấy", ["Người rang dùng mốc này để tính thời gian phát triển"], ["crack"]),
        entries("timeline", "Các mốc của một mẻ rang", [("1:30", "Điểm chuyển gần 90°C"), ("4:30", "Hạt vàng, Maillard bắt đầu"),
                                                         ("9:00", "Nứt lần 1 gần 196°C"), ("11:00", "Ra lò ở khoảng 210°C")], ["maillard", "crack"]),
        entries("pyramid", "Hương vị dựng trên các phản ứng", [("Hương thơm", "Phần người uống nhận ra đầu tiên"), ("Melanoidin", "Màu nâu và vị đậm"),
                                                                ("Maillard", "Đường và axit amin phản ứng"), ("Nhiệt đều", "Nền móng của mọi biến đổi")], ["maillard", "chemistry"]),
    ],
    "water_flow": [
        points("Áp suất đẩy nước qua bánh cà phê", ["Bơm tạo khoảng 9 bar", "Nước nóng đi qua bánh cà phê đã nén", "Bánh cà phê cản dòng chảy và tạo thời gian tiếp xúc",
                                                  "Ngâm trước làm ướt bánh ở áp suất thấp khoảng 8 giây"], ["pressure", "preinfusion"]),
        steps("Nước hòa tan chất tan theo hai giai đoạn, rồi dòng chảy ổn định dần khi bánh cà phê đã ướt đều",
              ["Ngâm trước làm ướt đều bánh cà phê ở áp suất thấp trong khoảng tám giây đầu tiên", "Bơm đưa áp suất lên khoảng 9 bar và giữ ổn định trong suốt phần còn lại của shot",
               "Nước rửa chất tan trên bề mặt hạt bột trước", "Sau đó hòa tan chậm hơn từ bên trong hạt bột", "Dòng chảy ổn định cho đến khi đạt khối lượng mục tiêu"], ["dissolve", "preinfusion"]),
        compare("Ngâm trước và vào áp ngay", ("Có ngâm trước", ["Bánh ướt đều trước khi chịu áp", "Ít nguy cơ nước tìm kênh"]),
                ("Vào áp ngay", ["Bánh chịu áp khi còn khô một phần", "Dễ có điểm chảy nhanh hơn"]), ["preinfusion", "pressure"]),
        quote("Bề mặt trước, bên trong sau", ["Hai tốc độ hòa tan giải thích vì sao vị thay đổi trong suốt shot", "Phần đầu shot đậm hơn phần cuối"], ["dissolve"]),
        entries("funnel", "Từ bột đến ly", [("Bột cà phê", "Toàn bộ chất có thể hòa tan"), ("Bề mặt hạt", "Rửa trôi trước, rất nhanh"),
                                             ("Bên trong hạt", "Khuếch tán chậm hơn"), ("Ly espresso", "Phần chất tan được giữ lại")], ["dissolve"]),
        entries("stats", "Hai con số của máy pha", [("9 bar", "Áp suất bơm đẩy nước qua bánh cà phê"), ("8 giây", "Ngâm trước ở áp suất thấp")], ["pressure", "preinfusion"]),
    ],
    "brew_targets": [
        points("Một shot tham chiếu", ["Khoảng 36 g trong khoảng 28 giây", "Hiệu suất chiết mục tiêu 18–22%"], ["shot", "control_chart"]),
        steps("Kiểm tra một shot", ["Cân bột", "Bấm giờ", "Cân shot", "Nếm và ghi lại"], ["shot"]),
        compare("Chiết thiếu và chiết đúng", ("Chiết thiếu", ["Nước xuyên kênh", "Phần lớn bột ít được chiết", "Vị chua và mỏng"]),
                ("Chiết đúng", ["Nước đi đều qua bánh", "Hiệu suất trong khoảng 18–22%", "Vị cân bằng hơn"]), ["channel", "control_chart"]),
        quote("Kênh nước làm hỏng cả shot", ["Một vết nứt nhỏ đủ để nước đi tắt", "Phân bố bột và nén đều giúp tránh kênh"], ["channel"]),
        columns("table", "Ba kết quả chiết", [("Kết quả", ["Chiết thiếu", "Chiết đúng", "Chiết quá"]), ("Dòng nước", ["Đi tắt qua kênh", "Đều qua bánh", "Quá chậm"]),
                                               ("Vị", ["Chua, mỏng", "Cân bằng", "Đắng, khô"])], ["channel", "control_chart"]),
        entries("stats", "Một shot tham chiếu", [("36 g", "Khối lượng shot"), ("28 giây", "Thời gian chảy"), ("18–22%", "Hiệu suất chiết mục tiêu")], ["shot", "control_chart"]),
    ],
}

TITLES = ["Rang và chiết xuất cà phê: nhiệt, gió và áp suất", "Nhiệt, gió và áp suất trong một tách cà phê", "Từ hạt xanh đến shot espresso",
          "Hiểu rang và chiết xuất qua bốn câu hỏi", "Cà phê từ trống rang đến tay pha", "Một mẻ rang và một shot espresso",
          "Bốn phần về rang và pha cà phê", "Rang, nứt hạt và dòng nước qua bánh cà phê"]


def start(title):
    """The renderer's rotation start for a deck title."""
    return int(hashlib.sha256(title.encode("utf-8")).hexdigest()[:8], 16) % len(VARIANTS)


def variant_fixture():
    source, knowledge, _ = figure_fixture()
    knowledge = knowledge.model_copy(update={"chapters": [
        Chapter(id=cid, title=title, section_ids=[section], unit_ids=ids, depth="expert", detail="detailed") for cid, title, section, ids in CHAPTERS]})
    parts = [LecturePart(chapter_id=cid, slides=PARTS[cid]) for cid, *_rest in CHAPTERS]
    decks = {}
    for title in TITLES:  # one title for each rotation start
        decks.setdefault(start(title), title)
    assert len(decks) == len(VARIANTS), "add a title that starts the rotation elsewhere"
    lectures = {first: LecturePlan(title=title, objectives=["Giải thích ba đường truyền nhiệt vào hạt.", "Mô tả các pha của một mẻ rang.", "Nhận ra dấu hiệu chiết thiếu."],
                                   takeaways=["Nhiệt và gió điều khiển các pha rang.", "Áp suất đẩy nước qua bánh cà phê.", "Kênh nước làm shot chiết thiếu."], parts=parts)
                for first, title in sorted(decks.items())}
    return source, knowledge, lectures


if __name__ == "__main__":
    from distill.renderer import render_lecture
    out = Path(".feasibility/variant-fixtures")
    source, knowledge, lectures = variant_fixture()
    for first, lecture in lectures.items():
        for theme in ("forest", "maroon"):
            render_lecture(source, knowledge, lecture, out / f"gallery-{first}-{theme}.html", theme=theme)
    print(out.resolve())
