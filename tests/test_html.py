from paper.html import render_html
from paper.models import Edition


def test_html_contains_content_and_escapes():
    ed = Edition(
        date="2026-07-01",
        headline="Big <script> day",
        lead="Lead text",
        yesterday=[{"project": "x-lens", "story": "Built <b>things</b>."}],
        open_loops=["loop one"],
        tech_wire=[{"title": "Show HN", "meta": "412 pts", "why": "", "url": ""}],
        actions=["Do it"],
        weather="72°F clear · Seattle",
    )
    html = render_html(ed, masthead="THE TEST TIMES")
    assert "THE TEST TIMES" in html
    assert "Big &lt;script&gt; day" in html
    assert "Built &lt;b&gt;things&lt;/b&gt;." in html
    assert "Wednesday, July 1, 2026" in html
    assert "412 pts" in html
    assert "Today's top three" in html
