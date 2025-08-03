import spacy
from transformers import BertTokenizer, BertModel
import torch
import pdfplumber
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Set, Any
from fuzzywuzzy import fuzz
import logging
from functools import lru_cache
import os
import json
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_skill_set(skill_db_path: str = "skill_db_relax_20.json") -> Dict[str, Dict[str, Any]]:
    """Load skill set from JSON with caching."""
    try:
        with open(skill_db_path, 'r') as f:
            skill_set = json.load(f)
            logger.info(f"Loaded skill set from {skill_db_path} with {len(skill_set)} skills")
            return skill_set
    except FileNotFoundError:
        logger.error(f"Skill database {skill_db_path} not found")
        raise
    except Exception as e:
        logger.error(f"Error loading {skill_db_path}: {e}")
        raise

@lru_cache(maxsize=1)
def load_spacy_model() -> spacy.language.Language:
    """Load spaCy model with caching."""
    try:
        return spacy.load("en_core_web_lg")  # Use smaller model for faster loading
    except Exception as e:
        logger.error(f"Failed to load spaCy model: {e}")
        raise

@lru_cache(maxsize=1)
def load_bert_model():
    """Load BERT tokenizer and model with caching."""
    try:
        tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        model = BertModel.from_pretrained('bert-base-uncased').eval()  # Set model to evaluation mode
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        return tokenizer, model, device
    except Exception as e:
        logger.error(f"Failed to load BERT model: {e}")
        raise

