import os
from datetime import datetime
from io import BytesIO
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_model():
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_path = os.path.abspath("./fine_tuned_model").replace("\\", "/")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")

        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True).to(device)
        logger.info(f"Loaded model from {model_path} on {device}")
        return tokenizer, model, device, model_path
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        raise

def build_prompt(form_data):
    return (
        f"Job Title: {form_data['job_title']}\n"
        f"Hiring Company: {form_data['company']}\n"
        f"Applicant Name: {form_data['applicant_name']}\n"
        f"Working Experience: {form_data['experience']}\n"
        f"Skillsets: {form_data['skills']}\n"
        f"Cover Letter:\n"
    )

def generate_letter_body(prompt, tokenizer, model, device):
    try:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=400,
                do_sample=True,
                temperature=0.7,
                top_k=50,
                top_p=0.95,
                pad_token_id=tokenizer.eos_token_id
            )
        generated = tokenizer.decode(output[0], skip_special_tokens=True)
        letter_body = generated.split("Cover Letter:")[-1].strip() if "Cover Letter:" in generated else generated.strip()
        logger.info(f"Generated cover letter body: {letter_body[:100]}...")
        return letter_body
    except Exception as e:
        logger.error(f"Error generating letter body: {str(e)}")
        raise

def apply_template(style, letter_body, applicant_name, address, phone, email, recruiter, company, company_address, job_title):
    try:
        today_str = datetime.today().strftime("%d %B %Y")

        if style == "Minimal":
            return f"""{applicant_name.upper()}
{address} | {phone} | {email}

{today_str}

{recruiter}
{company}
{company_address}

{letter_body}"""

        elif style == "Formal":
            address_parts = address.split(',')
            city = address_parts[1].strip() if len(address_parts) > 1 else ''
            state_zip = address_parts[2].strip() if len(address_parts) > 2 else ''
            return f"""{applicant_name.upper()}{" " * 40}{city}, {state_zip}
{" " * 45}{phone} | {email}
{"-" * 60}

{today_str}

{recruiter}
{company}
{company_address}

{letter_body}"""

        elif style == "Modern":
            return f"""{applicant_name.upper()}
{job_title.upper()}

{address} | {phone} | {email}
______________________________________________________

{today_str}

{recruiter}
{company}
{company_address}

Dear {recruiter.split()[0] if recruiter else 'Hiring Manager'},

{letter_body}"""

        else:
            return letter_body  # fallback to plain body
    except Exception as e:
        logger.error(f"Error applying template: {str(e)}")
        raise

def generate_pdf(letter_content, style):
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.black)

        margin = inch
        max_width = letter[0] - 2 * margin
        y_position = letter[1] - margin

        lines = letter_content.split('\n')
        for line in lines:
            if y_position < margin:
                c.showPage()
                c.setFont("Helvetica", 12)
                y_position = letter[1] - margin
            words = line.split()
            current_line = ""
            for word in words:
                if c.stringWidth(current_line + word, "Helvetica", 12) < max_width:
                    current_line += word + " "
                else:
                    c.drawString(margin, y_position, current_line.strip())
                    y_position -= 14
                    current_line = word + " "
            if current_line:
                c.drawString(margin, y_position, current_line.strip())
                y_position -= 14

        c.save()
        buffer.seek(0)
        logger.info(f"Generated PDF for cover letter with {style} style")
        return buffer
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise