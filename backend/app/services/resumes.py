import re

KNOWN_SKILLS = (
    "Java",
    "Spring Boot",
    "Python",
    "FastAPI",
    "React",
    "Next.js",
    "TypeScript",
    "PostgreSQL",
    "Docker",
    "AWS",
    "Kafka",
    "Kubernetes",
    "Terraform",
    "RAG",
)


def extract_resume(text: str) -> dict:
    lower = text.lower()
    skills = [skill for skill in KNOWN_SKILLS if skill.lower() in lower]
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    return {
        "name": next((line.strip() for line in text.splitlines() if line.strip()), ""),
        "email": email.group(0) if email else "",
        "education": [],
        "experience": [],
        "skills": skills,
        "projects": [],
        "languages": [],
    }
