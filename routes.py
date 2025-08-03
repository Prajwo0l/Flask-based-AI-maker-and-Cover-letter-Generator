from flask import Blueprint, render_template, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import re
import logging
import torch
from appe.resume_parser import extract_text_from_resume, parse_resume_text
from appe.job_desc_parser import extract_text_from_job_desc
from appe.skill_analyzer import find_skill_gaps
from appe.ats_scorer import calculate_ats_score
from appe.resume_summarizer import generate_section_summaries
from appe.cover_letter_generator import load_model, build_prompt, generate_letter_body, apply_template, generate_pdf
from appe.logic import generate_resume_summary, parse_resume
from appe.templates import generate_pdf_resume, generate_docx_resume, generate_all_previews
from appe.models import User, db
from appe.ats_scorer import calculate_ats_score
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)
UPLOAD_FOLDER = 'Uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
TEMPLATE_STYLES = ["Minimal", "Formal", "Modern"]

# Global model and tokenizer for cover letter generation
model = None
tokenizer = None
device = None
model_path = None

@main.route('/')
def home():
    return render_template('mainhome.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered')

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('main.login'))

    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['email'] = user.email
            return redirect(url_for('main.dashboard'))
        else:
            return render_template('login.html', error='Invalid user')

    return render_template('login.html')

@main.route('/dashboard')
def dashboard():
    if 'email' in session:
        user = User.query.filter_by(email=session['email']).first()
        return render_template('dashboard.html', user=user)
    
    return redirect(url_for('main.login'))

@main.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('main.login'))

