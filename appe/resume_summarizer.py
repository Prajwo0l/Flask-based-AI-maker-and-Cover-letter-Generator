import re
from collections import Counter

def generate_section_summaries(resume_sections, jd_text, matched_skills, jd_skills):
    """
    Generate concise, ATS-friendly summaries for each resume section.
    Args:
        resume_sections (dict): Parsed resume sections from resume_parser.parse_resume_text.
        jd_text (str): Job description text.
        matched_skills (list): Matched skills from skill_analyzer.find_skill_gaps.
        jd_skills (list): Job description skills from skill_analyzer.find_skill_gaps.
    Returns:
        dict: Dictionary with section names as keys and summary strings as values.
    """
    summaries = {}
    
    # Skills section summary
    if 'skills' in resume_sections:
        skills = matched_skills[:5] if matched_skills else resume_sections['skills'][:5]
        if skills:
            summaries['skills'] = f"Proficient in {', '.join(skills)} with expertise aligned to job requirements."
        else:
            summaries['skills'] = "No specific skills identified."

    # Experience section summary
    if 'experience' in resume_sections or 'professional experience' in resume_sections:
        section_key = 'experience' if 'experience' in resume_sections else 'professional experience'
        experience_text = '\n'.join(resume_sections[section_key])
        # Parse years of experience
        date_pattern = r'\d{4}[-–]\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*[-–]\s*(?:Present|\d{4})'
        dates = re.findall(date_pattern, experience_text.lower())
        total_years = 0
        for date in dates:
            try:
                start, end = re.split(r'[-–]', date)
                start_year = int(start[-4:]) if start[-4:].isdigit() else int(start[:4])
                end_year = int(end[-4:]) if end[-4:].isdigit() else 2025
                total_years += end_year - start_year
            except:
                continue
        # Extract key roles from job description
        jd_phrases = re.findall(r'\b(?:\w+\s+\w+|\w{4,})\b', jd_text.lower())
        role_keywords = [phrase for phrase in jd_phrases if phrase in experience_text.lower()][:2]
        role_text = f"focusing on {', '.join(role_keywords)}" if role_keywords else "in relevant roles"
        summaries[section_key] = f"{total_years}+ years of professional experience {role_text}."

    # Education section summary
    if 'education' in resume_sections:
        education = resume_sections['education'][:1]
        if education:
            summaries['education'] = f"Education: {education[0]}."
        else:
            summaries['education'] = "No education details provided."

    # Certifications section summary
    if 'certifications' in resume_sections:
        certs = resume_sections['certifications'][:2]
        if certs:
            summaries['certifications'] = f"Certified in {', '.join(certs)}."
        else:
            summaries['certifications'] = "No certifications listed."

    # Professional Summary (if present or as a new suggestion)
    if 'professional summary' in resume_sections or matched_skills or jd_skills:
        summary_skills = matched_skills[:3] if matched_skills else jd_skills[:3]
        summary_text = f"Skilled professional with expertise in {', '.join(summary_skills)}."
        summaries['professional summary'] = summary_text

    return summaries