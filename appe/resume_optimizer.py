import re

def optimize_resume_text(resume_sections, missing_skills, missing_keywords):
    """
    Generate an optimized resume by suggesting missing skills and keywords.
    Args:
        resume_sections (dict): Parsed resume sections from resume_parser.parse_resume_text.
        missing_skills (list): List of missing skills from skill_analyzer.find_skill_gaps.
        missing_keywords (list): List of missing keywords from skill_analyzer.find_skill_gaps.
    Returns:
        tuple: (optimized_text, suggestions) where optimized_text is the resume with suggested insertions,
               and suggestions is a list of applied changes.
    """
    optimized_sections = resume_sections.copy()
    suggestions = []

    # Suggest adding missing skills to the 'skills' section
    if 'skills' in optimized_sections and missing_skills:
        skill_suggestion = f"[SUGGESTED: Add skills - {', '.join(missing_skills[:3])}]"
        optimized_sections['skills'].append(skill_suggestion)
        suggestions.append(f"Added suggested skills ({', '.join(missing_skills[:3])}) to Skills section.")

    # Suggest adding missing keywords to 'professional summary' or 'header'
    if ('professional summary' in optimized_sections or 'header' in optimized_sections) and missing_keywords:
        target_section = 'professional summary' if 'professional summary' in optimized_sections else 'header'
        keyword_suggestion = f"[SUGGESTED: Add keywords - {', '.join(missing_keywords[:3])}]"
        optimized_sections[target_section].append(keyword_suggestion)
        suggestions.append(f"Added suggested keywords ({', '.join(missing_keywords[:3])}) to {target_section.title()} section.")

    # Format the optimized resume with suggestions
    formatted = []
    for section, content in optimized_sections.items():
        if content:
            formatted.append(f"{section.title()}\n{'-' * len(section)}\n")
            for line in content:
                if line.startswith("[SUGGESTED:"):
                    formatted.append(f"<span class='suggestion'>{line}</span>")
                else:
                    formatted.append(line)
            formatted.append("\n")
    optimized_text = '\n'.join(formatted).strip()
    return optimized_text, suggestions