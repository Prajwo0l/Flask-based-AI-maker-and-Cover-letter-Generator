import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig
import pdfplumber
import re

# Load the fine-tuned TinyLlama model and tokenizer
base_model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
lora_weights_path = "C:\\Users\\lamic\\Desktop\\Ai resume builder\\tinylama-resume-lora"

# Check if CUDA is available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)

# Load base model
model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.float16
)

# Manually load LoRA adapters from local directory
try:
    config = PeftConfig.from_pretrained(lora_weights_path, local_files_only=True)
    model = PeftModel.from_pretrained(model, lora_weights_path, local_files_only=True)
except Exception as e:
    print(f"Error loading LoRA adapters: {e}")
    raise

model.to(device)
model.eval()

def generate_resume_summary(job_title, experience_years, skills, max_length=150):
    # Normalize job title by removing common adjectives
    adjectives = r'\b(Dedicated|Results-driven|Broad-based|Experienced|Accomplished|Skilled|Proficient)\b\s*'
    clean_job_title = re.sub(adjectives, '', job_title, flags=re.IGNORECASE).strip()
    prompt = f"""### Instruction:
Generate a concise professional resume summary (100-150 characters) for a {clean_job_title} with {experience_years} years of experience and expertise in {', '.join(skills)}. Focus on their skills, achievements, and commitment to excellence, without including section headers or prefixes.

### Response:
"""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
            num_return_sequences=1
        )
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    summary = generated_text[len(prompt):].strip()
    # Clean up unwanted "Response:" prefix or similar artifacts
    summary = re.sub(r'###\s*Response:?\s*', '', summary, flags=re.IGNORECASE).strip()
    # Extract only the first paragraph
    paragraphs = summary.split('\n\n')
    if paragraphs:
        summary = paragraphs[0].strip()
    else:
        summary = summary.strip()
    # Ensure skills appear in input order
    for skill in skills:
        summary = summary.replace(skill.lower(), skill)  # Preserve case of input skills
    return summary

def parse_resume(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        
        name_pattern = r"^[A-Za-z\s]+(?=\n)"
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        job_title_pattern = r"(?:Professional Experience|Work Experience)[\s\S]*?(\w+\s+\w+)"
        experience_years_pattern = r"(\d+)\s*(?:year|yrs|years)"
        skills_pattern = r"(?:Skills|Technical Skills)[\s\S]*?((?:[A-Za-z\s,]+))"

        name = re.search(name_pattern, text, re.MULTILINE)
        email = re.search(email_pattern, text)
        phone = re.search(phone_pattern, text)
        job_title = re.search(job_title_pattern, text)
        experience_years = re.search(experience_years_pattern, text)
        skills = re.search(skills_pattern, text)

        parsed_data = {
            'name': name.group(0).strip() if name else "",
            'email': email.group(0) if email else "",
            'phone': phone.group(0) if phone else "",
            'job_title': job_title.group(1).strip() if job_title else "",
            'experience_years': int(experience_years.group(1)) if experience_years else 0,
            'skills': [s.strip() for s in skills.group(1).split(',')] if skills else []
        }
        return parsed_data
    except Exception as e:
        print(f"Error parsing resume: {e}")
        return {}