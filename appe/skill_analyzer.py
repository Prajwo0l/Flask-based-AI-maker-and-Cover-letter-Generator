import json
import re

# Load skill DB once
with open('skill_db_relax_20.json', 'r', encoding='utf-8') as f:
    SKILL_DB = json.load(f)

def preprocess_text(text):
    # Lowercase and normalize whitespace
    return re.sub(r'\s+', ' ', text.lower().strip())

def extract_skills(text, skill_db):
    text = preprocess_text(text)
    found_skills = set()

    for skill_id, skill_info in skill_db.items():
        # Exact phrase matching using word boundaries to avoid partial hits
        skill_name = skill_info['skill_name'].lower()
        pattern = r'\b' + re.escape(skill_name) + r'\b'
        if re.search(pattern, text):
            found_skills.add(skill_info['skill_name'])
            continue

        # Try low surface forms (alternate phrasings)
        for alt_form in skill_info.get('low_surface_forms', []):
            alt_pattern = r'\b' + re.escape(alt_form) + r'\b'
            if re.search(alt_pattern, text):
                found_skills.add(skill_info['skill_name'])
                break

    return found_skills

def find_skill_gaps(resume_text, jd_text):
    resume_skills = extract_skills(resume_text, SKILL_DB)
    jd_skills = extract_skills(jd_text, SKILL_DB)

    missing_skills = jd_skills - resume_skills
    matched_skills = resume_skills & jd_skills

    return {
        'missing_skills': sorted(missing_skills),
        'matched_skills': sorted(matched_skills),
        'all_resume_skills': sorted(resume_skills),
        'all_jd_skills': sorted(jd_skills)
    }
