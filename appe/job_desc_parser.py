from docx import Document
import PyPDF2
import re

def extract_text_from_job_desc(file_path):
    try:
        if file_path.endswith('.docx'):
            return extract_text_from_docx(file_path)
        elif file_path.endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        elif file_path.endswith('.txt'):
            return extract_text_from_txt(file_path)
        else:
            raise ValueError("Unsupported file format. Please use PDF, DOCX, or TXT.")
    except Exception as e:
        raise Exception(f"Error processing job description file: {str(e)}")

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        full_text = []
        current_section = None
        sections = {}
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
                
            # Identify section headers using common JD keywords
            if re.match(r'^(Job Title|Description|Responsibilities|Requirements|Qualifications|Skills|Benefits)\s*$', text, re.IGNORECASE):
                current_section = text.lower()
                sections[current_section] = []
            elif current_section:
                sections[current_section].append(text)
            else:
                sections['header'] = sections.get('header', []) + [text]
                
        return format_sections(sections)
    except Exception as e:
        raise Exception(f"Error reading DOCX: {str(e)}")

def extract_text_from_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            full_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
            text = '\n'.join(full_text)
            return parse_jd_text(text)
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")

def extract_text_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
            return parse_jd_text(text)
    except Exception as e:
        raise Exception(f"Error reading TXT: {str(e)}")

def parse_jd_text(text):
    sections = {}
    current_section = 'header'
    sections[current_section] = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines:
        # Identify section headers
        if re.match(r'^(Job Title|Description|Responsibilities|Requirements|Qualifications|Skills|Benefits)\s*$', line, re.IGNORECASE):
            current_section = line.lower()
            sections[current_section] = []
        else:
            sections[current_section].append(line)
    
    return format_sections(sections)

def format_sections(sections):
    # Format sections into a structured string
    formatted = []
    for section, content in sections.items():
        if content:
            formatted.append(f"{section.title()}\n{'-' * len(section)}\n")
            formatted.extend(content)
            formatted.append("\n")
    return '\n'.join(formatted).strip()