def get_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF, using OCR for scanned documents if needed."""
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return ""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        text = re.sub(r'\n\s*\n+', '\n', text).strip()
        if not text:
            logger.warning(f"No text extracted from {pdf_path}, attempting OCR.")
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Increase resolution for OCR
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img, config='--psm 6').strip()
                    text += ocr_text + "\n"
        logger.info(f"Extracted PDF text: {text[:100]}...")
        return text
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}")
        return ""

def get_bert_embeddings(text: str, tokenizer, model, device) -> np.ndarray:
    """Generate BERT embeddings for text."""
    try:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()
    except Exception as e:
        logger.error(f"Error generating BERT embeddings: {e}")
        return np.array([])

def calculate_skill_similarity(resume_text: str, jd_text: str, resume_skills: List[str], jd_skills: List[str], skill_db_path: str = "skill_db_relax_20.json") -> tuple[Set[str], List[str], float]:
    """Calculate skill match score using BERT embeddings."""
    try:
        tokenizer, model, device = load_bert_model()
        nlp = load_spacy_model()
        skill_set = load_skill_set(skill_db_path)

        # Normalize skills
        all_resume_skills = {skill.lower().strip() for skill in resume_skills}
        all_jd_skills = {skill.lower().strip() for skill in jd_skills}

        # Cache for embeddings to avoid recomputation
        skill_embeddings = {}

        # Expand skills with synonyms
        for skill in list(all_jd_skills):
            for skill_data in skill_set.values():
                skill_name = skill_data["skill_name"].lower().strip()
                low_surface_forms = [s.lower().strip() for s in skill_data.get("low_surface_forms", [])]
                if skill == skill_name or skill in low_surface_forms:
                    all_jd_skills.update(low_surface_forms)
                    all_jd_skills.add(skill_name)
        for skill in list(all_resume_skills):
            for skill_data in skill_set.values():
                skill_name = skill_data["skill_name"].lower().strip()
                low_surface_forms = [s.lower().strip() for s in skill_data.get("low_surface_forms", [])]
                if skill == skill_name or skill in low_surface_forms:
                    all_resume_skills.update(low_surface_forms)
                    all_resume_skills.add(skill_name)

        # Generate embeddings for all skills once
        for skill in all_resume_skills | all_jd_skills:
            if skill not in skill_embeddings:
                skill_embeddings[skill] = get_bert_embeddings(skill, tokenizer, model, device)

        # Calculate similarity for skill sets
        resume_emb = np.mean([skill_embeddings[skill] for skill in all_resume_skills if skill in skill_embeddings], axis=0) if all_resume_skills else np.array([])
        jd_emb = np.mean([skill_embeddings[skill] for skill in all_jd_skills if skill in skill_embeddings], axis=0) if all_jd_skills else np.array([])
        if resume_emb.size == 0 or jd_emb.size == 0:
            logger.warning("Empty embeddings generated for skills.")
            return set(), list(all_jd_skills), 0.0

        similarity = cosine_similarity(resume_emb.reshape(1, -1), jd_emb.reshape(1, -1))[0][0]
        threshold = 0.80
        matched_skills = set()

        # Optimize skill matching
        for skill in all_resume_skills:
            for jd_skill in all_jd_skills:
                for skill_data in skill_set.values():
                    skill_name = skill_data["skill_name"].lower().strip()
                    if skill == skill_name or jd_skill == skill_name:
                        if skill_data.get("match_on_tokens", False):
                            if fuzz.token_sort_ratio(skill, jd_skill) > 90:
                                matched_skills.add(skill)
                        elif (fuzz.token_sort_ratio(skill, jd_skill) > 90 or
                              cosine_similarity(
                                  skill_embeddings[skill].reshape(1, -1),
                                  skill_embeddings[jd_skill].reshape(1, -1)
                              )[0][0] > threshold):
                            matched_skills.add(skill)

        missing_skills = list(all_jd_skills - matched_skills)
        skill_score = min(len(matched_skills) / len(all_jd_skills) * 100, 100) if all_jd_skills else 0.0

        logger.info(f"Matched skills: {matched_skills}, Missing skills: {missing_skills}, Skill score: {skill_score}")
        return matched_skills, missing_skills, skill_score
    except Exception as e:
        logger.error(f"Error in skill similarity calculation: {e}")
        return set(), list(all_jd_skills) if jd_skills else [], 0.0

def parse_experience_dates(text: str) -> List[tuple[int, int]]:
    """Parse experience date ranges from text."""
    dates = []
    date_pattern = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\s*\d{1,2}[-/]\d{2,4}|\d{4}[-–]\d{4}'
    for match in re.finditer(date_pattern, text.lower()):
        try:
            date_str = match.group().replace("–", "-")
            parts = re.split(r'[-/]', date_str)
            if len(parts) == 2:
                start_year = int(parts[0][-4:])
                end_year = int(parts[1][-4:])
                if start_year <= end_year <= 2025:
                    dates.append((start_year, end_year))
        except ValueError:
            continue
    logger.info(f"Parsed dates: {dates}")
    return dates

def calculate_experience_score(resume_text: str, jd_text: str) -> float:
    """Score experience based on date overlap and role similarity."""
    try:
        tokenizer, model, device = load_bert_model()
        resume_dates = parse_experience_dates(resume_text)
        jd_dates = parse_experience_dates(jd_text)

        overlap = any(res_end >= jd_start and res_start <= jd_end
                      for res_start, res_end in resume_dates
                      for jd_start, jd_end in jd_dates)
        resume_summary = " ".join(resume_text.split("\n")[:5])
        jd_summary = " ".join(jd_text.split("\n")[:5])
        resume_emb = get_bert_embeddings(resume_summary, tokenizer, model, device)
        jd_emb = get_bert_embeddings(jd_summary, tokenizer, model, device)
        role_sim = cosine_similarity(resume_emb.reshape(1, -1), jd_emb.reshape(1, -1))[0][0]
        score = 100 if overlap and role_sim > 0.7 else (70 if overlap or role_sim > 0.7 else 40)
        logger.info(f"Experience overlap: {overlap}, Role similarity: {role_sim}, Experience score: {score}")
        return min(score, 100)
    except Exception as e:
        logger.error(f"Error in experience score calculation: {e}")
        return 0.0

def detect_sections(resume_text: str) -> tuple[Dict[str, int], float]:
    """Detect resume sections and compute normalized score."""
    try:
        nlp = load_spacy_model()
        sections = {"skills": 0, "experience": 0, "education": 0, "certifications": 0}
        weights = {"skills": 40, "experience": 30, "education": 20, "certifications": 10}
        lines = resume_text.split("\n")
        expected_order = ["skills", "experience", "education", "certifications"]
        order_score = 0
        current_section_index = -1

        for line in lines:
            line = re.sub(r'\s+', ' ', line.lower()).strip()
            if not line:
                continue
            doc = nlp(line)
            for section, weight in weights.items():
                if sections[section] == 0 and (
                    any(fuzz.partial_ratio(section, token.text) > 85 for token in doc) or
                    section in line or
                    re.match(r'^-{3,}$', line)
                ):
                    sections[section] = weight
                    if current_section_index + 1 < len(expected_order) and section == expected_order[current_section_index + 1]:
                        order_score += 10
                        current_section_index += 1

        section_score = min(sum(sections.values()) + min(order_score, 30), 100)
        missing_sections = [s for s, w in weights.items() if sections.get(s, 0) == 0]
        logger.info(f"Detected sections: {sections}, Section score: {section_score}, Missing sections: {missing_sections}")
        return sections, section_score
    except Exception as e:
        logger.error(f"Error in section detection: {e}")
        return sections, 0.0

def analyze_formatting(pdf_path: str) -> tuple[float, List[str]]:
    """Analyze PDF formatting for ATS compatibility."""
    try:
        formatting_score = 100.0
        issues = []
        with pdfplumber.open(pdf_path) as pdf:
            fonts = set()
            font_sizes = []
            has_tables = False
            has_images = False
            for page in pdf.pages:
                if page.chars:
                    fonts.update(char["fontname"].lower() for char in page.chars)
                    font_sizes.extend(char["size"] for char in page.chars)
                if page.extract_tables():
                    has_tables = True
                if page.images:
                    has_images = True
            ats_fonts = ["timesnewroman", "arial", "helvetica", "calibri"]
            if not any(f in font.lower() for font in ats_fonts for f in fonts):
                formatting_score -= 30
                issues.append("Use ATS-friendly fonts: Times New Roman, Arial, Helvetica, or Calibri.")
            avg_font_size = np.mean(font_sizes) if font_sizes else 11
            if not (10 <= avg_font_size <= 12):
                formatting_score -= 20
                issues.append("Maintain font sizes between 10–12pt.")
            if has_tables:
                formatting_score -= 20
                issues.append("Remove tables for ATS compatibility.")
            if has_images:
                formatting_score -= 20
                issues.append("Avoid images in resumes.")
            margin = pdf.pages[0].width / 72 if pdf.pages else 1.0
            if not (0.8 <= margin <= 1.2):
                formatting_score -= 10
                issues.append("Use 1-inch margins.")
        with fitz.open(pdf_path) as doc:
            if all(not page.get_text("text") for page in doc):
                formatting_score -= 30
                issues.append("Detected scanned PDF. Convert to text-based PDF.")
        logger.info(f"Formatting score: {formatting_score}, Issues: {issues}")
        return min(formatting_score, 100), issues
    except Exception as e:
        logger.error(f"Formatting analysis failed for {pdf_path}: {e}")
        return 0.0, ["Could not analyze formatting due to file error."]

def calculate_keyword_density(resume_text: str, jd_text: str) -> tuple[float, List[str]]:
    """Calculate keyword density score."""
    try:
        tokenizer, model, device = load_bert_model()
        resume_emb = get_bert_embeddings(resume_text, tokenizer, model, device)
        jd_emb = get_bert_embeddings(jd_text, tokenizer, model, device)
        similarity = cosine_similarity(resume_emb.reshape(1, -1), jd_emb.reshape(1, -1))[0][0]

        resume_text_norm = re.sub(r'\s+', ' ', resume_text.lower()).strip()
        jd_text_norm = re.sub(r'\s+', ' ', jd_text.lower()).strip()
        jd_phrases = re.findall(r'\b(?:\w+\s+\w+|\w{4,})\b', jd_text_norm)
        keyword_count = Counter(jd_phrases)
        total_words = len(resume_text_norm.split())
        resume_phrases = set(re.findall(r'\b(?:\w+\s+\w+|\w{4,})\b', resume_text_norm))

        density = sum(count for phrase, count in keyword_count.items() if phrase in resume_phrases) / total_words * 100 if total_words else 0
        density_score = 100 if 0.5 <= density <= 1.5 else (60 if density < 0.5 else 30)
        missing = [phrase for phrase, count in keyword_count.items() if count > 1 and phrase not in resume_phrases][:5]
        logger.info(f"Density score: {density_score}, Missing keywords: {missing}")
        return min(density_score, 100), missing
    except Exception as e:
        logger.error(f"Error in keyword density calculation: {e}")
        return 0.0, []

def calculate_file_format_score(pdf_path: str) -> tuple[float, List[str]]:
    """Score file format for ATS compatibility."""
    try:
        score = 100.0
        issues = []
        if pdf_path.endswith('.pdf'):
            with pdfplumber.open(pdf_path) as pdf:
                version = float(pdf.metadata.get('PDFVersion', '1.4'))
                if not (1.4 <= version <= 1.7):
                    score -= 20
                    issues.append("Use PDF version 1.4–1.7.")
                encoding = pdf.metadata.get('Encoding', 'UTF-8')
                if encoding not in ['UTF-8', 'ASCII']:
                    score -= 20
                    issues.append("Use UTF-8 or ASCII encoding.")
        elif pdf_path.endswith('.docx'):
            score = 80
            issues.append("PDF is preferred over DOCX for ATS.")
        else:
            score = 20
            issues.append("Use PDF or DOCX format.")
        logger.info(f"File format score: {score}, Issues: {issues}")
        return min(score, 100), issues
    except Exception as e:
        logger.error(f"Error in file format scoring: {e}")
        return 0.0, ["Could not verify file format."]

def calculate_ats_score(resume_text: str, jd_text: str, resume_skills: List[str], jd_skills: List[str], resume_pdf_path: str, jd_title: str, skill_db_path: str = "skill_db_relax_20.json") -> Dict[str, Any]:
    """Calculate ATS score with normalized components."""
    logger.info(f"Scoring resume from {resume_pdf_path} against job title '{jd_title}'")

    if not resume_text.strip() or not jd_text.strip():
        return {
            "total_score": 0.0,
            "skill_match_score": 0.0,
            "experience_score": 0.0,
            "section_score": 0.0,
            "formatting_score": 0.0,
            "job_title_score": 0.0,
            "keyword_density_score": 0.0,
            "file_format_score": 0.0,
            "matched_keywords": [],
            "missing_keywords": [],
            "matched_skills": [],
            "missing_skills": [],
            "recommendations": ["Ensure both resume and job description contain valid text."]
        }

    if not resume_text:
        resume_text = get_text_from_pdf(resume_pdf_path)
        if not resume_text:
            return {
                "total_score": 0.0,
                "skill_match_score": 0.0,
                "experience_score": 0.0,
                "section_score": 0.0,
                "formatting_score": 0.0,
                "job_title_score": 0.0,
                "keyword_density_score": 0.0,
                "file_format_score": 0.0,
                "matched_keywords": [],
                "missing_keywords": [],
                "matched_skills": [],
                "missing_skills": [],
                "recommendations": ["Failed to extract text from resume PDF."]
            }

    # Calculate scores
    matched_skills, missing_skills, skill_match_score = calculate_skill_similarity(resume_text, jd_text, resume_skills, jd_skills, skill_db_path)
    experience_score = calculate_experience_score(resume_text, jd_text)
    sections, section_score = detect_sections(resume_text)
    formatting_score, formatting_issues = analyze_formatting(resume_pdf_path)
    keyword_density_score, missing_keywords = calculate_keyword_density(resume_text, jd_text)
    file_format_score, file_format_issues = calculate_file_format_score(resume_pdf_path)

    # Job title score
    try:
        tokenizer, model, device = load_bert_model()
        resume_summary = " ".join(resume_text.split("\n")[:5])
        job_title_score = cosine_similarity(
            get_bert_embeddings(resume_summary, tokenizer, model, device).reshape(1, -1),
            get_bert_embeddings(jd_title.lower(), tokenizer, model, device).reshape(1, -1)
        )[0][0] * 100
        job_title_score = min(job_title_score, 100)
    except Exception as e:
        logger.error(f"Error in job title score calculation: {e}")
        job_title_score = 0.0

    # Calculate total score
    total_score = (
        0.35 * skill_match_score +
        0.25 * experience_score +
        0.15 * section_score +
        0.10 * formatting_score +
        0.10 * job_title_score +
        0.05 * keyword_density_score +
        0.05 * file_format_score
    )

    # Generate recommendations
    recommendations = []
    if skill_match_score < 80:
        recommendations.append(f"Add missing skills: {', '.join(missing_skills[:5])}. Consider online courses.")
    if experience_score < 70:
        recommendations.append("Enhance experience section with overlapping dates and relevant roles.")
    if section_score < 70:
        missing_sections = [s for s in ["skills", "experience", "education"] if sections.get(s, 0) == 0]
        if missing_sections:
            recommendations.append(f"Add missing sections: {', '.join(missing_sections)}.")
        else:
            recommendations.append("Ensure section headers (Skills, Experience, Education) are clearly labeled.")
    recommendations.extend(formatting_issues)
    if job_title_score < 70:
        recommendations.append(f"Include '{jd_title}' in your summary or title.")
    if keyword_density_score < 70:
        recommendations.append(f"Optimize keywords: {', '.join(missing_keywords)} to 0.5–1.5% density.")
    recommendations.extend(file_format_issues)

    logger.info(f"Final ATS results: total_score={total_score:.2f}, skill_match_score={skill_match_score:.2f}, "
                f"experience_score={experience_score:.2f}, section_score={section_score:.2f}, "
                f"formatting_score={formatting_score:.2f}, job_title_score={job_title_score:.2f}, "
                f"keyword_density_score={keyword_density_score:.2f}, file_format_score={file_format_score:.2f}")

    return {
        "total_score": round(min(total_score, 100), 2),
        "skill_match_score": round(skill_match_score, 2),
        "experience_score": round(experience_score, 2),
        "section_score": round(section_score, 2),
        "formatting_score": round(formatting_score, 2),
        "job_title_score": round(job_title_score, 2),
        "keyword_density_score": round(keyword_density_score, 2),
        "file_format_score": round(file_format_score, 2),
        "matched_keywords": list(set(re.findall(r'\b(?:\w+\s+\w+|\w{4,})\b', jd_text.lower())) &
                                set(re.findall(r'\b(?:\w+\s+\w+|\w{4,})\b', resume_text.lower())))[:10],
        "matched_skills": list(matched_skills),
        "missing_skills": missing_skills,
        "recommendations": recommendations
    }