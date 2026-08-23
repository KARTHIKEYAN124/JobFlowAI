CATEGORIES={"AI":("ai engineer","artificial intelligence","llm"),"ML":("machine learning","ml engineer"),"DATA":("data engineer","data scientist","analytics"),"BACKEND":("backend","fastapi","spring boot","django"),"FRONTEND":("frontend","react","next.js"),"FULLSTACK":("full stack","fullstack"),"DEVOPS":("devops","platform engineer","kubernetes"),"CLOUD":("cloud engineer","aws","azure")}
def classify(title,description):
    text=f"{title} {description}".lower(); scores={name:sum(term in text for term in terms) for name,terms in CATEGORIES.items()}; category=max(scores,key=scores.get); score=scores[category]
    return (category if score else "SOFTWARE",min(.99,.62+score*.11))
def searchable(data): return " ".join([data.get("headline",""),*data.get("skills",[]),*data.get("preferred_roles",[]),*(str(x) for x in data.get("experience",[])),*(str(x) for x in data.get("projects",[]))]).strip()

