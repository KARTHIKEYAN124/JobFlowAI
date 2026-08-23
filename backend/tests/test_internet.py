from app.services.internet import plain_text


def test_plain_text_decodes_and_removes_job_feed_markup():
    assert plain_text("&lt;p&gt;Python &amp;amp; FastAPI&lt;/p&gt;") == "Python & FastAPI"
