from app.services.jobs import classify, searchable


def test_rules_before_llm(): category,confidence=classify("Werkstudent Backend","FastAPI PostgreSQL APIs"); assert category=="BACKEND" and confidence>.7
def test_searchable_profile(): assert "Python" in searchable({"headline":"Engineer","skills":["Python"],"preferred_roles":["AI Engineer"],"experience":[],"projects":[]})