@main.route('/resume-enhancer', methods=['GET', 'POST'])
def resume_enhancer():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        resume_file = request.files.get('resume')
        jd_file = request.files.get('jd')
        
        if not resume_file or not jd_file:
            return render_template('resume_enhancer.html', error="Please upload both resume and job description")
        
        if not (resume_file.filename.endswith(('.pdf', '.docx')) and jd_file.filename.endswith(('.pdf', '.docx', '.txt'))):
            return render_template('resume_enhancer.html', error="Invalid file format. Resume must be PDF/DOCX, JD must be PDF/DOCX/TXT")

        resume_filename = secure_filename(resume_file.filename)
        jd_filename = secure_filename(jd_file.filename)
        resume_path = os.path.join(UPLOAD_FOLDER, resume_filename)
        jd_path = os.path.join(UPLOAD_FOLDER, jd_filename)

        try:
            resume_file.save(resume_path)
            jd_file.save(jd_path)

            try:
                resume_text = extract_text_from_resume(resume_path)
                jd_text = extract_text_from_job_desc(jd_path)
                resume_text = re.sub(r'\n\s*\n+', '\n', resume_text).strip()
            except Exception as e:
                return render_template('resume_enhancer.html', error=f"Error parsing files: {str(e)}")

            logger.info(f"Extracted resume text: {resume_text[:100]}...")

            action = request.form.get('action', 'ats')

            if action == 'parse':
                resume_preview = (resume_text[:500] + '...') if len(resume_text) > 500 else resume_text
                jd_preview = (jd_text[:500] + '...') if len(jd_text) > 500 else jd_text
                return render_template('result.html', 
                                    resume_text=resume_preview, 
                                    jd_text=jd_preview,
                                    full_resume_text=resume_text,
                                    full_jd_text=jd_text)
            elif action == 'summarize':
                skill_gap_results = find_skill_gaps(resume_text, jd_text)
                resume_sections = parse_resume_text(resume_text)
                summaries = generate_section_summaries(
                    resume_sections,
                    jd_text,
                    skill_gap_results['matched_skills'],
                    skill_gap_results['all_jd_skills']
                )
                return render_template('summary_result.html',
                                    summaries=summaries,
                                    jd_text=jd_text)
            else:  # action == 'ats'
                jd_title_match = re.search(r'job title:\s*([^\n]+)', jd_text, re.IGNORECASE)
                jd_title = jd_title_match.group(1).strip() if jd_title_match else "data scientist"
                skill_gap_results = find_skill_gaps(resume_text, jd_text)
                ats_results = calculate_ats_score(
                    resume_text, jd_text,
                    skill_gap_results['all_resume_skills'],
                    skill_gap_results['all_jd_skills'],
                    resume_pdf_path=resume_path,
                    jd_title=jd_title
                )
                return render_template('ats_result.html', **ats_results, resume_text=resume_text)

        except Exception as e:
            return render_template('resume_enhancer.html', error=f"Processing error: {str(e)}")
        finally:
            for path in [resume_path, jd_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass

    return render_template('resume_enhancer.html')

@main.route('/create', methods=['GET', 'POST'])
def create_resume():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'GET':
        return render_template('index.html')
    else:  # POST
        data = {
            'name': request.form.get('name', ''),
            'email': request.form.get('email', ''),
            'phone': request.form.get('phone', ''),
            'location': request.form.get('location', ''),
            'linkedin': request.form.get('linkedin', ''),
            'job_title': request.form.get('job_title', ''),
            'experience_years': int(request.form.get('experience_years', 0)),
            'skills': [s.strip() for s in request.form.get('skills', '').split(',') if s.strip()],
            'experience': request.form.get('experience', ''),
            'education': request.form.get('education', ''),
            'projects': request.form.get('projects', ''),
            'certifications': request.form.get('certifications', ''),
            'achievements': request.form.get('achievements', ''),
            'hobbies': request.form.get('hobbies', ''),
            'summary': ''
        }
        if not all([data['name'], data['email'], data['phone'], data['job_title'], data['experience_years'], data['skills']]):
            return render_template('index.html', error="All required fields must be filled")
        
        if data['experience'].strip():
            for exp in data['experience'].split('\n'):
                if exp.strip():
                    parts = exp.split(" - ")
                    if len(parts) < 3:
                        return render_template('index.html', error="Each experience entry must include at least Job Title, Company, and Dates")
                    if len(parts) >= 4 and not parts[3].strip():
                        return render_template('index.html', error="Achievements in experience entries cannot be empty if provided")

        try:
            data['summary'] = generate_resume_summary(
                data['job_title'],
                data['experience_years'],
                data['skills']
            )
            logger.info(f"Generated resume summary: {data['summary']}")
        except Exception as e:
            logger.error(f"Error generating resume summary: {str(e)}")
            return render_template('index.html', error=f"Error generating summary: {str(e)}")

        session['resume_data'] = data
        previews = generate_all_previews(data)
        if not previews.get('template'):
            logger.warning("No template preview generated")
            return render_template('index.html', error="Failed to generate resume preview")
        return render_template('edit_resume.html', data=data, generated_summary=data['summary'], previews=previews, template='template')

@main.route('/download', methods=['POST'])
def download():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    resume_data = session.get('resume_data', {})
    format_type = request.form.get('format', 'pdf')
    template_choice = 'template'

    data = {
        'name': resume_data.get('name', ''),
        'email': resume_data.get('email', ''),
        'phone': resume_data.get('phone', ''),
        'location': resume_data.get('location', ''),
        'linkedin': resume_data.get('linkedin', ''),
        'job_title': resume_data.get('job_title', ''),
        'experience_years': resume_data.get('experience_years', 0),
        'skills': resume_data.get('skills', []),
        'experience': resume_data.get('experience', ''),
        'education': resume_data.get('education', ''),
        'projects': resume_data.get('projects', ''),
        'certifications': resume_data.get('certifications', ''),
        'achievements': resume_data.get('achievements', ''),
        'hobbies': resume_data.get('hobbies', ''),
        'summary': resume_data.get('summary', '')
    }

    try:
        if format_type == 'pdf':
            pdf_path = generate_pdf_resume(data, template_choice)
            logger.info(f"Generated PDF resume for {data['name']}")
            return send_file(pdf_path, as_attachment=True, download_name=f"resume_{data['name'].replace(' ', '_')}.pdf")
        elif format_type == 'docx':
            docx_path = generate_docx_resume(data, template_choice)
            logger.info(f"Generated DOCX resume for {data['name']}")
            return send_file(docx_path, as_attachment=True, download_name=f"resume_{data['name'].replace(' ', '_')}.docx")
        return render_template('edit_resume.html', data=data, error="Invalid format")
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return render_template('edit_resume.html', data=data, error=f"Error generating resume: {str(e)}")

@main.route('/cover_letter_form')
def cover_letter_form():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    resume_data = session.get('resume_data', {})
    form_data = {
        'applicant_name': resume_data.get('name', ''),
        'address': resume_data.get('location', ''),
        'phone': resume_data.get('phone', ''),
        'email': resume_data.get('email', ''),
        'job_title': resume_data.get('job_title', ''),
        'company': '',
        'recruiter': '',
        'company_address': '',
        'experience': '',
        'skills': ', '.join(resume_data.get('skills', [])),
        'template_choice': 'Minimal'
    }
    return render_template('cover_letter_form.html', form_data=form_data, template_styles=TEMPLATE_STYLES)

@main.route('/generate_cover_letter', methods=['POST'])
def generate_cover_letter():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    global model, tokenizer, device, model_path
    form_data = {
        'applicant_name': request.form.get('applicant_name', ''),
        'address': request.form.get('address', ''),
        'phone': request.form.get('phone', ''),
        'email': request.form.get('email', ''),
        'job_title': request.form.get('job_title', ''),
        'company': request.form.get('company', ''),
        'recruiter': request.form.get('recruiter', ''),
        'company_address': request.form.get('company_address', ''),
        'experience': request.form.get('experience', ''),
        'skills': request.form.get('skills', ''),
        'template_choice': request.form.get('template_choice', 'Minimal')
    }
    if not all([form_data['applicant_name'], form_data['job_title'], form_data['company'], form_data['experience']]):
        return render_template('cover_letter_form.html', form_data=form_data, error_message="Please fill in all required fields: Name, Job Title, Company, and Work Experience", template_styles=TEMPLATE_STYLES)
    
    try:
        if model is None or tokenizer is None or device is None:
            logger.info("Model not loaded, initializing...")
            tokenizer, model, device, model_path = load_model()
            logger.info(f"Model loaded on {device}")
            if device.type == "cuda":
                logger.info(f"GPU memory allocated: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")
        
        prompt = build_prompt(form_data)
        letter_body = generate_letter_body(prompt, tokenizer, model, device)
        session['letter_body'] = letter_body
        session['form_data'] = form_data
        styled_letter = apply_template(
            form_data['template_choice'],
            letter_body,
            form_data['applicant_name'],
            form_data['address'],
            form_data['phone'],
            form_data['email'],
            form_data['recruiter'],
            form_data['company'],
            form_data['company_address'],
            form_data['job_title']
        )
        if device.type == "cuda":
            torch.cuda.empty_cache()
            logger.info(f"GPU memory after clearing: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")
    except Exception as e:
        logger.error(f"Error generating letter: {str(e)}")
        return render_template('cover_letter_form.html', form_data=form_data, error_message=f"Error generating letter: {str(e)}", template_styles=TEMPLATE_STYLES)
    
    device_info = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
    return render_template(
        'cover_letter_output.html',
        form_data=form_data,
        styled_letter=styled_letter,
        device_info=device_info,
        model_path=model_path,
        error_message="",
        template_styles=TEMPLATE_STYLES
    )

@main.route('/download_cover_letter/<style>')
def download_cover_letter(style):
    if 'email' not in session:
        return redirect(url_for('main.login'))

    global model, tokenizer, device
    if style not in TEMPLATE_STYLES:
        logger.error(f"Invalid template style: {style}")
        return "Invalid template style", 400

    letter_body = session.get('letter_body', '')
    form_data = session.get('form_data', {})
    if not letter_body or not form_data:
        logger.error("No letter content or form data available for download")
        return "No letter content available for download", 400

    try:
        styled_letter = apply_template(
            style,
            letter_body,
            form_data.get('applicant_name', ''),
            form_data.get('address', ''),
            form_data.get('phone', ''),
            form_data.get('email', ''),
            form_data.get('recruiter', ''),
            form_data.get('company', ''),
            form_data.get('company_address', ''),
            form_data.get('job_title', '')
        )
        pdf_buffer = generate_pdf(styled_letter, style)
        logger.info(f"Generated PDF for {style} style cover letter")
        if device and device.type == "cuda":
            torch.cuda.empty_cache()
            logger.info(f"GPU memory after PDF generation: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"cover_letter_{style.lower()}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        return f"Error generating PDF: {str(e)}", 500

@main.route('/cover-letter-generator', methods=['GET', 'POST'])
def cover_letter_generator():
    if 'email' not in session:
        return redirect(url_for('main.login'))

    if 'email' not in session:
        return redirect(url_for('main.login'))

    global model, tokenizer, device, model_path
    default_form = {
        'applicant_name': '',
        'address': '',
        'phone': '',
        'email': '',
        'job_title': '',
        'company': '',
        'recruiter': '',
        'company_address': '',
        'experience': '',
        'skills': '',
        'template_choice': 'Minimal'
    }

    form_data = {key: request.form.get(key, val) for key, val in default_form.items()}
    styled_letter = ""
    error_message = ""

    if request.method == 'POST':
        template_choice = form_data['template_choice']
        if template_choice not in TEMPLATE_STYLES:
            logger.error(f"Invalid template style selected: {template_choice}")
            error_message = "Invalid template style selected."
        else:
            try:
                if model is None or tokenizer is None or device is None:
                    logger.info("Model not loaded, initializing...")
                    tokenizer, model, device, model_path = load_model()
                    logger.info(f"Model loaded on {device}")
                    if device.type == "cuda":
                        logger.info(f"GPU memory allocated: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")
                
                prompt = build_prompt(form_data)
                letter_body = generate_letter_body(prompt, tokenizer, model, device)
                session['letter_body'] = letter_body
                session['form_data'] = form_data
                styled_letter = apply_template(
                    template_choice,
                    letter_body,
                    form_data['applicant_name'],
                    form_data['address'],
                    form_data['phone'],
                    form_data['email'],
                    form_data['recruiter'],
                    form_data['company'],
                    form_data['company_address'],
                    form_data['job_title']
                )
                logger.info(f"Generated cover letter with {template_choice} style.")
                
                if device.type == "cuda":
                    torch.cuda.empty_cache()
                    logger.info(f"GPU memory after clearing: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")
                
                return render_template('cover_letter_result.html',
                                    styled_letter=styled_letter,
                                    form_data=form_data,
                                    template_styles=TEMPLATE_STYLES)
            except Exception as e:
                logger.error(f"Error generating cover letter: {str(e)}")
                error_message = f"Error generating cover letter: {str(e)}"
                if device and device.type == "cuda":
                    torch.cuda.empty_cache()
                    logger.info(f"GPU memory after error clearing: {torch.cuda.memory_allocated(0)/1e9:.2f} GB")

    return render_template('cover_letter_generator.html',
                        form_data=form_data,
                        template_styles=TEMPLATE_STYLES,
                        error_message=error_message)