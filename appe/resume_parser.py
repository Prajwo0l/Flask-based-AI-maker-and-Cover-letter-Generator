import docx
import PyPDF2
import re

def extract_text_from_resume(file_path):
    try:
        if file_path.endswith('.docx'):
            return extract_text_from_docx(file_path)
        elif file_path.endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        else:
            raise ValueError("Unsupported file format. Please use PDF or DOCX.")
    except Exception as e:
        raise Exception(f"Error processing resume file: {str(e)}")

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        full_text = []
        current_section = None
        sections = {}
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
                
            # Identify section headers using common resume keywords
            if re.match(r'^(Professional Summary|Summary|Skills|Experience|Education|Projects|Certifications)\s*$', text, re.IGNORECASE):
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
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            full_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
            text = '\n'.join(full_text)
            return parse_resume_text(text)
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")

def parse_resume_text(text):
    sections = {}
    current_section = 'header'
    sections[current_section] = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines:
        # Identify section headers
        if re.match(r'^(Professional Summary|Summary|Skills|Experience|Education|Projects|Certifications)\s*$', line, re.IGNORECASE):
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

def clean_text(text):
    # Clean text while preserving structure
    text = re.sub(r'\n\s*\n+', '\n\n', text.strip())
    text = re.sub(r'\s+', ' ', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)